// dfrm_strand: the DFRM v1 evaluator through the engine's own loader and slot.
//
//   dfrm_strand_test --eval MESH.iff BLOCKS   pose MESH once per BLOCKS line
//       ("now c0 .. c39") through RenderActor3D::Deform and print the status,
//       vertices, face normals and outputs; dfrm_ref.py compares them with
//       its Python reference (parity, 1e-4).
//   dfrm_strand_test --unit DIR               the unit checks on the meshes
//       dfrm_ref.py --write DIR generates.
//
// Run both through the ctest: dfrm_ref.py --check <this binary>.
// docs/plans/2026-10-16-saltwater-seahorses.md, Phase 1 E6.
#include <renderassets/rendacto.hp>
#include <renderassets/dfrm_deform.h>
#include <gfx/backface_cull.hp>
#include <gfx/pixelmap.hp>
#include <memory/lmalloc.hp>
#include <hal/halbase.h>
#include <streams/binstrm.hp>

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

namespace {

struct TestCallbacks : public GfxCallbacks
{
    PixelMap pixelMap{PixelMap::MEMORY_VIDEO, 16, 16};
    LookupTextureStruct LookupTexture(const char*, int32) const override { return LookupTextureStruct(emptyTexture, pixelMap); }
protected:
    void _Validate() const override {}
};

LMalloc* g_memory = nullptr;
TestCallbacks* g_callbacks = nullptr;

void Init()
{
    static std::vector<char> scratch(4 << 20), heap(256 << 20);
    _HALScratchLmalloc = new LMalloc(scratch.data(), scratch.size() MEMORY_NAMED(COMMA "dfrm-scratch"));
    g_memory = new LMalloc(heap.data(), heap.size() MEMORY_NAMED(COMMA "dfrm-heap"));
    g_callbacks = new TestCallbacks;
}

std::vector<char> ReadFile(const std::string& path)
{
    std::ifstream in(path, std::ios::binary);
    if (!in) { std::fprintf(stderr, "dfrm_strand: cannot open %s\n", path.c_str()); std::exit(2); }
    return std::vector<char>(std::istreambuf_iterator<char>(in), {});
}

struct Mesh {
    std::vector<char> bytes;
    std::unique_ptr<RenderActor3D> actor;
    RenderObject3D& Object() { return const_cast<RenderObject3D&>(*actor->GetRenderObject()); }
    int VertexCount() { return Object().GetVertexCount(); }
    int FaceCount() { return Object().GetFaceCount(); }
    Vertex3D* Vertices() { return Object().GetWrittableVertexList(); }
    TriFace* Faces() { return Object().GetWritableFaceList(); }
    std::vector<float> Positions()
    {
        std::vector<float> out;
        for (int i = 0; i < VertexCount(); ++i) {
            const Vector3& p = Vertices()[i].position;
            out.insert(out.end(), {p.X().AsFloat(), p.Y().AsFloat(), p.Z().AsFloat()});
        }
        return out;
    }
};

std::unique_ptr<Mesh> Load(const std::string& path)
{
    std::unique_ptr<Mesh> m(new Mesh);
    m->bytes = ReadFile(path);
    binistream input(m->bytes.data(), int32(m->bytes.size()));
    m->actor.reset(new RenderActor3D(*g_memory, input, 0, *g_callbacks));
    return m;
}

// The DFRM payload of a MODL file, for driving DfrmEvaluator directly.
std::vector<uint8_t> DfrmPayload(const std::vector<char>& modl)
{
    size_t o = 8;
    while (o + 8 <= modl.size()) {
        uint32_t size; std::memcpy(&size, &modl[o + 4], 4);
        if (std::memcmp(&modl[o], "DFRM", 4) == 0) return std::vector<uint8_t>(modl.begin() + o + 8, modl.begin() + o + 8 + size);
        o += 8 + ((size + 3) & ~3u);
    }
    return {};
}

int Eval(const std::string& meshPath, const std::string& blocksPath)
{
    std::unique_ptr<Mesh> m = Load(meshPath);
    std::ifstream in(blocksPath);
    std::string line;
    while (std::getline(in, line)) {
        std::istringstream ss(line);
        double now; ss >> now;
        float block[40] = {0};
        for (float& c : block) ss >> c;
        const DeformStatus status = m->actor->Deform(DeformKind::Dfrm, block, 40, now);
        std::printf("S %d\n", int(status));
        for (int i = 0; i < m->VertexCount(); ++i) {
            const Vector3& p = m->Vertices()[i].position;
            std::printf("V %d %.9g %.9g %.9g\n", i, p.X().AsFloat(), p.Y().AsFloat(), p.Z().AsFloat());
        }
        for (int f = 0; f < m->FaceCount(); ++f) {
            const Vector3& n = m->Faces()[f].normal;
            std::printf("N %d %.9g %.9g %.9g\n", f, n.X().AsFloat(), n.Y().AsFloat(), n.Z().AsFloat());
        }
        float out[6] = {0};
        m->actor->DeformOutputs(out, 6);
        std::printf("O %.9g %.9g %.9g %.9g %.9g %.9g\n", out[0], out[1], out[2], out[3], out[4], out[5]);
    }
    return 0;
}

//----------------------------------------------------------------------------

int g_failures = 0;
void Check(bool ok, const char* what, double value = 0)
{
    std::printf("%s %s (%.3g)\n", ok ? "ok  " : "FAIL", what, value);
    if (!ok) ++g_failures;
}

float Dot(const float* a, const float* b) { return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]; }

