#!/usr/bin/env bash
# test-debug-listener.sh: build and run debug_listener_reconnect_test. Run it INSIDE the
# Linux test container (see `task test-debug-listener`).
#
#   (no flag)    the fix is in: the test must PASS.
#   --negative   builds the test against a copy of debug_server.cc whose listener does
#                not poll, then expects it to be killed by its own 10 s SIGALRM (exit
#                142): proof that the test fails without the fix. The repo is not touched.
set -euo pipefail

usage() {
    cat <<'EOF2'
Usage: scripts/test-debug-listener.sh [-h|--help] [--negative]
Inside the container: configure, build and run debug_listener_reconnect_test.
EOF2
}
negative=0
case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    --negative) negative=1 ;;
    "") ;;
    *) usage >&2; exit 2 ;;
esac

src=/src
build=/build/listener
if [ "$negative" = 1 ]; then
    # Work on a copy so the mounted checkout is never modified.
    src=/tmp/src-negative
    build=/build/listener-negative
    rm -rf "$src"
    rsync -a --exclude '/.git' --exclude '/.worktrees' --exclude '/.claude' --exclude '/build*' --exclude '/cmake-build-*' /src/ "$src/"
    grep -q '::poll(&pfd, 1, 100)' "$src/engine/stubs/debug_server.cc" || { echo "poll line not found: fix not present?" >&2; exit 1; }
    sed -i 's/const int ready = ::poll(&pfd, 1, 100);/const int ready = 1; (void)pfd;/' "$src/engine/stubs/debug_server.cc"
    grep -q 'const int ready = 1' "$src/engine/stubs/debug_server.cc"
fi

# Jolt ships as a tarball (what `task vendor-unpack` does).
if [ ! -d "$src/engine/vendor/jolt-physics-5.5.0" ]; then
    tar -xzf "$src/engine/vendor/jolt-physics-5.5.0.tar.gz" -C "$src/engine/vendor"
    extracted="$(find "$src/engine/vendor" -maxdepth 1 -type d -name 'jrouwe-JoltPhysics-*' | head -n 1)"
    mv "$extracted" "$src/engine/vendor/jolt-physics-5.5.0"
fi

cmake -S "$src" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DWF_ASAN=OFF >"$build.configure.log" 2>&1 \
    || { tail -20 "$build.configure.log"; exit 1; }
if ! cmake --build "$build" --target debug_listener_reconnect_test >"$build.build.log" 2>&1; then
    grep -m1 -A14 '^FAILED' "$build.build.log" || tail -20 "$build.build.log"
    exit 1
fi
tail -1 "$build.build.log"

cd "$build"
start=$(date +%s)
set +e
./debug_listener_reconnect_test
rc=$?
set -e
echo "exit=$rc after $(( $(date +%s) - start )) s"
if [ "$negative" = 1 ]; then
    [ "$rc" = 142 ] || { echo "FAIL: expected SIGALRM (142) without the fix, got $rc" >&2; exit 1; }
    echo "OK: without the poll the test hangs and is killed (the test guards the fix)"
else
    [ "$rc" = 0 ] || { echo "FAIL: expected PASS with the fix, got $rc" >&2; exit 1; }
    echo "OK: with the fix the test passes"
fi
