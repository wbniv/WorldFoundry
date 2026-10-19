---
name: OAD property structure is hierarchical
description: OAD properties are NOT flat; sub-blocks give natural dot-path scope for bridge protocol
type: project
originSessionId: 74264ee8-0dd9-4769-aa6d-89d5e8ac4009
---
OAD schemas use `LEVELCONFLAGCOMMONBLOCK(name)` and `PROPERTY_SHEET_HEADER(...)` to define named sub-structs. Both bare field names (`Speed`) and scoped paths (`common.Speed`, `movebloc.maxVelocity`) are technically accurate, but scoped is preferred — unambiguous, readable, and consistent with Godot's dot-path convention. Flat is not preferred.

**Why:** Sub-block structure is real and legible; scoped paths make block membership explicit in the wire format.

**How to apply:** Use `"key": "common.Speed"` style in `scene:set_prop` (Phase 2b). Aligns with Godot's property path convention.
