//=============================================================================
// gfx/host_gl_context.h: editor-supplied X11/GLX context registration
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Phase 0b sub-task #2 of the collaborative editor design. Lets an external
// host (Dear ImGui overlay, QOpenGLWidget, GLFW harness, etc.) supply its
// own X11 Display* / Window / GLXContext to the engine in place of having
// the engine call XOpenDisplay / glXCreateContext / XCreateWindow.
//
// Standalone wf_game leaves this unset; mesa.cc's InitWindow() falls through
// to OpenMainWindow("World Foundry") as before. An editor host calls
// SetHostGLContext({display, win, context, true}) BEFORE constructing WFGame
// (which constructs Display, which calls InitWindow); mesa.cc's InitWindow
// then dispatches to InitWithExistingContext() instead.
//
// Opaque void* / unsigned long types — header must compile in TUs that don't
// pull in X11.h or GLX.h (mobile stubs, editor public surface).
//
// Required GLX visual attributes the host's GLXContext must satisfy
// (matches mesa.cc:71 attributeList):
//   GLX_RGBA, GLX_RED_SIZE >= 1, GLX_GREEN_SIZE >= 1, GLX_BLUE_SIZE >= 1,
//   GLX_DOUBLEBUFFER, GLX_DEPTH_SIZE >= 1
//
// v1 single-WFGame-instance constraint: only one engine instance may consume
// the registered context; constructing a second WFGame while the first lives
// is unsupported (Tier 1 single-viewport per editor design doc).
//=============================================================================

#ifndef _GFX_HOST_GL_CONTEXT_H
#define _GFX_HOST_GL_CONTEXT_H

#if defined(__cplusplus)
extern "C" {
#endif

struct HostGLContext {
    void*         display;   // cast to XDisplay* inside the GL backend
    unsigned long win;       // GLX drawable the engine makes-current + swaps (XID,
                             // unsigned long per Xlib). On the modern GLX 1.3 path
                             // pass your GLXWindow (e.g. glfwGetGLXWindow), NOT the
                             // raw X11 Window — the compositor tracks the GLXWindow,
                             // so swapping the raw window leaves the viewport black.
    void*         context;   // cast to GLXContext inside the GL backend
    bool          valid;     // false = engine creates its own (standalone)
};

void           SetHostGLContext(const struct HostGLContext* h);
struct HostGLContext GetHostGLContext(void);
void           ClearHostGLContext(void);

#if defined(__cplusplus)
}
#endif

#endif // _GFX_HOST_GL_CONTEXT_H
