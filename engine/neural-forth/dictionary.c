/* dictionary.c — neural-forth dispatch table and word bootstrap.
 *
 * All NF Forth words share syscall 200 (ZF_SYSCALL_USER + 72).
 * The Forth side pushes a word-ID then calls `nf` (`: nf 200 sys ;`).
 * nf_dispatch() receives the popped word-ID and routes here.
 */
#include "neural_forth.h"
#include "dictionary.h"
#include "tensor.h"
#include "autograd.h"
#include "fuzzy.h"
#include "nn.h"
#include "slot.h"

#include <zforth.h>
#include <stdio.h>

/* ── NF syscall ID ─────────────────────────────────────────────────────────
 * 200 = ZF_SYSCALL_USER (128) + 72.
 * Chosen to leave custom IDs 3-71 free for WF primitives
 * (read-actor-mailbox, spawn-template, etc. — see TODO.md). */
#define NF_SYSCALL_ID 200

/* ── Handler type ────────────────────────────────────────────────────────── */
typedef void (*nf_handler)(zf_ctx *);

/* ── Stage 1: diagnostics ────────────────────────────────────────────────── */
static void h_ping(zf_ctx *ctx)
{
    (void)ctx;
    fprintf(stderr, "NF-PING ok\n");
}

/* ── Dispatch table ───────────────────────────────────────────────────────
 * Entry order MUST match the NF_WORD_* constants in dictionary.h. */
static const nf_handler nf_table[NF_WORD_COUNT] = {
    /* 0  */ h_ping,
    /* 1  */ nf_tensor_new,
    /* 2  */ nf_tensor_free,
    /* 3  */ nf_t_get,
    /* 4  */ nf_t_set,
    /* 5  */ nf_matmul,
    /* 6  */ nf_t_add,
    /* 7  */ nf_t_mul,
    /* 8  */ nf_sigmoid,
    /* 9  */ nf_relu,
    /* 10 */ nf_tanh_w,
    /* 11 */ nf_softmax,
    /* 12 */ nf_with_tape,
    /* 13 */ nf_end_tape,
    /* 14 */ nf_backward,
    /* 15 */ nf_zero_grad,
    /* 16 */ nf_linear,
    /* 17 */ nf_forward,
    /* 18 */ nf_loss_ce,
    /* 19 */ nf_loss_mse,
    /* 20 */ nf_adam_new,
    /* 21 */ nf_adam_step,
    /* 22 */ nf_triangular,
    /* 23 */ nf_trapezoidal,
    /* 24 */ nf_gaussian,
    /* 25 */ nf_mu_get,
    /* 26 */ nf_defuzz_cog,
    /* 27 */ nf_fand,
    /* 28 */ nf_for_logic,
    /* 29 */ nf_fnot,
    /* 30 */ nf_fimplies,
    /* 31 */ nf_t_norm_set,
    /* 32 */ nf_s_norm_set,
    /* 33 */ nf_fuzzy_reset,
    /* 34 */ nf_fuzzy_add,
    /* 35 */ nf_slot_declare,
    /* 36 */ nf_slot_run,
    /* 37 */ nf_slot_params,
    /* 38 */ nf_slot_temp,
};

/* ── Public API ─────────────────────────────────────────────────────────── */

void nf_dispatch(zf_ctx *ctx, int word_id)
{
    if (word_id < 0 || word_id >= NF_WORD_COUNT) {
        fprintf(stderr, "neural-forth: unknown word id %d\n", word_id);
        return;
    }
    nf_table[word_id](ctx);
}

/* Define all NF words in ctx.  The base word `nf` (syscall gate) is defined
 * first; all named words are thin wrappers that push their ID then call `nf`.
 *
 * Format:  : <forth-name>  <word-id> nf ;
 *
 * Numbers and `:` / `;` are zForth bootstrap primitives — no kCoreBootstrap
 * is required for these definitions.
 */
