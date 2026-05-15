# Plan — Q✱bert game-over hold + name-entry fix

**Date:** 2026-05-15
**Status:** Not started

## Problem

Two bugs in the current game-over flow:

1. **Restart fires during initials entry.** The Forth player script edge-detects
   any raw joystick press (mb `INDEXOF_HARDWARE_JOYSTICK1_RAW`) to trigger restart
   while `mb 420 = 1`. The C++ side also reads mb 1910 (JUSTPRESSED) for UP/DOWN/
   RIGHT/LEFT during `wf_hud_entering_initials`. The first joystick press to scroll
   a letter fires both paths simultaneously — restart wins, initials are lost.

2. **No minimum hold on the game-over screen.** If the score doesn't qualify for
   the high-score table, the restart fires on the very first button press, giving
   the player no time to read the GAME OVER screen or table.

## Fix

Two new global mailboxes:

| MB  | Name            | Purpose |
|-----|-----------------|---------|
| 590 | GO_BLOCK        | C++ sets 1 while initials entry is live; Forth must not restart while non-zero |
| 591 | GO_HOLD_TIMER   | Countdown (ticks) before restart is allowed; C++ arms to 180 on game-over edge, decrements each frame |

### `wfsource/source/game/game.cc`

In the HUD update block (around line 358):

**On fresh game-over edge** (`wf_hud_game_over && !s_prev_game_over`):
```cpp
mb.WriteMailbox(591, Scalar(180, 0));   // ~3 s hold regardless
if (HScore_IsHigh(wf_hud_score))
{
    mb.WriteMailbox(590, Scalar(1, 0)); // block Forth restart
    // ... existing initials-init code ...
    wf_hud_entering_initials = 1;
}
```

**When initials confirmed** (inside `s_initials_pos == 2` RIGHT branch):
```cpp
HScore_Insert(...);
HScore_Save();
wf_hud_entering_initials = 0;
mb.WriteMailbox(590, Scalar(0, 0));     // unblock Forth restart
mb.WriteMailbox(591, Scalar(180, 0));   // 3 s more to view updated table
```

**Each frame** (unconditional, outside the edge block):
```cpp
int hold = mb.ReadMailbox(591).WholePart();
if (hold > 0)
    mb.WriteMailbox(591, Scalar(hold - 1, 0));
```

### `wflevels/qbert_practice/blender_create_qbert.py`

Add mailbox comments and constants:
```python
#   590        GO_BLOCK (C++ sets 1 during initials entry; Forth must not restart)
#   591        GO_HOLD_TIMER (C++ countdown; Forth restart blocked while > 0)
GO_BLOCK_MB      = 590
GO_HOLD_TIMER_MB = 591
```

Change the game-over restart block in the player script from:
```forth
420 read-mailbox 1 = if
  0 = if           \ prev was idle
    stick 0 <> if  \ joystick now
      [restart]
    then
  then
  exit
else drop then
```
to:
```forth
420 read-mailbox 1 = if
  590 read-mailbox 0 = if    \ not blocked by C++ initials entry
    591 read-mailbox 0 = if  \ hold timer expired
      0 = if                 \ prev was idle
        stick 0 <> if        \ joystick now
          [restart]
        then
      else drop then         \ prev wasn't idle
    else drop then           \ hold still counting
  else drop then             \ GO_BLOCK set
  exit
else drop then
```

The `prev_stick` value that was on the stack entering the game-over block now
needs to be managed carefully with the extra nesting. See implementation notes
below for the exact stack trace.

## Stack trace for revised restart block

At entry to the game-over block, the stack holds `( prev_stick )`.

```forth
420 read-mailbox 1 = if           \ ( prev_stick ) — game over?
  590 read-mailbox 0 = if         \ ( prev_stick ) — not blocked?
    591 read-mailbox 0 = if       \ ( prev_stick ) — timer expired?
      0 = if                      \ ( ) — prev was idle?
        stick 0 <> if             \ ( ) — joystick now?
          [restart block]         \ ( )
        then                      \ ( )
      else drop then              \ consume prev_stick if non-zero
    else drop then                \ consume prev_stick while timer running
  else drop then                  \ consume prev_stick while blocked
  exit
else drop then                    \ consume prev_stick if not game-over
```

`else drop then` in the inner branches discards `prev_stick` without
restarting, so the stack stays clean in all paths.

## Critical files

- `wfsource/source/game/game.cc` — C++ mailbox writes
- `wflevels/qbert_practice/blender_create_qbert.py` — player Forth script

## Build steps

```bash
# After game.cc edit:
(cd engine && ./build_game.sh)

# After blender_create_qbert.py edit:
blender -b wflevels/qbert_practice/qbert_practice.blend \
        -P wflevels/qbert_practice/blender_create_qbert.py
wftools/wf_blender/build_level_binary.sh qbert_practice

# Run:
LD_LIBRARY_PATH=engine/libs DISPLAY=:0 engine/wf_game \
    -Lwflevels/qbert_practice-standalone.iff
```

## Verification

1. Play to game-over with a non-qualifying score: GAME OVER screen holds ~3 s
   before any button press does anything.
2. Play to game-over with a qualifying score: UP/DOWN scrolls letters without
   triggering restart; RIGHT advances; confirming 3rd letter saves to table and
   holds ~3 more s showing the updated table, then any button restarts.
3. Regression: normal hop, death, round-clear, score HUD unaffected.
