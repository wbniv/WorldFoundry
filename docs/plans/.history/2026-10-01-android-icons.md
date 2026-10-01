| Date | Change |
|------|--------|
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/5d8ea10a) | Icons: snowgoon third arm angled up from the chest centre; aquarium stalk water fill fixed and the fish raised in the icon |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/735bc2b8) | Snowgoon: the third arm on the centre of the upper chest, between the two raised arms; source research recorded |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/4a2dfa26) | Icons: three snowgoon arms from the upper torso (third centred), aquarium without the brown stalk, condo icon half and half at the front; plan and mockups updated |
| [2026-10-01](https://github.com/wbniv/WorldFoundry/commit/019a88ed) | New launcher icons and TV banners for the three Android games, one layout, with the logo as a separate script |

<!--history-meta v1
5d8ea10a	author	Will Norris
5d8ea10a	added	3
5d8ea10a	deleted	3
5d8ea10a	files	1
5d8ea10a	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
735bc2b8	author	Will Norris
735bc2b8	added	1
735bc2b8	deleted	1
735bc2b8	files	1
735bc2b8	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
4a2dfa26	author	Will Norris
4a2dfa26	added	7
4a2dfa26	deleted	6
4a2dfa26	files	1
4a2dfa26	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
019a88ed	author	Will Norris
019a88ed	added	134
019a88ed	deleted	0
019a88ed	files	1
019a88ed	body	Layout for every game on mobile and Chromecast: the game's art fills the icon, the World Foundry logo (the website\nfavicon) sits bottom-right. scripts/add-wf-logo.py stamps the logo onto ANY existing icon (in place, -o, many files,\n--safe-inset for adaptive foregrounds, --circle for round icons); scripts/gen-android-icons.py prepares each game's art\nand calls it, replacing the two per-flavor generators (now stubs that point to it).\n\nArt: snowgoons gets an original menacing three-armed snowman (Blender, scripts/render-snowgoon.py; the repo has no\nsnowman mesh); the aquarium icon is just the fish and the anemone (rock and sand removed from camshot B by\nscripts/derock-aquarium-frame.py, an edit of the capture); the condo is pulled back and lowered as far as the game's\ncamera controls allow (scripts/capture-condo-pullback.py, driven through the debug bridge). The snowgoons flavor now\noverrides main's icons with src/snowgoons/res.\n\nPlan with rendered mockups: docs/plans/2026-10-01-android-icons.md. Not yet built into an APK or seen on a device.\nAdds two TODO items (split the multi-level cd.iff into apps; a menu selector for it).\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01NNPhRbrqjqMDkScPvTE9yC
-->
