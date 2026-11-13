#!/usr/bin/env python3
"""Planted Tank step-9 soak on cast2, PHASE-LOCKED: one PSS sample per tank at PHASE s after its start.

Timing is on the device clock: tank starts are the 'PLANTS settings-source=OAD' logcat markers, and
each sample's own time is the one 'Explicit ... GC' line that dumpsys meminfo forces in the app.
The host fires each sample at (predicted next start + PHASE - measured request-to-GC latency),
re-anchored on the latest marker after every sample. The actual phase of every sample is recorded.

Derived from run-soak.py (continuous sampling); its notes follow.

Repeat of docs/diagnostics/runtime-editing-followups-2026-11-13/run-release-soak.py
with the sampling fix for its 914.8 s gap. That gap was not the coordinator or the
device: this laptop suspended (systemd-logind, 09:30:24 -> 09:45:17 +0700), freezing
the host-side sampler while the soak kept running on the Chromecast. The old loop
timed itself with time.monotonic(), which stops during suspend, so it never noticed.

Fixes, sampling method only (the 4 MiB limit is unchanged):
  * the whole run holds a systemd-inhibit sleep:idle block lock (re-exec below);
  * elapsed time and gaps use the wall clock, and a gap over GAP_LIMIT between
    sample attempts aborts the run as invalid instead of being silently absorbed.

Only coordinator Task commands are used. Settings and the screensaver selection are
read before the run and restored and read back afterwards.
"""
import datetime, json, math, os, re, statistics, subprocess, sys, tempfile, time
from pathlib import Path

DEVICE = 'chromecast-test-02'
APK = '/home/will/tmp/planted-soak-2026-11-13/planted-release-2d8f70c1.apk'
PLANTED = 'org.worldfoundry.plantedtank/org.worldfoundry.screensaver.PlantedTankDreamService'
TARGET_STARTS = 51          # 50 reloads
DURATION = 3600
GAP_LIMIT = 60.0            # seconds between sample attempts before the run is invalid
OUT = Path(__file__).resolve().parent / 'soak-phase'
PHASE = 20.0                # target seconds after each tank start (late grow; analyse with phase.py)

if '--help' in sys.argv or '-h' in sys.argv:
    print(__doc__); sys.exit(0)
if os.environ.get('WF_SOAK_INHIBITED') != '1':
    os.environ['WF_SOAK_INHIBITED'] = '1'
    os.execvp('systemd-inhibit', ['systemd-inhibit', '--what=sleep:idle', '--mode=block',
              '--who=planted-soak', '--why=Planted Tank soak: host-side PSS sampler must not suspend',
              sys.executable, *sys.argv])

OUT.mkdir(exist_ok=True)
def now(): return time.time()
TZ = datetime.timezone(datetime.timedelta(hours=7))
def devtime(line):
    mo, d, h, mi, s = re.match(r'(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d\.\d+)', line).groups()
    return datetime.datetime(2026, int(mo), int(d), int(h), int(mi), tzinfo=TZ).timestamp() + float(s)
def log(*a): print(time.strftime('%Y-%m-%dT%H:%M:%S%z'), *a, flush=True)
def task(*args): return subprocess.run(['task', *args], capture_output=True, text=True)
def task_logged(name, *args, required=True):
    p = task(*args, 'DEVICE=' + DEVICE)
    (OUT / (name + '.log')).write_text(p.stdout + p.stderr)
    log(name, 'rc', p.returncode)
    if required and p.returncode: raise RuntimeError(name + ': ' + p.stderr[-2000:])
    return p
def last_json(text):
    dec = json.JSONDecoder(); found = None; i = 0
    while True:
        i = text.find('\n{', i)
        if i < 0: return found
        try: found, _ = dec.raw_decode(text[i + 1:])
        except ValueError: pass
        i += 1
def planted_fields(obj, acc=None):
    acc = {} if acc is None else acc
    if isinstance(obj, dict):
        if 'wire_id' in obj and obj.get('key') in ('Growth speed', 'Hold seconds'):
            acc[obj['key']] = (obj['wire_id'], obj['value'])
        for v in obj.values(): planted_fields(v, acc)
    elif isinstance(obj, list):
        for v in obj: planted_fields(v, acc)
    return acc

# 1. Original state: selection from screensaver-list, Planted values from its selection readback.
pre = last_json(task_logged('pre-list', 'chromecast:screensaver-list').stdout)
original_component = pre['selected_component']
sel = last_json(task_logged('pre-select-planted', 'chromecast:screensaver-select', 'COMPONENT=' + PLANTED).stdout)
fields = planted_fields(sel)
assert set(fields) == {'Growth speed', 'Hold seconds'}, fields
(OUT / 'saved-preferences.json').write_text(json.dumps(
    {'original_component': original_component, 'settings': {k: {'wire_id': w, 'value': v} for k, (w, v) in fields.items()}}, indent=2) + '\n')
log('original', original_component, fields)

