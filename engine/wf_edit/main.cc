//=============================================================================
// engine/wf_edit/main.cc — World Foundry collaborative level editor (wf-edit).
//
// Milestone 2: embed the engine viewport. The editor owns a GLFW X11/GLX
// window, registers that context with the engine (SetHostGLContext) and a
// per-frame UI callback (SetEditorFrameCallback), then calls HALStart. The
// engine's PIGSMain runs in `--editor` mode → WFGame::RunEditor, which each
// frame does StepFrame(do_swap=false) (renders the level into the back buffer)
// then calls back here so we composite an ImGui overlay and swap. Approach (a)
// per docs/plans/2026-05-20-editor-app-shell.md; Linux/X11 only.
//=============================================================================

#define GLFW_EXPOSE_NATIVE_X11
#define GLFW_EXPOSE_NATIVE_GLX
#include <GLFW/glfw3.h>
#include <GLFW/glfw3native.h>

#include "imgui.h"
#include "imgui_internal.h"   // DockBuilder API (default panel layout)
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"

#include <gfx/host_gl_context.h>
#include <game/editor_hook.h>
#include <hal/hal.h>
#include <pigsys/pigsys.hp>

#include "level_doc.h"
#include "property_panel.h"
#include "engine_bridge.h"
#include "wfcrdt.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

// Provided by the engine's platform layer (mirrors the host-GL e2e harness).
extern void ParseWindowSwitches(int argc, char** argv);
extern char szAppName[];

namespace {

struct EditorCtx {
    GLFWwindow* win = nullptr;
    int         max_frames = -1;   // <0 = run until the window closes
    int         frame = 0;
    const char* shot = nullptr;    // --screenshot: PPM dump on the last frame

    // M4 read-only Y.Doc: actor names read out of the CRDT doc (see level_doc).
    std::string              level_name;
    std::vector<std::string> actor_names;
    int                      selected = -1;

    // Property panel: the selected actor's fields, read from the Doc and (Phase
    // 2) correlated against its class .oad into widget-typed PropFields, cached
    // until the selection changes. `doc` is owned by main().
    wfcrdt::Doc*                  doc = nullptr;
    int                           fields_for = -1;   // which actor `props` holds
    std::vector<wfedit::PropField> props;
};

// Dump the composited back buffer (engine render + ImGui overlay) to a P6 PPM.
// GL rows are bottom-up; flip for top-down PPM. Convert to PNG with ffmpeg.
void write_ppm(GLFWwindow* win, const char* path)
{
    int w, h;
    glfwGetFramebufferSize(win, &w, &h);
    std::vector<unsigned char> px(static_cast<size_t>(w) * h * 3);
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE, px.data());
    FILE* f = std::fopen(path, "wb");
    if (!f) { std::fprintf(stderr, "wf-edit: cannot write %s\n", path); return; }
    std::fprintf(f, "P6\n%d %d\n255\n", w, h);
    for (int y = h - 1; y >= 0; --y)
        std::fwrite(px.data() + static_cast<size_t>(y) * w * 3, 1, static_cast<size_t>(w) * 3, f);
    std::fclose(f);
    std::printf("wf-edit: screenshot %s (%dx%d)\n", path, w, h);
}

