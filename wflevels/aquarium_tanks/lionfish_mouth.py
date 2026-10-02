"""Articulated suction-feeding head, isolated from the other tank models."""
import math
from mesh import Mesh
from models import fish


def half_head(name, side):
    mesh = Mesh(name)
    # Hinge is at (.20, 0, -.025); each half closes against the same dark palate.
    def point(i, j):
        angle, latitude = math.pi*i/8, math.pi*j/6
        return (.10+.28*math.cos(latitude),
                .20*math.sin(latitude)*math.cos(angle),
                side*.18*math.sin(latitude)*math.sin(angle))
    for j in range(6):
        for i in range(8):
            points = [point(i,j),point(i,j+1),point(i+1,j+1),point(i+1,j)]
            points = list(dict.fromkeys(tuple(round(v,9) for v in p) for p in points))
            if len(points) >= 3:
                mesh.face(points if side > 0 else list(reversed(points)),
                          'brown' if j == 3 else 'pale')
    outline=[point(0,j) for j in range(7)]+[point(8,j) for j in range(5,0,-1)]
    mesh.face(outline if side > 0 else list(reversed(outline)), 'eye')
    return mesh


def feeding_models():
    meshes, offsets = fish('lionfish')
    body = meshes[0]
    trimmed = Mesh('body')
    # Remove the original snout and the forward body rings. Keep eyes and spines.
    # The first 120 body faces are the main ellipsoid; the following 60 are snout.
    for i, (face, color) in enumerate(zip(body.faces, body.colors)):
        points = [body.vertices[k] for k in face]
        if 120 <= i < 180 or (i < 120 and max(p[0] for p in points) > .31):
            continue
        trimmed.face(points, color)
    meshes[0] = trimmed
    meshes.extend([half_head('upper_mouth',1),half_head('lower_mouth',-1)])
    offsets.extend([(.20,0,-.025),(.20,0,-.025)])
    return meshes, offsets
