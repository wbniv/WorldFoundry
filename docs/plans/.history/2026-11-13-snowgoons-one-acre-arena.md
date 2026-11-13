| Date | Change |
|------|--------|
| [2026-11-13](https://github.com/wbniv/WorldFoundry/commit/ab3fc569) | Plan a one-acre Snowgoons backyard, with to-scale mockups |

<!--history-meta v1
ab3fc569	author	Will Norris
ab3fc569	added	257
ab3fc569	deleted	0
ab3fc569	files	1
ab3fc569	body	Will asked for the Snowgoons arena to be enlarged to one acre. Today's\nlawn is 697 m2 (0.17 acre; 1 WF unit = 1 m by gravity 9.81, a 2 m\nplayer and a 2 m door). The plan replaces the classic level's 3ds Max\narena with a generated, level 60 x 68 m yard (4,080 m2) in a new asset,\nyard01.iff, leaving snowgoons-blender.lev, quadpatch01.iff and the\nmacOS-gate level untouched.\n\nEngine facts found on the way shape it: UVs are clamped to 0-1\n(material.cc CLIP01), so the lawn tiles through a 4 m grid; mesh\ncolliders ignore actor rotation (jolt_backend.cc:287), so the yard has\nno pitch; and a static enclosing the spawn is skipped as a zone volume\n(jolt_backend.cc:681), so a ground slab and hedge walls carry collision.\n\nMockups: a plan view generated from the shipped meshes and CPU Cycles\nrenders from the Blender container, before and after. Six choices are\nopen for Will; no asset or engine change yet. TODO entry added (T4).\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqR6tvK6k2yfENoAXy7
-->
