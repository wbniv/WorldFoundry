//=============================================================================
// hal/ios/platform.mm: iOS platform-specific startup stub
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 1: enough symbols exist so the .app links and reaches a black
// UIViewController without crashing on HALGetAssetAccessor(). The UIKit
// entry point (native_app_entry.mm) owns app startup; the actual render
// + game loop hookup is deferred to Phase 2 (Metal backend).
//=============================================================================

#define _PLATFORM_C

#include <hal/hal.h>
#include <hal/_platfor.h>
#include <hal/salloc.hp>
#include <hal/asset_accessor.hp>

#import <Foundation/Foundation.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>

// Defined in hal/ios/asset_accessor_nsbundle.mm — wraps NSBundle's bundled
// resource lookup. Installed below from _PlatformSpecificInit.
extern "C" AssetAccessor* HALCreateNSBundleAccessor();

//=============================================================================

bool bFullScreen = true;

char szAppName[PATH_MAX];

int _halWindowWidth  = 800;
int _halWindowHeight = 600;
int _halWindowXPos   = 0;
int _halWindowYPos   = 0;

SAlloc* stacks = nullptr;
void*   halMemory = nullptr;

//=============================================================================
// UIKit layer (native_app_entry.mm) calls this when the CAMetalLayer /
// UIViewController view reports its first resolved size.
// Phase 2 will also forward to gfx/gl/display.cc's wfWindowWidth/Height once
// the gfx/ dir is in the iOS build; for Phase 1 we only need the HAL globals.

extern "C" void
WFIosSetSurfaceSize(int w, int h)
{
    _halWindowWidth  = w;
    _halWindowHeight = h;
}

//=============================================================================

void
_PlatformSpecificInit(int /*argc*/, char** /*argv*/,
                      int /*maxTasks*/, int /*maxMessages*/, int /*maxPorts*/)
{
    halMemory = malloc(cbHalLmalloc);
    ValidatePtr(halMemory);
    _HALLmalloc = new LMalloc(halMemory, cbHalLmalloc MEMORY_NAMED(COMMA "HalLMalloc"));
    assert(ValidPtr(_HALLmalloc));

    _HALDmalloc = new (*_HALLmalloc) DMalloc(*_HALLmalloc, HAL_DMALLOC_SIZE
                                             MEMORY_NAMED(COMMA "HALDmalloc"));
    ValidatePtr(_HALDmalloc);

    AssetAccessor* accessor = HALCreateNSBundleAccessor();
    if (!accessor)
    {
        FatalError("HALCreateNSBundleAccessor returned null");
    }
    HALSetAssetAccessor(accessor);
}

//=============================================================================

void
_PlatformSpecificUnInit(void)
{
    if (stacks) { delete stacks; stacks = nullptr; }
    MEMORY_DELETE((*_HALLmalloc), _HALDmalloc, DMalloc);
    delete _HALLmalloc;
    free(halMemory);
}

//=============================================================================

void
FatalError(const char* string)
{
    NSLog(@"FatalError: %s", string);
    std::abort();
}
