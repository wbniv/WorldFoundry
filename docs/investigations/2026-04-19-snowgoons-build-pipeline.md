# Snowgoons build pipeline — Blender to running game

**Date:** 2026-04-19
**Status:** Working end-to-end. Validated 2026-04-19: `./wftools/wf_blender/build_level_binary.sh snowgoons` produces `wflevels/snowgoons.iff` (md5 `010b6b97a9019fdc14f07ad9127a9cf9`, reproducible); `wf_game -L wflevels/snowgoons-standalone.iff` boots and plays.

## Purpose

One-stop reference for every tool in the snowgoons build chain, in the order they actually run, with inputs, outputs, and what each one does. Useful when onboarding, debugging a mid-chain divergence, or deciding where a new piece of work lands.

## The chain at a glance

```
Blender (.blend + addon)
     ↓   snowgoons.lev + per-mesh .iff + .tga
iffcomp-rs (stage 1/4)    .lev → .lev.bin
     ↓
levcomp-rs (stage 2/4)    .lev.bin + OAD schemas → .lvl + asset.inc + .iff.txt + .ini
     ↓
textile-rs (stage 3/4)    .ini + .tga + mesh .iff → palN.tga + atlases + .bin bundles
     ↓
iffcomp-rs (stage 4/4)    .iff.txt + .bin payloads → snowgoons.iff   (LVAS-rooted)
     ↓
iffcomp-rs (wrap, extra)  snowgoons-standalone.iff.txt → snowgoons-standalone.iff   (L4-rooted)
     ↓
wf_game -L                snowgoons-standalone.iff → live game window
```

Seven program invocations, one authoring tool, and a running game at the end. Stages 1–4 are what `build_level_binary.sh` chains; the L4 wrap is a separate manual step used for the `-L` CLI path (bypasses `cd.iff`).

## Stage 0 — Blender (+ `wftools/wf_blender/` addon)

- **Role:** scene authoring. Blender panels expose per-object WF attribute cards (one per class — Camera, Character, Path, Snowman, etc.) and an export operator.
- **In:** `.blend` file — meshes, transforms, per-object attach-schema properties (`Mesh Name`, `Script`, `Script Controls Input`, `Model Type`, `Bungee Camera`, object-specific mailbox bindings, etc.).
- **Out** (into `wflevels/snowgoons/`):
    - `snowgoons.lev` — text-IFF level source. One `OBJ` block per scene object carrying its OAD fields, plus `{ 'STR' { 'NAME' "Script" } ... }` fields. `Script` content is zForth source with the `\\ wf` shebang.
    - Per-mesh binary IFFs: `house.iff`, `player.iff`, `quadpatch01.iff`, `tree02.iff`, `tree03.iff`. Each contains MODL + TEX + UV chunks. Filenames lowercased to match `asset.inc` conventions (`export_level.py:1026`).
    - `snowgoons-blender.lev` — a debug variant kept for diff/archaeology.

Source TGAs (`wflevels/snowgoons/*.tga`) are pre-existing source art, not Blender-generated; mixed 16-bit BGR555 and 24-bit truecolor.

Replaces the retired 3D Studio Max pipeline (`wfmaxplugins/max2lev`, `max2iff`, `max2lvl`; purged 2026-04-13 in `c5761ca`, recoverable via `git show c5761ca^:wfmaxplugins/…`).

## Stage 1 — `iffcomp-rs` (text-IFF → binary-IFF)

- **Binary:** `wftools/iffcomp-rs/target/release/iffcomp` (Rust). Byte-identical to the C++ oracle; the first iffcomp to compose top-level `+`/`-` arithmetic correctly in 20+ years (see [2026-04-19-iffcomp-offsetof-arithmetic.md](2026-04-19-iffcomp-offsetof-arithmetic.md)).
- **Invocation:** `iffcomp -binary -o=snowgoons.lev.bin snowgoons.lev`
- **In:** `snowgoons.lev` (text-IFF).
- **Out:** `snowgoons.lev.bin` — same chunk tree, but every `{ 'TAG' ... }` is now a 4-byte tag + 4-byte LE size + payload, with `ALGN` pads where directed.

