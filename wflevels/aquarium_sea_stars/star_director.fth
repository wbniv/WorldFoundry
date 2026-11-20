\ Director constants and resident paths are generated at export.
: st-dt INDEXOF_DELTA_TIME st@ 0 max .05 min ;
: st-near ( x y radius -- flag ) dup * >r
  INDEXOF_Y_POS st-player read-actor-mailbox - dup *
  swap INDEXOF_X_POS st-player read-actor-mailbox - dup * +
  INDEXOF_Z_POS st-player read-actor-mailbox st-bottom - dup * + r> < ;
: st-face
  st-dx st@ 0 <> st-dy st@ 0 <> | if
    st-dx st@ 0 = if st-dy st@ 0 > if .25 else -.25 then else
    st-dx st@ 0 > if
      st-dy st@ 0 > if .125 else st-dy st@ 0 < if -.125 else 0 then then
    else st-dy st@ 0 > if .375 else st-dy st@ 0 < if -.375 else .5 then then
    then then st-turn st!
    \ Any arm leads; the body only turns by the residual, at most 36 degrees.
    st-turn st@ 5 * .5 + 5 + 1000 mod 5 - dup 5 + 5 mod st-leader st!
    .2 * st-turn st@ swap - st-heading st!
  then ;
: st-surface-angles ( surface -- a b c )
  dup 0 = if drop 0 0 st-heading st@ else
    1 - .25 * .25 st-heading st@ negate rot then ;
: st-pose-player
  st-face
  st-surface st@ st-surface-angles st-c st! st-b st! st-a st!
  st-roll st@ 0 > if
    st-old st@ st-surface-angles
    st-c st@ - dup .5 > if 1 - then dup -.5 < if 1 + then
    st-roll st@ 1.2 / * st-c st@ + st-c st!
    st-b st@ - st-roll st@ 1.2 / * st-b st@ + st-b st!
    st-a st@ - st-roll st@ 1.2 / * st-a st@ + st-a st!
  then
  st-a st@ INDEXOF_ROTATION_A st-visual write-actor-mailbox
  st-b st@ INDEXOF_ROTATION_B st-visual write-actor-mailbox
  st-c st@ INDEXOF_ROTATION_C st-visual write-actor-mailbox
  st-x st@ INDEXOF_X_POS st-visual write-actor-mailbox
  st-y st@ INDEXOF_Y_POS st-visual write-actor-mailbox
  st-z st@ INDEXOF_Z_POS st-visual write-actor-mailbox ;
