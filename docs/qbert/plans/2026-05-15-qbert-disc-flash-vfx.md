# Plan — Q✱bert disc rim colour flash VFX

**Date:** 2026-05-15
**Status:** Complete — e04fb99

## Problem

The flying discs spin (via `DISC_SPIN_RATE` → mb 3034 yaw-rate) but give no
visual feedback when Q✱bert boards one.  In the arcade the disc flashes
bright yellow/orange at the boarding moment.  The WF disc is a plain
purple-blue cylinder throughout.

## Approach

A scriptless yellow annular ring actor sits co-located with each disc.  Its
`wf_Visibility Mailbox` is a per-disc flash countdown mailbox
(`_DL_MB_FLASH`=536, `_DR_MB_FLASH`=537).  The disc script arms the
countdown (`FLASH_DURATION = 8` ticks ≈ 133 ms) when Q✱bert is detected,
then decrements it unconditionally after the phase gate so it drains even
after the disc is consumed.

## Changes — `wflevels/qbert_practice/blender_create_qbert.py`

### A. New constants (after `_DR_MB_PHASE = 535`)

```python
_DL_MB_FLASH   = 536
_DR_MB_FLASH   = 537
FLASH_DURATION = 8       # frames (~133 ms at 60 Hz)
FLASH_Z_OFFSET = 0.05   # render ring above disc surface
```

### B. `_disc_flash_ring_mesh()` — washer geometry

Outer radius 1.25, inner radius 0.85, 16 sides, half\_h=0.075.
Four vertices per segment (outer-top, outer-bot, inner-top, inner-bot);
four quads per segment (top annular, bottom annular, outer wall, inner wall).
Material: bright yellow `(1.0, 0.9, 0.1)`.

### C. Modified `_disc_script(my_row, my_col, my_phase_mb, my_flash_mb)`

```forth
\\ wf disc
{my_phase_mb} read-mailbox 1 = if
  {DISC_SPIN_RATE} 3034 write-mailbox
  400 read-mailbox {my_row} = if
    401 read-mailbox {my_col} = if
      0 419 write-mailbox
      1 426 write-mailbox
      0 {my_phase_mb} write-mailbox
      {DISC_PARK_Z} 3011 write-mailbox
      {FLASH_DURATION} {my_flash_mb} write-mailbox   \ NEW
    then then then
\ Flash countdown — runs every tick, after phase gate.
{my_flash_mb} read-mailbox dup 0 > if
  1 - {my_flash_mb} write-mailbox
else drop then
```

Stack safety: `dup 0 > if … else drop then` — true path consumes the
dup'd value with `1 -` then `write-mailbox`; false path `drop` discards
it.  3 `then` close the phase-gate `if`s; 1 closes the countdown `if`.

### D. Disc creation loop — add `_flash_mb` to tuple

```python
for _name, _row, _col, _phase_mb, _flash_mb in (
    ('disc_left',  DISC_L_ROW, DISC_L_COL, _DL_MB_PHASE, _DL_MB_FLASH),
    ('disc_right', DISC_R_ROW, DISC_R_COL, _DR_MB_PHASE, _DR_MB_FLASH),
):
    ...
    _d['wf_Script'] = _disc_script(_row, _col, _phase_mb, _flash_mb)
```

### E. Flash ring actor creation loop (after disc print)

```python
DISC_FL_ACTOR_IDX = _pre_disc_actor_count + 3
DISC_FR_ACTOR_IDX = _pre_disc_actor_count + 4
for _fname, _frow, _fcol, _fflash_mb in (
    ('disc_flash_L', DISC_L_ROW, DISC_L_COL, _DL_MB_FLASH),
    ('disc_flash_R', DISC_R_ROW, DISC_R_COL, _DR_MB_FLASH),
):
    _fx, _fy, _fz = _disc_world_xyz(_frow, _fcol)
    _fr = bpy.data.objects.new(_fname, _flash_ring_mesh)
    _fr.location = (_fx, _fy, _fz + FLASH_Z_OFFSET)
    ...
    _fr['wf_Visibility Mailbox']     = _fflash_mb
    _fr['wf_NumberOfLocalMailboxes'] = 0
    # No wf_Script — visibility-mailbox driven only.
```

### F. Round-reset additions (two locations in director script)

Both the level-init block and round-clear block get:
```forth
0 {_DL_MB_FLASH} write-mailbox 0 {_DR_MB_FLASH} write-mailbox
```

## Files changed

- `wflevels/qbert_practice/blender_create_qbert.py`

## Build steps

```bash
blender -b wflevels/qbert_practice/qbert_practice.blend \
        -P wflevels/qbert_practice/blender_create_qbert.py
wftools/wf_blender/build_level_binary.sh qbert_practice
LD_LIBRARY_PATH=engine/libs DISPLAY=:0 engine/wf_game \
    -Lwflevels/qbert_practice-standalone.iff
```

## Verification

Automated — flash countdown via debug bridge:

```python
b.watch(idx=1, mailbox=536)   # _DL_MB_FLASH
b.set_mailbox(mailbox=534, value=1, idx=0)   # disc-L present
b.set_mailbox(mailbox=400, value=1, idx=0)   # Q*bert row=1
b.set_mailbox(mailbox=401, value=-1, idx=0)  # Q*bert col=-1
assert b.wait_for_mailbox(idx=1, mailbox=536, expected=8.0, timeout=1.0)
assert b.wait_for_mailbox(idx=1, mailbox=536, expected=0.0, timeout=2.0)
```

Visual — screenshots captured via bridge screenshot op:

**disc_flash_ring_visible.png** — ring held visible (`set_mailbox(536, 999)`);
yellow washer visible off the top-left of the pyramid at disc-L position:

![flash ring visible](file:///home/will/tmp/qbert-screenshots/disc_flash_ring_visible.png)

**disc_flash_ring_gone.png** — countdown drained to 0, ring invisible:

![flash ring gone](file:///home/will/tmp/qbert-screenshots/disc_flash_ring_gone.png)
