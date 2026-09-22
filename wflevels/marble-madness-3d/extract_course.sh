#!/usr/bin/env bash
# extract_course.sh — pull a Marble Madness course out of the arcade ROM via MAME.
#
# Runs MAME headless on the vendored ROM set with the sweep Lua script, which
# dumps work RAM + playfield VRAM every 50 frames while the attract-mode demo
# plays the course, then merges the dumps with mm_merge_course.py (which
# re-implements the game's own surface-height code) into course-<name>.json,
# and finally scales/mirrors it into the gen_course.py contract (course.json).
#
# Usage: extract_course.sh [--rom-dir DIR] [--level N] [--out-dir DIR]
#   --rom-dir   directory holding marble.zip (default: ~/Downloads, then assets/arcade-roms)
#   --level     arcade level index 0..5 (default 0 = Practice)
#   --out-dir   where dumps go (default: a temp dir)
set -euo pipefail

usage() { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }
ROM_DIR=""; LEVEL=0; OUT_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage ;;
    --rom-dir) ROM_DIR="$2"; shift 2 ;;
    --level) LEVEL="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
if [[ -z "$ROM_DIR" ]]; then
  for d in "$HOME/Downloads" "$REPO/assets/arcade-roms"; do
    [[ -f "$d/marble.zip" ]] && ROM_DIR="$d" && break
  done
fi
[[ -f "$ROM_DIR/marble.zip" ]] || { echo "marble.zip not found (use --rom-dir)" >&2; exit 1; }
[[ -n "$OUT_DIR" ]] || OUT_DIR="$(mktemp -d)"
mkdir -p "$OUT_DIR/sweep"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ROM=$ROM_DIR/marble.zip level=$LEVEL out=$OUT_DIR"

# 1. flat 68000 ROM image (interleave the 16-bit ROM pairs)
python3 - "$ROM_DIR/marble.zip" "$OUT_DIR/marble_game.bin" <<'EOF'
import sys, zipfile
rom = bytearray(0x30000)
pairs = [('136033.623', '136033.624', 0x10000), ('136033.625', '136033.626', 0x18000),
         ('136033.627', '136033.628', 0x20000), ('136033.229', '136033.630', 0x28000)]
with zipfile.ZipFile(sys.argv[1]) as zf:
    for odd, even, base in pairs:
        o, e = zf.read(odd), zf.read(even)
        for i in range(len(o)):
            rom[base + 2 * i] = o[i]; rom[base + 2 * i + 1] = e[i]
open(sys.argv[2], 'wb').write(rom)
EOF

# 2. MAME sweep (attract mode plays Practice then Beginner; ~30 s emulated)
LUA="$REPO/scripts/research/mame/mm/mm_demo_sweep.lua"
( cd "$OUT_DIR" && S="$OUT_DIR" MM_SWEEP_DIR="$OUT_DIR/sweep" timeout 600 mame -rompath "$ROM_DIR" -video none -sound none -nothrottle \
    -seconds_to_run 60 -skip_gameinfo -snapshot_directory "$OUT_DIR/sweep" -autoboot_script "$LUA" marble 2>&1 | grep -v '^Average' || true )
[[ -f "$OUT_DIR/sweep/log.txt" ]] || { echo "sweep produced no log — MAME failed?" >&2; exit 1; }

# 3. merge + convert
NAME=$(python3 -c "print(['practice','beginner','intermediate','aerial','silly','ultimate'][$LEVEL])")
python3 "$HERE/mm_merge_course.py" --rom "$OUT_DIR/marble_game.bin" --sweep "$OUT_DIR/sweep" --level "$LEVEL" \
    --out "$HERE/course-$NAME.json"
case "$LEVEL" in
  0) python3 "$HERE/mm_course_to_level.py" "$HERE/course-$NAME.json" "$HERE/course.json" --spawn 139.97 140 --goal 77 64 81 68 --name "$NAME" ;;
  *) echo "no spawn/goal calibration for level $LEVEL yet; course-$NAME.json written" ;;
esac
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) done"
