# Asset Browser — Installation

## Requirements

- Blender 4.0 or later
- Internet connection (all asset searches are live)
- A Sketchfab API key if you want to download Sketchfab assets (free account at sketchfab.com)

---

## Installing the zip

### Blender 4.2 and later (extension system)

1. Open Blender
2. **Edit → Preferences → Get Extensions**
3. Click the **▾** dropdown in the top-right corner of the panel
4. Choose **Install from Disk…**
5. Select `wf_asset_browser-*.zip`
6. The addon appears in the list — enable it with the toggle

### Blender 4.0 – 4.1 (legacy addon)

1. Open Blender
2. **Edit → Preferences → Add-ons**
3. Click the **▾** dropdown → **Install from Disk…**
4. Select `wf_asset_browser-*.zip`
5. Search for "Asset Browser" and enable it with the checkbox

---

## First-time setup

1. Open a 3D Viewport, press **N** to open the sidebar, and click the **Asset Browser** tab
2. Search and import assets from any of these providers — no account needed:
   - **Polyhaven** — HDRIs, textures, and 3D assets (CC0)
   - **Kenney** — game-ready asset packs (CC0)
   - **AmbientCG** — PBR materials and HDRIs (CC0)
   - **Quaternius** — low-poly 3D models (CC0)
   - **OpenGameArt** — community game assets (various open licences)
3. **Sketchfab** is also supported but requires a free API key:
   - Get one at sketchfab.com/settings#api-token
   - Enter it in **Edit → Preferences → Add-ons → Asset Browser**

---

## Documentation

`wf-asset-browser.pdf` (included in this zip) covers:

- Searching and importing assets
- Licence policy configuration (`licence_policy.toml`)
- Provenance tracking and `manifest.json`
- Attribution audit workflow
