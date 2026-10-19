# Plan: Split wf_blender into two separate Blender addons

**Date:** 2026-04-29
**Status:** DONE.
**Related:**
- [docs/plans/2026-04-28-blender-addon-packaging.md](2026-04-28-blender-addon-packaging.md) — packaging plan that preceded this; its packaging section is superseded here
- [docs/plans/2026-04-28-wf-asset-provider-pure-python.md](2026-04-28-wf-asset-provider-pure-python.md) — eliminated `wf_asset_provider.so`; this plan eliminates the remaining asset-browser/level-editor coupling

---

## Problem

`wftools/wf_blender/` bundled two unrelated things:

- **Level editor** — OAD schema panels, validation, `.iff` import/export. WF-specific, requires `wf_core.so` (Rust native lib built with maturin).
- **Asset browser** — Sketchfab/Polyhaven/Kenney/Quaternius search, licence checking, provenance manifests. No WF dependency, pure Python.

Anyone wanting just the asset browser had to deal with `wf_core.so` and a maturin build step. The asset browser has nothing to do with World Foundry specifically — it's a general-purpose licence-aware asset tool that happens to live in the WF repo.

---

## Solution: two addons

### `wftools/wf_asset_browser/` (NEW)

Pure Python. No native deps. Publishable to extensions.blender.org as-is.

| File | Notes |
|---|---|
| `__init__.py` | New. Registers `WFAssetBrowserPreferences` (sketchfab_api_key) + asset_browser |
| `asset_browser.py` | Moved from `wf_blender/`. No code changes. |
| `asset_threading.py` | Moved. No code changes. |
| `providers.py` | Moved. No code changes. |
| `kenney_catalog.json` | Moved. |
| `quaternius_catalog.json` | Moved. |
| `blender_manifest.toml` | New. `id = "wf_asset_browser"`, no wheels/native libs. |
| `install.sh` | New. Symlinks .py, copies catalog JSONs. No maturin. |

`asset_browser.py` uses `__name__.split('.')[0]` to resolve addon preferences — resolves automatically to `wf_asset_browser` after the move, no code change needed.

### `wftools/wf_blender/` (MODIFIED — level editor only)

| Change | Detail |
|---|---|
| `__init__.py` | Removed: `asset_browser` import, `sketchfab_api_key` pref, `StringProperty` import |
| `blender_manifest.toml` | Renamed to "World Foundry Level Editor" |
| `install.sh` | Removed asset browser files from symlink list; removed catalog JSON copies |
| Deleted | `asset_browser.py`, `asset_threading.py`, `providers.py`, `kenney_catalog.json`, `quaternius_catalog.json` |

---

## Taskfile tasks

| Task | What it does |
|---|---|
| `asset-browser-install` | `bash wftools/wf_asset_browser/install.sh` — symlinks .py, copies JSONs |
| `asset-browser-validate` | `blender --command extension validate --source-dir wftools/wf_asset_browser` |
| `asset-browser-package` | `blender --command extension build` → `dist/wf_asset_browser-<ver>.zip` |
| `bump-asset-browser` | Bump version in `blender_manifest.toml` (see below) |
| `publish-asset-browser` | `gh release create` with the built zip attached |
| `package-all` | Packages both addons into `dist/` in one shot |
| `blender-install` (updated desc) | Level editor only — symlinks .py, copies `wf_core.so` |

### `bump-asset-browser` usage

```
task bump-asset-browser              # patch:  0.2.0 → 0.2.1
task bump-asset-browser BUMP=minor   # minor:  0.2.0 → 0.3.0  (resets patch)
task bump-asset-browser BUMP=major   # major:  0.2.0 → 1.0.0  (resets minor + patch)
task bump-asset-browser -- 1.5.0    # explicit version override
```

`task --summary bump-asset-browser` also prints this help inline.

---

## Verification

1. `task asset-browser-install` → installs to `~/.config/blender/<ver>/scripts/addons/wf_asset_browser/`; no `.so` present
2. Blender → Preferences → Add-ons → "Asset Browser" enables cleanly; sidebar panel appears
3. Sketchfab search works with API key in preferences
4. `task asset-browser-package` → `dist/wf_asset_browser-0.2.0.zip`; open zip, confirm no `.so`
5. `task blender-install` → installs `wf_blender/`; no catalog JSONs, no asset browser panel; OAD schema panel works
