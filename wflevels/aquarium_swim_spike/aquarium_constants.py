"""aquarium_constants.py — the 55 gal tank as numbers, in inches and in level metres.

Single source for the aquarium plan's "The tank, exactly" table
(docs/plans/2026-09-30-aquarium-level.md). Every level-space length is
`inches × IN × WORLD_SCALE`, so a ×1 and a ×10 build come from one constant.
Phase 1 imports this from the swim spike; Phase 2 should move it to
wflevels/aquarium/ unchanged.
"""
import os

IN = 0.0254                                     # metres per inch

# WORLD_SCALE: env override so the swim spike can build ×1 and ×10 from one script.
WORLD_SCALE = float(os.environ.get('WORLD_SCALE', '10'))

EXT_X, EXT_Y, EXT_Z = 48.0, 13.0, 21.0          # exterior, inches
WALL = 0.5                                      # acrylic, inches
SAND_TOP = 2.5                                  # inches above the outer base
WATER_Z = 19.0                                  # inches above the outer base (2 in freeboard)
FISH_LEN = 3.5                                  # ocellaris, inches


def m(inches):
    """Inches → level metres at the current WORLD_SCALE."""
    return inches * IN * WORLD_SCALE


def gallons(x_in, y_in, z_in):
    return x_in * y_in * z_in / 231.0


INT_X, INT_Y, INT_Z = EXT_X - 2 * WALL, EXT_Y - 2 * WALL, EXT_Z - WALL
FILL_GAL = gallons(INT_X, INT_Y, WATER_Z - WALL)        # 45.2 gal to the water line
EXT_GAL = gallons(EXT_X, EXT_Y, EXT_Z)                  # 56.7 gal (the "55")

if __name__ == '__main__':
    print(f'WORLD_SCALE={WORLD_SCALE}: exterior {m(EXT_X):.3f} × {m(EXT_Y):.3f} × {m(EXT_Z):.3f} m, '
          f'water line {m(WATER_Z):.3f} m, sand top {m(SAND_TOP):.3f} m, fish {m(FISH_LEN):.3f} m; '
          f'fill {FILL_GAL:.1f} gal, exterior {EXT_GAL:.1f} gal')
