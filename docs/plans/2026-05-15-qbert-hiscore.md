# Plan — Q✱bert high-score persistence

**Date:** 2026-05-15
**Status:** In progress

## Context

Q✱bert tracks SCORE (mb 70) and LIVES (mb 72); when game-over fires (mb 420) the engine shows "GAME OVER" but discards the score. This plan adds:

1. 23-entry high-score file (`qbert_hiscores.txt`, binary struct) persisted across runs; seeded with the arcade ROM's factory defaults on first run.
2. 3-char AAA-style initials picker on game-over when the score is a new high.
3. HIGH SCORES table rendered in the game-over overlay, faithfully reproducing the arcade's two-column layout.

No Forth changes — all work is in C++.

## Critical files

- `wfsource/source/game/hscore.h` — new
- `wfsource/source/game/hscore.cc` — new (auto-compiled; `game/` is in `build_game.sh` DIRS)
- `wfsource/source/game/main.cc` — add 3 new DESIGNER_CHEATS globals
- `wfsource/source/game/game.cc:333-341` — extend HUD mailbox block with state machine
- `wfsource/source/gfx/gl/display.cc:68-133` — extend `DrawHud()` game-over overlay

## Data format

```cpp
static constexpr int HS_COUNT = 23;
struct HiScore { int score; int round; char name[4]; };
```

Saved as raw binary (`fwrite` of `g_hiscores[HS_COUNT]`) to `qbert_hiscores.txt` in the working directory (`wfsource/source/game/`). Seeded with arcade factory defaults on missing/corrupt file.

## Arcade factory defaults (all 23)

From the attract-mode HIGH SCORES screen (verified via MAME screenshot 2026-05-15):

| # | Name | Score |   | # | Name | Score |
|---|------|-------|---|---|------|-------|
| 1 | TJC  | 3000  |   | 2 | JML  | 2500  |
| 3 | JAH  | 2000  |   | 4 | MJS  | 1750  |
| 5 | ECW  | 1500  |   | 6 | BLT  | 1250  |
| 7 | BMW  | 1000  |   | 8 | DMV  | 950   |
| 9 | FDA  | 900   |   |10 | LMG  | 825   |
|11 | DDT  | 800   |   |12 | JCM  | 775   |
|13 | ZAP  | 750   |   |14 | NAB  | 725   |
|15 | JUN  | 700   |   |16 | HFR  | 675   |
|17 | RON  | 650   |   |18 | FXS  | 625   |
|19 | DLB  | 600   |   |20 | LEE  | 575   |
|21 | CPB  | 550   |   |22 | WBD  | 525   |
|23 | SAM  | 500   |

## Arcade table layout (reproduced faithfully)

```
         HIGH SCORES
           1) TJC 3000
 2) JML 2500    3) JAH 2000
 4) MJS 1750    5) ECW 1500
 ...            ...
22) WBD  525   23) SAM  500
```

Entry #1 centered at top; entries 2–23 in two-column pairs (left = even rank, right = odd rank). Header "HIGH SCORES" in red; scores in yellow.

## Joystick bit layout (verified from sjoystic.h)

| Bit mask | Direction | Picker action |
|----------|-----------|---------------|
| `0x0800` | UP        | prev letter   |
| `0x1000` | DOWN      | next letter   |
| `0x2000` | RIGHT     | advance / confirm |
| `0x4000` | LEFT      | back one position |

Read from mb 1910 (`HARDWARE_JOYSTICK1_RAW_JUSTPRESSED`) — already edge-detected by engine.

## Build pipeline

```bash
cd /home/will/WorldFoundry.2026-new-level
bash engine/build_game.sh
(cd wfsource/source/game && ./wf_game)
```

## Verification

1. First launch — no `qbert_hiscores.txt` → table shows 5 blank `---` rows.
2. Play to game-over with score > 0 → AAA picker appears; UP/DOWN cycles letters, RIGHT advances/confirms, LEFT backs up.
3. After 3rd char confirmed → file written; table shows new entry.
4. Relaunch → persisted scores load from file and display in table.
5. Score below 5th place — picker skipped; table still shows.
6. Restart (after game-over) → SCORE/LIVES reset; table unchanged.
