# WorldFoundry Project Status

**As of:** 2026-05-18  
**Branch:** `2026-new-level`

---

## History

37 days of work (2026-04-12 – 2026-05-18). Newest first:

- **Engine embed-readiness — Phase 0b done (2026-05-18)** — All four sub-tasks of the collaborative-editor engine refactor shipped same-day (vs ~3 wk estimate): [frame-step API](docs/plans/2026-05-18-engine-frame-step-api.md) (`WFGame::StepFrame` / `LoadLevel` / `UnloadLevel` / `Display::MeasureDelta` / 100 ms deltaTime clamp / `--frame-step-smoke` CLI), [external GL context](docs/plans/2026-05-18-engine-external-gl-context.md) (`gfx/host_gl_context.h` opaque interface, `InitWithExistingContext`, `HALCloseWindow`/`XEventLoop` early-bails, `HALRequestClose`), `HALInjectJoystickButtons` for editor-driven input, and de-globaling `WFGame* theGame` — editor work can now drop directly onto `libwfengine.a`.

- **SMB Mario movement retune + Jolt airborne sync fix (2026-05-18)** — Bumped Mario's ground tuning (Running Accel 16→40, Max Ground Speed 12→24), zeroed Air Acceleration so the joystick has no effect once airborne, dropped Jumping Acceleration 70→60 so a full-hold apex tops out at the `?`-block underside (no landing on top), added SMB-style variable jump (releasing `kBtnJump` mid-jump zeros remaining `jumpDuration` in `AirHandler::predictPosition`), and root-caused the wall/under-block "stuck Mario" bug to `jolt_backend.cc`'s airborne velCache only reconciling Y from displacement — all three axes now derive from actual displacement so contacts zero the blocked component and Mario can rapid-bump from below. See [plan](docs/plans/2026-05-18-smb-mario-movement-retune.md).

- **SMB `?`-block coin pop-out (2026-05-18)** — Added a third stacked actor at block 0 (`qblock_00_coin`, anchored yellow disc) plus a 60-tick Forth animation in Mario's per-tick script that arcs the coin Z up + down via `write-actor-mailbox` to its `INDEXOF_Z_POS` (qbert popup_500 pattern). Two new SMB GLOBAL_USER mailboxes (`SMB_QBLOCK_0_COIN_VISIBLE`, `SMB_QBLOCK_0_COIN_PHASE`) drive visibility + phase. No engine changes — pure level authoring + Forth. The full bump-to-coin loop is in place; bridge-test capture mid-arc is bounded by the engine throttle / screenshot round-trip time, so verify interactively for the smooth visible feel. See [plan](docs/plans/2026-05-18-smb-qblock-coin-pop.md).

- **Per-actor collision mailboxes landed (2026-05-18)** — Reopened the parked `?`-block bump plan after finding a much simpler path: the engine now writes the colliding actor's index + contact normal to four new per-actor `LOCAL_SYSTEM` mailboxes (`INDEXOF_COLLIDER_IDX` + `_NORMAL_X/Y/Z`) on every `Actor::Collision()` callback, with `Actor::StartFrame()` clearing the freshness signal each frame. Finishes wiring that was stubbed years ago (the `NUM_COLLISIONS = 4000` slot was already reserved). SMB W1-1 demos the visibility-mailbox half end-to-end (stacked `qblock_00` + `qblock_00_used` actors toggled by Mario's Forth script reading `INDEXOF_COLLIDER_IDX`). See [plan](docs/plans/2026-05-17-per-actor-collision-mailboxes.md); supersedes [parked plan](docs/plans/2026-05-17-smb-qblock-bump-parked.md).

- **SMB Mario jumps + walks at NES-Mario pace (2026-05-17)** — Added the missing `kBtnJump` → AirHandler trigger in `MarbleHandler::predictPosition` (doomstick actors had no jump path; `GroundHandler` had the branch, `MarbleHandler` did not), and bumped Mario's OAS speed/jump tuning (Max Ground Speed 6→12, Running Accel 8→16, Jumping Accel 20→70, Air Accel 10→16, Max Air Speed 6→12) so the jump apex reaches `?` block height (~6.3 m). See [plan](docs/plans/2026-05-17-smb-mario-speed-jump-tuning.md).

- **levcomp-rs actor-outside-room-bbox warning (2026-05-17)** — `levcomp-rs` now prints a per-actor `stderr` warning (name + world-unit center) when an actor's center falls outside every room bbox, preventing the silent-invisible-actor failure that hit the curse bubble on 2026-05-12; companion section added to [docs/level-design-troubleshooting.md](docs/level-design-troubleshooting.md). See [plan](docs/plans/2026-05-16-levcomp-actor-outside-bbox-warning.md).

- **Q✱bert arcade-faithful spawn sequencer landed (2026-05-16)** — Six independent per-enemy spawn timers replaced with a single shared countdown reading ROM-decoded 16-round × N-entry sequence tables; Slick and Sam now correctly appear in L1R3 as in the arcade. See [plan](docs/qbert/plans/2026-05-16-qbert-spawn-sequencer.md).

- **Q✱bert second Coily egg in L4 (2026-05-16)** — Arcade rounds 12–15 now spawn two simultaneous Coily eggs via an independent `COILY_MB_SPAWN_DELAY_2` timer gated by `ROUND_NUMBER ≥ 12`. See [plan](docs/qbert/plans/2026-05-16-qbert-second-coily-egg.md).

- **Q✱bert SFX pass complete (2026-05-16)** — Swear sound now plays at fall initiation (curse bubble frame) instead of 30 frames late; added to all six enemy-contact death sites; kill sound (cmd_13, slot 5) fires on Slick/Sam catch (+300) and Green Ball touch (+100); disc-rescue sound (cmd_18, slot 6) fires when Coily falls off a disc (+500). See [plan](docs/qbert/plans/2026-05-16-qbert-sfx.md).

- **Q✱bert 16-round end-to-end test complete (2026-05-16)** — `tests/test_director_mailbox.py` verifies all 88 checks: palette screenshots, cube-state cycle (1-hop L1/L3, 2-hop L2/L4), score increments (+25/+50), mid-round revert, and enemy-mix gating (RB/Coily always; GB/Slick/Sam L2+; Ugg/WW L3+; CE2 L4). See [plan](docs/plans/2026-05-16-qbert-16round-test.md).

- **Q✱bert popup mailbox collision fixed (2026-05-16)** — Popup system MBs 580–584 (added today) collided with CE2 egg internals (MBs 580–584, added commit 8e55799); in L4 both systems are active simultaneously. Moved popup range to 592–596; all L2/L3/L4 spot-checks pass (b26373f).

- **Q✱bert +50 and +500 popup labels landed (2026-05-16)** — Two missing floating score labels added: orange "+50" for the 2nd cube hop in L2/L4 (was incorrectly showing "+25"), and hot-magenta "+500" for Coily falling off a disc (was showing nothing). Both new popup actors are 3D text meshes with correct colours; `cbRoom` pool bumped to 1,800,000 to fit the extra mesh load. See [plan](docs/plans/2026-05-16-qbert-popup-50-500.md).

- **Q✱bert curse-bubble texture landed — textile-rs RGBA alpha-inversion + false-dedup root cause fixed (2026-05-16)** — `Room0.tga` was 146 bytes (empty atlas) because `rgba_555()` in textile-rs maps fully-opaque RGBA pixels to 0x0000 (transparent key), then `find_existing()` falsely deduplicates the all-zero texture against the all-zero atlas and skips the blit; fix is generating 24-bit RGB TGA (bypasses `rgba_555()` via `try_load_tga_bgr555()`), plus text colour bumped from (20,20,20) to (40,40,40) to avoid the BGR555 transparent key. See [plan](docs/plans/2026-05-16-curse-bubble-texture.md) and [investigation](docs/investigations/2026-05-16-textile-rs-rgba555-dedup-bug.md).

- **Q✱bert high-score persistence + game-over screen (2026-05-15)** — 23-entry binary high-score file seeded with arcade defaults, AAA initials picker on game-over, two-column overlay table, and `GO_BLOCK`/`GO_HOLD_TIMER` mailboxes enforcing a 3 s minimum hold (commit `8f2b6a1`).

