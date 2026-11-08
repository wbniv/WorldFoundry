"""Procedural, irregular barrel sponge with an open cavity."""
import math


def populate(mesh, center=None):
    """The barrel sponge, standing on the right rock (reef.placement)."""
    if center is None:
        from .placement import actor_position
        center = actor_position('BarrelSponge')
    x, y, z = center
    n = 40
    for i in range(n):
        a,b=math.tau*i/n,math.tau*(i+1)/n
        # Multiple uneven rings let the wall bulge and fold organically.
        def r(t): return .43 + .035*math.sin(7*t) + .016*math.sin(13*t)
        def h(t): return z+.57 + .045*math.sin(5*t) + .025*math.sin(11*t+.4)
        def wall(t, level):
            f = level/4
            radius = .25 + (r(t)-.25)*f + .065*math.sin(math.pi*f)
            radius += .018*math.sin(9*t+3*f)*math.sin(math.pi*f)
            return (x+radius*math.cos(t), y+radius*math.sin(t),
                    z-.35 + (h(t)-(z-.35))*f)
        for level in range(4):
            mesh.face([wall(a,level), wall(b,level), wall(b,level+1), wall(a,level+1)], 'sponge')
        # Rim surrounds a genuinely open dark inner cavity.
        mesh.face([(x+r(a)*math.cos(a),y+r(a)*math.sin(a),h(a)),
                   (x+r(b)*math.cos(b),y+r(b)*math.sin(b),h(b)),
                   (x+.30*math.cos(b),y+.30*math.sin(b),z+.46),
                   (x+.30*math.cos(a),y+.30*math.sin(a),z+.46)], 'sponge_rim')
        mesh.face([(x+.30*math.cos(a),y+.30*math.sin(a),z+.46),
                   (x+.30*math.cos(b),y+.30*math.sin(b),z+.46),
                   (x+.18*math.cos(b),y+.18*math.sin(b),z-.08),
                   (x+.18*math.cos(a),y+.18*math.sin(a),z-.08)], 'sponge_inner')