## Stage 2 — `levcomp-rs` (binary-IFF → .lvl + companion files)

- **Binary:** `wftools/levcomp-rs/target/release/levcomp` (Rust). Subsumes the old C++ `iff2lvl` / `LevelCon` / `max2lvl` (same tool, three names) **and** `prep`.
- **Invocation:**
  ```
  levcomp snowgoons.lev.bin objects.lc snowgoons.lvl <oad-dir> \
    --mesh-dir . \
    --iff-txt snowgoons.iff.txt \
    --textile-ini snowgoons.ini
  ```
- **In:**
    - `snowgoons.lev.bin` — binary level source from stage 1.
    - `objects.lc` (from `wfsource/source/oas/`) — the OAS schema compile.
    - `<oad-dir>` — per-class `.oad` files (enum tables, dropdown choices).
    - `wflevels/snowgoons/*.iff` — per-mesh IFFs, for bbox extraction.
- **Out:**
    - `snowgoons.lvl` — binary LVL chunk. The engine's compiled object list: each `_ObjectOnDisk` is a 68-byte record, each `_RoomOnDisk` is 36 bytes aligned(4), covering mailbox bindings, asset IDs, positions, paths, etc. LVL content is byte-identical to oracle except 3 bytes of `_RoomOnDisk` heap-garbage pad (same `new char[]` family as the `_PathOnDisk.base.rot` Euler garbage — see [2026-04-19-path-base-rot-oracle-mystery.md](2026-04-19-path-base-rot-oracle-mystery.md)).
    - `asset.inc` — `ROOM_START / ROOM_ENTRY / ROOM_END` manifest keyed by asset ID (`3fff001`, `3000xxx`, …). Informational now that `prep` is retired; still useful for debugging.
    - `snowgoons.iff.txt` — LVAS text-IFF template that stitches everything back together. Each asset is a per-ID `ASS` chunk include, e.g. `{ 'ASS' $3fff001l [ "tree02.iff" ] }`.
    - `snowgoons.ini` — textile input listing `Room0 = …`, `Room1 = …`, `Permanents = …`.

Field-emission details (e.g. `I32` enum STR-lookup gated on `ShowAs == DROPMENU | RADIOBUTTONS` per `iff2lvl/oad.cc:1245-1276`) are documented in [../plans/2026-04-19-levcomp-common-block-two-phase.md](../plans/2026-04-19-levcomp-common-block-two-phase.md).

## Stage 3 — `textile-rs` (texture atlas + asset bundle)

- **Binary:** `wftools/textile-rs/target/release/textile` (Rust port of the 1999 C++ `textile`).
- **Invocation:**
  ```
  textile -ini=snowgoons.ini -Tlinux \
    -transparent=0,0,0 \
    -pagex=256 -pagey=256 \
    -permpagex=256 -permpagey=256 \
    -palx=256 -paly=8 \
    -alignx=w -aligny=h \
    -flipyout -powerof2size
  ```
  Flag recipe mirrors `wfsource/levels.src/unixmakelvl.pl:130-137`.
- **In:**
    - `snowgoons.ini` from stage 2.
    - `wflevels/snowgoons/*.tga` — source art. Two pixel formats handled: 16-bit BGR555 (native; copied byte-for-byte) and 24-bit truecolor (via the [`try_load_tga_bgr555` fast path](../../wftools/textile-rs/src/bitmap.rs) landed 2026-04-19 — prior to that, 24-bit art was routed through `rgba_555(r,g,b,255)` and tripped the `a > 170` translucent-sentinel at `bitmap.rs:39`, losing pixels). Note: the invisible-roof on `House.iff` was never actually fixed by the fast path and may pre-date the Rust port entirely — tracked separately, not a regression introduced by this pipeline.
    - Per-mesh `.iff` files named in the INI (for UV extraction).
