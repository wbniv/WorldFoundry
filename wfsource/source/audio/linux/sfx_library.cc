#include <audio/sfx_library.hp>
#include <audio/buffer.hp>
#include <hal/asset_accessor.hp>
#include <cstdio>
#include <vector>
#include <memory>

static std::vector<std::vector<uint8_t>>        sSfxData;   // raw bytes — keep alive for SoundBuffer
static std::vector<std::unique_ptr<SoundBuffer>> sSfx;

static std::vector<uint8_t> loadAssetBytes(const char* path)
{
	std::vector<uint8_t> out;
	AssetAccessor& a = HALGetAssetAccessor();
	AssetHandle* h = a.OpenForRead(path);
	if (!h) return out;
	const int64_t size = a.Size(h);
	if (size > 0) {
		out.resize(static_cast<size_t>(size));
		if (a.Read(h, out.data(), size) != size)
			out.clear();
	}
	a.Close(h);
	return out;
}

void SfxLibrary::Load(int id, const char* path)
{
	auto bytes = loadAssetBytes(path);
	if (bytes.empty()) {
		fprintf(stderr, "audio: sfx[%d] not found: %s\n", id, path);
		return;
	}
	if (id >= static_cast<int>(sSfx.size())) {
		sSfx.resize(id + 1);
		sSfxData.resize(id + 1);
	}
	sSfxData[id] = std::move(bytes);
	sSfx[id] = std::make_unique<SoundBuffer>(sSfxData[id].data(),
	                                          static_cast<unsigned>(sSfxData[id].size()));
	fprintf(stderr, "audio: sfx[%d] loaded (%s, %zu B)\n", id, path, sSfxData[id].size());
}

void SfxLibrary::Play(int id)
{
	if (id < 0 || id >= static_cast<int>(sSfx.size()) || !sSfx[id]) return;
	sSfx[id]->play();
	fprintf(stderr, "audio: sfx[%d] play\n", id);
}

void SfxLibrary::Clear()
{
	sSfx.clear();
	sSfxData.clear();
}
