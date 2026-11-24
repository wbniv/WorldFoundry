"""Moon Lantern wall-time geometry and approximate astronomical phase."""
import math


def clock_phases(hour, minute, second):
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError('invalid local time')
    return ((hour % 12 + minute / 60 + second / 3600) / 12,
            (minute + second / 60) / 60)


def moon_phase(day, hour, minute, second, utc_offset_minutes):
    """Approximate geocentric phase in [0,1), new=0, full=.5.

    day is local calendar days since 2000-01-01. The low-order solar and
    lunar ecliptic longitudes are evaluated at UTC days from J2000 noon.
    This is an approximation, not an ephemeris or a horizon-orientation model.
    """
    days = day + (hour + minute / 60 + second / 3600 - utc_offset_minutes / 60) / 24 - .5
    rad = math.pi / 180
    moon = 218.316 + 13.176396 * days + 6.289 * math.sin((134.963 + 13.064993 * days) * rad)
    sun = 280.460 + .9856474 * days + 1.915 * math.sin((357.528 + .9856003 * days) * rad)
    return ((moon - sun) / 360) % 1


def illuminated_fraction(phase):
    return (1 - math.cos(math.tau * phase)) / 2


def dial_point(radius, phase):
    return radius * math.sin(math.tau * phase), radius * math.cos(math.tau * phase)
