//=============================================================================
// gfx/gl/android_window.cc: Android EGL + ANativeWindow glue
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// Peer of gl/mesa.cc for the Android target. Exports the same surface that
// display.cc expects (OpenMainWindow, InitWindow, XEventLoop,
// SetX11AutoRepeat) plus AndroidSwapBuffers() and an internal
// WFAndroidCreateEglContext(window) used by native_app_entry.cc.
//============================================================================

// Body is compiled only when included by gl/display.cc on the Android build.
// If a build system (e.g. build_game.sh) sweeps the directory and compiles
// this TU directly on desktop, skip it: everything it defines is needed only
// inside display.cc's translation unit.
#if defined(__ANDROID__)

#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <android/log.h>
#include <android/native_window.h>

#include <hal/android/wf_android_export.hp>
#include <hal/phonepad/phonepad_overlay.h>
#include <hal/android/touch_controls.h>
#include "../../../../engine/vendor/stb_easy_font.h"

extern "C" void WFAndroidTouchLayout(int,int,androidtouch::Layout*,uint32_t*,float*,float*);

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace
{

EGLDisplay gEglDisplay = EGL_NO_DISPLAY;
EGLSurface gEglSurface = EGL_NO_SURFACE;
EGLContext gEglContext = EGL_NO_CONTEXT;
EGLConfig  gEglConfig  = nullptr;
ANativeWindow* gNativeWindow = nullptr;

// Touch-control HUD overlay — self-contained GL objects live alongside the
// game's modern backend in the shared EGL context. On EGL_CONTEXT_LOST
// (rare, below) these are reset to 0 so HudInit lazy-recompiles.
GLuint gHudProg    = 0;
GLuint gHudVao     = 0;
GLuint gHudVbo     = 0;
bool   gHudInited  = false;
bool   gHudEnabled = true;

// Phone-controller overlay (hal/phonepad/phonepad_overlay.h): its own VAO/VBO,
// re-uploaded only when the overlay changes, drawn with the HUD's program.
GLuint gPhoneVao   = 0;
GLuint gPhoneVbo   = 0;
GLsizei gPhoneVerts = 0;

// The level menu (game/level_menu.h): the same, for WFAndroidDrawLevelMenu.
GLuint gMenuVao = 0, gMenuVbo = 0;
GLsizei gMenuVerts = 0;
std::vector<PhonepadRect> gMenuLast;
int gMenuW = 0, gMenuH = 0;

#define WF_LOG_TAG "wf_game"
#define WFLOG(fmt, ...) __android_log_print(ANDROID_LOG_INFO, WF_LOG_TAG, fmt, ##__VA_ARGS__)
#define WFLOGE(fmt, ...) __android_log_print(ANDROID_LOG_ERROR, WF_LOG_TAG, fmt, ##__VA_ARGS__)

}  // namespace

// Feeds _halWindow{Width,Height} in hal/android/platform.cc once the surface
// dimensions are known.
extern "C" void WFAndroidSetSurfaceSize(int w, int h);

// Driven by native_app_entry.cc on APP_CMD_INIT_WINDOW / TERM_WINDOW.
// Returns true when GL context is live and current.
extern "C" bool WFAndroidEglInit(ANativeWindow* window);
extern "C" void WFAndroidEglTerm();

