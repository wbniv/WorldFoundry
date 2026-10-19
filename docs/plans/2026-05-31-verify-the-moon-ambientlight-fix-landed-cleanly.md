# Plan: verify the moon AmbientLight fix landed cleanly

## Context

Just landed `b280d591` (moon AmbientLight) and `70e53d03` (levcomp warning + mm_practice fix + docs). The moon level now has a `wf_lightType='Ambient'` Light with RGB (0.40, 0.42, 0.50). Before merging on, do a quick visual eye-test — capture a fresh moon screenshot post-ambient, compare against the pre-fix baseline, confirm no regressions on the existing scene (terrain shading, lander tower, astronaut, HUD overlay, minimap).

Five-minute sanity check, not a full investigation. Outputs: one new screenshot saved to `docs/plans/screenshots/`, a brief commit note (or no commit if nothing's worth recording).

## Approach

### Capture

`task run-moon` rebuilds and captures via the existing `WF_GAME_SCREENSHOT_PPM` + `-record_video` flow. Use the recipe documented in memory `project_wf_game_headless_capture`:

```bash
rm -f wflevels/moon_site01/engine_screenshot.ppm output.mp4 /tmp/wfgame.log
WF_GAME_SCREENSHOT_PPM=$PWD/wflevels/moon_site01/engine_screenshot.ppm \
LD_LIBRARY_PATH=engine/libs DISPLAY=:0 \
timeout 12 engine/wf_game -record_video \
    --vram-width=4096 --vram-height=2048 \
    --vram-slot-width=1024 --vram-slot-height=1024 \
    -Lwflevels/moon_site01-standalone.iff > /tmp/wfgame.log 2>&1
ffmpeg -y -i output.mp4 -update 1 /tmp/moon_post_ambient.png
```

### Eye-test checklist

Compare the new screenshot against the most recent pre-ambient capture (`docs/plans/screenshots/2026-05-31-moon-hud-overlay-capture.png` is the cleanest baseline). Look for:

| Element | Expected post-fix | Regression signal |
|---|---|---|
| Terrain shading | Slightly fuller / brighter shadow side of crater rims; lit side unchanged (clamps) | Terrain looks washed-out grey everywhere, or unchanged from baseline (suggesting ambient didn't apply) |
| Lander tower | Visible. Lit side bright white, shadow side dim grey (was near-black) | Lander gone, or completely uniform brightness |
| Astronaut | Visible speck. Slightly more visible in shadow now | Astronaut invisible, or strangely overlit |
| HUD text top-left | Yellow SCORE/TIME/LAT/LON/ELEV/POS exactly as before | Text gone, mis-coloured, or repositioned |
| Minimap top-right | 128×128 with hillshade + spawn square + lander X + player dot + compass chevron + cardinals (N/S/E/W) + lat/lon ticks | Any element missing, mis-rendered, or shifted |
| Compass chevron | Cyan, pointing in player heading direction | Wrong colour, wrong direction |
| Cardinal labels | Orange N/S/E/W at minimap edges | Missing, wrong positions |

### Commit (if anything's worth recording)

If the screenshot looks clean and notably better than the pre-fix one, save it to `docs/plans/screenshots/2026-06-02-moon-post-ambient-baseline.png` and `git commit` referencing it from the existing ambient-light plan doc. If it looks identical or worse, dig into why before committing anything.

## Files modified

- `docs/plans/screenshots/2026-06-02-moon-post-ambient-baseline.png` (NEW; only if eye-test passes)
- `docs/plans/2026-06-01-ambient-light-default-and-warnings.md` (one-line "verified clean against post-fix capture" link, only if committing)

## Verification

The verification *is* the plan. If the screenshot reads as "moon, but slightly fuller shadow detail than before," we're done. If anything looks broken, investigate root cause separately.

## Estimate

5–10 min: 2 min capture, 5 min eye-test, optional 3 min commit + push if worth recording.
