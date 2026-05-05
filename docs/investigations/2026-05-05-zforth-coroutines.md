# zForth coroutines — investigation

**Date:** 2026-05-05

## Problem

Every multi-step timed sequence in a Forth actor script is currently written as a manual
dispatch table: a mailbox stores the current step index, and every tick the script
compares it against each arm and jumps to the right one.

```forth
\ current style — Q*bert autopilot sketch
: autopilot
  STEP @ 0 = if  1  0 do-hop  1 STEP !  exit  then
  STEP @ 1 = if  -1 0 do-hop  2 STEP !  exit  then
  STEP @ 2 = if  1  1 do-hop  3 STEP !  exit  then
  STEP @ 3 = if  ... ;
```

The same sequence with coroutine-style `pause`:

```forth
: autopilot
  1  0 do-hop pause
  -1 0 do-hop pause
  1  1 do-hop pause
  ... ;
```

The dispatch table is a manually-implemented coroutine frame. The readable form is
what the code would look like if the language had first-class coroutines.

## Why zForth doesn't have them today

`pause`/`resume` requires saving and restoring the interpreter's execution state
(instruction pointer + return stack) across calls. zForth is a minimal Forth — its
`zforth.c` run loop is a tight `while` loop with no mechanism for suspending mid-word
and re-entering later. Adding it requires changes to `zforth.c`.

Engine changes are prohibited for arcade ports per
`feedback_no_runtime_changes_for_ports.md`. The dispatch table is the correct
content-only workaround for the ports. This document investigates what a proper
coroutine facility would look like — for evaluation as a future engine improvement.

---

## zForth VM state that must be saved

| Field | Type | Description |
|-------|------|-------------|
| `ip` | `zf_addr` | Instruction pointer — next opcode to execute in the dict |
| `rstack[0..rsp-1]` | `zf_cell[]` | Return stack — return addresses for nested word calls |
| `rsp` | `zf_int` | Return stack depth |

The data stack (`dstack`, `dsp`) does NOT need to be saved for actor-script coroutines:
each call to `autopilot` from the actor system starts with an empty data stack, and
`pause` is only valid at points where the data stack is also empty (between hops).
If data-stack save/restore is needed it can be added later.

---

## Option A — source preprocessor (content-only, no engine changes)

A Python script transforms `pause`-annotated Forth source into the dispatch-table
form before the script is embedded in the level. The readable form is the source of
truth; the generated form is what the engine runs.

### Transformation rules

1. Split the word body on `pause` boundaries to get N arms.
2. Emit one helper word per arm: `: autopilot-0 ... 1 STEP ! ;`
3. Emit a jump table (array of execution tokens) and a dispatcher:

```forth
\ generated output for: autopilot with 3 pauses (4 arms)
: _ap0  1  0 do-hop  1 STEP ! ;
: _ap1  -1 0 do-hop  2 STEP ! ;
: _ap2  1  1 do-hop  3 STEP ! ;
: _ap3  ...  0 STEP ! ;   \ last arm resets to step 0

: autopilot
  STEP @ 0 = if _ap0 exit then
  STEP @ 1 = if _ap1 exit then
  STEP @ 2 = if _ap2 exit then
  STEP @ 3 = if _ap3 exit then ;
```

Or with a computed jump (cheaper for long sequences, but zForth has no `execute`
available in all build configs — check `zf_config.h`):

```forth
: autopilot
  STEP @
  0 over = if drop _ap0 exit then
  1 over = if drop _ap1 exit then
  ...
  drop ;
```

### Implementation

- A small Python script `wftools/zf_preprocess.py` (≈ 80 lines).
- Input: `.zf.src` files. Output: `.zf` files embedded in the level via the existing
  Forth script pipeline.
- Add a preprocessing step in `blender_create_qbert.py` (or as a Taskfile target) that
  runs the preprocessor before building the level binary.

### Costs

- **Readability**: source files are clean; generated files look like the current dispatch tables.
- **Debuggability**: step through the generated form via the bridge; `STEP` mailbox still readable.
- **Scope**: zero engine changes. Fully within the content-only constraint.
- **Limitation**: `pause` is only valid at the top level of the coroutine word (not inside
  helper words called from it). A nested `pause` inside a called sub-word would require
  continuation-passing refactoring of the called word — significantly more complex.

---

## Option B — zForth primitive `pause` / `resume` (minimal engine change)

