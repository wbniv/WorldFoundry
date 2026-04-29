# Investigation: Godot Remote Debugger Protocol

**Date:** 2026-04-29
**Status:** Complete
**Motivation:** WF's live-editor bridge needs naming conventions for game-state editing ops (Phase 2b+). Godot is the only other engine with an out-of-process TCP game-state editing bridge. Before naming Phase 2b ops we should understand what Godot decided, adopt what fits, and note where WF diverges.

---

## Background

Godot runs the game in a child process and communicates with the editor over TCP (default port 6007). This is architecturally identical to WF's bridge. The protocol covers both code-level debugging (breakpoints, stack frames) and game-state editing (live property writes, node spawn/remove, scene tree inspection). There is no published spec; the schema is read from source.

**Key source locations (Godot 4.x main branch):**

| File | Purpose |
|---|---|
| `core/debugger/remote_debugger.cpp` | Engine-side: receives ops, sends broadcasts |
| `core/debugger/remote_debugger_peer.cpp` | TCP framing, reconnect logic |
| `core/debugger/engine_debugger.cpp` | Dispatch table, profiler integration |
| `editor/debugger/editor_debugger_node.cpp` | Editor-side: sends ops, receives broadcasts |
| `editor/debugger/script_editor_debugger.cpp` | Script-level op handling |
| `scene/debugger/scene_debugger.cpp` | Scene-editing op handlers |

---

## Wire format

4-byte big-endian length prefix + Godot `Array` serialised as binary Variant. Each message is an `Array` whose first element is the op name string; subsequent elements are the payload.

WF uses newline-delimited JSON. Wire-level compatibility is not a goal; op naming is.

---

## Operations

### Editor → Engine

#### Execution control

| Op name | Payload | WF equivalent |
|---|---|---|
| `step` | — | `step {"frames":1}` |
| `next` | — | step over (Phase 4) |
| `out` | — | step out (Phase 4) |
| `continue` | — | `resume` |
| `break` | — | `pause` |
| `set_skip_breakpoints` | `bool` | — |
| `set_ignore_error_breaks` | `bool` | — |

#### Script debugging

| Op name | Payload | WF equivalent |
|---|---|---|
| `breakpoint` | `file, line, enabled` | Phase 4 `scene:set_breakpoint` |
| `reload_scripts` | — | Phase 4 script hot-swap |
| `reload_all_scripts` | — | Phase 4 |
| `evaluate` | `expression` | Phase 4 |
| `get_stack_dump` | — | Phase 4 |
| `get_stack_frame_vars` | `level` | Phase 4 |

#### Scene / live editing

| Op name | Payload | WF equivalent |
|---|---|---|
| `scene:request_scene_tree` | — | implicit in `BroadcastState` |
| `scene:inspect_objects` | `object_ids[]` | `scene:pick` (WF) |
| `scene:set_object_property` | `id, property_path, value` | `scene:set_prop` |
| `scene:set_object_property_field` | `id, field, value` | (sub-field write — Phase 2b) |
| `scene:live_node_prop` | `node_path, property, value` | `scene:set_prop` (path-based) |
| `scene:live_node_call` | `node_path, method, args[]` | not planned |
| `scene:live_create_node` | `parent_path, type, name` | `scene:spawn` (Phase 2b) |
| `scene:live_remove_node` | `node_path` | `scene:remove` (Phase 2b) |
| `scene:live_duplicate_node` | `node_path` | not planned |
| `scene:live_reparent_node` | `node_path, new_parent` | not planned |

#### Profiling

| Op name | Payload |
|---|---|
| `profiler:visual` | `enable, data` |
| `profiler:servers` | `enable` |
| `servers:memory` | `enable` |
| `servers:draw` | `enable` |

---

### Engine → Editor

#### Execution state

| Op name | Payload | WF equivalent |
|---|---|---|
| `debug_enter` | `can_continue, reason` | `{"op":"paused"}` |
| `debug_exit` | — | `{"op":"resumed"}` |
| `output` | `type, text[]` | `{"op":"log"}` |
| `error` | `callstack, error` | `{"op":"error"}` |

#### Script debug responses

| Op name | Payload | WF equivalent |
|---|---|---|
| `stack_dump` | `frames[]` | Phase 4 |
| `stack_frame_vars` | `locals, members, globals` | Phase 4 (mailboxes) |
| `evaluation_return` | `result` | Phase 4 |
| `breakpoint_source` | `file, line` | Phase 4 |

#### Scene broadcasts

