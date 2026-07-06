# Engine caps — overrun defence

**Status:** Done  
**Date:** 2026-05-17  
**Investigation:** [docs/qbert/investigations/2026-05-10-qbert-engine-caps.md](../qbert/investigations/2026-05-10-qbert-engine-caps.md)

## Context

Follow-up from the May-10 engine-caps investigation. Fixed-size buffers are intentional — console targets partition RAM up front at level load; the declared max is the real constraint. Three layers of defence:

1. **Pre-write assertion audit (Phase A)** — before any `ReadBytes` into a fixed LMalloc buffer, the code reads the incoming chunk size and asserts it fits before writing. Audit of all `ReadBytes` callsites in `level.cc`, `assets.cc`, `assslot.cc` found all already guarded — no new code needed.
2. **LMalloc canary (Phase B)** — `0xDEADBEEF` sentinel at the end of every `DO_ASSERTIONS` allocation; checked at the start of the next `Allocate`, at `Free`, and in `_Validate()`. Catches any overrun the callsite assertion missed.
3. **ASan build target (Phase C)** — `task build-asan` enables `-fsanitize=address,undefined`; catches the exact write instruction on dev workstations. Guard pages are pool-boundary-only and don't help for interior overruns — ASan is the right tool.

## Files changed

- `wfsource/source/memory/lmalloc.cc` — Phase B: enable `LMALLOC_TRACK_SIZE 1`; add `CANARY_VALUE = 0xDEADBEEF` to `FileLine`; write canary on every `Allocate`; check previous block's canary on next `Allocate`; check canary on `Free`; walk all live blocks in `_Validate()`.
- `CMakeLists.txt` — Phase C: `option(WF_ASAN ...)` + `add_compile/link_options(-fsanitize=address,undefined)` guard.
- `Taskfile.yml` — Phase C: `task build-asan` target.
