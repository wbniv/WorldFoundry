"""The Aquarium screensaver's lionfish tank releases goldfish on its own.

The screensaver has no input, so the Director's automatic release (gf-auto-tick, mailboxes
980-982; docs/plans/2026-11-01-lionfish-auto-goldfish.md) is the only way a goldfish ever
appears there. scripts/build-aquarium-screensaver-levels.py swaps only the Player's script,
so the Director it ships is the exported aquarium_lionfish.lev's. These checks fail if that
Director, or the lionfish level inside the shipped bundle, lacks the automatic release
(docs/plans/2026-11-02-lionfish-screensaver-auto-goldfish.md).

The source checks always run. The bundle checks need
`python3 scripts/build-aquarium-screensaver-levels.py` and skip without its output.
"""
import importlib.util
from pathlib import Path
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ROOT / "wflevels"
TANK = "aquarium_lionfish"
# The flavor's tracked asset: a symlink to the bundle the builder packs.
SHIPPED = ROOT / "android/screensaver/src/aquarium/assets/cd.iff"
VARIANT = LEVELS / (TANK + "_screensaver-standalone.iff")
CONSTANTS = (b": gf-auto-clock 980 ;", b": gf-auto-due 981 ;", b": gf-auto-seed 982 ;",
             b": gf-auto-min 45 ;", b": gf-auto-max 60 ;", b": gf-auto 1 ;")

sys.path.insert(0, str(ROOT / "scripts"))  # the builder imports level_asset_links
spec = importlib.util.spec_from_file_location("aquarium_screensaver_builder_lf",
                                              ROOT / "scripts/build-aquarium-screensaver-levels.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def _screensaver_level_text() -> str:
    source = LEVELS / TANK
    driver = (source / "screensaver_player.fth").read_text()
    return builder.player_script((source / (TANK + ".lev")).read_text(), TANK, driver)


def _levels(bundle: bytes) -> list[bytes]:
    """The level chunks of a cdpack bundle, in TOC order (wftools/cdpack-rs/src/main.rs)."""
    assert bundle[:4] == b"GAME" and bundle[8:12] == b"TOC\0"
    toc_size = struct.unpack_from("<I", bundle, 12)[0]
    chunks = []
    for offset in range(16, 16 + toc_size, 12):
        tag, start, size = struct.unpack_from("<4sII", bundle, offset)
        if tag not in (b"SHEL", b"MENU", b"UIFT"):
            chunks.append(bundle[start:start + size])
    return chunks


def test_screensaver_director_is_the_canonical_director():
    canonical = (LEVELS / TANK / (TANK + ".lev")).read_text()
    assert builder.script_of(_screensaver_level_text(), "Director") == builder.script_of(canonical, "Director")


def test_screensaver_director_has_the_auto_release():
    director = builder.script_of(_screensaver_level_text(), "Director").encode()
    for constant in CONSTANTS:
        assert constant in director, constant
    # Defined, and called from gf-tick.
    assert director.count(b"gf-auto-tick") >= 2
    assert b"gf-release-one" in director


def test_screensaver_player_runs_no_release():
    player = builder.script_of(_screensaver_level_text(), "Player")
    assert "ss-drive" in player
    assert "gf-auto-tick" not in player


@pytest.mark.skipif(not SHIPPED.is_file(), reason="run scripts/build-aquarium-screensaver-levels.py first")
def test_shipped_bundle_lionfish_level_has_the_auto_release():
    levels = _levels(SHIPPED.read_bytes())
    # cdpack packs the tanks in TankChoice.IDS order, which the builder checks against TANKS.
    assert len(levels) == len(builder.TANKS)
    lionfish = levels[builder.TANKS.index(TANK)]
    for constant in CONSTANTS:
        assert constant in lionfish, constant
    assert lionfish.count(b"gf-auto-tick") >= 2
    # No other tank carries the lionfish release.
    for tank, level in zip(builder.TANKS, levels):
        if tank != TANK:
            assert b"gf-auto-tick" not in level, tank


@pytest.mark.skipif(not (SHIPPED.is_file() and VARIANT.is_file()),
                    reason="run scripts/build-aquarium-screensaver-levels.py first")
def test_shipped_bundle_carries_the_built_lionfish_variant():
    levels = _levels(SHIPPED.read_bytes())
    assert levels[builder.TANKS.index(TANK)] == VARIANT.read_bytes()
