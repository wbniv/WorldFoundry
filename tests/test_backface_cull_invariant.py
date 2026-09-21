"""Guards the `WF_CULL` default-ON flip (2026-09-21).

Regression guard for plan step 6 of
docs/plans/2026-06-13-planetarium-dome-view-engine-wide-backface-culling.md
("Effort 2" — the 20-level sweep that justified flipping the default).

Two invariants:

1. **The default is ON.** `backend_modern.cc::DrawTriangle` reads `WF_CULL`
   once as `!e || atoi(e) != 0`. A level whose faces are wound backwards
   therefore renders the same with the variable unset as with `WF_CULL=1`,
   and differently with `WF_CULL=0`. Asserting all three at once is what
   catches someone flipping the sense back (or an `e && ...` typo) — a test
   that only compared unset vs `WF_CULL=1` on *shipped* content would pass
   under either default, because shipped content is culling-clean.

   The deliberately-backwards level is built here, not committed: every
   `qbert_practice` cube triangle is reversed and the resulting MODL is
   spliced into a copy of the standalone bundle in a tmp dir. Reversing
   `(v1, v2, v3) -> (v1, v3, v2)` permutes shorts inside the FACE chunk
   without changing its length, and `cube.iff` is embedded verbatim exactly
   once, so the splice equals a real `task build-level` run (proven in the
   plan's Effort 1c step 6 and Effort 1f step 3). Same technique as
   tests/test_prelit_winding_invariant.py.

2. **The cull is a no-op on shipped content.** For each shipped
   `wflevels/*-standalone.iff`, frame 20 with `WF_CULL=0` and with
   `WF_CULL=1` must agree to within that level's accepted residual. 15 of
   the 20 are byte-identical; five differ only in the back-face bleed the
   cull correctly removes, with the pixel counts recorded in ACCEPTED below
   (unchanged since the 2026-06-13 baseline). A *new* difference, or growth
   in an accepted one, means a level regressed or the cull test changed.

`-record_video` is required on Linux or `--capture-frame` silently writes
nothing (the PNG write lives inside the recorder path, gfx/gl/display.cc).
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WF_GAME = REPO_ROOT / "engine" / "wf_game"
GAME_CWD = REPO_ROOT / "wfsource" / "source" / "game"
LIB_DIR = REPO_ROOT / "engine" / "libs"
LEVELS_DIR = REPO_ROOT / "wflevels"
QBERT_DIR = LEVELS_DIR / "qbert_practice"

CAPTURE_FRAME = 20

# Accepted cull-on vs cull-off residual, in differing pixels. 0 = must be
# byte-identical. The five non-zero entries are Effort 1b's case (a) —
# a back-facing polygon was bleeding over a brighter front face and the cull
# removed it; silhouette unchanged, mostly *brighter* after — plus
# qbert_practice's z-fight tie on its convex props. Numbers reproduced
# exactly by the Effort 2 sweep, 2026-09-21.
ACCEPTED = {
    "condo_639_640": 143,
    "condo_639_640_tour": 167,
    "dome": 0,
    "filelight": 0,
    "filesys": 0,
    "marble-madness": 0,
    "marble-madness-2": 0,
    "mm_practice": 0,
    "mm_practice_blender": 0,
    "mm_practice_blender_rt": 0,
    "moon_site01": 0,
    "pilot_demo": 0,
    "qbert_practice": 93,
    "smb_w1_1": 0,
    "smb_w1_2": 0,
    "smb_w1_3": 0,
    "smb_w1_4": 0,
    "snowgoons": 98,
    "snowgoons-blender": 97,
}

# snowgoons{,-blender} are not reliably byte-reproducible run-to-run, for a
# reason that has nothing to do with culling: WFGame::StepFrame advances the
# simulation by a *measured wall-clock* delta (`_deltaTime =
# _display->PageFlip()`, game.cc:691), so frame pacing jitter perturbs it.
# Both levels have an actor sitting on a room boundary, and an extra
# `Room::UpdateRoomContents: ... fell out of room 0; re-adding` event
# repositions it and changes ~100k px. Observed once per level in 60 sweep
# runs, on a WF_CULL=0 leg in one and a WF_CULL=1 leg in the other, i.e.
# independent of the cull. Comparing them here would be flaky; their A/B is
# recorded in the plan's Effort 2 instead, taken over 6 repeats per leg.
FLAKY = {"snowgoons", "snowgoons-blender"}

# Levels whose textures need a wider VRAM box than the default (task
# run-condo / run-moon).
VRAM_FLAGS = {
    "condo_639_640": [
        "--vram-width=4096", "--vram-height=2048",
        "--vram-slot-width=1024", "--vram-slot-height=1024",
        "--vram-perm-width=1024", "--vram-perm-height=1024",
    ],
    "condo_639_640_tour": [
        "--vram-width=4096", "--vram-height=2048",
        "--vram-slot-width=1024", "--vram-slot-height=1024",
        "--vram-perm-width=1024", "--vram-perm-height=1024",
    ],
    "moon_site01": [
        "--vram-width=4096", "--vram-height=2048",
        "--vram-slot-width=1024", "--vram-slot-height=1024",
        "--vram-perm-width=1024", "--vram-perm-height=512",
    ],
}

requires_display = pytest.mark.skipif(
    not os.environ.get("DISPLAY"),
    reason="no DISPLAY — wf_game needs an X server + GL context",
)


def _capture(level_path: Path, png_path: Path, cull: str | None,
             extra: list[str] | None = None) -> None:
    """Render frame 20 of `level_path`. `cull` of None leaves WF_CULL unset."""
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB_DIR}:{env.get('LD_LIBRARY_PATH', '')}"
    env.pop("WF_CULL", None)
    if cull is not None:
        env["WF_CULL"] = cull
    subprocess.run(
        [
            str(WF_GAME),
            "--frame-step-smoke=30",
            "--cycles=1",
            "-rate20",
            "-record_video",
            *(extra or []),
            f"--capture-frame={CAPTURE_FRAME}={png_path}",
            f"-L{level_path}",
        ],
        cwd=str(GAME_CWD),          # so cd.iff resolves
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=300,
        check=False,                # exit code is not the signal; the PNG is
    )


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _differing_pixels(a: Path, b: Path) -> int:
    np = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image")
    ia = np.asarray(Image.open(a).convert("RGB")).astype(np.int16)
    ib = np.asarray(Image.open(b).convert("RGB")).astype(np.int16)
    assert ia.shape == ib.shape, f"frame size changed between legs: {ia.shape} vs {ib.shape}"
    return int((np.abs(ia - ib).max(axis=2) > 0).sum())


def _load_gen_cube():
    spec = importlib.util.spec_from_file_location(
        "qbert_gen_cube", QBERT_DIR / "gen_cube.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inside_out_qbert(tmp_path: Path) -> Path:
    """A copy of qbert_practice-standalone.iff with every cube face reversed."""
    cube_iff = QBERT_DIR / "cube.iff"
    standalone = LEVELS_DIR / "qbert_practice-standalone.iff"
    for needed in (cube_iff, standalone, QBERT_DIR / "gen_cube.py"):
        if not needed.exists():
            pytest.skip(f"missing {needed} (run `task build-level -- qbert_practice`)")

    gen_cube = _load_gen_cube()
    gen_cube.FACES = [(v1, v3, v2, mat) for (v1, v2, v3, mat) in gen_cube.FACES]
    flipped = gen_cube.build_modl()
    original = cube_iff.read_bytes()

    assert len(flipped) == len(original), (
        "reversing winding changed the MODL length — the in-place splice is no "
        "longer safe; rebuild the level instead")
    assert flipped != original, "gen_cube.FACES flip was a no-op"

    bundle = standalone.read_bytes()
    assert bundle.count(original) == 1, (
        "cube.iff is not embedded verbatim exactly once in "
        f"{standalone.name} — regenerate it with `task build-level -- qbert_practice`")

    out = tmp_path / "qbert_inside_out-standalone.iff"
    out.write_bytes(bundle.replace(original, flipped))
    assert out.stat().st_size == standalone.stat().st_size
    return out


@requires_display
def test_cull_is_on_by_default(tmp_path):
    """WF_CULL unset must render as WF_CULL=1, and WF_CULL=0 must differ."""
    if not WF_GAME.exists():
        pytest.skip(f"missing {WF_GAME} (run `task build`)")

    level = _inside_out_qbert(tmp_path)
    pngs = {}
    for label, cull in (("unset", None), ("on", "1"), ("off", "0")):
        png = tmp_path / f"{label}.png"
        _capture(level, png, cull)
        assert png.exists(), f"no capture for WF_CULL={cull!r}"
        pngs[label] = _md5(png)

    assert pngs["unset"] == pngs["on"], (
        "WF_CULL unset does not match WF_CULL=1 "
        f"({pngs['unset']} vs {pngs['on']}) — the backface cull is no longer on "
        "by default. See backend_modern.cc::DrawTriangle's cullEnabled lambda: "
        "it must read `!e || atoi(e) != 0`.")
    assert pngs["off"] != pngs["on"], (
        "WF_CULL=0 renders identically to WF_CULL=1 on a level whose faces are "
        "deliberately wound backwards — the cull is not running at all, or the "
        "opt-out no longer works.")


@requires_display
@pytest.mark.parametrize("level", sorted(ACCEPTED))
def test_cull_is_a_noop_on_shipped_levels(level, tmp_path):
    """Frame 20 must agree cull-on vs cull-off, within the accepted residual."""
    if not WF_GAME.exists():
        pytest.skip(f"missing {WF_GAME} (run `task build`)")
    if level in FLAKY:
        pytest.skip(
            f"{level} is not byte-reproducible run-to-run (wall-clock sim delta "
            "+ a room-boundary actor); see FLAKY in this module")
    iff = LEVELS_DIR / f"{level}-standalone.iff"
    if not iff.exists():
        pytest.skip(f"missing {iff}")

    extra = VRAM_FLAGS.get(level)
    off = tmp_path / "off.png"
    on = tmp_path / "on.png"
    _capture(iff, off, "0", extra)
    _capture(iff, on, "1", extra)
    assert off.exists(), f"no WF_CULL=0 capture for {level}"
    assert on.exists(), f"no WF_CULL=1 capture for {level}"

    if _md5(off) == _md5(on):
        return

    n = _differing_pixels(off, on)
    budget = ACCEPTED[level]
    assert n <= budget, (
        f"{level} frame 20 differs in {n} px between WF_CULL=0 and WF_CULL=1, "
        f"over its accepted residual of {budget} px. Either a face is now being "
        "culled that should not be (check its winding: the engine's normal is "
        "(v2-v0)x(v1-v0), and the Blender exporter reverses each loop), or the "
        "cull test itself changed. Plan: docs/plans/"
        "2026-06-13-planetarium-dome-view-engine-wide-backface-culling.md")
