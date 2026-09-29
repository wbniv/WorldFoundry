# Aquarium level — 55 gal acrylic tank, one clownfish, one anemone

Status: **plan only — nothing built yet.** Phase 0 is a runtime spike whose result decides how the acrylic looks.

Will asked for an aquarium level: a **55 gallon acrylic tank**, **an anemone and a clownfish**, planned in
`docs/plans/` with mockups. The condo walkthrough went through the Blender → `.lev` → `.iff` pipeline first try, so this
plan reuses that pipeline unchanged and spends its risk budget on the three things a fish tank has that a condo does not:
**see-through walls, a player that swims, and a very small world.**

- [ ] Phase 0 — translucency spike (does an acrylic pane work?)
- [ ] Phase 1 — swim and scale spike (does a gravity-free fish work, at ×1 or ×10?)
- [ ] Phase 2 — tank, sand, rock, anemone, lighting, fog
- [ ] Phase 3 — clownfish mesh, controls, camera zones
- [ ] Phase 4 — anemone sway (optional), docs, tasks, regression test

## Mockups

All three are 1440×900 live HTML with a same-name PNG. They are **proposals**, drawn in the engine's flat-shaded low-poly
style; none of it is a screenshot of a running build.

[![Tank dimensions — front, side and top, real inches and level metres](2026-09-30-aquarium-level/tank-dimensions.png)](2026-09-30-aquarium-level/tank-dimensions.html)

[![Swimming and hosting — default side-on camera, and the anemone close-up](2026-09-30-aquarium-level/gameplay-states.png)](2026-09-30-aquarium-level/gameplay-states.html)

[![Acrylic pane options, the Phase 0 test card, and a phone-landscape touch layout](2026-09-30-aquarium-level/pane-fallbacks.png)](2026-09-30-aquarium-level/pane-fallbacks.html)

States shown: default view, anemone close-up, three pane options (one deliberately rejected), the Phase 0 pass and fail
test cards, and a narrow phone-landscape layout. There is no empty or error state because the level has no UI to be empty.

## What the repo already tells us (evidence)

