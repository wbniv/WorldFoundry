"""Planted Tank screensaver level: plants only, its catalog, and the Director's grow/hold cycle.

Plan: docs/plans/2026-10-21-planted-tank-screensaver.md (Phase 1, verification steps 3 and 14).
The source checks read the tracked .lev and actor map; the catalog and bundle checks need
`bash wflevels/planted_tank_screensaver/build.sh` and skip without it. The cycle runs the
generated Director script in the standalone zForth host (docs/reference/swarming-poster),
compiled with `cc` like tests/test_urchin_motion.py, with mock engine words.
"""
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEVEL = ROOT / "wflevels/planted_tank_screensaver"
LEV = LEVEL / "planted_tank_screensaver.lev"
STANDALONE = ROOT / "wflevels/planted_tank_screensaver-standalone.iff"
BUNDLE = ROOT / "wflevels/planted-screensaver-cd.iff"
CYCLE = ROOT / "wflevels/aquarium_tanks/planted_cycle.fth"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load("screensaver_builder", ROOT / "scripts/build-aquarium-screensaver-levels.py")
zf = _load("planted_zfhost", ROOT / "docs/reference/swarming-poster/zfhost.py")


def level_text():
    return LEV.read_text()


def actor_map():
    return json.loads((LEVEL / "actor-map.json").read_text())


def director_script():
    return builder.script_of(level_text(), "Director")


# --- The level: plants only -------------------------------------------------------------

def test_builder_asserts_pass_on_the_level():
    asset = LEVEL / "asset.inc"
    builder.check_planted(level_text(), actor_map(), asset.read_text() if asset.is_file() else "")


def test_actor_map_has_no_animals():
    indices = actor_map()["indices"]
    assert not [n for n in indices if re.search(r"urchin|goby|seahorse|rainbow|rock", n, re.I)]
    assert indices["Director"] == 4 and indices["Player"] == 9
    assert [indices[f"plant_chunk_{k:02d}"] for k in range(8)] == list(range(18, 26))
    data = actor_map()
    assert data["animal"] is None and data["seahorses"] is None
    assert data["urchin_contacts"] is None and data["urchin_spines"] is None


def test_player_is_an_inert_invisible_hull():
    blocks = [b for b in level_text().split("\t{ 'OBJ'") if "{ 'NAME' \"Player\" }" in b]
    assert len(blocks) == 1
    assert '"Mesh Name" } { \'STR\' "player_hull.iff" }' in blocks[0]
    assert "\"Visibility Mailbox\" } { 'DATA' 0l }" in blocks[0]
    script = builder.script_of(level_text(), "Player")
    assert ": tk-player-tick 0 INDEXOF_INPUT tk! ;" in script
    assert script.rstrip().endswith("tk-player-tick")
    assert "gb-" not in script and "pg-salt if" not in script


def test_director_has_no_animal_words_and_stays_wide():
    script = director_script()
    for word in ("uf-foot", "us-spine", "sh-tick", "sh-settings", "swim-deform", "1160", "1161", "gb-"):
        assert word not in script, word
    tick = script[script.index(": tk-director-tick"):]
    assert "tk-cam-wide INDEXOF_CAMSHOT tk!" in tick and "tk-camera-tick" not in tick


def test_framing_and_fog():
    text = level_text()
    blocks = {name: next(b for b in text.split("\t{ 'OBJ'") if "{ 'NAME' \"" + name + "\" }" in b)
              for name in ("cs_wide", "Camera")}
    for name, block in blocks.items():
        assert re.search(r"\"Position\" \} \{ 'DATA' 0\.0+\(1\.15\.16\) -8\.25000+\(1\.15\.16\) 2\.50+\(1\.15\.16\)", block), name
    assert '"FoggingStartDistance" } { \'DATA\' 5.7599' in blocks["Camera"]
    assert '"FoggingCompleteDistance" } { \'DATA\' 28.8000' in blocks["Camera"]
    assert "-12.0000000000000000(1.15.16)" not in text


