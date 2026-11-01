// Depth testing in a GL context created after a loss. Run on private Xvfb.
//
// Android's in-place rebuild (gfx/gl/android_window.cc RebuildEglContext)
// makes a new EGL context, and a new context starts with every capability at
// its default: GL_DEPTH_TEST off. The renderer never enabled depth testing
// per frame; it was a side effect of CreateTexture at level load, which does
// not run again after a loss. So after the rebuild the scene drew in
// submission order and later, farther geometry painted over nearer objects
// (the player's torso, the Goddess, doors and window frames on Cast2,
// finding-your-way docs/diagnostics/context-loss-device-2026-11-01/). The
// desktop context-loss tests deleted objects in the same context, whose state
// survived, so they never saw it.
//
// Here a second GLX context stands in for the rebuilt one: the backend is told
// of the loss, then draws a near red triangle before a far green one over the
// same pixels. With depth testing the centre stays red.
#define Display X11Display
#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>
#undef Display
#include <gfx/renderer_backend.hp>
#include <cstdio>
#include <cstdlib>

extern void ModernBackendSimulateSurfaceLoss();

static void Require(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "egl_rebuild_depth_gl: %s\n", what); std::exit(1); }
}

static const int SIZE = 32;

// A triangle covering the whole viewport at eye-space depth z, in one colour.
static void Cover(RendererBackend& backend, float z, float r, float g, float b)
{
    const float s = -z * 4.0f;      // well past the 60-degree frustum at that depth
    const RBVertex v0 = { -s, -s, z, r, g, b, 0, 0 };
    const RBVertex v1 = {  s, -s, z, r, g, b, 0, 0 };
    const RBVertex v2 = {  0,  s, z, r, g, b, 0, 0 };
    backend.DrawTriangle(v0, v1, v2, 0, 0, 1, nullptr, true);
}

// Clear, draw near red then far green, flush, and read the centre pixel.
static void DrawNearThenFar(RendererBackend& backend, unsigned char rgba[4])
{
    glViewport(0, 0, SIZE, SIZE);
    glClearColor(0, 0, 1, 1);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    backend.SetProjection(60.0f, 1.0f, 1.0f, 100.0f);
    backend.ResetModelView();
    backend.SetLightingEnabled(false);
    backend.SetFogEnabled(false);
    Cover(backend, -2.0f, 1, 0, 0);
    Cover(backend, -5.0f, 0, 1, 0);
    backend.EndFrame();
    glReadBuffer(GL_BACK);
    glReadPixels(SIZE / 2, SIZE / 2, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, rgba);
}

int main()
{
    X11Display* dpy = XOpenDisplay(nullptr);
    Require(dpy, "XOpenDisplay failed");
    int attributes[] = {GLX_RGBA, GLX_RED_SIZE, 8, GLX_GREEN_SIZE, 8, GLX_BLUE_SIZE, 8, GLX_DEPTH_SIZE, 16,
                        GLX_DOUBLEBUFFER, None};
    XVisualInfo* visual = glXChooseVisual(dpy, DefaultScreen(dpy), attributes);
    Require(visual, "glXChooseVisual failed");
    XSetWindowAttributes attr = {};
    attr.colormap = XCreateColormap(dpy, RootWindow(dpy, visual->screen), visual->visual, AllocNone);
    Window win = XCreateWindow(dpy, RootWindow(dpy, visual->screen), 0, 0, SIZE, SIZE, 0,
                               visual->depth, InputOutput, visual->visual, CWColormap, &attr);
    XMapWindow(dpy, win); XSync(dpy, False);
    GLXContext first = glXCreateContext(dpy, visual, nullptr, GL_TRUE);
    Require(first && glXMakeCurrent(dpy, win, first), "GL context setup failed");

    // Level load as it happens in the game: a level texture is created first.
    RendererBackend& backend = RendererBackendGet();
    const unsigned char texel[4] = {255, 255, 255, 255};
    Require(backend.CreateTexture(1, 1, RB_TEX_RGBA8, texel) != nullptr, "CreateTexture failed");
    unsigned char rgba[4] = {};
    DrawNearThenFar(backend, rgba);
    Require(rgba[0] > 200 && rgba[1] < 50, "first context: the far triangle was drawn over the near one");

    // The rebuild: a new context, current on the same surface, after the loss.
    GLXContext second = glXCreateContext(dpy, visual, nullptr, GL_TRUE);
    Require(second && glXMakeCurrent(dpy, win, second), "second GL context setup failed");
    Require(!glIsEnabled(GL_DEPTH_TEST), "test setup: a new context should start without depth testing");
    ModernBackendSimulateSurfaceLoss();
    DrawNearThenFar(backend, rgba);
    Require(glIsEnabled(GL_DEPTH_TEST), "rebuilt context: depth testing is off after the first draw");
    Require(rgba[0] > 200 && rgba[1] < 50, "rebuilt context: the far triangle was drawn over the near one");
    Require(glGetError() == GL_NO_ERROR, "GL error");
    std::puts("egl_rebuild_depth_gl: ok");
    return 0;
}
