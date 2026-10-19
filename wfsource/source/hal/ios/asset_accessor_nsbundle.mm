//=============================================================================
// hal/ios/asset_accessor_nsbundle.mm: NSBundle backend for AssetAccessor
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// On iOS, bundled resources (cd.iff, level0.mid, soundfont) live inside the
// .app as flat files that NSBundle locates and returns file-system paths for.
// Unlike Android's AAssetManager, we can use regular POSIX FILE*/fread on
// the resolved path. This accessor wraps them in the AssetAccessor shape so
// DiskFileHD sees the same interface as the other backends.
//=============================================================================

#include <hal/asset_accessor.hp>

#import <Foundation/Foundation.h>

#include <cstdio>
#include <cstring>
#include <sys/stat.h>

struct AssetHandle
{
    FILE*   fp;
    int64_t size;
};

class NSBundleAccessor : public AssetAccessor
{
public:
    AssetHandle* OpenForRead(const char* path) override;
    void         Close(AssetHandle* handle) override;
    int64_t      Size(AssetHandle* handle) override;
    int64_t      SeekAbsolute(AssetHandle* handle, int64_t offset) override;
    int64_t      Read(AssetHandle* handle, void* buffer, int64_t count) override;
};

AssetHandle*
NSBundleAccessor::OpenForRead(const char* path)
{
    assert(path);
    @autoreleasepool {
        // Engine asks for "cd.iff" — look it up as a top-level bundle resource.
        // splitpath any leading directory so ext/stem live in separate args
        // the way NSBundle expects.
        NSString* full = [NSString stringWithUTF8String:path];
        NSString* stem = [[full lastPathComponent] stringByDeletingPathExtension];
        NSString* ext  = [full pathExtension];
        if ([ext length] == 0) ext = nil;

        NSString* resolved = [[NSBundle mainBundle] pathForResource:stem ofType:ext];
        if (!resolved) return nullptr;

        const char* cpath = [resolved fileSystemRepresentation];
        FILE* fp = fopen(cpath, "rb");
        if (!fp) return nullptr;

        struct stat st;
        if (fstat(fileno(fp), &st) != 0) { fclose(fp); return nullptr; }

        AssetHandle* h = new AssetHandle;
        h->fp   = fp;
        h->size = st.st_size;
        return h;
    }
}

void
NSBundleAccessor::Close(AssetHandle* handle)
{
    assert(handle);
    fclose(handle->fp);
    delete handle;
}

int64_t
NSBundleAccessor::Size(AssetHandle* handle)
{
    assert(handle);
    return handle->size;
}

int64_t
NSBundleAccessor::SeekAbsolute(AssetHandle* handle, int64_t offset)
{
    assert(handle);
    if (fseeko(handle->fp, (off_t)offset, SEEK_SET) != 0) return -1;
    return (int64_t)ftello(handle->fp);
}

int64_t
NSBundleAccessor::Read(AssetHandle* handle, void* buffer, int64_t count)
{
    assert(handle);
    assert(buffer);
    return (int64_t)fread(buffer, 1, (size_t)count, handle->fp);
}

// Installed at HAL startup (hal/ios/platform.mm::_PlatformSpecificInit).
extern "C" AssetAccessor*
HALCreateNSBundleAccessor()
{
    return new NSBundleAccessor();
}
