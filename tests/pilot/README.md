# PILOT conformance corpus

The contract every PILOT backend must satisfy — the Phase 1 Python reference driver
(`pilot_driver.py`) and the Phase 2+ C++ `pilot_core`. Both run this same corpus; that is what keeps
the in-level interpreter and the external bridge driver from drifting.

Language spec: [`docs/pilot-language.md`](../../docs/pilot-language.md).
Plan: [`docs/plans/2026-05-30-pilot-for-world-foundry-in-engine-object-script-la.md`](../../docs/plans/2026-05-30-pilot-for-world-foundry-in-engine-object-script-la.md).

## Tiers

- **`@tier vm`** — runs against a **mock host**: pure language semantics (parse, `C:`, `M:`, `J:`/`U:`/`E:`,
  `Y:`/`N:` conditioners, `(guard)`, expressions, division). Deterministic, **no engine** needed.
- **`@tier engine`** — runs against a live `wf_game` over the TCP debug bridge (the `bridge` pytest
  fixture / a standalone launch). Exercises `IN:`/`ST:`/`WM:`/`SH:` and the WF integration.

## Expectation directives (`R:@…` remarks)

| Directive | Meaning |
|---|---|
| `R:@tier vm` \| `R:@tier engine` | which backend tier runs this scenario |
| `R:@desc text` | human description |
| `R:@level NAME` | (engine) level `.iff` to boot |
| `R:@needs ACTOR as #VAR` | (engine) discover `ACTOR` from the boot log; bind its index to `#VAR` |
| `R:@expect-exit N` | required exit code (`0` = ran off the end / top-level `E:`; nonzero via `EX:N`) |
| `R:@expect-out TEXT` | `T:`/`TH:` output must contain `TEXT` (substring; repeatable) |
| `R:@expect-no-out TEXT` | output must **not** contain `TEXT` |
| `R:@screenshot NAME.png` | (engine) a `screenshot_done` for `NAME.png` must be produced |

## Scenarios

| File | Tier | Covers |
|---|---|---|
| `arith.pilot` | vm | `C:` arithmetic, `/` vs `//` division, `T:` interpolation |
| `match_branch.pilot` | vm | `M:` relational sets the flag; `Y`/`N` conditioners |
| `subroutine.pilot` | vm | `U:`/`E:` call & return |
| `guard.pilot` | vm | `(expr)` guard, independent of the match flag |
| `loop.pilot` | vm | `J:*label` loop termination via a guarded jump |
| `walk_right.pilot` | engine | pause → inject RIGHT → step → relational await → match → screenshot |
| `read_global.pilot` | engine | `TIME` global auto-routed to idx=1; relational poll on a stepped clock |

The runner that consumes these directives lands in **Phase 1**. Until then they are the authored
contract; `python3 -c "import ..."` is not yet wired.
