/* neural_forth.h — public interface for the neural-forth dictionary.
 *
 * Include this header after <zforth.h> in C++ translation units.
 * In C translation units this header pulls in zforth.h itself.
 *
 * Two functions are exposed:
 *   nf_init     — defines all NF Forth words in the given context.
 *   nf_dispatch — called by scripting_zforth.cc when syscall 131 fires.
 *
 * Syscall assignment (ZF_SYSCALL_USER = 128):
 *   128 / custom 0 = read-mailbox      (existing WF)
 *   129 / custom 1 = write-mailbox     (existing WF)
 *   130 / custom 2 = write-actor-mailbox (existing WF)
 *   131 / custom 3 = neural-forth dispatch gate  ← this module
 *
 * All NF words share syscall 131; the word ID is passed on the data stack
 * immediately before the sys call, so nf_dispatch pops it first.
 */
#pragma once

/* Pull in zf_ctx type.  In C++ callers that already did
 *   extern "C" { #include <zforth.h> }
 * this include hits the guard and is a no-op. */
#include <zforth.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Define all NF Forth words in ctx.  Call once from Init(), after zf_bootstrap
 * and after the WF mailbox bridge words have been defined. */
void nf_init(zf_ctx *ctx);

/* Dispatch a neural-forth word call.  word_id has already been popped from
 * the data stack by the caller (scripting_zforth.cc's custom==3 branch). */
void nf_dispatch(zf_ctx *ctx, int word_id);

#ifdef __cplusplus
}
#endif
