#!/usr/bin/env python3
"""codemagic-queue.py — drive Codemagic builds for hours with no LLM in the loop.

Waits for every build that is already queued or running, then runs each --run item in
order (Codemagic's free plan allows one build at a time, so they queue anyway). For every
finished build it downloads the artifacts into OUT/<workflow>-<id6>/ and writes summary.txt
(status, failed steps, minutes, and the decisive log lines), so a later, short session can
read a few hundred tokens instead of digging through logs. Costs no tokens while it runs.

Guards: no new build starts after --stop-after (UTC) or once this month's Mac-minutes,
counted by scripts/codemagic-budget.sh, reach --cap.

  scripts/codemagic-queue.py [--run WORKFLOW:BRANCH ...] [--cap 300] [--stop-after 2026-09-30T20:30:00Z]

Needs ~/.config/codemagic/token and app-id; triggering reuses the codemagic-build skill's driver.
"""
import argparse, io, json, os, re, shutil, subprocess, sys, time, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path

API = 'https://api.codemagic.io'
DONE = {'finished', 'failed', 'canceled', 'timeout', 'skipped'}
KEEP = re.compile(r'(error:|CMake Error|What went wrong|BUILD (SUCCESSFUL|FAILED)|FAIL\b|PASS\b|PARITY|'
                  r'exceeding tolerance|exact=|presented=|^(MACOS|IOS|ANDROID|WINDOW|SIZE)[ :])', re.M)
CFG = Path.home() / '.config' / 'codemagic'
DRIVER = Path.home() / '.config/claude/will/skills/codemagic-build/codemagic.py'
REPO = Path(__file__).resolve().parent.parent


def token():
    return (CFG / 'token').read_text().strip()


def app_id():
    return (CFG / 'app-id').read_text().strip()


def get(path, raw=False):
    req = urllib.request.Request(path if raw else API + path, headers={'x-auth-token': token()})
    data = urllib.request.urlopen(req, timeout=120).read()
    return data if raw else json.loads(data)


def say(out, msg):
    n = datetime.now(timezone.utc)
    line = f"{n.astimezone():%H:%M:%S %z} = {n:%H:%M:%SZ}  {msg}"
    print(line, flush=True)
    with open(out / 'queue.log', 'a') as f:
        f.write(line + '\n')


def mac_minutes_used():
    env = dict(os.environ, DRY_RUN='1', BUDGET_MINUTES='500', STATE_FILE='/tmp/codemagic-queue-budget.json',
               CODEMAGIC_API_TOKEN=token(), WF_APP_ID=app_id())
    r = subprocess.run(['bash', str(REPO / 'scripts' / 'codemagic-budget.sh')], env=env, capture_output=True, text=True)
    m = re.search(r'used=(\d+)', r.stdout)
    return int(m.group(1)) if m else 10 ** 6          # unknown: refuse to start more


def wait(out, build_id, poll):
    while True:
        b = get(f'/builds/{build_id}')['build']
        if b['status'] in DONE:
            return b
        time.sleep(poll)


def collect(out, b):
    name = (b.get('config') or {}).get('name') or b.get('workflowId') or 'build'
    d = out / f"{re.sub(r'[^A-Za-z0-9]+', '-', name).strip('-')}-{b['_id'][-6:]}"
    d.mkdir(parents=True, exist_ok=True)
    lines = [f"{name}  {b['status']}  branch={b.get('branch')}  commit={(b.get('commit') or {}).get('hash', '')[:8]}",
             f"https://codemagic.io/app/{b.get('appId', app_id())}/build/{b['_id']}"]
    st, fin = b.get('startedAt'), b.get('finishedAt')
    if st and fin:
        f = lambda s: datetime.fromisoformat(s.replace('Z', '+00:00'))
        lines.append(f"minutes: {(f(fin) - f(st)).total_seconds() / 60:.1f}")
    lines.append('failed steps: ' + (', '.join(a['name'] for a in b.get('buildActions', []) if a.get('status') == 'failed') or '-'))
    for a in b.get('artefacts') or []:
        try:
            data = get(a['url'], raw=True)
        except Exception as e:                            # keep going: one bad artifact must not lose the rest
            lines.append(f"artifact {a['name']}: download failed ({e})")
            continue
        (d / a['name']).write_bytes(data)
        if a['name'].endswith('.zip') and 'artifacts' in a['name']:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                z.extractall(d)
    for p in sorted(d.glob('*.log')):
        hits = [l for l in p.read_text(errors='replace').splitlines() if KEEP.search(l)]
        if hits:
            lines += [f'--- {p.name} ({len(hits)} matching lines, first 25)'] + [h[:200] for h in hits[:25]]
    (d / 'summary.txt').write_text('\n'.join(lines) + '\n')
    return d, lines[0]


def notify(msg):
    if shutil.which('notify-send'):
        subprocess.run(['notify-send', 'Codemagic queue', msg], check=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog='Results: OUT/queue.log and OUT/<workflow>-<id6>/summary.txt')
    ap.add_argument('--run', action='append', default=[], metavar='WORKFLOW:BRANCH', help='build to trigger after the active ones (repeatable)')
    ap.add_argument('--out', default=str(Path.home() / 'tmp' / 'codemagic-runs'))
    ap.add_argument('--cap', type=int, default=300, help='do not start a build once this many Mac-minutes are used this month')
    ap.add_argument('--stop-after', default=None, help='UTC ISO time after which no new build is started')
    ap.add_argument('--poll', type=int, default=30)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stop = datetime.fromisoformat(args.stop_after.replace('Z', '+00:00')) if args.stop_after else None

    active = [b for b in get(f'/builds?appId={app_id()}')['builds'] if b['status'] not in DONE]
    say(out, f"watching {len(active)} active build(s): " + ', '.join(f"{(b.get('config') or {}).get('name')}/{b['status']}" for b in active))
    for b in reversed(active):                            # oldest first
        d, head = collect(out, wait(out, b['_id'], args.poll))
        say(out, f"done: {head}  -> {d}")
        notify(head)
    for item in args.run:
        workflow, _, branch = item.partition(':')
        if stop and datetime.now(timezone.utc) >= stop:
            say(out, f"stop time reached, not starting {item}")
            break
        used = mac_minutes_used()
        if used >= args.cap:
            say(out, f"Mac-minutes used {used} >= cap {args.cap}, not starting {item}")
            break
        say(out, f"starting {item} (used {used} min)")
        r = subprocess.run([sys.executable, '-u', str(DRIVER), 'build', '--app-id', app_id(), '--workflow', workflow,
                            '--branch', branch or 'HEAD', '--log-tail', '1'], capture_output=True, text=True)
        m = re.search(r'/build/([0-9a-f]{24})', r.stdout + r.stderr)
        if not m:
            say(out, f"could not start {item}: {(r.stdout + r.stderr)[-300:]}")
            continue
        d, head = collect(out, get(f'/builds/{m.group(1)}')['build'])
        say(out, f"done: {head}  -> {d}")
        notify(head)
    say(out, 'queue finished')


if __name__ == '__main__':
    main()
