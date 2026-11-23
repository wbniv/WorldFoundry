"""SeaStarsSettings: the type's nine fields and its registration (plan phase 0).

docs/plans/2026-11-20-sea-stars-settings.md. The director tests (edit-and-check per field,
parking) are added in the later phases; this file holds the type-shape checks.
"""
import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
OAS = ROOT / "wfsource/source/oas"
CATALOG = ROOT / "wftools/wf_attr_edit/target/release/catalog"

# label: (min, max, default). The phone's Dream form is built from these labels.
FIELDS = {
    "Chocolate-chip stars": (0, 4, 2),
    "Red Fromia": (0, 5, 3),
    "Sand-sifting stars": (0, 4, 2),
    "Brittle stars": (0, 2, 1),
    "Cushion stars": (0, 2, 1),
    "Speed": (0, 2, 1),
    "Glass climbing": (0, 1, 1),
    "Caustics": (0, 1, 1),
    "Seed": (0, 2147483647, 0),
}
# The level holds the maximum population; the director parks the extras (D10).
MAXIMUM_RESIDENTS = 4 + 5 + 4 + 2 + 2
DEFAULT_RESIDENTS = 2 + 3 + 2 + 1 + 1


def catalog():
    if not CATALOG.exists():
        pytest.skip("build the catalog tool first: cargo build --release --manifest-path "
                    "wftools/wf_attr_edit/Cargo.toml --bin catalog")
    out = subprocess.run([str(CATALOG), str(OAS / "seastarssettings.oad")],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_the_nine_fields_have_the_d9_ranges_and_defaults_and_are_live():
    fields = {f["key"]: f for f in catalog()["fields"]}
    for label, (low, high, default) in FIELDS.items():
        assert label in fields, label
        f = fields[label]
        assert (f["min"], f["max"], f["default"]) == (low, high, default), label
        assert f["live"], f"{label} must be SHOW_AS_LIVE or a runtime edit has no effect"


GLOBAL_FIELDS = {"Show framerate"}   # oas/global_settings.inc: every settings type carries these


def test_only_the_nine_settings_fields_and_the_global_ones_are_live():
    live = {f["key"] for f in catalog()["fields"] if f["live"]}
    assert live == set(FIELDS) | GLOBAL_FIELDS


def test_default_and_maximum_population_match_the_plan():
    defaults = sum(FIELDS[k][2] for k in list(FIELDS)[:5])
    maximum = sum(FIELDS[k][1] for k in list(FIELDS)[:5])
    assert (defaults, maximum) == (DEFAULT_RESIDENTS, MAXIMUM_RESIDENTS) == (9, 17)


def test_the_type_is_registered_once_and_after_every_existing_type():
    """objects.mac says new types are appended, never inserted: the position is the type id
    compiled into every level. Every registry file must agree on that position."""
    mac = [m for m in re.findall(r"^\s*OBJECTENTRY\((\w+),", (OAS / "objects.mac").read_text(), re.M)]
    assert mac.count("SeaStarsSettings") == 1
    position = mac.index("SeaStarsSettings")
    assert mac[position - 1] == "LevelRenderSettings"
    kinds = re.findall(r"^\s*(\w+)_KIND,", (OAS / "objects.h").read_text(), re.M)
    assert kinds.index("SeaStarsSettings") == position + (len(kinds) - len(mac))
    names = re.findall(r'^\s*"(\w+)",', (OAS / "objects.names").read_text(), re.M)
    assert names.index("SeaStarsSettings") == names.index("LevelRenderSettings") + 1
    assert (OAS / "objects.lc").read_text().split().index("seastarssettings") == \
        (OAS / "objects.lc").read_text().split().index("levelrendersettings") + 1
    assert '#include "seastarssettings.hp"' in (OAS / "objects.inc").read_text()
    assert "OadSeaStarsSettings" in (OAS / "objects.c").read_text()


# --- phase 1-2: the generator and the director script ----------------------------------------
import sys
sys.path.insert(0, str(ROOT / "wflevels/aquarium_sea_stars"))
import config as cfg  # noqa: E402
import controller  # noqa: E402


def _director_text():
    names = ["Room", "SunLight", "Camera", "Director", "LevelObj", "Matte", "cs_wide", "LookAt", "Player",
             "BlueStar", "SeaStarsSettings"] + [n for n, _, _ in cfg.RESIDENTS]
    indices = {n: i + 1 for i, n in enumerate(names)}
    fields = {label: 129 + i for i, label in enumerate(controller.FIELD_LABELS.values())}
    full = controller.director(indices, fields)
    split = full.index(': st-director-tick')
    return (full[:split], full[split:]), indices


def test_the_level_holds_the_maximum_population_and_the_defaults_are_the_shipped_nine():
    from collections import Counter
    assert len(cfg.RESIDENTS) == MAXIMUM_RESIDENTS == 17
    assert Counter(k for _, k, _ in cfg.RESIDENTS) == Counter(cfg.MAX_COUNTS)
    seen, selected = Counter(), []
    for name, kind, _ in cfg.RESIDENTS:
        if seen[kind] < cfg.DEFAULT_COUNTS[kind]:
            selected.append(name)
        seen[kind] += 1
    assert selected == ["ChipOne", "ChipTwo", "FromiaOne", "FromiaTwo", "FromiaThree", "SandOne", "SandTwo",
                        "Brittle", "Cushion"] == [n for n, _, _ in cfg.RESIDENTS][:9]
    assert len({n for n, _, _ in cfg.RESIDENTS}) == 17


def test_every_director_cell_is_unique_and_clear_of_the_other_ranges():
    cells = {}
    for table in (*controller.SERIAL_TABLES, *controller.KIND_TABLES):
        for serial in range(len(cfg.RESIDENTS)):
            owners = cells.setdefault(controller.rcell(table, serial), [])
            if (table, controller.kind_index(serial)) not in owners:   # kind tables repeat per kind
                owners.append((table, serial if table in controller.SERIAL_TABLES else controller.kind_index(serial)))
    for name, cell in controller.SC.items():
        cells.setdefault(cell, []).append((name, None))
    assert all(len(owners) == 1 for owners in cells.values()), {c: o for c, o in cells.items() if len(o) > 1}
    low, high = min(cells), max(cells)
    # Clear of the controller cells (600-625) and the DFRM blocks, and level-global: above
    # GLOBAL_USER_MAX a mailbox is local to one actor, so the scripts could not share it.
    assert low >= controller.dfrm_block(controller.ACTORS) and high <= controller.GLOBAL_USER_MAX, (low, high)
    assert max(controller.CELLS.values()) < controller.DFRM_BASE
    assert controller.dfrm_block(controller.ACTORS) - 1 <= controller.GLOBAL_USER_MAX


def test_the_cpp_entry_seed_mailbox_matches_the_forth_cell():
    header = (ROOT / "wfsource/source/game/seastarssettings.hp").read_text()
    value = int(re.search(r"kSeaStarsEntrySeedMailbox\s*=\s*(\d+)", header).group(1))
    assert value == controller.SC["entry"]


def test_the_director_reads_all_nine_fields_and_polls_once_a_second():
    (text, tick), _ = _director_text()
    assert text.count("property@") >= 1 and "property-int-bytes@" in text
    for key in controller.FIELD_LABELS:
        assert f": st-f-{key} " in text, key
    for kind in cfg.KIND_ORDER:
        assert f"st-f-{kind} {cfg.DEFAULT_COUNTS[kind]} st-setting {controller.COUNT_CELL[kind]} st!" in text
    assert f"{controller.SC['poll']} st@ st-dt -" in tick and "1 " + str(controller.SC["poll"]) + " st!" in tick


def test_a_parked_resident_is_skipped_but_still_scaled_to_nothing():
    (text, tick), indices = _director_text()
    for serial, (name, kind, _) in enumerate(cfg.RESIDENTS):
        act = controller.rcell("active", serial)
        assert f" {act} st@ if\n" in tick, name              # behaviour and deform only while active
        assert f"{act} st@ if " in tick and ".001 then" in tick
        want = f"{controller.kind_index(serial)} {controller.COUNT_CELL[kind]} st@ <"
        assert want in tick, name
    # dfrm-pose-curves for a resident appears only after its active guard.
    first_pose = tick.index(f"dfrm-pose-curves", tick.index(": st-director-tick"))
    assert first_pose > 0 and tick.count("dfrm-pose-curves") == 1 + sum(1 for _, k, _ in cfg.RESIDENTS if k != "cushion")


def test_glass_and_speed_cells_default_to_the_shipped_behaviour():
    header = controller.header()
    assert f"read-mailbox dup 0 = if drop 1 then" in header     # speed factor 0 (unset) is x1
    assert f"{controller.SC['glass']} read-mailbox 1 <> ;" in header   # glass cell 1 = Off, 0 or 2 = On


# --- phase 3: edit a field, step the director, assert the effect (the zForth VM) --------------
from test_aquarium_sea_stars import crawl  # noqa: E402,F401  (the module's VM fixture)

ACTORS_FIRST_RESIDENT = 5
SETTINGS_ACTOR = 5 + len(cfg.RESIDENTS)
FIELD_INDEX = {key: i for i, key in enumerate(controller.FIELD_LABELS)}      # the VM's small indices
FRAME = ".0166667"


def prop(key, value):
    return f"prop {SETTINGS_ACTOR} {FIELD_INDEX[key]} {value}\n"


def dumpg(raw, lo, hi):
    for line in raw.splitlines():
        if line.startswith("G "):
            parts = line.split()
            if int(parts[1]) == lo:
                return {lo + i: float(v) for i, v in enumerate(parts[2:2 + hi - lo + 1])}
    raise AssertionError("no dumpg " + str(lo))


def active_after(crawl, edits="", frames=150):
    """Run the director with the given property edits; return {name: active flag}."""
    lo = controller.rcell("active", 0)
    raw = crawl.raw(f"reset 0 0 .8\n{edits}step {frames} 0 {FRAME}\ndumpg {lo} {lo + len(cfg.RESIDENTS) - 1}\n")
    cells = dumpg(raw, lo, lo + len(cfg.RESIDENTS) - 1)
    return {name: int(cells[controller.rcell("active", s)]) for s, (name, _, _) in enumerate(cfg.RESIDENTS)}


def wanted(counts):
    seen = {k: 0 for k in counts}
    out = {}
    for name, kind, _ in cfg.RESIDENTS:
        out[name] = int(seen[kind] < counts[kind])
        seen[kind] += 1
    return out


def test_with_no_properties_the_default_population_is_active(crawl):
    assert active_after(crawl) == wanted(cfg.DEFAULT_COUNTS)
    assert sum(active_after(crawl).values()) == 9


@pytest.mark.parametrize("kind", cfg.KIND_ORDER)
def test_each_count_parks_and_unparks_to_match(crawl, kind):
    for value in range(cfg.MAX_COUNTS[kind] + 1):
        counts = dict(cfg.DEFAULT_COUNTS, **{kind: value})
        assert active_after(crawl, prop(kind, value)) == wanted(counts), (kind, value)


def test_every_count_from_all_zero_to_the_maximum_and_back(crawl):
    zero = {k: 0 for k in cfg.KIND_ORDER}
    edits_zero = "".join(prop(k, 0) for k in cfg.KIND_ORDER)
    edits_max = "".join(prop(k, cfg.MAX_COUNTS[k]) for k in cfg.KIND_ORDER)
    assert active_after(crawl, edits_zero) == wanted(zero) and sum(active_after(crawl, edits_zero).values()) == 0
    assert active_after(crawl, edits_max) == wanted(cfg.MAX_COUNTS) and sum(active_after(crawl, edits_max).values()) == 17
    # Raise then lower in one run: the poll sees the latest edit each second.
    lo = controller.rcell("active", 0)
    raw = crawl.raw(f"reset 0 0 .8\n{edits_max}step 120 0 {FRAME}\n{edits_zero}step 120 0 {FRAME}\n"
                    f"dumpg {lo} {lo + 16}\n")
    assert all(v == 0 for v in dumpg(raw, lo, lo + 16).values())


def test_a_raised_count_fades_in_over_two_seconds_and_a_parked_one_is_nothing(crawl):
    # Level start: defaults appear at once. Raising a count later fades the new resident in.
    chip3 = [n for n, _, _ in cfg.RESIDENTS].index("ChipThree")
    fade, act = controller.rcell("fade", chip3), controller.rcell("active", chip3)
    lo = min(fade, act)
    raw = crawl.raw(f"reset 0 0 .8\nstep 150 0 {FRAME}\n{prop('chip', 3)}step 70 0 {FRAME}\ndumpg {lo} {max(fade, act)}\n"
                    f"step 90 0 {FRAME}\ndumpg {lo} {max(fade, act)}\ndumpsc {ACTORS_FIRST_RESIDENT + chip3} {ACTORS_FIRST_RESIDENT + chip3}\n")
    glines = [l for l in raw.splitlines() if l.startswith("G ")]
    halfway = {lo + i: float(v) for i, v in enumerate(glines[0].split()[2:])}
    done = {lo + i: float(v) for i, v in enumerate(glines[1].split()[2:])}
    assert halfway[act] == 1 and 0 < halfway[fade] < 1            # fading in
    assert done[fade] == 1                                         # fully in after 2 s
    scale = [l for l in raw.splitlines() if l.startswith("S ")][0].split()
    assert [float(v) for v in scale[2:5]] == [1.0, 1.0, 1.0]
    # An unwanted resident is written at scale .001 and never posed.
    chip4 = [n for n, _, _ in cfg.RESIDENTS].index("ChipFour")
    raw = crawl.raw(f"reset 0 0 .8\nstep 150 0 {FRAME}\ndumpsc {ACTORS_FIRST_RESIDENT + chip4} {ACTORS_FIRST_RESIDENT + chip4}\n"
                    f"dumpg {controller.dfrm_block(chip4 + 1) + 40} {controller.dfrm_block(chip4 + 1) + 43}\n")
    scale = [l for l in raw.splitlines() if l.startswith("S ")][0].split()
    assert [float(v) for v in scale[2:5]] == pytest.approx([.001, .001, .001])
    block = dumpg(raw, controller.dfrm_block(chip4 + 1) + 40, controller.dfrm_block(chip4 + 1) + 43)
    assert all(v == 0 for v in block.values()), "a parked resident's deform block must never be written"


def test_speed_scales_the_resident_clock_and_the_player(crawl):
    rclock, speedf = controller.SC["rclock"], controller.SC["speedf"]
    out = {}
    for value, expected in ((0, .5), (1, 1.0), (2, 2.0)):
        raw = crawl.raw(f"reset 0 0 .8\n{prop('speed', value)}step 180 0 {FRAME}\ndumpg {speedf} {speedf}\ndumpg {rclock} {rclock}\n")
        assert dumpg(raw, speedf, speedf)[speedf] == expected
        out[value] = dumpg(raw, rclock, rclock)[rclock]
    # Three seconds of frames: the resident clock runs at x.5, x1, x2.
    assert out[0] == pytest.approx(out[1] * .5, rel=.05) and out[2] == pytest.approx(out[1] * 2, rel=.05)
    moved = {}
    for value in (0, 1, 2):
        rows = crawl(f"reset -3 0 .8\n{prop('speed', value)}step 90 8192 {FRAME}\n")
        moved[value] = rows[-1]["x"] - rows[0]["x"]
    assert moved[0] == pytest.approx(moved[1] * .5, rel=.1) and moved[2] == pytest.approx(moved[1] * 2, rel=.1)


def test_glass_climbing_off_stops_the_climb_and_brings_a_climber_down(crawl):
    on = crawl(f"reset 0 -2.4 .8\n{prop('glass', 1)}step 60 4096 {FRAME}\n")
    off = crawl(f"reset 0 -2.4 .8\n{prop('glass', 0)}step 60 4096 {FRAME}\n")
    assert {int(r[controller.CELLS['surface']]) for r in on} >= {0, 1}, "with Glass climbing On, pushing into the glass climbs it"
    assert {int(r[controller.CELLS['surface']]) for r in off} == {0}, "with Glass climbing Off the star stays on the sand"
    assert abs(off[-1]["y"] + 2.65) < .01                       # held at the glass, not through it
    # A star already on the glass climbs down once Glass climbing turns Off.
    lo = controller.CELLS['surface']
    rows = crawl(f"reset 0 -2.4 .8\n{prop('glass', 1)}step 60 4096 {FRAME}\nstep 60 2048 {FRAME}\n"
                 f"{prop('glass', 0)}step 400 0 {FRAME}\n")
    assert int(rows[119][controller.CELLS['surface']]) == 1                # climbing before the edit
    assert int(rows[-1][controller.CELLS['surface']]) == 0 and abs(rows[-1]["z"] - .8) < .001


def test_seed_sets_resident_spots_and_zero_uses_the_entry_seed(crawl):
    chip, sand = 0, [n for n, _, _ in cfg.RESIDENTS].index("SandOne")
    ox, tx = controller.rcell("ox", chip), controller.rcell("tx", chip)
    seedcell, entry = controller.SC["seed"], controller.SC["entry"]

    def offsets(edits):
        raw = crawl.raw(f"reset 0 0 .8\n{edits}step 150 0 {FRAME}\ndumpg {ox} {ox}\ndumpg {tx} {tx}\ndumpg {seedcell} {seedcell}\n")
        return dumpg(raw, ox, ox)[ox], dumpg(raw, tx, tx)[tx], dumpg(raw, seedcell, seedcell)[seedcell]
    set_entry = lambda v: f"set {entry} {v}\n"
    a = offsets(prop("seed", 4242) + set_entry(11))
    b = offsets(prop("seed", 4242) + set_entry(22222))
    assert a == b, "a non-zero Seed ignores the entry seed: the same spots every entry"
    c = offsets(prop("seed", 4243) + set_entry(11))
    assert c[1] != a[1], "a different Seed gives different spots"
    z1, z2 = offsets(set_entry(11)), offsets(set_entry(22222))
    assert z1[2] == 11 and z2[2] == 22222 and z1[1] != z2[1], "Seed 0 uses this entry's random seed"
    for off in (a, c, z1, z2):
        assert abs(off[0]) <= cfg.SEED_SPREAD["chip"][0] + 1e-3
        assert off[0] == pytest.approx(off[1], abs=1e-3), "offsets reach their target (instantly at level start)"


def test_a_seed_edit_makes_residents_glide_not_jump(crawl):
    ox, tx = controller.rcell("ox", 0), controller.rcell("tx", 0)
    raw = crawl.raw(f"reset 0 0 .8\n{prop('seed', 4242)}step 150 0 {FRAME}\ndumpg {tx} {tx}\n"
                    f"{prop('seed', 777)}step 70 0 {FRAME}\ndumpg {ox} {ox}\ndumpg {tx} {tx}\nstep 200 0 {FRAME}\ndumpg {ox} {ox}\n")
    before = [float(l.split()[2]) for l in raw.splitlines() if l.startswith("G ") and int(l.split()[1]) == tx]
    mid_ox = [float(l.split()[2]) for l in raw.splitlines() if l.startswith("G ") and int(l.split()[1]) == ox]
    assert before[0] != before[1], "the new Seed changed the target"
    assert abs(mid_ox[0] - before[1]) > 1e-3 and abs(mid_ox[0] - before[0]) > 1e-3, "mid-glide: neither at the old nor the new spot"
    assert mid_ox[1] == pytest.approx(before[1], abs=1e-3), "settled on the new spot"


def test_the_valid_cell_says_whether_the_overlay_answered(crawl):
    valid = controller.SC["valid"]
    none = dumpg(crawl.raw(f"reset 0 0 .8\nstep 5 0 {FRAME}\ndumpg {valid} {valid}\n"), valid, valid)[valid]
    some = dumpg(crawl.raw(f"reset 0 0 .8\n{prop('seed', 9)}step 5 0 {FRAME}\ndumpg {valid} {valid}\n"), valid, valid)[valid]
    assert (none, some) == (0, 1)


# --- phase 4: the Dream variant keeps the settings object ----------------------------------------
def test_the_dream_variant_keeps_the_settings_object_and_has_no_rprp_chunk():
    variant = ROOT / "wflevels/aquarium_sea_stars_screensaver/aquarium_sea_stars_screensaver.lev"
    standalone = ROOT / "wflevels/aquarium_sea_stars_screensaver-standalone.iff"
    if not variant.exists() or not standalone.exists():
        pytest.skip("build it first: python3 scripts/build-aquarium-screensaver-levels.py aquarium_sea_stars")
    text = variant.read_text()
    assert "SeaStarsSettings" in text
    # Only the Player's copy of the controller runs the autopilot; the director's copy stays 0.
    assert text.count(": st-dream 1 ;") == 1 and text.count(": st-dream 0 ;") == 1
    for iff in (ROOT / "wflevels/aquarium_sea_stars-standalone.iff", standalone):
        assert b"RPRP" not in iff.read_bytes(), iff.name


# --- phase 5: the phone's Dream form (generic, OAD-driven; no Planted bridge) ---------------------
import shutil  # noqa: E402
import tempfile  # noqa: E402

SCREENSAVER = ROOT / "android/screensaver/src"
JAVA = SCREENSAVER / "main/java/org/worldfoundry/screensaver"
ASSET = SCREENSAVER / "aquarium/assets/sea-stars-settings.json"


def test_the_capabilities_asset_is_what_the_generator_makes_from_the_oad():
    if not CATALOG.exists():
        pytest.skip("build the catalog tool first")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "caps.json"
        subprocess.run([sys.executable, str(ROOT / "scripts/gen-settings-capabilities.py"),
                        "--oad", str(OAS / "seastarssettings.oad"), "--inherited-oad", str(OAS / "actor.oad"),
                        "--actor-map", str(ROOT / "wflevels/aquarium_sea_stars/actor-map.json"),
                        "--actor-name", "SeaStarsSettings", "--type", "SeaStarsSettings",
                        "--title", "Sea Stars", "--out", str(out)], check=True, capture_output=True)
        assert out.read_text() == ASSET.read_text(), \
            "sea-stars-settings.json is stale: regenerate it with scripts/gen-settings-capabilities.py"


def test_the_asset_offers_exactly_the_nine_fields_with_the_d9_ranges():
    doc = json.loads(ASSET.read_text())
    owner = doc["objects"][0]
    assert owner["type"] == "SeaStarsSettings"
    settings = {s["key"]: s for s in owner["settings"]}
    assert list(settings) == list(FIELDS) + sorted(GLOBAL_FIELDS)   # the nine, then the global sheet
    for label, (low, high, default) in FIELDS.items():
        s = settings[label]
        assert not s["readonly"], label
        if s["type"] == "boolean":
            # An on/off setting is a real checkbox (Will, 2026-11-22), "true"/"false" on the wire.
            assert (low, high) == (0, 1) and s["show"] == 8 and s["value"] == ("true" if default else "false"), label
            continue
        assert int(s["value"]) == default, label
        if s["type"] == "choice":
            assert [o["id"] for o in s["options"]] == [str(i) for i in range(low, high + 1)], label
        else:
            assert (label, s["type"], int(s["minimum"]), int(s["maximum"])) == ("Seed", "integer", low, high)


def test_the_on_off_fields_are_real_checkboxes_not_off_on_choices():
    """Glass climbing and Caustics were "Off|On" radio buttons, drawn as Off/On segments while Show framerate was a
    checkbox. Every on/off setting is now a checkbox: a boolean in the catalog and in the phone asset."""
    kinds = {f["key"]: f for f in catalog()["fields"]}
    for key in ("Glass climbing", "Caustics", "Show framerate"):
        assert kinds[key]["kind"] == "Bool" and kinds[key]["show"] == 8, key
    types = {s["key"]: s["type"] for s in json.loads(ASSET.read_text())["objects"][0]["settings"]}
    assert types["Glass climbing"] == types["Caustics"] == types["Show framerate"] == "boolean"
    assert 'Off|On' not in (OAS / "seastarssettings.oas").read_text()


def test_the_java_cpp_and_provider_agree_on_names_and_routes():
    player = (JAVA / "TankPlayer.java").read_text()
    host = (SCREENSAVER / "main/cpp/dream_host.cc").read_text()
    # The JNI name matches the Java declaration, and it sets the engine's own launch overrides.
    assert "native void nativeLaunchOverride(String schema, String key, String value)" in player
    assert "Java_org_worldfoundry_screensaver_TankPlayer_nativeLaunchOverride" in host
    assert "launchOverrideSink.set(" in host
    # The tank that carries the settings is in the manifest, by the same id the level uses. (It was the
    # last entry until the Discus tank was appended on 2026-11-22; LevelLaunch matches the id, not a position.)
    manifest = (ROOT / "wflevels/aquarium-menu.manifest").read_text()
    tanks = re.findall(r"(?m)^level\s+(\S+)-standalone\.iff\s*\|", manifest)
    assert "aquarium_sea_stars" in tanks
    settings = (JAVA / "LevelSettings.java").read_text()
    assert 'SEA_STARS_TANK = "aquarium_sea_stars"' in settings and 'SEA_STARS_PREFIX = "sea-stars."' in settings
    # Every place that starts a tank goes through LevelLaunch, so the overrides always reach the engine.
    # AquariumActivity is now LauncherActivity (ac98d049): one launcher shell for both packs.
    for name in ("AquariumDreamService", "LauncherActivity", "ScreensaverPreviewActivity"):
        text = (JAVA / f"{name}.java").read_text()
        assert "LevelLaunch.startChosen(this, player, " in text, name
        assert "player.start(TankChoice" not in text, name
    assert "LevelSettings.SEA_STARS_PREFIX" in (JAVA / "TankSettingsProvider.java").read_text()
    # It is not the Planted bridge: nothing of the Sea Stars path touches it.
    for name in ("LevelSettings", "LevelSettingField", "LevelLaunch"):
        assert "Planted" not in (JAVA / f"{name}.java").read_text(), name


def test_the_plain_java_validation_test_passes():
    java = next((p for p in ("/usr/lib/jvm/java-21-openjdk-amd64/bin/java", "/usr/lib/jvm/java-17-openjdk-amd64/bin/java",
                             shutil.which("java") or "") if p and Path(p).exists()), None)
    if not java:
        pytest.skip("no java here; run it where a JDK or a JRE with jdk.compiler exists")
    modules = subprocess.run([java, "--list-modules"], capture_output=True, text=True).stdout
    if "jdk.compiler" not in modules:
        pytest.skip("this java has no compiler module")
    with tempfile.TemporaryDirectory() as tmp:
        sources = [JAVA / "LevelSettingField.java",
                   SCREENSAVER / "test/java/org/worldfoundry/screensaver/LevelSettingFieldTest.java"]
        subprocess.run([java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "-d", tmp, *map(str, sources)],
                       check=True, capture_output=True)
        run = subprocess.run([java, "-cp", tmp, "org.worldfoundry.screensaver.LevelSettingFieldTest"],
                             capture_output=True, text=True)
        assert run.returncode == 0 and " 0 failures" in run.stdout, run.stdout


def test_parked_residents_are_not_drawn():
    """The renderer draws an actor only if its visibility mailbox is nonzero (level.cc), and the
    director writes 1/0 to a resident's active cell when it unparks/parks it. So each resident's
    visibility mailbox must be its own active cell: a parked resident then costs no draw call.
    On cast1 the 8 parked residents cost 5.8 ms a frame (18.5 FPS against 20.7) before this."""
    import re
    lev = (ROOT / 'wflevels/aquarium_sea_stars/aquarium_sea_stars.lev').read_text()
    visibility = {}
    for block in lev.split("\t{ 'OBJ' ")[1:]:
        name = re.search(r"\{ 'NAME' \"([^\"]+)\" \}", block).group(1)
        vis = re.search(r"\"Visibility Mailbox\" \} \{ 'DATA' (-?\d+)l", block)
        if vis:
            visibility[name] = int(vis.group(1))
    assert visibility['BlueStar'] == 1                      # the player's star is always drawn
    cells = []
    for serial, (name, kind, pos) in enumerate(cfg.RESIDENTS):
        cell = controller.rcell('active', serial)
        assert visibility[name] == cell, f'{name}: visibility {visibility[name]}, active cell {cell}'
        assert 1 < cell < controller.GLOBAL_USER_MAX, f'{name}: active cell {cell} is not a global user mailbox'
        cells.append(cell)
    assert len(set(cells)) == len(cells)


def test_residents_re_pose_one_frame_in_three_and_the_player_every_frame():
    """The deform runs inside dfrm-pose-curves, about 1.2 ms a resident on cast1, and the arms move
    slowly: each resident re-poses on its own phase (order among the posed, mod 3) of a 0, 1, 2 frame counter, so
    the load is level. The player's star poses every frame: it answers the stick."""
    import re
    (_, tick), indices = _director_text()
    gated = re.findall(r"fphase_cell st@ (\d) = if\n", tick.replace(str(controller.SC['fphase']), 'fphase_cell'))
    posed = [(serial, kind) for serial, (name, kind, _) in enumerate(cfg.RESIDENTS) if kind != 'cushion']
    assert len(gated) == len(posed), (len(gated), len(posed))              # one gate per posed resident
    assert [int(g) for g in gated] == [slot % 3 for slot in range(len(posed))]   # by order among the posed
    counts = [gated.count(str(p)) for p in '012']
    assert max(counts) - min(counts) <= 1, counts                           # the phases are level
    assert tick.count('dfrm-pose-curves') == len(posed) + 1                 # the player's star is the extra
    # The counter itself cycles 0, 1, 2 once per director frame.
    assert f"{controller.SC['fphase']} st@ 1 + dup 3 >= if drop 0 then {controller.SC['fphase']} st!" in tick
