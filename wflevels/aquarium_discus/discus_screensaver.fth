\ Discus screensaver player: slow traversals of the tank, with long pauses, for the group to
\ gather round. The Tiger Barbs driver (wflevels/aquarium/tiger_barbs_screensaver.fth) with the
\ discus's own turn points (a 1.5 m fish turns 4.0 m from the centre) and a 4 s pause.
\ 760/761 are outside the aquarium controller and school mailbox ranges.
\ Plan: docs/plans/2026-11-22-discus-tank.md.
: aq-screen-leg 760 ; : aq-screen-pause 761 ;
: aq-screen-x aq-screen-leg fish@ if -4.0 else 4.0 then ;
: aq-screen-axis ( current target tolerance -- -1|0|1 )
  >r swap - dup r@ > if drop 1
  else r@ negate < if -1 else 0 then then r> drop ;
: aq-screen-input
  0 aq-dart-req fish!
  aq-screen-pause fish@ 0 > if
    aq-screen-pause fish@ fish-dt - 0 max aq-screen-pause fish!
    0 aq-dx fish! 0 aq-dy fish! 0 aq-dz fish!
  else
    INDEXOF_X_POS read-mailbox aq-screen-x 0.6 aq-screen-axis aq-dx fish!
    INDEXOF_Y_POS read-mailbox 0 0.3 aq-screen-axis aq-dy fish!
    INDEXOF_Z_POS read-mailbox 2.7 0.4 aq-screen-axis aq-dz fish!
    aq-dx fish@ 0 = if
      1 aq-screen-leg fish@ - aq-screen-leg fish!
      4 aq-screen-pause fish!
      0 aq-dy fish! 0 aq-dz fish!
    then
  then ;
: aq-screensaver-tick
  0 INDEXOF_INPUT write-mailbox
  aq-no-kicks aq-screen-input aq-dart
  0 aq-pushed fish!
  aq-trig aq-limits aq-keeps
  aq-targets aq-steer-yaw aq-steer-pitch aq-bank-tick
  aq-trig aq-limits aq-caps
  aq-gait aq-swim-write aq-remember aq-publish
  aq-any? aq-darting? | fish-idle-sense ;
