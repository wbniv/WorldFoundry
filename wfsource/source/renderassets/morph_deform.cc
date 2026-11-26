//============================================================================
// morph_deform.cc: MRPH parsing and the morph evaluator (morph_deform.h).
// docs/plans/2026-11-26-lava-lamp.md, "Engine addition E1".
//============================================================================
#include <renderassets/morph_deform.h>

#include <cmath>
#include <cstring>

namespace wf_render {

namespace {

uint32_t U32(const uint8_t* p) { uint32_t v; std::memcpy(&v, p, 4); return v; }
int32_t I32(const uint8_t* p) { int32_t v; std::memcpy(&v, p, 4); return v; }
int16_t I16(const uint8_t* p) { int16_t v; std::memcpy(&v, p, 2); return v; }

} // namespace

bool ParseMorph(const uint8_t* bytes, size_t size, int vertexCount, MorphData& out, const char*& reason)
{
    reason = "";
    if (size < 12) { reason = "MRPH header is short"; return false; }
    const uint32_t version = U32(bytes), targets = U32(bytes + 4), vertices = U32(bytes + 8);
    if (version != uint32_t(MorphVersion)) { reason = "MRPH version is not 1"; return false; }
    if (targets > uint32_t(MorphMaxTargets)) { reason = "MRPH has more than six targets"; return false; }
    if (vertexCount <= 0 || vertexCount > MorphMaxVertices || vertices != uint32_t(vertexCount)) {
        reason = "MRPH vertex count differs from the mesh"; return false;
    }
    const size_t expected = 12 + size_t(targets) * (16 + size_t(vertices) * (12 + 8));
    if (size != expected) { reason = "MRPH size does not match its header"; return false; }
    MorphData data;
    data.vertexCount = vertexCount;
    data.targets.resize(targets);
    const uint8_t* p = bytes + 12;
    for (uint32_t t = 0; t < targets; ++t, p += 16) {
        char name[17] = {0};
        std::memcpy(name, p, 16);
        data.targets[t].name = name;
    }
    for (uint32_t t = 0; t < targets; ++t) {
        std::vector<float>& pos = data.targets[t].position;
        pos.resize(3 * size_t(vertices));
        for (size_t i = 0; i < 3 * size_t(vertices); ++i, p += 4) pos[i] = float(I32(p)) / 65536.0f;
    }
    for (uint32_t t = 0; t < targets; ++t) {
        std::vector<float>& shade = data.targets[t].shade;
        shade.resize(3 * size_t(vertices));
        for (uint32_t i = 0; i < vertices; ++i, p += 8) {
            if (I16(p + 6) != 0) { reason = "MRPH shade pad is not zero"; return false; }
            for (int k = 0; k < 3; ++k) shade[3 * size_t(i) + k] = float(I16(p + 2 * k)) * MorphShadeUnit;
        }
    }
    out = std::move(data);
    return true;
}

bool MorphEvaluator::Bind(const MorphData& data, const float* rest, const uint8_t* colours, int vertexCount)
{
    if (vertexCount != data.vertexCount || vertexCount <= 0) return false;
    _data = &data;
    _count = vertexCount;
    _rest.assign(rest, rest + 3 * size_t(vertexCount));
    _positions = _rest;
    _restShade.resize(3 * size_t(vertexCount));
    for (size_t i = 0; i < 3 * size_t(vertexCount); ++i) _restShade[i] = float(colours[i]) / 255.0f;
    _colours.assign(colours, colours + 3 * size_t(vertexCount));
    return true;
}

void MorphEvaluator::Evaluate(const float* c)
{
    const int targets = int(_data->targets.size());
    const size_t n = 3 * size_t(_count);
    if (targets > 0) {
        for (size_t i = 0; i < n; ++i) {
            float p = _rest[i];
            for (int t = 0; t < targets; ++t) p += c[t] * _data->targets[t].position[i];
            _positions[i] = p;
        }
    }
    const float scale[3] = {255.0f * c[6] * c[9], 255.0f * c[7] * c[9], 255.0f * c[8] * c[9]};
    for (size_t i = 0; i < n; ++i) {
        float s = _restShade[i];
        for (int t = 0; t < targets; ++t) s += c[t] * _data->targets[t].shade[i];
        float v = std::nearbyint(scale[i % 3] * s);
        if (!(v > 0.0f)) v = 0.0f;
        if (v > 255.0f) v = 255.0f;
        _colours[i] = uint8_t(v);
    }
}

} // namespace wf_render
