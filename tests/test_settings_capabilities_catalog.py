"""Capabilities preserve Settings owners and OAD presentation from RP01."""
import importlib.util
import json
from pathlib import Path
import struct

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gen_settings_capabilities", ROOT / "scripts/gen-settings-capabilities.py")
GEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GEN)


def test_planted_catalog_has_all_fields_and_presentations():
    payload = (ROOT / "wflevels/planted_tank_screensaver/settings.rprp").read_bytes()
    result = GEN.capabilities(payload)
    assert result["schema"] == 2
    assert [(obj["owner"], obj["type"]) for obj in result["objects"]] == [
        (4, "PlantedTankSettings")]
    fields = {field["key"]: field for field in result["objects"][0]["settings"]}
    assert len(fields) == 8
    assert fields["Water type"]["type"] == "choice"
    assert fields["Growth speed"]["options"][0]["label"] == "Paused"
    assert fields["Textures"]["type"] == "boolean"
    assert fields["Seed"]["maximum"] == "4294967295"
    assert fields["Hold seconds"]["maximum"] == "86400"


def test_baseline_level_keeps_same_type_owners_distinct():
    level = (ROOT / "wflevels/baseline-standalone.iff").read_bytes()
    offset = level.rfind(b"RPRP")
    assert offset > 0
    size, = struct.unpack_from("<I", level, offset + 4)
    payload = level[offset + 8:offset + 8 + size]
    objects = GEN.capabilities(payload)["objects"]
    assert [(obj["owner"], obj["type"]) for obj in objects] == [
        (19, "Settings"), (20, "Settings"), (21, "Settings")]
    assert objects[0]["settings"] == objects[1]["settings"] == objects[2]["settings"]


def test_truncated_catalog_is_rejected():
    payload = (ROOT / "wflevels/planted_tank_screensaver/settings.rprp").read_bytes()
    with pytest.raises(GEN.CatalogError, match="truncated"):
        GEN.capabilities(payload[:-1])


def test_command_writes_bounded_json(tmp_path):
    import subprocess
    out = tmp_path / "settings.json"
    subprocess.run(["python3", str(ROOT / "scripts/gen-settings-capabilities.py"),
                    "--rprp", str(ROOT / "wflevels/planted_tank_screensaver/settings.rprp"),
                    "--out", str(out)], check=True, capture_output=True)
    assert len(out.read_bytes()) < 8192
    assert json.loads(out.read_text())["objects"][0]["owner"] == 4
