// debug_server.cc — WF TCP/JSON debug bridge implementation.
//
// See debug_server.hp for the public interface.

#include "debug_server.hp"

#ifdef WF_ENABLE_EDITOR

#include <pigsys/pigsys.hp>     // sys_atexit

#include <atomic>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <queue>
#include <string>
#include <thread>
#include <unordered_set>
#include <vector>
#include <algorithm>
#include <unordered_map>

// POSIX sockets
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

// Level + Actor API
#include "level.hp"
#include "actor.hp"
#include <mailbox/mailbox.hp>
#include <physics/physicalobject.hp>
#include <gfx/renderer_backend.hp>
#include "scripting_forth.hp"
#include <cstddef>

// GL for screenshot op.
#include <hal/hal.h>
#ifdef __ANDROID__
#  include <GLES3/gl3.h>
#else
#  include <GL/gl.h>
#endif

// stb_image_write — vendored single-header PNG encoder. Implementation lives
// in this TU; no other unit defines STB_IMAGE_WRITE_IMPLEMENTATION.
#define STB_IMAGE_WRITE_IMPLEMENTATION
#define STBI_WRITE_NO_STDIO_FILESYSTEM 0
#include "../vendor/stb/stb_image_write.h"

// Bind address: set by --debug-bind in main.cc; defaults to "127.0.0.1".
extern char gDebugBind[];

//=============================================================================
// Minimal JSON helpers

static std::string json_str(const char* key, const std::string& val)
{
    std::string out;
    out += '"'; out += key; out += "\":\"";
    for (unsigned char c : val) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:
                if (c < 0x20) {
                    char buf[8];
                    snprintf(buf, sizeof(buf), "\\u%04x", c);
                    out += buf;
                } else {
                    out += (char)c;
                }
                break;
        }
    }
    out += '"';
    return out;
}

static std::string json_int(const char* key, long long val)
{
    char buf[64];
    snprintf(buf, sizeof(buf), "\"%s\":%lld", key, val);
    return buf;
}

static std::string parse_jstr(const std::string& line, const char* key)
{
    std::string needle = std::string("\"") + key + "\"";
    auto pos = line.find(needle);
    if (pos == std::string::npos) return {};
    pos = line.find('"', pos + needle.size() + 1);
    if (pos == std::string::npos) return {};
    std::string out;
    ++pos;
    while (pos < line.size() && line[pos] != '"') {
        if (line[pos] == '\\' && pos + 1 < line.size()) {
            char esc = line[++pos];
            switch (esc) {
                case 'n':  out += '\n'; break;
                case 't':  out += '\t'; break;
                case 'r':  out += '\r'; break;
                case '"':  out += '"';  break;
                case '\\': out += '\\'; break;
                case '/':  out += '/';  break;
                default:   out += esc;  break;
            }
            ++pos;
        } else {
            out += line[pos++];
        }
    }
    return out;
}

static double parse_jnum(const std::string& line, const char* key)
{
    std::string needle = std::string("\"") + key + "\"";
    auto pos = line.find(needle);
    if (pos == std::string::npos) return 0.0;
    pos = line.find(':', pos + needle.size());
    if (pos == std::string::npos) return 0.0;
    while (++pos < line.size() && (line[pos] == ' ' || line[pos] == '\t'));
    return std::stod(line.c_str() + pos);
}

// Parse a JSON [x,y,z] array after "key": into out[3]. Returns false if missing.
static bool parse_jvec3(const std::string& line, const char* key, float out[3])
{
    std::string needle = std::string("\"") + key + "\"";
    auto pos = line.find(needle);
    if (pos == std::string::npos) return false;
    auto lb = line.find('[', pos + needle.size());
    if (lb == std::string::npos) return false;
    try {
        out[0] = (float)std::stod(line.c_str() + lb + 1);
        auto c1 = line.find(',', lb + 1);
        if (c1 == std::string::npos) return false;
        out[1] = (float)std::stod(line.c_str() + c1 + 1);
        auto c2 = line.find(',', c1 + 1);
        if (c2 == std::string::npos) return false;
        out[2] = (float)std::stod(line.c_str() + c2 + 1);
    } catch (...) { return false; }
    return true;
}

//=============================================================================
// Pause / step state (written from listener thread, read from game thread)

static std::atomic<bool> gPaused  { false };
static std::atomic<int>  gStepN   { 0 };

//=============================================================================
// Session change log (game-thread only — accessed exclusively in DrainQueue)
//
// gOriginals:     per-actor pre-session transform (for revert_all)
// gChangeStack:   ordered history of all changes (transform + prop) for undo_step
// gPropOriginals: per-(block, field) first-seen value, for revert_all

struct ChangeRecord {
    enum Kind { TRANSFORM, PROP, MAILBOX, SCRIPT } kind;
    int   actor_idx;
    // TRANSFORM:
    float px, py, pz;
    // PROP:
    char*  block;
    size_t field_offset;
    int32  old_raw;
    // MAILBOX:
    int    mailbox_idx;
    float  old_mbx_value;
    // SCRIPT: prior reloaded source for this actor (empty = no prior
    // override; undo restores OAD source). Re-compiled on undo via
    // ReloadActorScript — costs extra dict bytes (acceptable for debug).
    std::string script_prev_source;
};

