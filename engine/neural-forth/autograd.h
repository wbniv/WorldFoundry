/* autograd.h — reverse-mode tape for neural-forth. */
#pragma once
#include <zforth.h>

/* ── Op codes (used by tensor.c to record forward ops) ───────────────────── */

typedef enum {
    NF_OP_MATMUL = 0,
    NF_OP_T_ADD,
    NF_OP_T_MUL,
    NF_OP_SIGMOID,
    NF_OP_RELU,
    NF_OP_TANH_W,
    NF_OP_SOFTMAX,
    NF_OP_LOSS_MSE,  /* ( pred target -- loss )  grad only flows to pred */
    NF_OP_LOSS_CE,   /* ( pred target -- loss )  grad only flows to pred */
    NF_OP_SLOT_RUN,  /* soft op mixture; backward delegated to slot.c */
    NF_OP_COUNT
} NfOp;

/* ── Tape recording API (called from tensor.c) ───────────────────────────── */

#ifdef __cplusplus
extern "C" {
#endif

int  nf_tape_is_active(void);
void nf_tape_record(NfOp op, int in1, int in2, int out);
void nf_tape_free_outputs(void); /* free all tensors recorded as tape outputs */

/* ── Forth word handlers ─────────────────────────────────────────────────── */

void nf_with_tape (zf_ctx *ctx); /* ( -- )      open tape scope           */
void nf_end_tape  (zf_ctx *ctx); /* ( -- )      close tape, clear entries  */
void nf_backward  (zf_ctx *ctx); /* ( loss -- ) backprop through tape      */
void nf_zero_grad (zf_ctx *ctx); /* ( -- )      zero all accumulated grads */

#ifdef __cplusplus
}
#endif
