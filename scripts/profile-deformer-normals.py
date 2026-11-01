#!/usr/bin/env python3
"""Before/after Chromecast profile of the deformer face-normal fix (docs/plans/2026-11-01-deformer-face-normals.md).

  prepare   --before APK --after APK --out DIR   freeze both release APKs, add --frame-profile copies,
                                                 and write one variant-benchmark recipe per tank
  summarize EVIDENCE... --out FILE.json          fps, frame-time percentiles and CPU sections per variant
  frames    --pixel-before PNG --pixel-after PNG --cast DIR --out PAGE.html
                                                 a 1440x900 page of real device frames for the plan bundle

Device work is submitted separately, one job per recipe:
  task chromecast:submit DEVICE=chromecast-test-01 RECIPE=DIR/recipe-<scene>.json ASYNC=true
Each recipe alternates before, after, before, after (two runs each) so drift shows, then one
--frame-profile run of each build for the CPU sections. The restoration APK is the after build.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
# Every tank with a species deformer, by the coordinator's aquarium scene names.
SCENES = ['clownfish', 'betta', 'jellyfish', 'lionfish', 'planted-tank', 'arowana', 'tiger-barbs']


def run(args):
    subprocess.run([str(a) for a in args], check=True)


def with_frame_profile(apk, out, build_tools, keystore):
    """The same APK with --frame-profile appended to assets/wf_args.txt, re-signed with the debug key."""
    unsigned, aligned = out.with_suffix('.unsigned.apk'), out.with_suffix('.aligned.apk')
    with zipfile.ZipFile(apk) as src, zipfile.ZipFile(unsigned, 'w') as dst:
        args = src.read('assets/wf_args.txt').decode() if 'assets/wf_args.txt' in src.namelist() else ''
        for info in src.infolist():
            name = info.filename
            if name == 'assets/wf_args.txt' or (name.startswith('META-INF/') and (
                    name.endswith(('.SF', '.RSA', '.DSA')) or name == 'META-INF/MANIFEST.MF')):
                continue
            dst.writestr(info, src.read(name))
        dst.writestr('assets/wf_args.txt', args.rstrip('\n') + ('\n' if args.strip() else '') + '--frame-profile\n')
    run([build_tools / 'zipalign', '-f', '-p', '4', unsigned, aligned])
    run([build_tools / 'apksigner', 'sign', '--ks', keystore, '--ks-key-alias', 'androiddebugkey',
         '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', out, aligned])
    run([build_tools / 'apksigner', 'verify', out])
    unsigned.unlink(); aligned.unlink()


def prepare(a):
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    apks = {}
    for label, source in (('before', a.before), ('after', a.after)):
        frozen = out / f'{label}.apk'
        shutil.copyfile(source, frozen)
        apks[label] = frozen
        with_frame_profile(frozen, out / f'{label}-cpu.apk', a.build_tools, a.keystore)
        apks[label + '-cpu'] = out / f'{label}-cpu.apk'
    variants = []
    for round_ in (1, 2):
        for label in ('before', 'after'):
            variants.append({'label': f'{label}-{round_}', 'apk': str(apks[label]), 'runs': 2, 'warmup': a.warmup})
    for label in ('before', 'after'):
        variants.append({'label': f'{label}-cpu', 'apk': str(apks[label + '-cpu']), 'runs': 1, 'warmup': a.warmup})
    for scene in SCENES:
        recipe = {'workflow': 'variant-benchmark', 'app': 'aquarium', 'scene': scene, 'apk': str(apks['after']),
                  'restore_apk': str(apks['after']), 'trace': 'idle', 'duration': a.duration, 'variants': variants}
        (out / f'recipe-{scene}.json').write_text(json.dumps(recipe, indent=2) + '\n')
    hashes = {k: hashlib.sha256(v.read_bytes()).hexdigest() for k, v in apks.items()}
    (out / 'hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
    print(json.dumps(hashes, indent=2))


def cpu_window(log):
    """--frame-profile sections of the last launch in a wf.log (the log keeps earlier launches).

    The engine prints one window every 5 s. Each section gets the mean of the launch's windows after
    the first (which spans level load), with the window-to-window min and max as the spread; counters
    come from the last window.
    """
    session = log.rsplit('=== wf_game android_main', 1)[-1]
    windows = session.split('frame-window:')[1:]
    windows = windows[1:] if len(windows) > 2 else windows      # the first window spans level load
    sections = {}
    for window in windows:
        for n, f, m in re.findall(r'frame-profile: ([\w-]+) frames=(\d+) mean=([\d.]+)', window):
            sections.setdefault(n, []).append(float(m))
    means = {n: {'windows': len(v), 'mean': round(statistics.mean(v), 4), 'min': min(v), 'max': max(v)}
             for n, v in sections.items()}
    last = windows[-1] if windows else ''
    counts = {n: float(v) for n, v in re.findall(r'frame-count: ([\w-]+) frames=\d+ mean=([\d.]+)', last)}
    return means, counts


def summarize(a):
    rows = []
    for evidence in a.evidence:
        # task chromecast:evidence OUT=<dir> puts the variants directly in <dir>; older layouts nest J-*/.
        jobs = [evidence] if any(evidence.glob('*/run-*/summary.json')) else sorted(
            p for p in evidence.rglob('J-*') if p.is_dir())
        for job in jobs:
            for variant in sorted(p for p in job.iterdir() if p.is_dir()):
                runs = [json.loads(p.read_text()) for p in sorted(variant.glob('run-*/summary.json'))]
                if not runs:
                    continue
                row = {'job': job.name, 'variant': variant.name,
                       'fps': [round(r['fps'], 2) for r in runs], 'p50_ms': [r['p50_ms'] for r in runs],
                       'p95_ms': [r['p95_ms'] for r in runs], 'missed_refresh_percent':
                           [round(r['missed_refresh_percent'], 2) for r in runs]}
                log = variant / 'run-1' / 'wf.log'
                if variant.name.endswith('-cpu') and log.exists():
                    row['cpu_ms'], row['counters'] = cpu_window(log.read_text(errors='replace'))
                rows.append(row)
    a.out.write_text(json.dumps(rows, indent=2) + '\n')
    print(a.out)


FRAMES_PAGE = '''<!DOCTYPE html>
<!-- Generated by scripts/profile-deformer-normals.py frames; do not edit by hand. -->
<html lang="en"><head><meta charset="utf-8"><title>Mockup — device frames</title>
<style>
:root{--bg:#fff;--fg:#1f2328;--muted:#656d76;--line:#d1d9e0;--panel:#f6f8fa}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;--line:#30363d;--panel:#161b22}}
*{box-sizing:border-box}body{margin:0;width:1440px;height:900px;overflow:hidden;background:var(--bg);color:var(--fg);
font:13px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
header{display:flex;align-items:center;padding:12px 24px;border-bottom:1px solid var(--line);background:var(--panel);height:52px}
header h1{margin:0;font-size:16px;font-weight:600}header .tag{margin-left:auto;font:600 11px ui-monospace,Menlo,monospace;
color:var(--muted);border:1px solid var(--line);border-radius:10px;padding:2px 8px}
main{padding:14px 24px;display:grid;grid-template-columns:1fr 1fr;gap:14px 24px}
h2{font-size:14px;margin:0 0 6px}p{margin:0 0 8px;color:var(--muted)}
figure{margin:0}figure img{width:100%%;display:block;border:1px solid var(--line);border-radius:6px}
figcaption{color:var(--muted);font-size:12px;margin-top:3px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
</style></head><body>
<header><h1>Real device frames — Pixel 8 Pro before/after, cast1 after</h1>
<span class="tag">DEVICE SCREENSHOTS, NOT MOCKUP DRAWINGS</span></header>
<main>
<section><h2>Pixel 8 Pro — Lionfish, BEFORE (609fca52)</h2>
<figure><img src="%(pb)s" alt="Lionfish tank before the fix"><figcaption>%(pbc)s</figcaption></figure></section>
<section><h2>Pixel 8 Pro — Lionfish, AFTER (611cc679)</h2>
<figure><img src="%(pa)s" alt="Lionfish tank after the fix"><figcaption>%(pac)s</figcaption></figure></section>
<section style="grid-column:1/3"><h2>Chromecast HD (cast1) — every tank of the selector, AFTER build (menu-back check J‑5332f869244c)</h2>
<p>The two Pixel frames are different moments of free-swimming fish, so the poses are not matched; a per-face difference is not visible at this scale. The controlled before/after comparison at a matched extreme pose is the canvas re-render in the other pages.</p>
<div class="grid">%(cast)s</div></section>
</main></body></html>
'''


def frames(a):
    import base64
    import io
    from PIL import Image

    def uri(path, width, crop=None, quality=72):
        im = Image.open(path).convert('RGB')
        if crop:
            im = im.crop(crop)
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, 'JPEG', quality=quality, optimize=True)
        return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()

    pixel_crop = (700, 230, 2000, 700)          # the tank interior around the two lionfish (2244x1008 frames)
    cast = ''.join(f'<figure><img src="{uri(p, 320, quality=60)}" alt="{p.stem}"><figcaption>{p.stem.replace("-screenshot", "")}'
                   f'</figcaption></figure>' for p in sorted(a.cast.glob('*-screenshot.png')))
    html = FRAMES_PAGE % {'pb': uri(a.pixel_before, 680, pixel_crop), 'pa': uri(a.pixel_after, 680, pixel_crop),
                          'pbc': f'{a.pixel_before.parent.parent.name}/{a.pixel_before.parent.name}, idle segment',
                          'pac': f'{a.pixel_after.parent.parent.name}/{a.pixel_after.parent.name}, idle segment',
                          'cast': cast}
    a.out.write_text(html)
    print(a.out, len(html) // 1024, 'KB')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)
    x = sub.add_parser('prepare')
    x.add_argument('--before', type=Path, required=True); x.add_argument('--after', type=Path, required=True)
    x.add_argument('--out', type=Path, required=True)
    x.add_argument('--warmup', type=int, default=15); x.add_argument('--duration', type=int, default=20)
    x.add_argument('--build-tools', type=Path, default=Path.home() / 'android-sdk-local/build-tools/34.0.0')
    x.add_argument('--keystore', type=Path, default=Path.home() / '.android/debug.keystore')
    x.set_defaults(func=prepare)
    x = sub.add_parser('summarize')
    x.add_argument('evidence', type=Path, nargs='+'); x.add_argument('--out', type=Path, required=True)
    x.set_defaults(func=summarize)
    x = sub.add_parser('frames', help='device-frame page for the plan bundle')
    x.add_argument('--pixel-before', type=Path, required=True); x.add_argument('--pixel-after', type=Path, required=True)
    x.add_argument('--cast', type=Path, required=True, help='menu-back evidence dir with <scene>-screenshot.png')
    x.add_argument('--out', type=Path, required=True)
    x.set_defaults(func=frames)
    a = p.parse_args()
    a.func(a)
    return 0


if __name__ == '__main__':
    sys.exit(main())
