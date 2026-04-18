//=============================================================================
// hal/android/native_app_entry.cc: android_main + NativeActivity glue
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// Phase 3 step 2. android_main() is the entry point called by
// android_native_app_glue on the game thread. It:
//
//   1. Registers command / input handlers.
//   2. Blocks until APP_CMD_INIT_WINDOW delivers an ANativeWindow,
//      then creates the EGL context (gfx/gl/android_window.cc).
//   3. Calls HALStart → PIGSMain, which runs the game loop.
//   4. On every frame, Display::PageFlip → XEventLoop →
//      WFAndroidPumpEvents (below) drains pending commands + input
//      events with a zero-timeout ALooper_pollOnce so the game loop
//      stays responsive without blocking.
//
// Lifecycle: APP_CMD_PAUSE / RESUME → HALNotifySuspend / Resume; the main
// loop in game.cc already checks HALIsSuspended and skips render + PageFlip.
// Input wiring beyond the stub (touch / gamepad → EJ_BUTTONF_*) lands in
// Phase 3 step 4.
//=============================================================================

#include <android/input.h>
#include <android/keycodes.h>
#include <android/log.h>
#include <android_native_app_glue.h>

#include <cstdio>
#include <cstring>

#include <hal/hal.h>
#include <hal/lifecycle.h>

extern "C" void _HALSetJoystickButtons(joystickButtonsF joystickButtons);

extern "C" bool WFAndroidEglInit(struct ANativeWindow* window);
extern "C" void WFAndroidEglTerm();

#define WF_LOG_TAG "wf_game"
#define WFLOG(fmt, ...) __android_log_print(ANDROID_LOG_INFO,  WF_LOG_TAG, fmt, ##__VA_ARGS__)
#define WFLOGE(fmt, ...) __android_log_print(ANDROID_LOG_ERROR, WF_LOG_TAG, fmt, ##__VA_ARGS__)

