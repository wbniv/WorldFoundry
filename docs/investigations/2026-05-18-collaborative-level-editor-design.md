# Collaborative level editor — design exploration

**Date:** 2026-05-18
**Status:** Design brainstorm, no implementation yet. Captured before details fade.
**Trigger:** Open-ended brainstorm — "I want to design a new application that embeds the wf game engine into something else."
**Related TODO:** [Research: Qt as the UI toolkit](../../TODO.md) under § TOOLS.

---

## Application concept

A standalone collaborative level editor for World Foundry. Spiritually descended from [SubEthaEdit / Hydra](https://en.wikipedia.org/wiki/SubEthaEdit) (the first widely-known multi-user real-time editor on the Mac, by [TheCodingMonkeys](https://www.codingmonkeys.de/subethaedit/), launched 2003 — Bonjour peer discovery, coloured cursors, Apple Design Award), updated with the modern stack:

- **Multi-user, real-time** — several level designers, on different computers, working on the same level concurrently.
- **Text chat** in the editor sidebar. (Voice deferred from v1.)
- **The wf engine is embedded** in the editor process so designers see a live render of the level as it's being edited — every edit reflects immediately, no `.blend` → `.lev` → `.iff` → reload roundtrip per edit.
- **Each user has their own camera** into the shared scene (Unity-collab style); awareness shows other users' viewports as ghost cameras.

The `.blend` file remains the golden source for shipped artefacts (per [feedback_blender_golden_source](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_blender_golden_source.md)) — the editor "publishes" to `.blend` on save, and Blender stays in the picture for mesh / texture / material authoring.

---

## Mockups

ASCII sketches to give the design something to point at. Not pixel-faithful — the goal is to show the rough layout, where awareness/presence surfaces, what the widget breadth feels like, and how the chat/lobby UI fits.

### Main editor window

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ WorldFoundry Editor — smb_w1_1 — relay.studio.com/r/smb-w1-1     ● 3 users  │
├─────────────┬──────────────────────────────────────────────┬─────────────────┤
│  Outliner   │                                              │   Properties    │
│             │                                              │                 │
│  ▼ Level    │                                              │   House         │
│    House ●  │   ╔══════════════════════════════════════╗   │   ─────────     │
│    Ground   │   ║                                      ║   │                 │
│    Wall_L   │   ║                                      ║   │   Position      │
│    Wall_R   │   ║       (live 3D engine viewport)      ║   │    X ◄ 12.34 ►  │
│    Mario    │   ║                                      ║   │    Y ◄ -5.67 ►  │
│    Goomba   │   ║                ◯ alice               ║   │    Z ◄  0.10 ►  │
│    ...      │   ║       ┌─House─┐                      ║   │      👤 alice 3m│
│             │   ║       │       │ ┃ bob's selection    ║   │                 │
│  ▼ Cameras  │   ║       └───────┘ ┃                    ║   │   Orientation   │
│    cs_main  │   ║                ┏━┻━┓                 ║   │    a ◄ 0.000 ►  │
│             │   ║                ┃Wall┃                ║   │    b ◄ 0.000 ►  │
│  ▼ Director │   ║                ┗━━━┛                 ║   │    c ◄ 0.250 ►  │
│    Dir_main │   ╚══════════════════════════════════════╝   │                 │
│             │                                              │   Mass    👤 bob│
│  + New      │   📷 alice's ghost cam ▶                     │    ◄━━●━━━━━► 0 │
├─────────────┴──────────────────────────────────────────────┴─────────────────┤
│ Chat                                                  ● alice ● bob ● you   │
│   alice: scoot the goomba over a bit                                        │
│   bob:   ok                                                                 │
│   ┃ alice is typing…                                                        │
│   > _                                                       [Publish→.blend]│
└──────────────────────────────────────────────────────────────────────────────┘
```

Things visible: the embedded engine viewport (live render of CRDT state), the outliner (left), the type-aware property panel (right, with per-leaf `_author`/`_ts` attribution), other users' awareness — ghost cursors, selection rings, ghost camera frustums — chat sidebar at the bottom with typing indicator and current-room presence, the manual **Publish → .blend** button (per the workflow decision above).

### Open / Connect dialog

```
┌─ Open / Connect ─────────────────────────────────────────────────────┐
│                                                                      │
│  Relay: relay.studio.com                                  [Change…]  │
│  You: Will  ◆ #3b82f6                                     [Edit…]    │
│                                                                      │
│  ┌──[Active]──┬──[Recent]──┬──[URL]──┬──[New]──┐                     │
│  │                                                                   │
│  │  Active rooms on relay.studio.com                                 │
│  │                                                                   │
│  │  ●  smb-w1-1          • alice  • bob                  3 users     │
│  │     qbert-practice    • carol                         1 user      │
│  │     snowgoons         (hibernated)                    0           │
│  │                                                                   │
│  │  ─── on the LAN (v1.5) ────────────────────────                   │
│  │  ●  Will's editor     192.168.1.42  pyramid-tweaks                │
│  │                                                                   │
│  └─────────────────────────────────────────────────                  │
│                                                                      │
│                                                  [Join]    [Cancel]  │
└──────────────────────────────────────────────────────────────────────┘
```

Four tabs — **Active** (live rooms on the configured relay; LAN section below it when mDNS lands in v1.5), **Recent** (local history), **URL** (paste a `wfedit://` invite or short room code), **New** (create a fresh room). User identity (display name + colour chip) is set once and shown at the top.

### Property panel detail — widget breadth

```
┌─ Properties — House (statplat) ────────────────────────┐
│                                                        │
│  Position              VEC3              👤 alice 3m   │
│   X ◄ 12.345  ►                                        │
│   Y ◄ -5.678  ►                                        │
│   Z ◄  0.100  ►                                        │
│                                                        │
│  Orientation           EULR  (revolutions)             │
│   a ◄ 0.000   ►   pitch                                │
│   b ◄ 0.000   ►   roll                                 │
│   c ◄ 0.250   ►   heading                              │
│                                                        │
│  Mass                  FX32              👤 bob 1m     │
│   ◄━━━━━●━━━━━━━━━━━━━━━━━━━━━━━► 0.0                  │
│   min 0   max 1000   format 1.15.16                    │
│                                                        │
│  Moves Between Rooms   I32  (enum)                     │
│   ( ) False    (●) True                                │
│                                                        │
│  Background Color      I32  (showAs=COLOR)             │
│   ▓▓▓▓▓▓▓▓▓▓▓  #80A0FF   [Pick…]                      │
│                                                        │
│  Movement Mailbox      I32  (showAs=MAILBOX)           │
│   [ INDEXOF_INPUT  ▼ ]    (auto-completes from         │
│                            mailbox.inc)                │
│                                                        │
│  Mesh Name             FILE                            │
│   📦 House.iff   ◇ blob:a3f9b2…   [Change…]            │
│                                                        │
│  Script                STR  (showAs=TEXTEDITOR)        │
│   🔒 alice is editing (soft-lock) — wait or override   │
│   ┌────────────────────────────────────────────────┐   │
│   │  \ wf                                          │   │
│   │  : tick INDEXOF_HARDWARE_JOYSTICK1_RAW         │   │
│   │         read-mailbox                           │   │
│   │         INDEXOF_INPUT write-mailbox ;          │   │
│   │  ...                                           │   │
│   └────────────────────────────────────────────────┘   │
│                                                        │
│  Cave Logic Studios Notes  STR  (showAs=TEXTEDITOR)    │
│   ┌────────────────────────────────────────────────┐   │
│   │  TODO: make the door swing                     │   │
│   └────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────┘
```

Every widget is driven by the OAD's `showAs` value. The **Mailbox** combo auto-completes from `mailbox.inc`'s `INDEXOF_*` table (or `MB_*` post-prefix-rename). The **Script** field shows a soft-lock indicator and (v2+) becomes a `Y.Text` editor with character-level merging and per-character author attribution. **Notes** is treated the same as Script — both `SHOW_AS_TEXTEDITOR` fields flip to `Y.Text` together when v2 arrives. Per-leaf `_author`/`_ts` shown as a chip on the right side of any field that's been touched.

### Viewport presence overlay (zoomed)

```
                       ┌──────[ alice ]──────┐
                       │   📷  ghost camera  │   ← awareness: alice is looking
                       │   field of view  ▶  │     at this region from over here
                       └─────────────────────┘
                                ╲
                                 ╲   frustum lines
                                  ╲
        ╔══════════════════════════╲══════════════╗
        ║                           ╲             ║
        ║       ┌──House──┐          ╲            ║
        ║       │         │  ◯ alice's cursor     ║
        ║       └─────────┘                       ║
        ║                                         ║
        ║                ┃━ bob's selection ━┓    ║
        ║                ┃                   ┃    ║
        ║                ┃     ┌──Wall──┐    ┃    ║
        ║                ┃     │        │    ┃    ║
        ║                ┃     └────────┘    ┃    ║
        ║                ┗━━━━━━━━━━━━━━━━━━━┛    ║
        ║                                         ║
        ╚═════════════════════════════════════════╝
```

Awareness payload renders as: **ghost camera frustum** showing where other users are looking, **selection rings** in their colour around actors they've selected, **cursor dots** where their mouse is hovering. Ephemeral — disappears the instant a user disconnects. Same per-user UUID drives the colour and avatar everywhere it appears.

### Chat sidebar

```
┌─ Chat — smb-w1-1 ─────────────────────────────┐
│                                               │
│ Tuesday 18 May                                │
│                                               │
│ 14:23  ◆ alice                                │
│         moved House over a bit                │
│                                               │
│ 14:23  ◆ bob                                  │
│         looks great                           │
│                                               │
│ 14:25  ◆ alice                                │
│         working on goomba spawn now           │
│         ┃ alice is typing…                    │
│                                               │
│ ──────────────────────────────────────────    │
│ ● 3 in this room                              │
│    ◆ alice    (selected House)                │
│    ◆ bob      (looking around)                │
│    ◆ you      (selected Goomba)               │
│                                               │
│ ┌───────────────────────────────────────────┐ │
│ │ > _                                       │ │
│ └───────────────────────────────────────────┘ │
└───────────────────────────────────────────────┘
```

v1 = plaintext chat over the WebSocket relay; presence list at the bottom shows who's in the room with their current selection (from awareness). v2 = same UI, Matrix as the backend (E2E, federation, message history).

---

## Architectural decisions made during the brainstorm

### Not a Blender addon

Initial sketch put the editor inside Blender as a wf_blender addon extension. That was rejected: edit → Blender depsgraph → addon export → IFF pipeline → file watch → engine reload is a many-hundred-millisecond round trip per edit. Not editor-feel. The editor is a standalone application with the wf engine embedded directly.

Concrete shape:

- **In-memory CRDT mirroring the IFF chunk tree is the live source of truth**, not a `.iff` file on disk. Edits mutate the CRDT; the engine reads the CRDT; no file round-trip.
- **The engine is linked into the editor process.** Renders into a viewport widget the editor owns. State changes are direct (or via shared-memory observation), not "file changed, reload."
- **Blender moves off the hot path.** Used for (1) mesh / texture / material authoring and (2) the canonical save format written out on "Publish."
- **Save = serialize CRDT → IFF chunk tree → `.lev` → headless wf_blender exporter → `.blend`.** The `.blend` round-trip closes the golden-source rule.
- **Effectively the editor could be a special mode of the engine** — `wf_game --editor` launches the same binary with editing UI overlays. No separate editor codebase + engine codebase split.

### Implementation language: C++ for v1

C++ is the v1 implementation language for the editor itself. Reasons: the editor links the wf engine directly (engine is C++); [Dear ImGui](https://github.com/ocornut/imgui) is C++-native and shares the engine's GL context as overlays in the same process; [Yrs](https://github.com/y-crdt/y-crdt) (the Rust port of Yjs) is callable from C++ via cbindgen with a small C ABI. One process, one binary, no cross-language bridge in the hot path.

Reconsider in v2+ if a different language story becomes attractive (Python shell with the engine wrapped via pybind11 stays open if PySide/Qt enters the picture; Rust as a host language stays open if the engine grows a stable C API).

### UI toolkit: Dear ImGui for v1

[Dear ImGui](https://github.com/ocornut/imgui) is the v1 choice. Drops straight into the engine's existing GL context as overlays, fastest path to "editor = engine + UI overlays in one process." Game-tool aesthetic; what Unity / Godot / Unreal-editor-ish things use under the hood. No upfront research — we start writing editor code with ImGui.

[Qt](https://www.qt.io/) is a **post-v1** possibility — native widgets, polished apps, `QOpenGLWidget` for the viewport, PySide bindings if we want Python for the shell. Heavier integration but ships nicer-looking apps. Whether to migrate or stick with ImGui is a question for after v1 ships and we see how the ImGui UX actually feels in real use. TODO entry under § TOOLS is parked under that framing — no research happens until v1 is on the table.

[Egui](https://www.egui.rs/) (Rust) and a WASM web frontend are noted as possible directions but not actively pursued.

### Markdown rendering: `imgui_markdown` for v1, free with Qt later

Multiple v1 surfaces want markdown rendering — bundled into the existing v1 estimates (chat sidebar, property-panel widgets), not a separate line item:

- **Chat sidebar.** Inline code (`` `Position` ``), links to other rooms / docs, fenced code blocks for sharing Forth snippets, bold/italic. Wire format stays plaintext over WebSocket per the chat module decision; rendering happens client-side at display time.
- **Notes leaf** (`SHOW_AS_TEXTEDITOR` "Cave Logic Studios Notes"-style fields). Read mode renders markdown; edit mode is plain text. Pairs naturally with the post-v1 `Y.Text` upgrade — live-rendered markdown with collaborative cursors (HackMD / Notion shape).
- **Property-panel hover-info / help blurbs.** Optional, cheap once a renderer is in.

**v1 library: [imgui_markdown](https://github.com/juliettef/imgui_markdown)** (header-only, MIT). Renders into the same ImGui draw lists as the rest of the editor — no separate font atlas, no separate texture, works with the engine's GL context unchanged. Subset support (paragraphs, headings, lists, links, inline code, fenced code, bold/italic) covers v1 needs. Limitations (no tables, no images beyond simple inline, no math) are not v1-blocking.

**v2 (Qt-time): free via [`QTextDocument::setMarkdown`](https://doc.qt.io/qt-6/qtextdocument.html#setMarkdown)** — full CommonMark + GitHub Flavored Markdown out of the box; integrates with `QTextEdit` for the Notes editor's edit-mode side. The v1 → v2 migration is a swap behind the same `render_markdown(str) → widget` interface.

Not pursued: writing our own renderer (no upside vs. imgui_markdown); [cmark](https://github.com/commonmark/cmark) + custom ImGui glue (more flexible than imgui_markdown but ~weeks of glue work for marginal benefit at v1 scope).

### Sync model: CRDT, Yjs as the leaning library

Three sync models considered:

1. **Authoritative server** — server holds the ground truth, clients send intents. Pro: simple conflict semantics. Con: round-trip latency on every edit; painful for editor-feel.
2. **CRDT (Yjs / Automerge)** — convergent data structures, instant local edits, deterministic merge, robust to network blips. Con: more complex to reason about for structured data; harder to enforce business rules.
3. **OT (operational transform)** — centralised, transforms concurrent ops against each other. Pro: excellent for character-level text. Con: awkward for structured data; our edits are mostly point mutations, not text streams.

Decision: **CRDT**, with the chunk tree as the CRDT's data structure.

Library: **[Yjs](https://github.com/yjs/yjs)** (or its Rust port [Yrs](https://github.com/y-crdt/y-crdt)) accessed via [pycrdt](https://github.com/jupyter-server/pycrdt) for Python integration. Yjs is MIT-licensed, production-proven (JupyterLab, Logseq, Affine, Tiptap), has a mature provider model (`y-websocket` for relay, `y-webrtc` for P2P, `y-leveldb` for storage), and a built-in awareness channel for ephemeral presence state.

Why Yjs over Automerge: production traction, JupyterLab pedigree, more integrations, slightly faster on tree-shaped data. Automerge is a credible alternative; switching later is a protocol-level migration.

### Network model: relay server, not pure P2P

A dumb WebSocket relay (~200 LOC of Node or Rust, or use [hocuspocus](https://hocuspocus.dev/) for batteries-included) fans byte-shuffled Yjs updates to subscribers in a room. Stateless game-logic-wise. Persistence by snapshotting CRDT state to disk every N seconds.

Pure P2P (WebRTC) noted as possible later but adds NAT-traversal pain for the first release; relay is much simpler to ship and still gives the offline-tolerant editing CRDTs provide.

### Chat and lobby: relay-first for v1, Matrix-later for v2

Chat (text in editor sidebar) and lobby (discovery + room management) need a transport. Four options considered:

- **Discord / Slack / IRC** — closed-source (Discord/Slack) or no E2E in protocol (IRC); embedding their chat in a custom app is awkward; vendor risk. Dismissed.
- **[Matrix](https://matrix.org/)** + [matrix-rust-sdk](https://github.com/matrix-org/matrix-rust-sdk) — production E2E via Olm/Megolm (Signal-derived), rooms first-class, federation, self-hostable via [Synapse](https://github.com/element-hq/synapse) / [Dendrite](https://github.com/element-hq/dendrite) / [Conduit](https://gitlab.com/famedly/conduit). Cost: ~10 MB SDK dependency, device-verification UX surface, Synapse ops burden.
- **[XMPP](https://xmpp.org/) + [OMEMO](https://xmpp.org/extensions/xep-0384.html)** — also Signal-derived E2E, lighter than Matrix, but less ecosystem momentum in 2026. Defensible; not preferred.
- **Roll our own on the existing WebSocket relay** — chat flows through the same relay we already need for Yjs CRDT sync. Plaintext at first; add E2E later via [libsodium](https://doc.libsodium.org/) or [MLS / RFC 9420](https://datatracker.ietf.org/doc/html/rfc9420) (Rust impl: [OpenMLS](https://github.com/openmls/openmls)). Smallest dependency footprint; you're building a chat product.

**Decision: relay-first for v1, Matrix-later for v2.**

- **v1** ships chat through the existing CRDT WebSocket relay, plaintext over TLS. Lobby is `GET /rooms` from the relay. Identity is "pick a display name and a colour" — no auth. Same relay process, same room concept (one room per level editing session).
- **v2** (when E2E or federated identity becomes important) replaces the chat + lobby module with Matrix. Matrix rooms become the lobby; Matrix user IDs become identity; matrix-rust-sdk handles E2E. The CRDT keeps its own dumb WebSocket relay — Yjs is high-frequency and tight, doesn't fit Matrix message events. A Matrix room's state holds the pointer to the CRDT relay URL + room-id, and the relay accepts a signed token from Matrix as authorization.

Threat model for v1 ("designers in the same studio editing a level, chat is about level design") doesn't require E2E. When the userbase broadens to cross-organisation collaboration, Matrix kicks in. Migration is clean because chat/lobby is a module boundary, not a foundation layer.

**Implementation hygiene to make the migration easy:**

- Keep the chat module behind an interface (`send_message`, `subscribe`, `list_rooms`, `join_room`, `presence`, `whoami`). v1 implementation is "talk to our relay"; v2 implementation is "talk to Matrix homeserver."
- Don't embed display-name-and-colour identity into the CRDT's `_author` field as the user-facing primary key. Use a stable per-user UUID generated on first launch; display name / colour / (later) Matrix ID are display attributes resolved by the chat module.

**Why MQTT was considered and rejected.** [MQTT](https://mqtt.org/) was discussed as a candidate because the v1 designer happens to run an MQTT broker for home-automation purposes — broker reuse looked like a synergy. It isn't: the broker-already-exists benefit only applies to that one user; every other editor user would have to stand up Mosquitto just to chat. That flips the trade-off (tax everyone for a benefit only one person gets). MQTT also doesn't help with E2E in v2 — you'd still be rolling crypto, getting to roughly where Matrix already is. So the v1 → v2 path stays WebSocket-relay → Matrix; MQTT doesn't move the needle.

**External-system integration (e.g. Home Assistant) is via bridge, not via the chat protocol itself.** If a user wants editor events surfaced in HA or HA events surfaced in the editor, that's a small per-direction adapter (~50–100 LOC): an HA integration subscribes to whatever events it cares about and translates to/from the editor's WebSocket. The editor's chat protocol does not need to be "the same protocol HA speaks" — picking a chat protocol based on what external systems use is the wrong axis. Bridges keep the integration concern per-user / per-deployment without imposing infrastructure choices on the product.

### Rendezvous: how users find each other and join sessions

The rendezvous problem has five layers, each with a v1-appropriate answer that doesn't need accounts or directory services.

**1. Discover the relay.** Relay URL is configured per editor install. A studio (or any group) stands up a relay; users enter the URL in editor settings once. Default is empty; first-launch UX is "enter your group's relay URL, or use the public community relay" (see the hosting section below). The relay binary is ~200 LOC of WebSocket fan-out behind TLS — trivial to host on a $5 VPS for any self-hoster.

**2. Discover existing rooms.** `GET /rooms` on the relay returns active rooms with current participants. Listed in the editor's "Open" dialog under an **Active rooms** tab.

**3. Join a session.** Rooms are URLs of the form `wfedit://relay.example.com/r/<room-id>`. The URL *is* the invite — sharing happens by paste-into-Slack/email/IM. OS URL-handler registration (clicking a `wfedit://` link opens the editor) is a v1.1 nicety, not launch-blocking.

The editor's "Open" dialog has four tabs:

1. **Active rooms** — `GET /rooms` from the relay, with who's currently in each.
2. **My recent rooms** — local history of rooms I've joined; persists across editor restarts.
3. **Join via URL** — paste a `wfedit://` URL or short room code.
4. **New room** — create a fresh room.

**4. Identify yourself.** Per-user stable UUID generated on first launch (per the chat-module implementation hygiene above). Display name + colour are user-editable display attributes resolved by the chat module. No accounts in v1.

**5. Find specific people.** v1 punts. Your social graph is "people in the same room as me right now." Want to collab with Alice? Either join a room she's in (out-of-band coordination), or ask her to send you a URL. Cross-room user discovery is a v2 concern that Matrix solves naturally with user IDs and federated discovery.

**Identity & avatars.** Per-user stable UUID + display name + colour is the v1 identity primitive (no accounts, no auth). Avatars render in chat sidebar, presence list, ghost-cursor overlays, and `_author` hover-info — UUID is the key everywhere; display name, colour, and avatar are display attributes resolved by the chat module.

The avatar source uses a four-step fallback chain:

1. **User-uploaded avatar** (v1.5 — uses the blob store we're already designing for meshes/textures).
2. **[Gravatar](https://gravatar.com/) lookup** — optional **Email** field in editor settings; client-side MD5-of-email → `https://gravatar.com/avatar/<hash>?d=identicon&s=64`. No OAuth, no account on our side, email never sent to our relay. Used if the field is set and a gravatar exists for it.
3. **Generative identicon from UUID** — pleasant SVG via [DiceBear](https://dicebear.com/) (MIT, many styles) or similar; deterministic from the UUID so the same user always gets the same avatar; tinted with the user's chosen colour.
4. **Initials on coloured background** (Google-Calendar style). Lowest-tech fallback.

**No Google sign-in for v1.** Google OAuth for "just the avatar" really means Google OAuth for identity — server-side OAuth flow on the relay (breaks the dumb-byte-shuffler shape), account creation friction at first launch (contradicts the immediate-collaboration UX), vendor lock-in to Google, and excludes users who don't have or want a Google account. If federated identity becomes a v2 need, **Matrix is the answer** — Matrix user IDs are the identity primitive, the homeserver federation handles cross-org identity, and Matrix profiles natively store avatars. "Sign in with X" becomes implicit in "log into your Matrix account."

**v2 transition:** drop the Gravatar email field; Matrix profile avatars take over. Users keep their UUID and display name; the avatar source flips from client-side Gravatar lookup to the homeserver-stored Matrix profile avatar. Self-uploaded avatars in our blob store stay accessible via the user's profile.

**Room ↔ level mapping: 1:1 by default.** Each level in the repo has a canonical room id stored as a `meta` field in the level file (UUID, not the file path — stable across file moves). "Open level X" auto-joins the canonical room for X. Snapshots stored on the relay keyed by room UUID. This is predictable: "I'm editing qbert_practice" → you and everyone else editing qbert_practice end up in the same room without coordinating. Ad-hoc rooms ("scratch room for jam session") are available via the **New room** tab but not the common path.

**Room lifecycle.** Rooms with active participants live in relay memory. Rooms with no participants for N minutes hibernate to disk snapshot. Reactivating later restores state from snapshot. Hibernation is purely a relay-side memory optimisation, invisible to users. Hard-deleting a room is an explicit admin action (UI for it is later).

**Room creation triggers.** Three coherent paths, all available:

- **Auto-create on first level open.** Editor sees "this level UUID isn't on the relay yet"; uploads initial CRDT state from the local `.iff`; room exists. Subsequent opens just join.
- **Manual** via the "New room" tab.
- **Implicit on receiving an invite URL** for a room id that doesn't exist on the relay yet → editor offers to create it.

**Optional v1.5: mDNS / Bonjour for LAN auto-discovery.** Very [SubEthaEdit](https://www.codingmonkeys.de/subethaedit/)-spirit. Editor announces presence on the local network (mDNS service type `_wfedit._tcp`) and browses for other editors' announcements. "Active rooms" tab grows a **LAN** subsection above the relay-server section — designers in the same office literally see each other's editors and can join with no URL exchange. Bounded extra complexity (~few hundred LOC; standard libraries available); real UX win for in-person sessions. Not v1 launch-blocking; nice to ship in v1.5.

### Hosting & business model: free self-host + paid managed relays

Backend infrastructure is not a constraint (the project owner can spin up backend infra easily). The relay is a small enough piece of software that this opens an actual revenue opportunity alongside the OSS editor.

**Three hosting tiers, all running the same relay binary:**

1. **Free self-hosted.** Download the relay binary, run it on your own VPS. Same code as the managed offering. Configure TLS yourself; back up yourself. Aimed at studios / power users / privacy-conscious teams who'd rather own their infrastructure.
2. **Free public community relay** (`wfedit.org` or similar). Single shared relay we operate, public rooms welcome with conservative limits (rate, per-room storage cap, hibernation aggressive). Good for trying the editor out, OSS contributors, casual users, the editor's own onboarding flow.
3. **Paid managed relays.** Dedicated relay instance per customer, custom subdomain, no/higher limits, automated backups, uptime SLO, support. Revenue = markup on cloud infrastructure (AWS / Hetzner / fly.io / whatever — pay-as-you-go cloud), no inventory, no shipping, no per-seat licensing complexity. Single-instance cost is low enough that the markup is easy to justify by "you don't have to install or maintain it."

**Why this works as a product:**

- **Zero inventory; pure SaaS cost structure.** Cloud bill is the only variable cost; markup is gross margin.
- **No user-side vendor lock-in by design.** Same binary in all three tiers means users can switch tiers freely — including defecting from paid → self-hosted at any time. That's actually a *feature* for sales: it removes the "what if I get stuck on your platform" objection. Users who do stay paid are staying because hosting is genuinely more convenient than DIY, not because they can't leave.
- **No cloud-vendor lock-in on our side either.** Cloud compute is a commodity product — AWS, Hetzner, Fly.io, DigitalOcean, OVH all sell us the same Linux box at different prices. The relay binary doesn't care which one it runs on. We can shop on price/performance and move providers without users noticing (DNS handles the switch). No expensive AWS-proprietary services in the stack means no migration tax when a cheaper provider appears.
- **Recurring revenue.** Editor licence remains free / OSS; managed relay is the recurring item.
- **Aligns with the open-source-tool + paid-managed-service model** that works for GitLab, Sentry, Plausible, etc.

**Pricing dimensions to consider (defer until closer to launch):** per-relay (one customer = one relay instance) vs. per-active-user vs. per-MB-stored vs. tiered (small/medium/large by limits). For early product, per-relay-flat is probably simplest — "$X/month gets you a dedicated relay, up to N concurrent users, M GB persistent storage." Get fancier later.

**Bring-your-own-key (BYOK) as an enterprise / privacy-tier add-on.** Standard "managed relay" trusts us with the customer's level data at rest (snapshots on our disk). BYOK adds a layer: the customer supplies an encryption key (managed by their own KMS — AWS KMS, HashiCorp Vault, Azure Key Vault, [age](https://github.com/FiloSottile/age) for the small-shop case), the relay encrypts CRDT snapshots with it at rest, the customer's editors decrypt on read. We hold ciphertext only; revoking the key revokes our ability to read the data without touching our infra.

Why it's a fit for our shape:

- **Defends the no-lock-in stance against the "but you can read my data" objection.** Customers who want managed convenience but can't tolerate "the vendor sees my IP" (small game studios with NDA'd contracted work, indie devs paranoid about leaks, eventually maybe regulated industries) get an answer that doesn't force them to self-host.
- **Cheap to add architecturally.** The relay already serialises CRDT snapshots; adding a "wrap snapshot with customer key" step is a single hook. Live in-memory CRDT state during an active session can stay plaintext (the relay needs to fan out updates between connected clients, which would otherwise require client-side E2E — that's a v2+ Matrix-time concern).
- **Sits naturally in an enterprise pricing tier.** Differentiated upsell from the standard managed plan. KMS integrations + audit logs + the marketing-friendly word "BYOK" buy you a notable per-customer price bump for modest engineering work.
- **Compatible with the v2 Matrix migration.** Matrix already has BYOK-equivalent in its key-backup story; the customer's KMS-managed key could back the homeserver's E2E key escrow. Sales motion stays consistent across v1 and v2.

Probably not a v1 launch feature, but worth designing the snapshot-storage layer so a key-wrap step can drop in later — i.e., the snapshot writer takes a "wrap" function pointer that's identity in the default tier and "encrypt with this customer key" in the BYOK tier.

**For v2 (Matrix-time):** the same business shape extends — sell managed Matrix homeserver hosting alongside the CRDT relay, or partner with [Element Matrix Services](https://element.io/element-matrix-services). The CRDT relay is the one piece we definitely host ourselves regardless of what happens to the chat layer; that's the durable revenue line.

### v1 dev target level: smb_w1_1

[smb_w1_1](../../wflevels/smb_w1_1/) is the v1 development test bed. Reasons:

- It exercises the current WF stack (Jolt physics, scrolling camera, modern script style) rather than legacy patterns.
- Its feature demands are medium — long-level viewport navigation, texture-mapped statplats, multi-actor mailbox-signaling — none exotic, all things the editor will need eventually.
- It surfaces the new-OAS-field path (`Scroll Min X` / `Scroll Max X` on `camshot.oas`), which is exactly the OAD-driven widget code we want to exercise.
- It has no procedural-actor multiplier (unlike qbert_practice's 28-cubes-from-Python pattern), so it sidesteps the "what about the script that generated the level" question — that's v2 territory.
- It's a recent, in-progress real level rather than a toy.

**Suggested on-the-ground path:** the first 2–3 weeks of editor work happen against a **brand-new minimal level** (one statplat, one script, expand from there) — too many moving parts to iterate on editor *and* a real level at the same time. Once the editor can open and round-trip a real `OBJ` cleanly, switch the dev target to `smb_w1_1`.

Snowgoons and qbert_practice considered and not picked: snowgoons would let v1 ship with a feature set too thin for the levels people actually want to edit; qbert would force the procedural-actor question into v1 scope.

### Blob storage: content-addressed at the relay

Meshes, textures, sounds and other binary assets don't live in the CRDT (CRDTs choke on large binary). The relay carries a content-addressed blob store alongside its CRDT-relay duties.

**Data model.** Blob identity is `sha256(bytes)` — immutable, content-addressed, trivially dedup'd. The CRDT's `blobs: Y.Map<sha256 → metadata>` is the **manifest** (filename, kind, size, uploaded_by, uploaded_ts). Actor fields reference blobs either by filename string (today's format, kept for back-compat with the existing pipeline) or by `blob:<sha256>` URI (editor-managed blobs).

**HTTP API on the relay.**

```
POST /blob/<sha256>           → 201 if new, 200 if dedup'd, 400 if hash mismatch,
                                413 if over per-blob cap (v1: 50 MB)
GET  /blob/<sha256>            → bytes; Cache-Control: public, max-age=∞, immutable
```

Content-addressed + immutable = perfect for HTTP caching and CDN-front later. Range requests for partial fetch are a deferred nicety.

**Auth.** Upload: anyone in the room can upload. Download: hash-as-capability — anyone with the hash can fetch, and SHA-256 hashes aren't guessable (same model as [Backblaze B2](https://www.backblaze.com/cloud-storage) / [Cloudflare R2](https://www.cloudflare.com/products/r2/) with signed URLs, simpler because the hash *is* the URL). Per-room signed-URL tokens for download are a v1.5 add-on if anyone needs tighter control.

**Dedup.** Free side-effect of content addressing. Two designers upload the same `House.iff` → same hash → stored once, reference count bumps. Cross-room dedup automatic within a relay.

**Storage backend.**

- **v1:** local disk at `/var/wfrelay/blobs/<first-two-hex>/<rest-of-hash>` (the two-hex shard prefix keeps individual directories under ~65k entries — filesystem-friendly).
- **v2 / managed-tier scaling:** swap in S3-compatible storage (Cloudflare R2, Backblaze B2, MinIO, AWS S3). Content-addressed objects fit S3 naturally (PUT with hash as key). [R2](https://www.cloudflare.com/products/r2/) is the cost-effective default for the managed tier (no egress fees). Aligns with the "no cloud-vendor lock-in on our side" stance — the relay uses the [S3 API](https://docs.aws.amazon.com/s3/) so we can shop providers without changing code.

**GC.** Reference-counted with grace period — when a blob's references drop to 0, it enters pending-deletion for ~30 days (so undo-after-delete works), then a periodic sweep removes it. **Probably not in v1** — disk is cheap and blobs accumulate slowly during normal use. Add GC the first time a managed-tier customer hits a storage cap.

**Quotas.** Per-blob cap 50 MB v1; per-room storage cap ~1 GB on free public tier, configurable per-customer on paid; per-month upload bandwidth not enforced v1 (add when abuse appears).

**Integration with the existing `cd.iff` pipeline.** The editor's blobs are an authoring-time convenience that doesn't replace `cd.iff` — they feed into it. Round trip: blob lives on the relay during editing (referenced by hash from the CRDT) → on manual "Publish" the editor downloads referenced blobs to the local project tree (`wflevels/<level>/assets/` or wherever the convention puts them) → updates the `.blend` to reference local filenames in the conventional way → wf_blender exporter runs as today → build pipeline assembles `cd.iff` from local files exactly as it does now. Existing repo-shipped assets stay file-references; newly-uploaded blobs during a collab session land in the repo as ordinary files at publish time, indistinguishable from any other repo asset thereafter.

### Conflict resolution: field-level only

Critical scoping decision. Resolution is at the **OAS field** granularity (one whole `{ 'VEC3' { 'NAME' "Position" } { 'DATA' ... } }` chunk), not character-level or sub-chunk-level.

Implications:

- **No `Y.Text` in v1.** All leaves — including long-form text like Forth scripts — ship as plain-string field-level LWW for v1. `Y.Map` semantics are easier to reason about and `Y.Text` has more edge cases (interleaving, formatting marks, attribute spans). v2+ flips storage to `Y.Text` for `SHOW_AS_TEXTEDITOR` leaves (see the OAD-driven widget section) so concurrent script / Notes editing becomes character-level merging without a schema migration.
- **Sub-chunks inside a field move together as an atomic group.** An I32 field's `DATA 0l` and `STR "False"` children don't merge independently; the whole field is one CRDT leaf.
- **Concurrent script editing is a soft-lock-via-awareness pattern.** If Alice is mid-edit on a Forth tick handler and Bob saves a one-char fix to the same script, Bob's version wins, Alice's edit is in history but vanishes from current state. Mitigation: Awareness shows "Alice is editing Script on House" and other clients see a lock indicator and refrain. Collaborative-norms, not technical-prevention. Fine for a small team; less fine at scale; big teams aren't v1.
- **Multi-field atomic updates** (designer drags House → changes Position and Orientation in one operation) are still two independent CRDT writes. Yjs's `doc.transact(() => { … })` bundles them into one network message but doesn't add cross-field atomicity guarantees.

---

## CRDT schema — final shape

After several iterations sharpening what is and isn't in the CRDT.

### Top-level document

```js
Y.Doc {
  meta:    Y.Map { format_version, level_name, ... },     // bookkeeping
  content: Y.Array<OBJ | COMMENT>,                         // the level
  blobs:   Y.Map<sha256 → blob-metadata>                   // out-of-CRDT binary references
}
```

The editor's mental model is "the document is a list of actors" — which is how a designer thinks about a level. The chunk tree is a serialization detail; the `LVL` wrapper does not appear in the CRDT.

### What's in the CRDT vs what's not

| Layer | Examples | In CRDT? |
|---|---|---|
| Authored content | `OBJ` actors, OAS fields, authored `//` comments | ✅ yes |
| Pipeline scaffolding | `ALGN` (CD-sector padding — see [project_align_2048_cd_sector](../../../.claude/projects/-home-will-WorldFoundry/memory/project_align_2048_cd_sector.md)), the `LVL` wrapper | ❌ no — added/stripped at serialize/parse |
| Build manifest | L4-wrapper-level `RAM { OBJD, PERM, ROOM }`, `FLAG` bits, `cd.iff` layout | ❌ no — separate per-target config |
| Binary assets | Meshes, textures, sounds | ❌ no — content-addressed blob store, referenced by SHA-256 |

### Recursive chunk node — one shape

```js
chunk = Y.Map {
  chunk_type: "OBJ" | "VEC3" | "I32" | "STR" | "FX32" | "FILE" | "BOX3" | "EULR" | "COMMENT" | ...,

  // exactly one of these two:
  children: Y.Array<chunk>,   // container (OBJ at minimum) — child chunks editable independently
  text:     "...",            // leaf (every OAS field, and COMMENT) — body as literal text

  trailing_comment: " //x,y,z",   // optional, same-line // comment
  _author: "alice",
  _ts:     1716054321,
}
```

The split between container and leaf is **exactly where field-level resolution cuts**: above (OBJ) is a container so fields edit independently; at and below (every OAS field) is a leaf so the field is atomic.

### Widget + storage selection is OAD-driven, not chunk-type-driven

The chunk_type is the IFF storage type (`STR`, `I32`, `FX32`, etc.). That doesn't have enough resolution to pick an editor widget — two `STR` fields can want very different widgets (single-line property vs multi-line script). The right discriminator is the **OAD's `showAs` field**, declared per OAS field in the object's OAD ([wfsource/source/oas/oad.h:87](../../wfsource/source/oas/oad.h), [wfsource/source/oas/iff.s:22-34](../../wfsource/source/oas/iff.s)). The enum already exists in the OAD wire format:

```
SHOW_AS_N_A          0     (no widget hint)
SHOW_AS_NUMBER       1     numeric input
SHOW_AS_SLIDER       2     range slider
SHOW_AS_TOGGLE       3     two-state
SHOW_AS_DROPMENU     4     enum dropdown
SHOW_AS_RADIOBUTTONS 5     enum radios
SHOW_AS_HIDDEN       6     not displayed
SHOW_AS_COLOR        7     colour picker
SHOW_AS_CHECKBOX     8     boolean
SHOW_AS_MAILBOX      9     mailbox-name picker
SHOW_AS_COMBOBOX    10     dropdown + free text
SHOW_AS_TEXTEDITOR  11     multi-line text editor (already used by "Cave Logic Studios Notes")
SHOW_AS_FILENAME    12     file picker
```

The editor loads the OADs for each object class on level load and looks up each field's `showAs` value to pick its widget. The CRDT leaf stays a plain `STR` — no parallel chunk type, no content heuristic, no `\\ wf` shebang inspection. The Script field can also be discriminated by NAME (`"Script"`) directly when that's simpler — both routes resolve through the OAD.

**Y.Text upgrade for collaborative text editing post-v1.** Every `SHOW_AS_TEXTEDITOR` field becomes Y.Text-eligible. Script and Notes (and any future multi-line text field marked with the existing enum value) opt into character-level concurrent editing together — they're already declared as text-editor fields in their OADs, so the upgrade is symmetric and needs no new OAD enum value. v1 ships with all `SHOW_AS_TEXTEDITOR` leaves as plain-string field-level LWW; v2+ flips storage on those leaves to `Y.Text`. No OAD/LVL binary format change at any point — the discriminator (the existing `showAs` enum) is already in the wire format.

A narrower-scope opt-in (e.g. add a new `SHOW_AS_COLLAB_TEXT = 13` to mark only specific fields as Y.Text) stays available later if there's a reason to exclude some text-editor fields from the upgrade, but it's not the planned path.

### Worked example — snowgoons `House` actor, partial

```
Doc.content = Y.Array [
  chunk { chunk_type: "OBJ",
          children: Y.Array [
            chunk { chunk_type: "NAME", text: '"House"', _author: "will", _ts: ... },
            chunk { chunk_type: "VEC3", text: '{ \'NAME\' "Position" } { \'DATA\' -0.0359..(1.15.16) 12.05..(1.15.16) -0.12..(1.15.16) }',
                                        trailing_comment: " //x,y,z",
                                        _author: "alice", _ts: ... },
            chunk { chunk_type: "EULR", text: '{ \'NAME\' "Orientation" } { \'DATA\' 0..(1.15.16) -0..(1.15.16) 0..(1.15.16) }',
                                        _author: "will",  _ts: ... },
            chunk { chunk_type: "STR",  text: '{ \'NAME\' "Class Name" } { \'DATA\' "statplat" }',
                                        _author: "will",  _ts: ... },
            chunk { chunk_type: "I32",  text: '{ \'NAME\' "Moves Between Rooms" } { \'DATA\' 0l } { \'STR\' "False" }',
                                        trailing_comment: " //False|True",
                                        _author: "bob",   _ts: ... },
            chunk { chunk_type: "FX32", text: '{ \'NAME\' "Mass" } { \'DATA\' 0.0..(1.15.16) } { \'STR\' "0.0" }',
                                        _author: "bob",   _ts: ... },
            ...
          ] },
  chunk { chunk_type: "OBJ", children: Y.Array [...] },   // next actor
  ...
]
```

### Per-leaf attribution = "replay-to-time-T" for free

Every leaf carries `_author` and `_ts`. Yjs internally maintains the op history for CRDT correctness, so replay-to-time-T over the document state is essentially free — Yjs gives you `Y.snapshot()` / `Y.snapshot.diff()` primitives that walk the op log to a target point.

This is a small architectural feature that turns into a big editor feature: history scrubber, blame view per field, attribution UI, undo-someone-else's-change-and-show-it-as-mine-now, etc.

### Editor UX — typed widgets where they help

The OAD's `showAs` per OAS field selects the widget; the chunk_type informs serialization/parsing. The mapping is opt-in and lazy:

```
SHOW_AS_NUMBER       → numeric input
SHOW_AS_SLIDER       → range slider (with declared min/max from OAD)
SHOW_AS_TOGGLE       → two-state toggle
SHOW_AS_DROPMENU     → enum dropdown (options from OAD or trailing-// comment)
SHOW_AS_RADIOBUTTONS → enum radios
SHOW_AS_HIDDEN       → not shown in property panel
SHOW_AS_COLOR        → colour picker (24-bit RGB)
SHOW_AS_CHECKBOX     → boolean
SHOW_AS_MAILBOX      → mailbox-name picker (resolves INDEXOF_* / MB_* names from mailbox.inc;
                       per feedback_named_mailbox_constants + feedback_indexof_prefix_wanted_gone)
SHOW_AS_COMBOBOX     → dropdown + free-text input
SHOW_AS_TEXTEDITOR   → multi-line text editor; v1 = plain-string LWW;
                       v2+ = Y.Text storage (character-level concurrent editing,
                       ghost cursors, per-character author attribution)
SHOW_AS_FILENAME     → file-picker pointing at the blob store
SHOW_AS_N_A          → fallback: chunk_type-driven widget choice
                       (VEC3 → vec3 spin-box, EULR → euler spin-box (revolutions),
                        BOX3 → bbox gizmo, FX32 → decimal field, ...)
(unknown / no OAD)   → fallback: monospace text field showing the raw `text` blob
```

The fallback chain `showAs → chunk_type → raw text` means the editor degrades gracefully when it doesn't have a widget for a field, and gracefully when the OAD itself doesn't provide a hint.

Fallback path means the editor handles chunk types it doesn't have a widget for yet — designers edit them as raw text. New widgets added incrementally.

### Wire / save / load

- **Load** `.iff.txt` or `.iff` → [iffcomp-rs](../../wftools/iffcomp-rs/) parser → walk to produce the `Y.Doc` tree with the splits above, dropping pipeline chunks. One-time canonicalisation pass on first import so subsequent round-trips are byte-identical.
- **Wire** = Yjs binary updates over WebSocket (variable-int encoded, much smaller than JSON).
- **Save** = walk `Y.Doc` → canonical printer emits `.iff.txt` → iffcomp-rs / wf_blender exporter handles packaging and `.blend` round-trip. **v1 trigger is a manual "Publish" button** — the slow Blender round-trip happens only when the user explicitly asks for it. Whether to add autosave-on-idle, Ctrl-S, or every-Nth-edit triggers is a question for after v1 ships, when actual usage patterns reveal what's wanted.

Format-agnostic at the edges: load from binary or text, save to either. The CRDT lives in the abstract chunk tree regardless. For debugging, `.iff.txt` is the human-readable inspection view; the actual wire bytes are Yjs's own update format.

---

## The journal / event-stream unification

A side realization during the brainstorm that turns out to be architecturally bigger than the editor itself:

The CRDT's stream of timestamped, attributed mutations is one specific kind of **timestamped event stream**. The same shape covers:

| Use case | Stream contents | Source |
|---|---|---|
| Collaborative editing | CRDT mutations on chunk tree | Network peers |
| Bug repro | Joystick + RNG seed + initial state | Player's session, uploaded |
| Regression test | Recorded golden run | CI fixture |
| Attract mode | Curated demo play | Shipped asset |
| Speedrun ghost / time-attack | Past run overlaid on current | Player's own best, or someone else's |
| Time-travel debugger | All inputs + simulated-time clock | Live capture, paused + rewound |

Architecturally this suggests treating the engine as **a deterministic function of an event stream**, where "live play" is one driver and "replay" is another driver of the same boundary. The editor's collaborative-edit stream and the engine's input stream are two flavours of the same primitive.

### Recording layer: raw HID at the HAL boundary

Three plausible record-layer choices:

- **Raw HID** (joystick bytes at the HAL → engine boundary): smallest, most general, survives input-mapping changes, survives swap of input-driver (record on Linux evdev, replay on iOS).
- **Mailbox writes** (the `INPUT` mailbox etc.): bigger; ties recording to a specific abstraction layer.
- **Engine intent** (e.g. "actor 17 wants to jump"): cleanest semantically; but you record decisions the player didn't make.

**Decision: raw HID.** Record at the HAL → engine boundary in `wfsource/source/hal/`, post-canonicalisation but pre-mailbox-dispatch. Replay re-injects at the same point.

### Determinism gotchas (relevant for replay, irrelevant for collab)

1. **Variable tick rate** is load-bearing per [project_variable_tick_rate_loadbearing](../../../.claude/projects/-home-will-WorldFoundry/memory/project_variable_tick_rate_loadbearing.md). For replay, record `(input, simulated_time_received)` tuples — playback paces input injection by sim-clock, engine simulates as fast as it likes. Determinism from "same inputs at same sim times" rather than reproducing wall-clock timing.
2. **RNG seed must be in the stream.** Audit all randomness sources (physics solver, particle systems, script `random` words).
3. **No wall-clock dependencies** for game-state purposes (`time(NULL)` for FPS counters is fine; for game logic, read sim-clock).
4. **Physics determinism.** Jolt is deterministic given identical inputs **and** identical floating-point control (no fast-math, same SIMD width across platforms). Verify before counting on it.

### v1 scope: option (c) — YAGNI middle ground

**Decision: option (c).** Build the editor-only shape, but **design the editor's protocol to look like a journal-shaped append-only timestamped event stream from day 1** (which the CRDT update protocol already mostly does — that's what CRDTs are under the hood). Don't factor out a "journal library." When gameplay-side recording is built later, build it independently with the same shape; only refactor to share if it actually pays off.

For completeness, the alternatives considered:

- **(a) Editor-only, journal infra deferred.** Same code shape as (c) but without the deliberate journal-shaping of the protocol. Loses the migration path to a shared journal abstraction without saving any cost — strictly dominated by (c).
- **(b) Editor + minimal journal infra from day 1.** Define the journal abstraction up-front; engine grows a `hal_journal` record hook; bug-repro use case works on day 1. Buys ~4 weeks more time on the v1 estimate for a feature that nobody's asked for yet. Defensible if there's a concrete near-term need (e.g. regression testing for the physics-engine swap is on the roadmap); not justified by current pressure.

**Why (c) wins:** fastest path to a shipping editor while preserving the option to build gameplay recording later as either a separate codebase with the same shape, or a refactor-to-share if symmetry materializes. The cost of "design the protocol journal-shaped" is essentially zero — the Yjs update stream IS a journal. The cost of "build a journal library now" (option b) is real, and the value of that library is speculative until there's a second consumer.

**What this means concretely for v1 implementation:**

- The CRDT-update wire protocol is already an append-only timestamped event stream — every Yjs binary update carries `(client_id, clock, op_payload)`. Don't add ceremony around this; just lean into the shape.
- When persisting to disk (relay snapshots, recovery), persist as ordered update streams + occasional state snapshots — *don't* persist as opaque current-state blobs only. That's the journal-shape commitment.
- Name things in code in terms of "events" / "updates" / "stream" rather than "edits" / "mutations" / "writes." Lexical alignment now makes future refactor-to-share painless if it happens.
- No `hal_journal` hook in the engine in v1. No "journal library" extracted. No record-to-file gameplay UI. All deferred until there's a concrete need.

---

## Future direction: editor + debugger convergence

The editor and the runtime debugger are the same surface with two data sources.

Today WF has a debug bridge (per the [Live editor bridge Phase 2](../../TODO.md) work and the existing debug-bridge in the engine) for runtime mailbox watching, breakpoints, and live-state inspection. The collaborative editor's property panels, actor outliner, mailbox-name picker, and viewport overlays are *the same widgets* a debugger surface wants — only the data source differs:

- **Design-time / authoring (this doc's scope):** widgets read from / write to the CRDT.
- **Runtime / debugging:** widgets read from / write to the running engine via the debug bridge — live mailbox values, fires when a watch trips, step through scripts, mutate actor state at runtime to test what-ifs.

The convergence is more than aesthetic: a designer mid-edit who wants to "see what this value does in play" should be able to keep their property panel open, hit Play, and watch live values flow through the same fields. Stop, tweak the design, hit Play again.

**v1 architectural constraint that protects this convergence:** the editor's widget layer must be **data-source-agnostic**. Every widget takes a generic `value-provider + value-setter` pair, not a hard-coded "read from this CRDT path" / "write CRDT op" pair. In v1 the only providers/setters are CRDT-backed. In v2+ a `EngineBridgeProvider` plugs in for runtime inspection without rewriting widgets. Small upfront cost; large optionality preservation.

**What gets built when:**

- **v1:** authoring widgets, CRDT-backed providers only.
- **v2+:** debugger-mode toggle; engine-bridge-backed providers; live-value flow; runtime mutation UI. Probably also: timeline scrubber, once the journal/replay infrastructure is built (v1 chose option (c) so the substrate doesn't ship in v1 — it lands alongside the gameplay-recording work in v2+).

The journal/event-stream unification described above is the third leg of the same stool: editor edits, runtime inputs, and debugger-time replay are three drivers of one event-stream abstraction. The editor + debugger convergence makes the journal's value proposition concrete: time-travel debugging is "scrub the journal back, observe live values in the same widgets you'd use to edit."

---

## Time estimates per milestone

All numbers are **focused-developer-weeks** — actual heads-down implementation time, not calendar weeks. Solo-developer software projects routinely overrun focused estimates by 1.5–2× in calendar time once context-switches, other work, and unknowns are factored in. **These are sketches to calibrate ambition, not commitments.** They depend heavily on the still-open v1-scope decision (a/b/c) and on the engine-linkability research outcome.

### v1 — first usable collaborative editor

The base milestone: editor opens [smb_w1_1](../../wflevels/smb_w1_1/), two designers can edit it concurrently, chat works, manual "Publish to `.blend`" closes the golden-source round-trip.

| Component | Estimate |
|---|---|
| Engine linkability (refactor `wf_game` into `libwfengine` if needed) | 1–2 weeks |
| Yrs C ABI binding via cbindgen | 1 week |
| IFF chunk ↔ `Y.Doc` translator (parser via iffcomp-rs + canonical printer) | 2–3 weeks |
| WebSocket relay (~200 LOC + snapshot/restore + blob HTTP API) | 1–2 weeks |
| Editor shell (ImGui window, engine-GL-context viewport, basic panels) | 1–2 weeks |
| Property panel + widgets (showAs-driven dispatch + ~10 widget types + data-source-agnostic provider/setter abstraction per "Future direction") | 3–4 weeks |
| Outliner / actor-tree + selection / navigation | 1 week |
| Chat sidebar (plaintext over WebSocket) | 3–5 days |
| Awareness / presence overlays (ghost cursors, selection rings, viewport ghosts) | 1 week |
| Lobby / rendezvous UI (Open dialog with the four tabs + relay URL config + room creation) | 1 week |
| Blob storage (client upload/download + manifest in CRDT) | 1 week |
| Save / Publish workflow (CRDT → `.iff.txt` → wf_blender exporter → `.blend`) | 1 week |
| File-watch engine bridge (prototype only, throwaway) | 3 days |
| Direct-read engine bridge (Yrs observers → engine scene mutations; replaces file-watch before ship) | 1–2 weeks |
| Testing, debugging, polish | 2–3 weeks |

**Total** (option **(c)**, the chosen scope): **16–22 focused weeks → 4–6 calendar months** (solo, 1.5–2× overrun).

For reference, the alternatives — neither chosen:

| Scope | Focused weeks | ≈ Calendar months |
|---|---|---|
| **(a)** editor-only, journal deferred (no protocol-shape commitment) | 16–22 | 4–6 |
| **(b)** editor + minimal journal infra (record-to-file works day 1) | 20–28 | 5–8 |
| **(c)** YAGNI middle ground ← **chosen** | 16–22 | 4–6 |

(Previous back-of-envelope estimates earlier in this doc said 6–10 / 9–14 / 6–10 weeks; those undercounted the engine-linkability work, the widget breadth, and polish/debugging. Numbers above are the more honest version.)

### v1.5 — polish + nice-to-haves

Targeted at "the v1 user feedback says…" enhancements, plus the items we already flagged for v1.5 during this design.

| Component | Estimate |
|---|---|
| mDNS / Bonjour LAN auto-discovery (SubEthaEdit-spirit) | 1 week |
| OS URL handler registration (`wfedit://` links open the editor) | 3 days |
| User-uploaded avatars (via blob store) | 3–5 days |
| Gravatar lookup integration | 2 days |
| Concurrent-script-editing soft-lock indicator UX (the TBD-in-v1 detail) | 3–5 days |
| Blob GC + per-room storage quotas (if/when storage growth justifies) | 1 week |
| Per-room signed-URL tokens for blob download (if any customer needs it) | 3–5 days |
| Real-use UX polish (open-ended) | 2–4 weeks |

**Total:** 5–8 focused weeks → 1.5–2.5 calendar months.

### v2 — the big jump

The v2 milestone bundles the upgrades that need real infra additions, not just polish.

| Component | Estimate |
|---|---|
| `Y.Text` upgrade for `SHOW_AS_TEXTEDITOR` leaves (Script, Notes) + code-editor widget integration | 1–2 weeks |
| Matrix integration ([matrix-rust-sdk](https://github.com/matrix-org/matrix-rust-sdk)) for chat / lobby / E2E / identity | 6–10 weeks |
| Synapse (or Conduit) homeserver hosting + managed-tier integration | 2–3 weeks |
| Debugger integration — engine-bridge providers plugged into the existing widget layer (the v1 abstraction pays off here); live-value flow; runtime mutation UI | 4–8 weeks |
| Journal / replay UI — v1 chose (c) so the substrate doesn't exist yet; build it now alongside the UI | 4–8 weeks |
| Room permissions, roles, admin tools (Matrix gives most of it; UI to surface it) | 2–4 weeks |
| BYOK enterprise tier — snapshot wrap/unwrap with customer-supplied KMS key | 1–2 weeks |
| Home-automation bridge as integration proof-of-concept | 1–2 weeks |
| Pricing-page polish + billing integration (Stripe-style) | 2–3 weeks |
| Polish, testing | 3–5 weeks |

**Total:** ~26–47 focused weeks → 6–14 calendar months. v2 is genuinely a big release; consider sub-versioning into v2.0 (Matrix + Y.Text), v2.1 (debugger), v2.2 (BYOK + enterprise polish) if shipping in one chunk is too ambitious.

### v3+ aspirations (not estimated in detail)

- **OAD authoring inside the editor** (per the Tier 3 possibility) — ~8–16 focused weeks. Requires deep OAD wire-format work in [wf_oad](../../wftools/wf_oad/); enables designers to iterate on schemas at design speed.
- **WASM web frontend** — ~16+ focused weeks. Requires porting the engine to WASM, which is a major separate project (engine isn't currently structured for it).
- **Voice** (via WebRTC, Matrix Voice, or Jitsi bridge) — ~4–8 weeks once Matrix is in place.
- **Mobile editor** — explicitly not pursued; mobile is a viewer/player target only.

### Honest framing

Solo-developer estimates for projects of this shape are unreliable; the right way to read the numbers is "v1 is a multi-month commitment in calendar time, v2 is a multi-quarter one." The early estimates earlier in the doc (6–10 weeks for v1) were too aggressive — they didn't price in the engine-linkability work, the widget breadth, or the inevitable debugging tail. The numbers above are more honest, still uncertain, and likely still optimistic.

---

## Open questions / decisions deferred

Tiered by what they block. Tier 1 blocks the start of implementation; tier 2 is needed before substantial work but the architecture is set; tier 3 defers until prototyping shows the real shape.

### Tier 1 — blocks the start of implementation

- **Engine linkability — Phase 0a DONE (commit `d865c40`, 2026-05-18); Phase 0b in progress, ~3 weeks remaining.** Today `wf_game` is a single `add_executable` target ([CMakeLists.txt](../../CMakeLists.txt) line 444) — every engine `.cc` file (~150+, 22 MB debug binary) compiles into the one executable.

  **Entry points are already platform-isolated.** The `main()` functions live in HAL files, not in engine core:
    - Linux: [hal/linux/platform.cc](../../wfsource/source/hal/linux/platform.cc) line 166 — `int main(argc, argv)` → `HALStart(...)`.
    - Android: [hal/android/native_app_entry.cc](../../wfsource/source/hal/android/native_app_entry.cc) line 359 — `android_main(struct android_app*)` → `HALStart`.
    - iOS: [hal/ios/native_app_entry.mm](../../wfsource/source/hal/ios/native_app_entry.mm) line 136 — `int main()` → `UIApplicationMain(...)`.

  Each platform `main` calls `HALStart` ([hal/hal.cc](../../wfsource/source/hal/hal.cc) line 47), which sets up allocators and subsystems then calls `PIGSMain` ([game/main.cc](../../wfsource/source/game/main.cc) line 314). `PIGSMain` parses the command line, constructs `WFGame`, calls `RunGameScript`. `RunGameScript` ([game/game.cc](../../wfsource/source/game/game.cc) line 153) is the outer per-level loop; `RunLevel` (line 256) is the per-frame inner loop — `while (!_curLevel->done() && ... && !HALWindowCloseRequested()) { ... render ... PageFlip ... }`. **The engine owns the frame loop**, owns its X11 connection (created in [gfx/gl/mesa.cc](../../wfsource/source/gfx/gl/mesa.cc) `OpenMainWindow` line 117 via `XOpenDisplay(NULL)` → `glXCreateContext` → `XCreateWindow`), owns the GLX context, and assumes single-instance globals (`WFGame* theGame`, `_HALLmalloc`, `halDisplay`, `gSoundEnabled`, ...).

  **Phase 0a — produce `libwfengine.a`. ✅ DONE 2026-05-18 (commit `d865c40`).** Mechanical refactor of [CMakeLists.txt](../../CMakeLists.txt); half-a-day estimate held; no surprises:
    1. ✅ `add_library(wfengine STATIC ${WF_SOURCES})` replaces the single-executable build.
    2. ✅ Per-platform shell sources (`hal/linux/platform.cc` / `hal/android/native_app_entry.cc` + `android_native_app_glue.c` / `hal/ios/native_app_entry.mm`) factored into a `WF_PLATFORM_SHELL_SOURCES` list.
    3. ✅ `wf_game` is now a thin executable with only those shell sources, linking `wfengine` for everything else via `target_link_libraries(wf_game PRIVATE wfengine)`. Engine sources reference platform-shell symbols (`FatalError`, `_PlatformSpecificInit`, etc.) as unresolved in the library; they resolve at executable link time as expected for static libraries with unresolved references.
    4. ✅ `wf_game` still builds and runs identically; symbol resolution verified (`main` in executable only; `HALStart` in library, pulled at link time; `FatalError` in executable's shell, resolves library's references).

  Phase 0a is enough for "subprocess `wf_game` with a custom level" or "host program calls `PIGSMain` from its `main`" — both useful for prototyping. It is NOT enough for the editor's "engine renders into a viewport widget the editor owns" model, because the engine still owns the window and the outer loop.

  **Phase 0b — embed-readiness, before serious editor work. ✅ ALL FOUR SUB-TASKS DONE 2026-05-18.** Estimate was ~3 weeks; actual was a single afternoon — sub-tasks #3 and #4 came in at half-day each (existing seams already in the right place), and #1 / #2 landed in parallel commit streams.
    1. **[Frame-step API](../plans/2026-05-18-engine-frame-step-api.md)** ✅ **DONE 2026-05-18** (commits `8663618`, `d6bc566`, `aa65b79`, `0be94a5`, `c844f4a`, `47ef7cc`). `WFGame::RunLevel`'s `while` body extracted into `WFGame::StepFrame(do_swap, out_dt)`; loop predicate uses new `LevelDone()` / `ContinueRequested()` accessors; per-level setup/teardown extracted into `LoadLevel` / `UnloadLevel`. `Display::MeasureDelta()` factored out of `PageFlip` so `do_swap=false` callers can still recover deltaTime. ≤100 ms clamp on `_deltaTime` keeps the simulation stable after host stalls (editor pause-on-modal). `--frame-step-smoke=N` CLI flag drives the new entry points from a non-`RunLevel` path for verification + reference shape.
    2. **[Externally-supplied GL context](../plans/2026-05-18-engine-external-gl-context.md)** ✅ **DONE 2026-05-18** (commits `151e2fe`, `2193f77`, `50807a9`, `a68b119`, `3f80c58`, `a816e3b`). `gfx/host_gl_context.h` opaque (void*) interface; `mesa.cc:InitWindow` dispatches on `GetHostGLContext().valid` to either `OpenMainWindow` (standalone) or `InitWithExistingContext` (host-owned). `HALCloseWindow` + `XEventLoop` early-bail in host-owned mode. `HALRequestClose()` lets the host trigger the existing close-flag path. Smoke test at `engine/wf_host_gl_test/`. Linux-only for v1; iOS / Android stub as planned.
    3. **Editor-driven input injection** ✅ **DONE 2026-05-18** (commit `b0639c5`). Came in under estimate (~half a day) because the platform-internal `_HALSetJoystickButtons` setter already existed as the right boundary across all three platforms. Added a public C++ wrapper `HALInjectJoystickButtons(joystickButtonsF)` declared in [hal/_input.h](../../wfsource/source/hal/_input.h) and implemented on Linux / Android / iOS. Hosts (editor, replay driver, test harness) feed button state directly; the existing platform event loops keep working unchanged when no host is driving input. Symbol verified exported from `libwfengine.a`. The other half of "editor owns input fully" — making the engine's `XEventLoop` optional — is part of sub-tasks #1 (frame-step API) and #2 (externally-supplied GL context).
    4. **De-global `WFGame`** ✅ **DONE 2026-05-18** (commits `1a957f7` + `89bcb58`). Half-day estimate held; turned out to be three sub-tasks of which only the first was real work:
        - **#4a** (`1a957f7`) — drop the `WFGame* theGame` extern. Only 2 actual call sites in the entire engine: `theGame->MessagePortMemPool()` at [level.cc:268](../../wfsource/source/game/level.cc) (now `_game.MessagePortMemPool()` via a `WFGame&` reference threaded into `Level::Level`) and `theGame->GetLevelNum()` at [actor.cc:142](../../wfsource/source/game/actor.cc) (now reads a file-scope static set by `Actor::SetPrintLevelNum`, called from `Level::Level`, gated on `SW_DBSTREAM`).
        - **#4b** (`89bcb58`) — `gSoundEnabled` and `gCDEnabled` turned out to be **dead write-only globals** (set by `-sound` / `-cd` CLI flags, never read by anything). The doc's plan to "move them into a `WFGame` instance member" was misframed — there was no state to move. Deleted the globals + the CLI handlers + the lone unused extern. Updated the doc example in [coding-conventions.md](../coding-conventions.md) since it referenced the now-deleted symbols.
        - **#4c** — *no work needed.* The plan to "move CLI flags into a `WFGameConfig` struct" was speculative. Checking the actual `WFGame` constructor showed it already takes a single `int nStartingLevel` parameter — there are no WFGame-specific globals to bundle. The other CLI flags in [main.cc](../../wfsource/source/game/main.cc) (memory sizes, window dimensions, debug ports) are HAL / debug-subsystem config and belong with the process-scoped HAL globals (per the next paragraph). Multiple `WFGame` instances can already be constructed with different `nStartingLevel` values in the same process.

  **HAL globals stay process-scoped, deliberately.** `_HALLmalloc` (21 sites) and `halDisplay` (44 sites) remain process-wide — they're properly process-level (one allocator, one window/display per process), not game-level singletons. Most C++ programs have one process allocator and one main window; that's fine. Multiple `WFGame` instances *share* one HAL, which is exactly the right model for the future "two viewports into the same scene" use case (multiple game states rendered into one window) without the multi-window complexity.

  **Verdict.** The engine is *closer* to library-shaped than its single-executable build suggests — `main` is already platform-factored, `PIGSMain` / `HALStart` are functions, `WFGame` is a class. The two friction points are (a) the engine owns the outer loop and (b) the engine owns the window; both are fixable surgically. **Plan:** Phase 0a immediately when editor work starts (unblocks linking from a host process; costs essentially nothing). Phase 0b before the file-watch prototype gives way to direct-CRDT-read — file-watch tolerates the engine owning the window because the engine's own window IS the viewport during prototype phase; direct-read can't.

### Tier 2 — needed before substantial implementation

- **Engine ↔ CRDT bridge mechanism.** Direct read (editor owns the Y.Doc, observes CRDT events, translates ops into engine API calls) vs file-watch (CRDT serializes to a derived `.iff`; engine reloads on change). **Locked in 2026-05-19: editor owns the Y.Doc, engine stays Rust-free, engine exposes a plain C++ mutation API that the editor's CRDT bridge drives.** Same surface serves DAP debugger + replay UI + headless test harness, not just the editor. File-watch remains as a prototype-phase shortcut only.

  **Yrs C ABI binding landed 2026-05-19** (plan [docs/plans/2026-05-18-yrs-c-abi-binding.md](../plans/2026-05-18-yrs-c-abi-binding.md)) — `WF_ENABLE_CRDT=ON` builds `libwfcrdt.a` (wrapping `libyrs.a` from y-crdt's yffi crate via Corrosion + Cargo). Default OFF, so shipped game binaries (iOS / Android / Codemagic CI) stay byte-identical and Rust-free. `wfcrdt_smoke` exercises Doc/Map/Array round-trip + Yjs wire-format state-diff compat + observer registration.

  **C++ RAII wrapper landed 2026-05-19** (plan [docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md](../plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md)) — `engine/crdt/wfcrdt.hpp` gives the editor's CRDT bridge `wfcrdt::Doc / Transaction / Map / Array / Output / Subscription` instead of raw `YDoc*` / `YTransaction*` / `Branch*` handles. Move-only types, auto-commit on scope exit, `std::optional` for type-mismatch reads, heap `std::function` trampoline for observers. ASan-clean.

  **Latency budget:** the file-watch round-trip is `serialize .lev (~10 ms) + levcomp-rs (~50–200 ms) + iffcomp-rs (~50–200 ms) + engine reload (100s of ms)` — roughly **0.5–2 s per edit**, depending on level size. That's acceptable for "I moved an actor; where did it land?" but painful for slider scrubs, drag-to-position, colour pickers, and anything else that wants sub-100 ms feedback.

  **Mitigations that narrow the file-watch gap** (but don't close it):
    - *Debounce + coalesce* edits during a drag — re-export at 100 ms intervals instead of per event. Gets slider scrub from "unbearable" to "noticeably laggy."
    - *Incremental engine reload* — teach the engine to apply per-actor patches instead of tearing down/rebuilding the whole level. Substantial engine work; probably half the cost of just doing direct read.
    - *Cheap drag preview* — editor draws ghost-outline during interaction, only commits the real engine-view update on drag-end. Keeps interaction snappy at the cost of "engine view lies during a drag."

  **Direct-read cost:** Yrs has a C ABI via cbindgen; the binding plumbing is now landed (`libwfcrdt.a` smoke-test green). The C++ RAII wrapper [landed 2026-05-19](../plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md) (~1 h vs ~2–3 d estimate). The [engine mutation API](../plans/2026-05-19-engine-mutation-api.md) also landed same day (~3 h vs ~1–2 wk estimate) — `wfmut::SetActorField` / `SpawnActor` / `RemoveActor` / `SetMailbox` / `SetActorPos` / `SetActorOrientation` / `ReloadActorScript` with `lastError()` diagnostics; `engine/stubs/debug_server.cc`'s mutation cases all route through it. Remaining piece: IFF↔Y.Doc translator (~2–3 wk). Pays off for the editor's whole life (microsecond per-op feedback, no debounce engineering).

  **Plan:** prototype with file-watch for the first few weeks (proves the data path; reuses existing reload infrastructure; smb_w1_1 is small enough that 1–2 s round-trip will be tolerable for early dev). Switch to direct read before shipping v1 once the data path is settled.
- **Persistence model for the relay — researched: Yjs binary state on local disk, debounced snapshots, hibernation IS a snapshot, BYOK-ready wrap hook from day 1.**

  **Snapshot format: Yjs binary update, not `.iff.txt`.** [`Y.encodeStateAsUpdate(doc)`](https://docs.yjs.dev/api/document-updates) is the native Yjs format — compact, preserves the full op log + per-leaf `_author` / `_ts` attribution, restore is `Y.applyUpdate(newDoc, bytes)`. A `.iff.txt` round-trip is **not** a snapshot format: it captures current state but loses CRDT history (attribution, op-by-op scrubbing, undo-someone-else's-edit). `.iff.txt` is a **publish target** (the human-readable inspection / git-checkin / engine-load format), not a recovery format. Keeping the two roles distinct avoids the trap of "if we just snapshot `.iff.txt` we get debuggable files for free" — that path silently throws away the editor's most architecturally distinctive feature.

  **Snapshot interval: debounced + max-wait.** Match the [Hocuspocus default](https://hocuspocus.dev/api/extensions/database#default-configuration) shape: write after 2 s of edit-quiet, force-flush after 10 s of continuous activity. Per-room debounce; bursty editing on one room doesn't stall snapshots on another. Writes are async, fire-and-forget from the relay's WebSocket handler — no separate snapshot process, no extra TCP connection.

  **Storage location, three tiers (all running the same relay binary):**
    - **Free self-host:** local disk (`./rooms/<room-uuid>.ydoc`) in the relay's working directory. Backups are the operator's problem; document the path so they can `rsync` it.
    - **Free community relay:** local disk on our VPS + nightly object-storage push (S3 / [Backblaze B2](https://www.backblaze.com/cloud-storage) / [Cloudflare R2](https://www.cloudflare.com/developer-platform/products/r2/) — all S3-compatible, all commodity, no lock-in per the hosting-tier no-cloud-vendor-lock-in argument).
    - **Paid managed:** local disk + continuous backup (every snapshot also written to object storage). Per-customer separate bucket. Off-site backup for the paid tier needs an actual durability SLA — pick the SLA before pricing.

  **Recovery semantics on restart.**
    1. Relay scans `./rooms/` on boot.
    2. For each room file: load the latest snapshot via `Y.applyUpdate(newDoc, bytes)` into memory.
    3. **Corruption fallback:** keep N=3 generations (`<uuid>.ydoc`, `<uuid>.ydoc.1`, `<uuid>.ydoc.2`); rotate on each successful write. Try generations in order on load failure. Object storage backup is the last fallback.
    4. **Missing snapshot:** room starts empty. If the room UUID maps to a level file in the repo (`meta.level_path`), auto-initialise from the `.iff` on first join — same code path as "auto-create on first level open" in the rendezvous section.

  **Hibernation = cheap snapshot, not a separate path.** Room hibernation (per the room-lifecycle section) just IS the snapshot mechanism. When the last participant leaves after N minutes of inactivity, write current state to disk, evict from memory. Reactivation on next join restores from snapshot. No separate "hibernation file" vs "snapshot file" format — same `.ydoc` either way. Hibernation differs from the periodic snapshot only in eviction policy.

  **Storage growth + compaction.** Yjs op logs grow forever unless compacted; `Y.encodeStateAsUpdate(doc)` produces a single compact state vector that supersedes prior history. Trade-off: per-leaf `_author` attribution survives compaction, full op-by-op scrubbing past the compaction point does not.
    - **Active rooms:** compact daily off-peak, or every K=10 000 edits, whichever comes first.
    - **Archived rooms:** compact aggressively on hibernation. The canonical long-term record is the `.blend` / `.iff` published to the repo, not the CRDT — the CRDT is *working* state, not authoritative archive. Loss of scrubbing on cold rooms is acceptable; the publish artefacts are forever.
    - **Per-room storage cap** (community relay): hard cap (e.g. 100 MB) per room; on hit, force-compact, then refuse further edits with a "this room is full, please publish + start fresh" banner. Stops a runaway room from filling the disk.

  **BYOK hook from day 1, even though the feature ships in v2+.** The snapshot writer takes a `wrap: bytes → bytes` function pointer; default tier passes identity, BYOK tier passes "encrypt with customer's KMS-managed key." Symmetric `unwrap` on load. Adding the parameter from day 1 costs one struct field; retrofitting later means re-encrypting every existing snapshot. Recommend designing the interface with the identity wrap in v1, even though BYOK ships in v2+.

  **Plan: roll our own ~200 LOC over [Yrs](https://github.com/y-crdt/y-crdt), not adopt [Hocuspocus](https://hocuspocus.dev/).** Hocuspocus is Node-only; the relay should be Rust for op-footprint reasons (single static binary, no Node runtime to manage on tiny VPSes). Yrs in Rust = same Yjs protocol on the wire, much smaller deploy. Persistence is straightforward bytes-to-file with the debounce shape above. Hocuspocus stays as the reference for protocol details we can copy.

  **Not pursued:**
    - **Database backend** (Postgres / Redis / LevelDB). Snapshots are bounded-size opaque blobs; SQL/KV adds operational complexity for no benefit at our scale. Hocuspocus has Postgres / Redis providers; we don't need them.
    - **Object storage as primary** (without local disk). Object-store write latency (~100 ms for small puts) bites the debounce loop; users would feel hiccups on every snapshot. Local disk primary, object storage backup.
    - **At-rest encryption without BYOK.** E2E client-side encryption is a v2 Matrix-time concern (relay can't fan out updates without seeing plaintext today). Encrypting snapshots at rest with a server-side key buys little — an attacker with relay memory access already wins; an attacker with disk-only access is a non-threat-model.

### Tier 3 — defer until prototyping

- **Schema versioning + migration mechanism.** `meta.format_version` bump-on-breaking-change is the shape; migration scripts not designed yet. Needed before the second-ever schema change, not before v1 ships.
- **Awareness scope.** Selection + viewport camera + chat-typing at minimum; "soft-lock indicator on this actor by this user" possibly. Easy to grow incrementally.
- **Concurrent `SHOW_AS_TEXTEDITOR`-field editing UX.** v1 = soft-lock-via-awareness on plain-string LWW. Indicator prominence (toast banner? side-by-side diff if someone overwrites?) is TBD. v2+ swaps storage to `Y.Text` per the decision above.
- **Public-rooms default on the community relay.** Public-discoverable by default vs invite-only-with-opt-in-to-public. Probably invite-only by default; confirm closer to launch.
- **Pricing model for managed relays.** Per-relay-flat / per-active-user / per-MB-stored / tiered. Defer to closer to launch.
- **OAD authoring inside the editor (possibility, not committed).** Today OAD schemas (what fields each actor class has, their types, min/max, `showAs`) live in `iff.s` source files and are compiled separately. A future direction: let designers edit OADs in the same editor they use to author instances — add a new field to an actor class, tweak a slider's max, declare a new enum value, all without dropping out to `iff.s` + recompile. Big leverage if it pays off (designers iterate on schemas at design speed, not engineering speed); also a big scope expansion (the OAD wire format is non-trivial; existing OADs in `wftools/wf_oad/tests/fixtures/*.oad` need to round-trip). Worth exploring once the editor + debugger convergence above is more concrete.

---

## Cross-references

- [feedback_blender_golden_source](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_blender_golden_source.md) — Blender `.blend` is golden source; the editor's "save" must close the round-trip to `.blend` for shipped levels.
- [project_align_2048_cd_sector](../../../.claude/projects/-home-will-WorldFoundry/memory/project_align_2048_cd_sector.md) — why ALGN chunks exist; why they're a pipeline concern not an authoring concern.
- [project_variable_tick_rate_loadbearing](../../../.claude/projects/-home-will-WorldFoundry/memory/project_variable_tick_rate_loadbearing.md) — variable dt is load-bearing; affects determinism for replay-side features.
- [feedback_angles_in_revolutions](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_angles_in_revolutions.md) — euler-picker widget for EULR fields edits in revolutions, not degrees/radians.
- [feedback_named_mailbox_constants](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_named_mailbox_constants.md) — script-edit widget should respect `INDEXOF_*` names (and the upcoming `MB_` rename per [feedback_indexof_prefix_wanted_gone](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_indexof_prefix_wanted_gone.md)).
- TODO entry: [Research: Qt as the UI toolkit](../../TODO.md) under § TOOLS.
- Tooling that this design leans on: [iffcomp-rs](../../wftools/iffcomp-rs/), [wf_blender](../../wftools/wf_blender/).
- External: [Yjs](https://github.com/yjs/yjs), [Yrs](https://github.com/y-crdt/y-crdt), [pycrdt](https://github.com/jupyter-server/pycrdt), [hocuspocus](https://hocuspocus.dev/), [SubEthaEdit](https://www.codingmonkeys.de/subethaedit/), [Dear ImGui](https://github.com/ocornut/imgui), [Qt](https://www.qt.io/), [Egui](https://www.egui.rs/).
