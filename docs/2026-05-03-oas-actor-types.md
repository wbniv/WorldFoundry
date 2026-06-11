# Shipped OAS actor types — index

**Date:** 2026-05-03
**Source:** `wfsource/source/oas/*.oas`
**Purpose:** Quick reference for every shipped actor type, its fields, and what game patterns it enables. Built so port plans (Q✱bert and the rest of the catalogue under `~/wf-games/`) can pull from existing primitives instead of reinventing them.

## How to read this index

Each `.oas` file defines one object type via the `TYPEHEADER()` macro, which opens a `typeDescriptor[]` array containing one entry per editable field. OAS fields are defined using type macros: `TYPEENTRYINT32` (integer), `TYPEENTRYFIXED32` (16.16 fixed-point — the editor renders the float, but on disk it's an integer × 65536), `TYPEENTRYBOOLEAN` (checked/unchecked), `TYPEENTRYOBJREFERENCE` (pointer to another actor), `TYPEENTRYFILENAME` (asset file path), `TYPEENTRYSTRING` (text), `TYPEENTRYVECTOR3` (X/Y/Z components). The `@include` directives pull in shared field blocks: `actor.inc` is the base (mesh, animation mailbox, movement params), `common.inc` adds health/script/slopes, `movebloc.inc` provides movement mechanics (mobility class, mass, acceleration, elasticity), and similar blocks add domain-specific fields. Groups opened via `GROUP_START()` and closed by `GROUP_STOP()` organise fields visually in the editor.

A flag-trail at the bottom of a `TYPEHEADER` (e.g. `LEVELCONFLAGROOM`, `LEVELCONFLAGNOINSTANCES`, `LEVELCONFLAGEXTRACTLIGHT`) sets level-config bits used by `levcomp-rs` and the editor — for example, `LEVELCONFLAGROOM` declares the type as a room container, `LEVELCONFLAGNOINSTANCES` prevents direct placement (templates / shims), and `LEVELCONFLAGEXTRACTLIGHT` marks the type for 3DS-light-extraction during build.

## Common includes

These `.inc` files are pulled in by multiple OAS classes and define shared field blocks. Skim these first if you're trying to figure out where a field "comes from."

- **`actor.inc`** — Base actor block. Pulls in `movebloc.inc`, `toolset.inc`, `common.inc`; adds `Mesh Name` filename field (conditional on `Model Type==Box|Mesh`), mesh configuration (`Model Type` enum, `Animation Mailbox`, `Visibility Mailbox`), matte/emitter groups (background colour, image tiles, particle emission). This is the workhorse — most actor types `@include` it.
- **`mesh.inc`** — Mesh/rendering. `Model Type` enum (`Box | Mesh | Scarecrow | None | Light | Matte | Emitter`), Animation/Visibility mailbox refs, `Matte Type` (`None | Color | Image`) with conditional colour picker or tile/map groups, `Emitter` (`Pulse | Continuous`) with period/delay, particle emission (radius, velocity, angles, lifetime, alpha fade), dual force fields (constant/random/radial with magnitude and vector).
- **`common.inc`** — Health and AI. `hp` (hit points, 0–32767), `Number Of Local Mailboxes` (0–40 for runtime script state), `Poof` actor reference (spawned on death), `Is Needle Gun Target` (boolean), `Write To Mailbox On Death` (mailbox index), `Script` (XData script field), `Script Controls Input` (boolean), slope plane coefficients `slopeA/B/C/D` (hidden, for walking-surface math).
- **`movebloc.inc`** — Movement mechanics. `Movement Class` (integer), `Mobility` enum (`Anchored | Physics | Path | Camera | Follow`), `Mass` (0–100 fixed), `Moves Between Rooms` (boolean), `Movement Mailbox` (integer), `Step Size` (fixed), elasticity X/Y (0–1), `Surface Friction` (0–1). Physics-conditional subgroups: **On Ground** (Running Accel/Decel, Max Speed, Turn Rate), **Crawling** (Accel), **Jumping** (Accel, Momentum Transfer), **In Air** (Air Accel, Horiz/Vert Drag, Max Speed), **Falling** (Accel, Anim Threshold). Path-conditional: `At End Of Path` enum (`Ping-Pong | Stop | Jumpback | Delete | Derail | WarpBack`), `Object To Follow`, `Follow Offset`. Stun mechanics (Threshold, Duration).
- **`toolset.inc`** — Tool slots. `Tool A` through `Tool F` — each a `TYPEENTRYOBJREFERENCE` to a tool/weapon actor.
- **`shadow.inc`** — Shadow rendering. `Shadow Object Template` reference, `Check Below Only Once` boolean (conditional on shadow template).
- **`activate.inc`** — Activation triggers. `ActivatedBy` enum (`All | Actor | Class | List`), with conditional groups: by Actor (reference to e.g. `Player01`), by Class (class filter), by Object List (XData list, `XDATA_OBJECTLIST`).
- **`meter.inc`** — HUD meter display. `Object` ref, `Mailbox To Display` (integer), `Mailbox Type` enum (`Scalar | Integer`), `Path X/Y Start` (fixed-point screen coords), Display group (`Increment Before Display`, `Pause At Keyframe`, `Display Pause Duration`), `Text X/Y Offset` (0–319 / 0–223).
- **`flagbloc.inc`** — Generic flags. `Template Object` boolean — marks template actors that are not placed directly.
- **`xdata.inc`** — XData/asset filename helpers. Defines `BITMAP_FILESPEC` (BMP + TGA + SGI), `MAP_FILESPEC` (scrolling maps), `ALLFILES_FILESPEC`.
- **`objects.inc`** — Object-class enumeration (included by `movebloc.inc`).

## Shipped actor types

Sections sorted alphabetically by class name.

### `Activation` — Activation trigger record (minimal)

**Source:** `activate.oas`
**Includes:** `activate.inc`, `xdata.inc`
**Purpose.** Standalone activation record. Minimal type; primarily a way to instantiate the `activate.inc` conditional-activation block (filter by Actor / Class / Object-list).

**Key OAD fields:**
- `ActivatedBy` — Enum (`All | Actor | Class | List`); controls which conditional activation group is visible.
- `Activated By Actor` — Actor reference (visible when ActivatedBy=Actor).
- `Activated By Class` — Class filter reference (visible when ActivatedBy=Class).
- `Activated By Object List` — XData object list (visible when ActivatedBy=List).

### `Activation Box` — Mailbox trigger on collision

**Source:** `actbox.oas`
**Includes:** `actor.inc` (visibility=0, model=none, no mass)
**Purpose.** Invisible trigger zone. Writes a mailbox value when an activator (filtered) overlaps. Optional exit-clear (resets mailbox to a different value when the actor leaves).

**Key OAD fields:**
- `MailBox` — Mailbox to write on activation (0–3999, default 2).
- `MailBoxValue` — Value to write (0–65536, default 1).
- `Activated Actor Mailbox` — Mailbox storing the actor that triggered (0–3999).
- `ClearOnExit` — Boolean; if true, resets mailbox to `Mailbox Exit Value` on leave.
- `Mailbox Exit Value` — Value written on exit (fixed, default 0).
- `Activation Mailbox` — Read this mailbox to gate whether the trigger is active (0–3999, default 1).
- `ActivatedBy` — Enum (`All | Actor | Class | List`).
- **FieldFX group:** Vector X/Y/Z directional field effect (hidden until ActivatedBy filter set).

**Likely uses for arcade ports:** Generic trigger zone for level progression (Q✱bert level transitions, Pac-Man pellet-pickup zones, Space Invaders wave boundaries).

### `Activation Box Object Reference` — Mailbox-triggered camera switcher

**Source:** `actboxor.oas`
**Includes:** `actor.inc` (visibility=0, model=none, no mass), `activate.inc`
**Purpose.** Activation box that, on entry, writes a referenced object's index into a mailbox — the canonical way to cut to a `Camshot` actor when the player enters a region.

**Key OAD fields:**
- `MailBox` — Mailbox index (2–3999, default 100).
- `Object` — The object whose index is written (object reference, labelled "Camshot Object").
- `ActivatedBy` — Enum (`All | Actor | Class | List`).

### `Alias` — Lightweight pointer-to-another-actor

**Source:** `alias.oas`
**Includes:** None (minimal)
**Purpose.** A reference shortcut. Used for level-design shortcuts when you'd otherwise duplicate a complex setup.

**Key OAD fields:**
- `Base Object` — Object reference; the actor this alias points to.

(Marked `LEVELCONFLAGSHORTCUT` — flagged as alias.)

### `Camera` — Movable camera actor

**Source:** `camera.oas`
**Includes:** `actor.inc` (default mobility=Camera-follow)
**Purpose.** Camera with optional motion smoothing (bungee-cam), stereogram support, and fogging. The active gameplay camera.

**Key OAD fields:**
- **Stereogram group:** `EyeDistance` (fixed, 0–10, default 0.025), `EyeAngle` (fixed, 0–360°, default 2.5°).
- **Fogging group:** `FoggingColor` (RGB 0xRRGGBB), `FoggingStartDistance` (fixed, 0–1000), `FoggingCompleteDistance` (fixed, 0–1000).

**Likely uses for arcade ports:** Smooth follow-cam with fogging for depth (Galaga / Space Invaders zoomed viewport, Q✱bert isometric camera).

### `Camera Shot` — Camera placement preset

**Source:** `camshot.oas`
**Includes:** `actor.inc` (visibility=0, model=none)
**Purpose.** Defines a camera view (position, target, FOV, roll). The activation-box-or-camshot pattern (`actboxor` writing an `Camshot` index into the active-camshot mailbox) is the standard way to switch views. Supports fixed shots, bungee-cam following, or tracking targets.

**Key OAD fields:**
- `Camera` — Extracted camera record (position, orientation; `LEVELCONFLAGEXTRACTCAMERANEW` for 3DS extraction).
- `Target` — Look-at point (vector, conditional).
- `Follow` — Actor to follow (vector, conditional).
- **Bungee-Cam group:** `Climb Rate`, `Elasticity` (both fixed; control smooth following).
- **Tracking Object group:** `Track Object Mailbox` (read index from mailbox) OR `Track Object` (direct reference; mutually exclusive).
- **Tracking Type group:** `Rotation` toggle (`Fixed | Track`), `Position X/Y/Z` toggles (`Absolute | Relative`).
- `FOV` — Field of view (1–180°, default 50°).
- `Roll` — Camera roll angle (0–32000, default 0).
- **Mode: Switching Camshots:** `Pan Time In Seconds` (0–10 fixed, transition duration on cut).
- **Clipping Planes:** `Hither` (near, 0–1000, default 0.1), `Yon` (far, 0–1000, default 100).

**Likely uses for arcade ports:** Death cutscenes, level-clear pans, boss reveal pans (Q✱bert snake approach, Galaga boss entry).

### `Common` — Common-block schema shim

**Source:** `common.oas`
**Includes:** `common.inc`
**Purpose.** Standalone shim that re-emits the Common OAD from `common.inc` (health, script, slopes). Rarely instantiated; used to keep schema synchronised when `common.inc` changes.

**Key OAD fields:** (see `common.inc` above.)

### `Destroyer` — Destroy-on-mailbox trigger

**Source:** `destroyer.oas`
**Includes:** `actor.inc`, `activate.inc`
**Purpose.** Destroys a referenced object when its mailbox flips. Counterpart to `generator` — together they make up the spawn/despawn pair.

**Key OAD fields:**
- `Activation MailBox` — Mailbox to trigger destruction (0–3999, default 1).
- `ActivatedBy` — Enum (`All | Actor | Class | List`).

**Likely uses for arcade ports:** Despawning ball/Coily actors when the player hits them (Q✱bert), enemy cleanup on wave end (Galaga / Space Invaders), destructible walls.

### `Dir` — FSN directory tower (template-only)

**Source:** `dir.oas`
**Includes:** `actor.inc`
**Status:** ✅ Runtime actor — `OBJECTONLYTEMPLATEENTRY`; `dir.cc` / `dir.hp` present.
**Purpose.** Visual stand-in for a filesystem directory in the FSN-style filesystem browser level (`wflevels/filesys/`). Spawned at runtime by the Director Forth script via `ConstructTemplateObject`, never placed directly. Scale mailboxes 3040–3042 drive tower height proportional to √(file count in that subdirectory).

**Key OAD fields:** (none beyond `actor.inc`).

**Level authoring:** Place one `DirTemplate` object in the Blender scene with `Template Object = 1` and an OOB spawn position (Z = −200). The Director script calls `spawn-template` (custom syscall 7 / `135 sys`) to position and scale it at level start.

**Collision:** `COLTABLEENTRY(File, Player, CI_PHYSICS, CI_PHYSICS)` — player bounces off spawned towers. (The `File`/`Dir` collision entry covers both — the File entry in `objects.mac` line 109 handles the collidable player interaction for both types.)

**See also:** `wflevels/filesys/blender_filesys.py`, [docs/plans/2026-06-12-filesys-browser-level.md](plans/2026-06-12-filesys-browser-level.md).

### `Director` — Per-level orchestrator script

**Source:** `director.oas`
**Includes:** `actor.inc` (default mobility=Physics, model=none)
**Purpose.** Central script-controlled orchestrator for level-wide logic (game loop, enemy waves, spawn timing, camera cuts, win/lose evaluation). Conventionally one per level; the `Script` field on `actor.inc` carries the per-tick logic.

**Key OAD fields:** Empty custom block — full power comes from the `Script` field via `common.inc`. (Not the same as `dir.oas` above — `dir.oas` is a folder marker.)

**Likely uses for arcade ports:** Game-loop coordinator (every port). Ball-spawn cadence (Q✱bert), wave director (Galaga / Space Invaders), level state machine (Pac-Man pellet count, Q✱bert round-clear).

### `Disabled` — Stub for disabled types

**Source:** `disabled.oas`
**Includes:** None
**Purpose.** Placeholder for disabled object types. Marked `LEVELCONFLAGNOINSTANCES` — cannot be placed.

**Key OAD fields:** (none; structural only).

### `Enemy` — Generic enemy base

**Source:** `enemy.oas`
**Includes:** `actor.inc` (default mobility=Physics)
**Purpose.** Base for enemy actors. Empty custom field block — differentiation is done via `Script` and `Mesh Name`. Use as the starting point when an enemy doesn't fit any of the more specific classes.

**Key OAD fields:** (inherited from `actor.inc`).

**Likely uses for arcade ports:** Galaga / Space Invaders enemy ships, Pac-Man ghosts, Q✱bert bestiary (red/purple/green balls, Coily-snake form, Slick / Sam / Ugg / Wrongway).

### `Explosion` — Explosion template

**Source:** `explode.oas`
**Includes:** `actor.inc`
**Purpose.** Template for explosion effects (typically spawned by impact / destroyer / script — not placed by hand). Applies a health-modifier and a force impulse to nearby actors.

**Key OAD fields:**
- `Health Modifier` — Damage to apply (fixed, -100 to +100, default -1).
- `Force` — Impulse magnitude (fixed, 0–100, default 10).

**Likely uses for arcade ports:** Impact effects (bullets, collisions, destructible walls).

### `File` — FSN file box (template-only)

**Source:** `file.oas`
**Includes:** `actor.inc`
**Status:** ✅ Runtime actor — `OBJECTONLYTEMPLATEENTRY`; `file.cc` / `file.hp` present.
**Purpose.** Visual stand-in for a filesystem file in the FSN-style filesystem browser level (`wflevels/filesys/`). Spawned at runtime by the Director Forth script via `ConstructTemplateObject`, never placed directly. Scale mailboxes 3040–3042 drive box height proportional to √(file size in bytes) / 50, minimum 0.1.

**Key OAD fields:**
- `fileSize` — File size in bytes (INT32, 0–2 147 483 647, default 0). Set by the Director Forth script at spawn time.

**Level authoring:** Place one `FileTemplate` object in the Blender scene with `Template Object = 1` and an OOB spawn position (Z = −200). The Director script calls `spawn-template` (custom syscall 7 / `135 sys`) to position and scale it at level start.

**Collision:** `COLTABLEENTRY(File, Player, CI_PHYSICS, CI_PHYSICS)` (`objects.mac` line 109) — player bounces off spawned file boxes.

**See also:** `wflevels/filesys/blender_filesys.py`, [docs/plans/2026-06-12-filesys-browser-level.md](plans/2026-06-12-filesys-browser-level.md).

### `Font` — Font asset ⚠️ schema-only, not shipped

**Source:** `font.oas`
**Includes:** `actor.inc`
**Status:** 🔴 **OAS schema only — NOT registered, NO runtime.** `objects.mac:47` reads `@* OBJECTENTRY(Font,0)` (commented out). No `font.cc` exists. The `.wid` kerning-file format has no runtime consumer. The actually-working text path is `stb_easy_font` (vendored, no kerning file, no `Font` actor needed) called from `DrawHud` in `display.cc`.
**Purpose (intended).** Holds font kerning data. Used by text-rendering paths (HUD, intro text).

**Key OAD fields:**
- `Kerning File` — Path to a `.wid` font kerning file.

**Likely uses for arcade ports:** Score / lives / round indicators if a text-based HUD path is used.

### `Generator` — Spawn-by-mailbox primitive

**Source:** `generator.oas`
**Includes:** `actor.inc` (default no mass)
**Purpose.** Spawns instances of a `Template`-flagged actor at the generator's position, optionally on a periodic cadence and with random displacement. Triggered by mailbox — the canonical script primitive for "spawn an X."

**Key OAD fields:**
- `Activation MailBox` — Trigger mailbox (0–3999, default 1).
- `Object To Throw` — Actor to spawn (object reference; should be a `Template`-flagged actor).
- `Generation Rate` — Time between spawns in seconds (fixed, 0.001–10.0, default 1.0).
- **Object Velocity group:** X/Y/Z velocity at spawn (fixed, -100 to +100 m/s).
- **Random Displacement group:** X/Y/Z range for spawn-position variance (fixed, -100 to +100).

**Likely uses for arcade ports:** Ball / Coily spawner (Q✱bert), bullet generator (Galaga / Space Invaders), pellet drop (Pac-Man), bomb drops (Bomberman).

### `Gold` — Collectible-pickup stub

**Source:** `gold.oas`
**Includes:** `actor.inc` (default no mass, visibility=0, model=Box)
**Purpose.** Minimal stub for pickups / collectibles. Customisation is via `Mesh Name` and `Script`.

**Key OAD fields:** (inherited from `actor.inc`; empty custom block).

**Likely uses for arcade ports:** Score bonuses (Q✱bert bonus tiles, Galaga power-ups), pellets (Pac-Man).

### `Handle` — Level-data handle

**Source:** `handle.oas`
**Includes:** `common.inc`
**Purpose.** Level-wide state holder. Minimal; used for global script data and health tracking.

**Key OAD fields:** (inherited from `common.inc`).

### `InitData` — Level-init payload

**Source:** `init.oas`
**Includes:** `actor.inc`
**Purpose.** Invisible level-global data slot. Conventionally one per level — holds starting-position info and per-level config.

**Key OAD fields:**
- `placeholder` — Stub field (integer, 1–100). Real config comes from script + mailbox state.

**Likely uses for arcade ports:** Level entry-point info, initial actor spawn config.

### `Level Object` — Level metadata + sound bank

**Source:** `levelobj.oas`
**Includes:** `actor.inc`
**Purpose.** Master level container. Configures mailbox count, scratch space, the temporary-object pool, the 128-slot SFX bank, and music tracks.

**Key OAD fields:**
- **Number of Mailboxes group:** `Number Of Mailboxes` (2–500, default 101), `Number Of Scratch Mailboxes` (0–500, default 10).
- **Temporary Objects group:** `Number Of Temporary Objects` (0–500, default 200) — pool size for runtime-spawned objects (used by `generator` etc.).
- **Sound Effects Bank:** 128 slots `sfx0`…`sfx127`, each a `.wav` filename.
- **Music:** `MusicVh` (.vh vab header), `MusicVb` (.vb vab body), `MusicSeq` (.seq MIDI sequence).
- `Sound Yon` — Sound attenuation distance (fixed, 0–500, default 20).

**Likely uses for arcade ports:** Exactly one per level. Q✱bert needs `Number Of Mailboxes ≥ 500` per the MVP plan; SFX bank slots reserved for future audio phase.

### `Light` — Directional light

**Source:** `light.oas`
**Includes:** `actor.inc` (visibility=0, model=none)
**Purpose.** Static directional light. Originally extracted from 3DS Max via `LEVELCONFLAGEXTRACTLIGHT`. Per `level-design-troubleshooting.md`, default rotation `(0,0,0)` produces zero illumination — set `(π/2, 0, 0)` to actually light surfaces.

**Key OAD fields:**
- `lightRed`, `lightGreen`, `lightBlue` — Colour components (fixed, 0–1).
- `lightX`, `lightY`, `lightZ` — Direction vector (fixed, -32768 to +32767).
- `lightType` — Enum (`Directional | Ambient`).

### `Matte` — Background plane / skybox

**Source:** `matte.oas`
**Includes:** `actor.inc` (default model=none)
**Purpose.** Distant background plane (static colour or scrolling tile). Configured via `Model Type=Matte` in `mesh.inc` (background colour or tiled image).

**Key OAD fields:** Inherited from `mesh.inc` Matte groups (colour picker or tile/map config).

**Likely uses for arcade ports:** Single-colour starfield / sky (Q✱bert pyramid backdrop, Galaga starfield, Pac-Man maze surround). `mm_practice` uses one with `Matte Type=Color`.

### `Mesh` — Mesh-block schema shim

**Source:** `mesh.oas`
**Includes:** `mesh.inc`
**Purpose.** Standalone shim that re-emits the Mesh OAD from `mesh.inc`. Rarely instantiated; syncs schema only.

**Key OAD fields:** (see `mesh.inc` above.)

### `Meter` — On-screen mailbox-driven HUD gauge ⚠️ schema-only, not shipped

**Source:** `meter.oas`
**Includes:** `actor.inc`, `meter.inc`
**Status:** 🔴 **OAS schema only — NOT registered, NO runtime.** `meter.cc` / `meter.hp` / `meter.hpi` have never existed in any branch of any WF repo (verified 2026-05-03 across 5 sister repos via `git log --all --diff-filter=D`). The actor is *also* commented out in the type registry: `wfsource/source/oas/objects.mac:42` reads `@* OBJECTENTRY(Meter,0)`. Placing a Meter in a level today would not be recognised. Reaching "shipped" requires (1) a ~100 LOC `meter.cc` rendering pass that reuses `stb_easy_font` (already used by `DrawHud` in `wfsource/source/gfx/gl/display.cc:42-93`), and (2) uncommenting the `OBJECTENTRY` line. Same status for `Font` (`objects.mac:47`).
**Working alternative today:** `DrawHud` reads mailboxes 70 / 71 / 72 every frame and renders `SCORE %d` / `TIME %d` / `LIVES %d` via `stb_easy_font`. Gated `DESIGNER_CHEATS && __LINUX__`. Three slots only, hardcoded labels and positions.
**Purpose (intended).** Render an on-screen gauge driven by a mailbox value (e.g. health bar, ammo counter). Drawn at a fixed screen offset.

**Key OAD fields:**
- `Object` — Actor to monitor (object reference).
- `Mailbox To Display` — Mailbox index (0–3999).
- `Mailbox Type` — Enum (`Scalar | Integer`).
- `Path X Start`, `Path Y Start` — Screen position (fixed, -200 to +200).
- **Display group:** `Increment Before Display` (trigger redraw threshold), `Pause At Keyframe`, `Display Pause Duration` (fixed, 0–32000).
- `Text X Offset`, `Text Y Offset` — Label offset from gauge (0–319 / 0–223).

**Likely uses for arcade ports (once implemented):** Score / lives / energy bar / level / round / fuel — anything numeric. The 3-slot `DrawHud` path covers score/timer/lives today on Linux dev; Meter generalises to any mailbox at any screen position. See `~/wf-games/investigations/2026-05-03-meter-hud-availability.md` for the per-brief breakdown of what each port needs.

### `Missile` — Projectile/bullet template

**Source:** `missile.oas`
**Includes:** `actor.inc` (default mobility=Physics, moves between rooms, template flag)
**Purpose.** Template for projectiles — not placed; spawned by `generator` or by tool fire. Has explosion-on-impact mechanics.

**Key OAD fields:**
- `Explode On Impact` — Boolean (default true).
- `Arming Delay` — Time before active (fixed, 0–100s, default 0.2s).
- `Explosion Delay` — Time to detonate after impact (fixed, 0–3600s, default 2s).

**Likely uses for arcade ports:** Galaga / Space Invaders bullets, Bomberman bombs (delayed-fuse variant), Q✱bert ball-as-projectile if treated mechanically.

### `Movement` — Movement-block schema shim

**Source:** `movebloc.oas`
**Includes:** `movebloc.inc`
**Purpose.** Standalone shim that re-emits the Movement OAD from `movebloc.inc`. Rarely instantiated; syncs schema only.

**Key OAD fields:** (see `movebloc.inc` above.)

### `Movie` — Sprite-strip animation

**Source:** `movie.oas`
**Includes:** `actor.inc`
**Purpose.** Plays a frame-sequence animation (up to 8 frames, configurable per-frame delay). Originally for sprite-based animated actors.

**Key OAD fields:**
- `Frame 0` … `Frame 7` — Bitmap filename (BMP / TGA / SGI).
- `Frame 0 Delay` … `Frame 7 Delay` — Per-frame display duration (fixed, 0–100s, default ~16.67ms = 1/60s).
- `Loop Movie` — Boolean (default true).
- `Play On Texture` — Optional texture target (apply animation to a texture instead of a sprite).
- `Initial Frame` — Starting frame index (0–7).

**Likely uses for arcade ports:** Player walk cycle, enemy patrol patterns (Pac-Man ghost shimmer), title-screen sequence frames.

### `Platform` — Moving walkable surface

**Source:** `platform.oas`
**Includes:** `actor.inc` (default movement sheet expanded)
**Purpose.** Moving walkable surface. Full control via `Mobility` enum and movement params (path-following, physics).

**Key OAD fields:** Inherited from `movebloc.inc` — configure `Mobility=Path` and the path-related subgroup, or `Mobility=Physics` for a kinematic-driven body.

**Likely uses for arcade ports:** Moving platforms in Donkey-Kong-style ports, Pac-Man tunnel transitions, elevator effects.

### `Player` — Playable character

**Source:** `player.oas`
**Includes:** `actor.inc` (default mass=50, mobility=Physics, moves between rooms, hp=1)
**Purpose.** Playable character. Empty custom block — driven entirely by `Script` (often `Script Controls Input=true`) and the inherited movement params.

**Key OAD fields:** Inherited from `actor.inc` and `movebloc.inc`.

**Likely uses for arcade ports:** Q✱bert player (note: Q✱bert MVP plan considers `Mobility=Anchored` to avoid Jolt fighting per-frame `X/Y/Z_POS` writes during the hop arc), Pac-Man (grid-locked movement), Galaga fighter (X-axis-restricted).

### `Pole` — Climbable / swingable pole

**Source:** `pole.oas`
**Includes:** `actor.inc`
**Purpose.** Vertical or diagonal climbing surface with momentum transfer on mount/dismount. Originally for vines / fireman's poles.

**Key OAD fields:**
- `Swing Push` — Initial push velocity on mount (fixed, -100 to +100, default 1.5).
- **Momentum Transfer Ratio group:** `Mount Ratio` (fixed, -100 to +100, default 1.0), `Dismount Ratio` (fixed, -100 to +100, default 1.0).

**Likely uses for arcade ports:** Pitfall vines, Donkey Kong ladders/poles, Q✱bert disc warp (probably better served by `warp` though — see below).

### `Room` — Level-room container

**Source:** `room.oas`
**Includes:** `common.inc`. Marked `LEVELCONFLAGROOM` + `LEVELCONFLAGCOMMONBLOCK`.
**Purpose.** A playable area. Holds adjacent-room references and a room-load mailbox. Actors placed inside a room are culled when the room is unloaded; the global bounding box must strictly contain all renderable geometry, lights, and the camera.

**Key OAD fields:**
- **Adjacent Rooms group:** `Adjacent Room 1`, `Adjacent Room 2` (object references; null = dead end).
- `Room Loaded Mailbox` — Mailbox set when the room loads (0–3999, default 0).

**Likely uses for arcade ports:** One room per screen / level (Q✱bert level1–4, Pac-Man maze, single-screen arcade games).

### `Shadow` — Dynamic shadow template

**Source:** `shadow.oas`
**Includes:** `actor.inc` (default mobility=Physics, moves between rooms, template flag)
**Purpose.** Template for a dynamic shadow cast on the ground beneath an actor. Configured via `mesh.inc` Shadow group on the parent actor.

**Key OAD fields:** Inherited.

**Likely uses for arcade ports:** Depth cue under flying actors — **immediately relevant to Zaxxon's iconic ground-shadow primitive** (the difficulty-score report's friction-callout for Zaxxon may collapse if `shadow` already does what we need). Q✱bert's flying balls could use one too.

