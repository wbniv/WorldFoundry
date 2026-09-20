//==============================================================================
// engine/stubs/renderer_stub.cc — headless no-op RendererBackend for the
// renderer-agnostic macOS desktop bring-up.
//
// macOS desktop boots with rendering as a TRUE no-op: no window, no Metal/GL
// context. WFGame still constructs a Display and calls RendererBackendGet()
// each frame (SetProjection / SetLightingEnabled / ResetModelView / EndFrame),
// so it needs a backend whose virtuals are all empty. Selected by
// gfx/glpipeline/backend_factory.cc when WF_TARGET_MACOS is defined.
//
// When the real Metal renderer lands (shared with iOS), this stub is replaced
// by MetalBackendInstance() in the factory.
//==============================================================================

#if defined(WF_TARGET_MACOS)

#include <gfx/renderer_backend.hp>
#include <cstdio>

namespace {
class HeadlessBackend : public RendererBackend
{
public:
    // Phase 1 instrumentation (docs/plans/2026-09-20-macos-metal-renderer.md):
    // the whole point of compiling gfx/glpipeline on macOS is to find out
    // whether real geometry reaches a backend with no GL and no window. Counting
    // DrawTriangle and printing it at EndFrame is the cheapest possible answer —
    // a non-zero, frame-stable number confirms §2.1's "the eight rend*.cc files
    // are backend-agnostic" thesis; a zero refutes it. Kept after Phase 1: it
    // costs one increment per triangle in a build that draws nothing anyway, and
    // it gives the Metal backend a reference count to match against.
    void SetProjection(float, float, float, float) override {}
    void SetModelView(const Matrix34&) override {}
    void ResetModelView() override {}
    void SetAmbient(float, float, float) override {}
    void SetDirLight(int, float, float, float, float, float, float) override {}
    void SetLightingEnabled(bool) override {}
    void SetFog(float, float, float, float, float) override {}
    void SetFogEnabled(bool) override {}
    void DrawTriangle(const RBVertex&, const RBVertex&, const RBVertex&,
                      float, float, float, const PixelMap*, bool) override
    {
        ++_trianglesThisFrame;
    }
    void EndFrame() override
    {
        ++_frame;
        std::printf("headless: frame %lu DrawTriangle=%lu (total %lu)\n",
                    (unsigned long)_frame,
                    (unsigned long)_trianglesThisFrame,
                    (unsigned long)(_trianglesTotal += _trianglesThisFrame));
        std::fflush(stdout);
        _trianglesThisFrame = 0;
    }
    // ReloadProgram uses the base no-op default.

private:
    unsigned long _frame              = 0;
    unsigned long _trianglesThisFrame = 0;
    unsigned long _trianglesTotal     = 0;
};
}  // namespace

RendererBackend* HeadlessBackendInstance()
{
    static HeadlessBackend s;
    return &s;
}

#endif  // WF_TARGET_MACOS
