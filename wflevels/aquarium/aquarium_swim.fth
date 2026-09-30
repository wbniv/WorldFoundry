\ aquarium_swim.fth - the aquarium level's swim controller and camera zones.
\
\ Needs, in front of it: the clownfish constants header + clownfish_idle.fth
\ (fish@ fish! fish-dt fish-turn fish-idle-sense fish-swim-speed ...) and the
\ aquarium header that blender_create_aquarium.py generates (aq-touch, the
\ clamps aq-xmax aq-ymax aq-zmin aq-zmax, the dart, the zone, the camshot and
\ LookB actor indices, and the mailboxes aq-prev ... 700..719).
\
\ Entry points (one per script; the zForth host compiles everything up to the
\ last `;` once and runs only the text after it every tick):
\   aq-player-tick     the Physics Player's script. Replaces fish-swim-tick.
\   aq-camera-tick     the Director's script, after fish-rig-tick.
\   aq-sway-tick       the Director's script, after aq-camera-tick (Phase 4;
\                      generated after this file, one aq-sway-clump per clump;
\                      its mailboxes are 720..739).
\
\ Swim rules (aquarium plan Phase 1, measured): while a direction is held write
\ +-fish-swim-speed to that axis; write nothing on release, so the air drag
\ glides the fish; INPUT 0 every tick; never write ROTATION_C on the Player
\ (the rig owns the visual heading via fish-heading-target). The level owns
\ the clamps: they write the axis speed 0 and the position to the limit.
\ Plan: docs/plans/2026-09-30-aquarium-level.md (Phase 3)

: aq-joy INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox ;
\ ( bit -- 0|1 ) held this tick
: aq-held aq-joy & 0 <> if 1 else 0 then ;
\ ( bit -- 0|1 ) pressed this tick (held now, not last tick)
: aq-edge dup aq-held swap aq-prev fish@ & 0 <> if drop 0 then ;

\ ---- input -> aq-dx / aq-dy / aq-dz (-1/0/1) and a dart request ----------
\ Keyboard / gamepad: arrows swim X/Z, B (2) / C (3) held swim toward / away
\ from the glass (Y), A (1) darts.
: aq-read-keys
  JOYSTICK_BUTTON_RIGHT aq-held JOYSTICK_BUTTON_LEFT aq-held - aq-dx fish!
  JOYSTICK_BUTTON_UP aq-held JOYSTICK_BUTTON_DOWN aq-held - aq-dz fish!
  JOYSTICK_BUTTON_C aq-held JOYSTICK_BUTTON_B aq-held - aq-dy fish!
  JOYSTICK_BUTTON_A aq-edge aq-dart-req fish! ;
\ Touch (phone landscape: a D-pad plus A and B only): A cycles Swim -> Depth,
\ B darts. Swim mode: D-pad up/down = Z. Depth mode: up = away from the glass
\ (+Y), down = toward it. Left/right swim X in both modes.
: aq-read-touch
  JOYSTICK_BUTTON_A aq-edge if 1 aq-mode fish@ - aq-mode fish! then
  JOYSTICK_BUTTON_RIGHT aq-held JOYSTICK_BUTTON_LEFT aq-held - aq-dx fish!
  JOYSTICK_BUTTON_UP aq-held JOYSTICK_BUTTON_DOWN aq-held -
  aq-mode fish@ if aq-dy fish! 0 aq-dz fish! else aq-dz fish! 0 aq-dy fish! then
  JOYSTICK_BUTTON_B aq-edge aq-dart-req fish! ;

\ ( dir spdmb -- ) write +-swim speed to an axis while its direction is held
: aq-drive over 0 <> if swap fish-swim-speed * swap write-mailbox else 2drop then ;

\ ( -- ) dart: a burst of aq-dart-v along the facing for aq-dart-time, then
\ nothing is written and the air drag glides it out.
: aq-dart
  aq-dart-req fish@ if aq-dart-time aq-dart-t fish! then
  aq-dart-t fish@ 0 > if
    fish-heading-target fish@ 0 < if aq-dart-v negate else aq-dart-v then
    INDEXOF_XSPEED write-mailbox
    aq-dart-t fish@ fish-dt - aq-dart-t fish!
  then ;

\ ( lim posmb spdmb -- ) clamp an axis from above / from below. Positions are
\ 16.16 fixed point, so a position written at the limit reads back up to one
\ LSB beyond it: the 1 mm tolerance stops a clamp firing on every tick at its
\ own limit (which zeroed the speed, so the fish could never leave the floor).
: aq-clamp-hi >r over 0.001 + over read-mailbox < if 0 r> write-mailbox write-mailbox
  else r> drop 2drop then ;
: aq-clamp-lo >r over 0.001 - over read-mailbox > if 0 r> write-mailbox write-mailbox
  else r> drop 2drop then ;

\ ( spdmb prevmb -- ) the script is the fish's only motor: physics may slow an
\ axis (drag, a wall) but never speed it up. The Jolt character is a walker
\ (walk-stairs step-up 0.4 m, slopes up to 80 deg count as floor) and its
\ velocity is inferred from its position change, so brushing the rock or a bulb
\ stair-stepped it and launched it at 7 m/s. An axis now faster than the script
\ left it last tick is put back to that speed.
: aq-no-kick over read-mailbox abs over fish@ abs 0.001 + >
  if fish@ swap write-mailbox else 2drop then ;
