# WF Asset Browser — session 2026-04-28 summary

**Status:** Reference doc (session summary) — the asset-browser features it records shipped per the session notes.

**Branch:** `2026-new-level`  
**Files:** `wftools/wf_blender/asset_browser.py`, `wftools/wf_asset_provider/src/providers/opengameart.rs`, `wftools/wf_asset_provider/src/providers/polyhaven.rs`

## What was implemented

### Rust / wf_asset_provider
- **Poly Haven texture fix**: switched from reconstructing CDN paths to using the API's `include` map for companion files (textures, .bin). Removed `fetch_gltf_buffers`.
- **OGA thumbnail scraping**: `extract_content_slugs` now returns `(slug, title, thumb_url)`. Scans forward 2 kB from each title link for `<img src='...'>` (OGA uses single-quoted attrs, thumbnail link comes after title link in HTML). Added `extract_img_url_forward`.
- **OGA fallback slug thumbnail**: when the exact query slug isn't in search results, fetches the content page to get a real thumbnail instead of empty string.
- **Unit tests**: added for OGA slug+thumbnail extraction, Poly Haven include map parsing.

### Blender / asset_browser.py
- **`_icon_ids` dict**: store icon IDs in a plain Python dict after load; `draw_item` reads from it instead of querying the preview collection (fixes thumbnails not rendering).
- **`_pending_thumbs` / `_failed_thumbs`**: prevent duplicate in-flight fetches and infinite retry on failure.
- **Disk cache**: thumbnails cached to `~/.cache/wf_asset_provider/thumbs/` on first fetch; served from disk on subsequent draws.
- **`_redraw_3d()`**: tags all regions in all VIEW_3D areas across all windows.
- **`_try_load_preview`**: fixed `ImagePreview.__bool__` crash — use `image_pixels_float`, avoid bool-testing the preview object.
- **"No preview available"**: `IMAGE_ALPHA` icon + label text for assets with no thumbnail, in both list row and large preview box.
- **Wide popup** (`WF_OT_open_browser_popup`): 880px `invoke_popup` with two-column layout (list left, preview+import right). N-panel keeps its existing UI and adds "Open Wide Browser" button.
- **Popup search stays open**: extracted `_do_search()` from operator; added `search_pending: BoolProperty(update=_on_search_trigger)` to state. Popup uses prop toggle instead of operator button — property updates don't dismiss popups.
- **Quaternius removed** from provider toggles (no usable assets).
- **Progress bar** on search and import.
- **`template_list` rows=12**: taller result list in N-panel.

## Known limitations
- `invoke_popup` cannot be resized or moved — hard Blender constraint.
- OGA asset `table` has no preview image on their site — shows "No preview available" correctly.
- Picnic table and similar OGA assets with only `.blend` files can't be imported.
