# Q✱bert autopilot — coverage path and Forth script

**Date:** 2026-05-05  
**Level:** `wflevels/qbert_practice`  
**Status:** Ready to build and test

---

## What this is

A Forth autopilot mode embedded in the Q✱bert player script. When mailbox 430
(`AUTOPILOT_ON`) is set to 1, the player ignores the joystick and instead executes a
hardcoded 32-hop sequence that flips all 28 pyramid cubes to state 2, triggering
`ROUND_CLEAR`. Useful for demo mode, regression testing, and tuning the director's
round-clear / respawn flow without needing a human player.

---

## Quick start for a testing agent

### 1. Build the level

```bash
cd /home/will/WorldFoundry.2026-new-level
bash wftools/wf_blender/build_level_binary.sh qbert_practice
```

### 2. Run with the debug bridge

```bash
task run-debug -- wflevels/qbert_practice-standalone.iff
```

### 3. Enable autopilot via the bridge (port 7777)

```python
import socket, json

def send(op):
    s = socket.create_connection(('localhost', 7777))
    s.send((json.dumps(op) + '\n').encode())
    print(s.recv(4096).decode())
    s.close()

send({"op": "set_mailbox", "slot": 430, "value": 1})   # AUTOPILOT_ON = 1
```

### 4. Watch it run

```python
import time
for _ in range(35):
    send({"op": "get_mailbox", "slot": 431})   # AUTOPILOT_STEP, should count 0→31
    send({"op": "get_mailbox", "slot": 413})   # ROUND_CLEAR, fires = 1 when done
    time.sleep(0.5)
```

Expected: AUTOPILOT_STEP counts up one per ~12 ticks (one per hop cooldown), hits 31
on the last hop to (6,0), then stops. ROUND_CLEAR (mb 413) fires = 1. After the 90-tick
countdown the round resets and the autopilot restarts from step 0.

To verify full cube coverage: check mailboxes 200–227 (CUBE_STATE_BASE). All should
reach value 2 before ROUND_CLEAR fires.

---

## Coverage path

The pyramid has 28 cubes in a 7-row triangle. Valid hops are diagonal only:

| Name | Δ(row,col) | Cabinet direction |
|------|------------|-------------------|
| DL   | (+1, 0)    | DOWN  (0x1000)    |
| DR   | (+1,+1)    | RIGHT (0x2000)    |
| UL   | (-1,-1)    | LEFT  (0x4000)    |
| UR   | (-1, 0)    | UP    (0x0800)    |

**Why a Hamiltonian path from (0,0) is impossible:** nodes (6,0) and (6,6) each have
degree 1 (single neighbor). Both must be endpoints of any Hamiltonian path. A path
starting at (0,0) — degree 2 — can only end at one degree-1 node; the other cannot be
an interior node. Minimum revisits needed from (0,0): 2. The path below uses 5 (the
extras cover the apex-flip and the row-6 dead-end corners).

**Apex note:** the cube at (0,0) starts at state 0 (OFF). `QBERT_LANDED` (mb 411) fires
only on hops, not on spawn, so the apex is never flipped unless Q✱bert hops back onto
it. Steps 0–1 deliberately bounce off (1,0) and back to (0,0) to flip the apex.

### 32-hop sequence

```
step  0: DL (+1, 0) -> (1,0)            step 16: DR (+1,+1) -> (5,4)  [row-5 bridge]
step  1: UR (-1, 0) -> (0,0)  *APEX*    step 17: UR (-1, 0) -> (4,4)
step  2: DR (+1,+1) -> (1,1)            step 18: DR (+1,+1) -> (5,5)
step  3: DL (+1, 0) -> (2,1)            step 19: DR (+1,+1) -> (6,6)  [dead-end detour]
step  4: UL (-1,-1) -> (1,0)  *rev*     step 20: UL (-1,-1) -> (5,5)  *rev*
step  5: DL (+1, 0) -> (2,0)            step 21: DL (+1, 0) -> (6,5)
step  6: DL (+1, 0) -> (3,0)            step 22: UL (-1,-1) -> (5,4)  *rev*
step  7: DL (+1, 0) -> (4,0)            step 23: DL (+1, 0) -> (6,4)
step  8: UR (-1, 0) -> (3,0)  *rev*     step 24: UL (-1,-1) -> (5,3)
step  9: DR (+1,+1) -> (4,1)            step 25: DL (+1, 0) -> (6,3)
step 10: UR (-1, 0) -> (3,1)            step 26: UL (-1,-1) -> (5,2)
step 11: DR (+1,+1) -> (4,2)            step 27: DL (+1, 0) -> (6,2)
step 12: UR (-1, 0) -> (3,2)            step 28: UL (-1,-1) -> (5,1)
step 13: UR (-1, 0) -> (2,2)            step 29: DL (+1, 0) -> (6,1)
step 14: DR (+1,+1) -> (3,3)            step 30: UL (-1,-1) -> (5,0)
step 15: DL (+1, 0) -> (4,3)            step 31: DL (+1, 0) -> (6,0)  <- terminal
```

