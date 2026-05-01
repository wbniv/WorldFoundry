# Marble Madness — Faithful Replication Plan

**Date:** 2026-05-01  
**Status:** M1 complete — canonical iso camera + camera-relative input wired  
**Design source:** [`/home/will/wf-games/marble-madness.md`](../../../../../../wf-games/marble-madness.md) and [`/home/will/wf-games/marble-madness/`](../../../../../../wf-games/marble-madness/)  
**Level dir:** `wflevels/marble-madness-2/` (prototype), moving to `wflevels/mm_practice/` et al.

## Goal

Replicate Atari's Marble Madness (1984) faithfully inside World Foundry — same fixed isometric camera framing, same camera-relative controls, same six-stage structure — then diverge into 3D-specific expansions. The wf-games design docs are the source of truth; this plan tracks engine/level status against them.

---

## Milestones

### M1 — Canonical iso camera + camera-relative input

**Status:** Complete 2026-05-01

**Camera spec** (tuning.md):

| Param | Value |
|-------|-------|
| Yaw | 45° (camera sits in the −X, −Y quadrant looking northeast) |
| Tilt | 30° down from horizontal |
| Distance | 30 m from marble |
| FOV | 25° (narrow ≈ orthographic look) |

**Camera position** (relative to marble spawn; computed):

Horizontal distance = 30 × cos(30°) ≈ 26 m at 45° in XY → offset (−18, −18)  
Vertical = 30 × sin(30°) = 15 m  
Camera = spawn + (−18, −18, +15). If spawn = (0, 5, 13): **camera at (−18, −13, 28)**.

**Input math:**

Horizontal view direction from camera (−18,−13) to target (0,5): (+18, +18) → normalised (√2/2, √2/2).  
`fwd = (sin C, cos C, 0)` → need C = +π/4 = **+0.7854 rad**.

Button → world direction:
| Button | World XY |
|--------|----------|
| UP | (+0.707, +0.707) — northeast |
| DOWN | (−0.707, −0.707) — southwest |
| LEFT | (−0.707, +0.707) — northwest |
| RIGHT | (+0.707, −0.707) — southeast |

Diagonal combos for course legs (marble-madness-2 layout):
- UP+LEFT = pure +Y (leg 1 direction) ✓
- DOWN+LEFT = pure −X (leg 2 direction) ✓

**Changes required:**
- `gen_level1.py`: update camera, CamShot01 positions to (−18, −13, 28); Target01/02 at spawn
- `marble-madness.lev` Player EULR: set C = 0.7854 (π/4 radians, 1.15.16 fixed-point)
- `wfsource/source/game/level.cc` or camera OAD: FOV 50° → 25° (if scriptable; else note as deferred)

**Success criteria (tests.md T-101, T-103, T-104):**
- Pressing UP+LEFT accelerates marble in the +Y world direction (leg 1)
- Camera is visibly iso — identical framing to original arcade screenshots
- Marble rolls downhill from spawn with no input (gravity alone, T-104)

---

### M2 — `mm_practice` faithful course

**Status:** Not started

**Spec** (stages.md): straight ramp, two soft S-curves, wide trough with raised lips, no hazards, 90 s.  
Size: 30 m × 30 m × 4 m vertical drop.  
Course direction on screen: top-left (elevated spawn) → bottom-right (goal at floor level).  
In world: spawn at (+X, +Y end) high Z; goal at (−X, −Y end) low Z — i.e., ramp runs in (−X, −Y) world direction = DOWN+RIGHT on iso screen.

**Changes required:**
- Redesign gen_level1.py course geometry to match stages.md spec
- Remove current L-shaped prototype; replace with straight-ramp + S-curve layout
- Keep timer (90 s) and goal detection

**Success criteria:**
- Marble rolls from spawn to goal without input in < 90 s (T-104)
- Stick input deflects marble from the gravity-only path (T-101)
- Goal trigger warps/ends level (T-305 proxy; warp to mm_beginner deferred to M5)

---

### M3 — Game loop: lives, checkpoints, score, HUD

**Status:** Not started

**Spec** (tests.md T-3xx, tuning.md Score table, audio-anim-hud.md):
- Lives: 3 at start; death decrements; 0 → game over
- Checkpoints: set on path-progress triggers; death respawns at last checkpoint
- Score: 1000 base on goal + 100 × seconds remaining; "survival bonus" 50 per 5 s with no deaths
- HUD: score top-left, time top-centre, lives top-right (via `HUD_TEXT_*` mailbox slots)

**Changes required:**
- Director script: replace END_OF_LEVEL with proper lives/score accounting
- Player script: death → respawn at checkpoint, not level end
- Checkpoint trigger actors on path
- HUD overlay (existing EXT-1 bitmap-font overlay; wire mailbox slots per audio-anim-hud.md)

**Success criteria (T-301 through T-306):**
- Timer counts down visibly on screen
- Death decrements lives; respawns at last checkpoint with timer preserved
- Score reflects time bonus on goal

---

### M4 — `mm_beginner` + hazard actor foundation

**Status:** Not started

**Spec** (stages.md): 50 m × 40 m × 8 m, 75 s timer; slime-drip + fall-off-trigger actors; path forks.

**New actor types** (bestiary.md):
- `slime-drip`: periodic emitter; spawns `slime-blob` below; contact → 50% friction for 1.5 s
- `fall-off-trigger`: volume below unwalled path; entry → PLAYER_DEAD

**Changes required:**
- `mm_beginner.lev` new level
- Slime-drip actor OAD + Forth script per bestiary.md
- Fall-off trigger volume (trigger actor, no mesh, large invisible box below path edge)
- Verify T-201 through T-203

**Success criteria:** both forks reachable, slime slows marble, fall-off kills and respawns.

---

### M5+ — Remaining stages + lobby

**Status:** Not started

Stages: `mm_intermediate`, `mm_aerial`, `mm_silly`, `mm_ultimate`, `mm_lobby`.  
Each adds ≤ 2 new actor types (marble-muncher, hammer-guy, magnets, vacuum, acid, lobby portals).  
All fully specified in stages.md and bestiary.md — implement in order, one stage per sprint.

---

## Test coverage targets

| Milestone | Tests covered |
|-----------|--------------|
| M1 | T-101, T-103, T-104, T-401 |
| M2 | T-101, T-102, T-104, T-105, T-301 (proxy) |
| M3 | T-301–T-306, T-402, T-403, T-501 |
| M4 | T-201–T-203 |
| M5+ | T-204–T-216, T-402–T-403, T-502–T-504 |

Full 42-test coverage requires M5 complete.

---

## Notes

- FOV 25° is a CamShot OAD field; check if it's wired to the perspective matrix. If hardcoded, use a long focal-length workaround (camera at 60 m, FOV 10°) to approximate orthographic.
- The BungeeCam `Target/TrackObject` architecture already handles the follow; only the offset from marble needs updating.
- Camera-relative input relies on the Player actor's Rotation C field in the .lev. Because `MarbleHandler` reads `movementObject.currentDir()` = (sin C, cos C, 0), setting C = π/4 at spawn is sufficient — the marble is a sphere so visual rotation doesn't conflict.
- Per handoff note: angles in marble-madness-2 .lev are radians in 1.15.16 fixed-point. π/4 = 0.7854 rad → `0.7854000000000000(1.15.16)`.
