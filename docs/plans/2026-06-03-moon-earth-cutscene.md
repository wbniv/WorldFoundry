# Plan: Earth visibility fix + launch cutscene camera

## Why Earth is invisible

`Yon` (far clipping plane) defaults to 100 m. Earth is at 301 m.
**Fix: set `wf_Yon = 500.0` on `cs_chase`** so Earth is visible in normal play.

## Cutscene design

At ignition (phase 2, t=15–16 s) cut to `cs_earth` — a low-angle static shot
framing the lander on the pad with Earth hanging in the sky behind it. Camera
stays on `cs_earth` through early ascent so the rocket rises through frame with
Earth above. Returns to `cs_chase` when the player writes phase 0 (next level run).

```
cs_earth position: (30, -80, 5)   ← behind & below the lander
cs_earth tracks:   Player         ← always loaded; lander tracked via artemis_lander
                                    caused null GetObject (cross-PERM ref timing)
Yon:               500 m          ← Earth comfortably in range
FOV:               40°            ← telephoto, compresses lander+Earth
cutback:           t_minus > 20 s ← returns to cs_chase (~200 m ascent, off-screen)
```

### cs_chase (normal play) — after Yon fix

```
┌──────────────────────────────────────────────────────────────────┐
│ SCORE 0          TIME 12         LAT 26.13  LON -3.62           │
│                                                             ┌───┐│
│                                                             │ ◉ ││  ← minimap
│                     🌍                                      └───┘│
│                  (globe, upper sky)                              │
│                                                                  │
│     ████                                                         │
│    ██████  ← lander tower                                        │
│   ████████                                                       │
│─────┬──┬──────────────────────────────────────────────────────── │
│     │  │   ← lunar terrain                                       │
│   🧑‍🚀                                                             │
│  (astronaut)                                                     │
└──────────────────────────────────────────────────────────────────┘
  vista cam, fixed position (0,−75,50), FOV 60°, tracks player
  Earth visible as small disc in upper-right sky
```

### cs_earth (cutscene, ignition onward) — low telephoto behind lander

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                          🌍                                      │
│                     (Earth disc, larger —                        │
│                      40° FOV compresses scene)                   │
│                          │                                       │
│                          │  ← Earth directly above lander        │
│                         ███                                      │
│                        █████  ← lander mid-section              │
│                       ███████                                    │
│              🔥🔥🔥🔥🔥🔥🔥  ← Raptor exhaust cones (ignition) │
│─────────────────────────────────────────────────────────────────│
│              ░░░░░░░░░░░░░░░  ← crater rim / terrain            │
└──────────────────────────────────────────────────────────────────┘
  camera at (30,−80,5) tracking Player (see implementation notes), FOV 40°, Yon 500m

  at t+3s into ascent:

┌──────────────────────────────────────────────────────────────────┐
│                          🌍                                      │
│                         ███                                      │
│                        █████  ← lander higher in frame          │
│                       ███████                                    │
│                      █████████                                   │
│             🔥🔥🔥🔥🔥🔥🔥🔥🔥                                 │
│─────────────────────────────────────────────────────────────────│
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Camera switching mechanism

`EMAILBOX_CAMSHOT` (mailbox 1921) holds the active camshot's actor index.
Level.cc bootstraps it to the first camshot's index at load.

Each camshot writes its own actor index to a dedicated global mailbox at startup
so the player Forth script can reference them by name:

| Mailbox constant | Index | Written by |
|------------------|-------|------------|
| `MOON_CHASE_CAM_IDX` | 1883 | `cs_chase` startup script |
| `MOON_EARTH_CAM_IDX` | 1884 | `cs_earth` startup script |

Startup script (same pattern, different target mailbox):
```forth
\\ wf
INDEXOF_ACTOR_INDEX read-mailbox INDEXOF_MOON_CHASE_CAM_IDX write-mailbox
```

