# SMB coin follow-ups: wire OAD Gold Value into the live pickup path + correct stale doc

**Status:** Done (2026-05-25). `TryPickup` (`gold.cc:54`) now awards `getOad()->GoldValue` on the live proximity-pickup path; engine rebuilt clean (exit 0). Stale [coin-fixes plan](2026-05-22-smb-coin-fixes.md) status corrected to Done; dead-`Collision` path logged in `TODO.md`. Definitive +N HUD screenshot needs interactive play-test (headless pickup capture is throttle-bounded, same caveat as the prior coin plans).

## Context

The TTL stale-clock bug reported during play-testing is **already fixed**. Commit `948c3fbc`
(2026-05-22) added [`wfsource/source/game/level.cc`](../../wfsource/source/game/level.cc):1689
(`startupData->currentTime = theLevel->LevelClock()`) immediately before
`ConstructTemplateObject`, stamping a fresh spawn-time clock into the value-copy field that
`Gold::Gold` reads at [`gold.cc`](../../wfsource/source/game/gold.cc):29. The generator's coin
spawn routes through `SafelyConstructTemplateObject`, so it benefits. **No engine change is
needed for the TTL** — the earlier "STILL LIVE" diagnosis was wrong (it read `gold.cc:29` in
isolation and trusted the stale `Status:` line of
[the coin-fixes plan](2026-05-22-smb-coin-fixes.md)).

Confirming that surfaced two genuine gaps left over from the *same* commit:

1. **The OAD `Gold Value` field is dead.** The active pickup path is `TryPickup`
   (`gold.cc:54`, called every tick from `Gold::update()`), which hardcodes `+ Scalar::one`.
   The path that honors `getOad()->GoldValue` is `Gold::Collision` (`gold.cc:97`) — but the
   file header (`gold.cc:6`–9) documents that `Collision` is **never called** for these coins
   (they are `MOBILITY_PHYSICS` → CharacterVirtual, invisible to
   `JoltContactDispatch::FindActorForBodyID`). So the `Gold Value` field added in `948c3fbc`
   silently does nothing; every coin awards exactly 1, regardless of the OAD value.

2. **Stale plan-doc status.** [`2026-05-22-smb-coin-fixes.md`](2026-05-22-smb-coin-fixes.md)
   was *created* by `948c3fbc` but its `Status:` line still reads `Not started`, even though
   that commit implemented it. This is what produced the wrong diagnosis above.

## Changes

### 1. Wire the OAD value into the live pickup path — `gold.cc:54`

In `TryPickup`, replace the hardcoded award with the OAD-configured value, mirroring the
(currently-dead) `Gold::Collision` logic at line 97:

```cpp
// BEFORE (gold.cc:54):
pm.WriteMailbox(EMAILBOX_GOLD, pm.ReadMailbox(EMAILBOX_GOLD) + Scalar::one);
// AFTER:
pm.WriteMailbox(EMAILBOX_GOLD, pm.ReadMailbox(EMAILBOX_GOLD) + Scalar((float)getOad()->GoldValue));
```

`getOad()->GoldValue` is already proven (it compiles and is used at `gold.cc:97`).
`EMAILBOX_GOLD` is the existing named mailbox constant — keep it (no bare integers).

Leave `Gold::Collision` (`gold.cc:82`–101) as-is. It is dead for `MOBILITY_PHYSICS` coins but
harmless, and the two-path duplication is now intentional and consistent. Folding the two
paths into a shared helper is **out of scope** (separate cleanup).

### 2. Correct the stale doc status — `2026-05-22-smb-coin-fixes.md`

Flip `**Status:** Not started` to a Done line crediting `948c3fbc` for items 1–3 + the
spawn-Z offset, and noting the `Gold Value` wire-up (this change). Mark each of the five plan
items with its real state (TTL stale-clock, NES size, rightward drift, spawn-Z: done in
`948c3fbc`; friction params: verify present in the Blender script; OAD value: completed here).

### 3. Sync `wf-status.md`

Prepend a **one-sentence** paragraph to the Summary section recording that the SMB coin now
awards its OAD-configured `Gold Value` on the active proximity-pickup path (the field added in
`948c3fbc` had been wired only into the dead Jolt-`Collision` path). Link this plan doc; keep
it reverse-chronological at top.

### 4. Log the dead-`Collision` observation — `TODO.md`

Add an entry noting `Gold::Collision` is unreachable for `MOBILITY_PHYSICS`/CharacterVirtual
coins (cross-ref `gold.cc:82` + the file header), so future readers don't "fix" the
non-functional value there instead of `TryPickup`.

## Build & verify

```bash
task build                      # gold.cc changed
ls -la engine/wf_game           # confirm binary timestamp advanced (don't trust grep'd output)
```

End-to-end proof the `Gold Value` field now takes effect (screenshots as proof):

- Temporarily set `coin_template`'s `Gold Value` to `3` in
  [`wflevels/smb_w1_1/blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py),
  rebuild the level (`blender --background --python .../blender_create_smb.py` →
  `build_level_binary.sh smb_w1_1` → `iffcomp standalone smb_w1_1`), bump a `?`-block, walk
  Mario into the coin, and screenshot the HUD jumping by **3** not 1. Then revert `Gold Value`
  to the faithful default (1) and rebuild the level so the shipped artifact stays
  arcade-correct.
- Regression: `python3 tests/verify_smb_scroll.py` → all 4 screenshots pass.

## Commit

Single commit (code + both docs together):
`fix(gold): award OAD Gold Value on active pickup path; mark coin-fixes plan done`.

## Critical files

| File | Change |
|------|--------|
| [`wfsource/source/game/gold.cc`](../../wfsource/source/game/gold.cc) | `TryPickup` line 54 → `getOad()->GoldValue` |
| [`2026-05-22-smb-coin-fixes.md`](2026-05-22-smb-coin-fixes.md) | Status `Not started` → Done |
| [`wf-status.md`](../../wf-status.md) | One-sentence Summary row, synced with plan status |
| [`TODO.md`](../../TODO.md) | Note dead `Gold::Collision` path for MOBILITY_PHYSICS coins |
