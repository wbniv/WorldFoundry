#!/usr/bin/env bash
# engine/build_host_gl_test.sh — build the host GL context smoke test.
#
# Standalone build: doesn't depend on libwfengine.a / engine/wf_game being
# built first. Compiles three TUs and links against system X11/GLX:
#   1. gfx/gl/host_gl_context.cc  (the real registry impl)
#   2. wf_host_gl_test/mesa_stub.cc (minimal _closeRequested + getter)
#   3. wf_host_gl_test/host_gl_test.cc (the test driver with main())
#
# End-to-end exercise that wires the registry to a real WFGame requires
# linking against libwfengine.a with -Wl,--allow-multiple-definition (to
# dodge main.cc's main()) and is deferred to a follow-up TODO.
#
# Output: engine/wf_host_gl_test/wf_host_gl_test
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$REPO_ROOT/wfsource/source"
HARNESS_DIR="$SCRIPT_DIR/wf_host_gl_test"

CXXFLAGS=(
    -std=c++17 -O0 -g -Wall -Wextra -Wno-unused-parameter
    -D__LINUX__
    -I"$SRC"
)

echo "  CC gfx/gl/host_gl_context.cc"
g++ "${CXXFLAGS[@]}" -c "$SRC/gfx/gl/host_gl_context.cc" \
    -o "$HARNESS_DIR/host_gl_context.o"

echo "  CC mesa_stub.cc"
g++ "${CXXFLAGS[@]}" -c "$HARNESS_DIR/mesa_stub.cc" \
    -o "$HARNESS_DIR/mesa_stub.o"

echo "  CC host_gl_test.cc"
g++ "${CXXFLAGS[@]}" -c "$HARNESS_DIR/host_gl_test.cc" \
    -o "$HARNESS_DIR/host_gl_test.o"

echo "  LINK wf_host_gl_test"
g++ "$HARNESS_DIR/host_gl_test.o" \
    "$HARNESS_DIR/host_gl_context.o" \
    "$HARNESS_DIR/mesa_stub.o" \
    -lGL -lGLU -lX11 -lm -lpthread \
    -Wl,-z,noexecstack \
    -o "$HARNESS_DIR/wf_host_gl_test"

echo ""
echo "Built: $HARNESS_DIR/wf_host_gl_test"
echo "Run:   DISPLAY=:0 $HARNESS_DIR/wf_host_gl_test"
