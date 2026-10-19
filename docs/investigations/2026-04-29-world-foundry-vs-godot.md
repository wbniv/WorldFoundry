# Investigation: World Foundry vs. Godot — technical comparison

**Date:** 2026-04-29
**Status:** Snapshot — WF side sourced from `wfsource/`, investigation set, and plan docs on `2026-new-level`. Godot side sourced from Godot 4.4 documentation and source; version is noted where it matters. **Updated 2026-05-28:** Godot Asset Store launched May 2026 (integrates with Godot 4.7), replacing the Asset Library (now read-only for backward compatibility). Asset Store section updated below.
**Depends on:** [docs/investigations/2026-04-28-engine-capabilities-survey.md](2026-04-28-engine-capabilities-survey.md) (WF capability baseline), [docs/investigations/2026-04-14-jolt-physics-integration.md](2026-04-14-jolt-physics-integration.md)

**Scope:** Technical comparison only — renderer, physics, scripting, tooling, world model, audio, networking, platforms, asset pipeline, licensing. Community size, ecosystem maturity, and hiring-market considerations are excluded by intent.

---

## Summary table

| Dimension | World Foundry | Godot 4.4 |
|---|---|---|
| **Renderer** | OpenGL 3.3 / GLES 3.0; VBO+GLSL; ambient + 3 dir lights; linear fog; no PBR | Vulkan (Forward+ / Mobile); OpenGL compat fallback; full PBR; SDFGI GI; sky shaders; screen-space AO/reflections |
| **Shadows** | None | Shadow maps (directional, omni, spot); PCSS soft shadows |
| **2D** | None | First-class; separate 2D renderer, physics, tilemaps, canvas layers |
| **Physics** | Jolt (`CharacterVirtual`); no vehicle controller yet | Jolt (plugin) or GodotPhysics3D (built-in); `CharacterBody3D`; `VehicleBody3D`; soft body; joints |
| **AI / nav** | Scripted patrols only; no nav-mesh | `NavigationMesh`; `NavigationAgent3D`; A* built-in |
| **Scripting** | Lua 5.4, JS (QJS/Jerry), WASM, Forth (6 backends), Wren, Fennel — selectable at compile time; mailbox-mediated | GDScript, C#, GDExtension (C++); tightly bound to node lifecycle |
| **World model** | Room graph; discrete room containers | Open scene tree; no imposed structure; additive scene loading |
| **Editor** | Blender via plugin | Full integrated editor (scene, animation, shader, script, debugger, profiler) |
| **Audio** | MIDI music + fire-and-forget positional SFX | Full audio engine; effect buses; `AudioStreamPlayer3D`; dynamic mixing |
| **Networking** | None in-tree | High-level multiplayer API; RPC; scene replication; ENet / WebSocket / WebRTC |
| **UI** | No UI system (menus are level objects) | `Control` node tree; full UI toolkit; theming; layout containers |
| **Animation** | Per-actor keyframe; no blend tree | `AnimationPlayer`; `AnimationTree` (state machines, blend spaces); retargeting |
| **Asset pipeline** | Blender → IFF binary; OAD schema system; provenance manifest per asset; format support = Blender's (GLTF, FBX, OBJ, USD, Alembic, …) | Import from GLTF/FBX/OBJ/PNG/etc.; reimport on change; no per-asset licence provenance. Asset Store (May 2026) adds reviews, ratings, analytics, changelogs, tagging — paid assets not yet live |
| **Platforms** | Linux (primary), Android, iOS (in progress) | Windows, macOS, Linux, Android, iOS, Web; consoles via third-party exporters |
| **Binary size** | Small custom engine; mobile-budget ceiling is a design constraint | ~50–100 MB export templates; heavier runtime |
| **License** | GPL-2.0 | MIT |

---

## Renderer

**Godot** runs Vulkan with a Forward+ pipeline on desktop (deferred-ambient, clustered lighting, SDFGI global illumination, VoxelGI baked GI, SSAO, SSR, glow, depth of field, TAA) and a Mobile backend for lower-end targets (Forward rendering, reduced effects). An OpenGL 3 compatibility renderer is available for hardware that can't run Vulkan. Full PBR: metallic/roughness material model, normal maps, emission, clearcoat, subsurface scattering. Shadow maps on all light types with PCSS soft shadows. The visual bar is current-generation.

