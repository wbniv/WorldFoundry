# Plan — Shared cursors b2: viewport selection rings + camera frustums

**Date:** 2026-05-31
**Status:** Planned (not started)
**Parent:** §B of [A-E-B plan](2026-05-30-a-e-b-audit-follow-up-mailbox-999-fix-shared-curso.md)
**Predecessor commit:** [`39ebb708`](.) — b1 (presence camera-pose payload + sidebar tiles)

## Context

§B of the [A-E-B plan](2026-05-30-a-e-b-audit-follow-up-mailbox-999-fix-shared-curso.md) was split into two commits to stay reviewable.

**b1 shipped** as `39ebb708`: extended the CH_PRESENCE (0x02) JSON payload to carry each peer's camera pose (`cam_pos` / `cam_fwd` / `cam_up`), wired `identity.display_name` into the broadcast with a peer-id fallback, and replaced the chat sidebar's coloured presence dots with per-peer tiles showing each peer's selected actor and camera position. The payload flows but nothing is drawn in the 3D viewport yet, so b1 alone is a tiles-only refactor.

**b2 is the visible payoff:** render every remote peer's cursor data in the 3D viewport — a coloured ring on the actor they have selected and a small wireframe pyramid showing their camera frustum — plus a "Jump to view" button on each peer tile that teleports the local editor camera to the peer's pose. This turns "we know where everyone is" into "we can see where everyone is."

## State entering this plan

- [`engine/wf_edit/gizmo.h`](../../engine/wf_edit/gizmo.h) already declares two helpers b2 needs (`BuildViewProj`, `GetActorWorldPos`) — added late in the b1 turn but with no implementations yet. Build is currently green only because nothing calls them.
- `engine/wf_edit/gizmo.cc` + `engine/wf_edit/main.cc` — untouched for b2 since b1 landed.
- Build target: `task build-wf-edit` (Debug, ASan-on by default).

## Critical changes

### 1) [`engine/wf_edit/gizmo.cc`](../../engine/wf_edit/gizmo.cc) — implement the two stranded helpers (~30 lines)

- `BuildViewProj(fbw, fbh, view, proj)` — refactor of `BuildGizmoMats`'s top half: same `inv(camera_world)` view and `Mat4PerspectiveGL(60, fbw/fbh, 1, 1000)` projection it already produces, but without needing an actor model. Returns `false` if no live level/camera (caller skips drawing). Factor `BuildGizmoMats` to call this internally so the math has one home.
- `GetActorWorldPos(engine_idx, out_xyz)` — thin wrapper around `wfmut::GetActorPos(*theLevel, engine_idx)` returning a `float[3]`. Returns `false` if no actor found.

### 2) [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) — peer-overlay render pass (~80 lines)

Add a static free function called from the main frame, after the existing `BuildGizmoMats` call site and before the panels are drawn:

```cpp
static void RenderPeerOverlay(EditorCtx* c, float fbw, float fbh);
```

Inside:

- Call `wfedit::BuildViewProj(fbw, fbh, view, proj)` once. Bail if `false`.
- Per-frame EID → engine_idx map built from `c->actor_eids[i]` + `wfedit::DocActorToEngineIdx(i)` (already in [`engine/wf_edit/engine_bridge.h`](../../engine/wf_edit/engine_bridge.h)).
- For each remote peer `(pid, ps)`:
  - **Selection ring** when `ps.selected_eid` matches a live actor: world-pos via `GetActorWorldPos`; project to screen with a small local `world_to_screen(view, proj, fbw, fbh, world_xyz, &x, &y)` helper; draw a 12-px outline circle via `ImGui::GetForegroundDrawList()->AddCircle()` in the peer's `ps.colour`.
  - **Camera frustum** when `ps.has_cam`: build 5 world-space vertices — apex at `cam_pos`, four far-plane corners at `cam_pos + cam_fwd*8 ± cam_right*3 ± cam_up*3` where `cam_right = cross(cam_fwd, cam_up)`. Project each. Draw 4 apex→corner lines plus 4 closing corner→corner lines on the foreground drawlist. Skip the whole frustum if all 5 corners project behind the near plane.
