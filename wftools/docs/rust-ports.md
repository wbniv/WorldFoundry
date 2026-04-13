# Plan: Rust ports of wftools command-line tools

## Which tools, and why

| Tool | C++ LOC | Verdict | Rationale |
|------|---------|---------|-----------|
| **oas2oad** | ~400 (wpp+wlink chain) | **Done** | `prep` → `g++` → `objcopy .data`; same guarantee as original toolchain — 41/41 .oas files pass |
| **iffdump** | ~372 | **Done** | Natural companion to iffcomp-rs; IFF binary format already understood; all deps are trivial stubs |
| **oaddump** | ~546 | **Done** | Self-contained OAD parser; small; no external deps |
| eval | ~53 (CLI) + ~400 (grammar) | Blender work | Expression evaluator grammar needed by `wf_attr_validate`; belongs with Blender integration, not here |
| prep | ~1 615 | Maybe later | Custom tokenizer + macro expander; interesting but larger scope |
| **textile** | ~4 000+ | **Done** | Texture atlas packer; INI-driven room pipeline; TGA/BMP/SGI readers; 2D bin-packing algorithm |
| chargrab | ~1 000+ | Maybe later | Image processing companion to textile |
| iff2lvl | ~8 731 | No | Massive 3D level converter; hardcoded paths; PSX/Saturn targets |
| attribedit | ~3 517 | Blender plugin | GTK+ 2.x standalone OAD property editor — the reference implementation for what the Blender plugin needs to do |
| iffdb | ~536 | Superseded | Alternative iffdump using in-memory IFF tree; `iffdump-rs` renders it redundant |
| **lvldump** | ~1 600 | **Done** | Reads compiled `.lvl` game-level binaries; dump objects/paths/channels/rooms + OAD fields |

---

## Completed: `oas2oad-rs`

Linux replacement for the Windows-only `wpp + wlink + exe2bin` chain.
Uses `g++` + `objcopy` — the compiler handles struct layout, preserving
the same guarantee as the original pipeline.

### Prerequisites delivered

- **`wftools/prep/macro.cc`** — one-line 64-bit portability fix: `unsigned delimiterIndex` → `std::string::size_type delimiterIndex` (truncation of `string::npos` caused named-parameter branch to fire for all tokens)
- **`wftools/prep/build.sh`** — captures working `g++ -std=c++14` command including `regexp/` sources

### Fixups applied to prep output before g++ compilation

- Strip Watcom `huge` keyword
- Replace `pigtool.h`/`oad.h` with a portable header using `int32_t` (not `long`)
- `__attribute__((aligned(1)))` on `tempstruct` to suppress inter-variable padding
- `-Dname_KIND=0`, `-DDEFAULT_VISIBILITY=1`, `BITMAP_FILESPEC`/`MAP_FILESPEC` for missing context-dependent prep macros

### Sample invocation and output

```
$ oas2oad --prep=prep --types=wfsource/source/oas/types3ds.s \
    -o /tmp/missile.oad wfsource/source/oas/missile.oas
$ ls -l /tmp/missile.oad
-rw-rw-r-- 1 will will 196892 Apr 13 13:26 /tmp/missile.oad
```

(No output on success; exit 1 with message on error.)

### Smoke test results — 41/41 pass

| File | Size (bytes) | Entries |
|------|-------------|---------|
| **actbox** | 222,239 | 148 |
| **actboxor** | 207,329 | 138 |
| activate | 10,517 | 7 |
| actor | 190,928 | 128 |
| **alias** | 4,553 | 3 |
| **camera** | 204,347 | 136 |
| **camshot** | 235,658 | 157 |
| common | 20,954 | 14 |
| **destroyer** | 205,838 | 137 |
| **dir** | 192,419 | 129 |
| **director** | 192,419 | 129 |
| **disabled** | 1,571 | 1 |
| **enemy** | 192,419 | 129 |
| **explode** | 195,401 | 131 |
| **file** | 192,419 | 129 |
| **font** | 193,910 | 130 |
| **generator** | 211,802 | 141 |
| **handle** | 23,936 | 16 |
| **init** | 193,910 | 130 |
| **levelobj** | 402,650 | 269 |
| **light** | 204,347 | 136 |
| **matte** | 192,419 | 129 |
| mesh | 77,612 | 52 |
| meter | 210,311 | 140 |
| **missile** | 196,892 | 132 |
| movebloc | 61,211 | 41 |
| **movie** | 220,748 | 147 |
| **platform** | 192,419 | 129 |
| **player** | 192,419 | 129 |
| **pole** | 199,874 | 134 |
| **room** | 32,882 | 22 |
| shadow | 192,419 | 129 |
| **shadowp** | 6,044 | 4 |
| **shield** | 199,874 | 134 |
| **spike** | 205,838 | 137 |
| **statplat** | 192,419 | 129 |
| **target** | 190,928 | 128 |
| **template** | 192,419 | 129 |
| **tool** | 213,293 | 142 |
| toolset | 12,008 | 8 |
| **warp** | 205,838 | 137 |

