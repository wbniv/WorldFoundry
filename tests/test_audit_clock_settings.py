"""scripts/audit-clock-settings.py can say yes, and each of its six checks fails for the right reason.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md (D13). The audit reads a repository tree; here it reads a
tiny fake one built in a temporary directory, so a clock with every piece passes and removing any one piece
flips exactly that check.
"""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit-clock-settings.py"
spec = importlib.util.spec_from_file_location("audit_clock_settings", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

FILES = {
    "type": ["wfsource/source/oas/democlocksettings.oas", "wfsource/source/oas/democlocksettings.oad"],
    "level": ["wflevels/demo_clock/generate.py"],
    "phone": ["android/screensaver/src/clocks/assets/demo-clock-settings.json"],
    "test": ["tests/test_demo_clock_settings.py"],
}
OAS = "TYPEHEADER(Demo Clock Settings,DemoClockSettings)\n@include settings.inc\nTYPEENTRYBOOLEAN(Drift,,1,SHOW_AS_CHECKBOX|SHOW_AS_LIVE,\"\")\nTYPEFOOTER\n"
GEN = "place('democlocksettings.oad')\n# the director reads it:\nproperty@\n"


def build(root: Path, skip=()):
    for rel in sum(FILES.values(), []):
        if rel in skip:
            continue
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(OAS if rel.endswith(".oas") else GEN if rel.endswith(".py") else "x")


@pytest.fixture
def fake(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    return tmp_path


def test_a_complete_clock_passes_every_check(fake):
    build(fake)
    assert audit.audit("demo_clock") == {k: True for k in audit.CHECKS}


@pytest.mark.parametrize("missing,check", [
    ("wfsource/source/oas/democlocksettings.oas", "type"),
    ("wfsource/source/oas/democlocksettings.oad", "type"),
    ("android/screensaver/src/clocks/assets/demo-clock-settings.json", "phone"),
    ("tests/test_demo_clock_settings.py", "test"),
])
def test_removing_a_piece_fails_exactly_its_check(fake, missing, check):
    build(fake, skip=(missing,))
    res = audit.audit("demo_clock")
    assert not res[check]
    assert all(v for k, v in res.items() if k != check and not (check == "type" and k == "fields")), res


def test_a_level_that_does_not_place_the_object_or_read_it_fails(fake):
    build(fake)
    (fake / "wflevels/demo_clock/generate.py").write_text("print('nothing')\n")
    res = audit.audit("demo_clock")
    assert not res["level"] and not res["director"]


def test_a_type_with_no_live_field_fails_the_fields_check(fake):
    build(fake)
    (fake / "wfsource/source/oas/democlocksettings.oas").write_text(OAS.replace("|SHOW_AS_LIVE", ""))
    assert not audit.audit("demo_clock")["fields"]


def test_the_two_real_clocks_are_audited(capsys):
    audit.ROOT = Path(__file__).resolve().parent.parent
    names = audit.clocks()
    # The audited clocks are the bundle's (wflevels/clocks-menu.manifest). Tide Harbour joins it, and
    # so the audit, with one appended manifest line once its level is built; until then the built-in
    # list, which still names it, applies only when there is no manifest.
    assert names[0] == "minute_machine" and "tide_harbour" in audit.BUILTIN
    assert names == [l.split()[1][:-len("-standalone.iff")] for l in audit.MANIFEST.read_text().splitlines()
                     if l.startswith("level ")]
