# Asian Arowana — A3 poster

Actual poster: [HTML](poster.html), [PDF](poster.pdf), [PNG preview](poster.png). A3 portrait: 297 × 420 mm. The poster is a finished research/design artifact; its swimming panel explicitly describes proposed game motion, not measured species kinematics.

## Photos and permission

Both photographs are used under **Creative Commons Attribution–ShareAlike 3.0 Unported**. Original files are retained; display resizing is applied, and the hero layout crops black margins without retouching the animal. This poster is distributed under that same license. The license applies to this poster, its diagrams and its photographs; it does not relicense the game or unrelated repository files.

| File | Author and original | Use |
|---|---|---|
| [fanghong-asian-arowana.jpg](assets/fanghong-asian-arowana.jpg) | Fanghong, 5 March 2006; [Honglongyu3.jpg, Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Honglongyu3.jpg); 2360 × 1220 pixels | Full side-view hero; roughly 225 dpi at its maximum print width. |
| [scoute-dich-asian-arowana.jpg](assets/scoute-dich-asian-arowana.jpg) | Scoute-dich / Baumann Productions, 24 October 2009; [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Asiatische_Gabelbart_(Scleropages_formosus).jpg); 3888 × 2592 pixels | Head detail, photographed at Naturkundemuseum Karlsruhe. Camera coordinates are an aquarium location, not a wild occurrence. |

License: [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). Full-fish and head photographs remain framed independently from the native SVG diagrams. No generated illustration is presented as a photograph or a game render.

## Research and map

Sources checked 2 October 2026:

1. [USFWS Ecological Risk Screening Summary, web version 16 December 2019](https://www.fws.gov/sites/default/files/documents/Ecological-Risk-Screening-Summary-Asian-Bonytongue.pdf): historical native-region reports, habitat, diet, maximum total length, introduced-record caveats. This is an institutional synthesis, not new fieldwork.
2. [Pouyaud, Sudarto & Teugels (2003), Cybium 27(4):287–305](https://horizon.documentation.ird.fr/exl-doc/pleins_textes/divers19-11/010033034.pdf): primary anatomical descriptions, parental mouthbrooding and ornamental history. It proposes splitting colour forms; the poster identifies that taxonomy differs across accounts and uses the broader name.
3. [Larson & Vidthayanon (2019), IUCN assessment DOI](https://doi.org/10.2305/IUCN.UK.2019-3.RLTS.T152320185A89797267.en): assessment link. The IUCN full page was unavailable to the browser during this session; Endangered and the 3 June 2019 assessment date were checked against the [current FishBase field-guide entry](https://fishbase.se/Fieldguide/FieldGuideSummary.php?c_code=458&genusname=Scleropages&speciesname=formosus). Do not claim this is a new 2026 assessment.
4. [NUS Singapore Biodiversity Records 2013:21](https://lkcnhm.nus.edu.sg/app/uploads/2017/04/sbr2013-021.pdf): juvenile Lower Peirce record, explicitly introduced.
5. [NParks AVS ornamental-fish businesses, updated 13 July 2026](https://avs.nparks.gov.sg/businesses/breeders/ornamental-fish-business/): current institutional context for CITES Appendix I, used in the plan rather than as poster legal guidance.

[Natural Earth 1:110m country boundaries](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_admin_0_countries.geojson) form the map basemap; [terms](https://www.naturalearthdata.com/about/terms-of-use/) place the data in the public domain. This low-resolution equirectangular regional map intentionally omits detailed rivers. Four approximate regional centres are in [locations.json](locations.json), based on named regions in source 1. They are not occurrence GPS coordinates, confirmed extant populations, or a comprehensive distribution boundary. Country labels provide orientation, not a claim of occupancy throughout each country. The taxonomic ambiguity around older Myanmar reports is not converted into a point or range polygon.

## Rebuild

Run `python3 docs/reference/asian-arowana-poster/make_poster.py` from any directory. It embeds the downloaded originals in `poster.html`, writes vector map/anatomy/motion diagrams and builds the plan mockup gallery. Printing is separate so the generator itself needs no browser/network access.

Print `poster.html` using headless Chrome with `--no-pdf-header-footer`, `--print-to-pdf=<absolute poster.pdf path>` and a fresh profile. Then run `pdftoppm -r 150 -png -singlefile poster.pdf poster` for the preview. Inspect PDF page count, A3 dimensions and the rendered page; inspect the browser for element overflow and failed images.

- [x] Sources, image authors and licenses recorded.
- [x] Photos downloaded at original resolution; HTML embeds them for offline viewing.
- [x] Original diagrams and geographically sourced map included.
- [x] Final PDF page geometry and visual inspection complete: one A3 page, embedded fonts, loaded images and no text/page overflow.

See the [tank implementation plan](../../plans/2026-10-02-asian-arowana.md).
