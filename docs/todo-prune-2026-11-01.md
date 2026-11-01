# TODO Inbox triage, 2026-11-01

Will asked for the stale items to be ranked and pruned (2026‑11‑01: "rank and prune them"). The Inbox held 198 auto-captured items from plans' "Out of scope" and "Deferred" sections. Every one of them is still written in the plan it came from, so deleting it here loses nothing; the fingerprint ledger keeps it from coming back.

| Outcome | Count | Rule |
| --- | --- | --- |
| done | 19 | Marked `[x]`, `[done]` or `[completed]` in the plan. |
| duplicate | 12 | The same line captured more than once (repeated plans, repeated measurements). |
| resolved | 4 | Struck through in the plan, or a statement the plan itself has since corrected. |
| tracked elsewhere | 29 | An open, parked or done item already covers it. |
| non-goal | 91 | A scope exclusion with no follow-up implied; the plan keeps the text. |
| consolidated | 21 | Plan-verification nags with no PASS recorded; replaced by one ranked Parked item that lists the plans. |
| merged | 5 | Folded into the promoted item it belongs with. |
| kept | 17 | Ranked and moved to Open or Parked. |

## Done (19)

- Approach A (pooled-generator fireball) — already shipped; this is the orthogonal Approach B. — _the plan says it already shipped or landed; from 2026-06-13-spawn-template-forth-primitive.md_
- Any change to `blender_create_condo.py`'s wall/seam-shading work (`docs/plans/2026-09-20-condo-wall-shading-definition.md`) — unrelated, already landed. — _the plan says it already shipped or landed; from 2026-09-20-condo-sun-solar-position.md_
- **The condo** (`condo_639_640{,_tour}`) — already re-aimed by the engine-fix change, and explicitly excluded here. Note for whoever touches it next: its `wf_light_aim()` docstring still describes B as "tips the beam **down**". The… — _the plan says it already shipped or landed; from 2026-09-20-relight-swept-levels.md_
- Android/Chromecast selector and Back navigation implemented. A short Back returns to the selector; selector Back exits. Verified all seven Aquarium tanks and four SMB levels on 2026-10-02. — _marked done in the plan; from 2026-10-01-level-menu-selector.md_
- [x] Regression coverage in `tests/test_aquarium_barb_motion.py`: old/new heading boundary continuity at four elapsed intervals, glass bounds and shortest-wrap/capped rotation. — _marked done in the plan; from 2026-10-02-aquarium-tiger-barbs.md_
- [x] 48 aquarium asset, level, alpha/deformation, startle and movement checks passed; the final turn-cap/startle subset passed all 10 checks. — _marked done in the plan; from 2026-10-02-aquarium-tiger-barbs.md_
- [x] Regenerate the final standalone aquarium for integration into the five-tank selector. Standalone SHA-256: `04f5cc0723d1527280aa854c9c59d4a6c7a7536d9a739a0773c68342867f9081`; single-tank CD SHA-256: `46fb8315fa34ddb4f11f2b607f5… — _marked done in the plan; from 2026-10-02-aquarium-tiger-barbs.md_
- [x] [Final real-engine movement receipt](2026-10-02-aquarium-tiger-barbs/barb-motion-regression.json): 29 fish, 160 measured frames at 20 Hz; maximum movement 0.088902 world metres/tick, matching the 0.0889 speed limit within fixe… — _marked done in the plan; from 2026-10-02-aquarium-tiger-barbs.md_
- [x] Included and installed in the [five-tank selector release](2026-10-02-aquarium-five-tank-selector.md), with exact final standalone payload verified. APK SHA-256: `6236ade65122ff712556be9a183ca83f1240bf9d85549830eb6f1bcc6de352b… — _marked done in the plan; from 2026-10-02-aquarium-tiger-barbs.md_
- Build an Aquarium release APK from the clean checkout with the jellyfish update. — _marked done in the plan; from 2026-10-02-jellyfish-biomechanics-poster.md_
- Install and select the jellyfish tank on Chromecast HD. — _marked done in the plan; from 2026-10-02-jellyfish-biomechanics-poster.md_
- Inspect translucency and pulsing, and capture presented-frame timestamps. — _marked done in the plan; from 2026-10-02-jellyfish-biomechanics-poster.md_
- Record device results and push the focused commits. — _marked done in the plan; from 2026-10-02-jellyfish-biomechanics-poster.md_
- Build an Aquarium release APK from the clean checkout with the jellyfish update. — _marked done in the plan; from 2026-10-02-jellyfish-biomechanics-poster.md_
- Install and select the jellyfish tank on Chromecast HD. — _marked done in the plan; from 2026-10-02-jellyfish-biomechanics-poster.md_
- Inspect translucency and pulsing, and capture presented-frame timestamps. — _marked done in the plan; from 2026-10-02-jellyfish-biomechanics-poster.md_
- Record device results and push the focused commits. — _marked done in the plan; from 2026-10-02-jellyfish-biomechanics-poster.md_
- **2026-10-03-aquatic-plant-clumps-and-poster** — PASS: runtime/settings/colour checks and current-build mature texture comparison; broader growth/sway and repeated-entry measurements remain in the plan. — _marked done in the plan; from 2026-10-03-aquatic-plant-clumps-and-poster.md_
- **2026-10-04-chromecast-background-install** — PASS: all 50 isolated coordinator tests and verified background installation on both devices; hardware gameplay and playback continuity measurements remain pending in the plan. — _marked done in the plan; from 2026-10-04-chromecast-background-install.md_

