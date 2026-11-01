"""Each Field types case draws its own control on the TV settings form, the new choice lists,
segments and switch keep focus escapable, and path validation refuses no committed catalog.

docs/plans/2026-11-01-field-presentations.md. Runs the real form, host and TV renderer on the
catalog cooked into the baseline level (tests/runtime_property_presentation_test.cpp).
"""
import json
from pathlib import Path
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = {c["id"]: c for c in json.loads((ROOT / "docs/plans/2026-10-29-touch-settings-examples.json").read_text())}
IDS = json.loads((ROOT / "wflevels/baseline/actor-map.json").read_text())["indices"]
NEW = ["int-mailbox", "enum-default", "enum-number", "enum-dropdown", "enum-toggle", "enum-combo",
       "bool-toggle", "str-filename", "enum-long"]


def payload(level_bytes):
    """The RP01 payload of a level's RPRP chunk."""
    offset = level_bytes.rfind(b"RPRP")
    size, = struct.unpack_from("<I", level_bytes, offset + 4)
    return level_bytes[offset + 8:offset + 8 + size]


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    out = tmp_path_factory.mktemp("presentation") / "presentation"
    game = ROOT / "wfsource/source/game"
    subprocess.run([
        "c++", "-std=c++17", "-O1", "-I" + str(ROOT / "wfsource/source"),
        str(ROOT / "tests/runtime_property_presentation_test.cpp"),
        *[str(game / n) for n in ("runtime_property_ui.cc", "runtime_settings_ui.cc", "runtime_property_touch.cc",
                                  "ui_font.cc", "bitmap_text.cc")],
        *[str(ROOT / "engine" / n) for n in ("runtime_properties.cpp", "runtime_property_form.cpp", "runtime_property_host.cpp")],
        str(ROOT / "wftools/wf_attr_edit/target/release/libwf_attr_edit.a"), "-ldl", "-lpthread", "-lm", "-o", str(out)], check=True)
    return out


