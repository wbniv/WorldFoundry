//==============================================================================
// emscripten_window.cc — browser/canvas "window" layer for the web build.
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// #included from gfx/gl/display.cc (same pattern as mesa.cc on Linux and
// android_window.cc on Android) — not a standalone translation unit.
//
// Replaces mesa.cc's X11/GLX surface for the web build: a WebGL 2 context on
// the page's #canvas element, DOM keyboard events + Gamepad polling feeding
// the same joystick-button word mesa.cc builds from X key events, and the
// browser's visibilitychange driving the HAL suspend flag.
//
// There is no buffer swap here: the browser composites the canvas whenever
// the wasm yields to the event loop (the ASYNCIFY emscripten_sleep in
// WFGame::StepFrame for v1; the main-loop callback return in v2).
// See docs/plans/2026-06-11-web-canvas-port.md (D3, P2.1).
//==============================================================================

#include <emscripten.h>
#include <emscripten/html5.h>
#include <hal/lifecycle.h>
#include <atomic>
#include <cstring>

extern void _HALSetJoystickButtons(joystickButtonsF joystickButtons);

static joystickButtonsF _joystickButtons = 0;   // keyboard state
static joystickButtonsF _gamepadButtons  = 0;   // gamepad state, rebuilt each poll
static std::atomic<int> _closeRequested{0};
static EMSCRIPTEN_WEBGL_CONTEXT_HANDLE _webglContext = 0;

//==============================================================================
// Keyboard: same bindings as mesa.cc's ProcessXEvents, keyed on the physical
// KeyboardEvent.code so layouts don't move the controls.

static joystickButtonsF
KeyCodeToButton(const char* code)
{
    struct Binding { const char* code; joystickButtonsF button; };
    static const Binding kBindings[] = {
        { "ArrowLeft",      EJ_BUTTONF_LEFT  }, { "KeyJ",    EJ_BUTTONF_LEFT  },
        { "Numpad4",        EJ_BUTTONF_LEFT  },
        { "ArrowRight",     EJ_BUTTONF_RIGHT }, { "KeyL",    EJ_BUTTONF_RIGHT },
        { "Numpad6",        EJ_BUTTONF_RIGHT },
        { "ArrowUp",        EJ_BUTTONF_UP    }, { "KeyI",    EJ_BUTTONF_UP    },
        { "Numpad8",        EJ_BUTTONF_UP    },
        { "ArrowDown",      EJ_BUTTONF_DOWN  }, { "KeyK",    EJ_BUTTONF_DOWN  },
        { "Numpad2",        EJ_BUTTONF_DOWN  },
        { "Space",          EJ_BUTTONF_A     }, { "Digit1",  EJ_BUTTONF_A     },
        { "Numpad0",        EJ_BUTTONF_A     },
        { "Digit2",         EJ_BUTTONF_B     }, { "NumpadDecimal",  EJ_BUTTONF_B },
        { "Digit3",         EJ_BUTTONF_C     }, { "NumpadEnter",    EJ_BUTTONF_C },
        { "Digit4",         EJ_BUTTONF_D     }, { "NumpadAdd",      EJ_BUTTONF_D },
        { "Digit5",         EJ_BUTTONF_E     }, { "NumpadSubtract", EJ_BUTTONF_E },
        { "Digit6",         EJ_BUTTONF_F     }, { "NumpadMultiply", EJ_BUTTONF_F },
        { "Digit7",         EJ_BUTTONF_G     }, { "NumpadDivide",   EJ_BUTTONF_G },
        { "Digit8",         EJ_BUTTONF_H     }, { "Numpad7",        EJ_BUTTONF_H },
        { "Digit9",         EJ_BUTTONF_I     }, { "Numpad9",        EJ_BUTTONF_I },
        { "Digit0",         EJ_BUTTONF_J     }, { "Numpad3",        EJ_BUTTONF_J },
        { "Numpad1",        EJ_BUTTONF_K     },
    };
    for (const Binding& b : kBindings)
        if (strcmp(code, b.code) == 0)
            return b.button;
    return 0;
}