- **Q✱bert Coily-falls-off-disc (2026-05-15)** — Snake tracks Q✱bert onto disc coordinates and retires with +500 score; verified via automated debug-bridge test (`1f4b272`). See [disc flash plan](docs/qbert/plans/2026-05-15-qbert-disc-flash-vfx.md).

- **Q✱bert disc rim flash VFX (2026-05-15)** — Yellow ring mesh pulses for 8 frames via visibility mailbox when Q✱bert boards a disc; automated disc-lure test added (`e04fb99`). See [plan](docs/qbert/plans/2026-05-15-qbert-disc-flash-vfx.md).

- **Q✱bert enemy coexistence rules (2026-05-15)** — No climber (Ugg/Wrong-Way) while Coily is active; no two simultaneous climbers; shared freeze timer pauses all spawns after each kill. See [plan](docs/qbert/plans/2026-05-15-qbert-enemy-coexistence.md).

- **SMB W1-1 movement direction fixed — `currentDir()` comment wrong, C=π/2 needed (2026-05-15)** — Player moved toward camera (−Y) when joystick-RIGHT was pressed. Root cause: `currentDir()` in `physicalobject.hpi:50` returns `(cos C, sin C, 0)`, not `(sin C, cos C, 0)` as the comment in `movement.cc:698` claims. With C=0, the player faces +X and StepRight = −Y (toward camera). Fixed by setting Player Euler C = π/2 (`rotation_euler.z = math.pi/2` in the Blender script), which gives `currentDir=(0,1,0)` (facing +Y into the scene) and StepRight = +X (screen-right). Full numeric chain traced through `Angle::Sin/Cos` → `Scalar::Sin/Cos` → `levcomp-rs radians_fx_to_u16_revs`. See [investigation](docs/investigations/2026-05-15-wf-coordinate-system-and-currentdir.md) and updated `CLAUDE.md`.

- **WF graceful-degrade under Jolt pool exhaustion — investigation closed, already works (2026-05-10)** — Three reruns confirmed the marble parks cleanly when its floor body is lost. WF's existing `_joltBodyID` guards cover the degraded mode end-to-end; no fix needed.

- **Jolt body-pool exhaustion now fails loudly instead of segfaulting (2026-05-10)** — Every `CreateAndAddBody` wrapper now checks `IsInvalid()` and logs a pool-exhausted message instead of registering a bogus handle. Guards added in `JoltBodyDestroy` and `JoltBackendShutdown` cover the `RemoveBody` path too.

- **Q✱bert per-round cube palettes — full 16 arcade rounds (2026-05-09)** — All 16 arcade rounds now have correct per-round colors, pixel-sampled from MAME captures. Engine budgets bumped to fit the 1344-actor pyramid.

- **Q✱bert walker WF-side parity scaffolding landed (2026-05-09)** — All four Phase E pieces are in place: PNG encoding, a `screenshot` debug-bridge op, CAPTURE_TRIGGER writes in the autopilot dance, and a host harness mirroring the MAME-side walker. End-to-end run still pending.

- **Room::~Room double-free root cause + fix (2026-05-04, unverified)** — `Room::~Room` was calling `delete[]` on WF-pool memory; fix replaces it with `MEMORY_DELETE_ARRAY`. Verification was interrupted before completing.

- **ESC-key migrated to close-requested flag (2026-05-04)** — `XK_Escape` now writes `_closeRequested` instead of calling `sys_exit(0)`, taking the same clean shutdown path as the WM close button.

- **X-close button reliability fix landed (2026-05-04)** — Mid-event `sys_exit(0)` replaced with a polled `_closeRequested` atomic so X-close goes through the full clean shutdown path. Verified with WM_DELETE_WINDOW.

- **Debug-bridge Phase B2 — `reload_script` zForth hot-swap landed (2026-05-03)** — zForth scripts can be compiled and hot-swapped at runtime; `common.Script set_prop` now hard-errors directing callers to `reload_script`. Full bridge suite 10/10 in 17 s.

- **Debug-bridge Phase B1 — `set_shader` GLSL hot-reload landed (2026-05-03)** — GLSL shaders can be hot-reloaded via the bridge; broken GLSL is reported as a structured error while the prior shader stays live.

- **Debug-bridge Phase A — `set_mailbox` + `inject_input` landed (2026-05-03)** — Bridge can write any mailbox and override joystick inputs ahead of the live HID. pytest harness exercises both ops end-to-end against qbert_practice headless.

- **marble-madness faithful replication plan + M1 camera done (2026-05-01)** — Plan covers M1–M5+ against the wf-games design docs. M1 landed: camera placed at canonical 45°/30° and Player Rotation C = π/4 for correct UP+LEFT / DOWN+LEFT world-axis alignment.

- **marble-madness-2 game loop wired: 90-second timer + goal detection (2026-04-30)** — Director script runs a 90-second countdown; player script fires END_OF_LEVEL when the marble reaches the Mm1Goal platform position.

- **Marble rolls down ramp — physics working end-to-end (2026-04-30)** — Root cause was `MaxAirSpeed=0` zeroing all velocity (including gravity) every frame. Fixed by bumping MaxAirSpeed, zeroing HorizAirDrag, and widening mMaxSlopeAngle to 80°.

- **"Run in Engine" Blender operator (2026-04-29)** — One-click export + compile + launch from Properties > Scene. Blender stays open while the game runs.

- **wf_asset_provider: pure-Python rewrite (2026-04-28, unverified)** — `providers.py` + `wf_asset.py` replace the PyO3 Rust extension on disk, but whether the addon runs without the native extension is unverified.

- **wf_asset_provider: Sketchfab provider + licence-filter UI v2 (2026-04-28)** — Sketchfab added alongside Poly Haven; downloads blocked when the asset's licence policy is forbidden.

- **wf_asset_provider: Rust crate + Blender asset browser plugin v1 (2026-04-28)** — Initial asset browser with Poly Haven CC0 provider, licence-policy filter, thumbnails, and one-click import to scene.

- **iOS port Phase 2B3 verified — Metal RendererBackend compiles and links (2026-04-22)** — `backend_metal.mm` implements the RendererBackend vtable with inline MSL shaders. Nothing drives it yet; sim still shows cornflower blue.

- **iOS port Phase 2B2 verified — full engine links on iOS (2026-04-22)** — All ~120 engine sources compile and link for arm64 iOS Simulator; `wf_game.app` boots and shows cornflower blue.

- **iOS port Phase 2A verified — Metal is alive on Sim (2026-04-22)** — `WFMetalView` with `CAMetalLayer` + `CADisplayLink` confirmed rendering cornflower blue on the Simulator.

- **iOS port Phase 1 verified end-to-end (2026-04-22)** — Codemagic builds and boots `wf_game.app` on iPhone 17 Pro Sim, confirming `cd.iff` opens successfully with no user Mac required.

- **iOS port Phase 1 build green (2026-04-22)** — `wf_game.app` for iOS Simulator arm64 compiles and links under Apple clang with `cd.iff` + `level0.mid` bundled.

- **iOS port Phase 0 complete (2026-04-21)** — Codemagic cloud-Mac pipeline is green on `2026-ios`. Xcode build reaches per-source compilation and stops at the expected iOS HAL gap.

- **Snowgoons renders fully via textile-rs + levcomp-rs pipeline (2026-04-19)** — Two regressions fixed: textile-rs TGA translucency sentinel blanking the roof texture, and levcomp-rs over-eager STR preference removing both directional lights. Shadows and textured roof restored.

- **levcomp-rs LVL diff down to 5 bytes (2026-04-19)** — Prepending `\n` to the player-script source dropped the delta from 83 → 5 bytes. Remaining 5 are unpredictable heap-garbage pads.

- **textile-rs wired into snowgoons.iff.txt (2026-04-19)** — Oracle-extracted binary stopgaps replaced with explicit asset slots in the text-IFF. 24-bit TGA fast-path fixed an invisible-roof renderer bug.

- **levcomp-rs LVL diff down 97% to 83 bytes (2026-04-19)** — Three commits reduced the delta from 2,772 → 83 bytes via two-phase common-block emission, an OAD enum-label fix, and an Actboxor chunk-order swap.

- **OAD ButtonType audit written (2026-04-19)** — All 29 ButtonType variants cross-referenced against iff2lvl; three emission bugs found (one landed), 21 types already aligned.

- **levcomp-rs two-phase common-block refactor landed (2026-04-19)** — Pass-1/Pass-2 refactor brings LVL payload to byte-identical length (8628/8628). Total diff dropped from 2,772 → 141 bytes.

