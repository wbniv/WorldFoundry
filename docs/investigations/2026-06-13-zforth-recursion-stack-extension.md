# Extending zForth's recursion (return) stack — implementation & memory footprint

**Date:** 2026-06-13
**Branch:** `2026-new-level`
**Prompted by:** the FSN filesystem-browser level ([plan](../plans/2026-06-12-filesys-browser-level.md)), whose recursive directory-tree layout was pushed into C++ syscalls partly because zForth's return stack is shallow. This asks the inverse question: what would it actually cost to make the return stack deep enough for Forth-native recursion?

---

## TL;DR

- **It's a one-line change** and the footprint is **noise.** The stacks are fixed arrays inside a single, process-global `zf_ctx`; bump `ZF_RSTACK_SIZE` (and, for accumulator-passing recursion, `ZF_DSTACK_SIZE`) in `engine/stubs/zfconf.h`. Going from 64 → 256 each adds **1,536 bytes, once** — 2.3 % of today's `sizeof(zf_ctx)`, and 2.3 % of *one* context because there is exactly one.
- **It is safe.** zForth's inner interpreter is a trampoline, so deep Forth recursion consumes the `rstack[]` **array**, never the C call stack. A bigger array is sufficient; there is no stack-overflow-the-process risk.
- **The premise needed correcting.** The WF build is **not** 32-deep — that's the vendor's unused Linux sample. The real config (`engine/stubs/zfconf.h`) is **64**, with a **64 KB** dictionary.
- **But it would not, by itself, have unblocked the FSN builder.** Return-stack depth is one of *three* coupled walls (shallow rstack · no locals · no float trig). Extending the rstack only relieves the first — and partly the second — and leaves the float-trig wall (`atan2`/`hypot`/`sqrt` for radial layout + connector orientation) fully intact. That wall is why FSN's builder is C++, and a deeper stack doesn't move it.
- **On "native Forth scanner vs. the C++ `sys` word" (§6):** the `sys` boundary isn't a shortcut around real Forth — for a filesystem walk it's the *only representable* boundary, because `zf_cell` is a `float` and zForth has no strings, so OS handles and path strings can't cross into Forth (they must be interned to integer ids C-side). The most-native point reachable without re-architecting is the phase-1 index iterator (`cwd-*`), which Forth already drove. The most-native point *worth* reaching is **layout-policy-in-Forth over a flat numeric node table emitted by C** — hot-reloadable aesthetics, and it sidesteps recursion entirely. Porting the *recursion* into Forth is the only variant that needs this doc's stack bump, and it's the least worth doing.

---

## 1. Where the limit actually lives

The engine compiles zForth against **`engine/stubs/zfconf.h`** (it shadows the vendor's `src/linux/zfconf.h` because the stubs include dir is listed first; the vendor file is never compiled). The live values:

| Knob | `engine/stubs/zfconf.h` | Vendor `linux` sample (unused) |
|------|------------------------:|-------------------------------:|
| `ZF_RSTACK_SIZE` (return stack, **cells**) | **64** | 32 |
| `ZF_DSTACK_SIZE` (data stack, **cells**) | **64** | 32 |
| `ZF_DICT_SIZE` (dictionary, **bytes**) | **65,536** | 4,096 |
| `zf_cell` | `float` (4 B) | `float` (4 B) |
| `zf_addr` | `unsigned int` (4 B) | `unsigned int` (4 B) |

> The stub config's own comment records the history: dict was bumped 16 KB → 64 KB on 2026-05-03 (the Q\*bert MVP's ~150 `INDEXOF`/joystick constants overran 16 KB), and the stacks were raised from the upstream default of 8 to 64.

Both stacks are fixed-size arrays embedded directly in the context struct (`engine/vendor/zforth-41db72d1/src/zforth/zforth.h`):

```c
typedef struct {
    zf_cell rstack[ZF_RSTACK_SIZE];   /* return stack  — the recursion limit  */
    zf_cell dstack[ZF_DSTACK_SIZE];   /* data stack    — the co-limit         */
    uint8_t dict[ZF_DICT_SIZE];       /* dictionary    — dominates the struct */
    zf_input_state input_state;
    zf_addr  ip;
    jmp_buf  jmpbuf;                  /* setjmp target for zf_abort()         */
    char     read_buf[32];
    size_t   read_len;
    char     name_buf[32];
    zf_addr *uservar;                 /* aliased onto dict[] — see §2         */
} zf_ctx;
```

