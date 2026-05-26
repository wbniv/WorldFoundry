//=============================================================================
// engine/wf_edit/main.cc — World Foundry collaborative level editor (wf-edit).
//
// Milestone 2: embed the engine viewport. The editor owns a GLFW X11/GLX
// window, registers that context with the engine (SetHostGLContext) and a pair
// of per-frame callbacks (SetEditorFrameCallbacks), then calls HALStart. The
// engine's PIGSMain runs in `--editor` mode → WFGame::RunEditor, which each
// iteration calls editor_build (apply edits + build UI), then
// StepFrame(do_swap=false) (renders the level into the back buffer), then
// editor_present (composite the ImGui overlay + swap). Build-before-render is
// what makes a local edit appear the same frame — see
// docs/plans/2026-05-25-wf-edit-zero-latency-local-edits.md. Approach (a) per
// docs/plans/2026-05-20-editor-app-shell.md; Linux/X11 only.
//=============================================================================

// nlohmann/json must be included before WF engine headers — memory.hp's
// operator-new macro conflicts with STL internal placement-new in <valarray>.
#include <nlohmann/json.hpp>

#define GLFW_EXPOSE_NATIVE_X11
#define GLFW_EXPOSE_NATIVE_GLX
#include <GLFW/glfw3.h>
#include <GLFW/glfw3native.h>

#include "imgui.h"
#include "imgui_internal.h"   // DockBuilder API (default panel layout)
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"
#include "ImGuizmo.h"          // viewport translate/rotate gizmo
#include "imgui_markdown.h"    // chat sidebar markdown rendering (header-only)

#include <gfx/host_gl_context.h>
#include <gfx/renderer_backend.hp>   // RendererBackendGet().SetProjection on resize
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
#include "ws_client.h"
#include "gizmo.h"

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>
#include <unistd.h>
#include <sys/stat.h>

// Provided by the engine's platform layer (mirrors the host-GL e2e harness).
extern void ParseWindowSwitches(int argc, char** argv);
extern char szAppName[];

// gfx/gl/display.cc — drive WFInitGL's glViewport + projection aspect. main()
// seeds them from the GLFW framebuffer before HALStart; editor_build re-applies
// glViewport + SetProjection from them on window resize (the engine's own
// resize path early-bails in host-owned mode).
extern int wfWindowWidth, wfWindowHeight;

namespace {

// ── Phase 6: identity persistence + wfedit:// URL ───────────────────────────

struct RecentRoom { std::string relay_url, room_id; };

struct WfeditIdentity {
    std::string peer_id;
    std::string display_name = "Editor";
    float colour[3] = {0.5f, 0.5f, 0.5f};
    std::vector<RecentRoom> recent_rooms;
    // Gizmo snap prefs (persisted across sessions).
    bool  gizmo_snap = false;
    float gizmo_snap_trans = 1.0f;
    float gizmo_snap_rot   = 15.0f;
};

static std::string IdentityPath()
{
    const char* home = std::getenv("XDG_CONFIG_HOME");
    std::string base = home ? home : (std::string(std::getenv("HOME") ?: ".") + "/.config");
    return base + "/wf-edit/identity.json";
}

static std::optional<WfeditIdentity> LoadIdentity()
{
    const std::string path = IdentityPath();
    std::ifstream f(path);
    if (!f.is_open()) return std::nullopt;
    std::string raw((std::istreambuf_iterator<char>(f)),
                     std::istreambuf_iterator<char>());
    try {
        using json = nlohmann::json;
        json j = json::parse(raw);
        WfeditIdentity id;
        id.peer_id      = j.value("peer_id", "");
        id.display_name = j.value("display_name", "Editor");
        if (j.contains("colour") && j["colour"].is_array() && j["colour"].size() >= 3) {
            id.colour[0] = j["colour"][0].get<float>();
            id.colour[1] = j["colour"][1].get<float>();
            id.colour[2] = j["colour"][2].get<float>();
        }
        if (j.contains("recent_rooms") && j["recent_rooms"].is_array()) {
            for (const auto& r : j["recent_rooms"]) {
                id.recent_rooms.push_back({r.value("relay_url",""), r.value("room_id","")});
            }
        }
        id.gizmo_snap       = j.value("gizmo_snap", false);
        id.gizmo_snap_trans = j.value("gizmo_snap_trans", 1.0f);
        id.gizmo_snap_rot   = j.value("gizmo_snap_rot", 15.0f);
        if (id.peer_id.empty()) return std::nullopt;
        return id;
    } catch (...) {
        return std::nullopt;
    }
}

static void SaveIdentity(const WfeditIdentity& id)
{
    const std::string path = IdentityPath();
    // Ensure config dir exists.
    const std::string dir = path.substr(0, path.rfind('/'));
    ::mkdir(dir.substr(0, dir.rfind('/')).c_str(), 0755);  // ~/.config/
    ::mkdir(dir.c_str(), 0755);                             // ~/.config/wf-edit/
    try {
        using json = nlohmann::json;
        json rooms = json::array();
        for (const auto& r : id.recent_rooms)
            rooms.push_back(json{{"relay_url", r.relay_url}, {"room_id", r.room_id}});
        json j{
            {"peer_id",      id.peer_id},
            {"display_name", id.display_name},
            {"colour",       json::array({id.colour[0], id.colour[1], id.colour[2]})},
            {"recent_rooms", rooms},
            {"gizmo_snap",       id.gizmo_snap},
            {"gizmo_snap_trans", id.gizmo_snap_trans},
            {"gizmo_snap_rot",   id.gizmo_snap_rot}
        };
        std::ofstream f(path);
        f << j.dump(2) << "\n";
    } catch (...) {}
}

// Parse wfedit://<host:port>/r/<room-id> → {relay_url="ws://host:port", room_id}.
static std::optional<std::pair<std::string,std::string>> ParseWfeditUrl(const char* url)
{
    static const char kPfx[] = "wfedit://";
    if (std::strncmp(url, kPfx, sizeof(kPfx) - 1) != 0) return std::nullopt;
    std::string rest = url + sizeof(kPfx) - 1;
    // Split on "/r/"
    const auto rpos = rest.find("/r/");
    if (rpos == std::string::npos) return std::nullopt;
    std::string host_port = rest.substr(0, rpos);
    std::string room = rest.substr(rpos + 3);
    if (host_port.empty() || room.empty()) return std::nullopt;
    return std::make_pair("ws://" + host_port, room);
}

// Add or move room to the front of recent_rooms (capped at 10).
static void PushRecentRoom(WfeditIdentity& id,
                            const std::string& relay_url,
                            const std::string& room_id)
{
    auto& r = id.recent_rooms;
    r.erase(std::remove_if(r.begin(), r.end(),
        [&](const RecentRoom& x){ return x.relay_url == relay_url && x.room_id == room_id; }),
        r.end());
    r.insert(r.begin(), {relay_url, room_id});
    if (r.size() > 10) r.resize(10);
}

struct EditorCtx {
    GLFWwindow* win = nullptr;
    int         max_frames = -1;   // <0 = run until the window closes
    int         frame = 0;
    const char* shot = nullptr;    // --screenshot: PPM dump on the last frame

    // Last framebuffer size we applied to the engine viewport; 0 forces the
    // first editor_build to (re-)fit. See the resize block in editor_build.
    int         fb_w = 0, fb_h = 0;

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

    // Native Ctrl+Z/Ctrl+Y: the Yrs UndoManager (owned by main(), tracking the
    // Doc's local-origin edits). Reverts whatever transactions hit the "content"
    // scope — field edits, gizmo moves, add/delete — regardless of code path.
    wfcrdt::UndoManager*          undo = nullptr;

    // Viewport gizmo: true while a drag is in progress, so the Doc leaves are
    // written once on release (not every frame — that would flood the relay).
    bool                          gizmo_active = false;

    // Gizmo operation (G = move, R = rotate, W = both) + snap (S toggles).
    // Snap steps persist in identity.json. Combined mode can't snap (ImGuizmo
    // shares one snap[0] slot between translate XYZ and rotate degrees).
    ImGuizmo::OPERATION           gizmo_op = ImGuizmo::TRANSLATE | ImGuizmo::ROTATE;
    bool                          gizmo_snap = false;
    float                         gizmo_snap_trans = 1.0f;   // world units (XYZ)
    float                         gizmo_snap_rot   = 15.0f;  // degrees

    // Save round-trip: the .lev path File→Save writes (the Doc is lossless — v2
    // schema — so save needs no retained JSON), and a transient toast.
    std::string save_path;
    // True when the Doc was loaded from a binary source (a compiled .iff or a
    // cd.iff level): the source binary is read-only, so save_path was redirected
    // to a fresh .lev and File→Save is really a Save-As. Drives the menu label.
    bool        binary_source = false;
    std::string toast;
    int         toast_frames = 0;

    // File→Open (#2): re-exec the editor into another level. A fresh process
    // re-runs the whole startup path (incl. the cd.iff picker for a bare archive),
    // so we sidestep any in-place engine/bridge reset. exe_path is argv[0] (what we
    // relaunch); show_open drives the browser modal; browse_dir is the dir it lists;
    // browse_sel is the highlighted row; pending_open holds a pick awaiting the
    // discard-changes confirm; open_pick is a headless aid that auto-opens a path.
    std::string exe_path;
    bool        show_open = false;
    std::string browse_dir;
    int         browse_sel = -1;
    std::string pending_open;
    std::string open_pick;

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

    // Co-editing relay (Phase 2+). relay_client is connected when relay_url is set.
    wfedit::WsClient                    relay_client;
    std::string                         relay_url;
    std::string                         our_peer_id;
    std::optional<wfcrdt::Subscription> relay_sub;
    bool                                suppress_relay_send = false;

