//=============================================================================
// engine/wf_edit/main.cc — World Foundry collaborative level editor (wf-edit).
//
// Dear ImGui application that hosts the editor. Milestone 1: an ImGui window
// over an editor-owned X11/GLX context (raw Xlib + GLX, the same handles the
// engine's host-GL-context handshake expects). Later milestones register that
// context via SetHostGLContext + drive WFGame::StepFrame, and add a read-only
// wfcrdt::Doc outliner. Linux/X11 only for v1.
// See docs/plans/2026-05-20-editor-app-shell.md.
//
// Windowing is raw X11/GLX rather than GLFW: GLFW's X11 backend needs the
// Xrandr/Xinerama/Xcursor/Xi -dev packages (root to install). Raw X11/GLX uses
// only core Xlib + GLX (already present) and is exactly what M2 will register.
//=============================================================================

#include <cstdio>
#include <cstdlib>
#include <cstring>

#include <X11/Xlib.h>
#include <GL/glx.h>

#include "imgui.h"
#include "imgui_impl_opengl3.h"

int main(int argc, char** argv)
{
    // --frames N runs a bounded number of frames then exits (headless smoke).
    int max_frames = -1;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--frames") == 0 && i + 1 < argc)
            max_frames = std::atoi(argv[++i]);
    }

    Display* dpy = XOpenDisplay(nullptr);
    if (!dpy) {
        std::fprintf(stderr, "wf-edit: cannot open X display (DISPLAY set?)\n");
        return 1;
    }

    // Visual the engine's host-GL-context handshake requires (mesa.cc:71).
    int attrs[] = { GLX_RGBA,
                    GLX_RED_SIZE, 1, GLX_GREEN_SIZE, 1, GLX_BLUE_SIZE, 1,
                    GLX_DOUBLEBUFFER,
                    GLX_DEPTH_SIZE, 1,
                    None };
    XVisualInfo* vi = glXChooseVisual(dpy, DefaultScreen(dpy), attrs);
    if (!vi) {
        std::fprintf(stderr, "wf-edit: no suitable GLX visual\n");
        XCloseDisplay(dpy);
        return 1;
    }

    Window root = RootWindow(dpy, vi->screen);
    Colormap cmap = XCreateColormap(dpy, root, vi->visual, AllocNone);
    XSetWindowAttributes swa;
    swa.colormap = cmap;
    swa.event_mask = ExposureMask | StructureNotifyMask | KeyPressMask |
                     KeyReleaseMask | ButtonPressMask | ButtonReleaseMask |
                     PointerMotionMask;
    Window win = XCreateWindow(dpy, root, 0, 0, 1280, 800, 0, vi->depth,
                               InputOutput, vi->visual,
                               CWColormap | CWEventMask, &swa);
    XStoreName(dpy, win, "WF Editor");
    Atom wm_delete = XInternAtom(dpy, "WM_DELETE_WINDOW", False);
    XSetWMProtocols(dpy, win, &wm_delete, 1);
    XMapWindow(dpy, win);

    GLXContext ctx = glXCreateContext(dpy, vi, nullptr, GL_TRUE);
    if (!ctx) {
        std::fprintf(stderr, "wf-edit: glXCreateContext failed\n");
        XCloseDisplay(dpy);
        return 1;
    }
    glXMakeCurrent(dpy, win, ctx);

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;  // used from M3
    ImGui::StyleColorsDark();
    ImGui_ImplOpenGL3_Init("#version 130");

    std::printf("wf-edit: shell M1 up (raw X11/GLX, %s)\n",
                max_frames < 0 ? "interactive" : "bounded");

    int w = 1280, h = 800, frame = 0;
    bool running = true;
    // (Mouse/keyboard → ImGui IO wiring is M2+; M1 proves window + render.)
    while (running) {
        while (XPending(dpy)) {
            XEvent ev;
            XNextEvent(dpy, &ev);
            if (ev.type == ConfigureNotify) {
                w = ev.xconfigure.width;
                h = ev.xconfigure.height;
            } else if (ev.type == ClientMessage &&
                       (Atom)ev.xclient.data.l[0] == wm_delete) {
                running = false;
            }
        }

        io.DisplaySize = ImVec2((float)w, (float)h);
        io.DeltaTime = 1.0f / 60.0f;

        ImGui_ImplOpenGL3_NewFrame();
        ImGui::NewFrame();

        ImGui::Begin("World Foundry Editor");
        ImGui::TextUnformatted("Collaborative level editor — shell milestone 1");
        ImGui::Text("raw X11/GLX  |  %dx%d  |  frame %d", w, h, frame);
        ImGui::End();

        ImGui::Render();
        glViewport(0, 0, w, h);
        glClearColor(0.10f, 0.10f, 0.12f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        glXSwapBuffers(dpy, win);

        if (max_frames >= 0 && ++frame >= max_frames)
            running = false;
    }

    ImGui_ImplOpenGL3_Shutdown();
    ImGui::DestroyContext();
    glXMakeCurrent(dpy, None, nullptr);
    glXDestroyContext(dpy, ctx);
    XDestroyWindow(dpy, win);
    XCloseDisplay(dpy);
    std::printf("wf-edit: clean exit\n");
    return 0;
}
