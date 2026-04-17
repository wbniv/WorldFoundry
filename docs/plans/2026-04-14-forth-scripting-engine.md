# Plan: Forth as a scripting engine option for World Foundry

**Date:** 2026-04-14
**Status:** **Complete — all seven phases landed 2026-04-16.**
All six backends build and link; snowgoons.iff + cd.iff carry Forth scripts
(`\ wf` sigil) via `scripts/patch_snowgoons_forth.py` (byte-preserving patch,
no iff.txt recompile needed). zForth smoke-tested 2026-04-15 (GROUND, no
crashes); all five remaining backends (ficl, atlast, embed, libforth, pforth)
implemented and build-verified 2026-04-16. Notable integration issues resolved:
- **atlast**: neither `atldef.h` nor `atlast.h` safe to include in C++ TU
  (`atldef.h` macros pollute stdlib headers; `atlast.h` uses K&R empty parens).
  All needed symbols declared manually; `-DEXPORT` on atlast.c for stack access.
- **libforth**: `forth_t` is fully opaque; CALL bridge can't access `o->m[TOP]`
  safely. Redesigned to use C global exchange buffer addressed via Forth `!`/`@`.
- **pforth**: `pfInit()` is file-static; `PF_DEFAULT_*` constants are file-scoped
  in pf_core.c. Also needs posix/pf_io_posix.c + stdio/pf_fileio_stdio.c. 
  `system.fth` uses bare `include` filenames — requires `chdir` to fth/ during load.
**Prior art:** `docs/plans/2026-04-14-pluggable-scripting-engine.md` (JS pattern),
`docs/plans/2026-04-14-wasm3-scripting-engine.md` (wasm3 pattern),
`docs/plans/2026-04-14-wren-scripting-engine.md` (Wren pattern)

## Ranked shortlist (open-source, WF-viable)

| Rank | Name | Size | License | API quality | Role |
|------|------|------|---------|-------------|------|
| **1** | **zForth** | 4 KB core | MIT | ★★★★ | **Default** — smallest viable VM; 2 files; purpose-built for embedding |
| **2** | **ficl** | ~100 KB | BSD-2 | ★★★★★ | **Option** — best ANS compliance; named-word registration; most ergonomic scripts |
| **3** | **Atlast** | ~30 KB | PD | ★★★ | **Option** — Autodesk-pedigree; single C file; designed for embedding |
| **4** | **embed** | ~5 KB VM; ~43 KB binary | MIT | ★★★ | **Option** — smallest possible; 16-bit integer cells; correct on real target (fixed-point mailboxes); PC dev: float values truncated to int (documented dev divergence) |
| **5** | **libforth** | ~50 KB | MIT | ★★★★ | **Option** — clean push/pop/eval API; C99; fork adds libffi |
| **6** | **pForth** | ~120 KB | 0-BSD | ★★★ | **Option** — proven on 40+ platforms; strong FP; used in 3DO/WebTV |

---

## Forth implementation survey

All reasonable open-source and commercial Forth implementations evaluated against WF's
constraints: C-embeddable, statically linkable, no filesystem at runtime, MIT/BSD/PD
license, small binary footprint, per-frame call overhead low.

### Open-source — full comparison table

| # | Name | License | Core size | Embedding API | Forth standard | Maintenance | Notes |
|---|------|---------|-----------|---------------|----------------|-------------|-------|
| 1 | **zForth** | MIT | ~4 KB VM code; ~54 KB stripped binary | `zf_init/eval/push/pop`; single `zf_host_sys()` callback for all C ↔ Forth | Forth-83 influenced; pragmatic subset | Active (2026) | 2 files (`zforth.c/.h`); purpose-built for embedding; variable-length cells |
| 2 | **ficl** | BSD-2 | ~100 KB core; ~175 KB binary | `ficlSystemCreate` + `ficlVmEvaluate`; `ficlBuild()` registers named C words; stack macro API | ANS Forth 1994 + OOP extensions | Active (v3.06, Feb 2026) | Most professional embedding API; multiple VMs; shared dict |
| 3 | **libforth** | MIT | ~50 KB | `forth_new/eval/push/pop/delete` | Custom simplified | Stable | Howerj; fork adds libffi; C99; clean API |
| 4 | **pForth** | 0-clause BSD (PD) | ~120 KB | C glue via `pf_cglue.c`; dict exportable as C source | ANS Forth subset | Active (2024–2025) | Phil Burk; used in 3DO/OpenFirmware/WebTV; 40+ platforms; good FP |
| 5 | **Atlast** | Public domain | ~30 KB | `atlInit/atlRun/atlDefine` | Forth-like (custom) | Stable | John Walker (Autodesk founder); designed for embedding; used by Ghostscript |
| 6 | **embed** | MIT | ~5 KB VM; ~43 KB binary | `embed_new/eval` + I/O callbacks | eForth model | Stable | Howerj; 16-bit integer cells; correct on real target (fixed-point mailboxes); PC dev float values truncated to int (documented divergence); 128 KB image ceiling |
| 7 | ~~**Retro Forth**~~ | ~~ISC~~ | ~~\~300 KB~~ | ~~None — no C embedding API~~ | ~~Custom~~ | ~~Active~~ | ~~No per-frame call path; not suitable~~ |
| 8 | ~~**gForth**~~ | ~~GPL v3+~~ | ~~1+ MB~~ | ~~`gforth_stacks/execute`; libgforth.a~~ | ~~ANS Forth 2012 (best compliance)~~ | ~~Active~~ | ~~**GPL; too large (~1 MB); disqualified**~~ |
| 9 | ~~**kForth-64**~~ | ~~GPL~~ | ~~large~~ | ~~Standalone focus~~ | ~~ANS~~ | ~~Active~~ | ~~**GPL license; standalone-only; disqualified**~~ |
| 10 | ~~**4tH**~~ | ~~LGPL~~ | ~~medium~~ | ~~Compiler-oriented~~ | ~~Custom~~ | ~~Active~~ | ~~**LGPL; awkward for embedding; disqualified**~~ |
| 11 | ~~**SP-Forth**~~ | ~~GPL~~ | ~~—~~ | ~~Windows/x86 native~~ | ~~—~~ | ~~—~~ | ~~**GPL; Windows/x86-only; disqualified**~~ |
| 12 | ~~**bigFORTH**~~ | ~~GPL~~ | ~~large~~ | ~~Native code gen; GUI-heavy~~ | ~~—~~ | ~~—~~ | ~~**GPL; disqualified**~~ |
| 13 | ~~**JonesForth**~~ | ~~public domain~~ | ~~tiny~~ | ~~x86 assembly tutorial~~ | ~~—~~ | ~~—~~ | ~~Educational only; not a C library~~ |
| 14 | ~~**amForth**~~ | ~~GPL~~ | ~~\~11 KB Flash~~ | ~~AVR only~~ | ~~Forth-2012 variant~~ | ~~Active~~ | ~~**GPL; AVR microcontroller-only; disqualified**~~ |
| 15 | **mecrisp** | PD | ~11 KB Flash | Bare-metal; no C API | Forth-2012 variant | Active | ARM Cortex-M/MSP430/RISC-V; no desktop embedding |
| 16 | ~~**tinyforth**~~ | ~~unlicensed/MIT~~ | ~~tiny~~ | ~~Minimal~~ | ~~Custom~~ | ~~Sparse~~ | ~~173duprot; educational skeleton only~~ |
| 17 | **nanoFORTH** | MIT | 1 KB dict (configurable); 1.4 KB total VM | `n4_push/pop/api()` — Linux stubs already in source | ~62 words, 16-bit cells | Active (v2.2, 2024) | Port: ~120 lines, 2–3 days; 16-bit cells (same as embed); needs Stream wrapper for `eval`; not a WF backend yet — see deep-dive |
| 18 | ~~**MUF**~~ | ~~varies~~ | ~~—~~ | ~~MUCK-specific~~ | ~~—~~ | ~~—~~ | ~~Not general-purpose~~ |

