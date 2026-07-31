# Plan: position-display HUD overlay on the moon level (text + minimap)

**Status:** Done
**Date:** 2026-05-31
**Estimate:** 3.5 h · **Actual:** ~2 h (faster than estimate because the existing HUD plumbing took everything as expected)

## Context

The moon level drops the astronaut into a real 1 km × 1 km lunar play area at PGDA Site 01 (Connecting Ridge, ~89.5°S 227°E, between Shackleton and de Gerlache craters), but once you're walking around the regolith there's no on-screen indication of where you are. The user wants a HUD overlay that grounds the walk geographically — *this is the Moon, you're at this real lat/lon, this real elevation, and here's a top-down picture of the play area with you on it.*

Engine-side change is in scope (user-granted exception).

## Approach

Two-part overlay on the moon level: a 4-line text block in the top-left under SCORE, and a small minimap inset in the top-right. Both are mailbox-gated by `wf_moon_overlay_enabled` so SMB / qbert / other levels are untouched.

### Mockups

#### Full-screen composition (at spawn)

```
+--------------------------------------------------------------------------+
| SCORE 0                  TIME 0                  LIVES 3                 |
|                                              +------------------------+  |
| SITE 01 -- CONNECTING RIDGE                  |....::::::~~~~~~--------|  |
| LAT 89.5142 S  LON 227.0381 E                |....::::::~~~~~~--------|  |
| ELEV +1944 m   (delta +0.0 m)                |..::::~~~~~XX~~--------- |  |
| POS X+0   Y+0   (m from spawn)               |::::~~~~~~~--[#]-------- |  |
|                                              |::::~~~~~~~-----------  |  |
|                                              |::::~~~~~~~~----------- |  |
|                                              |::~~~~~~~~~~~~--------- |  |
|                                              |::~~~~~~~~~~~~--------- |  |
|                                              +------------------------+  |
|                                                                          |
|                                                                          |
|                  .                                                       |
|              (astronaut speck)        (Starship lander tower)            |
|                                                                          |
+--------------------------------------------------------------------------+
   Minimap legend (128x128 px, top-right corner, 8px margin):
     [#]  spawn point  -- hollow yellow square, 4x4 px, at game-world (0,0)
      X   lander       -- yellow cross, 6 px, at game-world (+30, +25)
      .   astronaut    -- yellow filled dot, 3x3 px, live position from mailboxes
      ^   compass tip  -- cyan triangle pointing in heading direction (live)
     ~/.  hillshade    -- 256x256 downsampled NAC tile (decimated to display size)
     1-px white border so it reads against the black lunar sky
```

#### Minimap detail (10x zoom of the inset, after walking +200 east, +120 north)

```
                       +-----------------------------+
                       |.....::::::~~~~~~~~~~~~~~~--|  <- 89.5188 S edge
                       |.....::::::~~~~~~~~~~~~~~~--|     (north edge of play area)
                       |.....::::::~~~~~~~~~~~~~~~--|
                       |....::::::~~~~~XX~~~~~~~~~--|  <- lander X (+30, +25)
                       |....::::::~~~~~~^~~~~~~~~~--|  <- cyan chevron tip (heading +Y up)
                       |....::::::~~~~~~.~~~~~~~~~--|  <- astronaut dot (+200, +120)
                       |....::::::~~~~~~~~~~~~~~~--|
                       |....::::::~~~~~~~~~~~~~~~--|
                       |....::::::~~~~[#]~~~~~~~~--|  <- spawn square (0, 0) at centre
                       |....::::::~~~~~~~~~~~~~~~--|
                       |....::::::~~~~~~~~~~~~~~~--|
                       |....::::::~~~~~~~~~~~~~~~--|
                       |....::::::~~~~~~~~~~~~~~~--|  <- 89.5096 S edge
                       +-----------------------------+   (south edge of play area)
                          227.012 E -----------> 227.064 E

  game-world axes inside the minimap:
     X+ -> right    (toward +east-ish; not exactly east at 89.5 S)
     Y+ -> up       (toward +north-ish)
  No cardinal-direction arrow in v1 (deferred -- needs PS meridian-convergence math)
```

#### Text block close-up (after walking +200 east, +120 north)

```
SITE 01 -- CONNECTING RIDGE
LAT 89.5101 S  LON 227.7795 E      <- lon shifted ~0.74 deg east (200m at this lat)
ELEV +1947 m   (delta +3.2 m)      <- +3.2 m above spawn elevation
POS X+200  Y+120   (m from spawn)  <- raw game-world delta
```

