# Build a faithful Super Mario Bros. World 1-3

**Date:** 2026-06-03
**Status:** Built + render-verified (Phases 0–6 done; Phase 7 partial — geometry/coins/counts
verified via stills, clean enemy-behaviour playthrough is a follow-up; Phase 8 TODO filed).
Two bugs found + fixed en route: the parked-popup visibility leak (the W1-1 "stray gold coin",
game-wide) and the load-time render-scale gap (wide shared-box statplats drew as 1-tile cubes).
**Author:** Claude (Opus 4.8)
**Verification stills:** [`tests/screenshots/smb_w13_01_spawn.png`](../../tests/screenshots/smb_w13_01_spawn.png)
(clean spawn — no stray coin), [`..._02_treetops.png`](../../tests/screenshots/smb_w13_02_treetops.png)
(wide mushroom canopies), [`..._03_flagpole.png`](../../tests/screenshots/smb_w13_03_flagpole.png)
(solid staircase). Enemy actors confirmed loaded: 3 koopa_green + 3 goomba + 2 paratroopa + 23 coins.

## Goal

Add a faithful recreation of **SMB World 1-3** — the first *Athletic* level — to the SMB
level set, following the exact conventions proven by [W1-1](../../wflevels/smb_w1_1/blender_create_smb.py)
and [W1-2](../../wflevels/smb_w1_2/blender_create_smb_w1_2.py). W1-3 is structurally the
**inverse** of W1-1/W1-2: instead of continuous ground with a few pits, it is a continuous
**bottomless pit** with green tree-top (mushroom) islands as the only footing. Fall = death.

Reference: [`docs/smb-level-layouts.md` §1-3](../smb-level-layouts.md) (164 tiles, 10.3 screens)
cross-checked against [MarioWiki: World 1-3](https://www.mariowiki.com/World_1-3_(Super_Mario_Bros.)).

## Scope decision (user call, 2026-06-03)

W1-3's signature mechanic is **rideable moving platforms** (one vertical lift + two
horizontal movers). The default **Jolt** physics cannot carry a player on a moving surface
today: `GroundHandler`'s Jolt branch ([`wfsource/source/movement/movement.cc:432-456`](../../wfsource/source/movement/movement.cc))
overrides a rider's velocity to joystick-input-only and explicitly sets
`supportingObject = NULL` (the carry machinery exists only in the legacy non-Jolt path).
W1-1 and W1-2 both dodged this with static jump-across stand-ins.

**Decision: build the full faithful level now with static stand-ins for the 3 movers**, and
**add the real moving-platform / `Path`-mobility carry engine work to TODO.md afterward**
(Phase 8). The level ships complete and traversable; the carry fix becomes a clearly-scoped
follow-up that also unblocks 1-4's boss bridge and 2-3.

## Faithful target (authoritative)

| Element | Count | Notes |
|---|---|---|
| Green Koopa Troopas | 3 | walk the tree-tops |
| Green Koopa Paratroopas | 2 | airborne, bounce in place |
| Goombas | 3 | 2 on the tallest early tree, 1 mid-level |
| Coins | 23 | all open-air (no underground) |
| `?` Block | 1 | power-up (Mushroom if Small, Fire Flower if Super) |
| Pipes / underground | 0 | none — drop the whole coin-room/pipe-warp/piranha apparatus |
| Moving platforms | 1 lift + 2 horizontal | **static stand-ins this pass** |

**Koopa colour — green, not red.** `docs/smb-level-layouts.md` §1-3 says "Red Koopa
Troopas"; the authoritative MarioWiki layout says **green** (green Koopas walk off ledges —
the defining 1-3 hazard on narrow tree-tops). We build green and **fix the repo doc** in
Phase 1. `koopa_green.iff` already exists in the shared mesh dir.

## Layout (left → right; X = col × T, T = 1.5 m)

