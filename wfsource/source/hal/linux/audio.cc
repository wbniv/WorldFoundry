#include <hal/linux/audio.h>
#include <audio/device.hp>

void _InitAudio()
{
	gSoundDevice = new SoundDevice();
}

void _TermAudio()
{
	delete gSoundDevice;
	gSoundDevice = nullptr;
}
