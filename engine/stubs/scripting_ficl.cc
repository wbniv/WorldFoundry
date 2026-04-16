// scripting_ficl.cc — ficl Forth backend for forth_engine namespace.
//
// Compiled in when WF_FORTH_ENGINE_FICL is defined (via build_game.sh).
// Sigil: `\` — handled by ScriptRouter before dispatch here.
//
// Cell type: FICL_INT (native integer, 64-bit on x86-64). Mailbox values
// are passed as integers; float mailbox values on PC dev are truncated.
// For integer-valued mailboxes (typical for WF objects) this is correct.
//
// Bridge words registered as named C words via ficlBuild:
//   read-mailbox  ( idx -- val ) — FICL_INT index → FICL_INT value
//   write-mailbox ( val idx -- ) — FICL_INT value + index → write mailbox
//
// Constants are loaded at AddConstantArray time via ficlEvaluate:
//   3024 constant INDEXOF_INPUT
//   ...

#ifdef WF_FORTH_ENGINE_FICL

#include "scripting_forth.hp"

extern "C" {
#include <ficl.h>
}

#include <scripting/scriptinterpreter.hp>
#include <mailbox/mailbox.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

// ---------------------------------------------------------------------------
// Module state

static FICL_SYSTEM*    g_sys    = nullptr;
static FICL_VM*        g_vm     = nullptr;
static MailboxesManager* g_mgr  = nullptr;
static int             g_curObj = 0;

// ---------------------------------------------------------------------------
// Bridge words (C functions registered as named Forth words)

static void ficl_read_mailbox(FICL_VM* pVM)
{
    // Stack: ( idx -- val )
    FICL_INT idx = POPINT();
    FICL_INT val = 0;
    if (g_mgr) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
        val = (FICL_INT)mb.ReadMailbox((int)idx).AsFloat();
    }
    PUSHINT(val);
}

static void ficl_write_mailbox(FICL_VM* pVM)
{
    // Stack: ( val idx -- )
    FICL_INT idx = POPINT();
    FICL_INT val = POPINT();
    if (g_mgr) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
        mb.WriteMailbox((int)idx, Scalar::FromFloat((float)val));
    }
}

// ---------------------------------------------------------------------------
// forth_engine namespace — public plug interface

namespace forth_engine {

void Init(MailboxesManager& mgr)
{
    g_mgr    = &mgr;
    g_curObj = 0;

    // Create a system with enough dictionary space for WF constants + scripts.
    // 8192 cells ≈ 64 KB on 64-bit, well above minimum; WF uses ~200 constants.
    g_sys = ficlInitSystem(8192);
    if (!g_sys) {
        fprintf(stderr, "ficl: ficlInitSystem failed\n");
        return;
    }

    g_vm = ficlNewVM(g_sys);
    if (!g_vm) {
        fprintf(stderr, "ficl: ficlNewVM failed\n");
        return;
    }

    // Register WF mailbox bridge words directly by name.
    ficlBuild(g_sys, "read-mailbox",  ficl_read_mailbox,  FW_DEFAULT);
    ficlBuild(g_sys, "write-mailbox", ficl_write_mailbox, FW_DEFAULT);
}

void Shutdown()
{
    if (g_sys) {
        ficlTermSystem(g_sys);
        g_sys = nullptr;
        g_vm  = nullptr;
    }
    g_mgr    = nullptr;
    g_curObj = 0;
}

void AddConstantArray(IntArrayEntry* entryList)
{
    if (!g_vm) return;
    // Eval each constant as: `N constant NAME`
    char buf[128];
    for (IntArrayEntry* p = entryList; p->name; p++) {
        snprintf(buf, sizeof(buf), "%d constant %s", p->value, p->name);
        int r = ficlEvaluate(g_vm, buf);
        if (r == VM_ERREXIT)
            fprintf(stderr, "ficl: failed to define constant %s\n", p->name);
    }
}

void DeleteConstantArray(IntArrayEntry* /*entryList*/)
{
    // ficl dictionary is append-only — constants persist for engine lifetime.
}

float RunScript(const char* src, int objectIndex)
{
    if (!g_vm || !src || !*src) return 0.0f;

    g_curObj = objectIndex;

    // ficlEvaluate manages SOURCE-ID and handles the `\ wf` opener line
    // as a standard Forth line comment — it is consumed without effect.
    int r = ficlEvaluate(g_vm, const_cast<char*>(src));
    if (r == VM_ERREXIT || r == VM_ABORT || r == VM_ABORTQ) {
        fprintf(stderr, "ficl error %d: %.120s\n", r, src);
        return 0.0f;
    }

    // Return TOS as float if stack is non-empty.
    if (stackDepth(g_vm->pStack) > 0) {
        FICL_INT top = stackPopINT(g_vm->pStack);
        return (float)top;
    }
    return 0.0f;
}

} // namespace forth_engine

#endif // WF_FORTH_ENGINE_FICL
