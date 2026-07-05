# Investigation: monetizing wf_edit — the real-time collaborative 3D level editor

**Date:** 2026-07-05
**Status:** Brainstorm / market scan. All figures are Fermi estimates, not researched numbers — see §2 before quoting anything from this document.
**Product:** `engine/wf_edit` on `origin/2026-new-level` (not present on this local branch — see the reconcile item in root `TODO.md`).

---

## 1. What we're actually selling

Capability inventory, assembled from the branch history and file tree (notably `ac3680d2` "one-click .lev export shipped — web editor v1 feature-complete"). Caveat: assessed from commit messages and file listings, not hands-on testing.

- **Native level editor** — ImGui-based: gizmo manipulation, property panel over the OAD attribute system, level document + save, live engine bridge (`engine/wf_edit/`).
- **Runs in the browser** — wasm via Emscripten, WebGL/GLES3, no install. Boots with a preloaded level.
- **Real-time multiplayer editing** — CRDT document sync (Yrs/Yjs via yffi, cross-compiled to wasm), multi-peer join-and-receive seeding.
- **Presence + text chat** — collaborators panel, per-peer presence.
- **Voice + video** — WebRTC; native build has RTCP PLI fast keyframe recovery and per-peer decoders; receive-only mode (`WF_COLLAB_NO_CAM`).
- **One-click `.lev` export** into the engine pipeline; the engine itself runs on Linux, Android, Chromecast/Google TV, iOS (in progress), with Steam packaging planned.
- **Engine traits with commercial relevance** — fixed-point math and a small footprint (runs on very low-spec, legacy, and retro hardware), scriptable actors (Lua/Fennel/zForth/wasm, experimental neural-forth), Blender round-trip pipeline.

The honest one-liner: **"Figma-style multiplayer editing for 3D scenes — with voice, video, and chat built in — running in the browser."**

Two structural facts drive everything below:

1. **The reusable asset is the collaboration substrate** (CRDT doc + WebRTC A/V + wasm 3D viewport), not the WorldFoundry format. Today the editor edits `.lev`/OAD only. Every non-game industry in Part A requires a **general scene-format layer (glTF import/export at minimum, USD for film)** plus auth, hosted persistence, TURN/SFU relay infrastructure, and billing before the first dollar arrives. The Part B industries mostly do not.
2. **A/V has real marginal cost.** TURN relay bandwidth runs ~$0.05–0.40/GB depending on provider; sustained multi-party video caps gross margins at ~50–70%, below the 75–90% of classic SaaS. Pricing needs to meter or cap A/V minutes.

## 2. How to read the estimates

- Assumes a 1–3 person team building on the existing stack, bootstrapped or lightly funded.
- **"Maturity"** = plausible annual revenue 3–5 years in, *if that idea is pursued as the main bet and executed well*.
- **"First revenue"** = elapsed time from deciding to pursue the idea to the first paying customer.
- **Confidence is low.** Any individual number is ±10×. The *rankings* (which industries are bigger, which are faster) are far more defensible than the absolute figures.
- Market-size figures are ballpark, from general knowledge as of early 2026, and unverified. Validate the top 2–3 picks with a real research pass (customer interviews + competitive scan) before committing a roadmap to any of them.
- **Revenue ≠ profit.** Rough gross margins: pure software SaaS 75–90%; A/V-heavy usage 50–70% after relay bandwidth; facilitated services/workshops 30–60%. Profit at this team size ≈ gross margin × revenue − (mostly) salaries.

---

## Part A — Five industries with the largest absolute-dollar potential

Ranked by realistic ceiling *for this product*, not by raw industry size.

### A1. Games & interactive entertainment

**Why:** Native fit — zero repositioning. Consumer games spend is ~$185B/yr; tools/middleware is a $2–5B slice; and UGC platforms are the existence proof that *editors* can out-earn games (Roblox books ~$4B/yr selling what is, at core, a collaborative editor plus distribution). wf_edit is already a game level editor with multiplayer built in.
**Entry cost:** Lowest of any industry here — the product works today. Platform-shaped ideas additionally need hosting, moderation, and payments.
**Ceiling:** A seat-license tools business plateaus around $1–10M ARR; a UGC platform that hits is $100M+, but that outcome is hits-driven (lottery-shaped, not grind-shaped).

