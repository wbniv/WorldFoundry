#include <audio/buffer.hp>
#include <audio/linux/audio_internal.hp>
#include <cstdio>
#include <cstddef>

struct SoundBuffer::Impl {
	const void* data;
	unsigned    len;
};

// Heap-allocated per-play instance; freed by the end callback.
struct PlayInstance {
	ma_decoder dec;
	ma_sound   snd;
};

static void on_sound_end(void* /*userData*/, ma_sound* pSound)
{
	PlayInstance* inst = (PlayInstance*)((char*)pSound - offsetof(PlayInstance, snd));
	ma_sound_uninit(&inst->snd);
	ma_decoder_uninit(&inst->dec);
	delete inst;
}

SoundBuffer::SoundBuffer(const void* data, unsigned len)
	: _loaded(false), _impl(nullptr)
{
	_impl       = new Impl();
	_impl->data = data;
	_impl->len  = len;
	_loaded     = (data != nullptr && len > 0);
}

SoundBuffer::~SoundBuffer()
{
	delete _impl;
}

void SoundBuffer::play() const
{
	if (!_loaded || !_impl) return;
	ma_engine* eng = ma_engine_get();
	if (!eng) return;

	PlayInstance* inst = new PlayInstance();

	ma_decoder_config dcfg = ma_decoder_config_init_default();
	if (ma_decoder_init_memory(_impl->data, _impl->len, &dcfg, &inst->dec) != MA_SUCCESS) {
		fprintf(stderr, "audio: SoundBuffer::play() — decoder init failed\n");
		delete inst;
		return;
	}

	ma_uint32 flags = MA_SOUND_FLAG_ASYNC
	                | MA_SOUND_FLAG_NO_PITCH
	                | MA_SOUND_FLAG_NO_SPATIALIZATION;
	ma_result r = ma_sound_init_from_data_source(eng, &inst->dec, flags,
	                  ma_sfx_group_get(), &inst->snd);
	if (r != MA_SUCCESS) {
		ma_decoder_uninit(&inst->dec);
		delete inst;
		return;
	}

	ma_sound_set_end_callback(&inst->snd, on_sound_end, nullptr);
	ma_sound_start(&inst->snd);
}

void SoundBuffer::play(float x, float y, float z) const
{
	if (!_loaded || !_impl) return;
	ma_engine* eng = ma_engine_get();
	if (!eng) return;

	PlayInstance* inst = new PlayInstance();

	ma_decoder_config dcfg = ma_decoder_config_init_default();
	if (ma_decoder_init_memory(_impl->data, _impl->len, &dcfg, &inst->dec) != MA_SUCCESS) {
		delete inst;
		return;
	}

	// Positional: no NO_SPATIALIZATION flag — miniaudio applies distance attenuation.
	ma_uint32 flags = MA_SOUND_FLAG_ASYNC | MA_SOUND_FLAG_NO_PITCH;
	ma_result r = ma_sound_init_from_data_source(eng, &inst->dec, flags,
	                  ma_sfx_group_get(), &inst->snd);
	if (r != MA_SUCCESS) {
		ma_decoder_uninit(&inst->dec);
		delete inst;
		return;
	}

	ma_sound_set_position(&inst->snd, x, y, z);
	ma_sound_set_end_callback(&inst->snd, on_sound_end, nullptr);
	ma_sound_start(&inst->snd);
}
