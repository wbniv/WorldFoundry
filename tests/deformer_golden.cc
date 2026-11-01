// deformer_golden: bit-for-bit regression guard for the five per-species mesh
// deformers (fish, fin, swim, jelly, lion).
//
// Loads the real aquarium meshes through RenderActor3D's on-disk constructor,
// exactly as the engine does, drives the public Set*Deformation / SetLionPose
// API with fixed parameter sequences, and records every vertex position (and
// every material's lion palette) after each call. The sequences include
// clamped inputs, a non-finite call, a changed swim span and a call for a
// different kind, so refusals are recorded too.
//
//   deformer_golden <repo-root> <fixture-dir>            compare (the ctest)
//   deformer_golden <repo-root> <fixture-dir> --record   write the fixtures
//
// The fixtures were recorded from the code before the E0 generic-slot move
// (docs/plans/2026-10-16-saltwater-seahorses.md, E0 "Regression guard"); the
// comparison is exact, so any change in arithmetic order fails it.
//
// After every step it also checks the face normals: each face's stored normal
// must equal a fresh CalculateNormal of its deformed vertices within 1e-4
// (docs/plans/2026-11-01-deformer-face-normals.md). Degenerate faces, which
// keep their last normal by design, are skipped.
//
//   deformer_golden <repo-root> <fixture-dir> --bench    time each kind's Deform call
//   deformer_golden <repo-root> <out-dir> --dump         write <case>.json: faces, rest and
//       per-step positions (input to scripts/deformer-normals-mockups.py)
#include <renderassets/rendacto.hp>
#include <gfx/pixelmap.hp>
#include <gfx/material.hp>
#include <memory/lmalloc.hp>
#include <hal/halbase.h>
#include <streams/binstrm.hp>

#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <limits>
#include <string>
#include <vector>

namespace {

struct TestCallbacks : public GfxCallbacks
{
    PixelMap pixelMap{PixelMap::MEMORY_VIDEO, 256, 256};
    LookupTextureStruct LookupTexture(const char*, int32) const override
    {
        return LookupTextureStruct(emptyTexture, pixelMap);
    }
protected:
    void _Validate() const override {}
};

std::vector<char> ReadFile(const std::string& path)
{
    std::vector<char> bytes;
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) { std::fprintf(stderr, "deformer_golden: cannot open %s\n", path.c_str()); std::exit(2); }
    char buffer[65536];
    size_t n;
    while ((n = std::fread(buffer, 1, sizeof(buffer), f)) > 0) bytes.insert(bytes.end(), buffer, buffer + n);
    std::fclose(f);
    return bytes;
}

// One recorded state: positions as raw float bits, then each material's palette.
void Capture(RenderActor3D& actor, std::vector<uint32_t>& out)
{
    RenderObject3D& object = const_cast<RenderObject3D&>(*actor.GetRenderObject());
    const int count = object.GetVertexCount();
    const Vertex3D* vertices = object.GetWrittableVertexList();
    out.push_back(uint32_t(count));
    for (int i = 0; i < count; ++i) {
        const float xyz[3] = {vertices[i].position.X().AsFloat(), vertices[i].position.Y().AsFloat(),
                              vertices[i].position.Z().AsFloat()};
        for (float f : xyz) { uint32_t bits; std::memcpy(&bits, &f, 4); out.push_back(bits); }
    }
    out.push_back(uint32_t(object.GetMaterialCount()));
    for (int i = 0; i < object.GetMaterialCount(); ++i) {
        out.push_back(object.GetMaterial(i).PaletteDark());
        out.push_back(object.GetMaterial(i).PaletteLight());
    }
}

