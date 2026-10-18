\ Seahorse behaviour: docs/plans/2026-10-16-saltwater-seahorses.md, Phase 3.
\ One state machine per seahorse over its DFRM block (sh-block s). Cells 0..39 face the
\ engine (Phase 1, E3); 40..97 are this file's. 1170..1179 are shared.
\ States: 0 hold, 1 release, 2 swim, 3 probe, 4 grasp, 5 strike, 6 greet.
\ Needs tk@ tk! tk-dt@ tk-frac tk-sin tk-cos tk-wrap tk-atan2 uf-hypot, the clip ids
\ (sh-clip-*) and the generated sh-spot / sh-spot-off / sh-spot-post / sh-count / sh-greeting.
: sh-b sh-shared 9 + tk@ ;
: sh-cell sh-b + dup 70 >= over 72 <= & sh-b 2 = & if 1042 + then ;
: sh@ sh-cell tk@ ; : sh! sh-cell tk! ;
: sh-init 40 ; : sh-state 41 ; : sh-age 42 ; : sh-spot# 43 ; : sh-rest 44 ;
: sh-x 45 ; : sh-y 46 ; : sh-z 47 ; : sh-yaw 48 ; : sh-vx 49 ; : sh-vy 50 ; : sh-vz 51 ;
: sh-strike 52 ; : sh-head 53 ; : sh-eyet 54 ; : sh-eyel 55 ; : sh-eyer 56 ; : sh-rudder 57 ;
: sh-seed 58 ; : sh-valid 59 ; : sh-greet 60 ; : sh-body 61 ; : sh-fins 62 ; : sh-sex 63 ;
: sh-ax 65 ; : sh-ay 66 ; : sh-az 67 ; : sh-r 68 ; : sh-start 69 ; : sh-tyaw 70 ;
: sh-tx 71 ; : sh-ty 72 ; : sh-tz 73 ; : sh-fin 74 ; : sh-c 76 ; : sh-s 77 ;
: sh-wx 78 ; : sh-wy 79 ; : sh-wz 80 ; : sh-ex 81 ; : sh-ey 82 ; : sh-hx 83 ; : sh-hy 84 ;
: sh-id 75 ;
: sh-hz 85 ; : sh-dist 86 ; : sh-kf 87 ; : sh-kl 88 ; : sh-pk 89 ; : sh-off 90 ; : sh-next 91 ;
: shg-phase sh-shared 0 + ; : shg-pair sh-shared 1 + ; : shg-time sh-shared 2 + ; : shg-due sh-shared 3 + ; : shg-on sh-shared 4 + ;
: shg-ready sh-shared 5 + ;
: sh-now INDEXOF_TIME tk@ ;
: sh-go ( state -- ) sh-state sh! 0 sh-age sh! ;
: sh-rand ( -- r ) sh-seed sh@ .6180339 + tk-frac dup sh-seed sh! tk-sin 9.137 * abs tk-frac ;
: sh-trig sh-yaw sh@ dup tk-cos sh-c sh! tk-sin sh-s sh! ;
\ Body-local (x, y) to world and back, by this frame's yaw.
: sh-rot ( lx ly -- wx wy ) 2dup sh-c sh@ * swap sh-s sh@ * + >r sh-s sh@ * swap sh-c sh@ * swap - r> ;
: sh-unrot ( wx wy -- lx ly ) 2dup sh-c sh@ * swap sh-s sh@ negate * + >r sh-s sh@ * swap sh-c sh@ * + r> ;
: sh-ease ( target cell rate -- ) tk-dt@ * 1 min >r dup >r sh@ - r> swap r> * over sh@ + swap sh! ;
\ Clips: B fades in over A; a new clip first makes the current one A.
: sh-cur ( -- id ) 27 sh@ dup 0 = if drop 25 sh@ then ;
: sh-play ( id fade -- ) over sh-cur = if 2drop exit then
  27 sh@ 0 <> if 27 sh@ 25 sh! 28 sh@ 26 sh! then 29 sh! 27 sh! sh-now 28 sh! ;
: sh-greet-clip sh-sex sh@ if sh-clip-greet-m else sh-clip-greet-f then ;
\ Spots: another visible seahorse holds or heads for spot n.
: sh-other ( n blk -- flag ) dup sh-b = if 2drop 0 exit then
  dup 40 + tk@ 0 = if 2drop 0 exit then 43 + tk@ = ;
