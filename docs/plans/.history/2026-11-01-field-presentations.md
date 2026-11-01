| Date | Change |
|------|--------|
| [2026-11-01](https://github.com/wbniv/WorldFoundry/commit/ab292c05) | Field presentations: APK on a refreshed runtime; Release desktop build task |
| [2026-11-01](https://github.com/wbniv/WorldFoundry/commit/ea44a512) | Field presentations: a distinct control for every settings case |

<!--history-meta v1
ab292c05	author	Will Norris
ab292c05	added	17
ab292c05	deleted	2
ab292c05	files	1
ab292c05	body	- Plan step 5: baseline-5b47e27b5516e543.apk (SHA-256 5b47e27b…7f47) on the\n  condo diagnostic runtime 205b4ede…f617, built from a clean worktree at\n  0ff49194; both ABIs carry the new controls.\n- Taskfile: build-desktop-release (CMake + Ninja in build-docker/jelly-engine)\n  as baseline:check's dependency. task build's debug binary cannot run the\n  baseline: it stops on the teapot's polygon assertion and has no\n  source-tree UI font fallback.\n- TODO: the item moves to verify; the cast1 capture remains.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqSWpcGmU9ZTVy7HDyx
ea44a512	author	Will Norris
ea44a512	added	210
ea44a512	deleted	0
ea44a512	files	1
ea44a512	body	The eleven "proposed" Field types cases now draw their own control on the\nTV form and on the phone touch form (docs/plans/2026-11-01-field-presentations.md):\n\n- engine/runtime_property_presentation.hpp maps a field's compiled kind,\n  showAs, rule and options to its control, and holds the row-key table\n  wfprops::keys(). Choice rows follow Will's option 6: up to\n  kCycleChoicesMax (4) options cycle with Left / Right and leave to the\n  rail from the first option; more only open the list; A opens it either way.\n- TV: choice boxes with a down-arrow and an open list (numbered ids,\n  wrapped long options), two-segment toggle, pill switch, mailbox bounds,\n  path with a file mark. Rows draw no text under an open list.\n- Touch: numbered and wrapping choice sheets, checkbox and switch drawn\n  differently, bounds and path marks; segment taps now choose the segment\n  (the row target used to swallow them).\n- The OAD normalizer makes an integer TOGGLE without choices a Bool; the\n  Field types catalog, level and main cd.iff are rebuilt.\n- Engine validation refuses a FILENAME value that is not a relative path.\n- Tests: each of the 27 cases asserts its control (engine, TV render, touch\n  fixture); key tests follow the rule table for 2, 4, 5 and 12 options;\n  every committed catalog still loads.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqSWpcGmU9ZTVy7HDyx
-->