void Block(float* b, float flex = 0)
{
    std::fill(b, b + 40, 0.f);
    for (int k = 0; k < 7; ++k) b[3*k] = flex;
}

struct Strand {
    wf_render::DfrmData data;
    wf_render::DfrmEvaluator eval;
    std::unique_ptr<Mesh> mesh;
};

std::unique_ptr<Strand> Evaluator(const std::string& path)
{
    std::unique_ptr<Strand> s(new Strand);
    s->mesh = Load(path);
    const std::vector<uint8_t> payload = DfrmPayload(s->mesh->bytes);
    const char* reason = "";
    if (!wf_render::ParseDfrm(payload.data(), payload.size(), s->mesh->VertexCount(), s->data, reason)) {
        std::fprintf(stderr, "dfrm_strand: %s: %s\n", path.c_str(), reason); std::exit(2);
    }
    std::vector<float> rest = s->mesh->Positions(), normals;
    std::vector<int> faces;
    for (int f = 0; f < s->mesh->FaceCount(); ++f) {
        const TriFace& t = s->mesh->Faces()[f];
        faces.insert(faces.end(), {t.v1Index, t.v2Index, t.v3Index});
        normals.insert(normals.end(), {t.normal.X().AsFloat(), t.normal.Y().AsFloat(), t.normal.Z().AsFloat()});
    }
    s->eval.Bind(s->data, rest.data(), s->mesh->VertexCount(), faces.data(), normals.data(), s->mesh->FaceCount());
    return s;
}