Entry count = `(bytes − 80) ÷ 1491` (80-byte `_oadHeader` + 1491 bytes per `_typeDescriptor`).
All 41 `.oas` files are standalone types. Shared property blocks live in `.inc` files:

`activate.inc` `actor.inc` `common.inc` `mesh.inc` `meter.inc` `movebloc.inc` `shadow.inc` `toolset.inc` `xdata.inc`

---

## Completed: `iffdump-rs`

### What it does

Reads a binary IFF file and prints its chunk structure in human-readable text,
either as a pretty hex+ASCII dump (`-f+`, default) or as iffcomp-compatible
source (`-f-`). The output of `iffdump -f-` is valid input to iffcomp — the
two tools are inverses.

### IFF reading format

Same 8-byte header as iffcomp writes, just read instead of written:

```
[4 bytes] Chunk ID  — big-endian FOURCC (e.g. 'TEST')
[4 bytes] Payload size — little-endian u32 (bytes after this field)
[N bytes] Payload
[0–3 bytes] Padding to 4-byte alignment (zeros, not part of payload size)
```

Chunks are nested: a "wrapper" chunk's payload is itself a sequence of chunks.
A whitelist (`chunks.txt`, default list hard-coded) says which FOURCCs are wrappers.

### CLI interface

```
iffdump [-c<chunks_file>] [-d+|-d-] [-f+|-f-] [-w=<width>] <infile> [outfile]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `-c<file>` | built-in list | Wrapper chunk whitelist file |
| `-d+` / `-d-` | `+` | Enable/disable hex dump of leaf chunks |
| `-f+` / `-f-` | `+` | Pretty HDump vs. iffcomp `$XX` format |
| `-w=<N>` | 16 | Chars per line in hex dump |

Exit codes: `0` success, `1` usage/I/O error.

### Default wrapper chunk list

`OADL TYPE LVAS L0 L1 L2 L3 PERM RM0 RM1 RM2 RM3 RM4 UDM IFFC`

Any FOURCC not in this list is treated as a leaf and its bytes are hex-dumped.

### Sample output — pretty mode (`-f+`, default)

```
$ iffdump testdata/expected.iff
//=============================================================================
// <stdout> Created by iffdump v0.1.0
//=============================================================================
{ 'TEST'  	// Size = 283
	0000: 00000300 CC4C0000 66660000 00800000    .....L..ff......
	0010: 48656C6C 6F207374 72696E67 48656C6C    Hello stringHell
	0020: 6F207374 72696E67 00000102 03040005    o string........
	0030: 00AA40F9 03333020 73657020 32303032    ..@..30 sep 2002
	0040: 0D0A2D2D 2D2D2D2D 2D2D2D2D 2D2D2D2D    ..--------------
	...
	0110: 206E756D 62657273 290D0A                numbers)..
}
```

### Sample output — IFFComp source mode (`-f-`)

```
$ iffdump -f- testdata/expected.iff
//=============================================================================
// <stdout> Created by iffdump v0.1.0
//=============================================================================
{ 'TEST'  	// Size = 283
	$00 $00 $03 $00
	$CC $4C $00 $00
	$66 $66 $00 $00
	$00 $80 $00 $00
	$48 $65 $6C $6C
	...
}
```

### Directory layout

```
iffdump-rs/
  Cargo.toml
  src/
    main.rs      — CLI arg parsing, open files, call lib
    lib.rs       — dump() public entry; re-exports
    reader.rs    — dump_chunks(), read_chunk_header(), id_name(), parse_chunk_list()
    dump.rs      — format_hdump(), format_iffcomp()
    error.rs     — IffDumpError enum (Io, Parse)
  testdata/      — symlink → ../iffcomp-go/testdata/
  tests/
    round_trip.rs  — iffdump -f- | iffcomp -binary should reproduce the original
