#include <audio/buffer.hp>
#include <audio/linux/audio_internal.hp>
#include <cstdio>
#include <cstddef>
#include <atomic>

struct SoundBuffer::Impl {
	const void* data;
	unsigned    len;
};

// Heap-allocated per-play instance.
// ma_sound_uninit must NOT be called from the end callback (audio thread) —
// miniaudio forbids destroying sounds from within callbacks. Instead the end
// callback pushes the instance onto a lock-free stack; SoundDevice::tick()
// drains and frees it on the main thread each frame.
struct PlayInstance {
	ma_decoder    dec;
	ma_sound      snd;
	PlayInstance* next = nullptr;  // intrusive free-list link
};

static std::atomic<PlayInstance*> sDoneHead{nullptr};

static void on_sound_end(void* /*userData*/, ma_sound* pSound)
{
	PlayInstance* inst = (PlayInstance*)((char*)pSound - offsetof(PlayInstance, snd));
	// Push onto done-list lock-free; main thread will uninit + delete.
	PlayInstance* old = sDoneHead.load(std::memory_order_relaxed);
	do { inst->next = old; }
	while (!sDoneHead.compare_exchange_weak(old, inst,
	        std::memory_order_release, std::memory_order_relaxed));
}

// Called from SoundDevice::tick() on the main thread.
void DrainDoneSounds()
{
	PlayInstance* list = sDoneHead.exchange(nullptr, std::memory_order_acquire);
	while (list) {
		PlayInstance* next = list->next;
		ma_sound_uninit(&list->snd);
		ma_decoder_uninit(&list->dec);
		delete list;
		list = next;
	}
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

	// Positional: omit NO_SPATIALIZATION; skip ASYNC (async init races with spatialization setup).
	ma_uint32 flags = MA_SOUND_FLAG_NO_PITCH;
	ma_result r = ma_sound_init_from_data_source(eng, &inst->dec, flags,
	                  ma_sfx_group_get(), &inst->snd);
	if (r != MA_SUCCESS) {
		ma_decoder_uninit(&inst->dec);
		delete inst;
		return;
	}

	ma_sound_set_position(&inst->snd, x, y, z);
	// Widen min_distance so sounds stay at full gain within a typical game-scale radius.
	// Default min=1 attenuates too aggressively for worlds measured in meters.
	ma_sound_set_min_distance(&inst->snd, 5.f);
	ma_sound_set_end_callback(&inst->snd, on_sound_end, nullptr);
	ma_sound_start(&inst->snd);
}
