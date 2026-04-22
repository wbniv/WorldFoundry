// iOS audio init/term — identical shape to hal/android/audio.cc.
// miniaudio auto-detects CoreAudio / AVAudioEngine on Apple platforms.

#include <audio/device.hp>
#include <audio/music.hp>

#include <cstdio>

void _InitAudio()
{
    std::fprintf(stderr, "wf_game: → _InitAudio\n");
    gSoundDevice = new SoundDevice();
    std::fprintf(stderr, "wf_game: ·  SoundDevice ctor done\n");
    gMusicPlayer = new MusicPlayer();
    std::fprintf(stderr, "wf_game: ← _InitAudio\n");
}

void _TermAudio()
{
    delete gMusicPlayer;
    gMusicPlayer = nullptr;
    delete gSoundDevice;
    gSoundDevice = nullptr;
}