static EM_BOOL
KeyCallback(int eventType, const EmscriptenKeyboardEvent* e, void* /*userData*/)
{
    if (eventType == EMSCRIPTEN_EVENT_KEYDOWN && strcmp(e->code, "Escape") == 0)
    {
        // Same shutdown path as the X11 WM-close button: set the flag, let the
        // main loop run its full cleanup.
        _closeRequested.store(1);
        return EM_TRUE;
    }

    joystickButtonsF button = KeyCodeToButton(e->code);
    if (!button)
        return EM_FALSE;        // not ours — let the browser have it

    if (!e->repeat)             // held-key repeats don't change the state word
    {
        if (eventType == EMSCRIPTEN_EVENT_KEYDOWN)
            _joystickButtons |= button;
        else
            _joystickButtons &= ~button;
        _HALSetJoystickButtons(_joystickButtons | _gamepadButtons);
    }
    return EM_TRUE;             // preventDefault: arrows must not scroll the page
}

//==============================================================================

static EM_BOOL
VisibilityCallback(int /*eventType*/, const EmscriptenVisibilityChangeEvent* e,
                   void* /*userData*/)
{
    // v2 (plan Phase 7): pausing the main loop is the suspend mechanism — the
    // browser stops calling WebTick, so StepFrame isn't run while backgrounded
    // (no torn-down-context renders, no wasted CPU). The first frame after
    // resume gets a large dt, but StepFrame already clamps to 100 ms. (Before
    // any loop is registered these are harmless no-ops.) HALNotify* is kept for
    // HAL-level state; on web HALIsSuspended() stays driven by it but the
    // suspended branch in StepFrame is unreachable because the loop is paused.
    if (e->hidden)
    {
        emscripten_pause_main_loop();
        HALNotifySuspend();
    }
    else
    {
        HALNotifyResume();
        emscripten_resume_main_loop();
    }
    return EM_FALSE;
}

//==============================================================================

bool
InitWindow( int /*xPos*/, int /*yPos*/, int /*xSize*/, int /*ySize*/ )
{
    EmscriptenWebGLContextAttributes attrs;
    emscripten_webgl_init_context_attributes(&attrs);
    attrs.majorVersion = 2;     // WebGL 2 = GLES 3.0, the engine's baseline
    attrs.minorVersion = 0;
    attrs.alpha   = EM_FALSE;
    attrs.depth   = EM_TRUE;
    attrs.stencil = EM_TRUE;
    // v2 (plan Phase 7): the loop is now driven by emscripten_set_main_loop and
    // the engine redraws fully every frame. Preserve the drawing buffer so the
    // canvas keeps showing the last frame between the browser's composites — it
    // removes any present/clear timing fragility (a skipped rAF can't flash a
    // cleared frame) at negligible cost for a full-redraw engine, and makes the
    // frame readable for headless screenshot verification.
    attrs.preserveDrawingBuffer = EM_TRUE;

    _webglContext = emscripten_webgl_create_context("#canvas", &attrs);
    if (_webglContext <= 0)
    {
        printf("InitWindow: emscripten_webgl_create_context failed (%d) — "
               "browser lacks WebGL 2?\n", (int)_webglContext);
        return false;
    }
    emscripten_webgl_make_context_current(_webglContext);

    // Same fixed surface size mesa.cc passes to XCreateWindow; the canvas
    // CSS may scale it, the GL framebuffer stays at this resolution.
    emscripten_set_canvas_element_size("#canvas", wfInitialWindowWidth,
                                       wfInitialWindowHeight);
    glViewport(0, 0, wfInitialWindowWidth, wfInitialWindowHeight);

    emscripten_set_window_title("World Foundry");

    emscripten_set_keydown_callback(EMSCRIPTEN_EVENT_TARGET_WINDOW, nullptr,
                                    EM_FALSE, KeyCallback);
    emscripten_set_keyup_callback(EMSCRIPTEN_EVENT_TARGET_WINDOW, nullptr,
                                  EM_FALSE, KeyCallback);
    emscripten_set_visibilitychange_callback(nullptr, EM_FALSE,
                                             VisibilityCallback);
    return true;
}

