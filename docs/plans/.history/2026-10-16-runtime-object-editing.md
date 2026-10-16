| Date | Change |
|------|--------|
| [2026-10-16](https://github.com/wbniv/WorldFoundry/commit/7ef36fbb) | Plan runtime object editing on OAS/OAD to replace RP02 |

<!--history-meta v1
7ef36fbb	author	Will Norris
7ef36fbb	added	148
7ef36fbb	deleted	0
7ef36fbb	files	1
7ef36fbb	body	Any object whose type declares a SHOW_AS_LIVE field becomes editable on\nthe TV/phone. Export resolves the list into LevelObj (no runtime scans),\nlabels are automatic with an optional Editor Label override, the form is\nbuilt from the type's shipped .oad, and edits go to a per-object writable\noverlay with a change hook and a test per live field. Settings holders\nbecome standard OAS types (PlantedTankSettings inherits Settings through\n@include); RP01, settings-bindings.json, the engine-compiled catalog and\nplanted::State retire. Decisions M1-M8 from Will (2026-10-16); engine\nscope still to confirm. The RP02 TODO line is replaced by this item.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01T3gB59hNsFhWnCTTKHc1yk
-->
