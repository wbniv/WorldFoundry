# Plan: SMB shared mesh library — one model per type, game-wide

**Date:** 2026-06-01
**Status:** Planning (gallery + approach; sharing-depth decision pending)

## Context

The mesh assets duplicate on **two axes** today:

1. **Per-instance** — the exporter ([`export_level.py:1025`](../../wftools/wf_blender/export_level.py))
   writes **one `.iff` per object**, named by object name, even when objects share a Blender mesh
   datablock. So 16 goombas → `goomba_00.iff … goomba_15.iff`, 19 coin-room coins →
   `cr_coin_0.iff … cr_coin_18.iff`, etc.
2. **Per-level** — every level dir (`wflevels/smb_w1_1/`, `wflevels/smb_w1_2/`) re-exports its **own**
   copy of every mesh; there's no shared `coin.iff`.

The room asset pool (`cbRoom`, the `Named Room #N` lmalloc) loads one entry per **unique mesh `.iff`
referenced**. W1-2's faithful population references **108 unique meshes** → the pool OOMs on load
(`Lmalloc … out of memory, Named Room #0`). The fix is **not** a pool bump
([[feedback_check_git_diff_before_bumping_pools]]) — it's **one mesh per model type, reused
everywhere** ([[feedback_share_mesh_datablocks]]).

**Goal (user):** *"one coin / player / brick / koopa … for the whole game, not per world/level."*

## Gallery of unique SMB models

Material colours shown as `RGB → #hex`. "Geometry" is the primitive recipe in the Blender builders.
"Now" = how many distinct `.iff`s currently exist (per-instance × per-level); "Target" = 1 shared.

### Characters
| Model | Geometry | Material(s) | Now → Target |
|---|---|---|---|
| **Mario** (player) | cube torso/head + cylinder limbs | red `0.87,0.14,0.07 → #DE2412`, blue `0.18,0.34,0.76 → #2E57C2`, skin `0.96,0.73,0.41 → #F5BA69` | 2 → **1** |
| **Goomba** | flattened UV-sphere body + tan band + 2 feet | brown `0.55,0.27,0.06 → #8C450F`, tan `0.83,0.65,0.34 → #D4A657` | ~29 → **1** |
| **Green Koopa** | flattened shell sphere + skin head sphere | green `0.14,0.56,0.20 → #248F33`, skin `0.90,0.76,0.34 → #E6C257` | ~4 → **1** |
| **Red Koopa** | same mesh, red shell | red `0.78,0.12,0.10 → #C71F1A` + skin | ~1 → **1** (shares geometry w/ green; material variant) |
| **Piranha Plant** | stem + head spheres/cyls | stem `0.20,0.70,0.24 → #33B33D`, head `0.85,0.16,0.12 → #D9291F` | ~4 → **1** |

### Pickups
| Model | Geometry | Material(s) | Now → Target |
|---|---|---|---|
| **Coin** | thin disc/cube | gold `1.0,0.84,0.0 → #FFD600` | ~40 → **1** |
| **Super Mushroom / Fire Flower** | shared state-aware template cube | base red `0.85,0.16,0.12 → #D9291F` (recolours to fire-white at runtime via FACE_COLOR) | ~2 → **1** |
| **Starman** | small cube/star | yellow `0.98,0.85,0.10 → #FAD91A` | ~2 → **1** |
| **1-Up Mushroom** | mushroom template | green `0.05,0.75,0.05 → #0DBF0D` | ~2 → **1** |

### Effects / projectiles
| Model | Geometry | Material(s) | Now → Target |
|---|---|---|---|
| **Fireball** | small cube | orange `0.98,0.45,0.05 → #FA730D` | ~2 → **1** |
| **Spark** (firework) | small bright cube | warm `1.0,0.95,0.55 → #FFF28C` | ~2 → **1** |
| **Score Popup** | small cube | yellow `1.0,0.95,0.2 → #FFF233` | ~2 → **1** |
| **Brick Debris** | small cube | brown `0.77,0.42,0.0 → #C46B00` | ~2 → **1** |