```

### Critical reference files

| File | Purpose |
|------|---------|
| `wftools/iffdump/iffdump.cc` | Original C++ source; CLI flags, output format, wrapper whitelist |
| `wfsource/source/iff/iffread.cc` | IFF chunk iterator — shows exact byte layout and alignment padding |
| `wfsource/source/recolib/hdump.cc` | Hex+ASCII formatter — port as `wf_hdump` crate |
| `wftools/iffcomp-rs/src/writer.rs` | Already has `id_name()` and IFF constants — reuse directly |

### Testing

```bash
# Round-trip: iffdump -f- output should recompile to identical bytes
./iffdump -f- testdata/expected.iff > /tmp/round.iff.txt
./iffcomp -binary -o /tmp/round.iff /tmp/round.iff.txt
diff /tmp/round.iff testdata/expected.iff   # zero diff (modulo timestamp mask)

# all_features fixture
./iffdump -f- testdata/all_features.iff > /tmp/af_rt.iff.txt
./iffcomp -binary -o /tmp/af_rt.iff /tmp/af_rt.iff.txt
diff /tmp/af_rt.iff testdata/all_features.iff
```

`cargo test` result:

```
running 2 tests
test round_trip_expected ... ok
test round_trip_all_features ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

---

## Completed: `oaddump-rs`

OAD (Object Attribute Data) files describe game object properties.
Implemented as two crates: `wf_oad` (library) + `oaddump-rs` (CLI).

### `.oad` file generation pathway

`.oad` files are **not** stored in the repo — they are build artifacts.
The original Windows pipeline (`wfsource/source/oas/objects.mak`):

```
prep -DTYPEFILE_OAS=<name> types3ds.s <name>.pp   # generates C source
wpp  <name>.pp                                      # Watcom C++ → <name>.obj
wlink system dos file <name>.obj                    # Watcom linker → DOS .exe
exe2bin <name>.exe <name>.tmp                       # strip MZ header → raw binary
copy <name>.tmp $(OAD_DIR)/<name>.oad
```

The `.oad` binary is literally the initialized-data section of a tiny Watcom
DOS program, stripped of its MZ executable header. The layout is exactly the
packed C structs from `wfsource/source/oas/oad.h` with `#pragma pack(1)`:

| Section | Size | Description |
|---------|------|-------------|
| `_oadHeader` | 80 bytes | magic `OAD ` (LE u32 = 0x4F414420), chunkSize, name[68], version |
| `_typeDescriptor` × N | 1491 bytes each | one entry per OAD field |

`oas2oad-rs` (see above) provides the Linux replacement using `prep` → `g++` → `objcopy`.

### Sample output — `disabled.oad` (1 entry, simplest case)

```
$ oas2oad --prep=prep --types=.../types3ds.s -o /tmp/disabled.oad disabled.oas
$ oaddump /tmp/disabled.oad
Disabled

   Type: LEVELCONFLAG_NOINSTANCES <9>
   Name: LEVELCONFLAG_NOINSTANCES (length = 24)
Display: 
    Min: 0	0
    Max: 0	0
Default: 0
  String:
 ShowAs: 6
```

### Sample output — `alias.oad` (3 entries)

```
$ oaddump /tmp/alias.oad
Alias

   Type: BUTTON_PROPERTY_SHEET <8>
   Name: Alias (length = 5)
Display: Alias
    Min: 0	0
    Max: 1	0.0000152587890625
Default: 1
  String:
 ShowAs: 0

   Type: BUTTON_OBJECT_REFERENCE <6>
   Name: Base Object (length = 11)
Display: Base Object
    Min: 0	0
    Max: 0	0
Default: 0
  String:
 ShowAs: 0

   Type: LEVELCONFLAG_SHORTCUT <28>
   Name: LEVELCONFLAG_SHORTCUT (length = 21)
Display: 
    Min: 0	0
    Max: 0	0
Default: 0
  String:
 ShowAs: 6
```

### Sample output — `missile.oad` (132 entries, first few)

```
$ oaddump /tmp/missile.oad | head -30
Missile

   Type: LEVELCONFLAG_COMMONBLOCK <17>
   Name: movebloc (length = 8)
Display: 
    Min: 0	0
    Max: 0	0
Default: 0
  String:
 ShowAs: 6

   Type: BUTTON_PROPERTY_SHEET <8>
   Name: Movement (length = 8)
Display: Movement
    Min: 0	0
    Max: 1	0.0000152587890625
Default: 0
  String:
 ShowAs: 0

   Type: BUTTON_INT32 <4>
   Name: MovementClass (length = 13)
Display: Movement Class
    Min: 0	0
    Max: 100	0.00152587890625
Default: 0
  String:
 ShowAs: 1
```

