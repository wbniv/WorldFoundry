# Investigation: why the whole Starship HLS sits on the moon (vs. Apollo / Blue Moon stage-separated landers)

**Date:** 2026-06-02
**Status:** Reference / rationale

## The question

The Artemis lander on `moon_site01` (built in [docs/plans/2026-05-31-moon-artemis-lander.md](../plans/2026-05-31-moon-artemis-lander.md)) is a ~47 m tall white cylinder with Raptor nozzles at the base, an ARTEMIS stripe, a crew door, and a nose cone — the entire silhouette of a Starship vehicle. Looking at it parked next to a 1.8 m astronaut on the regolith, the natural question is "isn't only a fraction of a Starship supposed to land? The launch rocket is huge."

Apollo / Blue Moon intuition says: yes, the launch vehicle stays on Earth, a small lander stage detaches and lands, often an even smaller ascent stage launches back. So why does our lander look like the whole rocket?

## Answer

**Starship HLS is the outlier.** Every other lunar lander concept — flown or proposed — separates into stages somewhere along the way. Starship HLS doesn't. The whole vehicle is what touches down, stays, and launches back.

| Lander | Launch vehicle | What lands | What ascends back |
|---|---|---|---|
| **Apollo LM** (Eagle, etc.) | Saturn V (~110 m) | Descent + Ascent stages (~7 m total) | Just the Ascent stage (~3.8 m, cabin + small engine) |
| **Blue Moon MK1 "Endurance"** | New Glenn (~98 m) | The lander (~7 m) — cargo only, one-way | Nothing — single-shot delivery |
| **Blue Moon MK2** (later Artemis variant) | New Glenn / Vulcan | Descent + Ascent stages | Ascent stage |
| **NASA Altair concept** (cancelled) | Ares V | Descent + Ascent stages | Ascent stage |
| **Chinese Lanyue** (planned) | Long March 10 | Descent stage (kept) + Crew cabin (ascends) | Crew cabin |
| **Starship HLS** (Artemis III, IV) | Super Heavy (~70 m) + Starship (~50 m) — booster returns to Earth, Starship continues | **Whole Starship (~50 m)** | **Whole Starship** |

The reason Starship can pull this off is the moon's small gravity well. A ~50 m, fully-fueled-at-launch vehicle can't ascend from *Earth* to orbit single-stage at any reasonable payload — that's why Super Heavy exists. But the moon's escape velocity is ~2.4 km/s vs. Earth's ~11.2 km/s. With Starship's Raptor performance and the refueling-in-Earth-orbit step that fills the tanks before the translunar transfer, a single Starship has enough delta-v to brake into lunar orbit, descend, land, sit a while, and ascend back to lunar orbit — all on its own propellant.

## Mission phasing (Starship HLS)

In rough order:

1. **Earth launch.** Super Heavy lifts Starship HLS to upper atmosphere. Super Heavy separates and returns to launch site (or catch tower). Starship HLS continues on its own.
2. **Earth orbit refueling.** Starship HLS docks (or "rendezvouses propellantly") with a chain of tanker Starships in low Earth orbit. Multiple tanker launches are needed to fill the HLS's tanks; the exact count depends on cryogenic boil-off and tanker efficiency and is still being refined.
3. **Translunar injection.** Fully fueled, HLS burns for the Moon.
4. **Lunar orbit insertion.** HLS brakes into NRHO or low lunar orbit (mission-dependent). Meanwhile, Orion launches separately on SLS with crew, also rendezvouses in lunar orbit.
5. **Crew transfer (orbit).** Astronauts EVA-walk (or transfer through a docking adapter) from Orion to HLS.
6. **Descent.** HLS does the powered descent and lands on the moon. Whole ~50 m vehicle on the regolith.
7. **Surface stay.** Days to weeks, depending on mission.
8. **Ascent.** Whole HLS lifts off the moon using its Raptors. No stages dropped.
9. **Lunar orbit rendezvous.** HLS meets Orion again. Crew transfers back to Orion.
10. **Earth return.** Orion comes home with the crew. HLS either stays in lunar orbit, returns to Earth orbit, or is disposed of (mission TBD).

## What this means for the moon level

The lander as built — full vehicle silhouette at 1:1 scale — is **architecturally faithful**. It's not an artistic compromise that should "really" show only the bottom half. If anyone looks at the screenshot and goes "isn't a Starship 110 m? Why is the lander so much shorter than that?" — the answer is the height comparison they're thinking of is **Super Heavy + Starship stacked on the launch pad** (~120 m). On the lunar surface, only the upper ~50 m exists.

For comparison value, if we wanted to author an Apollo-LM-style lander into the level later, the silhouette would be drastically different: ~7 m tall, splayed legs, descent stage with a separate ascent capsule perched on top. The Apollo LM `_build_apollo_lm()` would be roughly an order of magnitude shorter than the current Starship HLS — which would dramatically change the astronaut-vs-lander scale shot the current build captures.

## Alternative landers we considered

The original lander plan ([docs/plans/2026-05-31-moon-artemis-lander.md](../plans/2026-05-31-moon-artemis-lander.md)) briefly weighed Blue Moon MK1 (the actual vehicle landing at Site 01 fall 2026) vs. Starship HLS. Starship won for "iconic Artemis-era silhouette at vista distance" — Blue Moon MK1 is much smaller (~7 m) and would read as a tiny dot from the camera's vista position. The trade-off is real: Blue Moon would be more historically/locationally accurate; Starship is more visually dominant.

If we ever want a "fall 2026 actual landing site" mode, swapping to a Blue Moon MK1 silhouette is a 30-minute change — replace `_build_artemis_lander()` with a `_build_blue_moon_mk1()` helper. Either silhouette is fine geometrically; the choice is about which mission the player is supposed to be visiting.

## References

- [docs/plans/2026-05-31-moon-artemis-lander.md](../plans/2026-05-31-moon-artemis-lander.md) — the original moon lander plan, where Starship HLS was picked over Blue Moon MK1.
- `wflevels/moon_site01/blender_create_moon.py` — `_build_artemis_lander()` helper, the actual ~47 m primitive build.
- NASA Artemis III / IV mission overview: https://www.nasa.gov/humans-in-space/artemis/
- SpaceX Starship HLS overview: https://www.spacex.com/vehicles/starship/
- Blue Origin Blue Moon: https://www.blueorigin.com/blue-moon
