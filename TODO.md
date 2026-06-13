# TODO

## Open

### Platform / Display

- [ ] **macOS: `-fullscreen`, `-width=N`, `-height=N` window flags.** Linux uses `_NET_WM_STATE_FULLSCREEN` via X11. macOS needs the equivalent using AppKit (`NSWindow` frame sizing + `toggleFullScreen:` / `NSWindowStyleMaskFullScreen`) in the macOS platform HAL. Tablets (Android/iOS) are always fullscreen by OS design. [plan](docs/plans/2026-06-04-window-size-parity-fullscreen-flag.md)
- [~] **Backface culling — flip `WF_CULL` default ON after rewinding shipped meshes.** Mechanism shipped (default-OFF, `WF_CULL=1` opt-in; the dome is the first correct consumer). Remaining: several shipped generators are wound **inward** (box/disk "top" faces → −Z normals: `add_solid_box`/`make_box_mesh`/`disk_geo`); audit + rewind shipped level meshes to consistent normals (entangles with one-sided lighting + the `FACE_COLOR` override), then flip the default on. [plan](docs/plans/2026-06-13-planetarium-dome-view-engine-wide-backface-culling.md)
- [ ] **macOS Metal renderer.** iOS Metal backend exists; macOS desktop is still on GL stubs. Needs a real Metal renderer + window (shared with iOS), then re-enable Jolt + full scripting roster on macOS once headless is green. [investigation](docs/investigations/2026-05-26-macos-port-estimate.md)
- [ ] **iOS Phase 3+ / Android launcher polish** — adaptive icon XML, foreground/background drawables. [plan](docs/plans/2026-04-18-android-launcher-polish.md)
- [ ] **Android size trim iter 2 — miniaudio Vorbis trim + Windows-path deletion** (the `-fno-exceptions` / `-fvisibility=hidden` halves already shipped). [plan](docs/plans/2026-04-18-android-size-trim-iter-2.md)
- [ ] **Audio assets from IFF** — bundle MIDI/SF2/WAV inside `cd.iff`; retire loose-file audio loaders. [plan](docs/plans/2026-04-18-audio-assets-from-iff.md)
- [ ] **Steam Phases 3+4** — SteamPipe depot + build script; store page on Steamworks. [plan](docs/plans/2026-04-17-steam.md)
- [ ] **Chromecast/Google TV Phase 2** — on-device verification on physical hardware + CI (banner image already shipped). [plan](docs/plans/2026-04-23-chromecast-googletv-port.md)
- [ ] **Tech debt: `__LINUX__` aliased to mean POSIX on macOS/iOS — replace with `WF_POSIX`.** `pigsys/pigsys.hp` makes `cf_linux.h` the include for Darwin too, so any `#ifdef __LINUX__` guard silently covers macOS. Safe today; fragile if future `epoll`/`inotify`/`/proc` use lands under `__LINUX__`. Introduce `WF_POSIX` for shared Darwin+Linux paths; grep-and-replace sweep across `pigsys/`, `hal/`, `gfx/`, `audio/`. Trigger: before macOS Metal work starts.

### Scripting

- [ ] **Lua remote step debugger** — MobDebug / LuaLS-DAP wired into `lua_engine` for in-game step debugging.
- [ ] **Review actor variable space w.r.t. scripting languages** — audit whether per-actor `_ENV` (Lua), JS object state, wasm linear memory, and Fennel locals all play well with the fixed-size mailbox array; document per-language limits.
- [ ] **Review `write-actor-mailbox` — consider removing.** Custom syscall id 2 ([`engine/stubs/scripting_zforth.cc`](engine/stubs/scripting_zforth.cc)) lets one actor poke another's local mailbox (action-at-a-distance). Architecturally cleaner alternative is the signal-mailbox pattern in [`docs/level-building.md`](docs/level-building.md#mailbox-scope-rules). Only the qbert cube-colour fan-out uses it; weigh removal vs leaving a sharp tool in the box.
- [ ] **Finish "priorities working in updates" — per-tick script execution ordering.** [`level.cc`](wfsource/source/game/level.cc) (~:978) has a hardcoded Director-after-loop special case ("FIX - manually update director until we get priorities working in updates"). No priority/phase mechanism for actor scripts → signal-mailbox chains incur a 1-tick lag at the consumer. Fix: add a `Priority`/`Phase` field to `common.inc`; sort the actor-update iteration by it. Trigger: when a level surfaces a noticeable lag. [docs/level-building.md](docs/level-building.md)
- [ ] **Neural-forth pool size constants as OAD fields** (`NF_MAX_TENSORS`, `NF_MAX_PARAMS`, `NF_SLOT_VOCAB_SIZE`, …) — expose per-actor limits so complex AI nets can opt into larger pools without paying the cost globally.

### Camera & Rendering

- [ ] **Snowgoons-import fog trap: inherited Earth-fog defaults grey out distant terrain.** Levels scaffolded off snowgoons inherit `FoggingColor=0x888888`, `FoggingStartDistance=20`, `FoggingCompleteDistance=30` → any pixel past ~30 m fades to flat `#888888`. Workaround overrides the three fields per-level; consider adding an opt-in "strip snowgoons fog" to `wf_blender` import_level. [plan](docs/plans/2026-05-31-uninitialised-fog-defaults.md)

### Engine Robustness

- [ ] **`ActBox` writes `Activated Actor Mailbox` unconditionally — its default (0) is a reserved mailbox → abort.** [`actbox.cc`](wfsource/source/game/actbox.cc) (`:84`, `:131`) always `WriteMailbox(getOad()->ActivatedActorMailbox, …)`, but that field defaults to 0 and `mailbox.cc:63` asserts `mailbox >= 2` — so a default-config ActBox aborts the instant it fires. Considered fix (deferred): guard both writes with `if (ActivatedActorMailbox >= 2)`. Current workaround points it at a scratch slot. [plan](docs/plans/2026-05-25-smb-flagpole-end-of-level.md)
- [ ] **Actor identity / safe handles (generation-ID) to make index references reuse-safe.** Actors are referenced by a bare slot index with no generation/serial, and freed slots are reused, so any cached index can silently alias a different actor after a despawn. Proper cure: a `uint32` generation on `BaseObject`, a safe `ActorRef{idx,gen}` + `Level::Resolve(ActorRef)`. Surfaced fixing the camera stale-track crash. [plan](docs/plans/2026-06-13-camera-stale-track.md)
- [ ] **`long`→`int32` in [`gfx/gl/wfprim.h`](wfsource/source/gfx/gl/wfprim.h) — it's LIVE, not dead.** `Point3D{long x,y,z}` (16.16 fixed-point coords), PSX `SPRT_16`/`DR_MODE` packed words, `psxRECT`. Retype coords + packed words to `(u)int32` carefully (layout-sensitive rendering structs). Only `GfxLoadImage` + the `OTag` name are truly dead. [long audit F7](docs/plans/2026-05-20-runtime-long-audit.md)
- [ ] **IFF chunk names aren't a first-class FourCC type (audit + cleanup).** [`IFFTAG`](wfsource/source/iff/iffread.hp) expands to a bare `uint32` while the `ChunkID` wrapper exists but is never produced, so dispatch unwraps via `.ID()`. Make `FourCC` a real 4-byte type, have `IFFTAG`/`ChunkID` yield it, switch on it directly, and model fixed-width chunk records. Surfaced reviewing the long-audit `rendcrow` fix.
- [ ] **`Scalar(int32)` constructor is ambiguous — callers must cast explicitly.** `Scalar(long)`/`Scalar(float)` are both `explicit` but `int32` converts to neither without a cast. Fix: add an `explicit Scalar(int32)` overload in `math/scalar.hp`/`.hpi`. Surfaced when `Gold::Collision` called `Scalar(getOad()->GoldValue)`.
- [ ] **Make the fixed-point math's 64-bit `long` intermediates explicit (`int64`).** The Scalar/vector core uses bare `long` for 16.16 multiply/divide/sqrt/dot intermediates — correct on every WF ABI but doesn't *say* "64-bit." Clarity-only (no-op on LP64). Two deferred decisions: add WF `int64`/`uint64` typedefs to `pigtypes.h` vs raw `int64_t`; uniform-`int64` vs split intermediates/value-API. [long audit](docs/plans/2026-05-20-runtime-long-audit.md)

