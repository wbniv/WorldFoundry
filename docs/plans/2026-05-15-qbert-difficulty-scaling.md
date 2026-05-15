# Plan — Q✱bert per-round difficulty scaling

**Date:** 2026-05-15
**Status:** In progress — Phase 1 complete; Phase 2 implementation pending

## Context

Q✱bert currently has per-enemy independent spawn timers (mailboxes 512, 547, 550, 552, 570, 572). This plan extracts ground-truth spawn behaviour from the arcade ROM and implements faithful difficulty scaling.

**Phase 1 complete (2026-05-15):** ROM disassembled via Ghidra headless (x86:LE:16:Real Mode — Q✱bert runs on an **Intel 8088 at 5 MHz**, not a 6809 as commonly cited). Full annotated listing at [`docs/investigations/qbert-8088-disassembly.asm`](../investigations/qbert-8088-disassembly.asm).

## Critical files

- `wflevels/qbert_practice/blender_create_qbert.py` — all Forth changes
- `docs/investigations/qbert-8088-disassembly.asm` — full annotated ROM disassembly ✓ done
- `scripts/research/mame/qbert_spawn_timing.lua` — MAME runtime probe (optional, for validation)

## What the ROM actually does (Phase 1 finding)

The arcade does **not** use per-enemy independent timers. Instead it uses a **scripted spawn sequencer**:

- **RAM `$0085`** — shared countdown timer, decremented each game tick
- **RAM `$0D17`** — reload value (ticks); reloaded each time `$0085` hits zero
- **RAM `$0D13`** — current position in the spawn sequence table (advances +2 per fire)
- **RAM `$0D11`** — sequence start address (reset each round; `$FFFF` sentinel wraps here)

Each difficulty **stage** (18 total, table at ROM `$A899`) bundles a spawn sequence + reload value. Stage configs:

| Stage | Reload | b[5] | Sequence (enemy IDs: 0=RedBall 2=CoilyEgg 5=Slick 7=Sam) |
|-------|--------|------|-----------------------------------------------------------|
| 0     | 200    | 1    | E2 E2 END |
| 1     | 160    | 1    | E0 E0 E2 END |
| 2     | 136    | 1    | E5 E7 … E5 E7 … (Slick+Sam heavy) |
| 3     | 176    | 1    | E2 E0 E0 … (Coily+RedBall) |
| 4     | 208    | 1    | E5 E7 … (Slick+Sam+Coily) |
| 5–17  | 124–256| 1–4 | increasing enemy mix; b[5] likely max simultaneous Coily eggs |

Enemy type IDs in sequence (low 5 bits after masking 0x1F):
- E0 = Red Ball, E2 = Coily egg, E5 = Slick, E7 = Sam, E1 = Ugg(?), E3 = Wrong-Way(?)

`b[5]` field (1→4 across stages) likely controls max simultaneous Coily eggs (arcade L4 has 2 eggs).

## Current spawn mailboxes (WF implementation — to replace)

| Enemy     | Spawn timer mb | Current interval (ticks) | Arcade approach |
|-----------|---------------|--------------------------|-----------------|
| Red Ball  | 512           | `max(60, 300 - 12×R)`   | sequence entry  |
| Green Ball| 547           | 1500 (fixed)             | sequence entry  |
| Slick     | 550           | 480 (fixed)              | sequence entry  |
| Sam       | 552           | 1500 (fixed)             | sequence entry  |
| Ugg       | 570           | 1200 (fixed)             | sequence entry  |
| Wrong-Way | 572           | 1500 (fixed)             | sequence entry  |

## Phase 2 implementation plan

Faithful approach: replace independent timers with a single WF spawn sequencer:

1. **Single spawn-seq timer** — one director mailbox as countdown; reloads from a per-stage value
2. **Stage sequence table** — author the 18-stage sequences as Forth data (or `.lev` data)
3. **Stage counter** — advances on round clear; wraps at 18
4. **b[5] gating** — use to cap simultaneous Coily eggs

Simpler interim approach (good enough for now):
- Keep per-enemy timers but set them to the sequence-implied cadence
- Stage 0 reload=200 ticks; enemy mix: only Coily eggs initially
- Stage 1+: add Red Ball
- Stage 2+: add Slick/Sam
- etc.

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