// Largest component difference between each face's stored normal and a fresh
// CalculateNormal of its current vertices. Returns the number of faces checked.
int CheckNormals(RenderActor3D& actor, float& maxError)
{
    RenderObject3D& object = const_cast<RenderObject3D&>(*actor.GetRenderObject());
    const Vertex3D* vertices = object.GetWrittableVertexList();
    const TriFace* faces = object.GetWritableFaceList();
    int checked = 0;
    for (int f = 0; f < object.GetFaceCount(); ++f) {
        const Vector3 v0 = PSToVector3(vertices[faces[f].v1Index].position);
        const Vector3 v1 = PSToVector3(vertices[faces[f].v2Index].position);
        const Vector3 v2 = PSToVector3(vertices[faces[f].v3Index].position);
        const Vector3 cross = (v1 - v0).CrossProduct(v2 - v0);
        const float len = std::sqrt(cross.X().AsFloat()*cross.X().AsFloat() + cross.Y().AsFloat()*cross.Y().AsFloat()
                                    + cross.Z().AsFloat()*cross.Z().AsFloat());
        if (!(len > 1e-12f)) continue;                   // degenerate: keeps its last normal
        const Vector3 fresh = CalculateNormal(v0, v1, v2);
        const Vector3 stored = PSToVector3(faces[f].normal);
        for (int k = 0; k < 3; ++k) {
            const float e = std::fabs(fresh[k].AsFloat() - stored[k].AsFloat());
            if (!(e <= maxError)) maxError = std::isfinite(e) ? e : std::numeric_limits<float>::infinity();
        }
        ++checked;
    }
    return checked;
}

const float NormalTolerance = 1e-4f;

struct Case
{
    const char* name;
    const char* mesh;
    std::vector<std::function<void(RenderActor&)>> steps;
};

const float NaN = std::numeric_limits<float>::quiet_NaN();
const float ArowanaMin = -3.5563973f, ArowanaMax = 2.9436027f;   // arowana.py TAIL_X / NOSE_X
const float GobyMin = -0.46f, GobyMax = 0.34f;                   // goby.SPAN

std::vector<Case> Cases()
{
    using A = RenderActor&;
    std::vector<Case> cases;
    cases.push_back({"fish_clownfish_body", "wflevels/aquarium/clownfish_body.iff", {
        [](A a) { a.SetFishDeformation(0.f, .04f); },
        [](A a) { a.SetFishDeformation(.37f, .12f); },
        [](A a) { a.SetFishDeformation(1.73f, .5f); },            // amplitude clamps to .12
        [](A a) { a.SetFishDeformation(-.6f, .02f); },
        [](A a) { a.SetFishDeformation(NaN, .05f); },             // refused: not finite
        [](A a) { a.SetJellyDeformation(.5f, .2f, 0.f, 0.f); },   // refused: fish is bound
    }});
    cases.push_back({"fin_betta_tail", "wflevels/aquarium_betta/tail.iff", {
        [](A a) { a.SetFinDeformation(0.f, .065f, 0.f, 1.f); },
        [](A a) { a.SetFinDeformation(.29f, .1f, .05f, .85f); },
        [](A a) { a.SetFinDeformation(1.56f, .4f, -.3f, .3f); },  // clamps
        [](A a) { a.SetFinDeformation(-.2f, .03f, .1f, 1.1f); },
        [](A a) { a.SetFishDeformation(.3f, .05f); },             // refused: fin is bound
    }});
    cases.push_back({"swim_arowana_body", "wflevels/aquarium_arowana/ar_body.iff", {
        [](A a) { a.SetSwimDeformation(.1f, .05f, .02f, .3f, .01f, ArowanaMin, ArowanaMax); },
        [](A a) { a.SetSwimDeformation(.6f, .2f, -.1f, .7f, .04f, ArowanaMin, ArowanaMax); },
        [](A a) { a.SetSwimDeformation(2.3f, 5.f, .9f, -.4f, .5f, ArowanaMin, ArowanaMax); },  // clamps
        [](A a) { a.SetSwimDeformation(.4f, .1f, 0.f, 0.f, 0.f, -3.f, ArowanaMax); },          // refused: span changed
        [](A a) { a.SetSwimDeformation(-.35f, .3f, .15f, .2f, .02f, ArowanaMin, ArowanaMax); },
    }});
    cases.push_back({"swim_goby_body", "wflevels/aquarium_plants/rainbow_goby_body.iff", {
        [](A a) { a.SetSwimDeformation(.2f, .02f, .004f, .1f, .008f, GobyMin, GobyMax); },
        [](A a) { a.SetSwimDeformation(.75f, .06f, -.03f, .9f, .012f, GobyMin, GobyMax); },
        [](A a) { a.SetSwimDeformation(1.4f, 1.f, -.8f, 3.f, .3f, GobyMin, GobyMax); },      // clamps
        [](A a) { a.SetSwimDeformation(.2f, .02f, 0.f, .1f, .008f, GobyMin, GobyMax+.0005f); }, // refused: span
    }});
    cases.push_back({"swim_goby_fins", "wflevels/aquarium_plants/rainbow_goby_fins.iff", {
        [](A a) { a.SetSwimDeformation(.2f, .02f, .004f, .1f, .008f, GobyMin, GobyMax); },
        [](A a) { a.SetSwimDeformation(.75f, .06f, -.03f, .9f, .12f, GobyMin, GobyMax); },
        [](A a) { a.SetSwimDeformation(-.4f, .03f, .01f, -1.6f, .3f, GobyMin, GobyMax); },   // fin amp clamps
    }});
    cases.push_back({"jelly_bell", "wflevels/aquarium_jellyfish/bell.iff", {
        [](A a) { a.SetJellyDeformation(0.f, 0.f, 0.f, 0.f); },
        [](A a) { a.SetJellyDeformation(.6f, .3f, .01f, -.01f); },
        [](A a) { a.SetJellyDeformation(1.5f, 2.7f, .1f, -.1f); },  // clamps
        [](A a) { a.SetJellyDeformation(.2f, -.4f, -.02f, .02f); },
        [](A a) { a.SetJellyDeformation(.2f, NaN, 0.f, 0.f); },     // refused: not finite
    }});
    cases.push_back({"lion_lionfish", "wflevels/aquarium_lionfish/lionfish.iff", {
        [](A a) { a.SetLionPose(0.f, 0.f, 0.f, 0.f, 0x202020u, 0xf0e0d0u); },
        [](A a) { a.SetLionPose(.3f, .7f, -.4f, .5f, 0x401010u, 0xffeeddu); },
        [](A a) { a.SetLionPose(1.8f, 2.f, 3.f, -1.f, 0x000000u, 0xffffffu); },  // clamps
        [](A a) { a.SetLionPose(-.25f, .5f, .2f, 1.f, 0x123456u, 0x654321u); },
        [](A a) { a.SetFinDeformation(.1f, .1f, 0.f, 1.f); },                    // refused: lion is bound
    }});
    return cases;
}

} // namespace

