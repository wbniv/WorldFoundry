---
name: Blender asset browser storefront deficiencies
description: Things the Blender sidebar asset browser can't do — captured as requirements for a future dedicated WF asset storefront UI
type: project
originSessionId: a53ff3a9-5044-46e2-a1ba-f4ed10c7b4dc
---
These were identified while adding Sketchfab/commercial-provider support to `wftools/wf_blender/asset_browser.py` (2026-04-29). The user wants to build an improved storefront later; these are the gaps to solve.

1. **Linear-only layout** — Blender UIList is a fixed scrollable list; no masonry/grid, no resizable thumbnails. A web storefront could show 4–6 assets per row.
2. **No in-viewport 3D preview** — can't orbit/inspect a model before importing. A storefront could embed a Sketchfab viewer iframe.
3. **No purchase / OAuth flow** — paid assets require leaving Blender. A storefront could embed payment or a purchase-confirmation webhook.
4. **No wishlist or cart** — sessions are stateless; panel forgets results when closed. A storefront would persist a wishlist.
5. **Single-select only** — can't compare two candidates side-by-side or batch-import.
6. **No cross-provider price comparison** — TurboSquid vs. Sketchfab prices not visible in same view.
7. **API key in Blender prefs** — stored plaintext in Blender prefs JSON; not OS keychain.
8. **Attribution workflow is manual** — `attribution_string` in manifest.json but no "Export credits.txt" button.
9. **No semantic / similarity search** — keyword only; a storefront could embed vector search.
10. **No browse history or favorites** — panel forgets state between sessions.
11. **Licence provenance chain invisible** — `derived_from` in manifest.json has no UI; a storefront could render the remix DAG.
12. **Thumbnail fidelity** — Blender icon preview is effectively 128×128; a storefront can show 512px+.
13. **Audio out of scope entirely** — master/sync/mechanical rights can't be modelled in the policy TOML; a storefront could handle per-asset-type licensing.

**Why:** User explicitly noted these while building v2 of the asset browser, intending to use them as requirements for a future purpose-built storefront.
**How to apply:** When user asks about "storefront" or "improved asset browser" in this project, refer to this list as the starting requirements.
