# Plan: Split wf_blender into two separate Blender addons

## Context

The current `wftools/wf_blender/` directory is a single Blender addon that bundles two unrelated things:
- **Level editor** (`operators.py`, `panels.py`, `export_level.py`) — WF-specific, requires `wf_core.so` (Rust native lib)
- **Asset browser** (`asset_browser.py`, `asset_threading.py`, `providers.py`) — generic, pure Python, no WF dependency

The asset browser has no fundamental connection to World Foundry. It's a licence-aware provenance-tracking Blender asset browser that happens to live in the WF repo. Keeping them together makes distribution harder: anyone who wants just the asset browser has to deal with `wf_core.so` and a maturin build step.

Splitting them gives the asset browser a clean pure-Python identity that can be published to extensions.blender.org without platform-specific native libs.

**Related:** `docs/plans/2026-04-28-blender-addon-packaging.md` — the packaging plan that preceded this. It assumed a single combined addon; this plan supersedes the packaging section of that doc. The manifest/task structure below replaces what was planned there.

---

## What moves where

### New addon: `wftools/wf_asset_browser/`
Pure Python. No `wf_core` dependency. Distributable as-is.

| Action | File |
|---|---|
| NEW | `wftools/wf_asset_browser/__init__.py` |
| MOVE | `wftools/wf_blender/asset_browser.py` → `wftools/wf_asset_browser/asset_browser.py` |
| MOVE | `wftools/wf_blender/asset_threading.py` → `wftools/wf_asset_browser/asset_threading.py` |
| MOVE | `wftools/wf_blender/providers.py` → `wftools/wf_asset_browser/providers.py` |
| MOVE | `wftools/wf_blender/kenney_catalog.json` → `wftools/wf_asset_browser/kenney_catalog.json` |
| MOVE | `wftools/wf_blender/quaternius_catalog.json` → `wftools/wf_asset_browser/quaternius_catalog.json` |
| NEW | `wftools/wf_asset_browser/blender_manifest.toml` |
| NEW | `wftools/wf_asset_browser/install.sh` |

### Modified: `wftools/wf_blender/` (level editor only)

| Action | File |
|---|---|
| Modify | `wftools/wf_blender/__init__.py` — remove asset_browser import + sketchfab_api_key pref |
| Modify | `wftools/wf_blender/install.sh` — remove asset browser files from symlink + data copy list |
| Modify | `wftools/wf_blender/blender_manifest.toml` — rename to reflect level editor purpose |
| Delete | `wftools/wf_blender/asset_browser.py` |
| Delete | `wftools/wf_blender/asset_threading.py` |
| Delete | `wftools/wf_blender/providers.py` |
| Delete | `wftools/wf_blender/kenney_catalog.json` |
| Delete | `wftools/wf_blender/quaternius_catalog.json` |

### Modified: `Taskfile.yml`
Add 3 new tasks for the asset browser addon. Update `blender-install` description.

---

## Implementation

### 1. New `wftools/wf_asset_browser/__init__.py`

```python
"""
Asset Browser — licence-aware 3D asset browser with provenance tracking.

Searches Sketchfab, Polyhaven, Kenney, Quaternius; records provenance
manifest.json for every imported asset; filters by licence_policy.toml.

Installation: Edit > Preferences > Add-ons > Install from Disk
No build step required — pure Python.
"""

import bpy
from bpy.props import StringProperty

bl_info = {
    "name":        "Asset Browser",
    "author":      "World Foundry",
    "version":     (0, 2, 0),
    "blender":     (4, 0, 0),
    "location":    "3D Viewport > Sidebar > Asset Browser",
    "description": "Licence-aware asset browser with provenance tracking",
    "category":    "Import-Export",
}

from . import asset_browser  # noqa: E402


class WFAssetBrowserPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    sketchfab_api_key: StringProperty(
        name="Sketchfab API Key",
        description="Bearer token from sketchfab.com/settings#api-token. Required for downloading Sketchfab assets.",
        subtype='PASSWORD',
        default="",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "sketchfab_api_key")
        layout.label(text="Get your token at: sketchfab.com/settings#api-token", icon='URL')


def register():
    bpy.utils.register_class(WFAssetBrowserPreferences)
    asset_browser.register()


def unregister():
    asset_browser.unregister()
    bpy.utils.unregister_class(WFAssetBrowserPreferences)
```

No code change needed in `asset_browser.py`: it already uses `__name__.split('.')[0]` to look up addon prefs, which resolves to `wf_asset_browser` after the move.

### 2. New `wftools/wf_asset_browser/blender_manifest.toml`

```toml
schema_version = "1.0.0"
id = "wf_asset_browser"
name = "Asset Browser"
tagline = "Licence-aware 3D asset browser with provenance tracking"
version = "0.2.0"
type = "add-on"
blender_version_min = "4.2.0"
maintainer = "World Foundry <wbnorris@gmail.com>"
license = ["SPDX:GPL-2.0-or-later"]

[build]
paths_exclude_pattern = ["__pycache__/", ".git", "*.zip", "*.log"]
```

