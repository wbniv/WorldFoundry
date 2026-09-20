//=============================================================================
// hal/macos/window_macos.mm: GLFW window + CAMetalLayer host, and the macOS
// half of the HAL window/input seam.
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 4 of docs/plans/2026-09-20-macos-metal-renderer.md.
//
// D5/O4 chose GLFW over a bespoke ~150-line AppKit host so wf_game and wf_edit
// share one windowing + input path on macOS and gamepad support comes free.
// GLFW's Cocoa backend needed no coaxing against CAMetalLayer, so the escape
// hatch in D5 was not taken.
//
// D2 is preserved: the frame stays synchronous and owned by Display. GLFW is
// asked for a GLFW_NO_API window — it creates no context and drives no draw
// callback — and the engine keeps calling glfwPollEvents once per frame. That
// is the whole reason MTKView was rejected in D5.
//
// FAIL-SOFT THROUGHOUT. A CI runner with no window-server session cannot make
// a window, and that must degrade to the Phase 2-3 offscreen path rather than
// abort: Create() returns false, Exists() stays false, and the headless
// --frame-step-smoke run is bit-for-bit what it was before this file existed.
//=============================================================================

#import <Cocoa/Cocoa.h>
#import <QuartzCore/CAMetalLayer.h>
#import <Metal/Metal.h>

#define GLFW_INCLUDE_NONE
#define GLFW_EXPOSE_NATIVE_COCOA
#include <GLFW/glfw3.h>
#include <GLFW/glfw3native.h>

#include <pigsys/pigsys.hp>
#include <hal/lifecycle.h>
#include <hal/sjoystic.h>          // joystickButtonsF, EJ_BUTTONF_*
#include <hal/macos/window_macos.h>

#include <atomic>
#include <cstdio>

// The joystick-button seam the engine reads. Linux feeds it from
// ProcessXEvents (gfx/gl/mesa.cc:263), Android from native_app_entry.cc:134.
// This file is the macOS feeder. Declared with the real joystickButtonsF type
// from sjoystic.h rather than a hand-written `unsigned int`: it has C linkage,
// so a mismatched parameter type would link cleanly and misbehave at runtime.
extern "C" void _HALSetJoystickButtons(joystickButtonsF joystickButtons);

