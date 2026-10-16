#!/usr/bin/env bash
set -euo pipefail
TANK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$TANK_ROOT/wflevels/aquarium_plants"
export LD_LIBRARY_PATH="$TANK_ROOT/engine/libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export WF_REST_HOST="${WF_REST_HOST:-127.0.0.1}"
export WF_REST_PORT="${WF_REST_PORT:-18926}"
# Perm.tga packs into up to 1024 square (textile.flags PERMPAGEX/Y): reserve the aquarium app's slot sizes.
exec "$TANK_ROOT/engine/wf_game" --vram-width=2048 --vram-height=1024 --vram-slot-width=512 --vram-slot-height=512 --vram-perm-width=1024 --vram-perm-height=1024 --debug-port "${TANK_DEBUG_PORT:-17926}" "-L$TANK_ROOT/wflevels/aquarium_plants-standalone.iff" "$@"
