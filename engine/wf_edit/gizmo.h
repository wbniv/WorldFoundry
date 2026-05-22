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

}  // namespace wfedit
