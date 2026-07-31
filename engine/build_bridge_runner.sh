#!/usr/bin/env bash
# build_bridge_runner.sh — Build the standalone C++ PILOT bridge runner.
#
# The runner links only pilot_core + host_bridge + pthreads — no engine headers,
# no vendored libs. It is the Phase-3 replacement for tests/pilot/pilot_driver.py
# (engine-tier scenarios only; vm-tier still runs through the same binary).
#
# Output: engine/pilot_bridge_runner

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PILOT_DIR="$SCRIPT_DIR/pilot"
OUT="$SCRIPT_DIR"

CXX="${CXX:-g++}"
CXXFLAGS="${CXXFLAGS:--std=c++17 -g -Wall -Wextra -Wno-unused-parameter}"

echo "=== Building pilot_bridge_runner ==="
"$CXX" $CXXFLAGS \
    -I"$PILOT_DIR" \
    "$PILOT_DIR/pilot_core.cc" \
    "$PILOT_DIR/host_bridge.cc" \
    "$PILOT_DIR/pilot_bridge_runner.cc" \
    -lpthread \
    -o "$OUT/pilot_bridge_runner"
echo "Built: $OUT/pilot_bridge_runner"
