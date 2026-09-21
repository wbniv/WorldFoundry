"""A LIGHTING_PRELIT face's colour must not depend on its winding.

Regression guard for the defect fixed in "Effort 1c — prelit is unlit"
(docs/plans/2026-06-13-planetarium-dome-view-engine-wide-backface-culling.md).

`Material::LIGHTING_PRELIT` selected a renderer (`gfx/glpipeline/rend*p.cc`)
that was a byte-for-byte copy of the lit one, so a "prelit" face was still
shaded by `dot(N, L)` in the vertex shader. `N` is the per-face normal, and
`rendobj3.cc`'s load path derives it from winding via `CalculateNormal`, so
reversing a prelit triangle changed its rendered colour even with backface
culling off. That entanglement is what blocked rewinding the `qbert_practice`
cubes (and marble-madness) as pure visibility fixes.

Method: this is a **fixed-timestep capture comparison**, not a unit test —
the term lived in the GL vertex shader, which needs a real context. The test
renders `qbert_practice` frame 20 twice with `WF_CULL=0`, once from the
shipped level and once from the same level with every cube triangle reversed,
and requires the two PNGs to be byte-identical.

The flipped level is built here rather than committed as a fixture: the cube
mesh is `wflevels/qbert_practice/cube.iff`, embedded verbatim in the level's
`-standalone.iff`, and reversing `(v1, v2, v3) -> (v1, v3, v2)` permutes
shorts inside the FACE chunk without changing its length. So the flipped MODL
is spliced into a copy of the standalone bundle in a tmp dir. Nothing in the
repo is written, and the test cannot go stale against a rebuilt qbert level.
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
LEVEL_DIR = REPO_ROOT / "wflevels" / "qbert_practice"
CUBE_IFF = LEVEL_DIR / "cube.iff"
GEN_CUBE = LEVEL_DIR / "gen_cube.py"
STANDALONE = REPO_ROOT / "wflevels" / "qbert_practice-standalone.iff"

CAPTURE_FRAME = 20


def _load_gen_cube():
    spec = importlib.util.spec_from_file_location("qbert_gen_cube", GEN_CUBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _flipped_modl():
    """The cube MODL chunk with every triangle's winding reversed."""
    gen_cube = _load_gen_cube()
    gen_cube.FACES = [(v1, v3, v2, mat) for (v1, v2, v3, mat) in gen_cube.FACES]
    return gen_cube.build_modl()


def _capture(level_path: Path, png_path: Path) -> None:
    """Render one frame of `level_path` to `png_path` with culling off.

    `-record_video` is required on Linux or --capture-frame silently writes
    nothing. The run is a fixed-step smoke cycle, so it is deterministic.
    """
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB_DIR}:{env.get('LD_LIBRARY_PATH', '')}"
    env["WF_CULL"] = "0"
    subprocess.run(
        [
            str(WF_GAME),
            "--frame-step-smoke=30",
            "--cycles=1",
            "-rate20",
            "-record_video",
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


@pytest.mark.skipif(not os.environ.get("DISPLAY"),
                    reason="no DISPLAY — wf_game needs an X server + GL context")
def test_prelit_face_colour_is_winding_independent(tmp_path):
    for needed in (WF_GAME, CUBE_IFF, GEN_CUBE, STANDALONE):
        if not needed.exists():
            pytest.skip(f"missing {needed} (run `task build` / `task build-level`)")

    original_modl = CUBE_IFF.read_bytes()
    flipped_modl = _flipped_modl()

    # Sanity: the splice is only valid if the flip is a pure permutation.
    assert len(flipped_modl) == len(original_modl), (
        "reversing winding changed the MODL length — the in-place splice below "
        "is no longer safe; rebuild the level instead"
    )
    assert flipped_modl != original_modl, "gen_cube.FACES flip was a no-op"

    bundle = STANDALONE.read_bytes()
    assert bundle.count(original_modl) == 1, (
        "cube.iff is not embedded verbatim exactly once in "
        f"{STANDALONE.name} — regenerate it with `task build-level -- "
        "qbert_practice`"
    )

    orig_level = tmp_path / "qbert_orig-standalone.iff"
    flip_level = tmp_path / "qbert_flip-standalone.iff"
    shutil.copyfile(STANDALONE, orig_level)
    flip_level.write_bytes(bundle.replace(original_modl, flipped_modl))
    assert flip_level.stat().st_size == orig_level.stat().st_size

    orig_png = tmp_path / "orig.png"
    flip_png = tmp_path / "flip.png"
    _capture(orig_level, orig_png)
    _capture(flip_level, flip_png)

    assert orig_png.exists(), "no capture for the shipped winding"
    assert flip_png.exists(), "no capture for the reversed winding"

    orig_hash = hashlib.md5(orig_png.read_bytes()).hexdigest()
    flip_hash = hashlib.md5(flip_png.read_bytes()).hexdigest()
    assert orig_hash == flip_hash, (
        "qbert_practice frame 20 differs between the shipped and reversed cube "
        f"winding with WF_CULL=0 ({orig_hash} vs {flip_hash}). All three cube "
        "materials are LIGHTING_PRELIT, so their colour must be a pure function "
        "of the material colour — a normal- or winding-dependent term has come "
        "back into the prelit draw path."
    )
