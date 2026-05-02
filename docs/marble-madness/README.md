# Marble Madness — Level Recreation

Six arcade levels reproduced from the original ROM data.  
Source is `assets/arcade-roms/marble.zip`; all geometry derives from `decode_levels.py` → `levels.json`.

Related plans and investigations:

- [Level recreation workflow](../plans/2026-05-02-level-recreation-workflow.md)
- [Faithful recreation plan](../plans/2026-05-01-marble-madness-faithful.md)
- [ROM level-data investigation](../investigations/2026-05-01-marble-madness-rom-level-data.md)
- [Level elevations](../investigations/2026-05-01-mm-level-elevations.md)

---

## Running a Level

All level files live in `wflevels/marble-madness/`.  
The engine must be launched from `wfsource/source/game/` (it looks for `cd.iff` there).

```sh
cd wfsource/source/game
```

Then pass the standalone IFF with `-L`:

### Practice (tutorial)

```sh
../../engine/wf_game -L../../wflevels/marble-madness/mm_practice_rom-standalone.iff
```

### Beginner (Race 1)

```sh
../../engine/wf_game -L../../wflevels/marble-madness/mm_fromscratch-standalone.iff
```

### Intermediate (Race 2)

```sh
../../engine/wf_game -L../../wflevels/marble-madness/mm_intermediate-standalone.iff
```

### Aerial (Race 3)

```sh
../../engine/wf_game -L../../wflevels/marble-madness/mm_aerial-standalone.iff
```

### Silly (Race 4)

```sh
../../engine/wf_game -L../../wflevels/marble-madness/mm_silly-standalone.iff
```

### Ultimate (Race 5)

```sh
../../engine/wf_game -L../../wflevels/marble-madness/mm_ultimate-standalone.iff
```

---

## Build Pipeline (per level)

Run these from `wflevels/marble-madness/`.  
Set `IFFCOMP` and `LEVCOMP` to the release binaries once and reuse:

```sh
IFFCOMP=../../wftools/iffcomp-rs/target/release/iffcomp
LEVCOMP=../../wftools/levcomp-rs/target/release/levcomp
OAD_DIR=../../wftools/wf_oad/tests/fixtures
OBJECTS_LC=../../wfsource/source/oas/objects.lc
LEVEL=mm_intermediate          # change per level
```

```sh
# 1. Blender scene → .lev
blender --background --python blender_${LEVEL#mm_}.py

# 2. .lev → .lev.bin
$IFFCOMP -binary -o=${LEVEL}.lev.bin ${LEVEL}.lev

# 3. .lev.bin → .lvl + .iff.txt
$LEVCOMP ${LEVEL}.lev.bin $OBJECTS_LC ${LEVEL}.lvl $OAD_DIR \
    --mesh-dir . --iff-txt ${LEVEL}.iff.txt

# 4. .iff.txt → .iff
$IFFCOMP -binary -o=${LEVEL}.iff ${LEVEL}.iff.txt

# 5. standalone wrapper
$IFFCOMP -binary -o=${LEVEL}-standalone.iff ${LEVEL}-standalone.iff.txt
```

The Blender script name matches `blender_mm_<levelname>.py` where `<levelname>` is
the lowercase level name (`practice_rom`, `fromscratch`, `intermediate`, `aerial`,
`silly`, `ultimate`).

---

## Level Summary

| Level | Script | Segs | Path extent | Timer | Status |
|-------|--------|------|-------------|-------|--------|
| Practice | `blender_mm_practice_rom.py` | 9 path + 2 goal | ~28 m ENE + 7 m NE | 60 s | ✓ running |
| Beginner | `blender_mm_fromscratch.py` | 7 path + 2 goal | ~18 m NE | 25 s | ✓ running |
| Intermediate | `blender_mm_intermediate.py` | 2 path + 2 goal | ~8 m NNE | 40 s | built |
| Aerial | `blender_mm_aerial.py` | 9 path + 2 goal | ~5 m E + 14 m NE | 35 s | built |
| Silly | `blender_mm_silly.py` | 3 path + 2 goal | ~8 m NNE | 20 s | built |
| Ultimate | `blender_mm_ultimate.py` | 18 path + 5 goal | ~30 m NE | 55 s | built |

---

## Source Files

| File | Purpose |
|------|---------|
| `decode_levels.py` | Reads `assets/arcade-roms/marble.zip` → `levels.json` |
| `levels.json` | Decoded ROM segment data for all 6 levels |
| `rom_to_blender.py` | Converts `levels.json` → Blender collision mesh |
| `blender_mm_<level>.py` | Per-level Blender scene script (actors + path) |
| `mm_<level>.lev` | Exported level source (generated) |
| `mm_<level>.iff` | Assembled level asset bundle (generated) |
| `mm_<level>-standalone.iff.txt` | L4 wrapper for `wf_game -L` |
| `mm_<level>-standalone.iff` | Built standalone bundle (generated) |
