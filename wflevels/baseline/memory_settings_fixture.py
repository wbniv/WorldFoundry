"""Baseline configuration for the shared load-time level settings tooling."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('level_memory_settings', ROOT/'scripts/level_memory_settings.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)

FIELDS = shared.FIELDS
validate = shared.validate

def load(path=None):
    return shared.load(path or HERE/'memory-settings.json')

def sheet(config=None):
    return shared.sheet(load() if config is None else config)

def project_legacy(level, config=None):
    return shared.project_legacy(level, load() if config is None else config)
