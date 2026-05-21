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
#include "level_save.h"
#include "wfcrdt.hpp"
#include "collab_session.h"
#include "voice_track.h"
#include "video_track.h"
#include "collab_panel.h"

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

    // Save round-trip: the .lev path File→Save writes (the Doc is lossless — v2
    // schema — so save needs no retained JSON), and a transient toast.
    std::string save_path;
    std::string toast;
    int         toast_frames = 0;

    // M2: no longer set by delete/duplicate — the stable map (InitBridgeMap +
    // BridgeNotifyDelete/Duplicate) keeps propagation live through structural
    // edits. Kept for future use (e.g. non-recoverable corruption); currently
    // always false after M2.
    bool structural_dirty = false;

    // Voice + video collaboration (optional; only active when --room is given).
    wfedit::CollabSession* collab  = nullptr;
    wfedit::VoiceChat*     voice   = nullptr;
    wfedit::VideoChat*     video   = nullptr;
    std::string            room_id;
    bool                   show_collab = true;
};

// File→Save (and Ctrl+S / headless WF_EDIT_SAVE_UI): patch the parse JSON with
// the Doc and `levtree print` it to save_path; flash the result as a toast.
void DoSave(EditorCtx* c)
{
    if (!c->doc || c->save_path.empty()) {
        c->toast = "save: no document / path"; c->toast_frames = 180; return;
    }
    const bool ok = wfedit::SaveDocToLev(*c->doc, c->save_path);
    c->toast = (ok ? "saved " : "SAVE FAILED: ") + c->save_path;
    c->toast_frames = 180;
}

// File→Save + Compile: save the .lev, then run the .lev→.iff pipeline
// (build_level_binary.sh). Synchronous — blocks the frame for the few seconds
// the 5-stage build takes (a deliberate user action). The live engine is NOT
// reloaded (out of scope); the .iff is produced for the next play/load.
void SaveAndCompile(EditorCtx* c)
{
    if (!c->doc || c->save_path.empty()) {
        c->toast = "compile: no document / path"; c->toast_frames = 180; return;
    }
    if (!wfedit::SaveDocToLev(*c->doc, c->save_path)) {
        c->toast = "SAVE FAILED: " + c->save_path; c->toast_frames = 180; return;
    }
    std::string name = c->save_path;   // level name = basename without ".lev"
    if (auto s = name.find_last_of('/'); s != std::string::npos) name.erase(0, s + 1);
    if (auto d = name.rfind(".lev"); d != std::string::npos) name.erase(d);

    std::string log;
    const bool ok = wfedit::RunBuildLevel(name, log);
    std::fprintf(stderr, "%s", log.c_str());
    std::string last;   // last non-empty line: the script's "built …" or the error
    for (std::size_t i = 0, b = 0; i <= log.size(); ++i)
        if (i == log.size() || log[i] == '\n') { if (i > b) last.assign(log, b, i - b); b = i + 1; }
    // Drop the script's leading ✓ glyph (U+2713) + space — ImGui's default font
    // has no glyph for it, so it renders as "?".
    std::size_t k = 0;
    while (k < last.size() && static_cast<unsigned char>(last[k]) >= 0x80) ++k;
    if (k < last.size() && last[k] == ' ') ++k;
    c->toast = ok ? ("compiled: " + last.substr(k)) : "compile FAILED — see stderr";
    c->toast_frames = 240;
}

// After an Outliner add/delete: re-read the actor list from the Doc, clamp the
// selection, and force the property cache to re-resolve. Does NOT touch
// structural_dirty — the stable bridge map keeps propagation live (M2).
void RefreshActorList(EditorCtx* c)
{
    c->actor_names = wfedit::ReadActorNames(*c->doc);
    if (c->selected >= static_cast<int>(c->actor_names.size()))
        c->selected = static_cast<int>(c->actor_names.size()) - 1;
    c->fields_for = -1;          // force Properties to re-resolve on the next frame
}

void DoDelete(EditorCtx* c)
{
    if (!c->doc || c->selected < 0) return;
    wfedit::BridgeNotifyDelete(c->selected);   // erase map entry + RemoveActor before Doc mutates
    if (wfedit::DeleteActor(*c->doc, c->selected)) {
        RefreshActorList(c);
        c->toast = "actor deleted";
        c->toast_frames = 180;
    }
}

