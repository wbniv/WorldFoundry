# Plan — Ugg & Wrong-Way (side-of-pyramid climbers)

**Status:** Not started
**Stacks on:** Slick & Sam (`5c93811`), Green Ball + flash + spin (`2ad0459`, `bad66a1`, `5d2b345`).

## Context

The arcade Q*bert enemy roster has 8 members. We have player + 6 enemies (red ball, Coily egg, Coily snake, green ball, Slick, Sam); the final two — **Ugg** and **Wrong-Way** — are the only ones that don't bounce on cube *tops*. They climb the **sides** of the pyramid: Ugg ascends the right edge from the bottom-right corner toward the apex, and Wrong-Way ascends the left edge symmetrically. If they reach Q*bert's cube they kill him; Q*bert can lure them off the pyramid edge for points.

Two-phase plan, mirroring the Slick/Sam split:

| Phase | Adds | Cumulative gameplay |
|---|---|---|
| **A** | Ugg — orange hat, climbs right edge `(6,6) → (0,0)` | First "upward" enemy; player must watch the right slope |
| **B** | Wrong-Way — purple hat, climbs left edge `(6,0) → (0,0)` | Symmetric threat from the left |

After Phase B, the arcade enemy roster is complete (modulo bonus letter "S" pickups).

## Approach

### Reuse `redball_script(k, variant)` again

The slick/sam refactor proved this script is now a general "hopping enemy" generator. Ugg/Wrong-Way reuse the same hop pipeline (smoothstep XY lerp, arc-Z, stretch-and-squash, freeze-gate, contact check). They differ from a redball in only three places, all of which are already configurable via the `variant` arg pattern:

1. **Direction at landing tick** — fixed up-diagonal instead of LFSR random down-diagonal:
   - Ugg: `ROW -= 1, COL -= 1` (climbs apex-ward along right edge cubes `(r, r)`)
   - Wrong-Way: `ROW -= 1` (col stays 0; climbs along left edge cubes `(r, 0)`)
2. **Retire condition** — `ROW < 0` (reached/passed apex) instead of `ROW > 6` (off bottom).
3. **Contact action** — kill Q*bert (`1 414 write-mailbox`), same as the red ball.

The existing `flat_bases` dict ([blender_create_qbert.py:893](../../wflevels/qbert_practice/blender_create_qbert.py)) gets two new entries; the landing-tick block adds a `direction_block` template selected by variant; the off-pyramid check parameterises its threshold.

Spawn: at the BOTTOM of the chosen edge — Ugg at `(row=6, col=6)`, Wrong-Way at `(row=6, col=0)`.

### Mailbox layout

Red-ball director globals occupy `511..517`, so I can't use the contiguous range starting at 510. Allocate after the Slick/Sam director globals (`549..552`):

| mb | name | use |
|---|---|---|
| 553..560 | `UGG_STATE[8]` | ROW/COL/COOLDOWN/PHASE/START_Z/END_Z/FROM_ROW/FROM_COL |
| 561..568 | `WW_STATE[8]`  | same layout |
| 569 | `UGG_MB_ACTIVE` | director mirror |
| 570 | `UGG_MB_SPAWN_TIMER` | director countdown |
| 571 | `WW_MB_ACTIVE` | director mirror |
| 572 | `WW_MB_SPAWN_TIMER` | director countdown |

Spawn cadence:
- `UGG_SPAWN_INTERVAL = 1200` (20 s)
- `WW_SPAWN_INTERVAL  = 1500` (25 s — slightly rarer)
- `UGG_FIRST_DELAY    = 1200` (first Ugg ~20 s after intro)
- `WW_FIRST_DELAY     = 1800` (first WW ~30 s after intro)

### Mesh and material — arcade-faithful (in 3D)

Distinct procedural meshes per enemy, matching the arcade sprites' silhouettes recast as 3D geometry. The flipper hat-on-body proxy is **not** appropriate — Ugg and Wrong-Way are visibly distinct creatures in the arcade and should be distinct here.

Both are roughly the same shape (small chunky body, two horns / ears on top, two stubby legs) but differ in colour:

- **Ugg**:        orange/yellow body (RGB ≈ (1.00, 0.55, 0.10)), two short horns on top
- **Wrong-Way**:  purple body (RGB ≈ (0.55, 0.10, 0.85)), two ear-like nubs

