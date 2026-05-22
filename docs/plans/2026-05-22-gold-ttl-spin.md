# Gold coin: 5 s TTL + Z-axis spin (Forth script)

**Status:** Complete (2026-05-22, ~2 h)

## Goal

1. Extend gold coin lifetime from 3 s → 5 s.
2. Coin rotates about the WF Z-axis (up) at 1 rev/sec, driven by the coin's Forth script (not C++).

## Approach

`INDEXOF_TIME read-mailbox` gives the current level time in seconds.
Writing that value to `INDEXOF_ROTATION_C` (3014) sets WF Euler C (heading/Z) in revolutions.
`Angle::Revolution(Scalar)` calls `AsUnsignedFraction()` which strips the whole part, so the value wraps cleanly as time grows — no fmod needed in script.
Result: exactly 1 rev/sec spin, stateless, no new mailboxes.

## Files changed

### `wfsource/source/game/gold.cc` — line 25

```cpp
static const float kGoldTTL = 5.0f;   // was 3.0f
```

### `wflevels/smb_w1_1/blender_create_smb.py`

Added `COIN_SCRIPT` constant and assigned it in `_make_coin_template()`:

```python
COIN_SCRIPT = "\\ wf\nINDEXOF_TIME read-mailbox INDEXOF_ROTATION_C write-mailbox\n"

def _make_coin_template():
    ...
    obj['wf_Script'] = COIN_SCRIPT
    return obj
```

Also added three stale-name overrides discovered during Blender re-export debugging:

```python
player.name = 'Player'                           # was "player_33" from snowgoons import
camshot['wf_Target'] = 'Target02'                # was "target_14"
actboxor['wf_Activated By Actor'] = 'Player'     # was "player_33"
```

### `wfsource/source/memory/lmalloc.cc`

Removed `int32 _pad` from `FileLine` struct (added in `2e0b229a`).
`sizeof(FileLine)` must be a multiple of `WF_POINTER_ALIGN` (8) so the user pointer
at `block_start + sizeof(FileLine)` inherits block alignment.
With `LMALLOC_TRACK_LINE_AND_FILE=0`: `_state(4) + _size(4) = 8` ✓.
The `_pad` made it 12, causing UBSan "misaligned address" on every allocation.

## Bugs encountered

### 1. CamShot assertion crash (movecam.cc:273)

`shotData->Target == 0` → assert fires.
Cause: Blender re-export imported snowgoons camshot with `wf_Target = "target_14"`.
`levcomp-rs` name lookup returned 0 for an unknown name.
Fix: `camshot['wf_Target'] = 'Target02'` in blender_create_smb.py.

### 2. Player name mismatch

CamShot Track Object referenced `"Player"` but imported object was named `"player_33"`.
Fix: `player.name = 'Player'` after `find_by_class('player')`.

### 3. Actboxor stale actor reference

`"Activated By Actor"` was `"player_33"` from the snowgoons import.
Fix: `actboxor['wf_Activated By Actor'] = 'Player'`.

### 4. LMalloc FileLine misalignment (pre-existing, `2e0b229a`)

`int32 _pad` (64-bit only) made `sizeof(FileLine) = 12`.
User pointer = `block_start + 12`; since block_start is 8-byte aligned, user data
was 4-byte aligned — UBSan "misaligned address for type 'struct DMalloc'".
Fix: removed `_pad`; natural size is 8 bytes.

## Commits

- `aab65aac` — feat(gold): extend TTL to 5 s; spin coin via Forth ROTATION_C script
- `88899746` — fix(smb+lmalloc): blender re-export name fixups + revert bad FileLine pad
- `235e5633` — chore(smb): rebuild mesh IFFs from Blender re-export + transcript
