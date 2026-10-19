| Date | Change |
|------|--------|
| [2026-09-20](https://github.com/wbniv/WorldFoundry/commit/39e5310d) | feat(condo): seam-darkening + ambient trim so walls read at corners/ceiling |

<!--history-meta v1
39e5310d	author	Will Norris
39e5310d	added	236
39e5310d	deleted	0
39e5310d	files	1
39e5310d	body	Floor darkening (2026-09-19) only separated floor from wall; wall-to-wall\ncorners and the wall/ceiling line were still one flat colour, since the\nengine has no shadows/AO and the scene used only 1 of its 3 directional\nlight slots. Generalizes darken_floors() into darken_seams(): bisects wall\nquads and retints thin border strips at floor/ceiling bands and concave\nwall/wall corners, faking the contact-AO the renderer can't compute.\nAmbient trimmed 0.45 -> 0.38 to sharpen contrast.\n\nThe plan's third change (a 2nd directional fill light) is withdrawn: the\nengine reads any 2nd/3rd Light actor as AMBIENT_LIGHT regardless of\nauthored type and asserts (level.cc:1200). Fill-light code ships gated\noff (CONDO_FILL_INTENSITY=0) pending that engine-side fix.\n\nSee docs/plans/2026-09-20-condo-wall-shading-definition.md for the full\nverification record and before/after screenshots.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_011WmfFdmKRi46BtcEyu8pkT
-->
