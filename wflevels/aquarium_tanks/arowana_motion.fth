\ Long-bodied swimming. Shared aq-* words provide input, trig, limits and pose.
\ ar-state: 0 scull/coast, 1 cruise, 2 brake/turn, 3 burst, 4 recovery.
\ Conservative sweep reserve covers every yaw and the full permitted pitch/bank,
\ including animated tail, fins and barbels: turning never needs a sideways push.
: ar-direction-mask 30726 ;
: ar-control-mask 30727 ;
: ar-toggle 1 aq-mode fish@ - aq-mode fish! 1 ar-neutral fish! ;
: ar-read-touch
 JOYSTICK_BUTTON_A aq-edge if ar-toggle then
 JOYSTICK_BUTTON_RIGHT aq-held JOYSTICK_BUTTON_LEFT aq-held - aq-dx fish!
 JOYSTICK_BUTTON_UP aq-held JOYSTICK_BUTTON_DOWN aq-held -
 aq-mode fish@ if aq-dy fish! 0 aq-dz fish! else aq-dz fish! 0 aq-dy fish! then
 JOYSTICK_BUTTON_B aq-edge aq-dart-req fish! ;
: ar-read-remote
 JOYSTICK_BUTTON_RIGHT aq-held JOYSTICK_BUTTON_LEFT aq-held - aq-dx fish!
 JOYSTICK_BUTTON_UP aq-held JOYSTICK_BUTTON_DOWN aq-held -
 aq-mode fish@ if aq-dy fish! 0 aq-dz fish! else aq-dz fish! 0 aq-dy fish! then
 JOYSTICK_BUTTON_C aq-held JOYSTICK_BUTTON_B aq-held - dup 0 <> if aq-dy fish! else drop then
 0 aq-dart-req fish!
 JOYSTICK_BUTTON_A aq-edge if
  JOYSTICK_BUTTON_UP aq-held if ar-toggle
  else 1 aq-dart-req fish! then
 then ;
: ar-input
 ar-init fish@ 0 = if 1 ar-init fish! 1 ar-neutral fish! then
 INDEXOF_DELTA_TIME read-mailbox .2 > if
  1 ar-neutral fish! 0 aq-dart-t fish! 0 ar-cool fish! 0 aq-speed fish!
 then
 aq-remote if ar-read-remote else aq-touch if ar-read-touch else aq-read-keys then then
 ar-neutral fish@ if
  0 aq-dx fish! 0 aq-dy fish! 0 aq-dz fish! 0 aq-dart-req fish!
  aq-joy ar-control-mask & 0 = if 0 ar-neutral fish! then
 then ;
: ar-dart
 ar-cool fish@ fish-dt - 0 max ar-cool fish!
 aq-dart-t fish@ fish-dt - 0 max aq-dart-t fish!
 aq-dart-req fish@ ar-cool fish@ 0 = & ar-neutral fish@ 0 = & if
  aq-dart-time aq-dart-t fish! ar-recovery aq-dart-time + ar-cool fish!
 then ;
: ar-limits
 aq-limits
 ar-inner-x ar-sweep-xy - dup aq-hix fish@ min aq-hix fish!
 negate aq-lox fish@ max aq-lox fish!
 ar-inner-y ar-sweep-xy - dup aq-hiy fish@ min aq-hiy fish!
 negate aq-loy fish@ max aq-loy fish!
 ar-bottom ar-sweep-z + aq-loz fish@ max aq-loz fish!
 ar-top ar-sweep-z - aq-hiz fish@ min aq-hiz fish! ;
: ar-room-axis ( lo hi position -- distance ) >r r@ - swap r> swap - min ;
: ar-room
 aq-lox fish@ aq-hix fish@ INDEXOF_X_POS read-mailbox ar-room-axis
 aq-loy fish@ aq-hiy fish@ INDEXOF_Y_POS read-mailbox ar-room-axis min
 0 max ar-room-mb fish! ;
