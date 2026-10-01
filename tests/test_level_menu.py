"""The level menu of multi-level bundles: SMB world select (docs/plans/2026-10-01-level-menu-selector.md).

No device. Four layers:

  * cdpack: without --manifest every tracked bundle is reproduced byte for byte (the menu is opt-in); with the SMB
    manifest it writes the committed wflevels/smb-menu-cd.iff, whose levels sit at smb-cd.iff's indices with a MENU
    chunk last; bad manifests are refused;
  * the menu module (wfsource/source/game/level_menu.cc) in a host harness with ASan and UBSan and a fake clock:
    reading the real bundle, moving, clamping, repeating, scrolling, cutting long names, ignoring a button held at
    entry, starting only after release, the geometry; the rendered states go to ~/tmp/level-menu/;
  * the scripted input (wf_game --menu-input=);
  * the real engine on the desktop display (skipped without DISPLAY or a current engine/wf_game): the menu, World 1-3,
    the level's own LEVEL_TO_RUN chain (written through the debug bridge exactly as the flagpole ActBox writes it),
    Backspace's return request, a second pick and a clean quit.

    python3 -m pytest tests/test_level_menu.py -v        (or: task test-level-menu)
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import time
from pathlib import Path

import pytest

from level_menu_harness import (GAME, LEVELS, PLAIN_BUNDLES, REPO, SHELL, SHELL_MENU, SMB_LEVELS, SMB_MANIFEST,
                                SMB_MENU_BUNDLE, build_host, cdpack, read_menu, read_toc, rects, run_host, states)

SHOTS = Path.home() / "tmp" / "level-menu"
A, UP, DOWN = 0x1, 0x800, 0x1000
BAR, EDGE, BG = (0x23, 0x40, 0x6B, 255), (0x56, 0xD3, 0x64, 255), (0x0E, 0x17, 0x26, 255)
WORLDS = ["World 1-1", "World 1-2", "World 1-3", "World 1-4"]


# ---- cdpack -----------------------------------------------------------------

@pytest.mark.parametrize("bundle", sorted(PLAIN_BUNDLES))
def test_identical_without_manifest(bundle, tmp_path):
    out = tmp_path / "cd.iff"
    cdpack(SHELL, *(LEVELS / f for f in PLAIN_BUNDLES[bundle]), "-o", out)
    assert out.read_bytes() == (REPO / bundle).read_bytes(), f"cdpack no longer reproduces {bundle}"


def test_menu_bundle_is_current_and_keeps_the_smb_indices(tmp_path):
    out = tmp_path / "cd.iff"
    cdpack(SHELL_MENU, "--manifest", SMB_MANIFEST, "-o", out)
    data = out.read_bytes()
    assert data == SMB_MENU_BUNDLE.read_bytes(), "wflevels/smb-menu-cd.iff is stale: run task build-cd-iff-smb-menu"

    plain = (LEVELS / "smb-cd.iff").read_bytes()
    toc, plain_toc = read_toc(data), read_toc(plain)
    assert [t[0] for t in toc] == [b"SHEL"] + [e[0] for e in plain_toc[1:]] + [b"MENU"]
    assert toc[1:5] == plain_toc[1:5], "the four levels must sit at smb-cd.iff's TOC offsets (the flag/axe chain)"
    for (_, off, size), name in zip(toc[1:5], SMB_LEVELS):
        assert data[off:off + size] == (LEVELS / name).read_bytes()
    shel = data[2048:2048 + 8 + toc[0][2]]
    assert shel[8:] == SHELL_MENU.read_bytes()
    assert re.search(rb"\n\s*-1 INDEXOF_LEVEL_TO_RUN write-mailbox", SHELL_MENU.read_bytes())

    menu = read_menu(data)
    assert menu == {"version": 1, "levels": 4, "title": "WF SMB", "prompt": "Choose a world",
                    "entries": list(enumerate(WORLDS))}


@pytest.mark.parametrize("case", ["no-levels", "non-ascii", "too-long", "missing-file", "both", "keyword"])
def test_refuses_bad_manifests(case, tmp_path):
    lvl = LEVELS / SMB_LEVELS[0]
    lines = {
        "no-levels": "title Nothing here\n",
        "non-ascii": f"level {lvl} | Wörld 1-1\n",
        "too-long": f"level {lvl} | {'x' * 61}\n",
        "missing-file": "level no-such-level.iff | World 9-9\n",
        "both": f"level {lvl} | World 1-1\n",
        "keyword": f"levle {lvl} | World 1-1\n",
    }[case]
    manifest = tmp_path / "m.manifest"
    manifest.write_text(lines, encoding="utf-8")
    extra = [lvl] if case == "both" else []
    p = cdpack(SHELL_MENU, *extra, "--manifest", manifest, "-o", tmp_path / "out.iff", check=False)
    assert p.returncode == 1 and p.stderr.startswith("error:"), (p.returncode, p.stderr)
    assert not (tmp_path / "out.iff").exists()


def test_help_exits_zero():
    p = cdpack("-h", check=False)
    assert p.returncode == 0 and "--manifest" in p.stdout


# ---- the menu module ----------------------------------------------------------

@pytest.fixture(scope="module")
def host(tmp_path_factory):
    return build_host(tmp_path_factory.mktemp("level-menu-host"))


def test_button_bits_match_the_engine():
    """level_menu.h spells the bits as numbers (no engine header); game.cc static_asserts them too."""
    h = (REPO / "wfsource/source/hal/sjoystic.h").read_text()
    header = (GAME / "level_menu.h").read_text()
    for name, ours in (("A", "kButtonA"), ("UP", "kButtonUp"), ("DOWN", "kButtonDown")):
        bit = int(re.search(rf"^#define\s+EJ_BUTTONB_{name}\s+(\d+)", h, re.M).group(1))
        mine = re.search(rf"{ours}\s*=\s*1u << (\d+);", header).group(1)
        assert bit == int(mine), (name, bit, mine)


def test_host_reads_the_real_bundle(host):
    out = run_host(host, [f"bundle {SMB_MENU_BUNDLE}", "autopick"])
    assert out[:2] == ["TITLE WF SMB", "PROMPT Choose a world"]
    assert out[2:6] == [f"ENTRY {i} {i} {w}" for i, w in enumerate(WORLDS)]
    assert out[6:] == ["BUNDLE ok levels=4 entries=4", "AUTO -1"]


@pytest.mark.parametrize("bundle", ["wflevels/smb-cd.iff", "wfsource/source/game/cd.iff"])
def test_host_finds_no_menu_in_plain_bundles(host, bundle):
    assert run_host(host, [f"bundle {REPO / bundle}"]) == ["BUNDLE none"]


def test_host_autopick_one_or_no_entry(host):
    assert run_host(host, ["synthetic 1", "autopick", "synthetic 0", "autopick", "synthetic 4", "autopick"]) == [
        "SYNTHETIC 1", "AUTO 0", "SYNTHETIC 0", "AUTO 0", "SYNTHETIC 4", "AUTO -1"]


def test_host_moves_and_clamps(host):
    s = states(run_host(host, [f"bundle {SMB_MENU_BUNDLE}", "menu 0", "input 0 0",
                               f"input {UP:x} 10", "input 0 20",                    # up at the top: stays
                               *[f"input {b:x} {30 + 10 * k}" for k, b in enumerate([DOWN, 0] * 5)]]))
    assert [x["cursor"] for x in s] == [0, 0, 0, 0] + [1, 1, 2, 2, 3, 3, 3, 3, 3, 3]
    assert not any(x["chosen"] for x in s)


def test_host_held_at_entry_is_ignored(host):
    """The A still down as the menu appears (the press that ended the last level) must not pick World 1-1."""
    s = states(run_host(host, [f"bundle {SMB_MENU_BUNDLE}", "menu 0", f"input {A:x} 0", f"input {A:x} 16",
                               f"input {A | DOWN:x} 32", "input 0 48", f"input {A:x} 64"]))
    assert [(x["chosen"], x["cursor"]) for x in s] == [(0, 0), (0, 0), (0, 0), (0, 1), (0, 1), (1, 1)]


def test_host_starts_only_after_release(host):
    """A picks the level, but the level starts only once A is up, so the jump does not reach Mario."""
    s = states(run_host(host, [f"bundle {SMB_MENU_BUNDLE}", "menu 0", "input 0 0", f"input {DOWN:x} 16", "input 0 32",
                               f"input {DOWN:x} 48", "input 0 64", f"input {A:x} 80", f"input {A:x} 200", "input 0 216"]))
    assert [(x["chosen"], x["done"]) for x in s[-3:]] == [(1, 0), (1, 0), (1, 1)]
    assert s[-1]["level"] == 2, "World 1-3 is TOC level 2"


def test_host_starts_anyway_if_a_button_sticks(host):
    s = states(run_host(host, [f"bundle {SMB_MENU_BUNDLE}", "menu 3", "input 0 0", f"input {A:x} 100",
                               f"input {A:x} 1599", f"input {A:x} 1600"]))
    assert [(x["done"], x["level"]) for x in s[-3:]] == [(0, 3), (0, 3), (1, 3)]


def test_host_held_direction_repeats_and_scrolls(host):
    times = [0, 399, 400, 520, 1000]
    s = states(run_host(host, ["synthetic 20", "menu 0", "input 0 0", *[f"input {DOWN:x} {t}" for t in times]]))
    # pressed at 0 -> 1; repeats at 400, 520, then 640, 760, 880, 1000.
    assert [x["cursor"] for x in s[2:]] == [1, 1, 2, 3, 7]
    assert s[-1]["first"] == 2, "six rows: cursor 7 shows rows 2..7"


def test_host_scroll_window_and_arrows(host):
    out = run_host(host, ["synthetic 14", "menu 8", "rects 1920 1080"])
    assert states(out)[0]["first"] == 3
    _, rs = rects(out)
    def arrows(rs):   # the arrows are the grey strips centred on x = 960 (the counter is right-aligned)
        sub = [r for r in rs if r[4] == (0x8F, 0xA3, 0xBF, 255) and r[0] >= 920 and r[2] <= 1000]
        return any(250 <= r[1] < 290 for r in sub), any(904 <= r[1] < 940 for r in sub)
    assert arrows(rs) == (True, True), "rows hidden above and below"
    assert arrows(rects(run_host(host, ["synthetic 14", "menu 0", "rects 1920 1080"]))[1]) == (False, True)
    assert arrows(rects(run_host(host, ["synthetic 4", "menu 0", "rects 1920 1080"]))[1]) == (False, False), \
        "four entries: no arrows"


def test_host_cuts_a_long_name(host):
    long = "Snowgoons: the extended director's cut with all the bonus rooms"
    out = run_host(host, [f"synthetic 7 4 {long}", "menu 4", "row 4", "row 3", "rects 1920 1080"])
    row = next(line for line in out if line.startswith("ROW "))[4:]
    assert row.endswith("...") and long.startswith(row[:-3]) and len(row) < len(long), row
    assert "ROW Level 4" in out
    _, rs = rects(out)
    bar = next(r for r in rs if r[4] == BAR)
    text = [r for r in rs if r[4] == (255, 255, 255, 255) and bar[1] <= r[1] < bar[3]]
    assert text and max(r[2] for r in text) <= bar[2] - 20, "the cut name stays inside the highlight bar"


def test_host_geometry(host):
    out = run_host(host, [f"bundle {SMB_MENU_BUNDLE}", "menu 2", "rects 1920 1080", "rects 1920 1080", "rects 1280 720"])
    blocks = [i for i, line in enumerate(out) if line.startswith("RECTS ")]
    changed, big = rects(out[:blocks[1]])
    assert changed
    assert not rects(out[:blocks[2]])[0], "unchanged: no rebuild (Android re-uploads only on change)"
    changed, small = rects(out)
    assert changed and len(small) == len(big)
    assert big[0] == (0.0, 0.0, 1920.0, 1080.0, BG), "a full-screen background: nothing is loaded behind the menu"
    assert all(0 <= x0 < x1 <= 1920 and 0 <= y0 < y1 <= 1080 for x0, y0, x1, y1, _ in big)
    bar = [r for r in big if r[4] == BAR]
    assert bar == [(360.0, 500.0, 1560.0, 592.0, BAR)], "the highlight on row 3 (World 1-3)"
    assert [r for r in big if r[4] == EDGE] == [(360.0, 500.0, 374.0, 592.0, EDGE)]
    assert all(abs(s[2] - b[2] * 2 / 3) < 0.05 and abs(s[3] - b[3] * 2 / 3) < 0.05 for s, b in zip(small, big))


def test_host_renders_the_states(host):
    """Composited pictures of the real rectangles, for comparison with the plan's mockups."""
    pil = pytest.importorskip("PIL")
    from phonepad_harness import render_rects
    SHOTS.mkdir(parents=True, exist_ok=True)
    cases = {
        "default": [f"bundle {SMB_MENU_BUNDLE}", "menu 0"],
        "moved": [f"bundle {SMB_MENU_BUNDLE}", "menu 2"],
        "scrolling": ["synthetic 14", "menu 8"],
        "long-name": ["synthetic 7 4 Snowgoons: the extended director's cut with all the bonus rooms", "menu 4"],
        "tv-hint": [f"bundle {SMB_MENU_BUNDLE}", "menu 1 tv"],
    }
    for name, cmds in cases.items():
        _, rs = rects(run_host(host, [*cmds, "rects 1280 720"]))
        render_rects(rs, 1280, 720).save(SHOTS / f"{name}.png")
    assert pil and len(list(SHOTS.glob("*.png"))) >= len(cases)


