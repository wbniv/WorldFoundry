"""Procedural barrel sponge blockout."""
import math


def populate(mesh):
    x,y,z = 4.75, -.72, 2.0
    n = 40
    for i in range(n):
        a,b=math.tau*i/n,math.tau*(i+1)/n
        # Ribbing and an irregular lip keep the cup from looking machined.
        def r(t): return .43 + .035*math.sin(7*t) + .016*math.sin(13*t)
        def h(t): return z+.57 + .045*math.sin(5*t)
        mesh.face([(x+.25*math.cos(a),y+.25*math.sin(a),z-.35),
                   (x+.25*math.cos(b),y+.25*math.sin(b),z-.35),
                   (x+r(b)*math.cos(b),y+r(b)*math.sin(b),h(b)),
                   (x+r(a)*math.cos(a),y+r(a)*math.sin(a),h(a))], 'sponge')
        # Rim surrounds a genuinely open dark inner cavity.
        mesh.face([(x+r(a)*math.cos(a),y+r(a)*math.sin(a),h(a)),
                   (x+r(b)*math.cos(b),y+r(b)*math.sin(b),h(b)),
                   (x+.30*math.cos(b),y+.30*math.sin(b),z+.46),
                   (x+.30*math.cos(a),y+.30*math.sin(a),z+.46)], 'sponge_rim')
        mesh.face([(x+.30*math.cos(a),y+.30*math.sin(a),z+.46),
                   (x+.30*math.cos(b),y+.30*math.sin(b),z+.46),
                   (x+.18*math.cos(b),y+.18*math.sin(b),z-.08),
                   (x+.18*math.cos(a),y+.18*math.sin(a),z-.08)], 'sponge_inner')
