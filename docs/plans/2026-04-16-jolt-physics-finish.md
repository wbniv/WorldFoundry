# Finish the Jolt Physics integration

Take snowgoons from "frame-1 SIGABRT in `PhysicalAttributes::Validate`" to
"player walks on the floor without falling through for at least a minute."

## Current state

- NaN crash (uninitialized `BodyEntry` Vector3 members) — fixed.
- Double-free at `handle=0` (parameterized ctor didn't init `_joltBodyID`
  before calling `Construct`) — fixed.
- Tempo allocator SIGABRT (2 MB too small) — fixed, bumped to 10 MB.
- Level loads; `OptimizeBroadPhase` reports 33 occupied bodies (15 STATIC
  StatPlats + 18 "zombie" kinematic bodies + character lives in a
  separate registry).
- Frame 0: character `GROUND`, `feet=-0.879`.
- Frame 1: character `feet=2.178` (~3 m Z pop), still `GROUND`. Then
  `SIGABRT` from `PhysicalAttributes::Validate` at the top of frame 2's
  predictPosition.

## Why `Validate` fires

`GroundHandler::predictPosition` (movement.cc:426) writes the Jolt-authored
position back via `actorAttr.SetPredictedPosition(JoltCharacterGetPosition(charID))`.
`SetPredictedPosition` does `_predictedPosition = newPos; _colSpace.Expand(delta); Validate();`.
`ColBox::Expand` is **accumulating**: it extends max if delta>0 on that axis,
min if delta<0, and it's meant to run once per frame with the WF collision
system resetting the colspace afterwards. For Jolt-character actors we skip
the WF collision system entirely (collision.cc:513-519), so the colspace
expansion accumulates frame-over-frame and `Validate` can't reconstruct the
motion delta consistently.

Bottom line: `SetPredictedPosition` was designed for WF's swept-AABB
broadphase and is the wrong API for writing a position that came out of a
separate physics engine that already resolved collisions.

## Plan

Each step is a single logical change. Build + run after each step before
moving on. Don't bundle.

### Step 1 — Split Jolt-character position sync off SetPredictedPosition

**Fixes the SIGABRT.** Everything else stays as-is for now (character will
still pop ~3 m on frame 1), but the Validate assert stops firing and frames
keep running so we can see subsequent telemetry.

Touch:
- `physics/physical.hp` — declare `void JoltSyncFromCharacter(const Vector3&)`
  inside the `#ifdef PHYSICS_ENGINE_JOLT` block near the existing
  `JoltMakeCharacter()` declaration (around line 127).
- `physics/jolt/physical.hpi` — implement it. Sets `_position = newPos`,
  `_predictedPosition = newPos`. Resets colspace to unexpanded. Does NOT
  call `Validate()`.
  - `ColSpace` has no reset method today. If `ColSpace::SetBox(UnExpMin(),
    UnExpMax())` doesn't reset the expanded copy as well, add a
    `ResetExpansion()` method that does
    `_coarseExpandedColBox = _coarseColBox` (or equivalent).
- `movement/movement.cc` lines 426 and ~730 (the `SetPredictedPosition(JoltCharacterGetPosition(...))`
  calls in `GroundHandler::predictPosition` and `AirHandler::predictPosition`)
  — switch to `JoltSyncFromCharacter(...)`.

Check:
- Build clean.
- Run, confirm no `Validate` SIGABRT.
- `jolt: char f000 ... f001 ... f002 ...` lines keep appearing.
- Character likely still pops to `feet≈2.178` on frame 1 — that's Step 4.

### Step 2 — Stop creating zombie kinematic bodies

**Reduces 33 → 16 bodies.** Eliminates the kinematic→static/character
Destroy-then-Create dance in favour of a single explicit create.

Touch:
- `physics/physical.hpi::Construct()` (lines 179-187) — remove the
  `JoltBodyCreate` call. Leave the "destroy any previous body" guard as
  defensive no-op.
- The `JoltMakeStatic` / `JoltMakeCharacter` destroy guards become dead code
  on the normal path but cost nothing — leave them defensive.
- Add a comment at the top of `physics/physical.hpi` (or the Jolt-specific
  physical.hpi) documenting: "`Construct` creates no Jolt body;
  `JoltMakeStatic` / `JoltMakeCharacter` are the only Jolt-body entry
  points. Non-participating actors (lights, cameras, markers, triggers)
  carry no Jolt body at all."

Check:
- `jolt: body ...` lines: ~16 (15 STATIC + 1 kinematic-then-destroyed char).
- `jolt: OptimizeBroadPhase done (N static bodies)` → `15`.
- No gameplay regression — character still on GROUND, same feet position.

### Step 3 — Update() path for Jolt-character actors (WF→Jolt sync)

**Defensive.** Today `jolt/physical.hpi::Update()` handles `_joltBodyID`
only. Character actors' `_joltCharID` is never re-synced from WF's
authoritative `_position`. If any code path outside the Jolt fast path
mutates the player's `_position` (warps, scripts, cutscenes), Jolt won't
see it.

