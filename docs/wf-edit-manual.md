# `wf-edit` — World Foundry collaborative level editor: user manual

**Applies to:** `wf-edit` v1 (Linux/X11), as of 2026-05-21.
**Audience:** level designers and engine developers running the editor.

`wf-edit` is a standalone desktop application that **embeds the World Foundry game
engine** so you can edit a level and *see the change immediately* in a live 3D
viewport — no `.blend` → `.lev` → `.iff` → reload round-trip per tweak. It is built
on [Dear ImGui](https://github.com/ocornut/imgui) + [GLFW](https://www.glfw.org/),
and it represents the level as a [Yrs](https://github.com/y-crdt/y-crdt) CRDT document
(`wfcrdt::Doc`) so multiple designers can eventually edit the same level concurrently.
It also has Zoom/Skype-style **voice + video calling** built in, so collaborators can
see and hear each other without leaving the tool.

> The full design rationale lives in the
> [collaborative level editor design doc](investigations/2026-05-18-collaborative-level-editor-design.md).
> This manual is the *how-to-use-it*; that doc is the *why*.

---

## What works today (v1 scope)

| Capability | State |
|---|---|
| Open a level and render it live in an embedded viewport | ✅ |
| Open a text `.lev`, a compiled binary `.iff`/`.lvl`, or a level from a `cd.iff` archive | ✅ (binary decompiled on load; see [limitations](#known-limitations)) |
| Outliner: list every actor (read from the CRDT `Doc`) | ✅ |
| Properties: every field of the selected actor, with the right widget per type | ✅ |
| Edit a field → it commits to the `Doc` | ✅ |
| Edit Position / Orientation / a movement field → the **viewport updates live** | ✅ (subset — see [Live viewport preview](#live-viewport-preview)) |
| Duplicate / delete actors | ✅ (live for templated actors; otherwise on reload) |
| Save back to `.lev`; compile `.lev` → `.iff` | ✅ |
| Voice + video calling between editor instances in the same room | ✅ (LAN, Linux) |
| Real-time multi-user co-editing over a network (presence, relay, chat, disk persistence) | ✅ (WebSocket relay; only at-rest **BYOK** snapshot encryption is deferred — see [Known limitations](#known-limitations)) |

**Platform:** Linux/X11 only in v1. The editor adopts an existing GLX context; Wayland
and mobile hosts are v2+. `wf-edit` builds **only** when the engine is configured with
`WF_ENABLE_EDITOR=ON`; a shipped game build carries none of the editor stack.

---

## Building `wf-edit`

The editor is gated behind `WF_ENABLE_EDITOR` and built as a **Debug** CMake build in
`build-editor/` (GCC). Debug is the typical choice for editor work.

```bash
# from the repo root
cmake -S . -B build-editor -DWF_ENABLE_EDITOR=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build build-editor --target wf-edit -j
```

This produces `build-editor/wf-edit`. Debug host builds default to
ASan+UBSan; pass `-DWF_ASAN=OFF` if you need a faster (un-instrumented) editor.

`WF_ENABLE_EDITOR=ON` also implies `WF_ENABLE_CRDT=ON` (the editor owns the `Doc`).
The `task build-editor` Taskfile target builds the CRDT smoke tests and runs them; the
editor binary itself comes from the `cmake … -B build-editor` invocation above.

### Voice + video prerequisites

Voice and video are compiled in when their system libraries are present:

```bash
sudo apt install libopus-dev libvpx-dev   # Opus (voice) + libvpx VP8 (video)
```

Camera capture uses Linux [V4L2](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/v4l2.html)
(`/dev/video0`, no extra library); microphone capture uses
[miniaudio](https://miniaud.io/) (already vendored in the engine).

---

## Running `wf-edit`

```bash
./build-editor/wf-edit                          # default level (snowgoons-blender)
./build-editor/wf-edit --level=smb_w1_1          # open a specific level
./build-editor/wf-edit --level=qbert_practice --room=studio-1   # + join a call
```

### Command-line options

| Option | Form | Meaning |
|---|---|---|
| `--level=<name>` | `=` | Level the **engine** loads into the viewport (default `snowgoons-blender`). |
| `--leveltree=<name>` | `=` | Level the **Outliner/Properties** `Doc` is built from (defaults to match `--level`). Accepts a text `.lev`, a compiled binary `.iff`/`.lvl` (sniffed by content, decompiled on load), or a `cd.iff` archive with a level selector — `<file.iff>:<TAG\|index>` (e.g. `wflevels/cd.iff:L4` or `:1`). |
| `--room=<id>` | `=` or space | Join a voice + video call room. Omit to run solo (no call started). |
| `--frames <N>` | space | Headless: exit after *N* frames. **Note the space** — `--frames=N` is ignored. |
| `--screenshot <path.ppm>` | space | Headless: dump the composited frame (engine + UI) to a PPM. **Note the space.** |
| `--select=<N>` | `=` | Headless aid: preselect actor *N* in the Outliner. |

> The `--frames` / `--screenshot` space-vs-`=` quirk is a real gotcha: an `=`-joined value
> is silently ignored and the editor runs forever. See
> [the screenshot-capture notes](../.claude/projects/-home-will-WorldFoundry/memory/project_wfedit_screenshot_capture.md)
> for the headless-capture recipe.

---

## The editor window

![wf-edit window anatomy — menu bar, Outliner (left), Viewport (center), Properties (right)](../tests/screenshots/wfedit_m4_outliner.png)

The window is an ImGui **dockspace** with a menu bar and three docked panels. Panels are
dockable/resizable — drag a tab to rearrange.

- **Menu bar** (top) — `File` (Save / Save + Compile), and `View` (toggle the
  Collaborators panel) when a call is active. The room ID is shown to the right when joined.
- **Outliner** (left) — every actor in the level, read from the CRDT `Doc`. The header
  shows the level name and actor count (e.g. *snowgoons-blender.lev: 36 actors*). Click a
  row to select it.
- **Viewport** (center) — the live engine render. The overlay shows the current frame
  number and FPS. This is the real engine stepping each frame, not a static preview.
- **Properties** (right) — the selected actor's fields. Empty (*"(select an actor)"*) until
  you click a row in the Outliner.

---

## Selecting and inspecting actors

Click an actor in the Outliner to populate the Properties panel with its full field list.
The panel resolves each actor to its class schema (`.oad`) and renders **the right widget
per field type** — numeric spinners, enum dropdowns, checkboxes, colour swatches, file
pickers, object references, and so on.

![Properties panel for the snowgoons House actor — OAD-driven widgets, read-only state shown here](../tests/screenshots/wfedit_p2_house.png)

Field names, values, enum labels, and the actor's class all come straight from the
self-describing `.lev`; the `.oad` schema supplies the widget type, enum option lists, and
min/max ranges. Fields the schema doesn't name (the per-instance
`Position`/`Orientation`/`Global Bounding Box`/`Class Name` header) fall back to a
chunk-type widget, and anything still unrecognised degrades to raw monospace text rather
than failing.

---

## Editing properties

Every widget is editable. An edit commits to the actor's leaf in the CRDT `Doc`; re-reading
the `Doc` reflects it. Numeric edits preserve the level's fixed-point `(1.15.16)` / `l`
long suffix so they survive the save round-trip, and ints/floats clamp to the schema's
min/max.

![House after edits — Mass 5.0, Mobility → Physics, Movement Mailbox → 7 (editable widgets)](../tests/screenshots/wfedit_p3_edit.png)

Widget behaviour by field type:

| Field type | Widget | Notes |
|---|---|---|
| Int / Float | Spinner | Clamped to the schema's Min/Max. |
| `VEC3` / `BOX3` | 3 (or 6) float fields | e.g. Position, Bounding Box. |
| `EULR` (orientation) | 3 angle fields | **In revolutions** (0 ≤ rev < 1), not degrees/radians. |
| Enum | Dropdown | Full option list from the `.oad`; writes the label (+ index when present). |
| Boolean | Checkbox | |
| Colour | Swatch / picker | `showAs=COLOR` fields, e.g. background colours. |
| Mesh / file | Text + **Browse** | |
| Object reference | Actor name | Shows ⚠ if the referenced actor is missing. |
| Mailbox | Spinner (today) | Named-constant autocomplete from `mailbox.inc` is planned. |
| String | Inline / multi-line | |

> **Conventions that bite if you forget them:** orientation is in *revolutions*; the
> integer-vs-float distinction matters for the fixed-point suffix; and zForth's `/` is
> float division. These are documented in
> [docs/level-design-troubleshooting.md](level-design-troubleshooting.md).

---

## Live viewport preview

This is the headline feature: an edit in the Properties panel can change what you see in
the viewport *on the next frame*. Editing the snowgoons House's `Position` Z lifts it off
the snow:

| Before (`Position.Z = −0.125`) | After (`Position.Z = 6.0`) |
|---|---|
| ![House resting on the snow](../tests/screenshots/wfedit_m3_before.png) | ![House lifted off the snow after a Position edit](../tests/screenshots/wfedit_m3_after.png) |

**What propagates live (v1):** `Position`, `Orientation`, and ~15 movement/physics
fields — `Mass`, `Mobility`, `Step Size`, `Max Ground Speed`, and the rest of that set.
Editing these moves/rotates the actor or changes its physics behaviour across stepped
frames.

**What does *not* update the viewport yet:** every other field still edits the `Doc`
(and saves correctly), but the bridge logs *"no engine mapping yet"* and the on-screen
actor is unchanged. Most of these (elasticities, bounding box, script, notes) produce no
visible change even when applied.

> The ~15-field limit is in the **editor's bridge**, not the engine: the engine's mutation
> API (`wfmut`) now accepts 77 fields (auto-generated from the schema), but the editor's
> `engine_bridge` keeps its own ~15-entry name→path table for routing panel edits. Widening
> the editor's live-preview coverage to match is a planned follow-up.

Sync is **one-way**, `Doc` → engine: the viewport reflects your edit because the engine
re-renders the mutated actor; physics moving an actor does **not** write back into the
`Doc`. The `Doc` stays the source of truth.

---

## Adding and deleting actors

With an actor selected, the Outliner shows **Duplicate** and **Delete** buttons (and the
<kbd>Delete</kbd> key deletes the selection when you're not typing in a field):

![qbert_practice loaded — the Outliner's Duplicate / Delete buttons appear above the actor list](../tests/screenshots/qbert_editor_load.png)

- **Delete** removes the actor from the `Doc`. Surviving actors keep propagating live; the
  saved `.lev` has the actor gone.
- **Duplicate** clones the selected actor's full chunk subtree and appends it.
  - For a **template-spawnable** actor (e.g. a generator/enemy), the clone appears **live**
    in the viewport.
  - For a **non-templated** actor (e.g. a House), the clone exists in the `Doc` and saves
    correctly, but you won't see it in the viewport until you reload the saved level — a
    toast explains this.

After a structural edit the actor count updates immediately (here, a duplicated House
brings snowgoons to 37 actors):

![Outliner after duplicating the House — 37 actors, the new House selected](../tests/screenshots/wfedit_outliner_struct.png)

> There is **no undo** for add/delete in v1. Save deliberately (it overwrites the `.lev`),
> and keep your `.blend` as the golden source.

---

## Saving and compiling

The `File` menu has two actions:

- **Save Level** (<kbd>Ctrl</kbd>+<kbd>S</kbd>) — writes the `Doc` back to the level's
  `.lev` source. A toast confirms the path.
- **Save + Compile (.iff)** — saves, then runs the 5-stage `build_level_binary.sh`
  pipeline to produce the engine-loadable `.iff`. This blocks the frame for the few
  seconds the build takes; the live engine is **not** auto-reloaded — the fresh `.iff` is
  there for the next play/load.

![File→Save toast — "saved …​.lev / re-import in Blender (wf.import_level) to refresh the .blend"](../tests/screenshots/wfedit_save_toast.png)

A successful compile reports the built artifact and its size in the toast:

![Save + Compile toast — the .lev → .iff pipeline finished](../tests/screenshots/wfedit_save_compile.png)

**Golden-source note:** the saved `.lev` is *comment-free canonical* output (the
enum/axis `//` hints in a hand-authored `.lev` are schema-derived and regenerated, not
preserved). Because `.lev` → `.blend` re-import already exists
([`wf.import_level`](../wftools/wf_blender/export_level.py) in the Blender add-on), an
editor-saved `.lev` round-trips back into the golden `.blend` — the toast reminds you to
re-import there. Keep the `.blend` authoritative for shipped levels.

---

## Collaboration: voice + video

When you pass `--room=<id>`, the editor joins a call room. Editors started with the **same
room ID** on the same LAN discover each other automatically and can see + hear one another.

```bash
# two terminals, same room — they find each other:
./build-editor/wf-edit --level=qbert_practice --room=studio-1
./build-editor/wf-edit --level=qbert_practice --room=studio-1
```

The **Collaborators** panel (toggle via the `View` menu) shows your self-preview, per-peer
video thumbnails (or a coloured initials avatar when a peer has no camera), an audio level
meter per peer, and **Mute mic** / **Cam off** buttons:

```
┌─ Collaborators ─────────────────────────────┐
│ Room: studio-1                              │
│                                             │
│ You      (live)                             │
│  [ Mute mic ]   [ Cam off ]                 │
│ ─────────────────────────────────────────  │
│  ┌──────────┐  ┌──────────┐                │
│  │ [video]  │  │   (B)    │   ← initials    │
│  │ Alice    │  │  Bob     │     avatar      │
│  │ ████░░░░ │  │ ░░░░░░░░ │   ← level meter │
│  └──────────┘  └──────────┘                │
│                                             │
│  No peers? Share the room ID to invite.     │
└─────────────────────────────────────────────┘
```

Two editor instances in the same room (`--room=demo-266485`), each seeing the other. The
peer has no camera, so it shows as a coloured initials avatar (**E** for "Editor", the
fixed v1 display name); the self row reads *[cam off]* with *Unmute mic* / *Cam on* toggles:

![Collaborators panel — a second instance appears as the "Editor" peer (initials avatar) in the same room](../tests/screenshots/wfedit_collab.png)

**How it works (LAN v1):** peer discovery is a heartbeat beacon broadcast every 2 s on
multicast group `239.255.42.99:9877`, filtered by room ID. Voice is
[Opus](https://opus-codec.org/) (48 kHz mono, 20 ms frames) over UDP; video is
[VP8](https://www.webmproject.org/vp8/) (libvpx) from a V4L2 camera over UDP, fragmented to
fit the MTU. Each editor binds **ephemeral** UDP ports (OS-assigned), so several instances
can run on one machine. Your display name is currently fixed to *"Editor"*.

**Limitations:** LAN-only (multicast discovery, no STUN/relay yet — remote peers are v2);
audio is a flat stereo mix (no spatialisation). Text chat rides the separate WebSocket
co-editing relay, not this voice/video path. If `/dev/video0` is absent you appear with an
initials avatar (audio-only).

---

## Keyboard shortcuts

| Key | Action |
|---|---|
| <kbd>Ctrl</kbd>+<kbd>S</kbd> | Save Level (when not typing in a field) |
| <kbd>Delete</kbd> | Delete the selected actor (when not typing in a field) |

---

## Headless / automation hooks

For CI, screenshots, and scripted verification, the editor exposes environment-variable
hooks that drive one action and (mostly) exit. These are **not** part of the interactive
workflow — they exist so the editor can be proven headlessly.

| Env var | Effect |
|---|---|
| `WF_EDIT_SAVE=<path>` | Save the `Doc` to `<path>.lev` (CPU-only, before GL), then exit. |
| `WF_EDIT_SAVE_UI=<path>` | Drive File→Save once *inside* the frame loop (so the toast renders for a screenshot). |
| `WF_EDIT_COMPILE=1` | Drive Save + Compile once. |
| `WF_EDIT_TEST_SET="Field\|DATA\|new text"` | With `--select=N`: write one leaf on actor *N* (headless edit proof). |
| `WF_EDIT_STRUCT_TEST=…` | Headless structural edit (duplicate/delete) proof. |
| `WF_EDIT_STRUCT_UI=dup\|del` | Drive a structural edit once through the Outliner UI path. |
| `WF_EDIT_BRIDGE_DEBUG=1` | Dump the `Doc`↔engine actor-index map + field translations on the first frame. |
| `WF_EDIT_BRIDGE_TEST="Field Name\|new DATA"` | Edit a leaf as the panel would, propagate through the bridge, log before/after engine position. |
| `WF_EDIT_REMOTE_TEST="<docB>\|<x y z>"` | With `--select=A` (A≠B): apply a **remote**-origin Position edit to actor *B* and confirm the deep observer alone moves it in the engine. |
| `WF_EDIT_DRAGLOCK_TEST=1` | With `--select=N`: prove the active-drag transform lock — a remote edit to a simulated-dragged actor (non-transform *and* Position) leaves it put, and propagation resumes on release. |
| `WF_EDIT_SPAWN_CONFIRM_TEST=1` | Verify the `SpawnActor` runtime path (run with `--frames 5`). |

---

## Known limitations

- **Networked co-editing shipped** (presence/awareness cursors, a WebSocket `wf-relay`
  server, conflict-free remote merges, text chat, and debounced disk persistence of each
  room). The one deferred piece is **BYOK** at-rest snapshot encryption: the relay's
  snapshot writer takes a `wrap: bytes → bytes` hook that is identity today, leaving room
  to drop in customer-key encryption later without re-encoding existing snapshots.
- **Voice/video is LAN-only** (multicast discovery; no STUN/relay/remote peers). Text chat
  is available separately over the WebSocket co-editing relay.
- **Live viewport preview** covers Position/Orientation + all 77 common/movebloc/mesh OAD
  fields (the full generated field map) — they propagate live through the CRDT→engine
  bridge. The one exception is **mesh geometry** (Model Type / Tiles / Map): the value
  reaches the engine's mesh block, but the actor's render mesh is built once at spawn and
  isn't rebuilt live, so those three need a reload to be *seen*.
- **Undo/redo** is native (Ctrl+Z / Ctrl+Y) for field, gizmo, and structural edits via the
  Yrs `UndoManager`; remote peers' edits stay out of your local undo history.
- **While you drag an actor with the gizmo,** a concurrent edit to that actor from a remote peer
  (or your own undo) won't snap it back mid-gesture — the drag owns its transform until you release
  the mouse, then last-writer-wins resolves the transform. Other fields still propagate live.
- **Loads compiled binary levels; saving always produces a new standalone file.** The editor opens a
  text `.lev`/`.iff.txt`, a compiled bare `.iff`/`.lvl`, **and** a level selected out of a `cd.iff`
  archive (`--leveltree=wflevels/cd.iff:L4`) — a binary input is decompiled on load via
  `levcomp decompile`
  ([`wftools/levcomp-rs/src/decompile.rs`](../wftools/levcomp-rs/src/decompile.rs)). A binary-loaded
  level is fully editable; Save writes *out* to a new `.lev`, and **Save + Compile (.iff)** recompiles
  that to a bare `.iff` through the normal pipeline. Saving back **into** a multi-level `cd.iff`
  (rebuilding the archive in place) is by design **not** a feature — a `cd.iff` is read-only input,
  and you always save out as a new file. Also note: binary levels carry no authored object names
  (cross-references are stored by actor index; the decompiler synthesizes `{Class}_{index}` names),
  so a `.lev` saved from a binary load is a fresh derivative, not a round-trip to the original
  Blender/`.lev` source. See the [load-binary-iff plan](plans/2026-05-25-wf-edit-load-binary-iff.md).
- **Linux/X11 only.** Wayland and mobile hosts are v2+.

---

## Where to learn more

- [Collaborative level editor — design exploration](investigations/2026-05-18-collaborative-level-editor-design.md) — concept, mockups, widget taxonomy, roadmap.
- Implementation plans (each with screenshots):
  [app shell](plans/2026-05-20-editor-app-shell.md) ·
  [property panel](plans/2026-05-20-editor-property-panel.md) ·
  [CRDT→engine bridge](plans/2026-05-20-crdt-engine-bridge.md) ·
  [save round-trip](plans/2026-05-21-editor-save-roundtrip.md) ·
  [outliner add/delete](plans/2026-05-21-outliner-add-delete.md) ·
  [live structural sync](plans/2026-05-21-live-structural-sync.md) ·
  [voice + video](plans/2026-05-21-voice-video-collab.md).
- [docs/level-building.md](level-building.md) and
  [docs/level-design-troubleshooting.md](level-design-troubleshooting.md) — the level
  designer's reference and gotcha log.