1. **Hosted collaborative level-editor SaaS for indie teams.** Per-seat subscription ($10–25/seat/mo) for private rooms, cloud saves, version history. Estimate: $200k–2M ARR at maturity; first revenue in 2–4 months.
2. **"Retro Roblox" UGC platform.** Players build, publish, and play retro-styled worlds in the browser; monetize via premium currency and a 70/30 creator marketplace. Estimate: $1M–100M+ (power-law outcome); 12–24 months to first marketplace revenue.
3. **White-label collab SDK.** License the CRDT + WebRTC + wasm-viewport substrate to other engine and tool vendors who want "multiplayer editing" without building it. Estimate: $50k–500k/yr per licensee, 2–5 licensees realistic → $100k–2M ARR; 6–12 months.
4. **Live-ops levels-as-a-service for F2P studios.** Studios ship weekly content; sell the collaborative pipeline (design → review-on-call → export) as an enterprise contract. Estimate: $100k–1M/yr per studio, a handful of logos → $500k–5M ARR; 9–18 months.
5. **Paid game-jam hosting.** Branded jams with built-in team formation, live collab, and sponsor placement. Estimate: $5k–50k per event, 10–30 events/yr → $100k–1M/yr; 3–6 months.
6. **Co-development review rooms.** Studios working with external art/level outsourcers review work-in-progress together on video instead of trading builds. Estimate: $99–499/mo per studio-vendor pair → $300k–3M ARR; 6–12 months.
7. **Live playtest sessions.** Developers watch players navigate a level, talk to them, and edit the level live between runs; usage-priced. Estimate: $100k–1M ARR; 4–8 months.
8. **Level & asset marketplace.** 15–30% take rate on community-made levels, tilesets, and prefabs, attached to the SaaS user base. Estimate: $50k–2M/yr scaling with the base; 6–12 months after the SaaS exists.
9. **Commercial retro/homebrew toolchain licensing.** License the editor + engine export to publishers doing PSX-era re-releases and licensed minigames on set-top/TV hardware (the Chromecast/Google TV port is the wedge; fixed-point is the moat). Estimate: $25k–250k per deal, a few deals/yr; 6–12 months.
10. **AI level-design copilot.** In-editor agent that drafts layouts, places actors, and wires scripting (the neural-forth and scripting hooks make this unusually plausible here); sold as a +$10–30/mo add-on. Estimate: $100k–1M ARR as an attach to the SaaS; 6–12 months.

### A2. Architecture, engineering & construction (AEC) + real estate

**Why:** Construction is a ~$10–13T/yr global industry with famously poor multi-party coordination; AEC software exceeds $10B/yr, and design-review/coordination tools (Revizto, Autodesk Construction Cloud, Resolve) already command $100s–1000s per seat per year. The daily workflow this industry runs on — several stakeholders on a call staring at a 3D model, one person driving — is exactly what wf_edit collapses: everyone in the model, voice/video native, decisions captured in place. A lightweight browser viewport is a *feature* here (site laptops, client iPads).
**Entry cost:** Medium-high. Needs IFC/glTF import, measurement + markup tools, SSO and SOC2 for firm-wide deals. The game-specific parts matter less than the viewport + collab core.
**Ceiling:** $10–50M ARR — comparable focused review tools have reached this.

