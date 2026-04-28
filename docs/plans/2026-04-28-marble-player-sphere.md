# Replace Player Mesh with Sphere (Marble)

**Date:** 2026-04-28  
**Level:** `marble-madness`  
**Script:** `wflevels/marble-madness/blender_update_player_sphere.py`

## Problem

`marble-madness.lev` uses `player.iff` (the snowman model from snowgoons) as a placeholder
for the marble. The snowman mesh is tall and capsule-shaped; it looks wrong and has incorrect
physics dimensions for a marble.

## Approach

Headless Blender script: import `marble-madness.lev`, replace the Player object's mesh with
a UV sphere (radius 0.5, centred at Z=0.5 so it sits on the ground), update the WF custom
properties that control the exported mesh filename and collision box, tune marble physics
fields, then export back in-place.

## Changes made

| Property | Before | After |
|----------|--------|-------|
| Mesh file | `player.iff` (snowman) | `sphere.iff` |
| `wf_original_bbox` | (-0.332,-0.359,0.002, 0.332,0.359,2.002) | (-0.5,-0.5,0.0, 0.5,0.5,1.0) |
| Vertical Elasticity | 0.5 (default) | 0.3 |
| Horizontal Elasticity | 0.5 (default) | 0.7 |
| Running Acceleration | 10.0 (default) | 15.0 |

## How to re-run

```bash
cd wflevels/marble-madness
blender --background --python blender_update_player_sphere.py
bash ../../wftools/wf_blender/build_level_binary.sh marble-madness
```
