# Plan: textile → Rust — validation & round-trip integration

**Date:** 2026-04-19
**Status:** **In progress — Phase 1 in flight; PERM byte-identical; RM1 atlas content 29/31 textures match oracle**

## Alternate verification technique: per-texture extracted-bitmap equivalence

When the *atlas as a whole* isn't byte-identical to the oracle (because texture placement order differs), byte-diff of the full `.tga` isn't the right test — it conflates "content correctness" with "placement stability." Cleaner: use the atlas's own RMUV records to extract each texture as a standalone image, then compare per-texture.

Recipe:

1. Parse the atlas (`Room1.tga` or equivalent) and its RMUV (`Room1.ruv`). RMUV header is 4-byte magic `rmuv` + 4-byte cb + 4-byte entry count; each entry is 48 bytes (`szTextureName[33]` + `nFrame` + `u,v,w,h` i16×4 + `palx,paly` i16×2 + `flags` u16).
2. For each RMUV entry, slice pixels `tw × th` from the atlas starting at `(u, v)`. **Important: the RMUV `v` is in buffer coordinates (top-down), and when textile was invoked with `-flipyout` the atlas file bytes are also in buffer order — `file_row = v + y`. Without `-flipyout`, the file stores rows bottom-up and `file_row = H - 1 - (v + y)`. The TGA header's `desc` byte is always 0 regardless, so origin isn't self-describing.**
3. Wrap each slice in a minimal standalone TGA header (same w/h, 16bpp, `desc=0x20` for top-down) and md5 it.
4. For each (oracle, new) pair keyed by texture name, compare md5.

Expected outcome with a working textile-rs port: **all extracted pairs match**, even when the full atlas md5 differs. Any mismatch points at per-texture processing (quantization, palette-fit, transparent-color remap, colour-cycle expansion) — not placement.

Verified in the 2026-04-19 Phase 1 pass: 29/31 Room1 textures match between oracle and textile-rs atlases. The 2 mismatches (`G_HedgeWsnowSide.tga`, `G_shakesWsnowRM.tga`) are both 48×32 (non-square) — worth checking whether they're the *only* non-32×32 source textures in Room1 and diagnosing separately.

## Phase 1 findings (2026-04-19 first pass)

Running textile-rs on snowgoons surfaced three concrete gaps. Fix/next-action noted inline.

1. **16-bit BGR555 TGA loader — FIXED.** The `image` crate doesn't support 16-bit uncompressed truecolor TGAs (the `Unknown(16)` color type), which is WF's native source art format. All 52 snowgoons source TGAs failed to load with `The decoder for Tga does not support the color type Unknown(16)`. Fix landed: `wftools/textile-rs/src/bitmap.rs::try_load_tga_bgr555` copies the pixel bytes directly into textile's internal BGR555 representation (no round-trip through RGBA8 → `rgba_555` quantization). Preserves byte-identity for source art that's already in the target format.

2. **Palette atlas size mismatch.** textile-rs default `-palx=320, -paly=8` produces a 5138-byte `palPerm.tga`. Oracle `perm.bin`'s first ASS chunk embeds a `256×8` palette TGA = 4114 bytes. Fix: set `palx = 256` in `snowgoons.ini` (or make it the default for snowgoons). Re-run Phase 1 with the corrected INI to confirm Perm.tga / Perm.ruv / Perm.cyc sizes match oracle.

