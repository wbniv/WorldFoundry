# Plan: Pure-Python Asset Provider for Blender Plugin

## Context

The Blender asset browser currently binds to `wf_asset_provider` via PyO3 (a compiled Rust extension), and the CLI (`wf-asset`) is a Rust binary from the same crate. All the operations both tools perform — HTTP search, JSON parsing, TOML policy loading, file download, manifest writing — are straightforward stdlib Python. There is no performance or capability justification for Rust in either case.

**Decision:** Rewrite everything as pure Python.

- `wftools/wf_blender/providers.py` — shared provider logic (search, download, policy, credentials, manifest writing)
- `wftools/wf_asset.py` — Python CLI that imports `providers.py`; replaces the Rust `wf-asset` binary
- The Rust crate (`wftools/wf_asset_provider/`) — remove the PyO3 `--features python` bindings; the Rust binary can remain as a parallel implementation but is no longer the canonical tool

This eliminates all native build dependencies for both the addon and the CLI. Both work anywhere Python runs with no compilation step.

---

## Architecture

### What moves to Python

`wftools/wf_blender/providers.py` — a single new file containing:

1. **`LicenceId` constants** — string constants matching the Rust enum's `as_str()` values:
   ```python
   CC0       = "CC0-1.0"
   CC_BY     = "CC-BY-4.0"
   CC_BY_SA  = "CC-BY-SA-4.0"
   CC_BY_NC  = "CC-BY-NC-4.0"
   CC_BY_NC_SA = "CC-BY-NC-SA-4.0"
   CC_BY_ND  = "CC-BY-ND-4.0"
   CC_BY_NC_ND = "CC-BY-NC-ND-4.0"
   ROYALTY_FREE = "royalty-free"
   EDITORIAL = "editorial-only"
   ```

2. **`AssetCandidate` dataclass:**
   ```python
   @dataclass
   class AssetCandidate:
       provider: str
       provider_id: str
       title: str
       thumbnail_url: str
       licence_id: str
       download_url: str
       original_url: str
       attribution_string: str
       attribution_required: bool
       lower_trust: bool = False
   ```

3. **`LicencePolicy` dataclass + `load_policy(path)`:**
   - Walks up from `path` looking for `licence_policy.toml`
   - Uses `tomllib` (Python 3.11+) or `tomli` fallback
   - Returns a policy with `accept_ids`, `reject_ids`, `reject_default_ids`, `require_attribution_credits`
   - Fallback if no file found: accept CC0-1.0 only

4. **`Credentials` dataclass:**
   ```python
   @dataclass
   class Credentials:
       sketchfab_api_key: str | None = None
   ```

5. **`Provider` abstract base class:**
   ```python
   class Provider(ABC):
       @abstractmethod
       def search(self, query: str, policy: LicencePolicy, limit: int) -> list[AssetCandidate]: ...
       @abstractmethod
       def download(self, candidate: AssetCandidate, dest_dir: Path, creds: Credentials) -> Path: ...
   ```

6. **Six provider implementations** (inline in the same file, ~50–80 lines each):
   - `PolyHaven` — `GET https://api.polyhaven.com/assets?type=models` + search filter
   - `Kenney` — static JSON catalog
   - `AmbientCG` — `GET https://ambientcg.com/api/v2/full_json`
   - `Quaternius` — static JSON catalog
   - `OpenGameArt` — XML feed / API, `lower_trust=True`
   - `Sketchfab` — `GET https://api.sketchfab.com/v3/models`, download requires Bearer token

7. **`search(query, policy, credentials, providers, limit)` top-level function** — mirrors the Rust pybind signature exactly so `asset_browser.py` needs minimal changes.

8. **`download(candidate, dest_dir, credentials)` top-level function** — routes to the correct provider, writes `manifest.json`.

9. **`_write_manifest(candidate, dest_dir, download_date)` helper** — writes the same JSON schema as the Rust implementation.

### HTTP

Use `urllib.request` (stdlib). No third-party dependencies. Simple `urllib.request.urlopen()` with a timeout. Rate limiting: per-provider `time.sleep()` with conservative delays (Sketchfab: 1 req/s).

For Sketchfab authenticated requests, set `Authorization: Bearer {key}` header via `urllib.request.Request(url, headers={...})`.

---

## Changes

### New file: `wftools/wf_blender/providers.py`
~400–500 lines. All provider logic, policy loading, download, manifest writing.

### Modify: `wftools/wf_blender/asset_browser.py`

