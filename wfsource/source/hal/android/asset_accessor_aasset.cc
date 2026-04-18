//=============================================================================
// hal/android/asset_accessor_aasset.cc: AAssetManager backend for AssetAccessor
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Android assets (anything bundled in the APK under src/main/assets/) live
// inside the package and are opaque — no file descriptor, just an opaque
// AAsset* with its own read / seek / close / length APIs. This accessor
// wraps them in the AssetAccessor shape so DiskFileHD in the engine's HAL
// sees exactly the same interface as the POSIX backend on desktop.
//=============================================================================

#include <hal/asset_accessor.hp>

#include <android/asset_manager.h>

// native_app_entry.cc stashes app->activity->assetManager here at
// android_main entry so this backend can grab it without threading it
// through HALStart / _PlatformSpecificInit.
extern "C" AAssetManager* WFAndroidGetAssetManager();

struct AssetHandle
{
    AAsset* asset;
    int64_t size;
};

class AAssetAccessor : public AssetAccessor
{
public:
    explicit AAssetAccessor(AAssetManager* mgr) : _mgr(mgr) {}

    AssetHandle* OpenForRead(const char* path) override;
    void         Close(AssetHandle* handle) override;
    int64_t      Size(AssetHandle* handle) override;
    int64_t      SeekAbsolute(AssetHandle* handle, int64_t offset) override;
    int64_t      Read(AssetHandle* handle, void* buffer, int64_t count) override;

private:
    AAssetManager* _mgr;
};

AssetHandle*
AAssetAccessor::OpenForRead(const char* path)
{
    assert(path);
    // AASSET_MODE_RANDOM: we seek around in cd.iff based on the FORM index,
    // so the accessor must not use the (faster, streaming) unbuffered mode.
    AAsset* a = AAssetManager_open(_mgr, path, AASSET_MODE_RANDOM);
    if (!a) return nullptr;

    AssetHandle* h = new AssetHandle;
    h->asset = a;
    h->size  = AAsset_getLength64(a);
    return h;
}

void
AAssetAccessor::Close(AssetHandle* handle)
{
    assert(handle);
    AAsset_close(handle->asset);
    delete handle;
}

int64_t
AAssetAccessor::Size(AssetHandle* handle)
{
    assert(handle);
    return handle->size;
}

int64_t
AAssetAccessor::SeekAbsolute(AssetHandle* handle, int64_t offset)
{
    assert(handle);
    return AAsset_seek64(handle->asset, offset, SEEK_SET);
}

int64_t
AAssetAccessor::Read(AssetHandle* handle, void* buffer, int64_t count)
{
    assert(handle);
    assert(buffer);
    return AAsset_read(handle->asset, buffer, static_cast<size_t>(count));
}

// Installed at HAL startup (see hal/android/platform.cc). Returns nullptr
// if the NativeActivity hasn't yet given us an AAssetManager — which would
// be a programmer error: HALStart shouldn't run before android_main has
// stashed it.
extern "C" AssetAccessor*
HALCreateAAssetAccessor()
{
    AAssetManager* mgr = WFAndroidGetAssetManager();
    if (!mgr) return nullptr;
    return new AAssetAccessor(mgr);
}