//==============================================================================
// Per-frame platform pump (the XEventLoop name is the cross-platform contract
// — Android's android_window.cc provides it too). Keyboard arrives via the
// callbacks above; only the Gamepad API needs polling.

void
XEventLoop()
{
    // Responsive canvas: when the displayed (CSS) size of the canvas changes
    // (window resize, fullscreen enter/exit, iframe/layout reflow), resize the
    // GL backing to match and tell the engine, so the game fills the viewport
    // at the correct aspect instead of the fixed 640×480 set at boot. Polled
    // here (once per frame, acts only on change) so every resize path is caught
    // without juggling resize/fullscreenchange callbacks.
    {
        extern void WFResizeSurface(int w, int h);
        static int sLastW = 0, sLastH = 0;
        double cssW = 0, cssH = 0;
        if (emscripten_get_element_css_size("#canvas", &cssW, &cssH) == EMSCRIPTEN_RESULT_SUCCESS)
        {
            int w = (int)(cssW + 0.5), h = (int)(cssH + 0.5);
            if (w > 0 && h > 0 && (w != sLastW || h != sLastH))
            {
                sLastW = w;
                sLastH = h;
                emscripten_set_canvas_element_size("#canvas", w, h);
                WFResizeSurface(w, h);
            }
        }
    }

    if (emscripten_sample_gamepad_data() != EMSCRIPTEN_RESULT_SUCCESS)
        return;

    joystickButtonsF pad = 0;
    const int numPads = emscripten_get_num_gamepads();
    for (int i = 0; i < numPads; ++i)
    {
        EmscriptenGamepadEvent g;
        if (emscripten_get_gamepad_status(i, &g) != EMSCRIPTEN_RESULT_SUCCESS
            || !g.connected)
            continue;

        // Left stick (standard mapping axes 0/1)
        if (g.numAxes >= 2)
        {
            if (g.axis[0] < -0.5) pad |= EJ_BUTTONF_LEFT;
            if (g.axis[0] >  0.5) pad |= EJ_BUTTONF_RIGHT;
            if (g.axis[1] < -0.5) pad |= EJ_BUTTONF_UP;
            if (g.axis[1] >  0.5) pad |= EJ_BUTTONF_DOWN;
        }
        // Face buttons (standard mapping 0-3) → A-D, like the PSX word
        if (g.numButtons > 0 && g.digitalButton[0]) pad |= EJ_BUTTONF_A;
        if (g.numButtons > 1 && g.digitalButton[1]) pad |= EJ_BUTTONF_B;
        if (g.numButtons > 2 && g.digitalButton[2]) pad |= EJ_BUTTONF_C;
        if (g.numButtons > 3 && g.digitalButton[3]) pad |= EJ_BUTTONF_D;
        // D-pad (standard mapping 12-15)
        if (g.numButtons > 12 && g.digitalButton[12]) pad |= EJ_BUTTONF_UP;
        if (g.numButtons > 13 && g.digitalButton[13]) pad |= EJ_BUTTONF_DOWN;
        if (g.numButtons > 14 && g.digitalButton[14]) pad |= EJ_BUTTONF_LEFT;
        if (g.numButtons > 15 && g.digitalButton[15]) pad |= EJ_BUTTONF_RIGHT;
    }

    if (pad != _gamepadButtons)
    {
        _gamepadButtons = pad;
        _HALSetJoystickButtons(_joystickButtons | _gamepadButtons);
    }
}

//==============================================================================
// Called by the main game loop to know when to break out cleanly.

extern "C" int
HALWindowCloseRequested(void)
{
    return _closeRequested.load();
}

extern "C" void
HALCloseWindow(void)
{
    if (_webglContext)
    {
        emscripten_webgl_destroy_context(_webglContext);
        _webglContext = 0;
    }
}

//==============================================================================
