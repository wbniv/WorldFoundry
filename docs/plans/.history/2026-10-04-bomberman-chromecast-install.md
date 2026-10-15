| Date | Change |
|------|--------|
| [2026-10-09](https://github.com/wbniv/WorldFoundry/commit/ef99d415) | Record pending coordinator, runtime diagnostics and aquarium work |
| [2026-10-04](https://github.com/wbniv/WorldFoundry/commit/98485d9b) | Allow coordinated background installs and drain service upgrades |

<!--history-meta v1
ef99d415	author	Will Norris
ef99d415	added	34
ef99d415	deleted	2
ef99d415	files	1
ef99d415	body	Extract coordinator service code into the standalone project and retain producer wrappers. Add opt-in runtime diagnostics, runtime settings authoring, Android joystick controls, anemone and goby assets, updated posters and research references, and the accumulated device/review evidence. Preserve renamed A3 PDFs and omit the generated test executable.\n\nTargeted validation: 127 initial tests passed; phone and runtime-property UI tests pass 4/4 after installing the required browser and updating a stale native-colour-input test to the current palette UI. Android touch behavior passes 157 checks. Pending text credential-pattern scan found no matches.\n\nCo-Authored-By: Codex <noreply@openai.com>
98485d9b	author	Will Norris
98485d9b	added	25
98485d9b	deleted	0
98485d9b	files	1
98485d9b	body	Preserve personal reservations and per-device test exclusivity, add bounded deployment readiness and stopped-service recovery, and package Bomberman for offline Android TV installation. Record verified installations on both Chromecasts. The isolated staged coordinator suite passes all 50 tests.
-->
