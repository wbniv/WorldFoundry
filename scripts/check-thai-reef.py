#!/usr/bin/env python3
"""Desktop reaction test for the Gulf of Thailand reef (original plan step 6, W4).

Runs the real engine (wf_game) on a reef level, drives the boxfish (the Player)
to each reactor over the debug bridge, holds it there, moves it away, and
measures each reaction from the Director's own cells, frame by frame at -rate20
(0.05 s per frame):

  reactor          near test (generate.py)                     close            reopen after leaving
  Christmas worms  3D distance < 0.8 to each of 15 mouths      scale -> 0.02    timer 3 + 0.35*(7i mod 15) s
  feather dusters  3D distance < 0.8 to each of 4 fans         scale -> 0.02    timer 3 + w s
  giant clam       planar x,y distance < 1 and z > 0.82        close -> 1       timer 4 s
  guard crab       3D distance < 1                             threat           timer 2 s
  dascyllus pair   x,z distance < 1.2 (internally "humbug")    dive -> 1        timer 2.5 s
  cleaner shrimp   x,z distance < 1 and speed < 0.1 for 2 s    cleaning 5 s     (cleaning ends after 5 s)

The windows asserted are the plan's: worms, dusters and clam reopen 3-8 s after
the fish leaves, the pair 2.5 s and the crab 2 s; cleaning starts after 2 s still.
"Reopen" is the frame the reactor's timer reaches 0 and it starts to open again;
"open" is the frame it is fully open. Radii, timers and cells are read from the
generator (wflevels/aquarium_thai_reef/generate.py); positions come from
reef.scene, plus each hero's displacement cells (904-909) under a Random layout.

Layout defaults to Random in the shipped levels, so the run selects
--property=ReefSettings.Layout=0 (Fixed) unless --random-seed is given, which
selects Layout=1 with that Seed and reads the reactor positions from 904-909.

Run it INSIDE the Linux test container, under Xvfb, with a container-built engine:
  scripts/in-linux-container.sh scripts/build-wf-game-container.sh
  scripts/in-linux-container.sh xvfb-run -a -s '-screen 0 1280x720x24' \\
    python3 scripts/check-thai-reef.py --video
Writes results.json, runtime-<style>.log, per-reaction stills and (with --video)
one animated WebP per reaction to --out (default
docs/diagnostics/reef-reactions-2026-11-09). Exits 1 if any reaction misses its window.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path[:0] = [str(ROOT / 'wflevels/aquarium_tanks'), str(ROOT / 'wflevels/aquarium_thai_reef')]

FRAME = 3276 / 65536          # simulated seconds per frame at -rate20
CLOCK = 1906                  # the Player's elapsed-time mailbox (as check-arowana.py)
POS = (3009, 3010, 3011)      # INDEXOF_X_POS, _Y_POS, _Z_POS
VEL = (3018, 3019, 3020)
FAR = (3.2, -1.5, 4.5)        # clear of every reactor under Fixed; Random picks its own (far_point)
FAR_CANDIDATES = [(x, -1.9, z) for x in (-4.6, -3.0, -1.5, 0.0, 1.5, 3.0, 4.6) for z in (1.2, 3.0, 4.8)]
HERO = {'left': 0, 'arch': 1, 'right': 2}   # reef.kit.HEROES order: cells 904+i (x), 907+i (y)


def parse():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--wf-game', type=Path, default=ROOT / 'build-docker/wf-game/src/engine/wf_game',
                   help='engine binary (default: the container build from build-wf-game-container.sh)')
    p.add_argument('--style', choices=('realistic', 'anime', 'both'), default='both')
    p.add_argument('--random-seed', type=int, default=None,
                   help='run Layout=Random with this Seed (realistic only) instead of Fixed')
    p.add_argument('--out', type=Path, default=ROOT / 'docs/diagnostics/reef-reactions-2026-11-09')
    p.add_argument('--port', type=int, default=17991)
    p.add_argument('--video', action='store_true', help='record every reaction as an animated WebP')
    p.add_argument('--rejudge', action='store_true',
                   help='re-evaluate the saved Fixed traces in --out/frames without running the engine')
    return p.parse_args()


def reactors():
    """Each reactor: where to put the fish, the cells to read, and its window."""
    from reef.scene import anchor_map, worm_mouths
    a = anchor_map()
    worms = [w['mouth'] for w in worm_mouths()]
    dx, dy, dz = a['feather_duster']
    dusters = [(dx + (w - 1.5) * .42, dy, dz + (w % 2) * .12) for w in range(4)]
    return [
        dict(name='worms', hero='left', at=(-2.84, -1.5, 2.0), hold=1.5, after=11.0,
             parts=[dict(label=f'worm {i}', timer=1000 + i, state=1020 + i, closed=lambda v: v <= .05,
                         opened=lambda v: v >= .999, expect_reopen=3 + .35 * ((i * 7) % 15),
                         window=(3, 8), close_max=.3, point=m, radius=.8, axes=(0, 1, 2))
                    for i, m in enumerate(worms)]),
        dict(name='dusters', hero='left', at=(-1.96, -.3, 2.2), hold=1.5, after=10.0,
             parts=[dict(label=f'duster {w}', timer=780 + w, state=784 + w, closed=lambda v: v <= .05,
                         opened=lambda v: v >= .999, expect_reopen=3 + w, window=(3, 8), close_max=.3,
                         point=d, radius=.8, axes=(0, 1, 2)) for w, d in enumerate(dusters)]),
        dict(name='clam', hero='arch', at=(a['giant_clam'][0], -1.15, 1.2), hold=1.5, after=6.5,
             parts=[dict(label='giant clam', timer=746, state=745, closed=lambda v: v >= .99,
                         opened=lambda v: v <= .001, expect_reopen=4, window=(3, 8), close_max=.5,
                         point=(a['giant_clam'][0], -1.15, 0), radius=1, axes=(0, 1))]),
        dict(name='crab', hero='left', at=(a['guard_crab'][0], -1.1, 2.6), hold=1.5, after=3.5,
             parts=[dict(label='guard crab', timer=643, state=643, closed=lambda v: v > 0,
                         opened=lambda v: v <= 0, expect_reopen=2, window=(1.9, 2.15), close_max=.15,
                         point=a['guard_crab'], radius=1, axes=(0, 1, 2))]),
        dict(name='pair', hero='left', at=(a['humbug_pair'][0], -.5, 4.8), hold=1.5, after=5.0,
             parts=[dict(label='dascyllus pair', timer=740, state=741, closed=lambda v: v >= .99,
                         opened=lambda v: v <= .001, expect_reopen=2.5, window=(2.4, 2.65), close_max=.6,
                         point=a['humbug_pair'], radius=1.2, axes=(0, 2))]),
        # Held for the whole clean (2 s still + 5 s), then away.
        dict(name='shrimp', hero='arch', at=(a['cleaner_station'][0], -.6, 1.2), hold=7.6, after=3.0,
             parts=[]),
        # The fish leaves 1.5 s into the clean: an observation, not a window (the plan sets none).
        dict(name='shrimp-leave', hero='arch', at=(a['cleaner_station'][0], -.6, 1.2), hold=3.5, after=6.0,
             parts=[]),
    ]


def rejudge(out, styles):
    """Judge saved Fixed-layout traces again (hero displacements are zero under Fixed)."""
    results = {}
    for style in styles:
        rows = []
        for r in reactors():
            path = out / 'frames' / f'{style}-{r["name"]}-trace.json'
            if not path.is_file():
                continue
            trace = json.loads(path.read_text())
            near_frames = int(r['hold'] / FRAME)
            left = actual_left(trace, near_frames)
            fish = trace[near_frames - 1]['fish']
            if r['name'] == 'shrimp':
                rows.append(judge_shrimp(trace, near_frames, left, r['at'], fish))
            if r['name'] == 'shrimp-leave':
                rows.append(observe_shrimp_leave(trace, near_frames, r['at']))
            rows += [judge(p, trace, left, fish) for p in r['parts']]
        results[style] = rows
    return results


def main():
    args = parse()
    out = args.out.resolve()
    (out / 'frames').mkdir(parents=True, exist_ok=True)
    if args.rejudge:
        report(out, rejudge(out, ['realistic', 'anime'] if args.style == 'both' else [args.style]), 'fixed')
        return
    if not args.wf_game.is_file():
        sys.exit(f'no engine at {args.wf_game}; build it with scripts/build-wf-game-container.sh')
    styles = ['realistic', 'anime'] if args.style == 'both' else [args.style]
    if args.random_seed is not None:
        styles = ['realistic']
    results = {}
    for n, style in enumerate(styles):
        results[style] = run_style(args, out, style, args.port + 10 * n)
    report(out, results, f'random-seed{args.random_seed}' if args.random_seed is not None else 'fixed')


def report(out, results, tag):
    (out / f'results-{tag}.json').write_text(json.dumps(results, indent=2) + '\n')
    failures = [f'{style}: {r["label"]}: {r["verdict"]}' for style, rows in results.items()
                for r in rows if r['verdict'].startswith('FAIL')]
    findings = [f'{style}: {r["label"]}: {r["verdict"]}' for style, rows in results.items()
                for r in rows if r['verdict'].startswith(('FINDING', 'SKIP'))]
    print(table(results))
    if findings:
        print('Findings (not failures):\n' + '\n'.join(findings))
    if failures:
        print('FAIL\n' + '\n'.join(failures))
        sys.exit(1)
    print('PASS: every reaction inside its window')


def table(results):
    lines = ['style      reaction          close s  reopen s  expected  window      open s  verdict']
    for style, rows in results.items():
        for r in rows:
            lines.append(f"{style:10s} {r['label']:16s} {fmt(r.get('close')):>8s} {fmt(r.get('reopen')):>9s} "
                         f"{fmt(r.get('expected')):>9s}  {str(r.get('window', '')):11s} {fmt(r.get('open')):>7s}  {r['verdict']}")
    return '\n'.join(lines)


def fmt(v):
    return '-' if v is None else f'{v:.2f}'


def run_style(args, out, style, port):
    from debug_bridge_client import BridgeClient
    level = f'aquarium_thai_reef{"_anime" if style == "anime" else ""}'
    mapping = json.loads((ROOT / f'wflevels/{level}/actor-map.json').read_text())
    idx = mapping.get('indices', mapping.get('actors'))
    player, director = idx['Player'], idx['Director']
    props = ['--property=ReefSettings.Layout=0']
    if args.random_seed is not None:
        props = ['--property=ReefSettings.Layout=1', f'--property=ReefSettings.Seed={args.random_seed}']
    env = dict(os.environ, WF_REST_HOST='127.0.0.1', WF_REST_PORT=str(port + 1000))
    log = (out / f'runtime-{style}{"-random" if args.random_seed is not None else ""}.log').open('w')
    proc = subprocess.Popen([str(args.wf_game), '-L' + str(ROOT / f'wflevels/{level}-standalone.iff'), '-rate20',
                             '--debug-port', str(port), '--debug-bind', '127.0.0.1', '-width=1280', '-height=720',
                             # The reef's 1024-square atlas pages need the large VRAM slots
                             # (as scripts/sweep_blender_levels.py VRAM_BIG).
                             '--vram-width=4096', '--vram-height=2048', '--vram-slot-width=1024',
                             '--vram-slot-height=1024', '--vram-perm-width=1024', '--vram-perm-height=1024',
                             *props],
                            cwd=ROOT / f'wflevels/{level}', env=env, stdout=log, stderr=subprocess.STDOUT,
                            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
    cli = None
    rows = []
    try:
        cli = BridgeClient(port=port, timeout=300)   # level load under llvmpipe takes over a minute
        cli.send({'op': 'pause'})
        cli.inject_input('joystick1_raw', 0, duration_frames=-1)
        plan = reactors()
        for box in (*POS, *VEL, CLOCK):
            cli.watch(player, box)
        watched = sorted({c for r in plan for p in r['parts'] for c in (p['timer'], p['state'])}
                         | {640, 643, 644, 743, 744, 860, 861, 862, 863, *range(880, 883), *range(904, 910)})
        for box in watched:
            cli.watch(director, box)
        for name in ('ShrimpOne', 'HumbugOne'):
            for box in POS:
                cli.watch(idx[name], box)

        def value(actor, box):
            with cli._lock:
                return cli.mailbox_values.get((actor, box), 0.0)

        def cell(box):
            return value(director, box)

        def clock():
            return value(player, CLOCK)

        def step(n=1):
            start = clock()
            cli.send({'op': 'step', 'frames': n})
            deadline = time.monotonic() + 60
            while clock() < start + n * FRAME - .0002:
                if proc.poll() is not None:
                    raise RuntimeError('engine exited')
                if time.monotonic() > deadline:
                    raise RuntimeError('frame stepping timed out')
                time.sleep(.005)
            time.sleep(.02)

        def place(p):
            cli.inject_input('joystick1_raw', 0, duration_frames=-1)
            for box, v in zip(POS, p):
                cli.set_mailbox(box, v, player)
            for box in VEL:
                cli.set_mailbox(box, 0, player)

        def shot(path):
            cli.send({'op': 'screenshot', 'filename': str(path)})
            msg = cli.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error'), timeout=20)
            assert msg and msg.get('op') == 'screenshot_done', msg

        step(30)
        settings = [cell(b) for b in (860, 861, 862, 863)]
        expected_layout = 0 if args.random_seed is None else 1
        assert settings[0] == expected_layout, f'Layout is {settings[0]}, wanted {expected_layout}: --property not applied'
        shown = [cell(880 + i) for i in range(3)]
        disp = {h: (cell(904 + i), cell(907 + i)) for h, i in HERO.items()}

        def moved(p, hero):
            return (p[0] + disp[hero][0], p[1] + disp[hero][1], p[2])

        far = FAR if not any(any(d) for d in disp.values()) else far_point(
            [(moved(q['point'], r['hero']), q) for r in plan for q in r['parts']]
            + [(moved(r['at'], r['hero']), dict(axes=(0, 2), radius=1)) for r in plan
               if r['name'].startswith('shrimp')])

        for r in plan:
            if shown[HERO[r['hero']]] != 1:
                rows.append(dict(label=r['name'], verdict='SKIP (hero hidden)'))
                continue
            at = moved(r['at'], r['hero'])
            parts = [dict(p, point=moved(p['point'], r['hero'])) for p in r['parts']]
            place(far)
            step(int(9 / FRAME))          # every earlier reaction has reopened
            frames = []
            trace = []
            t0 = clock()
            place(at)
            near_frames = int(r['hold'] / FRAME)
            total = near_frames + int(r['after'] / FRAME)
            left = None
            for f in range(total):
                if f == near_frames:
                    place(far)
                    left = clock()
                step(1)
                row = dict(t=round(clock() - t0, 4), fish=[round(value(player, b), 4) for b in POS],
                           cells={str(p['timer']): cell(p['timer']) for p in parts}
                           | {str(p['state']): cell(p['state']) for p in parts}
                           | {k: cell(int(k)) for k in ('644', '743', '744')})
                row['shrimp_x'] = value(idx['ShrimpOne'], POS[0])
                row['humbug_z'] = value(idx['HumbugOne'], POS[2])
                trace.append(row)
                if args.video and f % 2 == 0:
                    path = out / 'frames' / f'{style}-{r["name"]}-{f // 2:03d}.png'
                    shot(path)
                    frames.append(path)
            (out / 'frames' / f'{style}-{r["name"]}-trace.json').write_text(json.dumps(trace) + '\n')
            fish = trace[near_frames - 1]['fish']
            gone = actual_left(trace, near_frames)
            if r['name'] == 'shrimp':
                rows.append(judge_shrimp(trace, near_frames, gone, at, fish))
            if r['name'] == 'shrimp-leave':
                rows.append(observe_shrimp_leave(trace, near_frames, at))
            for p in parts:
                rows.append(judge(p, trace, gone, fish))
            if args.video:
                write_video(frames, out / f'{style}-{r["name"]}.webp')
                keep_stills(frames, out, style, r['name'], near_frames // 2)
    finally:
        if cli:
            cli.close()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
    return rows


def actual_left(trace, near_frames):
    """Time of the last frame the fish was still at the reactor.

    The bridge applies a position write when the engine next reads its socket, which can
    be a frame or two after the step is sent, so the leave time comes from the fish's own
    position in the trace, not from when the move was requested.
    """
    at = trace[near_frames - 1]['fish']
    for i in range(near_frames - 1, len(trace)):
        if sum((a - b) ** 2 for a, b in zip(trace[i]['fish'], at)) > .25:
            return trace[i - 1]['t']
    raise AssertionError('the fish never left the reactor')


def far_point(points):
    """The parking spot whose nearest reactor is furthest away, in each reactor's own metric."""
    def margin(c):
        return min(sum((c[a] - pt[a]) ** 2 for a in q['axes']) ** .5 - q['radius'] for pt, q in points)
    best = max(FAR_CANDIDATES, key=margin)
    assert margin(best) > .3, ('no parking spot clear of every reactor', best, margin(best))
    return best


