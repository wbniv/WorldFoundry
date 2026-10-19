---
name: Verify scripting dialect across multiple files before claiming canonical
description: Don't assume which scripting dialect is canonical from one example. Check .s, .aib, .fth, and .lev embedded scripts before stating it.
type: feedback
originSessionId: 1bb8f4e2-9146-4504-8289-793c96be779b
---
When working on a project that's mid-migration between scripting dialects (e.g. WF moving from Scheme `.s` to zForth), don't take any one example file as canonical. The user has corrected this twice in one conversation:

1. I pushed Fennel based on one Plan agent's report; user asked "why are you interested in fennel" — the answer was just that Fennel was the freshest sigil I'd seen. Should have checked existing examples first.
2. I claimed "every working game script in wflevels/ is Lisp/Scheme dialect" based on `cart.s` / `fury1.s` / `shell.s`. User corrected: snowgoons and the shell HAVE been converted to Forth. Forth versions live in `.aib` files, `.fth` files, and embedded inside `.lev` Script fields — not just in `.s` files.

**Why:** mid-migration codebases have multiple coexisting dialects; pre-conversion samples remain on disk. Picking the wrong "canonical" sets the wrong default for new code and earns a correction.

**How to apply:** before stating "the language is X" in a plan or doc, grep for evidence in *all* relevant file types. For WF specifically:
- `find wflevels -name "*.s" -o -name "*.aib" -o -name "*.fth"` — Forth-converted scripts often have different extensions
- `grep -rln '\\\\ wf' wflevels/` — Forth scripts embedded in `.lev` files use `\ wf` sigil
- `find wfsource -name "*.fth"` — engine-side Forth code (e.g. `shell.fth`) signals the canonical direction
- `find scripts -name "*forth*"` — migration scripts indicate the conversion target
