"""Detailed glockenspiel artwork assembled in tower-local coordinates.

All geometry is original, uses the village atlas, and is grouped by material
into a small number of static engine actors. The shell and moving dial hands
come from the reusable tower asset. No figure animation is implied here.
"""
import math


def build(mesh_actor, tower_z):
    groups = {}
    component = 'tower_case'
    pivots = {}
    def add(tile, verts, faces):
        vs, fs, tiles = groups.setdefault(component, ([], [], []))
        offset = len(vs)
        vs.extend((x, y, z + tower_z) for x, y, z in verts)
        fs.extend(tuple(offset + i for i in f) for f in faces)
        tiles.extend([tile] * len(faces))

    def box(tile, x, y, z, sx, sy, sz):
        add(tile, [(x+dx*sx/2,y+dy*sy/2,z+dz*sz/2) for dx,dy,dz in
                   [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]],
            [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])

    def beam(tile, a, b, width, depth):
        # Extruded segment in the front elevation.
        x1,y1,z1=a; x2,y2,z2=b
        dx,dz=x2-x1,z2-z1
        length=math.hypot(dx,dz)
        nx,nz=-dz/length*width/2,dx/length*width/2
        verts=[(x1+nx,y1-depth/2,z1+nz),(x1-nx,y1-depth/2,z1-nz),
               (x2-nx,y2-depth/2,z2-nz),(x2+nx,y2-depth/2,z2+nz),
               (x1+nx,y1+depth/2,z1+nz),(x1-nx,y1+depth/2,z1-nz),
               (x2-nx,y2+depth/2,z2-nz),(x2+nx,y2+depth/2,z2+nz)]
        add(tile,verts,[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)])

    def ring(tile, x, y, z, outer, inner, n=40):
        vertices=[]
        for r in (outer,inner):
            for i in range(n):
                a=2*math.pi*i/n
                vertices.append((x+r*math.sin(a),y,z+r*math.cos(a)))
        add(tile,vertices,[(n+i,n+(i+1)%n,(i+1)%n,i) for i in range(n)])

    def sphere(tile, x, y, z, rx, ry, rz, n=12, m=8):
        v=[]
        for j in range(m+1):
            t=math.pi*j/m
            for i in range(n):
                a=2*math.pi*i/n
                v.append((x+rx*math.sin(t)*math.cos(a), y+ry*math.sin(t)*math.sin(a), z+rz*math.cos(t)))
        add(tile,v,[((j+1)*n+i,(j+1)*n+(i+1)%n,j*n+(i+1)%n,j*n+i) for j in range(m) for i in range(n)])

    def cone(tile, x, y, z, r1, r2, h, n=12):
        v=[]
        for zz,r in [(z,r1),(z+h,r2)]:
            for i in range(n):
                a=2*math.pi*i/n
                v.append((x+r*math.cos(a),y+r*math.sin(a),zz))
        add(tile,v,[(i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n)]+[tuple(range(n-1,-1,-1)),tuple(n+i for i in range(n))])

    # Layered cornices, framed clock case and balcony construction.
    for z,w,d,h in [(2.34,2.94,2.85,.15),(2.44,2.88,2.75,.10),
                    (3.28,2.82,2.56,.15),(3.40,2.70,2.42,.11),
                    (3.54,2.55,2.20,.12),(4.74,2.64,2.28,.15),
                    (4.88,2.78,2.40,.12),(5.03,2.95,2.55,.16)]:
        box(0,0,-.12,z,w,d,h)
    for x in (-1.18,1.18):
        box(0,x,-1.14,4.13,.16,.22,1.25)
        box(12,x,-1.27,4.13,.035,.035,1.10)
        for z in (3.66,4.58):
            sphere(12,x,-1.30,z,.08,.04,.08)
    for x in (-1.22,1.22):
        box(0,x,-1.69,2.89,.15,.18,.90)
        box(12,x,-1.80,2.89,.035,.04,.76)
        cone(12,x,-1.68,3.30,.12,.025,.16)
    box(0,0,-1.87,2.47,2.62,.15,.12)
    box(0,0,-1.87,2.76,2.62,.14,.10)
    for x in [i*.23 for i in range(-5,6)]:
        cone(0,x,-1.87,2.48,.055,.035,.27,8)
    # Gold and dark rings turn the pale stock face into a clock-case dial.
    # Hands from the source remain separate actors in front of these surfaces.
    ring(11,0,-1.071,4.08,.445,0.0)
    ring(12,0,-1.078,4.08,.50,.435)
    ring(0,0,-1.079,4.08,.55,.50)
    ring(12,0,-1.082,4.08,.424,.411)
    # Roman hour marks are built as strokes, so they stay crisp at close range. They are their own actor so that the level can
    # hide them: Bavaria mode shows a reversed dial instead (wflevels/cuckoo_village/bavaria.py).
    component = 'dial_numerals_classic'
    numerals=('XII','I','II','III','IV','V','VI','VII','VIII','IX','X','XI')
    for i, numeral in enumerate(numerals):
        a=math.tau*i/12; r=.35
        cx,cz=r*math.sin(a),4.08+r*math.cos(a)
        step=.026; total=(len(numeral)-1)*step
        for j,ch in enumerate(numeral):
            x=cx-total/2+j*step; y=-1.088; h=.052; w=.019
            if ch=='I':
                beam(12,(x,y,cz-h/2),(x,y,cz+h/2),.007,.009)
            elif ch=='V':
                beam(12,(x-w/2,y,cz+h/2),(x,y,cz-h/2),.007,.009)
                beam(12,(x,y,cz-h/2),(x+w/2,y,cz+h/2),.007,.009)
            else:
                beam(12,(x-w/2,y,cz-h/2),(x+w/2,y,cz+h/2),.007,.009)
                beam(12,(x-w/2,y,cz+h/2),(x+w/2,y,cz-h/2),.007,.009)
    component = 'tower_case'
    # Floral clock-case carving and sweeping brackets.
    for side in (-1,1):
        for i in range(7):
            z=3.64+i*.145
            x=side*(.82+.10*math.sin(i*1.2))
            # Curved, pointed carved leaves instead of round bead stand-ins.
            tip=(x+side*.14,-1.30,z+.09)
            beam(12,(x-side*.035,-1.30,z-.035),tip,.032,.035)
            beam(0,(x,-1.30,z),(x+side*.075,-1.30,z+.075),.08,.035)
            beam(12,(x,-1.325,z),(x+side*.065,-1.325,z+.055),.018,.015)
        beam(0,(side*.55,-1.26,3.56),(side*1.23,-1.26,3.84),.11,.11)
        for z in (3.64,4.63):
            sphere(12,side*.95,-1.30,z,.11,.04,.11)
    # Four individual mechanical performers: shoes, legs, skirts or jackets,
    # arms, faces, hair and hats. Their clear silhouettes are designed for the
    # balcony view; these are baked static geometry pending a proper figure rig.
    outfits=[(13,0),(14,8),(9,0),(12,8)]
    for i,x in enumerate((-.87,-.29,.29,.87)):
        component = 'tower_figure_%d' % (i+1)
        pivots[component] = (x, -1.61, 2.50 + tower_z)
        cloth,accent=outfits[i]; y=-1.61
        for dx in (-.065,.065):
            box(8,x+dx,y-.025,2.51,.10,.18,.10)
            box(accent,x+dx,y,2.64,.075,.10,.24)
        if i in (0,2):
            cone(cloth,x,y,2.69,.18,.095,.30)
        else:
            box(cloth,x,y,2.83,.25,.16,.31)
        for side in (-1,1):
            box(cloth,x+side*.165,y,2.83,.08,.10,.27)
            sphere(7,x+side*.165,y-.01,2.67,.045,.045,.05)
        sphere(7,x,y,3.10,.115,.085,.13)
        sphere(8,x,y+.025,3.16,.12,.08,.09)
        if i==1:
            cone(8,x,y,3.19,.14,.095,.08)
            cone(8,x,y,3.26,.095,.05,.11)
        elif i==3:
            cone(8,x,y,3.20,.16,.12,.045)
            cone(8,x,y,3.24,.105,.085,.10)
        else:
            sphere(accent,x,y,3.20,.13,.09,.055)
        # tiny contrasting buttons / apron
        for z in (2.75,2.83,2.91):
            sphere(12,x,y-.09,z,.014,.01,.014,8,6)
    component = 'tower_case'
    # Deep, framed cuckoo alcove above the dial, with a bird projecting forward.
    box(11,0,-1.19,4.70,.61,.10,.40)
    for x in (-.34,.34): box(0,x,-1.27,4.70,.09,.13,.46)
    box(0,0,-1.27,4.48,.73,.13,.09)
    beam(0,(-.39,-1.27,4.89),(0,-1.27,5.09),.09,.13)
    beam(0,(0,-1.27,5.09),(.39,-1.27,4.89),.09,.13)
    component = 'tower_bird'
    pivots[component] = (0, -1.27, 4.60 + tower_z)
    sphere(12,0,-1.34,4.67,.13,.10,.105)
    sphere(12,.10,-1.36,4.76,.075,.07,.075)
    sphere(11,.12,-1.42,4.78,.012,.01,.012,8,6)
    beam(8,(.15,-1.40,4.76),(.24,-1.40,4.74),.04,.04)
    component = 'tower_case'
    # Broad four-sided tiled roof with individually raised shingle courses.
    w,d,z0,z1=1.58,1.28,5.13,6.52
    add(2,[(-w,-d,z0),(w,-d,z0),(w,d,z0),(-w,d,z0),(0,0,z1)],
        [(0,1,4),(1,2,4),(2,3,4),(3,0,4),(3,2,1,0)])
    # Slightly projecting wooden fascia around the eaves.
    for y in (-d,d): box(0,0,y,5.13,3.30,.10,.14)
    for x in (-w,w): box(0,x,0,5.13,.10,2.60,.14)
    # Front shingle seams: thin, raised pieces arranged across each sloping course.
    for row in range(7):
        t=(row+.45)/8; zz=z0+(z1-z0)*t+.018
        yy=-d*(1-t)-.018; span=w*(1-t)
        beam(0,(-span,yy,zz),(span,yy,zz),.025,.025)
        count=max(2,8-row)
        for j in range(1,count):
            x=-span+2*span*j/count
            t2=min(t+.105,.96)
            beam(0,(x,yy-.008,zz),(x*(1-t2)/(1-t),-d*(1-t2)-.026,z0+(z1-z0)*t2+.018),.016,.02)
    cone(12,0,0,6.52,.16,.06,.18)
    cone(0,0,0,6.70,.045,.025,.36)
    sphere(12,0,0,7.08,.10,.10,.10)
    cone(12,0,0,7.17,.045,0,.16)
    # Lower glockenspiel mechanism from the day-and-dusk reference: a tall
    # open timber bay, nine suspended chime pipes, and large visible gears.
    # The dark inset stands in front of the old shell's domestic doorway.
    box(11,0,-1.205,1.36,2.43,.14,1.96)
    box(0,0,-1.30,2.28,2.76,.28,.19)
    box(0,0,-1.30,.50,2.68,.26,.15)
    for x in (-1.22,1.22):
        box(0,x,-1.30,1.40,.22,.28,1.83)
        box(12,x,-1.46,1.40,.035,.035,1.62)
        box(3,x,-1.28,.32,.48,.48,.42)
    box(3,0,-1.20,.17,2.95,.55,.34)
    # Stone joints on the foundation are modeled so they remain readable.
    for x in (-1.08,-.54,0,.54,1.08):
        box(7,x,-1.49,.17,.025,.035,.29)
    # Rear gear wheels and radial spokes in the open case.
    def gear(x,z,outer,inner,n=28):
        ring(12,x,-1.315,z,outer,inner,n)
        for j in range(n):
            a=math.tau*j/n
            xx=x+outer*math.sin(a); zz=z+outer*math.cos(a)
            sphere(12,xx,-1.33,zz,.035,.028,.035,8,4)
        for j in range(8):
            a=math.tau*j/8
            beam(12,(x,-1.34,z),(x+(inner-.025)*math.sin(a),-1.34,z+(inner-.025)*math.cos(a)),.065,.04)
        ring(0,x,-1.35,z,.12,.065,20)
        sphere(12,x,-1.38,z,.065,.03,.065)
    gear(0,.83,.49,.37,32)
    gear(-.71,.92,.23,.16,18)
    gear(.68,1.01,.27,.19,20)
    # Pipe lengths alternate like the reference; gold caps, ivory metal tubes.
    for i in range(9):
        x=(i-4)*.245
        length=(.78,.98,.85,1.07,.90,1.04,.82,.96,.76)[i]
        ztop=2.19; zbottom=ztop-length
        cone(12,x,-1.49,zbottom,.095,.095,length,16)
        cone(7,x,-1.505,zbottom+.08,.075,.075,length-.19,16)
        cone(12,x,-1.50,ztop-.09,.103,.103,.09,16)
        cone(12,x,-1.50,zbottom,.102,.102,.085,16)
        sphere(12,x,-1.50,ztop+.025,.055,.055,.055,10,6)
    # Curved timber braces frame the wheels at the foot of the mechanism.
    for side in (-1,1):
        beam(0,(side*1.13,-1.52,.58),(side*.98,-1.52,1.12),.13,.12)
        beam(0,(side*.98,-1.52,1.12),(side*.69,-1.52,1.37),.13,.12)
        beam(12,(side*1.10,-1.59,.63),(side*.95,-1.59,1.10),.025,.025)
    # Decorative painted apron between the figures and the chime chamber.
    box(1,0,-1.43,2.34,2.36,.12,.26)
    for x in (-.92,-.69,-.46,-.23,.23,.46,.69,.92):
        sphere(9,x,-1.505,2.35,.07,.025,.035,10,6)
    sphere(13,0,-1.515,2.35,.10,.025,.08,12,6)
    for name,(verts,faces,tiles) in sorted(groups.items()):
        obj = mesh_actor(name,verts,faces,tiles)
        if name in pivots:
            px,py,pz = pivots[name]
            for v in obj.data.vertices:
                v.co.x -= px; v.co.y -= py; v.co.z -= pz
            obj.location = (px,py,pz)
            obj.data.update()
