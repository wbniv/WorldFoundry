# moon_site01 — Cinematics Spec

Red-pen this doc to correct anything wrong. Implementation follows from the
approved table + mockups, not from prose descriptions.

---

## Actors & fixed positions

| Actor | Position (X,Y,Z) | Notes |
|-------|-----------------|-------|
| Artemis lander | (30, 25, 0) | Base at ground level; top ~47 m up |
| cs_earth cam | (30, −80, 5) | 105 m south of lander, 5 m off ground |
| cs_chase cam | (0, −100, 80) | Vista — 128 m diagonal from origin |
| Earth sphere | (0, 2000, 400) | R=80 m; ~4° apparent diameter |
| Sun disc | (164, 451, 17) | R=8 m; warm-white |
| Player spawn | (0, 0, 5) | Drops to terrain centre |

---

## Phase / timing table

| Phase | Level-clock range | Value of `MOON_LAUNCH_PHASE` | `T_MINUS` meaning |
|-------|------------------|------------------------------|-------------------|
| Idle / pre-launch | forever (no trigger yet) | 0 | — |
| Countdown | 0 – 10 s | 1 | 10→0 (seconds until launch) |
| Ignition | 10 – 11 s | 2 | 0 |
| Ascent | 11 s + | 3 | seconds since ignition |

*(Level clock starts when the level loads. Launch is automatic at t=10 s.)*

---

## Shot list

| # | Name | Active when | Duration |
|---|------|-------------|---------|
| A | `cs_earth` — pre-launch static | Phase 0–1 (t = 0 – 10 s) | 10 s |
| B | `cs_earth` — ignition | Phase 2 (t = 10 – 11 s) | 1 s |
| C | `cs_earth` — ascent tracking | Phase 3, T_MINUS ≤ 20 s | 20 s |
| D | `cs_chase` — overhead camp | Phase 3, T_MINUS > 20 s | rest of level |

---

## Shot A — `cs_earth`, pre-launch static (t = 0–10 s)

**Camera:** position (30, −80, 5) · Fixed rotation · FOV 40° · Yon 2500 m  
**Tracking:** launch_tracker (proxy at lander XY, Z = ground level during pre-launch)  
**What should be in frame:**

```
┌────────────────────────────────────────────────────────────────┐
│  ✦  ✦    ✦   ✦  ✦    ✦   ✦    ✦   ✦    ✦   ✦    ✦   ✦  ✦  │
│    ✦    🌍      ✦    ✦   ✦   ✦    ✦   ✦    ✦  ✦    ✦   ✦    │  ← Earth ~11° off-center upper area
│  ✦   ✦    ✦   ✦    ✦                        ☀   ✦    ✦   ✦  │  ← Sun ~14° right of center
│                                                                │
│─────────────────────────── horizon ───────────────────────────│
│                                                                │
│                    ▓▓▓▓▓                                       │  ← lander top
│                   ▓▓▓▓▓▓▓                                      │
│                   ▓▓▓▓▓▓▓                                      │
│                    ▓▓▓▓▓                                       │
│────────────────────┬──┬────────────────────────────────────────│
│     lunar surface  │  │                                        │
└────────────────────┴──┴────────────────────────────────────────┘
  FOV 40°  ·  sky upper ~40%  ·  lander centered  ·  T-minus HUD counting down
```

**HUD:** `LAUNCH IN T-N` banner, countdown 10→1.

---

## Shot B — `cs_earth`, ignition (t = 10–11 s)

Same framing as Shot A. The lander doesn't move yet.

```
┌────────────────────────────────────────────────────────────────┐
│  ✦  ✦    ✦   ✦  ✦    ✦   ✦    ✦   ✦    ✦   ✦    ✦   ✦  ✦  │
│    ✦    🌍      ✦    ✦   ✦   ✦    ✦   ✦    ✦  ✦    ✦   ✦    │
│  ✦   ✦    ✦   ✦    ✦                        ☀   ✦    ✦   ✦  │
│                                                                │
│─────────────────────────── horizon ───────────────────────────│
│                    ▓▓▓▓▓                                       │
│                   ▓▓▓▓▓▓▓                                      │
│                ░░░▓▓▓▓▓▓▓░░░                                   │  ← exhaust/glow at base
│                ░░░▓▓▓▓▓░░░░░                                   │
│────────────────────┬──┬────────────────────────────────────────│
│     lunar surface  │  │                                        │
└────────────────────┴──┴────────────────────────────────────────┘
  HUD: "IGNITION"
```

