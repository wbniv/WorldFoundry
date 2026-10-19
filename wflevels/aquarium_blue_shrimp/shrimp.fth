\ Blue Shrimp: player control, deterministic resident routes, five-part posing.
\ Generated header supplies actor indices, tuning and sh-* mailbox addresses.
\ Global state 600..639; residents 800..1213. Independent of other levels.
: sh@ read-mailbox ; : sh! write-mailbox ;
: sh-frac begin dup 1 >= if 1 - 0 else 1 then until
  begin dup 0 < if 1 + 0 else 1 then until ;
: sh-sin sh-frac dup .5 > if .5 - -1 else 1 then >r
  2 * dup 1 swap - * dup 16 * swap 4 * 5 swap - / r> * ;
: sh-cos .25 + sh-sin ;
: sh-wrap dup .5 > if 1 - then dup -.5 < if 1 + then ;
: sh-ease dup dup * swap 2 * 3 swap - * ;
: sh-atan-oct dup 1 swap - .04345 * .125 + * ;
: sh-atan2
  2dup abs swap abs + .000001 < if 2drop 0 else
    over abs over abs 2dup > if swap / sh-atan-oct .25 swap - else / sh-atan-oct then
    over 0 < if .5 swap - then rot 0 < if negate then nip then ;
: sh-held INDEXOF_HARDWARE_JOYSTICK1_RAW sh@ & 0 <> if 1 else 0 then ;
: sh-edge dup sh-held swap sh-prev sh@ & 0 <> if drop 0 then ;
: sh-dt@ INDEXOF_DELTA_TIME sh@ dup .2 > if drop 0 else 0 max .05 min then ;
: sh-v ( target mb -- ) >r r@ sh@ - sh-dt@ 7 * 1 min * r@ sh@ + r> sh! ;
: sh-input
  JOYSTICK_BUTTON_RIGHT sh-held JOYSTICK_BUTTON_LEFT sh-held - sh-dx sh!
  JOYSTICK_BUTTON_UP sh-held JOYSTICK_BUTTON_DOWN sh-held -
  sh-touch if
    JOYSTICK_BUTTON_A sh-edge if 1 sh-mode sh@ - sh-mode sh! 1 sh-neutral sh! then
    sh-mode sh@ if sh-dy sh! 0 sh-dz sh! else sh-dz sh! 0 sh-dy sh! then
    JOYSTICK_BUTTON_B sh-edge
  else
    sh-mode sh@ if sh-dy sh! 0 sh-dz sh! else sh-dz sh! 0 sh-dy sh! then
    JOYSTICK_BUTTON_C sh-held JOYSTICK_BUTTON_B sh-held - dup 0 <> if sh-dy sh! else drop then
    JOYSTICK_BUTTON_A sh-edge if JOYSTICK_BUTTON_UP sh-held if
      1 sh-mode sh@ - sh-mode sh! 1 sh-neutral sh! 0 else 1 then else 0 then
  then
  sh-neutral sh@ if drop 0 then
  if sh-cooldown sh@ 0 <= if .20 sh-dart sh! .75 sh-escape sh! .8 sh-cooldown sh! then then
  INDEXOF_DELTA_TIME sh@ .2 > if 1 sh-neutral sh! 0 sh-dart sh! 0 sh-escape sh! then
  sh-neutral sh@ if
    0 sh-dx sh! 0 sh-dy sh! 0 sh-dz sh!
    INDEXOF_HARDWARE_JOYSTICK1_RAW sh@ 30727 & 0 = if 0 sh-neutral sh! then
  then
  INDEXOF_HARDWARE_JOYSTICK1_RAW sh@ sh-prev sh!
  sh-dart sh@ sh-dt@ - 0 max sh-dart sh!
  sh-cooldown sh@ sh-dt@ - 0 max sh-cooldown sh! ;
