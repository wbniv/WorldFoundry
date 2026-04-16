// scripting_zforth.cc — zForth backend for forth_engine namespace.
//
// Compiled in when WF_FORTH_ENGINE_ZFORTH is defined (via build_game.sh).
// Sigil: `\` — handled by ScriptRouter before dispatch here; zForth also
// treats `\` as a standard line-comment so the `\ wf` opener is a no-op.
//
// Cell type: float (see wf_zfconf.h). Mailbox indices and values flow
// through as floats on PC dev; on the real fixed-point target integer
// values are exact in float representation for typical mailbox indices.
//
// Bridge words (eval'd at Init):
//   : read-mailbox  128 sys ;   \ ZF_SYSCALL_USER+0: ( idx -- val )
//   : write-mailbox 129 sys ;   \ ZF_SYSCALL_USER+1: ( val idx -- )
//
// Control flow (zForth uses `fi` not `then`):
//   if ... fi        ( flag -- )
//   if ... else ... fi
//   begin ... until  ( flag -- )
//   begin ... again
//   limit start do ... loop
//
// Constants are loaded at AddConstantArray time:
//   3024 constant INDEXOF_INPUT
//   1009 constant INDEXOF_HARDWARE_JOYSTICK1_RAW
//   ...

#ifdef WF_FORTH_ENGINE_ZFORTH

#include "scripting_forth.hp"

extern "C" {
#include <zforth.h>
}

#include <scripting/scriptinterpreter.hp>
#include <mailbox/mailbox.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdarg>
#include <string>

// ---------------------------------------------------------------------------
// Module state

static zf_ctx              g_ctx;
static MailboxesManager*   g_mgr     = nullptr;
static int                 g_curObj  = 0;

// ---------------------------------------------------------------------------
// Required zForth host callbacks

// System call dispatcher.
// Standard syscalls (EMIT, PRINT, TELL) route to stderr.
// WF custom syscalls (ZF_SYSCALL_USER+0/+1) implement the mailbox bridge.
zf_input_state zf_host_sys(zf_ctx* ctx, zf_syscall_id id, const char* /*last_word*/)
{
    switch (id) {
        case ZF_SYSCALL_EMIT: {
            char c = (char)zf_pop(ctx);
            fputc(c, stderr);
            break;
        }
        case ZF_SYSCALL_PRINT: {
            zf_cell v = zf_pop(ctx);
            fprintf(stderr, ZF_CELL_FMT " ", v);
            break;
        }
        case ZF_SYSCALL_TELL: {
            // TELL: ( addr len -- ) print string from dict
            zf_cell len  = zf_pop(ctx);
            zf_cell addr = zf_pop(ctx);
            // Access dict memory via dump to avoid internal struct coupling.
            // For WF builds this is only used by Forth's own I/O words, not
            // by game scripts, so a simple fprintf is fine.
            (void)len; (void)addr;
            break;
        }
        default: {
            // Custom WF syscalls
            int custom = (int)id - (int)ZF_SYSCALL_USER;
            if (custom == 0) {
                // read-mailbox ( idx -- val )
                int idx = (int)zf_pop(ctx);
                if (g_mgr) {
                    Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
                    float v = mb.ReadMailbox(idx).AsFloat();
                    zf_push(ctx, (zf_cell)v);
                } else {
                    zf_push(ctx, (zf_cell)0.0f);
                }
            } else if (custom == 1) {
                // write-mailbox ( val idx -- )
                int   idx = (int)zf_pop(ctx);
                float val = (float)zf_pop(ctx);
                if (g_mgr) {
                    Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
                    mb.WriteMailbox(idx, Scalar::FromFloat(val));
                }
            } else {
                fprintf(stderr, "zforth: unknown sys id %d\n", (int)id);
            }
            break;
        }
    }
    return ZF_INPUT_INTERPRET;
}

// Trace callback — only called when ZF_ENABLE_TRACE=1, which we set to 0.
void zf_host_trace(zf_ctx* /*ctx*/, const char* fmt, va_list va)
{
    vfprintf(stderr, fmt, va);
}

// Number parser — called when an unknown word is encountered.
// Parses integers (decimal, hex with 0x prefix) and floats.
zf_cell zf_host_parse_num(zf_ctx* ctx, const char* buf)
{
    char* end = nullptr;

    // Try hex: 0x...
    if (buf[0] == '0' && (buf[1] == 'x' || buf[1] == 'X')) {
        long v = strtol(buf, &end, 16);
        if (end && *end == '\0') return (zf_cell)v;
    }

    // Try float (handles integer literals too)
    float v = strtof(buf, &end);
    if (end && *end == '\0') return (zf_cell)v;

    // Not a number — abort
    zf_abort(ctx, ZF_ABORT_NOT_A_WORD);
    return (zf_cell)0;
}

// ---------------------------------------------------------------------------
// forth_engine namespace — public plug interface