## Duplicate (12)

- Play Store or any distribution beyond `adb` sideload. — _the same line is captured more than once; from 2026-09-30-aquarium-chromecast.md_
- A C++ fallback: the measured 7.0 ms (about 0.7 ms a follower, spread over frames) does not force one. The in-engine measurement can. — _the same line is captured more than once; from 2026-10-01-swarming-poster.md_
- A C++ fallback: the measured 7.5 ms (about 0.75 ms a follower, spread over frames) does not force one. The in-engine measurement can. — _the same line is captured more than once; from 2026-10-01-swarming-poster.md_
- A C++ fallback: the measured 7.3 ms (about 0.73 ms a follower, spread over frames) does not force one. The in-engine measurement can. — _the same line is captured more than once; from 2026-10-01-swarming-poster.md_
- Motorising plan B, or any automation of it, and an interior blind behind plan B's glass. — _the same line is captured more than once; from 2026-09-30-condo-balcony-shade.md_
- A level-model variant (§ 7d) for plan B until it is chosen. — _the same line is captured more than once; from 2026-09-30-condo-balcony-shade.md_
- Runtime TTF rasterization. As in finding-your-way, the runtime only ever sees baked pixels and metrics. — _the same line is captured more than once; from 2026-10-17-settings-editor-font.md_
- Scripts other than Latin. The atlas covers ASCII, Latin‑1 and common punctuation; widening it is a bake-list change. — _the same line is captured more than once; from 2026-10-17-settings-editor-font.md_
- Dialogue text. It keeps its own per-level `DLOG` bundles, which already use the same `WFGA` path. — _the same line is captured more than once; from 2026-10-17-settings-editor-font.md_
- Runtime TTF rasterization. As in finding-your-way, the runtime only ever sees baked pixels and metrics. — _the same line is captured more than once; from 2026-10-17-settings-editor-font.md_
- Scripts other than Latin. The atlas covers ASCII, Latin‑1 and common punctuation; widening it is a bake-list change. — _the same line is captured more than once; from 2026-10-17-settings-editor-font.md_
- Dialogue text. It keeps its own per-level `DLOG` bundles, which already use the same `WFGA` path. — _the same line is captured more than once; from 2026-10-17-settings-editor-font.md_

## Resolved (4)

