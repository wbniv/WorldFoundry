# Plan — Walker diff sample-point nudge

**Date:** 2026-05-09
**Status:** Obsolete 2026-05-11 — hardcoded pixel-sample points only made sense under the original 2D-ish fixed-camera capture. With Q*bert now in real 3D (per-hop camera changes, parabolic Z arc, hop-direction rotation, perspective foreshortening), `(x, y)` sample points no longer land on a fixed cube face across frames. Cube-colour parity should be verified by reading the live `EMAILBOX_FACE_COLOR_TOP` mailbox via the debug bridge, not by pixel-sampling the framebuffer.

## Context

After the cube-state-transition fix landed (commit `5cf6883`), the walker diff went from 0/32 → 1/32 PASS. Most state-0 FAILs are misleading: WF reads the cube's *shadow side* colour, not its top, because the hardcoded sample point in [scripts/research/wf/qbert_walker_diff.py](../../scripts/research/wf/qbert_walker_diff.py) lands a few pixels too low.

A vertical pixel scan of `docs/investigations/wf-screenshots/wf_walker_L1R1_state0.png` at x=320:

```
y=211..223 → #5545ED  (apex top — round-0 state-0 colour ≈ ROUND_COLORS[0][0] 0x5646EF)
y=225..    → #314545  (shadow side — ROUND_COLORS[0][3] 0x314646)
```

`WF_APEX_TOP = (320, 240)` lands at y=240 → shadow side. Should be y≈217 (mid-top-band).

`WF_CUBE10_TOP = (290, 285)` works for state-1 captures (we just verified L1R1 reads `#DCDC00` and passes the threshold). Worth a re-eyeball on one state-1 PNG; nudge only if visibly off-centre.

## Approach

One-line edit in [scripts/research/wf/qbert_walker_diff.py](../../scripts/research/wf/qbert_walker_diff.py):

```python
WF_APEX_TOP = (320, 217)   # was (320, 240) — landed on shadow side
```

Re-run `python3 scripts/research/wf/qbert_walker_diff.py` and expect L?R1 state-0 cells to now read R0 top colour `#5645ED`. Other state-0 rows will still FAIL because WF cycles 4 round palettes vs MAME's 16 (separate authoring workstream).

## Verification

1. Edit the constant.
2. `python3 scripts/research/wf/qbert_walker_diff.py | grep state0 | head -4` — expect WF column to show `#5545ED / #AC45AC / #B9CECE / #0066EF` (the four `gen_cube.py:ROUND_COLORS[*][0]` values), not the shadow-side colours.
3. Pass count stays at 1/32 (only L1R1 state-1 passes today) — this fix doesn't add PASSes, it just makes the FAILs honest. The remaining FAILs are the documented per-level palette diversity issue.

## Out of scope

- Per-level palette diversity (WF has 4 palettes, MAME has 16). Authoring fix in `gen_cube.py:ROUND_COLORS`.
- Walker `--max-rounds 16` to cover L4. Already documented.