### Commercial — summary

| Name | Price | Embedding model | Verdict |
|------|-------|-----------------|---------|
| ~~**SwiftForth** (FORTH Inc.)~~ | ~~$199 one-time + $199/yr support~~ | ~~Turnkey app distribution; native x86 code generator — not a C library you call into~~ | ~~**Unsuitable** — can't `eval` a string in-process per frame~~ |
| ~~**VFX Forth** (MPE)~~ | ~~Free (non-commercial) / €19–79/month~~ | ~~Turnkey app; royalty-free runtime for compiled apps; optimizing compiler, not an embeddable interpreter~~ | ~~**Unsuitable** — same issue~~ |
| ~~**iForth**~~ | ~~Unknown~~ | ~~Native code compiler~~ | ~~**Unsuitable** — same issue; pricing unclear~~ |

**Commercial verdict:** All major commercial Forths are native-code *compilers* that produce standalone executables, not interpreter VMs you link as a C library and call into per frame. For WF's "eval a script string each game tick" pattern, commercial Forths don't fit without a sub-process model. Open source only.

---

## Pluggable Forth backends: `WF_FORTH_ENGINE`

Forth follows the same pluggable-backend pattern as `WF_JS_ENGINE` (quickjs vs. jerryscript):
- **Exactly one** Forth engine may be compiled in at a time (or none).
- All six share the same sigil (`\`), the same `scripting_forth.hp` ABI, and the same `scripting_stub.cc` dispatch block.
- Each lives in its own `scripting_<engine>.cc` file.
- `WF_FORTH_ENGINE=zforth` is the default when Forth is enabled; the flag must be set explicitly.

```
WF_FORTH_ENGINE=none       (default — no Forth compiled in)
WF_FORTH_ENGINE=zforth     (4 KB core, MIT, sys-callback bridge)
WF_FORTH_ENGINE=ficl       (100 KB, BSD-2, named-word bridge)
WF_FORTH_ENGINE=atlast     (30 KB, PD, atlDefine bridge)
WF_FORTH_ENGINE=embed      (5 KB VM, MIT, 16-bit cells; ROM-able image; correct on fixed-point target)
WF_FORTH_ENGINE=libforth   (50 KB, MIT, forth_new/eval/push/pop API)
WF_FORTH_ENGINE=pforth     (120 KB, 0-BSD, ANS subset; strong FP; proven on 40+ platforms)
```

---

## Sigil: `\` (backslash)

`\` is the standard Forth line-comment marker. It is:
- **Invalid in Lua** at position 0 (not a valid token)
- **Invalid in JavaScript** at position 0
- **Idiomatic Forth** — `\ comment` is the universal Forth line-comment form

Dispatch check: `p[0] == '\\'` → route to Forth.

Scripts open with `\ wf` (a Forth line comment naming the engine):
```forth
\ wf
INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox
```

The `\` check is inserted **before** the `//wren\n` and `//` checks in `RunScript`. Updated full dispatch order:
`\` → Forth, `//wren\n` → Wren, `//` → JS, `#b64\n` → wasm3, `;` → Fennel, else → Lua fallthrough.

---

## Forth API surface — per-backend comparison

All six backends expose the same WF bridge (`read-mailbox`, `write-mailbox`) and the same constant globals. The mechanism differs per engine:

| | zForth | ficl | Atlast | embed | libforth | pForth |
|-|--------|------|--------|-------|----------|--------|
| **C→Forth word binding** | `sys` + `zf_host_sys()` callback keyed by integer | `ficlBuild(sys, "name", fn, flags)` — named word directly | `atlDefine("name", fn)` — named primitive | custom word + I/O dispatch callbacks | `forth_define_word(vm, "name", fn)` or similar callback | `pf_CCall()` via `pf_cglue.c` registration table |
| **Script ergonomics** | `read-mailbox`, `write-mailbox` via `sys`-dispatch bootstrap words | Named words — most natural syntax | Named words — natural syntax | Named words via custom primitives | Named words | Named words via C glue table |
| **Constants** | `N constant NAME` eval'd at init | `ficlVmEvaluate(vm, "N constant NAME\n...")` at init | `atlRun("N constant NAME\n...")` at init | eval'd into image at init | `forth_eval(vm, "N constant NAME\n...")` | `pforth_eval("N constant NAME")` |
| **Eval per frame** | `zf_eval(&ctx, src)` | `ficlVmEvaluate(vm, src)` | `atlRun(src)` | `embed_eval(m, src_stream)` — needs Stream wrapper | `forth_eval(vm, src)` | `pfSetNextToken(src)` + `pfCatch()` |
| **Return value** | `zf_pop(&ctx, &cell)` → cast to float | `ficlStackPopFloat(vm->dataStack)` | top of stack via `S0` macro | `embed_pop(m)` → 16-bit int | `forth_pop(vm)` → native int | `pfStackPop()` → cell |
| **Cell width** | 32-bit (configurable 16–128-bit) | native (32/64-bit) | native (32/64-bit) | **16-bit fixed** | native (32/64-bit) | 32/64-bit (platform native) |
| **Float support** | optional (compile flag) | ✓ built-in | ✗ | ✗ (16-bit int only) | ✗ | **✓ strong — best of group** |
| **Image ceiling** | none (heap) | none | none | **128 KB total** | none | none |
| **ROM-able image** | ✗ | ✗ | ✗ | **✓ only embed has this** | ✗ | ✗ |
| **Forth standard** | Forth-83 subset | ANS 1994 + OOP | Forth-like custom | eForth model | custom simplified | ANS subset |
| **Vocabulary richness** | minimal | **most complete** | moderate | eForth standard | moderate | moderate + FP |
| **Multiple VM instances** | ✓ (`zf_ctx` struct) | ✓ (shared dict, multiple VMs) | limited | ✓ (per `embed_t*`, costs 128 KB each) | ✓ | limited |
| **Maintenance** | active (2026) | active (v3.06, 2026) | stable | stable | stable | active (2024–25) |
| **License** | MIT | BSD-2 | Public domain | MIT | MIT | 0-clause BSD (PD) |
| **Binary size** | ~4 KB core / ~54 KB binary | ~100 KB core / ~175 KB binary | ~30 KB | ~5 KB VM / ~43 KB binary | ~50 KB | ~120 KB |
| **Vendor complexity** | **2 C files** | ~15 C files | **1 C file + header** | ~3 C files + image | 1 C file | ~9 C files |
| **PC dev float handling** | 32-bit cell — correct | 64-bit cell — correct | native — correct | **truncated to 16-bit int** | native — correct | native — correct |
| **Real target (fixed-point)** | correct | correct | correct | **correct and natural** | correct | correct |
| **Recommended for** | default; minimal footprint; per-frame speed | complex scripts; ANS compliance; OOP | minimal vendoring; simple embedding | real-target ROM deployment; absolute min size | clean API; mid-size; libffi available | float-heavy scripts; proven portability |

### C binding bootstrap snippets

**zForth** (`sys` dispatch, eval'd once at init):
```forth
: read-mailbox   0 sys ;
: write-mailbox  1 sys ;
```
`zf_host_sys()` switches on `ZF_SYSCALL_CUSTOM+0` / `+1`.

**ficl** (named word registration at init):
```cpp
ficlBuild(pSys, "read-mailbox",  ficl_read_mailbox,  FICL_WORD_DEFAULT);
ficlBuild(pSys, "write-mailbox", ficl_write_mailbox, FICL_WORD_DEFAULT);
```

**Atlast** (named primitive registration at init):
```cpp
atlDefine("read-mailbox",  atlast_read_mailbox);
atlDefine("write-mailbox", atlast_write_mailbox);
```

**libforth** (callback registration at init):
```cpp
forth_define_word(vm, "read-mailbox",  libforth_read_mailbox);
forth_define_word(vm, "write-mailbox", libforth_write_mailbox);
```

**pForth** (C glue table in `pf_cglue.c`):
```cpp
// Add to pfCGlueTable[]:
{ "read-mailbox",  pforth_read_mailbox },
{ "write-mailbox", pforth_write_mailbox },
```

---

## embed deep-dive: constraints, tradeoffs, and where it wins

### The 128 KB ceiling — what it actually is

The 128 KB is **per interpreter instance** (per `embed_t*`), not per script. It is the
total size of the Forth image: dictionary (all defined words) + data stack + return
stack + user variables — the entire VM state lives in one flat allocation. Estimated
consumption at startup for WF:

| Item | Approximate size |
|------|-----------------|
| eForth standard library (built-in words) | ~20–30 KB |
| ~100 `INDEXOF_*` / `JOYSTICK_BUTTON_*` constants | ~1–2 KB |
| `read-mailbox`, `write-mailbox` bootstrap words | < 100 bytes |
| Remaining for user-defined words + script execution | **~90–100 KB** |

Running multiple embed instances (e.g., one per game object) to work around the ceiling
is technically possible — each `embed_t*` has its own 128 KB allocation — but wastes
memory linearly with instance count and doesn't help if a single script exceeds the
dictionary budget on its own.

### embed vs zForth — feature comparison

| Feature | zForth | embed |
|---------|--------|-------|
| **Cell width** | 32-bit default (configurable 16–128-bit) | **16-bit fixed** — no path to wider without forking |
| **Integer range** | ±2 billion (32-bit) | ±32 767 — fine for mailbox indices and small counts |
| **Float support** | Optional at compile time | **None** — integer/fixed-point only |
| **Mailbox values on PC dev** | 32-bit float passed through correctly | **Truncated to 16-bit int** — documented dev divergence |
| **Mailbox values on real target** | Fixed-point cast to 32-bit cell — fine | **Fixed-point in 16-bit cell — correct and natural** |
| **Total VM memory** | Heap-allocated, no hard ceiling | **128 KB hard ceiling** per instance |
| **Dictionary growth** | Unlimited (heap) | Counted against 128 KB; ~90–100 KB available post-init |
| **Multiple VM instances** | ✓ — `zf_ctx` is a plain struct | Possible but each costs another 128 KB |
| **C API ergonomics** | `zf_eval(ctx, string)` — direct string | Requires wrapping source in a stream/callback |
| **Standard vocabulary** | Compact pragmatic subset | **eForth standard** — more complete word set |
| **Self-hosting / metacompiler** | No | **Yes** — can regenerate its own image from Forth source; customizable standard library |
| **Cold start** | Interprets bootstrap source at init — dictionary built in RAM | **Loads pre-compiled binary image** — faster cold start; image is ROM-able (flat relocation-free blob; dictionary frozen at image-build time; only stacks + user variables need writable RAM) |
| **ROM-able dictionary** | **No** — dictionary built at runtime via heap allocation | **Yes** — only embed has this; zForth/ficl/Atlast all build dictionaries in RAM at startup |
| **Variable-length cells** | ✓ — 30–50% space savings over fixed-size | Fixed 16-bit cells |
| **Maintenance** | Active (2026) | Stable (feature-complete; not actively developed) |

### Where embed wins over zForth

1. **Smallest binary on the real target** — essentially tied with zForth on VM code size (~4–5 KB), but embed's image is pre-compiled, so no Forth bootstrap interpretation at startup.
2. **More complete standard vocabulary** — eForth includes loops, strings, and I/O primitives that zForth's minimal subset omits; authors writing complex game logic get more built-in words for free.
3. **Self-hosting metacompiler** — the standard library can be customized and recompiled from Forth source. zForth has no equivalent.
4. **Best fit for real target hardware** — 16-bit cells match the natural word size of WF's era target hardware (many 16-bit or 32-bit fixed-point systems). The ceiling is a non-issue if mailbox values are fixed-point integers.
5. **ROM-able pre-compiled image (embed only)** — the embed image is a flat, relocation-free binary blob with no internal pointers that need patching. The dictionary is frozen at image-build time and can be placed directly in ROM/flash; only the stacks and user variables need writable RAM. None of the other candidates (zForth, ficl, Atlast) have this property — they all build their dictionaries in heap RAM at startup.

### Practical verdict

| Context | Recommendation |
|---------|---------------|
| PC dev work (float mailboxes) | **zForth** — 32-bit cells handle floats without surprises |
| Real target (fixed-point mailboxes) | **embed** — 16-bit cells match hardware; correct by design; smaller cold start |
| Long/complex scripts with many helper words | **zForth or ficl** — no 128 KB ceiling |
| Absolute minimum binary on real target | **embed** (`WF_FORTH_ENGINE=embed`) |

---

## Example snowgoons scripts (identical across all six backends)

**Player** (forward joystick input to input mailbox):
```forth
\ wf
INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox
```

**Director** (switch camshot based on trigger mailboxes):
```forth
\ wf
: ?cam ( mb -- ) read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then ;
100 ?cam  99 ?cam  98 ?cam
```

Because all backends register `read-mailbox` and `write-mailbox` as named words and share the same `constant` mechanism, the same script source runs on any backend. (embed note: on PC dev, float mailbox values are truncated to 16-bit int; on the real fixed-point target this is correct.)

---

## Implementation phases

### Phase 1 — Vendor all six engines ✓ DONE

#### zForth — `engine/vendor/zforth-41db72d1/`
Commit `41db72d165c1539d57f3f79970fc57ea881a79dc` from https://github.com/zevv/zForth
Core source at `src/zforth/zforth.c` and `src/zforth/zforth.h`.
SHA256 of archive: `34c578ec2aa979786387e5f244fa933b6b040f9a6f18888ed2cc4273ef06df8d`

#### ficl — `engine/vendor/ficl-3.06/`
Tag `ficl306` (commit `7ff58de370ffdfc066daceffbcd2341ae07235a5`) from https://github.com/jwsadler58/ficl
SHA256 of archive: `ac3bc105cab8f770dfbc2b3bcd7ca258da25cae638e790d9b0f07dc3976ebbe7`

#### Atlast — `engine/vendor/atlast-08ff0e1a/`
Commit `08ff0e1aa90310e401510e843540786ac97d2f4f` from https://github.com/Fourmilab/atlast
Source at `atlast-64/atlast.c` and `atlast-64/atlast.h` (64-bit variant; `atlast-32/` also present).
SHA256 of archive: `807ac62e966e6dc11f3e360beceb670103ddb6542766e204c80c11650e311e10`

#### embed — `engine/vendor/embed-154aeb2f/`
Commit `154aeb2faba01106c2324fb7b46cf5fe236e6a81` from https://github.com/howerj/embed
SHA256 of archive: `4312df38dc216c65d8acb2aec96c73c63657c22657504802d311061af21861c6`

#### libforth — `engine/vendor/libforth-b851c6a2/`
Commit `b851c6a25150e7d2114804fc8712664c6d825214` from https://github.com/howerj/libforth
SHA256 of archive: `26271b77ef930799e399157d65f50f6dc2c44149314d5f206c852bd2639669bc`

#### pForth — `engine/vendor/pforth-63d4a418/`
Commit `63d4a4181b39dda123bd63fed4c56bc8e3d47b1c` from https://github.com/philburk/pforth
Source in `csrc/`; Forth bootstrap files in `fth/`.
SHA256 of archive: `239a32e02cacc3b52702b939a59c4eca599cb23eac2052055d819736aa22e218`

Rows added to `engine/vendor/README.md`. ✓

### Phase 2 — Plug header (shared ABI)

**New file:** `wftools/engine/stubs/scripting_forth.hp`

```cpp
#pragma once
#ifdef WF_ENABLE_FORTH

class MailboxesManager;
struct IntArrayEntry;

namespace forth_engine {
    void  Init(MailboxesManager& mgr);
    void  Shutdown();
    void  AddConstantArray(IntArrayEntry* entryList);
    void  DeleteConstantArray(IntArrayEntry* entryList);  // no-op (dict not shrunk)
    float RunScript(const char* src, int objectIndex);
}

#endif // WF_ENABLE_FORTH
```

This header is identical regardless of which backend is compiled in. `ScriptRouter` in `scripting_stub.cc` only ever sees this interface.

### Phase 3 — Per-backend implementation files ✓ DONE

#### `scripting_zforth.cc` (zForth backend)

```cpp
#include "scripting_forth.hp"
#include "zforth.h"
// ... (MailboxesManager include)

static MailboxesManager* g_mgr    = nullptr;
static int               g_curObj = 0;
static zf_ctx            g_ctx;

zf_result zf_host_sys(zf_ctx* ctx, zf_syscall_id id, const char*) {
    switch (id) {
        case ZF_SYSCALL_CUSTOM + 0: {          // read-mailbox
            zf_cell idx; zf_pop(ctx, &idx);
            zf_push(ctx, g_mgr->ReadMailbox((int)idx, g_curObj));
            return ZF_OK; }
        case ZF_SYSCALL_CUSTOM + 1: {          // write-mailbox
            zf_cell val, idx;
            zf_pop(ctx, &val); zf_pop(ctx, &idx);
            g_mgr->WriteMailbox((int)idx, (float)val, g_curObj);
            return ZF_OK; }
        default: return ZF_ABORT_INTERNAL_ERROR;
    }
}

void forth_engine::Init(MailboxesManager& mgr) {
    g_mgr = &mgr;
    zf_init(&g_ctx, 0);
    zf_bootstrap(&g_ctx);
    zf_eval(&g_ctx, ": read-mailbox 0 sys ; : write-mailbox 1 sys ;");
}
void forth_engine::Shutdown() {}
void forth_engine::AddConstantArray(IntArrayEntry* e) {
    std::string s;
    for (; e->name; ++e) s += std::to_string(e->value) + " constant " + e->name + "\n";
    zf_eval(&g_ctx, s.c_str());
}
void forth_engine::DeleteConstantArray(IntArrayEntry*) {}  // dict is append-only
float forth_engine::RunScript(const char* src, int objectIndex) {
    g_curObj = objectIndex;
    // skip past sigil line (\ ...\n)
    while (*src && *src != '\n') ++src;
    if (*src == '\n') ++src;
    if (zf_eval(&g_ctx, src) != ZF_OK) return 0.0f;
    zf_cell result = 0;
    if (zf_stack_len(&g_ctx) > 0) zf_pop(&g_ctx, &result);
    return (float)result;
}
```

#### `scripting_ficl.cc` (ficl backend)

```cpp
#include "scripting_forth.hp"
#include "ficl.h"

static MailboxesManager* g_mgr    = nullptr;
static int               g_curObj = 0;
static ficlSystem*       g_sys    = nullptr;
static ficlVm*           g_vm     = nullptr;

static void ficl_read_mailbox(ficlVm* vm) {
    int idx = ficlStackPopInteger(vm->dataStack);
    ficlStackPushFloat(vm->dataStack, g_mgr->ReadMailbox(idx, g_curObj));
}
static void ficl_write_mailbox(ficlVm* vm) {
    float val = ficlStackPopFloat(vm->dataStack);
    int idx   = ficlStackPopInteger(vm->dataStack);
    g_mgr->WriteMailbox(idx, val, g_curObj);
}

void forth_engine::Init(MailboxesManager& mgr) {
    g_mgr = &mgr;
    g_sys = ficlSystemCreate(NULL);
    g_vm  = ficlSystemCreateVm(g_sys);
    ficlBuild(g_sys, "read-mailbox",  ficl_read_mailbox,  FICL_WORD_DEFAULT);
    ficlBuild(g_sys, "write-mailbox", ficl_write_mailbox, FICL_WORD_DEFAULT);
}
void forth_engine::Shutdown() {
    if (g_vm)  ficlVmDestroy(g_vm);
    if (g_sys) ficlSystemDestroy(g_sys);
}
void forth_engine::AddConstantArray(IntArrayEntry* e) {
    std::string s;
    for (; e->name; ++e) s += std::to_string(e->value) + " constant " + e->name + "\n";
    ficlVmEvaluate(g_vm, s.c_str());
}
void forth_engine::DeleteConstantArray(IntArrayEntry*) {}
float forth_engine::RunScript(const char* src, int objectIndex) {
    g_curObj = objectIndex;
    while (*src && *src != '\n') ++src;
    if (*src == '\n') ++src;
    ficlVmEvaluate(g_vm, src);
    return ficlStackDepth(g_vm->dataStack) > 0
        ? ficlStackPopFloat(g_vm->dataStack) : 0.0f;
}
```

#### `scripting_atlast.cc` (Atlast backend)

```cpp
#include "scripting_forth.hp"
#include "atlast.h"

static MailboxesManager* g_mgr    = nullptr;
static int               g_curObj = 0;

static void atlast_read_mailbox() {
    /* Atlast stack: TOS = idx */
    int idx = (int)S0;  Pop;
    Push = (atl_int)g_mgr->ReadMailbox(idx, g_curObj);
}
static void atlast_write_mailbox() {
    /* Atlast stack: TOS = value, NOS = idx */
    float val = (float)S0; Pop;
    int idx   = (int)S0;   Pop;
    g_mgr->WriteMailbox(idx, val, g_curObj);
}

void forth_engine::Init(MailboxesManager& mgr) {
    g_mgr = &mgr;
    atl_init();
    atlDefine("read-mailbox",  atlast_read_mailbox);
    atlDefine("write-mailbox", atlast_write_mailbox);
}
void forth_engine::Shutdown() { atl_fini(); }
void forth_engine::AddConstantArray(IntArrayEntry* e) {
    for (; e->name; ++e) {
        std::string s = std::to_string(e->value) + " constant " + e->name;
        atl_eval(const_cast<char*>(s.c_str()));
    }
}
void forth_engine::DeleteConstantArray(IntArrayEntry*) {}
float forth_engine::RunScript(const char* src, int objectIndex) {
    g_curObj = objectIndex;
    while (*src && *src != '\n') ++src;
    if (*src == '\n') ++src;
    // Atlast requires mutable char* — copy to local buffer
    std::string buf(src);
    atl_eval(buf.data());
    return (float)S0;   // top of stack after eval
}
```

> Atlast's stack API (`S0`, `Pop`, `Push`) uses C macros defined in `atlast.h`. Verify exact names against vendored source — they may differ by release.

### Phase 4 — Dispatch in `ScriptRouter` (`scripting_stub.cc`)

Changes are **identical regardless of backend**; the macro `WF_ENABLE_FORTH` is set by the build system for whichever backend was chosen.

1. Guarded include at top:
```cpp
#ifdef WF_ENABLE_FORTH
#include "scripting_forth.hp"
#endif
```

2. In `ScriptRouter::ScriptRouter()` (alongside `lua_engine::Init`, `js_engine::Init`, `wasm3_engine::Init`, `wren_engine::Init`):
```cpp
#ifdef WF_ENABLE_FORTH
    forth_engine::Init(mgr);
#endif
```

3. In `ScriptRouter::~ScriptRouter()` (reverse order):
```cpp
#ifdef WF_ENABLE_FORTH
    forth_engine::Shutdown();
#endif
```

4. In `ScriptRouter::AddConstantArray(entryList)` / `DeleteConstantArray(entryList)`, call the matching `forth_engine::` method under `#ifdef WF_ENABLE_FORTH`.

5. `ScriptRouter::RunScript()` — insert **first**, before the `//wren\n` / `//` / `#` arms (the single-byte `\` is the most specific backslash sigil):
```cpp
#ifdef WF_ENABLE_FORTH
    {
        const char* p = src;
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
        if (*p == '\\') {
            return Scalar::FromFloat(forth_engine::RunScript(src, objectIndex));
        }
    }
#endif
```

### Phase 5 — Build system

**File:** `engine/build_game.sh`

1. Feature-flag declaration (near line 35):
```bash
WF_FORTH_ENGINE="${WF_FORTH_ENGINE:-none}"   # none | zforth | ficl | atlast | embed | libforth | pforth
ZFORTH_DIR="$VENDOR/zforth-<sha8>"
FICL_DIR="$VENDOR/ficl-3.06"
ATLAST_DIR="$VENDOR/atlast-<sha8>"
EMBED_DIR="$VENDOR/embed-<sha8>"
LIBFORTH_DIR="$VENDOR/libforth-<sha8>"
PFORTH_DIR="$VENDOR/pforth-<sha8>"
```

2. Validation + include paths:
```bash
case "$WF_FORTH_ENGINE" in
    none|zforth|ficl|atlast|embed|libforth|pforth) ;;
    *) echo "error: WF_FORTH_ENGINE must be: none | zforth | ficl | atlast | embed | libforth | pforth" >&2; exit 2 ;;
esac
case "$WF_FORTH_ENGINE" in
    zforth)   CXXFLAGS+=(-DWF_ENABLE_FORTH -I"$ZFORTH_DIR")   ;;
    ficl)     CXXFLAGS+=(-DWF_ENABLE_FORTH -I"$FICL_DIR")     ;;
    atlast)   CXXFLAGS+=(-DWF_ENABLE_FORTH -I"$ATLAST_DIR")   ;;
    embed)    CXXFLAGS+=(-DWF_ENABLE_FORTH -I"$EMBED_DIR")    ;;
    libforth) CXXFLAGS+=(-DWF_ENABLE_FORTH -I"$LIBFORTH_DIR") ;;
    pforth)   CXXFLAGS+=(-DWF_ENABLE_FORTH -I"$PFORTH_DIR/src" -I"$PFORTH_DIR/csrc") ;;
