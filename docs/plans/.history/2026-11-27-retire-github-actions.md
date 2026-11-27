| Date | Change |
|------|--------|
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/cc22ca5a0) | Codemagic budget monitor: systemd user timer replaces the GitHub workflow |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/9569bcb77) | plan, todo: retire GitHub Actions approved (Will: "d1-d5: ok") |
| [2026-11-27](https://github.com/wbniv/WorldFoundry/commit/0ecc10d09) | plan: retire the remaining GitHub Actions workflows (local CI steps, Codemagic timer, local apt publish) |

<!--history-meta v1
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