Player phase script adds camera cut logic after phase update:
```forth
\ phase 2 → cs_earth; phase 3 ≤20 s → cs_earth; phase 3 >20 s → cs_chase
INDEXOF_MOON_LAUNCH_PHASE read-mailbox 1 > if
  INDEXOF_MOON_LAUNCH_PHASE read-mailbox 2 > if
    INDEXOF_MOON_LAUNCH_T_MINUS read-mailbox 20 > if
      INDEXOF_MOON_CHASE_CAM_IDX read-mailbox INDEXOF_CAMSHOT write-mailbox
    else
      INDEXOF_MOON_EARTH_CAM_IDX read-mailbox INDEXOF_CAMSHOT write-mailbox
    then
  else
    INDEXOF_MOON_EARTH_CAM_IDX read-mailbox INDEXOF_CAMSHOT write-mailbox
  then
then
```

## Mailbox additions (`wfsource/source/mailbox/mailbox.inc`)

After MOON_LAUNCH_T_MINUS (1882):
```
MAILBOXENTRY( MOON_CHASE_CAM_IDX, 1883 )
MAILBOXENTRY( MOON_EARTH_CAM_IDX, 1884 )
```

## Changes

- `wfsource/source/mailbox/mailbox.inc` — 2 new entries (1883, 1884)
- `wflevels/moon_site01/blender_create_moon.py`
  - `cs_chase`: add `wf_Yon = 500.0`, add startup script writing to 1883
  - new `cs_earth` camshot at (30, −80, 5), Track=Player, Yon=500, FOV=40,
    startup script writing to 1884
  - room z_max: 300 → 2000 m (lander ascent headroom)
  - player Forth script: 3-branch camera logic (phase 2/early-3/late-3)
- `wfsource/source/game/scripting_stub.cc` — touch to force mailbox.inc recompile

## Lander despawn (timebomb fix)

`z = 0.5t²` — lander exits the room bbox (z_max 2000 m) at t≈63 s. Despawn instead:

```forth
INDEXOF_MOON_LAUNCH_PHASE read-mailbox 2 > if
  INDEXOF_MOON_LAUNCH_T_MINUS read-mailbox dup * 0.5 *
  dup 500 > if
    drop 0 INDEXOF_ALIVE write-mailbox   \ t≈32 s; camera already cut to cs_chase
  else
    INDEXOF_Z_POS write-mailbox
  then
then
```

Camera cuts back to `cs_chase` at t_minus > 20 s (t≈20 s into ascent, z≈200 m).
Lander despawns at z > 500 m (t≈32 s) — 12 s after the cutback, well before room exit.

## Implementation notes

**`Follow` and `Target` required non-null** (`movecam.cc:236`): even with
`Position X/Y/Z = Absolute`, `SetCameraParametersFromShot` still dereferences
`shotData->Follow` for the relative-vector calc. Both must name a valid live
actor. Used `CamTarget` (same as `cs_chase`).

**`Track Object = artemis_lander` crashed** (`movecam.cc:1067`): lander index
resolved non-zero at export but `theLevel->GetObject(idx)` returned null at
runtime — cross-PERM actor reference timing issue. Changed to `Player` (always
available). Camera at (30,−80,5) still frames the launch site correctly since
Player is between camera and lander/Earth.

**Room z ceiling** was 300 m (`max(300, heights.max+50)`). Lander hits 300 m
at t≈24.5 s of ascent (`z = 0.5t²`), triggering
`UpdateRoomContents: fell out of room 0` → actor invalidation → crash.
Raised to 2000 m; lander now stays in-room until t≈63 s (long after cutback).

## Screenshots

*(add first-light capture here when available)*

*(add finished capture here when polished)*

## Verification

1. `task build && task build-level -- moon_site01`
2. `task run-moon` — Earth sphere visible in `cs_chase` immediately
3. t=15 s → cuts to `cs_earth`; lander + Earth in frame
4. t=36 s (t_minus=20) → cuts back to `cs_chase`; player on terrain