def judge(p, trace, left, fish):
    """Close time from arrival; reopen and open times from the frame the fish left."""
    near = sum((fish[a] - p['point'][a]) ** 2 for a in p['axes']) < p['radius'] ** 2
    t_state = [(row['t'], row['cells'][str(p['state'])], row['cells'][str(p['timer'])]) for row in trace]
    close = next((t for t, s, _ in t_state if t < left + 1e-6 and p['closed'](s)), None)
    after = [(t - left, s, timer) for t, s, timer in t_state if t > left + 1e-6]
    reopen = next((t for t, _, timer in after if timer <= 0), None)
    opened = next((t for t, s, _ in after if p['opened'](s)), None)
    lo, hi = p['window']
    if not near:
        verdict = 'SKIP (fish not within radius; check placement)'
    elif close is None or close > p['close_max'] + 1e-6:
        verdict = f'FAIL close {close} > {p["close_max"]}'
    elif reopen is None or not (lo - 1e-6 <= reopen <= hi + 1e-6):
        verdict = f'FAIL reopen {reopen} outside {p["window"]}'
    # The fish is seen gone on the first tick after it moves, so the timer is read one
    # frame late at most; allow 1.5 frames (float time accumulates in 0.05 s steps).
    elif abs(reopen - p['expect_reopen']) > 1.5 * FRAME:
        verdict = f'FAIL reopen {reopen} != timer {p["expect_reopen"]:.2f}'
    else:
        verdict = 'PASS'
    return dict(label=p['label'], close=close, reopen=reopen, expected=p['expect_reopen'],
                window=list(p['window']), open=opened, verdict=verdict)


