"""aquarium_constants.py — the 55 gal tank as numbers, in inches and in level metres.

Single source for the aquarium plan's "The tank, exactly" table
(docs/plans/2026-09-30-aquarium-level.md). Imported by blender_create_aquarium.py
and tests/test_aquarium_level.py, so the docs, the level and the test cannot drift.

Every level-space length is `inches × IN × WORLD_SCALE`. WORLD_SCALE is one constant:
Phase 1 (wflevels/aquarium_swim_spike/) measured ×1 and ×10 and ×10 won, so this is
not an env override any more. clownfish.py takes WORLD_SCALE and FISH_LEN from here
(its DEFAULT_WORLD_SCALE and FISH_REAL_LENGTH_M), so the fish and the tank agree.

Run it to print the table: python3 wflevels/aquarium/aquarium_constants.py
"""

IN = 0.0254                                     # metres per inch
WORLD_SCALE = 10.0                              # Phase 1 verdict: ×10 (×1 fails on fixed constants)

# ── The tank (inches) ────────────────────────────────────────────────────────
EXT_X, EXT_Y, EXT_Z = 48.0, 13.0, 21.0          # exterior
WALL = 0.5                                      # acrylic, every face
SAND_TOP = 2.5                                  # sand top above the outer base (2 in deep)
WATER_Z = 19.0                                  # water line above the outer base (2 in freeboard)
FISH_LEN = 3.5                                  # ocellaris
ANEMONE_SPAN = 7.0                              # bubble-tip, across the tentacle crown

HX, HY = EXT_X / 2, EXT_Y / 2                   # 24, 6.5   exterior half-extents
IX, IY = HX - WALL, HY - WALL                   # 23.5, 6.0 inner faces
INT_X, INT_Y, INT_Z = EXT_X - 2 * WALL, EXT_Y - 2 * WALL, EXT_Z - WALL


def m(inches):
    """Inches → level metres at WORLD_SCALE."""
    return inches * IN * WORLD_SCALE


def gallons(x_in, y_in, z_in):
    return x_in * y_in * z_in / 231.0


FILL_GAL = gallons(INT_X, INT_Y, WATER_Z - WALL)        # 45.2 gal to the water line
EXT_GAL = gallons(EXT_X, EXT_Y, EXT_Z)                  # 56.7 gal (the "55")
BRIM_GAL = gallons(INT_X, INT_Y, INT_Z)                 # 50.1 gal

# ── Level metres (origin = centre of the footprint, z = 0 = outer base) ────
EXT_X_M, EXT_Y_M, EXT_Z_M = m(EXT_X), m(EXT_Y), m(EXT_Z)   # 12.192 × 3.302 × 5.334
INNER_X_M, INNER_Y_M = m(IX), m(IY)                     # ±5.969, ±1.524
FLOOR_M = m(WALL)                                       # 0.127 inner floor
SAND_TOP_M = m(SAND_TOP)                                # 0.635
WATER_LINE_M = m(WATER_Z)                               # 4.826

# ── Anemone, rock, fish spawn (plan § "Coordinates") ─────────────────────────
ANEMONE_X, ANEMONE_Y = 0.25 * WORLD_SCALE, 0.0          # +2.5 m, 0 at ×10; the rock is under it
ANEMONE_ZONE_RADIUS = 0.22 * WORLD_SCALE                # 2.2 m at ×10 (camshot B zone; Phase 3)
FISH_SPAWN = (-0.16 * WORLD_SCALE, 0.0, 0.24 * WORLD_SCALE)   # (−1.6, 0, 2.4) m at ×10

# ── Water = fog (plan § 7). Distances scale with WORLD_SCALE; keep COMPLETE ≪ 1000 m
#    (past the 1000 m far clip fog is effectively off).
FOG_COLOR = 0x0d5f7a
FOG_START = 0.6 * WORLD_SCALE                           # 6 m at ×10
FOG_COMPLETE = 4.0 * WORLD_SCALE                        # 40 m at ×10

# ── Camshot A: locked, straight-on from outside the front, whole tank in frame ─
CAM_A_POS = (0.0, -1.1 * WORLD_SCALE, EXT_Z_M / 2)      # y −11 m at ×10
CAM_A_LOOK = (0.0, 0.0, EXT_Z_M / 2)                    # the tank's centre

# ── Camshot B: the anemone close-up (Phase 3), outside the front glass like A. The
#    Camera actor's bbox (CAMERA_HALF) must stay clear of every place the fish's box can
#    reach, or the bungee camera "collides" with the Mass-1 Player and climbs.
CAM_B_POS = (ANEMONE_X, -0.22 * WORLD_SCALE, 0.175 * WORLD_SCALE)   # tuned from captures (plan § Phase 3)
CAM_B_LOOK = (ANEMONE_X, ANEMONE_Y, 0.162 * WORLD_SCALE)            # LookB's rest point (anemone column)
CAM_B_LOOK_FOLLOW = 0.35                                # share of (fish − look) LookB leans toward the fish
CAMERA_HALF = 0.02 * WORLD_SCALE                        # Camera actor bbox half-size (0.2 m at ×10)
ANEMONE_ZONE_HYST = 0.03 * WORLD_SCALE                  # leave B only 0.3 m past the entry radius

# ── Controls (Phase 1, measured on the placeholder; re-validated in Phase 3 step 15) ─────
SWIM_SPEED = m(12.0)                                    # 12 in/s × scale = 3.048 m/s written while held
DART_SPEED = 2 * SWIM_SPEED                             # 6.096 = Max Air Speed (AirHandler caps to it)
DART_TIME = 0.15                                        # s of burst (3 ticks at 20 Hz), then the glide
CLAMP_MARGIN = m(0.25)                                  # keep the visible fish 0.25 in off a wall / the water line
# Jolt's CharacterVirtual counts any contact within its padding (0.02 m) + predictive contact
# distance (0.1 m) under the capsule as floor (OnGround → MarbleHandler, walk-stairs, stick-to-
# floor). The floor clamp keeps the capsule this far over the sand so the fish is never "standing".
# Jolt's constants are absolute metres, so this does not scale with WORLD_SCALE.
GROUND_CLEARANCE = 0.15

if __name__ == '__main__':
    print(f'WORLD_SCALE={WORLD_SCALE}: exterior {EXT_X_M:.3f} × {EXT_Y_M:.3f} × {EXT_Z_M:.3f} m, '
          f'inner x ±{INNER_X_M:.3f} y ±{INNER_Y_M:.3f}, water line {WATER_LINE_M:.3f} m, '
          f'sand top {SAND_TOP_M:.3f} m, fish {m(FISH_LEN):.3f} m; '
          f'fill {FILL_GAL:.1f} gal, brim {BRIM_GAL:.1f} gal, exterior {EXT_GAL:.1f} gal; '
          f'fog 0x{FOG_COLOR:06x} {FOG_START:g}→{FOG_COMPLETE:g} m; camera A {CAM_A_POS}')
