# SMB scrolling camera — engine-side route (parked)

**Status:** Parked 2026-05-17. We will implement this; not right now.

**Trigger to unpark:** After a new level ships. The in-progress SMB W1-1 (or whichever level next reaches shipped state) is the gate — once at least one level is out the door using the pure-Forth route, we come back to this plan and migrate to the engine-side design.

**Active plan instead:** Pure-Forth Director-driven SMB scroll — the Director script + CamShot signal-mailbox pattern. See the active plan doc (currently in the harness at `~/.claude/plans/implement-the-fixed-scrolling-camera-velvety-nova.md`; will be promoted to `docs/plans/2026-05-17-smb-scrolling-camera.md` when implementation starts).

---

## Context

`wflevels/smb_w1_1/blender_create_smb.py` (lines 11, 17) currently configures a **fixed all-Absolute** CamShot centred on Mario's spawn (X=4.5). The level extends to X≈70.5; Mario walks off-screen past ~X=15. The script's header explicitly flags scrolling as a deferred milestone.

Target behaviour (classic NES SMB):
- Horizontal scroll only (Y and Z locked).
- **Deadzone** — small horizontal window inside which Mario can move without scrolling.
- **One-way scroll** — once camera has advanced right, it never retreats.
- **Level-edge clamp** — camera X clamped so the frustum never shows void past `[ground_X0, ground_X1]`.
- **Forward lead ≈ 1 tile (T = 1.5 m)** — Mario sits left of centre when scrolling.

This plan describes the engine-side implementation route. The complementary pure-Forth route (zero engine code, all logic in the Director script) is the one being implemented first; this plan exists so the engine route is fully designed when we come back to it.

OAS schema additions are explicitly authorised for this work.

---

## Approach: per-CamShot OAS fields + inline branch in `NormalCameraHandler::_update`

No new C++ class. The existing `NormalCameraHandler` reads the active CamShot's new fields and adjusts its per-tick behaviour. Per-CamShot configurable from Blender's property editor; level designers tune SMB scroll without touching Forth.

### 1. New OAS fields on `camshot.oas`

A fresh `Mode: SMB Scroll` group, alongside the existing `Mode: Switching Camshots` (line 41) and `Mode: Tracking` (line 44) groups. The commented-out `XSlew/YSlew/ZSlew` stubs at lines 45-47 are precedent — Phil planned per-CamShot tracking-mode fields but never finished wiring them; this group fills in the same slot for SMB scroll behaviour.

```
GROUP_START(Mode: SMB Scroll,256)
TYPEENTRYBOOLEANTOGGLE(SMB Scroll X,, 0,, "Off|On")              // master toggle
TYPEENTRYFIXED32(Deadzone Half Width,, FIXED32(0), FIXED32(50), FIXED32(1.5))
TYPEENTRYFIXED32(Forward Lead,,        FIXED32(-50), FIXED32(50), FIXED32(1.5))
TYPEENTRYFIXED32(Scroll Min X,,        FIXED32(-10000), FIXED32(10000), FIXED32(0))
TYPEENTRYFIXED32(Scroll Max X,,        FIXED32(-10000), FIXED32(10000), FIXED32(0))
TYPEENTRYBOOLEANTOGGLE(One Way Scroll,, 1,, "Off|On")             // SMB-faithful ratchet
GROUP_STOP()
```

Six fields. `SMB Scroll X` off → existing behaviour, fully backwards-compatible with shipped levels (snowgoons, qbert_practice, mm_practice). `Scroll Min X == Scroll Max X` disables the edge clamp (useful for testing the deadzone alone).

### 2. `cameraData` struct extension (`movecam.hp:52-63`)

Two new transient state members:

```cpp
Scalar maxCameraX;      // one-way ratchet state
bool   smbInitialised;  // lazy-init flag for maxCameraX seed
```

The struct is shared across all camera handlers; ~5 extra bytes per CamShot are negligible. Already holds analogous transient state (`oldCameraPosition`, `idxOldCamShotActor`).

### 3. Branch in `NormalCameraHandler::_update()`