@pytest.fixture(scope="module")
def tv(harness, tmp_path_factory):
    rprp = tmp_path_factory.mktemp("catalog") / "baseline.rprp"
    rprp.write_bytes(payload((ROOT / "wflevels/baseline-standalone.iff").read_bytes()))
    result = subprocess.run([str(harness), "form", str(rprp), str(IDS["FieldTypes"]),
                             str(ROOT / "wfsource/source/game/ui-font.wfga")], capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.rstrip().endswith("done"), result.stdout + result.stderr
    rows, facts = {}, {}
    for line in result.stdout.splitlines():
        words = line.split()
        if words[0] == "tv":
            rows[words[1]] = dict(control=words[2], lines=int(words[3]), box=[float(w) for w in words[4:8]], section=int(words[8]))
        elif words[0] in ("keys", "count"):
            facts.setdefault("_" + words[0], []).append(" ".join(words[1:]))
        else:
            facts[words[0]] = " ".join(words[1:])
    return rows, facts


def test_every_case_draws_its_own_control(tv):
    rows, _ = tv
    assert sorted(rows) == sorted(CASES)
    for case_id, case in CASES.items():
        assert rows[case_id]["control"] == case["control"], case_id


def test_the_nine_new_controls_differ_from_a_plain_row(tv):
    rows, _ = tv
    plain = {"number", "text"}
    for case_id in NEW:
        assert rows[case_id]["control"] not in plain, case_id
    assert rows["enum-long"]["lines"] == 2  # the Placement value wraps in its box


# The row-navigation policy (Will, 2026-11-01, option 6), mirroring wfprops::keys in
# engine/runtime_property_presentation.hpp: (Left / Right change, Left on the first value goes to
# the rail, A opens the list). Choice rows with up to CYCLE_CHOICES_MAX options cycle and leave
# from the first option; with more they only open the list. The key tests follow the engine's
# table; this mirror pins the policy itself.
CYCLE_CHOICES_MAX = 4
FIXED = {
    "number": (0, 0, 0), "number-with-bounds": (0, 0, 0), "slider": (1, 0, 0), "path": (0, 0, 0),
    "segments": (1, 1, 0), "switch": (1, 1, 0),
    "chips": (1, 0, 0), "stepped-slider": (1, 0, 0), "checkbox": (1, 0, 0),
}


def policy(control, options):
    if control in ("choice-list", "numbered-choice-list"):
        return (1, 1, 1) if 2 <= options <= CYCLE_CHOICES_MAX else (0, 0, 1)
    return FIXED[control]


@pytest.fixture(scope="module")
def probes(tv):
    rows, facts = tv
    found = {}
    for raw in facts["_keys"]:
        words = raw.split()
        key, options = words[0], int(words[1])
        rule, probe = tuple(int(w) for w in words[2:5]), tuple(int(w) for w in words[6:10])
        found[key] = (rows[key]["control"], options, rule, probe)
    return found


def test_key_table_is_the_policy(probes):
    """The engine's rule table, read back for each Field types row, is the policy above."""
    for key, (control, options, rule, _) in probes.items():
        assert rule == policy(control, options), (key, control, options, rule)


def test_keys_follow_the_rule_table(probes):
    """What Left, Right and A did from the first value, derived from each row's rule."""
    for key, (control, _, (left_right, left_first_rail, a_list), probe) in probes.items():
        left_rail, left_changed, right_changed, opened = probe
        if left_right:
            assert right_changed == 1, key                      # Right changes the value
            assert left_changed == 0, key                       # nothing below the first value
            assert left_rail == left_first_rail, key            # the rail only where the rule says
        else:
            assert (left_rail, left_changed, right_changed) == (1, 0, 0), key  # Left goes to the rail
        assert opened == a_list, key


def counts(tv):
    _, facts = tv
    out = {}
    for raw in facts["_count"]:
        w = raw.split()
        out[int(w[0])] = dict(rule=tuple(int(x) for x in w[1:4]), first_rail=int(w[5]), first_value=w[6], mid_value=w[8],
                              mid_rail=int(w[9]), right_value=w[11], opened=int(w[13]), back_closed=int(w[15]), left_closed=int(w[17]))
    return out


@pytest.mark.parametrize("options", [2, 4, 5, 12])
def test_choice_row_keys_by_option_count(tv, options):
    c = counts(tv)[options]
    assert c["rule"] == policy("choice-list", options)
    cycles = c["rule"][0]
    if cycles:   # 2 to 4 options: Left / Right cycle (clamped); Left on the first option leaves
        assert (c["first_rail"], c["first_value"]) == (1, "0")
        start = min(2, options - 1)                              # the probe's mid-list value
        assert (c["mid_value"], c["mid_rail"]) == (str(start - 1), 0)  # Left mid-list cycles down, stays
        assert c["right_value"] == "1"
    else:        # 5 or more: no cycling; Left goes to the rail from anywhere, Right does nothing
        assert (c["first_rail"], c["first_value"]) == (1, "0")
        assert (c["mid_value"], c["mid_rail"]) == ("2", 1)
        assert c["right_value"] == "0"
    assert c["opened"] == 1                                     # A opens the list either way
    assert c["back_closed"] == 1 and c["left_closed"] == 1      # Back or Left closes it, no change


def test_no_choices_row_traps_focus(tv, probes):
    """Every Choices row reaches the section rail: by Left from its first value, or, for the
    rows that keep today's keys (chips, stepped slider), by Up / Down to a row that does."""
    rows, _ = tv
    choices = {k for k, r in rows.items() if r["section"] == rows["enum-default"]["section"]}
    escapes = {k for k in choices if probes[k][3][0] == 1}
    assert escapes and all(k in escapes or probes[k][2][0] == 1 for k in choices)
    assert choices - escapes <= {"enum-radio", "enum-slider", "enum-many"}


def test_open_list_selects_into_the_draft_and_closes(tv):
    _, facts = tv
    assert facts["choice-a-opens"] == "1 index 0"     # A opens on the current option
    assert facts["choice-options"] == "3"             # Calm, Lively, Stormy
    assert facts["choice-selected"] == "0->1 list 0 committed 0"  # draft only, list closed
    assert facts["choice-back-closes"] == "1 1 list 0"  # Back closes the list, not the form
    assert facts["choice-left-closes"] == "0 rail 0"    # Left closes an open list
    assert facts["numbered-options"] == "4"             # ids beside None, Speed, Flying, Shield
    assert facts["long-options"] == "3 wrapped 3"       # every Placement option wraps


def test_mailbox_editor_and_path_validation(tv):
    _, facts = tv
    assert facts["mailbox-editor"] == "Trigger mailbox (0 – 159)"
    assert facts["path-refused"] == "1 Asset path: Enter a relative path: names separated by /"
    assert facts["path-accepted"] == "1"


def committed_catalogs():
    """Every committed RPRP catalog: standalone .rprp files and the chunks in level files."""
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.rprp", "wflevels/*.iff"],
                           capture_output=True, text=True, check=True).stdout.split()
    # Built catalogs that are on disk but not tracked (the planted tank's, among others).
    files += sorted(str(p.relative_to(ROOT)) for p in (ROOT / "wflevels").glob("*/*.rprp") if str(p.relative_to(ROOT)) not in files)
    found = []
    for name in files:
        data = (ROOT / name).read_bytes()
        if name.endswith(".rprp"):
            found.append((name, data))
        elif b"RPRP" in data and data[:2] == b"L4":
            body = payload(data)
            if body[:4] == b"RP01":
                found.append((name, body))
    return found


def test_path_validation_refuses_no_committed_catalog(harness, tmp_path):
    catalogs = committed_catalogs()
    assert any(name == "wflevels/baseline-standalone.iff" for name, _ in catalogs)
    for name, body in catalogs:
        path = tmp_path / (Path(name).name + ".rp01")
        path.write_bytes(body)
        result = subprocess.run([str(harness), "load", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, (name, result.stdout)