def judge_shrimp(trace, near_frames, left, at, fish):
    """Cleaning starts after 2 s still within reach; the shrimp follow the fish for 5 s."""
    start = next((row['t'] for row in trace[:near_frames] if row['cells']['744'] >= 1), None)
    following = [row for row in trace if row['cells']['743'] > 0]
    follow_ok = bool(following) and abs(following[-1]['shrimp_x'] - (following[-1]['fish'][0] - .175)) < .3
    end = next((row['t'] - start for row in trace if start is not None and row['t'] > start + .01
                and row['cells']['743'] <= 0), None)
    back = trace[-1]['shrimp_x']
    if start is None:
        verdict = 'FAIL cleaning never started'
    elif not (1.95 <= start <= 2.15):
        verdict = f'FAIL cleaning started at {start}, wanted 2 s'
    elif not follow_ok:
        verdict = 'FAIL shrimp did not move to the fish'
    elif end is None or not (4 - 1e-6 <= end <= 6 + 1e-6):
        verdict = f'FAIL cleaning lasted {end} s, wanted 4-6 s'
    else:
        verdict = 'PASS'
    return dict(label='cleaner shrimp', close=start, reopen=end, expected=2.0, window=[2.0, 2.0],
                open=None, verdict=verdict, shrimp_x_after=back, note='close = cleaning start after '
                'arriving still (window 2 s); reopen = cleaning length (window 4-6 s)')


