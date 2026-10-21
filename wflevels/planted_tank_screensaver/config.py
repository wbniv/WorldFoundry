# Planted Tank screensaver: the planted tank with plants only (no urchin, goby,
# seahorses, posts or grazing rocks). Plan: docs/plans/2026-10-21-planted-tank-screensaver.md
KIND='plants'
TITLE='Planted Tank Screensaver'
COUNT=1
ANIMALS=False
ANIMAL=None
# The invisible Player hull (Level::reset() needs a Player) rests where the urchin did.
SPAWN=(0,-.85,.865)
BOTTOM=.865
TOP=.865
SPEED=.0125
CLOSE_LOOK=(0,-.85,1.35)
CLOSE_CAMERA=(0,-5.2,2.0)
RESIDENTS=[]
ROCKS=[]
# Spike S3: y=-8.25 fills 90% of a 16:9 frame with the tank (85% limit y=-8.638).
WIDE_CAMERA=(0,-8.25,2.5)
# Fog start and complete scaled by 0.64 from (9, 45) to keep the look at the nearer camera.
FOG=(5.76,28.8)
# Growth-clock seconds by which every measured seed is fully grown (spikes/maturity-sweep.md).
MATURITY_BOUND=195
# Fallback hold when the catalog has no Hold seconds; the catalog default is also 120.
HOLD_SECONDS=120
