# Plan — Red Ball subdued stretch-and-squash

**Date:** 2026-05-11
**Status:** Done (2026-05-11, commit `15705d1`)
**Phase B baseline:** commits `ba8d606` (multi-ball + spawning + arc-Z) + `35ee402` (80-face mesh).

## Context

Phase B's red balls hop on a smoothstep XY lerp + parabolic Z arc, but the mesh stays at scale (1, 1, 1) throughout. Q*bert's player has a stretch-and-squash deformation across each hop ([blender_create_qbert.py:624-648](../../wflevels/qbert_practice/blender_create_qbert.py)) which sells the "alive, springy" feel; the balls currently look rigid by comparison. The user wants the same idiom applied to the ball but **at a reduced amplitude — more subdued than the player**, since the ball should read as a bouncing object rather than a character.

Concrete goal: per hop, the ball compresses at takeoff, stretches mid-air, compresses at landing, snaps back to unit scale on the landing frame — mirroring the player but with half the deformation magnitude.

## Approach

### Reuse the player's formula

The player at [blender_create_qbert.py:639-647](../../wflevels/qbert_practice/blender_create_qbert.py) computes scale from the linear hop progress `t ∈ [0, 1]`:

- `bell = 4*t*(1-t)`     — peaks at mid-air (t=0.5)
- `imp  = (2t-1)²`        — peaks at takeoff (t=0) and landing (t=1)
- `z_scale  = 1 + 0.20*bell − 0.40*imp`
- `xy_scale = 1 − 0.10*bell + 0.40*imp`

For the ball, halve all coefficients and expose them as a Python constant so we can re-tune:

```python
REDBALL_SS_STRENGTH = 0.5    # 0.0 = no deformation, 1.0 = player-strength

REDBALL_SS_Z_BELL  =  0.20 * REDBALL_SS_STRENGTH   # 0.10
REDBALL_SS_Z_IMP   =  0.40 * REDBALL_SS_STRENGTH   # 0.20
REDBALL_SS_XY_BELL = -0.10 * REDBALL_SS_STRENGTH   # -0.05  (note: XY narrows at t=0.5)
REDBALL_SS_XY_IMP  =  0.40 * REDBALL_SS_STRENGTH   # 0.20
```

Resulting deformation:

| Phase | t | bell | imp | z_scale | xy_scale | Visual |
|---|---|---|---|---|---|---|
| Takeoff | 0.0 | 0.0 | 1.0 | 0.80 | 1.20 | mild crouch |
| Apex | 0.5 | 1.0 | 0.0 | 1.10 | 0.95 | gentle stretch |
| Landing | 1.0 | 0.0 | 1.0 | 0.80 | 1.20 | mild squash |
| Snap | 1.0 (cd=0) | — | — | 1.00 | 1.00 | identity |

Compare to player at strength 1.0: takeoff z=0.6 / xy=1.4 (extreme crouch). Ball at 0.5 strength is visibly springy without being cartoony.

### Per-ball script changes

In `redball_script(K)` in [blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) (current Phase B body ~lines 870-960), add a Forth block after the Z position write and before the contact check:

```forth
\\ Stretch-and-squash. Mailboxes 3040/3041/3042 = X/Y/Z_SCALE.
\\ Snap to identity on landing tick (cd <= 0); otherwise compute from t_raw.
{mb_cd} read-mailbox 0 <= if
  1.0 3040 write-mailbox 1.0 3041 write-mailbox 1.0 3042 write-mailbox
else
  \\ Recompute t_raw = (HOP_TICKS - cd_new) / DENOM.
  {HOP_TICKS} {mb_cd} read-mailbox - {DENOM} /                    ( t_raw )
  \\ imp = (2t-1)², bell = 4*t*(1-t).
  dup 2.0 * 1.0 - dup *                                            ( t imp )
  swap dup 1.0 swap - 4.0 * *                                      ( imp bell )
  \\ Z_SCALE = 1 + Z_BELL*bell + Z_IMP*imp     (Z_IMP is negative in code)
  over {Z_IMP} * over {Z_BELL} * + 1.0 + 3042 write-mailbox        ( imp bell )
  \\ XY_SCALE = 1 + XY_IMP*imp + XY_BELL*bell  (XY_BELL is negative, narrows at peak)
  {XY_BELL} * swap {XY_IMP} * + 1.0 +                              ( xy_scale )
  dup 3040 write-mailbox 3041 write-mailbox
then
```

