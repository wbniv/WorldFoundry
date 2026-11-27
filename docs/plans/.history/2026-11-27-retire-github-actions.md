| Date | Change |
|------|--------|
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/6bc5cdc41) | todo, plan: GitHub Actions retirement phases 1-2 done |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/57d753965) | Local CI: aquarium-check and blender-addon steps replace two GitHub workflows |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/cc22ca5a0) | Codemagic budget monitor: systemd user timer replaces the GitHub workflow |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/9569bcb77) | plan, todo: retire GitHub Actions approved (Will: "d1-d5: ok") |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/0ecc10d09) | plan: retire the remaining GitHub Actions workflows (local CI steps, Codemagic timer, local apt publish) |

<!--history-meta v1
6bc5cdc41	author	Will Norris
6bc5cdc41	added	1
6bc5cdc41	deleted	1
6bc5cdc41	files	1
6bc5cdc41	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqNTUqFTmHmqAtzA9X1
57d753965	author	Will Norris
57d753965	added	31
57d753965	deleted	0
57d753965	files	1
57d753965	body	GitHub Actions is retired (Will, 2026-11-27). Both steps run in the Blender\nimage and only when their inputs changed (the range since the last polled\ncommit, else the commit against its parent); otherwise SKIP (not touched),\nwhich is not a failure. --only S1,S2 runs a subset (no build headroom needed\nwithout build). task blender-matrix runs the other Blender versions on demand\n(D2). The Blender image gains python3-pytest and maturin 1.11.5.\n\nFirst runs found two real regressions the dead GitHub checks missed: stale\nAquarium outputs (fixed in d2320285d) and a stale qbert_practice golden since\n750a8db4a (TODO). Plan 2026-11-27-retire-github-actions Phase 1, steps 1-2.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqNTUqFTmHmqAtzA9X1
cc22ca5a0	author	Will Norris
cc22ca5a0	added	18
cc22ca5a0	deleted	0
cc22ca5a0	files	1
cc22ca5a0	body	GitHub Actions is retired (Will, 2026-11-27). codemagic-budget.timer runs on\nthe workflow's UTC schedule (hourly 06-22, plus 00:00); codemagic-budget-run.sh\nloads the token and app id from ~/.config/codemagic and the PagerDuty key from\nSSM. State moves to ~/.local/state/wf/codemagic-budget.json (old repo-root file\ncopied once). A desktop notification fires beside each PagerDuty alert (D3).\nPlan 2026-11-27-retire-github-actions Phase 2; verification step 3 PASS.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqNTUqFTmHmqAtzA9X1
9569bcb77	author	Will Norris
9569bcb77	added	1
9569bcb77	deleted	1
9569bcb77	files	1
9569bcb77	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqNTUqFTmHmqAtzA9X1
0ecc10d09	author	Will Norris
0ecc10d09	added	124
0ecc10d09	deleted	0
0ecc10d09	files	1
0ecc10d09	body	Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqNTUqFTmHmqAtzA9X1
-->