extern "C" WF_ANDROID_EXPORT bool
WFAndroidEglInit(ANativeWindow* window)
{
    if (!window)
    {
        WFLOGE("WFAndroidEglInit: null window");
        return false;
    }
    gNativeWindow = window;

    const EGLint configAttribs[] = {
        EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT,
        EGL_RED_SIZE,   8,
        EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE,  8,
        EGL_DEPTH_SIZE, 16,
        EGL_NONE
    };

    // First-time setup: display + config + context. Preserved across
    // pause/resume so textures and VBOs in the context survive.
    if (gEglDisplay == EGL_NO_DISPLAY)
    {
        gEglDisplay = eglGetDisplay(EGL_DEFAULT_DISPLAY);
        if (gEglDisplay == EGL_NO_DISPLAY)
        {
            WFLOGE("eglGetDisplay failed");
            return false;
        }
        if (!eglInitialize(gEglDisplay, nullptr, nullptr))
        {
            WFLOGE("eglInitialize failed: 0x%x", eglGetError());
            return false;
        }

        EGLint numConfigs = 0;
        if (!eglChooseConfig(gEglDisplay, configAttribs, &gEglConfig, 1, &numConfigs)
            || numConfigs < 1)
        {
            WFLOGE("eglChooseConfig failed: 0x%x", eglGetError());
            return false;
        }
    }

    if (gEglContext == EGL_NO_CONTEXT)
    {
        const EGLint contextAttribs[] = {
            EGL_CONTEXT_CLIENT_VERSION, 3,
            EGL_NONE
        };
        gEglContext = eglCreateContext(gEglDisplay, gEglConfig,
                                       EGL_NO_CONTEXT, contextAttribs);
        if (gEglContext == EGL_NO_CONTEXT)
        {
            WFLOGE("eglCreateContext failed: 0x%x", eglGetError());
            return false;
        }
    }

    // Per-surface setup: happens every pause/resume cycle.
    EGLint format = 0;
    eglGetConfigAttrib(gEglDisplay, gEglConfig, EGL_NATIVE_VISUAL_ID, &format);
    ANativeWindow_setBuffersGeometry(window, 0, 0, format);

    gEglSurface = eglCreateWindowSurface(gEglDisplay, gEglConfig, window, nullptr);
    if (gEglSurface == EGL_NO_SURFACE)
    {
        WFLOGE("eglCreateWindowSurface failed: 0x%x", eglGetError());
        return false;
    }

    if (!eglMakeCurrent(gEglDisplay, gEglSurface, gEglSurface, gEglContext))
    {
        EGLint err = eglGetError();
        WFLOGE("eglMakeCurrent failed: 0x%x", err);
        // EGL_CONTEXT_LOST (0x300E): the driver killed our GL objects on
        // the way back in — rare, but must be recovered from. Drop the
        // context, tell the backend to rebuild, and try once more with a
        // fresh context.
        if (err == EGL_CONTEXT_LOST)
        {
            WFLOG("EGL_CONTEXT_LOST — rebuilding");
            extern void WFAndroidNotifySurfaceLost();
            WFAndroidNotifySurfaceLost();
            gHudInited = false;
            gHudProg   = 0;
            gHudVao    = 0;
            gHudVbo    = 0;
            gPhoneVao   = 0;
            gPhoneVbo   = 0;
            gPhoneVerts = 0;
            gMenuVao    = 0;
            gMenuVbo    = 0;
            gMenuLast.clear();
            eglDestroyContext(gEglDisplay, gEglContext);
            gEglContext = EGL_NO_CONTEXT;
            // Fall through to normal retry on next INIT_WINDOW.
        }
        return false;
    }

    EGLint w = 0, h = 0;
    eglQuerySurface(gEglDisplay, gEglSurface, EGL_WIDTH,  &w);
    eglQuerySurface(gEglDisplay, gEglSurface, EGL_HEIGHT, &h);
    WFAndroidSetSurfaceSize(w, h);
    WFLOG("EGL surface ready: %dx%d (context %s)",
          w, h, gEglContext == EGL_NO_CONTEXT ? "NEW" : "reused");
    return true;
}

// Defined in gfx/glpipeline/backend_modern.cc — safety-net for the rare
// EGL_CONTEXT_LOST path (low-memory driver reset). Clears the modern
// backend's GL-object handles so the next draw recompiles.
extern "C" void WFAndroidNotifySurfaceLost();

extern "C" WF_ANDROID_EXPORT void
WFAndroidEglTerm()
{
    // Pause/background path: destroy only the surface. Context survives,
    // so all its textures, shader programs and VBOs survive. When the
    // user switches back, WFAndroidEglInit creates a new surface and
    // eglMakeCurrent's the existing context onto it — no rebuild needed.
    if (gEglDisplay != EGL_NO_DISPLAY && gEglSurface != EGL_NO_SURFACE)
    {
        eglMakeCurrent(gEglDisplay, EGL_NO_SURFACE, EGL_NO_SURFACE, gEglContext);
        eglDestroySurface(gEglDisplay, gEglSurface);
    }
    gEglSurface   = EGL_NO_SURFACE;
    gNativeWindow = nullptr;
}

