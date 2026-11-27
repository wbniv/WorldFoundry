"""Cuckoo Village's level file stays within its size gate.

Gate: 9,437,184 bytes (9 MiB), set by Will on 2026-11-27 ("Accept 9 MiB") after the size accounting in
docs/plans/2026-11-22-cuckoo-village-flowers.md (step 7, "Size gate re-set"). The level ships inside the
WF Clocks bundle, so every byte it adds is a byte on every Clocks download. Raising the gate is a
decision: record the new figure and its reason in that plan before changing it here.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEVEL = ROOT / "wflevels/cuckoo_village-standalone.iff"
GATE_BYTES = 9 * 1024 * 1024


def test_the_level_file_is_within_its_size_gate():
    size = LEVEL.stat().st_size
    assert size <= GATE_BYTES, (
        f"{LEVEL.relative_to(ROOT)} is {size:,} bytes, over its {GATE_BYTES:,}-byte gate by {size - GATE_BYTES:,}; "
        "see docs/plans/2026-11-22-cuckoo-village-flowers.md step 7")
