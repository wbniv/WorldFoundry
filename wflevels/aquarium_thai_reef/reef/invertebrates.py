"""Small mobile reef inhabitants in local coordinates."""


def guard_crab(mesh, center, limb_ranges=None):
    x, y, z = center
    mesh.ellipsoid((x,y,z), (.10,.075,.045), 'crab_shell', 14, 8)
    for side in (-1, 1):
        mesh.ellipsoid((x+.075,y+side*.042,z+.035), (.016,.014,.015), 'fish_dark', 8, 5)
        for i in range(4):
            px = x - .065 + i * .04
            start = len(mesh.vertices)
            mesh.swept_tube([(px,y+side*.05,z), (px-.025,y+side*.12,z+.01),
                             (px-.04,y+side*.15,z-.045)], .010, 'crab_leg', 5)
            if limb_ranges is not None:
                limb_ranges.append((start, len(mesh.vertices), (px, y+side*.05, z), side, 'leg'))
        start = len(mesh.vertices)
        mesh.swept_tube([(x+.07,y+side*.04,z), (x+.14,y+side*.09,z+.04)], .014, 'crab_leg', 5)
        mesh.ellipsoid((x+.15,y+side*.09,z+.04), (.035,.025,.025), 'crab_shell', 10, 6)
        for finger in (-1, 1):
            mesh.swept_tube([(x+.17,y+side*.09+finger*.012,z+.045),
                             (x+.20,y+side*.09+finger*.018,z+.055),
                             (x+.215,y+side*.09+finger*.009,z+.06)], .009, 'crab_finger', 5)
        if limb_ranges is not None:
            limb_ranges.append((start, len(mesh.vertices), (x+.07, y+side*.04, z), side, 'claw'))


def banded_shrimp(mesh, center, limb_ranges=None):
    x, y, z = center
    for i in range(5):
        mesh.ellipsoid((x-.06*i,y,z+.008*i), (.05,.045,.045),
                       'shrimp_red' if i % 2 else 'shrimp_white', 8, 5)
    mesh.ellipsoid((x+.05,y,z), (.075,.052,.052), 'shrimp_white', 10, 6)
    for side in (-1, 1):
        mesh.ellipsoid((x+.095,y+side*.038,z+.035), (.014,.012,.014), 'fish_dark', 8, 5)
        start = len(mesh.vertices)
        for i in range(4):
            px = x - .04*i
            mesh.swept_tube([(px,y+side*.035,z-.02), (px+.025,y+side*.11,z-.08)], .005, 'shrimp_white', 4)
        if limb_ranges is not None:
            limb_ranges.append((start, len(mesh.vertices), (x-.06, y+side*.035, z-.02), side, 'leg'))
        start = len(mesh.vertices)
        mesh.swept_tube([(x+.10,y+side*.025,z+.02), (x+.30,y+side*.14,z+.13)], .003, 'shrimp_white', 4)
        if limb_ranges is not None:
            limb_ranges.append((start, len(mesh.vertices), (x+.10, y+side*.025, z+.02), side, 'antenna'))
        start = len(mesh.vertices)
        mesh.swept_tube([(x+.07,y+side*.04,z), (x+.18,y+side*.12,z-.02)], .010, 'shrimp_red', 4)
        mesh.swept_tube([(x+.18,y+side*.12,z-.02), (x+.22,y+side*.14,z-.01)], .009, 'shrimp_white', 5)
        if limb_ranges is not None:
            limb_ranges.append((start, len(mesh.vertices), (x+.07, y+side*.04, z), side, 'claw'))
    for side in (-1, 1):
        mesh.face([(x-.27,y,z+.03), (x-.35,y+side*.07,z+.06),
                   (x-.32,y+side*.06,z-.025), (x-.26,y,z-.025)], 'shrimp_red')


def hermit_crab(mesh, center, limb_ranges=None):
    x, y, z = center
    mesh.ellipsoid((x-.08,y,z+.09), (.14,.11,.13), 'hermit_shell', 12, 7)
    # Overlapping whorls and a pale lip distinguish the shell from a pebble.
    mesh.ellipsoid((x-.16,y,z+.13), (.09,.085,.09), 'hermit_shell', 10, 6)
    mesh.ellipsoid((x-.21,y,z+.16), (.045,.05,.05), 'hermit_shell', 8, 5)
    mesh.swept_tube([(x+.015,y-.07,z+.035), (x+.025,y,z+.018),
                     (x+.015,y+.07,z+.035)], .012, 'hermit_lip', 6)
    mesh.ellipsoid((x+.05,y,z+.035), (.085,.075,.05), 'hermit_leg', 10, 6)
    for side in (-1,1):
        for i in range(3):
            px=x+i*.035
            start = len(mesh.vertices)
            mesh.swept_tube([(px,y+side*.045,z+.025), (px+.045,y+side*.12,z)], .008, 'hermit_leg', 4)
            if limb_ranges is not None:
                limb_ranges.append((start, len(mesh.vertices), (px, y+side*.045, z+.025), side, 'leg'))
