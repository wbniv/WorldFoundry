#!/usr/bin/env bash
# Build libwf_game.so for Android at two revisions and compare their loaded sections.
#
# Layer 1b of finding-your-way docs/plans/2026-11-08-ios-touch-parity.md: moving
# hal/android/touch_controls.h to hal/touch_controls.h (namespace wftouch, with an
# androidtouch alias) must leave the Android library's code and data byte for byte as
# they were. Builds the shipping configuration (Release: -O3, thin LTO, section GC,
# ICF; android-21) for arm64-v8a and armeabi-v7a with plain CMake and the NDK's
# toolchain file, the base revision first and then the head revision in the same
# build tree (so the head build recompiles only what changed), then runs
# scripts/android_alloc_sections_equal.py on each pair.
#
# The git checkout switches the tree, so the caller runs a copy of this script and of
# the compare script from outside it (the Codemagic android-touch-bytes workflow does).
#
# Usage: android_touch_bytes.sh BASE_REV HEAD_REV OUT_DIR
# Env:   SRC (default: the current git top level), NDK (default:
#        $ANDROID_SDK_ROOT/ndk/$WF_NDK_VERSION), COMPARE (default: alongside this script)
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -ne 3 ]]; then
  sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'
  [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && exit 0 || exit 2
fi

base_rev=$1 head_rev=$2 out=$3
SRC=${SRC:-$(git rev-parse --show-toplevel)}
SDK=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}
NDK=${NDK:-$SDK/ndk/${WF_NDK_VERSION:-26.2.11394342}}
COMPARE=${COMPARE:-$(cd "$(dirname "$0")" && pwd)/android_alloc_sections_equal.py}
mkdir -p "$out"
out=$(cd "$out" && pwd)
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

[[ -f "$NDK/build/cmake/android.toolchain.cmake" ]] || { echo "$(ts) no NDK at $NDK" >&2; exit 1; }
[[ -f "$COMPARE" ]] || { echo "$(ts) no compare script at $COMPARE" >&2; exit 1; }
base_sha=$(git -C "$SRC" rev-parse "$base_rev")
head_sha=$(git -C "$SRC" rev-parse "$head_rev")
echo "$(ts) base $base_sha, head $head_sha, NDK $NDK"

for rev in base head; do
  sha=$base_sha; [[ $rev == head ]] && sha=$head_sha
  git -C "$SRC" checkout --quiet --detach "$sha"
  echo "$(ts) checked out $rev $(git -C "$SRC" log --oneline -1)"
  for abi in arm64-v8a armeabi-v7a; do
    bld="$SRC/build-android-bytes-$abi"
    cmake -S "$SRC" -B "$bld" -G Ninja \
      -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
      -DANDROID_ABI="$abi" -DANDROID_PLATFORM=android-21 \
      -DCMAKE_BUILD_TYPE=Release > "$out/configure-$rev-$abi.log" 2>&1 \
      || { echo "$(ts) configure $rev $abi failed"; tail -40 "$out/configure-$rev-$abi.log"; exit 1; }
    start=$(date +%s)
    cmake --build "$bld" --target wf_game > "$out/build-$rev-$abi.log" 2>&1 \
      || { echo "$(ts) build $rev $abi failed"; grep -E -A3 'error:|FAILED' "$out/build-$rev-$abi.log" | head -60; exit 1; }
    lib=$(find "$bld" -name libwf_game.so -type f | head -1)
    cp "$lib" "$out/libwf_game-$rev-$abi.so"
    echo "$(ts) built $rev $abi in $(( $(date +%s) - start )) s: $(wc -c < "$lib") bytes," \
         "$(grep -c '^\[' "$out/build-$rev-$abi.log" || true) build steps"
  done
done
git -C "$SRC" checkout --quiet --detach "$head_sha"

status=0
for abi in arm64-v8a armeabi-v7a; do
  echo "=== $abi ==="
  python3 "$COMPARE" "$out/libwf_game-base-$abi.so" "$out/libwf_game-head-$abi.so" | tee "$out/compare-$abi.txt" || status=1
done
echo "$(ts) ANDROID BYTES: $([[ $status == 0 ]] && echo IDENTICAL || echo DIFFERENT) (loaded sections, Release, both ABIs)"
exit $status