def observe_shrimp_leave(trace, near_frames, at):
    """How far ShrimpOne travels from the cave mouth if the fish leaves mid-clean."""
    after = trace[near_frames:]
    still = [row for row in after if row['cells']['743'] > 0]
    reach = max((abs(row['shrimp_x'] - at[0]) for row in still), default=0.0)
    length = len(still) * FRAME
    verdict = (f'FINDING: shrimp keep cleaning {length:.2f} s after the fish leaves and follow it '
               f'{reach:.2f} units from the cave mouth' if reach > 1 else 'PASS')
    return dict(label='shrimp, fish leaves', close=None, reopen=length, expected=None, window=None,
                open=None, verdict=verdict, reach=reach)


def write_video(frames, path):
    from PIL import Image
    if not frames:
        return
    images = [Image.open(f).convert('RGB') for f in frames]
    w = 640
    images = [im.resize((w, round(im.height * w / im.width))) for im in images]
    images[0].save(path, save_all=True, append_images=images[1:], duration=100, loop=0, quality=55, method=4)


def keep_stills(frames, out, style, name, near_index):
    from PIL import Image
    picks = {'calm': 0, 'near': min(len(frames) - 1, max(0, near_index - 1)), 'after': len(frames) - 1}
    for label, i in picks.items():
        Image.open(frames[i]).convert('RGB').save(out / f'{style}-{name}-{label}.jpg', quality=82)
    for f in frames:
        f.unlink()


if __name__ == '__main__':
    main()