**World Foundry** runs OpenGL 3.3 (desktop) / GLES 3.0 (Android). The renderer backend (`gfx/renderer_backend.hp`, `gfx/glpipeline/backend_modern.cc`) is a VBO + GLSL per-triangle accumulator: one ambient color, up to three directional lights, linear fog, diffuse texture. No PBR, no normal maps, no shadow maps, no post-processing. This is a deliberate scope decision — the renderer is functional for the arcade-conversion genre target and avoids the complexity of a modern render graph. The visual style ceiling is late-1990s 3D: clean geometry, solid colors, simple lighting — which suits the genre.

**WF advantage:** none on rendering capability.
**WF niche:** the simple pipeline means no shader authoring burden per asset; everything renders predictably without PBR material tuning.

---

## Physics

Both engines now use **Jolt Physics** as the recommended backend, so the underlying simulation quality is the same.

**Godot** exposes Jolt via a maintained plugin (as of 4.3 it ships optionally; it will likely be official in 4.x mainline). It also has its own GodotPhysics3D if Jolt isn't wanted. High-level abstractions: `CharacterBody3D` (Jolt-backed), `RigidBody3D`, `VehicleBody3D`, `SoftBody3D`, joints (hinge, cone twist, slider, 6DOF), ray and shape casts from GDScript. Physics layers/masks, linear/angular damp, CCD.

**World Foundry** uses Jolt's `CharacterVirtual` for player movement (per `2026-04-14-jolt-physics-integration.md`), handles static-mesh level geometry as a `JPH::MeshShape`, and wraps everything behind the `PhysicalAttributes` API. Scripts do not call physics directly — they only write mailboxes (velocity, position intent); the engine ticks Jolt at a fixed 60 Hz substep rate internally. There is no vehicle controller yet (`JPH::VehicleConstraint` exists upstream but is not wired in). No ragdoll, no soft body.

**WF advantage:** none on feature coverage. The mailbox-mediated access pattern does mean scripts can't accidentally corrupt physics state mid-frame, which is a minor correctness advantage.

---

## Scripting

**Godot** offers GDScript (Python-like, tight engine integration, hot reload), C# (.NET 6+ via Mono or .NET), and GDExtension (C++ at near-native binding speed, replacing the old GDNative). GDScript and C# can call into each other. Signals are the pub/sub primitive. Coroutines via `await`. Each node's `_process`, `_physics_process`, `_ready`, `_input` are the lifecycle hooks. No other languages without external binding work.

**World Foundry** is the broader option by language count: Lua 5.4 (primary), Fennel (compiles to Lua), JavaScript (QuickJS or JerryScript — mutually exclusive at compile time), WebAssembly (WAMR; source languages include AssemblyScript, Rust, Zig, TinyGo, C, C++), Forth (six interchangeable backends), Wren. Languages are independently selectable at compile time; a scriptless build is valid. Multi-tick scripts via Lua coroutines, JS generators, Wren fibers; Forth and JerryScript are single-tick only. The critical architectural difference: **WF scripts do not call engine APIs directly — they read and write mailbox slots**. The engine reacts to mailbox state each tick. This makes scripts pure data transformers; they can't inadvertently cause re-entrant engine calls. The tradeoff is that anything the mailbox doesn't expose is unreachable from scripts.

**WF advantage:** WASM support means scripts can be written in Rust or Zig without a custom binding layer, which no mainstream engine offers. Forth for timing-sensitive deterministic logic. Language isolation from engine internals.

**Design philosophy note:** WF's mailbox boundary is intentional — scripts express gameplay logic; anything that needs deeper engine access belongs in C++. Godot's approach (scripts reach the full engine API) is a different tradeoff: more power per script, more surface area for misuse and tight coupling. Neither is universally better; they reflect different views on where the engine/gameplay boundary should live.

---

## World model

**Godot** uses an open scene tree: a root node containing child nodes in any hierarchy. No imposed world structure. Large worlds are handled via additive scene loading (loading/unloading scenes as the player moves through space). Multi-level streaming, background loading, resource preloading — all built-in. There is no concept of "rooms" unless you build one.

**World Foundry** uses a **room graph**: the world is partitioned into named zones (called `room` objects) and every actor lives inside exactly one zone at a time. The name is a misnomer — a "room" is not an architectural room; it is whatever spatial unit the designer draws. The mechanism was designed to solve **CD streaming**: as the player moved through a level, the engine could load and unload assets (geometry, textures, scripts, audio) zone-by-zone without stalling on a single bulk load. The room graph is the designer-controlled handle on that streaming budget. Camera rigs (`CamShot`, `actboxor` triggers) are attached per zone as a consequence of how zones are authored, not because zones are inherently camera units.

