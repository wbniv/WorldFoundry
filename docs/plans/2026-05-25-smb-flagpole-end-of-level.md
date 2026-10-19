# SMB W1-1: flagpole ends the level (statplat + ActBox composition)

**Status:** Done + verified (2026-05-25). Flagpole = `statplat` (pole+flag art) + an invisible
`ActBox` (`MailBox`=1905/`END_OF_LEVEL`, `MailBoxValue`=1, `Activated By Actor`=Player).
Verified headless ([tests/verify_flagpole.py](../../tests/verify_flagpole.py)): Mario walked into
the trigger (bbox reached ~61.5) → level ended with a **clean exit (code 0)**; the ActBox renders
nothing (screenshot: pole visible, no box). **Footgun hit + worked around:** `ActBox::activate`
writes `Activated Actor Mailbox` unconditionally and its default is the **reserved** mailbox 0
(`mailbox.cc` asserts `>= 2`) → the first attempt aborted (`SIGABRT: write to mailbox #0`). Fixed
level-side by pointing it at a scratch slot (`SCRATCH_USER_START = 4005`); the engine-guard
alternative is deferred to [`TODO.md`](../../TODO.md) § ENGINE ROBUSTNESS per owner.

## Context

Roadmap item #2: reaching the flagpole ends the level. The flagpole is **not a class** — it's a
**composition** (see the [composition pattern](../level-building.md#composing-actors--sensors--visuals-reach-for-this-before-a-new-class)
and the [SMB→primitives mapping](../investigations/2026-05-25-smb-features-to-wf-primitives.md)):
a dumb visual `statplat` (pole + flag art) **+** an invisible `ActBox` trigger volume that writes
`END_OF_LEVEL` when the Player enters it.

Two earlier drafts were rejected: an X-position threshold in Mario's script (forces the author to
transcribe the flagpole's coordinate) and flagpole-as-`generator`+script (overloads a class —
kind-vs-capability smell). The `ActBox` composition needs **no script, no coordinate, no class**.

**Mechanism (verified):**
- `INDEXOF_END_OF_LEVEL` = global mailbox **1905** ([`mailbox.inc:31`](../../wfsource/source/mailbox/mailbox.inc)); writing nonzero → [`level.cc`](../../wfsource/source/game/level.cc) `EMAILBOX_END_OF_LEVEL` sets `_done` → `RunLevel` loop exits → `UnloadLevel`.
- `ActBox` ([`actbox.oas`](../../wfsource/source/oas/actbox.oas)) writes `MailBox = MailBoxValue` when an actor passing its `Activated By` filter overlaps its volume. Its overlap test is `Activation::Activated()` → `PhysicalAttributes::CheckCollision` ([`activate.cc`](../../wfsource/source/physics/activate.cc)) — PA-based AABB, **independent** of the legacy collision pipeline that's dead under Jolt; the player is in `ROOM_OBJECT_LIST_COLLIDE` and its PA is Jolt-synced each frame before `ActBox::update()`. So it fires.

## Change — [`wflevels/smb_w1_1/blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py)

- **Flagpole pole + flag**: keep as `statplat`, visual only, no script. Pure art.
- **Add an invisible `ActBox` trigger volume** at the flagpole:
  - a cube mesh spanning ~`[FLAGPOLE_X−1.5 .. +1.5]` × `[−T .. +T]` × `[0 .. ~8]` so Mario's body
    overlaps it as he reaches the pole (the mesh bounds → the actor's `Global Bounding Box` =
    the activation volume, the same way the coin's BOX3 is derived);
  - `attach_schema(box, 'actbox')`;
  - `wf_MailBox = 1905` (`INDEXOF_END_OF_LEVEL`; define a Python `END_OF_LEVEL = 1905` with a
    comment citing `mailbox.inc:31`, not a bare literal);
  - `wf_MailBoxValue = 1`;
  - `wf_Activated By Actor = 'Player'` (ActivatedBy defaults to 1=Actor, matching snowgoons'
    actboxor);
  - keep it **invisible** (ActBox `DEFAULT_VISIBILITY = 0`; confirm Model Type / Visibility so it
    renders nothing but still carries a usable bbox).

## Build & verify

1. `blender --background --python wflevels/smb_w1_1/blender_create_smb.py`
2. **Confirm the fields landed** in `smb_w1_1.lev` (guard against an OAD-export drop like the
   `Gold Value` case): the actbox chunk should carry `MailBox`/`MailBoxValue`/`Activated By Actor`
   + a sensible `Global Bounding Box` BOX3.
3. `bash wftools/wf_blender/build_level_binary.sh smb_w1_1`
4. Bridge: `watch` mailbox **1905**; `inject_input joystick1_raw=0x2000` (RIGHT) to walk Mario to
   the flagpole; confirm 1905 → 1 on entry and the level ends (`RunLevel` loop exits → clean
   process exit — record it). Screenshot Mario at the pole; confirm the ActBox is **invisible**.
5. Regression: `python3 tests/verify_smb_scroll.py` → 4/4.

## Notes / scope

- No "course clear" screen — `END_OF_LEVEL` just unloads (polish = separate follow-up; tracked in
  the [SMB mapping](../investigations/2026-05-25-smb-features-to-wf-primitives.md) 🚧 list).
- Log any gotchas (ActBox volume sizing, invisible-actor bbox) to
  [`docs/level-design-troubleshooting.md`](../level-design-troubleshooting.md) as discovered.

## Files

| File | Change |
|------|--------|
| [`wflevels/smb_w1_1/blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) | flagpole stays `statplat`; add an invisible `ActBox` writing END_OF_LEVEL on Player overlap |
| `wflevels/smb_w1_1.iff` / `-standalone.iff` / `.lev` / `.lvl` | rebuilt artifacts |
