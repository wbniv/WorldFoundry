"""Level Object compatibility for the appended PrewarmNoPaletteProgram field.

The engine casts a level's Level Object OAD payload to ``_LevelObj``. The new
field is appended after the original 568-byte layout, so a level compiled
before it existed has no bytes for it: at that offset lies the next object.
``game/levelobj_fields.hp`` reads the field only when the payload's on-disk
length (``_ObjectOnDisk::OADSize``) holds it.

* An old level (``wflevels/mm_practice/mm_practice.lvl``, committed before the
  field) decodes as off, from an allocation of exactly its payload, under
  AddressSanitizer. The unchecked read of the same payload is the negative
  control: ASan must report the over-read, so the probe can detect one.
* The same level's ``.lev`` recompiled with the current schema (levcomp reads
  ``wfsource/source/oas``) gains exactly the 4 appended bytes, defaults off
  without editing, decodes on when the field is authored ``True``, and keeps
  the original 568 bytes unchanged.

Needs g++ with -fsanitize=address and the iffcomp/levcomp Rust tools (built
with cargo when absent; CARGO_TARGET_DIR is honoured).
See docs/level-building.md "No-palette opaque shader and level prewarm".
"""
from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
OAS = REPO / "wfsource" / "source" / "oas"
OLD_LEVEL = REPO / "wflevels" / "mm_practice"
LEVELOBJ_KIND = 15        # Actor::LevelObj_KIND, objects.e order
OBJ_HEADER = 68           # sizeof(_ObjectOnDisk); OADSize is the int16 at 66
ORIGINAL_BYTES = 568      # Level Object payload before the field was appended
FIELD = "Prewarm No Palette Program"


def level_object_payload(lvl: bytes) -> bytes:
    """Return the first LevelObj object's OAD payload, OADSize bytes long."""
    count, objects = struct.unpack_from("<ii", lvl, 4)
    found = []
    for index in range(count):
        offset = struct.unpack_from("<i", lvl, objects + 4 * index)[0]
        if struct.unpack_from("<h", lvl, offset)[0] == LEVELOBJ_KIND:
            size = struct.unpack_from("<h", lvl, offset + 66)[0]
            found.append(lvl[offset + OBJ_HEADER:offset + OBJ_HEADER + size])
    assert len(found) == 1, f"expected one Level Object, found {len(found)}"
    return found[0]


@pytest.fixture(scope="session")
def probe(tmp_path_factory) -> Path:
    if not shutil.which("g++"):
        pytest.skip("g++ not available")
    binary = tmp_path_factory.mktemp("levelobj") / "levelobj_fields_test"
    subprocess.run(["g++", "-std=c++17", "-fpermissive", "-w", "-g", "-O0",
                    "-fsanitize=address", "-fno-omit-frame-pointer",
                    f"-I{REPO / 'wfsource' / 'source'}", "-D__LINUX__", "-DWF_TARGET_LINUX",
                    "-DSCALAR_TYPE_FLOAT", "-DSW_DBSTREAM=0", "-DDO_ASSERTIONS=0", "-DDO_IOSTREAMS=1",
                    str(REPO / "tests" / "levelobj_fields_test.cc"), "-o", str(binary)], check=True)
    return binary


def tool(name: str) -> Path:
    crate = REPO / "wftools" / f"{name}-rs"
    target = Path(os.environ.get("CARGO_TARGET_DIR", crate / "target"))
    binary = target / "release" / name
    if not binary.exists():
        if not shutil.which("cargo"):
            pytest.skip(f"{binary} missing and cargo not available")
        subprocess.run(["cargo", "build", "--release", "--quiet",
                        "--manifest-path", str(crate / "Cargo.toml")], check=True)
    return binary


def run(probe: Path, mode: str, payload: bytes, tmp_path: Path) -> subprocess.CompletedProcess:
    path = tmp_path / f"{mode}-{len(payload)}.bin"
    path.write_bytes(payload)
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:abort_on_error=0")
    return subprocess.run([str(probe), mode, str(path)], capture_output=True, text=True, env=env)


