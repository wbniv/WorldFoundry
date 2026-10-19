# SMB coins — true-contact pickup (tighter radius, all coins) + spin the coin-room coins

**Status:** Done — 2026-05-31 (~1.5 h). gold.cc radius 1.5→1.0 (all coins); coin-room
pickup is true XZ contact (`dx²+dz² < 1.0` vs each coin's real Z); coin-room coins are now
anchored `enemy`-schema mesh actors running `COIN_SCRIPT` (spin), not statplats. Verified
(`tests/verify_coin_contact.py`, ALL PASS): floor-walk under a column collects nothing;
touching a top-row or low-row coin collects only on contact. Recording: tests/recordings/smb_coin_room.mp4.

## Context

Two problems the coin room exposed, plus a global tweak:

1. **Pickup ignores the coin's height.** The coin-room coins are collected by the player
   script ([`blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) ~1287-1345)
   via a loose "am I underground" Z-band (`(player_z+46)² < 9`) + **X-only** proximity
   (`(player_x−coin_x)² < 1.5`). The coin's *actual* Z (rows 3/5/7) is never checked, so
   standing on the floor collects coins floating 6 m overhead just by lining up X. The player
   should have to **actually contact** the coin (X *and* Z).
2. **Coin-room coins don't spin.** `cr_coin_0..18` are built with `add_statplat` (anchored
   *collision boxes*), not Gold actors, so they never run the spin script the surface coins use
   (`COIN_SCRIPT` = `ROTATION_C = TIME`). They should spin like the others.
3. **Pickup radius is too loose, everywhere.** The engine Gold pickup is an XZ circle of **1.5 m**
   ([`gold.cc:51`](../../wfsource/source/game/gold.cc) `dx*dx + dz*dz > 1.5*1.5`) — this governs
   *all* Gold coins (the surface coins). It should be tighter (true contact), globally.

**Why the coin-room coins are fakes (and stay Forth-driven):** real Gold actors have a hard-coded
**5 s TTL** (`gold.cc:25,64`) and despawn — they'd vanish long before the player warps down to the
room. So the room coins stay script-driven (anchored, persistent); only the *pickup math* and the
*spin* are corrected to match the real coins.

## Change

### 1. Engine — tighter pickup radius for all coins
[`wfsource/source/game/gold.cc`](../../wfsource/source/game/gold.cc) `TryPickup` (line 51):
replace the literal `1.5f` with a named constant **`kGoldPickupRadius = 1.0f`** (XZ circle, `dx²+dz²
< r²`). 1.0 m is tighter than 1.5 m but still safe from tunnelling at Mario's top speed (~11 m/s ≈
0.24 m/frame at ~46 fps → ~8 frames inside a 1.0 m radius). Tunable in one place.

### 2. Coin room — contact pickup (X *and* Z), generated from one source
In `blender_create_smb.py`:
- **Hoist** `_CR_LOW_Z/_CR_MID_Z/_CR_HIGH_Z` + the `CR_COINS` list above the player-script
  definition (they depend only on `CR_FLOOR_TOP`, `T`, `SMB_COIN_n` — all defined early).
- **Generate** the coin-pickup Forth from `CR_COINS` (one block per coin, indexed `i` →
  `INDEXOF_SMB_COIN_{i}`): replace the X-only test with the same XZ circle as the engine —
  `INDEXOF_X_POS read-mailbox {cx} - dup *  INDEXOF_Z_POS read-mailbox {cz} - dup *  +  1.0 < if`
  (`dx²+dz² < 1.0`, using the coin's **real** row Z). Drop the outer `(player_z+46)²<9` band gate
  — the per-coin Z check subsumes it (a coin at Z≈−38 won't match a surface player at Z≈1.5).
  Keeps the existing `GOLD += 1` + `Visibility Mailbox → 0` on pickup. (Uses only `- * + <` —
  no zForth float-division traps; see [[feedback_zforth_int_divide]].)

### 3. Coin room — spinning coin actors
Convert the `cr_coin_N` creation loop from `add_statplat(...)` to **anchored mesh actors** that run
`COIN_SCRIPT` (spin) and carry the `Visibility Mailbox`. Model on `_make_coin_template`
(lines 679-711) but `Mobility='Anchored'` (float, no gravity/TTL), no `Template Object`, reuse the
coin-disc mesh + `mat_coin`. Pickup stays in the player script (a coin can't write the *player's*
`GOLD` mailbox cleanly — cross-actor writes are discouraged, see TODO `write-actor-mailbox`).

## Build + verify

1. `python3 -m py_compile wflevels/smb_w1_1/blender_create_smb.py`
2. `blender --background --python wflevels/smb_w1_1/blender_create_smb.py` → `task build-level -- smb_w1_1`
3. `touch engine/stubs/scripting_stub.cc && task build` (engine — gold.cc changed)
4. Headless bridge check (mirror `tests/verify_smb_pipe_warp.py`): warp Mario into the coin room, then
   - **walk along the floor under a coin row** → `GOLD` must **NOT** rise (Z too far now);
   - **jump up into a row** → only the coin(s) actually contacted collect;
   - confirm the coins **spin** (ROTATION_C advancing) — screenshot/recording.
5. Surface regression: `tests/verify_smb_scoring.py` — qblock coins still collect at the tighter radius.

## Files
- `wfsource/source/game/gold.cc` — pickup radius constant (all coins)
- `wflevels/smb_w1_1/blender_create_smb.py` — hoist `CR_COINS`, generate XZ pickup, spinning coin actors

## Open knob
`kGoldPickupRadius = 1.0 m` is my pick for "true contact, no tunnelling." Trivial to dial tighter
(coin disc is 0.75 m wide × 1.5 m tall) if it still feels generous.
