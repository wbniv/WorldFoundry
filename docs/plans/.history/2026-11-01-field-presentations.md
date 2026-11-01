| Date | Change |
|------|--------|
| [2026-11-01](https://github.com/wbniv/WorldFoundry/commit/ea44a512) | Field presentations: a distinct control for every settings case |

<!--history-meta v1
ea44a512	author	Will Norris
ea44a512	added	210
ea44a512	deleted	0
ea44a512	files	1
ea44a512	body	The eleven "proposed" Field types cases now draw their own control on the\nTV form and on the phone touch form (docs/plans/2026-11-01-field-presentations.md):\n\n- engine/runtime_property_presentation.hpp maps a field's compiled kind,\n  showAs, rule and options to its control, and holds the row-key table\n  wfprops::keys(). Choice rows follow Will's option 6: up to\n  kCycleChoicesMax (4) options cycle with Left / Right and leave to the\n  rail from the first option; more only open the list; A opens it either way.\n- TV: choice boxes with a down-arrow and an open list (numbered ids,\n  wrapped long options), two-segment toggle, pill switch, mailbox bounds,\n  path with a file mark. Rows draw no text under an open list.\n- Touch: numbered and wrapping choice sheets, checkbox and switch drawn\n  differently, bounds and path marks; segment taps now choose the segment\n  (the row target used to swallow them).\n- The OAD normalizer makes an integer TOGGLE without choices a Bool; the\n  Field types catalog, level and main cd.iff are rebuilt.\n- Engine validation refuses a FILENAME value that is not a relative path.\n- Tests: each of the 27 cases asserts its control (engine, TV render, touch\n  fixture); key tests follow the rule table for 2, 4, 5 and 12 options;\n  every committed catalog still loads.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01YEenqSWpcGmU9ZTVy7HDyx
-->
