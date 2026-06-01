# Plan — Shared cursors B leftovers: Jump-to-view + live verification + display-name input

> Continuation of B in [`docs/plans/2026-05-30-a-e-b-audit-follow-up-mailbox-999-fix-shared-curso.md`](../../WorldFoundry.2026-new-level/docs/plans/2026-05-30-a-e-b-audit-follow-up-mailbox-999-fix-shared-curso.md) and [`docs/plans/2026-05-31-shared-cursors-b2-viewport-rings-frustums.md`](../../WorldFoundry.2026-new-level/docs/plans/2026-05-31-shared-cursors-b2-viewport-rings-frustums.md). The umbrella plan covers the design; this file is the per-turn staging layer. The hook will migrate to `docs/plans/2026-05-31-shared-cursors-b-leftovers-jump-to-view.md`.

## Context

b1 and b2 of §B shipped (presence camera-pose payload + sidebar tiles + viewport rings + camera frustums). Three pieces from the original plan are still open and each is small enough to land in one session:

- **(1) Jump-to-view button.** Each remote peer's sidebar tile already reserves the slot; the button itself is unwritten because the camera-mutation API turned out to fight `CamShot` — `movecam.cc:192` writes `Camera::SetCameraMatrix(...)` every CamShot tick, so a naive one-shot write is overwritten next frame. The clean fix is a small CamShot-suppress flag the editor flips while an override is active.
- **(2) Two-editor live verification.** b2's screenshot uses `WF_EDIT_FAKE_PEER` to prove the rendering path — but the full network path (`relay → CH_PRESENCE → parse → render`) hasn't been visually confirmed since b1 + b2 landed. A small headless smoke that spins up local `wf-relay` + two `wf-edit` instances against `ws://127.0.0.1` with distinct `XDG_CONFIG_HOME` and screenshots one of them is the proof.
- **(3) Display-name input UI.** b1 plumbed `identity.display_name` through to the broadcast (with a `peer_id`-prefix fallback when the user keeps the default `"Editor"`), but there's no in-editor way to change it. A one-line `ImGui::InputText` in the existing `Collaborate` menu and an `Apply` button that writes back to `identity.json` via the existing `SaveIdentity` helper.

Item (4) from the leftovers list — `WF_EDIT_FAKE_PEER` cleanup — defers to TODO.md as a judgement call; the env-gated injection costs nothing at runtime and is genuinely useful as a dev/screenshot aid.

## (1) Jump-to-view (~1 h)

### Engine change — CamShot-suppress flag (~5 lines)

A static-storage atomic boolean owned by the editor; checked by the CamShot per-frame tick. Implementing in `wfsource/source/game/movecam.cc` keeps it inside the engine TU (no header pollution).

- Add a private file-scope `std::atomic<bool> g_editor_cam_override{false};` at top of `movecam.cc`.
- Expose two free functions through a tiny header in `engine/mutation/wfmut.hpp` (`wfmut` is already the editor↔engine mutation API per [`project_engine_mutation_api`-style memory and the wfmut headers]):
  ```cpp
  // engine/mutation/wfmut.hpp
  void SetEditorCameraOverride(bool active);
  // (Reads: just access the atomic from the editor side.)
  ```
- At the top of the `MoveCamera`-style function in `movecam.cc` (where the existing `camera->SetCameraMatrix(mat)` lives), wrap the write:
  ```cpp
  if (!g_editor_cam_override.load()) {
      camera->SetCameraMatrix(mat);
      pa.SetPosition(destCam.position);
  }
  ```
  i.e. skip both the matrix and the position writes when the override is on; the editor takes responsibility for setting them itself.

This is engine code, not editor — but it's a 5-line guard, no new behaviour for the game build (the override is a no-op unless explicitly turned on by the editor).

### Editor change — `wfedit::SetEditorCameraPose` + Jump-to-view click

In `engine/wf_edit/gizmo.cc` (already has the engine headers cleanly):

```cpp
bool SetEditorCameraPose(const float pos[3], const float fwd[3], const float up[3])
{
    if (!theLevel || !theLevel->camera()) return false;
    // Build Matrix34 from rows: fwd (row 0), right = fwd×up (row 1), up (row 2), pos (row 3).
    // Same convention BuildViewProj / GetCameraPoseWS use.
    Vector3 v_fwd(fwd[0], fwd[1], fwd[2]);
    Vector3 v_up (up [0], up [1], up [2]);
    Vector3 v_right = Cross(v_fwd, v_up);  // or equivalent in WF's math lib
    Vector3 v_pos(pos[0], pos[1], pos[2]);
    Matrix34 m;
    m[0] = v_fwd; m[1] = v_right; m[2] = v_up; m[3] = v_pos;
    theLevel->camera()->SetCameraMatrix(m);
    return true;
}
```

