# Fix SMB scrolling camera bugs surfaced by Pass 1 video

**Status:** DONE 2026-05-18 (commits `e3308a2d`, `0723fd1c`) — camera tracks Player; coin arc re-tune; walkthrough harness despawns enemies.

## Context

Pass 1 of the validation plan (scripted walk-through capture) ran cleanly and produced [`tests/screenshots/smb_scroll_walkthrough.mp4`](../../WorldFoundry.2026-new-level/tests/screenshots/smb_scroll_walkthrough.mp4) (583 KB, 104.9 s, 30 fps). Visual review of extracted frames at t=3, 15, 30, 50, 70, 90, 100 s revealed three problems the still-shot panel missed:

1. **B1 — camera skew (proven from code).** Platform recedes from lower-left to upper-right in every frame. Root cause: in [`wflevels/smb_w1_1/blender_create_smb.py:641`](../../WorldFoundry.2026-new-level/wflevels/smb_w1_1/blender_create_smb.py), the CamShot's `wf_Track Object = 'Target02'`, and Target02 is set once at world position `LOOKAT_POS = (MARIO_SPAWN_X, 0, MARIO_Z)` and never updates. As the Forth script scrolls the camera right via `INDEXOF_X_POS`, the look-at direction at [`movecam.cc:301`](../../WorldFoundry.2026-new-level/wfsource/source/game/movecam.cc) (`outPos.direction = targetPos - camShotPos`) pivots back toward the static spawn — that's the yaw skew.

2. **B2 — Mario drifts off the right edge.** At t=3 s Mario is roughly centred; by t=15 s he's hugging the right edge; from t=50 s onward he's gone entirely. The Director math `TARGET = max(9, min(58.5, PLAYER_X))` should keep him centred, so something in the mailbox chain (`PLAYER_X` broadcast → Director → `TARGET_CAM_X` → CamShot `INDEXOF_X_POS`) is not firing as designed. Without per-frame mailbox values we can only hypothesise. **Sequenced approach (user-chosen):** fix B1 first; B1 makes the look-at follow Mario directly, so even if camera X lags, Mario stays in frame — that may show B2 was an artefact of B1 rather than a separate bug. Diagnose B2 only if it survives the B1 fix.

3. **B3 — Mario dies on the Goomba ~t=30 s.** Engine log has 205 `guard doing damage` lines. Goomba at `GOOMBA_X = 22*T = 33`; Mario reaches him at t≈32 s at observed ~0.9 m/s walk speed. Frames after t=30 s show no Mario — he despawned. The camera keeps scrolling but the test loses its subject.

## Approach

### Fix B1 — change CamShot Track Object to Player

One-line edit at [`wflevels/smb_w1_1/blender_create_smb.py:641`](../../WorldFoundry.2026-new-level/wflevels/smb_w1_1/blender_create_smb.py):

```python
# before:
camshot['wf_Track Object'] = 'Target02'
# after:
camshot['wf_Track Object'] = 'Player'
```

**Why this is safe**: Position X/Y/Z are all `'Absolute'`, which maps to `shotData->Position* == 0` at [`movecam.cc:235-248`](../../WorldFoundry.2026-new-level/wfsource/source/game/movecam.cc). At [`movecam.cc:371-376`](../../WorldFoundry.2026-new-level/wfsource/source/game/movecam.cc), the Track Object's position is **only added in Relative mode** (`if (shotData->PositionX) outPos.position.SetX(... + trackObjectPosition.X())`). So changing Track Object to Player affects **look-at direction only** — camera X stays driven by the script-written `INDEXOF_X_POS`.

