| Date | Change |
|------|--------|
| [2026-09-20](https://github.com/wbniv/WorldFoundry/commit/2b1c8c86) | docs(plans): 639-project-rm north wall is telescoping doors (design plan) |

<!--history-meta v1
2b1c8c86	author	Will Norris
2b1c8c86	added	162
2b1c8c86	deleted	0
2b1c8c86	files	1
2b1c8c86	body	The source survey modeled this as a partial window (639-window-1, 4.75m\nof the 6m wall, z 0.9-2.3 only) when the real unit has 3 floor-to-ceiling\nglass panels that gather at the east end (1 fixed, 2 movable), per user\ncorrection against real building knowledge. Verified room/wall geometry\nagainst the source .blend directly.\n\nNo door/mover actor exists in the engine (Platform.initPath() is a stub,\nno Forth syscall for runtime actor translation - see TODO.md:131). Plan\nrecommends the existing Visibility-Mailbox two-state swap + ActBox\ntrigger pattern over true sliding animation, which would be a\nfirst-of-its-kind pattern here with a documented Jolt-sync risk.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_011WmfFdmKRi46BtcEyu8pkT
-->
