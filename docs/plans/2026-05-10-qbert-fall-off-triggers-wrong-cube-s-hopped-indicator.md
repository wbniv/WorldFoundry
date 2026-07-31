# Plan: Qbert fall-off triggers wrong cube's hopped indicator

**Status:** Presumed resolved during the qbert_practice consolidation — no dedicated fix commit pinned, not re-verified. Reopen if it recurs.

## Context

In `qbert_practice` (post Phase 1 consolidation, commit `f3d2fe6`), hopping off the
bottom-right cube triggers a hopped-state change on an unrelated cube
(user observed the bottom-left top flip). The cube-hop indicator toggling is correct
in the normal case — the bug is that fall-off ALSO toggles a cube, using out-of-range
(row, col) as the array index.

## Root cause

In `wflevels/qbert_practice/blender_create_qbert.py`, the `do-hop` zForth word
(lines 490–508) writes the new (row, col) to mailboxes 400/401, then
unconditionally sets `mb[411] = 1` (QBERT_LANDED) at line 499, and only AFTER that
checks for off-edge (lines 500–507) to set `mb[419] = 1` (fall animation).

The director script (lines 904–908) runs on every tick and processes the LANDED
flag with the current (row, col):

```forth
411 read-mailbox 0 <> if
  400 read-mailbox dup 1 + * 2 / 401 read-mailbox + 200 +   \ R*(R+1)/2 + C + 200
  dup read-mailbox 0 = if 2 swap write-mailbox else drop then
  0 411 write-mailbox then
```

When the player hops off the pyramid, (row, col) is out of bounds (e.g. row=7,
col=7 or col>row), so the triangular-index formula computes a mailbox in the
CUBE_PREV_STATE region (228–255) or wraps onto a wrong CUBE_STATE slot. The
landing handler then writes `2` into that slot — corrupting either the prev-state
of an unrelated cube (causing its top to re-render) or directly flipping another
cube's state.

The bottom-LEFT cube corresponds to mailbox 221 (R=6, C=0, idx 21). Various
off-edge (row, col) combinations land on neighbouring slots in the 200–255 range
which is why the visible flip appears on a cube unrelated to the direction the
player departed in.

## Fix

Gate the LANDED flag on the in-bounds check so the director never processes a
landing for an off-pyramid (row, col).

**File:** `wflevels/qbert_practice/blender_create_qbert.py`
**Lines:** 499–508 in the `do-hop` definition.

Replace:

```forth
drop 1 411 write-mailbox 12 402 write-mailbox
400 read-mailbox dup 0 < swap 6 > |
401 read-mailbox 0 < |
401 read-mailbox 400 read-mailbox > |
if
  400 read-mailbox dup 0 < if drop 0 then dup 6 > if drop 6 then
  6 swap - 2 * 1 + 2 + INDEXOF_Z_POS write-mailbox
  1 419 write-mailbox
then ;
```

With:

```forth
drop 12 402 write-mailbox
400 read-mailbox dup 0 < swap 6 > |
401 read-mailbox 0 < |
401 read-mailbox 400 read-mailbox > |
if
  400 read-mailbox dup 0 < if drop 0 then dup 6 > if drop 6 then
  6 swap - 2 * 1 + 2 + INDEXOF_Z_POS write-mailbox
  1 419 write-mailbox
else
  1 411 write-mailbox
then ;
```

Only difference: `1 411 write-mailbox` moves from the unconditional pre-check
section into the `else` (on-pyramid) branch. mb 402 (hop cooldown) still
unconditionally gets `12`.

## Build / verify

1. `python3 -m py_compile wflevels/qbert_practice/blender_create_qbert.py`
2. Apply the per-CLAUDE.md qbert build pipeline:
   - re-run `blender_create_qbert.py` inside Blender (or run the build_level
     script that re-emits the `.lev`), then
   - `./scripts/build_level_binary.sh qbert_practice` to produce `qbert_practice.lvl`, then
   - `iffcomp` the standalone `qbert_practice-standalone.iff`.
3. Run via `task qbert` (or the standalone runner command we normally print).
4. Repro test: hop off the bottom-right cube in each off-edge direction
   (RIGHT, DOWN). Confirm:
   - Fall animation still plays (mb 419 path still fires).
   - No cube anywhere on the pyramid changes its top colour as a result of the
     fall.
5. Regression test: hop onto a fresh (state-0) cube on the pyramid — its top
   should still flip to the state-2 colour as before.

## Files touched

- `wflevels/qbert_practice/blender_create_qbert.py` (one zForth word edited)

No engine / C++ changes. No new mailboxes. No new fields.
