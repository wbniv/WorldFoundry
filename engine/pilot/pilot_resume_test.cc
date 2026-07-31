// pilot_resume_test.cc — proves the frame-resumable VM: a blocking WM: await
// parks the program counter and resumes across run() calls (the in-engine
// mechanism MailboxHost relies on). Pure pilot_core; FrameHost mirrors
// MailboxHost's await semantics with a mailbox that changes between frames.
//
//   g++ -std=c++17 -I engine/pilot engine/pilot/pilot_core.cc engine/pilot/pilot_resume_test.cc -o /tmp/pilot_resume_test

#include "pilot_core.hp"

#include <cstdio>
#include <string>
#include <unordered_map>

using namespace pilot;

namespace {

struct FrameHost : PilotHost
{
    std::string out;
    std::unordered_map<long, double> mb;
    double clk = 0.0;

    static long key(int a, int m) { return ((long)a << 20) | (long)m; }

    void   Type(const std::string& t, bool nl) override { out += t; if (nl) out += "\n"; }
    double ReadMailbox(int a, int m) override { auto it = mb.find(key(a, m)); return it != mb.end() ? it->second : 0.0; }
    void   SetMailbox(int a, int m, double v) override { mb[key(a, m)] = v; }
    double ClockSeconds() override { return clk; }

    AwaitState CheckAwait(const AwaitReq& r, double& o) override
    {
        if (r.kind == AwaitKind::ClockSeconds) {
            o = clk;
            return clk >= r.value ? AwaitState::Satisfied : AwaitState::Pending;
        }
        double c = ReadMailbox(r.actorIdx, r.mailbox); o = c;
        bool ok = false;
        switch (r.op) {
            case RelOp::Gt: ok = c >  r.value; break;
            case RelOp::Ge: ok = c >= r.value; break;
            case RelOp::Lt: ok = c <  r.value; break;
            case RelOp::Le: ok = c <= r.value; break;
            case RelOp::Ne: ok = c != r.value; break;
            default:        ok = c == r.value; break;
        }
        if (ok) return AwaitState::Satisfied;
        if (r.timeoutSecs > 0 && clk - r.startSecs > r.timeoutSecs) return AwaitState::TimedOut;
        return AwaitState::Pending;
    }
};

} // namespace

int main()
{
    // Wait for self-mailbox 100 to exceed 5, then record the crossing value into
    // mailbox 200. mb(100) ramps 0,1,2,... so it crosses at frame 6.
    const char* src =
        "R:pilot\n"
        "WM:0 100 > 5 timeout 100\n"
        "M:#last > 5\n"
        "TY:CROSSED at $#last\n"
        "C:mb(200) = #last\n"
        "E:\n";

    Program prog = parse(src);
    FrameHost host;
    ConstTable consts;
    VMState st;

    bool done = false;
    int frame = 0;
    for (; frame < 20 && !done; ++frame) {
        host.clk = frame * 0.1;
        host.SetMailbox(0, 100, (double)frame);
        run(prog, st, host, /*self*/0, consts, /*budget*/256, &done);
    }

    double mb200 = host.ReadMailbox(0, 200);
    bool ok = done
           && host.out.find("CROSSED") != std::string::npos
           && mb200 > 5.0
           && frame >= 7;   // must have taken multiple frames to resume
    std::printf("%s resume-test: frames=%d out=%s mb200=%g done=%d\n",
                ok ? "PASS" : "FAIL", frame, host.out.c_str(), mb200, (int)done);
    return ok ? 0 : 1;
}
