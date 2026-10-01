\ school.fth - the aquarium's followers: the Couzin et al. (2002) zone model of collective motion, with the player's fish as a leader.
\
\ Couzin, Krause, James, Ruxton & Franks (2002), "Collective memory and spatial sorting in animal groups", J. Theor. Biol. 218:1-11, eqns 1-3:
\   each fish sees the others except in a blind volume behind it; REPULSION (highest priority): anyone within r_r -> turn away from them;
\   otherwise ORIENTATION (the mean heading of those in the next dro) and ATTRACTION (the direction to those in the next dra), averaged when
\   both are present; no neighbour -> keep the heading; then turn toward the wanted direction by at most (turn rate x dt) and swim at constant speed.
\ Moving dro (and dra) is what changes the group between a SWARM and a (highly) parallel SCHOOL: sch-regime blends the two sets of widths.
\
\ Ours, not from the paper: fish 0 is the LEADER (the player's fish, written from outside each tick); followers count it with weight MB_LEADW in
\ the orientation and attraction sums. Tank walls repel like a neighbour (MB_WALL). A STARTLE (the leader's dart) sends followers near the leader
\ straight away from it for MB_STARTLE_T seconds. The error term is left to the caller (a small per-fish wander written into the wanted direction).
\
\ Needs, in front of it (the level builder generates these; the tests supply them): read-mailbox write-mailbox, the fish trig words fish-sin and
\ fish-cos (clownfish_idle.fth), and the constants sch-base (mailbox of fish 0, field 0), sch-scr (25 scratch cells), sch-par (21 parameter cells),
\ sch-n (fish incl. the leader). Plan: docs/plans/2026-10-01-aquarium-schooling.md and docs/plans/2026-10-01-swarming-poster.md.
\
\ Mailboxes. Global user mailboxes are 2..1900, shared by every actor; the aquarium already uses 600..638 the player's fish, 700..719 the level,
\ 720..739 the sway, 740..759 the camera. This file: sch-base = 800 (11 fish x 14 = 800..953), sch-par = 960 (960..980), sch-scr = 985 (985..1009).
\ Every MB_ name below is a SLOT inside one of those three blocks, not a mailbox number: fish f's MB_X is mailbox sch-base + 14 f + MB_X.

\ ---- slots in a fish's 14 mailboxes (sch@ and sch!): a position, a unit heading, the next state of both, and the startle timer
: MB_X 0 ;   : MB_Y 1 ;   : MB_Z 2 ;
: MB_VX 3 ;  : MB_VY 4 ;  : MB_VZ 5 ;
: MB_NX 6 ;  : MB_NY 7 ;  : MB_NZ 8 ;       \ the next position
: MB_NVX 9 ; : MB_NVY 10 ; : MB_NVZ 11 ;    \ the next heading
: MB_STARTLE 12 ;                           \ seconds of startle left; slot 13 is unused

\ ---- slots in the 21 parameter cells (par@ and par!)
: MB_RR 0 ;         : MB_DRO 1 ;       : MB_DRA 2 ;
: MB_COSB 3 ;                              \ cos of the blind volume's half-angle
: MB_COST 4 ;       : MB_SINT 5 ;          \ cos and sin of the most a fish can turn in one tick
: MB_STEP 6 ;                              \ distance swum in one tick
: MB_LEADW 7 ;      : MB_WALL 8 ;      : MB_STARTLE_T 9 ;   : MB_DT 10 ;
: MB_LOX 11 ;       : MB_HIX 14 ;          \ the tank box: low x y z, then high x y z
: MB_DRO_SWARM 17 ; : MB_DRA_SWARM 18 ;  : MB_DRO_SCHOOL 19 ; : MB_DRA_SCHOOL 20 ;

\ ---- slots in the 25 scratch cells (sc@ and sc!); a vector is three cells in a row
: MB_SUM_R 0 ;  : MB_SUM_O 3 ;  : MB_SUM_A 6 ;       \ the repulsion, orientation and attraction sums
: MB_N_R 9 ;    : MB_N_O 10 ;   : MB_N_A 11 ;        \ how many neighbours in each zone
: MB_WANT 12 ;                                       \ the wanted direction, then the new heading
: MB_ME 15 ;    : MB_YOU 19 ;                        \ the follower being updated, the neighbour being looked at
: MB_U 16 ;                                          \ r = c_j - c_i, then the unit vector u = r / d
: MB_PERP 20 ;  : MB_DIST 23 ;  : MB_R2 24 ;         \ a perpendicular, d, and the startle radius squared

: sch-stride 14 ;
: sch-addr ( f i -- mb ) sch-stride * + sch-base + ;
: sch@ ( f i -- v ) sch-addr read-mailbox ;
: sch! ( v f i -- ) sch-addr write-mailbox ;
: sc@ ( k -- v ) sch-scr + read-mailbox ;
: sc! ( v k -- ) sch-scr + write-mailbox ;
: sc+! ( v k -- ) dup sc@ rot + swap sc! ;
: par@ ( k -- v ) sch-par + read-mailbox ;
: par! ( v k -- ) sch-par + write-mailbox ;
: me MB_ME sc@ ;

: sch-sqrt ( n -- r )
  dup 0.000001 > if
    dup 1 > if dup 2 / else 1 then
    6 0 do 2dup / + 2 / loop nip
  else drop 0 then ;
: vlen2 ( k -- n ) dup sc@ dup * over 1 + sc@ dup * + swap 2 + sc@ dup * + ;
: vscale ( f k -- )
  >r dup r@ sc@ * r@ sc!
  dup r@ 1 + sc@ * r@ 1 + sc!
  r@ 2 + sc@ * r> 2 + sc! ;
: vnorm ( k -- len )
  dup vlen2 sch-sqrt dup 0.000001 > if
    dup 1 swap / rot vscale
  else nip then ;
: vzero ( k -- ) 0 over sc! 0 over 1 + sc! 0 swap 2 + sc! ;
: vcopy ( from to -- ) >r dup sc@ r@ sc! dup 1 + sc@ r@ 1 + sc! 2 + sc@ r> 2 + sc! ;
: vadd ( from to -- ) >r dup sc@ r@ sc+! dup 1 + sc@ r@ 1 + sc+! 2 + sc@ r> 2 + sc+! ;
: heading>sc ( k -- )
  >r MB_VX me sch@ r@ sc!
  MB_VY me sch@ r@ 1 + sc!
  MB_VZ me sch@ r> 2 + sc! ;

\ ( w k -- ) add w times the unit vector u (attraction, repulsion) or the neighbour's heading (orientation) into the sum at k
: acc+u ( w k -- ) >r
  dup MB_U sc@ * r@ sc+!
  dup MB_U 1 + sc@ * r@ 1 + sc+!
  MB_U 2 + sc@ * r> 2 + sc+! ;
: acc+v ( w k -- ) >r
  dup MB_VX MB_YOU sc@ sch@ * r@ sc+!
  dup MB_VY MB_YOU sc@ sch@ * r@ 1 + sc+!
  MB_VZ MB_YOU sc@ sch@ * r> 2 + sc+! ;
: weight ( j -- w ) 0 = if MB_LEADW par@ else 1 then ;
: heading-dot-u ( -- c )
  MB_VX me sch@ MB_U sc@ *
  MB_VY me sch@ MB_U 1 + sc@ * +
  MB_VZ me sch@ MB_U 2 + sc@ * + ;

\ ( j -- ) one neighbour of the follower: r = c_j - c_i, d = |r|, u = r/d; ignored in the blind volume or outside every zone
: you-delta ( f k -- ) >r dup MB_YOU sc@ sch@ swap me sch@ - r> sc! ;   \ the neighbour's field f minus mine, into slot k
: reach2 ( -- n ) MB_RR par@ MB_DRO par@ + MB_DRA par@ + dup * ;
: r-rep ( -- r ) MB_RR par@ ;
: r-ori ( -- r ) r-rep MB_DRO par@ + ;
: inside ( r -- f ) MB_DIST sc@ > ;
: you-weight ( -- w ) MB_YOU sc@ weight ;
: count+ ( k -- ) 1 swap sc+! ;
: sch-pair ( j -- )
  MB_YOU sc!
  MB_X MB_U you-delta
  MB_Y MB_U 1 + you-delta
  MB_Z MB_U 2 + you-delta
  MB_U vlen2 dup 0.000001 >
  over reach2 < &                 \ 0 < d^2 < reach^2
  if
    sch-sqrt dup MB_DIST sc!
    1 swap / MB_U vscale
    heading-dot-u MB_COSB par@ >=
    if
      r-rep inside if
        -1 MB_SUM_R acc+u
        MB_N_R count+
      else r-ori inside if
        you-weight MB_SUM_O acc+v
        MB_N_O count+
      else
        you-weight MB_SUM_A acc+u
        MB_N_A count+
      then then
    then
  else drop then ;

\ the six walls repel like a neighbour: inside the wall zone, one more repulsion neighbour straight away from the wall
: sch-wall ( a -- ) >r
  r@ me sch@ r@ MB_LOX + par@ - MB_WALL par@ <
  if 1 r@ MB_SUM_R + sc+!  1 MB_N_R sc+! then
  r@ MB_HIX + par@ r@ me sch@ - MB_WALL par@ <
  if -1 r@ MB_SUM_R + sc+!  1 MB_N_R sc+! then
  r> drop ;
: sch-walls 0 sch-wall 1 sch-wall 2 sch-wall ;

\ the wanted direction, from the sums: repulsion if any, else orientation and attraction, else the old heading; unit length
: seen? ( k -- f ) sc@ 0 > ;
: add-wanted ( sum -- ) dup vnorm drop MB_WANT vadd ;
: sch-want
  MB_WANT vzero
  MB_N_R seen? if
    MB_SUM_R add-wanted
  else
    MB_N_O seen? if MB_SUM_O add-wanted then
    MB_N_A seen? if MB_SUM_A add-wanted then
  then
  MB_WANT vnorm 0.000001 > not if
    MB_WANT heading>sc
  then ;

\ a startled follower swims straight away from the leader for MB_STARTLE_T seconds
: sch-startle-away
  MB_X me sch@ MB_X 0 sch@ - MB_WANT sc!
  MB_Y me sch@ MB_Y 0 sch@ - MB_WANT 1 + sc!
  MB_Z me sch@ MB_Z 0 sch@ - MB_WANT 2 + sc!
  MB_WANT vnorm drop ;
: sch-startle? MB_STARTLE me sch@ 0 > ;
: sch-startle-tick MB_STARTLE me sch@ MB_DT par@ - 0 max MB_STARTLE me sch! ;
\ ( r -- ) every follower within r of the leader is kicked: the leader's dart
: sch-startle-all ( r -- )
  dup * MB_R2 sc!
  sch-n 1 do
    MB_X i sch@ MB_X 0 sch@ - dup *
    MB_Y i sch@ MB_Y 0 sch@ - dup * +
    MB_Z i sch@ MB_Z 0 sch@ - dup * +
    MB_R2 sc@ <
    if MB_STARTLE_T par@ MB_STARTLE i sch! then
  loop ;

\ turn the heading toward the wanted direction by at most the turn angle; the new unit heading is left in MB_WANT
: perp-axis ( dot a -- dot ) >r
  MB_WANT r@ + sc@  over MB_VX r@ + me sch@ *  -  MB_PERP r> + sc! ;
: turn-axis ( a -- ) >r
  MB_VX r@ + me sch@ MB_COST par@ *
  MB_PERP r@ + sc@ MB_SINT par@ * +
  MB_WANT r> + sc! ;
: perp-all ( dot -- ) 3 0 do i perp-axis loop drop ;
: turn-all 3 0 do i turn-axis loop ;
: perp-fallback                                   \ (anti)parallel: any perpendicular will do
  MB_VY me sch@ MB_PERP sc!
  MB_VX me sch@ negate MB_PERP 1 + sc!
  0 MB_PERP 2 + sc!
  MB_PERP vnorm 0.000001 > not if
    1 MB_PERP sc!
    0 MB_PERP 1 + sc!
  then ;
: sch-turn
  MB_VX me sch@ MB_WANT sc@ *
  MB_VY me sch@ MB_WANT 1 + sc@ * +
  MB_VZ me sch@ MB_WANT 2 + sc@ * +   \ cos of the angle left
  dup MB_COST par@ >= if drop else
    perp-all
    MB_PERP vnorm 0.000001 > not if
      perp-fallback
    then
    turn-all
    MB_WANT vnorm drop
  then ;

: advance ( a -- ) >r
  MB_X r@ + me sch@  MB_NVX r@ + me sch@ MB_STEP par@ * +
  MB_NX r> + me sch! ;

\ the walls are also a hard limit: a follower that would leave the box is put back on its edge and its heading reflected inward (a fish at 2 body lengths a
\ second cannot always turn within the wall zone, and one that left the tank was seen on the Chromecast)
: clamp-axis ( a -- ) >r
  MB_NX r@ + me sch@  r@ MB_LOX + par@  <
  if r@ MB_LOX + par@ MB_NX r@ + me sch!  MB_NVX r@ + me sch@ 0 < if MB_NVX r@ + me sch@ negate MB_NVX r@ + me sch! then then
  r@ MB_HIX + par@  MB_NX r@ + me sch@  <
  if r@ MB_HIX + par@ MB_NX r@ + me sch!  MB_NVX r@ + me sch@ 0 > if MB_NVX r@ + me sch@ negate MB_NVX r@ + me sch! then then
  r> drop ;
: clamp-all 0 clamp-axis 1 clamp-axis 2 clamp-axis ;
\ ( i -- ) one follower: scan the others, walls, startle, wanted direction, turn, move (into the next-state slots)
: clear-sums
  MB_SUM_R vzero
  MB_SUM_O vzero
  MB_SUM_A vzero
  0 MB_N_R sc!
  0 MB_N_O sc!
  0 MB_N_A sc! ;
: sch-follow
  MB_ME sc!
  clear-sums
  sch-n 0 do
    i me <> if i sch-pair then
  loop
  sch-walls sch-want
  sch-startle? if
    sch-startle-away
    sch-startle-tick
  then
  sch-turn
  MB_WANT sc@ MB_NVX me sch!
  MB_WANT 1 + sc@ MB_NVY me sch!
  MB_WANT 2 + sc@ MB_NVZ me sch!
  0 advance 1 advance 2 advance
  clamp-all ;
\ the next state becomes the state, for every follower at once (the leader, fish 0, is written from outside)
\ ( i -- ) one follower's next state becomes its state (the round robin commits as it goes)
: sch-commit1 ( i -- ) MB_ME sc! 6 0 do MB_NX i + me sch@ MB_X i + me sch! loop ;
: sch-commit
  sch-n 1 do
    i MB_ME sc!
    6 0 do MB_NX i + me sch@ MB_X i + me sch! loop
  loop ;

\ ( dt turn-deg-per-s speed -- ) the per-tick parameters: the turn's cos and sin (the engine's revolution sine) and the distance swum
: sch-set-dt >r over * 360 / dup fish-cos MB_COST par! fish-sin MB_SINT par!  dup r> * MB_STEP par!  MB_DT par! ;
\ ( s -- ) 0 = swarm, 1 = school: the zone widths are blended, the one change the paper shows moves a group between the states
: sch-regime >r
  MB_DRO_SWARM par@ MB_DRO_SCHOOL par@ MB_DRO_SWARM par@ - r@ * + MB_DRO par!
  MB_DRA_SWARM par@ MB_DRA_SCHOOL par@ MB_DRA_SWARM par@ - r> * + MB_DRA par! ;

\ ( -- ) the whole tick, after the caller has written the leader (fish 0) and the parameters
: sch-tick sch-n 1 do i sch-follow loop sch-commit ;
