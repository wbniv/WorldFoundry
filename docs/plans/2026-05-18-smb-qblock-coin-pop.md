# SMB `?`-block coin pop-out animation

**Status:** Done 2026-05-18 — landed in 8a4f822. Follow-on to [2026-05-17-per-actor-collision-mailboxes.md](2026-05-17-per-actor-collision-mailboxes.md) — that plan landed the visibility-flip half (gold `?`-block → flat-tan used-block on Mario bump). This adds the missing visible feedback: a yellow coin emerges from the block top on bump, arcs up briefly, then disappears. The full classic SMB "hit `?`, coin pops out, block goes used" loop.

## Context

User picked option 3 from a follow-up menu after the collision-mailbox feature landed. Original framing was: *"you hit the ? boxes and coins come out the top (for some period of time, not sure how long) then the ? turns into a flat color"* — the "turns flat" half is done; this is the "coin comes out" half.

Out of scope this iteration: `+200` score popup label (separate plan), classic SMB "bing!" sound (separate plan; per memory audio must be verified on a different machine), generalising to blocks 1 + 2 (separate quick follow-up).

## Design

### New actor: `qblock_00_coin`

Pre-spawn an anchored statplat at block 0's top position. Mesh: small yellow disc (cylinder, radius ~0.3 m, depth ~0.08 m). Initial `Visibility Mailbox = SMB_QBLOCK_0_COIN_VISIBLE` (= 0 at start, hidden).

### Two new global mailboxes

Add to [mailbox.inc](../../wfsource/source/mailbox/mailbox.inc) right after `SMB_QBLOCK_0_USED`:

```c
MAILBOXENTRY( SMB_QBLOCK_0_COIN_VISIBLE, 1805 )   Comment("coin actor visibility, 0=hidden 1=visible")
MAILBOXENTRY( SMB_QBLOCK_0_COIN_PHASE,   1806 )   Comment("coin animation phase, 0=idle, 1..30=animating")
```

Plus the per-actor `Z_POS` write goes via the existing `INDEXOF_Z_POS` (mailbox 3011) + qbert's `write-actor-mailbox` Forth word.

### Mario's Forth script — two extensions

**1. Bump block kicks off the coin animation** (extend the existing bump conditional):

```forth
0 INDEXOF_SMB_QBLOCK_0_NORMAL  write-mailbox
1 INDEXOF_SMB_QBLOCK_0_USED    write-mailbox
1 INDEXOF_SMB_QBLOCK_0_COIN_VISIBLE write-mailbox    \ NEW
1 INDEXOF_SMB_QBLOCK_0_COIN_PHASE   write-mailbox    \ NEW
```

**2. Per-tick coin animation step** (new block at end of Mario's script):

```forth
\ If COIN_PHASE > 0, advance the animation.
INDEXOF_SMB_QBLOCK_0_COIN_PHASE read-mailbox 0<> if
  INDEXOF_SMB_QBLOCK_0_COIN_PHASE read-mailbox
  dup 30 > if
    \ End: hide coin, clear phase
    drop
    0 INDEXOF_SMB_QBLOCK_0_COIN_VISIBLE write-mailbox
    0 INDEXOF_SMB_QBLOCK_0_COIN_PHASE   write-mailbox
  else
    \ Z arc: piecewise linear (rise 1..15, fall 16..30)
    \ z = block_top + offset(phase)
    \ offset = phase * 0.1 for phase ≤ 15 (peak +1.5 m at phase=15)
    \ offset = (30 - phase) * 0.1 for phase > 15
    dup 15 <= if
      0.1 *                            \ phase * 0.1
    else
      30 swap - 0.1 *                  \ (30 - phase) * 0.1
    then
    7.5 +                              \ block_top + offset
    INDEXOF_Z_POS COIN_ACTOR_IDX write-actor-mailbox
    \ Advance phase
    INDEXOF_SMB_QBLOCK_0_COIN_PHASE read-mailbox 1 + 
    INDEXOF_SMB_QBLOCK_0_COIN_PHASE write-mailbox
  then
then
```

`COIN_ACTOR_IDX` is the coin actor's runtime index — hardcoded after a rebuild + `--debug-print-actors` lookup, same convention as Mario hardcoded `9` in earlier scripts. Currently the level has 20 actors after f4071a3 + ced8341; adding the coin makes it 21, with the coin likely at idx 14 (right after `qblock_00_used` at idx 13). Verify post-build.

### Coin mesh authoring (Blender)

In [blender_create_smb.py](../../wflevels/smb_w1_1/blender_create_smb.py), after the `qblock_00_used` add-statplat call:

```python
if i == 0:
    ...existing used-block...
    # Coin actor: small yellow disc, anchored, initially invisible. Stacked
    # at block 0's TOP position (z = block_top); Mario's Forth script
    # animates Z up + back down within a 30-tick visible window.
    coin_z = BLOCK_Z + BSIZE   # block top
    coin = add_statplat(f'qblock_{i:02d}_coin',
                        bx - 0.3, -0.08, coin_z - 0.04,
                        bx + 0.3,  0.08, coin_z + 0.04,
                        mat_coin)
    coin['wf_Visibility Mailbox'] = MB_SMB_QBLOCK_0_COIN_VISIBLE
```

Plus a new `mat_coin = make_mat('smb_coin', (1.0, 0.84, 0.0))` for SMB-coin yellow.

## Phases

1. **mailbox.inc** — add `SMB_QBLOCK_0_COIN_VISIBLE` (1805) + `SMB_QBLOCK_0_COIN_PHASE` (1806).
2. **Blender script** — coin material, coin actor, extend Mario's Forth script with the two blocks above (kickoff + per-tick step).
3. **Rebuild engine** (mailbox.inc changes need the constants compiled into zForth boot table).
4. **Rebuild level** (Blender → `build_level_binary.sh`).
5. **Verify** — bridge state-injection: `set_mailbox SMB_QBLOCK_0_COIN_PHASE = 1` and watch the coin Z over a few seconds. (Same workaround as f4071a3 because engine-throttled jumps still don't reach the block top.)
6. **Commit** — one commit.

## Out of scope (separate plans)

- `+200` score popup label (mirror qbert popup pattern)
- Coin pickup sound (miniaudio integration; headless wire-up)
- Generalising the visibility-flip + coin pop to blocks 1 + 2
- Generalising the hit-event handler to enemy stomps (Goomba squash)

## Critical files

- [wfsource/source/mailbox/mailbox.inc](../../wfsource/source/mailbox/mailbox.inc) — 2 new GLOBAL_USER entries.
- [wflevels/smb_w1_1/blender_create_smb.py](../../wflevels/smb_w1_1/blender_create_smb.py) — coin actor + material + Mario script extension.

## Verification

- `engine/build_game.sh` succeeds (mailbox constants compiled in).
- Bridge `set_mailbox SMB_QBLOCK_0_COIN_PHASE = 1` triggers the visible coin appearing at block top, rising, falling, disappearing within ~30 ticks.
- `~/tmp/smb-shots/coin_*.png` screenshots show the arc.
- After a real bump (interactive or focused-window play), the coin appears as part of the visibility-flip sequence.
