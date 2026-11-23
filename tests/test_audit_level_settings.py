"""scripts/audit-level-settings.py: the roster parsing and the six-piece check, on levels whose state is known."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit", ROOT / "scripts/audit-level-settings.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_rosters_follow_the_manifests():
    assert audit.roster("clocks")[:3] == ["minute_machine", "tide_harbour", "cuckoo_village"]
    tanks = audit.roster("aquarium")
    # Append-only: the Discus tank (2026-11-22) is the twelfth, after Sea Stars.
    assert len(tanks) == 12 and tanks[0] == "aquarium" and tanks[-2:] == ["aquarium_sea_stars", "aquarium_discus"]


def test_sea_stars_has_all_six_pieces():
    r = audit.audit("aquarium_sea_stars")
    assert r["type_name"] == "SeaStarsSettings"
    assert all(r[k] for k in audit.CHECKS), r


def test_a_level_with_no_settings_object_reports_nothing():
    r = audit.audit("aquarium_betta")
    assert r["type_name"] is None and not any(r[k] for k in audit.CHECKS)


def test_the_type_is_found_from_the_level_not_a_naming_rule():
    """Both reef tanks share ReefSettings, which no per-level name rule would find."""
    assert audit.audit("aquarium_thai_reef_anime")["type_name"] == "ReefSettings"
