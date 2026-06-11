# WF Level Building & Engine Knowledge

This doc is organised level-designer-first: start here, set up tooling,
follow authoring conventions, wire the engine systems your level needs,
crib from a worked example, and (for engine maintainers only) read the
internals at the bottom. For per-symptom debugging recipes, see
[docs/level-design-troubleshooting.md](level-design-troubleshooting.md).

## Contents

1. [Start here — references for level designers](#start-here--references-for-level-designers)
2. [Tooling](#tooling)
   - [Blender MCP Connector](#blender-mcp-connector)
   - [Headless Blender export fallback](#headless-blender-export-fallback)
   - [Build & Run](#build--run)
3. [Authoring conventions](#authoring-conventions)
   - [Blender Viewport Display by Object Type](#blender-viewport-display-by-object-type)
4. [Engine systems you wire from a level](#engine-systems-you-wire-from-a-level)
   - [Composing actors — sensors + visuals](#composing-actors--sensors--visuals-reach-for-this-before-a-new-class) — prefer composition over new classes; `ActBox` trigger volumes; catalog of live primitives
   - [Scripting System](#scripting-system) — per-frame player script, camera-relative input (SW iso), Director / ActBoxOR pattern, level selection without scripts
   - [Camera System](#camera-system) — state machine, EMAILBOX_CAMSHOT bootstrap
5. [Worked example — Marble Madness arcade-ROM pipeline](#worked-example--marble-madness-arcade-rom-pipeline)
   - [Tools](#tools)
   - [Step 1 — Extract ROM data](#step-1--extract-rom-data)
   - [Step 2 — Build path mesh in Blender (via MCP)](#step-2--build-path-mesh-in-blender-via-mcp)
   - [Step 3 — Build pipeline (unchanged)](#step-3--build-pipeline-unchanged)
   - [ROM Segment Format](#rom-segment-format)
   - [Coordinate Mapping](#coordinate-mapping)
   - [Calibration Constants (`rom_to_blender.py`)](#calibration-constants-rom_to_blenderpy)
   - [Actor Spawn Placement](#actor-spawn-placement)
   - [Camera Setup for Marble Madness (SW Isometric)](#camera-setup-for-marble-madness-sw-isometric)
   - [Marble Physics: Friction and Deceleration](#marble-physics-friction-and-deceleration)
   - [Goal Platform: Back Wall](#goal-platform-back-wall)
   - [Marble Actor: Use `sphere.iff`, Not `player.iff`](#marble-actor-use-sphereiff-not-playeriff)
6. [Creating a new OAD (actor) class](#creating-a-new-oad-actor-class) — masters (`objects.mac` + `.oas`) vs generated files, the regen pipeline (partly un-revived), the `Gold` "terminate" pitfall
7. [Engine internals](#engine-internals)
   - [Level File Format](#level-file-format) — cd.iff TOC, DO_CD_IFF, level object count
   - [LP64 Port Issues](#lp64-port-issues)
   - [Level Constructor Ordering Bug (fixed)](#level-constructor-ordering-bug-fixed)

---

## Start here — references for level designers

Three documents to keep open while building any level. They cover
"what actors are available," "what a finished port looks like," and
"how to verify behaviour at runtime without rebuilding."

- **[docs/2026-05-03-oas-actor-types.md](2026-05-03-oas-actor-types.md)** — Index of every shipped
  OAS actor type, its OAD fields, and what game patterns it enables.
  Read this *first* before planning any level — the engine's
  ecosystem is wider than the headline classes (`player`, `room`,
  `camera`, etc.) suggest. Notable types people miss on a first pass:
  - `Generator` + `Template` — spawn-by-mailbox primitive.
  - `Warp` / `Destroyer` — paired spawn/despawn for projectiles + pickups.
  - `Meter` — on-screen mailbox-driven HUD gauge (score, timer, lives,
    counters). Wires straight to a director-side mailbox; no bitmap-
    font subsystem needed for basic readouts.
  - `Activation Box` / `Activation Box Object Reference` — collision
    triggers that write to mailboxes; the `Object Reference` variant
    is how the camera switches between `CamShot`s in `mm_practice`.
  - `Enemy` — generic NPC base with path-follow support.
- **Worked-example port plans** — read these to see how shipped
  primitives actually wire together end-to-end:
  - **[docs/plans/2026-05-03-qbert-mvp.md](plans/2026-05-03-qbert-mvp.md)** — content-only port (no
    engine changes): 28-cube pyramid + hop state machine + colour-flip
    win condition + fall-and-respawn, built entirely from shipped OAS
    types + Forth scripts in actor Script fields + mailboxes. The
    verification block in that doc shows the canonical bridge-dump
    format for proving a level's scripts behave as intended.
  - **`wflevels/mm_practice/`** — the original generic test level (a
    marble on a ramp); see `~/.claude/projects/-home-will-wf-games/memory/project_mm_practice_status.md`
    for status and gotchas.
  - **§5 of this doc** — Marble Madness arcade-ROM pipeline (full ROM
    → JSON → Blender mesh → WF level reproduction).
- **`~/.claude/projects/-home-will-wf-games/memory/reference_wf_debug_bridge.md`**
  — TCP/JSON debug bridge on port 7777. Watch any mailbox at runtime,
  pause / step the simulation, edit OAD properties live. Launch with
  `task run-debug -- wflevels/<level>.iff` (binds 127.0.0.1) or
  `task run-debug-remote ...` (binds 0.0.0.0). Pending bridge ops
  (mailbox-write, input-inject, shader hot-reload, script hot-swap,
  DAP breakpoints) are tracked in
  [docs/plans/2026-05-03-debug-bridge-gap-features.md](plans/2026-05-03-debug-bridge-gap-features.md).

For gotchas hit during real level work — coordinate systems, BungeeCam
target placement, Mesh face-normal rules, `Mobility`+`MovementClass`
requirements, zForth bitwise-op pitfalls, the `Model Type=Box` random-
debug-cube behaviour, the wf_blender exporter's dual-`Mesh Name`
field, etc. — see [docs/level-design-troubleshooting.md](level-design-troubleshooting.md).

---

## Tooling

### Blender MCP Connector

The official Blender MCP server (released 2026-04-28, Blender + Anthropic) lets Claude
directly manipulate a live Blender session — execute Python, introspect the scene, and
capture viewport screenshots — instead of round-tripping through `blender --background`
scripts.

#### One-time setup

**1. Install `uv` (once per machine)**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Install the Blender addon (scripted, no GUI needed)**

```bash
bash wftools/wf_blender/install_blender_mcp.sh
```

This downloads the addon from [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp)
(Blender 3.0+, works with 4.0.2), installs it headlessly, and verifies it's enabled.
The official Blender Lab addon requires Blender 5.1+ and isn't usable yet.

**3. Connect Blender each session**

Open Blender, press **N** in the 3D Viewport → **BlenderMCP** tab → **Connect to Claude**.  
Keep this panel open while working; the socket server runs only while connected.

**4. Project MCP config** (already committed at `.mcp.json` in repo root)

```json
{
  "mcpServers": {
    "blender": {
      "command": "uvx",
      "args": ["blender-mcp"]
    }
  }
}
```

Claude Code picks this up automatically on session start. Restart the session after
the first-time setup.

#### What this replaces

| Before | After |
|--------|-------|
| Edit `blender_update_player_sphere.py`, run `blender --background --python …` | Ask Claude to modify the scene directly in the open Blender window |
| Blind iteration — no visual feedback until game runs | Viewport screenshot available immediately after each change |
| Script must handle import, export, and reload | Claude issues targeted Python API calls; you trigger export when ready |

#### Notes

- Only one MCP client may connect at a time (don't run Claude Desktop and Claude Code
  simultaneously against the same Blender session).
- The server process (`uvx blender-mcp`) is managed by Claude Code; don't launch it
  manually in a terminal.
- The Blender addon listens on `localhost:9876` by default.

### Headless Blender export fallback

`bpy.ops.wf.export_level` is only registered when MCP is connected (the `debug_bridge`
module injected by the MCP server is needed by `wf_blender/__init__.py`). For headless
`blender --background --python` runs (i.e. any `blender_create_*.py` driver script that
needs to run from the command line), use the direct module loader:

```python
try:
    bpy.ops.wf.export_level(filepath=OUT_LEV)
except AttributeError:
    import importlib.util as _ilu
    _addon = os.path.expanduser('~/.config/blender/4.0/scripts/addons/wf_blender')
    _spec = _ilu.spec_from_file_location(
        'wf_blender.export_level', os.path.join(_addon, 'export_level.py'))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ok, msg = _mod.export_scene_to_lev(bpy.context, OUT_LEV)
    if not ok:
        raise RuntimeError(f'export_scene_to_lev failed: {msg}')
```

This bypasses `__init__.py` entirely and calls `export_scene_to_lev` directly. Used by
both `blender_create_mm_practice.py` and `blender_create_qbert.py`.

### Build & Run

```bash
cd engine
bash build_game.sh

# Run:
cd wfsource/source/game
LD_LIBRARY_PATH=../../../engine/libs DISPLAY=:0 ../../../engine/wf_game
```

`build_game.sh` compiles all source dirs, skips test/Windows files, uses the scripting stub
and platform stubs from `wftools/engine/stubs/`.

For per-level builds (Q✱bert / mm_practice / etc.) use the four-stage Rust pipeline:

```bash
bash wftools/wf_blender/build_level_binary.sh <level-name>
```

For runtime use Taskfile entries: `task run-level -- wflevels/<level>.iff` (no bridge),
`task run-debug -- wflevels/<level>.iff` (debug bridge on `:7777`).

---

## Authoring conventions

### Blender Viewport Display by Object Type

**The rule: anything that does not render in the game engine should display as
Wire in Blender.** This keeps editor visibility unobstructed — infrastructure
boxes (cameras, CamShots, ActBoxORs, room bbox visualisations, etc.) otherwise
occlude the actual level geometry and make it impossible to see what the player
will see at runtime.

The two `wf_Model Type` values that *do* render in-engine are:

- **`Mesh`** — the actor renders the geometry from its `Mesh Name` (.iff) reference.
- **`Matte`** — the actor renders its `Matte Type` background (colour or tiled image).

`None`, `Scarecrow`, `Emitter`, and unset are internal scaffolding the engine
uses for physics / triggers / messaging but draws nothing.

> ⚠️ **`Model Type='Box'` is NOT non-rendering.** The engine's
> `RenderActor3DBox` (instantiated by `actor.cc:398` for any Box-model actor)
> renders as a small **random-coloured** cube via `MakeRandMaterialList`.
> If a Box actor falls inside the camera frustum, it will obscure real
> geometry with a magenta / lime / olive cube whose colour changes between
> runs. Always set infrastructure actors to `Model Type='None'`. See
> `level-design-troubleshooting.md` § "Infrastructure actors render as
> random-coloured debug cubes" for the full diagnosis.

> ⚠️ **Actors authored outside every room's bbox silently don't render.**
> The room bbox isn't just a runtime culling volume — it controls
> render-set membership at level-export time. levcomp-rs
> ([`wftools/levcomp-rs/src/rooms.rs:168-178`](../wftools/levcomp-rs/src/rooms.rs))
> assigns each non-room actor to the first room whose bbox contains the
> actor's world-space *center*. Actors whose center falls outside every
> room's bbox get no `room.entries` push, so the `.lev` lists them in the
> level's object table but not in any room. At engine load,
> `Room::AddObject` / `ROOM_OBJECT_LIST_RENDER` walks only the room's
> listed entries, so `BindAssets` (which calls `new
> RenderActor3DAnimates(...)`) is never called for orphaned actors. They
> stay invisible no matter what their `wf_Model Type`, `Visibility
> Mailbox`, `Mass`, `Mobility`, or schema says.
>
> Diagnose with `grep -c RenderActor3DAnimates wf_game.log` against your
> expected animated-mesh count. One short → an actor's authored center is
> outside every room's bbox. Compare against `object count = N` in the
> same log — that's the total actor count, so the diff "object count
> non-NULL minus rendered" tells you how many actors fell off the map.
>
> **Fix:** either move the actor's authored center inside an existing
> room's bbox, *or* expand the room. For single-room levels (like the
> qbert_practice pyramid) the cleanest fix is a global-ish room bbox
> (e.g. `±200` in every axis around the room centre) so that any
> authored position — including off-camera "parking" locations the
> scripts want to teleport actors to — lands inside the room.
> Worked example: see
> [docs/plans/2026-05-11-qbert-player-death-and-curse-bubble.md](plans/2026-05-11-qbert-player-death-and-curse-bubble.md)
> § "2026-05-12 implementation notes" — the curse bubble at authored
> `Z=-100` was outside the room and didn't render until the room bbox
> was expanded.

Wire-displayed objects in Blender should be everything that doesn't render
in-engine (`Mesh` / `Matte` excluded). The `display_type='WIRE'` automation
below applies to all non-rendering classes.

To apply in one shot (run via MCP or in the Blender scripting console):

```python
import bpy
RENDERED = ('Mesh', 'Matte')
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue  # EMPTY / LIGHT / CAMERA already non-occluding
    mt = obj.get('wf_Model Type', None)
    if mt not in RENDERED:
        obj.display_type = 'WIRE'
```

#### Standard infrastructure object table

| Class | Typical `wf_Model Type` | Renders in-engine? | Wireframe in Blender? |
|-------|-------------------------|--------------------|-----------------------|
| `statplat`, `player`, `enemy`, `missile` (with mesh) | `Mesh` | yes | ✗ |
| `matte` | `None` (background painted via `Matte Type`/`Background Color`) | yes (backdrop) | ✗ |
| `room` | *(no OAD on the bbox visualisation mesh)* | no | ✓ |
| `actboxor`, `actbox` | `None` | no | ✓ |
| `camshot` | `None` (override default `Box`) | no | ✓ |
| `camera` | `None` (override default `Box`) | no | ✓ |
| `levelobj` | `None` (override default `Box`) | no | ✓ |
| `target` | `None` (override default `Box`) | no | ✓ |
| `director` | `None` | no | ✓ (often EMPTY anyway) |
| `light` | `None` | no | ✓ (often EMPTY anyway) |
| `generator`, `destroyer`, `warp`, `init`, `dir`, `file` | `None` | no | ✓ |

For each `wf_Model Type='None'` row above where the OAS schema's default
`Model Type` is `Box`, the `blender_create_*.py` script *must* set
`obj['wf_Model Type'] = 'None'` explicitly — otherwise the actor renders as
a random debug cube and obscures real geometry. The matte row also flips
from `Matte` to `None`: matte's backdrop drawing is independent of its
Model Type field, and `Model Type='Matte'` plus the `MODEL_TYPE_BOX`-default
behaviour combine to surprising results in practice. Use `'None'` and rely
on `Matte Type='Color'` + `Background Color` for the backdrop.

Authoring scripts (`blender_create_*.py`) should apply the snippet above as a
last step before saving the .blend, so the `wf_Model Type` settings stay in
sync with viewport display.

---

## Engine systems you wire from a level

These are the runtime systems your level interacts with through OAD
fields, mailboxes, and Forth scripts. The patterns below are what the
existing levels (`mm_practice`, `qbert_practice`, `snowgoons`, the MM
reproduction) actually use.

### Lighting — every level needs Directional **and** Ambient

WF's vertex shader (`wfsource/source/gfx/glpipeline/backend_modern.cc:84`) builds the per-vertex `v_lit` term as `u_ambient + Σ(N·L × light_color)`. **There is no implicit ambient term** — `u_ambient` comes from `Camera::SetAmbientColor`, which `wfsource/source/game/level.cc:1158` defaults to `Color::black`. The only way to raise it is to author an `Ambient`-type Light actor (`wfsource/source/game/light.hpi:57` is where that flows back to the camera).

If you author only Directional lights, any face whose normal isn't facing one of them gets `N·L ≈ 0` → `v_lit ≈ 0` → the face renders pure black, regardless of the actor's material color or texture. Flat-shaded cubes (qbert, SMB blocks) get away with this because their lit faces *are* fully lit and their shadowed faces are intentionally pure black. Curved-geometry actors (spheres, terrain meshes, anything smooth-shaded) and any sub-grazing single-directional setup (the moon's near-horizon sun) fall apart.

**Pattern: author both, in the Blender script:**

```python
# Directional — your "sun" / key light. Affects which surfaces get lit.
light = find_by_class('light')           # or create from scratch
light.name = 'Sun'
light.rotation_euler = (math.pi/2 - math.radians(SUN_ALT_DEG),
                        0.0,
                        math.radians(SUN_AZ_DEG))
light['wf_lightType']  = 'Directional'
light['wf_lightRed']   = 1.0
light['wf_lightGreen'] = 1.0
light['wf_lightBlue']  = 1.0

# Ambient — the "fill" that prevents pure-black shadow sides. RGB ~0.4 grey
# is the studio-with-fill-light point: shadows still visible, but directional
# contrast preserved (lit side clearly brighter than shadow side).
ambient = light.copy()
ambient.data = light.data.copy() if light.data else None
scene.collection.objects.link(ambient)
ambient.name = 'AmbientLight'
ambient.location = (0.0, 0.0, 50.0)      # any spot inside the room
ambient['wf_lightType']  = 'Ambient'
ambient['wf_lightRed']   = 0.40
ambient['wf_lightGreen'] = 0.42
ambient['wf_lightBlue']  = 0.50
```

`levcomp-rs` warns at build time if your level has no `Ambient`-type Light, plus warns on the STR/DATA mismatch shape (`STR "Ambient" + DATA 0`) that's an easy authoring slip. Don't ignore those warnings.

Picking the value: ~0.4 grey is a "clear-day outdoor / studio-with-fill" floor (shadow:lit ≈ 1:2.5). Slightly higher (0.5) reads as overcast; much higher (≥0.8) starts to make the directional light invisible; lower (0.15) is dim-crevice territory. Atmospheric moon levels can explicitly set 0 RGB for true black if dramatic shadow is the look you want — author it explicitly so a future reader knows the dark is intentional. That also suppresses the levcomp warning (the level *does* have an Ambient Light, just at zero) and documents the choice.

See `docs/level-design-troubleshooting.md` "Actor renders pure black despite light" for the troubleshooting flow.

### Composing actors — sensors + visuals (reach for this *before* a new class)

WF game objects are usually **compositions of small, single-purpose primitive actors**, not
bespoke classes. A whole category of actors are **sensors / references designed to pair with
another object**: they detect something and write a mailbox, or they act on a *referenced*
object. **Before** you write a new `EActorKind` (see [Creating a new OAD class](#creating-a-new-oad-actor-class))
— or overload an existing class to get "scriptable + collidable" — check whether a composition
of existing primitives already does the job. It almost always does, and it keeps each actor
single-purpose.

**The workhorse trigger volume — `ActBox`.** An invisible activation volume (`Model Type =
None`). When an actor passes its `Activated By Actor` filter and overlaps its bounding volume,
it writes a configurable value to a configurable mailbox (its `MailBox` / `MailBoxValue`
fields), with a separate exit value (`ClearOnExit` / `Mailbox Exit Value`) and an optional
directional `FieldFX` (wind/conveyor). It is the canonical *"when the player reaches **here**,
fire **this** mailbox"* primitive — you place it **at** the thing it guards, so the placement
*is* the trigger region. (`ActBoxOR` is the sibling that activates a referenced **Object**,
e.g. a CamShot — used for camera-zone switches.)

> **ActBox fires under Jolt.** Its overlap test is `Activation::Activated()`
> ([`activate.cc`](../wfsource/source/physics/activate.cc)) → `PhysicalAttributes::CheckCollision`
> — a pure AABB test on position + bbox, **independent** of the legacy collision-event pipeline
> that is dead under Jolt. The player is in `ROOM_OBJECT_LIST_COLLIDE` (`Actor::CanCollide` =
> `collisionTable[kind] && Mass>0`) and its `PhysicalAttributes` are synced from Jolt each frame
> *before* `ActBox::update()` runs, so the trigger works. (Contrast the per-actor `COLLIDER_IDX`
> mailboxes, which *did* need explicit Jolt-contact-listener wiring — see the
> [troubleshooting guide](level-design-troubleshooting.md).)

**Worked example — flagpole ends the level.** A flagpole is *not* a class; compose it:

- the pole + flag are a plain **`statplat`** (just the art);
- drop an **`ActBox`** volume on the flagpole with `Activated By Actor = Player`,
  `MailBox = 1905` (`INDEXOF_END_OF_LEVEL`, [`mailbox.inc:31`](../wfsource/source/mailbox/mailbox.inc)),
  `MailBoxValue = 1`.

Mario walks into the volume → the ActBox writes `1` to `END_OF_LEVEL` → the level unloads
([`level.cc`](../wfsource/source/game/level.cc) `EMAILBOX_END_OF_LEVEL` → `_done`). No script,
no coordinate, no class.

**Anti-patterns this replaces**

- ❌ **Position threshold baked into a script** — e.g. the player's script doing
  `INDEXOF_X_POS read-mailbox 63 > if … END_OF_LEVEL …`. The author has to read the goal's
  coordinate off the level and transcribe it into *another* actor's script; it silently breaks
  the moment the goal moves, and it couples the player to the goal's placement. There's no clean
  way for the author to "know" that number. Use a trigger volume **co-located** with the goal.
- ❌ **Overloading a class to get capabilities** — e.g. making the flagpole a `generator` just
  because `generator` is the only anchored + collidable + **scriptable** class (`statplat`
  forbids scripts — `actor.cc:736`). That's the actor-kind-vs-capability smell. Compose a sensor
  (`ActBox`) next to the dumb visual instead.

**Catalog of composable primitives (all LIVE today)** — sensors/references you wire to other
objects:

| Primitive | Pairs with | Does |
|-----------|-----------|------|
| `ActBox` | a mailbox | overlap → write `MailBox = MailBoxValue` (+ exit value, + `FieldFX` push) |
| `ActBoxOR` | an Object (CamShot) | overlap → activate the referenced object (camera zones) |
| `Warp` | a `Target` | overlap → teleport the entering actor to the Target's position (← SMB pipes) |
| `Generator` | a template Object | on activation, spawn its `Object To Throw` (← `?`-block coins) |
| `Destroyer` | activation | remove objects on trigger |
| `Spike` | contact | apply a `Health Modifier` to whoever touches it (← hazards) |
| `Shield` | the Player | follows + absorbs hits (← power-ups) |
| `Shadow` | a template Object | casts that object's drop-shadow onto the floor |
| `Platform` | a path | moving / path-following surface |
| `Target` / `CamShot` / `Director` | referenced by others | position markers, camera shots, mailbox orchestration |

The shared `activate.inc` block — `Activated By Actor` = *any* / *specific-actor* / *class* /
*list* — is the filter that makes every trigger-style primitive selective.

**Dead stubs — do not author against these** (they have an `.oas` but no backing C++ class and
aren't registered as a kind): `Pole`, `Meter`, `Movie`. Each would need engine work first.

#### Full actor-class inventory (reference)

The authoritative list of what actually instantiates at runtime is the factory in
[`objects.c`](../wfsource/source/oas/objects.c) (dispatch on `EActorKind`) + the registration in
[`objects.lc`](../wfsource/source/oas/objects.lc). As of the 2026-05-25 survey:

**Live actor classes** (you can place/compose these):

| Class | Role |
|-------|------|
| `Player` | the playable character (Ground/Air handlers, jump) |
| `Enemy` | damage-dealing NPC |
| `StatPlat` | static platform / scenery — **scripts forbidden** (`actor.cc:736` asserts) |
| `Platform` | movable / path-following surface (C++ minimal; motion via OAS movement block) |
| `Generator` | spawns its `Object To Throw` template on activation |
| `Gold` | collectible coin *(template-only — spawned, not placed directly)* |
| `Shield` | player invulnerability/power-up, follows the player *(template-only)* |
| `Missile` | projectile *(template-only)* |
| `Explode` | explosion effect *(template-only)* |
| `Spike` | applies a `Health Modifier` to whoever contacts it |
| `Warp` | teleports the entering actor to a referenced `Target` |
| `Destroyer` | removes objects on activation |
| `ActBox` | activation-volume trigger — writes `MailBox=MailBoxValue` on filtered overlap |
| `ActBoxOR` | activation volume that activates a referenced Object (camera zones) |
| `Target` | position marker (referenced by `Warp`/`CamShot`/`Director`) |
| `CamShot` | camera shot / keyframe (Track/Target toggles) |
| `Camera` | camera control actor |
| `Director` | orchestration; runs *after* the main loop each tick |
| `Light` | light source (directional/omni) |
| `Matte` | background fill (e.g. SMB sky colour) |
| `LevelObj` | level-wide object (mailbox count, etc.) |
| `Shadow` | drop-shadow caster for a referenced template |
| `Tool` | held item / weapon |

**Component / data-only** (the `.oas` exists only to generate a `.ht` struct; *not* an
instantiable actor): `actor`(`.inc`), `common`, `movebloc`, `mesh`, `activate`, `toolset`,
`shadowp`, `handle`, plus the legacy/marker types `alias`, `dir`, `file`, `font`, `init`,
`template`, `disabled`, `test`.

**Dead stubs** (no C++ class, not registered): `Pole`, `Meter`, `Movie`.

### Scripting System

#### Per-frame player script (basic pattern)

Forwards raw joystick to the input mailbox:

```forth
\\ wf
INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox
```

For an isometric camera where screen-up ≠ world-N, use a bit-rotation word instead (see
"Camera-relative input" below). For complex per-tick behaviour (state machines,
hop arcs, AI), see `qbert_practice/blender_create_qbert.py` for the canonical multi-tick
state-machine pattern in Forth.

#### Available Forth words (zForth vocabulary)

The actor `{Script}` field runs in zForth with a vocabulary already loaded — **you don't need to define
these, and new scripts should use them directly** rather than inlining the old workarounds:

- **Stack:** `dup drop swap over rot -rot nip tuck ?dup 2dup 2drop 2swap pick`
- **Arithmetic:** `+ - * / 1+ 1- negate abs min max mod` (`%` is the native alias for `mod`)
- **Compare** *(true = `-1`, like standard Forth):* `= <> < > <= >= 0= 0< 0> 0<> not`
- **Bitwise:** `&` (= `and`), `|` (= `or`) — **not** `and`/`or`, which abort at runtime (`ZF_ABORT_NOT_A_WORD`)
- **Memory:** `@ ! +! , here`
- **Control flow:** `if … else … then` (`fi` = `then`), `begin … until`, `begin … again`, `limit start do … loop` (or `loop+`), loop indices `i` `j`
- **WF bridge:** `read-mailbox ( idx -- val )`, `write-mailbox ( val idx -- )`, `write-actor-mailbox ( val idx actor -- )`
- **Constants:** every `INDEXOF_*` mailbox name is pre-defined.

> **New as of 2026-06-02:** `0= 0< 0> negate abs min max ?dup nip tuck -rot 2dup 2drop 2swap +! mod`
> were added to `kCoreBootstrap` (`engine/stubs/scripting_zforth.cc`). Older scripts that inline
> equivalents — `over over` (→ `2dup`), `swap drop` (→ `nip`), `0 =` (→ `0=`) — still work, but reach for
> the words. (The cam-remap example below predates this and still uses `swap drop`; `nip` is equivalent.)

> **Cells are float**, so `/` is floating-point division. For an integer remainder use `mod` (or `%`),
> which truncate via zForth's native `%` primitive (and abort on divide-by-zero). Do **not** write
> `over over / * -` for mod — it cannot truncate under float division and silently returns garbage.

**Branching on a mailbox value** — three patterns; pick by whether you need the value after the test:
```forth
( 1. value not needed — direct: if consumes it )
INDEXOF_TRIGGER read-mailbox if  ...  then

( 2. value needed on true branch only — ?dup: copies non-zero, leaves 0 unchanged )
INDEXOF_CAM read-mailbox ?dup if INDEXOF_CAMSHOT write-mailbox then

( 3. value needed on both branches — dup 0= to test without consuming )
INDEXOF_DIST read-mailbox dup 0= if drop 0 else  ... use value ...  then
```
`0 <>` before `if` is unnecessary for branching — `if` treats any non-zero value as true. Only use
`0 <>` (or `0=`) when you need the normalized `-1`/`0` boolean itself on the stack.

Full catalogue + rename gotchas (`&`/`|`/`<0`/`%`) and compile-mode rules for `if/then` live in
[`docs/scripting-languages.md`](scripting-languages.md#L37).

#### PILOT in-level scripts

PILOT is a scripting language option alongside Forth/Lua/Wren/JS/Wasm (engine `kDispatch`
slot 6). Full grammar: [`docs/pilot-language.md`](pilot-language.md). To author a PILOT
`{Script}` on an actor, set its `wf_Script` custom property to a program whose **first
non-blank line is the `R:pilot` sigil**:

```pilot
R:pilot
C:mb(GOLD) = 1234
*top
C:mb(GOLD) = mb(GOLD) + 1
PA:0.1
J:*top
```

How routing works (no OAD field needed): the engine still dispatches per-actor scripts with
the hardcoded Forth language id (`actor.cc`), but `ScriptRouter::RunScript`
**content-sniffs** the source — a leading `R:pilot` re-routes to the PILOT engine
(Forth's own `\ wf` sigil never matches). Unlike Forth (which re-runs the whole script
every frame), **PILOT is a frame-resumable state machine**: the per-actor program counter
persists across frames, and blocking verbs (`A:`, `PA:`, `WM:`) suspend until satisfied —
loop explicitly with `J:*top`. `mb(IDX)` reads/writes the actor's mailbox; mailbox names are
available prefix-free (`GOLD`, `X_POS`, …). Angles are revolutions; `PA:`/`WT:` are seconds
(LevelClock). Worked end-to-end example: [`wflevels/pilot_demo/blender_create_pilot_demo.py`](../wflevels/pilot_demo/blender_create_pilot_demo.py),
verified by [`tests/pilot/in_level_demo.pilot`](../tests/pilot/in_level_demo.pilot).

#### Camera-relative input (SW iso pattern)

The WF `MarbleHandler` applies button bits as world-axis impulses:
`EJ_BUTTONF_UP` → world +Y (North), `EJ_BUTTONF_RIGHT` → world +X (East),
etc. Arrow keys map to these bits via `INDEXOF_HARDWARE_JOYSTICK1_RAW`.

For an SW isometric camera (offset −6,−8,+10 looking NE), screen-up =
world NE and screen-right = world SE. The player expects pressing Up to move
the ball "up the screen" (NE), not world-North. The fix is to rotate the
four direction bits 45° CW in a Forth word before writing to `INDEXOF_INPUT`:

```forth
\ zForth — use & and | for bitwise ops, NOT "and"/"or"
: cam-remap  0
  over 0x0800 & if 0x2800 | then    \ UP    → UP|RIGHT  (0x0800|0x2000) = NE
  over 0x1000 & if 0x5000 | then    \ DOWN  → DOWN|LEFT (0x1000|0x4000) = SW
  over 0x2000 & if 0x3000 | then    \ RIGHT → DOWN|RIGHT(0x1000|0x2000) = SE
  over 0x4000 & if 0x4800 | then    \ LEFT  → UP|LEFT  (0x0800|0x4000) = NW
  swap drop ;

INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox cam-remap INDEXOF_INPUT write-mailbox
```

Diagonal combos cancel correctly: pressing Up+Right produces
NE+SE = (UP|RIGHT)|(DOWN|RIGHT) — the NE and SE verticals cancel leaving pure
East. No special diagonal handling is needed.

**Bit values** (from `wfsource/source/hal/sjoystic.h`):

| Bit symbol | Value |
|---|---|
| `EJ_BUTTONF_UP` | `0x0800` |
| `EJ_BUTTONF_DOWN` | `0x1000` |
| `EJ_BUTTONF_RIGHT` | `0x2000` |
| `EJ_BUTTONF_LEFT` | `0x4000` |

**zForth operator note:** zForth does NOT have `and` or `or` as named words.
Use the primitive symbols `&` (bitwise AND) and `|` (bitwise OR).
Using `and`/`or` compiles silently into a ZF_ABORT_NOT_A_WORD error (code 7)
that prints `zforth compile error 7 (defs): : cam-remap ...` at runtime —
the word is simply not executed every tick, leaving `INDEXOF_INPUT` at 0.

#### Mailbox scope rules

WF mailboxes form a hierarchy. Understanding scope prevents the most common cross-actor scripting bugs.

| Range | Name | Scope | Notes |
|---|---|---|---|
| 0–1 | `EMAILBOX_FALSE` / `EMAILBOX_TRUE` | Global, read-only | Set by engine at level load; write attempts are silently dropped (assert in debug builds). Use mb[1] as a "always-true" visibility mailbox. |
| 2–999 | Global user | **Shared across all actors** | Director, player, cube actors, etc. all read/write the same cells. Q✱bert's cube-state mailboxes (200–227), round counter (425), etc. live here. |
| 1000–1999 | Global system | Global, side-effects | `INDEXOF_CAMSHOT` = **1921** writes the active camera — verified against [`mailbox.inc`](../wfsource/source/mailbox/mailbox.inc) (`MAILBOXENTRY( CAMSHOT, 1921 )`) and the engine's `zforth: INDEXOF_CAMSHOT = 1921` line. **It is NOT 1021** — an earlier revision of this table said 1021; an ActBoxOR/script that writes the wrong slot silently fails to switch the camera. |
| 2000–2099 | Local user | Per-actor | Each actor has its own storage at this range. Rarely needed for game logic. |
| 3000–3036 | Local system | Per-actor, side-effects | **`INDEXOF_X_POS` = 3009, `INDEXOF_Y_POS` = 3010, `INDEXOF_Z_POS` = 3011.** Writing here moves the *calling actor's* position. |
| 4000–4099 | Scratch | Per-script-call | Temporary storage within a single script execution. |

**Critical implication — you cannot teleport another actor from the director:**

```forth
\ WRONG: executed in the director's context — moves the director, not the player
0 INDEXOF_X_POS write-mailbox
```

`INDEXOF_X_POS` = 3009 is in the local-system range. A `write-mailbox` syscall routes through `LookupMailboxes(callerActorIndex)` → that actor's `WriteSystemMailbox` → moves *that* actor. From the director script, this moves the (invisible) director, not Q✱bert.

**Pattern for cross-actor teleport — use a signal mailbox:**

```forth
\ Director script: set a signal in the shared global range
1 426 write-mailbox   ( 426 = RESPAWN_REQUESTED )

\ Player script: handle the signal in player context
426 read-mailbox 1 = if
  0 INDEXOF_X_POS write-mailbox   ( these now move the player )
  6 INDEXOF_Y_POS write-mailbox
  15 INDEXOF_Z_POS write-mailbox
  0 426 write-mailbox             ( clear signal )
then
```

**Visibility mailbox (`wf_Visibility Mailbox`):**

Most gameplay actors (platform, statplat) default to `VisibilityMailbox = 1` (reads mb[1] = always 1 = always visible). Infrastructure actors (target, camshot, light, actboxor) default to `VisibilityMailbox = 0` (reads mb[0] = always 0 = always invisible). Cube variant actors use custom mailbox slots (300–383 in `qbert_practice`) so the director can switch which variant renders. Scripts cannot make a gameplay actor invisible: mb[1] is protected from writes.

#### Director / ActBoxOR pattern

- **Director script** (per frame): reads mailboxes 98/99/100 and writes to `$INDEXOF_CAMSHOT`.
  These mailboxes are set by ActBoxOR trigger zones.
- **ActBoxOR objects**: write a named object's index to a mailbox when the Player enters
  their trigger volume. In snowgoons, one ActBoxOR writes `CamShot01`'s index to mailbox 1921 (`INDEXOF_CAMSHOT`)
  (`EMAILBOX_CAMSHOT`) when the Player enters.
- **NullInterpreter stub**: `wftools/engine/stubs/scripting_stub.cc` — replaces Tcl scripting
  with a no-op. All `RunScript()` calls return 0. This is intentional pending replacement
  with a non-Tcl scripting system.

#### Per-tick execution order (and why signal chains pick up a 1-tick lag)

There is **no priority/phase/dependency mechanism for actor scripts.** Execution order per tick is:

1. **Main update loop** ([`level.cc:876`](../wfsource/source/game/level.cc) — `UpdatePhysics(...)`) — iterates every active actor in **actor-index order** (= the order the `.lev` file lists them = the order the Blender exporter wrote them = the creation order in the `blender_create_*.py` script). For each actor: physics step, then `Actor::update()` runs the actor's MovementHandler, then `EvalScript()` runs its Forth script.
2. **`updateRoomContents()`** (room-membership housekeeping).
3. **Director runs last, alone** ([`level.cc:881-888`](../wfsource/source/game/level.cc)) — hardcoded special case prefixed by the comment *"FIX - manually update director until we get priorities working in updates"*. The Director update is not part of the main loop; it gets its own slot after everything else.

**What this means for cross-actor signal mailbox chains** — the pattern of `actor A writes global → actor B reads, computes, writes another global → actor C reads, applies on self`:

- A producer that runs in the main loop will see its writes consumed by the Director on the **same** tick (Director runs after the main loop completes).
- A consumer that runs in the main loop will see the Director's writes only on the **next** tick (the Director hasn't run yet when the consumer fires in the main loop).
- **Net result:** any signal chain that crosses through the Director and back into a main-loop actor accumulates exactly **one tick of lag** at the final consumer. At 60 Hz that's 16 ms — invisible for camera positioning, score updates, colour pulses; potentially relevant for input-driven physics if you're stacking multiple chains.

**The alternative pattern — Director writes another actor's local mailbox directly via [`write-actor-mailbox`](../engine/stubs/scripting_zforth.cc) (custom syscall 2, signature `( val idx actor_idx -- )`)** — *also has the 1-tick lag*, because the target actor's update (which is what reads the changed mailbox) runs in the main loop before the Director's after-loop slot. The signal-chain design isn't slower than the direct-poke design on this metric; it's just architecturally cleaner. The direct-poke primitive is on the chopping block — see `TODO.md` § `SCRIPTING INFRASTRUCTURE`.

**Controlling actor-index order within the main loop** — actors run in the order the Blender script creates them. To get producer-before-consumer ordering inside one tick, create the producer actor first in the `blender_create_*.py` script. If you're not sure, dump actor indices with `--debug-print-actors` (see [§ `--debug-print-actors`](#--debug-print-actors-debug-builds-only) above) and read off the load-order column. Note that this only gates intra-main-loop chains; it can't shorten chains that cross through the Director.

**There is no way to declare a dependency like "run my script after actor X's script."** The closest workaround is to add the dependent logic to the Director's script (so it runs after every main-loop actor). Past that, you accept the 1-tick lag or restructure the chain. A real priority/phase mechanism is the right long-term fix; tracked in `TODO.md` § `SCRIPTING INFRASTRUCTURE` as "Finish 'priorities working in updates'".

#### Level Selection Without Scripts

`_desiredLevelNum` in `WFGame` must be set before `assert(_desiredLevelNum >= 0)` fires.
Normally the shell script (cubemenu) writes `EMAILBOX_LEVEL_TO_RUN` to choose a level.
**Fix (game.cc):** initialize `_desiredLevelNum = 4` (snowgoons) in the constructor
initializer list, and move the `_overrideLevelNum` check to BEFORE the asserts.

### Camera System

#### Camera State Machine

- **DelayCameraHandler**: waits up to 5 frames for `EMAILBOX_CAMSHOT > 0` then transitions.
  Assertion at `movecam.cc:885` fires if nobody writes a valid CamShot index within 5 frames.
- **BungeeCameraHandler**: main follow camera. Each frame reads `EMAILBOX_CAMSHOT` (mailbox 1921)
  to get the active CamShot object's index. Originally cleared the mailbox after reading
  (relied on ActBoxOR to re-write each frame).
- **NormalCameraHandler**: validates that the stored shot index is a real CamShot object.

#### CamShot tracking toggles — `Rotation` and `Position X/Y/Z`

For a camera that **follows the player**, the CamShot needs both its `Track Object`
set (e.g. `Player`) **and** the right mode toggles:

| Field | Value to follow the player | Effect if wrong (0) |
|-------|----------------------------|---------------------|
| `Rotation` (`Fixed`\|`Track`) | **`Track` (1)** | `Fixed` → camera orientation static, ignores `Track Object` |
| `Position X/Y/Z` (`Absolute`\|`Relative`) | **`Relative` (1)** | `Absolute` → camera parked at the CamShot's world position |

With `Fixed`/`Absolute` the BungeeCam ignores the player even though `Track Object`
is set, parking at a static wide pose. On a mostly-white level (e.g. a snow level)
that static view can read as "untextured/flat gray" when the textures are actually
fine — see [troubleshooting](level-design-troubleshooting.md). These toggles are
`TYPEENTRYBOOLEANTOGGLE` enums; a `.lev` where their `DATA` and `STR` disagree is
corrupt and now hard-fails on Blender import.

#### Fog OAS fields — match your environment, don't inherit snowgoons'

The `camera` actor carries three fog fields ([`camera.oas`](../wfsource/source/oas/camera.oas)):
`FoggingColor`, `FoggingStartDistance`, `FoggingCompleteDistance`. The engine
reads them per-level at [`game/camera.cc:56-57`](../wfsource/source/game/camera.cc)
and calls the renderer's `SetFog`. The default values in the snowgoons scaffold
are `#888888` ramp 20 → 30 m — tuned for an Earth-atmosphere chase-cam view of
a small playable area; any pixel past 30 m fades to flat `#888888`.

When you `bpy.ops.wf.import_level(SNOWGOONS)` to inherit infrastructure, find
the `camera` actor and set the fog to match your *actual* setting:

| Setting              | `FoggingColor` | `FoggingStartDistance` | `FoggingCompleteDistance` |
|----------------------|---------------:|-----------------------:|--------------------------:|
| Vacuum (Moon/Mars)   |     `0x000000` |                  999.0 |                    1000.0 |
| Earth, hazy outdoor  |     `0x888888` |    half visible-extent |           visible-extent  |
| Indoor / arcade      |     `0x000000` |                  999.0 |                    1000.0 |
| Dust / haze planet   |   tint match   |                  ~50.0 |                    ~200.0 |

Far-clip is 1000 m ([`gfx/gl/display.cc:307`](../wfsource/source/gfx/gl/display.cc)),
so pushing `FoggingCompleteDistance` past 1000 m effectively disables fog. See
[`wflevels/moon_site01/blender_create_moon.py`](../wflevels/moon_site01/blender_create_moon.py)
for a vacuum template and [`level-design-troubleshooting.md`](level-design-troubleshooting.md#vista-camera-renders-flat-mid-grey-chase-camera-looks-fine--snowgoons-fog-inheritance)
for the failure mode this prevents.

#### EMAILBOX_CAMSHOT Bootstrap

> **Correction (2026-05-25, verified):** an earlier version of this section claimed
> "with scripting disabled, ActBoxOR trigger zones never fire." **That is wrong.**
> `ActBoxOR::update` ([actboxor.cc](../wfsource/source/game/actboxor.cc)) activates via a
> pure **C++ overlap test** (`Activation::Activated()`), *independent* of the script
> engine — exactly like `ActBox`. A fresh ActBoxOR fired and switched the camera with
> Tcl scripting disabled (the SMB pipe-warp `abor_coin`). What actually broke that switch
> the first time was writing the **wrong mailbox** (1021 vs the real `INDEXOF_CAMSHOT` =
> 1921), not a dead ActBoxOR. Verify capability claims against the code, not this doc.

There is still a one-time **bootstrap**: in `level.cc::constructObject`, when a
`CamShot_KIND` object is constructed and `EMAILBOX_CAMSHOT` is still 0, the engine writes
that CamShot's actor index. This seeds the *initial* shot (the first CamShot constructed)
so a level with a single camshot needs no ActBoxOR at all.

`BungeeCameraHandler::predictPosition()` originally cleared the mailbox after use (line 988);
that clear is suppressed here, so the mailbox **persists** at the last written value. A
single-camshot level therefore stays on the bootstrapped shot forever; a multi-camshot level
must have an in-room ActBoxOR (or the Director) overwrite `INDEXOF_CAMSHOT` to switch shots.

#### Per-frame camera slew clamp (10 units/frame, hardcoded)

`NormalCameraHandler::_update()` ([`movecam.cc:495-511`](../wfsource/source/game/movecam.cc)) applies a slew clamp to the final camera position vector every tick the active CamShot index is unchanged from last frame:

```cpp
#define XSLEW SCALAR_CONSTANT(10)
#define YSLEW SCALAR_CONSTANT(10)
#define ZSLEW SCALAR_CONSTANT(10)
…
destCam.position = LimitRelativeMovementMagnitude(
    destCam.position, cd.oldCameraPosition, Vector3(XSLEW, YSLEW, ZSLEW));
```

`LimitRelativeMovementMagnitude` is per-axis: each axis can move at most 10 units between consecutive frames. The clamp is applied **after** the per-axis Absolute/Relative mux (lines 235-248 in `SetCameraParametersFromShot`), so it constrains all three axes regardless of which mode each is in — an Absolute axis is just as clamped as a Relative one.

The original author left a comment beside the constants: *"I don't understand why they are necessary, since we specify the pan time in seconds in the OAD. So, I'm defining them as constants here just to get this code working. — Phil"*. Take this as licence to tune the numbers when a level design needs to.

**When it doesn't bite:**

- **Player-driven follow cameras.** Mario's `Max Ground Speed` is 6 (`wflevels/smb_w1_1/blender_create_smb.py:274`); any speed under 10 leaves the slew dormant for normal tracking. SMB-style scroll, MM iso, and standard 3rd-person follow all stay well under budget.
- **First-frame handler activation.** Line 510 guards the clamp with `if(cd.idxOldCamShotActor)`, so the very first frame after `DelayCameraHandler` hands off (or after a CamShot switch) is exempt. A script can seed a fresh camera position with any delta on its first tick.
- **`gBungeeCam` global true.** Line 499 short-circuits the entire else-branch when set, skipping the slew. This is the existing knob for "I want the camera to teleport".

**When it does bite:**

- **Per-frame mailbox-driven camera moves** (e.g. a Director Forth script writing to a CamShot's `INDEXOF_X_POS` via `write-actor-mailbox` to drive scroll behaviour from script). The CamShot's authored position changes per tick, and the slew clamps the resulting camera delta. Fine if per-frame delta < 10; otherwise the camera lags visibly behind the script's intended position.
- **Cutscene-style jumps mid-level.** A Director that wants to snap the camera 50 units to set up a cutscene will see ~5 frames of slew-limited drift unless it flips `gBungeeCam` true or relies on a CamShot switch (which also resets the slew via the `idxOldCamShotActor != idxShot` else-branch that transitions to `PanCameraHandler`).

**Raising or removing the limit if a game design requires it:**

The slew limit is a 1996-vintage workaround, not a load-bearing invariant. Three routes to change it:

| Route | Mechanism | Trade-off |
|-------|-----------|-----------|
| **Edit C++ constants** | Bump `XSLEW`/`YSLEW`/`ZSLEW` at [`movecam.cc:495-497`](../wfsource/source/game/movecam.cc) | One-line engine edit. Affects every level. Easy, blunt instrument. |
| **Per-CamShot OAS field** | Add `Slew X/Y/Z` (or a single `Slew Max`) to [`camshot.oas`](../wfsource/source/oas/camshot.oas) and read them in `_update()` | Per-CamShot tunability. Currently gated by the "no new OAS fields pre-merge" rule until the first level ships ([`feedback_no_new_oas_fields_premerge`](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_no_new_oas_fields_premerge.md)). |
| **Toggle `gBungeeCam`** | Set the existing `extern bool gBungeeCam` true (line 49); the slew else-branch is skipped entirely | No engine code change. Crude — bypasses slew globally, not per-axis. Use as runtime escape hatch. |

If a level design hits this clamp, prefer the C++-constant bump for one-off relief and reserve the OAS field for when per-CamShot tuning becomes a recurring need across multiple games.

For deeper camera investigation (per-axis Absolute/Relative, runtime switching via
`INDEXOF_CAMSHOT`, target tracking) see [docs/investigations/2026-04-29-camera-system.md](investigations/2026-04-29-camera-system.md).

### Physics-mobility actor authoring rules

Actors with `wf_Mobility = 'Physics'` are driven by [Jolt's `CharacterVirtual`](https://jrouwe.github.io/JoltPhysics/class_character_virtual.html) (set up in [`jolt_backend.cc:JoltCharacterCreate`](../wfsource/source/physics/jolt/jolt_backend.cc)). The first level to exercise this code path was SMB W1-1 (Mario, 2026-05-17); the diagnosis that produced these rules is in [`docs/investigations/2026-05-17-colspace-authoring.md`](investigations/2026-05-17-colspace-authoring.md).

**Three rules, all level-side:**

1. **Mesh-local feet at z=0.** WF's convention is `actor.pos = feet position`. The Jolt character settles with `actor.pos.z = ground_top_z`, so anything with mesh-local z < 0 ends up *inside* the ground. In a Blender script, after joining multi-primitive bodies, call `bpy.ops.object.transform_apply(location=True, ...)` so the joined mesh origin sits at the lowest vertex (the feet), then assign `player.data = body.data`. Otherwise the body inherits the active object's pre-join location and the mesh-local feet drift below z=0.

2. **Collision shape = visual-mesh AABB (auto-derived).** The Blender exporter writes a `Global Bounding Box` (BOX3) per actor from the visual mesh AABB, and the engine turns it into a Z-up [`CapsuleShape`](../wfsource/source/physics/jolt/jolt_backend.cc) (radius = `min(halfX, halfY)`, halfHeight = `halfZ − radius`). For Mario-shaped actors (taller than wide) you get a capsule that fills the silhouette; for short, wide actors (halfZ ≤ radiusXY) the engine falls back to a single-radius sphere. There is no separate `wf_ColSpace` override field yet — see [`docs/investigations/2026-05-17-colspace-authoring.md`](investigations/2026-05-17-colspace-authoring.md) for when one might be worth adding.

3. **One Physics actor per level minimum** (today). Mario in `smb_w1_1` is the only Physics actor in any committed level — `qbert_practice`, `mm_practice`, `snowgoons-blender` all use `Anchored` (the script handles all movement). Every aspect of the Physics path is currently exercised by exactly one actor.

**What to verify after authoring a Physics actor:**

| Test | What to watch on the bridge |
|---|---|
| Resting on flat ground | `idx=N` Z should equal ground top z, not negative |
| Walking off a ledge | Z drops, then settles on the next platform |
| Walking *up* onto a 1-tile box (e.g. SMB `qblock`) | Step-up should work or feel like jumping into a wall — both are valid game-design choices, just be intentional |
| Jumping | Z arcs up then back down to the resting Z |
| Head-bonking a low ceiling | Capsule top hits, Z dips, no fall-through |
| Wall blocking (pipes / actboxor) | X stops at the wall, Z stays constant |

**Mobility values and their physics semantics:**

| Value | What drives position | Use for |
|---|---|---|
| `Anchored` | Forth script writes `INDEXOF_X/Y/Z_POS` mailboxes | Most arcade ports (no real physics — Q*bert, MM, snowgoons) |
| `Physics` | Jolt `CharacterVirtual` with gravity from `wf_Falling Acceleration` | Mario-style platformers, anything needing real ground collision + jump arcs |
| `Path` | An OAD path animates the actor | Moving platforms, scripted enemy paths |
| `Camera` | Camera handler in `movecam.cc` | Camera actors only |
| `Follow` | Follows another actor | Trailing camera, second-player |

---

### Debug bridge

Run with `--debug-port 7777` (or use `task run-debug -- wflevels/<level>.iff`) to
expose a TCP/JSON port. The bridge broadcasts per-frame state and accepts
commands (`ping`, `pause`, `step`, `resume`, `pick`, `screenshot`, `set_mailbox`,
`reload_script`).

#### Identifier spaces — three different "id" fields

When debugging a physics issue you will see **three distinct identifier spaces**
in the logs, with similar-looking small integers. They are not interchangeable
and confusing them sends you down the wrong rabbit hole.

| Identifier | Where it appears | What it indexes | Example |
|---|---|---|---|
| **WF actor `idx`** | Bridge `{"op":"state","idx":N,"pos":[…]}` and `{"op":"perf","actors":N}` | The current level's actor table (load order) | `idx=9` = "the 9th actor in this level" |
| **Jolt body `id`** | `jolt_backend.cc` stderr: `jolt: body STATIC pos=… id=N`, `jolt: body MESH_STATIC … id=N` | `JPH::BodyID` — Jolt's internal rigid-body handle (large numbers with high bits set) | `id=8388608` = "Jolt body #0 in the STATIC pool" |
| **Jolt character `handle`** | `jolt: character N created at (…) ctr=(…)` | Index into `gCharacters` in [`jolt_backend.cc:443`](../wfsource/source/physics/jolt/jolt_backend.cc) — separate namespace from body ids | `handle=0` = "the first `Mobility=Physics` actor" |

**A bridge `idx` is not a Jolt id.** Static colliders have ids; characters have
handles; bridge events use WF actor indices. There's no direct cross-reference
printed — correlate by position.

**Practical example.** Investigating the SMB W1-1 invisible-player on
2026-05-17, the bridge reported `idx=9 pos=(4.5, 0, -0.67)` (player below
ground). The Jolt log showed `character 0 created at (4.50, 0.00, 1.50)`
(handle=0) and `body STATIC … id=8388608` (ground). Three different
identifiers for two real things (player + ground). Diagnosis only worked
because we kept the spaces separated.

#### `--debug-print-actors` (debug builds only)

Add `--debug-print-actors` to the engine command line (already wired into
`task run-debug`) and the engine prints one stderr line per actor at
construction time. The flag and its supporting code are guarded by
`#if DO_TEST_CODE` and so don't exist in `safe-fast`, `release`, `final`,
or `profile` builds — zero cost in production. See
[`docs/compile-time-switches.md`](compile-time-switches.md) for the build-mode
table.

```
actor idx=9  mesh=player.iff  mobility=Physics  pos=(4.50,0.00,1.50)
actor idx=19 mesh=(none)      mobility=Anchored pos=(4.50,0.00,1.50)   ← Target02 (camera lookat)
actor idx=15 mesh=ground.iff  mobility=Anchored pos=(33.75,0.00,-0.75)
…
```

This is the canonical way to map bridge `{"op":"state","idx":N}` events
back to specific WF actors. Off by default — opt-in to keep production
logs clean.

---

## Worked example — Marble Madness arcade-ROM pipeline

Marble Madness level paths are not hand-authored — they are faithfully reproduced from the
arcade ROM. The pipeline goes: **ROM → JSON → Blender mesh → WF level**. Treat this section
as a worked example of "reproducing arcade geometry from extracted data" — the Q✱bert MVP
is the worked example for "synthesising a pyramid from a Python loop", and `mm_practice` is
the worked example for "the simplest possible WF level."

### Tools

| Script | Location | Purpose |
|--------|----------|---------|
| `decode_levels.py` | `wflevels/marble-madness/` | Extracts all 6 level segment records from the ROM ZIP into `levels.json` |
| `rom_to_blender.py` | `wflevels/marble-madness/` | Converts `levels.json` into a trough mesh in the live Blender scene |
| `blender_mm_fromscratch.py` | `wflevels/marble-madness/` | Full level build: clear scene, run converter, place all actors, export `.lev` |

### Step 1 — Extract ROM data

```bash
cd wflevels/marble-madness
python3 decode_levels.py ../../assets/arcade-roms/marble.zip
# → levels.json  (all 6 levels; h_left / h_right / h_center per segment)
```

`levels.json` is committed; only re-run if the ROM source changes.

### Step 2 — Build path mesh in Blender (via MCP)

With a Blender session open and MCP connected:

```python
import bpy, os
script = '/path/to/wflevels/marble-madness/blender_mm_fromscratch.py'
exec(open(script).read(), {'__file__': script, '__name__': 'blender_mm_fromscratch'})
# → mm_fromscratch.lev
```

Or run `rom_to_blender.py` alone to add just the path mesh to an existing scene:

```python
ns = {'__file__': '/path/to/rom_to_blender.py', '__name__': 'rom_to_blender', 'bpy': bpy}
exec(open('/path/to/rom_to_blender.py').read(), ns)
ns['build_path_mesh']('Practice', ns['load_levels']())
```

### Step 3 — Build pipeline (unchanged)

```bash
cd wflevels/marble-madness
bash build_level.sh
```

### ROM Segment Format

Level pointer table at `0x01DEC0` → per-level descriptor arrays (6-byte `[type:u16][addr:u32]`
entries, sentinel `0xFFFF`) → 24-byte segment records.

| Offset | Field | Notes |
|--------|-------|-------|
| `+02` | `h_left` | Wall/edge height — left side |
| `+04` | `h_right` | Wall/edge height — right side |
| `+0A` | `h_center` | Floor height at path centre |

Segments with `h_center == H_ZERO (5)` are goal zones — replaced by a flat platform.

Full reverse-engineering notes: [`docs/investigations/2026-05-01-marble-madness-rom-level-data.md`](investigations/2026-05-01-marble-madness-rom-level-data.md).

### Coordinate Mapping

The 16-bit `type` field encodes the **path heading** in its lower byte:

```
heading_angle = (type & 0xFF) / 256 × 2π  radians, CCW from +X axis (East = 0°)
```

Cross-section positions accumulate along the heading:

```
pos_{i+1} = pos_i + SEG_LEN × (cos θ_i, sin θ_i, 0)
```

Each cross-section has 3 vertices perpendicular to the heading (`right_perp = (sin θ, −cos θ, 0)`):

```
left   = (pos − PATH_HALF × right_perp,  Z(h_left))
center = (pos,                            Z(h_center))
right  = (pos + PATH_HALF × right_perp,  Z(h_right))
```

Height conversion: `Z(h) = (h − H_ZERO) × GAME_UNIT`

#### Trough vs. crowned sections

- `h_edge > h_center` → **walled trough**: edges rise above floor — ball is contained.
- `h_edge < h_center` → **crowned / open-sided**: edges drop below centre — ball rolls off without joystick steering (correct arcade geometry).

#### Practice level heading table

| Segments | `type` | Lower byte | Heading | Geometry |
|----------|--------|------------|---------|----------|
| 0–8 | `0x000D` | 13 | 18.28° (ENE) | Crowned S-curve — requires joystick |
| 9–10 | `0x0320` | 32 | 45.00° (NE) | Walled trough — rolls to goal unaided |
| 11–12 | `0x0D20` | 32 | — | Goal sentinel (`h_center=5`) → flat platform |

### Calibration Constants (`rom_to_blender.py`)

```python
H_ZERO    = 5      # goal h_center; subtracting puts goal at Z=0
GAME_UNIT = 0.05   # metres per game height unit  ← tune this
SEG_LEN   = 2.5    # metres per path segment       ← tune this
PATH_HALF = 2.0    # metres, centre → edge vertex  ← tune this
```

`GAME_UNIT=0.05` and `PATH_HALF=2.0` (calibrated 2026-05-02 against MAME screenshot):
trough walls at ΔH≈46–89 units over `PATH_HALF=2.0 m` give 30–48° slope angles, matching
the ~30–50° trough profiles in `assets/arcade-roms/reference/practice_start.png`.
`PATH_HALF=4.0` was visually too wide; `GAME_UNIT=0.1` produced 49–66° walls, too steep.

Compare viewport screenshots against `assets/arcade-roms/reference/practice_start.png` and
iterate GAME_UNIT / SEG_LEN until proportions match.

### Actor Spawn Placement

Spawn the Player above the **first walled (trough) segment** so the ball rolls toward the goal
without requiring joystick input during testing. For Practice this is seg 9:

```python
# heading-based position of seg-9 start: 9 segs × SEG_LEN × (cos 18.28°, sin 18.28°)
SPAWN_POS = (21.364, 7.058, 3.2)   # 0.6 m above seg-9 floor at Z=2.6
```

To play the full S-curve (segs 0–8), a joystick must be connected.

### Camera Setup for Marble Madness (SW Isometric)

The arcade original uses a fixed SW isometric view: camera is above-and-SW of the marble,
looking NE+down at roughly 45° elevation. All three BungeeCam axes must be `Relative` so
the camera offset stays fixed relative to the player position each frame.

**CamShot offset** (`CAMSHOT_POS`): `(-6, -8, 10)` from the marble works for Practice.
This gives ~45° elevation, camera is SW, and the sight line clears the west trough wall
(camera z=7.9 at wall crossing vs. wall top z≈5.1).

```python
SPAWN_POS    = (21.364, 7.058, 3.2)   # marble spawn
CAMSHOT_POS  = (-6.0, -8.0, 10.0)    # offset from marble
CAMERA_POS   = tuple(s + c for s, c in zip(SPAWN_POS, CAMSHOT_POS))
# → (-15.636+21.364, -0.942+7.058, 13.2) = approx (−15.6, −0.9, 13.2)
```

**CamShot `Target` field must be `'Player'`**, not a fixed Target02 empty. A fixed world
point causes the camera to look through the trough walls as the marble moves away from spawn.
With `Target='Player'` the camera always rotates to face the ball directly.

```python
props={
    'X Axis': 'Relative', 'Y Axis': 'Relative', 'Z Axis': 'Relative',
    'Target': 'Player',
    'Track Object': 'Target01',  # origin anchor at (0,0,0)
    'Follow': 'Target01',
    ...
}
```

**Sight-line geometry rule**: camera clears a wall of height `wall_z` when:
`cam_z - 0.5*(cam_z - marble_z) > wall_z`
i.e. the midpoint of the sight line is above the wall top.
With CAMSHOT_Z=10 and marble_z≈3.2: midpoint z = 10+3.2)/2 ≈ 6.6 > 5.1 ✓.

The camera-relative input bit-rotation Forth word for this SW iso view is in
[§4 — Camera-relative input (SW iso pattern)](#camera-relative-input-sw-iso-pattern) above.

### Marble Physics: Friction and Deceleration

The player OAD fields that most affect rolling feel:

| Field | Value | Rationale |
|-------|-------|-----------|
| `Running Deceleration` | `0.0` | Let physics (friction) handle braking; non-zero values easily exceed gravity on shallow slopes and freeze the ball |
| `Surface Friction` (player) | `0.3` | Low enough to roll down grades up to ~2° |
| `Surface Friction` (mesh) | `0.2` | Combined friction = player × mesh; keep low for smooth rolling |

`Running Deceleration` is applied as an artificial brake every frame when no joystick input
is present. On a 2.2° slope gravity = 0.38 m/s²; any `Running Deceleration` above ~0.35
will freeze the ball. Setting it to `0.0` leaves all braking to surface friction.

### Goal Platform: Back Wall

`rom_to_blender.py` adds a 2 m tall vertical quad face at the far end of the goal platform
(`PATH_HALF * 1.5` wide) to stop the marble rolling off. This is separate from the trough
walls and is always emitted when `goal_segs` is non-empty. If the marble still escapes,
increase `wall_h` in `build_path_mesh()`.

### Marble Actor: Use `sphere.iff`, Not `player.iff`

`player.iff` in the `marble-madness/` directory is a cube (8 verts, 576 bytes). The
marble must use `sphere.iff` (pre-built UV sphere, 21 KB):

```python
obj['wf_Mesh Name'] = 'sphere.iff'
```

`sphere.iff` is committed in `wflevels/marble-madness/` alongside `mm_fromscratch.ini`.

---

## Creating a new OAD (actor) class

Adding a brand-new actor class (a new `EActorKind`, e.g. the SMB `Gold`
collectible) is **not** a level-authoring task you do per-level — it touches the
engine's OAS codegen. But level designers hit it the moment a level needs a
behaviour no shipped class provides, so the full procedure lives here.

> **Try composition first.** Most "the level needs a behaviour no class provides" cases are
> actually solved by *combining existing primitives* — a trigger volume + a visual, a `Warp` +
> `Target`, a `Generator` + a template — not by a new class. See
> [Composing actors](#composing-actors--sensors--visuals-reach-for-this-before-a-new-class).
> Only reach for a new `EActorKind` when no composition of live primitives can express the
> behaviour. `Gold` qualified (a genuinely new collectible-pickup behaviour); a flagpole does
> **not** (it's `statplat` + `ActBox`).

> **The cardinal rule: edit the *masters*, then *regenerate* the derived files.
> Never hand-edit a generated `objects.*` / `*.ht` file.** Every `objects.*`
> output and every `<name>.ht` carries a `created from … DO NOT MODIFY` banner
> for a reason — they are produced from [`objects.mac`](../wfsource/source/oas/objects.mac)
> + the per-class `.oas` files by `prep`/`coltab.pl`. Hand-patching them is what
> broke `Gold` (see the case study below).

### The two masters you edit by hand

1. **[`wfsource/source/oas/objects.mac`](../wfsource/source/oas/objects.mac)** —
   the single master list of every creatable object. Two sections:
   - **OBJECTS** (`OBJECTSHEADER … OBJECTSFOOTER`): one line per class. Pick the
     right macro — name **must be ≤ 8 chars**, and a matching `.oas` file must exist:
     | Macro | Use for |
     |-------|---------|
     | `OBJECTENTRY(Name,collidable)` | standard load-time-creatable object |
     | `OBJECTNOACTORENTRY(Name,collidable)` | never has an Actor (e.g. collision boxes) |
     | `OBJECTONLYTEMPLATEENTRY(Name,collidable)` | only spawnable from a template (e.g. `Missile`, `Explode`, `Gold`) — not constructed at load time |
     | `OBJECTSUBENTRY(Child,Parent,collidable)` | derived from another object |
     `collidable` = 1 if the object does *anything* on intersection (it then
     receives general collision messages); 0 otherwise.
   - **COLTABLE** (`COLTABLEHEADER … COLTABLEFOOTER`): one
     `COLTABLEENTRY(A, B, CI_AtoB, CI_BtoA)` per interacting pair, where each
     `CI_*` is `CI_NOTHING` / `CI_PHYSICS` / `CI_SPECIAL`. **Any pair you don't
     list defaults to `CI_NOTHING` both ways** — i.e. the objects pass through
     each other. A collectible like `Gold` needs at least
     `COLTABLEENTRY(Gold, Player, CI_SPECIAL, CI_NOTHING)` (pickup) and probably
     `COLTABLEENTRY(Gold, StatPlat, CI_PHYSICS, CI_PHYSICS)` (lands on floor).
2. **`wfsource/source/oas/<name>.oas`** — the per-class OAD schema.
   Minimal example (`gold.oas`): `TYPEHEADER(Gold,Gold)` + `@include actor.inc`
   + `@define DEFAULT_*`. Field blocks (`actor.inc` → `movebloc.inc`, `meshbloc.inc`,
   …) supply the standard Position / Mobility / Mesh / Script fields.

You also write the C++ class by hand: **`wfsource/source/game/<name>.{hp,cc}`** —
an `Actor` subclass with `kind()`, any overridden `Collision()`, and an
`Oad<Name>(startupData)` factory. Add `<name>.cc` to the engine build
(CMake / Taskfile).

### What gets generated (and by what) — never edit these

Everything below is derived from `objects.mac` (+ the per-class `.oas` for `.ht`).
The `objects.<x>s` files are `prep` templates that `@include objects.mac`; the
`objects.<x>` outputs are what the engine actually compiles.

| Generated output | From (master/template) | Generator | Consumed by |
|------------------|------------------------|-----------|-------------|
| `objects.h` (`EActorKind` enum, `<Name>_KIND`) | `objects.hs` | `prep` | actor.cc, level.cc, collision.cc, … |
| `objects.e` (enum for inclusion) | `objects.es` | `prep` | `coltab.pl` input |
| `objects.c` (the `Oad<Name>` dispatch/factory cases) | `objects.s` | `prep` | level/object construction |
| `objects.inc` (list of `#include "<name>.hp"`) | `objects.ins` | `prep` | engine |
| `objects.ctb` (collision *exception* table) | `objects.cts` | `prep` | `coltab.pl` input |
| `objects.car` (the real `collisionInteractionTable[MAX_OBJECT_TYPES]²`) | `objects.e` + `objects.ctb` | **`coltab.pl`** | room.cc / level.cc / collision.cc |
| `objects.col` | `objects.cos` | `prep` | engine |
| `objects.lc` (ascii class list, name→kind) | `objects.lcs` | `prep` | **levcomp-rs** (maps `.lev` `Class Name` → kind) |
| `objects.p` / `objects.iff` / `objects.mak` / `objects.xml` | `objects.{ps,ifs,mas,xms}` | `prep` | tooling/build |
| `<name>.ht` (the read-struct for the OAD binary) | `oadtypes.s` + `<name>.oas` | `prep` → `cstruct`/awk | `#include <oas/<name>.ht>` in `<name>.cc` |

### Regenerating — and the part that still needs reviving

[`wfsource/source/oas/regen-headers.sh`](../wfsource/source/oas/regen-headers.sh)
(`task gen-oas-headers`) currently regenerates **only** `objects.{c,e,h}` and all
`*.ht`. The *rest* of the table — `objects.ctb`, `objects.car` (via `coltab.pl`),
`objects.col`, `objects.lc`, `objects.inc`, `objects.p`, `objects.iff` … — is **not
yet wired into any task**; those steps were part of the lost GNUmakefile build and
have to be **revived** before a new class can land cleanly. Until they are, those
files are the stale checked-in copies, and any class you add by editing only
`objects.mac` will be invisible to the collision table and to levcomp. (Tracking:
[TODO § BUILD / TOOLCHAIN](../TODO.md) — the `.ht` codegen repair, dispatched
2026-05-20, is the first piece.)

### Checklist

1. Add the OBJECTS line to `objects.mac` (≤ 8-char name; matching `.oas` exists).
2. Add the COLTABLE rows to `objects.mac` for every pair the class interacts with.
3. Write `wfsource/source/oas/<name>.oas`.
4. Write `wfsource/source/game/<name>.{hp,cc}` (+ add `.cc` to the build).
5. **Regenerate** all derived files from the masters (revive the generators if
   missing) — do *not* hand-edit them. Verify the regen reproduces every other
   class byte-for-byte first.
6. Rebuild the engine; verify in-game (the new kind constructs without the
   `kind()` assert firing, and collides as the COLTABLE says).

### Pitfall case study — `Gold` (2026-05-20): the "terminate" crash

`Gold` was added by editing the OBJECTS list correctly but then **hand-patching the
generated files** (`objects.{h,e,c,inc}` +rows; `gold.ht` hand-authored as a
renamed `target.ht` stopgap because the `.ht` codegen is broken) and **omitting the
COLTABLE rows entirely**. Consequences:

- The constructed coin's `MovementClass` (read through the wrong stopgap layout /
  ungenerated default) is **not** `Gold_KIND`. Every actor's `kind()` asserts
  `GetMovementBlockPtr()->MovementClass == <Name>_KIND` (the codegen default,
  [`movebloc.inc:26`](../wfsource/source/oas/movebloc.inc) `@e0(OASNAME@+_KIND)@-`,
  is each class's own kind, which doubles as its `collisionInteractionTable` row).
  So `Gold::kind()` aborts inside `Level::ConstructTemplateObject` → `Actor::BindAssets`
  the instant a `?`-block tries to throw a coin.
- The failed `assert` calls `exit()`; during `atexit`, the still-joinable
  debug-bridge `gListenerThread` destructs while joinable → `std::terminate`. So the
  symptom is the **misleading** `terminate called without an active exception`,
  not an assertion message. (Confirmed by `gdb` backtrace; reproduce with
  [`tests/repro_gold_spawn_crash.py`](../tests/repro_gold_spawn_crash.py).)
- Even once that's fixed, with no `COLTABLEENTRY(Gold,…)` the coin's collision row
  is all `CI_NOTHING` — it would fall through the player and floor (never
  collectible). The collision behaviour *is* the COLTABLE entry.

**Lesson:** the crash isn't in `gold.cc`; it's that the class was half-generated.
The fix is to revive the masters→derived regeneration (above), not to patch the
assert. See [docs/level-design-troubleshooting.md](level-design-troubleshooting.md)
for the symptom-first version of this entry.

---

## Engine internals

These sections are for engine maintainers, not level designers. They cover the binary
file format, the LP64 port, and a load-bearing constructor-ordering bug fix. Skip
unless you're modifying the engine itself.

### Level File Format

#### LVAS — Level Assets (per-level container)

**LVAS = "Level Assets".** The IFF container chunk that bundles one level
together with the binary assets it needs — effectively a list of the IFF
(binary) files that make up a playable level: the level data (`LVL`) plus its
asset blobs (`PERM`, `RM0`, `RM1`, … the permanent + per-room texture/mesh
bundles), indexed by a table of contents (`TOC`) and an asset map (`ASMP`).

Layout (per [`levcomp-rs/decompile.rs`](../wftools/levcomp-rs/src/decompile.rs)):

```
L4   → [ ALGN, RAM, ALGN, LVAS ]
LVAS → [ TOC, ALGN, ASMP, ALGN, LVL, PERM, RM0, RM1, … ]
```

The authored `.lev` text source roots at **`LVL`** (the level data alone);
**`LVAS`** is the downstream binary wrapper produced when the level and its
assets are packaged for the engine. `cd.iff` (below) is in turn an archive of
many such per-level files.

#### cd.iff — Multi-Level Archive

`cd.iff` is an IFF-format table-of-contents archive containing all game levels.

**Structure:**
- LVLHDR `{lvasTag, fileSize}` at byte offset 0
- TOC IFF chunk: array of `TOCENTRYONDISK {tag, offset, size}` entries

**Level index in cd.iff (snowgoons project):**
| Index | Tag  | Name       |
|-------|------|------------|
| 0     | SHEL | cubemenu shell |
| 1     | L0   | cubemenu   |
| 2     | L1   | primitives |
| 3     | L2   | cyberthug  |
| 4     | L3   | geosphere  |
| 5     | L4   | snowgoons  |
| 6     | L5   | whitestar  |
| 7     | L6   | whitestar2 |

`GAMEFILE_LEVELSTART` offset is added to the level index when seeking via DiskTOC.

#### DO_CD_IFF

Defined at `game/game.cc:26`. When defined, loads levels from `cd.iff` via DiskTOC.
When undefined, loads `level%d.iff` from disk directly.

#### Level Object Count

Each `.iff` level embeds `_levelData->objectCount` (37 in snowgoons). Temporary objects
(tools, shadows, projectiles) occupy `objectCount .. objectCount + NumberOfTemporaryObjects - 1`.
`NumberOfTemporaryObjects` comes from the levelobj OAD; default is 200.

### LP64 Port Issues

The engine was written for 32-bit PSX/Win32 where `long` = 4 bytes. On Linux 64-bit, `long` = 8 bytes.

#### Known LP64 fixes

- **`gfx/rmuv.cc`**: `long* pRMUV` → `int32* pRMUV`; IFFTAG comparison cast to `(int32)`.
- **`gfx/ccyc.cc`**: same fix — `long* pCCYC` → `int32* pCCYC`.

#### How to spot LP64 issues

Assertions of the form `assert(*ptr == IFFTAG('x','y','z','w'))` that fail at startup
usually mean a `long*` is being used to read a 4-byte IFF tag/size pair — it reads 8 bytes
instead of 4, so the tag value is wrong. Fix: use `int32*` and cast IFFTAG to `(int32)`.

### Level Constructor Ordering Bug (fixed)

**Symptom:** Tools and shadows are constructed in `Actor::reset()`, added as temp objects,
but then `Level::reset()` immediately deletes all temp objects. The Actor still holds dangling
`_tool[]` pointers → vtable corruption → SIGSEGV in `Tool::trigger()`.

**Root cause:** In the Level constructor, the per-actor `reset()` loop ran BEFORE `Level::reset()`.

**Fix (`level.cc`):** Move the per-actor `reset()` loop to AFTER `Level::reset()`, so that tools
and shadows are created AFTER the temp-object slots are cleared and the active rooms are set up.

```cpp
// BEFORE (broken):
for each actor: actor->reset();   // creates temp objects (tools, shadows)
Level::reset();                    // deletes all temp objects → dangling pointers

// AFTER (fixed):
Level::reset();                    // clears temp slots, initializes active rooms
for each actor: actor->reset();   // creates temp objects AFTER rooms are ready
```

The `Actor::reset()` / `_InitTools()` pattern:
- `Actor::reset()` calls `_InitTools()` and `_InitShadow()`
- `_InitTools()` calls `ConstructTemplateObject()` for each tool slot, then `AddObject()`
- Tools are added as temp objects (index >= `_levelData->objectCount`)
