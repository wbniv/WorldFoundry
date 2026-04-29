# WF Asset Browser — User Manual

The WF Asset Browser is a Blender sidebar panel that searches licensed 3D assets
across multiple online providers, filters them against the project's licence policy,
and imports the chosen asset directly into your scene with a provenance manifest.
The manual is organised around **licence tiers**, because every decision in the
browser — what you can see, what you can import, what you owe the author — is
driven by the asset's licence.

## Quick start

<img src="plans/blender object gallery by license.png" alt="WF Asset Browser — searching 'chair' across four providers. Poly Haven result selected; CC0-1.0 badge and thumbnail visible in the detail pane. OpenGameArt results carry a ⚠ lower-trust marker." style="float: right; width: 50%; margin: 0 0 1.2em 1.8em;">

1. Open a `.blend` file inside the `wflevels/` tree.
2. Press **N** in the 3D Viewport to open the sidebar and click the **WF** tab. (Also available via **File → Import → WF Asset Browser**.)
3. Type a query (`barrel`, `tree`, `crate`) and press the search icon or **Enter**.
4. Pick a result and click **Import Selected**.

That's it for CC0 assets (the default). Anything more — enabling Sketchfab,
accepting CC-BY, managing waivers — is covered in the sections below.

<div style="clear: both;"></div>


## The policy file

All filtering is driven by `wflevels/licence_policy.toml`. The plugin walks up
from the active `.blend` file's directory until it finds this file; the first one
found wins. The path shown in the panel under **Policy:** tells you which file is
in effect.

If no file is found the panel shows:

```
Policy: (fallback — no licence_policy.toml found)
Accept: CC0-1.0
```

The fallback is intentional: new checkouts work immediately, but only the safest
possible licence class passes. **Before you import anything other than CC0 assets,
make sure the panel shows the project policy file, not the fallback.**

### Policy file anatomy

```toml
require_attribution_credits = true   # attribution strings must appear somewhere

[[licence]]
id     = "CC0-1.0"
status = "accept"           # this licence passes the filter
reason = "public domain"

[[licence]]
id     = "CC-BY-4.0"
status = "reject-default"   # blocked unless a per-asset [[waiver]] exists
reason = "attribution required — waiver available"

[[licence]]
id     = "CC-BY-SA-4.0"
status = "reject"           # hard block, no waiver possible
reason = "share-alike incompatible with commercial distribution"
```

`status` values:

| Value | Meaning |
|---|---|
| `accept` | Assets with this licence appear in results and can be imported |
| `reject-default` | Blocked unless a `[[waiver]]` record exists for the specific asset |
| `reject` | Never passes — no waiver possible |


## Providers and their licence tiers

Each provider is a toggle in the **Providers:** box. The default-on set (grey
background) are all CC0-only sources; Sketchfab (off by default) introduces
mixed licences.

<table style="width:100%">
<colgroup><col style="width:16%"><col style="width:34%"><col style="width:50%"></colgroup>
<thead><tr><th>Provider</th><th>Licences available</th><th>Notes</th></tr></thead>
<tbody>
<tr><td><strong>Poly Haven</strong></td><td>CC0-1.0</td><td>All assets; no API key</td></tr>
<tr><td><strong>Kenney</strong></td><td>CC0-1.0</td><td>Curated static catalog; no API key</td></tr>
<tr><td><strong>AmbientCG</strong></td><td>CC0-1.0</td><td>Textures and materials; no API key</td></tr>
<tr><td><strong>Quaternius</strong></td><td>CC0-1.0</td><td>Curated static catalog; no API key</td></tr>
<tr><td><strong>OpenGameArt</strong></td><td>CC0-1.0 subset</td><td>Open-upload bazaar — see ⚠ note below</td></tr>
<tr><td><strong>Sketchfab</strong></td><td>CC0 · CC-BY · CC-BY-SA · CC-BY-NC · CC-BY-ND · Editorial · Paid RF</td><td>Requires API key; see §Sketchfab</td></tr>
</tbody>
</table>

### ⚠ OpenGameArt trust level

OpenGameArt is an open-upload site. Assets are pre-filtered to CC0 by the
provider API and re-filtered by the policy engine, but the accuracy of
user-submitted licence claims is weaker than on curated sources. Results from
OpenGameArt show a **⚠** warning glyph next to the licence label. Review
them with extra care before shipping.


## Licence tiers — what they mean and what they cost you

