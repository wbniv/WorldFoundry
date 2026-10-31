// PixelMap textures across a GL context loss. Run on private Xvfb.
//
// A real loss (Android EGL_CONTEXT_LOST) destroys every texture; the engine
// learns of it through ModernRendererBackend::OnSurfaceLost, which bumps
// TextureGeneration(). The level's PixelMaps must re-create their textures
// from their resident pixel buffers on the next bind or update, keep the
// newest UpdateRGBA8 pixels, leave the caller's GL state alone, and never
// pass a pre-loss name to glDeleteTextures (after a loss that name can belong
// to an unrelated new texture). Before the fix the bind used the dead name and
// sampled nothing (finding-your-way docs/plans/2026-10-31-context-loss-tests.md).
// Xlib's `Display` typedef clashes with the engine's Display class (pulled in
// by pixelmap.hp), so the X11 headers come first under another name.
#define Display X11Display
#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>
#undef Display
#include <gfx/renderer_backend.hp>
#include <gfx/pixelmap.hp>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

extern void ModernBackendSimulateSurfaceLoss();

static void Require(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "pixelmap_context_loss_gl: %s\n", what); std::exit(1); }
}

static const int W = 4, H = 4;

static GLuint Bound()
{
    GLint name = 0;
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &name);
    return GLuint(name);
}

// The texture's level-0 RGBA bytes, read through a scratch binding.
static std::vector<unsigned char> Read(GLuint name)
{
    std::vector<unsigned char> out(W * H * 4, 0xEE);
    const GLuint before = Bound();
    glBindTexture(GL_TEXTURE_2D, name);
    glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE, out.data());
    glBindTexture(GL_TEXTURE_2D, before);
    return out;
}

// What PixelMap::Load makes of a 1555 source pixel (pixelmap.cc).
static void Expect(std::vector<unsigned char>& rgba, int i, uint16_t p)
{
    rgba[i * 4 + 0] = ((p >> 10) & 0x1f) << 3;
    rgba[i * 4 + 1] = ((p >> 5) & 0x1f) << 3;
    rgba[i * 4 + 2] = (p & 0x1f) << 3;
    rgba[i * 4 + 3] = p == 0x8000 ? 255 : p == 0 ? 0 : (p & 0x8000) ? 128 : 255;
}

static void KillTexture(GLuint name)
{
    // The real thing: the driver's objects die with the context. The engine's
    // own hook only forgets names, so the texture is deleted here as well.
    ModernBackendSimulateSurfaceLoss();
    glDeleteTextures(1, &name);
    Require(!glIsTexture(name), "test setup: the texture survived its deletion");
}