1. **Design-review rooms.** Import the model, walk it together, annotate spatially, export a decision log tied to positions in the model. Estimate: $50–150/seat/mo → $1–10M ARR; first revenue 9–18 months (format work is the gate).
2. **Client-presentation walkthroughs with recorded sign-off.** The approval meeting happens inside the model and produces a video + annotation artifact for the project record. Estimate: $2–20k/yr per firm → $500k–5M ARR; 9–15 months.
3. **Punch-list / site-issue spatial annotation.** Field issues pinned in 3D, walked through remotely with subs on video. Estimate: $20–60/seat/mo → $500k–5M ARR; 12–18 months.
4. **New-build sales configurator.** Buyer + agent on video inside the unit; pick floors, finishes, furniture; export the selection sheet. Estimate: $10–50k per development project or per-seat → $500k–5M ARR; 9–15 months.
5. **Public-consultation portals for urban planning.** Councils publish a walkable proposal; residents leave spatial comments; planners hold live sessions. Estimate: $20–200k per contract, government sales → $500k–3M/yr; 12–24 months.
6. **Interior-design studio (SMB).** Designer and client co-edit a room live; prosumer pricing. Estimate: $29–99/mo → $200k–2M ARR; 6–12 months (lowest format bar in this industry).
7. **Modular/prefab configurator.** White-labeled per manufacturer: configure a building from their catalog, export a BOM + quote. Estimate: $50k–500k/yr per manufacturer → $500k–3M ARR; 9–18 months.
8. **Facilities digital-twin lite.** Building operators walk the as-built, annotate equipment, video-call the tech standing in front of it. Estimate: $5–50k/yr per portfolio → $500k–5M ARR; 12–24 months.
9. **Insurance & inspection walkthroughs.** Photogrammetry import; adjusters/inspectors produce annotated 3D records instead of photo sets. Estimate: per-claim or per-seat pricing → $500k–5M ARR; 12–24 months.
10. **Site-safety induction scenes.** Contractors walk new workers through the actual site's hazards before day one; sold per contractor/yr. Estimate: $10–100k/yr per contractor → $500k–3M ARR; 9–18 months.

### A3. Film, TV & media production (previz / virtual production)

**Why:** Media & entertainment is a ~$2.5–3T industry, and virtual-production tooling is a fast-growing $3–6B slice of it. Previsualization is inherently multi-party — director, DP, production designer, VFX supervisor, often on different continents — and today it mostly runs as one operator screen-sharing an Unreal session while everyone else talks over them. A browser previz room where *everyone can move things*, with A/V native, upgrades the early-stage workflow, and low-fidelity rendering is acceptable (even preferred) at that stage. Production budgets pay real money for schedule compression.
**Entry cost:** Medium. glTF/USD import, lens/FOV-accurate cameras, USD export for downstream handoff.
**Ceiling:** $5–30M ARR — smaller niche than AEC, but chunky per-production and per-studio deals.

1. **Virtual location scouting rooms.** Import photogrammetry/LiDAR scans; department heads walk the location together weeks before anyone flies. Estimate: $500–5k/mo per production → $1–5M ARR; 9–15 months.
2. **Previz-as-a-service seats.** Sell seats to previz houses as their delivery/review layer with clients. Estimate: $100–300/seat/mo → $500k–3M ARR; 9–15 months.
3. **Camera-blocking planner.** Lens-accurate shot design in the shared scene; exports shot lists and camera data. Estimate: $50–150/seat/mo → $300k–2M ARR; 9–12 months.
4. **Set-design sign-off with department layers.** Art, grip, lighting each own a layer; the sign-off meeting happens in the model. Estimate: $10–50k per production → $500k–3M ARR; 9–15 months.
5. **Episodic set-continuity twin.** Keep standing sets consistent across a season's episodes and reshoots; per-show license. Estimate: $25–100k per show → $500k–3M ARR; 12–18 months.
6. **Ad-agency 3D storyboard rooms.** Agencies block out a spot in 3D with the client approving on video; fast cycles, many small projects. Estimate: $10–50k/yr per agency → $500k–3M ARR; 6–12 months.
7. **Concert & stage-show design.** Tour set + lighting previz with the artist and production manager remote. Estimate: $5–50k per tour → $300k–2M ARR; 9–12 months.
8. **Theme-park & attraction previz.** Design firms walk clients through attractions pre-build; long projects, high budgets. Estimate: $50–250k per project engagement → $500k–3M/yr; 12–18 months.
9. **Interactive-content scene assembly.** Choose-your-path and interactive-streaming producers assemble branching 3D scenes collaboratively. Estimate: $50k–500k ARR (nascent market); 12–24 months.
10. **Digital backlot marketplace.** License reusable scanned sets/environments with a take rate, attached to the scouting product. Estimate: $100k–1M/yr at maturity; 12–24 months after the scouting product exists.

### A4. Defense, public safety & simulation training

