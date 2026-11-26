#!/usr/bin/env bash
# Open the lava lamp in a visible window on this PC's desktop, at the host's local time, for a review
# (docs/plans/2026-11-26-lava-lamp.md, Phase 6 and Verification 8). The engine runs in the Linux container
# (Mesa, software GL) and draws through the host's X display. Close the window to stop it (or:
# docker stop $(docker ps -q --filter label=org.wbniv.purpose=lava-lamp-review)).
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: bash wflevels/lava_lamp/review_pc.sh [-h|--help] [--size WxH] [-- ENGINE_ARGS...]

Runs wflevels/lava_lamp-standalone.iff in the container engine (build-docker/lava-rel, else lava-dev) in a
window on $DISPLAY, with the container's clock zone set to the host's, so the base shows the PC's local time.
  --size WxH     window size (default 1280x720)
  ENGINE_ARGS    passed to wf_game, e.g. '--property=LavaLampSettings.Lava color=0'
Build the level first (bash wflevels/lava_lamp/build.sh) and the engine
(scripts/in-linux-container.sh scripts/build-wf-game-container.sh --out /build/lava-rel).
EOF
}

size=1280x720 args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --size) [ $# -ge 2 ] || { usage >&2; exit 2; }; size="$2"; shift 2 ;;
        --) shift; args=("$@"); break ;;
        *) usage >&2; exit 2 ;;
    esac
done
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[ -n "${DISPLAY:-}" ] || { echo "review_pc.sh: no DISPLAY (run it from the desktop session)" >&2; exit 2; }
engine=/build/lava-rel/src/engine/wf_game
[ -x "$ROOT/build-docker/lava-rel/src/engine/wf_game" ] || engine=/build/lava-dev/src/engine/wf_game
[ -x "$ROOT/build-docker/${engine#/build/}" ] || { echo "review_pc.sh: no container engine; see --help" >&2; exit 2; }
zone="$(readlink /etc/localtime | sed 's|.*/zoneinfo/||')"
mounts="/tmp/.X11-unix:/tmp/.X11-unix /usr/share/zoneinfo:/usr/share/zoneinfo:ro"
env="DISPLAY=$DISPLAY TZ=$zone WF_REST_PORT=0"
if [ -n "${XAUTHORITY:-}" ] && [ -f "$XAUTHORITY" ]; then
    mounts="$mounts $XAUTHORITY:/tmp/wf-xauth:ro"
    env="$env XAUTHORITY=/tmp/wf-xauth"
fi
w="${size%x*}" h="${size#*x}"
echo "lava lamp review: $(date '+%H:%M') local ($zone), $size, $engine" >&2
WF_CONTAINER_MOUNTS="$mounts" WF_CONTAINER_ENV="$env" WF_CONTAINER_LABELS="org.wbniv.purpose=lava-lamp-review" \
    exec "$ROOT/scripts/in-linux-container.sh" bash -c \
    'cd wfsource/source/game && exec "$0" -L/src/wflevels/lava_lamp-standalone.iff "-width=$1" "-height=$2" "${@:3}"' \
    "$engine" "$w" "$h" "${args[@]}"