namespace forth_engine {

// Subset of zForth's core.zf needed to make `constant` work.
// zForth's bootstrap provides only primitive opcodes (>r, r>, :, ;, ,,, !!,
// _literal→literal, etc.) but not the higher-level words `!`, `@`,
// `postpone`, or `constant`. We eval just the minimum needed.
//
// Note: `constant` in zForth core.zf is defined as:
//   : constant >r : r> postpone literal postpone ; ;
// which requires `!` (for `postpone`'s body) and `postpone` itself.
// We also load `@` and `,` since scripts may use them.
static const char* kCoreBootstrap =
    // Dictionary shortcuts (default cell-width wrappers around sized ops)
    ": !    0 !! ; "
    ": @    0 @@ ; "
    ": ,    0 ,, ; "
    // Max-width cell stores for jump targets — must be fixed-width so the
    // compiler can back-patch branch addresses after emitting a placeholder.
    // 64 is ZF_MEM_SIZE_VAR_MAX; see zforth.c.
    ": !j  64 !! ; "
    ": ,j  64 ,, ; "
    // Interpreter state control
    ": [ 0 compiling ! ; immediate "
    ": ] 1 compiling ! ; "
    // postpone: sets _postpone flag so next word is compiled not executed
    ": postpone 1 _postpone ! ; immediate "
    // constant: canonical zForth definition — stores literal in new word
    ": constant >r : r> postpone literal postpone ; ; "
    // Derived operators useful in game scripts
    ": 1+ 1 + ; "
    ": 1- 1 - ; "
    ": over 1 pick ; "
    ": not 0 = ; "
    ": <  - <0 ; "
    ": >  swap < ; "
    ": <= over over >r >r < r> r> = + ; "
    ": >= swap <= ; "
    ": <> = not ; "
    ": 0<> 0 <> ; "
    // Control flow — if/else/fi, begin/until/again
    // `if` emits a jmp0 with a placeholder target; `fi` back-patches it.
    // `else` emits an unconditional jmp past the else-body, back-patches
    // the if's jmp0 to here, then leaves the else's jmp for `fi` to patch.
    ": if     ' jmp0 , here 0 ,j ; immediate "
    ": else   ' jmp  , here 0 ,j swap here swap !j ; immediate "
    ": fi     here swap !j ; immediate "
    ": begin  here ; immediate "
    ": again  ' jmp  , , ; immediate "
    ": until  ' jmp0 , , ; immediate "
    // Counted loop: `limit start do ... loop`
    // `i` pushes the current loop index (TOR[0]); `j` the outer index (TOR[2]).
    // loop+ increments by n; loop by 1.  All immediate — compiled, not eval'd.
    ": i     ' lit , 0 , ' pickr , ; immediate "
    ": j     ' lit , 2 , ' pickr , ; immediate "
    ": do    ' swap , ' >r , ' >r , here ; immediate "
    ": loop+ ' r> , ' + , ' dup , ' >r , ' lit , 1 , ' pickr , ' >= , "
             "' jmp0 , , ' r> , ' drop , ' r> , ' drop , ; immediate "
    ": loop  ' lit , 1 , postpone loop+ ; immediate "
    ;

void Init(MailboxesManager& mgr)
{
    g_mgr    = &mgr;
    g_curObj = 0;

    zf_init(&g_ctx, 0 /* no trace */);
    zf_bootstrap(&g_ctx);

    // Load the core bootstrap words (constant, !, @, etc.).
    zf_result r = zf_eval(&g_ctx, kCoreBootstrap);
    if (r != ZF_OK)
        fprintf(stderr, "zforth: core bootstrap failed: %d\n", r);

    // Define the WF mailbox bridge words.
    // ZF_SYSCALL_USER = 128; sys pops its argument directly as syscall id.
    r = zf_eval(&g_ctx, ": read-mailbox  128 sys ;");
    if (r != ZF_OK)
        fprintf(stderr, "zforth: init failed (read-mailbox): %d\n", r);
    r = zf_eval(&g_ctx, ": write-mailbox 129 sys ;");
    if (r != ZF_OK)
        fprintf(stderr, "zforth: init failed (write-mailbox): %d\n", r);
}

void Shutdown()
{
    // zForth state is a plain struct — no heap to free.
    g_mgr    = nullptr;
    g_curObj = 0;
}

void AddConstantArray(IntArrayEntry* entryList)
{
    // Eval each constant into the dictionary as: `N constant NAME`
    char buf[128];
    for (IntArrayEntry* p = entryList; p->name; p++) {
        snprintf(buf, sizeof(buf), "%d constant %s", p->value, p->name);
        zf_result r = zf_eval(&g_ctx, buf);
        if (r != ZF_OK)
            fprintf(stderr, "zforth: failed to define constant %s: %d\n", p->name, r);
    }
}

void DeleteConstantArray(IntArrayEntry* /*entryList*/)
{
    // zForth dictionaries are append-only — constants cannot be removed.
    // This is a no-op; constants persist for the lifetime of the engine.
}

float RunScript(const char* src, int objectIndex)
{
    if (!src || !*src) return 0.0f;

    g_curObj = objectIndex;

    // zForth's `\` word reads to end of line as a comment, so we can pass
    // the script verbatim — the `\ wf` opener line is silently consumed.
    zf_result r = zf_eval(&g_ctx, src);
    if (r != ZF_OK) {
        fprintf(stderr, "zforth error %d: %.120s\n", r, src);
        return 0.0f;
    }

    // Return TOS as float if stack is non-empty; 0 otherwise.
    // Use zf_uservar_get to check DSP without risking underrun.
    zf_cell dsp = 0;
    zf_uservar_get(&g_ctx, ZF_USERVAR_DSP, &dsp);
    if ((int)dsp > 0) {
        return (float)zf_pop(&g_ctx);
    }
    return 0.0f;
}

} // namespace forth_engine

#endif // WF_FORTH_ENGINE_ZFORTH
