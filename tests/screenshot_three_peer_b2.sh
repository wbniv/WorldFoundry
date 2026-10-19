#!/usr/bin/env bash
# Multi-peer (3-editor) live verification for the shared-cursors B feature.
# Same shape as screenshot_two_peer_b2.sh — spins up a local wf-relay + three
# wf-edit instances (Alice, Bob, Carol) with distinct XDG_CONFIG_HOME so each
# gets a distinct peer_id. The b2 overlay loops `for (peer : peer_presence)`
# in main.cc, so N peers should "just work"; this confirms it visually.
# Carol's screenshot is the canonical multi-peer proof — she should see both
# Alice's and Bob's frustums + selection rings simultaneously, and Peers (3)
# in her chat sidebar.
set -euo pipefail

ROOM=b2-three-$$
PORT=9991
ROOT=$(git rev-parse --show-toplevel)
RELAY=$ROOT/wftools/wf_collab/target/release/wf-relay
WFEDIT=$ROOT/build-editor/wf-edit
SCREENSHOTS=$ROOT/tests/screenshots

if [ ! -x "$RELAY" ]; then
    echo "building wf-relay…"
    cargo build --release --bin wf-relay \
        --manifest-path "$ROOT/wftools/wf_collab/Cargo.toml" >&2
fi

rm -rf /tmp/b2-alice /tmp/b2-bob /tmp/b2-carol
mkdir  /tmp/b2-alice /tmp/b2-bob /tmp/b2-carol
mkdir -p "$SCREENSHOTS"

"$RELAY" --port $PORT >/tmp/b2-relay.log 2>&1 &
RELAY_PID=$!
trap 'kill $RELAY_PID $A_PID $B_PID $C_PID 2>/dev/null || true' EXIT

for _ in 1 2 3 4 5; do
    ss -tln | grep -q ":$PORT " && break
    sleep 0.2
done

# Alice — selects actor index 5, broadcasts ring + frustum.
XDG_CONFIG_HOME=/tmp/b2-alice WF_EDIT_AUTO_SELECT=5 \
DISPLAY=:0 "$WFEDIT" --relay=ws://127.0.0.1:$PORT --room=$ROOM --frames 300 \
    --screenshot "$SCREENSHOTS/wfedit_shared_cursors_b2_live_three_A.ppm" \
    >/tmp/b2-A.log 2>&1 &
A_PID=$!

sleep 0.8

# Bob — selects actor index 15, distinct ring + frustum from Alice.
XDG_CONFIG_HOME=/tmp/b2-bob WF_EDIT_AUTO_SELECT=15 \
DISPLAY=:0 "$WFEDIT" --relay=ws://127.0.0.1:$PORT --room=$ROOM --frames 270 \
    --screenshot "$SCREENSHOTS/wfedit_shared_cursors_b2_live_three_B.ppm" \
    >/tmp/b2-B.log 2>&1 &
B_PID=$!

sleep 0.8

# Carol — last in, will see both Alice's and Bob's frustums in her viewport.
XDG_CONFIG_HOME=/tmp/b2-carol \
DISPLAY=:0 "$WFEDIT" --relay=ws://127.0.0.1:$PORT --room=$ROOM --frames 240 \
    --screenshot "$SCREENSHOTS/wfedit_shared_cursors_b2_live_three_C.ppm" \
    >/tmp/b2-C.log 2>&1 &
C_PID=$!

wait $A_PID || true
wait $B_PID || true
wait $C_PID || true

for p in "$SCREENSHOTS"/wfedit_shared_cursors_b2_live_three_{A,B,C}.ppm; do
    [ -f "$p" ] || { echo "missing: $p" >&2; continue; }
    png="${p%.ppm}.png"
    ffmpeg -y -i "$p" "$png" >/dev/null 2>&1 && rm -f "$p"
    echo "wrote $png ($(stat -c%s "$png") bytes)"
done

ls -la "$SCREENSHOTS"/wfedit_shared_cursors_b2_live_three_*.png 2>&1 || true
