#!/usr/bin/env bash
# Generate fennel_source.cc from a minified fennel.lua.
# Usage: gen_fennel_source.sh <fennel.min.lua> <fennel_source.cc>
set -euo pipefail
MIN="$1"
OUT="$2"
# xxd names the array after the filename argument; run from the file's dir
# so the basename is used rather than the full path.
cd "$(dirname "$MIN")"
xxd -i "$(basename "$MIN")" \
  | sed -E \
    's/^unsigned char [a-z_]+\[\]/extern "C" const char kFennelSource[]/;
     s/^unsigned int [a-z_]+_len/extern "C" const unsigned int kFennelSourceLen/' \
  > "$OUT"