**Why:** Global defense spending exceeds $2.5T/yr and is rising; US DoD modeling/simulation/training programs alone run ~$10B+/yr. The chronic, openly acknowledged bottleneck in training sims is **scenario authoring** — instructors can't build content without contractor cycles. A collaborative scenario editor that instructors drive themselves, with comms built in, is a credible pitch — and this stack's quirks are advantages here: small footprint, fixed-point (legacy/secure hardware), and a fully **self-hostable** collab stack (CRDT + WebRTC with no cloud dependency) for closed networks.
**Entry cost:** Highest. ITAR handling, ATO/accreditation, on-prem deployment, eventually DIS/HLA interop, and usually a prime/partner relationship. The realistic wedge is SBIR/STTR (Phase I ≈ $100–250k, Phase II ≈ $1–2M) — grant money that subsidizes the roadmap.
**Ceiling:** Program-of-record money is $10M+/yr but 3–5+ years out; the SBIR path is $1–3M across years 1–3.

1. **SBIR-funded scenario-authoring tool for training ranges.** The canonical entry: pitch instructor-driven authoring at a specific range/schoolhouse. Estimate: $100–250k Phase I, $1–2M Phase II; first (grant) revenue 6–12 months.
2. **Mission-rehearsal sandbox.** Import terrain, brief the team on-call inside the model, walk the plan. Estimate: $50–250k/yr per unit-level license → $1–5M/yr; 18–36 months.
3. **Emergency-management tabletop exercises.** Counties and states run disaster tabletops in a shared 3D scene; FEMA-adjacent grant funding buys it. Estimate: $10–50k/agency/yr → $500k–3M/yr; 9–18 months.
4. **Law-enforcement scenario builder.** Departments author de-escalation and response scenarios for their own facilities. Estimate: $10–50k/dept/yr → $500k–3M/yr; 12–24 months.
5. **Venue & campus security planning twins.** Stadiums, campuses, and event operators plan coverage and evacuation collaboratively. Estimate: $10–100k/venue/yr → $500k–3M/yr; 12–18 months.
6. **Base & installation facility planning.** Reuses the AEC feature set inside the compliance envelope. Estimate: $100k–1M per contract; 18–36 months.
7. **Disaster-response coordination sandbox for NGOs/UN agencies.** Shared operational picture + comms for response planning; grant/tender funded. Estimate: $50–500k per program; 12–24 months.
8. **Critical-infrastructure security review.** Utilities walk substations/plants with regulators and consultants without site visits. Estimate: $25–250k/yr per operator → $500k–3M/yr; 12–24 months.
9. **Wargaming platform for think tanks & staff colleges.** Turn-based/moderated wargames in a shared 3D theater with A/V. Estimate: $25–100k/yr per institution → $300k–2M/yr; 12–18 months.
10. **Subcontract licensing to primes.** Integrate the authoring/collab layer into CAE/Lockheed/Bohemia-ecosystem training products rather than selling direct. Estimate: $100k–1M/yr per integration → $500k–5M/yr; 18–36 months.

### A5. Enterprise training & industrial digital twins

**Why:** Corporate training is a ~$350–400B/yr market, and industrial digital-twin software is projected into the tens of billions by decade's end (projections vary widely). The concrete, recurring workflow underneath the buzzwords: every warehouse re-slot, factory line change, and plant outage involves a spatial plan argued over by a plant manager, an integrator, and a consultant — today via screen-share and PDFs. Enterprise contract sizes make the absolute dollars large even at modest logo counts.
**Entry cost:** Medium-high. CAD/point-cloud import, SSO/SOC2, and enough integration surface (export to the tools they already use) to survive procurement.
**Ceiling:** $5–30M ARR.

