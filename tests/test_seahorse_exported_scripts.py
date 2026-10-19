"""Compile the complete exported tank scripts with the engine's Forth vocabulary."""
from test_species_movement import vm  # noqa: F401


def test_complete_planted_tank_scripts_compile_and_tick(vm):
    rows = vm('plants', 'reset 0 0 2.5\nstep 2 0 .05\n')
    assert len(rows) == 2
