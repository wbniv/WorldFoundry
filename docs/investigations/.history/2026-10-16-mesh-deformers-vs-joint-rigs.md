| Date | Change |
|------|--------|
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/2dbebee6) | Compare mesh deformers with joint rigs for animated meshes |

<!--history-meta v1
2dbebee6	author	Will Norris
2dbebee6	added	141
2dbebee6	deleted	0
2dbebee6	files	1
2dbebee6	body	Investigation for Will: the DFRM generic deformer being built in the\nseahorse Phase 1 versus a skeleton with skinning, clips, IK and sockets.\nCovers the shared pose stage, per-animal fit, Chromecast costs (Mali-G31,\nGLES 3.2; CPU streaming dominates; GPU skinning obstacles), reuse of the\ncompiled-in but unused Jolt skeleton module, and a recommendation: keep\nPhase 1, run a joint-rig spike before Deformer phase 2.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
-->