1. **Factory & warehouse layout planning rooms.** Plant teams and integrators co-edit the layout live; export the agreed plan. Estimate: $20–100k/yr per site portfolio → $1–10M ARR; 9–18 months.
2. **Safety-training scenario authoring.** EHS teams author walkable incident scenarios (lockout/tagout, confined space) for their actual facility. Estimate: $10–50k/yr per site → $500k–5M ARR; 9–15 months.
3. **Remote-expert maintenance annotation.** The expert joins on video and draws in 3D space anchored to the equipment. Estimate: $30–80/seat/mo → $500k–3M ARR; 9–15 months.
4. **Virtual facility onboarding tours.** New hires walk the plant, guided live or self-serve, before badge day. Estimate: $5–25k/yr per site → $300k–2M ARR; 6–12 months.
5. **Retail planogram & store-layout collab.** Chains re-set hundreds of stores seasonally; HQ and regional teams co-edit the 3D set. Estimate: $50–250k/yr per chain → $500k–5M ARR; 9–18 months.
6. **Outage & turnaround planning for energy plants.** Sequence crews and crane positions spatially for maintenance windows where a day costs millions. Estimate: $50–250k per outage engagement → $500k–3M/yr; 12–24 months.
7. **Mine & field-site planning sandbox.** Remote sites planned collaboratively with terrain imports; poor-connectivity-friendly (small footprint helps). Estimate: $50–250k/yr per operator → $500k–3M ARR; 12–24 months.
8. **Ergonomics & process-flow review.** Walk the line virtually before building it; industrial engineers annotate reach/flow issues. Estimate: $20–100k/yr per manufacturer → $300k–2M ARR; 9–15 months.
9. **Evacuation & hazard drill rehearsal.** Run and critique drills in the facility twin with all shift leads on voice. Estimate: $10–50k/yr per site → $300k–2M ARR; 9–15 months.
10. **White-label twin viewer for systems integrators.** Integrators resell the collab viewport inside their digital-twin offerings. Estimate: $100k–500k/yr per integrator → $500k–3M ARR; 12–18 months.

---

## Part B — Five industries that are easiest to monetize

Ranked by friction-to-first-dollar: product fits as-is, buyers are self-serve, sales cycles are short, compliance is minimal. Ceilings are lower; floors arrive much faster.

### B1. Indie & retro game developers (prosumer)

**Why easiest:** The product is *already their tool* — no adaptation, no import formats, no compliance. Buyers are online, pay by card, and the retro/homebrew scene is passionate, underserved, and reachable through open channels (itch.io, jams, Discord, YouTube). The wallet is small but the distance to it is nearly zero.
**Realistic aggregate:** $100k–700k/yr across several of these; first dollars in weeks.

1. **Pro subscription.** $8–15/mo: private rooms, larger levels, cloud saves, priority relay bandwidth. Estimate: $50k–500k ARR; first revenue 1–2 months.
2. **Lifetime license on itch.io.** $40–80 one-time; the retro crowd strongly prefers buy-once. Estimate: $20k–200k/yr; ~1 month.
3. **Team rooms for small studios.** $25–50/mo per team: roles, persistent projects, history. Estimate: $30k–300k ARR; 2–3 months.
4. **Hosted game jams.** Entry fees and sponsor placement on jams run inside the tool (team formation + collab built in). Estimate: $2–10k per jam, monthly-ish → $25k–100k/yr; 2–4 months.
5. **Starter & template level packs.** $10–30 packs (genre kits, tilesets, example scripting). Estimate: $10k–100k/yr; 1–2 months.
6. **Sponsorware for the OSS core.** GitHub Sponsors/Patreon tiers gating early builds and votes on the roadmap. Estimate: $10k–80k/yr; ~1 month.
7. **Paid community + workshops.** $5–10/mo Discord tier with monthly live level-design workshops (the A/V is the venue). Estimate: $10k–80k/yr; 1–2 months.
8. **Commercial-shipping license.** Free/cheap to hobby, $200–500/yr once you ship a paid game built with it. Estimate: $20k–150k/yr; 2–4 months.
9. **Retro-console export add-on.** PSX-format/retro-target export as a paid feature — the fixed-point engine is the differentiator no web tool can copy. Estimate: $20k–150k/yr; 3–6 months.
10. **Merch & boxed collector's edition.** Big-box toolchain release with manual, the retro collector market buys physical. Estimate: $10k–75k/yr; 3–5 months.

### B2. Education (K-12 STEM, camps, bootcamps, universities)

