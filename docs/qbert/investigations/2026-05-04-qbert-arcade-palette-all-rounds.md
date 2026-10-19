# Q✱bert Arcade Palette — All Rounds (MAME palette investigation)

**Date:** 2026-05-04  
**Updated:** 2026-05-05  
**Status:** Partial — L1R1–L2R4 and L3R1 captured via pixel sampling; definitive `:palette` device
capture running now (see §Method — MAME palette device).

## Method

### MAME device discovery (2026-05-05)

Running `qbert_palette_dump.lua` revealed MAME exposes a `:palette` device (`type=palette`).
Full device list:

```
:           qbert        (root)
:maincpu    i8088
:nvram      nvram
:watchdog   watchdog
:screen     screen
:gfxdecode  gfxdecode
:palette    palette      ← readable via pen_color(i)
:speaker    speaker
:r1sound    gotsndspr1a
```

The `palette` device **bypasses the write-only hardware problem entirely**: MAME's palette
subsystem tracks every palette write internally and exposes the resolved ARGB value for each
pen directly in Lua. No write-tap needed.

### MAME palette device — definitive approach (current)

Script: `scripts/research/mame/qbert_palette_capture.lua`

```lua
palette_dev = manager.machine.devices[":palette"]
-- For each hardware pen (0–15):
local c = palette_dev:pen_color(i)   -- returns 0xAARRGGBB integer
local r = (c >> 16) & 0xFF
local g = (c >>  8) & 0xFF
local b =  c        & 0xFF
```

The script:
1. Sets Demo Mode DIP (`"Demo Mode (Unlim Lives, Start=Adv (Cheat)"` → 1)
2. Presses 1P Start every 1800 frames to advance rounds
3. Reads all 16 palette pens at frame+60 after each advance (game has loaded new palette by then)
4. Prints full `#RRGGBB` table and saves a PNG screenshot per round
5. Exits after 8 rounds (L1R1–L2R4)

This gives ROM-ground-truth color values without pixel coordinate calibration or DAC math.

### Earlier method: pixel sampling (2026-05-04)

Used when the `:palette` device approach was not yet known.

- MAME lossless 240×256 PNGs
- Calibrated face coordinates from L1R1 (known colors):
  - **Apex top face:** y=57, x=112–124
  - **Lit face:** y=89, x=90–93 and x=128–130
  - **Shadow face:** y=89, x=110–113 and x=148–150
- Python PIL pixel mode extraction

Pixel-sampled values are retained in the table below until superseded by `:palette` device output.

### How DIP switches were found

```bash
mame qbert -rompath ... -listxml | python3 -c "
import sys, xml.etree.ElementTree as ET
root = ET.fromstring(sys.stdin.read())
for game in root.findall('machine'):
    if game.get('name') == 'qbert':
        for dp in game.findall('.//dipswitch'):
            print(dp.get('name'))
"
```
Key DIPs: Demo Mode (Unlim Lives, Start=Adv), Free Play, Service Mode, Sound Test.

### Lit/shadow terminology

- **Lit** = left-side face in the isometric projection (facing approx upper-left; lighter in L1)
- **Shadow** = right-side face (facing lower-right; darker in L1)

For rounds where the lighter/darker assignment reverses (e.g. L1R2, L2R1), hardware bakes a
different implied light source into the palette. For the WF port: use the lighter of the two
as `side_rgb` since WF applies its own dynamic lighting.

---

## Per-round color table

Colors are pixel-sampled from MAME lossless PNGs — these are the exact bytes the framebuffer
holds. All values are 8-bit RGB hex. "?" = not captured or uncertain in this run.

Reference screenshots in `docs/plans/screenshots/qbert-arcade-L{L}R{R}-{timing}.png`.

### Level 1

| Round | Snap timing | start_top (state 0) | target_top (state 2) | lit_side | shadow_side | Notes |
|-------|-------------|---------------------|----------------------|----------|-------------|-------|
| L1R1  | early       | **`#5646EF`** purple | **`#DEDE00`** yellow | **`#56A999`** teal | **`#314646`** dark-teal | All colors ROM-verified (see below). Target at 0.2% of pixels in early snap. |
| L1R2  | late (all flipped) | ? | **`#EFDE77`** golden | **`#FF7721`** bright-orange | **`#663100`** dark-orange | Late snap — all cubes at target; start color not captured. Lit/shadow roles reversed vs L1R1 (right face = brighter here). |
| L1R3  | early       | **`#B9CECE`** silver-gray | ? | **`#777777`** mid-gray | **`#212121`** near-black | Early snap — all cubes at start. Target not yet visible. |
| L1R4  | early(?)    | **`#0066EF`** blue | ? | **`#778888`** gray-teal | **`#101099`** dark-blue | All cubes at one color — likely start. Target unknown. |

Screenshot sources: `qbert-arcade-L1R{1,2,3,4}-{early,late}.png`

### Level 2