Add `pause` and `resume` as two new ZF primitives. Each active coroutine gets a small
state buffer. The actor system calls `resume coroutine-xt` instead of `execute`.

### VM changes required (`zforth.c`, `zforth.h`)

#### 1. New result code

```c
// zforth.h
typedef enum {
    ZF_OK          = 0,
    ZF_ABORT_INTERNAL_ERROR,
    ZF_ABORT_OUTSIDE_MEM,
    // ...existing codes...
    ZF_PAUSE,          // ← new: word suspended via `pause`
} zf_result;
```

#### 2. Coroutine state struct

```c
// zforth.h  (or a new zf_coro.h)
#define ZF_CORO_RSTACK_MAX 32

typedef struct {
    zf_addr  ip;
    zf_int   rsp;
    zf_cell  rstack[ZF_CORO_RSTACK_MAX];
    int      active;   // 0 = not started or finished, 1 = suspended
} zf_coro;
```

One `zf_coro` per actor that uses coroutines. In WF the actor system allocates one per
running Forth script context — practically one per actor.

#### 3. `pause` primitive

When the interpreter executes `pause`:

```c
case ZF_PRIM_PAUSE:
    // snapshot state into the active coroutine handle
    coro->ip  = ip;
    coro->rsp = rsp;
    memcpy(coro->rstack, rstack, rsp * sizeof(zf_cell));
    coro->active = 1;
    // signal caller to stop
    return ZF_PAUSE;
```

The run-loop `while` exits via a `return` inside the `ZF_PRIM_PAUSE` case, so no other
state needs unwinding.

#### 4. `resume` entry point

A new API function (not a Forth word):

```c
zf_result zf_coro_resume(zf_coro *coro) {
    if (!coro->active) return ZF_ABORT_INTERNAL_ERROR;
    // restore state
    ip  = coro->ip;
    rsp = coro->rsp;
    memcpy(rstack, coro->rstack, rsp * sizeof(zf_cell));
    coro->active = 0;  // cleared on re-entry; set again if pause fires
    return zf_run();   // re-enter the interpreter loop
}
```

The actor system calls `zf_coro_resume(&actor->coro)` each tick instead of
`zf_exec_word(actor->script_xt)`.

#### 5. Forth-level `resume` word (optional)

If scripts need to chain coroutines:

```forth
: run-autopilot ( -- )   ['] autopilot resume ;
```

This calls back into the C `resume` via a primitive.

### Word count

~80 lines of C across `zforth.c` and `zforth.h`. No changes to the WF actor system
beyond adding one `zf_coro` field to the actor state struct (or the script context).

### Costs

- **Engine change**: Yes — modifies `zforth.c` and `zforth.h`. Requires explicit
  user permission under `feedback_no_runtime_changes_for_ports.md`.
- **Correctness risk**: The saved `ip` points into the compiled dictionary. If the
  dictionary is relocated between ticks (e.g. a `forget` or recompile), the saved `ip`
  becomes invalid. zForth doesn't currently relocate the dictionary at runtime, so this
  is safe in practice.
- **Return-stack overflow**: If the coroutine is suspended with a deeply nested call
  stack, `ZF_CORO_RSTACK_MAX` must be large enough. 32 cells is generous for simple
  actor sequences.
- **Concurrency**: Only one coroutine can be active inside the zForth VM at a time
  (the VM is single-threaded). Actor scripts already run sequentially per frame, so
  this is fine.

---

## Option C — setjmp/longjmp (alternative C implementation)

Instead of explicitly copying the return stack, use `setjmp` at the `resume` call site
and `longjmp` inside `pause`. This avoids copying but ties the coroutine to the C call
stack — each active coroutine must keep its C stack frame alive, requiring a dedicated
OS thread or `ucontext_t` per coroutine. Much heavier than Option B. Not recommended.

---

## Comparison

| | Option A (preprocessor) | Option B (primitive) |
|---|---|---|
| Engine changes | None | ~80 lines in zforth.c/h |
| Works for ports today | ✅ | Requires permission |
| `pause` inside sub-words | ❌ (top-level only) | ✅ (anywhere) |
| Source readability | ✅ (src files clean) | ✅ |
| Debug via bridge | ✅ (STEP mailbox) | ✅ (coro->active flag) |
| Implementation effort | ~80 lines Python | ~80 lines C |
| Risk | Low | Low–medium |

---

## Recommendation

