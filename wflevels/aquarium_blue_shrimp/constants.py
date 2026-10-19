"""Blue Shrimp dimensions, authored colony routes and tuning (level metres).

No dependency on wflevels/aquarium: that level is being edited independently.
The same 48 x 13 x 21 inch tank is represented at world scale 10.
"""
import math

LEVEL = 'aquarium_blue_shrimp'
HX, HY, HEIGHT = 6.096, 1.651, 5.334
WALL, SAND, WATER = .127, .635, 4.826
LIMIT_X, LIMIT_Y = 5.08, .73  # full rig, antenna reach and turn margin
HULL_LIFT = .33  # capsule clears Jolt's predictive ground contact; visual feet at sand
SPAWN = (1.9, -.65, SAND+HULL_LIFT)
CAMERA = (0, -11.8, 2.25)
CLOSE_CAMERA = (2.0, -3.7, 1.30)
CLOSE_LOOK = (2.0, -.4, .95)
ROCKS = [(-2.65, .30, .68, .65, .85), (-1.75, .50, .48, .48, .60),
         (3.95, .55, .72, .60, .62)]  # x,y,radius-x,radius-y,height
WOOD = [(-.7, .7, SAND), (.0, .70, 1.1), (.65, .72, 1.50), (1.30, .74, 1.85)]
MAILBOX = {'clock': 600, 'init': 601, 'slot': 602, 'x': 603, 'y': 604, 'z': 605,
           'yaw': 606, 'pitch': 607, 'phase': 608, 'activity': 609, 'scale': 610,
           'sy': 611, 'cy': 612, 'actor': 613, 'ox': 614, 'oy': 615, 'oz': 616,
           'dt': 617, 'head': 618, 'speed': 619, 'vx': 620, 'vy': 621, 'vz': 622,
           'prev': 623, 'dart': 624, 'dx': 625, 'dy': 626, 'dz': 627, 'mode': 628,
           'camera': 629, 'u': 630, 'travel': 631, 'state': 632, 'parity': 633,
           'target': 634, 'support': 635, 'escape': 636, 'elapsed': 637,
           'cooldown': 638, 'gait-phase': 639,
           'last-x':680,'last-y':681,'last-z':682,'pose-init':683,
           'player-pitch':684,'neutral':685,'drive':686,'flip':687,
           'cp':688,'sp':689,'local-x':690,'motion':691,'contact':692,'antenna-phase':693}
TABLE = 800
STRIDE = 18
# Per resident: five actor indices, home xyz, excursion xyz, period, phase,
# scale, yaw, last posed x/y, last update time (useful for validation).


def residents(n=23):
    """Disjoint authored lanes: independent phases without an all-pairs scan.

    Sand crawlers occupy 3 rows; raised residents perch on rocks or wood.
    Last two make short water-column excursions. No random runtime state.
    """
    rows = []
    for k in range(18):
        row, col = divmod(k, 6)
        rows.append(dict(home=(-4.5+col*1.75, -.87+row*.87, SAND),
                         excursion=(.25, 0, 0), period=12+(k*7 % 13),
                         phase=(k*.173)%1, size=.70+(k*3%5)*.05, yaw=0))
    # Shift lanes away from the boulder footprints (the routes stay on sand).
    for row in rows:
        x, y, z = row['home']
        if x == -4.5 and y >= 0:
            row['home'] = (-4.8, y, z)
            row['excursion'] = (.15, 0, 0)
        if x == -2.75 and y >= 0:
            row['home'] = (-3.75, y, z)
            row['excursion'] = (-.15, 0, 0)
            row['yaw'] = .5
        if x == 4.25 and y >= 0:
            row['home'] = (5.05, y, z)
            row['excursion'] = (-.1, 0, 0)
            row['yaw'] = .5
    rows += [dict(home=(-2.65, .3, SAND+.85), excursion=(.10, 0, 0), period=19, phase=.1, size=.76, yaw=0),
             dict(home=(3.95, .55, SAND+.62), excursion=(.15, 0, 0), period=21, phase=.4, size=.80, yaw=.5),
             dict(home=(.65, .72, 1.66), excursion=(.16, .005, .086), period=16, phase=.7, size=.72, yaw=0),
             dict(home=(-.8, -.25, 2.10), excursion=(.7, .12, .65), period=18, phase=.5, size=.85, yaw=0),
             dict(home=(2.4, .35, 2.80), excursion=(.7, -.10, .7), period=24, phase=.1, size=.82, yaw=.5)]
    if not 0 <= n <= len(rows):
        raise ValueError('SHRIMP_COUNT must be 1..24 (including the player)')
    return rows[:n]


def route_at(row, seconds):
    """Reference for geometric route validation; actual animation is zForth."""
    p = (seconds/row['period']+row['phase']) % 1
    if p < .35:
        u, moving = 0, False
    elif p < .65:
        u, moving = (p-.35)/.3, True
    elif p < .8:
        u, moving = 1, False
    else:
        u, moving = 1-(p-.8)/.2, True
    smooth = u*u*(3-2*u)
    x, y, z = [a+b*smooth for a, b in zip(row['home'], row['excursion'])]
    return (x, y, z), moving