<table style="width:100%">
<colgroup><col style="width:22%"><col style="width:13%"><col style="width:13%"><col style="width:13%"><col style="width:39%"></colgroup>
<thead><tr><th>Licence</th><th>Commercial</th><th>Attribution</th><th>Derivatives</th><th>WF project default</th></tr></thead>
<tbody>
<tr><td><strong>CC0-1.0</strong></td><td>✓</td><td>not required</td><td>✓</td><td>✓ accept</td></tr>
<tr><td><strong>CC-BY-4.0</strong></td><td>✓</td><td>required</td><td>✓</td><td>~ waiver only (credits screen required)</td></tr>
<tr><td><strong>CC-BY-SA-4.0</strong></td><td>✓</td><td>required</td><td>share-alike</td><td>✗ blocked — share-alike incompatible</td></tr>
<tr><td><strong>CC-BY-NC-4.0</strong></td><td>✗</td><td>required</td><td>✓</td><td>✗ blocked — no commercial use</td></tr>
<tr><td><strong>CC-BY-NC-SA-4.0</strong></td><td>✗</td><td>required</td><td>share-alike</td><td>✗ blocked — no commercial use</td></tr>
<tr><td><strong>CC-BY-ND-4.0</strong></td><td>✓</td><td>required</td><td>✗</td><td>✗ blocked — no derivatives</td></tr>
<tr><td><strong>CC-BY-NC-ND-4.0</strong></td><td>✗</td><td>required</td><td>✗</td><td>✗ blocked — no commercial use, no derivatives</td></tr>
<tr><td><strong>royalty-free</strong></td><td>✓</td><td>not required</td><td>✓</td><td>opt-in (add to policy; Sketchfab paid only)</td></tr>
<tr><td><strong>editorial-only</strong></td><td>✗</td><td>—</td><td>—</td><td>✗ blocked — press use only</td></tr>
<tr><td><strong>unknown</strong></td><td>?</td><td>?</td><td>?</td><td>✗ blocked — always fail-closed</td></tr>
</tbody>
</table>

### CC0-1.0 — Public domain · no restrictions · no attribution

