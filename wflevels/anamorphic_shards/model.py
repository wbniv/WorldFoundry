"""Projection and wall-clock model for Anamorphic Shards (no engine dependencies)."""
import math

CAMERA_Y = -12.0
CAMERA_Z = 3.0
DEPTHS = (-1.5, 1.0, 4.0)
# Seven-segment order: top, upper right, lower right, bottom, lower left, upper left, middle.
SEGMENTS = ((-.42, .82, .42, .98), (.34, .05, .50, .88), (.34, -.88, .50, -.05),
            (-.42, -.98, .42, -.82), (-.50, -.88, -.34, -.05),
            (-.50, .05, -.34, .88), (-.42, -.08, .42, .08))
MASKS = (0b0111111, 0b0000110, 0b1011011, 0b1001111, 0b1100110,
         0b1101101, 0b1111101, 0b0000111, 0b1111111, 0b1101111)
DIGIT_X = (-2.55, -1.15, 1.15, 2.55)
DISPLAY_SCALE = 1.65


def digits(hour, minute):
    """Use local 24-hour time, including a leading zero."""
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError('invalid local time')
    return hour // 10, hour % 10, minute // 10, minute % 10


def camera_x(second):
    """Hold alignment for four seconds, then make a smooth closed loop."""
    t = second % 60.0
    return 0.0 if t < 4.0 else 2.7 * (1.0 - math.cos(math.tau * (t - 4.0) / 56.0)) / 2.0


def project(point, camera_x=0.0):
    x, y, z = point
    factor = -CAMERA_Y / (y - CAMERA_Y)
    return camera_x + (x - camera_x) * factor, CAMERA_Z + (z - CAMERA_Z) * factor


def unproject(x, z, depth):
    factor = (depth - CAMERA_Y) / -CAMERA_Y
    return x * factor, depth, CAMERA_Z + (z - CAMERA_Z) * factor


def fragments(digit, segment):
    """A long bar for each stroke; the strokes occupy different real depths."""
    x0, z0, x1, z1 = SEGMENTS[segment]
    depth = DEPTHS[(digit * 5 + segment * 2) % len(DEPTHS)]
    poly = ((x0,z0),(x1,z0),(x1,z1),(x0,z1))
    return [tuple(unproject((DIGIT_X[digit] + x) * DISPLAY_SCALE,
                            CAMERA_Z + z * DISPLAY_SCALE, depth) for x,z in poly)]
