//! levtree — World Foundry `.lev` ↔ editable chunk tree translator.
//!
//! Parses the authored `.lev` chunk DSL into a recursive [`LevelDoc`] tree
//! (JSON-serializable) for the collaborative editor's CRDT, and prints a
//! canonical `.lev` back. See `docs/plans/2026-05-20-iff-lev-ydoc-translator.md`.
//!
//! v1 reads/writes `.lev`; the `.iff` byte-identity gate (recompile via
//! `build_level_binary.sh`) is the correctness proof. Annotation comments
//! (`//False|True`, `//x,y,z`) are dropped — they're redundant with the OAD,
//! and iffcomp strips them anyway, so the compiled `.iff` is unaffected.
//!
//! The parser reuses iffcomp-rs's `Lexer` (FOURCC, precision-tagged reals,
//! string escapes, int-width suffixes) and adds only the tree build; number
//! spellings are canonicalized at parse time so `parse → print → parse` is
//! idempotent (the `.iff` gate proves the spelling re-quantizes identically).

use iffcomp::lexer::{Lexer, SizeSpec, Token};
use iffcomp::writer::id_name;
use serde::{Deserialize, Serialize};

/// A literal token inside a chunk body: a quoted string, a number (with its
/// canonical `.lev` spelling), or a FOURCC char-literal.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Literal {
    /// `"..."` — body as written (escapes unresolved, matching iffcomp).
    Str { value: String },
    /// A `DATA`/value number; `text` is the canonical spelling incl. any
    /// `(S.W.F)` precision suffix so iffcomp re-quantizes identically.
    Num { text: String },
    /// A `'OBJ'`-style four-character code used as a value (rare in `.lev`).
    FourCC { id: String },
}

/// One body item: either a nested chunk or a literal.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Item {
    Chunk(Chunk),
    Literal(Literal),
}

/// A `{ 'ID' items… }` node. Deliberately generic: containers (`LVL`/`OBJ`)
/// hold child chunks; leaves (`VEC3`/`FX32`/…) hold their `NAME`/`DATA`/`STR`
/// sub-chunks and literals. The leaf "name/data/str" view is a lazy accessor
/// over `items`, not a separate storage shape (see plan Appendix A).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Chunk {
    pub id: String,
    pub items: Vec<Item>,
}

/// A parsed level: the root `LVL` chunk, kept whole for faithful print. The
/// editor's Y.Doc-population step drops `LVL` and lifts `OBJ`s into `content`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LevelDoc {
    pub root: Chunk,
}

#[derive(Debug)]
pub enum LevError {
    Parse(String),
    Io(std::io::Error),
}

impl std::fmt::Display for LevError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LevError::Parse(m) => write!(f, "parse error: {m}"),
            LevError::Io(e) => write!(f, "I/O error: {e}"),
        }
    }
}
impl std::error::Error for LevError {}
impl From<std::io::Error> for LevError {
    fn from(e: std::io::Error) -> Self {
        LevError::Io(e)
    }
}

pub type Result<T> = std::result::Result<T, LevError>;

// ── parse ──────────────────────────────────────────────────────────────────

/// Parse `.lev` source text into a [`LevelDoc`] tree.
///
/// Expects exactly one root chunk (`LVL`) followed by EOF. Comments are
/// dropped (the lexer skips them). Number spellings are canonicalized.
pub fn parse_lev(src: &str) -> Result<LevelDoc> {
    let mut lex = Lexer::from_source(src.as_bytes().to_vec(), "<lev>");
    let root = parse_chunk(&mut lex)?;
    match lex.peek(0).map_err(lex_err)? {
        Token::Eof => {}
        other => {
            return Err(LevError::Parse(format!(
                "trailing tokens after root chunk: {}",
                other.name()
            )))
        }
    }
    Ok(LevelDoc { root })
}

fn lex_err(e: iffcomp::IffError) -> LevError {
    LevError::Parse(format!("lex: {e}"))
}

/// Parse one `{ 'ID' items… }` chunk. Assumes the next token is `{`.
fn parse_chunk(lex: &mut Lexer) -> Result<Chunk> {
    match lex.next().map_err(lex_err)?.tok {
        Token::LBrace => {}
        other => {
            return Err(LevError::Parse(format!(
                "expected '{{' at chunk start, got {}",
                other.name()
            )))
        }
    }
    let id = match lex.next().map_err(lex_err)?.tok {
        Token::CharLit(packed) => id_name(packed),
        other => {
            return Err(LevError::Parse(format!(
                "expected chunk id (FOURCC) after '{{', got {}",
                other.name()
            )))
        }
    };

    let mut items = Vec::new();
    loop {
        match lex.peek(0).map_err(lex_err)? {
            Token::RBrace => {
                lex.next().map_err(lex_err)?; // consume '}'
                break;
            }
            Token::LBrace => items.push(Item::Chunk(parse_chunk(lex)?)),
            Token::Eof => {
                return Err(LevError::Parse(format!(
                    "unexpected EOF inside chunk '{id}'"
                )))
            }
            _ => items.push(Item::Literal(parse_literal(lex)?)),
        }
    }
    Ok(Chunk { id, items })
}

