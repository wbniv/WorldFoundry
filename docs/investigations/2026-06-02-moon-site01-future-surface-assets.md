# Moon Site 01 — Future Surface Assets

**Date:** 2026-06-02
**Author:** Claude (research)
**Context:** What real-world Artemis-architecture vehicles, habitats, and infrastructure are planned for the lunar south pole — to inform what to model next in `wflevels/moon_site01/`. The level already has an Artemis Starship HLS lander; this document surveys the rest of the planned surface campaign so we can keep adding to the scene with hardware that actually belongs there.

## TL;DR

- **Artemis V (NET 2030)** is the first crewed mission to use an **unpressurized Lunar Terrain Vehicle (LTV)** — NASA picked **Intuitive Machines (Moon RACER)**, **Lunar Outpost (Lunar Dawn)**, and **Venturi Astrolab (FLEX)** for a 12-month feasibility phase in April 2024 [^1][^2].
- **Artemis VII (NET 2031)** is the planned delivery of the **JAXA / Toyota Lunar Cruiser** — a 6 m × 5.2 m × 3.8 m pressurized rover with a 30-day, 20 km/day range [^3][^4].
- The **Foundation Surface Habitat (FSH)** — a three-storey hybrid metallic+inflatable structure with ~127 m³ habitable volume — is targeted for the 2030s [^5][^6].
- **Vertical Solar Array Technology (VSAT)** prototypes from Astrobotic, Honeybee Robotics and Lockheed Martin deploy 10 m–32 m tall above polar shadows [^7][^8].
- **Fission Surface Power**: 40 kW-class reactor design studies from Lockheed Martin, Westinghouse, and IX (X-energy + Intuitive Machines) completed Phase 1 in early 2026; flight-hardware RFP imminent [^9][^10].
- **PRIME-1** (TRIDENT drill + MSolo mass spectrometer) flew on IM-2 in early 2025 as the first polar ice-mining ISRU demo [^11][^12].
- **Blue Moon Mark 1** ("Endurance"), Blue Origin's 3-tonne cargo lander, completed thermal-vacuum testing at NASA JSC in May 2026; first flight late 2026 [^13][^14].
- **ESA Lunar Pathfinder** comms relay enters service in 2026 as the precursor to the **ESA Moonlight / NASA LunaNet** constellation [^15][^16].
- **Lunar Gateway** was paused in March 2026 in favour of accelerating the surface base; HALO/PPE hardware is being repurposed [^17].

---

## 1. Lunar Terrain Vehicle (LTV) — unpressurized rover

The LTV is the modern descendant of the Apollo Lunar Roving Vehicle: an open-cab, suited-driver, ~4 m-long electric buggy used by Artemis V (NET 2030) and beyond for extending EVA range beyond walking distance. On 3 April 2024 NASA awarded the LTV Services contract — an IDIQ vehicle with a combined maximum value of US$4.6 billion across all eventual task orders — to **Intuitive Machines** (vehicle: **Moon RACER**, partners Boeing, Northrop Grumman, Michelin, Roush), **Lunar Outpost** (vehicle: **Lunar Dawn**, partners Lockheed Martin, GM, Goodyear, MDA Space), and **Venturi Astrolab** (vehicle: **FLEX**). Each team received a US$30 million feasibility task order for a 12-month preliminary-design study, after which NASA will down-select to one provider for a demonstration mission that delivers the rover to the surface ahead of Artemis V crew operations. The LTV must survive a full lunar night at the south pole, be operable both crewed and tele-robotically (so it can do uncrewed science between Artemis missions), and provide a science platform with a robotic arm and sample stowage. Service provision extends through 2039 [^1][^2][^18].

