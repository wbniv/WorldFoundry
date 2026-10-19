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
: tk-dt@ INDEXOF_DELTA_TIME tk@ dup .2 > if drop 0 else 0 max .05 min then ;
: tk-v ( target mb -- ) >r r@ tk@ - tk-dt@ 5 * 1 min * r@ tk@ + r> tk! ;
: tk-bounds ( lo hi mb -- ) >r r@ tk@ min max r> tk! ;
\ One-button TV: Up+OK changes plane; OK-first remains Action.
: tk-toggle 1 tk-mode tk@ - tk-mode tk! 1 tk-neutral tk! ;
: tk-input
  0 tk-action tk!
  JOYSTICK_BUTTON_RIGHT tk-held JOYSTICK_BUTTON_LEFT tk-held - tk-dx tk!
  JOYSTICK_BUTTON_UP tk-held JOYSTICK_BUTTON_DOWN tk-held -
  tk-touch if
    JOYSTICK_BUTTON_A tk-edge if tk-toggle then
    tk-mode tk@ if tk-dy tk! 0 tk-dz tk! else tk-dz tk! 0 tk-dy tk! then
    JOYSTICK_BUTTON_B tk-edge tk-action tk!
  else
    tk-mode tk@ if tk-dy tk! 0 tk-dz tk! else tk-dz tk! 0 tk-dy tk! then
    JOYSTICK_BUTTON_C tk-held JOYSTICK_BUTTON_B tk-held - dup 0 <> if tk-dy tk! else drop then
    JOYSTICK_BUTTON_A tk-edge if
      JOYSTICK_BUTTON_UP tk-held if tk-toggle else 1 tk-action tk! then
    then
  then
  INDEXOF_DELTA_TIME tk@ .2 > if 1 tk-neutral tk! 0 tk-dart tk! 0 tk-drive tk! then
  tk-neutral tk@ if
    0 tk-dx tk! 0 tk-dy tk! 0 tk-dz tk! 0 tk-action tk!
    INDEXOF_HARDWARE_JOYSTICK1_RAW tk@ 30727 & 0 = if 0 tk-neutral tk! then
  then
  tk-action tk@ if tk-cooldown tk@ 0 <= if .3 tk-dart tk! 1 tk-cooldown tk! then then
  INDEXOF_HARDWARE_JOYSTICK1_RAW tk@ tk-prev tk!
  tk-dart tk@ tk-dt@ - 0 max tk-dart tk!
  tk-cooldown tk@ tk-dt@ - 0 max tk-cooldown tk! ;
\ SPECIES_CONTROLLER
\ Root matrix Rz(yaw) Ry(-elevation) Rx(bank), shared by every attachment.
: tk-root
  tk-pose-pitch tk@ tk-cos tk-cp tk! tk-pose-pitch tk@ tk-sin tk-sp tk!
  tk-pose-roll tk@ tk-cos tk-cr tk! tk-pose-roll tk@ tk-sin tk-sr tk! ;
: tk-place ( ox oy oz actor -- ) tk-actor tk! tk-oz tk! tk-oy tk! dup tk-local-x tk! tk-ox tk!
  tk-oy tk@ tk-cr tk@ * tk-oz tk@ tk-sr tk@ * - tk-lateral tk!
  tk-oy tk@ tk-sr tk@ * tk-oz tk@ tk-cr tk@ * + tk-vertical tk!
  tk-ox tk@ tk-cp tk@ * tk-vertical tk@ tk-sp tk@ * - tk-ox tk!
  tk-ox tk@ tk-cy tk@ * tk-lateral tk@ tk-sy tk@ * - tk-scale tk@ * tk-x tk@ +
  INDEXOF_X_POS tk-actor tk@ write-actor-mailbox
  tk-ox tk@ tk-sy tk@ * tk-lateral tk@ tk-cy tk@ * + tk-scale tk@ * tk-y tk@ +
  INDEXOF_Y_POS tk-actor tk@ write-actor-mailbox
  \ Re-read original x: tk-ox above is the projected horizontal component.
  tk-local-x tk@ tk-sp tk@ * tk-vertical tk@ tk-cp tk@ * + tk-scale tk@ * tk-z tk@ +
  INDEXOF_Z_POS tk-actor tk@ write-actor-mailbox ;
: tk-orient ( a b c actor -- ) >r rot tk-pose-roll tk@ + INDEXOF_ROTATION_A r@ write-actor-mailbox
  swap tk-pose-pitch tk@ - INDEXOF_ROTATION_B r@ write-actor-mailbox INDEXOF_ROTATION_C r> write-actor-mailbox ;
: tk-part ( ox oy oz a b c actor -- ) dup >r tk-orient r> tk-place ;
: tk-gait tk-phase tk@ tk-sin ;
: tk-camera-tick
  tk-x tk@ dup * tk-y tk@ dup * + tk-z tk@ tk-focus-z - dup * +
  tk-camera tk@ if 5 > if 0 tk-camera tk! then else 2.8 < if 1 tk-camera tk! then then
  tk-camera tk@ if tk-cam-close else tk-cam-wide then INDEXOF_CAMSHOT tk! ;
