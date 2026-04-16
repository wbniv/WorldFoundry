// scripting_embed.cc — embed eForth backend for forth_engine namespace.
//
// Compiled in when WF_FORTH_ENGINE_EMBED is defined (via build_game.sh).
// Sigil: `\` — handled by ScriptRouter before dispatch here.
//
// Cell type: uint16_t (embed is a 16-bit eForth VM). On the real fixed-point
// target this is correct and natural; on PC dev, float mailbox values are
// truncated to 16-bit integer range (±32767) which is a documented divergence.
//
// Bridge mechanism: embed exposes a single `vm` opcode that invokes
// `h->o.callback`. WF defines a dispatch convention: the top-of-stack value
// when `vm` executes is a dispatch index:
//   0 = read-mailbox  : ( idx -- val )  reads from Mailboxes
//   1 = write-mailbox : ( val idx -- )  writes to Mailboxes
//
// At init the bootstrap Forth code:
//   : read-mailbox  ( idx -- val ) 0 vm ;
//   : write-mailbox ( val idx -- ) 1 vm ;
// is evaluated into the dictionary once.
//
// Constants are eval'd at AddConstantArray time:
//   42 constant FOO
//
// Note: embed uses `embed_default_block` (the built-in eForth ROM image)
// which includes `constant`, `variable`, `if`, `else`, `then`, `do`, `loop`,
// etc. The full eForth standard word set is available to scripts.

#ifdef WF_FORTH_ENGINE_EMBED

#include "scripting_forth.hp"

extern "C" {
#include <embed.h>
}

#include <scripting/scriptinterpreter.hp>
#include <mailbox/mailbox.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

// ---------------------------------------------------------------------------
// Module state
//
// embed_t contains a void* to the core memory; we provide a static array
// sized EMBED_CORE_SIZE cells (32768 × 2 = 64 KB). The embed_t struct itself
// is tiny (options + void*); the bulk is in the cell array.

static cell_t            g_embed_mem[EMBED_CORE_SIZE];
static embed_t           g_embed     = { .m = g_embed_mem };
static MailboxesManager* g_mgr       = nullptr;
static int               g_curObj    = 0;

// ---------------------------------------------------------------------------
// embed callback — dispatched via the `vm` Forth word

static int wf_embed_callback(embed_t* h, void* /*param*/)
{
    // Convention: TOS is the dispatch index when `vm` is called.
    // embed_pop reads TOS; embed_push pushes a new TOS.
    cell_t dispatch = 0;
    if (embed_pop(h, &dispatch) < 0) return -1;

    if (dispatch == 0) {
        // read-mailbox ( idx -- val )
        cell_t idx = 0;
        if (embed_pop(h, &idx) < 0) return -1;
        cell_t val = 0;
        if (g_mgr) {
            Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
            val = (cell_t)(int16_t)mb.ReadMailbox((int)idx).AsFloat();
        }
        embed_push(h, val);
    } else if (dispatch == 1) {
        // write-mailbox ( val idx -- )
        cell_t idx = 0;
        if (embed_pop(h, &idx) < 0) return -1;
        cell_t val = 0;
        if (embed_pop(h, &val) < 0) return -1;
        if (g_mgr) {
            Mailboxes& mb = g_mgr->LookupMailboxes(g_curObj);
            mb.WriteMailbox((int)idx, Scalar::FromFloat((float)(int16_t)val));
        }
    } else {
        fprintf(stderr, "embed: unknown vm dispatch id %d\n", (int)dispatch);
        return -1;
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

    // Load the default eForth ROM image into the core memory.
    if (embed_load_buffer(&g_embed, embed_default_block, embed_default_block_size) < 0) {
        fprintf(stderr, "embed: failed to load default image\n");
        return;
    }

    // Configure options: suppress terminal I/O (scripts run headless),
    // install the WF bridge callback.
    embed_opt_t opt = embed_opt_default();
    opt.put      = embed_nputc_cb;      // discard output
    opt.get      = embed_ngetc_cb;      // no input (scripts supplied via eval)
    opt.save     = nullptr;             // no persistent image save
    opt.callback = wf_embed_callback;
    opt.param    = nullptr;
    opt.options  = EMBED_VM_QUITE_ON;   // suppress "ok" prompt
    embed_opt_set(&g_embed, &opt);

    // Define the WF bridge words in the dictionary.
    // `vm` is the embed eForth word that triggers the callback.
    int r = embed_eval(&g_embed,
        ": read-mailbox  ( idx -- val ) 0 vm ; "
        ": write-mailbox ( val idx -- ) 1 vm ; ");
    if (r < 0)
        fprintf(stderr, "embed: failed to define bridge words: %d\n", r);
}

void Shutdown()
{
    // embed_t is stack-allocated; no heap to free.
    g_mgr    = nullptr;
    g_curObj = 0;
}

void AddConstantArray(IntArrayEntry* entryList)
{
    // Eval each constant. eForth provides `constant` as a built-in word.
    char buf[256];
    for (IntArrayEntry* p = entryList; p->name; p++) {
        snprintf(buf, sizeof(buf), "%d constant %s", p->value, p->name);
        int r = embed_eval(&g_embed, buf);
        if (r < 0)
            fprintf(stderr, "embed: failed to define constant %s: %d\n", p->name, r);
    }
}

void DeleteConstantArray(IntArrayEntry* /*entryList*/)
{
    // embed dictionary is append-only; constants persist.
}

float RunScript(const char* src, int objectIndex)
{
    if (!src || !*src) return 0.0f;

    g_curObj = objectIndex;

    // Skip the `\ wf` sigil line. embed eForth's `\` word is present
    // in eForth-83 images but may not be in all embed builds; stripping
    // manually is safe and portable across embed image versions.
    while (*src && *src != '\n') ++src;
    if (*src == '\n') ++src;
    if (!*src) return 0.0f;

    int r = embed_eval(&g_embed, src);
    if (r < 0) {
        fprintf(stderr, "embed error %d: %.120s\n", r, src);
        return 0.0f;
    }

    // Return TOS as float if stack is non-empty.
    if (embed_depth(&g_embed) > 0) {
        cell_t top = 0;
        if (embed_pop(&g_embed, &top) == 0)
            return (float)(int16_t)top;  // sign-extend 16-bit cell
    }
    return 0.0f;
}

} // namespace forth_engine

#endif // WF_FORTH_ENGINE_EMBED
