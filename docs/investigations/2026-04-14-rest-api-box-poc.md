# Investigation: RESTful HTTP API for WF Engine — Box PoC

**Date:** 2026-04-14  
**Scope:** Proof-of-concept only. Minimal surface: create/recolor/resize/delete
axis-aligned boxes at runtime via HTTP, without touching the level format or the IFF
pipeline.

---

## What the API does

An HTTP server embedded in `wf_game` accepts JSON requests. A caller can:

1. **Create** a box at a given world-space position and size → receives an opaque ID.
2. **Recolor** a box by ID.
3. **Resize** a box by ID (any subset of l/w/h).
4. **Delete** a box by ID.

All coordinates and dimensions are in **meters** (WF standard unit).

---

## Routes

```
POST   /boxes                   Create a box
PATCH  /boxes/{id}/color        Change color
PATCH  /boxes/{id}/size         Change size (partial — any of l,w,h)
DELETE /boxes/{id}              Destroy the box
GET    /boxes/{id}              Read back current state (nice-to-have)
```

### POST /boxes

**Request body:**
```json
{
  "x": 0.0,
  "y": 1.0,
  "z": 0.0,
  "l": 1.0,
  "w": 1.0,
  "h": 1.0,
  "color": "#ff0000"
}
```
`color` is optional on creation (defaults to white `#ffffff`).

**Response `201 Created`:**
```json
{ "id": "a3f8c2d1" }
```
`id` is an 8-hex-digit opaque handle. Callers treat it as a string; the engine
maps it to an internal object index.

---

### PATCH /boxes/{id}/color

**Request body:**
```json
{ "color": "#00ff88" }
```
Color is CSS hex: `#rrggbb` or `#rrggbbaa` (alpha optional; defaults to `ff`).

**Response `200 OK`:**
```json
{ "id": "a3f8c2d1", "color": "#00ff88ff" }
```

---

### PATCH /boxes/{id}/size

At least one of `l`, `w`, `h` must be present. Omitted fields are unchanged.

**Request body:**
```json
{ "h": 2.5 }
```

**Response `200 OK`:**
```json
{ "id": "a3f8c2d1", "l": 1.0, "w": 1.0, "h": 2.5 }
```

---

### DELETE /boxes/{id}

No body. **Response `204 No Content`.**

---

### GET /boxes/{id}

**Response `200 OK`:**
```json
{
  "id": "a3f8c2d1",
  "x": 0.0, "y": 1.0, "z": 0.0,
  "l": 1.0, "w": 1.0, "h": 2.5,
  "color": "#00ff88ff"
}
```

---

## Error responses

| HTTP status | Meaning |
|-------------|---------|
| `400 Bad Request` | Missing required fields, invalid JSON, value out of range |
| `404 Not Found` | Unknown `id` |
| `409 Conflict` | Object exists but is in a state that rejects this mutation (rare) |
| `500 Internal Server Error` | Engine-side command queue overflow or crash |

Body: `{ "error": "human-readable message" }`.

---

## Embedded HTTP server

For a PoC, avoid a full framework. Two options:

### Option A — cpp-httplib (recommended)

Single-header MIT library. Embed directly in `wftools/wf_viewer/stubs/` or
`wfsource/source/`:

```
wftools/vendor/cpp-httplib-v0.x.y/httplib.h
```

Usage:
```cpp
#include "httplib.h"
httplib::Server svr;
svr.Post("/boxes", handle_create_box);
svr.listen("0.0.0.0", 8765);   // blocks — run on a dedicated thread
```

Pros: zero dependencies, one header, handles JSON body extraction, compiles with
`-std=c++17`. Cons: TLS requires OpenSSL (not needed for LAN PoC).

### Option B — Mongoose

Single C file + header, embeddable event loop. More control, but more boilerplate.
Overkill for this PoC.

**Decision: cpp-httplib.** The PoC is LAN-only; TLS is not required.

---

## Threading model

The game engine runs its main loop on the **main thread**. The HTTP server must run on
a **separate thread** so it doesn't block frame rendering.

Mutations from the HTTP thread must be applied on the main thread to avoid data races.
Use a **command queue**:

```cpp
// rest_api.hp
struct BoxCommand {
    enum class Type { Create, Recolor, Resize, Destroy };
    Type        type;
    uint32_t    id;       // 0 = allocate new
    float       x, y, z; // Create only
    float       l, w, h; // Create / Resize (NaN = unchanged for Resize)
    uint32_t    color;    // RGBA packed, Create / Recolor
};

// Thread-safe queue: HTTP thread pushes, game thread drains each frame.
void RestApi_Push(BoxCommand cmd);
bool RestApi_Pop(BoxCommand& out);   // non-blocking
```

