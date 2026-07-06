| Date | Change |
|------|--------|
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/d1e98510) | feat(gfx): software backface culling, opt-in via WF_CULL=1 (default off) |

<!--history-meta v1
d1e98510	author	Will Norris
d1e98510	added	156
d1e98510	deleted	0
d1e98510	files	1
d1e98510	body	The glpipeline/Metal renderers never enabled GL_CULL_FACE — both sides of every\ntriangle drew (z-fighting, back-face bleed-through). Add a winding-independent\nsoftware cull in the single DrawTriangle chokepoint: transform the object-space\nface normal + face centre into eye space via the modelview and skip the triangle\nwhen dot(Ne, Pe) > 0 (facing away from the camera at the origin). Mirrors the\nexisting SetDirLight eye-space transform. Honors a new DrawTriangle cullExempt\nparam — the matte/HUD background passes true, and the dormant DOUBLE_SIDED\nmaterial flag (Material::IsDoubleSided) exempts genuinely two-sided meshes.\n\nDEFAULT OFF (WF_CULL=1 opts in). An A/B sweep across 7 shipped levels showed the\nmechanism is correct (qbert/snowgoons/filesys/moon pixel-clean) but several\nprocedural mesh generators are wound INWARD — add_solid_box / make_box_mesh /\ndisk_geo: per CalculateNormal=(v2-v0)x(v1-v0) (face.hpi:35) the box top face\n(4,5,6,7) normal is -Z. Enabling globally culls those visible tops (SMB ground\nvanished; treemap/filelight tops dimmed), and reversing winding entangles with\none-sided lighting + the FACE_COLOR override, so it isn't a clean flip. Shipped\ngated off; rewinding shipped meshes to consistent normals + flipping the default\non is a separate effort (TODO). The planetarium dome is the first WF_CULL=1\nconsumer.\n\nTouches: backend_modern.cc + backend_metal.mm (the cull + WF_CULL gate),\nrenderer_backend.hp + renderer_stub.cc (cullExempt param), material.hp\n(IsDoubleSided), the 8 rend{f,g}{t,c}{l,p}.cc (pass the flag), rendmatt.cc\n(cull-exempt). Docs: level-design-troubleshooting.md + level-building.md\n(winding rule, inside-out box, WF_CULL toggle).\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
-->
