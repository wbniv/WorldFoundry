// pilot_test.cc — standalone PILOT conformance runner for the VM tier.
//
// Builds against pilot_core only (no engine). Proves the C++ core produces the
// same results as the Python reference driver on tests/pilot/*.pilot (@tier vm).
//
//   g++ -std=c++17 -I engine/pilot engine/pilot/pilot_core.cc engine/pilot/pilot_test.cc -o /tmp/pilot_test
//   /tmp/pilot_test tests/pilot/arith.pilot

#include "pilot_core.hp"

#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <unordered_map>

using namespace pilot;

namespace {

// Capture host: T:/TH: to a buffer; mailboxes in-memory; awaits resolve
// immediately (the VM tier uses none). Mirrors tests/pilot MockHost.
struct CaptureHost : PilotHost
{
    std::string out;
    std::unordered_map<long, double> mb;
    double clock = 0.0;

    void   Type(const std::string& t, bool nl) override { out += t; if (nl) out += "\n"; }
    double ReadMailbox(int a, int m) override { auto it = mb.find(((long)a << 20) | m); return it != mb.end() ? it->second : 0.0; }
    void   SetMailbox(int a, int m, double v) override { mb[((long)a << 20) | m] = v; }
    double ClockSeconds() override { return clock; }
    AwaitState CheckAwait(const AwaitReq&, double& v) override { v = 0.0; return AwaitState::Satisfied; }
};

std::string readFile(const char* path)
{
    std::ifstream f(path);
    std::stringstream ss; ss << f.rdbuf();
    return ss.str();
}

} // namespace

int main(int argc, char** argv)
{
    if (argc != 2) { std::fprintf(stderr, "usage: pilot_test FILE.pilot\n"); return 2; }

    std::string src = readFile(argv[1]);
    Program prog = parse(src.c_str());

    CaptureHost host;
    ConstTable consts;  // VM tier needs no engine constants
    VMState st;
    bool done = false;
    int guard = 0;
    while (!done && guard++ < 100000)
        run(prog, st, host, /*self*/0, consts, /*budget*/256, &done);
    int code = st.exited ? st.exitCode : 0;

    // Check @expect-* directives.
    std::vector<std::string> fails;
    auto contains = [&](const std::string& s) { return host.out.find(s) != std::string::npos; };
    for (auto& d : prog.directives) {
        if (d.key == "expect-exit") {
            if (code != std::atoi(d.val.c_str())) fails.push_back("expect-exit " + d.val + ", got " + std::to_string(code));
        } else if (d.key == "expect-out") {
            if (!contains(d.val)) fails.push_back("expect-out '" + d.val + "' not in output");
        } else if (d.key == "expect-no-out") {
            if (contains(d.val)) fails.push_back("expect-no-out '" + d.val + "' present");
        }
    }

    bool ok = fails.empty() && prog.ok;
    std::printf("%s %s (exit %d)\n", ok ? "PASS" : "FAIL", argv[1], code);
    if (!prog.ok) std::printf("   - parse error\n");
    for (auto& f : fails) std::printf("   - %s\n", f.c_str());
    return ok ? 0 : 1;
}
