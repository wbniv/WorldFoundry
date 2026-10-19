# Camera stale-/destroyed-track crash (closes TODO 134 + 135)

## Context

Two TODO bugs were the **same** bug:
- **134** "debug-bridge resume → dt-spike → out-of-range actor lookup → assert (`idxObject = 31158`)".
- **135** "camera track-object leaving the room → heap-use-after-free + `ValidPtr` assert".

134's dt premise is **debunked**: `deltaTime` is already clamped to ≤100 ms at three
layers — `Display::MeasureDelta` (200 ms), `WFGame::StepFrame` (100 ms, `game.cc:700`),
and `Level::update` itself (100 ms, `level.cc:816`, since the **2010** first commit) — and
`RunLevel` routes through `StepFrame`. So a >100 ms dt cannot reach actor movement; the
`idxObject = 31158` assert came from a **stale camera track index**, not a fling.

**Root cause:** the camera resolves a tracked-actor *index* (`cd.idxTrackObject`, an
`int32` from a CamShot mailbox or static shot field) and asserts/UAFs when it's invalid,
in two per-frame places:
1. `SetCameraParametersFromShot` (`movecam.cc`, every frame from `_update`/Pan):
   `getActor(idxTrackObject); assert(ValidPtr(trackObject))` — the primary crash for a
   *permanently* destroyed tracked actor.
2. the three `GetWatchObject` handlers (`Normal`/`Pan`/`Bungee`): `GetObject(idxTrackObject)`
   (asserts on out-of-range), else `return theLevel->mainCharacter()` — special-casing
   the main character.

`idxTrackObject` is never invalidated on despawn; a freed slot is nulled but **reused**
(`AddObject` `level.cc:1303`), and there is **no actor identity/generation**.

## Fix

A shared, non-asserting resolver (user-chosen semantics: null on no-match, caller decides,
no `mainCharacter()` dependence):
```cpp
// movecam.hp — public static on CameraHandler
static const PhysicalObject* CameraHandler::ResolveTrackObject(int32 idxTrackObject);
//   idx<=0 | idx>=GetMaxObjectIndex() (bounds-check before GetObject's RangeCheck)
//   | empty/freed slot | !IsPhysicalObject  → nullptr ; else the PhysicalObject*
```
- **`GetWatchObject` ×3** → `return ResolveTrackObject(cd.idxTrackObject);` — `mainCharacter()`
  fallback deleted. The sole caller (`level.cc:949`, `if (_camera && _camera->GetWatchObject())
  UpdateRoom(...)`) already null-skips, so null degrades to "active rooms hold this frame."
- **`SetCameraParametersFromShot`** → resolve via `ResolveTrackObject`; if gone, drop the
  track (`idx→0`) and use a zero track offset + skip rotation-tracking, so the camera
  degrades to its Follow-relative shot position (always a valid `destCam` — **no caller
  rewiring**, no sentinel/hold threading). Returning `idx==0` makes `GetWatchObject` null too.

**Known limit (filed as a follow-up):** an index isn't an identity and slots are reused, so
a *recycled* slot still aliases the new occupant. Full cure = actor generation-IDs / safe
handles (engine-wide) — see the new TODO item.

## Files
`wfsource/source/game/movecam.{hp,cc}` (resolver + 3 `GetWatchObject` + `SetCameraParametersFromShot`),
`engine/mutation/wfmut_smoke.cpp` (C1–C6 regression), `tests/verify_wfmut_bridge.py` +
`tests/verify_smb_w1_3_enemies.py` (corrected mis-blame comments), `TODO.md`.

Separate commit: dedup the inline `SCALAR_CONSTANT(0.1)` into one `kMaxSimDeltaSeconds`
(`game.cc:700` + `level.cc:816`; `Level::update` stays authoritative) — non-behavioral.

## Verification (executed)

1. **Build** `wf_game` (build-editor, `WF_ENABLE_EDITOR=ON` gates the smoke) — clean
   (`movecam.cc` net −58; handlers shrank).
2. **Test bites:** with `ResolveTrackObject`'s bounds-check temporarily removed, the smoke
   **aborts at C3** with the exact reported assert:
   ```
   --- Camera track resolve (C1-C6) ---
     [PASS] C1: ResolveTrackObject(0) == null (unset)
     [PASS] C2: ResolveTrackObject(-1) == null (negative)
   AssertMsg:idxObject = 31158, _actors.Size() = 331    (level.cc:1752 RangeCheck)
   ```
   wf_game exit 255; never reached the summary.
3. **Passes after** (bounds-check restored):
   ```
   --- Camera track resolve (C1-C6) ---
     [PASS] C1..C6   (incl. C3 idx 31158 → null, C5 player → that actor, C6 empty slot → null)
   ```
   `task test-wfmut` / `wf_game -L … --wfmut-smoke`: the camera group is green (the only
   remaining failure, `SR0` spawn-test, is pre-existing and unrelated to this change).
4. **Manual (optional):** drop a CamShot's tracked actor out of all rooms / despawn it
   (SMB W1-3 pit-fall) and step — the camera holds at its shot position, room-update skips,
   no abort (previously asserted). The `6479ebbe` terminate handler would name the cause if
   it ever did fire.

## Out of scope
- The dt clamp (already correct ×3) — only the constant dedup (separate commit).
- `DelayCameraHandler` (no track index).
- Actor generation-IDs / safe handles for slot-reuse aliasing — separate follow-up TODO.
