# WorldFoundry Project Status

**As of:** 2026-05-26  
**Branch:** `2026-new-level`

---

## History

45 days of work (2026-04-12 – 2026-05-26). Newest first:

- **SMB enemies dormant until on-screen (2026-05-26)** — Faithful to the arcade, the Goomba/Koopa now stay still until the Director's one-way camera ratchet (`SMB_MAX_CAM_X` + half-frustum) reveals them, so they no longer pre-walk off ground_1 into pit 0 and silently vanish before Mario arrives. See [plan](docs/plans/2026-05-25-smb-w1-1-enemies-dormant-until-on-screen-faithful.md).
- **`wf-edit` in-editor cd.iff level picker + viewport tracking (2026-05-25)** — Launching the editor on a bare multi-level `cd.iff` (no `:tag`) pops a startup modal listing the archive's levels to choose one this session, and the 3D viewport tracks the pick by slicing that cd.iff chunk into a `-L` temp `.iff` (no `_desiredLevelNum` rework). See [plan](docs/plans/2026-05-25-wf-edit-cdiff-level-picker.md).
- **`wf-edit` loads compiled binary levels (2026-05-25)** — The editor now opens a bare `.iff`/`.lvl` or a level selected out of a `cd.iff` archive (`--leveltree=cd.iff:L4`), decompiling the binary to a temp `.lev` via `levcomp decompile` before the existing `levtree`→Doc path. See [plan](docs/plans/2026-05-25-wf-edit-load-binary-iff.md).
- **SMB pit/fall death + level countdown timer (2026-05-25)** — A below-gap `ActBox` and a 400-unit Director countdown both feed Mario's existing respawn (−1 life), so falling into a pit or running the HUD timer to "TIME UP" now costs a life. See [plan](docs/plans/2026-05-25-smb-pit-death-and-level-timer.md).
- **Collab-hardening — leaf-granular, drag-aware propagation (2026-05-25)** — The CRDT→engine bridge now re-applies only the leaves actually flagged changed and a drag-lock stops a peer's or undo's concurrent edit from snapping your in-progress gizmo drag back to a stale pose. See [plan](docs/plans/2026-05-25-collab-hardening.md).
- **Plan-status sweep (2026-05-25)** — Reconciled all 225 plan docs against git/code, flipping ~50 done-but-mislabeled plans to DONE and giving the genuine backlog accurate status; every plan now carries a Status. See [sweep doc](docs/plans/2026-05-25-plan-status-sweep.md).
- **Deep Doc observer (2026-05-25)** — All Doc writers (remote peers, undo, replay, DAP) now drive the viewport, not just local Properties-panel edits, via a single `DrainEngineSync` propagation path. See [plan](docs/plans/2026-05-25-observe-deep-bridge.md).
- **SMB coin slides right again (2026-05-25)** — The coin froze on landing because it inherited the `Running Deceleration = 0.90` default while the friction knobs the level set are dead under Jolt; fixed by zeroing deceleration. See [plan](docs/plans/2026-05-25-smb-gold-value-wire-and-doc-fix.md).
- **SMB coin awards its OAD `Gold Value` (2026-05-25)** — The live proximity-pickup path now credits the player by the coin's OAD `Gold Value` instead of a hardcoded +1. See [plan](docs/plans/2026-05-25-smb-gold-value-wire-and-doc-fix.md).
- **Gold coin: 5 s TTL + Z-axis spin (2026-05-22)** — Coin lifetime 3→5 s plus a stateless Forth Z-axis spin; fixed three stale-object re-export bugs and a `lmalloc.cc` UBSan misalignment crash along the way. See [plan](docs/plans/2026-05-22-gold-ttl-spin.md).
- **Native Ctrl+Z/Y undo in `wf-edit` (2026-05-22)** — Wrapped the Yrs `UndoManager` into the editor with local-only-in-collab undo via tracked transaction origins. See [plan](docs/plans/2026-05-22-yrs-upgrade-and-native-undo.md).
- **Blender-snowgoons "untextured" was the camera (2026-05-22)** — The flat-gray render was a CamShot exported Fixed/Absolute, not a texture bug; the importer now hard-fails on DATA/STR enum disagreement. See [plan](docs/plans/2026-05-22-camshot-enum-roundtrip-hardfail.md).
- **Q✱bert humanoid enemies stand on the cubes (2026-05-22)** — Slick/Sam/Ugg/Wrong-Way re-based to feet-at-origin so they sit on the cubes instead of half-buried, verified via a debug-bridge screenshot harness. See [plan](docs/plans/2026-05-22-qbert-slick-sam-feet-origin.md).
- **Real-time multi-user co-editing in `wf-edit` (2026-05-21)** — Multiple editor instances share a CRDT Doc over a Rust relay, seeing each other's field edits, structural changes, presence dots, and chat live. See [plan](docs/plans/2026-05-21-realtime-coediting.md).
- **`wf-edit` user manual + screenshots (2026-05-21)** — New manual with 10 screenshots; the editor plans now embed proof screenshots inline (surfacing + fixing a md-to-pdf.sh table-cell `<img>` bug). See [manual](docs/wf-edit-manual.md).
- **Voice + video calling in `wf-edit` (2026-05-21)** — LAN-only Opus voice + VP8 video between editor instances over raw UDP, diverging from the originally-planned WebRTC/DTLS stack. See [plan](docs/plans/2026-05-21-voice-video-collab.md).
- **Live structural sync — add/delete reflects in the viewport (2026-05-21)** — Replaced the brittle positional Doc↔engine formula with a stable index map so add/delete reflects live without freezing field preview. See [plan](docs/plans/2026-05-21-live-structural-sync.md).
- **OAD codegen for `kPropMap` — 15 → 77 fields (2026-05-21)** — `regen-headers.sh` now generates the full 77-field property map, widening the engine *write* surface; editor live-preview coverage is a separate follow-up. See [plan](docs/plans/2026-05-21-oad-kpropmap-codegen.md).
- **SMB Gold coin TTL despawn (2026-05-21)** — Coin self-removes after 1.5 s using `LevelClock`, fixing a framerate-dependent tunnelling bug where it skipped past the floor before rendering. See [plan](docs/plans/2026-05-21-gold-ttl-despawn.md).
- **`JoltContactDispatch` self-index fix (2026-05-21)** — Static-world collisions were setting `COLLIDER_IDX` to the player's own index instead of 0; added a dedicated static-collision path. See [plan](docs/plans/2026-05-21-jolt-collision-selfindex-fix.md).
- **Outliner add/delete actor (2026-05-21)** — First structural editing in `wf-edit`, persisting through the save walk, with field→viewport propagation suspended during structural edits. See [plan](docs/plans/2026-05-21-outliner-add-delete.md).
- **Lossless Doc schema (2026-05-21)** — Each leaf's literals now live as structured `items` mirroring levtree exactly; the retained-JSON side-channel is gone and save is a pure Doc→JSON walk. See [plan](docs/plans/2026-05-21-lossless-doc-schema.md).
- **Editor property panel — editable widgets → Doc (Phase 3, 2026-05-20)** — The OAD-driven Properties panel became editable, committing each widget to the selected actor's Doc leaf. See [plan](docs/plans/2026-05-20-editor-property-panel.md).
- **Editor property panel — OAD-driven widgets, read-only (Phase 2, 2026-05-20)** — Each field renders with the widget its ButtonType×showAs dictates (dropdowns, checkboxes, swatches, file/object-refs), runtime byte-unchanged. See [plan](docs/plans/2026-05-20-editor-property-panel.md).
- **Editor app shell complete (M1–M6, 2026-05-20)** — The Dear ImGui editor embeds the live engine viewport and reads a read-only Y.Doc into the Outliner; surfaced a yrs 0.9.3 bug and prompted the project-wide flip to ASan+UBSan-by-default. See [plan](docs/plans/2026-05-20-editor-app-shell.md).
- **`.ht` codegen restored (2026-05-20)** — Revived the lost `cstruct.pl` canonicalizer as inline awk; all 34 `.ht` files reproduce byte-for-byte under a new oracle test. See [plan](docs/plans/2026-05-20-ht-codegen-repair.md).
- **IFF→Y.Doc translator landed — `levtree-rs` (2026-05-20)** — `levtree-rs` parses the `.lev` chunk DSL into the editor's chunk-tree JSON and prints canonical `.lev` back, proven by a byte-identity gate. See [plan](docs/plans/2026-05-20-iff-lev-ydoc-translator.md).
- **Engine mutation API landed — `wfmut::` (2026-05-19)** — Plain-C++ surface (pos/orient/field/mailbox, spawn/remove) shipped in ~3 h vs a 1–2 wk estimate, with the debug bridge routed through it. See [plan](docs/plans/2026-05-19-engine-mutation-api.md).
- **wfcrdt C++ RAII wrapper landed (2026-05-19)** — Thin move-only RAII wrapper (Doc/Map/Array/Transaction/Output) over the Yrs C ABI in ~1 h; key gotcha is that observers don't fire on the txn that registered them. See [plan](docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md).
- **Yrs C ABI binding landed (2026-05-19)** — Vendored y-crdt + Corrosion behind a default-OFF `WF_ENABLE_CRDT` flag so the engine stays Rust-free and the editor owns the Y.Doc; default build byte-identical to before. See [plan](docs/plans/2026-05-18-yrs-c-abi-binding.md).
- **HAL alignment → compile-time `WF_POINTER_ALIGN` (2026-05-19)** — Replaced hardcoded 8s with `constexpr WF_POINTER_ALIGN = sizeof(void*)` plus carve-outs for 32-bit ARM/ESP32, same codegen as a literal. See [`cpplib/align.hp`](wfsource/source/cpplib/align.hp).
- **HAL pool allocators 4→8-byte alignment fix (2026-05-19)** — Pool allocators now 8-byte-align, dropping ~3,500 misalignment warnings to 1; matters for iOS AArch64 atomics that SIGBUS on misaligned operands. See [BUGS.md](docs/BUGS.md).
- **`BaseObjectIterator` virtual-destructor fix + ASan sweep clean (2026-05-19)** — Fixed a 22-year-dormant new-delete-type-mismatch ASan caught; the full Load→StepFrame→Unload chain is now sanitizer-clean on snowgoons and qbert. See [BUGS.md](docs/BUGS.md).
- **Snowgoons "multi-cycle crash" root-caused (2026-05-19)** — Actually a frame-2 crash from a 16-year-old `&&` short-circuit over-read (plus a side-effecting `=` assert), both dating to the 2010 first commit. See [investigation](docs/investigations/2026-05-19-snowgoons-rendobj3-overread.md).
- **Yrs C ABI binding plan written (2026-05-18)** — Plan locked in: editor owns the Y.Doc behind a separate library, engine stays Rust-free, and the mutation API is a first-class deliverable. See [plan](docs/plans/2026-05-18-yrs-c-abi-binding.md).
- **Host-GL e2e harness + UnloadLevel LIFO fix (2026-05-18)** — Found and fixed 6 dormant LIFO destructor-ordering violations plus a Jolt ODR violation from inconsistent NDEBUG; took ~5 h vs a half-day estimate. See [plan](docs/plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md).
- **Engine embed-readiness — Phase 0b done (2026-05-18)** — All four collaborative-editor refactor sub-tasks (frame-step API, external GL context, input injection, de-globaling `theGame`) shipped same-day. See [plan](docs/plans/2026-05-18-engine-frame-step-api.md).
- **SMB Mario movement retune + Jolt airborne fix (2026-05-18)** — Retuned ground/air speed with SMB-style variable jump, and root-caused the "stuck Mario" bug to the airborne velCache only reconciling the Y axis. See [plan](docs/plans/2026-05-18-smb-mario-movement-retune.md).
- **SMB `?`-block coin pop-out (2026-05-18)** — A stacked coin actor arcs up/down on bump via a Forth animation in Mario's per-tick script; pure level authoring, no engine changes. See [plan](docs/plans/2026-05-18-smb-qblock-coin-pop.md).
- **Per-actor collision mailboxes landed (2026-05-18)** — The engine now writes the colliding actor's index + contact normal to per-actor mailboxes each collision, finishing wiring stubbed years ago. See [plan](docs/plans/2026-05-17-per-actor-collision-mailboxes.md).
- **SMB Mario jumps + walks at NES pace (2026-05-17)** — Added the missing jump trigger for doomstick actors (MarbleHandler lacked the branch GroundHandler had) and tuned speed/jump so the apex reaches `?`-block height. See [plan](docs/plans/2026-05-17-smb-mario-speed-jump-tuning.md).
- **levcomp-rs actor-outside-bbox warning (2026-05-17)** — Now warns per-actor when a center falls outside every room bbox, preventing the silent-invisible-actor failure. See [plan](docs/plans/2026-05-16-levcomp-actor-outside-bbox-warning.md).
- **Q✱bert arcade-faithful spawn sequencer (2026-05-16)** — Six independent timers replaced with one shared countdown reading ROM-decoded round sequence tables, so spawns match the arcade. See [plan](docs/qbert/plans/2026-05-16-qbert-spawn-sequencer.md).
- **Q✱bert second Coily egg in L4 (2026-05-16)** — Arcade rounds 12–15 now spawn two simultaneous Coily eggs via an independent gated timer. See [plan](docs/qbert/plans/2026-05-16-qbert-second-coily-egg.md).
- **Q✱bert SFX pass complete (2026-05-16)** — Fixed swear-sound timing (fall initiation, not 30 frames late) and added kill and disc-rescue sounds across all enemy-contact sites. See [plan](docs/qbert/plans/2026-05-16-qbert-sfx.md).
- **Q✱bert 16-round end-to-end test (2026-05-16)** — Automated test verifies all 88 checks across palettes, cube cycles, scoring, mid-round revert, and enemy-mix gating. See [plan](docs/plans/2026-05-16-qbert-16round-test.md).
- **Q✱bert popup mailbox collision fixed (2026-05-16)** — Moved the popup MB range off one that collided with CE2 egg internals when both are active in L4 (`b26373f`).
- **Q✱bert +50 and +500 popup labels (2026-05-16)** — Added the two missing floating-score labels as 3D text meshes; `cbRoom` pool bumped to fit. See [plan](docs/plans/2026-05-16-qbert-popup-50-500.md).
- **Q✱bert curse-bubble texture (2026-05-16)** — Root-caused an empty atlas to textile-rs mapping opaque RGBA to the transparent key then false-deduping; fixed by generating 24-bit RGB TGA. See [plan](docs/plans/2026-05-16-curse-bubble-texture.md).
- **Q✱bert high-score persistence + game-over (2026-05-15)** — Binary high-score file, initials picker, two-column overlay table, and a 3 s minimum game-over hold (`8f2b6a1`).
- **Q✱bert Coily-falls-off-disc (2026-05-15)** — Snake tracks Q✱bert onto a disc and retires with +500, automated-test verified. See [plan](docs/qbert/plans/2026-05-15-qbert-disc-flash-vfx.md).
- **Q✱bert disc rim flash VFX (2026-05-15)** — A yellow ring pulses when Q✱bert boards a disc, with an automated disc-lure test. See [plan](docs/qbert/plans/2026-05-15-qbert-disc-flash-vfx.md).
- **Q✱bert enemy coexistence rules (2026-05-15)** — No climber while Coily is active, no two simultaneous climbers, and a shared post-kill freeze timer. See [plan](docs/qbert/plans/2026-05-15-qbert-enemy-coexistence.md).
- **SMB W1-1 movement direction fixed (2026-05-15)** — The player moved toward the camera on joystick-right because `currentDir()` is `(cos C, sin C, 0)` (the code comment is wrong); fixed by setting Player Euler C = π/2. See [investigation](docs/investigations/2026-05-15-wf-coordinate-system-and-currentdir.md).
- **WF graceful-degrade under Jolt exhaustion (2026-05-10)** — Investigation closed: the marble already parks cleanly when its floor body is lost, no fix needed.
- **Jolt body-pool exhaustion fails loudly (2026-05-10)** — Every body-creation wrapper now checks `IsInvalid()` and logs instead of registering a bogus handle and segfaulting.
- **Q✱bert per-round cube palettes — all 16 rounds (2026-05-09)** — All 16 arcade rounds have pixel-sampled per-round colors; engine budgets bumped for the 1344-actor pyramid.
- **Q✱bert walker parity scaffolding (2026-05-09)** — All four Phase E pieces (PNG encoding, screenshot op, capture triggers, host harness) are in place; the end-to-end run is still pending.
- **Room::~Room double-free fix (2026-05-04, unverified)** — Replaced a `delete[]` on WF-pool memory with `MEMORY_DELETE_ARRAY`; verification was interrupted.
- **ESC-key migrated to close-requested flag (2026-05-04)** — ESC now writes `_closeRequested` and takes the clean shutdown path instead of calling `sys_exit(0)`.
- **X-close button reliability fix (2026-05-04)** — Mid-event `sys_exit(0)` replaced with a polled `_closeRequested` atomic so the close button goes through full clean shutdown.
- **Debug-bridge Phase B2 — `reload_script` (2026-05-03)** — zForth scripts can be compiled and hot-swapped at runtime; the bridge suite is 10/10.
- **Debug-bridge Phase B1 — `set_shader` (2026-05-03)** — GLSL shaders hot-reload via the bridge, with broken GLSL reported as a structured error while the prior shader stays live.
- **Debug-bridge Phase A — `set_mailbox` + `inject_input` (2026-05-03)** — The bridge can write any mailbox and override joystick input ahead of the live HID, exercised by a pytest harness.
- **marble-madness M1 camera (2026-05-01)** — Plan covers M1–M5+; M1 landed the canonical 45°/30° camera and Player Rotation C = π/4 for correct world-axis alignment.
- **marble-madness-2 game loop (2026-04-30)** — A 90-second countdown plus goal detection firing END_OF_LEVEL when the marble reaches the goal platform.
- **Marble rolls down ramp (2026-04-30)** — Root cause was `MaxAirSpeed=0` zeroing all velocity including gravity; fixed with speed/drag/slope-angle tuning.
- **"Run in Engine" Blender operator (2026-04-29)** — One-click export + compile + launch from Blender's Properties > Scene, with the game running alongside Blender.
- **wf_asset_provider pure-Python rewrite (2026-04-28, unverified)** — Python files replace the PyO3 Rust extension on disk, but whether the addon runs without the native extension is unverified.
- **wf_asset_provider Sketchfab + licence filter v2 (2026-04-28)** — Sketchfab added alongside Poly Haven, with downloads blocked on forbidden licences.
- **wf_asset_provider v1 (2026-04-28)** — Initial asset browser with Poly Haven CC0, a licence-policy filter, thumbnails, and one-click import.
- **iOS Phase 2B3 (2026-04-22)** — The Metal RendererBackend compiles and links with inline MSL shaders, but nothing drives it yet (sim still cornflower blue).
- **iOS Phase 2B2 (2026-04-22)** — All ~120 engine sources compile and link for arm64 iOS Simulator.
- **iOS Phase 2A (2026-04-22)** — Metal is alive on the Simulator (CAMetalLayer + CADisplayLink rendering cornflower blue).
- **iOS Phase 1 verified (2026-04-22)** — Codemagic builds and boots the app on iPhone 17 Pro Sim, opening `cd.iff` with no user Mac required.
- **iOS Phase 1 build green (2026-04-22)** — The app for iOS Simulator arm64 compiles and links under Apple clang.
- **iOS Phase 0 complete (2026-04-21)** — The Codemagic cloud-Mac pipeline is green, reaching per-source compilation and stopping at the expected iOS HAL gap.
- **Snowgoons renders fully (2026-04-19)** — Fixed two regressions (a TGA translucency sentinel, an over-eager STR preference dropping the lights); shadows and textured roof restored.
- **levcomp-rs LVL diff down to 5 bytes (2026-04-19)** — Prepending a newline to the player-script source dropped the delta to 5 unpredictable heap-garbage pad bytes.
- **textile-rs wired into snowgoons (2026-04-19)** — Oracle binary stopgaps replaced with explicit asset slots; a 24-bit TGA fast-path fixed an invisible-roof bug.
- **levcomp-rs LVL diff −97% to 83 bytes (2026-04-19)** — Three commits via two-phase common-block emission, an enum-label fix, and a chunk-order swap.
- **OAD ButtonType audit (2026-04-19)** — All 29 ButtonType variants cross-referenced against iff2lvl; three emission bugs found, 21 types already aligned.
- **levcomp-rs two-phase refactor landed (2026-04-19)** — The pass-1/pass-2 refactor brings the LVL payload to byte-identical length; total diff dropped 2,772 → 141 bytes.
- **levcomp-rs two-phase plan written (2026-04-19)** — Traced and documented the phase-ordering mismatch between levcomp-rs and iff2lvl, fix estimated at half a day.
- **textile-rs validation plan written (2026-04-19)** — Plan for a snowgoons validation harness and oracle byte-identity verification of the untested Rust port.
- **python-tui-lib extracted (2026-04-19)** — TUI library carved out of parking-space and vendored; `?` now opens rendered help in git-branch-browser.
- **`snowgoons.iff.txt` round-trips byte-identical (2026-04-19)** — iffcomp-rs now produces md5-identical output to the oracle, serving as a byte-drift regression anchor.
- **git-branch-browser v2 (2026-04-19)** — A curses TUI rendering branch topology as a chronological waypoint pipeline with fork detection and three diff modes.
- **Blender round-trip plays continuously, untextured (2026-04-19)** — Nine exporter/compiler fixes take `snowgoons-blender.iff` through a continuous per-frame loop with audio and camera and no assertions.
- **Android port closure (2026-04-18)** — The branch hits its close criterion with a polished sideloadable APK; only launcher icons and a stale comment remain.
- **Android audio — Für Elise on snowgoons (2026-04-18)** — Desktop miniaudio + TinySoundFont ported to Android via the asset-accessor memory loader.
- **Android post-boot polish (2026-04-18)** — Correct viewport aspect, pause/resume, a zForth bootstrap fix, and an on-screen d-pad; snowgoons is fully playable on stock arm64.
- **Snowgoons rendering on Android phone (2026-04-18)** — A sideloaded debug APK boots snowgoons on physical arm64 via NativeActivity + EGL 3.0 + asset-backed `cd.iff`, unblocked by four pre-flight fixes.
- **Snowgoons joystick control restored (2026-04-17)** — A byte-preserving re-patch landed the inlined director form that zForth's minimal bootstrap can compile (`a7ef46e`).
- **Window-close shutdown stability (2026-04-17)** — `mesa.cc` now handles WM_DELETE_WINDOW and a stop hook is registered, so the X11 close button exits cleanly instead of aborting.
- **Retire immediate-mode GL / Android Phase 0 (2026-04-18)** — The modern VBO + GLSL/GLES shader backend is the sole GL path on Linux and Android (−541 LOC net; tag `pre-legacy-gl-retire`).
- **Audio Phases 1–5 complete (2026-04-17)** — miniaudio + TinySoundFont with per-level music, fire-and-forget SFX, and 3D positional playback — but only via Lua closures; the mailbox-wired API for other engines is deferred.
- **Android Phases 0+1+2 + Phase 3 (2026-04-18)** — The full Android stack landed (NDK build, HAL seam, NativeActivity + EGL, Gradle, gamepad/touch, asset-backed `cd.iff`); only the device smoke test remained, since closed.
- **Blender ↔ level round-trip (2026-04-17)** — `levcomp-rs` compiles `.lev`→`.lvl` end-to-end and the plugin round-trips all 152 OAD fields; real path/channel keyframes are the last piece.
- **Level pipeline proof (2026-04-17, in progress)** — Phases A+B+C done; D–E (decompile source-less levels, multi-level `cd.iff`) gate the common.inc rearrangement.
- **Tooling and plans (2026-04-17)** — `engine/` reorganised to top-level, a REST API box PoC landed, the iOS plan written, and the CLI level override confirmed.
- **Scripting system (2026-04-16)** — Seven engines smoke-tested in snowgoons with Lua optional and wasm3 retired for WAMR; the five alternate Forth backends build but aren't end-to-end tested.
- **Dead-code removal (2026-04-15, closed 2026-04-18)** — Batches 1–7 cut `wfsource/source/` by 43.7% (64,252 → 36,199 lines); Batch 8 (`physics/wf/`) deferred until Jolt parity.
- **Jolt Physics (2026-04-14)** — Integrated as default with the five-step plan complete; legacy `physics/wf/` retained until parity on a second level.
- **Steam Phases 1+2 (2026-04-12)** — Steamworks SDK lifecycle and Steam Input wired into HAL (`WF_ENABLE_STEAM=1`); depot and store-page phases deferred.

