//=============================================================================
// audio/android/audio_stub.cc: silent audio backend for Android
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 3 step 1 stub. Android audio (Phase 6 of the audio plan) is deferred
// — miniaudio has AAudio / OpenSL ES backends, but we're not wiring them
// until the rest of the port works. SoundDevice / MusicPlayer methods are
// no-ops; isReady() returns false so SoundBuffer::play() early-returns in
// the callers that check it.
//=============================================================================

#include <audio/device.hp>
#include <audio/music.hp>
#include <audio/buffer.hp>

SoundDevice* gSoundDevice = nullptr;
MusicPlayer* gMusicPlayer = nullptr;

//-----------------------------------------------------------------------------
// SoundDevice

SoundDevice::SoundDevice() : _ready(false), _impl(nullptr) {}
SoundDevice::~SoundDevice() {}

void SoundDevice::setMasterVolume(float /*v*/) {}
void SoundDevice::setSfxVolume(float /*v*/) {}

void SoundDevice::tick(float /*px*/, float /*py*/, float /*pz*/,
                       float /*fx*/, float /*fy*/, float /*fz*/,
                       float /*ux*/, float /*uy*/, float /*uz*/) {}

//-----------------------------------------------------------------------------
// MusicPlayer

MusicPlayer::MusicPlayer() : _playing(false), _impl(nullptr) {}
MusicPlayer::~MusicPlayer() {}

bool MusicPlayer::play(const char* /*midiPath*/) { return false; }
void MusicPlayer::stop() {}
void MusicPlayer::setVolume(float /*v*/) {}

//-----------------------------------------------------------------------------
// SoundBuffer

SoundBuffer::SoundBuffer(const void* /*data*/, unsigned /*len*/)
    : _loaded(false), _impl(nullptr) {}
SoundBuffer::~SoundBuffer() {}

void SoundBuffer::play() const {}
void SoundBuffer::play(float /*x*/, float /*y*/, float /*z*/) const {}

//-----------------------------------------------------------------------------
// HAL audio init/term — called from HALStart/HALStop on the game thread.

void _InitAudio(void)
{
    gSoundDevice = new SoundDevice;
    gMusicPlayer = new MusicPlayer;
}

void _TermAudio(void)
{
    delete gMusicPlayer; gMusicPlayer = nullptr;
    delete gSoundDevice; gSoundDevice = nullptr;
}
