# Sea Stars species and animation reference

Research checked 2026-11-20. The game uses 10 world units per metre. Dimensions
below are selected display-animal sizes, not maximum-size claims. Population:
one player and nine residents. Live settings remain deferred (D11).

## Sources

- [Mueller, Bos, Graf & Gumanao 2011, *Aquatic Biology* 12:157–164](https://doi.org/10.3354/ab00326): measured mean locomotion on uniform substrate, **8.1 cm/min Linckia**, **18.8 cm/min Protoreaster**, **45.8 cm/min Archaster**. These are active movement rates, not time-averaged daily travel. Their maximum rates are higher. Specimens included Linckia 8–30 cm diameter, Protoreaster 4–28 cm and Archaster 2–10 cm.
- [Garm & Nilsson 2014, visual navigation in Linckia](https://doi.org/10.1098/rspb.2013.3011): arm-tip compound eyes and visually guided reef navigation. The raised leading tip and red eyespot are based on this anatomy; the A-button two-second reach is a game animation.
- [Bos et al. 2011, Archaster burrowing and habitat shifts](https://doi.org/10.1007/s00227-010-1588-0): sand burrowing is real. The game’s timed emergence and proximity-triggered fast burial are authored reactions, not measured biological latencies.
- [Kano et al. 2019, flexible coordination in Ophiarachna incrassata](https://pmc.ncbi.nlm.nih.gov/articles/PMC6923253/): actual species used in locomotor observations; arms coordinate rowing, with leading-arm changes. The game’s escape speed is a readability choice, not a measured species speed.
- [Western Australian Museum, Culcita novaeguineae](https://museum.wa.gov.au/online-collections/names/Culcita-novaeguineae/): thick pentagonal cushion, short arms, variable patch colours; reef flats and rubble substrate. An 8% ten-second vertical puff is deliberately stylized, not claimed biological respiration.
- [Reef Life Survey, Fromia milleporella](https://reeflife.org/species/fromia-milleporella/): photographed red porous sea star. [WoRMS taxonomy and distribution](https://www.marinespecies.org/aphia.php?id=213299&p=taxdetails) also records colour variation. The chosen red morph is not the only colour.
- [Smithsonian, Seagrasses, Phillips & Meñez 1988](https://repository.si.edu/server/api/core/bitstreams/67782105-af64-4627-9f3d-ea22208acdd7/content) and [SeagrassNet global identification guide](https://www.seagrassnet.org/downloads/seagrass_global_bioregion_photo_guide_2025.pdf): Thalassia hemprichii has ribbon-like, curved leaves, normally 10–40 cm long. Tufts here have 9–18 cm leaves and about 5 mm blade widths, selected for the tank’s scale.

## Export choices

| Species | Display diameter | Skin / silhouette | Movement in game |
|---|---:|---|---|
| Linckia laevigata | 18 cm | cobalt blue, long rounded arms; pale oral face with five grooves and central mouth | measured active speed ×30 = 4.05 cm/s; any arm may lead |
| Protoreaster nodosus | 20 cm | tan, thick triangular arms and raised dark knobs | measured active speed ×20 = 6.27 cm/s during travel; 20–60 s grazing pauses |
| Fromia milleporella | 8 cm | red with fine dark pores, short tapered arms | authored 0.9 cm/s target, slow fixed routes on the three rocks; no species-specific speed established |
| Archaster typicus | 11.2 cm | flattened grey-tan star, pale marginal plates | measured mean ×20 = 15.27 cm/s active speed ceiling; short travel and sand burial |
| Ophiarachna incrassata | 3.8 cm disc; 15 cm arms; ~34 cm extended span | small olive-green disc; long tapering arms with distinct S bends and curled tips | authored escape speed 6× player; two refuges, proximity reaction at 25 cm |
| Culcita novaeguineae | 14.4 cm | orange-brown cushion with irregular darker pattern | essentially stationary; stylized 8% vertical puff |

Speed multiplication, pauses, avoidance radii, five-plane glass traversal and
all scripted reaction deadlines are game design. Will explicitly approved
keeping the cushion puff and unsubstantiated exact reaction timings as stylized
animation/gameplay on 2026-11-20 ("sure"). Do not cite these timings as research.

The seed, routes, collider proxies and population are resolved at export. No
runtime type scan, collision raycast or SeaStarsSettings object is required.

## Brittle-star proportions and posture correction

The arms are articulated limbs rather than straight sea-star rays. [Matsuzaka et al. 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5399548/) used O. incrassata with 10–15 cm arms and observed aborally bent distal segments during locomotion. The selected model has a 3.8 cm disc and 15 cm free arms, with 16 joints per arm, asymmetric S bends, hooked tips and slightly lifted distal segments. The extended span is about 34 cm; a curled pose occupies less space. Hide and Row are authored clips in both the Blender master and the five-curve DFRM asset. The mesh’s straight skinning bind pose is not its displayed resting posture.