- **Out:**
    - `palN.tga`, `palPerm.tga` — 256×8 palette TGAs.
    - `Room0.tga`, `Room1.tga`, `Perm.tga` — packed atlases (area-sort rectangle-packing).
    - `Room0.ruv`/`.cyc`, `Room1.ruv`/`.cyc`, `Perm.ruv`/`.cyc` — per-atlas UV remap tables + color-cycle metadata.
    - `perm.bin`, `rm0.bin`, `rm1.bin` — ASS-wrapped asset bundles (each asset ID prefixed with its 4-byte packed ID), ready for LVAS inclusion. PERM byte-identical to oracle (29,492/29,492); RM1 atlas 31/31 textures byte-identical per-texture (see [../plans/2026-04-19-textile-rs-validation.md](../plans/2026-04-19-textile-rs-validation.md)).

## Stage 4 — `iffcomp-rs` (LVAS assembly)

- **Binary:** same as stage 1.
- **Invocation:** `iffcomp -binary -o=../snowgoons.iff snowgoons.iff.txt`
- **In:**
    - `snowgoons.iff.txt` from stage 2 (the LVAS template).
    - Files referenced by `[ "filename" ]` includes: `snowgoons.lvl` (stage 2), `perm.bin` / `rm0.bin` / `rm1.bin` (stage 3), and the raw per-mesh `.iff` files (stage 0).
- **Out:** `wflevels/snowgoons.iff` — **LVAS-rooted** standalone level file. Byte layout: `LVAS { TOC { ASMP, LVL, PERM, RM0, RM1, … entries } }` followed by each chunk at its TOC offset. 163,840 bytes; md5 `010b6b97a9019fdc14f07ad9127a9cf9`. This is the cd.iff-embeddable form — it goes inside `{ 'L4' [ "snowgoons.iff" ] }` in `cd_snowgoons.iff.txt` / `cd_full.iff.txt`.

### `snowgoons.iff.txt` (the text template levcomp-rs emits)

The full template — short enough to quote. `.offsetof` / `.sizeof` are iffcomp's symbol-table operators that get resolved when stage 4 runs (see [2026-04-19-iffcomp-offsetof-arithmetic.md](2026-04-19-iffcomp-offsetof-arithmetic.md)); `[ "filename" ]` is iffcomp's include directive for raw bytes.

```
{ 'LVAS'
	{ 'TOC'
		'ASMP' .offsetof(::'LVAS'::'ASMP') .sizeof(::'LVAS'::'ASMP')
		'LVL'  .offsetof(::'LVAS'::'LVL')  .sizeof(::'LVAS'::'LVL')
		'PERM' .offsetof(::'LVAS'::'PERM') .sizeof(::'LVAS'::'PERM')
		'RM0'  .offsetof(::'LVAS'::'RM0') .sizeof(::'LVAS'::'RM0')
		'RM1'  .offsetof(::'LVAS'::'RM1') .sizeof(::'LVAS'::'RM1')
		'FAKE' .offsetof(::'LVAS'::'LVL')  .sizeof(::'LVAS'::'ASMP')
	}
	{ 'ALGN' .align(2048) }
	{ 'ASMP'
		$3fff001l { 'STR' "tree02.iff" }  // IFF PERM fff:001
		$3fff002l { 'STR' "tree03.iff" }  // IFF PERM fff:002
		$3fff003l { 'STR' "player.iff" }  // IFF PERM fff:003
		$3001001l { 'STR' "house.iff" }  // IFF RM1 001:001
		$3001002l { 'STR' "quadpatch01.iff" }  // IFF RM1 001:002
	}
	{ 'ALGN' .align(2048) }
	{ 'LVL' [ "snowgoons.lvl" ] }
	{ 'ALGN' .align(2048) }
	{ 'PERM'
		{ 'ASS' $1fffffel [ "palPerm.tga" ] }  // TGA PERM fff:ffe
		{ 'ASS' $1ffffffl [ "Perm.tga" ] }     // TGA PERM fff:fff
		{ 'ASS' $5ffffffl [ "Perm.ruv" ] }     // RUV PERM fff:fff
		{ 'ASS' $7ffffffl [ "Perm.cyc" ] }     // CYC PERM fff:fff
		{ 'ASS' $3fff001l [ "tree02.iff" ] }   // IFF PERM fff:001
		{ 'ASS' $3fff002l [ "tree03.iff" ] }   // IFF PERM fff:002
		{ 'ASS' $3fff003l [ "player.iff" ] }   // IFF PERM fff:003
	}
	{ 'ALGN' .align(2048) }
	{ 'RM0'
		{ 'ASS' $1000ffel [ "pal0.tga" ] }    // TGA RM0 000:ffe
		{ 'ASS' $1000fffl [ "Room0.tga" ] }   // TGA RM0 000:fff
		{ 'ASS' $5000fffl [ "Room0.ruv" ] }   // RUV RM0 000:fff
		{ 'ASS' $7000fffl [ "Room0.cyc" ] }   // CYC RM0 000:fff
	}
	{ 'ALGN' .align(2048) }
	{ 'RM1'
		{ 'ASS' $1001ffel [ "pal1.tga" ] }          // TGA RM1 001:ffe
		{ 'ASS' $1001fffl [ "Room1.tga" ] }         // TGA RM1 001:fff
		{ 'ASS' $5001fffl [ "Room1.ruv" ] }         // RUV RM1 001:fff
		{ 'ASS' $7001fffl [ "Room1.cyc" ] }         // CYC RM1 001:fff
		{ 'ASS' $3001001l [ "house.iff" ] }         // IFF RM1 001:001
		{ 'ASS' $3001002l [ "quadpatch01.iff" ] }   // IFF RM1 001:002
	}
	{ 'ALGN' .align(2048) }
}
```

