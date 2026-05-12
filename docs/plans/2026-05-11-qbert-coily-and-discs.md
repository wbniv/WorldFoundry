# Plan — Coily + Spinning Discs (full arcade-faithful)

**Status:** Done (2026-05-11, commits `1e300a1` egg → `3f0e1d5` snake transform → `43c7718` chase AI → `930b066` spinning discs → `bad66a1` polish → `5d2b345` apex stretch)
**Stacks on:** Red Ball Phase B (`ba8d606`), 80-face mesh (`35ee402`), S&S (`15705d1`).

## Context

The arcade Q*bert game's iconic enemy is **Coily** — a purple snake that hatches from a bouncing egg, then chases Q*bert across the pyramid with the same hop pattern Q*bert uses. The most distinctive interaction is the **spinning discs** at the top-left and top-right of the pyramid: Q*bert can lure Coily onto a disc, and Coily falls off the bottom for bonus points.

Currently the level has the player, 28 cubes, and 3 red balls. Nothing chases Q*bert deterministically; there's no per-round single-threat enemy and no way for the player to *defeat* an enemy. This plan adds Coily (egg + snake + chase) and the discs that complete the lure mechanic.

Four sequenced phases, each shippable as its own commit:

| Phase | Adds | Cumulative gameplay |
|---|---|---|
| **A** | Coily egg (purple ball bouncing down from apex) | Visual hint of a new enemy; no chase yet |
| **B** | Egg → Coily transformation at bottom row | Coily exists; just stands there |
| **C** | Coily greedy-chase AI | Coily chases Q*bert; death on contact |
| **D** | 2 spinning discs + lure-and-die mechanic | Q*bert can defeat Coily |

## Architecture

### Reuse where possible