Continuous death pit from the start strip's right edge (col ~8) to the end strip (col ~148).
Tree-tops are the only footing. Heights are canopy-top Z in tiles above ground (`GROUND_TOP_Z = 0`).

| Cols | Element | Height | Contents |
|---|---|---|---|
| -2 … 8 | **Start ground strip** | 0 | Mario spawn (col 3) |
| 12 … 18 | Tree A (big launch pad) | 2T | — |
| 22-26, 28-32 | Tree pair (step 3) | 4T | **Koopa #1** on top + **3 coins** above |
| 36-40, 44-48, 52-56 | Three trees, stepping (step 4) | 3T/5T/3T | **2 Goombas** on the tallest (44-48) |
| 60-64 | Short tree (step 5) | 2T | the lone **`?` block** at col 62, row 6 |
| 68 | **Lift stand-in** (static) | 1T→4T steps | leads up to… |
| 72-78 | Tall tree (step 6) | 6T | **4 coins** in a row above |
| 84, 92 | **2 horizontal movers** (static) | 3T | **8 coins** suspended above/between |
| 98-102 | Small/med tree (step 8) | 3T | — |
| 106-114 | Wide/tall tree (step 8) | 4T | **Koopa #2** strolling |
| ~116 | airborne (step 9) | 5T | **Paratroopa #1** |
| 118-122 | Tree (step 9) | 3T | **Goomba #3** |
| 126-130 | Short tree (step 10) | 3T | **3 coins**; **Paratroopa #2** hovering above |
| 134-138, 140-144 | Two similar trees (step 11) | 3T | **Koopa #3** on one |
| 146-150 | Stone platform before flag | 1T | hard-block |
| 150 … 164 | **End ground strip** | 0 | staircase + flagpole (col 155) + castle |

Coin tally: 3 (step 3) + 4 (step 6) + 8 (step 7) + 3 (step 10) = 18, plus **5 scattered**
on the early launch-pad/three-trees arcs = **23**. Lay out to hit exactly 23.

All island gaps ≤ 4 tiles (6 m) so they're jumpable with the established Mario tuning
(steady ~11 m/s, `Jumping Acceleration` 60) — matches W1-1/W1-2 pit widths.

## Engine constraints honoured (from memory + verification)

- **Share mesh datablocks.** `add_statplat` already shares one unit-box datablock per
  material (`shared_mesh('unit_box::'+mat.name)`, [`smb_common.py:88`](../../wflevels/smb_common.py)).
  All green canopies → one mesh; all brown stems → one mesh; all hard blocks → one mesh.
  Koopas reuse `koopa_green`, Goombas reuse `goomba`, coins reuse `coin_template`.
- **Open-air coin pickup needs no new mailboxes.** `SMB_PLAYER_X` (1800) and `SMB_PLAYER_Z`
  (1803) globals already exist (player broadcasts both each tick). Each coin is an Anchored
  spinning `enemy` disc whose own `COIN_PICKUP_SCRIPT` reads those globals, and on proximity
  latches collected + writes its own (local) Visibility Mailbox to 0. Self-contained per
  actor — no 23-mailbox block, no shared-`player_script` bloat. (A shared coin/score counter
  is optional polish.)
- **No pool/limit bumps without sign-off.** Single room, ~60-70 actors — well within the
  standalone wrapper's pools (mirror W1-2's `OBJD 200000 / PERM 500000 / ROOM 1000000`).
- **zForth gotchas:** `/` is float (cast int via `dup 3 % - 3 /`); no `and`/`or` (use `&`/`|`);
  no nested `:` defs in script bodies; angles in revolutions.

## Phases

### Phase 0 — Scaffold
- `mkdir wflevels/smb_w1_3/`; add `mesh.flags` (`MESH_DIR=../smb`, `MESH_REF_PREFIX=../smb/`).
- Start `blender_create_smb_w1_3.py` from the W1-2 script; **strip** the entire underground
  apparatus (coin room, pipe warp, piranhas, second room, `cs_coin`/`abor_coin`, warp zone,
  brick ceiling). Keep the snowgoons-import → strip → configure-infrastructure skeleton.
