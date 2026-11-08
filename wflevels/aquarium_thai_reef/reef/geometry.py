"""Construct actual static blockout meshes for budget and exporter integration."""
import math
import random
from . import corals, life, rockscape, sponges


def _box(mesh, lo, hi, color):
    x,y,z=lo; X,Y,Z=hi
    v=((x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z))
    for face in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
        mesh.face([v[i] for i in face], color)


def build_groups(Mesh):
    """Build static mesh groups. This does not create physics bodies."""
    groups = {name: Mesh(name) for name in ('reef_left', 'reef_right', 'reef_arch',
              'reef_hard', 'reef_soft', 'reef_sponges', 'reef_life', 'reef_shell')}
    for group in ('left','right','arch'):
        rockscape.populate(groups['reef_' + group], group)
    corals.hard_corals(groups['reef_hard'])
    # Worm collars and opercula belong to the boulder: static, baked, outlined.
    life.worm_collars(groups['reef_hard'])
    corals.soft_corals(groups['reef_soft'])
    sponges.populate(groups['reef_sponges'])
    life.populate(groups['reef_life'])
    # FACE indices are signed 16-bit; baked corner colors can split vertices.
    # Partition the detailed life mesh on face boundaries before export.
    original = groups['reef_life']
    explicit = getattr(original, 'face_uvs', {})
    pieces = [Mesh('reef_life')]
    for index, (face, color) in enumerate(zip(original.faces, original.colors)):
        if len(pieces[-1].vertices) + len(face) > 18000:
            pieces.append(Mesh('reef_life_' + str(len(pieces))))
        pieces[-1].face([original.vertices[i] for i in face], color)
        if index in explicit:          # carry authored UVs (zoanthid discs)
            if not hasattr(pieces[-1], 'face_uvs'):
                pieces[-1].face_uvs = {}
            pieces[-1].face_uvs[len(pieces[-1].faces) - 1] = explicit[index]
    groups['reef_life'] = pieces[0]
    for piece in pieces[1:]:
        groups[piece.name] = piece
    shell=groups['reef_shell']
    # Extend the distant water beyond the physical tank frame so the camera's
    # wide view never exposes the black matte around the reef.  This backdrop
    # is visual only; the authored tank and collision boundaries stay put.
    for i in range(6):
        low = -1 + i * (12 / 6)
        high = -1 + (i + 1) * (12 / 6)
        shell.face([(-16,3.2,low), (16,3.2,low), (16,3.2,high), (-16,3.2,high)], f'water_{i}')
    # Faint opaque shafts sit immediately in front of the far water.  Their
    # placement leaves the animals and the cave unobscured.
    for x in (-6.0, -1.5, 3.0, 7.5):
        for low, high, band in ((4, 5, 3), (5, 7, 4), (7, 9, 5)):
            def edge(z):
                t = (11 - z) / 7
                return x + 1.85*t, .45 - .20*t
            a, wa = edge(low)
            b, wb = edge(high)
            shell.face([(a-wa,3.16,low), (a+wa,3.16,low),
                        (b+wb,3.16,high), (b-wb,3.16,high)], f'water_{band}')
    # Muted far-rock silhouettes give the central arch depth without adding
    # colliders or extra draw groups.
    for x, z, rx, rz in ((-5.3, .85, 1.35, .8), (-2.5, .75, 1.1, .65),
                         (2.6, .75, 1.15, .7), (5.1, .8, 1.25, .75)):
        shell.ellipsoid((x, 2.9, z), (rx, .18, rz), 'water_1', 10, 5)
    # The mockup's sand line is near y=800; from_mockup maps that to z≈.73.
    _box(shell, (-6,-3,0), (6,3,.72), 'sand')
    # Low, broad ripples and small fragments break up the bare foreground.
    def sand_height(x, y):
        return .735 + .025 * math.sin(x * 4.0 + .7 * math.sin(y * 2.0))
    for i in range(24):
        x0, x1 = -6 + i * .5, -6 + (i + 1) * .5
        for j in range(12):
            y0, y1 = -3 + j * .5, -3 + (j + 1) * .5
            shell.face([(x0,y0,sand_height(x0,y0)), (x1,y0,sand_height(x1,y0)),
                        (x1,y1,sand_height(x1,y1)), (x0,y1,sand_height(x0,y1))], 'sand')
    rng = random.Random(20261102 + 82)
    for i in range(28):
        x, y = rng.uniform(-5.5,5.5), rng.uniform(-2.7,-1.5)
        size = rng.uniform(.035,.11)
        shell.ellipsoid((x,y,sand_height(x,y)), (size,size*.7,size*.45),
                        'coralline' if i % 5 == 0 else 'rock', 6, 4)
    _box(shell, (-6.1,-3.1,-.22), (6.1,3.1,0), 'frame')
    return groups


def triangles(mesh):
    return sum(max(0,len(face)-2) for face in mesh.faces)

