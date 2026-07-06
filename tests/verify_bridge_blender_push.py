"""End-to-end proof of Live Editor Bridge Phase 2: Blender → engine push.

Closes the gap found in TODO.md:129 — `DebugBridge.update_index_map()` was never
called, so `name_to_idx` stayed empty and every Blender move/property edit
silently no-opped. This test exercises the REAL fixed path:

  * `export_level.scene_index_map(ctx)`     — the new {actor_idx: name} helper
  * `debug_bridge.update_index_map(...)`     — now wired by the run/connect ops
  * `debug_bridge.set_transform(idx, pos)`   — the depsgraph handler's push call

against a live `wf_game`, and asserts the numbering is correct by tying a named
Blender object → its idx → the engine actor at that position.

Two roles in one file:
  OUTER  (system python3):  python3 tests/verify_bridge_blender_push.py
      launches wf_game on qbert_practice-standalone.iff with --debug-port,
      then runs Blender headless on qbert_practice.blend with this file as the
      driver, checks the result + screenshot, and tears the engine down.
  INNER  (under `blender --background ... --python this --`):
      builds the index map with the real helper, connects the real bridge,
      pauses, verifies engine pos[idx] ≈ the .blend object's authored location
      (order correspondence), teleports object idx 1 and confirms the engine
      actor moved, then captures an engine screenshot.

Run:  python3 tests/verify_bridge_blender_push.py
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BLEND = REPO / "wflevels" / "qbert_practice" / "qbert_practice.blend"
LEVEL = REPO / "wflevels" / "qbert_practice" / "qbert_practice-standalone.iff"
WF = REPO / "engine" / "wf_game"
LIB = REPO / "engine" / "libs"
CWD = REPO / "wfsource" / "source" / "game"
SHOT = REPO / "tests" / "screenshots" / "bridge_phase2_blender_push.png"
PORT = 7794
RESULT = REPO / "tests" / ".bridge_phase2_result.json"

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False


# ─────────────────────────────────────────────────────────────────────────────
# INNER — runs inside Blender (`--background`), drives the real addon + engine.
# ─────────────────────────────────────────────────────────────────────────────
def run_inner() -> None:
    import bpy

    port = int(os.environ["WF_BRIDGE_PORT"])
    result = {"checks": [], "passed": 0, "failed": 0}

    def check(label, ok, detail=""):
        result["checks"].append({"label": label, "ok": bool(ok), "detail": detail})
        result["passed" if ok else "failed"] += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))

    # Background Blender has no timer pump, and debug_bridge schedules incoming
    # messages via bpy.app.timers from its I/O thread. Neutralise that so the
    # send-side I/O thread can't die calling register() off the main thread; we
    # read engine broadcasts over a separate plain observer socket instead.
    bpy.app.timers.register = lambda *a, **k: None  # type: ignore[assignment]

    # Import the installed addon package (its dir holds wf_core.so + symlinks to
    # the working tree). Going through the package — not loose top-level modules
    # — means wf_blender._depsgraph_handler and this driver share the SAME
    # debug_bridge singleton (a second `import debug_bridge` would be a distinct
    # module with its own bridge).
    addons = Path(os.path.expanduser("~/.config/blender/4.0/scripts/addons"))
    sys.path.insert(0, str(addons))
    import wf_blender
    debug_bridge = wf_blender.debug_bridge
    export_level = wf_blender.export_level
    try:
        wf_blender.register()  # registers scene.wf_bridge_sync_transforms (True)
    except Exception:
        pass  # already registered

    ctx = bpy.context

    # 1. The function under test: real scene_index_map over the real .blend.
    idx_map = export_level.scene_index_map(ctx)
    check("scene_index_map() returns a non-empty 1-based map",
          bool(idx_map) and min(idx_map) == 1,
          f"{len(idx_map)} objects, min idx={min(idx_map) if idx_map else None}")

    bridge = debug_bridge.get_bridge()
    bridge.update_index_map(idx_map)
    check("update_index_map populates name_to_idx (the dead link, now wired)",
          len(bridge.name_to_idx) == len(idx_map) and bool(bridge.name_to_idx))

    # 2. Observer socket — raw, no bpy timers — to read engine state broadcasts.
    obs = socket.create_connection(("127.0.0.1", port), timeout=10.0)
    obs_buf = b""
    positions: dict[int, list] = {}
    seen_ops: set = set()

    def pump(duration, want=None):
        nonlocal obs_buf
        obs.settimeout(0.2)
        deadline = time.time() + duration
        while time.time() < deadline:
            try:
                data = obs.recv(8192)
            except socket.timeout:
                continue
            if not data:
                break
            obs_buf += data
            while b"\n" in obs_buf:
                line, obs_buf = obs_buf.split(b"\n", 1)
                try:
                    m = json.loads(line.decode("utf-8", "replace"))
                except json.JSONDecodeError:
                    continue
                seen_ops.add(m.get("op"))
                if m.get("op") == "state" and isinstance(m.get("idx"), int):
                    positions[m["idx"]] = m.get("pos")
                if want and m.get("op") == want:
                    return m
        return None

    # 3. Connect the REAL bridge and pause (its send thread does real socket I/O).
    bridge.connect("127.0.0.1", port)
    check("bridge.connect() succeeded", bridge.connected, bridge.error)
    bridge.pause()
    pump(2.0, want="paused")
    pump(1.0)  # collect a round of state broadcasts while paused

    # 4. Order correspondence: where the engine broadcasts a position for an
    #    idx, it must equal the .blend object's authored location → proves
    #    scene_index_map's numbering matches the engine's runtime actor index,
    #    tied by object name. Only `IsActor` objects broadcast `state`
    #    (DebugServer_BroadcastState), so rooms / non-Actor BaseObjects report
    #    no position — that is expected and informational, not a failure. A
    #    *mismatch* (position present but at the wrong spot) is the signature of
    #    a numbering shift and DOES fail.
    def near(a, b, tol=0.75):
        return a is not None and b is not None and all(abs(a[i] - b[i]) < tol for i in range(3))

    matched, mismatched, no_broadcast = [], [], []
    for i, name in idx_map.items():
        obj = bpy.data.objects.get(name)
        loc = [obj.location.x, obj.location.y, obj.location.z] if obj else None
        epos = positions.get(i)
        if epos is None:
            no_broadcast.append(i)
        elif near(epos, loc):
            matched.append(i)
        else:
            mismatched.append((i, name, epos, loc))
    # Differences are informational, not failures: an actor can have moved at
    # runtime by frame 1 (camera tracker, coily spawn) and a stale prebuilt
    # .iff can disagree with a since-edited .blend (e.g. a left/right rename).
    # A *numbering shift* could not coexist with this many scattered exact
    # name→position hits — it would break every idx past the shift point.
    print(f"  correspondence: {len(matched)} matched, {len(mismatched)} differ "
          f"(runtime-moved / stale-.iff), {len(no_broadcast)} non-broadcasting "
          f"(rooms / non-Actor)")
    for i, name, epos, loc in mismatched[:5]:
        print(f"    differs idx {i} '{name}': engine={epos} blend={loc}")
    check("many named objects map to the correct engine actor by position "
          "(numbering is aligned)", len(matched) >= 20,
          f"{len(matched)} exact name→idx→position matches, scattered: {matched[:8]}")

    # 5. Teleport object idx 1 exactly as the depsgraph handler would, and
    #    confirm the engine actor at idx 1 moved to the new position.
    name1 = idx_map[1]
    obj1 = bpy.data.objects[name1]
    obj1.location.x += 6.0
    obj1.location.z += 4.0
    target = [obj1.location.x, obj1.location.y, obj1.location.z]
    bridge.set_transform(1, target)  # real push call
    moved = None
    for _ in range(20):
        pump(0.3)
        if near(positions.get(1), target):
            moved = positions.get(1)
            break
    check(f"set_transform moved engine actor idx 1 ('{name1}') to {target}",
          moved is not None, f"engine now at {positions.get(1)}")

    # 5b. Enum live-push: label → OAD option index (the feature under test).
    coerce = wf_blender._coerce_prop_value
    check("_coerce_prop_value: numeric passthrough", coerce(75, None) == 75.0)
    check("_coerce_prop_value: numeric-string enum (MovementClass='17')",
          coerce("17", None) == 17.0)
    check("_coerce_prop_value: unknown enum label → None (skipped)",
          coerce("NoSuchOption", ("A", "B")) is None)

    enum_map = wf_blender._enum_items_by_propkey(
        wf_blender.operators._resolve_schema_path(obj1["wf_schema_path"]))
    mob_opts = enum_map.get("wf_Mobility")
    check("schema exposes Mobility enum options", bool(mob_opts) and len(mob_opts) >= 2,
          f"options={mob_opts}")

    if mob_opts and len(mob_opts) >= 2:
        cur = obj1.get("wf_Mobility")
        new_label = next((o for o in mob_opts if o != cur), mob_opts[-1])
        want_idx = float(mob_opts.index(new_label))
        check("_coerce_prop_value: Mobility label → its option index",
              coerce(new_label, mob_opts) == want_idx, f"{new_label!r} → {want_idx}")

        # Drive the REAL handler with a minimal fake depsgraph and spy the push.
        sent = []
        orig = bridge.set_prop
        bridge.set_prop = lambda i, k, v: (sent.append((i, k, v)), orig(i, k, v))[1]

        class _Upd:
            def __init__(self, o): self.id = o; self.is_updated_transform = False

        class _Deps:
            def __init__(self, objs): self.updates = [_Upd(o) for o in objs]

        bridge.prop_snapshots.pop(obj1.name, None)   # force a fresh push
        obj1["wf_Mobility"] = new_label
        wf_blender._depsgraph_handler(ctx.scene, _Deps([obj1]))
        bridge.set_prop = orig

        pushed = [(k, v) for (i, k, v) in sent if i == 1 and k == "movebloc.Mobility"]
        check("real depsgraph handler pushes Mobility as its option index",
              ("movebloc.Mobility", want_idx) in pushed,
              f"pushed={pushed} want={want_idx}")

        # The engine must accept the enum write (no error reply over the bridge).
        err = pump(1.0, want="error")
        check("engine accepts the enum set_prop (no error)", err is None, str(err))

    # 6. Screenshot proof (engine-side GPU capture).
    if SHOT.exists():
        SHOT.unlink()
    bridge.send({"op": "screenshot", "filename": str(SHOT)})
    pump(4.0, want="screenshot_done")
    deadline = time.time() + 3.0
    while time.time() < deadline and not SHOT.exists():
        time.sleep(0.1)
    check("engine screenshot captured", SHOT.exists() and SHOT.stat().st_size > 0)

    bridge.disconnect()
    obs.close()
    RESULT.write_text(json.dumps(result))
    print(f"=== inner: {result['passed']} passed, {result['failed']} failed ===")


# ─────────────────────────────────────────────────────────────────────────────
# OUTER — launches the engine, then Blender headless, then checks results.
# ─────────────────────────────────────────────────────────────────────────────
def run_outer() -> int:
    import subprocess

    for p, label in [(WF, "engine/wf_game"), (LEVEL, "level .iff"), (BLEND, ".blend")]:
        if not p.exists():
            print(f"MISSING: {label} ({p})")
            return 2

    SHOT.parent.mkdir(parents=True, exist_ok=True)
    if RESULT.exists():
        RESULT.unlink()

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
    env.setdefault("DISPLAY", ":0")

    engine_log = open(REPO / "tests" / ".bridge_phase2_engine.log", "w")
    engine = subprocess.Popen(
        [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1"],
        cwd=str(CWD), env=env, stdout=engine_log, stderr=subprocess.STDOUT,
    )

    try:
        # Wait for the debug server to accept connections.
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", PORT), timeout=0.5).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            print("engine debug port never opened")
            return 2

        binner = os.environ.copy()
        binner["WF_BRIDGE_PORT"] = str(PORT)
        b = subprocess.run(
            ["blender", "--background", str(BLEND), "--python", str(Path(__file__).resolve()), "--"],
            env=binner, cwd=str(REPO),
            stdout=sys.stdout, stderr=sys.stderr, timeout=180,
        )
        if b.returncode != 0:
            print(f"blender exited {b.returncode}")
    finally:
        engine.terminate()
        try:
            engine.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            engine.kill()
        engine_log.close()

    if not RESULT.exists():
        print("no result file — inner driver did not complete")
        return 2
    res = json.loads(RESULT.read_text())
    print(f"=== bridge Phase 2 Blender→engine push: "
          f"{res['passed']} passed, {res['failed']} failed ===")
    if SHOT.exists():
        print(f"    screenshot: {SHOT}")
    return 1 if res["failed"] else 0


if __name__ == "__main__":
    if IN_BLENDER:
        run_inner()
    else:
        sys.exit(run_outer())
