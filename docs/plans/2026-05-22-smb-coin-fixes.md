# Fix SMB coin: TTL bug, size, rightward motion, physics params, OAD value

**Status:** Not started

## Context

Four issues with the ?-block coin reported after play-testing, plus a pickup-value feature request:

1. **Coin disappears in a flash** — root cause confirmed in `gold.cc`: `_despawnTime` is
   initialised with `startupData->currentTime.Current()`, but `SObjectStartupData::currentTime`
   is a value-copy of the level Clock made at level-load time
   (`level.cc:267 startupData.currentTime = LevelClock()`). `Clock::Current()` returns
   `_nWallClock` (a stored Scalar, not a live reference — `clock.hpi:12`). So
   `_despawnTime ≈ 0 + 3 = 3 s` for every coin ever spawned. Any coin spawned after t > 3 s
   immediately satisfies `LevelClock().Current() >= _despawnTime` in `Gold::update()` and is
   removed on the very first tick.

2. **Coin too small** — current `COIN_R=0.3` gives 0.6 m height vs 1.5 m block (40%). NES
   reference: coin sprite is 8×16 px, block is 16×16 px → **50% width, 100% height**.
   Use NES reference dimensions.

3. **No rightward motion** — `wf_Object X Velocity = 0.0`; NES coins drift right slightly.

4. **Physics params not set** — user wants 0 ground friction, 0 air friction, full collision.

5. **Pickup value in OAD** — user wants the per-coin gold value to be OAD-configurable.
   `Gold::Collision` in C++ already handles player-only pickup + `SetPendingRemove`; the only
   gap is the value is hardcoded to +1. A `Gold Value` OAD field (default 1) makes it
   configurable without script changes. A Forth coin script **cannot** implement this
   independently: there is no `COLLIDER_KIND` mailbox, and `GOLD` (3001) is a per-actor local
   on the player that a coin script cannot write.

## Secondary: spawn Z overlap

The generator spawns coins with the coin's **centre** at `topZ` (block top Z = 5.25 m).
With new `COIN_Z = 0.5625` half-height the coin's bottom is at 4.6875 m — 0.5625 m inside
the block. Jolt depenetration would push the coin upward violently. Fix in `generator.cc`:
offset spawn Z by the template's Z half-size so the coin's **bottom** starts at `topZ`.

## Changes

### 1. TTL fix — two options (recommend B)

**Option A — Gold-specific patch (`gold.cc` line 25)**

```cpp
// BEFORE:
, _despawnTime(startupData->currentTime.Current() + Scalar(kGoldTTL))
// AFTER:
, _despawnTime(theLevel->LevelClock().Current() + Scalar(kGoldTTL))
```
Narrow fix: only Gold benefits. Stale-clock problem persists for any other actor that
stores `startupData->currentTime` for timing.

**Option B — Engine fix in `level.cc::SafelyConstructTemplateObject` ✓ RECOMMENDED**

`SafelyConstructTemplateObject` already transiently mutates the shared template
`startupData` for `idxCreator` (lines 1688/1691). Apply the same pattern to `currentTime`:

```cpp
// Add immediately before the ConstructTemplateObject call (~line 1689):
startupData->currentTime = theLevel->LevelClock();   // stamp spawn time
Actor* retVal = ConstructTemplateObject( startupData->objectData->type, startupData );
```

No reset needed. With Option B, `gold.cc` constructor stays unchanged; all future
spawnable actors also get correct spawn-time clocks automatically.

### 1b. `wfsource/source/game/gold.cc` — OAD value only (TTL handled by engine fix)

Collision (line 70) — replace hardcoded `Scalar::one` with OAD value:
```cpp
pm.WriteMailbox(EMAILBOX_GOLD,
    pm.ReadMailbox(EMAILBOX_GOLD) + Scalar(getOad()->GetGoldValue()));
```

### 2. `wfsource/source/oas/gold.oas` — add Gold Value field

```
TYPEHEADER(Gold,Gold)
    @include actor.inc
    STARTPROPERTY( Gold Value, INT32, 1, 1, 99 )
        ENDPROPERTY
TYPEFOOTER
```

Then run `task gen-oas-headers` — `regen-headers.sh` processes all `.oas` files through
the `prep → .pp → awk` pipeline and regenerates `gold.ht` with the new field. Do not
hand-edit `gold.ht`; it carries a "DO NOT MODIFY" header and is owned by codegen.

### 3. `wfsource/source/game/generator.cc` — offset spawn Z by template half-height

After `topZ` (line 113), replace the `pos` line (114) with:
```cpp
// Offset so the spawned object's BOTTOM lands at topZ, not its centre.
SObjectStartupData* tmplData =
    (SObjectStartupData*)theLevel->FindTemplateObjectData(objectToGenerate);
Scalar tmplHalfZ = Scalar::zero;
if (tmplData)
{
    Scalar tMinZ = Scalar::FromFixed32(tmplData->objectData->coarse.minZ);
    Scalar tMaxZ = Scalar::FromFixed32(tmplData->objectData->coarse.maxZ);
    tmplHalfZ = (tMaxZ - tMinZ) / Scalar::two;
}
Vector3 pos = Vector3(center.X(), center.Y(), topZ + tmplHalfZ) + displacement;
```

### 4. `wflevels/smb_w1_1/blender_create_smb.py` — shape, velocity, physics

Replace `COIN_R, COIN_T = 0.3, 0.2` with:
```python
COIN_X = T * 0.25    # half-width  = NES 8px/16px  → 50% → 0.375 m
COIN_Z = T * 0.5     # half-height = NES 16px/16px → 100% → 0.75 m
COIN_T = 0.2         # Y-depth (min to render from side cam, unchanged)
```
(`T = 1.5`, so `COIN_X = 0.375 m`, `COIN_Z = 0.75 m`.)

In `_make_coin_template`, update the scale call:
```python
_bmesh.ops.scale(bm, vec=(COIN_X*2, COIN_T*2, COIN_Z*2), verts=bm.verts)
```

Add physics properties to the coin template:
```python
obj['wf_Surface Friction'] = 0.0
obj['wf_Horiz Air Drag']   = 0.0
obj['wf_Vert Air Drag']    = 0.0
```

In the qblock loop, set rightward X velocity:
```python
blk['wf_Object X Velocity'] = 1.5   # +X = screen-right in side-scroller
```

## Build & verify

```bash
# 1. Rebuild level binary
blender --background --python /home/will/WorldFoundry.2026-new-level/wflevels/smb_w1_1/blender_create_smb.py
bash /home/will/WorldFoundry.2026-new-level/wftools/wf_blender/build_level_binary.sh smb_w1_1
iffcomp standalone smb_w1_1

# 2. Rebuild engine (gold.cc + generator.cc changed)
task build
```

Manual checks:
- Bump a ?-block at t > 3 s into the session → coin stays visible for ~3 s (TTL fix).
- Coin visibly drifts rightward and does not shoot off erratically (spawn-overlap fix).
- Coin is taller and narrower than before (size fix).
- Player walks into coin → coin disappears and GOLD mailbox increments (existing Gold::Collision).
- `python3 tests/verify_smb_scroll.py` → all 4 screenshots pass (regression).

## Critical files

| File | Change |
|------|--------|
| `wfsource/source/game/gold.cc` | TTL fix + OAD value |
| `wfsource/source/oas/gold.oas` | Add `Gold Value` field |
| `wfsource/source/oas/gold.ht` | Add `GetGoldValue()` accessor |
| `wfsource/source/game/generator.cc` | Spawn Z offset |
| `wflevels/smb_w1_1/blender_create_smb.py` | Coin shape, X velocity, friction |
