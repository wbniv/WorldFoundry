| Date | Change |
|------|--------|
| [2026-06-14](https://github.com/wbniv/WorldFoundry/commit/033002cc) | docs(todo): migrate TODO.md to the four-bucket Open/Watch/Parked/Done model |

<!--history-meta v1
033002cc	author	Will Norris
033002cc	added	150
033002cc	deleted	0
033002cc	files	1
033002cc	body	Swept the legacy topical-section TODO into the model the global /todo skill\nenforces. Done items collapsed to dated one-liners (- [x] YYYY-MM-DD — [slug] …),\nnewest first; open items kept full detail under ## Open ### subsections;\ndeferred/trigger work → ## Parked; verify/monitor → ## Watch.\n\nAudit (6 parallel verification agents) caught ~18 items marked open that had\nactually shipped — now in ## Done: PILOT (Phases 0-4), spawn-template syscall,\nUV uint8→uint16 widening, moon Jolt vehicle physics, SMB W1-4 castle, level\npipeline Phase D & E, macOS headless+.app, iOS Phase 2C, pure-Python asset\nprovider, Blender Run operator, deterministic mesh export + camera null-guard,\nPATH/CHAN keyframes, .001 mesh-name dedup, setup-wf-workspace.sh, .ht codegen,\ntask apt source. Also marks task apt fix done + reframes the y-crdt workaround\n(submodule already at v0.26.0 → cleanup now actionable).\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
-->