esac
```

3. Compilation block (after Wren section):
```bash
case "$WF_FORTH_ENGINE" in
    zforth)
        g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_zforth.cc"  -o "$OUT/stubs__scripting_zforth.o"
        gcc -std=c99 -O2 -w -I"$ZFORTH_DIR" -c "$ZFORTH_DIR/zforth.c" -o "$OUT/zforth__zforth.o"
        OBJS+=("$OUT/stubs__scripting_zforth.o" "$OUT/zforth__zforth.o")
        ;;
    ficl)
        g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_ficl.cc" -o "$OUT/stubs__scripting_ficl.o"
        FICL_SRCS=(ficl.c dictionary.c vm.c stack.c word.c system.c
                   float.c double.c math64.c extras.c fileaccess.c
                   prefix.c search.c softcore.c)
        for c in "${FICL_SRCS[@]}"; do
            gcc -std=c99 -O2 -w -I"$FICL_DIR" -c "$FICL_DIR/$c" -o "$OUT/ficl__${c%.c}.o"
            OBJS+=("$OUT/ficl__${c%.c}.o")
        done
        OBJS+=("$OUT/stubs__scripting_ficl.o")
        ;;
    atlast)
        g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_atlast.cc" -o "$OUT/stubs__scripting_atlast.o"
        gcc -std=c99 -O2 -w -I"$ATLAST_DIR" -c "$ATLAST_DIR/atlast.c" -o "$OUT/atlast__atlast.o"
        OBJS+=("$OUT/stubs__scripting_atlast.o" "$OUT/atlast__atlast.o")
        ;;
    embed)
        g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_embed.cc"  -o "$OUT/stubs__scripting_embed.o"
        gcc -std=c99 -O2 -w -I"$EMBED_DIR" -c "$EMBED_DIR/embed.c" -o "$OUT/embed__embed.o"
        OBJS+=("$OUT/stubs__scripting_embed.o" "$OUT/embed__embed.o")
        ;;
    libforth)
        g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_libforth.cc" -o "$OUT/stubs__scripting_libforth.o"
        gcc -std=c99 -O2 -w -I"$LIBFORTH_DIR" -c "$LIBFORTH_DIR/libforth.c" -o "$OUT/libforth__libforth.o"
        OBJS+=("$OUT/stubs__scripting_libforth.o" "$OUT/libforth__libforth.o")
        ;;
    pforth)
        g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_pforth.cc" -o "$OUT/stubs__scripting_pforth.o"
        PFORTH_SRCS=(pf_cglue.c pf_clib.c pf_core.c pf_forth.c pf_inner.c
                     pf_io.c pf_save.c pf_text.c pf_words.c)
        for c in "${PFORTH_SRCS[@]}"; do
            gcc -std=c99 -O2 -w -I"$PFORTH_DIR/csrc" -c "$PFORTH_DIR/csrc/$c" -o "$OUT/pforth__${c%.c}.o"
            OBJS+=("$OUT/pforth__${c%.c}.o")
        done
        OBJS+=("$OUT/stubs__scripting_pforth.o")
        ;;
    none) : ;;