void Geometry(const std::string& dir)
{
    // Arc length on every mockup-like pose of the real strand.
    std::unique_ptr<Strand> s = Evaluator(dir + "/strand.iff");
    double rest = 0;
    for (const auto& sm : s->data.samples) rest += sm.length;
    const float poses[][5] = {{0, 0, 0, 0, 0}, {8, 1, 18, .04f, 1}, {4, 2, 16, .06f, 1}, {36, 0, 18, .04f, 0}, {-3, 0, 0, 0, 0}};
    double worstArc = 0;
    for (const auto& p : poses) {
        float b[40]; Block(b, p[0]); b[21] = p[1]; b[22] = p[2]; b[23] = p[3]; b[24] = p[4];
        s->eval.Evaluate(b, 40, 0);
        const auto& J = s->eval.Joints();
        double arc = 0;
        for (size_t i = 0; i + 1 < J.size() / 3; ++i)
            arc += std::sqrt(std::pow(J[3*i+3]-J[3*i], 2) + std::pow(J[3*i+4]-J[3*i+1], 2) + std::pow(J[3*i+5]-J[3*i+2], 2));
        worstArc = std::max(worstArc, std::fabs(arc - rest) / rest);
    }
    Check(worstArc < 1e-3, "arc length preserved within 0.1 % on five poses (worst relative error)", worstArc);

    // Two full coils: frames stay orthonormal, no axis flips sign between samples,
    // and every wrapped joint lies on the analytic holdfast circle.
    std::unique_ptr<Strand> c = Evaluator(dir + "/coil.iff");
    const float radius = .02f / (18.f * 0.01745329252f) - .003f;      // 18 degrees per sample
    float b[40]; Block(b); b[21] = 1; b[22] = 0; b[23] = radius; b[24] = 1;
    const int status = c->eval.Evaluate(b, 40, 0);
    double turned = 0;
    for (size_t i = 0; i < c->eval.Angles().size() / 3; ++i) turned += c->eval.Angles()[3*i];
    Check(status == wf_render::DfrmOk && turned >= 719.9, "coil test turns two full coils unclamped (degrees)", turned);
    const auto& F = c->eval.Frames();
    double worstOrtho = 0; int flips = 0;
    for (size_t i = 0; i < F.size() / 9; ++i) {
        const float* d = &F[9*i]; const float* v = d + 3; const float* sv = d + 6;
        const double e[] = {Dot(d, d) - 1, Dot(v, v) - 1, Dot(sv, sv) - 1, Dot(d, v), Dot(d, sv), Dot(v, sv)};
        for (double x : e) worstOrtho = std::max(worstOrtho, std::fabs(x));
        if (i > 0) {
            const float* p = &F[9*(i-1)];
            if (Dot(d, p) <= 0 || Dot(v, p + 3) <= 0 || Dot(sv, p + 6) <= 0) ++flips;
        }
    }
    Check(worstOrtho < 1e-5, "frames orthonormal within 1e-5 through two coils (worst)", worstOrtho);
    Check(flips == 0, "no frame axis flips sign between samples (flips)", flips);
    const float* centre = c->eval.Outputs();
    const float R = radius + .003f;
    double worstCircle = 0;
    const auto& J = c->eval.Joints();
    for (size_t i = 0; i < J.size() / 3; ++i) {
        const double dist = std::sqrt(std::pow(J[3*i]-centre[0], 2) + std::pow(J[3*i+1]-centre[1], 2) + std::pow(J[3*i+2]-centre[2], 2));
        worstCircle = std::max(worstCircle, std::fabs(dist - R));
    }
    Check(worstCircle < .005, "wrapped joints within 0.5 mm (0.005 units) of the analytic circle (worst, units)", worstCircle);

    // Face normals after a 180-degree coil: each driven normal equals the
    // normal of its deformed triangle (a rigid ring rotates its rest normal), and
    // a face that truly faces the camera is not culled. With the stale rest
    // normals some of those faces would be culled: that is the bug this guards.
    std::unique_ptr<Mesh> m = Load(dir + "/coil.iff");
    const std::vector<float> restPos = m->Positions();
    std::vector<float> restN;
    for (int f = 0; f < m->FaceCount(); ++f) {
        const Vector3& n = m->Faces()[f].normal;
        restN.insert(restN.end(), {n.X().AsFloat(), n.Y().AsFloat(), n.Z().AsFloat()});
    }
    Block(b); b[21] = 1; b[22] = 30; b[23] = radius; b[24] = 1;    // 10 samples x 18 = 180 degrees
    const DeformStatus st = m->actor->Deform(DeformKind::Dfrm, b, 40, 0);
    Check(st == DeformStatus::Ok, "180-degree coil poses (status)", int(st));
    const std::vector<float> P = m->Positions();
    float mv[16] = {1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,-3,1};             // camera 3 units in front, looking down -Z
    double worstNormal = 0; int visibleCulled = 0, visibleStaleCulled = 0, coiled = 0;
    for (int f = 0; f < m->FaceCount(); ++f) {
        const TriFace& t = m->Faces()[f];
        const float* a = &P[3*t.v1Index]; const float* bb = &P[3*t.v2Index]; const float* cc = &P[3*t.v3Index];
        const float e1[] = {cc[0]-a[0], cc[1]-a[1], cc[2]-a[2]}, e2[] = {bb[0]-a[0], bb[1]-a[1], bb[2]-a[2]};
        float g[] = {e1[1]*e2[2]-e1[2]*e2[1], e1[2]*e2[0]-e1[0]*e2[2], e1[0]*e2[1]-e1[1]*e2[0]};
        const float gl = std::sqrt(Dot(g, g)); for (float& x : g) x /= gl;
        const float n[] = {t.normal.X().AsFloat(), t.normal.Y().AsFloat(), t.normal.Z().AsFloat()};
        const float* rn = &restN[3*f];
        const bool turned = Dot(n, rn) < .99f;
        if (turned) ++coiled;
        for (int k = 0; k < 3; ++k) worstNormal = std::max(worstNormal, double(std::fabs(n[k] - g[k])));
        const float centroid[] = {(a[0]+bb[0]+cc[0])/3, (a[1]+bb[1]+cc[1])/3, (a[2]+bb[2]+cc[2])/3};
        const float toCamera[] = {-centroid[0], -centroid[1], 3 - centroid[2]};
        if (Dot(g, toCamera) > 1e-3f) {               // truly facing the camera
            if (WfFaceIsBackfacing(mv, n[0], n[1], n[2], a[0], a[1], a[2], bb[0], bb[1], bb[2], cc[0], cc[1], cc[2])) ++visibleCulled;
            if (WfFaceIsBackfacing(mv, rn[0], rn[1], rn[2], a[0], a[1], a[2], bb[0], bb[1], bb[2], cc[0], cc[1], cc[2])) ++visibleStaleCulled;
        }
    }
    Check(coiled > 0 && worstNormal < 1e-4, "coiled face normals equal their rotated rest normals within 1e-4 (worst)", worstNormal);
    Check(visibleCulled == 0, "no camera-facing face is reported back-facing (count)", visibleCulled);
    Check(visibleStaleCulled > 0, "with rest normals some camera-facing faces would be culled (count)", visibleStaleCulled);
}