// ---- API surface that gl/display.cc expects ---------------------------------

void OpenMainWindow(char* /*title*/)
{
    // NativeActivity owns the window — it's been created (or will be) via
    // WFAndroidEglInit. Nothing to do here.
}

bool InitWindow(int /*xPos*/, int /*yPos*/, int /*xSize*/, int /*ySize*/)
{
    return gEglDisplay != EGL_NO_DISPLAY;
}

// Polled once per frame by Display::PageFlip. native_app_entry.cc sets the
// pumping hook below; if unset, this is a no-op.
extern "C" void WFAndroidPumpEvents();

void XEventLoop()
{
    WFAndroidPumpEvents();
}

void SetX11AutoRepeat(int /*state*/) {}

// ---- Touch-control HUD overlay ---------------------------------------------
// Self-contained GL state (own shader + VBO) so we don't disturb the game's
// modern backend. Drawn at the end of every frame, just before swap. Shows
// semi-transparent rectangles over the (otherwise invisible) hit-test regions
// wired up in hal/android/native_app_entry.cc — keep in sync with those.

extern int _halWindowWidth;
extern int _halWindowHeight;

namespace
{

const char* kHudVS =
    "#version 300 es\n"
    "layout(location=0) in vec2 a_pos;\n"
    "layout(location=1) in vec4 a_color;\n"
    "out vec4 v_color;\n"
    "void main() {\n"
    "    gl_Position = vec4(a_pos, 0.0, 1.0);\n"
    "    v_color = a_color;\n"
    "}\n";

const char* kHudFS =
    "#version 300 es\n"
    "precision highp float;\n"
    "in vec4 v_color;\n"
    "out vec4 frag;\n"
    "void main() { frag = v_color; }\n";

struct HudVert { float x, y, r, g, b, a; };

GLuint CompileHudShader(GLenum type, const char* src)
{
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, nullptr);
    glCompileShader(s);
    GLint ok = 0;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok)
    {
        char log[1024] = { 0 };
        glGetShaderInfoLog(s, sizeof(log) - 1, nullptr, log);
        WFLOGE("HUD shader compile failed:\n%s", log);
        glDeleteShader(s);
        return 0;
    }
    return s;
}

void HudInit()
{
    if (gHudInited) return;

    GLuint vs = CompileHudShader(GL_VERTEX_SHADER,   kHudVS);
    GLuint fs = CompileHudShader(GL_FRAGMENT_SHADER, kHudFS);
    gHudProg = glCreateProgram();
    glAttachShader(gHudProg, vs);
    glAttachShader(gHudProg, fs);
    glLinkProgram(gHudProg);
    glDeleteShader(vs);
    glDeleteShader(fs);

    glGenVertexArrays(1, &gHudVao);
    glGenBuffers(1, &gHudVbo);
    glBindVertexArray(gHudVao);
    glBindBuffer(GL_ARRAY_BUFFER, gHudVbo);

    const GLsizei stride = sizeof(HudVert);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, (void*)offsetof(HudVert, x));
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, stride, (void*)offsetof(HudVert, r));

    glBindVertexArray(0);
    glBindBuffer(GL_ARRAY_BUFFER, 0);

    gHudInited = true;
}

// Pixel coords (origin top-left, Y down) → NDC (origin center, Y up).
void PushHudRect(std::vector<HudVert>& v,
                 float x0, float y0, float x1, float y1,
                 float w, float h,
                 float r, float g, float b, float a)
{
    const float nx0 = (x0 / w) * 2.0f - 1.0f;
    const float nx1 = (x1 / w) * 2.0f - 1.0f;
    const float ny0 = 1.0f - (y0 / h) * 2.0f;   // top
    const float ny1 = 1.0f - (y1 / h) * 2.0f;   // bottom
    v.push_back({nx0, ny0, r, g, b, a});
    v.push_back({nx1, ny0, r, g, b, a});
    v.push_back({nx1, ny1, r, g, b, a});
    v.push_back({nx0, ny0, r, g, b, a});
    v.push_back({nx1, ny1, r, g, b, a});
    v.push_back({nx0, ny1, r, g, b, a});
}

