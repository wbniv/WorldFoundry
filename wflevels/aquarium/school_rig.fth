\ school_rig.fth - the aquarium's ten followers: school.fth's Couzin model, the player's fish as the leader, and the clownfish rig posing each follower.
\ Plan: docs/plans/2026-10-01-aquarium-schooling.md. Entered once a tick from the Director, after the player's own fish-rig-tick (see blender_create_aquarium.py).
\
\ Generated in front of it by the level builder: sch-base sch-par sch-scr sch-n (school.fth's three mailbox blocks and the fish count including the leader),
\ sd-cx sd-cy sd-cz (the tank's centre, metres), sd-bl (one body length, metres), sd-hx sd-hy sd-hz (the half extents of the swim box, body lengths), and
\ sd-actors, which writes the 50 follower part-actor indices to mailboxes 1040..1089 (fish k, part j at 1040 + 5 (k - 1) + j).
\
\ Mailboxes this file owns (the aquarium also owns 600..638 the player's rig, 700..759 the level, sway and camera; school.fth 800..1009):
\   1015 set-up done   1016 fish-off (the rig's per-fish offset)   1017..1021 the part actors of the follower being posed   1022 round-robin phase
\   1023 swarm 0 .. school 1 blend   1024 mode   1025..1027 the leader's last position   1028..1030 its heading   1031 its speed
\   1032..1034 the position the rig reads for a follower   1040..1089 the part actor table   1100..1499 the followers' rig blocks, 40 each at 1100 + 40 (k - 1).
\
\ The followers are updated TWO a frame, round robin (a full step every five frames, 12 Hz); between updates the position is carried along the heading.
\ Every follower is posed every frame.

: sd-flag 1015 ;  : sd-off 1016 ;  : sd-slot 1017 ;  : sd-phase 1022 ;  : sd-blend 1023 ;  : sd-mode 1024 ;
: sd-prev 1025 ;  : sd-lhead 1028 ;  : sd-lspeed 1031 ;  : sd-px 1032 ;  : sd-py 1033 ;  : sd-pz 1034 ;  : sd-act 1040 ;
: sd-per 5 ;                                        \ frames in a full round-robin cycle: 10 followers / 2 a frame

\ ---- atan2 in revolutions (the rig's angle unit): atan(a) ~ a (pi/4 + 0.273 (1 - a)) for a in 0..1, error under 0.005 rad
: sd-oct ( a -- rev ) dup 1 swap - 0.04345 * 0.125 + * ;
: sd-atan2 ( y x -- rev )
  2dup abs swap abs + 0.000001 < if 2drop 0 else
    over abs over abs
    2dup > if swap / sd-oct 0.25 swap - else / sd-oct then
    over 0 < if 0.5 swap - then
    rot 0 < if negate then nip
  then ;
: sd-wrap ( d -- d' ) dup 0.5 > if 1 - then dup -0.5 < if 1 + then ;

\ ---- the leader: the player's fish, in body lengths from the tank centre
: sd-world>bl ( world centre -- bl ) - sd-bl / ;
: sd-leader
  INDEXOF_X_POS fish-actor-player read-actor-mailbox sd-cx sd-world>bl
  INDEXOF_Y_POS fish-actor-player read-actor-mailbox sd-cy sd-world>bl
  INDEXOF_Z_POS fish-actor-player read-actor-mailbox sd-cz sd-world>bl
  \ ( x y z ) the step since last tick, into MB_WANT's three cells
  dup sd-prev 2 + read-mailbox - MB_WANT 2 + sc!
  over sd-prev 1 + read-mailbox - MB_WANT 1 + sc!
  2 pick sd-prev read-mailbox - MB_WANT sc!
  MB_Z 0 sch! MB_Y 0 sch! MB_X 0 sch!
  MB_X 0 sch@ sd-prev write-mailbox  MB_Y 0 sch@ sd-prev 1 + write-mailbox  MB_Z 0 sch@ sd-prev 2 + write-mailbox
  MB_WANT vnorm                                       \ the distance moved this tick
  fish-dt / dup sd-lspeed write-mailbox               \ the speed, body lengths a second
  0.05 > if                                           \ moving: the heading is the step, unit length
    MB_WANT sc@ sd-lhead write-mailbox
    MB_WANT 1 + sc@ sd-lhead 1 + write-mailbox
    MB_WANT 2 + sc@ sd-lhead 2 + write-mailbox
  then
  sd-lhead read-mailbox MB_VX 0 sch!
  sd-lhead 1 + read-mailbox MB_VY 0 sch!
  sd-lhead 2 + read-mailbox MB_VZ 0 sch! ;

\ ---- the mode: school above 1.0 body lengths a second, swarm below 0.45 (a hysteresis), blended so it never snaps
: sd-mode-update
  sd-lspeed read-mailbox
  sd-mode read-mailbox 0 = if 1 > if 1 sd-mode write-mailbox then
  else 0.45 < if 0 sd-mode write-mailbox then then
  sd-mode read-mailbox sd-blend read-mailbox - 1.6 * fish-dt * sd-blend read-mailbox + dup sd-blend write-mailbox
  sch-regime ;

\ ---- one follower, one round-robin update: scan, turn, move, and commit (the others read the new state next frame)
: sd-update ( k -- ) dup sch-follow sch-commit1 ;
: sd-round-robin
  sd-phase read-mailbox
  dup 2 * 1 + sd-update
  2 * 2 + sd-update
  sd-phase read-mailbox 1 + sd-per mod sd-phase write-mailbox ;

\ ---- posing one follower k (1..10): its rig block, its five part actors, its world position, its heading
: sd-load ( k -- )                                  \ fish-off and the part-actor slots
  dup 1 - 40 * 500 + sd-off write-mailbox
  1 - 5 * sd-act +
  5 0 do dup i + read-mailbox sd-slot i + write-mailbox loop drop ;
: sd-cyc ( k -- c ) 1 - dup 2 mod - 2 / ;       \ the round-robin slot a follower is updated in: fish 1 and 2 in slot 0, 3 and 4 in slot 1 ...
: sd-frames ( -- e ) me sd-cyc sd-phase read-mailbox swap - 4 + sd-per mod ;   \ frames since this follower was last updated (0 if this frame)
: sd-pos ( a centre -- world )                      \ the follower's rendered position on axis a, carried along its heading since its last update
  MB_PERP 1 + sc!  MB_PERP sc!
  MB_X MB_PERP sc@ + me sch@
  MB_VX MB_PERP sc@ + me sch@ MB_STEP par@ *
  sd-frames sd-per / * +
  sd-bl * MB_PERP 1 + sc@ + ;
: sd-place
  0 sd-cx sd-pos sd-px write-mailbox
  1 sd-cy sd-pos sd-py write-mailbox
  2 sd-cz sd-pos sd-pz write-mailbox ;
: sd-aim                                            \ heading and pitch from the unit heading, eased
  MB_VY me sch@  MB_VX me sch@  sd-atan2
  fish-heading fish@ - sd-wrap fish-dt 8 * fish-clamp01 * fish-heading fish@ + sd-wrap fish-heading fish!
  MB_VZ me sch@ negate 0.16 *
  fish-pitch fish@ - fish-dt 8 * fish-clamp01 * fish-pitch fish@ + fish-pitch fish!
  2 sd-bl * fish-speed fish!  1 fish-burst fish!  0 fish-roll fish!  0 fish-brake fish!  0 fish-yaw-rate fish! ;
: sd-pose ( k -- )
  dup MB_ME sc! sd-load
  sd-place sd-aim
  fish-rig-tick ;
: sd-pose-all
  sch-n 1 do i sd-pose loop
  0 sd-off write-mailbox ;                          \ the player's own tick reads fish-off, and the Director's next frame starts with the player's rig

\ ---- first frame: the follower state, the school's parameters, the rig phases, the part actor table
: sd-fish ( k -- )
  MB_ME sc!
  me 5.5 - 1.1 * MB_X me sch!
  me 3 mod 1 - 0.8 * MB_Y me sch!
  me 4 mod 1.5 - 0.9 * MB_Z me sch!
  me 0.13 * fish-cos MB_VX me sch!
  0 MB_VY me sch!
  me 0.13 * fish-sin MB_VZ me sch!
  0 MB_STARTLE me sch!
  me 40 * 460 + sd-off write-mailbox                  \ the rig block's offset: 500 + 40 (k - 1)
  me 0.137 * fish-wrap fish-ph-bob fish!
  me 0.211 * fish-wrap fish-ph-tail fish!
  me 0.317 * fish-wrap fish-ph-pec fish!
  me 0.419 * fish-wrap fish-ph-dorsal fish!
  me 0.523 * fish-wrap fish-ph-swim fish!
  me 0.619 * fish-wrap fish-ph-sway fish!
  0 fish-w fish!  0 fish-tail-env fish! ;
: sd-prev-init                                      \ the leader's last position, so the first step is not a jump from the origin
  INDEXOF_X_POS fish-actor-player read-actor-mailbox sd-cx sd-world>bl sd-prev write-mailbox
  INDEXOF_Y_POS fish-actor-player read-actor-mailbox sd-cy sd-world>bl sd-prev 1 + write-mailbox
  INDEXOF_Z_POS fish-actor-player read-actor-mailbox sd-cz sd-world>bl sd-prev 2 + write-mailbox
  1 sd-lhead write-mailbox ;
: sd-setup
  1 MB_RR par!  5 MB_DRO par!  6 MB_DRA par!  -0.7071 MB_COSB par!
  3 MB_LEADW par!  0.6 MB_WALL par!  0.5 MB_STARTLE_T par!
  sd-hx negate MB_LOX par!  sd-hy negate MB_LOX 1 + par!  sd-hz negate MB_LOX 2 + par!
  sd-hx MB_HIX par!  sd-hy MB_HIX 1 + par!  sd-hz MB_HIX 2 + par!
  0.08333 120 2 sch-set-dt                            \ a follower's step is five frames of 1/60 s
  sd-prev-init
  sd-actors
  sch-n 1 do i sd-fish loop
  0 sd-off write-mailbox
  1 sd-flag write-mailbox ;

\ ---- the whole thing, once a tick
: sd-tick
  sd-flag read-mailbox 0 = if sd-setup then
  sd-leader sd-mode-update
  sd-round-robin
  sd-pose-all ;
