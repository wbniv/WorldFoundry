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

Open the editor in **two separate browser windows** (separate windows/profiles, **not** two
tabs in one window — see the gotcha below) on the **same room**:

[http://localhost:8081/wf-edit.html?room=demo&relay=ws://localhost:9900](http://localhost:8081/wf-edit.html?room=demo&relay=ws://localhost:9900)

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

- **⚠ Don't run two peers as two tabs in one browser window.** The editor services the relay +
  WebRTC signaling from its per-frame `requestAnimationFrame` loop, and browsers **throttle/pause
  rAF in a background (non-focused) tab** — so the inactive tab stalls its networking and its peer
  connection won't establish/flow reliably (verified: a background second tab registered *no peer*
  at all). This is **not** about the camera. Run each peer in its **own browser window** (keep both
  visible), its **own profile/process** (`--user-data-dir=…`), or **two machines**. The headless
  fake-camera peer works precisely because it's a separate full-speed process.
  *(Follow-up: decouple the relay/WebRTC servicing from the rAF loop so background tabs stay live.)*
- **`localhost` is a secure context**, so `getUserMedia` (camera/mic) works. A **LAN IP does
  not** — browsers block camera/mic over plain `http://` on non-localhost; that path needs
  HTTPS (e.g. the deployed `wss://wf.worldfoundry.org` + an HTTPS-served editor).
- **Joining as a viewer (no camera)** — on the **web** build the mic and camera are **off by
  default** and aren't opened until you click **Unmute mic** / **Cam on**, so joining as a
  viewer/listener is just the default — no flag needed. (`WF_COLLAB_NO_CAM` is a **native-only**
  env var: the *native* editor opens `/dev/video0` at startup, so that flag suppresses it; it has
  no effect on the web build, where nothing opens a device until you click.)
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
