# Planetarium dome view (`wflevels/dome/`) — sunburst on a hemisphere

**Branch:** `2026-new-level`

Fourth view in the filesystem-visualization family (FSN node-link · Filelight flat sunburst ·
KDirStat treemap · **this**), on the same **§6 flat-table + Forth-policy core**. The planetarium
dome is the **Filelight sunburst wrapped onto a hemisphere**: the player stands at the centre and
**looks up**; the cwd sits as a cap directly overhead (the zenith), its children fan out in
**concentric elevation bands descending toward the horizon**, each segment's **azimuth arc ∝
recursive size**, **coloured per branch** (Filelight's hue signature).

## The headline: this view needs ZERO engine code

Every prior view added a C emitter (`fsn-scan`, `fl-scan`, `tm-scan`). The dome is the first that
**reuses an existing emitter verbatim**: it reads the *same* `fl-scan` table Filelight already
produces —

| `fl-scan` row field | Filelight (flat) uses it as | Dome (hemisphere) uses it as |
|---------------------|-----------------------------|------------------------------|
| `seg-depth`         | radius ring (depth·9 u)     | **elevation band** (depth→φ range) |
| `seg-a0` / `seg-a1` | azimuth arc (revolutions)   | **azimuth arc** (revolutions) — *unchanged* |
| `seg-size`          | Z-extrusion height          | *unused* (size already lives in the arc) |
| `seg-branch`        | per-branch hue              | per-branch hue — *unchanged* |

So the dome is **a new Blender level + a Director `.fth` render policy + new spherical-patch band
meshes** — `scripting_zforth.cc` is **not touched, the engine binary is not rebuilt**. This is the
strongest possible proof of the platform thesis: *"a new view is a new `.fth` + meshes."* The only
runtime primitive it needs — `spawn0`, `set-rotation` (Z-heading by revolutions), `set-color`,
`hsv>rgb`, `fl-config`, `fl-scan`, `seg-*` — all already ship for Filelight.

## Mockups

### Side cross-section — the dome you stand inside and look up at

```
                       depth 0 = cwd CAP at the zenith (straight overhead)
                              ╔═══════╗   φ∈[72°,90°]
                         ╔════╝       ╚════╗
                    ╔════╝   depth 1 band   ╚════╗   φ∈[50°,72°]   ← cwd's children
                ╔══╝       depth 2 band         ╚══╗   φ∈[28°,50°] ← grandchildren
             ╔═╝          depth 3 band              ╚═╗  φ∈[8°,28°]
             ║                  (P)                    ║  ← player at centre, camera ↑
   ──────────╨────────────────────────────────────────╨──────────  floor (z≈0, horizon φ=0)
   hemisphere radius R≈35 ·  deeper = lower toward the horizon ·  arc ∝ size ·  hue ∝ branch
```

### Top-down (what the player sees looking up) — azimuth ∝ size

```
                 ░░ band 3 (depth-3, near horizon) ░░
            ╔═══════════════════════════════════════╗
        ╔═══╣      band 2  (grandchildren)           ╠═══╗
      ╔═╣       band 1   src │ usr │ home │ var │ …      ╠═╗   ← arc ∝ recursive size
      ║ ║                ┌────────────────────────┐      ║ ║
      ║ ║                │   depth-0 ZENITH CAP    │      ║ ║   cwd, "you are here"
      ║ ║                │        (P looks up)      │      ║ ║
      ╚═╣                └────────────────────────┘      ╠═╝
        ╚═══╗                                         ╔═══╝
            ╚═════════════════════════════════════════╝
   each band is a full 360° ring of azimuth wedges; a child's wedge sits at the SAME
   azimuth as its Filelight counterpart — only the radius→elevation mapping changed.
```

### Colour — per-branch hue (identical policy to Filelight)

```
   depth-1 branch i → hue = (i mod 8)/8 ; deeper bands desaturate (pale tint of the ancestor)
     src=red   usr=green   home=cyan   var=blue   …          value stays bright
```

### Geometry — one baked spherical patch per band, instanced by a Z-rotation

```
  Bake ONE annular spherical patch per elevation band (band1/2/3), centred on azimuth 0,
  curving across its φ range on a sphere of radius R — exactly analogous to Filelight's
  baked annular-sector wedge, but on the hemisphere instead of the flat plane. A spawned
  instance needs only a Z-rotation (heading, revolutions — set-rotation) to sit on its arc.
  depth 0 → a full-circle spherical CAP at the zenith (the disk_geo analogue). No height
  scale (size is in the arc), no trig on the Forth side (the mesh bakes the φ/θ curvature).
```

## Geometry — `spherical_band_geo` (Z-up, base of the dome at z≈0)

Hemisphere radius `R = 35`. A point at azimuth θ, elevation φ (0 = horizon, π/2 = zenith):

```
P(θ, φ) = ( R·cos φ·cos θ ,  R·cos φ·sin θ ,  R·sin φ )
```

**Elevation bands** (deeper = lower; reserve the cap for cwd, stop band-3 above the horizon so
it never clips the floor):

| depth | φ range      | mesh        |
|-------|--------------|-------------|
| 0 cwd | [72°, 90°]   | zenith cap (full circle) |
| 1     | [50°, 72°]   | `Band1Template` |
| 2     | [28°, 50°]   | `Band2Template` |
| 3     | [8°, 28°]    | `Band3Template` |

```python
def spherical_band_geo(R, phi0_deg, phi1_deg, sweep_deg, az_segs=4, el_segs=3):
    """One spherical-shell patch: azimuth [0,sweep], elevation [phi0,phi1], on radius R.
    Centred on azimuth 0 so a spawned instance needs only a Z-rotation to land on its arc.
    No culling in the desktop GL path → single winding; faces wound so normals point
    INWARD (toward the player below) for correct lit appearance under the down-light."""
    phi0, phi1, sw = map(math.radians, (phi0_deg, phi1_deg, sweep_deg))
    verts, nθ = [], az_segs + 1
    for j in range(el_segs + 1):
        phi = phi0 + (phi1 - phi0) * j / el_segs
        for i in range(az_segs + 1):
            th = sw * i / az_segs
            verts.append((R*math.cos(phi)*math.cos(th),
                          R*math.cos(phi)*math.sin(th),
                          R*math.sin(phi)))
    idx = lambda j, i: j*nθ + i
    faces = [(idx(j,i), idx(j,i+1), idx(j+1,i+1), idx(j+1,i))   # CCW seen from outside
             for j in range(el_segs) for i in range(az_segs)]   # → normal outward; flip if dark
    return verts, faces
```

**Zenith cap** = the `disk_geo` analogue: a fan of triangles from the pole `(0,0,R)` out to the
φ=72° circle, full 360°. Spawned once at the origin, no rotation; coloured the fixed light-blue
"you are here" marker.

**Room / floor.** The hemisphere occupies X,Y ∈ [−R, R], Z ∈ [0, R]. Room bbox contains it with
margin (≈ X,Y[−45,45], Z[−2,42]); floor a thin slab at z≈0; player spawns at the centre `(0,0,1)`.

## Camera — the one genuinely new thing: look UP

Filelight's camera is high, looking *down*; the dome's is low at the centre, pitched *up* at the
zenith cap. Author the CamShot at an up-looking pose and **do not call `fl-flydown`** (the table is
otherwise identical):

- Camera / CamShot start `(0, −6, 3)` — just behind & above the player's head.
- `Target` (look-at) high at the zenith `(0, 2, 30)` → an up-and-slightly-forward gaze that frames
  the cap overhead with the descending bands around it; `Follow` = the player at centre.
- `Track Object = Player`, `Rotation = Fixed`, `FOV ≈ 80` (wide, to take in the dome).

(Tune the exact pose in M2 against a screenshot; a slow azimuthal camera spin is a future tunable,
deferred — see Out of scope.)

## Director `.fth` — the render policy (hot-reloadable, no height curve)

```forth
\ wf
: BAND1 12 ; : BAND2 13 ; : BAND3 14 ; : CAP 15 ;
: MAXDEPTH 3 ; : MAXNODES 450 ; : PLAYER-IDX 10 ;
: WEDGE-STEP 0.0167 ;                       \ 6° in revolutions; == baked sweep_deg
: band-tmpl ( depth -- tmpl )
   dup 1 = if drop BAND1 else
   dup 2 = if drop BAND2 else drop BAND3 fi fi ;
: seg-color ( branch depth -- 0xRRGGBB )    \ identical to Filelight's per-branch hue
   swap 8 mod 8 /  swap 1 - 0.18 * 0.85 swap - 0.25 max  0.95  hsv>rgb ;
: place-wedge ( i angle -- )                \ NO set-z-scale — size is in the arc
   over seg-depth band-tmpl spawn0  >r
   r@ swap set-rotation
   r@ over seg-branch 2 pick seg-depth seg-color set-color
   r> drop drop ;
: place-cap ( i -- )
   CAP spawn0 >r  r@ 0xd0e8ff set-color  r> drop drop ;
: tile-wedges ( i -- )
   dup seg-a1 over seg-a0
   begin 2 pick over place-wedge  WEDGE-STEP +  2dup < until  2drop drop ;
: tile-seg ( i -- )
   dup seg-depth 0 = if place-cap else tile-wedges fi ;
: render-dome
   fl-scan dup 0 = if drop else 0 do i tile-seg loop fi ;
10 read-mailbox 0 = if
  1 10 write-mailbox
  MAXDEPTH MAXNODES PLAYER-IDX fl-config
  render-dome
fi
```

(Static — no `fl-navigate` / `fl-flydown` calls. The whole dome renders once on the first frame,
exactly like the static treemap.)

## Files & changes

- **NEW** `wflevels/dome/blender_dome.py` — scaffolding cloned from `blender_filelight.py`
  (astronaut, lights, floor, room, Director, ActBoxOR) with: the up-looking camera; three
  `spherical_band_geo` band templates (idx 12/13/14) + a zenith `cap_geo` template (idx 15); the
  Director script above. + its build artifacts via `task build-level -- dome`.
- **NEW** `task run-dome` in `Taskfile.yml` (mirror of `run-filelight`).
- **NEW** this plan; **TODO.md** open-item update (mark dome done, link the commit).
- **NO engine change** — `scripting_zforth.cc` untouched, no `task build`.

## Verification

```
blender --background --python wflevels/dome/blender_dome.py
task build-level -- dome
task run-dome                                # walk to centre, look up at the dome
```

- M1 — static dome renders: `FL: scanned '.' — N segments`, bands tile the hemisphere overhead,
  zenith cap present; no asserts, no "fell out of room", no terminate. Actor count < 500 pool.
- M2 — per-branch hue reads correctly (distinct hues per depth-1 branch, paler with depth); camera
  framing shows the cap overhead with descending bands; screenshot into
  `wflevels/dome/screenshots/`.
- M3 — **hot-reload proof**: edit only the Director `.fth` (e.g. band φ ranges via re-bake, or the
  hue policy), re-export + `task build-level -- dome`, relaunch → look changes, **engine binary
  untouched** (no `task build`).

Paste raw output + PASS/FAIL under each step on completion.

## Out of scope (future tunables, all policy-only)
- **Azimuthal camera spin** (planetarium drift) — a per-frame camshot heading write; needs either a
  tiny C helper or a Forth frame-counter driving a mailbox.
- **Walk-/aim-to-re-root navigation** — the dome is static; the `fl-navigate` pattern is available
  (map player *facing* → azimuth instead of position → polar, since the wedges are overhead).
- **Size→radial relief** — bump each patch outward (larger R) by `seg-size` for a domed-relief look
  (redundant with arc-encoding; a `set-scale` radial nudge if wanted).
- **Tiered monument (#2)** — the remaining sunburst variant; stacks the flat rings at rising Z.