---

## Plans

### Active

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-05-25 | [Plan: wf-edit in-editor cd.iff level picker](docs/plans/2026-05-25-wf-edit-cdiff-level-picker.md) | **DONE 2026-05-25 (~1.5 h)** | Launching `wf-edit` on a bare multi-level `cd.iff` (no `:tag`) shows a startup modal listing the archive's levels (`#`/tag/size/offset); choosing one loads it via the existing `cd.iff:<tag>` path **and** the 3D viewport tracks it — the cd.iff chunk is sliced into a `-L` temp `.iff` (the engine's `-L` wants exactly an `L<N>` chunk, so no `_desiredLevelNum` rework). A startup pick, not runtime switching. Verified by tag/index + viewport render; explicit selector / bare `.iff` / text `.lev` / explicit `--level=` all behave correctly. |
| 2026-05-25 | [Plan: wf-edit load compiled binary levels (`.iff`/`cd.iff`)](docs/plans/2026-05-25-wf-edit-load-binary-iff.md) | **DONE 2026-05-25 (~1 h editor wiring)** | `wf-edit` opens a bare compiled `.iff`/`.lvl` or a level picked from a `cd.iff` archive (`--leveltree=cd.iff:L4`), sniffing binary-vs-text by content and decompiling via `levcomp decompile` before the existing `levtree`→Doc path; verified on snowgoons (36 actors) by tag, index, and bare file. Corrected the plan's wrong "no binary writer" claim — bare-`.iff` recompile already exists; saving always emits a new standalone file (`.lev` or recompiled `.iff`), and `cd.iff` re-pack is by design not a goal. |
| 2026-05-25 | [Plan: SMB pipe warp → underground coin room](docs/plans/2026-05-25-smb-pipe-warp-coin-room.md) | **DONE 2026-05-25** | WF's first cross-room transition, full round trip: Down on a surface pipe warps Mario into a genuine second `room` (lit underground coin room, camera frames it cleanly), he collects 3 coins, then a pure `Warp`+`Target` exit pipe warps him back to the surface; bridge-verified end to end. Nine gotchas fixed + written to the designer guide (player `Moves Between Rooms`, per-room light, rooms must be *contiguous* not gapped or the camera freezes mid-pan, `INDEXOF_CAMSHOT`=1921-not-1021, ActBoxOR fires via C++ overlap, surface camera zone needs a real in-room volume for the return, Warp renders its volume unless `Visibility Mailbox=0`, warp-landing floor must be wide+thick or depenetration shoves the player off it, `gold` TTL blocks pre-placed coins so use static discs + script proximity-pickup). |
| 2026-05-25 | [Plan: SMB Gold Value wire-up + coin-doc fix](docs/plans/2026-05-25-smb-gold-value-wire-and-doc-fix.md) | **DONE 2026-05-25** | Confirmed the reported TTL bug was already fixed and wired the dead OAD `Gold Value` field into the live pickup path. Surfaced a gap where the SMB Blender export reads a stale fixtures OAD dir, so new canonical fields silently drop. |
| 2026-05-22 | [Plan: Upgrade Yrs 0.9.3→0.26.0 + native undo/redo](docs/plans/2026-05-22-yrs-upgrade-and-native-undo.md) | **DONE 2026-05-22 — both phases** | Upgraded the Yrs submodule to v0.26.0 (fixing a root-resolution deadlock with lazy txn acquisition) and added native Ctrl+Z/Y undo, local-only-in-collab via tracked transaction origins. |
| 2026-05-22 | [Plan: Q✱bert humanoid feet-origin meshes](docs/plans/2026-05-22-qbert-slick-sam-feet-origin.md) | **DONE 2026-05-22 — verified** | Re-based Slick/Sam/Ugg/Wrong-Way to feet-at-origin so they stand on the cubes instead of half-buried, verified with a new debug-bridge screenshot harness. |
| 2026-05-22 | [Plan: Viewport translate + rotate gizmo](docs/plans/2026-05-22-viewport-gizmo.md) | **DONE 2026-05-22 (Phases 0–3) — user-verified** | Direct drag-to-move/rotate in the 3D viewport via vendored ImGuizmo with no engine change, persisting to the Doc on release. Also fixed a latent radians-vs-revolutions Orientation bug and an editor source-path tangle; scale deferred. |
| 2026-05-21 | [Plan: Voice + video calling](docs/plans/2026-05-21-voice-video-collab.md) | **DONE 2026-05-21 (~3 h)** | LAN voice (Opus) + video (VP8) between editor instances in the same room over raw UDP, diverging from the planned WebRTC/DTLS stack. |
| 2026-05-21 | [Plan: Live structural sync (M2)](docs/plans/2026-05-21-live-structural-sync.md) | **DONE 2026-05-21** | Replaced the stale positional Doc↔engine formula with a stable index map so add/delete reflects live in the viewport without freezing field preview. |
| 2026-05-21 | [Plan: OAD codegen for `kPropMap` (M3)](docs/plans/2026-05-21-oad-kpropmap-codegen.md) | **DONE 2026-05-21** | Generated a 77-entry property map from the `.ht` files, widening the engine **write** surface; editor live-preview coverage remains a separate follow-up. |
| 2026-05-21 | [Plan: Outliner add/delete actor](docs/plans/2026-05-21-outliner-add-delete.md) | **DONE 2026-05-21 (~1.5 h)** | First structural editing in `wf-edit` (add/delete actor) persisting through the save walk, with field→viewport propagation suspended during structural edits as the safe path. |
| 2026-05-21 | [Plan: Lossless Doc schema](docs/plans/2026-05-21-lossless-doc-schema.md) | **DONE 2026-05-21 (~2 h)** | Made the Doc self-sufficient (literals as structured items, retained-JSON side-channel deleted), unblocking structural and remote save; byte-identical to canonical levtree print. |
| 2026-05-21 | [Plan: Editor save round-trip (Doc → `.lev`)](docs/plans/2026-05-21-editor-save-roundtrip.md) | **DONE 2026-05-21 (~2 h)** | Closed the read-edit-write loop (Doc→JSON→levtree→`.lev`) including Save+Compile; edits land in exactly the changed lines, the live engine isn't reloaded. |
| 2026-05-20 | [Plan: CRDT→engine bridge (Option C)](docs/plans/2026-05-20-crdt-engine-bridge.md) | **DONE 2026-05-21 (~3 h)** | A Properties-panel edit now moves the actor on screen via the `wfmut::` surface (identity index map, OAD-name-keyed field translation). v1 covers transform + 15 kPropMap fields; full coverage is a codegen follow-up. |
| 2026-05-20 | [Plan: Editor app shell](docs/plans/2026-05-20-editor-app-shell.md) | **DONE 2026-05-20 (M1–M6)** | Full ImGui editor shell: embeds the engine viewport and reads a read-only Y.Doc into the Outliner, ASan/UBSan-clean. Surfaced a yrs 0.9.3 bug worked around with a saved upstream patch. |
| 2026-05-20 | [Plan: Editor property panel (OAD-driven widgets)](docs/plans/2026-05-20-editor-property-panel.md) | **Phase 3 done 2026-05-20 (~4 h)** | All three phases done — OAD-driven widgets (ButtonType×showAs dispatch), now editable to the Doc leaf. The levtree round-trip is deferred at this stage. |
| 2026-05-20 | [Plan: `.lev` ↔ Y.Doc translator (`levtree-rs`)](docs/plans/2026-05-20-iff-lev-ydoc-translator.md) | **Done 2026-05-20 (~2 h)** | `levtree-rs` parses `.lev`→chunk-tree JSON and prints canonical `.lev` back, gated by a byte-identity test on snowgoons/smb/qbert. The final block of the engine↔CRDT bridge. |
| 2026-05-19 | [Plan: SMB block-IS-generator + collectible Gold](docs/plans/2026-05-19-smb-block-generator-coin.md) | **Needs user play-test** | Each `?`-block is a self-bumping Generator throwing a Gold collectible coin (touch Mario → vanish + credit GOLD mailbox); all engine + level wiring done and spawn verified headless. Interactive pickup needs a full-framerate play-test. |
| 2026-05-19 | [Plan: Engine mutation API (`wfmut::`)](docs/plans/2026-05-19-engine-mutation-api.md) | **Mostly done — spawn path open** | Plain-C++ `wfmut::` surface (pos/orient/field/mailbox, spawn/remove) with the debug bridge routed through it. The `SpawnActor` runtime path is committed-but-unconfirmed, to be settled by the SMB Gold work. |
| 2026-05-19 | [Plan: Template-object Jolt body sync on spawn](docs/plans/2026-05-19-template-object-jolt-body-sync.md) | **Done — verified by play 2026-05-20** | The spawn crash was the Jolt body created at the parking position instead of the spawn position; the fix landed (hidden inside an RTTI-labeled commit) and Will play-verified it. |
| 2026-05-19 | [Plan: wfcrdt C++ RAII wrapper](docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md) | **Done 2026-05-19 (~1 h)** | Thin move-only RAII wrapper (Doc/Map/Array/Transaction/Output) over the Yrs C ABI. Key gotcha: observers don't fire on the txn that registered them. |
| 2026-05-18 | [Plan: Yrs C ABI binding](docs/plans/2026-05-18-yrs-c-abi-binding.md) | **Done 2026-05-19 (~1 h)** | Vendored y-crdt + Corrosion behind a default-OFF `WF_ENABLE_CRDT` flag so the engine stays Rust-free and the editor owns the Y.Doc; default build byte-identical to before. |
| 2026-04-29 | [Plan: Eliminate C++ RTTI](docs/plans/2026-04-29-eliminate-rtti.md) | **Done (2026-05-19)** | Removed all 68 `dynamic_cast` sites and applied `-fno-rtti` engine-wide (binary carries zero typeinfo symbols, Android + UBSan green). "No RTTI" is load-bearing on fixed-point MCU targets — cost, not ideology. |
| 2026-04-29 | [Plan: Live Editor Bridge](docs/plans/2026-04-29-live-editor-bridge.md) | **Phases 1–3 done; Phase 4 partial** | Bidirectional Blender↔engine bridge (one-way push, pause/step, OAD writes, undo, shader + zForth hot-reload) all landed; only DAP script breakpoints remain, arguably subsumed by the editor mutation path. |
| 2026-04-28 | [Plan: Blender addon packaging](docs/plans/2026-04-28-blender-addon-packaging.md) | **Not started** | Add `blender_manifest.toml` for the 4.2+ extension system, fix `install.sh`, add build/package task commands, and reframe the docs around provenance capture. |
| 2026-04-28 | [Plan: game-ideas dependency graph and tooling](docs/plans/2026-04-28-game-ideas-dependency-graph-and-tooling.md) | **Not started** | A Mermaid dependency graph + table across all 32 conversion briefs, an idealised implementation order, and a tooling brainstorm. |
| 2026-04-16 | [Plan: Blender ↔ Level Round-Trip](docs/plans/2026-04-16-blender-level-roundtrip.md) | **Step 6 closed (2026-05-22)** | Renders and plays; the "untextured" symptom was the camera and the old statplat assertion no longer reproduces under Jolt. The remaining Phase 2c path/channel keyframes are parked for net-new authored levels. |
| 2026-04-19 | [Plan: Blender round-trip — oracle dependencies](docs/plans/2026-04-19-blender-roundtrip-oracle-dependencies.md) | **Done** | Builds a fully working `.iff` via the Rust tool chain (iffcomp-rs → levcomp-rs → textile-rs) with no oracle bytes reused; 1687-byte diff, all known-OK deltas. |
| 2026-04-19 | [Plan: textile-rs validation & round-trip](docs/plans/2026-04-19-textile-rs-validation.md) | **Phase 1 done** | Seven fixes give an end-to-end pipeline with the PERM chunk byte-identical and all textures rendering correctly in game. |
| 2026-04-19 | [Plan: levcomp-rs two-phase common-block emission](docs/plans/2026-04-19-levcomp-common-block-two-phase.md) | **Phase A + follow-ups done — 3 bytes remain** | Two-phase emission plus four follow-ups bring it 99.9% closed with zero content-diff; the remaining 3 bytes are non-deterministic uninitialized allocator pad. |
| 2026-04-17 | [Plan: Prove all 7 level pipelines before breaking common.inc](docs/plans/2026-04-17-level-pipeline-proof.md) | **In progress — Phases A+B done** | Phases A+B done (primitives/whitestar compile; common.oad fixture test); Phases C–E remain before the gated common.inc rearrangement that unblocks the ScriptLanguage OAD plan. |
| 2026-04-21 | [Plan: iOS port (via Codemagic)](docs/plans/2026-04-21-ios-port-codemagic.md) | **Phase 2A verified** | Metal is alive on the Simulator (CAMetalLayer + CADisplayLink rendering cornflower blue); Phase 2B (GLSL→MSL, RendererBackend subclass, first triangle) is next. |