### Physics

- [ ] **No restitution / bounce for gameplay actors (PHYSICS).** Every `MOBILITY_PHYSICS` actor becomes a kinematic Jolt `CharacterVirtual` (zeroes vertical velocity on landing); the backend never sets `mRestitution`, and the `Vertical/Horizontal Elasticity` OAS fields are dead legacy. To get true bounce: add a dynamic-rigid-body mobility and wire Elasticity into Jolt `mRestitution`. Pairs with the physics-replacement follow-up.
- [ ] **`Surface Friction` + air-drag OAD fields are non-functional under Jolt (dead knobs).** `MarbleHandler::predictPosition` ([`movement.cc:689`](wfsource/source/movement/movement.cc)) decays velocity solely by `Running Deceleration`; the wheel-friction path that read `Surface Friction` is skipped (no `supportingObject` for a Jolt CharacterVirtual). Decide: wire these into the Jolt movement path, or formally retire them. [troubleshooting doc](docs/level-design-troubleshooting.md)
- [ ] **Per-actor render scale (`EMAILBOX_X/Y/Z_SCALE` 3040–3042) does not scale collision or physics.** Scale forwards to `RenderActor3D::SetActorScale` (visual only); never touches the collision bbox or the Jolt shape — a silent desync. Real fix is physics-correct instance scale via OAD fields (see Parked → *Physics-correct instance scale*). [troubleshooting doc](docs/level-design-troubleshooting.md)
- [ ] **Rideable moving platforms — Jolt ground-velocity carry (`Mobility=Path` / scripted mover).** The carry logic exists only in the legacy non-Jolt path; the Jolt `GroundHandler` branch ([`movement.cc:432`](wfsource/source/movement/movement.cc)) sets a rider's velocity to joystick-only and `supportingObject = NULL`. Bounded fix: add `JoltCharacterGetGroundVelocity()` wrapping `CharacterVirtual::GetGroundVelocity()`, add ground velocity to the character XY, give movers a KINEMATIC pose-driven body, route `MOBILITY_PATH` through body creation. Then retrofit W1-3's 3 static stand-ins + W1-2's end lifts. [plan](docs/plans/2026-06-03-build-faithful-smb-w1-3.md)
- [ ] **textile-rs Phase 2** — diagnose 2 non-square texture mismatches (`G_HedgeWsnowSide`, `G_shakesWsnowRM`); package texture outputs into the pipeline. [plan](docs/plans/2026-04-19-textile-rs-validation.md)

### Collaborative Editor

- [ ] **Deeper "fail-clean": engine-side `ConstructTemplateObject` fail-soft.** The `wfmut::SpawnActor` kind-guard landed (rejects Room/Tool/StatPlat before the call), but the deeper cause is that the engine's `ConstructTemplateObject` ([`objects.c`](wfsource/source/oas/objects.c)) `terminate()`s on *any* unmet prerequisite. Make it fail-soft (return NULL) to cover all kinds **and** let [`engine_bridge.cc`](engine/wf_edit/engine_bridge.cc)'s `RunSpawnConfirmTest` be un-deferred. The `-fexceptions` host-lib escape hatch stays deferred. [plan](docs/plans/2026-06-02-editor-fail-clean-nuggets.md)
- [ ] **Drop the `wfcrdt` nested-map workaround — y-crdt bump trigger has FIRED (submodule now `v0.26.0`).** The committed submodule pin is `v0.26.0` (not the `v0.9.3` the workaround assumed). But cleanup was never done: `fill_map`/`fill_array` still live in [`engine/crdt/wfcrdt.cpp`](engine/crdt/wfcrdt.cpp) (`:312`/`:315`) and `docs/patches/yrs-0.9.3-yinput-ymap-integrate-loop.patch` still exists. Now-actionable: verify a prefilled `yinput_ymap` integrates correctly on 0.26 (FFI was refactored upstream — re-check), collapse `fill_map`/`fill_array` to a direct prefilled insert, delete the patch. ⚠ Also: the submodule working tree shows uncommitted "modified content" — resolve it. [plan](docs/plans/2026-05-22-yrs-upgrade-and-native-undo.md)
- [ ] **Decompose `HALStart` into `HALInit`/`HALShutdown` (editor approach (b)).** Today [`HALStart`](wfsource/source/hal/hal.cc) is monolithic (init → `PIGSMain` → teardown), so a host can't init, own a `WFGame`, and drive `StepFrame` from its own loop without `PIGSMain`. The editor uses approach (a) (`--editor` `RunEditor` callback). (b) splits `HALStart` so the editor owns the loop outright. Catch: the scoped scratch `LMalloc` must become heap-managed. Trigger: when (a)'s callback inversion chafes. [plan](docs/plans/2026-05-20-editor-app-shell.md)
- [ ] **Editor: re-bake a moved statplat's per-room collision (currently best-effort until save+reload).** Moving a StatPlat works without aborting and the mesh + Jolt body follow the gizmo live, but the static per-room collision baking isn't recomputed live — only correct after save + reload. For full-fidelity preview, re-bake the moved statplat's room/collision in editor mode after the move settles. Trigger: when stale live collision becomes a real authoring annoyance. [investigation](docs/investigations/2026-05-25-wf-edit-statplat-move-abort.md)
- [ ] **Editor v1 relay persistence — BYOK `wrap: fn(&[u8]) -> Vec<u8>` seam.** Snapshotting itself shipped (rotating `.ydoc`, debounce, idle hibernation, load-newest-on-rejoin). The remaining piece is the `wrap` hook (identity today; "encrypt with customer KMS key" for v2 BYOK) so snapshots never need re-encrypting on retrofit — one struct field in [`relay.rs`](wftools/wf_collab/src/bin/relay.rs).

