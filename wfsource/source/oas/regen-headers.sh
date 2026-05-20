#!/usr/bin/env bash
# regen-headers.sh — restore the prep → .pp → .ht pipeline lost in 61761e4.
#
# Historical process (wfsource/source/oas/GNUmakefile @ a2784f6):
#   prep -DTYPEFILE_OAS=<stem> oadtypes.s <stem>.pp
#   perl cstruct.pl <stem>.pp > <stem>.ht
#
# cstruct.pl removed with the rest of the old build system. Reimplemented here
# as an inline awk one-pass filter (no perl dependency) that reproduces the
# same byte-identical output.
#
# Usage:
#   regen-headers.sh [OUTDIR]
#
# OUTDIR defaults to the oas source directory (regenerate in place).
# Pass a temp dir to validate without touching the source tree (the oracle test
# does this).
#
# Must be run from any directory; the script cd-s to its own directory so that
# prep's relative @include paths (oadtypes.s → types.h, <stem>.oas;
# objects.s → objects.mac) resolve correctly.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTDIR="${1:-$SCRIPT_DIR}"
PREP="$SCRIPT_DIR/../../../wftools/prep/prep"
BUILD_SH="$SCRIPT_DIR/../../../wftools/prep/build.sh"

# Build prep if missing (same pattern as oas2oad-rs/tests/oas_to_oad.rs).
if [ ! -x "$PREP" ]; then
    echo "prep not found — building via $(basename "$BUILD_SH") ..." >&2
    bash "$BUILD_SH"
fi

# Canonicalizer: faithful awk port of cstruct.pl (a2784f6).
# Per line: strip trailing whitespace, skip blanks, split on ", strip
# non-[A-Za-z0-9_] from inside-quote fields (odd array indices in 1-based awk),
# rejoin without quotes.  Text outside quotes (type keywords, comments, tabs)
# is untouched.
CSTRUCT_AWK='
  { sub(/[ \t\r]*$/,"") }
  length($0) {
    n = split($0, f, "\"")
    for (i = 2; i <= n; i += 2)
      gsub(/[^A-Za-z0-9_]/, "", f[i])
    s = ""
    for (i = 1; i <= n; i++) s = s f[i]
    print s
  }'

TMP=$(mktemp -d /tmp/regen-oas.XXXXXX)
trap 'rm -rf "$TMP"' EXIT

cd "$SCRIPT_DIR"

echo "Regenerating .ht headers..." >&2
count=0
for ht in *.ht; do
    stem="${ht%.ht}"
    "$PREP" -dTYPEFILE_OAS="$stem" oadtypes.s "$TMP/$stem.pp"
    awk "$CSTRUCT_AWK" "$TMP/$stem.pp" > "$OUTDIR/$stem.ht"
    count=$((count + 1))
done
echo "  $count .ht files written to $OUTDIR" >&2

echo "Regenerating objects.{c,e,h}..." >&2
"$PREP" objects.s  "$OUTDIR/objects.c"
"$PREP" objects.es "$OUTDIR/objects.e"
"$PREP" objects.hs "$OUTDIR/objects.h"
echo "  objects.c objects.e objects.h written to $OUTDIR" >&2

echo "Done." >&2
