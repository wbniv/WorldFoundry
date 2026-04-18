//=============================================================================
// hal/android/asset_accessor_posix.cc: POSIX AssetAccessor for Android builds
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Temporary POSIX impl mirroring hal/linux/asset_accessor_posix.cc. Works
// during development when the game is sideloaded with cd.iff pushed to
// /data/local/tmp or similar. The real Android backend (AAssetManager) is
// a peer implementation landing in Phase 3 step 3.
//=============================================================================

#include <hal/asset_accessor.hp>

#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>

struct AssetHandle
{
    int fd;
    int64_t size;
};

class PosixAssetAccessor : public AssetAccessor
{
public:
    AssetHandle* OpenForRead(const char* path) override;
    void         Close(AssetHandle* handle) override;
    int64_t      Size(AssetHandle* handle) override;
    int64_t      SeekAbsolute(AssetHandle* handle, int64_t offset) override;
    int64_t      Read(AssetHandle* handle, void* buffer, int64_t count) override;
};

AssetHandle*
PosixAssetAccessor::OpenForRead(const char* path)
{
    assert(path);
    int fd = ::open(path, O_RDONLY);
    if (fd < 0) return nullptr;

    struct stat st;
    if (::fstat(fd, &st) < 0 || st.st_size <= 0)
    {
        ::close(fd);
        return nullptr;
    }

    AssetHandle* h = new AssetHandle;
    h->fd   = fd;
    h->size = static_cast<int64_t>(st.st_size);
    return h;
}

void
PosixAssetAccessor::Close(AssetHandle* handle)
{
    assert(handle);
    ::close(handle->fd);
    delete handle;
}

int64_t
PosixAssetAccessor::Size(AssetHandle* handle)
{
    assert(handle);
    return handle->size;
}

int64_t
PosixAssetAccessor::SeekAbsolute(AssetHandle* handle, int64_t offset)
{
    assert(handle);
    off_t r = ::lseek(handle->fd, static_cast<off_t>(offset), SEEK_SET);
    return (r == static_cast<off_t>(-1)) ? -1 : static_cast<int64_t>(r);
}

int64_t
PosixAssetAccessor::Read(AssetHandle* handle, void* buffer, int64_t count)
{
    assert(handle);
    assert(buffer);
    ssize_t r = ::read(handle->fd, buffer, static_cast<size_t>(count));
    return static_cast<int64_t>(r);
}

// Installed at HAL startup (see hal/android/platform.cc).
AssetAccessor*
HALCreatePosixAssetAccessor()
{
    return new PosixAssetAccessor;
}