### Tools & Pipeline

- [ ] **OAS codegen drops `SHOW_AS_TEXTEDITOR` for the Notes field → Notes is never drawn in the editor.** `xdata.inc`'s `TYPEENTRYXDATA_NOTES` passes `SHOW_AS_TEXTEDITOR`, but the binary `.oad` (via [`oas2oad-rs`](wftools/oas2oad-rs)) emits `BUTTON_XDATA` + `SHOW_AS_N_A`, so `WidgetFor` maps it to `FieldKind::Skip`. Fix `oas2oad-rs` to honor the `showas`, regenerate the `.oad`s, and the dormant Notes-Markdown render lights up with no editor change.
- [ ] **Blender export uses a STALE OAD dir — canonical OAD fields can't be authored.** [`wflevels/smb_w1_1/blender_create_smb.py:38`](wflevels/smb_w1_1/blender_create_smb.py) sets `OAD_DIR` to `wftools/wf_oad/tests/fixtures`; the fixtures `gold.oad` predates `Gold Value`, so the field silently drops from the exported `.lev` (un-authorable). Fix: repoint `OAD_DIR` to `wfsource/source/oas` after confirming the rest stays byte-stable. [plan](docs/plans/2026-05-25-smb-gold-value-wire-and-doc-fix.md)
- [ ] **Move OAD schema fixtures out of test path.** Production code (`wflevels/qbert_practice/blender_create_qbert.py:46-47`) loads `STATPLAT_OAD`/`ENEMY_OAD` from `wftools/wf_oad/tests/fixtures/*.oad`. Schemas are first-class production artefacts — relocate to e.g. `wftools/wf_oad/schemas/` and update consumers.
- [ ] **`blender_asset_finder` OpenGameArt provider is broken; AmbientCG is flaky.** [`providers.py::OpenGameArt.search`](wftools/blender_asset_finder/providers.py) hits a dead JSON API (`field_art_type=3` → 404; 3D type is `tid=10`) and has an unconditional CC0-only gate that rejects CC-BY. Decide: (1) fix the OGA provider (HTML scrape + drop the CC0 gate), (2) deprecate ours and lean on BlenderMCP's Polyhaven/Sketchfab connectors, or (3) keep ours as the license-filter front-end calling BlenderMCP for fetches.
- [ ] **Game ideas dependency graph** — extract dependencies from `docs/game-ideas/` docs; build synthesis tooling. [plan](docs/plans/2026-04-28-game-ideas-dependency-graph-and-tooling.md)
- [ ] **`wflevels/cd_full.iff.txt` is stale — won't build against current level files.** References nonexistent `/tmp/L*_*.iff` paths and bare-includes `[ "snowgoons.iff" ]` at the `L4` slot **with no `{ 'L4' … }` wrapper** — but snowgoons roots at `LVAS`, so the binding has nothing to resolve. Regenerate to the wrapper form (cf. the correct `cd_snowgoons.iff.txt`) or delete it.
- [ ] **Consider 8-byte alignment in the IFF file format itself.** Chunks are 4-byte aligned (`iff/iffread.cc:55`); on 64-bit hosts every chunk with a pointer/`int64`/`double` payload lands 4-aligned-but-not-8. Bumping to 8 lets consumers read native types without copy. Tradeoff: re-emit all `cd*.iff` + standalone `.iff`s (cheap via Rust tools), audit reader sites. Worth doing alongside a future asset-pipeline bump; low priority alone.
- [ ] **BaseObject 2003 extraction.** [plan](docs/plans/2026-05-30-baseobject-2003-extraction.md)

### Naming & Hygiene

- [ ] **Rename `room`** — "room" is a misnomer; the concept is a designer-drawn zone that controls CD asset streaming. Candidates: **Zone** (most self-explanatory), **Cell** (Elder Scrolls precedent), **Sector** (Doom/Quake lineage), **Region**.
- [ ] **Q\*bert mailboxes** — replace raw mailbox numbers in [`blender_create_qbert.py`](wflevels/qbert_practice/blender_create_qbert.py), [`docs/qbert/catalogue.md`](docs/qbert/catalogue.md), and two raw-int holdouts in [`game.cc`](wfsource/source/game/game.cc) with `INDEXOF_*`/`EMAILBOX_*` names. [plan](docs/plans/2026-05-17-qbert-named-mailboxes.md) (~95 new `MAILBOXENTRY` rows)
- [ ] **Sweep: pre-increment standalone `++`/`--`, and `ARRAY_COUNT` for array bounds (partial).** Codifies [coding-conventions.md](docs/coding-conventions.md) §4: convert bare `i++;` to `++i`, replace hardcoded array bounds with `ARRAY_COUNT(arr)`. A few `i++;` / hardcoded bounds remain (e.g. `rendmatt.cc`). Run as a dedicated mechanical pass.
- [ ] **`Gold::Collision` is dead code for `MOBILITY_PHYSICS` coins — don't "fix" coin value there.** [`gold.cc:82`](wfsource/source/game/gold.cc) reads `GoldValue` but is never called for CharacterVirtual coins; the live pickup is `Gold::update()` → `TryPickup`. Cleanup: fold both into a shared helper, or delete `Collision` if CharacterVirtual coins stay the only `Gold` use.
- [ ] **`WF_EDIT_FAKE_PEER` + `WF_EDIT_AUTO_SELECT` + `WF_EDIT_AUTO_JUMP` cleanup decision.** Env-gated dev/screenshot aids; zero production cost but small maintenance surface. Tear down in a future cleanup pass if they become noise, keep as documented dev tools otherwise.

### Level / Gameplay

