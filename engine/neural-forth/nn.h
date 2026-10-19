/* nn.h — linear layer, losses, Adam optimizer. */
#pragma once
#include <zforth.h>

#define NF_MAX_LAYERS 16
#define NF_MAX_OPTS    4

#ifdef __cplusplus
extern "C" {
#endif

/* Register a tensor handle as a trainable parameter visible to Adam. */
void nf_param_register(int tensor_h);

void nf_linear    (zf_ctx *ctx); /* ( in out -- layer )            */
void nf_forward   (zf_ctx *ctx); /* ( x layer -- y )  y = W@x + b */
void nf_loss_mse  (zf_ctx *ctx); /* ( pred target -- loss )        */
void nf_loss_ce   (zf_ctx *ctx); /* ( pred target -- loss )        */
void nf_adam_new  (zf_ctx *ctx); /* ( lr -- opt )                  */
void nf_adam_step (zf_ctx *ctx); /* ( opt -- )                     */

#ifdef __cplusplus
}
#endif
