"""Wall-clock reading and smooth phase functions for Lava-lamp Digits."""
import math

# Segment order: top, upper right, lower right, bottom, lower left,
# upper left, middle. All four places are always shown, including leading zero.
DIGITS = ('abcdef', 'bc', 'abdeg', 'abcdg', 'bcfg',
          'acdfg', 'acdefg', 'abc', 'abcdefg', 'abcdfg')
SEGMENTS = 'abcdefg'


def reading(hour, minute):
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError('invalid local time')
    return hour // 10, hour % 10, minute // 10, minute % 10


def ease(t):
    t = max(0., min(1., t))
    return t * t * (3 - 2 * t)


def phase(second):
    if not 0 <= second < 60:
        raise ValueError('invalid second')
    if second < 6:
        return 'forming', ease(second / 6)
    if second < 54:
        return 'holding', 1.
    return 'melting', ease((60 - second) / 6)


def rise(index, second):
    """Background blob height, looping at its own staggered cadence."""
    return ((second / 20 + index * .137) % 1)


def camera(second):
    angle = math.tau * second / 60
    return tuple(48 * value for value in (0.6 * math.sin(angle), -8.5, 4.4 + .20 * math.cos(angle)))