def compile_level(lev_text: str, tmp_path: Path) -> bytes:
    (tmp_path / "level.lev").write_text(lev_text)
    subprocess.run([str(tool("iffcomp")), "-binary", f"-o={tmp_path / 'level.lev.bin'}",
                    str(tmp_path / "level.lev")], check=True, cwd=tmp_path, capture_output=True)
    subprocess.run([str(tool("levcomp")), "level.lev.bin", str(OAS / "objects.lc"), "level.lvl", str(OAS),
                    "--mesh-dir", str(OLD_LEVEL), "--iff-txt", "level.iff.txt",
                    "--textile-ini", "level.ini"], check=True, cwd=tmp_path, capture_output=True)
    return (tmp_path / "level.lvl").read_bytes()


def with_field(lev_text: str, value: bool) -> str:
    """Author the field on the level's levelobj object, as the exporter writes it."""
    entry = (f"\t\t{{ 'I32' {{ 'NAME' \"{FIELD}\" }} {{ 'DATA' {int(value)}l }} "
             f"{{ 'STR' \"{'True' if value else 'False'}\" }} }}  //False|True\n")
    marker = re.search(r"\{\s*'STR'\s*\{\s*'NAME'\s*\"Class Name\"\s*\}\s*\{\s*'DATA'\s*\"levelobj\"\s*\}\s*\}[ \t]*\n",
                       lev_text)
    assert marker, "no levelobj object in the source level"
    return lev_text[:marker.end()] + entry + lev_text[marker.end():]


def test_field_is_appended_after_the_original_layout(probe):
    out = subprocess.run([str(probe), "layout"], capture_output=True, text=True, check=True).stdout
    assert out.strip() == f"offset={ORIGINAL_BYTES} size={ORIGINAL_BYTES + 4}"
    header = (OAS / "levelobj.ht").read_text()
    members = re.findall(r"^\s*(?:int32|fixed32)\s+(\w+);", header, re.M)
    assert members[-1] == "PrewarmNoPaletteProgram", "new Level Object fields must stay appended"


def test_old_level_decodes_off_without_reading_past_its_payload(probe, tmp_path):
    payload = level_object_payload((OLD_LEVEL / "mm_practice.lvl").read_bytes())
    assert len(payload) == ORIGINAL_BYTES
    checked = run(probe, "decode", payload, tmp_path)
    assert checked.returncode == 0, checked.stderr
    assert checked.stdout.strip() == f"payload-bytes={ORIGINAL_BYTES} prewarm=0"
    # Negative control: the same read without the length check is caught.
    unchecked = run(probe, "unchecked", payload, tmp_path)
    assert unchecked.returncode != 0 and "heap-buffer-overflow" in unchecked.stderr, unchecked.stderr[-2000:]


def test_recompiled_level_round_trips_the_field(probe, tmp_path):
    source = (OLD_LEVEL / "mm_practice.lev").read_text()
    old = level_object_payload((OLD_LEVEL / "mm_practice.lvl").read_bytes())
    results = {}
    for label, text in (("absent", source), ("false", with_field(source, False)), ("true", with_field(source, True))):
        work = tmp_path / label
        work.mkdir()
        payload = level_object_payload(compile_level(text, work))
        assert len(payload) == ORIGINAL_BYTES + 4, label
        assert payload[:ORIGINAL_BYTES] == old, f"{label}: original Level Object bytes changed"
        decoded = run(probe, "decode", payload, tmp_path)
        assert decoded.returncode == 0, decoded.stderr
        results[label] = decoded.stdout.strip()
    assert results == {"absent": "payload-bytes=572 prewarm=0",
                       "false": "payload-bytes=572 prewarm=0",
                       "true": "payload-bytes=572 prewarm=1"}
