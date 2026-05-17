#!/usr/bin/env bash
# Initialise a local aptly repo named 'foundry' for the 'resolute' suite
# (Kubuntu 26.04 codename: 'resolute raccoon'). Idempotent.
#
# Prereqs: aptly installed (apt install aptly).

set -euo pipefail
cd "$(dirname "$0")/.."

export APTLY_CONFIG="${APTLY_CONFIG:-$(pwd)/aptly/aptly.conf}"

if ! command -v aptly &>/dev/null; then
    echo "ERROR: aptly not installed. Run: sudo apt install aptly" >&2
    exit 1
fi

# Create the repo if it doesn't exist
if ! aptly -config="$APTLY_CONFIG" repo show foundry &>/dev/null; then
    echo "Creating aptly repo 'foundry'..."
    aptly -config="$APTLY_CONFIG" repo create \
        -distribution=resolute \
        -component=main \
        -architectures=amd64,arm64,all \
        foundry
else
    echo "Repo 'foundry' already exists."
fi

aptly -config="$APTLY_CONFIG" repo show foundry
