// Frame-profile regression: the backend draws a frame's last batch in
// EndFrame (PageFlip), after Level::RenderScene has closed the profile frame.
// That batch's draws and triangles must count in the frame they belong to.
// Each case below is a frame whose only batch is the one EndFrame flushes.
// Run on private Xvfb.
#include <gfx/renderer_backend.hp>
#include <game/runtime_profile.hp>
#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>
#include <cstdio>
#include <cstdlib>

extern RendererBackend* ModernBackendInstance();

static void Require(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "frame_profile_flush_gl: %s\n", what); std::exit(1); }
}

static RBStaticTriangle Triangle(float left)
{
    RBStaticTriangle t = {};
    t.v[0] = {left, -.8f, 0, 1, 0, 0, 0, 0};
    t.v[1] = {left + .3f, -.8f, 0, 1, 0, 0, 0, 0};
    t.v[2] = {left + .15f, .8f, 0, 1, 0, 0, 0, 0};
    t.nz = 1; t.opacity = 1; t.paletteLight = 0xffffff;
    return t;
}

static unsigned long Total(int counter) { return wf_profile::state().totals[counter]; }

int main()
{
    Display* dpy = XOpenDisplay(nullptr);
    Require(dpy, "XOpenDisplay failed");
    int attributes[] = {GLX_RGBA, GLX_RED_SIZE, 8, GLX_GREEN_SIZE, 8,
                        GLX_BLUE_SIZE, 8, GLX_DOUBLEBUFFER, None};
    XVisualInfo* visual = glXChooseVisual(dpy, DefaultScreen(dpy), attributes);
    Require(visual, "glXChooseVisual failed");
    XSetWindowAttributes attr = {};
    attr.colormap = XCreateColormap(dpy, RootWindow(dpy, visual->screen), visual->visual, AllocNone);
    Window win = XCreateWindow(dpy, RootWindow(dpy, visual->screen), 0, 0, 64, 64, 0,
                              visual->depth, InputOutput, visual->visual, CWColormap, &attr);
    XMapWindow(dpy, win); XSync(dpy, False);
    GLXContext context = glXCreateContext(dpy, visual, nullptr, GL_TRUE);
    Require(context && glXMakeCurrent(dpy, win, context), "GL context setup failed");
    glViewport(0, 0, 64, 64);
    glDisable(GL_DEPTH_TEST); glDisable(GL_DITHER);
    RendererBackend* backend = ModernBackendInstance();
    backend->SetLightingEnabled(false); backend->SetFogEnabled(false);
    wf_profile::enableFresh();

    // Streamed: five triangles under one state form one batch, still queued
    // when the frame closes.
    wf_profile::begin_frame();
    for (int i = 0; i < 5; ++i)
    {
        const RBStaticTriangle t = Triangle(-.9f + .35f * i);
        backend->DrawTriangle(t.v[0], t.v[1], t.v[2], t.nx, t.ny, t.nz, nullptr, true, true);
    }
    wf_profile::end_frame();
    backend->EndFrame();
    wf_profile::begin_frame();
    Require(wf_profile::state().frames.size() == 1, "streamed frame not folded at the next begin_frame");
    Require(Total(wf_profile::Draws) == 1, "streamed final batch's draw not counted in its frame");
    Require(Total(wf_profile::Triangles) == 5, "streamed final batch's triangles not counted in its frame");
    Require(Total(wf_profile::Uploads) == 1, "streamed final batch's upload not counted in its frame");

    // Static: three baked triangles drawn as one indexed batch.
    RBStaticTriangle three[3] = {Triangle(-.9f), Triangle(-.2f), Triangle(.5f)};
    RBStaticMeshHandle mesh = backend->CreateStaticMesh(three, 3);
    Require(mesh, "mesh creation failed");
    const unsigned all[3] = {0, 1, 2};
    backend->DrawStaticTriangles(mesh, all, 3, nullptr, true);
    wf_profile::end_frame();
    backend->EndFrame();
    // Paused: the level renders without updating, so end_frame follows
    // end_frame and folds the frame before it.
    wf_profile::end_frame();
    Require(wf_profile::state().frames.size() == 2, "frame not folded by a following end_frame");
    Require(Total(wf_profile::Triangles) == 5 + 3, "static final batch's triangles not counted in its frame");
    Require(Total(wf_profile::StaticDraws) == 1, "static final batch's draw not counted in its frame");
    Require(wf_profile::state().maxima[wf_profile::Triangles] == 5, "per-frame maximum wrong");
    backend->DestroyStaticMesh(mesh);

    glXMakeCurrent(dpy, None, nullptr);
    glXDestroyContext(dpy, context);
    XDestroyWindow(dpy, win);
    XCloseDisplay(dpy);
    std::puts("frame_profile_flush_gl: ok");
    return 0;
}