: ar-targets
 aq-targets
 aq-yaw-t fish@ ar-target-last fish@ - aq-wrap-h abs .001 > if 0 ar-turn-side fish! then
 aq-yaw-t fish@ ar-target-last fish!
 aq-yaw-t fish@ aq-yaw fish@ - aq-wrap-h ar-error fish!
 ar-error fish@ abs .40 > ar-turn-side fish@ 0 = & if aq-centre-side ar-turn-side fish! then
 ar-turn-side fish@ 0 <> if
  ar-error fish@ ar-turn-side fish@ * 0 < if ar-error fish@ ar-turn-side fish@ + ar-error fish! then
  ar-error fish@ abs .35 < if 0 ar-turn-side fish! then
 then
 aq-any? ar-error fish@ abs .18 >
 aq-blocked? ar-error fish@ abs .005 > & | & if 1 ar-turn fish! then
 ar-error fish@ abs .005 < aq-any? 0 = | if 0 ar-turn fish! then
 ar-room
 ar-room-mb fish@ ar-length < aq-dart-t fish@ 0 > | if ar-radius-wall else ar-radius-cruise then ar-radius fish! ;
: ar-gait
 0 aq-brake fish! 0 aq-burst fish! 0 ar-state fish!
 aq-dart-t fish@ 0 > if
  aq-dart-v aq-tau-dart aq-ease 3 ar-state fish!
 else aq-drive? if
  ar-turn fish@ if
   ar-turn-speed .18 aq-ease 1 aq-brake fish! 2 ar-state fish!
  else
   aq-v 1 ar-error fish@ abs .18 / fish-clamp01 .35 * - *
   aq-tau-a aq-ease 1 ar-state fish!
  then
 else
  0 aq-tau-glide aq-ease aq-speed fish@ aq-v / fish-clamp01 aq-brake fish!
 then then
 ar-cool fish@ 0 > aq-dart-t fish@ 0 = & if 4 ar-state fish! then
 aq-speed fish@ .005 < if 0 aq-speed fish! then
 aq-drive? aq-was-moving fish! ;
: ar-steer-yaw
 ar-turn fish@ if
  ar-pivot-rate aq-speed fish@ aq-v / fish-clamp01
  ar-pivot-rate aq-v ar-radius-cruise / 6.2831853 / - * -
 else
  aq-speed fish@ ar-radius fish@ / 6.2831853 / aq-yaw-wmax min
 then ar-yaw-cap fish!
 ar-error fish@ aq-yaw-wn dup * *
 aq-yaw-w fish@ 2 aq-yaw-zeta * aq-yaw-wn * * -
 fish-dt * aq-yaw-w fish@ + ar-yaw-cap fish@ fish-clampabs aq-yaw-w fish!
 aq-yaw-w fish@ fish-dt * aq-yaw fish@ + aq-wrap-h aq-yaw fish! ;
: ar-bank
 aq-yaw-w fish@ aq-bank * negate aq-bank-max fish-clampabs
 aq-roll fish@ - fish-dt .35 / fish-clamp01 * aq-roll fish@ + aq-roll fish! ;
: ar-bend-tick
 aq-yaw-w fish@ -1.8 *
 .35 fish-clampabs ar-bend fish@ - fish-dt .25 / fish-clamp01 * ar-bend fish@ + ar-bend fish! ;
: ar-caps
 \ Ray distance / (lookahead + glide time) anticipates stopping before the swept envelope.
 aq-caps
 aq-speed fish@ aq-cap fish@ min aq-speed fish!
 aq-speed fish@ aq-v / fish-clamp01 aq-burst fish!
 ar-state fish@ 2 = if 1 aq-brake fish! then ;
: ar-player-tick
 0 INDEXOF_INPUT write-mailbox aq-no-kicks ar-input ar-dart
 aq-trig ar-limits
 0 aq-pushed fish! aq-keeps
 ar-targets ar-gait
 \ Cap speed before computing curvature, so yaw cannot exceed the final speed/radius.
 aq-trig ar-limits ar-caps
 ar-steer-yaw aq-steer-pitch ar-bank
 aq-trig ar-limits ar-caps
 \ Reapply the curvature bound after a changed facing reduces the available speed.
 ar-turn fish@ 0 = if
  aq-yaw-w fish@ aq-speed fish@ ar-radius fish@ / 6.2831853 / fish-clampabs aq-yaw-w fish!
 then
 ar-bend-tick aq-swim-write aq-remember aq-publish
 aq-joy aq-prev fish! aq-any? aq-darting? | fish-idle-sense ;
