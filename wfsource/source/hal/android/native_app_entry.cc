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

#include <android/log.h>
#include <android_native_app_glue.h>

#include <cstdio>
#include <cstring>

#include <hal/hal.h>
#include <hal/lifecycle.h>

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

int32_t HandleInputEvent(struct android_app* /*app*/, AInputEvent* /*event*/)
{
    // Phase 3 step 4 wires touch + gamepad → _HALSetJoystickButtons.
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
