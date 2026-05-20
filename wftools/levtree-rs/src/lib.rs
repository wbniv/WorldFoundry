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

use serde::{Deserialize, Serialize};

/// A literal token inside a chunk body: a quoted string, a number (with its
/// `.lev` precision spelling preserved), or a FOURCC char-literal.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Literal {
    /// `"..."` — body as written (escapes unresolved, matching iffcomp).
    Str { value: String },
    /// A `DATA`/value number; `text` keeps the canonical spelling incl. any
    /// `(S.W.F)` precision suffix so iffcomp re-quantizes identically.
    Num { text: String },
    /// A `'OBJ'`-style four-character code.
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

/// Parse `.lev` source text into a [`LevelDoc`] tree.
///
/// TODO(step 2-3): drive iffcomp-rs's `Lexer` and build the recursive tree.
pub fn parse_lev(_src: &str) -> Result<LevelDoc> {
    Err(LevError::Parse(
        "parse_lev: not implemented yet (plan step 2-3)".into(),
    ))
}

/// Print a [`LevelDoc`] back to canonical `.lev` text.
///
/// TODO(step 4): canonical indentation + number spelling, comments dropped.
pub fn print_lev(_doc: &LevelDoc) -> String {
    String::new()
}