| Round | Snap timing | start_top (state 0) | target_top (state 2) | lit_side | shadow_side | Notes |
|-------|-------------|---------------------|----------------------|----------|-------------|-------|
| L2R1  | early       | **`#0046DE`** dark-blue | ? | **`#FF7721`** orange | **`#663100`** dark-orange | Same side colors as L1R2. All cubes at start. |
| L2R2  | mixed(?)    | **`#990066`** dark-magenta | ? | **`#778888`** gray-teal | **`#101099`** dark-blue | Same side colors as L1R4. Top color may be start or target — uncertain. |
| L2R3  | early       | **`#FF6666`** red-pink | **`#DEDE00`** yellow | **`#56A999`** teal | **`#314646`** dark-teal | Same sides AND same target as L1R1. Target at 0.23% of pixels. |
| L2R4  | late        | ? | **`#CECE00`** golden-yellow | **`#000000`** black | **`#000000`** black | **Black sides — cubes render as flat diamonds.** Very distinctive look. Only one dominant color in the screenshot. |

Screenshot sources: `qbert-arcade-L2R{1,2,3,4}-{early,late}.png`

### Level 3

| Round | Snap timing | state 0 | state 1 (intermediate) | state 2 (target) | sides | Notes |
|-------|-------------|---------|------------------------|-----------------|-------|-------|
| L3R1  | mid (3-state visible) | **`#2188CE`** medium-blue (tentative) | **`#B93131`** red (tentative) | **`#B9B921`** yellow-green (tentative) | **`#000000`** black (tentative) | Three cube top colors visible in equal proportions (~11.8% each). Side colors not prominent — likely black. State ordering is tentative (bottom rows of pyramid appear blue = unvisited → state 0). |
| L3R2–L3R4 | not captured | ? | ? | ? | ? | — |

Screenshot source: `qbert-arcade-L3R1-mid.png`

### Level 4

| Round | All colors | Notes |
|-------|------------|-------|
| L4R1–L4R4 | **Not captured** | Run ended at L3R1. Extend `qbert_dip_cheat.lua` to 40000+ frames to capture. |

---

## ROM research

### Gottlieb hardware palette

The Q✱bert cabinet uses a Gottlieb System 2 board with a runtime-programmable 16-color palette:

- **Palette RAM address:** CPU 0x5000–0x57FF (programmed by the 6809 CPU)
- **Read behavior:** write-only hardware — reads always return `0x00` regardless of what was written
- **Encoding:** 2 bytes per color entry (32 bytes for 16 colors):
  - Even byte (index × 2): `G[7:4] | B[3:0]` — 4-bit green in high nibble, 4-bit blue in low nibble
  - Odd byte (index × 2 + 1): `R[3:0]` — 4-bit red in low nibble, upper nibble unused
- **DAC:** Resistor network {2000, 1000, 470, 240} Ω; 4-bit value → 8-bit output via MAME's `gottlieb_state::palette_init_gottlieb`
  - Theoretical mapping: `{0,16,33,49,70,86,102,118,136,152,169,185,206,222,238,255}`
  - MAME-rendered pixel values differ slightly from the theoretical formula (hardware calibration)

### L1R1 palette location in ROM

The 16-color master palette for L1R1 was found at **file offset `0x0F50`** in `qb-rom2.bin`
(CPU address `0xAF50` in the 6809 address space).

Cross-checked: the pixel-sampled MAME output for all 4 confirmed L1R1 colors
(`#5646EF`, `#DEDE00`, `#56A999`, `#314646`) appear in the decoded ROM block at 0x0F50.

Adjacent 32-byte blocks were examined but not definitively matched to specific rounds. The game
programs palette RAM at startup and on level transitions — capturing these writes requires
a MAME memory write-tap (see below).

### Why direct reads fail for palette discovery

Confirmed via Lua scan: `mem:read_u8(0x5000)` always returns 0x00 regardless of game state.
This is not a bug — the Gottlieb palette RAM is write-only hardware.

**Two working alternatives:**

1. **`:palette` device** (preferred): `manager.machine.devices[":palette"]:pen_color(i)` returns the
   MAME-tracked ARGB value for each pen. Bypasses the hardware write-only restriction entirely.

2. **Write-tap** (alternative): intercept the writes at the hardware address:
   ```lua
   mem:install_write_tap(0x5000, 0x501F, "pal_tap", function(off, data, mask)
       local idx = off - 0x5000   -- NOTE: off is absolute address, subtract base
       -- even idx = G[7:4]|B[3:0], odd idx = R[3:0]
   end)
   ```
   Earlier scripts had a bug using `off` directly as the index instead of `off - 0x5000`.
   The `:palette` device approach is simpler and avoids this.

### Lives counter

- **Address:** `0x0D00`
- **Confirmed:** RAM diff at T0 (3 lives) vs T1 (after first death) showed `03→02` at `0x0D00`
- Writing `3` to `0x0D00` every frame = infinite lives (used in early scripts before DIP cheat was found)

---

## Patterns and observations

