# OAS/OAD editor rendering audit

Date: 2026-10-06. Source audit of Blender, wf-edit and the runtime form.

## Finding

The runtime shares Rust schema normalization and strict scalar validation with
authoring tooling, but does not share their widget rendering or complete editing
behavior. Its initial implementation supports a small scalar subset with simple
fallbacks; those fallbacks lose meaningful `showAs` presentation.

The authoring editors also differ. Blender often shows enums as visible buttons;
wf-edit originally used dropdowns even for radio hints. The approved update now
uses highlighted choice buttons for that hint. Neither implements every legacy
type/hint exactly. Copying either renderer wholesale would retain gaps.

## Observed behavior

| Feature | Blender | wf-edit | Runtime TV / phone |
|---|---|---|---|
| Metadata | Shared Rust schema through Python | Own OAD reader, correlated to document fields | Shared Rust-normalized cooked catalog |
| Plain integer | Blender property | InputInt; Enter commits; range clamp | TV numeric keypad; phone bounded text; shared validation |
| Fixed point | Blender numeric property | InputFloat; slider hint uses SliderFloat | TV keypad/arrow step; phone text/range; scale-aware slider audit remains |
| Integer slider | Plain numeric property; enums become buttons | Plain Int still uses InputInt | Initial TV only stepped arrows; approved update draws track/thumb and labelled stops. Phone already renders range for show=2 |
| Enum/dropdown | Button row; hints 4/5 with >3 choices use two-column grid | BeginCombo for all enums | Initially one label on TV, dropdown on phone unless slider |
| Enum/radio | Selected/depressed buttons | Previously dropdown; new show=5 branch renders highlighted buttons | show=5 renders highlighted single-choice buttons on TV and phone, without circles; device verification pending |
| Boolean | Checkbox-style operator; special two-choice enum handling | Checkbox | TV left/off, right/on; phone checkbox for Bool; enum radio is separate |
| RGB colour | Hex label and colour picker | ColorEdit3 and hex | Palette-first TV/phone UI with original/preview, recent colours, Custom HSV and exact RGB/hex entry. Packed integer storage unchanged; local tests pass; full device colour-edit acceptance pending |
| Object reference | Searchable scene picker; missing-target warning | Editable reference text | Read-only reference; no typed target picker |
| File/mesh reference | Path text plus filtered browser | Editable path; Browse disabled | Read-only; no cooked-asset picker |
| Text | Blender text property | Text input; multiline/Notes path has documented caveats | Android native EditText/system IME for text and numbers; custom key grids removed. Phone native text keyboard. Standalone desktop runtime currently uses connected browser entry; physical text-event integration remains pending |
| Annotation/XData | Ignored annotation surfaced by normalizer | Some annotations hidden; shipped Notes multiline path documented dormant | Explicitly bound Notes become multiline string overlays: native Android multiline editor, phone textarea. Actual TV IME newline acceptance pending. Converted/script XData stays outside configuration |
| Vector/Euler/box | Native scene properties plus scalar schema fields | Component widgets for document VEC3/EULR/BOX3 | No grouped vector/Euler/box catalog widget |
| Sections/groups | Panel structure | Section/group controls | TV section rail but skips group labels; phone heading rows |
| Hidden fields | Panel skips | Dispatcher skips | Cooker omits, so effective-value readback cannot retrieve them through this catalog |
| Commit | Blender object properties; separate exporter/live bridge | Document transactions, CRDT/live engine propagation | Per-instance draft, Apply/Cancel, revision/session/generation checks, Forth effective reads |

The earlier claim that both TV and phone lost growth-speed's slider hint was
too broad: the phone already honored it. TV did not. Growth speed briefly used
INT32 / RADIOBUTTONS for comparison, then Will selected SHOW_AS_SLIDER. Final
speed is a seven-stop visible slider preserving values 0–6 and rate mapping.
Water type keeps SHOW_AS_RADIOBUTTONS metadata, presented as highlighted choices
without a literal radio circle. Blender already uses this style; wf-edit, TV and
phone now match it.
Choice rendering is host-specific implementation, not a shared wf-edit widget.