After `SetCameraParametersFromShot()` returns (`movecam.cc:486`), branch on `shotData->SMBScrollX`. When SMB mode is on:

1. On first tick (`!cd.smbInitialised`), seed `cd.maxCameraX = destCam.position.X()` and set the flag.
2. Compute `desired = player_x + shotData->ForwardLead`.
3. Apply deadzone: if `|desired - cd.maxCameraX| < shotData->DeadzoneHalfWidth`, leave `cd.maxCameraX` unchanged.
4. Apply one-way ratchet (if `shotData->OneWayScroll`): `target = max(desired, cd.maxCameraX)`.
5. Apply edge clamp (if `ScrollMinX != ScrollMaxX`): `target = clamp(target, ScrollMinX + halfFrustumX, ScrollMaxX - halfFrustumX)` where `halfFrustumX` is computed from the CamShot's FOV and Y-depth.
6. Update `cd.maxCameraX = target`; overwrite `destCam.position.X() = target`.
7. Y and Z come from the existing per-axis Abs/Rel mux unchanged.

The slew clamp at lines 495-511 still runs afterwards. Mario's max ground speed is 6, well under the 10/frame budget, so the slew is dormant in normal play. See [`docs/level-building.md`](../level-building.md) § Per-frame camera slew clamp.

### 4. No new handler class. No `MovementHandlerArray[]` edits.

Earlier drafts of this plan had an `SMBCameraHandler` subclass that needed swapping into the per-mobility singleton at `actor.cc:105-113`. That swap is unnecessary once selection happens per-CamShot via the OAS fields — `NormalCameraHandler` simply reads the active CamShot's `SMBScrollX` field each tick. Multiple CamShots in the same level can independently choose SMB vs. non-SMB.

---

## Files to change

| File | Edit |
|------|------|
| `wfsource/source/oas/camshot.oas` | Add `Mode: SMB Scroll` group with 6 fields. |
| `wfsource/source/game/movecam.hp` | Add `maxCameraX` + `smbInitialised` to `cameraData` struct (lines 52-63). |
| `wfsource/source/game/movecam.cc` | Branch in `NormalCameraHandler::_update()` after line 486 on `shotData->SMBScrollX`. ~40-60 LOC. |
| Generated OAS bindings | The OAS-to-C-struct generator (whatever consumes `camshot.oas` to produce `_CamShot` headers) re-runs as part of `task build`. The new fields appear on `shotData->`. To confirm tool path during implementation. |
| `wflevels/smb_w1_1/blender_create_smb.py` | Set `camshot['wf_SMB Scroll X'] = 'On'`, `wf_Deadzone Half Width = 1.5`, `wf_Forward Lead = 1.5`, `wf_Scroll Min X = -3.0`, `wf_Scroll Max X = 70.5`, `wf_One Way Scroll = 'On'`. Leave `Position X = Absolute` (the SMB code path overwrites X). Set `Follow = player` so `SetCameraParametersFromShot` knows whose X to read. **Remove** the Forth Director script the active plan introduced (the engine now does that work). Update header comment. |

No new `.hp`/`.cc` files. No new mailbox enum values.

---

## Risks / gotchas

1. **OAS field additions need backwards-compat verification.** Existing levels (snowgoons, qbert_practice, mm_practice) have CamShots with the old schema. Adding fields at the end of the property sheet is the standard append pattern in WF and should not break those levels — the [`project_oad_compat_policy`](../../.claude/projects/-home-will-WorldFoundry/memory/project_oad_compat_policy.md) memory confirms "new OAS fields go after existing ones". Verify by re-running each level after the schema change.
2. **Generated `_CamShot` struct.** The fields need to appear on `shotData->` for `_update()` to read them. The OAS file is consumed by some generator (likely Rust-based given the wftools rewrite — confirm path during implementation). If the generator doesn't pick up the new fields automatically, the build will fail with "no member named SMBScrollX" — a fast, loud failure rather than a silent one.
3. **Slew clamp interaction.** Same as the active plan's analysis: Mario's speed 6 < limit 10, doesn't bite. If a future use case needs >10/frame movement, the slew constant in `movecam.cc:495-497` can be raised, or the commented-out per-CamShot slew override fields at `camshot.oas:45-47` can be uncommented and wired up. Documented in [`docs/level-building.md`](../level-building.md) § Per-frame camera slew clamp.
4. **State lives in shared `cameraData`.** If a level has multiple CamShots with `SMB Scroll X` on and the player crosses between them, `maxCameraX` carries over from the first. That's almost certainly the right behaviour (you don't want the screen lurching backwards when transitioning between two adjacent SMB-scroll regions), but worth being explicit about. To reset, write `smbInitialised = false` on CamShot switch — implementable as a one-line addition to the existing `PanCameraHandler` transition.

