# Sea urchins: locomotion, spine movement and visual reference

Research saved 5 October 2026, before creating the poster and implementation plan. This is a separate project from the paused sea-anemone and generic-deformation work.

## Scope and species

The game currently calls its resident `sea_urchin` without specifying a species. Its purple, compact shape suggests a short-spined regular urchin. Use the purple sea urchin, *Strongylocentrotus purpuratus*, as the proposed visual reference; this is a design proposal, not an identification of the existing asset. It inhabits the eastern Pacific rocky coast and reaches about 7 cm test diameter. Its tube feet crawl and handle food; its spines articulate on ball-and-socket joints. [Monterey Bay Aquarium: purple sea urchin](https://www.montereybayaquarium.org/animals-the-ocean/animals-a-to-z/purple-sea-urchin).

Regular urchins have fivefold organization, visible in the test. This does not require every visible spine to have an identical counterpart or equal spacing. [Oregon Department of Fish and Wildlife: sea urchin biology](https://www.dfw.state.or.us/mrp/shellfish/commercial/urchin/life_history.asp).

## Locomotion: attachment and traction

Repeated tube-foot attachment and release let an urchin pull itself across a surface; spines also contribute to locomotion. Tube-foot discs use an adhesive/de-adhesive secretion system. They should not be animated as passive suction cups sliding over the floor. [Repeated Hyposalinity Pulses Immediately and Persistently Impair the Sea Urchin Adhesive System, 2024](https://academic.oup.com/icb/article/64/2/257/7623019).

The tube foot is a hydraulic, extensible organ with a stem and terminal disc. Research on *Paracentrotus lividus* identifies adhesive secretory structures and proteins. A controllable contact point and a changing stem shape are appropriate visual abstractions; a molecular simulation is unnecessary. [Pjeta et al., 2020: tube-foot adhesive secretions](https://doi.org/10.3390/ijms21030946).

Suggested animation interpretation: reach → attach → pull/support → detach → recover. During support, keep the disc fixed in world space while the body advances. Several contacts overlap; the illustrated sequence is an animation model, not a measured universal five-stage gait. Use actual travel to advance the walking cycle. Search/probing may continue while stopped, separately from the traction cycle. All-direction substrate movement fits a radial animal; mandatory fish-like steering and forward-only locomotion do not.

Righting requires coordinated feet and spines. Experiments on green urchins measured righting, locomotion and adhesion separately and found they respond differently to salinity changes. These are distinct abilities; a decorative spine cycle is not evidence of traction. [Moura et al., 2023: hyposalinity reduces coordination and adhesion](https://doi.org/10.1242/jeb.245750).

## Spines: rigid shafts, moving joints, held poses

Spine muscle changes orientation; the collagenous catch apparatus can change stiffness and maintain posture. Isolated catch-apparatus experiments on *Heterocentrotus mammillatus* support connective-tissue stiffness changes rather than attributing passive holding to muscle contraction alone. This supports explicit movement and hold intervals in animation. [Takemae and Motokawa, 2005](https://doi.org/10.2307/3593098).

In *Diadema setosum*, darkening evoked spine waving and catch-apparatus softening. Local touch produced movements of nearby spines toward the stimulated region. The study demonstrates nervous coordination between muscle and connective tissue. Its shadow reflex is species-specific evidence, not a requirement that a purple urchin wave every spine whenever the game's lighting changes. [Motokawa and Fuchigami, 2015](https://doi.org/10.1242/jeb.115972).

Model each visible spine as a shaft rotating around its basal joint. Adjacent spines can respond locally and then hold/recover; keep the test comparatively rigid. Gentle occasional orientation changes can make idle life visible. Continuous synchronized sinusoidal bending would misrepresent these mechanisms. No source here establishes a universal tilt angle, gait period, idle frequency or response duration; those remain game parameters pending species-matched footage.

## Mesh, texture and habitat implications

Separate the rigid test, articulated spines and soft tube feet visually. Use a rounded test with anatomical organization, basal tubercles, varied spine lengths and finer secondary spines. Tube-foot discs must remain distinguishable from sharp spine tips. Fine plate boundaries, pore hints, spine ridges and pigmentation can live in the texture; silhouette and pivot movement require geometry. Selective translucent feet are a rendering proposal, not a measured opacity claim.

The current plant level allows both freshwater and saltwater. An urchin should be presented in a marine habitat; freshwater must not be represented as suitable husbandry. Proposed resolution: use the saltwater variant for the urchin realism preview and settle the freshwater resident/control design before changing the shipped selector. This research does not authorize that product change. The salinity experiments above concern marine salinity reductions, not adaptation to freshwater.

## Current game evidence, read-only audit

| Item | Current source behavior | Consequence |
|---|---|---|
| Body and spines | `wflevels/aquarium_tanks/urchin.py`: ellipsoid plus 61 four-sided tapered fixed spines | Improve joints, silhouette and surface detail |
| Feet | `generate.py`: eight separate foot actors | Preserve a low actor cost; do not add one actor per spine |
| Traction phase | Actual displacement, but `abs(dx)+abs(dy)` | Use true distance or a direction-corrected equivalent; diagonal gait differs today |
| Contact placement | Each foot follows body position plus cyclic offset | No persistent world-space anchor during support |
| Movement | `plants_controller.fth`: direct X/Y input, normalized diagonal, filtered velocity, fixed substrate height | Retain slow crawl; improve contact and response continuity |
| Scene | Generated `aquarium_plants/actor-map.json`: 38 actors | Nine are body plus feet; scene cost must be separated from animal cost |
| Button A | Runtime generator delegates camera taps/settings holds to existing native plant settings | Preserve the current tap/hold behavior unless separately agreed |

## Evidence limits and next observation

This research combines identified regular-urchin studies. Species, stimulus and experiment are named rather than treating every echinoid as interchangeable. Before final animation tuning, inspect matched-species footage from side and underside: planted-disc stability, how many contacts overlap, basal spine tilt, idle holds and reversal. Do not infer real-world speed from game units or reuse another aquarium level's performance baseline.

The sources' indexed abstracts and aquarium descriptions were available during research; some full-text web requests were blocked by publisher/PMC access checks. No experimental spine-angle or timing values are claimed from inaccessible full text. The poster diagrams will be original schematic illustrations rather than traced photographs.
