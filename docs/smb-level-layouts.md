# Super Mario Bros (NES, 1985) — Complete Level Layout Reference

**Purpose:** Faithful 3D conversion reference. All 32 main levels (Worlds 1-1 through 8-4).

**Coordinate system:**
- NES tile = 16×16 pixels. Screen = 16 tiles wide × 15 tiles tall (240px).
- Columns are 0-indexed from the left edge of the level.
- Rows: row 0 = top of play area; row 14 = bottom (ground row).
- Ground is typically rows 13–14 (2-tile-tall ground).
- "Row 10" from top means the block row that is 4 tiles above the ground, which in NES coordinates is the most common block row height.

**Tile widths** (derived from mariowiki.com NES map pixel widths ÷ 16):

| Level | Pixel W | Tiles | Screens |
|-------|---------|-------|---------|
| 1-1   | 3584    | 224   | 14.0    |
| 1-2   | 4096    | 256   | 16.0    |
| 1-3   | 2624    | 164   | 10.3    |
| 1-4   | 2560    | 160   | 10.0    |
| 2-1   | 4944    | 309   | 19.3    |
| 2-2   | 3840    | 240   | 15.0    |
| 2-3   | 3792    | 237   | 14.8    |
| 2-4   | 2560    | 160   | 10.0    |
| 3-1   | 5120    | 320   | 20.0    |
| 3-2   | 3504    | 219   | 13.7    |
| 3-3   | 2608    | 163   | 10.2    |
| 3-4   | 2560    | 160   | 10.0    |
| 4-1   | 4096    | 256   | 16.0    |
| 4-2   | 5632    | 352   | 22.0    |
| 4-3   | 2544    | 159   | 9.9     |
| 4-4   | 3072    | 192   | 12.0    |
| 5-1   | 3584    | 224   | 14.0    |
| 5-2   | 5712    | 357   | 22.3    |
| 5-3   | 2624    | 164   | 10.3    |
| 5-4   | 2560    | 160   | 10.0    |
| 6-1   | 3184    | 199   | 12.4    |
| 6-2   | 6672    | 417   | 26.1    |
| 6-3   | 2864    | 179   | 11.2    |
| 6-4   | 2560    | 160   | 10.0    |
| 7-1   | 3328    | 208   | 13.0    |
| 7-2   | 3840    | 240   | 15.0    |
| 7-3   | 3792    | 237   | 14.8    |
| 7-4   | 3584    | 224   | 14.0    |
| 8-1   | 6480    | 405   | 25.3    |
| 8-2   | 3888    | 243   | 15.2    |
| 8-3   | 3664    | 229   | 14.3    |
| 8-4   | 6272    | 392   | 24.5    |

**Sources consulted:**
- mariowiki.com individual level pages (all 32 levels)
- mariowiki.com NES map PNG images (all 32 downloaded and visually inspected)
- SMBDIS.ASM annotated NES disassembly (gist.github.com/1wErt3r/4048722)

**Image files (downloaded locally):**
`/tmp/smb_maps2/world{W-L}.png` — full-resolution NES map PNGs (4-bit colormap, 240px tall)

---

## Level-type quick reference

| World | -1 | -2 | -3 | -4 |
|-------|----|----|----|----|
| 1 | Overworld | Underground | Athletic (bridge/island) | Castle |
| 2 | Overworld | Underwater | Athletic (bridge) | Castle |
| 3 | Overworld (night) | Overworld (night) | Athletic (night island) | Castle |
| 4 | Overworld | Underground | Athletic (mushroom platforms) | Castle (maze) |
| 5 | Overworld | Mixed (overworld + underwater) | Athletic (island) | Castle |
| 6 | Overworld (night) | Overworld (night) | Athletic (night) | Castle |
| 7 | Overworld | Underwater | Athletic (bridge) | Castle (maze) |
| 8 | Overworld (night) | Overworld | Overworld | Castle (maze) |

