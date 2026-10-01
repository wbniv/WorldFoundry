"""Regression guard: the mailbox read/write path must not stream debug text.

Found 2026-10-01 on the real Chromecast HD (docs/plans/2026-10-01-swarming-poster.md, Phase E step 1): every script mailbox call
cost 4.2 us because three DBSTREAM1 statements in the path (`cmailbox << ... << std::endl`) run in EVERY build (the CMake defines
SW_DBSTREAM=1 even for the Android release). A Forth script making 8,000 calls a tick spent 34 ms of 39 ms in them: 20 fps instead of 60.
dbstrm.hp says what each level is for: DBSTREAM1 is "nothing in the game loop (startup and shutdown only)"; a per-call trace belongs at DBSTREAM5.
With them at DBSTREAM5 the same calls cost 0.28 us (measured with the timer's own overhead included) and the level runs at 59.9 fps.

This test reads the three sources and fails if a streaming macro below level 5 reappears in a mailbox read/write function.
    python3 -m pytest tests/test_mailbox_hot_path.py -v
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GAME = REPO / "wfsource" / "source" / "game"


def _functions(text, names):
    """Bodies of the C++ functions whose definition line contains one of `names` (up to the next line that starts at column 0 with `}`)."""
    out = {}
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        for n in names:
            if re.match(rf"\S.*\b{re.escape(n)}\s*\(", ln) and not ln.rstrip().endswith(";"):
                j = i
                while j < len(lines) and not lines[j].startswith("}"):
                    j += 1
                out[(n, i + 1)] = "\n".join(lines[i:j + 1])
    return out


def test_mailbox_calls_do_not_stream_at_levels_one_to_four():
    hot = {
        GAME / "mailbox.cc": ["ReadMailbox", "WriteMailbox"],
        GAME / "level.cc": ["WorldFoundryMailboxesManager::LookupMailboxes", "Level::ReadSystemMailbox", "Level::WriteSystemMailbox"],
    }
    found = 0
    offenders = []
    for path, names in hot.items():
        for (name, line), body in _functions(path.read_text(), names).items():
            found += 1
            for m in re.finditer(r"DBSTREAM([1-4])\s*\(", body):
                offenders.append(f"{path.name}:{line} {name}: DBSTREAM{m.group(1)}")
    assert found >= 4, "the scan found too few mailbox functions: it is out of date"
    assert offenders == [], "a per-call debug stream is back in the mailbox path (4 us a call on the Chromecast): " + "; ".join(offenders)


def test_the_three_known_sites_are_at_level_five():
    for f, needle in ((GAME / "mailbox.cc", "LevelMailboxes::ReadMailbox"), (GAME / "mailbox.cc", "GameMailboxes::ReadMailbox"), (GAME / "level.cc", "wfmbm: index")):
        line = next(l for l in f.read_text().splitlines() if needle in l and "cmailbox" in l)
        assert "DBSTREAM5" in line, line
