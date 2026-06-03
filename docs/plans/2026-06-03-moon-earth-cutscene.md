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
cs_earth tracks:   artemis_lander ← tilts up as lander ascends
Yon:               500 m          ← Earth comfortably in range
FOV:               40°            ← telephoto, compresses lander+Earth
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
  camera at (30,−80,5) tracking artemis_lander, FOV 40°, Yon 500m
  as lander ascends, camera tilts up — Earth stays in upper frame

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
INDEXOF_MOON_LAUNCH_PHASE read-mailbox 1 > if
  INDEXOF_MOON_EARTH_CAM_IDX read-mailbox INDEXOF_CAMSHOT write-mailbox
then
```
(phase > 1 = ignition or ascent → cs_earth; phase ≤ 1 = cs_chase via bootstrap)

No "return to chase cam" write needed — the level restarts fresh (phase resets
to 0) and bootstrap re-writes 1921.

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
  - new `cs_earth` camshot at (30, −80, 5), Track=lander, Yon=500, FOV=40,
    startup script writing to 1884
  - player Forth script: append camera cut trigger after phase write
- `wfsource/source/game/scripting_stub.cc` — touch to force mailbox.inc recompile

## Verification

1. `task build && task build-level -- moon_site01`
2. `task run-moon` — Earth sphere visible in `cs_chase` view immediately
3. Wait to t=15 s — camera cuts to `cs_earth` at ignition; lander + Earth
   both in frame; lander rises through frame during ascent
