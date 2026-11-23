"""Time and circular-track geometry for Train Loops."""
import math

RADII = {'hour': 3.0, 'minute': 4.45, 'express': 5.9}

# Camera position and look-at point, sampled every ten seconds. The route
# starts outside, crosses low over the railway, travels past its far side,
# then returns to the wide view. A closed Catmull-Rom spline joins the keys.
CAMERA_KEYS = (
    (0.0, -14.5, 16.0, 0.0, 0.0, 0.0),
    (-8.0, -10.0, 8.0, -3.0, -1.0, .5),
    (-6.0, -2.0, 4.8, -1.0, 3.0, .3),
    (0.0, 2.5, 4.2, 0.0, 6.0, .3),
    (7.0, -1.5, 5.2, 3.0, 3.0, .3),
    (9.0, -12.0, 9.0, 3.0, 0.0, .2),
)
CAMERA_STILL = (0.0, -10.6, 14.2, 0.0, 0.0, 0.0)


def spline_coefficients(segment, component):
    """Cubic coefficients in Horner order for one closed Catmull-Rom span."""
    n = len(CAMERA_KEYS)
    p0,p1,p2,p3 = (CAMERA_KEYS[i % n][component] for i in
                    (segment-1,segment,segment+1,segment+2))
    return ((-p0+3*p1-3*p2+p3)/2, (2*p0-5*p1+4*p2-p3)/2,
            (-p0+p2)/2, p1)


def camera_pose(second):
    progress = (second % 60.0) / 10.0
    segment = int(progress)
    u = progress-segment
    return tuple(((a*u+b)*u+c)*u+d for a,b,c,d in
                 (spline_coefficients(segment, component) for component in range(6)))


def phases(hour, minute, second):
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError('invalid local time')
    return {'hour': ((hour % 12) + minute/60 + second/3600)/12,
            'minute': (minute + second/60)/60,
            'express': second/60}


def pose(radius, phase):
    """Clockwise from +Y; local train nose points along +Y before rotation."""
    angle = math.tau * phase
    return (radius * math.sin(angle), radius * math.cos(angle),
            (-phase - .25) % 1.0)


def trailing_phase(lead, radians_behind):
    return (lead - radians_behind / math.tau) % 1.0
