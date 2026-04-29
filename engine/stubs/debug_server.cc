// debug_server.cc — WF TCP/JSON debug bridge implementation.
//
// See debug_server.hp for the public interface.

#include "debug_server.hp"

#ifdef WF_DEBUG_BRIDGE

#include <pigsys/pigsys.hp>     // sys_atexit

#include <atomic>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <queue>
#include <string>
#include <thread>
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
#include <physics/physicalobject.hp>
#include <cstddef>

// Bind address: set by --debug-bind in main.cc; defaults to "127.0.0.1".
extern char gDebugBind[];

//=============================================================================
// Minimal JSON helpers

static std::string json_str(const char* key, const std::string& val)
{
    std::string out;
    out += '"'; out += key; out += "\":\"";
    for (char c : val) {
        if (c == '"' || c == '\\') out += '\\';
        out += c;
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
        if (line[pos] == '\\' && pos + 1 < line.size()) ++pos;
        out += line[pos++];
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
    enum Kind { TRANSFORM, PROP } kind;
    int   actor_idx;
    // TRANSFORM:
    float px, py, pz;
    // PROP:
    char*  block;
    size_t field_offset;
    int32  old_raw;
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
    enum Kind { SET_PROP, SET_TRANSFORM, PICK, UNDO_STEP, REVERT_ALL } kind;
    int  actor_idx;
    std::string key;
    double value;
    float  px, py, pz;              // SET_TRANSFORM: new position
    float  ray_ox, ray_oy, ray_oz;  // PICK: ray origin
    float  ray_dx, ray_dy, ray_dz;  // PICK: ray direction (unit)
};

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
    if (gServerFd >= 0) { ::close(gServerFd); gServerFd = -1; }
    {
        std::lock_guard<std::mutex> lk(gQueueMutex);
        for (int fd : gClients) ::close(fd);
        gClients.clear();
    }
    if (gListenerThread.joinable()) gListenerThread.join();
    gOriginals.clear();
    gChangeStack.clear();
    gPropOriginals.clear();
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
            gChangeStack.clear();
            std::lock_guard<std::mutex> lk(gQueueMutex);
            send_all_locked("{\"op\":\"reverted\"}\n");

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

#endif // WF_DEBUG_BRIDGE
