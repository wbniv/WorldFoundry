#pragma once
#ifdef WF_ENABLE_STEAM

#include <hal/sjoystic.h>

void              _InitSteam();
void              _TermSteam();
void              _SteamRunCallbacks();
joystickButtonsF  _GetSteamJoystickButtons();

#endif // WF_ENABLE_STEAM