void DoDuplicate(EditorCtx* c)
{
    if (!c->doc || c->selected < 0) return;
    const int src = c->selected;
    const int ni = wfedit::DuplicateActor(*c->doc, src);
    if (ni < 0) return;
    const bool live = wfedit::BridgeNotifyDuplicate(src, ni);
    RefreshActorList(c);
    c->selected = ni;            // select the copy
    if (!live) {
        c->toast = "duplicated — non-templated actor: reload to see in viewport";
        c->toast_frames = 300;
    }
}

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

    // One-shot GL-state diagnostic (WF_EDIT_GL_DEBUG): the editor renders fine to
    // the back buffer (glReadPixels) yet the window is black on screen, while a
    // plain GLFW window presents. Dump the GL/GLX state at callback time to find
    // what the engine's context adoption changed vs a stock GLFW loop.
    static bool s_gl_dumped = false;
    if (!s_gl_dumped && std::getenv("WF_EDIT_GL_DEBUG")) {
        s_gl_dumped = true;
        GLint fb = -1, drawbuf = -1, readbuf = -1;
        GLboolean dbl = GL_FALSE;
        glGetIntegerv(GL_FRAMEBUFFER_BINDING, &fb);
        glGetIntegerv(GL_DRAW_BUFFER, &drawbuf);
        glGetIntegerv(GL_READ_BUFFER, &readbuf);
        glGetBooleanv(GL_DOUBLEBUFFER, &dbl);
        GLXContext  curctx  = glXGetCurrentContext();
        GLXDrawable curdraw = glXGetCurrentDrawable();
        std::fprintf(stderr,
            "[gl-debug] FRAMEBUFFER_BINDING=%d DRAW_BUFFER=0x%04x READ_BUFFER=0x%04x "
            "DOUBLEBUFFER=%d glErr=0x%04x\n",
            fb, drawbuf, readbuf, (int)dbl, glGetError());
        std::fprintf(stderr,
            "[gl-debug] curGLXctx=%p curGLXdraw=0x%lx | glfwGLXWindow=0x%lx "
            "glfwX11Window=0x%lx glfwGLXctx=%p glfwCurCtx=%p win=%p\n",
            (void*)curctx, (unsigned long)curdraw,
            (unsigned long)glfwGetGLXWindow(c->win),
            (unsigned long)glfwGetX11Window(c->win),
            (void*)glfwGetGLXContext(c->win),
            (void*)glfwGetCurrentContext(), (void*)c->win);
    }

    // M2: initialize the stable doc→engine index map on the first frame the live
    // level is available (theLevel non-null). No-op once initialized.
    if (c->doc) wfedit::InitBridgeMap(*c->doc);

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
    // M3 headless proof (WF_EDIT_BRIDGE_TEST="Field Name|new DATA"): edit the
    // --select'd actor's field as the panel commit would, propagate it through
    // the bridge, and log the engine actor's pos before/after. The change lands
    // before this frame's swap, so subsequent frames render it and --screenshot
    // captures the moved actor.
    static bool s_bridge_tested = false;
    if (!s_bridge_tested && c->doc && c->selected >= 0) {
        if (const char* spec = std::getenv("WF_EDIT_BRIDGE_TEST"); spec && *spec) {
            s_bridge_tested = true;
            std::string s = spec;
            if (auto bar = s.find('|'); bar != std::string::npos)
                wfedit::RunBridgeTest(*c->doc, c->selected, s.substr(0, bar), s.substr(bar + 1));
        }
    }
    // M3 save-UI screenshot proof: WF_EDIT_SAVE_UI=<path> drives File→Save once
    // from inside the frame loop (so the toast renders + --screenshot captures
    // it), unlike the pre-GL WF_EDIT_SAVE which exits before any UI.
    static bool s_save_ui = false;
    if (!s_save_ui && c->doc) {
        if (const char* p = std::getenv("WF_EDIT_SAVE_UI"); p && *p) {
            s_save_ui = true;
            c->save_path = p;
            DoSave(c);
        }
    }
    // Outliner-UI screenshot proof: WF_EDIT_STRUCT_UI=dup|del drives a structural
    // edit via the UI path once (sets structural_dirty + the toast/hint), so the
    // screenshot shows the post-edit Outliner.
    static bool s_struct_ui = false;
    if (!s_struct_ui && c->doc && c->selected >= 0) {
        if (const char* p = std::getenv("WF_EDIT_STRUCT_UI"); p && *p) {
            s_struct_ui = true;
            if (std::string(p) == "dup") DoDuplicate(c);
            else if (std::string(p) == "del") DoDelete(c);
        }
    }
    // SpawnActor runtime-path confirmation: WF_EDIT_SPAWN_CONFIRM_TEST=1 finds
    // the first valid template in the live level, spawns it at a safe position,
    // and logs PASS/FAIL to stderr. Confirms the Jolt position-sync fix
    // (commit 0adf1d4) works end-to-end. Run with --frames 5 to exit after.
    static bool s_spawn_tested = false;
    if (!s_spawn_tested && std::getenv("WF_EDIT_SPAWN_CONFIRM_TEST")) {
        s_spawn_tested = true;
        wfedit::RunSpawnConfirmTest();
    }

    // M4 headless: WF_EDIT_COMPILE drives Save + Compile once (saves to the
    // level's source path, then runs the .lev→.iff pipeline) for the gate.
    static bool s_compile_ui = false;
    if (!s_compile_ui && c->doc && std::getenv("WF_EDIT_COMPILE")) {
        s_compile_ui = true;
        SaveAndCompile(c);
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

    // Tick collab session (peer discovery + voice recv + video frame upload).
    if (c->collab) {
        double now = wfedit::MonoNow();
        c->collab->Tick(now);
        c->voice->SyncPeers(c->collab->Peers());
        c->video->SyncPeers(c->collab->Peers());
        c->voice->Tick();
        c->video->UploadFrames();
    }

    if (ImGui::BeginMainMenuBar()) {
        if (ImGui::BeginMenu("File")) {
            if (ImGui::MenuItem("Save Level", "Ctrl+S")) DoSave(c);
            if (ImGui::MenuItem("Save + Compile (.iff)")) SaveAndCompile(c);
            ImGui::MenuItem("Publish to .blend", nullptr, false, false);   // later: hand off to wf.import_level
            ImGui::EndMenu();
        }
        if (c->collab && ImGui::BeginMenu("View")) {
            ImGui::MenuItem("Collaborators", nullptr, &c->show_collab);
            ImGui::EndMenu();
        }
        ImGui::TextDisabled("   World Foundry Editor");
        if (c->collab)
            ImGui::TextDisabled("  | room: %s", c->room_id.c_str());
        ImGui::EndMainMenuBar();
    }

    // Keyboard shortcuts (when no text widget is capturing the keypress).
    const bool typing = ImGui::GetIO().WantTextInput;
    if (!typing && ImGui::GetIO().KeyCtrl && ImGui::IsKeyPressed(ImGuiKey_S, false))
        DoSave(c);
    if (!typing && c->selected >= 0 && ImGui::IsKeyPressed(ImGuiKey_Delete, false))
        DoDelete(c);

    ImGui::Begin("Outliner");
    ImGui::Text("%s: %zu actors", c->level_name.c_str(), c->actor_names.size());
    ImGui::TextDisabled("(read from the Y.Doc)");
    // Add/delete actors (structural; persists on save). Duplicate clones the
    // selected actor; Delete removes it (or the Del key).
    ImGui::BeginDisabled(c->selected < 0);
    if (ImGui::SmallButton("Duplicate")) DoDuplicate(c);
    ImGui::SameLine();
    if (ImGui::SmallButton("Delete"))    DoDelete(c);
    ImGui::EndDisabled();
    if (c->structural_dirty) {
        ImGui::SameLine();
        ImGui::TextDisabled("(reload for live preview)");
    }
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
        // edits commit to the Doc leaf. M3 CRDT→engine bridge: each committed
        // field is propagated through wfmut on the live level (game thread — this
        // callback runs inside RunEditor), so the next StepFrame re-renders the
        // change. Transform + the 15 kPropMap fields move the viewport; the rest
        // edit the Doc only (logged NoOp).
        if (c->doc) {
            std::vector<int> committed;
            wfedit::RenderProperties(*c->doc, c->selected, c->props, &committed);
            // structural_dirty guard: kept for future cases; currently always
            // false (M2 stable map keeps propagation live through structural edits).
            if (!c->structural_dirty)
                for (int ci : committed)
                    if (ci >= 0 && ci < static_cast<int>(c->props.size()))
                        wfedit::PropagateToEngine(c->selected, c->props[ci]);
        }
        int matched = 0;
        for (const auto& p : c->props) matched += p.matched;
        ImGui::TextDisabled("%zu fields (editable → Doc) — %d OAD-matched",
                            c->props.size(), matched);
    } else {
        ImGui::TextDisabled("(select an actor)");
    }
    ImGui::End();

    // Collaborators panel (voice + video; only when a room is active).
    if (c->collab)
        wfedit::RenderCollabPanel(c->show_collab, *c->collab,
                                  *c->voice, *c->video, c->room_id);

    // Status readout floating over the central (engine) region.
    ImGui::SetNextWindowBgAlpha(0.35f);
    if (ImGui::Begin("##status", nullptr,
            ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
            ImGuiWindowFlags_NoDocking | ImGuiWindowFlags_NoNav)) {
        ImGui::Text("Viewport: engine StepFrame   frame %d   %.1f FPS",
                    c->frame, ImGui::GetIO().Framerate);
    }
    ImGui::End();

    // Save toast (bottom-left), flashed for ~180 frames after a save.
    if (c->toast_frames > 0) {
        --c->toast_frames;
        ImGuiViewport* vp = ImGui::GetMainViewport();
        ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + 16,
                                       vp->WorkPos.y + vp->WorkSize.y - 56));
        ImGui::SetNextWindowBgAlpha(0.85f);
        if (ImGui::Begin("##savetoast", nullptr,
                ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
                ImGuiWindowFlags_NoDocking | ImGuiWindowFlags_NoNav | ImGuiWindowFlags_NoInputs)) {
            ImGui::TextUnformatted(c->toast.c_str());
            ImGui::TextDisabled("re-import in Blender (wf.import_level) to refresh the .blend");
        }
        ImGui::End();
    }

    ImGui::Render();
    ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());

    if (c->shot && c->max_frames > 0 && c->frame == c->max_frames - 1)
        write_ppm(c->win, c->shot);   // capture the last composited frame

    // Editor owns the swap (StepFrame ran do_swap=false). glfwSwapBuffers swaps
    // GLFW's GLXWindow — the same drawable we hand the engine to render into (see
    // the HostGLContext below, which passes glfwGetGLXWindow) and the one the X
    // compositor tracks. Swapping the raw X11 window instead presents to a buffer
    // the compositor never reads → a black viewport, with only the engine's
    // teardown PageFlip swap flashing the last frame just before exit.
    glfwSwapBuffers(c->win);

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
    std::string room_id;           // --room=<id>: join a voice+video call room
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
        else if (std::strncmp(argv[i], "--room=", 7) == 0)
            room_id = argv[i] + 7;
        else if (std::strcmp(argv[i], "--room") == 0 && i + 1 < argc)
            room_id = argv[++i];
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

    // 0b2. Headless structural-edit proof (env-gated): WF_EDIT_STRUCT_TEST=
    //      "dup=N;del=M;…" duplicates / deletes actors in the Doc `content`
    //      before save — the lossless schema's payoff (changing the actor count,
    //      not just field values). Combined with WF_EDIT_SAVE below it proves the
    //      structural change persists. CPU-only, pre-GL.
    if (const char* spec = std::getenv("WF_EDIT_STRUCT_TEST"); spec && *spec) {
        std::string all = spec;
        for (std::size_t pos = 0; pos < all.size() + 1; ) {
            std::size_t semi = all.find(';', pos);
            std::string s = all.substr(pos, semi == std::string::npos ? std::string::npos : semi - pos);
            pos = (semi == std::string::npos) ? all.size() + 1 : semi + 1;
            auto eq = s.find('=');
            if (eq == std::string::npos) continue;
            std::string op = s.substr(0, eq);
            int idx = std::atoi(s.substr(eq + 1).c_str());
            const int before = static_cast<int>(wfedit::ReadActorNames(doc).size());
            if (op == "del") {
                bool ok = wfedit::DeleteActor(doc, idx);
                std::fprintf(stderr, "[struct] del=%d  %d -> %zu actors (%s)\n",
                             idx, before, wfedit::ReadActorNames(doc).size(), ok ? "ok" : "FAIL");
            } else if (op == "dup") {
                int ni = wfedit::DuplicateActor(doc, idx);
                std::fprintf(stderr, "[struct] dup=%d  %d -> %zu actors (new idx %d)\n",
                             idx, before, wfedit::ReadActorNames(doc).size(), ni);
            }
        }
    }

    // 0c. Headless save (env-gated): WF_EDIT_SAVE=<path> walks the Doc → canonical
    //     `.lev` (incl. any WF_EDIT_TEST_SET / WF_EDIT_STRUCT_TEST edits above) and
    //     exits — no GL. The headless mirror of File→Save (M3); the round-trip
    //     identity gate runs this with no edits. CPU-only; pre-window/engine init.
    if (const char* save_path = std::getenv("WF_EDIT_SAVE"); save_path && *save_path) {
        const bool ok = wfedit::SaveDocToLev(doc, save_path);
        std::fprintf(stderr, "wf-edit: WF_EDIT_SAVE %s -> %s\n", save_path, ok ? "ok" : "FAIL");
        return ok ? 0 : 1;
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
    // Opaque framebuffer (no alpha), matching standalone wf_game's GLX visual
    // (mesa.cc attributeList omits GLX_ALPHA_SIZE). Defensive: GLFW defaults to
    // 8 alpha bits, and on a compositing WM a window with alpha can be blended
    // translucent where the rendered alpha < 1. Not the black-screen fix (that
    // was the GLX drawable below) — the engine clears alpha to 1.0 each frame —
    // but it keeps the viewport unconditionally opaque.
    glfwWindowHint(GLFW_ALPHA_BITS, 0);
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
    // Pass GLFW's GLXWindow (NOT the raw X11 window) as the GLX drawable. GLFW
    // creates the window via the modern GLX 1.3 path — a glXCreateWindow GLXWindow
    // layered over the X11 window — and that GLXWindow is what the compositor
    // tracks and what glfwSwapBuffers presents. The engine glXMakeCurrent +
    // (teardown) glXSwapBuffers this drawable. Standalone wf_game works because it
    // makes its own window with a GLX *visual* (legacy 1.2), where the raw window
    // doubles as a valid GLXDrawable; an adopted GLFW window does not. In editor
    // (host-owned) mode mesa.cc uses halDisplay.win purely as the GLX drawable —
    // XEventLoop / HALCloseWindow early-bail — so a GLXWindow XID here is correct.
    HostGLContext hc{ glfwGetX11Display(),
                      static_cast<unsigned long>(glfwGetGLXWindow(win)),
                      glfwGetGLXContext(win),
                      true };
    SetHostGLContext(&hc);
    EditorCtx ctx{ win, max_frames, 0, shot };
    ctx.level_name  = std::move(level_name);
    ctx.actor_names = std::move(actor_names);
    ctx.doc         = &doc;   // read field subtrees on selection (read-only)
    ctx.save_path   = leveltree;               // Save writes back to the .lev source
    ctx.room_id     = room_id;
    if (preselect >= 0 && preselect < static_cast<int>(ctx.actor_names.size()))
        ctx.selected = preselect;   // headless: exercise the Outliner→Properties path

    // 3b. Start voice + video call if a room ID was provided.
    wfedit::CollabSession collab_session;
    wfedit::VoiceChat     voice_chat;
    wfedit::VideoChat     video_chat;
    if (!room_id.empty()) {
        // Bind to port 0 — the OS assigns an ephemeral port. Each editor
        // instance on the same machine gets a different port automatically.
        voice_chat.Start();
        video_chat.Start();
        collab_session.Start(room_id, "Editor",
                             voice_chat.ListenPort(), video_chat.ListenPort());
        ctx.collab = &collab_session;
        ctx.voice  = &voice_chat;
        ctx.video  = &video_chat;
        std::printf("wf-edit: collab room '%s' started\n", room_id.c_str());
    }

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

    // Tell the engine its real surface size. Otherwise it keeps the 640×480
    // wfWindow* defaults — ParseWindowSwitches, which would set them, is #if 0'd —
    // and WFInitGL runs glViewport(0,0,640,480) + a 640/480 projection aspect, so
    // the level renders into only the bottom-left of our 1280×800 window. Set
    // before HALStart, which constructs Display (→ _xSize/_ySize) and calls
    // WFInitGL (→ glViewport + aspect). Window resize isn't handled yet — the
    // engine's ConfigureNotify viewport path (mesa.cc) early-bails in host-owned
    // mode — so the viewport is fixed at the initial framebuffer size for now.
    extern int wfWindowWidth, wfWindowHeight;       // gfx/gl/display.cc: GL viewport + aspect
    extern int _halWindowWidth, _halWindowHeight;   // hal/linux: feeds Display _xSize/_ySize
    int fbw = 0, fbh = 0;
    glfwGetFramebufferSize(win, &fbw, &fbh);
    wfWindowWidth  = _halWindowWidth  = fbw;
    wfWindowHeight = _halWindowHeight = fbh;
    std::printf("wf-edit: engine surface size %dx%d\n", fbw, fbh);

    std::printf("wf-edit: HALStart (--editor, level=%s)\n", level.c_str());
    HALStart(hal_argc, hal_argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
    std::printf("wf-edit: HALStart returned\n");

    // 5. Engine released its references; clear the registries + tear down.
    //    Unregister the frame callback before `ctx` leaves scope so the
    //    engine's stored ctx pointer can't dangle (no callbacks fire after
    //    HALStart returns, but keep it tidy — mirrors ClearHostGLContext).
    SetEditorFrameCallback(nullptr, nullptr);
    if (!room_id.empty()) {
        collab_session.Stop();
        voice_chat.Stop();
        video_chat.Stop();
    }
    ClearHostGLContext();
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    glfwDestroyWindow(win);
    glfwTerminate();
    std::printf("wf-edit: clean exit\n");
    return 0;
}
