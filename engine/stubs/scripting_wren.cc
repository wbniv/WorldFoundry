// scripting_wren.cc — Wren scripting backend for wren_engine namespace.
//
// Compiled in when WF_ENABLE_WREN is defined (via build_game.sh).
// Sigil: `//wren\n` — ScriptRouter dispatches here before the generic `//`.
//
// Each RunScript call creates a fresh Wren module (unique name "s<N>") so
// that module-level var declarations in the preamble don't collide across
// script invocations.  The GC reclaims old modules over time.
//
// Mailbox bridge: Env is a foreign class declared in the preamble injected
// before every script.
//   Env.read_mailbox(idx)         — slot 1 = idx (int)  → sets slot 0 = val
//   Env.write_mailbox(idx, val)   — slot 1 = idx, slot 2 = val
//
// INDEXOF_* / JOYSTICK_BUTTON_* constants arrive via AddConstantArray and
// are appended to g_preamble as `var NAME = VALUE\n` lines.
//
// Multi-tick Fiber support
// ------------------------
// A script that wants to span multiple ticks assigns a Fiber to a module-level
// variable named `_thread`:
//
//   var _thread = Fiber.new {
//       while (Env.read_mailbox(INDEXOF_TRIGGER_A) == 0) Fiber.yield()
//       Env.write_mailbox(INDEXOF_ALARM, 1)
//       ...
//   }
//
// After wrenInterpret, RunScript checks for `_thread`, grabs a WrenHandle*,
// and calls fiber.call() immediately (first step).  On subsequent ticks,
// RunScript resumes the stored handle instead of re-interpreting the script.
// When fiber.isDone becomes true (or a runtime error occurs) the handle is
// released and the actor reverts to normal per-tick execution.

#ifdef WF_ENABLE_WREN

#include "scripting_wren.hp"
#include <scripting/scriptinterpreter.hp>
#include <mailbox/mailbox.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unordered_map>

// Wren amalgamation — compiled as a C translation unit; include header here.
extern "C" {
#include <wren.h>
}

// ---------------------------------------------------------------------------
// Module state

static WrenVM*            g_vm       = nullptr;
static MailboxesManager*  g_mgr      = nullptr;
static int                g_curObj   = 0;
static int                g_scriptId = 0;
static std::string        g_preamble;

// Per-actor live Fiber handles: objectIndex → WrenHandle* for the Fiber object.
// Present while the fiber is suspended; cleared on completion or error.
static std::unordered_map<int, WrenHandle*> gActorFiberHandles;

// Persistent call handles created once in Init, released in Shutdown.
static WrenHandle* gFiberCallHandle   = nullptr; // fiber.call()
static WrenHandle* gFiberIsDoneHandle = nullptr; // fiber.isDone

// ---------------------------------------------------------------------------
// Foreign class preamble — declared in every script module.

static const char* kEnvDecl =
    "foreign class Env {\n"
    "  foreign static read_mailbox(idx)\n"
    "  foreign static write_mailbox(idx, val)\n"
    "}\n";

// ---------------------------------------------------------------------------
// Wren host callbacks

static void wren_write(WrenVM* /*vm*/, const char* text)
{
    fputs(text, stderr);
}

static void wren_error(WrenVM* /*vm*/, WrenErrorType type,
                       const char* module, int line, const char* message)
{
    switch (type) {
        case WREN_ERROR_COMPILE:
            fprintf(stderr, "wren [%s:%d] compile error: %s\n",
                    module ? module : "?", line, message);
            break;
        case WREN_ERROR_RUNTIME:
            fprintf(stderr, "wren runtime error: %s\n", message);
            break;
        case WREN_ERROR_STACK_TRACE:
            fprintf(stderr, "wren [%s:%d] in %s\n",
                    module ? module : "?", line, message);
            break;
    }
}

// Foreign method: Env.read_mailbox(idx) → slot 0 = float value
static void wren_read_mailbox(WrenVM* vm)
{
    int idx = (int)wrenGetSlotDouble(vm, 1);
    float val = 0.0f;
    if (g_mgr) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
        val = mb.ReadMailbox(idx).AsFloat();
    }
    wrenSetSlotDouble(vm, 0, (double)val);
}

// Foreign method: Env.write_mailbox(idx, val)
static void wren_write_mailbox(WrenVM* vm)
{
    int   idx = (int)wrenGetSlotDouble(vm, 1);
    float val = (float)wrenGetSlotDouble(vm, 2);
    if (g_mgr) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
        mb.WriteMailbox(idx, Scalar::FromFloat(val));
    }
}

static WrenForeignMethodFn wren_bind_method(WrenVM* /*vm*/,
    const char* /*module*/, const char* className,
    bool isStatic, const char* signature)
{
    if (isStatic && strcmp(className, "Env") == 0) {
        if (strcmp(signature, "read_mailbox(_)")   == 0) return wren_read_mailbox;
        if (strcmp(signature, "write_mailbox(_,_)") == 0) return wren_write_mailbox;
    }
    return nullptr;
}

// Allocator for Env instances (never called in practice — only static methods
// are used, so Env is never instantiated — but Wren requires the allocator to
// be present when the class is declared as foreign).
static void wren_alloc_env(WrenVM* vm)
{
    wrenSetSlotNewForeign(vm, 0, 0, 0);
}

