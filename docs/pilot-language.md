# PILOT for World Foundry — language specification (v1)

> Authoritative grammar + semantics for the PILOT scripting language. The contract that both
> backends (the Phase 1 Python reference driver and the Phase 2+ C++ `pilot_core`) must satisfy.
> Plan: [`docs/plans/2026-05-30-pilot-for-world-foundry-in-engine-object-script-la.md`](plans/2026-05-30-pilot-for-world-foundry-in-engine-object-script-la.md).

PILOT (*Programmed Inquiry, Learning, Or Teaching*) is a 1960s line-oriented language built around
one loop: **emit a stimulus → await a response → classify it → branch**. World Foundry runs it on
two surfaces from **one shared interpreter core**:

- **in-engine** (`MailboxHost`) — a per-actor `{Script}` (`kDispatch` slot 6), frame-resumable: a
  dialogue/cutscene/AI state machine. Blocking verbs *suspend* the actor's program counter and
  resume next frame (it runs on the game thread and must never block).
- **external** (`BridgeHost`) — a host program driving a running engine over the TCP debug bridge for
  tutorials, cutscene/demo direction, and headless verification. Blocking verbs *block* the driver
  thread on the socket.

Only the **effect verbs** differ between the two, and only in their tail; the parser, control flow,
variables, match flag, and expression evaluator are identical.

---

## 1. Lexical structure

One statement per line. A line is:

```
[ *label ]  [ VERB [Y|N] [ (guard-expr) ] : operand ]
```

- **Labels** start with `*` (`*top`, `*fail`) and may sit alone or precede a statement. They are jump
  targets for `J:` / `U:`; resolved once at parse time → O(1) jumps.
- **Verb** is a 1–2 letter mnemonic (table §5). The colon is mandatory and separates verb from operand.
- **Conditioner** `Y` / `N` immediately after the verb runs the statement only if the persistent match
  flag is set / clear (`TY:`, `JN:*again`).
- **Guard** `(expr)` is an extra boolean AND-condition (`T(#hp>0):still alive`). Evaluated VM-local.
- Blank lines are ignored. There is no line-continuation; one logical statement per physical line.

### Comments and the sigil

