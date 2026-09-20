//=============================================================================
// gfx/glpipeline/backend_factory.cc: RendererBackend singleton accessor
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// Modern (VBO + GLSL) backend on Linux + Android.
// Metal backend on BOTH Apple targets (gfx/metal/backend_metal.mm) — macOS
// joined iOS in Phase 2 of docs/plans/2026-09-20-macos-metal-renderer.md, which
// also moved that file out of hal/ios/ since it is renderer code, not iOS HAL
// code (D3). macOS previously used the headless no-op stub
// (engine/stubs/renderer_stub.cc); that stub is still built and still selected
// by nothing, kept as the fallback if a machine has no Metal device.
// Legacy fixed-function backend retired Android Phase 0 step 4c/f.
//============================================================================

#include <gfx/renderer_backend.hp>

#if defined(WF_TARGET_IOS) || defined(WF_TARGET_MACOS)
RendererBackend* MetalBackendInstance();
#else
RendererBackend* ModernBackendInstance();
#endif

RendererBackend& RendererBackendGet()
{
#if defined(WF_TARGET_IOS) || defined(WF_TARGET_MACOS)
    static RendererBackend* s = MetalBackendInstance();
#else
    static RendererBackend* s = ModernBackendInstance();
#endif
    return *s;
}