static WrenForeignClassMethods wren_bind_class(WrenVM* /*vm*/,
    const char* /*module*/, const char* className)
{
    WrenForeignClassMethods m = { nullptr, nullptr };
    if (strcmp(className, "Env") == 0)
        m.allocate = wren_alloc_env;
    return m;
}

// ---------------------------------------------------------------------------
// Fiber helpers

// Call fiber.call() on a stored handle. Returns true if the fiber is now done
// (either it finished normally or errored). Releases and erases the handle
// from gActorFiberHandles on completion.
static bool FiberStep(int objectIndex, WrenHandle* h)
{
    wrenEnsureSlots(g_vm, 1);
    wrenSetSlotHandle(g_vm, 0, h);
    WrenInterpretResult r = wrenCall(g_vm, gFiberCallHandle);
    if (r != WREN_RESULT_SUCCESS) {
        wrenReleaseHandle(g_vm, h);
        gActorFiberHandles.erase(objectIndex);
        return true;
    }
    // Check fiber.isDone
    wrenSetSlotHandle(g_vm, 0, h);
    wrenCall(g_vm, gFiberIsDoneHandle);
    bool done = (wrenGetSlotType(g_vm, 0) == WREN_TYPE_BOOL &&
                 wrenGetSlotBool(g_vm, 0));
    if (done) {
        wrenReleaseHandle(g_vm, h);
        gActorFiberHandles.erase(objectIndex);
    }
    return done;
}

// ---------------------------------------------------------------------------
// wren_engine namespace — public plug interface

namespace wren_engine {

void Init(MailboxesManager& mgr)
{
    g_mgr      = &mgr;
    g_curObj   = 0;
    g_scriptId = 0;
    g_preamble = kEnvDecl;

    WrenConfiguration cfg;
    wrenInitConfiguration(&cfg);
    cfg.writeFn             = wren_write;
    cfg.errorFn             = wren_error;
    cfg.bindForeignMethodFn = wren_bind_method;
    cfg.bindForeignClassFn  = wren_bind_class;

    g_vm = wrenNewVM(&cfg);
    if (!g_vm) {
        fprintf(stderr, "wren: wrenNewVM failed\n");
        return;
    }

    gFiberCallHandle   = wrenMakeCallHandle(g_vm, "call()");
    gFiberIsDoneHandle = wrenMakeCallHandle(g_vm, "isDone");
}

void Shutdown()
{
    if (g_vm) {
        for (auto& kv : gActorFiberHandles)
            wrenReleaseHandle(g_vm, kv.second);
        gActorFiberHandles.clear();

        if (gFiberCallHandle)   { wrenReleaseHandle(g_vm, gFiberCallHandle);   gFiberCallHandle   = nullptr; }
        if (gFiberIsDoneHandle) { wrenReleaseHandle(g_vm, gFiberIsDoneHandle); gFiberIsDoneHandle = nullptr; }

        wrenFreeVM(g_vm);
        g_vm = nullptr;
    }
    g_mgr = nullptr;
    g_curObj = 0;
    g_preamble.clear();
}

void AddConstantArray(IntArrayEntry* entryList)
{
    // Append `var NAME = VALUE\n` to the preamble injected before each script.
    char buf[128];
    for (IntArrayEntry* p = entryList; p->name; p++) {
        snprintf(buf, sizeof(buf), "var %s = %d\n", p->name, p->value);
        g_preamble += buf;
    }
}

void DeleteConstantArray(IntArrayEntry* /*entryList*/)
{
    // Preamble string is append-only; constants persist for VM lifetime.
}

float RunScript(const char* src, int objectIndex)
{
    if (!src || !*src || !g_vm) return 0.0f;

    g_curObj = objectIndex;

    // Resume a live fiber instead of re-interpreting the script.
    {
        auto it = gActorFiberHandles.find(objectIndex);
        if (it != gActorFiberHandles.end()) {
            FiberStep(objectIndex, it->second);
            return 0.0f;
        }
    }

    // Build full Wren source: preamble + script.
    // The `//wren\n` first line is a valid Wren `//` comment — no stripping needed.
    std::string full = g_preamble;
    full += src;

    char mod[32];
    snprintf(mod, sizeof(mod), "s%d", g_scriptId++);

    WrenInterpretResult r = wrenInterpret(g_vm, mod, full.c_str());
    if (r != WREN_RESULT_SUCCESS) {
        fprintf(stderr, "wren: script error in module %s\n", mod);
        return 0.0f;
    }

    // Detect multi-tick fiber: check for a `_thread` variable of object type.
    wrenEnsureSlots(g_vm, 1);
    if (wrenHasVariable(g_vm, mod, "_thread")) {
        wrenGetVariable(g_vm, mod, "_thread", 0);
        if (wrenGetSlotType(g_vm, 0) == WREN_TYPE_UNKNOWN) {
            WrenHandle* h = wrenGetSlotHandle(g_vm, 0);
            gActorFiberHandles[objectIndex] = h;
            FiberStep(objectIndex, h);  // first call — starts the fiber
        }
    }

    return 0.0f;
}

} // namespace wren_engine

#endif // WF_ENABLE_WREN