| # | Finding | Source |
|---|---|---|
| E1 | Level pipeline is `blender_create_<level>.py` → `<level>.lev` → `build_level_binary.sh` → `wflevels/<level>-standalone.iff`; `task run-level` runs it. Condo is the closest working template. | [`condo_639_640.md`](../../wflevels/condo_639_640/condo_639_640.md), `Taskfile.yml` `condo-level` |
| E2 | `statplat` actors with `Model Type = Mesh` get a **Jolt trimesh body from their render mesh**, built from raw local verts (bake scale and rotation into the mesh first). So a tank shell with an open interior is solid on the outside and hollow inside for free. | [condo plan](2026-09-19-condo-639-640-level.md) |
| E3 | Actors that can run scripts (anchored `Platform`/`Target`, `Physics`) do **not** get a trimesh; StatPlats cannot have scripts. The condo therefore moves its door panels from the Director with `write-actor-mailbox`. | `blender_create_condo.py` §7c |
| E4 | Mailboxes `X_POS/Y_POS/Z_POS`, `ROTATION_A/B/C`, `XSPEED/YSPEED/ZSPEED`, `INPUT`, `CAMSHOT` exist. The condo already writes speeds and `CAMSHOT` from Forth. | [`mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc) |
| E5 | **Fog is per-level** (`camera` actor's three fog fields). A water tint is a fog setting, and the snowgoons default (`0x888888`, 20→30 m) must be overridden. | [level-building § Fog](../level-building.md) |
| E6 | Jolt's character capsule is sized from the mesh's `ColSpace` box, so a small fish mesh yields a small capsule. Whether Jolt behaves at 9 cm is untested. | `jolt_backend.cc:613` |
| E7 | **Correction:** the condo doc said "`MATL` has no alpha; glass must be opaque". Half true. Flat-colour materials have no alpha, but **textured** materials do support translucency: a 16-bit BGR555 TGA texel with bit 15 set becomes alpha 128 (`pixelmap.cc:190`), `material.cc:124` flags the material `TEXTURE_TRANSLUCENCY_HALF_BACK_HALF_PRIMITIVE`, and `display.cc:669` enables `GL_BLEND`. Fixed in [`condo_639_640.md`](../../wflevels/condo_639_640/condo_639_640.md) on 2026‑09‑30. **Read from code, not yet run.** | see left |
| E8 | 32-bit RGBA TGAs are a trap (`rgba_555` maps opaque to `0x0000`, "fully transparent"). Author 16-bit BGR555 directly, or 24-bit RGB for opaque textures. | [troubleshooting](../level-design-troubleshooting.md) |

## The tank, exactly

A "55 gallon" tank is a nominal size. The standard footprint is 48 × 13 × 21 in (exterior). Acrylic 55s use ½ in walls;
the numbers below are computed, not looked up, so the level and the docs can share one set of constants.

| Quantity | Value |
|---|---|
| Exterior | 48 × 13 × 21 in = 121.9 × 33.0 × 53.3 cm |
| Acrylic thickness (all faces) | 0.5 in = 12.7 mm |
| Interior | 47 × 12 × 20.5 in = 119.4 × 30.5 × 52.1 cm |
| Volume, exterior | 13 104 in³ = **56.7 gal** (the "55") |
| Volume, interior to the brim | 11 562 in³ = 50.1 gal |
| Operating fill, water 19 in above the outer base (2 in freeboard) | 47 × 12 × 18.5 = 10 434 in³ = **45.2 gal = 171 L** |
| Sand | 2 in deep, top at 2.5 in above the outer base (displaces roughly 3 gal; not modelled) |

Anemone: bubble-tip (*Entacmaea quadricolor*), about 7 in across. Clownfish: ocellaris (*Amphiprion ocellaris*), about
3.5 in, orange with three white bands edged in black (head, mid, tail base) and black-edged fins. Ocellaris hosting in a
bubble-tip is the natural pairing, and it is what the second camera zone dramatises.

## Scale decision: author at ×10, verify against ×1 first

One WF unit is one metre and the engine is tuned for a 1.7 m walker: camera clip, capsule, fog ranges, speeds, the
condo's proven `Running Acceleration` calibration. A 9 cm fish at 1:1 sits below all of that.

**Decision:** a single `WORLD_SCALE = 10` constant in the Blender script. At ×10 the tank is 12.19 × 3.30 × 5.33 m, the
fish 0.89 m, the anemone 1.8 m. Every derived number (fog, camera offsets, speeds) is written as a multiple of it, so the
choice is one line, not a rewrite. **Phase 1 tests ×1 and ×10 before Phase 2 depends on either.** If ×1 turns out to
work, the plan switches to ×1 with no other change.

Coordinates (X right, Y depth, Z up, per the project convention). Origin is the centre of the tank's floor footprint:

| Thing | ×10 position (m) |
|---|---|
| Tank exterior | x ±6.096, y ±1.651, z 0 → 5.334 |
| Interior floor / walls | z 0.127 up; x ±5.969; y ±1.524 |
| Sand top | z 0.635 |
| Water line | z 4.826 |
| Rock | base on sand at x +2.5, y 0 |
| Anemone | on the rock, x +2.5, y 0 (base at local z = 0) |
| Fish spawn | x −1.6, y 0, z 2.4 |
| Front-glass camera | y ≈ −11, aimed at the tank centre (tuned in Phase 3) |

## Approach

### 1. Files

| File | Purpose |
|---|---|
| `wflevels/aquarium/blender_create_aquarium.py` | Headless Blender build, same shape as `blender_create_moon.py` / `blender_create_condo.py`: import the snowgoons scaffold, strip to one of each infrastructure class, add geometry, export. |
| `wflevels/aquarium/aquarium_constants.py` | The table above as code: inches, `WORLD_SCALE`, derived metres. Imported by the build script **and** the regression test, so the docs, the level and the test cannot drift. |
| `wflevels/aquarium/make_pane_texture.py` | Writes the pane's 16-bit BGR555 TGA (bit 15 set) deterministically. |
| `wflevels/aquarium/aquarium.md` | Level README: build/run, controls, what is and is not modelled. |
| `Taskfile.yml` | `aquarium-level` and `run-aquarium`, cloned from the condo entries, with `deps` on the tool build and the texture task so nothing needs a manual pre-step. |
| `tests/test_aquarium_level.py` | Regression guard (see § Regression guard). |

### 2. Actors

| Actor name | Class / mobility | Mesh | Notes |
|---|---|---|---|
| `Player` (clownfish) | `Physics` | `clownfish` | Gravity 0, script-driven speeds, see § 4 |
| `tank-shell` | `statplat`, Mesh | bottom, back wall and two end walls; open at the front and top | Trimesh body keeps the fish inside. Acrylic faces, flat pale cyan |
| `tank-front-pane` | `statplat`, Mesh | one quad, thin | **Translucent, textured.** No collision needed, but it gets one from E2; the shell's own front lip stops the fish first |
| `tank-rim` | `statplat`, Mesh | top perimeter bevel | Reads as a tank edge even if the pane fails (Plan B) |
| `sand`, `rock` | `statplat`, Mesh | flat-shaded low poly | Rock base at local z = 0 (mesh-origin rule) |
| `anemone` | `statplat`, Mesh | base, column, tentacles | Static in v1, see § 5 |
| `anemone-zone` | `target` | none | Invisible; carries the zone bbox (condo room-outline pattern) |
| `water-surface` | `statplat`, Mesh | one quad at the water line | Translucent, prelit |
| `room-backdrop`, `stand` | `statplat`, Mesh | dark quads | So the camera never sees the void |
| `Director`, `camera`, `levelobj`, `matte`, `light`s, `room`, `camshot`s | scaffold classes | | One of each; **rename the survivors** so no snowgoons `player_33`/`target_14` name leaks into an object reference |

### 3. The acrylic — the fallback ladder

The pane is the level's identity, so it is decided by measurement, not hope:

1. **Plan A (preferred):** `tank-front-pane` carries a small textured material whose texels have bit 15 set, so it draws at
   about 50 %. The pane is tinted very slightly blue to double as "the water". End and back faces are the same material.
2. **Plan B:** leave the front face out entirely. The four acrylic edges, the rim, the bevel highlights and a blue back film
   still read as a tank, and the fish is never occluded. Fully within the engine as it is today.
3. **Plan C (rejected, shown in the mockup so nobody reinvents it):** an opaque tinted pane hides the fish and the anemone.
   It survives only for the side and back faces, which the camera never looks through.

Plan A's risk is not that translucency is missing (E7) but that translucent polygons are drawn **with depth writes and in
scene order**, so a pane drawn before the fish would hide it. Phase 0 tests exactly that, and tests the fix (draw order
by actor order in the `.lev`) before any modelling is invested.

### 4. The clownfish (player)

A `Physics` actor: it is the one class that both scripts and collides. It is a kinematic Jolt `CharacterVirtual`, so the
tank shell's trimesh contains it without any extra collision authoring.

| Field | Value | Reason |
|---|---|---|
| `Falling Acceleration` | 0 | Neutral buoyancy. Phase 1 must confirm the character controller then holds altitude |
| `Script Controls Input` | True | As the condo: the script owns `INPUT` and the speed mailboxes |
| `Turn Rate` | 0 | Heading is set by the script, not by the joystick |
| `Mass` | ~1 (scaled) | Irrelevant to a kinematic character; kept small |
| `wf_original_bbox` | **deleted** | Otherwise the imported snowgoons 2 m capsule wins (condo hit exactly this) |

Controls reuse the existing logical buttons; **no engine or host change** (same rule the condo camera plan set):

| Input | Action |
|---|---|
| Arrows / D-pad | Swim left/right and up/down; heading turns to face travel |
| B (`2`) / C (`3`) held | Swim toward / away from the glass (Y) |
| A (`1`) | Dart: a short speed burst, then glide |

Each frame the script reads `JOYSTICK1_RAW`, maps directions to `XSPEED` / `ZSPEED` (and `YSPEED` on B/C), damps toward
zero for the glide, writes `ROTATION_C` to face the direction of travel, and clamps `Z` under the water line so the fish
cannot leave the water. Phase 1 confirms that `ROTATION_C` writes take effect on a `Physics` actor.

### 5. The anemone

Static mesh in v1: a flat-shaded base, a column, and ~17 tentacles, each a two-tone tapered strip with a bulb tip (the
"bubble tip"). Two authoring rules for the hosting shot: tentacles are **split into a back set and a front set** in the
mesh so the fish, sitting between them, is naturally overlapped — no engine layering; and every tentacle keeps its base at
the local origin plane.

**Optional v2 (Phase 4):** swaying tentacles. Tentacle clumps become separate anchored actors moved from the Director with
`write-actor-mailbox`, like the condo doors, on a sine of level time. Ships only if it costs no framerate and the clumps
do not shear against the base.

### 6. Camera

Two camshots, same mechanism the condo uses for its window/patio zones (Director reads the fish's `X_POS/Y_POS/Z_POS`
and writes `CAMSHOT`):

- **A — front glass (default):** locked, straight-on, whole tank in frame.
- **B — anemone close-up:** selected inside `anemone-zone` (radius about 2.2 m at ×10).

Both cameras sit **outside** the tank, looking through the front. That avoids the bungee camera's habit of climbing when its
box overlaps a shell (recorded in the condo camera plan), and it is why Plan B (no front pane) costs nothing to the camera.
Distances are starting values, tuned in Phase 3 from captured frames.

### 7. Lighting and water

Every level needs a Directional **and** an Ambient light. Overhead directional, cool ambient. Fog is the water: teal,
`FoggingColor ≈ 0x0d5f7a`, start about 6 m, complete about 40 m at ×10 (both scale with `WORLD_SCALE`). Fog is by distance,
not by medium, so it also tints the dark room slightly; that is accepted, and the room is dark enough not to care.
`FoggingCompleteDistance` past 1000 m would disable fog, which is not what is wanted here.

## Verification

Steps are the spec; the output is the evidence. Each is filled in when run: raw output in a block, then PASS/FAIL.

**Phase 0 — translucency**

1. Build the test card: two `statplat` quads (checkerboard backdrop and a bit‑15 pane), one fish-shaped mesh behind the pane and one in front. Expected: level builds, `textile` log lists the pane texture with `Translucent = yes`.
2. Run with `-rate20 --capture-frame=30` and open the PNG. Expected: the far fish is visible through the pane at about 50 %; the near fish is not clipped.
3. Swap the two fish's order in the `.lev` and re-run. Expected: the result tells us whether draw order matters. If a fish is hidden or clipped in either order, record which, and pick Plan B.
4. Sample a pixel where the pane overlaps the checkerboard. Expected: the value is the arithmetic mean of pane and background colour within ±8 per channel.

**Phase 1 — swim and scale**

5. Minimal level: an open box (statplat mesh), one `Physics` fish, `Falling Acceleration` 0. Expected: with no input the fish holds altitude for 10 s (Z changes < 1 % of tank height).
6. Drive `ZSPEED` from Forth. Expected: the fish rises and stops at a Z clamp under the water line; it does not pass through the sand or the walls.
7. Write `ROTATION_C` from Forth. Expected: the mesh's heading changes on screen. If not, the recorded fallback is `Turn Rate` > 0.
8. Repeat 5–7 at ×1 and at ×10. Expected: ×10 passes all three; record what ×1 does. The winner becomes `WORLD_SCALE`.

**Phase 2–3 — level**

9. `task aquarium-level` from a clean checkout. Expected: builds with no manual pre-step, and is a no-op on the second run.
10. `python3 -m pytest tests/test_aquarium_level.py`. Expected: pass (see § Regression guard).
11. `task run-aquarium`; capture frame A. Expected: the whole tank in frame, fish visible, no z-fighting on the acrylic rims, water colour in the range of mockup A.
12. Swim into the anemone zone; capture frame B. Expected: the close-up camshot engages, and the fish is partly overlapped by front tentacles.
13. Hold each direction into every wall for 5 s. Expected: the fish never leaves the tank volume.
14. Run on a phone-landscape build with the touch profile. Expected: swim and dart reachable with existing A/B + D-pad regions. **Unverified on hardware; report, do not claim.**

## Regression guard

`tests/test_aquarium_level.py`, in the same commit as the level, reading `aquarium_constants.py`:

- the exported shell's bounding box is 48 × 13 × 21 in at the current `WORLD_SCALE`;
- water-line volume computed from the constants is 45.2 gal ±1 % (so a stray edit to a dimension is caught);
- the pane texture's texels have bit 15 set and the file is 16-bit (E8: a 32-bit RGBA save would silently turn every texel into a cut-out);
- exactly one `Player`, one `anemone`, one `anemone-zone`; no snowgoons-derived actor names remain.

## Risks and open questions

| Risk | Consequence | Mitigation |
|---|---|---|
| Translucent draw order (§ 3) | Pane hides the fish | Phase 0 first; Plan B is engine-free |
| Gravity-free `CharacterVirtual` drifts or sticks | Fish sinks or floats | Phase 1 step 5; script writes speeds every frame as the condo does |
| Tiny capsule misbehaves at ×1 | Jitter or tunnelling | ×10 authoring, ×1 compared first |
| `ROTATION_C` writes ignored | Fish swims backwards | Phase 1 step 7; `Turn Rate` fallback |
| Anemone sway shears or costs frames | Visual glitch | It is Phase 4 and optional; v1 is static |
| Any of the above needs an engine change | Scope grows | **Stop and escalate**; do not patch the engine inside this plan |

**Assumed, not asked (say so if wrong):** the player *is* the clownfish, rather than a fixed viewer; both are scripted from
existing controls; acrylic is a pale cyan edge tint, not a specific brand's look.

**Out of scope:** more fish, feeding, audio, bubble particles, a lid or a stand model, and photoreal caustics. Cost
breakdown: none — no infrastructure or paid service is involved.

## Delegation

| Phase | Tier | Why |
|---|---|---|
| 0, 1 | T4 | Unknown root outcomes; a wrong turn costs a redesign |
| 2, 3 | T3 | Multi-file against this plan once 0 and 1 have settled it |
| 4 | T2 | Bounded, optional |
| Final integration and review | T5 | Whole-session judgment |
