"""Regression guard for the one-app-per-game Android split: smb, snowgoons and qbert (beside aquarium and condo).

Plan: docs/plans/2026-10-01-split-cd-iff-one-app-per-game.md (the pattern is tests/test_condo_android.py).
Static only (no device, no display):

  * each game's committed cd.iff (task build-cd-iff-<game>) is shell.fth + today's standalone levels, in TOC order, byte for byte.
  * the audit: the only writes to LEVEL_TO_RUN (mailbox 5000) are SMB's flag/axe ActBoxes (1, 2, 3, 0), every target is a
    level inside the same bundle, and snowgoons and Q*bert write none, so no bundle can jump to a missing or foreign level.
  * the desktop's multi-level wfsource/source/game/cd.iff is still exactly what task build-cd-iff packs.

    python3 -m pytest tests/test_game_apps_android.py -v
"""

from __future__ import annotations

import re
import struct

import pytest
import yaml

from test_aquarium_android import REPO, SECTOR, SHELL, read_game_toc

LEVELS = REPO / "wflevels"
# game -> (bundle, standalone levels in TOC order)
GAMES = {
    "smb": ("smb-cd.iff", ["smb_w1_1", "smb_w1_2", "smb_w1_3", "smb_w1_4"]),
    "snowgoons": ("snowgoons-cd.iff", ["snowgoons"]),
    "qbert": ("qbert-cd.iff", ["qbert_practice"]),
}
LEVEL_TO_RUN = 5000                     # wfsource/source/mailbox/mailbox.inc: MAILBOXENTRY( LEVEL_TO_RUN, 5000 )
# The audit (plan § The audit): level -> the LEVEL_TO_RUN values its ActBoxes write.
WRITES = {"smb_w1_1": [1], "smb_w1_2": [2], "smb_w1_3": [3], "smb_w1_4": [0], "snowgoons": [], "qbert_practice": []}


def standalone(level):
    return LEVELS / f"{level}-standalone.iff"


