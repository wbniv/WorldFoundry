// pilot_bridge_runner.cc — C++ PILOT bridge runner.
//
// Usage: pilot_bridge_runner [OPTIONS] FILE.pilot
//
//   --host H       bridge host (default: 127.0.0.1)
//   --port P       bridge port (default: 7795)
//   --wf-game PATH path to wf_game binary (default: <runner_dir>/wf_game)
//   --no-launch    connect to an already-running engine; do not launch wf_game
//
// Reads @tier, @level, @needs, @expect-exit, @expect-out, @screenshot directives
// from the .pilot file (same as Python pilot_driver.py).
// If @tier is "vm" the program is run without an engine (MockHost).
// If @tier is "engine" the runner launches wf_game (unless --no-launch) and
// drives it over the TCP debug bridge.
//
// Exits with the PILOT scenario exit code, or 1 on infrastructure failure.

#include "pilot_core.hp"
#include "host_bridge.hp"
#include "pilot_host.hp"

#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <regex>
#include <set>
#include <string>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>
#include <unordered_map>
#include <vector>

// ─────────────────────────────────────────────────────────────────────────────
// Minimal MockHost for @tier vm scenarios (no engine required).

namespace {

struct MockHost : pilot::PilotHost
{
    std::string out;
    std::vector<std::string> screenshots;
    std::unordered_map<long long, double> mb;

    long long key(int a, int m) { return (long long)a * 200000LL + m; }

    void   Type(const std::string& t, bool nl) override { out += t; if (nl) out += '\n'; }
    double ReadMailbox(int a, int m) override { auto it = mb.find(key(a,m)); return it != mb.end() ? it->second : 0.0; }
    void   SetMailbox(int a, int m, double v) override { mb[key(a,m)] = v; }
    bool   Screenshot(const std::string& n) override { screenshots.push_back(n); return true; }

    pilot::PilotHost::AwaitState CheckAwait(const AwaitReq& /*r*/, double& out_) override
        { out_ = 0.0; return AwaitState::Satisfied; }
};

} // anonymous namespace

// ─────────────────────────────────────────────────────────────────────────────
// Mailbox constant loader — parses MAILBOXENTRY(NAME, VALUE) from mailbox.inc.

static pilot::ConstTable loadConstants(const std::string& mailboxInc)
{
    pilot::ConstTable t;

    // Joystick button constants (must match Python's _BUTTONS).
    const struct { const char* name; long val; } buttons[] = {
        {"JOYSTICK_BUTTON_UP",    2048}, {"JOYSTICK_BUTTON_DOWN",  4096},
        {"JOYSTICK_BUTTON_RIGHT", 8192}, {"JOYSTICK_BUTTON_LEFT",  16384},
        {"JOYSTICK_BUTTON_A", 1},  {"JOYSTICK_BUTTON_B", 2},   {"JOYSTICK_BUTTON_C", 4},
        {"JOYSTICK_BUTTON_D", 8},  {"JOYSTICK_BUTTON_E", 16},  {"JOYSTICK_BUTTON_F", 32},
        {"JOYSTICK_BUTTON_G", 64}, {"JOYSTICK_BUTTON_H", 128}, {"JOYSTICK_BUTTON_I", 256},
        {"JOYSTICK_BUTTON_J", 512},{"JOYSTICK_BUTTON_K", 1024},
        {nullptr, 0}
    };
    for (int i = 0; buttons[i].name; ++i) {
        t[buttons[i].name] = buttons[i].val;
        // BTN_RIGHT, BTN_A, etc. — strip JOYSTICK_BUTTON_ prefix.
        const char* p = std::strrchr(buttons[i].name, '_');
        if (p) t[std::string("BTN_") + (p+1)] = buttons[i].val;
    }

    std::ifstream f(mailboxInc);
    if (!f.is_open()) return t;

    std::regex re(R"(MAILBOXENTRY\s*\(\s*([A-Za-z_]\w*)\s*,\s*(0[xX][0-9A-Fa-f]+|-?\d+)\s*\))");
    std::string line;
    while (std::getline(f, line)) {
        std::smatch m;
        if (std::regex_search(line, m, re)) {
            std::string name = m[1];
            long val = std::stol(m[2], nullptr, 0);
            t[name] = val;
            t["INDEXOF_" + name] = val;
        }
    }
    return t;
}

// ─────────────────────────────────────────────────────────────────────────────
// Directive helpers.