Will's follow-up requires finishing the **Enum/dropdown** row on TV, phone and
the authoring editors. Target highlighted choice buttons, with hints 4/5 and
more than three choices arranged in two columns; retain labelled sliders for
slider hints. The initial label/dropdown fallbacks in the table are historical
observations, not the completion target. Shared policy, navigation rules and
actual TV/phone/editor acceptance are specified in the
[runtime plan](../plans/2026-10-06-runtime-oas-oad-object-editor.md#finish-enumdropdown-controls-on-tv-phone-and-authoring-editors).

## Visibility filtering and known usage

Apply visibility and semantic eligibility before counting a missing widget.
`SHOW_AS_HIDDEN` fields need omission and, where required, retention/readback
checks; they do not need visible controls. A disabled conditional field is not
universally hidden: evaluate the states that can enable it. Likewise, one
host skipping a descriptor does not establish that its intended presentation
is hidden in every host.

A binary inventory of the 43 checked-in `wfsource/source/oas/*.oad` files and
`wflevels/aquarium_plants/settings.oad` found the following. Counts include
repeated fields from common blocks, not unique property definitions. This is
known shipped-descriptor usage, not a claim about every possible OAS schema.

| Case | Known usage | Treatment in the review/gallery |
|---|---|---|
| Compiler flags and common-block markers | All 355 occurrences have `showAs=HIDDEN`: NoInstances, Room, CommonBlock, EndCommon, ExtractCameraNew, ExtractLight and Shortcut | Exclude from visible-widget gaps and runtime configuration rows; audit authoring/export semantics and omission |
| Generated slope coefficients | 144 hidden Fixed32 entries, `slopeA`…`slopeD`; the same inventory also has 1,692 visible Fixed32 entries | Exclude these generated fields from visible slider/numeric requirements; retain visible fixed-point coverage and hidden omission checks |
| Light colour/direction components | Hidden component declarations in `light.oas` are commented out | Do not count commented declarations as active widget examples; this does not exclude visible RGB controls or document transforms |
| RGB colour | 69 Int32/COLOR entries, including camera fog and background colours | Keep the visible colour-widget gap; these examples are not explicitly hidden, though some have enable conditions |
| Object/file/class references | 360 object references, 242 filenames and 6 class references; none use HIDDEN | Keep visible reference behavior in scope; conditional references must be tested in an eligible state |
| Annotation/XData | 37 Notes and one test String use XDATA_IGNORE with non-hidden hints; 43 other XData entries have conversion actions | Separate annotation behavior from converted/script data. wf-edit skips shipped N_A Notes, but Blender surfaces annotations; do not classify all annotations as hidden. Converted/script data stays outside runtime configuration |
| Vector/Euler/box | 71 object-reference descriptors carry the VECTOR modifier; these are not scalar X/Y/Z triplets. wf-edit also handles document VEC3/EULR/BOX3 fields independently of OAD | Keep document-transform behavior distinct from a proposed grouped scalar runtime widget. Do not claim a shipped scalar-vector gap from hidden light components or reference modifiers |
| Unused type/hint combinations | No entries for narrow numeric storage, camera/light references or mesh-name descriptors in this inventory | Mark proposed examples as synthetic compatibility coverage, rather than missing controls required by known shipped examples |

The Observed behavior table describes renderer capabilities, including fallback
paths. Its rows are not automatically runtime implementation requirements.
Retain historical observations even when a case is filtered from the visible
gallery, and record the exclusion reason. For annotations, runtime retention
must be an explicit decision because XDATA_IGNORE produces no actor binary
bytes; an authoring text box alone does not imply a runtime editable setting.

## Sharing and remaining work

Reuse schema parsing, order/IDs, widths/scales, choice labels, constraints and
validation fixtures. Define a shared presentation policy mapping type plus hint
to an abstract control family, then render through host-specific widgets. Enum
radios, dropdowns and labelled sliders must remain distinct despite integer
storage. Do not import wf-edit or ImGui into the game.

Keep layout, focus, scrolling, accessibility and input local. Authoring
document/CRDT transactions remain separate from runtime instance transactions.
Equivalent values and constraints do not imply identical mutation capabilities.

- [ ] Define a tested type/`showAs` presentation policy; runtime dispatch is currently local.
- [ ] Finish generic enum/dropdown choice rows and two-column grids across TV, phone, wf-edit and Blender; verify actual displays and interaction before marking complete.
- [ ] Add visible TV sliders and audit fixed-point min/max/step conversion on phone.
- [x] Implement RGB UI through the approved scope, preserving packed values and existing transactions; local UI/browser tests pass, actual device acceptance remains.
- [ ] Design vector widgets through separately approved scope, preserving atomic typed edits.
- [ ] Design cooked-asset and typed-reference pickers with lifetime checks; retain read-only fallbacks meanwhile.
- [x] Replace custom Android text/numeric grids with the system editor/IME; native callbacks and phone text/Notes round trips pass local tests. Launch/resume passes on cast1; the reviewed coordinator update is deployed, but actual Gboard entry is blocked by device connection/recovery failures.
- [ ] Connect standalone desktop runtime text events/IME; existing browser text entry works. No custom on-screen keyboard fallback is requested.
- [ ] Render TV group labels and verify section navigation with an all-enum section.
- [ ] Separate hidden retention from visibility when effective readback is required.
- [ ] Audit conditional enable expressions and original metadata retention; do not claim full legacy form parity.
- [ ] Use the baseline pair-coverage fixture to verify gaps; numeric fallbacks do not count as finished widgets.

## Source anchors

- [Blender](../../wftools/wf_blender/panels.py): `_draw_field`.
- [wf-edit](../../engine/wf_edit/property_panel.cc): `WidgetFor` / `RenderProperties`. Its header's read-only wording is stale; renderer commits edits.
- [Shared normalization](../../wftools/wf_attr_schema/src/lib.rs): `classify` / `field_layout`.
- [Catalog cooker](../../scripts/build-object-properties.py): `KINDS` / `catalog`.
- [Runtime input](../../engine/runtime_property_form.cpp), [TV](../../wfsource/source/game/runtime_property_ui.cc), [phone](../../wfsource/source/hal/phonepad/controller.html).
- [OAS macros](../../wfsource/source/oas/types3ds.s), [descriptor codes](../../wfsource/source/oas/oad.h).

Related: [runtime plan](../plans/2026-10-06-runtime-oas-oad-object-editor.md),
[baseline gallery](../plans/2026-10-05-world-foundry-baseline.md).


### Runtime colour picker replacement (2026-10-06)

The runtime RGB control now uses the selected palette-first design, with Custom HSV editing and exact RGB/hex entry. Its `BUTTON_INT32 / SHOW_AS_COLOR` representation remains packed RGB; no alpha channel was added. Android text dialogs and phone fields have explicit contrast colours. See the [replacement plan and actual captures](../plans/2026-10-06-runtime-colour-picker.html) for verified behaviour and remaining Chromecast interaction/profiling acceptance. Existing wf-edit/Blender colour widgets are retained.