// Key into gPropOriginals: the exact memory address of a specific field.
struct PropKey {
    char*  block;
    size_t field_offset;
    bool operator==(const PropKey& o) const {
        return block == o.block && field_offset == o.field_offset;
    }
};
struct PropKeyHash {
    size_t operator()(const PropKey& k) const {
        size_t h = std::hash<char*>()(k.block);
        h ^= std::hash<size_t>()(k.field_offset) + 0x9e3779b9u + (h << 6) + (h >> 2);
        return h;
    }
};

static std::unordered_map<int, ChangeRecord>              gOriginals;
static std::vector<ChangeRecord>                          gChangeStack;
static std::unordered_map<PropKey, int32, PropKeyHash>    gPropOriginals;

// Mailbox watchpoints — actor_idx → set of global mailbox indices.
// Touched exclusively from the game thread (DrainQueue / BroadcastMailboxes).
static std::unordered_map<int, std::unordered_set<int>> gWatches;

// Last reloaded source per actor — needed so undo_step can recompile the
// previous override (zForth has no dict-rewind). Empty string in the map
// means "actor was reloaded at least once but currently has no override".
static std::unordered_map<int, std::string> gLastReloadSource;
// Change detection: key = actor_idx * 100000 + mailbox_idx → last-sent float value.
static std::unordered_map<uint64_t, float>              gMailboxPrev;

// ── Property map (block + field → offset + type) ─────────────────────────────

struct PropInfo {
    enum Block { COMMON, MOVEBLOC, MESH } block;
    size_t field_offset;
    bool   is_fixed32;
};

static const std::unordered_map<std::string, PropInfo> kPropMap = {
    // common block
    {"common.hp",                     {PropInfo::COMMON,   offsetof(_Common,   hp),                    true }},
    {"common.Script",                 {PropInfo::COMMON,   offsetof(_Common,   Script),                false}},
    {"common.NumberOfLocalMailboxes", {PropInfo::COMMON,   offsetof(_Common,   NumberOfLocalMailboxes), false}},
    {"common.WriteToMailboxOnDeath",  {PropInfo::COMMON,   offsetof(_Common,   WriteToMailboxOnDeath),  false}},
    // movebloc block
    {"movebloc.Mass",                 {PropInfo::MOVEBLOC, offsetof(_Movement, Mass),                  true }},
    {"movebloc.MaxGroundSpeed",       {PropInfo::MOVEBLOC, offsetof(_Movement, MaxGroundSpeed),        true }},
    {"movebloc.RunningAcceleration",  {PropInfo::MOVEBLOC, offsetof(_Movement, RunningAcceleration),   true }},
    {"movebloc.JumpingAcceleration",  {PropInfo::MOVEBLOC, offsetof(_Movement, JumpingAcceleration),   true }},
    {"movebloc.FallingAcceleration",  {PropInfo::MOVEBLOC, offsetof(_Movement, FallingAcceleration),   true }},
    {"movebloc.StepSize",             {PropInfo::MOVEBLOC, offsetof(_Movement, StepSize),              true }},
    {"movebloc.Mobility",             {PropInfo::MOVEBLOC, offsetof(_Movement, Mobility),              false}},
    {"movebloc.MovementClass",        {PropInfo::MOVEBLOC, offsetof(_Movement, MovementClass),         false}},
    // mesh block
    {"mesh.ModelType",                {PropInfo::MESH,     offsetof(_Mesh,     ModelType),             false}},
    {"mesh.AnimationMailbox",         {PropInfo::MESH,     offsetof(_Mesh,     AnimationMailbox),      false}},
    {"mesh.VisibilityMailbox",        {PropInfo::MESH,     offsetof(_Mesh,     VisibilityMailbox),     false}},
};

// Return a mutable pointer to the named sub-block, or nullptr if unavailable.
static char* debug_get_block(Actor* actor, PropInfo::Block block_id)
{
    const void* ptr = nullptr;
    switch (block_id) {
        case PropInfo::COMMON:   ptr = actor->GetCommonBlockPtr();    break;
        case PropInfo::MOVEBLOC: ptr = actor->GetMovementBlockPtr();  break;
        case PropInfo::MESH:     ptr = actor->GetMeshBlockPtr();      break;
    }
    if (!ptr) return nullptr;
    // The underlying storage is heap-allocated char[] (not truly const).
    // The existing engine code already strips const via C-style casts in .hpi files.
    return const_cast<char*>(static_cast<const char*>(ptr));
}

//=============================================================================
// Pending update queue

struct PendingUpdate {
    enum Kind { SET_PROP, SET_TRANSFORM, PICK, UNDO_STEP, REVERT_ALL,
                WATCH, UNWATCH, SET_MAILBOX, INJECT_INPUT, SET_SHADER,
                RELOAD_SCRIPT, SCREENSHOT, CLIENT_DISCONNECT } kind;
    int  actor_idx;
    std::string key;
    double value;
    float  px, py, pz;              // SET_TRANSFORM: new position
    float  ray_ox, ray_oy, ray_oz;  // PICK: ray origin
    float  ray_dx, ray_dy, ray_dz;  // PICK: ray direction (unit)
    int    mailbox_idx;             // WATCH / UNWATCH / SET_MAILBOX: mailbox number
    int    duration_frames;         // INJECT_INPUT: 0=this frame, N>0=N frames, -1=sticky
    std::string vert_src;           // SET_SHADER: vertex shader GLSL
    std::string frag_src;           // SET_SHADER: fragment shader GLSL
    std::string script_src;         // RELOAD_SCRIPT: zForth source
    std::string filename;           // SCREENSHOT: output path (PNG)
};

