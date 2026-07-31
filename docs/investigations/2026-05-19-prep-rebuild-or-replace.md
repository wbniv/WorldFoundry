# prep — Rebuild from Source vs. Replace

**Date:** 2026-05-19
**Status:** Path 1 implemented (2026-05-19) — `prep` rebuilt self-contained under `wftools/prep/`: `eval/` restored from `330a23d^` (with committed bison/flex output), `recolib`/`regexp` moved in, `build.sh` repointed. Verified via the OAS→OAD oracle test ([`wftools/oas2oad-rs/tests/oas_to_oad.rs`](../../wftools/oas2oad-rs/tests/oas_to_oad.rs)): all 43 `.oas` reproduce their golden `.oad` byte-for-byte, and prep's `.pp` output matches the canonical [apt.worldfoundry.org](http://apt.worldfoundry.org/) build. The in-repo `prep` binary is now gitignored. Path 3 (Rust rewrite) remains the long-term follow-up.
**Trigger:** `prep` binary's `eval` feature is broken; we need either to fix it (rebuild from source) or retire `prep` in favour of a standard tool such as [GNU m4](https://www.gnu.org/software/m4/) or [GNU cpp](https://gcc.gnu.org/onlinedocs/cpp/). The asset-production pipeline still depends on `prep` for `.oas` → `.oad` compilation, so it cannot simply be dropped.

Related references:

- Production pipeline diagram: [`docs/reference/production-pathway.md`](../reference/production-pathway.md)
- OAS file schema: [`docs/2026-05-03-oas-actor-types.md`](../2026-05-03-oas-actor-types.md)
- Rust caller of `prep`: [`wftools/oas2oad-rs/src/main.rs`](../../wftools/oas2oad-rs/src/main.rs)

---

## TL;DR