esac
```

### Phase 6 — Documentation ✓ DONE

**`docs/scripting-languages.md`:** Forth rows updated; "not yet built" text removed
from all five backends. Runtime memory column (`—`) left pending measured values.

To fill in the memory column: measure actual RAM footprint at steady state
(dict + stacks) for each backend analogous to the zForth entry
(`~17 KB` with `ZF_DICT_SIZE=16384`), then update the table rows.

Also add snowgoons player + director Forth scripts to the **reference scripts section** of `docs/scripting-languages.md`, alongside the existing Lua/Fennel/JS/wasm examples:

**Player** (forward raw joystick input to the input mailbox):
```forth
\ wf
INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox
```

**Director** (switch camshot based on trigger mailboxes):
```forth
\ wf
: ?cam ( mb -- ) read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then ;
100 ?cam  99 ?cam  98 ?cam
```

Notes for the `docs/scripting-languages.md` entry:
- The `\ wf` opening line is a standard Forth line comment — zero runtime cost
- `: ?cam ... ;` defines a helper word in the persistent dictionary; on repeated calls (same engine instance) the word is already defined — add a guard or use `FORGET ?cam` before redefining if needed
- All four backends produce identical script syntax; the backend choice is invisible to script authors
- embed note: on PC dev, mailbox float values are truncated to 16-bit int; correct on real fixed-point target

### Phase 7 — Snowgoons demo scripts ✓ DONE

**File:** `scripts/patch_snowgoons_forth.py`

Byte-preserving patcher (no iff.txt recompile). Rewrites the existing Fennel
player + director scripts in place and pads each replacement with trailing
spaces so total byte counts stay identical — `_Common` struct offsets are
fixed so no chunk-size changes, IFF size shifts, or alignment repair are
needed.

- **Player** (76 B script, 77 B slot): `\ wf\nINDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox\n`
- **Director** (225 B script, 439 B slot): three inline `if/else/then`
  blocks for mailboxes 100/99/98. Avoids defining a word per tick (zForth
  dict is append-only).

Script source is engine-agnostic — the same patch works against whichever
backend `WF_FORTH_ENGINE` selects at build time.

Applied to both `wflevels/snowgoons.iff` and `wfsource/source/game/cd.iff`.

---

## Critical files

| File | Action |
|------|--------|
| `engine/vendor/zforth-<sha8>/` | Create |
| `engine/vendor/ficl-3.06/` | Create |
| `engine/vendor/atlast-<sha8>/` | Create |
| `engine/vendor/embed-<sha8>/` | Create |
| `engine/vendor/libforth-<sha8>/` | Create |
| `engine/vendor/pforth-<sha8>/` | Create |
| `engine/vendor/README.md` | Add 6 rows + SHA256s |
| `wftools/engine/stubs/scripting_forth.hp` | Create (shared ABI header) |
| `wftools/engine/stubs/scripting_zforth.cc` | Create |
| `wftools/engine/stubs/scripting_ficl.cc` | Create |
| `wftools/engine/stubs/scripting_atlast.cc` | Create |
| `wftools/engine/stubs/scripting_embed.cc` | Create |
| `wftools/engine/stubs/scripting_libforth.cc` | Create |
| `wftools/engine/stubs/scripting_pforth.cc` | Create |
| `wftools/engine/stubs/scripting_stub.cc` | Add `\` dispatch + lifecycle hooks |
| `engine/build_game.sh` | Add `WF_FORTH_ENGINE` block |
| `docs/scripting-languages.md` | Add 3 Forth rows + reference scripts |
| `scripts/patch_snowgoons_forth.py` | Create patcher |

---

## Verification

1. **Default build (no Forth):** `./engine/build_game.sh` — zero footprint change.
2. **zForth:** `WF_FORTH_ENGINE=zforth ./engine/build_game.sh` — compiles; binary delta ~10 KB.
3. **ficl:** `WF_FORTH_ENGINE=ficl ./engine/build_game.sh` — compiles; binary delta ~100 KB.
4. **Atlast:** `WF_FORTH_ENGINE=atlast ./engine/build_game.sh` — compiles; binary delta ~30 KB.
5. **embed:** `WF_FORTH_ENGINE=embed ./engine/build_game.sh` — compiles; binary delta ~5 KB.
6. **libforth:** `WF_FORTH_ENGINE=libforth ./engine/build_game.sh` — compiles; binary delta ~50 KB.
7. **pForth:** `WF_FORTH_ENGINE=pforth ./engine/build_game.sh` — compiles; binary delta ~120 KB.
8. **Selftest per backend:** eval `\ wf\n42 INDEXOF_INPUT write-mailbox`, confirm mailbox 3024 = 42.
9. **Script portability:** same snowgoons script source runs correctly on all six backends.
10. **Snowgoons integration:** patch Forth scripts into IFF, launch `wf_game`, confirm gameplay.
11. **Polyglot build:** `WF_FORTH_ENGINE=zforth WF_JS_ENGINE=quickjs WF_ENABLE_LUA=1` — all compiled in; sigil dispatch routes correctly for each.

---

## nanoFORTH deep-dive: a surprise port candidate

nanoFORTH (https://github.com/chochain/nanoFORTH, MIT, active v2.2 2024) targets Arduino Nano
but turns out to be much more portable than its row in the survey table suggests. Research
findings after reading the full source:

### The 1 KB figure — what it actually means

The `~1 KB RAM` headline is the **dictionary size** only, and it is a compile-time constant:

```cpp
// n4_core.h line 12
constexpr U16 N4_DIC_SZ = 0x400;   // 1024 bytes — change freely
constexpr U16 N4_STK_SZ = 0x80;    // 128 bytes (64-entry param + return stacks)
constexpr U16 N4_TIB_SZ = 0x80;    // 128-byte input buffer
// Total VM footprint: 1408 bytes
```

Bump `N4_DIC_SZ` to `0x2000` for 8 KB — no other changes needed.

### Linux stubs already exist in the source

The author already anticipated a non-Arduino build. `n4.h` lines 42–59:

```cpp
#if ARDUINO
#include <Arduino.h>
#define log(msg)  Serial.print(F(msg))
// ...
#else  // already there:
#include <cstdio>
#define PROGMEM
#define millis()         10000
#define pgm_read_byte(p) (*(p))
#define log(msg)         ::printf("%s", msg)
extern int Serial;
#endif
```

`n4_core.cpp` has matching `#if ARDUINO / #else` blocks for every I/O function
(`key()`, `d_chr()`, `d_in/out()`, `a_in/out()`). Interrupt handling in `n4_intr.cpp`
already has `_fake_intr()` for the non-Arduino path. EEPROM already falls back to
`mockrom.h` (in-memory array).

