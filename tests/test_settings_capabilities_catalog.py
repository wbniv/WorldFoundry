"""Capabilities preserve Settings owners and OAD presentation from RP01."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gen_settings_capabilities", ROOT / "scripts/gen-settings-capabilities.py")
GEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GEN)

def test_planted_actor_capabilities_use_oad_field_indices():
    subprocess.run(['cargo','build','--release','--offline','--manifest-path',str(ROOT/'wftools/wf_attr_edit/Cargo.toml')],check=True)
    oas = ROOT/'wfsource/source/oas'
    result = GEN.capabilities_oad(oas/'plantedtanksettings.oad', oas/'actor.oad', 17,
                                  'PlantedTankSettings', 'Planted Tank', ('Seahorses', 'Greeting'))
    owner, = result['objects']
    assert owner['owner'] == 17
    fields = {field['key']: field for field in owner['settings']}
    assert len(fields) == 8 and fields['Seed']['maximum'] == '2147483647'
    assert fields['Hold seconds']['value'] == '120' and fields['Hold seconds']['maximum'] == '86400'
    assert not fields['Hold seconds']['readonly'] and fields['Initial age']['readonly']



def test_invalid_inherited_oad_is_rejected(tmp_path):
    invalid = tmp_path / "invalid.oad"
    invalid.write_bytes(b"bad")
    with pytest.raises(GEN.CatalogError, match="invalid inherited OAD"):
        GEN.capabilities_oad(invalid, invalid, 17, "Settings", "Settings")
