# Add `read-actor-mailbox` to the scripting engines

## Context

`write-actor-mailbox` lets a script write mailbox `idx` on *another* actor
(zForth custom syscall 2 / `130 sys`, `( val idx actor_idx -- )`,
`engine/stubs/scripting_zforth.cc:955`), but there is **no cross-actor read** in
zForth. Cross-actor reads today need a "push to global" indirection (actor A
writes its `X_POS` to a shared global mailbox each tick so actor B can read it).
The fix: add `read-actor-mailbox` so B can pull `<A_idx> INDEXOF_X_POS
read-actor-mailbox` directly. Reads are pure observation across the actor
boundary — no encapsulation concern.

**The TODO was stale on two points (verified):**
- It said custom syscall id **3** is free — it is **not**: FSN claimed custom
  3-7 / sys 131-135 (`scripting_zforth.cc:67`). `read-actor-mailbox` needs the next
  free id (24-29 are free).
- It said Lua/JS need the primitive — they **already** have it: `read_mailbox`
  takes an optional trailing actor arg in Lua (`scripting_lua.cc:79`) and
  jerryscript (`scripting_jerryscript.cc:34`). Only **zForth** (no cross-actor
  read at all) and **WASM/wamr** (`read_mailbox(i32)` is current-actor-only,
  `scripting_wamr.cc:97`) are missing it.

## Design

### zForth — the real gap (primary)
Add a new word `read-actor-mailbox ( idx actor_idx -- val )` — symmetric with
`write-actor-mailbox` (actor on top of stack, matching the Lua/JS `(mailbox,
actor)` order). Use the next free custom id **24 / `152 sys`**.

- **Handler** (`scripting_zforth.cc`, place right after the `custom == 2`
  write-actor-mailbox block so the four mailbox syscalls stay grouped; note in a
  comment that the id is 24 because 3-23 are claimed):
  ```cpp
  } else if (custom == 24) {
      // read-actor-mailbox ( idx actor_idx -- val ) — symmetric partner of
      // write-actor-mailbox (custom 2). id 24 (3-23 are FSN/etc.).
      int actorIdx = (int)zf_pop(ctx);
      int idx      = (int)zf_pop(ctx);
      float v = 0.0f;
      if (g_mgr) { Mailboxes& mb = g_mgr->LookupMailboxes(actorIdx);
                   v = mb.ReadMailbox(idx).AsFloat(); }
      zf_push(ctx, (zf_cell)v);
  }
  ```
  This mirrors the existing `read-mailbox` (custom 0) read path + the
  `write-actor-mailbox` actor-lookup path — no new API.
- **Word definition** (after `scripting_zforth.cc:1369`):
  `zf_eval(&g_ctx, ": read-actor-mailbox 152 sys ;");` with the same error check.
- **Syscall-map comments**: add the line to the header table
  (`scripting_zforth.cc:12-14`) and `engine/neural-forth/neural_forth.h:13`.

### WASM (wamr) — parity for the one missing engine
Add a `read_actor_mailbox(i32 idx, i32 actor) -> f32` host function: define
`host_read_actor_mailbox` (mirrors `host_read_mailbox` `scripting_wamr.cc:99` but
reads `LookupMailboxes(actor)` instead of `g_curObj`), register a `(i32,i32)->f32`
func type, and add an `else if (nm_str == "read_actor_mailbox")` branch in the
import-matching loop (`scripting_wamr.cc:244`). Update the ABI doc comment
(`:16`). *(Optional — wamr is non-canonical per the "zForth only for new level
scripts" convention; can be dropped if you'd rather keep this zForth-only.)*

### Lua / JS — confirm, don't duplicate
Lua + jerryscript already accept the optional actor arg → no change. Confirm
`scripting_quickjs.cc` does too; if its `read_mailbox` is current-actor-only, add
the same `if (argc >= 2) actor = args[1]` branch jerryscript uses.

## Files

| File | Change |
|------|--------|
| `engine/stubs/scripting_zforth.cc` | `read-actor-mailbox` handler (custom 24), word def, syscall-map comment |
| `engine/neural-forth/neural_forth.h` | add the syscall to the doc list |
| `engine/stubs/scripting_wamr.cc` | `host_read_actor_mailbox` + register (parity) |
| `engine/stubs/scripting_quickjs.cc` | optional-actor arg if missing (confirm) |

## Regression test

A Forth round-trip proving the new word resolves a *cross-actor* read. Drive it
where a level + mailbox manager exist — extend the existing `wfmut` smoke
(`engine/mutation/wfmut_smoke.cpp` `run_mailbox_tests`, runs on a loaded level via
`task test-wfmut`): pick the player actor, run a one-line script through the zForth
interpreter that does `<val> <scratch_idx> <player_idx> write-actor-mailbox` then
`<scratch_idx> <player_idx> read-actor-mailbox`, and assert the read returns the
written sentinel. Fails before the fix (word undefined → `ZF_ABORT_NOT_A_WORD`),
passes after. (If evaluating an ad-hoc Forth string on an actor isn't reachable
from the smoke, fall back to a focused interpreter unit test that `Init`s the
zForth interpreter with a stub `MailboxesManager`, writes a value, evals
`read-actor-mailbox`, and checks the result.)

## Verification

1. **Build**: `task build` (engine) → clean. (zForth is the default engine,
   `WF_FORTH_ENGINE=zforth`.)
2. **Test bites / passes**: `task test-wfmut` → the new round-trip case passes;
   temporarily rename the word def to confirm it fails (word-not-found) before the
   handler/def, then restore.
3. **Manual**: in a running level, a Director script reading another actor's
   `INDEXOF_X_POS` via `read-actor-mailbox` returns the live value (no push-to-global
   needed) — e.g. wire it into the qbert/SMB director and observe the tracked value.

## Out of scope
- Lua / jerryscript (already support cross-actor read).
- A cross-actor *write* for WASM (this task is the read primitive; wamr also lacks
  `write_actor_mailbox`, but that's a separate parity gap).