Declared in `gizmo.h` next to the existing `GetCameraPoseWS` (same float-only API shape, same header-pollution constraint).

In `engine/wf_edit/main.cc` at the per-peer sidebar tile (where the b1 tile was added), add:

```cpp
ImGui::SameLine();
if (ps.has_cam && ImGui::SmallButton("Jump")) {
    if (wfedit::SetEditorCameraPose(ps.cam_pos, ps.cam_fwd, ps.cam_up))
        wfmut::SetEditorCameraOverride(true);
}
```

A second small button next to the `Jump` per-peer button, somewhere above the peer list (e.g. on the "you" tile): **`Follow CamShot`** that calls `wfmut::SetEditorCameraOverride(false)` to release the override and resume the level's authored camera. Pairs naturally with the per-peer Jump.

### Two unknowns to confirm during implementation

- Whether `MoveCamera`'s caller does anything else with the camera matrix outside the function (e.g. compute frustum planes, occlusion culling) that would now be stale when override is on. Quick read of `movecam.cc` callers + a smoke confirms.
- Whether `Vector3 Cross(...)` is the actual name in WF's math headers; otherwise inline the cross-product.

## (2) Two-editor live verification (~½ h)

### Headless smoke recipe — `task wf-edit-two-peer-smoke` or shell script

