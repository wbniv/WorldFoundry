# Duplicate marble-madness level for physics/motion co-agent

**Status:** DONE — [`wflevels/marble-madness-2`](../../wflevels/marble-madness-2) created and building.

## Context

The marble-madness level is the active playground for physics and motion work on the 2026-new-level branch. A co-agent is working independently on physics/motion in that level. Duplicating the map gives the co-agent an isolated sandbox (`marble-madness-2`) without conflicting with the primary `marble-madness` level.

The `.lev` file contains zero internal `marble-madness` string references, so duplication requires only minimal text edits.

---

## How the level build pipeline works

`build_level_binary.sh <level-name>` chains four tools, all driven purely by the level directory name and the source `.lev`:

```
wflevels/<name>/<name>.lev
  → iffcomp-rs  → <name>.lev.bin
  → levcomp-rs  → <name>.lvl + asset.inc + <name>.iff.txt + <name>.ini
  → textile-rs  → palN.tga, Room0.{tga,ruv,cyc}, Perm.{tga,ruv,cyc}
  → iffcomp-rs  → ../wflevels/<name>.iff
```

The script auto-generates `.iff.txt`, `.ini`, and all texture assets; we do **not** need to copy those intermediates.

The `-standalone.iff` wrapper is **not** produced by the script — it must be authored once and compiled manually.

---

## Files to create

### 1. `wflevels/marble-madness-2/` directory

Minimum source files needed (the build script derives everything else):

| File | Action |
|---|---|
| `marble-madness-2.lev` | Copy of `marble-madness/marble-madness.lev` — no edits needed |
| `sphere.iff` | Copy of `marble-madness/sphere.iff` (21 KB player marble mesh) |
| `ramp.iff` | Symlink → `../mm_practice_blender/ramp.iff` (same shared ramp) |

Optional but recommended for independence:
- If the co-agent will **modify the ramp geometry**, copy `ramp.iff` instead of symlinking.

### 2. `wflevels/marble-madness-2/marble-madness-2-standalone.iff.txt`

Create this one new text file — it wraps the base `.iff` for `-L` standalone launch:

```
// marble-madness-2-standalone.iff.txt
// Build: iffcomp -binary -o=../marble-madness-2-standalone.iff marble-madness-2-standalone.iff.txt
{ 'L4'
    { 'ALGN' .align( 2048 ) }
    { 'RAM'
        'OBJD' 100000l
        'PERM' 300000l
        'ROOM' 300000l
        'FLAG' 1l 1l
    }
    { 'ALGN' .align( 2048 ) }
    [ "../marble-madness-2.iff" ]
}
```

---

## Build steps

```bash
# From repo root:

# 1. Build the base level IFF
wftools/wf_blender/build_level_binary.sh marble-madness-2

# 2. Build the standalone wrapper
cd wflevels/marble-madness-2
../../wftools/iffcomp-rs/target/release/iffcomp \
  -binary \
  -o=../marble-madness-2-standalone.iff \
  marble-madness-2-standalone.iff.txt
```

---

## Run it

```bash
cd wfsource/source/game
./wf_game -L/absolute/path/to/wflevels/marble-madness-2-standalone.iff
```

---

## Critical files

| Path | Role |
|---|---|
| `wflevels/marble-madness/marble-madness.lev` | Source to copy from |
| `wflevels/marble-madness/sphere.iff` | Player marble mesh to copy |
| `wftools/wf_blender/build_level_binary.sh` | Four-stage build pipeline |
| `wftools/iffcomp-rs/target/release/iffcomp` | IFF compiler (must be pre-built) |
| `wftools/levcomp-rs/target/release/levcomp` | Level compiler (must be pre-built) |
| `wftools/textile-rs/target/release/textile` | Texture packer (must be pre-built) |

---

## Verification

1. `build_level_binary.sh marble-madness-2` exits 0 and reports a non-zero `.iff` size.
2. `wflevels/marble-madness-2.iff` and `marble-madness-2-standalone.iff` both exist.
3. `wf_game -L.../marble-madness-2-standalone.iff` launches, shows the marble on the ramp, and physics/motion behave identically to `marble-madness`.

---

## What NOT to do

- Do **not** add `marble-madness-2` to `cd_full.iff.txt` — standalone `-L` mode is sufficient for physics dev; the multi-level cd.iff is for the shipped game build.
- Do **not** copy intermediate files (`.lev.bin`, `.lvl`, `.iff.txt`, `.ini`, `*.tga`, `*.ruv`, `*.cyc`) — the build script regenerates them all.