: sh-support-height
  sh-sand sh-support sh!
  \ The visual feet may settle on authored rock tops; the capsule stays clear
  \ of predictive ground contact. Entry must be above the rock, not inside it.
  sh-rock-support ;
: sh-bounds ( lo hi posmb -- ) >r r@ sh@ min max r> sh! ;
: sh-player-tick
  0 INDEXOF_INPUT sh!
  sh-input sh-support-height
  sh-dx sh@ sh-dy sh@ abs + 0 <> if
    sh-dy sh@ sh-dx sh@ sh-atan2 sh-target sh!
    sh-target sh@ sh-head sh@ - sh-wrap dup abs .45 > if
      sh-head sh@ sh-cos 0 >= if abs negate else abs then then sh-dt@ 2 * dup >r negate max r> min
    sh-head sh@ + sh-frac sh-head sh!
  then
  sh-dart sh@ 0 > if
    sh-head sh@ sh-cos -3.2 * sh-vx sh-v
    sh-head sh@ sh-sin -3.2 * sh-vy sh-v
    .8 sh-vz sh-v
  else
    sh-dx sh@ abs sh-dy sh@ abs + 0 > sh-dz sh@ 0 > | if
      sh-target sh@ sh-head sh@ - sh-wrap abs .08 < if .70 else 0 then
    else 0 then sh-drive sh!
    sh-head sh@ sh-cos sh-drive sh@ * sh-vx sh-v
    sh-head sh@ sh-sin sh-drive sh@ * sh-vy sh-v
    sh-dz sh@ 0 > if .65 else
      INDEXOF_Z_POS sh@ sh-support sh@ sh-lift + - dup .008 >
      if 2 * .28 min negate else drop 0 then
    then sh-vz sh-v
  then
  \ Abort suspended motion and stop backward escape before glass, never axis slide.
  sh-dt@ 0 = if 0 sh-vx sh! 0 sh-vy sh! 0 sh-vz sh! then
  sh-limit-x negate sh-limit-x INDEXOF_X_POS sh-bounds
  sh-limit-y negate sh-limit-y INDEXOF_Y_POS sh-bounds
  sh-support sh@ sh-lift + sh-top INDEXOF_Z_POS sh-bounds
  \ No outward speed at a bound. Every frame owns velocity: stair kicks cannot accumulate.
  INDEXOF_X_POS sh@ abs sh-limit-x .01 - >=
  INDEXOF_X_POS sh@ sh-vx sh@ * 0 > & if 0 sh-vx sh! then
  INDEXOF_Y_POS sh@ abs sh-limit-y .01 - >=
  INDEXOF_Y_POS sh@ sh-vy sh@ * 0 > & if 0 sh-vy sh! then
  INDEXOF_Z_POS sh@ sh-support sh@ sh-lift + .01 + <= sh-vz sh@ 0 < & if 0 sh-vz sh! then
  INDEXOF_Z_POS sh@ sh-top .01 - >= sh-vz sh@ 0 > & if 0 sh-vz sh! then
  sh-vx sh@ dup 0 > if sh-limit-x INDEXOF_X_POS sh@ - else sh-limit-x negate INDEXOF_X_POS sh@ - then
  INDEXOF_DELTA_TIME sh@ .0001 max / over 0 > if min else max then sh-vx sh!
  sh-vy sh@ dup 0 > if sh-limit-y INDEXOF_Y_POS sh@ - else sh-limit-y negate INDEXOF_Y_POS sh@ - then
  INDEXOF_DELTA_TIME sh@ .0001 max / over 0 > if min else max then sh-vy sh!
  sh-vz sh@ dup 0 > if sh-top INDEXOF_Z_POS sh@ - else sh-support sh@ sh-lift + INDEXOF_Z_POS sh@ - then
  INDEXOF_DELTA_TIME sh@ .0001 max / over 0 > if min else max then sh-vz sh!
  sh-vx sh@ INDEXOF_XSPEED sh! sh-vy sh@ INDEXOF_YSPEED sh! sh-vz sh@ INDEXOF_ZSPEED sh!
  sh-vx sh@ abs sh-vy sh@ abs + sh-vz sh@ abs + sh-speed sh! ;

