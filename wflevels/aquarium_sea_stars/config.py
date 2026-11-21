"""Sea Stars export-time configuration. The level holds the maximum population (D10);
the director parks the residents beyond the SeaStarsSettings counts."""
SEED = 0
TITLE = 'Sea Stars'
STATIC_TRIANGLES_MAX = 20000
STATIC_GROUPS_MAX = 4
SAND_Z = .80
LIMIT_X, LIMIT_Y, TOP = 5.65, 2.65, 4.85
# 10 world units/metre. Measured cm/min -> world units/sec, then D5 speedup.
PLAYER_SPEED = 8.1 / 600 * 30
SPECIES = {
    'linckia': dict(scientific='Linckia laevigata', count=1, radius=.9, disc=.20, width=.14, height=.105, color=(28,106,208), speed=PLAYER_SPEED),
    'chip': dict(scientific='Protoreaster nodosus', count=2, radius=1.0, disc=.37, width=.24, height=.15, color=(201,164,112), speed=18.8/600*20),
    'fromia': dict(scientific='Fromia milleporella', count=3, radius=.40, disc=.17, width=.11, height=.055, color=(215,53,38), speed=.09),
    'sand': dict(scientific='Archaster typicus', count=2, radius=.56, disc=.17, width=.11, height=.045, color=(183,176,153), speed=45.8/600*20),
    'brittle': dict(scientific='Ophiarachna incrassata', count=1, radius=1.69, disc=.19, width=.047, height=.07, color=(91,133,68), speed=PLAYER_SPEED*6),
    'cushion': dict(scientific='Culcita novaeguineae', count=1, radius=.72, disc=.64, width=.35, height=.37, color=(211,134,66), speed=0),
}
# Rock clearance is resolved at export, no runtime scene scan or raycast.
ROCKS = ((-3.4, 1.15, 1.0, .70, 1.0), (0, 1.45, .75, .65, .65), (3.4, 1.1, 1.05, .70, 1.15))
# The first nine are the shipped default population, in the shipped order, names and spots;
# the rest are the extra spots a raised count unparks. Within a kind, residents are taken in
# list order, so the default counts (2, 3, 2, 1, 1) select exactly the shipped nine.
RESIDENTS = (
    ('ChipOne','chip',(-3.5,-.9,SAND_Z)), ('ChipTwo','chip',(3.1,-.9,SAND_Z)),
    ('FromiaOne','fromia',(-3.5,.6,1.8)), ('FromiaTwo','fromia',(0,1.0,1.35)), ('FromiaThree','fromia',(3.4,.5,1.8)),
    ('SandOne','sand',(-1.8,-1.55,SAND_Z)), ('SandTwo','sand',(1.8,-1.4,SAND_Z)),
    ('Brittle','brittle',(3.3,.25,SAND_Z)), ('Cushion','cushion',(-4.7,0,SAND_Z)),
    ('ChipThree','chip',(-1.0,-.4,SAND_Z)), ('ChipFour','chip',(1.2,-1.7,SAND_Z)),
    ('FromiaFour','fromia',(-3.0,.9,1.8)), ('FromiaFive','fromia',(3.8,.9,1.95)),
    ('SandThree','sand',(-.3,-1.7,SAND_Z)), ('SandFour','sand',(4.2,-1.6,SAND_Z)),
    ('BrittleTwo','brittle',(-2.6,.2,SAND_Z)), ('CushionTwo','cushion',(4.6,-.5,SAND_Z)),
)
KIND_ORDER = ('chip','fromia','sand','brittle','cushion')   # the order of the settings' five counts
MAX_COUNTS = dict(chip=4, fromia=5, sand=4, brittle=2, cushion=2)       # D10
DEFAULT_COUNTS = dict(chip=2, fromia=3, sand=2, brittle=1, cushion=1)   # D9
# Seed offsets, in world units, by kind: (x amplitude, y amplitude). Chips and sand stars stay on
# open sand in front of the rocks (rock fronts start at y = .4); Fromia only slide along a rock.
SEED_SPREAD = dict(chip=(1.0,.5), sand=(1.0,.4), fromia=(.3,0))
