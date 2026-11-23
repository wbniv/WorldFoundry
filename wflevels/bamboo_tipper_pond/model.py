"""Time and geometry for the Bamboo Tipper and Pond clock."""
import math

CAMERA_KEYS = (
    (0,-11,10,.7,0,0),
    (-3,-9,7.5,-.8,.5,0),
    (1,-6,5,2,0,.1),
    (6.8,-5,3.6,5.4,0,1.2),
    (8,-9,6,4,0,.4),
    (3,-13,9,1,0,0),
)
CAMERA_STILL=(0,-8,8.5,.7,0,0)


def spline_coefficients(segment, component):
    n=len(CAMERA_KEYS)
    p0,p1,p2,p3=(CAMERA_KEYS[i%n][component] for i in (segment-1,segment,segment+1,segment+2))
    return ((-p0+3*p1-3*p2+p3)/2,(2*p0-5*p1+4*p2-p3)/2,(-p0+p2)/2,p1)


def camera_pose(second):
    progress=(second%60)/10
    segment=int(progress);u=progress-segment
    return tuple(((a*u+b)*u+c)*u+d for a,b,c,d in (spline_coefficients(segment,i) for i in range(6)))


def phases(hour, minute, second):
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError('invalid local time')
    return ((hour % 12 + minute / 60 + second / 3600) / 12,
            (minute + second / 60) / 60)


def orbit(radius, phase):
    angle=math.tau*phase
    return radius*math.sin(angle),radius*math.cos(angle)


def tip_angle(second):
    """Tip after the minute changes, empty, and return gently to rest."""
    if second < 1: return .10*second
    if second < 2: return .10
    if second < 3: return .10*(3-second)
    return 0.0


def fill(second):
    return 0.0 if second < 3 else (second-3)/57