### Backlog

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-04-18 | [Plan: Android launcher polish — adaptive-icon XML](docs/plans/2026-04-18-android-launcher-polish.md) | **Not started** | Layer adaptive-icon XML on top of the legacy mipmaps so Android 8+ renders rounded/themed/dynamic icons. Carry-over from the Android port closure audit. |
| 2026-04-18 | [Plan: audio assets from iff](docs/plans/2026-04-18-audio-assets-from-iff.md) | **Not started** | Route all audio (MIDI/soundfont/SFX) through IFF chunks instead of loose files; requires new chunk tags + tool updates and unblocks iOS asset bundling. |
| 2026-04-17 | [Plan: Steam release](docs/plans/2026-04-17-steam.md) | **In progress — Phases 1+2 done** | Steamworks SDK lifecycle + Steam Input wired in (`WF_ENABLE_STEAM=1`, SDK not committed); depot build and store page deferred. |
| 2026-04-17 | [Plan: Mailbox-wired audio API](docs/plans/deferred/2026-04-17-audio-mailbox-api.md) | **Not started** | Let every scripting engine trigger music/SFX via mailbox writes; the handler + slot loader were deleted in a dead-code sweep and need restoring. |
| 2026-04-16 | [ScriptLanguage OAD field](docs/plans/2026-04-16-script-language-oad-field.md) | **Deferred — blocked on round-trip** | Field added then reverted for binary-layout compat; the dispatch table remains (passing 0=Lua), to be re-introduced once all levels compile through Blender+levcomp-rs. |

