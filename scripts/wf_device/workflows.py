"""Reviewed device operations: no caller shell, scripts, or executable adapters."""
import fcntl
import hashlib
import json
import os
import re
import shlex
import signal
import statistics
import subprocess
import time
import zipfile
from pathlib import Path
from .store import Store

APPS = {'aquarium', 'condo', 'snowgoons', 'smb', 'qbert'}
SCENES = ['clownfish', 'blue-shrimp', 'betta', 'jellyfish', 'lionfish', 'planted-tank', 'arowana', 'tiger-barbs']

class Cancelled(Exception):
    pass

class NeedsSetup(Exception):
    pass

class Adapter:
    def __init__(self, store, job, config):
        self.store, self.job, self.config = store, job, config
        self.device = next(d for d in store.devices() if d['id'] == job['device'])
        self.req = dict(job['request'])
        self.out = store.root/'evidence'/job['id']
        self.out.mkdir(exist_ok=True)
        self.cleanup_mode = False
        self.uncertain_install = False
        self.record_pid = None
        self.process = None
        self.commands = []
        self.restoration = None
        self.previous = None
        self.identity_verified = False
        self.lock_fd = None
        self.package = ('org.worldfoundry.wf_game' +
                        ('' if self.req.get('app') == 'snowgoons' else '.'+self.req.get('app', 'aquarium')))
        self.env = dict(os.environ)
        if config.get('adb_socket'):
            self.env['ADB_SERVER_SOCKET'] = config['adb_socket']
        self.env['ANDROID_USER_HOME'] = config.get('adb_home', str(Path.home()/'.android'))
        self.env['ADB_VENDOR_KEYS'] = self.env['ANDROID_USER_HOME']+'/adbkey'
        self.selector = self.device.get('endpoint')

    def guard(self):
        job = self.store.validate_lease(self.job['id'], self.job['device'], self.job['generation'])
        if job['cancel'] and not self.cleanup_mode:
            raise Cancelled('Owner requested cancellation')

    def wait(self, seconds):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            self.guard()
            time.sleep(min(.1, max(0, deadline-time.monotonic())))

    def adb(self, *args, binary=False, timeout=30, allow_failure=False, target=True):
        self.guard()
        command = [self.config['adb']]+(['-s', self.selector] if target else [])+list(args)
        started = time.time()
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, pass_fds=((self.lock_fd,) if self.lock_fd is not None else ()))
        try:
            deadline = time.monotonic()+timeout
            while True:
                try:
                    stdout, stderr = self.process.communicate(timeout=.2)
                    break
                except subprocess.TimeoutExpired:
                    self.guard()
                    if time.monotonic() >= deadline:
                        raise TimeoutError('ADB command exceeded bounded timeout')
            if self.process.returncode and not allow_failure:
                raise RuntimeError('ADB failed: '+stderr.decode(errors='replace')[:1000])
            return stdout if binary else stdout.decode(errors='replace')
        finally:
            if self.process.poll() is None:
                if args and args[0]=='install':
                    self.uncertain_install=True
                self.process.terminate()
                try:
                    self.process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.communicate()
            self.commands.append({'args': list(args), 'start': started, 'end': time.time(),
                                  'returncode': self.process.returncode})
            self.process = None

    def shell(self, *args, **kwargs):
        # Android joins shell arguments. Quote each word, including generated layer names.
        return self.adb('shell', ' '.join(shlex.quote(str(a)) for a in args), **kwargs)

    def key(self, code):
        self.shell('input', 'keyevent', code)
        self.wait(.15)

    def pair(self, setup):
        self.guard()
        self.store.phase(self.job['id'],'pairing')
        process=subprocess.Popen([self.config['adb'],'pair',setup['endpoint']],
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                 env=self.env,pass_fds=(self.lock_fd,))
        try:
            output,_=process.communicate((setup['code']+'\n').encode(),timeout=20)
            if process.returncode or b'Successfully paired' not in output:
                raise NeedsSetup('Pairing failed; obtain a fresh pairing endpoint/code from the TV')
        except subprocess.TimeoutExpired:
            process.kill();process.communicate()
            raise NeedsSetup('Pairing timed out; reopen the TV pairing screen')
        finally:
            setup.clear()

    def connect(self):
        self.store.phase(self.job['id'], 'connecting')
        if self.device['transport'] == 'tls':
            deadline=time.monotonic()+5
            while True:
                services = self.adb('mdns', 'services', target=False)
                matches = [line.split() for line in services.splitlines()
                           if '_adb-tls-connect._tcp' in line and
                           line.split()[0].startswith('adb-'+self.device['serial']+'-')]
                if matches or time.monotonic()>=deadline:break
                self.wait(.5)
            if len(matches) != 1:
                raise NeedsSetup('No unique advertised connection for expected serial; enable Wireless debugging on the TV')
            self.selector = matches[0][-1]
        else:
            self.selector = self.device['endpoint']
            if self.req.get('address'):
                self.selector=self.req['address']+':'+self.selector.rsplit(':',1)[1]
            elif self.device.get('cast_udn'):
                from .discovery import rediscover
                try:host=rediscover(self.selector.rsplit(':',1)[0],self.device['cast_udn'],guard=self.guard)
                except RuntimeError as exc:raise NeedsSetup(str(exc)) from exc
                self.selector=host+':'+self.selector.rsplit(':',1)[1]
        connected = self.adb('connect', self.selector, target=False, allow_failure=True)
        if 'failed' in connected.lower() or 'cannot' in connected.lower():
            raise NeedsSetup('Connect failed; enable debugging and authorize this service host on the TV')
        try:
            actual = self.shell('getprop', 'ro.serialno').strip()
        except RuntimeError as exc:
            raise NeedsSetup('Host authorization required on the TV') from exc
        if actual != self.device['serial']:
            raise RuntimeError('Hardware serial mismatch; refusing this endpoint')
        self.identity_verified = True
        self.device['endpoint'] = self.selector
        self.device['last_seen'] = time.time()
        self.previous_boot=self.device.get('boot_id')
        self.device['boot_id']=self.shell('cat','/proc/sys/kernel/random/boot_id').strip()
        for key, prop in [('model','ro.product.model'), ('android','ro.build.version.release'),
                          ('sdk','ro.build.version.sdk'), ('device','ro.product.device')]:
            self.device[key] = self.shell('getprop', prop).strip()
        self.device['abis'] = self.shell('getprop','ro.product.cpu.abilist').strip().split(',')
        addresses=self.shell('ip','-6','addr','show','wlan0',allow_failure=True)
        self.device['ipv6_addresses']=re.findall(r'inet6 ([0-9a-fA-F:]+)/',addresses)
        self.store.update_device(self.device['id'], self.device)

    def foreground(self):
        raw = self.shell('dumpsys', 'activity', 'activities')
        return [line for line in raw.splitlines() if 'topResumedActivity=' in line or 'mResumedActivity:' in line]

    def require_foreground(self):
        self.guard()
        if not any(self.package+'/' in line for line in self.foreground()):
            raise RuntimeError('Target app left foreground; measurement invalid')
        if not self.shell('pidof', self.package, allow_failure=True).strip():
            raise RuntimeError('Target process exited')

    def launch(self, scene=None):
        self.shell('am','force-stop',self.package)
        self.key('KEYCODE_WAKEUP')
        result = self.shell('am','start','-W','-n',self.package+'/android.app.NativeActivity')
        if 'Error' in result or 'Exception' in result:
            raise RuntimeError('App launch failed: '+result[:1000])
        self.wait(self.config.get('launch_wait', 5))
        self.require_foreground()
        self.dismiss_panel()
        if scene:
            index = self.config.get('scenes', SCENES).index(scene)
            for _ in range(index):
                self.key('KEYCODE_DPAD_DOWN')
            self.key('KEYCODE_DPAD_CENTER')
            self.wait(2)
            self.require_foreground()
            log = self.shell('cat', '/sdcard/Android/data/'+self.package+'/files/wf.log', allow_failure=True)
            if f'level-menu: level {index} starts' not in log:
                log += self.adb('logcat','-d','-v','brief')
            if f'level-menu: level {index} starts' not in log:
                raise RuntimeError('Scene selection was not confirmed in engine log')

    def dismiss_panel(self):
        apk = self.req.get('apk')
        if apk:
            with zipfile.ZipFile(self.store.root/'inputs'/apk) as bundle:
                if 'assets/layout.json' not in bundle.namelist():
                    return
            self.key('KEYCODE_BACK')
            self.wait(1)
            self.require_foreground()

    def capture(self, prefix=''):
        self.require_foreground()
        self.out.joinpath(prefix+'screenshot.png').write_bytes(self.adb('exec-out','screencap','-p',binary=True))
        pid = self.shell('pidof',self.package).strip().split()[0]
        self.out.joinpath(prefix+'logcat.txt').write_text(self.adb('logcat','-d','-v','threadtime','--pid='+pid))
        self.out.joinpath(prefix+'wf.log').write_text(self.shell('cat','/sdcard/Android/data/'+self.package+'/files/wf.log',allow_failure=True))
        self.out.joinpath(prefix+'meminfo.txt').write_text(self.shell('dumpsys','meminfo',self.package))
        self.out.joinpath(prefix+'thermal.txt').write_text(self.shell('dumpsys','thermalservice'))
        log = (self.out/(prefix+'logcat.txt')).read_text() + (self.out/(prefix+'wf.log')).read_text().rsplit('=== wf_game android_main',1)[-1]
        if any(word in log for word in ('Fatal signal','ASSERTION FAILED','zforth compile error','zforth eval error')):
            raise RuntimeError('Runtime failure in captured logs')

    def install(self, name):
        self.store.phase(self.job['id'],'installing')
        path = self.store.root/'inputs'/name
        if hashlib.sha256(path.read_bytes()).hexdigest()+'.apk' != name:
            raise RuntimeError('Staged input hash mismatch')
        with zipfile.ZipFile(path) as bundle:
            abis = {n.split('/')[1] for n in bundle.namelist() if n.startswith('lib/')}
        if not abis.intersection(self.device['abis']):
            raise ValueError('APK has no compatible native ABI')
        badging = subprocess.check_output([self.config['aapt'], 'dump', 'badging', str(path)], timeout=15, text=True)
        match = re.search(r"package: name='([^']+)'",badging)
        if not match or match[1] != self.package:
            raise ValueError('APK package does not match requested app')
        if self.req.get('scene'):
            with zipfile.ZipFile(path) as bundle:
                data = bundle.read('assets/cd.iff')
            if b'level-menu' not in data:
                raise ValueError('Named scene requires a menu APK; standalone variant must omit scene')
        result = self.adb('install','-r',str(path),timeout=90)
        if 'Success' not in result:
            raise RuntimeError('APK installation unsuccessful: '+result[:1000])
        installed = self.shell('pm','path',self.package).strip().removeprefix('package:')
        actual = self.shell('sha256sum',installed).split()[0]
        if actual+'.apk' != name:
            raise RuntimeError('Installed APK hash does not match immutable input')

    def profile(self, prefix=''):
        results = []
        traces = {
            'idle': [('idle', None)],
            'swarm': [('swarm', None)],
            'all': [('swarm', None), ('school-right','KEYCODE_DPAD_RIGHT'),
                    ('dart','KEYCODE_DPAD_CENTER'), ('turn-left','KEYCODE_DPAD_LEFT'),
                    ('close-up-right','KEYCODE_DPAD_RIGHT')],
            'plants': [('wide-idle',None),('close-idle','KEYCODE_DPAD_CENTER'),('crawl-close','KEYCODE_DPAD_RIGHT')],
        }
        trace = traces[self.req.get('trace','idle')]
        for run in range(self.req.get('runs',1)):
            if run:
                self.launch(self.req.get('scene'))
            self.store.phase(self.job['id'],'warming-up')
            self.wait(self.req.get('warmup',15))
            self.require_foreground()
            layers=self.shell('dumpsys','SurfaceFlinger','--list').splitlines()
            candidates=[s for s in layers if self.package in s and ('SurfaceView' in s or s.startswith(self.package+'/'))]
            if not candidates:
                raise RuntimeError('No target SurfaceFlinger layer')
            layer=candidates[-1]
            self.shell('dumpsys','SurfaceFlinger','--latency-clear',layer)
            self.store.phase(self.job['id'],'measuring')
            samples=[];segments=[];t0=time.monotonic()
            folder=self.out/prefix/f'run-{run+1}'
            folder.mkdir(parents=True,exist_ok=True)
            for name,key in trace:
                start=time.monotonic()-t0
                deadline=time.monotonic()+self.req.get('duration',12)
                if key=='KEYCODE_DPAD_CENTER':
                    self.shell('input','keyevent','--longpress',key)
                while time.monotonic()<deadline:
                    samples.append({'host_seconds':time.monotonic()-t0,
                                    'raw':self.shell('dumpsys','SurfaceFlinger','--latency',layer)})
                    if key and key!='KEYCODE_DPAD_CENTER':
                        self.shell('input','keyevent','--longpress',key)
                    else:
                        self.wait(min(.75,max(0,deadline-time.monotonic())))
                segments.append({'name':name,'start':start,'end':time.monotonic()-t0})
                self.require_foreground()
                folder.joinpath(name+'.png').write_bytes(self.adb('exec-out','screencap','-p',binary=True))
            presents=set();refresh=None
            for sample in samples:
                rows=sample['raw'].splitlines()
                if rows and rows[0].isdigit():refresh=int(rows[0])/1e6
                for row in rows[1:]:
                    cells=row.split()
                    if len(cells)==3 and all(v.isdigit() for v in cells) and 0<int(cells[1])<9223372036854775807:
                        presents.add(int(cells[1]))
            ordered=sorted(presents)
            if ordered:
                limit=(time.monotonic()-t0)*1e9
                ordered=[p for p in ordered if p>=ordered[-1]-limit]
            intervals=[(b-a)/1e6 for a,b in zip(ordered,ordered[1:])]
            if len(intervals)<10:
                raise RuntimeError('Insufficient valid presented-frame intervals')
            ordered_intervals=sorted(intervals)
            result={'run':run+1,'frames':len(intervals),'interval_count':len(intervals),
                    'fps':1000/statistics.mean(intervals),'refresh_ms':refresh,
                    **{f'p{percent}_ms':ordered_intervals[int((len(intervals)-1)*percent/100)] for percent in [50,90,95,99]},
                    'worst_ms':max(intervals),'missed_refresh_percent':100*sum(v>refresh*1.5 for v in intervals)/len(intervals),
                    'duration_seconds':self.req.get('duration',12),'layer':layer}
            results.append(result)
            for name,data in [('samples.json',samples),('segments.json',segments),('presents-ns.json',ordered),('summary.json',result)]:
                folder.joinpath(name).write_text(json.dumps(data,indent=2))
            self.capture()
            for name in ['meminfo.txt','thermal.txt','wf.log','logcat.txt']:
                folder.joinpath(name).write_bytes(self.out.joinpath(name).read_bytes())
        self.out.joinpath(prefix,'summary.json').write_text(json.dumps({'runs':results,'median':{'fps':statistics.median(r['fps'] for r in results)}},indent=2))

    def record(self):
        self.wait(self.req.get('warmup',15))
        self.require_foreground()
        remote = '/data/local/tmp/wf-'+self.job['id']+'.mp4'
        # Only service-generated filenames/validated integer duration enter this fixed command.
        command = f'screenrecord --time-limit {int(self.req.get("duration",10))} {remote} >/dev/null 2>&1 & echo $!'
        if self.req.get('trace')=='school':
            command=f'screenrecord --time-limit 50 --size 960x540 --bit-rate 6000000 {remote} >/dev/null 2>&1 & echo $!'
        self.record_pid = int(self.adb('shell',command).strip())
        (self.out/'recording.json').write_text(json.dumps({'pid':self.record_pid,'path':remote}))
        self.store.phase(self.job['id'],'recording')
        if self.req.get('trace')=='school':
            timeline=[('REST - the fish idles, the ten swarm round it',None,8),('SWIM RIGHT - they school behind it','KEYCODE_DPAD_RIGHT',6),('REST - they gather round it again',None,6),('DART (A) - the school scatters, then regroups','KEYCODE_DPAD_CENTER',6),('SWIM LEFT','KEYCODE_DPAD_LEFT',5),('REST',None,4),('SWIM RIGHT, climbing','KEYCODE_DPAD_RIGHT',4),('REST',None,3)]
            segments=[];t0=time.monotonic()
            for label,key,seconds in timeline:
                start=time.monotonic()-t0;end=time.monotonic()+seconds
                if key=='KEYCODE_DPAD_CENTER':
                    self.shell('input','keyevent','--longpress',key)
                while time.monotonic()<end:
                    if key and key!='KEYCODE_DPAD_CENTER':
                        self.shell('input','keyevent','--longpress',key)
                    else:self.wait(min(.2,max(0,end-time.monotonic())))
                self.require_foreground()
                segments.append([start,time.monotonic()-t0,label])
            (self.out/'segments.json').write_text(json.dumps(segments,indent=2))
        deadline = time.monotonic()+(60 if self.req.get('trace')=='school' else self.req.get('duration',10)+10)
        while time.monotonic()<deadline:
            self.require_foreground()
            running = self.shell('cat',f'/proc/{self.record_pid}/cmdline',allow_failure=True)
            if 'screenrecord' not in running:
                break
            self.wait(.5)
        else:
            raise RuntimeError('Recording exceeded duration bound')
        self.out.joinpath('capture.mp4').write_bytes(self.adb('exec-out','cat',remote,binary=True))
        if self.out.joinpath('capture.mp4').stat().st_size<1000:
            raise RuntimeError('Empty/invalid recording')
        self.shell('rm','-f',remote)
        self.record_pid = None
        self.capture()

    def check_menu(self):
        if self.req['app'] != 'aquarium':
            raise ValueError('menu-back validator currently targets Aquarium')
        self.launch()
        initial = self.shell('pidof',self.package).strip()
        cursor = 0
        assertions = []
        for index, scene in enumerate(self.config.get('scenes',SCENES)):
            for _ in range(index-cursor):
                self.key('KEYCODE_DPAD_DOWN')
            self.key('KEYCODE_DPAD_CENTER'); self.wait(1.5)
            self.require_foreground()
            self.capture(scene+'-')
            if scene=='betta':
                from .image_assertions import changed_center
                first=self.adb('exec-out','screencap','-p',binary=True)
                self.wait(.55)
                second=self.adb('exec-out','screencap','-p',binary=True)
                count=changed_center(first,second)
                (self.out/'betta-animated-a.png').write_bytes(first)
                (self.out/'betta-animated-b.png').write_bytes(second)
                if count<=500:
                    raise RuntimeError('Betta animation assertion failed')
                assertions.append({'betta_animated_pixels':count})
            self.key('KEYCODE_HOME'); self.wait(.5)
            self.shell('am','start','-n',self.package+'/android.app.NativeActivity'); self.wait(1)
            if self.shell('pidof',self.package).strip() != initial:
                raise RuntimeError('Home/resume changed process')
            self.key('KEYCODE_BACK'); self.wait(1)
            self.require_foreground()
            if self.shell('pidof',self.package).strip()!=initial:
                raise RuntimeError('Back from level changed process')
            log=self.adb('logcat','-d','--pid='+initial,'-v','brief')
            if f'level-menu: level {index} starts' not in log or 'Back in level: returning to selector' not in log:
                raise RuntimeError('Scene start / Back assertion failed')
            assertions.append({'scene':scene,'start_back_home_resume':'PASS'})
            cursor=index
        self.key('KEYCODE_BACK'); self.wait(1)
        if any(self.package+'/' in s for s in self.foreground()):
            raise RuntimeError('Back from selector did not leave activity')
        (self.out/'assertions.json').write_text(json.dumps(assertions,indent=2))

    def cleanup(self):
        self.cleanup_mode = True
        if self.uncertain_install:
            raise RuntimeError('Uncertain remote install: device restart required before readd')
        if not self.identity_verified:
            raise RuntimeError('Device identity/connection not verified; recovery required before further control')
        self.store.phase(self.job['id'],'restoring')
        if self.record_pid:
            cmdline = self.shell('cat',f'/proc/{self.record_pid}/cmdline',allow_failure=True)
            if 'screenrecord' in cmdline and 'wf-'+self.job['id']+'.mp4' in cmdline:
                self.shell('kill','-2',str(self.record_pid),allow_failure=True)
                time.sleep(1)
                if 'screenrecord' in self.shell('cat',f'/proc/{self.record_pid}/cmdline',allow_failure=True):
                    raise RuntimeError('Owned device recording still running')
        if self.req['workflow']=='variant-benchmark':
            self.install(self.req['restore_apk'])
        if self.req['workflow'] != 'readd':
            self.shell('am','force-stop',self.package)
            if self.previous:
                package=self.previous.split('/',1)[0]
                result=self.shell('am','start','-W','-a','android.intent.action.MAIN','-c','android.intent.category.LEANBACK_LAUNCHER','-p',package,allow_failure=True)
                if 'Error' not in result and 'Exception' not in result and any(package+'/' in line for line in self.foreground()):
                    self.restoration='previous-app-TV-launcher'
                else:
                    self.key('KEYCODE_HOME')
                    self.restoration='home-fallback: previous app launcher unavailable'
            else:
                self.key('KEYCODE_HOME')
                self.restoration='home'
            if self.shell('pidof',self.package,allow_failure=True).strip() and self.restoration!='previous-app-TV-launcher':
                raise RuntimeError('Test process still running after cleanup')

    def run(self):
        self.connect()
        if self.req['workflow']=='readd':
            with self.store.db() as db:
                oldjobs=[self.store.job(row[0]) for row in db.execute("SELECT id FROM jobs WHERE device=? AND state='recovery-required' AND recovery_resolved=0",(self.device['id'],))]
            for old in oldjobs:
                error=old.get('error') or ''
                if ('during installing' in error or 'Uncertain remote install' in error) and self.previous_boot==self.device['boot_id']:
                    raise NeedsSetup('Uncertain previous install: restart this Chromecast, enable debugging and rerun readd')
                if old['request']['workflow']=='variant-benchmark':
                    original=self.req
                    self.package='org.worldfoundry.wf_game'+('' if old['request']['app']=='snowgoons' else '.'+old['request']['app'])
                    self.req=old['request']
                    self.install(old['request']['restore_apk'])
                    self.req=original
            # Startup recovery cannot grant before reconciling any device-side operation.
            for file in self.store.root.joinpath('evidence').glob('*/recording.json'):
                oldjob = self.store.job(file.parent.name)
                if oldjob['device'] != self.device['id'] or oldjob['state'] not in {'recovery-required','running'}:
                    continue
                recording=json.loads(file.read_text())
                cmd=self.shell('cat',f'/proc/{recording["pid"]}/cmdline',allow_failure=True)
                if 'screenrecord' in cmd and recording['path'] in cmd:
                    self.shell('kill','-2',str(recording['pid']),allow_failure=True)
                    self.wait(1)
                    if 'screenrecord' in self.shell('cat',f'/proc/{recording["pid"]}/cmdline',allow_failure=True):
                        raise RuntimeError('Orphaned recording still running')
            with self.store.db() as db:
                for old in oldjobs:
                    db.execute('UPDATE jobs SET recovery_resolved=1 WHERE id=?',(old['id'],))
                    self.store.event(db,old['id'],'recovery-resolved',{'maintenance_job':self.job['id']})
            return
        foreground=' '.join(self.foreground())
        components=re.findall(r'([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)',foreground)
        self.previous=components[-1] if components else None
        self.store.phase(self.job['id'],'installing')
        self.install(self.req['apk'])
        self.store.phase(self.job['id'],'launching')
        self.launch(self.req.get('scene'))
        if self.req['workflow']=='check':
            self.wait(self.req.get('duration',3))
            self.capture()
            if self.req.get('validator')=='menu-back':
                self.check_menu()
            elif self.req.get('validator')=='poke-resume':
                initial=self.shell('pidof',self.package).strip()
                self.key('KEYCODE_DPAD_RIGHT');self.key('KEYCODE_DPAD_UP')
                self.capture('after-keys-')
                self.key('KEYCODE_DPAD_CENTER');self.wait(1);self.capture('after-ok-')
                self.key('KEYCODE_HOME');self.wait(1)
                self.shell('am','start','-n',self.package+'/android.app.NativeActivity');self.wait(2)
                self.require_foreground()
                if self.shell('pidof',self.package).strip()!=initial:
                    raise RuntimeError('Home/resume changed process')
                self.capture('resumed-')
        elif self.req['workflow']=='profile':
            self.profile()
        elif self.req['workflow']=='record':
            self.record()
        elif self.req['workflow']=='variant-benchmark':
            base_request=dict(self.req)
            for variant in self.req['variants']:
                self.req=dict(base_request,**{k:variant[k] for k in ('runs','warmup') if k in variant})
                self.install(variant['apk'])
                self.launch(self.req.get('scene'))
                self.profile(variant['label'])
            self.req=base_request


