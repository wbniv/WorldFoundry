# Investigation: VR / AR / mixed-reality headset support in World Foundry

**Date:** 2026-04-28
**Status:** Survey + scoped plan. Not committed; intended as the reference doc for any future "should we put WF on a headset?" conversation. Two artifacts: (a) an engine-side gap analysis — what WF would have to grow to ship a VR or AR build — and (b) an exhaustive catalog of headset hardware still in production as of 2026-04, to ground "which targets first" decisions in actual market reality rather than nostalgia.
**Depends on:** `docs/investigations/2026-04-28-engine-capabilities-survey.md` (engine profile), `docs/investigations/2026-04-14-jolt-physics-integration.md` (variable tick rate is load-bearing).
**Related:** `docs/investigations/2026-04-14-multiplayer-voice-mobile-input.md` (mobile input + AR back-camera scenarios), `docs/investigations/2026-04-28-mainline-console-controllers-since-1996.md` (sibling catalog format).

## Context

The engine-capabilities survey listed "first-person camera rig" as a known gap. VR / AR is the more demanding cousin of that gap: it's a first-person camera rig *plus* per-eye stereo rendering *plus* a 90 Hz+ frame-time floor *plus* 6DoF tracked input *plus* — for AR — composited passthrough and spatial anchors. Each of those is a known-shape engine project; together they are roughly the largest single bundle of new subsystems the engine could take on.

This investigation does two things. First, it characterises that bundle: which WF subsystems would have to change, in what order, and what each costs. Second, it catalogues the headset market that bundle would target — what's actually still being made in 2026, what each device's API surface looks like, and which clusters of hardware can be hit with a single engine investment.

The framing is "if we wanted to," not "we should." The recommendation section closes with a lean first-target shortlist for the user to react to, not a roadmap.

---

## Part 1 — Engine-side gap analysis

### What "VR-ready" actually requires

Headset support is not one feature; it's a stack. A faithful list, ordered by how non-negotiable each piece is:

