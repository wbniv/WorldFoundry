| Date | Change |
|------|--------|
| [2026-09-20](https://github.com/wbniv/WorldFoundry/commit/2e4d894ad) | feat(ci): Codemagic Mac-minute budget monitor on GitHub Actions |
| [2026-05-25](https://github.com/wbniv/WorldFoundry/commit/84418c7c2) | docs(plans): Waves B–E of status sweep — stamp/accurate-ize the rest |
| [2026-05-12](https://github.com/wbniv/WorldFoundry/commit/64d64c629) | ci(codemagic): stop-bleed — disable ios-simulator-debug auto-trigger |

<!--history-meta v1
2e4d894ad	author	Will Norris
2e4d894ad	added	14
2e4d894ad	deleted	3
2e4d894ad	files	1
2e4d894ad	body	Codemagic's 500 free Mac-min/month quota is dashboard-only — there is no\n/usage REST endpoint — so there has been no quota visibility at all since\nthe May 2026 burn. The Metal renderer work opens an iteration loop\nagainst that pool, and every option in its build-strategy table is being\nchosen blind without this. It runs on ubuntu-latest, so it costs zero\nMac-minutes, which is why it can run hourly.\n\nImplements Implementation steps 6 + 7 of\ndocs/plans/2026-05-12-codemagic-budget-monitor.md: sum the current UTC\nmonth's mac_* instance-minutes from GET /builds, and fire a PagerDuty\nEvents API v2 alert the first time each of 50/80/95% is crossed, with\nthe already-fired set round-tripped through actions/cache so alerts are\nat-most-once per month and reset on rollover.\n\nFour places the plan left undetermined, decided here and worth knowing:\n\n- The plan's cache key is constant within a month, and actions/cache\n  cannot overwrite an existing key — the fired list would have been\n  frozen at the first run's value. Key is now suffixed with the run id\n  and recovered via restore-keys.\n- /builds is paged backwards and filtered client-side on startedAt, so\n  the unverified buildAfter parameter name cannot silently skew the sum.\n- Instance type and duration are read through every field spelling the\n  API has used (instanceType / instance_type, nested under config or\n  buildSettings; buildDuration else finishedAt - startedAt), and\n  millisecond timestamps are stripped before fromdateiso8601, which\n  refuses them.\n- A missing PagerDuty routing key logs the alert instead of failing, so\n  the monitor is useful before the PD service exists; a missing API\n  token or app id still fails loudly.\n\nExercised end-to-end against a local stub API: accounting (mac vs linux,\nin-month vs prior-month, both duration spellings), at-most-once firing,\nand month rollover all behave. Still inert in CI until the one-time\nmanual steps 4 + 5 provide secrets.CODEMAGIC_API_TOKEN,\nsecrets.PAGERDUTY_ROUTING_KEY and vars.WF_CODEMAGIC_APP_ID.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_015ksFy3ZSSz2XMdto3jVA9v
84418c7c2	author	Will Norris
84418c7c2	added	2
84418c7c2	deleted	0
84418c7c2	files	1
84418c7c2	body	Every plan now carries an accurate Status (0 remaining with none). Breakdown:\n- Wave E: 28 no-status plans stamped (mostly DONE — the verify agent badly\n  under-reported completion; spot-checks corrected ~10 false-OPENs incl.\n  voice/video calling, android phase 2, blender test-matrix, debug-print-actors,\n  per-level palette, camera pullback, mm-2 level, wf-workspace-setup).\n- Wave B: 16 genuine backlog plans given accurate PARTIAL/OPEN text (the real\n  remaining work — video capture, steam SDK, lua-on, neural-forth examples,\n  asset-provider, codemagic budget, fetch-paper, …).\n- Wave C: apt-worldfoundry-org marked DONE — apt.worldfoundry.org serves HTTP 200\n  (external infra; no in-repo artifact by design).\n- Wave D: the 4 docs/qbert/plans duplicates marked DONE (features shipped).\n- runtime-long-audit → DONE (F1–F6 + pass-2; only F7 left); walker-rom-grounded\n  → ABANDONED (low-ROI, 89761d17).\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
64d64c629	author	Will Norris
64d64c629	added	195
64d64c629	deleted	0
64d64c629	files	1
64d64c629	body	490/500 Mac-build minutes burned by day 12 of May. Empty the events list\nfor ios-simulator-debug so pushes don't kick off Mac builds. Manual builds\nfrom the Codemagic dashboard still work. Caching + monitor + restoration\nfollow in docs/plans/2026-05-12-codemagic-budget-monitor.md.\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
-->