### `Shadowp` — Shadow plane variant

**Source:** `shadowp.oas`
**Includes:** `actor.inc`
**Purpose.** Variant of the shadow primitive. Likely a planar / projected variant rather than the template form. Read the source if implementing — only one of `shadow` or `shadowp` is usually wanted per use.

**Key OAD fields:** (inspect source on first use.)

### `Shield` — Temporary invulnerability template

**Source:** `shield.oas`
**Includes:** `actor.inc` (default no mass, mobility=Physics, moves between rooms, template flag)
**Purpose.** Template for a temporary protective state. Blink effect on activation; configurable display duration.

**Key OAD fields:**
- `Blink Frequency` — Blink rate (fixed, 0–100, default 0.2s per blink).
- **Display group:** `Shield Purchase Display` (fixed, 0–100, default 1s), `Invulnerability Display` (fixed, 0–100, default 3s).

**Likely uses for arcade ports:** Galaga power-up invulnerability, Q✱bert green-ball freeze-window for the player, Pac-Man power-pellet "ghosts vulnerable" mode (the inverse — the *enemies* get a state, but the same mechanism applies to the player).

### `Spike` — Damage hazard

**Source:** `spike.oas`
**Includes:** `actor.inc`, `activate.inc`
**Purpose.** Deals damage on collision. Filterable via `ActivatedBy`.