// Input override table for inject_input. Game-thread only — read by
// DebugServer_GetInputOverride from inside Level::ReadSystemMailbox, written
// by DrainQueue when applying an INJECT_INPUT op, ticked by DrainQueue once
// per frame. Both happen on the game thread, so no mutex needed.
struct InputOverride {
    int32 value;
    int   frames_remaining;  // -1 = sticky forever
};
static std::unordered_map<int, InputOverride> gInputOverrides;

static std::mutex                gQueueMutex;
static std::queue<PendingUpdate> gQueue;
static std::vector<int>          gClients;

//=============================================================================
// Server state

static int               gServerFd = -1;
static std::atomic<bool> gRunning  { false };
static std::thread       gListenerThread;

//=============================================================================
// Send a line to all connected clients. Must hold gQueueMutex.

static void send_all_locked(const std::string& line)
{
    std::vector<int> dead;
    for (int fd : gClients) {
        if (::write(fd, line.c_str(), line.size()) < 0)
            dead.push_back(fd);
    }
    for (int fd : dead) {
        ::close(fd);
        gClients.erase(std::find(gClients.begin(), gClients.end(), fd));
    }
}

//=============================================================================
// Per-client reader (runs on listener thread, detached).

static void handle_client(int fd)
{
    char buf[4096];
    std::string partial;

    while (gRunning) {
        ssize_t n = ::read(fd, buf, sizeof(buf) - 1);
        if (n <= 0) break;
        buf[n] = '\0';
        partial += buf;

        size_t start = 0;
        for (;;) {
            auto nl = partial.find('\n', start);
            if (nl == std::string::npos) break;
            std::string line = partial.substr(start, nl - start);
            start = nl + 1;

            std::string op = parse_jstr(line, "op");

            if (op == "ping") {
                const char* resp = "{\"op\":\"pong\"}\n";
                ::write(fd, resp, strlen(resp));

            } else if (op == "scene:set_prop") {
                PendingUpdate u;
                u.kind      = PendingUpdate::SET_PROP;
                u.actor_idx = (int)parse_jnum(line, "idx");
                u.key       = parse_jstr(line, "key");
                u.value     = parse_jnum(line, "value");
                if (u.actor_idx > 0 && !u.key.empty()) {
                    std::lock_guard<std::mutex> lk(gQueueMutex);
                    gQueue.push(u);
                }

            } else if (op == "scene:set_transform") {
                PendingUpdate u;
                u.kind      = PendingUpdate::SET_TRANSFORM;
                u.actor_idx = (int)parse_jnum(line, "idx");
                float pos[3] = {};
                parse_jvec3(line, "pos", pos);
                u.px = pos[0]; u.py = pos[1]; u.pz = pos[2];
                if (u.actor_idx > 0) {
                    std::lock_guard<std::mutex> lk(gQueueMutex);
                    gQueue.push(u);
                }

            } else if (op == "pause") {
                gPaused = true;
                gStepN  = 0;
                std::lock_guard<std::mutex> lk(gQueueMutex);
                send_all_locked("{\"op\":\"paused\"}\n");

            } else if (op == "resume") {
                gPaused = false;
                gStepN  = 0;
                std::lock_guard<std::mutex> lk(gQueueMutex);
                send_all_locked("{\"op\":\"resumed\"}\n");

            } else if (op == "step") {
                int n = (int)parse_jnum(line, "frames");
                if (n <= 0) n = 1;
                gStepN.fetch_add(n);

            } else if (op == "undo_step") {
                PendingUpdate u;
                u.kind = PendingUpdate::UNDO_STEP;
                u.actor_idx = 0;
                std::lock_guard<std::mutex> lk(gQueueMutex);
                gQueue.push(u);

            } else if (op == "revert_all") {
                PendingUpdate u;
                u.kind = PendingUpdate::REVERT_ALL;
                u.actor_idx = 0;
                std::lock_guard<std::mutex> lk(gQueueMutex);
                gQueue.push(u);

            } else if (op == "scene:pick") {
                PendingUpdate u;
                u.kind = PendingUpdate::PICK;
                float ro[3] = {}, rd[3] = {};
                if (parse_jvec3(line, "ray_origin", ro) && parse_jvec3(line, "ray_dir", rd)) {
                    u.ray_ox = ro[0]; u.ray_oy = ro[1]; u.ray_oz = ro[2];
                    u.ray_dx = rd[0]; u.ray_dy = rd[1]; u.ray_dz = rd[2];
                    std::lock_guard<std::mutex> lk(gQueueMutex);
                    gQueue.push(u);
                }

            } else if (op == "set_mailbox") {
                PendingUpdate u;
                u.kind        = PendingUpdate::SET_MAILBOX;
                u.actor_idx   = (int)parse_jnum(line, "idx");      // 0 = global
                u.mailbox_idx = (int)parse_jnum(line, "mailbox");
                u.value       = parse_jnum(line, "value");
                std::lock_guard<std::mutex> lk(gQueueMutex);
                gQueue.push(u);

            } else if (op == "inject_input") {
                PendingUpdate u;
                u.kind = PendingUpdate::INJECT_INPUT;
                // Either "slot_id" (raw mailbox enum int) or "slot" (string name).
                int slot_id = (int)parse_jnum(line, "slot_id");
                if (slot_id == 0) {
                    std::string slot = parse_jstr(line, "slot");
                    if      (slot == "joystick1")                slot_id = EMAILBOX_HARDWARE_JOYSTICK1;
                    else if (slot == "joystick1_raw")            slot_id = EMAILBOX_HARDWARE_JOYSTICK1_RAW;
                    else if (slot == "joystick1_raw_justpressed") slot_id = EMAILBOX_HARDWARE_JOYSTICK1_RAW_JUSTPRESSED;
                    else if (slot == "joystick2")                slot_id = EMAILBOX_HARDWARE_JOYSTICK2;
                    else if (slot == "joystick2_raw")            slot_id = EMAILBOX_HARDWARE_JOYSTICK2_RAW;
                    else if (slot == "joystick2_raw_justpressed") slot_id = EMAILBOX_HARDWARE_JOYSTICK2_RAW_JUSTPRESSED;
                    else if (slot == "joystick3")                slot_id = EMAILBOX_HARDWARE_JOYSTICK3;
                    else if (slot == "joystick3_raw")            slot_id = EMAILBOX_HARDWARE_JOYSTICK3_RAW;
                    else if (slot == "joystick3_raw_justpressed") slot_id = EMAILBOX_HARDWARE_JOYSTICK3_RAW_JUSTPRESSED;
                    else if (slot == "joystick4")                slot_id = EMAILBOX_HARDWARE_JOYSTICK4;
                    else if (slot == "joystick4_raw")            slot_id = EMAILBOX_HARDWARE_JOYSTICK4_RAW;
                    else if (slot == "joystick4_raw_justpressed") slot_id = EMAILBOX_HARDWARE_JOYSTICK4_RAW_JUSTPRESSED;
                }
                u.mailbox_idx     = slot_id;
                u.value           = parse_jnum(line, "value");
                u.duration_frames = (int)parse_jnum(line, "duration_frames");
                if (slot_id != 0) {
                    std::lock_guard<std::mutex> lk(gQueueMutex);
                    gQueue.push(u);
                }

            } else if (op == "reload_script") {
                PendingUpdate u;
                u.kind       = PendingUpdate::RELOAD_SCRIPT;
                u.actor_idx  = (int)parse_jnum(line, "idx");
                u.script_src = parse_jstr(line, "source");
                if (u.actor_idx > 0 && !u.script_src.empty()) {
                    std::lock_guard<std::mutex> lk(gQueueMutex);
                    gQueue.push(u);
                }

            } else if (op == "set_shader") {
                PendingUpdate u;
                u.kind     = PendingUpdate::SET_SHADER;
                u.vert_src = parse_jstr(line, "vert");
                u.frag_src = parse_jstr(line, "frag");
                if (!u.vert_src.empty() && !u.frag_src.empty()) {
                    std::lock_guard<std::mutex> lk(gQueueMutex);
                    gQueue.push(u);
                }

            } else if (op == "screenshot") {
                PendingUpdate u;
                u.kind     = PendingUpdate::SCREENSHOT;
                u.filename = parse_jstr(line, "filename");
                if (!u.filename.empty()) {
                    std::lock_guard<std::mutex> lk(gQueueMutex);
                    gQueue.push(u);
                }

            } else if (op == "watch" || op == "unwatch") {
                PendingUpdate u;
                u.kind        = (op == "watch") ? PendingUpdate::WATCH : PendingUpdate::UNWATCH;
                u.actor_idx   = (int)parse_jnum(line, "idx");
                u.mailbox_idx = (int)parse_jnum(line, "mailbox");
                if (u.actor_idx > 0) {
                    std::lock_guard<std::mutex> lk(gQueueMutex);
                    gQueue.push(u);
                }
            }
            // Unknown ops are silently ignored.
        }
        if (start < partial.size())
            partial = partial.substr(start);
        else
            partial.clear();
    }

    {
        std::lock_guard<std::mutex> lk(gQueueMutex);
        ::close(fd);
        auto it = std::find(gClients.begin(), gClients.end(), fd);
        if (it != gClients.end()) gClients.erase(it);
        PendingUpdate disc;
        disc.kind = PendingUpdate::CLIENT_DISCONNECT;
        gQueue.push(disc);
    }
    std::fprintf(stderr, "[debug] client disconnected fd=%d\n", fd);
}

