# Discus fish — corrected brief

**Correction:** Will intended a discus, not the Malawi mbuna previously assumed. This section supersedes all conflicting model, texture and poster decisions below. The existing cichlid draft and poster are not the requested design and are reference for the abandoned approach only.

Build a three-dimensional discus with its characteristic tall, nearly circular, laterally compressed body, small mouth and eye, long dorsal and anal fins following the body contour, a narrow caudal peduncle, fan-shaped tail, and both paired pectoral and long pelvic fins. Use a specific documented discus reference and record source and proportions before modelling; check side, front and oblique views and actual engine export. The exact species or ornamental strain remains to be selected from references; do not label creative palette variations as distinct species.

Primary shape and markings reference: the side-view *Symphysodon aequifasciatus* photograph in [Kohda et al., PLOS ONE (2016), figure 1](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0154543). Use it to study the disc-shaped body, long dorsal and anal fins, head and tail; verify image reuse terms before reproducing it in the poster. Supplement with the [US Fish and Wildlife Service red discus account](https://www.fws.gov/sites/default/files/documents/Ecological-Risk-Screening-Summary-Red-Discus.pdf) for another side view and anatomy. The palette-only variants are creative colorways, not claims of species or strain accuracy.

Create at least twelve variations by palette changes alone, with one shared geometry, UVs, masks and markings; verify the texture indices remain identical. Rebuild the A3 poster around the finished discus and its palette gallery. Retain the planned editable source, reproducible exports, verification and model-making FAQ, and the requirement for explicit permission before any engine code changes. No new tank or menu entry is implied.

---

# Superseded cichlid draft and original plan

# Cichlid fish — model, palette variants and A3 poster

Date: 2026-11-22. Status: proposed; no assets built yet.

## Goal and design

Create a reusable, fully three-dimensional cichlid for the World Foundry aquarium, with many texture variations made **only by changing the palette**, and an A3 poster as a deliverable. “Cichlid” covers many different fish; this design is a stylised Lake Malawi mbuna-inspired fish, not a claim to reproduce a particular species. Final placement, population and controls are outside this request; provide a reviewable standalone asset and preview without changing existing tanks or menus.

The fish has a deep, laterally compressed oval body, blunt sloping forehead, small terminal mouth, large readable eye and defined gill cover. A long continuous dorsal fin rises from behind the head to the tail base; a short anal fin balances it below. Use a rounded, slightly notched fan tail, paired pectoral and pelvic fins on both sides. Build real thickness so head-on and three-quarter views read as fish. Show fin rays and overlapping scale hints in the texture; avoid exaggerated individual scale geometry. Use opaque fin surfaces and deliberate edge colors so the asset remains legible in the existing renderer.

Design for a neutral horizontal swimming pose, head to tail along the established aquarium fish axis. Separate or label body, tail and fins as needed by the existing asset pipeline, with shared root transforms and clean fin attachments. Aim initially for 500–1,500 triangles for the visible fish, subject to actual silhouette and export inspection; this is a target, not a performance promise. Reuse available fish animation and authoring conventions where suitable, with a gentle increasing body wave toward the tail and restrained paired-fin motion. Do not change engine code without separate discussion and explicit permission.

## One pattern, twelve palettes

Author one UV layout and one master indexed/color-region texture: dark back, mid-body, pale belly, five soft vertical bars, fin field, fin edge, eye and highlights. Keep the bars, scales, eyes, shading, masks, transparency/opacity, resolution and texel positions identical across variants. A deterministic palette table maps each master color index to its output color; export full textures if the current pipeline requires them. No hand repainting, different masks, UVs, geometry or material parameters between variants. Keep eye pupil and highlight readable in every palette. The names below describe creative colorways, not species identifications.

| Variant | Back / bars | Body | Belly | Fins / edge |
|---|---|---|---|---|
| Cobalt | navy | cobalt blue | ice blue | blue / pale cyan |
| Electric blue | deep indigo | bright blue | silver blue | azure / white |
| Yellow | umber | golden yellow | cream | gold / charcoal |
| Tangerine | deep rust | orange | peach | orange / cream |
| Coral | burgundy | coral red | pale peach | red / ivory |
| Violet | plum | violet | lavender | purple / pale lilac |
| Turquoise | deep teal | turquoise | pale aqua | teal / cream |
| Emerald | forest green | emerald | mint | green / pale yellow |
| Silver | charcoal | silver gray | near white | slate / white |
| Copper | dark brown | copper | sand | bronze / cream |
| Rose | dark wine | rose pink | pale pink | mauve / ivory |
| Pearl | slate | warm ivory | white | pearl / gray |

Choose final precise sRGB palette values during authoring and record them in a machine-readable manifest. Maintain sufficient contrast between bars and body and avoid hiding the eye or fin outline. Test the same light and camera for each variant. A contact sheet will show all twelve at identical scale and pose, labeled by colorway.

## Deliverables

- Editable model and texture sources, export/build script, and engine-consumable asset using the established aquarium pipeline; document paths, orientation, scale, triangle count, material and reproduction steps.
- Master indexed texture, palette manifest and twelve generated textures; one mesh and UV layout shared by every variant. Provide a reproducible palette-only verification comparing index assignments and alpha to the master, plus a visual contact sheet and side, front and three-quarter renders of the actual export.
- An **A3 landscape poster** (420 × 297 mm) with print-ready PDF, editable source and PNG preview. Feature a large annotated fish, anatomy, a labeled twelve-color palette gallery, a small UV/palette explanation, and concise sourced context about cichlids. Distinguish this stylised design from biological species identification. Include attribution and licensing for any external references, and keep type and labels readable at print size. Use original renders or appropriately licensed imagery. Check actual PDF page size and a print preview.
- A short README with build commands, asset inventory, palette mapping, sources and validation results. No assertion of device performance without measurement.
- A new quick FAQ at `docs/model-making-faq.md`, written after reviewing the existing documentation and completing this model and texture. Focus on making and exporting individual models: scale and axes, geometry and normals, UVs and texture conventions, palette variants, editable source, export, and checking the result in the engine. Link to existing authoritative guidance and use lessons verified during this work; identify unverified advice. Do not cover world or level construction.

## Work sequence and acceptance

- [ ] Inspect current aquarium asset generators, texture formats, renderer limits and animation path; select a compatible representation and document assumptions.
- [ ] Develop the fish silhouette and UVs; export and inspect actual geometry from side, front and oblique views. Verify normals, fin attachment, texture seams and animation at rest and maximum bend.
- [ ] Generate the twelve palettes deterministically from the same indexed master. Verify every output pixel derives from the corresponding source index and palette entry, with unchanged alpha and dimensions; render the contact sheet and inspect contrast.
- [ ] Build the poster and check its 420 × 297 mm page, print readability, source credits and agreement with the final model and palette names.
- [ ] After reading existing guidance and completing the model and texture, write the model-making quick FAQ; check that its instructions reflect the tested asset pipeline and do not expand into world building.
- [ ] Run the asset build and relevant checks; inspect the asset in the actual desktop renderer. If integrated into a runnable Chromecast build, freeze the APK and use the shared coordinator to capture and profile the actual result, reporting device and evidence. If that integration is unavailable, explicitly record it as unverified.

Any proposed engine change requires its own concrete proposal and Will’s explicit permission before editing. This plan authorizes asset, script and tooling work only; it does not prescribe a tank, add a menu entry, or authorize engine edits.

## Implementation progress, 2026-11-22

An initial procedural model, editable Blender/OBJ sources, twelve indexed palette textures, software previews and an A3 poster draft are in [the asset directory](../../wflevels/aquarium_cichlid/README.md) and [poster directory](../reference/cichlid-poster/). All twelve texture index arrays were checked identical; PDF page size was checked as A3 landscape. The 334-triangle draft is below the initial 500–1,500 triangle target. It still requires art refinement, animation, World Foundry export/cooking and actual engine verification; the poster also needs the planned anatomical annotations and sourced biological context. None of the implementation acceptance boxes above is marked complete on the basis of the draft alone.

## Model correction

The current draft does not convincingly resemble a cichlid and is superseded as a visual target. Rebuild the geometry using the published holotype photograph and measurements of *Metriaclima melissa* in [Stauffer and Konings (2023), figure 2 and table 1](https://ecosystems.psu.edu/research/labs/stauffer/publications/2010-present/geograph.pdf/@@download/file/geograph.pdf). Its reported 5–7 flank bars suit the shared palette constraint. Compare standard length, body depth, head length and eye placement against the specimen, with the tail excluded from standard length. Reconstruct the continuous dorsal fin, tapered caudal peduncle, fin rays and head from the reference; render side, front and oblique actual mesh views. The resulting model is inspired by this specimen, not a verified taxonomic reconstruction. Do not reuse the current poster as a final deliverable; regenerate it after the model is rebuilt.