    // Phase 4: presence — stable actor eids (parallel to actor_names), peer state.
    std::vector<std::string> actor_eids;
    struct PresenceState {
        std::string name;
        float colour[3] = {0.8f, 0.8f, 0.8f};
        std::string selected_eid;
        double last_seen = 0.0;   // glfwGetTime()
    };
    std::unordered_map<std::string, PresenceState> peer_presence;  // peer_id → state
    double last_presence_send = 0.0;
    float  our_colour[3] = {0.5f, 0.5f, 0.5f};   // set on relay connect from peer_id hash

    // Phase 5: chat sidebar (only visible when relay is connected).
    struct ChatEntry {
        std::string name;
        float colour[3] = {0.8f, 0.8f, 0.8f};
        std::string text;
    };
    std::vector<ChatEntry> chat_log;
    bool                   chat_demo = false;  // WF_EDIT_CHAT_DEMO: show Chat panel w/o relay
    char chat_input[256]   = {};
    bool chat_scroll_btm   = false;
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
    c->actor_eids  = wfedit::ReadActorEids(*c->doc);
    if (c->selected >= static_cast<int>(c->actor_names.size()))
        c->selected = static_cast<int>(c->actor_names.size()) - 1;
    c->fields_for = -1;          // force Properties to re-resolve on the next frame
}

// Re-sync the editor's UI after the Doc was mutated underneath us (a remote SYNC
// apply, or a native undo/redo). Re-reads the actor list and re-resolves the
// selected actor's properties so the panel shows the new values. Engine/viewport
// propagation is NOT done here — the bridge's deep observer queued every touched
// actor (any actor, not just the selected one) and DrainEngineSync flushes it at
// frame top.
void ReSyncAfterDocChange(EditorCtx* c)
{
    RefreshActorList(c);
    if (c->selected >= 0) {
        c->props = wfedit::ResolveProperties(
            wfedit::ReadActorFields(*c->doc, c->selected));
        c->fields_for = c->selected;
    }
}

void DoDelete(EditorCtx* c)
{
    if (!c->doc || c->selected < 0) return;
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
    RefreshActorList(c);
    c->selected = ni;
}

void DoAddActor(EditorCtx* c, const std::string& class_name)
{
    if (!c->doc) return;
    const int ni = wfedit::AddActor(*c->doc, class_name);
    if (ni < 0) {
        c->toast = "no .oad for " + class_name;
        c->toast_frames = 180;
        return;
    }
    RefreshActorList(c);
    c->selected = ni;
    c->fields_for = -1;
    c->structural_dirty = true;
    c->toast = "added " + class_name;
    c->toast_frames = 180;
}

// Ctrl+Z / Ctrl+Y. The native UndoManager mutates the Doc directly (its revert
// txn fires observeUpdates, so the relay broadcasts it to peers); we just re-
// sync the UI + engine and flash a toast. Runs at frame top with no live txn —
// yundo_manager_undo/redo open their own internal write txn.
void DoUndo(EditorCtx* c)
{
    if (!c->doc || !c->undo) return;
    if (c->undo->undo()) { ReSyncAfterDocChange(c); c->toast = "undo"; }
    else                   c->toast = "nothing to undo";
    c->toast_frames = 120;
}

void DoRedo(EditorCtx* c)
{
    if (!c->doc || !c->undo) return;
    if (c->undo->redo()) { ReSyncAfterDocChange(c); c->toast = "redo"; }
    else                   c->toast = "nothing to redo";
    c->toast_frames = 120;
}

// Derive a vibrant RGB colour from a peer_id string for consistent colouring.
static void PeerColourFromId(const std::string& id, float col[3])
{
    std::size_t h = std::hash<std::string>{}(id);
    // Avoid dark colours by keeping each channel in [0.45, 1.0].
    col[0] = 0.45f + 0.55f * static_cast<float>((h      ) & 0xFF) / 255.f;
    col[1] = 0.45f + 0.55f * static_cast<float>((h >>  8) & 0xFF) / 255.f;
    col[2] = 0.45f + 0.55f * static_cast<float>((h >> 16) & 0xFF) / 255.f;
}

// Drain incoming relay messages (SYNC + PRESENCE). Non-blocking; called each frame.
void CollabDrain(EditorCtx* c) {
    if (!c->relay_client.connected() || !c->doc) return;
    std::vector<uint8_t> frame;
    while (c->relay_client.poll(frame)) {
        if (frame.size() < 2) { frame.clear(); continue; }
        const uint8_t ch = frame[0];

        if (ch == 0x01) {
            // SYNC — apply remote CRDT update without echoing it back. Use the
            // remote-origin txn so peer edits never enter our undo history.
            c->suppress_relay_send = true;
            {
                auto txn = c->doc->beginRemote();
                txn.apply(wfcrdt::ByteView{frame.data() + 1, frame.size() - 1});
            }
            c->suppress_relay_send = false;
            ReSyncAfterDocChange(c);
        } else if (ch == 0x02) {
            // PRESENCE — parse JSON and update peer state.
            try {
                using json = nlohmann::json;
                json j = json::parse(frame.begin() + 1, frame.end());
                const std::string pid = j.value("peer_id", "");
                if (!pid.empty() && pid != c->our_peer_id) {
                    auto& ps = c->peer_presence[pid];
                    ps.name = j.value("name", "peer");
                    if (j.contains("colour") && j["colour"].is_array()
                        && j["colour"].size() >= 3) {
                        ps.colour[0] = j["colour"][0].get<float>();
                        ps.colour[1] = j["colour"][1].get<float>();
                        ps.colour[2] = j["colour"][2].get<float>();
                    } else {
                        PeerColourFromId(pid, ps.colour);
                    }
                    ps.selected_eid = j.value("selected_eid", "");
                    ps.last_seen    = glfwGetTime();
                }
            } catch (...) {}
        } else if (ch == 0x03) {
            // CHAT — append to log.
            try {
                using json = nlohmann::json;
                json j = json::parse(frame.begin() + 1, frame.end());
                std::string text = j.value("text", "");
                if (!text.empty()) {
                    EditorCtx::ChatEntry e;
                    e.name = j.value("name", "peer");
                    e.text = std::move(text);
                    if (j.contains("colour") && j["colour"].is_array()
                        && j["colour"].size() >= 3) {
                        e.colour[0] = j["colour"][0].get<float>();
                        e.colour[1] = j["colour"][1].get<float>();
                        e.colour[2] = j["colour"][2].get<float>();
                    } else {
                        const std::string pid = j.value("peer_id", "");
                        PeerColourFromId(pid, e.colour);
                    }
                    c->chat_log.push_back(std::move(e));
                    c->chat_scroll_btm = true;
                }
            } catch (...) {}
        }
        // CONTROL (0x04) is ignored here.
        frame.clear();
    }
    // Evict peers not seen in 8 s.
    {
        const double now = glfwGetTime();
        for (auto it = c->peer_presence.begin(); it != c->peer_presence.end();)
            it = (now - it->second.last_seen > 8.0) ? c->peer_presence.erase(it) : ++it;
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

// ── startup cd.iff level picker ──────────────────────────────────────────────
// Shown once, at launch, when the editor is given a bare multi-level cd.iff (no
// `:tag` selector). Lists the archive's levels; the user picks one to load this
// session — a *startup* choice, NOT runtime level switching (the engine/bridge
// haven't started yet). Renders pure-ImGui frames on `win` before HALStart.
// Returns the chosen FOURCC tag via `out_tag` and true; returns false if the user
// quit (window closed / Quit). `max_frames`/`shot` honour the headless harness;
// `pick_level` is a headless aid — when non-empty, auto-confirm that tag/index on
// the first rendered frame (equivalent to clicking that row + Open).
static bool RunCdIffPickerModal(GLFWwindow* win, const std::string& cd_path,
                                const std::vector<wfedit::CdIffLevel>& levels,
                                std::string* out_tag, int max_frames,
                                const char* shot, const std::string& pick_level)
{
    // Default selection: first non-SHEL level (the common "open the level"); else 0.
    int sel = 0;
    for (std::size_t i = 0; i < levels.size(); ++i)
        if (levels[i].tag != "SHEL") { sel = static_cast<int>(i); break; }

    auto resolve_pick = [&](const std::string& p) -> int {       // tag or decimal index
        for (std::size_t i = 0; i < levels.size(); ++i)
            if (levels[i].tag == p) return static_cast<int>(i);
        char* end = nullptr;
        const long v = std::strtol(p.c_str(), &end, 10);
        if (end && *end == '\0')
            for (std::size_t i = 0; i < levels.size(); ++i)
                if (levels[i].index == static_cast<int>(v)) return static_cast<int>(i);
        return -1;
    };
    auto human_size = [](long b) -> std::string {
        char buf[32];
        if (b < 1024)               std::snprintf(buf, sizeof(buf), "%ld B", b);
        else if (b < 1024 * 1024)   std::snprintf(buf, sizeof(buf), "%.1f KB", b / 1024.0);
        else                        std::snprintf(buf, sizeof(buf), "%.2f MB", b / (1024.0 * 1024.0));
        return buf;
    };

    int  frame = 0;
    bool confirmed = false, quit = false;
    for (;;) {
        if (glfwWindowShouldClose(win)) quit = true;
        glfwPollEvents();

        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        const ImGuiViewport* vp = ImGui::GetMainViewport();
        ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + vp->WorkSize.x * 0.5f,
                                       vp->WorkPos.y + vp->WorkSize.y * 0.5f),
                                ImGuiCond_Always, ImVec2(0.5f, 0.5f));
        ImGui::SetNextWindowSize(ImVec2(540, 0), ImGuiCond_Always);
        ImGui::Begin("Open Level", nullptr,
                     ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove |
                     ImGuiWindowFlags_NoCollapse);
        ImGui::TextUnformatted(("Archive:  " + cd_path).c_str());
        ImGui::Text("%zu levels in this cd.iff - pick one to open:", levels.size());
        ImGui::Separator();
        if (ImGui::BeginTable("toc", 4, ImGuiTableFlags_RowBg |
                              ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("#",      ImGuiTableColumnFlags_WidthFixed, 28.0f);
            ImGui::TableSetupColumn("Tag");
            ImGui::TableSetupColumn("Size");
            ImGui::TableSetupColumn("Offset");
            ImGui::TableHeadersRow();
            for (int i = 0; i < static_cast<int>(levels.size()); ++i) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                char label[32];
                std::snprintf(label, sizeof(label), "%d##row%d", levels[i].index, i);
                if (ImGui::Selectable(label, i == sel,
                                      ImGuiSelectableFlags_SpanAllColumns |
                                      ImGuiSelectableFlags_AllowDoubleClick))
                    sel = i;
                if (ImGui::IsItemHovered() && ImGui::IsMouseDoubleClicked(0)) { sel = i; confirmed = true; }
                ImGui::TableSetColumnIndex(1); ImGui::TextUnformatted(levels[i].tag.c_str());
                ImGui::TableSetColumnIndex(2); ImGui::TextUnformatted(human_size(levels[i].size).c_str());
                ImGui::TableSetColumnIndex(3); ImGui::Text("0x%06lx", levels[i].offset);
            }
            ImGui::EndTable();
        }
        ImGui::Separator();
        if (ImGui::Button("Open", ImVec2(120, 0))) confirmed = true;
        ImGui::SameLine();
        if (ImGui::Button("Quit", ImVec2(120, 0))) quit = true;
        ImGui::End();

        ImGui::Render();
        int fbw, fbh;
        glfwGetFramebufferSize(win, &fbw, &fbh);
        glViewport(0, 0, fbw, fbh);
        glClearColor(0.10f, 0.10f, 0.11f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        ++frame;

        // Headless auto-pick once the modal has rendered (equivalent to Open).
        if (!confirmed && !quit && !pick_level.empty()) {
            const int p = resolve_pick(pick_level);
            if (p >= 0) { sel = p; confirmed = true; }
            else {
                std::fprintf(stderr, "wf-edit: --pick-level='%s' not in archive\n", pick_level.c_str());
                quit = true;
            }
        }
        const bool frame_cap = (max_frames >= 0 && frame >= max_frames);
        if ((confirmed || quit || frame_cap) && shot) write_ppm(win, shot);   // back buffer, pre-swap
        glfwSwapBuffers(win);

        if (confirmed || quit) break;
        if (frame_cap) { quit = true; break; }   // headless, no pick → treat as quit
    }

    if (confirmed && sel >= 0 && sel < static_cast<int>(levels.size())) {
        *out_tag = levels[sel].tag;
        return true;
    }
    return false;
}

// File→Open: relaunch the editor pointed at `leveltree`, preserving the collab
// flags (and any headless --screenshot/--frames so a re-exec can still be driven
// without a window). A fresh process re-runs the whole startup path — including
// the cd.iff picker when `leveltree` is a bare multi-level archive — so we sidestep
// any in-place engine/bridge reset. execvp replaces this image; the OS reclaims the
// GL context + X resources, so no graceful teardown is needed. Returns only on
// failure (the image was not replaced).
static void ReExecWithLevel(const EditorCtx* c, const std::string& leveltree)
{
    std::vector<std::string> args = { c->exe_path, "--leveltree=" + leveltree };
    if (!c->room_id.empty())   args.push_back("--room=" + c->room_id);
    if (!c->relay_url.empty()) args.push_back("--relay=" + c->relay_url);
    if (c->shot)               { args.emplace_back("--screenshot"); args.emplace_back(c->shot); }
    if (c->max_frames >= 0)    { args.emplace_back("--frames");
                                 args.push_back(std::to_string(c->max_frames)); }
    std::vector<char*> argv;
    argv.reserve(args.size() + 1);
    for (auto& s : args) argv.push_back(const_cast<char*>(s.c_str()));
    argv.push_back(nullptr);
    std::printf("wf-edit: re-exec into %s\n", leveltree.c_str());
    std::fflush(nullptr);
    execvp(c->exe_path.c_str(), argv.data());
    std::fprintf(stderr, "wf-edit: re-exec '%s' failed: %s\n",
                 c->exe_path.c_str(), std::strerror(errno));
}

// The directory File→Open lists first: prefer wflevels/ (where shipped levels
// live), else the current working directory.
static std::string DefaultBrowseDir()
{
    std::error_code ec;
    namespace fs = std::filesystem;
    if (fs::is_directory("wflevels", ec))
        return fs::weakly_canonical("wflevels", ec).string();
    return fs::current_path(ec).string();
}

// Minimal hand-rolled ImGui file browser for File→Open (no vendored dialog). Lists
// subdirs + .iff/.lev/.lvl files under c->browse_dir; double-click a dir to descend
// (".." to go up), double-click a file or hit Open to load it. Loading re-execs into
// the pick, which discards the live Doc — so when there are undoable edits we first
// require a "discard changes?" confirm (rendered inline to avoid nested popups).
static void RunOpenBrowserModal(EditorCtx* c)
{
    namespace fs = std::filesystem;
    if (c->show_open && !ImGui::IsPopupOpen("Open Level"))
        ImGui::OpenPopup("Open Level");
    if (!ImGui::BeginPopupModal("Open Level", &c->show_open,
                                ImGuiWindowFlags_AlwaysAutoResize))
        return;

    // Inline discard-changes confirm: a pending pick is held until the user OKs
    // losing the current Doc. Replaces the browser body while it's pending.
    if (!c->pending_open.empty()) {
        ImGui::TextUnformatted("Unsaved edits in this session will be lost.");
        ImGui::TextUnformatted(("Open " + c->pending_open + " anyway?").c_str());
        ImGui::Separator();
        if (ImGui::Button("Discard & Open", ImVec2(140, 0)))
            ReExecWithLevel(c, c->pending_open);          // does not return on success
        ImGui::SameLine();
        if (ImGui::Button("Cancel", ImVec2(110, 0))) {
            c->pending_open.clear();
            c->show_open = false;
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
        return;
    }

    ImGui::TextUnformatted(("Dir:  " + c->browse_dir).c_str());
    ImGui::Separator();

    // Rebuild the listing each frame: ".." (unless at filesystem root), then dirs,
    // then level files, each group sorted. Dotfiles skipped.
    std::error_code ec;
    fs::path dir(c->browse_dir);
    std::vector<std::pair<std::string, bool>> entries;   // (name, is_dir)
    if (dir.has_parent_path() && dir != dir.root_path())
        entries.emplace_back("..", true);
    std::vector<std::string> dirs, files;
    for (const auto& e :
         fs::directory_iterator(dir, fs::directory_options::skip_permission_denied, ec)) {
        const std::string name = e.path().filename().string();
        if (name.empty() || name[0] == '.') continue;
        if (e.is_directory(ec)) { dirs.push_back(name); continue; }
        const std::string ext = e.path().extension().string();
        if (ext == ".iff" || ext == ".lev" || ext == ".lvl") files.push_back(name);
    }
    std::sort(dirs.begin(), dirs.end());
    std::sort(files.begin(), files.end());
    for (auto& d : dirs)  entries.emplace_back(d, true);
    for (auto& f : files) entries.emplace_back(f, false);

    std::string chosen;          // set when a file is double-clicked / Open pressed
    std::string descend;         // set when a dir is double-clicked
    if (ImGui::BeginListBox("##entries", ImVec2(480, 300))) {
        for (int i = 0; i < static_cast<int>(entries.size()); ++i) {
            const bool is_dir = entries[i].second;
            const std::string label =
                (is_dir ? "[dir] " : "      ") + entries[i].first + "##e" + std::to_string(i);
            if (ImGui::Selectable(label.c_str(), c->browse_sel == i,
                                  ImGuiSelectableFlags_AllowDoubleClick)) {
                c->browse_sel = i;
                if (ImGui::IsMouseDoubleClicked(0)) {
                    if (is_dir) descend = entries[i].first;
                    else        chosen  = (dir / entries[i].first).string();
                }
            }
        }
        ImGui::EndListBox();
    }

    ImGui::Separator();
    const bool file_sel = c->browse_sel >= 0 &&
                          c->browse_sel < static_cast<int>(entries.size()) &&
                          !entries[c->browse_sel].second;
    ImGui::BeginDisabled(!file_sel);
    if (ImGui::Button("Open", ImVec2(110, 0)))
        chosen = (dir / entries[c->browse_sel].first).string();
    ImGui::EndDisabled();
    ImGui::SameLine();
    if (ImGui::Button("Cancel", ImVec2(110, 0))) {
        c->show_open = false;
        ImGui::CloseCurrentPopup();
    }

    if (!descend.empty()) {
        c->browse_dir = fs::weakly_canonical(
            descend == ".." ? dir.parent_path() : dir / descend, ec).string();
        c->browse_sel = -1;
    } else if (!chosen.empty()) {
        if ((c->undo && c->undo->canUndo()) || c->structural_dirty)
            c->pending_open = chosen;                     // route through the confirm
        else
            ReExecWithLevel(c, chosen);                   // does not return on success
    }
    ImGui::EndPopup();
}

// Build phase (EditorBuildCallback): called by WFGame::RunEditor at the TOP of
// each iteration, BEFORE StepFrame. We poll input, apply any pending Doc edits
// to the live engine (the bridge drain), and build the ImGui UI — so the
// StepFrame render that follows reflects this frame's edits this frame (no
// render-ahead-of-edit latency). editor_present then composites + swaps.
// Return false to quit — always BEFORE ImGui::NewFrame so the NewFrame/Render
// pair stays balanced (present is skipped when build returns false).
bool editor_build(void* p)
{
    EditorCtx* c = static_cast<EditorCtx*>(p);
    glfwPollEvents();
    if (glfwWindowShouldClose(c->win))
        return false;
    // --frames N: stop after N frames have been presented. Checked here (before
    // NewFrame) so the quit path never opens an ImGui frame present won't close.
    if (c->max_frames >= 0 && c->frame >= c->max_frames)
        return false;

    // --open-pick=<path>: headless aid — re-exec into the path on the first build,
    // exercising the same running-editor re-exec a File→Open click would (engine is
    // already up here). Not propagated to the child, so it fires exactly once.
    if (!c->open_pick.empty()) {
        const std::string p = c->open_pick;
        c->open_pick.clear();
        ReExecWithLevel(c, p);   // does not return on success
    }

    // Follow window resize. WFInitGL set glViewport + projection ONCE from the
    // initial size and nothing re-applies them per frame (the engine's
    // ConfigureNotify path early-bails in host-owned mode), so re-fit here when
    // the framebuffer changes. ImGui's GL3 backend save/restores the viewport
    // around its draw, so this glViewport persists into the next StepFrame
    // (one-frame lag). Skip while minimized (0×0 → bad viewport / div-by-zero).
    {
        int fbw = 0, fbh = 0;
        glfwGetFramebufferSize(c->win, &fbw, &fbh);
        if (fbw > 0 && fbh > 0 && (fbw != c->fb_w || fbh != c->fb_h)) {
            c->fb_w = fbw; c->fb_h = fbh;
            wfWindowWidth = fbw; wfWindowHeight = fbh;   // keep engine globals truthful
            glViewport(0, 0, fbw, fbh);
            // Mirror WFInitGL (display.cc:283-284): FOV 60°, near 1, far 1000.
            // Constants duplicated because we must not modify the engine build.
            RendererBackendGet().SetProjection(60.0f, float(fbw) / float(fbh), 1.0f, 1000.0f);
        }
    }

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
    // level is available (theLevel non-null). No-op once initialized. Must run
    // before CollabDrain so the content + deep observers it registers are live
    // when the SYNC below fires them.
    if (c->doc) wfedit::InitBridgeMap(*c->doc);

    // Phase 2: drain incoming relay SYNC + PRESENCE messages. A SYNC fires the
    // content observer (marks a rebuild) and the deep observer (queues touched
    // actor indices), so it must precede UpdateBridgeMap + DrainEngineSync.
    CollabDrain(c);

    // Phase 3: apply pending structural changes AFTER CollabDrain, so a SYNC that
    // carries both a structural add/remove and a field edit in one commit rebuilds
    // the doc→engine map *this* frame. The rebuild forces s_resync_all, which makes
    // the field edit below re-propagate against the fresh map rather than the stale
    // pre-SYNC one (which would mistarget the shifted actor for a frame). Local
    // structural edits from last frame's Outliner UI are picked up here too.
    if (c->doc) wfedit::UpdateBridgeMap(*c->doc);

    // Flush Doc field edits (local panel, remote SYNC just applied above, undo/
    // redo, replay, DAP) into the live engine — the single propagation path. Runs
    // after UpdateBridgeMap so it reads the rebuilt doc→engine map, at frame top
    // (no live txn). While a gizmo drag is live, lock that actor's transform so a
    // concurrent remote/undo edit can't snap it back mid-gesture.
    if (c->doc) wfedit::DrainEngineSync(*c->doc, c->gizmo_active ? c->selected : -1);

    // Phase 4: broadcast own presence ~10 Hz when relay is connected.
    if (c->relay_client.connected()) {
        const double now = glfwGetTime();
        if (now - c->last_presence_send >= 0.1) {
            c->last_presence_send = now;
            const std::string sel_eid =
                (c->selected >= 0 && c->selected < static_cast<int>(c->actor_eids.size()))
                ? c->actor_eids[c->selected] : "";
            using json = nlohmann::json;
            const std::string body = json{
                {"peer_id",      c->our_peer_id},
                {"name",         "Editor"},
                {"colour",       json::array({c->our_colour[0], c->our_colour[1], c->our_colour[2]})},
                {"selected_eid", sel_eid}
            }.dump();
            std::vector<uint8_t> msg;
            msg.reserve(1 + body.size());
            msg.push_back(0x02);   // PRESENCE channel
            msg.insert(msg.end(), body.begin(), body.end());
            c->relay_client.send(msg.data(), msg.size());
        }
    }

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
    // Deep-observer regression proof (WF_EDIT_REMOTE_TEST="<docB>|<x y z>"): with
    // actor A selected (--select), apply a REMOTE-origin Position edit to a
    // DIFFERENT actor B and confirm it moves in the engine purely via the deep
    // observer (no direct PropagateToEngine). The pre-fix bridge only re-synced
    // the selected actor, so B would not move. See docs/plans/2026-05-25-observe-deep-bridge.md.
    static bool s_remote_tested = false;
    if (!s_remote_tested && c->doc && c->selected >= 0) {
        if (const char* spec = std::getenv("WF_EDIT_REMOTE_TEST"); spec && *spec) {
            s_remote_tested = true;
            std::string s = spec;
            if (auto bar = s.find('|'); bar != std::string::npos)
                wfedit::RunRemoteSyncTest(*c->doc, c->selected,
                                          std::atoi(s.substr(0, bar).c_str()),
                                          s.substr(bar + 1));
        }
    }
    // Active-drag transform-lock proof (WF_EDIT_DRAGLOCK_TEST=1): runs the
    // finding-#2 regression check on the selected actor. See engine_bridge.h.
    static bool s_draglock_tested = false;
    if (!s_draglock_tested && c->doc && c->selected >= 0) {
        if (const char* spec = std::getenv("WF_EDIT_DRAGLOCK_TEST"); spec && *spec) {
            s_draglock_tested = true;
            wfedit::RunDragLockTest(*c->doc, c->selected);
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
    // Add-actor UI screenshot proof: WF_EDIT_ADD_UI=<class> calls DoAddActor once
    // so --screenshot captures the new row selected + "added <class>" toast.
    static bool s_add_ui = false;
    if (!s_add_ui && c->doc) {
        if (const char* p = std::getenv("WF_EDIT_ADD_UI"); p && *p) {
            s_add_ui = true;
            DoAddActor(c, p);
        }
    }
    // Chat-markdown screenshot proof: WF_EDIT_CHAT_DEMO=1 seeds sample markdown
    // messages and forces the Chat panel visible (no relay needed) so
    // --screenshot captures rendered markdown.
    static bool s_chat_demo = false;
    if (!s_chat_demo && std::getenv("WF_EDIT_CHAT_DEMO")) {
        s_chat_demo = true;
        c->chat_demo = true;
        auto push = [&](const char* who, float r, float g, float b, const char* md) {
            EditorCtx::ChatEntry e;
            e.name = who;
            e.colour[0] = r; e.colour[1] = g; e.colour[2] = b;
            e.text = md;
            c->chat_log.push_back(std::move(e));
        };
        push("Ada", 0.4f, 0.8f, 1.0f,
             "# Heads up\nMoved the **House** to `(7, 0, 0)` — check the _Outliner_.\n\n"
             "- bumped Mass\n- re-anchored\n\nSee [docs](http://wf/x).");
        push("Me", 0.6f, 1.0f, 0.6f,
             "Nice, that **fixes** the clip. Hit `Ctrl+Z` if it drifts.");
        c->chat_scroll_btm = true;
    }
    // Undo-UI screenshot proof: WF_EDIT_UNDO_UI=dup|del|field performs one edit
    // then one DoUndo via the UI path, so the screenshot shows the Outliner /
    // Properties + "undo" toast back in the pre-edit state. (field edits the
    // first field's DATA, then undoes it.)
    static bool s_undo_ui = false;
    if (!s_undo_ui && c->doc && c->selected >= 0 && c->undo) {
        if (const char* p = std::getenv("WF_EDIT_UNDO_UI"); p && *p) {
            s_undo_ui = true;
            const std::string op = p;
            if (op == "dup")      DoDuplicate(c);
            else if (op == "del") DoDelete(c);
            else if (op == "field") {
                auto fields = wfedit::ReadActorFields(*c->doc, c->selected);
                if (!fields.empty())
                    wfedit::WriteFieldLeaf(*c->doc, c->selected,
                                           fields.front().child_index, "DATA", "999");
            }
            c->undo->stopCapturing();   // ensure the edit is its own undo step
            DoUndo(c);
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
    ImGuizmo::BeginFrame();

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
            if (ImGui::MenuItem("Open Level…", "Ctrl+O")) {
                if (c->browse_dir.empty()) c->browse_dir = DefaultBrowseDir();
                c->browse_sel = -1;
                c->pending_open.clear();
                c->show_open = true;
            }
            ImGui::Separator();
            // A binary-loaded session is read-only at the source, so Save writes a
            // fresh .lev (save_path was redirected) — label it Save As to match.
            if (ImGui::MenuItem(c->binary_source ? "Save As .lev" : "Save Level", "Ctrl+S"))
                DoSave(c);
            if (c->binary_source && ImGui::IsItemHovered())
                ImGui::SetTooltip("Source binary is read-only; writes a new .lev (%s)",
                                  c->save_path.c_str());
            if (ImGui::MenuItem("Save + Compile (.iff)")) SaveAndCompile(c);
            ImGui::MenuItem("Publish to .blend", nullptr, false, false);   // later: hand off to wf.import_level
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Edit")) {
            // Greyed out when the corresponding stack is empty.
            if (ImGui::MenuItem("Undo", "Ctrl+Z", false, c->undo && c->undo->canUndo()))
                DoUndo(c);
            if (ImGui::MenuItem("Redo", "Ctrl+Y", false, c->undo && c->undo->canRedo()))
                DoRedo(c);
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

    // File→Open browser (renders only while c->show_open). Driven by the menu item,
    // Ctrl+O, or --open / --open-pick at startup.
    RunOpenBrowserModal(c);

    // Keyboard shortcuts (when no text widget is capturing the keypress).
    const bool typing = ImGui::GetIO().WantTextInput;
    if (!typing && ImGui::GetIO().KeyCtrl && ImGui::IsKeyPressed(ImGuiKey_S, false))
        DoSave(c);
    if (!typing && ImGui::GetIO().KeyCtrl && ImGui::IsKeyPressed(ImGuiKey_O, false)) {
        if (c->browse_dir.empty()) c->browse_dir = DefaultBrowseDir();
        c->browse_sel = -1;
        c->pending_open.clear();
        c->show_open = true;
    }
    if (!typing && c->selected >= 0 && ImGui::IsKeyPressed(ImGuiKey_Delete, false))
        DoDelete(c);
    // Ctrl+Z = undo; Ctrl+Shift+Z and Ctrl+Y = redo. Gate plain-Z on !Shift so a
    // single Ctrl+Shift+Z press can't trip both branches.
    {
        ImGuiIO& io = ImGui::GetIO();
        if (!typing && io.KeyCtrl && !io.KeyShift && ImGui::IsKeyPressed(ImGuiKey_Z, false))
            DoUndo(c);
        if (!typing && io.KeyCtrl && (ImGui::IsKeyPressed(ImGuiKey_Y, false)
                || (io.KeyShift && ImGui::IsKeyPressed(ImGuiKey_Z, false))))
            DoRedo(c);
    }
    // Gizmo mode (Blender-style): G = move-only, R = rotate-only, pressing the
    // active key again or W returns to combined; S (no Ctrl — Ctrl+S is Save)
    // toggles snap. All gated on !typing so text fields keep their keystrokes.
    // Gated on c->selected >= 0 (like Delete): the gizmo isn't rendered without
    // a selection, so none of these keys should act — notably S, which otherwise
    // toggles gizmo_snap into identity.json while nothing is selected.
    if (!typing && !ImGui::GetIO().KeyCtrl && c->selected >= 0) {
        const ImGuizmo::OPERATION both = ImGuizmo::TRANSLATE | ImGuizmo::ROTATE;
        if (ImGui::IsKeyPressed(ImGuiKey_G, false))
            c->gizmo_op = (c->gizmo_op == ImGuizmo::TRANSLATE) ? both : ImGuizmo::TRANSLATE;
        if (ImGui::IsKeyPressed(ImGuiKey_R, false))
            c->gizmo_op = (c->gizmo_op == ImGuizmo::ROTATE) ? both : ImGuizmo::ROTATE;
        if (ImGui::IsKeyPressed(ImGuiKey_W, false))
            c->gizmo_op = both;
        if (ImGui::IsKeyPressed(ImGuiKey_S, false))
            c->gizmo_snap = !c->gizmo_snap;
    }

    ImGui::Begin("Outliner");
    ImGui::Text("%s: %zu actors", c->level_name.c_str(), c->actor_names.size());
    ImGui::TextDisabled("(read from the Y.Doc)");
    // Add/delete actors (structural; persists on save). Duplicate clones the
    // selected actor; Delete removes it (or the Del key). Add… inserts a new
    // actor of a user-chosen class populated from OAD defaults.
    ImGui::BeginDisabled(c->selected < 0);
    if (ImGui::SmallButton("Duplicate")) DoDuplicate(c);
    ImGui::SameLine();
    if (ImGui::SmallButton("Delete"))    DoDelete(c);
    ImGui::EndDisabled();
    ImGui::SameLine();
    if (ImGui::SmallButton("Add..."))    ImGui::OpenPopup("add_actor");

    // Class-picker popup for "Add..."
    static const char* kClasses[] = {
        "NullObject", "actbox", "actboxor", "alias", "camera", "camshot",
        "destroyer", "director", "disabled", "enemy", "explode", "generator",
        "gold", "levelobj", "light", "matte", "missile", "platform", "player",
        "room", "shadow", "shield", "spike", "statplat", "target", "tool", "warp"
    };
    static const int kClassCount = static_cast<int>(sizeof(kClasses) / sizeof(kClasses[0]));
    static std::string s_add_class = "statplat";
    if (ImGui::BeginPopup("add_actor")) {
        ImGui::Text("Class:");
        if (ImGui::BeginCombo("##add_class", s_add_class.c_str())) {
            for (int k = 0; k < kClassCount; ++k) {
                bool sel = (s_add_class == kClasses[k]);
                if (ImGui::Selectable(kClasses[k], sel)) s_add_class = kClasses[k];
                if (sel) ImGui::SetItemDefaultFocus();
            }
            ImGui::EndCombo();
        }
        if (ImGui::Button("Add")) {
            DoAddActor(c, s_add_class);
            ImGui::CloseCurrentPopup();
        }
        ImGui::SameLine();
        if (ImGui::Button("Cancel")) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (c->structural_dirty) {
        ImGui::SameLine();
        ImGui::TextDisabled("(reload for live preview)");
    }
    ImGui::Separator();
    ImDrawList* dl = ImGui::GetWindowDrawList();
    for (int i = 0; i < static_cast<int>(c->actor_names.size()); ++i) {
        const std::string& eid = (i < static_cast<int>(c->actor_eids.size()))
                                 ? c->actor_eids[i] : "";
        // Find any peer that has this actor selected.
        const EditorCtx::PresenceState* peer_sel = nullptr;
        if (!eid.empty()) {
            for (const auto& [pid, ps] : c->peer_presence)
                if (ps.selected_eid == eid) { peer_sel = &ps; break; }
        }
        if (ImGui::Selectable(c->actor_names[i].c_str(), c->selected == i))
            c->selected = i;
        if (peer_sel) {
            // Draw a small coloured dot in the right margin of the row.
            const ImVec2 rmin = ImGui::GetItemRectMin();
            const ImVec2 rmax = ImGui::GetItemRectMax();
            const float r = (rmax.y - rmin.y) * 0.28f;
            dl->AddCircleFilled(
                ImVec2(rmax.x - r - 2.f, (rmin.y + rmax.y) * 0.5f), r,
                IM_COL32(static_cast<int>(peer_sel->colour[0] * 255),
                         static_cast<int>(peer_sel->colour[1] * 255),
                         static_cast<int>(peer_sel->colour[2] * 255), 220));
        }
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
        // edits commit to the Doc leaf. The commit fires the bridge's deep
        // observer, which queues the edit for DrainEngineSync at the next frame
        // top (see InitBridgeMap / DrainEngineSync) — the SINGLE propagation path,
        // so a local edit reaches the viewport the same way a remote one does. No
        // direct PropagateToEngine call here anymore.
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

    // ── Gizmo toolbar overlay (mode + snap) ──────────────────────────────────
    // Pinned to the top-left of the viewport; mirrors the G/R/W/S keys. Runs
    // before the gizmo below so a click updates the mode the same frame.
    if (c->selected >= 0) {
        ImGuiDockNode* cn = ImGui::DockBuilderGetCentralNode(dock_id);
        const ImVec2 cp = cn ? cn->Pos : ImGui::GetMainViewport()->WorkPos;
        ImGui::SetNextWindowPos(ImVec2(cp.x + 8, cp.y + 8), ImGuiCond_Always);
        ImGui::SetNextWindowBgAlpha(0.55f);
        const ImGuizmo::OPERATION both = ImGuizmo::TRANSLATE | ImGuizmo::ROTATE;
        if (ImGui::Begin("##gizmo_toolbar", nullptr,
                ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize |
                ImGuiWindowFlags_NoDocking | ImGuiWindowFlags_NoNav |
                ImGuiWindowFlags_NoFocusOnAppearing)) {
            if (ImGui::RadioButton("Move (G)", c->gizmo_op == ImGuizmo::TRANSLATE))
                c->gizmo_op = ImGuizmo::TRANSLATE;
            ImGui::SameLine();
            if (ImGui::RadioButton("Rotate (R)", c->gizmo_op == ImGuizmo::ROTATE))
                c->gizmo_op = ImGuizmo::ROTATE;
            ImGui::SameLine();
            if (ImGui::RadioButton("Both (W)", c->gizmo_op == both))
                c->gizmo_op = both;
            ImGui::SameLine(); ImGui::TextDisabled("|"); ImGui::SameLine();
            ImGui::Checkbox("Snap (S)", &c->gizmo_snap);
            if (c->gizmo_snap && c->gizmo_op == both)
                { ImGui::SameLine(); ImGui::TextDisabled("(pick Move/Rotate to snap)"); }
            else if (c->gizmo_snap) {
                ImGui::SameLine(); ImGui::SetNextItemWidth(64);
                if (c->gizmo_op == ImGuizmo::ROTATE) {
                    ImGui::InputFloat("deg", &c->gizmo_snap_rot, 0.0f, 0.0f, "%.0f");
                    if (c->gizmo_snap_rot < 1.0f) c->gizmo_snap_rot = 1.0f;
                } else {
                    ImGui::InputFloat("units", &c->gizmo_snap_trans, 0.0f, 0.0f, "%.2f");
                    if (c->gizmo_snap_trans < 0.01f) c->gizmo_snap_trans = 0.01f;
                }
            }
        }
        ImGui::End();
    }

    // ── Viewport translate/rotate gizmo ──────────────────────────────────────
    // Drag the selected actor directly in the 3D view. Live preview moves the
    // engine actor each frame (wfmut, no Doc write); the Doc Position/Orientation
    // leaves are written ONCE on release — writing every drag frame would emit a
    // relay SYNC per frame (observeUpdates fires on every Doc commit). The gizmo
    // is fed the engine's exact view+proj so it projects onto the live actor.
    // DocActorToEngineIdx + BuildGizmoMats both no-op safely when there's no live
    // level/camera, so no theLevel reference is needed here.
    {
        const int eidx = (c->selected >= 0 && !c->structural_dirty)
                       ? wfedit::DocActorToEngineIdx(c->selected) : 0;
        if (eidx > 0) {
            wfedit::GizmoMats m =
                wfedit::BuildGizmoMats(eidx, float(c->fb_w), float(c->fb_h));
            if (m.valid) {
                ImGuizmo::SetOrthographic(false);
                ImGuizmo::SetDrawlist(ImGui::GetForegroundDrawList());
                ImGuiDockNode* central = ImGui::DockBuilderGetCentralNode(dock_id);
                const ImVec2 rp = central ? central->Pos  : ImGui::GetMainViewport()->WorkPos;
                const ImVec2 rs = central ? central->Size : ImGui::GetMainViewport()->WorkSize;
                ImGuizmo::SetRect(rp.x, rp.y, rs.x, rs.y);

                // Snap only in a pure mode — ImGuizmo has one snap[0] slot it
                // reads as XYZ for translate and degrees for rotate, so combined
                // mode can't snap both correctly; pass null there.
                float snap_arr[3];
                const float* snap = nullptr;
                if (c->gizmo_snap && c->gizmo_op == ImGuizmo::TRANSLATE) {
                    snap_arr[0] = snap_arr[1] = snap_arr[2] = c->gizmo_snap_trans;
                    snap = snap_arr;
                } else if (c->gizmo_snap && c->gizmo_op == ImGuizmo::ROTATE) {
                    snap_arr[0] = c->gizmo_snap_rot;
                    snap = snap_arr;
                }
                ImGuizmo::Manipulate(m.view, m.proj, c->gizmo_op, ImGuizmo::WORLD,
                                     m.model, nullptr, snap);

                if (ImGuizmo::IsUsing()) {
                    wfedit::ApplyGizmoToEngine(eidx, m.model);   // live preview
                    c->gizmo_active = true;
                } else if (c->gizmo_active) {
                    // Drag released: persist + sync once, refresh the panel cache
                    // so the Position/Orientation widgets reflect the new pose.
                    c->gizmo_active = false;
                    if (c->doc) {
                        wfedit::CommitGizmoToDoc(*c->doc, c->selected, m.model);
                        c->props = wfedit::ResolveProperties(
                            wfedit::ReadActorFields(*c->doc, c->selected));
                        c->fields_for = c->selected;
                    }
                }
            }
        } else if (c->gizmo_active) {
            c->gizmo_active = false;   // selection/level lost mid-drag — drop cleanly
        }
    }

    // Collaborators panel (voice + video; only when a room is active).
    if (c->collab)
        wfedit::RenderCollabPanel(c->show_collab, *c->collab,
                                  *c->voice, *c->video, c->room_id);

    // Chat panel (when a relay is connected, or forced by WF_EDIT_CHAT_DEMO).
    if (c->relay_client.connected() || c->chat_demo) {
        if (c->chat_demo) {
            // Demo/screenshot: float it over the viewport so the capture shows it
            // (normally it's docked once the user drags it into the layout).
            const ImVec2 wp = ImGui::GetMainViewport()->WorkPos;
            const ImVec2 ws = ImGui::GetMainViewport()->WorkSize;
            ImGui::SetNextWindowPos(ImVec2(wp.x + ws.x * 0.30f, wp.y + ws.y * 0.30f),
                                    ImGuiCond_Always);
            ImGui::SetNextWindowSize(ImVec2(ws.x * 0.40f, ws.y * 0.45f), ImGuiCond_Always);
            ImGui::SetNextWindowFocus();
        }
        ImGui::Begin("Chat");
        // Peer presence list above history.
        if (!c->peer_presence.empty()) {
            for (const auto& [pid, ps] : c->peer_presence)
                ImGui::TextColored(
                    ImVec4(ps.colour[0], ps.colour[1], ps.colour[2], 1.f),
                    "● %s", ps.name.c_str());
            ImGui::Separator();
        }
        // Scrollable message history.
        const float reserve = ImGui::GetFrameHeightWithSpacing() + 4;
        ImGui::BeginChild("##chat_hist", ImVec2(0, -reserve), false);
        // Body rendered as Markdown (bold/italic/headings/lists/links). The wire
        // format stays plaintext — rendering is client-side at display time. The
        // default MarkdownConfig is exactly what we want: default font + heading
        // separators, and NULL-safe (inert) link clicks. Name stays on its own
        // line; markdown is block-level so the body renders below it.
        static ImGui::MarkdownConfig s_md;
        for (size_t i = 0; i < c->chat_log.size(); ++i) {
            const auto& e = c->chat_log[i];
            ImGui::PushID(static_cast<int>(i));
            ImGui::TextColored(ImVec4(e.colour[0], e.colour[1], e.colour[2], 1.f),
                               "%s:", e.name.c_str());
            ImGui::Markdown(e.text.c_str(), e.text.size(), s_md);
            ImGui::PopID();
        }
        if (c->chat_scroll_btm) {
            ImGui::SetScrollHereY(1.0f);
            c->chat_scroll_btm = false;
        }
        ImGui::EndChild();
        // Input row.
        ImGui::SetNextItemWidth(-70);
        const bool send = ImGui::InputText("##chat_in", c->chat_input,
                                           sizeof(c->chat_input),
                                           ImGuiInputTextFlags_EnterReturnsTrue);
        ImGui::SameLine();
        if ((send || ImGui::Button("Send")) && c->chat_input[0]) {
            EditorCtx::ChatEntry mine;
            mine.name = "Me";
            std::copy(c->our_colour, c->our_colour + 3, mine.colour);
            mine.text = c->chat_input;
            c->chat_log.push_back(mine);
            c->chat_scroll_btm = true;

            using json = nlohmann::json;
            std::string body = json{
                {"peer_id", c->our_peer_id},
                {"name",    "Editor"},
                {"colour",  json::array({c->our_colour[0], c->our_colour[1], c->our_colour[2]})},
                {"text",    mine.text}
            }.dump();
            std::vector<uint8_t> msg;
            msg.push_back(0x03);
            msg.insert(msg.end(), body.begin(), body.end());
            c->relay_client.send(msg.data(), msg.size());
            c->chat_input[0] = '\0';
        }
        ImGui::End();
    }

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

    // Build done. RunEditor calls StepFrame next (renders the scene with this
    // frame's edits applied), then editor_present composites this ImGui frame on
    // top and swaps.
    return true;
}

// Present phase (EditorPresentCallback): composite the ImGui overlay built in
// editor_build onto the scene StepFrame just rendered, capture --screenshot if
// due, and swap. Called only when editor_build returned true, so the ImGui
// NewFrame/Render pair is always balanced.
void editor_present(void* p)
{
    EditorCtx* c = static_cast<EditorCtx*>(p);

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
    std::string ctx_relay_url;     // --relay=<ws://...>: connect to co-edit relay
    std::string pick_level;        // --pick-level=<tag|index>: headless aid — auto-confirm the cd.iff picker
    bool        open_at_start = false;  // --open: show the File→Open browser at startup
    std::string open_pick;         // --open-pick=<path>: headless aid — re-exec into <path> on first frame
    // Viewport level (engine LoadLevel) + the .lev parsed into the read-only
    // Y.Doc. Default both to the BLENDER-built snowgoons so the viewport and
    // Outliner show the same source — and so File→"Save + Compile (.iff)"
    // (build_level_binary.sh) regenerates exactly the standalone the viewport
    // loads. (The byte-oracle snowgoons-standalone.iff is kept for the
    // engine-stability smoke tests; it is NOT what the editor edits.)
    std::string level     = "wflevels/snowgoons-blender-standalone.iff";
    std::string leveltree = "wflevels/snowgoons-blender/snowgoons-blender.lev";
    bool        level_explicit = false;   // --level= given → don't auto-track the viewport
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--frames") == 0 && i + 1 < argc)
            max_frames = std::atoi(argv[++i]);
        else if (std::strcmp(argv[i], "--screenshot") == 0 && i + 1 < argc)
            shot = argv[++i];
        else if (std::strncmp(argv[i], "--level=", 8) == 0)
            { level = argv[i] + 8; level_explicit = true; }
        else if (std::strncmp(argv[i], "--leveltree=", 12) == 0)
            leveltree = argv[i] + 12;
        else if (std::strncmp(argv[i], "--select=", 9) == 0)
            preselect = std::atoi(argv[i] + 9);
        else if (std::strncmp(argv[i], "--pick-level=", 13) == 0)
            pick_level = argv[i] + 13;
        else if (std::strcmp(argv[i], "--open") == 0)
            open_at_start = true;
        else if (std::strncmp(argv[i], "--open-pick=", 12) == 0)
            open_pick = argv[i] + 12;
        else if (std::strncmp(argv[i], "--room=", 7) == 0)
            room_id = argv[i] + 7;
        else if (std::strcmp(argv[i], "--room") == 0 && i + 1 < argc)
            room_id = argv[++i];
        else if (std::strncmp(argv[i], "--relay=", 8) == 0)
            ctx_relay_url = argv[i] + 8;
        else if (std::strcmp(argv[i], "--relay") == 0 && i + 1 < argc)
            ctx_relay_url = argv[++i];
        else if (std::strncmp(argv[i], "--url=", 6) == 0) {
            if (auto parsed = ParseWfeditUrl(argv[i] + 6)) {
                ctx_relay_url = parsed->first;
                room_id       = parsed->second;
            } else {
                std::fprintf(stderr, "wf-edit: invalid --url (expected wfedit://host:port/r/room)\n");
            }
        }
    }

    // Phase 6: load persisted identity (peer_id, colour, recent rooms).
    WfeditIdentity identity;
    if (auto loaded = LoadIdentity()) {
        identity = *loaded;
        std::printf("wf-edit: loaded identity peer_id=%.8s… from %s\n",
                    identity.peer_id.c_str(), IdentityPath().c_str());
    } else {
        // No identity yet — peer_id will be assigned at relay-connect time.
    }

    // 0. Read-only Y.Doc (M4): shell out to `levtree parse`, build a wfcrdt::Doc
    //    in the editor CRDT schema, and read the actor names back out of it for
    //    the Outliner. CPU-only; done before any GL. The Doc is held for the
    //    program lifetime (read-only here; the CRDT→engine bridge is the next
    //    plan). A failure here is non-fatal — the shell still runs.
    wfcrdt::Doc              doc;
    std::string              level_name;
    std::string              save_path;   // where Save writes (.lev in-place, or Save-As for a binary load)
    std::vector<std::string> actor_names;
    std::vector<std::string> actor_eids;

    // A bare multi-level cd.iff (no `:tag` selector) defers its load to the
    // startup picker (run below, after the window/ImGui exist) — the picker needs
    // a GL window, which must stay AFTER the pre-window headless hooks. So load
    // early only for an unambiguous source (text .lev / bare .iff / explicit
    // cd.iff:tag); the picker case loads after the modal resolves a tag.
    const bool show_picker = wfedit::NeedsLevelPicker(leveltree);

    // Reused by both load sites (early below, and the picker block) to fill the
    // Outliner state from a populated Doc and seed the save path.
    auto finish_doc_load = [&]() {
        actor_names = wfedit::ReadActorNames(doc);
        actor_eids  = wfedit::ReadActorEids(doc);
        // Display name = the Save target's basename (clean for a binary load:
        // cd.iff:L4 → cd_L4.lev; matches the source .lev for a text load).
        level_name  = save_path;
        if (auto slash = level_name.find_last_of('/'); slash != std::string::npos)
            level_name.erase(0, slash + 1);
        std::printf("wf-edit: Outliner shows %zu actors from the Y.Doc\n",
                    actor_names.size());
    };

    if (!show_picker) {
        if (wfedit::LoadLevelTreeIntoDoc(leveltree, doc, &save_path))
            finish_doc_load();
        else
            std::fprintf(stderr, "wf-edit: Y.Doc population failed for %s "
                                 "(Outliner will be empty)\n", leveltree.c_str());
    }

    // Native undo/redo — addScope runs AFTER the level is populated so the load
    // isn't itself an undo step. The UndoManager binds the Doc here; for the
    // early-load path we register the "content" scope now, for the picker path we
    // register it after the deferred load (below). Tracks the actor array so every
    // Doc::begin() edit (panel / gizmo / add / delete) is reversible; remote
    // applies (Doc::beginRemote) stay out of history. Held for the program lifetime.
    wfcrdt::UndoManager undo(doc);
    if (!show_picker) { auto txn = doc.begin(); undo.addScope(txn.array("content")); }

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

    // 0b2b. Headless add-actor proof (env-gated): WF_EDIT_ADD_TEST=<class> inserts
    //       a new actor of that class and asserts actor count +1, Class Name correct,
    //       and field count > 4 (OAD defaults populated). CPU-only, pre-GL.
    //       Honors WF_EDIT_SAVE if also set (falls through); otherwise exits.
    if (const char* cls = std::getenv("WF_EDIT_ADD_TEST"); cls && *cls) {
        const int before = static_cast<int>(wfedit::ReadActorNames(doc).size());
        const int ni = wfedit::AddActor(doc, cls);
        const int after = static_cast<int>(wfedit::ReadActorNames(doc).size());
        std::string got_class;
        int field_count = 0;
        if (ni >= 0) {
            for (const auto& f : wfedit::ReadActorFields(doc, ni)) {
                ++field_count;
                if (f.name == "Class Name")
                    got_class = !f.data.empty() ? f.data : f.label;
            }
        }
        const bool pass = (ni >= 0) && (after == before + 1) &&
                          (got_class == cls) && (field_count > 4);
        std::fprintf(stderr, "[add] class=%s  %d -> %d actors (ni=%d fields=%d class='%s') %s\n",
                     cls, before, after, ni, field_count, got_class.c_str(),
                     pass ? "PASS" : "FAIL");
        if (!pass) return 1;
        if (!std::getenv("WF_EDIT_SAVE")) return 0;
    }

    // 0b3. Headless undo/redo proof (env-gated): WF_EDIT_UNDO_TEST drives a ';'-
    //      separated step list against the native UndoManager + Doc, asserting the
    //      Doc's observable state (actor count + the --select'd actor's field
    //      label:data) returns to the recorded checkpoint after each undo/redo.
    //      Steps: field:<Name>|<LEAF>|<value> | dup:<idx> | del:<idx> | undo | redo.
    //      e.g. WF_EDIT_UNDO_TEST="field:Mass|DATA|2.5;undo;redo;dup:0;undo;del:1;undo"
    //      Prints "[undo] all PASS" and exits — CPU-only, pre-GL (mirrors WF_EDIT_SAVE).
    if (const char* spec = std::getenv("WF_EDIT_UNDO_TEST"); spec && *spec) {
        undo.clear();   // start from a clean stack regardless of prior test edits
        // Observable signature: actor count + the preselect actor's fields.
        auto sig = [&]() -> std::string {
            auto names = wfedit::ReadActorNames(doc);
            std::string s = std::to_string(names.size());
            if (preselect >= 0 && preselect < static_cast<int>(names.size()))
                for (auto& f : wfedit::ReadActorFields(doc, preselect))
                    s += "|" + f.name + "=" + f.label + ":" + f.data;
            return s;
        };
        std::vector<std::string> hist = { sig() };   // hist[cursor] == current state
        int  cursor = 0;
        bool pass   = true;
        auto fail = [&](const std::string& m) {
            pass = false; std::fprintf(stderr, "[undo] FAIL: %s\n", m.c_str());
        };
        auto record = [&]() { hist.resize(cursor + 1); hist.push_back(sig()); ++cursor; };

        std::string all = spec;
        for (std::size_t pos = 0; pos < all.size() + 1; ) {
            std::size_t semi = all.find(';', pos);
            std::string step = all.substr(pos, semi == std::string::npos ? std::string::npos : semi - pos);
            pos = (semi == std::string::npos) ? all.size() + 1 : semi + 1;
            if (step.empty()) continue;

            if (step.rfind("field:", 0) == 0) {
                std::string body = step.substr(6);
                auto a = body.find('|'), b = body.rfind('|');
                if (a == std::string::npos || b <= a) { fail("bad field step: " + step); continue; }
                std::string fname = body.substr(0, a),
                            leaf  = body.substr(a + 1, b - a - 1),
                            value = body.substr(b + 1);
                int ci = -1;
                for (auto& f : wfedit::ReadActorFields(doc, preselect))
                    if (f.name == fname) { ci = f.child_index; break; }
                if (ci < 0) { fail("field not found: " + fname); continue; }
                wfedit::WriteFieldLeaf(doc, preselect, ci, leaf.c_str(), value);
                undo.stopCapturing();   // discrete undo step
                record();
                std::fprintf(stderr, "[undo] field %s.%s='%s' -> step %d\n",
                             fname.c_str(), leaf.c_str(), value.c_str(), cursor);
            } else if (step.rfind("dup:", 0) == 0) {
                wfedit::DuplicateActor(doc, std::atoi(step.substr(4).c_str()));
                undo.stopCapturing(); record();
                std::fprintf(stderr, "[undo] dup -> %s\n", sig().c_str());
            } else if (step.rfind("del:", 0) == 0) {
                wfedit::DeleteActor(doc, std::atoi(step.substr(4).c_str()));
                undo.stopCapturing(); record();
                std::fprintf(stderr, "[undo] del -> %s\n", sig().c_str());
            } else if (step == "undo") {
                const bool had = cursor > 0;
                const bool ok  = undo.undo();
                if (had  && !ok) fail("undo() false with a non-empty stack");
                if (!had &&  ok) fail("undo() true on an empty stack");
                if (had) --cursor;
                if (sig() != hist[cursor]) fail("state mismatch after undo (cursor " + std::to_string(cursor) + ")");
                std::fprintf(stderr, "[undo] undo -> cursor %d %s\n", cursor, ok ? "(ok)" : "(noop)");
            } else if (step == "redo") {
                const bool had = cursor < static_cast<int>(hist.size()) - 1;
                const bool ok  = undo.redo();
                if (had  && !ok) fail("redo() false with a redoable step");
                if (!had &&  ok) fail("redo() true with nothing to redo");
                if (had) ++cursor;
                if (sig() != hist[cursor]) fail("state mismatch after redo (cursor " + std::to_string(cursor) + ")");
                std::fprintf(stderr, "[undo] redo -> cursor %d %s\n", cursor, ok ? "(ok)" : "(noop)");
            } else {
                fail("unknown step: " + step);
            }
        }
        std::fprintf(stderr, pass ? "[undo] all PASS\n" : "[undo] FAILED\n");
        return pass ? 0 : 1;
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

    // 2b. Startup cd.iff level picker. When launched on a bare multi-level archive
    //     (no `:tag` selector), show the modal now — the window + ImGui exist but
    //     the engine hasn't started — and load the chosen level into the Doc. This
    //     is a startup pick, not runtime switching: nothing is loaded yet, so the
    //     bridge/engine come up against the picked level like any other launch.
    if (show_picker) {
        // NeedsLevelPicker was true ⇒ no valid `:tag` selector ⇒ leveltree is the
        // bare cd.iff archive path.
        const std::string& base = leveltree;
        const std::vector<wfedit::CdIffLevel> levels = wfedit::ListCdIffLevels(base);
        std::string tag;
        if (RunCdIffPickerModal(win, base, levels, &tag, max_frames, shot, pick_level)) {
            std::printf("wf-edit: picker selected %s from %s\n", tag.c_str(), base.c_str());
            leveltree = base + ":" + tag;
            if (wfedit::LoadLevelTreeIntoDoc(leveltree, doc, &save_path)) {
                finish_doc_load();
                auto txn = doc.begin();
                undo.addScope(txn.array("content"));   // track AFTER the deferred load
            } else {
                std::fprintf(stderr, "wf-edit: Y.Doc population failed for %s\n", leveltree.c_str());
            }
        } else {
            // Quit / window closed with no selection — exit cleanly (no empty session).
            std::printf("wf-edit: level picker dismissed — nothing selected, exiting\n");
            ImGui_ImplOpenGL3_Shutdown();
            ImGui_ImplGlfw_Shutdown();
            ImGui::DestroyContext();
            glfwDestroyWindow(win);
            glfwTerminate();
            return 0;
        }
    }

    // 2c. Viewport tracks the (now-final) Doc level: when the Doc was sourced from
    //     a binary level, point the engine's -L at the same level so the 3D
    //     viewport matches the Outliner/Properties. A bare .iff is itself an L<N>
    //     chunk (used directly); a cd.iff:tag is sliced to a temp .iff (unlinked
    //     at exit). A text .lev or an explicit --level= leaves the viewport alone.
    std::string viewport_temp;   // owns the sliced cd.iff chunk; unlinked before return
    if (!level_explicit) {
        bool is_temp = false;
        if (std::string vp = wfedit::ResolveEngineViewportLevel(leveltree, is_temp); !vp.empty()) {
            level = vp;
            if (is_temp) viewport_temp = vp;
            std::printf("wf-edit: viewport tracks %s\n", level.c_str());
        }
    }

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
    ctx.actor_eids  = std::move(actor_eids);
    ctx.doc         = &doc;   // read field subtrees on selection (read-only)
    ctx.undo        = &undo;  // Ctrl+Z / Ctrl+Y
    // Save target: the source .lev in-place for a text load, or a fresh sibling
    // .lev (Save-As) for a binary load — set by LoadLevelTreeIntoDoc. Falls back
    // to the raw arg when the load failed (empty save_path).
    ctx.save_path   = save_path.empty() ? leveltree : save_path;
    // Binary source ⇔ save was redirected to a fresh .lev (a text .lev saves
    // in-place, so save_path == leveltree). Drives the Save/Save-As menu label.
    ctx.binary_source = !save_path.empty() && save_path != leveltree;
    // File→Open (#2): exe_path is what we re-exec; --open opens the browser at
    // startup, --open-pick re-execs into a path on the first build frame.
    ctx.exe_path    = argv[0];
    ctx.open_pick   = std::move(open_pick);
    if (open_at_start) { ctx.show_open = true; ctx.browse_dir = DefaultBrowseDir(); }
    ctx.room_id     = room_id;
    ctx.gizmo_snap       = identity.gizmo_snap;        // restore persisted snap prefs
    ctx.gizmo_snap_trans = identity.gizmo_snap_trans;
    ctx.gizmo_snap_rot   = identity.gizmo_snap_rot;
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

    // 3c. Connect to the co-edit relay (Phase 2+). Non-fatal on failure.
    if (!ctx_relay_url.empty() && !room_id.empty()) {
        ctx.relay_url = ctx_relay_url;
        // Phase 6: prefer persisted peer_id over collab-session's ephemeral id.
        if (!identity.peer_id.empty()) {
            ctx.our_peer_id = identity.peer_id;
            std::copy(identity.colour, identity.colour + 3, ctx.our_colour);
        } else {
            ctx.our_peer_id = ctx.collab ? ctx.collab->OurPeerId() : std::string("editor-anon");
            PeerColourFromId(ctx.our_peer_id, ctx.our_colour);
            // First run — persist the generated id.
            identity.peer_id = ctx.our_peer_id;
            std::copy(ctx.our_colour, ctx.our_colour + 3, identity.colour);
        }
        if (ctx.relay_client.connect(ctx_relay_url.c_str())) {
            // Send CONTROL join message: [0x04][room_id NUL peer_id].
            std::vector<uint8_t> ctrl;
            ctrl.push_back(0x04);
            for (char ch : room_id)         ctrl.push_back(static_cast<uint8_t>(ch));
            ctrl.push_back(0);
            for (char ch : ctx.our_peer_id) ctrl.push_back(static_cast<uint8_t>(ch));
            ctx.relay_client.send(ctrl.data(), ctrl.size());

            // Wait for the relay's initial full-state SYNC (up to 1 s).
            {
                std::vector<uint8_t> frame;
                for (int t = 0; t < 1000 && !ctx.relay_client.poll(frame); ++t)
                    usleep(1000);
                if (!frame.empty() && frame[0] == 0x01 && frame.size() > 1) {
                    // Remote-origin apply — the initial peer state must not seed
                    // our undo history.
                    auto txn = doc.beginRemote();
                    txn.apply(wfcrdt::ByteView{frame.data() + 1, frame.size() - 1});
                    ctx.actor_names = wfedit::ReadActorNames(doc);
                    ctx.actor_eids  = wfedit::ReadActorEids(doc);
                }
            }

            // Wire local commits → relay.
            ctx.relay_sub = doc.observeUpdates([&ctx](wfcrdt::ByteView update) {
                if (ctx.suppress_relay_send) return;
                std::vector<uint8_t> msg;
                msg.push_back(0x01);  // CH_SYNC
                msg.insert(msg.end(), update.data, update.data + update.len);
                ctx.relay_client.send(msg.data(), msg.size());
            });

            // Phase 6: persist recent room + updated identity.
            PushRecentRoom(identity, ctx_relay_url, room_id);
            SaveIdentity(identity);
            std::printf("wf-edit: relay connected %s room=%s (peer %.8s…)\n",
                        ctx_relay_url.c_str(), room_id.c_str(), ctx.our_peer_id.c_str());
        } else {
            std::fprintf(stderr, "wf-edit: relay connect failed: %s\n",
                         ctx_relay_url.c_str());
        }
    } else if (!identity.peer_id.empty() && identity.peer_id != "editor-anon") {
        // Relay not used this session, but peer_id still available for
        // display/debugging.
        ctx.our_peer_id = identity.peer_id;
        std::copy(identity.colour, identity.colour + 3, ctx.our_colour);
    }

    SetEditorFrameCallbacks(editor_build, editor_present, &ctx);

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
    // WFInitGL (→ glViewport + aspect). Later resizes are tracked per-frame in
    // editor_build (wfWindowWidth/Height is the file-scope extern above).
    extern int _halWindowWidth, _halWindowHeight;   // hal/linux: feeds Display _xSize/_ySize
    int fbw = 0, fbh = 0;
    glfwGetFramebufferSize(win, &fbw, &fbh);
    wfWindowWidth  = _halWindowWidth  = fbw;
    wfWindowHeight = _halWindowHeight = fbh;
    std::printf("wf-edit: engine surface size %dx%d\n", fbw, fbh);

    std::printf("wf-edit: HALStart (--editor, level=%s)\n", level.c_str());
    HALStart(hal_argc, hal_argv, HAL_MAX_TASKS, HAL_MAX_MESSAGES, HAL_MAX_PORTS);
    std::printf("wf-edit: HALStart returned\n");

    // Persist gizmo snap prefs. Only when a peer_id exists — LoadIdentity rejects
    // an identity with an empty one, so saving without one would write a file that
    // never loads back (solo sessions get a peer_id once they touch a relay).
    if (!identity.peer_id.empty()) {
        identity.gizmo_snap       = ctx.gizmo_snap;
        identity.gizmo_snap_trans = ctx.gizmo_snap_trans;
        identity.gizmo_snap_rot   = ctx.gizmo_snap_rot;
        SaveIdentity(identity);
    }

    // 5. Engine released its references; clear the registries + tear down.
    //    Unregister the frame callback before `ctx` leaves scope so the
    //    engine's stored ctx pointer can't dangle (no callbacks fire after
    //    HALStart returns, but keep it tidy — mirrors ClearHostGLContext).
    SetEditorFrameCallbacks(nullptr, nullptr, nullptr);
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
    if (!viewport_temp.empty()) ::unlink(viewport_temp.c_str());   // sliced cd.iff chunk
    std::printf("wf-edit: clean exit\n");
    return 0;
}
