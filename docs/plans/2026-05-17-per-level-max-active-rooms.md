# Per-level MAX_ACTIVE_ROOMS

**Status:** Parked — defer until after first level ships  
**Date:** 2026-05-17  
**Investigation:** [docs/qbert/investigations/2026-05-10-qbert-engine-caps.md](../../WorldFoundry.2026-new-level/docs/qbert/investigations/2026-05-10-qbert-engine-caps.md)

## Context

`AssetManager` pre-allocates `cbRoomMemory × MAX_ACTIVE_ROOMS` bytes upfront (`assets.cc:41`). `MAX_ACTIVE_ROOMS = 3` is a compile-time constant; Q✱bert only ever loads 1 room slot, wasting `2 × cbRoomMemory` (= 2 × 1.8 MB = 3.6 MB at current budgets).

`levelobj.oas` has no room-count field; adding a new OAS field is blocked until first level ships per project policy. The RAM block approach avoids the OAS change.

Parked because the waste (3.6 MB) is not blocking anything — HalLmalloc headroom is ample — and the OAD compat constraint makes now the wrong time.

## Investigation needed before implementation

**Can `nMaxActiveRooms` be derived dynamically at level load instead of authored explicitly?**

The level data (`_LevelOnDisk` / `_RoomOnDisk` in `levelcon.h`) is parsed before `AssetManager` is constructed. Each `_RoomOnDisk` has an `adjacentRooms[MAX_ADJACENT_ROOMS]` array of room indices. The actual maximum fan-out (how many distinct rooms are ever simultaneously adjacent) could be computed by scanning that array at load time:

- If every room lists itself as its only neighbour → `nMaxActiveRooms = 1`
- If any room lists 1 distinct neighbour → `nMaxActiveRooms = 2`
- If any room lists 2 distinct neighbours → `nMaxActiveRooms = 3`

This would eliminate the need for the `'NRMS'` IFF tag entirely. Verify that `_LevelOnDisk` / room data is available at the point in `Level::Level` where `AssetManager` is constructed (currently line 465, after `LoadLevelData()` at line 467 — check ordering). If level data is loaded *after* the AssetManager is constructed, the dynamic approach doesn't work and the explicit tag is required.

Value is always 1, 2, or 3 (1 for single-room games like Q✱bert, 3 for large multi-room games; 2 is rare).

## Design

Thread a per-level `nMaxActiveRooms` (explicit tag or derived — see investigation above) through the `AssetManager` constructor to the single `new char[]` at `assets.cc:41`. Fixed-size pointer arrays (`_activeRooms[MAX_ACTIVE_ROOMS]` in `actrooms.hp:84`, `adjacentRooms[MAX_ACTIVE_ROOMS]` in `room.hp:113`, `_assets[MAX_ACTIVE_SLOTS]` in `assets.hp:103`) are left unchanged.

### IFF wire format (fallback if dynamic derivation isn't feasible)

Append optional field pair after the existing FLAG group in `levelMemoryConfiguration` (`level.hp:254–264`). The sector is 2048 bytes, the struct is only ~44 bytes, so there's room. Backward-compatible: reader checks the tag before trusting the value; old IFFs fall back to `MAX_ACTIVE_ROOMS = 3`.

```
'NRMS' 1l      // number of active room slots; omit → default MAX_ACTIVE_ROOMS
```

### File changes

**1. `wfsource/source/game/level.hp:264`** — extend struct:
```cpp
uint32 tagFlags, doomStickFlag, bungeeCamFlag;
// optional — only present when tagNrms == IFFTAG('N','R','M','S')
uint32 tagNrms, nMaxActiveRooms;
```

**2. `wfsource/source/game/level.cc:421+`** — read after existing asserts, pass to constructor:
```cpp
int nMaxActiveRooms = MAX_ACTIVE_ROOMS;
if (plmc->tagNrms == IFFTAG('N','R','M','S'))
{
    RangeCheck(1, (int)plmc->nMaxActiveRooms, MAX_ACTIVE_ROOMS + 1);
    nMaxActiveRooms = (int)plmc->nMaxActiveRooms;
}
// line 465:
_theAssetManager = new (HALLmalloc) AssetManager(
    plmc->cbPerm, plmc->cbRoom, nMaxActiveRooms,
    videoMemory, *_levelFile, *_memory, *_assetCallbackRoom);
```

**3. `wfsource/source/asset/assets.hp:65`** — add `int maxActiveRooms` parameter; add `int _nMaxActiveRooms` private member.

**4. `wfsource/source/asset/assets.cc:38–41`** — store and use `_nMaxActiveRooms` in allocation.

**5. `wfsource/source/asset/assets.cc:143`** — fix perm-slot memory offset:
```cpp
(void*)&_assetMemory[_cbRoomMemory * _nMaxActiveRooms]   // was: PERM_SLOT_INDEX
```

**6. `wfsource/source/asset/assets.cc:194`** (`LoadRoomSlot`) — guard `slotNum < _nMaxActiveRooms`.

**7. `wflevels/qbert_practice/qbert_practice-standalone.iff.txt`** — add `'NRMS' 1l` after `'FLAG' 1l 1l`. Legacy levels use the backward-compat default.

## Verification

```sh
task build
task run-level -- wflevels/qbert_practice-standalone.iff
# HalLmalloc used should drop ~3.6 MB (measure via std::cerr << HALLmalloc after Level ctor)
task run-level -- wflevels/snowgoons-standalone.iff   # legacy path: still MAX_ACTIVE_ROOMS=3
```
