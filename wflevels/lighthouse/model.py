"""Wall-clock dial geometry for the Lighthouse level."""
import math

RING_RADIUS = 7.0
BOAT_RADIUS = 5.35
CAMERA_KEYS = (
    (0, -15.8, 16.8, 0, 0, 1.8),
    (4.0, -15.5, 15.7, 0, 0, 1.8),
    (6.0, -14.5, 14.8, 0, 0, 1.8),
    (1.0, -16.5, 16.1, 0, 0, 1.8),
    (-5.0, -15.2, 15.0, 0, 0, 1.8),
    (-4.0, -15.5, 16.3, 0, 0, 1.8),
)
# Keep the whole dial in view while bringing the rock detail closer to camera.
CAMERA_KEYS = tuple((tx + (x-tx)*.86, ty + (y-ty)*.86, tz + (z-tz)*.86, tx, ty, tz)
                    for x,y,z,tx,ty,tz in CAMERA_KEYS)
CAMERA_STILL = CAMERA_KEYS[0]


def phases(minute, second):
    if not 0 <= minute < 60 or not 0 <= second < 60:
        raise ValueError('invalid local time')
    return (minute + second / 60) / 60, second / 60


def lit_windows(hour):
    if not 0 <= hour < 24:
        raise ValueError('invalid local hour')
    return hour % 12


def point(radius, phase):
    angle = math.tau * phase
    return radius * math.sin(angle), radius * math.cos(angle)


def spline_coefficients(segment, component):
    n = len(CAMERA_KEYS)
    p0, p1, p2, p3 = (CAMERA_KEYS[i % n][component] for i in (segment-1, segment, segment+1, segment+2))
    return ((-p0+3*p1-3*p2+p3)/2, (2*p0-5*p1+4*p2-p3)/2, (-p0+p2)/2, p1)


def camera_pose(second):
    t = (second % 60)/10
    i = int(t)
    u = t-i
    return tuple(((a*u+b)*u+c)*u+d for a,b,c,d in (spline_coefficients(i,j) for j in range(6)))
