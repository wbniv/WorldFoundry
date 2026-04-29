# Plan: Rust rewrite of `wftools/iffcomp`

**Status at time of writing:** Scaffolding on disk, lexer / parser / writer / test file still to be written, Rust toolchain not yet installed. The user asked for a plan file after I'd already started writing code; this is that plan, capturing the design decisions so the implementation can resume from a clean starting point once the toolchain is in place.

## Context

This is the third port of iffcomp in this session, following the C++ modernization (`sprightly-scribbling-brook.md` → `docs/investigations/2026-04-11-iffcomp-modernization.md`) and the Go rewrite (`iffcomp-go-rewrite-plan.md` → `docs/investigations/2026-04-11-iffcomp-go-rewrite.md`). The Rust port's entire reason to exist is that `docs/investigations/2026-04-11-wftools-rewrite-analysis.md` §5 argues Rust is the right *default* rewrite language for this codebase going forward, and walking through iffcomp first validates that recommendation against a real tool with a real byte-exact oracle before anything more ambitious gets attempted.

**Goal.** A Rust port of iffcomp that produces the same 292 bytes of binary output and same 1214 bytes of text output as the modernized C++ `iffcomp` and the Go port, for the same `test.iff.txt` input. The Go port is the natural reference — the Rust implementation should feel like a faithful translation, not a creative re-imagining, so that any byte-level divergence is obviously a bug and not an "improvement."

## Current state on disk

Already written (at time of this plan):

```
wftools/iffcomp-rs/
├── Cargo.toml              edition 2021, binary + lib, no deps
├── src/
│   ├── error.rs            IffError enum, Pos struct, Result alias
│   ├── lib.rs              compile() entry point, Options, Mode re-export
│   ├── main.rs             CLI wrapper
│   ├── lexer.rs            MISSING
│   ├── parser.rs           MISSING
│   └── writer.rs           MISSING
├── tests/                  (dir exists, no tests yet)
└── testdata/
    ├── test.iff.txt        ✓ (copied from iffcomp-go/testdata/)
    ├── TODO                ✓
    ├── expected.iff        ✓ (292 bytes, binary oracle)
    └── expected.iff.txt    ✓ (1214 bytes, text oracle)
```

The CLI and library surface are already shaped to match the Go version's flag set:

- `compile(in_file, out_file, Options { mode, verbose }) -> Result<usize>`
- `Mode::Binary` / `Mode::Text`
- `main.rs` parses `-o=file`, `-binary`, `-ascii`, `-v`, `-q`, positional input

The three remaining files are where the real work is.

## Structure

Everything mirrors the Go port's file layout and function names 1:1 so cross-reading works. The Rust idioms are where differences appear.

### `src/error.rs` (exists)

One enum, variants for I/O, lex, parse, resolve errors. `Pos { filename, line, col }` struct shared by lex and parse errors. `Display` + `std::error::Error` impls for both. `Result<T> = std::result::Result<T, IffError>` alias.

No `thiserror` / `anyhow` — the whole crate has zero dependencies. This is a no-deps policy, not a dogma, and it matters because the Go version's appeal is partly "zero deps, one binary, fast build"; the Rust version should preserve that.

### `src/lexer.rs`

The token type is an enum, not a struct-with-kind. This is the biggest idiom difference from the Go port:

```rust
pub enum Token {
    Eof,
    LBrace, RBrace, LParen, RParen, LBrack, RBrack, Comma,
    DoubleColon, Plus, Minus,
    SizeY, SizeW, SizeL,
    Timestamp, Align, Offsetof, Sizeof, FillChar, Start, Length, Precision,
    Integer { val: u64, width: u8 },     // width=0 means default
    Real { val: f64, precision: Option<SizeSpec> },
    String { body: String, size_override: usize },
    CharLit(u32),                         // FOURCC packed MSB-first
    PrecSpec(SizeSpec),                   // bare N.N.N triple
}

pub struct SpannedToken {
    pub tok: Token,
    pub pos: Pos,
}
```

Bundling the token's data into each variant replaces the Go version's `token` struct with ~10 always-present fields, only some of which are populated per kind. It's cleaner, but it means pattern matching at call sites rather than reaching into fields.

Lexer state:

