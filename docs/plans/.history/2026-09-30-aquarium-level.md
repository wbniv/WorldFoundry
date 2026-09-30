| Date | Change |
|------|--------|
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/1aa8e779) | Run aquarium Phase 0 translucency spike: pane is opaque, fall back to Plan B |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/f964a400) | Plan aquarium level (55 gal acrylic, clownfish, anemone) and correct condo alpha note |

<!--history-meta v1
1aa8e779	author	Will Norris
1aa8e779	added	188
1aa8e779	deleted	4
1aa8e779	files	1
1aa8e779	body	The test card (wflevels/aquarium_spike/) builds and the bit-15 pane texels reach the\nGPU with alpha 128, but backend_modern.cc's fragment shader writes alpha 1.0 for every\nfragment (since 23e632ec), so the pane renders opaque and hides the far fish in either\nactor order. Hot-swapping a shader that keeps texture alpha over the debug bridge\n(no engine file touched) shows the rest of the chain works: with the pane created last\nin actor order the blend is exact (max |delta| 1 per channel); created earlier, anything\nbehind it and drawn after it vanishes, because depth writes are always on.\n\nRecords steps 1-4 and the verdict in the plan, corrects the condo glass note, and\ncorrects level-building.md: bungee cameras aim at Target - Follow + Track Object.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
f964a400	author	Will Norris
f964a400	added	243
f964a400	deleted	0
f964a400	files	1
f964a400	body	Plan + three 1440x900 mockups (tank dimensions, gameplay states, pane\nfallbacks / Phase 0 test card). Nothing is built; Phase 0 is a runtime spike\non translucent draw order.\n\nAlso corrects condo_639_640.md: "MATL has no alpha" is true for flat-colour\nmaterials, but textured materials support ~50% translucency via texel bit 15\n(pixelmap.cc:190 -> material.cc:124 -> GL_BLEND). Read from code, not yet run.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
-->