/// Parse a single value literal (string, number, or bare FOURCC).
fn parse_literal(lex: &mut Lexer) -> Result<Literal> {
    let tok = lex.next().map_err(lex_err)?.tok;
    match tok {
        Token::String { body, .. } => Ok(Literal::Str { value: body }),
        Token::Integer { val, width } => Ok(Literal::Num {
            text: format_int(val, width),
        }),
        Token::Real { val, precision } => Ok(Literal::Num {
            text: format_real(val, precision),
        }),
        Token::CharLit(packed) => Ok(Literal::FourCC {
            id: id_name(packed),
        }),
        other => Err(LevError::Parse(format!(
            "unexpected token in value position: {}",
            other.name()
        ))),
    }
}

/// Canonical integer spelling: value + size suffix (`y`/`w`/`l` for 1/2/4).
fn format_int(val: u64, width: u8) -> String {
    let suffix = match width {
        1 => "y",
        2 => "w",
        4 => "l",
        _ => "",
    };
    format!("{val}{suffix}")
}

/// Canonical real spelling: shortest round-trip decimal (always with a `.`)
/// plus the `(sign.whole.fraction)` precision suffix when present. Because the
/// shortest form denotes the same `f64`, iffcomp quantizes it to the same
/// fixed-point as the original — proven by the `.iff` byte-identity gate.
fn format_real(val: f64, precision: Option<SizeSpec>) -> String {
    let mut s = format!("{val}");
    if !s.contains('.') && !s.contains('e') && !s.contains('E') && val.is_finite() {
        s.push_str(".0");
    }
    if let Some(p) = precision {
        s.push_str(&format!("({}.{}.{})", p.sign, p.whole, p.fraction));
    }
    s
}

// ── print ──────────────────────────────────────────────────────────────────

/// Print a [`LevelDoc`] back to canonical `.lev` text.
///
/// Canonical form: tab indentation; a chunk is **block-level** (children on
/// their own indented lines) iff it contains a child chunk that itself has
/// child chunks (→ `LVL`/`OBJ`/`PATH`); otherwise it is **inline**
/// (`{ 'ID' … }` on one line, → leaf fields like `VEC3`/`I32`). Annotation
/// comments are not emitted (D8). Whitespace/comments don't affect the
/// compiled `.iff`, so this form recompiles byte-identically (step-5 gate).
pub fn print_lev(doc: &LevelDoc) -> String {
    let mut out = String::new();
    emit(&doc.root, 0, &mut out);
    out
}

/// True if `c` should print across multiple lines: it holds a child chunk
/// that itself holds a child chunk (a structural container of containers).
fn is_block(c: &Chunk) -> bool {
    c.items.iter().any(|it| {
        matches!(it, Item::Chunk(child)
            if child.items.iter().any(|i| matches!(i, Item::Chunk(_))))
    })
}

/// Emit `c` at `indent` tabs, dispatching block vs inline.
fn emit(c: &Chunk, indent: usize, out: &mut String) {
    if is_block(c) {
        push_tabs(indent, out);
        out.push_str("{ '");
        out.push_str(&c.id);
        out.push_str("'\n");
        for it in &c.items {
            match it {
                Item::Chunk(child) => emit(child, indent + 1, out),
                Item::Literal(lit) => {
                    push_tabs(indent + 1, out);
                    push_literal(lit, out);
                    out.push('\n');
                }
            }
        }
        push_tabs(indent, out);
        out.push_str("}\n");
    } else {
        push_tabs(indent, out);
        emit_inline(c, out);
        out.push('\n');
    }
}

/// Emit `c` as a single-line `{ 'ID' item … }` with no trailing newline.
fn emit_inline(c: &Chunk, out: &mut String) {
    out.push_str("{ '");
    out.push_str(&c.id);
    out.push('\'');
    for it in &c.items {
        out.push(' ');
        match it {
            Item::Chunk(child) => emit_inline(child, out),
            Item::Literal(lit) => push_literal(lit, out),
        }
    }
    out.push_str(" }");
}