void Clips(const std::string& dir)
{
    std::unique_ptr<Strand> s = Evaluator(dir + "/clips.iff");
    // clip 3 "ramp": one-shot, flex 0, 2, 4, 6. clip 4 "wave": loop, flex 1, -1, 3.
    // clip 5 "hold": one frame, flex 5. 30 fps.
    auto flex0 = [&](float a, float startA, float b, float startB, float fade, double now) {
        float blk[40]; Block(blk); blk[25] = a; blk[26] = startA; blk[27] = b; blk[28] = startB; blk[29] = fade;
        s->eval.Evaluate(blk, 40, now);
        return s->eval.Angles()[0];
    };
    float v = flex0(3, 0, 0, 0, 0, 1.5 / 30);
    Check(std::fabs(v - 3) < 1e-5f, "linear interpolation between frames (ramp at frame 1.5)", v);
    v = flex0(3, 1, 0, 0, 0, 1 + 2.0 / 30);
    Check(std::fabs(v - 4) < 1e-4f, "a clip plays from its start time (ramp at frame 2 after start)", v);
    v = flex0(3, 0, 0, 0, 0, 10);
    Check(v == 6, "one-shot holds its last frame", v);
    v = flex0(4, 0, 0, 0, 0, 3.5 / 30);
    Check(std::fabs(v) < 1e-5f, "looping clip wraps (wave at frame 3.5 = frame 0.5)", v);
    v = flex0(4, 0, 0, 0, 0, 2.5 / 30);
    Check(std::fabs(v - 2) < 1e-5f, "looping clip interpolates last -> first (wave at frame 2.5)", v);
    v = flex0(99, 0, 0, 0, 0, 1);
    Check(v == 0, "unknown clip id is no clip", v);

    // Crossfade endpoints exact: the whole pose equals A alone at w = 0 and B alone at w = 1.
    auto pose = [&](float a, float b, double now) {
        float blk[40]; Block(blk); blk[25] = a; blk[26] = 0; blk[27] = b; blk[28] = 2; blk[29] = 1;
        s->eval.Evaluate(blk, 40, now);
        return s->eval.Positions();
    };
    const std::vector<float> aAt2 = pose(3, 0, 2), bAt3 = pose(0, 5, 3);
    Check(pose(3, 5, 2) == aAt2, "crossfade at w = 0 equals clip A exactly");
    Check(pose(3, 5, 3) == bAt3, "crossfade at w = 1 equals clip B exactly");
    v = flex0(3, 0, 5, 2, 1, 2.5);
    Check(std::fabs(v - 5.5f) < 1e-5f, "crossfade midway blends (6 -> 5 at w = .5 is 5.5)", v);
}

