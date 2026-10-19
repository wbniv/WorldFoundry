#!/usr/bin/env python3
"""capture-condo-pullback.py: capture the condo's opening doll-house shot with the camera pulled further back.

Runs the Linux engine on the standalone condo level with the debug bridge, holds button F (zoom farther,
condo_639_640.md "Controls") for a while, and writes backend frame N to a PNG with --capture-frame. The same
camera the player gets with the F key, so the icon shows what the game renders.

Usage: scripts/capture-condo-pullback.py OUT.png [--hold-frames N] [--frame N] [-h]
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))
from debug_bridge_client import BridgeClient   # noqa: E402

# the condo's 1024x1024 permanent texture atlas needs the same flags the Android app ships in wf_args.txt
VRAM = [l.strip() for l in (REPO / 'android' / 'app' / 'src' / 'condo' / 'assets' / 'wf_args.txt').read_text().split() if l.strip()]

p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
p.add_argument("out"); p.add_argument("--hold-frames", type=int, default=240); p.add_argument("--frame", type=int, default=420)
p.add_argument("--tilt", action="store_true", help="also hold D + up: raise the inspection angle toward a plan view")
p.add_argument("--lower-frames", type=int, default=0, help="first hold D + down for N frames (30 degrees per second) to lower the viewing angle")
p.add_argument("--port", type=int, default=7792)
a = p.parse_args()
env = dict(os.environ, LD_LIBRARY_PATH=f"{REPO/'engine'/'libs'}:{os.environ.get('LD_LIBRARY_PATH','')}", DISPLAY=os.environ.get("DISPLAY", ":0"))
proc = subprocess.Popen([str(REPO / "engine" / "wf_game"), f"-L{REPO/'wflevels'/'condo_639_640-standalone.iff'}", "--debug-port", str(a.port),
                         "--debug-bind", "127.0.0.1", "-width=1920", "-height=1080", *VRAM, f"--capture-frame={a.frame}={a.out}"],
                        cwd=str(REPO / "wfsource" / "source" / "game"), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        preexec_fn=lambda: __import__("resource").setrlimit(__import__("resource").RLIMIT_CORE, (0, 0)))
try:
    time.sleep(2.5)
    cli = BridgeClient(port=a.port)
    if a.lower_frames:
        cli.inject_input(slot="joystick1_raw", value=(1 << 6) | (1 << 12), duration_frames=a.lower_frames)    # D (bit 6) + down (bit 12): lower the angle
        time.sleep(a.lower_frames / 60.0 + 0.5)
    cli.inject_input(slot="joystick1_raw", value=(1 << 2) | (((1 << 6) | (1 << 11)) if a.tilt else 0), duration_frames=a.hold_frames)   # F (bit 2) zoom farther; D (bit 6) + up (bit 11) raise the angle
    deadline = time.time() + 150
    while time.time() < deadline and not Path(a.out).exists():
        time.sleep(0.5)
finally:
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()
sys.exit(0 if Path(a.out).exists() else 1)
