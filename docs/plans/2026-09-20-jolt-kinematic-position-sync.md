# Sync scripted position-mailbox writes into Jolt for non-character actors

## Context

The condo's telescoping doors (`docs/plans/2026-09-20-condo-project-room-telescoping-doors.md`)
shipped as an instant open/closed visibility swap, not real sliding motion, because true
motion needs the engine to move a solid actor's *collision* along with its mesh — and
today it can't. User feedback: "instant-swap look isn't good enough."

The only existing scripted-motion mechanism is writing the `X_POS`/`Y_POS`/`Z_POS` local
mailboxes each tick (`game/actor.cc:1458-1503`), the pattern `fsn_flydown()`
(`engine/stubs/scripting_zforth.cc:189-201`) already uses to lerp a camera. Traced where
those writes go: they only push into Jolt for actors with a `JoltCharacterID()`
(`actor.cc:1471,1487,1503`) — there is no equivalent branch for a plain `JoltBodyID()`.
This exact gap was already flagged, unfixed, in
`docs/plans/2026-05-11-mailbox-pos-write-bypasses-jolt.md:97`: "rigid-body actors that
need mailbox teleport later will need a parallel `JoltBodySetPosition` call."

Checked what's actually available before designing a fix (research pass, not
assumption): **every actor body is already created kinematic by default**
(`wfsource/source/physics/jolt/jolt_backend.cc:225-248` — "All actor bodies start as
KINEMATIC — Jolt maintains the collision structure but WF drives position/velocity via
`Update()` each frame"). The capability to move a kinematic body already has a
first-class helper, `JoltBodySetPosition()` (`jolt_backend.cc:389-395`) — but it has
**zero callers anywhere in the codebase**. Jolt's own sweep-correct kinematic-move API,
`BodyInterface::MoveKinematic` (vendored Jolt 5.5.0, `CMakeLists.txt:613`), is likewise
never called anywhere. So a script-driven position write on a door panel today either
moves nothing in Jolt at all (if the actor has no character ID), or — worse — moves the
visible mesh while its stale collision volume stays behind.

> **Research correction (2026‑09‑20, implementation pass).** The two claims in the
> paragraph above are **false**, and the approach below does not work as written. Left
> in place above for traceability; corrected here. See **Status** at the bottom.
>
> 1. `JoltBodySetPosition()` does **not** have zero callers. It has two:
>    `wfsource/source/game/actor.hpi:107` (in `setCurrentPosition`) and, critically,
>    `wfsource/source/physics/jolt/physical.hpi:24` inside `PhysicalAttributes::Update()`.
> 2. Because of that second caller, scripted position writes on a body actor **do**
>    already reach Jolt. `Update()` runs once per physics frame from
>    `MovementObject::DoneWithPhysics()` (`wfsource/source/movement/movementobject.cc:77`)
>    and unconditionally pushes `_position` into the body. The premise that collision
>    stays stale behind the mesh is wrong — collision already follows, every frame.
>
> The real gap is narrower than the plan states: the existing sync is a **teleport**, not
> a sweep. That is a genuine limitation, but it is not what the Approach below fixes.

Also checked, and rejected as the fix target: building out `Platform::initPath()` into a
generic OAD-authored waypoint/path system. `platform.hp/.cc`'s `initPath()` is a fully
empty stub (its only line is a commented-out call to a base-class method that doesn't
exist), and `platform.oas` has zero path/waypoint/speed fields — there was never
authored data for it to consume. Building that for real is a three-surface change (new
OAD schema fields + Jolt kinematic plumbing + Platform/Actor C++), a small feature
project, not what a two-point door slide needs. The legacy `Path`/`PathHandler` keyframe
system (`anim/path.hp`, `movement/movepath.cc`) is a dead, pre-Jolt, `assert(0)`-stubbed
spline system — reviving it would cost more than building the narrow fix fresh.

## Approach

Extend the existing `X_POS`/`Y_POS`/`Z_POS` mailbox-write handlers
(`game/actor.cc:1458-1503`) with a new branch for actors that have a `JoltBodyID()` but
no `JoltCharacterID()`: push the write into Jolt via a new
`JoltBodyMoveKinematic(bodyID, targetPosition, deltaTime)` helper (added alongside the
existing, currently-dead `JoltBodySetPosition()` in `jolt_backend.cc`/`.hp`), using
Jolt's `BodyInterface::MoveKinematic` rather than an instant `SetPosition`.
`MoveKinematic` computes the body's velocity from the target position and the frame's
delta-time, giving Jolt real sweep-based collision response — a plain teleport-style
`SetPosition` could let a fast-moving door tunnel through a thin collider, or fail to
correctly push the player out of the way, and would defeat the entire point of doing
this via physics instead of the already-rejected instant-swap.

This is a small, general-purpose, additive fix — not door-specific. It closes the exact
gap `docs/plans/2026-05-11-mailbox-pos-write-bypasses-jolt.md` already named, benefits
any future scripted-motion rigid actor, and requires no OAD schema changes: the existing
mailbox-write path is already exposed to Forth, so once this lands, the door's sliding
motion is authored entirely at the level-script layer — a per-tick Forth script writing
local `X_POS`/`Y_POS`/`Z_POS` for each movable panel, following the same `fsn_flydown()`
lerp-over-time template already proven for the camera. No new syscall needed.

**Rejected**: building `Platform::initPath()` out into a real generic mover (see
Context) — bigger, unnecessary three-surface change for what a two-point slide needs.
**Rejected**: reviving `Path`/`PathHandler` — dead, pre-Jolt, orthogonal system.

Critical files: `wfsource/source/physics/jolt/jolt_backend.cc`/`.hp` (new
`JoltBodyMoveKinematic` helper), `wfsource/source/game/actor.cc:1458-1503` (new branch
in the three mailbox-write handlers). The door's own Forth script is a follow-up once
this lands — tracked in `docs/plans/2026-09-20-condo-project-room-telescoping-doors.md`,
not written here.

No visible surface in this plan's own scope — it's a physics-plumbing fix with no
rendered output of its own; the door slide it enables is the follow-up's visible
surface, not this one's. Mockups section dropped per the plan template's allowance.

## Out of scope

- The door's actual sliding Forth script and panel-motion authoring — follow-up once
  this engine fix lands, tracked in the telescoping-doors plan.
- A generic OAD-authored `Platform`/waypoint system — see Context for why it was
  rejected as the fix target; worth its own plan if a future level wants
  designer-authored multi-point paths, not attempted here.
- Reviving `Path`/`PathHandler` — dead code, not worth resurrecting for this.
- Any change to the existing `JoltCharacterID()` branch's behavior — pure addition,
  character-controlled actors (the player) are untouched.

## Verification

1. Build a small scratch test actor (or reuse an existing non-character statplat actor
   in a throwaway level) with a `JoltBodyID` and a script writing its `X_POS` mailbox
   each tick; confirm Jolt's body position actually updates every frame — read it back
   via `BodyInterface`, or observe a player standing in its path being correctly pushed
   or blocked, rather than the mesh visually moving while collision stays at spawn.
2. Confirm the sweep behavior: move the same test actor quickly (large per-tick delta)
   into a thin static collider and confirm it doesn't tunnel through — this is
   specifically what `MoveKinematic` buys over `SetPosition`; if a first cut only wires
   up `SetPosition` (deferring the sweep-correct call), state that residual gap
   explicitly here rather than claim full correctness.
3. No regression to existing character-controlled actors — the player's own
   `X_POS`/`Y_POS`/`Z_POS` mailbox writes (the `JoltCharacterID()` branch) are provably
   untouched; re-run any existing player-movement test/level walkthrough.
4. Once this lands, re-verify the telescoping door's Forth script actually slides with
   working collision (the follow-up task's own verification, referenced here for
   traceability, not duplicated).

**Not run — no code was written.** The implementation pass stopped before editing any
source file, because the Approach does not survive contact with the code (see the
Research correction in Context, and Status below). Recording why each step was not
reached, rather than leaving them blank:

1. **Build a small scratch test actor … confirm Jolt's body position actually updates
   every frame.** Not run. Investigating this step is what surfaced the blocker: the body
   position *already* updates every frame today, via
   `PhysicalAttributes::Update()` → `JoltBodySetPosition()`
   (`wfsource/source/physics/jolt/physical.hpi:22-28`), called from
   `MovementObject::DoneWithPhysics()` (`wfsource/source/movement/movementobject.cc:77`).
   The behaviour this step was written to prove absent is present. **N/A** — premise
   invalid.

2. **Confirm the sweep behavior … doesn't tunnel through a thin static collider.** Not
   run, and believed **not achievable by this mechanism**. Actor bodies are `Kinematic`
   in the `DYNAMIC` object layer (`jolt_backend.cc:215-219`). A kinematic body has
   effectively infinite mass and is never positionally corrected by a static body, so it
   passes through static geometry whether moved by `SetPosition` or `MoveKinematic`. The
   object-layer filter (`jolt_backend.cc:92-94`) does let DYNAMIC↔STATIC contacts be
   *detected*, but detection is not blocking. `MoveKinematic`'s sweep buys correct
   pushing of *dynamic* bodies and `CharacterVirtual` contact resolution — i.e. the door
   shoving the player out of the way — not static-collider tunnelling. This step needs
   rewriting against a dynamic/character obstacle before it can pass or fail.

3. **No regression to character-controlled actors.** Trivially satisfied — no code was
   changed. **N/A.**

4. **Re-verify the telescoping door's Forth script.** Not reached; blocked behind steps
   1–2, and the script itself is out of scope per **Out of scope**.

## Status: blocked, escalated

Implementing the Approach literally — calling `JoltBodyMoveKinematic` from the three
mailbox-write handlers — would produce a **silent no-op**. `MoveKinematic` works by
setting a velocity for Jolt to integrate across the next step. But
`PhysicalAttributes::Update()` runs later in the same frame and unconditionally does
`JoltBodySetPosition(_joltBodyID, _position)` followed by
`JoltBodySetLinVelocity(_joltBodyID, Vector3::zero)` — teleporting the body and zeroing
exactly the velocity `MoveKinematic` just established. The change would compile, read
correctly, and do nothing.

Making the sweep effective means changing the authority model that
`wfsource/source/physics/jolt/physical.hpi:16-28` states deliberately and in comments:
*"WF fully controls kinematic positions; Jolt only maintains the broadphase collision
structure."* That is a cross-cutting decision this plan never made, and it opens
questions with no authored answer:

- **Which actors opt into sweep authority?** All bodies, or only scripted movers (a new
  per-actor flag, `Mass == 0`, something else)? Flipping it globally changes physics for
  every body actor in every level.
- **Who wins when a swept move is blocked?** There is no body-side read-back path — the
  character path has `JoltSyncFromCharacter()`, bodies have nothing equivalent. Either
  WF's `_position` gets corrected from Jolt (new plumbing, and scripts then fight the
  correction), or the mesh visually desyncs from its collision volume.
- **Is a kinematic body even the right body type** for a door that should be stopped by
  the world, given the layer analysis in verification step 2 above?

**ESCALATE: this needs T4/T5** — the fix requires redesigning the WF↔Jolt authority model
for kinematic bodies, not the additive plumbing change this plan describes.

Nothing was landed: no source file was modified, and no helper was added (adding a
`JoltBodyMoveKinematic` with no working caller would just be a second dead function
beside the one this plan wrongly believed was dead). This plan file is the only change.

<!--
When the work lands, this section becomes the permanent record:

1. **Step as originally written.**

```
$ the exact command
raw output, unedited
```

**PASS** — one line on what the output proves.

An item stays `[verify T<n>]` in TODO.md until every step here has recorded output.
-->