Authority model we're locking in:
- **During predictPosition:** Jolt is authoritative. WF hands it velocity;
  Jolt computes position; WF reads back.
- **Between frames (Update):** WF is authoritative. Any WF-side mutation
  gets pushed into Jolt before the next frame's predictPosition.

Touch:
- `physics/jolt/physical.hpi::Update()` — add an
  `else if (_joltCharID != kJoltInvalidBodyID)` branch that calls
  `JoltCharacterSetPosition(_joltCharID, _position)` and
  `JoltCharacterSetLinVelocity(_joltCharID, linVelocity)`.

Check:
- Behaviour on snowgoons should be unchanged (nothing outside the fast path
  mutates the player on snowgoons).
- Defensive check: if ground state flips to `AIR` immediately after this
  change when it was `GROUND` before, the Update-push is clobbering Jolt's
  computed position. Re-examine call order in
  `movement/movementobject.cc` `DoneWithPhysics`.

### Step 4 — Diagnose and fix the 3 m vertical pop

**Turns "doesn't crash" into "actually works."** Don't code until the logs
tell us which theory is right.

Strongest hypothesis (from Plan agent): WF authors actor positions at
**feet** (`_colSpace.UnExpMin().Z() ≈ 0`, `UnExpMax().Z() > 0`). We
currently compute `ctr = minPt + half` and place the Jolt character at
`pos + ctr`, i.e. the actor's **centre**, not feet. CharacterVirtual's
reference point is then the centre, not the feet, and its penetration
recovery + stick-to-floor can produce a 3 m axis-aligned pop when the
authored pose barely overlaps a static AABB.

Right fix: wrap the `BoxShape` in a `RotatedTranslatedShape` with a
feet-aligned offset so Jolt's character reference point = WF "feet."
Drop the `ctr` translation in `JoltCharacterCreate` /
`JoltCharacterSetPosition` / `JoltCharacterUpdate` readback — character
positions flow through in WF feet coordinates unmodified.

Quick bisect: zero `upd.mStickToFloorStepDown` and re-run. If the pop
disappears, it was stick-to-floor; if it persists, it's penetration
recovery from bad shape/offset and the `RotatedTranslatedShape` fix is the
answer.

Unit-scale sanity check: log `UnExpMin/UnExpMax` for the character at
creation. If `halfExt.Z ≈ 1.5` the box is 3 m tall (matches the pop
exactly) and WF is in metres; if much smaller, we have an engine-unit
scale mismatch and Jolt's metre defaults (gravity 9.81, stick-to-floor
0.5) need rescaling.

Touch (pending diagnosis):
- `physics/jolt/jolt_backend.cc::JoltCharacterCreate` (lines ~382-395)
- `physics/jolt/jolt_backend.cc::JoltCharacterSetPosition`
- `physics/jolt/jolt_backend.cc::JoltCharacterUpdate` readback

Check:
- `jolt: char f000 f001 f002 ...` trace: `feet.z` stable across frames
  (variation of a few cm from stick-to-floor is fine; no 3 m jump).
- Idle 60 s: character stays at same `feet.z`.
- Walk forward: horizontal translation only, Z stable.

### Step 5 — Soak

- Idle 60 s. Zero asserts.
- Walk all four directions 30 s. No tunnelling through walls, no teleport.
- Jump. `AirHandler` path exercised; `JoltCharacterIsOnGround` returns
  true on landing; handler switches back to ground.

Any script-warp path that fires a `SetPredictedPosition` on the player and
asserts → option 2 from Q1: make `SetPredictedPosition` delegate to
`JoltSyncFromCharacter` when `_joltCharID` is valid.

## Architectural smells (future cleanup, not blocking)

Capture as code comments or a follow-up doc, don't do today.

1. **`SetPredictedPosition` conflates two ops.** "Record where the actor
   is going to be" and "expand swept colspace for WF broadphase" should be
   separate methods. Jolt-character callers would call only the first.
2. **Two sources of position authority with implicit hand-off.** A future
   dev adding a new `SetPosition` call somewhere won't know to push to
   Jolt. Long-term: unified position handle that knows which backend owns
   each actor.
3. **`ColBox::Expand` accumulates.** Depends on an undocumented
   reset-per-frame contract. Rewriteable as
   `expandedMin = unexpMin + min(delta,0); expandedMax = unexpMax + max(delta,0)`
   when the WF backend is retired.
4. **Kinematic-body remnant logic** after Step 2 — destroy guards in
   `JoltMakeStatic`/`JoltMakeCharacter` become dead code on the normal
   path. Leave as defensive, but call it out.
5. **Per-frame stderr tracing** in `JoltCharacterUpdate` should be behind a
   debug flag before ship.

## Files

- `wfsource/source/physics/physical.hp`
- `wfsource/source/physics/physical.hpi`
- `wfsource/source/physics/jolt/physical.hpi`
- `wfsource/source/physics/jolt/jolt_backend.cc`
- `wfsource/source/physics/jolt/jolt_backend.hp`
- `wfsource/source/physics/colspace.hp` / `colspace.hpi` (if `ResetExpansion`
  is needed)
- `wfsource/source/movement/movement.cc`
