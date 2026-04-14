# Investigation: Replacing the WF Scripting Language

**Date:** 2026-04-14
**Context:** The WF engine has cycled through several scripting languages over its
lifetime — original TCL (never intended to ship), a Scheme-like bytecode interpreter,
Lua, and Perl. With the Linux resurrection underway and TCL currently stubbed out
(`NullInterpreter` at `wftools/wf_viewer/stubs/scripting_stub.cc`), now is the right
time to pick a replacement. This document surveys the field.

## What the scripting system actually needs to do

The `ScriptInterpreter` interface (`wfsource/source/scripting/scriptinterpreter.hp`)
is minimal:

```cpp
class ScriptInterpreter {
    virtual Scalar RunScript(const void* script, int objectIndex) = 0;
    virtual void AddConstantArray(IntArrayEntry* entryList);
    virtual void DeleteConstantArray(IntArrayEntry* entryList);
protected:
    MailboxesManager& _mailboxesManager;
};

ScriptInterpreter* ScriptInterpreterFactory(MailboxesManager&, Memory&);
```

Real scripts are tiny. From `wflevels/snowgoons/snowgoons.lev`:

```tcl
# Player script (runs per frame):
write-mailbox $INDEXOF_INPUT [read-mailbox $INDEXOF_HARDWARE_JOYSTICK1_RAW]

# Director script:
if { [read-mailbox 100] } { write-mailbox $INDEXOF_CAMSHOT [read-mailbox 100] }
if { [read-mailbox 99] }  { write-mailbox $INDEXOF_CAMSHOT [read-mailbox 99] }
if { [read-mailbox 98] }  { write-mailbox $INDEXOF_CAMSHOT [read-mailbox 98] }
```

The whole world of WF scripting is **small functions that poke mailboxes**, plus
named integer constants (`$INDEXOF_CAMSHOT` = 1021, etc.) provided by
`AddConstantArray`. Mailboxes are the ABI between game logic and scripts — they
are also language-agnostic, so swapping the language is cheap.

## Requirements

| Requirement | Why |
|-------------|-----|
| Easy C++ embedding | Engine is C++; no Rust/Zig/Go runtime shenanigans |
| Small binary footprint | One script per object, dozens per level; runtime shouldn't dwarf engine |
| Fast per-frame execution | Called on every update tick for every actor with a script |
| GPL-compatible license | Engine is GPL v2 |
| Still actively maintained | Engine revival is a long-term project; pick something with a future |
| Simple host-language bindings | `read-mailbox` / `write-mailbox` + named constants is the whole API |
| Reasonable error messages | Level designers aren't systems programmers |

