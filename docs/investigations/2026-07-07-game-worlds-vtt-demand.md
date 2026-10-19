# Investigation: does the game-worlds / VTT segment actually want real-time browser co-editing?

**Date:** 2026-07-07
**Status:** Deep-research output (verified, 103 agents). Tests the load-bearing demand assumption under WorldFoundry's whole pitch. Read together with the [competitive landscape](2026-07-07-competitive-landscape.md) (which found the *supply* side — collaboration — already commoditized): this pass finds the *demand* side is weak for structured building too.

## Verdict: mostly NO for structured building; the Figma pattern breaks against version control

The evidence splits cleanly by sub-segment, and for anything resembling **serious or structured** building it breaks **against** the Figma real-time-co-editing pattern in favor of version control. Real-time co-*building* only clearly wins in the **casual, low-stakes, play-integrated sandbox**.

| Sub-segment | Want real-time co-*editing*? | Evidence |
|---|:--:|---|
| **(b) Pro / prosumer game & level devs** | **NO** (high conf) | Version control won. Unity killed Collaborate (EOL early 2022) for Plastic SCM / Unity Version Control — branching/merging + **Smart Locks that prevent concurrent edits** (the opposite of CRDT). Even Unreal Multi-User Editing, which *does* ship live co-editing, states it is **"not a replacement for source control… augment"** on Perforce/SVN/Git. |
| **(a) Casual / consumer sandbox** | **YES** (med conf) | Minecraft creative-mode: real-time collaborative building is a *core, valued engagement driver.* The one clean YES. |
| **(a) Structured UGC builders** | **NO** (high conf) | Epic's UEFN and Core use version-control / per-asset check-out; "collaboration" means multiplayer **play** as the output, not live co-authoring. |
| **(c) Virtual-tabletop GMs** | **SPLIT / unproven** (med conf) | TaleSpire ships & markets real-time collaborative 3D building (even multiple simultaneous GMs) — but that's *vendor positioning*, not demonstrated demand. Behavioral signal points the other way: **solo prep of 20–40 min/encounter**, and a healthy paid market for **pre-built drop-in maps** — i.e. solo prep + async delivery is "good enough" for most GMs. |

**Central tension resolved:** the Figma-multiplayer pattern is *technically viable and shipped* in this space, but it consistently sits **alongside or beneath** version control for structured building, and **only clearly wins in the casual sandbox.** It transfers to casual co-creation; it breaks against the VCS pattern for professional/prosumer level building; it is unproven (positioning-only) for VTT authoring.

## The honest data problem

**This split verdict rests on thin *demand* data.** The strong conclusions are about what tools *ship* and how they *position* collaboration (well-sourced from primary engine/product docs). **Direct willingness-to-pay or adoption evidence for real-time collaborative *authoring* was not found in either direction** — and the *only* WTP evidence that surfaced points the *opposite* way (a paid market for pre-built solo-prep maps; single Patreon-quality source). Specifically:

- The **Minecraft YES** rests on a single (good, peer-reviewed) study whose "social connections" construct **bundles collaborative building with collaborative play/camaraderie** — it doesn't cleanly isolate demand for *authoring*, and Minecraft→structured-browser-3D-editor generalization is unestablished.
- The **TaleSpire evidence is vendor positioning** (Steam page + FAQ), not revealed preference.
- **Roblox Team Create is a genuine gap** — multiple claims, *both* pro-adoption and anti-scaling/data-loss, were **refuted** (0-3). Do not cite Team Create adoption in either direction; the evidence isn't there.

## What this means, read with the competitive pass

The two 2026-07-07 passes converge and are decisive together:

- **Supply:** collaboration is **commoditized** — PlayCanvas, Spline, and Tabula Sono all ship real-time browser 3D co-editing ([competitive landscape](2026-07-07-competitive-landscape.md)).
- **Demand:** collaboration is **not strongly wanted** for structured building — VCS wins for pros, solo prep is good-enough for most GMs, and co-building clearly wins only in the casual Minecraft sandbox (this doc).

**Conclusion: real-time collaborative editing is not a viable moat — on either axis.** It is neither novel nor strongly demanded for the structured authoring WorldFoundry's editor does. This is the clearest signal yet that **the moat is the engine** (fixed-point / tiny / everywhere / retro-export), exactly as the [sim-env strategy](2026-07-05-worldfoundry-default-sim-environment.md) argued — *not* the collaborative editor.

## Implications

- **Stop positioning collaboration as the wedge.** "Figma for 3D worlds" is weak: commoditized on supply, thin on demand. Reframe around the engine + export target.
- **If collaboration is kept, aim it where it actually wins:** the **casual, social, build-together-for-fun sandbox** (Minecraft's lane) and collaborative **play** (VTT tables) — *not* professional structured authoring, where VCS is the revealed preference.
- **The VTT wedge's collaboration premise is weaker than assumed.** Most GMs prep *solo*; the collaborative part of tabletop is *play*, not *building*. So the [VTT plan](../plans/2026-07-07-vtt-wedge.md) should lean on **browser + zero-install + retro + buy-once**, and treat collaborative *building* as a casual/social nice-to-have, not the core reason to buy. Async "grab a pre-built map" is the revealed behavior to serve.
- **Don't over-engineer CRDT authoring.** If the demand is casual co-build + collaborative play + async map sharing, the heavy real-time-multi-writer-authoring investment may be aimed at a use case few structured builders want. Validate before deepening it.

## Open questions

1. **Does the casual Minecraft YES generalize** beyond the voxel sandbox to a *structured* browser 3D editor, or is it tied to Minecraft's specific play-integrated, low-stakes context? (The crux — and unestablished.)
2. **Roblox Team Create adoption/value** — a real gap; direct evidence was refuted in both directions.
3. **Any WTP/retention/conversion for real-time collaborative *authoring* specifically** — none surfaced; the only WTP evidence found was for the opposite (pre-built solo-prep maps).
4. **For VTT GMs, would frictionless live co-authoring convert** from a marketed feature into demonstrated preference, or is solo prep a stable revealed preference? A price test is the only way to know.

## Sources

Primary: [Unity — Collaborate → Plastic SCM](https://unity.com/blog/engine-platform/upgrading-from-collaborate-to-unity-plastic-scm), [Unity Version Control](https://unity.com/features/version-control), [Rojo (Roblox Git workflow)](https://rojo.space/docs/v7/), [Unreal Multi-User Editing overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/multi-user-editing-overview-for-unreal-engine), TaleSpire (Steam + FAQ), a peer-reviewed Minecraft collaborative-building study.
Weak/flagged: Moonlight Maps (Patreon — pre-built-map WTP, single source); Roblox Team Create claims (multiple refuted — treat as unresolved).