void PushHudDisc(std::vector<HudVert>& v,float cx,float cy,float radius,
                 float w,float h,float r,float g,float b,float a)
{
    const float nx=cx/w*2-1,ny=1-cy/h*2;
    for(int i=0;i<48;++i) {
        const float angle=i*6.2831853f/48,next=(i+1)*6.2831853f/48;
        v.push_back({nx,ny,r,g,b,a});
        v.push_back({(cx+std::cos(angle)*radius)/w*2-1,1-(cy+std::sin(angle)*radius)/h*2,r,g,b,a});
        v.push_back({(cx+std::cos(next)*radius)/w*2-1,1-(cy+std::sin(next)*radius)/h*2,r,g,b,a});
    }
}

}  // namespace

// native_app_entry.cc calls this after AConfiguration_getUiModeType — suppress
// the HUD on Google TV / Android TV where input is gamepad-only.
extern "C" WF_ANDROID_EXPORT void
WFAndroidSetHudEnabled(int enabled)
{
    gHudEnabled = (enabled != 0);
}

extern "C" void
WFAndroidDrawHUD()
{
    if (!gHudEnabled) return;
    const int w = _halWindowWidth;
    const int h = _halWindowHeight;
    if (w <= 0 || h <= 0) return;

    HudInit();
    if (gHudProg == 0) return;

    const float fw = float(w);
    const float fh = float(h);

    // Rendering and input use the same density-aware control geometry.
    std::vector<HudVert> verts;
    androidtouch::Layout layout;uint32_t held=0;float stickX=0,stickY=0;
    WFAndroidTouchLayout(w,h,&layout,&held,&stickX,&stickY);
    if(!layout.valid)return;
    const float radius=androidtouch::stickRadius(layout),cx=(layout.pad.x0+layout.pad.x1)/2,cy=(layout.pad.y0+layout.pad.y1)/2;
    PushHudDisc(verts,cx,cy,radius,fw,fh,.42f,.50f,.62f,.65f);
    PushHudDisc(verts,cx,cy,radius-layout.cell*.03f,fw,fh,.05f,.075f,.125f,.55f);
    const bool moving=(held&(androidtouch::Up|androidtouch::Down|androidtouch::Left|androidtouch::Right))!=0;
    const float knobRadius=layout.cell*.6f,travel=radius-knobRadius;
    PushHudDisc(verts,cx+stickX*travel,cy+stickY*travel,knobRadius,fw,fh,
                moving?.42f:.22f,moving?.62f:.32f,moving?.85f:.46f,.85f);
    for(int i=4;i<8;++i) {
        const auto& control=layout.controls[i];
        const auto& r=control.rect;
        const bool action=control.bit<=androidtouch::D;
        const float alpha=(held&control.bit)?0.85f:0.55f;
        PushHudRect(verts,r.x0,r.y0,r.x1,r.y1,fw,fh,
                    action?0.20f:0.38f,action?0.28f:0.38f,action?0.43f:0.38f,alpha);
        float text[256];
        const int count=stb_easy_font_print(0,0,(char*)control.label,nullptr,text,sizeof(text));
        const float scale=(r.x1-r.x0)/16;
        const float x=(r.x0+r.x1-stb_easy_font_width((char*)control.label)*scale)/2;
        const float y=(r.y0+r.y1-8*scale)/2;
        for(int q=0;q<count;++q) {
            const float* v=text+q*16;
            float x0=v[0],x1=v[0],y0=v[1],y1=v[1];
            for(int k=1;k<4;++k){x0=std::min(x0,v[k*4]);x1=std::max(x1,v[k*4]);y0=std::min(y0,v[k*4+1]);y1=std::max(y1,v[k*4+1]);}
            PushHudRect(verts,x+x0*scale,y+y0*scale,x+x1*scale,y+y1*scale,fw,fh,1,1,1,0.95f);
        }
    }

    // Save minimal GL state we'll touch.
    GLboolean prevBlend   = glIsEnabled(GL_BLEND);
    GLboolean prevDepth   = glIsEnabled(GL_DEPTH_TEST);
    GLboolean prevCull    = glIsEnabled(GL_CULL_FACE);

    glDisable(GL_DEPTH_TEST);
    glDisable(GL_CULL_FACE);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);

    glUseProgram(gHudProg);
    glBindVertexArray(gHudVao);
    glBindBuffer(GL_ARRAY_BUFFER, gHudVbo);
    glBufferData(GL_ARRAY_BUFFER,
                 GLsizeiptr(verts.size() * sizeof(HudVert)),
                 verts.data(),
                 GL_STREAM_DRAW);
    glDrawArrays(GL_TRIANGLES, 0, GLsizei(verts.size()));

    glBindVertexArray(0);
    glBindBuffer(GL_ARRAY_BUFFER, 0);
    glUseProgram(0);

    if (!prevBlend) glDisable(GL_BLEND);
    if ( prevDepth) glEnable(GL_DEPTH_TEST);
    if ( prevCull)  glEnable(GL_CULL_FACE);
}

