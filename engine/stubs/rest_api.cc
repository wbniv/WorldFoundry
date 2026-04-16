// rest_api.cc — WF REST API implementation (WF_REST_API builds only).
//
// See rest_api.hp for the public interface.

#include "rest_api.hp"

#ifdef WF_REST_API

// TLS not needed for LAN PoC — ensure OpenSSL support is off.
#undef CPPHTTPLIB_OPENSSL_SUPPORT
#include "httplib.h"

#include <GL/gl.h>

#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <future>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <variant>
#include <vector>

//=============================================================================
// Box state

struct BoxRecord {
    float x, y, z;       // world-space centre
    float l, w, h;       // dimensions in metres (full extent, not half-extent)
    float r, g, b, a;    // colour [0,1]
};

static std::mutex                           gBoxMutex;
static std::unordered_map<uint32_t, BoxRecord> gBoxes;
static std::atomic<uint32_t>               gNextId{1};

//=============================================================================
// Minimal JSON helpers — avoids pulling in a JSON library for a PoC.

// Parse a named float from JSON body, e.g. "x":1.23 → 1.23f. Returns NaN if absent.
static float json_float(const std::string& body, const char* key)
{
    std::string needle = std::string("\"") + key + "\"";
    auto pos = body.find(needle);
    if (pos == std::string::npos) return std::nanf("");
    pos = body.find(':', pos + needle.size());
    if (pos == std::string::npos) return std::nanf("");
    // skip whitespace
    while (++pos < body.size() && (body[pos]==' '||body[pos]=='\t'||body[pos]=='\n'||body[pos]=='\r'));
    return std::stof(body.c_str() + pos);
}

// Parse a named string value from JSON, e.g. "color":"#ff0000" → "#ff0000".
static std::string json_string(const std::string& body, const char* key)
{
    std::string needle = std::string("\"") + key + "\"";
    auto pos = body.find(needle);
    if (pos == std::string::npos) return {};
    pos = body.find('"', pos + needle.size() + 1); // find opening quote of value
    if (pos == std::string::npos) return {};
    auto end = body.find('"', pos + 1);
    if (end == std::string::npos) return {};
    return body.substr(pos + 1, end - pos - 1);
}

// Parse CSS hex color "#rrggbb" or "#rrggbbaa" → (r,g,b,a) in [0,1].
// Returns false on parse failure.
static bool parse_color(const std::string& hex, float& r, float& g, float& b, float& a)
{
    const char* s = hex.c_str();
    if (*s == '#') s++;
    auto hex2 = [](const char* p) -> int {
        char buf[3] = { p[0], p[1], 0 };
        return (int)strtol(buf, nullptr, 16);
    };
    size_t len = strlen(s);
    if (len != 6 && len != 8) return false;
    r = hex2(s+0) / 255.0f;
    g = hex2(s+2) / 255.0f;
    b = hex2(s+4) / 255.0f;
    a = (len == 8) ? hex2(s+6) / 255.0f : 1.0f;
    return true;
}

// Format uint32 id as 8-digit hex string.
static std::string id_str(uint32_t id)
{
    char buf[16];
    snprintf(buf, sizeof(buf), "%08x", id);
    return buf;
}

//=============================================================================
// Command queue — HTTP thread pushes, game thread drains.

struct CmdCreate {
    uint32_t id;
    BoxRecord box;
};
struct CmdRecolor {
    uint32_t id;
    float r, g, b, a;
};
struct CmdResize {
    uint32_t id;
    float l, w, h;      // NaN = unchanged
};
struct CmdDestroy {
    uint32_t id;
};

using Cmd = std::variant<CmdCreate, CmdRecolor, CmdResize, CmdDestroy>;

struct QueueEntry {
    Cmd                   cmd;
    std::promise<bool>    done;   // game thread fulfils; true = success
};

static std::mutex               gQueueMutex;
static std::vector<QueueEntry*> gQueue;

static std::future<bool> enqueue(Cmd&& cmd)
{
    auto* entry = new QueueEntry{ std::move(cmd), {} };
    auto fut = entry->done.get_future();
    {
        std::lock_guard<std::mutex> lock(gQueueMutex);
        gQueue.push_back(entry);
    }
    return fut;
}

//=============================================================================
// Route helpers

static std::string box_json(uint32_t id, const BoxRecord& b)
{
    char buf[256];
    snprintf(buf, sizeof(buf),
        "{\"id\":\"%s\","
        "\"x\":%.4f,\"y\":%.4f,\"z\":%.4f,"
        "\"l\":%.4f,\"w\":%.4f,\"h\":%.4f,"
        "\"color\":\"#%02x%02x%02x%02x\"}",
        id_str(id).c_str(),
        b.x, b.y, b.z, b.l, b.w, b.h,
        (int)(b.r*255+.5f), (int)(b.g*255+.5f),
        (int)(b.b*255+.5f), (int)(b.a*255+.5f));
    return buf;
}