There is **exactly one instance** for the whole engine — `static zf_ctx g_ctx;` (`engine/stubs/scripting_zforth.cc:61`). Every script, every actor's per-frame `zf_eval`, and neural-forth (`nf_init(&g_ctx)`) share it. So whatever a stack bump costs, it is paid **once**, in BSS, not per actor or per frame.

### `sizeof(zf_ctx)` today (measured, x86-64 dev build)

Probe compiled against the real headers (`gcc -I engine/stubs -I .../src/zforth`):

```
sizeof(zf_cell)      = 4
sizeof(zf_addr)      = 4
sizeof(jmp_buf)      = 200      (glibc x86-64; platform-dependent)
rstack bytes         = 256      (64 × 4)
dstack bytes         = 256      (64 × 4)
dict bytes           = 65536
sizeof(zf_ctx) TOTAL = 66336
```

```
zf_ctx memory map (66,336 B)
┌──────────────────────────────────────────────────────────────┐
│ dict[65536]                                            98.80 % │  ← the whole struct, basically
├───────────┬───────────┬─────────┬──────────────────────────────┤
│ rstack256 │ dstack256 │ jmpbuf  │ ip/bufs/uservar*  (≈88 B)     │
│  0.39 %   │  0.39 %   │  0.30 % │                               │
└───────────┴───────────┴─────────┴──────────────────────────────┘
   ^^^^^^^^^^^^^^^^^^^^^^
   the two stacks together are 0.77 % of the context
```

The headline: **the dictionary is the context.** The two stacks combined are under 1 % of it. Any plausible stack enlargement is rounding error next to the 64 KB dict that already ships.

---

## 2. What "recursion depth" actually buys, and why 64 ≠ 64 levels

zForth's inner interpreter (`run()`, `engine/vendor/.../zforth.c:455`) is a **trampoline**, not a recursive evaluator:

```c
static void run(zf_ctx *ctx, const char *input) {
    while (ctx->ip != 0) {
        ...
        if (code < PRIM_COUNT) { do_prim(ctx, code, input); ... }
        else {                          /* a colon (user) word: */
            zf_pushr(ctx, ctx->ip);     /*   save return IP on the RETURN STACK */
            ctx->ip = code;             /*   jump into its body (no C recursion) */
        }
    }
}
```

`PRIM_EXIT` (`;`/end-of-word) does `ctx->ip = zf_popr(ctx)` — pop the saved IP. So **the entire Forth call tree runs in a single C stack frame**; nesting lives in `rstack[]`. Two consequences:

