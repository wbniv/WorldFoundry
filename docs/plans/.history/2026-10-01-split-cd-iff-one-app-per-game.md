| Date | Change |
|------|--------|
| [2026-10-02](https://github.com/wbniv/WorldFoundry/commit/2ad47077) | Stale Google TV tiles: the launcher's own cache, fixed by clearing its data (reboot and reinstall did not) |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/6475a96c) | Plan: the device rerun with the final APKs, and the Snowgoons label and icon |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/ccede076) | The snowgoons app is called Snowgoons |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/c19865bb) | Plan: icons for every app, the snowgoons level banner, and the verification results |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/fad9efcf) | Plan: split the multi-level cd.iff into one Android app per game (smb, snowgoons, qbert) |

<!--history-meta v1
2ad47077	author	Will Norris
2ad47077	added	13
2ad47077	deleted	1
2ad47077	files	1
2ad47077	body	Plan step 9 and porting-status record the result with a screenshot of the Apps row after\n`pm clear com.google.android.apps.tv.launcherx`; the TODO Verify bullet for it is removed.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
6475a96c	author	Will Norris
6475a96c	added	47
6475a96c	deleted	5
6475a96c	files	1
6475a96c	body	Verification 9: smb, qbert and snowgoons release APKs built from ccede076 PASS\non the Chromecast HD (alive, no crash lines, EGL up, 59.9 fps); smb now opens on\nthe world-select menu (a40da0de). The launcher shows round icons, not banners;\nthe snowgoons tile still shows the cached old "World Foundry" name and mark\nalthough the installed APK is byte-identical to the build (label Snowgoons,\nsnowman icons). Verification 11: the label and icon tests and the APK check.\nThe TV was left on the Google TV home screen.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
ccede076	author	Will Norris
ccede076	added	3
ccede076	deleted	3
ccede076	files	1
ccede076	body	Asked by the user. android/app/src/snowgoons/res/values/strings.xml overrides\nmain's "World Foundry" (log viewer: "Snowgoons Log"); the id stays\norg.worldfoundry.wf_game so installs upgrade in place, and the other labels are\nunchanged. Its launcher icons already override main's in every density and\nform (the snowman); a new test pins that, another pins every app's label.\nREADME, the split plan (Icons table, mockups) and a note in the icons plan\nfollow.\nPlan: docs/plans/2026-10-01-split-cd-iff-one-app-per-game.md\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
c19865bb	author	Will Norris
c19865bb	added	145
c19865bb	deleted	6
c19865bb	files	1
c19865bb	body	An Icons section with each app's adaptive and legacy icon and TV banner, read\nfrom the real res files, with where each art comes from and what to replace\n(names only; no placeholder images). The snowgoons banner row now cites the\nlevel screenshot. Verification 1-8 and 10 PASS (step 5's one failure is the\naquarium debug APK against another session's newer aquarium-cd.iff); step 9\nPASS for the first device run, the rerun with the final APKs PENDING: the user\nasked not to use the Chromecast while another agent records a video.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
fad9efcf	author	Will Norris
fad9efcf	added	189
fad9efcf	deleted	0
fad9efcf	files	1
fad9efcf	body	The decisions, the audit of every LEVEL_TO_RUN write (every per-game bundle is\nself-consistent with no level edit), the bundles, flavors, art and plumbing, and\ntwo mockups rendered from the real generated resources.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DxMP4jUNjCjDz8E9DWzXcM
-->