int main(int argc, char** argv)
{
    const bool modeOk = argc == 3 || (argc == 4 && (std::strcmp(argv[3], "--record") == 0 ||
                        std::strcmp(argv[3], "--bench") == 0 || std::strcmp(argv[3], "--dump") == 0));
    if (!modeOk) {
        std::fprintf(stderr, "usage: deformer_golden <repo-root> <fixture-dir> [--record|--bench|--dump]\n");
        return 2;
    }
    const std::string root = argv[1], fixtures = argv[2];
    const bool record = argc > 3 && std::strcmp(argv[3], "--record") == 0;
    const bool bench = argc > 3 && std::strcmp(argv[3], "--bench") == 0;
    const bool dump = argc > 3 && std::strcmp(argv[3], "--dump") == 0;

    static std::vector<char> scratch(4 << 20), heap(256 << 20);
    _HALScratchLmalloc = new LMalloc(scratch.data(), scratch.size() MEMORY_NAMED(COMMA "golden-scratch"));
    LMalloc memory(heap.data(), heap.size() MEMORY_NAMED(COMMA "golden-heap"));
    TestCallbacks callbacks;

    int failures = 0;
    for (const Case& c : Cases()) {
        std::vector<char> bytes = ReadFile(root + "/" + c.mesh);
        binistream input(bytes.data(), int32(bytes.size()));
        RenderActor3D actor(memory, input, 0, callbacks);
        if (bench) {
            // The second step is a successful pose for every kind: bind on the
            // first call, then time the steady-state Deform calls alone.
            const int calls = 20000;
            c.steps[0](actor);
            const auto start = std::chrono::steady_clock::now();
            for (int i = 0; i < calls; ++i) c.steps[1](actor);
            const double ns = std::chrono::duration<double, std::nano>(std::chrono::steady_clock::now() - start).count() / calls;
            const RenderObject3D& object = *actor.GetRenderObject();
            std::printf("bench %-22s %5d vertices %5d faces %9.0f ns per Deform call\n", c.name,
                        const_cast<RenderObject3D&>(object).GetVertexCount(), object.GetFaceCount(), ns);
            continue;
        }
        if (dump) {
            RenderObject3D& object = const_cast<RenderObject3D&>(*actor.GetRenderObject());
            const std::string path = fixtures + "/" + c.name + ".json";
            FILE* f = std::fopen(path.c_str(), "w");
            if (!f) { std::fprintf(stderr, "deformer_golden: cannot write %s\n", path.c_str()); return 2; }
            auto positions = [&]() {
                const Vertex3D* v = object.GetWrittableVertexList();
                std::fprintf(f, "[");
                for (int i = 0; i < object.GetVertexCount(); ++i)
                    std::fprintf(f, "%s%.7g,%.7g,%.7g", i ? "," : "", v[i].position.X().AsFloat(),
                                 v[i].position.Y().AsFloat(), v[i].position.Z().AsFloat());
                std::fprintf(f, "]");
            };
            const TriFace* faces = object.GetWritableFaceList();
            std::fprintf(f, "{\"name\":\"%s\",\"mesh\":\"%s\",\"faces\":[", c.name, c.mesh);
            for (int i = 0; i < object.GetFaceCount(); ++i)
                std::fprintf(f, "%s%d,%d,%d", i ? "," : "", faces[i].v1Index, faces[i].v2Index, faces[i].v3Index);
            std::fprintf(f, "],\"rest\":");
            positions();
            std::fprintf(f, ",\"steps\":[");
            for (size_t s = 0; s < c.steps.size(); ++s) { c.steps[s](actor); if (s) std::fprintf(f, ","); positions(); }
            std::fprintf(f, "]}\n");
            std::fclose(f);
            std::printf("dumped %-22s %s\n", c.name, path.c_str());
            continue;
        }
        std::vector<uint32_t> got;
        got.push_back(uint32_t(c.steps.size()));
        float normalError = 0;
        int normalFaces = 0;
        for (const auto& step : c.steps) {
            step(actor); Capture(actor, got);
            normalFaces = CheckNormals(actor, normalError);
        }
        if (!record) {
            if (normalError <= NormalTolerance) {
                std::printf("ok   %-22s normals: %d faces, max error %.2g\n", c.name, normalFaces, normalError);
            } else {
                ++failures;
                std::printf("FAIL %-22s normals: max error %.3g over %d faces (tolerance %.0e)\n",
                            c.name, normalError, normalFaces, NormalTolerance);
            }
        }

        const std::string path = fixtures + "/" + c.name + ".bin";
        if (record) {
            FILE* f = std::fopen(path.c_str(), "wb");
            if (!f || std::fwrite(got.data(), 4, got.size(), f) != got.size()) {
                std::fprintf(stderr, "deformer_golden: cannot write %s\n", path.c_str()); return 2;
            }
            std::fclose(f);
            std::printf("recorded %-22s %zu steps, %zu words\n", c.name, c.steps.size(), got.size());
            continue;
        }
        std::vector<char> want = ReadFile(path);
        size_t firstDiff = SIZE_MAX, diffs = 0;
        if (want.size() != got.size() * 4) firstDiff = 0, diffs = 1;
        else for (size_t i = 0; i < got.size(); ++i) {
            uint32_t w; std::memcpy(&w, want.data() + i * 4, 4);
            if (w != got[i]) { if (firstDiff == SIZE_MAX) firstDiff = i; ++diffs; }
        }
        if (diffs) {
            ++failures;
            std::printf("FAIL %-22s %zu words differ (first at word %zu; sizes %zu vs %zu)\n",
                        c.name, diffs, firstDiff, want.size() / 4, got.size());
        } else {
            std::printf("ok   %-22s %zu steps, %zu words identical\n", c.name, c.steps.size(), got.size());
        }
    }
    return failures ? 1 : 0;
}