Replace:
```python
import wf_asset_provider as _wap
# ...
credentials = _wap.make_credentials(sketchfab_api_key=key or None)
results = _wap.search(query, policy, credentials=credentials, providers=enabled, limit=50)
```

With:
```python
from . import providers as _prov
# ...
credentials = _prov.Credentials(sketchfab_api_key=key or None)
results = _prov.search(query, policy, credentials=credentials, providers=enabled, limit=50)
```

The function signatures are designed to match, so the rest of `asset_browser.py` is unchanged.

Policy loading changes from `_wap.load_policy(path)` to `_prov.load_policy(path)` — same return shape.

### Modify: `wftools/wf_blender/__init__.py`

Remove the `wf_asset_provider` import check (it's no longer a native extension). The `wf_core` check for the OAD system stays.

### New file: `wftools/wf_asset.py` — Python CLI

Replaces `wftools/wf_asset_provider/src/bin/wf_asset.rs`. Uses `argparse`. Imports `providers` by adding `wftools/wf_blender` to `sys.path`.

```
usage: wf_asset.py [-h] {search,download,policy,providers} ...

  search   QUERY [--provider p1,p2] [--limit N] [--policy-dir DIR]
  download PROVIDER/ID --dest DIR [--policy-dir DIR]
  policy   show [--blend-dir DIR]
  providers list
```

Credentials: reads `WF_SKETCHFAB_API_KEY` env var (same as the Rust CLI). Output format identical to the Rust CLI so existing scripts/docs don't change.

```python
#!/usr/bin/env python3
import argparse, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'wf_blender'))
import providers as _p

# ... argparse setup ...
```

### Taskfile.yml — add `wf-asset` task

```yaml
wf-asset:
  desc: "Run the wf-asset CLI (usage: task wf-asset -- search 'tree')"
  cmds:
    - python3 wftools/wf_asset.py {{.CLI_ARGS}}
```

### Rust crate changes (`wftools/wf_asset_provider/`)

Remove the PyO3 bindings: delete `src/pybind.rs`, remove `pyo3` from `Cargo.toml` dependencies, remove `--features python` from any build instructions. The Rust binary (`src/bin/wf_asset.rs`) can remain as-is — it still compiles and works — but is no longer the primary interface.

### No changes to:
- `wftools/wf_blender/install.sh` (no longer needs to build/copy `wf_asset_provider.so`)
- Taskfile.yml `blender-build` task (no longer needs `wf_asset_provider` maturin build)

---

## Files Modified / Created

| Action | Path |
|--------|------|
| **New** | `wftools/wf_blender/providers.py` |
| **New** | `wftools/wf_asset.py` — Python CLI |
| Modify | `wftools/wf_blender/asset_browser.py` — swap `_wap` import |
| Modify | `wftools/wf_blender/__init__.py` — remove wf_asset_provider import check |
| Modify | `wftools/wf_asset_provider/src/pybind.rs` — delete (PyO3 bindings no longer needed) |
| Modify | `wftools/wf_asset_provider/Cargo.toml` — remove pyo3 dependency |
| Modify | `Taskfile.yml` — add `wf-asset` task |

---

## Packaging impact

After this plan: the Blender addon has **one** native dependency (`wf_core.so`) instead of two. The `blender-package` task simplifies to: extract `wf_core.so` from its wheel, copy into addon dir, run `blender --command extension build`. The `wf_asset_provider` wheel is never needed by the addon.

---

## Verification

1. `python3 -c "import sys; sys.path.insert(0,'wftools/wf_blender'); import providers; print('ok')"` — module imports cleanly
2. `python3 wftools/wf_asset.py providers list` — prints all six provider names
3. `python3 wftools/wf_asset.py search "tree" --provider polyhaven --limit 5` — returns results
4. `task wf-asset -- search "barrel"` — same via task runner
5. Install addon via `task blender-install` and run a search in Blender — results appear, download works, `manifest.json` written
6. Test Sketchfab search (no key) — results appear; download without key shows clear error
7. Test Sketchfab download with `WF_SKETCHFAB_API_KEY` set — asset downloads, manifest has correct `licence_id` and `attribution_string`
8. `task blender-package` — resulting zip contains `providers.py` and `wf_core.so` but NOT `wf_asset_provider.so`
9. `cargo build --manifest-path wftools/wf_asset_provider/Cargo.toml` — still compiles (pyo3 removed but binary target intact)
