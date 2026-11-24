"""Compile the local-time timetable and a periodic camera spline to level zForth."""
from town import BERTHS, BRIDGE, MARKET, SPAN
import forth

# Landing, over the west quay, courtyard lane, square, footbridge, boatyard,
# mill panorama and growers' bank. Each knot pairs an eye with its point of interest.
ROUTE = [
    (-2.3,-10.3,6.15,-2.15,-.80,2.25),
    (-5.95,-3.65,5.75,-6.55,.75,1.45),
    (-6.48,1.50,4.80,-6.80,4.65,.98),
    (-6.28,3.45,4.55,-3.52,4.65,1.15),
    (-2.15,2.74,3.60,-.12,5.54,.95),
    (1.20,2.74,4.20,3.94,4.28,1.12),
    (7.25,4.26,5.25,7.70,.60,1.15),
    (7.47,-1.32,5.30,9.30,1.30,1.63),
    (12.50,-5.32,8.02,3.65,1.42,1.45),
    (6.30,-12.0,8.30,-.65,.25,2.00),
]
STILL=(-1.6,-16.5,14.0,-.5,1.4,1.20)


def coefficients(leg):
    prev,p,q,following=(ROUTE[(leg+k)%len(ROUTE)] for k in (-1,0,1,2))
    return [((-a+3*b-3*c+d)/2,(2*a-5*b+4*c-d)/2,(-a+c)/2,b)
            for a,b,c,d in zip(prev,p,q,following)]


def write_camera_component(ix,component):
    axis='xyz'[component%3]
    if component<3:
        # Pose the physical camera too: the bungee otherwise cuts straight through
        # the blocks between the landing and a mid-lap start or a clock correction.
        return f'dup {ix["Camera"]} cv-w{axis} {ix["cs_wide"]} cv-w{axis}'
    return f'{ix["LookAt"]} cv-w{axis}'


def camera_words(ix):
    # The eye and target have matching tangents on either side of a knot.
    out=[]
    for i in range(len(ROUTE)):
        out.append(f': quay-leg-{i}')
        for j,co in enumerate(coefficients(i)):
            expr=' cv-u cv@ * '.join([forth.n(co[0])]+[forth.n(term)+' +' for term in co[1:]])
            out.append(f' {expr} {write_camera_component(ix,j)}')
        out.append(';')
    out+=[': quay-camera quay-still if']
    for i,value in enumerate(STILL):
        out.append(f' {value} {write_camera_component(ix,i)}')
    out+=[' else',' cv-mi cv@ 15 cv-mod 60 * cv-sc cv@ + cv-lap cv!',
          ' cv-mi cv@ 15 < if 24 else 8 then cv-hold cv!',
          ' cv-lap cv@ cv-hold cv@ - 0 max 900 cv-hold cv@ - / 4 * cv-frac',
          # Slow the first and last eight percent of each lap down to a stop.
          ' dup .08 < if dup .08 / dup 2 swap - * * else',
          ' dup .92 > if 1 swap - dup .08 / dup 2 swap - * * 1 swap - then then',
          f' {len(ROUTE)} * dup cv-floor cv-k cv! cv-frac cv-u cv!']
    out += [f' cv-k cv@ {i} = if quay-leg-{i} then' for i in range(len(ROUTE))]
    return out+[' then ;']


