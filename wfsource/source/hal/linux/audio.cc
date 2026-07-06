#include <hal/linux/audio.h>
#include <audio/device.hp>
#include <audio/music.hp>

void _InitAudio()
{
	gSoundDevice  = new SoundDevice();
	gMusicPlayer  = new MusicPlayer();
}

void _TermAudio()
{
	delete gMusicPlayer;
	gMusicPlayer = nullptr;
	delete gSoundDevice;
	gSoundDevice = nullptr;
}
