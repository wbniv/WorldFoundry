//=============================================================================
// hal/android/input.cc: Android input stub
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 3 step 1 stub. NativeActivity wrapper (Phase 3 step 2/4) feeds touch
// + gamepad events into _HALSetJoystickButtons from the UI thread; the game
// thread reads them via _JoystickButtonsF.
//=============================================================================

#include <hal/hal.h>

static joystickButtonsF _buttons = 0;

extern "C" void
_HALSetJoystickButtons(joystickButtonsF joystickButtons)
{
    _buttons = joystickButtons;
}

void _InitJoystickInterface(void) {}
void _TermJoystickInterface(void) {}

int _JoystickUserAbort(void)
{
    return (_buttons & 0x8000000) ? 1 : 0;
}

joystickButtonsF
_JoystickButtonsF(IJoystick joystick)
{
    SJoystick* self = ITEMRETRIEVE(joystick, SJoystick);
    if (self->_stickNum == EJW_JOYSTICK1)
        return _buttons;
    return 0;
}
