"""Paint a deterministic miniature-material atlas, with mortar, slates, glass and wood grain."""
import math
import random

COLORS = {
    'brick': (151,72,52), 'rose': (178,101,71), 'umber': (109,66,51),
    'stone': (207,189,151), 'cream': (242,221,178), 'white': (226,222,196),
    'slate': (71,76,86), 'tile': (170,88,55), 'oak': (128,86,49),
    'wood': (85,55,38), 'dark': (48,45,43), 'cobalt': (34,55,97),
    'glass': (73,104,112), 'glow': (255,189,80), 'green': (57,88,68),
    'grass': (103,127,70), 'leaf': (73,104,58), 'tree': (94,126,61),
    'pink': (228,155,164), 'red': (196,55,62), 'yellow': (246,188,61),
    'clay': (152,75,53), 'water': (56,94,101), 'ripple': (109,150,150),
    'mud': (104,85,58), 'pave': (148,123,104), 'gold': (210,161,67),
    'skin': (209,161,121), 'coat': (61,90,112), 'cheese': (228,167,58),
    'rain': (145,166,170), 'brass': (172,127,61), 'black': (43,40,39),
}
TILE = 32
SIZE = 256
KEYS = list(COLORS)


def pixels():
    rng = random.Random(1417)
    image = [0.0] * (SIZE * SIZE * 4)
    for index, (key, rgb) in enumerate(COLORS.items()):
        left, bottom = index % 8 * TILE, index // 8 * TILE
        for y in range(TILE):
            for x in range(TILE):
                shade = rng.uniform(.94, 1.04)
                if key in ('brick', 'rose', 'umber', 'pave', 'stone'):
                    row = y // 8
                    offset = (x + (row % 2)*10) % 20
                    shade *= 1.20 if y%8 == 0 or offset == 0 else 1.0
                    if y%8 == 1 or offset == 1:
                        shade *= .78
                elif key in ('tile', 'slate'):
                    shade *= .56 if y%8 == 0 else .9 + .14*math.cos((x + y//8*3)*.65)
                elif key in ('wood', 'oak', 'dark'):
                    shade *= .91 + .09*math.sin(y*.72 + .5*math.sin(x*.2))
                    if y%12 == 0:
                        shade *= .73
                elif key in ('glass','water'):
                    shade *= .96 + .10*math.sin(.2*x + .61*y + math.sin(x*.29))
                pos = ((bottom+y)*SIZE + left+x)*4
                image[pos:pos+4] = [min(1, component*shade/255) for component in rgb] + [1]
    return image


def uv_material(key, u, v):
    i = KEYS.index(key)
    return ((i%8 + .04 + .92*u)/8, (i//8 + .04 + .92*v)/8)
