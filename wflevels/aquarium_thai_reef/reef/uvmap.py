"""Per-face atlas UVs for reef meshes, in pure Python (no bpy).

generate.py assigns these to Blender loops; the texel audit and the review
renders use the same function, so what is measured is what is exported.
UV convention: u = x / 1024, v = y / 1024 with y measured from the atlas top
(see atlas.py); the exporter handles the flip.

Key families, in order of precedence:
  explicit       mesh.face_uvs[face] authored with the geometry (worm crowns,
                 zoanthid discs)
  flat swatches  fish_dark, fish_white, fish_grey, water_N: one texel in utility cell 15
  clam_shell     the striped shell strip in cell 15
  flowerpot      tile 5, per-face dominant-normal projection over mesh bounds
  SKINS          creature skins in cells 9-15: projected (mirrored repeat)
                 within a sub-rect at a per-key frequency, or a base-to-top
                 gradient ('height')
  SWATCH         static surface tiles 0-7, world projected (0.37 cycles/unit;
                 1.1 for the polyp tile)
"""
from .atlas import CELL, CLAM_SHELL, FISH_DARK, FISH_GREY, FISH_WHITE, WATER_X0

SWATCH = {'rock': 4, 'porites': 1, 'pocillopora': 1, 'pocillopora_tip': 1,
          'acropora': 1, 'scroll': 0, 'flowerpot': 5, 'flowerpot_tip': 5,
          'leather': 1, 'fan': 0, 'sponge': 2, 'sponge_rim': 2,
          'sponge_inner': 2, 'sand': 3, 'frame': 4, 'coralline': 0,
          'polyp': 1, 'zoanthid': 5, 'clam': 6, 'fish': 7}

# key: (cell, (x, y, w, h) inside the cell in px, cycles per world unit, mode)
SKINS = {
    'duster_light': (9, (0, 0, 256, 96), 5.0, 'project'),
    'duster_dark': (9, (0, 96, 256, 96), 5.0, 'project'),
    'duster_tube': (9, (0, 192, 256, 64), 4.0, 'project'),
    'crab_shell': (10, (0, 0, 256, 128), 4.0, 'project'),
    'crab_leg': (10, (0, 128, 256, 80), 6.0, 'project'),
    'crab_finger': (10, (0, 208, 256, 48), 6.0, 'project'),
    'shrimp_red': (11, (0, 0, 256, 128), 5.0, 'project'),
    'shrimp_white': (11, (0, 128, 256, 128), 5.0, 'project'),
    'nudi_body': (12, (0, 0, 256, 192), 3.0, 'project'),
    'nudi_ridge': (12, (0, 192, 256, 32), 5.0, 'project'),
    'nudi_tubercle': (12, (0, 224, 256, 32), 8.0, 'project'),   # mottled yellow-orange caps
    'hermit_shell': (13, (0, 0, 256, 128), 3.0, 'project'),
    'hermit_leg': (13, (0, 128, 256, 64), 6.0, 'project'),
    'hermit_lip': (13, (0, 192, 256, 64), 4.0, 'project'),
    'crust_sponge': (14, (0, 0, 256, 128), 2.5, 'project'),
    'crust_coralline': (14, (0, 128, 256, 128), 2.5, 'project'),
    # Zoanthid columns and tentacles: the mottled coralline tile, densely.
    'zoanthid_column': (0, (0, 0, 256, 256), 6.0, 'project'),
    'humbug_white': (15, (0, 96, 256, 32), 0.0, 'height'),
    # Dascyllus reticulatus body (D10): grey scales with dark margins in a 64-px
    # square; 4 cycles/unit puts about 7 px (0.03 units) per scale, some 20
    # scales along the 0.62-unit body.
    'humbug_scales': (15, (0, 192, 64, 64), 4.0, 'project'),
    'fan_grad': (15, (0, 128, 256, 32), 0.0, 'height'),
    'star_grad': (15, (0, 160, 256, 32), 0.0, 'height'),
}


def _mirror(t):
    """Triangle wave in [0, 1] with period 2: 0, 1, 0, 1 ..."""
    f = t % 2.0
    return f if f <= 1.0 else 2.0 - f


