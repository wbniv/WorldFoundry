# Cuckoo Village: flickering candle flames

**Status:** proposal for review, 2026-11-22. Nothing is in the level yet. The mockups below are drawn from the level's real candle positions and the proposed rule, run live; they are not engine captures. The flicker rule is measured by the script that draws them, [`scripts/mockup-candle-flicker.py`](../../scripts/mockup-candle-flicker.py).

## Context

Will asked how the candle flames flicker (2026-11-22). They do not. Each tree carries ten candles, and today the flames of one tree are **one static mesh** (`candle_flames_NN`, ten diamonds of 8 triangles, 80 triangles) whose only input is a visibility mailbox, cells 215 to 226. The director switches it on at dusk and off at dawn ([`forth.py`](../../wflevels/cuckoo_village/forth.py) `cv-flames`), so a lit flame is the same shape in every frame. A Christmas tree full of candles that never move looks like a string of lamps.

The village already moves a great deal, all of it driven by the director from the wall clock: the clock's hands, the parade figures on the hour, the cuckoo bird and the window lights. The engine can also **deform** a mesh: the `DFRM` chunk bends a rooted curve under script control, and version 2 carries up to 16 curves in one mesh, each with its own scale, clip and flex bias ([`dfrm_deform.h`](../../wfsource/source/renderassets/dfrm_deform.h)). What limits a flickering flame is therefore not that bending is impossible but what each way **costs a frame on cast1**, where the village already runs at 30 fps. Two ways are described below, and the plan's first step is to measure them against each other before building either.

## Approach

### Option A: swap between two built shapes (visibility only)

No new engine machinery: it costs what the village's other switched actors cost, the director writing visibility cells.

**Two shapes, two groups, one rule.** Each flame is built in two shapes: **shape 1**, tall and leaning toward a fixed draught direction (the world +X axis), and **shape 2**, short and leaning the other way. The ten candles of a tree already come in two sets of five, `j = 0` and `j = 1` of [`candle_bases`](../../wflevels/cuckoo_village/candles.py), standing on opposite sides of the trunk; those are **group A** and **group B**. Each tree therefore gets four flame meshes (A1, A2, B1, B2) in place of today's one, and at any moment exactly one of A1 or A2, and one of B1 or B2, is visible when the tree is lit.

[![the flame poses, the ten candles and the four actors](2026-11-22-cuckoo-village-candle-flicker/flame-shapes.png)](2026-11-22-cuckoo-village-candle-flicker/flame-shapes.html)

| Pose | Height | Ring radius | Tip leans | Triangles |
|---|---|---|---|---|
| Today (static) | 75 mm | 22 mm | 0 | 8 |
| Shape 1: tall | 90 mm | 20 mm | +14 mm toward the draught | 8 |
| Shape 2: short | 60 mm | 24 mm | −10 mm away from it | 8 |

**The rule.** For tree `i` and group `g`, with the phase `p = frac((2i + g) × 0.618034)` and `t` the director's second of the minute (`cv-sc`, which carries the fraction of a second):

```
shape 1 when  sin(2π(2.3 t + p)) + sin(2π(3.7 t + 2p)) > 0,   otherwise shape 2
```

Two sines of unrelated rates added together cross zero at irregular intervals, so the flicker has no beat. 2.3 and 3.7 revolutions a second are **whole cycles in a minute** (138 and 222), so the pattern is continuous where the second of the minute wraps from 59.99 to 0, the same rule Tide Harbour's glints follow. Measured over 60 s of the real rule for all 24 groups: **7.38 shape changes a second per group, 136 ms between changes on average, about 4 frames at 30 fps**. The 24 phases all differ, so no two groups, and so no two sides of a tree, move together.

