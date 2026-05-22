# Plan — Q✱bert per-round difficulty scaling

**Date:** 2026-05-15
**Status:** Not started
**Plan doc:** `docs/plans/2026-05-15-qbert-difficulty-scaling.md`

## Context

Two related gaps:
1. All enemies are rendered at startup (tiny at bottom of screen) because `wf_Visibility Mailbox = 1` (hardwired TRUE) — they're just parked at Z=-30, not truly hidden.
2. All enemies spawn on every round regardless of level — arcade introduces enemies progressively (L1: Red Ball + Coily; L2: add Slick + Sam; L3: add Ugg + Wrong-Way; L4: 2 Coily eggs).

Fix: add per-enemy ACTIVE mailboxes (mb 600–604). Point each enemy's `wf_Visibility Mailbox` to its ACTIVE mb — engine hides it when 0. The ACTIVE mailbox tracks whether the enemy is **currently placed on the board**:
- Written to **1 when the enemy is spawned/placed** (becomes visible)
- Written to **0 when the enemy retires/parks** (becomes invisible)

Level-introduction gating (Slick doesn't appear until L2, etc.) is handled separately by not re-arming the spawn timer for enemy types whose level hasn't been reached. No separate "allowed" mailbox — just a level check in the spawn re-arm code.

ROM disassembly (Phase 2) extracts ground-truth spawn intervals to replace the current fixed values.

## Critical files

- **`wflevels/qbert_practice/blender_create_qbert.py`** — all changes (Blender authoring + Forth script)
  - Blender authoring for each enemy: lines ~1262, 1302, 1416, 1433, 1542, 1558 (`wf_Visibility Mailbox` assignments)
  - Level init block: lines ~2311–2324 (spawn timer setup)
  - Round-clear block: lines ~2648–2689 (enemy retire + spawn re-arm)
  - Each enemy spawn handler: Green Ball ~line 1100, Slick ~1400, Sam ~1430, Ugg ~1520, Wrong-Way ~1540

## New mailboxes (mb 600–604, currently free)

```python
GB_MB_ACTIVE    = 600   # Green Ball: 1 = on the board now
SLICK_MB_ACTIVE = 601   # Slick: 1 = on the board now
SAM_MB_ACTIVE   = 602   # Sam: 1 = on the board now
UGG_MB_ACTIVE   = 603   # Ugg: 1 = on the board now
WW_MB_ACTIVE    = 604   # Wrong-Way: 1 = on the board now
# Red Ball and Coily already have per-instance active mirrors — unchanged
```

## Part A — Visibility gating (fixes startup bug + progressive intro)

### A1. Blender authoring changes

Change `wf_Visibility Mailbox` for each enemy actor:
```python
_gball['wf_Visibility Mailbox'] = GB_MB_ACTIVE    # was 1
_slick['wf_Visibility Mailbox'] = SLICK_MB_ACTIVE # was 1
_sam['wf_Visibility Mailbox']   = SAM_MB_ACTIVE   # was 1
_ugg['wf_Visibility Mailbox']   = UGG_MB_ACTIVE   # was 1
_ww['wf_Visibility Mailbox']    = WW_MB_ACTIVE     # was 1
```

### A2. Level init block (~line 2316, alongside existing active-mirror clears)

Add ACTIVE mailbox clears alongside the existing `0 {SLICK_MB_ACTIVE} write-mailbox` etc. — these are already there (mb 547, 550, 552, 570, 572 are the existing active mirrors). The new mailboxes (600–604) need the same 0-init:

```python
f"0 {GB_MB_ACTIVE} write-mailbox "
f"0 {SLICK_MB_ACTIVE} write-mailbox "
f"0 {SAM_MB_ACTIVE} write-mailbox "
f"0 {UGG_MB_ACTIVE} write-mailbox "
f"0 {WW_MB_ACTIVE} write-mailbox "
```

### A3. In each enemy's spawn/place code: write 1 → ACTIVE

When the enemy is placed on the board (position written, phase set to active):
```forth
1 <ACTIVE_MB> write-mailbox
```

### A4. In each enemy's retire/park code: write 0 → ACTIVE

When enemy falls off or is retired (phase set to 0, Z parked):
```forth
0 <ACTIVE_MB> write-mailbox
```

### A5. Level-introduction gating via spawn re-arm (NOT the ACTIVE mailbox)

In the level init block and round-clear block, guard the spawn timer re-arm with a level check:

```forth
( Slick/Sam/Green Ball: only arm spawn timer from L2 = round >= 4 )
425 read-mailbox 3 > if
  <arm GB/Slick/Sam spawn timers>
then

( Ugg/Wrong-Way: only arm from L3 = round >= 8 )
425 read-mailbox 7 > if
  <arm Ugg/WW spawn timers>
then
```

Enemies not yet introduced simply never get their spawn timers armed, so their spawn handler never fires.

## Part B — ROM disassembly (ground-truth spawn intervals)

### B1. Setup and disassemble

```bash
sudo apt-get install -y z80dasm
cd /home/will/WorldFoundry.2026-new-level/assets/arcade-roms
mkdir -p /tmp/qbert-roms
unzip -o qbert.zip qb-rom0.bin qb-rom1.bin qb-rom2.bin -d /tmp/qbert-roms/
cat /tmp/qbert-roms/qb-rom0.bin \
    /tmp/qbert-roms/qb-rom1.bin \
    /tmp/qbert-roms/qb-rom2.bin > /tmp/qbert-roms/qbert-full.bin
z80dasm --origin=0x0000 --address --hex /tmp/qbert-roms/qbert-full.bin \
    > docs/investigations/qbert-z80-disassembly.asm
```

### B2. Find spawn tables

Search for 16-byte decreasing sequences (round LUTs) and `LD A, (HL)` / `LD HL, nn` patterns referencing the known round-counter RAM address (0x0081 from game_state.txt):

```bash
grep -n "0081\|0x81" docs/investigations/qbert-z80-disassembly.asm | head -30
```

### B3. MAME timing probe (fallback/verification)

New script `scripts/research/mame/qbert_spawn_timing.lua`: watches sprite state transitions per frame, records spawn intervals per enemy per round to CSV. Run across all 16 rounds using `qbert_advance_levels.lua` as template.

## Part C — Spawn interval scaling (after B)

Replace fixed spawn intervals in init + round-clear blocks with ROM-derived per-round values. Pattern extends the existing Red Ball formula:
```forth
( example for Slick: base 480, ramp by <n> per round, floor <min> )
425 read-mailbox <n> * 480 swap - dup <min> < if drop <min> then SLICK_MB_SPAWN_TIMER write-mailbox
```

Exact values filled in from ROM data.

## Build pipeline

```bash
blender -b wflevels/qbert_practice/qbert_practice.blend \
        -P wflevels/qbert_practice/blender_create_qbert.py
wftools/wf_blender/build_level_binary.sh qbert_practice
(cd wfsource/source/game && ./wf_game)
```

## Verification

1. **Startup**: No enemy sprites visible at scene start (all hidden by ENABLED=0).
2. **L1 (round 0)**: Only Red Ball and Coily appear; Green Ball/Slick/Sam/Ugg/Wrong-Way invisible.
3. **L2 (round 4)**: Green Ball, Slick, Sam become visible and start spawning.
4. **L3 (round 8)**: Ugg and Wrong-Way appear.
5. **Round transition**: enemies from prior round invisible on new round's first frame.
6. **Regression**: hop arc, death, score HUD, cube cycles unaffected.