Game loop calls `RestApi_Pop` once per frame (after input, before physics) and
applies pending commands. Response is written back via a separate
`std::promise<Result>` stored alongside the command. HTTP thread blocks on the
future; game thread fulfils the promise after applying the command.

```
HTTP thread                    Game thread (main loop)
──────────                     ─────────────────────
POST /boxes arrives
  → push BoxCommand + promise
  → future.get()  ←────────── game drains queue
                               applies command
                               fulfils promise → { id }
  ← 201 Created { id }
```

Queue is protected by a `std::mutex` + `std::condition_variable` (or a lock-free
ring buffer for v2).

---

## Object ID scheme

```cpp
static std::atomic<uint32_t> gNextBoxId{1};

uint32_t allocate_id() {
    return gNextBoxId.fetch_add(1, std::memory_order_relaxed);
}
```

IDs are monotonically increasing unsigned 32-bit integers. Serialised as 8 hex digits
in JSON (`"a3f8c2d1"`). The engine maintains a
`std::unordered_map<uint32_t, BoxRecord>` mapping IDs to internal state.

IDs are never reused within a session (prevents accidental resurrection via stale ID).

---

## What a "box" is in the engine

For the PoC, a box is a **procedural renderable + AABB collider** created at runtime,
not loaded from IFF. Two implementation strategies:

### Strategy A — Synthesised BaseObject (preferred)

Allocate a minimal `BaseObject`-derived instance in the running room's object list.
Give it:
- A position (world-space `x,y,z` from the API call).
- A renderable component: 12-triangle box mesh generated from `l,w,h` at creation
  time, rebuilt on resize. Color = vertex color or a flat material.
- A kinematic AABB collider (no physics response — PoC boxes are static obstacles).

This hooks into the existing render and collision pipeline with minimal new code.

### Strategy B — Debug overlay (simpler, zero physics)

A parallel `std::vector<BoxRecord>` outside the normal object system. Each frame,
render boxes using immediate-mode GL calls (8 `glVertex3f` calls per box, no VBO).
Zero integration with physics or the object factory.

**Decision for PoC: Strategy B.** No risk of corrupting the object system; fastest
to implement. Promote to Strategy A when the PoC is validated.

---

## Color format

Internal representation: `uint32_t` packed RGBA (`0xRRGGBBAA`).

API accepts CSS hex:
- `"#rrggbb"` → alpha defaults to `0xff`.
- `"#rrggbbaa"` → explicit alpha.

Parse on the HTTP thread before enqueueing; reject malformed strings with `400`.

---

## Build integration

`WF_REST_API` compile-time flag (default off), analogous to `WF_JS_ENGINE`:

```bash
WF_REST_API="${WF_REST_API:-0}"   # 0 = off (default), 1 = embed HTTP server
```

When on:
- Adds `-DWF_REST_API -I"$VENDOR/cpp-httplib-v0.x.y"` to `CXXFLAGS`.
- Compiles `wftools/wf_viewer/stubs/rest_api.cc`.
- Links nothing extra (cpp-httplib is header-only).

Server starts automatically at game boot, listening on `127.0.0.1:8765` (LAN PoC;
restrict to loopback by default, make host/port configurable via env vars
`WF_REST_HOST` / `WF_REST_PORT`).

---

## New files

```
wftools/vendor/cpp-httplib-v0.x.y/
  httplib.h                         — vendored, header-only

wftools/wf_viewer/stubs/
  rest_api.hp                       — BoxCommand struct, push/pop API
  rest_api.cc                       — HTTP server thread, route handlers,
                                      command queue, ID allocator
```

Modify:
- `wftools/wf_engine/build_game.sh` — `WF_REST_API` flag, conditional compile.
- Main game loop (likely `wfsource/source/game/main.cc` or equivalent) — call
  `RestApi_DrainQueue()` once per frame; call `RestApi_Shutdown()` on exit.

---

## Example session (curl)

