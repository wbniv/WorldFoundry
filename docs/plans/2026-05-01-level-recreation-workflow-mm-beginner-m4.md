# Plan: Level Recreation Workflow + mm_beginner (M4)

**Status:** DONE — ROM extraction complete and the recreation workflow is proven end-to-end; MM Blender levels built ([`wflevels/mm_practice*`](../../wflevels)).

## Context

We need to faithfully reproduce the original Marble Madness arcade game (Atari, 1984) in WorldFoundry — same path topology, same hazard types, same general gameplay feel. Levels are not designed; they are reproduced from reference.

**bestiary.md and stages.md are of unknown provenance and partially invented** — verified against [Wikipedia](https://en.wikipedia.org/wiki/Marble_Madness), [MobyGames](https://www.mobygames.com/game/466/marble-madness/), and [Arcade Museum](https://www.arcade-museum.com/Videogame/marble-madness): marble-muncher and acid-puddle are real; magnet-attractor/repulsor are not in the original game. These docs must be validated against the ROM before use.

The source of truth hierarchy:
1. **Arcade ROM** — canonical; vendored at `assets/arcade-roms/marble.zip` (git binary)
2. **MAME + ROM** — run the actual game; extract heightmap data from ROM for exact geometry
3. **NES port level maps** — secondary visual reference ([nesmaps.com](https://nesmaps.com/maps/MarbleMadness/MarbleMadness.html)); NES deviates from arcade but path topology is close
4. **`/home/will/wf-games/marble-madness/stages.md`** and **`bestiary.md`** — treat as rough starting point only; verify every claim against ROM/MAME

Previous authoring method (`gen_lev.py`) generated `.lev` in Python with no visual feedback — every change required a full rebuild cycle. We now have Blender MCP for an interactive loop with viewport screenshots.

---

## Part 1 — Level Recreation Workflow

### Reference images → Blender background → level geometry

Standard game porting technique:
1. Download NES map PNG for the target level from nesmaps.com
2. Import as a Blender background reference image in the top viewport
3. Scale the reference to match stages.md world dimensions (e.g. Beginner = 50 m × 40 m)
4. Model path geometry on top of the reference, matching topology tile-by-tile
5. Screenshots via MCP to compare viewport vs. reference during iteration

NES map PNG URLs (direct):
- Practice: `https://nesmaps.com/maps/MarbleMadness/MarbleMadnessRace1.png`
- Beginner: `https://nesmaps.com/maps/MarbleMadness/MarbleMadnessRace2.png`
- Intermediate: `https://nesmaps.com/maps/MarbleMadness/MarbleMadnessRace3.png`
- Aerial: `https://nesmaps.com/maps/MarbleMadness/MarbleMadnessRace4.png`
- Silly: `https://nesmaps.com/maps/MarbleMadness/MarbleMadnessRace5.png`
- Ultimate: `https://nesmaps.com/maps/MarbleMadness/MarbleMadnessRace6.png`

(Verify URLs before use; nesmaps.com naming may differ. Source: [NES Maps - Marble Madness](https://nesmaps.com/maps/MarbleMadness/MarbleMadness.html) — complete maps originally by Ray Dempsey / Nintendo Player.)

### ROM extraction — COMPLETE ✓

ROM format fully reverse-engineered 2026-05-01 via MAME Lua runtime analysis. See [`docs/investigations/2026-05-01-marble-madness-rom-level-data.md`](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-01-marble-madness-rom-level-data.md) for full methodology.

**What's done:**
- `assets/arcade-roms/marble.zip` — 38-file complete ROM vendored (git binary)
- `assets/arcade-roms/reference/practice_start.png` — MAME screenshot
- `wflevels/marble-madness/decode_levels.py` — decoder for all 6 levels; run against `assets/arcade-roms/marble.zip` to get `wflevels/marble-madness/levels.json`

**Format confirmed:** Level pointer table at `0x01DEC0` → per-level descriptor arrays (6-byte `[type:u16][addr:u32]` entries, sentinel `0xFFFF`) → 24-byte segment records at `+02` h_left, `+04` h_right, `+0A` h_center. Segments with h_center=5 are goal zones.

**All 6 levels decoded:**

| Level | Segments | desc_addr |
|-------|----------|-----------|
| Practice | 13 | 0x01DF26 |
| Beginner | 9 | 0x01DF7A |
| Intermediate | 4 | 0x01DFB6 |
| Aerial | 12 | 0x01DFD4 |
| Silly | 5 | 0x01E022 |
| Ultimate | 23 | 0x01E046 |

**Unknowns still open:** type field semantics (camera angle? path heading?), absolute world-scale for height values, path width encoding (`0x0C14` constant — may be L=12, R=20 units).

### ROM → WF geometry converter (NEXT STEP)

`decode_levels.py` outputs `levels.json` with h_left/h_right/h_center per segment. Need a converter that turns these into Blender mesh geometry in WF world coordinates.

**Key unknowns to resolve before writing converter:**
1. **Height scale**: h_center ranges ~5–60 in Practice. mm_practice spawns at Z≈13, goal at Z≈0 → roughly 13 m drop. Practice has 13 segments; centre heights go from ~17 down to 5. Working hypothesis: 1 game unit ≈ 0.3–0.5 WF metres (needs calibration from MAME screen + mm_practice visual match).
2. **Path width**: constant `0x0C14` in segment records may encode left/right wall offsets (12 and 20 game units from centre → path ~8 units wide). Wall heights (h_left, h_right) are likely lip heights above the path spine.
3. **Segment length**: unknown how long each path segment is in world units. Approach: divide total level run length by segment count, or look for the path length field in the 24-byte record's unknown words.

**Converter plan (`wflevels/marble-madness/rom_to_blender.py`):**

```python
# Pseudocode — fill in once scale is calibrated
import json, bpy

GAME_UNIT = 0.4  # metres per game unit (calibrate from mm_practice)
SEG_LENGTH = 3.0  # metres per segment (estimate; calibrate)

def segment_to_mesh(seg, i, direction=(−0.707, −0.707, 0)):
    """
    Build a trapezoidal cross-section path segment in Blender:
      - floor at height = h_center × GAME_UNIT
      - left lip at height = (h_center + h_left) × GAME_UNIT
      - right lip at height = (h_center + h_right) × GAME_UNIT
      - width: 8 game units × GAME_UNIT
    """
    pass
```

Run `decode_levels.py` first to produce `levels.json`, then `rom_to_blender.py` imports it via MCP to build the full course geometry in Blender before the export step.

### MAME screenshot reference

`assets/arcade-roms/reference/practice_start.png` — Practice level start (captured headless). Use for topology sanity-check during Blender modelling. Capture more level screenshots if needed:

```bash
mame marble -window -seconds_to_run 8 -snapshot_directory assets/arcade-roms/reference/ -snapname beginner_start
# then navigate in-game to Beginner start before frame 480
```

### Full workflow per level

```
ROM GEOMETRY EXTRACTION (one-time per level, already done for all 6)
  python3 wflevels/marble-madness/decode_levels.py assets/arcade-roms/marble.zip
    → wflevels/marble-madness/levels.json   (h_left/h_right/h_center per segment)

BLENDER SESSION (MCP-driven Python)
  Import mm_practice.lev as infrastructure template
    (Director, Player, Camera, Room, CamShot — pre-configured OAD + scripts)
  Clear gameplay geometry (delete ramp mesh)
  Run rom_to_blender.py via MCP → generates path mesh from levels.json
    (segment trough geometry: floor at h_center, lips at h_left/h_right)
  [Optional] Load NES map PNG as background for topology/hazard position check
  Place hazard actor empties at segment-matching positions
  Set OAD properties + Forth scripts on actors
  Screenshot loop: compare viewport to ROM data / NES reference; adjust scale
  Export: bpy.ops.wf.export_level(filepath=<level>.lev)

BUILD PIPELINE (unchanged from mm_practice)
  iffcomp-rs  <level>.lev      → <level>.lev.bin
  iff2lvl     <level>.lev.bin  → <level>.lvl
  levcomp-rs  <level>.ini      → <level>.iff.txt
  iffcomp-rs  <level>.iff.txt  → <level>-standalone.iff
```

### What stays in build scripts (not Blender)

- `<level>.ini` — nRooms + asset list
- `<level>.iff.txt` — asset manifest (levcomp-rs generates this)
- `build_level.sh` — orchestrates full pipeline
- New actor OAD schemas if any new actor type needed (edit `.oad` source in `wftools/`)

### Infrastructure template objects (from mm_practice, kept as-is)

Director, Player, Camera, Room, CamShot — keep these from the mm_practice import; only adjust:
- Room bbox to match new stage dimensions
- Director Forth for correct timer value
- Player spawn position
- Camera position above the new level footprint

### Per-level checklist

- [x] ROM decoded → `levels.json` (all 6 levels; 2026-05-01)
- [ ] Write `rom_to_blender.py` geometry converter (calibrate scale against mm_practice)
- [ ] Open Blender + MCP connect
- [ ] Import mm_practice.lev, delete ramp mesh
- [ ] Run `rom_to_blender.py` via MCP → path mesh in scene
- [ ] [Optional] NES PNG as background for hazard position reference
- [ ] Place hazard actors at segment positions
- [ ] Screenshot + compare to MAME reference; iterate on scale
- [ ] Export → build → smoke test
- [ ] Commit
- [ ] Evaluate before continuing to next level

---

## Part 2 — mm_beginner (first application of workflow, M4)

### stages.md spec

- **Size:** 50 m × 40 m × 8 m vertical drop
- **Timer:** 75 s
- **Path:** forks at mid-level — short/slimy left vs. long/clean right; merges lower
- **Hazards:** 3 slime-drip emitters, 2 fall-off-edge trigger volumes
- **New actors:** `slime-drip`, `fall-off-trigger` — script-only; no new C++ class

### NES Beginner reference topology

Sources: [nesmaps.com Beginner Race](https://nesmaps.com/maps/MarbleMadness/MarbleMadnessRace2.html); [GameFAQs NES walkthrough by Ranza](https://gamefaqs.gamespot.com/nes/587438-marble-madness/faqs/9367); [Neoseeker complete walkthrough](https://www.neoseeker.com/marble-madness/faqs/114160-nes-a.html)

Path flows top→bottom (high→low Y in WF). One fork at ~mid-level:
- Left branch: narrower, 3 hazard positions (slime-drip translations of NES worm/obstacle positions)
- Right branch: unwalled ramp (fall-off zone below = fall-off-trigger volume)
- Merge platform lower
- Gap section (missing tile area marble routes around)
- Final ramp to goal

### Geometry objects to model in Blender (over reference)

| Object | Based on |
|--------|----------|
| `upper_path` | Wide trough, spawn to fork |
| `slimy_fork` | Left branch, trough with lips, 3 slime positions overhead |
| `clean_fork` | Right branch, **no side walls** — fall-off-trigger volume below |
| `lower_merge` | Platform joining both branches |
| `gap_section` | Path with ~1 m gap for marble to route around |
| `lower_ramp` | Descent to goal platform |
| `goal_platform` | Flat area, goal trigger |

### Actor placement

| Actor | OAD | Change from mm_practice |
|-------|-----|------------------------|
| Director | `director.oad` | Timer = 75 s (`INDEXOF_TIME read-mailbox 75 +`) |
| Player | `player.oad` | Spawn position updated for new stage |
| Camera | `camera.oad` | Repositioned above 50×40 footprint |
| Room | `room.oad` | Bbox: local ≥ (-30,-25,-20)-(30,25,15) |
| CamShot ×2 | `camshot.oad` | One per fork region |
| slime-drip ×3 | `statplat.oad` | New: countdown → slime signal MB |
| fall-off-trigger ×2 | `actboxor.oad` | New: Z_POS < floor → MB13 |

### slime-drip as script-only (simplified M4 — no engine spawner yet)

Writes a "slime active" global mailbox that the Player script reads to cap speed:

```forth
\ wf
: do-slime-drip-tick
  MB_LOCAL_TIMER read-mailbox 1 -
  dup 0 <= if drop 90 1 MB_SLIME_SIGNAL write-mailbox
            else      0 MB_SLIME_SIGNAL write-mailbox
  then
  MB_LOCAL_TIMER write-mailbox
;
do-slime-drip-tick
```

### fall-off-trigger as script-only

```forth
\ wf
INDEXOF_Z_POS read-mailbox -10 < if 1 13 write-mailbox then
```

Trigger's bbox covers death plane below unwalled section. Entry → MB13 → director decrements lives.

### Files to create

| File | Action |
|------|--------|
| `wflevels/marble-madness/rom_to_blender.py` | **First**: converter `levels.json` → Blender mesh; calibrate GAME_UNIT + SEG_LENGTH against mm_practice visual |
| `wflevels/mm_beginner/blender_create_mm_beginner.py` | MCP script: import mm_practice template, run converter, place actors, export |
| `wflevels/mm_beginner/mm_beginner.ini` | nRooms=1 + asset list |
| `wflevels/mm_beginner/build_level.sh` | pipeline orchestration |
| `docs/plans/2026-05-01-level-recreation-workflow.md` | workflow plan doc (write after first level complete) |
| `docs/plans/2026-05-01-marble-madness-faithful.md` | M4 status update |

### Reference files to read before writing blender script

- `wflevels/mm_practice/blender_create_mm_practice.py` — MCP bootstrap pattern
- `wflevels/mm_practice/gen_lev.py` — current actor property values (bbox, spawn, scripts)
- `docs/level-design-troubleshooting.md` — bbox/camera/physics gotchas

### Verification

1. Blender viewport screenshot matches NES Beginner reference topology
2. Build pipeline → `mm_beginner-standalone.iff` runs 10+ s without crash
3. Marble reaches goal via both forks
4. Fall off unwalled section → respawn (lives decrement, HUD updates)
5. Timer counts down from 75 on HUD
6. Evaluate workflow quality before proceeding to mm_intermediate

### Deferred to M5

- Actual slime-blob mesh (engine-side spawner not implemented; using friction signal for now)
- CamShot transitions between forks
- Goal → warp to mm_intermediate
- Checkpoint at fork merge point
