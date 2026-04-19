//! Recursive-descent parser for the iffcomp DSL.
//!
//! Mirrors the productions in `wftools/iffcomp/lang.y` one-for-one. The two
//! major differences from the C++ bison grammar are:
//!
//! 1. `chunk` vs. `state_push` disambiguation is explicit 2-token lookahead
//!    on `{` here. Bison handled it implicitly via its shift preference
//!    (which was the source of the 30 S/R conflicts in the `.y` file).
//! 2. The `MINUS` operator in `expr` is actually wired up to subtract,
//!    where the C++ grammar left the action empty. Two-character
//!    behavior change from the unfinished original.

use crate::error::{IffError, Pos, Result};
use crate::lexer::{Lexer, SizeSpec, Token};
use crate::writer::{id_name, SignedTerm, Term, Writer};
use std::path::PathBuf;

/// One layer of push-down state for the nested `{ Y … }` / `{ .precision … }`
/// blocks. The parser constructor seeds one default frame; each state-push
/// pushes a derived frame; the matching `}` pops.
pub struct State {
    pub size_override: i32,
    pub precision: SizeSpec,
}

pub struct Parser<'w> {
    lex: Lexer,
    w: &'w mut Writer,

    states: Vec<State>,

    // Per-item scratch state used by the file-include path.
    start_pos_override: u64,
    length_override: u64,

    pub verbose: bool,
}

impl<'w> Parser<'w> {
    pub fn new(lex: Lexer, w: &'w mut Writer) -> Self {
        Parser {
            lex,
            w,
            states: vec![State {
                size_override: 1,
                precision: SizeSpec {
                    sign: 1,
                    whole: 15,
                    fraction: 16,
                },
            }],
            start_pos_override: 0,
            length_override: u64::MAX,
            verbose: false,
        }
    }

    fn top_state(&self) -> &State {
        self.states.last().unwrap()
    }

    fn push_state(&mut self, s: State) {
        self.states.push(s);
    }

    fn pop_state(&mut self) {
        assert!(self.states.len() > 1, "pop_state on default stack");
        self.states.pop();
    }

    // --- token helpers ------------------------------------------------------

    fn peek(&mut self) -> Result<Token> {
        self.lex.peek(0)
    }

    fn peek1(&mut self) -> Result<Token> {
        self.lex.peek(1)
    }

    fn consume(&mut self) -> Result<Token> {
        Ok(self.lex.next()?.tok)
    }

    fn expect_pos(&mut self, want: &str) -> Pos {
        // Best-effort position of the next token for error reporting.
        // Doesn't consume anything.
        match self.lex.peek(0) {
            Ok(_) => {
                // lexer already populated its lookahead; grab the span.
                // We can't actually access the span here without changing
                // the lex interface, so we synthesize from Default.
                let _ = want;
                Pos::default()
            }
            Err(_) => Pos::default(),
        }
    }

    fn expect(&mut self, want: &Token, what: &str) -> Result<Token> {
        let got = self.peek()?;
        if !discriminant_eq(&got, want) {
            return Err(IffError::Parse {
                at: self.expect_pos(what),
                msg: format!("expected {}, got {}", what, got.name()),
            });
        }
        self.consume()
    }

    fn expect_integer(&mut self, what: &str) -> Result<(u64, u8)> {
        let tok = self.peek()?;
        if let Token::Integer { val, width } = tok {
            self.consume()?;
            Ok((val, width))
        } else {
            Err(IffError::Parse {
                at: self.expect_pos(what),
                msg: format!("expected {}, got {}", what, tok.name()),
            })
        }
    }

    fn expect_char_lit(&mut self, what: &str) -> Result<u32> {
        let tok = self.peek()?;
        if let Token::CharLit(v) = tok {
            self.consume()?;
            Ok(v)
        } else {
            Err(IffError::Parse {
                at: self.expect_pos(what),
                msg: format!("expected {}, got {}", what, tok.name()),
            })
        }
    }

    fn expect_prec_spec(&mut self, what: &str) -> Result<SizeSpec> {
        let tok = self.peek()?;
        if let Token::PrecSpec(s) = tok {
            self.consume()?;
            Ok(s)
        } else {
            Err(IffError::Parse {
                at: self.expect_pos(what),
                msg: format!("expected {}, got {}", what, tok.name()),
            })
        }
    }

