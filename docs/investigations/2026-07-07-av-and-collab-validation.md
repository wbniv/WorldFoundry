# Investigation: built-in A/V, remote co-editing, and Omniverse — validation

**Date:** 2026-07-07
**Status:** Deep-research output (verified, 104 agents). Closes the three open questions the [A3 previz](2026-07-07-a3-previz-validation.md) and earlier [validation](2026-07-05-wf-edit-market-validation.md) passes left dangling. The most consequential is Q3 — it tests the single assumption under WorldFoundry's whole pitch.

## The one distinction that reframes everything

**Simultaneous real-time collaboration and built-in A/V are two different things, and only one is a differentiator.** The research conflated-then-separated them, and the separation is the headline:

- **Simultaneous multi-user editing** (many people changing one shared document/scene live — Figma, Google Docs, SubEthaEdit, Spline) *is* the category-defining capability. Figma launched multiplayer in 2016 with **zero built-in A/V** and won on exactly this.
- **Built-in voice/video/chat** is a **neutralized non-factor** — bring-your-own-Zoom/Discord replaces it in every segment tested.

So WorldFoundry's real moat is the **CRDT simultaneous-editing substrate**, not the bundled WebRTC A/V. Lead with the first; treat the second as table-stakes convenience, not the pitch.

## The three verdicts

1. **Q3 — Built-in A/V is NOT a differentiator (high confidence).** Category-definers omit it (Figma coordinates via live cursors/selections/presence, not voice); products that bundled A/V as their core mechanic (Gather, Teamflow, Kumospace) drove trial but not retention and the "virtual office" category *contracted*; and even vendors that ship A/V defer to Discord where users actually socialize (Roll20). Across consumer and enterprise, bring-your-own-Zoom/Discord neutralizes it. **Honest causation caveat:** the bundled-A/V products failed *substantially* because of return-to-office + the metaverse/virtual-office cooldown, **not solely** because bundling A/V is bad — the evidence supports *"bundled A/V doesn't create stickiness and BYO-Discord neutralizes it,"* not *"bundling A/V causes failure."* No direct willingness-to-pay data surfaced in either direction; the verdict rests on strong *indirect* signals.

2. **Q2 — Remote real-time 3D co-editing is a real, monetizable pain, but not where we ruled in (medium confidence).** Top investors funded purpose-built tools that landed paying customers — Gravity Sketch ($33M Series A), Spline ($15M, 2023), Evercast (~$8.7M rev, weak algorithmic estimate). But it's **modest mid-scale**, and demand concentrates in **product/industrial design and creative review** (Adidas, VW, Ford) — *not* film or AEC. **The competitive sting:** **[Spline](https://spline.design/) already occupies WorldFoundry's exact positioning minus A/V** — a browser-based, no-code 3D tool with full Figma-style real-time multiplayer co-editing (live multi-cursor). The browser-collaborative-3D slot is *not* empty; it's held, in the design corner.

3. **Q1 — Omniverse is a second collaborative-3D incumbent, but industrial (high confidence).** NVIDIA Nucleus provides live cross-app multi-user co-authoring functionally equivalent to Unreal's Multi-User Editing — but as of 2025–26 NVIDIA rebranded Omniverse *"The Operating System for the Industrial AI Era,"* names only manufacturing/robotics adopters (Foxconn, Caterpillar, BMW, Amazon Robotics, Siemens, TSMC), **deprecated its standalone creator/authoring apps** (Create / USD Composer, Oct 2025), and made the software **free for production** (May 2026, dropping the prior $4,500/GPU/yr). It's a **heavy local RTX/data-center-GPU** workload, **not a browser tool.** Net: it **reinforces the no-go in industrial/AEC**, is largely **vacating film/VP**, and **never occupies the lightweight-browser slot.** (Caveat: retains some film/VFX users — ILM asset-search, Weta — so it's industrial-*concentrated*, not film-*absent*.)

## What this means for WorldFoundry

- **Reposition the pitch off A/V and onto simultaneous editing.** Every doc that leans on "voice/video built-in" as an edge should demote it. The differentiator is *"Figma-style live multiplayer for 3D game worlds, in the browser."* A/V stays (it's cheap and expected) but is never the reason anyone buys.
- **The browser-collaborative-3D slot has an incumbent — in design (Spline), not games/worlds/VTT.** WorldFoundry's defensible ground is precisely where Spline isn't: **game levels, retro-engine export, virtual tabletops, simulation worlds, the long tail** — not product-design or web-3D, where Spline is funded and entrenched. This *narrows* the "vacant quadrant" thesis of the [sim-env strategy](2026-07-05-worldfoundry-default-sim-environment.md): browser + collaborative 3D is vacant in *simulation/games*, occupied in *design*.
- **A/V-dependent likelihoods don't move, but their rationale sharpens.** In the [ranking method](2026-07-07-monetization-ranking-method.md), the VTT/collab ideas rank where they do because of *multiplayer editing*, not bundled A/V — pursue them accordingly.
- **Two more incumbent-filled verticals confirmed.** Omniverse cements industrial/AEC as incumbent-owned (alongside the AEC no-go), and reinforces that WorldFoundry's edge is the long tail, not enterprise verticals.

## Refuted — do not cite

- ~~Figma markets a Zoom integration / treats the cursor as a voice substitute / uses a last-writer-wins model~~ (all 0-3) — the "Figma omits A/V and wins on presence" point stands, but not via these specific mechanisms.
- ~~Omniverse Enterprise is $4,500/GPU/yr today~~ (0-3) — superseded; software is now free for production (May 2026), enterprise *support* still costs.
- ~~Specific Omniverse RTX VRAM tiers (RTX 3060/4080/4090)~~ (1-2) and ~~"too compute-heavy for any browser"~~ (0-3) — only the general "heavy local GPU, not a browser tool" claim survived.

## Open questions (still)

1. **WorldFoundry's own target segment.** The real collaborative-3D demand is in product/industrial design — the segments already ruled out are film/AEC — and the game-worlds/VTT segment WorldFoundry aims at is *assumed*, not yet demand-verified. This is now the single most important unknown.
2. **Direct A/V willingness-to-pay.** No pricing/WTP data either way; the (strong) Q3 verdict is all indirect. A price test could confirm it cheaply.
3. **Spline's defensibility.** It's funded and full-featured; how a new browser-3D entrant differentiates against it (answer: not in design — in games/worlds) needs its own look if that corner is ever targeted.
4. **Quantified VTT behavior.** "Tables use Discord not the VTT's built-in A/V" is qualitative (Roll20 defers to Discord); no hard % of tables was found.

## Sources

Primary: [NVIDIA newsroom (industrial AI / manufacturing)](https://nvidianews.nvidia.com/news/nvidia-us-manufacturing-robotics-physical-ai), [Omniverse Nucleus docs](https://docs.omniverse.nvidia.com/nucleus/latest/features.html), NVIDIA Developer Forums (licensing change, Jul 2026), [Spline](https://spline.design/), Figma multiplayer engineering posts, Roll20/Discord docs.
Secondary: [StorageReview (Omniverse free)](https://www.storagereview.com/news/nvidia-quietly-makes-omniverse-free-for-production-use), Introl (Omniverse industrial), Gravity Sketch / Spline funding coverage, getLatka (Evercast revenue — flagged weak). Report-mill/paywalled items flagged inline in the run.
