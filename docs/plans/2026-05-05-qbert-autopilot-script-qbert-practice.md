# Plan: Q*bert Autopilot Script (qbert_practice)

**Status:** DONE (commit `9c6695f1`) — 32-step autopilot path + step-move word; respawn handlers reset mb 431.

## Context

The `qbert_practice` level needs a Forth autopilot that covers all 28 pyramid cubes.
`INDEXOF_HARDWARE_JOYSTICK1_RAW` (mb 1009) is read-only in the engine — scripts cannot
write to it. The autopilot is therefore embedded inside the player script itself,
activated via mb 430 (AUTOPILOT_ON).

**Key fact the user asked about:** the apex cube (0,0) starts at state 0 (OFF).
`QBERT_LANDED` (mb 411) only fires on hops, not on spawn, so the apex is never flipped
unless Q*bert hops back onto it. The path includes a deliberate apex-flip on steps 0-1.

## Why no Hamiltonian path from (0,0) exists

The pyramid has two degree-1 nodes: (6,0) [only neighbor: (5,0)] and (6,6) [only
neighbor: (5,5)]. Both must be endpoints of any Hamiltonian path. A path starting at
(0,0) — degree 2 — can only end at one degree-1 node, leaving the other stranded.
Minimum revisits for full coverage from (0,0): **at least 2**. The path below uses 5.

## Coverage path — 32 hops, all 28 cubes, ends at (6,0)

```
step  0: DL -> (1,0)           step 11: DR -> (4,2)
step  1: UR -> (0,0)  <APEX>   step 12: UR -> (3,2)
step  2: DR -> (1,1)           step 13: UR -> (2,2)
step  3: DL -> (2,1)           step 14: DR -> (3,3)
step  4: UL -> (1,0)  <rev>    step 15: DL -> (4,3)
step  5: DL -> (2,0)           step 16: DR -> (5,4) [row5 bridge]
step  6: DL -> (3,0)           step 17: UR -> (4,4)
step  7: DL -> (4,0)           step 18: DR -> (5,5)
step  8: UR -> (3,0)  <rev>    step 19: DR -> (6,6) [dead-end detour]
step  9: DR -> (4,1)           step 20: UL -> (5,5)  <rev>
step 10: UR -> (3,1)           step 21: DL -> (6,5)
                               step 22: UL -> (5,4)  <rev>
                               step 23: DL -> (6,4)
                               step 24: UL -> (5,3)
                               step 25: DL -> (6,3)
                               step 26: UL -> (5,2)
                               step 27: DL -> (6,2)
                               step 28: UL -> (5,1)
                               step 29: DL -> (6,1)
                               step 30: UL -> (5,0)
                               step 31: DL -> (6,0)  <- terminal
```

Revisits: (0,0) at step 1 (apex flip), (1,0) at step 4, (3,0) at step 8,
          (5,5) at step 20, (5,4) at step 22.

## Complete Forth script (player script patch)

New mailboxes: **430 = AUTOPILOT_ON**, **431 = AUTOPILOT_STEP**

Add `step-move` word before `do-hop`, then replace the `cd 0 = if` section with the
autopilot-first version below. Also reset mb 431 in both respawn locations.

### step-move word (32-entry dispatch table)

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

### Modified cd 0 = if block

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

### Reset AUTOPILOT_STEP in the two respawn locations

In the `426 read-mailbox 1 = if` block: add `0 431 write-mailbox`
In the game-over restart block: add `0 431 write-mailbox`

## Implementation steps

1. Write `WorldFoundry.2026-new-level/docs/investigations/2026-05-05-qbert-autopilot.md`
   with the full path analysis, complete Forth script, and testing instructions.

2. Edit `WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py`:
   - Add `step-move` definition before `do-hop` in the player `wf_Script`
   - Replace the `cd 0 = if` joystick block with the autopilot-first version
   - Add `0 431 write-mailbox` to both respawn reset locations

3. Build: `bash wftools/wf_blender/build_level_binary.sh qbert_practice`

4. Test via debug bridge: `{"op":"set_mailbox","slot":430,"value":1}` (AUTOPILOT_ON=1),
   then watch mb 431 advance 0→31, mb 200-227 all reach state 2, mb 413=1 fires.

## Critical files

- `WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py` — EDIT
- `WorldFoundry.2026-new-level/docs/investigations/2026-05-05-qbert-autopilot.md` — CREATE

## Risks

- **Dict size**: `step-move` adds ~32 words to zForth dict. If abort with
  `ZF_ABORT_OUTSIDE_MEM`, increase `ZF_DICT_SIZE` in `engine/zforth/zf_conf.h`.
- **No `\` comments** inside script body (zForth gotcha); use `( ... )` only.
- **Auto-loop**: after step 31, player sits at (6,0). Round-clear fires (90-tick
  countdown), director resets cubes + sets mb 426=1. Player respawn handler resets
  mb 431=0, so autopilot restarts automatically each round.
