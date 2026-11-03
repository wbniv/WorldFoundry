//============================================================================
// dfrm_deform.cc: DFRM v1/v2 loader and evaluator. See dfrm_deform.h for the
// chunk layout and the control block; wflevels/aquarium_tanks/dfrm_ref.py is
// the reference the dfrm_strand test compares against.
//============================================================================
#include <renderassets/dfrm_deform.h>
#include <renderassets/face_normal.h>

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
    if ((version != DfrmVersion && version != DfrmVersion2) || flags != 0) { reason = "unknown version"; return false; }
    if (version == DfrmVersion && nCurves != 1) { reason = "v1 needs exactly one curve"; return false; }
    if (nCurves < 1 || nCurves > DfrmMaxCurves) { reason = "curve count out of range"; return false; }
    const uint32_t maxSamples = version == DfrmVersion ? DfrmMaxSamplesV1 : DfrmMaxSamples;
    if (nSamples < 1 || nSamples > maxSamples) { reason = "sample count out of range"; return false; }
    if (nTransforms > DfrmMaxTransforms) { reason = "too many transforms"; return false; }
    if (vertexCount <= 0 || nInfluences != uint32_t(vertexCount)) { reason = "influence count != vertex count"; return false; }
    if (nClips > 65535 || nFrames > 1000000) { reason = "clip table too large"; return false; }
    const size_t stride = 3 * size_t(nSamples) + nTransforms;
    const size_t frameBytes = (2 * stride * nFrames + 3) & ~size_t(3);
    const size_t expected = 32 + 52 * size_t(nCurves) + 16 * size_t(nSamples) + 28 * size_t(nTransforms)
                          + 16 * size_t(nInfluences) + 16 * size_t(nClips) + frameBytes;
    if (size != expected) { reason = "chunk size does not match its counts"; return false; }

    DfrmData d;
    d.version = int(version);
    d.frameStride = int(stride);
    d.sampleCurve.assign(nSamples, 0);
    int next = 0;                              // the partition: curve c starts where c - 1 ended
    for (uint32_t c = 0; c < nCurves; ++c) {
        DfrmCurve curve{};
        for (float& f : curve.root) f = r.fixed();
        for (float& f : curve.d) f = r.fixed();
        for (float& f : curve.v) f = r.fixed();
        curve.firstSample = r.get<uint16_t>(); curve.sampleCount = r.get<uint16_t>();
        curve.knotCount = r.get<uint8_t>(); r.get<uint8_t>(); r.get<uint8_t>(); r.get<uint8_t>();
        for (int& k : curve.knots) k = r.get<uint8_t>();
        if (curve.firstSample != next || curve.sampleCount < 1 || next + curve.sampleCount > int(nSamples)) {
            reason = "curves must partition the samples in order"; return false;
        }
        std::fill(d.sampleCurve.begin() + next, d.sampleCurve.begin() + next + curve.sampleCount, uint8_t(c));
        next += curve.sampleCount;
        // Curve 0's knots are driven by the block; a later curve may carry none.
        if (!(c > 0 && curve.knotCount == 0)) {
            if (curve.knotCount < 2 || curve.knotCount > DfrmMaxKnots) { reason = "knot count out of range"; return false; }
            if (curve.knots[0] != 0 || curve.knots[curve.knotCount - 1] != curve.sampleCount - 1) { reason = "knots must span the curve"; return false; }
            for (int k = 1; k < curve.knotCount; ++k)
                if (curve.knots[k] <= curve.knots[k - 1]) { reason = "knots not increasing"; return false; }
        }
        if (!Normalize(curve.d) || !Normalize(curve.v)) { reason = "degenerate root frame"; return false; }
        if (std::fabs(Dot(curve.d, curve.v)) > .99f) { reason = "degenerate root frame"; return false; }
        Orthonormalize(curve.d, curve.v, curve.s);
        d.curves.push_back(curve);
    }
    if (next != int(nSamples)) { reason = "curves must partition the samples in order"; return false; }
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
    const size_t N = data.samples.size(), C = data.curves.size();
    if (C < 1 || C > size_t(DfrmMaxCurves) || data.sampleCurve.size() != N ||
        int(data.influences.size()) != vertexCount || faceCount < 0) return false;
    _data = &data;
    _rest.assign(rest, rest + 3 * size_t(vertexCount));
    _positions = _rest;
    _faces.assign(faces, faces + 3 * size_t(faceCount));
    _restNormals.assign(restNormals, restNormals + 3 * size_t(faceCount));
    _normals = _restNormals;
    _faceMode.assign(faceCount, FaceStatic);
    _faceIndex.assign(faceCount, 0);
    _faceCoeff.assign(3 * size_t(faceCount), 0.f);
    // At rest every sample frame is its curve's root frame (each curve's bind
    // pose is straight), so a rigid face's normal is stored once in coefficients
    // of its own curve's root frame. It is taken from the triangle as the rig
    // binds it (joint + offset), not from the loaded normal: VRTX and the offsets
    // are rounded to 16.16 separately, which on a 1.4 mm tip ring tilts the
    // loaded normal by up to ~1e-2. Joints: curve c's root is joint
    // firstSample + c, and sample i of curve c ends at joint i + c + 1.
    std::vector<float> restJoint(3 * (N + C));
    for (size_t c = 0; c < C; ++c) {
        const DfrmCurve& cv = data.curves[c];
        float* j = &restJoint[3 * (cv.firstSample + c)];
        for (int k = 0; k < 3; ++k) j[k] = cv.root[k];
        for (int i = 0; i < cv.sampleCount; ++i, j += 3)
            for (int k = 0; k < 3; ++k) j[3 + k] = j[k] + cv.d[k] * data.samples[cv.firstSample + i].length;
    }
    auto boundRest = [&](const DfrmInfluence& in, float* o) {
        const int c = data.sampleCurve[in.index];
        const DfrmCurve& cv = data.curves[c];
        const float* j = &restJoint[3 * (in.index + c)];
        for (int k = 0; k < 3; ++k) o[k] = j[k] + in.a*cv.d[k] + in.b*cv.v[k] + in.c*cv.s[k];
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
        // Same kind and index: a face whose vertices span two samples (or two
        // curves) is recomputed.
        const bool same = in[0]->kind == in[1]->kind && in[1]->kind == in[2]->kind &&
                          in[0]->index == in[1]->index && in[1]->index == in[2]->index;
        const float* n = &_restNormals[3*f];
        float bound[3];
        if (same && in[0]->kind == DfrmNone) _faceMode[f] = FaceStatic;
        else if (same && in[0]->kind == DfrmOnSample) {
            _faceMode[f] = FaceSample; _faceIndex[f] = in[0]->index;
            const DfrmCurve& cv = data.curves[data.sampleCurve[in[0]->index]];
            float p0[3], p1[3], p2[3];
            boundRest(*in[0], p0); boundRest(*in[1], p1); boundRest(*in[2], p2);
            if (TriangleNormal(p0, p1, p2, bound)) n = bound;   // the loaded normal only for a degenerate triangle
            _faceCoeff[3*f] = Dot(n, cv.d); _faceCoeff[3*f+1] = Dot(n, cv.v); _faceCoeff[3*f+2] = Dot(n, cv.s);
        } else if (same && in[0]->kind == DfrmOnTransform && in[0]->a == in[1]->a && in[1]->a == in[2]->a) {
            _faceMode[f] = FaceTransform; _faceIndex[f] = in[0]->index;
        } else _faceMode[f] = FaceRecompute;
    }
    const DfrmCurve& curve = data.curves[0];
    _rootPitch = std::atan2(-curve.d[0], -curve.d[2]) / kDegToRad;
    _joints.assign(3 * (N + C), 0.f);
    for (size_t c = 0; c < C; ++c)
        for (int k = 0; k < 3; ++k) _joints[3 * (data.curves[c].firstSample + c) + k] = data.curves[c].root[k];
    _frames.assign(9 * N, 0.f);
    _angles.assign(3 * N, 0.f);
    _xf.assign(data.transforms.size(), 0.f);
    std::fill(_outputs, _outputs + 6, 0.f);
    _clipA.assign(data.frameStride, 0.f); _clipB.assign(data.frameStride, 0.f); _clipC.assign(data.frameStride, 0.f);
    _flex.assign(N, 0.f); _lateral.assign(N, 0.f); _twist.assign(N, 0.f);
    _scale.assign(C, 1.f);
    _xfNext = _xf; _jointsNext = _joints; _framesNext = _frames;
    _positionsNext = _positions; _normalsNext = _normals;
    return true;
}