1. **Side colors repeat across rounds.** Rounds share the same lit/shadow side pair:
   - Teal pair `#56A999` / `#314646`: L1R1, L2R3
   - Orange pair `#FF7721` / `#663100`: L1R2, L2R1
   - Gray-blue pair `#778888` / `#101099`: L1R4, L2R2
   - Gray pair `#777777` / `#212121`: L1R3 (unique so far)
   - Black `#000000` / `#000000`: L2R4, L3R1 (flat diamond look)

2. **Target color `#DEDE00` (yellow) recurs.** L1R1 and L2R3 both use yellow as target.

3. **Level 2, Round 4** has black sides — an intentionally flat look, very different from Level 1.

4. **Level 3 is 3-state.** Three distinct top colors visible simultaneously.

5. **The lit/shadow face assignment appears to reverse** for orange-sided rounds vs teal-sided rounds.
   Hardware bakes the 3D shading illusion; the light source direction (implied by the brighter face)
   differs between palettes. For the WF port: use the lighter of the two side colors as `side_rgb`.

---

## Data gaps and how to fill them

The `:palette` device approach (`qbert_palette_capture.lua`, currently running) will fill
most gaps for L1R1–L2R4: it dumps all 16 pens at round start AND we can read at
multiple points within a round to distinguish start vs target colors.

| Missing | Status | Method |
|---------|--------|--------|
| L1R2 start color | **Filling now** | `qbert_palette_capture.lua` round 2 pen dump |
| L1R3 target color | **Filling now** | Same — need late-round pen read |
| L1R4 start vs target | **Filling now** | Dump pens early + late in the round |
| L2R1 target color | **Filling now** | Same |
| L2R2 all colors | **Filling now** | Same |
| L2R4 start color | **Filling now** | Same |
| L3R1 state order | Partially — round 9 not in current run | Extend to 12+ rounds |
| L3R2–L4R4 | Not in current run | Extend `qbert_palette_capture.lua` to 16 rounds |

To capture L3–L4: change the exit condition in `qbert_palette_capture.lua` from 8 to 16
and bump the total frame budget accordingly.

---

## WF Phase A.5 mapping

Phase A.5 = 12 IFF variants, level counter = `ROUND_NUMBER / 4` (integer divide, 0-based).

| Level | Round range | Representative round | state0_top | state1_top | state2_top | side_rgb | Status |
|-------|-------------|----------------------|------------|------------|------------|---------|--------|
| 1 | R1–R4 | L1R1 | `#5646EF` | placeholder | `#DEDE00` | `#56A999` | ✅ implemented |
| 2 | R5–R8 | L2R1 | `#0046DE` | placeholder | **`?`** | `#FF7721` | target unknown |
| 3 | R9–R12 | L3R1 | `#2188CE`? | `#B93131`? | `#B9B921`? | `#000000`? | tentative |
| 4 | R13–R16 | L4R1 | ? | ? | ? | ? | not captured |

For levels 1–2 (1-step arcade mechanic), state 1 is unused by the game logic but the mesh still
exists; use a visually plausible placeholder (e.g. interpolate between state 0 and state 2).

For levels 3–4 (2-step mechanic, added in Phase E), all three states are meaningful.

---

## Lua scripts used

All scripts checked in under `scripts/research/mame/`.
Run via: `mame qbert -rompath assets/arcade-roms -autoboot_script scripts/research/mame/<name>.lua -window -sound none -skip_gameinfo`

| Script | Purpose | Status |
|--------|---------|--------|
| `qbert_palette_capture.lua` | **Current:** DIP cheat + `:palette` device read, 8 rounds, screenshots per round | Active |
| `qbert_palette_dump.lua` | Device enumeration — found `:palette` device; fixed `shortname` property vs method | Done |
| `qbert_dip_cheat.lua` | DIP cheat + screenshot every 1500 frames — produced original pixel-sample table | Done |
| `qbert_palette_tap.lua` | Write-tap on 0x5000–0x501F — installs correctly; had `off` vs `off-0x5000` index bug | Superseded |
| `qbert_wide_scan.lua` | Full RAM range scan — found lives counter at 0x0D00 | Done |
| `qbert_lives_hunt.lua` | RAM diff across a Q✱bert death to isolate lives address | Done |
| `qbert_find_state_and_palette.lua` | RAM snapshot diff before/after one hop to find cube-state address | Done |
| `qbert_get_colors.lua` | Earlier `:palette` device prototype; coin-insert timing + live palette reads | Superseded by capture |
| `qbert_level_colors.lua` | `:palette` device + candidate cube-state RAM scan in one pass | Superseded by capture |
| `qbert_diag.lua` | Dump all MAME input fields (found DIP names) | Done |
| `qbert_discover.lua` | Dump all ioport fields with tags and types | Done |
| `qbert_levels.lua` | 30-hop covering-walk sequence (Warnsdorff DFS) to visit all 28 cubes | Superseded by DIP cheat |
| `qbert_advance_levels.lua` | Earlier hop-sequence round advance — desynchronized after deaths | Superseded by DIP cheat |