### Packed asset ID layout

Each `$<hex>l` literal is a 32-bit `packedAssetID` (defined in [../../wfsource/source/streams/asset.hp](../../wfsource/source/streams/asset.hp) and emitted by [levcomp-rs's asset_registry.rs](../../wftools/levcomp-rs/src/asset_registry.rs)):

```
bits [31:24]  type  (8 bits)  — file-extension fourcc code
bits [23:12]  room  (12 bits) — 0xFFF = permanent; 0..N = room N
bits [11:0]   index (12 bits) — 1-based slot per (room, type);
                                0xFFE / 0xFFF reserved for palette / atlas
```

Type codes (from [../../wfsource/source/streams/assets.inc](../../wfsource/source/streams/assets.inc)):

| code | fourcc | code | fourcc |
|---|---|---|---|
| 0 | NUL | 5 | RUV |
| 1 | TGA | 6 | WAV |
| 2 | BMP | 7 | CYC |
| 3 | IFF | 8 | CHR |
| 4 | (unused) | 9 | MAP |

So `$3fff001l` decodes as **IFF PERM fff:001** — an IFF-format asset in the permanent room at slot 1. `$1ffffffl` is **TGA PERM fff:fff** — the permanent room's atlas TGA at the reserved `fff` slot. Levcomp-rs now emits this decode as a `//` comment on every ID line (iffcomp strips `//` comments, so the compiled bytes are unchanged).

`build_level_binary.sh` stops here. For the default cd.iff-based game boot, this is enough.

## Stage 5 — final assembly (pick your wrapper)

Neither branch below is in `build_level_binary.sh` yet — both are one-off invocations of `iffcomp-rs` that take `snowgoons.iff` from stage 4 and wrap it in the outer structure the engine actually wants to read. Pick based on how you're launching:

- **5a. cd.iff path** (normal boot, default): wrap in `GAME { TOC, SHEL, L4, … }` so the engine reads it via `cd.iff`'s game-TOC lookup.
- **5b. `-L` path** (direct single-level launch): wrap in bare `L4 { ALGN, RAM, ALGN, LVAS }` so `wf_game -L<path>` works.

Both wrappers inject the `RAM` memory-budget chunk (OBJD/PERM/ROOM sizes, doomstick + bungeecam flags) and the `ALGN` padding that puts `RAM` at offset SECTOR_SIZE inside its enclosing `L4` chunk. Keep the RAM values in sync between them.

### 5a. cd.iff assembly

- **Template** ([cd_snowgoons.iff.txt](../../wflevels/cd_snowgoons.iff.txt)) — minimal cd.iff with just `shell.aib` + one L4:
  ```
  { 'GAME'
      { 'TOC'
          'SHEL'  .offsetof( ::'GAME'::'SHEL' )  .sizeof( ::'GAME'::'SHEL' )
          'L4'    .offsetof( ::'GAME'::'L4' )    .sizeof( ::'GAME'::'L4' )
      }
      { 'ALGN' .align( 2048 ) }
      { 'SHEL' [ "shell.aib" ] }
      { 'ALGN' .align( 2048 ) }
      { 'L4'
          { 'ALGN' .align( 2048 ) }
          { 'RAM'
              'OBJD' 100000l
              'PERM' 300000l
              'ROOM' 300000l
              'FLAG' 1l 1l                    // doomstick, bungeecam
          }
          { 'ALGN' .align( 2048 ) }
          [ "snowgoons.iff" ]
      }
      { 'ALGN' .align( 2048 ) }
  }
  ```
  For multi-level discs, duplicate the `{ 'L4' … }` block — see [cd_full.iff.txt](../../wflevels/cd_full.iff.txt). The `SHEL` slot is the compiled zForth shell (`shell.aib`) the engine boots before dispatching to the first level.
- **Invocation:** `cd wflevels && iffcomp-rs -binary -o=cd.iff cd_snowgoons.iff.txt` (then copy to `wfsource/source/game/cd.iff`).
- **Out:** `wflevels/cd.iff` — **GAME-rooted**, 174,080 bytes. At runtime `game.cc`'s non-`-L` path reads its GAME TOC, loads SHEL, then seeks `L4._offsetInDiskFile + SECTOR_SIZE` and lands on RAM.

### 5b. L4-standalone (for `-L`)

- **Why it exists:** `wf_game`'s `-L` loader (`game.cc:151-162`) does a hard-coded `diskFile->SeekRandom(DiskFileCD::_SECTOR_SIZE)` — byte 2048 — and the next level-loading step (`level.cc:415`) asserts `tagRam == IFFTAG('R','A','M','\0')` at that offset. Inside cd.iff, each `{ 'L4' … }` chunk is laid out as **8-byte L4 header + ALGN pad to 2048 + RAM + ALGN + LVAS**, so SECTOR_SIZE lands exactly on RAM. A standalone LVAS-rooted file has ASMP at offset 2048 instead → assertion fires immediately.
- **Template** ([wflevels/snowgoons/snowgoons-standalone.iff.txt](../../wflevels/snowgoons/snowgoons-standalone.iff.txt)) — just the L4 block from the cd.iff template, hoisted to top-level:
  ```
  { 'L4'
      { 'ALGN' .align( 2048 ) }
      { 'RAM'
          'OBJD' 100000l
          'PERM' 300000l
          'ROOM' 300000l
          'FLAG' 1l 1l                    // doomstick, bungeecam
      }
      { 'ALGN' .align( 2048 ) }
      [ "../snowgoons.iff" ]
  }
  ```
- **Invocation:** `cd wflevels/snowgoons && iffcomp-rs -binary -o=../snowgoons-standalone.iff snowgoons-standalone.iff.txt`
- **Out:** `wflevels/snowgoons-standalone.iff` — **L4-rooted**, 167,936 bytes. RAM lands at offset 0x800. `-L`-compatible.

## Stage 6 — `wf_game`

- **Binary:** `engine/wf_game` (C++; built via `engine/build_game.sh`).
- **Invocation:** `cd wfsource/source/game && wf_game -L/…/wflevels/snowgoons-standalone.iff`
- **In:**
    - `snowgoons-standalone.iff` via `-L`.
    - Alongside in CWD: `shell.aib` (zForth shell bytecode), font + misc resources miniaudio and others load by relative path. (The `cd.iff` that normally lives in the same dir is unused on the `-L` path.)
- **Boot sequence** (from the actual run log):
    1. Static init + `audio: miniaudio v0.11.25 ready`.
    2. CLI parse (`main.cc:165`): `-L<path>` → `gLevelOverridePath`.
    3. Jolt physics init: `RegisterDefaultAllocator → Factory → RegisterTypes → RunSelftest → backend init → backend ready (gravity -Z)`. (Jolt is default; legacy `physics/wf/` kept but unused — see the `project_jolt_physics_functional` memory.)
    4. `game.cc:154`: opens `-L` file as `DiskFile`, `SeekRandom(SECTOR_SIZE)`, calls `RunLevel()`.
    5. `level.cc:414-419`: reads 2048 bytes from offset 2048 as `levelMemoryConfiguration`; asserts tags `RAM / OBJD / PERM / ROOM / FLAG` match, captures doomstick + bungeecam flags, allocates per-budget DMallocs.
    6. Loads PERM first, then RM0 / RM1 (textures + RUV + CYC), builds the scene objects.
    7. Main loop: X11 keyboard + XInput feed `INDEXOF_HARDWARE_JOYSTICK1_RAW` mailbox; per-object `{ Script }` STRs run under zForth; Jolt steps physics each tick; Mesa/OpenGL rasterizes.
- **Out:** live game window + log lines like `jolt: char f118 jolt_ctr=(-1.000,-0.075,0.985) feet=(-1.000,-0.075,-0.017) vel_z=0.000 GROUND` showing the player grounded on the terrain. Clean `sys_exit(0)` on quit.

## Byte-identity scorecard (2026-04-19)

| Chunk | Rebuilt vs oracle | Notes |
|---|---|---|
| PERM | **byte-identical** (29,492/29,492) | |
| RM0 | byte-identical | |
| RM1 | 31/31 textures byte-identical per-texture extraction | Atlas bytes match per-texture; whole-chunk may drift by Blender-regenerated mesh data. |
| LVL | 3 bytes diff (from 2,772 baseline, 99.9% convergence) | `_RoomOnDisk` heap-garbage pads — same `new char[]` family as Euler garbage. Accepted. |
| Whole `snowgoons.iff` | not byte-identical | Blender-regenerated `tree02.iff` / `tree03.iff` are 140 bytes smaller each → PERM whole-chunk gap of 280 bytes. Documented in [../plans/2026-04-19-blender-roundtrip-oracle-dependencies.md](../plans/2026-04-19-blender-roundtrip-oracle-dependencies.md). |

## Files the pipeline touches (for grep-ability)

**Source / authoring:**
- `wflevels/snowgoons/snowgoons.lev`, `snowgoons-blender.lev`
- `wflevels/snowgoons/*.iff` (per-mesh: `house`, `player`, `quadpatch01`, `tree02`, `tree03`)
- `wflevels/snowgoons/*.tga` (source textures)
- `wflevels/snowgoons/snowgoons-standalone.iff.txt` (L4 wrap template)
- `wfsource/source/oas/objects.lc`, `*.oad`

**Intermediate (generated each run):**
- `snowgoons.lev.bin` (stage 1)
- `snowgoons.lvl`, `asset.inc`, `snowgoons.iff.txt`, `snowgoons.ini` (stage 2)
- `palN.tga`, `Room{0,1}.tga`, `Perm.tga`, `*.ruv`, `*.cyc`, `{perm,rm0,rm1}.bin` (stage 3)

**Final:**
- `wflevels/snowgoons.iff` (stage 4 — cd.iff-embeddable, LVAS-rooted)
- `wflevels/snowgoons-standalone.iff` (stage 5 — `-L`-compatible, L4-rooted)

## Follow-ups

- Fold stage 5 into `build_level_binary.sh` so `-L`-compatible files come out of the same command.
- Have `levcomp-rs` emit the standalone wrapper alongside `.iff.txt` / `.ini` — avoids the per-level hand-authored `snowgoons-standalone.iff.txt`.
- `.lev → Blender → .lev` round-trip (loop #2) — consistency check on the Blender importer.