The green **◈** icon in the results list. These assets are contributed by their
authors to the public domain. You can use, modify, and ship them with zero
obligations. No credits line required (though `require_attribution_credits = true`
in the policy file means the plugin will still write the author's name to
`manifest.json` for traceability, even if you don't technically need to display it).

**All five default providers serve CC0-only assets. If you leave the default
provider set and the default policy, every result you see is CC0.**


### CC-BY-4.0 — Attribution required

The yellow **🛡** icon. The author allows any use — commercial, derivative works,
redistribution — as long as you credit them. The credit line is provided by the
plugin in `manifest.json` under `attribution_string`.

**Default policy status: `reject-default`.** CC-BY assets do *not* appear in
results unless you either:

- Set the licence to `accept` in `licence_policy.toml` (accepts CC-BY globally); or
- Add a `[[waiver]]` for the specific asset (accepts one asset despite the default rejection).

When you enable CC-BY globally or via waiver, you are committing the project to
maintaining a credits screen that displays the `attribution_string` for every
imported CC-BY asset. Run `grep -r attribution_string wflevels/*/assets/*/manifest.json`
to audit outstanding attribution obligations.

**How to add a global accept:**

```toml
[[licence]]
id     = "CC-BY-4.0"
status = "accept"
reason = "credits screen maintained; legal sign-off"
```

**How to add a per-asset waiver** (the safer choice for one-off assets):

```toml
[[waiver]]
asset_id    = "sketchfab/abc123uid"
licence_id  = "CC-BY-4.0"
approved_by = "wbnorris"
approved_at = "2026-04-29"
reason      = "stylistic fit; credits screen updated with attribution_string"
```

Or via the CLI:

```
wf-asset policy add-waiver sketchfab/abc123uid CC-BY-4.0 \
  --reason "stylistic fit; credits updated"
```


### CC-BY-SA-4.0 — Attribution + ShareAlike

**Hard block. No waiver path.** ShareAlike (SA) requires any derivative work
to be released under the same licence. For a commercial game, that means releasing
the entire project under CC-BY-SA — incompatible with the project's commercial intent.

Assets with this licence are silently stripped from results. If you explicitly need
one, that decision requires legal review and is outside the scope of the policy file.


### CC-BY-NC-4.0 and CC-BY-NC-SA-4.0 — NonCommercial

**Hard block. No waiver path.** NonCommercial clauses prohibit any
revenue-generating use, including game sales on Steam or any storefront.


### CC-BY-ND-4.0 and CC-BY-NC-ND-4.0 — NoDerivatives

**Hard block.** ND licences prohibit creating derivative works — which includes
format conversion, scaling, re-texturing, and any modification made during the
normal level-building pipeline. Almost never appropriate for game assets.


### royalty-free — Sketchfab Standard (paid)

The **▶** icon. Assets purchased through Sketchfab's store under the Standard
licence: one-time purchase, unlimited commercial use, no attribution required.
Comparable to a stock photo royalty-free licence.

**Default policy status: not listed — blocked by default.** To accept purchased
Sketchfab Standard assets, add to `licence_policy.toml`:

```toml
[[licence]]
id     = "royalty-free"
status = "accept"
reason = "purchased Sketchfab Standard; one-time fee logged in manifest"
```

The plugin will write the purchase price as $0 in `manifest.json` (it has no
access to your payment receipt). Keep your own record of the purchase date and
order number.


### editorial-only — Press/editorial use

**Hard block.** These licences permit press coverage and editorial illustration
but explicitly exclude entertainment products and games. Cannot be waived.


### unknown — Unrecognised licence string

**Always blocked.** The provider returned a licence string the engine could not
map to any known `LicenceId`. Check the provider's site for the actual licence,
then either add a mapping (requires a code change in `src/licence.rs`) or add a
waiver referencing the correct licence ID.


## Reading the results list

The screenshot at the top of this document shows a live search for "chair" across
four providers. Key things to notice:

- **Poly Haven and Kenney results** appear at the top of the list — curated,
  all CC0, no warning markers.
- **OpenGameArt results** (lower portion) carry a **⚠** after the licence label —
  the lower-trust flag for open-upload sources.
- The **selected row** (`SchoolChair_01 [polyhaven]`) shows a thumbnail and
  `polyhaven · CC0-1.0` in the detail pane on the right.
- The **Import Selected** button is active because the selected asset passes
  the current policy.

Each row in the results list shows:

```
[thumb]  Asset Title
         Provider  ·  LICENCE-ID  [icon]
```

| Icon | Meaning |
|---|---|
| ◈ (green) | CC0-1.0 — public domain, zero obligations |
| 🛡 (yellow) | CC-BY variant — attribution required |
| ▶ | royalty-free (paid Sketchfab Standard) |
| ✕ (red) | editorial-only or unknown — policy will block import |
| ⚠ (after licence) | OpenGameArt lower-trust source |

The **Filter** dropdown above the list narrows what's shown:

| Filter | Shows |
|---|---|
| All | Everything that passes the policy |
| CC0 only | CC0-1.0 exclusively |
| CC (free) | Any CC licence — CC0, CC-BY, CC-BY-SA, etc. |
| Paid RF | royalty-free purchased assets only |

Note: the filter is applied *after* the policy. Setting Filter to "CC (free)"
while CC-BY-SA is `reject` in the policy will show CC0 and any CC-BY you've
explicitly accepted, but *not* CC-BY-SA.


## Sketchfab setup

Sketchfab is the only provider that requires authentication. Search works without
a key (you can browse and preview); download requires a Bearer API token.

**How to add your key:**

1. Visit `sketchfab.com/settings#api-token` and copy your token.
2. In Blender: **Edit → Preferences → Add-ons**, search for **World Foundry**.
3. Paste the token into the **Sketchfab API Key** field.

The field is stored in Blender's user preferences (not in any project file or
environment variable). It is masked as a password field in the UI.

**Enable Sketchfab in the panel:**

In the **Providers:** box, toggle **Sketchfab** on. If no API key has been set,
the panel shows an information note:

```
No API key — search works, download won't.
Set key in Edit › Preferences › Add-ons › World Foundry.
```

With a key set, enabling the toggle and searching returns Sketchfab results
alongside the CC0 providers. Results carry per-asset licence badges — a single
Sketchfab search may return CC0, CC-BY, Editorial, and paid assets all at once;
the policy filter strips everything that isn't accepted.

**For the CLI** (`wf-asset` binary), set the environment variable instead:

```bash
export WF_SKETCHFAB_API_KEY="your-token-here"
wf-asset search "medieval chair" --provider sketchfab
```


## Importing an asset

1. Run a search and select a result row.
2. Click **Import Selected**.

The plugin:

- Downloads the asset to `assets/<provider>/<asset-id>/` relative to the active
  `.blend` file (created automatically).
- Writes `manifest.json` alongside the asset file (see below).
- Invokes Blender's built-in glTF importer.
- Places the imported mesh at the **3D cursor**.
- Sets a `wf_schema_path` custom property on the imported objects pointing to
  `wfsource/source/oas/statplat.oad` (the default static-platform schema).

The status bar at the top of the panel shows progress and the final result:

```
Imported "Oak Tree" (CC0-1.0) from Poly Haven; manifest written alongside asset
```

### The manifest file

Every imported asset gets a `manifest.json` next to it:

```json
{
  "licence_id":           "CC0-1.0",
  "attribution_required": false,
  "attribution_string":   "",
  "licence_url":          "https://creativecommons.org/publicdomain/zero/1.0/",
  "provider":             "polyhaven",
  "provider_id":          "oak-tree-01",
  "download_date":        "2026-04-29",
  "original_url":         "https://polyhaven.com/a/oak-tree-01",
  "download_url":         "https://cdn.polyhaven.com/...",
  "derived_from":         []
}
```