// Called by WFGame::RunEditor each frame, after StepFrame has rendered the
// engine into the back buffer (no swap). We composite the ImGui overlay and
// swap. Return false to quit.
bool editor_frame(void* p)
{
    EditorCtx* c = static_cast<EditorCtx*>(p);
    glfwPollEvents();
    if (glfwWindowShouldClose(c->win))
        return false;

    // M1 CRDT->engine bridge: one-shot identity-map verification dump (Doc
    // actor <-> engine actor idx), gated WF_EDIT_BRIDGE_DEBUG. Runs on the first
    // frame, by which point the engine has loaded the level (theLevel valid).
    static bool s_bridge_dumped = false;
    if (!s_bridge_dumped && c->doc && std::getenv("WF_EDIT_BRIDGE_DEBUG")) {
        s_bridge_dumped = true;
        wfedit::DumpIdentityMap(*c->doc);
        // M2: field-translation dump for the selected actor (House/0 by default
        // — the richest field set), showing each field's Doc->wfmut mapping.
        wfedit::DumpTranslations(*c->doc, c->selected >= 0 ? c->selected : 0);
    }

    ImGui_ImplOpenGL3_NewFrame();
    ImGui_ImplGlfw_NewFrame();
    ImGui::NewFrame();

    // Dockspace with a pass-through central node: the engine already rendered
    // fullscreen into the back buffer (StepFrame), and the central node draws
    // no background, so the engine viewport shows through; panels dock around
    // it. (Rendering the engine into an FBO for a discrete viewport texture is
    // a confirmed-viable refinement — the engine renders into whatever FBO is
    // bound in non-record mode — but not needed for the M3 layout.)
    ImGuiID dock_id = ImGui::DockSpaceOverViewport(
        0, ImGui::GetMainViewport(), ImGuiDockNodeFlags_PassthruCentralNode);

    static bool s_layout = false;
    if (!s_layout) {
        s_layout = true;
        ImGui::DockBuilderRemoveNode(dock_id);
        ImGui::DockBuilderAddNode(dock_id,
            ImGuiDockNodeFlags_PassthruCentralNode | ImGuiDockNodeFlags_DockSpace);
        ImGui::DockBuilderSetNodeSize(dock_id, ImGui::GetMainViewport()->WorkSize);
        ImGuiID center = dock_id;
        ImGuiID left   = ImGui::DockBuilderSplitNode(center, ImGuiDir_Left,  0.20f, nullptr, &center);
        ImGuiID right  = ImGui::DockBuilderSplitNode(center, ImGuiDir_Right, 0.25f, nullptr, &center);
        ImGui::DockBuilderDockWindow("Outliner",   left);
        ImGui::DockBuilderDockWindow("Properties", right);
        ImGui::DockBuilderFinish(dock_id);
    }

    if (ImGui::BeginMainMenuBar()) {
        if (ImGui::BeginMenu("File")) {
            ImGui::MenuItem("Publish to .blend", nullptr, false, false);   // M5+
            ImGui::EndMenu();
        }
        ImGui::TextDisabled("   World Foundry Editor");
        ImGui::EndMainMenuBar();
    }

    ImGui::Begin("Outliner");
    ImGui::Text("%s: %zu actors", c->level_name.c_str(), c->actor_names.size());
    ImGui::TextDisabled("(read from the Y.Doc)");
    ImGui::Separator();
    for (int i = 0; i < static_cast<int>(c->actor_names.size()); ++i) {
        if (ImGui::Selectable(c->actor_names[i].c_str(), c->selected == i))
            c->selected = i;
    }
    ImGui::End();

    ImGui::Begin("Properties");
    if (c->selected >= 0 && c->selected < static_cast<int>(c->actor_names.size())) {
        // Re-read this actor's fields from the Doc and re-correlate against its
        // class .oad when the selection changes.
        if (c->doc && c->fields_for != c->selected) {
            c->props = wfedit::ResolveProperties(
                wfedit::ReadActorFields(*c->doc, c->selected));
            c->fields_for = c->selected;
        }
        ImGui::Text("Name");
        ImGui::SameLine(150);
        ImGui::TextUnformatted(c->actor_names[c->selected].c_str());
        ImGui::Separator();
        // Phase 3: OAD-driven widgets keyed on (ButtonType × showAs), editable —
        // edits commit to the Doc leaf (the in-memory field mirrors the new value
        // for display). Doc→engine→viewport propagation is the separate bridge.
        if (c->doc)
            wfedit::RenderProperties(*c->doc, c->selected, c->props);
        int matched = 0;
        for (const auto& p : c->props) matched += p.matched;
        ImGui::TextDisabled("%zu fields (editable → Doc) — %d OAD-matched",
                            c->props.size(), matched);
    } else {
        ImGui::TextDisabled("(select an actor)");
    }
    ImGui::End();

    // Status readout floating over the central (engine) region.
    ImGui::SetNextWindowBgAlpha(0.35f);
    if (ImGui::Begin("##status", nullptr,
            ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
            ImGuiWindowFlags_NoDocking | ImGuiWindowFlags_NoNav)) {
        ImGui::Text("Viewport: engine StepFrame   frame %d   %.1f FPS",
                    c->frame, ImGui::GetIO().Framerate);
    }
    ImGui::End();

    ImGui::Render();
    ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());

    if (c->shot && c->max_frames > 0 && c->frame == c->max_frames - 1)
        write_ppm(c->win, c->shot);   // capture the last composited frame
    glfwSwapBuffers(c->win);   // editor owns the swap (StepFrame ran do_swap=false)

    ++c->frame;
    if (c->max_frames >= 0 && c->frame >= c->max_frames)
        return false;
    return true;
}

