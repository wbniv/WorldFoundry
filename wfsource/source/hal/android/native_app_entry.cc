#include <game/plant_settings.h>
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

#include <dlfcn.h>
#include <ucontext.h>
#include <android/asset_manager.h>
#include <android/configuration.h>
#include <android/input.h>
#include <android/keycodes.h>
#include <android/log.h>
#include <android_native_app_glue.h>

#include <fcntl.h>
#include <signal.h>
#include <sys/stat.h>
#include <unistd.h>

#include <time.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include <hal/hal.h>
#include <hal/lifecycle.h>
#include <pigsys/pigsys.hp>
#include <hal/android/wf_android_export.hp>
#include <game/level_menu.h>   // Back: selected level -> selector -> exit
#include <hal/phonepad/phonepad.h>
#include <hal/phonepad/phonepad_overlay.h>

extern "C" void _HALSetJoystickButtons(joystickButtonsF joystickButtons);

extern int _halWindowWidth;
extern int _halWindowHeight;

extern "C" bool WFAndroidEglInit(struct ANativeWindow* window);
extern "C" void WFAndroidEglTerm();
extern "C" void WFAndroidSetHudEnabled(int enabled);

#define WF_LOG_TAG "wf_game"
#define WFLOG(fmt, ...) __android_log_print(ANDROID_LOG_INFO,  WF_LOG_TAG, fmt, ##__VA_ARGS__)
#define WFLOGE(fmt, ...) __android_log_print(ANDROID_LOG_ERROR, WF_LOG_TAG, fmt, ##__VA_ARGS__)

namespace
{

struct android_app* gApp         = nullptr;
AAssetManager*      gAssetMgr    = nullptr;
bool                gEglReady    = false;
bool                gExitLoop    = false;

// ---- diagnostic log -------------------------------------------------------
// Redirect stdout/stderr into a file in the app's external-files dir
// (/storage/emulated/0/Android/data/org.worldfoundry.wf_game/files/wf.log) so
// crashes on a sideloaded device leave a trail the user can open with any
// Files app. Also catches SIGSEGV / SIGABRT / SIGBUS to log where we died
// before the OS tombstones us.

static const char* kWfLogName = "wf.log";

// Print one code address as "module+offset", the form addr2line wants against
// the unstripped library (the APK's copy is stripped). Not async-signal-safe
// (dladdr, stdio); this runs once, on the way to a tombstone.
void PrintCodeAddress(const char* label, void* pc)
{
    Dl_info di;
    if (pc && dladdr(pc, &di) && di.dli_fname && di.dli_fbase)
        std::fprintf(stderr, "  %s %p %s+0x%lx\n", label, pc, di.dli_fname,
                     (unsigned long)((uintptr_t)pc - (uintptr_t)di.dli_fbase));
    else
        std::fprintf(stderr, "  %s %p\n", label, pc);
}

void CrashSigHandler(int sig, siginfo_t* info, void* ucontext)
{
    std::fprintf(stderr,
                 "\n!!! wf_game crashed: signal=%d si_code=%d si_addr=%p !!!\n",
                 sig, info ? info->si_code : 0, info ? info->si_addr : nullptr);
    if (ucontext)
    {
        const ucontext_t* uc = static_cast<const ucontext_t*>(ucontext);
#if defined(__arm__)
        PrintCodeAddress("fault pc", reinterpret_cast<void*>(uc->uc_mcontext.arm_pc));
        PrintCodeAddress("lr      ", reinterpret_cast<void*>(uc->uc_mcontext.arm_lr));
#elif defined(__aarch64__)
        PrintCodeAddress("fault pc", reinterpret_cast<void*>(uc->uc_mcontext.pc));
        PrintCodeAddress("lr      ", reinterpret_cast<void*>(uc->uc_mcontext.regs[30]));
#endif
    }
    std::fflush(stderr);
    // Let the OS finish the job with a tombstone.
    signal(sig, SIG_DFL);
    raise(sig);
}

void InstallCrashHandlers()
{
    struct sigaction sa;
    std::memset(&sa, 0, sizeof(sa));
    sa.sa_flags     = SA_SIGINFO;
    sa.sa_sigaction = CrashSigHandler;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGSEGV, &sa, nullptr);
    sigaction(SIGBUS,  &sa, nullptr);
    sigaction(SIGABRT, &sa, nullptr);
    sigaction(SIGILL,  &sa, nullptr);
    sigaction(SIGFPE,  &sa, nullptr);
}

