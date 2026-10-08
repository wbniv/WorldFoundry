# Sea anemones: locomotion, tentacle motion and surface appearance

Research saved **5 October 2026**, before preparing the poster and implementation plan.
This document records biological evidence separately from game design. The current
aquarium asset is labelled **bubble-tip anemone, Entacmaea quadricolor** in its generator.
Other species below provide comparisons, not automatic behavior rules for this animal.
Sources were read online; this is a literature synthesis, not original observation.

## The structures are tentacles

Sea anemones are animals. Their tentacles are flexible living tissue bearing
stinging-cell structures, rather than rigid spines. Muscles acting against fluid
pressure support extension, bending and contraction. The oral disc surrounds the
mouth; a column connects it to the pedal disc that attaches to the substrate.
[University of Hawaiʻi, Cnidaria](https://manoa.hawaii.edu/exploringourfluidearth/biological/invertebrates/phylum-cnidaria)
explains the fluid-supported body and contraction response. The
[cnidarian muscle review](https://pmc.ncbi.nlm.nih.gov/articles/PMC5253434/)
describes retraction, feeding and locomotion across polyps.

## Locomotion: attachment can change

[Watson et al. (2022), bubble-tip aquaculture](https://onlinelibrary.wiley.com/doi/10.1111/are.15786)
observed adult E. quadricolor relocation in reef tanks. Mean fractions of observation
days with movement varied from 27% to 44% among treatments; some individuals moved
on 60% of days. Those are daily occurrence measures, **not crawling velocities**.
The paper discusses light and nutritional conditions as influences on relocation;
water-flow preferences need further study. Detachment occurred in some animals,
including cut individuals. That does not establish a routine swimming gait.

[Robson (1976), pedal-disc locomotion](https://link.springer.com/chapter/10.1007/978-1-4757-9724-4_50)
describes the foot's alternating attachment and locomotor functions. Only the
publisher abstract was accessible: it supports the general mechanism, not a
numerical speed or a fully documented E. quadricolor stepping sequence.
The muscle review above also describes creeping, tentacle-assisted movement and
burrowing across different anemones. These strategies vary by species.

[Clarke, Davey & Aldred (2020)](https://link.springer.com/article/10.1186/s40850-020-00054-6)
found a secreted adhesive and distinctive pedal-disc structure in **Exaiptasia pallida**.
They did not find discharged spirocysts responsible for its pedal attachment.
This supports treating attachment as a biological process, with release and
reattachment. Its chemistry should not be claimed as proven for E. quadricolor.

The appropriate visual inference for the current bubble-tip is slow,
substrate-bound repositioning with a deforming foot and column, punctuated by
settled periods. A proposed moving adhesion front is an animation approximation;
the exact local attachment sequence requires closer species-specific footage.
No reliable physical crawling velocity for E. quadricolor was established here.

## Swimming is a separate, species-specific behavior

[Robson (1961), Stomphia coccinea](https://journals.biologists.com/jeb/article-abstract/38/2/343/13508/Some-Observations-On-the-Swimming-Behaviour-of-the?redirectedFrom=fulltext)
reports swimming triggered by particular predatory sea stars, involving column
elongation, potential detachment and coordinated muscles. The accessible abstract
does not justify importing this escape response into bubble-tip controls.
Similarly, the muscle review's examples of tentacle walking and burrowing belong
to particular taxa. A general poster can show this diversity with species labels.

## Tentacle motion has passive and active components

[Full et al., SICB 2013 field-motion abstract](https://sicb.org/abstracts/sea-anemone-tentacles-flutter-and-flap-in-water-flow-in-the-field/)
studied **Aiptasia diaphana** in turbulent flow. A prevailing current bent tentacles
downstream while waves caused flutter; wave-dominated conditions produced much
larger reversals. Longer tentacles showed larger excursions. The water and tissue
were coupled: there was shared environmental timing, not independently random
oscillation for every tentacle. This is a **conference abstract**, not a full
methods/results paper, and amplitudes should not be transferred numerically to
bubble-tips in sheltered reef crevices.

The muscle review describes active shortening, extension, prey handling and
protective retraction. A useful modeling distinction is therefore: the current
sets a shared direction and broad rhythm; local flexibility makes tips lag and
bend more than roots; active contractions change individual curves or the whole
crown. Treating all visible movement as water-driven misses active behavior.
This layered animation interpretation is an inference, not a measured dynamical
model. Small coherent motion is appropriate for the current species' sheltered
habitat; stronger whipping is a comparative example, not the default.

## Bubble-tip mesh and texture references

[Titus et al. (2024), original taxonomic treatment](https://publication.plazi.org/GgServer/xhtml/038187876444FFCC1BD2F8B1FB9475D8)
documents mixed bulbed and slender tentacles within one E. quadricolor, blunt
tips, dense crowns, and variable striation, speckling and translucency. Colors
include brown/tan, green and red/orange; tips can be magenta. The column lacks
verrucae and is usually concealed in a reef crevice on stable hard substrate.
This morphology supports irregular curved tentacles with selective near-tip
swelling, fine surface markings and a recessed foot. A bulb should form a
continuous fleshy silhouette, rather than a sphere visibly glued to a strip.

The biological cause of tip inflation and its short-term timing remain unresolved
in this research. Do not tie bubble shape mechanically to every button press.
Clownfish associations depend on species and setting; an aquarium association
does not automatically demonstrate a natural host pairing.

## Evidence strength and remaining work

| Topic | Evidence | What remains uncertain |
| --- | --- | --- |
| Bubble-tip morphology/habitat | Species-specific 2024 taxonomic treatment | Exact form/color to use is an art choice within observed variation. |
| Bubble-tip relocation | Species-specific aquaculture observations | Speed, attachment sequence, effects of this tank's current. |
| Water-driven flutter | Field measurements summarized in a conference abstract, another species | Bubble-tip stiffness, lag, frequency and amplitudes. |
| Muscle-driven retraction | University explanation and comparative review | Bubble-tip action timing under particular stimuli. |
| Pedal adhesion | Primary microscopy study of Exaiptasia | Exact bubble-tip adhesive chemistry and foot gait. |
| Escape swimming | Primary Stomphia paper abstract | Not a basis for routine bubble-tip swimming. |

Before calibrating an implementation, collect continuous E. quadricolor footage
of gentle flow, withdrawal/re-expansion, and crawling with a visible substrate.
Record source, playback acceleration, scale reference and elapsed real time.
Time-lapse relocation cannot supply real-time tentacle frequency. Until then,
all proposed speeds, response durations and animation amplitudes must be labelled
**game settings**, not measurements.

## Downstream use

The A3 poster and code plan must link back to this document. Keep biological
claims, cross-species analogies and proposed game settings distinguishable.
Original diagrams are schematics; they are not photographs or validated anatomy
reconstructions. Preserve these source links when updating either artifact.
