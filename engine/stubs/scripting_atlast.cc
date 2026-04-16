// scripting_atlast.cc — Atlast Forth backend for forth_engine namespace.
//
// Compiled in when WF_FORTH_ENGINE_ATLAST is defined (via build_game.sh).
// Sigil: `\` — handled by ScriptRouter before dispatch here.
//
// Cell type: atl_int = int64_t. Mailbox values are cast to int64_t;
// float mailbox values on PC dev are truncated. Correct on real fixed-point
// target where mailbox values are integers.
//
// Bridge words are registered via atl_primdef (struct primfcn table).
// The atldef.h internal header (from atlast-64/) is included for access
// to the exported stack pointer and S0/Pop/Push macros. Atlast.c is
// compiled with -DEXPORT so these symbols are externally visible.
//
// Note: Atlast uses a single-instance global interpreter — only one
// interpreter can exist per process. This matches WF's one-engine-per-build
// contract.

#ifdef WF_FORTH_ENGINE_ATLAST

#include "scripting_forth.hp"
#include <cstdint>

// We include neither atlast.h nor atldef.h in this C++ TU.
//
// * atldef.h #defines heap, stack, ip, stk, etc. as macros that corrupt
//   C++ stdlib headers (std::fpos, etc.).
//
// * atlast.h declares atl_eval() with K&R empty parens which C++ treats as
//   taking zero arguments — conflicting with any explicit parameter declaration.
//
// Instead, everything needed is declared directly below.
//
// atlast.c must be compiled with -DEXPORT to use atl__* external names.

typedef int64_t  atl_int;    // matches atlast.h typedef (int64_t)
#define ATL_SNORM 0           // normal evaluation status (matches atlast.h)

typedef void (*wf_codeptr)();
extern "C" {
    void      atl_init(void);
    int       atl_eval(char* s);         // explicit param avoids K&R conflict
    void      atl_primdef(struct primfcn* pt);
    extern atl_int  atl_redef;           // allow silent word redefinition
    // EXPORT-mangled stack pointer and stack base
    extern atl_int* atl__sp;             // stk  — points one past TOS
    extern atl_int* atl__sb;             // stackbot — stack base

    struct primfcn { char* pname; wf_codeptr pcode; };
}
// Stack access macros using the mangled names only.
#define S0   (atl__sp[-1])   // TOS (read or assign)
#define Pop  (atl__sp--)     // discard TOS
#define Push (*atl__sp++)    // assign then advance: Push = val

#include <scripting/scriptinterpreter.hp>
#include <mailbox/mailbox.hp>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <cstring>

// ---------------------------------------------------------------------------
// Module state

static MailboxesManager* g_mgr   = nullptr;
static int               g_curObj = 0;

// ---------------------------------------------------------------------------
// Bridge primitives (called via atl_primdef table)

// read-mailbox ( idx -- val )
static void atlast_read_mailbox()
{
    atl_int idx = S0; Pop;
    atl_int val = 0;
    if (g_mgr) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
        val = (atl_int)mb.ReadMailbox((int)idx).AsFloat();
    }
    Push = val;
}

// write-mailbox ( val idx -- )
static void atlast_write_mailbox()
{
    atl_int idx = S0; Pop;
    atl_int val = S0; Pop;
    if (g_mgr) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
        mb.WriteMailbox((int)idx, Scalar::FromFloat((float)val));
    }
}

// Null-terminated primitive table consumed by atl_primdef.
// Names are upper-case by Atlast convention; scripts use lower-case
// because Atlast is case-insensitive on modern 64-bit builds.
static struct primfcn wf_atlast_prims[] = {
    { const_cast<char*>("0READ-MAILBOX"),  atlast_read_mailbox  },
    { const_cast<char*>("0WRITE-MAILBOX"), atlast_write_mailbox },
    { nullptr, nullptr }
};

// ---------------------------------------------------------------------------
// forth_engine namespace — public plug interface

namespace forth_engine {

void Init(MailboxesManager& mgr)
{
    g_mgr    = &mgr;
    g_curObj = 0;

    atl_init();

    // Allow silent redefinition of words (constants re-evalued per level).
    atl_redef = 1;

    // Register WF bridge primitives.
    atl_primdef(wf_atlast_prims);

    // Alias lower-case names (Atlast primitive names must start with a count
    // byte = 0 meaning "not immediate" in the Fourmilab format, but
    // atl_primdef accepts plain C strings). Test with lowercase eval:
    atl_eval(const_cast<char*>(": read-mailbox  READ-MAILBOX ;"));
    atl_eval(const_cast<char*>(": write-mailbox WRITE-MAILBOX ;"));
}

void Shutdown()
{
    // Atlast has no public cleanup function; globals are process-scoped.
    g_mgr    = nullptr;
    g_curObj = 0;
}

void AddConstantArray(IntArrayEntry* entryList)
{
    // Eval each constant as `N constant NAME`. atl_eval takes mutable char*.
    char buf[256];
    for (IntArrayEntry* p = entryList; p->name; p++) {
        snprintf(buf, sizeof(buf), "%d constant %s", p->value, p->name);
        int r = atl_eval(buf);
        if (r != ATL_SNORM)
            fprintf(stderr, "atlast: failed to define constant %s: %d\n", p->name, r);
    }
}

void DeleteConstantArray(IntArrayEntry* /*entryList*/)
{
    // Atlast dictionary is append-only; use atl_redef=1 so re-definitions
    // are silently accepted without error. Nothing to delete here.
}

float RunScript(const char* src, int objectIndex)
{
    if (!src || !*src) return 0.0f;

    g_curObj = objectIndex;

    // Skip the `\ wf` sigil line — Atlast does not support the standard
    // Forth `\` line-comment word by default (it uses ( ) comments and
    // "  " as a line comment variant). Stripping the line manually avoids
    // an "undefined word" error for `\`.
    while (*src && *src != '\n') ++src;
    if (*src == '\n') ++src;

    // atl_eval requires a mutable buffer.
    std::string buf(src);
    int r = atl_eval(buf.data());
    if (r != ATL_SNORM) {
        fprintf(stderr, "atlast error %d: %.120s\n", r, src);
        return 0.0f;
    }

    // Return TOS if stack is non-empty. Stack depth check via atl__sp vs atl__sb.
    if (atl__sp > atl__sb) {
        atl_int top = S0;
        Pop;
        return (float)top;
    }
    return 0.0f;
}

} // namespace forth_engine

#endif // WF_FORTH_ENGINE_ATLAST
