# macOS Port — Effort & Time Estimate (Runtime, then Engine delta)

**Date:** 2026-05-26
**Author:** investigation (Claude)
**Status:** Estimate only — no macOS branch exists yet. Greenfield.
**Repo:** [github.com/wbniv/WorldFoundry](https://github.com/wbniv/WorldFoundry)

## TL;DR

| Pass | Scope | Effort (avg programmer) | Wall-clock |
|------|-------|-------------------------|------------|
| **1 — Runtime** | `wf_game` plays a level natively on macOS | **≈ 15 working days** (range 12–25) | **≈ 3 weeks** (2–5) |
| **2 — Engine delta** | `wf-edit` collaborative editor + CRDT + collab A/V, *given* the runtime works | **≈ 20 working days** (range 16–28) | **≈ 4 weeks** (3–6) |
| **Both, sequential** | Full macOS desktop story | ≈ 35 working days | ≈ 7–9 weeks |

**The single most important finding:** macOS should reuse the **existing OpenGL renderer**, not the in-progress Metal backend. The desktop modern pipeline ([`backend_modern.cc:56`](../../wfsource/source/gfx/glpipeline/backend_modern.cc)) is `#version 330 core`, which runs natively under macOS's OpenGL 4.1 core profile. iOS was *forced* onto Metal (no GL on iOS at all) and is still stuck at "cornflower blue" — its Metal `RendererBackend` compiles but does not yet draw game content (see [wf-status.md](../wf-status.md), iOS Phase 2B3). macOS skips that entire tar pit. The renderer (~58k LOC of engine) is reused verbatim; the genuine port surface is **~1,000–1,500 LOC of X11/GLX windowing + input**.

These numbers are on the **average-programmer scale** per [estimate convention](../../CLAUDE.md). This project's *historical* velocity is far above that (iOS went Phase 0 → all-sources-compiling in ~2 days), so actuals will likely beat these — but the estimate does not bake in that speed.

---

## 1. Scope & interpretation

"macport (runtime only)" then "the engine … a delta from the runtime" maps cleanly onto the codebase's real seam, the **`WF_ENABLE_EDITOR` boundary** ([`CMakeLists.txt:60`](../../CMakeLists.txt), [feedback_editor_code_compile_gate](../../CLAUDE.md)):

- **Pass 1 — Runtime** = the shipped game engine: `wf_game` boots `cd.iff`, loads a level, renders, takes input, plays. `WF_ENABLE_EDITOR=OFF`. This is "the World Foundry game engine" as a player experiences it.
- **Pass 2 — Engine delta** = everything a *shipped runtime build* leaves out: the `wf-edit` collaborative editor app, the CRDT/Yjs stack, in-editor voice/video chat, and the host-side authoring tools. `WF_ENABLE_EDITOR=ON`. This is a strict superset that *links* the Pass-1 engine library and adds to it.

> Note on what is **not** in the delta: the TCP debug bridge, REST API, and the full scripting-engine roster (Lua/Fennel/QuickJS/WAMR/Wren) are **on by default in a desktop runtime build** — they're gated off only on Android/iOS ([`CMakeLists.txt:66`](../../CMakeLists.txt)), not by `WF_ENABLE_EDITOR`. So they come along *for free* in Pass 1 on macOS. The honest Pass-2 delta is the **editor app + collaboration + Rust/CRDT + AVFoundation capture**.

"macOS port" here means a **native desktop `.app`** (GLFW-Cocoa window, keyboard/mouse/gamepad, runs like any Mac app), targeting **Apple Silicon (arm64) first** — that's what Codemagic's `mac_mini_m2` runners and 2026-era Macs are. A universal (arm64 + x86_64) binary is a later distribution concern, not a porting concern.

## 2. Why macOS is cheap: the HAL is already abstracted, and iOS retired the hard risks

Two prior ports already did most of the de-risking:

1. **Apple-Clang compilation is a solved problem.** The iOS port got *all ~120 engine sources* compiling and linking under Apple Clang for arm64 in ~2 days (wf-status: iOS Phase 1 → 2B2, 2026-04-22). The legacy-`register`, `-Wno-register`, `SCALAR_TYPE_FLOAT`, and pool-alignment (`WF_POINTER_ALIGN`) issues are already fixed in-tree. macOS desktop is the *same compiler* with *fewer* restrictions than the iOS Simulator.
2. **The engine is cleanly HAL-split.** Platform code lives behind three directory swaps in [`CMakeLists.txt:128-162`](../../CMakeLists.txt) — `hal/{linux,android,ios}`, a renderer-backend `#define`, and a per-platform shell file ([`CMakeLists.txt:579`](../../CMakeLists.txt), the `libwfengine.a` split). Adding a 4th platform is *editing those switch arms*, not surgery.

The architecture, with macOS's reused-vs-ported split:

```
                       wf_game  (macOS .app, arm64)
   ┌──────────────────────────────────────────────────────────┐
   │  game · movement · room · physics (Jolt) · scripting ·     │  REUSED as-is
   │  anim · menu · particle · math · iff · mailbox · asset ·   │  ~56k LOC, already
   │  loadfile · timer · memory · streams                       │  Apple-Clang-clean
   ├───────────────────────── gfx ─────────────────────────────┤  via iOS Phase 2B2
   │  glpipeline GL backend   (#version 330 core, 1.4k LOC)     │  REUSED: macOS GL 4.1
   ├────────────────────────────────────────────────────────────┤  core profile runs it
   │  HAL                                                        │
   │    audio  (miniaudio → CoreAudio) ................. REUSE   │
   │    assets (asset_accessor_posix, Darwin POSIX) .... REUSE   │
   │    savegame (savegame/linux, POSIX) ............... REUSE   │
   │   ┌── windowing   X11/GLX (mesa.cc/display.cc) ──┐  PORT    │  ← the actual work
   │   └── input        X11 (hal/linux/input.cc)    ──┘  PORT    │     ~1–1.5k LOC →
   │                       ↓ replace with ↓                      │     GLFW-Cocoa
   │              GLFW-Cocoa window + NSGL 3.3-core ctx          │
   └────────────────────────────────────────────────────────────┘
```

The thing being *ported* is the part touching the window system. Everything above it is identical to the Linux build.

## 3. The pivotal decision — OpenGL, not Metal

This is the highest-leverage call in the whole estimate, so it gets its own section.

| | **Option A — reuse OpenGL (recommended)** | **Option B — reuse iOS Metal** |
|---|---|---|
| Renderer code | Linux `glpipeline` GL backend, **unchanged** | iOS `backend_metal.mm` + MSL shaders |
| Shaders | `#version 330 core` already authored & working | GLSL→MSL translation (iOS still incomplete) |
| macOS support | GL 4.1 core profile (since 10.7); 330-core is well within it | Metal native (the "supported" API) |
| Blocking deps | none — Linux renderer already draws real content | **blocked on iOS Phase 2C+** (Metal doesn't draw game content yet) |
| Windowing | GLFW-Cocoa (already vendored) | MTKView + AppKit |
| Risk | core-profile strictness, Retina, deprecation | large net-new surface, couples macOS to iOS schedule |
| Lifespan | Apple has deprecated-but-not-removed GL through 2026 | future-proof |

**Recommendation: Option A for both passes.** Rationale:
- The Linux GL renderer **already renders real game content** (Snowgoons, SMB, Q✱bert). iOS's Metal backend, by contrast, compiles and links but "nothing drives it yet (sim still cornflower blue)" — Metal is the reason iOS isn't visually done. Choosing Metal for macOS would import that unfinished dependency.
- macOS OpenGL 4.1 is a superset of the 3.3-core profile the shaders target. No shader rewrite, no new backend.
- GLFW's Cocoa backend creates a 3.3-core context with two hint lines; it's already vendored ([`third_party/glfw`](../../third_party/glfw)) and the editor already links it.

**Option B is the strategic/eventual path** — if Apple removes OpenGL, macOS would ride whatever Metal `RendererBackend` iOS lands. Worth noting as a future convergence, but it should *not* gate the macOS port. macOS and iOS would then share Metal; today they share nothing because iOS has no GL.

> Deprecation caveat (honest): `-framework OpenGL` raises deprecation warnings on macOS and Apple could remove GL in a future major release. The mitigation is exactly Option B, which becomes a forced migration *shared with iOS* if/when it happens. Until then, GL is fully functional.

## 4. Pass 1 — Runtime macport

Get `wf_game` to boot `cd.iff`, load Snowgoons, render via GL, and respond to keyboard/gamepad — as a native `.app`.

### Work breakdown

| # | Item | What it touches | Effort | Risk |
|---|------|-----------------|-------:|------|
| R1 | **CMake macOS-desktop branch** — a 4th arm in the platform `if/elseif`: `RENDERER_GL` like Linux, Apple frameworks, `.app` via `MACOSX_BUNDLE` (reuse the iOS bundle block at [`CMakeLists.txt:835`](../../CMakeLists.txt)), arm64, Ninja generator | `CMakeLists.txt`, new `Taskfile` target | 1–2 d | Low |
| R2 | **Windowing backend** — replace X11/GLX in [`mesa.cc`](../../wfsource/source/gfx/gl/mesa.cc) / [`display.cc`](../../wfsource/source/gfx/gl/display.cc) with a GLFW-Cocoa `HalDisplay`: 3.3-core context, swap, resize, framebuffer (Retina) scaling, close-request | new `gfx/gl/cocoa_window` (or `mesa_glfw`), `display.cc` `#ifdef` | 3–5 d | **Med** — core-profile/VAO strictness + HiDPI first-light |
| R3 | **Input backend** — GLFW key/mouse/gamepad callbacks → WF input map, mirroring [`hal/linux/input.cc`](../../wfsource/source/hal/linux/input.cc) | new `hal/macos/input` | 2–3 d | Low |
| R4 | **Audio** — miniaudio's CoreAudio backend (already proven on Darwin by the iOS build); link `CoreAudio`/`AudioToolbox`. ~0 new code | `CMakeLists.txt` link libs | 0.5–1 d | Low (verify needs a real Mac w/ speakers — [audio_verify](../../CLAUDE.md)) |
| R5 | **Assets / bundle** — `cd.iff` into `.app/Contents/Resources` (reuse the iOS resource-copy pattern); confirm `asset_accessor_posix` on Darwin | `CMakeLists.txt`, `hal/macos` shim | 1 d | Low |
| R6 | **WAMR on Apple Silicon** — `invokeNative_em64.s` is x86_64-only; `invokeNative_aarch64.s` exists → set `WAMR_BUILD_TARGET=AARCH64` for arm64 (or gate WAMR off as mobile does) | `CMakeLists.txt:313` | 0.5–1 d | Low |
| R7 | **Physics (Jolt)** — keep Jolt: the iOS fallback to legacy is **Xcode-generator-specific** ([`CMakeLists.txt:447`](../../CMakeLists.txt)); macOS desktop uses Ninja, so Jolt builds like Linux | verify only | 0.5 d | Low |
| R8 | **Integration & first playable** — boot Snowgoons, move the player, debug the inevitable framework/link/focus/Retina issues | end-to-end | 3–5 d | **Med-High** |
| R9 | **CI** — native-macOS Codemagic workflow (mirror the iOS-sim one, but a desktop target + headless screenshot verify) | `codemagic.yaml` | 1–2 d | Low |

**Total: 12.5–24.5 person-days → central ≈ 15 days ≈ 3 weeks.** Risk concentrates in **R2** and **R8** (making a GL core-profile context actually present content on macOS, then shaking out integration). If those go smoothly, the low end (~2 weeks) is reachable; the high end covers Retina/core-profile/window-focus surprises.

### Notable runtime risks
- **GL core-profile strictness on macOS.** macOS core profiles are stricter than Mesa: a VAO must be bound for every draw, no compatibility fallbacks, forward-compatible flag required. The pipeline is already a modern core pipeline, but expect a few "blank screen until the VAO is right" sessions. This is the main reason R2 isn't a half-day.
- **Retina / HiDPI.** Framebuffer size ≠ window size on Mac. Viewport/scissor math in [`viewport.cc`](../../wfsource/source/gfx/gl/viewport.cc) needs the framebuffer scale, not the point size.
- **Window focus / event loop.** The Linux build has X11 focus quirks ([keyboard_focus_fix](../../CLAUDE.md)); the Cocoa equivalent (first-responder, app activation) is different but analogous. GLFW abstracts most of it.

## 5. Pass 2 — Engine (editor) delta

Given a working runtime, add the `wf-edit` collaborative editor ([`CMakeLists.txt:910-1021`](../../CMakeLists.txt)) and its stack. The editor *links the Pass-1 engine library* and renders the engine viewport into a GLFW+ImGui host window via the **host-GL-context handshake** — which is today **X11/GLX-typed end to end**.

### Work breakdown (delta over Pass 1)

| # | Item | What it touches | Effort | Risk |
|---|------|-----------------|-------:|------|
| E1 | **Rust / Corrosion / CRDT** — `libwfcrdt.a` wrapping `libyrs.a` via Corrosion+Cargo. Rust is inherently cross-platform; Corrosion supports macOS. Mostly "rustup + arm64 target + verify" | [`engine/crdt`](../../engine/crdt), `cmake/Corrosion` | 1–2 d | Low |
| E2 | **Host-GL handshake GLX→NSGL/CGL** — [`host_gl_context.h`](../../wfsource/source/gfx/host_gl_context.h) carries `Display*`/`Window`/`GLXContext`; [`main.cc:839-851`](../../engine/wf_edit/main.cc) calls `glfwGetGLXWindow`/`glfwGetGLXContext`/`glXGetCurrentContext`. macOS needs the Cocoa/NSGL (or CGL) equivalent + the swap-drawable analogue of fix `efff7f69` | `host_gl_context.{h,cc}`, `wf_edit/main.cc`, GL backend ctx cast | 4–6 d | **Med-High** |
| E3 | **wf-edit build** — GLFW-Cocoa + ImGui (`imgui_impl_glfw` + `imgui_impl_opengl3` are both cross-platform); swap `glfw GL` link line for `-framework OpenGL`; drop the X11-only GLFW config | `CMakeLists.txt:920` | 1–2 d | Low |
| E4 | **Camera capture V4L2→AVFoundation** — [`video_track.cc`](../../engine/wf_edit/video_track.cc) does VP8 + **V4L2** capture (Linux-only). Net-new AVFoundation `AVCaptureSession` backend for the Mac camera | new `wf_edit/video_capture_avf.mm` | 4–6 d | **Med-High** |
| E5 | **Mic capture + codecs** — Opus + libvpx via Homebrew (portable C); mic via miniaudio CoreAudio capture | `voice_track.cc`, deps | 1–2 d | Low |
| E6 | **Collab transport on macOS** — UDP-multicast discovery ([`collab_session.cc`](../../engine/wf_edit/collab_session.cc)), WS relay ([`ws_client.cc`](../../engine/wf_edit/ws_client.cc)), and the **mandated** libdatachannel DTLS-SRTP + `wss` encryption ([internet-voice-video investigation](2026-05-26-internet-voice-video-nat-traversal.md), [collab encryption requirement](../../CLAUDE.md)). Sockets portable; verify macOS multicast (entitlement quirks on recent macOS) | transport files, libdatachannel via brew | 2–3 d | Med |
| E7 | **Homebrew dep bootstrap** — a macOS equivalent of the `worldfoundry-editor-dev` apt metapackage (opus, libvpx, libdatachannel; GLFW is vendored); CMake `find_package`/`pkg_check_modules` paths under `/opt/homebrew` | docs + CMake | 1–2 d | Low |
| E8 | **wf-relay** — standalone Cargo binary ([`CMakeLists.txt:1016`](../../CMakeLists.txt)); builds on macOS unchanged | verify | 0.5 d | Low |
| E9 | **Editor test suite + screenshot verify** — `wf_edit_spawn_confirm` / `_undo` / `_add` ([`CMakeLists.txt:993-1012`](../../CMakeLists.txt)) green on macOS; screenshot proof per [screenshots-for-proof](../../CLAUDE.md) | CTest, capture | 2–3 d | Low-Med |

**Total: 16.5–27.5 person-days → central ≈ 20 days ≈ 4 weeks.** Risk concentrates in **E2** (the editor's entire viewport-embedding mechanism is GLX-typed and must be re-expressed in NSGL/CGL) and **E4** (a net-new AVFoundation capture path — V4L2 has no Mac analogue to reuse).

### What is *not* a problem in the delta
- **ImGui, ImGuizmo, imgui_markdown, nlohmann/json** — cross-platform / header-only.
- **Yrs / Yjs** — pure Rust; the [yrs upgrade decision](../../CLAUDE.md) is platform-agnostic.
- **Toolchain bonus:** the editor's Linux Release build *fails* on the engine's Clang-only `-flto=thin` (which is why Linux editor builds are Debug/GCC — [wf_edit build path](../../CLAUDE.md)). On macOS *everything is Clang*, so a Release editor build is actually **easier** than on Linux.
- **The Rust host tools** (iffcomp-rs, levcomp-rs, textile-rs, chargrab-rs) are already cross-platform Rust and build on macOS trivially — but they're not on the critical path, since level-building can stay on a Linux host.

## 6. Cross-cutting concerns

- **Architecture — arm64 first.** Target Apple Silicon (matches Codemagic `mac_mini_m2` and 2026 Macs). The only arch-sensitive engine code is WAMR's asm (R6, editor-irrelevant since runtime carries it) and the pool-alignment work already landed. A universal binary (`lipo` arm64+x86_64) is a *distribution* task, ~1–2 d, deferrable.
- **CI is already paid for.** Codemagic's Mac runners build native macOS the same way they build the iOS Simulator today ([`codemagic.yaml`](../../codemagic.yaml); iOS builds avg 3.4 min, budget 500 Mac-min/mo). A `macos-desktop-debug` workflow is a near-copy of `ios-simulator-debug`. **No user Mac is required** for build or headless verify — same as the iOS pipeline.
- **Distribution paths exist.** The [`steam/`](../../steam) dir (controller config) signals desktop-Steam intent; macOS is a first-class Steam target. Direct `.dmg`/notarized `.app` is the other path. Both are out of scope for "make it run" but the hooks are present. Steam's macOS redistributable (`libsteam_api.dylib`) would need wiring analogous to the Linux `redistributable_bin/linux64` block ([`CMakeLists.txt:716`](../../CMakeLists.txt)) — only if `WF_ENABLE_STEAM=ON`, which is off by default.
- **Code signing.** Not needed for local dev or Codemagic headless verify (iOS Phase 1 ran unsigned on the Simulator). Needed for Gatekeeper-clean distribution (Developer ID + notarization) — a distribution task, ~1–2 d once an Apple Developer account exists (the [$99 account is still pending](../../CLAUDE.md) for iOS Phases 4–5; the macOS port can proceed unsigned until then).

## 7. Recommended sequencing

```
Pass 1 (runtime, ~3 wk)                 Pass 2 (engine delta, ~4 wk)
─────────────────────────               ──────────────────────────────
R1 CMake branch        ─┐               E1 Rust/CRDT        ─┐ (parallelizable
R7 Jolt verify          │ week 1         E3 wf-edit build    │  with late Pass 1)
R6 WAMR aarch64        ─┘               E2 host-GL NSGL/CGL ─┘ ← critical path
R2 GLFW-Cocoa window  ─┐ week 2         E4 AVFoundation cap ─┐
R3 input               │                E5 mic + codecs      │ weeks 2–3
R4 audio / R5 bundle  ─┘               E6 collab transport  ─┘
R8 integration/playable┐ week 3         E7 brew deps / E8 relay  week 3
R9 CI                  ┘                E9 tests + screenshots   week 4
        │                                        │
        ▼                                        ▼
   PLAYABLE .app                          COLLABORATIVE EDITOR .app
```

- **Do Pass 1 first and in full** — it retires every shared risk (toolchain, frameworks, windowing, GL-on-mac) and produces an independently valuable artifact (a playable Mac game) before any editor work.
- **The two passes can overlap** at the boundary: once R2 (GLFW-Cocoa) lands, the editor's E1/E3 can start in parallel against the same windowing work, since the [iOS port has a second collaborator](../../CLAUDE.md) who could take the editor delta.
- **Front-load the two scary items** within each pass: R2 (window first-light) and E2 (host-GL handshake). Both are "blank screen until it's exactly right" tasks; failing fast on them de-risks the rest.

## 8. Open questions (decisions, not blockers)

1. **GL vs Metal** — recommended GL (§3). If the project wants macOS to *lead* the Metal migration instead of riding iOS, add the iOS Phase 2C+ Metal completion (a separate, larger effort) as a prerequisite and re-scope Pass 1 R2 to MTKView. Default: GL.
2. **arm64-only vs universal** — recommended arm64-first, universal deferred to distribution.
3. **GLFW for the runtime, or raw Cocoa/CGL?** — recommended GLFW (vendored, editor already uses it, minimal new code). Raw Cocoa is more "native" but unjustified for a windowing shim.
4. **Does the macOS runtime ship the full scripting roster** (Lua/JS/WAMR/Wren) like Linux desktop, or trim to Forth-only like mobile? Desktop has the RAM/flash budget, so default to the full roster; trimming is a one-line `if(APPLE AND NOT IOS)` change if desired.

## 9. Out of scope

App Store / notarized distribution, Steam macOS depot upload, universal-binary lipo, Touch Bar / macOS-specific UI chrome, sandbox entitlements beyond camera/mic for E4/E6, localization, crash reporting. (Parallels the [Android port closure](2026-04-18-android-port-closure.md) "intentionally out of scope" list.)

## References

- [`CMakeLists.txt`](../../CMakeLists.txt) — platform branches (`:103-162`), Jolt/Xcode note (`:447`), iOS bundle (`:835`), wf-edit target (`:910-1021`)
- [`wfsource/source/gfx/gl/mesa.cc`](../../wfsource/source/gfx/gl/mesa.cc), [`display.cc`](../../wfsource/source/gfx/gl/display.cc) — X11/GLX windowing to port
- [`wfsource/source/gfx/glpipeline/backend_modern.cc`](../../wfsource/source/gfx/glpipeline/backend_modern.cc) — `#version 330 core` (the reuse-on-macOS keystone)
- [`wfsource/source/gfx/host_gl_context.h`](../../wfsource/source/gfx/host_gl_context.h) + [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) — GLX-typed editor handshake (E2)
- [`wfsource/source/hal/ios/`](../../wfsource/source/hal/ios) — Metal backend reference (Option B)
- [docs/plans/2026-04-21-ios-port-codemagic.md](../plans/2026-04-21-ios-port-codemagic.md) — iOS port plan/phasing (calibration)
- [docs/investigations/2026-04-18-android-port-closure.md](2026-04-18-android-port-closure.md) — comparable port closure (calibration)
- [docs/investigations/2026-05-18-collaborative-level-editor-design.md](2026-05-18-collaborative-level-editor-design.md) — editor architecture
- [docs/investigations/2026-05-26-internet-voice-video-nat-traversal.md](2026-05-26-internet-voice-video-nat-traversal.md) — collab encryption requirement (E6)
- [docs/wf-status.md](../wf-status.md) — iOS phase status ("cornflower blue" / Phase 2B3)
