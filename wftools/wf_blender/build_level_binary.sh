#!/usr/bin/env bash
# build_level_binary.sh — end-to-end single-level build pipeline
#
# Chains the Rust tools that turn a Blender-exported .lev into a level
# binary IFF and, when a -standalone.iff.txt wrapper exists, the
# engine-loadable L4-wrapped standalone form:
#
#   iffcomp-rs .lev                  → .lev.bin
#   levcomp-rs .lev.bin              → .lvl + asset.inc + .iff.txt + .ini
#   textile-rs .ini                  → palN.tga / RoomN.{tga,ruv,cyc} / Perm.{tga,ruv,cyc}
#   iffcomp-rs .iff.txt              → .iff (inner)
#   iffcomp-rs -standalone.iff.txt   → -standalone.iff (optional; if present)
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

echo "[1/5] iffcomp-rs  $LEVEL.lev  →  $LEVEL.lev.bin"
"$IFFCOMP" -binary -o="$LEVEL.lev.bin" "$LEVEL.lev" >/dev/null

echo "[2/5] levcomp-rs  $LEVEL.lev.bin  →  $LEVEL.lvl + asset.inc + $LEVEL.iff.txt + $LEVEL.ini"
# Optional shared mesh dir: wflevels/<level>/mesh.flags may set MESH_DIR (where the
# per-mesh .iff files live, relative to the level dir — for bbox reads) and
# MESH_REF_PREFIX (path prepended to the .iff.txt file-include refs so iffcomp embeds
# from there). Default = self-contained level dir. SMB levels point both at ../smb/.
# See docs/plans/2026-06-03-smb-shared-mesh-dir.md.
MESH_DIR="."
MESH_REF_PREFIX=""
if [[ -f "$LEVEL_DIR/mesh.flags" ]]; then
  # shellcheck disable=SC1091
  source "$LEVEL_DIR/mesh.flags"
  echo "    mesh.flags: MESH_DIR=$MESH_DIR MESH_REF_PREFIX=$MESH_REF_PREFIX"
fi
LEVCOMP_ARGS=("$LEVEL.lev.bin" "$OBJECTS_LC" "$LEVEL.lvl" "$OAD_DIR"
  --mesh-dir "$MESH_DIR"
  --iff-txt "$LEVEL.iff.txt"
  --textile-ini "$LEVEL.ini")
[[ -n "$MESH_REF_PREFIX" ]] && LEVCOMP_ARGS+=(--mesh-ref-prefix "$MESH_REF_PREFIX")
"$LEVCOMP" "${LEVCOMP_ARGS[@]}"

echo "[3/5] textile-rs  -ini=$LEVEL.ini  →  palN.tga / RoomN.{tga,ruv,cyc} / Perm.{tga,ruv,cyc}"
# Options mirror the historical Makefile recipe at
# wfsource/levels.src/unixmakelvl.pl:130-137.
#
# Per-level texture-page-size override: if wflevels/<level>/textile.flags
# exists, source it to set PAGEX / PAGEY / PERMPAGEX / PERMPAGEY. Existing
# levels with no flags file keep the historical 256² defaults. See
# docs/plans/2026-05-30-runtime-vram-cli-overrides.md.
PAGEX=256
PAGEY=256
PERMPAGEX=256
PERMPAGEY=256
if [[ -f "$LEVEL_DIR/textile.flags" ]]; then
  # shellcheck disable=SC1091
  source "$LEVEL_DIR/textile.flags"
  echo "    textile.flags overrides: PAGEX=$PAGEX PAGEY=$PAGEY PERMPAGEX=$PERMPAGEX PERMPAGEY=$PERMPAGEY"
fi
"$TEXTILE" -ini="$LEVEL.ini" -Tlinux \
  -transparent=0,0,0 \
  -pagex=$PAGEX -pagey=$PAGEY \
  -permpagex=$PERMPAGEX -permpagey=$PERMPAGEY \
  -palx=256 -paly=8 \
  -alignx=w -aligny=h \
  -flipyout -powerof2size \
  >/dev/null 2>&1

echo "[4/5] iffcomp-rs  $LEVEL.iff.txt  →  ../$LEVEL.iff"
"$IFFCOMP" -binary -o="../$LEVEL.iff" "$LEVEL.iff.txt" >/dev/null

SIZE=$(stat -c %s "$REPO/wflevels/$LEVEL.iff")
echo
echo "✓ built $REPO/wflevels/$LEVEL.iff ($SIZE bytes)"

STANDALONE_TXT="$LEVEL-standalone.iff.txt"
if [[ -f "$STANDALONE_TXT" ]]; then
  echo
  echo "[5/5] iffcomp-rs  $STANDALONE_TXT  →  ../$LEVEL-standalone.iff"
  "$IFFCOMP" -binary -o="../$LEVEL-standalone.iff" "$STANDALONE_TXT" >/dev/null
  SIZE_S=$(stat -c %s "$REPO/wflevels/$LEVEL-standalone.iff")
  echo "✓ built $REPO/wflevels/$LEVEL-standalone.iff ($SIZE_S bytes)"
fi