\ Pose scratch contains visual origin, heading, pitch, gait and uniform scale.
\ ( ox oy oz actor -- ) local hinge to world. Player pitch deliberately small.
: sh-place sh-actor sh! sh-oz sh! sh-oy sh! dup sh-local-x sh! sh-ox sh!
  sh-ox sh@ sh-cp sh@ * sh-oz sh@ sh-sp sh@ * - sh-ox sh!
  sh-ox sh@ sh-cy sh@ * sh-oy sh@ sh-sy sh@ * - sh-scale sh@ * sh-x sh@ +
  INDEXOF_X_POS sh-actor sh@ write-actor-mailbox
  sh-ox sh@ sh-sy sh@ * sh-oy sh@ sh-cy sh@ * + sh-scale sh@ * sh-y sh@ +
  INDEXOF_Y_POS sh-actor sh@ write-actor-mailbox
  sh-local-x sh@ sh-sp sh@ * sh-oz sh@ sh-cp sh@ * + sh-scale sh@ * sh-z sh@ + INDEXOF_Z_POS sh-actor sh@ write-actor-mailbox ;
: sh-orient ( a b c actor -- ) >r rot INDEXOF_ROTATION_A r@ write-actor-mailbox
  swap sh-pitch sh@ - INDEXOF_ROTATION_B r@ write-actor-mailbox INDEXOF_ROTATION_C r> write-actor-mailbox ;
: sh-part ( offx offy offz a b c actor -- ) dup >r sh-orient r> sh-place ;
: sh-walk sh-phase sh@ sh-sin sh-contact sh@ if .035 else .012 then * sh-activity sh@ * ;
: sh-tail-bend sh-flip sh@ .04 * sh-phase sh@ sh-sin .008 * + ;
: sh-pose
  sh-pitch sh@ sh-cos sh-cp sh! sh-pitch sh@ sh-sin sh-sp sh!
  sh-yaw sh@ sh-sin sh-sy sh! sh-yaw sh@ sh-cos sh-cy sh!
  sh-pose-parts ;

: sh-table sh-slot sh@ sh-stride * sh-table-base + ;
: sh-cell sh-table + sh@ ;
: sh-route
  \ Route phase advances with elapsed time since this resident's last pose.
  sh-clock sh@ 17 sh-cell - sh-elapsed sh!
  12 sh-cell sh-elapsed sh@ 11 sh-cell / + sh-frac dup
  sh-table 12 + sh! sh-u sh!
  sh-clock sh@ sh-table 17 + sh!
  0 sh-travel sh! 0 sh-state sh!
  sh-u sh@ .35 < if 0 else
    sh-u sh@ .65 < if sh-u sh@ .35 - .3 / 1 sh-travel sh! 1 sh-state sh! else
      sh-u sh@ .8 < if 1 else
        1 sh-u sh@ .8 - .2 / - 1 sh-travel sh! 2 sh-state sh!
      then then then sh-ease sh-u sh!
  5 sh-cell 8 sh-cell sh-u sh@ * + sh-x sh!
  6 sh-cell 9 sh-cell sh-u sh@ * + sh-y sh!
  7 sh-cell 10 sh-cell sh-u sh@ * + sh-z sh!
  13 sh-cell sh-scale sh!
  \ The current route displacement supplies heading and distance-driven gait.
  sh-x sh@ 15 sh-cell - sh-dx sh! sh-y sh@ 16 sh-cell - sh-dy sh!
  sh-dx sh@ abs sh-dy sh@ abs + sh-motion sh!
  sh-motion sh@ .00001 > if
    sh-dy sh@ sh-dx sh@ sh-atan2 sh-yaw sh!
    sh-yaw sh@ sh-heads sh-slot sh@ + sh!
  else sh-heads sh-slot sh@ + sh@ sh-yaw sh! then
  1450 sh-slot sh@ + sh@ sh-motion sh@ 4 * + sh-frac dup
  1450 sh-slot sh@ + sh! sh-phase sh!
  sh-motion sh@ sh-elapsed sh@ .0001 max / 4 * 1 min sh-activity sh!
  10 sh-cell abs .01 < dup sh-contact sh!
  if 0 sh-pitch sh! else
    10 sh-cell 8 sh-cell abs 9 sh-cell abs + .001 max sh-atan2
    sh-state sh@ 2 = if negate then -.0833333 max .0833333 min sh-pitch sh!
    sh-travel sh@ if .5 sh-activity sh! then
  then
  0 sh-flip sh!
  sh-x sh@ sh-table 15 + sh! sh-y sh@ sh-table 16 + sh!
  sh-resident-actors sh-pose ;

