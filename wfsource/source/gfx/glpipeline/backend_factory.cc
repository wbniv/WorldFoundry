//=============================================================================
// gfx/glpipeline/backend_factory.cc: RendererBackend singleton accessor
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// Modern (VBO + GLSL) backend on Linux + Android.
// Metal backend on iOS (hal/ios/backend_metal.mm).
// Legacy fixed-function backend retired Android Phase 0 step 4c/f.
//============================================================================

#include <gfx/renderer_backend.hp>

#if defined(WF_TARGET_IOS)
RendererBackend* MetalBackendInstance();
#else
RendererBackend* ModernBackendInstance();
#endif

RendererBackend& RendererBackendGet()
{
#if defined(WF_TARGET_IOS)
    static RendererBackend* s = MetalBackendInstance();
#else
    static RendererBackend* s = ModernBackendInstance();
#endif
    return *s;
}
