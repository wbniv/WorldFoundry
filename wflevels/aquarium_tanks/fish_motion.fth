\ Betta / lionfish: orient, forward cruise, brake, hover. No axis sliding.
: tk-forward
  tk-pitch tk@ tk-cos tk-heading tk@ tk-cos * tk-fx tk!
  tk-pitch tk@ tk-cos tk-heading tk@ tk-sin * tk-fy tk!
  tk-pitch tk@ tk-sin tk-fz tk! ;
: tk-axis-cap ( facing lo hi position -- cap )
  tk-cap-pos tk! tk-cap-hi tk! tk-cap-lo tk! tk-cap-facing tk!
  tk-cap-facing tk@ abs .0001 < if 10 else
    tk-cap-facing tk@ 0 > if tk-cap-hi tk@ tk-cap-pos tk@ - else
      tk-cap-lo tk@ tk-cap-pos tk@ - then tk-cap-facing tk@ / .20 / 0 max
  then ;
: tk-caps
  tk-fx tk@ tk-limit-x negate tk-limit-x INDEXOF_X_POS tk@ tk-axis-cap
  tk-fy tk@ tk-limit-y negate tk-limit-y INDEXOF_Y_POS tk@ tk-axis-cap min
  tk-fz tk@ tk-bottom tk-top INDEXOF_Z_POS tk@ tk-axis-cap min
  tk-drive tk@ min tk-drive tk! ;
: tk-player-tick
  0 INDEXOF_INPUT tk! tk-input
  tk-dx tk@ abs tk-dy tk@ abs + 0 > if
    tk-dy tk@ tk-dx tk@ tk-atan2 tk-target tk!
  then
  tk-target tk@ tk-last-target tk@ - tk-wrap abs .001 > if 0 tk-turn-side tk! then
  tk-target tk@ tk-last-target tk!
  tk-target tk@ tk-heading tk@ - tk-wrap tk-error tk!
  \ Keep the chosen arc stable; prefer front glass only while both arcs have room.
  tk-error tk@ abs .45 > tk-turn-side tk@ 0 = & if
    tk-heading tk@ tk-cos 0 >= if -1 else 1 then
    INDEXOF_Y_POS tk@ tk-limit-y negate - .10 < if negate then tk-turn-side tk!
  then
  tk-turn-side tk@ 0 <> if
    tk-error tk@ tk-turn-side tk@ * 0 < if tk-error tk@ tk-turn-side tk@ + tk-error tk! then
    tk-error tk@ abs .40 < if 0 tk-turn-side tk! then
  then
  tk-error tk@ tk-dt@ tk-turn-rate * dup >r negate max r> min dup tk-steer tk!
  tk-heading tk@ + tk-frac tk-heading tk!
  tk-dz tk@ tk-pitch-max * tk-pitch-target tk!
  tk-pitch-target tk@ tk-pitch tk@ - tk-dt@ .18 * dup >r negate max r> min
  tk-pitch tk@ + tk-pitch tk!
  tk-steer tk@ tk-dt@ .0001 max / -.06 * -.018 max .018 min tk-roll tk-v
  tk-dx tk@ abs tk-dy tk@ abs + tk-dz tk@ abs + 0 > tk-dart tk@ 0 > | if
    tk-speed tk-error tk@ abs .125 > if .18 * then
    tk-dart tk@ 0 > if tk-error tk@ abs .125 <= if 1.35 * then then
  else 0 then tk-drive tk-v
  tk-limit-x negate tk-limit-x INDEXOF_X_POS tk-bounds
  tk-limit-y negate tk-limit-y INDEXOF_Y_POS tk-bounds
  tk-bottom tk-top INDEXOF_Z_POS tk-bounds
  tk-forward tk-caps
  tk-drive tk@ .002 < if 0 tk-drive tk! then
  tk-drive tk@ tk-fx tk@ * dup tk-vx tk! INDEXOF_XSPEED tk!
  tk-drive tk@ tk-fy tk@ * dup tk-vy tk! INDEXOF_YSPEED tk!
  tk-drive tk@ tk-fz tk@ * dup tk-vz tk! INDEXOF_ZSPEED tk! ;
