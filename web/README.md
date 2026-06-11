# wf_game — web (Emscripten / WebGL 2) build

Browser build of the World Foundry engine: C++ → WebAssembly via Emscripten,
rendering through WebGL 2 (the engine's GLES 3 path). Single-threaded, no
SharedArrayBuffer — so **no COOP/COEP headers are required**.

Plan: [docs/plans/2026-06-11-web-canvas-port.md](../docs/plans/2026-06-11-web-canvas-port.md) ·
Feasibility: [docs/investigations/2026-06-11-web-canvas-embedding.md](../docs/investigations/2026-06-11-web-canvas-embedding.md)

## Build & run locally

```sh
task build-web      # emcmake cmake -B build-web && cmake --build  (needs task setup-emsdk first)
task serve-web      # python3 -m http.server 8080  → http://localhost:8080/wf_game.html
```

Outputs into `build-web/`:

| File | What |
|------|------|
| `wf_game.html` | the custom shell (`web/shell.html`) — click-to-start, load progress, level selector |
| `wf_game.js`   | Emscripten glue (~123 KB, ~33 KB gz) |
| `wf_game.wasm` | engine + Jolt + zForth + miniaudio (~3.1 MB, ~0.98 MB gz) |
| `wf_game.data` | preloaded level(s), mounted into MEMFS at `/` |

## Choosing a level

The shell selects the level via a query string — one build fronts many levels:

```
wf_game.html?level=snowgoons-standalone     ← default is moon_site01-standalone
```

The named file must be in the build's `--preload-file` set (see the `EMSCRIPTEN`
block in `CMakeLists.txt`). **Use the `-standalone` level variant** (a complete
`L`-chunk the `-L` loader reads directly), not the `LVAS` asset-bundle `.iff`.
The engine parses the switch as one joined token — `-L<path>`, never `-L <path>`.

## Embedding in another page / iframe

```html
<canvas id="canvas" width="1280" height="720"></canvas>
<script>Module = { canvas: document.getElementById('canvas'),
                  arguments: ['-L/snowgoons-standalone.iff'] };</script>
<script src="wf_game.js"></script>
```

## Deploy (Cloudflare Pages)

```sh
task bundle-web     # stages the 4 artifacts + index.html into dist/web/
```

`dist/web/` is a complete static site. Deploy it to the existing worldfoundry
Cloudflare Pages project (separate repo) by either:

- **Dashboard:** drag-drop `dist/web/` into the Pages project's upload, or
- **Wrangler:** `wrangler pages deploy dist/web --project-name <worldfoundry-pages>`

No special configuration is needed — static files, `$0` on the free tier.
The `.wasm` must be served as `application/wasm` (Pages does this automatically).

## Per-level engine args

Some levels need extra engine switches. The shell carries a small per-level
arg map (`LEVEL_ARGS` in `shell.html`) so the right switches go through
`Module.arguments` automatically. **moon_site01** needs a wider VRAM box +
transient texture slot for its 1024² NAC terrain texture
(`--vram-width=4096 --vram-height=2048 --vram-slot-width=1024 --vram-slot-height=1024`,
matching native `task run-moon`); without them the texture overflows the slot
(`texture.cc:74`). This is **not** web-specific — native needs the same flags.

## Known limitations

- v1 uses `-sASYNCIFY` for the blocking main loop; **v2 (Phase 7)** replaces it
  with `emscripten_set_main_loop`. See the plan.
