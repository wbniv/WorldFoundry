\ Anemone controller core, independent of new engine APIs.
\ Reserve 720..739, replacing the old six-clump sway block on integration.
\ 0 phase; 1 withdrawal; 2/3 surface offsets; 4/5 velocities;
\ 6/7 requested directions; 8 action held; 9 focus; 10 previous focus;
\ 11 swallow held input; 12 dt; 13 scratch norm; 14 scratch factor;
\ 15 speed; 16/17 legal patch half extents; 18 state; 19 previous hold.
\ Positions are offsets on one connected flat rock patch; actor writes belong
\ to the generator glue. No fish-like vertical swim or actor per tentacle.
: an@ 720 + read-mailbox ; : an! 720 + write-mailbox ;
: an-clamp01 0 max 1 min ;
: an-dt 12 an@ 0 max .25 min ;
: an-reset
  20 0 do 0 i an! loop
  .09 15 an! .75 16 an! .35 17 an! ;
: an-wrap begin dup 1 >= if 1 - then dup 1 < until ;
: an-sqrt 13 an! 1 14 an!
  6 0 do 14 an@ 13 an@ 14 an@ / + .5 * 14 an! loop 14 an@ ;
: an-clear-intent 0 6 an! 0 7 an! 0 8 an! ;
: an-focus
  9 an@ 10 an@ <> if
    0 4 an! 0 5 an! 1 11 an!
    9 an@ 10 an!
  then
  11 an@ if
    6 an@ abs 7 an@ abs + 8 an@ + 0 = if 0 11 an! then
    an-clear-intent
  then
  9 an@ 0 = if an-clear-intent then ;
: an-normalize
  6 an@ dup * 7 an@ dup * + an-sqrt 1 max 13 an!
  6 an@ 13 an@ / 6 an! 7 an@ 13 an@ / 7 an! ;
: an-envelope
  8 an@ 0 <> if 1 .55 else 0 2.2 then
  an-dt swap / an-clamp01 14 an!
  1 an@ - 14 an@ * 1 an@ + an-clamp01 1 an! ;
: an-velocity
  \ No crawl while withdrawing/recovering. Easing starts from current speed.
  1 an@ .015 < 8 an@ 0 = & if 15 an@ else 0 then
  dup 6 an@ * 4 an@ - an-dt .30 / an-clamp01 * 4 an@ + 4 an!
  7 an@ * 5 an@ - an-dt .30 / an-clamp01 * 5 an@ + 5 an! ;
: an-axis ( position-slot velocity-slot extent-slot -- )
  an@ 13 an! >r
  r@ an@ an-dt * over an@ +
  13 an@ negate max 13 an@ min
  dup 13 an@ abs >= if 0 r@ an! then
  swap an! r> drop ;
: an-state
  8 an@ if 2 else 1 an@ .015 > if 3 else
    4 an@ abs 5 an@ abs + .001 > if 1 else 0 then
  then then 18 an! ;
: an-step
  0 an@ 12 an@ 0 max 60 min 6 / + an-wrap 0 an!
  an-focus an-normalize an-envelope an-velocity
  2 4 16 an-axis 3 5 17 an-axis an-state
  8 an@ 19 an! ;