---

## Migration path from the Forth route

When this plan is unparked, the active SMB level will already be running on the Forth Director. Migration:

1. Add the OAS fields and engine branch first (no level changes yet — `SMB Scroll X` defaults to Off, so behaviour is unchanged).
2. Verify shipped levels still work (snowgoons, qbert, mm_practice, SMB W1-1).
3. Switch SMB W1-1 from the Forth route to the engine route by editing the .blend.py: set the new OAS field values, remove the Director's scroll Forth script, remove the Player's `X_POS` broadcast line (which only existed to feed the Director), drop the `PLAYER_X` / `MAX_CAM_X` / `CAM_INIT` global mailbox usage.
4. Rebuild the level and screenshot-verify identical scroll behaviour.

The Forth route doesn't have to come down all at once — both paths can coexist while the engine route is being validated.

---

## Verification

- [ ] Engine builds — `task build`.
- [ ] OAS regen picks up the new fields — grep generated `_CamShot` struct for `SMBScrollX`.
- [ ] Snowgoons, qbert_practice, mm_practice still run (OAS schema additions need backwards-compat verification per gotcha #1).
- [ ] SMB level builds end-to-end.
- [ ] Four in-game screenshots: spawn framing · scroll-on-advance · no-scroll-on-retreat (one-way) · edge-clamp at flagpole. Compare against the same screenshots from the Forth route for behavioural parity.
- [ ] Commit after each phase ([`feedback_commit_after_each_phase`](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md)). Three commits: OAS schema + struct extension; `_update` branch; level-script migration.

---

## A benefit over the Forth route worth noting

The Forth-route signal chain (Player → global → Director → global → CamShot self-apply) picks up a mandatory 1-tick camera-position lag because of WF's per-tick execution order: producers in the main loop are seen by the Director on the same tick, but Director writes are seen by consumers only on the next tick (verified at [`level.cc:881-888`](../../wfsource/source/game/level.cc), confirmed in [`docs/level-building.md`](../level-building.md) § Per-tick execution order). 16 ms at 60 Hz — invisible for SMB. **This engine-side route is immune to that lag** because all the SMB scroll logic runs inside a single `NormalCameraHandler::_update()` call: it reads the player position (this-tick value via `SetCameraParametersFromShot`) and computes/writes the camera position in the same function in the same main-loop slot. No cross-actor handoff means no scheduling-induced staleness. Not a reason to rush the unpark on its own, but a real quality difference once the lag is being measured rather than just tolerated.

## Related follow-ups

- **Hybrid Room-bbox fallback for `Scroll Min X` / `Scroll Max X`.** When both fields are 0 (unset/default), fall back to the containing Room's bbox; when explicitly set, use those values. Defers the field-duplication concern (Room bbox + Scroll Min/Max both encoding the same level extent in the common case) without giving up the escape hatch for CamShots that want sub-region bounds. Investigate after a second 2D-scroller level exists. Tracked in [`TODO.md`](../../TODO.md) under `CAMERA SYSTEM`.
- **Wire the commented-out per-CamShot slew override.** `camshot.oas:45-47` has `XSlew/YSlew/ZSlew` stubs Phil drafted but never finished. Already documented in [`docs/level-building.md`](../level-building.md) § Per-frame camera slew clamp. Not needed for SMB (Mario speed = 6 < 10/frame).
