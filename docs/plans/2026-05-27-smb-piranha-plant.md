# SMB Piranha Plant

> Plan authored before implementation (plan-workflow convention). Commit with the code.
> **Status:** **Done** (2026-05-27, ~3 h — feature behaviourally correct early; the time went into
> a flaky *test*). Verified headless ([`tests/verify_smb_piranha.py`](../../tests/verify_smb_piranha.py),
> 4/4 across runs) + recording
> **[`tests/recordings/smb_piranha.mp4`](../../tests/recordings/smb_piranha.mp4)** (512×384, ~7 s).
> 3 new `mailbox.inc` globals, no C++ logic. The engine-fact bets all held: an **Anchored `Enemy`
> runs its `wf_Script`, has no Jolt body (non-colliding), and its `X/Z_POS` read+write both work**
> — so a script-driven, pipe-piercing, `DELTA_TIME`-smooth plant works exactly as designed.
>
> **What the bring-up surfaced (test-side, all now handled):**
> 1. **`discover_substr("piranha")` matched the *pipe* (`piranha_pipe`), not the plant
>    (`piranha_00`)** — and statplats don't broadcast `Z_POS`, so I saw a frozen 0 and wrongly
>    suspected the Anchored actor. Match the specific mesh.
> 2. **The bridge's per-step dt is wildly variable**, so step-COUNT windows ≠ level-TIME windows;
>    the plant's TIME-deadline oscillation sometimes didn't advance within N steps. Fixed by driving
>    every test window by **elapsed `TIME` (mailbox 1906)**, not step count — this was the real flake.
> 3. **Teleporting Mario onto an already-emerged plant bites him** (faithful), and those i-frames
>    masked the later hurt check. Fixed by ordering (hurt before retract) and pinning Mario *high
>    above* the pipe for the retract check (horizontal-only retract gate → still retracts, too high
>    to be bitten).
> **Estimate:** ~half a day (average-programmer scale). Compose + Forth; engine cost: three new
> `mailbox.inc` globals (rebuild to regenerate `INDEXOF_` — no C++ logic).

## Goal

A Piranha Plant that rises out of a pipe, pauses, sinks back, and repeats — hurting Mario on
contact, **retracting while Mario stands on the pipe** (so he can wait it out / ride it), and dying
to a fireball. New mechanic: smooth **vertical oscillation from a pipe**.

## Key engine facts (verified)

- **A non-moving actor still runs its `wf_Script`.** `Actor::CanUpdate()` is `true` for all actors,
  and `Actor::update` runs the script (`actor.cc:964`) for any actor with one, regardless of
  mobility. (The Generator's early-`return` that skipped its script was a Generator-specific quirk,
  since fixed — not a general Anchored limitation.)
- **An Anchored `Enemy` with a mesh has no Jolt body.** `actor.cc:803` only creates a body for
  `StatPlat`, an Anchored *Generator* mesh, or `Physics` (CharacterVirtual). So an **Anchored Enemy
  renders, scripts, and is non-colliding** → it can pass *through* a solid pipe (no need to hollow
  it) and be positioned purely by script.
- **Scripts can read frame delta:** `DELTA_TIME` (mailbox 1907, alongside `TIME`). So motion can be
  `Z_POS += RATE × DELTA_TIME` — smooth and **framerate-independent** (no ZSPEED/physics needed),
  honouring the variable-tick-rate rule (timing in seconds, not per-tick steps).

So the Piranha is an **Anchored, non-colliding `Enemy`** driven entirely by its script: it slides
its own `Z_POS` between a hidden Z (inside the opaque pipe → occluded) and an emerged Z (head above
the pipe top), and uses proximity (not collision) for hurt + fireball-defeat, exactly like the
Goomba/Koopa.

## Placement

New decorative pipe + plant at **X = 24** — a clear stretch between `qblock1` (@21) and `pit0`
(@28.5) on `ground_0`. Pipe: 2 tiles wide (X 23–25), 2 tall (top `Z = 3`), solid green `statplat`
(Mario can stand on it). Plant at `(24, 0, …)` (Y=0 = pipe centre, behind the front face when
hidden). This is the warp-`entry_pipe`'s twin minus the warp — no conflict with the pipe-warp.

## New globals ([`mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc), free 18xx)

| Name | idx | role |
|---|---|---|
| `SMB_PIRANHA_UP` | 1835 | phase target: nonzero = emerge, 0 = retract (toggled on a `TIME` deadline) |
| `SMB_PIRANHA_NEXT` | 1836 | level-time of the next phase toggle |
| `SMB_PIRANHA_GO` | 1837 | per-tick decision (1 = rise this tick, 0 = sink): phase-up **and** Mario not on top |

(`INDEXOF_` prefix per the standing convention; flagged wanted-gone, not silently spread.)

