"""The WF Clocks artwork is drawn by scripts/gen-wf-clocks-art.py: the committed files must be what it draws."""
import importlib.util
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "android/screensaver/art-src"


def load():
    spec = importlib.util.spec_from_file_location("gen_wf_clocks_art", ROOT / "scripts/gen-wf-clocks-art.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_art_is_what_the_script_draws():
    gen = load()
    for name, image in (("wf-clocks-frame.png", gen.frame_image()), ("wf-clocks-icon.png", gen.icon_image())):
        committed = Image.open(ART / name).convert("RGB")
        assert committed.size == image.size, name
        assert committed.tobytes() == image.tobytes(), f"{name} is stale: run scripts/gen-wf-clocks-art.py"


def test_sizes_match_what_the_icon_pipeline_expects():
    gen = load()
    assert gen.frame_image().size == (1280, 720)
    assert gen.icon_image().size == (720, 720)


def test_the_whole_bezel_sits_inside_androids_safe_area():
    """The adaptive icon's safe circle and the legacy crop keep the inner 72/108 of the tile: a clock bigger
    than that is clipped (the first draft's radius 290 of 360 was)."""
    gen = load()
    assert gen.ICON_CLOCK_RADIUS <= gen.ICON_SIZE / 2 * 72 / 108