//=============================================================================
// Listener thread

static void listener_loop(int port)
{
    gServerFd = ::socket(AF_INET, SOCK_STREAM, 0);
    if (gServerFd < 0) {
        std::fprintf(stderr, "[debug] socket() failed: %s\n", strerror(errno));
        return;
    }
    int opt = 1;
    ::setsockopt(gServerFd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr {};
    addr.sin_family = AF_INET;
    addr.sin_port   = htons((uint16_t)port);
    if (gDebugBind[0] == '\0' || strcmp(gDebugBind, "0.0.0.0") == 0)
        addr.sin_addr.s_addr = INADDR_ANY;
    else
        inet_pton(AF_INET, gDebugBind, &addr.sin_addr);

    if (::bind(gServerFd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        std::fprintf(stderr, "[debug] bind(:%d) failed: %s\n", port, strerror(errno));
        ::close(gServerFd); gServerFd = -1; return;
    }
    ::listen(gServerFd, 4);
    std::fprintf(stderr, "[debug] listening on :%d\n", port);

    while (gRunning) {
        struct sockaddr_in client_addr {};
        socklen_t len = sizeof(client_addr);
        int cfd = ::accept(gServerFd, (struct sockaddr*)&client_addr, &len);
        if (cfd < 0) {
            if (gRunning)
                std::fprintf(stderr, "[debug] accept() failed: %s\n", strerror(errno));
            break;
        }
        char ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client_addr.sin_addr, ip, sizeof(ip));
        std::fprintf(stderr, "[debug] client connected fd=%d from %s\n", cfd, ip);
        {
            std::lock_guard<std::mutex> lk(gQueueMutex);
            gClients.push_back(cfd);
        }
        std::thread(handle_client, cfd).detach();
    }
}

//=============================================================================
// Public API

void DebugServer_Start(int port)
{
    if (port <= 0) return;
    gRunning = true;
    gListenerThread = std::thread(listener_loop, port);

    static bool atexitRegistered = false;
    if (!atexitRegistered) {
        sys_atexit([](int) { DebugServer_Stop(); });
        atexitRegistered = true;
    }
}

void DebugServer_Stop()
{
    if (!gRunning) return;
    gRunning = false;
    if (gServerFd >= 0) {
        ::shutdown(gServerFd, SHUT_RDWR);  // unblocks accept() in listener thread
        ::close(gServerFd);
        gServerFd = -1;
    }
    {
        std::lock_guard<std::mutex> lk(gQueueMutex);
        for (int fd : gClients) ::close(fd);
        gClients.clear();
    }
    if (gListenerThread.joinable()) gListenerThread.join();
    gOriginals.clear();
    gChangeStack.clear();
    gPropOriginals.clear();
    gWatches.clear();
    gMailboxPrev.clear();
    gInputOverrides.clear();
#ifdef WF_WITH_FORTH
    forth_engine::ClearActorScriptOverrides();
#endif
    gLastReloadSource.clear();
}

bool DebugServer_IsPaused()
{
    if (!gPaused) return false;
    int steps = gStepN.load();
    if (steps > 0) {
        gStepN.fetch_sub(1);
        return false;  // allow this frame through
    }
    return true;
}

void DebugServer_DrainQueue(Level& level)
{
    if (!gRunning) return;

    // Per-frame tick of input overrides. Runs BEFORE this frame's update reads
    // the joystick mailboxes — so an override applied in frame N stays alive
    // through frame N's reads, and is decremented at the start of frame N+1.
    for (auto it = gInputOverrides.begin(); it != gInputOverrides.end(); ) {
        if (it->second.frames_remaining > 0) {
            if (--it->second.frames_remaining == 0) {
                it = gInputOverrides.erase(it);
                continue;
            }
        }
        ++it;
    }

    std::queue<PendingUpdate> local;
    {
        std::lock_guard<std::mutex> lk(gQueueMutex);
        std::swap(local, gQueue);
    }

    while (!local.empty()) {
        const PendingUpdate& u = local.front();
        BaseObject* bo = level.GetObject(u.actor_idx);
        Actor* actor = bo ? dynamic_cast<Actor*>(bo) : nullptr;

        if (u.kind == PendingUpdate::SET_TRANSFORM && actor) {
            const Vector3& cur = actor->currentPos();
            ChangeRecord rec;
            rec.kind     = ChangeRecord::TRANSFORM;
            rec.actor_idx = u.actor_idx;
            rec.px = cur.X().AsFloat();
            rec.py = cur.Y().AsFloat();
            rec.pz = cur.Z().AsFloat();
            rec.block = nullptr; rec.field_offset = 0; rec.old_raw = 0;
            // Save pre-session original on first touch
            if (gOriginals.find(u.actor_idx) == gOriginals.end())
                gOriginals[u.actor_idx] = rec;
            gChangeStack.push_back(rec);

            Vector3 pos(Scalar::FromDouble((double)u.px),
                        Scalar::FromDouble((double)u.py),
                        Scalar::FromDouble((double)u.pz));
            actor->setCurrentPos(pos);

        } else if (u.kind == PendingUpdate::SET_PROP && actor) {
            // common.Script is a resolved pointer/handle into level data —
            // a raw int32 write here corrupts script dispatch. Use the
            // reload_script op instead.
            if (u.key == "common.Script") {
                std::string errmsg = "{\"op\":\"error\","
                    + json_str("msg", "common.Script is read-only over set_prop; use reload_script") + ","
                    + json_int("idx", u.actor_idx) + "}\n";
                std::lock_guard<std::mutex> lk(gQueueMutex);
                send_all_locked(errmsg);
                local.pop();
                continue;
            }
            auto pit = kPropMap.find(u.key);
            if (pit == kPropMap.end()) {
                std::string errmsg = "{\"op\":\"error\","
                    + json_str("msg", "unknown property: " + u.key) + ","
                    + json_int("idx", u.actor_idx) + "}\n";
                std::lock_guard<std::mutex> lk(gQueueMutex);
                send_all_locked(errmsg);
            } else {
                const PropInfo& info = pit->second;
                char* block = debug_get_block(actor, info.block);
                if (block) {
                    int32 old_raw = *reinterpret_cast<const int32*>(block + info.field_offset);
                    int32 new_raw = info.is_fixed32
                        ? static_cast<int32>(u.value * 65536.0)
                        : static_cast<int32>(u.value);

                    // Record pre-session original (first touch only)
                    PropKey pk { block, info.field_offset };
                    if (gPropOriginals.find(pk) == gPropOriginals.end())
                        gPropOriginals[pk] = old_raw;

                    ChangeRecord rec;
                    rec.kind         = ChangeRecord::PROP;
                    rec.actor_idx    = u.actor_idx;
                    rec.px = rec.py = rec.pz = 0.f;
                    rec.block        = block;
                    rec.field_offset = info.field_offset;
                    rec.old_raw      = old_raw;
                    gChangeStack.push_back(rec);

                    // In-place write — same pattern as actor.hpi C-style casts.
                    *reinterpret_cast<int32*>(block + info.field_offset) = new_raw;
                }
            }

        } else if (u.kind == PendingUpdate::PICK) {
            // Find actor whose position is closest to the ray (within 2 units).
            float best_dist2 = 4.0f;  // 2-unit pick radius
            int   best_idx   = -1;
            BaseObjectList& list = level.GetObjectList();
            for (int i = 1; i < list.Size(); ++i) {
                BaseObject* bo2 = list[i];
                if (!bo2) continue;
                Actor* a = dynamic_cast<Actor*>(bo2);
                if (!a) continue;
                const Vector3& p = a->currentPos();
                float dx = p.X().AsFloat() - u.ray_ox;
                float dy = p.Y().AsFloat() - u.ray_oy;
                float dz = p.Z().AsFloat() - u.ray_oz;
                float t  = dx*u.ray_dx + dy*u.ray_dy + dz*u.ray_dz;
                if (t <= 0.0f) continue;  // behind ray origin
                float dist2 = (dx - t*u.ray_dx)*(dx - t*u.ray_dx)
                            + (dy - t*u.ray_dy)*(dy - t*u.ray_dy)
                            + (dz - t*u.ray_dz)*(dz - t*u.ray_dz);
                if (dist2 < best_dist2) {
                    best_dist2 = dist2;
                    best_idx   = i;
                }
            }
            char buf[64];
            snprintf(buf, sizeof(buf), "{\"op\":\"picked\",\"idx\":%d}\n", best_idx);
            std::lock_guard<std::mutex> lk(gQueueMutex);
            send_all_locked(buf);

        } else if (u.kind == PendingUpdate::UNDO_STEP) {
            if (!gChangeStack.empty()) {
                const ChangeRecord& r = gChangeStack.back();
                if (r.kind == ChangeRecord::TRANSFORM) {
                    BaseObject* bo2 = level.GetObject(r.actor_idx);
                    Actor* a = bo2 ? dynamic_cast<Actor*>(bo2) : nullptr;
                    if (a) {
                        Vector3 prev(Scalar::FromDouble(r.px),
                                     Scalar::FromDouble(r.py),
                                     Scalar::FromDouble(r.pz));
                        a->setCurrentPos(prev);
                    }
                } else if (r.kind == ChangeRecord::PROP && r.block) {
                    *reinterpret_cast<int32*>(r.block + r.field_offset) = r.old_raw;
                } else if (r.kind == ChangeRecord::SCRIPT) {
#ifdef WF_WITH_FORTH
                    if (r.script_prev_source.empty()) {
                        forth_engine::ClearActorScriptOverride(r.actor_idx);
                        gLastReloadSource.erase(r.actor_idx);
                    } else {
                        std::string log;
                        forth_engine::ReloadActorScript(
                            r.actor_idx, r.script_prev_source.c_str(), log);
                        gLastReloadSource[r.actor_idx] = r.script_prev_source;
                    }
#endif
                } else if (r.kind == ChangeRecord::MAILBOX) {
                    Mailboxes* boxes = nullptr;
                    if (r.actor_idx == 0) {
                        boxes = &level.GetMailboxes();
                    } else {
                        BaseObject* bo2 = level.GetObject(r.actor_idx);
                        Actor* a = bo2 ? dynamic_cast<Actor*>(bo2) : nullptr;
                        if (a) boxes = &a->GetMailboxes();
                    }
                    if (boxes)
                        boxes->WriteMailbox(r.mailbox_idx,
                                            Scalar::FromDouble((double)r.old_mbx_value));
                }
                gChangeStack.pop_back();
            }

        } else if (u.kind == PendingUpdate::REVERT_ALL) {
            // Restore transform originals
            for (auto& kv : gOriginals) {
                BaseObject* bo2 = level.GetObject(kv.first);
                Actor* a = bo2 ? dynamic_cast<Actor*>(bo2) : nullptr;
                if (a) {
                    const ChangeRecord& r = kv.second;
                    Vector3 orig(Scalar::FromDouble(r.px),
                                 Scalar::FromDouble(r.py),
                                 Scalar::FromDouble(r.pz));
                    a->setCurrentPos(orig);
                }
            }
            gOriginals.clear();
            // Restore property originals
            for (auto& kv : gPropOriginals) {
                *reinterpret_cast<int32*>(kv.first.block + kv.first.field_offset) = kv.second;
            }
            gPropOriginals.clear();
            // Clear hot-reloaded script overrides (revert to OAD-baked source).
#ifdef WF_WITH_FORTH
            forth_engine::ClearActorScriptOverrides();
#endif
            gLastReloadSource.clear();
            gChangeStack.clear();
            std::lock_guard<std::mutex> lk(gQueueMutex);
            send_all_locked("{\"op\":\"reverted\"}\n");

        } else if (u.kind == PendingUpdate::SET_MAILBOX) {
            // idx==0 means the global mailbox space; nonzero is per-actor.
            // Either way, GetMailboxes() handles the routing (per-actor falls
            // through to the parent for non-local indices).
            Mailboxes* boxes = nullptr;
            if (u.actor_idx == 0) {
                boxes = &level.GetMailboxes();
            } else if (actor) {
                boxes = &actor->GetMailboxes();
            }
            if (boxes) {
                float old_val = boxes->ReadMailbox(u.mailbox_idx).AsFloat();
                ChangeRecord rec;
                rec.kind          = ChangeRecord::MAILBOX;
                rec.actor_idx     = u.actor_idx;
                rec.px = rec.py = rec.pz = 0.f;
                rec.block         = nullptr;
                rec.field_offset  = 0;
                rec.old_raw       = 0;
                rec.mailbox_idx   = u.mailbox_idx;
                rec.old_mbx_value = old_val;
                gChangeStack.push_back(rec);

                boxes->WriteMailbox(u.mailbox_idx, Scalar::FromDouble(u.value));
            } else {
                std::string errmsg = "{\"op\":\"error\","
                    + json_str("msg", "set_mailbox: actor not found")
                    + "," + json_int("idx", u.actor_idx) + "}\n";
                std::lock_guard<std::mutex> lk(gQueueMutex);
                send_all_locked(errmsg);
            }

        } else if (u.kind == PendingUpdate::RELOAD_SCRIPT) {
#ifdef WF_WITH_FORTH
            std::string log;
            // Capture prior source for undo BEFORE we overwrite it.
            std::string prev;
            auto pit = gLastReloadSource.find(u.actor_idx);
            if (pit != gLastReloadSource.end()) prev = pit->second;

            bool ok = forth_engine::ReloadActorScript(
                u.actor_idx, u.script_src.c_str(), log);
            std::string reply;
            if (ok) {
                ChangeRecord rec;
                rec.kind          = ChangeRecord::SCRIPT;
                rec.actor_idx     = u.actor_idx;
                rec.px = rec.py = rec.pz = 0.f;
                rec.block         = nullptr;
                rec.field_offset  = 0;
                rec.old_raw       = 0;
                rec.mailbox_idx   = 0;
                rec.old_mbx_value = 0.f;
                rec.script_prev_source = prev;
                gChangeStack.push_back(rec);
                gLastReloadSource[u.actor_idx] = u.script_src;

                reply = "{\"op\":\"script_reloaded\","
                      + json_int("idx", u.actor_idx) + "}\n";
            } else {
                reply = "{\"op\":\"error\","
                      + json_str("what", "script_compile") + ","
                      + json_int("idx", u.actor_idx) + ","
                      + json_str("log", log) + "}\n";
            }
            std::lock_guard<std::mutex> lk(gQueueMutex);
            send_all_locked(reply);
#else
            std::string reply = "{\"op\":\"error\","
                + json_str("what", "script_compile") + ","
                + json_int("idx", u.actor_idx) + ","
                + json_str("log", "Forth engine not compiled in") + "}\n";
            std::lock_guard<std::mutex> lk(gQueueMutex);
            send_all_locked(reply);
#endif

        } else if (u.kind == PendingUpdate::SET_SHADER) {
            std::string log;
            bool ok = RendererBackendGet().ReloadProgram(
                u.vert_src.c_str(), u.frag_src.c_str(), log);
            std::string reply;
            if (ok) {
                reply = "{\"op\":\"shader_reloaded\"}\n";
            } else {
                reply = "{\"op\":\"error\","
                      + json_str("what", "shader_compile") + ","
                      + json_str("log", log) + "}\n";
            }
            std::lock_guard<std::mutex> lk(gQueueMutex);
            send_all_locked(reply);

        } else if (u.kind == PendingUpdate::INJECT_INPUT) {
            InputOverride ov;
            ov.value = (int32)u.value;
            // duration_frames: 0 → one frame (this frame), N>0 → N frames,
            // -1 → sticky until cleared by another inject_input on the same slot.
            if (u.duration_frames == 0)
                ov.frames_remaining = 1;
            else
                ov.frames_remaining = u.duration_frames;
            gInputOverrides[u.mailbox_idx] = ov;

        } else if (u.kind == PendingUpdate::WATCH) {
            gWatches[u.actor_idx].insert(u.mailbox_idx);
            // Erase prev so first broadcast sends immediately.
            gMailboxPrev.erase((uint64_t)u.actor_idx * 100000ull + (uint64_t)u.mailbox_idx);

        } else if (u.kind == PendingUpdate::UNWATCH) {
            auto it = gWatches.find(u.actor_idx);
            if (it != gWatches.end()) {
                it->second.erase(u.mailbox_idx);
                if (it->second.empty()) gWatches.erase(it);
            }
            gMailboxPrev.erase((uint64_t)u.actor_idx * 100000ull + (uint64_t)u.mailbox_idx);

        } else if (u.kind == PendingUpdate::CLIENT_DISCONNECT) {
            gWatches.clear();
            gMailboxPrev.clear();

        } else if (u.kind == PendingUpdate::SCREENSHOT) {
            // glReadPixels against the default framebuffer at the current
            // viewport. Game thread; called after the frame has rendered
            // (DrainQueue runs near top of game loop, so we capture the
            // *previous* frame's contents — which is what the host expects
            // when it issues the op in response to a watched mailbox event).
            GLint vp[4] = {0};
            glGetIntegerv(GL_VIEWPORT, vp);
            int w = vp[2], h = vp[3];
            std::string reply;
            if (w <= 0 || h <= 0) {
                reply = "{\"op\":\"error\","
                      + json_str("what", "screenshot") + ","
                      + json_str("msg", "viewport not initialised") + "}\n";
            } else {
                std::vector<uint8_t> buf((size_t)w * (size_t)h * 4);
                glPixelStorei(GL_PACK_ALIGNMENT, 1);
                glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, buf.data());
                // glReadPixels yields bottom-left origin; PNG wants top-left.
                std::vector<uint8_t> flipped((size_t)w * (size_t)h * 4);
                size_t row = (size_t)w * 4;
                for (int y = 0; y < h; ++y)
                    std::memcpy(&flipped[(size_t)y * row],
                                &buf[((size_t)h - 1 - (size_t)y) * row], row);
                int ok = stbi_write_png(u.filename.c_str(),
                                        w, h, 4, flipped.data(), (int)row);
                if (ok) {
                    char b[256];
                    snprintf(b, sizeof(b),
                        "{\"op\":\"screenshot_done\",\"filename\":\"%s\","
                        "\"w\":%d,\"h\":%d}\n",
                        u.filename.c_str(), w, h);
                    reply = b;
                } else {
                    reply = "{\"op\":\"error\","
                          + json_str("what", "screenshot") + ","
                          + json_str("filename", u.filename) + ","
                          + json_str("msg", "stbi_write_png failed") + "}\n";
                }
            }
            std::lock_guard<std::mutex> lk(gQueueMutex);
            send_all_locked(reply);

        } else if (!bo) {
            std::string errmsg = "{\"op\":\"error\","
                + json_str("msg", "actor not found")
                + "," + json_int("idx", u.actor_idx) + "}\n";
            std::lock_guard<std::mutex> lk(gQueueMutex);
            send_all_locked(errmsg);
        }
        local.pop();
    }
}

