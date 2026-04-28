# Plan — Blender plugin: licensed-asset browser & importer

## Context

The `docs/investigations/2026-04-28-level-construction-tooling.md` Seam 5 specifies an asset-sourcing system with provider abstractions, per-asset `manifest.json`, project-level `licence_policy.toml` (structured `[[licence]]` records with `id` / `status` / `reason`), and a Blender plugin that searches across providers with the policy as a hard filter. Phase B and Phase D of the investigation cover the Rust crate side and the plugin side respectively. The user's request is the *plugin* deliverable, with the licence-policy schema we just defined as the filter input.

What exists today (verified by exploration):

- `wftools/wf_blender/` is an OAD-driven Blender plugin (operators.py, panels.py, export_level.py, ~2000 LOC). Synchronous, local-file-only — no HTTP code, no async patterns, no preview/thumbnail support, no `bpy.ops.import_scene.*` callsites (mesh import is via WF's custom binary IFF format).
- `wftools/levcomp-rs/` exists but has no licence-checking logic.
- `wftools/wf_asset_provider/` does **not** exist (specced only).
- `wftools/wf_audit/` does **not** exist (specced only).
- No `licence_policy.toml` file exists anywhere in the repo.
- No `manifest.json` with the `licence_id` schema exists.
- No TOML library is currently a dependency (Python or Rust side).
- `bpy.utils.previews` is unused.

Decisions confirmed via clarifying questions:

- **v1 provider scope: CC0-only.** Poly Haven, Kenney, AmbientCG, Quaternius CC0 packs, OpenGameArt CC0 subset. All key-less HTTP, all CC0 default. Sketchfab + commercial deferred to v2 (API-key UX is a separate workstream).
- **Policy location: project-level.** Single `wflevels/licence_policy.toml`. Plugin walks up from the current `.blend` file's directory until it finds one. Per-level overrides deferred to v2.

## Outcome

A Blender designer hits "File → Import → WF Asset Browser", types a query (`tree`, `barrel`, `lava-rock`), the plugin fans out across the configured providers in parallel, the policy filter strips results whose `licence_id` doesn't have a matching `[[licence]]` entry with `status = "accept"`, surviving results render as a thumbnail catalog (rate-limited, async, with placeholder images while loading), the designer picks one and clicks "Import", the plugin downloads the asset to `wflevels/<level>/assets/<provider>/<asset-id>/`, writes a `manifest.json` alongside it (full provenance: `licence_id`, `attribution_required`, `attribution_string`, `licence_url`, `provider`, `provider_id`, `download_date`, `original_url`, `derived_from = []`), invokes Blender's native glTF importer, places the imported mesh at the 3D cursor, and attaches a default OAD schema (`statplat` for static meshes; user can re-attach via the existing `wf.attach_schema` operator).

The Rust `wf_asset_provider` crate is **in scope** and built up-front, not punted. Two reasons: (a) the licence-mapping table (provider raw response → canonical `licence_id`) is the bug-prone part of this work and wants a single source of truth — doing it once in Rust and binding to Python via `pyo3` avoids the duplicate-implementation tax that Phase B (`wf_audit`) and `levcomp-rs`'s licence gate would otherwise pay; (b) the precedent already exists — the existing Blender plugin already loads `wf_core.so` (a Rust extension built via the same `pyo3` path), so the toolchain and packaging story are solved. Doing it twice (Python in plugin + Rust in CLI later) would mean two implementations to maintain, two licence-mapping codepaths to keep in sync, and two places where a provider API change breaks something. The "extract later" promise rarely lands once Python works.

The audit tool (`wf_audit`, Phase B) is still out of scope of *this* plan, but it consumes the same Rust crate when it lands. The crate ships with both `pyo3` Python bindings (for the plugin) and a thin CLI binary (`wf-asset search ...`, `wf-asset download ...`) so CI scripts and the eventual audit tool can use it without touching Python.

## Files to create

```
wftools/wf_asset_provider/      NEW Rust crate. Single source of truth for provider HTTP, licence-mapping, and download logic. Built once, used by both the Blender plugin (via pyo3 bindings) and CLI / future wf_audit tool.
├── Cargo.toml                  Deps: reqwest (HTTP), serde + serde_json (JSON), pyo3 (Python bindings, optional feature), clap (CLI), tokio (async runtime), thiserror (error types).
├── src/
│   ├── lib.rs                  Crate root; re-exports the provider trait + the canonical licence enum + AssetCandidate / Manifest types.
│   ├── licence.rs              Canonical `LicenceId` enum (CC0_1_0, CC_BY_4_0, CC_BY_SA_4_0, GPL_3_0, ...) and the licence-mapping table that turns each provider's raw response into a canonical ID. **The single source of truth for provider-string → canonical-ID translation.**
│   ├── candidate.rs            AssetCandidate struct (provider, provider_id, title, thumbnail_url, licence_id, download_url, original_url, attribution_string, attribution_required).
│   ├── manifest.rs             Manifest struct + serde_json serialiser. write_manifest(path, fields) is the single canonical writer.
│   ├── policy.rs               licence_policy.toml reader. Walks up from a given path to find policy. Same fallback-to-CC0-only behaviour as planned. Uses `toml` crate.
│   ├── http.rs                 Shared reqwest client with per-provider rate limiter (governor crate or hand-rolled token-bucket); retry-with-backoff helper.
│   ├── provider.rs             `Provider` trait: `async fn search(&self, query: &str, accept: &PolicyFilter) -> Result<Vec<AssetCandidate>>; async fn download(&self, candidate: &AssetCandidate, dest: &Path) -> Result<(PathBuf, Manifest)>;`.
│   ├── providers/
│   │   ├── mod.rs              Provider registry; each sub-module registers via inventory crate or explicit list.
│   │   ├── polyhaven.rs        https://api.polyhaven.com/ adapter. All assets CC0.
│   │   ├── kenney.rs           Static curated catalog (baked-in `catalog.json` resource) + ZIP download. No live search API.
│   │   ├── ambientcg.rs        https://ambientcg.com/api/v2/full_json adapter; filtered to CC0 1.0.
│   │   ├── quaternius.rs       Static curated catalog like kenney.rs.
│   │   └── opengameart.rs      Unofficial JSON API adapter; CC0 subset only; flagged as "lower trust" (lower-trust flag also surfaced through to the plugin UI).
│   ├── pybind.rs               pyo3 bindings exposing search() / download() / load_policy() to Python. Behind a `python` feature flag so the CLI binary doesn't pull in libpython.
│   └── bin/
│       └── wf_asset.rs         CLI binary (`wf-asset search "tree" --provider polyhaven`, `wf-asset download <id>`, `wf-asset audit <level-dir>`). Used by CI and (eventually) wf_audit. Not used by the plugin directly.
└── tests/
    └── licence_mapping.rs      Unit tests: each provider's canonical raw-response samples → expected `LicenceId`. The bug-prone part of the system; tests are the gate.

wftools/wf_blender/
├── asset_browser.py            New. WF_OT_browse_assets operator + WF_PT_asset_browser panel + WF_OT_import_asset operator. Calls into the Rust crate via `import wf_asset_provider`. Owns the Blender-side UI (UIList, PropertyGroup, bpy.utils.previews thumbnail cache, async timer/queue glue).
├── asset_threading.py          New. Thin shim that bridges Blender's main thread + a Python ThreadPoolExecutor calling into the (sync) pyo3-bound Rust functions; uses `bpy.app.timers` to drain the result queue back onto the main thread.
└── (no separate Python providers/ dir — the Rust crate owns provider logic.)

wflevels/
└── licence_policy.toml         New. Seed file with v1 schema (CC0 accepted, share-alike + GPL + editorial-only + royalty-on-revenue rejected). Hand-authored once; thereafter tool-managed via `wf-asset policy add` (subcommand of the new CLI binary; replaces the previously-mooted `wf-licence` separate tool).
```

## Files to modify

```
wftools/wf_blender/
├── __init__.py                 Modify. Register the new operators (WF_OT_browse_assets, WF_OT_import_asset) and the new panel (WF_PT_asset_browser). Add the "File → Import → WF Asset Browser" menu entry via `bpy.types.TOPBAR_MT_file_import.append`.
└── operators.py                No changes expected. New operators live in asset_browser.py.

docs/investigations/2026-04-28-level-construction-tooling.md
                                Modify. Phase D's "Blender brief-import operator" entry is unchanged; ADD a new bullet under Seam 5 §4 ("Filter UI in the Blender plugin") cross-referencing this plan's deliverable. Update Phase B to note the plugin v1 ships before the Rust asset-provider crate (which is now optional / Phase B-deferred).
```

## Design

### Architecture

**Three-layer split.** The Rust crate owns provider logic + licence mapping + manifest writing + policy reading + the CLI. The Blender plugin owns the UI (UIList, panels, thumbnail rendering, the import-into-the-scene step). A thin Python shim layer bridges Blender's main thread to the (sync, blocking) pyo3-exported Rust functions via a `ThreadPoolExecutor` + `queue.Queue` + `bpy.app.timers.register(...)` pump.

```
┌─ Blender main thread ──────────────────────────┐
│  asset_browser.py: panel, UIList, operator,     │
│  bpy.utils.previews thumbnail cache             │
└──────────┬─────────────────────────────────────┘
           │ submit search/download via
           │ asset_threading.py (ThreadPoolExecutor)
           ▼
┌─ Python worker threads ────────────────────────┐
│  Each worker calls into the pyo3-bound Rust    │
│  functions: wf_asset_provider.search(...) etc. │
│  Result queued back to main via queue.Queue.   │
└──────────┬─────────────────────────────────────┘
           │ pyo3 sync call
           ▼
┌─ Rust crate (wf_asset_provider) ────────────────┐
│  Provider trait, reqwest HTTP, licence mapping,│
│  manifest writer, policy reader, rate limiter, │
│  retry/backoff. Tokio used internally for      │
│  per-provider concurrency; the pyo3 surface    │
│  is sync (block_on).                           │
└────────────────────────────────────────────────┘
```

The crate's pyo3 bindings expose **sync** functions (the Rust side `block_on`s its own tokio runtime internally). This avoids forcing async into Blender's already-tricky main-thread / timer model. The plugin's Python-side concurrency is the standard `ThreadPoolExecutor` + `queue.Queue` + `bpy.app.timers` pattern (canonical Blender-plugin-with-network-IO shape; documented in `bpy.app.timers` docs and used by other ecosystem plugins).

The CLI binary (`wf-asset`) does *not* go through pyo3 — it calls the Rust crate directly with its native tokio runtime. CI / shell scripts / the future `wf_audit` tool use the CLI; only the Blender plugin uses the pyo3 bindings.

### Rust crate API (the pyo3 surface)

```rust
// In wf_asset_provider/src/pybind.rs (behind `python` feature flag)

#[pyfunction]
fn load_policy(blend_dir: &str) -> PyResult<PyLicencePolicy> { ... }
//   Walks up from blend_dir to find wflevels/licence_policy.toml.
//   On miss, returns the fallback (CC0-only + a warning string).

#[pyfunction]
fn search(query: &str, providers: Vec<&str>, policy: &PyLicencePolicy, limit: usize)
    -> PyResult<Vec<PyAssetCandidate>> { ... }
//   Fans out across the named providers in parallel (tokio JoinSet),
//   returns results filtered by the policy. Rate-limited per provider.

#[pyfunction]
fn download(candidate: &PyAssetCandidate, dest_dir: &str)
    -> PyResult<(String, PyManifest)> { ... }
//   Downloads asset bytes + writes manifest.json.
//   Returns (path-to-asset, manifest-as-dict).

#[pyfunction]
fn validate_licence_match(asset_path: &str, candidate: &PyAssetCandidate) -> PyResult<bool> { ... }
//   Defence-in-depth: re-checks the downloaded asset's actual licence
//   matches the candidate's claimed licence (where the provider supplies
//   metadata in-bundle). Returns false on mismatch, plugin refuses to write
//   manifest in that case.
```

The Python plugin is a thin caller: it calls `load_policy()` once on panel-open, calls `search()` on submit, calls `download()` on import. Nothing licence-related is reimplemented in Python.

### Rust crate — `LicencePolicy` (in `policy.rs`)

```rust
pub struct LicencePolicy {
    pub accept_ids: HashSet<LicenceId>,
    pub reject_ids: HashSet<LicenceId>,
    pub reject_default_ids: HashSet<LicenceId>,
    pub waivers: HashMap<String /*asset_id*/, LicenceId>,
    pub require_attribution_credits: bool,
    pub policy_path: Option<PathBuf>,  // None => fallback, no file found
}

impl LicencePolicy {
    pub fn permits(&self, asset_id: &str, licence: LicenceId) -> bool {
        if let Some(waived_lic) = self.waivers.get(asset_id) {
            return *waived_lic == licence;
        }
        self.accept_ids.contains(&licence)
    }
}

pub fn load_policy(blend_dir: &Path) -> Result<LicencePolicy, PolicyError> { ... }
```

Fallback ("no policy file found, defaulting to CC0-only") is deliberate — lets the plugin work in a fresh checkout without forcing the user to author a policy first, while still being a hard gate (only CC0 assets pass through). The pyo3 wrapper surfaces the fallback flag so the plugin can render a "no policy file found" warning in the panel.

### Provider trait (in `provider.rs`)

```rust
#[async_trait]
pub trait Provider: Send + Sync {
    fn name(&self) -> &'static str;
    fn trust_level(&self) -> TrustLevel;  // High | Medium | Low; OpenGameArt = Low

    async fn search(
        &self,
        query: &str,
        accept: &HashSet<LicenceId>,
        limit: usize,
    ) -> Result<Vec<AssetCandidate>, ProviderError>;

    async fn download(
        &self,
        candidate: &AssetCandidate,
        dest_dir: &Path,
    ) -> Result<(PathBuf, Manifest), ProviderError>;
}
```

Each provider in `providers/*.rs` impls this trait. The crate's top-level `search()` fans out across all impls (or a subset if the plugin specifies via the providers array). Defence-in-depth: the crate's own filter step re-applies the policy to returned candidates regardless of what the provider claims to have filtered.

### UI

A new sidebar panel `WF_PT_asset_browser` in the 3D Viewport's `WF` category (existing convention from `wf_blender`). Layout:

```
┌─ WF Asset Browser ─────────────────────┐
│ Search: [tree                       ]🔍 │
│                                         │
│ Providers:                              │
│  ☑ Poly Haven   ☑ Kenney    ☑ AmbCG    │
│  ☑ Quaternius   ☑ OpenGameArt           │
│                                         │
│ Policy: wflevels/licence_policy.toml    │
│ Accept: CC0-1.0, CC-BY-4.0, royalty-... │
│ [Show waivers (0)]                      │
│                                         │
│ ┌─ Results (12 / 12 after filter) ──┐  │
│ │ [thumb] Oak tree  CC0-1.0  Poly..│  │
│ │ [thumb] Pine tree CC0-1.0  Quat. │  │
│ │ [thumb] Bare tree CC0-1.0  Kenney│  │
│ │ ... (lazy-loaded on scroll)      │  │
│ └──────────────────────────────────┘  │
│ [Import Selected]  [Cancel]            │
└────────────────────────────────────────┘
```

Implementation: a `bpy.types.UIList` for the result rows (Blender's idiomatic scrollable list), a `bpy.types.PropertyGroup` to hold the result data, `bpy.utils.previews` for the thumbnail icon column. Provider toggles are bool properties on a scene-scope PropertyGroup so they persist per-scene. The "Show waivers" button opens a separate popup listing per-asset waivers — read-only in v1 (waiver creation is part of the v2 elevation flow).

### Import flow

1. Designer clicks "Import Selected" with one row selected.
2. `WF_OT_import_asset.execute()` fires.
3. Provider's `download()` is called on a worker thread (operator returns `{'RUNNING_MODAL'}`, polls a queue for completion).
4. Asset bytes land in `wflevels/<level>/assets/<provider>/<asset-id>/`. Subdir layout: `model.glb` or `model.gltf` + textures + `manifest.json`.
5. Manifest is written by `manifest.py.write_manifest()` with all provenance fields.
6. Main thread invokes `bpy.ops.import_scene.gltf(filepath=...)` — Blender ships glTF in core (no addon dependency). Imported objects are placed at the 3D cursor.
7. The imported mesh's primary object gets a default `wf_schema_path` set to `wfsource/source/oas/statplat.oad` (configurable via a default-schema-per-asset-class table in `asset_browser.py`); existing `_seed_defaults` from `export_level.py` runs to populate WF properties.
8. Operator reports back: `INFO: Imported "Oak tree" (CC0-1.0) from Poly Haven; manifest written to <path>`.

### Rate limiting + politeness

Each provider gets its own `time.monotonic()`-based rate limiter (default 2 req/sec). The Poly Haven adapter respects their published 1 req/sec advisory. Failed requests retry once with exponential backoff, then surface as a row-level "Failed: <reason>" entry rather than crashing the search. Total parallelism is capped at 8 concurrent fetches across all providers via the `ThreadPoolExecutor(max_workers=8)`.

### Defence-in-depth

- Plugin re-applies the policy filter after providers return (provider misclassification is real per Seam 5 §7).
- Plugin verifies the downloaded asset's reported licence matches the candidate's claimed licence; mismatch → refuse to write manifest, surface a clear warning.
- Manifest writer requires every field; missing fields fail loudly (asserts at write time).
- Policy reader fails closed: malformed TOML → no assets pass through, user sees "policy file is invalid: <line> <reason>" in the UIstatus bar.

## Verification

Run the plugin against the `wflevels/snowgoons-blender/` reference scene:

1. **Policy discovery.** Open `wflevels/snowgoons-blender/snowgoons.blend`. Open the WF Asset Browser panel. Verify the "Policy" line shows `wflevels/licence_policy.toml`. Delete that file and reload the panel — verify the fallback warning ("policy file not found, defaulting to CC0-only") appears.

2. **Search smoke-test.** Type `tree` in the query field, click search. Verify results from Poly Haven + Quaternius (both have curated tree assets). Verify rows appear within ~3 seconds, thumbnails populate within ~10 seconds, no UI hang.

3. **Filter applied.** Edit `licence_policy.toml` to remove `CC0-1.0` from the accept list. Re-run the same search. Verify the result count drops to 0 (or to only the licence-IDs that *are* still accepted; in v1 the answer should be 0 because all v1 providers are CC0-only).

4. **Import flow.** Search `barrel`, pick a Kenney result, click "Import Selected". Verify:
   - Bytes land at `wflevels/<active-level>/assets/kenney/<asset-id>/model.glb`.
   - `manifest.json` is written next to it with all required fields populated.
   - Mesh appears in Blender at the 3D cursor.
   - Mesh has `wf_schema_path` custom property pointing to `statplat.oad`.

5. **Rate-limit / politeness.** Run 5 searches in 5 seconds. Verify the worker pool throttles correctly (no 429 responses observed in the operator's report log).

6. **Failure surface.** Disconnect network, run a search. Verify each provider row reports a clean "fetch failed: connection error" instead of crashing. Reconnect and retry; verify recovery.

7. **Provider toggles.** Untick all providers except Kenney, run a search. Verify only Kenney rows appear; other providers don't fire HTTP requests.

8. **Build pipeline regression.** After importing one CC0 asset, run `wftools/wf_blender/build_level_binary.sh` on the level. Verify it still builds (we should not have broken the existing pipeline). The new `assets/<provider>/...` subdir must not interfere with the existing build's mesh-discovery or texture-baking passes; this means making sure the build script ignores the `assets/` subdir or the manifest.json files. Check `build_level_binary.sh` line-by-line to see whether it does any wildcard glob that would pick them up; if so, add an exclusion.

9. **No-policy-file behaviour.** Open a `.blend` file outside `wflevels/`. Verify the plugin shows the fallback policy (CC0-only) with the warning, rather than crashing or hiding the panel.

10. **Manifest schema.** After import, run `python -c 'import json, sys; m = json.load(open(sys.argv[1])); assert all(k in m for k in ["licence_id", "attribution_required", "provider", "provider_id", "download_date", "original_url"]); print("ok")' wflevels/.../manifest.json` — should print `ok`.

## Out of scope (explicit punts)

- **Sketchfab + commercial providers.** v2 work; needs API-key config screen + OAuth flow + the per-asset-licence-display logic since Sketchfab's per-asset licence varies. ~3–5 days. Adapter goes in `wf_asset_provider/src/providers/sketchfab.rs` when it lands; the Rust crate's API is unchanged.
- **Per-level policy overrides + cascade.** v2; current scope is project-level only. The crate's `load_policy()` already takes a path argument, so per-level cascade is a single-function extension when needed.
- **Waiver creation UI** (the elevation flow that adds `[[waiver]]` blocks to the policy file). v2; v1 only *displays* existing waivers read-only. CLI side: `wf-asset policy add-waiver <asset-id> <licence> --reason="..."` is the canonical path, also v2.
- **`wf_audit` CI tool.** Investigation Phase B; consumes the same `wf_asset_provider` crate this plan delivers (via the CLI binary or a direct Rust dep). Sequenced after this plan; not part of v1.
- **AI-generated assets.** Investigation §7 hard case; needs jurisdiction-specific decisions.
- **Audio assets.** Investigation §7 explicitly defers to a sibling investigation.
- **Mesh format other than glTF.** v1 only handles `.glb` / `.gltf` because all 5 v1 providers ship glTF. FBX / OBJ support deferred (would mean per-format Blender importer dispatch + per-format texture-path patching).

## Estimated effort

**Rust crate (`wf_asset_provider`):**

- Crate scaffolding + Cargo.toml + clap CLI surface + tokio runtime: 1 day.
- `licence.rs` — canonical `LicenceId` enum + the per-provider mapping table + unit tests for raw → canonical translation: 1 day. (The bug-prone part; tests are the gate.)
- `candidate.rs` + `manifest.rs` + `policy.rs` + `http.rs` (rate-limited reqwest client + retry): 2 days.
- `provider.rs` trait + `providers/mod.rs` registry: 0.5 day.
- 5 provider impls at ~0.5–1 day each (Poly Haven and AmbientCG fastest; Kenney and Quaternius need a static catalog harness; OpenGameArt needs the most plumbing): 3–4 days.
- `pybind.rs` pyo3 bindings + sync wrapper around tokio block_on: 1 day.
- `bin/wf_asset.rs` CLI entry points (search, download, policy show): 0.5 day.
- Integration tests against live provider APIs (recorded with `mockito` for CI): 1 day.

Subtotal: ~10–11 days.

**Blender plugin (Python side):**

- `asset_browser.py` (operator + panel + UIList + thumbnail integration + import flow): 3 days. The UIList async-thumbnail pattern is the load-bearing complexity.
- `asset_threading.py` (ThreadPoolExecutor + queue + timer pump): 0.5 day.
- `__init__.py` registration + menu entry + ensure pyo3 wheel ships in the plugin's bundled deps: 1 day. (The wheel-bundling is the real work; the plugin needs to ship the compiled `wf_asset_provider*.so` for Linux + macOS + Windows.)
- `licence_policy.toml` seed file: 0.5 day.
- Verification pass against the snowgoons scene: 1 day.

Subtotal: ~6 days.

**Total: ~16–17 working days (~3.25 weeks)** assuming uninterrupted focus. Real-world pad to ~4 weeks. Higher than the original ~2 weeks because we're building the Rust crate up-front instead of punting it — but this avoids the duplicate-implementation tax (the Python provider modules would have needed to be rewritten in Rust anyway when `wf_audit` lands), and the licence-mapping table — the bug-prone part — has a single source of truth from day one.

The cross-platform `.so` bundling is the highest-risk item in the plugin-side estimate. Mitigation: use `maturin build --release --features python` for build, and ship the per-platform wheels in `wftools/wf_blender/wheels/` with a small loader stanza in `__init__.py` that picks the right one. Precedent: `wf_core.so` is already shipped this way per the existing plugin's `__init__.py`.