| Path | Effort | Risk | Recommendation |
|------|--------|------|----------------|
| **1. Rebuild prep by restoring eval** | ~½ day | Low — eval source still in git history; near-minimum restore is 4 files / ~387 LOC under `wftools/prep/eval/` | **Yes — short term** |
| **2. Replace prep with [m4](https://www.gnu.org/software/m4/) + sed/awk shims** | 3–5 days | Medium — `.oas` macro syntax (`@define`, `@e0()`, `@strcmp`, `@replace` regex) doesn't map 1‑to‑1 onto any standard tool | Candidate for long term |
| **3. Reimplement prep in Rust** | 1–2 weeks | Medium — well-defined input set (~25 `.oas` files, `iff.s` template), all features observed; same path that worked for `iffcomp-rs` / `levcomp-rs` | Best long-term home; needs rebuilt prep as the byte-match oracle |
| **4. Eliminate `.oas` entirely** | many weeks | High — `.oas` is the only authoring path for new actor types; would need a Blender-driven replacement | Out of scope; mention only |

The investigation argues for **Path 1 now, Path 3 later**. Path 2 stays in the back pocket if Path 3 turns out to be harder than expected.

The on-disk `prep` binary still works on tested inputs (`player.oas` via the full `oas2oad-rs` invocation, plus synthetic `@=`, `@e`, `@w` exercises). The actual broken thing is the *rebuild path*, not the runtime evaluator.

---

## 1. Current state of `prep`

### Source tree

The full C++ source is intact at [`wftools/prep/`](../../wftools/prep/):

```
wftools/prep/
├── build.sh        # Linux rebuild script (g++ -std=c++14)
├── CHANGELOG
├── global.hp       (42 LOC)
├── macro.cc        (290 LOC)
├── macro.hp        (67 LOC)
├── prep            # 290 KB binary, built 2026-04-28
├── prep.cc         (209 LOC)  — main, command-line parsing
├── prep.doc
├── prep.hp         (45 LOC)
├── source.cc       (1116 LOC) — macro-expansion engine
├── source.hp       (84 LOC)
├── test
└── TODO
```

Total: **1 853 LOC of C++14**, GPL‑v2 licensed, original copyright Kevin T. Seghetti 1995–2003.

`prep` was **not** purged in the 2026-04-13 "slash & burn" commit (`61761e4`); only its Windows GNUMakefile was deleted. The build script ([`wftools/prep/build.sh`](../../wftools/prep/build.sh)) is dated 2026-04-28 and is the modern Linux replacement for the Watcom toolchain.

### What `prep` does (feature inventory)

Cataloged from [`wftools/prep/source.cc:178-210`](../../wftools/prep/source.cc) (the in-source command reference) and verified against the implementation:

| Feature | Syntax | Notes |
|---------|--------|-------|
| Comments | `@*` … to EOL | Single-line only — no streaming `/* */` |
| Include | `@include filename` | Nested includes, depth limited to 100 |
| Define / Redefine / Undef | `@define NAME value`, `@redefine`, `@undef` | Supports parameters and default values, e.g. `@define TYPEHEADER(displayName,variableName=displayName) …` |
| Conditionals | `@ifdef(NAME)(body)`, `@ifndef(NAME)(body)`, `@if(expr)(body)` | `@if` calls the external expression evaluator |
| Loops | `@w(expr)(body)` | While-loop on arithmetic expression |
| Evaluation | `@=(format)(expr)` | `format` ∈ `{i,f,h,d}` (int / fixed / hex / decimal), optional width 0–9 |
| Nested eval | `@e{0-9}(expr)` | Defers evaluation to a specific `@define` nesting depth |
| String ops | `@uppercase`, `@lowercase`, `@strlen`, `@strcmp` | All in `source.cc` |
| Regex | `@replace(regex)(repl)(body)`, `@search(regex)(body)` | Uses [Henry Spencer regexp](https://github.com/garyhouston/regexp.old) (`wfsource/source/recolib/regexp/`) |
| Whitespace | `@+`, `@-`, `@n`, `@c`, `@@` | Eat fwd / back, emit newline, line concat, literal `@` |
| Special | `@file`, `@line`, `@0`–`@9` | Source-location and ASCII-code emission |
| Output redirection | `@redirectoutput filename`, `@redirectend` | Divert output to file |

That is **substantially more than what cpp does**, and the regex / string operations exceed what m4 ships natively.

### Build dependencies — and the broken one

[`build.sh`](../../wftools/prep/build.sh) compiles `prep` by passing **`.cc` source files directly** to `g++` in one invocation, bundling every dependency into the prep binary. The five source directories under `wfsource/source/` it pulls from:

| Path | State | Used for |
|------|-------|----------|
| `recolib/command.cc`, `infile.cc`, `ktstoken.cc` | ✅ Present | Command-line parsing, file IO, tokeniser |
| `regexp/regexp.cc`, `regsub.cc`, `regerror.cc` | ✅ Present | Henry Spencer regex for `@replace`/`@search` |
| **`eval/expr_tab.cc`, `lexyy.cc`** | ❌ **Deleted 2026-04-15** (commit `330a23d`) | Expression parser called by `@if`, `@w`, `@=` |

The deletion commit message claims:

> Dead expression evaluator (lex/yacc grammar + test harness) — not in any build target, no callers in the game.

That is **incorrect**. There were no callers *in the game*, but `wftools/prep/build.sh:24-25` still wants the lex/yacc-generated outputs. The deletion broke the prep rebuild.

### Anti-pattern: source-files-as-libraries

[`build.sh`](../../wftools/prep/build.sh) admits it in the header comment:

> This replaces the Windows Watcom toolchain and the complex GNUMakefile.tool system (which requires pre-built wfsource libraries).

The original Watcom + `GNUMakefile.tool` flow built three static libraries (`librecolib.a`, `libeval.a`, `libregexp.a`) and linked `prep` against them. The Linux shortcut bypasses library construction and re-compiles every `.cc` from those directories on each `prep` build. Costs:

- **No incremental builds.** Touch any `recolib`/`regexp`/`eval` source and the whole prep rebuilds.
- **Duplicated work the day a second tool wants the same code.** If another `wftools/` binary also needs `recolib`, it gets its own private copy of every `.o` — and the moment two binaries are linked into one process (unlikely here, but real in general), you get ODR violations.
- **Hidden include-path coupling.** `prep` already needs `-I"$WF_SRC"` to find the headers; promoting `recolib`/`regexp`/`eval` to actual library targets would make the dependency explicit at the link line.

This is worth cleaning up while we're already touching the build — see Path 1 step 5 below.

### What was deleted, exactly

`git show 330a23d --stat` shows the 8 files removed:

```
wfsource/source/eval/TODO        |  10 deletions
wfsource/source/eval/eval.h      |   6 deletions
wfsource/source/eval/evaltest.cc |  35 deletions
wfsource/source/eval/expr.h      |  16 deletions
wfsource/source/eval/expr.l      | 174 deletions  (flex source)
wfsource/source/eval/expr.y      | 191 deletions  (bison/yacc grammar)
wfsource/source/eval/fixlex.pl   |   1 deletion
wfsource/source/eval/flexle~1.h  | 175 deletions  (committed-in flex output)
                                     608 lines total
```

All recoverable via `git show 330a23d^:wfsource/source/eval/<file>`.

The `_tab.cc` / `lexyy.cc` files referenced by `build.sh` are **generated** files — produced by [GNU Bison](https://www.gnu.org/software/bison/) from `expr.y` and [flex](https://github.com/westes/flex) from `expr.l`. They were never committed. Anyone rebuilding `prep` was expected to run `bison` and `flex` first, or rely on an old generated copy somewhere. (`flexle~1.h` looks like a checked-in flex header for ancient Watcom toolchains.)

---

## 2. The pipeline that depends on `prep`

### `.oas` is the only remaining input

Confirmed via `find . -name '*.oas'` — all 25 `.oas` files live in [`wfsource/source/oas/`](../../wfsource/source/oas/) along with their `.inc` includes (`actor.inc`, `common.inc`, `xdata.inc`, `mesh.inc`, `flagbloc.inc`, `movebloc.inc`) and the template generator [`iff.s`](../../wfsource/source/oas/iff.s). No `*.oas.in`, no `*.las.in`, no other extensions invoke `prep`.

Historical level-build (`.lev`/`.ini.prp`/`asset.inc` templating) used to go through `prep` too, but those paths have been replaced by [`levcomp-rs`](../../wftools/levcomp-rs/) and [`textile-rs`](../../wftools/textile-rs/) — neither calls `prep`.

### How `prep` is invoked today

[`wftools/oas2oad-rs/src/main.rs:202-241`](../../wftools/oas2oad-rs/src/main.rs) is the sole caller:

```rust
let status = Command::new(&prep_bin)
    .arg(format!("-DTYPEFILE_OAS={stem}"))
    .arg(types_s.file_name().unwrap_or(types_s.as_os_str()))   // iff.s
    .arg(&pp_path)                                              // <stem>.pp
    .current_dir(&types_dir)
    .status()?;
```

The full pipeline is:

```
<stem>.oas ──┐
             │  (prep -DTYPEFILE_OAS=<stem>  iff.s  →  <stem>.pp)
iff.s ───────┤      "iff.s @includes the .oas via the macro"
             │
             ▼
        <stem>.pp        (preprocessed C++ source)
             │
             │  (g++ -c  <stem>.pp  →  <stem>.o)
             ▼
        <stem>.o
             │
             │  (objcopy --dump-section .data=<stem>.oad  <stem>.o)
             ▼
        <stem>.oad       (binary actor descriptor consumed by engine + editor)
```

Without working `prep`, no new actor types can be authored and existing ones cannot be modified (no field additions, default changes, UI-hint edits). The runtime is unaffected: `.oad` is a *build-time* schema consumed by the level compiler ([`levcomp-rs`](../../wftools/levcomp-rs/), formerly [`iff2lvl`](../../wftools/iff2lvl/) — see `level.cc` including `oad.hp`) and by the Blender/Max property-panel UI. The level compiler bakes per-actor field layouts directly into the `.lvl` binary, so the engine never reads a `.oad` file at runtime. `cd.iff` (the asset bundle) contains `GAME`/`TOC`/`SHEL`/`L4`/`RAM` chunks — no `OAD` data. The 10 committed `.oad` files in `wfsource/source/oas/` are enough for every existing level to keep building and running; the production pipeline is frozen only for schema-level changes.

### Example `.oas` (excerpt, [`player.oas`](../../wfsource/source/oas/player.oas))

```c
@define DEFAULT_MASS 50.0
@define DEFAULT_MOBILITY 1
@define DEFAULT_HITPOINTS 1

TYPEHEADER(Player)
  @include actor.inc
  PROPERTY_SHEET_HEADER(Player,1)
  PROPERTY_SHEET_FOOTER
TYPEFOOTER
```

The macros `TYPEHEADER`, `PROPERTY_SHEET_HEADER`, `TYPEENTRYFIXED32(…)` etc. live in [`iff.s`](../../wfsource/source/oas/iff.s) and rely heavily on `@define` with parameters, `@if`, and `@e0()` / `@e1()` nested evaluation.

---

## 3. Path 1: Rebuild prep, self-contained under `wftools/prep/`

### Active vs. inert consumers of the support libraries

`build.sh` pulls `.cc` files from three directories under `wfsource/source/`: `recolib/`, `regexp/`, `eval/`. Checking who else needs them:

| Library | Other directory `#include`-rs | Active build path |
|---------|-------------------------------|-------------------|
| `recolib` | `wftools/iffdump/`, `wftools/iff2lvl/`, `wftools/iffcomp/` | **None** — all three are frozen oracle source with no `build.sh`/`CMakeLists.txt`/`Makefile`; superseded by [`iffcomp-rs`](../../wftools/iffcomp-rs/), [`iffdump-rs`](../../wftools/iffdump-rs/), [`levcomp-rs`](../../wftools/levcomp-rs/) (= LevelCon = iff2lvl per existing project memory) |
| `regexp` | `wftools/regexp/` is a duplicate source copy, not a consumer | **None** |
| `eval` | nobody | **None** — deletion commit was correct about this; only the build script's reference contradicted it |

So `prep` is the **only** active build consumer for all three. The `#include "recolib/..."` lines in the frozen C++ tools are dead paths until someone tries to revive those tools, at which point they consult git history the same way anyone else would.

### Layout: all three libraries move under `wftools/prep/`

Make `prep` self-contained. Final layout:

```
wftools/prep/
├── build.sh          (or CMakeLists.txt)
├── prep.cc, source.cc, macro.cc, *.hp
├── eval/             ← restored from 330a23d^
│   ├── eval.h, expr.h, expr.l, expr.y, evaltest.cc
│   └── (generated) expr_tab.cc, lexyy.cc
├── recolib/          ← moved from wfsource/source/recolib/
│   └── command.cc, infile.cc, ktstoken.cc, *.hp
└── regexp/           ← moved from wfsource/source/recolib/regexp/ (or wftools/regexp/)
    └── regexp.cc, regsub.cc, regerror.cc, *.h
```

Benefits:

- **`prep` is one self-contained directory.** When `prep-rs` (Path 3) lands, the entire `wftools/prep/` retires as one unit — no orphan support libraries left behind in `wfsource/source/` or elsewhere.
- **`wfsource/source/` shrinks** by three directories that were never really engine code — they're tool-side support that ended up under `wfsource/` for historical reasons.
- **No active breakage from the move.** Nothing else builds against these directories. The dead `#include "recolib/..."` lines in frozen oracle C++ tools stay dead either way.

### Near-minimum eval restore

From the original 8-file deletion at commit `330a23d`, restore only what's needed:

| File | Lines | Need? |
|---|---|---|
| `eval.h` | 6 | ✅ public API: `double eval(const char* expr, double (*lookup)(const char*))` |
| `expr.h` | 16 | ✅ internal symbol table |
| `expr.y` | 191 | ✅ [GNU Bison](https://www.gnu.org/software/bison/) grammar |
| `expr.l` | 174 | ✅ [flex](https://github.com/westes/flex) lexer |
| `evaltest.cc` | 35 | optional — keep as a build-time smoke test |
| `flexle~1.h` | 175 | ❌ pre-generated flex output for Watcom; modern flex regenerates |
| `fixlex.pl` | 1 | ❌ obsolete Perl patcher |
| `TODO` | 10 | ❌ historical |

Total restored: **~387 lines / 4 files** (or 422 lines / 5 files with the smoke test), down from 608 lines / 8 files.

### Alternative layout: restore eval into `wfsource/source/eval/`

Simpler diff (literally `git show 330a23d^:… > …` for each file, no path changes in `build.sh`), but `wfsource/source/eval/` returns as a tool-only directory in the engine source tree. The recommended layout above is only marginally more work and produces a cleaner long-term shape.

Near-minimum file set to restore:

| File | Lines | Purpose |
|---|---|---|
| `eval.h` | 6 | Public API: `double eval(const char* expr, double (*lookup)(const char*))` |
| `expr.h` | 16 | Internal symbol-table struct |
| `expr.y` | 191 | [GNU Bison](https://www.gnu.org/software/bison/) grammar — operators, function calls, symbol lookup |
| `expr.l` | 174 | [flex](https://github.com/westes/flex) lexer |
| `evaltest.cc` | 35 | Optional standalone test harness — keep as a build-time smoke test |

Drop from the original 8-file set:
- `flexle~1.h` (175 lines) — pre-generated flex output for Watcom; modern flex regenerates fresh.
- `fixlex.pl` (1 line) — Perl patcher for old flex output; obsolete.
- `TODO` (10 lines) — historical.

Total restored: **~387 lines across 4 files** (or 422 lines / 5 files with the smoke test), down from 608 lines / 8 files. Recovery:

```
mkdir -p wftools/prep/eval
for f in eval.h expr.h expr.l expr.y evaltest.cc; do
  git show 330a23d^:wfsource/source/eval/$f > wftools/prep/eval/$f
done
```

### Sub-path 1b (alternative): restore eval into `wfsource/source/eval/`

Restore at the original location so `build.sh` works without modification. Simpler diff (literally `git show 330a23d^:… > …` per file, plus generate two files with bison/flex), but `wfsource/source/eval/` becomes a tool-only directory living in the engine source tree — a smell that has to be revisited when prep retires.

This is the path of least resistance if the rebuild is urgent and the cleanup is deferred.

### Full step list

1. **Restore eval into `wftools/prep/eval/`:**
   ```
   mkdir -p wftools/prep/eval
   for f in eval.h expr.h expr.l expr.y evaltest.cc; do
     git show 330a23d^:wfsource/source/eval/$f > wftools/prep/eval/$f
   done
   ```

2. **Move recolib and regexp under `wftools/prep/`:**
   ```
   git mv wfsource/source/recolib         wftools/prep/recolib
   git mv wfsource/source/recolib/regexp  wftools/prep/regexp     # adjust if path differs
   ```
   (Verify the actual regexp source location first — there are also `wftools/regexp/` and `wfsource/source/regexp/` candidates.)

3. **Generate `expr_tab.cc` and `lexyy.cc`** from the restored eval sources:
   ```
   cd wftools/prep/eval
   bison -d -o expr_tab.cc expr.y
   flex  -o lexyy.cc expr.l
   ```

4. **Update [`build.sh`](../../wftools/prep/build.sh)** — repoint the `$WF_SRC/{eval,recolib,regexp}/...` paths to local `./eval/`, `./recolib/`, `./regexp/`. Also drop the `-I"$WF_SRC"` and replace with `-I.`.

5. **Run `./build.sh` once** to confirm the rebuild works end-to-end. Expect compilation warnings (1999-vintage C++) but no errors.

6. **Add a regression test.** A small `.oas` snippet exercising `@=f`, `@if`, `@w` plus a golden output. Wire it into CI alongside [`wftools/oas2oad-rs`](../../wftools/oas2oad-rs/)'s existing tests.

7. **(Stretch) Replace `build.sh` with `CMakeLists.txt`.** The current script compiles every dependency `.cc` into one g++ invocation — no incremental builds, no library boundaries. With everything now under `wftools/prep/`, the natural shape is three `add_library(... STATIC ...)` targets (`prep_eval`, `prep_recolib`, `prep_regexp`) linked into the `prep` executable. Optional but the right home if the rebuild stops being a one-shot exercise.

### Estimated effort

Half a day. Most of the time is the regression-test scaffolding, not the fix.

### Risks

- **Lex/yacc-generated output is sensitive to bison/flex versions.** If the existing eval grammar uses constructs that recent bison rejects, the grammar may need cleanup. Modern `bison` warns about deprecated `%pure_parser` directives etc.; usually purely cosmetic.
- **The deletion commit was authored by a previous Claude session.** Be deliberate about *un-deleting*: prefer `git show 330a23d^:<path> > <path>` over `git revert 330a23d`, since the latter touches commit history. The user's standing preference is to fix root causes, not paper over upstream bugs — but here the root cause is the bad deletion, not the deletion-machinery.

### Why this is the right short-term move

The existing `.oas` files are written *to `prep`'s syntax*. Any replacement (Path 2 or 3) has to first reach output-byte parity with a working `prep`. We need a working `prep` regardless, even if only as an oracle.

---

## 4. Path 2: Replace `prep` with a standard tool

### Why this is tempting

`prep` is 1 853 LOC of mid-1990s C++ that links against [Henry Spencer regexp](https://github.com/garyhouston/regexp.old) and a custom lex/yacc evaluator. It is the only tool in the WF tree still written this way. Every other tool has moved to Rust. Carrying `prep` forward means carrying its idiom forward.

### Candidates

#### [GNU m4](https://www.gnu.org/software/m4/)

| `prep` feature | m4 equivalent | Notes |
|----------------|---------------|-------|
| `@include` | `include()` | Direct |
| `@define NAME val` | `define(\`NAME', \`val')` | Direct, quoting differs |
| `@ifdef(N)(B)` | `ifdef(\`N', \`B')` | Direct |
| `@if(expr)(B)` | `ifelse(eval(expr), 1, \`B')` | Combined `eval` + `ifelse` |
| `@= ` arithmetic | `eval()` | Built-in; integer-only by default |
| `@= f(expr)` Q16.16 fixed | `eval(expr * 65536)` | Trivial integer multiply |
| `@uppercase` / `@lowercase` | `translit()` | Available |
| `@strlen` | `len()` | Direct |
| `@strcmp` | `ifelse(s1, s2, \`1', \`0')` | Direct |
| `@replace(re)(rep)(body)` | `patsubst()` | m4 patsubst uses POSIX BRE, not the Henry Spencer dialect — escape risk |
| `@search(re)(body)` | `regexp()` | Same caveat |
| `@w(expr)(body)` while-loop | `forloop`/recursive macro | Not built in; common library macro |
| `@redirectoutput`, `@redirectend` | `divert(N)` / `undivert(N)` | Available, indirect |
| `@n` newline, `@c` line concat, `@+/@-` ws | Manual quoting tricks | Awkward — m4's whitespace model differs sharply |

**Verdict:** m4 covers ~80 % of the surface, but the syntax delta is enormous. Migrating `iff.s` (the master template, ~50 lines of dense macro) is straightforward; migrating every actor `.oas` requires either:

- A two-stage build that runs an `@` → `m4-quoted` transform first, then m4.
- A one-shot rewrite of all 25 `.oas` files plus the 6 `.inc` files to m4 syntax. Possibly merged with cleanup of the OAS authoring docs.

Either way, the result is a stranger codebase to incoming contributors than just fixing `prep`.

#### [GNU cpp](https://gcc.gnu.org/onlinedocs/cpp/)

cpp has `#include`, `#define`, `#ifdef`, `#if`, `__LINE__`, `__FILE__` — and that's where it stops. No string ops, no regex, no arithmetic eval beyond preprocessor-constant expressions, no loops, no output redirection. The `@uppercase`/`@strlen`/`@replace`/`@w` features have **no cpp equivalent**. cpp is out unless we also drop those features from the `.oas` corpus, which appears non-trivial.

#### [GPP — Generic Preprocessor](https://logological.org/gpp)

GPP is the closest spiritual successor to `prep` in the open-source world: configurable delimiters (so you could keep `@`), `#mode quote`, regex via PCRE, arithmetic. It is GPL'd, ~7 KLOC of C, actively maintained on Debian and Homebrew. Likely the smoothest 1-to-1 replacement of any standard tool — but it is also the most obscure, with the smallest community. Adopting GPP just moves the maintenance bus-factor problem one step sideways.

#### [Jinja2](https://jinja.palletsprojects.com/) (Python) or [Handlebars](https://handlebarsjs.com/)

If we're willing to break `.oas` source-compatibility, a templating engine offers richer string ops and obvious extension points. But this is equivalent to rewriting every `.oas` file *and* introducing a Python runtime dependency in the build, which conflicts with the move-everything-to-Rust direction.

### Estimated effort, m4 path

3–5 days, mostly hand-translating `iff.s` and validating that each `.oas` produces a byte-identical `.oad` versus the prep-built oracle.

### Estimated effort, GPP path

2–3 days. Less syntax delta but more "what does this configuration knob mean exactly" research.

---

## 5. Path 3: Reimplement `prep` in Rust (`prep-rs`)

### Sketch

A standalone Rust crate under `wftools/prep-rs/` that re-implements `prep`'s feature set. Architecture:

- **Tokeniser:** Hand-written; the existing `ktsRWCTokenizer` is a thin layer over `std::string` and is easy to mirror with Rust `str::char_indices`.
- **Macro store:** `HashMap<String, Macro>` with parameter lists and default values.
- **Expression evaluator:** [`evalexpr`](https://crates.io/crates/evalexpr) crate, ~3 KLOC of safe Rust, handles arithmetic, function calls, custom symbol-lookup callbacks. Drop-in replacement for the lex/yacc evaluator — no `bison` required.
- **Regex:** [`regex`](https://crates.io/crates/regex) crate, with a translation pass from Henry Spencer dialect (almost identical to POSIX BRE; the surprises are `\(…\)` grouping and `\<`/`\>` word anchors).
- **Output redirection:** Trivial — model as a stack of `Write` sinks.

### Effort

1–2 weeks calendar time. The bulk is regression-testing every existing `.oas` file against the prep-built oracle. With `iffcomp-rs` we did this with `cmp -l` over the `.iff` bytes; same playbook works here for `.oad`.

### Why later, not now

We need a working `prep` first to *act as the oracle*. Path 1 produces that oracle. Once `prep` is rebuilt and the test corpus exists, Path 3 is the natural follow-up — replace `prep` byte-for-byte, then delete the C++ binary.

This is the same pattern that worked for `iffcomp` ([`iffcomp-rs surpassed cpp iffcomp`](../../docs/notes/) — Rust oracle-match first, deviation later).

---

## 6. Why not just retire `.oas`?

`.oas` is the author-facing schema for actor *types* — `Player`, `Goomba`, `Director`, `Platform`. Each `.oas` declares fields with default values, ranges, UI hints (`SHOW_AS_SLIDER`, `SHOW_AS_MAILBOX`, …), and Blender/Max import behaviour (`XDATA_COPY`, `XDATA_OBJECTLIST`). The compiled `.oad` blob is consumed by both the engine (to validate `OAS` instance data in `.iff`) and the level editor (to draw property sheets).

Replacing this pipeline would require:

1. A new schema format (Rust struct + serde derive? YAML? Sticking with C structs but emitting them from a Rust DSL?).
2. New `.oad` emitters in whatever language.
3. Blender-addon changes ([`wftools/wf_blender/`](../../wftools/wf_blender/)) to read the new format for property panels.
4. Engine-side changes to consume the new `.oad` layout — or keep the old one byte-identical, which means re-implementing the field-table format.

That is a multi-week migration of its own, and is out of scope for this investigation. **Mentioned only to head off the suggestion** — if anyone asks "why not just kill `.oas`?", the answer is: yes eventually, but not as a route to fixing the immediate prep-eval bug.

---

## 7. Recommendation

**Do Path 1 now.** Restore `wfsource/source/eval/`, generate `expr_tab.cc`/`lexyy.cc`, rebuild `prep`, fix the ~5-line nested-eval bug, add a regression test, commit.

**Schedule Path 3 as a follow-up.** After `prep` is working again, treat the rebuilt binary as the oracle for a Rust reimplementation. Once `prep-rs` matches byte-for-byte across the entire `.oas` corpus, retire the C++ binary.

**Do not pursue Path 2** unless Path 3 turns out to be unexpectedly expensive. The standard-tools route requires rewriting every `.oas` file *and* keeping a fragile cross-toolchain shim — strictly worse than either fix-it-as-is or full-rewrite-in-Rust.

---

## Appendix A — Files of interest

| Path | Purpose |
|------|---------|
| [`wftools/prep/`](../../wftools/prep/) | prep source + binary + build script |
| [`wftools/prep/source.cc:178-210`](../../wftools/prep/source.cc) | In-source command reference |
| [`wftools/prep/source.cc:623-650`](../../wftools/prep/source.cc) | Nested-eval bug site |
| [`wftools/prep/build.sh`](../../wftools/prep/build.sh) | Build script (references deleted eval/) |
| [`wfsource/source/oas/`](../../wfsource/source/oas/) | All `.oas` and `.inc` files |
| [`wfsource/source/oas/iff.s`](../../wfsource/source/oas/iff.s) | Master template invoked by `prep` |
| [`wfsource/source/oas/iff.s:16`](../../wfsource/source/oas/iff.s) | `@define FIXED32(num) @=f(num)` — concrete eval failure case |
| [`wftools/oas2oad-rs/src/main.rs:202-241`](../../wftools/oas2oad-rs/src/main.rs) | Sole prep caller |
| [`docs/reference/production-pathway.md`](../reference/production-pathway.md) | Full pipeline diagram |
| Commit `330a23d` | `cleanup: remove wfsource/source/eval/` — the bad deletion |
| Commit `330a23d^` | Last commit containing eval source; use as restore target |

## Appendix B — Sources

- [GNU m4 manual](https://www.gnu.org/software/m4/manual/m4.html) — feature surface for the m4 mapping table
- [GNU cpp manual](https://gcc.gnu.org/onlinedocs/cpp/) — feature surface for cpp
- [GPP — Denis Auroux's Generic Preprocessor](https://logological.org/gpp) — configurable-delimiter alternative
- [GNU Bison manual](https://www.gnu.org/software/bison/manual/bison.html) — required for regenerating `expr_tab.cc`
- [flex manual](https://westes.github.io/flex/manual/) — required for regenerating `lexyy.cc`
- [`evalexpr` Rust crate](https://crates.io/crates/evalexpr) — proposed eval replacement for Path 3
- [`regex` Rust crate](https://crates.io/crates/regex) — proposed regex replacement for Path 3
- [Henry Spencer regexp library](https://github.com/garyhouston/regexp.old) — vendored at `wfsource/source/recolib/regexp/`; defines the current regex dialect