**For ports (now):** Option A. The preprocessor keeps the source readable while
staying within the content-only constraint. Write the autopilot as `pause`-style,
run the preprocessor at build time.

**For the engine (future):** Option B. The primitive is small, low-risk, and unlocks
`pause` anywhere in the call tree — something the preprocessor can never match. Should
be proposed as a standalone engine improvement after the current port ships, with the
"small well-scoped C change" framing distinct from "runtime changes for ports."

---

## Files affected

### Option A
| File | Change |
|------|--------|
| `wftools/zf_preprocess.py` | New — ~80-line preprocessor |
| `wflevels/*/blender_create_*.py` | Add preprocessing step before script embedding |
| `Taskfile.yml` | New `preprocess-scripts` target |
| Actor source files (`*.zf.src`) | Rename from `.zf`; add `pause` annotations |

### Option B
| File | Change |
|------|--------|
| `engine/stubs/zforth.h` | `ZF_PAUSE` result code, `zf_coro` struct |
| `engine/stubs/zforth.c` | `ZF_PRIM_PAUSE` case, `zf_coro_resume()` |
| Actor system (1 file, ~10 lines) | Add `zf_coro` field; call `zf_coro_resume` per tick |

---

## Open questions

1. **Multiple coroutines per actor?** Probably not needed — one per actor is sufficient
   for the Q*bert use case. A pool would be needed for e.g. cutscene directors that
   sequence multiple sub-routines.

2. **`pause` with arguments on the data stack?** If the coroutine needs to yield a
   value (e.g. `42 pause` to signal the caller), the data stack save/restore is also
   needed. Straightforward extension of Option B.

3. **Preprocessor composability?** Can two `pause`-words call each other? No — the
   preprocessor approach breaks down with mutual recursion. Option B handles it naturally.

---

## Coroutines across all WF Forth engines

WF vendors six Forth implementations besides zForth. Each has a different architecture;
coroutine difficulty varies dramatically. This section evaluates them all so the engine
choice can be revisited if zForth proves unsuitable.

The question for each engine: **can the actor system suspend a running Forth word mid-
execution and resume it next tick, with zero or minimal engine-source changes?**

---

### nanoFORTH (`engine/vendor/nanoforth-3b9c3aab/`)

**Architecture**: Arduino-native Forth with a cooperative multitasker designed in from
the start.

**Relevant API** (`n4.h`):

```c
static void yield();           // suspend current task, run next
static void wait(U32 ms);      // yield for at least ms milliseconds
void add_api(U32 api_code, void(*fp)());  // register C function as Forth word
```

`N4_TASK` is a Forth keyword; the runtime maintains a task ring. `yield()` suspends the
calling task and hands control to the next one.

**Coroutine approach**: Call `yield()` directly from Forth source. No C scaffolding
required at all — it is the designed use case.

**Engine changes required**: None.

**Host effort**: Zero. Use `yield` in Forth scripts as-is.

**Caveat**: nanoFORTH targets Arduino/AVR. The vendor copy may not compile cleanly for
Linux or Android without a porting shim. Check `CMakeLists.txt` for platform guards
before betting on this.

---

### embed (`engine/vendor/embed-154aeb2f/`)

**Architecture**: Minimal ANS Forth VM written as a portable C library, explicitly
designed for embedding in host applications.

**Relevant API** (`embed.h`):

```c
// Yield callback — return non-zero to suspend the VM
typedef int (*embed_yield_t)(void *param);

typedef struct {
    embed_yield_t yield;    // called every N instructions
    size_t        yields;   // how often to call yield (0 = never)
    // ...
} embed_opt_t;

// VM memory image snapshot/restore
int embed_core_get(embed_t *h, void *core, size_t length);
int embed_core_set(embed_t *h, const void *core, size_t length);
```

**Coroutine approach**: Set `opt.yields = 1` and provide a yield callback that sets a
flag and returns 1 when the `pause` word executes. The VM exits its run loop via the
callback. Save the full memory image with `embed_core_get()` before returning; restore
it with `embed_core_set()` on the next tick call.

`pause` can be a thin Forth word that calls back through a registered C function (via
`embed_add_prim()` or the primitive table) which sets the flag.

**Engine changes required**: None. The yield callback is the designed mechanism.

**Host effort**: ~30 lines of C in the WF actor layer (flag variable, callback function,
core snapshot buffer, save/restore wrappers).

---

### Atlast (`engine/vendor/atlast-08ff0e1a/`)

