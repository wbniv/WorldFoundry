// engine/wf_host_gl_test/host_gl_test.cc — smoke test for the editor-host
// GL context registry (gfx/host_gl_context.h) and HALRequestClose.
//
// Phase 0b sub-task #2 of the collaborative editor design. Verifies the
// registry / close-flag chain in isolation:
//   1. Open an X11 Display + GLXContext + Window using the same visual
//      attributes the engine would have picked (mesa.cc:71 attributeList).
//   2. SetHostGLContext({dpy, win, cx, true}); confirm GetHostGLContext
//      returns the same values with valid=true.
//   3. HALRequestClose(); confirm HALWindowCloseRequested() returns 1.
//   4. ClearHostGLContext(); confirm GetHostGLContext returns valid=false.
//   5. Tear down X11/GLX cleanly.
//
// End-to-end exercise (construct WFGame against the host context, drive 60
// StepFrame ticks, glXSwapBuffers the host window) is a follow-up: requires
// either lifting main() out of wfengine.a or linking with
// -Wl,--allow-multiple-definition. Tracked in TODO.md.

#include <gfx/host_gl_context.h>
#include <hal/lifecycle.h>

#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>

#include <cassert>
#include <cstdio>
#include <cstdlib>

namespace {

// Mirror of mesa.cc:71 attributeList. Tests assume the host's chosen visual
// is link-compatible with the engine's expectations; this duplication is
// load-bearing — any drift here vs. mesa.cc is the bug the smoke test
// would surface.
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
    if (!h.dpy) { std::fprintf(stderr, "XOpenDisplay failed\n"); return false; }

    h.vi = glXChooseVisual(h.dpy, DefaultScreen(h.dpy), kAttributeList);
    if (!h.vi) { std::fprintf(stderr, "glXChooseVisual failed\n"); return false; }

    h.cx = glXCreateContext(h.dpy, h.vi, nullptr, GL_TRUE);
    if (!h.cx) { std::fprintf(stderr, "glXCreateContext failed\n"); return false; }

    Window root = RootWindow(h.dpy, h.vi->screen);
    XSetWindowAttributes attr{};
    attr.colormap   = XCreateColormap(h.dpy, root, h.vi->visual, AllocNone);
    attr.event_mask = ExposureMask | StructureNotifyMask;

    h.win = XCreateWindow(h.dpy, root, 0, 0, 64, 64, 0,
                          h.vi->depth, InputOutput, h.vi->visual,
                          CWColormap | CWEventMask, &attr);
    if (!h.win) { std::fprintf(stderr, "XCreateWindow failed\n"); return false; }

    // Note: NOT XMapRaised — keep the test window invisible. The smoke
    // test is verifying the registry plumbing, not painting pixels.
    glXMakeCurrent(h.dpy, h.win, h.cx);
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

int main(int /*argc*/, char** /*argv*/)
{
    HostGL h;
    if (!open_host_context(h)) {
        std::fprintf(stderr, "host_gl_test: failed to set up X11/GLX\n");
        return 1;
    }

    // Test 1: registry write/read round-trips.
    HostGLContext set{h.dpy, static_cast<unsigned long>(h.win), h.cx, true};
    SetHostGLContext(&set);
    HostGLContext got = GetHostGLContext();
    assert(got.valid);
    assert(got.display == h.dpy);
    assert(got.win     == static_cast<unsigned long>(h.win));
    assert(got.context == h.cx);
    std::printf("ok: registry round-trip (display=%p win=%lu context=%p)\n",
                got.display, got.win, got.context);

    // Test 2: HALRequestClose sets the close-requested flag the game loop
    // polls. Mirrors what the X11 WM_DELETE_WINDOW handler does in
    // standalone wf_game.
    assert(HALWindowCloseRequested() == 0);
    HALRequestClose();
    assert(HALWindowCloseRequested() != 0);
    std::printf("ok: HALRequestClose -> HALWindowCloseRequested\n");

    // Test 3: ClearHostGLContext returns the registry to a "no host" state.
    // Important for hosts that briefly own the engine then return to a
    // standalone-style mode (multi-tab editor closing the engine tab).
    ClearHostGLContext();
    got = GetHostGLContext();
    assert(!got.valid);
    assert(got.display == nullptr);
    assert(got.win     == 0);
    assert(got.context == nullptr);
    std::printf("ok: ClearHostGLContext clears registry\n");

    close_host_context(h);
    std::printf("host_gl_test: all checks passed\n");
    return 0;
}
