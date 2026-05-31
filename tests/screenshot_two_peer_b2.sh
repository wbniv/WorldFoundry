#!/usr/bin/env bash
# Live two-editor verification for the shared-cursors B feature.
# Spins up a local wf-relay on loopback + two wf-edit instances with distinct
# XDG_CONFIG_HOME (so distinct peer_ids), captures each viewport. Instance B's
# screenshot proves the network path end-to-end: A's broadcast (cam pose +
# selected actor) flows through the relay → B parses → B's viewport renders
# A's frustum + selection ring.
# Plan: docs/plans/2026-05-31-shared-cursors-b-leftovers.md §2
set -euo pipefail

ROOM=b2-smoke-$$
PORT=9991
ROOT=$(git rev-parse --show-toplevel)
LEVEL=$ROOT/wflevels/qbert_practice/qbert_practice.iff
RELAY=$ROOT/wftools/wf_collab/target/release/wf-relay
WFEDIT=$ROOT/build-editor/wf-edit
SCREENSHOTS=$ROOT/tests/screenshots

# Build the relay if absent (release build, takes a moment first time).
if [ ! -x "$RELAY" ]; then
    echo "building wf-relay…"
    cargo build --release --bin wf-relay \
        --manifest-path "$ROOT/wftools/wf_collab/Cargo.toml" >&2
fi

# Free state.
rm -rf /tmp/b2-alice /tmp/b2-bob
mkdir  /tmp/b2-alice /tmp/b2-bob
mkdir -p "$SCREENSHOTS"

# Start relay on loopback.
"$RELAY" --port $PORT >/tmp/b2-relay.log 2>&1 &
RELAY_PID=$!
trap 'kill $RELAY_PID $A_PID $B_PID 2>/dev/null || true' EXIT

# Wait briefly for the relay to bind (cheap: poll netstat once).
for _ in 1 2 3 4 5; do
    ss -tln | grep -q ":$PORT " && break
    sleep 0.2
done

# Instance A — Alice, broadcasts an actor selection (WF_EDIT_AUTO_SELECT=5) so
# she contributes a ring + frustum without any interactive click. Distinct
# display name lets us recognise her in B's screenshot.
XDG_CONFIG_HOME=/tmp/b2-alice WF_EDIT_AUTO_SELECT=5 \
DISPLAY=:0 "$WFEDIT" --relay=ws://127.0.0.1:$PORT --room=$ROOM --frames 200 \
    --screenshot "$SCREENSHOTS/wfedit_shared_cursors_b2_live_A.ppm" \
    "$LEVEL" >/tmp/b2-A.log 2>&1 &
A_PID=$!

# Instance B — Bob, captures what Alice's overlay looks like from his viewport.
XDG_CONFIG_HOME=/tmp/b2-bob \
DISPLAY=:0 "$WFEDIT" --relay=ws://127.0.0.1:$PORT --room=$ROOM --frames 200 \
    --screenshot "$SCREENSHOTS/wfedit_shared_cursors_b2_live_B.ppm" \
    "$LEVEL" >/tmp/b2-B.log 2>&1 &
B_PID=$!

# Both auto-exit at frame 200; we wait for them.
wait $A_PID || true
wait $B_PID || true

# PPM → PNG, then drop PPMs (large + binary).
for p in "$SCREENSHOTS"/wfedit_shared_cursors_b2_live_A.ppm "$SCREENSHOTS"/wfedit_shared_cursors_b2_live_B.ppm; do
    [ -f "$p" ] || { echo "missing: $p" >&2; continue; }
    png="${p%.ppm}.png"
    ffmpeg -y -i "$p" "$png" >/dev/null 2>&1 && rm -f "$p"
    echo "wrote $png ($(stat -c%s "$png") bytes)"
done

ls -la "$SCREENSHOTS"/wfedit_shared_cursors_b2_live_*.png 2>&1 || true
