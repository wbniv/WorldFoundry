//=============================================================================
// hal/android/key_map.h: Android key code -> engine button bit
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// One mapping for every Android host: the NativeActivity game app
// (hal/android/native_app_entry.cc) and the screensaver's launcher menu
// (android/screensaver/src/main/cpp/dream_host.cc), so a remote key means the
// same button in the playable menu whichever package draws it.
// docs/plans/2026-11-21-one-aquarium-app.md.
//=============================================================================

#ifndef WF_HAL_ANDROID_KEY_MAP_H
#define WF_HAL_ANDROID_KEY_MAP_H

#include <android/keycodes.h>
#include <cstdint>

#include <hal/sjoystic.h>

// The engine button bit for an Android key code, or 0 for a key the engine does not use
// (Back is handled by each host: it navigates the menu rather than pressing a button).
inline uint32_t WFAndroidMapKeyCode(int32_t code)
{
    switch (code)
    {
        case AKEYCODE_DPAD_LEFT:       return EJ_BUTTONF_LEFT;
        case AKEYCODE_DPAD_RIGHT:      return EJ_BUTTONF_RIGHT;
        case AKEYCODE_DPAD_UP:         return EJ_BUTTONF_UP;
        case AKEYCODE_DPAD_DOWN:       return EJ_BUTTONF_DOWN;
        case AKEYCODE_BUTTON_A:        return EJ_BUTTONF_A;
        case AKEYCODE_DPAD_CENTER:     return EJ_BUTTONF_A;   // Chromecast / Google TV remote's OK
        case AKEYCODE_BUTTON_B:        return EJ_BUTTONF_B;
        case AKEYCODE_BUTTON_X:        return EJ_BUTTONF_C;
        case AKEYCODE_BUTTON_Y:        return EJ_BUTTONF_D;
        case AKEYCODE_BUTTON_L1:       return EJ_BUTTONF_E;
        case AKEYCODE_BUTTON_R1:       return EJ_BUTTONF_F;
        case AKEYCODE_BUTTON_START:    return EJ_BUTTONF_G;
        case AKEYCODE_BUTTON_SELECT:   return EJ_BUTTONF_H;
        default:                       return 0;
    }
}

#endif // WF_HAL_ANDROID_KEY_MAP_H