# ---- scripted input -----------------------------------------------------------

def test_script_frames(host):
    out = run_host(host, ["script down,a,wait:3,back,quit", *["next"] * 12, "script dowm", "script wait:x"])
    assert out[0] == "SCRIPT ok 11"
    assert out[1:13] == ["FRAME 1000 back=0 quit=0", "FRAME 0 back=0 quit=0", "FRAME 1 back=0 quit=0", "FRAME 0 back=0 quit=0",
                         *["FRAME 0 back=0 quit=0"] * 3, "FRAME 0 back=1 quit=0", "FRAME 0 back=0 quit=0",
                         "FRAME 0 back=0 quit=1", "FRAME 0 back=0 quit=0", "FRAME end"]
    assert out[13].startswith("SCRIPT error unknown --menu-input token \"dowm\"")
    assert out[14].startswith("SCRIPT error unknown --menu-input token \"wait:x\"")


# ---- the real engine ------------------------------------------------------------

WF_GAME = REPO / "engine" / "wf_game"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_line(log: Path, pattern: str, timeout: float, proc) -> str:
    rx, deadline = re.compile(pattern, re.M), time.monotonic() + timeout
    while time.monotonic() < deadline:
        m = rx.search(log.read_text(errors="replace"))
        if m:
            return m.group(0)
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    tail = "\n".join(log.read_text(errors="replace").splitlines()[-25:])
    raise AssertionError(f"no line matching {pattern!r} within {timeout} s (exit {proc.poll()}); log tail:\n{tail}")


