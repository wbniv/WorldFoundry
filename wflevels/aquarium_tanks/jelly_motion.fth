\ Jelly: the stroke drives propulsion and bell deformation, never a fish gait.
: j-ease dup dup * swap 2 * 3 swap - * ;
: j-contract dup .20 < if .20 / j-ease else dup .50 < if
  .20 - .30 / j-ease 1 swap - else drop 0 then then ;
: j-span INDEXOF_DELTA_TIME tk@ dup .2 > if drop 0 else 0 max then ;
: j-v >r r@ tk@ - j-span 4 * 1 min * r@ tk@ + r> tk! ;
: j-advance
  j-phase tk@ j-dt tk@ j-period tk@ / + 1 min j-phase tk! ;
: j-contact ( velocity lo hi position -- velocity )
  tk-cap-pos tk! tk-cap-hi tk! tk-cap-lo tk!
  dup 0 > if tk-cap-hi tk@ tk-cap-pos tk@ - INDEXOF_DELTA_TIME tk@ .0001 max / 0 max min
  else tk-cap-lo tk@ tk-cap-pos tk@ - INDEXOF_DELTA_TIME tk@ .0001 max / 0 min max then ;
: j-substep
  j-phase tk@ 1 >= j-suppress tk@ not & if 0 j-phase tk! then
  j-advance
  \ A small bounded current sampled at this animal's position; water-relative drag.
  tk-x tk@ .03 * tk-y tk@ .2 * + tk-sin .045 * j-current-x tk!
  tk-x tk@ .04 * tk-cos .008 * j-current-y tk!
  j-phase tk@ .20 < if 1.10 else 0 then j-thrust tk!
  tk-pose-pitch tk@ tk-sin negate j-thrust tk@ *
    j-current-x tk@ tk-vx tk@ - 1.1 * + j-dt tk@ * tk-vx tk@ + tk-vx tk!
  tk-pose-roll tk@ tk-sin negate tk-pose-pitch tk@ tk-cos * j-thrust tk@ *
    j-current-y tk@ tk-vy tk@ - 1.1 * + j-dt tk@ * tk-vy tk@ + tk-vy tk!
  tk-pose-pitch tk@ tk-cos tk-pose-roll tk@ tk-cos * j-thrust tk@ *
    .18 - tk-vz tk@ 1.1 * - j-dt tk@ * tk-vz tk@ + tk-vz tk!
  tk-vx tk@ tk-limit-x negate tk-limit-x tk-x tk@ j-contact tk-vx tk!
  tk-vy tk@ tk-limit-y negate tk-limit-y tk-y tk@ j-contact tk-vy tk!
  tk-vz tk@ tk-bottom tk-top tk-z tk@ j-contact tk-vz tk! ;
: j-step
  \ At most four stable integration steps; suspended time is discarded.
  j-span dup .15 > if drop 4 else dup .10 > if drop 3 else .05 > if 2 else 1 then then then j-steps tk!
  j-span j-steps tk@ / j-dt tk!
  j-steps tk@ 0 do j-substep loop ;
: tk-player-tick
  0 INDEXOF_INPUT tk! tk-input 0 tk-dart tk!
  INDEXOF_DELTA_TIME tk@ .2 > if 1 j-player-phase tk! 0 j-pending tk! then
  j-player-phase tk@ j-phase tk! tk-dz tk@ 0 > if 3.2 else 4 then j-period tk!
  tk-action tk@ if 1 j-pending tk! then
  JOYSTICK_BUTTON_A tk-held tk-touch if drop JOYSTICK_BUTTON_B tk-held then
  tk-neutral tk@ not & j-held tk!
  j-held tk@ 0 = tk-action tk@ 0 = & if 0 j-pending tk! then
  j-phase tk@ .75 >= j-held tk@ j-pending tk@ | & if 0 j-phase tk! 0 j-pending tk! then
  j-phase tk@ 1 >= tk-dz tk@ 0 >= & tk-neutral tk@ not & if 0 j-phase tk! then
  tk-dx tk@ -.075 * tk-pitch j-v
  tk-dy tk@ -.06 * tk-roll j-v
  tk-pitch tk@ tk-pose-pitch tk! tk-roll tk@ tk-pose-roll tk!
  tk-limit-x negate tk-limit-x INDEXOF_X_POS tk-bounds
  tk-limit-y negate tk-limit-y INDEXOF_Y_POS tk-bounds
  tk-bottom tk-top INDEXOF_Z_POS tk-bounds
  INDEXOF_X_POS tk@ tk-x tk! INDEXOF_Y_POS tk@ tk-y tk! INDEXOF_Z_POS tk@ tk-z tk!
  tk-dz tk@ 0 < tk-neutral tk@ | j-suppress tk!
  j-step j-phase tk@ j-player-phase tk!
  tk-dt@ 0 = if 0 tk-vx tk! 0 tk-vy tk! 0 tk-vz tk! then
  tk-vx tk@ j-player-vx tk! tk-vy tk@ j-player-vy tk! tk-vz tk@ j-player-vz tk!
  tk-vx tk@ INDEXOF_XSPEED tk! tk-vy tk@ INDEXOF_YSPEED tk! tk-vz tk@ INDEXOF_ZSPEED tk! ;
: j-resident
  \ State is integrated per animal; home positions are initialization only.
  0 j-cell tk-x tk! 1 j-cell tk-y tk! 2 j-cell tk-z tk!
  3 j-cell j-phase tk! 4 j-cell j-period tk!
  tk-x tk@ tk-limit-x / .055 * tk-pose-pitch tk!
  tk-y tk@ tk-limit-y / .06 * tk-pose-roll tk!
  5 j-cell tk-vx tk! 6 j-cell tk-vy tk! 7 j-cell tk-vz tk!
  0 j-suppress tk! j-step
  tk-x tk@ tk-vx tk@ j-span * + dup tk-x tk! 0 j-store
  tk-y tk@ tk-vy tk@ j-span * + dup tk-y tk! 1 j-store
  tk-z tk@ tk-vz tk@ j-span * + dup tk-z tk! 2 j-store
  j-phase tk@ 3 j-store
  tk-vx tk@ 5 j-store tk-vy tk@ 6 j-store tk-vz tk@ 7 j-store
  8 j-cell tk-scale tk! 0 tk-yaw tk!
  9 j-cell j-lag-pitch tk! 10 j-cell j-lag-roll tk! ;
: j-trail
  tk-pose-pitch tk@ tk-vx tk@ .06 * + j-lag-pitch tk@ - tk-dt@ 2 * * j-lag-pitch tk@ + j-lag-pitch tk!
  tk-pose-roll tk@ tk-vy tk@ .12 * + j-lag-roll tk@ - tk-dt@ 2 * * j-lag-roll tk@ + j-lag-roll tk! ;
: j-rig
  j-trail j-phase tk@ j-contract j-contraction tk!
  j-contraction tk@ j-phase tk@ j-lag-pitch tk@ tk-pose-pitch tk@ -
  j-lag-roll tk@ tk-pose-roll tk@ - 650 tk@ jelly-deform
  j-contraction tk@ j-phase tk@ j-lag-pitch tk@ tk-pose-pitch tk@ -
  j-lag-roll tk@ tk-pose-roll tk@ - 651 tk@ jelly-deform ;