- Reuse `smb_common` imports verbatim; add the new `paratroopa_mesh`, `PARATROOPA_SCRIPT`,
  `COIN_PICKUP_SCRIPT`, and a `_add_treetop` helper (see below).

### Phase 1 — Terrain, room, camera
- Start ground strip (cols -2…8) + end ground strip (cols 148…164) via
  `build_textured_ground_mesh` → level-tagged `w1_3_ground_0/1`.
- **One** continuous pit-death sensor spanning cols 8…148 (Z band [-15,-1]) →
  `w1_3_pit_death_0`. Any fall costs a life via the existing `SMB_PLAYER_HURT` respawn.
- Single `room_surface` (no second room). `actboxor` `w1_3_abor_surface` re-asserts `cs_side`.
- Matte background = SMB **sky blue** `0x5C94FC` (daytime overworld, not underground);
  camera fog already sky-blue. Director/levelobj/light/camera configured as W1-2.
- **Fix `docs/smb-level-layouts.md` §1-3** Koopa colour red→green (commit with this phase).

### Phase 2 — Tree-top islands
- `_add_treetop(name, col, top_z, width_tiles)`: a green canopy `add_statplat` (the standing
  surface, material `smb_treetop_green`) + a narrow brown stem `add_statplat` below it
  (material `smb_tree_stem`, decorative). Both share their per-material datablock.
- Place every island from the layout table.

### Phase 3 — Enemies
- 3 green Koopas via the existing `_build_koopa(name, x)` (green) on the named trees.
- 3 Goombas via the shared `goomba` datablock (2 on tree 44-48, 1 on tree 118-122).
- **Paratroopas:** `paratroopa_mesh(name)` = `koopa_green` body + two white wing quads
  (shared datablock, one `paratroopa.iff`). `PARATROOPA_SCRIPT` bounces it vertically in
  place (Z oscillation between a low and high Z at a fixed rate, like `PIRANHA_SCRIPT` but
  airborne and continuous). Anchored, hurts on contact, stompable like a Koopa → shell.

### Phase 4 — Coins + `?` block
- 23 Anchored spinning `coin_template` discs at the table positions; each runs
  `COIN_PICKUP_SCRIPT` (proximity self-hide via `SMB_PLAYER_X`/`SMB_PLAYER_Z`).
- One `_make_powerup_block('w13_powerup', 62*T, 'powerup_template', 0.0, z=BLOCK_Z_6)` — the
  level's single item block. Reuses the proven mushroom/fire-flower template + script.

### Phase 5 — Movers (static stand-ins) + end sequence
- Lift stand-in: 2-3 staggered hard-block steps (col ~68) up to the tall tree (cols 72-78).
- Two horizontal movers: two static hard-block platforms (cols 84, 92) positioned so the
  gap is jumpable, with the 8 coins suspended above. Comment each clearly as a
  **static stand-in for a moving platform** (so the Phase-8 follow-up knows where to wire).
