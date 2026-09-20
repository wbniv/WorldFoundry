#!/usr/bin/env bash
# Generate fennel_source.cc from a minified fennel.lua.
# Usage: gen_fennel_source.sh <fennel.min.lua> <fennel_source.cc>
set -euo pipefail
MIN="$1"
OUT="$2"
# xxd names the array after the filename argument; run from the file's dir
# so the basename is used rather than the full path.
#
# Kept as `unsigned char`, matching xxd's own output -- NOT rewritten to
# `char`. Fennel's source embeds UTF-8 (e.g. the lambda "λ" symbol), whose
# bytes run up to 0xce/0xbb (>127); (signed) char can't represent that in a
# braced initializer list without an explicit cast, and Clang (upstream and
# AppleClang alike) treats that as a hard "narrowing conversion" error, not a
# warning like GCC does. Consumers cast to `const char*` at the call site
# (scripting_lua.cc) instead.
cd "$(dirname "$MIN")"
xxd -i "$(basename "$MIN")" \
  | sed -E \
    's/^unsigned char [a-z_]+\[\]/extern "C" const unsigned char kFennelSource[]/;
     s/^unsigned int [a-z_]+_len/extern "C" const unsigned int kFennelSourceLen/' \
  > "$OUT"
