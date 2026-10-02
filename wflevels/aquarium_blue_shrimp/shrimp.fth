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
: sh-dt@ INDEXOF_DELTA_TIME sh@ .1 min ;
: sh-v ( target mb -- ) >r r@ sh@ - sh-dt@ 7 * 1 min * r@ sh@ + r> sh! ;
: sh-input
  JOYSTICK_BUTTON_RIGHT sh-held JOYSTICK_BUTTON_LEFT sh-held - sh-dx sh!
  JOYSTICK_BUTTON_UP sh-held JOYSTICK_BUTTON_DOWN sh-held -
  sh-touch if
    JOYSTICK_BUTTON_A sh-edge if 1 sh-mode sh@ - sh-mode sh! then
    sh-mode sh@ if sh-dy sh! 0 sh-dz sh! else sh-dz sh! 0 sh-dy sh! then
    JOYSTICK_BUTTON_B sh-edge
  else
    sh-dz sh! JOYSTICK_BUTTON_C sh-held JOYSTICK_BUTTON_B sh-held - sh-dy sh!
    JOYSTICK_BUTTON_A sh-edge
  then
  if sh-cooldown sh@ 0 <= if .20 sh-dart sh! .75 sh-escape sh! .8 sh-cooldown sh! then then
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
    sh-target sh@ sh-head sh@ - sh-wrap sh-dt@ 2 * dup >r negate max r> min
    sh-head sh@ + sh-frac sh-head sh!
  then
  sh-dart sh@ 0 > if
    sh-head sh@ sh-cos -3.2 * sh-vx sh-v
    sh-head sh@ sh-sin -3.2 * sh-vy sh-v
    .8 sh-vz sh-v
  else
    sh-dx sh@ 1.2 * sh-vx sh-v sh-dy sh@ 1.2 * sh-vy sh-v
    sh-dz sh@ 0 <> if sh-dz sh@ 1.15 * else
      INDEXOF_Z_POS sh@ sh-support sh@ sh-lift + - dup .008 >
      if 2 * .28 min negate else drop 0 then
    then sh-vz sh-v
  then
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
  sh-vx sh@ INDEXOF_XSPEED sh! sh-vy sh@ INDEXOF_YSPEED sh! sh-vz sh@ INDEXOF_ZSPEED sh!
  sh-vx sh@ abs sh-vy sh@ abs + sh-vz sh@ abs + sh-speed sh! ;

\ Pose scratch contains visual origin, heading, pitch, gait and uniform scale.
\ ( ox oy oz actor -- ) local hinge to world. Player pitch deliberately small.
: sh-place sh-actor sh! sh-oz sh! sh-oy sh! sh-ox sh!
  sh-ox sh@ sh-cy sh@ * sh-oy sh@ sh-sy sh@ * - sh-scale sh@ * sh-x sh@ +
  INDEXOF_X_POS sh-actor sh@ write-actor-mailbox
  sh-ox sh@ sh-sy sh@ * sh-oy sh@ sh-cy sh@ * + sh-scale sh@ * sh-y sh@ +
  INDEXOF_Y_POS sh-actor sh@ write-actor-mailbox
  sh-oz sh@ sh-scale sh@ * sh-z sh@ + INDEXOF_Z_POS sh-actor sh@ write-actor-mailbox ;
: sh-orient ( a b c actor -- ) >r rot INDEXOF_ROTATION_A r@ write-actor-mailbox
  swap INDEXOF_ROTATION_B r@ write-actor-mailbox INDEXOF_ROTATION_C r> write-actor-mailbox ;
: sh-part ( offx offy offz a b c actor -- ) dup >r sh-orient r> sh-place ;
: sh-walk sh-phase sh@ sh-sin .035 * sh-activity sh@ .6 * .4 + * ;
: sh-tail-bend sh-escape sh@ .04 * sh-phase sh@ sh-sin .008 * + ;
: sh-pose
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
  14 sh-cell sh-state sh@ 2 = if .5 + then sh-yaw sh!
  \ Turning between route ends eases; heading state stored outside the fixed table.
  sh-yaw sh@ sh-heads sh-slot sh@ + sh@ - sh-wrap sh-elapsed sh@ 1.5 *
  dup >r negate max r> min sh-heads sh-slot sh@ + sh@ + sh-frac
  dup sh-heads sh-slot sh@ + sh! sh-yaw sh!
  12 sh-cell 11 sh-cell * 1.7 * sh-frac sh-phase sh!
  sh-travel sh@ sh-activity sh!
  sh-x sh@ sh-table 15 + sh! sh-y sh@ sh-table 16 + sh!
  0 sh-pitch sh!
  sh-resident-actors sh-pose ;

: sh-player-pose
  INDEXOF_X_POS sh-player read-actor-mailbox sh-x sh!
  INDEXOF_Y_POS sh-player read-actor-mailbox sh-y sh!
  INDEXOF_Z_POS sh-player read-actor-mailbox sh-lift - sh-z sh!
  sh-head sh@ sh-yaw sh! 0 sh-pitch sh! 1 sh-scale sh!
  sh-speed sh@ .8 min sh-activity sh!
  \ Bounded accumulator: long idle sessions must not pay for wrapping an
  \ ever-growing clock hundreds or thousands of times each frame.
  sh-gait-phase sh@ sh-dt@ 1.7 * + sh-frac dup sh-gait-phase sh! sh-phase sh!
  sh-player-actors sh-pose ;
: sh-camera-tick
  \ Hysteresis around the foreground grazing patch. Both views stay outside glass.
  sh-x sh@ 2 - dup * sh-y sh@ .4 + dup * + sh-z sh@ .9 - dup * +
  sh-camera sh@ if 3.6 > if 0 sh-camera sh! then else 2.4 < if 1 sh-camera sh! then then
  sh-camera sh@ if sh-cam-close else sh-cam-wide then INDEXOF_CAMSHOT sh! ;
: sh-director-tick
  sh-init sh@ 0 = if sh-setup 1 sh-init sh! then
  sh-clock sh@ sh-dt@ + sh-clock sh!
  sh-escape sh@ sh-dt@ - 0 max sh-escape sh!
  sh-count 0 > if
    sh-count 0 do
      i 3 mod sh-parity sh@ = if i sh-slot sh! sh-route then
    loop
  then
  sh-parity sh@ 1 + 3 mod sh-parity sh!
  sh-player-pose sh-camera-tick ;
