// scripting_zforth.cc — zForth backend for forth_engine namespace.
//
// Compiled in when WF_FORTH_ENGINE_ZFORTH is defined (via build_game.sh).
// Sigil: `\` — handled by ScriptRouter before dispatch here; RunScript
// strips the `\ wf` opener line before passing to zf_eval.
//
// Cell type: float (see wf_zfconf.h). Mailbox indices and values flow
// through as floats on PC dev; on the real fixed-point target integer
// values are exact in float representation for typical mailbox indices.
//
// Bridge words (eval'd at Init):
//   : read-mailbox  128 sys ;   \ ZF_SYSCALL_USER+0: ( idx -- val )
//   : write-mailbox 129 sys ;   \ ZF_SYSCALL_USER+1: ( val idx -- )
//   : write-actor-mailbox 130 sys ;   \ ZF_SYSCALL_USER+2: ( val idx actor_idx -- )
//
// Control flow (zForth uses `fi` not `then`):
//   if ... fi        ( flag -- )
//   if ... else ... fi
//   begin ... until  ( flag -- )
//   begin ... again
//   limit start do ... loop
//
// Constants are loaded at AddConstantArray time:
//   3024 constant INDEXOF_INPUT
//   1009 constant INDEXOF_HARDWARE_JOYSTICK1_RAW
//   ...

#ifdef WF_FORTH_ENGINE_ZFORTH

#include "scripting_forth.hp"

extern "C" {
#include <zforth.h>
}

#ifdef WF_NEURAL_FORTH
#include "neural_forth.h"
#endif

#include <scripting/scriptinterpreter.hp>
#include <mailbox/mailbox.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdarg>
#include <string>
#include <unordered_map>
#include <vector>
#include <algorithm>  // std::sort — Filelight orders sibling segments biggest-first
#include <dirent.h>
#include <sys/stat.h>
#include <cmath>      // atan2/cos/sin/sqrt for the FSN connector orientation
#include <ctime>      // time() for FSN file color-by-age

#include "level.hp"   // theLevel global (extern Level* theLevel); pulls in Actor/PhysicalAttributes
#include <math/euler.hp>     // Euler — connector orientation
#include <math/angle.hp>

// ---------------------------------------------------------------------------
// Module state

static zf_ctx              g_ctx;
static MailboxesManager*   g_mgr     = nullptr;
static int                 g_curObj  = 0;

// FSN filesystem syscalls (custom 3-7 / sys 131-135)
struct CwdEntry { std::string name; bool is_dir; int64_t size; };
static std::vector<CwdEntry> g_cwd_entries;

// ---------------------------------------------------------------------------
// FSN Phase 2 — recursive tree builder (custom 8-10 / sys 136-138).
// The whole scan → radial layout → spawn (towers, files-on-tops, connector
// wires) lives here in C++ because zForth has no float trig/sqrt and only a
// 32-deep return stack (no deep recursion, no locals). The Director Forth
// script just calls fsn-config / fsn-build / fsn-navigate.
// See docs/plans/2026-06-12-filesys-browser-level.md.

struct FsnTower { int actorIdx; std::string path; float x, y, topZ; };
static std::vector<FsnTower> g_fsn_towers;    // dir towers in the CURRENT view (descend targets)
static std::vector<int>      g_fsn_spawned;   // every actor spawned this view (despawn on rebuild)
static std::string           g_fsn_root, g_fsn_start;   // current view root; start dir (ascend floor)
static int g_fsn_dirT = 0, g_fsn_fileT = 0, g_fsn_connT = 0;
static int g_fsn_maxDepth = 2, g_fsn_maxNodes = 120, g_fsn_playerIdx = 0;
static bool g_fsn_enterLatch = false, g_fsn_backLatch = false;
static bool g_fsn_pendingBuild = false;   // navigation despawns one frame, respawns the next

static const float FSN_PI = 3.14159265358979f;

// ---------------------------------------------------------------------------
// Filelight — 3D radial disk-usage sunburst (custom 12-21 / sys 140-149).
//
// The §6 split (docs/investigations/2026-06-13-zforth-recursion-stack-extension.md):
// C walks the tree, computes recursive byte sizes, and subdivides the [0,1)
// revolution circle proportionally — emitting a FLAT NUMERIC TABLE of segments.
// The Director .fth iterates the table and applies the render *policy* (size→
// height, hue, wedge tiling) by spawning + rotating + scaling + colouring. No
// string ever crosses to Forth; angles are revolutions (the engine-native Euler
// unit). See docs/plans/2026-06-13-filesystem-viz-on-a-flat-table-forth-policy-core-f.md.
struct FlSeg {
    int         depth;    // 0 = centre disk (cwd); 1.. = ring bands outward
    float       a0, a1;   // arc start/end, REVOLUTIONS ∈ [0,1)
    int64_t     sizeKB;   // recursive subtree size, KiB  (Forth: size→height)
    int         branchId; // depth-1 ancestor index       (Forth: branch→hue)
    std::string path;     // navigation re-root target (never crosses to Forth)
};
static std::vector<FlSeg> g_fl_segments;
static std::string  g_fl_root, g_fl_start;
static int   g_fl_maxDepth    = 3;
static int   g_fl_playerIdx   = 0;
static int   g_fl_branchCount = 0;
static bool  g_fl_pendingBuild = false;
static bool  g_fl_enterLatch = false, g_fl_backLatch = false;
static const float FL_MIN_REV    = 0.012f;  // cull arcs below ~4.3° (and stop recursing)
static const float FL_RING_WIDTH = 9.0f;    // world units per ring band (matches Blender)

// ---------------------------------------------------------------------------
// FSN Phase 3 — retrofit the tree builder to the same flat-table + Forth-policy
// split as Filelight. fsn-scan walks the tree in C (BFS + the fan/connector trig)
// and EMITS a flat numeric table; the filesys Director .fth renders it (tower
// height curve, file age→colour, wire spawn+rotate+scale). Structure (positions,
// angles — the trig) stays C; the *look* moves to Forth (hot-reloadable).
enum { FSN_KIND_TOWER = 0, FSN_KIND_FILE = 1, FSN_KIND_CONN = 2 };
struct FsnNode {
    int   kind;     // tower / file / connector
    float x, y, z;  // spawn position
    float p1;       // tower: child-count (Forth isqrt→height); file: sizeKB; conn: heading rev
    float p2;       // tower: depth; file: age-days (Forth → warm→cool); conn: length L
};
static std::vector<FsnNode> g_fsn_nodes;

static bool fsn_emit(int kind, float x, float y, float z, float p1, float p2) {
    if ((int)g_fsn_nodes.size() >= g_fsn_maxNodes) return false;
    g_fsn_nodes.push_back(FsnNode{ kind, x, y, z, p1, p2 });
    return true;
}

static float fsn_age_days(long mtime) {
    long now = (long)time(nullptr);
    long age = now - mtime; if (age < 0) age = 0;
    return (float)age / 86400.0f;
}

static int fsn_isqrt(int n) { int s = 0; while ((s + 1) * (s + 1) <= n) s++; return s; }

static int fsn_budget_left() { return g_fsn_maxNodes - (int)g_fsn_spawned.size(); }

// Room bbox guard (matches blender_filesys.py ROOM_LOCAL_BBOX, minus a margin):
// SafelyConstructTemplateObject asserts (level.cc:1692) on a spawn outside every
// room, so never hand it an out-of-room position — skip instead.
static const float FSN_X_LIM = 48.0f, FSN_Y_MAX = 53.0f, FSN_Y_MIN = -70.0f;

// Spawn template `tmpl` at (x,y,z); record it; return actor index (0 on failure).
static int fsn_spawn(int tmpl, float x, float y, float z) {
    if (!theLevel || fsn_budget_left() <= 0) return 0;
    if (x < -FSN_X_LIM || x > FSN_X_LIM || y < FSN_Y_MIN || y > FSN_Y_MAX) {
        static int warned = 0;
        if (warned++ < 3) fprintf(stderr, "FSN: skip out-of-room spawn (%.1f,%.1f)\n", x, y);
        return 0;
    }
    Vector3 pos(Scalar::FromFloat(x), Scalar::FromFloat(y), Scalar::FromFloat(z));
    Actor* a = theLevel->ConstructTemplateObject(tmpl, g_curObj, pos, Vector3::zero);
    if (!a) return 0;
    theLevel->AddObject(a, pos);
    int idx = a->GetActorIndex();
    g_fsn_spawned.push_back(idx);
    return idx;
}

// Per-axis scale via the qbert scale mailboxes (3040-3042) — same path as set-z-scale.
static void fsn_set_scale(int idx, float sx, float sy, float sz) {
    if (!g_mgr || !idx) return;
    Mailboxes& mb = g_mgr->LookupMailboxes(idx);
    mb.WriteMailbox(3040, Scalar::FromFloat(sx));
    mb.WriteMailbox(3041, Scalar::FromFloat(sy));
    mb.WriteMailbox(3042, Scalar::FromFloat(sz));
}