### Port effort: ~120 lines across 3 files

| File | What changes | Lines |
|------|-------------|-------|
| `n4_core.cpp` lines 60–112 | Replace `Serial.print` → `printf`; stub GPIO (already stubbed) | ~50 |
| `n4_intr.cpp` | Leave fake ISR as-is, or wire POSIX `setitimer` | 0–30 |
| `CMakeLists.txt` (new) | Build system for Linux | ~20 |
| `n4_asm.cpp` line 15 | EEPROM → already uses `mockrom.h` | 0 |

Total: **~70–120 lines, 2–3 days.**

### C API

Clean embedding API already exists (`nanoFORTH.h`):

```cpp
void n4_setup(const char* code=0, Stream& io=Serial, int ucase=0);
void n4_api(int slot, void (*fp)());   // register C function in slot 0–7
void n4_push(int v);
int  n4_pop();
void n4_run();                         // execute one input line
```

**Limitation:** no `eval(string)` — source is fed through a `Stream&` interface. Workable via a thin `StringStream` wrapper (~20 lines) that makes a `const char*` look like a stream.

**Registering host functions:** slot-based (`n4_api(0, fn)`); called from Forth as `0 API`. Readable but requires defining wrapper words:
```forth
: read-mailbox   0 API ;
: write-mailbox  1 API ;
```

