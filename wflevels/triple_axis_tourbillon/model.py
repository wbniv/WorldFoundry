"""Local clock and cage phases for the tourbillon."""

CAMERA_KEYS=((0,-11,6,0,0,3.3),(-5,-9,5.5,-.5,0,3.8),(-5,-5,4.8,-.4,0,4),
             (0,-5,5,0,0,4),(5,-5.5,5,.4,0,4),(5,-10,6,.5,0,3.5))
CAMERA_STILL=(0,-11,6,0,0,3.3)


def spline_coefficients(segment,component):
    n=len(CAMERA_KEYS)
    p0,p1,p2,p3=(CAMERA_KEYS[i%n][component] for i in (segment-1,segment,segment+1,segment+2))
    return ((-p0+3*p1-3*p2+p3)/2,(2*p0-5*p1+4*p2-p3)/2,(-p0+p2)/2,p1)


def camera_pose(second):
    t=(second%60)/10;i=int(t);u=t-i
    return tuple(((a*u+b)*u+c)*u+d for a,b,c,d in (spline_coefficients(i,j) for j in range(6)))


def phases(hour,minute,second):
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError('invalid local time')
    t=(minute%6)*60+second
    return {'hour':((hour%12)+minute/60+second/3600)/12,
            'minute':(minute+second/60)/60,
            'outer':t/60%1,'middle':t/120%1,'inner':t/180%1}
