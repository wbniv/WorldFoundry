#!/usr/bin/env python3
"""record-aquarium-school-chromecast.py: a real-time video of the school and the swarm on the real Chromecast, from the device's own screen.

Relaunches the installed aquarium app, hides the phone-controller overlay (Back), starts `screenrecord` on the device, and plays a scripted run with the
remote's D-pad only: the fish rests (the ten followers SWARM round it), swims right (they SCHOOL behind it), rests, swims left, rests. Then pulls the
recording, re-encodes it small (H.264, 960x540) with each segment's name burnt in, and writes the same-name .txt segment list.

Needs adb to the Chromecast (the serial or ip:port as the one argument, or the only device), and ffmpeg with drawtext. Do not run it while someone is using the
remote or the TV: it presses the D-pad and launches the app.

Usage: scripts/record-aquarium-school-chromecast.py [-h] [--out PATH] [--serial S]
Default out: tests/recordings/aquarium_school_demo.mp4
"""
import argparse, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
ap.add_argument("--out", default=str(REPO / "tests" / "recordings" / "aquarium_school_demo.mp4")); ap.add_argument("--serial", default="")
args = ap.parse_args()
ADB = os.environ.get("ADB") or str(Path.home() / "android-sdk-local" / "platform-tools" / "adb")
A = [ADB] + (["-s", args.serial] if args.serial else [])
PKG = "org.worldfoundry.wf_game.aquarium"


def sh(cmd, check=True):
    return subprocess.run(A + ["shell", cmd], capture_output=True, text=True, check=check).stdout


def hold(key, seconds):
    """Hold a D-pad key about `seconds`: --longpress sends the key down, repeats, and releases after about a second; repeat it back to back."""
    end = time.time() + seconds
    while time.time() < end:
        sh(f"input keyevent --longpress {key}", check=False)


segments = []        # (start s, end s, label), seconds from the start of the recording
sh("input keyevent KEYCODE_WAKEUP", check=False)
sh(f"am force-stop {PKG}"); time.sleep(1)
sh(f"am start -n {PKG}/android.app.NativeActivity"); time.sleep(9)
sh("input keyevent KEYCODE_BACK", check=False); time.sleep(2)             # hide the phone-controller overlay
sh("rm -f /sdcard/school.mp4")
rec = subprocess.Popen(A + ["shell", "screenrecord --time-limit 52 --size 960x540 --bit-rate 6000000 /sdcard/school.mp4"])
t0 = time.time(); time.sleep(1.5)
plan = [("REST - the fish idles, the ten swarm round it", None, 9), ("SWIM RIGHT - they school behind it", "KEYCODE_DPAD_RIGHT", 6), ("REST - they gather round it again", None, 7),
        ("SWIM LEFT", "KEYCODE_DPAD_LEFT", 6), ("REST", None, 7), ("SWIM RIGHT, climbing", "KEYCODE_DPAD_RIGHT", 5), ("REST", None, 5)]
for label, key, secs in plan:
    s = time.time() - t0
    hold(key, secs) if key else time.sleep(secs)
    segments.append((s, time.time() - t0, label))
rec.wait(timeout=30)
work = Path(tempfile.mkdtemp(prefix="aqschool-rec-"))
subprocess.run(A + ["pull", "/sdcard/school.mp4", str(work / "raw.mp4")], check=True, capture_output=True)
out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
draw = ",".join(f"drawtext=text='{lab.replace(':', ' ')}':enable='between(t,{a:.2f},{b:.2f})':x=24:y=h-52:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=8" for a, b, lab in segments)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(work / "raw.mp4"), "-vf", draw, "-c:v", "libx264", "-crf", "27", "-preset", "slow", "-pix_fmt", "yuv420p", "-an", str(out)], check=True)
out.with_suffix(".txt").write_text("".join(f"{a:6.1f} s to {b:6.1f} s  {lab}\n" for a, b, lab in segments))
print(f"wrote {out} ({out.stat().st_size // 1024} KB) and {out.with_suffix('.txt')}")