// Override an actor's material colour on all three faces (mailboxes 3037-3039,
// packed 0xRRGGBB) — the qbert per-cube colour path.
static void fsn_set_color(int idx, int r, int g, int b) {
    if (!g_mgr || !idx) return;
    float packed = (float)(((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF));
    Mailboxes& mb = g_mgr->LookupMailboxes(idx);
    mb.WriteMailbox(3037, Scalar::FromFloat(packed));   // FACE_COLOR_TOP
    mb.WriteMailbox(3038, Scalar::FromFloat(packed));   // FACE_COLOR_LIT
    mb.WriteMailbox(3039, Scalar::FromFloat(packed));   // FACE_COLOR_SHADOW
}

// Camera fly-down: ease the CamShot from the high establishing pose to the play
// pose over FSN_FLY_SECS, given the level clock t (seconds). The bungee camera
// follows the camshot. Poses must match blender_filesys.py (CAM_OFFSET high start).
static void fsn_flydown(int camIdx, float t) {
    if (!g_mgr || !camIdx) return;
    const float SECS = 2.5f;
    const float HY = -100.0f, HZ = 90.0f, PY = -70.0f, PZ = 41.0f;   // high → play
    float f = t / SECS; if (f < 0.0f) f = 0.0f; if (f > 1.0f) f = 1.0f;
    Mailboxes& mb = g_mgr->LookupMailboxes(camIdx);
    mb.WriteMailbox(3010, Scalar::FromFloat(HY + (PY - HY) * f));   // EMAILBOX_Y_POS
    mb.WriteMailbox(3011, Scalar::FromFloat(HZ + (PZ - HZ) * f));   // EMAILBOX_Z_POS
}

// FSN file colour-by-age: warm (new) → cool (old) over ~a year of mtime.
static void fsn_color_by_age(int idx, long mtime) {
    long now = (long)time(nullptr);
    long age = now - mtime; if (age < 0) age = 0;
    float t = (float)age / (365.0f * 86400.0f);   // 0 = brand new … 1 = a year+ old
    if (t > 1.0f) t = 1.0f;
    int r = (int)(255.0f * (1.0f - t) +  40.0f * t);   // 255 → 40
    int g = (int)( 90.0f * (1.0f - t) + 130.0f * t);   //  90 → 130
    int b = (int)( 40.0f * (1.0f - t) + 255.0f * t);   //  40 → 255
    fsn_set_color(idx, r, g, b);
}

// FSN connector wire: a base-pivot unit beam (local +X ∈ [0,1]) spawned at p1,
// rotated so +X aims at p2 (flat: heading only), and X-scaled to the distance.
static void fsn_spawn_connector(float x1, float y1, float z1, float x2, float y2) {
    float dx = x2 - x1, dy = y2 - y1;
    float L = std::sqrt(dx * dx + dy * dy);
    if (L < 0.01f) return;
    int idx = fsn_spawn(g_fsn_connT, x1, y1, z1);
    if (!idx) return;
    float headingRev = std::atan2(dy, dx) / (2.0f * FSN_PI);   // WF Euler C is in revolutions
    Actor* a = theLevel->getActor(idx);
    if (a) {
        a->GetWritablePhysicalAttributes().SetRotation(
            Euler(Angle::Revolution(Scalar::zero),
                  Angle::Revolution(Scalar::zero),
                  Angle::Revolution(Scalar::FromFloat(headingRev))));
    }
    fsn_set_scale(idx, L, 1.0f, 1.0f);   // stretch local +X to span the gap
}

// Recursively scan `dir` (skip hidden; lstat → never follow symlinks → loop-safe).
struct FsnEntry { std::string name, path; bool is_dir; int64_t size; long mtime; };
static void fsn_scan(const std::string& dir, std::vector<FsnEntry>& out) {
    out.clear();
    DIR* d = opendir(dir.c_str());
    if (!d) return;
    struct dirent* ent;
    while ((ent = readdir(d)) != nullptr) {
        if (ent->d_name[0] == '.') continue;                  // hidden, '.' and '..'
        std::string full = dir + "/" + ent->d_name;
        struct stat st;
        if (lstat(full.c_str(), &st) != 0) continue;          // skip on stat failure
        if (S_ISLNK(st.st_mode)) continue;                    // never follow symlinks
        FsnEntry e;
        e.name = ent->d_name; e.path = full;
        e.is_dir = S_ISDIR(st.st_mode);
        e.size   = e.is_dir ? 0 : (int64_t)st.st_size;
        e.mtime  = (long)st.st_mtime;
        out.push_back(e);
    }
    closedir(d);
}

// Files are secondary to the tree, so cap how many a node shows (the rest are
// implied) — otherwise a file-heavy dir eats the whole actor budget and the
// tower tree starves.
static const int FSN_MAX_FILES_PER_NODE = 6;

// Ring up to N of a node's files on its tower top (z=topZ), scaled by √size.
static void fsn_place_files(const std::vector<FsnEntry>& entries, float x, float y, float topZ) {
    int nf = 0; for (auto& e : entries) if (!e.is_dir) nf++;
    if (nf > FSN_MAX_FILES_PER_NODE) nf = FSN_MAX_FILES_PER_NODE;
    int fi = 0;
    for (auto& e : entries) {
        if (e.is_dir) continue;
        if (fi >= nf || fsn_budget_left() <= 0) break;
        float ang = (nf > 1) ? (2.0f * FSN_PI * (float)fi / (float)nf) : 0.0f;
        float fr  = (nf > 1) ? 0.6f : 0.0f;
        float fx = x + fr * std::cos(ang), fy = y + fr * std::sin(ang);
        int fh = fsn_isqrt((int)(e.size / 1000)); if (fh < 1) fh = 1; if (fh > 4) fh = 4;
        int file = fsn_spawn(g_fsn_fileT, fx, fy, topZ);
        if (file) { fsn_set_scale(file, 1.0f, 1.0f, (float)fh); fsn_color_by_age(file, e.mtime); }
        fi++;
    }
}

// A queued tree node: render its tower when dequeued, wire it to its parent.
struct FsnJob { std::string path; float x, y, px, py; int depth; };

// Mark the current view's actors for removal (freed at end of frame).
static void fsn_despawn() {
    if (theLevel) {
        for (int idx : g_fsn_spawned) {
            BaseObject* o = theLevel->GetObject(idx);
            if (o) theLevel->SetPendingRemove(o);
        }
    }
    g_fsn_spawned.clear();
    g_fsn_towers.clear();
}

// Spawn the tree for g_fsn_root, BREADTH-FIRST (assumes the previous view was
// already despawned). The ROOT (CWD) gets NO tower — the player stands there;
// its files ring the standpoint and its child dirs fan across the +Y half-field
// in front of the player (camera looks from -Y). BFS spreads the node budget
// across breadth before depth, so siblings appear instead of one subtree clumping.
static int fsn_spawn_tree() {
    std::vector<FsnEntry> entries;
    fsn_scan(g_fsn_root, entries);

    // Root files: a low ring of slabs around the standpoint (radius 6), capped.
    int nf = 0; for (auto& e : entries) if (!e.is_dir) nf++;
    if (nf > 10) nf = 10;
    int fi = 0;
    for (auto& e : entries) {
        if (e.is_dir) continue;
        if (fi >= nf) break;
        float ang = (nf > 1) ? (2.0f * FSN_PI * (float)fi / (float)nf) : 0.0f;
        float fx = 6.0f * std::cos(ang), fy = 6.0f * std::sin(ang);
        int fh = fsn_isqrt((int)(e.size / 1000)); if (fh < 1) fh = 1; if (fh > 4) fh = 4;
        int file = fsn_spawn(g_fsn_fileT, fx, fy, 0.0f);
        if (file) { fsn_set_scale(file, 1.0f, 1.0f, (float)fh); fsn_color_by_age(file, e.mtime); }
        fi++;
    }

    // Seed the BFS queue with the root's child dirs, fanned wide across +Y (15°..165°).
    std::vector<FsnJob> q;
    int nd = 0; for (auto& e : entries) if (e.is_dir) nd++;
    int ci = 0;
    for (auto& e : entries) {
        if (!e.is_dir) continue;
        float t = (nd > 1) ? ((float)ci / (float)(nd - 1)) : 0.5f;
        float a = (15.0f + 150.0f * t) * (FSN_PI / 180.0f);
        q.push_back(FsnJob{ e.path, 30.0f * std::cos(a), 30.0f * std::sin(a), 0.0f, 0.0f, 1 });
        ci++;
    }

    // Process breadth-first: each job spawns its wire-to-parent + tower + files,
    // then enqueues its own child dirs fanned on a cone pointing away from centre.
    for (size_t qi = 0; qi < q.size(); ++qi) {
        if (fsn_budget_left() <= 1) break;             // 1 for the connector + 1 for the tower
        FsnJob job = q[qi];
        fsn_spawn_connector(job.px, job.py, 0.3f, job.x, job.y);

        std::vector<FsnEntry> sub;
        fsn_scan(job.path, sub);
        int h = fsn_isqrt((int)sub.size()); if (h < 1) h = 1; if (h > 6) h = 6;
        int tower = fsn_spawn(g_fsn_dirT, job.x, job.y, 0.0f);
        if (!tower) continue;
        fsn_set_scale(tower, 1.0f, 1.0f, (float)h);
        float topZ = 2.0f * (float)h;
        g_fsn_towers.push_back(FsnTower{ tower, job.path, job.x, job.y, topZ });
        fsn_place_files(sub, job.x, job.y, topZ);

        if (job.depth < g_fsn_maxDepth) {
            int snd = 0; for (auto& e : sub) if (e.is_dir) snd++;
            float R = (job.depth == 1) ? 16.0f : 10.0f;
            float outward = std::atan2(job.y, job.x);  // fan away from the field centre
            int si = 0;
            for (auto& e : sub) {
                if (!e.is_dir) continue;
                float frac = (snd > 1) ? ((float)si / (float)(snd - 1) - 0.5f) : 0.0f;
                float ang  = outward + (FSN_PI * 0.78f) * frac;   // ±70° cone
                q.push_back(FsnJob{ e.path, job.x + R * std::cos(ang),
                                    job.y + R * std::sin(ang), job.x, job.y, job.depth + 1 });
                si++;
            }
        }
    }
    return (int)g_fsn_spawned.size();
}

// Initial / full rebuild in one call (used by fsn-build at startup, where nothing
// is spawned yet so there is no 2× pool peak). Navigation instead despawns one
// frame and respawns the next (fsn_navigate), so the freed slots are reusable.
static int fsn_build() {
    fsn_despawn();
    return fsn_spawn_tree();
}

// ---------------------------------------------------------------------------
// FSN Phase 3 — EMIT versions: same walk + trig as fsn_spawn_tree/place_files,
// but push flat rows instead of spawning. The filesys Director renders the rows.
// Budget is capped on the row count (nothing is spawned yet during the emit).
// Note: topZ (file-on-top Z) uses the default isqrt height so file slabs sit on
// the tower tops; the Director's tower-height word matches it by construction.
static void fsn_emit_place_files(const std::vector<FsnEntry>& entries, float x, float y, float topZ) {
    int nf = 0; for (auto& e : entries) if (!e.is_dir) nf++;
    if (nf > FSN_MAX_FILES_PER_NODE) nf = FSN_MAX_FILES_PER_NODE;
    int fi = 0;
    for (auto& e : entries) {
        if (e.is_dir) continue;
        if (fi >= nf) break;
        float ang = (nf > 1) ? (2.0f * FSN_PI * (float)fi / (float)nf) : 0.0f;
        float fr  = (nf > 1) ? 0.6f : 0.0f;
        float fx = x + fr * std::cos(ang), fy = y + fr * std::sin(ang);
        if (!fsn_emit(FSN_KIND_FILE, fx, fy, topZ, (float)(e.size / 1000), fsn_age_days(e.mtime))) break;
        fi++;
    }
}

static int fsn_emit_tree() {
    g_fsn_nodes.clear();
    g_fsn_towers.clear();
    std::vector<FsnEntry> entries;
    fsn_scan(g_fsn_root, entries);

    // Root files: a low ring of slabs around the standpoint (radius 6), capped.
    int nf = 0; for (auto& e : entries) if (!e.is_dir) nf++;
    if (nf > 10) nf = 10;
    int fi = 0;
    for (auto& e : entries) {
        if (e.is_dir) continue;
        if (fi >= nf) break;
        float ang = (nf > 1) ? (2.0f * FSN_PI * (float)fi / (float)nf) : 0.0f;
        float fx = 6.0f * std::cos(ang), fy = 6.0f * std::sin(ang);
        fsn_emit(FSN_KIND_FILE, fx, fy, 0.0f, (float)(e.size / 1000), fsn_age_days(e.mtime));
        fi++;
    }

    // Seed the BFS queue with the root's child dirs, fanned wide across +Y (15°..165°).
    std::vector<FsnJob> q;
    int nd = 0; for (auto& e : entries) if (e.is_dir) nd++;
    int ci = 0;
    for (auto& e : entries) {
        if (!e.is_dir) continue;
        float t = (nd > 1) ? ((float)ci / (float)(nd - 1)) : 0.5f;
        float a = (15.0f + 150.0f * t) * (FSN_PI / 180.0f);
        q.push_back(FsnJob{ e.path, 30.0f * std::cos(a), 30.0f * std::sin(a), 0.0f, 0.0f, 1 });
        ci++;
    }

    for (size_t qi = 0; qi < q.size(); ++qi) {
        if ((int)g_fsn_nodes.size() >= g_fsn_maxNodes - 1) break;   // room for connector + tower
        FsnJob job = q[qi];

        // connector wire: base-to-base, heading + length computed in C (the trig).
        float dx = job.x - job.px, dy = job.y - job.py;
        float L = std::sqrt(dx * dx + dy * dy);
        if (L >= 0.01f) {
            float hRev = std::atan2(dy, dx) / (2.0f * FSN_PI);
            fsn_emit(FSN_KIND_CONN, job.px, job.py, 0.3f, hRev, L);
        }

        std::vector<FsnEntry> sub;
        fsn_scan(job.path, sub);
        int h = fsn_isqrt((int)sub.size()); if (h < 1) h = 1; if (h > 6) h = 6;   // topZ placement
        if (!fsn_emit(FSN_KIND_TOWER, job.x, job.y, 0.0f, (float)sub.size(), (float)job.depth)) continue;
        float topZ = 2.0f * (float)h;
        g_fsn_towers.push_back(FsnTower{ 0, job.path, job.x, job.y, topZ });
        fsn_emit_place_files(sub, job.x, job.y, topZ);

        if (job.depth < g_fsn_maxDepth) {
            int snd = 0; for (auto& e : sub) if (e.is_dir) snd++;
            float R = (job.depth == 1) ? 16.0f : 10.0f;
            float outward = std::atan2(job.y, job.x);   // fan away from the field centre
            int si = 0;
            for (auto& e : sub) {
                if (!e.is_dir) continue;
                float frac = (snd > 1) ? ((float)si / (float)(snd - 1) - 0.5f) : 0.0f;
                float ang  = outward + (FSN_PI * 0.78f) * frac;   // ±70° cone
                q.push_back(FsnJob{ e.path, job.x + R * std::cos(ang),
                                    job.y + R * std::sin(ang), job.x, job.y, job.depth + 1 });
                si++;
            }
        }
    }
    return (int)g_fsn_nodes.size();
}

// Warp the player back to the standpoint (origin, just above the floor) — the
// centre of the freshly-built view after a descend/ascend.
static void fsn_reset_player() {
    if (!g_mgr || !g_fsn_playerIdx) return;
    Mailboxes& mb = g_mgr->LookupMailboxes(g_fsn_playerIdx);
    mb.WriteMailbox(3009, Scalar::FromFloat(0.0f));   // X_POS
    mb.WriteMailbox(3010, Scalar::FromFloat(0.0f));   // Y_POS
    mb.WriteMailbox(3011, Scalar::FromFloat(1.0f));   // Z_POS
}

// Per-frame navigation + play-area bounds (custom 10 / sys 138). Called by the
// Director every frame. Button B (bit 2) descends into the nearest dir tower
// within reach; button C (bit 4) ascends to the parent (floored at the start
// dir). The rebuild is deferred one frame to avoid a 2× actor-pool peak.
static int fsn_navigate() {
    if (!theLevel || !g_mgr || !g_fsn_playerIdx) return 0;

    // Deferred rebuild: the frame after a navigate despawn, the old actors have
    // been freed (removePendingObjects). The render lives in Forth now, so just
    // warp the player home and signal the Director to re-scan + re-render.
    if (g_fsn_pendingBuild) {
        g_fsn_pendingBuild = false;
        fsn_reset_player();
        return 1;
    }

    Actor* player = theLevel->getActor(g_fsn_playerIdx);
    if (!ValidPtr(player)) return 0;
    Vector3 p = player->currentPos();
    float px = p.X().AsFloat(), py = p.Y().AsFloat(), pz = p.Z().AsFloat();

    // Play-area bounds: clamp the player onto the floor so it can't walk off into
    // the void (which falls out of the room and trips the bungee-cam assert).
    {
        const float BX = 44.0f, BY0 = -36.0f, BY1 = 48.0f;
        bool clamp = false;
        if (px < -BX)  { px = -BX;  clamp = true; }
        if (px >  BX)  { px =  BX;  clamp = true; }
        if (py <  BY0) { py =  BY0; clamp = true; }
        if (py >  BY1) { py =  BY1; clamp = true; }
        if (pz <  0.0f){ pz =  0.5f;clamp = true; }
        if (clamp) {
            Mailboxes& mb = g_mgr->LookupMailboxes(g_fsn_playerIdx);
            mb.WriteMailbox(3009, Scalar::FromFloat(px));
            mb.WriteMailbox(3010, Scalar::FromFloat(py));
            mb.WriteMailbox(3011, Scalar::FromFloat(pz));
        }
    }

    int buttons = (int)g_mgr->LookupMailboxes(g_curObj).ReadMailbox(1909).AsFloat();  // raw joystick
    bool enterDown = (buttons & 2) != 0;   // button B
    bool backDown  = (buttons & 4) != 0;   // button C

    // Descend: on the rising edge of B, re-root into the nearest tower in reach.
    if (enterDown && !g_fsn_enterLatch) {
        g_fsn_enterLatch = true;
        int best = -1; float bestD2 = 1e18f;
        for (size_t i = 0; i < g_fsn_towers.size(); ++i) {
            float dx = g_fsn_towers[i].x - px, dy = g_fsn_towers[i].y - py;
            float d2 = dx * dx + dy * dy;
            if (d2 < bestD2) { bestD2 = d2; best = (int)i; }
        }
        const float ENTER_R2 = 8.0f * 8.0f;
        if (best >= 0 && bestD2 < ENTER_R2) {
            g_fsn_root = g_fsn_towers[best].path;
            fsn_despawn();
            g_fsn_pendingBuild = true;
        }
    }
    if (!enterDown) g_fsn_enterLatch = false;

    // Ascend: on the rising edge of C, re-root to the parent dir (not above start).
    if (backDown && !g_fsn_backLatch) {
        g_fsn_backLatch = true;
        if (g_fsn_root != g_fsn_start) {
            size_t slash = g_fsn_root.find_last_of('/');
            g_fsn_root = (slash == std::string::npos || slash == 0)
                         ? g_fsn_start : g_fsn_root.substr(0, slash);
            fsn_despawn();
            g_fsn_pendingBuild = true;
        }
    }
    if (!backDown) g_fsn_backLatch = false;
    return 0;
}

// ---------------------------------------------------------------------------
// Filelight helpers — structure only (the C side of the §6 split).

// Recursive byte sum under `dir`. statBudget caps total stat() calls so a huge
// tree can't stall a frame; when it bottoms out we stop descending.
static int64_t fl_subtree_bytes(const std::string& dir, int& statBudget) {
    if (statBudget <= 0) return 0;
    int64_t total = 0;
    std::vector<FsnEntry> entries;
    fsn_scan(dir, entries);                 // skips hidden / '.' '..'; lstat; no symlinks
    for (const FsnEntry& e : entries) {
        if (--statBudget <= 0) break;
        if (e.is_dir) total += fl_subtree_bytes(e.path, statBudget);
        else          total += e.size;
    }
    return total;
}

// Push the node's own row, then split its arc ∝ child subtree-bytes and recurse.
// Depth 0 = the centre disk (full [0,1) turn). Loose files fold into the node's
// size (the Filelight default: dirs fan, files don't get their own wedge).
static void fl_subdivide(const std::string& path, int depth, float a0, float a1,
                         int branchId, int64_t myBytes, int& statBudget) {
    g_fl_segments.push_back(FlSeg{ depth, a0, a1, myBytes / 1024, branchId, path });
    if (depth >= g_fl_maxDepth || (a1 - a0) < FL_MIN_REV || statBudget <= 0) return;

    std::vector<FsnEntry> entries;
    fsn_scan(path, entries);
    struct Kid { std::string path; int64_t bytes; };
    std::vector<Kid> kids;
    int64_t total = 0;
    for (const FsnEntry& e : entries) {
        if (!e.is_dir) continue;            // files already folded into myBytes
        int64_t kb = fl_subtree_bytes(e.path, statBudget);
        kids.push_back(Kid{ e.path, kb });
        total += kb;
    }
    if (total <= 0) return;
    std::sort(kids.begin(), kids.end(),
              [](const Kid& a, const Kid& b) { return a.bytes > b.bytes; });  // biggest first

    float a = a0;
    for (const Kid& k : kids) {
        float span = (a1 - a0) * (float)((double)k.bytes / (double)total);
        if (span < FL_MIN_REV) break;       // cull the small tail (keeps the actor budget sane)
        fl_subdivide(k.path, depth + 1, a, a + span,
                     depth == 0 ? g_fl_branchCount++ : branchId, k.bytes, statBudget);
        a += span;
    }
}

// Rebuild the segment table for the current root. Returns the row count.
static int fl_scan() {
    g_fl_segments.clear();
    g_fl_branchCount = 0;
    int statBudget = 200000;
    int64_t rootBytes = fl_subtree_bytes(g_fl_root, statBudget);
    fl_subdivide(g_fl_root, 0, 0.0f, 1.0f, 0, rootBytes, statBudget);
    return (int)g_fl_segments.size();
}

// Camera fly-down for the centred sunburst: high overhead → angled play pose.
static void fl_flydown(int camIdx, float t) {
    if (!g_mgr || !camIdx) return;
    const float SECS = 2.5f;
    const float HY = -55.0f, HZ = 96.0f, PY = -30.0f, PZ = 88.0f;   // high → steep top-down
    float f = t / SECS; if (f < 0.0f) f = 0.0f; if (f > 1.0f) f = 1.0f;
    Mailboxes& mb = g_mgr->LookupMailboxes(camIdx);
    mb.WriteMailbox(3010, Scalar::FromFloat(HY + (PY - HY) * f));   // EMAILBOX_Y_POS
    mb.WriteMailbox(3011, Scalar::FromFloat(HZ + (PZ - HZ) * f));   // EMAILBOX_Z_POS
}

// Per-frame navigation. The render lives in Forth, so we only flag a rebuild:
// returns 1 on the frame the Director should (re)render, else 0. Re-root despawn
// happens here in C (frame N); the deferred frame (N+1) returns 1 so Forth
// re-runs fl-scan + its tile loop into the freed slots.
static int fl_navigate() {
    if (!theLevel || !g_mgr || !g_fl_playerIdx) return 0;

    if (g_fl_pendingBuild) {                 // deferred frame: old actors freed → render now
        g_fl_pendingBuild = false;
        Mailboxes& mb = g_mgr->LookupMailboxes(g_fl_playerIdx);
        mb.WriteMailbox(3009, Scalar::FromFloat(0.0f));   // warp player back to centre
        mb.WriteMailbox(3010, Scalar::FromFloat(0.0f));
        mb.WriteMailbox(3011, Scalar::FromFloat(1.0f));
        return 1;
    }

    // Headless regression hook: WF_FL_TEST_DESCEND=1 drives a descend (~3 s, into
    // the largest depth-1 segment) then an ascend (~6 s) with no input device, so
    // the despawn→re-scan→re-render path can be smoke-tested. No effect unset.
    if (getenv("WF_FL_TEST_DESCEND")) {
        static int s_n = 0;
        s_n++;
        if (s_n == 8) {                      // descend into the largest depth-1 segment
            for (const FlSeg& s : g_fl_segments)
                if (s.depth == 1) { g_fl_root = s.path; fsn_despawn(); g_fl_pendingBuild = true; break; }
            fprintf(stderr, "FL-TEST: descend(frame %d) → '%s'\n", s_n, g_fl_root.c_str());
            return 0;
        }
        if (s_n == 20) {                      // ascend back to the parent
            if (g_fl_root != g_fl_start) {
                size_t slash = g_fl_root.find_last_of('/');
                g_fl_root = (slash == std::string::npos || slash == 0)
                            ? g_fl_start : g_fl_root.substr(0, slash);
                fsn_despawn(); g_fl_pendingBuild = true;
            }
            fprintf(stderr, "FL-TEST: ascend(frame %d) → '%s'\n", s_n, g_fl_root.c_str());
            return 0;
        }
    }

    Actor* player = theLevel->getActor(g_fl_playerIdx);
    if (!ValidPtr(player)) return 0;
    Vector3 p = player->currentPos();
    float px = p.X().AsFloat(), py = p.Y().AsFloat(), pz = p.Z().AsFloat();

    // Disk play-bounds: clamp r ≤ outer ring radius so the astronaut stays on the relief.
    float r = std::sqrt(px * px + py * py);
    float rMax = (float)(g_fl_maxDepth + 1) * FL_RING_WIDTH - 1.0f;
    bool clamp = false;
    if (r > rMax)   { float s = rMax / r; px *= s; py *= s; clamp = true; }
    if (pz < 0.0f)  { pz = 0.5f; clamp = true; }
    if (clamp) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_fl_playerIdx);
        mb.WriteMailbox(3009, Scalar::FromFloat(px));
        mb.WriteMailbox(3010, Scalar::FromFloat(py));
        mb.WriteMailbox(3011, Scalar::FromFloat(pz));
    }

    int buttons = (int)g_mgr->LookupMailboxes(g_curObj).ReadMailbox(1909).AsFloat();
    bool enterDown = (buttons & 2) != 0;   // button B — zoom into the wedge under foot
    bool backDown  = (buttons & 4) != 0;   // button C — ascend

    // Descend: must be standing out on the rings (r ≥ one band), then the polar
    // angle picks the depth-1 segment to re-root into.
    if (enterDown && !g_fl_enterLatch) {
        g_fl_enterLatch = true;
        if (r >= FL_RING_WIDTH) {
            float th = std::atan2(py, px) / (2.0f * FSN_PI);   // revolutions
            if (th < 0.0f) th += 1.0f;
            for (const FlSeg& s : g_fl_segments) {
                if (s.depth != 1) continue;
                if (th >= s.a0 && th < s.a1) {
                    g_fl_root = s.path;
                    fsn_despawn();
                    g_fl_pendingBuild = true;
                    break;
                }
            }
        }
    }
    if (!enterDown) g_fl_enterLatch = false;

    // Ascend: re-root to the parent dir (not above the start dir).
    if (backDown && !g_fl_backLatch) {
        g_fl_backLatch = true;
        if (g_fl_root != g_fl_start) {
            size_t slash = g_fl_root.find_last_of('/');
            g_fl_root = (slash == std::string::npos || slash == 0)
                        ? g_fl_start : g_fl_root.substr(0, slash);
            fsn_despawn();
            g_fl_pendingBuild = true;
        }
    }
    if (!backDown) g_fl_backLatch = false;
    return 0;
}

