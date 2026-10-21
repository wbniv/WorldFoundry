# Spike 0e: maturity sweep

Part of [the Planted Tank screensaver plan](../../2026-10-21-planted-tank-screensaver.md) (Phase 0e, Verification step 2).

**Question.** How long does a tank take to finish growing, and does every seed finish before the engine's 240 s age clamp (`planted::tick` in `wfsource/source/game/plant_settings.h`)?

**Method.** `tests/plant_maturity_sweep.cpp` calls `plantgrowth::colonies` and `plantgrowth::meshes` (`wfsource/source/game/plant_growth.h`) for seeds 0 to 199 in both waters. T(seed, water) is the maximum of `birth + duration` over every vertex of all 8 chunks; a vertex is fully grown once `age >= birth + duration` (see `deformedWave`). The harness exits non-zero if any T exceeds 240. Run it with `task test-plant-maturity` (builds and runs in `wf-linux-test:local`, repo mounted read-only).

## Raw output

```
water          min  median     p95     max  worst   vtx_min   vtx_max >200/>240
freshwater  103.49  135.26  162.61  187.84     48     73332     99420     0/0  
  determinism seed 713: T=137.5392 vertices=82888, repeat T=137.5392 vertices=82888 -> identical
saltwater   107.54  141.15  167.91  193.34     48     71776     83684     0/0  
  determinism seed 713: T=144.2470 vertices=78212, repeat T=144.2470 vertices=78212 -> identical
RESULT: PASS (all T <= 240 s)
```

## Numbers

T in seconds of growth age (that is, wall seconds at 1× speed).

| Water | min | median | p95 | max | worst seed | T > 200 | T > 240 | vertices (min to max) |
|---|---|---|---|---|---|---|---|---|
| Freshwater | 103.49 | 135.26 | 162.61 | 187.84 | 48 | 0 | 0 | 73 332 to 99 420 |
| Saltwater | 107.54 | 141.15 | 167.91 | 193.34 | 48 | 0 | 0 | 71 776 to 83 684 |

- No seed exceeds 200 s, so none comes near the 240 s clamp. The largest T overall is 193.34 s (saltwater, seed 48), 46.66 s below the clamp.
- Determinism: seed 713 computed twice gives identical T and vertex count in both waters (freshwater 137.5392 s, saltwater 144.2470 s).
- Vertex counts (about 72 000 to 99 000 per tank) are plausible for 8 chunks of blade geometry, so the sweep is measuring real meshes, not empty ones.

## Recommended maturity bound

**195 s** (sweep maximum 193.34 s rounded up to the next 5 s).

Margin: the bound is 1.66 s above the worst measured tank and 45 s below the 240 s clamp, so the growth clock can never hold a tank short of fully grown for seeds 0 to 199, and a longer-growing unseen seed would still finish before the clamp unless it exceeds about 240 s. The sweep covers 200 seeds, not all 2^32; if the level wants extra safety it can use a larger bound up to 235 s at the cost of a longer hold. The bound is in growth-age seconds, so the level's clock (which adds `dt × speed`) compares against it directly at any speed.
