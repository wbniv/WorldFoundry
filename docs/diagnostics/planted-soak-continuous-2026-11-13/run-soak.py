#!/usr/bin/env python3
"""Planted Tank step-9 soak on cast2 with continuous PSS sampling.

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
import json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

DEVICE = 'chromecast-test-02'
APK = '/home/will/tmp/planted-soak-2026-11-13/planted-release-2d8f70c1.apk'
PLANTED = 'org.worldfoundry.plantedtank/org.worldfoundry.screensaver.PlantedTankDreamService'
TARGET_STARTS = 51          # 50 reloads
DURATION = 3600
GAP_LIMIT = 60.0            # seconds between sample attempts before the run is invalid
OUT = Path(__file__).resolve().parent / 'soak'

if '--help' in sys.argv or '-h' in sys.argv:
    print(__doc__); sys.exit(0)
if os.environ.get('WF_SOAK_INHIBITED') != '1':
    os.environ['WF_SOAK_INHIBITED'] = '1'
    os.execvp('systemd-inhibit', ['systemd-inhibit', '--what=sleep:idle', '--mode=block',
              '--who=planted-soak', '--why=Planted Tank soak: host-side PSS sampler must not suspend',
              sys.executable, *sys.argv])

OUT.mkdir(exist_ok=True)
def now(): return time.time()
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
    with (OUT / 'samples.jsonl').open('w') as f:
        while now() - started < DURATION + 600:
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
                time.sleep(10); continue    # rate limit between retries, not a readiness wait
            failures = 0; s = json.loads(p.stdout); s['host_wall'] = t0; samples.append(s)
            if not s['stable'] or s['pid_before'] != samples[0]['pid_before']: log('process changed', s); break
            if len(samples) % 4 == 1:
                with tempfile.TemporaryDirectory(prefix='wf-planted-') as tmp:
                    ev = task('chromecast:evidence', 'JOB=' + job, 'OUT=' + tmp)
                    if ev.returncode == 0:
                        for path in Path(tmp).glob('*logcat.txt'):
                            markers.update(l for l in path.read_text(errors='replace').splitlines() if 'PLANTS settings-source=OAD ' in l)
                (OUT / 'markers.json').write_text(json.dumps(sorted(markers), indent=2) + '\n')
                log('samples', len(samples), 'tank starts', len(markers), 'pss', s['total_pss_kb'])
                if len(markers) >= TARGET_STARTS: break
            time.sleep(15)                  # sampling cadence, not a readiness wait
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
