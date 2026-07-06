# Investigation: WF camera system — projection type, FOV, CamShot, Director

**Date:** 2026-04-29
**Motivation:** Party-games platform plan asks whether a forced-perspective / isometric camera is possible, or whether the engine is perspective-only.

---

## Verdict

**Perspective-only. No orthographic path exists.** For an isometric or forced-perspective look, the workaround is a CamShot placed far back with a narrow FOV — visually indistinguishable from ortho at typical marble-game working scale. However, **per-camera FOV is not currently applied** (see below), so even that workaround requires a one-line fix first.

---

## Projection pipeline

`backend_modern.cc` has exactly one projection function:

```cpp
static void Mat4Perspective(float fovDegY, float aspect, float nz, float fz, float out[16])
{
    const float f = 1.0f / std::tan((fovDegY * 0.5f) * (3.14159265358979323846f / 180.0f));
    // standard perspective matrix — no orthographic path
}
```

No `Mat4Ortho` or equivalent exists. Orthographic would require adding one and routing it through `RendererBackend::SetProjection`.

The global default projection is set at display init (`gfx/gl/display.cc:105`):

```cpp
RendererBackendGet().SetProjection(60.0f, fAspect, 1.0f, 1000.0f);
```

---

## Per-camera FOV and clipping planes: stored but not applied

`CamShot` OAS stores FOV (range 1–180°, default 50), Hither, and Yon. These are read into a `cameraPosition` struct in `movecam.cc`:

```cpp
outPos.field  = shotData->GetFOV();
outPos.hither = shotData->GetHither();
outPos.yon    = shotData->GetYon();
```

And `cameraPosition` carries them:

```cpp
struct cameraPosition {
    Vector3 position;
    Vector3 direction;
    Vector3 up;
    Scalar  field;   // FOV
    Scalar  hither;
    Scalar  yon;
};
```

But `SetCamera()` never passes them to `RendererBackend::SetProjection()`. There is even an unresolved pragma in `movecam.cc:184`:

```cpp
#pragma message ("KTS: write field of view, hither and yon code")
```

This is Kevin T. Seghetti — the same engineer whose Jan/May 2003 commits introduced `dynamic_cast`. He left himself a TODO that was never resolved. All cameras currently render at the global 60° FOV regardless of what CamShot specifies.

**Fix is trivial:** in `NormalCameraHandler` (and `PanCameraHandler`, which already interpolates the values correctly), call `RendererBackendGet().SetProjection(camPos.field, aspect, camPos.hither, camPos.yon)` after applying the view matrix.

---

## Camera switching (fully functional)

The `ActBoxOR` → mailbox → `CameraHandler` chain works:

1. Player enters an `ActBoxOR` zone → it writes a CamShot actor index to `EMAILBOX_CAMSHOT`
2. `NormalCameraHandler` reads that mailbox each tick and updates the active shot
3. `PanCameraHandler` interpolates position, FOV, Hither, and Yon between shots during transitions (the interpolation code is correct; the problem is only that the result never reaches `SetProjection`)

---

## Director class

`wfsource/source/game/director.cc` is effectively empty — it inherits from `Actor` but has no active camera logic. Not load-bearing for any current level.

---

## CamBoxOR

`ActBoxOR` (`actboxor.cc`) detects overlap with the player and writes an object reference to a mailbox. It is the standard mechanism for triggering camera switches as the player moves through a level. Fully functional.

---

## Summary table

| Capability | Status | Notes |
|---|---|---|
| Perspective projection | ✅ works | Only projection type |
| Orthographic projection | ❌ not implemented | No `Mat4Ortho`; would need ~20 lines |
| Per-camera FOV | ⚠️ stored, not applied | `#pragma message (KTS)` since ~2003 |
| Per-camera clipping planes | ⚠️ stored, not applied | Same fix as FOV |
| Camera zone switching (ActBoxOR) | ✅ works | Mailbox-driven |
| Smooth pan transitions | ✅ works | `PanCameraHandler` interpolates correctly |
| Director | ➖ empty | No active role |

---

## For the party-games isometric look

Two options in increasing effort:

**Option A — long-focal-length perspective (no engine change needed once FOV fix lands):**
Place the CamShot far above and behind the marble with FOV ≈ 15–25°. At marble working scale this is visually indistinguishable from ortho. Requires the one-line FOV fix above.

**Option B — true orthographic (engine change):**
Add `Mat4Ortho(left, right, bottom, top, nz, fz)` to `backend_modern.cc`, route it through a new `SetProjectionOrtho()` call on `RendererBackend`, add a projection-type flag to `CamShot` OAS, and honour it in `NormalCameraHandler`. Roughly 2–3 hours including OAD schema change (which requires level-pipeline-proof Phase E to land first).

Option A is the right call for the marble game.
