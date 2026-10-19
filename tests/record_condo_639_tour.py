#!/usr/bin/env python3
"""record_condo_639_tour.py — record the guided tour of every 639-owned room.

The tour build (wflevels/condo_639_640_tour, made by `task tour-condo-639` from
wflevels/condo_639_640/tour-639.path.json) walks itself: the player's Forth script
is a waypoint state machine whose leg counter is global mailbox 500 and whose
"done" flag is mailbox 502. This script only launches the engine with
-record_video + the debug bridge, watches those mailboxes to time the room
captions, stops the engine when the tour is over, then post-processes with
ffmpeg (burnt-in captions, title card, optional setpts to a target length).

Usage:
    python3 tests/record_condo_639_tour.py [--seconds 20] [--out wflevels/condo_639_640/tour-639.mp4]
    python3 tests/record_condo_639_tour.py --verify-only
Exit 0 = every labelled room was entered in route order (and the player really
was inside its bbox at the hold), with the door open at completion; unless
--verify-only was selected, the mp4 + srt were also written.

Plan: docs/plans/2026-09-19-condo-639-tour-video.md
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient   # noqa: E402

REPO   = Path(__file__).resolve().parent.parent
WF     = REPO / "engine" / "wf_game"
LIB    = REPO / "engine" / "libs"
LEVEL  = "condo_639_640_tour"
LEVDIR = REPO / "wflevels" / LEVEL
IFF    = REPO / "wflevels" / f"{LEVEL}-standalone.iff"
FONT   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
PORT   = int(os.environ.get("WF_BRIDGE_PORT", "7795"))
MB_LEG, MB_DONE, MB_TIME, MB_DOOR_CLOSEDNESS = 500, 502, 1906, 94
X_POS, Y_POS = 3009, 3010

ap = argparse.ArgumentParser()
ap.add_argument("--seconds", type=float, default=20.0, help="target length after setpts (0 = keep real time)")
ap.add_argument("--out", default=str(REPO / "wflevels" / "condo_639_640" / "tour-639.mp4"))
ap.add_argument("--timeout", type=float, default=1800.0,
                help="wall-clock watchdog; software-rendered recording can be much slower than level time")
ap.add_argument("--verify-only", action="store_true",
                help="walk and validate the route without recording or post-processing video")
ap.add_argument("--size", default=os.environ.get("TOUR_SIZE", "640x480"),
                help="WxH passed to the engine as -width/-height (recording = window size)")
args = ap.parse_args()
VW, VH = (int(v) for v in args.size.lower().split("x"))
CAPTION_PX = max(22, round(22 * VH / 480))       # caption/title scale with the frame height
OUT = Path(args.out).resolve(); SRT = OUT.with_suffix(".srt")
WORK = Path(os.environ.get("TOUR_WORKDIR", REPO / "tests" / ".tour_work")).resolve(); WORK.mkdir(parents=True, exist_ok=True)
LOG = WORK / "wf_game.log"

legs = json.loads((LEVDIR / f"{LEVEL}.legs.json").read_text())
room_of_leg = {l["leg"]: l["room"] for l in legs if l.get("room")}
rooms_expected = [l["room"] for l in legs if l.get("room")]
door_legs = [l for l in legs if l.get("kind") == "DOOR_OPEN"]
if len(door_legs) != 1:
    raise SystemExit(f"expected exactly one DOOR_OPEN leg, found {len(door_legs)}")

# room bboxes from the tour .lev (target actors) for the cross-check
lev = (LEVDIR / f"{LEVEL}.lev").read_text()
bbox = {}
for ch in lev.split("'OBJ'")[1:]:
    nm = re.search(r"'NAME'\s*\"([^\"]+)\"", ch); cls = re.search(r"\"Class Name\" \} \{ 'DATA' \"([a-z]+)\"", ch)
    pm = re.search(r"\"Position\" \} \{ 'DATA' ([-\d.]+)\(1\.15\.16\) ([-\d.]+)\(1\.15\.16\)", ch)
    bb = re.search(r"\"Global Bounding Box\" \} \{ 'DATA' ([-\d.]+)\(1\.15\.16\) ([-\d.]+)\(1\.15\.16\) [-\d.]+\(1\.15\.16\) ([-\d.]+)\(1\.15\.16\) ([-\d.]+)\(1\.15\.16\)", ch)
    if nm and cls and cls.group(1) == "target" and pm and bb:
        px, py = float(pm.group(1)), float(pm.group(2))
        bbox[nm.group(1)] = (px + float(bb.group(1)), py + float(bb.group(2)), px + float(bb.group(3)), py + float(bb.group(4)))

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
env.setdefault("DISPLAY", ":0")
for stale in ("output.mp4",):
    (WORK / stale).unlink(missing_ok=True)
log_fp = open(LOG, "w")
game_args = [str(WF), f"-L{IFF}", f"-width={VW}", f"-height={VH}"]
if not args.verify_only:
    game_args.append("-record_video")
game_args += ["--debug-port", str(PORT),
              "--debug-bind", "127.0.0.1", "--debug-print-actors",
              # 1024² PERM atlas for the site sky/ground textures (wflevels/condo_639_640/textile.flags);
              # same VRAM flag set as Taskfile run-condo
              "--vram-width=4096", "--vram-height=2048", "--vram-slot-width=1024", "--vram-slot-height=1024",
              "--vram-perm-width=1024", "--vram-perm-height=1024"]
proc = subprocess.Popen(game_args,
                        cwd=str(WORK), env=env, stdout=log_fp, stderr=subprocess.STDOUT)
t_launch = time.time()
time.sleep(2.0)
failures = []
entries = []          # (room, capture-wall-time since launch, inside)
try:
    rx = re.compile(r"actor idx=(\d+) mesh=player\.iff mobility=Physics")
    player = None
    for _ in range(100):
        m = rx.search(LOG.read_text(errors="replace"))
        if m:
            player = int(m.group(1)); break
        time.sleep(0.1)
    assert player is not None, "player not found in --debug-print-actors output"
    cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
    for mb in (MB_LEG, MB_DONE, MB_TIME, MB_DOOR_CLOSEDNESS, X_POS, Y_POS):
        cli.watch(idx=player, mailbox=mb)

    def mv(mb):
        with cli._lock:
            return cli.mailbox_values.get((player, mb))

    last_leg, deadline, t_done = -1, time.time() + args.timeout, None
    while time.time() < deadline:
        leg = mv(MB_LEG)
        if leg is not None and int(leg) != last_leg:
            last_leg = int(leg)
            if last_leg in room_of_leg:
                room, t, x, y = room_of_leg[last_leg], mv(MB_TIME), mv(X_POS), mv(Y_POS)
                bx = bbox.get(room)
                inside = bool(bx and bx[0] <= x <= bx[2] and bx[1] <= y <= bx[3]) if (bx and x is not None) else False
                wall_t = time.time() - t_launch
                entries.append((room, wall_t, inside))
                print(f"HOLD {room:20s} t={float(t or 0):6.2f}s wall={wall_t:6.2f}s pos=({x:.2f},{y:.2f}) inside={inside}")
                if not inside:
                    failures.append(f"{room}: player at ({x:.2f},{y:.2f}) outside bbox {bx}")
        if mv(MB_DONE) == 1.0:
            t_done = mv(MB_TIME)
            print(f"TOUR_DONE t={t_done:.2f}s wall={time.time() - t_launch:.2f}s")
            time.sleep(1.5)                 # linger on the last room
            break
        time.sleep(0.03)
    else:
        failures.append(f"tour did not finish within {args.timeout}s (last leg {last_leg})")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log_fp.close()
    capture_end_wall = time.time() - t_launch

rooms_seen = [e[0] for e in entries]
missing = [r for r in rooms_expected if r not in rooms_seen]
if missing:
    failures.append(f"rooms never entered: {missing}")
if rooms_seen != rooms_expected:
    failures.append(f"room order mismatch: expected {rooms_expected}, saw {rooms_seen}")
door_closedness = mv(MB_DOOR_CLOSEDNESS)
if door_closedness is None or door_closedness > 0.001:
    failures.append(f"project-room glass door did not finish open (closedness={door_closedness})")
raw = WORK / "output.mp4"
if not args.verify_only and (not raw.exists() or raw.stat().st_size < 10_000):
    failures.append("recorder wrote no usable output.mp4")
if failures:
    print("RESULT: FAIL", failures); sys.exit(1)
if args.verify_only:
    print(f"RESULT: PASS  route verified ({len(entries)} rooms; no video requested)")
    sys.exit(0)

# ── captions: one cue per hold, aligned to capture wall time ─────────────────
def fmt(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3_600_000); m, ms = divmod(ms, 60_000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw)],
                       capture_output=True, text=True)
real_len = float(probe.stdout.strip() or 0)
speed = (real_len / args.seconds) if args.seconds and real_len > args.seconds else 1.0   # setpts factor: output time = raw-video time / speed
# The engine's software recorder starts producing frames several seconds after
# process launch. Align wall-clock room entries to raw-video time using the
# observed capture duration and the process end time.
capture_start_wall = max(0.0, capture_end_wall - real_len)
video_entries = [(room, max(0.0, min(real_len, wall_t - capture_start_wall)), inside)
                 for room, wall_t, inside in entries]
TITLE = 0.4
srt_lines = []
for i, (room, t, _) in enumerate(video_entries):
    if i + 1 < len(video_entries):
        start, end = TITLE + t / speed, TITLE + video_entries[i + 1][1] / speed
    else:
        start, end = TITLE + t / speed, TITLE + real_len / speed      # last room: caption to the end
    srt_lines += [str(i + 1), f"{fmt(start)} --> {fmt(end)}", room, ""]
SRT.write_text("\n".join(srt_lines))

# ── ffmpeg: title card + burnt-in captions (+ setpts to the target length) ────
title = WORK / "title.mp4"
rw, rh = (int(v) for v in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                          "-of", "csv=p=0", str(raw)], capture_output=True, text=True).stdout.strip().split(","))
k = rh / 480.0
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={rw}x{rh}:r=30:d={TITLE}",
                "-vf", f"drawtext=fontfile={FONT}:text='205/639 room tour':fontcolor=white:fontsize={round(34*k)}:x=(w-text_w)/2:y=(h-text_h)/2-{round(20*k)},"
                       f"drawtext=fontfile={FONT}:text='WorldFoundry condo_639_640  2026-09-20':fontcolor=#bbbbbb:fontsize={round(16*k)}:x=(w-text_w)/2:y=(h-text_h)/2+{round(30*k)}",
                "-pix_fmt", "yuv420p", str(title)], check=True)
body = WORK / "body.mp4"
vf = (f"setpts=PTS/{speed:.6f}," if speed != 1.0 else "") + "fps=30"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-vf", vf, "-an", "-pix_fmt", "yuv420p", str(body)], check=True)
concat = WORK / "concat.txt"
concat.write_text(f"file '{title}'\nfile '{body}'\n")
joined = WORK / "joined.mp4"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(joined)], check=True)
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(joined),
                "-vf", f"subtitles={SRT}:force_style='FontName=DejaVu Sans,FontSize={CAPTION_PX},Bold=1,Outline={max(2, round(2*k))},Shadow=0,MarginV={round(24*k)}'",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(OUT)], check=True)
final = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(OUT)],
                       capture_output=True, text=True).stdout.strip()
print(f"RESULT: PASS  {OUT} ({final}s, {rw}x{rh}; raw {real_len:.1f}s, speed x{speed:.2f}; {len(entries)} rooms)  captions {SRT}")