// Cache: src pointer → compiled word name.
// Scripts are compiled once on first call; subsequent calls just invoke the word.
static std::unordered_map<const char*, std::string> g_scriptCache;

// Debug-bridge per-actor script overrides: actor_idx → compiled word name.
// Populated by ReloadActorScript; consulted by RunScript before the
// src-pointer cache. zForth's dict is append-only, so reloads accumulate
// orphaned definitions in the global dict — restart the engine after
// ~100 reloads (ZF_DICT_SIZE = 64 KB).
static std::unordered_map<int, std::string> g_actorOverride;
static int g_reloadCounter = 0;

// Map zForth result codes to printable strings for error replies.
static const char* zf_result_str(zf_result r)
{
    switch (r) {
        case ZF_OK:                       return "ok";
        case ZF_ABORT_INTERNAL_ERROR:     return "internal_error";
        case ZF_ABORT_OUTSIDE_MEM:        return "outside_mem";
        case ZF_ABORT_DSTACK_UNDERRUN:    return "dstack_underrun";
        case ZF_ABORT_DSTACK_OVERRUN:     return "dstack_overrun";
        case ZF_ABORT_RSTACK_UNDERRUN:    return "rstack_underrun";
        case ZF_ABORT_RSTACK_OVERRUN:     return "rstack_overrun";
        case ZF_ABORT_NOT_A_WORD:         return "not_a_word";
        case ZF_ABORT_COMPILE_ONLY_WORD:  return "compile_only_word";
        case ZF_ABORT_INVALID_SIZE:       return "invalid_size";
        case ZF_ABORT_DIVISION_BY_ZERO:   return "division_by_zero";
        case ZF_ABORT_INVALID_USERVAR:    return "invalid_uservar";
        case ZF_ABORT_EXTERNAL:           return "external";
        default:                          return "unknown";
    }
}

