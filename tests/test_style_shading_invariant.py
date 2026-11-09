"""Compare old cooked levels on frozen pre-style and candidate GL engines.

Set WF_STYLE_BASELINE_ENGINE and WF_STYLE_CANDIDATE_ENGINE to frozen binaries
built from the same source revision except for Phase S. Run under an X display
inside the build container. This is a real image comparison, not a source check.
The GL engines must define DESIGNER_CHEATS, or --capture-frame writes nothing
(gfx/gl/display.cc): engine/build_game.sh defines it, a CMake build needs
-DCMAKE_CXX_FLAGS=-DDESIGNER_CHEATS=1. The Metal capture is not gated.

Metal (reef plan step 14): the macos-style-metal Codemagic workflow
(scripts/macos/style-metal-ci.sh) renders the same sweep on pre-style and style
Metal engines and the shared style scene (tests/fixtures/renderer/style-scene.json).
Download its artifacts and set WF_STYLE_METAL_DIR to the style-metal/ directory.
The scene comparison also needs WF_STYLE_GL_ENGINE, a Debug GL engine built
from the checkout the workflow reports in summary.json.
"""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LEVELS = sorted((ROOT / "wflevels").glob("*-standalone.iff"))
BASELINE = os.environ.get("WF_STYLE_BASELINE_ENGINE")
CANDIDATE = os.environ.get("WF_STYLE_CANDIDATE_ENGINE")
FIXTURE = json.loads((ROOT / "tests/fixtures/renderer/style-scene.json").read_text())
# Shared with the Metal sweep, so both backends run each level with the same VRAM page.
VRAM = {name: tuple(v) for name, v in FIXTURE["sweep"]["vram"].items()}
METAL = Path(os.environ["WF_STYLE_METAL_DIR"]) if os.environ.get("WF_STYLE_METAL_DIR") else None
GL_ENGINE = os.environ.get("WF_STYLE_GL_ENGINE")


def test_standalone_fixtures_are_present():
    assert LEVELS, "no standalone levels found for the style regression sweep"


@pytest.mark.skipif(not os.environ.get("DISPLAY") or not BASELINE or not CANDIDATE,
                    reason="requires DISPLAY and both frozen GL engine paths")
@pytest.mark.parametrize("level", LEVELS, ids=lambda level: level.name)
def test_existing_level_is_pixel_identical(level, tmp_path):
    image = pytest.importorskip("PIL.Image")
    image_chops = pytest.importorskip("PIL.ImageChops")
    frames = []
    level_name = level.name.removesuffix("-standalone.iff")
    extra = []
    if level_name in VRAM:
        width, height, slot, perm_height = VRAM[level_name]
        extra = [f"--vram-width={width}", f"--vram-height={height}",
                 f"--vram-slot-width={slot}", f"--vram-slot-height={slot}",
                 "--vram-perm-width=1024", f"--vram-perm-height={perm_height}"]
    # aquarium_plants otherwise creates a new random reef on each launch.
    extra += FIXTURE["sweep"]["extra"].get(level_name, [])
    for name, binary in (("baseline", BASELINE), ("candidate", CANDIDATE)):
        out = tmp_path / (name + ".png")
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = str(ROOT / "engine/libs") + ":" + env.get("LD_LIBRARY_PATH", "")
        log_path = tmp_path / (name + ".log")
        with log_path.open("w") as log:
            result = subprocess.run([binary, "--frame-step-smoke=30", "--cycles=1", "-rate20",
                                     "-record_video", "--no-fps", f"--capture-frame=20={out}",
                                     *extra, f"-L{level}"], cwd=ROOT / "wfsource/source/game", env=env,
                                    stdout=log, stderr=subprocess.STDOUT,
                                    timeout=300, check=False)
        assert out.is_file(), f"{name} did not capture {level.name} (exit {result.returncode}; log: {log_path})"
        if level_name == "aquarium_plants":
            log_text = log_path.read_text(errors="replace")
            assert re.search(r"PLANTS settings-source=.* seed=123456 .* random_entry=0", log_text), (
                f"{name} did not use the requested deterministic plant seed; log: {log_path}")
        with image.open(out) as frame:
            frames.append(frame.convert("RGB"))
    assert frames[0].size == frames[1].size, f"frame dimensions changed for {level.name}"
    diff = image_chops.difference(*frames)
    bounds = diff.getbbox()
    assert bounds is None, f"style-off pixels changed for {level.name}, bounds {bounds}"


