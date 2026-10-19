# Plan: Autopilot round-through + per-round cube palette

**Status:** DONE (commit `9c6695f1`) — autopilot completes rounds via joystick injection. Per-round palette extension lives in [per-level-palette-diversity](2026-05-09-per-level-palette-diversity-extend-cube-palettes-from.md).

## Context
The debug bridge Phase A ops (`set_mailbox`, `inject_input`) are shipped and
unit-tested. The user wants: (1) a test that triggers the in-game autopilot
via the bridge and drives it through a full round, verifying round-clear fires
and the pyramid resets; (2) visually distinct per-round cube colors when the
round advances. Missing arcade colors are filled with confirmed data where
available and clearly-labeled placeholders elsewhere.

---

## Palette table (4 rounds = one full level cycle)

| Round | state0 top | state2 top | lit side | shadow side | Notes |
|-------|-----------|------------|----------|-------------|-------|
| R0 (L1R1) | `#5646EF` purple | `#DEDE00` yellow | `#56A999` teal | `#314646` dark-teal | ✅ confirmed |
| R1 (L1R2) | `#AC46AC` magenta | `#EFDE77` golden | `#FF7721` orange | `#663100` dk-orange | ⚠️ start placeholder |
| R2 (L1R3) | `#B9CECE` silver | `#3399CC` blue | `#777777` gray | `#212121` near-black | ⚠️ target placeholder |
| R3 (L1R4) | `#0066EF` blue | `#CC8822` amber | `#778888` gray-teal | `#101099` dk-blue | ⚠️ target placeholder |

State 1 (mid-hop intermediate): `#CC7733` orange placeholder for all rounds.

---

## Mailbox layout

Current visibility base: `300 + i*3 + s` (84 slots).  
New visibility base: `440 + r*84 + i*3 + s` (336 slots, r=round%4, i=cube 0..27, s=state 0..2).  
Max index = 440 + 3×84 + 27×3 + 2 = 775 < 998 cap. ✓  
Existing handshake mailboxes 411–430 are unaffected.

---

## Implementation steps

### 1 — `gen_cube.py`: generate 12 source IFFs
File: `wflevels/qbert_practice/gen_cube.py`

- Add `ROUND_COLORS` list (4 entries per table above).
- Loop rounds 0–3 × states 0–2; write `cube_state{s}_r{r}.iff`.
- Total: 12 source IFFs (was 3).

### 2 — `blender_create_qbert.py`: 336 actors + palette-aware director Forth
File: `wflevels/qbert_practice/blender_create_qbert.py`

**Actor generation** (was 84, now 336):
```
for r in 0..3:
  for i in 0..27:
    for s in 0..2:
      actor name          = f"cube_{i:02d}_r{r}_s{s}"
      mesh IFF            = f"cube_state{s}_r{r}.iff"  (shutil.copyfile)
      wf_VisibilityMailbox = 440 + r*84 + i*3 + s
      initial mailbox val  = 1 if (r==0 and s==0) else 0
```

**Director Forth changes** — palette-aware visibility:

Replace the `show-cube-state` / `hide-cube-state` helpers. Key new logic:

```forth
\ palette = ROUND_NUMBER % 4
: cur-pal  425 read-mailbox 4 mod ;

\ absolute visibility mailbox for cube i, round r, state s
: vis-mbx  ( i r s -- mbx )  rot 3 * + swap 84 * + 440 + ;

\ on hop: set cube i to new state ns in cur palette; hide all others for cube i
: set-cube-state  ( i ns -- )
    cur-pal  ( i ns r )
    \ write 1 to the target slot
    over >r  over >r        \ save ns, r
    2 pick r@ vis-mbx  1 swap write-mailbox
    \ zero the other 2 states in cur palette
    3 0 do  i r@ = not if  2 pick r@ i vis-mbx  0 swap write-mailbox  then  loop
    r> drop  r> drop  drop drop ;

\ on round-clear: hide all r=prev_pal actors for every cube, show r=new_pal state-0
: init-round-vis  ( -- )
    425 read-mailbox 1 - 4 mod  ( prev_pal )
    28 0 do
        3 0 do  i over j vis-mbx  0 swap write-mailbox  loop   \ hide prev
        i cur-pal 0 vis-mbx  1 swap write-mailbox               \ show new state-0
    loop  drop ;
```

Call `init-round-vis` from the existing round-clear reset path (after ROUND_NUMBER++, where `init-vis` currently is).

### 3 — Rebuild level binary
```bash
cd wflevels/qbert_practice
python3 gen_cube.py            # writes 12 IFFs
python3 blender_create_qbert.py  # regenerates .lev
bash ../../wftools/wf_blender/build_level_binary.sh qbert_practice
```

### 4 — `tests/test_autopilot.py` (new)
Location: `tests/test_autopilot.py`

Uses existing `bridge` session fixture (port 7778, qbert_practice-standalone.iff).

**test_autopilot_completes_round:**
1. Watch mb[425] (ROUND_NUMBER).
2. `set_mailbox(mailbox=430, value=1)` — enable autopilot.
3. Wait up to 45 s for mb[425] to change from 0 to 1.
4. Assert ROUND_NUMBER == 1.

**test_round_advance_changes_palette:**
After round completes (ROUND_NUMBER==1):
1. Watch mb[440] (cube 0, round 0, state 0) and mb[524] (cube 0, round 1, state 0).
2. Assert mb[440] == 0 (old palette hidden).
3. Assert mb[524] == 1 (new palette's state-0 visible).
4. Spot-check 3 more cube indices for both rounds.

### 5 — Run tests
```bash
cd tests
DISPLAY=:0 python3 -m pytest test_phase_a.py test_autopilot.py -v
```
All 6 tests should pass.

---

## Files changed

| File | Change |
|------|--------|
| `wflevels/qbert_practice/gen_cube.py` | Add ROUND_COLORS, generate 12 IFFs |
| `wflevels/qbert_practice/blender_create_qbert.py` | 336 actors, new vis mailbox range, palette-aware Forth |
| `tests/test_autopilot.py` | New — 2 bridge tests |

No C++ / engine changes required.