: sh-taken ( n -- flag ) 0 sh-population 0 do over i sh-block sh-other | loop nip ;
: sh-ok ( n -- flag ) dup sh-spot# sh@ = over sh-taken |
  swap 2 < shg-phase tk@ 0 <> & | not ;
: sh-floor ( x -- n ) 0 sh-spot-count 1 do over i >= if 1 + then loop nip ;
: sh-pick ( -- n ) sh-greet sh@ if sh-sex sh@ exit then
  -1 sh-pk sh! sh-rand sh-spot-count * sh-floor sh-off sh!
  sh-spot-count 0 do
    i sh-off sh@ + dup sh-spot-count >= if sh-spot-count - then
    dup sh-ok if
      sh-pk sh@ 0 < if dup sh-pk sh! then
      dup sh-spot-post sh-spot# sh@ sh-spot-post <>
      sh-pk sh@ sh-spot-post sh-spot# sh@ sh-spot-post = & if dup sh-pk sh! then
    then drop
  loop sh-pk sh@ ;
: sh-load ( n -- ) dup sh-spot# sh! dup sh-spot sh-tyaw sh! sh-start sh! sh-r sh! sh-az sh! sh-ay sh! sh-ax sh!
  sh-spot-off sh-hz sh! sh-hy sh! sh-hx sh! sh-ey sh! sh-ex sh! ;
\ The approach target: the body position that puts the entry wrap centre on the axis, at
\ the held coil height. Uses the spot's yaw, then restores this frame's.
: sh-target sh-yaw sh@ >r sh-tyaw sh@ sh-yaw sh! sh-trig
  sh-ex sh@ sh-ey sh@ sh-rot sh-ay sh@ swap - sh-ty sh! sh-ax sh@ swap - sh-tx sh!
  sh-az sh@ sh-hz sh@ - sh-tz sh! r> sh-yaw sh! sh-trig ;
\ Contact solve, vertical post: move the body so the engine-reported wrap centre (cells
\ 33..35, body-local, one frame late) lies on the post axis. The centre is extrapolated
\ from the last two reports (cells 92..95), so a swaying body stays on the post. gain 1 is exact.
: sh-k ( -- k ) 95 sh@ if tk-dt@ 94 sh@ .001 max / 2 min else 0 then ;
: sh-pred ( -- cx cy ) sh-k >r 33 sh@ dup 92 sh@ - r@ * + 34 sh@ dup 93 sh@ - r> * + ;
: sh-solve ( gain -- ) sh-valid sh@ 0 = if drop exit then >r
  sh-pred sh-rot sh-ay sh@ swap - sh-y sh@ - r@ * sh-y sh@ + sh-y sh!
  sh-ax sh@ swap - sh-x sh@ - r> * sh-x sh@ + sh-x sh! ;
: sh-wrap-on 2 21 sh! sh-start sh@ 22 sh! sh-r sh@ 23 sh! ;
\ Seek and arrive (upright): cruise above the foliage until near the spot, then descend.
: sh-steer ( vmax -- )
  sh-tx sh@ sh-x sh@ - sh-wx sh! sh-ty sh@ sh-y sh@ - sh-wy sh!
  sh-wx sh@ sh-wy sh@ uf-hypot sh-dist sh!
  sh-tz sh@ sh-dist sh@ .6 > if sh-cruise-z max then sh-z sh@ - sh-wz sh!
  sh-dist sh@ sh-wz sh@ uf-hypot .0001 max dup .5 / 1 min rot * swap /
  dup sh-wx sh@ * sh-vx 1.2 sh-ease dup sh-wy sh@ * sh-vy 1.2 sh-ease sh-wz sh@ * sh-vz 1.2 sh-ease
  sh-x sh@ sh-vx sh@ tk-dt@ * + sh-x sh! sh-y sh@ sh-vy sh@ tk-dt@ * + sh-y sh!
  sh-z sh@ sh-vz sh@ tk-dt@ * + sh-z sh! ;
: sh-turn ( yaw -- err ) sh-yaw sh@ - tk-wrap dup tk-dt@ .15 * min tk-dt@ .15 * negate max
  sh-yaw sh@ + tk-frac sh-yaw sh! sh-trig ;
: sh-heading ( -- yaw ) sh-dist sh@ .5 < if sh-tyaw sh@ exit then
  sh-vx sh@ sh-vy sh@ uf-hypot .02 < if sh-yaw sh@ exit then sh-vy sh@ sh-vx sh@ tk-atan2 tk-frac ;
