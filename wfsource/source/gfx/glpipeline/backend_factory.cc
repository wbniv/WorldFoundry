//=============================================================================
// gfx/glpipeline/backend_factory.cc: RendererBackend singleton accessor
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// Modern (VBO + shader) backend is the only backend on both Linux and Android.
// The fixed-function legacy backend was retired after visual parity on
// snowgoons (Android port plan Phase 0 step 4c/f).
//============================================================================

#include <gfx/renderer_backend.hp>

RendererBackend* ModernBackendInstance();

RendererBackend& RendererBackendGet()
{
    static RendererBackend* s = ModernBackendInstance();
    return *s;
}
