/*
 * wfcrdt_stub.c — one-file placeholder so CMake has a real translation unit
 * for the libwfcrdt.a target. Until the C++ RAII wrapper lands as a
 * follow-up phase, libwfcrdt.a is essentially "libyrs.a + the public
 * libyrs.h include path" surfaced as a single linkable target.
 *
 * Plan: docs/plans/2026-05-18-yrs-c-abi-binding.md
 */

void wfcrdt_link_anchor(void) {}