\ Transitions.
: sh-to-swim sh-next sh@ sh-load sh-target 0 21 sh! 0 24 sh! 0 sh-valid sh! sh-clip-swim .8 sh-play 2 sh-go ;
: sh-to-release sh-pick dup 0 < if drop 8 sh-rest sh! exit then sh-next sh! sh-next sh@ sh-spot# sh!
  sh-clip-release .3 sh-play 1 sh-go ;
: sh-to-probe sh-clip-probe .5 sh-play 3 sh-go ;
: sh-to-grasp sh-wrap-on 0 24 sh! 0 97 sh! sh-clip-hold-idle .6 sh-play 4 sh-go ;
: sh-to-hold 1 24 sh! sh-clip-hold-idle .8 sh-play 25 sh-rand 25 * + sh-rest sh! 0 sh-go ;
: sh-to-greet sh-greet-clip 2.5 sh-play 6 sh-go ;
\ A strike at an ambient particle: a one-frame head snap (cell 30), then a slow recovery.
\ Holding, only the head moves, so the coil stays put; swimming, the startle clip flicks the
\ whole body too. Cell 96 is the state to return to.
: sh-from 96 ;
: sh-to-strike 10 sh-rand 15 * + sh-strike sh! 24 sh-head sh! sh-state sh@ sh-from sh!
  sh-state sh@ 2 = if sh-clip-startle .08 sh-play then 5 sh-go ;
\ States.
: sh-hold sh-tyaw sh@ sh-now .13 * sh-b 300 / + tk-sin .008 * + tk-frac sh-yaw sh! sh-trig 1 sh-solve
  sh-rest sh@ tk-dt@ - sh-rest sh! sh-strike sh@ tk-dt@ - sh-strike sh!
  sh-greet sh@ if sh-spot# sh@ sh-sex sh@ = if sh-to-greet else sh-to-release then exit then
  sh-rest sh@ 0 <= if sh-to-release exit then
  sh-strike sh@ 0 <= if sh-to-strike then ;
: sh-release tk-dt@ 6 * 1 min sh-solve
  24 sh@ tk-dt@ 1.2 / - 0 max 24 sh! 24 sh@ 0 = if sh-to-swim then ;
: sh-swim sh-greet sh@ sh-spot# sh@ sh-sex sh@ <> & if sh-sex sh@ sh-next sh! sh-to-swim exit then
  sh-swim-speed sh-steer sh-heading sh-turn 50 * 8 min -8 max sh-rudder 2 sh-ease
  sh-strike sh@ tk-dt@ - sh-strike sh!
  sh-dist sh@ sh-z sh@ sh-tz sh@ - uf-hypot .12 < if sh-to-probe exit then
  sh-strike sh@ 0 <= sh-dist sh@ 1 > & if sh-to-strike then ;
\ The tail tip (cells 36..38) reaches for the post through the knot layer.
: sh-reach sh-ax sh@ sh-x sh@ - 36 sh@ 37 sh@ sh-rot >r - r> sh-ay sh@ sh-y sh@ - swap - sh-unrot
  ( lx ly ) 60 * 10 min -10 max sh-kl 3 sh-ease 60 * 10 min -8 max sh-kf 3 sh-ease ;
: sh-probe sh-swim-speed .3 * sh-steer sh-tyaw sh@ sh-turn drop 0 sh-rudder 2 sh-ease sh-reach
  sh-ax sh@ sh-x sh@ - 36 sh@ 37 sh@ sh-rot >r - r> sh-ay sh@ sh-y sh@ - swap - uf-hypot sh-r sh@ -
  .05 < sh-age sh@ .6 > & sh-age sh@ 2 > | if sh-to-grasp then ;
\ Grasp: the coil spreads from the tip. Progress eases in and out (cell 97 is the linear
\ ramp), so the coil stops smoothly and the solve's extrapolation does not overshoot.
: sh-grasp 24 sh@ 6 * 1 min sh-solve sh-tyaw sh@ sh-turn drop
  0 sh-kf 2 sh-ease 0 sh-kl 2 sh-ease 0 sh-vx 4 sh-ease 0 sh-vy 4 sh-ease 0 sh-vz 4 sh-ease
  sh-z sh@ sh-vz sh@ tk-dt@ * + sh-z sh!
  97 sh@ tk-dt@ 1.6 / + 1 min dup 97 sh! dup dup * swap 2 * 3 swap - * 24 sh! 97 sh@ 1 >= if
    sh-greet sh@ sh-spot# sh@ sh-sex sh@ = & if sh-to-greet else sh-to-hold then then ;