// Defined in hal/android/native_app_entry.cc.
extern "C" int WFAndroidPhoneOverlayRects(int w, int h, const PhonepadRect** rects, int* changed);

// The phone-controller panel and toasts (Phase E of docs/plans/2026-09-30-aquarium-chromecast.md),
// drawn over the game like the touch HUD but also on TV, where the HUD is off.
extern "C" void
WFAndroidDrawPhoneOverlay()
{
    const int w = _halWindowWidth;
    const int h = _halWindowHeight;
    if (w <= 0 || h <= 0) return;
    const PhonepadRect* rects = nullptr;
    int changed = 0;
    const int n = WFAndroidPhoneOverlayRects(w, h, &rects, &changed);
    if (n <= 0) { gPhoneVerts = 0; return; }

    HudInit();
    if (gHudProg == 0) return;
    if (gPhoneVao == 0)
    {
        glGenVertexArrays(1, &gPhoneVao);
        glGenBuffers(1, &gPhoneVbo);
        glBindVertexArray(gPhoneVao);
        glBindBuffer(GL_ARRAY_BUFFER, gPhoneVbo);
        const GLsizei stride = sizeof(HudVert);
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, (void*)offsetof(HudVert, x));
        glEnableVertexAttribArray(1);
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, stride, (void*)offsetof(HudVert, r));
        glBindVertexArray(0);
        changed = 1;
    }
    if (changed || gPhoneVerts == 0)
    {
        std::vector<HudVert> verts;
        verts.reserve(size_t(n) * 6);
        const float fw = float(w), fh = float(h);
        for (int i = 0; i < n; ++i)
        {
            const PhonepadRect& r = rects[i];
            PushHudRect(verts, r.x0, r.y0, r.x1, r.y1, fw, fh,
                        float((r.rgba >> 24) & 255) / 255.0f, float((r.rgba >> 16) & 255) / 255.0f,
                        float((r.rgba >> 8) & 255) / 255.0f, float(r.rgba & 255) / 255.0f);
        }
        glBindBuffer(GL_ARRAY_BUFFER, gPhoneVbo);
        glBufferData(GL_ARRAY_BUFFER, GLsizeiptr(verts.size() * sizeof(HudVert)), verts.data(), GL_STATIC_DRAW);
        glBindBuffer(GL_ARRAY_BUFFER, 0);
        gPhoneVerts = GLsizei(verts.size());
    }

    GLboolean prevBlend = glIsEnabled(GL_BLEND);
    GLboolean prevDepth = glIsEnabled(GL_DEPTH_TEST);
    GLboolean prevCull  = glIsEnabled(GL_CULL_FACE);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_CULL_FACE);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    glUseProgram(gHudProg);
    glBindVertexArray(gPhoneVao);
    glDrawArrays(GL_TRIANGLES, 0, gPhoneVerts);
    glBindVertexArray(0);
    glUseProgram(0);
    if (!prevBlend) glDisable(GL_BLEND);
    if ( prevDepth) glEnable(GL_DEPTH_TEST);
    if ( prevCull)  glEnable(GL_CULL_FACE);
}