static uint32_t path_id(const httplib::Request& req, int param_idx = 0)
{
    // params_ vector: path param values in order of named captures
    const auto& match = req.matches;
    if (param_idx + 1 >= (int)match.size()) return 0;
    return (uint32_t)strtoul(match[param_idx + 1].str().c_str(), nullptr, 16);
}

//=============================================================================
// HTTP server

static httplib::Server* gServer = nullptr;
static std::thread       gServerThread;

void RestApi_Start()
{
    const char* host = getenv("WF_REST_HOST");
    if (!host) host = "127.0.0.1";
    const char* port_env = getenv("WF_REST_PORT");
    int port = port_env ? atoi(port_env) : 8765;

    gServer = new httplib::Server();

    // POST /boxes — create
    gServer->Post("/boxes", [](const httplib::Request& req, httplib::Response& res) {
        BoxRecord b{};
        b.x = json_float(req.body, "x"); if (std::isnan(b.x)) b.x = 0;
        b.y = json_float(req.body, "y"); if (std::isnan(b.y)) b.y = 0;
        b.z = json_float(req.body, "z"); if (std::isnan(b.z)) b.z = 0;
        b.l = json_float(req.body, "l"); if (std::isnan(b.l) || b.l <= 0) b.l = 1;
        b.w = json_float(req.body, "w"); if (std::isnan(b.w) || b.w <= 0) b.w = 1;
        b.h = json_float(req.body, "h"); if (std::isnan(b.h) || b.h <= 0) b.h = 1;
        b.r = b.g = b.b = 1.0f; b.a = 1.0f;
        std::string color_str = json_string(req.body, "color");
        if (!color_str.empty()) parse_color(color_str, b.r, b.g, b.b, b.a);

        uint32_t id = gNextId.fetch_add(1, std::memory_order_relaxed);
        b = b; // already set
        auto fut = enqueue(CmdCreate{id, b});
        bool ok = fut.get();
        if (ok) {
            char buf[64];
            snprintf(buf, sizeof(buf), "{\"id\":\"%s\"}", id_str(id).c_str());
            res.status = 201;
            res.set_content(buf, "application/json");
        } else {
            res.status = 500;
            res.set_content("{\"error\":\"engine rejected command\"}", "application/json");
        }
    });

    // GET /boxes/:id
    gServer->Get(R"(/boxes/([0-9a-f]{8}))", [](const httplib::Request& req, httplib::Response& res) {
        uint32_t id = path_id(req);
        std::lock_guard<std::mutex> lock(gBoxMutex);
        auto it = gBoxes.find(id);
        if (it == gBoxes.end()) {
            res.status = 404;
            res.set_content("{\"error\":\"not found\"}", "application/json");
            return;
        }
        res.set_content(box_json(id, it->second), "application/json");
    });

    // PATCH /boxes/:id/color
    gServer->Patch(R"(/boxes/([0-9a-f]{8})/color)", [](const httplib::Request& req, httplib::Response& res) {
        uint32_t id = path_id(req);
        std::string color_str = json_string(req.body, "color");
        if (color_str.empty()) {
            res.status = 400;
            res.set_content("{\"error\":\"missing 'color'\"}", "application/json");
            return;
        }
        float r, g, b, a;
        if (!parse_color(color_str, r, g, b, a)) {
            res.status = 400;
            res.set_content("{\"error\":\"invalid color format\"}", "application/json");
            return;
        }
        auto fut = enqueue(CmdRecolor{id, r, g, b, a});
        bool ok = fut.get();
        if (ok) {
            std::lock_guard<std::mutex> lock(gBoxMutex);
            auto it = gBoxes.find(id);
            res.set_content(it != gBoxes.end() ? box_json(id, it->second) : "{}", "application/json");
        } else {
            res.status = 404;
            res.set_content("{\"error\":\"not found\"}", "application/json");
        }
    });

    // PATCH /boxes/:id/size
    gServer->Patch(R"(/boxes/([0-9a-f]{8})/size)", [](const httplib::Request& req, httplib::Response& res) {
        uint32_t id = path_id(req);
        float l = json_float(req.body, "l");
        float w = json_float(req.body, "w");
        float h = json_float(req.body, "h");
        // all NaN = pointless but not an error
        auto fut = enqueue(CmdResize{id, l, w, h});
        bool ok = fut.get();
        if (ok) {
            std::lock_guard<std::mutex> lock(gBoxMutex);
            auto it = gBoxes.find(id);
            res.set_content(it != gBoxes.end() ? box_json(id, it->second) : "{}", "application/json");
        } else {
            res.status = 404;
            res.set_content("{\"error\":\"not found\"}", "application/json");
        }
    });

    // DELETE /boxes/:id
    gServer->Delete(R"(/boxes/([0-9a-f]{8}))", [](const httplib::Request& req, httplib::Response& res) {
        uint32_t id = path_id(req);
        auto fut = enqueue(CmdDestroy{id});
        bool ok = fut.get();
        if (ok) {
            res.status = 204;
        } else {
            res.status = 404;
            res.set_content("{\"error\":\"not found\"}", "application/json");
        }
    });

    gServerThread = std::thread([host, port]() {
        std::fprintf(stderr, "rest_api: listening on http://%s:%d\n", host, port);
        gServer->listen(host, port);
        std::fprintf(stderr, "rest_api: server stopped\n");
    });
}

