// Verify baked vertex colors interpolate over a texture on the actual GL backend.
#include <gfx/renderer_backend.hp>
#include <gfx/pixelmap.hp>
#define GL_GLEXT_PROTOTYPES 1
#include <GL/gl.h>
#define Display XDisplay
#include <GL/glx.h>
#include <X11/Xlib.h>
#undef Display
#include <cmath>
#include <cstdio>
#include <cstdlib>

extern RendererBackend* ModernBackendInstance();
static void require(bool ok, const char* what) {
    if (!ok) { std::fprintf(stderr, "prelit_vertex_gl: %s\n", what); std::exit(1); }
}

int main() {
    XDisplay* display = XOpenDisplay(nullptr);
    require(display, "XOpenDisplay failed");
    int attrs[] = {GLX_RGBA, GLX_RED_SIZE, 8, GLX_GREEN_SIZE, 8, GLX_BLUE_SIZE, 8, GLX_DOUBLEBUFFER, None};
    XVisualInfo* visual = glXChooseVisual(display, DefaultScreen(display), attrs);
    require(visual, "glXChooseVisual failed");
    XSetWindowAttributes wa{};
    wa.colormap = XCreateColormap(display, RootWindow(display, visual->screen), visual->visual, AllocNone);
    Window window = XCreateWindow(display, RootWindow(display, visual->screen), 0, 0, 64, 64, 0,
                                  visual->depth, InputOutput, visual->visual, CWColormap, &wa);
    XMapWindow(display, window); XSync(display, False);
    GLXContext context = glXCreateContext(display, visual, nullptr, GL_TRUE);
    require(context && glXMakeCurrent(display, window, context), "GL context setup failed");
    glViewport(0, 0, 64, 64); glDisable(GL_DITHER); glDisable(GL_DEPTH_TEST);
    RendererBackend* backend = ModernBackendInstance();
    backend->SetLightingEnabled(true); backend->SetFogEnabled(false);
    backend->SetTexturePalette(false, 0, 0); backend->SetTextureModulation(true);
    backend->SetOpacity(1); backend->SetAlphaCutout(false);
    PixelMap texture(PixelMap::MEMORY_VIDEO, 1, 1);
    const unsigned short white = 0xffff;
    texture.Load(&white, 1, 1);
    RBStaticTriangle tri{};
    tri.v[0] = {-.9f, -.8f, 0, .2f, .2f, .2f, 0, 0};
    tri.v[1] = {-.1f, -.8f, 0, .9f, .9f, .9f, 0, 0};
    tri.v[2] = {-.5f,  .8f, 0, .2f, .2f, .2f, 0, 0};
    tri.nz = 1; tri.opacity = 1;
    auto sample = [](int x) { unsigned char p[4]{}; glReadPixels(x,24,1,1,GL_RGBA,GL_UNSIGNED_BYTE,p); return int(p[0]); };
    glClearColor(0,0,0,1); glClear(GL_COLOR_BUFFER_BIT);
    backend->DrawTriangle(tri.v[0], tri.v[1], tri.v[2], 0, 0, 1, &texture, true, true);
    backend->EndFrame();
    int left = sample(11), right = sample(20);
    require(right > left + 25, "prelit colors did not interpolate over the texture");
    RBStaticMeshHandle mesh = backend->CreateStaticMesh(&tri, 1);
    require(mesh, "static mesh creation failed");
    unsigned index = 0;
    glClear(GL_COLOR_BUFFER_BIT);
    backend->DrawStaticTriangles(mesh, &index, 1, &texture, true);
    backend->EndFrame();
    require(std::abs(sample(11)-left) <= 2 && std::abs(sample(20)-right) <= 2,
            "static and streamed prelit shading differ");
    backend->DestroyStaticMesh(mesh);
    glXMakeCurrent(display, None, nullptr); glXDestroyContext(display, context);
    XDestroyWindow(display, window); XFree(visual); XCloseDisplay(display);
    return 0;
}
