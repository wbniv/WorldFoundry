// engine/wf_host_gl_test/host_gl_e2e_test.cc — end-to-end host-GL integration
// test. The companion smoke test (host_gl_test.cc) verifies the registry +
// close-flag plumbing in isolation against a stubbed mesa.cc. This binary
// is the real thing: it links libwfengine.a, opens its own X11/GLX, registers
// the context with SetHostGLContext, then drives WFGame through the full
// LoadLevel → StepFrame × N → UnloadLevel cycle (re-used via HALStart's
// existing --frame-step-smoke / --cycles CLI path).
//
// Phase 0b sub-task #3 of the collaborative editor design. Proves:
//   - libwfengine.a links cleanly without colliding with the harness's main()
//     (Phase A platform.cc split paid off).
//   - mesa.cc's InitWithExistingContext path adopts the host's display/window/
//     context instead of OpenMainWindow'ing its own.
//   - The unload chain (Phase B LIFO fixes) holds when driven by an external
//     host, not just wf_game's own main.
//
// Usage:
//   wf_host_gl_e2e_test [--frames=N] [--cycles=N] [--level=PATH]
// Default: frames=30, cycles=1, level=wflevels/qbert_practice/qbert_practice-standalone.iff
//
// Exit codes:
//   0 — all cycles completed cleanly, full Load/Unload chain didn't crash.
//   non-zero — X11 setup failure, level file missing, or HALStart aborted.
//
// Verified 2026-05-18: cycles=1 and cycles=2 on qbert_practice exit 0 with
// the full Load → StepFrame×N → UnloadLevel chain. Multi-cycle on snowgoons
// crashes during cycle 2+ — same crash in wf_game, pre-existing snowgoons-
// specific issue, NOT host-GL specific. See docs/BUGS.md for the Jolt ODR
// violation that gated this harness for several hours; the fix was to
// PUBLIC-define NDEBUG on the Jolt CMake target so JPH_ENABLE_ASSERTS is
// consistently off across Jolt.a and its consumers.

#include <gfx/host_gl_context.h>
#include <hal/hal.h>
#include <pigsys/pigsys.hp>

#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

extern "C" int HALWindowCloseRequested(void);
extern void ParseWindowSwitches(int argc, char** argv);
extern char szAppName[];

namespace {

// Mirror of mesa.cc:71 attributeList. mesa.cc's InitWithExistingContext
// adopts whatever visual the host already picked, but matching here keeps
// the harness's window depth-buffer-compatible with what wf_game would
// normally create.
int kAttributeList[] = {
    GLX_RGBA,
    GLX_RED_SIZE,   1,
    GLX_GREEN_SIZE, 1,
    GLX_BLUE_SIZE,  1,
    GLX_DOUBLEBUFFER,
    GLX_DEPTH_SIZE, 1,
    None
};

struct HostGL {
    Display*    dpy = nullptr;
    XVisualInfo* vi = nullptr;
    Window      win = 0;
    GLXContext  cx = nullptr;
};

bool open_host_context(HostGL& h)
{
    h.dpy = XOpenDisplay(nullptr);
    if (!h.dpy) { std::fprintf(stderr, "XOpenDisplay failed (DISPLAY set?)\n"); return false; }

    h.vi = glXChooseVisual(h.dpy, DefaultScreen(h.dpy), kAttributeList);
    if (!h.vi) { std::fprintf(stderr, "glXChooseVisual failed\n"); return false; }

    h.cx = glXCreateContext(h.dpy, h.vi, nullptr, GL_TRUE);
    if (!h.cx) { std::fprintf(stderr, "glXCreateContext failed\n"); return false; }

    Window root = RootWindow(h.dpy, h.vi->screen);
    XSetWindowAttributes attr{};
    attr.colormap   = XCreateColormap(h.dpy, root, h.vi->visual, AllocNone);
    attr.event_mask = ExposureMask | StructureNotifyMask;

    h.win = XCreateWindow(h.dpy, root, 0, 0, 512, 384, 0,
                          h.vi->depth, InputOutput, h.vi->visual,
                          CWColormap | CWEventMask, &attr);
    if (!h.win) { std::fprintf(stderr, "XCreateWindow failed\n"); return false; }

    XMapRaised(h.dpy, h.win);
    XSync(h.dpy, False);

    if (!glXMakeCurrent(h.dpy, h.win, h.cx)) {
        std::fprintf(stderr, "glXMakeCurrent failed\n"); return false;
    }
    return true;
}

void close_host_context(HostGL& h)
{
    if (h.dpy) {
        glXMakeCurrent(h.dpy, None, nullptr);
        if (h.cx)  glXDestroyContext(h.dpy, h.cx);
        if (h.win) XDestroyWindow(h.dpy, h.win);
        if (h.vi)  XFree(h.vi);
        XCloseDisplay(h.dpy);
    }
}

}  // namespace