def execute(root, jid, config, setup=None):
    store=Store(root)
    job=store.job(jid)
    if not config.get('fake'):
        # ADB can fork a persistent server on its first client command. Start it
        # before opening the device lock so the daemon cannot inherit ownership.
        try:
            ensure_adb_server(config)
        except (RuntimeError,subprocess.TimeoutExpired) as exc:
            store.finish(jid,'needs-local-setup',str(exc),health='needs-local-setup')
            return
    lock=open(store.root/'locks'/(job['device']+'.lock'),'a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        store.finish(jid,'recovery-required','Previous worker still holds device kernel lock',health='recovery-required')
        return
    device=next(d for d in store.devices() if d['id']==job['device'])
    legacy=None
    if device.get('legacy_lock'):
        legacy=open(device['legacy_lock'],'a')
        while True:
            try:
                fcntl.flock(legacy,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                store.phase(jid,'waiting-for-legacy-owner')
                if store.job(jid)['cancel']:
                    store.finish(jid,'cancelled','Cancelled while waiting for legacy owner')
                    lock.close();legacy.close();return
                time.sleep(.2)
    with store.db() as db:
        db.execute('UPDATE jobs SET worker_pid=? WHERE id=?',(os.getpid(),jid))
    adapter=None
    state,error,health='completed',None,'ready'
    interrupted=[False]
    def signal_handler(*_):
        interrupted[0]=True
        with store.db() as db:
            db.execute('UPDATE jobs SET cancel=1 WHERE id=?',(jid,))
    signal.signal(signal.SIGTERM,signal_handler)
    try:
        if config.get('fake'):
            store.phase(jid,'fake-command')
            deadline=time.monotonic()+job['request'].get('duration',.3)
            while time.monotonic()<deadline:
                if store.job(jid)['cancel']:
                    raise Cancelled('Cancelled fake job')
                time.sleep(.02)
        else:
            adapter=Adapter(store,job,config)
            adapter.lock_fd=lock.fileno()
            if setup:
                adapter.pair(setup)
            adapter.run()
    except Cancelled as exc:
        state,error='cancelled',str(exc)
    except NeedsSetup as exc:
        state,error,health='needs-local-setup',str(exc),'needs-local-setup'
    except BaseException as exc:
        state,error='failed',str(exc)
    finally:
        if adapter and state!='needs-local-setup':
            try:
                adapter.cleanup()
            except BaseException as exc:
                state,error,health='recovery-required',str(exc),'recovery-required'
        elif config.get('fake'):
            store.phase(jid,'restoring'); time.sleep(.05)
        out=store.root/'evidence'/jid;out.mkdir(exist_ok=True)
        receipt={'job':store.job(jid),'device':adapter.device if adapter else job['device'],
                 'result':state,'error':error,'cleanup_verified':health=='ready',
                 'restoration':adapter.restoration if adapter else 'fake-cleanup',
                 'commands':adapter.commands if adapter else [], 'finished':time.time(),
                 'concurrent_jobs':[j['id'] for j in store.snapshot()['jobs'] if j['state']=='running' and j['id']!=jid]}
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2))
        store.finish(jid,state,error,health)
        lock.close()
        if legacy:
            legacy.close()


def ensure_adb_server(config):
    env=dict(os.environ)
    if config.get('adb_socket'):env['ADB_SERVER_SOCKET']=config['adb_socket']
    env['ANDROID_USER_HOME']=config.get('adb_home',str(Path.home()/'.android'))
    env['ADB_VENDOR_KEYS']=env['ANDROID_USER_HOME']+'/adbkey'
    result=subprocess.run([config['adb'],'start-server'],env=env,close_fds=True,
                          capture_output=True,text=True,timeout=15)
    if result.returncode:
        raise RuntimeError('Private ADB server startup failed: '+result.stderr[:1000])