namespace {

GLFWwindow*    g_window     = nullptr;
CAMetalLayer*  g_layer      = nil;
bool           g_inited     = false;
joystickButtonsF g_buttons  = 0;
std::atomic<int> g_closeRequested{0};

// Same chords as the Linux X11 path (gfx/gl/mesa.cc:288-345) so muscle memory
// and the level-design docs carry over unchanged. Deliberately a mapping
// function rather than a copied switch: one table, obvious to diff.
joystickButtonsF ButtonForKey(int key)
{
    switch (key)
    {
        case GLFW_KEY_LEFT:  case GLFW_KEY_KP_4: case GLFW_KEY_J: return EJ_BUTTONF_LEFT;
        case GLFW_KEY_RIGHT: case GLFW_KEY_KP_6: case GLFW_KEY_L: return EJ_BUTTONF_RIGHT;
        case GLFW_KEY_UP:    case GLFW_KEY_KP_8: case GLFW_KEY_I: return EJ_BUTTONF_UP;
        case GLFW_KEY_DOWN:  case GLFW_KEY_KP_2: case GLFW_KEY_K: return EJ_BUTTONF_DOWN;
        case GLFW_KEY_SPACE: case GLFW_KEY_1:    case GLFW_KEY_KP_0:       return EJ_BUTTONF_A;
        case GLFW_KEY_2:     case GLFW_KEY_KP_DECIMAL:                     return EJ_BUTTONF_B;
        case GLFW_KEY_3:     case GLFW_KEY_KP_ENTER:                       return EJ_BUTTONF_C;
        case GLFW_KEY_4:     case GLFW_KEY_KP_ADD:                         return EJ_BUTTONF_D;
        case GLFW_KEY_5:     case GLFW_KEY_KP_SUBTRACT:                    return EJ_BUTTONF_E;
        case GLFW_KEY_6:     case GLFW_KEY_KP_MULTIPLY:                    return EJ_BUTTONF_F;
        default: return 0;
    }
}

void KeyCallback(GLFWwindow*, int key, int, int action, int)
{
    if (key == GLFW_KEY_ESCAPE && action == GLFW_PRESS)
    {
        g_closeRequested.store(1, std::memory_order_release);
        return;
    }
    const joystickButtonsF bit = ButtonForKey(key);
    if (!bit) return;
    if      (action == GLFW_PRESS)   g_buttons |=  bit;
    else if (action == GLFW_RELEASE) g_buttons &= ~bit;
    _HALSetJoystickButtons(g_buttons);
}

void CloseCallback(GLFWwindow*)
{
    g_closeRequested.store(1, std::memory_order_release);
}

// Retina: the layer must be sized in PIXELS and told the backing scale, or the
// drawable is a quarter of the window and everything renders into the
// bottom-left corner. GLFW reports both sizes; the framebuffer one is pixels.
void SyncDrawableSize()
{
    if (!g_window || !g_layer) return;
    int fbw = 0, fbh = 0;
    glfwGetFramebufferSize(g_window, &fbw, &fbh);
    if (fbw <= 0 || fbh <= 0) return;

    NSWindow* nsw = glfwGetCocoaWindow(g_window);
    const CGFloat scale = nsw ? [nsw backingScaleFactor] : 1.0;
    g_layer.contentsScale = scale;
    g_layer.drawableSize  = CGSizeMake(fbw, fbh);
}

void FramebufferSizeCallback(GLFWwindow*, int, int)
{
    SyncDrawableSize();
}

// GLFW gamepad state, polled each frame and OR'd into the keyboard bits. Free
// with GLFW, and the reason D5 preferred it over an AppKit host.
void PollGamepad()
{
    GLFWgamepadstate gs;
    if (!glfwJoystickIsGamepad(GLFW_JOYSTICK_1) ||
        !glfwGetGamepadState(GLFW_JOYSTICK_1, &gs))
        return;

    joystickButtonsF pad = 0;
    const float ax = gs.axes[GLFW_GAMEPAD_AXIS_LEFT_X];
    const float ay = gs.axes[GLFW_GAMEPAD_AXIS_LEFT_Y];
    const float kDead = 0.35f;          // generous: this is a d-pad surrogate
    if (gs.buttons[GLFW_GAMEPAD_BUTTON_DPAD_LEFT]  || ax < -kDead) pad |= EJ_BUTTONF_LEFT;
    if (gs.buttons[GLFW_GAMEPAD_BUTTON_DPAD_RIGHT] || ax >  kDead) pad |= EJ_BUTTONF_RIGHT;
    if (gs.buttons[GLFW_GAMEPAD_BUTTON_DPAD_UP]    || ay < -kDead) pad |= EJ_BUTTONF_UP;
    if (gs.buttons[GLFW_GAMEPAD_BUTTON_DPAD_DOWN]  || ay >  kDead) pad |= EJ_BUTTONF_DOWN;
    if (gs.buttons[GLFW_GAMEPAD_BUTTON_A]) pad |= EJ_BUTTONF_A;
    if (gs.buttons[GLFW_GAMEPAD_BUTTON_B]) pad |= EJ_BUTTONF_B;
    if (gs.buttons[GLFW_GAMEPAD_BUTTON_X]) pad |= EJ_BUTTONF_C;
    if (gs.buttons[GLFW_GAMEPAD_BUTTON_Y]) pad |= EJ_BUTTONF_D;
    if (gs.buttons[GLFW_GAMEPAD_BUTTON_START]) g_closeRequested.store(1, std::memory_order_release);

    _HALSetJoystickButtons(g_buttons | pad);
}

void ErrorCallback(int code, const char* desc)
{
    std::printf("macos: glfw error %d: %s\n", code, desc ? desc : "(null)");
    std::fflush(stdout);
}

}  // namespace