- Pure no-op when no remote peers or no cam data.

The single new world-to-screen helper at the top of the function:

```cpp
// clip = proj * view * world(.,.,.,1); ndc = clip.xyz/clip.w; screen pixels w/ top-left origin
static bool world_to_screen(const float v[16], const float p[16],
                            float fbw, float fbh,
                            const float w[3], float* sx, float* sy);
```

Returns `false` if the point is behind the near plane (`clip.w <= 0`).

### 3) Wire the call into the frame loop

Find the existing `BuildGizmoMats(...)` invocation in `WfEditFrameSimple` (around the gizmo handle drawing, near `ImGuizmo::BeginFrame`) and add `RenderPeerOverlay(c, fbw, fbh)` immediately after — before any panel `ImGui::Begin` blocks. Same `ImGui::GetForegroundDrawList()` ImGuizmo uses; no extra overlay setup needed.

### 4) "Jump to view" button — defer if camera mutation is non-trivial

Per b1's sidebar tiles, each remote peer tile has space for a `Jump to view` `ImGui::SmallButton`. Implementation needs a way to *write* the editor's camera pose. Quick check during b2: if `wfmut` (or a similar surface) already exposes a "set camera world transform" path that doesn't fight CamShot, wire the button to it. If the camera-mutation API is not in place, leave the button out of this commit and file a TODO — the rings + frustums alone deliver the visible value.

## Out of scope (confirmed deferrals)

- Yrs Awareness via yffi (see §B umbrella plan).
- Hovered-actor signaling (lighter than selection).
- Multi-peer voice/video, screen share.
- A dedicated `Peers` panel — the upgraded Chat sidebar tiles already cover the per-peer roster.

## Verification

- **Build:** `task build-wf-edit` → `✓ wf-edit built` (Debug, ASan-on).
- **Headless single-instance smoke:** launch `wf-edit` on a level → no remote peers → zero rings/frustums drawn → sidebar shows only the "you" tile. Confirms the no-peer path is a true no-op (no `ImGui::GetForegroundDrawList()` overhead with `peer_presence` empty).
- **Two-editor live test:** identical recipe to b1's two-instance setup (the manual already documents distinct `XDG_CONFIG_HOME` for distinct peer ids, against the local `task quick-tunnel` URL). Move the camera in instance A and watch a moving wireframe pyramid in B's viewport at A's pose; select an actor in A and watch a coloured ring snap to that actor in B.
- **Screenshot proof** per `feedback_screenshots_for_proof`: capture B's window showing A's frustum overlay + the sidebar tile listing what A is looking at. Save under `tests/screenshots/` and link from the b2 commit body.
- **Older-peer backwards compat:** an "old" peer (running b1 or earlier) joining a room with new peers parses fine — the missing `cam_pos`/`cam_fwd`/`cam_up` leave `ps.has_cam == false` so the receiver skips the frustum draw for that peer; rings still draw if they broadcast `selected_eid`.
- **Jump-to-view (if shipped):** click on B's sidebar tile for A → B's camera teleports to A's pose; movement after that point is independent again.

## Commit shape

Single `feat(wf-edit): shared cursors b2 — viewport rings + frustums` commit covering `gizmo.cc` impls, `main.cc` overlay pass + helpers, and the screenshot. `wf-status.md` row prepended (one sentence). Memory entry for the world-to-screen helper as a reusable utility — only if a second consumer appears; otherwise the plan-doc link is the paper trail.

## Sizing

~½ day average-programmer scale. Most of the time is the world-to-screen helper getting the matrix conventions right (column-major GL, y-flip for ImGui's top-left origin) and the two-editor screenshot setup.