def _metal_summary():
    summary = METAL / "summary.json"
    assert summary.is_file(), f"no summary.json in {METAL}; is it the style-metal/ artifact directory?"
    return json.loads(summary.read_text())


@pytest.mark.skipif(METAL is None, reason="requires WF_STYLE_METAL_DIR (macos-style-metal artifacts)")
def test_metal_sweep_is_pixel_identical():
    image = pytest.importorskip("PIL.Image")
    image_chops = pytest.importorskip("PIL.ImageChops")
    sweep = _metal_summary()["sweep"]
    assert sweep, "the Metal run recorded no sweep levels"
    failures = []
    for name in sorted(sweep):
        frames = [METAL / "sweep" / f"{name}-{side}.png" for side in ("baseline", "candidate")]
        if not all(f.is_file() for f in frames):
            failures.append(f"{name}: capture missing (see logs/sweep-{name}-*.log)")
            continue
        with image.open(frames[0]) as a, image.open(frames[1]) as b:
            a, b = a.convert("RGB"), b.convert("RGB")
            if a.size != b.size:
                failures.append(f"{name}: size {a.size} vs {b.size}")
            elif (bounds := image_chops.difference(a, b).getbbox()) is not None:
                failures.append(f"{name}: style-off pixels changed, bounds {bounds}")
    assert not failures, "Metal sweep:\n" + "\n".join(failures)


# Will, 2026-11-09: "Mark expected-fail" for the textured scenes. Their only GL/Metal
# differences are texture sampling; the untextured flat-* scenes cover the shading and
# stay hard asserts.
TEXTURE_SAMPLING = pytest.mark.xfail(strict=True, reason=(
    "texture sampling differs between Mesa llvmpipe and the Apple GPU (bilinear, no mipmaps: "
    "backend_modern.cc:811-812, backend_metal.mm:853-854); the untextured flat-* scenes cover "
    "the S1/S3 shading. See docs/diagnostics/reef-style-metal-2026-11-09/README.md"))


def _scene_param(scene):
    return pytest.param(scene, marks=() if scene.startswith("flat-") else TEXTURE_SAMPLING)


@pytest.mark.skipif(METAL is None or not GL_ENGINE or not os.environ.get("DISPLAY"),
                    reason="requires WF_STYLE_METAL_DIR, WF_STYLE_GL_ENGINE and DISPLAY")
@pytest.mark.parametrize("scene", [_scene_param(s) for s in sorted(FIXTURE["scenes"])])
def test_style_scene_gl_matches_metal(scene, tmp_path):
    image = pytest.importorskip("PIL.Image")
    image_chops = pytest.importorskip("PIL.ImageChops")
    metal = METAL / "scene" / f"{scene}-metal.png"
    assert metal.is_file(), f"Metal run did not capture {scene}"
    out, log_path = tmp_path / f"{scene}-gl.png", tmp_path / f"{scene}-gl.log"
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(ROOT / "engine/libs") + ":" + env.get("LD_LIBRARY_PATH", "")
    with log_path.open("w") as log:
        result = subprocess.run([GL_ENGINE, *FIXTURE["common_args"],
                                 f"--capture-frame={FIXTURE['capture_frame']}={out}",
                                 f"-L{ROOT / FIXTURE['scenes'][scene]}"],
                                cwd=ROOT / "wfsource/source/game", env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=300, check=False)
    assert out.is_file(), f"GL did not capture {scene} (exit {result.returncode}; log: {log_path})"
    with image.open(out) as gl, image.open(metal) as mt:
        gl, mt = gl.convert("RGB"), mt.convert("RGB")
        assert gl.size == mt.size, f"{scene}: GL {gl.size} vs Metal {mt.size}"
        worst = max(high for _, high in image_chops.difference(gl, mt).getextrema())
    assert worst <= FIXTURE["max_channel_delta"], (
        f"{scene}: GL and Metal differ by up to {worst}/255 per channel "
        f"(allowed {FIXTURE['max_channel_delta']}); GL capture {out}")
