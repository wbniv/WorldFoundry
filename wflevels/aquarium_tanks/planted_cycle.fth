\ Planted Tank screensaver cycle: grow to the maturity bound, hold, then end the level.
\ Plan: docs/plans/2026-10-21-planted-tank-screensaver.md (decisions 2-4).
\ The generated header defines the constants (pt-director, the field ids, pt-bound,
\ pt-max-age, pt-stall, pt-hold-default, pt-hold-max, pt-level-to-run) and the
\ mailboxes (pt-clock, pt-holding, pt-hold, pt-hold-begin, pt-ended); tests redefine them.
\ The growth clock mirrors planted::tick (wfsource/source/game/plant_settings.h):
\ a frame longer than pt-stall counts as 0, and age += dt * speedValue(Growth speed).
\ The hold is measured on the level clock (TIME, 1906), which restarts with each load.
\ END_OF_LEVEL (1905) is only ever written with 1: a 0 falls through to CAMSHOT (level.cc).
\ Growth speed index 0..6 to its rate, as speedValue: 0, .25, .5, 1, 2, 4, 8.
: pt-speed-value
  dup 1 < if drop 0 exit then dup 2 < if drop .25 exit then dup 3 < if drop .5 exit then
  dup 4 < if drop 1 exit then dup 5 < if drop 2 exit then 6 < if 4 exit then 8 ;
\ A missing catalog runs the engine default, 1x.
: pt-speed pt-director pt-speed-field property@ if pt-speed-value else drop 1 then ;
: pt-dt INDEXOF_DELTA_TIME tk@ dup pt-stall > if drop 0 else 0 max then ;
\ Hold seconds may exceed 32767, so read its four bytes (property@ refuses it).
: pt-hold@ pt-director pt-hold-field property-int-bytes@
  if 256 * + 256 * + 256 * + else drop drop drop drop pt-hold-default then
  0 max pt-hold-max min ;
\ Called once, right after plant-register has run planted::enter(): start at Initial age.
: pt-start pt-director pt-age-field property@ if else drop 0 then
  dup 0 < if drop 0 then dup pt-max-age > if drop 0 then pt-clock tk! ;
: pt-end 1 pt-ended tk! 0 pt-level-to-run tk! 1 INDEXOF_END_OF_LEVEL tk! ;
: pt-cycle-tick
  pt-holding tk@ 0 = if
    pt-clock tk@ pt-dt pt-speed * + pt-max-age min dup pt-clock tk!
    pt-bound < if exit then
    \ Hold seconds is read now, the frame the hold starts, never cached before it,
    \ so a host write from frame 2 onward is honoured.
    pt-hold@ pt-hold tk! INDEXOF_TIME tk@ pt-hold-begin tk! 1 pt-holding tk!
  then
  pt-ended tk@ if exit then
  INDEXOF_TIME tk@ pt-hold-begin tk@ - pt-hold tk@ < if exit then
  pt-end ;
