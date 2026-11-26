"""TideHarbourSettings, the type (plan D13 and Q9): its fields, the clocks' shared Clock sheet, and its registration.

wfsource/source/oas/tideharboursettings.oas includes settings.inc and clocksettings.inc (the Clock sheet every
clock's settings type shares: Camera drift), then Tide Harbour's own sheet. It is registered after
SeaStarsSettings in every object table, as each settings type is (Sea Stars: 53d7c718), so no existing type id
moves. The object in the level and the director's reads are tests/test_tide_harbour_settings.py.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OAS = ROOT / "wfsource/source/oas"


def test_the_type_includes_settings_and_the_shared_clock_sheet():
    oas = (OAS / "tideharboursettings.oas").read_text()
    assert re.search(r"TYPEHEADER\(Tide Harbour Settings,TideHarbourSettings\)", oas)
    assert oas.index("@include settings.inc") < oas.index("@include clocksettings.inc")
    shared = (OAS / "clocksettings.inc").read_text()
    entries = re.findall(r"TYPEENTRYINT32\(([^,]+),,(\d+),(\d+),(\d+),\"([^\"]*)\",([A-Z_|]+),", oas + shared)
    got = {name: (int(lo), int(hi), int(default), choices, "SHOW_AS_LIVE" in show) for name, lo, hi, default, choices, show in entries}
    assert got == {"Camera drift": (0, 1, 0, "Slow|Off", True), "Dial numerals": (0, 2, 0, "Roman|Thai|None", True),
                   "Gauge board": (0, 1, 0, "On|Off", True), "Boats and birds": (0, 1, 0, "On|Off", True),
                   "River panel": (0, 1, 0, "On|Off", True),
                   # Loy Krathong (a54cbd6ec, docs/plans/2026-11-24-tide-harbour-loy-krathong.md): when, and how many afloat
                   "River krathongs": (0, 1, 0, "Festival nights|Every night", True), "Krathong count": (0, 100, 30, "", True),
                   "About the map": (0, 1, 0, "(c) OpenStreetMap contributors|ODbL: openstreetmap.org/copyright", False)}   # read-only: the credit
    assert "Camera drift" in shared and "Camera drift" not in oas                 # the shared field lives in the shared sheet
    assert (OAS / "tideharboursettings.oad").is_file() and (OAS / "tideharboursettings.ht").is_file()
    assert "int32 Cameradrift;" in (OAS / "tideharboursettings.ht").read_text()


def test_every_registry_file_puts_the_type_right_after_sea_stars():
    """Append-only: the position is the type id compiled into every level, so no existing id may move.
    Tide Harbour was appended after Sea Stars; Cuckoo Village was appended after it (docs/plans/2026-11-21-cuckoo-village.md)."""
    mac = re.findall(r"^\s*OBJECTENTRY\((\w+),", (OAS / "objects.mac").read_text(), re.M)
    # Later types are appended after these two (Cuckoo Village, then LevelSettings, the global holder), so test adjacency, not the tail.
    assert mac.index("TideHarbourSettings") == mac.index("SeaStarsSettings") + 1
    for name, pattern in (("objects.h", r"(\w+)_KIND"), ("objects.e", r"(\w+)_KIND"), ("objects.names", r'"(\w+)"')):
        found = re.findall(pattern, (OAS / name).read_text())
        assert found.index("TideHarbourSettings") == found.index("SeaStarsSettings") + 1, name
    lc = (OAS / "objects.lc").read_text().split()
    assert lc.index("tideharboursettings") == lc.index("seastarssettings") + 1
    assert '#include "tideharboursettings.hp"' in (OAS / "objects.inc").read_text()
    assert (OAS / "objects.c").read_text().count("OadTideHarbourSettings(startData)") == 2
    assert "0,\t// TideHarbourSettings" in (OAS / "objects.col").read_text()