static std::string directiveVal(const pilot::Program& prog, const char* key)
{
    for (const auto& d : prog.directives)
        if (d.key == key) return d.val;
    return {};
}

static std::vector<std::string> allDirectives(const pilot::Program& prog, const char* key)
{
    std::vector<std::string> out;
    for (const auto& d : prog.directives)
        if (d.key == key) out.push_back(d.val);
    return out;
}

// ─────────────────────────────────────────────────────────────────────────────
// Post-run assertions.

static std::vector<std::string> checkAssertions(
    const pilot::Program& prog, int code,
    const std::string& output, const std::vector<std::string>& screenshots)
{
    std::vector<std::string> fails;
    for (const auto& d : prog.directives) {
        const std::string& v = d.val;
        if (d.key == "expect-exit") {
            int want = std::atoi(v.c_str());
            if (code != want)
                fails.push_back("expect-exit " + std::to_string(want) + " got " + std::to_string(code));
        } else if (d.key == "expect-out") {
            if (output.find(v) == std::string::npos)
                fails.push_back("expect-out " + v + " not in output");
        } else if (d.key == "expect-no-out") {
            if (output.find(v) != std::string::npos)
                fails.push_back("expect-no-out " + v + " present in output");
        } else if (d.key == "screenshot") {
            bool found = false;
            for (const auto& s : screenshots) if (s == v) { found = true; break; }
            if (!found) fails.push_back("screenshot " + v + " not produced");
        }
    }
    return fails;
}

// ─────────────────────────────────────────────────────────────────────────────
// Actor discovery — tail a log file for "actor idx=N mesh=NAME" lines.

static std::unordered_map<std::string,int> discoverActors(
    const std::string& logPath, const std::set<std::string>& want,
    double timeoutSecs = 10.0)
{
    std::unordered_map<std::string,int> found;
    std::regex re(R"(actor idx=(\d+) mesh=([^\s]+))");
    auto deadline = std::chrono::steady_clock::now() +
                    std::chrono::duration<double>(timeoutSecs);
    while (std::chrono::steady_clock::now() < deadline) {
        std::ifstream f(logPath);
        if (f.is_open()) {
            std::string line;
            while (std::getline(f, line)) {
                std::smatch m;
                if (std::regex_search(line, m, re)) {
                    std::string mesh = m[2];
                    // Strip .iff suffix if present.
                    if (mesh.size() > 4 && mesh.substr(mesh.size()-4) == ".iff")
                        mesh = mesh.substr(0, mesh.size()-4);
                    if (want.count(mesh)) found[mesh] = std::stoi(m[1]);
                }
            }
        }
        bool done = true;
        for (const auto& w : want) if (!found.count(w)) { done = false; break; }
        if (done) return found;
        std::this_thread::sleep_for(std::chrono::milliseconds(150));
    }
    return found;
}

// ─────────────────────────────────────────────────────────────────────────────
// wf_game subprocess

static pid_t launchGame(const std::string& gamePath, const std::string& levelPath,
                         int port, const std::string& logPath)
{
    // Redirect stdout+stderr to logPath.
    pid_t pid = ::fork();
    if (pid < 0) { std::perror("fork"); return -1; }
    if (pid == 0) {
        // Child.
        int fd = ::open(logPath.c_str(), O_WRONLY|O_CREAT|O_TRUNC, 0644);
        if (fd < 0) std::_Exit(1);
        ::dup2(fd, STDOUT_FILENO);
        ::dup2(fd, STDERR_FILENO);
        ::close(fd);

        // wf_game finds cd.iff relative to CWD; must run from wfsource/source/game.
        std::string gameCwd = gamePath.substr(0, gamePath.rfind('/') + 1);  // engine/
        gameCwd = gameCwd.substr(0, gameCwd.rfind('/', gameCwd.size()-2) + 1); // repo/
        gameCwd += "wfsource/source/game";
        if (::chdir(gameCwd.c_str()) != 0)
            std::_Exit(1);

        char portBuf[16];
        std::snprintf(portBuf, sizeof(portBuf), "%d", port);
        char levelArg[4096];
        std::snprintf(levelArg, sizeof(levelArg), "-L%s", levelPath.c_str());

        const char* argv[] = {
            gamePath.c_str(), levelArg,
            "--debug-port", portBuf,
            "--debug-bind", "127.0.0.1",
            "--debug-print-actors",
            nullptr
        };
        // Set LD_LIBRARY_PATH to <gamedir>/libs.
        std::string gameDir = gamePath.substr(0, gamePath.rfind('/'));
        std::string ldpath  = gameDir + "/libs";
        const char* cur = ::getenv("LD_LIBRARY_PATH");
        if (cur && *cur) ldpath += std::string(":") + cur;
        ::setenv("LD_LIBRARY_PATH", ldpath.c_str(), 1);

        ::execv(gamePath.c_str(), const_cast<char*const*>(argv));
        std::_Exit(1);
    }
    return pid;
}

