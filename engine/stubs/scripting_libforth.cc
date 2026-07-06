// scripting_libforth.cc — libforth backend for forth_engine namespace.
//
// Compiled in when WF_FORTH_ENGINE_LIBFORTH is defined (via build_game.sh).
// Sigil: `\` — handled by ScriptRouter before dispatch here.
//
// Cell type: forth_cell_t = uintptr_t (native pointer width, 64-bit on
// x86-64). Mailbox values are cast to forth_cell_t; float values on PC dev
// are truncated to integer. Correct on the real fixed-point target.
//
// Bridge mechanism: C-global exchange buffer + Forth `!`/`@`.
//
// forth_t is fully opaque; the CALL callback receives only `forth_t *o` and
// cannot access stack internals (o->m, o->S) safely through the public API.
// Instead, two static C variables (wf_bridge_arg, wf_bridge_result) are used
// as the exchange buffer. The addresses are registered as Forth constants at
// init time; Forth scripts use `!` / `@` to store/fetch through them.
//
// Forth bridge words defined at init via forth_eval:
//
//   : read-mailbox  ( idx -- val )
//       wf-arg-a !          \ store idx into wf_bridge_arg
//       0 0 call drop drop  \ trigger read (call index 0), drop dummy+success
//       wf-ret-a @ ;        \ fetch result from wf_bridge_result
//
//   : write-mailbox ( val idx -- )
//       wf-arg-a !          \ store idx
//       wf-val-a !          \ store val
//       0 1 call drop drop ; \ trigger write (call index 1), drop dummy+success
//
// The CALL functions (index 0 = read, index 1 = write) only use the C globals
// and never touch the Forth stack through the API.  A dummy `0` is pushed
// before each `call` so CALL has a valid NOS to consume; it and the success
// code (0) are removed by `drop drop`.
//
// Constants are defined via forth_define_constant (one API call each).

#ifdef WF_FORTH_ENGINE_LIBFORTH

#include "scripting_forth.hp"

extern "C" {
#include <libforth.h>
}

#include <scripting/scriptinterpreter.hp>
#include <mailbox/mailbox.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>

// ---------------------------------------------------------------------------
// Module state

static forth_t*          g_forth  = nullptr;
static MailboxesManager* g_mgr    = nullptr;
static int               g_curObj = 0;

// Exchange buffer for Forth ↔ C bridge (read by CALL functions).
// Addresses are baked into Forth constants at init.
static forth_cell_t wf_bridge_arg = 0;  // mailbox index (for read) or idx (for write)
static forth_cell_t wf_bridge_val = 0;  // value (for write-mailbox)
static forth_cell_t wf_bridge_ret = 0;  // result (for read-mailbox)

// ---------------------------------------------------------------------------
// CALL bridge functions (index 0 = read-mailbox, index 1 = write-mailbox)
//
// These are invoked by the CALL instruction.  The Forth wrappers have already
// stored idx/val into wf_bridge_arg/wf_bridge_val via `!` before CALL fires.
// Neither function touches the Forth stack (forth_pop/push would corrupt state
// because CALL has already repositioned o->S).

static int wf_libforth_read(forth_t* /*o*/)
{
    if (g_mgr) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
        wf_bridge_ret = (forth_cell_t)(intptr_t)mb.ReadMailbox((int)wf_bridge_arg).AsFloat();
    } else {
        wf_bridge_ret = 0;
    }
    return 0;
}

static int wf_libforth_write(forth_t* /*o*/)
{
    if (g_mgr) {
        Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
        mb.WriteMailbox((int)wf_bridge_arg,
                        Scalar::FromFloat((float)(intptr_t)wf_bridge_val));
    }
    return 0;
}

// ---------------------------------------------------------------------------
// forth_engine namespace — public plug interface