- **levcomp-rs common-block two-phase plan written (2026-04-19)** — Phase-ordering mismatch between levcomp-rs and iff2lvl traced and documented. Fix estimated at ~half-day.

- **textile-rs validation plan written (2026-04-19)** — Rust port exists but has no tests. Plan lays out a snowgoons validation harness and oracle byte-identity verification.

- **python-tui-lib extracted + embedded markdown help in git-branch-browser (2026-04-19)** — TUI library extracted from parking-space, vendored into WorldFoundry. `?` in git-branch-browser now opens rendered help.

- **`snowgoons.iff.txt` round-trips byte-identical (2026-04-19)** — iffcomp-rs now produces md5-identical output to the oracle, serving as a byte-drift regression anchor for future tool changes.

- **git-branch-browser v2 shipped (2026-04-19)** — Curses TUI renders branch topology as a chronological waypoint pipeline with strata bars, fork detection, and three diff modes.

- **Blender round-trip plays continuously, untextured (2026-04-19)** — Nine exporter/compiler fixes take `snowgoons-blender.iff` through a continuous per-frame loop with audio and camera and no assertions.

- **Android port closure (2026-04-18)** — Branch hits its close criterion with a polished sideloadable APK. Only launcher icons and a stale comment remain.

- **Android audio — Für Elise on snowgoons (2026-04-18)** — Desktop miniaudio + TinySoundFont ported to Android via `HALGetAssetAccessor()` memory loader.

- **Android post-boot polish (2026-04-18)** — Correct viewport aspect, pause/resume, zForth bootstrap fix, and on-screen d-pad landed. Snowgoons is fully playable on stock arm64.

- **Snowgoons rendering on Android phone (2026-04-18)** — Phase 3 step 7 ✅: sideloaded debug APK boots snowgoons on physical arm64 via `NativeActivity` + EGL 3.0 + `AAssetManager`-backed `cd.iff`, unblocked by four pre-flight fixes (Forth shell bootstrap, graceful missing-engine no-op, 4096² framebuffer cap, GLSL ES `int` precision) and on-device `wf.log` since `adb logcat` wasn't reachable.

- **Snowgoons joystick control restored (2026-04-17)** — On-disk `snowgoons.iff`/`cd.iff` still had the pre-`671de1e` `?cam`-helper director that zForth's minimal bootstrap couldn't compile; byte-preserving re-patch (`a7ef46e`) landed the inlined three-block form the current `patch_snowgoons_forth.py` produces.

- **Window-close shutdown stability (2026-04-17)** — `mesa.cc` now handles `WM_DELETE_WINDOW` and `rest_api.cc` registers `RestApi_Stop` via `sys_atexit`; X11 close button exits cleanly instead of aborting.

- **Graphics — retire immediate-mode GL / Android Phase 0 (2026-04-18, complete)** — Modern VBO + GLSL 330 / GLES 300 es shader backend is the sole GL path on Linux and Android (legacy fixed-function retired at `ff589c8`, **−541 LOC** net across 16 files; tag `pre-legacy-gl-retire` at `807d1ea` preserves the last `backend_legacy.cc` commit).

- **Audio (Phases 1–5 complete) (2026-04-17)** — miniaudio + TinySoundFont vendored with per-level `level<N>.mid` music, fire-and-forget SFX, and 3D positional playback audible in snowgoons, but only via `scripting_lua.cc` closures — mailbox-wired audio API for the other seven engines is deferred.

- **Android port (Phases 0+1+2 complete; Phase 3 steps 1–6 done) (2026-04-18)** — Phase 0 retired legacy GL, Phases 1+2 landed CMake+NDK build / HAL lifecycle seam / AssetAccessor, and Phase 3 added `NativeActivity` + EGL 3.0, a Gradle project (AGP 8.5.2, leanback manifest, arm64-v8a, min 21 / target 34), gamepad + touch with TV-mode detection, and `AAssetManager`-backed `cd.iff` — only step 7 (device smoke test) remained at the time, since closed.

- **Blender ↔ level round-trip (2026-04-17)** — `levcomp-rs` compiles `.lev` → `.lvl` end-to-end and the Blender plugin round-trips 152/152 OAD fields with Phase 2c mesh bboxes / packed asset IDs / `asset.inc` landed — real path/channel keyframes are the last remaining piece.

