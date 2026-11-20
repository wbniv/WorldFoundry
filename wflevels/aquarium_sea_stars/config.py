"""Sea Stars export-time configuration; D11 live settings are deferred."""
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
RESIDENTS = (
    ('ChipOne','chip',(-3.5,-.9,SAND_Z)), ('ChipTwo','chip',(3.1,-.9,SAND_Z)),
    ('FromiaOne','fromia',(-3.5,.6,1.8)), ('FromiaTwo','fromia',(0,1.0,1.35)), ('FromiaThree','fromia',(3.4,.5,1.8)),
    ('SandOne','sand',(-1.8,-1.55,SAND_Z)), ('SandTwo','sand',(1.8,-1.4,SAND_Z)),
    ('Brittle','brittle',(3.3,.25,SAND_Z)), ('Cushion','cushion',(-4.7,0,SAND_Z)),
)