- **Egg** = a single fork of `redball_script(k)` with one ball (not three), purple material, slower hop cadence (matches arcade ~24 ticks vs red ball's 18), spawn once per round.
- **Coily snake** = a separate actor with a stacked-segment mesh. Shares the per-tick countdown + smoothstep XYZ + arc-Z + S&S idioms with the ball; differs in the *landing tick decision* (greedy AI instead of LFSR coin flip) and the *retire path* (death/round-end logic).
- **Discs** = 2 pre-created actors at fixed off-edge positions. Each is a short purple cylinder (rotation animation deferred — visual fidelity is "obviously a disc, but not actually spinning").

### Mailbox layout

Free block above 517 (existing Phase B). Allocate:

| mb | name | use |
|---|---|---|
| 518..525 | `COILY_EGG[8]` | egg state — same 8-slot layout as a red ball (ROW/COL/COOLDOWN/PHASE/START_Z/END_Z/FROM_ROW/FROM_COL) |
| 526..533 | `COILY_SNAKE[8]` | snake state — same 8-slot layout |
| 534..541 | `DISC_LEFT[8]`, `DISC_RIGHT[8]` | per-disc state: ROW/COL position sentinel, PHASE (0=consumed, 1=present), per-disc visual scratch (4 slots reserved for the spin-anim if added later) |
| 542 | `COILY_ROUND_DONE` | director one-shot per round: has-spawned-coily-this-round latch |
| 543 | `COILY_PHASE_GLOBAL` | 0=neither, 1=egg active, 2=snake active. Director tracks; balls don't read it. |

24 + 16 + 2 = 42 new mailboxes. Range 518..559.

### Director additions

After the existing red-ball spawn-timing block (gated on INTRO_DONE), append a per-round single-shot block that:

1. Detects ROUND_CHANGED (mb 426=1) or first-round (mb 542==0 and INTRO_DONE). On detect: spawn the egg, latch `COILY_ROUND_DONE = 1`, clear ROUND_CHANGED.
2. On every tick: if `COILY_PHASE_GLOBAL == 1` (egg) AND egg's PHASE flips 0→0 *with row=6* (signal: egg-just-reached-bottom), spawn the snake at egg's last (row, col), latch `COILY_PHASE_GLOBAL = 2`.
3. On round-clear (mb 413=1): retire egg and snake (PHASE=0 + park Z), refresh discs to PHASE=1, clear `COILY_ROUND_DONE`. Next round wakes a fresh egg.

(Step 2's "egg reached bottom" signal needs a tiny addition to the egg script: when retire fires from row=6 specifically, the egg writes its (row, col) to a known scratch (`COILY_PHASE_GLOBAL` itself can carry: e.g. egg writes 2 → "transform pending", director sees and activates snake.)

### Coily snake chase AI (greedy Manhattan)

On Coily's landing tick (cd <= 0), enumerate the four valid next-cubes:

- `(row+1, col)`, `(row+1, col+1)` — down-left, down-right
- `(row-1, col)`, `(row-1, col-1)` — up-left, up-right

Filter to pyramid-valid: `0 <= new_col <= new_row <= 6`.

Score each by Manhattan distance to player `(qb_row, qb_col)`: `|new_row - qb_row| + |new_col - qb_col|`. Pick the minimum (tiebreak: prefer down moves, then left). Encode as a 4-branch Forth cascade — each branch tests validity and scores; final winner is one mb-slot's worth of (new_row, new_col).

Hop cadence: 12 ticks (matches Q*bert player's HOP_COOLDOWN). Arc-Z and S&S identical to the ball at full player-strength (Coily is character-class, not bouncy-ball).

### Coily death paths

- **Caught Q*bert**: same as red ball — Coily writes 1 to mb 414. Player's FALL_DEATH machinery runs.
- **Fell off disc**: disc detects Coily on its (row, col), writes Coily's PHASE=0 + parks. No player death.
- **Round cleared**: director retires both egg and snake (PHASE=0 + park) when ROUND_CLEAR latches.

### Discs

Two discs at fixed off-edge positions:

- `disc_left`  at (row=1, col=-1) — just left of the row-1 leftmost cube
- `disc_right` at (row=1, col=2)  — just right of the row-1 rightmost cube

World positions computed via the same `cube_world_position(row, col)` formula (which works for fractional/out-of-range col too — gives positions just off the pyramid).

**Disc script (per-tick):**

```forth
\\ PHASE 0 (consumed): exit
\\ PHASE 1 (present):
\\   read player (row,col); if match → TELEPORT player back to (0,0) apex
\\     (write 0 to mb 400, 0 to mb 401, 14.5 to actor 1 / mb 3011)
\\     write own PHASE=0 + park
\\   read snake (row,col) from globals 526/527; if match → kill Coily
\\     (write 0 to COILY_SNAKE PHASE, retire, park)
\\     write own PHASE=0 + park
```

Disc activation: director on round-init wakes both discs (PHASE=1). On round-clear, refresh both.

**Q*bert hopping ONTO a disc** — the player's existing edge-hop logic writes FALL_PHASE=1 when Q*bert hops past the pyramid. We need to intercept that:

- Easiest: have the player's hop-arc landing tick check if there's a disc at the target (row, col) BEFORE FALL_PHASE fires. If yes, snap to apex instead of fall.
- This requires reading disc state from the player's script. Use a global "disc-at" lookup: 2 mailboxes (DISC_LEFT_ROW=534, DISC_LEFT_COL=535, etc.) the player's landing logic can check.

OR (cleaner): the disc itself owns the intercept. On every tick, the disc reads player ROW/COL; if match, write player back to apex + park self. The player's FALL_PHASE will still fire one tick (until apex teleport overrides) — visual: Q*bert briefly tilts off-edge before being snatched back. Acceptable for v1.

I'll go with the disc-owns-the-intercept design — simpler, no player-script changes.

### Coily mesh — stacked spheres

Build via Blender Python: 4 purple icospheres stacked vertically along +Z, slightly compressed (Z scale 0.7 per segment), join into one mesh. Eye dots on top segment (2 black tiny spheres at the front face). Material: deep purple (RGB ≈ (0.6, 0.1, 0.9)) Principled BSDF.

Bounding box authored to be tall-skinny so the engine's collision approximation is reasonable.

### Disc mesh — flat cylinder

`bpy.ops.mesh.primitive_cylinder_add(radius=1.2, height=0.15, vertices=16)`, purple/blue gradient material (single Base Color for v1; arcade "spinning" effect deferred). Author the disc at its own origin; place each instance via `obj.location`.

## Critical files

| File | Change |
|---|---|
| [`wflevels/qbert_practice/blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py) | (a) Add `coily_egg_script()`, `coily_snake_script()`, `disc_script()` generators. (b) Add procedural Coily mesh (stacked 4-segment icospheres + eye dots, purple). (c) Add procedural disc mesh (flat cylinder, purple-blue). (d) Pre-create 1 egg + 1 snake + 2 disc actors with park-Z positions; capture `COILY_EGG_ACTOR_IDX`, `COILY_SNAKE_ACTOR_IDX`, `DISC_LEFT_ACTOR_IDX`, `DISC_RIGHT_ACTOR_IDX` for director addressing. (e) Director: append per-round Coily-spawn block, egg→snake transition watcher, ROUND_CLEAR retire block, and round-init disc activation. |
| (no engine changes) | EMAILBOX_X/Y/Z_POS, FACE_COLOR, X/Y/Z_SCALE handlers all reused. write-actor-mailbox addresses fixed actor indices. |

## Verification

### Phase A (egg)

1. Build + boot; egg appears at apex after intro, bounces down via LFSR like a red ball but PURPLE.
2. Debug bridge: probe `COILY_EGG[*]`, verify PHASE=1 during bounce, retire at row > 6.
3. Visual: egg recognisable as distinct from red balls (purple ≠ red, slower hop).

### Phase B (transform)

1. After egg reaches row 6, snake actor wakes at egg's last cube; egg parks.
2. Debug bridge: probe `COILY_PHASE_GLOBAL` transition 1→2 at landing.
3. Visual: stacked-purple Coily mesh visible at row 6.

### Phase C (chase)

1. After transform, drive Q*bert via the walker harness or manual joystick. Coily hops once per ~12 ticks; the new (row, col) reduces Manhattan distance.
2. Drive Q*bert directly INTO Coily; expect FALL_DEATH latch + cs_death + lives--.
3. Visual: Coily clearly follows Q*bert across the pyramid.

### Phase D (discs)

1. 2 discs visible at left/right edges next to row 1 cubes.
2. Drive Q*bert onto a disc cube (left or right off-edge hop): expect snap-to-apex instead of FALL_DEATH; disc PHASE flips to 0 (visually disappears).
3. Lure Coily: drive Q*bert onto the disc with Coily one step away on the side; Coily's next greedy hop should target the disc cube; on landing there, expect Coily death (PHASE=0 + retire).
4. Round-clear: clear a round (drive all cubes to state 2); discs refresh to PHASE=1 next round; egg + snake retire.

### Regression

- Red-ball Phase B behaviour unchanged (3 balls, spawn cadence per ROUND_NUMBER).
- Player hop-arc + S&S unchanged.
- Round-clear / FALL_DEATH pipelines unchanged.

## Commit sequence

Each phase as a separate commit:

1. `feat(qbert): Coily egg — purple ball, per-round spawn`
2. `feat(qbert): Coily snake — egg-to-snake transform at bottom row`
3. `feat(qbert): Coily chase AI — greedy Manhattan-distance pursuit`
4. `feat(qbert): spinning discs — apex teleport + Coily-falls-off`

## Out of scope (future plans)

- Coily egg's purple-and-red **flashing** visual (arcade shows alternating frames during the bounce-down) — defer to a follow-up
- **Multiple Coily eggs per round** at higher levels — arcade scales to 2 eggs at L4+. Defer.
- **Disc spinning animation** — currently static visual; add a per-frame rotation later
- **Disc-jump anticipation arc** — Q*bert's arcade hop to a disc is a longer arc; we'll use the standard hop for now
- **Coily speech** ("@#!*?") on disc-death — arcade shows a speech bubble; defer
- **Green Ball / Slick / Sam / Ugg / Wrong-Way** — separate enemy plans