    fn expect_string(&mut self, what: &str) -> Result<(String, usize)> {
        let tok = self.peek()?;
        if let Token::String {
            body,
            size_override,
        } = tok
        {
            self.consume()?;
            Ok((body, size_override))
        } else {
            Err(IffError::Parse {
                at: self.expect_pos(what),
                msg: format!("expected {}, got {}", what, tok.name()),
            })
        }
    }

    fn trace(&mut self, rule: &str) {
        if !self.verbose {
            return;
        }
        match self.peek() {
            Ok(tok) => eprintln!("parse: {} (lookahead={})", rule, tok.name()),
            Err(_) => eprintln!("parse: {} (lookahead=<err>)", rule),
        }
    }

    // --- top level ----------------------------------------------------------

    pub fn parse(&mut self) -> Result<()> {
        loop {
            match self.peek()? {
                Token::Eof => return Ok(()),
                _ => self.parse_chunk()?,
            }
        }
    }

    // --- chunk --------------------------------------------------------------

    fn parse_chunk(&mut self) -> Result<()> {
        self.trace("chunk");
        self.expect(&Token::LBrace, "'{' starting chunk")?;
        let id = self.expect_char_lit("chunk ID")?;
        self.w.enter_chunk(id);
        loop {
            match self.peek()? {
                Token::RBrace | Token::Eof => break,
                _ => self.parse_chunk_statement()?,
            }
        }
        self.expect(&Token::RBrace, "'}' closing chunk")?;
        self.w.exit_chunk();
        Ok(())
    }

    fn parse_chunk_statement(&mut self) -> Result<()> {
        match self.peek()? {
            Token::LBrace => {
                // chunk vs. state_push: 2-token lookahead.
                if matches!(self.peek1()?, Token::CharLit(_)) {
                    return self.parse_chunk();
                }
                // Fall through to expression path (handles state_push via parse_item).
            }
            Token::Align => return self.parse_alignment(),
            Token::FillChar => return self.parse_fill_char(),
            _ => {}
        }
        self.parse_expr()
    }

    fn parse_alignment(&mut self) -> Result<()> {
        self.consume()?; // .align
        self.expect(&Token::LParen, "'(' after .align")?;
        let (n, _) = self.expect_integer("integer in .align")?;
        self.expect(&Token::RParen, "')' closing .align")?;
        if n == 0 {
            return Err(IffError::Parse {
                at: Pos::default(),
                msg: "align(0) doesn't make sense".into(),
            });
        }
        self.w.align_function(n as usize);
        Ok(())
    }

    fn parse_fill_char(&mut self) -> Result<()> {
        self.consume()?; // .fillchar
        self.expect(&Token::LParen, "'(' after .fillchar")?;
        let (n, _) = self.expect_integer("integer in .fillchar")?;
        self.expect(&Token::RParen, "')' closing .fillchar")?;
        self.w.set_fill_char(n as u8);
        Ok(())
    }

    // --- expr / item --------------------------------------------------------
    //
    // Grammar shape:
    //   expr : item (('+' | '-') item)*
    // Items fall into two buckets:
    //   - **arithmetic** (`Integer`, `.offsetof`, `.sizeof`) — build a
    //     `SignedTerm` and compose via `+/-`. Emitted ONCE as a single
    //     int32 via `Writer::emit_expr`.
    //   - **non-arithmetic** (`String`, `Real`, `CharLit`, `.timestamp`,
    //     file-include `[...]`, state-push `{Y/W/L/.precision ...}`) —
    //     emit immediately; return `None` so `parse_expr` stops.
    //
    // The original C++ bison grammar emitted bytes at item-reduction time
    // and discarded the arithmetic result — a regression that shipped
    // after the oracle was built. This implementation matches what the
    // oracle bytes show: arithmetic composes, expr emits once. See
    // `docs/investigations/2026-04-19-iffcomp-offsetof-arithmetic.md`.

