# Plan: ambient-light defaults, exporter warning, level data fixes

**Status:** Proposed
**Date:** 2026-06-01
**Estimate:** ~1 h (low-risk pieces only) / ~2 h (with engine-default change)

## Context

The moon Earth/Sun investigation ([2026-06-01-moon-sky-earth-sun-stars](../investigations/2026-06-01-moon-sky-earth-sun-stars.md)) uncovered that **no shipped level actually has a working Ambient-type Light actor**:

| Level | Lights | Ambient? |
|---|---|---|
| snowgoons-blender | 4 Directional | none |
| smb_w1_1 | 1 Directional | none |
| smb_w1_2 | 1 Directional | none |
| qbert_practice | 1 Directional | none |
| moon_site01 | 1 Directional | none |
| mm_practice | 1 with `STR "Ambient" + DATA 0` | **broken** (DATA says Directional, STR says Ambient — runtime reads DATA) |

So every level runs with `Camera::SetAmbientColor(Color::black)` (defaulted in `wfsource/source/game/level.cc:1158`). Most levels get away with it — qbert / SMB are flat-shaded so each face is fully lit or fully shadowed (intentional), snowgoons has 4 directionals covering many angles. The moon's curved heightfield + 2°-altitude sun is the first time the absence shows up as "any sphere actor renders pure black."

This makes "no ambient light" both a **level-data bug** (every level needs to author at least one) and a **latent engine default** (defaulting `SetAmbientColor` to *black* makes the forgetful case fail silently).

## Four changes, four risk levels

### 1. Fix the moon level data — add an Ambient Light actor

**Effort:** 5 min. **Risk:** zero. **Value:** moon stops being broken for any curved-geometry actor.

`wflevels/moon_site01/blender_create_moon.py`: duplicate the existing directional Light, set `wf_lightType='Ambient'`, RGB ≈ 0.4 grey with a slight blue tint. Pattern is in the new `docs/level-design-troubleshooting.md` "Actor renders pure black despite light" entry (commit `914816df`).

### 2. Fix `mm_practice` data corruption — DATA 0 vs STR "Ambient"

**Effort:** 10 min. **Risk:** low (only mm_practice runs are affected).

The .lev has `DATA 0l` with `STR "Ambient"`. Pick one and make them consistent — almost certainly DATA should be `1l` (= Ambient) since the author clearly meant Ambient. Confirms with a quick visual check that mm_practice gets noticeably lighter.

While there, audit the rest of the file for other STR/DATA mismatches (`a decompiled .lev enum field whose DATA and STR disagree is corrupt` is already documented at `docs/level-design-troubleshooting.md:383` — this finding belongs in `BUGS.md` per the pre-2026 originated rule).

### 3. `levcomp-rs` warning — no Ambient Light authored

**Effort:** 30 min. **Risk:** very low (warning only, no behaviour change).

In `wftools/levcomp-rs`, during level parse: count actors of class `light` and group by `lightType` enum value. If the count of `lightType=1 (Ambient)` is zero, emit:

```
levcomp-rs: WARNING: level has no Ambient-type Light actor — Camera::SetAmbientColor
            defaults to black, so any curved-geometry actor (spheres, terrain meshes,
            anything with N·L = 0 at any face) will render pure black on its shadowed
            side. See docs/level-design-troubleshooting.md "Actor renders pure black
            despite light".
```

Also catch the mm_practice-style DATA/STR mismatch and warn. The "actor outside room bbox" warning is precedent for this style; same file (`levcomp-rs/src/`).

### 4. Engine default raise — **dropped from scope**

Originally proposed raising `SetAmbientColor`'s default from black to 0.4 grey. Cut from scope per user direction: don't change existing levels' appearance. The engine default stays at `Color::black`; new levels (and the moon fix) author their own Ambient Light explicitly.

That keeps qbert / SMB / snowgoons / mm_practice pixel-identical to today and means:

- The levcomp warning at (3) is now the ONLY catch for "new level forgot ambient" — it's a build-time warning, not a runtime safety net.
- Any new author who ignores the warning gets the same pure-black-sphere disaster the moon hit. That's an OK trade-off given the warning is loud.

If a future author finds the warning insufficient and wants the engine-level floor anyway, it can come back as its own plan with explicit before/after of every existing level so the visual change is documented.

## Documentation alongside

Already covered:
- `docs/level-design-troubleshooting.md` "Actor renders pure black despite light" (commit `914816df`)
- `docs/investigations/2026-06-01-moon-sky-earth-sun-stars.md`

Still missing:
- `docs/level-building.md` — the *positive* guide. Add a short "Lighting" section ahead of any level creation: "Every level should author at least one Directional Light (with non-zero RGB and a sensible azimuth) AND at least one Ambient Light (RGB ≈ 0.3–0.5 grey). Without ambient, curved-geometry actors render their shadow side pure black."

## Recommended order

1. **(3) Levcomp warning** first — lowest risk, immediately useful for the next person authoring a level. Will fire on every existing level too — that's the *signal* that they're consuming the default; they don't get rebuilt against this warning unless someone touches them.
2. **(1) Moon level fix** — adds an Ambient Light to `moon_site01` (the only level where the missing-ambient bug actually shows up visibly). Also lets us drop in test Earth/Sun spheres knowing the ambient pre-req is satisfied.
3. **(2) mm_practice data fix** — separate, smaller. Logged to BUGS.md if pre-2026; the existing "STR/DATA disagree is corrupt" rule already covers it.

Engine default change (#4): **dropped from scope**.

Documentation update (`docs/level-building.md`) goes alongside (1).

## Post-landing verification (2026-06-02)

Captured `docs/plans/screenshots/2026-06-02-moon-post-ambient-baseline.png` after `b280d591` to eye-test for regressions. Plan: [`2026-05-31-verify-the-moon-ambientlight-fix-landed-cleanly.md`](2026-05-31-verify-the-moon-ambientlight-fix-landed-cleanly.md). Result: **clean**. HUD/text-block/minimap/cardinals/lat-lon-ticks all intact; terrain shading shows the subtle ambient lift (shadow side of crater rims slightly fuller, lit side unchanged because it clamps). No regressions.

## Files affected (per item)

- (1) `wflevels/moon_site01/blender_create_moon.py`
- (2) `wflevels/mm_practice/mm_practice.lev`
- (3) `wftools/levcomp-rs/src/main.rs` (the levcomp warning path used for the bbox warnings is the precedent)
- (4) `wfsource/source/game/level.cc`
- Docs: `docs/level-building.md`

## Verification

- After (1): re-screenshot moon at default ambient — terrain looks slightly brighter, shadowed slopes readable. No black holes on the astronaut.
- After (2): run mm_practice, confirm marble visible from any angle (was previously bright from forward, dark from behind).
- After (3): rebuild each existing level via `task build-level -- …`. Expect zero warnings for mm_practice (after the data fix) and warnings for every other level. The exit code stays 0 (warnings don't fail the build).
- After (4): screenshot every level (moon, smb_w1_1, smb_w1_2, qbert_practice, snowgoons-blender, mm_practice) before and after. Look for unintended brightness changes. If qbert's shadowed cube faces become too bright, reconsider the grey value.
