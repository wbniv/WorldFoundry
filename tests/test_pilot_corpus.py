"""Run the PILOT conformance corpus (tests/pilot/*.pilot) against the reference driver.

VM-tier scenarios run always (pure language, no engine). Engine-tier scenarios
self-launch wf_game per their @level directive and drive it over the debug
bridge; they skip if wf_game isn't built, no level, or no DISPLAY.

Spec: docs/pilot-language.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "pilot"))
import pilot_driver as pd  # noqa: E402

CORPUS = sorted((HERE / "pilot").glob("*.pilot"))
VM_CASES = [p for p in CORPUS if pd.tier_of(p) == "vm"]
ENGINE_CASES = [p for p in CORPUS if pd.tier_of(p) == "engine"]


@pytest.mark.parametrize("path", VM_CASES, ids=[p.name for p in VM_CASES])
def test_vm(path):
    ok, fails, code, out = pd.run_vm_scenario(path)
    assert ok, f"{path.name}: {fails}\n--- output ---\n{out}"


@pytest.mark.parametrize("idx,path", list(enumerate(ENGINE_CASES)),
                         ids=[p.name for p in ENGINE_CASES])
def test_engine(idx, path):
    # Unique port per scenario so back-to-back engine launches in one session
    # don't collide while a prior engine is still releasing its socket.
    res = pd.run_engine_scenario(path, port=7796 + idx)
    if res is None:
        pytest.skip("engine prereqs missing (wf_game / level / DISPLAY)")
    ok, fails, code, out = res
    assert ok, f"{path.name}: {fails}\n--- output ---\n{out}"
