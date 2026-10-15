//============================================================================
// dfrm_deform.cc: DFRM v1 loader and evaluator. See dfrm_deform.h for the
// chunk layout and the control block; wflevels/aquarium_tanks/dfrm_ref.py is
// the reference the dfrm_strand test compares against.
//============================================================================
#include <renderassets/dfrm_deform.h>

#include <algorithm>
#include <cmath>
#include <cstring>

namespace wf_render {

namespace {

const float kDegToRad = 0.01745329251994329577f;

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
// Rotate the pair (a, c) in its plane: a toward c by angle (tail-rig.html rot()).
inline void Rot(float* a, float* c, float angle)
{
    const float C = std::cos(angle), S = std::sin(angle);
    for (int k = 0; k < 3; ++k) {
        const float na = a[k]*C + c[k]*S, nc = c[k]*C - a[k]*S;
        a[k] = na; c[k] = nc;
    }
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
// Rodrigues: rotate x about unit axis by angle.
inline void Rotate(const float* axis, float angle, const float* x, float* out)
{
    const float C = std::cos(angle), S = std::sin(angle), dot = Dot(axis, x);
    float ax[3]; Cross(axis, x, ax);
    for (int k = 0; k < 3; ++k) out[k] = x[k]*C + ax[k]*S + axis[k]*dot*(1 - C);
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

//----------------------------------------------------------------------------

float DfrmHermite(const int* KN, const float* vals, int count, float x)
{
    int k = 0;
    while (k < count - 2 && x > KN[k + 1]) k++;
    auto m = [&](int j) {
        if (j <= 0) return (vals[1] - vals[0]) / float(KN[1] - KN[0]);
        if (j >= count - 1) return (vals[j] - vals[j - 1]) / float(KN[j] - KN[j - 1]);
        return (vals[j + 1] - vals[j - 1]) / float(KN[j + 1] - KN[j - 1]);
    };
    const float x0 = float(KN[k]), x1 = float(KN[k + 1]), y0 = vals[k], y1 = vals[k + 1];
    const float h = x1 - x0, s = (x - x0) / h, s2 = s * s, s3 = s2 * s;
    return (2*s3 - 3*s2 + 1)*y0 + (s3 - 2*s2 + s)*h*m(k) + (-2*s3 + 3*s2)*y1 + (s3 - s2)*h*m(k + 1);
}

//----------------------------------------------------------------------------

bool DfrmEvaluator::Bind(const DfrmData& data, const float* rest, int vertexCount,
                         const int* faces, const float* restNormals, int faceCount)
{
    if (data.curves.size() != 1 || int(data.influences.size()) != vertexCount || faceCount < 0) return false;
    _data = &data;
    _rest.assign(rest, rest + 3 * size_t(vertexCount));
    _positions = _rest;
    _faces.assign(faces, faces + 3 * size_t(faceCount));
    _restNormals.assign(restNormals, restNormals + 3 * size_t(faceCount));
    _normals = _restNormals;
    _faceMode.assign(faceCount, FaceStatic);
    _faceIndex.assign(faceCount, 0);
    _faceCoeff.assign(3 * size_t(faceCount), 0.f);
    const DfrmCurve& curve = data.curves[0];
    // At rest every sample frame is the root frame (the bind pose is straight),
    // so a rigid face's normal is stored once in root-frame coefficients. It is
    // taken from the triangle as the rig binds it (joint + offset), not from the
    // loaded normal: VRTX and the offsets are rounded to 16.16 separately, which
    // on a 1.4 mm tip ring tilts the loaded normal by up to ~1e-2.
    std::vector<float> restJoint(3 * (data.samples.size() + 1));
    for (int k = 0; k < 3; ++k) restJoint[k] = curve.root[k];
    for (size_t i = 0; i < data.samples.size(); ++i)
        for (int k = 0; k < 3; ++k) restJoint[3*(i + 1) + k] = restJoint[3*i + k] + curve.d[k] * data.samples[i].length;
    auto boundRest = [&](const DfrmInfluence& in, float* o) {
        for (int k = 0; k < 3; ++k) o[k] = restJoint[3*in.index + k] + in.a*curve.d[k] + in.b*curve.v[k] + in.c*curve.s[k];
    };
    for (int f = 0; f < faceCount; ++f) {
        const DfrmInfluence* in[3];
        bool valid = true;
        for (int k = 0; k < 3; ++k) {
            const int v = _faces[3*f + k];
            if (v < 0 || v >= vertexCount) { valid = false; break; }
            in[k] = &data.influences[v];
        }
        if (!valid) return false;
        const bool same = in[0]->kind == in[1]->kind && in[1]->kind == in[2]->kind &&
                          in[0]->index == in[1]->index && in[1]->index == in[2]->index;
        const float* n = &_restNormals[3*f];
        float bound[3];
        if (same && in[0]->kind == DfrmNone) _faceMode[f] = FaceStatic;
        else if (same && in[0]->kind == DfrmOnSample) {
            _faceMode[f] = FaceSample; _faceIndex[f] = in[0]->index;
            float p0[3], p1[3], p2[3];
            boundRest(*in[0], p0); boundRest(*in[1], p1); boundRest(*in[2], p2);
            const float ea[3] = {p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]};
            const float eb[3] = {p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]};
            Cross(ea, eb, bound);
            if (Normalize(bound)) n = bound;          // the loaded normal only for a degenerate triangle
            _faceCoeff[3*f] = Dot(n, curve.d); _faceCoeff[3*f+1] = Dot(n, curve.v); _faceCoeff[3*f+2] = Dot(n, curve.s);
        } else if (same && in[0]->kind == DfrmOnTransform && in[0]->a == in[1]->a && in[1]->a == in[2]->a) {
            _faceMode[f] = FaceTransform; _faceIndex[f] = in[0]->index;
        } else _faceMode[f] = FaceRecompute;
    }
    _rootPitch = std::atan2(-curve.d[0], -curve.d[2]) / kDegToRad;
    const size_t N = data.samples.size();
    _joints.assign(3 * (N + 1), 0.f);
    for (int k = 0; k < 3; ++k) _joints[k] = curve.root[k];
    _frames.assign(9 * N, 0.f);
    _angles.assign(3 * N, 0.f);
    _xf.assign(data.transforms.size(), 0.f);
    std::fill(_outputs, _outputs + 6, 0.f);
    return true;
}

int DfrmEvaluator::Evaluate(const float* block, int n, double now)
{
    if (!_data) return DfrmNoData;
    if (!block || n < DfrmInputCount) return DfrmBadInput;
    for (int i = 0; i < DfrmInputCount; ++i) if (!std::isfinite(block[i])) return DfrmNotFinite;
    if (!std::isfinite(now)) return DfrmNotFinite;
    const DfrmData& D = *_data;
    const DfrmCurve& curve = D.curves[0];
    const int N = curve.sampleCount, T = int(D.transforms.size()), stride = D.frameStride;
    std::vector<float>& A = _scratch;          // stride angles: clip base pose, degrees
    A.assign(stride, 0.f);

    // 1. Clips A and B at now - start, linear between frames; loops wrap, one-shots hold.
    auto clipOf = [&](float id) -> const DfrmClip* {
        const long k = std::lround(id);
        return (k >= 1 && k <= long(D.clips.size()) && std::fabs(id - float(k)) < 1e-3f) ? &D.clips[k - 1] : nullptr;
    };
    auto sample = [&](const DfrmClip& c, double start, float* out) {
        double f = std::max(0.0, now - start) * c.fps;
        int i0, i1; double a;
        if (c.loop) {
            f = std::fmod(f, double(c.frameCount));
            i0 = int(std::floor(f)); if (i0 >= c.frameCount) i0 = c.frameCount - 1;
            i1 = (i0 + 1) % c.frameCount; a = f - i0;
        } else if (f >= c.frameCount - 1) { i0 = i1 = c.frameCount - 1; a = 0; }
        else { i0 = int(std::floor(f)); i1 = i0 + 1; a = f - i0; }
        const int16_t* p0 = &D.frames[size_t(c.firstFrame + i0) * stride];
        const int16_t* p1 = &D.frames[size_t(c.firstFrame + i1) * stride];
        const float af = float(a);
        for (int k = 0; k < stride; ++k)
            out[k] = af == 0.f ? p0[k] * .01f : (p0[k] + (p1[k] - p0[k]) * af) * .01f;
    };
    const DfrmClip* clipA = clipOf(block[25]);
    const DfrmClip* clipB = clipOf(block[27]);
    if (clipA) sample(*clipA, block[26], A.data());
    if (clipB) {
        std::vector<float> B(stride);
        sample(*clipB, block[28], B.data());
        const double fade = block[29];
        double w = fade > 0 ? (now - block[28]) / fade : (now >= block[28] ? 1.0 : 0.0);
        w = std::min(1.0, std::max(0.0, w));
        const float wf = float(w);
        if (wf >= 1.f) A = B;                                   // endpoints exact
        else if (wf > 0.f) for (int k = 0; k < stride; ++k) A[k] = A[k] + (B[k] - A[k]) * wf;
    }

    // 2. Additive knot layer (Hermite over the knots' sample indices).
    std::vector<float> F(N), L(N), Tw(N);
    float kf[DfrmMaxKnots], kl[DfrmMaxKnots], kt[DfrmMaxKnots];
    for (int k = 0; k < curve.knotCount; ++k) { kf[k] = block[3*k]; kl[k] = block[3*k + 1]; kt[k] = block[3*k + 2]; }
    for (int i = 0; i < N; ++i) {
        const float x = float(i);
        F[i] = A[3*i] + DfrmHermite(curve.knots, kf, curve.knotCount, x);
        L[i] = A[3*i + 1] + DfrmHermite(curve.knots, kl, curve.knotCount, x);
        Tw[i] = A[3*i + 2] + DfrmHermite(curve.knots, kt, curve.knotCount, x);
    }

    // 3. Wrap override: holdfast curvature from the tip toward the start sample.
    const long mode = std::lround(block[21]);
    const float radius = block[23], progress = std::min(1.f, std::max(0.f, block[24]));
    const bool wrapping = (mode == 1 || mode == 2) && progress > 0 && radius > 0;
    const float start = std::min(float(N), std::max(0.f, block[22]));
    const float s = float(N) - (float(N) - start) * progress;
    if (wrapping && mode == 2) {               // vertical post: lead-in turns the tail horizontal
        const int i0 = std::max(0, int(std::floor(s)) - 5);
        float acc = -_rootPitch;
        for (int i = 0; i < i0; ++i) acc += F[i];
        const float per = (90 - acc) / 5, w = std::min(1.f, progress * 4);
        for (int i = i0; i < std::min(N, i0 + 5); ++i) { F[i] = F[i]*(1 - w) + per*w; L[i] *= (1 - w); }
    }
    if (wrapping) {
        for (int i = 0; i < N; ++i) {
            const float w = std::max(0.f, std::min(1.f, float(i) + 1 - s));
            if (w == 0) continue;
            const DfrmSample& sm = D.samples[curve.firstSample + i];
            const float kap = sm.length / (radius + sm.halfWidth) / kDegToRad;
            if (mode == 1) { F[i] = F[i]*(1 - w) + kap*w; L[i] *= (1 - w); }
            else           { L[i] = L[i]*(1 - w) + kap*w; F[i] *= (1 - w); }
            Tw[i] *= (1 - w);
        }
    }

    // 4. Clamp to each sample's limits.
    bool clamped = false;
    for (int i = 0; i < N; ++i) {
        const DfrmSample& sm = D.samples[curve.firstSample + i];
        if (F[i] > sm.ventral) { F[i] = sm.ventral; clamped = true; }
        if (F[i] < -sm.dorsal) { F[i] = -sm.dorsal; clamped = true; }
        if (std::fabs(L[i]) > sm.lateral) { L[i] = std::copysign(sm.lateral, L[i]); clamped = true; }
        if (std::fabs(Tw[i]) > sm.twist) { Tw[i] = std::copysign(sm.twist, Tw[i]); clamped = true; }
    }
    // Transform angles: clip value plus the block's, clamped to the transform's range.
    std::vector<float> xf(T);
    for (int t = 0; t < T; ++t) {
        const float a = A[3*N + t] + block[30 + t];
        const DfrmTransform& tr = D.transforms[t];
        xf[t] = std::min(tr.hi, std::max(tr.lo, a));
        if (xf[t] != a) clamped = true;
    }

    // 5. Forward kinematics: frames propagated down the chain, re-orthonormalised every 8 samples.
    std::vector<float> joints(3 * (N + 1)), frames(9 * N);
    float d[3], v[3], sv[3], p[3];
    std::memcpy(d, curve.d, sizeof d); std::memcpy(v, curve.v, sizeof v); std::memcpy(sv, curve.s, sizeof sv);
    std::memcpy(p, curve.root, sizeof p);
    std::memcpy(&joints[0], p, sizeof p);
    for (int i = 0; i < N; ++i) {
        Rot(d, v, F[i] * kDegToRad);       // ventral flex: d toward v
        Rot(d, sv, L[i] * kDegToRad);      // lateral bend: d toward s
        Rot(v, sv, Tw[i] * kDegToRad);     // twist about d
        if ((i + 1) % 8 == 0) Orthonormalize(d, v, sv);
        std::memcpy(&frames[9*i], d, sizeof d); std::memcpy(&frames[9*i + 3], v, sizeof v);
        std::memcpy(&frames[9*i + 6], sv, sizeof sv);
        const float len = D.samples[curve.firstSample + i].length;
        for (int k = 0; k < 3; ++k) p[k] += d[k] * len;
        std::memcpy(&joints[3*(i + 1)], p, sizeof p);
    }

    // 6. Vertices: rigid per sample; weighted transforms about their pivots.
    const int V = int(D.influences.size());
    std::vector<float> pos(3 * size_t(V));
    for (int i = 0; i < V; ++i) {
        const DfrmInfluence& in = D.influences[i];
        float* o = &pos[3*i];
        const float* r = &_rest[3*i];
        if (in.kind == DfrmOnSample) {
            const int j = in.index - curve.firstSample;
            const float* fr = &frames[9*j];
            for (int k = 0; k < 3; ++k) o[k] = joints[3*j + k] + in.a*fr[k] + in.b*fr[3 + k] + in.c*fr[6 + k];
        } else if (in.kind == DfrmOnTransform) {
            const DfrmTransform& tr = D.transforms[in.index];
            const float rel[3] = {r[0] - tr.pivot[0], r[1] - tr.pivot[1], r[2] - tr.pivot[2]};
            Rotate(tr.axis, xf[in.index] * in.a * kDegToRad, rel, o);
            for (int k = 0; k < 3; ++k) o[k] += tr.pivot[k];
        } else std::memcpy(o, r, 3 * sizeof(float));
    }
    for (float f : pos) if (!std::isfinite(f)) return DfrmNotFinite;

    // Face normals: a rigid face turns with its sample or transform; a face that
    // spans two is recomputed with the loader's CalculateNormal winding.
    const int Fc = int(_faceMode.size());
    std::vector<float> normals(_normals);
    for (int f = 0; f < Fc; ++f) {
        float* out = &normals[3*f];
        switch (_faceMode[f]) {
        case FaceStatic: break;
        case FaceSample: {
            const float* fr = &frames[9*(_faceIndex[f] - curve.firstSample)];
            const float* c = &_faceCoeff[3*f];
            for (int k = 0; k < 3; ++k) out[k] = c[0]*fr[k] + c[1]*fr[3 + k] + c[2]*fr[6 + k];
            break;
        }
        case FaceTransform: {
            const int t = _faceIndex[f];
            const float w = D.influences[_faces[3*f]].a;
            Rotate(D.transforms[t].axis, xf[t] * w * kDegToRad, &_restNormals[3*f], out);
            break;
        }
        case FaceRecompute: {
            const float* v0 = &pos[3*_faces[3*f]];
            const float* v1 = &pos[3*_faces[3*f + 1]];
            const float* v2 = &pos[3*_faces[3*f + 2]];
            const float a[3] = {v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]};
            const float b[3] = {v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]};
            float nrm[3]; Cross(a, b, nrm);
            if (Normalize(nrm)) std::memcpy(out, nrm, sizeof nrm);   // degenerate: keep the last normal
            break;
        }
        }
    }