Non-requirements:
- Heavyweight stdlib (scripts don't do I/O, crypto, networking)
- Advanced type systems
- Concurrency primitives (engine runs scripts on the main thread)
- JIT compilation (scripts are too small to benefit)

## Side-by-side comparison

### Memory budget

The target platform has **2 MB of system RAM** (separate from video RAM), and
the scripting runtime is only one consumer competing with level data, engine
state, physics, audio buffers, and actor state. A realistic budget for the
scripting runtime + baseline heap is **under ~500 KB combined** — and that's
already generous.

Rows struck through below exceed the 2 MB *system* budget outright (either
their baseline RAM alone blows the budget, or the combined code + RAM leaves
too little for the rest of the game to function). Rows that survive the cut
still vary wildly in how much of the budget they consume; the "tight fit"
cluster is called out after the table.

Two separate size measurements matter here and shouldn't be conflated:

- **Code size** — how much the language runtime adds to the linked `wf_game`
  binary. A stripped `.so` / statically-linked library figure. This is what
  you pay once, regardless of how many scripts run.
- **Baseline RAM** — working-set memory cost of a freshly initialised VM with
  no scripts loaded yet. A rough "what does it cost just to exist?" number.
  Small scripts add a few KB on top.

Both depend heavily on build-time configuration (strip unused modules, disable
debug, etc.). Treat the numbers as order-of-magnitude, not exact.

| Speed rank | Lang        | Code size (lib) | Baseline RAM      | Notes |
|------------|-------------|-----------------|-------------------|-------|
| ~~1~~      | ~~OpenJDK~~ | ~~100+ MB~~     | ~~100+ MB~~       | ~~HotSpot JIT fastest in raw; 50× over budget~~ |
| 2          | LuaJIT      | ~500–700 KB     | ~150–250 KB       | Lua 5.1 API frozen; ~1 MB total is half the system budget |
| 3          | WAMR (AOT)  | ~100–500 KB     | ~100 KB–few MB    | AOT modules; only the trimmed configuration fits |
| ~~4~~      | ~~Hermes~~  | ~~~1 MB~~       | ~~2–5 MB~~        | ~~Tuned for React Native; baseline RAM alone exceeds 2 MB~~ |
| ~~5~~      | ~~AngelScript~~ | ~~~600 KB~~ | ~~~100 KB + classes~~ | ~~C++-adjacent syntax defeats the purpose of a scripting layer~~ |
| 6          | QuickJS     | ~500–700 KB     | ~300 KB–1 MB      | Modern ES2020; heap is tunable; tight fit |
| 7          | Wren        | ~100 KB         | ~20–40 KB         | Purpose-built for C embedding; excellent host API |
| 8 (tie)    | Lua 5.4     | ~250–350 KB     | ~30–50 KB         | Default choice; comfortably fits |
| 8 (tie)    | Fennel      | 0 (build-time compiler) | same as Lua | Lisp syntax → Lua bytecode; zero extra runtime cost |
| 10         | wasm3       | ~64 KB          | ~10 KB + module   | Smallest serious WASM runtime; MCU-grade footprint |
| ~~11~~     | ~~Guile (w/JIT)~~ | ~~3–5 MB~~ | ~~10+ MB~~       | ~~Way over budget; LGPL v3 license risk~~ |
| 12         | Squirrel    | ~400 KB         | ~50–200 KB        | Valve-approved; Lua-like with classes; fits |
| ~~13~~     | ~~s7~~      | ~~~500 KB~~     | ~~~500 KB–1 MB~~  | ~~Heap eats 25–50 % of system RAM; Fennel supersedes~~ |
| ~~14~~     | ~~Janet~~   | ~~~500 KB~~     | ~~~200–500 KB~~   | ~~Clojure-esque Lisp; Fennel supersedes~~ |
| ~~15~~     | ~~Duktape~~ | ~~150–250 KB~~  | ~~80–200 KB~~     | ~~ES5 baseline; superseded by QuickJS and JerryScript~~ |
| ~~16~~     | ~~Avian JVM~~ | ~~~1 MB~~     | ~~5–20 MB~~       | ~~RAM alone is 2.5–10× the budget~~ |
| ~~17~~     | ~~Chibi~~   | ~~~200 KB~~     | ~~~200–500 KB~~   | ~~R7RS Scheme; Fennel supersedes~~ |
| ~~18~~     | ~~MicroPython~~ | ~~~100–500 KB~~ | ~~~20–200 KB~~ | ~~Python semantics unsuitable for gameplay scripting~~ |
| 19         | JerryScript | ~60–100 KB      | ~40–80 KB         | Smallest serious JS engine; IoT heritage; fits easily |

### How the speed rank is determined

The **Speed rank** column is a rough ordering (1 = fastest) based on:

- Published language-benchmark comparisons (the shuttered Computer Language
  Benchmarks Game, academic VM papers, the various "N-body / binary-trees /
  spectral-norm" shootouts run against small VMs).
- Whether the runtime has a JIT, an AOT compiler, a bytecode interpreter, or
  a tree-walking interpreter — a coarse but reliable predictor.
- Whether the source language is statically typed (skips per-op type checks)
  or dynamically typed.
- Personal benchmarking experience for the runtimes I've embedded myself.

Big caveats:

- For the **WF workload specifically** (1–3-line mailbox scripts per actor per
  frame), script dispatch overhead is probably not the bottleneck — but this is
  a game, and performance always has a claim. Speed rank is worth tracking even
  if it isn't currently decisive. When in doubt, profile.
- Numbers can swing **2–10×** depending on workload: integer arithmetic vs.
  string processing vs. table allocation vs. GC-heavy object churn can all
  reorder the middle of the list. Treat ties and adjacent ranks as
  interchangeable.
- JIT'd runtimes (LuaJIT, OpenJDK, wasmtime/WAMR-AOT, Hermes) need **warm-up**
  before they're fast. For a game loop that runs the same scripts every frame
  that warm-up is quickly amortised; for one-shot trigger scripts it matters.
- "WAMR (AOT)" means compiled ahead-of-time. WAMR's plain interpreter mode is
  closer to wasm3 in speed.

### Which survivors still eat a big slice of the budget?

Of the rows that survive, three consume a significant fraction of the 2 MB
envelope and leave proportionally less for game state:

- **LuaJIT** (~1 MB total): ~50 % of system RAM. The speed is unmatched but
  the JIT's code pages aren't free.
- **QuickJS** (up to ~1.7 MB in worst case): tight; the heap size is tunable.
- **Janet** (~1 MB total): same tight-fit territory as LuaJIT but slower.

If the memory target tightens further (1 MB or sub-1 MB systems), only the
**comfortable-fit** cluster remains viable: **Lua 5.4 / Fennel, Wren, wasm3,
Squirrel, QuickJS, JerryScript**. Those six (five + Fennel-via-Lua) are the
"always-safe" set for a memory-constrained target.

---

## The candidates

### Tier 1: Obvious choices

#### [Lua 5.4](https://www.lua.org/)
- **License:** MIT. **Footprint:** ~300 KB. **Perf:** fast interpreter; [LuaJIT](https://luajit.org/) 2–10× faster but frozen at 5.1.
- **Syntax fit:** ★★★★★ — **Community:** ★★★★★ — **Embedding:** ★★★★★
- **Pros:** industry standard for game scripting (WoW, Roblox, Garry's Mod, Defold, Love2D). Decades of docs, books, tooling. C API is small and battle-tested. `luaconf.h` lets you strip features. Coroutines are a natural fit for cutscenes / AI tick state.
- **Cons:** 1-indexed arrays famously trip people up. No class system out of the box (just tables + metatables). If you want types, you layer Teal / TypeScript-to-Lua on top.
- **Lineage fit:** WF already ran on Lua once. Safe "re-adopt" path.

#### [Wren](https://wren.io/)
- **License:** MIT. **Footprint:** ~100 KB. **Perf:** comparable to Lua.
- **Syntax fit:** ★★★★ — **Community:** ★★ — **Embedding:** ★★★★★
- **Pros:** designed from scratch for C embedding by Bob Nystrom (author of [*Crafting Interpreters*](https://craftinginterpreters.com/)). Small, clean, class-based, fibers (coroutines). Excellent host API — you bind methods like `foreign static read(box)` and the VM handles marshalling.
- **Cons:** smaller community than Lua. Development tempo has slowed (last release 2022). Less mindshare = fewer modders will already know it.
- **Lineage fit:** none, but the "small language, big embedding story" vibe matches where WF is going.

### Tier 2: Scheme family

#### ~~[s7 Scheme](https://ccrma.stanford.edu/software/snd/snd/s7.html)~~
~~**Excluded:** superseded by Fennel. If you want real Lisp, Fennel gives you macros and S-expression syntax on top of Lua at zero extra runtime cost. s7's advantages (continuations, hygienic macros, numeric tower) don't matter for 3-line mailbox scripts. RAM budget is also tight: s7's default heap eats 25–50 % of system RAM.~~

#### ~~[Chibi-Scheme](https://github.com/ashinn/chibi-scheme)~~
~~**Excluded:** same reasoning as s7. Chibi is the cleaner R7RS implementation, but adds a separate runtime for capabilities WF scripts won't use. Fennel covers the Lisp aesthetic without the cost.~~

#### ~~[Guile](https://www.gnu.org/software/guile/)~~
- ~~**License:** LGPL v3. **Footprint:** multi-MB.~~
- ~~**Pros:** mature (GNU project). Full Scheme with modules, threads, CLOS-like OO.~~
- ~~**Cons:** big. LGPL v3 isn't GPL-v2 compatible without a "plus later versions" clause — **licensing risk for the engine**. Overkill.~~
- **Excluded:** multi-MB RAM footprint blows the 2 MB system-RAM budget, and LGPL v3 is a license-compatibility problem regardless of size.

#### ~~[Janet](https://janet-lang.org/)~~
~~**Excluded:** superseded by Fennel. Janet's Clojure-esque syntax and PEG parser are interesting, but it adds a full separate runtime for features WF scripts won't use. Fennel gives you the Lisp aesthetic on top of Lua at no extra binary cost.~~

#### [Fennel](https://fennel-lang.org/) (Lisp → Lua)

Fennel deserves a longer treatment because it's the strongest "and also" candidate —
the one language on this list that lets you ship Lisp without carrying a second
runtime in the binary.

##### What it is
- **Language:** a Lisp / Scheme-family front-end whose compiler emits Lua source.
- **Author:** [Phil Hagelberg](https://technomancy.us/) (aka `technomancy`). Same person who shepherded [Leiningen](https://leiningen.org/) for Clojure. Started circa 2016.
- **License:** MIT.
- **Runtime footprint:** **zero**. Fennel scripts are compiled to Lua — bytecode or source — and run on the same Lua VM that's already embedded. Nothing new to link.
- **Compiler:** itself a Lua program (~2000 lines of Fennel, self-hosted). Can run inside the same embedded Lua VM that's evaluating gameplay logic, so you can compile Fennel at load time on the target machine. Or compile ahead-of-time with `fennel --compile` and ship `.lua` only.

##### Syntax sketch
```fennel
;; Player input-forwarding script in Fennel
(write-mailbox INDEXOF_INPUT
               (read-mailbox INDEXOF_HARDWARE_JOYSTICK1_RAW))

;; Director script
(each [_ box (ipairs [98 99 100])]
  (let [val (read-mailbox box)]
    (when (> val 0)
      (write-mailbox INDEXOF_CAMSHOT val))))
```

Compare to the equivalent Lua:
```lua
write_mailbox(INDEXOF_INPUT, read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW))

for _, box in ipairs({98, 99, 100}) do
    local val = read_mailbox(box)
    if val > 0 then
        write_mailbox(INDEXOF_CAMSHOT, val)
    end
end
```

Both compile down to the same bytecode. Fennel is not pretending to be a new VM;
it's a reader macro system and a surface syntax choice.

##### Real Lisp features

Fennel implements genuine Lisp macros — `macro`, `macrodebug`, `macrosvar`,
hygiene via gensyms, compile-time code execution. This is the bit that "real
Schemers" will care about:

```fennel
(macro defmailbox [name index]
  `(do (global ,name ,index)
       (fn ,(.. "read-" (tostring name)) [] (read-mailbox ,index))
       (fn ,(.. "write-" (tostring name)) [val] (write-mailbox ,index val))))

(defmailbox CAMSHOT 1021)
(defmailbox INPUT 2005)

;; after expansion: CAMSHOT / read-CAMSHOT / write-CAMSHOT / INPUT / ... all defined
```

Thanks to macros you can build domain-specific forms — `(on-frame ...)`,
`(on-enter-trigger ...)`, `(state-machine ...)` — without the engine learning
anything new. The generated Lua is still boring Lua that existing tooling can
read and debug.

Fennel supports most of what day-to-day Clojure / Scheme code wants:
destructuring in `let` and function argument lists; pattern-style `match`;
threading macros (`->`, `->>`); tail-call-optimised `recur` via Lua's
tail-calls; early-return via `:return` values; anaphoric and hygienic macros;
reader macros via `,`, `,@`, `` ` ``.

What it *doesn't* give you is continuations (Lua doesn't have them), real
multiple dispatch (no runtime MOP), or a persistent immutable data structure
library (there's `:persistent` for some types, or you pull in a library like
`fennel.table` / `persistent-data-structures`).

##### Tooling
- **`fennel`** CLI: `fennel --compile`, `fennel --repl`, `fennel --eval`, `fennel --watch`.
- **`mpm`-style package manager:** no official one, but `leinjacker` / `love-fennel` templates exist. For WF you'd just check `.fnl` files into the levels directory next to the `.iff` assets.
- **[`fnlfmt`](https://git.sr.ht/~technomancy/fnlfmt)** — official formatter. Solves "everyone indents differently."
- **[`fennel-ls`](https://git.sr.ht/~xerool/fennel-ls)** — language server implementing LSP, so VS Code / Emacs / Neovim get completions, go-to-definition, diagnostics.
- **[`Conjure`](https://github.com/Olical/conjure) / `fennel-mode`** — REPL-driven development via editor integration. Evaluate-form-at-cursor with the game still running. This is the Lisp superpower that nobody who's tried it wants to give up.
- **Stacktraces** map back to Fennel source via sourcemaps; you don't debug generated Lua.

##### Community & industry use
- **[TIC-80](https://tic80.com/)** (fantasy console) — Fennel is a first-class scripting choice alongside Lua, JS, [MoonScript](https://moonscript.org/), Wren.
- **[LÖVE2D](https://love2d.org/)** — the most popular Lua game framework; Fennel is a common choice inside it and has idiomatic guides ([`love2d-fennel`](https://gitlab.com/alexjgriffith/min-love2d-fennel)).
- Small indie titles ship with it: *EXAPUNKS*-style hack-and-slash and several TIC-80 jam games. Zachtronics-style studios are the usual suspects.
- Not yet present in AAA engines; that's Lua territory.
- Active mailing list, IRC (`#fennel` on Libera Chat), well-maintained docs at [fennel-lang.org](https://fennel-lang.org/).

##### Embedding in a Lua host
The embedding story is "embed Lua, then load the Fennel compiler." Concretely:

```c
// 1. Start Lua as you would anyway.
lua_State *L = luaL_newstate();
luaL_openlibs(L);

// 2. Load fennel.lua (~60 KB single file, ship it with assets)
//    Equivalent to: fennel = dofile("fennel.lua")
luaL_loadfile(L, "fennel.lua");
lua_pcall(L, 0, 1, 0);
lua_setglobal(L, "fennel");

// 3. Install the Fennel searcher so `require "mything"` can find "mything.fnl"
luaL_dostring(L, "table.insert(package.loaders or package.searchers, fennel.searcher)");

// 4. From now on, either .lua or .fnl sources load via require().
```

If you're paranoid about ship weight, use `fennel --compile` offline and ship
only the generated `.lua`. The engine never sees Fennel at runtime.

##### Why Fennel specifically matches WF's history

WF has been through a "Scheme-like bytecode interpreter" era and a "Lua" era.
Fennel *is* those two eras reconciled: Lispy surface for the authors who liked
that era, Lua machinery underneath for everyone else. You get:

- Exactly one VM to debug, profile, and reason about.
- Two entry-point languages, whose union is exactly what WF has historically
  wanted from a scripting system.
- Zero extra binary footprint — the Fennel compiler is a few tens of KB of Lua
  source that you only need at build time (or at load time if you want hot-swap
  compilation).
- An obvious migration path: the mailbox scripts in existing `.lev` files can
  be machine-rewritten from the old TCL dialect to Fennel (or to Lua) with a
  simple translator. Both targets see the same primitive API.

##### Caveats

- Fennel is still Lua under the hood. `nil` / `false` / empty-table quirks and
  1-indexed arrays are unchanged. If you hated those things in Lua, Fennel
  doesn't fix them.
- The community is small. One-maintainer situation for the core project. This
  matters less because Fennel is a compiler, not a VM — if development froze
  tomorrow you could freeze the compiler, too, and nothing in your shipped
  game would break.
- Lisp parentheses are a non-starter for some level designers. You can't
  have *everyone* writing macros; you need to decide whether Fennel is "the
  official scripting language" or "a power-user surface over Lua."

##### Recommended use

Ship Lua as the official language. Document that `.fnl` is also accepted and
compiled transparently. Power users write Fennel; everyone else writes Lua.
Because the compile step is invisible from the engine's perspective, there
is no binary-size or runtime-complexity penalty for offering both.

- **Lineage fit:** honours both the Scheme-ish and Lua eras simultaneously.
- **Syntax fit:** ★★★★★ — **Community:** ★★★ — **Embedding:** inherits Lua (★★★★★)

### Tier 3: Game-industry embeds

#### Squirrel
- **License:** MIT. Used by Valve (L4D2, CS:GO, Portal 2), Electronic Arts.
- **Syntax fit:** ★★★★ — **Community:** ★★ — **Embedding:** ★★★★
- Lua-like but with classes, static typing hints, stricter semantics. 0-indexed arrays.
- **Con:** main development has stagnated since ~2022.

#### ~~[AngelScript](https://www.angelcode.com/angelscript/)~~
- ~~**License:** zlib. Used by *Overgrowth*, *Ashes of the Singularity*.~~
- ~~C++-like syntax — may appeal to level designers with C/C++ background.~~
- ~~Strong static typing, good C++ binding story (registers directly against C++ function signatures).~~
- ~~**Con:** heavier than Lua; C++-adjacent syntax is verbose for 3-line mailbox scripts.~~
- **Excluded:** the whole point of a scripting language is to *escape* C++ for gameplay. Recreating C++'s type declarations, semicolons, and curly braces in the surface syntax is the opposite of the win.

#### ~~Pawn~~
~~**License:** free (custom). Used by SA-MP modding. C-subset language; bytecode compiled. **Excluded:** C-syntax is the wrong aesthetic for gameplay scripting — the whole point of a scripting layer is to get away from declarations, semicolons, and curly braces. Also niche, small community, tied to Compuphase.~~

### Tier 4: JavaScript

There are half a dozen embeddable JS engines, with very different trade-offs.

#### QuickJS (and QuickJS-ng)
- **Author:** Fabrice Bellard (also wrote FFmpeg, QEMU, TinyCC). **License:** MIT. **Footprint:** ~600 KB. **Standard:** ES2020 + most ES2023 proposals.
- **Syntax fit:** ★★★ — **Community:** ★★★★ — **Embedding:** ★★★
- **Pros:** modern JS without a browser. Small, fast reference counting + cycle detector GC. Compiles to bytecode; can pre-compile scripts offline. Bellard quality, meaning the code is tight. "QuickJS-ng" fork is where active development has migrated.
- **Cons:** JS warts (`==` vs `===`, hoisting, `this`-binding quirks, truthiness surprises). The runtime ships a lot of functionality you don't need (regex, intl, proxies, generators) — most can be compiled out.

#### ~~Duktape~~
~~**License:** MIT. **Footprint:** ~200 KB. **Standard:** ES5.1 + some ES2015. **Excluded:** QuickJS and JerryScript are both better choices — QuickJS for modern syntax, JerryScript for footprint. Duktape's ES5 baseline and slowing release cadence leave it with no niche to own.~~

#### ~~Hermes (Meta / React Native)~~
~~**License:** MIT. **Footprint:** ~1 MB. Modern JS with a strict subset profile. **Excluded:** too heavy for memory-constrained targets, release cadence tied to React Native's roadmap, and tuned for mobile app scripting rather than C++-hosted game loops. QuickJS covers the same JS ground at half the size with no external dependency.~~

#### JerryScript (Samsung / Eclipse Foundation)
- **License:** Apache 2.0. **Footprint:** ~100 KB (smallest of the bunch). **Standard:** ES5.1 with some ES2015.
- **Syntax fit:** ★★★ — **Community:** ★★ — **Embedding:** ★★★
- **Pros:** designed for IoT / microcontrollers — "can JS run in 64 KB RAM" was the goal. Extremely small. Apache 2.0 plays well with GPL.
- **Cons:** performance is modest; ES5-era semantics; community has shifted to QuickJS.

#### ~~[V8](https://v8.dev/) / [JavaScriptCore](https://developer.apple.com/documentation/javascriptcore) / [SpiderMonkey](https://spidermonkey.dev/)~~
- ~~**License:** BSD / LGPL / MPL. **Footprint:** 20–50 MB. **Performance:** world-class JIT.~~
- ~~**Not recommended** for WF. These are built to run web pages; embedding them for a per-frame mailbox poke is like towing a trailer with a Formula 1 car. Binary size alone rules them out.~~
- **Excluded:** 20–50 MB — 10–25× the entire 2 MB system RAM budget.

#### For WF specifically
- **QuickJS** is the one to reach for if JS wins. Modern JS, reasonable size, good embedding API.
- **JerryScript** if footprint is paramount (unlikely for a desktop game engine).
- ~~**Duktape** — superseded by both of the above.~~
- **JS-as-scripting-for-a-3D-game** isn't unheard of (Godot added it as a secondary target; Playdate uses JS-like Pulp scripting) but it's swimming against the current of Lua's dominance.

### ~~Tier 5: Python — MicroPython~~

**Excluded.** Python — in any form (CPython, [MicroPython](https://micropython.org/),
[CircuitPython](https://circuitpython.org/), [RustPython](https://rustpython.github.io/),
Jython, PyPy, Pyodide, etc.) — is off the table. The Python case always
reduced to "lots of people already know Python from other contexts," which
isn't a strong enough reason to anchor a game engine's scripting layer to
Python's semantics (`None`/`False`/`0` muddle, indentation-as-syntax, import
system), ecosystem expectations (`import numpy`), or memory footprint. Lua
and JS cover the "familiar dynamic scripting" need more compactly and with
fewer gameplay-hostile edges.

The overlap with embedded-systems Python (Blender add-ons, Adafruit
CircuitPython boards, scientific-computing notebooks) was the only
interesting angle, and overlap with *other projects* is not by itself a
reason to pick a language for a *game engine*.

~~Remaining Python detail for the record — collapsed, not recommended:~~

- ~~**MicroPython** by Damien George, MIT-licensed, ~100–500 KB. Viper emitter for typed hot loops. Clean C embedding API (`MP_REGISTER_MODULE`, `mp_obj_t`). Bytecode via `mpy-cross`.~~
- ~~The ergonomics win was "huge familiarity pool" — Python is taught everywhere, Blender add-ons use it, designers coming from data science already know it.~~
- ~~The ergonomics loss was indentation-as-syntax (awkward in inline strings in level files), heavier footprint than Lua, `None`/`False`/`0` confusion on top of the same quirks Lua has, and the "I expect `import numpy`" reflex that MicroPython can't satisfy.~~

### ~~Tier 6: JVM languages~~

**Excluded.** No embeddable JVM fits the 2 MB system-RAM budget. The smallest
realistic option ([Avian](https://github.com/ReadyTalk/avian), ~1 MB code +
several MB RAM) is still in the same weight class as running a second copy of
the engine, and full JVMs ([OpenJDK](https://openjdk.org/), [OpenJ9](https://www.eclipse.org/openj9/),
[GraalVM](https://www.graalvm.org/)) are 30–100 MB before you load a class.
The JVM's superpowers (huge type system, rich stdlib, enterprise tooling) are
exactly the features that don't help with three-line mailbox scripts.

Two observations from the JVM investigation are still useful to carry forward:

- **If Lisp-on-a-serious-VM is ever the draw,** [Clojure](https://clojure.org/)
  is the gold standard — but the weight argument above rules it out here. The
  attainable version of that aesthetic is [Janet](https://janet-lang.org/)
  or [Fennel](https://fennel-lang.org/), covered above.
- **A JVM "redesigned for fixed-point math"** would quickly become a new VM,
  not a modified JVM. If deterministic arithmetic is the underlying need,
  [WebAssembly](https://webassembly.org/) (Tier 7) is the better starting
  point — bit-exact integer semantics across platforms, compile fixed-point
  math libraries once from Rust/C and reuse from any script language.

### Tier 7: WebAssembly

WebAssembly is the most architecturally interesting option on this list — it
deserves its own tier rather than a footnote. It's the only candidate that
cleanly dissolves the "one language per game" constraint without paying for
multiple runtimes, and the only one that gives you bit-exact determinism for
free.

##### What WASM actually is
- A stack-machine bytecode with a W3C specification.
- A host-neutral module format (`.wasm`): imports, exports, linear memory, tables, globals.
- Integer ops (`i32.*`, `i64.*`) are **bit-exact across platforms**. Same module, same inputs, same outputs, on any CPU.
- Float ops are IEEE 754 with small documented holes around NaN canonicalisation; the
  ["deterministic profile"](https://github.com/WebAssembly/design/blob/main/Nondeterminism.md)
  proposal tightens those.
- Stringly-typed sandbox: a module can't touch memory the host hasn't given it and can't
  call functions the host hasn't imported. Good fit for "untrusted mod loaded at runtime."
- Hot reload is native: drop in a new `.wasm` file, instantiate, swap.

##### Embedded runtimes

| Runtime | License | Size | Execution | Notes |
|---------|---------|------|-----------|-------|
| **wasm3** | MIT | ~64 KB code, ~10 KB RAM + module | Interpreter (fast for an interpreter) | Works on MCUs. Tiny. By Volodymyr Shymanskyy. |
| **WAMR** (Wasm Micro Runtime) | Apache 2.0 | ~50 KB–1 MB depending on config | Interpreter, fast-interpreter, AOT, JIT | Intel, now Bytecode Alliance. Configurable: strip everything down to tiny, or enable LLVM JIT. |
| **wasmtime** | Apache 2.0 | ~10–30 MB | Cranelift JIT | Bytecode Alliance reference runtime. Fast but fat. |
| **wasmer** | MIT | ~5–20 MB | LLVM / Cranelift / Singlepass | Commercial backer; multiple JIT backends. |
| **wazero** | Apache 2.0 | — | Go-only | Not relevant for C++ host. |
| **wasmi** | Apache 2.0 / MIT | Rust crate | Interpreter | Not relevant for C++ host. |

For WF-style embedding, the relevant choices are **wasm3** (if you want the
absolute smallest embedding footprint) or **WAMR** (if you want AOT
compilation and a path to good performance without linking LLVM). Both are C
libraries with straightforward C++ integration.

##### Source languages that target WASM

This is where WASM becomes especially interesting — it's not one language, it's
*a common back-end for many*:

<small>

| Source lang | Toolchain | Module size (hello-world-ish) | Notes |
|-------------|-----------|-------------------------------|-------|
| **AssemblyScript** | `asc` (npm) | ~1–5 KB | TypeScript-flavoured syntax designed for WASM. Small runtime. Most popular "WASM-first" language. |
| **Rust** | `cargo` + `wasm-bindgen` / `wasm-pack` | ~5–50 KB (with `panic=abort` + `opt-level=z`) | Mature, fast modules, strict typing. |
| **C / C++** | Emscripten, or `clang --target=wasm32` | ~5–30 KB | Can port existing C libraries as scripts. |
| **Zig** | `zig build-lib` | ~1–10 KB | Intentionally tiny output; excellent WASM story. |
| **TinyGo** | `tinygo build` | ~20–100 KB | Go subset that actually produces small WASM. Full Go is too heavy. |
| **Grain** | `grain compile` | ~20–100 KB | Purpose-built for WASM; typed functional language. |
| ~~**Kotlin/Wasm**~~ | Kotlin compiler | 100s of KB (still maturing) | Experimental but Google-backed. Too heavy. |
| ~~**Motoko**~~ | Dfinity | — | Canister-flavoured; too niche. |
| ~~**Virgil**~~ | `v3c` | ~5 KB | Academic but WASM-friendly. |

</small>

So "which language do scripters write in?" and "what runtime does the engine
link?" become two decoupled questions. Link **one** WASM runtime; *per game*
(or even *per script*) choose whichever source language the author prefers.

##### Conspicuous absences: Lua and JS → WASM

The two languages with the strongest "I already know this" gravity — Lua and
JavaScript — are not first-class WASM targets, and that's worth naming.

**"Lua → WASM"** in practice means one of two things:

1. **Compile the Lua *interpreter* to WASM.** `emcc` or `clang --target=wasm32`
   on the ~15k LoC Lua C sources produces a ~150–200 KB Lua VM that runs inside
   the WASM sandbox. You then feed it Lua source the normal way. This works
   fine — [wasmoon](https://github.com/ceifa/wasmoon) and
   [fengari-wasm](https://github.com/fengari-lua/fengari) are reference
   implementations — but it's two layers of interpretation (WASM interprets
   Lua-VM-bytecode, Lua-VM-bytecode interprets your script). Speed is
   noticeably worse than native Lua, and you've paid the WASM runtime cost
   for effectively nothing new.
2. **Compile Lua *source* directly to WASM bytecode.** This doesn't really
   exist as a production option. Lua's dynamic typing, string interning, and
   table semantics don't map onto WASM's typed stack machine without carrying
   an entire Lua runtime along for the ride — at which point you're back at
   option 1. There have been academic attempts and side projects; none are
   widely used.

**"JS → WASM"** has the same shape: you compile QuickJS / Duktape /
JerryScript to WASM (all feasible, all done) and get a JS engine hosted on a
WASM host — the same two-layer structure. Direct "JavaScript source → WASM
module" doesn't exist; [AssemblyScript](https://www.assemblyscript.org/) is
the nearest thing, but it's a strict TypeScript subset designed around WASM's
typed semantics, not a JS compiler.

The shared reason: both Lua and JS are fundamentally *dynamically typed with a
rich runtime*. WASM is fundamentally *statically typed with a minimal
runtime*. You can always put the runtime inside the sandbox, but the
mismatch means there's no free lunch — no "10× faster Lua because WASM."
WASM's performance wins come from compiling languages that already think in
WASM-shaped terms (Rust, C, Zig, AssemblyScript).

Practical consequence for WF: if we pick **Lua**, we embed native Lua; we
don't embed WASM-hosting-Lua. If we pick **WASM**, we pick a *different*
source language (AssemblyScript or Rust) and get WASM's real benefits. The
question "should we use WASM as a universal runtime and run Lua on top of
it?" has a clear answer: **no, that's the worst of both worlds.**

##### The multi-language resolution

Earlier we filed away "multiple scripting languages in one game" as probably
over-engineered. WASM is the version of that idea that *isn't* over-engineered:

- **One runtime linked** (wasm3 or WAMR).
- **Any number of source languages** — AssemblyScript for the artists, Rust
  for the engine programmer's contributed AI, a legacy C module for the
  physics prototype.
- **Identical binding ABI** — every module calls the same `env.read_mailbox`
  / `env.write_mailbox` imports the host defines once.

The "you have to learn three languages to mod this game" downside is still
real — that was always the human cost, not the engineering cost. But at the
engineering level, multi-language becomes close to free.

##### Binding pattern

A concrete sketch of what a gameplay script looks like. Host side (C++):

```cpp
// Register host functions that every WASM module can import.
wasm_runtime_register_natives("env", (NativeSymbol[]){
    {"read_mailbox",  (void*)host_read_mailbox,  "(i)i",  NULL},
    {"write_mailbox", (void*)host_write_mailbox, "(ii)",  NULL},
}, 2);

// Per-script load:
wasm_module_t  m = wasm_runtime_load(wasm_bytes, wasm_size, ...);
wasm_module_inst_t inst = wasm_runtime_instantiate(m, stack, heap, ...);

// Call its exported update() each frame:
wasm_function_inst_t fn = wasm_runtime_lookup_function(inst, "update");
wasm_runtime_call_wasm(env, fn, 1, (uint32_t[]){ actor_index });
```

Script side (AssemblyScript):
```typescript
@external("env", "read_mailbox")  declare function readMailbox(i: i32): i32;
@external("env", "write_mailbox") declare function writeMailbox(i: i32, v: i32): void;

const INDEXOF_INPUT: i32 = 2005;
const INDEXOF_JOYSTICK_RAW: i32 = 3001;

export function update(actorIndex: i32): void {
  writeMailbox(INDEXOF_INPUT, readMailbox(INDEXOF_JOYSTICK_RAW));
}
```

Or the same logic in Rust:
```rust
#[link(wasm_import_module = "env")]
extern "C" {
    fn read_mailbox(i: i32) -> i32;
    fn write_mailbox(i: i32, v: i32);
}

const INDEXOF_INPUT: i32 = 2005;
const INDEXOF_JOYSTICK_RAW: i32 = 3001;

#[no_mangle]
pub unsafe extern "C" fn update(_actor: i32) {
    write_mailbox(INDEXOF_INPUT, read_mailbox(INDEXOF_JOYSTICK_RAW));
}
```

Host sees both as the same `.wasm` module with the same entrypoints.

##### Performance
- **wasm3 interpreter:** roughly 5–10× slower than native C, 2–3× faster than
  Lua interpreter for compute-heavy code. Fine for mailbox poking.
- **WAMR fast-interpreter or AOT:** near-native, comparable to LuaJIT.
- **wasmtime JIT:** native speed on hot code. Overkill for WF scripts.
- **FFI overhead:** each host call (`read_mailbox`) crosses a boundary and
  costs ~10–50 ns in wasm3, less with AOT/JIT. Per-frame scripts aren't
  sensitive to this; extremely chatty scripts would be.

##### Determinism — the fixed-point angle, revisited
This is the answer that the "JVM redesigned for fixed-point" section was
groping toward. WASM gives you:

- **Bit-exact integer math** across all platforms.
- **Deterministic NaN handling** under the proposed deterministic profile
  (and consistent in practice across all mainstream runtimes today).
- A clean starting point for a **fixed-point library** written in Rust or C,
  compiled once to a `.wasm`, reused from every script.

If cross-machine determinism ever matters (netplay, replay, physics in a
deterministic lockstep game), shipping gameplay logic through WASM is a
stronger answer than trying to make every scripter avoid `float`.

##### Ergonomics for inline scripts
Here's where WASM stops being a slam-dunk. The snowgoons player script is
*one line of TCL*. The AssemblyScript version above is 10 lines of source
plus a build step plus a compiler toolchain in the level-build pipeline.

Realistic WF integration would look like this:
- Scripts live in `.ts` (AssemblyScript), `.rs` (Rust), or `.c` source files
  next to level assets, not as inline strings in `.lev`.
- The level build pipeline (`iffcomp`, `prep`) gains an AssemblyScript /
  Rust / C compile step that emits `.wasm` modules into `cd.iff` as
  separate chunks.
- Level data references scripts by asset ID (same model as meshes, textures,
  sounds).

That's a bigger shift than Lua or Fennel, which can ingest inline strings.
It's also a better shift in the long run: scripts become first-class typed
assets with their own build products instead of string literals that
silently break at runtime.

##### Pros & cons summary

**Pros**
- One runtime, many source languages — technical escape valve for "multiple scripting languages."
- Bit-exact cross-platform determinism.
- Strong sandboxing (good for mods).
- AOT-compile scripts ahead of shipping; load fast, small modules.
- Already the de-facto portable-bytecode standard; not going anywhere.
- Hot-reload friendly.
- Future-proof: every language with a WASM backend becomes a WF scripting language for free.

**Cons**
- Compile-step in the pipeline; not a "paste a line of code into a level" model.
- Footprint bigger than Lua at the low end (64 KB wasm3 + per-script overhead vs ~30 KB baseline Lua), though WAMR with compile-time trimming is competitive.
- Debugging WASM is adequate (DWARF source maps exist, browser DevTools-quality debuggers don't exist outside the browser yet).
- Ecosystem optimism > ecosystem maturity in some corners — AssemblyScript is the only "write-it-once-for-WASM" language with real traction, and even it is smaller-community than Lua.

##### Recommended role
Not the default. But the *right* default for a game where any of the following is true:
- Netplay or replay determinism matters (the physics or gameplay has to be bit-exact across machines).
- Mods will be written by contributors who want to use Rust, TypeScript, C, etc. rather than learn a custom scripting language.
- Sandboxing is a hard requirement (untrusted mods loading by default).
- Scripts are big enough to warrant a real build step — AI behaviours, dialogue systems,
  physics-adjacent logic.

For mailbox-level scripting specifically, it's overkill. For "what we might want
in five years," it's the strongest forward-looking option on this list.

### ~~Tier 8: Rust-native embeddables (mentioned for completeness)~~

~~- **Rhai** — Rust embedding for Rust hosts. Not useful for C++ WF.~~
~~- **Mun** — hot-reload-first, Rust native. Not useful for C++ WF.~~
~~- **RustPython / rustpython_compiler** — CPython in Rust. Same story.~~

~~If WF ever Rust-ifies, revisit these.~~

### What "Syntax fit for WF" means

That column is compressing several properties that together decide whether a
language feels awkward or natural when used for the specific job WF's scripts
do. The underlying scripts are:

- **Tiny** — usually 1–3 lines, occasionally up to a dozen.
- **Imperative** — read mailbox, maybe branch, write mailbox.
- **Expression-heavy** — most lines are a single call whose value flows into another.
- **Stored as strings inside level files** — they pass through IFF serialisation, escape sequences, and level editors before they ever run.

Given that workload, a high "syntax fit" score means:

1. **Low ceremony for a 3-line script.** Bare statements at file scope work; no `main()`, no class wrapping, no `package foo;` header, no forced type annotations.
2. **Function-call–oriented surface.** The dominant operation is `write(box, read(otherBox))`. Languages that express that in one natural clause (`(write-mailbox X (read-mailbox Y))` in Lisp; `write_mailbox(X, read_mailbox(Y))` in Lua) score well. Languages that push you toward builder objects or method chains (`Mailbox.get(Y).pipeTo(Mailbox.set(X))`) score worse.
3. **Whitespace-tolerant.** The script will be edited, pasted, and re-serialised by people and tools that don't care about your indentation. Significant-whitespace languages (Python) pay a penalty here — not a fatal one, but real. Bracket/paren-delimited languages shrug it off.
4. **First-class named integer constants.** `INDEXOF_CAMSHOT` needs to be a bareword in scope, not `Mailbox.Index.CAMSHOT` or `com.worldfoundry.mailbox.Index.CAMSHOT`. Anything that forces a module path hurts readability of inline scripts.
5. **Readable by a non-programmer** squinting at the level file in a diff. Too many sigils (`$@%->`), too much static-typing decoration, or too much punctuation and the score drops.

Rough scoring rubric I used:

- ★★★★★ — the script is one expression and reads like English or natural math
  (`write-mailbox INPUT (read-mailbox JOYSTICK)`). Lua, Fennel, LuaJIT, Scheme.
- ★★★★ — similar, but some vocabulary creeps in: method dispatch (`Mailbox.write(...)`),
  optional semicolons, or a keyword you wouldn't need in the Lisp form. Wren,
  Squirrel, Janet, MicroPython.
- ★★★ — works, but feels bulky for a three-liner. JS's function-expression
  weirdness, QuickJS wanting you to think about hoisting.
- ★★ — noticeably awkward. AngelScript needs return types and semicolons and
  parentheses on entry points. Full Java needs a wrapping class.

It's a judgement, not a measurement. Different reviewers will shuffle the
ratings by a star in either direction. The point of the column is to flag
the languages whose surface syntax is actively *fighting* the job, not to
rank the plausible candidates against each other at fine resolution.

### What these numbers actually mean

- **Lua 5.4** is the "you won't notice it's there" benchmark. Under a megabyte
  of code and RAM combined for a typical configuration.
- **Wren** is startlingly small; the design goal was to be small.
- **Scheme implementations** tend to have relatively heavy baseline RAM because
  of symbol interning and initial environment setup — s7 and Chibi want
  ~500 KB–1 MB of heap even before you load anything interesting.
- **JS engines** vary by an order of magnitude. JerryScript is the same class
  of tiny as Wren; QuickJS and Hermes are full JS runtimes. V8 / SpiderMonkey /
  JavaScriptCore weren't included because they start at 10+ MB code and tens of
  MB RAM.
- **JVMs** start at megabytes and go up. Avian is the minimum realistic
  embedded JVM and it's still 10× the weight of Lua on RAM.
- **MicroPython** is competitive on raw footprint with the small JS engines;
  the Python API makes it feel bigger because there's more language to learn.
- **WASM runtimes** are a wildcard — they measure the *runtime* only. The
  size of the `.wasm` modules themselves is separate, and you bring your own
  source language (C, Rust, AssemblyScript), which decides what's in the module.

### Per-script cost (not in table)

Each *running script* adds, roughly:
- **Lua / Fennel:** a few hundred bytes per closure + stack frame.
- **Wren / Squirrel:** similar order.
- **Scheme / Lisp:** more — conses, environments, closures all count.
- **JS:** closures capture their entire scope chain; a script that closes over
  a lot of variables can balloon. Each object carries a hidden class.
- **Python:** every Python object has at least a type pointer + refcount + dict
  overhead; tiny objects are ~60 bytes in MicroPython vs ~30 bytes in Lua.
- **JVM:** class metadata dwarfs your scripts; once loaded the *incremental*
  cost of new scripts can be small.

For WF, with dozens of actors each running three-line scripts, these
per-script costs are negligible under any of the candidates. The only place
they'd matter is a level with hundreds of active scripted objects — primarily
a Scheme / JS concern.

## Mailbox typing: a cross-cutting concern

Mailboxes in WF are **deliberately untyped** — each is a bag of 32 bits that
can mean:

- a plain integer,
- a Scalar (16.16 fixed-point),
- a Scalar stored as IEEE-754 float (under `SCALAR_TYPE_FLOAT` builds),
- an actor index / object reference,
- a packed RGBA colour,
- a bitfield of flags,
- an enum value,
- a button-mask from the input system,
- probably other things we'll invent later.

The engine enforces no type discipline at the mailbox boundary. The "type"
of a given mailbox is a convention between whoever writes to it and whoever
reads from it. `EMAILBOX_CAMSHOT` happens to hold an actor index;
`EMAILBOX_INPUT` holds a joystick-button bitmask; someone could freely
`WriteMailbox(EMAILBOX_CAMSHOT, joystickBits)` and the engine wouldn't
complain — it would just break at the point the camera tried to use a
button bitmask as an actor index.

This matters for the scripting-language choice because different languages
interact with that untyped blob very differently.

### Dynamically typed hosts (Lua, Fennel, JS, Scheme, Squirrel)

The natural fit. `read_mailbox(i)` returns "a number"; the script decides
what it means. Same language call no matter whether the mailbox holds an
integer, a colour, or an actor index.

```lua
-- Lua: everything's just a number until you treat it as something
local actor   = read_mailbox(EMAILBOX_CAMSHOT)
local fixed   = read_mailbox(EMAILBOX_HORIZ_VELOCITY)
local speed   = fixed / 65536   -- interpret 16.16 as float
local colour  = read_mailbox(EMAILBOX_TINT)
local r       = (colour >> 24) & 0xff
```

Pro: the binding is one C function — `i32 read_mailbox(i32)`. No per-type
plumbing. Matches the engine's untyped semantics exactly.

Con: the language doesn't help you. You can extract the red channel of an
actor index and nothing warns you. Good code discipline comes from writing
**typed wrapper helpers** on the script side:

```lua
-- Wrappers provided by the WF scripting SDK
function read_actor(i)  return read_mailbox(i) end
function read_fixed(i)  return read_mailbox(i) / 65536 end
function read_color(i)  return Color.unpack(read_mailbox(i)) end
function write_actor(i, a) write_mailbox(i, a) end
function write_fixed(i, f) write_mailbox(i, math.floor(f * 65536)) end
```

Lisp family gets to do this with macros instead of functions, which means
zero-cost at runtime and lets you write `(on-frame (:camshot a) ...)`
style DSLs.

### Statically typed hosts with zero-cost wrappers (Rust → WASM)

This is the *best* case for mailbox polymorphism, not the worst. Rust's
newtype pattern plus `#[repr(transparent)]` lets you wrap an `i32` in a
distinct type *with no runtime cost*, and the compiler stops you from
mixing them:

```rust
#[repr(transparent)] pub struct ActorId(pub i32);
#[repr(transparent)] pub struct Fixed32(pub i32);
#[repr(transparent)] pub struct Rgba(pub u32);

extern "C" {
    // Low-level bindings the host provides, all i32-shaped
    fn read_mailbox(i: i32) -> i32;
    fn write_mailbox(i: i32, v: i32);
}

// Typed accessors layered on top (monomorphised away at compile time)
pub fn read_actor(i: i32)  -> ActorId  { unsafe { ActorId(read_mailbox(i)) } }
pub fn read_fixed(i: i32)  -> Fixed32  { unsafe { Fixed32(read_mailbox(i)) } }
pub fn read_color(i: i32)  -> Rgba     { unsafe { Rgba(read_mailbox(i) as u32) } }

// Arithmetic on Fixed32, comparisons on ActorId, etc. — all compile-time checked
impl std::ops::Add for Fixed32 { /* ... */ }
```

This is strictly better than the dynamic-language case: same engine-side
binding (one untyped `i32 → i32` function), but now the *script* has a type
system that catches "passed a Color where an ActorId was expected" at compile
time. AssemblyScript can do this too, somewhat less elegantly (it lacks
newtypes; you use class wrappers that have some per-object cost).

### The middle ground: Wren / Squirrel classes

Class-based languages land between the two. You can wrap mailbox values in
classes, but every wrapper is a heap object — a real allocation per read.
For a three-line script that reads one mailbox and writes another, this is
negligible. For a script that pulls dozens of values per frame it adds up.

### Effect on language selection

Honestly, **it's not a differentiator between the surviving candidates** —
every one can handle untyped mailboxes. But the ranking shifts slightly:

- Languages with **zero-cost typed wrappers** (Rust-via-WASM, Fennel via
  macros) raise the correctness floor for free.
- **Straight-dynamic** languages (Lua, JS) rely on convention — the engine
  SDK needs to ship typed helper functions, and humans need to use them.
- **Object-wrapping** languages (Wren, Squirrel) get safer wrappers but pay
  allocations for them.

### What the engine SDK should provide

Whatever scripting language wins, the WF SDK for that language should ship
with a standardised set of typed mailbox accessors:

- `read_actor / write_actor` — actor index
- `read_fixed / write_fixed` — 16.16 fixed-point (or float, depending on
  Scalar build)
- `read_color / write_color` — packed RGBA
- `read_flags / write_flags` — bitfield helpers
- `read_bool / write_bool` — nonzero-is-true convention
- `read_int / write_int` — for the cases that really are just integers

That registry can live in one header file (`mailboxes.h`) or one Lua
module (`mailbox.lua`) and get wrapped for each scripting language. It's
~100 lines of boilerplate per language binding, and it makes scripts
self-documenting — `read_color(EMAILBOX_TINT)` reads better than
`read_mailbox(EMAILBOX_TINT)` and fails loudly if someone swaps the type
later.

### Engine-side alternatives

Two engine-level changes could make mailboxes self-describing:

1. **Tagged mailboxes.** Each mailbox stores `(type_tag, value)`. Runtime
   checks on every read/write, catches type mismatches at runtime.
2. **Typed namespaces.** Split the mailbox index space by type —
   `actor_mailboxes[]`, `color_mailboxes[]`, `fixed_mailboxes[]`, each
   with its own read/write API.

Both would let the engine *and* the scripting runtime agree on a type.
Neither would actually make gameplay scripts simpler than the
wrapper-function approach — the readability payoff is the same, and the
engine churn is real. The wrapper-function SDK is simpler and can be
shipped alongside whatever language is chosen without touching any engine
internals.

## Multiple languages per game?

The user raised this: could we support multiple languages in the same game, even per-object?

Technically trivial: `ScriptInterpreterFactory` already abstracts the language. Each
object's script is stored as a string in the level file and handed to `RunScript()`.
You could dispatch per-object based on a magic prefix (`#!lua` / `#!scheme`), file
extension, or an explicit tag in the OAD.

Practical cost:
- **Binary size**: each runtime you link adds 200 KB – 1 MB.
- **Mental tax**: level designers and modders need to know which language each
  object speaks. Debugging tools need to understand both.
- **Toolchain fragmentation**: syntax highlighting, linter, formatter, language
  server — multiply everything.

**Verdict:** one language per *game* is almost certainly the right ceiling.
`ScriptInterpreterFactory` already lets different games shipping on the WF engine
pick different languages at build time — that flexibility comes for free and
solves the realistic variant of "multiple languages."

## Recommendation

**Primary: Lua 5.4.**

- Safe choice. Engine has used it before. Decades of documentation.
- Tiny (300 KB), fast enough, MIT-licensed, actively maintained.
- `read-mailbox` / `write-mailbox` are trivial C functions to register.
- Coroutines are a good fit for any eventual cutscene / AI scripting.
- Huge pool of people who can write Lua without training.

**If the Scheme itch needs scratching: layer Fennel on top.**

- Fennel compiles to Lua; no runtime cost. Write scripts in `.fnl`, ship the
  compiled `.lua`. Keeps the engine single-runtime while giving authors who
  *want* Lisp the option. `(write-mailbox INPUT (read-mailbox JOYSTICK_RAW))`
  reads naturally.
- This honours both the "Scheme-like bytecode" and Lua eras of WF history without
  doubling down on runtime complexity.

**If we want a cleaner break and a modern design: Wren.**

- Purpose-built for embedding, excellent host API. Smaller and newer than Lua.
- Risk: smaller community; slower release cadence since 2022.

**Not recommended:**

- **TCL** again (excluded from day one).
- **Guile** — LGPL v3 collision with engine GPL v2, plus dependency weight.
- **Perl** — the embedding API (`ExtUtils::Embed`, `perl_parse` / `perl_run`) is actually pleasant; WF used it successfully. The reasons to exclude Perl are different: its sigil-heavy syntax is unfriendly to non-programmers, its community has shrunk to a small, dedicated core, and modern tooling (LSP, formatters, syntax highlighters for embedded contexts) has largely moved on. "Perl is easy to *embed*" and "Perl is the right *language* for gameplay scripts in 2026" are different questions.
- **Pure s7 / Chibi** unless Lisp is a hard requirement — for a team of one, Lua+Fennel
  gives you Lisp when you want it and Lua when you don't.

## Suggested next step

Before committing: stand up a one-afternoon spike where the `NullInterpreter` is
replaced by a `LuaInterpreter` that just executes one hand-ported snowgoons
script (the player joystick-forwarding one). This shakes out the embedding
approach, the mailbox marshalling, and the constant-array registration path. If
that works cleanly, commit to Lua.
