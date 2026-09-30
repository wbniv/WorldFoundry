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
ANEMONE_SPAN = 12.0                             # bubble-tip, across the tentacle crown (Phase 4: a large
                                                # E. quadricolor; was 7 in, which read stubby against the mockup)

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
# Phase 2–3 had the eye at the tank's half height (2.667 m), aimed level: already straight-on
# (every tank edge projects where a level camera puts it, to 1 px), but 2 m over the sand, so the
# 3 m-deep sand floor showed as a band in perspective and read as "looking down". Phase 4 lowers
# the eye and keeps the aim level (Target = Follow = Track Object = LookAt at the eye's height);
# the fixed 60° FOV cannot be narrowed, so the distance stays and the tank still spans ~85 %.
CAM_A_EYE_Z = 0.19 * WORLD_SCALE                        # 1.9 m at ×10: the lower third of the water
CAM_A_POS = (0.0, -1.1 * WORLD_SCALE, CAM_A_EYE_Z)      # y −11 m at ×10
CAM_A_LOOK = (0.0, 0.0, CAM_A_EYE_Z)                    # level aim: no pitch

# ── Camshot B: the anemone close-up (Phase 3), outside the front glass like A. The
#    Camera actor's bbox (CAMERA_HALF) must stay clear of every place the fish's box can
#    reach, or the bungee camera "collides" with the Mass-1 Player and climbs.
CAM_B_POS = (ANEMONE_X, -0.25 * WORLD_SCALE, 0.20 * WORLD_SCALE)    # Phase 4: back 0.3 m for the 12 in crown
CAM_B_LOOK = (ANEMONE_X, ANEMONE_Y, 0.20 * WORLD_SCALE)             # LookB's rest point: level aim at the crown
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

# ── Steer and swim (Phase 4). A fish only moves along its facing: input sets a target facing,
#    yaw/pitch turn toward it as spring-dampers, and the script writes speed × facing each tick.
#    Lengths/speeds in body lengths where it matters (L = FISH_LEN at WORLD_SCALE; space is ×10,
#    time is not, so frequencies and time constants are real seconds). Sources in comments:
#    "verified" = opened and checked, "unverified", or "ours" (tuned by looking at captures).
L_M = m(FISH_LEN)                                       # 0.889 m at ×10
# Gait: burst-and-coast (Wu, Yang & Zeng 2007, JEB 210:2181, verified: koi; drag while coasting
# ≈ 1/4 of bursting, ~45 % energy saved). Fish keep the CYCLE constant and change the burst share to
# set the speed (Li et al. 2021, Commun. Biol. 4:40: as reported by the orchestrator, not opened).
GAIT_CYCLE = 0.5                                        # s per burst+coast cycle (unverified; ours)
GAIT_DUTY = 0.4                                         # burst share at cruise (ours)
BURST_SPEED = 1.309 * SWIM_SPEED                        # 3.99 m/s: burst target; the mean is SWIM_SPEED
TAU_ACCEL = 0.10                                        # s, speed-up during a burst (ours)
TAU_COAST = 0.50                                        # s, coast decay within a cycle (ours)
TAU_GLIDE = 0.45                                        # s, stop after release: glide ≈ 0.45 × speed ≈ 1.4 m (Phase 1)
TAU_DART = 0.05                                         # s, the dart's speed-up
# Steering (ours; second-order: rate' = wn² err − 2 ζ wn rate). Pitch is slower than yaw.
YAW_WN, YAW_ZETA, YAW_WMAX = 8.0, 0.9, 1.25             # rad/s, -, rev/s (≈ 180° in 0.5 s)
PITCH_WN, PITCH_ZETA, PITCH_WMAX = 5.0, 0.8, 0.40       # rad/s, -, rev/s (144°/s)
PITCH_MAX = 40.0 / 360                                  # rev: Up/Down alone climbs/dives this steeply
PITCH_DIAG = 30.0 / 360                                 # rev: with a horizontal direction too
BANK_MAX = 15.0 / 360                                   # rev: bank into a turn at the full yaw rate
BANK_GAIN = BANK_MAX / YAW_WMAX                         # rev of bank per rev/s of yaw
TURN_DIP = 0.25                                         # burst speed × (1 − 0.25 |yaw rate| / max)
TAU_WALL = 0.25                                         # s: speed ≤ room ahead / 0.25 s (eases to a stop)
FLATTEN_D = 0.06 * WORLD_SCALE                          # 0.6 m: pitch flattens within this of the sand/surface
FIN_HALF_WIDTH = 0.014 * WORLD_SCALE                    # 0.14 m: body 0.11 + flared pectorals / tail beat

# ── Anemone sway (Phase 4). The tentacles are six clumps (back/front row × left/centre/right),
#    each an anchored Mass-0 platform whose origin is its base on the oral disc. The Director
#    rotates each one about that base every tick: B (in the X–Z plane) = amp_b·sin φ and
#    A (toward / away from the glass) = amp_a·sin(φ + ¼), with φ = t / period + phase. Purely
#    visual: net zero over a period, bounded, no Jolt body. Periods are whole 20 Hz ticks and at
#    least 0.25 s apart, so no two clumps ever lock together (with periods only 0.2 s apart two
#    clumps swung in near-lockstep for most of a 10 s window, |r| 0.97, in the first run).
#    (row, side, amp_b deg, amp_a deg, period s, phase rev)
ANEMONE_CLUMPS = [
    ('back', 'l', 5.0, 1.5, 3.30, 0.00),
    ('back', 'c', 4.0, 1.2, 4.75, 0.37),
    ('back', 'r', 5.0, 1.5, 4.30, 0.71),
    ('front', 'l', 5.5, 1.5, 3.90, 0.18),
    ('front', 'c', 4.5, 1.2, 3.55, 0.55),
    ('front', 'r', 5.5, 1.5, 3.05, 0.89),
]
SWAY_MB_BASE = 720                                      # the sway's mailboxes: 720..739 (level 700..719, fish 600..639)


def clump_name(row, side):
    return f'anemone-tent-{row}-{side}'


if __name__ == '__main__':
    print(f'WORLD_SCALE={WORLD_SCALE}: exterior {EXT_X_M:.3f} × {EXT_Y_M:.3f} × {EXT_Z_M:.3f} m, '
          f'inner x ±{INNER_X_M:.3f} y ±{INNER_Y_M:.3f}, water line {WATER_LINE_M:.3f} m, '
          f'sand top {SAND_TOP_M:.3f} m, fish {m(FISH_LEN):.3f} m; '
          f'fill {FILL_GAL:.1f} gal, brim {BRIM_GAL:.1f} gal, exterior {EXT_GAL:.1f} gal; '
          f'fog 0x{FOG_COLOR:06x} {FOG_START:g}→{FOG_COMPLETE:g} m; camera A {CAM_A_POS}')
