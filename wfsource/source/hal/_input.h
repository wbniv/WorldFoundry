//=============================================================================
// int9.h: Replacement keyboard handler for PC
//=============================================================================
// use only once insurance

#ifndef __INPUT_H
#define __INPUT_H

//=============================================================================
// Documentation:
//=============================================================================

//	Abstract:

//	History:
//			Created Joseph Boyle @ Cave Logic Studios  Jan 11 1995
//			Updated 03-24-95 06:35pm Kevin T. Seghetti, renamed to _input.h from int9.h, added pc joystick interface
//	Class Hierarchy:
//			none

//	Dependancies:

//	Restrictions:

//	Example:
//=============================================================================

#include <hal/sjoystic.h>

void _InitJoystickInterface(void);
void _TermJoystickInterface(void);
joystickButtonsF _JoystickButtonsF(IJoystick joystick);
int  _JoystickUserAbort(void);

// HALInjectJoystickButtons: public boundary for hosts (editor, replay driver,
// test harness, ...) to feed joystick-button state into the engine without
// going through the engine's own X11/Android/iOS event loop. The engine reads
// the most recently injected button mask via the existing input pipeline; the
// host calls this each frame (or whenever the state changes) with the OR'd
// bitmask of buttons currently held.
//
// Added 2026-05-18 (Phase 0b sub-task #3, embed-readiness). See
// docs/investigations/2026-05-18-collaborative-level-editor-design.md
// § Engine linkability.
//
// Thin wrapper around the platform-internal _HALSetJoystickButtons so the
// existing platform event loops (mesa.cc XEventLoop, android native_app_entry,
// ios MFi gamepad) keep working unchanged when no host is driving input.
void HALInjectJoystickButtons( joystickButtonsF buttons );

#ifdef TEST_JOYSTICK
void _TestJoystickInterface(void);
#endif

//=============================================================================
#endif
//=============================================================================