## `PIRANHA_SCRIPT` (Anchored Enemy)

```
\ wf
\ Phase toggle every DWELL (~2 s): rise-phase <-> sink-phase.
TIME > PIRANHA_NEXT ? -> flip PIRANHA_UP ; PIRANHA_NEXT = TIME + DWELL

\ Decide GO this tick: rise iff phase-up AND Mario is NOT standing on the pipe.
GO = (PIRANHA_UP != 0)
if |playerX - myX| < ~1.2  AND  playerZ > 2.0  ->  GO = 0   \ Mario on top -> retract

\ Move toward the limit at RATE * DELTA_TIME (framerate-independent slide).
GO ? (Z_POS < EMERGED_Z -> Z_POS += RATE*dt)
   : (Z_POS > HIDDEN_Z  -> Z_POS -= RATE*dt)

\ Hurt: emerged (Z_POS > PIPE_TOP) AND Mario in contact (close in X AND Z) -> SMB_PLAYER_HURT.
\ (Walking past at ground level is safe — the plant is overhead; jumping into it hurts.)

\ Fireball defeat (any height): fresh fireball within r^2=2.5 -> ALIVE 0  (same idiom as goomba).
```

Constants: `HIDDEN_Z ≈ 1` (inside the pipe, occluded), `EMERGED_Z ≈ 5` (head clears the pipe top
@3), `PIPE_TOP = 3`, `RATE ≈ 3` units/s, `DWELL ≈ 2` s. No stomp branch — a Piranha can't be
stomped (touching it always hurts), unlike the Goomba/Koopa.

## Authoring (`blender_create_smb.py`)

- Build the plant mesh (green stem box + a red/white head sphere, ~koopa style).
- `attach_schema('enemy')`, **`Mobility = Anchored`**, `Model Type = Mesh`, `Visibility = 1`,
  `wf_Script = PIRANHA_SCRIPT`. Seed it at `HIDDEN_Z`.
- Add the decorative green pipe `statplat` at X=24.

## Verification

New `tests/verify_smb_piranha.py` (debug bridge):
1. Discover `player` + the plant (by mesh name). Step and sample the plant's `Z_POS` over ~3 s →
   assert it **oscillates** (max − min above a threshold, i.e. it rises and sinks).
2. **Retract-on-top:** pin the player above the pipe (`X≈24`, high `Z`) for ~2 s → assert the plant
   stays low (`Z_POS` near `HIDDEN_Z`, doesn't emerge).
3. **Hurt on contact:** place the player at the emerged plant's height beside the pipe → assert
   `SMB_PLAYER_HURT` fires.
4. **Fireball defeat:** drop a fireball's live broadcast onto the plant (or fire at it) → assert the
   plant despawns (`set_mailbox` → "actor not found"; reuse the despawn probe).
5. **Recording:** `python3 tests/verify_smb_piranha.py --record` →
   **[`tests/recordings/smb_piranha.mp4`](../../tests/recordings/smb_piranha.mp4)**, per the
   [recording convention](2026-05-26-fire-mario-fireball-pooled-generator.md#recording-checked-in-proof).

> Test-harness note: drive every window by **elapsed `TIME` (mailbox 1906)**, not step count — the
> bridge's per-step dt is too variable for step-count windows. And `discover` the plant by its
> specific mesh (`piranha_00`), not `piranha` (which also matches `piranha_pipe`, a statplat that
> doesn't broadcast `Z_POS`).

Reuse the despawn-probe + onto-the-projectile idioms from the
[fireball-defeat test](../../tests/verify_smb_fireball_defeat.py); both gotchas are in the
[designer guide](../level-design-troubleshooting.md). Regression: enemy + fireball harnesses still
pass (run individually).

## Known limitations / follow-ups

- **Single plant.** `SMB_PIRANHA_*` are globals (one plant in W1-1); multiple plants need per-actor
  state slots, same ceiling as the one-Koopa / one-fireball limits.
- **Non-colliding plant.** It hurts via proximity, not a real collision body — consistent with how
  every WF enemy works under Jolt (CharacterVirtual-vs-CharacterVirtual fires no contact).
- **No biting animation / placeholder mesh** — a head that opens/closes is polish.

## Sources

- [Koopa shell-kick](2026-05-27-smb-koopa-shell-kick.md) / [Fireball defeats enemies](2026-05-27-smb-fireball-defeats-enemies.md) — the proximity-defeat + freshness idioms reused here.
- `actor.cc` (`CanUpdate`, the `Actor::update` script run at `:964`, the Jolt-body gating at `:803`); `DELTA_TIME` in [`mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc).
- Pipe/`statplat` authoring + `ENEMY_SCRIPT` in [`blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py).