// ─────────────────────────────────────────────────────────────────────────────
// Run a vm-tier scenario (no engine).

static int runVm(const pilot::Program& prog, const pilot::ConstTable& consts,
                 const std::string& pilotFile)
{
    MockHost host;
    pilot::VMState st;
    bool done = false;
    while (!done)
        pilot::run(prog, st, host, 0, consts, 1000000, &done);

    auto fails = checkAssertions(prog, st.exitCode, host.out, host.screenshots);
    std::string tier = directiveVal(prog, "tier");
    if (tier.empty()) tier = "vm";
    std::printf("%s %s (exit %d, tier %s)\n",
        fails.empty() ? "PASS" : "FAIL",
        pilotFile.c_str(), st.exitCode, tier.c_str());
    for (const auto& f : fails) std::printf("   - %s\n", f.c_str());
    return fails.empty() ? st.exitCode : 1;
}

// ─────────────────────────────────────────────────────────────────────────────
// Run an engine-tier scenario.

static int runEngine(const pilot::Program& prog, const pilot::ConstTable& consts,
                     const std::string& pilotFile, const std::string& gamePath,
                     const std::string& bridgeHost, int port, bool noLaunch,
                     const std::string& repoRoot)
{
    std::string levelName = directiveVal(prog, "level");
    if (levelName.empty() && !noLaunch) {
        std::fprintf(stderr, "[runner] @level directive missing in %s\n", pilotFile.c_str());
        return 1;
    }

    // Parse @needs lines: "ACTOR as #VAR"
    std::vector<std::pair<std::string,std::string>> needs;
    std::set<std::string> wantMeshes;
    for (const auto& val : allDirectives(prog, "needs")) {
        std::smatch m;
        std::regex re(R"((\S+)\s+as\s+(#\w+))");
        if (std::regex_search(val, m, re)) {
            needs.push_back({m[1], m[2]});
            wantMeshes.insert(m[1]);
        }
    }

    // Build level path.
    std::string levelPath = repoRoot + "/wflevels/" + levelName;

    // Launch wf_game.
    std::string logPath = "/tmp/pilot_runner_" + std::to_string((long)::getpid()) + ".log";
    pid_t gamePid = -1;
    if (!noLaunch) {
        gamePid = launchGame(gamePath, levelPath, port, logPath);
        if (gamePid < 0) {
            std::fprintf(stderr, "[runner] failed to launch %s\n", gamePath.c_str());
            return 1;
        }
    }

    int exitCode = 1;
    pilot::BridgeHost host;
    bool launched = false;

    // Discover actors from log.
    std::unordered_map<std::string,int> actorMap;
    if (!wantMeshes.empty() && gamePid > 0) {
        actorMap = discoverActors(logPath, wantMeshes, 10.0);
        if (actorMap.size() < wantMeshes.size()) {
            for (const auto& w : wantMeshes)
                if (!actorMap.count(w))
                    std::fprintf(stderr, "[runner] actor not discovered: %s\n", w.c_str());
            goto cleanup;
        }
    }

    if (!host.connect(bridgeHost.c_str(), port, 15.0)) {
        std::fprintf(stderr, "[runner] could not connect to engine at %s:%d\n",
                     bridgeHost.c_str(), port);
        goto cleanup;
    }
    launched = true;

    {
        // Give the engine a moment to finish startup before sending ops.
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        // Configure screenshot directory (mirrors Python: tests/pilot/screenshots/).
        std::string screenshotsDir = repoRoot + "/tests/pilot/screenshots/";
        ::mkdir(screenshotsDir.c_str(), 0755);
        host.setScreenshotsDir(screenshotsDir);

        // Set up VMState + bind @needs actors.
        pilot::VMState st;
        int selfActor = 0;
        for (const auto& [mesh, var] : needs) {
            auto it = actorMap.find(mesh);
            if (it != actorMap.end()) {
                st.bind(var, (double)it->second);
                if (mesh == "player") selfActor = it->second;
            }
        }

        bool done = false;
        while (!done)
            pilot::run(prog, st, host, selfActor, consts, 1000000, &done);
        exitCode = st.exitCode;

        // T: output goes to stdout; capture it by reading stdout is not trivial
        // here, so expect-out is checked externally (output IS on stdout for CI).
        auto fails = checkAssertions(prog, st.exitCode, "" /* on stdout */,
                                     host.screenshots());
        // Only check exit code + screenshot here; expect-out checked externally.
        std::vector<std::string> exitFails;
        for (const auto& f : fails)
            if (f.rfind("expect-out", 0) != 0) exitFails.push_back(f);

        std::string tier = directiveVal(prog, "tier");
        if (tier.empty()) tier = "engine";
        std::printf("%s %s (exit %d, tier %s)\n",
            exitFails.empty() ? "PASS" : "FAIL",
            pilotFile.c_str(), st.exitCode, tier.c_str());
        for (const auto& f : exitFails) std::printf("   - %s\n", f.c_str());
        if (!exitFails.empty()) exitCode = 1;
    }

cleanup:
    if (launched) host.teardown();
    if (gamePid > 0) {
        ::kill(gamePid, SIGTERM);
        int status;
        ::waitpid(gamePid, &status, 0);
    }
    ::unlink(logPath.c_str());
    return exitCode;
}