job = None
try:
    task_logged('set-speed', 'chromecast:screensaver-setting', 'SETTING_ID=' + fields['Growth speed'][0], 'VALUE=6')
    task_logged('set-hold', 'chromecast:screensaver-setting', 'SETTING_ID=' + fields['Hold seconds'][0], 'VALUE=5')
    recipe = OUT / 'recipe.json'
    recipe.write_text(json.dumps(dict(duration=DURATION, interactive=True, record=False, idle_seconds=900), indent=2) + '\n')
    p = task('chromecast:record', 'DEVICE=' + DEVICE, 'APP=planted-screensaver', 'APK=' + APK, 'RECIPE=' + str(recipe),
             'PANEL=require-hidden', 'ASYNC=true')
    (OUT / 'submit.log').write_text(p.stdout + p.stderr); assert p.returncode == 0, p.stderr
    job = re.search(r'Accepted (J-[a-f0-9]+)', p.stdout).group(1); (OUT / 'job.txt').write_text(job + '\n'); log('job', job)

    started = now(); last_attempt = None; samples = []; markers = set(); failures = 0; invalid = None
    lat = []                                   # device GC time minus host request time, per sample
    def refresh():
        """Download the job's evidence; return sorted tank starts and {sample logcat: GC device time}."""
        with tempfile.TemporaryDirectory(prefix='wf-planted-') as tmp:
            ev = task('chromecast:evidence', 'JOB=' + job, 'OUT=' + tmp)
            gcs = {}
            if ev.returncode == 0:
                for path in Path(tmp).glob('*logcat.txt'):
                    lines = path.read_text(errors='replace').splitlines()
                    markers.update(l for l in lines if 'PLANTS settings-source=OAD ' in l)
                    g = [devtime(l) for l in lines if 'Explicit' in l and ' GC ' in l]
                    if g: gcs[path.name] = g[-1]
        (OUT / 'markers.json').write_text(json.dumps(sorted(markers), indent=2) + '\n')
        return sorted(devtime(l) for l in markers), gcs
    with (OUT / 'samples.jsonl').open('w') as f:
        while now() - started < DURATION + 600:
            starts, _ = refresh() if not samples else (starts, None)
            fire = now()
            if samples and len(starts) >= 2 and lat:
                # next start after the latest one, predicted from the measured period, plus the target phase
                period = statistics.median([b - a for a, b in zip(starts, starts[1:])][-10:])
                last_dev = starts[-1]
                host_now_dev = now() + statistics.median(lat[-8:])   # where a sample fired now would land
                k = max(0, math.ceil((host_now_dev + 1.0 - last_dev - PHASE) / period))
                fire = last_dev + k * period + PHASE - statistics.median(lat[-8:])
                if fire - now() > 0: time.sleep(fire - now())     # deliberate schedule to the target phase
            t0 = now()
            if last_attempt is not None and t0 - last_attempt > GAP_LIMIT:
                invalid = f'sampling gap {t0 - last_attempt:.1f} s > {GAP_LIMIT} s'; log('INVALID', invalid); break
            last_attempt = t0
            p = task('chromecast:input:sample', 'JOB=' + job)
            f.write(json.dumps(dict(wall=t0, elapsed=t0 - started, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)) + '\n'); f.flush()
            if p.returncode:
                failures += 1
                if samples and 'not accepting input' in p.stderr: log('job stopped accepting input'); break
                if failures >= 30: break
                time.sleep(5); continue          # rate limit between retries, not a readiness wait
            failures = 0; s = json.loads(p.stdout); s['host_wall'] = t0
            starts, gcs = refresh()
            s['gc_device'] = gcs.get(s['logcat'])
            if s['gc_device'] is not None:
                lat.append(s['gc_device'] - t0)
                prev = [x for x in starts if x <= s['gc_device']]
                s['phase'] = s['gc_device'] - prev[-1] if prev else None
            samples.append(s)
            if not s['stable'] or s['pid_before'] != samples[0]['pid_before']: log('process changed', s); break
            log('sample', len(samples), 'starts', len(starts), 'phase', None if s.get('phase') is None else round(s['phase'], 2),
                'pss', s['total_pss_kb'], 'lat', round(lat[-1], 2) if lat else None)
            if len(starts) >= TARGET_STARTS: break
    (OUT / 'sample-values.json').write_text(json.dumps(samples, indent=2) + '\n')
    (OUT / 'run-status.json').write_text(json.dumps(dict(invalid=invalid, samples=len(samples), tank_starts=len(markers)), indent=2) + '\n')
finally:
    if job:
        p = task('chromecast:input:finish', 'JOB=' + job); (OUT / 'finish.log').write_text(p.stdout + p.stderr)
        p = task('chromecast:watch', 'JOB=' + job); (OUT / 'watch.log').write_text(p.stdout + p.stderr)
        p = task('chromecast:evidence', 'JOB=' + job, 'OUT=' + str(OUT / 'evidence')); (OUT / 'download.log').write_text(p.stdout + p.stderr)
        log('evidence rc', p.returncode)
    task_logged('restore-select-planted', 'chromecast:screensaver-select', 'COMPONENT=' + PLANTED, required=False)
    for key, (wire, value) in fields.items():
        task_logged('restore-' + wire, 'chromecast:screensaver-setting', 'SETTING_ID=' + wire, 'VALUE=' + str(value), required=False)
    sel = last_json(task_logged('restore-readback-planted', 'chromecast:screensaver-select', 'COMPONENT=' + PLANTED, required=False).stdout) or {}
    task_logged('restore-selection', 'chromecast:screensaver-select', 'COMPONENT=' + original_component, required=False)
    post = last_json(task_logged('post-list', 'chromecast:screensaver-list', required=False).stdout) or {}
    back = {k: v for k, (w, v) in planted_fields(sel).items()}
    keys = ('selected_component', 'enabled', 'activate_on_sleep', 'idle_timeout_ms', 'sleep_timeout_ms', 'stay_on_while_plugged_in')
    restoration = dict(device=DEVICE, settings=back, expected_settings={k: v for k, (w, v) in fields.items()},
                       before={k: pre.get(k) for k in keys}, after={k: post.get(k) for k in keys},
                       running_state=post.get('running_state'))
    restoration['readback_verified'] = (back == restoration['expected_settings'] and restoration['before'] == restoration['after'])
    (OUT / 'restoration.json').write_text(json.dumps(restoration, indent=2) + '\n')
    log('restoration verified', restoration['readback_verified'])