//=============================================================================
// Game-thread command drain

void RestApi_DrainQueue()
{
    std::vector<QueueEntry*> entries;
    {
        std::lock_guard<std::mutex> lock(gQueueMutex);
        entries.swap(gQueue);
    }

    for (auto* entry : entries) {
        bool ok = false;

        if (auto* c = std::get_if<CmdCreate>(&entry->cmd)) {
            std::lock_guard<std::mutex> lock(gBoxMutex);
            gBoxes[c->id] = c->box;
            ok = true;
        }
        else if (auto* c = std::get_if<CmdRecolor>(&entry->cmd)) {
            std::lock_guard<std::mutex> lock(gBoxMutex);
            auto it = gBoxes.find(c->id);
            if (it != gBoxes.end()) {
                it->second.r = c->r; it->second.g = c->g;
                it->second.b = c->b; it->second.a = c->a;
                ok = true;
            }
        }
        else if (auto* c = std::get_if<CmdResize>(&entry->cmd)) {
            std::lock_guard<std::mutex> lock(gBoxMutex);
            auto it = gBoxes.find(c->id);
            if (it != gBoxes.end()) {
                if (!std::isnan(c->l) && c->l > 0) it->second.l = c->l;
                if (!std::isnan(c->w) && c->w > 0) it->second.w = c->w;
                if (!std::isnan(c->h) && c->h > 0) it->second.h = c->h;
                ok = true;
            }
        }
        else if (auto* c = std::get_if<CmdDestroy>(&entry->cmd)) {
            std::lock_guard<std::mutex> lock(gBoxMutex);
            ok = (gBoxes.erase(c->id) > 0);
        }

        entry->done.set_value(ok);
        delete entry;
    }
}

//=============================================================================
// Debug GL wireframe rendering

static void draw_wire_box(float cx, float cy, float cz,
                           float l, float w, float h)
{
    // half-extents
    float hl = l * 0.5f, hw = w * 0.5f, hh = h * 0.5f;

    // 8 corners: bottom face (y = cy-hh), top face (y = cy+hh)
    float x0 = cx - hl, x1 = cx + hl;
    float y0 = cy - hh, y1 = cy + hh;
    float z0 = cz - hw, z1 = cz + hw;

    glBegin(GL_LINES);
    // bottom square
    glVertex3f(x0,y0,z0); glVertex3f(x1,y0,z0);
    glVertex3f(x1,y0,z0); glVertex3f(x1,y0,z1);
    glVertex3f(x1,y0,z1); glVertex3f(x0,y0,z1);
    glVertex3f(x0,y0,z1); glVertex3f(x0,y0,z0);
    // top square
    glVertex3f(x0,y1,z0); glVertex3f(x1,y1,z0);
    glVertex3f(x1,y1,z0); glVertex3f(x1,y1,z1);
    glVertex3f(x1,y1,z1); glVertex3f(x0,y1,z1);
    glVertex3f(x0,y1,z1); glVertex3f(x0,y1,z0);
    // verticals
    glVertex3f(x0,y0,z0); glVertex3f(x0,y1,z0);
    glVertex3f(x1,y0,z0); glVertex3f(x1,y1,z0);
    glVertex3f(x1,y0,z1); glVertex3f(x1,y1,z1);
    glVertex3f(x0,y0,z1); glVertex3f(x0,y1,z1);
    glEnd();
}

void RestApi_RenderBoxes()
{
    std::lock_guard<std::mutex> lock(gBoxMutex);
    if (gBoxes.empty()) return;

    // Save state we're about to change.
    glPushAttrib(GL_CURRENT_BIT | GL_ENABLE_BIT | GL_LINE_BIT);
    glDisable(GL_TEXTURE_2D);
    glDisable(GL_LIGHTING);
    glLineWidth(2.0f);

    for (const auto& [id, b] : gBoxes) {
        glColor4f(b.r, b.g, b.b, b.a);
        draw_wire_box(b.x, b.y, b.z, b.l, b.w, b.h);
    }

    glPopAttrib();
}

//=============================================================================

void RestApi_Stop()
{
    if (gServer) {
        gServer->stop();
        if (gServerThread.joinable()) gServerThread.join();
        delete gServer;
        gServer = nullptr;
    }
}

#endif // WF_REST_API
