#include <audio/linux/audio_internal.hp>
#include <cstdio>

SoundDevice* gSoundDevice = nullptr;

SoundDevice::SoundDevice() : _ready(false), _impl(nullptr)
{
	_impl = new Impl();

	ma_engine_config cfg = ma_engine_config_init();
	ma_result r = ma_engine_init(&cfg, &_impl->engine);
	if (r != MA_SUCCESS) {
		fprintf(stderr, "audio: ma_engine_init failed (%d) — running silent\n", r);
		delete _impl;
		_impl = nullptr;
		return;
	}

	ma_sound_group_init(&_impl->engine, 0, nullptr, &_impl->sfxGroup);
	_ready = true;
	fprintf(stderr, "audio: miniaudio v%s ready\n", ma_version_string());
}

SoundDevice::~SoundDevice()
{
	if (!_impl) return;
	if (_ready) {
		ma_sound_group_uninit(&_impl->sfxGroup);
		ma_engine_uninit(&_impl->engine);
	}
	delete _impl;
}

void SoundDevice::setMasterVolume(float v)
{
	if (_ready) ma_engine_set_volume(&_impl->engine, v);
}

void SoundDevice::setSfxVolume(float v)
{
	if (_ready) ma_sound_group_set_volume(&_impl->sfxGroup, v);
}

void SoundDevice::tick(float x, float y, float z)
{
	if (_ready)
		ma_engine_listener_set_position(&_impl->engine, 0, x, y, z);
}
