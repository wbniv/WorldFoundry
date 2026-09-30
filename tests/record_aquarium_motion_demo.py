#!/usr/bin/env python3
"""record_aquarium_motion_demo.py — a real-time video of the aquarium clownfish's steer-and-swim.

Plays a scripted run of the built aquarium level (`task aquarium-level`) with held buttons only —
hover, a U-turn, a cruise across the tank, a climb facing right, a dive facing left, toward the glass
and away, the approach into the anemone's crown and a rest there (camshot B, the sway), a wall
approach and a dart — and writes a 640×480 H.264 video that plays in REAL TIME, with each segment's
name burnt in, plus a same-name .srt and a segment list (.txt).

How: the engine runs PAUSED under -rate20 and is stepped one tick at a time over the debug bridge by
the aquarium harness (wflevels/aquarium/run_aquarium_checks.py), with a sticky injected joystick
value on every tick, so desktop keys cannot reach the fish; the harness's `run isolation` check must
say CLEAN or no video is written. After every tick the bridge takes a screenshot, and the frames are
encoded at exactly 20 fps (one frame per 0.05 s tick), so video time == level time.
Rejected: the engine's own `-record_video` (display.cc) stamps frames with the WALL clock
(`-use_wallclock_as_timestamps 1`), so a paused, stepped run — or a loaded host — would play at the
harness's stepping speed, not in real time; the condo tour needs setpts for the same reason.

Usage: python3 tests/record_aquarium_motion_demo.py [-h] [--out PATH] [--work DIR] [--port N] [--keep-frames]
Default out: ~/tmp/aquarium-phase4/motion-demo.mp4 (never commit the video). Needs DISPLAY and wf_game
(engine/wf_game, else the main checkout's; WF_GAME= overrides), ffmpeg with drawtext.
Plan: docs/plans/2026-09-30-aquarium-level.md (Phase 4, item B).
"""
import argparse
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
ap.add_argument('--out', default=os.path.expanduser('~/tmp/aquarium-phase4/motion-demo.mp4'))
ap.add_argument('--work', default=None, help='frames + engine log (default: <out dir>/motion-demo-work)')
ap.add_argument('--port', type=int, default=int(os.environ.get('WF_BRIDGE_PORT', '7815')))
ap.add_argument('--keep-frames', action='store_true')
args = ap.parse_args()

OUT = Path(args.out).expanduser().resolve()
WORK = Path(args.work).expanduser().resolve() if args.work else OUT.parent / 'motion-demo-work'
FRAMES = WORK / 'frames'
shutil.rmtree(FRAMES, ignore_errors=True)
FRAMES.mkdir(parents=True)
os.environ['OUT'] = str(WORK)
os.environ['WF_BRIDGE_PORT'] = str(args.port)
sys.argv = sys.argv[:1]                                   # the harness reads sys.argv at import
sys.path.insert(0, str(REPO / 'wflevels' / 'aquarium'))
sys.path.insert(0, str(REPO / 'tests'))
import run_aquarium_checks as R                          # noqa: E402
import aquarium_constants as C                           # noqa: E402

B = R.BTN
if R.displays_blanked():
    print('warning: every display is blanked (DPMS off), so the engine is paced at 1 frame/s and this run takes '
          'about a second per tick; the video itself is unaffected (one frame per tick). Wake the screen to speed '
          'it up.', file=sys.stderr)
r = R.Run()
g = r.g
n_frames = 0
segments = []                                             # (name, first frame, end frame, description)


def grab():
    global n_frames
    fn = g.shot(f'frames/f{n_frames:05d}')
    if fn.startswith('FAILED'):
        raise RuntimeError(f'screenshot {n_frames}: {fn}')
    n_frames += 1


def hold(bits, secs):
    g.inject(bits)
    for _ in range(round(secs / R.DT)):
        g.step(1)
        grab()
    g.inject(0)


def segment(name, desc, moves):
    a = n_frames
    for bits, secs in moves:
        hold(bits, secs)
    segments.append((name, a, n_frames, desc))