| Op name | Payload | WF equivalent |
|---|---|---|
| `scene:scene_tree` | full tree of nodes with properties | `{"op":"state"}` per-actor |
| `scene:inspect_objects` | `{id: {property: value}}` | `{"op":"state"}` |
| `scene:live_node_path` | `id → node_path mapping` | idx↔name map (WF) |

#### Profiling broadcasts

| Op name | Payload | WF equivalent |
|---|---|---|
| (frame data) | `frame_time, process_time, physics_time, physics_frame_time` | `{"op":"perf"}` (Phase 4) |
| `servers:draw` data | draw call counts | Phase 4 |

---

## Key structural differences

**Object identity:** Godot uses `ObjectID` (integer) + `node_path` (string). WF uses `idxActor` (1-based integer from export order). These are equivalent in spirit but not interchangeable. WF has no node-path concept; the idx↔name map in Blender is the closest analogue.

**Scene tree vs actor list:** Godot's `scene:scene_tree` sends the full hierarchy with parent-child relationships. WF's `BroadcastState` sends a flat list of actor positions. WF has no hierarchy in the level IFF — actors are peers, not trees. No need to emulate `scene:scene_tree`.

**Property access:** Godot uses `property_path` strings that traverse the object graph (e.g. `"position:x"`). WF OAD fields can be addressed either way: as bare names (`"Speed"`) or as scoped paths (`"common.Speed"`, `"movebloc.maxVelocity"`) using the `LEVELCONFLAGCOMMONBLOCK` / `PROPERTY_SHEET_HEADER` block names as a prefix. Both are technically accurate. Scoped paths are preferred: they're unambiguous, make the block structure legible in the wire format, and read better. Use `"common.Speed"` not `"Speed"` for `scene:set_prop`.

**Method calls:** `scene:live_node_call` lets the editor call arbitrary methods on live objects. WF has no equivalent and it's not planned — mailbox writes cover the same use case more safely.

---

## Adoption decisions

| Godot op | WF decision | Rationale |
|---|---|---|
| `step` / `continue` / `break` | **Adopted as-is** (`step`, `resume`, `pause`) | Obvious verbs, no conflict |
| `scene:set_object_property` | **Adopt as `scene:set_prop`** | Shorter; WF already uses `key` not `property_path` |
| `scene:live_create_node` | **Adopt as `scene:spawn`** | "spawn" more natural in game context |
| `scene:live_remove_node` | **Adopt as `scene:remove`** | Symmetrical with spawn |
| `scene:inspect_objects` | **Adopt as `scene:pick`** | WF's pick is ray-based; name still fits "inspect an object" |
| `scene:scene_tree` | **Skip** | WF has no hierarchy; `state` broadcast is sufficient |
| `scene:live_node_call` | **Skip** | Not planned; mailboxes cover it |
| `scene:live_reparent_node` | **Skip** | No parent-child in WF actor model |
| DAP ops (breakpoints etc.) | **Phase 4 — adopt DAP not Godot** | DAP is editor-agnostic (VS Code); Godot's schema is tightly coupled to its script VM |
| Profiling broadcasts | **Phase 4** | `{"op":"perf"}` as planned |

---

## Resulting Phase 2b protocol additions

Based on this analysis, Phase 2b should add:

**Editor → Engine:**
```json
{"op": "scene:set_prop",  "idx": 3, "key": "common.Speed",         "value": 3.5}
{"op": "scene:set_prop",  "idx": 3, "key": "movebloc.maxVelocity", "value": 12.0}
{"op": "scene:spawn",     "template_idx": 5, "pos": [1.0, 0.0, 2.0]}
{"op": "scene:remove",    "idx": 7}
```

The `key` field uses dot-separated `block.field` notation matching the OAD sub-block structure (`LEVELCONFLAGCOMMONBLOCK` name + field name). Flat properties (no sub-block) use the field name alone.

**Engine → Editor:**
```json
{"op": "prop_ack",  "idx": 3, "key": "Speed", "value": 3.5}
{"op": "spawned",   "idx": 12, "template_idx": 5}
{"op": "removed",   "idx": 7}
```

The `spawn` op requires the template-based constructor system and is gated on Phase 2b COW infrastructure. `scene:set_prop` is the priority.

---

## Source references

- `scene/debugger/scene_debugger.cpp` — `parse_message()` function: definitive list of scene op names
- `editor/debugger/script_editor_debugger.cpp` — `_parse_message()`: editor-side handler
- `core/debugger/remote_debugger.cpp` — `_core_patch_status()` / `_send_profiling_frame_data()`
- Godot 4.x tag: `4.4-stable`
