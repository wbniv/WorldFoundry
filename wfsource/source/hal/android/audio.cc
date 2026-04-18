// Android audio init/term — identical shape to hal/linux/audio.cc.
// The underlying miniaudio-based SoundDevice / MusicPlayer implementation
// (audio/linux/*.cc) is portable: miniaudio auto-detects AAudio / OpenSL
// ES on Android. Kept in a platform directory for symmetry with Linux +
// future console targets.

#include <audio/device.hp>
#include <audio/music.hp>

void _InitAudio()
{
    gSoundDevice = new SoundDevice();
    gMusicPlayer = new MusicPlayer();
}

void _TermAudio()
{
    delete gMusicPlayer;
    gMusicPlayer = nullptr;
    delete gSoundDevice;
    gSoundDevice = nullptr;
}
