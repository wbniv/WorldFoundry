# Plan — Q✱bert Score HUD wiring

**Date:** 2026-05-14
**Status:** In progress

## Context

`DrawHud()` in [`wfsource/source/gfx/gl/display.cc:68-133`](../../wfsource/source/gfx/gl/display.cc) already renders SCORE / TIMER / LIVES from mb 70/71/72 using [STB Easy Font](https://github.com/nothings/stb/blob/master/stb_easy_font.h). `build_game.sh` passes `-DDESIGNER_CHEATS=1` so it's active in every dev build. No C++ changes needed.

The gaps are entirely in the Forth director script embedded in [`wflevels/qbert_practice/blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py):
- mb 70 (SCORE) is initialized to 0 and never incremented.
- mb 71 (TIMER) is initialized to 0 and never ticked.
- On full-game restart, mb 70/71 are not reset.

## Changes

### 1. Cube-flip score (+25 pts) — `blender_create_qbert.py:2580`

In the director landing handler, inside the `0 = if` branch (cube was unflipped → now flipped):

```python
# Old
"dup read-mailbox 0 = if 2 swap write-mailbox else drop then ",
# New
"dup read-mailbox 0 = if 2 swap write-mailbox 70 read-mailbox 25 + 70 write-mailbox else drop then ",
```

### 2. Round-clear bonus (+1000 pts) + timer reset — `blender_create_qbert.py:2646`

Prepend to the round-clear expiry block (fires once when 90-tick countdown hits 0):

```python
"70 read-mailbox 1000 + 70 write-mailbox "
"0 71 write-mailbox "
"28 0 do 0 200 i + write-mailbox loop ",   # existing line
```

### 3. Score + timer reset on restart — `blender_create_qbert.py:506`

Add alongside `"3 72 write-mailbox "` in the player restart block:

```python
"3 72 write-mailbox "
"0 70 write-mailbox "   # added
"0 71 write-mailbox "   # added
"0 411 write-mailbox ..."
```

### 4. Per-tick timer increment — after `blender_create_qbert.py:2324`

Insert after the LEVEL_INITIALIZED `then\n`, before the intro state machine:

```python
"71 read-mailbox 1 + 71 write-mailbox ",
```

Elapsed-tick display (not a countdown). Arcade-pressure countdown deferred.

## Out of scope (deferred)

Enemy-kill scoring (Slick/Sam +300, Green Ball +100, disc rescue +500) — collision handlers are spread through the 2700-line script; deferred to follow-up.

Arcade-style countdown timer with time-pressure death — deferred.

## Build pipeline

```bash
blender -b wflevels/qbert_practice/qbert_practice.blend \
        -P wflevels/qbert_practice/blender_create_qbert.py
wflevels/qbert_practice/build_level_binary.sh
wftools/iffcomp-rs/target/release/iffcomp-rs wflevels/qbert_practice-standalone.iff.txt
(cd wfsource/source/game && ./wf_game)
```

## Verification

1. Start game — SCORE 0, TIMER 0, LIVES 3.
2. Hop one unflipped cube — SCORE → 25.
3. Flip all 28 cubes — SCORE → 700; round-clear fires → SCORE → 1700, TIMER resets.
4. TIMER increments each frame during play.
5. Trigger game-over → restart — SCORE 0, TIMER 0, LIVES 3.
6. Normal hop animation unchanged (regression).
