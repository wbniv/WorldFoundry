//============================================================================
// mesh_deformer.h: one deformer slot per RenderActor3D, for every kind.
//
// Each kind (fish, fin, swim, jelly, lion, DFRM) is a MeshDeformer. An actor
// holds at most one, so exclusivity is structural: a call for a different kind
// returns OtherKindBound. The five species kinds were moved here verbatim from
// RenderActor3D; their maths stays in fish_deform.h ... lionfish_deform.h.
// See docs/plans/2026-10-16-saltwater-seahorses.md, Phase 1 E0.
//============================================================================
#ifndef WF_MESH_DEFORMER_H
#define WF_MESH_DEFORMER_H

#include <cstdint>
#include <memory>
#include <gfx/rendobj3.hp>

// Values are what scripts see (deform/deform-block return them, and DFRM
// writes them to block + 39): 0 ok, 1 no metadata, 2 another kind bound,
// 3 posed but a joint clamped, 4 non-finite input, 5 bad input.
enum class DeformKind : uint8_t { Fish = 1, Fin, Swim, Jelly, Lion, Dfrm };
enum class DeformStatus : uint8_t { Ok = 0, NoMetadata = 1, OtherKindBound = 2, Clamped = 3, NotFinite = 4, BadInput = 5 };

struct DeformTarget {                   // everything a deformer may touch
    Vertex3D* vertices; int count;      // writable list: the actor streams, as before
    RenderObject3D& object;             // metadata (LRIG, DFRM), faces and side effects (lion palette)
    double time;                        // level seconds (DFRM clip playback); 0 for the species kinds
    // The actor's world rotation, row-major, row i = model axis i in world space
    // (Matrix34 rows). DFRM's vertical-post lead-in turns the tail horizontal in
    // world space with it. NULL: the model frame is taken as the world frame.
    const float* worldRotation;
};

class MeshDeformer {
public:
    virtual ~MeshDeformer() = default;
    virtual DeformKind Kind() const = 0;
    virtual int MaxChannels() const = 0;
    // Before the vertex list is taken: channel count and input checks that
    // must not move the actor off the static path when they fail.
    virtual DeformStatus Check(const float* channels, int n) const = 0;
    // Once: rest data and weights. Channels are passed because swim's weights
    // depend on its span (min-x, max-x), which is model metadata.
    virtual DeformStatus Bind(const DeformTarget&, const float* channels, int n) = 0;
    virtual DeformStatus Pose(const DeformTarget&, const float* channels, int n) = 0;
    // Values for the caller to publish (DFRM: wrap centre, tail tip). Returns the count.
    virtual int Outputs(float* /*out*/, int /*max*/) const { return 0; }
};

std::unique_ptr<MeshDeformer> MakeDeformer(DeformKind);   // the one place a kind is registered

#endif