**Why easy:** Browser-based + no-install + *supervised, built-in* A/V is precisely what teaching game design in classrooms and remote programs needs, and IT departments approve browser tools far faster than installs. Per-classroom price points ($200–1000/yr) clear teacher purchase-card thresholds without procurement. COPPA/FERPA work is real but bounded and one-time. Sales are seasonal (school-year cycles) but renewals are sticky.
**Realistic aggregate:** $500k–3M ARR; first revenue one school-buying-season away.

1. **Classroom site license.** $300–800/classroom/yr, teacher dashboard, student rosters. Estimate: $100k–1M ARR; 3–6 months (land pilots before the fall term).
2. **Curriculum packs.** Lesson plans, rubrics, and standards-aligned projects sold atop the license. Estimate: $50k–300k/yr; 3–6 months.
3. **Camp & after-school operator licensing.** Chains (Code-Ninjas-style) license per-location for summer/after-school programs. Estimate: $1–5k/location/yr → $100k–500k ARR; 3–6 months.
4. **Teacher PD workshops & certification.** Paid training delivered inside the tool itself. Estimate: $30k–200k/yr; 2–4 months.
5. **University game-design lab licenses.** Departmental licenses; the collab + A/V fits studio-course critique sessions. Estimate: $2–10k/dept/yr → $50k–300k ARR; 4–8 months.
6. **Student showcase & portfolio hosting.** Parents pay a small fee for a hosted, shareable portfolio of the student's worlds. Estimate: $20k–150k/yr; 4–6 months.
7. **Sponsored student competitions.** Sponsors fund themed build competitions; schools join free. Estimate: $25k–150k/yr in sponsorships; 4–8 months.
8. **LMS integration add-on.** Canvas/Google Classroom roster + grade passback as a paid tier. Estimate: $30k–200k/yr attach; 6–9 months.
9. **Homeschool co-op bundles.** Family/co-op pricing with a lighter curriculum; reachable through homeschool networks. Estimate: $20k–150k/yr; 2–4 months.
10. **Grant-funded STEM programs.** Partner with nonprofits on rural/underserved programs funded by state and federal STEM grants. Estimate: $50k–300k per program cycle; 6–12 months.

### B3. Tabletop RPG & virtual tabletops (VTT)

