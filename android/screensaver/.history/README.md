| Date | Change |
|------|--------|
| [2026-10-22](https://github.com/wbniv/WorldFoundry/commit/80f43e98) | Use generic Settings catalogs for screensaver controls |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/d1676c33) | Planted Tank: generate the APK's coordinator settings from the OAD |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/3d56263d) | Planted Tank Phase 4a: Taskfile build and test entries, coordinator and README docs |
| [2026-10-21](https://github.com/wbniv/WorldFoundry/commit/8876f6cd) | Planted Tank screensaver: Java side (PlantedConfig, settings, provider, activity, Dream) |
| [2026-10-19](https://github.com/wbniv/WorldFoundry/commit/0df0c0ad) | Add branded aquarium and seahorse screensavers |
| [2026-10-18](https://github.com/wbniv/WorldFoundry/commit/54f44b51) | Add live aquarium screensaver with per-tank players |

<!--history-meta v1
80f43e98	author	Will Norris
80f43e98	added	2
80f43e98	deleted	2
80f43e98	files	1
d1676c33	author	Will Norris
d1676c33	added	2
d1676c33	deleted	2
d1676c33	files	1
d1676c33	body	Will's decision (docs/plans/2026-10-21-planted-tank-screensaver.md): the APK's\nsettings come from the OAD, not a second copy in Java.\n\n- scripts/gen-planted-capabilities.py reads the compiled settings-class OAD\n  (type name ending in Settings) through build-object-properties.py's\n  normalizer (new oad_schema()) and writes the schema-1 capabilities JSON.\n  Labelled choices (radio, labelled slider) become choice; Hold's number\n  keeps the 1/2/5/10 min presets, validated against the OAD range; Paused\n  is dropped; checkbox/text/bare-number fields are skipped with a warning.\n- build_planted() writes it to the planted flavor's assets (gitignored).\n- PlantedSettingsProvider.getCapabilities serves the asset with the saved\n  values overlaid (same document as before) and throws if it is missing.\n- PlantedConfigTest takes the generated JSON and fails when PlantedConfig\n  and the OAD disagree; tests/test_planted_capabilities.py pins the\n  document; task test-planted-screensaver runs both.\n- Docs: replace the unconfirmed "coordinator does not register the\n  package" claim with what the APK declares.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
3d56263d	author	Will Norris
3d56263d	added	2
3d56263d	deleted	0
3d56263d	files	1
3d56263d	body	Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
8876f6cd	author	Will Norris
8876f6cd	added	23
8876f6cd	deleted	0
8876f6cd	files	1
8876f6cd	body	Phase 2a of docs/plans/2026-10-21-planted-tank-screensaver.md. PlantedConfig is a\npure-Java validator for water, seed, speed, hold and the developer keys, with a\nplain-javac test. PlantedSettings, PlantedSettingsProvider, PlantedTankActivity and\nPlantedTankDreamService wrap it; TankPlayer gains an additive configure(line) that\ncalls nativeConfigure only when set. The planted flavor manifest and strings are in\nsrc/planted; the Gradle flavor itself is not in this commit.\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01LmFZJSGwibDCpz7J9wzY9X
0df0c0ad	author	Will Norris
0df0c0ad	added	5
0df0c0ad	deleted	1
0df0c0ad	files	1
54f44b51	author	Will Norris
54f44b51	added	20
54f44b51	deleted	0
54f44b51	files	1
-->
