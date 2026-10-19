#!/usr/bin/env bash
# device_bench.sh: time one tick of school.fth (11 fish) on a real Android device, with no engine and no pipe in the way.
#
# Cross-compiles zf_host.c (the engine's own zForth, float cells) for armeabi-v7a, pushes it with a command file made by
# `python3 bench_cmds.py`, runs it, and prints the mean milliseconds per `sch-tick` over 200 ticks, three times.
# This is the INTERPRETER's cost with the mailboxes as a plain array; the engine's mailbox lookups are extra (not measured here).
#
# Usage: device_bench.sh [-h] [adb-serial]      (default: the only adb device)
set -euo pipefail
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0; fi
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
NDK="${ANDROID_NDK_HOME:-$(ls -d "$HOME"/android-sdk-local/ndk/*/ | tail -1)}"
ADB="${ADB:-$HOME/android-sdk-local/platform-tools/adb}"
SERIAL_ARGS=()
if [[ -n "${1:-}" ]]; then SERIAL_ARGS=(-s "$1"); fi
CC="$(ls "$NDK"/toolchains/llvm/prebuilt/*/bin/armv7a-linux-androideabi21-clang)"
Z="$ROOT/engine"
OUT="$HOME/tmp/swarm-bench"; mkdir -p "$OUT"
"$CC" -O2 -I"$Z/stubs" -I"$Z/vendor/zforth-41db72d1/src/zforth" "$HERE/zf_host.c" "$Z/vendor/zforth-41db72d1/src/zforth/zforth.c" -lm -o "$OUT/zf_host_arm"
python3 "$HERE/bench_cmds.py" > "$OUT/bench_cmds.txt"
"$ADB" "${SERIAL_ARGS[@]}" push "$OUT/zf_host_arm" /data/local/tmp/zf_host >/dev/null
"$ADB" "${SERIAL_ARGS[@]}" push "$OUT/bench_cmds.txt" /data/local/tmp/bench_cmds.txt >/dev/null
echo "device: $("$ADB" "${SERIAL_ARGS[@]}" shell 'getprop ro.product.model; getprop ro.product.cpu.abi' | tr -d '\r' | paste -sd' ')"
for _ in 1 2 3; do
  "$ADB" "${SERIAL_ARGS[@]}" shell 'cd /data/local/tmp && ./zf_host < bench_cmds.txt | tail -1' | tr -d '\r'
done
