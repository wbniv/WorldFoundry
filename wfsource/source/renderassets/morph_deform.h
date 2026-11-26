//============================================================================
// morph_deform.h: the MRPH mesh chunk (morph targets) and its evaluator.
//
// Up to six morph targets per mesh, each a position delta and a shade delta per
// vertex, blended by weights a script sets every frame; the evaluator also
// writes prelit vertex colours (tint x shade x glow), so a Gouraud-shaded
// prelit material shows smooth, recoloured wax. A chunk with no targets makes
// a pure tint actor (the lava lamp's liquid, glass, wall glow and table light).
// Plain C++17, no engine types, so tests drive it on arrays directly.
// docs/plans/2026-11-26-lava-lamp.md, "Engine addition E1".
//
// Chunk layout (little-endian, 4-byte aligned):
//   header   12 B  u32 version(1) targets(0..6) vertices (= the VRTX count)
//   names    16 B per target: ASCII, NUL-padded (the shape key's name after
//                  "morph_"); for tools and tests, the engine ignores it
//   position 12 B per target per vertex: i32 dx dy dz, 16.16 model units
//   shade     8 B per target per vertex: i16 dr dg db pad, 1/4096 of full
//                  scale (full scale = vertex colour byte 255)
//
// Channels (MorphChannels = 10): weights 0-5 (one per target; weights past
// the target count are ignored), tint R G B (0..1 multipliers), glow (a
// multiplier on all three). Pose:
//   position = rest + sum w_i dp_i
//   shade    = rest colour / 255 + sum w_i ds_i
//   colour   = clamp(round(255 x tint x shade x glow), 0, 255) per channel
//============================================================================
#ifndef WF_MORPH_DEFORM_H
#define WF_MORPH_DEFORM_H

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace wf_render {

const int MorphVersion = 1;
const int MorphMaxTargets = 6;
const int MorphChannels = 10;            // six weights, tint R G B, glow
const int MorphMaxVertices = 32767;
const float MorphShadeUnit = 1.0f / 4096.0f;

struct MorphTarget {
    std::string name;
    std::vector<float> position;         // 3 per vertex, model units
    std::vector<float> shade;            // 3 per vertex, 1.0 = colour byte 255
};

struct MorphData {
    int vertexCount = 0;
    std::vector<MorphTarget> targets;
};

// Parses an MRPH payload. False (with a reason) for a bad version, a target
// count above six, a vertex count that differs from the mesh's, a size that
// does not match, or a non-zero pad.
bool ParseMorph(const uint8_t* bytes, size_t size, int vertexCount, MorphData& out, const char*& reason);

class MorphEvaluator {
public:
    // rest: 3 floats per vertex; colours: 3 bytes (R G B) per vertex.
    bool Bind(const MorphData& data, const float* rest, const uint8_t* colours, int vertexCount);
    // channels: MorphChannels values (the caller has checked they are finite).
    // Writes Positions() (unchanged when there are no targets) and Colours().
    void Evaluate(const float* channels);
    bool MovesVertices() const { return _data && !_data->targets.empty(); }
    const std::vector<float>& Positions() const { return _positions; }
    const std::vector<uint8_t>& Colours() const { return _colours; }
private:
    const MorphData* _data = nullptr;
    int _count = 0;
    std::vector<float> _rest, _restShade, _positions;
    std::vector<uint8_t> _colours;
};

} // namespace wf_render

#endif