Colour: yellow (0xFFFF00) to match the existing SCORE/TIME/LIVES text; same `glColor3f(1,1,0)` already in `DrawHud()`.

### Part A: text block (top-left)

Reuses the SMB/qbert HUD plumbing wholesale — `DrawHudText` + `stb_easy_font` + mailbox-to-extern path. No new GL primitives, no font work.

### What the overlay shows (4 lines)

```
SITE 01 — CONNECTING RIDGE
LAT 89.5142 S  LON 227.0381 E
ELEV +1944 m   (Δ +0.3 m)
POS X+12  Y+47   (m from spawn)
```

- Line 1: static site label (compiled constant in display.cc).
- Line 2: live lat/lon converted from game-world (X, Y) via south polar stereographic inverse, using the PGDA centre offset and spheroid radius documented in `wflevels/moon_site01/data/README.md`.
- Line 3: live elevation in metres above the lunar reference radius (player Z plus the +1944.77 m centre offset from `terrain_heights.json`), with Δ from spawn.
- Line 4: live game-world position in metres (useful for level-design debug; pairs with line 2 as a sanity check).

### Plumbing reuse (no new APIs)

The existing path is `actor → local mailbox X_POS/Y_POS/Z_POS (3009–3011) → Forth script copies to global mailbox → game.cc reads global → extern int wf_hud_* → display.cc:DrawHud reads extern → DrawHudText`. This is exactly how SCORE/TIMER/LIVES already flow (`game.cc:554–561`). We add four globals along the same wire.

### Files to change

1. **`wfsource/source/mailbox/mailbox.inc`** — add five entries (slots in the reserved user range, e.g. 1875–1879):
   - `MOON_PLAYER_X` (local 3009 → here per tick)
   - `MOON_PLAYER_Y` (local 3010)
   - `MOON_PLAYER_Z` (local 3011)
   - `MOON_PLAYER_HEADING` (local 3014 `ROTATION_C` → here per tick; revolutions per [[feedback_angles_in_revolutions]])
   - `MOON_OVERLAY_ENABLED` (0 on every other level, set to 1 by moon player init → display.cc only draws when this is set, so SMB/qbert stay untouched)

2. **`wflevels/moon_site01/blender_create_moon.py`** — extend the player's `wf_Script` to copy `X_POS`/`Y_POS`/`Z_POS`/`ROTATION_C` (local 3009/3010/3011/3014) into the global `MOON_PLAYER_*` slots each tick, and set `MOON_OVERLAY_ENABLED=1`. (`ROTATION_C` is the Z-axis heading per `CLAUDE.md` — angle is in revolutions on the script surface per memory [[feedback_angles_in_revolutions]], converted to radians once in display.cc.)

3. **`wfsource/source/game/game.cc`** — in the HUD mailbox-read block at `game.cc:554`, add reads for the five new slots into externs (`wf_moon_overlay_enabled`, `wf_moon_player_x_mm`, `wf_moon_player_y_mm`, `wf_moon_player_z_mm`, `wf_moon_player_heading_rev` — store as fixed-point Scalar via `.GetFixed()` so float math happens once in display.cc, not per-frame in Forth).

4. **`wfsource/source/gfx/gl/display.cc`** — extend `DrawHud()` (around line 79–257) with a conditional block: `if (wf_moon_overlay_enabled) { … }`. Inside:
   - PS-inverse math at the play-area centre (PS X₀ = −11000 m, PS Y₀ = −12000 m, R = 1 737 400 m). For a 1 km × 1 km patch around 89.5°S the local linearisation (degrees-per-metre constants computed once) is sub-arcsecond accurate and avoids per-frame `atan2`/`asin`. Compute the constants offline and bake them in as comments-with-derivation.
   - Format four `char[64]` strings with `snprintf`.
   - Four `DrawHudText` calls stacked at y = 40, 60, 80, 100 (under the SCORE row at y=8).

### Coordinate math (bake into display.cc, with derivation)

