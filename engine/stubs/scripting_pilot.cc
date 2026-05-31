// scripting_pilot.cc — PILOT engine plug. Wraps pilot_core + MailboxHost and
// presents the five-function ABI ScriptRouter expects. See scripting_pilot.hp.

#include "scripting_pilot.hp"

#ifdef WF_PILOT_ENGINE_BUILTIN

#include <scripting/scriptinterpreter.hp>   // IntArrayEntry
#include <mailbox/mailbox.hp>               // MailboxesManager

#include "pilot_core.hp"                    // -I engine/pilot
#include "host_mailbox.hp"

#include <cctype>
#include <cstring>
#include <string>
#include <unordered_map>

// Phase 4 HUD text — ring buffer defined in main.cc, rendered in display.cc.
// Declared here (global namespace) so InEngineMailboxHost can access them.
#if defined(DESIGNER_CHEATS)
extern char wf_hud_pilot[4][128];
extern int  wf_hud_pilot_count;
extern char wf_hud_pilot_pending[128];
#endif

namespace pilot_engine {

using namespace pilot;

#if defined(DESIGNER_CHEATS)

// MailboxHost subclass that additionally writes T:/TH: output to the HUD ring.
class InEngineMailboxHost : public MailboxHost
{
public:
    void Type(const std::string& text, bool nl) override
    {
        MailboxHost::Type(text, nl);   // stderr (existing behaviour)
        size_t cur = std::strlen(wf_hud_pilot_pending);
        std::strncat(wf_hud_pilot_pending, text.c_str(),
                     sizeof(wf_hud_pilot_pending) - 1 - cur);
        if (nl) {
            int slot = wf_hud_pilot_count % 4;
            std::strncpy(wf_hud_pilot[slot], wf_hud_pilot_pending, 127);
            wf_hud_pilot[slot][127] = '\0';
            wf_hud_pilot_pending[0] = '\0';
            ++wf_hud_pilot_count;
        }
    }
};
static InEngineMailboxHost g_host;
#else
// Module state (mirrors scripting_zforth.cc's module-static pattern).
static MailboxHost g_host;                                     // no heap
#endif
static ConstTable  g_consts;
static std::unordered_map<const char*, Program> g_progCache;   // by src pointer
static std::unordered_map<int, VMState>          g_actorState; // by objectIndex
static std::unordered_map<int, const char*>      g_actorSrc;   // index-reuse guard

void Init(MailboxesManager& mgr)
{
    g_host.setManager(&mgr);
}

void Shutdown()
{
    g_host.setManager(nullptr);
    g_progCache.clear();
    g_actorState.clear();
    g_actorSrc.clear();
    g_consts.clear();
}

void AddConstantArray(IntArrayEntry* e)
{
    for (; e && e->name; ++e) {
        g_consts[e->name] = e->value;
        if (std::strncmp(e->name, "INDEXOF_", 8) == 0)
            g_consts[e->name + 8] = e->value;                         // prefix-free
        else if (std::strncmp(e->name, "JOYSTICK_BUTTON_", 16) == 0)
            g_consts[std::string("BTN_") + (e->name + 16)] = e->value; // BTN_RIGHT…
    }
}

void DeleteConstantArray(IntArrayEntry*) { /* table not shrunk */ }

bool LooksLikePilot(const char* src)
{
    if (!src) return false;
    const char* p = src;
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') ++p;
    return std::strncmp(p, "R:pilot", 7) == 0;
}

float RunScript(const char* src, int objectIndex)
{
    if (!src) return 0.0f;

    auto pit = g_progCache.find(src);
    if (pit == g_progCache.end())
        pit = g_progCache.emplace(src, parse(src)).first;
    const Program& prog = pit->second;

    // Reset per-actor state if this index is now running a different script
    // (index reuse after despawn) so a halted prior program doesn't suppress it.
    const char*& seen = g_actorSrc[objectIndex];
    if (seen != src) { g_actorState[objectIndex] = VMState(); seen = src; }

    VMState& st = g_actorState[objectIndex];
    g_host.setCurObj(objectIndex);
    bool done = false;
    return (float)run(prog, st, g_host, objectIndex, g_consts, /*budget*/256, &done);
}

} // namespace pilot_engine

#endif // WF_PILOT_ENGINE_BUILTIN