### Blocks / terrain (fixed-size → 1 mesh; sized → 1 unit cube + per-object scale)
| Model | Geometry | Material / texture | Now → Target |
|---|---|---|---|
| **? Block** | 1-tile cube | `qblock` TGA (yellow ? on orange) | ~5 → **1** |
| **Brick** | 1-tile cube | `brick` TGA (orange running-bond) | ~15 → **1** |
| **Hard Block** (staircase / pyramid steps) | **unit cube, per-object scale** | hard-block `0.48,0.25,0.05 → #7A400D` | ~28 → **1** |
| **Ground segment** | **unit cube, per-object scale** | grid TGA top + side `0.56,0.38,0.15 → #8F6126` | ~6 → **1** |
| **Pipe** | box (+ optional rim) | pipe-green `0.0,0.62,0.0 → #009E00` | ~7 → **1** (+ scale for height) |
| **Underground Ceiling** | wide box | brick TGA / `0.55,0.30,0.14 → #8C4D24` | ~2 → **1** |
| **Coin-Room Floor** | box | `0.45,0.22,0.05 → #73380D` | ~1 → **1** |

### Flagpole / castle
| Model | Geometry | Material(s) | Now → Target |
|---|---|---|---|
| **Flagpole Pole** | 16-sided cylinder | grey `0.72,0.72,0.72 → #B8B8B8` | ~2 → **1** |
| **Pole Flag** | vertical slab | green `0.10,0.65,0.16 → #1AA629` | ~2 → **1** |
| **Castle** | stone block | `0.60,0.55,0.50 → #998C80` | ~1 → **1** |
| **Castle Door** | dark face | `0.05,0.04,0.06 → #0D0A0F` | ~1 → **1** |
| **Warp-Zone Sign** | small board | yellow `0.95,0.92,0.20 → #F2EB33` | ~1 → **1** |

≈ **26 unique model types** vs **108 unique meshes** currently in W1-2 alone.

## Architecture (corrected, per user 2026-06-01)
- **Rooms are the asset-streaming unit.** Each SMB level has **2 rooms**: `RM0` (the whole surface
  level, loaded at level start) and `RM1` (the bonus coin room, streamed in on pipe-entry). The OOM
  is `RM0` — it must hold every unique surface mesh at once.
- **PERM is per-level** (loaded once per level, shared by *that level's* rooms) — NOT game-wide.
  So "load once for the whole game" is not a thing; the runtime unit is the level. "One coin for the
  whole game" means **one source `.iff`** (no per-level source copies), loaded per-level.

## Approach
1. **Exporter dedup** — `export_level.py`: write one `.iff` per **mesh datablock**, not per object;
   the 2nd+ object sharing a datablock references the first's `.iff`. Auto-fixes the already-shared
   goombas/coins (no limit change). Builders for the rest (koopas, bricks, hard-blocks, pipes,
   piranhas) start sharing a datablock — build geometry once, instance with per-object location
   (and scale for size variants) — so the dedup applies to them too.
2. **Put the common meshes in PERM** — these levels barely stream, so the shared models
   (coin/goomba/brick/koopa/…) belong in PERM: loaded once per level and shared by `RM0`+`RM1`
   instead of duplicated per-room. Cuts the `RM0` pool directly.
3. **One source `.iff` per type** — a single canonical mesh per model in a shared dir, referenced by
   all SMB levels (no per-level source copies).
4. **If PERM overflows** (plausible if "everything" goes in PERM — fine for these small 80s ports):
   **shrink the ROOM texture allocation** (`PAGEX/PAGEY` in `textile.flags`, freeing room for
   `PERMPAGEX/PERMPAGEY`). This is a limit/allocation change → **discuss with user first**
   ([[feedback_check_git_diff_before_bumping_pools]]).

## Order of operations
(1) exporter dedup + builder datablock-sharing is the no-limit-change core that fixes the per-instance
bloat (108→~26 unique in RM0) and very likely the OOM by itself. (2) PERM placement + (4) the
texture rebalance come after, with sign-off, only if still needed.

## Rule captured
[[feedback_share_mesh_datablocks]] (identical actors share one mesh; each unique mesh = a room-pool
entry) + [[feedback_check_git_diff_before_bumping_pools]] (never bump a limit without asking).