    fn parse_expr(&mut self) -> Result<()> {
        let Some(first) = self.parse_item_maybe_term()? else {
            return Ok(()); // non-arithmetic item already emitted
        };
        let mut terms: Vec<SignedTerm> = first;
        loop {
            let op = self.peek()?;
            let sign = match op {
                Token::Plus => {
                    self.consume()?;
                    1
                }
                Token::Minus => {
                    self.consume()?;
                    -1
                }
                _ => break,
            };
            let Some(rhs) = self.parse_item_maybe_term()? else {
                return Err(IffError::Parse {
                    at: Pos::default(),
                    msg: "right-hand side of '+'/'-' must be an arithmetic term \
                         (integer, .offsetof, or .sizeof)"
                        .into(),
                });
            };
            // Distribute the outer sign across all terms the RHS produced.
            for st in rhs {
                terms.push(SignedTerm {
                    sign: sign * st.sign,
                    term: st.term,
                });
            }
        }
        self.w.emit_expr(terms)?;
        Ok(())
    }

    /// Parse the addend expression inside `.offsetof(path, <expr>)`. This is
    /// a sub-grammar that accepts any arithmetic expression — the 2nd
    /// parameter of `.offsetof` was originally designed as the workaround for
    /// broken top-level `+`/`-`, so expressions like `.offsetof(X, -.offsetof(Y))`
    /// are the idiomatic way to express "X's offset relative to Y". Returns
    /// the terms that should be added to the enclosing offsetof's term list.
    fn parse_addend_expr(&mut self) -> Result<Vec<SignedTerm>> {
        // Optional leading sign.
        let leading_sign = match self.peek()? {
            Token::Plus => {
                self.consume()?;
                1
            }
            Token::Minus => {
                self.consume()?;
                -1
            }
            _ => 1,
        };
        let Some(first) = self.parse_item_maybe_term()? else {
            return Err(IffError::Parse {
                at: Pos::default(),
                msg: ".offsetof addend must be an arithmetic expression \
                     (integer, .offsetof, or .sizeof, possibly with +/-)"
                    .into(),
            });
        };
        let mut terms: Vec<SignedTerm> = first
            .into_iter()
            .map(|st| SignedTerm {
                sign: leading_sign * st.sign,
                term: st.term,
            })
            .collect();
        loop {
            let sign = match self.peek()? {
                Token::Plus => {
                    self.consume()?;
                    1
                }
                Token::Minus => {
                    self.consume()?;
                    -1
                }
                _ => break,
            };
            let Some(rhs) = self.parse_item_maybe_term()? else {
                return Err(IffError::Parse {
                    at: Pos::default(),
                    msg: ".offsetof addend +/- RHS must be arithmetic".into(),
                });
            };
            for st in rhs {
                terms.push(SignedTerm {
                    sign: sign * st.sign,
                    term: st.term,
                });
            }
        }
        Ok(terms)
    }

    fn parse_expr_list(&mut self) -> Result<()> {
        loop {
            match self.peek()? {
                Token::RBrace | Token::Eof => break,
                _ => {
                    self.parse_expr()?;
                }
            }
        }
        Ok(())
    }

