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

namespace {
class HeadlessBackend : public RendererBackend
{
public:
    void SetProjection(float, float, float, float) override {}
    void SetModelView(const Matrix34&) override {}
    void ResetModelView() override {}
    void SetAmbient(float, float, float) override {}
    void SetDirLight(int, float, float, float, float, float, float) override {}
    void SetLightingEnabled(bool) override {}
    void SetFog(float, float, float, float, float) override {}
    void SetFogEnabled(bool) override {}
    void DrawTriangle(const RBVertex&, const RBVertex&, const RBVertex&,
                      float, float, float, const PixelMap*, bool) override {}
    void EndFrame() override {}
    // ReloadProgram uses the base no-op default.
};
}  // namespace

RendererBackend* HeadlessBackendInstance()
{
    static HeadlessBackend s;
    return &s;
}

#endif  // WF_TARGET_MACOS
