#!/usr/bin/env python3
"""Run a published Finding Your Way chapter on the iOS Simulator (Codemagic).

Two subcommands, used in this order by the `ios-simulator-chapter` workflow in
codemagic.yaml:

  bundle  Check a downloaded chapter APK against its pinned SHA-256, take its
          assets/cd.iff (checked against the level SHA-256) and
          assets/wf_args.txt, and write a copy of the built wf_game.app that
          carries them. The level data comes from the published APK, never
          from a blob committed here.
  run     Install that copy on an iPhone and an iPad simulator and drive one
          launch per device through a fixed timeline (below), keeping
          screenshots, the launch log and a verdict.

Timeline of `run`, seconds after `simctl launch` returns:

   0     launch with no launch arguments, so the engine gets its arguments
         only from the bundled wf_args.txt, as a home-screen launch would;
         WF_TOUCH_SCRIPT (hal/ios/input.mm) is the scripted input
  20     screenshot: the opening card; the app must be alive
  20-25  background (Settings) and resume; tests/check_frame_rate_log.py --resume
  28     touch script presses A: closes the card (SELECT: continue)
  31,32  two screenshots one second apart: the Temple braziers must change
  33-37  touch script holds UP twice (the Cast1 Temple-to-Love route)
  38     screenshot at the Love portal; A pressed at 38.6
  42     screenshot: Love arrival (stretch goal, informational)

The touch script is the engine's own CI input path: it presses each button's
on-screen centre through the same tracker and hit test a finger uses; only
UIKit's touch delivery is skipped. simctl itself has no tap injection.

Verdict per device (`IOS IPHONE: OK` / `IOS IPAD: OK`) needs install, launch,
alive at 20 s and at the end, wf_args.txt read with its arguments,
`ROOM-RENDER scope=current-only`, no zForth or texture-slot error, the
pause/resume frame-rate check, and changed fire-coloured pixels between the two
brazier screenshots. The iOS touch HUD is a D-pad with A and B, not Android's
joystick with A to D (see hal/ios/input.mm and hal/android/touch_controls.h),
so touch parity is reported on its own line and is not part of OK.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUNDLE_ID = "org.worldfoundry.wf-game"

# Seconds after launch; see the module docstring.
CARD_AT = 20.0
RESUME_SETTLE = 3.0
FIRE_AT = (31.0, 32.0)
PORTAL_AT = 38.0
LOVE_AT = 42.0
TOUCH_SCRIPT = "a@28+0.3,up@33+2,up@35.3+2,a@38.6+0.15"

ZFORTH_ERROR = re.compile(r"zforth[: ].*\b(error|unknown|failed)\b")
TEXTURE_SLOT_ERROR = "does not fit its"
ROOM_RENDER = "ROOM-RENDER scope=current-only"
WF_ARGS_LINE = re.compile(r"wf_args\.txt found, gave (\d+) argument")


def log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}", flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ─── bundle ─────────────────────────────────────────────────────────────────

def find_app(root: Path) -> Path | None:
    """The built wf_game.app: engine/ first (build-ios-sim/ is cached and could
    hold a stale one), as the ios-simulator-release run step does."""
    for sub in ("engine", "build-ios-sim"):
        base = root / sub
        if base.is_dir():
            for p in sorted(base.rglob("wf_game.app")):
                if p.is_dir():
                    return p
    return None


def bundle(apk: Path, apk_sha: str, level_sha: str, app: Path, out: Path) -> Path:
    got = sha256(apk)
    log(f"APK {apk.name}: SHA-256 {got}")
    log(f"APK expected:      SHA-256 {apk_sha}")
    if got != apk_sha:
        raise SystemExit(f"APK SHA-256 mismatch: got {got}, expected {apk_sha}")
    log("APK SHA-256 matches the milestone manifest")
    with zipfile.ZipFile(apk) as z:
        level = z.read("assets/cd.iff")
        args = z.read("assets/wf_args.txt")
    level_got = hashlib.sha256(level).hexdigest()
    log(f"assets/cd.iff: {len(level)} bytes, SHA-256 {level_got}")
    if level_got != level_sha:
        raise SystemExit(f"cd.iff SHA-256 mismatch: got {level_got}, expected {level_sha}")
    log("assets/wf_args.txt: " + " ".join(args.decode().split()))

    out.mkdir(parents=True, exist_ok=True)
    dst = out / app.name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(app, dst, symlinks=True)
    targets = sorted(dst.rglob("cd.iff")) or [dst / "cd.iff"]
    for t in targets:
        t.write_bytes(level)
        (t.parent / "wf_args.txt").write_bytes(args)
        log(f"wrote {t.relative_to(out)} and {(t.parent / 'wf_args.txt').relative_to(out)}")
    for t in targets:
        if sha256(t) != level_sha:
            raise SystemExit(f"{t}: copy does not match the level SHA-256")
    return dst


# ─── analysis (host-tested in tests/test_ios_sim_chapter.py) ───────────────

def read_png(path: Path):
    sys.path.insert(0, str(REPO / "tests"))
    from compare_renderer_frames import read_png as _read
    return _read(str(path))


def is_fire(r: int, g: int, b: int) -> bool:
    """Saturated orange to yellow: the Doom-fire palette in doom_fire.hp from
    (220, 65, 8) up to (255, 205, 70), allowing for lighting. Red leads, blue
    sits well below green, saturation at least 0.5. Not fire: the HUD's red A
    button (blue equal to green), its gray D-pad, and the Temple's tan floor
    (saturation about 0.4). Only the palest stop (255, 245, 175) is missed; a
    flickering flame passes through the others."""
    return (r >= 180 and g >= 50 and r > g and b <= g - 15
            and (r - min(g, b)) * 2 >= r)


def write_png(path: Path, w: int, h: int, px: bytes) -> None:
    """8-bit RGB PNG, no dependencies (the Codemagic Mac has no Pillow)."""
    raw = b"".join(b"\0" + bytes(px[y * w * 3:(y + 1) * w * 3]) for y in range(h))

    def chunk(t, body):
        return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def fire_change(w: int, h: int, px_a, px_b, threshold: int = 24, mask=None):
    """Pixels that changed between two frames (any channel by more than
    `threshold`) where either frame is fire-coloured. Returns (count, bbox).
    With `mask` (a bytearray of w*h*3, frame A dimmed), counted pixels are
    painted white there, for the reviewer."""
    count, x0, y0, x1, y1 = 0, w, h, -1, -1
    for i in range(w * h):
        o = i * 3
        ra, ga, ba = px_a[o], px_a[o + 1], px_a[o + 2]
        rb, gb, bb = px_b[o], px_b[o + 1], px_b[o + 2]
        if abs(ra - rb) <= threshold and abs(ga - gb) <= threshold and abs(ba - bb) <= threshold:
            continue
        if not (is_fire(ra, ga, ba) or is_fire(rb, gb, bb)):
            continue
        count += 1
        if mask is not None:
            mask[o:o + 3] = b"\xff\xff\xff"
        x, y = i % w, i // w
        x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
    return count, ((x0, y0, x1, y1) if count else None)


def centre_colours(w: int, h: int, px) -> int:
    c = Counter(bytes(px[(y * w + x) * 3:(y * w + x) * 3 + 3])
                for y in range(h * 3 // 10, h * 7 // 10)
                for x in range(w * 3 // 10, w * 7 // 10))
    return len(c)


def log_findings(text: str) -> dict:
    m = WF_ARGS_LINE.search(text)
    return {
        "room_render": ROOM_RENDER in text,
        "zforth_errors": [l for l in text.splitlines() if ZFORTH_ERROR.search(l)][:10],
        "texture_slot_error": TEXTURE_SLOT_ERROR in text,
        "wf_args": int(m.group(1)) if m else 0,
        "touch_a": "touch buttons 0x0001" in text,
        "touch_up": "touch buttons 0x0800" in text,
    }


def device_ok(v: dict) -> bool:
    return (v["install"] and v["launch"] and v["alive_20s"] and v["alive_end"]
            and v["wf_args"] > 0 and v["room_render"] and not v["zforth_errors"]
            and not v["texture_slot_error"] and v["fps_check"] and v["fire_pixels"] >= 20)


# ─── run ────────────────────────────────────────────────────────────────────

def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


def pick_devices():
    """Newest iOS runtime with an iPhone and an iPad (as ios-simulator-release)."""
    devs = json.loads(sh(["xcrun", "simctl", "list", "-j", "devices", "available"]).stdout)["devices"]

    def ver(rt):
        m = re.search(r"iOS-(\d+)-(\d+)", rt)
        return tuple(int(x) for x in m.groups()) if m else (0, 0)

    for rt in sorted((r for r in devs if "SimRuntime.iOS" in r), key=ver, reverse=True):
        ds = [d for d in devs[rt] if d.get("isAvailable")]
        phone = next((d for d in ds if d["name"].startswith("iPhone")), None)
        pad = next((d for d in ds if d["name"].startswith("iPad")), None)
        if phone and pad:
            return rt, [("iphone", phone["udid"], phone["name"]), ("ipad", pad["udid"], pad["name"])]
    return None, []


def downscaled(shot: Path) -> Path:
    small = shot.with_suffix(".small.png")
    subprocess.run(["sips", "-Z", "1024", "-s", "format", "png", str(shot), "--out", str(small)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return small


def run_device(label: str, udid: str, name: str, app: Path, out: Path) -> dict:
    v = {"label": label, "name": name, "install": False, "launch": False, "alive_20s": False,
         "alive_end": False, "fps_check": False, "fire_pixels": 0, "fire_bbox": None,
         "card_colours": 0, "level_loaded_at": None}
    stdout_f, stderr_f = out / f"ios-chapter-{label}-stdout.txt", out / f"ios-chapter-{label}-stderr.txt"
    shot = lambda tag: out / f"ios-chapter-{label}-{tag}.png"
    log(f"=== {label}: {name} ({udid}) ===")
    sh(["xcrun", "simctl", "boot", udid])
    if sh(["xcrun", "simctl", "bootstatus", udid, "-b"]).returncode != 0:
        log(f"{label}: boot failed")
        return v | log_findings("")
    v["install"] = sh(["xcrun", "simctl", "install", udid, str(app)]).returncode == 0
    if not v["install"]:
        return v | log_findings("")
    env = dict(os.environ, SIMCTL_CHILD_WF_FRAME_RATE_CHECKS="1",
               SIMCTL_CHILD_WF_TOUCH_SCRIPT=TOUCH_SCRIPT)
    start_wall = time.time()
    r = sh(["xcrun", "simctl", "launch", "--terminate-running-process",
            f"--stdout={stdout_f}", f"--stderr={stderr_f}", udid, BUNDLE_ID], env=env)
    log(r.stdout.strip() + r.stderr.strip())
    t0 = time.monotonic()
    v["launch"] = r.returncode == 0
    if not v["launch"]:
        return v | log_findings("")
    pid = r.stdout.strip().split()[-1]
    alive = lambda: subprocess.run(["ps", "-p", pid], stdout=subprocess.DEVNULL).returncode == 0

    def wait_until(t: float) -> None:
        while (now := time.monotonic() - t0) < t:
            if v["level_loaded_at"] is None and stderr_f.exists() and ROOM_RENDER in stderr_f.read_text(errors="replace"):
                v["level_loaded_at"] = round(now, 1)
                log(f"{label}: ROOM-RENDER seen at t={now:.1f} s")
            time.sleep(min(0.5, t - now))

    def snap(tag: str) -> Path:
        p = shot(tag)
        sh(["xcrun", "simctl", "io", udid, "screenshot", str(p)])
        log(f"{label}: screenshot {p.name} at t={time.monotonic() - t0:.1f} s")
        return p

    wait_until(CARD_AT)
    v["alive_20s"] = alive()
    card = snap("card")
    sh(["xcrun", "simctl", "launch", udid, "com.apple.Preferences"])
    time.sleep(2)
    sh(["xcrun", "simctl", "launch", udid, BUNDLE_ID])
    time.sleep(RESUME_SETTLE)
    fps = sh([sys.executable, str(REPO / "tests" / "check_frame_rate_log.py"), str(stdout_f), "--resume"])
    log(f"{label}: frame-rate check: {(fps.stdout + fps.stderr).strip()[-300:]}")
    v["fps_check"] = fps.returncode == 0
    wait_until(FIRE_AT[0]); fire1 = snap("fire-1")
    wait_until(FIRE_AT[1]); fire2 = snap("fire-2")
    wait_until(PORTAL_AT); snap("portal")
    wait_until(LOVE_AT); snap("love")
    v["alive_end"] = alive()

    if card.exists():
        w, h, px = read_png(downscaled(card))
        v["card_colours"] = centre_colours(w, h, px)
    if fire1.exists() and fire2.exists():
        wa, ha, pa = read_png(downscaled(fire1))
        wb, hb, pb = read_png(downscaled(fire2))
        if (wa, ha) == (wb, hb):
            mask = bytearray(c // 3 for c in pa)
            v["fire_pixels"], v["fire_bbox"] = fire_change(wa, ha, pa, pb, mask=mask)
            v["fire_frame"] = [wa, ha]
            write_png(shot("fire-diff"), wa, ha, mask)
    for f in out.glob(f"ios-chapter-{label}-*.small.png"):
        f.unlink()

    ulog = sh(["xcrun", "simctl", "spawn", udid, "log", "show", "--predicate",
               'processImagePath CONTAINS "wf_game"', "--style", "compact", "--last", "3m"]).stdout
    text = "\n".join(p.read_text(errors="replace") for p in (stdout_f, stderr_f) if p.exists())
    (out / f"ios-chapter-{label}-launch.log").write_text(
        f"=== {label}: {name} ({udid}) ===\n=== stdout ===\n"
        + (stdout_f.read_text(errors="replace") if stdout_f.exists() else "")
        + "=== stderr ===\n" + (stderr_f.read_text(errors="replace") if stderr_f.exists() else "")
        + "=== unified log (wf_game, last 3m) ===\n" + ulog)
    v |= log_findings(text + "\n" + ulog)
    for f in Path.home().glob("Library/Logs/DiagnosticReports/wf_game*"):
        if f.stat().st_mtime >= start_wall:
            shutil.copy(f, out / f"ios-chapter-crash-{label}-{f.name}")
            log(f"{label}: crash report {f.name}")
    sh(["xcrun", "simctl", "terminate", udid, BUNDLE_ID])
    sh(["xcrun", "simctl", "shutdown", udid])
    return v


def run(app: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    # Evidence for the plan's question: does simctl offer tap injection?
    help_text = "".join(c.stdout + c.stderr for c in (sh(["xcrun", "simctl", "help"]),
                                                       sh(["xcrun", "simctl", "io", "help"])))
    (out / "ios-chapter-simctl-help.txt").write_text(help_text)
    log("simctl subcommands mentioning tap/touch/input: "
        + (", ".join(l.strip() for l in help_text.splitlines() if re.search(r"\b(tap|touch|input)\b", l, re.I)) or "none"))
    runtime, devices = pick_devices()
    log(f"runtime: {runtime}")
    results = [run_device(label, udid, name, app, out) for label, udid, name in devices]
    (out / "ios-chapter-verdict.json").write_text(json.dumps({"runtime": runtime, "devices": results}, indent=1))
    print(f"=== iOS chapter verdict (runtime {runtime}) ===")
    rc = 0 if results else 1
    for v in results:
        ok = device_ok(v)
        rc |= 0 if ok else 1
        print(f"{v['label']}: {v['name']} install={v['install']} launch={v['launch']} "
              f"alive_20s={v['alive_20s']} alive_end={v['alive_end']} wf_args={v['wf_args']} "
              f"room_render={v['room_render']} zforth_errors={len(v['zforth_errors'])} "
              f"texture_slot_error={v['texture_slot_error']} fps_check={v['fps_check']} "
              f"fire_pixels={v['fire_pixels']} fire_bbox={v['fire_bbox']} card_colours={v['card_colours']} "
              f"level_loaded_at={v['level_loaded_at']} touch_a={v['touch_a']} touch_up={v['touch_up']}")
        for line in v["zforth_errors"]:
            print(f"  zforth: {line}")
        print(f"IOS {v['label'].upper()}: {'OK' if ok else 'FAIL'}")
    print("TOUCH PARITY: NOT MET (iOS HUD is a D-pad with A and B, hal/ios/input.mm; "
          "Android draws a joystick with A to D and narrows to A and C over a card, "
          "hal/android/touch_controls.h)")
    if not any(d[0] == "ipad" for d in devices):
        print("IOS IPAD: FAIL (no iPad on an iOS runtime with an iPhone)")
    return rc


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bundle", help="verify the APK and write a .app copy that carries its chapter")
    b.add_argument("--apk", type=Path, required=True)
    b.add_argument("--apk-sha256", required=True)
    b.add_argument("--level-sha256", required=True)
    b.add_argument("--app", type=Path, help="built wf_game.app (default: found under engine/ or build-ios-sim/)")
    b.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("run", help="run the chapter .app on an iPhone and an iPad simulator")
    r.add_argument("--app", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    if a.cmd == "bundle":
        app = a.app or find_app(Path.cwd())
        if not app:
            raise SystemExit("no wf_game.app under engine/ or build-ios-sim/")
        log(f"app: {app}")
        print(bundle(a.apk, a.apk_sha256, a.level_sha256, app, a.out))
        return 0
    return run(a.app, a.out)


if __name__ == "__main__":
    sys.exit(main())
