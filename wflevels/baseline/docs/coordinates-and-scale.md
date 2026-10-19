# Coordinates and scale

Authoring and exported known coordinates use X/Y horizontally and Z vertically.
One Blender unit is one World Foundry unit. A metre interpretation remains
provisional until measured native movement/scale evidence is reviewed.

The floor is −100…+100 on X/Y, with its top at Z=0 and bottom at Z=−0.5.
The shared grid origin is (0,0,0). Unit basis tips are exactly (1,0,0),
(0,1,0) and (0,0,1), with negative ticks and independent text labels.
The cube spans 1 × 1 × 1 at (5,0,0.5). The ruler spans 10 units on +X near Y=−2.
Spawn is (0,−5,0.92), facing +Y at rotation C=0.25 revolutions. Native C=0 faces +X.

Room bounds are −120…+120 on X/Y and −20…+40 on Z. CamShot Hither/Yon are
0.1/350; FOV is 65 degrees. Follow/target origin references keep camera offsets
stable as the player moves. Native tests must check axis movement, floor
quadrants, near labels and camera changes rather than assuming export parity.