**Key OAD fields:**
- `Health Modifier` — Damage (fixed, -100 to +100, default -1).
- `ActivatedBy` — Enum (`All | Actor | Class | List`).

**Likely uses for arcade ports:** Deadly terrain (Q✱bert spikes / lava), enemy contact damage, wall collisions (Pac-Man).

### `Stationary Platform` — Static walkable surface

**Source:** `statplat.oas`
**Includes:** `actor.inc` (default mesh sheet expanded, mobility disabled)
**Purpose.** Non-moving walkable surface (floor, wall, ramp). Mobility is anchored. Mesh drives appearance.

**Key OAD fields:** Inherited; mobility disabled, mesh configuration is the primary lever.

**Likely uses for arcade ports:** Level geometry — Q✱bert pyramid cube tops, Pac-Man maze walls, Galaga playfield base. `mm_practice` uses a `statplat` for the ramp.

### `Target Position` — Named point in space

**Source:** `target.oas`
**Includes:** `actor.inc` (default no mass, visibility=0, model=none)
**Purpose.** Named point in space. Used by `Camshot` to define look-at or follow targets.

**Key OAD fields:** Inherited (position is the only meaningful data).

**Likely uses for arcade ports:** Cutscene camera-pan targets, follow-cam focus points. `mm_practice` uses two targets to anchor its CamShot.