@pytest.mark.parametrize("game", GAMES)
def test_bundle_is_shell_plus_the_current_levels(game):
    name, levels = GAMES[game]
    data = (LEVELS / name).read_bytes()
    toc = read_game_toc(data)
    bodies = [standalone(lv).read_bytes() for lv in levels]
    assert [t[0] for t in toc] == [b"SHEL"] + [b[:4] for b in bodies], toc
    _, shel_off, shel_len = toc[0]
    assert (shel_off, shel_len) == (SECTOR, len(SHELL.read_bytes()))
    assert data[shel_off + 8:shel_off + 8 + shel_len] == SHELL.read_bytes()
    off = 2 * SECTOR
    for (_, lv_off, lv_len), body, lv in zip(toc[1:], bodies, levels):
        assert (lv_off, lv_len) == (off, len(body)), lv
        assert data[lv_off:lv_off + lv_len] == body, f"wflevels/{name} is stale against {lv}: task build-cd-iff-{game}"
        off += -(-lv_len // SECTOR) * SECTOR
    assert len(data) == off


def test_bundle_tasks():
    tasks = yaml.safe_load((REPO / "Taskfile.yml").read_text())["tasks"]
    for game, (name, levels) in GAMES.items():
        cmds = str(tasks[f"build-cd-iff-{game}"]["cmds"])
        packed = re.findall(r"wflevels/(\S+)-standalone\.iff", cmds)
        assert packed == levels, (game, packed)
        assert f'default "wflevels/{name}"' in str(tasks[f"build-cd-iff-{game}"]["vars"])


# ---- the audit: who writes the level index ------------------------------------------------------------------

def _level_to_run_writes(body: bytes) -> list[int]:
    """Values written to LEVEL_TO_RUN by ActBoxes in a shipped level: an aligned int32 5000 (wf_MailBox) followed by the value
    (wf_MailBoxValue), as wflevels/smb_common.py lays the flag ActBox out."""
    return [struct.unpack_from("<i", body, m.start() + 4)[0]
            for m in re.finditer(re.escape(struct.pack("<i", LEVEL_TO_RUN)), body) if m.start() % 4 == 0]


@pytest.mark.parametrize("level", WRITES)
def test_audit_level_to_run_writes(level):
    body = standalone(level).read_bytes()
    assert _level_to_run_writes(body) == WRITES[level], level
    # No script names the mailbox (the one "5000" in the SMB player script is the flag-height score bonus).
    assert b"LEVEL_TO_RUN" not in body
    assert not re.search(rb"5000\s+write-mailbox|write-mailbox\s+5000", body)
    assert not re.search(rb"\b60\d\d\s+write-mailbox", body), "a level writing a persistent user mailbox (6000 is the shell's)"


def test_audit_lev_sources_agree():
    """The .lev sources say the same as the binaries: one ActBox with MailBox 5000 per SMB level."""
    for level, values in WRITES.items():
        if not level.startswith("smb_"):
            continue
        lev = (LEVELS / level / f"{level}.lev").read_text(errors="replace")
        found = [int(v) for v in re.findall(
            r"'NAME' \"MailBox\" \} \{ 'DATA' 5000l \}.*?'NAME' \"MailBoxValue\" \} \{ 'DATA' (-?\d+)l", lev, re.S)]
        assert found == values, (level, found)


@pytest.mark.parametrize("game", GAMES)
def test_audit_every_target_is_inside_its_bundle(game):
    _, levels = GAMES[game]
    for level in levels:
        for target in WRITES[level]:
            assert 0 <= target < len(levels), f"{level} jumps to TOC {target}, outside the {game} bundle"
    # shell.fth boots TOC 0 on the first pass and never again; each bundle's level 0 is the game's first level.
    assert re.search(r"\b0 INDEXOF_LEVEL_TO_RUN write-mailbox\b", SHELL.read_text())


def test_desktop_cd_iff_unchanged():
    """The desktop bundle is out of scope: still shell.fth + the seven levels in the original order."""
    data = (REPO / "wfsource" / "source" / "game" / "cd.iff").read_bytes()
    toc = read_game_toc(data)
    order = ["smb_w1_1", "smb_w1_2", "smb_w1_3", "smb_w1_4", "snowgoons", "qbert_practice", "marble-madness-3d-astra"]
    assert len(toc) == 1 + len(order)
    for (_, off, size), level in zip(toc[1:], order):
        assert data[off:off + size] == standalone(level).read_bytes(), level
    cmds = str(yaml.safe_load((REPO / "Taskfile.yml").read_text())["tasks"]["build-cd-iff"]["cmds"])
    assert re.findall(r"wflevels/(\S+)-standalone\.iff", cmds) == order


# ---- the apps ----------------------------------------------------------------------------------------------------

from test_aquarium_android import APP, DENSITIES, GRADLE, SRC  # noqa: E402

# flavor -> (applicationId suffix or None for the original id, label, the assets it ships)
FLAVORS = {
    "snowgoons": (None, "World Foundry", ["cd.iff", "florestan-subset.sf2", "level0.mid"]),
    "smb": (".smb", "WF SMB", ["cd.iff"]),                 # the label is a placeholder (the plan's Decisions)
    "qbert": (".qbert", "WF Q*bert", ["cd.iff"]),          # placeholder too
}


@pytest.mark.parametrize("flavor", FLAVORS)
def test_flavor_boots_its_own_game(flavor):
    """assets/cd.iff is a symlink to this game's bundle, so TOC level 0 (what shell.fth boots) is the game's first level."""
    link = SRC / flavor / "assets" / "cd.iff"
    assert link.is_symlink() and link.resolve() == (LEVELS / GAMES[flavor][0]).resolve()
    toc = read_game_toc(link.read_bytes())
    first = standalone(GAMES[flavor][1][0]).read_bytes()
    assert link.read_bytes()[toc[1][1]:toc[1][1] + toc[1][2]] == first
    assert sorted(p.name for p in (SRC / flavor / "assets").iterdir()) == FLAVORS[flavor][2]


@pytest.mark.parametrize("flavor", FLAVORS)
def test_flavor_id_and_no_permission(flavor):
    g = GRADLE.read_text()
    block = re.search(rf'create\("{flavor}"\) \{{(.*?)\n        \}}', g, re.S)
    assert block, flavor
    body = re.sub(r"//.*", "", block.group(1))
    suffix = FLAVORS[flavor][0]
    if suffix is None:
        assert "applicationId" not in body, "snowgoons keeps org.worldfoundry.wf_game (installs upgrade in place)"
    else:
        assert f'applicationIdSuffix = "{suffix}"' in body
    assert "externalNativeBuild" not in body
    # No phone controller and no permission: only aquarium and condo have a flavor manifest (tests/test_phone_controller_android.py).
    assert not (SRC / flavor / "AndroidManifest.xml").exists()


def test_flavor_list_is_complete():
    """Every game in GAMES is an app, and FLAVORS describes exactly those (aquarium and condo have their own tests)."""
    assert set(FLAVORS) == set(GAMES) & set(FLAVORS)
    names = set(re.findall(r'create\("(\w+)"\)', GRADLE.read_text()))
    assert set(FLAVORS) <= names, names


@pytest.mark.parametrize("flavor", [f for f in FLAVORS if f != "snowgoons"])
def test_new_flavor_art_and_label(flavor):
    """Launcher icons and TV banner override main's with the same names and sizes; the label is the flavor's own."""
    from PIL import Image
    main, res = SRC / "main" / "res", SRC / flavor / "res"
    assert Image.open(res / "drawable" / "tv_banner.png").size == Image.open(main / "drawable" / "tv_banner.png").size
    for d in DENSITIES:
        for name in ("ic_launcher.png", "ic_launcher_round.png", "ic_launcher_foreground.png"):
            assert Image.open(res / f"mipmap-{d}" / name).size == Image.open(main / f"mipmap-{d}" / name).size, (d, name)
    strings = (res / "values" / "strings.xml").read_text()
    assert re.search(rf'name="app_name">{re.escape(FLAVORS[flavor][1])}<', strings)
    assert 'name="log_viewer_label"' in strings
    assert 'name="ic_launcher_background"' in (res / "values" / "colors.xml").read_text()
    # The art is a real engine frame committed in art-src (scripts/gen-android-icons.py), not drawn.
    gen = (REPO / "scripts" / "gen-android-icons.py").read_text()
    art = re.search(rf'"{flavor}": dict\(icon=ART / "([^"]+)"', gen).group(1)
    assert (APP / "art-src" / art).exists(), art


@pytest.mark.parametrize("flavor", FLAVORS)
def test_built_release_apk(flavor):
    import zipfile
    p = APP / "build" / "outputs" / "apk" / flavor / "release" / f"worldfoundry-{flavor}-release.apk"
    if not p.exists():
        pytest.skip(f"{p.relative_to(REPO)} not built (cd android && ./gradlew :app:assemble{flavor.title()}Release)")
    with zipfile.ZipFile(p) as z:
        names = set(z.namelist())
        assert z.read("assets/cd.iff") == (LEVELS / GAMES[flavor][0]).read_bytes()
        assert {"lib/arm64-v8a/libwf_game.so", "lib/armeabi-v7a/libwf_game.so"} <= names
        assert {n for n in names if n.startswith("assets/")} == {f"assets/{a}" for a in FLAVORS[flavor][2]}
