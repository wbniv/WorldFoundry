#!/usr/bin/env bash
# wf_viewer/build.sh — compile the standalone WF MODL .iff viewer
#
# Requires GL + X11 dev headers and libraries from the host package
# manager. On Debian/Ubuntu: `apt install libgl-dev libx11-dev g++`.
#
# Earlier revisions of this script pointed `-idirafter` and `-L` at a
# host-specific podman overlay layer; that path doesn't exist on any
# other machine. Standard apt headers work without overrides.
set -euo pipefail

cd "$(dirname "$0")"

g++ -std=c++17 -O2 -Wall \
    -o wf_viewer viewer.cc \
    -lGL -lX11 \
    && echo "Built: wf_viewer"
