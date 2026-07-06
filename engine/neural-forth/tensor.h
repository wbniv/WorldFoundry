/* tensor.h — tiny CPU tensor library for neural-forth.
 *
 * Tensors are 2D float32 arrays (rows × cols).  Forth code holds integer
 * handles (0..NF_MAX_TENSORS-1); all shape and data live in a global table.
 * Vectors are tensors with cols=1.
 *
 * The grad field is NULL until Stage 3 (autograd) pins it.  All other code
 * should leave grad alone for now.
 */
#pragma once
#include <zforth.h>

/* ── Tensor pool ─────────────────────────────────────────────────────────── */

#define NF_MAX_TENSORS   64
#define NF_INVALID_TENSOR (-1)

typedef struct {
    float *data;   /* malloc'd row-major storage, NULL if slot free */
    float *grad;   /* same shape; NULL until autograd stage */
    int    rows;
    int    cols;
} NfTensor;

#ifdef __cplusplus
extern "C" {
#endif

/* Internal accessors for use by autograd.c, nn.c, slot.c */
NfTensor *nf_tensor_get(int handle);
int        nf_tensor_alloc(int rows, int cols);  /* returns handle or NF_INVALID_TENSOR */
void       nf_tensor_release(int handle);
void       nf_tensor_zero(int handle);
void       nf_tensor_copy(int dst, int src);     /* must be same shape */

/* ── Forth word handlers ──────────────────────────────────────────────────── */

void nf_tensor_new  (zf_ctx *ctx); /* ( rows cols -- t )          */
void nf_tensor_free (zf_ctx *ctx); /* ( t -- )                    */
void nf_t_get       (zf_ctx *ctx); /* ( i j t -- v )              */
void nf_t_set       (zf_ctx *ctx); /* ( v i j t -- )              */
void nf_matmul      (zf_ctx *ctx); /* ( a b -- c )   A×B → new C  */
void nf_t_add       (zf_ctx *ctx); /* ( a b -- c )   element-wise */
void nf_t_mul       (zf_ctx *ctx); /* ( a b -- c )   element-wise */
void nf_sigmoid     (zf_ctx *ctx); /* ( t -- t' )    new tensor   */
void nf_relu        (zf_ctx *ctx); /* ( t -- t' )    new tensor   */
void nf_tanh_w      (zf_ctx *ctx); /* ( t -- t' )    new tensor   */
void nf_softmax     (zf_ctx *ctx); /* ( t -- t' )    new tensor   */

#ifdef __cplusplus
}
#endif