```
Game (X, Y) metres → PS (X_ps, Y_ps) metres = (-11000 + X, -12000 + Y)
PS → lat/lon (south polar stereographic, R = 1737.4 km):
  ρ      = √(X_ps² + Y_ps²)
  c      = 2 · atan(ρ / (2R))
  lat    = -(90° - c·180/π)          // south pole convention
  lon    = atan2(X_ps, -Y_ps)·180/π   // PS convention (PROJ: +proj=stere +lat_0=-90)

Local-linearisation form (sub-arcsecond over 1 km):
  d_lat_dY = -180 / (π · R)               ≈ -3.3e-5 °/m
  d_lon_dX =  180 / (π · R · sin(|lat₀|)) ≈ +3.7e-3 °/m at 89.5°S
  lat ≈ lat₀ + (Y - Y₀) · d_lat_dY
  lon ≈ lon₀ + (X - X₀) · d_lon_dX
```

I'll implement the linearised form — it's a handful of multiplies per frame, no transcendentals, and accurate well past play-area extent.

### Elevation

```
Absolute lunar elevation (m above 1737.4 km datum) = player_z + 1944.77
Δ from spawn (m)                                   = player_z - spawn_z (= player_z, since spawn is at z=5 above centre z=0)
```

### Per-frame budget (text part)

Four mailbox reads + ~20 multiplies + 4 `snprintf` + 4 `DrawHudText`. Negligible (~µs).

### Part B: minimap inset (top-right)

Small (128×128 px) top-down view of the heightfield with a dot for the astronaut, an X for the lander, and a hollow square for the spawn point. Anchored to the top-right corner with an 8-px margin (mirroring the SCORE text-left margin).

#### Asset pipeline

1. **`wflevels/moon_site01/make_terrain_texture.py`** — extend to also emit `minimap.tga` (256×256, RGB) alongside `terrain_texture.tga`. Use the same NAC composite as input; downsample with simple area averaging. Add a thin border for visibility against dark sky. Output to `wflevels/moon_site01/minimap.tga`.
2. **`wflevels/moon_site01/moon_site01-standalone.iff.txt`** — add `minimap.tga` to the asset list so it's bundled into the standalone IFF and reachable via `HALGetAssetAccessor`. (Follow the existing pattern for `terrain_texture.tga` / `Room0.tga`.)

#### Engine path (display.cc)

