"""Regression guard for the clownfish idle rig (the aquarium level's canonical fish).

Plan: docs/plans/2026-09-30-clownfish-idle-animation.md
Model + Forth: wflevels/aquarium/clownfish.py, wflevels/aquarium/clownfish_idle.fth
Level: wflevels/aquarium_idle (task aquarium-idle-level; the probe: task aquarium-idle-probe-level)

Static (no display needed): the exported .lev carries exactly the five rig parts as Mass-0
statplats, an invisible gravity-free Physics Player, both Forth entry points, the actor
indices the Director addresses, and no snowgoons actor names.

Runtime (needs a display and engine/wf_game): the level runs paused under the debug bridge
and is stepped frame by frame at -rate20, so every sample is one engine tick.
  * idle: the idle weight reaches 1; the tail, pectoral and dorsal channels all move; the
    body part bobs about the Player's z with the authored amplitude; the Player itself
    does not move (the idle is cosmetic). Two bridge screenshots of the idle must differ.
  * blend: holding RIGHT drops the idle weight to 0 through at least one intermediate tick
    (a blend, not a snap) and the Player swims +x; after release the weight climbs back to
    1 (no stuck state) and the parts move again.
  * probe: ROTATION_C written by a Physics actor's own script, by the Director into a
    statplat (write-actor-mailbox) and by an anchored platform's own script all read back.

WF_IDLE_SABOTAGE=1 hot-reloads the Director with an empty script before measuring: the
runtime test must then FAIL (that is how the guard was checked to have teeth).

    task test-aquarium-idle            # builds both levels first
    python3 -m pytest tests/test_aquarium_idle.py -v
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO / "wflevels" / "aquarium"))
from debug_bridge_client import BridgeClient  # noqa: E402
import clownfish  # noqa: E402

WF = REPO / "engine" / "wf_game"
LIB = REPO / "engine" / "libs"
GAME_CWD = REPO / "wfsource" / "source" / "game"
LEV = REPO / "wflevels" / "aquarium_idle" / "aquarium_idle.lev"
IFF = REPO / "wflevels" / "aquarium_idle-standalone.iff"
PROBE_IFF = REPO / "wflevels" / "aquarium_idle_probe-standalone.iff"
PORT = int(os.environ.get("WF_BRIDGE_PORT", "7797"))
SHOTS = Path(os.environ.get("AQUARIUM_IDLE_SHOTS", str(Path.home() / "tmp" / "aquarium-idle")))

X_POS, Y_POS, Z_POS, ROT_A, ROT_B, ROT_C, Z_SCALE, TIME = 3009, 3010, 3011, 3012, 3013, 3014, 3042, 1906
JOY_RIGHT = 1 << 13
JOY_RAW = 1909                  # INDEXOF_HARDWARE_JOYSTICK1_RAW
FISH = clownfish.Clownfish()
T = FISH.T
MB = clownfish.MB
DT = 0.05                       # -rate20


# ── .lev parsing ─────────────────────────────────────────────────────────────
def _objects(lev_text: str) -> dict[str, str]:
    out = {}
    for chunk in lev_text.split("{ 'OBJ'")[1:]:
        m = re.search(r"\{ 'NAME' \"([^\"]+)\" \}", chunk)
        if m:
            out[m.group(1)] = chunk
    return out


def _field(chunk: str, name: str) -> str | None:
    m = re.search(r"\{ '(?:STR|FX32|I32|FILE)'\s*\{ 'NAME' \"" + re.escape(name) + r"\" \}(.*?)\n", chunk)
    return m.group(1) if m else None


def _str(chunk: str, name: str) -> str | None:
    f = _field(chunk, name)
    if f is None:
        return None
    m = re.search(r"\{ '(?:DATA|STR)' \"(.*)\" \}", f)
    return m.group(1) if m else None


def _num(chunk: str, name: str) -> float | None:
    f = _field(chunk, name)
    m = re.search(r"\{ 'DATA' (-?[\d.]+)", f or "")
    return float(m.group(1)) if m else None


@pytest.fixture(scope="module")
def lev():
    if not LEV.exists():
        pytest.skip(f"missing {LEV} (run `task aquarium-idle-level`)")
    return _objects(LEV.read_text(errors="replace"))


def test_rig_parts_are_mass0_anchored_platforms(lev):
    for name in clownfish.PART_NAMES:
        assert name in lev, f"rig part {name} missing from the .lev"
        chunk = lev[name]
        # NOT statplat: every StatPlat gets a Jolt static body whatever its Mass, and a
        # statplat body part pins the Player's capsule (actor.cc:747-762, :543-593).
        assert _str(chunk, "Class Name") == "platform", f"{name} must be an anchored platform, not a statplat"
        assert _str(chunk, "Mobility") == "Anchored", name
        assert _num(chunk, "Mass") == 0.0, f"{name} must be Mass 0 (out of WF actor collision)"
        assert _str(chunk, "Mesh Name") == clownfish.mesh_file(name), name
    assert sum(1 for n in lev if n.startswith("clownfish-")) == len(clownfish.PART_NAMES)


def test_player_is_invisible_gravity_free_physics_hull(lev):
    p = lev["Player"]
    assert _str(p, "Class Name") == "player"
    assert _str(p, "Mobility") == "Physics"
    assert _num(p, "Falling Acceleration") == 0.0
    assert _num(p, "Visibility Mailbox") == 0.0, "the Player is the invisible hull; the parts are the fish"
    assert _str(p, "Mesh Name") == clownfish.PLAYER_MESH.replace("-", "_") + ".iff"
    script = _str(p, "Script") or ""
    assert script.rstrip("\\n").endswith(clownfish.ENTRY_PLAYER), "Player script must run fish-player-tick"


def test_player_collision_box_is_authored_symmetric_and_not_thin(lev):
    """levcomp grows any side under 0.25 m from its MIN face, shoving the capsule sideways
    (aquarium plan, Phase 1 verdict); an authored symmetric box >= 0.25 m is taken verbatim."""
    m = re.search(r"\"Global Bounding Box\" \} \{ 'DATA' " + r"\s*".join([r"(-?[\d.]+)\(1\.15\.16\)"] * 6),
                  lev["Player"])
    assert m, "Player has no Global Bounding Box"
    x0, y0, z0, x1, y1, z1 = (float(v) for v in m.groups())
    for lo, hi, axis in ((x0, x1, "x"), (y0, y1, "y"), (z0, z1, "z")):
        assert hi - lo >= clownfish.MIN_COLLISION_SPAN_M - 1e-4, f"Player box {axis} span {hi - lo:.3f} < 0.25 m"
        assert abs(lo + hi) < 1e-3, f"Player box not symmetric in {axis}: {lo:.3f}..{hi:.3f}"
    assert (x0, y0, z0, x1, y1, z1) == pytest.approx(FISH.collision_box(), abs=1e-3)


def test_mesh_triangles_clear_the_engine_floor():
    """math/vector3.hpi:243 aborts the load on a triangle under ~3e-5 m²; keep a 2x margin at x10."""
    area = FISH.min_triangle_area()
    assert area > 2 * clownfish.ENGINE_MIN_TRIANGLE_M2, f"smallest triangle {area:.2e} m²"


def test_director_runs_the_rig_with_the_right_indices(lev):
    script = _str(lev["Director"], "Script") or ""
    assert clownfish.ENTRY_DIRECTOR in script
    names = list(lev)                     # exporter order = runtime order − bias (checked at runtime below)
    for name in clownfish.PART_NAMES:
        m = re.search(r": fish-actor-" + clownfish.ROLES[name] + r" (\d+) ;", script)
        assert m, f"no index constant for {name}"
        assert int(m.group(1)) == names.index(name) + 1, f"{name}: header index != export position + 1"


def test_no_snowgoons_names_survive(lev):
    leaked = [n for n in lev if re.search(r"(player|target|camshot|light|matte|room|director|camera)_?\d+$", n, re.I)]
    assert not leaked, f"snowgoons scaffold names leaked: {leaked}"


# ── runtime ──────────────────────────────────────────────────────────────────
requires_runtime = pytest.mark.skipif(
    not os.environ.get("DISPLAY") or not WF.exists(),
    reason="needs a display (wf_game opens a GL window) and engine/wf_game")


class Game:
    def __init__(self, iff: Path, tag: str):
        if not iff.exists():
            pytest.skip(f"missing {iff} (run the level's task)")
        SHOTS.mkdir(parents=True, exist_ok=True)
        self.log_path = SHOTS / f"{tag}.log"
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
        self.log = self.log_path.open("w")
        self.proc = subprocess.Popen(
            [str(WF), f"-L{iff}", "-rate20", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1",
             "--debug-print-actors"],
            cwd=str(GAME_CWD), env=env, stdout=self.log, stderr=subprocess.STDOUT,
            preexec_fn=lambda: __import__("resource").setrlimit(__import__("resource").RLIMIT_CORE, (0, 0)))
        self.cli = BridgeClient("127.0.0.1", PORT, timeout=20.0)
        self.cli.send({"op": "pause"})

    def actor(self, mesh: str) -> int:
        rx = re.compile(r"actor idx=(\d+) mesh=" + re.escape(mesh) + r" ")
        deadline = time.time() + 15
        while time.time() < deadline:
            m = rx.search(self.log_path.read_text(errors="replace"))
            if m:
                return int(m.group(1))
            time.sleep(0.1)
        raise AssertionError(f"{mesh} not in --debug-print-actors output ({self.log_path})")

    def watch(self, pairs):
        for idx, mb in pairs:
            self.cli.watch(idx=idx, mailbox=mb)

    def value(self, idx, mb):
        with self.cli._lock:
            return self.cli.mailbox_values.get((idx, mb))

    def step(self, clock_idx: int, n: int = 1):
        """Advance n ticks; return once the level clock (watched on clock_idx) has moved n × DT."""
        t0 = self.value(clock_idx, TIME) or 0.0
        self.cli.send({"op": "step", "frames": n})
        deadline = time.time() + 10
        while time.time() < deadline:
            t = self.value(clock_idx, TIME)
            if t is not None and t >= t0 + n * DT - 1e-4:
                time.sleep(0.03)          # the same frame's batch finishes arriving
                return
            time.sleep(0.005)
        raise AssertionError(f"step {n} did not advance TIME from {t0} ({self.log_path})")

    def screenshot(self, path: Path):
        path.unlink(missing_ok=True)
        self.cli.send({"op": "screenshot", "filename": str(path)})
        msg = self.cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=10)
        assert msg and msg.get("op") == "screenshot_done", f"screenshot failed: {msg}"

    def close(self):
        try:
            self.cli.close()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.log.close()


def _differing_pixels(a: Path, b: Path) -> int:
    np = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    ia = np.asarray(Image.open(a).convert("RGB")).astype(np.int16)
    ib = np.asarray(Image.open(b).convert("RGB")).astype(np.int16)
    return int((np.abs(ia - ib).max(axis=2) > 8).sum())


@requires_runtime
def test_idle_moves_parts_not_physics_and_blends_with_swimming():
    g = Game(IFF, "aquarium_idle")
    try:
        player = g.actor(clownfish.PLAYER_MESH.replace("-", "_") + ".iff")
        part = {n: g.actor(n.replace("-", "_") + ".iff") for n in clownfish.PART_NAMES}
        # The indices baked into the Director are the ones the engine assigned.
        script = _str(_objects(LEV.read_text(errors="replace"))["Director"], "Script") or ""
        for n, i in part.items():
            assert f": fish-actor-{clownfish.ROLES[n]} {i} ;" in script, f"{n} is runtime actor {i}; header disagrees"
        assert f": fish-actor-player {player} ;" in script

        body, tail, dorsal, pec = (part["clownfish-body"], part["clownfish-tail"],
                                   part["clownfish-dorsal"], part["clownfish-pec-near"])
        g.watch([(player, TIME), (player, X_POS), (player, Y_POS), (player, Z_POS), (player, MB["fish-w"]),
                 (player, JOY_RAW),
                 (body, Z_POS), (body, ROT_C), (tail, ROT_C), (pec, ROT_B), (dorsal, Z_SCALE)])
        # Hermetic input: the window opens on a shared desktop and reads X11 key events
        # (gfx/gl/mesa.cc), so pin joystick1_raw to an injected 0 unless a step injects more.
        g.cli.inject_input("joystick1_raw", 0, duration_frames=-1)
        time.sleep(0.3)
        if os.environ.get("WF_IDLE_SABOTAGE") == "1":
            director = list(_objects(LEV.read_text(errors="replace"))).index("Director") + 1
            g.cli.send({"op": "reload_script", "idx": director, "source": "\\ wf\n1 drop\n"})
            time.sleep(0.3)

        def sample():
            return dict(w=g.value(player, MB["fish-w"]), px=g.value(player, X_POS), py=g.value(player, Y_POS),
                        pz=g.value(player, Z_POS), bz=g.value(body, Z_POS), bc=g.value(body, ROT_C),
                        tc=g.value(tail, ROT_C), pb=g.value(pec, ROT_B), ds=g.value(dorsal, Z_SCALE),
                        t=g.value(player, TIME), joy=g.value(player, JOY_RAW))

        # Warm up past the idle delay + ramp, then one idle window longer than a bob period.
        g.step(player, int((T["fish-idle-delay"] + T["fish-idle-in"] + 0.5) / DT))
        idle = []
        for i in range(int(3.2 / DT)):
            g.step(player)
            idle.append(sample())
            if i == 0:
                g.screenshot(SHOTS / "idle-a.png")
            if i == 7:
                g.screenshot(SHOTS / "idle-b.png")

        rng = lambda k, rows: max(r[k] for r in rows) - min(r[k] for r in rows)
        assert all(abs(r["w"] - 1.0) < 1e-3 for r in idle), \
            ("idle weight not 1 while nothing is injected (t, w, joystick1_raw): "
             f"{[(round(r['t'], 2), round(r['w'], 3), r['joy']) for r in idle if abs(r['w'] - 1) >= 1e-3]}")
        for k in ("px", "py", "pz"):
            assert rng(k, idle) < 1e-3, f"Player {k} drifted {rng(k, idle):.5f} m while idle (idle must be cosmetic)"
        # Rotation mailboxes read back in [0, 1) rev, so -0.01 comes back as 0.99: wrap every
        # angle (and every difference) into [-0.5, 0.5) or a wrap jump would fake a ~1 rev swing.
        wrap = lambda r: ((r + 0.5) % 1.0) - 0.5
        tail_rel = [wrap(r["tc"] - r["bc"]) for r in idle]
        assert max(tail_rel) - min(tail_rel) > 1.2 * T["fish-tail-idle-amp"], f"tail barely moved: {tail_rel[:6]}"
        assert max(abs(v) for v in tail_rel) < 1.2 * T["fish-tail-idle-amp"], f"tail swings too far: {max(map(abs, tail_rel))}"
        pec_sw = [wrap(r["pb"]) for r in idle]
        assert max(pec_sw) - min(pec_sw) > 1.2 * T["fish-pec-idle-amp"], \
            f"pectoral barely moved ({max(pec_sw) - min(pec_sw):.4f} rev)"
        assert max(abs(v) for v in pec_sw) < 1.3 * T["fish-pec-idle-amp"], f"pectoral swings too far: {max(map(abs, pec_sw))}"
        assert min(r["ds"] for r in idle) < 1 - 0.7 * T["fish-dorsal-amp"], "dorsal never lowered"
        assert max(r["ds"] for r in idle) > 0.97, "dorsal never raised"
        bob = [r["bz"] - r["pz"] for r in idle]
        amp = T["fish-bob-amp"]
        assert 1.5 * amp < max(bob) - min(bob) < 2.3 * amp, f"bob peak-to-peak {max(bob) - min(bob):.4f} m, want ≈ {2 * amp}"
        assert abs(sum(bob) / len(bob)) < 0.5 * amp, f"bob not centred on the Player: mean {sum(bob) / len(bob):.4f}"
        diff = _differing_pixels(SHOTS / "idle-a.png", SHOTS / "idle-b.png")
        print(f"\nIDLE  {len(idle)} ticks: w {min(r['w'] for r in idle):.3f}..{max(r['w'] for r in idle):.3f}  "
              f"tail yaw {min(tail_rel):+.4f}..{max(tail_rel):+.4f} rev  pectoral {min(pec_sw):+.4f}..{max(pec_sw):+.4f} rev  "
              f"dorsal Z_SCALE {min(r['ds'] for r in idle):.3f}..{max(r['ds'] for r in idle):.3f}  "
              f"bob {min(bob) * 1000:+.2f}..{max(bob) * 1000:+.2f} mm (mean {sum(bob) / len(bob) * 1000:+.2f})  "
              f"Player drift x/y/z {rng('px', idle):.5f}/{rng('py', idle):.5f}/{rng('pz', idle):.5f} m  "
              f"frames 0.35 s apart differ in {diff} px")
        assert diff > 300, f"two idle frames 0.35 s apart differ in only {diff} px"

        def hold(bits):
            g.cli.inject_input("joystick1_raw", bits, duration_frames=-1)     # 0 = released (and masked)
            time.sleep(0.15)

        def teleport(x):
            # X_POS through the mailbox path also moves the Jolt character (actor.cc WriteSystemMailbox).
            g.cli.set_mailbox(X_POS, x, idx=player)
            time.sleep(0.15)
            g.step(player)

        # Input arrives (LEFT): a blend, not a snap; the Player swims -x (Phase 1 speed, glide on
        # the air drag); the rig turns the visible fish half a turn. The camera is static and the
        # swim covers ~0.14 m per tick, so the fish is teleported back into frame for pictures.
        x0 = g.value(player, X_POS)
        hold(1 << 14)
        turn = []
        for i in range(int(T["fish-turn-time"] / DT) + 3):
            g.step(player)
            turn.append(sample())
            if i == 3:
                g.screenshot(SHOTS / "turn-mid.png")
        ws = [r["w"] for r in turn]
        out_ticks = next((i for i, w in enumerate(ws) if w < 1e-3), None)
        assert out_ticks is not None, f"idle weight never left 1 with LEFT held: {ws[:8]}"
        assert out_ticks <= int(T["fish-idle-out"] / DT) + 2, f"blend-out took {out_ticks} ticks"
        assert any(0.0 < w < 1.0 for w in ws[:out_ticks + 1]), f"idle → swim snapped in one tick: {ws[:6]}"
        assert g.value(player, X_POS) < x0 - 0.5, "the Player did not swim -x"
        assert rng("pz", turn) < 1e-3, "a horizontal swim moved the Player vertically"
        heading = turn[-1]["bc"] % 1.0
        assert abs(heading - 0.5) < 0.05, f"body heading {turn[-1]['bc']:.3f} rev after turning left, want ±0.5"
        print(f"LEFT  w per tick {[round(w, 3) for w in ws[:5]]}  x {x0:+.3f} -> {g.value(player, X_POS):+.3f} m "
              f"in {len(turn)} ticks  body heading {turn[-1]['bc']:.3f} rev  Player z range {rng('pz', turn):.5f} m")
        teleport(0.45)
        g.screenshot(SHOTS / "swim-left.png")

        # Release: the glide dies out, the idle comes back (no stuck state), the rig moves again.
        hold(0)
        back = []
        for _ in range(int((T["fish-idle-delay"] + T["fish-idle-in"] + 1.5) / DT)):
            g.step(player)
            back.append(sample())
        wb = [r["w"] for r in back]
        assert wb[-1] > 0.999, f"idle weight stuck at {wb[-1]:.3f} after release"
        assert any(0.0 < w < 1.0 for w in wb), "swim → idle snapped"
        late = back[-10:]
        pec_late = [wrap(r["pb"]) for r in late]
        assert max(pec_late) - min(pec_late) > 0.5 * T["fish-pec-idle-amp"], "pectorals frozen after returning to idle"
        # The release glide is the AirHandler drag (× 0.9 per tick) and never reaches exactly 0;
        # what matters is that nothing drives the Player once idle: < 1 % of swim speed, decaying.
        steps = [abs(b["px"] - a["px"]) for a, b in zip(late, late[1:])]
        back_in = next(i for i, w in enumerate(wb) if w > 0.999) + 1           # ticks since release
        print(f"BACK  w reached 1 after {back_in} ticks ({back_in * DT:.2f} s; delay+ramp = "
              f"{T['fish-idle-delay'] + T['fish-idle-in']:.2f} s)  glide at window end {steps[-1] / DT:.4f} m/s  "
              f"pectoral swing over last 10 ticks {max(pec_late) - min(pec_late):.4f} rev")
        assert steps[-1] <= steps[0] + 1e-6, f"Player motion is not decaying once idle: {steps}"
        assert steps[-1] / DT < 0.01 * T["fish-swim-speed"], f"Player still moving {steps[-1] / DT:.3f} m/s once idle"

        # RIGHT: turns back to face +X and swims +x.
        teleport(-0.6)
        x1 = g.value(player, X_POS)
        hold(JOY_RIGHT)
        right = []
        for _ in range(int(T["fish-turn-time"] / DT) + 3):
            g.step(player)
            right.append(sample())
        print(f"RIGHT x {x1:+.3f} -> {g.value(player, X_POS):+.3f} m in {len(right)} ticks  "
              f"body heading {right[-1]['bc']:.3f} rev")
        assert g.value(player, X_POS) > x1 + 0.5, "the Player did not swim +x"
        assert abs(((right[-1]["bc"] + 0.5) % 1.0) - 0.5) < 0.05, f"body heading {right[-1]['bc']:.3f}, want 0"
        teleport(-0.25)
        g.screenshot(SHOTS / "swim-right.png")
        hold(0)
    finally:
        g.close()


@requires_runtime
def test_rotation_writes_reach_physics_statplat_and_platform():
    """Aquarium plan Phase 1 step 7: do ROTATION_C writes take effect on each actor kind?"""
    g = Game(PROBE_IFF, "aquarium_idle_probe")
    try:
        fish = g.actor(clownfish.PLAYER_MESH.replace("-", "_") + ".iff")
        stat = g.actor("probe_statplat.iff")
        plat = g.actor("probe_platform.iff")
        g.watch([(fish, TIME)] + [(i, mb) for i in (fish, stat, plat) for mb in (ROT_A, ROT_B, ROT_C)])
        time.sleep(0.3)
        g.step(fish, 20)
        g.screenshot(SHOTS / "probe.png")
        got = {k: g.value(i, ROT_C) for k, i in (("physics", fish), ("statplat", stat), ("platform", plat))}
        print(f"\nPROBE ROTATION_C read back after 20 ticks (wrote 0.125): {got}  "
              f"A/B: {[(g.value(i, ROT_A), g.value(i, ROT_B)) for i in (fish, stat, plat)]}")
        for kind, v in got.items():
            assert v is not None and abs(v - 0.125) < 0.002, f"ROTATION_C on the {kind} reads {v}, wrote 0.125"
        g.step(fish, 20)                  # and it sticks while Jolt keeps stepping the character
        assert abs(g.value(fish, ROT_C) - 0.125) < 0.002
    finally:
        g.close()