// Broadcast actor positions at ~10 Hz (rate-limited to every 6th call).
void DebugServer_BroadcastState(Level& level)
{
    if (!gRunning) return;
    {
        std::lock_guard<std::mutex> lk(gQueueMutex);
        if (gClients.empty()) return;
    }

    static int sTick = 0;
    if (++sTick % 6 != 0) return;

    BaseObjectList& list = level.GetObjectList();
    std::string batch;
    for (int i = 1; i < list.Size(); ++i) {
        BaseObject* bo = list[i];
        if (!bo) continue;
        Actor* actor = dynamic_cast<Actor*>(bo);
        if (!actor) continue;

        const Vector3& pos = actor->currentPos();
        char buf[256];
        snprintf(buf, sizeof(buf),
            "{\"op\":\"state\",\"idx\":%d,"
            "\"pos\":[%.4f,%.4f,%.4f]}\n",
            i,
            pos.X().AsFloat(), pos.Y().AsFloat(), pos.Z().AsFloat());
        batch += buf;
    }

    if (!batch.empty()) {
        std::lock_guard<std::mutex> lk(gQueueMutex);
        send_all_locked(batch);
    }
}

// Broadcast performance metrics at ~10 Hz (same cadence as BroadcastState).
void DebugServer_BroadcastPerf(float frame_ms, int actor_count)
{
    if (!gRunning) return;
    {
        std::lock_guard<std::mutex> lk(gQueueMutex);
        if (gClients.empty()) return;
    }

    static int sTick = 0;
    if (++sTick % 6 != 0) return;

    char buf[128];
    snprintf(buf, sizeof(buf),
        "{\"op\":\"perf\",\"frame_ms\":%.2f,\"actors\":%d}\n",
        frame_ms, actor_count);
    std::lock_guard<std::mutex> lk(gQueueMutex);
    send_all_locked(buf);
}