def test_wrapper_shrinks_perm_and_keeps_room():
    wrapper = (LEVEL / "planted_tank_screensaver-standalone.iff.txt").read_text()
    assert "'PERM' 1000000l" in wrapper and "'ROOM' 24000000l" in wrapper
    assert '"../planted_tank_screensaver.iff"' in wrapper
    assert not (LEVEL / "textile.flags").exists()


# --- END_OF_LEVEL is written with 1 only -------------------------------------------------

def test_end_of_level_is_only_ever_written_with_one():
    for text in (director_script(), CYCLE.read_text()):
        text = re.sub(r"\\ [^\n]*", "", text)  # drop Forth line comments
        writes = re.findall(r"(\S+)\s+(?:INDEXOF_END_OF_LEVEL|1905)\s+(?:tk!|write-mailbox)", text)
        assert writes == ["1"], writes
        assert len(re.findall(r"INDEXOF_END_OF_LEVEL|\b1905\b", text)) == 1


# --- The catalog -------------------------------------------------------------------------

def test_settings_sources_drop_seahorses_and_add_hold():
    bindings = json.loads((LEVEL / "settings-bindings.json").read_text())
    fields = bindings["fields"]
    assert bindings["owner"] == "Director"
    assert {k: v["id"] for k, v in fields.items()} == {
        "Seed": 1, "Water type": 2, "Growth speed": 3, "Initial age": 4, "Textures": 5,
        "Sway": 6, "Random seed on entry": 7, "Hold seconds": 10}
    assert not fields["Hold seconds"].get("readonly")
    oas = "\n".join(line for line in (LEVEL / "settings.oas").read_text().splitlines()
                    if not line.startswith("@*"))
    assert "TYPEHEADER(PlantedTankSettings)" in oas
    assert re.search(r"TYPEENTRYINT32\(Hold seconds,,0,86400,120,", oas)
    assert "Seahorses" not in oas and "Greeting" not in oas


def _catalog_fields(level: bytes):
    """Decode the RP01 catalog appended by build-object-properties.py."""
    start = level.index(b"RP01")
    data = memoryview(level)[start:]
    pos = 12

    def string():
        nonlocal pos
        n = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        value = bytes(data[pos:pos + n]).decode()
        pos += n
        return value

    schema, _title = string(), string()
    fields = {}
    count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    for _ in range(count):
        fid, kind, _show, readonly, _rule, low, high = struct.unpack_from("<IBBBBii", data, pos)
        pos += struct.calcsize("<IBBBBiiIII")
        key, _label, _help, _group, _choices, initial = (string() for _ in range(6))
        fields[key] = dict(id=fid, kind=kind, readonly=bool(readonly), min=low, max=high, initial=initial)
    return schema, fields


@pytest.mark.skipif(not STANDALONE.is_file(), reason="build wflevels/planted_tank_screensaver first")
def test_standalone_level_carries_the_catalog():
    level = STANDALONE.read_bytes()
    builder.check_catalog(level)
    schema, fields = _catalog_fields(level)
    assert schema == "PlantedTankSettings"
    stored = {k: v for k, v in fields.items() if v["id"] and v["id"] < 100}
    assert {k: v["id"] for k, v in stored.items()} == {
        "Seed": 1, "Water type": 2, "Growth speed": 3, "Initial age": 4, "Textures": 5,
        "Sway": 6, "Random seed on entry": 7, "Hold seconds": 10}
    hold = stored["Hold seconds"]
    assert (hold["kind"], hold["readonly"], hold["min"], hold["max"], hold["initial"]) == (0, False, 0, 86400, "120")


def _toc(bundle: bytes):
    size = struct.unpack_from("<I", bundle, 12)[0]
    return [bundle[16 + k:20 + k] for k in range(0, size, 12)]