int main()
{
    X11Display* dpy = XOpenDisplay(nullptr);
    Require(dpy, "XOpenDisplay failed");
    int attributes[] = {GLX_RGBA, GLX_RED_SIZE, 8, GLX_GREEN_SIZE, 8, GLX_BLUE_SIZE, 8, GLX_DOUBLEBUFFER, None};
    XVisualInfo* visual = glXChooseVisual(dpy, DefaultScreen(dpy), attributes);
    Require(visual, "glXChooseVisual failed");
    XSetWindowAttributes attr = {};
    attr.colormap = XCreateColormap(dpy, RootWindow(dpy, visual->screen), visual->visual, AllocNone);
    Window win = XCreateWindow(dpy, RootWindow(dpy, visual->screen), 0, 0, 16, 16, 0,
                               visual->depth, InputOutput, visual->visual, CWColormap, &attr);
    XMapWindow(dpy, win); XSync(dpy, False);
    GLXContext context = glXCreateContext(dpy, visual, nullptr, GL_TRUE);
    Require(context && glXMakeCurrent(dpy, win, context), "GL context setup failed");

    RendererBackend& backend = RendererBackendGet();
    uint16_t source[W * H];
    std::vector<unsigned char> expected(W * H * 4);
    for (int i = 0; i < W * H; ++i)
    {
        source[i] = uint16_t((i * 0x0843) ^ (i & 1 ? 0x8000 : 0));
        Expect(expected, i, source[i]);
    }

    PixelMap* map = new PixelMap(PixelMap::MEMORY_VIDEO, W, H);
    map->Load(source, W, H);
    const GLuint first = GLuint(uintptr_t(map->GetTextureHandle()));
    Require(first && glIsTexture(first), "no texture after Load");
    Require(Read(first) == expected, "wrong texels after Load");
    const unsigned generation = backend.TextureGeneration();
    Require(generation != 0, "the GL backend reports no texture generation");

    // 1. No loss: binding keeps the same name (the normal path is unchanged).
    map->SetGLTexture();
    Require(Bound() == first && GLuint(uintptr_t(map->GetTextureHandle())) == first,
            "the handle changed without a context loss");

    // 2. Loss, then an unrelated texture that may reuse the dead name.
    KillTexture(first);
    Require(backend.TextureGeneration() != generation, "OnSurfaceLost did not bump the generation");
    GLuint unrelated = 0;
    glGenTextures(1, &unrelated);
    glBindTexture(GL_TEXTURE_2D, unrelated);
    unsigned char marker[4] = {1, 2, 3, 4};
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 1, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, marker);
    glBindTexture(GL_TEXTURE_2D, 0);

    // 3. The next bind re-creates the texture from the resident buffer and
    //    leaves blend and depth as the draw had set them.
    glDisable(GL_BLEND); glDisable(GL_DEPTH_TEST);
    map->SetGLTexture();
    const GLuint second = Bound();
    Require(second && second != unrelated && glIsTexture(second), "no live texture bound after the loss");
    Require(GLuint(uintptr_t(map->GetTextureHandle())) == second, "the handle is not the bound texture");
    Require(Read(second) == expected, "wrong texels after the loss");
    Require(!glIsEnabled(GL_BLEND) && !glIsEnabled(GL_DEPTH_TEST), "the restore changed blend or depth state");
    Require(glIsTexture(unrelated), "the restore deleted an unrelated texture");

    // 4. An update straight after a loss (the brazier fire writes every frame)
    //    lands in a re-created texture with every earlier pixel kept.
    KillTexture(second);
    const unsigned char fire[4] = {250, 120, 10, 255};
    Require(map->UpdateRGBA8(1, 2, 1, 1, fire), "UpdateRGBA8 failed after the loss");
    const GLuint third = GLuint(uintptr_t(map->GetTextureHandle()));
    // (GL may hand the freed name out again, so only liveness and texels count.)
    Require(third && glIsTexture(third), "UpdateRGBA8 did not re-create the texture");
    for (int c = 0; c < 4; ++c) expected[(2 * W + 1) * 4 + c] = fire[c];
    Require(Read(third) == expected, "wrong texels after an update across the loss");

    // 5. A reload after a loss must not delete the dead name either.
    KillTexture(third);
    GLuint reused = 0;
    glGenTextures(1, &reused);              // glIsTexture is false until a name is first bound
    glBindTexture(GL_TEXTURE_2D, reused);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 1, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, marker);
    glBindTexture(GL_TEXTURE_2D, 0);
    map->Load(source, W, H);
    Require(glIsTexture(reused), "Load deleted a texture it did not own");

    // 6. Destruction after a loss must not delete whatever reuses the name.
    const GLuint fourth = GLuint(uintptr_t(map->GetTextureHandle()));
    KillTexture(fourth);
    GLuint later = 0;
    glGenTextures(1, &later);
    glBindTexture(GL_TEXTURE_2D, later);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 1, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, marker);
    delete map;
    Require(glIsTexture(later), "~PixelMap deleted a texture it did not own");
    Require(glGetError() == GL_NO_ERROR, "GL error");
    std::puts("pixelmap_context_loss_gl: ok");
    return 0;
}
