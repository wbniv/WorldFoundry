| Date | Change |
|------|--------|
| [2026-05-25](https://github.com/wbniv/WorldFoundry/commit/84418c7c) | docs(plans): Waves B–E of status sweep — stamp/accurate-ize the rest |
| [2026-05-12](https://github.com/wbniv/WorldFoundry/commit/64d64c62) | ci(codemagic): stop-bleed — disable ios-simulator-debug auto-trigger |

<!--history-meta v1
84418c7c	author	Will Norris
84418c7c	added	2
84418c7c	deleted	0
84418c7c	files	1
84418c7c	body	Every plan now carries an accurate Status (0 remaining with none). Breakdown:\n- Wave E: 28 no-status plans stamped (mostly DONE — the verify agent badly\n  under-reported completion; spot-checks corrected ~10 false-OPENs incl.\n  voice/video calling, android phase 2, blender test-matrix, debug-print-actors,\n  per-level palette, camera pullback, mm-2 level, wf-workspace-setup).\n- Wave B: 16 genuine backlog plans given accurate PARTIAL/OPEN text (the real\n  remaining work — video capture, steam SDK, lua-on, neural-forth examples,\n  asset-provider, codemagic budget, fetch-paper, …).\n- Wave C: apt-worldfoundry-org marked DONE — apt.worldfoundry.org serves HTTP 200\n  (external infra; no in-repo artifact by design).\n- Wave D: the 4 docs/qbert/plans duplicates marked DONE (features shipped).\n- runtime-long-audit → DONE (F1–F6 + pass-2; only F7 left); walker-rom-grounded\n  → ABANDONED (low-ROI, 89761d17).\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
64d64c62	author	Will Norris
64d64c62	added	195
64d64c62	deleted	0
64d64c62	files	1
64d64c62	body	490/500 Mac-build minutes burned by day 12 of May. Empty the events list\nfor ios-simulator-debug so pushes don't kick off Mac builds. Manual builds\nfrom the Codemagic dashboard still work. Caching + monitor + restoration\nfollow in docs/plans/2026-05-12-codemagic-budget-monitor.md.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
-->