// Broadcast watched mailbox values — sent whenever a value changes (no rate cap).
void DebugServer_BroadcastMailboxes(Level& level)
{
    if (!gRunning || gWatches.empty()) return;
    {
        std::lock_guard<std::mutex> lk(gQueueMutex);
        if (gClients.empty()) return;
    }

    std::string batch;
    for (auto& [actor_idx, mbx_set] : gWatches) {
        BaseObject* bo = level.GetObject(actor_idx);
        Actor* actor   = bo ? dynamic_cast<Actor*>(bo) : nullptr;
        if (!actor) continue;
        for (int mbx : mbx_set) {
            float    val = actor->GetMailboxes().ReadMailbox(mbx).AsFloat();
            uint64_t key = (uint64_t)actor_idx * 100000ull + (uint64_t)mbx;
            auto pit = gMailboxPrev.find(key);
            if (pit != gMailboxPrev.end() && pit->second == val) continue;
            gMailboxPrev[key] = val;
            char buf[128];
            snprintf(buf, sizeof(buf),
                "{\"op\":\"mailbox\",\"idx\":%d,\"mailbox\":%d,\"value\":%.6f}\n",
                actor_idx, mbx, val);
            batch += buf;
        }
    }
    if (!batch.empty()) {
        std::lock_guard<std::mutex> lk(gQueueMutex);
        send_all_locked(batch);
    }
}

// Called from Level::ReadSystemMailbox at the EMAILBOX_HARDWARE_JOYSTICK*
// case branches. Game-thread only — same thread that mutates gInputOverrides
// from DrainQueue, so no synchronization needed.
bool DebugServer_GetInputOverride(int mailbox_id, int32_t* out_value)
{
    if (!gRunning || gInputOverrides.empty()) return false;
    auto it = gInputOverrides.find(mailbox_id);
    if (it == gInputOverrides.end()) return false;
    *out_value = it->second.value;
    return true;
}

#endif // WF_ENABLE_EDITOR
