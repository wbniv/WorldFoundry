"""Single source of scene placements for both future reef styles.

The x/z proportions follow the plan's 1600 x 900 wide-view mockup. Depth is
authored separately: the camera is in front of the negative-y tank face.
These are design anchors, not physics or identification evidence.
"""
from dataclasses import dataclass

SEED = 20261102
TANK = (12.0, 6.0, 5.5)


def from_mockup(x, y, depth=0.0):
    """Map mockup points to the inner tank, in world units."""
    return (round((x / 1600.0 - .5) * 11.2, 5), round(depth, 5),
            round(.18 + (900.0 - y) / 900.0 * 4.95, 5))


@dataclass(frozen=True)
class Anchor:
    name: str
    taxon: str
    x: int
    y: int
    depth: float = 0.0

    @property
    def position(self):
        return from_mockup(self.x, self.y, self.depth)


# Dropped unverified blue sea star and ascidian, and sea cucumber at Will's
# request. The unnamed gorgonian and genus-level corals await Phase 0's final
# species/model decisions; do not treat these labels as species identifications.
ANCHORS = (
    Anchor('coralline', 'Corallinales', 230, 610, .5),
    Anchor('flowerpot', 'Goniopora sp.', 175, 500, .4),
    Anchor('cauliflower', 'Pocillopora damicornis', 250, 360, .35),
    Anchor('guard_crab', 'Trapezia cymodoce', 352, 420, .2),
    Anchor('humbug_pair', 'Dascyllus aruanus', 335, 250, -.15),
    Anchor('scroll_coral', 'Turbinaria sp.', 470, 455, .5),
    Anchor('feather_duster', 'Sabellastarte sp.', 520, 560, .15),
    Anchor('zoanthids', 'Zoanthus sp.', 330, 610, .1),
    Anchor('nudibranch', 'Phyllidia varicosa', 260, 690, -.25),
    Anchor('mushroom_coral', 'Fungiidae', 520, 835, -.8),
    Anchor('sea_fan_left', 'gorgonian', 100, 400, 1.0),
    Anchor('leather_coral', 'Sarcophyton sp.', 760, 380, .7),
    Anchor('cup_coral', 'Tubastraea coccinea', 790, 540, .65),
    Anchor('cleaner_station', 'Stenopus hispidus', 700, 590, -.15),
    Anchor('boulder_coral', 'Porites lutea', 680, 760, .0),
    Anchor('tree_worms', 'Spirobranchus sp.', 775, 715, -.15),
    Anchor('feather_star', 'Lamprometra palmata', 930, 380, .3),
    Anchor('boxfish_spawn', 'Ostracion cubicus', 900, 290, -.5),
    Anchor('table_coral', 'Acropora sp.', 1290, 360, .45),
    Anchor('giant_clam', 'Tridacna squamosa', 1060, 805, -.9),
    Anchor('hermit_crab', 'Dardanus lagopodes', 985, 852, -1.0),
    Anchor('barrel_sponge', 'Xestospongia testudinaria', 1480, 650, .5),
)

ROCK_MASSES = {
    'left': ((300,650,230,170),(210,560,130,120),(390,545,140,110),
             (300,470,120,90),(470,660,120,110)),
    'right': ((1250,630,230,170),(1340,520,140,130),(1170,560,130,110),
              (1260,445,110,90),(1430,670,120,120)),
    'arch': ((640,670,90,115),(985,660,95,120),(810,478,250,52),
             (700,452,70,40),(925,448,85,45)),
}


def anchor_map():
    return {a.name: a.position for a in ANCHORS}
