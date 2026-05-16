# Plan — Q✱bert multi-step cube cycles

**Date:** 2026-05-14  
**Status:** Complete — implemented at blender_create_qbert.py:2876-2883

## Context

The current landing handler does a single-flip: state 0→2 regardless of round. The arcade has per-level rules:

| Level | Rounds (ROUND_NUMBER) | Hops to clear | Extra-hop revert |
|-------|-----------------------|--------------|-----------------|
| L1 | 0–3 | 1 | none |
| L2 | 4–7 | 2 | 2→0 |
| L3 | 8–11 | 1 | none |
| L4 | 12–15 | 2 | 2→1 |

The supporting infrastructure is already in place: `CUBE_STATE_BASE` (mb 200–227) supports values 0/1/2, `ROUND_TOP_LUT` (mb 256–303) has 3 distinct RGB colors per round indexed as `256 + ROUND_NUMBER*3 + state`, and the per-tick color-update loop already reads `ROUND_TOP_LUT[ROUND_NUMBER*3 + cur_state]` and writes it to each cube's `FACE_COLOR_TOP` actor mailbox. The win check (`state != 2` for all 28 cubes) is already correct. Only the landing handler needs replacing.

`ROUND_NUMBER` (mb 425) is 0–15; integer `level = ROUND_NUMBER ÷ 4`. Even level (0,2) = 1-step; odd level (1,3) = 2-step.

## Critical file

[`wflevels/qbert_practice/blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py) — DIRECTOR_SCRIPT landing handler (~line 2578)

## Change — landing handler

### Old (~lines 2578–2584)

```python
"411 read-mailbox 0 <> if ",
"400 read-mailbox dup 1 + * 2 / 401 read-mailbox + 200 + ",
"dup read-mailbox 0 = if 2 swap write-mailbox 70 read-mailbox 25 + 70 write-mailbox else drop then ",
"0 411 write-mailbox then\n",
```

### New

```python
"411 read-mailbox 0 <> if ",
"400 read-mailbox dup 1 + * 2 / 401 read-mailbox + 200 + ",
"dup read-mailbox ",
"dup 0 = if drop 425 read-mailbox dup 4 % - 4 / 2 % 0 = if 2 swap write-mailbox else 1 swap write-mailbox then 70 read-mailbox 25 + 70 write-mailbox ",
"else dup 1 = if drop 2 swap write-mailbox 70 read-mailbox 50 + 70 write-mailbox ",
"else drop 425 read-mailbox dup 4 % - 4 / dup 1 = if drop 0 swap write-mailbox else dup 3 = if drop 1 swap write-mailbox else drop drop then then ",
"then then ",
"0 411 write-mailbox then\n",
```

### Logic

- **state=0, 1-step level (level even):** write 2, +25 pts
- **state=0, 2-step level (level odd):** write 1, +25 pts
- **state=1:** write 2, +50 pts
- **state=2, L2 (level=1):** revert to 0, no score
- **state=2, L4 (level=3):** revert to 1, no score
- **state=2, L1/L3 (level=0/2):** no-op

All five paths leave an empty stack before `0 411 write-mailbox`. Stack traces verified in plan.

## Scoring

- First touch: **+25 pts**
- Second touch: **+50 pts**
- Revert: no change

Full L1 round: 28×25 + 1000 = **1 700 pts**  
Full L2 round: 28×(25+50) + 1000 = **3 100 pts**

## Build pipeline

```bash
blender -b wflevels/qbert_practice/qbert_practice.blend \
        -P wflevels/qbert_practice/blender_create_qbert.py
wftools/wf_blender/build_level_binary.sh qbert_practice
(cd wfsource/source/game && ./wf_game)
```

## Verification

1. **L1R1 (round 0):** hop a virgin cube once → done-color, SCORE +25. Hop again → no change. Clear all 28 in 28 hops → round-clear fires.
2. **L2R1 (round 4):** hop virgin → intermediate color, +25. Hop again → done-color, +50. Hop done cube → reverts to virgin color, no score. Clearing requires two hops per cube.
3. **L4R1 (round 12):** hop done cube → reverts to intermediate color (not virgin).
4. **Score totals:** L1 clear = 1 700; L2 clear = 3 100.
5. **Regression:** hop arc and death animation unaffected.