Revisits (5): (0,0) step 1, (1,0) step 4, (3,0) step 8, (5,5) step 20, (5,4) step 22.

---

## Forth script

The script lives inside `blender_create_qbert.py` as the `wf_Script` property of the
player actor. See that file for the full player script; the autopilot adds three pieces:

### 1. `step-move` word (add before `: do-hop`)

```forth
: step-move ( step -- dr dc )
  dup  0 = if drop  1  0 exit then
  dup  1 = if drop -1  0 exit then
  dup  2 = if drop  1  1 exit then
  dup  3 = if drop  1  0 exit then
  dup  4 = if drop -1 -1 exit then
  dup  5 = if drop  1  0 exit then
  dup  6 = if drop  1  0 exit then
  dup  7 = if drop  1  0 exit then
  dup  8 = if drop -1  0 exit then
  dup  9 = if drop  1  1 exit then
  dup 10 = if drop -1  0 exit then
  dup 11 = if drop  1  1 exit then
  dup 12 = if drop -1  0 exit then
  dup 13 = if drop -1  0 exit then
  dup 14 = if drop  1  1 exit then
  dup 15 = if drop  1  0 exit then
  dup 16 = if drop  1  1 exit then
  dup 17 = if drop -1  0 exit then
  dup 18 = if drop  1  1 exit then
  dup 19 = if drop  1  1 exit then
  dup 20 = if drop -1 -1 exit then
  dup 21 = if drop  1  0 exit then
  dup 22 = if drop -1 -1 exit then
  dup 23 = if drop  1  0 exit then
  dup 24 = if drop -1 -1 exit then
  dup 25 = if drop  1  0 exit then
  dup 26 = if drop -1 -1 exit then
  dup 27 = if drop  1  0 exit then
  dup 28 = if drop -1 -1 exit then
  dup 29 = if drop  1  0 exit then
  dup 30 = if drop -1 -1 exit then
  drop  1  0 ;
```

### 2. Modified `cd 0 = if` block (replace the existing joystick section)

When `AUTOPILOT_ON` (mb 430) is non-zero, this runs the step-sequence instead of
reading the joystick. Both paths share the same `do-hop` word and cooldown.

```forth
cd 0 = if
  418 read-mailbox 1 = if
    430 read-mailbox 0 <> if
      431 read-mailbox dup 32 < if
        step-move do-hop
        431 read-mailbox 1 + 431 write-mailbox
      else drop then
      exit
    then
    stick 0x0800 & if -1  0 do-hop exit then
    stick 0x2000 & if  1  1 do-hop exit then
    stick 0x1000 & if  1  0 do-hop exit then
    stick 0x4000 & if -1 -1 do-hop exit then
  then
then
```

### 3. Reset `AUTOPILOT_STEP` on respawn (two locations in the player script)

In the round-clear apex-respawn block (`426 read-mailbox 1 = if ...`):
```forth
0 431 write-mailbox
```

In the game-over restart block (`420 read-mailbox 1 = if ...`):
```forth
0 431 write-mailbox
```

This makes the autopilot restart from step 0 on each round or on game-over restart.

---

## New mailboxes

| mb  | Symbolic name  | Direction       | Notes                                 |
|-----|----------------|-----------------|---------------------------------------|
| 430 | AUTOPILOT_ON   | user → player   | 0 = joystick, 1 = autopilot           |
| 431 | AUTOPILOT_STEP | player internal | counts 0..31, resets on respawn       |

Both fit within the existing 500-slot cap (highest previously used slot: 426).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Script aborts `ZF_ABORT_OUTSIDE_MEM` | Dict full | Increase `ZF_DICT_SIZE` in `engine/zforth/zf_conf.h` |
| `NOT_A_WORD` abort | `\` comment inside script body | zForth gotcha — use `( ... )` comments only |
| ROUND_CLEAR never fires | Apex cube stuck at state 0 | Verify step 1 lands at (0,0) and mb 411 fires |
| Autopilot doesn't start after round-clear | mb 431 not reset | Confirm `0 431 write-mailbox` in respawn block |

---

## Why not coroutines?

Coroutines would let you write the sequence as:

```forth
: autopilot  1 0 do-hop pause  -1 0 do-hop pause  1 1 do-hop pause  ... ;
```

Much more readable. The mailbox step counter is a manual coroutine frame. zForth has no
`pause`/`resume`, and adding them would require C++ engine changes (prohibited for ports
per `feedback_no_runtime_changes_for_ports.md`). The dispatch table is the correct
content-only workaround.
