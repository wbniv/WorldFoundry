// gizmo.h — viewport translate/rotate gizmo support for wf-edit.
//
// Declares the matrix-reconstruction + write-back surface consumed by main.cc's
// ImGuizmo wiring. Keeps the engine math headers (Matrix34/Euler/RenderCamera)
// confined to gizmo.cc, mirroring engine_bridge.{h,cc}.
//
// Plan: docs/plans/2026-05-22-viewport-gizmo.md
#pragma once

namespace wfcrdt { class Doc; }

namespace wfedit {

// Column-major GL float[16] matrices that align with the engine's own render
// (proj * view * model) — see the plan doc for the proof.
struct GizmoMats {
    float view[16];
    float proj[16];
    float model[16];   // selected actor's world transform (rotation + translation)
    bool  valid = false;
};

// Reconstruct the engine's exact view + projection editor-side (no engine change)
// and build the selected actor's model matrix. engine_idx is 1-based
// (wfmut::ActorIdx). valid=false if there's no live level/camera/actor.
GizmoMats BuildGizmoMats(int engine_idx, float fbw, float fbh);

// Push a manipulated GL model matrix into the LIVE engine actor (no Doc write):
// translation -> wfmut::SetActorPos, rotation (via Matrix34::AsEuler) ->
// wfmut::SetActorOrientation. For smooth per-frame drag preview.
void ApplyGizmoToEngine(int engine_idx, const float model_gl[16]);

// On drag release: write the actor's Position (VEC3) + Orientation (EULR, in
// RADIANS to match the .lev convention) Doc leaves, so the move persists on save
// and syncs to co-edit peers. doc_index is the 0-based content[] index.
void CommitGizmoToDoc(wfcrdt::Doc& doc, int doc_index, const float model_gl[16]);

// Extract the live engine camera's world pose into three float[3] vectors:
// position (row 3 of camera-world Matrix34), forward axis (row 0 — WF actor +X
// = forward), and up axis (row 2 — WF +Z = up). Returns false if there's no
// live level/camera (caller leaves the outs untouched). Float-only API so
// main.cc can call it without pulling engine headers (game/camera.hp →
// gfx/display.hp clashes with X11's `Display` typedef under
// GLFW_EXPOSE_NATIVE_X11). Used by the shared-cursors presence broadcast
// (docs/plans/2026-05-30-a-e-b-…md §B).
bool GetCameraPoseWS(float pos[3], float fwd[3], float up[3]);

// Build the editor's view + projection matrices without an actor model — the
// peer-cursor renderer calls this once per frame, then projects each peer's
// cursor data with its own ProjectToScreen calls. Same matrices BuildGizmoMats
// uses (column-major GL float[16]). Returns false if no live level/camera.
bool BuildViewProj(float fbw, float fbh, float view[16], float proj[16]);

// Get the live engine actor's world-space position. engine_idx is 1-based
// (wfmut::ActorIdx). Returns false if no actor. Float-only API for the
// peer-cursor renderer in main.cc.
bool GetActorWorldPos(int engine_idx, float out[3]);

}  // namespace wfedit
