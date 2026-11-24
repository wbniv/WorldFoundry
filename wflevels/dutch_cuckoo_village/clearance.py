"""Check the authored Journey against the exported town before cooking the level."""
import math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from director import ROUTE, coefficients


def check(models):
    points,faces=[],[]
    for mesh,origin,_ in models.values():
        offset=len(points)
        points.extend(tuple(a+b for a,b in zip(p,origin)) for p in mesh.vertices)
        faces.extend(tuple(offset+i for i in face) for face in mesh.faces)
    world=BVHTree.FromPolygons(points,faces)
    nearest=float('inf')
    for leg in range(len(ROUTE)):
        co=coefficients(leg)
        for step in range(101):
            u=step/100
            pose=[((a*u+b)*u+c)*u+d for a,b,c,d in co]
            eye=Vector(pose[:3])
            forward=(Vector(pose[3:])-eye).normalized()
            right=forward.cross(Vector((0,0,1))).normalized()
            up=right.cross(forward)
            distance=world.find_nearest(eye)[3]
            nearest=min(nearest,distance)
            if distance < .60:
                raise ValueError(f'Journey leg {leg} at {u:.2f}: camera only {distance:.2f} m from the model')
            # The desktop's one-metre near plane at 60° vertical FOV, 16:9.
            # Sweep rays across its edges and centre to catch roof clipping.
            half=math.tan(math.radians(30))
            for x in (-1,0,1):
                for y in (-1,0,1):
                    ray=forward + right*(x*half*16/9) + up*(y*half)
                    if world.ray_cast(eye,ray.normalized(),ray.length+.10)[0] is not None:
                        raise ValueError(f'Journey leg {leg} at {u:.2f}: near plane intersects town')
    print(f'Journey clearance: {nearest:.2f} m minimum eye distance; 1,010 near-plane samples clear')