void nf_init(zf_ctx *ctx)
{
#define DEFWORD(name, id) \
    do { \
        char _buf[64]; \
        int _n = snprintf(_buf, sizeof(_buf), ": %s %d nf ;", (name), (id)); \
        if (_n < 0 || _n >= (int)sizeof(_buf)) { \
            fprintf(stderr, "neural-forth: word name too long: %s\n", (name)); \
            return; \
        } \
        zf_result _r = zf_eval(ctx, _buf); \
        if (_r != ZF_OK) \
            fprintf(stderr, "neural-forth: failed to define %s (err %d)\n", (name), _r); \
    } while (0)

    /* Gate word — all NF syscalls go through this single entry point.
     * ZF_SYSCALL_USER = 128; NF_SYSCALL_ID = 200; 200 - 128 = 72 = custom. */
    zf_result r = zf_eval(ctx, ": nf 200 sys ;");
    if (r != ZF_OK) {
        fprintf(stderr, "neural-forth: failed to define gate word `nf` (err %d)\n", r);
        return;
    }

    /* Diagnostics */
    DEFWORD("nf-ping",        NF_WORD_PING);

    /* Tensors */
    DEFWORD("tensor-new",     NF_WORD_TENSOR_NEW);
    DEFWORD("tensor-free",    NF_WORD_TENSOR_FREE);
    DEFWORD("t@",             NF_WORD_T_GET);
    DEFWORD("t!",             NF_WORD_T_SET);
    DEFWORD("matmul",         NF_WORD_MATMUL);
    DEFWORD("t-add",          NF_WORD_T_ADD);
    DEFWORD("t-mul",          NF_WORD_T_MUL);
    DEFWORD("sigmoid",        NF_WORD_SIGMOID);
    DEFWORD("relu",           NF_WORD_RELU);
    DEFWORD("tanh-w",         NF_WORD_TANH_W);
    DEFWORD("softmax",        NF_WORD_SOFTMAX);

    /* Autograd */
    DEFWORD("with-tape",      NF_WORD_WITH_TAPE);
    DEFWORD("end-tape",       NF_WORD_END_TAPE);
    DEFWORD("backward",       NF_WORD_BACKWARD);
    DEFWORD("zero-grad",      NF_WORD_ZERO_GRAD);

    /* NN primitives */
    DEFWORD("linear",         NF_WORD_LINEAR);
    DEFWORD("forward",        NF_WORD_FORWARD);
    DEFWORD("loss-ce",        NF_WORD_LOSS_CE);
    DEFWORD("loss-mse",       NF_WORD_LOSS_MSE);
    DEFWORD("adam-new",       NF_WORD_ADAM_NEW);
    DEFWORD("adam-step",      NF_WORD_ADAM_STEP);

    /* Fuzzy */
    DEFWORD("triangular",     NF_WORD_TRIANGULAR);
    DEFWORD("trapezoidal",    NF_WORD_TRAPEZOIDAL);
    DEFWORD("gaussian",       NF_WORD_GAUSSIAN);
    DEFWORD("mu@",            NF_WORD_MU_GET);
    DEFWORD("defuzz-cog",     NF_WORD_DEFUZZ_COG);
    DEFWORD("fand",           NF_WORD_FAND);
    DEFWORD("for-logic",      NF_WORD_FOR_LOGIC);
    DEFWORD("fnot",           NF_WORD_FNOT);
    DEFWORD("fimplies",       NF_WORD_FIMPLIES);
    DEFWORD("t-norm!",        NF_WORD_T_NORM_SET);
    DEFWORD("s-norm!",        NF_WORD_S_NORM_SET);
    DEFWORD("fuzzy-reset",    NF_WORD_FUZZY_RESET);
    DEFWORD("fuzzy-add",      NF_WORD_FUZZY_ADD);

    /* ∂4 slots */
    DEFWORD("slot-declare",   NF_WORD_SLOT_DECLARE);
    DEFWORD("slot-run",       NF_WORD_SLOT_RUN);
    DEFWORD(".params",        NF_WORD_SLOT_PARAMS);
    DEFWORD("temperature!",   NF_WORD_SLOT_TEMP);
    /* SLOT: and PERMUTE-SLOT: are parsing words defined in slot.c via zf_eval */
    nf_slot_register_parsing_words(ctx);

#undef DEFWORD
}
