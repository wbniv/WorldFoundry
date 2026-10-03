\ Planted Urchin: substrate crawl, static planting and manually selected views.
: tk-neutral 718 ;
: tk@ read-mailbox ; : tk! write-mailbox ;
: tk-dt@ INDEXOF_DELTA_TIME tk@ dup .2 > if drop 0 else 0 max .05 min then ;
: tk-held INDEXOF_HARDWARE_JOYSTICK1_RAW tk@ & 0 <> if 1 else 0 then ;
: tk-edge dup tk-held swap tk-prev tk@ & 0 <> if drop 0 then ;
: tk-v >r r@ tk@ - tk-dt@ 5 * 1 min * r@ tk@ + r> tk! ;
: tk-bounds >r r@ tk@ min max r> tk! ;
: tk-player-tick
  0 INDEXOF_INPUT tk!
  INDEXOF_DELTA_TIME tk@ .2 > if 1 tk-neutral tk! 0 tk-vx tk! 0 tk-vy tk! then
  JOYSTICK_BUTTON_RIGHT tk-held JOYSTICK_BUTTON_LEFT tk-held - tk-dx tk!
  JOYSTICK_BUTTON_UP tk-held JOYSTICK_BUTTON_DOWN tk-held - tk-dy tk!
  JOYSTICK_BUTTON_A tk-edge tk-neutral tk@ not & if 1 tk-camera tk@ - tk-camera tk! then
  tk-neutral tk@ if
    0 tk-dx tk! 0 tk-dy tk!
    INDEXOF_HARDWARE_JOYSTICK1_RAW tk@ 30727 & 0 = if 0 tk-neutral tk! then
  then
  INDEXOF_HARDWARE_JOYSTICK1_RAW tk@ tk-prev tk!
  \ Normalize the only possible diagonal, retaining the species' tiny speed.
  tk-dx tk@ abs tk-dy tk@ abs + 2 = if .70710678 else 1 then tk-sy tk!
  tk-dx tk@ tk-speed * tk-sy tk@ * tk-vx tk-v
  tk-dy tk@ tk-speed * tk-sy tk@ * tk-vy tk-v 0 tk-vz tk!
  tk-dt@ 0 = if 0 tk-vx tk! 0 tk-vy tk! then
  tk-limit-x negate tk-limit-x INDEXOF_X_POS tk-bounds
  tk-limit-y negate tk-limit-y INDEXOF_Y_POS tk-bounds
  tk-bottom tk-top INDEXOF_Z_POS tk-bounds
  INDEXOF_X_POS tk@ abs tk-limit-x .01 - >= INDEXOF_X_POS tk@ tk-vx tk@ * 0 > & if 0 tk-vx tk! then
  INDEXOF_Y_POS tk@ abs tk-limit-y .01 - >= INDEXOF_Y_POS tk@ tk-vy tk@ * 0 > & if 0 tk-vy tk! then
  INDEXOF_Z_POS tk@ tk-bottom .01 + <= tk-vz tk@ 0 < & if 0 tk-vz tk! then
  INDEXOF_Z_POS tk@ tk-top .01 - >= tk-vz tk@ 0 > & if 0 tk-vz tk! then
  tk-vx tk@ INDEXOF_XSPEED tk! tk-vy tk@ INDEXOF_YSPEED tk! tk-vz tk@ INDEXOF_ZSPEED tk! ;
: tk-camera-tick
  INDEXOF_X_POS tk-player read-actor-mailbox dup INDEXOF_X_POS tk-look-close write-actor-mailbox
  INDEXOF_X_POS tk-cam-close write-actor-mailbox
  INDEXOF_Y_POS tk-player read-actor-mailbox INDEXOF_Y_POS tk-look-close write-actor-mailbox
  INDEXOF_Z_POS tk-player read-actor-mailbox  .485 + dup INDEXOF_Z_POS tk-look-close write-actor-mailbox
  1.135 + INDEXOF_Z_POS tk-cam-close write-actor-mailbox
  tk-camera tk@ if tk-cam-close else tk-cam-wide then INDEXOF_CAMSHOT tk!
  1 tk-init tk! ;
