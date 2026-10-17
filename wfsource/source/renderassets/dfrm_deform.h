//============================================================================
// dfrm_deform.h: the DFRM v1 mesh chunk and its evaluator.
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
// A vertical holdfast (wrap mode 2) is world-vertical: the lead-in turns the
// tail horizontal in world space, using the actor's rotation from the caller.
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

class DfrmEvaluator {
public:
    // rest: 3 floats per vertex (the mesh as loaded). faces: 3 vertex indices
    // per face; restNormals: 3 floats per face. False if counts do not match.
    bool Bind(const DfrmData& data, const float* rest, int vertexCount,
              const int* faces, const float* restNormals, int faceCount);
    // One frame. block holds n >= DfrmInputCount cells. On DfrmOk or
    // DfrmClamped, Positions(), FaceNormals() and Outputs() hold the new pose;
    // on any other status they keep the previous one (no partial pose).
    // worldRotation: 9 floats, row i = model axis i in world (NULL = model frame).
    int Evaluate(const float* block, int n, double now, const float* worldRotation = nullptr, bool materialize = true);
    // Materialize the published pose without sampling clips or advancing state.
    bool Materialize();
    const std::vector<float>& TransformAngles() const { return _xf; }

    const std::vector<int>& FaceIndices() const { return _faces; }
    const std::vector<float>& RestPositions() const { return _rest; }
    const std::vector<float>& Positions() const { return _positions; }
    const std::vector<float>& FaceNormals() const { return _normals; }
    bool FaceNormalDriven(int face) const { return _faceMode[face] != FaceStatic; }
    const float* Outputs() const { return _outputs; }       // wrap centre xyz, tip xyz
    // Inspection for tests: the last evaluated chain.
    const std::vector<float>& Joints() const { return _joints; }   // 3 x (samples + 1)
    const std::vector<float>& Frames() const { return _frames; }   // 9 per sample: d, v, s
    const std::vector<float>& Angles() const { return _angles; }   // 3 per sample, degrees, clamped
    float RootPitch() const { return _rootPitch; }

private:
    bool PlaceVertices(const std::vector<float>& joints, const std::vector<float>& frames,
                       const std::vector<float>& xf, std::vector<float>& positions, std::vector<float>& normals);
    enum FaceMode : uint8_t { FaceStatic, FaceSample, FaceTransform, FaceRecompute };
    const DfrmData* _data = nullptr;
    std::vector<float> _rest, _positions, _restNormals, _normals;
    std::vector<int> _faces;
    std::vector<uint8_t> _faceMode;
    std::vector<uint16_t> _faceIndex;      // sample or transform of a rigid face
    std::vector<float> _faceCoeff;         // FaceSample: rest normal in the rest (d, v, s)
    std::vector<float> _joints, _frames, _angles, _xf;
    // Per-frame working buffers, sized once in Bind so Evaluate never allocates.
    // The *Next buffers are swapped with the published ones on success only.
    std::vector<float> _clipA, _clipB, _flex, _lateral, _twist;
    std::vector<float> _xfNext, _jointsNext, _framesNext, _positionsNext, _normalsNext;
    float _outputs[6] = {0, 0, 0, 0, 0, 0};
    float _rootPitch = 0;
};

// The mockup's non-uniform cubic Hermite with Catmull-Rom tangents over knot
// positions (tail-rig.html interp()). Exposed for tests.
float DfrmHermite(const int* knots, const float* values, int count, float x);

} // namespace wf_render

#endif
