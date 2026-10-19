"""site_constants.py — the condo's real-world placement, shared by
blender_create_condo.py (level geometry) and make_site_textures.py (sky/ground
textures) so the two can never disagree about where north, west or the sun is.

Level axes ↔ compass (the model's back/balconies are +Y and face straight west):

    +X north    −X south    +Y west (balconies, river)    −Y east (front doors)

Direction of true azimuth θ (0 = N, clockwise): (cos θ, −sin θ, 0).
Level origin (0, 0) is the map pin. Plan: docs/plans/2026-09-19-condo-site-skybox.md
"""
import math

SITE_LATLON  = (13.6935894, 100.5334137)   # 34 Soi Sathu Pradit, Bang Phong Phang, Yan Nawa
SITE_OFFSET_EN = (0.0, 0.0)                # metres (east, north) from the pin to the level origin.
                                           # The pin geocodes to the Soi 34 / Sathu Pradit Road corner
                                           # (a road in OSM, no footprint); nudge this to put the
                                           # units over the real building, then `task condo-textures`.
UNIT_FLOOR   = 6                           # ground floor counts as 1 (unit numbers 6xx)
STOREY_CLEAR = 3.0
SLAB_T       = 0.15                        # the model's slab: slab-bottom faces at z = −0.15
UNIT_Z       = (UNIT_FLOOR - 1) * (STOREY_CLEAR + SLAB_T)   # 15.75 m: unit floor top

GROUND_HALF  = 80.0                        # site-map quad ±80 m → condo_ground.tga 512² (0.3125 m/px)
GROUND_PX    = 512
SKY_W, SKY_H = 1024, 512                   # condo_sky.tga equirect: u = θ/360, v = 1 at zenith
SKY_R        = 160.0                       # dome radius: > farthest ground corner (≈116 m), < Yon 200

# The Sun actor is authored with rotation_euler = (π/2 − alt, 0, az). The engine takes the
# light direction as the actor's local +X (game/light.hpi:31 `Vector3 src(unitX); src *= Matrix()`),
# which a pitch about X never moves — so only the heading reaches the renderer: the light
# travels along (cos az, sin az, 0) in level axes, i.e. it *comes from* compass
# θ = 180 − az … here 150° (SSE), horizontally. The painted sun uses that azimuth and the
# intended altitude so the sky reads as the same time of day.
SUN_ALT_DEG  = 50.0
SUN_AZ_DEG   = 30.0


def sun_compass():
    """(azimuth θ, altitude) of the painted sun, degrees, compass convention."""
    lx, ly = math.cos(math.radians(SUN_AZ_DEG)), math.sin(math.radians(SUN_AZ_DEG))   # light travel dir
    fx, fy = -lx, -ly                                                                # where it comes from
    theta = math.degrees(math.atan2(-fy, fx)) % 360.0                                # (cos θ, −sin θ) ⇒ θ = atan2(−y, x)
    return theta, SUN_ALT_DEG


def compass_to_level(theta_deg):
    """Unit XY vector in level axes for a compass azimuth."""
    t = math.radians(theta_deg)
    return math.cos(t), -math.sin(t)


def level_to_compass(x, y):
    """Compass azimuth (degrees, 0 = N clockwise) of a level-space XY offset."""
    return math.degrees(math.atan2(-y, x)) % 360.0