---

## Shot C — `cs_earth`, ascent tracking (phase 3, T_MINUS 0–13 s)

Camera stays fixed at (30,−80,5). `launch_tracker` Z rises as `z = 0.5 × T_MINUS²`.  
At T=13s: tracker Z ≈ 84 m. Camera tilts up to keep lander centred.

```
t = 0 s after ignition:           t = 13 s after ignition:
┌──────────────────────────┐      ┌──────────────────────────┐
│ ✦  🌍  ✦   ✦   ✦  ☀  ✦ │      │ ✦  ✦   ✦   ✦   ✦  ✦  ✦ │
│ ✦   ✦   ✦   ✦   ✦   ✦  │      │ ✦   ✦   ✦   ✦   ✦   ✦  │
│ ──────── horizon ─────── │      │ ✦   ✦   ✦   ✦   ✦   ✦  │
│         ▓▓▓▓▓            │      │ ──────── horizon ─────── │
│        ▓▓▓▓▓▓▓           │      │         ▓▓▓▓▓            │  ← lander at ~84 m
│         ▓▓▓▓▓            │      │        ▓▓▓▓▓▓▓    🌍  ☀ │  ← Earth/Sun now lower
│ ─ lunar surface ──────── │      │         ▓▓▓▓▓            │
└──────────────────────────┘      │ ─ lunar surface ──────── │
                                  └──────────────────────────┘
```

At T=20s the lander is ~200m up and accelerating; cut to Shot D.

---

## Shot D — `cs_chase`, overhead camp (phase 3, T_MINUS > 13 s)

**Camera:** position (0, −100, 80) · Fixed rotation · FOV 60° · Yon 2500 m  
**Tracking:** Player  
**What should be in frame:**

```
┌────────────────────────────────────────────────────────────────┐
│ SCORE 0        TIME 0:23        LAT 26.13  LON -3.62     ┌──┐ │
│                                                           │  │ │  ← minimap
│                                                           └──┘ │
│ ✦  ✦   ✦   ✦  ✦   ✦   ✦   ✦  ✦   ✦   ✦  ✦   ✦   ✦  ✦  ✦  │
│ ✦   ✦   ✦   ✦   ✦   ✦   ✦   ✦   ✦   ✦   ✦   ✦   ✦   ✦   ✦  │
│──────────────────────────── horizon ──────────────────────────│
│                                                                │
│   [LTV rover]  [VSAT tower]   [Blue Moon lander]              │
│                                              [FSH hab]         │
│─────────────────────────────────────────────────────────────── │
│          🧑‍🚀  ← player walking around                           │
└────────────────────────────────────────────────────────────────┘
  FOV 60°  ·  39° downward angle  ·  Earth NOT in frame (47° off-axis)
  Note: Earth not visible here — that's fine, the rocket show is over
```

---

## Open questions — please red-pen

1. **Shot A framing** — is Earth in the right place (upper area, slightly off-center)? Or should it be more centered? More prominent?
2. **Shot A sky/terrain split** — roughly 40% sky, 60% terrain+lander. Should there be more sky?
3. **Earth apparent size** — ~4° diameter (vs real ~1.9° from Moon). Larger? Smaller?
4. **Cut timing at 13 s** — does the ascent-tracking phase feel long enough before we cut away?
5. **Shot D** — is the overhead camp view correct for the "rest of level" period? Or should the player have control of camera?
6. **Anything missing?** — fade between shots? Additional shots?

---

## Current script logic (for reference — edit the table above, not this)

```forth
\ runs every frame on the Player actor
phase = MOON_LAUNCH_PHASE
if phase > 1                              \ phase 2 or 3
  if phase > 2                            \ phase 3 (ascent)
    if T_MINUS > 20
      CAMSHOT ← MOON_CHASE_CAM_IDX       \ Shot D
    else
      CAMSHOT ← MOON_EARTH_CAM_IDX       \ Shot C
    then
  else
    CAMSHOT ← MOON_EARTH_CAM_IDX         \ Shot B
  then
else
  CAMSHOT ← MOON_EARTH_CAM_IDX           \ Shot A  (guarded: skip if idx=0)
then
```
