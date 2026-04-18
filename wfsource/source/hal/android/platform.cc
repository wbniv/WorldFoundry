//=============================================================================
// hal/android/platform.cc: Android platform-specific startup stub
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 3 step 1: enough symbols exist so libwf_game.so links. The
// NativeActivity wrapper (Phase 3 step 2) owns the entry point and calls
// HALStart/HALStop, plus feeds _halWindow{Width,Height} from the actual
// surface dimensions when onNativeWindowCreated fires.
//=============================================================================

#define _PLATFORM_C

#include <hal/hal.h>
#include <hal/_platfor.h>
#include <hal/salloc.hp>
#include <hal/asset_accessor.hp>

#include <android/log.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>

// Installed below by _PlatformSpecificInit. Defined in
// hal/android/asset_accessor_aasset.cc — wraps AAssetManager_open from the
// APK bundle. native_app_entry.cc stashes the AAssetManager pointer before
// HALStart is entered.
extern "C" AssetAccessor* HALCreateAAssetAccessor();

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
// NativeActivity glue calls this once it has the ANativeWindow dimensions.

extern "C" void
WFAndroidSetSurfaceSize(int w, int h)
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

    AssetAccessor* accessor = HALCreateAAssetAccessor();
    if (!accessor)
    {
        FatalError("HALCreateAAssetAccessor returned null — "
                   "AAssetManager pointer not yet stashed");
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
    __android_log_print(ANDROID_LOG_FATAL, "wf_game", "FatalError: %s", string);
    std::abort();
}
