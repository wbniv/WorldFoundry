# Investigation: ranking the 100 monetization ideas — method + full table

**Date:** 2026-07-07
**Status:** Companion/appendix to [2026-07-05-wf-edit-monetization.md](2026-07-05-wf-edit-monetization.md). Documents how the 100 ideas were ranked by likelihood, and lists the full ranking. The summary tables and quadrants in the monetization doc are all derived from this.

> **Read this first — what these numbers are and are not.** The "likelihood" values here are **my subjective estimates**, not market-measured probabilities. They are Fermi-grade: any single figure is soft by ±10–15 points, and the dollar ceilings are ±10× (per the monetization doc's §2). **Trust the tiers, not the exact positions** — "top-20 vs bottom-20" is defensible; "#7 vs #12" is noise. The ranking is a *structured opinion*, transparent enough to argue with, not a measurement.

## 1. What is being ranked, and by what

Every one of the 100 ideas (10 industries × 10 ideas) in the monetization doc, scored on one metric:

> **Likelihood** = the rough probability the idea reaches **at least the low end of its stated revenue estimate** if pursued as a focused effort by a 1–3 person team.

Two deliberate choices in that definition:

- **Not expected value.** Ranking by likelihood × dollars would put the $100M-ceiling lottery tickets (the "Retro Roblox" UGC platform) near the top purely on ceiling. The question is "*most likely to generate revenue*," so probability leads and size is shown separately (the `$ ceiling` column, and the monetization doc's §3 quadrant).
- **"Meaningful" revenue, so trivial-but-easy ideas are capped.** A $75k gift-voucher idea is *easy*, but its odds of *meaningful* revenue are middling because "meaningful" implies non-trivial scale — so it lands mid-pack (~#37), not top, despite low friction.

## 2. What drove each estimate (the anchors)

Each idea's likelihood was set from four inputs, in rough priority order:

1. **Validation results** (the strongest signal — from the [2026-07-05 validation](2026-07-05-wf-edit-market-validation.md) and [2026-07-07 A3 previz](2026-07-07-a3-previz-validation.md) passes):
   - **VTT (B3) confirmed** as the wedge → boosted.
   - **AEC (A2) and film previz (A3) both no-go** (a collaborative-3D incumbent already fills the slot) → floored at ~0.16–0.30.
   - **Education (B2) demoted** to self-serve → mid.
   - **Defense (A4)** SBIR-slow, **industrial (A5)** enterprise-slow → low-mid.
2. **Build friction** — sell-it-today (services, prosumer) beats needs-a-build (VTT client, platform, hosted SaaS), which beats needs-a-big-platform (UGC).
3. **Buyer type** — self-serve consumer/prosumer (card, no procurement) beats enterprise sales (procurement, long cycles, incumbent competition).
4. **Magnitude realism** — power-law / platform ceilings are penalized: a huge ceiling is *evidence of a hard, hits-driven build*, not of good odds.

The resulting **starting anchor per category** (individual ideas were then nudged ± around it for their specific friction/buyer/magnitude):

| Category | Anchor | Why |
|---|:--:|---|
| B5 Team-building & events | ~0.63 | Services, sellable today, zero build |
| B1 Indie/retro gamedev | ~0.60 | Product already *is* their tool; prosumer, fast |
| B3 Tabletop / VTT | ~0.57 | Validated demand, but needs the VTT build |
| B4 Creators & communities | ~0.50 | Consumer, but attention-dependent |
| B2 Education | ~0.48 | Self-serve works; district procurement drags |
| A1 Games & interactive | ~0.43 | Native fit, but competitive / platform-heavy |
| A5 Industrial twins | ~0.35 | Enterprise sales, slow, format work |
| A4 Defense & sim | ~0.31 | SBIR-gated, long cycles |
| A2 AEC + real estate | ~0.22 | **No-go** — incumbent-filled |
| A3 Film/TV previz | ~0.21 | **No-go** — incumbent-filled (free Unreal) |

## 3. How the ranking was produced (reproducibility)

- Each idea got a single likelihood value (the `Likelihood` column below *is* the full record — nothing hidden).
- **Sort:** descending by likelihood; ties broken by `$ ceiling` (higher first), then by idea code — deterministic and stable, so the same inputs always give the same order.
- No weighting, no composite score, no expected-value math. One number per idea, sorted. That's the whole model — its honesty is that you can see and dispute every input.

## 4. The full ranking (all 100, by likelihood)

<!-- generated: idea, category, likelihood, $ ceiling -->

| # | Idea | Category | Likelihood | $ ceiling |
|--:|---|---|:--:|--:|
| 1 | B5.1 Facilitated workshops | Team-building & events | ~85% | $300k |
| 2 | B1.1 Pro subscription | Indie/retro gamedev | ~80% | $500k |
| 3 | B1.2 Lifetime license (itch.io) | Indie/retro gamedev | ~78% | $200k |
| 4 | B3.1 GM subscription (3D maps) | Tabletop / VTT | ~70% | $1M |
| 5 | B1.3 Team rooms | Indie/retro gamedev | ~70% | $300k |
| 6 | B5.2 Self-serve event kits | Team-building & events | ~70% | $200k |
| 7 | B5.3 Seasonal themed events | Team-building & events | ~66% | $200k |
| 8 | B5.6 White-label for agencies | Team-building & events | ~64% | $250k |
| 9 | B5.4 Onboarding icebreakers | Team-building & events | ~62% | $150k |
| 10 | B3.2 Map & asset marketplace | Tabletop / VTT | ~60% | $500k |
| 11 | B4.1 Streamer mode | Creators & communities | ~60% | $500k |
| 12 | B3.3 Campaign hosting | Tabletop / VTT | ~60% | $400k |
| 13 | B5.7 Recurring guild subscriptions | Team-building & events | ~60% | $150k |
| 14 | B5.9 Offsite/hackathon add-ons | Team-building & events | ~60% | $100k |
| 15 | B3.7 Kickstarter themed edition | Tabletop / VTT | ~58% | $300k |
| 16 | B5.5 Escape-room puzzles | Team-building & events | ~58% | $250k |
| 17 | B1.8 Commercial-shipping license | Indie/retro gamedev | ~58% | $150k |
| 18 | B2.3 Camp/after-school licensing | Education | ~56% | $500k |
| 19 | B4.4 Community world servers | Creators & communities | ~56% | $400k |
| 20 | B3.4 Roll20/Foundry export plugin | Tabletop / VTT | ~56% | $200k |
| 21 | B5.8 Conference/booth experiences | Team-building & events | ~56% | $150k |
| 22 | B1.4 Hosted game jams | Indie/retro gamedev | ~56% | $100k |
| 23 | A1.1 Hosted collab-editor SaaS | Games & interactive | ~55% | $2M |
| 24 | B2.1 Classroom site license | Education | ~54% | $1M |
| 25 | B3.5 Pro-GM toolkit | Tabletop / VTT | ~54% | $300k |
| 26 | B4.3 Timelapse & replay export | Creators & communities | ~54% | $200k |
| 27 | B1.5 Starter/template packs | Indie/retro gamedev | ~54% | $100k |
| 28 | B1.7 Paid community + workshops | Indie/retro gamedev | ~54% | $80k |
| 29 | B1.9 Retro-console export add-on | Indie/retro gamedev | ~52% | $150k |
| 30 | B3.10 Actual-play streamer kit | Tabletop / VTT | ~52% | $150k |
| 31 | B2.2 Curriculum packs | Education | ~50% | $300k |
| 32 | B4.2 Speedbuild competitions | Creators & communities | ~50% | $300k |
| 33 | B2.4 Teacher PD & certification | Education | ~50% | $200k |
| 34 | B3.9 Mini-STL export | Tabletop / VTT | ~50% | $150k |
| 35 | B3.8 Convention/one-shot mode | Tabletop / VTT | ~50% | $100k |
| 36 | B1.6 Sponsorware (OSS core) | Indie/retro gamedev | ~50% | $80k |
| 37 | B5.10 Gift vouchers | Team-building & events | ~50% | $75k |
| 38 | B3.6 Publisher partnerships | Tabletop / VTT | ~48% | $500k |
| 39 | B4.7 Sponsored build events | Creators & communities | ~48% | $300k |
| 40 | B2.9 Homeschool co-op bundles | Education | ~48% | $150k |
| 41 | B4.6 Niche-community meetups | Creators & communities | ~48% | $150k |
| 42 | B4.9 Creator affiliate (indirect) | Creators & communities | ~48% | $60k |
| 43 | A1.6 Co-development review rooms | Games & interactive | ~46% | $3M |
| 44 | A1.10 AI level-design copilot | Games & interactive | ~46% | $1M |
| 45 | B2.5 University lab licenses | Education | ~46% | $300k |
| 46 | B4.5 Commission marketplace | Creators & communities | ~46% | $200k |
| 47 | B2.6 Student portfolio hosting | Education | ~46% | $150k |
| 48 | B4.10 Clip-to-level contests | Creators & communities | ~46% | $150k |
| 49 | A1.4 Live-ops levels for F2P | Games & interactive | ~44% | $5M |
| 50 | A1.8 Level & asset marketplace | Games & interactive | ~44% | $2M |
| 51 | B2.10 Grant-funded STEM programs | Education | ~44% | $300k |
| 52 | B4.8 Tip-driven public builds | Creators & communities | ~44% | $100k |
| 53 | B1.10 Merch & boxed edition | Indie/retro gamedev | ~44% | $75k |
| 54 | A1.3 White-label collab SDK | Games & interactive | ~42% | $2M |
| 55 | A1.7 Live playtest sessions | Games & interactive | ~42% | $1M |
| 56 | B2.8 LMS integration add-on | Education | ~42% | $200k |
| 57 | B2.7 Sponsored competitions | Education | ~42% | $150k |
| 58 | A4.1 SBIR scenario-authoring | Defense & sim | ~40% | $2M |
| 59 | A5.4 Facility onboarding tours | Industrial twins | ~40% | $2M |
| 60 | A1.5 Paid game-jam hosting | Games & interactive | ~40% | $1M |
| 61 | A1.9 Retro toolchain licensing | Games & interactive | ~40% | $750k |
| 62 | A5.1 Factory/warehouse planning | Industrial twins | ~38% | $10M |
| 63 | A5.2 Safety-training authoring | Industrial twins | ~38% | $5M |
| 64 | A5.10 White-label twin viewer | Industrial twins | ~36% | $3M |
| 65 | A5.3 Remote-expert annotation | Industrial twins | ~36% | $3M |
| 66 | A5.5 Retail planogram collab | Industrial twins | ~34% | $5M |
| 67 | A4.3 Emergency-mgmt tabletops | Defense & sim | ~34% | $3M |
| 68 | A5.8 Ergonomics/process review | Industrial twins | ~34% | $2M |
| 69 | A5.9 Evacuation drill rehearsal | Industrial twins | ~34% | $2M |
| 70 | A4.10 Subcontract to primes | Defense & sim | ~32% | $5M |
| 71 | A4.2 Mission-rehearsal sandbox | Defense & sim | ~30% | $5M |
| 72 | A4.4 Law-enforcement scenarios | Defense & sim | ~30% | $3M |
| 73 | A4.5 Venue & campus security | Defense & sim | ~30% | $3M |
| 74 | A5.6 Outage/turnaround planning | Industrial twins | ~30% | $3M |
| 75 | A5.7 Mine & field-site sandbox | Industrial twins | ~30% | $3M |
| 76 | A2.6 Interior-design studio (SMB) | AEC + real estate | ~30% | $2M |
| 77 | A4.9 Wargaming platform | Defense & sim | ~30% | $2M |
| 78 | A1.2 "Retro Roblox" UGC platform | Games & interactive | ~28% | $100M |
| 79 | A4.8 Critical-infra security review | Defense & sim | ~28% | $3M |
| 80 | A4.7 Disaster-response (NGO/UN) | Defense & sim | ~28% | $500k |
| 81 | A3.6 Ad-agency storyboard rooms | Film/TV previz | ~26% | $3M |
| 82 | A4.6 Base/installation planning | Defense & sim | ~26% | $1M |
| 83 | A2.1 Design-review rooms | AEC + real estate | ~24% | $10M |
| 84 | A2.4 New-build sales configurator | AEC + real estate | ~24% | $5M |
| 85 | A3.1 Virtual location scouting | Film/TV previz | ~24% | $5M |
| 86 | A2.2 Client walkthroughs + sign-off | AEC + real estate | ~22% | $5M |
| 87 | A3.2 Previz-as-a-service seats | Film/TV previz | ~22% | $3M |
| 88 | A3.3 Camera-blocking planner | Film/TV previz | ~22% | $2M |
| 89 | A3.7 Concert & stage-show design | Film/TV previz | ~22% | $2M |
| 90 | A2.3 Punch-list annotation | AEC + real estate | ~20% | $5M |
| 91 | A2.8 Facilities digital-twin lite | AEC + real estate | ~20% | $5M |
| 92 | A2.9 Insurance & inspection | AEC + real estate | ~20% | $5M |
| 93 | A2.10 Site-safety induction scenes | AEC + real estate | ~20% | $3M |
| 94 | A2.7 Modular/prefab configurator | AEC + real estate | ~20% | $3M |
| 95 | A3.4 Set-design sign-off | Film/TV previz | ~20% | $3M |
| 96 | A3.5 Episodic set-continuity twin | Film/TV previz | ~20% | $3M |
| 97 | A3.8 Theme-park previz | Film/TV previz | ~20% | $3M |
| 98 | A3.10 Digital backlot marketplace | Film/TV previz | ~18% | $1M |
| 99 | A3.9 Interactive scene assembly | Film/TV previz | ~18% | $500k |
| 100 | A2.5 Public-consultation portals | AEC + real estate | ~16% | $3M |

## 5. What the ranking shows

- **A near-total B-track / A-track split.** All **20 of the top-20** ideas are B-track; all **30 of the bottom-30** are A-track. Median rank: B-track **26.5**, A-track **75.5**. The consumer/prosumer/long-tail "easiest" industries dominate likelihood; the big-ceiling enterprise verticals sink.
- **Only one A-vertical idea cracks the top half:** A1.1 hosted collab-editor SaaS at **#23** — and A1 (games) is the *native fit* (the product already is a game level editor), not a repositioning. Every other A-vertical idea sits #43 or lower.
- **The bottom is the two validated no-go verticals.** 18 of the bottom 20 are AEC (A2) or film previz (A3) — exactly where research found a collaborative-3D incumbent already owns the slot. The single lowest idea is A2.5 (public-consultation portals, ~16%).
- **Biggest ≠ likeliest, starkly.** "Retro Roblox" (A1.2), the highest ceiling in the whole doc at $100M+, ranks **#78** — the clearest illustration that ceiling and odds are near-inverted for the platform bets.
- **Within-B-track order is noisy.** Ranks ~6–40 are a dense band of B-track service/prosumer ideas at 0.50–0.66 that are genuinely hard to separate — read that region as one tier, not a precise order.

## 6. Limitations & when to update

- **Subjective.** These are my judgments, anchored to the research but not measured. A landing-page price test or real customer conversations would replace them with evidence — and *should*, before any figure here drives a roadmap decision.
- **The A/V finding may nudge the collab-dependent ideas.** The [2026-07-07 A/V research](2026-07-07-av-and-collab-validation.md) (built-in voice/video is *not* a differentiator; real-time *simultaneous collaboration* is) doesn't change the B-vs-A split, but it sharpens *why* the VTT/collab ideas rank where they do — pursue them for the multiplayer editing, not the bundled A/V.
- **Ties are arbitrary within a likelihood value.** The tiebreak (ceiling, then code) is deterministic but not meaningful — don't read significance into the order of two ideas sharing a likelihood.
- **To regenerate:** update the per-idea likelihoods (e.g. after a price test), re-sort descending. The monetization doc's TL;DR table, the "category flagships" table, and the do-first quadrant all derive from this ordering and should be regenerated with it.
