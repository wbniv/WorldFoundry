"""Sources needed by portable tests that include the plant selector."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def preview_sources(directory):
    subprocess.run(['python3', str(ROOT/'scripts/embed-planted-oad.py'),
                    str(ROOT/'wfsource/source/oas/plantedtanksettings.oad'),
                    str(directory/'planted_oad.inc')], check=True)
    return ['-I'+str(directory), str(ROOT/'engine/planted_preview.cpp'), str(ROOT/'engine/runtime_oad_adapter.cpp')]