def script(ix,fields):
    who=ix['DutchCuckooVillageSettings']
    out=forth.common_words()+[': cv-sgn 1 ;']
    for word,label,default in [('quay-still','Camera motion',0),('quay-lights','Window lights',1)]:
        out.append(f': {word} {who} {fields[label]} property@ if else drop {default} then ;')
    out+=forth.hand_words(ix)+forth.clockwork_words(ix)
    out+=camera_words(ix)
    x,y,z=BRIDGE
    mx,my=MARKET
    out+=[': quay-crossing',
          ' cv-tm cv@ 4 / cv-sm 1 cv-tm cv@ 16 - 5 / cv-sm - * .216 * cv-th cv!',
          f' cv-th cv@ dup {ix["BridgeLeaf"]} cv-wa {ix["BridgeBeam"]} cv-wa',
          f' cv-th cv@ cv-cos {SPAN} * {y} + {ix["BridgeChains"]} cv-wy',
          f' cv-th cv@ cv-sin {SPAN} * {z} + {ix["BridgeChains"]} cv-wz',
          ' cv-tm cv@ 4 - 12 / cv-sm .92 * cv-tm cv@ 16 - 8 / cv-sm .08 * +',
          ' cv-hr cv@ 2 cv-mod if 1 swap - then',
          f' {BERTHS[1]-BERTHS[0]} * {BERTHS[0]} + dup {ix["BulbBarge"]} cv-wx {ix["Wake"]} cv-wx',
          ' cv-tm cv@ 4 > cv-tm cv@ 24 < & if 1 else 0 then 215 cv!',
          f' cv-o cv@ -.23 * {ix["Hatch"]} cv-wc ;',
          ': quay-market',
          ' cv-sc cv@ 20 - 3 / cv-sm 1 cv-sc cv@ 27 - 5 / cv-sm - * cv-f cv!',
          ' cv-sc cv@ 22 - 2 / cv-sm 1 cv-sc cv@ 27 - 4 / cv-sm - *',
          ' cv-sc cv@ 23 - 4 / cv-sm .5 * 1 swap - * -.035 * cv-th cv!',
          f' cv-th cv@ {ix["Balance"]} cv-wb',
          ' cv-th cv@ cv-sin .45 * cv-bow cv!',
          f' .67 cv-bow cv@ + {ix["CheesePan"]} cv-wz .67 cv-bow cv@ - {ix["WeightPan"]} cv-wz',
          f' cv-f cv@ .30 * {mx-.39} + dup {ix["WeighedWheel"]} cv-wx {ix["MerchantHand"]} cv-wx',
          f' .66 cv-f cv@ .053 cv-bow cv@ + * + dup {ix["WeighedWheel"]} cv-wz .07 + {ix["MerchantHand"]} cv-wz ;',
          ': quay-weather',
          ' cv-mi cv@ 10 cv-mod 60 * cv-sc cv@ + cv-s cv!',
          ' cv-s cv@ 10 / cv-sm 1 cv-s cv@ 80 - 10 / cv-sm - * cv-w cv!',
          ' cv-w cv@ 0 > if 1 else 0 then 214 cv!',
          ' cv-s cv@ 120 < if 1 else 0 then 216 cv!',
          f' cv-sc cv@ 2 * cv-frac -.52 * 1 cv-w cv@ - 2 * + {ix["Raindrops"]} cv-wz',
          ' cv-sc cv@ 2 * cv-frac 3 * cv-floor cv-i cv!',
          *[f' cv-i cv@ {i} = cv-w cv@ 0 > & if 1 else 0 then {217+i} cv!' for i in range(3)],
          f' cv-sc cv@ 2 * cv-frac -.16 * cv-s cv@ 90 - 30 / cv-sm 1.4 * - {ix["Runoff"]} cv-wz',
          f' cv-sc cv@ 12 / cv-sin .13 * {ix["WaterGlints"]} cv-wx',
          ' cv-hr cv@ 60 * cv-mi cv@ + cv-s cv!']
    for i in range(8):
        out.append(f' cv-sc cv@ 6 / {i*.123} + cv-sin .075 * {ix["Lamplight"+str(i)]} cv-wx')
        stagger=(i*5%8)*7.5
        out.append(f' cv-s cv@ {1050+stagger} >= cv-s cv@ {330+stagger} < + quay-lights & if 1 else 0 then {200+i} cv!')
    out+=[' ;',': quay-tick',
          ' INDEXOF_WALL_SECOND cv@ cv-sc cv! INDEXOF_WALL_MINUTE cv@ cv-mi cv! INDEXOF_WALL_HOUR cv@ cv-hr cv!',
          ' cv-mi cv@ 60 * cv-sc cv@ + cv-tm cv!',
          f' cv-tm cv@ 48 / cv-frac {ix["PostMillSails"]} cv-wb',
          f' cv-tm cv@ 72 / .087 + cv-frac {ix["PolderMillSails"]} cv-wb',
          ' cv-hands cv-figs cv-bird quay-crossing quay-market quay-weather quay-camera ;','quay-tick']
    return '\n'.join(out)+'\n'