`wf_Follow` stays `'Target02'`; Follow is required (assert at `movecam.cc:223`) but only enters the position math when in Relative mode (line 232's `relative = camShotPos - followVect` is unused in Absolute mode).

Pattern already used in other levels: [`marble-madness/blender_mm_*.py`](../../WorldFoundry.2026-new-level/wflevels/marble-madness/) all use `Track Object='Player'`; qbert_practice uses it for its death cam (`blender_create_qbert.py:919`).

**Alternative considered (rejected for SMB):** keep `Track Object='Target02'` but make Target02 *follow* the player (via a per-frame Forth update writing player.x to Target02's X mailbox, or via Blender parenting). That introduces an indirection layer worth its weight only when the look-at needs to differ from the player's exact position — e.g. a look-ahead lead during sprint, a peek at an objective marker, a cutscene pan, a death-pit zoom. SMB classic scroll has none of those needs, so the simpler `Track Object='Player'` wins. Captured as durable design guidance for future camera setups.

After the edit: re-export the level (Blender → `build_level_binary.sh smb_w1_1` → `iffcomp standalone` per [`feedback_qbert_blender_build_pipeline`](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_qbert_blender_build_pipeline.md)).

### Fix B3 — despawn the Goomba at test start

The `ALIVE` mailbox at [`mailbox.inc:67`](../../WorldFoundry.2026-new-level/wfsource/source/mailbox/mailbox.inc) is a per-actor local at slot 3004 — comment: *"if cleared object will kill self"*. Write 0 to that slot for the Goomba's actor index right after bridge connect.

Modify [`tests/verify_smb_walkthrough.py`](../../WorldFoundry.2026-new-level/tests/verify_smb_walkthrough.py):

1. After `cli = BridgeClient(...)`, discover the Goomba's actor index. Pattern from [`tests/verify_smb_scroll.py`](../../WorldFoundry.2026-new-level/tests/verify_smb_scroll.py) — likely `cli.list_actors()` or similar; if no such method, fall back to a hard-coded idx from the level's actor order (need to check `BridgeClient` API first).
2. Call `cli.set_mailbox(3004, 0, idx=goomba_idx)`.
3. **Verify the kill actually worked** (the user's "make sure it actually works!" hint):
   - Count `guard doing damage` lines in `tests/.smb_walkthrough.log` after the run. Expected: 0. If non-zero, the despawn didn't take effect (wrong idx, wrong slot, timing issue) and the plan needs a follow-up.
   - Print the count from the test script at the end so it's visible without manually grepping the log.

### Re-record + review

Run `python3 tests/verify_smb_walkthrough.py` again. Replace [`tests/screenshots/smb_scroll_walkthrough.mp4`](../../WorldFoundry.2026-new-level/tests/screenshots/smb_scroll_walkthrough.mp4) and the extracted frames under [`tests/screenshots/smb_walkthrough_frames/`](../../WorldFoundry.2026-new-level/tests/screenshots/smb_walkthrough_frames/). Sample frames at the same timestamps (t=3, 15, 30, 50, 70, 90, 100 s) for direct visual comparison.

**Decision matrix:**
- **Both B1 and B2 visually resolved** → mark SMB camera as shipped per [`feedback_wf_status_rolling_summary`](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_wf_status_rolling_summary.md) and [`feedback_wf_status_paragraph_length`](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_wf_status_paragraph_length.md).
- **B1 fixed, B2 still visible** → write follow-up plan: instrument `verify_smb_walkthrough.py` with `cli.watch(player_idx, 3009)` (X_POS), `cli.watch(0, 1800)` (SMB_PLAYER_X), `cli.watch(0, 1801)` (SMB_TARGET_CAM_X), `cli.watch(camshot_idx, 3009)`, log values every ~30 frames during the walk. The pattern of values pinpoints which chain link is broken.
- **B3 not actually fixed (guard-damage count > 0)** → diagnose: wrong idx, slot, or `ALIVE` doesn't despawn the way the comment claims.

## Critical files

| Path | Why |
|------|-----|
| [`wflevels/smb_w1_1/blender_create_smb.py:641`](../../WorldFoundry.2026-new-level/wflevels/smb_w1_1/blender_create_smb.py) | Single source-line change for B1. |
| [`tests/verify_smb_walkthrough.py`](../../WorldFoundry.2026-new-level/tests/verify_smb_walkthrough.py) | Add Goomba despawn + verification of the despawn. |
| [`tests/debug_bridge_client.py`](../../WorldFoundry.2026-new-level/tests/debug_bridge_client.py) | Reference for `set_mailbox(slot, value, idx)` and actor-index discovery API. |
| [`wfsource/source/mailbox/mailbox.inc:67`](../../WorldFoundry.2026-new-level/wfsource/source/mailbox/mailbox.inc) | `ALIVE` mailbox = slot 3004. |
| [`wfsource/source/game/movecam.cc:208-376`](../../WorldFoundry.2026-new-level/wfsource/source/game/movecam.cc) | Reference: why Track Object change is position-safe in Absolute mode. |
| [`docs/plans/2026-05-17-smb-scrolling-camera.md`](../../WorldFoundry.2026-new-level/docs/plans/2026-05-17-smb-scrolling-camera.md) | Existing SMB camera plan — update once the fix lands (note the Track Object change + B2 resolution status). |

## Verification

1. **B1 fix landed**: re-exported `wflevels/smb_w1_1-standalone.iff` differs from current; `blender_create_smb.py:641` shows `'Player'`.
2. **B3 fix landed**: `verify_smb_walkthrough.py` ends with a printed line like `goomba damage events: 0 (expected 0)`. Non-zero = plan failed; investigate before re-recording is meaningful.
3. **Visual review of re-recorded video**:
   - Platform renders horizontal (no diagonal recede) when camera is anywhere on the scroll range.
   - Mario visible in every sampled frame across the walk (no off-screen, no despawn).
   - Mario reaches the flagpole area (X ≥ 58.5; camera clamped at right edge) before script ends.

## Notes

- No engine rebuild needed for B1 — it's a level-source change picked up at level load.
- No engine rebuild needed for B3 — `ALIVE` mailbox already wired (see comment in `mailbox.inc:67`).
- Per [`feedback_qbert_blender_build_pipeline`](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_qbert_blender_build_pipeline.md), I run the level rebuild steps after the .py edit.
- Goomba despawn is **test-only** — the .py source remains unchanged; the level still has a Goomba when played normally.
- If B1 + B3 fix both work and the result still shows judder or other artefacts not predicted by the existing investigation, that's a sign to consider unparking the Route B engine-side plan at [`docs/plans/2026-05-17-smb-scroll-engine-route.md`](../../WorldFoundry.2026-new-level/docs/plans/2026-05-17-smb-scroll-engine-route.md).