**Repeated castle layouts:**
- 1-4 ≈ 6-4 (same structure, 6-4 adds more Fire-Bars and Podoboos)
- 2-4 ≈ 5-4 (same structure, 5-4 adds more Fire-Bars; also has the game's only long Fire-Bar)
- 3-4, 4-4, 7-4, 8-4 are maze castles (must take correct path or loop)

---

## WORLD 1

### 1-1 — Overworld (The iconic first level)
**Dimensions:** 224 tiles wide (14 screens) | Time: 400 | **No piranha plants anywhere**

**Ground:** Continuous ground rows 13-14 across most of level. Two pits near the end (the "pyramid" section).

**Left-to-right layout (approximate tile columns):**

| Col | Object | Details |
|-----|--------|---------|
| 0   | Mario spawn | On ground |
| 16  | ? Block (row 8) | Contains Super Mushroom (coin if Super) |
| 20  | Brick (row 8) | Empty |
| 21  | ? Block (row 8) | Coin |
| 22  | Brick (row 8) | Empty |
| 23  | ? Block (row 8) | Contains Super Mushroom or Fire Flower |
| 24  | Brick (row 8) | Empty |
| 28  | Pipe (height 2) | No Piranha Plant |
| 38  | Pipe (height 2) | No Piranha Plant |
| 46  | Pipe (height 3) | No Piranha Plant. Leads to underground bonus (19 coins) |
| 57  | Hidden ? Block (row 7) | Between pipe 4 and first pit — contains 1-Up Mushroom |
| 64  | Pipe (height 4) | Exit of underground bonus area (cannot enter from outside) |
| 77  | Pit (gap) | ~4 tiles wide |
| 80  | ? Block (row 8) | Contains Super Mushroom or Fire Flower |
| 91  | Brick row (row 8, ~8 wide) | Extended overhead row; leftmost brick = 10-coin block |
| 99  | Brick (row 8) | Contains Starman |
| 107 | ? Block (row 8) | Coin |
| 108 | Brick (row 6) | Empty |
| 109 | ? Block (row 6) | Contains Fire Flower (Mushroom if small) |
| 110 | Brick (row 6) | Empty |
| 118 | Pit (gap in ground) | Second pit |
| 134 | Hard-block pyramid A | 4-step pyramid, center gap |
| 148 | Hard-block pyramid B | 4-step pyramid, pit in center |
| 160 | Pipe (tall) | Exit of underground bonus (unreachable entry) |
| 198 | Staircase | 8-step ascending staircase (col 198 = 1T, col 205 = 8T) leading to flagpole |
| 210 | Flagpole | Col ~210 |
| 212 | Castle | End of level |

**Enemies (approximate columns):**
- Goomba × 1: col ~22 (first enemy in the game)
- Goomba × 2: between pipes 1-2 (cols ~32-36)
- Goomba × 2: between pipes 2-3 (cols ~42-44)
- Goomba × 1: col ~50
- Goomba × 2: near ? block col ~80
- Goomba × 4: overhead block row area (fall off edge), cols ~88-100
- Goomba × 2: near pyramid A (~col 130)
- Goomba × 2: near pyramid B (~col 145)
- Green Koopa Troopa × 1: col ~113 (between pyramids / starman area)

**Total: 16 Goombas, 1 Green Koopa Troopa**

**Secret area:** Pipe at col ~46 drops to underground room with 19 coins in a row plus a 10-coin block. Exit pipe at col ~64 (surface, unreachable normally).

**Items:** 39 coins total. 3 Mushroom/Fire Flower power-ups. 1 Starman. 1 1-Up Mushroom (hidden block).

---

### 1-2 — Underground
**Dimensions:** 256 tiles wide (16 screens) | Time: 400 | Entry via pipe from surface

**Background:** Black/teal underground tileset. Ceiling of bricks. Entry is a pipe at surface level (col 0 surface, drops underground).

**Layout summary (left to right):**

**Section 1 — Entry (cols 0-40):**
- 2 Goombas on ground after entry pipe
- Row of 5 ? Blocks at row 8: leftmost = Mushroom/Fire Flower, rest = coins
- Block tower with 1 Goomba
- Brick containing 10-coin block

**Section 2 — Mid underground (cols 40-120):**
- Multiple brick formations
- Brick containing Starman (hidden)
- 2 Green Koopa Troopas
- Area with 5+ Goombas and 1 Koopa
- Brick containing hidden power-up
- Brick containing 10-coin block
- Short gap
- Platform with hidden 1-Up Mushroom (invisible block above)

**Section 3 — Pipe corridor (cols 120-180):**
- 2 Goombas
- 3 pipes with Piranha Plants (pipes ~cols 130, 145, 160)
- Pipe 1 leads to bonus room (~27 coins + 10-coin block)

**Section 4 — Lifts / exit area (cols 180-230):**
- 2 gaps with ground platforms
- Half-pyramid with 2 Goombas
- Ascending + descending lifts (moving platforms)
- Brick platform with 1 Red Koopa Troopa + bricks
- Final brick row with hidden power-up

**WARP ZONE (secret — cols ~210 via ceiling gap):**
Accessible by riding the ascending lift through the ceiling. Sign reads "WELCOME TO WARP ZONE".
Three pipes (right to left):
- Right pipe → **World 2-1**
- Middle pipe → **World 3-1**
- Left pipe → **World 4-1**
- (Glitch: wall-clip between left pipe and left wall → **Minus World -1**)

**Section 5 — Exit (cols 230-256):**
- Overground section (exits underground)
- Pipe with Piranha Plant on surface
- Hard-block staircase to flagpole
- Flagpole at col ~248

**Enemies:** 14 Goombas, 3 Green Koopa Troopas, 1 Red Koopa Troopa, 4 Piranha Plants
**Items:** 68 coins total, 3 power-ups, 1 Starman, 1 1-Up Mushroom

---

### 1-3 — Athletic (Tree/Island platforms)
**Dimensions:** 164 tiles wide (10.3 screens) | Time: 300

**Type:** Side-scrolling platform level. Tree-top mushroom platforms of varying heights. No ground row (fall = death).

**Layout (left to right):**

| Segment | Description |
|---------|-------------|
| Start | Small ground patch at left, then first gap |
| Platform A (cols ~20-30) | Two-tree island with 1 Red Koopa Troopa on top |
| Gap | ~4 tiles |
| Platform B (cols ~35-50) | Island with 1 Red Koopa Troopa |
| Moving lifts | 2 horizontal-moving platforms (coins in row between them) |
| ? Block (row ~6) | Contains Super Mushroom or Fire Flower (col ~70) |
| Platform C (cols ~75-90) | Island with Red Koopa Paratroopa |
| Platform D (cols ~95-110) | Island with Red Koopa Paratroopa |
| Stone platform + stairs | Final approach to flagpole |
| Flagpole (col ~155) | Standard flagpole |

**Enemies:** 3 Goombas, 3 Red Koopa Troopas, 2 Red Koopa Paratroopas (airborne)
**Items:** 23 coins (open air). 1 Mushroom/Fire Flower.
**Notes:** No pipes, no underground areas.

---

### 1-4 — Castle (First castle)
**Dimensions:** 160 tiles wide (10 screens) | Time: 300

**Type:** Castle (gray brick tileset). Lava floor in sections. No outdoor section.

**Layout (left to right):**

| Section | Description |
|---------|-------------|
| Start | Stairs down to first lava pit |
| Lava pit 1 | Platform over lava with single Fire-Bar |
| ? Block over platform | Contains Mushroom/Fire Flower |
| Fire-Bar corridor | Ceiling-level Fire-Bars in a long row (cols ~40-70) |
| Fire-Bar room | Fire-Bars on both ceiling and floor |
| Hidden Block chamber | Several hidden blocks before boss |
| Boss bridge (cols ~130-155) | Horizontally-moving lift above. Fake Bowser (Goomba disguised) walks bridge. Fires fireballs. |
| Axe | Far right of bridge (col ~155). Touch = bridge collapses, fake Bowser falls in lava. |
| Toad room | Princess says "Thank you Mario! But our princess is in another castle!" |

**Enemies:** 7 Fire-Bars total. 1 Fake Bowser (Goomba in disguise).
**Items:** 6 hidden-block coins before boss. 1 Mushroom/Fire Flower.
**Shared layout with:** World 6-4 (identical structure, 6-4 adds more Fire-Bars + Podoboos)

---

## WORLD 2

### 2-1 — Overworld (Night sky, many pipes)
**Dimensions:** 309 tiles wide (19.3 screens) | Time: 400

**Background:** Night sky (black). Heavy pipe presence throughout.

**Layout (left to right):**

**Opening (cols 0-30):**
- 3 bricks at col ~12 (row 8); middle contains Mushroom/Fire Flower
- Short brick platform with Goomba
- Gap with 2 Green Koopa Troopas

**Early mid (cols 30-90):**
- 2 Goombas
- Pipe with Piranha Plant (~col 35)
- Two ? Block rows (lower-left = Mushroom/Fire Flower, rest = coins)
- Brick rows with Starman hidden in top-left brick (~col 60)
- Another Piranha Plant pipe
- ? + brick rows; one brick = hidden Vine → Coin Heaven (sky bonus)

**Mid section (cols 90-180):**
- Multiple Piranha Plant pipes (~cols 90, 105, 120, 135, 160)
- Goombas and Paratroopas between pipes
- Underground pipe leads to coin room (enters near col 150, exits ~col 175)
- ? blocks with coins
- Paratroopa gap

**Late section (cols 180-280):**
- Several Goomba groups
- Multiple Piranha Plant pipes
- Short gaps with Paratroopas over them
- 3-vertical-block tower to jump over
- Paratroopa + gap
- ? and brick blocks (coins)

**End (cols 280-309):**
- Jumping board (trampoline)
- Tall brick wall (must use trampoline or hidden block to clear)
- Flagpole (~col 300)

**Enemies:** 16 Goombas, 6 Green Koopa Troopas, 3 Green Koopa Paratroopas, 8 Piranha Plants
**Items:** 2 Mushroom/Fire Flower power-ups. 1 Starman. Hidden Vine → Coin Heaven.
**Secret areas:**
- Vine from brick → Coin Heaven sky level (moving cloud platform, coins)
- Underground bonus room (accessible via pipe ~col 150)

---

### 2-2 — Underwater
**Dimensions:** 240 tiles wide (15 screens) | Time: 300

**Type:** Underwater (blue water background, swimming mechanics). Entry via pipe at start.

**Layout features:**
- Seabed terrain with coral-like green block formations
- 3 downward-current zones (force player down; go too far = death)
- Open swimming areas with collectible coins
- Cheep-Cheeps: infinite horizontal spawns from off-screen right
- Bloopers: 6 active at once, erratic movement

**Current zones (approximate columns):** cols ~60-70, ~130-140, ~190-200

**Coins:** 28 coins scattered in open water areas.

**Enemies:** 6 Bloopers (squid), infinite Cheep-Cheeps, 1 Piranha Plant (exit pipe)

**Exit:** Pipe leads to surface then flagpole (~col 232).

---

### 2-3 — Athletic (Bridge over water)
**Dimensions:** 237 tiles wide (14.8 screens) | Time: 300

**Type:** Side-scrolling bridge level over water. Constant Cheep-Cheep spawns jumping upward from below.

**Layout:**
- Long continuous brick/hard-block bridge with notched gaps
- Bridge sections have 1-3 tile gaps at irregular intervals
- Coins floating in the air above the bridge
- Second half: small floating platforms replace the main bridge
- Single ? Block containing power-up (~col 130)
- Cheep-Cheeps stop spawning at stone steps near end
- Flagpole at ~col 230

**Bridge gap pattern:** Gaps every ~8-12 tiles, increasing in difficulty in second half.
**Floating platforms (second half):** 3-tile-wide platforms at varying heights.

**Enemies:** Red Cheep-Cheeps (infinite upward spawns from below)
**Items:** 35 coins in open air. 1 Mushroom/Fire Flower.

---

### 2-4 — Castle
**Dimensions:** 160 tiles wide (10 screens) | Time: 300

**Type:** Castle. Two distinct pathways (top/bottom) separated by lava.

**Layout:**

| Section | Description |
|---------|-------------|
| Start | Stairs down to lava pit with Podoboos jumping up |
| Center platform | Over lava; ? Block above = Mushroom/Fire Flower. Long platform spans lava. |
| Dual path corridor | Top path: fewer Fire-Bars. Bottom path: more Fire-Bars. |
| Lift section | 2 lifts moving in opposite vertical directions |
| Gap section | Several gaps with Podoboos |
| Boss arena | Fake Bowser (Green Koopa Troopa disguised) breathes fire. Gap-jumping approach. |
| Axe | Right side of bridge |

**Enemies:** 6 Fire-Bars, 2 Podoboos, 1 Fake Bowser (Koopa Troopa disguised)
**Items:** 6 open-air coins. 1 power-up.
**Shared with:** World 5-4 (5-4 has 11 Fire-Bars including the game's only long Fire-Bar)

---

## WORLD 3

### 3-1 — Overworld (Night, long level with Hammer Bros)
**Dimensions:** 320 tiles wide (20 screens) | Time: 400 — **longest overworld**

**Background:** Night sky.

**Layout (left to right):**

**Opening (cols 0-40):**
- ? Blocks with coins and power-up
- Green Koopa Paratroopas (bouncing)
- Gap with pipes (pipe 2 = underground bonus with coins)

**Bridge section (cols 40-90):**
- Long brick bridge over water/pit
- Goombas walking bridge
- Hidden block above bridge → 1-Up Mushroom
- Piranha Plant pipes at both ends

**Block rows (cols 90-130):**
- Brick + ? Block formations
- Brick containing Starman
- More Goombas, Paratroopas

**Hammer Brothers (cols 130-155):**
- 2 Hammer Brothers on 2-block-tall brick platform, jumping and throwing hammers

**Trampoline + beanstalk (cols 155-170):**
- Trampoline
- Brick block containing Vine → Coin Heaven (sky bonus area)

**Staircase section (cols 170-270):**
- Multiple ascending stone staircases
- Goombas descending from tops
- Piranha Plant pipes between staircases

**Final approach (cols 270-320):**
- Green Koopa Troopas descending stairs
- Stone pillar
- Flagpole (~col 310)

**Enemies:** 14 Goombas, 7 Green Koopa Troopas, 5 Green Koopa Paratroopas, 5 Piranha Plants, 2 Hammer Brothers
**Items:** Starman in brick. 1-Up Mushroom (hidden block over bridge). Vine to Coin Heaven.
**Secret areas:** Underground bonus (pipe 2). Coin Heaven via Vine.

---

### 3-2 — Overworld (Night, Koopa-heavy)
**Dimensions:** 219 tiles wide (13.7 screens) | Time: 300

**Background:** Night sky.

**Layout:**
- Opening: ? Block over stone pillar (power-up) + 2-brick platform (lower=coin, upper=Starman)
- Mid: Multiple ground stretches with dense Koopa Troopa placement
- Gap with enemies
- Small platform + brick block
- Long row of Koopa Troopas (distinctive)
- Pipe with Piranha Plant (one, near mid-level)
- Final enemies leading to stone stairs + flagpole (~col 210)

**Enemies:** 15 Goombas, 19 Green Koopa Troopas, 1 Green Koopa Paratroopa, 1 Piranha Plant
**Items:** 17 coins. 1 Mushroom/Fire Flower. 1 Starman.

---

### 3-3 — Athletic (Night island platforms)
**Dimensions:** 163 tiles wide (10.2 screens) | Time: 300

**Background:** Night sky.

**Type:** Island platform level. Variety of platform mechanics.

**Platform sequence (left to right):**
1. Ground section → first island
2. 2 horizontal-moving lifts (coins between them)
3. Island with Koopa Troopa
4. Flimsy Lift (sinks when stood on)
5. Balance Lift (seesaw)
6. 3 more horizontal-moving lifts
7. Final island with 2 Red Koopa Troopas
8. Flagpole (reached via scale/lift, ~col 155)

**? Block:** 1, containing power-up (roughly mid-level, ~col 80)

**Enemies:** 1 Goomba, 5 Red Koopa Troopas, 1 Red Koopa Paratroopa
**Items:** 22 coins. 1 Mushroom/Fire Flower.

---

### 3-4 — Castle
**Dimensions:** 160 tiles wide (10 screens) | Time: 300

**Type:** Castle with many Podoboos and heavy Fire-Bar placement.

**Layout:**

| Section | Description |
|---------|-------------|
| Start | Platforms over gaps with Fire-Bars at center; Podoboos between platforms |
| Three ? Blocks | Center contains Mushroom/Fire Flower |
| Fire-Bar triples | 3 sets of Fire-Bars with jumps between |
| More lava gaps + Podoboos | |
| Boss arena | Brick-Block barrier + horizontally-moving platform above. Fake Bowser. |

**Enemies:** 9 Fire-Bars, 6 Podoboos, 1 Fake Bowser (Koopa Troopa)
**Items:** 3 ? Blocks (one Mushroom/Fire Flower, two coins).
**Note:** No axe/bridge mechanic in this castle — boss area uses moving platform instead.

---

## WORLD 4

### 4-1 — Overworld (Lakitu level)
**Dimensions:** 256 tiles wide (16 screens) | Time: 400

**Defining feature:** Lakitu flies overhead at 3 fixed positions, continually throwing Spinies.

**Layout (left to right):**

**Opening (cols 0-30):**
- Pipe with Piranha Plant at col ~16
- 2 ? Blocks (row 8): lower = power-up
- Open stretch

**Mid section (cols 30-100):**
- ? Block row + coin ? blocks
- Hidden block above second-from-right ? block → 1-Up Mushroom
- Stone pillar
- 2 pipes (pipe 2 leads underground bonus area)
- Brick row with hidden power-up

**Underground bonus (accessible from second pipe):**
- Row of blocks
- Items to collect

**Late section (cols 100-200):**
- Gaps + stone pillars
- More Piranha Plant pipes (4 total in level)
- Third Lakitu spawn
- Long stretches with Spinies on ground

**End (cols 200-256):**
- Stone stairs to flagpole
- Coin block on way to flagpole
- Flagpole (~col 248)

**Enemies:** 3 Lakitu (infinite Spiny respawn), infinite Spinies (projectile), 4 Piranha Plants
**Items:** 62 coins (18 in ? blocks, 34 open air, 10 from Coin Block). 3 power-ups. 1 1-Up Mushroom.

---

### 4-2 — Underground (Major warp hub)
**Dimensions:** 352 tiles wide (22 screens) | Time: 400

**Type:** Underground. Contains two separate warp zones — the primary warp hub for skipping to late-game worlds.

**Layout (left to right):**

**Opening (cols 0-60):**
- Entry via pipe
- Large gaps with narrow platforms
- Brick structure with power-up
- 3 Goombas (coin block above leftmost)
- ? Blocks (middle-right = power-up)

**Lift + beanstalk section (cols 60-110):**
- Descending-moving lift
- Invisible blocks below lift → if hit = beanstalk revealed in left brick structure
- Beanstalk leads to WARP ZONE 1 (sky area):
  - 3 pipes leading to **Worlds 6, 7, 8** (right to left)
  - VS. Super Mario Bros: only World 6 pipe present

**Pipe corridor (cols 110-230):**
- 4 pipes with Piranha Plants
- 1 Koopa Troopa between each pipe pair
- 4 Buzzy Beetles descending stairs
- Starman hidden in a brick after pipe 2
- Pipe 3 → short coin room (many coins), exit returns to same area
- Platform with moving lift + power-up

**WARP ZONE 2 (cols ~230-250, above exit):**
- Brick staircase near exit pipe
- Jump above exit pipe area → pipe to **World 5-1**

**End section (cols 250-352):**
- Stone platforms + lifts
- Row of coins on block tops
- Stairs over final pipe
- Exit warp pipe (~col 340)
- Flagpole (~col 345) with staircase

**Enemies:** 3 Goombas, 6 Green Koopa Troopas, 4 Buzzy Beetles, 10 Piranha Plants
**Items:** 81 coins total (42 open, 5 in ? blocks, 4 hidden, 30 from coin blocks). Power-ups.

**WARP ZONE SUMMARY for 4-2:**
| Zone | Location | Destinations |
|------|----------|-------------|
| Beanstalk warp | Cols ~80 (sky) | World 6, 7, 8 |
| Exit-pipe warp | Cols ~235 (above) | World 5 |

---

### 4-3 — Athletic (Mushroom platforms)
**Dimensions:** 159 tiles wide (9.9 screens) | Time: 300

**Type:** Sky athletic level. Distinctive orange/red mushroom-cap platforms on tall brown stalks.

**Layout (left to right):**
- Multiple mushroom-platform columns at varying heights
- Scale lifts (seesaws) connecting mushroom tops
- 2 vertically-moving lifts after first scale
- Group of 3 scales before final lift
- 1 ? Block above third-tallest mushroom (power-up)
- Koopa Troopas + Paratroopas on mushroom tops
- Flagpole at ~col 152

**Enemies:** 5 Red Koopa Troopas, 1 Red Koopa Paratroopa
**Items:** 27 coins. 1 Mushroom/Fire Flower.

---

### 4-4 — Castle (First maze castle)
**Dimensions:** 192 tiles wide (12 screens) | Time: 300

**Type:** Maze castle. Wrong paths loop player back to start. Annotations in map read "TO A" and "TO B" at branch points.

**Maze structure:**

**Path A puzzle (cols ~15-60):**
- 2 paths from entry: top loops back (TO A), bottom goes forward (TO B)
- Correct: bottom path
- Piano-key pipe formation (distinctive visual)

**Path B puzzle (cols ~70-130):**
- 3 paths: bottom → fake Bowser. Top two → reset to beginning
- Correct: specific middle route

**Boss arena (cols ~150-185):**
- Fake Bowser (Blooper disguised) at bridge
- 5 Fire-Bars total (one on boss bridge — only castle in game with Fire-Bar on bridge)
- 1 Piranha Plant
- 1 Podoboo jumping from below bridge

**Enemies:** 5 Fire-Bars, 1 Piranha Plant, 1 Podoboo, 1 Fake Bowser (Blooper)
**Items:** Minimal — maze design focuses on navigation over collectibles.

---

## WORLD 5

### 5-1 — Overworld (Bullet Bill cannons + Paratroopas)
**Dimensions:** 224 tiles wide (14 screens) | Time: 400

**Layout:**
- Opening: row of Koopa Troopas + Goombas
- Pipes with Piranha Plants + gaps
- Brick structure with hidden Starman
- Hidden block between brick structures → 1-Up Mushroom
- 3 Bill Blaster (Turtle Cannon) formations firing Bullet Bills
- 4 Green Koopa Paratroopas at various points
- Underground bonus via pipe (20 coins)
- Stone stairs + floating pillar at end
- Flagpole (~col 215)

**Enemies:** 21 Goombas, 6 Green Koopa Troopas, 4 Green Koopa Paratroopas, 4 Piranha Plants, 3 Bill Blasters (infinite Bullet Bills)
**Items:** 1 Starman (hidden brick). 1 1-Up Mushroom (invisible block). 20 coins in bonus area.

---

### 5-2 — Mixed (Overworld + Underwater + indoor sections)
**Dimensions:** 357 tiles wide (22.3 screens) | Time: 400 — **very long mixed level**

**Sections:**

1. **Opening overworld:** Stairs + Bill Blaster + Koopa Paratroopa + Jumping board
2. **First indoor chamber:** 2 rows Brick Blocks (top-right = power-up); Hammer Brother on stairs
3. **Overworld gap:** Pipe with Piranha Plant
4. **Underwater section:** Bloopers, Cheep-Cheeps, sinking lifts (~cols 100-180)
5. **Return overworld:** Broken stairs, block formation
6. **Second Hammer Brother** on stairs; Hidden block → Coin Heaven (beanstalk)
7. **Exit chamber:** Buzzy Beetles; low blocks (Coin Block + power-up); platforms with enemies
8. **Finale:** Final Piranha Plant pipe, broken stairs, flagpole (~col 350)

**Enemies:** 4 Goombas, 5 Green Koopa Paratroopas, 4 Hammer Brothers, 2 Bill Blasters, 3 Piranha Plants, 3 Bloopers, 3 Buzzy Beetles + infinite Cheep-Cheeps
**Items:** 87 coins. 3 power-ups. 1 Starman (hidden brick). Vine to Coin Heaven.

---

### 5-3 — Athletic (Island platforms, Bullet Bills)
**Dimensions:** 164 tiles wide (10.3 screens) | Time: 300

**Type:** Island platform level. Similar layout to 1-3 but with Bullet Bills.

**Layout:**
- Multiple island platforms of varying heights
- 2 horizontal-moving lifts
- Bullet Bills spawn from right side (second half)
- Tall stone platform structure near end
- Flagpole at ~col 157

**Enemies:** 3 Goombas, 3 Red Koopa Troopas, 2 Red Koopa Paratroopas, infinite Bullet Bills
**Items:** 23 coins. 1 Mushroom/Fire Flower.

---

### 5-4 — Castle (Hardest of the 2-4/5-4 pair)
**Dimensions:** 160 tiles wide (10 screens) | Time: 300

**Type:** Castle. Identical structure to 2-4 but significantly more Fire-Bars. Features the game's only **long Fire-Bar**.

**Layout:**

| Section | Description |
|---------|-------------|
| Start | Stairs → lava pit with Podoboos, platforms above |
| Center platform | ? Block = Mushroom/Fire Flower. **Long Fire-Bar** here (reaches adjacent platforms) |
| Dual path | Top path (fewer Fire-Bars). Bottom path (more Fire-Bars). |
| Lift section | 2 opposite-direction lifts; Fire-Bars on both sides |
| Gap section + Podoboos | |
| Boss arena | Fake Bowser (Lakitu) + fire breath, gap approach |

**Enemies:** 11 Fire-Bars (including unique long Fire-Bar), 6 Podoboos, 1 Fake Bowser (Lakitu)
**Items:** 6 open-air coins. 1 power-up.

---

## WORLD 6

### 6-1 — Overworld (Night, Lakitu returns)
**Dimensions:** 199 tiles wide (12.4 screens) | Time: 400

**Background:** Night sky.

**Layout:**
- Opening: 2 ? Blocks (coins + power-up)
- Stone stairs sequences (multiple)
- Broken staircase section + floating platform
- Hidden blocks (one = 1-Up Mushroom between two block rows)
- 1 Pipe with Piranha Plant
- 2 Lakitu spawn positions (infinite Spiny respawn)
- Background hill terrain
- Flagpole (~col 190)

**Enemies:** 2 Lakitu (infinite Spinies), 1 Piranha Plant
**Items:** 31 coins (3 in ? blocks, up to 20 from Coin Blocks, 8 open air). 2 power-ups. 1 1-Up Mushroom.

---

### 6-2 — Overworld (Night, maximum Piranha Plants — 28!)
**Dimensions:** 417 tiles wide (26.1 screens) | Time: 400 — **widest level in the game**

**Defining feature:** 28 Piranha Plants — more than any other level.

**Sections:**
1. **Opening:** First pipe → underground coin room. Coin Block above requiring hidden block.
2. **Mid:** Long brick rows with power-ups. Buzzy Beetle groups.
3. **Optional underwater:** Bloopers, Cheep-Cheeps, descending lifts.
4. **Beanstalk:** In far-right Brick Block → Coin Heaven
5. **Starman:** Hidden in top-left brick after underwater area.
6. **Second underground:** More coins + power-up.
7. **Exit section:** Dense Piranha Plant pipes. Flagpole (~col 408).

**Enemies:** 28 Piranha Plants, 4 Goombas, 4 Buzzy Beetles, infinite Cheep-Cheeps (in underwater)
**Items:** 122 coins. 2 Mushrooms + 2 Fire Flowers (conditional). 1 Starman.

---

### 6-3 — Athletic (Night)
**Dimensions:** 179 tiles wide (11.2 screens) | Time: 300

**Background:** Night sky.

**Platform sequence:**
1. Ground stretch → first island
2. 3 islands + vertical lift access
3. Trampoline → 3 horizontal lifts (? Block above final lift = power-up)
4. Vertical lift → 2 Balance Lift sets
5. Jumping board → horizontal lift → scale → 4 Flimsy Lifts
6. Final island + Flagpole (~col 172)

**Special:** Bullet Bills spawn from right in second half.

**Enemies:** Infinite Bullet Bills (second half)
**Items:** 24 coins. 1 Mushroom/Fire Flower.

---

### 6-4 — Castle (Harder 1-4)
**Dimensions:** 160 tiles wide (10 screens) | Time: 300

**Type:** Same layout as World 1-4 with more obstacles.

**Layout:** Identical to 1-4 structure but:
- 11 Fire-Bars (vs 7 in 1-4)
- 3 Podoboos added
- Fake Bowser is a Blooper (not Goomba as in 1-4)

**Items:** 1 power-up (same ? Block position as 1-4).

---

## WORLD 7

### 7-1 — Overworld (Night, Bill Blaster + Hammer Bros)
**Dimensions:** 208 tiles wide (13 screens) | Time: 400

**Background:** Night sky with snow (Super Mario All-Stars only).

**Layout:**
- Brick block formations
- **13 Bill Blasters** — most of any level
- **4 Hammer Brothers** (in 2 separate pairs on brick platforms)
- 4 Green Koopa Paratroopas
- 5 Piranha Plants in pipes
- 1 Buzzy Beetle
- 1 Green Koopa Troopa
- 2 underground coin chambers (via pipe pairs)
- Hard-block staircases at end
- Trampoline + brick wall
- Flagpole (~col 200)

**Enemies:** 13 Bill Blasters (infinite Bullet Bills), 4 Hammer Brothers, 4 Green Koopa Paratroopas, 5 Piranha Plants, 1 Buzzy Beetle, 1 Green Koopa Troopa
**Items:** 33 coins. 2 power-ups. 1 1-Up Mushroom.

---

### 7-2 — Underwater (More Bloopers than 2-2)
**Dimensions:** 240 tiles wide (15 screens) | Time: 400

**Type:** Underwater. Similar structure to 2-2 but with 13 Bloopers (vs 6 in 2-2).

**Layout:**
- Entry via pipe
- 3 downward-current zones
- Bloopers: 13 active (14 spawn locations; 1 blocked by green blocks)
- Infinite Cheep-Cheep spawns
- 28 coins scattered
- 1 Piranha Plant in exit pipe
- Flagpole at ~col 232

**Enemies:** 13 Bloopers, infinite Cheep-Cheeps, 1 Piranha Plant
**Items:** 28 coins.

---

### 7-3 — Athletic (Bridge + Cheep-Cheeps)
**Dimensions:** 237 tiles wide (14.8 screens) | Time: 300

**Type:** Bridge-over-water level. Nearly identical layout to 2-3.

**Layout:**
- Long brick/hard-block bridges with gaps
- Small floating platforms in second half
- Coins floating above bridge
- 1 ? Block (~mid-level) = power-up
- Small ground enemies on bridge sections
- Cheep-Cheeps stop at stone stairs near end
- Flagpole at ~col 230

**Enemies:** 1 Green Koopa Troopa, 3 Red Koopa Troopas, 3 Green Koopa Paratroopas, infinite Red Cheep-Cheeps
**Items:** 35 coins. 1 Mushroom/Fire Flower.

---

### 7-4 — Castle (Maze castle with hammer-throwing Fake Bowser)
**Dimensions:** 224 tiles wide (14 screens) | Time: 300

**Type:** Maze castle. Notable: Fake Bowser **throws hammers** (Hammer Brother behavior).

**Layout:**

**Pre-maze (cols 0-25):**
- 2 Flimsy Lifts over lava
- Podoboo between them

**Puzzle 1 (cols 25-80):**
- 3 paths. Correct: bottom → middle → top
- Wrong paths return to Puzzle 1 start

**Puzzle 2 (cols 80-165):**
- Fire-Bar on top path
- Correct: top (Fire-Bar) → middle (gap jumps) → top again
- Wrong: resets to Fire-Bar section

**Boss (cols 165-215):**
- Fake Bowser (Hammer Brother disguised) throws hammers + breathes fire
- Podoboo jumping from below

**Enemies:** 1 Fire-Bar, 2 Podoboos, 1 Fake Bowser (Hammer Brother behavior)

---

## WORLD 8

### 8-1 — Overworld (Night, longest level in game)
**Dimensions:** 405 tiles wide (25.3 screens) | Time: 300 — **longest level in the game**

**Background:** Night sky.

**Layout:**
- Continuous ground with numerous obstacles
- Dense enemy placement throughout
- 12 Piranha Plant pipes distributed widely
- Large gap with narrow middle platform (requires careful jumping)
- Coin blocks + Starman hidden in bricks
- 1-Up Mushroom in invisible block
- Stone staircases
- Flagpole (~col 395)

**Enemies:** 26 Goombas, 17 Green Koopa Troopas, 3 Green Koopa Paratroopas, 4 Buzzy Beetles, 12 Piranha Plants
**Items:** 53 coins (20 in Coin Blocks, 32 open air, 1 hidden). 1 Starman. 1 1-Up Mushroom.

---

### 8-2 — Overworld (Bill Blaster gauntlet)
**Dimensions:** 243 tiles wide (15.2 screens) | Time: 300

**Layout:**
- Opening: broken flight of stone stairs; 2 Koopa Paratroopas + 1 Lakitu
- Row of ? Blocks; Jumping board; Brick block with hidden 1-Up above
- Gaps with Koopa Paratroopas (12 green total in level)
- **10 Bill Blasters** with infinite Bullet Bills throughout
- 4 Buzzy Beetles
- 2 underground areas (short coin rooms via pipes)
- 2 Goombas near end
- Stone stairs to flagpole (~col 235)

**Enemies:** 12 Green Koopa Paratroopas, 10 Bill Blasters (infinite Bullet Bills), 4 Buzzy Beetles, 2 Goombas, 1 Lakitu
**Items:** 1 1-Up Mushroom. Coin areas.

---

### 8-3 — Overworld (Hammer Brother gauntlet — 8 Hammer Bros)
**Dimensions:** 229 tiles wide (14.3 screens) | Time: 300

**Type:** Final overworld. No water, no underground. Dense Hammer Brother placement.

**Layout (left to right):**

| Segment | Enemies |
|---------|---------|
| Col ~0-30 | Bill Blaster + Koopa Paratroopa + Bill Blaster + Piranha Plant pipe |
| Col ~35-70 | **Hammer Bro pair** (2) on brick platform; power-up in 2nd block top row |
| Col ~75-90 | Small staircase + Bill Blaster + Paratroopa + stone pillars |
| Col ~95-130 | **Hammer Bro pair** (2); power-up in 2nd-left block top row + pipe |
| Col ~135-175 | **Hammer Bro row** (4 more) — row of 4 Hammer Brothers |
| Col ~175-195 | Hidden Coin Block (castle wall area) |
| Col ~195-225 | Small Hard Block platforms; Piranha Plant pipes (3 total in level) |
| Col ~225 | Flagpole |

**Enemies:** 8 Hammer Brothers, 2 Green Koopa Paratroopas, 3 Bill Blasters (infinite Bullet Bills), 3 Piranha Plants, 1 Green Koopa Troopa
**Items:** 2 Mushroom/Fire Flowers. Up to 10 coins from 1 block.

---

### 8-4 — Castle (Final castle — real Bowser, maze + pipe system)
**Dimensions:** 392 tiles wide (24.5 screens) | Time: 400 — **final level**

**Type:** Pipe-maze castle. Distinct rooms accessed via warp pipes. Underwater section mid-level. Ends with real Bowser.

**Room structure:**

**Room 1 (cols 0-80):**
- 3 warp pipes visible
- Pipe A: loops back to Room 1 start
- Pipe B: loops back to Room 1 start  
- Pipe C: correct path → Room 2 (requires crossing lava gap with lift platform)

**Room 2 (cols 80-150):**
- Entry pipe drops here
- 2 pipes visible; one returns to Room 1
- Floating pipe ahead (accessed via hidden block as stepping stone)
- Correct pipe → Room 3

**Room 3 (cols 150-220):**
- Cheep-Cheeps jump upward from below (water below)
- 5 Fire-Bars
- 3 Bloopers swimming
- One pipe returns to start; immediate pipe after lava gap → underwater section

**Underwater section (cols 220-280):**
- Recolored castle tiles (sewer aesthetic)
- Fire-Bars and Bloopers
- Leads to final room

**Final corridor (cols 280-380):**
- Hammer Brother enemy (before Bowser)
- 1 Podoboo before boss
- Boss bridge

**Boss chamber (cols 380-392):**
- **REAL BOWSER** (not a disguised enemy):
  - Throws hammers continuously
  - Breathes fire
  - Jumps
- Axe at far right of bridge: touch it = bridge collapses, Bowser falls into lava
- Alternatively, 5 fireballs defeat him (reveals the Koopa Troopa underneath)
- Princess Peach room after boss: "Thank you Mario! The princess is here!"

**Enemies:** Hammer Brother, Podoboo, 3 Bloopers, 5 Fire-Bars, infinite Cheep-Cheeps (Room 3), **Real Bowser**

---

## SECRET / BONUS AREAS

### Underground Bonus Rooms
Accessible by entering specific pipes (not all pipes lead to bonuses):

| Level | Entry pipe col (approx) | Contents |
|-------|------------------------|----------|
| 1-1 | col ~46 (pipe 3) | 19 coins in a row + 10-coin block |
| 1-2 | col ~130 (pipe 1) | ~27 coins + 10-coin block |
| 2-1 | col ~150 (near end) | Coins |
| 3-1 | col ~45 (pipe 2) | Coins |
| 4-2 | col ~170 (pipe 3) | Coins |
| 5-1 | mid-level pipe | 20 coins |
| 6-2 | opening pipe | Coins |
| 6-2 | mid-level pipe | Coins + power-up |
| 7-1 | 2 pipe pairs | Coin chambers |
| 8-2 | 2 pipes | Short coin rooms |

### Coin Heaven (Sky Bonus Areas)
Accessible via Vine (beanstalk) grown from hitting the right brick:

| Level | Vine location | Contents |
|-------|--------------|----------|
| 2-1 | Mid-level brick row | Moving cloud platform, coins |
| 3-1 | Brick near trampoline | Coins |
| 5-2 | Hidden block area | Coin Heaven |
| 6-2 | Far-right brick | Coin Heaven |

### Warp Zones

| Level | Access method | Pipes available |
|-------|--------------|-----------------|
| 1-2 | Ride lift through ceiling | World 2, 3, 4 |
| 4-2 | Beanstalk (hit hidden block under descending lift) | World 6, 7, 8 |
| 4-2 | Jump above exit pipe area | World 5 |

### Minus World (-1)
- **Access:** World 1-2 only. Stand on top of the brick wall at the Warp Zone entrance. Duck and jump toward the left wall of the warp zone, phasing through the wall. Enter leftmost pipe.
- **Destination:** World -1 (underwater level that loops infinitely — same map data as World 2-2 but the level counter is invalid).
- **Escape:** None (loops forever). In vs. mode it terminates normally.

---

## LEVEL LAYOUT REUSE TABLE

Many levels share underlying area data:

| Pair | Relationship |
|------|-------------|
| 1-3 / 5-3 | Near-identical island platform layouts |
| 2-3 / 7-3 | Near-identical bridge + Cheep-Cheep layouts |
| 1-4 / 6-4 | Same castle structure; 6-4 adds hazards |
| 2-4 / 5-4 | Same castle structure; 5-4 adds 5 Fire-Bars + long Fire-Bar |
| 2-2 / 7-2 | Same underwater map; 7-2 has 13 Bloopers vs 6 |
| 3-3 / (none) | Unique night island layout |
| 3-4 / (none) | Unique castle with no axe/bridge |
| 4-4 / 7-4 / 8-4 | All maze castles; difficulty increases |

---

## 3D CONVERSION NOTES

### Level scale
- NES tile = 16×16px = **1 WF unit = 1 metre** (per project convention)
- Play field is 15 tiles tall = 15 m; ground at y=0, top at y=15
- Level width varies from ~160 tiles (castles) to ~417 tiles (6-2)

### Enemy heights
- Goomba: 1 tile tall (1 m)
- Koopa Troopa: 1.5 tiles tall (shell height ~0.75 m)
- Piranha Plant: 2 tiles tall when fully emerged from pipe
- Bowser: 2×2 tiles (2 m × 2 m bounding box)
- Hammer Bro: 2 tiles tall

### Block/pipe dimensions
- Standard pipe: 2 tiles wide, 2–4 tiles tall (varies per level)
- ? Block / Brick: 1×1 tile
- Ground rows: 2 tiles tall (rows 13-14 in 15-row grid)
- Typical block row height: row 8 from top = 4 tiles above ground = 4 m above ground

### Camera
- NES: fixed 256×240 viewport, scrolls right only
- For 3D: side-scroller camera at Y=−20 looking toward +Y (per CLAUDE.md recipe)
- Player starts with `rotation_euler.z = π/2` (WF Euler C=π/2)

### Lava / water / void
- Castle lava: floor below bridge/platforms; instant death on contact
- Pits/gaps in overworld: tile void below = death
- Underwater: entire level is swim-physics; gravity reduced

### Flagpole scoring
- Flagpole height = 8 tiles tall
- Score bonus based on height of contact: 100/400/800/2000/5000 points
- In 3D: flagpole as a collidable object, star height = attach point

---

*Map images downloaded from mariowiki.com NES map gallery (all 32 levels, 4-bit colormap PNG, 240px tall, variable width). All column positions in this document are approximate ±2-3 tiles; use the downloaded PNG files at `/tmp/smb_maps2/world{W-L}.png` for precise pixel-level measurements.*

---

## W1-1 — WF Implementation Detail

This section records the exact positions used in `wflevels/smb_w1_1/blender_create_smb.py`.
Tile = T = 1.5 m. All Z values are WF Z (up axis). Source: SMBDIS.ASM, verified via web.

### Coordinate conventions (WF)

| Concept | Formula |
|---|---|
| 1 tile = T | 1.5 m |
| Tile column | col = X / T |
| Ground surface Z | GROUND_TOP_Z = 0 |
| Block row Z | T = 1.5 m above ground |
| Pipe height | 2 T = 3.0 m |
| Underground floor Z | CR_FLOOR_TOP = −48.0 m |

### Surface object positions

| Object | Col (X/T) | X (m) | WF Z (m) | Notes |
|---|---|---|---|---|
| Mario spawn | 3 | 4.5 | 1.5 | MARIO_SPAWN_X, MARIO_SPAWN_Z |
| Mushroom ?-block | 6 | 9.0 | 1.5 | mushroom while Small, flower while Super |
| ?-block 0 | 8 | 12.0 | 1.5 | coin |
| Fireflower ?-block | 10 | 15.0 | 1.5 | FIREFLOWER_BLOCK_X |
| Entry pipe | 11–12 | 16.5–19.5 | 0–3.0 | 2 tiles wide; ENTRY_PIPE_X=18 (center) |
| Brick 0 | 13.5 | 20.25 | 1.5 | breakable |
| ?-block 1 | 14 | 21.0 | 1.5 | coin |
| Brick 1 | 15 | 22.5 | 1.5 | breakable; above piranha pipe |
| Piranha pipe | 15–16 | 22.5–25.5 | 0–3.0 | 2 tiles wide; PIRANHA_X=24 (center) |
| Brick 2 | 16 | 24.0 | 1.5 | breakable; above piranha pipe |
| ?-block 2 | 17 | 25.5 | 1.5 | coin |
| Hidden powerup brick | 18 | 27.0 | 1.5 | mushroom/flower |
| Pit 0 | 19–20 | 28.5–31.5 | — | 2-tile gap |
| Goomba | 29 | 43.5 | 0 | GOOMBA_X |
| Koopa Troopa | 32 | 48.0 | 0 | KOOPA_X |
| Pit 1 | 34–35 | 51.0–54.0 | — | 2-tile gap |
| Star ?-block | 38 | 57.0 | 1.5 | STAR_BLOCK_X |
| Hidden 1UP brick | 40 | 60.0 | 1.5 | ONEUP_BRICK_X |
| Flagpole | 42 | 63.0 | 0–13.5 | FLAGPOLE_X |

### Underground coin room — WF positions

**Room geometry:** 16 tiles wide (X: 0–24 m), 10 tiles tall (Z: −48 to −33), floor at CR_FLOOR_TOP = −48.

```
col:  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
R9:   ·  ·  ·  ·  ·  o  o  o  o  o  ·  ·  ·  P  P  ·   ← row 3 (top): cols 5–9
R7:   ·  ·  ·  ·  o  o  o  o  o  o  o  ·  ·  P  P  ·   ← row 5 (mid): cols 4–10
R5:   ·  ·  ·  ·  o  o  o  o  o  o  o  ·  ·  P  P  ·   ← row 7 (low): cols 4–10
      =====================================P  P  ====   ← floor + exit pipe
```

| Coin | Col | Row | X (m) | Z (m) | Mailbox |
|---|---|---|---|---|---|
| 0 | 4 | 7 (low) | 6.75 | −41.25 | SMB_COIN_0 = 1811 |
| 1 | 5 | 7 | 8.25 | −41.25 | SMB_COIN_1 = 1812 |
| 2 | 6 | 7 | 9.75 | −41.25 | SMB_COIN_2 = 1813 |
| 3 | 7 | 7 | 11.25 | −41.25 | SMB_COIN_3 = 1846 |
| 4 | 8 | 7 | 12.75 | −41.25 | SMB_COIN_4 = 1847 |
| 5 | 9 | 7 | 14.25 | −41.25 | SMB_COIN_5 = 1848 |
| 6 | 10 | 7 | 15.75 | −41.25 | SMB_COIN_6 = 1849 |
| 7 | 4 | 5 (mid) | 6.75 | −38.25 | SMB_COIN_7 = 1850 |
| 8 | 5 | 5 | 8.25 | −38.25 | SMB_COIN_8 = 1851 |
| 9 | 6 | 5 | 9.75 | −38.25 | SMB_COIN_9 = 1852 |
| 10 | 7 | 5 | 11.25 | −38.25 | SMB_COIN_10 = 1853 |
| 11 | 8 | 5 | 12.75 | −38.25 | SMB_COIN_11 = 1854 |
| 12 | 9 | 5 | 14.25 | −38.25 | SMB_COIN_12 = 1855 |
| 13 | 10 | 5 | 15.75 | −38.25 | SMB_COIN_13 = 1856 |
| 14 | 5 | 3 (top) | 8.25 | −35.25 | SMB_COIN_14 = 1857 |
| 15 | 6 | 3 | 9.75 | −35.25 | SMB_COIN_15 = 1858 |
| 16 | 7 | 3 | 11.25 | −35.25 | SMB_COIN_16 = 1859 |
| 17 | 8 | 3 | 12.75 | −35.25 | SMB_COIN_17 = 1860 |
| 18 | 9 | 3 | 14.25 | −35.25 | SMB_COIN_18 = 1861 |

Z formula: `Z = CR_FLOOR_TOP + (row + 0.5) × T`

Pickup gate: `(player_z + 46)² < 9` (player is underground) + `(player_x − coin_x)² < 1.5` (X proximity).
Three coins at the same column (rows 3, 5, 7) are collected simultaneously — by design.

Source: `wflevels/smb_w1_1/blender_create_smb.py`
