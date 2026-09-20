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