namespace wf_macos_window {

bool Create(int width, int height, bool fullscreen, const char* title)
{
    if (g_window) return true;

    glfwSetErrorCallback(ErrorCallback);
    if (!g_inited)
    {
        if (!glfwInit())
        {
            // Expected on a build machine with no window-server session. Say so
            // plainly — a silent fallback here would look identical to a
            // working window in the log, which is how a broken visual gate gets
            // called green.
            std::printf("macos: glfwInit failed — no window (headless session?); "
                        "falling back to the offscreen render target\n");
            std::fflush(stdout);
            return false;
        }
        g_inited = true;
    }

    // NO_API: GLFW makes the window and pumps events, but creates no GL/GLES
    // context and owns no frame loop. Display keeps the frame (D2).
    glfwWindowHint(GLFW_CLIENT_API, GLFW_NO_API);
    glfwWindowHint(GLFW_SCALE_TO_MONITOR, GLFW_TRUE);

    GLFWmonitor* monitor = fullscreen ? glfwGetPrimaryMonitor() : nullptr;
    g_window = glfwCreateWindow(width, height,
                                title ? title : "World Foundry",
                                monitor, nullptr);
    if (!g_window)
    {
        std::printf("macos: glfwCreateWindow(%dx%d) failed — "
                    "falling back to the offscreen render target\n", width, height);
        std::fflush(stdout);
        return false;
    }

    // Attach a CAMetalLayer to the content view. This is the whole GLFW/Metal
    // handshake: glfwGetCocoaWindow gives the NSWindow, and the layer replaces
    // the view's default backing layer.
    NSWindow* nsw  = glfwGetCocoaWindow(g_window);
    NSView*   view = [nsw contentView];
    g_layer = [CAMetalLayer layer];
    g_layer.device          = MTLCreateSystemDefaultDevice();
    g_layer.pixelFormat     = MTLPixelFormatBGRA8Unorm;
    g_layer.framebufferOnly = NO;   // NO so --capture-frame can read it back
    [view setWantsLayer:YES];
    [view setLayer:g_layer];

    SyncDrawableSize();

    glfwSetKeyCallback(g_window, KeyCallback);
    glfwSetWindowCloseCallback(g_window, CloseCallback);
    glfwSetFramebufferSizeCallback(g_window, FramebufferSizeCallback);

    int fbw = 0, fbh = 0;
    glfwGetFramebufferSize(g_window, &fbw, &fbh);
    std::printf("macos: window %dx%d points, %dx%d pixels (scale %.1f), "
                "CAMetalLayer attached\n",
                width, height, fbw, fbh,
                (double)(nsw ? [nsw backingScaleFactor] : 1.0));
    std::fflush(stdout);
    return true;
}

bool  Exists()      { return g_window != nullptr; }
void* MetalLayer()  { return (__bridge void*)g_layer; }

void PollEvents()
{
    if (!g_window) return;
    glfwPollEvents();
    PollGamepad();
    if (glfwWindowShouldClose(g_window))
        g_closeRequested.store(1, std::memory_order_release);
}

void GetDrawableSize(int& width, int& height)
{
    width = height = 0;
    if (!g_window) return;
    glfwGetFramebufferSize(g_window, &width, &height);
}

bool CloseRequested() { return g_closeRequested.load(std::memory_order_acquire) != 0; }

void SetSize(int width, int height)
{
    if (g_window && width > 0 && height > 0)
    {
        glfwSetWindowSize(g_window, width, height);
        SyncDrawableSize();
    }
}

void SetFullscreen(bool fullscreen)
{
    if (!g_window) return;
    if (fullscreen)
    {
        GLFWmonitor* m = glfwGetPrimaryMonitor();
        if (!m) return;
        const GLFWvidmode* mode = glfwGetVideoMode(m);
        if (!mode) return;
        glfwSetWindowMonitor(g_window, m, 0, 0,
                             mode->width, mode->height, mode->refreshRate);
    }
    else
    {
        int w = 0, h = 0;
        glfwGetWindowSize(g_window, &w, &h);
        glfwSetWindowMonitor(g_window, nullptr, 100, 100, w, h, 0);
    }
    SyncDrawableSize();
}

void Destroy()
{
    if (g_window) { glfwDestroyWindow(g_window); g_window = nullptr; }
    g_layer = nil;
    if (g_inited) { glfwTerminate(); g_inited = false; }
}

}  // namespace wf_macos_window

//=============================================================================
// The HAL seam. These replace the atomics-with-no-window-behind-them that
// hal/macos/window_macos.cc carried through Phases 0-3.
//=============================================================================

extern "C" int
HALWindowCloseRequested(void)
{
    return wf_macos_window::CloseRequested() ? 1 : 0;
}

extern "C" void
HALRequestClose(void)
{
    g_closeRequested.store(1, std::memory_order_release);
}

extern "C" void
HALCloseWindow(void)
{
    wf_macos_window::Destroy();
}