    /// Consume one item. Arithmetic items (Integer, .offsetof, .sizeof)
    /// return `Some(Vec<SignedTerm>)` and emit nothing — the caller
    /// accumulates them into a compound expression and flushes via
    /// `Writer::emit_expr`. A single item can produce multiple terms when
    /// it carries an inline arithmetic addend (see `.offsetof(X, <expr>)`).
    /// Non-arithmetic items emit directly and return `None`.
    fn parse_item_maybe_term(&mut self) -> Result<Option<Vec<SignedTerm>>> {
        self.trace("item");
        let tok = self.peek()?;
        match tok {
            Token::LBrace => {
                self.parse_state_push()?;
                Ok(None)
            }
            Token::Real { val, precision } => {
                self.consume()?;
                let prec = precision.unwrap_or(self.top_state().precision);
                self.w.out_fixed(val, prec);
                Ok(None)
            }
            Token::Integer { val, width } => {
                self.consume()?;
                let width = if width == 0 {
                    self.top_state().size_override as u8
                } else {
                    width
                };
                // For non-int32 widths, emit directly at the token's width
                // and return None — arithmetic only makes sense for int32.
                // This preserves byte-for-byte compat for `42y` / `42w`
                // sequences that never participate in arithmetic.
                if width != 4 {
                    let s = val as i64;
                    match width {
                        1 => {
                            if s < i8::MIN as i64 || s > u8::MAX as i64 {
                                return Err(IffError::Parse {
                                    at: Pos::default(),
                                    msg: "value doesn't fit in int8".into(),
                                });
                            }
                            self.w.out_int8(val as u8);
                        }
                        2 => {
                            if s < i16::MIN as i64 || s > u16::MAX as i64 {
                                return Err(IffError::Parse {
                                    at: Pos::default(),
                                    msg: "value doesn't fit in int16".into(),
                                });
                            }
                            self.w.out_int16(val as u16);
                        }
                        _ => {
                            return Err(IffError::Parse {
                                at: Pos::default(),
                                msg: format!("bad width {}", width),
                            });
                        }
                    }
                    return Ok(None);
                }
                // Width = 4: treat as arithmetic term so `42l + 10l` and
                // `$Nl + .offsetof(X)` compose correctly.
                let s = val as i64;
                if s < i32::MIN as i64 || s > u32::MAX as i64 {
                    return Err(IffError::Parse {
                        at: Pos::default(),
                        msg: "value doesn't fit in int32".into(),
                    });
                }
                Ok(Some(vec![SignedTerm {
                    sign: 1,
                    term: Term::Const(s),
                }]))
            }
            Token::String { .. } => {
                self.parse_string_list()?;
                Ok(None)
            }
            Token::LBrack => {
                self.parse_file_include()?;
                Ok(None)
            }
            Token::CharLit(v) => {
                self.consume()?;
                self.w.out_id(v);
                Ok(None)
            }
            Token::Timestamp => {
                self.consume()?;
                let secs = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .map(|d| d.as_secs() as i64)
                    .unwrap_or(0);
                self.w.out_timestamp(secs);
                Ok(None)
            }
            Token::Offsetof => Ok(Some(self.parse_offsetof_terms()?)),
            Token::Sizeof => {
                let path = self.parse_sizeof_term()?;
                Ok(Some(vec![SignedTerm {
                    sign: 1,
                    term: Term::Sizeof { path },
                }]))
            }
            _ => Err(IffError::Parse {
                at: Pos::default(),
                msg: format!("unexpected {} in item", tok.name()),
            }),
        }
    }

    fn parse_state_push(&mut self) -> Result<()> {
        self.consume()?; // '{'
        let top = self.top_state();
        let mut new = State {
            size_override: top.size_override,
            precision: top.precision,
        };
        match self.peek()? {
            Token::SizeY => {
                self.consume()?;
                new.size_override = 1;
            }
            Token::SizeW => {
                self.consume()?;
                new.size_override = 2;
            }
            Token::SizeL => {
                self.consume()?;
                new.size_override = 4;
            }
            Token::Precision => {
                self.consume()?;
                self.expect(&Token::LParen, "'(' after .precision")?;
                let ps = self.expect_prec_spec("precision specifier")?;
                self.expect(&Token::RParen, "')' closing .precision")?;
                new.precision = ps;
            }
            other => {
                return Err(IffError::Parse {
                    at: Pos::default(),
                    msg: format!(
                        "expected Y/W/L or .precision inside '{{ … }}' block, got {}",
                        other.name()
                    ),
                });
            }
        }
        self.push_state(new);
        self.parse_expr_list()?;
        self.expect(&Token::RBrace, "'}' closing state push")?;
        self.pop_state();
        Ok(())
    }

    fn parse_string_list(&mut self) -> Result<()> {
        let (first_body, first_size) = self.expect_string("STRING")?;
        if first_size > 0 {
            self.w.out_string_pad(&first_body, first_size);
        } else {
            self.w.out_string(&first_body);
        }
        while matches!(self.peek()?, Token::String { .. }) {
            let (body, _) = self.expect_string("STRING")?;
            self.w.out_string_continue(&body);
        }
        Ok(())
    }