namespace forth_engine {

void Init(MailboxesManager& mgr)
{
    g_mgr    = &mgr;
    g_curObj = 0;

    // Allocate the function list for CALL dispatch (2 functions).
    struct forth_functions* ff = forth_new_function_list(2);
    if (!ff) {
        fprintf(stderr, "libforth: forth_new_function_list failed\n");
        return;
    }
    ff->functions[0].function = wf_libforth_read;
    ff->functions[0].depth    = 0;
    ff->functions[1].function = wf_libforth_write;
    ff->functions[1].depth    = 0;

    // 32768 cells (256 KB) comfortably holds all INDEXOF_* constants + scripts.
    g_forth = forth_init(32768, stdin, stderr, ff);
    if (!g_forth) {
        fprintf(stderr, "libforth: forth_init failed\n");
        forth_delete_function_list(ff);
        return;
    }
    // ff is copied into forth_t at init; safe to release the list struct.
    forth_delete_function_list(ff);

    // Register C exchange-buffer addresses as Forth constants so that the
    // bridge words can use `!` and `@` to store/fetch through them.
    forth_define_constant(g_forth, "wf-arg-a", (forth_cell_t)(uintptr_t)&wf_bridge_arg);
    forth_define_constant(g_forth, "wf-val-a", (forth_cell_t)(uintptr_t)&wf_bridge_val);
    forth_define_constant(g_forth, "wf-ret-a", (forth_cell_t)(uintptr_t)&wf_bridge_ret);

    // Define the WF bridge words.
    // The `0 0 call drop drop` pattern:
    //   - first `0` is a dummy NOS so CALL has a valid cell to pop into TOP
    //   - second `0` is the call index
    //   - CALL pops call_index (TOS), moves dummy to TOP, calls fn, then
    //     pushes old TOP back and puts fn's return code as new TOP
    //   - `drop drop` removes dummy and success code
    int r;
    r = forth_eval(g_forth,
        ": read-mailbox  ( idx -- val ) "
        "  wf-arg-a !  "         // store idx
        "  0 0 call drop drop "  // trigger, clean up
        "  wf-ret-a @ ; ");
    if (r < 0) fprintf(stderr, "libforth: failed to define read-mailbox\n");
    r = forth_eval(g_forth,
        ": write-mailbox ( val idx -- ) "
        "  wf-arg-a !  "         // store idx
        "  wf-val-a !  "         // store val
        "  0 1 call drop drop ; ");  // trigger, clean up
    if (r < 0) fprintf(stderr, "libforth: failed to define write-mailbox\n");
}

void Shutdown()
{
    if (g_forth) {
        forth_free(g_forth);
        g_forth = nullptr;
    }
    g_mgr    = nullptr;
    g_curObj = 0;
}

void AddConstantArray(IntArrayEntry* entryList)
{
    if (!g_forth) return;
    for (IntArrayEntry* p = entryList; p->name; p++) {
        int r = forth_define_constant(g_forth, p->name, (forth_cell_t)p->value);
        if (r < 0)
            fprintf(stderr, "libforth: failed to define constant %s: %d\n", p->name, r);
    }
}

void DeleteConstantArray(IntArrayEntry* /*entryList*/)
{
    // libforth dictionary is append-only; constants persist.
}

float RunScript(const char* src, int objectIndex)
{
    if (!g_forth || !src || !*src) return 0.0f;

    g_curObj = objectIndex;

    // Skip the `\ wf` sigil line. libforth uses `\` for line comments but
    // the interpreter might not have it loaded depending on core state.
    // Stripping it manually is safe and avoids any potential parse error.
    while (*src && *src != '\n') ++src;
    if (*src == '\n') ++src;
    if (!*src) return 0.0f;

    int r = forth_eval(g_forth, src);
    if (r < 0) {
        fprintf(stderr, "libforth error %d: %.120s\n", r, src);
        return 0.0f;
    }

    // Return TOS as float if stack is non-empty.
    forth_cell_t depth = forth_stack_position(g_forth);
    if (depth > 0) {
        forth_cell_t top = forth_pop(g_forth);
        return (float)(intptr_t)top;
    }
    return 0.0f;
}

} // namespace forth_engine

#endif // WF_FORTH_ENGINE_LIBFORTH
