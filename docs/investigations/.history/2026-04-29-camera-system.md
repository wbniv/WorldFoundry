| Date | Change |
|------|--------|
| [2026-04-29](https://github.com/wbniv/WorldFoundry/commit/f9579c09) | camera-system: add real snowgoons Director script + fix fi/then note |
| [2026-04-29](https://github.com/wbniv/WorldFoundry/commit/a9325421) | camera-system: add Forth Director script examples |
| [2026-04-29](https://github.com/wbniv/WorldFoundry/commit/bc73a491) | camera-system: correct Director description — scripting, not camera logic |
| [2026-04-29](https://github.com/wbniv/WorldFoundry/commit/80ee5168) | docs: camera system investigation — full reference doc |

<!--history-meta v1
f9579c09	author	Will Norris
f9579c09	added	32
f9579c09	deleted	1
f9579c09	files	1
f9579c09	body	Adds the actual Director script from snowgoons.lev as a worked example:\nthree per-zone mailboxes (100, 99, 98) fanned into INDEXOF_CAMSHOT each\ntick, with a stack trace and explanation of why per-zone indirection\navoids ActBoxOR stomping.  Corrects the Notes bullet: both `fi` and\n`then` are valid in this zForth build; snowgoons uses `then`.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
a9325421	author	Will Norris
a9325421	added	83
a9325421	deleted	0
a9325421	files	1
a9325421	body	Adds three annotated zForth scripts for the Director actor: one-shot cut\nwith fire-once guard, timed cut after N ticks, and looping two-shot\nsequence with phase tracking.  Also adds a Notes subsection covering\nobject index lookup, tick rate, `fi`/`then` difference, `write-mailbox`\nstack order, and pan-time sourcing.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
bc73a491	author	Will Norris
bc73a491	added	5
bc73a491	deleted	1
bc73a491	files	1
bc73a491	body	Director is CanRender/CanUpdate=false; its Script field is the interface.\nIntended for scripted camera sequences (write EMAILBOX_CAMSHOT, etc.).\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
80ee5168	author	Will Norris
80ee5168	added	212
80ee5168	deleted	0
80ee5168	files	1
80ee5168	body	Covers all four actor types (Camera, CamShot, ActBoxOR, Director), the\nCameraHandler state machine (Delay→Normal→Pan→Normal, Bungee variant),\nPanCameraHandler lerp details, all CamShot OAS fields with notes on what\nworks vs what's broken (FOV/Hither/Yon not applied, roll disabled,\nperspective-only), and a level-authoring how-to.\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
-->