def test_engine_smb_menu_chain_and_return(tmp_path):
    if not os.environ.get("DISPLAY"):
        pytest.skip("the engine needs an X display")
    if not WF_GAME.exists() or WF_GAME.stat().st_mtime < (GAME / "level_menu.cc").stat().st_mtime:
        pytest.skip("engine/wf_game is missing or older than level_menu.cc: run task build")
    from debug_bridge_client import BridgeClient

    (tmp_path / "cd.iff").write_bytes(SMB_MENU_BUNDLE.read_bytes())
    port, log, shot = _free_port(), tmp_path / "wf_game.log", tmp_path / "menu.png"
    # down, down, a: World 1-3. The long wait leaves time for the bridge to play the flagpole; then back, up, a, quit.
    script = "wait:10,down,down,a,wait:1500,back,wait:10,up,a,wait:30,quit"
    env = dict(os.environ, LD_LIBRARY_PATH=f"{REPO / 'engine/libs'}:{os.environ.get('LD_LIBRARY_PATH', '')}")
    with log.open("w") as f:
        proc = subprocess.Popen([str(WF_GAME), "-pps", "--debug-port", str(port), f"--menu-input={script}",
                                 f"--capture-frame=4={shot}"], cwd=tmp_path, env=env, stdout=f, stderr=subprocess.STDOUT,
                                preexec_fn=lambda: __import__("resource").setrlimit(__import__("resource").RLIMIT_CORE, (0, 0)))
    try:
        assert _wait_line(log, r'^level-menu: showing 4 entries \("WF SMB"\), cursor on 0$', 60, proc)
        assert _wait_line(log, r"^level-menu: LEVEL_TO_RUN=2 \(World 1-3\)$", 30, proc)
        assert _wait_line(log, r"^level-menu: level 2 starts$", 30, proc)
        # The flagpole ActBox's writes: LEVEL_TO_RUN (5000) = next level, END_OF_LEVEL (1905) = 1.
        cli = BridgeClient(port=port, timeout=20.0)
        try:
            cli.set_mailbox(5000, 3)
            cli.set_mailbox(1905, 1)
        finally:
            cli.close()
        assert _wait_line(log, r"^level-menu: level 3 starts$", 30, proc), "World 1-3's chain reaches World 1-4"
        assert _wait_line(log, r"^level-menu: back to the menu$", 120, proc)
        assert _wait_line(log, r'^level-menu: showing 4 entries \("WF SMB"\), cursor on 2$', 30, proc), \
            "the menu comes back on the last pick"
        assert _wait_line(log, r"^level-menu: LEVEL_TO_RUN=1 \(World 1-2\)$", 30, proc)
        assert _wait_line(log, r"^level-menu: level 1 starts$", 30, proc)
        assert proc.wait(timeout=60) == 0, "quit exits cleanly"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    text = log.read_text(errors="replace")
    assert "ASSERTION FAILED" not in text and "Sanitizer" not in text
    pil = pytest.importorskip("PIL.Image")
    img = pil.open(shot).convert("RGB")
    SHOTS.mkdir(parents=True, exist_ok=True)
    img.save(SHOTS / "engine-menu.png")
    colours = {c for _, c in img.getcolors(1 << 20)}
    assert BAR[:3] in colours and EDGE[:3] in colours, "the captured menu frame shows the highlight bar"
