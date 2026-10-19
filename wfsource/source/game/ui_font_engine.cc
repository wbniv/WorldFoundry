//==============================================================================
// game/ui_font_engine.cc — load the UI atlas from cd.iff, draw its quads
// Copyright ( c ) 2026 World Foundry Group
// This program is free software; you can redistribute it and/or modify it
// under the terms of the GNU General Public License Version 2.
// This program is distributed without ANY WARRANTY. See www.fsf.org.
//==============================================================================
// Description: the engine half of wfui (ui_font.hp): the F6 start-up check
// and the atlas texture's lifetime. Plan: docs/plans/2026-10-17-settings-editor-font.md.
//==============================================================================
#include "ui_font.hp"

#include <gfx/renderer_backend.hp>
#include <hal/asset_accessor.hp>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#if defined(__ANDROID__)
#include <android/log.h>
#endif

namespace wfui
{
namespace
{
std::vector<uint8_t> gBytes;         // the bundle, kept for the process's lifetime
RBTextureHandle gTexture = nullptr;
unsigned gGeneration = 0;

[[noreturn]] void Unavailable(const std::string& reason)
{
    std::fprintf(stderr, "UI_FONT unavailable: %s\n", reason.c_str());
    std::fflush(stderr);
#if defined(__ANDROID__)
    __android_log_print(ANDROID_LOG_ERROR, "wf_game", "UI_FONT unavailable: %s", reason.c_str());
#endif
    std::exit(1);
}

uint32_t U32(const uint8_t* p) { return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24; }

// The whole asset, or false if the accessor cannot open it.
bool ReadAll(AssetAccessor& a, AssetHandle* h, int64_t offset, int64_t size, std::vector<uint8_t>& out)
{
    out.assign(size_t(size), 0);
    return a.SeekAbsolute(h, offset) == offset && a.Read(h, out.data(), size) == size;
}

// The UIFT chunk of a GAME bundle (cdpack writes it as the last TOC entry).
std::string FromBundle(AssetAccessor& a, AssetHandle* h, const char* name)
{
    uint8_t sector[2048];
    const int64_t size = a.Size(h);
    if (size < int64_t(sizeof(sector)) || a.SeekAbsolute(h, 0) != 0 || a.Read(h, sector, sizeof(sector)) != int64_t(sizeof(sector)))
        return std::string(name) + " is shorter than its TOC sector";
    if (std::memcmp(sector + 8, "TOC\0", 4) != 0) return std::string(name) + " has no TOC";
    const uint32_t tocBytes = U32(sector + 12);
    if (tocBytes % 12 != 0 || 16 + size_t(tocBytes) > sizeof(sector)) return std::string(name) + " has a malformed TOC";
    for (uint32_t at = 16; at < 16 + tocBytes; at += 12)
    {
        if (U32(sector + at) != kChunkTag) continue;
        const uint32_t offset = U32(sector + at + 4), bytes = U32(sector + at + 8);
        std::vector<uint8_t> chunk;
        if (bytes < 8 || int64_t(offset) + int64_t(bytes) > size || !ReadAll(a, h, offset, bytes, chunk))
            return std::string(name) + "'s UIFT chunk lies outside the file";
        if (U32(chunk.data()) != kChunkTag || size_t(U32(chunk.data() + 4)) + 8 != chunk.size())
            return std::string(name) + "'s UIFT chunk header does not match its TOC entry";
        gBytes.assign(chunk.begin() + 8, chunk.end());
        return "";
    }
    return std::string(name) + " has no UIFT chunk (repack it with cdpack, which adds wfsource/source/game/ui-font.wfga)";
}

// Reads `name` (a GAME bundle or a bare WFGA file) into gBytes. Returns false if
// it cannot be opened, so the next candidate is tried; a file that opens but
// holds no usable font is final.
bool TryRead(AssetAccessor& a, const char* name, std::string& error)
{
    AssetHandle* h = a.OpenForRead(name);
    if (!h) return false;
    uint8_t magic[4] = {};
    const int64_t size = a.Size(h);
    if (size < 4 || a.Read(h, magic, 4) != 4) error = std::string(name) + " is empty";
    else if (!std::memcmp(magic, "GAME", 4)) error = FromBundle(a, h, name);
    else if (!std::memcmp(magic, "WFGA", 4)) { if (!ReadAll(a, h, 0, size, gBytes)) error = std::string("cannot read ") + name; }
    else error = std::string(name) + " is neither a GAME bundle nor a WFGA atlas";
    a.Close(h);
    return true;
}
}

void LoadOrDie(bool levelOverride)
{
    if (Loaded()) return;
    AssetAccessor& accessor = HALGetAssetAccessor();
    // cd.iff is every app's bundle; the web build preloads the bare atlas; Linux desktop
    // -L runs from any directory fall back to the source tree's own bake.
    const char* candidates[] = {"cd.iff", kFileName,
#if defined(WF_UI_FONT_SOURCE_PATH)
                                WF_UI_FONT_SOURCE_PATH,
#endif
    };
    std::string first;
    bool found = false;
    for (const char* name : candidates)
    {
        std::string error;
        if (!TryRead(accessor, name, error)) continue;
        if (error.empty()) { found = true; break; }
        // The game's own cd.iff must carry the font. A -L run plays no cd.iff, so one
        // that happens to sit in its directory (wflevels/cd.iff, say) is not its bundle.
        if (!levelOverride) Unavailable(error);
        if (first.empty()) first = error;
    }
    if (!found) Unavailable(!first.empty() ? first : std::string("no cd.iff or ") + kFileName + " among the packaged assets");
    const char* invalid = nullptr;
    if (!Load(gBytes.data(), gBytes.size(), invalid)) Unavailable(std::string("invalid atlas: ") + invalid);
    std::fprintf(stderr, "UI_FONT %dx%d atlas, %zu bytes\n", Catalog().Width(), Catalog().Height(), gBytes.size());
}

void Draw(const bitmaptext::Quad* quads, int count, int width, int height)
{
    if (count <= 0 || width <= 0 || height <= 0) return;
    if (!Loaded()) Unavailable("text drawn before PIGSMain loaded the font");
    RendererBackend& rb = RendererBackendGet();
    if (!rb.BitmapTextSupported()) return;     // the headless backend draws nothing at all
    if (!gTexture || gGeneration != rb.TextureGeneration())
    {
        // A new GL context (Android context loss) already freed the old name.
        gGeneration = rb.TextureGeneration();
        gTexture = rb.CreateTexture(Catalog().Width(), Catalog().Height(), RB_TEX_COVERAGE8, Catalog().Pixels());
        if (!gTexture) Unavailable("the atlas texture could not be created");
    }
    rb.DrawGlyphs(quads, count, width, height, gTexture, false);
}
}
