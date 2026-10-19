# Investigation: A3 film previz — go/no-go validation

**Date:** 2026-07-07
**Status:** Deep-research output (verified). Focused single-industry validation of **A3 (film, TV & media production — previsualization / virtual production)** as WorldFoundry's "later big bet," the one Part-A industry the [2026-07-05 validation pass](2026-07-05-wf-edit-market-validation.md) left un-researched. Companion to that doc and to [the monetization analysis](2026-07-05-wf-edit-monetization.md).
**Method:** 6 search angles → 27 sources → 117 falsifiable claims → top 25 adversarially verified (3 refute-votes each; 2/3 kills) → **20 confirmed, 5 refuted, 0 unverified.** 110 agents.

**Terminology:** previz — *previsualization*, the rough 3D blocking of shots/scenes before shooting. Virtual production (VP) — real-time 3D on set, esp. LED-volume shooting. "Previz house" — a studio (The Third Floor, Halon, NVIZ, DNEG) that produces previz for films. Multi-User Editing — Unreal Engine's built-in feature for many operators co-editing one live 3D scene.

---

## Verdict: NO-GO — and it's the *same* failure mode as AEC

**A3 is a no-go as the later big bet**, and the four lenses converge as cleanly as they did against AEC. The decisive fact: **WorldFoundry's core capability — collaborative multi-user 3D editing — is already shipped, for free, by the entrenched incumbent, and explicitly built for this exact use.**