void glfw_error(int code, const char* desc)
{
    std::fprintf(stderr, "wf-edit: GLFW error %d: %s\n", code, desc);
}

}  // namespace

int main(int argc, char** argv)
{
    int         max_frames = -1;
    int         preselect  = -1;   // --select=N: headless aid — preselect actor N
    const char* shot = nullptr;
    // Viewport level (engine LoadLevel) + the .lev parsed into the read-only
    // Y.Doc. Default both to snowgoons-blender so the viewport and Outliner
    // show the same level (plan D7); override independently for now.
    std::string level     = "wflevels/snowgoons-blender/snowgoons-standalone.iff";
    std::string leveltree = "wflevels/snowgoons-blender/snowgoons-blender.lev";
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--frames") == 0 && i + 1 < argc)
            max_frames = std::atoi(argv[++i]);
        else if (std::strcmp(argv[i], "--screenshot") == 0 && i + 1 < argc)
            shot = argv[++i];
        else if (std::strncmp(argv[i], "--level=", 8) == 0)
            level = argv[i] + 8;
        else if (std::strncmp(argv[i], "--leveltree=", 12) == 0)
            leveltree = argv[i] + 12;
        else if (std::strncmp(argv[i], "--select=", 9) == 0)
            preselect = std::atoi(argv[i] + 9);
    }

    // 0. Read-only Y.Doc (M4): shell out to `levtree parse`, build a wfcrdt::Doc
    //    in the editor CRDT schema, and read the actor names back out of it for
    //    the Outliner. CPU-only; done before any GL. The Doc is held for the
    //    program lifetime (read-only here; the CRDT→engine bridge is the next
    //    plan). A failure here is non-fatal — the shell still runs.
    wfcrdt::Doc              doc;
    std::string              level_name;
    std::vector<std::string> actor_names;
    if (wfedit::LoadLevelTreeIntoDoc(leveltree, doc)) {
        actor_names = wfedit::ReadActorNames(doc);
        level_name  = leveltree;
        if (auto slash = level_name.find_last_of('/'); slash != std::string::npos)
            level_name.erase(0, slash + 1);
        std::printf("wf-edit: Outliner shows %zu actors from the Y.Doc\n",
                    actor_names.size());
    } else {
        std::fprintf(stderr, "wf-edit: Y.Doc population failed for %s "
                             "(Outliner will be empty)\n", leveltree.c_str());
    }

    // 0b. Headless edit proof (env-gated, off by default): WF_EDIT_TEST_SET=
    //     "Field Name|DATA|new text" writes one leaf on the --select=N actor
    //     before the UI loop, prints before→after from two independent Doc reads
    //     (the second reflects the committed write), and leaves the Doc edited so
    //     the panel/screenshot show it. Exercises WriteFieldLeaf + read-back for
    //     the Phase-3 gate without UI interaction. Kept until the plan completes.
    if (const char* spec = std::getenv("WF_EDIT_TEST_SET"); spec && *spec && preselect >= 0) {
        // One or more ';'-separated edits, each "Field Name|DATA|new text".
        std::string all = spec;
        for (std::size_t pos = 0; pos < all.size() + 1; ) {
            std::size_t semi = all.find(';', pos);
            std::string s = all.substr(pos, semi == std::string::npos ? std::string::npos : semi - pos);
            pos = (semi == std::string::npos) ? all.size() + 1 : semi + 1;
            auto a = s.find('|'), b = s.rfind('|');
            if (a == std::string::npos || b <= a) continue;
            std::string fname = s.substr(0, a), leaf = s.substr(a + 1, b - a - 1),
                        text = s.substr(b + 1);
            int ci = -1; std::string before;
            for (auto& f : wfedit::ReadActorFields(doc, preselect)) if (f.name == fname) {
                ci = f.child_index; before = (leaf == "STR") ? f.label : f.data; break;
            }
            if (ci < 0) {
                std::fprintf(stderr, "[edit] field '%s' not found on actor %d\n", fname.c_str(), preselect);
                continue;
            }
            bool ok = wfedit::WriteFieldLeaf(doc, preselect, ci, leaf.c_str(), text);
            std::string now;
            for (auto& f : wfedit::ReadActorFields(doc, preselect))
                if (f.name == fname) { now = (leaf == "STR") ? f.label : f.data; break; }
            std::fprintf(stderr, "[edit] %s.%s: '%s' -> '%s' (write %s)\n",
                         fname.c_str(), leaf.c_str(), before.c_str(), now.c_str(), ok ? "ok" : "FAIL");
        }
    }

    // 1. Editor-owned GLFW X11/GLX window + context.
    glfwSetErrorCallback(glfw_error);
    if (!glfwInit()) {
        std::fprintf(stderr, "wf-edit: glfwInit failed (no display?)\n");
        return 1;
    }
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_COMPAT_PROFILE);  // engine uses legacy GL
    GLFWwindow* win = glfwCreateWindow(1280, 800, "WF Editor", nullptr, nullptr);
    if (!win) {
        std::fprintf(stderr, "wf-edit: window creation failed\n");
        glfwTerminate();
        return 1;
    }
    glfwMakeContextCurrent(win);

    // 2. ImGui (GLFW context is current; the GL3 backend creates its device
    //    objects lazily on first NewFrame, after the engine adopts this ctx).
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGui::GetIO().ConfigFlags |= ImGuiConfigFlags_DockingEnable;  // used from M3
    ImGui::StyleColorsDark();
    ImGui_ImplGlfw_InitForOpenGL(win, true);
    ImGui_ImplOpenGL3_Init("#version 130");

    // 3. Hand the engine our X11/GLX (mesa.cc adopts it via InitWithExistingContext
    //    instead of opening its own window) + register the per-frame callback.
    HostGLContext hc{ glfwGetX11Display(),
                      static_cast<unsigned long>(glfwGetX11Window(win)),
                      glfwGetGLXContext(win),
                      true };
    SetHostGLContext(&hc);
    EditorCtx ctx{ win, max_frames, 0, shot };
    ctx.level_name  = std::move(level_name);
    ctx.actor_names = std::move(actor_names);
    ctx.doc         = &doc;   // read field subtrees on selection (read-only)
    if (preselect >= 0 && preselect < static_cast<int>(ctx.actor_names.size()))
        ctx.selected = preselect;   // headless: exercise the Outliner→Properties path
    SetEditorFrameCallback(editor_frame, &ctx);

    // 4. Drive the engine. HALStart inits HAL/audio + calls PIGSMain, which in
    //    --editor mode constructs WFGame and runs RunEditor (StepFrame + our
    //    callback). The init dance mirrors the host-GL e2e harness.
    char         prog[64];
    std::strcpy(prog, "wf-edit");
    char         editflag[] = "--editor";
    std::string  lvlarg = "-L" + level;
    char         lvlbuf[1024];
    std::snprintf(lvlbuf, sizeof(lvlbuf), "%s", lvlarg.c_str());

    char*  hal_argv_storage[] = { prog, editflag, lvlbuf, nullptr };
    char** hal_argv = hal_argv_storage;
    int    hal_argc = 3;

    sys_init(&hal_argc, &hal_argv);
    std::strcpy(hal_argv[0], szAppName);   // matches platform_main.cc / e2e harness
    ParseWindowSwitches(hal_argc, hal_argv);

    std::printf("wf-edit: HALStart (--editor, level=%s)\n", level.c_str());
    HALStart(hal_argc, hal_argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
    std::printf("wf-edit: HALStart returned\n");

    // 5. Engine released its references; clear the registries + tear down.
    //    Unregister the frame callback before `ctx` leaves scope so the
    //    engine's stored ctx pointer can't dangle (no callbacks fire after
    //    HALStart returns, but keep it tidy — mirrors ClearHostGLContext).
    SetEditorFrameCallback(nullptr, nullptr);
    ClearHostGLContext();
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    glfwDestroyWindow(win);
    glfwTerminate();
    std::printf("wf-edit: clean exit\n");
    return 0;
}
