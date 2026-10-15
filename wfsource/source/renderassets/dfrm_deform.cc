//============================================================================
// dfrm_deform.cc: DFRM v1 loader. See dfrm_deform.h for the
// chunk layout and the control block; wflevels/aquarium_tanks/dfrm_ref.py is
// the reference the dfrm_strand test compares against.
//============================================================================
#include <renderassets/dfrm_deform.h>

#include <algorithm>
#include <cmath>
#include <cstring>

namespace wf_render {

namespace {


struct Reader {
    const uint8_t* p; size_t left; bool ok = true;
    template <class T> T get() {
        T v{};
        if (left < sizeof(T)) { ok = false; return v; }
        std::memcpy(&v, p, sizeof(T)); p += sizeof(T); left -= sizeof(T);   // little-endian targets only
        return v;
    }
    float fixed() { return float(get<int32_t>()) / 65536.f; }
    float centi() { return float(get<int16_t>()) * .01f; }
};

inline float Dot(const float* a, const float* b) { return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]; }
inline void Cross(const float* a, const float* b, float* out)
{
    out[0] = a[1]*b[2] - a[2]*b[1]; out[1] = a[2]*b[0] - a[0]*b[2]; out[2] = a[0]*b[1] - a[1]*b[0];
}
inline bool Normalize(float* a)
{
    const float n = std::sqrt(Dot(a, a));
    if (!(n > 1e-12f)) return false;
    a[0] /= n; a[1] /= n; a[2] /= n;
    return true;
}
// Gram-Schmidt on (d, v); s = v x d, the handedness of the root frame.
inline void Orthonormalize(float* d, float* v, float* s)
{
    Normalize(d);
    const float dv = Dot(v, d);
    for (int k = 0; k < 3; ++k) v[k] -= dv * d[k];
    Normalize(v);
    Cross(v, d, s);
}

} // namespace

//----------------------------------------------------------------------------

bool ParseDfrm(const void* bytes, size_t size, int vertexCount, DfrmData& out, const char*& reason)
{
    Reader r{static_cast<const uint8_t*>(bytes), size};
    const uint32_t version = r.get<uint32_t>(), flags = r.get<uint32_t>();
    const uint32_t nCurves = r.get<uint32_t>(), nSamples = r.get<uint32_t>(), nTransforms = r.get<uint32_t>();
    const uint32_t nInfluences = r.get<uint32_t>(), nClips = r.get<uint32_t>(), nFrames = r.get<uint32_t>();
    if (!r.ok) { reason = "truncated header"; return false; }
    if (version != DfrmVersion || flags != 0) { reason = "unknown version"; return false; }
    if (nCurves != 1) { reason = "v1 needs exactly one curve"; return false; }
    if (nSamples < 1 || nSamples > DfrmMaxSamples) { reason = "sample count out of range"; return false; }
    if (nTransforms > DfrmMaxTransforms) { reason = "too many transforms"; return false; }
    if (vertexCount <= 0 || nInfluences != uint32_t(vertexCount)) { reason = "influence count != vertex count"; return false; }
    if (nClips > 65535 || nFrames > 1000000) { reason = "clip table too large"; return false; }
    const size_t stride = 3 * size_t(nSamples) + nTransforms;
    const size_t frameBytes = (2 * stride * nFrames + 3) & ~size_t(3);
    const size_t expected = 32 + 52 * size_t(nCurves) + 16 * size_t(nSamples) + 28 * size_t(nTransforms)
                          + 16 * size_t(nInfluences) + 16 * size_t(nClips) + frameBytes;
    if (size != expected) { reason = "chunk size does not match its counts"; return false; }

    DfrmData d;
    d.frameStride = int(stride);
    for (uint32_t c = 0; c < nCurves; ++c) {
        DfrmCurve curve{};
        for (float& f : curve.root) f = r.fixed();
        for (float& f : curve.d) f = r.fixed();
        for (float& f : curve.v) f = r.fixed();
        curve.firstSample = r.get<uint16_t>(); curve.sampleCount = r.get<uint16_t>();
        curve.knotCount = r.get<uint8_t>(); r.get<uint8_t>(); r.get<uint8_t>(); r.get<uint8_t>();
        for (int& k : curve.knots) k = r.get<uint8_t>();
        if (curve.firstSample != 0 || curve.sampleCount != int(nSamples)) { reason = "curve samples out of range"; return false; }
        if (curve.knotCount < 2 || curve.knotCount > DfrmMaxKnots) { reason = "knot count out of range"; return false; }
        if (curve.knots[0] != 0 || curve.knots[curve.knotCount - 1] != curve.sampleCount - 1) { reason = "knots must span the curve"; return false; }
        for (int k = 1; k < curve.knotCount; ++k)
            if (curve.knots[k] <= curve.knots[k - 1]) { reason = "knots not increasing"; return false; }
        if (!Normalize(curve.d) || !Normalize(curve.v)) { reason = "degenerate root frame"; return false; }
        if (std::fabs(Dot(curve.d, curve.v)) > .99f) { reason = "degenerate root frame"; return false; }
        Orthonormalize(curve.d, curve.v, curve.s);
        d.curves.push_back(curve);
    }
    for (uint32_t i = 0; i < nSamples; ++i) {
        DfrmSample s{};
        s.length = r.fixed(); s.halfWidth = r.fixed();
        s.ventral = r.centi(); s.dorsal = r.centi(); s.lateral = r.centi(); s.twist = r.centi();
        if (!(s.length > 0) || s.halfWidth < 0 || s.ventral < 0 || s.dorsal < 0 || s.lateral < 0 || s.twist < 0) {
            reason = "invalid sample"; return false;
        }
        d.samples.push_back(s);
    }
    for (uint32_t i = 0; i < nTransforms; ++i) {
        DfrmTransform t{};
        for (float& f : t.pivot) f = r.fixed();
        for (float& f : t.axis) f = r.fixed();
        t.lo = r.centi(); t.hi = r.centi();
        if (!Normalize(t.axis) || t.lo > t.hi) { reason = "invalid transform"; return false; }
        d.transforms.push_back(t);
    }
    for (uint32_t i = 0; i < nInfluences; ++i) {
        DfrmInfluence f{};
        f.kind = r.get<uint8_t>(); r.get<uint8_t>(); f.index = r.get<uint16_t>();
        f.a = r.fixed(); f.b = r.fixed(); f.c = r.fixed();
        const bool ok = f.kind == DfrmNone ||
            (f.kind == DfrmOnSample && f.index < nSamples) ||
            (f.kind == DfrmOnTransform && f.index < nTransforms && f.a >= 0 && f.a <= 1);
        if (!ok) { reason = "influence index out of range"; return false; }
        d.influences.push_back(f);
    }
    for (uint32_t i = 0; i < nClips; ++i) {
        DfrmClip c{};
        c.nameHash = r.get<uint32_t>(); c.fps = r.get<uint16_t>(); c.frameCount = r.get<uint16_t>();
        c.loop = (r.get<uint16_t>() & 1) != 0; r.get<uint16_t>(); c.firstFrame = int(r.get<uint32_t>());
        if (!(c.fps > 0) || c.frameCount < 1 || c.firstFrame < 0 || size_t(c.firstFrame) + c.frameCount > nFrames) {
            reason = "clip frames out of range"; return false;
        }
        d.clips.push_back(c);
    }
    d.frames.resize(stride * nFrames);
    for (int16_t& v : d.frames) v = r.get<int16_t>();
    if (!r.ok) { reason = "truncated"; return false; }
    out = std::move(d);
    reason = "";
    return true;
}

} // namespace wf_render