void Loader(const std::string& dir)
{
    for (const char* name : {"bad_count.iff", "bad_version.iff", "bad_index.iff"}) {
        std::unique_ptr<Mesh> m = Load(dir + "/" + name);
        const std::vector<float> rest = m->Positions();
        float b[40]; Block(b, 10); b[21] = 1; b[22] = 10; b[23] = .04f; b[24] = 1;
        const DeformStatus st = m->actor->Deform(DeformKind::Dfrm, b, 40, 0);
        const std::string what = std::string("loader drops ") + name + ": no metadata, rest pose kept (status)";
        Check(m->Object().GetDfrm() == nullptr && st == DeformStatus::NoMetadata && m->Positions() == rest, what.c_str(), int(st));
    }
}

void Exclusivity(const std::string& dir)
{
    float b[40]; Block(b, 5);
    {
        std::unique_ptr<Mesh> m = Load(dir + "/strand.iff");
        m->actor->SetFinDeformation(.1f, .1f, 0, 1);                       // fin weights exist
        const std::vector<float> before = m->Positions();
        const DeformStatus st = m->actor->Deform(DeformKind::Dfrm, b, 40, 0);
        Check(st == DeformStatus::OtherKindBound && m->Positions() == before, "DFRM refused when fin weights exist (status)", int(st));
    }
    {
        std::unique_ptr<Mesh> m = Load(dir + "/strand.iff");
        m->actor->SetLionPose(.2f, .5f, 0, 0, 0, 0);                       // no LRIG: lion never binds
        DeformStatus st = m->actor->Deform(DeformKind::Dfrm, b, 40, 0);
        Check(st == DeformStatus::Ok, "DFRM binds when lion found no rig (status)", int(st));
        const std::vector<float> before = m->Positions();
        const float lion[] = {.2f, .5f, 0, 0, 0, 0};
        st = m->actor->Deform(DeformKind::Lion, lion, 6, 0);
        m->actor->SetFishDeformation(.3f, .1f);
        Check(st == DeformStatus::OtherKindBound && m->Positions() == before, "lion and fish refused once DFRM is bound (status)", int(st));
        float bad[40]; Block(bad, 5); bad[3] = NAN;
        st = m->actor->Deform(DeformKind::Dfrm, bad, 40, 0);
        Check(st == DeformStatus::NotFinite && m->Positions() == before, "non-finite input keeps the previous pose (status)", int(st));
        st = m->actor->Deform(DeformKind::Dfrm, b, 20, 0);
        Check(st == DeformStatus::BadInput && m->Positions() == before, "too few channels is bad input, pose kept (status)", int(st));
    }
}

void Timing(const std::string& dir)
{
    std::unique_ptr<Mesh> m = Load(dir + "/dense.iff");
    float b[40]; Block(b, 6); b[21] = 2; b[22] = 16; b[23] = .06f; b[24] = .7f; b[30] = 5;
    const int reps = 2000;
    const auto t0 = std::chrono::steady_clock::now();
    for (int i = 0; i < reps; ++i) { b[24] = .5f + .4f * float(i % 10) / 10; m->actor->Deform(DeformKind::Dfrm, b, 40, i / 60.0); }
    const double us = std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - t0).count() / reps;
    std::printf("info evaluator: %.1f us per pose, %d vertices, %d faces (this host, Release)\n", us, m->VertexCount(), m->FaceCount());
}

} // namespace

int main(int argc, char** argv)
{
    Init();
    if (argc == 4 && std::strcmp(argv[1], "--eval") == 0) return Eval(argv[2], argv[3]);
    if (argc == 3 && std::strcmp(argv[1], "--unit") == 0) {
        const std::string dir = argv[2];
        Geometry(dir); Clips(dir); Loader(dir); Exclusivity(dir); Timing(dir);
        std::printf("dfrm_strand unit: %s\n", g_failures ? "FAIL" : "PASS");
        return g_failures ? 1 : 0;
    }
    std::fprintf(stderr, "usage: dfrm_strand_test --eval MESH BLOCKS | --unit DIR (run via dfrm_ref.py --check)\n");
    return 2;
}
