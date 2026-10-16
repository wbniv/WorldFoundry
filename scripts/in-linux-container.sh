#!/usr/bin/env bash
# in-linux-container.sh: run a command in the Linux test image (docker/Dockerfile.linux-test).
#
#   scripts/in-linux-container.sh ctest --test-dir /build
#
# The repo is mounted at /src and build-docker/ at /build, both as the calling
# user (no root-owned files). Core dumps are off and memory is capped, per the
# house rule for batch engine runs. Builds the image on first use.
set -euo pipefail

usage() {
    cat <<'EOF2'
Usage: scripts/in-linux-container.sh [-h|--help] COMMAND [ARGS...]

Runs COMMAND in wf-linux-test:local with the repo at /src and build-docker/ at
/build. Environment: WF_CONTAINER_MEMORY (default 12g), WF_CONTAINER_CPUS (default
all).
EOF2
}
case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    "") usage >&2; exit 2 ;;
esac

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="wf-linux-test:local"
if ! docker image inspect "$image" >/dev/null 2>&1; then
    # Host networking for the build: package downloads then do not depend on Docker's bridge
    # and its firewall rules (a stale ufw/iptables setup breaks the bridge's outbound traffic).
    docker build --network=host -f "$root/docker/Dockerfile.linux-test" -t "$image" "$root/docker" >&2
fi
mkdir -p "$root/build-docker"
cpus=()
[ -n "${WF_CONTAINER_CPUS:-}" ] && cpus=(--cpus "$WF_CONTAINER_CPUS")
# Files must come out owned by the calling user. A rootful daemon maps container
# uids 1:1, so run as $(id -u). A rootless daemon maps container uid 0 to the
# calling user and every other uid to an unprivileged sub-uid that cannot write
# the bind mounts, so there the calling user is --user 0:0.
user=(--user "$(id -u):$(id -g)")
security="$(docker info --format '{{.SecurityOptions}}' 2>/dev/null || true)"
case "$security" in *rootless*) user=(--user 0:0) ;; esac
exec docker run --rm \
    "${user[@]}" \
    --ulimit core=0 --memory "${WF_CONTAINER_MEMORY:-12g}" "${cpus[@]}" \
    -v "$root":/src -v "$root/build-docker":/build -w /src \
    "$image" "$@"
