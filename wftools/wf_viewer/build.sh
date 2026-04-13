#!/usr/bin/env bash
# wf_viewer/build.sh — compile the standalone WF MODL .iff viewer
set -euo pipefail

cd "$(dirname "$0")"

# GL/GLX dev headers live in a Podman container overlay layer;
# GL runtime .so symlinks are there too.
CBASE=/home/will/.local/share/containers/storage/overlay/eb44d05a7edcb9f08dba3fb4a0d3f10b39d504fa6bf5df78b1d94d042ce909bf/diff

g++ -std=c++17 -O2 -Wall \
    -idirafter "$CBASE/usr/include" \
    -o wf_viewer viewer.cc \
    -L"$CBASE/usr/lib/x86_64-linux-gnu" \
    -lGL -lX11 \
    && echo "Built: wf_viewer"
