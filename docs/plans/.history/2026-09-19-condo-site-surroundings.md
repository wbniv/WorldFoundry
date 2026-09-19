| Date | Change |
|------|--------|
| [2026-09-19](https://github.com/wbniv/WorldFoundry/commit/70815109) | feat(condo): the surroundings — near buildings as geometry, 8 km skyline, the bridges, catalog |

<!--history-meta v1
70815109	author	Will Norris
70815109	added	233
70815109	deleted	0
70815109	files	1
70815109	body	Every OSM footprint within 150 m is now a prism in one site-buildings mesh (heights by\nbuilding type; nothing near the pin is tagged), a podium carries floors 1–5 under the units,\nand the sky panorama holds the 642 towers ≥ 40 m within 8 km plus Rama IX, Bhumibol 1 and 2\nand Kanchanaphisek as deck + pylon + cable silhouettes (pylon heights from a table — OSM has\nnone; the named bridges are man_made=bridge outlines, merged with the cable-stayed\nexpressway ways by proximity). make_site_textures.py also writes site-buildings.json,\na generated site-catalog.md (what is in view and from which window) and an overview\nmockup of buildings and heights.\n\nTwo engine facts learned on the way, both now in the level README:\n- WF's face normal is (v2−v0)×(v1−v0), the opposite hand of Blender's, so exterior\n  geometry built in Blender must be recalc'd then reversed; the sky dome is left\n  Blender-outward. With the prisms wound the Blender way the walls were culled under\n  WF_CULL=1 and lit from the wrong side, which read as a flat, depth-less mass.\n- Coincident faces at the ground flicker (the reported "z-buffer issue at the bottom of\n  the buildings"): the prisms had bottom faces coplanar with the ground quad sharing its\n  base edge. Prisms are open-bottomed now and the podium is inset 5 cm from the ground,\n  the parapet plane and the slab bottoms.\n\nAlso: levcomp places an actor by its mesh-bbox centre, so the room bbox is ±170 m\n(the merged mesh's centre fell outside ±15 m, the actor was dropped and the engine\ndereferenced a null actor).\n\nPlan: docs/plans/2026-09-19-condo-site-surroundings.md\n\nCo-Authored-By: Claude Opus 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_017hM4VFRoFFkipNVRLTs42g
-->