```rust
pub struct Lexer {
    stack: Vec<Frame>,                 // include-file stack
    lookahead: VecDeque<SpannedToken>, // peek buffer
}

struct Frame {
    src: Vec<u8>,
    offset: usize,
    line: u32,
    col: u32,
    filename: String,
}
```

`Lexer::open(path)` reads the initial file and pushes the first frame. `push_include(path)` / `push_system_include(name)` handle the `include "f"` / `include <f>` forms. `pop_include()` returns `true` if we popped, `false` at the outermost frame.

`Lexer::peek(k)` returns the k'th token ahead (backed by a `VecDeque` that gets drained on `next()`). `Lexer::next()` returns the next token, calling `scan()` to refill.

**The scan function mirrors the Go port's state machine byte-for-byte**, including the two disambiguations that bit it:

1. Top-level `.` dispatch: if the byte after `.` is a digit, route to `scan_number` (handles `.5`), else to `scan_dot_keyword`.
2. Speculative rollback in `scan_number`: after parsing a digit-only mantissa, peek for `(`; if it's a well-formed precision triple, reclassify as REAL with that precision, otherwise roll back.

Rollback in Rust is cleaner than in Go: save `(offset, line, col)` as a `LexPos` struct, restore on mismatch. No naked field-by-field save/restore.

**String literal handling** follows the Go version: preserve escape sequences literally as `\n`, `\t`, `\\`, `\"`, `\DDD` in the token body; translate them at write time inside `Writer::out_string` (not inside the lexer). This matches `iffwrite/binary.cc`'s `translate_escape_codes`.

**Speculative `(N)` size override** after a string literal: save position, try to parse `(digits)`, commit or roll back. Same logic as Go.

Expected size: ~600 lines of Rust, down from the Go version's 817 because the variant-enum token avoids the ~100 lines of boilerplate `token_name` and `token` struct fields.

### `src/parser.rs`

```rust
pub struct Parser<'w> {
    lex: Lexer,
    w: &'w mut Writer,
    states: Vec<State>,
    start_pos_override: u64,
    length_override: u64,
    pub verbose: bool,
}

pub struct State {
    pub size_override: i32,
    pub precision: SizeSpec,
}
```

Constructor pushes the default `State { size_override: 1, precision: SizeSpec { sign: 1, whole: 15, fraction: 16 } }`.

**The lifetime on `Writer`** is the trickiest piece of the Rust implementation. Options:

1. `&'w mut Writer` — borrow-check guarantees exclusive access, simple, but the parser can't outlive the writer. Fine because `compile()` holds both and drops the parser first. ← **chosen**
2. `Box<dyn WriterTrait>` — abstract behind a trait, each writer mode is a separate type. More Rusty, but gratuitous indirection for a tool that only has two modes.
3. `Writer` by value, moved into the parser. The parser has to give it back on completion. Ugly return types.

Option 1 is the least surprising and keeps the structure close to the Go port.

**Production functions are methods**, one per `lang.y` rule:

```rust
impl<'w> Parser<'w> {
    pub fn parse(&mut self) -> Result<()> { … }
    fn parse_chunk(&mut self) -> Result<()> { … }
    fn parse_chunk_statement(&mut self) -> Result<()> { … }
    fn parse_expr(&mut self) -> Result<u64> { … }
    fn parse_item(&mut self) -> Result<u64> { … }
    fn parse_state_push(&mut self) -> Result<()> { … }
    fn parse_string_list(&mut self) -> Result<()> { … }
    fn parse_file_include(&mut self) -> Result<()> { … }
    fn parse_extract_spec(&mut self) -> Result<()> { … }
    fn parse_chunk_specifier(&mut self) -> Result<String> { … }
    fn parse_offsetof(&mut self) -> Result<()> { … }
    fn parse_sizeof(&mut self) -> Result<()> { … }
    fn parse_alignment(&mut self) -> Result<()> { … }
    fn parse_fill_char(&mut self) -> Result<()> { … }
}
```

The two-token lookahead for chunk-vs-state-push (`if peek().is_lbrace() && peek(1).is_char_lit() → chunk`) is the same as Go.

**`trace(&self, rule: &str)`** helper for `-v` verbose mode. Prints `parse: {rule} @ {pos} (lookahead={tok_name})` to stderr when `self.verbose` is set.

