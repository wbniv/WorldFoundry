# Condo sun: tie SUN_ALT_DEG/SUN_AZ_DEG to a true solar position

## Context

`wflevels/condo_639_640/site_constants.py:35-36` hardcodes the condo's sun as
`SUN_ALT_DEG = 50.0`, `SUN_AZ_DEG = 30.0` (compass ≈150°/SSE per the file's own
`sun_compass()` comment) — an artist pick, not a real moment. Both downstream
consumers already read these two constants through the shared `sun_compass()` helper:
`blender_create_condo.py`'s `Sun` actor (lines 863-877, via `SUN_ALT_DEG`/`SUN_AZ_DEG`
directly) and `make_site_textures.py:396`'s painted sun disc in `condo_sky.tga`. The
site's real coordinates are already plumbed through (`SITE_LATLON = (13.6935894,
100.5334137)`, Soi Sathu Pradit, Bangkok), so nothing else needs new site data — the
gap is purely that the sun angle isn't derived from it.

This was flagged as out of scope by `docs/plans/2026-09-20-condo-wall-shading-definition.md`
(unrelated to that plan's flatness fix) and auto-captured into `TODO.md`'s Inbox at
commit time; this plan picks it up on its own.

**Checked first, before designing anything:** whether the current 50°/150° pair
corresponds to *any* real moment at this latitude. It doesn't, closely — a brute-force
scan across all of 2026 finds the closest real match is 2026-06-21 ~11:55 local
(altitude 78.6°, azimuth 150.0°), off by ~29° combined from today's altitude. At
13.69°N the sun swings through a much wider altitude/azimuth range across a single day
than the fixed pair implies (see the plan's Mockups table: 08:00 → alt 27°/az 84° (E),
12:00 → alt 77°/az 13°, 16:00 → alt 32°/az 278° (W)). So "tie it to reality" is a real
design decision, not just plumbing — the user's direction: default to the actual
wall-clock time when the level is built, not a fixed historical moment.

## Approach

Add a small, self-contained NOAA-low-precision solar-position function — pure Python,
stdlib only (`math` + `zoneinfo` for `Asia/Bangkok`, no new pip dependency) — so it runs
identically inside Blender's bundled interpreter (`blender_create_condo.py`) and plain
`python3` (`make_site_textures.py`), with no new manual install step. Rejected: the
`astral` package (does exactly this, but isn't installed in either Python and adding it
is an avoidable manual/reproducibility burden for ~50 lines of self-contained math).

In `site_constants.py`:

1. New function `solar_position(lat_deg, lon_deg, dt_utc) -> (altitude_deg, azimuth_deg)`
   implementing the standard NOAA low-precision algorithm (Julian-day → geometric mean
   longitude/anomaly → equation of time → hour angle → altitude/azimuth). Verified
   against known values during planning (see Mockups table) — accurate to a fraction of
   a degree, which is all a fixed-angle level light needs.
2. Resolve the datetime to use: `CONDO_SUN_DATETIME` env var (ISO 8601 local time, e.g.
   `2026-06-21T16:00:00`) if set, else `datetime.now(ZoneInfo("Asia/Bangkok"))` — the
   actual moment the script runs, per the user's direction. (Thailand has no DST, so
   `Asia/Bangkok` is a fixed UTC+7 offset — no ambiguity to handle.)
3. Replace the two literals: `SUN_ALT_DEG, SUN_AZ_DEG = solar_position(*SITE_LATLON,
   dt_utc)` computed once at import time, keeping the same names so `sun_compass()`,
   `blender_create_condo.py`, and `make_site_textures.py` need **no changes** — they
   already just read these two module-level constants.
4. **Altitude floor.** Below some low altitude (proposed: 5°) the level has no real
   night/dusk rendering support (no shadows, no sky-color transition), so a near-horizon
   or below-horizon real sun would light the scene almost entirely from ambient with a
   near-useless grazing directional term, or (if literally negative, i.e. actually
   nighttime at build time) point the "sun" below the ground plane entirely. Clamp
   altitude to the floor rather than let a level built at 22:00 come out looking like a
   rendering bug. Log a `[condo] sun: <real alt> clamped to <floor>°` line when this
   fires, so it's visible, not silent.
5. **Reproducibility trade-off — explicit, not hidden.** `condo-textures` is currently
   documented in `Taskfile.yml:759` as "offline, byte-stable." With a wall-clock-default
   sun, a rebuild an hour later produces a different `condo_sky.tga` and a different
   `Sun` actor angle — no longer byte-stable by default. Update that task's `desc:` to
   say so, and document `CONDO_SUN_DATETIME=<iso>` as the way to get a byte-stable
   rebuild (e.g. for CI or a deliberate "freeze this look" commit).

## Mockups

[![Sun path at this site's latitude across one day — fixed art-direction sun (50°/150°) vs. what a real sun does](2026-09-20-condo-sun-solar-position/sun-path-diagram.png)](2026-09-20-condo-sun-solar-position/sun-path-diagram.html)

The table and sun-path diagram in the interactive mockup are **real outputs of the
algorithm above**, computed during planning for 2026-09-20 at this site's lat/lon — not
illustrative guesses. They show the dynamic range `CONDO_SUN_DATETIME` introduces:
altitude swings 27°→77°→32°→10° and azimuth swings 84°→13°→278° across a single day,
against today's single fixed 50°/150° pair. [Open the interactive
mockup](2026-09-20-condo-sun-solar-position/sun-path-diagram.html) — it also states the
mechanism (algorithm, default-to-now, `CONDO_SUN_DATETIME` override) so a reviewer can
see the whole shape of the change in one place.

There's no "after" render of `condo_sky.tga`/the level itself yet, since the change
doesn't exist — once implemented, a rebuild at the moment of landing is itself the real
"after" state (that's the point of the feature), so Verification step 3 captures that
rather than a separate mockup screenshot.

## Out of scope

- A live in-engine day/night cycle (this is build-time only — the sun angle is baked
  into the level at export, not recomputed while playing).
- Daylight-saving handling beyond `Asia/Bangkok`'s fixed UTC+7 (Thailand has none).
- Any change to `blender_create_condo.py`'s wall/seam-shading work
  (`docs/plans/2026-09-20-condo-wall-shading-definition.md`) — unrelated, already
  landed.
- Extending real-solar-position sun angles to other levels — this plan only touches
  `wflevels/condo_639_640/site_constants.py`, which is condo-specific.
- Deciding a "canonical frozen" `CONDO_SUN_DATETIME` for the committed level artifacts
  (`condo_639_640.iff`, `condo_sky.tga`, etc.) — those get whatever moment they're next
  rebuilt at, per the user's direction; if a specific frozen look is wanted later for a
  release/screenshot, that's a follow-up decision, not this plan's.

## Verification

1. Unit-check `solar_position()` against the known reference values computed during
   planning: for `SITE_LATLON` on 2026-09-20 local time, 08:00 → alt≈26.6°/az≈84.3°,
   12:00 → alt≈77.1°/az≈12.9°, 16:00 → alt≈32.1°/az≈277.5°, 17:30 → alt≈10.3°/az≈271.5°
   (within 0.5° is a pass — these came from the same algorithm run standalone, so this
   is really "does the in-repo copy match the planning copy," catching transcription
   bugs).
2. Run `CONDO_SUN_DATETIME=2026-06-21T11:55:00 python3 -c "from site_constants import
   SUN_ALT_DEG, SUN_AZ_DEG; print(SUN_ALT_DEG, SUN_AZ_DEG)"` (from
   `wflevels/condo_639_640/`) and confirm it prints ≈`78.6 150.0` — the best real match
   to today's fixed look found during planning.
3. Run `task condo-textures` and `task condo-level` with no `CONDO_SUN_DATETIME` set
   (default = actual current time) and confirm both complete without error, the `[condo]
   sun: …` log line reports a plausible altitude/azimuth for whatever time it actually
   ran, and (if it's currently below the floor) the clamp message fires correctly.
   Capture the resulting `condo_sky.tga` and a level screenshot into this plan's bundle
   as the real "after" state.
4. Re-run `task condo-textures` twice one minute apart with `CONDO_SUN_DATETIME` **set**
   to the same fixed value both times; confirm `condo_sky.tga` is byte-identical
   (`cmp` exit 0) — proves the override restores byte-stability for anyone who needs it.

<!--
When the work lands, this section becomes the permanent record:

1. **Step as originally written.**

```
$ the exact command
raw output, unedited
```

**PASS** — one line on what the output proves.

An item stays `[verify T<n>]` in TODO.md until every step here has recorded output.
-->
