# SMB W1-1: enemies dormant until on-screen (faithful), so they stop vanishing into pit 0

**Status:** Done — 2026-05-26. Reveal-latch + repositioned spawns implemented in
`blender_create_smb.py`, level re-exported, verified with
[`tests/verify_smb_enemy_dormant.py`](../../tests/verify_smb_enemy_dormant.py) and the
[`smb_enemy_meet`](../../tests/screenshots/smb_enemy_meet.png) screenshot (Mario meets the
revealed Goomba on ground_1). No engine rebuild (no new mailbox).

## Context

In `smb_w1_1` the Goomba (X=33) and Koopa (X=42) spawn on the inter-pit segment
**ground_1** (X∈[31.5, 51]) and the shared `ENEMY_SCRIPT` forces a constant leftward
walk (`XSPEED = -4` every tick) from frame 0 — so both walk off ground_1's left edge
into **pit 0** (edge X=31.5) within ~0.4 s / ~2.6 s, fall into the inter-room Z gap,
hit "not in any room," and are silently removed. They're gone before the player ever
crosses pit 0 to see them. Logged in TODO.md.

The **real arcade behavior** (confirmed by the user): SMB enemies are **dormant until
they scroll into the visible screen**, then they activate and walk. That's *why* they
don't pre-walk into pits — they don't move at all until revealed. The first plan
(reposition + always-walking) was wrong: not faithful, and timing-fragile. This plan
implements the authentic screen-reveal activation, which inherently fixes the vanish
(a dormant enemy can't walk into a pit).

## Approach

Gate the enemy's walk on a **screen-reveal latch** built from the camera ratchet the
Director already maintains:

- `INDEXOF_SMB_MAX_CAM_X` (mb 1802) is the camera X **one-way ratchet** (monotonically
  increasing, clamped [9, 58.5]) — see the Director script,
  `wflevels/smb_w1_1/blender_create_smb.py:167-180`.
- The camera shows `camX ± 12` (HALF_FRUSTUM = 12.0, per the Director comment at
  `:163-164`). So an enemy has entered the frame from the right exactly when
  `SMB_MAX_CAM_X + 12 ≥ enemyX`. Because the ratchet never decreases, this is a
  **monotonic latch** — once revealed, it stays revealed. **No per-actor state flag
  and no new mailbox needed → no engine rebuild.**

Until revealed the enemy stands still (XSPEED 0); once revealed it does the existing
*dumb* leftward walk (and the existing stomp/hurt proximity), so it can still fall
into pit 0 if Mario leaves it uneaten — faithful "dumb" enemy, just no longer
pre-walking before the player arrives.

### Change 1 — `ENEMY_SCRIPT` in `wflevels/smb_w1_1/blender_create_smb.py` (~line 835)

Wrap the current body in the reveal gate. The existing script forces `-ENEMY_WALK_SPEED`
to `INDEXOF_XSPEED` then runs the player-proximity stomp/hurt block; move all of that
inside the gate, and stand still (write 0) when dormant:

```forth
\ wf
INDEXOF_SMB_MAX_CAM_X read-mailbox 12.0 + INDEXOF_X_POS read-mailbox > if
  -4.0 INDEXOF_XSPEED write-mailbox            ( on-screen: dumb walk left toward Mario )
  ( ...existing dx/dz proximity stomp + hurt block, unchanged... )
else
  0 INDEXOF_XSPEED write-mailbox               ( dormant: stand still until revealed )
then
```

(zForth notes already satisfied: `>` is defined; floats fine; real `\n`; the whole body
is in the auto-wrapped run word so `if/else/then` is legal — see
`docs/level-design-troubleshooting.md`.)

### Change 2 — spawn positions (`GOOMBA_X` / `KOOPA_X`, ~lines 54-55)

Place them on the **right portion of ground_1** so they reveal right as Mario crosses
onto ground_1 and then walk left toward him (rather than revealing at pit 0's edge and
falling straight in):

```python
GOOMBA_X = 29 * T     # was 22*T (33) → 43.5  (reveals ~camX 31.5, i.e. Mario just past pit0)
KOOPA_X  = 32 * T     # was 28*T (42) → 48    (reveals ~camX 36, staggered deeper into ground_1)
```

Both stay inside ground_1 (31.5 < 43.5 < 48 < 51), and well left of the flagpole (63).

## Build

No `mailbox.inc` change → **no engine rebuild**. Level pipeline only:

```
cd wflevels/smb_w1_1 && blender --background --python blender_create_smb.py
cd ../.. && bash wftools/wf_blender/build_level_binary.sh smb_w1_1
```

(Re-export overwrites per-actor `.iff`s; commit the regenerated level artifacts as in
the prior SMB commits.)

## Verification

Bridge-driven (reuse `tests/verify_smb_pipe_warp.py` / `verify_smb_walkthrough.py`
patterns), on `wflevels/smb_w1_1-standalone.iff`; get enemy indices from
`--debug-print-actors`:

1. **Dormant at start:** boot, hold for ~3 s with no input — both enemies' X stays
   constant (they do NOT move or get removed). Confirms the reveal gate.
2. **Activate on reveal:** `resume` + hold RIGHT to walk Mario right and jump pit 0;
   confirm each enemy's X stays put until the camera's right edge (`SMB_MAX_CAM_X`+12)
   reaches it, then starts decreasing (walking left toward Mario). **Screenshot** Mario
   meeting an enemy on ground_1 (both visible, walking toward him).
3. **Still "dumb":** leave one uneaten and confirm it eventually reaches X≈31.5 and
   falls (Z < −10) — the faithful fall is preserved, just no longer pre-emptive.

Then update **TODO.md** (remove the "Goomba walks straight into pit 0" entry — resolved)
and sync the SMB row in **wf-status.md**.