**Expression evaluation** (`expr -> item (('+' | '-') item)*`) returns the accumulated `u64` value. The grammar's integer arithmetic happens to wrap naturally with `u64::wrapping_add` / `u64::wrapping_sub` — match the Go version's plain `+`/`-` on `uint64`, which also wraps. The original C++ grammar left the `MINUS` action empty; I wired it up in Go and will do the same here.

Expected size: ~500 lines of Rust.

### `src/writer.rs`

**Two modes via enum**, not a flag:

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Mode {
    #[default] Binary,
    Text,
}

pub struct Writer {
    mode: Mode,
    // shared state
    stack: Vec<ChunkFrame>,
    path_ids: Vec<u32>,
    symbols: HashMap<String, ChunkSym>,
    pending: Vec<BackpatchRec>,
    fill_char: u8,
    // binary state
    buf: Vec<u8>,
    pos: usize,
    // text state
    text_buf: String,
    text_on_line: usize,
}
```

Each emit method matches on `self.mode` at entry:

```rust
pub fn out_int8(&mut self, v: u8) {
    match self.mode {
        Mode::Binary => self.buf.push(v),
        Mode::Text => {
            use std::fmt::Write;
            let _ = write!(self.text_buf, "{}y ", v as i8);
        }
    }
}
```

Same single-struct-with-mode-branch approach as Go. It's dirtier than two types behind a trait, but (a) matches the Go version for cross-referencing, and (b) keeps the binary and text implementations of each primitive next to each other for easy diffing.

**Key invariants to get right**, all learned the hard way in the Go port:

1. **LP64 cast from `int32` slot:** the C++ `IffWriterBinary::exitChunk` patches the size field with `_out->write((char*)&size, sizeof(long))` which is 8 bytes on LP64 Linux. The modernized C++ version hard-codes it to 4 bytes, and the Go / Rust ports both use an explicit `u32` (4-byte) field.
2. **Fixed-point negative-value cast:** `int64(val * 2^fraction) as u32` gives modular wrap on Rust (`as u32` for a negative `i64` reinterprets the two's-complement bits). The gcc output on x86-64 does the same thing, so this matches without extra work. Just use `(val * (1 << fraction)) as i64 as u32`, go *through* `i64` first.
3. **IffWriterText off-by-one indent:** the C++ `_IffWriter` ctor pushes a sentinel onto `chunkSize`, so `chunkSize.size()` is `1 + depth`. All the `iffwrite/text.cc` indent formulas assume that. Bake the off-by-one into the Rust `text_emit_indent(depth)` helper directly — depth-before-push for `{`, depth-after-pop for `}`, depth+1 for the `out_file` wrap marker.
4. **`out_string_continue`:** binary mode seeks back 1 byte over the previous NUL and re-emits; text mode just emits a second `"..."` literal (`IffWriterText::out_string_continue` delegates to `out_string` without the seek).
5. **`"..."(N)` size override:** binary mode pads with zeros to exactly N bytes; text mode ignores the override (matches `IffWriterText`).
6. **`out_file` in text mode:** unrolls the file as individual `<byte>y` items with a ` //\n<tabs>` wrap marker every 100 bytes. Off-by-one fix applies to the wrap indent too.
7. **Real formatting in text mode:** `%#.16g` is Go's closest match to C++ iostreams' `setprecision(16) + showpoint`. For Rust, `format!("{:.16}", val)` gives a different result — need to reproduce the `#.16g` form. Options: (a) call out to a `format_g` helper that mimics printf's `%#.16g`; (b) use `format!("{:e}", val)` and post-process; (c) accept `format!("{:.16}", val)` and regenerate the oracle. Will try (a) first — write a small `format_g_alt` function that matches printf semantics byte-for-byte.

Expected size: ~650 lines of Rust.

### `tests/byte_exact.rs`

Two integration tests (not unit tests — integration tests live in `tests/` and link the crate as a library, which is what we want):

