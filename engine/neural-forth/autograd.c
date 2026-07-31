/* autograd.c — reverse-mode tape for neural-forth.
 *
 * The tape records (op, in1, in2, out) for each forward operation while
 * nf_tape_is_active() returns true.  nf_backward() walks the tape in reverse,
 * accumulating gradients into NfTensor::grad.
 *
 * Tensor lifetimes are always the caller's responsibility: the tape holds
 * handles only; it never allocates or frees tensors.  grad arrays are
 * allocated on first use by ensure_grad() and freed by nf_tensor_release().
 */
#include "autograd.h"
#include "tensor.h"
#include "slot.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── Tape ─────────────────────────────────────────────────────────────────── */

#define NF_MAX_TAPE 1024

typedef struct { NfOp op; int in1, in2, out; } NfTapeEntry;

static NfTapeEntry g_tape[NF_MAX_TAPE];
static int         g_tape_len    = 0;
static int         g_tape_active = 0;

int nf_tape_is_active(void) { return g_tape_active; }

void nf_tape_record(NfOp op, int in1, int in2, int out)
{
    if (!g_tape_active) return;
    if (g_tape_len >= NF_MAX_TAPE) {
        fprintf(stderr, "autograd: tape full (limit %d)\n", NF_MAX_TAPE);
        return;
    }
    g_tape[g_tape_len++] = (NfTapeEntry){ op, in1, in2, out };
}

void nf_with_tape(zf_ctx *ctx) { (void)ctx; g_tape_len = 0; g_tape_active = 1; }
void nf_end_tape (zf_ctx *ctx) { (void)ctx; g_tape_active = 0; g_tape_len = 0; }

/* ── Gradient helpers ─────────────────────────────────────────────────────── */

static void ensure_grad(int h)
{
    NfTensor *t = nf_tensor_get(h);
    if (!t || t->grad) return;
    t->grad = (float *)calloc((size_t)(t->rows * t->cols), sizeof(float));
}

/* grad_A (m×k) += grad_C (m×n) @ B^T (n→k) */
static void acc_BT(float *gA, int m, int k,
                   const float *gC, int n, const float *B)
{
    for (int i = 0; i < m; i++)
        for (int j = 0; j < k; j++) {
            float s = 0.0f;
            for (int p = 0; p < n; p++) s += gC[i*n+p] * B[j*n+p];
            gA[i*k+j] += s;
        }
}

/* grad_B (k×n) += A^T (k←m) @ grad_C (m×n) */
static void acc_AT(float *gB, int k, int n,
                   const float *A, int m, const float *gC)
{
    for (int i = 0; i < k; i++)
        for (int j = 0; j < n; j++) {
            float s = 0.0f;
            for (int p = 0; p < m; p++) s += A[p*k+i] * gC[p*n+j];
            gB[i*n+j] += s;
        }
}

/* ── Backward ─────────────────────────────────────────────────────────────── */

