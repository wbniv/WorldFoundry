| Date | Change |
|------|--------|
| [2026-11-11](https://github.com/wbniv/WorldFoundry/commit/be05fad1) | Balcony solar research: turning the inserts 6 degrees instead of tilting |
| [2026-11-11](https://github.com/wbniv/WorldFoundry/commit/e51a74d5) | Balcony solar: the ledge runs inward, so no shade; test a tilted 10 cm frame |
| [2026-11-11](https://github.com/wbniv/WorldFoundry/commit/c24de9c3) | Balcony screen frame: v3 shop sheet; split solar research and v1/v2 archive |

<!--history-meta v1
be05fad1	author	Will Norris
be05fad1	added	3
be05fad1	deleted	1
be05fad1	files	1
be05fad1	body	PVGIS: +2.5 % facing 6 degrees toward the south, -3.2 % toward the north,\nbefore sawtooth self-shading and the loss of sealed joints.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
e51a74d5	author	Will Norris
e51a74d5	added	51
e51a74d5	deleted	27
e51a74d5	files	1
e51a74d5	body	Will (2026-11-11): the ledge's outer edge is flush with the outside wall\nand it runs 35 cm inward, so panels at the frame's outer plane are never\nshaded. Removes the ledge-shadow model and shadow bands, recomputes yield\n(option B 400 W = 268 kWh a year), value and payback with the 2026-11-11\nLazada checkout price, and answers the shade plan's open question 4.\n\nAdds the tilt variation: a 10 cm frame lets the solar inserts lean 3.8\ndegrees; PVGIS hourly planes plus the soffit's shadow give +2 % a year\n(+6 kWh, 20-29 THB), with a sun study at five moments. Verdict: not\nworth a deeper frame.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
c24de9c3	author	Will Norris
c24de9c3	added	82
c24de9c3	deleted	0
c24de9c3	files	1
c24de9c3	body	v3 shop sheet (v2 untouched) adds a continuous latch channel along the\nhead and sill so panels of any width lock in, and a third panel set of\nfour solar inserts, with a drawn page: the four inserts and one insert\ndimensioned, the channel with both latch spacings, and a sill section.\nBuilt by build_spec_v3.py from v2 plus build_solar_sheet_svgs.py.\n\nThe plan keeps a solar summary (option B, layout diagram, payback chart)\nand moves the research to 2026-11-11-condo-639-balcony-solar-research.md;\nthe v1 and v2 designs and drawings move to\n2026-11-11-condo-639-balcony-screen-frame-archive.md. The overhang idea\nis dropped: every panel size costs about the same per square metre.\nOpen question 7 is answered by the latch channel.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqRTjYzU5APTKovfevg
-->
