// Material shader regression: opacity/cutout transitions, depth, custom reload
// and actual context recreation. Run on a private Xvfb display.
#include <gfx/renderer_backend.hp>
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
    Require(glGetError()==GL_NO_ERROR,"GL error before context reset");

    // Both built-in programs must work after actual context recreation.
    ModernBackendSimulateSurfaceLoss();
    glXMakeCurrent(dpy,None,nullptr); glXDestroyContext(dpy,context);
    context=glXCreateContext(dpy,visual,nullptr,GL_TRUE);
    Require(context && glXMakeCurrent(dpy,win,context),"replacement context failed");
    glViewport(0,0,64,64); glDisable(GL_DITHER); glEnable(GL_DEPTH_TEST);
    clear(); draw(1,false,nullptr,0,1,0); backend->EndFrame(); Pixel(16,24,0,255,0);
    clear(); draw(1,true,nullptr,1,0,0); backend->EndFrame(); Pixel(16,24,255,0,0);
    Require(glGetError()==GL_NO_ERROR,"GL error after context reset");
    glXMakeCurrent(dpy,None,nullptr); glXDestroyContext(dpy,context);
    XDestroyWindow(dpy,win); XFree(visual); XCloseDisplay(dpy);
    std::puts("PASS opaque/cutout/blended transitions, depth, reload success/failure and context recreation");
}
