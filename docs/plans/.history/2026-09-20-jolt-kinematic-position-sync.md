| Date | Change |
|------|--------|
| [2026-09-20](https://github.com/wbniv/WorldFoundry/commit/b3bafe66) | docs(plans): plan to sync scripted position-mailbox writes into Jolt |

<!--history-meta v1
b3bafe66	author	Will Norris
b3bafe66	added	120
b3bafe66	deleted	0
b3bafe66	files	1
b3bafe66	body	Real sliding motion for the condo's telescoping doors needs an actor's\nJolt collision to move with its mesh. Traced why it doesn't: the\nX_POS/Y_POS/Z_POS mailbox-write handlers (actor.cc:1458-1503) only\npush into Jolt for character-controlled actors, not plain rigid\nbodies - a gap already flagged, unfixed, in the 2026-05-11 mailbox/Jolt\nbypass plan.\n\nResearch confirms every actor body is already created kinematic by\ndefault and a JoltBodySetPosition helper exists with zero callers -\nthis is a narrow, additive fix (new branch in three handlers + a\nMoveKinematic wrapper), not the three-surface Platform::initPath()\nsystem that was the other candidate.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_011WmfFdmKRi46BtcEyu8pkT
-->