    // 7. Write-backs: wrap centre (centre of the first fully wrapped ring's
    // circle) and the tail tip, both body-local.
    float centre[3] = {0, 0, 0};
    if (wrapping) {
        const int j = std::min(N - 1, std::max(0, int(std::ceil(s))));
        const float* fr = &frames[9*j];
        const float* nrm = mode == 1 ? fr + 3 : fr + 6;
        const float theta = (mode == 1 ? F[j] : L[j]) * kDegToRad;
        const DfrmSample& sm = D.samples[curve.firstSample + j];
        if (std::fabs(theta) > 1e-4f) {
            const float h = sm.length * .5f / std::tan(theta * .5f);
            for (int k = 0; k < 3; ++k) centre[k] = .5f*(joints[3*j + k] + joints[3*(j + 1) + k]) + nrm[k]*h;
        } else {
            for (int k = 0; k < 3; ++k) centre[k] = joints[3*j + k] + nrm[k]*(radius + sm.halfWidth);
        }
    }

    _positions.swap(pos);
    _normals.swap(normals);
    _joints.swap(joints);
    _frames.swap(frames);
    for (int i = 0; i < N; ++i) { _angles[3*i] = F[i]; _angles[3*i + 1] = L[i]; _angles[3*i + 2] = Tw[i]; }
    _xf.swap(xf);
    std::memcpy(_outputs, centre, sizeof centre);
    std::memcpy(_outputs + 3, &_joints[3*N], 3 * sizeof(float));
    return clamped ? DfrmClamped : DfrmOk;
}

} // namespace wf_render
