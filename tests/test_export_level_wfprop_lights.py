"""Regression guard: a `wf_*`-custom-property Light must reach the .lev.

Every shipped Light actor is authored as a **plain Blender object carrying
`wf_lightRed`/`wf_lightGreen`/`wf_lightBlue`/`wf_lightType` custom properties**
— not as a native Blender `LIGHT` datablock. Since
docs/plans/2026-09-20-export-level-light-field-duplication.md removed the
hand-written emission block, the data-driven schema walk (`_emit_lev_fields`)
is the *single* path those four fields can reach the `.lev` by, and it emits a
field only when that actor's `.oad` declares it **visible** (`show_as != 6`).

`wflevels/oad/light.oad` was an older OAD generation that marks all four
``show_as == 6``. Result: `wflevels/dome` (and `filelight`/`filesys`/`treemap`,
which point at the same directory) exported with **no light fields at all**,
`levcomp` fell back to light.oas's default of 0, and the level rendered
completely black — with no error anywhere. Two guards, both pure data/text, no
Blender and no DISPLAY:

1. every OAD directory a level script actually points at declares the four
   fields visible, so the stale-schema trap cannot come back; and
2. `_warn_if_light_fields_missing` is loud when it does, so the next occurrence
   is a message rather than a black screen.

See docs/plans/2026-06-13-planetarium-dome-view-engine-wide-backface-culling.md
"Effort 1b".
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORT_LEVEL = REPO_ROOT / "wftools" / "wf_blender" / "export_level.py"

LIGHT_FIELDS = ("lightRed", "lightGreen", "lightBlue", "lightType")
HIDDEN = 6  # OAD show_as value meaning "hidden non-content" — never emitted


def _oad_dirs_used_by_level_scripts() -> dict[Path, list[str]]:
    """Map each OAD directory a `wflevels/*/blender_*.py` points at → scripts.

    The scripts spell it as an `os.path.join(REPO, ...)` of literals, so the
    path components are read straight out of the assignment's AST rather than
    by executing the script (which would need Blender).
    """
    found: dict[Path, list[str]] = {}
    for script in sorted(REPO_ROOT.glob("wflevels/*/blender_*.py")):
        try:
            tree = ast.parse(script.read_text(), filename=str(script))
        except SyntaxError:                       # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "OAD_DIR" not in names:
                continue
            call = node.value
            if not (isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "join"):
                continue
            parts = [a.value for a in call.args
                     if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if not parts:
                continue
            found.setdefault((REPO_ROOT / Path(*parts)).resolve(),
                             []).append(script.name)
    assert found, "no level script's OAD_DIR could be resolved — parser broke?"
    return found


def _load_wf_core():
    so = REPO_ROOT / "tests" / ".cache" / "wf_core.so"
    if not so.exists():
        pytest.skip("wf_core not built — run tests/test_blender_addon_export.py first")
    sys.path.insert(0, str(so.parent))
    try:
        import wf_core  # noqa: PLC0415
    except ImportError as exc:                    # pragma: no cover
        pytest.skip(f"wf_core not importable: {exc}")
    return wf_core


@pytest.mark.parametrize("oad_dir,scripts",
                         sorted(_oad_dirs_used_by_level_scripts().items()),
                         ids=lambda v: v.name if isinstance(v, Path) else "")
def test_light_oad_declares_colour_and_type_visible(oad_dir, scripts):
    """Every OAD set a level uses must emit the four light fields.

    A `show_as == 6` here is silent data loss: the light exports with no
    colour and no type, and the level renders black.
    """
    wf_core = _load_wf_core()
    light_oad = oad_dir / "light.oad"
    if not light_oad.exists():
        pytest.skip(f"{oad_dir} has no light.oad")

    schema = wf_core.load_schema(str(light_oad))
    by_key = {f.key: f for f in schema.fields()}

    problems = []
    for name in LIGHT_FIELDS:
        field = by_key.get(name)
        if field is None:
            problems.append(f"{name}: absent from the schema")
        elif getattr(field, "show_as", None) == HIDDEN:
            problems.append(f"{name}: show_as == {HIDDEN} (hidden — never emitted)")

    assert not problems, (
        f"{light_oad} is a stale/trimmed OAD generation:\n  "
        + "\n  ".join(problems)
        + f"\nUsed by: {', '.join(sorted(set(scripts)))}\n"
        "Lights authored as wf_* custom properties would export with NO colour "
        "and NO type, levcomp would default them to 0, and the level would "
        "render BLACK with no error. Refresh it from wfsource/source/oas/."
    )


def _exec_helper_namespace():
    """Exec just the helper functions out of export_level.py.

    The module imports `bpy` at top level, so it cannot be imported in a plain
    pytest run; the three functions under test touch nothing but `sys` and the
    object's `.get`, so lifting them out by AST is faithful and Blender-free.
    """
    tree = ast.parse(EXPORT_LEVEL.read_text(), filename=str(EXPORT_LEVEL))
    wanted = {"_prop_key", "_light_prop_keys", "_warn_if_light_fields_missing"}
    picked = [n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name in wanted]
    missing = wanted - {n.name for n in picked}
    assert not missing, f"{EXPORT_LEVEL}: helper(s) gone: {sorted(missing)}"
    ns: dict = {}
    exec(compile(ast.Module(body=picked, type_ignores=[]), str(EXPORT_LEVEL), "exec"), ns)
    return ns


class _StubObj:
    """Minimal stand-in for a Blender object carrying wf_* custom properties."""

    def __init__(self, name, props):
        self.name = name
        self._props = props

    def get(self, key, default=None):
        return self._props.get(key, default)


def test_warns_when_a_wfprop_light_emits_no_light_chunks(capsys):
    """The dome's exact failure: props authored, schema walk emitted nothing."""
    ns = _exec_helper_namespace()
    obj = _StubObj("Light01", {ns["_prop_key"](f): v for f, v in
                               zip(LIGHT_FIELDS, (0.65, 0.65, 0.85, "Directional"))})

    # What the stale schema produced: position/class chunks, no light chunks.
    emitted = ['{ \'I32\' { \'NAME\' "Mobility" } { \'DATA\' 0l } { \'STR\' "Anchored" } }']
    ns["_warn_if_light_fields_missing"](obj, emitted, "/x/wflevels/oad/light.oad")

    err = capsys.readouterr().err
    assert "[wf_export] ERROR" in err and "Light01" in err, err
    for name in LIGHT_FIELDS:
        assert name in err, f"{name} not named in the warning:\n{err}"
    assert "BLACK" in err, f"the consequence must be spelled out:\n{err}"
    assert "/x/wflevels/oad/light.oad" in err, err


def test_silent_when_the_light_chunks_are_present(capsys):
    """A healthy export must not warn — otherwise the signal is worthless."""
    ns = _exec_helper_namespace()
    obj = _StubObj("Light01", {ns["_prop_key"](f): v for f, v in
                               zip(LIGHT_FIELDS, (0.65, 0.65, 0.85, "Directional"))})
    emitted = [f'{{ \'FX32\' {{ \'NAME\' "{n}" }} {{ \'DATA\' 1.0(1.15.16) }} }}'
               for n in LIGHT_FIELDS]
    ns["_warn_if_light_fields_missing"](obj, emitted, "/x/oas/light.oad")
    assert capsys.readouterr().err == ""


def test_silent_for_a_light_actor_that_authors_no_colour(capsys):
    """Not every Light actor carries the props; absence is not an error."""
    ns = _exec_helper_namespace()
    ns["_warn_if_light_fields_missing"](_StubObj("Light01", {}), [], "/x/oas/light.oad")
    assert capsys.readouterr().err == ""
