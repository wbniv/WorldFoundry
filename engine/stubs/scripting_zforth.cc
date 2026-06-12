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
#include <dirent.h>
#include <sys/stat.h>
#include <cmath>      // atan2/cos/sin/sqrt for the FSN connector orientation

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

static const float FSN_PI = 3.14159265358979f;

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
        if (file) fsn_set_scale(file, 1.0f, 1.0f, (float)fh);
        fi++;
    }
}

// A queued tree node: render its tower when dequeued, wire it to its parent.
struct FsnJob { std::string path; float x, y, px, py; int depth; };

// Despawn the current view and rebuild from g_fsn_root, BREADTH-FIRST. Returns
// the spawned count. The ROOT (CWD) gets NO tower — the player stands there; its
// files ring the standpoint and its child dirs fan across the +Y half-field in
// front of the player (camera looks from -Y). BFS spreads the node budget across
// breadth before depth, so siblings all appear instead of one subtree clumping.
static int fsn_build() {
    if (theLevel) {
        for (int idx : g_fsn_spawned) {
            BaseObject* o = theLevel->GetObject(idx);
            if (o) theLevel->SetPendingRemove(o);
        }
    }
    g_fsn_spawned.clear();
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
        int fh = fsn_isqrt((int)(e.size / 1000)); if (fh < 1) fh = 1; if (fh > 4) fh = 4;
        int file = fsn_spawn(g_fsn_fileT, fx, fy, 0.0f);
        if (file) fsn_set_scale(file, 1.0f, 1.0f, (float)fh);
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
                // fsn-navigate ( -- ) — proximity descend / back ascend. M3 fills this in.
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