**Architecture**: John Walker's FORTH-83 derived scripting engine. All interpreter state
is **global `extern` variables** — the interpreter has no encapsulation at all.

**Relevant symbols** (`atldef.h`):

```c
// Instruction pointer — next word to execute
extern dictword **ip;           // atldef.h line 125

// Return stack pointers — all global
extern dictword ***rstack;      // base of return stack
extern dictword ***rstk;        // current top (post-increment)
extern dictword ***rstackbot;
extern dictword ***rstacktop;

// Data stack (also global; may need saving if non-empty at pause)
extern stackitem *stack, *stk, *stackbot, *stacktop;
```

**Coroutine approach**: From host C, snapshot `ip`, `rstk`, and the stack contents into
a per-actor struct before returning from `atl_exec()`. Restore them the next tick.
Because all state is global, no struct traversal is needed — just pointer copies and
`memcpy`.

```c
typedef struct {
    dictword **ip;
    dictword ***rstk;
    dictword  **rstack_buf[ATL_RSTACK_DEPTH];
    int        rstack_depth;
    int        active;
} AtlCoro;

// On pause:
coro->ip = ip;
coro->rstk = rstk;
coro->rstack_depth = (int)(rstk - rstack);
memcpy(coro->rstack_buf, rstack, coro->rstack_depth * sizeof(*rstk));
coro->active = 1;
return Memerrs;   // exit atl_exec() via error path (simplest exit)

// On resume:
ip   = coro->ip;
rstk = coro->rstk;
memcpy(rstack, coro->rstack_buf, coro->rstack_depth * sizeof(*rstk));
atl_exec(NULL);   // re-enter interpreter
```

The `pause` Forth word itself is registered with `atl_primdef()`.

**Engine changes required**: None. All state is already accessible.

**Host effort**: ~35 lines of C (struct definition + two helper functions).

**Caveat**: Atlast is single-threaded; all globals are shared. Only one coroutine can be
"in flight" inside `atl_exec()` at a time — the same constraint as zForth. That is fine
for the WF actor model (one script runs per actor per tick).

---

### ficl (`engine/vendor/ficl-3.06/`)

**Architecture**: ANSI C99 Forth interpreter with clean object-oriented C API. VM state
lives in a `ficlVm` struct that is fully visible to the host.

**Relevant fields** (`ficl.h`):

```c
struct ficlVm {
    // ...
    IPTYPE        ip;       // line 398 — instruction pointer, public struct field
    FICL_STACK   *rStack;  // line 403 — return stack, public struct field
    FICL_STACK   *dataStack;
    // ...
};

// Stack API (public):
int   stackDepth(FICL_STACK *stack);
void  stackPush(FICL_STACK *stack, CELL cell);
CELL  stackPop(FICL_STACK *stack);
```

**Coroutine approach**: After registering a `pause` primitive (via `ficlSystemCreatePrimitive`),
when `pause` executes it snapshots `vm->ip` and deep-copies `vm->rStack` into a
per-actor buffer, then returns `VM_INNEREXIT` to unwind the run loop. On the next tick,
the actor layer restores those fields and calls `ficlVmExecuteXT()`.

**Engine changes required**: None. The public struct makes host-driven snapshotting
straightforward.

**Host effort**: ~40 lines of C (snapshot struct + save/restore functions + `pause`
primitive registration).

---

### pForth (`engine/vendor/pforth-63d4a418/`)

**Architecture**: Portable Forth written by Phil Burk. Designed from the start with
cooperative multitasking in mind — the task struct mirrors traditional Forth TASK
blocks.

**Relevant API** (`pf_guts.h`):

```c
typedef struct pfTaskData_t {
    cell_t  *td_StackBase;    // data stack base
    cell_t  *td_StackPtr;     // data stack pointer
    cell_t  *td_ReturnBase;   // return stack base
    cell_t  *td_ReturnPtr;    // return stack pointer (= IP save slot)
    cell_t  *td_InsPtr;       // instruction pointer
    // ...
} pfTaskData_t;

extern pfTaskData_t *gCurrentTask;  // line 511 — active task, globally accessible
```

A `?PAUSE` word exists in `fth/misc1.fth` ("pause if key hit") — the infrastructure is
present but `PAUSE` as a cooperative yield is not wired.

