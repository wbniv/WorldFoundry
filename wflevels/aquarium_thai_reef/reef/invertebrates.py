"""Small mobile reef inhabitants in local coordinates."""


def guard_crab(mesh, center):
    x, y, z = center
    mesh.ellipsoid((x,y,z), (.10,.075,.045), 'sponge', 10, 6)
    for side in (-1, 1):
        for i in range(4):
            px = x - .065 + i * .04
            mesh.swept_tube([(px,y+side*.05,z), (px-.025,y+side*.12,z+.01),
                             (px-.04,y+side*.15,z-.045)], .008, 'sponge', 4)
        mesh.swept_tube([(x+.07,y+side*.04,z), (x+.14,y+side*.09,z+.04)], .014, 'sponge', 5)
        mesh.ellipsoid((x+.15,y+side*.09,z+.04), (.035,.025,.025), 'sponge', 8, 5)


def banded_shrimp(mesh, center):
    x, y, z = center
    for i in range(5):
        mesh.ellipsoid((x-.06*i,y,z+.008*i), (.05,.045,.045),
                       'sponge' if i % 2 else 'sand', 8, 5)
    mesh.ellipsoid((x+.05,y,z), (.075,.052,.052), 'sand', 10, 6)
    for side in (-1, 1):
        for i in range(4):
            px = x - .04*i
            mesh.swept_tube([(px,y+side*.035,z-.02), (px+.025,y+side*.11,z-.08)], .005, 'sand', 4)
        mesh.swept_tube([(x+.10,y+side*.025,z+.02), (x+.30,y+side*.14,z+.13)], .003, 'sand', 4)
        mesh.swept_tube([(x+.07,y+side*.04,z), (x+.18,y+side*.12,z-.02)], .01, 'sponge', 4)


def hermit_crab(mesh, center):
    x, y, z = center
    mesh.ellipsoid((x-.08,y,z+.09), (.14,.11,.13), 'rock', 12, 7)
    mesh.ellipsoid((x+.05,y,z+.035), (.085,.075,.05), 'sponge', 10, 6)
    for side in (-1,1):
        for i in range(3):
            px=x+i*.035
            mesh.swept_tube([(px,y+side*.045,z+.025), (px+.045,y+side*.12,z)], .008, 'sponge', 4)