: sh-strike-step sh-from sh@ 2 = if
    sh-swim-speed .5 * sh-steer sh-age sh@ .5 > if sh-clip-swim .4 sh-play then
  else 1 sh-solve then
  sh-age sh@ 1.2 > if sh-from sh@ sh-go then ;
: sh-greet-step 1 sh-solve sh-greet sh@ 0 = if sh-to-hold then ;
\ Eyes: independent saccades through the transform channels; both look ahead in a strike.
: sh-eyes sh-eyet sh@ tk-dt@ - dup sh-eyet sh! 0 <= if
    sh-rand .5 - 50 * sh-eyel sh! sh-rand .5 - 50 * sh-eyer sh! .4 sh-rand 1.6 * + sh-eyet sh! then
  sh-state sh@ 5 = if 0 sh-eyel sh! 0 sh-eyer sh! then
  sh-eyel sh@ 31 sh@ - tk-dt@ 25 * 1 min * 31 sh@ + 31 sh!
  sh-eyer sh@ 32 sh@ - tk-dt@ 25 * 1 min * 32 sh@ + 32 sh! ;
\ Setup on entry (or when its pair reappears): holding its home spot (or a free one),
\ placed for hold_idle at t = 0 (sh-spot-off), so the first frame is already on the post;
\ the solve's history (cells 92..97 and 64) is seeded with the centre's velocity there (sh-spot-vel).
: sh-setup ( s -- ) dup .1373 * sh-seed sh!
  sh-home dup sh-taken if drop 0 sh-greet sh! -1 sh-spot# sh! sh-pick then sh-load
  sh-tyaw sh@ sh-yaw sh! sh-trig
  sh-hx sh@ sh-hy sh@ sh-rot sh-ay sh@ swap - sh-y sh! sh-ax sh@ swap - sh-x sh! sh-az sh@ sh-hz sh@ - sh-z sh!
  0 sh-vx sh! 0 sh-vy sh! 0 sh-vz sh! 0 sh-greet sh! 0 sh-valid sh! 0 sh-head sh! 0 sh-rudder sh!
  0 sh-kf sh! 0 sh-kl sh! 0 sh-eyet sh!
  21 0 do 0 i sh! loop sh-wrap-on 1 24 sh!
  sh-clip-hold-idle 25 sh! sh-now 26 sh! 0 27 sh! 0 28 sh! 0 29 sh! 0 30 sh!
  sh-hx sh@ 33 sh! sh-hy sh@ 34 sh! 1 sh-valid sh! 0 95 sh! 1 64 sh!
  sh-spot# sh@ sh-spot-vel tk-dt@ * sh-hy sh@ swap - 93 sh! tk-dt@ * sh-hx sh@ swap - 92 sh!
  sh-id sh@ sh-first-rest sh-rest sh! 6 sh-rand 15 * + sh-strike sh! 0 sh-go 1 sh-init sh! ;
\ The next solve trusts the reported wrap centre (sh-valid) only while progress x (35 - start)
\ >= 1, 35 being the tail's ring count: then the centre is a fully wrapped ring's. Below that
\ DFRM measures the half-wrapped tip ring, whose centre runs off as 1/progress near the end of a
\ release, and one solve on it threw the body out of the room (docs/diagnostics/seahorse-actor30-2026-10-18).
: sh-place ( actor -- ) >r sh-x sh@ INDEXOF_X_POS r@ write-actor-mailbox sh-y sh@ INDEXOF_Y_POS r@ write-actor-mailbox
  sh-z sh@ INDEXOF_Z_POS r@ write-actor-mailbox sh-yaw sh@ INDEXOF_ROTATION_C r> write-actor-mailbox ;