int DfrmEvaluator::Evaluate(const float* block, int n, double now, const float* worldRotation)
{
    if (!_data) return DfrmNoData;
    const DfrmData& D = *_data;
    const int C = int(D.curves.size());
    const bool records = D.version >= DfrmVersion2;      // a v1 mesh reads no per-curve records
    const int need = DfrmBlockCells(D.version, C);
    if (!block || n < need) return DfrmBadInput;
    for (int i = 0; i < DfrmInputCount; ++i) if (!std::isfinite(block[i])) return DfrmNotFinite;
    for (int i = DfrmBlockSize; i < need; ++i) if (!std::isfinite(block[i])) return DfrmNotFinite;
    if (!std::isfinite(now)) return DfrmNotFinite;
    const DfrmCurve& curve = D.curves[0];
    // N: curve 0's samples (knots, wrap, outputs); NS: every curve's.
    const int N = curve.sampleCount, NS = int(D.samples.size()), T = int(D.transforms.size()), stride = D.frameStride;
    std::vector<float>& A = _clipA;            // stride angles: clip base pose, degrees
    std::fill(A.begin(), A.end(), 0.f);

    // 1. Clips A and B at now - start, linear between frames; loops wrap, one-shots hold.
    auto clipOf = [&](float id) -> const DfrmClip* {
        const long k = std::lround(id);
        return (k >= 1 && k <= long(D.clips.size()) && std::fabs(id - float(k)) < 1e-3f) ? &D.clips[k - 1] : nullptr;
    };
    // Columns k0..k1-1 of the clip's row (a curve's slice, or the whole stride).
    auto sample = [&](const DfrmClip& c, double start, float* out, int k0, int k1) {
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
        for (int k = k0; k < k1; ++k)
            out[k] = af == 0.f ? p0[k] * .01f : (p0[k] + (p1[k] - p0[k]) * af) * .01f;
    };
    // Crossfade weight of a clip started at start, over cell 29's fade time.
    auto fadeIn = [&](double start) {
        const double fade = block[29];
        double w = fade > 0 ? (now - start) / fade : (now >= start ? 1.0 : 0.0);
        w = std::min(1.0, std::max(0.0, w));
        return float(w);
    };
    const DfrmClip* clipA = clipOf(block[25]);
    const DfrmClip* clipB = clipOf(block[27]);
    if (clipA) sample(*clipA, block[26], A.data(), 0, stride);
    if (clipB) {
        std::vector<float>& B = _clipB;
        sample(*clipB, block[28], B.data(), 0, stride);
        const float wf = fadeIn(block[28]);
        if (wf >= 1.f) std::copy(B.begin(), B.end(), A.begin());   // endpoints exact
        else if (wf > 0.f) for (int k = 0; k < stride; ++k) A[k] = A[k] + (B[k] - A[k]) * wf;
    }
    // 1b. v2: a curve's own clip replaces its slice of the shared pose, blended
    // in over the same fade from its own start (exact at the endpoints).
    if (records) {
        std::vector<float>& P = _clipC;
        for (int c = 0; c < C; ++c) {
            const float* rec = block + DfrmBlockSize + DfrmCurveCells * c;
            const DfrmClip* own = clipOf(rec[DfrmCurveClip]);
            if (!own) continue;
            const DfrmCurve& cv = D.curves[c];
            const int k0 = 3 * cv.firstSample, k1 = 3 * (cv.firstSample + cv.sampleCount);
            sample(*own, rec[DfrmCurveStart], P.data(), k0, k1);
            const float wf = fadeIn(rec[DfrmCurveStart]);
            if (wf >= 1.f) std::copy(P.begin() + k0, P.begin() + k1, A.begin() + k0);
            else if (wf > 0.f) for (int k = k0; k < k1; ++k) A[k] = A[k] + (P[k] - A[k]) * wf;
        }
    }

    // 2. Additive knot layer (Hermite over the knots' sample indices), curve 0 only.
    std::vector<float>& F = _flex;
    std::vector<float>& L = _lateral;
    std::vector<float>& Tw = _twist;
    float kf[DfrmMaxKnots], kl[DfrmMaxKnots], kt[DfrmMaxKnots];
    for (int k = 0; k < curve.knotCount; ++k) { kf[k] = block[3*k]; kl[k] = block[3*k + 1]; kt[k] = block[3*k + 2]; }
    for (int i = 0; i < N; ++i) {
        const float x = float(i);
        F[i] = A[3*i] + DfrmHermite(curve.knots, kf, curve.knotCount, x);
        L[i] = A[3*i + 1] + DfrmHermite(curve.knots, kl, curve.knotCount, x);
        Tw[i] = A[3*i + 2] + DfrmHermite(curve.knots, kt, curve.knotCount, x);
    }
    for (int i = N; i < NS; ++i) { F[i] = A[3*i]; L[i] = A[3*i + 1]; Tw[i] = A[3*i + 2]; }

    // 3. Wrap override (curve 0): holdfast curvature from the tip toward the start sample.
    const long mode = std::lround(block[21]);
    const float radius = block[23], progress = std::min(1.f, std::max(0.f, block[24]));
    const bool wrapping = (mode == 1 || mode == 2) && progress > 0 && radius > 0;
    const float start = std::min(float(N), std::max(0.f, block[22]));
    const float s = float(N) - (float(N) - start) * progress;
    if (wrapping && mode == 2) {               // vertical post: lead-in turns the tail horizontal
        // The mockup measures the root's pitch from straight down. In world
        // space: flexing the root by phi makes d horizontal with v up when
        // d0.u cos phi + v0.u sin phi = 0 and v.u > 0, i.e. phi = atan2(v0.u,
        // d0.u) - 90 deg, u being world up in model coordinates. The mockup's
        // pitch is phi - 90; for the identity rotation it equals _rootPitch.
        float pitch = _rootPitch;
        if (worldRotation) {
            float u[3] = {worldRotation[2], worldRotation[5], worldRotation[8]};
            if (Normalize(u)) {
                const float a = Dot(curve.d, u), c = Dot(curve.v, u);
                if (a*a + c*c > 1e-8f) {       // else the flex plane is horizontal: keep the model pitch
                    float phi = std::atan2(c, a) / kDegToRad - 90;
                    while (phi > 180) phi -= 360;
                    while (phi <= -180) phi += 360;
                    pitch = phi - 90;
                }
            }
        }
        const int i0 = std::max(0, int(std::floor(s)) - 5);
        float acc = -pitch;
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

    // 4. v2: each curve's flex bias and scale (clamped to 0.02-1); then clamp
    // every sample to its limits.
    bool clamped = false;
    if (records) {
        for (int c = 0; c < C; ++c) {
            const float* rec = block + DfrmBlockSize + DfrmCurveCells * c;
            const DfrmCurve& cv = D.curves[c];
            const float bias = rec[DfrmCurveBias];
            if (bias != 0) for (int i = cv.firstSample; i < cv.firstSample + cv.sampleCount; ++i) F[i] += bias;
            const float sc = rec[DfrmCurveScale];
            _scale[c] = std::min(DfrmMaxScale, std::max(DfrmMinScale, sc));
            if (_scale[c] != sc) clamped = true;
        }
    }
    for (int i = 0; i < NS; ++i) {
        const DfrmSample& sm = D.samples[i];
        if (F[i] > sm.ventral) { F[i] = sm.ventral; clamped = true; }
        if (F[i] < -sm.dorsal) { F[i] = -sm.dorsal; clamped = true; }
        if (std::fabs(L[i]) > sm.lateral) { L[i] = std::copysign(sm.lateral, L[i]); clamped = true; }
        if (std::fabs(Tw[i]) > sm.twist) { Tw[i] = std::copysign(sm.twist, Tw[i]); clamped = true; }
    }
    // Transform angles: clip value plus the block's, clamped to the transform's range.
    std::vector<float>& xf = _xfNext;
    for (int t = 0; t < T; ++t) {
        const float a = A[3*NS + t] + block[30 + t];
        const DfrmTransform& tr = D.transforms[t];
        xf[t] = std::min(tr.hi, std::max(tr.lo, a));
        if (xf[t] != a) clamped = true;
    }

    // 5. Forward kinematics per curve from its own root frame, re-orthonormalised
    // every 8 samples; joint steps are scaled about the root (x 1 is exact).
    std::vector<float>& joints = _jointsNext;
    std::vector<float>& frames = _framesNext;
    for (int c = 0; c < C; ++c) {
        const DfrmCurve& cv = D.curves[c];
        const float scale = _scale[c];
        float d[3], v[3], sv[3], p[3];
        std::memcpy(d, cv.d, sizeof d); std::memcpy(v, cv.v, sizeof v); std::memcpy(sv, cv.s, sizeof sv);
        std::memcpy(p, cv.root, sizeof p);
        float* J = &joints[3 * (cv.firstSample + c)];
        std::memcpy(J, p, sizeof p);
        for (int i = 0; i < cv.sampleCount; ++i) {
            const int g = cv.firstSample + i;
            Rot(d, v, F[g] * kDegToRad);       // ventral flex: d toward v
            Rot(d, sv, L[g] * kDegToRad);      // lateral bend: d toward s
            Rot(v, sv, Tw[g] * kDegToRad);     // twist about d
            if ((i + 1) % 8 == 0) Orthonormalize(d, v, sv);
            std::memcpy(&frames[9*g], d, sizeof d); std::memcpy(&frames[9*g + 3], v, sizeof v);
            std::memcpy(&frames[9*g + 6], sv, sizeof sv);
            const float len = D.samples[g].length * scale;
            for (int k = 0; k < 3; ++k) p[k] += d[k] * len;
            std::memcpy(J + 3*(i + 1), p, sizeof p);
        }
    }

    // 6. Vertices: rigid per sample, offsets scaled with their curve; weighted
    // transforms about their pivots.
    const int V = int(D.influences.size());
    std::vector<float>& pos = _positionsNext;
    for (int i = 0; i < V; ++i) {
        const DfrmInfluence& in = D.influences[i];
        float* o = &pos[3*i];
        const float* r = &_rest[3*i];
        if (in.kind == DfrmOnSample) {
            const int j = in.index, c = D.sampleCurve[j];
            const float sc = _scale[c], a = in.a * sc, b = in.b * sc, cc = in.c * sc;
            const float* fr = &frames[9*j];
            const float* J = &joints[3*(j + c)];
            for (int k = 0; k < 3; ++k) o[k] = J[k] + a*fr[k] + b*fr[3 + k] + cc*fr[6 + k];
        } else if (in.kind == DfrmOnTransform) {
            const DfrmTransform& tr = D.transforms[in.index];
            const float rel[3] = {r[0] - tr.pivot[0], r[1] - tr.pivot[1], r[2] - tr.pivot[2]};
            Rotate(tr.axis, xf[in.index] * in.a * kDegToRad, rel, o);
            for (int k = 0; k < 3; ++k) o[k] += tr.pivot[k];
        } else std::memcpy(o, r, 3 * sizeof(float));
    }
    for (float f : pos) if (!std::isfinite(f)) return DfrmNotFinite;

    // Face normals: a rigid face turns with its sample or transform (a uniform
    // scale does not turn it); a face that spans two is recomputed with the
    // loader's CalculateNormal winding.
    const int Fc = int(_faceMode.size());
    std::vector<float>& normals = _normalsNext;
    std::copy(_normals.begin(), _normals.end(), normals.begin());   // static faces and degenerate recomputes keep theirs
    for (int f = 0; f < Fc; ++f) {
        float* out = &normals[3*f];
        switch (_faceMode[f]) {
        case FaceStatic: break;
        case FaceSample: {
            const float* fr = &frames[9*_faceIndex[f]];
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
        case FaceRecompute:                     // degenerate: keeps the last normal
            TriangleNormal(&pos[3*_faces[3*f]], &pos[3*_faces[3*f + 1]], &pos[3*_faces[3*f + 2]], out);
            break;
        }
    }

    // 7. Write-backs: wrap centre (centre of the first fully wrapped ring's
    // circle) and the tail tip, both body-local, both curve 0's (its joints
    // are 0..N).
    float centre[3] = {0, 0, 0};
    if (wrapping) {
        const int j = std::min(N - 1, std::max(0, int(std::ceil(s))));
        const float* fr = &frames[9*j];
        const float* nrm = mode == 1 ? fr + 3 : fr + 6;
        const float theta = (mode == 1 ? F[j] : L[j]) * kDegToRad;
        const DfrmSample& sm = D.samples[curve.firstSample + j];
        if (std::fabs(theta) > 1e-4f) {
            const float h = sm.length * _scale[0] * .5f / std::tan(theta * .5f);
            for (int k = 0; k < 3; ++k) centre[k] = .5f*(joints[3*j + k] + joints[3*(j + 1) + k]) + nrm[k]*h;
        } else {
            for (int k = 0; k < 3; ++k) centre[k] = joints[3*j + k] + nrm[k]*(radius + sm.halfWidth);
        }
    }

    _positions.swap(pos);                       // swaps of equal-sized buffers: no allocation
    _normals.swap(normals);
    _joints.swap(joints);
    _frames.swap(frames);
    for (int i = 0; i < NS; ++i) { _angles[3*i] = F[i]; _angles[3*i + 1] = L[i]; _angles[3*i + 2] = Tw[i]; }
    _xf.swap(xf);
    std::memcpy(_outputs, centre, sizeof centre);
    std::memcpy(_outputs + 3, &_joints[3*N], 3 * sizeof(float));
    return clamped ? DfrmClamped : DfrmOk;
}

} // namespace wf_render