3. **textile-rs doesn't produce `perm.bin` / `rmN.bin` — it emits separate files.** Current output is per-room `{Room0,Room1,Perm}.{tga,ruv,cyc}` + `pal{0,1,Perm}.tga`. levcomp-rs's `lvas_writer` references `perm.bin` / `rm0.bin` / `rm1.bin` — each an ASS-wrapped concatenation of the individual outputs *plus* per-mesh IFF file contents, with a 4-byte packed asset ID prefixing each ASS payload. Per the historical `wfsource/levels.src/iff.prp` template, asset IDs are:
    - `$1fffffe` = palPerm.tga
    - `$1ffffff` = Perm.tga
    - `$5ffffff` = Perm.ruv
    - `$7ffffff` = Perm.cyc
    - `$1fffXXX` etc. for per-mesh IFFs (X = PERM slot index — `3fff001` = tree02.iff etc. per `asset.inc`)

    Three options:
    - (a) **Add `--emit-ass-bin` to textile-rs** — post-processing pass that reads its own per-room outputs + reads the per-room mesh IFFs from `asset.inc`, wraps each in an ASS chunk with the right ID, concatenates into `perm.bin` / `rmN.bin`. Additive, doesn't touch existing texture-atlas code paths.
    - (b) **New packager tool `wftools/ass_packer/`** — dedicated Rust crate that does (a). Cleaner separation but more crate boilerplate.
    - (c) **Levcomp-rs does the packaging** — since levcomp-rs already owns the LVAS layout, it could also glue textile outputs + mesh IFFs into `.bin` files. Least new surface area, mixes concerns (levcomp-rs shouldn't know about ASS details).

    Preferred: (a). Smallest change, cleanest ownership (textile-rs owns the `.bin` contract because levcomp-rs treats `.bin` as opaque).

4. **Output naming mismatch.** textile-rs uses `Room0` / `Room1` / `Perm` in filenames (hardcoded `format!("Room{}", n)` at `main.rs:234`); levcomp-rs's `lvas_writer.rs:128-131` references `perm.bin` / `rm0.bin` / `rm1.bin` (lowercase, `rm` prefix). Either rename in textile-rs to lowercase `rm0` / `rm1` / `perm` (matches `lvas_writer`), or have the `--emit-ass-bin` option from (3a) write under the `rm*.bin` / `perm.bin` names regardless of internal room-name convention. Latter is simpler — individual `Room0.tga` etc. become intermediate build artifacts, only the `.bin` output is authoritative.

The first-pass harness INI committed at `wflevels/snowgoons/snowgoons.ini` — currently references the three PERM IFFs + two RM1 IFFs, points `[Texture] Path` at the current directory, leaves Room0 empty. Next iteration: bump `palx = 256`, add `--emit-ass-bin`, re-run and md5-diff the `.bin` files.

---

## Context

The Blender → level round-trip currently produces a standalone `LVL` chunk but splices it into the oracle `snowgoons.iff` via `swap_lvl.py`, reusing every other chunk — notably the `PERM` and `RM1` binary IFF chunks, which package textile's texture-atlas outputs (`palN.tga` + `rmN.tga` + `rmN.ruv` + `rmN.cyc`). Until textile can regenerate those from Blender-exported materials, the round-trip has a hard oracle dependency. `docs/plans/2026-04-19-blender-roundtrip-oracle-dependencies.md` lists textile as the single biggest blocker.

A Rust port **already exists** at `wftools/textile-rs/` (~1.8K LOC, 8 modules, 3 commits dated 2026-04-14, builds clean, CLI-flag-parity with the C++ tool). It was written fast and has never been validated — zero unit tests, zero `testdata/`, zero integration tests, no byte-identity claims versus either the C++ reference or the oracle `snowgoons.iff`. We don't yet know whether running it on a snowgoons-shaped input produces the oracle's bytes.

This plan takes the existing port the rest of the way: build a snowgoons validation harness, confirm byte-identity against the oracle, close any divergences, wire textile-rs into the round-trip, and retire `swap_lvl.py`'s texture-chunk dependency.

**Pipeline context — `prep` is already out.** Commit `86df893` on 2026-04-19 landed `lvas_writer` in `levcomp-rs` + a `--iff-txt=` flag that emits the LVAS text-IFF directly, subsuming the old `prep` + `iff.prp` macro-expansion step. Oracle-extracted `wflevels/snowgoons/perm.bin` / `rm0.bin` / `rm1.bin` placeholders are already committed; `levcomp-rs`'s emitted `snowgoons.iff.txt` references them via `{ 'PERM' [ "perm.bin" ] }` includes. The textile-rs integration narrows to "produce those three `.bin` files byte-identically from source TGAs."

**Decisions (from user, this session):**
1. **Success bar: byte-identical vs oracle PERM/RM1.** Same mirror-first policy as iffcomp-rs / levcomp-rs.
2. **No SGI support.** snowgoons has zero `.rgb`/`.bw` source files; restoring the 226-line C++ SGI reader is a day's work for a zero-use format. Keep the "use ImageMagick" hint.
3. **No C++ textile backport of semantic fixes.** C++ textile is oracle/reference only (per the `project_tools_language.md` memory); single active implementation going forward. Exception: if Phase 2's area-tie triage (see below) requires it, a minimal *determinism* patch (e.g., `std::sort` → `std::stable_sort` in `texture.cc:478`) is on the table — purely to re-establish a clean oracle for the Rust port to match. That's not a feature backport; it's one-time oracle-regeneration. After such a patch, the C++ binary stays frozen.

## Old-codebase reference locations

The original WF build pipeline for turning loose textures + per-level
asset manifests into a compiled `snowgoons.iff` already exists in the
tree (preserved from 1995–2003 era). This section is the complete
inventory so that Phase 4 can mirror the original flow rather than
reinvent it.

### Old C++ tools (`wftools/`)

| Path | Role |
|---|---|
| `wftools/textile/` | Atlas compositor — reads per-object IFFs, packs TGAs into `palN.tga`/`rmN.tga`, emits `rmN.ruv` + `rmN.cyc`. Main entry `main.cc` + `texture.cc` (913 LOC) + `bitmap.cc` (734 LOC) + `allocmap.cc` + `profile.cc` (INI parser) + `rmuv.cc` + `ccyc.cc` + `locfile.cc`. Sample inputs: `test.ini`, `ccycle.ini`, `58x41.tga`. |
| `wftools/prep/` | Macro preprocessor — expands `@define` / `@include` / `@if()` directives in `.prp` templates. Entry `prep.cc`, globals `global.hp`, macro engine `macro.cc`/`macro.hp`, source iterator `source.cc`. Used to turn `iff.prp` + `asset.inc` into a concrete level text-IFF. Also has `prep.doc` and `CHANGELOG`. |
| `wftools/iffcomp/` | Text-IFF → binary compiler (oracle only; see `project_iffcomp_rs_surpassed_cpp` memory). |
| `wftools/iffdump/` | Inverse of iffcomp; oracle reference for `wftools/iffdump-rs/`. |
| `wftools/iff2lvl/` | **`.lev` → `.lvl` converter.** Reads Max's exported `.lev` text-IFF files and writes the binary `.lvl` format the engine consumes. Per its `README`: originally a 1995 DOS/4G program reading 3DSR4 files, ported to a Max plugin in 1997 (internally named **`max2lvl`**, per the Windows registry path hardcoded in `levelcon.cc:138`), then ported back to a command-line tool in late 1999 — which is the form preserved here. Also the file at the centre of the 2026-04-19 `path.cc` / `Euler`-struct archaeology (see `docs/investigations/2026-04-19-path-base-rot-oracle-mystery.md`). |
| `wftools/iffwrite/` | Low-level IFF writer used by several old tools. |
| `wftools/lvldump/` | LVL chunk dumper (oracle for `lvldump-rs`). |
| `wftools/oaddump/` | OAD dumper (oracle for `oaddump-rs`). |
| `wftools/recolib/` | Utility library (`fpath.hp` path helpers used by the tools). |
| `wftools/regexp/` | Regex library vendored for the tools. |

### Old authoring-pipeline templates & scripts (`wfsource/levels.src/`)

Historical build-orchestration reference. Not on the active path anymore — commit `86df893` subsumed `prep` into `levcomp-rs`, making the `.prp` templates and Perl orchestrators one-way archaeology. Still useful for cross-referencing how the original pipeline produced the oracle bytes.

| Path | Role |
|---|---|
| `wfsource/levels.src/iff.prp` | **Primary template.** Two-pass macro layout — first pass emits `ASMP` from `asset.inc`, second pass wraps `{ 'ASS' $<id>l [ "palN.tga" ] } ...` chunks inside `{ 'PERM' ... }` / `{ 'RMn' ... }` using `ROOM_START`/`ROOM_ENTRY`/`ROOM_END` macros. Includes `ram.iff.txt`. |
| `wfsource/levels.src/asset.prp` | Asset-list template (populates ASMP). |
| `wfsource/levels.src/assetdir.prp` | Asset-directory enumeration template. |
| `wfsource/levels.src/unixassetdir.prp` | Unix variant of `assetdir.prp`. |
| `wfsource/levels.src/ini.prp` | INI template (used by textile's `-ini=` input). |
| `wfsource/levels.src/buildlvl` | **Top-level shell orchestrator** for a single level (`#!/bin/sh`). Enumerates `*.i3d` + `*.max` into `files.lst`, invokes `prep unixassetdir.prp` → produces `assetdir` script, runs it, then calls `unixmakelvl.pl`. Copyright 2001 KTS. |
| `wfsource/levels.src/unixmakelvl.pl` | Per-level Perl driver (called by `buildlvl`). |
| `wfsource/levels.src/makelvl.pl` | Windows-era Perl driver. |
| `wfsource/levels.src/makeleve.btm` | DOS `.btm` batch launcher (pre-POSIX era). |
| `wfsource/levels.src/cd.pl` | **Perl generator for the multi-level `cd.iff` text-IFF** — writes the `{ 'GAME' { 'TOC' ... } ... }` structure and per-`LN` include lines from stdin. Direct ancestor of the reconstructed `wflevels/cd_full.iff.txt` / `cd_snowgoons.iff.txt`. |
| `wfsource/levels.src/shell.tcl` / `shell.scm` | Embedded in-game shell scripts (Tcl was the original host, Scheme an alternate). Now replaced by zForth (`shell.aib`). |
| `wfsource/levels.src/template.ali` | Alias template. |
| `wfsource/levels.src/joystick.def`, `joystick.txt` | Joystick config defaults. |
| `wfsource/levels.src/user.def` | User-configurable macros. |
| `wfsource/levels.src/level.htm` | Build-log HTML template. |
| `wfsource/levels.src/readme` | **Original build docs.** |
| `wfsource/levels.src/todo.txt` | Historical TODO list. |
| `wfsource/levels.src/oad/` | Subdirectory with OAD templates. |

### Per-level manifests (`wflevels/<name>/`)

| Path | Role |
|---|---|
| `wflevels/primitives/asset.inc` | **Only committed `asset.inc` in the tree** — model for what snowgoons's would look like. `ROOM_START(Permanents,PERM) ... ROOM_ENTRY(geosphere01.iff, 3fff001) ... ROOM_END`. |
| `wflevels/snowgoons/ram.iff.txt` | Snowgoons's RAM-chunk source (`OBJD`/`PERM`/`ROOM`/`FLAG` sizes). Already referenced by `iff.prp`'s `FILE_HEADER` macro. |
| `wflevels/primitives/ram.iff.txt` | Primitives' RAM chunk. |
| `wflevels/whitestar/ram.iff.txt` | Whitestar's RAM chunk. |

### Legacy authoring plugins (`wfmaxplugins/`, deleted 2026-04-13 in commit `c5761ca` "purge")

The `wfmaxplugins/` directory was the full 3D Studio Max plugin collection — the original source-of-truth for level authoring, ancestor of the current Blender plugin at `wftools/wf_blender/`. It was removed from the tree on 2026-04-13 in commit `c5761ca`. Modern docs (plans, investigations, the Blender exporter source) still cite files from this directory — e.g., `max2lev.cc:374 process_bounding_box`, `max2lev/oadobj.cc:289-393` for light-property injection, etc. Those citations all refer to the pre-purge tree and are recoverable via `git show c5761ca^:<path>`.

Full pre-purge inventory (from `git ls-tree c5761ca^ wfmaxplugins/`):

| Path | Role |
|---|---|
| `wfmaxplugins/max2iff/` | Max → per-object `.iff` file exporter. Produces the per-mesh IFFs (tree02.iff, tree03.iff, etc.) that textile then reads. |
| `wfmaxplugins/max2lev/` | Max → `.lev` text-IFF level exporter. Cited throughout the modern codebase as `max2lev.cc:NNN` for specific field-emission behaviours — e.g., `process_bounding_box` (BOX3 gating), `oadobj.cc` light and slope-plane injection, path+channel serialization reference. |
| `wfmaxplugins/max2lvl/` | Max → `.lvl` binary exporter. The canonical tool name in the Windows registry (`iff2lvl/levelcon.cc:138`). Overlaps with `max2lev` + `iff2lvl` — likely the end-to-end form that bypassed the `.lev` intermediate. |
| `wfmaxplugins/oad2txt/` | OAD binary → text decompiler (for the Max-side authoring loop). |
| `wfmaxplugins/txt2oad/` | Text → OAD binary compiler (paired with `oad2txt`). |
| `wfmaxplugins/attrib/` | Attribute-UI system — the largest subdirectory; a generic Max widget toolkit for the per-object attribute editors (buttons, colour pickers, checkboxes, dropdowns, filename fields, mailbox references, etc.). |
| `wfmaxplugins/colour/` | Colour-picker plugin (icon: `colour.gif`). |
| `wfmaxplugins/debug/` | Debug helpers. |
| `wfmaxplugins/eval/` | Expression evaluator (for computed attributes). |
| `wfmaxplugins/handle/` | Handle-gizmo plugin (icons: `handle.gif`, `handle_cropped.gif`). |
| `wfmaxplugins/select/` | Selection plugin (icon: `select.gif`). |
| `wfmaxplugins/slope/` | Slope-plane plugin (icons: `slope.gif`, `slope_cropped.gif`). Injects the slope-plane coefficients referenced by `wf_blender/export_level.py:1079-…`. |
| `wfmaxplugins/terrain/` | Terrain-generation plugin. |
| `wfmaxplugins/toolbar/` | Custom Max toolbar (icon: `toolbar.gif`). |
| `wfmaxplugins/lib/` | Shared C++ library used by all plugins (common UI helpers, IFF reader/writer glue, string utils). |
| `wfmaxplugins/makefile`, `makefile.def`, `makefile.inc` | Plugin build rules (nmake for Max SDK). |
| `wfmaxplugins/max plugins.dsw` | Visual Studio 6 workspace file. |
| `wfmaxplugins/libs.txt` | Library dependency list. |
| `wfmaxplugins/questions.doc`, `todo.txt` | Historical notes. |
| `wfmaxplugins/*.gif` | UI icons for the plugins above. |

If Phase 2 / Phase 4 ever needs to consult exact byte-emission behaviour from the old Max pipeline (e.g., "what does max2lev do with a unit-cube helper?"), the recipe is `git show c5761ca^:wfmaxplugins/max2lev/max2lev.cc` (etc.) — the SourceForge `wf-gdk` CVS archive is also an option but the purged git history is closer at hand.

### Old runtime consumers (`wfsource/source/`)

Not part of the build pipeline, but these are the load-time targets of the
tool chain output — included for completeness because byte-identity only
matters if the runtime reads the same bytes the oracle did.

| Path | Role |
|---|---|
| `wfsource/source/asset/assets.cc`, `assets.hp` | Asset-slot runtime manager (reads ASMP). |
| `wfsource/source/asset/assslot.cc`, `.hp`, `.hpi` | Individual asset slot loader. |
| `wfsource/source/game/level.cc` | Top-level LVAS loader (reads `TOC` and dispatches to PERM/RMn loaders). |
| `wfsource/source/renderassets/rendacto.cc` | Render-asset consumer of PERM/RMn payloads. |

### External historical archive

Three progressively-older sources, in order:

1. **Current working tree** — `wftools/`, `wfsource/`, `wflevels/`. Most recent state of everything.
2. **Git history at `c5761ca^`** — the tree just before the 2026-04-13 "purge" commit. Includes the full `wfmaxplugins/` (+ `wfi3dplugins/` and possibly others). Read any file with `git show c5761ca^:<path>`.
3. **SourceForge `wf-gdk` CVS snapshot** — for anything even older than the current git history. This project was originally hosted on SourceForge and migrated to Git/GitHub; the pre-migration CVS revisions are only recoverable from the archive. Download URL:

   ```
   https://sourceforge.net/code-snapshots/cvs/w/wf/wf-gdk.zip
   ```

   The snapshot contains `Attic/` directories with `,v` RCS-format files for every file that ever existed in CVS (including deleted-before-migration ones). Already consulted in the 2026-04-19 iffcomp investigation — it's where the `iffcomp/Attic/lang.y,v` historical grammar and `wfsource/levels.src/Attic/iff.prp,v` were recovered (HEAD = revision 1.7, dated 2010, marked `state dead` at the project's CVS → Git move). See [iffcomp-offsetof-arithmetic Postscript 3](../investigations/2026-04-19-iffcomp-offsetof-arithmetic.md#postscript-3-sourceforge-cvs-resolves-the-mystery) for the recipe.

   Use when the git-history approach ((2) above) comes up empty — usually for pre-2010 code that was retired before the project moved to Git.

## Approach

Six phases. Phases 1–3 are the core work; 4–5 close the loop; 6 is stretch.

### Phase 1 — Harness + first run

**Goal:** Run textile-rs on a snowgoons-shaped input, diff its outputs against the oracle `.bin` files already committed at `wflevels/snowgoons/`, triage what doesn't match.

1. **Oracle reference bytes already on disk.** Commit `86df893` ("feat(levcomp-rs): emit snowgoons.iff.txt — subsumes prep") landed three files extracted from the oracle `snowgoons.iff`:

    - `wflevels/snowgoons/perm.bin` — 29,492 bytes, PERM chunk's `ASS`-slot payload
    - `wflevels/snowgoons/rm0.bin` — 4,336 bytes, RM0 chunk's ASS payload
    - `wflevels/snowgoons/rm1.bin` — 112,028 bytes, RM1 chunk's ASS payload

    These are the regression targets textile-rs must produce byte-identically. No `iffdump-rs` extraction step needed — the bytes are already there, and `levcomp-rs`'s new `lvas_writer` references them via `{ 'PERM' [ "perm.bin" ] }` / `{ 'RM0' [ "rm0.bin" ] }` / `{ 'RM1' [ "rm1.bin" ] }` includes.

2. **Author `wflevels/snowgoons/snowgoons.ini`** — textile input. Structure (per `wftools/textile/test.ini` + `profile.cc:60-403`):
   ```ini
   [Rooms]
   nRooms = 2
   Room0 = rm0
   Room1 = rm1
   Permanents = perm

   [Texture]
   Path = wflevels/snowgoons

   [Configuration]
   x_page = 512
   y_page = 2048
   perm_x_page = 128
   perm_y_page = 512
   pal_x_page = 320
   pal_y_page = 8
   ```
   Enumerate which snowgoons IFF objects belong to PERM / RM0 / RM1 by cross-referencing the ASMP asset-ID packing already documented in `docs/plans/2026-04-19-blender-roundtrip-oracle-dependencies.md` and inspectable in `wflevels/snowgoons/asset.inc` (emitted by levcomp-rs): `3fff00X` = PERM slots, `3000XXX` / `3001XXX` = RM0 / RM1 slots. Source IFFs already live in `wflevels/snowgoons/`.

3. **Textile-rs output shape: ASS-wrapped `.bin` files per room.** The integration contract is that textile-rs produces `perm.bin` / `rm0.bin` / `rm1.bin` directly — each a ready-to-include ASS-slot payload (ASS chunk header + concatenated palette / atlas / RUV / CYC bytes). If the current textile-rs only writes the individual `palN.tga` / `rmN.tga` / `.ruv` / `.cyc` files, add a packager step (either a new CLI flag `--emit-ass=<room>` or a post-processing pass) that emits the combined `.bin`. Format is whatever matches the oracle's existing `perm.bin` — which means the easiest validation is "produce a candidate .bin, diff against the committed one."

4. **Diff outputs.** `md5sum wflevels/snowgoons/{perm,rm0,rm1}.bin` vs textile-rs's newly-generated versions. Expected: at least one will diverge on first run.

### Phase 2 — Close byte-identity gaps

For each file that doesn't md5-match the oracle, root-cause and fix inside `wftools/textile-rs/`. Likely suspects, roughly in order of probability:

- **BGR555 quantization drift.** C++ `bitmap.cc` hand-rolls `(r<<10)|(g<<5)|b` with explicit shifting; Rust port may route through `image` crate expand-to-RGBA8 then quantize. Edge cases: translucent bit, top-bit semantics (which WF encodes as the translucent flag), rounding on 8→5 bit collapse. Check `wftools/textile-rs/src/bitmap.rs` against `wftools/textile/bitmap.cc:150-280` for the exact quantization function.
- **Palette ordering & dedup.** If two source textures share a palette entry, both the oracle and textile-rs need to produce the same slot index. Check `bitmap.rs` palette-build against `bitmap.cc` — particularly how "unused" slots get filled.
- **Allocmap packing order.** `wftools/textile-rs/src/allocmap.rs` vs `wftools/textile/allocmap.cc:50-197`. Same algorithm per the survey, but textures are fed in object-order and any difference in ordering (stable vs unstable sort, HashMap iteration in Rust) would shift every placement. If this diverges, fix is usually "use `BTreeMap` / `Vec` preserving insertion order" in Rust.

- **Area-tie ordering (load-bearing for byte-identity).** Both packers sort by `area()` descending — Rust `textile-rs/src/texture.rs:301` does `textures.sort_by(|a, b| b.area().cmp(&a.area()))`, C++ `textile/texture.cc:478` does `sort(tblTextures.begin(), tblTextures.end(), g)` with `Bitmap::operator>` comparing `_area` only (`bitmap.cc:371-378`; the "w × h × b" comment in `bitmap.hp:76` is misleading — only `_area` = w×h is actually compared). Two concrete risks:

    1. **Rust's `sort_by` is stable; C++'s `std::sort` is not.** For textures with equal area, the two implementations produce different orderings even given identical inputs. Rust preserves insertion order; C++ can reorder arbitrarily per the libstdc++ std::sort implementation at oracle-build time. Whatever specific ordering `std::sort` happened to produce when the oracle was built is baked into the oracle atlas; reproducing it requires either replicating that sort quirk or matching inputs closely enough that no area-ties arise.

    2. **Insertion order into the textures list.** Before the sort, textures enter the vector via IFF-MODL-chunk scan order. That's deterministic per input IFF set, but inherits from whatever order the scan visits files — `readdir`-equivalent filesystem enumeration for unexpanded globs, explicit INI-declared order for the `Room0 = ...` / `Permanents = ...` sections. Different filesystems can produce different enumeration orders for the same physical set of files.

  If Phase 1's diff shows atlas contents that are "right textures, wrong positions" (same pixel data present, just at different XY coordinates), this is the most likely cause. Diagnostic order: (a) check whether any two oracle textures have equal area — if no ties exist, this is not the cause. (b) If ties exist, inspect oracle atlas placement to infer the specific ordering the oracle's `std::sort` produced.

  Three escape hatches, in order of preference:

    1. **Encode explicit order in the INI.** If the ordering can be inferred by working backwards from the oracle atlas, just list textures in that exact order in `snowgoons.ini`'s `Room0 = …` / `Permanents = …` sections. Both packers see identical input order; stable-vs-unstable sort becomes irrelevant because no ties fall through to the sort's tiebreaker.

    2. **Add a deterministic tiebreaker to textile-rs and accept oracle non-determinism.** Change `texture.rs:301` to `b.area().cmp(&a.area()).then(a.name.cmp(&b.name))`, run textile-rs, pin its output as the *new* deterministic regression oracle. Document the drift from the historical oracle and move on. Lose strict historical byte-identity; gain a reproducible test.

    3. **Patch the C++ oracle tool to be deterministic, regenerate oracles.** Change C++ `textile/texture.cc:478` from `std::sort` to `std::stable_sort` (or add the same `.then(name)` tiebreaker via the `greater_p` comparator), re-run C++ textile on snowgoons, pin the *newly-generated* oracle atlases as regression references. Both textile (C++) and textile-rs (Rust) now produce identical bytes for ties. This is a carve-out from the "no C++ backport" rule (Decision 3, Context section) — the rule was about not backporting semantic fixes; a minimal determinism patch to re-establish a clean oracle is a different category. After this one patch, the C++ binary stays frozen as oracle.

  Prefer (1) where feasible — it's the smallest change and preserves historical byte-identity. Fall to (2) if the oracle's ordering is genuinely unrecoverable. Reach for (3) if (1) is infeasible and we want C++ and Rust to match each other rather than locking in Rust's output unilaterally.

  `wftools/textile-rs/testdata/snowgoons/snowgoons.ini` should encode the exact texture order the oracle used (option 1), verifiable by examining texture positions in the oracle `rm1.tga` and working backwards.
- **RMUV / CYC record layout.** The survey claims `rmuv.rs` and `ccyc.rs` match the C++ byte layout. Byte-diff will confirm or refute.
- **TGA header fields.** Image crate writes TGA headers differently than hand-rolled. Minor header deltas (origin, interleave) are easy to fix; check `bitmap.rs::save_tga` vs `bitmap.cc::save_tga`.

Fix each divergence with the smallest change that restores byte-identity. Don't refactor; don't "clean up" the C++ quirks. Commit after each file md5-matches.

### Phase 3 — Document unsupported flags, move on

No support work planned for any of the C++ textile stubs. `-colourcycle=`
file parsing, `-mipmap`, `-source_control`, and SGI (`.rgb`/`.bw`) input
support are all explicitly out of scope (see Out of scope section). If
Phase 1's diff turns up a `.cyc` divergence that traces to
`-colourcycle=` not being wired, accept the diff — the oracle's `.cyc`
bytes came from some pipeline we're not recreating. Only action in this
phase: document the unsupported flags in `wftools/textile-rs/README.md`
so future readers aren't surprised.

### Phase 4 — Wire into Blender round-trip

**Orchestration is already shaped.** Commit `86df893` (2026-04-19) landed
a `lvas_writer` module + `--iff-txt` flag in `levcomp-rs` that **subsumes
prep entirely.** `levcomp-rs` now emits the LVAS text-IFF directly,
referencing sibling `perm.bin` / `rmN.bin` via `{ 'PERM' [ "perm.bin" ] }`
includes — no `prep` invocation, no `iff.prp` macro expansion. Current
pipeline:

```
Blender export  → per-mesh .iff files + snowgoons.lev
levcomp-rs      → snowgoons.lvl + asset.inc + snowgoons.iff.txt (LVAS text-IFF)
textile-rs      → perm.bin + rm0.bin + rm1.bin   ← THE gap this plan fills
iffcomp-rs      → snowgoons.iff (byte-identical against oracle)
```

The textile-rs role is narrow and clean: produce the three `.bin` files
that `levcomp-rs`'s emitted `.iff.txt` already references. Currently
those files exist in `wflevels/snowgoons/` as oracle-extracted
placeholders (same commit `86df893`); when textile-rs can produce them
byte-identically from source TGAs, the Blender round-trip drops its
last oracle dependency.

| Stage | Rust tool | Status |
|---|---|---|
| `.lev` → `.lvl` + `asset.inc` + `.iff.txt` | `levcomp-rs` | **Done** (`86df893`); `lvas_writer.rs` emits the full LVAS text-IFF |
| source TGAs → `perm.bin` / `rmN.bin` | `textile-rs` | **This plan — gap to close** |
| `.iff.txt` + `.bin` payloads → `.iff` | `iffcomp-rs` | **Done** (byte-identical against oracle per 2026-04-19 investigation) |

Concretely for Phase 4:

- **No orchestrator shell script needed** — the Blender exporter can
  invoke each CLI in sequence. `wftools/wf_blender/export_level.py`
  already calls `levcomp-rs`; extend the same pathway to run textile-rs
  immediately before, producing the `.bin` files that `levcomp-rs`
  then references in the `.iff.txt`. Final `iffcomp-rs` invocation
  closes the chain.
- **`asset.inc`** — emitted by `levcomp-rs` (`main.rs:219-231`
  + `asset_registry.rs:94+`, same `FILE_HEADER`/`ROOM_START`/`ROOM_ENTRY`
  shape LevelCon used at `iff2lvl/level2.cc:354-401`). In the new
  pipeline it's informational only (nothing downstream consumes it
  since `prep` is out), but keep emitting it — useful for debugging
  and for any human authoring a level without Blender.
- **Retire `swap_lvl.py`** once textile-rs produces the three `.bin`
  files byte-identically. Script stays in-tree as documentation of
  what the oracle-dependency era looked like.

The `cd.iff` assembly (`cd_full.iff.txt` / `cd_snowgoons.iff.txt`) is
already covered — those text-IFF sources wrap each level's LVAS file in
`{ 'L4' [ "snowgoons.iff" ] }`. For a new level, duplicate the
`{ 'L4' ... }` block per the comment at `wflevels/cd_snowgoons.iff.txt:21-27`.

### Phase 5 — Pin as regression test

- **`wftools/textile-rs/testdata/snowgoons/`** — commit the `snowgoons.ini`, copies of the 5 source IFF meshes + their texture TGAs, and the 8 oracle-extracted reference outputs. Size check: each TGA is 2-8 KB, IFFs similar, total fixture footprint < 500 KB. Acceptable per the "don't vendor giant bootstrap binaries" memory (cap ~40 MB; this is far under).
- **`wftools/textile-rs/tests/oracle.rs`** — integration test. `#[test] fn snowgoons_byte_identical()` runs the CLI on `testdata/snowgoons/snowgoons.ini`, compares each of the 8 output files against `testdata/snowgoons/expected/`, fails with a diff summary on mismatch.
- **Three unit tests** (`src/bitmap.rs`, `src/allocmap.rs`, `src/rmuv.rs`): known RGB → known BGR555, known packing input → known placements, known texture metadata → known 48-byte RMUV record. These pin the primitives so future refactors don't silently regress.

### Phase 6 — Stretch: other levels

If snowgoons passes, the five other level roots (`L0` cube, `L1` basic, `L2` cyber, `L3` primitives, `L5` main_game, `L6` whitestar) may have source TGAs somewhere and can be run through the same validation. Not gating on this — snowgoons is the golden path. Track as follow-up.

## Critical files

**Read-only references:**
- `wftools/textile/` (all `.cc`/`.hp`) — oracle C++ tool
- `wflevels/snowgoons.iff` + `wflevels/snowgoons.iff.txt` — oracle binary + reconstructed text source
- `wflevels/snowgoons/*.tga`, `*.iff` — source art (42 TGAs, 5 object IFFs, per the survey)
- `docs/plans/2026-04-19-blender-roundtrip-oracle-dependencies.md` — the plan that calls out textile as a blocker

**To be modified:**
- `wftools/textile-rs/src/bitmap.rs` — most likely site of Phase 2 fixes (BGR555 quantization, palette dedup)
- `wftools/textile-rs/src/allocmap.rs` — possible packing-order divergence fix
- `wftools/textile-rs/src/rmuv.rs`, `src/ccyc.rs` — minor record-layout fixes if any
- `wftools/iffdump-rs/` — add `--extract-to=<dir>` if not already there (Phase 1)

**To be created:**
- `wflevels/snowgoons/snowgoons.ini` (~20 lines, textile input)
- `wftools/textile-rs/testdata/snowgoons/` (INI + inputs + oracle `.bin` reference files)
- `wftools/textile-rs/tests/oracle.rs` (integration test)
- `wftools/textile-rs/README.md` (note on SGI, `-mipmap`, `-colourcycle` stubs)

Phase 4 orchestration doesn't need a new shell script — the existing `wftools/wf_blender/export_level.py` can invoke textile-rs before levcomp-rs.

## Verification

**Unit and integration:**
- `cargo test -p textile-rs` passes, including new integration test and three unit tests.
- `cd wftools/textile-rs && cargo run --release -- -ini=../../wflevels/snowgoons/snowgoons.ini -outdir=/tmp/textile-out` produces 8 files whose md5sums match the oracle-extracted references bit-for-bit.

**End-to-end, on snowgoons:**
- Re-run the Blender → level round-trip *without* `swap_lvl.py`. The resulting `snowgoons-blender.iff` builds via `textile-rs → iffcomp-rs → levcomp-rs` and boots in `wf_game` with textures rendering correctly (no purple-checker / missing-texture fallbacks).
- 60-second soak: snowman walks its path, bounce-camera tracks, player input works, no assertion failures. Same bar as the existing Blender round-trip "plays continuously" criterion.
- `md5sum snowgoons-blender.iff` vs the current oracle-swapped `snowgoons-blender.iff` — these won't be byte-identical overall (LVL will differ, as already documented in the oracle-deps plan), but the PERM + RM1 chunks extracted from each should byte-match.

**Regression guard:**
- The `tests/oracle.rs` integration test is the canonical regression guard. Any future change to `textile-rs/src/` that breaks byte-identity fails CI.

## Out of scope

- SGI (`.rgb` / `.bw`) source texture support. Document only.
- Mipmap generation (`-mipmap` flag) — C++ 1999 TODO, out of scope per the "limit scope to bug fixes, don't chase abstractions" principle.
- Color-cycle parsing from `-colourcycle=<file>` — unless Phase 3 discovers snowgoons's oracle `.cyc` files *require* it. If they don't, document and defer.
- C++ textile grammar/quantization backport — C++ textile is oracle only.
- Other levels (L0/L1/L2/L3/L5/L6). Phase 6 stretch, follow-up plan if pursued.