fn push_tabs(n: usize, out: &mut String) {
    for _ in 0..n {
        out.push('\t');
    }
}

fn push_literal(lit: &Literal, out: &mut String) {
    match lit {
        Literal::Str { value } => {
            out.push('"');
            out.push_str(value);
            out.push('"');
        }
        Literal::Num { text } => out.push_str(text),
        Literal::FourCC { id } => {
            out.push('\'');
            out.push_str(id);
            out.push('\'');
        }
    }
}

// ── tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn count_objs(c: &Chunk) -> usize {
        c.items
            .iter()
            .filter(|it| matches!(it, Item::Chunk(ch) if ch.id == "OBJ"))
            .count()
    }

    fn parse_fixture(rel: &str) -> LevelDoc {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../..")
            .join(rel);
        let src = std::fs::read_to_string(&path)
            .unwrap_or_else(|e| panic!("read {}: {e}", path.display()));
        parse_lev(&src).unwrap_or_else(|e| panic!("parse {}: {e}", path.display()))
    }

    #[test]
    fn parse_minimal() {
        let doc = parse_lev("{ 'LVL' }").unwrap();
        assert_eq!(doc.root.id, "LVL");
        assert!(doc.root.items.is_empty());
    }

    #[test]
    fn parse_leaf_shapes() {
        // VEC3 with NAME + DATA (3 reals), and an I32 with NAME/DATA/STR.
        let src = r#"{ 'LVL'
            { 'OBJ'
                { 'NAME' "House" }
                { 'VEC3' { 'NAME' "Position" } { 'DATA' -0.25(1.15.16) 12.0(1.15.16) 0.0(1.15.16)  //x,y,z
                } }
                { 'I32' { 'NAME' "Mobility" } { 'STR' "Anchored" } }
                { 'I32' { 'NAME' "Moves Between Rooms" } { 'DATA' 0l } { 'STR' "False" } }  //False|True
            }
        }"#;
        let doc = parse_lev(src).unwrap();
        assert_eq!(doc.root.id, "LVL");
        assert_eq!(count_objs(&doc.root), 1);
        let Item::Chunk(obj) = &doc.root.items[0] else { panic!("expected OBJ") };
        assert_eq!(obj.id, "OBJ");
        // NAME leaf carries one string literal.
        let Item::Chunk(name) = &obj.items[0] else { panic!() };
        assert_eq!(name.id, "NAME");
        assert!(matches!(&name.items[0], Item::Literal(Literal::Str { value }) if value == "House"));
        // VEC3 → DATA has 3 numeric literals; the //x,y,z comment is dropped.
        let Item::Chunk(vec3) = &obj.items[1] else { panic!() };
        assert_eq!(vec3.id, "VEC3");
        let Item::Chunk(data) = &vec3.items[1] else { panic!() };
        assert_eq!(data.id, "DATA");
        let nums = data.items.iter().filter(|i| matches!(i, Item::Literal(Literal::Num { .. }))).count();
        assert_eq!(nums, 3, "DATA should have 3 numbers, comment dropped");
    }

    #[test]
    fn serde_round_trip_smb() {
        let doc = parse_fixture("wflevels/smb_w1_1/smb_w1_1.lev");
        let json = serde_json::to_string(&doc).unwrap();
        let back: LevelDoc = serde_json::from_str(&json).unwrap();
        assert_eq!(doc, back, "serde JSON round-trip must be lossless");
    }

    #[test]
    fn parse_real_levels_structure() {
        for (rel, objs) in [
            ("wflevels/snowgoons-blender/snowgoons-blender.lev", 36),
            ("wflevels/smb_w1_1/smb_w1_1.lev", 22),
            ("wflevels/qbert_practice/qbert_practice.lev", 66),
        ] {
            let doc = parse_fixture(rel);
            assert_eq!(doc.root.id, "LVL", "{rel}: root must be LVL");
            assert_eq!(count_objs(&doc.root), objs, "{rel}: OBJ count");
        }
    }

    #[test]
    fn print_inline_and_block_forms() {
        let src = r#"{ 'LVL' { 'OBJ' { 'NAME' "H" } { 'VEC3' { 'NAME' "Position" } { 'DATA' 1.0(1.15.16) } } } }"#;
        let doc = parse_lev(src).unwrap();
        let printed = print_lev(&doc);
        // LVL and OBJ are containers-of-containers → block; VEC3 is a leaf → inline.
        assert!(printed.contains("{ 'LVL'\n"), "LVL should be block:\n{printed}");
        assert!(printed.contains("\t{ 'OBJ'\n"), "OBJ block, indented:\n{printed}");
        assert!(
            printed.contains("{ 'VEC3' { 'NAME' \"Position\" } { 'DATA' 1.0(1.15.16) } }"),
            "VEC3 should be inline:\n{printed}"
        );
        assert_eq!(doc, parse_lev(&printed).unwrap(), "idempotent");
    }

    #[test]
    fn print_parse_idempotent_real_levels() {
        for rel in [
            "wflevels/snowgoons-blender/snowgoons-blender.lev",
            "wflevels/smb_w1_1/smb_w1_1.lev",
            "wflevels/qbert_practice/qbert_practice.lev",
        ] {
            let doc = parse_fixture(rel);
            let printed = print_lev(&doc);
            let reparsed =
                parse_lev(&printed).unwrap_or_else(|e| panic!("reparse printed {rel}: {e}"));
            assert_eq!(doc, reparsed, "{rel}: parse→print→parse must be idempotent");
        }
    }

    /// Compile `.lev` source to its binary IFF bytes via iffcomp's library API
    /// (the `iffcomp -binary` stage of the build pipeline), in-process.
    fn compile_lev_bin(src: &str) -> Vec<u8> {
        use iffcomp::lexer::Lexer;
        use iffcomp::parser::Parser;
        use iffcomp::writer::{Mode, Writer};
        let lex = Lexer::from_source(src.as_bytes().to_vec(), "<lev>");
        let mut w = Writer::new(Mode::default()); // default = binary
        let mut p = Parser::new(lex, &mut w);
        p.parse().expect("iffcomp parse");
        drop(p);
        w.resolve_backpatches().expect("resolve backpatches");
        w.bytes().to_vec()
    }

    /// THE correctness gate (plan D5/R4): canonicalizing a `.lev` (dropping
    /// comments, reformatting numbers) must not change the `.lev.bin` the
    /// engine ultimately loads. iffcomp(`.lev`) is the only pipeline stage
    /// that consumes the `.lev`, so byte-identity here ⟹ full-`.iff` identity.
    #[test]
    fn lev_bin_byte_identity_gate() {
        for rel in [
            "wflevels/snowgoons-blender/snowgoons-blender.lev",
            "wflevels/smb_w1_1/smb_w1_1.lev",
            "wflevels/qbert_practice/qbert_practice.lev",
        ] {
            let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../..")
                .join(rel);
            let orig_src = std::fs::read_to_string(&path).unwrap();
            let canon_src = print_lev(&parse_lev(&orig_src).unwrap());
            let orig_bin = compile_lev_bin(&orig_src);
            let canon_bin = compile_lev_bin(&canon_src);
            assert_eq!(
                orig_bin, canon_bin,
                "{rel}: canonicalized .lev must compile to a byte-identical .lev.bin"
            );
            assert!(!orig_bin.is_empty(), "{rel}: .lev.bin should be non-empty");
        }
    }
}

