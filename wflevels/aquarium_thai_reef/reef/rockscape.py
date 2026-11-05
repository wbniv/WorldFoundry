"""Seeded low-poly rock masses in tank coordinates.

Each blob is closed and has non-degenerate triangles at both poles. The output
is a visual blockout; Boolean union and decimation remain a Phase 1 task.
"""
import math
import random
from .scene import ROCK_MASSES, SEED, from_mockup


def rock_blob(mesh, center, radii, rng, color='rock', segments=32, rings=16):
    cx, cy, cz = center
    rx, ry, rz = radii
    north = (cx, cy, cz + rz)
    south = (cx, cy, cz - rz)
    # Broad eroded lobes plus smaller ledges break up the rounded blockout.
    phase = rng.uniform(0, math.tau)
    loops = []
    for j in range(1, rings):
        phi = math.pi * j / rings
        row = []
        for i in range(segments):
            theta = math.tau * i / segments
            wobble = (1 + .12 * math.sin(3 * theta + phase) * math.sin(phi)
                      + .075 * math.cos(5 * theta - 2 * phi + phase)
                      + .045 * math.sin(8 * theta + 3 * phi)
                      + .025 * math.sin(11 * theta - 5 * phi + phase))
            row.append((cx + rx * math.sin(phi) * math.cos(theta) * wobble,
                        cy + ry * math.sin(phi) * math.sin(theta) * wobble,
                        cz + rz * math.cos(phi) * wobble))
        loops.append(row)
    for i in range(segments):
        ni = (i + 1) % segments
        mesh.face([north, loops[0][i], loops[0][ni]], color)
        for j in range(len(loops) - 1):
            mesh.face([loops[j][i], loops[j+1][i], loops[j+1][ni], loops[j][ni]], color)
        mesh.face([loops[-1][i], south, loops[-1][ni]], color)


def populate(mesh, group):
    """Append one named mass; deterministic regardless of call order."""
    group_seeds = {'left': 11, 'right': 23, 'arch': 37}
    rng = random.Random(SEED + group_seeds[group])
    masses = ROCK_MASSES[group]
    # Build the reef's center as a true open arch. The blockout used a single
    # thin ellipsoid for its lintel, which read as a floating plate in profile.
    if group == 'arch':
        masses = masses[:2] + masses[3:]
    for x, y, rx, ry in masses:
        center = from_mockup(x, y, .5)
        rock_blob(mesh, center, (rx / 1600 * 11.2, .48 + rx / 500,
                                 ry / 900 * 4.95), rng)
    if group == 'arch':
        arch = [from_mockup(x, y, .15) for x, y in
                ((625, 665), (680, 520), (760, 430), (855, 430),
                 (945, 520), (1000, 660))]
        mesh.swept_tube(arch, .36, 'rock', 10)

