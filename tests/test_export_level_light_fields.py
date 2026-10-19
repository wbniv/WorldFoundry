"""Regression guard: export_level.py must not re-implement light.oas's enums.

See docs/plans/2026-09-20-export-level-light-field-duplication.md.

``wftools/wf_blender/export_level.py`` used to emit ``lightRed``/``lightGreen``/
``lightBlue``/``lightType`` twice for every ``Light`` actor — once from the
data-driven schema walk (``_emit_lev_fields``, which reads ``light.oas``'s own
field declarations) and once from a hand-written block that carried its own
``lt_map = {"directional": 0, "ambient": 1}`` copy of light.oas's
``"Directional|Ambient"`` ordering.

That is the same bug class that cost a multi-day investigation in
``wfsource/source/oas/levelcon.h`` (see
``docs/plans/2026-09-20-engine-multi-directional-light-fix.md`` and
``tests/test_light_type_enum.py``): a hand-copied enum ordering, disconnected
from the schema, free to drift.

These tests are pure text parsing — no Blender, no build, no DISPLAY.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORT_LEVEL = REPO_ROOT / "wftools" / "wf_blender" / "export_level.py"
LIGHT_OAS = REPO_ROOT / "wfsource" / "source" / "oas" / "light.oas"

# The single function that is *allowed* to turn an enum label into an index —
# and it does so via the schema's own ``field.enum_items()``, never a literal.
SCHEMA_WALK_FUNC = "_emit_lev_fields"


def _oas_light_type_labels() -> list[str]:
    """Enum-string list for `lightType`, in value order, from light.oas."""
    labels = None
    for line in LIGHT_OAS.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("@*"):  # commented-out .oas line
            continue
        m = re.search(r'TYPEENTRYINT32\(\s*lightType\s*,.*?"([^"]*\|[^"]*)"', stripped)
        if m:
            labels = [p.strip() for p in m.group(1).split("|")]
    assert labels, f"no active TYPEENTRYINT32(lightType, ...) found in {LIGHT_OAS}"
    return labels


def test_no_hand_written_light_type_label_map():
    """No dict literal in export_level.py maps light.oas's labels to indices.

    Catches the exact shape of the deleted line::

        lt_map = {"directional": 0, "ambient": 1}

    regardless of key casing, ordering or variable name.
    """
    labels = {lbl.lower() for lbl in _oas_light_type_labels()}
    tree = ast.parse(EXPORT_LEVEL.read_text(), filename=str(EXPORT_LEVEL))

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = set()
        for k in node.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.add(k.value.lower())
        if labels and labels.issubset(keys):
            offenders.append(node.lineno)

    assert not offenders, (
        f"{EXPORT_LEVEL}: dict literal(s) at line(s) {offenders} map light.oas's "
        f"lightType labels {sorted(labels)} by hand. The index must come from the "
        f"schema itself (field.enum_items() inside {SCHEMA_WALK_FUNC}) — a second "
        f"copy of the ordering is exactly the drift that broke levelcon.h. See "
        f"docs/plans/2026-09-20-export-level-light-field-duplication.md"
    )


def test_light_field_names_emitted_only_by_the_schema_walk():
    """The four light field names appear as emitted chunk names in no function
    other than the data-driven schema walk.

    ``_emit_lev_fields`` derives every chunk name from ``field.key``, so it
    contains no ``"lightRed"``-style literal at all; any such literal elsewhere
    in the file is a second emission path.
    """
    source = EXPORT_LEVEL.read_text()
    tree = ast.parse(source, filename=str(EXPORT_LEVEL))
    field_names = ("lightRed", "lightGreen", "lightBlue", "lightType")

    # Lines that legitimately name a light field: the custom-property writes
    # that feed the schema walk, via _prop_key(...). Collect those linenos.
    allowed_lines = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_prop_key"):
            allowed_lines.add(node.lineno)

    offenders = []
    for i, line in enumerate(source.splitlines(), start=1):
        if i in allowed_lines:
            continue
        # The emission lines are f-strings whose chunk names are backslash-escaped
        # (`\"lightRed\"`); drop the escapes so a plain quoted-name match sees them.
        flat = line.replace("\\", "")
        for name in field_names:
            if f'"{name}"' in flat or f"'{name}'" in flat:
                offenders.append((i, name, line.strip()))

    assert not offenders, (
        f"{EXPORT_LEVEL}: light field name literal(s) outside a _prop_key() call — "
        f"a second .lev emission path for fields {SCHEMA_WALK_FUNC} already emits "
        f"from light.oas:\n" + "\n".join(f"  line {i}: {name}: {t}" for i, name, t in offenders)
    )