: aq-no-kicks
  INDEXOF_XSPEED aq-vx aq-no-kick INDEXOF_YSPEED aq-vy aq-no-kick
  INDEXOF_ZSPEED aq-vz aq-no-kick ;
: aq-remember
  INDEXOF_XSPEED read-mailbox aq-vx fish! INDEXOF_YSPEED read-mailbox aq-vy fish!
  INDEXOF_ZSPEED read-mailbox aq-vz fish! ;
: aq-clamps
  aq-xmax INDEXOF_X_POS INDEXOF_XSPEED aq-clamp-hi
  aq-xmax negate INDEXOF_X_POS INDEXOF_XSPEED aq-clamp-lo
  aq-ymax INDEXOF_Y_POS INDEXOF_YSPEED aq-clamp-hi
  aq-ymax negate INDEXOF_Y_POS INDEXOF_YSPEED aq-clamp-lo
  aq-zmax INDEXOF_Z_POS INDEXOF_ZSPEED aq-clamp-hi
  aq-zmin INDEXOF_Z_POS INDEXOF_ZSPEED aq-clamp-lo ;

: aq-player-tick
  0 INDEXOF_INPUT write-mailbox
  aq-no-kicks
  aq-touch if aq-read-touch else aq-read-keys then
  aq-dx fish@ INDEXOF_XSPEED aq-drive
  aq-dy fish@ INDEXOF_YSPEED aq-drive
  aq-dz fish@ INDEXOF_ZSPEED aq-drive
  aq-dx fish@ 0 > if 0 fish-heading-target fish! then
  aq-dx fish@ 0 < if -0.5 fish-heading-target fish! then
  aq-dart fish-turn aq-clamps aq-remember
  aq-joy aq-prev fish!
  aq-dx fish@ 0 <> aq-dy fish@ 0 <> | aq-dz fish@ 0 <> | aq-dart-t fish@ 0 > |
  aq-dart-req fish@ 0 <> | fish-idle-sense ;

\ ---- Director: camera zones --------------------------------------------
\ Camshot B (anemone close-up) while the Player is within aq-zone-in of the
\ zone centre; back to A only once it is past aq-zone-out (hysteresis, so the
\ shot cannot flicker at the boundary). Bungee mode never clears CAMSHOT, so
\ it is written every tick.
: aq-sq dup * ;
: aq-player@ fish-actor-player read-actor-mailbox ;
: aq-zone-d2
  INDEXOF_X_POS aq-player@ aq-zone-x - aq-sq
  INDEXOF_Y_POS aq-player@ aq-zone-y - aq-sq +
  INDEXOF_Z_POS aq-player@ aq-zone-z - aq-sq + ;
\ LookB (camshot B's aim) leans a share of the way from the anemone toward the
\ fish, so a fish at the zone's edge stays in frame. ( base posmb -- )
: aq-look-axis >r r@ aq-player@ over - aq-look-follow * +
  r> aq-look-b write-actor-mailbox ;
: aq-camera-tick
  aq-zone-d2 aq-in-b fish@
  if aq-zone-out aq-sq > if 0 aq-in-b fish! then
  else aq-zone-in aq-sq < if 1 aq-in-b fish! then then
  aq-in-b fish@ if aq-shot-b else aq-shot-a then INDEXOF_CAMSHOT write-mailbox
  aq-look-b-x INDEXOF_X_POS aq-look-axis
  aq-look-b-z INDEXOF_Z_POS aq-look-axis ;

\ ---- Director: anemone sway (Phase 4) -----------------------------------
\ Each tentacle clump is a Mass-0 anchored platform whose origin is its base on
\ the oral disc; rotating it swings it about that base. Purely visual: it
\ writes only the clumps' ROTATION_A/B/C, never a position, a speed or the
\ Player. The generated aq-sway-tick calls aq-sway-clump once per clump with
\ its amplitudes (rev), phase offset (rev), frequency (Hz), phase mailbox
\ (720..) and actor index. Time is the rig's: a phase accumulator advanced by
\ INDEXOF_DELTA_TIME (fish-dt), wrapped into [0,1), like fish-advance.
\ ( offset hz phmb -- phase ) advance the accumulator; phase = accumulator + offset
: aq-sway-phase dup >r fish@ swap fish-dt * + fish-wrap dup r> fish! + ;
\ ( amp-a amp-b phase actor -- ) B = amp-b sin(phase) sways the clump in the
\ X-Z plane; A = amp-a sin(phase + 1/4) leans it toward / away from the glass.
\ A, then B, then C, every time: only the C write applies all three.
: aq-sway-pose >r
  dup fish-sin rot * aq-sway-b fish!
  0.25 + fish-sin * INDEXOF_ROTATION_A r@ write-actor-mailbox
  aq-sway-b fish@ INDEXOF_ROTATION_B r@ write-actor-mailbox
  0 INDEXOF_ROTATION_C r> write-actor-mailbox ;
\ ( amp-a amp-b offset hz phmb actor -- )
: aq-sway-clump >r aq-sway-phase r> aq-sway-pose ;
