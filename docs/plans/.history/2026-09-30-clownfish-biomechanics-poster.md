| Date | Change |
|------|--------|
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/2f0f0efb) | Poster: drop off-page header icon that left a sliver at the PDF edge; TODO done |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/810cfe93) | Clownfish biomechanics poster (A3): data sheet, generator, PDF/PNG, tests, Taskfile entry |
| [2026-09-30](https://github.com/wbniv/WorldFoundry/commit/f54741bc) | Plan clownfish biomechanics poster (A3) with computed-diagram mockups |

<!--history-meta v1
2f0f0efb	author	Will Norris
2f0f0efb	added	1
2f0f0efb	deleted	1
2f0f0efb	files	1
2f0f0efb	body	The hero fish icon after the header note overflowed the 277 mm header and\nleft a 0.7 mm sliver of its nose at the right edge of the A3 PDF. It was\nnever visible, so remove it and guard the page edges with a test (the outer\n5 mm of the rendered PDF must be blank; it flags the previous PDF).\n\nRecord the review in the plan and move the clownfish poster to Done. Still\nopen: printing it (step 10), and URLs for sources S2 and S9.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
810cfe93	author	Will Norris
810cfe93	added	227
810cfe93	deleted	37
810cfe93	files	1
810cfe93	body	Phases A-D of docs/plans/2026-09-30-clownfish-biomechanics-poster.md. Every 'ours'\nnumber is read from aquarium_constants.py / clownfish.py at build time; each chip\nmust agree with the label in the constant's comment (tested, with a doctored-chip\nnegative test). Seven computed diagrams + parameter table + sources. The plan's\nstale pre-Phase 4 numbers and four over-generous 'verified' labels are corrected;\nverification steps 1-9 recorded, step 10 (print) unverified.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
f54741bc	author	Will Norris
f54741bc	added	135
f54741bc	deleted	0
f54741bc	files	1
f54741bc	body	Plan + two mockups (whole-page layout, diagrams A/B/C at print scale) and the\ngenerator that computes their curves. Every number carries a verified /\nunverified / ours status; sources were opened and three earlier mis-attributions\n(Rohr & Fish is cetaceans; Wu, Yang & Zeng 2007; burst duration) are corrected.\nNothing is built; build waits for aquarium Phase 4 so the poster reads its\nconstants from clownfish.py.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0148itHvh6GL5Qc7uwSjFC2n
-->
