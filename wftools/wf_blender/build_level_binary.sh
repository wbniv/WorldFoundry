#!/usr/bin/env bash
# build_level_binary.sh — end-to-end single-level build pipeline
#
# Chains the four Rust tools (iffcomp twice) that turn a Blender-exported
# .lev into a standalone level binary IFF:
#
#   iffcomp-rs .lev             → .lev.bin
#   levcomp-rs .lev.bin         → .lvl + asset.inc + .iff.txt + .ini
#   textile-rs .ini             → palN.tga / RoomN.{tga,ruv,cyc} / Perm.{tga,ruv,cyc}
#   iffcomp-rs .iff.txt         → .iff
#
# Usage:
#   wftools/wf_blender/build_level_binary.sh <level-name>
#   wftools/wf_blender/build_level_binary.sh snowgoons
#
# The level-name arg picks the directory under wflevels/. Sources live in
# `wflevels/<level-name>/` with `<level-name>.lev` and the per-mesh .iff
# files Blender (or the historical max2lev pipeline) produced. Final
# output is written to `wflevels/<level-name>.iff`.

set -euo pipefail

LEVEL="${1:?usage: build_level_binary.sh <level-name>}"

# Resolve key paths relative to repo root (script is under wftools/wf_blender/).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

LEVEL_DIR="$REPO/wflevels/$LEVEL"
OAD_DIR="$REPO/wfsource/source/oas"
OBJECTS_LC="$OAD_DIR/objects.lc"

IFFCOMP="$REPO/wftools/iffcomp-rs/target/release/iffcomp"
LEVCOMP="$REPO/wftools/levcomp-rs/target/release/levcomp"
TEXTILE="$REPO/wftools/textile-rs/target/release/textile"

for bin in "$IFFCOMP" "$LEVCOMP" "$TEXTILE"; do
  [[ -x "$bin" ]] || { echo "missing $bin — run \`cargo build --release\` in its crate" >&2; exit 1; }
done
[[ -d "$LEVEL_DIR" ]]      || { echo "no level dir: $LEVEL_DIR" >&2; exit 1; }
[[ -f "$LEVEL_DIR/$LEVEL.lev" ]] || { echo "no .lev source: $LEVEL_DIR/$LEVEL.lev" >&2; exit 1; }
[[ -f "$OBJECTS_LC" ]]     || { echo "no objects.lc: $OBJECTS_LC" >&2; exit 1; }

cd "$LEVEL_DIR"

echo "[1/4] iffcomp-rs  $LEVEL.lev  →  $LEVEL.lev.bin"
"$IFFCOMP" -binary -o="$LEVEL.lev.bin" "$LEVEL.lev" >/dev/null

echo "[2/4] levcomp-rs  $LEVEL.lev.bin  →  $LEVEL.lvl + asset.inc + $LEVEL.iff.txt + $LEVEL.ini"
"$LEVCOMP" "$LEVEL.lev.bin" "$OBJECTS_LC" "$LEVEL.lvl" "$OAD_DIR" \
  --mesh-dir . \
  --iff-txt "$LEVEL.iff.txt" \
  --textile-ini "$LEVEL.ini"

echo "[3/4] textile-rs  -ini=$LEVEL.ini  →  palN.tga / RoomN.{tga,ruv,cyc} / Perm.{tga,ruv,cyc}"
# Options mirror the historical Makefile recipe at
# wfsource/levels.src/unixmakelvl.pl:130-137.
"$TEXTILE" -ini="$LEVEL.ini" -Tlinux \
  -transparent=0,0,0 \
  -pagex=256 -pagey=256 \
  -permpagex=256 -permpagey=256 \
  -palx=256 -paly=8 \
  -alignx=w -aligny=h \
  -flipyout -powerof2size \
  >/dev/null 2>&1

echo "[4/4] iffcomp-rs  $LEVEL.iff.txt  →  ../$LEVEL.iff"
"$IFFCOMP" -binary -o="../$LEVEL.iff" "$LEVEL.iff.txt" >/dev/null

SIZE=$(stat -c %s "$REPO/wflevels/$LEVEL.iff")
echo
echo "✓ built $REPO/wflevels/$LEVEL.iff ($SIZE bytes)"
