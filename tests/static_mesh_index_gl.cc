// Shared-index regression: interleaved 16/32-bit draws, deletion, last-owner
// release and stale-handle destruction after context loss. Run on private Xvfb.
#include <gfx/renderer_backend.hp>
#include <gfx/static_mesh.hp>
#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>
#include <cstdio>
#include <cstdlib>
#include <vector>

extern RendererBackend* ModernBackendInstance();
extern void ModernBackendSimulateSurfaceLoss();

static void Require(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "static_mesh_index_gl: %s\n", what); std::exit(1); }
}

static RBStaticTriangle Triangle(float left, float r, float g, float b)
{
    RBStaticTriangle t = {};
    t.v[0] = {left, -.8f, 0, r, g, b, 0, 0};
    t.v[1] = {left + .8f, -.8f, 0, r, g, b, 0, 0};
    t.v[2] = {left + .4f, .8f, 0, r, g, b, 0, 0};
    t.nz = 1; t.opacity = 1; t.paletteLight = 0xffffff;
    return t;
}

static void Pixel(int x, int y, unsigned char r, unsigned char g, unsigned char b)
{
    unsigned char p[4] = {};
    glReadPixels(x, y, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, p);
    Require(p[0] == r && p[1] == g && p[2] == b, "wrong pixel after indexed draw");
}

static size_t Gpu(RendererBackend* backend)
{
    size_t gpu, cpu; backend->StaticMeshBytes(gpu, cpu); return gpu;
}

int main(int argc, char** argv)
{
    StaticMeshSetSharedIndex(argc < 2 || std::atoi(argv[1]) != 0);
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

    const RBStaticTriangle red = Triangle(-.9f, 1, 0, 0);
    std::vector<RBStaticTriangle> large(21846, Triangle(.1f, 0, 1, 0));
    RBStaticMeshHandle small = backend->CreateStaticMesh(&red, 1);
    RBStaticMeshHandle big = backend->CreateStaticMesh(large.data(), int(large.size()));
    Require(small && big, "mesh creation failed");
    const size_t vertices = Gpu(backend);
    const unsigned first = 0, last = 21845; // vertices 65535..65537 need 32-bit indices
    glClear(GL_COLOR_BUFFER_BIT);
    backend->DrawStaticTriangles(small, &first, 1, nullptr, true);
    backend->DrawStaticTriangles(big, &last, 1, nullptr, true);
    backend->EndFrame();
    Pixel(16, 24, 255, 0, 0); Pixel(48, 24, 0, 255, 0);
    Require(Gpu(backend) == vertices + (StaticMeshSharedIndex() ? 12 : 18), "index bytes counted incorrectly");

    // Deleting another mesh must not delete the buffer used by a queued draw.
    glClear(GL_COLOR_BUFFER_BIT);
    backend->DrawStaticTriangles(big, &last, 1, nullptr, true);
    backend->DestroyStaticMesh(small);
    backend->EndFrame(); Pixel(48, 24, 0, 255, 0);
    // Return to 16-bit indices, then destroy the mesh whose draw is still queued.
    small = backend->CreateStaticMesh(&red, 1);
    backend->DrawStaticTriangles(small, &first, 1, nullptr, true);
    backend->DestroyStaticMesh(small);
    Pixel(16, 24, 255, 0, 0);
    backend->DestroyStaticMesh(big);
    Require(Gpu(backend) == 0, "last-owner cleanup retained GPU bytes");

    // Drop the real context as Android does. Destroy stale handles after a
    // new generation has acquired a new shared buffer, guarding the refcount.
    small = backend->CreateStaticMesh(&red, 1);
    ModernBackendSimulateSurfaceLoss();
    Require(!backend->StaticMeshLive(small) && Gpu(backend) == 0, "loss did not invalidate mesh");
    glXMakeCurrent(dpy, None, nullptr); glXDestroyContext(dpy, context);
    context = glXCreateContext(dpy, visual, nullptr, GL_TRUE);
    Require(context && glXMakeCurrent(dpy, win, context), "replacement context setup failed");
    glViewport(0, 0, 64, 64); glDisable(GL_DITHER);
    big = backend->CreateStaticMesh(large.data(), int(large.size()));
    Require(big, "mesh creation after loss failed");
    backend->DestroyStaticMesh(small);
    backend->DrawStaticTriangles(big, &last, 1, nullptr, true);
    backend->EndFrame(); Pixel(48, 24, 0, 255, 0);
    backend->DestroyStaticMesh(big);
    Require(Gpu(backend) == 0, "cleanup after loss retained GPU bytes");
    Require(glGetError() == GL_NO_ERROR, "GL error");
    glXMakeCurrent(dpy, None, nullptr); glXDestroyContext(dpy, context);
    XDestroyWindow(dpy, win); XFreeColormap(dpy, attr.colormap); XFree(visual); XCloseDisplay(dpy);
    std::puts("static_mesh_index_gl: PASS");
    return 0;
}