### `Template` — Generic template-actor base

**Source:** `template.oas`
**Includes:** `actor.inc`
**Purpose.** Abstract template base. Used to mark actors that are *not* placed in the level but live in a template pool — `generator` references these by name in its `Object To Throw` field.

**Key OAD fields:** Empty custom block.

**Likely uses for arcade ports:** Source pool for spawn-by-mailbox patterns: ball/Coily/disc templates (Q✱bert), enemy variants (Galaga), pellet types (Pac-Man), bomb (Bomberman).

### `Test` — Editor field-type test harness

**Source:** `test.oas`
**Includes:** `actor.inc`
**Purpose.** Comprehensive test of all OAS field-widget types — waveform editor, enum dropdowns, sliders, text, object references, numeric ranges. Editor/dev only, not shipped in game data.

**Key OAD fields:** Many — `Waveform`, three views of an enum (`Powerups Menu / Slider / #`), `Field 1`, `LookAt`, `String`, four widget views of "Number of powerups", `Damage` (number + slider), `Aperture`, `Speed`. Use as a reference when adding new OAS fields.

### `Tool` — Weapon / ability definition

**Source:** `tool.oas`
**Includes:** `actor.inc` (default visibility=0, model=none, template flag)
**Purpose.** Weapon or ability. Assigned to a player via `toolset.inc` Tool A–F slots. Configurable activation button, recharge delay, projectile type, scripted behaviour.