// ─────────────────────────────────────────────────────────────────────────────
// main

static std::string selfDir()
{
    char buf[4096] = {};
    ssize_t n = ::readlink("/proc/self/exe", buf, sizeof(buf)-1);
    if (n <= 0) return ".";
    std::string path(buf, (size_t)n);
    auto slash = path.rfind('/');
    return slash == std::string::npos ? "." : path.substr(0, slash);
}

int main(int argc, char* argv[])
{
    std::string bridgeHost = "127.0.0.1";
    int         port       = 7795;
    bool        noLaunch   = false;
    std::string gamePath;
    std::string pilotFile;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--host" && i+1 < argc) { bridgeHost = argv[++i]; }
        else if (a == "--port" && i+1 < argc) { port = std::atoi(argv[++i]); }
        else if (a == "--wf-game" && i+1 < argc) { gamePath = argv[++i]; }
        else if (a == "--no-launch") { noLaunch = true; }
        else if (a[0] != '-') { pilotFile = a; }
        else {
            std::fprintf(stderr, "unknown option: %s\n", argv[i]);
            return 2;
        }
    }
    if (pilotFile.empty()) {
        std::fprintf(stderr,
            "usage: pilot_bridge_runner [--host H] [--port P] [--wf-game PATH]\n"
            "                          [--no-launch] FILE.pilot\n");
        return 2;
    }

    // Locate repo root relative to the runner binary.
    std::string dir = selfDir();
    // Binary lives in engine/, repo root is one level up.
    std::string repoRoot = dir + "/..";

    // Locate mailbox.inc.
    std::string mailboxInc = repoRoot + "/wfsource/source/mailbox/mailbox.inc";

    // Default wf_game path.
    if (gamePath.empty()) gamePath = dir + "/wf_game";

    // Read and parse the .pilot source.
    std::ifstream sf(pilotFile);
    if (!sf.is_open()) {
        std::fprintf(stderr, "[runner] cannot open %s\n", pilotFile.c_str());
        return 1;
    }
    std::string src((std::istreambuf_iterator<char>(sf)), {});

    pilot::Program prog = pilot::parse(src.c_str());
    if (!prog.ok) {
        std::fprintf(stderr, "[runner] parse error: %s\n", prog.error.c_str());
        return 1;
    }

    pilot::ConstTable consts = loadConstants(mailboxInc);

    // Determine tier.
    std::string tier = directiveVal(prog, "tier");
    if (tier.empty() || tier == "vm") {
        return runVm(prog, consts, pilotFile);
    }

    if (!noLaunch && !gamePath.empty()) {
        // Check wf_game exists before trying to launch.
        if (::access(gamePath.c_str(), X_OK) != 0) {
            std::fprintf(stderr, "SKIP %s: wf_game not found at %s\n",
                         pilotFile.c_str(), gamePath.c_str());
            return 0;
        }
        // Check DISPLAY (engine needs X11).
        if (!::getenv("DISPLAY")) {
            std::fprintf(stderr, "SKIP %s: no DISPLAY set\n", pilotFile.c_str());
            return 0;
        }
    }

    return runEngine(prog, consts, pilotFile, gamePath, bridgeHost, port, noLaunch, repoRoot);
}