- **Level pipeline proof (2026-04-17, in progress)** — Phases A+B+C done (`primitives.lev`/`whitestar.lev` compile through the pipeline; `wf_oad` has a `common.oad` fixture test; `levcomp decompile` round-trips snowgoons' 36 objects with an 8-byte common-block delta), with D–E (decompile 4 source-less levels, multi-level `cd.iff`) gating the `common.inc` rearrangement the deferred ScriptLanguage OAD plan needs.

- **Tooling and plans (2026-04-17)** — `engine/` reorganised to top-level; REST API box PoC landed; iOS plan written (blocked on Android); CLI level override (`-L<path>`) confirmed; IFF lineage + MIDI-source investigations filed.

- **Scripting system (2026-04-16)** — Seven engines smoke-tested end-to-end in snowgoons (Lua 5.4, Fennel, QuickJS, JerryScript, WAMR, Wren, zForth) with Lua optional (`WF_LUA_ENGINE=lua54|none`) and wasm3 retired in favour of WAMR — five alternate Forth backends build+link but aren't end-to-end tested, WAMR AOT deferred.

- **Dead-code removal (2026-04-15, closed 2026-04-18)** — Batches 1–7 complete (`wfsource/source/` 64,252 → 36,199 lines, −43.7%) with Batch 8 (`physics/wf/`, ~1,700 LOC) deferred until Jolt parity on a second level and `hal/_list` / `_mempool` migration left as future opt-in.

- **Jolt Physics (2026-04-14)** — Integrated as default (`WF_PHYSICS_ENGINE=jolt`) with the five-step plan complete (SIGABRT, zombie bodies, authority model, vertical pop, 60 s soak); legacy `physics/wf/` retained until parity on a second level.

- **Steam (Phases 1+2) (2026-04-12)** — Steamworks SDK lifecycle wired into HAL + `PageFlip` with Steam Input ORing into `_JoystickButtonsF` each frame (`WF_ENABLE_STEAM=1`; SDK not committed); Phases 3 (depot) and 4 (store page) deferred.

---

## Plans

### Active

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-04-29 | [Plan: Live Editor Bridge](docs/plans/2026-04-29-live-editor-bridge.md) | **Not started** | Bidirectional network bridge between Blender and `wf_game`: Blender sends incremental scene diffs over a TCP socket; engine applies them without restart. Phase 1: one-way push (transform + property changes → live engine update). Phase 2: engine → Blender feedback (physics state, collision events). Closes the iteration-loop gap that "Run in Engine" doesn't (build+relaunch vs. sub-second live update). |
| 2026-04-28 | [Plan: Blender addon packaging](docs/plans/2026-04-28-blender-addon-packaging.md) | **Not started** | Add `blender_manifest.toml` (required by Blender 4.2+ extension system), fix `install.sh` to include `asset_browser.py` + `asset_threading.py`, add `task` commands for building and packaging the addon. Rewrite `docs/wf-asset-browser.md` to frame the tool around provenance capture rather than WF-commercial defaults. |
| 2026-04-28 | [Plan: game-ideas dependency graph and tooling](docs/plans/2026-04-28-game-ideas-dependency-graph-and-tooling.md) | **Not started** | Mermaid dependency graph + table across all 32 `docs/game-ideas/` conversion briefs; idealised implementation order (waves / parallel tracks); tooling brainstorm (skills, Blender plugins, pluggable-LLM ideas). |
| 2026-04-16 | [Plan: Blender ↔ Level Round-Trip](docs/plans/2026-04-16-blender-level-roundtrip.md) | **In progress — step 6 🟡 (plays, untextured)** | Steps 1–5 complete.  2026-04-19 (`c1550f7` et al.): nine exporter/compiler fixes took `snowgoons-blender.iff` from "asserts at frame 0" to "runs continuously with audio + camera, no assertions" — notably real path+channel serialization, the oadFlags MovesBetweenRooms bit, and the `_RoomOnDisk` 36-byte struct-alignment padding.  Remaining oracle dependencies (texture atlases, MeshName asset-ID packing, etc.) are a separate plan. |
| 2026-04-19 | [Plan: Blender round-trip — oracle dependencies](docs/plans/2026-04-19-blender-roundtrip-oracle-dependencies.md) | **Done** | `build_level_binary.sh snowgoons-blender` produces a fully working `.iff` via iffcomp-rs → levcomp-rs → textile-rs with no oracle bytes reused; `swap_lvl.py` deleted. 1687-byte diff against oracle, all known-OK deltas (Actboxor reorder, mesh-size drift, base.rot heap-garbage, NULL_Object sentinel). Textures render correctly in game. Deferred deviations (a–f) gated on script-language-OAD-field plan. |
| 2026-04-19 | [Plan: textile-rs validation & round-trip integration](docs/plans/2026-04-19-textile-rs-validation.md) | **Phase 1 done — end-to-end pipeline working** | Seven fixes landed: 16-bit BGR555 TGA fast path (`f3da913`); 24-bit TGA fast path matching C++ `BR_COLOUR_BGRA` — also fixes invisible-roof renderer bug (`11cbca7`); `align_to_size_multiple` unit mismatch that made `-alignx=w -aligny=h` always fail (`a45194c`); `paly=-1` for 16-bit textures matching C++'s unconditional division (`72a4af9`); levcomp-rs `--textile-ini` flag replicating `prep ini.prp` (`a45194c`); per-asset ASS expansion in `lvas_writer` replacing `[ "perm.bin" ]` placeholder with individual `{ 'ASS' $<id>l [ "file" ] }` includes per iff.prp semantics (`a45194c`); textile-rs output files replace the oracle-extracted `.bin` placeholders (`edaffb3`). PERM chunk byte-identical (29492/29492); RM1 atlas content 31/31 textures byte-identical per-texture extraction. Game runs with textile-rs outputs + levcomp-rs `.lvl`, House roof + directional shadows all rendering correctly. |
| 2026-04-19 | [Plan: levcomp-rs two-phase common-block emission](docs/plans/2026-04-19-levcomp-common-block-two-phase.md) | **Phase A + follow-ups done — 3 heap-pad bytes remain (99.9% closed, content-diff zero)** | Five commits land the refactor plus four follow-up fixes: (a) `8e2f244` — two-phase emission + `_ObjectOnDisk` heap-garbage type/rot pads (141 diffs); (b) `21ca707` — audit-fix 1, `field_str_child_only` accessor for I32 enum-label lookup (134 diffs; closed CamShot `Rotation`/`Position X/Y/Z` per obj[12]/obj[35]); (c) `0a37e20` — Actboxor01/02 OBJ-chunk swap in the `.lev` (83 diffs); (d) `88b9df7` — prepend `\n` to joystick-input `Script` STR in `snowgoons.lev` to match oracle byte-for-byte (5 diffs); (e) `4c3e652` — gate I32 STR-lookup on `ShowAs ∈ {DROPMENU, RADIOBUTTONS}` per iff2lvl's `oad.cc:1245-1276` (3 diffs; also the fix that restored directional lighting in-game — `21ca707`'s too-eager heuristic had demoted Omni01/Omni02 to AMBIENT). Remaining 3 bytes are all uninitialized `_RoomOnDisk` pad from iff2lvl's `new char[]` allocator (Room 0 trailing pad + Room 1 struct-alignment pad) — same `new char[size]` family as the `_PathOnDisk.base.rot` Euler garbage; no deterministic mirror rule possible. Content-diff is effectively zero; structural identity achieved. |
| 2026-04-17 | [Plan: Prove all 7 level pipelines before breaking common.inc](docs/plans/2026-04-17-level-pipeline-proof.md) | **In progress — Phases A+B done** | Phase A (`534ead7`): `primitives.lev` + `whitestar.lev` compile through `iffcomp-rs` → `levcomp-rs` (skips OBJ chunks with no Class Name — Max aim-point helpers). Phase B: `wf_oad/tests/fixtures/common.oad` committed; `parse_common_oad` test asserts 14 entries + `Script` field; 6 tests pass. Phases C (decompile subcommand), D (4 source-less levels), E (multi-level `cd.iff`) remaining before the gated common.inc rearrangement that unblocks the ScriptLanguage OAD plan. |
| 2026-04-21 | [Plan: iOS port (via Codemagic)](docs/plans/2026-04-21-ios-port-codemagic.md) | **Phase 2A verified — Metal alive on Sim** | `WFMetalView` hosts a `CAMetalLayer` as root view; `CADisplayLink` ticks a clear-to-color render pass each frame. Sim-verify screenshot is solid cornflower blue — real Metal present-drawable loop. `MTLDevice`="Apple iOS simulator GPU" @3x. 14 commits total. Phase 2B next: port GLSL→MSL, implement `RendererBackend` subclass with vertex batching, pull `gfx/` + `game/` into iOS build, first snowgoons triangle. |

### Backlog

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-04-18 | [Plan: Android launcher polish — adaptive-icon XML](docs/plans/2026-04-18-android-launcher-polish.md) | **Not started** | **Goal:** Layer `res/mipmap-anydpi-v26/ic_launcher.xml` adaptive-icon XML on top of the legacy mipmap PNGs that just landed, so Android 8+ renders rounded / themed / dynamic-shape forms via foreground + background drawables. Carry-over from the Android port closure audit. |
| 2026-04-18 | [Plan: audio assets from iff](docs/plans/2026-04-18-audio-assets-from-iff.md) | **Not started** | **Goal:** retire every filesystem / loose-file audio loader — MIDI, soundfont, SFX all come through `cd.iff` / `level<N>.iff` chunks like meshes and textures already do. Current `loadAssetBytes(path)` path stays behind a `-DWF_AUDIO_DEV_LOOSE_FILES=1` opt-in for iteration. Requires new IFF chunk tags (MIDI/SFNT/SFX) + `iffcomp-rs` + `levcomp-rs` + Blender plugin updates. Unblocks the iOS port from needing its own asset-bundling pipeline. |
| 2026-04-17 | [Plan: Steam release](docs/plans/2026-04-17-steam.md) | **In progress — Phases 1+2 done** | Steamworks SDK lifecycle wired into HAL + PageFlip. Steam Input → `EJ_BUTTONF_*` merged in `_JoystickButtonsF`. `WF_ENABLE_STEAM=1` build flag; SDK not committed (see vendor README). Phases 3 (depot) and 4 (store page) deferred. |
| 2026-04-17 | [Plan: Mailbox-wired audio API](docs/plans/deferred/2026-04-17-audio-mailbox-api.md) | **Not started** | **Goal:** Every scripting engine can trigger music + SFX via mailbox writes. `EMAILBOX_SOUND=3017` enum and OAD `sfx0..sfx127` asset slots still exist; handler + slot loader were deleted in the `460a3fd` dead-code sweep (pre-cleanup impl was Linux-stubbed). Phase A: restore `_sfx[128]` loader + `EMAILBOX_SOUND` handler that plays at the actor's position. Phase B: `MUSIC_PLAY`/`MUSIC_STOP`/`MUSIC_VOLUME` mailboxes; Lua closures become forwarders. Phase C (opt): named `SFX_*` constants. |
| 2026-04-16 | [ScriptLanguage OAD field](docs/plans/2026-04-16-script-language-oad-field.md) | **Deferred — blocked on Blender+levcomp-rs level round-trip** | Field added then reverted from `common.oad` to restore binary layout compat with existing compiled levels. Dispatch table + language param threading remain in engine (passing 0=Lua). Will re-introduce once all levels compile through Blender+levcomp-rs. |