// ── C ABI (web editor one-click Export) ─────────────────────────────────────
// The browser editor can't shell out to the `levtree` binary (no popen on wasm),
// so it links this crate as a static lib and calls levtree_print_json in-process:
// a levtree chunk-tree JSON string → canonical `.lev` text. Only compiled for the
// emscripten staticlib build; native keeps using the CLI via popen.
#[cfg(target_os = "emscripten")]
mod cabi {
    use std::ffi::{CStr, CString};
    use std::os::raw::c_char;

    /// JSON levtree chunk-tree → canonical `.lev`. Returns a heap C string the
    /// caller must release with `levtree_free`; NULL on null/invalid-UTF8/parse error.
    #[no_mangle]
    pub extern "C" fn levtree_print_json(json: *const c_char) -> *mut c_char {
        if json.is_null() {
            return std::ptr::null_mut();
        }
        let s = match unsafe { CStr::from_ptr(json) }.to_str() {
            Ok(s) => s,
            Err(_) => return std::ptr::null_mut(),
        };
        let doc: crate::LevelDoc = match serde_json::from_str(s) {
            Ok(d) => d,
            Err(_) => return std::ptr::null_mut(),
        };
        match CString::new(crate::print_lev(&doc)) {
            Ok(c) => c.into_raw(),
            Err(_) => std::ptr::null_mut(), // interior NUL (can't happen in .lev text)
        }
    }

    /// Free a string returned by `levtree_print_json`.
    #[no_mangle]
    pub extern "C" fn levtree_free(s: *mut c_char) {
        if !s.is_null() {
            unsafe { drop(CString::from_raw(s)) };
        }
    }
}