![Intuitive Machines Moon RACER artist concept](https://www.nasa.gov/wp-content/uploads/2024/04/intuitive-machines.jpg)
*Moon RACER concept art (Intuitive Machines / NASA, April 2024). Source: [NASA News Release 24-027](https://www.nasa.gov/news-release/nasa-selects-companies-to-advance-moon-mobility-for-artemis-missions/).*

---

## 2. Pressurized Rover (Toyota / JAXA Lunar Cruiser)

The **Lunar Cruiser** is JAXA's contribution to the Artemis architecture, developed jointly with Toyota since 2019. It is a pressurized, crewed mobile habitat — roughly the size of two microbuses (6 m long × 5.2 m wide × 3.8 m high) with a ~7 m² internal pressurized cabin — that lets two astronauts roam up to 20 km/day for 30 days at a stretch, using its own ECLSS as a backup to the fixed base. Power comes from a regenerative fuel cell (RFC): a closed water-electrolysis-and-fuel-cell loop driven by solar input, which also produces drinking water as a by-product. Toyota is developing per-wheel motors with independent steering and lunar-dust-tolerant tires; the design target lifespan is 10 years. JAXA hopes for an Artemis VII delivery in 2031 [^3][^4][^19]. A 1/5-scale model of the updated design was exhibited at Expo 2025 Osaka [^20].

![Toyota / JAXA Lunar Cruiser concept](https://upload.wikimedia.org/wikipedia/commons/7/79/NASA_Foundation_Surface_Habitat.png)
*NASA Artemis Plan figure depicting Foundation Surface Habitat alongside surface mobility — the canonical Lunar Cruiser renders from Toyota's site are behind a 403 and JAXA's press page hosts no embeddable images, so the embedded image here shows the wider base-camp context; the canonical official Lunar Cruiser artwork is the hero render on [global.toyota/en/mobility/technology/lunarcruiser/](https://global.toyota/en/mobility/technology/lunarcruiser/index.html) (Toyota Motor Corporation, 2023–2025).*

---

## 3. Foundation Surface Habitat (FSH)

The FSH is the keystone of NASA's Artemis Base Camp — a fixed, non-mobile habitat that anchors long-term human presence at the south pole and provides housing for up to four astronauts on rotations of one to two months. The current reference design is a three-storey hybrid: a 4 m-diameter metallic base module containing the airlock, EVA suit storage, and the geology lab (so suit-borne regolith never spreads into the living quarters), with two upper floors inside a 6.5 m-diameter inflatable shell containing crew quarters, galley, hygiene, and operations stations. Total habitable volume is ~127 m³ — roughly one-tenth of the ISS but enormous by deep-space-habitat standards. The habitat is self-sufficient: its own ECLSS (Collins Aerospace pallets are the current reference design, with two oxygen generation pallets processing CO₂ back to O₂), thermal control, radiation shielding, waste management, and science utilization. NASA does not build it itself — it will be procured commercially, in the same vein as the LTV and HLS. Target deployment is the 2030s, currently penciled in for the Artemis VIII timeframe [^5][^6][^21][^22].

![NASA Foundation Surface Habitat concept](https://upload.wikimedia.org/wikipedia/commons/7/79/NASA_Foundation_Surface_Habitat.png)
*NASA Foundation Surface Habitat concept, from NASA's *Artemis Plan* (NASA, 23 September 2020). Public-domain. Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:NASA_Foundation_Surface_Habitat.png).*

---

## 4. Vertical Solar Array Technology (VSAT)

At Shackleton-region latitudes (~89.9° S) the sun never climbs more than ~1.5° above the horizon, so flat ground panels are useless — every boulder and crater rim is a several-kilometre shadow. The VSAT programme funds vertical, autonomously self-deploying solar towers that get the cells above the local horizon line. NASA awarded ~US$19.4 million in March 2022 to three contractors to mature prototype hardware to a TRL-6 demonstration:

- **Astrobotic Technology** (Pittsburgh) — US$6.2 M; the **LunaGrid** product family, with the 10 kW "VSAT" mast and a 50 kW / 30 m-tall **VSAT-XL** funded by a follow-on SBIR Phase II. LunaGrid VSAT entered thermal-vacuum testing at NASA Glenn in July 2024 [^23][^24].
- **Honeybee Robotics** (Brooklyn) — US$7 M; vertical deployable array.
- **Lockheed Martin** (Littleton, CO) — US$6.2 M.

Requirements: deploy autonomously to ~10 m baseline (32 ft), and ideally up to ~20 m, with the array retractable and relocatable. Final reports from the prototype phase came in in early 2025; flight-hardware procurement to follow [^7][^8].

![Astrobotic LunaGrid VSAT rendering](https://www.astrobotic.com/wp-content/uploads/2024/07/02_LunaGrid_Griffin_CR_VSAT_3.1_CAM.002_4K_NT.01_R.010_PS1.2-1024x576.jpg)
*LunaGrid VSAT delivered to the Moon by Astrobotic's Griffin lander, tethered to a CubeRover wireless-charging node (Astrobotic, 19 July 2024). Source: [Astrobotic press release](https://www.astrobotic.com/lunagrids-vertical-solar-array-technology-enters-tvac/).*

---

## 5. Fission Surface Power (FSP)

VSAT towers solve the daylight-side power problem, but the polar night (continuous shadow for weeks at a time inside permanently shadowed regions, or PSRs) needs a non-solar source. Hence the joint NASA/DOE **Fission Surface Power** programme: a ~40 kW-class compact fission reactor that can run for a decade unattended on the surface. In June 2022 NASA and the Department of Energy awarded three US$5 M Phase 1 design contracts:

- **Lockheed Martin** with BWX Technologies and Creare — emphasising high-reliability primary cooling and in-situ regolith shielding.
- **Westinghouse** with Aerojet Rocketdyne — leveraging the **eVinci** heat-pipe microreactor, which has minimal moving parts.
- **IX** (a Maxar + Intuitive Machines + Boeing-backed joint venture, fuel from X-energy's TRISO-X) — closed Brayton cycle with a He-Xe working fluid.

All three Phase 1 design concepts were submitted; by late February 2026 the project transitioned into a competitive procurement for flight hardware, with a Final RFP expected in early 2026. Recent NASA/Congressional guidance is pushing the target output upward toward 100 kW. Target deployment is "early 2030s" [^9][^10][^25].

![Fission Surface Power concept](https://www.nasa.gov/wp-content/uploads/2023/05/fsp-lunar-setup-concept.jpg)
*NASA's Fission Surface Power surface-deployment concept (NASA Glenn Research Center, May 2023). Source: [NASA Fission Surface Power](https://www.nasa.gov/exploration-systems-development-mission-directorate/fission-surface-power/).*

---

## 6. ISRU pilot plants (PRIME-1 / PRIME-2)

In-Situ Resource Utilization is the long-game payoff at the south pole: the PSRs contain water ice that can be cracked to hydrogen and oxygen for life support and propellant. The first demonstration was **PRIME-1** (Polar Resources Ice Mining Experiment 1), a payload pair carried on Intuitive Machines' **IM-2** Nova-C lander that touched down at Mons Mouton on 6 March 2025. PRIME-1 combined two instruments built by NASA Kennedy: **TRIDENT** (The Regolith and Ice Drill for Exploring New Terrain), a 1 m-augering drill, and **MSolo** (Mass Spectrometer Observing Lunar Operations), a COTS mass spectrometer capable of identifying species in the 1–100 amu range and distinguishing terrestrial contamination from native volatiles. The mission's science goal was to characterize how water and other volatiles are distributed with depth in polar regolith. (The IM-2 lander tipped over on landing, but PRIME-1 still produced useful surface-volatile measurements before LOS.) PRIME-2 is in concept-study phase as a successor with a larger sample throughput [^11][^12][^26].

![PRIME-1 TRIDENT drill](https://www.nasa.gov/wp-content/uploads/2020/07/prime-1_web_photo_1.jpg)
*PRIME-1 TRIDENT drill flight unit at NASA Kennedy Space Center (NASA, 2020). Source: [NASA PRIME-1 mission page](https://www.nasa.gov/mission/polar-resources-ice-mining-experiment-1-prime-1/).*

---

## 7. Cargo landers

The Artemis architecture pairs the two crewed Human Landing System variants (SpaceX Starship HLS, Blue Origin Blue Moon Mark 2) with dedicated **uncrewed cargo landers** that pre-position rovers, habitats, VSAT towers, ISRU plants, and bulk supplies. The two main near-term cargo variants are:

- **Blue Origin Blue Moon Mark 1 ("Endurance")** — single-launch, single-stage uncrewed lander; ~8 m tall, ~3 m diameter, 21,350 kg wet mass; payload to lunar surface ~3,000 kg. Optimised for New Glenn launch. Environmental testing wrapped up in NASA JSC's Thermal Vacuum Chamber A in May 2026; first flight (MK1-SN001 pathfinder) is currently manifesting for late 2026 [^13][^14][^27].
- **Starship Cargo** — uncrewed variant of the SpaceX Starship HLS, capable of delivering 12–15 tonnes of payload in a single landing per NASA's payload-class statement. Target first flight slipped to 2032 alongside Artemis VII in current planning [^14][^28].

Both vehicles enable the "deliver heavy infrastructure ahead of crew" model — habitats, the pressurized rover, the fission reactor and the VSAT towers all need a cargo lander to put them on the surface.

![Blue Moon Mark 1 in thermal-vacuum testing](https://www.nasa.gov/wp-content/uploads/2026/05/blue-origin-mk-1.jpg)
*Blue Origin's Blue Moon Mark 1 (MK1) lander after environmental testing in Chamber A, NASA Johnson Space Center (NASA, 4 May 2026). Source: [NASA Blue Origin lander testing](https://www.nasa.gov/missions/artemis/blue-origin-moon-lander-completes-testing-at-nasa-vacuum-chamber/).*

---

## 8. Lunar comms relay — LunaNet / ESA Moonlight / Lunar Pathfinder

The south pole is comms-hostile: half the candidate surface sites lose direct line-of-sight to Earth because of crater rims, and operations inside PSRs lose it entirely. The reference architecture is a small fleet of relay satellites in lunar elliptical or frozen orbits, federated under the NASA-ESA-JAXA **LunaNet Interoperability Specification (LNIS)** so providers from different agencies and commercial vendors deliver compatible services. Two near-term elements:

- **ESA Lunar Pathfinder** — a Surrey Satellite Technology Ltd (SSTL) S-band/X-band relay, launch slipped to 2026; the precursor to ESA's full **Moonlight Lunar Communications and Navigation Service (LCNS)** constellation, which prioritises south-pole coverage [^15][^29].
- **NASA Lunar Communications Relay and Navigation Systems (LCRNS)** — a commercial-services contract under which providers deliver LunaNet-compatible relay capacity to NASA missions [^16].

Lunar Pathfinder provides two S-band uplinks to surface and orbital assets plus an X-band downlink to Earth, removing the need for every small lander/rover to carry its own Direct-To-Earth high-gain antenna [^15].

![ESA Lunar Pathfinder concept](https://www.esa.int/var/esa/storage/images/esa_multimedia/images/2021/09/lunar_pathfinder/23463393-2-eng-GB/Lunar_Pathfinder.png)
*ESA / SSTL Lunar Pathfinder artist's impression (ESA / SSTL, 16 September 2021). Source: [ESA Multimedia](https://www.esa.int/ESA_Multimedia/Images/2021/09/Lunar_Pathfinder).*

---

## 9. Surface stowage / sample caches / cargo offload

Beyond the headline hardware, NASA's surface architecture white papers call out a constellation of mundane-but-essential surface equipment: **sample collection boxes** (the Apollo Lunar Sample Return Container is the canonical precedent and modern Artemis boxes are direct evolutions of it), **EVA suit cache stations** stored in the airlock to keep regolith out of the habitat, **middeck-locker equipment racks** on the FSH third level, and dedicated **science utilization workstations** in the habitat geology lab. For getting equipment off the lander and over to base camp, NASA Langley's **ALLGO** (Advanced Lightweight Lunar Gantry for Operations) challenge — and the open Lunar Logistics & Mobility solicitation that followed in October 2024 — seeks inflatable-element mobile gantries that can transfer payloads roughly a mile from landing site to base. The 2024 Moon to Mars Architecture white papers detail the cargo-offload-and-transport problem explicitly as a near-term capability gap that needs commercial solutions [^21][^22][^30][^31].

![Artemis Base Camp surface concept](https://www.nasa.gov/wp-content/uploads/2020/10/surface-1024x576-1.jpg)
*Astronauts on the lunar South Pole — Artemis Base Camp concept, showing pressurized rover, FSH, sample stowage and surface mobility (NASA, 28 October 2020). Source: [NASA "Lunar Living: Artemis Base Camp Concept"](https://www.nasa.gov/blogs/missions/2020/10/28/lunar-living-nasas-artemis-base-camp-concept/).*

---

## 10. Lunar Gateway (orbital context)

The **Lunar Gateway** was the originally-planned small space station in a Near-Rectilinear Halo Orbit (NRHO) around the Moon — Orion would dock with it, transfer crew to the HLS, and the HLS would descend from there. The first two modules (Northrop Grumman's HALO habitation/logistics outpost and the Maxar PPE Power and Propulsion Element) were under construction with HALO arriving in the US in April 2025. However, in March 2026 NASA announced it would **pause Gateway as designed**, citing HALO structural-corrosion issues and the fact that HLS providers (SpaceX, Blue Origin) had designed their landers to operate without Gateway docking anyway. The current direction is for Orion to rendezvous directly with the HLS in lunar orbit, with Gateway hardware and international-partner contributions (ESA's Lunar View, Canadarm3, JAXA's ECLSS) repurposed into the surface base programme between 2029 and 2036 [^17][^32]. **Implication for Moon Site 01:** Gateway is not a surface asset and the architecture is in flux, but if we ever model an orbital backdrop the HALO/PPE silhouette is still the canonical Artemis-era station shape.

![Gateway HALO module at Thales Alenia Space, Turin](https://www.nasa.gov/wp-content/uploads/2024/07/halo-tas-for-nasa-03-2.jpg)
*Gateway HALO module under construction at Thales Alenia Space, Turin (NASA, July 2024). Source: [NASA Gateway gallery](https://www.nasa.gov/image-article/gateway-illuminating-the-future/).*

---

## What to model next in Moon Site 01

The existing scene has the **Starship HLS** as a vertical, ~50 m hero silhouette on the regolith. To maximise visual variety and architectural plausibility per modelled hour, I'd recommend adding hardware in this order:

**Round 1 — ground-level companions to the lander.** The **LTV** (one of the three concepts; **Moon RACER** has the cleanest published reference photos because Intuitive Machines built a drivable Earth-side mock-up in November 2024) is the highest-bang-for-buck next addition: it's small (~4 m), it sits in the foreground, it's recognisably "Artemis" rather than generic sci-fi, and it pairs naturally with two suited-astronaut figures. Next, a **VSAT** tower (Astrobotic LunaGrid is the most-photographed reference) — 10 m to 32 m vertical posts give a striking vertical counterpoint to the horizontal regolith while staying physically small and modular. Together those two pieces transform the lone-lander silhouette into a "south-pole construction site" mise-en-scène without requiring new airspace.

**Round 2 — mid-size pressurised hardware.** Add the **Toyota/JAXA Lunar Cruiser** (6 m × 5.2 m × 3.8 m — a microbus-sized boxy module on six wheels) as the long-duration mobility counterpoint to the LTV, and a **Blue Moon Mark 1 cargo lander** (8 m × 3 m, gold-foil-wrapped — visually very distinct from Starship's stainless cylinder) to establish that this is a logistics-hub base, not a single-mission landing site. The Lunar Cruiser is genuinely iconic (Toyota brand recognition + JAXA's first lunar presence) and the gold-foil/silver-cylinder contrast between MK1 and Starship is visually dramatic in side-lit polar lighting.

**Round 3 — heavy infrastructure (longer to model).** The **Foundation Surface Habitat** is the largest commitment (three-storey hybrid metallic+inflatable, regolith-shielded), but it transforms the level from "early-mission tableau" into "established base camp." Pair it with a **Fission Surface Power** reactor (sited a few hundred metres away with the radiator skirt visible, per the NASA Glenn reference imagery) and a **PRIME-style ISRU plant** with TRIDENT drill near a PSR rim. Comms relays (Lunar Pathfinder / LunaNet) are orbital and probably not worth modelling unless we add a sky/space backdrop; same for Gateway. For surface stowage, even just a few **sample-return boxes**, an EVA cache rack outside the airlock, and a generic equipment pallet near the cargo lander would sell the "this is a working base" impression cheaply.

Stylistic note: every one of these designs is at TRL 5–6 today (April 2024 / 2025 / 2026 contracts), which means the reference geometry will keep shifting. Modelling against the published 2025/2026 reference renders is fine — when down-select happens (one LTV winner, one VSAT winner, one FSP winner) we can swap them in. For now, **Moon RACER, Lunar Cruiser, MK1, FSH, LunaGrid VSAT, and a generic FSP reactor** are the six pieces with the strongest published reference geometry to model against.

---

## References

[^1]: NASA, "NASA Selects Companies to Advance Moon Mobility for Artemis Missions," news release, 3 April 2024. https://www.nasa.gov/news-release/nasa-selects-companies-to-advance-moon-mobility-for-artemis-missions/
[^2]: Intuitive Machines, "Intuitive Machines-led Moon RACER Team Awarded NASA Lunar Terrain Vehicle Contract," press release, 3 April 2024. https://investors.intuitivemachines.com/news-releases/news-release-details/intuitive-machines-led-moon-racer-team-awarded-nasa-lunar
[^3]: Toyota Motor Corporation, "LUNAR CRUISER — Technology / Mobility," accessed 2 June 2026. https://global.toyota/en/mobility/technology/lunarcruiser/index.html
[^4]: JAXA, "JAXA and Toyota Announce 'LUNAR CRUISER' As Nickname for Manned Pressurized Rover," press release, 28 August 2020. https://global.jaxa.jp/press/2020/08/20200828-1_e.html
[^5]: New Space Economy, "The Artemis Foundation Surface Habitat," 12 August 2025. https://newspaceeconomy.ca/2025/08/12/the-artemis-foundation-surface-habitat/
[^6]: NASA Technical Reports Server, Burke et al., "Internal Layout of a Lunar Surface Habitat," 2022 ASCEND AIAA. https://ntrs.nasa.gov/api/citations/20220013669/downloads/Internal%20Layout%20of%20a%20Lunar%20Surface%20Habitat.pdf
[^7]: NASA, "Three Companies to Help NASA Advance Solar Array Technology for Moon," news release, March 2022. https://www.nasa.gov/news-release/three-companies-to-help-nasa-advance-solar-array-technology-for-moon/
[^8]: NASA, "NASA, Industry to Mature Vertical Solar Array Technologies for Lunar Surface," March 2021. https://www.nasa.gov/technology/nasa-industry-to-mature-vertical-solar-array-technologies-for-lunar-surface/
[^9]: NASA, "Fission Surface Power," programme page, accessed 2 June 2026. https://www.nasa.gov/exploration-systems-development-mission-directorate/fission-surface-power/
[^10]: American Nuclear Society Newswire, "Westinghouse's lunar microreactor concept gets a contract for continued R&D," 15 January 2025. https://www.ans.org/news/2025-01-15/article-6686/westinghouses-lunar-microreactor-concept-gets-a-contract-for-continued-rd/
[^11]: NASA, "Polar Resources Ice Mining Experiment-1 (PRIME-1)," mission page. https://www.nasa.gov/mission/polar-resources-ice-mining-experiment-1-prime-1/
[^12]: NASA Technical Reports Server, "Polar Resources Ice Mining Experiment-1 (PRIME-1): NASA's First Polar Drilling and Volatiles Detection Mission," 2023. https://ntrs.nasa.gov/citations/20230007582
[^13]: Blue Origin, "Blue Moon Mark 1 Lunar Lander," product page. https://www.blueorigin.com/blue-moon/mark-1
[^14]: NASA, "Blue Origin Moon Lander Completes Testing at NASA Vacuum Chamber," 4 May 2026. https://www.nasa.gov/missions/artemis/blue-origin-moon-lander-completes-testing-at-nasa-vacuum-chamber/
[^15]: ESA, "Lunar Pathfinder," Business Space Generation Network service page. https://bsgn.esa.int/service/lunar-pathfinder/
[^16]: NASA Goddard Exploration and Space Communications, "Lunar Communications Relay and Navigation Systems (LCRNS)." https://www.nasa.gov/goddard/esc/lcrns/
[^17]: NASA / SpacePolicyOnline coverage of March 2026 Gateway pause and lunar-surface reprioritisation. (Cross-referenced in [New Space Economy: "NASA's Moon Base"](https://newspaceeconomy.ca/2026/04/20/nasas-moon-base-architecture-phasing-and-the-engineering-gaps-behind-a-permanent-lunar-outpost/), 20 April 2026.)
[^18]: SpaceNews, "Companies race to win ground transportation contracts for the moon." https://spacenews.com/companies-race-to-win-ground-transportation-contracts-for-the-moon/
[^19]: Toyota Times, "Team Japan Sets Sights on Space! Update on LUNAR CRUISER Development." https://toyotatimes.jp/en/toyota_news/1039.html
[^20]: Toyota Motor Corporation, "Lunar Cruiser Design Update: A newly designed 1/5 scale model will be exhibited at Expo 2025 Osaka," 31 March 2025. https://global.toyota/en/mobility/technology/lunarcruiser/20250331.html
[^21]: AmericaSpace, "Living on the Moon: Inside Artemis' Foundation Habitat," 13 January 2024. https://www.americaspace.com/2024/01/13/living-on-the-moon-inside-artemis-foundation-habitat/
[^22]: NASA, "Lunar Living: NASA's Artemis Base Camp Concept," 28 October 2020. https://www.nasa.gov/blogs/missions/2020/10/28/lunar-living-nasas-artemis-base-camp-concept/
[^23]: Astrobotic, "LunaGrid's Vertical Solar Array Technology Enters TVAC," 19 July 2024. https://www.astrobotic.com/lunagrids-vertical-solar-array-technology-enters-tvac/
[^24]: Astrobotic, "Astrobotic Awarded Lunar Power Study with VSAT-XL." https://www.astrobotic.com/astrobotic-awarded-lunar-power-study-with-vsat-xl/
[^25]: ANS Nuclear Newswire, "Nuclear power on the moon: What we're watching," 2 September 2025. https://www.ans.org/news/2025-09-02/article-7336/nuclear-power-on-the-moon-what-were-watching/
[^26]: Wikipedia (cross-reference), "PRIME-1." https://en.wikipedia.org/wiki/PRIME-1
[^27]: SatNews, "Blue Moon MK1: The 'Innovative, Affordable, and Expedited' Pivot for Artemis," 6 January 2026. https://satnews.com/2026/01/06/blue-moon-mk1-the-innovative-affordable-and-expedited-pivot-for-artemis/
[^28]: Payload Space, "SpaceX and Blue Origin Cargo Advance Work on Cargo Lunar Landers." https://payloadspace.com/spacex-and-blue-origin-cargo-advance-work-on-cargo-lunar-landers/
[^29]: ESA, "ESA's Moonlight programme: Pioneering the path for lunar exploration." https://www.esa.int/Applications/Connectivity_and_Secure_Communications/ESA_s_Moonlight_programme_Pioneering_the_path_for_lunar_exploration
[^30]: NASA Langley, "Help Wanted: Designers for NASA's Artemis Base Camp Cargo System." https://www.nasa.gov/centers-and-facilities/langley/help-wanted-designers-for-nasas-artemis-base-camp-cargo-system/
[^31]: NASA, "Moon to Mars Architecture White Papers — Lunar Surface Cargo," 2024. https://www.nasa.gov/wp-content/uploads/2024/06/acr24-lunar-surface-cargo.pdf
[^32]: NASA, "NASA Welcomes Gateway Lunar Space Station's HALO Module to US." https://www.nasa.gov/missions/artemis/nasa-welcomes-gateway-lunar-space-stations-halo-module-to-us/
