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

// POSIX sockets
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

// Level + Actor API
#include "level.hp"
#include "actor.hp"

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
// Pending update queue

struct PendingUpdate {
    enum Kind { SET_PROP, SET_TRANSFORM, PICK } kind;
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
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons((uint16_t)port);

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
            Vector3 pos(Scalar::FromDouble((double)u.px),
                        Scalar::FromDouble((double)u.py),
                        Scalar::FromDouble((double)u.pz));
            actor->setCurrentPos(pos);

        } else if (u.kind == PendingUpdate::SET_PROP) {
            // Phase 1: OAD property writes are acknowledged but not yet applied.
            // Phase 2 will wire directly into the OAD block once the property
            // name→offset map is established.
            std::string msg = "{\"op\":\"log\",\"level\":\"info\","
                + json_int("idx", u.actor_idx) + ","
                + json_str("msg", "scene:set_prop queued (Phase 2b): " + u.key)
                + "}\n";
            std::lock_guard<std::mutex> lk(gQueueMutex);
            send_all_locked(msg);

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

#endif // WF_DEBUG_BRIDGE