void nf_backward(zf_ctx *ctx)
{
    int loss_h = (int)zf_pop(ctx);
    NfTensor *loss = nf_tensor_get(loss_h);
    if (!loss) {
        fprintf(stderr, "backward: invalid loss handle %d\n", loss_h);
        return;
    }
    ensure_grad(loss_h);
    int n = loss->rows * loss->cols;
    for (int i = 0; i < n; i++) loss->grad[i] = 1.0f;

    for (int ti = g_tape_len - 1; ti >= 0; ti--) {
        NfTapeEntry *e = &g_tape[ti];
        NfTensor *out = nf_tensor_get(e->out);
        NfTensor *a   = nf_tensor_get(e->in1);
        NfTensor *b   = (e->in2 >= 0) ? nf_tensor_get(e->in2) : NULL;
        if (!out || !out->grad) continue;

        switch (e->op) {

        case NF_OP_MATMUL:
            /* C(m×n) = A(m×k) @ B(k×n)
             * grad_A += grad_C @ B^T,  grad_B += A^T @ grad_C */
            if (a) {
                ensure_grad(e->in1);
                acc_BT(a->grad, a->rows, a->cols,
                       out->grad, out->cols, b ? b->data : NULL);
            }
            if (b) {
                ensure_grad(e->in2);
                acc_AT(b->grad, b->rows, b->cols,
                       a ? a->data : NULL, a ? a->rows : 0, out->grad);
            }
            break;

        case NF_OP_T_ADD:
            n = out->rows * out->cols;
            if (a) { ensure_grad(e->in1); for (int i=0;i<n;i++) a->grad[i] += out->grad[i]; }
            if (b) { ensure_grad(e->in2); for (int i=0;i<n;i++) b->grad[i] += out->grad[i]; }
            break;

        case NF_OP_T_MUL:
            n = out->rows * out->cols;
            if (a && b) {
                ensure_grad(e->in1); ensure_grad(e->in2);
                for (int i = 0; i < n; i++) {
                    a->grad[i] += out->grad[i] * b->data[i];
                    b->grad[i] += out->grad[i] * a->data[i];
                }
            }
            break;

        case NF_OP_SIGMOID:
            /* grad_x += grad_y * y * (1 - y) */
            if (a) {
                ensure_grad(e->in1);
                n = out->rows * out->cols;
                for (int i = 0; i < n; i++)
                    a->grad[i] += out->grad[i] * out->data[i] * (1.0f - out->data[i]);
            }
            break;

        case NF_OP_RELU:
            /* grad_x += grad_y * (x > 0) */
            if (a) {
                ensure_grad(e->in1);
                n = out->rows * out->cols;
                for (int i = 0; i < n; i++)
                    a->grad[i] += out->grad[i] * (a->data[i] > 0.0f ? 1.0f : 0.0f);
            }
            break;

        case NF_OP_TANH_W:
            /* grad_x += grad_y * (1 - y^2) */
            if (a) {
                ensure_grad(e->in1);
                n = out->rows * out->cols;
                for (int i = 0; i < n; i++)
                    a->grad[i] += out->grad[i] * (1.0f - out->data[i] * out->data[i]);
            }
            break;

        case NF_OP_SOFTMAX: {
            /* grad_x[i] = y[i] * (grad_y[i] - dot(grad_y, y)) */
            if (a) {
                ensure_grad(e->in1);
                n = out->rows * out->cols;
                float dot = 0.0f;
                for (int i = 0; i < n; i++) dot += out->grad[i] * out->data[i];
                for (int i = 0; i < n; i++)
                    a->grad[i] += out->data[i] * (out->grad[i] - dot);
            }
            break;
        }

        case NF_OP_LOSS_MSE: {
            /* loss = sum((pred-target)^2)/n
             * grad_pred[i] += grad_loss * 2*(pred[i]-target[i])/n */
            if (a) {
                ensure_grad(e->in1);
                n = a->rows * a->cols;
                float inv_n = 1.0f / (float)n;
                for (int i = 0; i < n; i++) {
                    float diff = a->data[i] - (b ? b->data[i] : 0.0f);
                    a->grad[i] += out->grad[0] * 2.0f * diff * inv_n;
                }
            }
            break;
        }

        case NF_OP_LOSS_CE: {
            /* loss = -sum(target*log(pred+eps))/n
             * grad_pred[i] += grad_loss * -target[i]/(pred[i]+eps)/n */
            if (a) {
                ensure_grad(e->in1);
                n = a->rows * a->cols;
                float inv_n = 1.0f / (float)n;
                float eps = 1e-7f;
                for (int i = 0; i < n; i++) {
                    float t_val = b ? b->data[i] : 0.0f;
                    a->grad[i] += out->grad[0] * (-t_val / (a->data[i] + eps)) * inv_n;
                }
            }
            break;
        }

        case NF_OP_SLOT_RUN:
            /* in1=logits_h (tensor), in2=slot_id (int, not a tensor handle) */
            if (out && out->grad)
                nf_slot_backward(e->in2, e->in1, e->out);
            break;

        default:
            fprintf(stderr, "autograd: unknown op %d at tape[%d]\n", (int)e->op, ti);
            break;
        }
    }
}

void nf_tape_free_outputs(void)
{
    for (int i = 0; i < g_tape_len; i++)
        nf_tensor_release(g_tape[i].out);
}

void nf_zero_grad(zf_ctx *ctx)
{
    (void)ctx;
    for (int h = 0; h < NF_MAX_TENSORS; h++) {
        NfTensor *t = nf_tensor_get(h);
        if (t && t->grad)
            memset(t->grad, 0, (size_t)(t->rows * t->cols) * sizeof(float));
    }
}