```bash
# Create a 2×1×3 red box at origin
curl -s -X POST http://localhost:8765/boxes \
  -H 'Content-Type: application/json' \
  -d '{"x":0,"y":0,"z":0,"l":2,"w":1,"h":3,"color":"#ff0000"}' \
  | jq .
# → { "id": "00000001" }

# Make it taller
curl -s -X PATCH http://localhost:8765/boxes/00000001/size \
  -H 'Content-Type: application/json' \
  -d '{"h":6}' | jq .
# → { "id": "00000001", "l": 2.0, "w": 1.0, "h": 6.0 }

# Recolor
curl -s -X PATCH http://localhost:8765/boxes/00000001/color \
  -H 'Content-Type: application/json' \
  -d '{"color":"#0044ff"}' | jq .

# Delete
curl -s -X DELETE http://localhost:8765/boxes/00000001
# → 204 No Content
```

---

## Event generation and playback scripts

Two Python scripts live in `scripts/rest_box_demo/`:

---

### `generate_events.py` — produce a demo event sequence

Generates a JSON file of timestamped REST calls — a mix of box creations and
deletions at random positions, sizes, and colours. The output is a replay file, not
live HTTP traffic, so it can be inspected and edited before playback.

```
scripts/rest_box_demo/
  generate_events.py    — produce events.json
  playback.py           — replay events.json against a live server
  events.json           — example output (checked in as a sample)
```

**Usage:**
```bash
python3 scripts/rest_box_demo/generate_events.py \
  --count 50 \
  --seed 42 \
  --out events.json
```

**Flags:**
| Flag | Default | Meaning |
|------|---------|---------|
| `--count N` | 50 | Total number of events (creates + deletes combined) |
| `--seed S` | random | RNG seed for reproducible sequences |
| `--max-live N` | 10 | Maximum boxes alive at once; a delete is forced when exceeded |
| `--size-min F` | 0.5 | Minimum dimension for any of l/w/h (meters) |
| `--size-max F` | 5.0 | Maximum dimension for any of l/w/h |
| `--out FILE` | `events.json` | Output path |

**Event mix logic:** the generator maintains a simulated pool of live box IDs. At
each step it randomly picks `create` (60% weight) or `delete` (40% weight, only when
at least one box is alive). When `--max-live` is reached, it forces a delete.
Positions are uniform-random within a configurable world cube (default ±10 m on each
axis). Colors are chosen from a small palette so the visual result is legible.

**Output format: Postman Collection v2.1**

The generated file is a valid **Postman Collection** (schema v2.1.0) and can be
imported directly into Postman for manual exploration. The playback script reads the
same file.

Timing between requests is stored in each item's `description` field as a
`x-playback-t` tag — a plain-text annotation the playback script parses; Postman
ignores it. The `ref` label (used by the playback script to track which
server-assigned `id` belongs to each created box) lives there too.

```json
{
  "info": {
    "name": "WF Box Demo",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Create box_01 — red tall box",
      "description": "x-playback-t: 0.000\nx-playback-ref: box_01",
      "request": {
        "method": "POST",
        "header": [{ "key": "Content-Type", "value": "application/json" }],
        "body": {
          "mode": "raw",
          "raw": "{\"x\":2.1,\"y\":0.0,\"z\":-1.4,\"l\":1.2,\"w\":0.8,\"h\":3.0,\"color\":\"#e05050\"}",
          "options": { "raw": { "language": "json" } }
        },
        "url": {
          "raw": "http://{{wf_host}}:{{wf_port}}/boxes",
          "protocol": "http",
          "host": ["{{wf_host}}"],
          "port": "{{wf_port}}",
          "path": ["boxes"]
        }
      }
    },
    {
      "name": "Create box_02 — blue small cube",
      "description": "x-playback-t: 1.200\nx-playback-ref: box_02",
      "request": {
        "method": "POST",
        "header": [{ "key": "Content-Type", "value": "application/json" }],
        "body": {
          "mode": "raw",
          "raw": "{\"x\":-3.0,\"y\":0.0,\"z\":0.5,\"l\":0.5,\"w\":0.5,\"h\":0.5,\"color\":\"#5080e0\"}",
          "options": { "raw": { "language": "json" } }
        },
        "url": {
          "raw": "http://{{wf_host}}:{{wf_port}}/boxes",
          "protocol": "http",
          "host": ["{{wf_host}}"],
          "port": "{{wf_port}}",
          "path": ["boxes"]
        }
      }
    },
    {
      "name": "Delete box_01",
      "description": "x-playback-t: 2.500\nx-playback-ref: box_01",
      "request": {
        "method": "DELETE",
        "header": [],
        "url": {
          "raw": "http://{{wf_host}}:{{wf_port}}/boxes/{{box_01}}",
          "protocol": "http",
          "host": ["{{wf_host}}"],
          "port": "{{wf_port}}",
          "path": ["boxes", "{{box_01}}"]
        }
      }
    },
    {
      "name": "Recolor box_02 — green",
      "description": "x-playback-t: 3.100\nx-playback-ref: box_02",
      "request": {
        "method": "PATCH",
        "header": [{ "key": "Content-Type", "value": "application/json" }],
        "body": {
          "mode": "raw",
          "raw": "{\"color\":\"#50e080\"}",
          "options": { "raw": { "language": "json" } }
        },
        "url": {
          "raw": "http://{{wf_host}}:{{wf_port}}/boxes/{{box_02}}/color",
          "protocol": "http",
          "host": ["{{wf_host}}"],
          "port": "{{wf_port}}",
          "path": ["boxes", "{{box_02}}", "color"]
        }
      }
    },
    {
      "name": "Resize box_02 — taller",
      "description": "x-playback-t: 3.800\nx-playback-ref: box_02",
      "request": {
        "method": "PATCH",
        "header": [{ "key": "Content-Type", "value": "application/json" }],
        "body": {
          "mode": "raw",
          "raw": "{\"h\":2.0}",
          "options": { "raw": { "language": "json" } }
        },
        "url": {
          "raw": "http://{{wf_host}}:{{wf_port}}/boxes/{{box_02}}/size",
          "protocol": "http",
          "host": ["{{wf_host}}"],
          "port": "{{wf_port}}",
          "path": ["boxes", "{{box_02}}", "size"]
        }
      }
    }
  ],
  "variable": [
    { "key": "wf_host", "value": "localhost" },
    { "key": "wf_port", "value": "8765" }
  ]
}
```