@pytest.mark.skipif(not BUNDLE.is_file(), reason="build wflevels/planted_tank_screensaver first")
def test_bundle_holds_exactly_one_level():
    bundle = BUNDLE.read_bytes()
    assert _toc(bundle) == [b"SHEL", b"L4\0\0", b"UIFT"]
    assert bundle.count(b"PlantedTankSettings") == 1 and b"Hold seconds" in bundle


# --- The Director cycle in zForth --------------------------------------------------------

SPEEDS = [float(v.rstrip("f")) for v in re.search(
    r"speedValue\(int i\)\{constexpr float v\[\]=\{([^}]*)\}",
    (ROOT / "wfsource/source/game/plant_settings.h").read_text()).group(1).split(",")]


def test_cycle_constants_mirror_planted_tick():
    header = (ROOT / "wfsource/source/game/plant_settings.h").read_text()
    tick = re.search(r"inline void tick\(float dt.*", header).group()
    assert "dt=dt>.2f?0:std::max(0.f,dt)" in tick and "std::min(240.f," in tick
    assert SPEEDS == [0, .25, .5, 1, 2, 4, 8]
    script = director_script()
    for word, value in (("pt-stall", "0.2"), ("pt-max-age", "240"), ("pt-bound", "195"),
                        ("pt-hold-default", "120"), ("pt-hold-max", "86400"), ("pt-director", "4"),
                        ("pt-speed-field", "3"), ("pt-age-field", "4"), ("pt-hold-field", "10")):
        assert f": {word} {value} ;" in script, word


@pytest.fixture(scope="session")
def zf_binary(tmp_path_factory):
    folder = tmp_path_factory.mktemp("planted-forth")
    binary = folder / "zf_host"
    src = ROOT / "engine/vendor/zforth-41db72d1/src/zforth"
    # The engine's Scalar is float on every target, so the float host matches its mailboxes.
    subprocess.run(["cc", "-O1", f"-I{ROOT / 'engine/stubs'}", f"-I{src}",
                    str(ROOT / "docs/reference/swarming-poster/zf_host.c"), str(src / "zforth.c"),
                    "-lm", "-o", str(binary)], check=True)
    return binary


# Mock engine words. Catalog field f lives in mailbox 7000+f with its valid flag at 7050+f;
# Hold seconds' four bytes are 7100..7103 with the flag at 7104; plant-register counts in 7200.
FIELD, VALID, HOLD_BYTES, REGISTERED = 7000, 7050, 7100, 7200
MOCKS = (
    ": property@ swap drop dup 7000 + read-mailbox swap 7050 + read-mailbox ;\n"
    ": property-int-bytes@ drop drop 7100 read-mailbox 7101 read-mailbox 7102 read-mailbox 7103 read-mailbox 7104 read-mailbox ;\n"
    ": property-text-byte@ drop drop drop 0 0 ;\n"
    ": read-actor-mailbox drop drop 0 ; : write-actor-mailbox drop drop drop ;\n"
    ": plant-register drop drop 7200 read-mailbox 1 + 7200 write-mailbox ;\n"
    ": plant-step drop drop ;\n"
)


def _constants(script: str) -> str:
    mailbox = dict((n, int(v)) for n, v in re.findall(
        r"MAILBOXENTRY\(\s*(\w+)\s*,\s*(\d+)\s*\)", (ROOT / "wfsource/source/mailbox/mailbox.inc").read_text()))
    assert (mailbox["END_OF_LEVEL"], mailbox["TIME"], mailbox["DELTA_TIME"]) == (1905, 1906, 1907)
    words = sorted(set(re.findall(r"\b(INDEXOF_\w+|JOYSTICK_\w+)\b", script)))
    out = []
    for k, word in enumerate(words):
        name = word[len("INDEXOF_"):] if word.startswith("INDEXOF_") else None
        value = mailbox.get(name) if name else None
        out.append(f": {word} {value if value is not None else 7500 + k} ;")
    return "\n".join(out) + "\n"


