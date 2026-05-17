#!/usr/bin/env bash
# Test harness for foundry-linux-setup/install.sh.
# Runs the installer in disposable Docker containers across Ubuntu versions.
#
# Usage:
#   bash test/run-test.sh              # dry-run on Ubuntu 24.04 + 26.04
#   bash test/run-test.sh --real       # full install test (slow)
#   bash test/run-test.sh --version 26.04 --real

set -euo pipefail

cd "$(dirname "$0")/.."

REAL=false
VERSIONS=(24.04 26.04)

while [[ $# -gt 0 ]]; do
    case "$1" in
        --real)        REAL=true ;;
        --version)     shift; VERSIONS=("$1") ;;
        --version=*)   VERSIONS=("${1#*=}") ;;
        -h|--help)
            sed -n '2,9p' "$0" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
    shift
done

if ! command -v docker &>/dev/null; then
    echo "ERROR: docker (or podman aliased to docker) required" >&2
    exit 1
fi

fail=0
for v in "${VERSIONS[@]}"; do
    tag="foundry-test:$v"
    dockerfile="test/Dockerfile.ubuntu${v}"
    if [[ ! -f "$dockerfile" ]]; then
        echo "ERROR: $dockerfile not found" >&2
        fail=1
        continue
    fi

    echo
    echo "=== Building $tag ==="
    docker build -q -f "$dockerfile" -t "$tag" .

    echo
    echo "=== Testing $tag (dry-run) ==="
    if [[ "$v" == "24.04" ]]; then
        # 24.04 needs --allow-24.04
        docker run --rm "$tag" --dry-run --allow-24.04 || { fail=1; continue; }
    else
        docker run --rm "$tag" --dry-run || { fail=1; continue; }
    fi

    if $REAL; then
        echo
        echo "=== Testing $tag (real install, no network optional) ==="
        # Real install runs the full apt + rustup + clone path.
        # Network access is required for rustup + git clone + apt update.
        if [[ "$v" == "24.04" ]]; then
            docker run --rm "$tag" --role engine-dev --allow-24.04 --skip-clone --skip-blender || { fail=1; continue; }
        else
            docker run --rm "$tag" --role engine-dev --skip-clone --skip-blender || { fail=1; continue; }
        fi
    fi
done

if [[ $fail -eq 0 ]]; then
    echo
    echo "=== All tests passed ==="
else
    echo
    echo "=== One or more tests FAILED ===" >&2
    exit 1
fi
