// level_script_vm: run every actor script of an exported level the way the engine does.
//
// One shared zForth context (engine/stubs/scripting_zforth.cc), the engine's
// definitions-then-body split (engine/stubs/forth_source.hp), one `_wfsN` word per
// script, scripts run once per frame in actor-index order. Mailboxes are mocked:
// LOCAL_SYSTEM (3000..3047) belongs to the running actor, everything else is the
// level's. HARDWARE_JOYSTICK1 / _RAW / _RAW_JUSTPRESSED (1908..1910) carry the
// stick bits of the current `step`. The game-over hold of game.cc (mb 591, armed
// to 180 on a rising edge of mb 420, decremented every frame) is emulated so a
// script's restart guard sees what it sees on a device. A script that aborts is
// counted and the frame goes on, as RunScript does.
//
//   level_script_vm PRELUDE.fth SCRIPTS.txt < commands
//
// PRELUDE.fth: core bootstrap + bridge words + INDEXOF constants (built by the test).
// SCRIPTS.txt: records "<actor index>\n<byte count>\n<script bytes>\n".
// Commands (one per line):
//   step N BITS     run N frames with the stick held at BITS
//   set MB VALUE    write a level mailbox
//   get MB...       print "G v1 v2 ..." for level mailboxes
//   errors          print "E total" and one "E actor count first-error" per script that aborted
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include <sstream>
#include <iostream>
#include <fstream>
extern "C" {
#include "zforth.h"
}
#include "forth_source.hp"

static zf_ctx ctx;
static std::map<int, float> level;
static std::map<int, std::map<int, float>> local;
static int current = 0;

static bool isLocal(int mb) { return mb >= 3000 && mb < 3048; }
static float rd(int actor, int mb) { return isLocal(mb) ? local[actor][mb] : level[mb]; }
static void wr(int actor, int mb, float v) { if (isLocal(mb)) local[actor][mb] = v; else level[mb] = v; }

extern "C" zf_input_state zf_host_sys(zf_ctx* c, zf_syscall_id id, const char*)
{
    int custom = (int)id - (int)ZF_SYSCALL_USER;
    switch (custom) {
        case 0: { int mb = (int)zf_pop(c); zf_push(c, rd(current, mb)); break; }                       // read-mailbox
        case 1: { int mb = (int)zf_pop(c); float v = zf_pop(c); wr(current, mb, v); break; }           // write-mailbox
        case 2: { int a = (int)zf_pop(c); int mb = (int)zf_pop(c); float v = zf_pop(c); wr(a, mb, v); break; } // write-actor-mailbox
        case 24: { int a = (int)zf_pop(c); int mb = (int)zf_pop(c); zf_push(c, rd(a, mb)); break; }    // read-actor-mailbox
        default:
            if (id == ZF_SYSCALL_EMIT || id == ZF_SYSCALL_PRINT) { zf_pop(c); break; }
            std::fprintf(stderr, "unexpected syscall %d\n", (int)id);
            std::exit(3);
    }
    return ZF_INPUT_INTERPRET;
}
extern "C" void zf_host_trace(zf_ctx*, const char*, va_list) {}
extern "C" zf_cell zf_host_parse_num(zf_ctx* c, const char* buf)   // same rules as the engine
{
    char* end = nullptr;
    if (buf[0] == '0' && (buf[1] == 'x' || buf[1] == 'X')) {
        long v = std::strtol(buf, &end, 16);
        if (end && *end == '\0') return (zf_cell)v;
    }
    float v = std::strtof(buf, &end);
    if (end && *end == '\0') return (zf_cell)v;
    std::fprintf(stderr, "unknown token: %s\n", buf);
    zf_abort(c, ZF_ABORT_NOT_A_WORD);
    return 0;
}

static std::string slurp(const char* path)
{
    std::ifstream f(path, std::ios::binary);
    if (!f) { std::fprintf(stderr, "cannot read %s\n", path); std::exit(2); }
    std::stringstream s; s << f.rdbuf(); return s.str();
}

