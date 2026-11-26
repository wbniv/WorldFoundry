"""The lava lamp clock: the MRPH export, the wax model, the Forth director, the settings.

docs/plans/2026-11-26-lava-lamp.md, Verification 4, 5 and 7. Select with -k:

  export / morph     the exporter's MRPH chunk keeps every morph target (run after wflevels/lava_lamp/build.sh)
  model / trace      model.py holds its character; the generated zForth matches it step for step in the real VM
  settings / palette the LavaLampSettings type, the phone capability file, all 64 colour pairings
"""
from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEVEL = ROOT / "wflevels" / "lava_lamp"
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "wftools" / "wf_blender"))
import level_modules  # noqa: E402
import mrph_chunk  # noqa: E402

L, M, shapes = level_modules.load("lava_lamp", "lamp", "model", "shapes")
needs_cc = pytest.mark.skipif(shutil.which("cc") is None or shutil.which("c++") is None, reason="needs a C and C++ compiler")


def _mesh(name):
    path = LEVEL / f"{name}.iff"
    if not path.exists():
        pytest.skip(f"{path} is built by wflevels/lava_lamp/build.sh")
    return path.read_bytes()


def _vertices(iff):
    v = mrph_chunk.find_chunk(iff, b"VRTX")
    return [tuple(c / 65536 for c in struct.unpack_from("<iiIiii", v, 24 * i)[3:]) for i in range(len(v) // 24)]


# ---------------------------------------------------------------- export / morph
def test_exported_blob_keeps_every_morph_target():
    iff = _mesh("blob")
    names, pos, shade, count = mrph_chunk.decode(mrph_chunk.find_chunk(iff, b"MRPH"))
    base = _vertices(iff)
    assert names == list(shapes.BLOB_TARGETS) and count == len(base) and count >= 300
    worst = 0.0
    for t, (name, fn) in enumerate(shapes.BLOB_TARGETS.items()):
        for i, b in enumerate(base):
            want = fn(b)
            got = tuple(b[k] + pos[t][i][k] for k in range(3))
            worst = max(worst, max(abs(g - w) for g, w in zip(got, want)))
        assert all(s == (0.0, 0.0, 0.0) for s in shade[t]), f"{name}: no shade layer was authored"
    assert worst < 2e-4, f"a morph target came back {worst} away from its shape key"


def test_tint_actors_carry_an_empty_morph_chunk():
    for name in ("liquid", "glass", "wall_glow", "table_light"):
        names, _pos, _shade, count = mrph_chunk.decode(mrph_chunk.find_chunk(_mesh(name), b"MRPH"))
        assert names == [] and count > 0, name
    names, *_ = mrph_chunk.decode(mrph_chunk.find_chunk(_mesh("pool"), b"MRPH"))
    assert names == ["mound", "tower", "neck", "dip"]
    assert mrph_chunk.find_chunk(_mesh("lamp_body"), b"MRPH") is None


def test_morph_meshes_rest_where_the_level_needs_them():
    """The project's mesh-origin rule: the lamp body and the pool rest on their lowest vertex at z = 0; the blob is a
    sphere, centred."""
    for name in ("lamp_body", "pool"):
        zs = [v[2] for v in _vertices(_mesh(name))]
        assert abs(min(zs)) < 1e-4, name
    zs = [v[2] for v in _vertices(_mesh("blob"))]
    assert abs(min(zs) + max(zs)) < 1e-3


# ---------------------------------------------------------------- model / trace
def test_model_character():
    """Verification 5: pooled 25-40 %, resting 20-35 %, a cycle of 2-4 min, climbs below 0.12 globe heights a second,
    over 20 simulated minutes."""
    c = M.character(1200.0)
    assert 0.25 <= c["pooled"] <= 0.40, c
    assert 0.20 <= c["resting"] <= 0.35, c
    assert 120 <= c["cycle"] <= 240 and c["cycles"] >= 8, c
    assert c["peak_climb"] < 0.12, c


def test_model_is_deterministic_and_warmed_mid_flow():
    a, b = M.warmed(), M.warmed()
    assert [x["y"] for x in a.blobs] == [x["y"] for x in b.blobs]
    moving = [x for x in a.blobs if x["stuck"] == M.F(0)]
    assert moving, "D9: the level opens with wax moving"


@needs_cc
def test_forth_trace_matches_model():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "verify_lava_lamp_forth.py")],
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert r.stdout.strip().endswith("PASS"), r.stdout[-800:]


def test_model_script_obeys_the_level_guides():
    """docs/level-design-troubleshooting.md: ASCII only, a backslash comment only on the first line, no and/or/<0,
    the definitions above and the per-tick call last."""
    _l, _m, forth = level_modules.load("lava_lamp", "lamp", "model", "forth")
    text = forth.director_script(forth.default_indices(), forth.default_fields())
    assert text.isascii()
    lines = text.strip().split("\n")
    assert lines[0].startswith("\\ ") and not any("\\" in line for line in lines[1:])
    assert not {"and", "or", "<0"} & set(text.split())
    assert lines[-1] == "ll-tick"


# ---------------------------------------------------------------- settings / palette
def _catalog():
    exe = ROOT / "wftools/wf_attr_edit/target/release/catalog"
    if not exe.exists():
        pytest.skip("task build-rust-test-tools builds the catalog")
    out = subprocess.check_output([str(exe), str(ROOT / "wfsource/source/oas/lavalampsettings.oad")], text=True)
    return {f["key"]: f for f in json.loads(out)["fields"]}


def test_settings_type_has_the_lava_lamp_sheet():
    f = _catalog()
    for name, names, default in (("Lava color", L.LAVA, L.DEFAULT_LAVA), ("Water color", L.WATER, L.DEFAULT_WATER),
                                 ("Time display", [("Base", ""), ("Off", "")], L.DEFAULT_TIME)):
        assert name in f, name
        text = json.dumps(f[name])
        assert all(n in text for n, _ in names), name
    oas = (ROOT / "wfsource/source/oas/lavalampsettings.oas").read_text()
    sheets = [line.split("(")[1].split(",")[0] for line in oas.splitlines() if "PROPERTY_SHEET_HEADER" in line]
    assert sheets == ["Lava lamp"] and "@include clocksettings.inc" in oas and oas.rstrip().endswith("TYPEFOOTER")
    assert oas.index("clocksettings.inc") < oas.index("Lava lamp") < oas.index("global_settings.inc")


def test_settings_capability_file_lists_both_colour_fields():
    path = LEVEL / "settings-capabilities.json"
    text = path.read_text()
    for name in ("Lava color", "Water color", "Time display", "Camera drift", "Show framerate"):
        assert name in text, name
    for colour, _hex in L.LAVA + L.WATER:
        assert colour in text, colour


def test_palette_tables_match_the_plan():
    plan = (ROOT / "docs/plans/2026-11-26-lava-lamp.md").read_text()
    for (lava, lhex), (water, whex) in zip(L.LAVA, L.WATER):
        assert f"`{lhex}`" in plan and f"`{whex}`" in plan, (lava, water)
    assert L.LAVA[L.DEFAULT_LAVA][0] == "Orange" and L.WATER[L.DEFAULT_WATER][0] == "Violet"


@needs_cc
def test_every_one_of_the_64_pairings_applies_palette():
    """Every lava and water pairing goes through the director's settings path in the real VM: the wax tint and the four
    tint actors' cells are finite colours, each re-sent once and never again while unchanged."""
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "verify_lava_lamp_forth.py"), "--palette"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0 and "64 colour pairings" in r.stdout, r.stdout[-3000:] + r.stderr[-2000:]