1. **Stereo rendering.** Render the scene twice per frame (once per eye) with per-eye view + projection matrices supplied by the runtime. Single-pass-stereo (multiview) and two-pass implementations both exist; multiview saves ~20–40% GPU cost and is the modern default.
2. **Head pose tracking.** Read predicted head pose every frame (position + orientation in room space) and drive the camera matrices from it. Pose source is the runtime (OpenXR on most platforms, Apple's `CompositorServices` / ARKit on visionOS).
3. **Frame-rate floor.** VR demands 72 Hz minimum, 90 Hz typical, 120 Hz on flagship hardware. WF's tick rate is variable (`docs/investigations/2026-04-14-jolt-physics-integration.md`). Variable-tick is fine for *gameplay logic*; for *rendering* the engine must hit a rock-steady headset cadence or the runtime drops frames into reprojection. This is the single hardest constraint to retrofit.
4. **Lens distortion + chromatic aberration + reprojection.** All handled by the runtime in OpenXR; the engine submits a flat-projected image per eye and the runtime warps. Free (in the sense that no engine code has to do it), but the engine must submit correctly-sized targets and respect the runtime's expected color space (usually linear sRGB or HDR10).
5. **6DoF controller input.** Tracked controllers report position + orientation + buttons + analog axes. WF's input layer is a joystick bitmask (`INDEXOF_HARDWARE_JOYSTICK*`); 6DoF pose is a different shape and needs new mailbox slots. Same axis question as the mobile-input doc's gyro/accelerometer slots.
6. **Locomotion + comfort.** VR-specific movement modes: smooth locomotion with head-relative direction, teleport, snap-turn, optional vignette-on-acceleration. These are *gameplay primitives*, not engine subsystems — but the existing character controller assumes a fixed forward axis from a third-person camera, so adapting it for head-relative control is a small but real refactor.
7. **Hand tracking (optional).** OpenXR exposes 26-joint hand pose on devices that support it (Quest, Vision Pro, Galaxy XR, Pico, AVP). New input shape — interpret pinch / point / fist as button events, or feed joint positions to scripts.
8. **Eye tracking (optional, increasingly common).** Used for *gaze pointer* (looks-at-button activates) and *foveated rendering* (high resolution where the eye looks, lower elsewhere). Quest Pro / PSVR2 / AVP / Galaxy XR / Beyond 2e / Crystal Super all support it.
9. **Foveated rendering (optional but accelerating).** Without it, the high-resolution headsets (Crystal Super at 3840×3840 per eye, AVP, Galaxy XR) are unreachable on commodity GPUs. Two flavours: *fixed foveation* (always lower-resolution at the periphery, cheap) and *eye-tracked foveation* (follows the gaze, expensive to integrate but ~2× the GPU savings).
10. **Passthrough composition.** For mixed-reality. The runtime provides the camera image; the engine composites virtual pixels on top with alpha. Quest 3 / Vision Pro / Galaxy XR / AVP / Vive Focus Vision all have colour passthrough. Mono passthrough on Quest 2 / older PSVR; not useful for MR.
11. **Spatial anchors + plane detection (AR-specific).** Persistent virtual-content placement keyed to recognised features in the real world. ARKit on visionOS, OpenXR `XR_FB_spatial_entity` extensions on Quest, ARCore `ARSession` on Android XR. No equivalent in WF today; the room-graph world model has nothing to anchor to.
12. **Room-scale boundary / guardian.** The runtime exposes a play-space polygon; the game should read it and constrain content. Free from OpenXR; engine just consumes it.

### Mapping that onto WF subsystems

| WF subsystem | Today | Required change for VR | Change for AR (deltas vs VR) |
|---|---|---|---|
| `gfx/glpipeline/` | Single-viewport OpenGL renderer | Stereo: dual viewport, per-eye view matrices, multiview path. New OpenXR runtime backend. Likely Vulkan backend on Android-XR targets (Quest / Pico / Steam Frame / Galaxy XR all expect Vulkan; OpenGL ES path exists but is deprecated on Quest). | Composite over passthrough alpha. Add HDR-aware tone-mapping for AVP / Galaxy XR. |
| `gfx/camera.{cc,hp}` | `CamShot` + `BungeeCameraHandler` | New `HeadPoseCameraHandler` driven by OpenXR `xrLocateViews`. CamShots become irrelevant in VR (the headset *is* the camera) but must be cleanly bypassed, not deleted, since non-VR builds still use them. | Same as VR. AR adds spatial-anchor-relative camera origins. |
| `hal/` (input) | Joystick bitmask (`EJ_BUTTONF_*`, mailbox 3024) | New mailbox slots for left + right controller pose (×7 floats each), grip / trigger analogs (already joystick-like), thumbstick (already joystick-like), system / menu / B / Y face buttons. Hand-tracking joints behind a feature flag. | Eye-tracking gaze ray as new input axis. |
| `room/` | Static room graph; teleporting actors between rooms | Mostly fine — VR experiences fit room-graph structure naturally (small "scene" levels rather than open worlds). Add play-space-aware spawn logic so the player is never teleported into a wall. | Spatial anchors as a *new* room-graph primitive: rooms anchored to real-world features rather than world-space coordinates. Open-shape design problem. |
| `movement/` | Walk/run/jump/fall character controller | New "VR locomotion" controller modes: head-relative smooth locomotion, teleport-with-arc, snap-turn, optional vignetting. Existing walk mode usable as a *seated VR* baseline. | AR doesn't generally use locomotion — the player walks in the real world. The engine must accept *real* head motion as the only input, with no virtual locomotion. |
| `physics/` (Jolt, post-integration) | Jolt with variable tick | Jolt is fine; the issue is *frame pacing*, not physics. Pin the render loop to the headset's vsync; let physics tick at its existing variable rate inside a fixed wall-clock budget. The Jolt integration plan already sketches this. | Same as VR. |
| `audio/` | Per-level MIDI + 3D-positional SFX | 3D audio is already there; the additional ask is HRTF spatialisation, which most headsets expect. OpenXR exposes head-pose-relative audio listener; route via Steam Audio or built-in OpenXR audio. | Same as VR, plus AR-specific "occluded by real-world geometry" — out of scope for v1. |
| Mailbox bus | Single shared scalar bus | Add per-controller, per-eye, gaze, hand-joint mailbox regions. Same pattern as the cell-array regions sketched in the Lode Runner / Bomberman briefs. | Add anchor-pose mailboxes. |
| Build / packaging | Linux primary, Android, iOS WIP | Add: (a) PCVR build (OpenXR via SteamVR or Oculus runtime), (b) Quest / Pico / Steam Frame standalone Android-XR build, (c) Vision Pro visionOS build (separate ecosystem; see Part 3). | Same as VR — but the Vision Pro / Galaxy XR / Quest 3 split between "VR mode" and "MR mode" is an OS-level configuration, not three different builds. |

### Phasing — engine work

Treat this as a one- to two-quarter project per phase, building the lowest-risk capability first and stopping where the value stops.

- **Phase A — PCVR baseline (1 quarter).** OpenXR runtime against SteamVR on Linux. Stereo OpenGL via the existing `glpipeline/`. `HeadPoseCameraHandler`. Existing keyboard / gamepad input — no tracked controllers yet. Verify on a Valve Index or Bigscreen Beyond 2 over Wi-Fi. Acceptance: snowgoons-blender renders in stereo, head-look works, frame rate ≥ 90 Hz at native resolution. This phase says "the engine can VR" without committing to standalone or controllers.
- **Phase B — 6DoF controllers + comfort (~1.5 months).** OpenXR Action API → mailbox bus. Smooth locomotion (head-relative), snap-turn, teleport. Vignette-on-acceleration as a global toggle. Acceptance: `wflevels/snowgoons-blender/` is playable end-to-end with two Touch / Index / Sense controllers.
- **Phase C — Standalone Android-XR (1 quarter).** Vulkan backend in `gfx/glpipeline/` (or `gfx/vkpipeline/`). OpenXR Android loader. Quest 3 + Pico 4 Ultra + Steam Frame as primary targets. Performance budget overhaul: target ≥ 72 Hz on Snapdragon XR2 Gen 2 hardware. Acceptance: a single `.apk` runs snowgoons-blender on Quest 3 standalone at 72 Hz.
- **Phase D — Hand tracking, eye tracking, foveated rendering (~1.5 months).** Behind feature flags. Hand-pinch as the default "select" interaction; gaze + pinch as an alternative. Fixed foveation as default on standalone; eye-tracked foveation on Quest Pro / Crystal Super / AVP / Galaxy XR. Acceptance: snowgoons playable controllerless on Quest 3 + Vision Pro; Crystal Super hits 90 Hz at native res via foveation.
- **Phase E — Mixed-reality / passthrough (~1 month).** Compose over passthrough alpha. Define an "MR mode" for selected levels (`physics/`-style demos translate well — a stack of dominoes on the user's actual coffee table). Acceptance: a domino-stack MR demo on Quest 3 with passthrough background.
- **Phase F — AR / spatial anchors (1 quarter).** OpenXR spatial-entity extensions on Quest; ARKit on visionOS; ARCore on Android XR. Persistent placement of virtual content keyed to real-world features. New room-graph primitive: `AnchoredRoom`. Acceptance: a treasure-hunt level where prizes are placed in the user's actual room and persist across sessions. This phase is the largest design-shape change in the bundle and the most reasonable to defer or skip.
- **Phase G — Apple Vision Pro / Galaxy XR native (~1 quarter).** Separate from VR-on-OpenXR because visionOS does not implement OpenXR (Apple has not adopted it; see Part 3). Requires a Metal renderer, `CompositorServices` integration, `RealityKit` interop for AR mode. Galaxy XR is OpenXR-conformant via Android XR, so it's covered by Phase C — Vision Pro is the genuine ecosystem fork.

Total greenfield engine work for *all* of A–F: roughly 7–9 months of concentrated effort by one engineer who knows the renderer; longer with realistic ramp-up. Phase G is a separate parallel track for the Apple ecosystem, costing another quarter.

Stopping after Phase B is a defensible "PCVR-only" outcome with most of the value of VR-as-a-feature; stopping after Phase C is a defensible "standalone-headset-supported" outcome that addresses ~80% of the consumer install base.

### Things this plan deliberately does not include

- **Full-body tracking** (Vive Trackers, SlimeVR). Niche; out of scope.
- **Haptic suits** (bHaptics, Teslasuit). Niche.
- **Treadmill / locomotion hardware** (Virtuix, KAT VR). Niche.
- **Webcam-based positional tracking** (early Pico, Windows Mixed Reality). Hardware deprecated.
- **Cloud-streamed VR** (CloudXR, Resolution Games' streaming). Tail-end use case; Phase A's PCVR streaming path covers most of it.
- **Cross-headset session multiplayer.** That's a multiplayer concern, covered by `docs/investigations/2026-04-14-multiplayer-voice-mobile-input.md`.

---

## Part 2 — Hardware market survey (still in production, 2026-04)

This is the catalog the engine work targets. Same shape as `docs/investigations/2026-04-28-mainline-console-controllers-since-1996.md`: per-category tables, MSRP at the manufacturer's storefront, production status, link to the canonical purchase page (or eBay search if discontinued).

**Caveats.** "In production" means the manufacturer ships new units through their direct channel as of 2026-04. Prices are USD MSRP; some are recent (Quest 3 increase to $619 effective 2026-04-19) and some are stable from launch. I have not personally verified every spec line against datasheets — fact-check before quoting in commitments. URLs are storefront category pages where deep-product URLs are unstable.

### Category 1 — Standalone consumer VR (the volume bracket)

The "Quest-shaped" market: self-contained Snapdragon-class headsets, optional PCVR streaming. This is where the install base lives.

| Headset | Launch | Display (per eye) | Tracking | Compute | Connectivity | MSRP (USD) | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| **Meta Quest 3** | 2023-10 | 2064×2208 LCD, pancake lens, 110° H FOV, 120 Hz | Inside-out 6DoF + colour passthrough + hand + (optional) eye-tracking accessory | Snapdragon XR2 Gen 2, 8 GB | Wi-Fi 6E + USB-C (Link / Air Link) | $499 → **$619** (2026-04-19 increase) | In production | The default consumer VR target. RAM-shortage-driven price hike in April 2026. [Buy at Meta](https://www.meta.com/quest/quest-3/) |
| **Meta Quest 3S** | 2024-10 | 1832×1920 LCD, *Fresnel* lens, 96° H FOV, 120 Hz | Same as Quest 3 minus depth sensor | Snapdragon XR2 Gen 2, 8 GB | Wi-Fi 6E + USB-C | $299 (128 GB) / $399 (256 GB) | In production | Quest 2 optics + Quest 3 SOC; the "cheap entry" SKU. [Buy at Meta](https://www.meta.com/quest/quest-3s/) |
| **Pico 4 Ultra** | 2024-09 | 2160×2160 LCD pancake, 105° H FOV, 90 Hz | Inside-out 6DoF + colour passthrough + hand | Snapdragon XR2 Gen 2, 12 GB | Wi-Fi 7 + USB-C | €549 (~$590) | In production | ByteDance's flagship; **not sold in North America**. Pico 5 was cancelled in favour of a 2026 high-end model targeting Vision Pro. [Buy at Pico](https://www.picoxr.com/global/products/pico4-ultra) |
| **Pico (2026 unnamed)** | Late 2026 / early 2027 (announced) | ~4000 PPI micro-OLED, 40 PPD avg / 45 PPD peak | Inside-out + dedicated R1-style passthrough chip | Successor SOC: claims 2× CPU/GPU vs XR2 Gen 2 | TBA | TBA | Announced | Same "Vision Pro fighter" positioning as Galaxy XR. ~270 g target weight. North-America availability unconfirmed. |
| **HTC Vive Focus Vision** | 2024-10 | 2448×2448 LCD, Fresnel, 120° H FOV, 90 Hz | Inside-out + eye-tracking + colour passthrough | Snapdragon XR2 Gen 1 (older), 12 GB | Wi-Fi 6 + DisplayPort *via dongle* (PCVR) | $1,000 | In production | Hybrid standalone + tethered. Older SOC reflects HTC's enterprise-leaning pricing. [Buy at HTC](https://www.vive.com/us/product/vive-focus-vision/) |
| **HTC Vive XR Elite** | 2023 | 1920×1920 LCD, pancake, 110° H FOV, 90 Hz | Inside-out + colour passthrough | Snapdragon XR2 Gen 1, 12 GB | Wi-Fi 6 + USB-C | $900 (down from $1,100 launch) | In production | Convertible glasses-form-factor; battery in the strap, detachable. [Buy at HTC](https://www.vive.com/us/product/vive-xr-elite/) |
| **Valve Steam Frame** | 2026 H1 (announced 2025-11) | 2160×2160 LCD pancake, 72/80/90/120/144 Hz | Inside-out 6DoF + 4× monochrome passthrough cams + IR + eye-tracking | Snapdragon 8 Gen 3, 16 GB | Multiple Wi-Fi 7 radios (split traffic) + USB-C | "cheaper than Index" — speculation $700–$1000 | Announced (delayed by RAM pricing) | SteamOS-on-ARM-native; Proton translates Linux apps. Streaming-first. The Index successor. [Steam Frame product page](https://store.steampowered.com/) |

Hitting all six in-production devices in this category is what Phase C buys: one Vulkan / OpenXR Android-XR build covers Quest 3 + Quest 3S + Pico 4 Ultra + Vive XR Elite + Vive Focus Vision (the latter two run an Android-derived OS, also OpenXR-conformant) + Steam Frame at launch. Deltas are per-device tuning, not per-device builds.

### Category 2 — Spatial-computing / mixed-reality (premium)

Higher-priced, higher-resolution headsets that emphasise mixed-reality use cases over gaming.

| Headset | Launch | Display (per eye) | Tracking | Compute | Connectivity | MSRP (USD) | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| **Apple Vision Pro (M5)** | 2025-10 (M5 refresh) | 4K micro-OLED, ~3,660×3,200, 100° FOV, 100/120 Hz | Inside-out + LiDAR + eye + hand (no controllers shipped) | Apple M5 + R1 | Wi-Fi 6E + tethered battery pack (~2 h) | $3,499 (256 GB) | In production | M5 refresh keeps original price; adds 120 Hz, hardware ray-tracing, ~10% more rendered pixels. visionOS = **does not implement OpenXR**; engine must support `CompositorServices` + Metal natively (Phase G). [Buy at Apple](https://www.apple.com/shop/buy-vision/apple-vision-pro) |
| **Samsung Galaxy XR** | 2025-10 | 3552×3840 micro-OLED, 72/90 Hz | Inside-out + eye + hand; optional motion controllers ($250 sep.) | Snapdragon XR2+ Gen 2, 16 GB | Wi-Fi + tethered battery pack (~2–2.5 h) | $1,800 (256 GB; controllers separate) | In production | First Android XR device; OpenXR-conformant. The closest "Apple Vision Pro competitor at half the price." 847 g total. [Buy at Samsung](https://www.samsung.com/us/mobile/virtual-reality/) |
| **Apple Vision Air / "Vision Pro 2"** | Rumoured 2027 | Lighter, lower-cost successor | TBA | TBA | TBA | Rumoured ~$2,000 | Rumoured | Per the same Apple roadmap reporting. Not committed. |

### Category 3 — Tethered PCVR (high-end, narrow market)

Lighthouse-tracked or PC-tethered devices serving the SteamVR install base. Smaller volumes; loyal users; high spec ceilings.

| Headset | Launch | Display (per eye) | Tracking | Connectivity | MSRP (USD) | Status | Notes |
|---|---|---|---|---|---|---|---|
| **Valve Index** (full kit) | 2019 | 1440×1600 LCD, 130° FOV, 80/90/120/144 Hz | SteamVR Lighthouse 2.0 (external base stations) + Index Knuckles | DisplayPort + USB | $999 | In production (low volume) | Aging displays but the SteamVR-Lighthouse benchmark for tracking precision. Steam Frame is the standalone successor. [Buy at Steam](https://store.steampowered.com/valveindex) |
| **Bigscreen Beyond 2** | 2025-04 | 2560×2560 micro-OLED, pancake, 116° FOV, 90 Hz | SteamVR Lighthouse (BYO base stations) | DisplayPort + USB | $1,019 | In production | 107 g — ~⅓ the weight of a Quest 3. PCVR-only. Custom face-cushion based on a face scan. [Buy at Bigscreen](https://store.bigscreenvr.com/products/bigscreen-beyond-2) |
| **Bigscreen Beyond 2e** | 2025-04 | 2560×2560 micro-OLED + integrated eye-tracking | SteamVR Lighthouse + AI-driven eye tracking | DisplayPort + USB | $1,219 | In production | Eye-tracking variant. Same form factor, ~108 g. [Buy at Bigscreen](https://store.bigscreenvr.com/products/bigscreen-beyond-2e) |
| **Pimax Crystal Light** | 2024 | 2880×2880 QLED, glass aspheric lens, 120 Hz | Inside-out (no Lighthouse) | DisplayPort + USB | $899 (or $599 + Pimax Prime sub) | In production | Tethered-only; "lighter Crystal" — the entry into Pimax's high-PPD line. [Buy at Pimax](https://pimax.com/pages/crystal-light) |
| **Pimax Crystal Super** | 2025-04 | 3840×3840 QLED (or optional micro-OLED engine), 57 PPD, 120° FOV | Inside-out; optional Lighthouse faceplate | DisplayPort + USB | $1,695 ($999 + Pimax Prime) | In production | "Retina-level" PPD claim is real on paper — eats GPUs alive without foveated rendering. [Buy at Pimax](https://pimax.com/products/pimax-crystal-super/) |
| **Pimax Crystal Super 2** | Q4 2026 (announced) | TBA | TBA | TBA | TBA | Announced | Successor product; specs not yet final. |

This category is the *Phase A* target for WF: SteamVR + OpenXR is the lowest-friction path to a working VR build, and it covers all of the above in one runtime. No standalone Android work needed.

### Category 4 — Console VR (Sony)

| Headset | Launch | Display (per eye) | Tracking | Connectivity | MSRP (USD) | Status | Notes |
|---|---|---|---|---|---|---|---|
| **PlayStation VR2** | 2023-02 | 2000×2040 OLED, 110° FOV, 90/120 Hz | Inside-out + integrated eye-tracking + Sense controllers | Single USB-C to PS5 | $549 (down from $549 launch; Sony has aggressively discounted at retail) | In production | The cheapest OLED-with-eye-tracking on the market. PSVR2 is OpenXR-conformant per Khronos's adopters list. [Buy at PlayStation](https://direct.playstation.com/en-us/playstation-vr2) |
| **PlayStation VR2 PC Adapter** | 2024-08 | (uses PSVR2 hardware) | (PSVR2 tracking, PSVR2 Sense controllers) | DisplayPort + USB to PC | $59.99 | In production | Sony-blessed PC support: SteamVR via the adapter. Eye-tracking works on PC; haptics / adaptive triggers do not. Unlocks PSVR2 as a PCVR target. [Buy at PlayStation](https://direct.playstation.com/en-us/buy-accessories/playstationvr2-pc-adapter) |

A native PS5 build of WF is its own engineering project (Sony devkit, certification, store submission). The PSVR2 PC Adapter sidesteps that — the same Phase A SteamVR build hits PSVR2 users on PC without any Sony involvement.

### Category 5 — "Display" smart glasses (transparent display, lightweight)

Glasses-form-factor devices with a real display in the lens, typically driven by a tethered phone or a dedicated puck. The market split is between *micro-OLED birdbath* designs (XREAL / Viture / Rokid) which deliver a virtual TV-style image and *waveguide* designs (Even Realities / Halliday / Meta Ray-Ban Display) which are lower-resolution but sized like real glasses.

| Glasses | Launch | Display | Connectivity | MSRP (USD) | Status | Notes |
|---|---|---|---|---|---|---|
| **XREAL One** | 2024 | 1920×1080 micro-OLED birdbath, 50° FOV, 120 Hz | USB-C DP-Alt; tethered to phone/PC/console | $499 | In production | XREAL's flagship. 3DoF tracking. [Buy at XREAL](https://www.xreal.com/) |
| **XREAL One Pro** | 2025 | 1920×1080 micro-OLED, ~57° FOV, 120 Hz | USB-C DP-Alt | ~$599 | In production | Larger FOV variant. Direct successor to the One. |
| **XREAL 1S** | 2026 | 1920×1080 micro-OLED, 120 Hz | USB-C DP-Alt | $449 | In production | The 2026 entry-tier; slots below the One. Hardware partner for **Google Project Aura** (Android XR glasses). |
| **XREAL Air 2 Pro** | 2023 | 1920×1080 micro-OLED, 46° FOV, 120 Hz | USB-C DP-Alt | $399 (regular $429) | In production | Older but still shipping. Electrochromic dimmable lenses. 75 g. [Buy at XREAL](https://www.xreal.com/) |
| **VITURE Pro / Beast** | 2025–2026 | 1920×1080 micro-OLED, 3DoF | USB-C DP-Alt | ~$439 (Pro); Beast TBA | In production | XREAL's closest competitor. The Beast (CES 2026) prototype hints at a higher-end launch. [Buy at VITURE](https://www.viture.com/) |
| **Rokid AR Spatial / Rokid Glasses** | 2024–2025 | 1920×1080 micro-OLED (Spatial); mono-display waveguide (Glasses) | USB-C DP-Alt or BT to phone | ~$550 (Spatial); $599 (Glasses) | In production | Glasses (49 g) are the closest "all-day-wearable" model; Spatial competes directly with XREAL One. [Buy at Rokid](https://global.rokid.com/) |
| **Even Realities G1** | 2024 | Waveguide, 640×200 monochrome | BT to phone | $599 | In production | Prescription-frame form factor. Very limited UI surface — notifications + AI replies. |
| **Even Realities G2** | 2025–2026 | Waveguide, 640×350 monochrome green, 27.5° FOV, 60 Hz, 1200 nits | BT to phone | TBA (G1 is $599) | In production | "HAO 2.0" — micro-LED + thinner waveguide. The closest "actual eyeglasses with a display" experience. |
| **Halliday DigiWindow Glasses** | 2025-03 | Single-eye waveguide, 3.5″ virtual display | BT to phone | $489 (post-Kickstarter) / $369 backer | In production | DigiWindow projector module sits above one eye. AI assistant + 40-language live translation. 28.5 g. [Halliday store](https://hallidayglobal.com/) |
| **Meta Ray-Ban Display + Neural Band** | 2025-09-30 | 600×600, 42 PPD, 20° FOV, 5,000 nits monocular waveguide | Wi-Fi/LTE to phone + EMG wristband | $799 (incl. Neural Band) | In production | First mainstream "actually wearable" smart glasses with a display. Neural Band reads forearm muscle signals as input — a genuine novel input shape. [Buy at Meta](https://www.meta.com/ai-glasses/meta-ray-ban-display/) |

Engine fit for this category is *limited*. Most of these glasses are passive displays — the connected phone or PC produces the image, the glasses just present it. For WF this means: a phone build that detects DP-Alt-Mode display and renders a stereo or mono image is sufficient to "support" XREAL / VITURE / Rokid Spatial. There is no head-tracking on these without a separate hardware path (XREAL Beam Pro accessory, Spatial mode), so they are not first-class VR targets. They are content-display targets — closer in shape to "WF on a phone with a big screen attached" than to "WF on a Quest."

The Even / Halliday / Meta Ray-Ban Display tier is even further out of scope: pixel budgets too small, FOV too narrow, no positional tracking. They're notification surfaces, not gameplay surfaces. Acknowledged for completeness, not as targets.

### Category 6 — "Camera + audio" smart glasses (no display)

Glasses with camera, microphones, speakers, and AI features but **no display in the lens**. Out of scope for game rendering, but worth listing because they overlap heavily with the AR-glasses headlines and the user is likely to hit them when researching.

| Glasses | Launch | Capabilities | MSRP (USD) | Status |
|---|---|---|---|---|
| **Ray-Ban Meta (Gen 2)** | 2023, ongoing SKU updates | Camera, mics, speakers, Meta AI assistant; **no display** | $299 (Wayfarer) – $379 (Headliner) | In production |
| **Ray-Ban Meta Gen 3** | 2026 (rumoured / FCC filing) | Same shape, faster SOC, longer battery | TBA | Announced |

Useful as a microphone-and-camera input channel in a multi-device experience (cf. the mobile-input plan's "phone-as-companion-screen" idea), but the engine has nothing to render to here.

### Category 7 — Enterprise / industrial XR

Enterprise headsets with high spec ceilings and high prices. Mostly off-strategy for WF (which is a consumer-grade engine), but listed because requests *do* come in for this segment and the engineering cost looks superficially similar to consumer VR.

| Headset | Launch | Display (per eye) | Tracking | MSRP (USD) | Status | Notes |
|---|---|---|---|---|---|---|
| **Varjo XR-4** (standard) | 2023-12 | 3840×3744 micro-OLED + Bionic 51 PPD lens system, 120° H FOV, 90 Hz | Inside-out + eye + hand; tethered to PC | $5,990 | In production | Auto-IPD; eye-tracking-driven foveated rendering is *required* to drive these displays. |
| **Varjo XR-4 Focal Edition** | 2023-12 | XR-4 + autofocus passthrough | + autofocus cams | $9,990 | In production | The autofocus passthrough is the genuine differentiator — close-range MR tasks read sharp. |
| **Varjo XR-4 Secure Edition** | 2024 | XR-4 + air-gapped firmware variants | (closed) | $18,000–$32,000 | In production | Defence / classified-environment SKU. Plus a $2,500/yr advanced-MR subscription for Focal Edition features. |
| **Microsoft HoloLens 2** | 2019 | Waveguide, 2K equivalent | Inside-out + hand + eye | $3,500 | **Production ended 2024-10**, support until 2027-12 | HoloLens 3 cancelled. Industrial AR headset; engine work on WF would not target this. |
| **Microsoft HoloLens IVAS** | (military) | (not public) | — | — | In production (military only) | The U.S. Army Integrated Visual Augmentation System variant lives on. Not a WF target. |
| **Magic Leap 2** | 2022 | Waveguide, 1440×1760 per eye, 70° diagonal FOV | Inside-out + eye | ~$3,300 (base) | **Sales discontinued globally 2026-03** | Magic Leap pivoting to technology-licensing partnerships rather than hardware. |
| **Vuzix Blade / M-series** | ongoing | Waveguide, lower-res | Limited | $500–$2,500 | In production | Industrial headsets with narrow, focused use cases (warehouse picking, telepresence). |
| **RealWear Navigator 520** | 2023 | Single-eye micropanel | — | ~$2,500 | In production | Hands-free voice-driven industrial wearable. Out of game-engine scope. |

The Varjo XR-4 line and the Bigscreen Beyond 2 are the only two entries on the entire survey that *require* eye-tracked foveated rendering to be usable; everything else benefits from foveation but doesn't depend on it.

### Recently discontinued (still relevant context)

Worth noting because online searches surface these and they are *not* live targets:

- **Meta Quest 2** — production ended 2024. Still a large install base; the App Store accepts updates, but it's a v1-only target now.
- **Meta Quest Pro** — discontinued 2023.
- **HP Reverb G2** — discontinued; Windows Mixed Reality platform deprecated by Microsoft 2023.
- **All Windows Mixed Reality headsets** (Acer, Dell, Lenovo Explorer, HP, Samsung Odyssey) — platform-deprecated; OS-side runtime is gone.
- **Varjo XR-3 / VR-3 / Aero** — software support ends 2026-01; production already ended.
- **Pimax 8K / 8KX / Crystal OG** — superseded by Crystal Light / Super.
- **Oculus Rift / Rift S** — discontinued 2021.

### Aggregate market shape (rough, observational)

- **Consumer VR install base is Quest-dominated.** Quest 2 + 3 + 3S together represent a large majority of consumer headsets in active use. Pico is the second-largest globally but absent from North America. Steam Frame, Galaxy XR, and the 2026 Pico high-end are all positioned to *fight Quest's dominance*, not to grow a separate market.
- **PCVR is a niche that won't die.** Bigscreen Beyond 2 (107 g, $1,019) and Pimax Crystal Super ($1,695, 57 PPD) sell to a small audience that is not price-sensitive. Steam Frame is Valve's bet that the niche is large enough to be worth the engineering.
- **Apple has the premium MR slice to itself (for now).** Vision Pro at $3,499 is unique in its tier. Galaxy XR at $1,800 is the cheapest credible competitor.
- **Smart glasses-with-display are happening but not as gameplay surfaces.** Ray-Ban Meta Display, Halliday, Even G2, XREAL One are real products selling real units, but their pixel budgets and FOVs do not reach "play a 3D game" territory. They are notification + AI-assistant surfaces.
- **Enterprise AR is contracting, not expanding.** HoloLens dead, Magic Leap pivoting away from hardware. Varjo holds the high-end-VR-with-passthrough niche unchallenged.

---

## Part 3 — API / SDK landscape

The reason "VR support" is *one bundle* and not eight separate ones is that the industry has mostly standardised on **OpenXR** (Khronos) as the runtime API. An OpenXR-conformant engine builds once and runs on every conformant runtime. Where it doesn't apply is the question.

### OpenXR-conformant runtimes (in production)

| Runtime | Vendor | Headsets covered |
|---|---|---|
| **Meta Quest OpenXR runtime** | Meta | Quest 2 / 3 / 3S / Pro (standalone + PCVR via Link) |
| **Oculus PC runtime (PCVR)** | Meta | Quest series tethered to PC |
| **SteamVR / OpenXR** | Valve | Index, Bigscreen Beyond 2, Pimax (Crystal Light / Super), HTC Vive series, PSVR2 (via PC adapter), Steam Frame (announced) |
| **Pico OpenXR (1.1-conformant)** | ByteDance | Pico 4 Ultra (and back-ported to Pico 4 / Neo 3) |
| **PSVR2 OpenXR (PS5 native)** | Sony | PSVR2 on PS5 (Sony is an OpenXR adopter; PS5-native build path) |
| **HTC OpenXR** | HTC | Vive Focus Vision, XR Elite |
| **Android XR OpenXR** | Google + Samsung | Galaxy XR, future Project Aura glasses, future Android XR licensees |
| **Varjo OpenXR** | Varjo | XR-4 series |
| **Monado** | Open-source (Collabora) | Reference open-source runtime; covers any device with a Monado driver, including Lighthouse hardware on Linux |

### Notable holdouts

- **Apple visionOS** does not implement OpenXR. Apple has not signed Khronos OpenXR adoption. The visionOS path is Metal + `CompositorServices` (the immersive-app API) + RealityKit (for AR-style content). Unity / Unreal provide compatibility shims but require a separate build target. **For WF, this means Vision Pro is its own engine port (Phase G), distinct from the OpenXR umbrella.**
- **Console-native PSVR2-on-PS5** requires Sony's developer programme (libpsvr2-equivalent) for full feature parity (haptics, adaptive triggers, headset-feedback motor). The PC adapter sidesteps this but exposes only ~80% of PSVR2's hardware.

### Engine-side architectural implication

The cleanest engine architecture is two backends:

1. **OpenXR backend** — used for everything except Apple. One implementation; SteamVR / Quest / Pico / Steam Frame / PSVR2-on-PC / Galaxy XR / Vive Focus Vision / Varjo / etc. all light up.
2. **visionOS backend** — Apple-specific. Metal renderer, `CompositorServices`, RealityKit interop. Only worth building once Phase A–F have validated the design and if Apple's market share warrants it (current AVP install base is small but high-spend).

For the AR-specific pieces (spatial anchors, plane detection), OpenXR exposes them as optional extensions. Coverage varies — `XR_FB_spatial_entity` is supported on Quest, partially on Pico, not yet on Steam Frame. The engine should treat AR features as **per-device capability flags** read from OpenXR at startup, not as global build-time choices.

---

## Part 4 — Recommendation if forced to pick

The question this investigation is meant to answer is *not* "should WF do VR" — that's a strategic call separate from this doc — but *what would it take and where would we start*.

If the answer is "yes, eventually," the lowest-risk first target is unambiguous:

**Phase A → SteamVR PCVR via OpenXR on Linux.** Valve Index or Bigscreen Beyond 2 as the daily-driver dev hardware. Pick one level (snowgoons-blender) and ship it as a stereo head-tracked experience with existing keyboard / gamepad input. ~1 quarter for someone fluent in the renderer. The result is a binary that runs on every PCVR headset on the market — Index, Beyond 2, Crystal Super, Quest 3 via Link, PSVR2 via PC adapter, Vive Focus Vision via DP, Steam Frame at launch — without per-device branches.

**Phase B → tracked controllers + comfort.** Same engine, same backend; adds 6DoF input to the mailbox bus and three locomotion modes. Now the same level is *playable*, not just observable. ~1.5 months.

That's the natural stopping point for "VR-as-an-engine-feature-not-a-product." Stopping there is fine; the value of "the engine technically supports VR" is real even if no level is purpose-built for it.

**Phase C → standalone Android XR (Quest / Pico / Steam Frame).** This is where VR becomes a serious product target rather than a tech demo, because standalone is where the install base is. It requires the Vulkan backend, which is the largest single piece of engine work in the bundle. ~1 quarter, parallel-able with content work.

**Phases D–F (eye/hand/foveation, MR, AR)** are quality-of-life additions on top of C; pick on a per-product basis.

**Phase G (visionOS)** stays deferred until there is a level that specifically benefits from Vision Pro's strengths (high pixel density, eye-tracked foveation, AR-spatial anchors over a quiet living-room environment) and the install base has grown past its current niche.

A defensible "minimum viable VR" deliverable — Phase A + B — sits at roughly **4–5 months** of engineering work; "VR product" — through Phase C — at roughly **8 months**.

### Counterargument worth flagging

VR is the highest-effort engine bundle on the menu. The engine-capabilities-survey lists several other gaps (vehicle physics, first-person camera rig, aimable ranged combat) whose engineering cost is much smaller and whose game-design payoff is comparable in size. None of those alternatives makes VR cheaper later, but they all ship faster. Whether VR is the *right* next major engine investment depends on whether the project's audience is "people who would play WF on a Quest" or "people who have not adopted VR." This investigation does not answer that question — it answers "if yes, here is the shape."

---

## Caveats / out of scope

- **Pricing volatility.** RAM-shortage-driven hikes (Quest 3, possibly others) are reshaping consumer VR pricing in 2026. Quote prices conservatively; verify against the manufacturer's storefront before committing in any contract or proposal.
- **Standalone-vs-tethered hardware boundary blurs.** Vive Focus Vision, Quest 3 with Link, Steam Frame in streaming mode all bridge categories. The categorisation above is by the *primary* operating mode, not the only one.
- **No personal hardware testing.** I have not tested any of these devices in this session. Specs + status are from manufacturer pages, Wikipedia, and well-sourced press as of 2026-04. Hands-on impressions are not in scope.
- **No deeper Apple / Metal architecture audit.** The visionOS entry above asserts "needs Metal + CompositorServices + RealityKit" as the path. A future investigation should validate that against current Apple developer documentation and Unity / Unreal porting guides before any commitment to Phase G.
- **No gameplay-design treatment.** This is an engine-side and market-side investigation. *What kinds of WF levels would be good in VR* (motion-comfort considerations, scale, locomotion patterns) is a separate brief.
- **No commercial / business-case analysis.** Storefront economics on Quest, App Store ratification for Vision Pro, SteamVR distribution — out of scope.
- **Per-platform certification effort not estimated.** Sony / Apple / Meta all have store-submission and certification processes that add time on top of pure engineering.

## Follow-ups (not committed)

1. **OpenXR runtime spike.** A 1-week spike: bring up an OpenXR Hello-world (clear-to-colour each eye + headset pose) inside the existing `glpipeline/` and validate on Linux + SteamVR + a test headset. Resolves the "can we get from here to there" question with a real PR rather than a doc.
2. **Vulkan backend scoping.** Separate investigation: how much of `glpipeline/` is genuinely backend-agnostic vs. how much is GL-specific. If it's mostly the former, Phase C cost shrinks; if the latter, Phase C cost grows.
3. **Foveated-rendering algorithm survey.** Fixed vs. eye-tracked; OpenXR `XR_FB_foveation_*` extensions vs. NVIDIA VRWorks vs. AMD's variable-rate shading. Gating subsystem for the high-PPD headsets.
4. **AR room-graph design.** If Phase F (spatial anchors) ever lands, the room model needs a redesign that this doc only sketches. Worth its own investigation before any code.
5. **Comfort-options taxonomy.** What's the WF default for snap-turn vs. smooth-turn? Vignette intensity? Standing vs. seated? Pull from existing OpenXR best-practice docs and propose a project-wide default; expose per-game overrides.
6. **Hand-input → mailbox shape.** Pinch / point / open / fist / one-finger-extended as the joystick-bitmask analogue. Worth aligning with the mobile-input plan's `INDEXOF_FACE_*` shape so scripts read fingers and faces from the same convention.
