// level_script_compile: compile every actor script of many levels the way the engine does.
//
// For each level: a fresh zForth context with the engine's dictionary (PRELUDE.fth, built by
// tests/check_level_scripts.py from engine/stubs/scripting_zforth.cc Init(), the math word table
// and the mailbox/joystick constants), then every script in actor order through the engine's
// own opener strip and definitions/body split (engine/stubs/forth_source.hp), compiled into a
// `_wfsN` word exactly as forth_engine::RunScript does. Nothing is run: a word that does not
// exist aborts at compile time, which is the failure this catches. A script whose first line is
// `R:pilot` goes to the PILOT engine (ScriptRouter's content sniff) and is skipped here.
//
//   level_script_compile [--legacy-opener] PRELUDE.fth SCRIPTS.txt
//
// SCRIPTS.txt records: "L <level>\n" starts a level; "<actor>\n<byte count>\n<bytes>\n" is a script.
// Output, one line each: "FAIL <level> <actor> <defs|call> <first unknown token or zf_result>",
// then "LEVEL <level> <scripts> <compiled> <pilot> <failed>".
// --legacy-opener drops the first non-blank line unconditionally, as RunScript did before
// 00978ee7d (2026-09-25); it exists to show what that commit changed.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
extern "C" {
#include "zforth.h"
}
#include "forth_source.hp"

static zf_ctx ctx;
static std::string g_unknown;   // first token the number parser rejected in the current compile

extern "C" zf_input_state zf_host_sys(zf_ctx* c, zf_syscall_id id, const char*)
{
    // Compile-only: no script body runs. The prelude's definitions only compile `sys` calls.
    if (id == ZF_SYSCALL_EMIT || id == ZF_SYSCALL_PRINT) { zf_pop(c); return ZF_INPUT_INTERPRET; }
    std::fprintf(stderr, "unexpected syscall %d at compile time\n", (int)id);
    std::exit(3);
}
extern "C" void zf_host_trace(zf_ctx*, const char*, va_list) {}
extern "C" zf_cell zf_host_parse_num(zf_ctx* c, const char* buf)   // engine rules (scripting_zforth.cc)
{
    char* end = nullptr;
    if (buf[0] == '0' && (buf[1] == 'x' || buf[1] == 'X')) {
        long v = std::strtol(buf, &end, 16);
        if (end && *end == '\0') return (zf_cell)v;
    }
    float v = std::strtof(buf, &end);
    if (end && *end == '\0') return (zf_cell)v;
    if (g_unknown.empty()) g_unknown = buf;
    zf_abort(c, ZF_ABORT_NOT_A_WORD);
    return 0;
}

static std::string slurp(const char* path)
{
    std::ifstream f(path, std::ios::binary);
    if (!f) { std::fprintf(stderr, "cannot read %s\n", path); std::exit(2); }
    std::stringstream s; s << f.rdbuf(); return s.str();
}

static bool looksLikePilot(const char* p)   // scripting_pilot.cc LooksLikePilot
{
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') ++p;
    return std::strncmp(p, "R:pilot", 7) == 0;
}

static const char* legacyOpener(const char* src)   // RunScript before 00978ee7d
{
    while (*src == ' ' || *src == '\t' || *src == '\r' || *src == '\n') ++src;
    while (*src && *src != '\n') ++src;
    if (*src == '\n') ++src;
    return src;
}

struct Level { std::string name; int scripts = 0, compiled = 0, pilot = 0, failed = 0; };

static void finish(const Level& l)
{
    if (!l.name.empty())
        std::printf("LEVEL %s %d %d %d %d\n", l.name.c_str(), l.scripts, l.compiled, l.pilot, l.failed);
}

static void reset(const std::string& prelude)
{
    zf_init(&ctx, 0);
    zf_bootstrap(&ctx);
    g_unknown.clear();
    if (zf_eval(&ctx, prelude.c_str()) != ZF_OK) {
        std::fprintf(stderr, "prelude failed (unknown token: %s)\n", g_unknown.c_str());
        std::exit(2);
    }
}

int main(int argc, char** argv)
{
    bool legacy = false;
    int a = 1;
    if (argc > 1 && std::strcmp(argv[1], "--legacy-opener") == 0) { legacy = true; ++a; }
    if (argc - a != 2) { std::fprintf(stderr, "usage: level_script_compile [--legacy-opener] PRELUDE.fth SCRIPTS.txt\n"); return 2; }
    const std::string prelude = slurp(argv[a]);
    const std::string all = slurp(argv[a + 1]);

    Level level;
    int word = 0;
    size_t pos = 0;
    while (pos < all.size()) {
        size_t nl = all.find('\n', pos);
        if (nl == std::string::npos) break;
        const std::string head = all.substr(pos, nl - pos);
        if (head.rfind("L ", 0) == 0) {
            finish(level);
            level = Level();
            level.name = head.substr(2);
            reset(prelude);
            word = 0;
            pos = nl + 1;
            continue;
        }
        const int actor = std::atoi(head.c_str());
        size_t nl2 = all.find('\n', nl + 1);
        const size_t n = std::strtoul(all.substr(nl + 1, nl2 - nl - 1).c_str(), nullptr, 10);
        const std::string text = all.substr(nl2 + 1, n);
        pos = nl2 + 1 + n + 1;
        if (text.empty()) continue;                       // RunScript: empty source is a no-op
        ++level.scripts;
        if (looksLikePilot(text.c_str())) { ++level.pilot; continue; }

        const char* src = legacy ? legacyOpener(text.c_str()) : text.c_str();
        const auto parts = forth_source::Split(src);
        const char* stage = "defs";
        zf_result rc = ZF_OK;
        g_unknown.clear();
        if (!parts.definitions.empty()) rc = zf_eval(&ctx, parts.definitions.c_str());
        if (rc == ZF_OK) {
            stage = "call";
            const std::string name = "_wfs" + std::to_string(word++);
            rc = zf_eval(&ctx, forth_source::Wrap(name, parts.body).c_str());
        }
        if (rc == ZF_OK) { ++level.compiled; continue; }
        ++level.failed;
        std::string why = g_unknown.empty() ? ("zf_result " + std::to_string((int)rc)) : g_unknown;
        for (char& ch : why) if (ch == '\n' || ch == '\r') ch = ' ';
        std::printf("FAIL %s %d %s %s\n", level.name.c_str(), actor, stage, why.c_str());
    }
    finish(level);
    return 0;
}
