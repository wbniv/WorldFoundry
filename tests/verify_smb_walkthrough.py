"""Scripted SMB W1-1 walk-through with video capture.

Launches wf_game on the SMB level with -record_video, despawns the
enemies via ALIVE=0 (mailbox slot 3004) so they can't kill Mario,
drives Mario right via sticky inject_input for ~90 s, then exits
cleanly so ffmpeg flushes the mp4. Output lands at
tests/screenshots/smb_scroll_walkthrough.mp4.

Companion to tests/verify_smb_scroll.py (still-shot panel) — this one
captures continuous motion to validate the 1-tick lag is invisible at
60 Hz under live play, which stills can't show.

The despawn step is gated by `guard doing damage` count in the engine
log: at exit we print the count and treat any non-zero as a despawn
failure (wrong idx, wrong slot, race) — see
docs/plans/2026-05-18-smb-camera-bug-fixes.md.

Note: Mario's effective Jolt walk speed is ~0.9 m/s in observed runs,
much slower than wf_Max Ground Speed=6.0 suggests. 90 s of held RIGHT
should get him from X=4.5 to roughly X=85, well past the flagpole at
X=63 — so the video covers spawn, scroll, and the right-edge camera
clamp (camera stops at X=58.5) in one continuous take.
"""
from __future__ import annotations

import os, re, sys, time, subprocess, signal, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient  # noqa: E402

REPO    = Path(__file__).resolve().parent.parent
WF      = REPO / "engine" / "wf_game"
LEVEL   = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB     = REPO / "engine" / "libs"
CWD     = REPO / "wfsource" / "source" / "game"   # output.mp4 lands here
PORT    = 7779
OUT_MP4 = REPO / "tests" / "screenshots" / "smb_scroll_walkthrough.mp4"

JOY_RIGHT = 0x2000
ALIVE_MAILBOX = 3004     # mailbox.inc:67 — writing 0 makes the actor kill itself
ENEMY_MESHES  = ("goomba_00.001.iff", "koopa_00.001.iff")

WALK_SECS    = 90.0   # sticky RIGHT duration
SETTLE_SECS  = 2.0    # let Mario fall + scripts spin up before walking
COOLDOWN_SECS = 2.0   # post-walk settle, so the mp4 doesn't end mid-frame

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
env.setdefault("DISPLAY", ":0")

log_path = REPO / "tests" / ".smb_walkthrough.log"
log_fp = open(log_path, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}",
     "--debug-port", str(PORT),
     "--debug-bind", "127.0.0.1",
     "--debug-print-actors",
     "-record_video"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT,
)

ACTOR_RE = re.compile(r"^actor idx=(\d+) mesh=(\S+) ")

def find_enemy_indices() -> dict[str, int]:
    """Parse the engine log for `actor idx=N mesh=foo.iff` lines.

    Re-reads each call so it works the moment those lines have been
    flushed; returns {mesh_filename: idx} for the enemy meshes found.
    """
    found: dict[str, int] = {}
    if not log_path.exists():
        return found
    for line in log_path.read_text(errors="replace").splitlines():
        m = ACTOR_RE.match(line)
        if not m: continue
        mesh = m.group(2)
        if mesh in ENEMY_MESHES:
            found[mesh] = int(m.group(1))
    return found

cli = None
try:
    cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
    print(f"bridge: connected (port {PORT})")

    # Wait for the actor-print pass (engine emits all actor lines at
    # construction time, before the main loop starts). Connect-success
    # is already past that point in practice, but give a small grace
    # period in case the log buffer hasn't flushed.
    enemies: dict[str, int] = {}
    for _ in range(20):
        enemies = find_enemy_indices()
        if len(enemies) == len(ENEMY_MESHES):
            break
        time.sleep(0.1)
    print(f"discovered enemies: {enemies}")
    missing = [m for m in ENEMY_MESHES if m not in enemies]
    if missing:
        print(f"WARN: did not find {missing} in {log_path} — proceeding anyway")

    for mesh, idx in enemies.items():
        cli.set_mailbox(mailbox=ALIVE_MAILBOX, value=0, idx=idx)
        print(f"  despawn {mesh}: set_mailbox(idx={idx}, slot={ALIVE_MAILBOX}, value=0)")

    print(f"settle {SETTLE_SECS}s — Mario falling onto ground, enemies dying")
    time.sleep(SETTLE_SECS)

    print(f"walk {WALK_SECS}s — holding RIGHT")
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    time.sleep(WALK_SECS)
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)

    print(f"cooldown {COOLDOWN_SECS}s — release + settle")
    time.sleep(COOLDOWN_SECS)

finally:
    if cli is not None:
        try: cli.close()
        except Exception: pass
    print("stopping engine (SIGTERM, then flush)")
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=2.0)
    log_fp.close()

# Verify the despawn worked — engine logs "guard doing damage" each tick
# Mario is in contact with an alive enemy. Expected: 0 after despawn.
log_text = log_path.read_text(errors="replace")
damage_count = log_text.count("guard doing damage")
print(f"\ngoomba damage events: {damage_count} (expected 0)")
if damage_count > 0:
    print(f"  WARN: despawn did not stop damage — check enemy idx + ALIVE slot")

src_mp4 = CWD / "output.mp4"
if src_mp4.exists():
    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_mp4), str(OUT_MP4))
    print(f"video: {OUT_MP4} ({OUT_MP4.stat().st_size // 1024} KB)")
else:
    print(f"WARN: {src_mp4} not produced — check {log_path}")
    sys.exit(1)
