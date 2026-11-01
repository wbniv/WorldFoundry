// face_normal.h: the one triangle-normal routine the deformers share.
//
// The loader's CalculateNormal winding (gfx/face.hpi): (v1-v0) x (v2-v0),
// normalised. DFRM's recomputed faces and the five species deformers both use
// it (docs/plans/2026-11-01-deformer-face-normals.md).
#ifndef WF_FACE_NORMAL_H
#define WF_FACE_NORMAL_H
#include <cmath>
namespace wf_render {
// False, with out untouched, for a degenerate triangle: the caller keeps the last normal.
inline bool TriangleNormal(const float* v0, const float* v1, const float* v2, float* out)
{
    const float a[3] = {v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]};
    const float b[3] = {v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]};
    const float n[3] = {a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]};
    const float len = std::sqrt(n[0]*n[0] + n[1]*n[1] + n[2]*n[2]);
    if (!(len > 1e-12f)) return false;
    out[0] = n[0] / len; out[1] = n[1] / len; out[2] = n[2] / len;
    return true;
}
}
#endif
