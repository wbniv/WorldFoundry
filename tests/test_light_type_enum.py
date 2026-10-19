"""Regression guard: the engine's lightType enum must match the OAD schema.

See docs/plans/2026-09-20-engine-multi-directional-light-fix.md.

`wfsource/source/oas/light.oas` declares the Light actor's ``lightType`` field as an
INT32 with the enum-string list ``"Directional|Ambient"`` — so the value stored in a
level's OAD blob is 0 for Directional and 1 for Ambient.  That is what
``wftools/wf_blender/export_level.py`` writes, what ``levcomp-rs`` reasons about, and
what every ``.lev`` in the tree (including the legacy 3ds-Max-exported
``wflevels/snowgoons-blender/snowgoons.lev``) actually contains.

``wfsource/source/oas/levelcon.h`` had the two constants in the opposite order since the
2010 import, so ``Light::Type()`` reported every Directional light as AMBIENT_LIGHT and
vice versa.  A level with one of each survived by accident (it still got one of each,
just swapped); authoring a *second* Directional light produced two ambients and killed
the engine on ``assert(ambientLightIndex < 1)`` (wfsource/source/game/level.cc:1200).

This test locks the two definitions together so the N-th Light actor keeps resolving to
its authored type.  It is pure text parsing — no build, no DISPLAY, no engine run.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
OAS_DIR = REPO_ROOT / "wfsource" / "source" / "oas"
LIGHT_OAS = OAS_DIR / "light.oas"
LEVELCON_H = OAS_DIR / "levelcon.h"

# The same enum is mirrored here; a stale copy is how the original drift happened.
LVLDUMP_LEVELCON_H = REPO_ROOT / "wftools" / "lvldump" / "source" / "levelcon.h"


def _oas_light_type_labels() -> list[str]:
    """Enum-string list for `lightType`, in value order, from light.oas.

    Matches the *active* (non-`@*`-commented) TYPEENTRYINT32 line, e.g.

        TYPEENTRYINT32(lightType,, 0, 1, 0, "Directional|Ambient", , "...")
    """
    labels = None
    for line in LIGHT_OAS.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("@*"):  # commented-out .oas line
            continue
        m = re.search(r'TYPEENTRYINT32\(\s*lightType\s*,.*?"([^"]*\|[^"]*)"', stripped)
        if m:
            assert labels is None, "more than one active lightType entry in light.oas"
            labels = [p.strip() for p in m.group(1).split("|")]
    assert labels, f"no active TYPEENTRYINT32(lightType, ...) found in {LIGHT_OAS}"
    return labels


def _c_light_enum(header: Path) -> dict[str, int]:
    """Values of AMBIENT_LIGHT / DIRECTIONAL_LIGHT from a levelcon.h."""
    text = header.read_text()
    # The enum is anonymous; grab the braced body that mentions both names.
    m = re.search(r"enum[^{]*\{([^}]*AMBIENT_LIGHT[^}]*)\}", text)
    assert m, f"no lightType enum found in {header}"
    # Strip comments from the whole body *before* splitting on ',' — a comment
    # may itself contain commas (the body quotes light.oas's TYPEENTRYINT32 line).
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)
    body = re.sub(r"//[^\n]*", "", body)
    values: dict[str, int] = {}
    nxt = 0
    for raw in body.split(","):
        item = raw.strip()
        if not item:
            continue
        if "=" in item:
            name, val = item.split("=", 1)
            nxt = int(val.strip(), 0)
            name = name.strip()
        else:
            name = item
        values[name] = nxt
        nxt += 1
    return values


def test_oas_declares_directional_then_ambient():
    """Guard the premise: light.oas orders the labels Directional, Ambient."""
    assert _oas_light_type_labels() == ["Directional", "Ambient"]


@pytest.mark.parametrize(
    "header",
    [LEVELCON_H, LVLDUMP_LEVELCON_H],
    ids=["wfsource/source/oas", "wftools/lvldump/source"],
)
def test_c_enum_matches_oas_label_order(header):
    """AMBIENT_LIGHT / DIRECTIONAL_LIGHT must equal their light.oas label indices."""
    if not header.exists():
        pytest.skip(f"{header} not present")
    labels = _oas_light_type_labels()
    expected = {f"{label.upper()}_LIGHT": i for i, label in enumerate(labels)}
    actual = _c_light_enum(header)
    for name, want in expected.items():
        assert name in actual, f"{header}: enum is missing {name}"
        assert actual[name] == want, (
            f"{header}: {name} = {actual[name]}, but light.oas puts "
            f"{name.split('_')[0].title()!r} at index {want} of "
            f"{'|'.join(labels)!r}. The engine and the level data disagree on "
            f"lightType — see docs/plans/2026-09-20-engine-multi-directional-light-fix.md"
        )
