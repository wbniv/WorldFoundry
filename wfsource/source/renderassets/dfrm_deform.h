//============================================================================
// dfrm_deform.h: the DFRM v1 mesh chunk.
//
// A rooted curve (a chain of rigid samples, one per tail ring) with clip
// playback, an additive Hermite knot layer and a holdfast wrap, plus weighted
// transforms (head, eyes). Plain C++17, no engine types, so tests can drive it
// on a vertex array directly. docs/plans/2026-10-16-saltwater-seahorses.md,
// Phase 1 E1-E5; the reference maths is wflevels/aquarium_tanks/dfrm_ref.py.
//
// Chunk layout (little-endian, 4-byte aligned; positions and lengths 16.16
// fixed in model units, angles int16 centidegrees):
//   header     32 B  u32 version(1) flags(0) curves samples transforms
//                    influences clips frames
//   curve      52 B  i32 root[3] d[3] v[3]; u16 firstSample sampleCount;
//                    u8 knotCount, pad[3]; u8 knots[8]   (s = v x d)
//   sample     16 B  i32 length halfWidth; i16 ventral dorsal lateral twist
//   transform  28 B  i32 pivot[3] axis[3]; i16 lo hi
//   influence  16 B  u8 kind(0 none, 1 sample, 2 transform) pad; u16 index;
//                    i32 a b c: sample -> offset along the sample's rest
//                    (d, v, s); transform -> a = weight (0..1)
//   clip       16 B  u32 nameHash; u16 fps frameCount flags(bit0 loop) pad;
//                    u32 firstFrame
//   frames           i16 per frame: per sample (flex, lateral, twist), then
//                    one per transform; the table is padded to 4 bytes
//
// Control block (40 cells, E3): 0-20 seven knots x (flex, lateral, twist) deg,
// additive; 21-24 wrap mode (0 off, 1 horizontal, 2 vertical), start sample,
// holdfast radius (model units), progress 0-1; 25-29 clip A id, clip A start
// (level s), clip B id, clip B start, fade time (s); 30-32 transform angles
// (head pitch, eye L yaw, eye R yaw) deg, added to the clips'. Outputs, written
// by the caller: 33-35 wrap centre, 36-38 tail tip (model units), 39 status.
// A clip id is its 1-based index in the clip table; 0 or unknown = no clip.
//============================================================================
#ifndef WF_DFRM_DEFORM_H
#define WF_DFRM_DEFORM_H

#include <cstddef>
#include <cstdint>
#include <vector>

namespace wf_render {

enum : int {
    DfrmVersion = 1,
    DfrmBlockSize = 40, DfrmInputCount = 33,
    DfrmMaxSamples = 64, DfrmMaxKnots = 7, DfrmMaxTransforms = 3,
    DfrmOutWrap = 33, DfrmOutTip = 36, DfrmOutStatus = 39,
};
enum DfrmInfluenceKind : uint8_t { DfrmNone = 0, DfrmOnSample = 1, DfrmOnTransform = 2 };
// Same values as DeformStatus (mesh_deformer.h).
enum DfrmStatus : int { DfrmOk = 0, DfrmNoData = 1, DfrmClamped = 3, DfrmNotFinite = 4, DfrmBadInput = 5 };

struct DfrmCurve {
    float root[3], d[3], v[3], s[3];      // root position and orthonormal frame
    int firstSample, sampleCount, knotCount;
    int knots[8];                         // curve-local sample indices
};
struct DfrmSample { float length, halfWidth, ventral, dorsal, lateral, twist; };   // limits in degrees
struct DfrmTransform { float pivot[3], axis[3], lo, hi; };                         // degrees
struct DfrmInfluence { uint8_t kind; uint16_t index; float a, b, c; };
struct DfrmClip { uint32_t nameHash; float fps; int frameCount; bool loop; int firstFrame; };

struct DfrmData {
    std::vector<DfrmCurve> curves;
    std::vector<DfrmSample> samples;
    std::vector<DfrmTransform> transforms;
    std::vector<DfrmInfluence> influences;
    std::vector<DfrmClip> clips;
    std::vector<int16_t> frames;          // frameCount x frameStride
    int frameStride = 0;                  // 3 x samples + transforms
};

// Validates everything; on failure returns false, leaves out untouched and
// sets reason. v1 accepts exactly one curve (the block drives one curve).
bool ParseDfrm(const void* bytes, size_t size, int vertexCount, DfrmData& out, const char*& reason);

} // namespace wf_render

#endif