URL templates use Postman's `{{variable}}` syntax. `{{wf_host}}` and `{{wf_port}}`
are collection-level variables (override them in a Postman environment). ID variables
like `{{box_01}}` are populated at run time by the playback script (or via a
Postman pre-request script when running manually inside Postman).

The playback script substitutes `{{box_NNN}}` with the server-assigned `id` returned
by the corresponding `POST /boxes` response, tracking the mapping via `x-playback-ref`.

---

### `playback.py` — replay events against a live server

Reads `events.json` and issues the corresponding HTTP requests to the running
`wf_game` REST API, with timing scaled by a speed multiplier.

**Usage:**
```bash
python3 scripts/rest_box_demo/playback.py \
  --file events.json \
  --speed 1.0 \
  --host localhost \
  --port 8765
```

**Flags:**
| Flag | Default | Meaning |
|------|---------|---------|
| `--file FILE` | `events.json` | Event sequence to replay |
| `--speed F` | `1.0` | Playback speed multiplier. `2.0` = twice as fast; `0.5` = half speed; `0` = instant (fire all events with no delay) |
| `--host HOST` | `localhost` | REST API host |
| `--port N` | `8765` | REST API port |
| `--loop` | off | Repeat the sequence indefinitely until Ctrl-C; resets all live boxes between loops |

**Timing implementation:**

The script computes `sleep_duration = (event[i+1].t − event[i].t) / speed` between
consecutive events. With `--speed 0`, all sleeps are skipped and events fire as fast
as the server can accept them (useful for stress testing the command queue).

```python
for i, event in enumerate(events):
    dispatch(event, live_ids)          # issues the HTTP request
    if i + 1 < len(events) and args.speed > 0:
        gap = events[i+1]["t"] - event["t"]
        time.sleep(gap / args.speed)
```

`live_ids` is a dict mapping `ref` → server-assigned `id` string, populated as
`create` responses arrive and cleared on `delete`.

**Dependencies:** Python 3.9+, `requests` library (`pip install requests`). No other
deps.

---

## Open questions / follow-ups

- **Port conflicts:** default `8765` — make it a `WF_REST_PORT` env var override.
- **Strategy A promotion:** once PoC is validated, replace debug-GL boxes with proper
  BaseObject instances so they participate in physics and the normal render pipeline.
- **Authentication:** none for PoC (LAN-only, loopback). Add a static bearer token
  (`WF_REST_TOKEN` env var) before any non-loopback exposure.
- **Batch endpoint:** `POST /boxes/batch` accepting an array of create commands —
  avoids round-trip overhead when populating a scene programmatically.
- **Position change:** the spec doesn't include moving a box after creation. Add
  `PATCH /boxes/{id}/position` when needed.
- **Persistence:** boxes created via REST exist only for the session — they are not
  written back into `cd.iff`. A follow-up could serialise the box list to a sidecar
  JSON file that gets loaded on next game start.