void OpenDiagnosticLog(struct android_app* app)
{
    if (!app->activity || !app->activity->externalDataPath) return;
    mkdir(app->activity->externalDataPath, 0755);  // usually already exists
    char logpath[512];
    std::snprintf(logpath, sizeof(logpath), "%s/%s",
                  app->activity->externalDataPath, kWfLogName);
    int fd = open(logpath, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) return;
    dup2(fd, STDOUT_FILENO);
    dup2(fd, STDERR_FILENO);
    close(fd);
    std::setvbuf(stdout, nullptr, _IOLBF, 0);
    std::setvbuf(stderr, nullptr, _IOLBF, 0);
    std::fprintf(stderr, "\n=== wf_game android_main (log → %s) ===\n", logpath);
    __android_log_print(ANDROID_LOG_INFO, WF_LOG_TAG,
                        "diagnostic log: %s", logpath);
}

// Bitmask of WF buttons currently held — combined gamepad + touch + phone
// states are merged here and flushed to _HALSetJoystickButtons.
joystickButtonsF    gGamepadButtons = 0;
joystickButtonsF    gTouchButtons   = 0;
joystickButtonsF    gPhoneButtons   = 0;   // the phone controller (hal/phonepad), below

// True when running on Google TV / Android TV (leanback). On TV there's no
// touchscreen worth hit-testing and the on-screen d-pad is suppressed.
bool                gIsTvMode       = false;

constexpr uint32_t kDPadBits   = EJ_BUTTONF_LEFT | EJ_BUTTONF_RIGHT
                               | EJ_BUTTONF_UP   | EJ_BUTTONF_DOWN;
constexpr uint32_t kActionBits = EJ_BUTTONF_A | EJ_BUTTONF_B;

void Emit()
{
    _HALSetJoystickButtons(gGamepadButtons | gTouchButtons | gPhoneButtons);
}

// ---- The phone as a gamepad (docs/plans/2026-09-30-aquarium-chromecast.md, Phase E) ----
// An app that ships assets/layout.json (aquarium, condo; not snowgoons) serves
// assets/controller.html on its Wi-Fi address while resumed. The phone's mask is
// a third input source OR-ed in Emit(); the server releases it on every kind of
// disconnect. Polled once per frame from WFAndroidPumpEvents on this thread.

phonepad::Server    gPhone;
phonepad::Overlay   gPhoneOverlay;
bool                gPhoneEnabled   = false;   // assets/layout.json present
bool                gPhoneResumed   = false;   // between APP_CMD_RESUME and APP_CMD_PAUSE
std::string         gPhonePage, gPhoneLayout, gPhonePin;
int64_t             gPhoneRetryMs   = 0;       // next attempt to find a LAN address
std::vector<PhonepadRect> gPhoneRects;