// ---------------------------------------------------------------------------
// Required zForth host callbacks

// System call dispatcher.
// Standard syscalls (EMIT, PRINT, TELL) route to stderr.
// WF custom syscalls (ZF_SYSCALL_USER+0/+1) implement the mailbox bridge.
zf_input_state zf_host_sys(zf_ctx* ctx, zf_syscall_id id, const char* /*last_word*/)
{
    switch (id) {
        case ZF_SYSCALL_EMIT: {
            char c = (char)zf_pop(ctx);
            fputc(c, stderr);
            break;
        }
        case ZF_SYSCALL_PRINT: {
            zf_cell v = zf_pop(ctx);
            fprintf(stderr, ZF_CELL_FMT " ", v);
            break;
        }
        case ZF_SYSCALL_TELL: {
            // TELL: ( addr len -- ) print string from dict
            zf_cell len  = zf_pop(ctx);
            zf_cell addr = zf_pop(ctx);
            // Access dict memory via dump to avoid internal struct coupling.
            // For WF builds this is only used by Forth's own I/O words, not
            // by game scripts, so a simple fprintf is fine.
            (void)len; (void)addr;
            break;
        }
        default: {
            // Custom WF syscalls
            int custom = (int)id - (int)ZF_SYSCALL_USER;
            if (custom == 0) {
                // read-mailbox ( idx -- val )
                int idx = (int)zf_pop(ctx);
                if (g_mgr) {
                    Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
                    float v = mb.ReadMailbox(idx).AsFloat();
                    zf_push(ctx, (zf_cell)v);
                } else {
                    zf_push(ctx, (zf_cell)0.0f);
                }
            } else if (custom == 1) {
                // write-mailbox ( val idx -- )
                int   idx = (int)zf_pop(ctx);
                float val = (float)zf_pop(ctx);
                if (g_mgr) {
                    Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
                    mb.WriteMailbox(idx, Scalar::FromFloat(val));
                }
            } else if (custom == 2) {
                // write-actor-mailbox ( val idx actor_idx -- )
                // Writes mailbox `idx` on the actor identified by `actor_idx`,
                // not the currently-running actor. Needed for the qbert
                // director to set per-cube material color overrides
                // (LOCAL_SYSTEM mailboxes 3037..3039) — a normal write-mailbox
                // would target the director's own override, not the cube's.
                int   actorIdx = (int)zf_pop(ctx);
                int   idx      = (int)zf_pop(ctx);
                float val      = (float)zf_pop(ctx);
                if (g_mgr) {
                    Mailboxes& mb = g_mgr->LookupMailboxes(actorIdx);
                    mb.WriteMailbox(idx, Scalar::FromFloat(val));
                }
            } else if (custom == 3) {
                // cwd-scan ( -- n )
                // Scan CWD, populate g_cwd_entries (skipping . and ..), push count.
                g_cwd_entries.clear();
                DIR* d = opendir(".");
                if (d) {
                    struct dirent* ent;
                    while ((ent = readdir(d)) != nullptr) {
                        if (ent->d_name[0] == '.') continue;
                        struct stat st;
                        if (stat(ent->d_name, &st) != 0) continue;
                        CwdEntry ce;
                        ce.name   = ent->d_name;
                        ce.is_dir = S_ISDIR(st.st_mode);
                        ce.size   = ce.is_dir ? 0 : (int64_t)st.st_size;
                        g_cwd_entries.push_back(ce);
                    }
                    closedir(d);
                }
                zf_push(ctx, (zf_cell)(float)g_cwd_entries.size());
            } else if (custom == 4) {
                // cwd-is-dir ( i -- bool )
                int i = (int)zf_pop(ctx);
                bool is_dir = (i >= 0 && i < (int)g_cwd_entries.size())
                              ? g_cwd_entries[i].is_dir : false;
                zf_push(ctx, (zf_cell)(is_dir ? 1.0f : 0.0f));
            } else if (custom == 5) {
                // cwd-file-size ( i -- bytes )
                int i = (int)zf_pop(ctx);
                float sz = (i >= 0 && i < (int)g_cwd_entries.size())
                           ? (float)g_cwd_entries[i].size : 0.0f;
                zf_push(ctx, (zf_cell)sz);
            } else if (custom == 6) {
                // cwd-dir-count ( i -- n )
                // Count non-hidden entries in subdir g_cwd_entries[i].name.
                int i = (int)zf_pop(ctx);
                int count = 0;
                if (i >= 0 && i < (int)g_cwd_entries.size() && g_cwd_entries[i].is_dir) {
                    DIR* d = opendir(g_cwd_entries[i].name.c_str());
                    if (d) {
                        struct dirent* ent;
                        while ((ent = readdir(d)) != nullptr)
                            if (ent->d_name[0] != '.') ++count;
                        closedir(d);
                    }
                }
                zf_push(ctx, (zf_cell)(float)count);
            } else if (custom == 7) {
                // spawn-template ( x y z tmpl -- actor )
                // Pop tmpl index and position; spawn via Level::ConstructTemplateObject;
                // push the new actor's index.
                int   tmpl = (int)zf_pop(ctx);
                float z    = (float)zf_pop(ctx);
                float y    = (float)zf_pop(ctx);
                float x    = (float)zf_pop(ctx);
                int   idx  = 0;
                if (theLevel) {
                    Vector3 pos(Scalar::FromFloat(x), Scalar::FromFloat(y), Scalar::FromFloat(z));
                    Actor* a = theLevel->ConstructTemplateObject(tmpl, g_curObj, pos, Vector3::zero);
                    if (a) {
                        theLevel->AddObject(a, pos);
                        idx = a->GetActorIndex();
                    }
                }
                zf_push(ctx, (zf_cell)(float)idx);
            } else if (custom == 8) {
                // fsn-config ( dirT fileT connT maxDepth maxNodes playerIdx -- )
                g_fsn_playerIdx = (int)zf_pop(ctx);
                g_fsn_maxNodes  = (int)zf_pop(ctx);
                g_fsn_maxDepth  = (int)zf_pop(ctx);
                g_fsn_connT     = (int)zf_pop(ctx);
                g_fsn_fileT     = (int)zf_pop(ctx);
                g_fsn_dirT      = (int)zf_pop(ctx);
                g_fsn_root = g_fsn_start = ".";
                g_fsn_enterLatch = g_fsn_backLatch = false;
            } else if (custom == 9) {
                // fsn-build ( -- nodeCount )
                int n = fsn_build();
                fprintf(stderr, "FSN: built '%s' — %d actors (%d towers)\n",
                        g_fsn_root.c_str(), n, (int)g_fsn_towers.size());
                zf_push(ctx, (zf_cell)(float)n);
            } else if (custom == 10) {
                // fsn-navigate ( -- rebuild? ) — play-area bounds + proximity descend / ascend.
                zf_push(ctx, (zf_cell)(float)fsn_navigate());
            } else if (custom == 11) {
                // fsn-flydown ( t camIdx -- ) — ease the camshot high→play over the clock t.
                int camIdx = (int)zf_pop(ctx);
                float t    = (float)zf_pop(ctx);
                fsn_flydown(camIdx, t);
            } else if (custom == 12) {
                // fl-config ( maxDepth maxNodes playerIdx -- )
                g_fl_playerIdx = (int)zf_pop(ctx);
                g_fsn_maxNodes = (int)zf_pop(ctx);   // shared spawn budget (fsn_spawn/fsn_budget_left)
                g_fl_maxDepth  = (int)zf_pop(ctx);
                g_fl_root = g_fl_start = ".";
                g_fl_branchCount = 0;
                g_fl_pendingBuild = false;
                g_fl_enterLatch = g_fl_backLatch = false;
            } else if (custom == 13) {
                // fl-scan ( -- nSegments ) — rebuild the flat segment table for the root.
                int n = fl_scan();
                fprintf(stderr, "FL: scanned '%s' — %d segments\n", g_fl_root.c_str(), n);
                zf_push(ctx, (zf_cell)(float)n);
            } else if (custom == 14) {
                // seg-depth ( i -- d )
                int i = (int)zf_pop(ctx);
                zf_push(ctx, (zf_cell)(float)((i >= 0 && i < (int)g_fl_segments.size())
                                              ? g_fl_segments[i].depth : 0));
            } else if (custom == 15) {
                // seg-a0 ( i -- rev )
                int i = (int)zf_pop(ctx);
                zf_push(ctx, (zf_cell)((i >= 0 && i < (int)g_fl_segments.size())
                                       ? g_fl_segments[i].a0 : 0.0f));
            } else if (custom == 16) {
                // seg-a1 ( i -- rev )
                int i = (int)zf_pop(ctx);
                zf_push(ctx, (zf_cell)((i >= 0 && i < (int)g_fl_segments.size())
                                       ? g_fl_segments[i].a1 : 0.0f));
            } else if (custom == 17) {
                // seg-size ( i -- kb )
                int i = (int)zf_pop(ctx);
                zf_push(ctx, (zf_cell)(float)((i >= 0 && i < (int)g_fl_segments.size())
                                              ? g_fl_segments[i].sizeKB : 0));
            } else if (custom == 18) {
                // seg-branch ( i -- branchId )
                int i = (int)zf_pop(ctx);
                zf_push(ctx, (zf_cell)(float)((i >= 0 && i < (int)g_fl_segments.size())
                                              ? g_fl_segments[i].branchId : 0));
            } else if (custom == 19) {
                // set-rotation ( actor revs -- ) — Euler heading about Z (revolutions).
                float rev = (float)zf_pop(ctx);
                int   idx = (int)zf_pop(ctx);
                if (theLevel) {
                    Actor* a = theLevel->getActor(idx);
                    if (a) a->GetWritablePhysicalAttributes().SetRotation(
                        Euler(Angle::Revolution(Scalar::zero),
                              Angle::Revolution(Scalar::zero),
                              Angle::Revolution(Scalar::FromFloat(rev))));
                }
            } else if (custom == 20) {
                // fl-navigate ( -- rebuild? )
                zf_push(ctx, (zf_cell)(float)fl_navigate());
            } else if (custom == 21) {
                // fl-flydown ( t camIdx -- )
                int camIdx = (int)zf_pop(ctx);
                float t    = (float)zf_pop(ctx);
                fl_flydown(camIdx, t);
            } else if (custom == 22) {
                // hsv>rgb ( h s v -- 0xRRGGBB ) — math primitive (like isqrt); the
                // *which* hue/sat/val is the Director's colour policy. h,s,v ∈ [0,1].
                float v = (float)zf_pop(ctx);
                float s = (float)zf_pop(ctx);
                float h = (float)zf_pop(ctx);
                if (s < 0.0f) s = 0.0f; if (s > 1.0f) s = 1.0f;
                if (v < 0.0f) v = 0.0f; if (v > 1.0f) v = 1.0f;
                h -= std::floor(h); if (h < 0.0f) h += 1.0f;
                float hh = h * 6.0f;
                int   i  = (int)hh;
                float f  = hh - (float)i;
                float p  = v * (1.0f - s);
                float q  = v * (1.0f - s * f);
                float tt = v * (1.0f - s * (1.0f - f));
                float r, g, b;
                switch (i % 6) {
                    case 0:  r=v;  g=tt; b=p;  break;
                    case 1:  r=q;  g=v;  b=p;  break;
                    case 2:  r=p;  g=v;  b=tt; break;
                    case 3:  r=p;  g=q;  b=v;  break;
                    case 4:  r=tt; g=p;  b=v;  break;
                    default: r=v;  g=p;  b=q;  break;
                }
                int ri = (int)(r * 255.0f + 0.5f);
                int gi = (int)(g * 255.0f + 0.5f);
                int bi = (int)(b * 255.0f + 0.5f);
                int packed = ((ri & 0xFF) << 16) | ((gi & 0xFF) << 8) | (bi & 0xFF);
                zf_push(ctx, (zf_cell)(float)packed);
            } else if (custom == 23) {
                // fsn-scan ( -- nNodes ) — rebuild the FSN tree's flat render table.
                int n = fsn_emit_tree();
                fprintf(stderr, "FSN: emitted '%s' — %d nodes (%d towers)\n",
                        g_fsn_root.c_str(), n, (int)g_fsn_towers.size());
                zf_push(ctx, (zf_cell)(float)n);
            } else if (custom >= 24 && custom <= 29) {
                // node-kind/x/y/z/p1/p2 ( i -- v ) — index accessors into the table.
                int i = (int)zf_pop(ctx);
                float v = 0.0f;
                if (i >= 0 && i < (int)g_fsn_nodes.size()) {
                    const FsnNode& nd = g_fsn_nodes[i];
                    switch (custom) {
                        case 24: v = (float)nd.kind; break;
                        case 25: v = nd.x;  break;
                        case 26: v = nd.y;  break;
                        case 27: v = nd.z;  break;
                        case 28: v = nd.p1; break;
                        default: v = nd.p2; break;   // 29
                    }
                }
                zf_push(ctx, (zf_cell)v);
            } else if (custom == 30) {
                // node-count ( -- n )
                zf_push(ctx, (zf_cell)(float)(int)g_fsn_nodes.size());
            } else if (custom == 31) {
                // pack-rgb ( r g b -- 0xRRGGBB ) — floor+clamp 3 channels, pack. The
                // colour *ramp* (which r,g,b) is the Director's policy; this is the prim.
                int b = (int)zf_pop(ctx); if (b < 0) b = 0; if (b > 255) b = 255;
                int g = (int)zf_pop(ctx); if (g < 0) g = 0; if (g > 255) g = 255;
                int r = (int)zf_pop(ctx); if (r < 0) r = 0; if (r > 255) r = 255;
                zf_push(ctx, (zf_cell)(float)(((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)));
            } else if (custom == 72) {
                /* Neural-forth dispatch gate: syscall 200 = ZF_SYSCALL_USER + 72.
                 * Pops word-id from stack and routes to nf_dispatch().
                 * Syscalls 8-71 are reserved for future WF primitives. */
#ifdef WF_NEURAL_FORTH
                int word_id = (int)zf_pop(ctx);
                nf_dispatch(ctx, word_id);
#else
                fprintf(stderr, "zforth: neural-forth syscall (200) received but WF_NEURAL_FORTH not compiled in\n");
#endif
            } else {
                fprintf(stderr, "zforth: unknown sys id %d\n", (int)id);
            }
            break;
        }
    }
    return ZF_INPUT_INTERPRET;
}

// Trace callback — only called when ZF_ENABLE_TRACE=1, which we set to 0.
void zf_host_trace(zf_ctx* /*ctx*/, const char* fmt, va_list va)
{
    vfprintf(stderr, fmt, va);
}

// Number parser — called when an unknown word is encountered.
// Parses integers (decimal, hex with 0x prefix) and floats.
zf_cell zf_host_parse_num(zf_ctx* ctx, const char* buf)
{
    char* end = nullptr;

    // Try hex: 0x...
    if (buf[0] == '0' && (buf[1] == 'x' || buf[1] == 'X')) {
        long v = strtol(buf, &end, 16);
        if (end && *end == '\0') return (zf_cell)v;
    }

    // Try float (handles integer literals too)
    float v = strtof(buf, &end);
    if (end && *end == '\0') return (zf_cell)v;

    // Not a number — abort
    zf_abort(ctx, ZF_ABORT_NOT_A_WORD);
    return (zf_cell)0;
}

// ---------------------------------------------------------------------------
// forth_engine namespace — public plug interface

namespace forth_engine {

// Subset of zForth's core.zf needed to make `constant` work.
// zForth's bootstrap provides only primitive opcodes (>r, r>, :, ;, ,,, !!,
// _literal→literal, etc.) but not the higher-level words `!`, `@`,
// `postpone`, or `constant`. We eval just the minimum needed.
//
// Note: `constant` in zForth core.zf is defined as:
//   : constant >r : r> postpone literal postpone ; ;
// which requires `!` (for `postpone`'s body) and `postpone` itself.
// We also load `@` and `,` since scripts may use them.
static const char* kCoreBootstrap =
    // Dictionary shortcuts (default cell-width wrappers around sized ops)
    ": !    0 !! ; "
    ": @    0 @@ ; "
    ": ,    0 ,, ; "
    // Max-width cell stores for jump targets — must be fixed-width so the
    // compiler can back-patch branch addresses after emitting a placeholder.
    // 64 is ZF_MEM_SIZE_VAR_MAX; see zforth.c.
    ": !j  64 !! ; "
    ": ,j  64 ,, ; "
    // `here` — fetch current HERE (compilation pointer) value.
    // `h` alone is a uservar word that pushes its address (0); control-flow
    // words need the stored VALUE, so they use `here` (= `h @`). Matches the
    // vendor core.zf convention (see engine/vendor/zforth-41db72d1/forth/core.zf).
    ": here h @ ; "
    // Interpreter state control
    ": [ 0 compiling ! ; immediate "
    ": ] 1 compiling ! ; "
    // postpone: sets _postpone flag so next word is compiled not executed
    ": postpone 1 _postpone ! ; immediate "
    // constant: canonical zForth definition — stores literal in new word
    ": constant >r : r> postpone literal postpone ; ; "
    // Derived operators useful in game scripts
    ": 1+ 1 + ; "
    ": 1- 1 - ; "
    ": over 1 pick ; "
    ": not 0 = ; "
    ": <  - <0 ; "
    ": >  swap < ; "
    ": <= over over >r >r < r> r> = + ; "
    ": >= swap <= ; "
    ": <> = not ; "
    ": 0<> 0 <> ; "
    // Control flow — if/else/fi/then, begin/until/again
    // `if` emits a jmp0 with a placeholder target at HERE; `fi`/`then` back-
    // patch it with the value of HERE at their point. `else` emits an
    // unconditional jmp past the else-body, back-patches the if's jmp0 to
    // current HERE, then leaves the else's jmp placeholder for `fi`/`then`
    // to patch. All use `here` (the VALUE) not `h` (the uservar ID).
    ": if     ' jmp0 , here 0 ,j ; immediate "
    ": else   ' jmp  , here 0 ,j swap here swap !j ; immediate "
    ": fi     here swap !j ; immediate "
    ": then   here swap !j ; immediate "   // standard Forth alias for fi
    ": begin  here ; immediate "
    ": again  ' jmp  , , ; immediate "
    ": until  ' jmp0 , , ; immediate "
    // Counted loop: `limit start do ... loop`
    // `i` pushes the current loop index (TOR[0]); `j` the outer index (TOR[2]).
    // loop+ increments by n; loop by 1.  All immediate — compiled, not eval'd.
    ": i     ' lit , 0 , ' pickr , ; immediate "
    ": j     ' lit , 2 , ' pickr , ; immediate "
    ": do    ' swap , ' >r , ' >r , here ; immediate "
    ": loop+ ' r> , ' + , ' dup , ' >r , ' lit , 1 , ' pickr , ' >= , "
             "' jmp0 , , ' r> , ' drop , ' r> , ' drop , ; immediate "
    ": loop  ' lit , 1 , postpone loop+ ; immediate "
    // --- Standard ANS CORE words (tiers 1+2 + mod) — see
    // docs/plans/2026-05-17-add-tier-1-2-standard-forth-words-to-the-wf-zforth.md.
    // Order matters: later defs reuse earlier ones and the control-flow / stack
    // primitives defined above (over, <, >, if, then, =, <0, @, !, rot, >r, r>).
    ": 0=     0 = ; "
    ": 0<     <0 ; "                       // <0 is the zForth primitive; 0< is the ANS name
    ": 0>     0 > ; "
    ": negate 0 swap - ; "
    ": abs    dup 0< if negate then ; "
    ": min    over over > if swap then drop ; "
    ": max    over over < if swap then drop ; "
    ": ?dup   dup if dup then ; "
    ": nip    swap drop ; "
    ": tuck   swap over ; "
    ": -rot   rot rot ; "
    ": 2dup   over over ; "
    ": 2drop  drop drop ; "
    ": 2swap  >r -rot r> -rot ; "          // a b c d -> c d a b
    ": +!     dup @ rot + swap ! ; "
    // `mod` is the ANS name for zForth's native `%` primitive — integer remainder
    // (int)a%(int)b with a divide-by-zero abort (zforth.c PRIM_MOD). Same family as
    // & = and, | = or, <0 = 0<. NOT `over over / * -` — `/` is float division here.
    ": mod    % ; "
    ;

void Init(MailboxesManager& mgr)
{
    g_mgr    = &mgr;
    g_curObj = 0;

    zf_init(&g_ctx, 0 /* no trace */);
    zf_bootstrap(&g_ctx);

    // Load the core bootstrap words (constant, !, @, etc.).
    zf_result r = zf_eval(&g_ctx, kCoreBootstrap);
    if (r != ZF_OK)
        fprintf(stderr, "zforth: core bootstrap failed: %d\n", r);

    // Define the WF mailbox bridge words.
    // ZF_SYSCALL_USER = 128; sys pops its argument directly as syscall id.
    r = zf_eval(&g_ctx, ": read-mailbox  128 sys ;");
    if (r != ZF_OK)
        fprintf(stderr, "zforth: init failed (read-mailbox): %d\n", r);
    r = zf_eval(&g_ctx, ": write-mailbox 129 sys ;");
    if (r != ZF_OK)
        fprintf(stderr, "zforth: init failed (write-mailbox): %d\n", r);
    r = zf_eval(&g_ctx, ": write-actor-mailbox 130 sys ;");
    if (r != ZF_OK)
        fprintf(stderr, "zforth: init failed (write-actor-mailbox): %d\n", r);

    // FSN filesystem bridge words (custom 3-7 / sys 131-135)
    r = zf_eval(&g_ctx, ": cwd-scan      131 sys ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (cwd-scan): %d\n", r);
    r = zf_eval(&g_ctx, ": cwd-is-dir    132 sys ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (cwd-is-dir): %d\n", r);
    r = zf_eval(&g_ctx, ": cwd-file-size 133 sys ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (cwd-file-size): %d\n", r);
    r = zf_eval(&g_ctx, ": cwd-dir-count 134 sys ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (cwd-dir-count): %d\n", r);
    r = zf_eval(&g_ctx, ": spawn-template 135 sys ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (spawn-template): %d\n", r);

    // FSN Phase 2 — recursive tree builder (C++ does scan/layout/spawn).
    r = zf_eval(&g_ctx, ": fsn-config 136 sys ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (fsn-config): %d\n", r);
    r = zf_eval(&g_ctx, ": fsn-build 137 sys ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (fsn-build): %d\n", r);
    r = zf_eval(&g_ctx, ": fsn-navigate 138 sys ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (fsn-navigate): %d\n", r);
    r = zf_eval(&g_ctx, ": fsn-flydown 139 sys ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (fsn-flydown): %d\n", r);

    // Uniform scale helper — sets qbert scale mailboxes 3040-3042 on an actor.
    // Stack: ( actor scale -- )
    // write-actor-mailbox signature: ( val idx actorIdx -- )
    // 2dup swap 3040 swap builds ( actor scale scale 3040 actor ) then pops val=scale, idx=3040, actorIdx=actor.
    r = zf_eval(&g_ctx,
        ": set-scale "
        "  2dup swap 3040 swap write-actor-mailbox "
        "  2dup swap 3041 swap write-actor-mailbox "
        "  2dup swap 3042 swap write-actor-mailbox "
        "  2drop ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (set-scale): %d\n", r);

    // Z-only scale helper — sets X/Y=1.0 and Z=scale. Stack: ( actor scale -- )
    // Used for towers/boxes that should stay unit-width but vary in height.
    // 3 pick from ( actor scale 1.0 3040 ) reaches actor at depth 3.
    r = zf_eval(&g_ctx,
        ": set-z-scale "
        "  1.0 3040 3 pick write-actor-mailbox "
        "  1.0 3041 3 pick write-actor-mailbox "
        "  2dup swap 3042 swap write-actor-mailbox "
        "  2drop ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (set-z-scale): %d\n", r);

    // Integer square root (iterative). Stack: ( n -- s )
    // begin..until: increment s first, exit when s*s > n, return s-1.
    r = zf_eval(&g_ctx,
        ": isqrt "
        "  dup 0 = if else "
        "    1 swap "
        "    begin swap 1+ swap over dup * over > until "
        "    swap drop 1- "
        "  fi ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (isqrt): %d\n", r);

    // ---------------------------------------------------------------------
    // Filelight bridge words (custom 12-21 / sys 140-149) + shared render
    // primitives. The render *policy* (tile-seg, place-wedge, hue, height
    // curve) lives in the level's Director .fth for hot-reload — only the
    // primitives below live in the engine.
    static const struct { const char* name; const char* body; } kFlWords[] = {
        { "fl-config",    "140 sys" },
        { "fl-scan",      "141 sys" },
        { "seg-depth",    "142 sys" },
        { "seg-a0",       "143 sys" },
        { "seg-a1",       "144 sys" },
        { "seg-size",     "145 sys" },
        { "seg-branch",   "146 sys" },
        { "set-rotation", "147 sys" },
        { "fl-navigate",  "148 sys" },
        { "fl-flydown",   "149 sys" },
        { "hsv>rgb",      "150 sys" },
    };
    for (const auto& w : kFlWords) {
        char buf[64];
        snprintf(buf, sizeof(buf), ": %s %s ;", w.name, w.body);
        if (zf_eval(&g_ctx, buf) != ZF_OK)
            fprintf(stderr, "zforth: init failed (%s)\n", w.name);
    }

    // r@ — peek the return-stack top without popping (immediate: compiles `0 pickr`).
    // Render words stash a spawned actor on the rstack while configuring it.
    // (zForth ships `i`/`j` but no `r@`.)
    r = zf_eval(&g_ctx, ": r@ ' lit , 0 , ' pickr , ; immediate");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (r@): %d\n", r);

    // spawn0 ( tmpl -- actor ) — spawn a template at the world origin (0,0,0).
    r = zf_eval(&g_ctx, ": spawn0 >r 0 0 0 r> spawn-template ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (spawn0): %d\n", r);

    // set-color ( actor 0xRRGGBB -- ) — write the packed colour to all three face
    // colour mailboxes (3037/3038/3039). Mirrors set-scale's stack shuffle.
    r = zf_eval(&g_ctx,
        ": set-color "
        "  2dup swap 3037 swap write-actor-mailbox "
        "  2dup swap 3038 swap write-actor-mailbox "
        "  2dup swap 3039 swap write-actor-mailbox "
        "  2drop ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (set-color): %d\n", r);

    // set-x-scale ( actor scale -- ) — X=scale, Y=Z=1 (the FSN connector stretch).
    r = zf_eval(&g_ctx,
        ": set-x-scale "
        "  2dup swap 3040 swap write-actor-mailbox "
        "  1.0 3041 3 pick write-actor-mailbox "
        "  1.0 3042 3 pick write-actor-mailbox "
        "  2drop ;");
    if (r != ZF_OK) fprintf(stderr, "zforth: init failed (set-x-scale): %d\n", r);

    // FSN Phase 3 flat-table bridge words (custom 23-31 / sys 151-159).
    static const struct { const char* name; const char* body; } kFsnWords[] = {
        { "fsn-scan",   "151 sys" },
        { "node-kind",  "152 sys" },
        { "node-x",     "153 sys" },
        { "node-y",     "154 sys" },
        { "node-z",     "155 sys" },
        { "node-p1",    "156 sys" },
        { "node-p2",    "157 sys" },
        { "node-count", "158 sys" },
        { "pack-rgb",   "159 sys" },
    };
    for (const auto& w : kFsnWords) {
        char buf[64];
        snprintf(buf, sizeof(buf), ": %s %s ;", w.name, w.body);
        if (zf_eval(&g_ctx, buf) != ZF_OK)
            fprintf(stderr, "zforth: init failed (%s)\n", w.name);
    }

#ifdef WF_NEURAL_FORTH
    nf_init(&g_ctx);
#endif
}

void Shutdown()
{
    // zForth state is a plain struct — no heap to free.
    g_mgr    = nullptr;
    g_curObj = 0;
    g_scriptCache.clear();
    g_actorOverride.clear();
    g_reloadCounter = 0;
}

void AddConstantArray(IntArrayEntry* entryList)
{
    // Define each constant as `: NAME VALUE ;` — the integer literal is
    // embedded inline at compile time so at runtime NAME just pushes VALUE.
    // `constant` (r> + postpone literal) is compile-time-only and broken
    // at runtime in zForth's embedding model.
    char buf[128];
    for (IntArrayEntry* p = entryList; p->name; p++) {
        snprintf(buf, sizeof(buf), ": %s %d ;", p->name, p->value);
        zf_result r = zf_eval(&g_ctx, buf);
        if (r != ZF_OK)
            fprintf(stderr, "zforth: failed to define constant %s: %d\n", p->name, r);
    }
    // Spot-check: verify INDEXOF_CAMSHOT loaded correctly.
    if (zf_eval(&g_ctx, "INDEXOF_CAMSHOT") == ZF_OK) {
        zf_cell v = zf_pop(&g_ctx);
        fprintf(stderr, "zforth: INDEXOF_CAMSHOT = %d (expect 1921)\n", (int)v);
    }
}

void DeleteConstantArray(IntArrayEntry* /*entryList*/)
{
    // zForth dictionaries are append-only — constants cannot be removed.
    // This is a no-op; constants persist for the lifetime of the engine.
}

float RunScript(const char* src, int objectIndex)
{
    if (!src || !*src) return 0.0f;

    g_curObj = objectIndex;

    // Debug-bridge override: if a hot-reloaded script is registered for this
    // actor, dispatch to it instead of the OAD-baked source. The override
    // word was compiled by ReloadActorScript and lives in the global dict.
    auto ov = g_actorOverride.find(objectIndex);
    if (ov != g_actorOverride.end()) {
        zf_result r = zf_eval(&g_ctx, ov->second.c_str());
        if (r != ZF_OK) {
            fprintf(stderr, "zforth error %d calling override %s\n",
                    r, ov->second.c_str());
            return 0.0f;
        }
        zf_cell dsp = 0;
        zf_uservar_get(&g_ctx, ZF_USERVAR_DSP, &dsp);
        if ((int)dsp > 0) return (float)zf_pop(&g_ctx);
        return 0.0f;
    }

    // Skip leading whitespace, then the `\ wf` sigil line.
    while (*src == ' ' || *src == '\t' || *src == '\r' || *src == '\n') ++src;
    while (*src && *src != '\n') ++src;
    if (*src == '\n') ++src;
    if (!*src) return 0.0f;

    // Flush any suspended \ (line-comment) loop left by a prior partial eval.
    // shell.aib's defs string ends at a ; inside a \ comment with no trailing \n,
    // leaving the \ loop in ZF_INPUT_PASS_CHAR. Feeding \n here lets it exit
    // cleanly before this script's compilation begins.
    zf_eval(&g_ctx, "\n");

    // Compile each unique script once (keyed by src pointer) into a named word
    // so if/else/then work correctly (they require compile mode) and the
    // dictionary doesn't grow every frame.
    //
    // Scripts may contain `: word ... ;` definitions followed by a call body.
    // We can't nest `:` definitions inside the wrapper word, so we split:
    //   1. Eval the definitions part (everything up to and including the last `;`)
    //      directly — compiled once, never re-eval'd.
    //   2. Wrap only the call body (everything after the last `;`) in `_wfsN`.
    auto it = g_scriptCache.find(src);
    if (it == g_scriptCache.end()) {
        const char* callBody = src;

        // Find last `;` to locate the boundary between definitions and call body.
        const char* lastSemi = nullptr;
        for (const char* p = src; *p; ++p)
            if (*p == ';') lastSemi = p;

        if (lastSemi) {
            std::string defs(src, static_cast<size_t>(lastSemi + 1 - src));
            zf_result rc = zf_eval(&g_ctx, defs.c_str());
            if (rc != ZF_OK) {
                fprintf(stderr, "zforth compile error %d (defs): %.120s\n", rc, src);
                return 0.0f;
            }
            callBody = lastSemi + 1;
            while (*callBody == ' ' || *callBody == '\t' || *callBody == '\r' || *callBody == '\n')
                ++callBody;
        }

        char wordName[32];
        snprintf(wordName, sizeof(wordName), "_wfs%zu", g_scriptCache.size());
        if (*callBody) {
            std::string def = ": ";
            def += wordName;
            def += " ";
            def += callBody;
            def += " ;";
            zf_result rc = zf_eval(&g_ctx, def.c_str());
            if (rc != ZF_OK) {
                fprintf(stderr, "zforth compile error %d (call): %.120s\n", rc, callBody);
                return 0.0f;
            }
        } else {
            // No call body — define an empty word so cache is populated.
            std::string def = ": "; def += wordName; def += " ;";
            zf_eval(&g_ctx, def.c_str());
        }
        g_scriptCache[src] = wordName;
        it = g_scriptCache.find(src);
    }

    zf_result r = zf_eval(&g_ctx, it->second.c_str());
    if (r != ZF_OK) {
        fprintf(stderr, "zforth error %d calling %s\n", r, it->second.c_str());
        return 0.0f;
    }

    // Return TOS as float if stack is non-empty; 0 otherwise.
    // Use zf_uservar_get to check DSP without risking underrun.
    zf_cell dsp = 0;
    zf_uservar_get(&g_ctx, ZF_USERVAR_DSP, &dsp);
    if ((int)dsp > 0) {
        return (float)zf_pop(&g_ctx);
    }
    return 0.0f;
}

// ---------------------------------------------------------------------------
// Debug-bridge hot reload (B2)

bool ReloadActorScript(int actor_idx, const char* source, std::string& log_out)
{
    if (!source || !*source) {
        log_out = "empty source";
        return false;
    }

    // Skip leading whitespace + optional `\ wf` sigil line (same as RunScript).
    const char* src = source;
    while (*src == ' ' || *src == '\t' || *src == '\r' || *src == '\n') ++src;
    if (src[0] == '\\') {
        while (*src && *src != '\n') ++src;
        if (*src == '\n') ++src;
    }

    // Split definitions (everything up to last `;`) from the call body.
    const char* lastSemi = nullptr;
    for (const char* p = src; *p; ++p)
        if (*p == ';') lastSemi = p;

    const char* callBody = src;
    if (lastSemi) {
        std::string defs(src, static_cast<size_t>(lastSemi + 1 - src));
        zf_result rc = zf_eval(&g_ctx, defs.c_str());
        if (rc != ZF_OK) {
            log_out = std::string("defs: ") + zf_result_str(rc);
            return false;
        }
        callBody = lastSemi + 1;
        while (*callBody == ' ' || *callBody == '\t' || *callBody == '\r' || *callBody == '\n')
            ++callBody;
    }

    char wordName[40];
    snprintf(wordName, sizeof(wordName), "_wfsRld%d", g_reloadCounter++);
    std::string def = ": ";
    def += wordName;
    def += " ";
    def += (*callBody) ? callBody : "";
    def += " ;";
    zf_result rc = zf_eval(&g_ctx, def.c_str());
    if (rc != ZF_OK) {
        log_out = std::string("call: ") + zf_result_str(rc);
        return false;
    }

    g_actorOverride[actor_idx] = wordName;
    return true;
}

void ClearActorScriptOverrides()
{
    g_actorOverride.clear();
    // Note: orphaned _wfsRld* definitions remain in the dict (append-only).
}

void ClearActorScriptOverride(int actor_idx)
{
    g_actorOverride.erase(actor_idx);
}

} // namespace forth_engine

#endif // WF_FORTH_ENGINE_ZFORTH
