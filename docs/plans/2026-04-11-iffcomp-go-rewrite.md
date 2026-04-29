# Plan: Go rewrite of `wftools/iffcomp`

**Status at time of writing:** Implemented and passing byte-exact tests. This is a post-hoc design memo rather than a forward-looking plan — written because the original request ("now rewrite iffcomp in go") went straight from conversation to code without a plan file. It documents what was built, why each structural decision was made, and what was left out of scope.

## Context

The modernized C++ `iffcomp` (see `sprightly-scribbling-brook.md` and `docs/investigations/2026-04-11-iffcomp-modernization.md`) builds and runs on 2026 Linux, but only after patching 10 upstream files across `pigsys/`, `math/`, and `iffwrite/`, wiring up a missing `wfsource/source/libstrm.inc` file, forcing `SCALAR_TYPE=float` to dodge x86-32 inline asm, and dragging 13 internal static libraries through a recursive make. For a tool whose entire job is "read a small text DSL, write binary bytes," that build chain is wildly out of proportion to the work being done.

A Go rewrite cuts all of that and gives us a self-contained static binary. The companion investigation `docs/investigations/2026-04-11-wftools-rewrite-analysis.md` argues Rust is the preferred rewrite language for this codebase going forward, but the immediate-term choice was Go because (a) the user already picked it in the conversation as the next step, and (b) it serves as a de-risking intermediate step — a working Go version validates the byte-level behavior before Rust gets layered on top.

**Goal.** Produce a Go port of iffcomp that compiles `test.iff.txt` to the exact same 292 bytes as the modernized C++ version. Everything downstream — any Go-specific idiom choices, the CLI shape, the test harness — is in service of that byte-exact requirement. The C++ version stays on disk as the reference oracle.

## Structure

```
wftools/iffcomp-go/
├── go.mod              module decl, no external deps (stdlib only)
├── main.go             CLI: -o=file, -binary|-ascii, -v, -q, positional input
├── iffcomp.go          Compile() library entry + Options struct + Mode enum
├── lexer.go            hand-rolled tokenizer, ~800 lines
├── parser.go           recursive descent, one function per lang.y production
├── writer.go           IffWriterBinary + IffWriterText via mode flag
├── iffcomp_test.go     byte-exact diff tests against C++ oracle (binary + text)
└── testdata/
    ├── test.iff.txt    copied from wftools/iffcomp/
    ├── TODO            referenced by `[ "TODO" ]` inclusion
    ├── expected.iff    C++ IffWriterBinary reference (292 bytes)
    └── expected.iff.txt C++ IffWriterText reference (1214 bytes)
```

**Production-to-function mapping** (each `lang.y` production has a matching function in `parser.go`):

| `lang.y` production | `parser.go` function |
|---|---|
| `statement_list` | `Parse()` |
| `chunk` | `parseChunk()` |
| `chunk_statement` | `parseChunkStatement()` |
| `alignment` | `parseAlignment()` |
| `fillchar` | `parseFillChar()` |
| `expr` | `parseExpr()` |
| `expr_list` | `parseExprList()` |
| `item` | `parseItem()` |
| `state_push` | `parseStatePush()` |
| `string_list` | `parseStringList()` |
| `'[' STRING extractSpec* ']'` | `parseFileInclude()` |
| `extractSpecifier` | `parseExtractSpec()` |
| `chunkSpecifier` | `parseChunkSpecifier()` |
| `.offsetof(...)` | `parseOffsetof()` |
| `.sizeof(...)` | `parseSizeof()` |

`chunk` vs `state_push` disambiguation (both start with `{`) is 2-token lookahead — if the token after `{` is `CHAR_LITERAL`, it's a chunk; otherwise it's a state push. Same as the bison grammar's implicit rule.

**Writer is a single struct with a `text bool` flag.** Every emit method (`outInt8`, `outInt16`, `outInt32`, `outID`, `outString`, `outFixed`, `outFile`, `enterChunk`, `exitChunk`, `align`, `alignFunction`) branches on the flag at entry:

