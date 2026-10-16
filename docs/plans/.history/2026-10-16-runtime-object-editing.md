| Date | Change |
|------|--------|
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/3801e13d) | Runtime object editing plan: fix flowchart and decisions table |
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/928ee745) | Runtime object editing: no 'live' in the UI; padlock on read-only fields |
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/7ef36fbb) | Plan runtime object editing on OAS/OAD to replace RP02 |

<!--history-meta v1
3801e13d	author	Will Norris
3801e13d	added	1
3801e13d	deleted	2
3801e13d	files	1
3801e13d	body	The flowchart fell back to a code block: Mermaid 11 parses '@' in an\nunquoted node label as node metadata (renderer warned 'Parse error ...\ngot LINK_ID'); quote that label. A blank line split the decisions table,\nturning M6 into a bold header row; join it back.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
928ee745	author	Will Norris
928ee745	added	5
928ee745	deleted	5
928ee745	files	1
928ee745	body	Will, 2026-10-16: never print "live" on edit fields. Editable fields\ncarry no marker; read-only fields are dimmed with a padlock icon. The\nmockup drops the in-frame annotation tags and draws the padlock as an\ninline SVG so it reads at TV distance.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
7ef36fbb	author	Will Norris
7ef36fbb	added	148
7ef36fbb	deleted	0
7ef36fbb	files	1
7ef36fbb	body	Any object whose type declares a SHOW_AS_LIVE field becomes editable on\nthe TV/phone. Export resolves the list into LevelObj (no runtime scans),\nlabels are automatic with an optional Editor Label override, the form is\nbuilt from the type's shipped .oad, and edits go to a per-object writable\noverlay with a change hook and a test per live field. Settings holders\nbecome standard OAS types (PlantedTankSettings inherits Settings through\n@include); RP01, settings-bindings.json, the engine-compiled catalog and\nplanted::State retire. Decisions M1-M8 from Will (2026-10-16); engine\nscope still to confirm. The RP02 TODO line is replaced by this item.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
-->