: sh-tick ( body fins sex s -- )
  dup sh-block sh-shared 9 + tk! dup sh-id sh! >r sh-sex sh! sh-fins sh! sh-body sh!
  sh-init sh@ 0 = if r@ sh-setup then r> drop
  sh-age sh@ tk-dt@ + sh-age sh! sh-trig
  sh-state sh@ dup 0 = if sh-hold else dup 1 = if sh-release else dup 2 = if sh-swim else
    dup 3 = if sh-probe else dup 4 = if sh-grasp else dup 5 = if sh-strike-step else sh-greet-step
  then then then then then then drop
  sh-state sh@ 3 <> if 0 sh-kf .8 sh-ease 0 sh-kl .8 sh-ease then
  sh-state sh@ 2 <> if 0 sh-rudder 1 sh-ease then
  sh-head sh@ dup tk-dt@ 3 * 1 min * - dup sh-head sh! 30 sh! sh-eyes
  sh-kf sh@ dup 12 sh! dup 15 sh! 18 sh!
  sh-kl sh@ sh-rudder sh@ + dup 13 sh! dup 16 sh! 19 sh!
  sh-body sh@ sh-place sh-fins sh@ sh-place
  64 sh@ if 0 64 sh! else 33 sh@ 92 sh! 34 sh@ 93 sh! then sh-valid sh@ 95 sh! tk-dt@ 94 sh!
  sh-b sh-body sh@ dfrm-pose drop
  24 sh@ 35 22 sh@ - * 1 >= 39 sh@ 1 <> & 39 sh@ 2 <> & sh-valid sh!
  sh-fin sh@ tk-dt@ 2.2 * sh-vx sh@ sh-vy sh@ uf-hypot 8 * 1 + * + tk-frac sh-fin sh!
  sh-fin sh@ .022 0 1 sh-fins sh@ fin-deform ;
\ Greeting (shared, once a frame before the seahorses): pair p's female and male take
\ spots 0 and 1, on opposite sides of the whip, for sh-greet-time seconds. Ours.
: shg-a shg-pair tk@ 2 * sh-block ;
: shg-m shg-pair tk@ 2 * 1 + sh-block ;
: shg-flag ( v -- ) dup shg-a 60 + tk! shg-m 60 + tk! ;
: shg-free ( blk -- flag ) dup 40 + tk@ 0 <> swap 41 + tk@ dup 0 = swap 2 = | & ;
: shg-clear ( blk -- ) sh-shared 9 + tk! sh-state sh@ 6 = if sh-clip-hold-idle 2.5 sh-play sh-to-hold
  4 sh-rand 8 * + sh-rest sh! 8 sh-rand 10 * + sh-strike sh! then ;
: shg-stop 0 shg-flag shg-a 40 + tk@ if shg-a shg-clear then shg-m 40 + tk@ if shg-m shg-clear then
  0 shg-phase tk! 0 shg-time tk! sh-now .0137 * tk-sin abs 120 * 240 + shg-due tk! ;
: shg-clearof ( blk -- flag ) dup 40 + tk@ 0 = swap 43 + tk@ 2 >= | ;
: shg-other-clear 1 sh-population 0 do
  i 2 / shg-pair tk@ <> if i sh-block shg-clearof & then loop ;
: shg-start shg-pair tk@ 1 + dup sh-count >= if drop 0 then shg-pair tk!
  shg-a shg-free shg-m shg-free & shg-other-clear &
  if 1 shg-flag 1 shg-phase tk! 0 shg-time tk! else 10 shg-due tk! then ;
: shg-tick 0 sh-vis tk@ not if 0 shg-ready tk! exit then
  shg-ready tk@ 0 = if 45 shg-due tk! 0 shg-phase tk! 1 shg-pair tk! 0 shg-flag 1 shg-ready tk! then
  shg-phase tk@ 0 <> shg-on tk@ 0 = shg-pair tk@ sh-vis tk@ 0 = | & if shg-stop exit then
  shg-phase tk@ 0 = if shg-on tk@ if shg-due tk@ tk-dt@ - dup shg-due tk! 0 <= if shg-start then then exit then
  shg-time tk@ tk-dt@ + shg-time tk!
  shg-phase tk@ 1 = if
    shg-a 41 + tk@ 6 = shg-m 41 + tk@ 6 = & if 2 shg-phase tk! 0 shg-time tk! exit then
    shg-time tk@ 180 > if shg-stop then exit then
  shg-time tk@ sh-greet-time >= if shg-stop then ;
\ Settings and visibility, every frame: pair n shows when saltwater and the count >= n.
: sh-settings sh-greeting shg-on tk!
  sh-pair-count 0 do
    pg-salt sh-count i > & dup i sh-vis tk!
    not if 0 i 2 * sh-block 40 + tk! 0 i 2 * 1 + sh-block 40 + tk! then
  loop 0 sh-vis tk@ not if 0 shg-ready tk! then ;
