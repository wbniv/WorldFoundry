# 640 Xiaomi installation locations

HomePro installed the Xiaomi on 2026-09-24. Will confirmed its placement on
2026-09-25. Move the compressor
along the same exterior wall toward the divider, approximately 1.5 m into the southern
section. Move the indoor head to the southern face of that divider. Its condensate
drain runs right along the divider to the intersecting wall, enters a pump, rises into
the drop ceiling, then runs to 640's front bathroom.

The divider is `640-master-bed-S-wall-W` (plan y = 108). Direction words here follow
the original floor-plan convention, not the later real-world compass mapping. The
compressor centre is represented at plan y = 132, 1.5 m from the divider, after Will’s
follow-up to move it 50 cm farther south. Will
specified that the head is 2 m from the exterior wall along the divider; this is
represented by the head centre at plan x = −94.4. Power connects to the front
consumer unit in 640. All Xiaomi wiring and pipework stay within 640 or on its
exterior wall; none enters 639 or its joined rooms. Heights, pump dimensions and
the exact ceiling/power/refrigerant paths remain schematic. The Midea and Daikin
installations are unchanged.

## Implementation

- [x] Update the canonical generator `~/scripts/aircon-blender.py`, keeping existing
  Xiaomi object names stable and adding a visible condensate pump.
- [x] Update the installation record and regenerate the source Blender model and
  top/oblique reference images.
- [x] Rebuild the interactive and tour WorldFoundry levels from the updated source.
- [x] Inspect the generated geometry and renders; document confirmed versus
  approximate placement in the level README.

## Visual reference

[![Installed Xiaomi layout](2026-09-25-condo-xiaomi-installed/layout.png)](2026-09-25-condo-xiaomi-installed/layout.html)

The source-model top and oblique renders were regenerated in `~/docs/aircon/`. The
top-view camera now includes the compressor that the old framing clipped.

## Verification

1. Build the source model; inspect Xiaomi transforms and drain points. Verify that
   the compressor retains its exterior-wall offset and rotation, the head is on the
   divider's southern face, and the only drain rise occurs at the pump. Compare all
   non-Xiaomi source objects with the previous model.

    ```text
    PASS: 77 non-Xiaomi objects unchanged
    PASS: compressor same wall and rotation, centre 1.0 m from divider
    PASS: indoor head on living-area face of divider, centre 2.0 m from exterior wall
    PASS: drain right to pump; only upward leg at pump; ceiling route ends in front bathroom
    ```

    PASS — compared transforms and geometry with vertex/face order normalised and
    coordinates rounded to 0.00001 m. Blender's regenerated `unit-640` shell differs
    in raw ordering/float representation, but its rounded spatial geometry is unchanged.

2. Rebuild both WorldFoundry levels. Confirm the new pump and relocated Xiaomi
   objects are exported and the build completes without errors.

    ```text
    task condo-level CONDO_BLEND=/tmp/condo-xiaomi-installed/units-639-640.blend
    ✓ built /home/will/WorldFoundry-wbniv/wflevels/condo_639_640.iff (2381824 bytes)
    ✓ built /home/will/WorldFoundry-wbniv/wflevels/condo_639_640-standalone.iff (2385920 bytes)
    task tour-condo-639 CONDO_BLEND=/tmp/condo-xiaomi-installed/units-639-640.blend
    ✓ built /home/will/WorldFoundry-wbniv/wflevels/condo_639_640_tour.iff (2392064 bytes)
    ✓ built /home/will/WorldFoundry-wbniv/wflevels/condo_639_640_tour-standalone.iff (2396160 bytes)
    ```

    PASS — both exports include `640-xiaomi-condensate-pump` and the relocated head
    and compressor. The checked source model was copied to the canonical
    `~/docs/aircon/units-639-640.blend`, alongside the updated generator and renders.

3. Inspect the updated plan and oblique render, then smoke-load both engine levels.

    ```text
    PASS: condo_639_640: exit 0, rendered frame 20, 640x480, no assertion
    PASS: condo_639_640_tour: exit 0, rendered frame 20, 640x480, no assertion
    ```

    PASS — inspected the source top/oblique renders and the labelled 1440×900 layout.
    Smoke runs used `--frame-step-smoke=30 --cycles=1 -rate20`, the condo's normal
    VRAM flags and `--capture-frame=20=...`. This verifies loading/rendering; the
    full walking tour video was not regenerated.

## Follow-up: compressor 50 cm farther south

Will requested a further 50 cm move south along the same exterior wall. The centre
moves from plan y = 124 to y = 132 (Blender Y −7.75 to −8.25 m), now 1.5 m from
the divider. The refrigerant endpoint follows the compressor. The head, pump,
drain, power and all other equipment retain their positions. The initial 1.0 m
verification above records the earlier revision.

- [x] Rebuild source, renders and both walkthroughs; verify the 0.50 m delta.

```text
PASS: compressor delta (0.00, -0.50, 0.00) m; rotation and exterior-wall offset unchanged
PASS: refrigerant endpoint follows by 0.50 m
PASS: all 81 other objects unchanged, including head, pump, drain and power
PASS: compressor centre now 1.50 m from divider
PASS: condo_639_640: exit 0, rendered frame 20, 640x480, no assertion
PASS: condo_639_640_tour: exit 0, rendered frame 20, 640x480, no assertion
```

Both levels rebuilt successfully. Refreshed the source model, top/oblique renders
and labelled diagram. Also corrected the installation record and diagram caption:
**installed by HomePro on 2026-09-24**; placement reported by Will on 2026-09-25.

## Follow-up: corner column and surface trunking

Will confirmed a 40 × 40 cm column at the living room’s top-left corner and
surface-mounted services. Model the column from the finished wall faces. Route
the compressor connection around its two room-facing sides, along the interior
wall, and through the exterior wall only opposite the compressor. All Xiaomi
services receive white rectangular AC covers, with nominal 75 mm dimensions
for illustration. Power follows the wall surfaces around the front bathroom to
the consumer unit, below the drop ceiling. The pumped drain still rises into
the drop ceiling as previously reported. Heights and the penetration height
remain schematic; the exterior drop is directly opposite the compressor.

- [x] Rebuild the source and both levels with column and covered service routes.
- [x] Inspect source renders and diagram; check routing and smoke-load both levels.

Validation passed: column dimensions, column clearance, exterior routing only
opposite the compressor, white covers on all three Xiaomi service meshes, and
surface power below the drop ceiling. Both engine levels loaded and rendered
frame 20 without assertions. The full 639/640 teleport regression passed,
including saved positions, button isolation and reset on reload. Source model,
generators and reference renders were copied to their canonical home locations.

## Follow-up: below-window compressor run

From the compressor the route enters below the window, runs horizontally inside
around the column and onto the divider, then rises there to the head’s bottom
edge. Both left and right connections align with that bottom edge (2.05 m in the
model). The low run is illustrated at 0.60 m, below the assumed 0.90 m sill; its
exact height and the rise’s offset along the divider are unmeasured. The pump
centre is lowered to 2.00 m to retain a slight fall from the head into the pump.
This supersedes the high window run/exterior drop in the previous revision.

- [x] Rebuild source, renders and both levels; check height sequence and connections.

Verified the level below-window run, column clearance, single rise on the divider,
left/right connections at the head bottom and downward fall to the pump. Inspected
the corrected diagram and oblique render. Both rebuilt engine levels loaded and
rendered frame 20 without assertions.
