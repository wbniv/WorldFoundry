# Plan: SMB `?`-block coin pop-out animation

**Status:** Active 2026-05-18. Replaces the (now landed) per-actor collision mailboxes plan. In-repo copy at [docs/plans/2026-05-18-smb-qblock-coin-pop.md](../../WorldFoundry.2026-new-level/docs/plans/2026-05-18-smb-qblock-coin-pop.md).

## Context

User picked option 3 from the post-bump-mechanic menu: add the visible coin pop-out that the original framing called for (*"you hit the ? boxes and coins come out the top for some period of time"*). The visibility-flip half (gold `?`-block → flat-tan used-block) landed in `f4071a3`; this adds the coin coming out of the block top on bump → arcs up → falls back → vanishes.

Verified during exploration:
- **`write-actor-mailbox` does relocate Anchored statplats** — `Actor::WriteSystemMailbox` on `EMAILBOX_Z_POS` (mailbox 3011) calls `_physicalAttributes.SetPosition()` immediately; the renderer reads the new position next frame. No Jolt sync needed for anchored actors without physics bodies.
- **`write-actor-mailbox` stack signature is `( val idx actor_idx -- )`** — confirmed at `engine/stubs/scripting_zforth.cc:136-148`. qbert's popup_500 already uses this exact pattern for runtime-positioned popup labels (`wflevels/qbert_practice/blender_create_qbert.py:3269-3271`) — direct precedent.

No engine changes needed. Pure level + Forth.

## Design

### New mailboxes — add to `wfsource/source/mailbox/mailbox.inc` after `SMB_QBLOCK_0_USED`

```c
MAILBOXENTRY( SMB_QBLOCK_0_COIN_VISIBLE, 1805 )   Comment("coin visibility 0=hidden 1=visible")
MAILBOXENTRY( SMB_QBLOCK_0_COIN_PHASE,   1806 )   Comment("coin animation phase, 0=idle, 1..30=animating")
```

Mailbox.inc is in zForth's constant table, so **must rebuild the engine** after adding entries — same gotcha that bit me in `f4071a3`.

### New actor — coin disc, anchored statplat stacked on block 0

In `wflevels/smb_w1_1/blender_create_smb.py`, add inside the `if i == 0:` block (right after `qblock_00_used`):

```python
mat_coin = make_mat('smb_coin', (1.0, 0.84, 0.0))   # NES coin yellow
COIN_R, COIN_T = 0.3, 0.04
coin_z = BLOCK_Z + BSIZE   # block top
coin = add_statplat(f'qblock_{i:02d}_coin',
                    bx - COIN_R, -COIN_T, coin_z - COIN_T,
                    bx + COIN_R,  COIN_T, coin_z + COIN_T,
                    mat_coin)
coin['wf_Visibility Mailbox'] = MB_SMB_QBLOCK_0_COIN_VISIBLE   # =1805, init 0 ⇒ hidden
```

Plus the Python literal `MB_SMB_QBLOCK_0_COIN_VISIBLE = 1805` near the existing `MB_SMB_QBLOCK_0_NORMAL/USED` constants (Blender custom props take literals, not `INDEXOF_*` names).

### Mario's Forth script — two extensions

**(a) On bump (extend the existing inner conditional):**

```forth
0 INDEXOF_SMB_QBLOCK_0_NORMAL  write-mailbox
1 INDEXOF_SMB_QBLOCK_0_USED    write-mailbox
1 INDEXOF_SMB_QBLOCK_0_COIN_VISIBLE write-mailbox    \ NEW
1 INDEXOF_SMB_QBLOCK_0_COIN_PHASE   write-mailbox    \ NEW
```

**(b) New per-tick block at the end of Mario's script:**

```forth
\ Advance coin animation when phase > 0
INDEXOF_SMB_QBLOCK_0_COIN_PHASE read-mailbox dup 0<> if
  1 +                                         \ next phase
  dup 30 > if
    \ End of animation: hide coin, clear phase
    drop
    0 INDEXOF_SMB_QBLOCK_0_COIN_VISIBLE write-mailbox
    0 INDEXOF_SMB_QBLOCK_0_COIN_PHASE   write-mailbox
  else
    \ Store new phase, then compute + write coin Z
    dup INDEXOF_SMB_QBLOCK_0_COIN_PHASE write-mailbox
    \ z = block_top + offset(phase)
    \   rise:  phase * 0.1     for phase ≤ 15  (peak +1.5 m at phase=15)
    \   fall:  (30 - phase) * 0.1  for phase > 15
    dup 15 <= if
      0.1 *
    else
      30 swap - 0.1 *
    then
    7.5 +                                     \ block_top + offset
    INDEXOF_Z_POS COIN_ACTOR_IDX write-actor-mailbox
  then
else
  drop
then
```

`COIN_ACTOR_IDX` is hardcoded post-rebuild via `--debug-print-actors`. Current expectation: adding the coin after `qblock_00_used` (idx 13) makes the coin idx 14, shifting `qblock_01`/`02`/goomba/koopa/flagpole indices up by one. Verified during impl.

## Phases

1. **Edit mailbox.inc** — 2 new GLOBAL_USER entries.
2. **Rebuild engine** (`engine/build_game.sh`) — picks up new zForth constants.
3. **Edit blender_create_smb.py** — `mat_coin`, coin actor in `if i == 0:` block, extend Mario script with kickoff + per-tick animation.
4. **Rebuild level** (Blender → `build_level_binary.sh`).
5. **`--debug-print-actors` lookup** of the coin's actor idx; if not 14, update `COIN_ACTOR_IDX` constant and re-rebuild.
6. **Verify** via bridge state-injection: `set_mailbox SMB_QBLOCK_0_COIN_PHASE = 1` and screenshot every ~0.3 s for ~3 s — should see coin appear at block top, rise, fall, disappear. (Same workaround as `f4071a3` — bridge-driven, since interactive jump apex doesn't reach the block at the engine's no-window-focus framerate.)
7. **Commit** — one commit.

## Out of scope

- `+200` score popup label (mirror qbert popup pattern; separate plan)
- Coin pickup sound via miniaudio (separate plan; memory says audio verifies on a different machine)
- Generalizing to blocks 1 + 2 (quick repeat once block 0 is solid)

## Critical files

- `wfsource/source/mailbox/mailbox.inc` — 2 new GLOBAL_USER entries (`SMB_QBLOCK_0_COIN_VISIBLE = 1805`, `SMB_QBLOCK_0_COIN_PHASE = 1806`).
- `wflevels/smb_w1_1/blender_create_smb.py` — coin material, coin actor, Mario script (kickoff in bump branch + per-tick animation block).
- Reference: `wflevels/qbert_practice/blender_create_qbert.py:3269-3271` (popup_500 position writes) — the pattern this mirrors.

## Verification

- `engine/build_game.sh` succeeds.
- Bridge sequence: `set_mailbox 1806 1` (kick off animation) then 4–5 screenshots at 0.3 s intervals — coin visible in successive shots at rising → peak → falling positions, then absent.
- After an actual in-game bump (interactive run), the coin appears as part of the visibility-flip sequence at block top.
- `~/tmp/smb-shots/coin_*.png` captured for the commit message.