**Key OAD fields:**
- `Activation Script` — XData script (`XDATA_SCRIPT`).
- `Object To Throw` — Projectile / beam actor (object reference).
- `Activation Cost` — Resource cost (0–100, default 1).
- `Autofire` — Boolean.
- `Moving Throw Percentage` — Accuracy reduction while moving (0–100%, default 25%).
- `Type` — Enum (`Beam Weapon | Projectile Weapon | Shield | Script Only`).
- `Activation Button` — Enum (`A`–`Z`, `Left Shift`, `Right Shift`).
- `Recharge` — Cooldown (fixed, 0–100s, default 0.2s).
- `Horiz Speed`, `Vert Speed` — Projectile / beam speed (fixed, 0–360).
- **Needle Gun group:** `Max Range` (fixed, 0–10000, default 800), `Beam Spread Angle` (fixed, 0–1 radians, default 0.125).

**Likely uses for arcade ports:** Galaga / Space Invaders blaster, Q✱bert disc-jump (as a "tool" of the player), Bomberman bomb-place ability.

### `Toolset` — Tool-block schema shim

**Source:** `toolset.oas`
**Includes:** `toolset.inc`
**Purpose.** Standalone shim that re-emits the Toolset OAD (six tool slots A–F).

**Key OAD fields:** (see `toolset.inc` above.)

