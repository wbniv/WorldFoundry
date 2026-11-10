"""levcomp writes the runtime-editing fields of the Level Object.

docs/plans/2026-10-16-runtime-object-editing.md, verification steps 2 and 3
(Phase 1): a level is compiled with the real schemas in wfsource/source/oas,
after objects of the settings type ``PlantedTankSettings`` (which declares
``SHOW_AS_LIVE`` fields) are added to ``wflevels/mm_practice/mm_practice.lev``,
whose own objects (platforms, a camera, a player...) declare none. Then:

* Editable Objects lists exactly the settings objects, in .lev order;
* Editable Object Labels holds their labels: automatic ("Planted Tank
  Settings 2"), or the object's ``Editor Label`` field;
* Editable Type Descriptors holds one entry for the type, whose trimmed .oad
  starts at its first own property sheet and whose payload offset finds the
  object's Seed and Water type;
* a ``SHOW_AS_RADIOBUTTONS|SHOW_AS_LIVE`` field authored by label only (Water
  type "Saltwater") compiles to its index (R4);
* a duplicate label fails the build.

Needs the iffcomp/levcomp Rust tools (built with cargo when absent;
CARGO_TARGET_DIR is honoured).
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
OAS = REPO / "wfsource" / "source" / "oas"
BASE = REPO / "wflevels" / "mm_practice"
OBJ_HEADER = 68
HEADER, ENTRY = 80, 1491              # .oad header and entry sizes
LEVELOBJ_PREWARM_END = 572            # Runtime Editing offsets follow at 572, 576, 580
SHOW_AS_LIVE = 0x40


def kinds() -> list[str]:
    text = (OAS / "objects.lc").read_text().split("{", 1)[1].split("}", 1)[0]
    return [line.strip() for line in text.splitlines() if line.strip()]


LEVELOBJ = kinds().index("levelobj")
SETTINGS = kinds().index("plantedtanksettings")


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


def settings_object(name: str, seed: int | None = None, water: str | None = None,
                    label: str | None = None) -> str:
    fields = [f"\t\t{{ 'NAME' \"{name}\" }}",
              "\t\t{ 'VEC3' { 'NAME' \"Position\" } { 'DATA' 0.0(1.15.16) 0.0(1.15.16) 0.0(1.15.16) } }",
              "\t\t{ 'EULR' { 'NAME' \"Orientation\" } { 'DATA' 0.0(1.15.16) 0.0(1.15.16) 0.0(1.15.16) } }",
              "\t\t{ 'STR' { 'NAME' \"Class Name\" } { 'DATA' \"plantedtanksettings\" } }"]
    if seed is not None:
        fields.append(f"\t\t{{ 'I32' {{ 'NAME' \"Seed\" }} {{ 'DATA' {seed}l }} }}")
    if water is not None:   # label only, no DATA: the value can come only from the label
        fields.append(f"\t\t{{ 'I32' {{ 'NAME' \"Water type\" }} {{ 'STR' \"{water}\" }} }}")
    if label is not None:   # a plain .lev field, not an OAD field (R1)
        fields.append(f"\t\t{{ 'STR' {{ 'NAME' \"Editor Label\" }} {{ 'STR' \"{label}\" }} }}")
    return "\t{ 'OBJ'\n" + "\n".join(fields) + "\n\t}\n"


def level_with(*objects: str) -> str:
    text = (BASE / "mm_practice.lev").read_text().rstrip()
    assert text.endswith("}")
    return text[:-1] + "".join(objects) + "}\n"


def compile_level(text: str, work: Path) -> subprocess.CompletedProcess:
    work.mkdir(parents=True, exist_ok=True)
    (work / "level.lev").write_text(text)
    subprocess.run([str(tool("iffcomp")), "-binary", f"-o={work / 'level.lev.bin'}", str(work / "level.lev")],
                   check=True, cwd=work, capture_output=True)
    return subprocess.run([str(tool("levcomp")), "level.lev.bin", str(OAS / "objects.lc"), "level.lvl", str(OAS),
                           "--mesh-dir", str(BASE), "--iff-txt", "level.iff.txt", "--textile-ini", "level.ini"],
                          cwd=work, capture_output=True, text=True)


class Level:
    def __init__(self, lvl: bytes):
        self.lvl = lvl
        count, objects = struct.unpack_from("<ii", lvl, 4)
        common_len, common_off = struct.unpack_from("<ii", lvl, 44)
        self.common = lvl[common_off:common_off + common_len]
        self.objects = []   # (kind, payload), index = level object index
        for i in range(count):
            at = struct.unpack_from("<i", lvl, objects + 4 * i)[0]
            kind, size = struct.unpack_from("<h", lvl, at)[0], struct.unpack_from("<h", lvl, at + 66)[0]
            self.objects.append((kind, lvl[at + OBJ_HEADER:at + OBJ_HEADER + size]))

    def word(self, at: int, k: int = 0) -> int:
        return struct.unpack_from("<i", self.common, at + 4 * k)[0]

    def editing_offsets(self) -> tuple[int, int, int]:
        payloads = [p for kind, p in self.objects if kind == LEVELOBJ]
        assert len(payloads) == 1
        return struct.unpack_from("<iii", payloads[0], LEVELOBJ_PREWARM_END)

    def editable(self) -> list[int]:
        at = self.editing_offsets()[0]
        out = []
        while (v := self.word(at, len(out))) != -1:
            out.append(v)
        return out

    def labels(self) -> list[str]:
        at = self.editing_offsets()[1]
        raw = self.common[at:].split(b"\0")
        return [s.decode() for s in raw[:len(self.editable())]]

    def types(self) -> list[tuple[int, int, int, bytes]]:
        at = self.editing_offsets()[2]
        out = []
        for t in range(self.word(at)):
            type_id, first, payload, oad_at, oad_len = (self.word(at, 1 + 5 * t + k) for k in range(5))
            out.append((type_id, first, payload, self.common[oad_at:oad_at + oad_len]))
        return out


def oad_entries(oad: bytes) -> list[tuple[int, str, int]]:
    """(button type, name, showAs) of each entry."""
    out = []
    for i in range((len(oad) - HEADER) // ENTRY):
        e = oad[HEADER + i * ENTRY:HEADER + (i + 1) * ENTRY]
        out.append((e[0], e[1:65].split(b"\0")[0].decode(), e[1 + 64 + 12 + 2 + 512]))
    return out


@pytest.fixture(scope="module")
def editable_level(tmp_path_factory) -> Level:
    work = tmp_path_factory.mktemp("editable")
    text = level_with(settings_object("Settings.001", seed=2147483647, water="Saltwater"),
                      settings_object("Settings.002", label="Goldie"),
                      settings_object("Settings.003"))
    result = compile_level(text, work)
    assert result.returncode == 0, result.stderr
    return Level((work / "level.lvl").read_bytes())


def test_lists_only_objects_whose_type_declares_a_live_field(editable_level):
    settings = [i for i, (kind, _) in enumerate(editable_level.objects) if kind == SETTINGS]
    assert len(settings) == 3
    assert editable_level.editable() == settings
    others = {kind for i, (kind, _) in enumerate(editable_level.objects) if i and i not in settings}
    assert others and SETTINGS not in others


def test_labels_are_automatic_or_the_editor_label(editable_level):
    assert editable_level.labels() == ["Planted Tank Settings 1", "Goldie", "Planted Tank Settings 3"]


def test_descriptors_are_trimmed_to_the_types_own_sheets(editable_level):
    (type_id, first, payload_offset, oad), = editable_level.types()
    assert type_id == SETTINGS
    full = (OAS / "plantedtanksettings.oad").read_bytes()
    actor_entries = (len((OAS / "actor.oad").read_bytes()) - HEADER) // ENTRY
    assert first == actor_entries == 128
    assert oad[:HEADER] == full[:HEADER]
    assert oad[HEADER:] == full[HEADER + first * ENTRY:], "descriptor indices must stay global"
    entries = oad_entries(oad)
    assert entries[0][1] == "Plant growth" and entries[0][0] == 8   # BUTTON_PROPERTY_SHEET
    live = [name for _, name, show in entries if show & SHOW_AS_LIVE]
    assert live == ["Seed", "Water type", "Growth speed", "Textures", "Sway", "Seahorses", "Greeting", "Hold seconds"]
    screensaver = next(i for i, entry in enumerate(entries) if entry[1] == "Screensaver")
    assert entries[screensaver + 1][1] == "Hold seconds"
    # The payload offset finds the first object's authored Seed, then Water type.
    first_settings = editable_level.objects[editable_level.editable()[0]][1]
    seed, water = struct.unpack_from("<ii", first_settings, payload_offset)
    assert (seed, water) == (2147483647, 1), "a radio|live field authored by label must compile to its index"


def test_duplicate_label_fails_the_build(tmp_path):
    text = level_with(settings_object("Settings.001", label="Goldie"),
                      settings_object("Settings.002", label="Goldie"))
    result = compile_level(text, tmp_path)
    assert result.returncode != 0
    assert '"Goldie"' in result.stderr and "Settings.001" in result.stderr and "Settings.002" in result.stderr


def test_a_single_object_gets_the_bare_type_name(tmp_path):
    result = compile_level(level_with(settings_object("Settings.001")), tmp_path)
    assert result.returncode == 0, result.stderr
    assert Level((tmp_path / "level.lvl").read_bytes()).labels() == ["Planted Tank Settings"]


def test_a_level_without_live_types_lists_nothing(tmp_path):
    result = compile_level((BASE / "mm_practice.lev").read_text(), tmp_path)
    assert result.returncode == 0, result.stderr
    assert Level((tmp_path / "level.lvl").read_bytes()).editing_offsets() == (-1, -1, -1)
