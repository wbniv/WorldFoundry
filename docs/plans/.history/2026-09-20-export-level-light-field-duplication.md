| Date | Change |
|------|--------|
| [2026-09-20](https://github.com/wbniv/WorldFoundry/commit/e175ff38) | fix(wf_blender): stop double-emitting light fields in export_level.py |
| [2026-09-20](https://github.com/wbniv/WorldFoundry/commit/a5aef4b1) | docs(plans): plan to stop export_level.py double-emitting light fields |

<!--history-meta v1
e175ff38	author	Will Norris
e175ff38	added	227
e175ff38	deleted	8
e175ff38	files	1
e175ff38	body	export_level.py emitted lightRed/Green/Blue/lightType twice for every\nLight actor: once from the schema walk (correct, reads light.oas),\nonce from a hardcoded is_light block carrying its own hand-copied\nlt_map enum mapping - the same drift-prone pattern class just fixed in\nlevelcon.h. Harmless today only because levcomp-rs resolves duplicate\nfield names by first match and both copies happened to agree.\n\nRoutes the native-Blender-LIGHT-object case through the same\nwf_light* custom-property path the schema walk already reads, instead\nof emitting .lev text by hand; deletes the now-fully-redundant\nhardcoded block and its lt_map. New static regression test\n(tests/test_export_level_light_fields.py) asserts no second\nhand-written copy of light.oas's enum labels can reappear.\n\nVerified byte-identical .iff output across 420/424 rebuildable levels\n(4 failures are pre-existing stale committed artifacts, unrelated -\nreproduced identically with export_level.py stashed back to HEAD).\ncondo_639_640's .lev lost exactly the 12 duplicate lines, nothing\nelse changed.\n\nOne escalation left open, not fixed here: the qbert_practice golden\nfixture test now fails, because that fixture .blend carries a stale\nabsolute wf_schema_path from a different repo checkout\n(WorldFoundry.2026-new-level, not this one), which silently fails\nschema loading and was relying on the now-removed duplicate block as\nits only light-field emitter. Confined to the test fixture - the\nreal shipped qbert_practice.lev (valid schema path) is unaffected.\nTracked as a follow-up TODO item rather than papered over by\nregenerating the golden without fixing the actual stale path.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_011WmfFdmKRi46BtcEyu8pkT
a5aef4b1	author	Will Norris
a5aef4b1	added	112
a5aef4b1	deleted	0
a5aef4b1	files	1
a5aef4b1	body	Every Light actor's lightRed/Green/Blue/lightType gets emitted twice in\nthe exported .lev text: once from the schema walk (correct, reads\nlight.oas), once from a hardcoded is_light block with its own\nhand-copied lt_map enum mapping - the same drift-prone pattern just\nfixed in levelcon.h. Harmless today only because levcomp-rs resolves\nduplicate field names by first-match and both copies happen to agree.\n\nTraced the resolution mechanism (lev_parser.rs:94, Iterator::find) to\nconfirm which copy actually governs behavior before writing the fix\nplan. Flagged as a known trap in the sibling\n2026-09-20-engine-multi-directional-light-fix.md plan's Out of scope.\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_011WmfFdmKRi46BtcEyu8pkT
-->