Geometry: built procedurally via Blender Python in the same idiom as `_coily_build_mesh` ([blender_create_qbert.py:1361](../../wflevels/qbert_practice/blender_create_qbert.py)) — small icosphere body (radius ≈ 0.4), two small cones/spheres on top for horns, two small flat cylinders at the bottom for feet. Single material per actor (cheaper than per-feature materials; matches Coily snake's authoring).

### Side-face positioning and rotation — in scope

Arcade Ugg/Wrong-Way appear to stand on the *side faces* of the pyramid cubes with gravity rotated 90°. The 3D-faithful version puts them on the appropriate cube side face:

- **Ugg (right edge)**: sits on the +X face of cube `(r, r)`. World X is offset outward by `+CUBE_SIZE/2 + UGG_HALF_THICKNESS`; the body is yaw-rotated so "up" points in +X (feet on the cube face).
- **Wrong-Way (left edge)**: sits on the −X face of cube `(r, 0)`. World X is offset by `−CUBE_SIZE/2 − WW_HALF_THICKNESS`; body yaw-rotated so "up" points in −X.

Z position: at the vertical midpoint of the cube face (cube_centre_Z, not cube_top + half_body). The script's per-tick X/Y/Z writes therefore use the same row/col formulas plus a per-variant offset baked in.

Rotation is written once at spawn-time via the director (yaw to ROTATION_C / mb 3014) since Ugg/WW orientation never changes during a hop — they always face the cube they're climbing. No per-tick rotation write needed.

### Director additions

A mostly-cloned spawn block from Slick/Sam, except the initial spawn-cube differs per variant:

- Ugg: `ROW := 6, COL := 6, FROM_ROW := 7, FROM_COL := 7` (lerps in from below the bottom-right)
- WW:  `ROW := 6, COL := 0, FROM_ROW := 7, FROM_COL := 0`

Z computation:
- Bottom row is at `_RB_Z_BASE - 6 * _RB_Z_MUL = 14.5 - 12 = 2.5`
- Spawn `START_Z = _RB_Z_BASE - 7 * _RB_Z_MUL = 0.5` (one row below the bottom — they appear to "climb up onto" the bottom row)
- `END_Z = 2.5`

The freeze-gate is shared with the rest of the redball variants, so a green-ball touch pauses Ugg/WW too.

Round-clear refresh: retire both, rearm spawn timers.

## Critical files

| File | Change |
|---|---|
| [`wflevels/qbert_practice/blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py) | (a) Add `UGG_*` / `WW_*` constants including the per-variant X-offset and yaw. (b) Build `_climber_build_mesh(horn_height, …)` returning verts/faces — small icosphere body + 2 horn cones + 2 foot discs; produce 2 distinct meshes (Ugg orange, WW purple). (c) Extend `redball_script(k, variant)` with `variant in {'ugg','wrongway'}`: new entries in `flat_bases`; parameterise the landing-tick direction picker, the retire-threshold (`6 >` vs `0 <`), and the per-variant X-offset added to the world-X write. (d) Create 1 Ugg + 1 WW actor with captured `UGG_ACTOR_IDX` / `WW_ACTOR_IDX`. (e) Director: spawn blocks (cloned from Slick/Sam loop, with different starting `(row, col)` and Z) that also write the per-variant yaw to mb 3014 at activation; level-init arm; round-clear refresh. |
| (no engine changes) | Hop pipeline, FACE_COLOR, write-actor-mailbox, freeze-gate all reused. |

## Verification

### Phase A (Ugg)
1. Build + boot; ~20 s after intro a small orange-hat actor appears at the bottom-right cube `(6, 6)`.
2. Each hop ascends one step toward the apex along the right edge: `(6,6) → (5,5) → ... → (0,0)`. Cadence matches REDBALL_HOP_TICKS (18 ticks ≈ 0.3 s).
3. Drive Q*bert into Ugg's path: expect FALL_DEATH latch (mb 414=1), cs_death camshot, lives decrement.
4. Off-apex retire: when Ugg's next ROW would be `-1`, the existing retire path fires (PHASE=0, park).
5. Regression: red balls, green ball, Coily egg/snake, Slick/Sam all unchanged.

### Phase B (Wrong-Way)
1. ~30 s after intro a purple-hat actor appears at the bottom-left cube `(6, 0)`.
2. Hops up the left edge: `(6,0) → (5,0) → ... → (0,0)` at the same cadence.
3. Same kill-on-contact + apex-retire as Ugg.
4. Ugg and WW can coexist (different actors, independent timers).

### Regression
- FREEZE_TIMER from green-ball touch pauses both climbers (shared freeze-gate).
- Round-clear retires both; spawn timers re-arm to first-delay.

## Commit sequence

1. `feat(qbert): Ugg — orange climber up the right edge`
2. `feat(qbert): Wrong-Way — purple climber up the left edge`

## Out of scope (v2 polish)

- **Edge fall-off mechanic** — Q*bert hopping diagonally toward the edge Ugg/WW is on can shove them off (arcade behaviour). Deferred to a separate plan since it couples player movement with enemy retire.
- **Per-round spawn-rate scaling** — flat cadences for now; arcade ramps frequency by level.
- **Coexistence rules** — arcade has constraints on which enemies spawn simultaneously (e.g. no Ugg + WW at the same time as Coily). Defer to a spawn-orchestrator pass once all enemies exist.
