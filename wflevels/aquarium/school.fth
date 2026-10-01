\ school.fth - the aquarium's followers: the Couzin et al. (2002) zone model of collective motion, with the player's fish as a leader.
\
\ Couzin, Krause, James, Ruxton & Franks (2002), "Collective memory and spatial sorting in animal groups", J. Theor. Biol. 218:1-11, eqns 1-3:
\   each fish sees the others except in a blind volume behind it; REPULSION (highest priority): anyone within rr -> turn away from them;
\   otherwise ORIENTATION (the mean heading of those in the next dro) and ATTRACTION (the direction to those in the next dra), averaged when
\   both are present; no neighbour -> keep the heading; then turn toward the wanted direction by at most (turn rate x dt) and swim at constant speed.
\ Moving dro (and dra) is what changes the group between a SWARM and a (highly) parallel SCHOOL: sch-regime blends the two sets of widths.
\
\ Ours, not from the paper: fish 0 is the LEADER (the player's fish, written from outside each tick); followers count it with weight sch-wl in
\ the orientation and attraction sums. Tank walls repel like a neighbour (nr, dr). A STARTLE (the leader's dart) sends followers near the leader
\ straight away from it for sch-startle-time. The error term is left to the caller (a small per-fish wander written into the wanted direction).
\
\ Needs, in front of it (the level builder generates these; the tests supply them): read-mailbox write-mailbox, the fish trig words fish-sin and
\ fish-cos (clownfish_idle.fth), and the constants sch-base (mailbox of fish 0, field 0), sch-scr (25 scratch cells), sch-par (parameter cells), sch-n
\ (fish incl. the leader). Plan: docs/plans/2026-10-01-aquarium-schooling.md and docs/plans/2026-10-01-swarming-poster.md.
\
\ State per fish (14 mailboxes): 0 x, 1 y, 2 z, 3 vx, 4 vy, 5 vz (a UNIT heading), 6-8 next position, 9-11 next heading, 12 startle timer.
\ Parameter cells (sch-par + k): 0 rr, 1 dro, 2 dra, 3 cos(blind half-angle), 4 turn cos, 5 turn sin, 6 speed x dt, 7 leader weight, 8 wall zone,
\ 9 startle time, 10 dt, 11-13 box low x y z, 14-16 box high x y z, 17 dro swarm, 18 dra swarm, 19 dro school, 20 dra school.

: sch-stride 14 ;
: sch-addr ( f i -- mb ) sch-stride * + sch-base + ;
: sch@ ( f i -- v ) sch-addr read-mailbox ;
: sch! ( v f i -- ) sch-addr write-mailbox ;
: sc@ ( k -- v ) sch-scr + read-mailbox ;
: sc! ( v k -- ) sch-scr + write-mailbox ;
: sc+! ( v k -- ) dup sc@ rot + swap sc! ;
: par@ ( k -- v ) sch-par + read-mailbox ;
: par! ( v k -- ) sch-par + write-mailbox ;

\ scratch cells: 0-2 dr, 3-5 do, 6-8 da, 9 nr, 10 no, 11 na, 12-14 wanted, 15 the follower, 16-18 r then u, 19 the neighbour, 20-22 perp, 23 d, 24 startle radius^2
: cur 15 sc@ ;
: sch-sqrt ( n -- r ) dup 0.000001 > if dup 1 > if dup 2 / else 1 then 6 0 do 2dup / + 2 / loop nip else drop 0 then ;
: vlen2 ( k -- n ) dup sc@ dup * over 1 + sc@ dup * + swap 2 + sc@ dup * + ;
: vscale ( f k -- ) >r dup r@ sc@ * r@ sc! dup r@ 1 + sc@ * r@ 1 + sc! r@ 2 + sc@ * r> 2 + sc! ;
: vnorm ( k -- len ) dup vlen2 sch-sqrt dup 0.000001 > if dup 1 swap / rot vscale else nip then ;
: vzero ( k -- ) 0 over sc! 0 over 1 + sc! 0 swap 2 + sc! ;
: acc+u ( w k -- ) >r dup 16 sc@ * r@ sc+! dup 17 sc@ * r@ 1 + sc+! 18 sc@ * r> 2 + sc+! ;
: acc+v ( w k -- ) >r dup 3 19 sc@ sch@ * r@ sc+! dup 4 19 sc@ sch@ * r@ 1 + sc+! 5 19 sc@ sch@ * r> 2 + sc+! ;
: weight ( j -- w ) 0 = if 7 par@ else 1 then ;
: heading-dot-u ( -- c ) 3 cur sch@ 16 sc@ * 4 cur sch@ 17 sc@ * + 5 cur sch@ 18 sc@ * + ;

\ ( j -- ) one neighbour of the follower: r = c_j - c_i, d = |r|, u = r/d; ignored in the blind volume or outside every zone
: sch-pair
  dup 19 sc!
  0 over sch@ 0 cur sch@ - 16 sc!   1 over sch@ 1 cur sch@ - 17 sc!   2 swap sch@ 2 cur sch@ - 18 sc!
  16 vlen2 dup 0.000001 > over 1 par@ 0 par@ + 2 par@ + dup * < & if      \ 0 < d^2 < (rr+dro+dra)^2
    sch-sqrt dup 23 sc!  1 swap / 16 vscale
    heading-dot-u 3 par@ >= if
      23 sc@ 0 par@ < if
        -1 0 acc+u  1 9 sc+!
      else 23 sc@ 0 par@ 1 par@ + < if
        19 sc@ weight 3 acc+v  1 10 sc+!
      else
        19 sc@ weight 6 acc+u  1 11 sc+!
      then then
    then
  else drop then ;

\ the six walls repel like a neighbour: inside the wall zone, one more repulsion neighbour straight away from the wall
: sch-wall ( a -- ) >r
  r@ cur sch@ r@ 11 + par@ - 8 par@ < if 1 r@ sc+! 1 9 sc+! then
  r@ 14 + par@ r@ cur sch@ - 8 par@ < if -1 r@ sc+! 1 9 sc+! then r> drop ;
: sch-walls 0 sch-wall 1 sch-wall 2 sch-wall ;

\ wanted direction into 12-14 from the sums: repulsion if any, else orientation and attraction, else the heading; unit length
: sch-want
  12 vzero
  9 sc@ 0 > if 0 vnorm drop 0 sc@ 12 sc! 1 sc@ 13 sc! 2 sc@ 14 sc!
  else
    10 sc@ 0 > if 3 vnorm drop 3 sc@ 12 sc+! 4 sc@ 13 sc+! 5 sc@ 14 sc+! then
    11 sc@ 0 > if 6 vnorm drop 6 sc@ 12 sc+! 7 sc@ 13 sc+! 8 sc@ 14 sc+! then
  then
  12 vnorm 0.000001 > not if 3 cur sch@ 12 sc! 4 cur sch@ 13 sc! 5 cur sch@ 14 sc! then ;

\ a startled follower swims straight away from the leader for sch-startle-time
: sch-startle-away
  0 cur sch@ 0 0 sch@ - 12 sc!  1 cur sch@ 1 0 sch@ - 13 sc!  2 cur sch@ 2 0 sch@ - 14 sc!  12 vnorm drop ;
: sch-startle?  12 cur sch@ 0 > ;
: sch-startle-tick  12 cur sch@ 10 par@ - 0 max 12 cur sch! ;
\ ( -- ) every follower within r of the leader is kicked: the leader's dart
: sch-startle-all ( r -- ) dup * 24 sc! sch-n 1 do
    0 i sch@ 0 0 sch@ - dup * 1 i sch@ 1 0 sch@ - dup * + 2 i sch@ 2 0 sch@ - dup * + 24 sc@ <
    if 9 par@ 12 i sch! then loop ;

\ turn the heading toward the wanted direction (12-14) by at most the turn angle; the new unit heading is left in 12-14
: sch-turn
  3 cur sch@ 12 sc@ * 4 cur sch@ 13 sc@ * + 5 cur sch@ 14 sc@ * + dup 4 par@ >= if
    drop
  else
    >r
    12 sc@ r@ 3 cur sch@ * - 20 sc!   13 sc@ r@ 4 cur sch@ * - 21 sc!   14 sc@ r> 5 cur sch@ * - 22 sc!
    20 vnorm 0.000001 > not if 4 cur sch@ 20 sc!  3 cur sch@ negate 21 sc!  0 22 sc! 20 vnorm 0.000001 > not if 1 20 sc! 0 21 sc! then then
    3 cur sch@ 4 par@ * 20 sc@ 5 par@ * + 12 sc!
    4 cur sch@ 4 par@ * 21 sc@ 5 par@ * + 13 sc!
    5 cur sch@ 4 par@ * 22 sc@ 5 par@ * + 14 sc!
    12 vnorm drop
  then ;

\ ( i -- ) one follower: scan the others, walls, startle, wanted direction, turn, move (into the next-state fields)
: sch-follow
  15 sc!  0 vzero 3 vzero 6 vzero 0 9 sc! 0 10 sc! 0 11 sc!
  sch-n 0 do i cur <> if i sch-pair then loop
  sch-walls sch-want
  sch-startle? if sch-startle-away sch-startle-tick then
  sch-turn
  12 sc@ 9 cur sch!  13 sc@ 10 cur sch!  14 sc@ 11 cur sch!
  0 cur sch@ 9 cur sch@ 6 par@ * + 6 cur sch!
  1 cur sch@ 10 cur sch@ 6 par@ * + 7 cur sch!
  2 cur sch@ 11 cur sch@ 6 par@ * + 8 cur sch! ;
: sch-commit sch-n 1 do 6 i sch@ 0 i sch!  7 i sch@ 1 i sch!  8 i sch@ 2 i sch!  9 i sch@ 3 i sch!  10 i sch@ 4 i sch!  11 i sch@ 5 i sch! loop ;

\ ( dt -- ) the per-tick parameters from dt: turn cos/sin from the turn rate (degrees per second) via the engine's revolution sine
: sch-set-dt ( dt turn-deg-per-s speed -- ) >r over * 360 / dup fish-cos 4 par! fish-sin 5 par! dup r> * 6 par! 10 par! ;
\ ( s -- ) 0 = swarm, 1 = school: the zone widths are blended, the one change the paper shows moves a group between the states
: sch-regime ( s -- ) >r 17 par@ 19 par@ 17 par@ - r@ * + 1 par!  18 par@ 20 par@ 18 par@ - r> * + 2 par! ;

\ ( -- ) the whole tick, after the caller has written the leader (fish 0) and the parameters
: sch-tick sch-n 1 do i sch-follow loop sch-commit ;
