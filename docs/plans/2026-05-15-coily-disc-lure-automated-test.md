# Plan — Coily disc-lure automated test

## Context

The disc-lure mechanic (commit `1f4b272`) can't be verified by interactive play on the dev machine. The repo already has a debug-bridge test harness (`tests/`, port 7778) that speaks JSON over TCP to a running `wf_game` instance. The bridge can write mailboxes directly — so we can teleport the snake to a disc coord with cooldown=0, then watch for the retirement mailboxes and +500 score without any human input.

## Approach

New file: **`tests/test_disc_lure.py`** — three pytest tests using the existing session-scoped `bridge` fixture from `conftest.py`.

**Setup per test (shared helper):**
1. `bridge.watch(...)` for score (mb 70), `COILY_SNAKE_ACTIVE_MB` (mb 574), `COILY_MB_PHASE_GLOBAL` (mb 543)
2. `set_mailbox(70, 0)` — zero score so delta is unambiguous
3. Set snake active: mb 543 = 2, mb 574 = 1, mb 529 (`_CS_MB_PHASE`) = 1
4. Set snake position: mb 526 (`_CS_MB_ROW`), mb 527 (`_CS_MB_COL`) = target coord
5. `set_mailbox(528, 0)` — cooldown=0 forces a landing tick next frame

**Teardown:** set mb 529 = 0 to stop the snake script.

### Test 1 — disc-L retirement
- Set snake to (row=1, col=−1)
- Assert `COILY_SNAKE_ACTIVE_MB` → 0 within 3 s
- Assert score → 500
- Assert `COILY_MB_PHASE_GLOBAL` → 0

### Test 2 — disc-R retirement
- Set snake to (row=1, col=2)
- Same assertions

### Test 3 — regression: normal coord does NOT retire
- Set snake to (row=2, col=1), cooldown=0, phase=1
- `time.sleep(0.5)` — let a few frames tick
- Assert `COILY_SNAKE_ACTIVE_MB` is still 1 (no spurious retire)
- Teardown: set mb 529 = 0

## Mailbox constants (all global, from `blender_create_qbert.py`)

| Symbol | MB# |
|--------|-----|
| Score | 70 |
| `_CS_MB_COOLDOWN` | 528 |
| `_CS_MB_PHASE` | 529 |
| `_CS_MB_ROW` | 526 |
| `_CS_MB_COL` | 527 |
| `COILY_MB_PHASE_GLOBAL` | 543 |
| `COILY_SNAKE_ACTIVE_MB` | 574 |

## Critical files

- **`tests/test_disc_lure.py`** — new file (create)
- `tests/conftest.py` — provides `bridge` fixture (read-only reference)
- `tests/debug_bridge_client.py` — `BridgeClient.set_mailbox`, `watch`, `wait_for_mailbox`

## Verification

```bash
cd /home/will/WorldFoundry.2026-new-level/tests
DISPLAY=:0 pytest test_disc_lure.py -v
```

Requires: `DISPLAY=:0`, `engine/wf_game` built, `wflevels/qbert_practice-standalone.iff` present.