**Why easy:** The D&D-era audience already pays for online play (Roll20 subscriptions, Foundry VTT's $50 license, D&D Beyond) and already runs sessions over voice/video — wf_edit's shared 3D scene + A/V + chat *is* a VTT core loop, and 3D encounter building is the premium differentiator over 2D maps (TaleSpire proved demand). Buyers are consumers with cards; the paid-GM economy adds a prosumer tier that pays for production value.
**Watch out:** naming — "Foundry VTT" is an entrenched incumbent; "WorldFoundry" predates it but confusion cuts both ways. Brand the product line distinctly.
**Realistic aggregate:** $500k–5M ARR.

1. **GM subscription for 3D encounter maps.** $8–15/mo: build and run encounters in 3D with players joining free in-browser. Estimate: $100k–1M ARR; 2–4 months.
2. **Map & asset marketplace.** 30% take on community tilesets, tokens, and prebuilt encounters. Estimate: $50k–500k/yr; 4–8 months.
3. **Campaign hosting.** Persistent per-campaign worlds with session history; per-campaign or bundled pricing. Estimate: $50k–400k ARR; 3–6 months.
4. **Roll20/Foundry export plugin.** Paid bridge: build in 3D, export battlemap renders + walls/lighting into the incumbent VTTs — sell to their users without fighting them. Estimate: $30k–200k/yr; 3–5 months.
5. **Pro-GM toolkit.** Paid DMs (charging $20–50/seat/session) buy production value: staged reveals, camera control, ambience. Estimate: $50k–300k ARR; 3–6 months.
6. **Publisher partnerships.** Official adventure modules as ready-to-run 3D scenes, revenue-shared with the publisher. Estimate: $50k–500k/yr; 6–12 months.
7. **Kickstarter themed edition.** Dungeon tileset + tool bundle as a campaign — the TTRPG Kickstarter channel is proven and doubles as marketing. Estimate: $30k–300k one-time; 4–6 months.
8. **Convention & one-shot event mode.** Per-event licensing for cons and organized play: drop-in tables, spectator mode. Estimate: $20k–100k/yr; 4–8 months.
9. **Mini-STL export.** Build the encounter, print the terrain — export watertight STLs as a paid add-on bridging to the 3D-printing hobby. Estimate: $20k–150k/yr; 4–6 months.
10. **Actual-play streamer toolkit.** Spectator cameras, overlay-friendly output, scene-switching for shows. Estimate: $20k–150k/yr; 3–6 months.

### B4. Content creators, streamers & online communities

**Why easy:** Creators buy tools that generate content, and *collaborative building is itself content* — speedbuilds, chat-driven builds, community world projects. Payments are consumer-grade, integrations (Twitch/Discord) are cheap to build, and the tool being on-stream is its own acquisition channel (CAC ≈ 0 when the product is the show). Attention is fickle, so revenue is spikier than B1–B3.
**Realistic aggregate:** $200k–2M/yr.

1. **Streamer mode.** Chat-triggered edits, votes, and channel-point redemptions manipulate the live scene. Estimate: $15–30/mo → $50k–500k ARR; 2–4 months.
2. **Speedbuild competition platform.** Scheduled head-to-head builds with entry fees, spectating, and sponsor slots. Estimate: $30k–300k/yr; 4–8 months.
3. **Timelapse & replay export.** The CRDT history *is* a replay — render build timelapses for YouTube as a pro feature. Estimate: $20k–200k/yr; 2–4 months.
4. **Community world servers.** Discord-integrated persistent rooms; the server owner pays $10–50/mo. Estimate: $50k–400k ARR; 3–6 months.
5. **Commission marketplace.** Match scene-builders with buyers (streamer sets, community hubs); take 15–25%. Estimate: $20k–200k/yr; 4–8 months.
6. **Niche-community meetup spaces.** Fandoms and hobby groups hold events in worlds they built together; community pricing. Estimate: $20k–150k/yr; 3–6 months.
7. **Sponsored build events.** Brands fund themed public builds with creator rosters. Estimate: $10–50k per campaign → $50k–300k/yr; 6–9 months.
8. **Tip-driven public builds.** Viewers tip to influence a communal build; platform takes a cut. Estimate: $10k–100k/yr; 3–5 months.
9. **Creator affiliate program.** Rev-share on Pro-tier referrals from build-content creators. Estimate: indirect — accelerates B1/B4 subscriptions 10–30%; 2–3 months.
10. **Clip-to-level contests.** Sponsors fund contests recreating famous scenes/moments as playable levels. Estimate: $20k–150k/yr; 4–6 months.

### B5. Corporate team-building & virtual events (SMB)

**Why easy:** HR and team leads buy remote team activities at $20–80/head on a credit card with zero procurement, and "build a tiny world together while on voice/video" is a complete team-building activity **with the product exactly as it exists today**. Facilitation is a services wrapper you can sell before writing another line of code — the fastest possible first dollar in this whole document. The trade-off: services-flavored, and it doesn't scale without productizing.
**Realistic aggregate:** $100k–1M/yr.

1. **Facilitated build-together workshops.** 90-minute guided sessions, $750–2500 per team. Estimate: $50k–300k/yr; first revenue in 2–6 weeks.
2. **Self-serve event kits.** $199–499: themed scenario, prompts, and a run-of-show the team lead follows. Estimate: $30k–200k/yr; 1–3 months.
3. **Seasonal themed events.** Holiday-party and mid-year offsites; December and June spike hard. Estimate: $30k–200k/yr; 2–3 months (time the launch).
4. **Onboarding icebreakers.** "Build our office / our team world" as a recurring new-cohort ritual; subscription per cohort. Estimate: $20k–150k/yr; 2–4 months.
5. **Escape-room-style collaborative puzzles.** Scripted puzzle levels (the scripting engine does the work) solved by co-editing. Estimate: $30k–250k/yr; 3–6 months.
6. **White-label for team-building agencies.** Agencies resell it inside their catalogs; $100–300 platform fee per event. Estimate: $30k–250k/yr; 3–6 months.
7. **Recurring team "guild" subscriptions.** Monthly build nights for distributed teams, $50–150/team/mo. Estimate: $20k–150k ARR; 2–4 months.
8. **Conference & booth experiences.** Event organizers run collaborative-build installations; per-event licensing. Estimate: $20k–150k/yr; 4–6 months.
9. **Offsite & hackathon add-ons.** Packaged as the social track of engineering offsites and hackathons. Estimate: $20k–100k/yr; 2–4 months.
10. **Gift vouchers.** Give a team a facilitated build session; consumer-style gifting flow. Estimate: $10k–75k/yr; 2–3 months.

---

## 3. Cross-cutting summary

| Track | Industry | Ceiling (ARR at maturity) | First revenue | Adaptation required | Main risk |
|---|---|---|---|---|---|
| A1 | Games & interactive | $1M–100M+ | 2–24 mo | None → platform infra | Hits-driven at the top end |
| A2 | AEC + real estate | $10–50M | 9–18 mo | IFC/glTF, markup, SOC2 | Entrenched incumbents, sales motion |
| A3 | Film/TV previz | $5–30M | 9–15 mo | USD/glTF, camera tools | Small niche, relationship-driven |
| A4 | Defense & sim training | $10M+ (slow) | 6–12 mo (SBIR) | Compliance, on-prem, standards | Timeline + compliance burden |
| A5 | Industrial twins & training | $5–30M | 9–18 mo | CAD import, SSO, integrations | Enterprise sales capacity at team size |
| B1 | Indie/retro gamedev | $0.1–0.7M | 1–2 mo | ~None | Small wallets |
| B2 | Education | $0.5–3M | 3–6 mo | COPPA/FERPA, dashboards | Seasonal cycles, slow districts |
| B3 | Tabletop/VTT | $0.5–5M | 2–4 mo | Content pipeline, UX polish | Incumbent ecosystems; naming collision |
| B4 | Creators & communities | $0.2–2M | 2–4 mo | Twitch/Discord integrations | Fickle attention |
| B5 | Team-building events | $0.1–1M | <2 mo | None (services wrapper) | Doesn't scale unproductized |

Observations:

- **The single highest-leverage engineering investment is glTF import/export.** It converts wf_edit from "WorldFoundry's editor" into "a collaborative 3D scene tool," unlocking all of Part A. Nothing else on the list changes the ceiling as much.
- **The B industries are also the beachhead for A1.** Indie/VTT/creator traction produces the user base an eventual marketplace or platform needs; they aren't detours.
- **A/V is the differentiator but also the cost center.** Every pricing model above should meter or cap relay bandwidth from day one.
- **If vertical traction stalls, the substrate is the fallback.** Licensing the CRDT + WebRTC + wasm-viewport layer as an SDK (A1.3) monetizes the hardest-to-replicate engineering directly.

## 4. Recommended sequencing (opinion, not gospel)

1. **Now (0–3 months):** B5 facilitated workshops + B1 prosumer tier. First dollars on the current stack with zero new engineering; every paid session is also user research and a testimonial.
2. **3–12 months:** Pick **one** of B3 (VTT) or B2 (education) as the product wedge — VTT if consumer energy shows up, education if you want steadier renewals. Ship glTF import/export during this phase regardless.
3. **12+ months:** With the format layer done, run a real validation pass (deep research + ~20 customer interviews each) on A2 vs A3, and commit to one. File SBIR applications (A4) opportunistically throughout — grant money subsidizes the roadmap without a pivot.
4. **The UGC platform (A1.2) is the lottery ticket.** Keep it as the north star that shapes architecture decisions (identity, persistence, moderation hooks), but don't bet the runway on it.

## 5. Validation before committing

None of the figures above have been market-tested. Before any roadmap commitment:

- A structured research pass per shortlisted industry (market size, buyer, incumbent pricing) — the deep-research tooling in this environment is suited to exactly this.
- 10+ customer conversations for each of the top two picks.
- A price test (landing page + checkout) for the B-track ideas — they're cheap to test for real.
- Competitive scan minimums: Roblox/Fortnite-UGC and Core (A1); Revizto, Resolve, Autodesk Construction Cloud (A2); Unreal previz workflows, Cine Tracer (A3); Bohemia VBS, CAE (A4); Matterport, NVIDIA Omniverse (A5); TaleSpire, Foundry VTT, Roll20 (B3); Gather, Teamflow (B5).