: sh-player-pose
  INDEXOF_X_POS sh-player read-actor-mailbox sh-x sh!
  INDEXOF_Y_POS sh-player read-actor-mailbox sh-y sh!
  INDEXOF_Z_POS sh-player read-actor-mailbox sh-lift - sh-z sh!
  sh-head sh@ sh-yaw sh! 1 sh-scale sh! sh-escape sh@ sh-flip sh!
  sh-pose-init sh@ 0 = if
    sh-x sh@ sh-last-x sh! sh-y sh@ sh-last-y sh! sh-z sh@ sh-last-z sh! 1 sh-pose-init sh!
  then
  sh-x sh@ sh-last-x sh@ - abs sh-y sh@ sh-last-y sh@ - abs + sh-motion sh!
  sh-z sh@ sh-support sh@ - .025 < sh-vz sh@ abs .05 < & sh-contact sh!
  sh-contact sh@ if
    0 sh-player-pitch sh! sh-motion sh@ sh-dt@ .0001 max / 1.4 * 1 min sh-activity sh!
    sh-gait-phase sh@ sh-motion sh@ 4 * + sh-frac
  else
    sh-vz sh@ sh-vx sh@ abs sh-vy sh@ abs + .08 max sh-atan2
    -.0833333 max .0833333 min sh-player-pitch sh-v
    sh-speed sh@ .1 > if .65 else 0 then sh-activity sh!
    sh-gait-phase sh@ sh-dt@ 3.5 * sh-activity sh@ * + sh-frac
  then dup sh-gait-phase sh! sh-phase sh!
  sh-player-pitch sh@ sh-z sh@ sh-support sh@ - .35 / 0 max 1 min .0833333 * dup >r negate max r> min sh-pitch sh!
  sh-x sh@ sh-last-x sh! sh-y sh@ sh-last-y sh! sh-z sh@ sh-last-z sh!
  sh-player-actors sh-pose ;
: sh-camera-tick
  \ Hysteresis around the foreground grazing patch. Both views stay outside glass.
  sh-x sh@ 2 - dup * sh-y sh@ .4 + dup * + sh-z sh@ .9 - dup * +
  sh-camera sh@ if 3.6 > if 0 sh-camera sh! then else 2.4 < if 1 sh-camera sh! then then
  sh-camera sh@ if sh-cam-close else sh-cam-wide then INDEXOF_CAMSHOT sh! ;
: sh-director-tick
  sh-init sh@ 0 = if sh-setup 1 sh-init sh! then
  sh-clock sh@ sh-dt@ + sh-clock sh!
  sh-antenna-phase sh@ sh-dt@ .65 * + sh-frac sh-antenna-phase sh!
  sh-escape sh@ sh-dt@ - 0 max sh-escape sh!
  sh-count 0 > if
    sh-count 0 do
      i 3 mod sh-parity sh@ = if i sh-slot sh! sh-route then
    loop
  then
  sh-parity sh@ 1 + 3 mod sh-parity sh!
  sh-player-pose sh-camera-tick ;
