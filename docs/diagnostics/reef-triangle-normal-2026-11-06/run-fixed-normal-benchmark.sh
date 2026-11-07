#!/bin/sh
set -eu
root=$(git rev-parse --show-toplevel)
out="$root/docs/diagnostics/reef-triangle-normal-2026-11-06"
work=$(mktemp -d /tmp/reef-fixed-normal.XXXXXX)
mkdir -p "$work/baseline/gfx"
cp "$out/fixed-normal-baseline-face.hpi" "$work/baseline/gfx/face.hpi"
flags='-O3 -std=c++17 -fno-rtti -fpermissive -Wno-register -DDEBUG=0 -DDEBUG_VARIABLES=0 -DDO_ASSERTIONS=0 -DDO_DEBUGGING_INFO=0 -DDO_DEBUG_FILE_SYSTEM=0 -DDO_IOSTREAMS=0 -DDO_TEST_CODE=0 -DDO_VALIDATION=0 -DNDEBUG -DSW_DBSTREAM=0 -DRENDERER_GL -DRENDERER_PIPELINE_GL -DSCALAR_TYPE_FIXED -DWF_TARGET_LINUX -D__LINUX__'
# Deliberate splitting of the fixed list of compiler flags.
# shellcheck disable=SC2086
g++ $flags -I"$work/baseline" -I"$root/wfsource/source" -I"$root/engine/include" -I"$root/engine/stubs" "$out/fixed-normal-host-bench.cpp" -o "$work/baseline-bench"
# shellcheck disable=SC2086
g++ $flags -I"$root/wfsource/source" -I"$root/engine/include" -I"$root/engine/stubs" "$out/fixed-normal-host-bench.cpp" -o "$work/candidate-bench"
for variant in baseline candidate; do
  "$work/$variant-bench" "$out/fixed-normal-triangles.bin"
done
printf 'Executables: %s\n' "$work"