### 3. New `wftools/wf_asset_browser/install.sh`

Simplified — no maturin, no wf_core:

```bash
#!/usr/bin/env bash
# Install the wf_asset_browser addon (pure Python — no build step needed).
# Python files are symlinked; catalog JSONs are copied.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -ge 1 ]]; then
    ADDONS_DIR="$1"
else
    CONFIG_BASE="${XDG_CONFIG_HOME:-$HOME/.config}/blender"
    BLENDER_VER=$(ls "$CONFIG_BASE" | sort -V | tail -1)
    ADDONS_DIR="$CONFIG_BASE/$BLENDER_VER/scripts/addons"
fi

DEST="$ADDONS_DIR/wf_asset_browser"
mkdir -p "$DEST"

for pyfile in __init__.py asset_browser.py asset_threading.py providers.py; do
    ln -sf "$SCRIPT_DIR/$pyfile" "$DEST/$pyfile"
done

cp "$SCRIPT_DIR/kenney_catalog.json"     "$DEST/kenney_catalog.json"
cp "$SCRIPT_DIR/quaternius_catalog.json" "$DEST/quaternius_catalog.json"

echo "Installed to: $DEST"
echo "Enable 'Asset Browser' in Blender > Edit > Preferences > Add-ons"
```

### 4. Update `wftools/wf_blender/__init__.py`

Remove:
- `from . import asset_browser` (line ~59)
- `sketchfab_api_key` property from `WF_AddonPreferences`
- The `layout.prop(self, "sketchfab_api_key")` line and its label in `draw()`
- `asset_browser.register()` call in `register()`
- `asset_browser.unregister()` call in `unregister()`

### 5. Update `wftools/wf_blender/blender_manifest.toml`

```toml
schema_version = "1.0.0"
id = "wf_blender"
name = "World Foundry Level Editor"
tagline = "OAD schema-driven game object attributes for World Foundry engine"
version = "0.2.0"
type = "add-on"
blender_version_min = "4.2.0"
maintainer = "World Foundry <wbnorris@gmail.com>"
license = ["SPDX:GPL-2.0-or-later"]

[build]
paths_exclude_pattern = ["__pycache__/", ".git", "*.zip", "*.log", "docs/"]
```

### 6. Update `wftools/wf_blender/install.sh`

Line 72: remove `asset_browser.py asset_threading.py providers.py` from the symlink loop.
Lines 79–80: remove the two `kenney_catalog.json` / `quaternius_catalog.json` cp lines.

### 7. New Taskfile.yml tasks

```yaml
  asset-browser-install:
    desc: "Install wf_asset_browser addon (pure Python, no build step)"
    cmds:
      - bash wftools/wf_asset_browser/install.sh

  asset-browser-validate:
    desc: "Validate wf_asset_browser extension manifest (requires Blender 4.2+)"
    cmds:
      - blender --command extension validate --source-dir wftools/wf_asset_browser

  asset-browser-package:
    desc: "Build distributable wf_asset_browser zip; output in dist/"
    deps: [asset-browser-validate]
    cmds:
      - mkdir -p dist
      - blender --command extension build --source-dir wftools/wf_asset_browser --output-dir dist
      - echo "Package written to dist/"
```

Update `blender-install` desc: `"Install World Foundry level editor addon (symlinks .py, copies wf_core.so; builds if needed)"`.

---

## Files summary

| Action | Path |
|---|---|
| **New dir + 3 files** | `wftools/wf_asset_browser/__init__.py`, `blender_manifest.toml`, `install.sh` |
| **Move 5 files** | `asset_browser.py`, `asset_threading.py`, `providers.py`, `kenney_catalog.json`, `quaternius_catalog.json` |
| **Delete 5 from wf_blender** | same files after move |
| Modify | `wftools/wf_blender/__init__.py` |
| Modify | `wftools/wf_blender/install.sh` |
| Modify | `wftools/wf_blender/blender_manifest.toml` |
| Modify | `Taskfile.yml` — 3 new tasks, 1 desc update |

No changes to `asset_browser.py`, `asset_threading.py`, or `providers.py` — they move as-is.

---

## Verification

1. `task asset-browser-install` — installs to `~/.config/blender/<ver>/scripts/addons/wf_asset_browser/`; all `.py` files symlinked, catalog JSONs copied, no `.so` present
2. Open Blender → Edit → Preferences → Add-ons → search "Asset Browser" → appears, enables cleanly
3. Sidebar > Asset Browser panel shows; Sketchfab search works with API key from preferences
4. `task asset-browser-validate` — passes with no errors
5. `task asset-browser-package` — `dist/wf_asset_browser-0.2.0.zip` produced; no `.so` inside
6. `task blender-install` — installs to `wf_blender/`; no `asset_browser.py` symlink, no catalog JSONs; `wf_core.so` present
7. Open Blender → "World Foundry Level Editor" addon enables; OAD schema panel works on objects; no Asset Browser panel