### `cargo test` result

```
$ cargo test --manifest-path wf_oad/Cargo.toml
running 3 tests
test tests::round_trip_empty ... ok
test tests::bad_magic_rejected ... ok
test tests::round_trip_one_entry ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

### Reference files

| File | Purpose |
|------|---------|
| `wfsource/source/oas/oad.h` | Binary format: `_oadHeader`, `_typeDescriptor`, button type constants |
| `wfsource/source/oas/types3ds.s` | `prep` template that generates the C source compiled into `.oad` |
| `wfsource/source/oas/objects.mas` | Master Makefile template showing the full `prep`→`wpp`→`exe2bin` pipeline |
| `wftools/oaddump/oad.{cc,hp}` | Original C++ parser and display logic |

---

## Tool: `oas2oad-rs` — Linux OAS → OAD compiler

Replaces the Windows-only `wpp + wlink + exe2bin` chain with a Rust binary
that runs on Linux.

### Design note

The key property of the `.oas` → `prep` pipeline is that a single source
file produces two things in lockstep: the `.oad` binary and the C struct
declarations (`.ht` files) used by the game engine to interpret that binary.
They are guaranteed to agree because they come from the same `prep` run.

The Linux pipeline mirrors the original: compile `prep`'s C output with
`g++` and extract the `.data` section with `objcopy`. The binary layout is
therefore determined by the same compiler and the same struct definitions —
not reimplemented independently.

The fixups needed to compile `prep`'s Watcom-targeted output with `g++`:
- Strip the `huge` keyword (Watcom memory model, meaningless on Linux)
- Replace `pigtool.h` / `oad.h` with a portable equivalent using `int32_t`
  instead of `long` (which is 8 bytes on 64-bit Linux)
- Add `__attribute__((aligned(1)))` to `tempstruct` to suppress inter-variable
  alignment padding that would corrupt the `.data` layout
- Define `name_KIND=0` (`EActorKind` enum value from ungenerated `objects.h`)
- Define `DEFAULT_VISIBILITY=1` (prep default from `movebloc.inc`, absent in
  `mesh.oas` which doesn't pull in that include chain)
- Define `BITMAP_FILESPEC` / `MAP_FILESPEC` (prep string macros from
  `xdata.inc`, absent when `xdata.inc` isn't in the include chain)

### Pipeline

```
oas2oad <name>.oas
  → prep -DTYPEFILE_OAS=<name> types3ds.s   (macro expansion)
  → strip 'huge', replace headers, fix alignment attr
  → g++ -c -x c++                           (compile to object file)
  → objcopy --only-section=.data -O binary  (extract raw .data → .oad)
```

`prep` must be on `$PATH` or specified via `--prep=<path>`.
`types3ds.s` defaults to `$WF_DIR/wfsource/source/oas/types3ds.s`
or `--types=<path>`. `g++` can be overridden with `--gpp=<path>`.

### CLI

```
oas2oad [--prep=<path>] [--types=<path>] [--gpp=<path>] [-o <outfile>] <infile.oas>
```

Exit codes: `0` success, `1` error.

### Directory layout

```
oas2oad-rs/
  Cargo.toml
  src/
    main.rs   — CLI, fixups, orchestrates prep → g++ → objcopy
