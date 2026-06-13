# Testing the web editor (`wf_edit_web`) locally

How to build, serve, and exercise the browser build of `wf-edit` — co-edit, presence,
text chat, and **voice + video** — on one machine. See
[wf-edit-manual.md → Running in the browser](wf-edit-manual.md#running-in-the-browser-wasmwebgl2)
for what it is; this is the run-it-yourself recipe.

## 1. One-time toolchain setup

The CRDT + levtree layers cross-compile from Rust to `wasm32-unknown-emscripten`, which
needs an isolated rustup toolchain (the distro Rust can't target it):

```bash
task dev-setup-web-edit
```

## 2. Build

```bash
task build-web-edit          # → build-web-edit/wf-edit.{html,js,wasm,data}
```

## 3. Start a local relay + web server

Co-edit / presence / chat / A/V all flow through a `wf-relay` WebSocket server. For a
local test, run the relay binary and serve the build dir:

```bash
# relay (build once with: cargo build --release --manifest-path wftools/wf_collab/Cargo.toml)
wftools/wf_collab/target/release/wf-relay --port 9900

# web server (separate terminal) — or: task serve-web-edit  (also :8081)
python3 -m http.server 8081 --directory build-web-edit
```

## 4. Open two peers

Open **two browser windows** (or tabs) to the **same room**:

```
http://localhost:8081/wf-edit.html?room=demo&relay=ws://localhost:9900
```

Query params: `room=<id>` and `relay=<ws-url>` join a co-edit room; omit both for
local-only. Also `leveltree=<preloaded .lev>`, `level=<preloaded .iff>`, and repeatable
`wfenv=KEY=VAL` (sets an Emscripten env var — drives the `WF_EDIT_*` / `WF_COLLAB_*` hooks).

What to try:
- **Presence + co-edit** — each window shows the other as a peer in the **Collaborators**
  panel; move/edit an actor in one and it syncs live to the other. A window that joins after
  the room exists *adopts* the current level (join-and-receive), so both see the same actors.
- **Text chat** — the Chat panel round-trips between the windows.
- **Voice + video** — click **Unmute mic** and **Cam on** in each window's Collaborators
  panel, then grant the camera/mic permission. Each window's video shows as a tile over the
  other's panel thumbnails, and you hear audio. The per-peer audio meter animates with voice.

## Gotchas

- **Two tabs sharing one webcam can conflict** — the OS may let only one tab open the camera,
  so two-way *video* in one browser may be one-sided. **Audio + co-edit + presence + chat work
  two-tab.** For clean two-way video use **two different browsers** (Chrome + Firefox), two
  browser **profiles**, or two machines.
- **`localhost` is a secure context**, so `getUserMedia` (camera/mic) works. A **LAN IP does
  not** — browsers block camera/mic over plain `http://` on non-localhost; that path needs
  HTTPS (e.g. the deployed `wss://wf.worldfoundry.org` + an HTTPS-served editor).
- **Camera-less / "join as viewer"** — set `wfenv=WF_COLLAB_NO_CAM=1` (or env on native) to
  join without opening the webcam at all; you still see/hear others.
- **Native interop** — a native `wf-edit --room=demo --relay=ws://localhost:9900` joins the
  same call; audio interoperates with browser peers (display of *remote* video on the native
  side has a known bug — see TODO).

## Testing without a real camera (and how CI verifies it)

Launch a window with Chrome's fake-media flags + autostart — a synthetic test-pattern video
and beep, permission auto-granted:

```bash
google-chrome --use-fake-device-for-media-stream --use-fake-ui-for-media-stream \
  "http://localhost:8081/wf-edit.html?room=demo&relay=ws://localhost:9900&wfenv=WF_COLLAB_AV_AUTOSTART=1"
```

`WF_COLLAB_AV_AUTOSTART=1` turns mic+cam on automatically once a peer connects. This is the
basis of the **headless** verification: two such Chrome processes driven over the Chrome
DevTools Protocol (a dependency-free Node script — `Target.createTarget`/`Runtime.evaluate`),
asserting `getStats()` shows inbound audio+video RTP both ways and the overlay `<video>` is
positioned over the panel. (Run two *separate* Chrome processes — a background `createTarget`
tab pauses its rAF loop; each needs its own `--user-data-dir`.)

## Cleanup

Stop the relay and web server when done:

```bash
pkill -x wf-relay
# stop the python http.server (Ctrl-C in its terminal, or kill its PID)
```
