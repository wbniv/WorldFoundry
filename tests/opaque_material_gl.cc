// Material shader regression: opacity/cutout transitions, depth, the
// no-palette opaque program selector, custom reload and actual context
// recreation. Run on a private Xvfb display.
#include <gfx/renderer_backend.hp>
#include <game/runtime_profile.hp>
#define GL_GLEXT_PROTOTYPES 1
#include <gfx/static_mesh.hp>
#include <gfx/pixelmap.hp>
#include <GL/gl.h>
#define Display XDisplay
#include <GL/glx.h>
#include <X11/Xlib.h>
#undef Display
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

extern RendererBackend* ModernBackendInstance();
extern void ModernBackendSimulateSurfaceLoss();

static void Require(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "opaque_material_gl: %s\n", what); std::exit(1); }
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

int main(int argc, char** argv)
{
    StaticMeshSetSharedIndex(true);
    XDisplay* dpy = XOpenDisplay(nullptr);
    Require(dpy, "XOpenDisplay failed");
    int attributes[] = {GLX_RGBA, GLX_RED_SIZE, 8, GLX_GREEN_SIZE, 8,
                        GLX_BLUE_SIZE, 8, GLX_DEPTH_SIZE, 24, GLX_DOUBLEBUFFER, None};
    XVisualInfo* visual = glXChooseVisual(dpy, DefaultScreen(dpy), attributes);
    Require(visual, "glXChooseVisual failed");
    XSetWindowAttributes attr = {};
    attr.colormap = XCreateColormap(dpy, RootWindow(dpy, visual->screen), visual->visual, AllocNone);
    Window win = XCreateWindow(dpy, RootWindow(dpy, visual->screen), 0, 0, 64, 64, 0,
                              visual->depth, InputOutput, visual->visual, CWColormap, &attr);
    XMapWindow(dpy, win); XSync(dpy, False);
    GLXContext context = glXCreateContext(dpy, visual, nullptr, GL_TRUE);
    Require(context && glXMakeCurrent(dpy, win, context), "GL context setup failed");
    // Count from the first draw: the opacity/cutout/modulation transitions
    // below must not link the no-palette program either.
    wf_profile::enableFresh();
    glViewport(0, 0, 64, 64);
    glDisable(GL_DEPTH_TEST); glDisable(GL_DITHER);
    RendererBackend* backend = ModernBackendInstance();
    backend->SetLightingEnabled(false); backend->SetFogEnabled(false);

    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LESS);
    PixelMap transparent(PixelMap::MEMORY_VIDEO, 1, 1);
    const unsigned short texel = 0;
    transparent.Load(&texel, 1, 1);
    auto clear = [&]() { glDepthMask(GL_TRUE); glClearColor(0,0,1,1); glClearDepth(1); glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT); };
    auto draw = [&](float opacity, bool cutout, const PixelMap* texture, float r, float g, float b) {
        backend->SetOpacity(opacity); backend->SetAlphaCutout(cutout);
        backend->SetTextureModulation(true);
        const RBStaticTriangle t=Triangle(-.9f,r,g,b);
        backend->DrawTriangle(t.v[0],t.v[1],t.v[2],0,0,1,texture,true,false);
    };
    clear(); draw(1,false,&transparent,1,1,1); backend->EndFrame();
    Pixel(16,24,0,0,0); // transparent texture texel remains opaque without cutout
    clear(); draw(1,true,&transparent,1,1,1); backend->EndFrame();
    Pixel(16,24,0,0,255); // cutout leaves background and depth untouched
    draw(1,false,nullptr,0,1,0); backend->EndFrame(); Pixel(16,24,0,255,0);
    clear(); draw(.5f,false,nullptr,1,0,0); backend->EndFrame();
    unsigned char blend[4]; glReadPixels(16,24,1,1,GL_RGBA,GL_UNSIGNED_BYTE,blend);
    Require(blend[0]>=127 && blend[0]<=128 && blend[2]>=127 && blend[2]<=128, "blending changed");
    draw(1,false,nullptr,0,1,0); backend->EndFrame(); Pixel(16,24,0,255,0); // blended draw did not write depth
    clear(); draw(1,false,nullptr,1,0,0); backend->EndFrame(); Pixel(16,24,255,0,0);

    // No-palette selector. An eligible batch (opaque, textured, unmodulated)
    // whose queued geometry is wholly ordinary uses the no-palette program;
    // palette-only and mixed batches stay one draw on the palette-capable
    // program. The no-palette program is linked only for an ordinary batch.
    // Nothing above drew an eligible batch, so it does not exist yet.
    auto counter = [](int k) { return wf_profile::state().counters[k]; };
    Require(counter(wf_profile::NoPalettePrograms) == 0 && counter(wf_profile::NoPaletteDraws) == 0,
            "an ineligible batch linked or used the no-palette program");
    auto frame = [&]() {
        std::vector<unsigned char> p(64*64*4);
        glReadPixels(0,0,64,64,GL_RGBA,GL_UNSIGNED_BYTE,p.data());
        return p;
    };
    auto sameHalf = [](const std::vector<unsigned char>& a, const std::vector<unsigned char>& b, bool left) {
        for (int y = 0; y < 64; ++y)
            for (int x = left ? 0 : 32; x < (left ? 32 : 64); ++x)
                if (std::memcmp(&a[(y*64+x)*4], &b[(y*64+x)*4], 4)) return false;
        return true;
    };
    PixelMap colored(PixelMap::MEMORY_VIDEO, 1, 1);
    const unsigned short redTexel = 0xf800;
    colored.Load(&redTexel, 1, 1);
    PixelMap other(PixelMap::MEMORY_VIDEO, 1, 1);
    const unsigned short otherTexel = 0x07e0;
    other.Load(&otherTexel, 1, 1);
    // Left: ordinary. Right: palette-enabled, same texture.
    RBStaticTriangle pair[2] = {Triangle(-.9f,1,1,1), Triangle(.1f,1,1,1)};
    pair[1].paletteEnabled = 1; pair[1].paletteDark = 0x0000ff; pair[1].paletteLight = 0xffff00;
    // Byte-exact colors bake the 28-byte compact layout, whose palette is a
    // per-draw constant. .995 is not byte-exact, so `legacyPair` bakes the
    // 76-byte layout with per-vertex palette; it still reads as white
    // (is_white), so both meshes render the same pixels as `pair` streamed.
    RBStaticTriangle legacyPair[2] = {pair[0], pair[1]};
    for (RBStaticTriangle& t : legacyPair)
        for (RBVertex& v : t.v) v.r = v.g = v.b = .995f;
    auto staticBytes = [&]() { size_t gpu, cpu; backend->StaticMeshBytes(gpu, cpu); return gpu; };
    RBStaticMeshHandle compactMesh = backend->CreateStaticMesh(pair, 2);
    Require(compactMesh && staticBytes() == 2*3*28, "byte-exact static mesh did not bake compact");
    RBStaticMeshHandle legacyMesh = backend->CreateStaticMesh(legacyPair, 2);
    Require(legacyMesh && staticBytes() == 2*3*28 + 2*3*76, "inexact static mesh did not bake legacy");
    RBStaticMeshHandle mesh = compactMesh;
    auto eligible = [&]() {
        clear();
        wf_profile::enableFresh();
        backend->SetOpacity(1); backend->SetAlphaCutout(false); backend->SetTextureModulation(false);
    };
    auto submit = [&](bool indexed, unsigned t, const PixelMap* texture) {
        backend->SetTexturePalette(t == 1, pair[t].paletteDark, pair[t].paletteLight);
        if (indexed) backend->DrawStaticTriangles(mesh, &t, 1, texture, false);
        else backend->DrawTriangle(pair[t].v[0],pair[t].v[1],pair[t].v[2],0,0,1,texture,true,false);
    };
    // which: bit 0 = left ordinary triangle, bit 1 = right palette triangle.
    auto scene = [&](bool indexed, int which, const PixelMap* rightTexture) {
        eligible();
        for (unsigned t = 0; t < 2; ++t)
            if (which & (1 << t)) submit(indexed, t, t == 1 ? rightTexture : &colored);
        backend->EndFrame();
        return frame();
    };
    // source: 0 = streaming, 1 = compact static mesh, 2 = legacy static mesh.
    std::vector<unsigned char> mixedFrames[3], ordinaryStreaming;
    for (int source = 0; source < 3; ++source) {
        const bool indexed = source != 0;
        // Only a compact batch splits at a palette change: its palette is one
        // constant per draw, so each half is chosen alone (ordinary half on
        // the no-palette program, palette half on the palette-capable one).
        const bool compact = source == 1;
        mesh = source == 2 ? legacyMesh : compactMesh;
        const auto paletteOnly = scene(indexed, 2, &colored);
        Require(counter(wf_profile::Draws) == 1 && counter(wf_profile::NoPaletteDraws) == 0
                && counter(wf_profile::MixedPaletteDraws) == 0, "palette-only batch left the palette program");
        Require(counter(wf_profile::NoPalettePrograms) == 0, "palette-only batch created the no-palette program");
        const auto mixed = scene(indexed, 3, &colored);
        if (compact) {
            Require(counter(wf_profile::Draws) == 2, "compact palette transition did not split the batch");
            Require(counter(wf_profile::NoPaletteDraws) == 1 && counter(wf_profile::MixedPaletteDraws) == 0,
                    "compact halves did not each choose their own program");
        } else {
            Require(counter(wf_profile::Draws) == 1, indexed ? "static palette transition split a batch"
                                                             : "streaming palette transition split a batch");
            Require(counter(wf_profile::MixedPaletteDraws) == 1 && counter(wf_profile::NoPaletteDraws) == 0,
                    "mixed batch left the palette-capable program");
        }
        Require(counter(wf_profile::NoPalettePrograms) == 0, "mixed batch created the no-palette program");
        const auto ordinary = scene(indexed, 1, &colored);
        Require(counter(wf_profile::Draws) == 1 && counter(wf_profile::NoPaletteDraws) == 1,
                "ordinary batch did not use the no-palette program");
        Require(counter(wf_profile::NoPalettePrograms) == (indexed ? 0u : 1u),
                "no-palette program must be linked once, by the first ordinary batch");
        // The no-palette program renders ordinary faces exactly as the
        // palette-capable program does inside the mixed batch.
        Require(sameHalf(mixed, ordinary, true), "no-palette program changed ordinary pixels");
        Require(sameHalf(mixed, paletteOnly, false), "mixed batch changed palette pixels");
        Require(std::memcmp(&mixed[(24*64+16)*4], &mixed[(24*64+48)*4], 3) != 0,
                "palette did not visibly change the palette-enabled face");
        mixedFrames[source] = mixed;
        if (!indexed) ordinaryStreaming = ordinary;
    }
    // Every program that draws a static mesh decodes both layouts exactly.
    Require(mixedFrames[0] == mixedFrames[1], "streaming and compact static mixed batches differ");
    Require(mixedFrames[0] == mixedFrames[2], "streaming and legacy static mixed batches differ");
    mesh = compactMesh;

    // A texture change splits batches as before; each half is chosen alone.
    scene(false, 3, &other);
    Require(counter(wf_profile::Draws) == 2 && counter(wf_profile::NoPaletteDraws) == 1
            && counter(wf_profile::MixedPaletteDraws) == 0, "texture change: wrong program per batch");

    // A culled palette face queues nothing, so the batch stays ordinary.
    eligible();
    submit(false, 0, &colored);
    backend->SetTexturePalette(true, pair[1].paletteDark, pair[1].paletteLight);
    backend->DrawTriangle(pair[1].v[0],pair[1].v[1],pair[1].v[2],1,0,0,&colored,false,false);
    backend->EndFrame();
    Require(counter(wf_profile::FacesCulled) == 1 && counter(wf_profile::Draws) == 1
            && counter(wf_profile::NoPaletteDraws) == 1, "culled palette face made a batch mixed");
    Require(frame() == ordinaryStreaming, "culled palette face changed pixels");
    // An all-culled static run (no surviving triangles) submits nothing either.
    eligible();
    backend->SetTexturePalette(true, pair[1].paletteDark, pair[1].paletteLight);
    backend->DrawStaticTriangles(mesh, nullptr, 0, &colored, false);
    submit(true, 0, &colored);
    backend->EndFrame();
    Require(counter(wf_profile::Draws) == 1 && counter(wf_profile::NoPaletteDraws) == 1,
            "empty static palette run made a batch mixed");

    // Ineligible effects keep their programs, even for ordinary geometry.
    for (int effect = 0; effect < 3; ++effect) {
        eligible();
        if (effect == 0) backend->SetTextureModulation(true);
        if (effect == 1) backend->SetAlphaCutout(true);
        if (effect == 2) backend->SetOpacity(.5f);
        submit(false, 0, &colored);
        backend->EndFrame();
        Require(counter(wf_profile::Draws) == 1 && counter(wf_profile::NoPaletteDraws) == 0,
                "modulated, cutout or blended batch used the no-palette program");
    }
    backend->SetOpacity(1); backend->SetAlphaCutout(false); backend->SetTextureModulation(true);
    backend->DestroyStaticMesh(compactMesh);
    backend->DestroyStaticMesh(legacyMesh);
    wf_profile::state().enabled = false;

    // Reload must flush old geometry and affect opaque and cutout draws alike.
    const char* vs="layout(location=0)in vec3 p;void main(){gl_Position=vec4(p,1);}";
    const char* fs="out vec4 c;void main(){c=vec4(1,1,0,1);}";
    std::string log;
    clear(); draw(1,false,nullptr,0,1,0);
    Require(backend->ReloadProgram(vs,fs,log), "valid reload failed");
    Pixel(16,24,0,255,0);
    for(int mode=0;mode<3;mode++) {
        clear(); draw(mode==2?.5f:1,mode==1,&transparent,1,1,1); backend->EndFrame();
        Pixel(16,24,255,255,0);
    }
    Require(!backend->ReloadProgram(vs,"invalid fragment shader",log), "invalid reload accepted");
    clear(); draw(1,false,nullptr,0,1,0); backend->EndFrame(); Pixel(16,24,255,255,0);
    // A custom reload also replaces the no-palette program for ordinary batches.
    eligible();
    submit(false, 0, &colored);
    backend->EndFrame();
    Require(counter(wf_profile::NoPaletteDraws) == 0 && counter(wf_profile::NoPalettePrograms) == 0,
            "no-palette program used after a custom reload");
    Pixel(16,24,255,255,0);
    backend->PrepareNoPaletteProgram();
    Require(counter(wf_profile::NoPalettePrograms) == 0, "prewarm linked a program after a custom reload");
    wf_profile::state().enabled = false;
    Require(glGetError()==GL_NO_ERROR,"GL error before context reset");

    // Both built-in programs must work after actual context recreation.
    ModernBackendSimulateSurfaceLoss();
    glXMakeCurrent(dpy,None,nullptr); glXDestroyContext(dpy,context);
    context=glXCreateContext(dpy,visual,nullptr,GL_TRUE);
    Require(context && glXMakeCurrent(dpy,win,context),"replacement context failed");
    glViewport(0,0,64,64); glDisable(GL_DITHER); glEnable(GL_DEPTH_TEST);
    clear(); draw(1,false,nullptr,0,1,0); backend->EndFrame(); Pixel(16,24,0,255,0);
    clear(); draw(1,true,nullptr,1,0,0); backend->EndFrame(); Pixel(16,24,255,0,0);
    // The new context relinks the no-palette program on its first ordinary
    // batch, once, with the same pixels as before the loss.
    PixelMap recreated(PixelMap::MEMORY_VIDEO, 1, 1);
    recreated.Load(&redTexel, 1, 1);
    for (int pass = 0; pass < 2; ++pass) {
        eligible();
        submit(false, 0, &recreated);
        backend->EndFrame();
        Require(counter(wf_profile::NoPaletteDraws) == 1
                && counter(wf_profile::NoPalettePrograms) == (pass == 0 ? 1u : 0u),
                "no-palette program not relinked exactly once after context recreation");
        Require(frame() == ordinaryStreaming, "no-palette pixels changed after context recreation");
    }

    // Level-load prewarm in a fresh context: links the program once without
    // drawing; palette-only batches still use the palette-capable program,
    // and the first ordinary batch reuses the prewarmed program.
    ModernBackendSimulateSurfaceLoss();
    glXMakeCurrent(dpy,None,nullptr); glXDestroyContext(dpy,context);
    context=glXCreateContext(dpy,visual,nullptr,GL_TRUE);
    Require(context && glXMakeCurrent(dpy,win,context),"second replacement context failed");
    glViewport(0,0,64,64); glDisable(GL_DITHER); glEnable(GL_DEPTH_TEST);
    PixelMap prewarmed(PixelMap::MEMORY_VIDEO, 1, 1);
    prewarmed.Load(&redTexel, 1, 1);
    wf_profile::enableFresh();
    backend->PrepareNoPaletteProgram();
    backend->PrepareNoPaletteProgram();
    Require(counter(wf_profile::NoPalettePrograms) == 1 && counter(wf_profile::Draws) == 0,
            "prewarm did not link the program exactly once without drawing");
    eligible();
    submit(false, 1, &prewarmed);
    backend->EndFrame();
    Require(counter(wf_profile::Draws) == 1 && counter(wf_profile::NoPaletteDraws) == 0,
            "prewarm moved a palette-only batch off the palette-capable program");
    eligible();
    submit(false, 0, &prewarmed);
    backend->EndFrame();
    Require(counter(wf_profile::NoPaletteDraws) == 1 && counter(wf_profile::NoPalettePrograms) == 0,
            "first ordinary batch relinked a prewarmed program");
    Require(frame() == ordinaryStreaming, "prewarmed program changed ordinary pixels");
    wf_profile::state().enabled = false;
    Require(glGetError()==GL_NO_ERROR,"GL error after context reset");
    glXMakeCurrent(dpy,None,nullptr); glXDestroyContext(dpy,context);
    XDestroyWindow(dpy,win); XFree(visual); XCloseDisplay(dpy);
    std::puts("PASS opaque/cutout/blended transitions, depth, no-palette selector (palette-only, mixed, ordinary,"
              " streaming/static, culled, texture change, ineligible effects, prewarm), reload success/failure"
              " and context recreation");
}