struct Script { int actor; std::string word; int errors = 0; int firstError = 0; };

// RunScript pops the script's return value (one cell) when the stack is non-empty;
// an abort has already reset the stack (zf_eval sets DSP to 0).
static void popReturnValue()
{
    zf_cell dsp = 0;
    zf_uservar_get(&ctx, ZF_USERVAR_DSP, &dsp);
    if ((int)dsp > 0) zf_pop(&ctx);
}

int main(int argc, char** argv)
{
    if (argc != 3) { std::fprintf(stderr, "usage: level_script_vm PRELUDE.fth SCRIPTS.txt\n"); return 2; }
    zf_init(&ctx, 0);
    zf_bootstrap(&ctx);
    const std::string prelude = slurp(argv[1]);
    if (zf_eval(&ctx, prelude.c_str()) != ZF_OK) { std::fprintf(stderr, "prelude failed\n"); return 2; }

    std::vector<Script> scripts;
    const std::string all = slurp(argv[2]);
    size_t pos = 0;
    while (pos < all.size()) {
        size_t nl = all.find('\n', pos); if (nl == std::string::npos) break;
        const int actor = std::atoi(all.substr(pos, nl - pos).c_str());
        size_t nl2 = all.find('\n', nl + 1);
        const size_t n = std::strtoul(all.substr(nl + 1, nl2 - nl - 1).c_str(), nullptr, 10);
        const std::string src = all.substr(nl2 + 1, n);
        pos = nl2 + 1 + n + 1;
        const auto parts = forth_source::Split(src.c_str());
        if (!parts.definitions.empty() && zf_eval(&ctx, parts.definitions.c_str()) != ZF_OK) {
            std::fprintf(stderr, "compile error (defs) actor %d\n", actor); return 4;
        }
        Script s; s.actor = actor; s.word = "_wfs" + std::to_string(scripts.size());
        const std::string def = forth_source::Wrap(s.word, parts.body);
        if (zf_eval(&ctx, def.c_str()) != ZF_OK) { std::fprintf(stderr, "compile error (call) actor %d\n", actor); return 4; }
        scripts.push_back(s);
    }

    int prevBits = 0, prevGameOver = 0;
    std::string line;
    while (std::getline(std::cin, line)) {
        std::istringstream in(line);
        std::string cmd; in >> cmd;
        if (cmd == "step") {
            int frames = 0, bits = 0; in >> frames >> bits;
            for (int f = 0; f < frames; ++f) {
                level[1908] = (float)bits; level[1909] = (float)bits;
                level[1910] = (float)(bits & ~prevBits); prevBits = bits;
                for (auto& s : scripts) {
                    current = s.actor;
                    const zf_result r = zf_eval(&ctx, s.word.c_str());
                    if (r != ZF_OK) { if (!s.errors) s.firstError = (int)r; ++s.errors; }
                    popReturnValue();
                }
                // game.cc: GO_HOLD_TIMER decrements each frame and is armed on the game-over edge.
                if (level[591] > 0) level[591] = level[591] - 1;
                const int gameOver = (int)level[420];
                if (gameOver && !prevGameOver) level[591] = 180;
                prevGameOver = gameOver;
            }
        } else if (cmd == "set") {
            int mb; float v; in >> mb >> v; level[mb] = v;
        } else if (cmd == "get") {
            std::printf("G");
            int mb; while (in >> mb) std::printf(" %.9g", (double)level[mb]);
            std::printf("\n");
        } else if (cmd == "errors") {
            int total = 0; for (auto& s : scripts) total += s.errors;
            std::printf("E %d\n", total);
            for (auto& s : scripts) if (s.errors) std::printf("E %d %d %d\n", s.actor, s.errors, s.firstError);
        }
        std::fflush(stdout);
    }
    return 0;
}
