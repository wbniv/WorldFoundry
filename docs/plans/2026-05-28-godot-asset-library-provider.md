# Add Godot Asset Library provider + MIT/GPL licence support

## Context

The Godot Asset Store launched (godotengine.org/article/introducing-the-godot-asset-store/).
The new store has no public API yet. Its predecessor, Godot Asset Library
(asset-library.godotengine.org), has a documented REST API and is what the Godot Editor itself
uses. This plan targets that API; a TODO comment in the provider marks where the endpoint
changes once the Asset Store API ships.

Most Godot assets are GDScript addons or `.tscn` scenes — not importable into Blender. Assets
that carry `.glb`/`.gltf`/`.obj`/`.fbx` source files inside their zip are usable. The download
step extracts the first importable 3D file found; if none exists it raises a clear
`RuntimeError`. All results carry `lower_trust=True` so the UI shows the warning flag.

Godot Asset Library uses a free-form `cost` field (`"CC0"`, `"MIT"`, `"GPLv3"`, `"Custom"`,
etc.). The existing licence system only covered CC licences, mapping everything else to
`UNKNOWN` — which silently filtered out MIT, Apache, and GPL assets. This plan adds proper
named constants for those licences so they can be opted into via `licence_policy.toml` and
filtered in the Blender UI.

The `licence_filter` enum existed in the UI but was never wired up — results were never
actually filtered. `filter_items()` is now implemented on the UIList.

## Files changed

| File | Change |
|------|--------|
| `wftools/blender_asset_finder/providers.py` | New licence constants (MIT, Apache-2.0, BSD-2/3, GPL-2/3); updated `_LICENCE_URLS`, `_ATTRIBUTION_REQUIRED`, `_RAW_TO_LICENCE`; `GodotAssetLibrary` provider class; add to `_ALL_PROVIDERS` |
| `wftools/blender_asset_finder/asset_browser.py` | `godot` toggle in `WF_AssetProviderToggles`; wire `sketchfab` + `godot` into `_do_search` enabled list (sketchfab was missing — bug fix); MIT_OSS + GPL options in `licence_filter` enum; implement `WF_UL_AssetResults.filter_items()` |

## Licence system additions (providers.py)

Six new SPDX-ID constants added alongside the existing CC constants:

| Constant | Value | Attribution required? |
|----------|-------|-----------------------|
| `MIT` | `"MIT"` | yes (keep copyright notice) |
| `APACHE2` | `"Apache-2.0"` | yes |
| `BSD2` | `"BSD-2-Clause"` | yes |
| `BSD3` | `"BSD-3-Clause"` | yes |
| `GPL2` | `"GPL-2.0"` | no (copyleft — different obligation) |
| `GPL3` | `"GPL-3.0"` | no (copyleft) |

`_ATTRIBUTION_REQUIRED` extended to include MIT, Apache-2.0, BSD-2, BSD-3 (these require
preserving copyright notices in distributions, analogous to CC-BY in spirit).

`_RAW_TO_LICENCE` maps common raw strings to the new constants:
`"mit"` → MIT, `"gplv3"` → GPL3, `"apache-2.0"` → APACHE2, etc.

## GodotAssetLibrary provider

- **Search**: `GET https://asset-library.godotengine.org/asset?filter=…&max_results=…&type=any&support=official,community`
  - Over-fetches by 3× to allow for CC policy filtering
  - Maps `cost` field via `licence_from_raw()`
  - `lower_trust=True` on all results
- **Download**: `GET /asset/{id}` → get `download_url` (GitHub archive zip) → extract first
  `.glb`/`.gltf`/`.obj`/`.fbx` found → write manifest
- **UI toggle**: `godot: BoolProperty(name="Godot Asset Lib", default=False)`

## licence_filter — now functional

`WF_UL_AssetResults.filter_items()` implemented. Filter options:

| Option | Shows |
|--------|-------|
| All | everything policy allows |
| CC0 only | `CC0-1.0` |
| CC (free) | anything starting with `CC-` |
| MIT/OSS | MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause |
| GPL | GPL-2.0, GPL-3.0 |
| Paid RF | `royalty-free` (Sketchfab Standard) |

## Opting into MIT or GPL assets

The default `licence_policy.toml` (and the CC0 fallback) does not accept MIT or GPL. To
enable them project-wide, add to `licence_policy.toml`:

```toml
accept = ["CC0-1.0", "CC-BY-4.0", "MIT", "Apache-2.0"]   # permissive
# or for GPL (note: affects distribution obligations for the whole project)
accept = [..., "GPL-3.0"]
```

## Verification

1. **Syntax check** (no bpy needed):
   ```
   python3 -m py_compile wftools/blender_asset_finder/providers.py
   python3 -m py_compile wftools/blender_asset_finder/asset_browser.py
   ```

2. **Licence mapping round-trip**:
   ```
   python3 -c "
   import sys; sys.path.insert(0, 'wftools/blender_asset_finder')
   import providers as p
   assert p.licence_from_raw('MIT') == 'MIT'
   assert p.licence_from_raw('GPLv3') == 'GPL-3.0'
   assert p.licence_from_raw('Apache-2.0') == 'Apache-2.0'
   assert p.licence_from_raw('Custom') == 'unknown'
   assert p.MIT in p._ATTRIBUTION_REQUIRED
   assert p.GPL3 not in p._ATTRIBUTION_REQUIRED
   assert 'godot' in p._ALL_PROVIDERS
   print('all assertions passed')
   "
   ```

3. **CLI search** (requires network):
   ```
   python3 wftools/wf_asset.py search "tree" --providers godot
   ```
   With default (CC0-only) policy: likely 0 results.
   With `accept = ["MIT"]` in policy: MIT-licensed Godot assets appear.

4. **Blender UI** — install addon, enable "Godot Asset Lib" toggle, search "3d model",
   confirm results show ⚠ lower-trust flag. Switch `licence_filter` to "MIT/OSS" — verify
   list narrows to MIT/Apache results only.

5. **No-3D graceful failure** — pick a known addon-only Godot asset; confirm download
   raises a readable `RuntimeError` rather than crashing Blender.