- Stone platform (col 146-150, hard block) + `_add_staircase('w13_stairs', base_col=150,
  steps=8)` + `smb_common.celebration({'FLAGPOLE_X': 155*T, 'NEXT_LEVEL_INDEX': 0})`
  (loop back to W1-1 — W1-4 doesn't exist yet).

### Phase 6 — Build pipeline + level chaining
1. `blender --background --python wflevels/smb_w1_3/blender_create_smb_w1_3.py` → `.lev`
2. `bash wftools/wf_blender/build_level_binary.sh smb_w1_3` → `.lvl`/`.iff.txt`/`.ini`/
   textures/`.iff`. Add `smb_w1_3/smb_w1_3-standalone.iff.txt` (W1-2 wrapper, `../smb_w1_3.iff`).
3. **Insert W1-3 as cd.iff level 2** (snowgoons→3, qbert→4): edit the `build-cd-iff`
   Taskfile cmd + its order comment.
4. **Re-point W1-2 → W1-3:** change W1-2's `celebration` `NEXT_LEVEL_INDEX` 0→**2**, re-export
   + rebuild W1-2. New loop: W1-1(0) → W1-2(1) → W1-3(2) → W1-1(0).
5. `task build-cd-iff`.

### Phase 7 — Verify (headless)
- Build the game (`task build`; verify binary timestamp advanced).
- Boot `smb_w1_3-standalone.iff` headless; capture stills (engine `-record_video` FBO→mp4 or
  `WF_GAME_SCREENSHOT_PPM`, per the headless-capture memory) at spawn, mid-islands, and flag.
- Optional debug-bridge walk: inject `joystick1_raw=0x2000` to drive Mario right across the
  islands; confirm tree-top landings, a pit fall → respawn, a coin vanish, a Koopa stomp.
- Add `tests/screenshots/smb_w13_*.png` checkpoints if the walk-through is scripted.

### Phase 8 — TODO follow-up (real moving platforms)
Per the user's instruction, after the level is built, add a TODO.md entry under SCRIPTING/
PHYSICS for the **rideable moving-platform / `Path`-mobility carry** engine work (the
root-cause fix W1-1/W1-2/W1-3 all deferred). Bounded scope from the investigation:
1. `JoltCharacterGetGroundVelocity()` backend accessor wrapping
   `CharacterVirtual::GetGroundVelocity()` ([`jolt_backend.cc`](../../wfsource/source/physics/jolt_backend.cc)).
2. Add ground velocity to the character's XY before `JoltCharacterSetLinVelocity` in the Jolt
   ground branch ([`movement.cc:441`](../../wfsource/source/movement/movement.cc)) — restoring
   the legacy `supportingVelocity` carry the comment at `:437` notes is absent.
3. Give movers a **KINEMATIC** Jolt body on a layer the character's `WFCharObjLayerFilter`
   accepts; drive its pose each frame from the actor's `Path`/scripted position.
4. Route a mover actor (`MOBILITY_PATH` Platform, or scripted Anchored) through body creation
   in `actor.cc` (today only StatPlat / anchored mesh-Generator / Physics characters get bodies).
Additive — no current level uses movers, so no regression risk. Then retro-fit W1-3's 3
static stand-ins (and W1-2's end lifts) to real movers.

## New artifacts
- `wflevels/smb_w1_3/` — `blender_create_smb_w1_3.py`, `mesh.flags`, standalone wrapper,
  generated `.lev`/`.lvl`/`.iff*`/`.ini`/textures.
- `wflevels/smb/paratroopa.iff` (+ level-tagged `w1_3_ground_0/1`, `w1_3_pit_death_0`,
  `w1_3_abor_surface`).
- `smb_common` additions: `paratroopa_mesh`, `PARATROOPA_SCRIPT`, `COIN_PICKUP_SCRIPT`,
  `_add_treetop`.
- Edits: `docs/smb-level-layouts.md` (Koopa colour), `Taskfile.yml` (cd.iff order),
  W1-2 script (`NEXT_LEVEL_INDEX`), `TODO.md` (Phase-8 follow-up).

## Risks / open questions
- **Jumpability of island gaps** — the one thing only runtime confirms. Keep gaps ≤ 4 tiles
  and tune in Phase 7; widen runways (wider trees) if a hop falls short.
- **Paratroopa read** — green koopa + wing quads should read clearly at the side-camera FOV;
  confirm in a Phase-7 still.
- **Coin proximity radius** — tune the `COIN_PICKUP_SCRIPT` XZ threshold (start ~0.9 m, the
  coin-room value) so a near-miss jump doesn't vacuum coins.