```

### Prerequisites delivered

- **`wftools/prep/macro.cc`** — one-line 64-bit portability fix: `unsigned delimiterIndex` → `std::string::size_type delimiterIndex` (truncation of `string::npos` on 64-bit caused named-parameter branch to fire for all tokens)
- **`wftools/prep/build.sh`** — captures working `g++ -std=c++14` command including `regexp/` sources

---

## Completed: `textile-rs`

Texture atlas packer. Reads an INI file describing rooms and their 3D object
files, parses IFF object binaries to find texture references, loads TGA/BMP/SGI
images, packs them into composite atlases, and writes RMUV UV-mapping data.

### What it does

1. Reads a room `.ini` file (Windows INI format) for room→object-list mappings
2. Parses IFF binary objects (`MODL`/`CROW` chunks) to collect texture filenames
3. Loads texture images (TGA 16/24-bit, BMP, SGI) and normalizes to 16-bit 5:5:5
4. Sorts textures by area (largest first), then runs 2D bin-packing into atlas pages
5. Writes output per room: composite `.tga` atlas, palette `.tga`, RMUV `.ruv`, colour-cycle `.cyc`, HTML log

### Design decisions

- **No inheritance** — the C++ `Bitmap` subclass hierarchy (TargaBitmap, WindowsBitmap, SgiBitmap) becomes a single `Bitmap` struct; format-specific header state is a `BitmapFormat` enum used only during load/save
- **No global mutable state** — replace all globals from `main.cc` and `texture.cc` with a `Config` struct passed by reference
- **No external crates** — pure `std` + internal `wf_iff` for IFF chunk parsing
- **INI parsing** — custom minimal parser (Windows-style `[Section]` / `key=value`); no external crate
- **Error handling** — `enum Error { Io(io::Error), Format(String), NotFound(String) }`; fatal errors call `process::exit(1)` to match C++ behavior
- **HTML log** — `&mut dyn Write` threaded through call stack instead of global `ofstream*`

### CLI (matches C++ textile exactly)

```
textile -ini=<file> [-pagex=N] [-pagey=N] [-permpagex=N] [-permpagey=N]
        [-palx=N] [-paly=N] [-alignx=(N|w)] [-aligny=(N|h)]
        [-transparent=r,g,b] [-outdir=dir] [-o=file]
        [-Tpsx|-Twin|-Tlinux] [-powerof2size] [-mipmap]
        [-verbose] [-frame] [-showalign] [-showpacking] [-nocrop]
        [-translucent] [-flipyout] [-debug] [-sourcecontrol]
        [-colourcycle=file]
```

### Output files (per room)

| File | Description |
|------|-------------|
| `Room0.tga` | 16-bit 5:5:5 composite texture atlas |
| `pal0.tga` | Palette atlas (for ≤8-bit textures) |
| `Room0.ruv` | RMUV binary: `rmuv` tag + size + count + `_RMUV[]` entries |
| `Room0.cyc` | Colour cycle binary: `ccyc` tag + size + count + `CCYC[]` entries |
| `textile.log.htm` | HTML diagnostic log with packing table |

### `_RMUV` binary layout

```
#[repr(C, packed)]
struct RmuvEntry {
    texture_name: [u8; 33],  // 32-char name + null
    n_frame:      i8,
    u, v:         i16,       // position in atlas
    w, h:         i16,       // texture dimensions
    palx, paly:   i16,       // palette coordinates
    flags:        u16,       // [15:11]=bitdepth [10]=translucent [9:0]=padding
}
// assert!(size_of::<RmuvEntry>() % 4 == 0)
```

### Directory layout

```
textile-rs/
  Cargo.toml
  src/
    main.rs       — CLI arg parsing, HTML log open/close, main loop
    config.rs     — Config struct (all global vars from main.cc/texture.cc)
    profile.rs    — INI file parser (get_int, get_string)
    locfile.rs    — locate_file(): search semicolon-delimited path list
    bitmap.rs     — Bitmap struct; TGA/BMP/SGI readers; save_tga(); packing helpers
    allocmap.rs   — AllocationMap + AllocationRestrictions (2D bin-packing)
    rmuv.rs       — RmuvEntry; write_rmuv()
    ccyc.rs       — ColourCycle, CcycEntry, write_ccyc()
    texture.rs    — process_room(), lookup_textures(), load_textures(),
                    texture_fit(), palette_fit(), write_texture_log()
```

### Reference files

| File | Purpose |
|------|---------|
| `wftools/textile/main.cc` | CLI parsing, global config, HTML log frame |
| `wftools/textile/texture.cc` | Full processing pipeline (IFF parse → pack → write) |
| `wftools/textile/bitmap.hp/cc`, `tga.cc`, `bmp.cc`, `sgi.cc` | Bitmap class hierarchy and format readers |
| `wftools/textile/allocmap.hp/cc` | 2D bin-packing algorithm |
| `wftools/textile/rmuv.hp/cc` | UV mapping struct and binary I/O |
| `wftools/textile/ccyc.hp/cc` | Colour cycle animation struct |
| `wftools/textile/profile.cc` | Windows INI reader |
| `wftools/textile/locfile.cc` | Path searching |

### Testing

```bash
# Build
cargo build --manifest-path textile-rs/Cargo.toml

# Integration test: compare outputs against C++ binary
cd textile && ./textile -ini=test.ini
cd ../textile-rs && cargo run -- -ini=../textile/test.ini