class Tank:
    """One level load: the generated Director script on a fresh zForth host."""

    def __init__(self, binary, tmp_path, speed_index=3, hold=120, age=0.0, catalog=True):
        zf.BIN = binary
        self.h = zf.Host()
        script = director_script()
        body = script.rstrip()
        assert body.endswith("tk-director-tick")
        body = body[:-len("tk-director-tick")]
        path = tmp_path / "director.fth"
        path.write_text(MOCKS + _constants(script) + body + "\n")
        assert self.h.load(path) == "ok"
        self.time = 0.0
        if catalog:
            for field, value in ((3, speed_index), (4, age)):
                self.h.write(FIELD + field, value)
                self.h.write(VALID + field, 1)
            self.set_hold(hold)
        self.frames = 0

    def set_hold(self, hold):
        for k in range(4):
            self.h.write(HOLD_BYTES + k, (hold >> (8 * k)) & 255)
        self.h.write(HOLD_BYTES + 4, 1)

    def frame(self, dt):
        self.time += dt
        self.h.write(1907, dt)
        self.h.write(1906, self.time)
        assert self.h.eval("tk-director-tick") == "ok"
        self.frames += 1

    def ended(self):
        return self.h.read(1905) == 1

    def clock(self):
        return self.h.read(730)

    def run(self, dt=.05, limit=2000.0):
        while not self.ended():
            assert self.time < limit, "the tank never ended"
            self.frame(dt)
        return self.time

    def close(self):
        self.h.close()


@pytest.fixture
def tank(zf_binary, tmp_path):
    made = []

    def make(**kw):
        t = Tank(zf_binary, tmp_path, **kw)
        made.append(t)
        return t
    yield make
    for t in made:
        t.close()


def test_speed_8_hold_5_ends_after_grow_plus_hold(tank):
    t = tank(speed_index=6, hold=5)
    end = t.run()
    assert end == pytest.approx(195 / 8 + 5, abs=0.11)
    assert t.h.read(REGISTERED) == 8 and t.h.read(5000) == 0
    assert t.h.read(731) == 1 and t.h.read(732) == 5


def test_speed_1_hold_120_ends_after_about_315_seconds(tank):
    t = tank(speed_index=3, hold=120)
    assert t.run() == pytest.approx(315, abs=0.11)


def test_end_of_level_stays_zero_until_the_end(tank):
    t = tank(speed_index=6, hold=5)
    while t.time < 29.2:
        t.frame(.05)
        assert t.h.read(1905) == 0
    assert t.run() == pytest.approx(29.375, abs=0.11)


def test_stall_frame_does_not_advance_the_growth_clock(tank):
    t = tank(speed_index=3, hold=120)
    t.frame(.1)
    before = t.clock()
    assert before == pytest.approx(.1, abs=1e-6)
    t.frame(.5)
    assert t.clock() == before
    t.frame(.2)
    assert t.clock() == pytest.approx(before + .2, abs=1e-6)


@pytest.mark.parametrize("index", range(7))
def test_speed_index_maps_like_speed_value(tank, index):
    t = tank(speed_index=index)
    t.frame(.1)
    assert t.clock() == pytest.approx(.1 * SPEEDS[index], abs=1e-6)


def test_growth_clock_starts_at_initial_age(tank):
    t = tank(speed_index=3, hold=0, age=100.0)
    assert t.run() == pytest.approx(95, abs=0.11)


def test_hold_is_read_when_the_hold_starts(tank):
    t = tank(speed_index=6, hold=120)
    t.frame(.05)
    t.set_hold(3)  # a host write from frame 2 on
    assert t.run() == pytest.approx(195 / 8 + 3, abs=0.11)


def test_hold_above_32767_seconds_reads_through_int_bytes(tank):
    t = tank(speed_index=6, hold=86400)
    while t.h.read(731) == 0:
        assert t.time < 25
        t.frame(.05)
    assert t.h.read(732) == 86400
    for _ in range(100):
        t.frame(.05)
    assert not t.ended()


def test_missing_catalog_falls_back_to_1x_and_120_s(tank):
    t = tank(catalog=False)
    assert t.run(dt=.1) == pytest.approx(315, abs=0.21)