`R:` (Remark) is a comment. The **first** non-blank line of an in-level PILOT script must be the
sigil remark `R:pilot` — a valid PILOT comment that the engine's content-sniff uses to route the
script to slot 6 (analogous to zForth's `\ wf`). It is stripped before execution.

### Harness directives

Conformance-corpus expectations ride inside `R:` remarks with an `@` prefix, so they are ordinary
comments to the interpreter but machine-readable to the test runner (§6).

---

## 2. Variables, literals, constants

| Kind | Sigil | Backing type | Notes |
|---|---|---|---|
| Numeric variable | `#name` | `Scalar` | float on PC dev, fixed-point on target. Default `0`. |
| String variable | `$name` | host string | **host-RAM only — never written to a mailbox.** Default `""`. |
| `#last` | (predefined `#`) | `Scalar` | the most recent `A:` / `WM:` result. |

**Literals:** numbers `40`, `40.0`, `0x2000`, `0.25`; strings `"double-quoted"`.

**Predefined constants** (resolved at parse time from the engine's broadcast tables — see
[`scripting_stub.cc`](../engine/stubs/scripting_stub.cc) `mailboxIndexArray` / `joystickArray`):

- **Mailbox names**, exposed **prefix-free** — `X_POS`, `Y_POS`, `Z_POS`, `XSPEED`, `GOLD`,
  `HITPOINTS`, `ALIVE`, `ACTOR_INDEX`, `TIME`, … The engine hands PILOT the `INDEXOF_`-prefixed
  array; PILOT registers **both** `INDEXOF_GOLD` *and* bare `GOLD`. PILOT is the first engine to
  preview the global de-prefixing the project wants (the `INDEXOF_` prefix is a known wart —
  [`TODO.md` → rename to `MB_`](../TODO.md)); we alias, we do not propagate the prefix into scripts.
- **Button names**, both forms — `BTN_UP`/`BTN_DOWN`/`BTN_LEFT`/`BTN_RIGHT`/`BTN_A`…`BTN_K` aliasing
  `JOYSTICK_BUTTON_*`. (`BTN_RIGHT = JOYSTICK_BUTTON_RIGHT = 8192 = 0x2000`.)

**Actor references are numeric** — wherever a verb takes an *actor* operand (`WA:`, `WM:`, `SP:`, …)
or `mb(idx, actor)`, it is a numeric expression (the actor's index). In-engine, the running actor's
own index is implicit (and readable as `mb(ACTOR_INDEX)`); externally, bind a discovered actor with
`R:@needs player as #P` and pass `#P`.

---

## 3. Expressions

Used in `C:` right-hand sides, `(guard)` clauses, `M:` relational forms, and numeric verb operands.

- **Arithmetic:** `+` `-` `*`, unary `-`, parentheses.
- **Division — two operators, explicitly distinct** (PILOT defines its own; it does *not* inherit
  zForth's float-`/` gotcha):
  - `/` → `Scalar` division (measured quantities), e.g. `#d = #dist / 2`.
  - `//` → truncating **integer** division (index/counter math), e.g. `#row = #i // 3`.
- **Comparison** (yield `1` / `0`): `=` `<>` `<` `<=` `>` `>=`.
- **Mailbox accessor** `mb(idxExpr)` reads the **current actor's** mailbox; `mb(idxExpr, actorExpr)`
  reads another actor's. As a `C:` left-hand side it **writes** (§5, `C:`). Index is range-checked
  against `GLOBAL_USER_MAX` (1900) and the per-actor range; out-of-range reads yield `0` and warn.
- Boolean combinators `&` (and) `|` (or) `!` (not) over `0`/non-`0`.

`mb()` is the single mailbox primitive; transform/prop writes go through the `SP:` / `SF:` verbs, not
overloaded expression syntax.

---

## 4. Execution model

### In-engine (frame-resumable)
Each actor owns a persistent program counter, match flag, call stack, variable maps, accept buffer,
and `waitUntil`, keyed by `objectIndex`. The immutable parsed program is cached by the `{Script}`
source pointer (stable for the level's lifetime). `RunScript` is called once per actor per frame; the
VM executes up to `kMaxStmtsPerFrame = 256` statements then **suspends** (resumes next frame — it does
not abort). Blocking verbs (`A:`, `PA:`, `WM:`, `WT:`) park the PC until satisfied. `E:` at top level
marks the program `Halted` (no auto-restart; loop explicitly with `J:*top`). Call depth caps at 64.

### External (blocking)
The same VM, but the `Await` backend blocks the driver thread on the socket instead of yielding.
Engine-control verbs (`PS:`/`PR:`/`ST:`/`SH:`/…) map to debug-bridge ops.

---

## 5. Verb reference

**Standard PILOT verbs**

| Verb | Form | In-engine (`MailboxHost`) | External (`BridgeHost`) |
|---|---|---|---|
| `T:` | `T:text` | emit text + newline → **stderr on desktop, no-op on target** (no HUD-text mailbox exists yet; see plan Phase 4). Interpolation below. | print to operator console |
| `TH:` | `TH:text` | same, no trailing newline | console, no newline |
| `A:` | `A:#var` / `A:$var` | **await the engine**: suspend until the bound source updates → deposit in `#last` + accept buffer (+ named var) | block on the awaited source |
| `M:` | `M:list` or `M:EXPR RELOP EXPR` | list form: string-match accept buffer vs comma list; relational form: set match flag from the comparison | identical (client-side) |
| `C:` | `C:LHS = EXPR` | assign. LHS = `#name` / `$name` / `mb(idx[,actor])`. `mb(...) =` writes a mailbox. | identical; `mb(...) =` → `set_mailbox` |
| `J:` | `J:*label` | jump (O(1)) | jump |
| `U:` | `U:*label` | call subroutine (push return) | call |
| `E:` | `E:` | return from `U:`; top level → `Halted` (exit 0 external) | return / exit 0 |
| `EX:` | `EX:N` | n/a (assert) | exit driver with code `N` (assertion failure path) |
| `Y:`/`N:` | suffix | gate on match flag (`TY:`, `JN:*l`) | identical |
| `R:` | `R:text` | comment; `R:pilot` sigil; `R:@…` harness directive | comment |
| `PA:` | `PA:secs` | suspend `secs` **seconds** (`LevelClock` via `TIME`=1906); not ticks | operator breakpoint (sleep / getchar) |

**`T:` / `TH:` interpolation:** `$name` → string var; `$#name` → numeric var (formatted); `$$` → literal `$`.

**WF engine-control extension verbs** (colon form; each external verb = exactly one bridge op; unknown
ops are silently ignored engine-side so v1 needs no new engine C++ on the bridge path):

| Verb | Form | In-engine | External bridge op |
|---|---|---|---|
| `PS:` | `PS:` | no-op/assert | `{"op":"pause"}`, block for `paused` |
| `PR:` | `PR:` | no-op/assert | `{"op":"resume"}` ⚠ feeds one large dt — prefer staying paused + `ST:` |
| `ST:` | `ST:N` | no-op/assert | `{"op":"step","frames":N}` (deterministic; default 1) |
| `IN:` | `IN:slot BITS [held N]` | write the RAW joystick mailbox | `{"op":"inject_input","slot","value","duration_frames"}` (`held -1`=sticky, omitted=one frame) |
| `WM:` | `WM:actor mbx RELOP val [timeout S]` | `Await({Mailbox,op,val})` coroutine → `#last` | `watch` + **relational poll** → `#last` |
| `WB:` | `WB:op [timeout S]` | n/a | `wait_for(op==…)` (`paused`/`screenshot_done`/`picked`/`error`/`reverted`) |
| `WT:` | `WT:secs` | `waitUntil = mb(TIME)+secs` coroutine | watch `TIME` **at idx=1** + relational `>=` poll. LevelClock seconds — the clock advances only on stepped frames, so interleave `ST:` when driving a *paused* engine |
| `SP:` | `SP:actor x y z` | `SetTransform` | `{"op":"scene:set_transform"}` |
| `SF:` | `SF:actor key value` | `SetProp` | `{"op":"scene:set_prop"}` |
| `SM:` | `SM:actor mbx value` | `SetMailbox` | `{"op":"set_mailbox"}` |
| `WA:` | `WA:actor mbx [off]` | n/a | `{"op":"watch"}` / `{"op":"unwatch"}` |
| `SH:` | `SH:filename` | n/a | `{"op":"screenshot"}` → await `screenshot_done` |
| `SR:` | `SR:actor source` | n/a | `{"op":"reload_script"}` (language-aware, plan Phase 5) |
| `SG:` | `SG:vert frag` | n/a | `{"op":"set_shader"}` |
| `PK:` | `PK:ox oy oz dx dy dz` | n/a | `{"op":"scene:pick"}` → await `picked` → `#last` |
| `UN:`/`RV:` | `UN:` / `RV:` | n/a | `{"op":"undo_step"}` / `{"op":"revert_all"}` |
| `NW:`/`DL:`/`BT:` | — | (pooled-actor activate via `SM:`) | **reserved (v2)** — no spawn/despawn/batch op over TCP today; do not fake |

> **Reserved for Phase 6 (turtle graphics):** `GR:` (and the 3D `F`/`YAW`/`PITCH`/`ROLL`/`PUSH`/`POP`
> turtle vocabulary, degrees-default angles). Not part of v1 — see the plan's deferred follow-ups.

### Three load-bearing semantics (verified against the engine)

1. **Relational await is a new primitive.** The existing `wait_for_mailbox` helper is *exact-equality
   only* (`abs(cur-expected) < 1e-3`). `WM:`/`WT:`'s `>`/`>=`/`<` require a **new** poll over the
   watched value evaluating the `RelOp`. Do not implement `WM:` on top of `wait_for_mailbox`.
2. **Globals are watched at idx=1.** `BroadcastMailboxes` only emits for a *valid actor index*; a
   global/system mailbox watched at idx 0 yields nothing. `WA:`/`WM:`/`mb()` auto-route global
   mailboxes (below the per-actor range) to **idx=1** (the convention every `verify_smb_*.py` uses);
   per-actor mailboxes use the actor's own index.
3. **`IN:` targets exactly one slot.** Injecting on `joystick1_raw` (1909) does **not** populate
   `*_RAW_JUSTPRESSED` (1910), and a sticky inject never returns to 0 on its own. Edge-sensitive
   gameplay needs injecting on the JUSTPRESSED slot too, or an explicit press→release pulse across
   separate `ST:` frames.

---

## 6. Conformance corpus & directives

Each `tests/pilot/*.pilot` file is one scenario. Expectations are `R:@` remark directives:

| Directive | Meaning |
|---|---|
| `R:@tier vm` | runs against a **mock host** — pure language, deterministic, no engine |
| `R:@tier engine` | runs against a live `wf_game` over the bridge |
| `R:@desc text` | human description |
| `R:@level NAME` | (engine) level `.iff` to boot (default: the test level) |
| `R:@needs ACTOR as #VAR` | (engine) discover actor `ACTOR` from boot log; bind its index to numeric `#VAR` |
| `R:@expect-exit N` | required process/driver exit code |
| `R:@expect-out TEXT` | `T:`/`TH:` output must contain `TEXT` (repeatable) |
| `R:@expect-no-out TEXT` | output must **not** contain `TEXT` |
| `R:@screenshot NAME.png` | (engine) assert a `screenshot_done` for `NAME.png` was produced |

**Tiers** let the language (parse, `C:`, `M:`, control flow, conditioners, guards, `PA:` against a
mock clock) be validated with zero engine — fast and deterministic — while engine integration
(`IN:`/`ST:`/`WM:`/`SH:`) is exercised against a live build. Both backends run the same corpus; that
is what keeps the in-level interpreter and the external driver from drifting.

Exit-code convention: a program that runs off the end or hits a top-level `E:` exits `0`. Use `EX:N`
on a failure branch (typically reached via `JN:*fail`) for a nonzero code.
