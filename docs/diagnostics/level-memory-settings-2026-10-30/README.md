# Level memory settings: cast1 check

On Chromecast HD, J‑36131a45c778 installed or reused the frozen baseline APK
`3d8c01db3273074744928c6235dd97930fc8891baf7384bba32fb2279b18977e`, opened
the first Baseline settings owner, selected Level Memory, and returned to play.
The [capture](cast1-final/input-frame-004.png) shows all 4 authored values as
read-only and the warning that launch overrides affect the display only. The
[input recipe](cast1-recipe.json) records the navigation. This checks display
and basic runtime loading, not changed allocator sizes or a live resize.

The preceding validator job J‑1c913fdddae6 loaded the level and observed the
new fields, but failed its `baseline_catalog_attached` assertion because it
expects the old schema name `BaselineSettings`; the current schema is
`Settings`. Its coordinator cleanup was subsequently verified. The direct
input check above did not use that stale assertion.
