"""Counting and wave motion for the Metronome Forest."""
import math

CAMERA_KEYS=((4.9,-7.7,11.44,0,0,.8),(2.8,-8.4,11.44,0,0,.8),(-2.1,-8.4,11.44,0,0,.8),
             (-4.9,-7.7,11.44,0,0,.8),(-2.8,-9.1,12.14,0,0,.8),(2.1,-9.1,12.14,0,0,.8))
CAMERA_STILL=CAMERA_KEYS[0]


def spline_coefficients(segment,component):
    n=len(CAMERA_KEYS)
    p0,p1,p2,p3=(CAMERA_KEYS[i%n][component] for i in (segment-1,segment,segment+1,segment+2))
    return ((-p0+3*p1-3*p2+p3)/2,(2*p0-5*p1+4*p2-p3)/2,(-p0+p2)/2,p1)


def camera_pose(second):
    t=(second%60)/10;i=int(t);u=t-i
    return tuple(((a*u+b)*u+c)*u+d for a,b,c,d in (spline_coefficients(i,j) for j in range(6)))


def hour_columns(hour):
    if not 0<=hour<24: raise ValueError('invalid hour')
    return hour%12 or 12


def is_green(column,row,minute):
    if not (0<=column<12 and 0<=row<5 and 0<=minute<60): raise ValueError('invalid reading')
    return column*5+row<minute


def arm_angle(index,second):
    if not (0<=index<60 and 0<=second<60): raise ValueError('invalid oscillator or second')
    return .07*math.sin(math.tau*(60+index)*second/60)