**WF advantage:** the zone-streaming architecture is explicit and designer-controlled. Camera scaffolding and asset scoping fall out naturally from authoring zones. Godot requires you to build additive-scene streaming and camera switching yourself.

**Godot advantage:** no structural constraint. In practice the difference is minimal — a WF level that doesn't need streaming just uses one zone.

---

## Editor and tooling

**Godot** ships a full integrated editor: scene tree view, 3D/2D viewport with transform gizmos, property inspector, animation editor, shader graph, script editor with debugger and profiler, import configuration, export dialog, and a live play-in-editor mode. Everything runs inside the engine itself; the editor is a Godot game. Remote debugger connects to running builds on device.

**World Foundry** uses **Blender as its editor** via `wftools/wf_blender/`. Blender is a professional 3D tool with a much stronger modeling and rigging story than Godot's editor — but it is not a game editor. There is no scene debugger, no live play mode, no property inspector for mailbox values, no in-editor preview of physics. The workflow is: build in Blender → export → run `wf_game` as a separate binary → observe → return to Blender. Iteration loops are longer. The OAD schema system (`.oad` files, validated per-object attribute definitions) partially compensates — it gives type safety and structured data authoring per object inside Blender — but it's not a replacement for a live editor.

The `wf-asset-browser` plugin (source: `wftools/wf_blender/`) provides something Godot does not: a **licence-aware asset browser** with per-asset provenance manifests, policy-file-driven filtering, and a structured attribution audit trail. Godot's Asset Store (launched May 2026, replacing the deprecated Asset Library) adds reviews, ratings, publisher analytics, multiple version downloads, changelog tracking, and custom tagging — but still has no per-asset licence provenance, no policy-file filtering, and no attribution audit trail.

**WF advantage:** Blender modeling quality; OAD schema system; asset provenance/licensing infrastructure.
**Godot advantage:** everything else about editing — live play, debugging, profiling, shader authoring, animation editing, device remote debug.

---

## Audio

**Godot** has a first-class audio engine: `AudioStreamPlayer` (2D), `AudioStreamPlayer3D` (positional with attenuation models), `AudioStreamPlayer` (non-positional), effect buses (reverb, EQ, compressor, chorus, delay, limiter), dynamic mixing, `AudioStreamGenerator` for procedural audio. Streams can be OGG, MP3, WAV, or generated. AnimationPlayer can drive audio cues.

**World Foundry** has MIDI music (per-level) and fire-and-forget 3D-positional sound effects. The audio subsystem investigation ([docs/investigations/2026-04-14-audio-sound-music.md](2026-04-14-audio-sound-music.md)) notes these as the current capabilities. No effect buses, no dynamic mixing, no procedural audio.

**WF advantage:** none.

---

## Networking

**Godot** has a high-level multiplayer API: `MultiplayerPeer` abstraction over ENet, WebSocket, and WebRTC transports; `@rpc` annotation for remote procedure calls; `MultiplayerSpawner` and `MultiplayerSynchronizer` for scene replication; authoritative server + client prediction patterns are documented and community-validated.

**World Foundry** has no networking in-tree. The multiplayer/voice/mobile-input investigation ([docs/investigations/2026-04-14-multiplayer-voice-mobile-input.md](2026-04-14-multiplayer-voice-mobile-input.md)) is exploratory; nothing has landed.

**WF advantage:** none.

---

## AI and pathfinding

**Godot** has `NavigationMesh` (baked or runtime), `NavigationAgent3D` (A* over the nav-mesh with avoidance), `NavigationObstacle3D`. Suitable for NPCs navigating complex geometry. Built-in pathfinding is good enough for most action/adventure titles without external libraries.

**World Foundry** has scripted patrols and trigger-based behaviours. Enemies can move (physics-backed) and react to mailbox signals, but there is no nav-mesh and no A* search. Complex NPC navigation requires baking the path as a sequence of waypoints and writing the traversal logic in scripts.

**WF advantage:** none.

---

## Asset pipeline

