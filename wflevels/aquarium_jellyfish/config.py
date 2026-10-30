KIND='jellyfish'
TITLE='Jellyfish'
COUNT=51
SPAWN=(0,-.25,2.6)
BOTTOM=1.85
TOP=3.65
SPEED=.65
CLOSE_LOOK=(0,0,2.6)
CLOSE_CAMERA=(0,-4.6,2.8)
# home xyz, excursion xyz, period, phase, scale, heading (turns)
RESIDENTS=[(-3.8,.1,3.0,.25,.08,.40,15,.1,.78,0),(-2.0,.2,2.1,.3,.08,.25,19,.35,.85,0),
           (1.8,.2,3.5,.30,.08,.35,21,.65,.75,0),(3.8,.1,2.2,.25,.08,.35,18,.8,.85,0),
           (3.5,.25,3.55,.22,.06,.24,23,.42,.65,0)]
# Fill staggered lanes, then reveal the most separated candidate next. This
# keeps small companion counts spread across the tank instead of filling each
# row from the left. The original five positions keep the default composition.
_extras=[(-4.1+(i%8)*1.17,(-.28,.28)[(i//8)%2],
          1.95+(i//16)*.65,.22,.06,.28,
          16+(i%7)*.8,(i*.173)%1,.55+(i%3)*.07,0)
         for i in range(COUNT-6)]
while _extras:
    _next=max(range(len(_extras)),key=lambda i:min(
        ((_extras[i][0]-placed[0])/1.4)**2+((_extras[i][1]-placed[1])/.4)**2+
        ((_extras[i][2]-placed[2])/.55)**2
        for placed in RESIDENTS))
    RESIDENTS.append(_extras.pop(_next))
ROCKS=[]
