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

#include <android/configuration.h>
#include <android/input.h>
#include <android/keycodes.h>
#include <android/log.h>
#include <android_native_app_glue.h>

#include <cstdio>
#include <cstring>

#include <hal/hal.h>
#include <hal/lifecycle.h>

extern "C" void _HALSetJoystickButtons(joystickButtonsF joystickButtons);

extern int _halWindowWidth;
extern int _halWindowHeight;

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

// Bitmask of WF buttons currently held — combined gamepad + touch states are
// merged here and flushed to _HALSetJoystickButtons.
joystickButtonsF    gGamepadButtons = 0;
joystickButtonsF    gTouchButtons   = 0;

// True when running on Google TV / Android TV (leanback). On TV there's no
// touchscreen worth hit-testing and the on-screen d-pad is suppressed.
bool                gIsTvMode       = false;

constexpr uint32_t kDPadBits   = EJ_BUTTONF_LEFT | EJ_BUTTONF_RIGHT
                               | EJ_BUTTONF_UP   | EJ_BUTTONF_DOWN;
constexpr uint32_t kActionBits = EJ_BUTTONF_A | EJ_BUTTONF_B;

void Emit()
{
    _HALSetJoystickButtons(gGamepadButtons | gTouchButtons);
}

// Joystick axes trigger LEFT/RIGHT/UP/DOWN when past this threshold — matches
// Android's AGAMEPAD guideline. Separate from D-pad key events which fire as
// discrete AKEYCODE_DPAD_* presses.
constexpr float kJoystickThreshold = 0.5f;

// ---- Touch hit-test ---------------------------------------------------------
// Simple fixed-pixel layout (no rendering yet — the modern backend picks up
// overlay drawing in a follow-up). Coords are raw surface pixels, origin
// top-left, +Y down.
//
// Bottom-left quadrant: d-pad cross, 200 px × 200 px.
//   LEFT  (0..66, h-133..h-66)
//   RIGHT (133..200, h-133..h-66)
//   UP    (66..133, h-200..h-133)
//   DOWN  (66..133, h-66..h)
//
// Bottom-right corner: action buttons.
//   A     (w-120..w-0,   h-120..h-0)
//   B     (w-240..w-120, h-120..h-0)

uint32_t HitTestTouch(float x, float y)
{
    const int w = _halWindowWidth;
    const int h = _halWindowHeight;
    if (w <= 0 || h <= 0) return 0;

    // D-pad (bottom-left).
    if (x >= 0.0f   && x < 200.0f &&
        y >= h-200  && y < h)
    {
        if (x < 66.0f   && y >= h-133 && y <  h-66)   return EJ_BUTTONF_LEFT;
        if (x >= 133.0f && y >= h-133 && y <  h-66)   return EJ_BUTTONF_RIGHT;
        if (x >= 66.0f  && x < 133.0f && y <  h-133)  return EJ_BUTTONF_UP;
        if (x >= 66.0f  && x < 133.0f && y >= h-66)   return EJ_BUTTONF_DOWN;
    }

    // A button (far bottom-right).
    if (x >= w-120 && x <  w   && y >= h-120 && y < h)
        return EJ_BUTTONF_A;

    // B button (inside of A).
    if (x >= w-240 && x <  w-120 && y >= h-120 && y < h)
        return EJ_BUTTONF_B;

    return 0;
}

void RecomputeTouchState(AInputEvent* event, bool clearOnUp)
{
    if (clearOnUp)
    {
        gTouchButtons = 0;
        return;
    }
    joystickButtonsF active = 0;
    const size_t n = AMotionEvent_getPointerCount(event);
    for (size_t i = 0; i < n; ++i)
    {
        const float x = AMotionEvent_getX(event, i);
        const float y = AMotionEvent_getY(event, i);
        active |= HitTestTouch(x, y);
    }
    gTouchButtons = active;
}

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

        case APP_CMD_CONFIG_CHANGED:
            if (app->config)
            {
                const int32_t uiMode = AConfiguration_getUiModeType(app->config);
                gIsTvMode = (uiMode == ACONFIGURATION_UI_MODE_TYPE_TELEVISION);
                WFLOG("APP_CMD_CONFIG_CHANGED: uiMode=%d (tv=%d)",
                      uiMode, gIsTvMode ? 1 : 0);
            }
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

        if (action == AKEY_EVENT_ACTION_DOWN)      gGamepadButtons |=  mask;
        else if (action == AKEY_EVENT_ACTION_UP)   gGamepadButtons &= ~mask;
        Emit();
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

            gGamepadButtons = (gGamepadButtons & ~kDPadBits) | axes;
            Emit();
            return 1;
        }

        // Touch — suppressed on TV.
        if ((source & AINPUT_SOURCE_TOUCHSCREEN) && !gIsTvMode)
        {
            const int32_t raw    = AMotionEvent_getAction(event);
            const int32_t action = raw & AMOTION_EVENT_ACTION_MASK;
            const bool    clear  = (action == AMOTION_EVENT_ACTION_UP
                                 || action == AMOTION_EVENT_ACTION_CANCEL);
            RecomputeTouchState(event, clear);
            Emit();
            return 1;
        }
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

    if (app->config)
    {
        const int32_t uiMode = AConfiguration_getUiModeType(app->config);
        gIsTvMode = (uiMode == ACONFIGURATION_UI_MODE_TYPE_TELEVISION);
        WFLOG("uiMode=%d (tv=%d)", uiMode, gIsTvMode ? 1 : 0);
    }

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
