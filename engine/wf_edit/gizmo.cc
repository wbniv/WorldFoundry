// gizmo.cc — viewport translate/rotate gizmo support for wf-edit.
//
// Reconstructs the engine's exact view + projection editor-side so ImGuizmo
// projects to the same pixels the engine renders — no engine change. The
// reconstruction is provably the engine's own proj*view*model math (see
// docs/plans/2026-05-22-viewport-gizmo.md). Lives in its own TU to keep the
// engine math headers out of main.cc, mirroring engine_bridge.cc.

#include "gizmo.h"

#include "level_doc.h"      // ReadActorFields, WriteFieldLeaf
#include "wfmut.hpp"        // wfmut::GetActorPos / SetActorPos / *Orientation
#include "wfcrdt.hpp"       // wfcrdt::Doc

#include <game/level.hp>    // Level, theLevel, camera()
#include <game/camera.hp>   // Camera::GetRenderCamera
#include <game/actor.hp>    // pulls in Vector3 / Scalar
#include <gfx/camera.hp>    // RenderCamera::GetPosition
#include <math/matrix34.hp> // Matrix34
#include <math/euler.hp>    // Euler
#include <math/angle.hp>    // Angle::AsRadian

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <optional>

extern Level* theLevel;

namespace {

// ── GL float[16] <-> WF Matrix34 ──────────────────────────────────────────────
// Source of truth: wfsource/source/gfx/glpipeline/backend_modern.cc:159-180
// (Matrix34ToFloat16 — file-static there, so duplicated verbatim). WF stores a
// row-major 4x3 (rows 0-2 = rotation, row 3 = translation); GL wants a
// column-major 4x4, hence the transpose.
void Matrix34ToGL(const Matrix34& m, float out[16])
{
    out[0]  = m[0][0].AsFloat(); out[1]  = m[0][1].AsFloat(); out[2]  = m[0][2].AsFloat(); out[3]  = 0.0f;
    out[4]  = m[1][0].AsFloat(); out[5]  = m[1][1].AsFloat(); out[6]  = m[1][2].AsFloat(); out[7]  = 0.0f;
    out[8]  = m[2][0].AsFloat(); out[9]  = m[2][1].AsFloat(); out[10] = m[2][2].AsFloat(); out[11] = 0.0f;
    out[12] = m[3][0].AsFloat(); out[13] = m[3][1].AsFloat(); out[14] = m[3][2].AsFloat(); out[15] = 1.0f;
}

// Exact inverse of Matrix34ToGL: GL column-major 4x4 -> WF row-major 4x3 (drops
// the homogeneous row).
Matrix34 GLToMatrix34(const float in[16])
{
    Matrix34 m;
    m[0] = Vector3(Scalar::FromFloat(in[0]),  Scalar::FromFloat(in[1]),  Scalar::FromFloat(in[2]));
    m[1] = Vector3(Scalar::FromFloat(in[4]),  Scalar::FromFloat(in[5]),  Scalar::FromFloat(in[6]));
    m[2] = Vector3(Scalar::FromFloat(in[8]),  Scalar::FromFloat(in[9]),  Scalar::FromFloat(in[10]));
    m[3] = Vector3(Scalar::FromFloat(in[12]), Scalar::FromFloat(in[13]), Scalar::FromFloat(in[14]));
    return m;
}

// Source of truth: backend_modern.cc:135-145 (Mat4Perspective — file-static).
void Mat4PerspectiveGL(float fovDegY, float aspect, float nz, float fz, float out[16])
{
    const float f = 1.0f / std::tan((fovDegY * 0.5f) * (3.14159265358979323846f / 180.0f));
    for (int i = 0; i < 16; ++i) out[i] = 0.0f;
    out[0]  = f / aspect;
    out[5]  = f;
    out[10] = (fz + nz) / (nz - fz);
    out[11] = -1.0f;
    out[14] = (2.0f * fz * nz) / (nz - fz);
}

}  // namespace

namespace wfedit {

GizmoMats BuildGizmoMats(int engine_idx, float fbw, float fbh)
{
    GizmoMats g;
    if (!theLevel || !theLevel->camera() || engine_idx < 1 || fbh <= 0.0f)
        return g;  // valid stays false

    // VIEW = inverse of the camera's world transform (the engine's
    // _invertedPosition; camera.cc:206 does exactly this then feeds it through
    // Matrix34ToFloat16).
    const Matrix34& camWorld = theLevel->camera()->GetRenderCamera().GetPosition();
    Matrix34 inv;
    inv.Inverse(camWorld);
    Matrix34ToGL(inv, g.view);

    // PROJECTION — the exact params the editor sets on resize (main.cc
    // RendererBackendGet().SetProjection(60, fbw/fbh, 1, 1000)).
    Mat4PerspectiveGL(60.0f, fbw / fbh, 1.0f, 1000.0f, g.proj);

    // MODEL — actor world transform (rotation + translation) so the rotate rings
    // display at the actor's current orientation.
    std::optional<Vector3> pos = wfmut::GetActorPos(*theLevel, engine_idx);
    if (!pos) return g;
    std::optional<Euler> ori = wfmut::GetActorOrientation(*theLevel, engine_idx);
    Matrix34 model(ori ? *ori : Euler(), *pos);
    Matrix34ToGL(model, g.model);

    if (std::getenv("WF_EDIT_GIZMO_DEBUG")) {
        static bool once = false;
        if (!once) {
            once = true;
            std::fprintf(stderr,
                "[gizmo] view t=(%.3f %.3f %.3f)  proj[f/asp=%.3f f=%.3f z=%.4f w=%.0f]  "
                "model pos=(%.3f %.3f %.3f)\n",
                g.view[12], g.view[13], g.view[14],
                g.proj[0], g.proj[5], g.proj[10], g.proj[11],
                g.model[12], g.model[13], g.model[14]);
        }
    }

    g.valid = true;
    return g;
}

void ApplyGizmoToEngine(int engine_idx, const float model_gl[16])
{
    if (!theLevel || engine_idx < 1) return;
    Matrix34 m = GLToMatrix34(model_gl);
    wfmut::SetActorPos(*theLevel, engine_idx, m[3]);          // translation = row 3
    wfmut::SetActorOrientation(*theLevel, engine_idx, m.AsEuler());  // WF's own extraction
}

void CommitGizmoToDoc(wfcrdt::Doc& doc, int doc_index, const float model_gl[16])
{
    Matrix34 m = GLToMatrix34(model_gl);
    const Vector3& t = m[3];
    Euler e = m.AsEuler();

    int posChild = -1, oriChild = -1;
    for (const auto& af : ReadActorFields(doc, doc_index)) {
        if      (af.name == "Position")    posChild = af.child_index;
        else if (af.name == "Orientation") oriChild = af.child_index;
    }

    char buf[96];
    if (posChild >= 0) {
        std::snprintf(buf, sizeof buf, "%.6f %.6f %.6f",
                      t.X().AsFloat(), t.Y().AsFloat(), t.Z().AsFloat());
        WriteFieldLeaf(doc, doc_index, posChild, "DATA", buf);
    }
    if (oriChild >= 0) {
        // .lev EULR DATA is RADIANS (levcomp-rs radians_fx_to_u16_revs).
        std::snprintf(buf, sizeof buf, "%.6f %.6f %.6f",
                      e.GetA().AsRadian().AsFloat(),
                      e.GetB().AsRadian().AsFloat(),
                      e.GetC().AsRadian().AsFloat());
        WriteFieldLeaf(doc, doc_index, oriChild, "DATA", buf);
    }
}

}  // namespace wfedit
