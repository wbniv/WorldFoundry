\ Three independent tanks: bounded phases, input, neutral buoyancy and posing.
: tk@ read-mailbox ; : tk! write-mailbox ;
: tk-frac begin dup 1 >= if 1 - 0 else 1 then until
  begin dup 0 < if 1 + 0 else 1 then until ;
: tk-sin tk-frac dup .5 > if .5 - -1 else 1 then >r
  2 * dup 1 swap - * dup 16 * swap 4 * 5 swap - / r> * ;
: tk-cos .25 + tk-sin ;
: tk-wrap dup .5 > if 1 - then dup -.5 < if 1 + then ;
: tk-atan-oct dup 1 swap - .04345 * .125 + * ;
: tk-atan2
  2dup abs swap abs + .000001 < if 2drop 0 else
    over abs over abs 2dup > if swap / tk-atan-oct .25 swap - else / tk-atan-oct then
    over 0 < if .5 swap - then rot 0 < if negate then nip then ;
: tk-held INDEXOF_HARDWARE_JOYSTICK1_RAW tk@ & 0 <> if 1 else 0 then ;
: tk-edge dup tk-held swap tk-prev tk@ & 0 <> if drop 0 then ;
: tk-dt@ INDEXOF_DELTA_TIME tk@ .1 min ;
: tk-v ( target mb -- ) >r r@ tk@ - tk-dt@ 5 * 1 min * r@ tk@ + r> tk! ;
: tk-bounds ( lo hi mb -- ) >r r@ tk@ min max r> tk! ;
: tk-input
  JOYSTICK_BUTTON_RIGHT tk-held JOYSTICK_BUTTON_LEFT tk-held - tk-dx tk!
  JOYSTICK_BUTTON_UP tk-held JOYSTICK_BUTTON_DOWN tk-held -
  tk-touch if
    JOYSTICK_BUTTON_A tk-edge if 1 tk-mode tk@ - tk-mode tk! then
    tk-mode tk@ if tk-dy tk! 0 tk-dz tk! else tk-dz tk! 0 tk-dy tk! then
    JOYSTICK_BUTTON_B tk-edge
  else
    tk-dz tk! JOYSTICK_BUTTON_C tk-held JOYSTICK_BUTTON_B tk-held - tk-dy tk!
    JOYSTICK_BUTTON_A tk-edge
  then
  if tk-cooldown tk@ 0 <= if .3 tk-dart tk! 1 tk-cooldown tk! then then
  INDEXOF_HARDWARE_JOYSTICK1_RAW tk@ tk-prev tk!
  tk-dart tk@ tk-dt@ - 0 max tk-dart tk!
  tk-cooldown tk@ tk-dt@ - 0 max tk-cooldown tk! ;
: tk-player-tick
  0 INDEXOF_INPUT tk!
  tk-input
  tk-dx tk@ tk-dy tk@ abs + 0 <> if
    tk-dy tk@ tk-dx tk@ tk-atan2 tk-target tk!
    tk-target tk@ tk-heading tk@ - tk-wrap tk-dt@ .65 * dup >r negate max r> min
    tk-heading tk@ + tk-frac tk-heading tk!
  then
  tk-dx tk@ tk-speed * tk-vx tk-v tk-dy tk@ tk-speed * tk-vy tk-v
  tk-dz tk@ tk-speed * tk-vz tk-v
  tk-dart tk@ 0 > if
    tk-jelly if 1.25 tk-vz tk-v else
      tk-heading tk@ tk-cos 1.9 * tk-vx tk-v
      tk-heading tk@ tk-sin 1.9 * tk-vy tk-v
    then
  then
  tk-limit-x negate tk-limit-x INDEXOF_X_POS tk-bounds
  tk-limit-y negate tk-limit-y INDEXOF_Y_POS tk-bounds
  tk-bottom tk-top INDEXOF_Z_POS tk-bounds
  INDEXOF_X_POS tk@ abs tk-limit-x .01 - >= INDEXOF_X_POS tk@ tk-vx tk@ * 0 > & if 0 tk-vx tk! then
  INDEXOF_Y_POS tk@ abs tk-limit-y .01 - >= INDEXOF_Y_POS tk@ tk-vy tk@ * 0 > & if 0 tk-vy tk! then
  INDEXOF_Z_POS tk@ tk-bottom .01 + <= tk-vz tk@ 0 < & if 0 tk-vz tk! then
  INDEXOF_Z_POS tk@ tk-top .01 - >= tk-vz tk@ 0 > & if 0 tk-vz tk! then
  tk-vx tk@ INDEXOF_XSPEED tk! tk-vy tk@ INDEXOF_YSPEED tk! tk-vz tk@ INDEXOF_ZSPEED tk! ;

: tk-place ( ox oy oz actor -- ) tk-actor tk! tk-oz tk! tk-oy tk! tk-ox tk!
  tk-ox tk@ tk-cy tk@ * tk-oy tk@ tk-sy tk@ * - tk-scale tk@ * tk-x tk@ +
  INDEXOF_X_POS tk-actor tk@ write-actor-mailbox
  tk-ox tk@ tk-sy tk@ * tk-oy tk@ tk-cy tk@ * + tk-scale tk@ * tk-y tk@ +
  INDEXOF_Y_POS tk-actor tk@ write-actor-mailbox
  tk-oz tk@ tk-scale tk@ * tk-z tk@ + INDEXOF_Z_POS tk-actor tk@ write-actor-mailbox ;
: tk-orient ( a b c actor -- ) >r rot INDEXOF_ROTATION_A r@ write-actor-mailbox
  swap INDEXOF_ROTATION_B r@ write-actor-mailbox INDEXOF_ROTATION_C r> write-actor-mailbox ;
: tk-part ( ox oy oz a b c actor -- ) dup >r tk-orient r> tk-place ;
: tk-gait tk-phase tk@ tk-sin ;
: tk-camera-tick
  tk-x tk@ dup * tk-y tk@ dup * + tk-z tk@ tk-focus-z - dup * +
  tk-camera tk@ if 5 > if 0 tk-camera tk! then else 2.8 < if 1 tk-camera tk! then then
  tk-camera tk@ if tk-cam-close else tk-cam-wide then INDEXOF_CAMSHOT tk! ;