```rust
use std::env;
use std::fs;
use std::path::PathBuf;
use iffcomp::{compile, Mode, Options};

fn testdata_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("testdata")
}

#[test]
fn byte_exact_binary_vs_cpp() {
    let _guard = ChdirGuard::new(testdata_dir());  // [`ChdirGuard`] runs `set_current_dir` on Drop
    let out = tempfile::NamedTempFile::new().unwrap();  // or manual tmp handling since no deps
    compile("test.iff.txt", out.path(), Options { mode: Mode::Binary, ..Default::default() }).unwrap();
    let got = fs::read(out.path()).unwrap();
    let want = fs::read("expected.iff").unwrap();
    assert_bytes_eq(&got, &want);
}

#[test]
fn byte_exact_text_vs_cpp() { /* mode: Mode::Text, fixture: expected.iff.txt */ }
```

**Chdir-on-drop guard:** the `[ "TODO" ]` path in `test.iff.txt` resolves relative to the current working directory, matching the C++ and Go behaviors. The Rust test needs to temporarily `std::env::set_current_dir(testdata/)` for the duration of the compile and restore on return. The Go version used `t.Cleanup`; the Rust version will use a small `ChdirGuard` struct with `Drop`.

**No `tempfile` dep:** since we're zero-deps, the tests will manually manage a tmp file in `std::env::temp_dir()` and clean it up themselves. Not pretty but keeps the dependency list honest.

**`assert_bytes_eq`** helper that reports offset and hex context on mismatch, same as `hexDiffContext` in the Go port.

Expected size: ~150 lines of Rust.

## Bring-up bug predictions

Based on the Go experience, these are the most likely first-run failures:

1. **`3(1.15.16)` tokenizes wrong** — virtually certain. Same issue as Go. Fix: speculative-rollback after digit-only mantissa.
2. **`.5` tokenizes wrong** — virtually certain. Same issue as Go. Fix: one-line dispatch.
3. **Fixed-point modular cast produces wrong bytes for negative values** — possible if I use `val.mul_add(scale) as u32` instead of going through `i64`.
4. **`%#.16g` doesn't match C printf byte-for-byte** — probable, because Rust's `format!` doesn't have an `alt .16g` form. Will need a custom formatter.
5. **Text-mode indent off-by-one** — probable if I don't bake it in from the start. The fix is documented in the Go port investigation; copy-paste the formula.
6. **`HashMap` iteration order affects error reporting** — the Go port's `ResolveBackpatches` iterates `pending` in insertion order. Rust `HashMap` has randomized iteration. Use `Vec<BackpatchRec>` (which I specced above — the Vec is ordered, the HashMap is only for symbol lookup, not iteration).

## Verification

1. `cargo build` — should compile cleanly.
2. `cargo test` — both byte-exact tests pass.
3. `cargo build --release && ./target/release/iffcomp -o=/tmp/out.iff testdata/test.iff.txt && cmp /tmp/out.iff testdata/expected.iff`.
4. Same with `-ascii`.
5. `-v` smoke test: stderr gets `parse: chunk @ …` lines.

## Success criteria

Same as the Go port, same as the C++ modernization: byte-exact match on `test.iff.txt` for both binary and text modes. The oracle files are committed to `testdata/` and were produced by the modernized C++ `iffcomp` — we're diffing three implementations against one reference.

Once that passes, the Rust port has earned the right to be the fourth implementation sitting alongside C++ and Go. Whether it eventually *replaces* them is a separate decision — the companion investigation argues Rust is the preferred long-term target, but none of that needs to be settled in this session.

## Out of scope

- Writer as a trait. If we ever want to add a third output format (JSON? MessagePack?), the mode-enum approach will need a refactor. Not today.
- Lexer fuzz tests. Easy to add via `cargo-fuzz` or `proptest`, but both are deps.
- Incremental / streaming output. Both the C++ and Go versions buffer the entire output in memory. Files are small; don't optimize yet.
- Cross-target compilation matrix. `cargo build --target x86_64-pc-windows-gnu` should Just Work given no deps, but I won't verify it this session.

## Next step after plan approval

Install the Rust toolchain (`! sudo apt install -y cargo rustc` or rustup — user pick), then write `src/lexer.rs`, `src/parser.rs`, `src/writer.rs`, `tests/byte_exact.rs`, in that order. `cargo test` after each file so the failure mode is local. Expect 1–3 iterations on the text-mode float formatter before byte-exact match.