1. **A bigger `rstack[]` is genuinely sufficient** — there is no companion C-stack growth to worry about, and no risk that "deep Forth recursion" blows the process stack. (The only C recursion is a host syscall that re-enters `zf_eval`, which WF scripts don't do mid-recursion.)
2. **The rstack holds the active *call chain*, not the recursion depth.** Each frame contributes:
   - **1 cell** for its saved return IP, **plus**
   - **1 cell per live variable it must preserve across the recursive call.** zForth has **no locals**, so a recursive word carries its parameters on the return stack: `>r >r >r  …recurse…  r> r> r>` (`PRIM_PUSHR`/`PRIM_POPR`, `zforth.c:739`/`744`). The data stack is unusable for this because the recursive call clobbers it.

So for a word like the FSN layout's `build ( x y depth -- )`, **each recursion level costs ≈ 1 (return IP) + 3 (x, y, depth stashed via `>r`) = 4 cells.** With `ZF_RSTACK_SIZE = 64` minus the sentinel/eval frames, that's **≈ 15–16 levels** — which is exactly the shallow ceiling that helped push FSN into C++. The arithmetic, made explicit:

```
usable levels ≈ (ZF_RSTACK_SIZE − sentinel/eval overhead) / (1 + live_vars_per_frame)
             ≈ (64 − 2) / (1 + 3)   ≈ 15      ← FSN's (x, y, depth)
```

A clean **self-tail-recursion with nothing to preserve** approaches the other extreme — ≈ `RSTACK − 2` ≈ 62 levels. Real recursive layout code sits near the pessimistic end because the no-locals wall forces the `>r` stashing. **This couples the two limits:** the shallow rstack hurts *because* there are no locals, and a deeper rstack directly mitigates the no-locals tax.

---

## 3. Implementation

### Option A — bump the `#define` (recommended)

One line each in `engine/stubs/zfconf.h`:

```diff
-#define ZF_DSTACK_SIZE 64
-#define ZF_RSTACK_SIZE 64
+#define ZF_DSTACK_SIZE 256
+#define ZF_RSTACK_SIZE 256
```

This is **complete** — no other code change is needed — and the reasons are worth stating because they're what make it cheap:

- **The arrays auto-size.** `rstack[ZF_RSTACK_SIZE]` / `dstack[ZF_DSTACK_SIZE]` are declared from the macro.
- **The bounds checks auto-track.** Every overflow/underrun guard references the macro directly, e.g. `CHECK(ctx, RSP(ctx) < ZF_RSTACK_SIZE, ZF_ABORT_RSTACK_OVERRUN)` (`zforth.c:189`). Nothing hardcodes `64`. A repo-wide grep confirms the only references to the size macros are the array declarations and these checks.
- **No pointer-width ceiling.** The stack pointers `DSP`/`RSP` are `zf_addr` = `unsigned int` (32-bit), held in the uservar slots (`zforth.c:76-77`). They can already index billions of cells, so raising the array to 256/1k/4k needs **no type change**. (Contrast a hypothetical `uint8_t` SP, where 256 would silently wrap — not the case here.)
- **Single instance ⇒ multiplier of 1.** Because there is one `g_ctx`, the cost is the raw struct delta, not `× actors`.

**Bump both, or just the return stack?** They're independent `#define`s. Recursion *depth* is gated by `ZF_RSTACK_SIZE`; raise `ZF_DSTACK_SIZE` too only if recursive words also accumulate results on the data stack (most non-trivial ones do — e.g. building a list of spawned indices). They cost the same per cell, so raising them together is the simplest defensible choice.

### Option B — dynamic / heap-allocated stacks — *rejected*

Make `rstack`/`dstack` heap pointers sized at `zf_init`. This forks the vendor's flat-struct design (touches `zf_ctx`, `zf_init`, every `DSP`/`RSP` access) for **zero benefit**: the static cost is already trivial, and the single global context means there's nothing to amortize. Not worth carrying a vendor patch.

### Option C — tail-call elimination in the trampoline — *rejected for this purpose*

Teaching `run()` to reuse the current frame on a tail call would make *tail*-recursive words O(1) in rstack. But FSN-style tree recursion is **not** tail recursion — `build` recurses into each child and then keeps going (place files, draw connectors), so the frame is still live after the recursive call. TCO wouldn't help it, and it's an invasive change to vendored code. Skip.

### Option D — keep recursion in C++ — *the status quo, and still correct for FSN*

What FSN actually does. See §5 for why this remains right even with a deeper stack.

---

## 4. Memory footprint

Cost of raising **both** stacks from 64 to `N` cells (`zf_cell` = 4 B), paid **once** in BSS:

```
Δ bytes = 2 × (N − 64) × 4
```

| `N` (each stack) | rstack+dstack | Δ vs current | `sizeof(zf_ctx)` | Δ as % of current ctx | ≈ usable (x,y,depth) levels |
|-----------------:|--------------:|-------------:|-----------------:|----------------------:|----------------------------:|
| **64** (today)   |        512 B  |        —     |      66,336 B    |          —            |  ~15 |
| 128              |      1,024 B  |     +512 B   |      66,848 B    |        +0.77 %        |  ~31 |
| **256**          |      2,048 B  |   +1,536 B   |      67,872 B    |        +2.3 %         |  ~63 |
| 512              |      4,096 B  |   +3,584 B   |      69,920 B    |        +5.4 %         | ~127 |
| 1024             |      8,192 B  |   +7,680 B   |      74,016 B    |       +11.6 %         | ~255 |
| 4096             |     32,768 B  |  +32,256 B   |      98,592 B    |       +48.6 %         | ~1023 |

(Raising only `ZF_RSTACK_SIZE` is exactly half each Δ.)

Reading the table: even a **16×** jump to 1024/1024 — enough for ~255 levels of parameter-passing recursion, far beyond any real directory tree — adds **7.7 KB** to a one-off BSS allocation, ~11 % of a struct whose dictionary is unchanged. It is demand-paged zero memory, touched lazily, never per-frame. **There is no footprint reason to be conservative here**; the only reason to stop short of "huge" is that scripts deep enough to need >256 are better written in C++ anyway (§5).

**Embedded/fixed-point caveat.** The stub comment alludes to "the real fixed-point target." Even there the 64 KB **dict** dominates by ~100×; if memory ever became tight you'd shrink the dictionary long before the stacks register. So the conclusion holds across targets: stack size is not the lever that matters for footprint.

---

## 5. The honest caveat: depth is one wall of three

It would be easy to read this as "so we could have kept the FSN builder in Forth." We could not — and it's worth being precise about why, because it scopes when a stack bump is actually the right tool.

zForth blocks recursive 3D layout on **three coupled limits**:

| Wall | What it blocks | Does a deeper rstack help? |
|------|----------------|----------------------------|
| **Shallow return stack** (this doc) | nesting depth of the call chain | **Yes — directly.** |
| **No locals** | holding `x, y, depth, i…` across a recursive call without `>r` juggling | **Partly** — a deeper rstack absorbs the `>r` stashing the missing locals force, but the code stays awkward and error-prone. |
| **No float `atan2`/`hypot`/`sqrt`** | radial child placement (`R·cosθ`, `R·sinθ`) and connector orientation (`heading = atan2(dy,dx)`, `len = hypot`) | **No — not at all.** |

The third wall is absolute and stack-independent: the connector beams and the radial fan-out are *trigonometric*, and `zf_cell` is a `float` with no trig primitives. No return-stack size makes `atan2` exist. That single fact is sufficient to put the FSN layout/orientation math in C++ (syscalls 136–139 in `scripting_zforth.cc`), independent of how deep the stack is.

**So the value of extending the stack is general headroom, not an FSN unblock:** it makes *moderately* recursive, trig-free scripts (tree walks, nested menus, state machines that `>r`-thread a few parameters) comfortable, and removes a sharp 15-level cliff that's surprising to script authors. It is not a substitute for a C++ syscall when the recursion needs real arithmetic or genuine locals.

---

## 6. Could the scanner be written in native Forth instead of one C++ `sys` word?

This is the inverse design question: today `fsn-build` (sys 137) does the *entire* recursive scan + layout + spawn in C++ and Forth just triggers it. How much of that could move up into the Director `.fth`, and what would it take? The answer reframes the `sys`-word boundary: **it isn't a shortcut that dodged "real" Forth — for this workload it's the only representable boundary, and the code already sits at the most-native point that's actually reachable.**

### The boundary is a dial, and the codebase already has three detents

```
  more C++  ◄─────────────────────────────────────────────►  more Forth
 ┌────────────────────┬──────────────────────────┬──────────────────────┐
 │ MONOLITH           │ INDEX-ITERATOR           │ FULLY NATIVE         │
 │ fsn-build (137)    │ cwd-* (131-135)          │ (hypothetical)       │
 │ one sys call;      │ C owns scan+string+OS;   │ Forth owns the scan  │
 │ all scan/layout/   │ Forth owns the loop &    │ recursion AND the    │
 │ spawn in C++.      │ placement, by integer    │ OS edge.             │
 │ Forth = trigger.   │ index. ← PHASE 1 USED    │ ← NOT REACHABLE      │
 │                    │   THIS.                  │   (see string wall)  │
 └────────────────────┴──────────────────────────┴──────────────────────┘
```

The middle detent already *is* a "native Forth scanner" for the flat case: in phase 1 the Director looped in Forth — `cwd-scan` (`( -- n )`), then per index `cwd-is-dir ( i -- ? )` / `cwd-file-size ( i -- bytes )`, then `spawn-template ( x y z tmpl -- actor )`. Notice every one of those signatures is **purely numeric**. That is the load-bearing observation.

### Why "fully native" is unreachable: the float-cell / no-string wall

`zf_cell` is `float`. zForth has **no string type, no `malloc`, no concat** — only the byte-addressable `dict[]` and two 32-byte scratch buffers. But the OS filesystem edge traffics in exactly the things a float can't hold:

- `opendir`/`readdir`/`lstat` hand back a `DIR*`, a `struct dirent`, a `struct stat` — pointers and structs. A 64-bit pointer does not round-trip through a 32-bit float.
- `fsn_scan` produces `FsnEntry{ std::string name, std::string path, … }`, and the path is built `dir + "/" + name` and **carried through the BFS queue** as `FsnJob{ std::string path, … }`. The recursion's per-node state *is* a string.

So the OS handle and the path strings are intrinsically C-side. The most-native boundary that can exist is therefore *forced* to be exactly what `cwd-*` already is: **C interns the strings/handles behind integer ids; Forth only ever touches numbers.** The index model isn't a convenience — it's the only thing representable.

### What `fsn_spawn_tree` actually is, decomposed

Mapping the real builder (`scripting_zforth.cc:244`) line-class by line-class against "could this be Forth?":

| Part of `fsn_spawn_tree` | Mechanism | Native-Forth-able? |
|--------------------------|-----------|--------------------|
| directory read | `opendir`/`readdir`/`lstat` (`fsn_scan`) | **No** — pointers/structs; must stay C |
| path building & the BFS queue's `path` field | `dir + "/" + name`, `std::string` in `FsnJob` | **No** — the string wall; the algorithm's state is a string |
| radial placement, connector fan | `std::cos` / `std::sin` / `std::atan2` | **No** — zForth has no float trig |
| tower/file heights | `fsn_isqrt` (integer) | Yes (Forth, or a sys word) |
| BFS queue, budget loop, counters | `std::vector<FsnJob>`, `for`, `if depth < max` | Yes — but see the recursion tax |
| spawn / scale / color / connector | already `sys` words | already the boundary |

It comes out roughly **70 % edge work that cannot be Forth** (OS + strings + trig) and **30 % control flow** that could be. And the 30 % is gated on the string-carrying queue: you can't move the loop up while its per-item payload is a `std::string`.

### What it would take to move the 30 % up anyway

The unlock is to make **no string ever cross to Forth** — intern each scanned directory to an integer node-id on the C side, so the recursion's per-node state becomes `(nodeId, x, y, parentX, parentY, depth)`, which is *all numbers* and fits float cells. With that, a native-Forth recursive scanner becomes representable. Concretely you'd add (all still C++ `sys` words — you shrink the bricks, you don't escape C++):

1. **A path-interning node iterator** (a recursion-capable replacement for `cwd-*`), e.g.
   `node-scan ( parentId childIdx -- childId )` · `node-count ( id -- n )` ·
   `node-is-dir ( id i -- ? )` · `node-size ( id i -- bytes )` · `node-mtime ( id i -- t )`.
   ≈ 5 words; the C side holds a node arena keyed by id, Forth never sees a path.
2. **Float math as sys words:** `fcos fsin fatan2 fsqrt fhypot` — ≈ 5 words for the radial/connector trig.
3. The existing `spawn-template` / scale / color / connector words stay.

Then you port the BFS + placement policy into the Director `.fth` — **and immediately hit §2 of this very doc.** The per-node state is 6 values; with no locals you `>r`-stash ~5 of them per level, so at the current 64-deep return stack you get ~10 levels before `ZF_ABORT_RSTACK_OVERRUN`. **The return-stack extension analysed above is a prerequisite for a native scanner, not an optional nicety** — which is the neat link back: the two questions are the same question. (The BFS queue itself becomes a hand-rolled ring buffer in `dict[]` memory — workable *only because*, post-interning, every queued field is numeric.)

### The better shape if you actually want this: port the policy, not the recursion

The only real upside of moving code into Forth here is **hot-reload of the layout aesthetic** — fan angles, radii, the height curve, file caps, the age→color ramp — tunable in the level's `.fth` without an engine recompile. Runtime speed is irrelevant (it's a one-shot build at level load); what you're buying is designer iteration speed on *looks*. But you don't need Forth-side *recursion* to get that. Keep the part that genuinely needs strings + recursion (the tree walk) in C, and have it emit a **flat numeric node table** — one row per node `(id, parentId, depth, x?, y?, childCount, size, mtime)`. Then Forth just **iterates the table** applying the placement formulas (via the trig sys words) and spawning:

```
flat table in C  ──►  Forth loop (no recursion, no >r juggling, no stack bump):
  node-count ( -- n )                 \ rows the C walker produced
  : build  node-count 0 do
      i node-depth  i node-parent  i node-size  …    \ all numbers
      …fcos/fsin placement…  spawn-template  …color…
    loop ;
```

This captures ~all the hot-reload benefit, leaves the unrepresentable work (OS edge, strings, the recursion itself) in C where it belongs, and **needs no return-stack change** because flat iteration has constant call depth. It's strictly better than porting the recursion.

### Verdict

| Approach | New sys words | Needs rstack bump? | Layout hot-reloadable? | Worth it? |
|----------|:-------------:|:------------------:|:----------------------:|-----------|
| Monolith `fsn-build` (today) | 0 | no | no | **default — correct for a fixed aesthetic** |
| Index-iterator, flat (phase-1 `cwd-*`) | 0 (exists) | no | partial (flat only) | good for simple/flat policy |
| **Policy-in-Forth over a flat C node table** | ~5 (trig) + a table-emit word | **no** | **yes** | **the right move *if* live-tunable looks are wanted** |
| Recursion-in-Forth (node iterator) | ~10 | **yes (≥256)** | yes | rarely — most pain, little extra gain |
| "Fully native" (Forth owns the OS edge) | — | — | — | **impossible** (string/pointer wall) |

The `sys`-word boundary the FSN builder uses is not a workaround; it sits where the representability wall is. The most-Forth thing reachable without re-architecting is the phase-1 index iterator. The most-Forth thing *worth* reaching for is **policy-over-a-flat-table**, and notably it sidesteps the recursion stack entirely — the only variant that genuinely wants the stack extension (recursion-in-Forth) is also the one least worth doing.

---

## 7. Recommendation

1. **Raise both stacks to 256** in `engine/stubs/zfconf.h` (`+1,536 B` once, 2.3 % of one context). Cheap, safe, removes the surprising ~15-level cliff, and gives ~63 levels of parameter-passing recursion — comfortably past any real script. Going to 512/1024 is equally defensible if a concrete script wants it; the footprint stays trivial.
2. **Leave the dictionary alone** — it already dwarfs the stacks and isn't the constraint here.
3. **Keep arithmetic-heavy or deeply-recursive layout in C++ syscalls** regardless. The stack bump buys headroom for simple recursion; it does not erase the no-float-trig wall that defines where the C++/Forth boundary belongs.

### Verification (if implemented)

```bash
# 1. probe sizeof before/after the #define change
gcc -I engine/stubs -I engine/vendor/zforth-41db72d1/src/zforth /tmp/zfsize.c -o /tmp/zfsize && /tmp/zfsize
#    expect sizeof(zf_ctx): 66336 (at 64) → 67872 (at 256)

# 2. build the engine; confirm zForth still compiles & bootstraps clean
task build

# 3. a recursive Forth probe that overflows at 64 but survives at 256
#    e.g. a self-recursive countdown that >r-stashes a counter ~30 deep:
#    pre-change → ZF_ABORT_RSTACK_OVERRUN; post-change → runs to completion.
```

---

## References

- zForth VM: `engine/vendor/zforth-41db72d1/src/zforth/zforth.c`, `…/zforth.h`
- WF config (the live one): `engine/stubs/zfconf.h`
- Engine integration / single context: `engine/stubs/scripting_zforth.cc:61` (`g_ctx`)
- FSN builder that took the recursion into C++: [filesys plan, "Phase 2 — implemented"](../plans/2026-06-12-filesys-browser-level.md)
- Upstream project: [zForth on GitHub](https://github.com/zevv/zForth)
