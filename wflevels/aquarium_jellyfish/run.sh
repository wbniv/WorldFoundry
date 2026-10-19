#!/usr/bin/env bash
set -euo pipefail
TANK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$TANK_ROOT/wflevels/aquarium_jellyfish"
export LD_LIBRARY_PATH="$TANK_ROOT/engine/libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export WF_REST_HOST="${WF_REST_HOST:-127.0.0.1}"
export WF_REST_PORT="${WF_REST_PORT:-18922}"
exec "$TANK_ROOT/engine/wf_game" --debug-port "${TANK_DEBUG_PORT:-17922}" "-L$TANK_ROOT/wflevels/aquarium_jellyfish-standalone.iff" "$@"
