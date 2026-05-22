/* tensor.c — tiny CPU tensor library for neural-forth.
 *
 * All ops allocate a new output tensor and return its handle.
 * Callers are responsible for freeing intermediates (or delegating to the
 * autograd tape in Stage 3, which will track and free them).
 */
#include "tensor.h"
#include "autograd.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── Tensor pool ─────────────────────────────────────────────────────────── */

static NfTensor g_pool[NF_MAX_TENSORS];
static int       g_pool_init = 0;

static void pool_init(void)
{
    if (g_pool_init) return;
    memset(g_pool, 0, sizeof(g_pool));
    g_pool_init = 1;
}

NfTensor *nf_tensor_get(int handle)
{
    if (handle < 0 || handle >= NF_MAX_TENSORS) return NULL;
    if (!g_pool[handle].data) return NULL;
    return &g_pool[handle];
}

int nf_tensor_alloc(int rows, int cols)
{
    pool_init();
    if (rows <= 0 || cols <= 0) return NF_INVALID_TENSOR;
    for (int i = 0; i < NF_MAX_TENSORS; i++) {
        if (!g_pool[i].data) {
            g_pool[i].data = (float *)calloc((size_t)(rows * cols), sizeof(float));
            if (!g_pool[i].data) return NF_INVALID_TENSOR;
            g_pool[i].grad = NULL;
            g_pool[i].rows = rows;
            g_pool[i].cols = cols;
            return i;
        }
    }
    fprintf(stderr, "neural-forth: tensor pool exhausted (NF_MAX_TENSORS=%d)\n", NF_MAX_TENSORS);
    return NF_INVALID_TENSOR;
}

void nf_tensor_release(int handle)
{
    if (handle < 0 || handle >= NF_MAX_TENSORS) return;
    free(g_pool[handle].data);
    free(g_pool[handle].grad);
    memset(&g_pool[handle], 0, sizeof(NfTensor));
}

void nf_tensor_zero(int handle)
{
    NfTensor *t = nf_tensor_get(handle);
    if (!t) return;
    memset(t->data, 0, (size_t)(t->rows * t->cols) * sizeof(float));
}

void nf_tensor_copy(int dst, int src)
{
    NfTensor *d = nf_tensor_get(dst);
    NfTensor *s = nf_tensor_get(src);
    if (!d || !s || d->rows != s->rows || d->cols != s->cols) return;
    memcpy(d->data, s->data, (size_t)(d->rows * d->cols) * sizeof(float));
}

/* ── Internal helpers ────────────────────────────────────────────────────── */

static inline float *elem(NfTensor *t, int i, int j)
{
    return &t->data[i * t->cols + j];
}

/* ── Forth word handlers ──────────────────────────────────────────────────── */

/* ( rows cols -- t ) */
void nf_tensor_new(zf_ctx *ctx)
{
    int cols = (int)zf_pop(ctx);
    int rows = (int)zf_pop(ctx);
    int h = nf_tensor_alloc(rows, cols);
    if (h == NF_INVALID_TENSOR)
        fprintf(stderr, "tensor-new: allocation failed (%d x %d)\n", rows, cols);
    zf_push(ctx, (zf_cell)h);
}

/* ( t -- ) */
void nf_tensor_free(zf_ctx *ctx)
{
    int h = (int)zf_pop(ctx);
    nf_tensor_release(h);
}

/* ( i j t -- v ) */
void nf_t_get(zf_ctx *ctx)
{
    int h = (int)zf_pop(ctx);
    int j = (int)zf_pop(ctx);
    int i = (int)zf_pop(ctx);
    NfTensor *t = nf_tensor_get(h);
    if (!t || i < 0 || i >= t->rows || j < 0 || j >= t->cols) {
        fprintf(stderr, "t@: out of bounds (%d,%d) on handle %d\n", i, j, h);
        zf_push(ctx, (zf_cell)0.0f);
        return;
    }
    zf_push(ctx, (zf_cell)*elem(t, i, j));
}

/* ( v i j t -- ) */
void nf_t_set(zf_ctx *ctx)
{
    int h   = (int)zf_pop(ctx);
    int j   = (int)zf_pop(ctx);
    int i   = (int)zf_pop(ctx);
    float v = (float)zf_pop(ctx);
    NfTensor *t = nf_tensor_get(h);
    if (!t || i < 0 || i >= t->rows || j < 0 || j >= t->cols) {
        fprintf(stderr, "t!: out of bounds (%d,%d) on handle %d\n", i, j, h);
        return;
    }
    *elem(t, i, j) = v;
}

/* ( a b -- c )  C = A × B  (A is m×k, B is k×n, C is m×n) */
void nf_matmul(zf_ctx *ctx)
{
    int hb = (int)zf_pop(ctx);
    int ha = (int)zf_pop(ctx);
    NfTensor *a = nf_tensor_get(ha);
    NfTensor *b = nf_tensor_get(hb);
    if (!a || !b) {
        fprintf(stderr, "matmul: invalid handle\n");
        zf_push(ctx, (zf_cell)NF_INVALID_TENSOR);
        return;
    }
    if (a->cols != b->rows) {
        fprintf(stderr, "matmul: shape mismatch %dx%d × %dx%d\n",
                a->rows, a->cols, b->rows, b->cols);
        zf_push(ctx, (zf_cell)NF_INVALID_TENSOR);
        return;
    }
    int m = a->rows, k = a->cols, n = b->cols;
    int hc = nf_tensor_alloc(m, n);
    if (hc == NF_INVALID_TENSOR) {
        fprintf(stderr, "matmul: output allocation failed\n");
        zf_push(ctx, (zf_cell)NF_INVALID_TENSOR);
        return;
    }
    NfTensor *c = nf_tensor_get(hc);
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            float acc = 0.0f;
            for (int p = 0; p < k; p++)
                acc += *elem(a, i, p) * *elem(b, p, j);
            *elem(c, i, j) = acc;
        }
    }
    zf_push(ctx, (zf_cell)hc);
    if (nf_tape_is_active()) nf_tape_record(NF_OP_MATMUL, ha, hb, hc);
}

