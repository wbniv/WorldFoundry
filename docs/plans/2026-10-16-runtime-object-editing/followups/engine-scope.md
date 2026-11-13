# Engine follow-up scope proposed 13 November 2026

**Decision, 13 November:** Will selected "Device checks and proposals only".
Neither engine implementation is authorized in this follow-up run.

These changes are not part of the completed O4 migration scope. AGENTS.md requires
explicit permission before engine edits. Device acceptance work can proceed
independently.

## Bounded strings in the writable overlay

Add an OAD kind for fixed-capacity UTF-8 text slots, with an OAS declaration that
states the capacity. The compiler writes a terminated value into the actor
payload; layout tools and the runtime walker agree on its size and alignment.
The property adapter reads and validates the bounded slot, and Apply writes it
through the existing per-object transaction. Over-capacity or malformed values
fail before any write. Keep TV/phone controls and their existing text/path
validation, restoring the four bounded text/path examples in baseline.

Touch points: OAD definitions and parser, oas2oad, levcomp, Rust/C ABI layout
helpers, runtime OAD adapter, baseline OAS and generated level. Verify with mixed
numeric/string layouts, UTF-8 boundary cases, instance isolation, Apply/Cancel,
both forms, and Android ABI builds. Add a cross-language size/alignment/offset
check for the C++/Rust FFI struct: the earlier isolated-build black preview
showed that a stale struct definition must be caught explicitly. Shared XDATA_COPY strings remain immutable.
No legacy alias or parallel catalog representation is added.

## Editor Label as a first-class OAD field

Proposed approach: declare Editor Label in actor.inc as an export-only OAD
metadata field with zero actor-payload storage. Exporters discover it through the
schema; levcomp resolves it into the existing LevelObj label table and keeps the
current uniqueness checks. The runtime layout walker skips the metadata kind;
there is no Actor struct member and no shift in actor payload offsets. The type's
own descriptor indices change, so regenerate OADs and affected levels/scripts
and verify their field IDs together. Replace the special plain-custom-property
path with schema-driven authoring, preserving the text IFF spelling Editor Label.

Touch points: OAD definitions/parser, actor.inc, header generation, Blender
import/export, levcomp metadata resolution and the runtime layout walker.
Verify zero storage, unchanged numeric offsets, automatic/custom labels,
duplicate rejection, Blender round-trip, and text IFF compilation. This proposal
requires validation against the existing descriptor/header generators before
implementation; if zero-storage metadata cannot fit cleanly, bring back the
layout alternatives rather than silently adding an actor member.
