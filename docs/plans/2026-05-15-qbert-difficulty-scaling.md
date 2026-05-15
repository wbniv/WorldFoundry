# Plan — Q✱bert per-round difficulty scaling

**Date:** 2026-05-15
**Status:** In progress

## Context

Q✱bert currently has only one round-dependent spawn variable: Red Ball interval (`max(60, 300 - 12×ROUND_NUMBER)` ticks). All other enemies use fixed intervals across all 16 rounds. This plan extracts ground-truth spawn timing from the arcade ROM, then implements per-round scaling in the Forth director script.

## Critical files

- `wflevels/qbert_practice/blender_create_qbert.py` — all Forth changes
- `docs/investigations/qbert-z80-disassembly.asm` — full ROM disassembly (Phase 1 output)
- `docs/investigations/qbert-spawn-timing.csv` — MAME timing probe output (Phase 1 output)
- `scripts/research/mame/qbert_spawn_timing.lua` — new MAME probe script

## Current spawn mailboxes

| Enemy     | Spawn timer mb | Current interval (ticks) |
|-----------|---------------|--------------------------|
| Red Ball  | 512           | `max(60, 300 - 12×R)`    |
| Green Ball| 547           | 1500 (fixed)             |
| Slick     | 550           | 480 (fixed)              |
| Sam       | 552           | 1500 (fixed)             |
| Ugg       | 570           | 1200 (fixed)             |
| Wrong-Way | 572           | 1500 (fixed)             |

## Arcade rules (to implement)

**Enemy introduction by level:**
- L1 (rounds 0–3): Red Ball + Coily only
- L2 (rounds 4–7): add Slick + Sam
- L3 (rounds 8–11): add Ugg + Wrong-Way
- L4 (rounds 12–15): increase Coily eggs (2 simultaneous)

**Gating pattern** (Forth, at level init):
```forth
( Slick: only from L2 = round >= 4 )
425 read-mailbox 4 < if 32767 550 write-mailbox then
```

**Spawn interval scaling** (per-round values from ROM/MAME probe — filled in after Phase 1):

| Round | Red Ball | Green Ball | Slick | Sam | Ugg | Wrong-Way |
|-------|----------|------------|-------|-----|-----|-----------|
| 0     | 300      | (off)      | (off) |(off)|(off)| (off)     |
| 4     | 252      | ?          | ?     | ?   |(off)| (off)     |
| 8     | 204      | ?          | ?     | ?   | ?   | ?         |
| 12    | 156      | ?          | ?     | ?   | ?   | ?         |

*Fill in from ROM disassembly / MAME probe.*

## Build pipeline

```bash
blender -b wflevels/qbert_practice/qbert_practice.blend \
        -P wflevels/qbert_practice/blender_create_qbert.py
wftools/wf_blender/build_level_binary.sh qbert_practice
(cd wfsource/source/game && ./wf_game)
```

## Verification

1. L1 (round 0): Only Red Ball and Coily spawn; Slick/Sam/Ugg/Wrong-Way absent.
2. L2 (round 4): Slick and Sam appear; Ugg/Wrong-Way absent.
3. L3 (round 8): Ugg and Wrong-Way appear.
4. L4 (round 12): Two Coily eggs spawn simultaneously.
5. Enemy frequency: visibly shorter gaps in later rounds.
6. Regression: hop arc, death, score HUD, cube cycles unaffected.
