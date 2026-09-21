# Plan: Marble Madness — true-3D reimplementation (independent attempt)

**Date:** 2026-09-21
**Status:** Not started
**Goal:** A faithful, true-3D reimplementation of arcade Marble Madness's courses in WorldFoundry, built fresh — not by extending the existing stalled implementation. This is one of **two independent, parallel attempts** (this one, on branch `marble-madness-3d-fable`; a second on branch `marble-madness-3d-astra`, built by a different AI tool in a separate worktree). Will is comparing the two approaches; they must not share code or coordinate with each other.

## Why "start fresh" — read this first

WorldFoundry already has a Marble Madness recreation effort at `wflevels/marble-madness/` (see `docs/marble-madness/README.md`), and separately the currently-shipped `marble-madness`/`marble-madness-2` levels in `wflevels/`. **Will's explicit instruction: ignore both existing implementations. Do not read, reuse, extend, or build on top of their `.lev`/`.iff`/Blender-script files.** The existing effort's own verdict on the shipped levels was that they were never accurate arcade conversions (physics/ball-movement was fine, course geometry was not), and the ROM-faithful effort stalled part-way (M3 of 5, see `docs/plans/2026-05-01-marble-madness-faithful.md` for what that means if you're curious about *why* it stalled, but do not treat its implementation choices as a starting point).

**What you SHOULD use freely — all the prior research, none of the prior implementation:**

- `docs/investigations/2026-05-01-marble-madness-rom-level-data.md` — how the arcade ROM's level data was located and decoded. This is the ground truth for accurate course geometry: real arcade level layouts, not guesses.
- `docs/investigations/2026-05-01-mm-level-elevations.md` — elevation/height-field data for the courses, with MAME reference screenshots for cross-checking.
- `wflevels/marble-madness/decode_levels.py` and `wflevels/marble-madness/levels.json` (already-decoded output) — **you may run/read the decoder and use its output data**, but do not reuse `rom_to_blender.py` or any of the Blender scene scripts that consume it; write your own geometry pipeline.
- `assets/arcade-roms/marble.zip` — the vendored ROM the decoder reads, if you need to re-derive anything the decoder doesn't already expose.
- `docs/plans/2026-05-02-level-recreation-workflow.md` — process notes on how the previous effort approached level recreation (useful context on pitfalls, not a spec to follow).
- `docs/plans/2026-05-01-marble-madness-faithful.md` — the previous effort's full milestone breakdown (M1–M5+), physics/camera notes (isometric camera math, camera-relative input, fixed-point angle format gotchas), and its 42-test coverage target table. Read this for the *domain knowledge* (what an accurate camera/physics/course setup needs to get right) — the specific files it produced are what you're not reusing.
- `docs/plans/2026-04-28-marble-player-sphere.md`, `docs/plans/2026-04-28-replace-player-mesh-with-sphere-marble-in-marble.md`, `docs/plans/2026-04-30-duplicate-marble-madness-level-for-physics-motion-co.md` — smaller prior investigations into ball/physics representation, same rule: read for findings, don't reuse the artifacts.
- General engine docs: `docs/level-building.md`, `docs/level-design-troubleshooting.md`, `docs/level-layouts.md`, `~/WorldFoundry-wbniv/CLAUDE.md` (coordinate systems, Euler angle conventions — read carefully, there's a documented bug in a code comment vs. the actual implementation, noted there).

## What "true 3D" means here

The shipped `marble-madness`/`marble-madness-2` levels are simplified/inaccurate course geometry riding on the engine's existing 3D renderer and (per the recent backface-culling effort) correctly-wound meshes — but the *courses themselves* don't match the arcade original's layout. "True 3D reimplementation" means: use the engine's real 3D physics (Jolt, already integrated — see `wfsource/source/physics/jolt/`) and real 3D course geometry derived from the decoded ROM data, so the marble actually rolls on accurately-shaped 3D terrain (slopes, chutes, ramps, gaps) matching the arcade courses' real elevation/layout data, viewed from an isometric-style camera as the original used.

## Scope

Pick your own implementation path, but the deliverable should be:

1. At least one fully accurate, playable course (Practice and/or Beginner are the natural starting points — smallest courses, per the ROM data). Judge "accurate" against the decoded level data and the MAME reference screenshots in the elevations investigation, not against the existing WF implementation.
2. A clear write-up of your approach: how you turned the decoded ROM data into WF level geometry, what your camera/physics setup is, what's faithful vs. approximated and why, and how far you got (which of the 6 arcade courses — Practice, Beginner, Intermediate, Aerial/Advanced, Silly, Ultimate — are complete vs. not attempted).
3. If you have time/budget after a first accurate course, extend to more courses — but a single genuinely accurate course beats a rough pass at all six.

## Where to put it

New level(s) under `wflevels/marble-madness-3d/` (or similar — your call), **not** inside the existing `wflevels/marble-madness/` directory, so there's no risk of colliding with or accidentally modifying the existing implementation. Don't touch `wflevels/marble-madness/`, `wflevels/marble-madness-2/`, or the shipped `cd.iff` bundle list — this is a standalone, non-shipped level for now, run directly via `wf_game -L<path>`, same as the existing effort's levels are.

## Process

Follow this repo's normal conventions: plan-first (this doc, update it as you go), commit at natural checkpoints on your branch (`marble-madness-3d-fable`), don't touch files outside your remit. `task build` must stay green throughout. Write up verification the way this repo does it elsewhere (numbered steps + raw output + PASS/FAIL) rather than prose claims.
