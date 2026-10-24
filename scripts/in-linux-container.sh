#!/usr/bin/env bash
# in-linux-container.sh: run a command in the Linux test image (docker/Dockerfile.linux-test),
# or in the Blender level-build image (docker/Dockerfile.blender: Ubuntu 26.04 with the host's Blender).
#
#   scripts/in-linux-container.sh ctest --test-dir /build
#   WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --version
#
# The repo is mounted at /src and build-docker/ at /build, both as the calling
# user (no root-owned files). Core dumps are off and memory is capped, per the
# house rule for batch engine runs. Builds the image on first use.
set -euo pipefail

usage() {
    cat <<'EOF2'
Usage: scripts/in-linux-container.sh [-h|--help] COMMAND [ARGS...]

Runs COMMAND in a container with the repo at /src and build-docker/ at /build.
Environment:
  WF_CONTAINER_IMAGE    linux-test (default: wf-linux-test:local) or blender
                        (wf-blender:local, docker/Dockerfile.blender: Foundry Linux's Blender 5.0.1)
  WF_CONTAINER_MEMORY   memory cap (default 12g)
  WF_CONTAINER_CPUS     CPU cap (default all)
  WF_CONTAINER_ENV      space-separated docker -e entries, NAME or NAME=VALUE (no
                        spaces inside an entry); NAME alone forwards the caller's value
  WF_CONTAINER_NETWORK  docker --network value (default: Docker's default bridge)
EOF2
}
case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    "") usage >&2; exit 2 ;;
esac

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Build an image from its Dockerfile if it is not in the local store yet.
# Host networking for the build: package downloads then do not depend on Docker's bridge
# and its firewall rules (a stale ufw/iptables setup breaks the bridge's outbound traffic).
ensure_image() {
    local tag="$1" dockerfile="$2"
    docker image inspect "$tag" >/dev/null 2>&1 && return 0
    docker build --network=host -f "$root/docker/$dockerfile" -t "$tag" "$root/docker" >&2
}
case "${WF_CONTAINER_IMAGE:-linux-test}" in
    linux-test)
        image="wf-linux-test:local"
        ensure_image "$image" Dockerfile.linux-test ;;
    blender)
        image="wf-blender:local"
        ensure_image "$image" "${WF_BLENDER_DOCKERFILE:-Dockerfile.blender}" ;;
    *)
        echo "in-linux-container.sh: unknown WF_CONTAINER_IMAGE '${WF_CONTAINER_IMAGE}' (linux-test|blender)" >&2
        exit 2 ;;
esac
mkdir -p "$root/build-docker"
extra=()
[ -n "${WF_CONTAINER_CPUS:-}" ] && extra+=(--cpus "$WF_CONTAINER_CPUS")
[ -n "${WF_CONTAINER_NETWORK:-}" ] && extra+=(--network "$WF_CONTAINER_NETWORK")
for entry in ${WF_CONTAINER_ENV:-}; do
    extra+=(-e "$entry")
done
# Files must come out owned by the calling user. A rootful daemon maps container
# uids 1:1, so run as $(id -u). A rootless daemon maps container uid 0 to the
# calling user and every other uid to an unprivileged sub-uid that cannot write
# the bind mounts, so there the calling user is --user 0:0.
user=(--user "$(id -u):$(id -g)")
security="$(docker info --format '{{.SecurityOptions}}' 2>/dev/null || true)"
case "$security" in *rootless*) user=(--user 0:0) ;; esac
exec docker run --rm \
    "${user[@]}" \
    --ulimit core=0 --memory "${WF_CONTAINER_MEMORY:-12g}" "${extra[@]}" \
    -v "$root":/src -v "$root/build-docker":/build -w /src \
    "$image" "$@"
