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

#include <cstdio>
#include <cstdlib>
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

extern "C" bool
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

extern "C" void
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

}  // namespace

// native_app_entry.cc calls this after AConfiguration_getUiModeType — suppress
// the HUD on Google TV / Android TV where input is gamepad-only.
extern "C" void
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

    // D-pad cross + A + B — same pixel regions the hit test uses.
    std::vector<HudVert> verts;
    verts.reserve(6 * 6);

    // D-pad: four directional buttons. Slightly brighter gray; 50% alpha.
    const float gR = 0.6f, gG = 0.6f, gB = 0.6f, gA = 0.5f;
    PushHudRect(verts, 0,    h-133, 66,  h-66,  fw, fh, gR, gG, gB, gA);  // LEFT
    PushHudRect(verts, 133,  h-133, 200, h-66,  fw, fh, gR, gG, gB, gA);  // RIGHT
    PushHudRect(verts, 66,   h-200, 133, h-133, fw, fh, gR, gG, gB, gA);  // UP
    PushHudRect(verts, 66,   h-66,  133, h,     fw, fh, gR, gG, gB, gA);  // DOWN

    // Action buttons. A=red (primary); B=blue.
    PushHudRect(verts, w-120, h-120, w,     h, fw, fh, 0.80f, 0.25f, 0.25f, 0.55f);
    PushHudRect(verts, w-240, h-120, w-120, h, fw, fh, 0.25f, 0.35f, 0.85f, 0.55f);

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

void AndroidSwapBuffers()
{
    if (gEglDisplay != EGL_NO_DISPLAY && gEglSurface != EGL_NO_SURFACE)
    {
        WFAndroidDrawHUD();
        eglSwapBuffers(gEglDisplay, gEglSurface);
    }
}

#endif  // __ANDROID__