**Godot** imports assets natively: GLTF 2.0, FBX, OBJ, Collada, PNG/WebP/JPEG/EXR (with compression and mipmap options), WAV/OGG/MP3, TTF fonts. On-import configuration via `.import` sidecar files. The import system reruns automatically when source files change. No per-asset licence tracking. The **Godot Asset Store** (May 2026, replaces the now-read-only Asset Library) is a live marketplace integrated with Godot 4.7 — user reviews, ratings, publisher analytics, multiple-version downloads, changelog tracking, and custom tagging. Free distribution only at launch; paid asset sales are on the roadmap. No provenance or licence compliance infrastructure.

**World Foundry** converts assets through a custom pipeline: Blender scenes export to `.lev` (level descriptor) + per-mesh `.iff` (Interchange File Format) files via `iffcomp-rs` / `levcomp-rs` / `textile-rs`. Textures are packed into IFF chunks. The pipeline is explicit and reproducible (driven by `build_level_binary.sh`) but requires a build step between Blender edits and engine runs. The OAD schema system attaches typed attribute definitions to objects at export time. The `wf-asset-browser` plugin (Poly Haven, Kenney, AmbientCG, Quaternius, OpenGameArt, Sketchfab) provides provenance-tracked asset sourcing with per-asset `manifest.json` records (licence, attribution string, source URL, download date) — a capability Godot has no equivalent of.

**WF advantage:** asset provenance and licence compliance infrastructure. Format support is Blender's format support — GLTF, FBX, OBJ, USD, Alembic, and anything else Blender imports — which is at least as broad as Godot's.
**Godot advantage:** no intermediate build step; reimport on change is automatic.

---

## Platforms

**Godot** targets Windows, macOS, Linux, Android, iOS, Web (WebAssembly + WebGL2). Console ports (Switch, PS4/5, Xbox) are available via third-party exporters (W4 Games, etc.) at commercial cost. Web export is production-quality.

**World Foundry** targets Linux (primary development platform), Android (APK builds, ARM64), and iOS (Metal port in progress). No Windows binary today; no Web export; no console path. The mobile-budget ceiling — an explicit design constraint — means the renderer and runtime are scoped to fit within Android/iOS memory and GPU constraints. This rules out the high-end visual effects that would be natural in a Godot Forward+ project.

**WF advantage:** none on platform breadth. The Android/iOS-first budget ceiling is a constraint, not an advantage.

---

## Licensing

**Godot** is MIT-licensed. You can use it in commercial projects, modify it, redistribute it, without royalties or attribution in the shipped binary (though crediting Godot is conventional).

**World Foundry** is a proprietary engine owned by this project. No licensing question for internal use; would become relevant if distributing the engine itself.

**WF advantage:** full control over the codebase; no upstream policy risk.
**Godot advantage:** no licensing cost or friction for any use case.

---

## Where WF leads

1. **WASM scripting.** Write game scripts in Rust, Zig, TinyGo, or AssemblyScript — compiled to WASM, run via WAMR — without a custom C++ binding layer. No mainstream engine offers this out of the box.

2. **Scripting language breadth.** Six Forth backends, Lua + coroutines, QuickJS/JerryScript, Wren, Fennel. Pick the right tool for the right actor. Compile out languages you don't need.

3. **Mailbox isolation.** Scripts cannot call engine internals directly. This makes scripting errors local (wrong mailbox value) rather than global (corrupted engine state). A useful correctness property for a multi-author project.

4. **OAD schema system.** Per-object typed attribute definitions, validated at export time. Godot has `@export` annotations; OAD is more structured and tool-checked.

5. **Asset provenance.** Every imported asset carries a `manifest.json` with licence, attribution string, source URL, and download date. The policy file controls which licences are accepted per project. The Godot Asset Store (May 2026) adds discovery and distribution infrastructure but has no per-asset licence provenance, no policy-file filtering, and no attribution audit trail — the gap remains.

6. **Blender as editor.** Modeling, UV unwrapping, rigging, animation editing are all first-class in Blender. Godot's 3D editor is functional but not a DCC tool.

---

## Where Godot leads — and what WF needs to add