### `Warp` — Teleport / level-transition trigger

**Source:** `warp.oas`
**Includes:** `actor.inc`, `activate.inc`
**Purpose.** Teleports the activator (or warps to a target room) when triggered. Filterable via `ActivatedBy`.

**Key OAD fields:**
- `Target` — Destination actor (object reference; spawn point in the next room or a specific position).
- `ActivatedBy` — Enum (`All | Actor | Class | List`).

**Likely uses for arcade ports:** Pac-Man tunnel wrap, Q✱bert disc-warp-to-apex (the side-disc primitive in the GDD — `warp` looks like the right answer; this should be tried before scripting the warp animation manually), boss-arena entry (Galaga), level transitions in general.

---

## Cross-references — what to use when

These are bindings from common port-implementation needs to the actor types above. **First action when implementing any of these: read the linked OAS source in full and check that the fields match your need.**

| Port-implementation need | Use this primitive |
|---|---|
| Spawn an enemy / projectile / pickup on a mailbox event | `Generator` + `Template`-flagged target |
| Despawn that actor on another mailbox event | `Destroyer` |
| Teleport the player to another actor's position | `Warp` |
| Cut to a different camera view when the player enters a region | `Activation Box Object Reference` (writes a `Camshot` index into a mailbox) |
| Trigger a scripted event when the player enters a region | `Activation Box` (writes a value into a mailbox) |
| Dynamic shadow under a flying actor (Zaxxon ground-shadow, Q✱bert ball shadow) | `Shadow` (template) — investigate; may collapse Zaxxon's friction callout |
| Damage the player / enemy on contact | `Spike` |
| On-screen score / health gauge driven by a mailbox | **Today (3 slots only):** `DrawHud` (`display.cc:42-93`) reads mb 70/71/72 as score/timer/lives via `stb_easy_font`, Linux dev only. **Per-actor configurable form:** `Meter` OAS schema exists but is **not implemented** (no `meter.cc`, registration commented out in `objects.mac:42`) — needs ~100 LOC. |
| Temporary invulnerability or blink effect | `Shield` (template) |
| Climbable vine / pole | `Pole` |
| Static level geometry | `Stationary Platform` |
| Moving platform / kinematic surface | `Platform` |
| Sprite-strip animation (e.g. character walk cycle) | `Movie` |
| Static directional light | `Light` (set rotation `(π/2, 0, 0)`) |
| Solid-colour or scrolling-tile backdrop | `Matte` (with `Model Type=Matte`) |
| Look-at / follow target for a CamShot | `Target Position` |
| Per-level config + SFX bank + music | `Level Object` (one per level) |
| Per-level orchestration script | `Director` |
| Level-init data slot | `InitData` |
| Room container | `Room` |
| Camera entity | `Camera` + one or more `Camshot`s |
| Player character | `Player` |
| Generic enemy AI base | `Enemy` |