- Binary mode: appends to a `[]byte` buffer, tracks a logical `pos`, maintains a chunk stack with `sizeFieldPos` for end-of-chunk backpatching, and a `map[string]chunkSym` symbol table keyed by `::'A'::'B'` paths (matching the grammar's `chunkSpecifier` format).
- Text mode: appends to a `bytes.Buffer` in the format that `IffWriterText` produces. Ints as `<n>y`/`<n>w`/`<n>l`, reals via `%#.16g` then `(<S>.<W>.<F>)`, strings as `"..."` with `\n` producing the same `\n"` + newline + indent + `"` line-break iostreams did, chunks as `\n<tabs>{ 'ID'` and `\n<tabs>}`.

The single-struct approach is slightly dirtier than two types behind an interface, but keeps the parser code polymorphism-free and lets each emit method's binary/text paths sit next to each other for easy diffing.

## Rust / Go / C++ cross-reference

All three ports mirror the same productions and function names. Cross-reading `wftools/iffcomp/lang.y` against `wftools/iffcomp-go/parser.go` against `wftools/iffcomp-rs/src/parser.rs` should be line-by-line tractable. The test fixtures are deliberately identical — `testdata/test.iff.txt`, `testdata/TODO`, `testdata/expected.iff`, `testdata/expected.iff.txt` — so the byte-exact tests in each language validate against the same C++ oracle.

## Bring-up bugs (two)

Both were lexer disambiguation failures, both were caught by `TestByteExactAgainstCpp` on the first run, both fixed on the first iteration.

### 1. `3(1.15.16)` tokenizes as REAL, not INTEGER

The C++ flex regex is one pattern that handles both "real with optional precision" *and* "bare integer with optional precision" under the same rule:

```
-?(([0-9]*(\.[0-9]+)([eE][+-]?[0-9]+)?)|([0-9]+)){1}(\([0-9]+\.[0-9]+\.[0-9]+\))?
```

Flex longest-match means `3(1.15.16)` is a REAL with integer mantissa, not an INTEGER followed by LPAREN. My initial Go lexer had separate integer and real paths and the integer path didn't know about the trailing `(N.N.N)`.

**Fix:** after parsing a digit-only mantissa, peek for `(`. If it's followed by a well-formed triple and a `)`, reclassify as REAL with that precision. Otherwise roll back (save/restore offset, line, col) and emit INTEGER.

### 2. `.5` is a real number, not a `.keyword` directive

Top-level scan dispatcher routed everything starting with `.` to `scanDotKeyword`. `.5` hit that, tried to look up `5`, failed.

**Fix:** in `scan()`, if the byte after `.` is a digit, route to `scanNumber`. One line.

## Feature scope

**In scope, implemented and tested:**

- Chunk framing with 4-byte FOURCC IDs packed MSB-first
- Back-patched size field on `exitChunk`
- `.sizeof` / `.offsetof` with immediate resolution when the target is already closed, and deferred backpatches when it isn't
- Numeric expressions with `+` and `-` operators
- Fixed-point reals with precision-triple override `(S.W.F)`
- State-push blocks `{ Y … }`, `{ W … }`, `{ L … }`, `{ .precision(…) … }`
- String concatenation via `string_list` (adjacent STRING tokens) — binary mode uses `out_string_continue` with seek-back-over-NUL, text mode emits them as separate quoted literals
- `"..."(N)` padded string literals — binary mode pads with zeros, text mode ignores the size override (matching `IffWriterText`)
- File inclusion with `.start(N)` / `.length(M)` slicing
- `.timestamp`, `.align(N)`, `.fillchar(N)` directives
- `include "file"` and `include <file>` with `WF_DIR` resolution for the system form
- Hex integer literals `$DEADBEEF` with optional `[ywl]` width suffix
- Negative number literals
- C-style string escape translation `\n \t \\ \" \DDD` at `out_string` time (not at lex time — matches iffwrite layering)
- `-ascii` mode byte-exact against `IffWriterText` including the 100-byte `out_file` line-wrap marker

**Out of scope, deliberately:**

- `-v` verbose mode produces rule-entry traces to stderr, not bison's shift/reduce trace. Different debug model but same "what decision did the parser make at each step" utility.
- The `expr MINUS expr` rule is fully wired up to `$1 - $3` in the Go version, where the original C++ grammar left the MINUS action empty (probably an unfinished feature). Two-character change, feature is trivially obvious, but technically a behavior change from the broken original.
- Lexer doesn't capture the current input line text for inclusion in error messages. The original C++ lexer had a `\n.+$` + `yyless(1)` hack to snapshot each line; I dropped it in favor of `%locations`-style filename:line:col reporting. Usually better, but doesn't show the offending source line inline.
- `-v` doesn't flip the parser tracer through the same mechanism the C++ tool used (which was `extern int yydebug; yydebug = 1`). With the bison 3.8 C++ parser class, the modernized C++ tool lost the `-v` flag entirely too; the Go port re-implements it via its own trace hook.

## Test harness

Two Go tests, both byte-exact diffs against artifacts produced by the modernized C++ `iffcomp`:

```go
func TestByteExactAgainstCpp(t *testing.T)  // binary mode, 292 bytes
func TestTextOutputAgainstCpp(t *testing.T) // text mode, 1214 bytes
```

Both `chdir` into `testdata/` so that `[ "TODO" ]` resolves to the local copy of `TODO`, compile via `Compile(..., Options{Mode: Mode...})`, read the reference file, diff byte-by-byte, and on mismatch report the offset and hex context from both buffers.

Regenerating the reference files:

```
cd wftools/iffcomp
make
./iffcomp -binary -o=../iffcomp-go/testdata/expected.iff ../iffcomp-go/testdata/test.iff.txt
./iffcomp -ascii  -o=../iffcomp-go/testdata/expected.iff.txt ../iffcomp-go/testdata/test.iff.txt
```

Adding a new fixture is three steps: commit `testdata/foo.iff.txt`, regenerate `testdata/foo.iff` and/or `testdata/foo.iff.txt`, add a subtest that compiles `foo.iff.txt` with the Go port and diffs against the reference.

## Verification

1. `cd wftools/iffcomp-go && go build ./...` — should compile cleanly (no external deps).
2. `go test ./...` — both byte-exact tests pass.
3. End-to-end CLI sanity: `go build -o /tmp/iffcomp-go . && cd testdata && /tmp/iffcomp-go -o=/tmp/out.iff test.iff.txt && cmp /tmp/out.iff expected.iff` and the same for `-ascii`.
4. Verbose trace: `/tmp/iffcomp-go -v -o=/tmp/out.iff testdata/test.iff.txt 2>&1 | head -20` — should emit `parse: chunk @ …` and `parse: item @ …` lines to stderr.

## Known coverage gaps

Exercised by `test.iff.txt`:

- Chunk framing, reals with default and explicit precision, string concatenation, explicit-width integers, file inclusion.

**Not** exercised, therefore not validated:

- Nested chunks at depth > 1
- `.sizeof` / `.offsetof` back-patches (both immediate-resolve and forward-reference paths)
- `.align(N)` / `.fillchar(N)`
- `.timestamp`
- Hex integer literals `$DEADBEEF`
- Negative number literals
- String escape sequences `\n \t \\ \" \DDD`
- `Y`/`W`/`L` state-push blocks
- `include "file"` / `include <file>`

Every one of these is a free regression test if we commit a fixture that touches it. `.sizeof` / `.offsetof` is the highest-priority coverage gap — it's the most complex part of the writer and the path with the most room for subtle correctness bugs.

## Next steps

1. Wire `wfsource/source/iffwrite/test.scr` into the test harness (two nested chunks, documented expected bytes in the format investigation).
2. Add a fixture exercising `.sizeof` / `.offsetof`.
3. `go test -fuzz` over the lexer — the speculative-rollback paths in `scanNumber` and the string-literal `(N)` size-override parser are the most likely places for future regressions.
4. Commit real `.oas`-derived `.iff.txt` files from `wfsource/source/oas/` as differential testdata.
5. Update `wftools/GNUmakefile` to drive the Go build once test coverage is sufficient to make Go the primary entry point. The C++ version stays on disk and can be rebuilt on demand via its own makefile.
6. Consider lifting `writer.go` into a reusable `worldfoundry-iff` Go package if/when other wftools get ported.