try:
    g.step(30)                                            # load settle; not recorded
    segment('Hover', 'no input: the idle — a small bob, pectorals sculling, the anemone swaying',
            [(0, 2.0)])
    segment('U-turn left', 'Left: the fish turns in an arc (head first, banking) and swims off along its facing',
            [(B['LEFT'], 1.2), (0, 1.0)])
    segment('Cruise across', 'Right: U-turn back, then burst-and-coast across the tank; release = glide',
            [(B['RIGHT'], 2.3), (0, 0.8)])
    segment('Climb facing right', 'Up alone while facing right: it climbs FORWARD at the 40° pitch limit, then levels on release',
            [(B['UP'], 1.1), (0, 1.5)])
    segment('Dive facing left', 'Left (arc), then Down alone: a forward dive at the pitch limit, levelling on release',
            [(B['LEFT'], 1.2), (B['DOWN'], 1.1), (0, 1.5)])
    segment('Toward the glass', 'B: turns to face the camera and swims to the glass, easing to a stop before it',
            [(B['B'], 1.6), (0, 1.0)])
    segment('Away from the glass', 'C: turns (toward the centre line, never into the glass) and swims to the back',
            [(B['C'], 1.8), (0, 1.0)])
    # the anemone: steer like a player (the harness's navigate(): buttons toward the host point each tick)
    a = n_frames
    R.navigate(r, R.host_point(), lambda: g.v(r.dir, r.mb['aq-speed']) or 0.0, C.TAU_GLIDE, on_tick=grab)
    hold(0, 5.0)
    segments.append(('Into the anemone', a, n_frames, 'arrows + B/C toward the crown; camshot B takes over in the '
                     'zone; it rests level among the swaying tentacles'))
    segment('Wall approach', 'Right out of the crown to the end wall: it eases to a stop facing the wall (camera back to A)',
            [(B['RIGHT'], 3.0), (0, 0.5)])
    segment('Turn and dart', 'Left to turn away from the wall, then an A tap: a dart along the facing, then the glide',
            [(B['LEFT'], 0.6), (B['A'], 0.05), (0, 2.5)])
    segment('Hover', 'no input again: the idle fades back in', [(0, 1.5)])
finally:
    clean = r.isolation()
    g.close()

segs = segments
if not clean:
    raise SystemExit('run CONTAMINATED (desktop input reached the engine, or the fish moved before the harness '
                     'took over): no video written; run it again')

fps_in = round(1 / R.DT)                                  # 20: one frame per level tick = real time


def ts(frame, sep='.'):
    t = frame / fps_in
    return f'{int(t // 60):02d}:{t % 60:06.3f}'.replace('.', sep)


# captions: one drawtext per segment, shown for its span
esc = lambda s: s.replace('\\', '\\\\').replace(':', '\\:').replace("'", '’').replace('%', '\\%')
draws = []
for name, a, b, _ in segs:
    draws.append(f"drawtext=fontfile={FONT}:text='{esc(name)}':x=12:y=12:fontsize=22:fontcolor=white:"
                 f"box=1:boxcolor=black@0.55:boxborderw=6:enable='between(t,{a / fps_in:.3f},{b / fps_in - 0.001:.3f})'")
vf = 'scale=640:480:flags=bicubic,' + ','.join(draws) + ',fps=30'
OUT.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-framerate', str(fps_in), '-i', str(FRAMES / 'f%05d.png'),
                '-vf', vf, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(OUT)], check=True)
with open(OUT.with_suffix('.srt'), 'w') as fh:
    for k, (name, a, b, desc) in enumerate(segs, 1):
        fh.write(f'{k}\n00:{ts(a, ",")} --> 00:{ts(b, ",")}\n{name}: {desc}\n\n')
with open(OUT.with_suffix('.txt'), 'w') as fh:
    for name, a, b, desc in segs:
        fh.write(f'{ts(a)[:-1]}–{ts(b)[:-1]}  {name}: {desc}\n')
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(OUT)],
                           capture_output=True, text=True, check=True).stdout.strip())
print(f'{n_frames} ticks = {n_frames / fps_in:.2f} s of level time; video {OUT} is {dur:.2f} s '
      f'(real time: {math.isclose(dur, n_frames / fps_in, abs_tol=0.1)})')
print(open(OUT.with_suffix('.txt')).read(), end='')
if not args.keep_frames:
    shutil.rmtree(FRAMES, ignore_errors=True)