int main(int argc, char** argv)
{
    // Parse our own args before handing off to HALStart.
    int         frames = 30;
    int         cycles = 1;
    std::string level  = "/home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/qbert_practice-standalone.iff";

    for (int i = 1; i < argc; ++i) {
        if (std::strncmp(argv[i], "--frames=", 9) == 0) {
            frames = std::atoi(argv[i] + 9);
        } else if (std::strncmp(argv[i], "--cycles=", 9) == 0) {
            cycles = std::atoi(argv[i] + 9);
        } else if (std::strncmp(argv[i], "--level=", 8) == 0) {
            level = argv[i] + 8;
        } else {
            std::fprintf(stderr, "wf_host_gl_e2e_test: unknown arg '%s'\n", argv[i]);
            std::fprintf(stderr, "  usage: %s [--frames=N] [--cycles=N] [--level=PATH]\n", argv[0]);
            return 2;
        }
    }
    std::printf("host_gl_e2e: frames=%d cycles=%d level=%s\n", frames, cycles, level.c_str());

    // 1. Open the host's X11/GLX (the "editor's window" stand-in).
    HostGL h;
    if (!open_host_context(h)) {
        std::fprintf(stderr, "host_gl_e2e: failed to set up X11/GLX\n");
        return 1;
    }
    std::printf("host_gl_e2e: opened host window dpy=%p win=%lu ctx=%p\n",
                (void*)h.dpy, (unsigned long)h.win, (void*)h.cx);

    // 2. Register with the engine BEFORE HALStart runs. mesa.cc's
    //    InitWithExistingContext will see valid=true and adopt these
    //    instead of opening its own window.
    HostGLContext set{h.dpy, static_cast<unsigned long>(h.win), h.cx, true};
    SetHostGLContext(&set);

    // 3. Build an argv for HALStart → PIGSMain. Re-use wf_game's existing
    //    --frame-step-smoke / --cycles / -L flags so this harness exercises
    //    the same Load/Step/Unload path that `wf_game --frame-step-smoke`
    //    does — no second copy of that logic.
    char frames_arg[64];
    char cycles_arg[64];
    char level_arg[1024];
    std::snprintf(frames_arg, sizeof(frames_arg), "--frame-step-smoke=%d", frames);
    std::snprintf(cycles_arg, sizeof(cycles_arg), "--cycles=%d", cycles);
    std::snprintf(level_arg,  sizeof(level_arg),  "-L%s", level.c_str());

    char prog_arg[] = "wf_host_gl_e2e_test";
    char* hal_argv_storage[] = { prog_arg, frames_arg, cycles_arg, level_arg, nullptr };
    char** hal_argv = hal_argv_storage;
    int    hal_argc = 4;

    // 4. Drive the engine. The init dance mirrors platform_main.cc's main():
    //    sys_init populates the pigsys __argc/__argv globals that HALStart
    //    forwards to PIGSMain; ParseWindowSwitches fills the _halWindow*
    //    globals the engine reads for default window dimensions.
    sys_init(&hal_argc, &hal_argv);
    std::strcpy(hal_argv[0], szAppName);  // matches platform_main.cc:48
    ParseWindowSwitches(hal_argc, hal_argv);

    // HALStart does _PlatformSpecificInit + audio/joystick setup, calls
    // PIGSMain (which sees --frame-step-smoke=N --cycles=M and runs
    // SmokeRunFrameStep), then tears down. Engine teardown frees everything
    // the LIFO fixes from Phase B address.
    std::printf("host_gl_e2e: HALStart...\n");
    HALStart(hal_argc, hal_argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
    std::printf("host_gl_e2e: HALStart returned\n");

    // 5. Engine has released its references to the host context. Clear the
    //    registry and tear down our X11/GLX.
    ClearHostGLContext();
    close_host_context(h);

    std::printf("host_gl_e2e: all cycles complete\n");
    return 0;
}
