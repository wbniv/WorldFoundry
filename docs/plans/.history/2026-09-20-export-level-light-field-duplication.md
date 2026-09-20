| Date | Change |
|------|--------|
| [2026-09-20](https://github.com/wbniv/WorldFoundry/commit/a5aef4b1) | docs(plans): plan to stop export_level.py double-emitting light fields |

<!--history-meta v1
a5aef4b1	author	Will Norris
a5aef4b1	added	112
a5aef4b1	deleted	0
a5aef4b1	files	1
a5aef4b1	body	Every Light actor's lightRed/Green/Blue/lightType gets emitted twice in\nthe exported .lev text: once from the schema walk (correct, reads\nlight.oas), once from a hardcoded is_light block with its own\nhand-copied lt_map enum mapping - the same drift-prone pattern just\nfixed in levelcon.h. Harmless today only because levcomp-rs resolves\nduplicate field names by first-match and both copies happen to agree.\n\nTraced the resolution mechanism (lev_parser.rs:94, Iterator::find) to\nconfirm which copy actually governs behavior before writing the fix\nplan. Flagged as a known trap in the sibling\n2026-09-20-engine-multi-directional-light-fix.md plan's Out of scope.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_011WmfFdmKRi46BtcEyu8pkT
-->
