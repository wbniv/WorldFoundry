| Date | Change |
|------|--------|
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/95fab4ad8) | Combined host: restore the menu row tap, the story-card layout and the gamepad stick |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/4bf3e71aa) | Combined host: the engine's touch settings form, driven on the game thread before the controller |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/db1a8c3f8) | Touch controls plan: Aquarium verified on the Pixel; TV, Clocks and Dream pending |
| [2026-11-22](https://github.com/wbniv/WorldFoundry/commit/033595644) | An on-screen controller for the combined Aquarium and Clocks apps on a phone |

<!--history-meta v1
95fab4ad8	author	Will Norris
95fab4ad8	added	4
95fab4ad8	deleted	4
95fab4ad8	files	1
95fab4ad8	body	Will, 2026-11-22: "why wouldn't i want all of it? didn't we develop those things for a reason?"\nAll three were in the standalone NativeActivity host. task test-touch-bridge: 42 checks.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
4bf3e71aa	author	Will Norris
4bf3e71aa	added	16
4bf3e71aa	deleted	0
4bf3e71aa	files	1
4bf3e71aa	body	The standalone app was a NativeActivity host that fed touches to propertyui (an entry button at the top right,\nthen the form). The screensaver host never did, so neither app could open or drive level settings by touch.\nTouches now queue on the UI thread and the per-frame hook gives each to the form first, then the controller;\na touch the form takes releases the controller's buttons. The plan lists what else the standalone host did.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
db1a8c3f8	author	Will Norris
db1a8c3f8	added	29
db1a8c3f8	deleted	6
db1a8c3f8	files	1
db1a8c3f8	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
033595644	author	Will Norris
033595644	added	51
033595644	deleted	0
033595644	files	1
033595644	body	The shared host drew none, so on the Pixel the menu could not be moved and the Clocks chooser and its hold-A\nsettings form could not be used. TouchBridge turns touches into the remote's joystick bits through the key\nlatch; the engine draws the controller through WFAndroidTouchLayout. Phones only (a touchscreen, no TV), never in\nthe Dream. task test-touch-bridge: 28 checks. Not yet checked on a device.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqQdpzaEWB9yHz5H9v3
-->
