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
#include <renderassets/rendacto.hp>
#include <gfx/pixelmap.hp>
#include <gfx/material.hp>
#include <memory/lmalloc.hp>
#include <hal/halbase.h>
#include <streams/binstrm.hp>

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
    if (argc < 3 || (argc > 3 && std::strcmp(argv[3], "--record") != 0)) {
        std::fprintf(stderr, "usage: deformer_golden <repo-root> <fixture-dir> [--record]\n");
        return 2;
    }
    const std::string root = argv[1], fixtures = argv[2];
    const bool record = argc > 3;

    static std::vector<char> scratch(4 << 20), heap(256 << 20);
    _HALScratchLmalloc = new LMalloc(scratch.data(), scratch.size() MEMORY_NAMED(COMMA "golden-scratch"));
    LMalloc memory(heap.data(), heap.size() MEMORY_NAMED(COMMA "golden-heap"));
    TestCallbacks callbacks;

    int failures = 0;
    for (const Case& c : Cases()) {
        std::vector<char> bytes = ReadFile(root + "/" + c.mesh);
        binistream input(bytes.data(), int32(bytes.size()));
        RenderActor3D actor(memory, input, 0, callbacks);
        std::vector<uint32_t> got;
        got.push_back(uint32_t(c.steps.size()));
        for (const auto& step : c.steps) { step(actor); Capture(actor, got); }

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
