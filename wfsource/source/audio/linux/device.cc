#include <audio/linux/audio_internal.hp>
#include <cstdio>
#include <cmath>

#if defined(WF_TARGET_IOS)
#  include <TargetConditionals.h>
#endif

SoundDevice* gSoundDevice = nullptr;

SoundDevice::SoundDevice() : _ready(false), _impl(nullptr)
{
	_impl = new Impl();

	ma_engine_config cfg = ma_engine_config_init();
#if defined(WF_TARGET_IOS) && TARGET_OS_SIMULATOR
	// iOS Simulator's CoreAudio Initialize RPC deadlocks (~9s timeout) on
	// Codemagic's headless Mac mini — no audio hardware session, so
	// ma_engine_init never returns and HALStart stalls inside _InitAudio.
	// noDevice=MA_TRUE keeps the engine's mixing graph alive without opening
	// a playback device; nothing is rendered. On real-device iOS builds
	// (TARGET_OS_SIMULATOR==0) we init normally — CoreAudio resolves fine
	// with an actual audio session, so snowgoons' MIDI music plays through
	// speakers like on Linux / Android.
	cfg.noDevice = MA_TRUE;
#endif
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

void SoundDevice::tick(float px, float py, float pz,
                       float fx, float fy, float fz,
                       float ux, float uy, float uz)
{
	if (!_ready) return;
	DrainDoneSounds();
	ma_engine_listener_set_position(&_impl->engine, 0, px, py, pz);
	float fLen2 = fx*fx + fy*fy + fz*fz;
	float uLen2 = ux*ux + uy*uy + uz*uz;
	if (fLen2 > 1e-6f && uLen2 > 1e-6f) {
		ma_engine_listener_set_direction(&_impl->engine, 0, fx, fy, fz);
		ma_engine_listener_set_world_up(&_impl->engine, 0, ux, uy, uz);
	}
}
