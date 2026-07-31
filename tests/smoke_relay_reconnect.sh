#!/usr/bin/env bash
# Headless smoke for wf-edit mid-session relay reconnect (2026-06-01 critique ⑤).
# Starts a local wf-relay, connects one wf-edit, kills the relay (simulating a
# dropped tunnel), then restarts it — and asserts the editor's stderr shows the
# drop being detected and the room being re-joined:
#     wf-edit: relay dropped — reconnecting to ws://127.0.0.1:<port>
#     wf-edit: relay reconnected, re-joined room=<room>
# The editor runs with a huge --frames budget; timing is controlled entirely by
# when this script kills/restarts the relay and finally kills the editor by PID
# (no fragile frame-rate assumptions). Plan:
#   docs/plans/2026-06-01-implement-the-relay-connect-critique-s-recommendat.md
set -euo pipefail

ROOM=reconnect-smoke-$$
PORT=9993
ROOT=$(git rev-parse --show-toplevel)
RELAY=$ROOT/wftools/wf_collab/target/release/wf-relay
WFEDIT=${WFEDIT:-$ROOT/build-editor-fast/wf-edit}
LOG=/tmp/reconnect-editor.log
RELAYLOG=/tmp/reconnect-relay.log

[ -x "$WFEDIT" ] || { echo "missing editor: $WFEDIT (build with: task build-wf-edit-fast)" >&2; exit 1; }
[ -x "$RELAY" ]  || cargo build --release --bin wf-relay --manifest-path "$ROOT/wftools/wf_collab/Cargo.toml" >&2

rm -rf /tmp/reconnect-cfg; mkdir -p /tmp/reconnect-cfg
EDITOR_PID=""; RELAY_PID=""
cleanup() { kill "$EDITOR_PID" "$RELAY_PID" 2>/dev/null || true; }
trap cleanup EXIT

start_relay() { "$RELAY" --port $PORT >>"$RELAYLOG" 2>&1 & RELAY_PID=$!; }
relay_bound() { for _ in 1 2 3 4 5 6 7 8 9 10; do ss -tln | grep -q ":$PORT " && return 0; sleep 0.2; done; return 1; }
# Wait up to ~20 s for a pattern to appear in the editor log (polls, no sleep-loop on our own state).
wait_for() { local pat="$1"; for _ in $(seq 1 100); do grep -qF "$pat" "$LOG" && return 0; sleep 0.2; done; return 1; }

: >"$LOG"; : >"$RELAYLOG"

echo "[1] start relay on :$PORT"
start_relay; relay_bound || { echo "relay never bound" >&2; exit 1; }

echo "[2] start editor → connect"
XDG_CONFIG_HOME=/tmp/reconnect-cfg DISPLAY=:0 \
    "$WFEDIT" --relay=ws://127.0.0.1:$PORT --room=$ROOM --frames 100000 >>"$LOG" 2>&1 &
EDITOR_PID=$!
wait_for "relay connected" || { echo "editor never connected" >&2; tail -20 "$LOG" >&2; exit 1; }
echo "    connected ✓"

echo "[3] kill relay (simulate tunnel drop)"
kill "$RELAY_PID" 2>/dev/null || true; wait "$RELAY_PID" 2>/dev/null || true
wait_for "relay dropped" || { echo "drop never detected" >&2; tail -20 "$LOG" >&2; exit 1; }
echo "    drop detected ✓"

echo "[4] restart relay → expect reconnect + re-join"
start_relay; relay_bound || { echo "relay never re-bound" >&2; exit 1; }
wait_for "relay reconnected, re-joined" || { echo "never reconnected" >&2; tail -30 "$LOG" >&2; exit 1; }
echo "    reconnected ✓"

echo "[5] PASS — mid-session reconnect verified"
echo "--- editor relay log lines ---"
grep -E "relay (connected|dropped|reconnected)" "$LOG" || true
