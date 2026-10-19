//==============================================================================
// iOS audio init/term — identical shape to hal/android/audio.cc.
// miniaudio auto-detects CoreAudio / AVAudioEngine on Apple platforms.
//
// Simulator: audio is SKIPPED by default. On a headless Codemagic Mac the
// simulator's AURemoteIO::Initialize RPC to the host audio server never
// answers, and AudioToolbox aborts the process after 10 s ("Initialize: RPC
// timeout. Apparently deadlocked. Aborting now.", build 6abd3f6b, stack
// ma_engine_init -> ma_device_init__coreaudio -> AudioUnitInitialize). The
// abort happens inside AudioToolbox, so it cannot be time-bounded from here —
// only avoided. Every consumer already null-checks gSoundDevice/gMusicPlayer
// (game.cc, level.cc, audio_internal.hp), so the game runs silent.
// Set WF_IOS_SIM_AUDIO=1 to opt back in on a simulator with working audio.
// Real devices are unchanged.

#include <audio/device.hp>
#include <audio/music.hp>

#import <Foundation/Foundation.h>
#include <TargetConditionals.h>
#include <cstdlib>
#include <cstring>

void _InitAudio()
{
#if TARGET_OS_SIMULATOR
    const char* optIn = std::getenv("WF_IOS_SIM_AUDIO");
    if (!optIn || std::strcmp(optIn, "1") != 0) {
        NSLog(@"wf_game: audio: simulator, skipping CoreAudio init "
              @"(set WF_IOS_SIM_AUDIO=1 to enable); running silent");
        gSoundDevice = nullptr;
        gMusicPlayer = nullptr;
        return;
    }
#endif
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
