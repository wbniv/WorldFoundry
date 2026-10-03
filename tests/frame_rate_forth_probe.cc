// Real optional Forth bridges; a sampler-backed mailbox isolates their numeric
// representation from unrelated level scripts and rendering dependencies.
#include <game/frame_rate.h>
#include <mailbox/mailbox.hp>
#include <scripting/scriptinterpreter.hp>
#include "scripting_forth.hp"
#include <cmath>
#include <cstdio>
#include <cstdlib>

Mailboxes::~Mailboxes() = default;
MailboxesManager::~MailboxesManager() = default;
void _sys_assert(int, const char* expression, const char* file, int line) {
    std::fprintf(stderr, "assert %s at %s:%d\n", expression, file, line);
    std::abort();
}
#if SW_DBSTREAM
void Mailboxes::_Print(std::ostream&) const {}
#endif

struct ProbeMailboxes : Mailboxes, MailboxesManager {
    FrameRateSampler sampler;
    Scalar scratch = Scalar::FromFloat(-30000);
    Mailboxes& LookupMailboxes(int object) override {
        if (object != 0) std::abort();
        return *this;
    }
    Scalar ReadMailbox(int32 index) const override {
        if (index == EMAILBOX_FRAMERATE) return Scalar::FromDouble(sampler.Read(0));
        if (index == 1899) return scratch;
        std::abort();
    }
    void WriteMailbox(int32 index, Scalar value) override {
        if (index != 1899) std::abort();
        scratch = value;
    }
};

int main() {
    ProbeMailboxes mb;
    forth_engine::Init(mb);
    IntArrayEntry constants[] = {{"INDEXOF_FRAMERATE", EMAILBOX_FRAMERATE}, {nullptr, 0}};
    forth_engine::AddConstantArray(constants);
    const char* source = "\\ fps probe\nINDEXOF_FRAMERATE read-mailbox 1899 write-mailbox\n";
    for (double interval : {0.016, 0.5, 2.0}) {
        mb.sampler.Reset();
        auto start = FrameRateSampler::TimePoint{};
        mb.sampler.BeginFrame(start, 0);
        mb.sampler.EndFrame(start + std::chrono::duration_cast<FrameRateSampler::Clock::duration>(std::chrono::duration<double>(interval)), 0);
        mb.scratch = Scalar::FromFloat(-30000);
        forth_engine::RunScript(source, 0);
        const double raw = mb.ReadMailbox(EMAILBOX_FRAMERATE).AsFloat();
        const double actual = mb.scratch.AsFloat();
        if (actual != std::trunc(raw)) {
            std::fprintf(stderr, "FAIL optional Forth raw=%g script=%g expected=%g\n", raw, actual, std::trunc(raw));
            return 1;
        }
        std::printf("PASS optional Forth raw=%g script=%g (integer bridge)\n", raw, actual);
    }
    forth_engine::Shutdown();
}
