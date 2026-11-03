"""Construct actual static blockout meshes for budget and exporter integration."""
from . import corals, life, rockscape, sponges


def _box(mesh, lo, hi, color):
    x,y,z=lo; X,Y,Z=hi
    v=((x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z))
    for face in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
        mesh.face([v[i] for i in face], color)


def build_groups(Mesh):
    """Build eight static mesh groups. This does not create physics bodies."""
    groups = {name: Mesh(name) for name in ('reef_left', 'reef_right', 'reef_arch',
              'reef_hard', 'reef_soft', 'reef_sponges', 'reef_life', 'reef_shell')}
    for group in ('left','right','arch'):
        rockscape.populate(groups['reef_' + group], group)
    corals.hard_corals(groups['reef_hard'])
    corals.soft_corals(groups['reef_soft'])
    sponges.populate(groups['reef_sponges'])
    life.populate(groups['reef_life'])
    shell=groups['reef_shell']
    # The mockup's sand line is near y=800; from_mockup maps that to z≈.73.
    _box(shell, (-6,-3,0), (6,3,.72), 'sand')
    _box(shell, (-6.1,-3.1,-.22), (6.1,3.1,0), 'frame')
    # Slim rim segments are opaque. Glass and collision shapes must be authored
    # separately by the Blender scene; these meshes are only the visible blockout.
    for lo,hi in (((-6.1,-3.1,5.4),(6.1,-3,5.5)),
                  ((-6.1,3,5.4),(6.1,3.1,5.5)),
                  ((-6.1,-3.1,5.4),(-6,3.1,5.5)),
                  ((6,-3.1,5.4),(6.1,3.1,5.5))):
        _box(shell,lo,hi,'frame')
    return groups


def triangles(mesh):
    return sum(max(0,len(face)-2) for face in mesh.faces)

