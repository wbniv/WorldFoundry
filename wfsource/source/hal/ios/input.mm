//=============================================================================
// hal/ios/input.mm: iOS input stub
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 1 stub — matches hal/android/input.cc. Phase 3 wires UITouch +
// GCController (MFi gamepad) events into _HALSetJoystickButtons from the
// UI thread; the game thread reads them via _JoystickButtonsF.
//=============================================================================

#include <hal/hal.h>

#include <atomic>
#include <cstdio>

// UI thread writes via _HALSetJoystickButtons; engine thread reads via
// _JoystickButtonsF every frame. std::atomic is correct (relaxed is fine
// for a bitmask that doesn't need to pair with other loads/stores).
static std::atomic<joystickButtonsF> _buttons{0};

extern "C" void
_HALSetJoystickButtons(joystickButtonsF joystickButtons)
{
    _buttons.store(joystickButtons, std::memory_order_relaxed);
}

void _InitJoystickInterface(void)
{
    std::fprintf(stderr, "wf_game: _InitJoystickInterface (stub)\n");
}
void _TermJoystickInterface(void) {}

int _JoystickUserAbort(void)
{
    return (_buttons.load(std::memory_order_relaxed) & 0x8000000) ? 1 : 0;
}

joystickButtonsF
_JoystickButtonsF(IJoystick joystick)
{
    SJoystick* self = ITEMRETRIEVE(joystick, SJoystick);
    if (self->_stickNum == EJW_JOYSTICK1)
        return _buttons.load(std::memory_order_relaxed);
    return 0;
}