A new `tests/screenshot_two_peer_b2.sh` (mirroring `tests/screenshot_qbert_enemies.py`'s shape but as a shell script since wf-edit doesn't run under pytest's `BridgeClient` fixture):

```sh
#!/usr/bin/env bash
set -euo pipefail
ROOM=b2-smoke-$$
PORT=9991
ROOT=$(git rev-parse --show-toplevel)
LEVEL=$ROOT/wflevels/qbert_practice/qbert_practice.iff
RELAY=$ROOT/wftools/wf_collab/target/release/wf-relay
WFEDIT=$ROOT/build-editor/wf-edit

# Build the relay if absent.
[ -x "$RELAY" ] || cargo build --release --bin wf-relay \
    --manifest-path "$ROOT/wftools/wf_collab/Cargo.toml"

# Start relay on loopback.
"$RELAY" --port $PORT >/tmp/b2-relay.log 2>&1 &
RELAY_PID=$!
trap 'kill $RELAY_PID $A_PID $B_PID 2>/dev/null || true' EXIT

# Instance A — Alice, selects an actor, will be the "watched" peer.
XDG_CONFIG_HOME=/tmp/b2-alice DISPLAY=:0 \
    "$WFEDIT" --relay=ws://127.0.0.1:$PORT --room=$ROOM --frames 240 \
    --screenshot $ROOT/tests/screenshots/wfedit_shared_cursors_b2_live_A.ppm \
    "$LEVEL" >/tmp/b2-A.log 2>&1 &
A_PID=$!

# Instance B — Bob, captures Alice's frustum + ring.
XDG_CONFIG_HOME=/tmp/b2-bob DISPLAY=:0 \
    "$WFEDIT" --relay=ws://127.0.0.1:$PORT --room=$ROOM --frames 240 \
    --screenshot $ROOT/tests/screenshots/wfedit_shared_cursors_b2_live_B.ppm \
    "$LEVEL" >/tmp/b2-B.log 2>&1 &
B_PID=$!

wait $A_PID $B_PID
for p in tests/screenshots/wfedit_shared_cursors_b2_live_{A,B}.ppm; do
    ffmpeg -y -i "$p" "${p%.ppm}.png" >/dev/null 2>&1 && rm -f "$p"
done
ls -la tests/screenshots/wfedit_shared_cursors_b2_live_*.png
```

If B's screenshot shows Alice's orange wireframe frustum overlaying the qbert pyramid, the network path is verified end to end. Replaces the fake-peer screenshot as the canonical b2 proof; both can stay.

### Auto-bind first-actor selection

For the screenshots to actually demonstrate the ring, A needs to *have* an actor selected when B's screenshot fires. Currently the editor starts with `selected = -1`. Two ways to force it:

- Add a `WF_EDIT_AUTO_SELECT=0` env var: if set, default `c->selected` to that index at startup. Two lines in main.cc near where `selected` is initialised.
- Have the smoke script send a select message through the relay — far more involved, defer.

The env-var path keeps the test scriptable and adds a tiny dev tool. Same shape as `WF_EDIT_FAKE_PEER`.

## (3) Display-name input UI (~15 min)

Inside the existing `if (ImGui::BeginMenu("Collaborate"))` block in `engine/wf_edit/main.cc:1582`, add a child menu or in-place item:

```cpp
ImGui::Separator();
ImGui::Text("Display name");
ImGui::SameLine();
static char buf[64] = {};
static bool init = false;
if (!init) { std::strncpy(buf, c->display_name.c_str(), sizeof(buf)-1); init = true; }
if (ImGui::InputText("##displayname", buf, sizeof(buf), ImGuiInputTextFlags_EnterReturnsTrue)) {
    c->display_name = buf;
    // Persist back to identity.json via the existing SaveIdentity helper.
    // Need to either (a) carry the identity ref through EditorCtx, or
    // (b) re-load identity from disk, mutate display_name, save.
    // (a) is cleaner; (b) is one less moving part. Confirm at impl.
}
```

The fallback (when display_name == "Editor" we substitute `Editor (<peer_id 6 prefix>)`) shipped in b1 stays — applies to the broadcast at connect time, so changing display_name and reconnecting picks up the new value, but live changes during a session need a small re-eval on each broadcast (cheap: redo the substitution inline in the broadcast block).

## Out of scope (deferred to TODO)

- **(4) `WF_EDIT_FAKE_PEER` cleanup decision.** Stays as a documented dev/screenshot aid; tracked as a TODO row for future cleanup pass if it becomes noise.
- Yrs Awareness via yffi.
- Hovered-actor signal.
- Screen share, dedicated Peers panel.

## Critical files

- `wfsource/source/game/movecam.cc` — add the `g_editor_cam_override` guard around `camera->SetCameraMatrix` (~5 lines).
- `engine/mutation/wfmut.hpp` + `engine/mutation/wfmut.cpp` — expose `SetEditorCameraOverride(bool)`.
- `engine/wf_edit/gizmo.cc` + `gizmo.h` — add `SetEditorCameraPose(float pos[3], float fwd[3], float up[3])` (mirror of `GetCameraPoseWS`).
- `engine/wf_edit/main.cc` — Jump-to-view button per peer tile + `Follow CamShot` release button + display-name `Collaborate` menu input + optional `WF_EDIT_AUTO_SELECT` env hook.
- `tests/screenshot_two_peer_b2.sh` (new) — live two-editor verification script.
- `Taskfile.yml` — new `task wf-edit-two-peer-smoke` wrapping the script.
- `tests/screenshots/wfedit_shared_cursors_b2_live_*.png` (new) — proof screenshots.
- `wf-status.md` — one-sentence history row.
- `TODO.md` — `WF_EDIT_FAKE_PEER` cleanup row.

## Verification

- **Engine no-op:** `task build` (`wf_game` Debug + Release) passes; existing CamShot tests / snowgoons play unchanged when `g_editor_cam_override` is false (its default). Confirm with the existing snowgoons / qbert smoke.
- **Editor build:** `task build-wf-edit` → `✓ wf-edit built`.
- **Solo smoke:** WF_EDIT_FAKE_PEER screenshot still works exactly as in b2 (the override path is opt-in and never engaged in solo).
- **Two-editor live:** `bash tests/screenshot_two_peer_b2.sh` produces two PNGs; B's PNG shows Alice's orange frustum + selection ring on Alice's selected actor. Ship that PNG as the canonical b2 proof.
- **Jump-to-view:** click Jump on a peer tile → local cam snaps to peer's pose AND stays there even as time advances (CamShot is suppressed). Click `Follow CamShot` → cam returns to authored camera.
- **Display name:** type a name into `Collaborate → Display name`, hit Enter, observe `name` field on the broadcast change (`b2-B.log` shows the next 0x02 frame with the new name); restart the editor and confirm the name persisted to `identity.json`.
- **Backwards compat:** a b1-vintage peer joining the room with `Follow CamShot` mode + display name from old default still shows up correctly; b2 peers without a Jump button (older binary) still produce frustums for newer viewers.

## Notes

- Sizing, *average-programmer scale*: (1) ~1 h, (2) ~½ h, (3) ~15 min. Total ~2 h.
- (1)'s engine change is the only piece that touches the game runtime path. Keeping the guard inside `movecam.cc` (vs a header field on `Camera`) means zero impact when override is off.
- The Jump-to-view UX choice: pose snap-jump (one-shot) vs follow-peer-live (re-applied each frame as their broadcast updates). One-shot is simpler and more predictable; the user picks up live tracking later if it turns out to be the right interaction. Default: one-shot.
- Two-editor screenshot landing alongside the commit closes the visual-proof gap b2 left open, per `feedback_screenshots_for_proof`.