[![the schedule, one tree in three frames, the flame's size on screen](2026-11-22-cuckoo-village-candle-flicker/flicker-schedule.png)](2026-11-22-cuckoo-village-candle-flicker/flicker-schedule.html)

```mermaid
flowchart TD
    T["cv-tick, every frame"] --> S["cv-sc: second of the minute<br/>(latched with WALL_HOUR)"]
    T --> L["lit: candles show AND window glow of house i mod 13"]
    S --> R["for each of 24 groups:<br/>x = sin(2π(2.3 t + p)) + sin(2π(3.7 t + 2p))"]
    R --> P{"x &gt; 0 ?"}
    L --> W
    P -- yes --> W["write lit × 1 to the shape 1 cell<br/>write 0 to the shape 2 cell"]
    P -- no --> V["write 0 to the shape 1 cell<br/>write lit × 1 to the shape 2 cell"]
    W --> M["visibility mailboxes 232 to 279"]
    V --> M
    M --> D["render loop skips hidden actors:<br/>one shape per group is drawn"]
```

**Lit stays today's rule.** A group draws only while the candles show (1 December to 6 January, or Candles all year) and the glow of house `i mod 13` is on, so the Window lights setting still puts every flame out, and a tree's flames still come on with its own stagger at dusk. Only the choice *between* the two shapes is new.

```mermaid
stateDiagram-v2
    [*] --> Unlit
    Unlit --> Shape1: lit and x above 0
    Unlit --> Shape2: lit and x at or below 0
    Shape1 --> Shape2: x crosses zero downward<br/>(about every 136 ms)
    Shape2 --> Shape1: x crosses zero upward
    Shape1 --> Unlit: dawn, season over, or Window lights Off
    Shape2 --> Unlit: dawn, season over, or Window lights Off
```

**Build.** In [`candles.py`](../../wflevels/cuckoo_village/candles.py) `flame()` takes a height, a ring radius and a lean, and `tree_candles` returns the flames split by group and pose. In [`blender_create_cuckoo_village.py`](../../wflevels/cuckoo_village/blender_create_cuckoo_village.py) each tree makes `candle_flames_a1_NN`, `a2`, `b1`, `b2`, each a static mesh actor with one visibility mailbox: `FLICKER_CELL0 + 4i + k`, with `FLICKER_CELL0 = 232` and `k` = 0 to 3 for A1, A2, B1, B2. The twelve cells 215 to 226 stop being flame cells and are freed. Cells 232 to 279 are free today: the glow is 200 to 213, the candle sticks 214, the flowers 227 and 228, Bavaria 230 and 231, and the director's scratch cells start at 600.

```mermaid
flowchart LR
    C["candles.py<br/>flame(height, radius, lean)"] --> G["tree_candles(i)<br/>split by group j and pose"]
    G --> B["blender_create_cuckoo_village.py<br/>4 × mesh_actor per tree"]
    B --> A["candle_flames_a1…b2_NN<br/>48 actors, cells 232–279"]
    F["forth.py cv-flames<br/>24 group rules"] --> A
    TL["timeline.py<br/>FLICKER_CELL0, rule constants"] --> C
    TL --> F
    TL --> TST["test_cuckoo_village_candles.py<br/>verify_cuckoo_village_forth.py"]
```

**Director.** `cv-flames` is rewritten: the loop runs over the 24 groups, works out `x`, and writes the pair of cells. Because `timeline.py` is the reference model (it already holds `christmas_season` and the cell numbers), the rule is written there first as `flame_shape(t, tree, group)`, and the director's words are checked against it in the real zForth VM like every other cell.

```mermaid
sequenceDiagram
    participant E as Engine frame
    participant D as Director (cv-tick)
    participant C as Mailbox cells
    participant R as Render loop
    E->>D: update, WALL_SECOND latched
    D->>D: cv-candles: season or Candles all year
    D->>D: cv-wins: window glow cells 200 to 212
    loop 24 groups
        D->>D: x from t and the group's phase
        D->>C: shape 1 cell and shape 2 cell (one is 1 when lit)
    end
    E->>R: draw
    R->>C: isVisible per actor
    R-->>E: 12 trees × 2 groups × 1 shape drawn
```

### Option B: a deformed flame (`DFRM`)

Each tree's ten flames become **one `DFRM` v2 mesh with ten short curves**, one curve per flame (the format allows 16 a mesh). Each flame is a few rooted samples; the director writes each curve's **flex bias** (cell `40 + 4c` of the mesh's control block, degrees added to every sample of that curve) and, if wanted, its **scale** about its root, every frame, from the same kind of two-sine rule. A flame then sways and stretches smoothly instead of snapping between two shapes, and the flicker needs no extra actors: 12 deformed meshes replace 12 static ones, and the 36 extra actors and 36 extra cells of Option A are not needed.

What is **known**: the format and its evaluator exist and are tested (`dfrm_deform.h`); one pose row can drive every curve; a curve's bias and scale are separate script cells. What is **not known**, and is the reason for the first verification step:

- **The frame cost on cast1.** The measured numbers are for much larger meshes: Seahorse Grid reaches 29.6 FPS with 24 deforming meshes, and the six-pair seahorse comparison puts CPU `DFRM` at 47 to 69 ms a presented frame ([reef plan](2026-11-02-gulf-of-thailand-reef-tank.md), [seahorse comparison](2026-10-16-saltwater-seahorses/comparison.md)). A flame mesh is about 60 vertices a tree, far smaller, but the evaluator's per-mesh cost (pose, skin, upload, cull) may not scale down with the vertex count. The village sits at 30 fps (33.4 ms) already, so there is almost no headroom to spend.
- **The authoring path.** The exporter and `dfrm_ref.py` were built for tails and fish. A tree's ten flames as ten curves of one mesh is a new rig to author and to check in `dfrm_ref.py`.
- **The size of the effect.** A flame is 4 to 11 px tall on screen (below), so a smooth sway and a two-shape swap may look much the same at the Chromecast's distance. Smooth only wins if it is visible.

GPU skinning ([plan](2026-10-16-gpu-skinning-chromecast-experiment.md)) would make Option B cheap if it is ever adopted, but it is not built, so it is not counted on here.

**How to choose.** A short spike, on one tree: build the ten-curve flame mesh, drive its biases from the rule, and run the variant benchmark below on cast1 with all 12 trees against Option A's 48 actors. Option B is adopted only if it passes the gate in verification step 0 (CPU total from the engine's frame profile, not present intervals); otherwise Option A is built. The rest of this plan specifies Option A, which needs no new machinery; Option B replaces its Build and Director sections and shares everything else.

## Decisions for Will

1. **A or B?** Recommended: **measure first** (the spike above, about a day), then take B only if it is cheap and visibly better; A is the safe default and is a day of work on its own.
2. **Does the flicker stop under Camera motion Still?** Recommended: **no**. That setting stills the camera path (it exists so a screen is not always moving for burn-in), not candlelight, and a still camera is where a motionless tree would be most noticed. If a still screen should stay still for burn-in's sake, the rule gets one extra factor and the cost is nil.
3. **Does it slow down or stop at a low frame rate?** Recommended: **no**. The rule is a function of the clock, not of frame count, so at 30 fps it is sampled every 33 ms and at 15 fps every 67 ms, still changing about every other sample. Nothing accumulates and nothing needs to catch up.
4. **A new setting?** Recommended: **none** now. The flicker is not luminance: both shapes are the same flat colour, so nothing flashes, and each change is a few pixels (below). If a reduced-motion switch is wanted later it is one more field like Detailed flowers.
5. **Two shapes or three?** (Option A only.) Recommended: **two**. A third, upright and mid-height, makes the flicker softer but costs 24 more actors and another 24 cells; the mockup's schedule shows two shapes already give irregular motion.
6. **The rate.** 7.4 changes a second per group is lively. A calmer pair, 1.3 and 2.1 revolutions a second (78 and 126 a minute), gives about 4 a second. Recommended: start at 2.3 and 3.7, judge it on cast1, and slow it if it reads as nervous. The numbers are constants in `timeline.py`.

## Budgets

| | Today | Option A | Option B (to be measured) |
|---|---|---|---|
| Flame actors | 12 | 48 (+36) | 12 |
| Flame triangles in the level | 960 | 3,840 (every shape of every flame is in the level) | 960 (one shape, bent) |
| Flame triangles drawn | 960 | 960 (one shape per group is visible; hidden actors are skipped) | 960 |
| Flame visibility cells | 12 (215–226) | 48 (232–279) | 12, plus 10 curve cells each in the mesh's control block |
| Level size | | about +40 KB (36 mesh actors); measured at build, see the note below | about the same as today, plus the deformer chunk |
| Director work per frame | 12 cell writes | 48 cell writes and 24 × two sines | 120 curve writes and 120 × two sines |
| Renderer and deformer cost on cast1 | none new | none new (hidden actors are skipped) | **unknown**: 12 more deformed meshes against a village already at 33.4 ms |

**On screen the flames are small.** At 1080p with the 60° view, a flame is 11 px tall and 7 px wide at the village's nearest camera distance (6.3 m) and 4 px by 3 px at the farthest (16 m). The change from shape 1 to shape 2 is a height change of 30 mm and a lean of 24 mm: 4 px at the nearest, 2 px at the farthest. At the far end of the orbit the effect is a **twinkle** of single pixels, not a visible waving flame; at the front of the orbit, and on a tablet held close or a phone, it reads as a flame. That is the cost of a candle being 75 mm tall in a village built at 1:1. If it proves too faint at distance, the lever is the lean and height difference (a larger swing, drawn only for the tall pose), not a faster rate.

**Level size.** The flowers plan's size budget already misses its step by 0.006 MB; this adds about 40 KB. The size gate has to be re-set deliberately when this lands rather than passed by a coincidence, and the figure recorded in the result paragraph.

## Out of scope

- **Light from the flames.** There is no light control in the engine (Will's earlier direction), so the glow on the pine is not a thing.
- **Sparks, smoke, a wind that moves the whole tree.** Not at this size.
- **The date range and other December events.** They have their own TODO items.
- **A level-of-detail replacement of the flames.** [The flowers LOD plan](2026-11-22-cuckoo-village-flowers-lod.md) covers geometry that is replaced by distance; if it lands, the flames join it.

## Judging them by eye

Will wants to see how the variants **look**, not only what they cost (2026‑11‑22: "profiles but also video clips (on trees) plus a near study in order to compare how they LOOK"). So the spike produces, for each of today, A and B, with the same clock, the same camera and Candles all year On:

- **Clips on the trees.** A 10 s clip, recorded on cast1 (the real Chromecast pixels, 30 fps) of the village's own camera as it passes the pines, one clip per variant. On the desktop engine the same moment is also recorded with `-record_video` at 1920 × 1080 where cast1's 1280 × 720 is too coarse to judge. The clock is frozen at the same wall time (`WF_WALL_CLOCK`) so every variant shows the same sky and the same lit trees.
- **A near study.** The same flames from 1.5 m away, so a flame is about 60 px tall rather than 4 to 11. A study build puts the camera at a fixed spot facing one pine (a camera override in the variant builds only; the shipped level is untouched). Recorded for 10 s per variant, plus **a strip of 8 consecutive frames** (33 ms apart at 30 fps) cut from it, which shows whether a swap reads as a flicker or as a blink.
- **A comparison page.** One HTML page with the three clips of each kind side by side and started together, and the three strips one above another, linked from the report.

[![the look comparison: clips on the trees, the near study and a frame strip, today against A against B](2026-11-22-cuckoo-village-candle-flicker/look-comparison.png)](2026-11-22-cuckoo-village-candle-flicker/look-comparison.html)

The mockup is drawn from the proposed rules, not from the engine: the real clips replace it in the report. The look decides between A and B (the gate's last clause), and Will may reject both on sight even if the numbers pass.

## Verification

0. **The choice, measured and looked at first.** Three frozen cast1 builds of the village in season (Candles all year On), identical but for the flames: **today** (12 static flame meshes), **A** (48 actors, the director's 24 rules) and **B** (12 `DFRM` meshes of ten curves, driven from the same rule). They run through the coordinator's `variant-benchmark` workflow with the engine's `--frame-profile`, as the [seahorse population comparison](../diagnostics/seahorse-population-cast1-20261017/README.md) did: 60 s of the village after a 15 s warm-up, three runs each in varying order, reading the **main-thread CPU total (update plus render)** and the director section. The plain `profile` job is not enough here: it reports present intervals, and the village sits locked at 33.4 ms (30 fps), so a change of a tenth of a millisecond cannot show in it; it is kept as a guard that nothing drops below 30 fps. **Adopt** a variant only if its CPU total rises by less than 0.25 ms over today and the floor stays at 30 fps; **choose B over A** only if B is within 0.1 ms of A (or cheaper) **and** a capture at the nearest view shows a visibly better flame; otherwise build A. **The look is gathered in the same session**: the tree clips, the near study, its 8-frame strip and the comparison page of [Judging them by eye](#judging-them-by-eye), with the cast1 job ids and file hashes in the report. Steps 1 to 8 are written for A and are adapted for B (the cells become curve biases).
1. **The shapes.** `tests/test_cuckoo_village_candles.py` gains: each tree has four flame meshes; groups A and B hold five candles each, from `j = 0` and `j = 1`; every flame is 8 triangles in both shapes; the heights, radii and leans are the table's; the two shapes of a candle share its foot.
2. **The rule in the model.** A test of `timeline.flame_shape` over 60 s at 600 samples a second for all 24 groups: between 7 and 8 changes a second per group, a mean of 120 to 150 ms between changes, the pattern identical one minute apart, no two groups with the same phase.
3. **The director, in the real VM.** `tests/verify_cuckoo_village_forth.py` sets `WALL_SECOND` to a spread of values with the candles in season and the glow on: for each group exactly one of its two cells is 1 and the cell equals `timeline.flame_shape`; out of season, with Candles all year Off, both are 0; with Window lights Off, both are 0 for every group; with Candles all year On in July, the pairs follow the rule.
4. **The level.** The rebuilt level has 48 flame actors, each with its cell, and none left on cells 215 to 226; the level-size gate is re-set and its figure recorded.
5. **The desktop engine.** With the clock frozen at 10 consecutive frames at one tree's nearest view, a capture sequence shows the flames' pixels differing between frames: the count of changed pixels inside each flame's box is above 0 on at least half of the frame pairs, and 0 anywhere outside the flames.
6. **Not in step.** In the same sequence, at least 5 of the 12 trees change shape on a frame where at least 5 others do not.
7. **The frame cost.** The step 0 numbers for the chosen variant, plus the coordinator `profile` job as a guard: the floor is unchanged (30 fps, 33.4 ms).
8. **The Chromecast and the phone.** A cast1 `record` of the village in season, and a Pixel screenshot pair 100 ms apart: the flames differ, and nothing else in the picture moves.

## Who

The village session owns this: `candles.py`, the build script, `timeline.py` and `forth.py` for Cuckoo Village. It touches no engine file and no other level; Option B would add a `DFRM` rig for the flames and would need `dfrm_ref.py` and the exporter checked for a many-short-curves mesh, which is why it is measured before it is chosen. It lands after the display-mailboxes commits, which are unrelated; whoever builds the next Cuckoo Village level (the Show framerate setting changes `settings.inc` and forces a rebuild) should include it.