/* Element-wise binary op helper; allocates new output tensor */
static void ew_binop(zf_ctx *ctx, const char *name, NfOp tape_op,
                     float (*op)(float, float))
{
    int hb = (int)zf_pop(ctx);
    int ha = (int)zf_pop(ctx);
    NfTensor *a = nf_tensor_get(ha);
    NfTensor *b = nf_tensor_get(hb);
    if (!a || !b || a->rows != b->rows || a->cols != b->cols) {
        fprintf(stderr, "%s: shape mismatch or invalid handle\n", name);
        zf_push(ctx, (zf_cell)NF_INVALID_TENSOR);
        return;
    }
    int hc = nf_tensor_alloc(a->rows, a->cols);
    if (hc == NF_INVALID_TENSOR) { zf_push(ctx, (zf_cell)NF_INVALID_TENSOR); return; }
    NfTensor *c = nf_tensor_get(hc);
    int n = a->rows * a->cols;
    for (int i = 0; i < n; i++) c->data[i] = op(a->data[i], b->data[i]);
    zf_push(ctx, (zf_cell)hc);
    if (nf_tape_is_active() && hc != NF_INVALID_TENSOR)
        nf_tape_record(tape_op, ha, hb, hc);
}

static float op_add(float a, float b) { return a + b; }
static float op_mul(float a, float b) { return a * b; }

void nf_t_add(zf_ctx *ctx) { ew_binop(ctx, "t-add", NF_OP_T_ADD, op_add); }
void nf_t_mul(zf_ctx *ctx) { ew_binop(ctx, "t-mul", NF_OP_T_MUL, op_mul); }

/* Element-wise unary activation helper; allocates new output tensor */
static void ew_unary(zf_ctx *ctx, const char *name, NfOp tape_op,
                     float (*fn)(float))
{
    int ha = (int)zf_pop(ctx);
    NfTensor *a = nf_tensor_get(ha);
    if (!a) {
        fprintf(stderr, "%s: invalid handle %d\n", name, ha);
        zf_push(ctx, (zf_cell)NF_INVALID_TENSOR);
        return;
    }
    int hb = nf_tensor_alloc(a->rows, a->cols);
    if (hb == NF_INVALID_TENSOR) { zf_push(ctx, (zf_cell)NF_INVALID_TENSOR); return; }
    NfTensor *b = nf_tensor_get(hb);
    int n = a->rows * a->cols;
    for (int i = 0; i < n; i++) b->data[i] = fn(a->data[i]);
    zf_push(ctx, (zf_cell)hb);
    if (nf_tape_is_active() && hb != NF_INVALID_TENSOR)
        nf_tape_record(tape_op, ha, -1, hb);
}

static float act_sigmoid(float x) { return 1.0f / (1.0f + expf(-x)); }
static float act_relu(float x)    { return x > 0.0f ? x : 0.0f; }
static float act_tanh(float x)    { return tanhf(x); }

void nf_sigmoid(zf_ctx *ctx) { ew_unary(ctx, "sigmoid", NF_OP_SIGMOID, act_sigmoid); }
void nf_relu   (zf_ctx *ctx) { ew_unary(ctx, "relu",    NF_OP_RELU,    act_relu);    }
void nf_tanh_w (zf_ctx *ctx) { ew_unary(ctx, "tanh-w",  NF_OP_TANH_W,  act_tanh);   }

/* ( t -- t' )  softmax across all elements */
void nf_softmax(zf_ctx *ctx)
{
    int ha = (int)zf_pop(ctx);
    NfTensor *a = nf_tensor_get(ha);
    if (!a) {
        fprintf(stderr, "softmax: invalid handle %d\n", ha);
        zf_push(ctx, (zf_cell)NF_INVALID_TENSOR);
        return;
    }
    int hb = nf_tensor_alloc(a->rows, a->cols);
    if (hb == NF_INVALID_TENSOR) { zf_push(ctx, (zf_cell)NF_INVALID_TENSOR); return; }
    NfTensor *b = nf_tensor_get(hb);
    int n = a->rows * a->cols;
    /* Numerically stable: subtract max before exp */
    float mx = a->data[0];
    for (int i = 1; i < n; i++) if (a->data[i] > mx) mx = a->data[i];
    float sum = 0.0f;
    for (int i = 0; i < n; i++) { b->data[i] = expf(a->data[i] - mx); sum += b->data[i]; }
    if (sum > 0.0f) for (int i = 0; i < n; i++) b->data[i] /= sum;
    zf_push(ctx, (zf_cell)hb);
    if (nf_tape_is_active() && hb != NF_INVALID_TENSOR)
        nf_tape_record(NF_OP_SOFTMAX, ha, -1, hb);
}
