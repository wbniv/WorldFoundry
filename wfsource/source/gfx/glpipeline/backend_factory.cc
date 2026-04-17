//=============================================================================
// gfx/glpipeline/backend_factory.cc: RendererBackend singleton selection
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// Android → modern (GLES 3.0 has no fixed-function pipeline).
// Linux   → legacy by default; WF_RENDERER=modern flips to the VBO+shader
//           path for regression testing.
//============================================================================

#include <gfx/renderer_backend.hp>
#include <cstdlib>
#include <cstring>

// Each backend TU exposes an instance accessor.
RendererBackend* LegacyBackendInstance();
RendererBackend* ModernBackendInstance();

namespace
{

RendererBackend* PickBackend()
{
#if defined(__ANDROID__)
    return ModernBackendInstance();
#else
    const char* sel = std::getenv("WF_RENDERER");
    if (sel && std::strcmp(sel, "modern") == 0)
        return ModernBackendInstance();
    return LegacyBackendInstance();
#endif
}

}  // namespace

RendererBackend& RendererBackendGet()
{
    static RendererBackend* s = PickBackend();
    return *s;
}