int64_t NowMs()
{
    timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return int64_t(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
}

void PhoneLog(const char* line) { WFLOG("%s", line); }

bool ReadAsset(const char* name, std::string* out)
{
    if (!gAssetMgr) return false;
    AAsset* a = AAssetManager_open(gAssetMgr, name, AASSET_MODE_BUFFER);
    if (!a) return false;
    const off_t len = AAsset_getLength(a);
    const void* buf = AAsset_getBuffer(a);
    if (buf && len > 0) out->assign(static_cast<const char*>(buf), size_t(len));
    AAsset_close(a);
    return buf && len > 0;
}

void PhoneInit()
{
    gPhoneEnabled = ReadAsset("layout.json", &gPhoneLayout) && ReadAsset("controller.html", &gPhonePage);
    if (!gPhoneEnabled) { WFLOG("phone controller: off (no assets/layout.json)"); return; }
    gPhonePin = phonepad::MakePin();          // one PIN per launch, kept across pause/resume
    if (gPhonePin.empty()) { gPhoneEnabled = false; WFLOGE("phone controller: off (no random source)"); return; }
    gPhone.SetLog(PhoneLog);
    gPhone.SetCommandHandler(planted::command);
}

// Listen on the Wi-Fi address (never 0.0.0.0, never a public address).
void PhoneStart()
{
    if (!gPhoneEnabled || gPhone.Running()) return;
    gPhoneRetryMs = NowMs() + 3000;
    uint32_t addr = 0;
    if (!phonepad::DiscoverLanAddress(&addr))
    {
        WFLOG("phone controller: no network yet; retrying every 3 s");
        return;
    }
    if (!phonepad::IsPrivateIPv4(addr) || (addr >> 24) == 127)
    {
        WFLOG("phone controller: %s is not a private LAN address; not listening",
              phonepad::FormatIPv4(addr).c_str());
        return;
    }
    phonepad::Config cfg;
    cfg.bindAddr   = addr;
    cfg.port       = phonepad::kDefaultPort;
    cfg.pin        = gPhonePin;
    cfg.pageHtml   = gPhonePage;
    cfg.layoutJson = gPhoneLayout;
    if (!gPhone.Start(cfg)) return;
    const std::string url = phonepad::ControllerUrl(addr, gPhone.Port(), gPhonePin);
    char hostPort[32];
    std::snprintf(hostPort, sizeof(hostPort), "%s:%u", phonepad::FormatIPv4(addr).c_str(), unsigned(gPhone.Port()));
    gPhoneOverlay.SetEndpoint(url, hostPort, gPhonePin);
    WFLOG("phone controller: open %s (PIN %s)", url.c_str(), gPhonePin.c_str());
}

void PhoneStop()
{
    planted::state().phone=false;
    if (!gPhoneEnabled) return;
    gPhone.Stop();
    gPhone.TakeEvents();
    gPhoneOverlay.ClearEndpoint();
    if (gPhoneButtons)
    {
        WFLOG("phone mask=0x0 (paused: every phone button released)");
        gPhoneButtons = 0;
        Emit();
    }
}

void PhonePoll()
{
    if (!gPhoneEnabled) return;
    const int64_t now = NowMs();
    if (!gPhone.Running())
    {
        if (gPhoneResumed && now >= gPhoneRetryMs) PhoneStart();
        return;
    }
    const joystickButtonsF m = gPhone.Poll(now);
    planted::state().phone=gPhone.PhoneConnected();
    static int64_t plantSent=0;
    if(now-plantSent>=150){gPhone.SendText(planted::message());plantSent=now;}
    const uint32_t ev = gPhone.TakeEvents();
    if (ev) gPhoneOverlay.OnEvents(ev, now);
    if (m != gPhoneButtons)
    {
        // One line per change, like the key-edge line below, so logcat shows what the phone held.
        WFLOG("phone mask=0x%x", unsigned(m));
        gPhoneButtons = m;
        Emit();
    }
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
            gPhoneResumed = false;
            PhoneStop();            // listen only while resumed
            break;

        case APP_CMD_RESUME:
            WFLOG("APP_CMD_RESUME");
            HALNotifyResume();
            gPhoneResumed = true;
            PhoneStart();
            break;

        case APP_CMD_CONFIG_CHANGED:
            if (app->config)
            {
                const int32_t uiMode = AConfiguration_getUiModeType(app->config);
                gIsTvMode = (uiMode == ACONFIGURATION_UI_MODE_TYPE_TELEVISION);
                WFAndroidSetHudEnabled(gIsTvMode ? 0 : 1);
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
        // One line per key edge (not per auto-repeat), so logcat shows whether a remote key
        // arrived and what it mapped to: "key code=23 action=0 mask=0x...".
        // Back dismisses the visible phone panel before navigating the game.
        // Consume the entire press, including repeats, and hide once on release.
        if(keyCode==AKEYCODE_BACK&&planted::state().modal){if(action==AKEY_EVENT_ACTION_UP)planted::apply();return 1;}
        if (keyCode == AKEYCODE_BACK && gPhoneOverlay.PanelVisible(NowMs()))
        {
            if (action == AKEY_EVENT_ACTION_UP) gPhoneOverlay.OnBack(NowMs());
            if (AKeyEvent_getRepeatCount(event) == 0)
                WFLOG("key code=%d action=%d (Back: hides the phone panel)", keyCode, action);
            return 1;
        }
        // With no panel, Back returns from a level; on its selector Back exits.
        if (keyCode == AKEYCODE_BACK && levelmenu::MenuRunning())
        {
            if (action == AKEY_EVENT_ACTION_UP)
            {
                if (levelmenu::SelectorVisible())
                {
                    WFLOG("Back on selector: leaving the app");
                    ANativeActivity_finish(gApp->activity);
                }
                else
                {
                    WFLOG("Back in level: returning to selector");
                    levelmenu::RequestReturn();
                }
            }
            return 1;
        }
        // Standalone apps keep Back's system meaning once the panel is hidden.
        if (AKeyEvent_getRepeatCount(event) == 0)
            WFLOG("key code=%d action=%d mask=0x%x%s", keyCode, action, mask,
                  mask ? "" : " (unmapped, dropped)");
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

// Read by hal/android/asset_accessor_aasset.cc when creating the accessor
// during _PlatformSpecificInit.
extern "C" WF_ANDROID_EXPORT AAssetManager*
WFAndroidGetAssetManager()
{
    return gAssetMgr;
}

// True while an EGL surface exists (between APP_CMD_INIT_WINDOW and APP_CMD_TERM_WINDOW). HALIsSuspended
// also waits on this: after Home and reopen, APP_CMD_RESUME arrives ~100 ms BEFORE the new window, and drawing
// in that gap raised GL error 1286 and aborted (display.cc AssertGLOK, seen on the Chromecast HD).
extern "C" WF_ANDROID_EXPORT int
WFAndroidHasWindow()
{
    return gEglReady ? 1 : 0;
}

// The shared level and menu loops must finish when NativeActivity is destroyed.
// Otherwise its old game thread survives and competes with a reopened activity
// for the process-global engine and EGL context (EGL_BAD_ACCESS).
extern "C" WF_ANDROID_EXPORT int
WFAndroidCloseRequested()
{
    return gExitLoop ? 1 : 0;
}

extern "C" WF_ANDROID_EXPORT void
WFAndroidRequestClose()
{
    gExitLoop = true;
}

// Called from XEventLoop (display.cc PageFlip) once per frame. Non-blocking
// drain of any queued commands + input events.
extern "C" WF_ANDROID_EXPORT void
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
    PhonePoll();
}

// The phone overlay's rectangles for a w x h surface, drawn by gfx/gl/android_window.cc after
// the touch HUD. Returns the count; *changed is 1 when the list differs from the last call's.
extern "C" WF_ANDROID_EXPORT int
WFAndroidPhoneOverlayRects(int w, int h, const PhonepadRect** rects, int* changed)
{
    *changed = gPhoneOverlay.Build(w, h, NowMs(), &gPhoneRects) ? 1 : 0;
    *rects   = gPhoneRects.data();
    return int(gPhoneRects.size());
}

// Entry point — android_native_app_glue calls this on a dedicated thread
// after ANativeActivity_onCreate returns to the UI thread.
extern "C" WF_ANDROID_EXPORT void
android_main(struct android_app* app)
{
    gApp = app;
    OpenDiagnosticLog(app);
    InstallCrashHandlers();
    WFLOG("android_main: enter");

    app->onAppCmd     = HandleAppCmd;
    app->onInputEvent = HandleInputEvent;

    // AAssetManager is live as soon as the NativeActivity is created;
    // asset_accessor_aasset.cc grabs it during _PlatformSpecificInit.
    if (app->activity && app->activity->assetManager)
        gAssetMgr = app->activity->assetManager;
    WFLOG("android_main: assetMgr=%p", (void*)gAssetMgr);
    PhoneInit();

    if (app->config)
    {
        const int32_t uiMode = AConfiguration_getUiModeType(app->config);
        gIsTvMode = (uiMode == ACONFIGURATION_UI_MODE_TYPE_TELEVISION);
        WFAndroidSetHudEnabled(gIsTvMode ? 0 : 1);
        WFLOG("android_main: uiMode=%d (tv=%d)", uiMode, gIsTvMode ? 1 : 0);
    }

    // Block until the first surface arrives so EGL is live before the
    // engine tries to draw.
    WFLOG("android_main: waiting for APP_CMD_INIT_WINDOW");
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
        WFLOG("android_main: destroyRequested before EGL ready");
        WFAndroidEglTerm();
        return;
    }
    WFLOG("android_main: EGL ready, entering HALStart");

    // Per-app command line: an app flavor may ship assets/wf_args.txt, whitespace-
    // separated arguments appended after argv[0] (the condo app's VRAM overrides,
    // the same flags `task run-condo` passes on the desktop). Absent → argv[0] only,
    // as before. docs/plans/2026-10-01-condo-chromecast.md.
    static char argBuf[1024];
    char arg0[] = "wf_game";
    char* argv[33] = { arg0 };
    int argc = 1;
    if (gAssetMgr)
    {
        if (AAsset* a = AAssetManager_open(gAssetMgr, "wf_args.txt", AASSET_MODE_BUFFER))
        {
            const int n = AAsset_read(a, argBuf, sizeof(argBuf) - 1);
            AAsset_close(a);
            argBuf[n > 0 ? n : 0] = '\0';
            for (char* tok = strtok(argBuf, " \t\r\n"); tok && argc < 32; tok = strtok(nullptr, " \t\r\n"))
            {
                // "qr_logo=planet|full|none": what sits in the middle of the phone-controller QR code
                // (default planet). Read here and not passed on: the engine never sees it.
                if (std::strncmp(tok, "qr_logo=", 8) == 0)
                {
                    const int mode = phonepad::ParseLogoMode(tok + 8);
                    if (mode >= 0) gPhoneOverlay.SetLogo(mode);
                    WFLOG("android_main: %s%s", tok, mode >= 0 ? "" : " (unknown: use planet, full or none)");
                    continue;
                }
                argv[argc++] = tok;
            }
            WFLOG("android_main: wf_args.txt gave %d argument(s)", argc - 1);
        }
    }
    argv[argc] = nullptr;
    // HALStart hands PIGSMain the pigsys globals, not its own argc/argv; on the
    // desktop sys_init() fills them, Android never called it, so PIGSMain saw
    // argc = 0 and every argument was dropped. Set them here.
    __argc = argc;
    __argv = argv;
    HALStart(argc, argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);

    // HALStart returns when the game exits (PIGSMain's loop terminates).
    WFLOG("android_main: HALStart returned, tearing down EGL");
    PhoneStop();
    WFAndroidEglTerm();
    WFLOG("android_main: exit");
    // The legacy engine and renderer have process-lifetime globals. Home keeps
    // this activity alive (singleTask); Back finishes it. Start the next game
    // activity in a fresh process rather than running HALStart a second time
    // against the previous engine's globals and preserved EGL context.
    std::fflush(nullptr);
    _exit(EXIT_SUCCESS);
}
