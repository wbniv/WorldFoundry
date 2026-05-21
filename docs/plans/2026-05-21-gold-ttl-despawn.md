# Gold coin — TTL despawn in `Gold::update()`

**Status:** In progress  
**Parent plan:** [2026-05-19-smb-coin-fix-and-template.md](2026-05-19-smb-coin-fix-and-template.md)

## Problem

Coins spawned by the `?`-block Generator are invisible in gameplay.  Root cause: physics tunnelling at low framerates (1 fps on the dev machine gives dt ≈ 1 s). In two frames the coin's Jolt character accumulates −16 m/s Z velocity, tunnels through the 1.5 m-thick floor trimesh, and disappears below the level geometry permanently.

## Fix

Add `Gold::update()` with a 1.5-second TTL despawn.  
- `_despawnTime = startupData->currentTime.Current() + 1.5` (set in constructor)  
- `update()`: if `LevelClock().Current() >= _despawnTime`, call `SetPendingRemove(this)` and return  
- Matches SMB arcade behaviour — coin pops up briefly then vanishes

No OAD field for TTL per `feedback_no_new_oas_fields_premerge`; hardcoded `kGoldTTL = 1.5f`.

## Files

| File | Change |
|------|--------|
| `wfsource/source/game/gold.hp` | Add `virtual void update()` + `_despawnTime` member |
| `wfsource/source/game/gold.cc` | Implement `Gold::update()` + set `_despawnTime` in ctor |

## Plan

- [x] Write `gold.hp` + `gold.cc` (constructor sets `_despawnTime`, `update()` checks TTL)
- [ ] Rebuild: `task build`
- [ ] Test: bump `?` block, coin appears ~1 s then vanishes; no crash
- [ ] Update parent plan status
