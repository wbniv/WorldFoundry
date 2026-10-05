"""APK-derived artwork checks on real HOME tiles, inside a coordinator lease."""
import hashlib
import io
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image, ImageChops, ImageDraw, ImageStat

# Reviewed Google TV launchers. Will authorized data reset for stale artwork on
# 2026-10-05; this resets HOME layout, never the game's data.
REFRESHABLE = {'com.google.android.apps.tv.launcherx', 'com.google.android.tvlauncher'}


def apk_references(path, aapt, out):
    def dump(*args):
        return subprocess.check_output([aapt, 'dump', *args, str(path)] if args == ('badging',)
                                       else [aapt, 'dump', *args[:1], str(path), *args[1:]],
                                       timeout=20, text=True)
    badging = dump('badging')
    app = re.search(r"^application: (.+)$", badging, re.M)
    if not app:
        raise RuntimeError('Cannot resolve APK launcher artwork')
    attrs = dict(re.findall(r"(label|icon|banner)='([^']*)'", app[1]))
    package = re.search(r"^package: name='([^']+)'", badging, re.M)[1]
    activity = re.search(r"^(?:leanback-)?launchable-activity: (.+)$", badging, re.M)
    if activity:
        attrs.update({k: v for k, v in re.findall(r"(label|icon|banner)='([^']*)'", activity[1]) if v})
    resources = subprocess.check_output([aapt, 'dump', '--values', 'resources', str(path)], timeout=20, text=True)
    values = {}
    current = None
    for line in resources.splitlines():
        m = re.search(r'^\s+resource (0x[0-9a-f]+) .*: t=', line)
        if m:
            current = m[1]
        m = re.search(r'\(string8?\) "(res/[^\"]+)"', line)
        if m and current:
            values.setdefault(current, []).append(m[1])
    references = []
    with zipfile.ZipFile(path) as bundle:
        for kind in ('banner', 'icon'):
            name = attrs.get(kind)
            if not name:
                continue
            names = [name]
            if name.endswith('.xml'):
                tree = dump('xmltree', name)
                # Resolve raster fallback for the exact primary icon resource,
                # never include another activity's unrelated icon.
                ids = [rid for rid, paths in values.items() if name in paths]
                names = [n for rid in ids for n in values[rid] if n.endswith('.png')]
                fg = re.search(r'E: foreground.*?drawable\([^)]*\)=@(0x[0-9a-f]+)', tree, re.S)
                if fg:
                    for n in values.get(fg[1], []):
                        if n.endswith('.png'):
                            # Adaptive icons expose their central 72dp viewport
                            # from a 108dp canvas. Preserve the actual PNG too.
                            image = Image.open(io.BytesIO(bundle.read(n))).convert('RGBA')
                            w, h = image.size
                            image = image.crop((w//6, h//6, w*5//6, h*5//6))
                            refs_name = 'expected-adaptive-' + str(len(references)) + '.png'
                            image.save(out/refs_name)
                            references.append({'kind': 'icon', 'resource': n, 'image': image, 'file': refs_name,
                                               'sha256': hashlib.sha256(bundle.read(n)).hexdigest()})
            for name in dict.fromkeys(names):
                if not name.endswith('.png'):
                    continue
                data = bundle.read(name)
                image = Image.open(io.BytesIO(data)).convert('RGBA')
                filename = 'expected-' + kind + '-' + str(len(references)) + '.png'
                image.save(out/filename)
                references.append({'kind': kind, 'resource': name, 'image': image, 'file': filename,
                                   'sha256': hashlib.sha256(data).hexdigest()})
    if not references:
        raise RuntimeError('No supported raster launcher reference in APK; artwork unverified')
    metadata = {'package': package, 'label': attrs.get('label'), 'apk_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'references': [{k: v for k, v in r.items() if k != 'image'} for r in references]}
    (out/'references.json').write_text(json.dumps(metadata, indent=2))
    return metadata, references


def bounds(node):
    m = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
    if not m:
        return None
    box = tuple(map(int, m.groups()))
    return box if box[2] > box[0] and box[3] > box[1] else None


def tile_boxes(xml, label, size):
    root = ET.fromstring(xml)
    parents = {child: node for node in root.iter() for child in node}
    matches = [n for n in root.iter('node') if n.get('text', '').strip() == label
               or n.get('content-desc', '').strip() == label]
    result = []
    for node in matches:
        # A label may be a child of the image/tile container. Ignore page-sized
        # ancestors and never scan arbitrary parts of the screen for similar art.
        for _ in range(4):
            box = bounds(node)
            if box and 40 <= box[2]-box[0] <= size[0]*.65 and 40 <= box[3]-box[1] <= size[1]*.65:
                result.append(box)
            node = parents.get(node)
            if node is None:
                break
    return list(dict.fromkeys(result))


def compare_tile(screen, boxes, references):
    best = None
    for box in boxes:
        x, y, right, bottom = box
        for ref in references:
            expected = ref['image']
            aspect = expected.width / expected.height
            # Insets allow launcher focus borders/padding, not arbitrary crops.
            for inset in (0, .025, .05, .075, .1):
                w = (right-x)*(1-2*inset)
                h = w/aspect
                if h > bottom-y+3:
                    continue
                left = x+(right-x)*inset
                top = y+(right-x)*inset
                crop_box = (round(left), round(top), round(left+w), round(top+h))
                if crop_box[2] > screen.width or crop_box[3] > screen.height:
                    continue
                actual = screen.crop(crop_box).convert('RGB').resize((48, 48), Image.Resampling.LANCZOS)
                wanted = expected.convert('RGB').resize((48, 48), Image.Resampling.LANCZOS)
                # Exclude the focus ring and mask corners, while retaining the
                # bottom-right badge inside the icon's circular safe area.
                mask = Image.new('L', (48,48), 0)
                draw = ImageDraw.Draw(mask)
                if ref['kind']=='icon':draw.ellipse((2,2,45,45),fill=255)
                else:draw.rectangle((2,2,45,45),fill=255)
                mean_a, mean_b = ImageStat.Stat(actual,mask).mean, ImageStat.Stat(wanted,mask).mean
                gain = sum(mean_a)/max(1, sum(mean_b))
                comparable_brightness = .65 <= gain <= 1.3
                # A recognizable tile with wildly different brightness is a
                # mismatch, not missing geometry. Keep its score so stale-cache
                # recovery runs; limit gain correction so it cannot hide it.
                correction = min(1.3,max(.65,gain))
                wanted = wanted.point(lambda value: min(255, round(value*correction)))
                difference = ImageChops.difference(actual, wanted)
                delta = ImageStat.Stat(difference,mask)
                error = sum(delta.mean)/3
                rms = sum(delta.rms)/3
                # A bland uniform image cannot establish which artwork is shown.
                textured = sum(ImageStat.Stat(wanted,mask).stddev)/3 >= 12
                local_errors=[]
                for by in range(3):
                    for bx in range(3):
                        region=(bx*16,by*16,(bx+1)*16,(by+1)*16)
                        local=ImageStat.Stat(difference.crop(region),mask.crop(region))
                        local_errors.append(sum(local.mean)/3)
                worst_local=max(local_errors)
                score = {'bounds': crop_box, 'reference': ref['file'], 'resource': ref['resource'],
                         'kind': ref['kind'], 'mean_absolute_error': error, 'rms_error': rms,
                         'worst_region_error':worst_local,
                         'brightness_gain': gain, 'verified': comparable_brightness and textured and error <= 15 and rms <= 24 and worst_local <= 28}
                if best is None or (error+rms) < (best['mean_absolute_error']+best['rms_error']):
                    best = score
    return best or {'verified': False, 'reason': 'No identifiable tile geometry or comparable artwork'}


def verify(adapter):
    out = adapter.out/'launcher'; out.mkdir(exist_ok=True)
    expected = adapter.store.root/'inputs'/adapter.job['installation']
    installed = adapter.shell('pm', 'path', adapter.package).strip().removeprefix('package:')
    actual_hash = adapter.shell('sha256sum', installed).split()[0]+'.apk'
    if actual_hash != adapter.job['installation']:
        return {'status': 'superseded', 'expected': adapter.job['installation'], 'installed': actual_hash}
    metadata, references = apk_references(expected, adapter.config['aapt'], out)
    if metadata['package'] != adapter.package or not metadata['label']:
        raise RuntimeError('Launcher reference package/label does not match installation')
    component = adapter.shell('cmd', 'package', 'resolve-activity', '--brief', '-a', 'android.intent.action.MAIN',
                              '-c', 'android.intent.category.HOME').strip().splitlines()[-1]
    if not re.fullmatch(r'[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+', component):
        raise RuntimeError('Cannot resolve HOME launcher')
    package = component.split('/')[0]
    adapter.launcher_touched = True
    result = {'status': 'unverified', 'home': component, 'apk': adapter.job['installation'], 'attempts': []}
    (out/'result.json').write_text(json.dumps(result, indent=2))

    def ui(name):
        remote = '/data/local/tmp/wf-'+adapter.job['id']+'-launcher.xml'
        if remote not in adapter.capture_remote:
            adapter.capture_remote.append(remote)
        adapter.shell('uiautomator', 'dump', '--compressed', remote, timeout=20)
        xml = adapter.shell('cat', remote)
        (out/(name+'.xml')).write_text(xml)
        return xml

    for attempt in range(3):
        adapter.store.phase(adapter.job['id'], 'verifying-launcher' if attempt == 0 else 'refreshing-launcher')
        if attempt:
            if package not in REFRESHABLE:
                break
            if attempt==2:
                # A reset is justified by an identified mismatching tile, not
                # merely by inability to locate the app in the hierarchy.
                if not any('mean_absolute_error' in a for a in result['attempts']):
                    break
                cleared=adapter.shell('pm','clear',package,timeout=30)
                if 'Success' not in cleared:
                    raise RuntimeError('Launcher data reset failed: '+cleared[:500])
                operation='launcher-data-reset-and-home'
            else:
                adapter.shell('am', 'force-stop', package)
                operation='launcher-force-stop-and-home'
            result.setdefault('refreshes',[]).append({'operation':operation,'package':package})
        adapter.shell('am', 'start', '-W', '-n', component)
        adapter.wait(3)
        for step in range(10):
            if not any(package+'/' in line for line in adapter.foreground()):
                raise RuntimeError('HOME launcher left foreground during artwork verification')
            name = 'attempt-'+str(attempt+1)+'-view-'+str(step+1)
            xml = ui(name)
            image = Image.open(io.BytesIO(adapter.adb('exec-out', 'screencap', '-p', binary=True))).convert('RGB')
            if max(ImageStat.Stat(image).mean)<1:
                # Some TV builds return black from ordinary screencap. Use the
                # already-reviewed UI Automation helper rather than accepting a
                # blank image or resetting a launcher based on it.
                image.save(out/(name+'-screencap-black.png'))
                from .capture import capture_current
                previous_out, previous_req = adapter.out, adapter.req
                try:
                    adapter.out=out
                    adapter.req=dict(previous_req,method='uiautomation')
                    capture_current(adapter)
                    image=Image.open(out/'uiautomation.png').convert('RGB')
                finally:
                    adapter.out, adapter.req = previous_out, previous_req
                if max(ImageStat.Stat(image).mean)<1:
                    raise RuntimeError('Both screen capture methods are blank; launcher artwork unverified')
            image.save(out/(name+'.png'))
            boxes = tile_boxes(xml, metadata['label'], image.size)
            if boxes:
                score = compare_tile(image, boxes, references)
                score.update({'screenshot': name+'.png', 'hierarchy': name+'.xml', 'attempt': attempt+1})
                result['attempts'].append(score)
                if score['verified']:
                    image.crop(score['bounds']).save(out/'verified-tile.png')
                    result['status'] = 'verified'
                # The identified tile's stale art requires refresh, not scanning
                # unrelated artwork elsewhere for a coincidental match.
                break
            nodes = list(ET.fromstring(xml).iter('node'))
            navigation = next((n for label in ('See all', 'View all', 'Your apps', 'Apps') for n in nodes
                               if (n.get('text') == label or n.get('content-desc') == label) and bounds(n)), None)
            if navigation is not None and step < 3:
                box = bounds(navigation)
                adapter.shell('input', 'tap', (box[0]+box[2])//2, (box[1]+box[3])//2)
            else:
                # Horizontal app rows; only navigation keys, never OK on an app.
                adapter.key('KEYCODE_DPAD_RIGHT')
            adapter.wait(1)
        (out/'result.json').write_text(json.dumps(result, indent=2))
        if result['status'] == 'verified':
            return result
    result['status'] = 'failed'
    result['error'] = 'APK installed, but launcher artwork is stale or unverified after bounded recovery; inspect launcher evidence.'
    (out/'result.json').write_text(json.dumps(result, indent=2))
    return result