Both of the two "biggest-absolute-dollar" verticals we tested now return no-go **for one structural reason**: a collaborative-3D incumbent already occupies the slot. In AEC it was Revizto + Resolve; in previz it's **Unreal Engine's native Multi-User Editing**. That is the meta-finding worth carrying forward — see [§ implications](#implications).

Confidence: medium (synthesis over high-confidence findings; the market-size *numbers* are weak, but the verdict doesn't depend on them).

---

## Evidence by lens

### 1. Competitor economics — the price floor is $0 (confidence: high)

- **Unreal Engine is free for all non-games/previz/VP work by studios under ~$1M annual gross revenue, and $1,850/seat/yr only above that.** The entire indie/small-studio tier WorldFoundry would target already runs the industry-standard tool at **zero cost**. ([Epic's licensing](https://www.unrealengine.com/license); [CG Channel](https://www.cgchannel.com/2024/03/new-pricing-for-unreal-engine-twinmotion-and-realitycapture/) states verbatim the fee "applies to… previs and virtual production work"; Epic's April-2024 pricing blog + 7 outlets. 3-0.) *Caveat:* the $1,850 figure came via search snippets (Epic's `/license` 403s); corroborated and current to mid-2026. A separate claim that Unreal charges **no royalty on rendered film output** was **refuted** (1-2, unconfirmed) — treat only the seat price as established.
- **The third-party indie tools that exist charge prosumer prices and mostly lack real-time collaboration:** Previs Pro ($0 / $39.99·mo / $119.99·yr / $359.99 lifetime; native Apple app, no multiplayer/voice — only async web review links); Cine Tracer ($89.99 one-time, single-player, no glTF/USD export); DragonFly by Glassbox ($129/mo → $1,350 perpetual per seat); Cuebric AI backdrops ($15–120/mo). **None occupy the browser-collaborative slot, and indie willingness-to-pay is demonstrably low.** (Primary vendor/storefront pages. 3-0 on five of six claims.)

### 2. The incumbent already fills the slot (confidence: high)

- **Unreal ships built-in Multi-User Editing that lets "potentially dozens of operators work together on set," "designed and tested in large-scale virtual film & TV production teams"** ([Epic's own UE docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/multi-user-editing-in-unreal-engine)). Unreal has been the de facto real-time previz engine across Halon, NVIZ, DNEG, and The Third Floor since ~2017–2020 ([VFX Voice](https://vfxvoice.com/how-previs-has-gone-real-time/)). WorldFoundry's "multiplayer 3D editing" is not a new capability here — it's a free incumbent feature. (3-0 across four claims.)
- **The apparent gap closes on inspection.** The same Epic docs warn *"Do not expect to share sessions over an open Internet connection"* — Multi-User Editing is **LAN/VPN-centric.** That *looks* like an opening for browser-native remote editing, but it isn't a real one **for this buyer**: studios and previz houses run VPNs, Perforce, and managed networks as baseline IT, so "needs a VPN" is no barrier to them. Zero-install/zero-VPN collaboration has teeth only where users won't configure anything — the consumer/long-tail segments, i.e. precisely *not* previz. (The one thin residual — *cross-company* remote sessions are genuinely harder to VPN than intra-org ones — is small, already served by screen-share tools like Evercast, and not a felt pain a new vendor gets paid to remove.) The wedge does not survive against a free incumbent that owns the on-set/LAN case.

### 3. Buyer behavior — a closed shop at the app layer (confidence: high)

- **Leading previz houses build their own director-facing tools in-house on Unreal/Maya rather than buying third-party apps:** NVIZ "ARENA," The Third Floor "Chimera"/"Cyclops" (used on The Marvels/Ahsoka/House of the Dragon), Halon and DNEG custom Unreal suites. Adversarial searches for major houses *buying* small third-party previz apps returned nothing — those tools target indies. ([VFX Voice](https://vfxvoice.com/taking-previs-tools-to-the-next-level/), studio sites. #17 = 3-0; the "closed-shop" framing #18 = 2-1, the split noting houses *do* license Unreal/Maya, just build the app layer themselves.) A small outside vendor selling into the big houses faces a build-in-house wall.

### 4. Failure post-mortem — a motivated indie tried this exact thing and couldn't (confidence: high)

- **Cine Tracer is the direct cautionary tale.** A solo developer publicly planned real-time multiplayer previz in 2018, launched in Early Access Sept 2018, **never shipped multiplayer, never left EA, and abandoned it** (Steam's platform banner: "last update… over 3 years ago"; reviews call it dead). The UE5 sequel also stalled. **Even a determined indie who wanted precisely WorldFoundry's differentiator could not deliver it.** ([Steam](https://store.steampowered.com/app/904960/Cine_Tracer/). 3-0.)

### Market size — no defensible TAM (confidence: medium)

There is **no reliable film-previz-specific TAM.** The broad VP market is ~$2.75–2.8B (2024/25), but only ~41% is software (rest is LED volumes, cameras, integration services), and the lone "previsualization software" figure ($1.49B 2025) is a report-mill number bundling Film & TV with Architecture, Gaming, Advertising, and Automotive — film is 1 of 6 buckets, so film-previz is materially smaller, and browser-collaborative previz smaller still. ([Grand View](https://www.grandviewresearch.com/industry-analysis/virtual-production-market), [Growth Market Reports](https://growthmarketreports.com/report/previsualization-software-market), [Market Research Future](https://www.marketresearchfuture.com/reports/virtual-production-market-33073). All syndicated report-mills; three *other* TAM numbers were refuted 0-3 — hence medium confidence in the figures, though not in the "no defensible TAM" conclusion.)

## Refuted — do not cite

1. ~~Unreal charges no royalty on rendered film/broadcast output~~ — refuted 1-2 (unconfirmed). Only the $1,850/seat price is established.
2. ~~VP market $2.10B → $8.76B at 33.1% CAGR (MarketsandMarkets)~~ — refuted 0-3.
3. ~~VP market is hardware-dominated~~ — refuted 0-3.
4. ~~IMARC $3.1B 2025 / 9.5% CAGR~~ — refuted 0-3.
5. ~~The Third Floor's Chimera already fills the "everyone-can-edit" slot internally~~ — refuted 0-3. The slot signal rests on Unreal's **native** Multi-User Editing, not any single house's tool.

## Open questions (coverage gaps — all requested, none resolved)

1. ~~NVIDIA Omniverse was never addressed~~ — **RESOLVED** ([2026-07-07 A/V+collab validation](2026-07-07-av-and-collab-validation.md)): Omniverse is a genuine second collaborative-3D incumbent (Nucleus live co-authoring), but it has repositioned to **industrial "physical AI"** (Foxconn, Caterpillar, BMW), deprecated its standalone creator apps, and is a heavy local-RTX-GPU (non-browser) workload — so it **reinforces the no-go in industrial/AEC while largely vacating film/VP**, and never occupies the lightweight-browser slot.
2. **Is remote co-editing a felt, paid-for pain?** Largely moot for the *enterprise* previz buyer — Unreal's LAN/VPN limitation is trivially cleared by studios' baseline IT (VPNs), so it isn't a real limitation for them. The browser/zero-VPN advantage is a consumer/long-tail lever, not an enterprise one; no demand-side evidence surfaced that any previz buyer would pay to remove the VPN step.
3. ~~Is built-in voice/video a differentiator?~~ — **RESOLVED** ([2026-07-07 A/V+collab validation](2026-07-07-av-and-collab-validation.md)): **no** — built-in A/V is a neutralized non-factor across segments (Figma wins without it; Roll20 ships it but tables use Discord). The genuine differentiator is *simultaneous real-time editing*, not the bundled A/V.
4. **Fidelity expectations** at the previz stage (does a fixed-point/WebGL engine's low-fi suffice?), and whether shared virtual location scouting is a real sized market — both unquantified.

## Implications

- **Update the sequencing.** The monetization doc's §4 named A3 the "default candidate for the later big bet, pending its own research pass." That pass is done: **A3 is no-go.** With A2 (AEC) also no-go, **both tested big-money verticals fail for the same reason** — a collaborative-3D incumbent already owns the slot (Revizto+Resolve; Unreal Multi-User Editing).
- **The pattern is the lesson, not just the two verdicts.** In any established, high-budget 3D vertical, expect an incumbent to already occupy "collaborative 3D." WorldFoundry's edge is *browser-native, zero-install, remote* collaboration — which matters most where the incumbents are weakest: **consumer/prosumer and long-tail segments** (the B-track: VTT, indie, education, creators), not the enterprise verticals where Unreal/Autodesk/Revizto are entrenched and free-or-cheap.
- **This strengthens, not weakens, the plan.** It concentrates the bet: the wedge (VTT) and the platform ambition (default *open* sim environment) are exactly the browser-native/long-tail plays the incumbents don't defend. The "later big bet" among the A-verticals is, for now, **none of the tested ones** — revisit only via primary discovery, and only where a remote/browser gap is a *proven* felt pain.
- **A sharper strategic rule, from why the "remote gap" wasn't real:** the value of browser-native / zero-install / zero-VPN **scales inversely with the buyer's IT sophistication** — worth a lot where users won't configure anything (consumers, indies, classrooms, ad-hoc tables), worth almost nothing where IT handles it (enterprise verticals with VPNs and admins). This is the same conclusion every vertical pass reaches, stated as a heuristic: don't lean on "browser-native" as an *enterprise* differentiator; it's a *long-tail* one. It also cautions against over-valuing the browser advantage in enterprise-flavored B-track deals.
- **The one A3 re-entry angle, and why even it's weak:** "remote, browser, zero-install collaborative *review/scouting* for distributed teams" is the only framing not already lost to free Unreal — but the teams that do previz are businesses with VPNs, so the friction it removes is small, and demand is unproven. Out of scope now.

## Sources

Primary: [unrealengine.com/license](https://www.unrealengine.com/license), [Epic UE Multi-User Editing docs](https://dev.epicgames.com/documentation/en-us/unreal-engine/multi-user-editing-in-unreal-engine), [previspro.com pricing](https://www.previspro.com/previs-pro-pricing), [Cine Tracer (Steam)](https://store.steampowered.com/app/904960/Cine_Tracer/), [DragonFly/Glassbox](https://glassboxtech.com/products/dragonfly/buy).
Secondary: [CG Channel (UE pricing)](https://www.cgchannel.com/2024/03/new-pricing-for-unreal-engine-twinmotion-and-realitycapture/), [VFX Voice — previz real-time](https://vfxvoice.com/how-previs-has-gone-real-time/) & [previz tools](https://vfxvoice.com/taking-previs-tools-to-the-next-level/), [Grand View Research (VP market)](https://www.grandviewresearch.com/industry-analysis/virtual-production-market), Market Research Future, Growth Market Reports. Report-mill TAM figures flagged low-confidence; three refuted outright.