<table style="width:100%">
<colgroup><col style="width:50%"><col style="width:50%"></colgroup>
<thead><tr><th>Where Godot leads</th><th>What WF needs to add</th></tr></thead>
<tbody>
<tr><td><strong>Renderer</strong> — Vulkan PBR, GI, shadow maps, post-processing. WF is OpenGL 3.3 / early-2000s visual ceiling.</td><td>Modern lighting model (shadow maps at minimum; PBR materials). Structural work — not a small project.</td></tr>
<tr><td><strong>2D</strong> — first-class 2D engine: separate renderer, TileMaps, CanvasLayer, 2D physics. WF has none.</td><td>Out of scope for the current target genre; revisit if WF expands to 2D titles.</td></tr>
<tr><td><strong>Integrated editor</strong> — live play, scene debugger, shader graph, animation editor, remote device debug. WF's Blender workflow has a long iteration loop.</td><td>A play-in-editor mode or at minimum a live debug bridge from the running binary back to Blender. Structural gap.</td></tr>
<tr><td><strong>Networking</strong> — high-level multiplayer API (RPC, scene replication, ENet/WebSocket/WebRTC). WF has nothing.</td><td>Defined engineering project; Godot's RPC + replication design is worth studying as a reference.</td></tr>
<tr><td><strong>AI / pathfinding</strong> — <code>NavigationMesh</code> + <code>NavigationAgent3D</code> + A*. WF is scripted patrols only.</td><td>Nav-mesh build + NavigationAgent equivalent. Defined engineering project.</td></tr>
<tr><td><strong>Audio engine</strong> — effect buses, positional attenuation models, dynamic mixing. WF is MIDI + fire-and-forget SFX.</td><td>Audio bus system + streaming audio. Defined engineering project.</td></tr>
<tr><td><strong>UI system</strong> — <code>Control</code> node tree; full widget toolkit; theming; layout containers. WF has no UI system.</td><td>In-game widget system (menus, HUD). Defined engineering project.</td></tr>
<tr><td><strong>Animation system</strong> — <code>AnimationTree</code>: blend spaces, state machines, IK, retargeting. WF has per-actor keyframes.</td><td>Blend tree / animation state machine. Defined engineering project.</td></tr>
<tr><td><strong>Platform breadth</strong> — Web, all major desktops, mobile, consoles. WF is Linux + Android + iOS-in-progress.</td><td>Web export; Windows/macOS builds. Incremental — no fundamental blocker.</td></tr>
<tr><td><strong>Licensing</strong> — MIT; permissive, no copyleft obligations. WF is GPL-2.0.</td><td>GPL-2.0 requires distributing source of derivative works. Not a blocker for internal use or shipping games (game content is separate); matters if distributing the engine itself or linking proprietary code against it.</td></tr>
</tbody></table>

---

## Genre fit

| Genre | WF today | Godot |
|---|---|---|
| Third-person platformer / action-adventure | Suited primitives (`CamShot`, `actboxor`, `CharacterVirtual`, zone streaming) — but camera rig and world structure are still authored by hand | Suited primitives (`CharacterBody3D`, `Camera3D`, signals) — camera rig and world structure also authored by hand |
| 2D (side-scroller, arcade single-screen) | Not supported | Native |
| FPS / TPS shooter | First-person camera rig and aimable weapon system not in the C++ engine, but buildable with objects and scripts | Native |
| Racing / vehicle | Missing: vehicle controller | Native (`VehicleBody3D`) |
| Open-world / streaming | Zone graph is a streaming mechanism — fits, but zones must be explicitly designed | Native |
| RTS / grid / turn-based | Missing: tile grid, turn manager | Build in scripts |
| Multiplayer | Missing: networking | Native |
| VR/AR | Not in scope | Supported via OpenXR |

---

## Bottom line

Godot is the broader tool. For any project that isn't specifically a room-graph third-person 3D action/platformer, Godot removes months of engine work that WF would require. Its renderer, editor, audio, networking, AI, and platform story are all ahead.

WF has a focused identity that Godot lacks: the mailbox actor model, the OAD schema system, the Blender-native workflow, the asset provenance infrastructure, and the WASM scripting story are genuine differentiators for its target genre. It is also a codebase you own entirely — there is no upstream to break your build or change terms.

The practical question is not replacement but competition: what does a developer choosing between WF and Godot see? Right now Godot's advantages — renderer, integrated editor, networking, AI, audio, UI, platform breadth — are visible and concrete. WF's advantages — WASM scripting, OAD schema system, asset provenance, Blender-native workflow, mailbox isolation — are real but less obvious to an outsider. The gaps that most affect that competitive perception are the renderer (hard to close), the lack of a live editor (structural), and networking (a defined engineering project). Godot is most useful to WF as a reference implementation: what its networking, nav-mesh, and animation systems look like is worth studying before designing WF equivalents.
