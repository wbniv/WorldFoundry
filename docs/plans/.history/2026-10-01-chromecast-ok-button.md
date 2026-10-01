| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/773f860b) | Chromecast OK button: confirmed on the remote in snowgoons; log each key and its mask |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/15452b11) | OK-button plan: the condo release builds for both ABIs against ~/android-sdk-local |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/44319b44) | Chromecast remote: the OK button (DPAD_CENTER) is now button 1 / A |

<!--history-meta v1
773f860b	author	Will Norris
773f860b	added	11
773f860b	deleted	11
773f860b	files	1
773f860b	body	Adds one logcat line per key edge in HandleInputEvent (code, action, mask, 'unmapped, dropped' when\nMapKeyCode returns 0). Plan: step 4 PASS by hand; step 3's 'the condo hops' expectation was\nunverified and wrong, so it is rewritten (A has a visible effect in snowgoons, not necessarily in the condo).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
15452b11	author	Will Norris
15452b11	added	17
15452b11	deleted	3
15452b11	files	1
15452b11	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
44319b44	author	Will Norris
44319b44	added	79
44319b44	deleted	0
44319b44	files	1
44319b44	body	MapKeyCode had no AKEYCODE_DPAD_CENTER, which is what the Chromecast with\nGoogle TV remote's OK sends, so the key was dropped. Map it to EJ_BUTTONF_A.\nAdds a source test of the key map (fails without the line), and an OK press\nto android-device-run.sh --poke. Plan: docs/plans/2026-10-01-chromecast-ok-button.md\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
-->