- Higher than 640 × 480: the Linux HAL has no `-width/-height` switch yet (TODO item exists); upscale with ffmpeg if needed. — _struck through in the plan; from 2026-09-19-condo-639-tour-video.md_
- Higher than 640 × 480: ~~the Linux HAL has no `-width/-height` switch yet~~ — it does; the game parser was eating `-height=` (fixed 2026‑09‑19, [plan](2026-09-19-window-size-flags-reach-the-game-parser.md)). `TOUR_SIZE=1280x960` w… — _struck through in the plan; from 2026-09-19-condo-639-tour-video.md_
- ~~A runtime collision toggle so the closed state actually re-blocks the doorway — needs engine work (a collision/mass mailbox) and is a design decision nobody has made. The doors ship `Mass 0` in both states; see Collision under A… — _struck through in the plan; from 2026-09-20-condo-project-room-telescoping-doors.md_
- ~~True continuous sliding animation (mailbox-driven per-tick position lerp, the `fsn_flydown()` pattern) — rejected for v1 as a first-of-its-kind, Jolt-sync-risk pattern with no precedent in this codebase; the two-state `Visibilit… — _struck through in the plan; from 2026-09-20-condo-project-room-telescoping-doors.md_

## Tracked elsewhere (29)

- Template-name → constant authoring (investigation option 2) — separate follow-up when a — _Parked: Forth spawn primitive; from 2026-06-13-spawn-template-forth-primitive.md_
- Arbitrary-velocity / concurrent-burst consumers — this primitive enables them; wiring a — _Parked: Forth spawn primitive; from 2026-06-13-spawn-template-forth-primitive.md_
- A generic "mover/door" actor class or Forth "move actor over time" syscall — the real engine gap this surfaced (`TODO.md:131`, `docs/investigations/2026-05-26-spawn-template-forth-primitive.md`). Worth its own engine-level investi… — _Open: Rideable moving platforms; Parked: Forth spawn primitive; from 2026-09-20-condo-project-room-telescoping-doors.md_
- **`mm_practice_blender` / `mm_practice_blender_rt` cannot be rebuilt from their `.lev`.** Their ambient is authored in the `.lev` but cannot reach the shipped `.iff`. Pre-existing and already tracked in `TODO.md` ("qbert_practice … — _Open: qbert_practice and mm_practice_blender_rt no longer rebuild; from 2026-09-20-engine-multi-directional-light-fix.md_
- **`mm_practice_blender{,_rt}`** — still blocked on the pre-existing rebuild defect recorded in the engine-fix plan's Verification step 8. — _Open: qbert_practice and mm_practice_blender_rt no longer rebuild; from 2026-09-20-relight-swept-levels.md_
- **Making the inward-wound levels culling-correct.** Re-winding those meshes would flip every aim in the table above; it is the real fix and a separate effort (it is what `WF_CULL=1` is waiting on). — _the backface-culling work (planetarium-dome-view-engine-wide-backface-culling plan); from 2026-09-20-relight-swept-levels.md_
- 4K framebuffer optimisation (EGL surface from `ANativeWindow` already adapts to the display size — no extra code) — _nothing to do: the EGL surface already adapts; from 2026-04-23-chromecast-google-tv-port.md_
- 4K framebuffer optimisation (`EGL` surface from `ANativeWindow` already adapts to the display size — no extra code) — _nothing to do: the EGL surface already adapts; from 2026-04-23-chromecast-googletv-port.md_
- Audio (silent stub on Android; the "Audio assets from IFF" item in `TODO.md`). — _Audio assets from IFF (Parked); from 2026-10-01-condo-chromecast.md_
- Audio (silent stub on Android; the "Audio assets from IFF" item in `TODO.md`). — _Audio assets from IFF (Parked); from 2026-09-30-aquarium-chromecast.md_
- Music control from non-Lua engines: `MUSIC_PLAY`, `MUSIC_STOP` and `MUSIC_VOLUME` mailboxes (Phase B of the [deferred mailbox plan](deferred/2026-04-17-audio-mailbox-api.md)). The three Lua closures stay as they are. — _Audio assets from IFF (Parked) and the deferred audio-mailbox plan; from 2026-10-01-sfx-without-lua.md_
- Named `SFX_<name>` constants instead of slot numbers (Phase C of that plan). — _the deferred audio-mailbox plan; from 2026-10-01-sfx-without-lua.md_
- Moving the music and the soundfont into the IFF (the rest of Audio assets from IFF). — _Audio assets from IFF (Parked); from 2026-10-01-sfx-without-lua.md_
- Hearing audio on iOS: it needs a real device with Apple signing. — _Audio assets from IFF (Parked); from 2026-10-01-sfx-without-lua.md_
- The aquarium and condo flavors still bundle no music or sound effects: that is [Phase D of the aquarium-Chromecast plan](2026-09-30-aquarium-chromecast.md) (music) and [the SFX plan](2026-10-01-sfx-without-lua.md) (sound effects). — _Audio assets from IFF (Parked); from 2026-10-01-soundfont-subset.md_
- Moving the soundfont into the IFF ([Audio assets from IFF](2026-04-18-audio-assets-from-iff.md)); this plan only makes the loose file reproducible. — _Audio assets from IFF (Parked); from 2026-10-01-soundfont-subset.md_
- A menu that picks a level inside one `cd.iff` (its own TODO item). — _Done: main cd.iff manifest and level menu; from 2026-10-01-split-cd-iff-one-app-per-game.md_
- Music and sound for SMB and Q\*bert ("Audio assets from IFF"). — _Audio assets from IFF (Parked); from 2026-10-01-split-cd-iff-one-app-per-game.md_
- Returning to the menu on game over (needs per-level signals). — _Parked: Level menu follow-ups; from 2026-10-01-level-menu-selector.md_
- Mouse and touch selection. — _Parked: Level menu follow-ups; from 2026-10-01-level-menu-selector.md_
- Screenshots or icons per entry. — _Parked: Level menu follow-ups; from 2026-10-01-level-menu-selector.md_
- **Six-pair density:** implemented at Will’s request on 2026‑10‑16, superseding the earlier two-pair limit. Chromecast performance at this density still needs measurement. — _Seahorse handoff: step 10 PASS 2026‑10‑17; from 2026-10-16-saltwater-seahorses.md_
- **2026-10-17-settings-editor-font** — Verification section present but no PASS recorded — run + record the steps. — _an open [verify] item already covers this plan; from 2026-10-17-settings-editor-font.md_
- **2026-10-21-planted-tank-screensaver** — Verification section present but no PASS recorded — run + record the steps. — _an open [verify] item already covers this plan; from 2026-10-21-planted-tank-screensaver.md_
- **2026-10-29-touch-settings-phone-tablet** — Verification section present but no PASS recorded — run + record the steps. — _an open [verify] item already covers this plan; from 2026-10-29-touch-settings-phone-tablet.md_
- Drawing the eleven `proposed` controls. That belongs to the touch settings work. — _Done: field-presentations; from 2026-10-31-baseline-settings-cleanup.md_
- Making runtime options editable. — _Open: Runtime object editing on OAS/OAD; from 2026-10-31-baseline-settings-cleanup.md_
- **2026-10-31-baseline-settings-cleanup** — Verification section present but no PASS recorded — run + record the steps. — _an open [verify] item already covers this plan; from 2026-10-31-baseline-settings-cleanup.md_
- Making runtime options editable. — _Open: Runtime object editing on OAS/OAD; from 2026-11-01-field-presentations.md_

## Non-goal (91)

- Motorising plan B, or any automation of it, and an interior blind behind plan B's glass. — _a scope exclusion; the plan still records it; from 2026-09-30-condo-balcony-shade.md_
- A level-model variant (§ 7d) for plan B until it is chosen. — _a scope exclusion; the plan still records it; from 2026-09-30-condo-balcony-shade.md_
- Room presence triggers (`actbox` per room writing a `CONDO_ROOM` mailbox + a `Meter` readout) — first useful upgrade once the walkthrough exists. — _a scope exclusion; the plan still records it; from 2026-09-19-condo-639-640-level.md_
- Drop‑ceiling toggle (a `Visibility Mailbox` on a re‑enabled `unit-640-drop-ceiling` statplat). — _a scope exclusion; the plan still records it; from 2026-09-19-condo-639-640-level.md_
- Translucent glass — needs a `MATL` flag + renderer path; engine work, tracked separately if wanted. — _a scope exclusion; the plan still records it; from 2026-09-19-condo-639-640-level.md_
- A 640 tour (same script, different waypoints; do it once 639's cut is approved). — _a scope exclusion; the plan still records it; from 2026-09-19-condo-639-tour-video.md_
- Camera moves other than the doll‑house follow (a fly‑through would need a second CamShot + ActBoxOR switching). — _a scope exclusion; the plan still records it; from 2026-09-19-condo-639-tour-video.md_
- A tour of 640's *own* (ochre) rooms — same script, different waypoints. — _a scope exclusion; the plan still records it; from 2026-09-19-condo-639-tour-video.md_
- Room‑by‑room floor colours (would need per‑room face selection from the `target` bboxes). — _a scope exclusion; the plan still records it; from 2026-09-19-condo-darker-floors.md_
- Any change to the source model's materials. — _a scope exclusion; the plan still records it; from 2026-09-19-condo-darker-floors.md_
- macOS AppKit window sizing — blocked on the Metal window (open TODO), see Approach 5. — _a scope exclusion; the plan still records it; from 2026-09-19-window-size-flags-reach-the-game-parser.md_
- Non‑4:3 sizes: `Display` inscribes a square 3D viewport and letterboxes; 16:9 works but shows the matte bars — a separate aspect decision. — _a scope exclusion; the plan still records it; from 2026-09-19-window-size-flags-reach-the-game-parser.md_
- Applying the seam-shade generalization to other levels — condo-specific script only for now; worth extracting into a shared helper if a second level needs it. — _a scope exclusion; the plan still records it; from 2026-09-20-condo-wall-shading-definition.md_
- A live in-engine day/night cycle (this is build-time only — the sun angle is baked into the level at export, not recomputed while playing). — _a scope exclusion; the plan still records it; from 2026-09-20-condo-sun-solar-position.md_
- Daylight-saving handling beyond `Asia/Bangkok`'s fixed UTC+7 (Thailand has none). — _a scope exclusion; the plan still records it; from 2026-09-20-condo-sun-solar-position.md_
- Extending real-solar-position sun angles to other levels — this plan only touches `wflevels/condo_639_640/site_constants.py`, which is condo-specific. — _a scope exclusion; the plan still records it; from 2026-09-20-condo-sun-solar-position.md_
- Deciding a "canonical frozen" `CONDO_SUN_DATETIME` for the committed level artifacts (`condo_639_640.iff`, `condo_sky.tga`, etc.) — those get whatever moment they're next rebuilt at, per the user's direction; if a specific frozen … — _a scope exclusion; the plan still records it; from 2026-09-20-condo-sun-solar-position.md_
- Extending this telescoping-door pattern to any other wall/unit — 639-project-rm only. — _a scope exclusion; the plan still records it; from 2026-09-20-condo-project-room-telescoping-doors.md_
- Real-world-accurate door hardware/track visuals (rollers, header track, handles) — glass panels + a plausible frame, not a hardware-accurate model. — _a scope exclusion; the plan still records it; from 2026-09-20-condo-project-room-telescoping-doors.md_
- Any change to `light.oas` — its schema is already correct; this plan makes the export code actually rely on it as the single source of truth, nothing more. — _a scope exclusion; the plan still records it; from 2026-09-20-export-level-light-field-duplication.md_
- The 12-level Ambient-light sweep or any level *content* changes — unrelated, tracked in `docs/plans/2026-09-20-engine-multi-directional-light-fix.md`. — _a scope exclusion; the plan still records it; from 2026-09-20-export-level-light-field-duplication.md_
- A generic OAD-authored `Platform`/waypoint system — see Context for why it was rejected as the fix target; worth its own plan if a future level wants designer-authored multi-point paths, not attempted here. — _a scope exclusion; the plan still records it; from 2026-09-20-jolt-kinematic-position-sync.md_
- Reviving `Path`/`PathHandler` — dead code, not worth resurrecting for this. — _a scope exclusion; the plan still records it; from 2026-09-20-jolt-kinematic-position-sync.md_
- Any change to the existing `JoltCharacterID()` branch's behavior — pure addition, character-controlled actors (the player) are untouched. — _a scope exclusion; the plan still records it; from 2026-09-20-jolt-kinematic-position-sync.md_
- **`main_game`** has an Ambient in its `.lev` but no `.lvl`/standalone `.iff` build path, so the change is source-only and not runtime-verifiable here. — _a scope exclusion; the plan still records it; from 2026-09-20-engine-multi-directional-light-fix.md_
- **Re-aiming the other levels' directional lights.** Every level still uses the `(pi/2 - alt, 0, az)` recipe, so their key lights are exactly horizontal. That is not *new* — it has always been true — but until now the position leak… — _a scope exclusion; the plan still records it; from 2026-09-20-engine-multi-directional-light-fix.md_
- **Re-tuning the condo's exposure.** With the Sun finally applied as a key light at its authored 1.0/1.0/0.96, lit floors clip (`0.38` ambient `+ ~0.77 N·L` ≈ 1.15). It reads well in the captures, but if a flatter look is wanted th… — _a scope exclusion; the plan still records it; from 2026-09-20-engine-multi-directional-light-fix.md_
- **`main_game`** — no runtime-verifiable build path here, same as in the sweep. — _a scope exclusion; the plan still records it; from 2026-09-20-relight-swept-levels.md_
- Choosing a supplier or price; this plan fixes the spec, not the purchase. — _a scope exclusion; the plan still records it; from 2026-09-30-condo-balcony-shade.md_
- Shading the *interior* side or the other patio room (x 5.40–7.80, full-height wall). — _a scope exclusion; the plan still records it; from 2026-09-30-condo-balcony-shade.md_
- Weather in the level (rain, wind on the fabric). — _a scope exclusion; the plan still records it; from 2026-09-30-condo-balcony-shade.md_
- Adding the balcony's real slab thickness, drainage falls or waterproofing lip under the 7 cm recess. — _a scope exclusion; the plan still records it; from 2026-09-30-condo-balcony-shade.md_
- A solar-yield model tied to `SUN_ALT_DEG` / `SUN_AZ_DEG`; the existing sun-position item ([plan](2026-09-20-condo-sun-solar-position.md)) is the prerequisite. — _a scope exclusion; the plan still records it; from 2026-09-30-condo-balcony-shade.md_
- Raising the whole level to 3 m ceilings (filed separately). — _a scope exclusion; the plan still records it; from 2026-09-30-condo-balcony-shade.md_
- **Real iPhone or iPad hardware:** needs Apple signing and provisioning; TestFlight and the App Store as well. Only simulators here. — _a scope exclusion; the plan still records it; from 2026-09-30-aquarium-platforms.md_
- **Play Store submission** and any distribution beyond `adb` sideload. — _a scope exclusion; the plan still records it; from 2026-09-30-aquarium-platforms.md_
- **Steering the fish with only a TV remote** (a D-pad and OK, no B, C or A). The gamepad profile is the target. — _a scope exclusion; the plan still records it; from 2026-09-30-aquarium-platforms.md_
- **Changing `WORLD_SCALE`** or the engine's fixed limits (decided 2026‑09‑30). — _a scope exclusion; the plan still records it; from 2026-09-30-aquarium-platforms.md_
- **macOS close paths** (⌘Q, red button, Retina, `-fullscreen`): stay under the macOS Metal renderer item in `TODO.md`. — _a scope exclusion; the plan still records it; from 2026-09-30-aquarium-platforms.md_
- **Restoring texture alpha** (translucent front pane): its own `TODO.md` item. — _a scope exclusion; the plan still records it; from 2026-09-30-aquarium-platforms.md_
- The condo on a phone, iPad, iPhone or Mac (the `_touch` profile exists for phones); a separate item. — _a scope exclusion; the plan still records it; from 2026-10-01-condo-chromecast.md_
- Optimising the frame rate by changing the level or the engine. — _a scope exclusion; the plan still records it; from 2026-10-01-condo-chromecast.md_
- Play Store or any distribution beyond `adb` sideload. — _a scope exclusion; the plan still records it; from 2026-10-01-condo-chromecast.md_
- A gamepad profile beyond the existing key mapping, until a gamepad is paired (Phase D). — _a scope exclusion; the plan still records it; from 2026-09-30-aquarium-chromecast.md_
- Phone and tablet devices, iPhone and iPad (separate items in the porting status). — _a scope exclusion; the plan still records it; from 2026-09-30-aquarium-chromecast.md_
- Volume, pitch, looping and stopping a sound that is playing; HRTF, reverb, occlusion. — _a scope exclusion; the plan still records it; from 2026-10-01-sfx-without-lua.md_
- Renaming `florestan-subset.sf2`. — _a scope exclusion; the plan still records it; from 2026-10-01-soundfont-subset.md_
- Predators, feeding, breeding, more than a build-time constant of followers, and followers that are not clownfish (a separate plan). — _a scope exclusion; the plan still records it; from 2026-10-01-aquarium-schooling.md_
- Jolt bodies or real collisions for followers. — _a scope exclusion; the plan still records it; from 2026-10-01-aquarium-schooling.md_
- Sound or haptics for the school (the [SFX plan](2026-10-01-sfx-without-lua.md) and the phone controller could hook in later). — _a scope exclusion; the plan still records it; from 2026-10-01-aquarium-schooling.md_
- A C++ flocking implementation, unless Phase 0 forces it (then it is a decision). **What that means:** if Forth proves too slow for ten fish on the Chromecast, the ladder is (1) stay in Forth and update a third of the fish per tick… — _a scope exclusion; the plan still records it; from 2026-10-01-aquarium-schooling.md_
- Wiring `school.fth` into the aquarium level: that is [the schooling plan](2026-10-01-aquarium-schooling.md). This plan produced the evidence its Phase 0 asks for (size, cost, parameters, the tank's real depth). — _a scope exclusion; the plan still records it; from 2026-10-01-swarming-poster.md_
- A C++ fallback: the measured 6.2 ms (about 0.6 ms a follower, spread over frames) does not force one. The in-engine measurement can. — _a scope exclusion; the plan still records it; from 2026-10-01-swarming-poster.md_
- The desktop `cd.iff`, its task and every desktop `run-*` task. — _a scope exclusion; the plan still records it; from 2026-10-01-split-cd-iff-one-app-per-game.md_
- An app for Astra Marble Madness. — _a scope exclusion; the plan still records it; from 2026-10-01-split-cd-iff-one-app-per-game.md_
- The phone controller and any permission for the new apps. — _a scope exclusion; the plan still records it; from 2026-10-01-split-cd-iff-one-app-per-game.md_
- iOS and macOS apps for these games. — _a scope exclusion; the plan still records it; from 2026-10-01-split-cd-iff-one-app-per-game.md_
- Real names and real art (the user's choice; the placeholders are listed in the Result). — _a scope exclusion; the plan still records it; from 2026-10-01-split-cd-iff-one-app-per-game.md_
- A tuned startle (radius, gain, duration by eye on the TV), a startle that scales with the dart's speed, or other triggers (the leader hitting a wall). Tuning is Phase 2 of [the schooling plan](2026-10-01-aquarium-schooling.md). — _a scope exclusion; the plan still records it; from 2026-10-02-school-dart-startle.md_
- The anemone: the startled fish still ignore it. — _a scope exclusion; the plan still records it; from 2026-10-02-school-dart-startle.md_
- **A playable seahorse.** The urchin stays the saltwater player; seahorses are autonomous residents. — _a scope exclusion; the plan still records it; from 2026-10-16-saltwater-seahorses.md_
- **Gripping live plants.** It needs a C++ stem-position query and sway tracking; the posts come first (D4). — _a scope exclusion; the plan still records it; from 2026-10-16-saltwater-seahorses.md_
- **Real prey particles and feeding.** Strikes target ambient drifting particles only. — _a scope exclusion; the plan still records it; from 2026-10-16-saltwater-seahorses.md_
- **Breeding, pouch pumping and fry.** — _a scope exclusion; the plan still records it; from 2026-10-16-saltwater-seahorses.md_
- **Morph targets and the sea anemone.** The anemone stays set aside, but it can resume on the same evaluator after Deformer phase 2. The travelling-wave operator is part of Deformer phase 2, not this plan's Phase 1. — _a scope exclusion; the plan still records it; from 2026-10-16-saltwater-seahorses.md_
- **More than 2 pairs.** The tank's biological ceiling is 4 pairs. The setting stops at 2. — _a scope exclusion; the plan still records it; from 2026-10-16-saltwater-seahorses.md_
- **Persisting runtime edits** back to the level or the repository. Edits stay session-only, as in the 2026‑10‑06 plan. — _a scope exclusion; the plan still records it; from 2026-10-16-runtime-object-editing.md_
- **Editing the `.oad` schemas themselves at runtime.** — _a scope exclusion; the plan still records it; from 2026-10-16-runtime-object-editing.md_
- **Translatable labels** (a string table). Revisit if localisation is planned. — _a scope exclusion; the plan still records it; from 2026-10-16-runtime-object-editing.md_
- **Trimming the shipped `.oad` padding.** It's an optimisation, deferred until size matters. — _a scope exclusion; the plan still records it; from 2026-10-16-runtime-object-editing.md_
- The level menu, the plant HUD, the FPS overlay and the phone overlay (F5). Each becomes a small follow-up once the atlas exists. — _a scope exclusion; the plan still records it; from 2026-10-17-settings-editor-font.md_
- Runtime TTF rasterization. As in finding-your-way, the runtime only ever sees baked pixels and metrics. — _a scope exclusion; the plan still records it; from 2026-10-17-settings-editor-font.md_
- Scripts other than Latin. The atlas covers ASCII, Latin‑1 and common punctuation; widening it is a bake-list change. — _a scope exclusion; the plan still records it; from 2026-10-17-settings-editor-font.md_
- Dialogue text. It keeps its own per-level `DLOG` bundles, which already use the same `WFGA` path. — _a scope exclusion; the plan still records it; from 2026-10-17-settings-editor-font.md_
- A desktop (Linux or macOS) screen saver; this is the Android TV Dream. — _a scope exclusion; the plan still records it; from 2026-10-21-planted-tank-screensaver.md_
- Seed entry in the coordinator tray: schema 1 carries choices only today; the seed stays on the command line. — _a scope exclusion; the plan still records it; from 2026-10-21-planted-tank-screensaver.md_
- A cross-fade between tanks. The reload shows the engine's normal load gap; Phase 5 measures it and an overlay fade (Java-side, no engine edit) is a follow-up if it looks rough. — _a scope exclusion; the plan still records it; from 2026-10-21-planted-tank-screensaver.md_
- An exact "plant is mature" engine word. The Forth clock plus a measured bound is enough; an exact word would need an engine edit. — _a scope exclusion; the plan still records it; from 2026-10-21-planted-tank-screensaver.md_
- Audio, as for Seahorse Grid. — _a scope exclusion; the plan still records it; from 2026-10-21-planted-tank-screensaver.md_
- Public distribution and signing, unchanged from the [aquarium plan](2026-10-17-aquarium-screensaver.md). — _a scope exclusion; the plan still records it; from 2026-10-21-planted-tank-screensaver.md_
- A reverse-landscape-only value. `sensor-landscape` covers both directions. — _a scope exclusion; the plan still records it; from 2026-10-24-screensaver-landscape-orientation.md_
- Rotating the picture ourselves when the system will not rotate the Dream (for example an Android version that ignores the request). Revisit if the verification below fails on a device. — _a scope exclusion; the plan still records it; from 2026-10-24-screensaver-landscape-orientation.md_
- Android 10 and earlier hardware testing, unless an enrolled device runs that version (verification step 7). — _a scope exclusion; the plan still records it; from 2026-10-24-screensaver-landscape-orientation.md_
- Per-tank or per-level orientation. The setting belongs to the screensaver app. — _a scope exclusion; the plan still records it; from 2026-10-24-screensaver-landscape-orientation.md_
- The Chromecast TVs, which are landscape already. — _a scope exclusion; the plan still records it; from 2026-10-24-screensaver-landscape-orientation.md_
- Declaring `Orientation` in the levels' OAD Settings instead of in the provider (see **Rejected**). Revisit it with a rule that merges the per-level owners into one app-level field, and with the engine's launch-override table check… — _a scope exclusion; the plan still records it; from 2026-10-24-screensaver-landscape-orientation.md_
- The Planted Tank and Aquarium catalogs, which share the host but not this fixture. — _a scope exclusion; the plan still records it; from 2026-10-31-baseline-settings-cleanup.md_
- A new engine API for level scripts to open a chosen owner. — _a scope exclusion; the plan still records it; from 2026-10-31-baseline-settings-cleanup.md_
- Settings on the diagnostics preset. — _a scope exclusion; the plan still records it; from 2026-10-31-baseline-settings-cleanup.md_
- Collision for teapots, and textures or UV mapping beyond a flat colour. — _a scope exclusion; the plan still records it; from 2026-10-31-baseline-utah-teapots.md_
- The 2026 curvature-continuous revision by Yuksel, Blinn and Newell, and the 1992 and 2006 solid variants. — _a scope exclusion; the plan still records it; from 2026-10-31-baseline-utah-teapots.md_

## Consolidated (21)

- **2026-06-13-spawn-template-forth-primitive** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-06-13-spawn-template-forth-primitive.md_
- **2026-06-13-web-av-finish-deferred-items** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-06-13-web-av-finish-deferred-items.md_
- **2026-09-19-condo-639-tour-video** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-09-19-condo-639-tour-video.md_
- **2026-09-30-condo-balcony-shade** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-09-30-condo-balcony-shade.md_
- **2026-09-30-ios-ci-revival** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-09-30-ios-ci-revival.md_
- **2026-10-02-aquarium-levels-blue-shrimp** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-02-aquarium-levels-blue-shrimp.md_
- **2026-10-02-aquarium-tiger-barbs** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-02-aquarium-tiger-barbs.md_
- **2026-10-02-betta-poster-and-flowing-fins** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-02-betta-poster-and-flowing-fins.md_
- **2026-10-02-lionfish-goldfish-feeding** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-02-lionfish-goldfish-feeding.md_
- **2026-10-02-condo-translucency** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-02-condo-translucency.md_
- **2026-10-06-freshwater-rainbow-goby** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-06-freshwater-rainbow-goby.md_
- **2026-10-06-runtime-oas-oad-object-editor** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-06-runtime-oas-oad-object-editor.md_
- **2026-10-06-runtime-diagnostics-bridge-audit** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-06-runtime-diagnostics-bridge-audit.md_
- **2026-10-06-runtime-diagnostics-bridge** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-06-runtime-diagnostics-bridge.md_
- **2026-10-06-standalone-chromecast-coordinator** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-06-standalone-chromecast-coordinator.md_
- **2026-10-16-saltwater-seahorses** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-16-saltwater-seahorses.md_
- **2026-10-16-runtime-object-editing** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-16-runtime-object-editing.md_
- **2026-10-16-blender-normal-convention-engine-wide** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-16-blender-normal-convention-engine-wide.md_
- **2026-10-18-aquarium-screensaver-input-verification** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-18-aquarium-screensaver-input-verification.md_
- **2026-10-24-screensaver-landscape-orientation** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-10-24-screensaver-landscape-orientation.md_
- **2026-11-01-touch-controls-over-cards** — Verification section present but no PASS recorded — run + record the steps. — _into the plan-verification backlog item; from 2026-11-01-touch-controls-over-cards.md_

## Merged (5)

- Re‑pointing the other level scripts' `~/.config/blender/4.0/…` fallback path (they still say 4.0). — _into the promoted item above; from 2026-09-19-condo-639-640-level.md_
- **Republish `worldfoundry-blender-editor-exporter`** from the current exporter (the apt build is `git3fa94cbe`, 2026‑05‑19; the restored exporter is `a148bd7d`+) so a fresh machine gets the dedup/deterministic export too. — _into the promoted item above; from 2026-09-19-condo-639-640-level.md_
- Baked/offline per-vertex ambient occlusion — same reasoning; would fix this at the root but is a cross-cutting engine feature, not a condo-script change. — _into the promoted item above; from 2026-09-20-condo-wall-shading-definition.md_
- The rest of the Newell tea set (teacup, teaspoon), which ships in the same dataset and is a natural follow-up. — _into the promoted item above; from 2026-10-31-baseline-utah-teapots.md_
- Making the teapots optional per preset. Every preset (default, diagnostics, settings-gallery) includes them today. — _into the promoted item above; from 2026-10-31-baseline-utah-teapots.md_

## Kept (17)

- **Republish `worldfoundry-blender-editor-exporter` on apt.worldfoundry.org from the current exporter — the apt build is `git3fa94cbe` (2026-05-19); the restored exporter (`a148bd7d`+) adds mesh dedup, deterministic vertex order an… — _promoted (see list)_
- Fixing `install.sh`'s dependency on `~/.config/blender/<latest>` for a non‑default Blender install. — _promoted (see list); from 2026-09-19-condo-639-640-level.md_
- **HD recordings play too fast.** Found while testing: the capture pipe declares `-framerate 30` and writes one frame per *rendered* frame, so at 1280 × 960 (≈21 fps on this box) a 30.7 s tour became a 23.4 s mp4. A wall‑clock‑pace… — _promoted (see list); from 2026-09-19-window-size-flags-reach-the-game-parser.md_
- Real shadow mapping or dynamic shadows — an engine-architecture change, not a per-level fix. Worth its own investigation if seam-faking proves insufficient. — _promoted (see list); from 2026-09-20-condo-wall-shading-definition.md_
- **Tie the condo sun to a true solar position.** Current `SUN_ALT_DEG`/`SUN_AZ_DEG` (`site_constants.py`) are an artist pick with no real match at this latitude (closest is off ~29°). Self-contained NOAA solar-position calc, defaul… — _promoted (see list)_
- Auditing other actor classes (`Matte`, etc.) in `export_level.py` for the same hardcoded-block-alongside-schema-walk pattern. Worth a follow-up grep-and-check, but not attempted here — if this pattern repeats elsewhere, it's a sep… — _promoted (see list); from 2026-09-20-export-level-light-field-duplication.md_
- **Re-reading the conclusions in `docs/plans/2026-06-01-ambient-light-default-and-warnings.md` and `docs/plans/2026-05-31-verify-the-moon-ambientlight-fix-landed-cleanly.md`.** Those were written while the mapping was inverted, so … — _promoted (see list); from 2026-09-20-engine-multi-directional-light-fix.md_
- **Fixing the condo's oversized texture.** It belongs to whoever owns the level; this plan reports the finding and checks the Android release build is not corrupted by it. — _promoted (see list); from 2026-10-01-condo-chromecast.md_
- **Stale face normals in the five existing deformers.** They move vertices but keep rest-pose face normals (`rendobj3.cc:286`), so culling and lighting lag the deformation. The fix changes their output, so it needs re-recorded gold… — _promoted (see list); from 2026-10-16-saltwater-seahorses.md_
- **Run the baseline build in the Blender container**, like the `aquarium_*` levels (`scripts/level-build.sh`). `build.py` is host-only today, so this work ran on the host as the Taskfile defines. — _promoted (see list); from 2026-10-31-baseline-utah-teapots.md_
- Distance-based level of detail at runtime. The ladder is for measuring, not for swapping meshes. — _promoted (see list); from 2026-10-31-baseline-utah-teapots.md_
- The other observations from cast1, unless a control built here fixes them as a side effect: the "(read only)" label without a padlock, six-decimal slider end labels, and the flattened multi-line Notes. — _promoted (see list); from 2026-11-01-field-presentations.md_
- The connected-phone browser form (`controller.html`), apart from path validation, which it gets from the engine. — _promoted (see list); from 2026-11-01-field-presentations.md_
- Validate condo camera touch controls on physical Android phones/tablets and confirm iPhone/iPad host bindings. [Plan](docs/plans/2026-09-25-condo-camera-controls.md) — _promoted (see list)_
- Redesign the shared Forth script loader around parser/compiler boundaries, including arbitrary defining/immediate-word layouts; separate from the focused comment fix. [Context](docs/plans/2026-09-25-forth-comments-and-script-loadi… — _promoted (see list)_
- Investigate transactional Forth hot-reload dictionary rollback and reclamation; preserving an actor entry alone does not undo changed definitions. [Context](docs/plans/2026-09-25-forth-comments-and-script-loading.md) — _promoted (see list)_
- Improve Forth diagnostics with source positions and token context across initial loading and hot reload. [Context](docs/plans/2026-09-25-forth-comments-and-script-loading.md) — _promoted (see list)_