// The level menu (game/level_menu.h; docs/plans/2026-10-01-level-menu-selector.md):
// called by WFGame::RunLevelMenu between RenderBegin and RenderEnd, with the menu's
// rectangles for the w x h surface. Same HUD program as the phone panel; its own
// VAO/VBO, re-uploaded only when the rectangles change.
extern "C" void
WFAndroidDrawLevelMenu(const PhonepadRect* rects, int n, int w, int h)
{
    if (w <= 0 || h <= 0 || n <= 0) return;
    HudInit();
    if (gHudProg == 0) return;
    bool changed = gMenuVao == 0 || w != gMenuW || h != gMenuH || size_t(n) != gMenuLast.size()
                   || std::memcmp(gMenuLast.data(), rects, size_t(n) * sizeof(PhonepadRect)) != 0;
    if (gMenuVao == 0)
    {
        glGenVertexArrays(1, &gMenuVao);
        glGenBuffers(1, &gMenuVbo);
        glBindVertexArray(gMenuVao);
        glBindBuffer(GL_ARRAY_BUFFER, gMenuVbo);
        const GLsizei stride = sizeof(HudVert);
        glEnableVertexAttribArray(0);
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, (void*)offsetof(HudVert, x));
        glEnableVertexAttribArray(1);
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, stride, (void*)offsetof(HudVert, r));
        glBindVertexArray(0);
    }
    if (changed)
    {
        std::vector<HudVert> verts;
        verts.reserve(size_t(n) * 6);
        const float fw = float(w), fh = float(h);
        for (int i = 0; i < n; ++i)
        {
            const PhonepadRect& r = rects[i];
            PushHudRect(verts, r.x0, r.y0, r.x1, r.y1, fw, fh,
                        float((r.rgba >> 24) & 255) / 255.0f, float((r.rgba >> 16) & 255) / 255.0f,
                        float((r.rgba >> 8) & 255) / 255.0f, float(r.rgba & 255) / 255.0f);
        }
        glBindBuffer(GL_ARRAY_BUFFER, gMenuVbo);
        glBufferData(GL_ARRAY_BUFFER, GLsizeiptr(verts.size() * sizeof(HudVert)), verts.data(), GL_STATIC_DRAW);
        glBindBuffer(GL_ARRAY_BUFFER, 0);
        gMenuVerts = GLsizei(verts.size());
        gMenuLast.assign(rects, rects + n);
        gMenuW = w;
        gMenuH = h;
    }
    GLboolean prevBlend = glIsEnabled(GL_BLEND);
    GLboolean prevDepth = glIsEnabled(GL_DEPTH_TEST);
    GLboolean prevCull  = glIsEnabled(GL_CULL_FACE);
    glViewport(0, 0, w, h);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_CULL_FACE);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    glUseProgram(gHudProg);
    glBindVertexArray(gMenuVao);
    glDrawArrays(GL_TRIANGLES, 0, gMenuVerts);
    glBindVertexArray(0);
    glUseProgram(0);
    if (!prevBlend) glDisable(GL_BLEND);
    if ( prevDepth) glEnable(GL_DEPTH_TEST);
    if ( prevCull)  glEnable(GL_CULL_FACE);
}

void AndroidSwapBuffers()
{
    if (gEglDisplay != EGL_NO_DISPLAY && gEglSurface != EGL_NO_SURFACE)
    {
        WFAndroidDrawHUD();
        WFAndroidDrawPhoneOverlay();
        eglSwapBuffers(gEglDisplay, gEglSurface);
    }
}

#endif  // __ANDROID__