namespace
{

struct android_app* gApp        = nullptr;
bool                gEglReady   = false;
bool                gExitLoop   = false;

// Bitmask of WF buttons currently held (updated by HandleInputEvent, read by
// hal/android/input.cc's _JoystickButtonsF via _HALSetJoystickButtons).
joystickButtonsF    gButtons    = 0;

// Joystick axes trigger LEFT/RIGHT/UP/DOWN when past this threshold — matches
// Android's AGAMEPAD guideline. Separate from D-pad key events which fire as
// discrete AKEYCODE_DPAD_* presses.
constexpr float kJoystickThreshold = 0.5f;

uint32_t MapKeyCode(int32_t code)
{
    switch (code)
    {
        case AKEYCODE_DPAD_LEFT:       return EJ_BUTTONF_LEFT;
        case AKEYCODE_DPAD_RIGHT:      return EJ_BUTTONF_RIGHT;
        case AKEYCODE_DPAD_UP:         return EJ_BUTTONF_UP;
        case AKEYCODE_DPAD_DOWN:       return EJ_BUTTONF_DOWN;
        case AKEYCODE_BUTTON_A:        return EJ_BUTTONF_A;
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

void HandleAppCmd(struct android_app* app, int32_t cmd)
{
    switch (cmd)
    {
        case APP_CMD_INIT_WINDOW:
            WFLOG("APP_CMD_INIT_WINDOW");
            if (app->window)
                gEglReady = WFAndroidEglInit(app->window);
            break;

        case APP_CMD_TERM_WINDOW:
            WFLOG("APP_CMD_TERM_WINDOW");
            WFAndroidEglTerm();
            gEglReady = false;
            break;

        case APP_CMD_PAUSE:
            WFLOG("APP_CMD_PAUSE");
            HALNotifySuspend();
            break;

        case APP_CMD_RESUME:
            WFLOG("APP_CMD_RESUME");
            HALNotifyResume();
            break;

        case APP_CMD_DESTROY:
            WFLOG("APP_CMD_DESTROY");
            gExitLoop = true;
            break;

        default:
            break;
    }
}

int32_t HandleInputEvent(struct android_app* /*app*/, AInputEvent* event)
{
    const int32_t type = AInputEvent_getType(event);

    if (type == AINPUT_EVENT_TYPE_KEY)
    {
        const int32_t keyCode = AKeyEvent_getKeyCode(event);
        const int32_t action  = AKeyEvent_getAction(event);
        const uint32_t mask   = MapKeyCode(keyCode);
        if (mask == 0) return 0;

        if (action == AKEY_EVENT_ACTION_DOWN)      gButtons |=  mask;
        else if (action == AKEY_EVENT_ACTION_UP)   gButtons &= ~mask;
        _HALSetJoystickButtons(gButtons);
        return 1;
    }

    if (type == AINPUT_EVENT_TYPE_MOTION)
    {
        const int32_t source = AInputEvent_getSource(event);

        // Gamepad analog sticks. Android reports the left stick on AXIS_X /
        // AXIS_Y and the D-pad hat on AXIS_HAT_X / AXIS_HAT_Y.
        if (source & AINPUT_SOURCE_JOYSTICK)
        {
            float x = AMotionEvent_getAxisValue(event, AMOTION_EVENT_AXIS_X,     0);
            float y = AMotionEvent_getAxisValue(event, AMOTION_EVENT_AXIS_Y,     0);
            float hx = AMotionEvent_getAxisValue(event, AMOTION_EVENT_AXIS_HAT_X, 0);
            float hy = AMotionEvent_getAxisValue(event, AMOTION_EVENT_AXIS_HAT_Y, 0);

            if (hx != 0.0f) x = hx;
            if (hy != 0.0f) y = hy;

            joystickButtonsF axes = 0;
            if (x < -kJoystickThreshold)  axes |= EJ_BUTTONF_LEFT;
            if (x >  kJoystickThreshold)  axes |= EJ_BUTTONF_RIGHT;
            if (y < -kJoystickThreshold)  axes |= EJ_BUTTONF_UP;
            if (y >  kJoystickThreshold)  axes |= EJ_BUTTONF_DOWN;

            constexpr uint32_t kAxisBits = EJ_BUTTONF_LEFT | EJ_BUTTONF_RIGHT
                                          | EJ_BUTTONF_UP  | EJ_BUTTONF_DOWN;
            gButtons = (gButtons & ~kAxisBits) | axes;
            _HALSetJoystickButtons(gButtons);
            return 1;
        }

        // Touch (AINPUT_SOURCE_TOUCHSCREEN) is deferred to a follow-up — the
        // on-screen d-pad hit-test lands alongside the UI-mode detection.
    }

    return 0;
}

}  // namespace

// Called from XEventLoop (display.cc PageFlip) once per frame. Non-blocking
// drain of any queued commands + input events.
extern "C" void
WFAndroidPumpEvents()
{
    if (!gApp) return;
    for (;;)
    {
        int events = 0;
        struct android_poll_source* source = nullptr;
        int ident = ALooper_pollOnce(0, nullptr, &events, (void**)&source);
        if (ident < 0) break;
        if (source) source->process(gApp, source);
        if (gApp->destroyRequested) { gExitLoop = true; break; }
    }
}

// Entry point — android_native_app_glue calls this on a dedicated thread
// after ANativeActivity_onCreate returns to the UI thread.
extern "C" void
android_main(struct android_app* app)
{
    gApp = app;
    app->onAppCmd     = HandleAppCmd;
    app->onInputEvent = HandleInputEvent;

    // Block until the first surface arrives so EGL is live before the
    // engine tries to draw.
    while (!gEglReady && !app->destroyRequested)
    {
        int events = 0;
        struct android_poll_source* source = nullptr;
        if (ALooper_pollOnce(-1, nullptr, &events, (void**)&source) >= 0)
        {
            if (source) source->process(app, source);
        }
    }
    if (app->destroyRequested)
    {
        WFAndroidEglTerm();
        return;
    }

    char arg0[] = "wf_game";
    char* argv[1] = { arg0 };
    HALStart(1, argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);

    // HALStart returns when the game exits (PIGSMain's loop terminates).
    WFAndroidEglTerm();
    WFLOG("android_main exiting");
}
