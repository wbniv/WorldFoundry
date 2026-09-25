# Forth comments and script loading

WF's shared zForth bootstrap now provides both `( parenthesised comments )` and
backslash line comments. No level needs to define or strip these. Backslash
comments end at LF, CR or the end of the supplied source, including an empty
comment consisting only of the backslash. Parenthesised comments end at the first
closing parenthesis; they are not nested.

Actor scripts retain the existing convention: definitions first, then a body
that executes each frame. The optional opening `\ wf` marker is removed only
when it occupies its own line. Normal loading and hot reload use the same
source-boundary helper. The compiled per-frame entry is cached.

The helper recognizes comment words and the plain `s"` / `."` string forms when
finding the final definition terminator. It ignores delimiters inside their
contents and respects word names following `:`, tick and `postpone`. This does
not install a string library or support arbitrary user-defined parsing words.
Plain quoted strings have no C-style backslash escape handling. Strings can
contain semicolons or backslashes without the loader stripping them.

A generated entry ends with a newline before its closing semicolon, so a final
line comment without a newline cannot consume that terminator.

Hot reload still appends dictionary words and is not transactional: a failed
compile can have changed definitions even if the previous actor entry remains.
Parser redesign, reload rollback/reclamation and richer diagnostics are deferred
in [the plan](plans/2026-09-25-forth-comments-and-script-loading.md).

Run `task test-forth-source` for the focused source-boundary/VM regression.
After building the engine and condo level, run
`python3 tests/verify_forth_reload.py` for actual engine loading and debug reload.