- [ ] **FSN browser design references — desktop filesystem visualizers.** Study for layout/encoding ideas: **KDirStat/QDirStat** ([QDirStat](https://github.com/shundhammer/qdirstat)) treemaps; **Filelight** ([source](https://invent.kde.org/utilities/filelight)) radial sunbursts.
- [ ] **Filesystem-viz family — remaining views.** Platform shipped (flat numeric table from C + per-view Forth Director); done views: filelight, fsn `filesys`, treemap, planetarium dome. **Open:** **Tiered monument** (#2) sunburst variant; **unified runtime view-switcher** (one level, mode mailbox cycles tree↔sunburst↔treemap↔tiered↔dome); **procedural single-mesh** upgrade (exact sectors via one runtime `RenderObject3D`). [plan](docs/plans/2026-06-13-filesystem-viz-on-a-flat-table-forth-policy-core-f.md)
- [ ] **Marble-madness: script-based input remapping** — `Script Controls Input = True`; script reads raw joystick (1008), remaps, writes `EMAILBOX_INPUT` (3024). Current impl handles LEFT/RIGHT strafe in `movement.cc` (TurnRate==0 branch); the script approach is a viable future refactor. See `player.cc:192` for the passthrough pattern.
- [ ] **Object-model / class taxonomy — collectibles shouldn't masquerade as coins.** Mushroom/FireFlower/Star are all authored as `gold` actors with `Gold Value = 0` + a pickup script (the only stock class with the right walk-through + floor-landing collision profile). Real fix: a base `Collectible` (collision profile + pluggable pickup effect + despawn/TTL + visual) that `Gold`/`Mushroom`/`Star`/`1-Up`/`FireFlower` specialise. Four clones now exist (the trigger has fired). Pairs with the dead-`Gold::Collision` cleanup. [plan](docs/plans/2026-05-26-smb-super-mushroom-powerup.md)


## Watch

### Verify (interactive / live)

- **SMB coin no longer gets stuck on top of the `?` block** — couldn't reproduce at this machine's frame rate; confirm next interactive run. Repro tool: [`tests/observe_coin_landing.py`](tests/observe_coin_landing.py). If it recurs, suspect unclamped-dt coarse arc / spawn-Z offset / CharacterVirtual ground-snap.
- **SMB qblock: one head-bump = exactly one coin** — the qblock Forth re-pulses `SMB_QBLOCK_ACTIVATE` each tick while `COLLIDER_IDX ≠ 0`. In real play the engine resets `COLLIDER_IDX` when contact ends; confirm a single bump produces one coin (not one-per-tick) in interactive play.
- **SMB W1-4 headless mid-level screenshots come out black** — root cause NOT established; most likely a capture-method artifact (`Rotation=Fixed` camshot left aimed away after a discontinuous teleport), normal play probably renders fine. Play-test on `:0`; if a real bug, read camera (idx 1) actual X vs the camshot, check `Fixed`-rotation in [`movecam.cc`](wfsource/source/game/movecam.cc). [plan](docs/plans/2026-06-03-build-faithful-smb-w1-4.md)
- **Relay connect: live two-machine joiner over public `wss://`** — the code fix (host loopback connect + time-budget retry + `connect_retry.h`) landed and is unit-tested; steps 3–5 (a real two-machine joiner run) remain open. [plan](docs/plans/2026-06-01-relay-connect-localhost-and-resilient-retry.md)
- **Live two-instance collab-undo GUI wiring** — the origin-gating property is covered deterministically by `test_undo_local_only_across_sync`; this is belt-and-suspenders confirmation of `DoUndo`/`DoRedo` + `CollabDrain` via two DISPLAY-bound windows + the relay. Trigger: a live editor session, or a suspected collab-undo regression. [plan](docs/plans/2026-05-22-yrs-upgrade-and-native-undo.md)
- **wf-edit named tunnel — live verification** — needs a real Cloudflare account, can't be CI'd; checklist in the [plan](docs/plans/2026-05-30-quick-tunnel-named-tunnel.md).

### Monitor

- **zForth dictionary size** — append-only dict grows with every unique script word + all `INDEXOF_*` constants; fixed at `ZF_DICT_SIZE` (64 KB in `zfconf.h`, ~100 reloads). If level script count grows: bump `ZF_DICT_SIZE` or reinit `g_ctx` at level unload + replay bootstrap. [investigation](docs/investigations/2026-04-29-forth-compile-run-audit.md)
- **Never link `libwfcrdt.a` into `libwfengine.a`** — engine stays Rust-free (editor owns the Y.Doc). If a change appears to "simplify" by linking it in: STOP and re-open the design decision (would bloat every iOS/Android/`wf_game` binary with dead Rust, chain mobile CI to the Rust toolchain, couple engine ABI to Yrs churn). [plan](docs/plans/2026-05-18-yrs-c-abi-binding.md)


## Parked

### Deferred until level / phase

- Engine-side SMB scroll route — per-CamShot OAS fields (`Mode: SMB Scroll`) on [`camshot.oas`](wfsource/source/oas/camshot.oas) + inline branch in `NormalCameraHandler::_update()`; replaces the pure-Forth Director scroll. Unpark when a level needs it. [plan](docs/plans/2026-05-17-smb-scroll-engine-route.md)
- **Physics-correct instance scale via OAD fields** — scale render + collision bbox + Jolt `ScaledShape` together, authored as Blender object scale, persisted through the `.lev` pipeline (insertion points mapped: `decompile.rs`/`lev_parser.rs`/`lvl_writer.rs`/`export_level.py`). Proper fix for the visual-only render-scale bug + unblocks the wf-edit scale gizmo. Blocked on new OAS fields → after a new level ships.
- Hybrid Room-bbox fallback for SMB scroll bounds — when `Scroll Min X == Scroll Max X` (unset), fall back to the Room bbox; else use explicit values. Evaluate after a second multi-CamShot level exists.
- ScriptLanguage OAD field — re-add to `common.inc`; revert the `language = 3;` stopgap in `scripting_stub.cc`. (Phase E now clear; still gated by the no-new-OAS-fields-pre-merge policy.) [plan](docs/plans/2026-04-16-script-language-oad-field.md)
- Orthographic projection — `Mat4Ortho` + `SetProjectionOrtho()` + `orthographic: Bool` on `camshot.oas`; needed by Marble Madness / Crystal Castles / Miner 2049er. Whichever ships first pays the cost. [investigation](docs/investigations/2026-04-29-camera-system.md)
- Strip spurious BOX3 chunks from non-geometry actors in `wflevels/snowgoons/snowgoons.lev`. [plan](docs/plans/2026-04-19-strip-nongeom-box3.md)
- Per-level `MAX_ACTIVE_ROOMS` — currently compile-time constant. [plan](docs/plans/per-level-max-active-rooms.md)
- PILOT Phase 5 (language-aware hot-reload) + Phase 6 (turtle graphics: 2D `GR:` + 3D H/L/U-frame). [plan](docs/plans/2026-05-30-pilot-for-world-foundry-in-engine-object-script-la.md)

### Scripting engine variants

- `WF_DEFAULT_ENGINE` knob — sigil-less script fallback engine selection. [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- Collapse wasm sigil `#b64\n` → bare `#` — workaround for cd.iff `##` TCL lines; revert once cd.iff cleaned up.
- Alternate wasm sigil `#!wat` — deferred pending wabt vendor (won't be needed). [plan](docs/plans/2026-04-14-wasm3-scripting-engine.md)
- `scripts/check_iff_no_js.py` — JS footprint checker; blocked on JS scripts being authored into assets.
- `WF_JS_ENGINE=jerryscript-nano` footprint build — deferred until footprint pressure.
- WAMR Phase 2 (AOT ship path) + Phase 3 (w2c2 AOT backend). [plan](docs/plans/2026-04-14-wamr-dev-aot-ship.md)
- zForth Phase 2 — adopt the new tier-1/2 words in existing scripts (collapse `over over`→`2dup`, `swap drop`→`nip`, etc.); pure readability cleanup of `wflevels/*/blender_*.py`. [deferred plan](docs/plans/deferred/2026-06-02-adopt-new-forth-words-in-existing-scripts.md)
- Rename the `INDEXOF_` prefix on scripting-side mailbox constants to `MB_` — single-source at `scripting_stub.cc:72`, sed across all script source, re-export. Parked until the next mailbox-naming sweep (pairs with the qbert named-mailboxes item). [investigation](docs/investigations/2026-05-18-indexof-prefix-removal.md)

### Other deferred

- **Forth primitive: spawn template object with arbitrary runtime velocity / concurrent bursts.** The base `spawn-template` syscall shipped (used by filesys/filelight/dome) and Fire Mario's fireball shipped via a pooled teleported Generator (zero engine code). The remaining gap is what those can't express cheaply — arbitrary runtime velocity (a moved Generator's velocity is baked at load) or concurrent bursts from one spawner. Full syscall design (slot 4 / id 132) in [investigation](docs/investigations/2026-05-26-spawn-template-forth-primitive.md).
- wf-edit web — IDBFS cross-session persistence (`-lidbfs.js` + `syncfs`). ⚠ Do **not** persist `identity.json` wholesale (shared `peer_id` reintroduces the presence/chat self-drop); persist prefs, keep minting a per-tab `peer_id`. Low marginal value (relay snapshot already persists co-edit state). [plan](docs/plans/2026-06-12-wf-edit-in-the-browser.md)
- Up-hop vs down-hop arc asymmetry — climbing leaps heavier, falling snappier; a qbert 3D-only embellishment. Hold until the arcade copy is complete.
- Concurrency (the 1994 cooperative tasker is deleted) — if a use case arises, explore `std::thread` + work queue (background loading), C++20 coroutines (scripted AI), or a fiber library (closest to the original stackful model).
- Foundry Linux Phase 0 — split `install.sh` into per-metapackage scripts. (Lives in the sibling `linuxfoundry.org` repo, out of this tree.) [plan](docs/plans/2026-05-17-per-metapackage-install-scripts.md)

### Future evaluation

- **Post-v1: evaluate Qt as a replacement UI toolkit for the collaborative editor.** v1 ships on Dear ImGui. Once v1 is in real use, evaluate migrating to Qt (native widgets, `QOpenGLWidget` viewport, PySide). Trigger: v1 shipped + UX friction observed. No research before then. [investigation](docs/investigations/2026-05-18-collaborative-level-editor-design.md)


## Done

- [x] 2026-06-14 — [apt-task] `task` migrated to live cloudsmith `ubuntu/questing`; apt owns `/usr/bin/task` 3.51.1 (foundry winner + cloudsmith auto-update), shadowing manual binary removed. [plan](docs/plans/2026-06-13-fix-task-apt-source.md)
- [x] 2026-06-13 — [dome] Planetarium dome view — Filelight sunburst on a hemisphere; reuses `fl-scan` verbatim; first `WF_CULL=1` consumer. [plan](docs/plans/2026-06-13-planetarium-dome-view.md)
- [x] 2026-06-13 — [read-actor-mb] `read-actor-mailbox` cross-actor read (zForth syscall 24 + WASM parity); regression guard `wfmut_smoke` RA1. [plan](docs/plans/2026-06-13-add-read-actor-mailbox-to-the-scripting-engines.md)
- [x] 2026-06-13 — [cull-mech] Software backface culling mechanism (normal-vs-view dot, GL + Metal, honors `DOUBLE_SIDED`), opt-in `WF_CULL=1`. [plan](docs/plans/2026-06-13-planetarium-dome-view-engine-wide-backface-culling.md)
- [x] 2026-06-13 — [camera-track] Camera degrades gracefully on a stale/destroyed track index (shared non-asserting `ResolveTrackObject`); closes 134+135. [plan](docs/plans/2026-06-13-camera-stale-track.md)
- [x] 2026-06-13 — [treemap] KDirStat/QDirStat squarified disk-usage treemap view (`tm-scan`, 678 cells). [plan](docs/plans/2026-06-13-kdirstat-treemap-view.md)
- [x] 2026-06-13 — [rtcp-pli] RTCP PLI fast keyframe recovery both directions (~1 RTT vs ~1 s); guard `wf_edit_pli`. [plan](docs/plans/2026-06-13-rtcp-pli-keyframe-request.md)
- [x] 2026-06-13 — [video-race] Lazy-create per-peer video decoder so a keyframe beating presence isn't dropped; guard `wf_edit_video_race`. [plan](docs/plans/2026-06-13-fix-native-videochat-drops-the-keyframe-when-media.md)
- [x] 2026-06-13 — [web-av] wf-edit web voice+video over browser WebRTC (web↔web bidirectional + web↔native + 3-peer mesh). [plan](docs/plans/2026-06-13-web-editor-audio-video.md)
- [x] 2026-06-13 — [web-edit] wf-edit in the browser (WASM/WebGL2) — render/edit, CRDT sync, presence/chat, multi-peer join, one-click `.lev` export. [plan](docs/plans/2026-06-12-wf-edit-in-the-browser.md)
- [x] 2026-06-13 — [terminate] Clean debug-bridge listener teardown + shared de-noising `std::set_terminate` handler in `wf_game` + `wf_edit`; guard `wf_edit_terminate`. [investigation](docs/investigations/2026-06-13-terminate-masking-audit.md)
- [x] 2026-06-12 — [filesys] FSN filesystem browser level — recursive SGI-FSN tree, fly-down, walk-in descend/ascend, EVA astronaut (syscalls 136-139). [plan](docs/plans/2026-06-12-filesys-browser-level.md)
- [x] 2026-06-12 — [spawn-template] `spawn-template` Forth syscall (135) → `ConstructTemplateObject`; used by filesys/filelight/dome.
- [x] 2026-06-12 — [scalar-random] Fixed `Scalar::Random()` abort (RangeCheck cast `1<1` aborted every call, dormant since 2010). [`2fe49ef4`](https://github.com/wbniv/WorldFoundry/commit/2fe49ef4)
- [x] 2026-06-11 — [web-port] Web/canvas port (Emscripten/WebGL2) — `wf_game` live in-browser, 8 levels, ASYNCIFY dropped (wasm −34%). [plan](docs/plans/2026-06-11-web-canvas-port.md)
- [x] 2026-06-04 — [viewport-resize] Linux viewport resizes on window maximize/resize (ConfigureNotify inscribed-square math + FBO blit + per-frame projection). [plan](docs/plans/2026-06-04-viewport-doesn-t-resize-on-window-maximize.md)
- [x] 2026-06-04 — [fullscreen-flags] Linux `-fullscreen`/`-width=N`/`-height=N` window flags (X11 screen-dim query); `WF_FULLSCREEN`/`WF_RECORD` on all `task run-*`. [plan](docs/plans/2026-06-04-window-size-parity-fullscreen-flag.md)
- [x] 2026-06-04 — [pipeline-e] Multi-level `cd.iff` — W1-1→W1-2→W1-3→W1-4→W1-1 chain, all levels load. [`f5cd620e`](https://github.com/wbniv/WorldFoundry/commit/f5cd620e) [plan](docs/plans/2026-04-17-level-pipeline-proof.md)
- [x] 2026-06-03 — [moon-vehicle] Jolt `WheeledVehicleController` for lunar cruisers (6-wheel, steer/throttle/brake, GTA entry/exit). [`a3e02904`](https://github.com/wbniv/WorldFoundry/commit/a3e02904) [plan](docs/plans/2026-06-03-moon-ground-clamping-extra-cruisers-entry-exit.md)
- [x] 2026-06-03 — [smb-w1-4] SMB World 1-4 castle — fire-bars, Fake Bowser, axe, castle corridor (Phases 1-3). [plan](docs/plans/2026-06-03-smb-world-1-4-castle-phase-1-phase-2-stub.md)
- [x] 2026-06-03 — [moon-assets] Moon Site 01 surface asset models — 6 Artemis-era props (racer, vsat tower, cruiser, Blue Moon, FSH, FSP reactor). [plan](docs/plans/2026-06-03-moon-site-01-surface-asset-models.md)
- [x] 2026-06-03 — [load-scale] Load-time OAS/Blender object scale now reaches the render actor (`SetActorScale` in `BindAssets`); fixed wide shared-box statplats. [troubleshooting](docs/level-design-troubleshooting.md)
- [x] 2026-06-02 — [mesh-determ] Deterministic Blender mesh export — canonicalize vertex/face order (was crash-severity: float-perturbed meshes dropped actors through the floor). [`67e79ef1`](https://github.com/wbniv/WorldFoundry/commit/67e79ef1)
- [x] 2026-06-02 — [moon-ambient] Verified the moon AmbientLight fix landed cleanly (HUD/minimap/terrain shading intact, no regressions). [plan](docs/plans/2026-05-31-verify-the-moon-ambientlight-fix-landed-cleanly.md)
- [x] 2026-06-01 — [moon-sky] Moon Site 01 sky — Earth in frame, Sun disc, inverted-normal starfield skydome. [plan](docs/plans/2026-06-01-moon-sky-earth-in-frame-sun-disc-starfield-skydome.md)
- [x] 2026-06-01 — [relay-critique] Relay-connect critique recommendations — loopback host connect, time-budget retry, fail-fast classification, mid-session reconnect; guard `connect_retry_test`. [plan](docs/plans/2026-06-01-implement-the-relay-connect-critique-s-recommendat.md)
- [x] 2026-06-01 — [mesh-dedup] Dedup mesh `.iff` export by datablock (one mesh per model, not per actor) — kills `.001` suffixes, fixed W1-2 room-pool OOM. [`ce29f15c`](https://github.com/wbniv/WorldFoundry/commit/ce29f15c)
- [x] 2026-05-31 — [uv-int16] Widened `CalcUV` uint8→uint16 across the GL pipeline — fixes texture repeat for mesh UVs >~5 (atlas-coord overflow). [`7848b466`](https://github.com/wbniv/WorldFoundry/commit/7848b466) [plan](docs/plans/2026-05-30-uv-int16-widening.md)
- [x] 2026-05-31 — [pilot] PILOT in-engine object-script language — Phases 0-4: Python ref driver, C++ `pilot_core` + in-engine `pilot_engine` (kDispatch slot 6), `BridgeHost`, HUD-text, in-level demo. [plan](docs/plans/2026-05-30-pilot-for-world-foundry-in-engine-object-script-la.md)
- [x] 2026-05-31 — [moon-turn] Moon turn-style movement (LEFT/RIGHT rotate, UP/DOWN walk per facing; `wf_Turn Rate=0.5`). [plan](docs/plans/2026-05-31-moon-turn-style-movement.md)
- [x] 2026-05-31 — [moon-doomstick] Moon doomstick 4-direction strafe input cleanup (raw passthrough + `gDoomStick`/`TurnRate=0`). [plan](docs/plans/2026-05-31-doomstick-4-direction-strafe-input-on-the-moon-lev.md)
- [x] 2026-05-31 — [moon-hud] Moon position-display HUD overlay — lat/lon text + 128² minimap with hillshade, player dot, compass chevron. [plan](docs/plans/2026-05-31-position-display-hud-overlay-on-the-moon-level-tex.md)
- [x] 2026-05-31 — [lmalloc-warn] Fixed per-frame `LMalloc not 8-byte aligned` warning spam (canary added before alignment check). [plan](docs/plans/2026-05-31-fix-lmalloc-canary-breaking-wf-pointer-align-the-1.md)
- [x] 2026-05-31 — [cd-iff-boot] Fixed stale/truncated committed `cd.iff` aborting default boot; regenerated the correct 538 KB bundle. (default boot)
- [x] 2026-05-31 — [relay-frames] Fixed `wf-edit --relay --frames N` `ReadActorNames` crash (nested yrs txn → NULL raw txn). [plan](docs/plans/2026-05-31-fix-relay-frames-readactornames-crash.md)
- [x] 2026-05-31 — [standalone-fallback] `wfedit::ResolveEngineViewportLevel` picks `<base>-standalone.iff` for the engine `-L` (avoids the multi-level `tagRam` assert).
- [x] 2026-05-30 — [stod-strtod] `debug_server.cc` `std::stod`→`std::strtod` (the `catch` was a silent no-op under `-fno-exceptions`). [plan](docs/plans/2026-05-30-a-e-b-audit-follow-up-mailbox-999-fix-shared-curso.md)
- [x] 2026-05-28 — [pure-python] WF asset provider pure-Python rewrite — no C extensions; `providers.py` replaces the Rust `wf_asset_provider`. [plan](docs/plans/2026-04-28-wf-asset-provider-pure-python.md)
- [x] 2026-05-28 — [blender-5x] Verified `wf-blender` + `blender-asset-finder` on Blender 5.x (no 4→5 API breaks; fixed `bl_info` version).
- [x] 2026-05-27 — [smb-popup] SMB score pop-up actor — floating yellow diamond above scored enemies/coins/bricks. [plan](docs/plans/2026-05-27-smb-score-pop-up-actors.md)
- [x] 2026-05-26 — [smb-bricks] SMB breakable bricks — Super shatters (4-fragment debris), Small bumps; faithful W1-1 brick row. [plan](docs/plans/2026-05-26-breakable-bricks-smb-world-1-1.md)
- [x] 2026-05-26 — [smb-fire-star] SMB Fire Flower (Small/Super→Fire) + Star (ground-aware bounce invincibility, no engine change). [plan](docs/plans/2026-05-26-smb-fire-flower-and-star.md)
- [x] 2026-05-26 — [smb-powerup] SMB power-up polish — self-determining mushroom-or-flower block + Starman wall/pipe X-reversal. [plan](docs/plans/2026-05-26-smb-powerup-block-and-star-reversal.md)
- [x] 2026-05-26 — [bridge-phase2] Live editor bridge Phase 2 — Blender → engine property/transform push without restart (`scene_index_map`, `--debug-port`). [plan](docs/plans/2026-04-29-live-editor-bridge-phase-2-make-blender-engine-pus.md)
- [x] 2026-05-26 — [bridge-enum] Live enum→index translation in the Blender depsgraph push (`_coerce_prop_value` mirrors `TranslateField`). [plan](docs/plans/2026-05-26-live-editor-bridge-live-enum-index-translation-in.md)
- [x] 2026-05-26 — [run-operator] Blender "Run in Engine" operator (`WF_OT_run_level`) — export `.lev` → `build_level_binary.sh` → launch `wf_game`. (`operators.py`)
- [x] 2026-05-26 — [level-ux] wf-edit level-loading UX — "Save As .lev" label + File→"Open Level…" / Ctrl+O browser (re-exec); friendly picker names dropped. [plan](docs/plans/2026-05-25-wf-edit-finish-the-level-loading-ux-ordered.md)
- [x] 2026-05-26 — [markdown-chat] wf-edit imgui_markdown chat sidebar + Notes-leaf render code (dormant pending the OAD `SHOW_AS_TEXTEDITOR` fix). [plan](docs/plans/2026-05-26-wf-edit-notes-markdown.md)
- [x] 2026-05-25 — [observe-deep] CRDT→engine true Doc observer (`observeDeep`) for remote/replay/DAP edits; single propagation path via `DrainEngineSync`. [plan](docs/plans/2026-05-25-observe-deep-bridge.md)
- [x] 2026-05-25 — [collab-harden] wf-edit collab-hardening — leaf-granular, drag-aware propagation (no more snap-back on a peer's edit). [plan](docs/plans/2026-05-25-collab-hardening.md)
- [x] 2026-05-25 — [code-review-34] wf-edit code-review #3+#4 — gizmo-snap hotkey requires a selection; snap-step clamps. [plan](docs/plans/2026-05-25-fix-wf-edit-code-review-findings-3-and-4.md)
- [x] 2026-05-22 — [neural-forth] Neural-forth AI library Stages 1-8 — fuzzy, NN, autograd, ∂4 slots, 62/62 tests. [plan](docs/plans/2026-05-22-neural-forth.md)
- [x] 2026-05-22 — [outliner] Outliner add/delete actor (structural editing) — `wfcrdt::Array::remove`, live structural sync, templated/blank Add. [plan](docs/plans/2026-05-21-outliner-add-delete.md)
- [x] 2026-05-22 — [panel-names] Property panel shows the OAD short `displayName` under interleaved section/group headers. [plan](docs/plans/2026-05-22-property-panel-displayname-sections.md)
- [x] 2026-05-21 — [lossless-doc] Lossless Doc schema (literals as a structured array) for structural/remote save; `SaveDocToLev` is now a pure Doc→JSON walk. [plan](docs/plans/2026-05-21-lossless-doc-schema.md)
- [x] 2026-05-21 — [kpropmap] CRDT→engine bridge full OAD field coverage via schema-generated `kPropMap` (77 fields). [plan](docs/plans/2026-05-21-oad-kpropmap-codegen.md)
- [x] 2026-05-21 — [kpropmap-oracle] Extended `task test-codegen` oracle to cover `kpropmap_generated.inc`.
- [x] 2026-05-21 — [editor-resize] Editor viewport follows window resize (`glfwGetFramebufferSize` poll + re-`glViewport`/`SetProjection`).
- [x] 2026-05-21 — [jolt-selfindex] Fixed `JoltContactDispatch` no-other-actor branch setting `COLLIDER_IDX` to the character's own index (added `JoltStaticCollision`). [plan](docs/plans/2026-05-21-jolt-collision-selfindex-fix.md)
- [x] 2026-05-20 — [ht-codegen] Repaired the `.ht` C++ codegen (clean identifiers vs `struct _"Target"`); regen script + oracle test; dropped `gold.ht` stopgap. [plan](docs/plans/2026-05-20-ht-codegen-repair.md)
- [x] 2026-05-19 — [hal-align] HAL pool allocators round to `WF_POINTER_ALIGN` (8 on 64-bit) — UBSan misalignment warnings 3.5k→1. [BUGS.md](docs/BUGS.md)
- [x] 2026-05-19 — [jolt-contacts] Wired Jolt contacts into `Actor::Collision` so per-actor collision mailboxes (3044-3047) work for Jolt actors. [`6bb9a14`](https://github.com/wbniv/WorldFoundry/commit/6bb9a14)
- [x] 2026-05-18 — [unloadlevel] Fixed `UnloadLevel` LMalloc accounting assert (6 dormant LIFO violations + `Array<T>` misuse + Jolt ODR). [plan](docs/plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md)
- [x] 2026-05-18 — [phase-0a] Editor Phase 0a — extracted `libwfengine.a` (CMake split); `wf_game` links it.
- [x] 2026-05-18 — [phase-0b] Editor Phase 0b — engine embed-readiness (`StepFrame`/`LoadLevel`/`UnloadLevel`, external GL context, input injection, de-global `WFGame`). [plan](docs/plans/2026-05-18-engine-frame-step-api.md)
- [x] 2026-05-18 — [phase-0b-e2e] Editor Phase 0b host-GL-context end-to-end test (`wf_host_gl_e2e_test`, in `task test-cycle`). [plan](docs/plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md)
- [x] 2026-05-17 — [lmalloc-canary] LMalloc DEBUG canary — `0xDEADBEEF` sentinel + pre-write assertion + ASan `task build-asan`. [plan](docs/plans/2026-05-17-engine-caps.md)
- [x] 2026-05-17 — [clear-watches] Debug bridge clears watches on client disconnect (`CLIENT_DISCONNECT` sentinel → `DrainQueue` clears `gWatches`). [`67ae680`](https://github.com/wbniv/WorldFoundry/commit/67ae680)
- [x] 2026-05-17 — [workspace-setup] `setup-wf-workspace.sh` — clone repos, install Rust, build wftools, register addon (now in the `linuxfoundry.org` repo). [plan](docs/plans/2026-05-17-wf-workspace-setup.md)
- [x] 2026-05-16 — [qbert-difficulty] Q\*bert per-round difficulty scaling — visibility gating + spawn-interval scaling (16-round sequencer). [plan](docs/qbert/plans/2026-05-16-qbert-spawn-sequencer.md)
- [x] 2026-05-16 — [qbert-popups] Q\*bert bonus-points popups (+25/+50/+100/+300/+500) incl. +500 Coily-off-disc. [plan](docs/plans/2026-05-16-qbert-popup-50-500.md)
- [x] 2026-05-16 — [qbert-coily2] Q\*bert second Coily egg in L4 (two simultaneous eggs from round 12). [plan](docs/qbert/plans/2026-05-16-qbert-second-coily-egg.md)
- [x] 2026-05-16 — [qbert-coexist] Q\*bert enemy coexistence rules (no climber while Coily active; no simultaneous climbers). [plan](docs/qbert/plans/2026-05-15-qbert-enemy-coexistence.md)
- [x] 2026-05-16 — [qbert-curse-text] Q\*bert curse bubble "@!#?*" texture map on bubble mesh. [plan](docs/plans/2026-05-16-curse-bubble-texture.md)
- [x] 2026-05-16 — [qbert-sfx] Q\*bert sound effects — hop, land, fall, death (Votrax swear), round-clear (MAME-extracted PCM).
- [x] 2026-05-16 — [qbert-coily-disc] Q\*bert Coily-falls-off-disc (chases onto disc, retires +500).
- [x] 2026-05-16 — [qbert-16round] Q\*bert end-to-end test of all 16 rounds + L2-L4 behaviour confirmation (`test_director_mailbox.py`).
- [x] 2026-05-16 — [actor-bbox-warn] levcomp-rs emits a build warning when a non-room actor's center falls outside every room bbox.
- [x] 2026-05-15 — [qbert-highscore] Q\*bert high-score persistence (23-entry binary, AAA initials picker, two-column overlay).
- [x] 2026-05-15 — [qbert-discvfx] Q\*bert disc spin VFX — yellow rim flash ring on boarding. [plan](docs/qbert/plans/2026-05-15-qbert-disc-flash-vfx.md)
- [x] 2026-05-15 — [qbert-gameover] Q\*bert game-over screen + name entry (GO_BLOCK / GO_HOLD_TIMER gates).
- [x] 2026-05-14 — [qbert-hud] Q\*bert score & lives HUD + TIMER.
- [x] 2026-05-14 — [qbert-cubes] Q\*bert multi-step cube cycles (L1/L3 single-hop, L2/L4 two-hop). [plan](docs/plans/2026-05-14-qbert-multi-step-cube-cycles.md)
- [x] 2026-05-12 — [qbert-death] Q\*bert player death animation — tumble + splat + curse bubble visual. [`e3a50b4`](https://github.com/wbniv/WorldFoundry/commit/e3a50b4)
- [x] 2026-05-11 — [qbert-meshes] Q\*bert distinct enemy meshes (Slick/Sam, Ugg/Wrong-Way, Coily spiral). [plan](docs/qbert/plans/2026-05-11-qbert-distinct-enemy-meshes.md)
- [x] 2026-05-10 — [jolt-null] Jolt defensive null in `JoltBodyCreateStaticMesh` (`IsInvalid()` guard in all 3 `CreateAndAddBody` wrappers).
- [x] 2026-04-29 — [no-rtti] Eliminated RTTI — all 51 `dynamic_cast` replaced with `kind()`-guarded `static_cast`; `-fno-rtti` engine-wide. [plan](docs/plans/deferred/2026-04-29-eliminate-rtti.md)
- [x] 2026-04-28 — [addon-pkg] Blender addon packaging — `blender_manifest.toml`, build/install/validate/package tasks, addon split. [plan](docs/plans/2026-04-28-blender-addon-packaging.md)
- [x] 2026-04-22 — [ios-2c] iOS Phase 2C — MetalView `CADisplayLink` → engine frame loop; engine thread owns the Metal frame. [`e63b0c80`](https://github.com/wbniv/WorldFoundry/commit/e63b0c80)
- [x] 2026-04-19 — [levcomp-cb] levcomp-rs common-block — `snowgoons.lvl` flip; output byte-identical to oracle (modulo 3 heap-pad bytes). [plan](docs/plans/2026-04-19-levcomp-common-block-two-phase.md)
- [x] 2026-04-19 — [pipeline-d] Decompiled the 4 source-less levels (`cube`, `basic`, `cyber`, `main_game`) to `.lev`. [plan](docs/plans/2026-04-17-level-pipeline-proof.md)
- [x] 2026-04-16 — [jolt] Jolt physics integration — snowgoons player walks on floor, 60 s soak. [plan](docs/plans/2026-04-16-jolt-physics-finish.md)
- [x] 2026-04-16 — [lua-fixes] lua_engine fixes #1-6 — compile cache, per-actor `_ENV`, Fennel pre-compile, sandbox, coroutine continuations. [plan](docs/plans/2026-04-15-lua-engine-fixes.md)
- [x] 2026-04-16 — [forth-plug] Forth scripting plug — `scripting_zforth.cc`, `\` sigil, snowgoons smoke. [plan](docs/plans/2026-04-14-forth-scripting-engine.md)
- [x] 2026-04-16 — [wren-plug] Wren scripting plug — `//wren` sigil, snowgoons smoke. [plan](docs/plans/2026-04-14-wren-scripting-engine.md)
- [x] 2026-04-16 — [wamr] WAMR interpreter — wasm-C-API, global-import constants, snowgoons smoke. [plan](docs/plans/2026-04-14-wamr-dev-aot-ship.md)
- [x] 2026-04-16 — [jerryscript] JerryScript — 7 GCC 14 bugs fixed, snowgoons smoke. [plan](docs/plans/2026-04-15-scripting-plans-align-scriptrouter.md)
- [x] 2026-04-15 — [rust-ports] Rust tool ports (`iffcomp`, `iffdump`, `oaddump`, `lvldump`) build + pass tests; `wf_iff`/`wf_oad` libs.
- [x] 2026-04-14 — [vendor-lua] Vendored Lua 5.4 statically into `wf_game`. [plan](docs/plans/2026-04-14-vendor-lua.md)
- [x] 2026-04-14 — [fennel] Fennel on Lua — `;` sigil, embedded fennel.lua, sub-dispatch in lua_engine. [plan](docs/plans/2026-04-14-fennel-on-lua.md)
- [x] 2026-04-14 — [pluggable] Pluggable scripting engine — `ScriptRouter` neutral dispatcher, all engines as peers. [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [x] 2026-04-14 — [wasm3] wasm3 scripting spike — `#b64` sigil, wasm3 engine plug. [plan](docs/plans/2026-04-14-wasm3-scripting-engine.md)
- [x] 2026-04-13 — [lua-spike] Lua 5.4 interpreter spike — NullInterpreter replaced, snowgoons player + director ported. [plan](docs/plans/2026-04-13-lua-interpreter-spike.md)
- [cancelled] 2026-05-16 — [qbert-letter-s] Bonus letter "S" — not in the original Gottlieb arcade; cancelled.
- [x] ????-??-?? — [rest-api] REST API PoC — cpp-httplib, 5 routes, GL wireframe box renderer, Postman playback.
- [x] ????-??-?? — [wf-game-L] `wf_game -L<level.iff>` CLI flag — bypass cd.iff for dev iteration.
- [x] ????-??-?? — [movecam-crash] movecam crash stabilised — invalid `(Actor*)&msgData` cast at `movecam.cc:964` guarded.