### Complete

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-05-18 | [Plan: Host-GL e2e harness + UnloadLevel LIFO fix](docs/plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md) | **Done 2026-05-18 (~5 h)** | Fixed 6 dormant LIFO destructor-ordering bugs, an `Array` allocator misuse, a teardown-timing segfault, and a Jolt NDEBUG ODR violation; shipped an external harness linking `libwfengine.a`. Estimate off ~10×. |
| 2026-05-18 | [Plan: Engine frame-step API](docs/plans/2026-05-18-engine-frame-step-api.md) | **Done 2026-05-18** | Extracted `StepFrame`/`LoadLevel`/`UnloadLevel` with a ≤100 ms deltaTime clamp and a smoke CLI for host-driven loops. Single afternoon vs ~1–2 wk estimate. |
| 2026-05-18 | [Plan: Engine external GL context](docs/plans/2026-05-18-engine-external-gl-context.md) | **Done 2026-05-18** | Opaque interface letting an editor host register its own X display/window/GLX context, with `HALCloseWindow`/`XEventLoop` early-bail in host-owned mode. Linux-only for v1. |
| 2026-05-10 | [Jolt pool exhaustion degraded-mode follow-up](docs/plans/2026-05-10-jolt-pool-exhaustion-degraded-mode.md) | **Done 2026-05-10** | Closed — the one-off `terminate` didn't reproduce and existing `_joltBodyID` guards already deliver degraded mode; no code change. |
| 2026-05-10 | [Jolt body-pool exhaustion guard](docs/plans/2026-05-10-jolt-body-pool-exhaustion-guard.md) | **Done 2026-05-10** | All body-creation wrappers check `IsInvalid()` and skip removal on invalid IDs instead of segfaulting; verified with a forced-exhaustion test. |
| 2026-04-29 | [Plan: "Run in Engine" Blender operator](docs/plans/2026-04-29-blender-run-operator.md) | **Closed 2026-04-29** | `WF_OT_run_level` runs export → `build_level_binary.sh` → detached `wf_game`, with a level-name scene property and repo-root addon pref. |
| 2026-04-28 | [Plan: marble-madness player sphere + rolling physics](docs/plans/2026-04-28-marble-player-sphere.md) | **Complete 2026-04-30** | Sphere mesh + `MarbleHandler` gravity-slope rolling via Jolt `CharacterVirtual`; the `MaxAirSpeed=50` fix lets the marble fall onto the ramp (9.9 m/s on 45°). |
| 2026-04-28 | [Plan: wf_asset_provider pure Python](docs/plans/2026-04-28-wf-asset-provider-pure-python.md) | **Status unknown** | Files exist and a commit claims done, but the plan has no completion marker and the Rust crate still exists — needs verification. |
| 2026-04-28 | [Plan: Blender asset browser plugin](docs/plans/2026-04-28-blender-asset-browser-plugin.md) | **Closed 2026-04-28** | v1 (Poly Haven CC0) → v2 (Sketchfab + licence filter) → pure-Python rewrite all landed, with a `manifest.json` provenance record. |
| 2026-04-19 | [Plan: python-tui-lib extraction](docs/plans/2026-04-19-python-tui-lib-extraction.md) | **Closed 2026-04-19** | Carved the reusable TUI subset out of parking-space into a standalone repo and consumed it via submodule, with a `?`-key help overlay. |
| 2026-04-16 | [Plan: git-branch-browser](docs/plans/2026-04-16-git-branch-browser.md) | **Closed 2026-04-19** | A Python curses program surfacing branch topology as a chronological waypoint pipeline with fork detection and three diff modes; v2 verified under a pty. |
| 2026-04-16 | [Plan: Android port](docs/plans/2026-04-16-android-port.md) | **Closed 2026-04-18** | Phases 0–3 fully landed including the on-device smoke test and post-boot polish; remaining polish split into separate plans. |
| 2026-04-15 | [Dead-code removal](docs/plans/2026-04-15-dead-code-removal.md) | **Closed 2026-04-18** | Batches 1–7 cut the tree 64,252 → 36,199 LOC (−43.7%), verified against git history; Batch 8 (`physics/wf/`) deferred. |
| 2026-04-16 | [Plan: Lua engine is not special](docs/plans/2026-04-16-lua-not-special.md) | **Done** | Lua extracted behind `WF_LUA_ENGINE=lua54\|none` and made as optional as any other engine. |
| 2026-04-16 | [Engine directory reorganization](docs/plans/2026-04-16-engine-directory-reorganization.md) | **Complete** | `engine/` promoted to a top-level directory; `wftools/` is now strictly dev tooling. |
| 2026-04-16 | [Finish Jolt physics integration](docs/plans/2026-04-16-jolt-physics-finish.md) | **Complete** | Five-step plan (SIGABRT, zombie bodies, authority model, vertical pop, 60 s soak) complete; the player walks on the snowgoons floor. |
| 2026-04-15 | [Lua engine fixes (#1–#6)](docs/plans/2026-04-15-lua-engine-fixes.md) | **Complete** | All six fixes (cache, per-actor envs, Fennel precompile, debug gating, stdlib sandbox, coroutine continuations), smoke-tested. |
| 2026-04-15 | [Align scripting plans to ScriptRouter](docs/plans/2026-04-15-scripting-plans-align-scriptrouter.md) | **Complete** | All plan docs + namespaces aligned; WAMR/Wren/Forth landed and all engine smoke tests passed. |
| 2026-04-14 | [WAMR (dev interp + AOT ship)](docs/plans/2026-04-14-wamr-dev-aot-ship.md) | **Complete** | Phase 1 classic interpreter landed and smoke-tested; AOT (Phase 2) and w2c2 (Phase 3) deferred until ship targets are concrete. |
| 2026-04-14 | [Forth scripting engine](docs/plans/2026-04-14-forth-scripting-engine.md) | **Complete** | All seven phases landed; zForth is the default and smoke-tested, the five alternate backends are build-verified only. |
| 2026-04-14 | [Pluggable JS engines (QuickJS / JerryScript)](docs/plans/2026-04-14-pluggable-scripting-engine.md) | **Complete** | Both engines landed under the `js_engine` namespace and smoke-tested on snowgoons. |
| 2026-04-14 | [Wren scripting engine](docs/plans/2026-04-14-wren-scripting-engine.md) | **Complete** | All phases (vendor, plug, dispatch, build, docs, patcher) complete and smoke-tested. |
| 2026-04-14 | [WebAssembly (wasm3)](docs/plans/2026-04-14-wasm3-scripting-engine.md) | **Retired 2026-04-16** | Initial wasm spike, retired once WAMR reached parity; sources deleted and `WF_WASM_ENGINE=wamr` is the only wasm option. |
| 2026-04-14 | [Fennel on Lua](docs/plans/2026-04-14-fennel-on-lua.md) | **Complete** | `;` sigil sub-dispatch inside `lua_engine` with vendored Fennel 1.6.1, minifier, codegen, and snowgoons Fennel scripts. |
| 2026-04-14 | [Vendor Lua 5.4](docs/plans/2026-04-14-vendor-lua.md) | **Complete** | Lua 5.4.8 compiled directly from source, no system `liblua5.4` dependency. |
| 2026-04-13 | [Lua interpreter spike](docs/plans/2026-04-13-lua-interpreter-spike.md) | **Complete** | Landed and refactored into the `lua_engine` ScriptRouter namespace; snowgoons player/director ported, movement and camera cuts work. |

---

## Investigations

| Date | Investigation | Status | Summary |
|------|---------------|--------|---------|
| 2026-05-22 | [Blender-snowgoons renders untextured](docs/investigations/2026-05-22-blender-snowgoons-untextured.md) | **✅ RESOLVED** | It was the camera, not textures — a CamShot exported Fixed/Absolute instead of Track/Relative, so the cam parked at a static gray view. The earlier euler-shuffle lead was a misread. |
| 2026-05-15 | [WF coordinate system, Euler angles, and `currentDir()`](docs/investigations/2026-05-15-wf-coordinate-system-and-currentdir.md) | **Complete** | `currentDir()` returns `(cos C, sin C, 0)`, not `(sin C, cos C, 0)` as the comment claims; the full radian→revolution→sin/cos chain is traced and the side-scroller recipe documented. |
| 2026-04-29 | [Blender Game Engine removal — history, gap, WF's fit](docs/investigations/2026-04-29-blender-game-engine-removal.md) | **Complete** | History of BGE removal and why the Godot recommendation missed the point — integration was the product, not the renderer. |
| 2026-04-29 | [World Foundry vs. Godot — technical comparison](docs/investigations/2026-04-29-world-foundry-vs-godot.md) | **Complete** | Technical snapshot across renderer, physics, scripting, tooling, world model, audio, networking, platforms, and licensing. |
| 2026-04-29 | [WF camera system — projection, FOV, CamShot, Director](docs/investigations/2026-04-29-camera-system-audit.md) | **Complete** | Perspective-only today; an orthographic `Mat4Ortho` path is ~½ day of work, gated on a Phase E OAD schema change. |
| 2026-04-29 | [World Foundry camera system](docs/investigations/2026-04-29-camera-system.md) | **Complete** | Anatomy of movecam/camshot/camera/actboxor — how CamShot keyframes, the Director, and ActBoxor drive cuts and room transitions. A reference for camera scripting. |
| 2026-04-29 | [Forth compile vs. run separation](docs/investigations/2026-04-29-forth-compile-run-audit.md) | **Complete** | Compile/run separation is correctly handled in `scripting_zforth.cc`; a level-load pre-compile pass is feasible but deferred until hitching is observed. |
| 2026-04-29 | [Godot Remote Debugger Protocol](docs/investigations/2026-04-29-godot-remote-debugger-protocol.md) | **Complete** | Naming and wire protocol for Godot's TCP game-state bridge, used to inform Phase 2b naming of WF's live-editor bridge. |
| 2026-04-29 | [C++ RTTI usage audit](docs/investigations/2026-04-29-rtti-audit.md) | **Complete** | 51 `dynamic_cast` calls found; RTTI was introduced in 2003 when `Actor*` containers generalised to `BaseObject*`. Fed the RTTI elimination plan. |
| 2026-04-28 | [Level authoring comparison — hand-crafted vs Blender](docs/investigations/2026-04-28-mm-practice-authoring-comparison.md) | **Complete** | Both paths produce a runnable level; Blender round-trip iterates tighter, hand-crafted `.lev` is faster for geometry-only test levels. |
| 2026-04-28 | [WF engine capabilities survey](docs/investigations/2026-04-28-engine-capabilities-survey.md) | **Snapshot** | Descriptive snapshot of renderer/physics/scripting/audio/platforms at branch HEAD; a reference baseline for genre-fit discussions. |
| 2026-04-28 | [Level-construction tooling](docs/investigations/2026-04-28-level-construction-tooling.md) | **Survey** | What tooling investments accelerate brief→playable level — Blender plugin gaps, LLM-assisted gen, CC0 sourcing, and the game-ideas dependency graph. |
| 2026-04-28 | [Console controllers since N64/PS1/Xbox eras](docs/investigations/2026-04-28-mainline-console-controllers-since-1996.md) | **Reference catalog** | Exhaustive catalog of controller hardware from 1996 to present, grounding input-remapping and gamepad-layout decisions. |
| 2026-04-28 | [VR/AR headset support](docs/investigations/2026-04-28-vr-ar-headset-support.md) | **Survey** | Engine-side gap analysis for VR/AR plus a catalog of in-production headsets; reference for any future headset decision. |
| 2026-04-19 | [Snowgoons build pipeline — Blender to running game](docs/investigations/2026-04-19-snowgoons-build-pipeline.md) | **Working end-to-end** | One-stop reference for every tool in the snowgoons build chain, in run order, with inputs and outputs. |
| 2026-04-19 | [OAD ButtonType audit — iff2lvl vs levcomp-rs](docs/investigations/2026-04-19-oad-buttontype-audit.md) | **In progress** | Cross-references all 29 `ButtonType` variants against how iff2lvl and levcomp-rs emit each, to catch divergence. |
| 2026-04-19 | [`.offsetof` arithmetic in iffcomp](docs/investigations/2026-04-19-iffcomp-offsetof-arithmetic.md) | **Recommendation accepted** | Oracle vs current `.offsetof` behaviour while reconstructing `snowgoons.iff.txt` for byte-identical output. |
| 2026-04-19 | [`_PathOnDisk.base.rot` mystery bytes](docs/investigations/2026-04-19-path-base-rot-oracle-mystery.md) | **In progress** | An email to the original WF team about unexplained oracle bytes from a `new char[]` allocator in `path.cc`. |
| 2026-04-18 | [Android port — executable size and RAM](docs/investigations/2026-04-18-android-port-size-and-ram.md) | **In progress** | Executable-size and RAM measurements for the arm64 debug APK. |
| 2026-04-18 | [Closing the Android Port](docs/investigations/2026-04-18-android-port-closure.md) | **Playable APK shipped** | Remaining-work writeup for the Android port; a playable APK has shipped. |
| 2026-04-17 | [IFF format lineage — EA IFF 85, AIFF, RIFF, WF IFF](docs/investigations/2026-04-17-iff-format-lineage.md) | **Complete** | Traces all four formats from the 1985 ancestor; WF uniquely separates text interchange from platform binary and aligns chunks to CD sectors. |
| 2026-04-16 | [Reverse-engineering the WF binary level format](docs/investigations/2026-04-16-levcomp-rs-reverse-engineering.md) | **Phase 2c complete** | Binary format fully mapped (mesh bbox, packed asset IDs, `asset.inc`, 37 objects validated); real path/channel keyframes remain. |
| 2026-04-16 | [Coding-conventions remediation](docs/investigations/2026-04-16-coding-conventions-remediation.md) | **In progress** | Honest audit of where recent 2026-authored code doesn't yet follow the conventions it proposes. |
| 2026-04-15 | [LOC tracking](docs/investigations/2026-04-15-loc-tracking.md) | **Ongoing** | Tracks LOC over time — 64,252 → 36,199 (−43.7%); retiring the legacy physics backend projects to ~−45.3%. |
| 2026-04-14 | [Scripting language replacement](docs/investigations/2026-04-14-scripting-language-replacement.md) | **Complete** | Survey that recommended Lua 5.4 as the primary engine and spawned all scripting plans. |
| 2026-04-14 | [Physics engine survey](docs/investigations/2026-04-14-physics-engine-survey.md) | **Complete** | Surveyed Bullet/PhysX/Rapier/Jolt and recommended Jolt (MIT, ~300 KB, CharacterVirtual, active upstream); spawned the integration plan. |
| 2026-04-14 | [Jolt Physics integration](docs/investigations/2026-04-14-jolt-physics-integration.md) | **Functional** | Jolt is the default and snowgoons is playable; legacy `physics/wf/` retained pending parity on a second level. |
| 2026-04-14 | [Remove audio subsystem](docs/investigations/2026-04-14-remove-audio.md) | **Complete** | The old non-functional Linux audio stubs were deleted, to be replaced by miniaudio. |
| 2026-04-13 | [ButtonType × showAs coverage audit](docs/investigations/2026-04-13-showas-coverage.md) | **Complete** | Audited all OAD field type × showAs combinations against the Blender plugin; gaps identified and fixed. |
| 2026-04-11 | [iffcomp — Rust rewrite](docs/investigations/2026-04-11-iffcomp-rs-rewrite.md) | **Complete** | Rust port byte-exact against the C++ oracle, with a comprehensive torture test. |
| 2026-04-11 | [iffcomp — Go rewrite](docs/investigations/2026-04-11-iffcomp-go-rewrite.md) | **Complete** | Go port byte-exact against the oracle; primary at the time, now superseded by Rust. |
| 2026-04-11 | [iffcomp — C++ modernization](docs/investigations/2026-04-11-iffcomp-modernization.md) | **Complete** | Modernized the 1996 flex/bison code to build on modern compilers; now serves as the byte-exact oracle. |
| 2026-04-14 | [Audio: sound effects, music, positional sound](docs/investigations/2026-04-14-audio-sound-music.md) | **Phases 1–5 complete** | SFX, MIDI, per-level music, a Lua surface, and 3D positional SFX all landed; mobile/docs and the mailbox-wired API for non-Lua engines are deferred. |
| 2026-04-14 | [Constraint-based props](docs/investigations/2026-04-14-constraint-based-props.md) | **Deferred** | Doors/chains/pulleys/elevators via Jolt constraints; the hard prerequisite (Jolt landing) is met but IFF binary chunks are still needed. |
| 2026-04-14 | [Multiplayer, voice chat, mobile input](docs/investigations/2026-04-14-multiplayer-voice-mobile-input.md) | **Deferred** | Surveyed multiplayer sync models, voice SDKs, and mobile input; blocked on the mobile port landing first. |
| 2026-04-14 | [REST API box PoC](docs/investigations/2026-04-14-rest-api-box-poc.md) | **Complete** | Embedded cpp-httplib server in `wf_game` creating/recoloring/resizing/deleting GL wireframe boxes at runtime. |

---

## Reference

| Date | Document | Summary |
|------|----------|---------|
| 2026-05-21 | [wf-edit user manual](docs/wf-edit-manual.md) | How to build, run, and use the collaborative editor (layout, OAD editing, live preview, save+compile, voice/video, automation env-vars, v1 limits), with screenshots throughout. |
| 2026-04-16 | [Scripting languages in WF](docs/scripting-languages.md) | Survey of all engines covering integration surface, binary/RAM cost, compile-time switches, and reference scripts. |
| 2026-04-16 | [Coding conventions](docs/coding-conventions.md) | Authoritative C++ style guide for WF runtime code; subsumes the old `codingstandards.txt`. |
| 2026-04-15 | [JerryScript GCC 14 build fixes](docs/reference/2026-04-15-jerryscript-gcc14-build-fixes.md) | Documents seven GCC 14 build failures in JerryScript v3.0.0 and how they were fixed. |
| 2026-04-14 | [Compile-time switches](docs/reference/2026-04-14-compile-time-switches.md) | Generated catalogue of 929 unique `#ifdef` switches across the codebase. |
| 2026-04-14 | [WF viewer design notes](docs/reference/wf-viewer.md) | The standalone geometry-viewer approach, superseded by `wf_game` running end-to-end. |
| 2026-04-14 | [Production pathway diagram](docs/reference/production-pathway.md) | Mermaid diagram of the original `.oas`/editor → `cd.iff` pipeline and where each tool fits. |
| 2026-04-13 | [Blender → cd.iff pipeline](docs/reference/2026-04-13-blender-to-cd-iff-pipeline.md) | Maps the existing pipeline and proposes the Blender-native replacement for the 3DS Max content path. |
| 2026-04-13 | [OAS / OAD format](docs/reference/2026-04-13-oas-oad-format.md) | Documents the object-attribute source (OAS) and compiled descriptor (OAD) binary format used by `wf_blender` and oas2oad-rs. |
| 2026-04-12 | [Steam shipping plan](docs/reference/2026-04-12-steam-shipping-plan.md) | Enumerates runtime blockers (build system, dialect, HAL, graphics, scripting), most now resolved; packaging itself not started. |
| 2026-04-11 | [wftools rewrite analysis](docs/reference/2026-04-11-wftools-rewrite-analysis.md) | Recommends which of ~23 `wftools/` directories to drop, rewrite (Go/Rust), or replace with off-the-shelf tools. |
| 2026-03-22 | [WorldFoundry Engine: Code Analysis & Opinions](docs/investigations/2026-03-22-engine-code-analysis.md) | External deep-dive concluding WF is a serious, disciplined, professionally-architected engine for the PS1 era, with many patterns still good today. |

---

## Blockers

No hard blockers — Jolt is functional and all scripting engines are smoke-tested; active areas of ongoing work are listed in the TODO below.

---

## TODO

### Scripting
- **WAMR Phase 2 (AOT)** — deferred; offline `.wasm`→native compile, ISA-specific blobs, ~10 KB loader vs ~107 KB interp. Revisit when ship targets are concrete.
- **wasm3 retired** — done 2026-04-16; sources removed, `WF_WASM_ENGINE=wamr` is the only wasm option.
- **Lua remote step debugger** — explicit "later" request: wire MobDebug/DBG.lua/LuaLS-DAP into the Lua interpreter.
- **Fennel macros / `require`** — `fennel.searcher` / `package.searchers` plus a `.fnl` build step.
- **Coroutine smoke test** — fix #6 landed but untested end-to-end with a real yielding script.
- **wasm module cache** — reuse compiled modules across `RunScript` calls (needed before wasm in hot-loop scripts).
- **Binary IFF chunk types** — `WSM`/`AOT` tags with explicit length; drop base64 for ~33% asset shrink.
- **Cross-language API parity** — typed accessors must stay consistent across engines; no canonical IDL yet.
- **`WF_DEFAULT_ENGINE` knob** — for Lua-off builds, select the sigil-less fallthrough engine; currently undefined.
- **Lua → JS / Lua → Wren converters** — mirror `tcl_to_lua_in_dump.py`.
- **Load level by filename from CLI** — done; `-L<path>` bypasses `cd.iff`.

### Physics
- **Remove `physics/wf/`** — kept until Jolt passes parity on another level; removal is a separate reviewable commit.
- **Constraint-based props** — doors/chains/pulleys via Jolt; blocked on parity + IFF binary chunks.

### Dead code
- **Batch 8** — Jolt replaces WF physics (in progress).
- **`hal/_list` + `hal/_mempool` migration** — refactor `MsgPort` onto `cpplib`/`memory`, then delete the HAL remnants.
- **`eval/` (120 LOC)** — tool-side callers need porting to the Blender plugin first.

### Content pipeline
- **Blender → `cd.iff` pipeline** — Phases 2a–2c landed (37 objects, valid Jolt bodies); real path/channel keyframes remain.
- **iffcomp: Rust is primary** — four implementations pass the torture test; Rust (`iffcomp-rs/`) is going-forward, C++ is the oracle, Go/Node.js superseded.

### Larger / deferred work
- **Audio (miniaudio)** — Phases 1–5 complete; the API is Lua-only (not mailbox-wired), so the other seven engines can't trigger music or SFX.
- **Mobile port** — Android Phases 1+2 done; immediate-mode-GL retirement step 4c (real directional-lighting/fog/matte shader ports, not stubs) remains, and iOS is blocked on Android.
- **Multiplayer / voice / mobile input** — blocked on the mobile port.
- **Steam packaging** — Phases 1+2 done; depot build + store page deferred, blocked on a Steamworks partner account and capsule art.

---

## Last Change

**2026-05-25** — SMB pit/fall death + level countdown timer: a below-gap `ActBox` and a 400-unit Director countdown both feed Mario's existing respawn (−1 life), so falling into a pit or running the HUD timer to "TIME UP" now costs a life. See [plan](docs/plans/2026-05-25-smb-pit-death-and-level-timer.md).