**Coroutine approach**: Allocate a `pfTaskData_t` per actor at startup (via `pfCreateTask`
if that API exists, or `calloc` + manual init). Each tick, swap `gCurrentTask` to the
actor's task pointer, call `pfCatch()` or `pfExecuteColon()`, and swap back.

The `PAUSE` word sets a flag that causes the execution loop to return early; on the next
tick `gCurrentTask` still points at the correct task struct, so execution resumes where
it left off.

**Engine changes required**: None for the struct; need to wire `PAUSE` to set an exit
flag (~15 lines in `pf_inner.c`). OR avoid touching pForth source and implement it the
same way as the Atlast approach: snapshot `gCurrentTask->td_InsPtr` and return stack
from within the `PAUSE` primitive registered from the host.

**Host effort**: ~50 lines of C (task init, swap harness, pause primitive, resume path).

---

### libforth (`engine/vendor/libforth-b851c6a2/`)

**Architecture**: Compact ANS Forth implementation. The `forth_t` / `struct forth` is
**fully opaque** — no fields are exposed in the public header.

**Relevant non-API** (`libforth.h`):

```c
// That's it. The struct is never defined in the public header.
struct forth;
typedef struct forth forth_t;
```

**Coroutine approach**: None possible from the host without modifying `libforth.c`.
A `pause` primitive can be registered (via `forth_define_primitive()`), but when it
fires there is no way to save `ip` or the return stack without reading the private source.

**Engine changes required**: Yes. Need to either:
- Expose a `forth_suspend(forth_t*, forth_coro_t*)` / `forth_resume()` API, or
- Add a `pause` flag and early-exit hook inside the eval loop (~40–50 lines in
  `libforth.c`).

**Host effort**: ~50 lines of C *inside* `libforth.c` plus ~20 lines in the WF actor
layer.

---

## Engine comparison table

| Engine | VM state | Native yield | Host-side approach | Engine src changes | Host effort |
|--------|----------|----|----|----|-----|
| **nanoFORTH** | internal (task ring) | ✅ `yield()` built in | Use `yield` in Forth source | None | 0 lines |
| **embed** | `embed_core_get/set` | ✅ `embed_yield_t` callback | Set yield callback; snapshot core image | None | ~30 lines C |
| **Atlast** | `extern` globals | ❌ | Snapshot `ip`/`rstk` globals; exit via error | None | ~35 lines C |
| **ficl** | public struct fields | ❌ | Snapshot `vm->ip`/`vm->rStack`; `VM_INNEREXIT` | None | ~40 lines C |
| **pForth** | public `pfTaskData_t` | Partial (`?PAUSE`) | Swap `gCurrentTask`; snapshot task struct | ~15 lines (optional) | ~50 lines C |
| **zForth** | static locals (private) | ❌ | Option A: preprocessor | None | ~80 lines Python |
|            |                       | | Option B: `ZF_PAUSE` primitive | ~80 lines C | ~10 lines C |
| **libforth** | opaque struct | ❌ | Must add `suspend`/`resume` to source | ~50 lines C | ~20 lines C |

*"Engine src changes"* = edits to vendored engine source (not WF actor layer).
*"Host effort"* = WF-side C code only, excluding engine changes.

---

## Updated recommendation

**For Q*bert ports (now):** Use Option A (preprocessor) for zForth — it requires no
engine changes and keeps Forth source readable. The dispatch-table output is the same
code that works today.

**If switching engines for coroutine quality:**

1. **embed** is the best fit for WF's use case. The yield callback was designed for
   exactly this (cooperative scheduling in a host-driven game loop), core save/restore
   is a first-class API, and it is already vendored. Zero engine changes.

2. **Atlast** is second — all state is global, so saving/restoring a coroutine frame is
   trivial C. Already vendored. Zero engine changes.

3. **ficl** is third — public struct, clean API, already vendored.

4. **nanoFORTH** has the most capable multitasking but is Arduino-targeted; verify it
   builds for Linux/Android before committing to it.

5. **pForth** is viable but has the most WF-side plumbing.

6. **libforth** and **zForth** are the hardest — both require engine source changes for
   proper coroutines. zForth at least has Option A as a no-change workaround.

**Recommended long-term path:** Switch actor scripts to **embed** when the engine team
is ready for a scripting backend upgrade. embed's yield callback makes the game-loop
integration clean: each tick calls `embed_eval()`, the yield callback fires when a
`pause` word executes, and `embed_core_get()` snapshots the entire VM state in one call.
No engine source modifications required.
