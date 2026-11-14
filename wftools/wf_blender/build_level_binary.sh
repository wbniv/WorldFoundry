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
# WF_LEVEL_DIR optionally selects a different source directory (absolute, or
# relative to the repository); final outputs still use wflevels/<level-name>.
# WF_LEVEL_OUT_DIR optionally moves the final <level>.iff and <level>-standalone.iff
# out of wflevels/ (a test building a level variant in a temp dir); the standalone
# wrapper includes "../<level>.iff", so it must be the source directory's parent.
# WF_TEXTILE_OUT_DIR optionally isolates atlas output when source models are
# shared with another level; generated IFF includes point into that directory.

set -euo pipefail

LEVEL="${1:?usage: build_level_binary.sh <level-name>}"

# Resolve key paths relative to repo root (script is under wftools/wf_blender/).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

LEVEL_DIR="${WF_LEVEL_DIR:-$REPO/wflevels/$LEVEL}"
[[ "$LEVEL_DIR" = /* ]] || LEVEL_DIR="$REPO/$LEVEL_DIR"
LEVEL_DIR="$(cd "$LEVEL_DIR" && pwd)"
OUT_DIR="${WF_LEVEL_OUT_DIR:-$REPO/wflevels}"
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
TEXTILE_OUT_DIR="${WF_TEXTILE_OUT_DIR:-.}"
"$TEXTILE" -ini="$LEVEL.ini" -Tlinux -outdir="$TEXTILE_OUT_DIR" \
  -transparent=0,0,0 \
  -pagex=$PAGEX -pagey=$PAGEY \
  -permpagex=$PERMPAGEX -permpagey=$PERMPAGEY \
  -palx=256 -paly=8 \
  -alignx=w -aligny=h \
  -flipyout -powerof2size \
  >/dev/null 2>&1

if [[ "$TEXTILE_OUT_DIR" != "." ]]; then
  python3 - "$LEVEL.iff.txt" "$TEXTILE_OUT_DIR" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
prefix = pathlib.Path(sys.argv[2])
pattern = r'\[ "((?:Room\d+|Perm|pal\d+|palPerm)\.(?:tga|ruv|cyc))" \]'
path.write_text(re.sub(pattern, lambda m: '[ "' + (prefix / m[1]).as_posix() + '" ]', path.read_text()))
PY
fi

echo "[4/5] iffcomp-rs  $LEVEL.iff.txt  →  $OUT_DIR/$LEVEL.iff"
"$IFFCOMP" -binary -o="$OUT_DIR/$LEVEL.iff" "$LEVEL.iff.txt" >/dev/null

SIZE=$(stat -c %s "$OUT_DIR/$LEVEL.iff")
echo
echo "✓ built $OUT_DIR/$LEVEL.iff ($SIZE bytes)"

STANDALONE_TXT="$LEVEL-standalone.iff.txt"
if [[ -f "$STANDALONE_TXT" ]]; then
  echo
  echo "[5/5] iffcomp-rs  $STANDALONE_TXT  →  ../$LEVEL-standalone.iff"
  "$IFFCOMP" -binary -o="$OUT_DIR/$LEVEL-standalone.iff" "$STANDALONE_TXT" >/dev/null
  SIZE_S=$(stat -c %s "$OUT_DIR/$LEVEL-standalone.iff")
  echo "✓ built $OUT_DIR/$LEVEL-standalone.iff ($SIZE_S bytes)"
fi