diff ../textile/Room0.tga Room0.tga          # atlas image
diff ../textile/Room0.ruv Room0.ruv          # RMUV binary (byte-for-byte)
diff ../textile/Room0.cyc Room0.cyc          # colour cycle binary
```

---

## Completed: `lvldump-rs`

Diagnostic tool that parses compiled `.lvl` binary game-level files and dumps their contents as
human-readable text. Two modes: basic (hex-dump OAD data) and full (`-l objects.lc`, named types
and parsed OAD fields).

### What it does

1. Reads entire `.lvl` file into memory
2. Parses `_LevelOnDisk` header (52 bytes, 13 × i32 LE) for section counts + offsets
3. Follows offset arrays to dump objects, paths, channels, rooms, common block
4. With `-l objects.lc`: loads object type names + per-type `.oad` schema files, displays parsed
   OAD field values for each object instead of raw hex

### CLI

```
lvldump [switches] <.lvl file> [output file]
  -analysis            print object type histogram at end
  -l<lc_file>          load objects.lc + companion .oad files
```

### Binary structures (all LE, `#pragma pack(1)`)

| Struct | Fixed bytes | Notes |
|--------|-------------|-------|
| `_LevelOnDisk` | 52 | 13 × i32: version, 6 pairs of (count, offset) |
| `_ObjectOnDisk` | 65 + OADSize | i16 type; 3×fixed32 pos; 3×fixed32 scale; wf_euler (7 bytes); 6×fixed32 coarse bbox; i32 oadFlags; i16 pathIndex; i16 OADSize |
| `_PathOnDisk` | 43 | 3×fixed32 base pos; wf_euler; 6×i32 channel indices |
| `_ChannelOnDisk` | 12 + numKeys×8 | i32 compressorType; fixed32 endTime; i32 numKeys; entries: (fixed32 time, i32 value) |
| `_RoomOnDisk` | 34 + count×2 | i32 count; 6×fixed32 bbox; i16[2] adjacentRooms; i16 roomObjectIndex |

`fixed32` = i32 Q16.16 → `v as f32 / 65536.0`. `LEVEL_VERSION = 28`.

### Design decisions

- **Zero-copy binary parsing** — `Vec<u8>` + offset arithmetic; no unsafe transmute
- **Reuse `wf_oad`** — schema loading via `OadFile::read()`; binary OAD struct reading
  implemented in `oad.rs` using entry descriptors (port of `QObjectAttributeData::LoadStruct`)
- **Reuse `wf_hdump`** — for common block and raw OAD hex dump (4-indent, 16 bytes/line)
- **`process::exit` + flush** — same pattern as textile-rs
- **Skip `-p` stream redirection** — debug/progress streams suppressed; errors to stderr

### OAD field sizes (for binary struct reading)

| Types | Bytes |
|-------|-------|
| Fixed32, Int32, ObjectReference, Filename, CommonBlock, MeshName, ClassReference | 4 |
| Fixed16, Int16 | 2 |
| Int8 | 1 |
| String | `entry.len` |
| XData | 4 if `conversion_action ≤ 3`, else 0 |
| All flags, PropertySheet, CameraRef, LightRef, etc. | 0 |

### Directory layout

```
lvldump-rs/
  Cargo.toml
  .gitignore
  src/
    main.rs    — CLI arg parsing, load file, open output, call dump_level
    level.rs   — parse + dump: objects, paths, channels, rooms, common block, histogram
    oad.rs     — load_lc_file, load_oad_files, dump_oad_struct (binary OAD reader)
```

### Reference files

| File | Purpose |
|------|---------|
| `wftools/lvldump/lvldump.cc` | CLI, main, file loading |
| `wftools/lvldump/level.cc` | All dump_* functions + exact output format |
| `wftools/lvldump/oad.cc` | OAD schema loading, binary parsing, SizeOfOnDisk |
| `wfsource/source/oas/levelcon.h` | All binary struct definitions |
| `wftools/wf_oad/src/lib.rs` | OadFile, OadEntry, ButtonType — reused for schema |
| `wftools/wf_hdump/src/lib.rs` | `hdump()` — reused for hex output |

### Testing

```bash
cargo build --manifest-path wftools/lvldump-rs/Cargo.toml
# Run on any available .lvl file (build artifacts, not in repo)
lvldump-rs/target/debug/lvldump some.lvl
lvldump-rs/target/debug/lvldump -lobjects.lc some.lvl output.txt
```