1. **Texture load (one-shot)** on first frame after `wf_moon_overlay_enabled` flips true:
   - `HALGetAssetAccessor()->Open("minimap.tga")` → TGA bytes
   - Decode TGA (WF already has a TGA loader in the GL backend that builds 3D mesh textures; reuse the same path or factor a minimal decoder if it's hard-locked to mesh import. Worst case: vendor stb_image.h, which is a single header and already in the project for stb_easy_font.)
   - `glGenTextures`, `glTexImage2D`, store handle in `static GLuint gMinimapTex`.
2. **Per-frame draw** inside `DrawHud()`, inside the `if (wf_moon_overlay_enabled)` block:
   - `glEnable(GL_TEXTURE_2D); glBindTexture(GL_TEXTURE_2D, gMinimapTex);`
   - Textured quad at `(xSize - 136, 8) → (xSize - 8, 136)` with UVs `(0,0)→(1,1)`.
   - `glDisable(GL_TEXTURE_2D);`
   - Map player game-world `(X, Y)` to minimap pixel: `u = (X + HALF_M) / SIDE_M`, `v = (Y + HALF_M) / SIDE_M` (flip v if the TGA is bottom-up — verify against terrain_texture.tga orientation, which is already proven correct in the mesh).
   - Player dot: 3×3 px yellow filled quad centred on `(u·128 + (xSize-136), v·128 + 8)`.
   - Compass chevron at the player dot: 7-px isoceles triangle pointing in the heading direction. Vertices in screen-space, computed as `tip = dot + 6·(cos θ, -sin θ)`, `back_l = dot + 3·(cos(θ+2.4), -sin(θ+2.4))`, `back_r = dot + 3·(cos(θ-2.4), -sin(θ-2.4))` where `θ = heading_rev · 2π` and the screen-space `-sin` accounts for the Y-down ortho. Drawn as a `GL_TRIANGLES` fill in cyan (0x00FFFF) so it's distinguishable from the yellow dot. WF `currentDir = (cos C, sin C, 0)` (per `CLAUDE.md`) so C=0 → +X (right on map), C=π/2 → +Y (up on map at the chosen UV orientation).
   - Lander X marker: 6 px yellow cross at lander UV `(30+500)/1000, (25+500)/1000` (lander world position from `blender_create_moon.py` is baked into a `const float`).
   - Spawn square: 4-pixel hollow yellow outline at `(0.5, 0.5)` (spawn is at game-world origin).
   - 1-px white border around the minimap rect for visibility.
3. **State save/restore**: bracket the GL state changes with the same `glDisable(GL_DEPTH_TEST)` / projection-matrix push that `DrawHud()` already does — no new state-management work.

#### Per-frame budget (minimap part)

One bound-texture quad + ~6 unlit primitives. ~10 GL calls. Negligible.

#### Why not reuse the live terrain mesh texture handle?

Cleaner to ship a dedicated `minimap.tga`: (a) the mesh texture is 1024² and we'd waste samples, (b) decoupling means changes to the in-game terrain texture don't bleed into the minimap aesthetic, (c) we can add the border + adjust contrast for legibility against the dark sky without affecting in-world appearance.

## Verification

1. `python3 wflevels/moon_site01/make_terrain_texture.py` produces `minimap.tga` (256×256).
2. `task build-level -- moon_site01` clean (binary build picks up new mailbox.inc entries + bundles minimap.tga).
3. `task build` (engine rebuild — display.cc + game.cc + mailbox.inc all changed).
4. `task run-moon` boots; capture screenshot via `WF_GAME_SCREENSHOT_PPM` + `-record_video`.
5. Screenshot shows:
   - Top-left: four overlay lines (site, lat/lon, elev, pos); lat ≈ "89.51 S", lon ≈ "227.04 E", elev ≈ "+1944 m", pos "X+0 Y+0" at spawn.
   - Top-right: 128×128 minimap with hillshade visible, hollow spawn square at centre, yellow lander X at upper-right of the minimap, player dot overlapping the spawn square.
6. Walk player +X via debug-bridge `joystick1_raw` injection (per memory `project_smb_coin_pickup_verify`), step a few frames, capture a second screenshot — confirm:
   - Text lat/lon/pos update live.
   - Minimap dot has moved to the right of the spawn square.
7. Boot a non-moon level (e.g. snowgoons) — confirm neither the text block nor the minimap renders (both gated on `wf_moon_overlay_enabled`).

## Implementation notes (added during execution)

Three things bit on the way through; logging them so the next person doesn't pay the same tax:

1. **`compile_stub` in `engine/build_game.sh` ignored its own depfile.** It generated `-MMD -MP` output but the staleness check was source-mtime only — so a `mailbox.inc` edit silently did NOT trigger a rebuild of `scripting_stub.cc`, and the engine carried stale `INDEXOF_*` constants. Memory `project_wf_game_build` noted this as a known trap requiring a manual `touch`. Fixed by giving `compile_stub` the same depfile-walk logic as `compile`. Header changes now propagate properly.

2. **`DrawHud` was gated on the existing HUD mailboxes only.** The moon overlay added a new gate variable (`wf_moon_overlay_enabled`); the gate at the `DrawHud(...)` call site needed it added to the OR. Without that the moon-overlay block inside DrawHud never ran.

3. **`DrawHud(wfWindowWidth, wfWindowHeight)` mis-sized the HUD viewport in capture mode.** `wfWindowWidth` defaults to 640, but `WF_GAME_SCREENSHOT_PPM` writes from an FBO at `_xSize/_ySize` (here 512×384). The minimap (top-right) was drawn at x = 640−136 = 504, mostly past the right edge of the 512-wide FBO. Switched the call site to `DrawHud(_xSize, _ySize)` so HUD coords match whatever surface is actually being captured/displayed.

## Follow-ups (out of scope for v1)

- **Cardinal-direction overlay (N/S/E/W) on minimap**: at 89.5°S the game-world axes don't align with lunar north — need to compute the rotation from PS-projection meridian convergence. Defer.
- **Lat/lon grid lines on minimap**: tiny tick marks at integer-arcminute intervals across the play area. Defer.
- **Heading-aware "X meters north" / cardinal-bearing readout** in the text block: needs the same PS-meridian-convergence work as the N arrow.

## Estimate

~3.5 h: 30 min text-HUD plumbing (mailboxes + Forth + game.cc), 20 min lat/lon math + text display.cc block, 30 min minimap texture pipeline (extend make_terrain_texture.py + IFF bundling), 60 min minimap GL draw (texture load, quad, markers + compass chevron), 30 min build + screenshot verify + walk-test + rotate-test third capture (turn player to verify chevron rotation), 20 min slack.

## Pre-implementation step (per [[feedback_plan_workflow]])

Copy this plan to `docs/plans/2026-05-31-moon-position-overlay.md` BEFORE writing any code.
