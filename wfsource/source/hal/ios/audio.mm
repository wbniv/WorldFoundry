// iOS audio init/term — identical shape to hal/android/audio.cc.
// miniaudio auto-detects CoreAudio / AVAudioEngine on Apple platforms.

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
