#!/usr/bin/env bash
set -euo pipefail
SHRIMP_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$SHRIMP_ROOT/wflevels/aquarium_blue_shrimp"
export LD_LIBRARY_PATH="$SHRIMP_ROOT/engine/libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$SHRIMP_ROOT/engine/wf_game" "-L$SHRIMP_ROOT/wflevels/aquarium_blue_shrimp-standalone.iff" "$@"
