| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/44319b44) | Chromecast remote: the OK button (DPAD_CENTER) is now button 1 / A |

<!--history-meta v1
44319b44	author	Will Norris
44319b44	added	79
44319b44	deleted	0
44319b44	files	1
44319b44	body	MapKeyCode had no AKEYCODE_DPAD_CENTER, which is what the Chromecast with\nGoogle TV remote's OK sends, so the key was dropped. Map it to EJ_BUTTONF_A.\nAdds a source test of the key map (fails without the line), and an OK press\nto android-device-run.sh --poke. Plan: docs/plans/2026-10-01-chromecast-ok-button.md\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
-->