def _normal(points):
    """Newell normal of a polygon (unnormalised)."""
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(points):
        b = points[(i + 1) % len(points)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def _bounds(mesh, keys):
    pts = [mesh.vertices[i] for face, key in zip(mesh.faces, mesh.colors) if key in keys for i in face]
    return [(min(p[a] for p in pts), max(p[a] for p in pts)) for a in range(3)] if pts else None


def face_uvs(mesh):
    """List of per-face UV lists, in face vertex order."""
    explicit = getattr(mesh, 'face_uvs', {})
    flowerpot_bounds = None
    if any(key in ('flowerpot', 'flowerpot_tip') for key in mesh.colors):
        flowerpot_bounds = [(min(v[a] for v in mesh.vertices), max(v[a] for v in mesh.vertices))
                            for a in range(3)]
    height_keys = {k for k, s in SKINS.items() if s[3] == 'height'}
    height_bounds = {k: _bounds(mesh, {k}) for k in height_keys if k in mesh.colors}
    out = []
    for index, (face, key) in enumerate(zip(mesh.faces, mesh.colors)):
        pts = [mesh.vertices[i] for i in face]
        if index in explicit:
            out.append(list(explicit[index]))
        elif key in ('fish_dark', 'fish_white', 'fish_grey') or key.startswith('water_'):
            x, y = (FISH_DARK if key == 'fish_dark' else FISH_WHITE if key == 'fish_white'
                    else FISH_GREY if key == 'fish_grey'
                    else (WATER_X0 + 8 + 16 * int(key.removeprefix('water_')), FISH_DARK[1]))
            out.append([(x / 1024, y / 1024)] * len(pts))
        elif key == 'clam_shell':
            cx, cy, cw, ch = CLAM_SHELL
            row = []
            for p in pts:
                along = max(0.0, min(1.0, (p[0] + .45) / .90))
                across = max(0.0, min(1.0, abs(p[1]) / .32))
                row.append(((cx + 4 + (cw - 8) * along) / 1024, (cy + 4 + (ch - 8) * across) / 1024))
            out.append(row)
        elif key in ('flowerpot', 'flowerpot_tip'):
            tile = SWATCH[key]
            n = _normal(pts)
            normal_axis = max(range(3), key=lambda a: abs(n[a]))
            axes = ((1, 2), (0, 2), (0, 1))[normal_axis]
            row = []
            for p in pts:
                values = []
                for a in axes:
                    lo, hi = flowerpot_bounds[a]
                    values.append((p[a] - lo) / (hi - lo) if hi > lo else .5)
                row.append(((tile % 4 + .04 + .92 * values[0]) / 4,
                            (tile // 4 + .04 + .92 * values[1]) / 4))
            out.append(row)
        elif key in SKINS:
            cell, (sx, sy, sw, sh), freq, mode = SKINS[key]
            x0, y0 = (cell % 4) * CELL + sx, (cell // 4) * CELL + sy
            row = []
            if mode == 'height':
                (zlo, zhi) = height_bounds[key][2]
                for p in pts:
                    t = (p[2] - zlo) / (zhi - zlo) if zhi > zlo else .5
                    # v runs from the strip's bottom (base) to its top (tip).
                    row.append(((x0 + sw / 2) / 1024, (y0 + sh - 3 - (sh - 6) * t) / 1024))
            else:
                # Mirrored repeat: continuous across period boundaries, so a
                # face never spans a wrap and smears the whole strip.
                for x, y, z in pts:
                    u = x0 + 3 + (sw - 6) * _mirror(x * freq + y * freq * .3)
                    v = y0 + 3 + (sh - 6) * _mirror(z * freq + y * freq * .3)
                    row.append((u / 1024, v / 1024))
            out.append(row)
        else:
            tile = SWATCH[key]
            frequency = 1.1 if tile == 1 else .37
            row = []
            for x, y, z in pts:
                u = (tile % 4 + .04 + .92 * ((x * frequency + y * .11) % 1)) / 4
                v = (tile // 4 + .04 + .92 * ((z * frequency + y * .11) % 1)) / 4
                row.append((u, v))
            out.append(row)
    return out