### Architecture

- **Threading model:** subroutine-threaded bytecode (hybrid token/subroutine)
- **Opcode format:** 8-bit opcodes; 1-byte literals (0–127), 3-byte literals (16-bit signed), 12-bit branch addresses
- **Cell width:** 16-bit signed — same constraint as embed; same PC dev float truncation issue; same correctness on real fixed-point target
- **Vocabulary:** ~62 words (50 primitives + immediate words). Similar depth to zForth. Missing: strings, floats, advanced memory ops vs. ANS.

### nanoFORTH vs. zForth after porting

| | nanoFORTH (ported) | zForth |
|-|-------------------|--------|
| Core size | 1.4 KB (configurable) | ~4 KB |
| Cell width | 16-bit | 32-bit (configurable) |
| C host function slots | 8 (fixed) | unlimited via `zf_host_sys()` |
| Eval API | Stream wrapper needed | `zf_eval(ctx, string)` — direct |
| Vocabulary | ~62 words | ~50 words |
| ROM-able | No | No |
| Float on PC dev | truncated to 16-bit | correct (32-bit cell) |
| Maintenance | active (2024) | active (2026) |
| Port effort | 2–3 days | 0 (purpose-built) |
| Standard compliance | custom subset | Forth-83 influenced |

**Verdict:** After porting, nanoFORTH is marginally smaller than zForth but shares
the same 16-bit cell limitation as embed and requires a Stream wrapper that zForth
doesn't need. Not added as a `WF_FORTH_ENGINE` option yet — the port effort isn't
justified when zForth already exists and is smaller to vendor. Revisit if the real-
target footprint of zForth ever becomes a constraint.

---

## Appendix: Disqualified implementations

- **GPL** (gForth, kForth, 4tH, SP-Forth, bigFORTH, amForth) — commercial path closed
- **No C embedding API** (Retro Forth, mecrisp) — not callable in-process; mecrisp is bare-metal only (replaces OS, not portable to hosted environments including phones)
- **Commercial compilers** (SwiftForth, VFX Forth, iForth) — native-code compilers, not per-frame-callable C libraries; don't fit WF's `eval(string)` pattern
- **nanoFORTH** — port is feasible (~120 lines, 2–3 days) but not yet warranted; same 16-bit cell limitation as embed; zForth is smaller to vendor and already purpose-built; revisit if real-target footprint becomes a constraint