### Complete

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-05-18 | [Plan: Engine frame-step API](docs/plans/2026-05-18-engine-frame-step-api.md) | **Done 2026-05-18** | Phase 0b sub-task #1. `WFGame::RunLevel`'s `while` body extracted into `WFGame::StepFrame(do_swap, out_dt)` returning a `FrameResult` enum; per-level setup/teardown into `LoadLevel`/`UnloadLevel`; `Display::MeasureDelta` factored out of `PageFlip` so host-swap callers still recover deltaTime; ≤100 ms `_deltaTime` clamp keeps the sim stable across host stalls; `LevelDone()`/`ContinueRequested()` accessors for caller-owned loop predicates; `--frame-step-smoke=N` CLI drives the new entry points from a non-`RunLevel` path. Single afternoon vs ~1–2 wk estimate. Commits `8663618`, `d6bc566`, `aa65b79`, `0be94a5`, `c844f4a`, `47ef7cc`. |
| 2026-05-18 | [Plan: Engine external GL context](docs/plans/2026-05-18-engine-external-gl-context.md) | **Done 2026-05-18** | Phase 0b sub-task #2. `gfx/host_gl_context.h` opaque (void*) interface lets an editor host register its own `XDisplay*` / `Window` / `GLXContext`; `mesa.cc:InitWindow` dispatches on `GetHostGLContext().valid` to either `OpenMainWindow` (standalone) or new `InitWithExistingContext` (host-owned); `HALCloseWindow` + `XEventLoop` early-bail in host-owned mode; `HALRequestClose()` lets the host trigger the existing close-flag path. Linux-only for v1; iOS / Android stub. Single afternoon vs ~1 wk estimate. Commits `151e2fe`, `2193f77`, `50807a9`, `a68b119`, `3f80c58`, `a816e3b`. |
| 2026-05-10 | [Jolt pool exhaustion degraded-mode follow-up](docs/plans/2026-05-10-jolt-pool-exhaustion-degraded-mode.md) | **Done 2026-05-10** | Investigation closed: yesterday's one-off `terminate` did not reproduce (3 reruns + 30 s `gdb catch throw` all clean). WF's existing `_joltBodyID != kJoltInvalidBodyID` guards in [physical.hpi](wfsource/source/physics/physical.hpi) (lines 199, 213, 231, 248, 253) plus yesterday's wrapper-layer guards already deliver degraded mode — actors that lost their body simply have no collision; engine continues. No code change. |
| 2026-05-10 | [Jolt body-pool exhaustion guard](docs/plans/2026-05-10-jolt-body-pool-exhaustion-guard.md) | **Done 2026-05-10** | All 3 wrappers around `CreateAndAddBody` check `IsInvalid()` and log `jolt: body pool exhausted (max=N); returning kJoltInvalidBodyID for <wrapper>` instead of registering a bogus handle; `JoltBodyDestroy` and `JoltBackendShutdown` skip `RemoveBody`/`DestroyBody` on invalid IDs (was the segfault path); pool size lifted to file-scope `kJoltBodyPoolMax=1024` so log stays in sync. Verified happy-path snowgoons clean, force-exhaustion test (pool=8) emits log + no segfault. WF actor-layer graceful-degrade is a follow-up. |
| 2026-04-29 | [Plan: "Run in Engine" Blender operator](docs/plans/2026-04-29-blender-run-operator.md) | **Closed 2026-04-29** | `WF_OT_run_level` implemented in `wftools/wf_blender/`. `export_scene_to_lev()` extracted from export operator; operator runs export → `build_level_binary.sh` → detached `wf_game`. Level name scene property + repo-root addon pref. |
| 2026-04-28 | [Plan: marble-madness player sphere + rolling physics](docs/plans/2026-04-28-marble-player-sphere.md) | **Complete 2026-04-30** | Player mesh replaced with `sphere.iff` (UV sphere, radius 0.5); `MarbleHandler` drives gravity-based slope rolling via Jolt `CharacterVirtual`; OAD `MaxAirSpeed=50` fix lets marble fall through `AirHandler` onto the ramp; marble accelerates to 9.9 m/s on the 45° test ramp. |
| 2026-04-28 | [Plan: wf_asset_provider pure Python](docs/plans/2026-04-28-wf-asset-provider-pure-python.md) | **Status unknown** | `providers.py` and `wf_asset.py` exist on disk and a commit claims this was done, but plan has no completion marker and the Rust crate still exists. Needs verification. |
| 2026-04-28 | [Plan: Blender asset browser plugin](docs/plans/2026-04-28-blender-asset-browser-plugin.md) | **Closed 2026-04-28** | v1 (Poly Haven CC0) → v2 (+ Sketchfab, licence-filter UI) → pure-Python rewrite all landed. Asset browser sidebar with thumbnail previews, policy enforcement, `manifest.json` provenance. |
| 2026-04-19 | [Plan: python-tui-lib extraction](docs/plans/2026-04-19-python-tui-lib-extraction.md) | **Closed 2026-04-19** | **Goal:** carve the reusable TUI subset out of parking-space into a standalone `python-tui-lib` repo and consume it from WorldFoundry. Four phases all landed same-day: tuilib repo stood up at `/home/will/python-tui-lib` (~27K LOC, 68 .py files, commits `2695044` / `1942141` / `82764dd`), imports rewritten to `tuilib.*`, `parkingspace`-hardcoded paths parameterized via `tuilib.APP_NAME`, and WorldFoundry's `git-branch-browser.py` submodules it at `vendor/python-tui-lib/` with a `?`-key help overlay rendered by `DocViewer` (commit `f75e7c7`). Follow-on plans 2/3/4 (parking-space migration, logs.py + LogSource, worker-pool) remain separate. |
| 2026-04-16 | [Plan: git-branch-browser — curses TUI for browsing a branch pipeline](docs/plans/2026-04-16-git-branch-browser.md) | **Closed 2026-04-19** | **Goal:** A Python curses program at `scripts/git-branch-browser.py` that surfaces branch topology as a chronological waypoint pipeline with strata bars, sideways-fork detection, and three diff modes (vs parent, vs master, compare). v2 (~1260 LOC) shipped 2026-04-19; clean Ctrl+C handling in main loop, diff pager, and compare view verified under a pty. |
| 2026-04-16 | [Plan: Android port](docs/plans/2026-04-16-android-port.md) | **Closed 2026-04-18** | Phases 0+1+2 + Phase 3 steps 1–7 all landed: legacy GL retired (`ff589c8`, `pre-legacy-gl-retire` tag at `807d1ea`), CMake+NDK build, HAL lifecycle seam, AssetAccessor, `NativeActivity` + EGL 3.0, Gradle project (AGP 8.5.2, leanback, arm64-v8a, min 21 / target 34), gamepad + touch with TV-mode detection, `AAssetManager`-backed `cd.iff`, on-device smoke test on arm64 phone. Post-boot polish shipped (viewport aspect, pause/resume EGL preservation, zForth `here` director fix, on-screen touch HUD). Remaining polish tracked as separate plans: [android-launcher-polish](docs/plans/2026-04-18-android-launcher-polish.md) and [audio-assets-from-iff](docs/plans/2026-04-18-audio-assets-from-iff.md). |
| 2026-04-15 | [Dead-code removal](docs/plans/2026-04-15-dead-code-removal.md) | **Closed 2026-04-18** | Batches 1–7 landed (64,252 → 36,199 LOC, −43.7%). LOC claims verified against git history — Batch 5 `03211f9` shows −20,967 across 208 files; `e2dcc98` milestone records the 36,199 total. Batch 8 (`physics/wf/` deletion, ~1,700 LOC) + `hal/_list`/`_mempool` migration (stretch) accepted at their estimates, deferred to future opportunistic commits. |
| 2026-04-16 | [Plan: Lua engine is not special — make it optional](docs/plans/2026-04-16-lua-not-special.md) | **Done** | `scripting_lua.cc/hp` extracted; `WF_LUA_ENGINE=lua54\|none` added to `build_game.sh`; all `lua_engine::` calls guarded; Fennel+none warns and forces lua54; stale `scripting_wasm3.hp` include removed. |
| 2026-04-16 | [Engine directory reorganization](docs/plans/2026-04-16-engine-directory-reorganization.md) | **Complete** | `engine/` is now a top-level directory. `wftools/wf_engine/` → `engine/`, `wftools/vendor/` → `engine/vendor/`, `wf_viewer/stubs/` → `engine/stubs/`, `wf_viewer/include/` → `engine/include/`. `wftools/` is now strictly dev tooling. |
| 2026-04-16 | [Finish Jolt physics integration](docs/plans/2026-04-16-jolt-physics-finish.md) | **Complete** | Five-step plan: fix SIGABRT (`JoltSyncFromCharacter`), eliminate zombie kinematic bodies, lock WF↔Jolt authority model, fix 3 m vertical pop (feet vs centre offset), 60 s soak. Player walks on snowgoons floor. |
| 2026-04-15 | [Lua engine fixes (#1–#6)](docs/plans/2026-04-15-lua-engine-fixes.md) | **Complete** | All 6 fixes: script cache, per-actor envs, Fennel precompile, debug gating, stdlib sandbox, coroutine continuations. Smoke-tested 2026-04-16. |
| 2026-04-15 | [Align scripting plans to ScriptRouter](docs/plans/2026-04-15-scripting-plans-align-scriptrouter.md) | **Complete** | Phases A–E complete: all plan docs updated, JS/wasm3 renamed to `js_engine`/`wasm3_engine` namespaces, WAMR/Wren/Forth landed. All engine smoke tests passed 2026-04-16. |
| 2026-04-14 | [WAMR (dev interp + AOT ship)](docs/plans/2026-04-14-wamr-dev-aot-ship.md) | **Complete** | Phase 1 (classic interpreter) landed 2026-04-15; smoke-tested 2026-04-16 (GROUND, no crashes). Phase 2 (AOT) and Phase 3 (w2c2) deferred until ship targets are concrete. |
| 2026-04-14 | [Forth scripting engine](docs/plans/2026-04-14-forth-scripting-engine.md) | **Complete** | All seven phases landed 2026-04-16. All six backends build and link; snowgoons.iff + cd.iff carry Forth scripts (`\ wf` sigil) via byte-preserving patcher. zForth is the default and smoke-tested; the five alternates (ficl, atlast, embed, libforth, pforth) are build-verified but not yet end-to-end smoke-tested. |
| 2026-04-14 | [Pluggable JS engines (QuickJS / JerryScript)](docs/plans/2026-04-14-pluggable-scripting-engine.md) | **Complete** | Both engines landed 2026-04-14 with `js_engine` namespace. QuickJS and JerryScript both smoke-tested 2026-04-16 (snowgoons passes). |
| 2026-04-14 | [Wren scripting engine](docs/plans/2026-04-14-wren-scripting-engine.md) | **Complete** | All phases complete: vendor, plug, dispatch, build, docs, patcher. Smoke-tested 2026-04-16 (GROUND, no crashes). |
| 2026-04-14 | [WebAssembly (wasm3)](docs/plans/2026-04-14-wasm3-scripting-engine.md) | **Retired 2026-04-16** | Initial wasm spike. WAMR reached parity; `engine/vendor/wasm3-v0.5.0/` + `scripting_wasm3.{hp,cc}` deleted. `WF_WASM_ENGINE=wamr` is now the only wasm option. |
| 2026-04-14 | [Fennel on Lua](docs/plans/2026-04-14-fennel-on-lua.md) | **Complete** | Landed 2026-04-14. `;` sigil, sub-dispatch inside `lua_engine`, vendored Fennel 1.6.1, minifier, codegen, snowgoons Fennel scripts. |
| 2026-04-14 | [Vendor Lua 5.4](docs/plans/2026-04-14-vendor-lua.md) | **Complete** | Landed 2026-04-14. Lua 5.4.8 in `engine/vendor/lua-5.4.8/`, compiled directly from source, no system `liblua5.4` dependency. |
| 2026-04-13 | [Lua interpreter spike](docs/plans/2026-04-13-lua-interpreter-spike.md) | **Complete** | Landed 2026-04-13; refactored 2026-04-15 to `lua_engine` namespace in `ScriptRouter`. Snowgoons player + director ported to Lua; player moves, cameras cut. |

---

## Investigations

| Date | Investigation | Status | Summary |
|------|---------------|--------|---------|
| 2026-05-15 | [Investigation: WF coordinate system, Euler angles, and `currentDir()`](docs/investigations/2026-05-15-wf-coordinate-system-and-currentdir.md) | **Complete** | `currentDir()` returns `(cos C, sin C, 0)`, not `(sin C, cos C, 0)` as the comment claims. Full chain traced: `.lev` radian → `levcomp-rs` `u16` revolution fraction → `Angle::Sin/Cos` → `Scalar::Sin/Cos` (multiplies by 2π). With C=0 the player faces +X and StepRight = −Y (toward camera). Fix: C=π/2 → faces +Y, StepRight=+X. Side-scroller recipe documented. |
| 2026-04-29 | [Investigation: Blender Game Engine removal — history, gap, and WF's fit](docs/investigations/2026-04-29-blender-game-engine-removal.md) | **Complete** | History of BGE removal (2018, 916 files, Dalai Felinto), what filled the gap (UPBGE, Armory3D, Godot), why the Godot recommendation missed the point (integration was the product, not the renderer), WF's position in that space. "Run in Engine" operator noted as implemented; live-reload gap documented. |
| 2026-04-29 | [Investigation: World Foundry vs. Godot — technical comparison](docs/investigations/2026-04-29-world-foundry-vs-godot.md) | **Complete** | Technical snapshot: renderer, physics (Jolt vs Godot Physics/Jolt), scripting (multi-engine vs GDScript/C#), tooling, world model, audio, networking, platforms, asset pipeline, licensing. |
| 2026-04-29 | [Investigation: WF camera system — projection type, FOV, CamShot, Director](docs/investigations/2026-04-29-camera-system-audit.md) | **Complete** | Whether forced-perspective / isometric camera is possible without an ortho projection. Conclusion: perspective only today; `Mat4Ortho` path is ~½ day work, gated on Phase E OAD schema change. Feeds orthographic projection TODO. |
| 2026-04-29 | [Investigation: World Foundry camera system](docs/investigations/2026-04-29-camera-system.md) | **Complete** | Comprehensive anatomy of `movecam.cc` / `camshot.cc` / `camera.cc` / `actboxor.cc` — how CamShot keyframes drive cuts, transitions, and follow modes; how Director sequences them; how ActBoxor triggers room-transitions. Reference for camera scripting and the live-editor bridge. |
| 2026-04-29 | [Investigation: Forth compile vs. run separation](docs/investigations/2026-04-29-forth-compile-run-audit.md) | **Complete** | Compile/run separation correctly handled in `scripting_zforth.cc`: `RunScript` splits at last `;`, compiles defs once into persistent `g_ctx`, wraps call body in `_wfsN`. Pre-compile pass at level load is feasible (deferred until hitching observed). |
| 2026-04-29 | [Investigation: Godot Remote Debugger Protocol](docs/investigations/2026-04-29-godot-remote-debugger-protocol.md) | **Complete** | Naming conventions and wire protocol for Godot's out-of-process TCP game-state editing bridge. Used to inform Phase 2b naming decisions for WF's live-editor bridge. Adopted what fits, noted WF divergences. |
| 2026-04-29 | [Investigation: C++ RTTI usage audit](docs/investigations/2026-04-29-rtti-audit.md) | **Complete** | 51 `dynamic_cast` calls across `level.cc`, `movecam.cc`, `actor.cc`, `room/`, `movement/`; `-fno-rtti` not viable without replacing all of them. `kind()` dispatch has only 2 live call sites. RTTI introduced 2003 when `Actor*` containers generalised to `BaseObject*` — confirmed via SourceForge CVS history. Feeds the Eliminate RTTI TODO. |
| 2026-04-28 | [Investigation: Level authoring comparison — hand-crafted .lev vs Blender-driven](docs/investigations/2026-04-28-mm-practice-authoring-comparison.md) | **Complete** | First brand-new level (`mm_practice`) exercised both authoring paths. Both produce a compilable `.lev` that runs through the full pipeline; Blender round-trip has tighter iteration loop but more export steps; hand-crafted .lev is faster for geometry-only test levels. |
| 2026-04-28 | [Investigation: World Foundry engine capabilities survey](docs/investigations/2026-04-28-engine-capabilities-survey.md) | **Snapshot** | Descriptive snapshot of what the engine does on `2026-new-level` HEAD: renderer, physics, scripting, audio, platforms, asset pipeline, tool surface. Reference baseline for genre-fit discussions and capability-gap plans. |
| 2026-04-28 | [Investigation: Level-construction tooling — skills, Blender plugins, pluggable LLM, licensed-asset sourcing](docs/investigations/2026-04-28-level-construction-tooling.md) | **Survey** | What tooling investments accelerate brief → playable level for WF. Covers Blender plugin gaps, LLM-assisted level gen, CC0 asset sourcing, and the dependency graph across all 32 game-ideas briefs. Companion to `docs/game-ideas/README.md`. |
| 2026-04-28 | [Investigation: Mainline console controllers since N64/PS1/Xbox eras](docs/investigations/2026-04-28-mainline-console-controllers-since-1996.md) | **Reference catalog** | Exhaustive catalog of controller hardware from 1996 to present — button layout, stick count, trigger style, gyro, haptics. Used to ground input-remapping and gamepad-layout design decisions across all target platforms. |
| 2026-04-28 | [Investigation: VR/AR headset support in World Foundry](docs/investigations/2026-04-28-vr-ar-headset-support.md) | **Survey** | Engine-side gap analysis for VR/AR (stereo render, reprojection, 6DOF input, variable refresh); catalog of headsets still in production as of 2026-04. Reference for any future "should we ship on a headset?" decision. |
| 2026-04-19 | [Snowgoons build pipeline — Blender to running game](docs/investigations/2026-04-19-snowgoons-build-pipeline.md) | **Working end-to-end** | One-stop reference for every tool in the snowgoons build chain, in the order they actually run, with inputs, outputs, and what each one does. Useful when onboarding, debugging a mid-chain … |
| 2026-04-19 | [OAD ButtonType audit — iff2lvl vs levcomp-rs](docs/investigations/2026-04-19-oad-buttontype-audit.md) | **In progress** | **Purpose:** cross-reference every `ButtonType` variant from `wf_oad::ButtonType` (29 total) against how `wftools/iff2lvl` emits it and how `wftools/levcomp-rs/src/oad_loader.rs` emits it, to catch … |
| 2026-04-19 | [`.offsetof` arithmetic in iffcomp — oracle vs current behavior](docs/investigations/2026-04-19-iffcomp-offsetof-arithmetic.md) | **Recommendation accepted** | **Context:** Reconstructing `wflevels/snowgoons.iff.txt` as a proper compile-source text-IFF file (mirror-first, deviate-later), chunk-by-chunk, so iffcomp-rs can produce byte-identical output … |
| 2026-04-19 | [Email: `_PathOnDisk.base.rot` mystery bytes in oracle `snowgoons.iff`](docs/investigations/2026-04-19-path-base-rot-oracle-mystery.md) | **In progress** | **To:** Kevin T. Seghetti (cc: original WF team — this is about `wftools/iff2lvl/path.cc`) **From:** Will, via Claude-assisted archaeology **Subject:** Do you remember what `_PathOnDisk.base.rot` … |
| 2026-04-18 | [Android Port — Executable Size and RAM Usage](docs/investigations/2026-04-18-android-port-size-and-ram.md) | **In progress** | **Branch:** 2026-android **Artifact:** `android/app/build/outputs/apk/debug/worldfoundry-debug.apk` **NDK:** 26.2.11394342, arm64-v8a, `-DCMAKE_BUILD_TYPE=RelWithDebInfo`, then stripped by AGP … |
| 2026-04-18 | [Closing the Android Port — Remaining Work](docs/investigations/2026-04-18-android-port-closure.md) | **Playable APK shipped** | **Branch:** 2026-android |
| 2026-04-17 | [IFF format lineage — EA IFF 85, AIFF, RIFF, WorldFoundry IFF](docs/investigations/2026-04-17-iff-format-lineage.md) | **Complete** | Traces all four formats from the common 1985 ancestor. Key findings: AIFF and WF IFF independently arrived at the same solution (bake navigational offsets at write time for slow-media random access); WF uniquely separates interchange (text source) from execution (platform binary); `.align(2048)` maps CD-ROM sectors. Side-by-side comparison table included. |
| 2026-04-16 | [Reverse-engineering the WF binary level format for `levcomp-rs`](docs/investigations/2026-04-16-levcomp-rs-reverse-engineering.md) | **Phase 2c complete** | Binary format fully mapped; Phase 2c (2026-04-17): mesh bbox from MODL/VRTX, packed asset IDs, `asset.inc` output, 37 objects validated. Remaining: real path/channel keyframes. |
| 2026-04-16 | [Coding-conventions remediation](docs/investigations/2026-04-16-coding-conventions-remediation.md) | **In progress** | Audit of 2026-authored code in `wfsource/source/` against `docs/coding-conventions.md`. Honest accounting of where recent additions don't yet follow the rules they propose. |
| 2026-04-15 | [LOC tracking](docs/investigations/2026-04-15-loc-tracking.md) | **Ongoing** | Tracks code line count over time. Dead-code removal took the tree from 64,252 (baseline `74d1a47`) to 36,199 (−43.7%, `e2dcc98` after Batch 7); retiring the legacy `physics/wf/` backend is projected to land the reduction at ~35,113 (−45.3%). Tool: `scripts/loc_report.py`. |
| 2026-04-14 | [Scripting language replacement](docs/investigations/2026-04-14-scripting-language-replacement.md) | **Complete** | Comprehensive survey that recommended Lua 5.4 as the primary engine. Spawned all scripting plans. Decision: Lua won. |
| 2026-04-14 | [Physics engine survey](docs/investigations/2026-04-14-physics-engine-survey.md) | **Complete** | Surveyed Bullet, PhysX, Rapier, Jolt, and others. Recommended **Jolt Physics** (MIT, ~300 KB, `CharacterVirtual`, active upstream). Spawned Jolt integration plan. |
| 2026-04-14 | [Jolt Physics integration](docs/investigations/2026-04-14-jolt-physics-integration.md) | **Functional** | Jolt is the default (`WF_PHYSICS_ENGINE=jolt`); snowgoons is playable. Runtime init/shutdown moved to `WFGame` (`b5dc7fe`). Legacy `physics/wf/` retained pending parity on a second level. |
| 2026-04-14 | [Remove audio subsystem](docs/investigations/2026-04-14-remove-audio.md) | **Complete** | Implemented 2026-04-15. `wfsource/source/audio/` and `wfsource/source/audiofmt/` deleted. Stub audio stubs were non-functional on Linux. To be replaced by miniaudio (see audio investigation). |
| 2026-04-13 | [ButtonType × showAs coverage audit](docs/investigations/2026-04-13-showas-coverage.md) | **Complete** | Audited all OAD field type × showAs combinations against the Blender plugin. Gaps identified and fixed. |
| 2026-04-11 | [iffcomp — Rust rewrite](docs/investigations/2026-04-11-iffcomp-rs-rewrite.md) | **Complete** | Rust port in `wftools/iffcomp-rs/`. Byte-exact against C++ oracle. Includes comprehensive `all_features.iff.txt` torture test shared with Go port. |
| 2026-04-11 | [iffcomp — Go rewrite](docs/investigations/2026-04-11-iffcomp-go-rewrite.md) | **Complete** | Go port in `wftools/iffcomp-go/`. Byte-exact against C++ oracle (both binary and text output). Passes shared torture fixture. Go is primary; C++ kept as oracle. |
| 2026-04-11 | [iffcomp — C++ modernization](docs/investigations/2026-04-11-iffcomp-modernization.md) | **Complete** | Modernized the 1996 flex/bison C++ `iffcomp` to build on GCC 15 / Clang under C++17. Now serves as byte-exact oracle for Go and Rust ports. |
| 2026-04-14 | [Audio: sound effects, music, positional sound](docs/investigations/2026-04-14-audio-sound-music.md) | **Phases 1–5 complete** | Phase 1: miniaudio SFX one-shots. Phase 2: TinySoundFont MIDI player audible. Phase 3: per-level `level<N>.mid` + load/stop hooks. Phase 4: `play_music`/`stop_music`/`set_music_volume` Lua closures (Lua-only, not mailbox). Phase 5: 3D positional SFX + listener tracking from camera (three miniaudio gotchas surfaced and fixed). Phases 6 (mobile) and 7 (docs) deferred; mailbox-wired audio API for non-Lua engines deferred. |
| 2026-04-14 | [Constraint-based props](docs/investigations/2026-04-14-constraint-based-props.md) | **Deferred** | Doors, chains, pulleys, elevators via Jolt constraints. **Hard prerequisite:** Jolt integration must land first; also requires IFF binary chunk support. Not yet scheduled. |
| 2026-04-14 | [Multiplayer, voice chat, mobile input](docs/investigations/2026-04-14-multiplayer-voice-mobile-input.md) | **Deferred** | Surveyed multiplayer sync models, voice (LKWS/Agora/LiveKit), mobile input (touch/gyro/haptics). Depends on mobile port landing first. Not yet scheduled. |
| 2026-04-14 | [REST API box PoC](docs/investigations/2026-04-14-rest-api-box-poc.md) | **Complete** | cpp-httplib embedded server in `wf_game`; create/recolor/resize/delete GL wireframe boxes via HTTP at runtime. Landed `7e690e1`. |

---
## Reference

| Date | Document | Summary |
|------|----------|---------|
| 2026-04-16 | [Scripting languages in WF](docs/scripting-languages.md) | Survey of all supported engines (Lua, Fennel, JS, wasm, Wren, Forth). Covers integration surface, binary cost (`.text`, `-O2`), RAM footprint, compile-time switches, and reference scripts for each language. |
| 2026-04-16 | [Coding conventions](docs/coding-conventions.md) | Authoritative C++ style guide for WF runtime code. Subsumes `wfsource/source/codingstandards.txt`. Covers target envelope, naming, Validate() discipline, assert family, no-fallback policy, lookup tables, OAS/OAD decision tree, mailboxes, streams, and foreign-library interop. |
| 2026-04-15 | [JerryScript GCC 14 build fixes](docs/reference/2026-04-15-jerryscript-gcc14-build-fixes.md) | Documents 7 GCC 14 build failures in JerryScript v3.0.0 with `wf-minimal` profile and how they were fixed. Applied as part of the JS engine landing. |
| 2026-04-14 | [Compile-time switches](docs/reference/2026-04-14-compile-time-switches.md) | Generated catalogue of 929 unique `#ifdef` switches across the codebase. Informational. See also `docs/compile-time-switches.md` (live version). |
| 2026-04-14 | [WF viewer design notes](docs/reference/wf-viewer.md) | Describes the standalone `wftools/wf_viewer/` approach for rendering level geometry without the full engine stack. Superseded by `wf_game` running end-to-end. |
| 2026-04-14 | [Production pathway diagram](docs/reference/production-pathway.md) | Mermaid diagram of the original pipeline from `.oas` / 3D editor → `cd.iff`. Useful map of where each tool fits. |
| 2026-04-13 | [Blender → cd.iff pipeline](docs/reference/2026-04-13-blender-to-cd-iff-pipeline.md) | Maps the existing pipeline and proposes the Blender-native replacement for the 3DS Max content path. Key follow-up: no automated `.lev` → `.iff` path from Blender yet. |
| 2026-04-13 | [OAS / OAD format](docs/reference/2026-04-13-oas-oad-format.md) | Documents the OAS (object attribute source) and OAD (compiled descriptor) binary format. Used by `wf_blender` and `oas2oad-rs`. |
| 2026-04-12 | [Steam shipping plan](docs/reference/2026-04-12-steam-shipping-plan.md) | Comprehensive plan for shipping a WF-based game on Steam. Enumerates runtime blockers (build system, C++ dialect, HAL, graphics, scripting). Most blockers are now resolved or being resolved; Steam packaging itself not yet started. |
| 2026-04-11 | [wftools rewrite analysis](docs/reference/2026-04-11-wftools-rewrite-analysis.md) | Analyzes all ~23 `wftools/` directories; recommends which to drop, rewrite (Go/Rust), or replace with off-the-shelf tools. |
| 2026-03-22 | [WorldFoundry Engine: Code Analysis & Opinions](docs/investigations/2026-03-22-engine-code-analysis.md) | External deep-dive into the original `wfsource` codebase (~750 C/C++ files, 1994–2003). Covers architecture (23 libraries, PIGS layer), fixed-point math, arena memory management, OAS/OAD data-driven object system, Tcl scripting, state-machine movement handlers, order-table renderer, room streaming, mailbox communication bus, content pipeline, and coding standards. Concludes: serious professional engine, disciplined architecture, correct calls for the PS1 era, many patterns remain good ideas today. |


## Blockers

No hard blockers. Jolt is functional and all scripting engines are smoke-tested. Active areas of ongoing work are listed in Open follow-up work below.

---

## TODO

### Scripting
- **WAMR Phase 2 (AOT)** — deferred; `wamrc` compiles `.wasm` → native machine code offline; output is ISA-specific (x86_64, arm32, arm64 each need a separate `.aot` blob); ~10 KB AOT loader vs. ~107 KB classic interp. Revisit when ship targets are concrete.
- **wasm3 retired** — done 2026-04-16; `engine/vendor/wasm3-v0.5.0/` + `scripting_wasm3.{hp,cc}` removed; `WF_WASM_ENGINE=wamr` is the only wasm option.
- **Lua remote step debugger** — explicit user request for "later": MobDebug/DBG.lua/LuaLS-DAP into LuaInterpreter for in-game step debugging.
- **Fennel macros / `require`** — `fennel.searcher` / `package.searchers`; `.fnl` build step.
- **Coroutine smoke test** — fix #6 landed but untested end-to-end with a real yielding script.
- **wasm module cache** — hash source pointer + size, reuse compiled modules across `RunScript` calls (needed before wasm in hot-loop scripts).
- **Binary IFF chunk types** — `WSM `/`AOT ` tags with explicit length; drop base64 for ~33% asset shrink.
- **Cross-language API parity audit** — `read_actor`/`read_fixed`/`read_color`/`read_flags` typed accessors need to be consistent across all engines when added. No canonical IDL yet.
- **`WF_DEFAULT_ENGINE` knob** — for Lua-off builds, needs a way to select the sigil-less fallthrough engine. Currently undefined behavior.
- **Lua → JS / Lua → Wren script converters** — mirroring `tcl_to_lua_in_dump.py`.
- **Load level by filename from CLI** — **done**: `-L<path>` flag in `main.cc:167`; `gLevelOverridePath` in `game.cc:140`. `wf_game -L<level.iff>` bypasses `cd.iff`.

### Physics
- **Remove `physics/wf/`** — kept until Jolt passes snowgoons parity on at least one other level; removal is a separate reviewable commit.
- **Constraint-based props** — doors/chains/pulleys via Jolt; blocked on Jolt parity + IFF binary chunks.

### Dead code
- **Batch 8** — Jolt replaces WF physics (in progress).
- **`hal/_list` + `hal/_mempool` migration** — refactor `MsgPort` to use `cpplib/minlist.hp` + `memory/mempool.hp`, then delete the HAL remnants.
- **`eval/` (120 LOC)** — tool-side callers (`wftools/prep`, `wftools/iff2lvl`) need porting to Blender plugin first.

### Content pipeline
- **Blender → `cd.iff` pipeline** — Phases 2a + 2b + 2c landed; snowgoons loads 37 objects end-to-end, all Jolt bodies valid. Remaining: real path/channel keyframes.
- **iffcomp: Rust is primary** — Decision: tools in Rust. Four implementations exist (C++ modernized oracle, Go, Node.js, Rust); all pass `all_features.iff.txt`. Rust port (`iffcomp-rs/`) is the going-forward implementation. C++ kept as byte-exact oracle; Go and Node.js ports are superseded.

### Larger / deferred work
- **Audio (miniaudio)** — Phases 1–5 complete (SFX one-shots, MIDI MusicPlayer, per-level music, Lua scripting surface, 3D positional SFX + listener tracking). Phases 6 (mobile backends) and 7 (docs) deferred. **Gap:** audio API is Lua-only (C closures in `scripting_lua.cc`), not mailbox-wired; the other seven scripting engines currently can't trigger music or SFX.
- **Mobile port** — Android arm64 / iOS arm64; plans written ([Android](docs/plans/2026-04-16-android-port.md), [iOS](docs/plans/2026-04-16-ios-port.md)). Android Phases 1+2 done; Phase 0 (immediate-mode GL retirement) in progress — steps 1/2/4a/4b landed 2026-04-17, step 4c remaining is **proper shader ports of directional lighting + linear fog + matte triangles, not Android-only stubs**. iOS still blocked on Android.
- **Multiplayer / voice / mobile input** — blocked on mobile port.
- **Steam packaging** — Phases 1+2 done: Steamworks SDK lifecycle and Steam Input are wired in. Phases 3 (SteamPipe depot build + upload) and 4 (store page assets) deferred; blocked on Steamworks partner account and store capsule art.

---

## Last Change

**2026-05-15** — SMB W1-1: fixed player movement direction (Euler C 0→π/2); fixed camera off-centre (Camera/camshot/Target02 X from 33.75→4.5); documented WF coordinate system in `CLAUDE.md`; filed coordinate-system investigation.