## Notes on the Q✱bert MVP plan in light of this index

Two specific friction items in [docs/plans/2026-05-03-qbert-mvp.md](plans/2026-05-03-qbert-mvp.md) should be re-evaluated against this index before being implemented as listed:

1. **§ 2 "Cube colour state" friction (84 actors / scripts).** The plan considers a "Visibility = mailbox value matches integer N" predicate as a hypothetical runtime helper. It does not exist in the index above — the visibility model in `mesh.inc` uses a single `Visibility Mailbox` slot (0=hidden, 1=shown). The 84-actor approach stands. (No reduction.)

2. **HUD deferral.** The plan defers visible HUD on the assumption that the engine doesn't render mailboxes 70/71/72. **In fact `DrawHud` already does** — `wfsource/source/gfx/gl/display.cc:42-93` reads those exact slots and rasterises score/timer/lives via the vendored `stb_easy_font`. Linux dev only (`DESIGNER_CHEATS`). The `Meter` OAS actor (which would let any level place per-actor configurable readouts) is **schema-only and disabled in `objects.mac:42`** — needs ~100 LOC to ship. For Q✱bert MVP+ the 3-slot path covers score/timer/lives today; level/round/cubes-to-target need the Meter renderer first.

3. **Disc-warp animation in the bestiary phase.** `warp` is in the index. The disc-warp-to-apex primitive in the Q✱bert GDD is most likely just a `Warp` with `Target=apex-cube`. The custom Forth handler may not be needed.

4. **Spawn-by-mailbox** (already corrected in the plan): `Generator` + `Template` is the path.