    fn parse_file_include(&mut self) -> Result<()> {
        self.consume()?; // '['
        self.start_pos_override = 0;
        self.length_override = u64::MAX;

        let (path, _) = self.expect_string("filename in '[ … ]'")?;

        loop {
            match self.peek()? {
                Token::Start | Token::Length => self.parse_extract_spec()?,
                _ => break,
            }
        }
        self.expect(&Token::RBrack, "']' closing file include")?;
        self.w
            .out_file(&PathBuf::from(&path), self.start_pos_override, self.length_override)
    }

    fn parse_extract_spec(&mut self) -> Result<()> {
        let tok = self.consume()?;
        self.expect(&Token::LParen, "'(' after extract spec")?;
        let (n, _) = self.expect_integer("integer in extract spec")?;
        self.expect(&Token::RParen, "')' closing extract spec")?;
        match tok {
            Token::Start => self.start_pos_override = n,
            Token::Length => self.length_override = n,
            _ => unreachable!(),
        }
        Ok(())
    }

    fn parse_chunk_specifier(&mut self) -> Result<String> {
        let mut path = String::new();
        while matches!(self.peek()?, Token::DoubleColon) {
            self.consume()?;
            let id = self.expect_char_lit("CHAR_LITERAL after '::'")?;
            path.push_str("::'");
            path.push_str(&id_name(id));
            path.push('\'');
        }
        if path.is_empty() {
            return Err(IffError::Parse {
                at: Pos::default(),
                msg: "expected chunkSpecifier starting with '::'".into(),
            });
        }
        Ok(path)
    }

    /// Parse `.offsetof(<path>)` or `.offsetof(<path>, <addend-expr>)`.
    /// Returns the ordered list of SignedTerms that the caller should splice
    /// into its expression: the primary offsetof term first, then any addend
    /// terms. When the addend is a bare integer literal we fold it into the
    /// offsetof's `addend` field (backward-compat with the original int-only
    /// 2nd-parameter form); when it's a full expression we spread its terms
    /// into the outer sum.
    fn parse_offsetof_terms(&mut self) -> Result<Vec<SignedTerm>> {
        self.consume()?; // .offsetof
        self.expect(&Token::LParen, "'(' after .offsetof")?;
        let path = self.parse_chunk_specifier()?;
        let mut terms: Vec<SignedTerm> = Vec::new();
        if matches!(self.peek()?, Token::Comma) {
            self.consume()?;
            // Look ahead: if the next tokens are exactly `INTEGER RPAREN`,
            // take the fast path — fold the integer into the addend field
            // and avoid building a compound expression. This keeps the
            // existing test fixtures (`.offsetof(X, 8)`) on the simpler
            // resolution path. Anything more complex (including leading
            // `-` before an integer or any symbolic term) goes through
            // the full addend-expression path.
            let fold_int = matches!(self.peek()?, Token::Integer { .. })
                && matches!(self.peek1()?, Token::RParen);
            if fold_int {
                let (n, _) = self.expect_integer("addend integer in .offsetof")?;
                terms.push(SignedTerm {
                    sign: 1,
                    term: Term::Offsetof {
                        path,
                        addend: n as i32,
                    },
                });
            } else {
                terms.push(SignedTerm {
                    sign: 1,
                    term: Term::Offsetof { path, addend: 0 },
                });
                let addend_terms = self.parse_addend_expr()?;
                terms.extend(addend_terms);
            }
        } else {
            terms.push(SignedTerm {
                sign: 1,
                term: Term::Offsetof { path, addend: 0 },
            });
        }
        self.expect(&Token::RParen, "')' closing .offsetof")?;
        Ok(terms)
    }

    fn parse_sizeof_term(&mut self) -> Result<String> {
        self.consume()?; // .sizeof
        self.expect(&Token::LParen, "'(' after .sizeof")?;
        let path = self.parse_chunk_specifier()?;
        self.expect(&Token::RParen, "')' closing .sizeof")?;
        Ok(path)
    }
}

/// Loose discriminant comparison — the parser's `expect()` helper only cares
/// that the token is the right *kind*, not that payload fields match. Built-in
/// `std::mem::discriminant` works because the variants are well-behaved but
/// is noisier than this helper.
fn discriminant_eq(a: &Token, b: &Token) -> bool {
    std::mem::discriminant(a) == std::mem::discriminant(b)
}