(Pass the Python constants in as numeric literals so they bake into the Forth — same pattern as `_RB_X_MUL`.)

Sign convention: player uses `over 0.40 * over 0.20 * swap - 1.0 +` which is `1 + 0.20*bell - 0.40*imp`. I use signed coefficients so the same `+` works for both stretch and squash directions — slightly less terse than player's hand-coded sign juggle, but easier to re-tune.

### Director changes — none required

The activation block already implicitly leaves scale at whatever the previous owner of the actor's scale slot wrote, which on a clean wake is the "snap to 1.0" from the previous retire. Adding 1.0 writes to scale in the activation is **not needed** but **also not harmful** — if it turns out a freshly-spawned actor ever has uninitialised scale, we can add 3 writes to the activation cascade. Default plan: do not add, verify it's fine.

### Retire branch

The off-pyramid retire branch runs through the same `cd <= 0` snap-to-1.0 path described above (the new S&S block runs before the existing retire/next-hop logic), so the ball parks at unit scale. No special handling needed in the retire block itself.

## Mailbox usage

No new mailboxes. Reuses the per-actor system slots already wired by the engine:
- mb 3040 = X_SCALE
- mb 3041 = Y_SCALE
- mb 3042 = Z_SCALE

## Critical files

| File | Change |
|---|---|
| [`wflevels/qbert_practice/blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py) | Add `REDBALL_SS_STRENGTH` + 4 derived coefficients near `REDBALL_HOP_TICKS` constants. Append S&S Forth block to `redball_script(k)` after the Z write, before the contact check. |
| (no engine changes) | EMAILBOX_X/Y/Z_SCALE handlers exist on `RenderActor3D` (per [actor.cc:1482-1499](../../wfsource/source/game/actor.cc), the same path the player uses for its S&S). |

## Verification

1. **Build:** `blender --background … --python blender_create_qbert.py && bash wftools/wf_blender/build_level_binary.sh qbert_practice`. Clean exit.
2. **Engine boot:** `task run-level -- wflevels/qbert_practice-standalone.iff`. No FATAL / Validate / abort.
3. **Visual via record_video:** capture 30 s. During each ball's hop, expect a visible "compress on takeoff → stretch mid-air → compress on landing → snap to round" cycle, but milder than the player's deformation. Ball should not look static (Phase B baseline) nor over-squashed (player-strength).
4. **Debug-bridge probe:** watch ball-0 mailboxes 3040/3041/3042 across one hop (18 ticks). Expect:
   - At cd=17 (~t=0.06): z≈0.83, xy≈1.17 (early crouch)
   - At cd=10 (~t=0.47): z≈1.10, xy≈0.95 (near-peak stretch)
   - At cd=2 (~t=0.94): z≈0.81, xy≈1.18 (pre-landing squash)
   - At cd=0 (landing): z=xy=1.00 (snap)
5. **Player regression:** confirm the player's S&S is unchanged (its block is untouched).
6. **Idle balls:** force a ball into PHASE 0 mid-hop; verify it parks at Z=-30 and scale stays at the last computed value (no visual artefact because it's off-screen). When director wakes it, the first hopping tick will overwrite scale to the early-crouch value, so it pops in with proper anticipation.

## Out of scope

- Per-round S&S intensity scaling (could grow with ROUND_NUMBER for "more frantic" later rounds) — defer.
- Squash amplitude per enemy type — Green Ball / Coily will have their own plans.
- Rotation-during-hop (additional rolling effect for a ball) — separate follow-up.
