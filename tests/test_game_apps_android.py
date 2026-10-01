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