For CC-BY assets, `attribution_required` is `true` and `attribution_string`
contains the credit line the author requests (e.g. `"Oak Tree" by Jane Smith
(sketchfab.com/...)`). This string is what your credits screen must display.

**Never delete `manifest.json`.** It is the legal record of where the asset came
from and under what terms. The future `wf_audit` CI tool will validate every
asset in the level against its manifest.


## Attribution obligations audit

To see every asset in the project that requires attribution:

```bash
grep -rl '"attribution_required": true' wflevels/*/assets/
```

To extract just the credit strings for your credits screen:

```bash
grep -h '"attribution_string"' wflevels/*/assets/*/manifest.json | \
  grep -v '""' | sort -u
```


## CLI reference

The `wf-asset` binary (built from `wftools/wf_asset_provider/`) lets you use the
asset system from the terminal without opening Blender.

```bash
# Search (reads policy from current directory upward)
wf-asset search "tree" --provider polyhaven --limit 10

# Download directly
wf-asset download polyhaven/oak-tree-01 --dest wflevels/test/assets

# Show the active policy
wf-asset policy show

# List registered providers
wf-asset providers list
```

Set `WF_SKETCHFAB_API_KEY` in the environment to enable Sketchfab downloads.


## Troubleshooting

### "wf_asset_provider not loaded"

The compiled Rust extension (`.so` / `.pyd`) is missing from the add-on directory.
Build it:

```bash
cd wftools/wf_asset_provider
maturin develop --features python
```

Then copy the resulting `.so` into `wftools/wf_blender/` and reload the add-on.

### Results I expected are missing

Check the **Policy:** line in the panel. If it says `(fallback)`, the plugin
couldn't find `wflevels/licence_policy.toml` and is accepting only CC0.
Open the `.blend` file from inside `wflevels/` so the walk-up finds the policy.

Check the **Filter** dropdown — if it is set to "CC0 only" and you are searching
Sketchfab, non-CC0 results will be hidden even if they passed the policy.

### "authentication required for sketchfab"

The Sketchfab toggle is on and you attempted to download, but no API key is
configured. See §Sketchfab setup.

### A Sketchfab asset I bought is blocked

The `royalty-free` licence ID is not in your `licence_policy.toml`. Add:

```toml
[[licence]]
id     = "royalty-free"
status = "accept"
reason = "purchased Sketchfab Standard assets"
```

### An asset shows ✕ (red icon) in the list

Its licence is `editorial-only` or `unknown`. Editorial-only is a hard block with
no waiver path. For `unknown`, check the provider's page for the actual licence
text; if it maps to a known ID, file an issue so the `LicenceId::from_raw()`
table can be updated.

### Imported mesh has no WF properties, or has the wrong object type

Every imported asset is tagged with the `statplat` (static platform) schema by
default. If the asset is something else — a pickup, a door, an NPC spawn point —
open the **WF** properties panel for the object and use **Attach Schema** to
select the correct `.oad` file from `wfsource/source/oas/`.


## Licence decision flowchart

```
Is the licence CC0-1.0?
  └─ Yes → Import freely. No obligations.
  └─ No  → Is it CC-BY-4.0?
             └─ Yes → Is it in policy as accept or waived?
                        └─ Yes → Import. Add attribution_string to credits screen.
                        └─ No  → Add waiver in licence_policy.toml, then import.
             └─ No  → Is it CC-BY-SA, CC-BY-NC, CC-BY-ND, GPL, or editorial?
                        └─ Yes → Hard block. Do not import. Find a different asset.
             └─ No  → Is it royalty-free (Sketchfab paid Standard)?
                        └─ Yes → Add "royalty-free" as accept in policy. Import.
                                 Keep your purchase receipt separately.
             └─ No  → licence is unknown.
                        → Check the provider's page. If recognisable, file an
                          issue to extend LicenceId::from_raw(). Otherwise skip.
```

---

<small>

**Design reference**

- [Asset Browser Plugin Plan](plans/2026-04-28-blender-asset-browser-plugin.md) —
  v1 implementation plan: architecture, provider scope, import flow, effort estimate.
- [Sketchfab + Commercial Providers Plan](../../../.claude/plans/add-support-for-sketchfab-effervescent-rossum.md) —
  v2 implementation plan: credentials layer, Sketchfab API, licence-filter UI.
- [Level Construction Tooling Investigation](investigations/2026-04-28-level-construction-tooling.md) —
  Seam 5 context: why licence is a gate, not metadata; full provider shortlist; phased roadmap.

</small>
