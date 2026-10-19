\ aquarium_swim.fth - the aquarium level's swim controller, camera zones and anemone sway.
\
\ Needs, in front of it: the clownfish constants header + clownfish_idle.fth
\ (fish@ fish! fish-dt fish-sin fish-cos fish-clampabs fish-clamp01 fish-idle-sense
\ and the rig's input mailboxes fish-heading/-pitch/-roll/-yaw-rate/-speed/-burst/
\ -brake) and the aquarium header that blender_create_aquarium.py generates (aq-*
\ constants: the gait, the steering, the tank limits, the fish's box, the zone,
\ the camshot and LookB actor indices; mailboxes 700..719 and 740..759).
\
\ Entry points (one per script; the zForth host compiles everything up to the
\ last `;` once and runs only the text after it every tick):
\   aq-player-tick     the Physics Player's script (replaces fish-swim-tick).
\   aq-camera-tick     the Director's script, after fish-rig-tick.
\   aq-sway-tick       the Director's script, after aq-camera-tick (generated
\                      after this file, one aq-sway-clump per clump; 720..739).
\
\ STEER AND SWIM (Phase 4; replaces Phase 1's "write +-V to the held axis").
\ A fish only ever moves along the way it faces. The held buttons give a
\ desired direction; the fish turns toward it (yaw and pitch are spring-dampers,
\ pitch slower than yaw, a bank proportional to the yaw rate) and swims along
\ its CURRENT facing: every tick the script writes speed x facing to X/Y/ZSPEED,
\ and nothing else ever writes a velocity. So a reversal is a U-turn arc, and
\ Up alone climbs forward at the pitch limit. The speed is burst-and-coast:
\ a constant cycle (aq-cycle), a burst toward aq-burst-v for aq-duty of it, then
\ a coast (Li et al. 2021: fish keep the cycle and change the burst share; Wu,
\ Yang & Zeng 2007: burst-and-coast). Released, the fish glides to a stop along
\ its facing with its pectorals flared (the brake) and its pitch levels.
\ The Player's air drag is 0: the script owns the speed. Nobody writes the
\ Player's ROTATION_*: the rig poses the visible parts from fish-heading etc.
\ Walls: the visible fish's box (nose, tail, fins, dorsal, belly) is turned
\ with the facing each tick, which gives six limits for the body origin. The
\ speed is capped at (distance ahead to a limit) / aq-tau-wall, so the fish
\ eases to a stop facing a wall; a turn that swings the tail or nose past a
\ limit moves the body back inside (a "push", flagged in aq-pushed). The
\ pitch flattens near the sand and the surface, so a dive levels out.
\ Plan: docs/plans/2026-09-30-aquarium-level.md (Phase 3; Phase 4 steer-and-swim)

: aq-joy INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox ;
\ ( bit -- 0|1 ) held this tick
: aq-held aq-joy & 0 <> if 1 else 0 then ;
\ ( bit -- 0|1 ) pressed this tick (held now, not last tick)
: aq-edge dup aq-held swap aq-prev fish@ & 0 <> if drop 0 then ;

\ ---- input -> aq-dx / aq-dy / aq-dz (-1/0/1) and a dart request ----------
\ Keyboard / gamepad: arrows = x (left/right) and z (up/down), B (2) / C (3)
\ held = y (toward / away from the glass), A (1) darts.
: aq-read-keys
  JOYSTICK_BUTTON_RIGHT aq-held JOYSTICK_BUTTON_LEFT aq-held - aq-dx fish!
  JOYSTICK_BUTTON_UP aq-held JOYSTICK_BUTTON_DOWN aq-held - aq-dz fish!
  JOYSTICK_BUTTON_C aq-held JOYSTICK_BUTTON_B aq-held - aq-dy fish!
  JOYSTICK_BUTTON_A aq-edge aq-dart-req fish! ;
\ Touch (phone landscape: a D-pad plus A and B only): A cycles Swim -> Depth,
\ B darts. Swim mode: D-pad up/down = z. Depth mode: up = away from the glass
\ (+y), down = toward it. Left/right = x in both modes. Same steering.
: aq-read-touch
  JOYSTICK_BUTTON_A aq-edge if 1 aq-mode fish@ - aq-mode fish! then
  JOYSTICK_BUTTON_RIGHT aq-held JOYSTICK_BUTTON_LEFT aq-held - aq-dx fish!
  JOYSTICK_BUTTON_UP aq-held JOYSTICK_BUTTON_DOWN aq-held -
  aq-mode fish@ if aq-dy fish! 0 aq-dz fish! else aq-dz fish! 0 aq-dy fish! then
  JOYSTICK_BUTTON_B aq-edge aq-dart-req fish! ;

: aq-hor? aq-dx fish@ 0 <> aq-dy fish@ 0 <> | ;
: aq-any? aq-hor? aq-dz fish@ 0 <> | ;

\ ( -- ) dart: an A tap starts a burst of aq-dart-time toward aq-dart-v along
\ the facing (aq-gait), then the glide.
: aq-dart
  aq-dart-req fish@ if aq-dart-time aq-dart-t fish! then
  aq-dart-t fish@ 0 > if aq-dart-t fish@ fish-dt - aq-dart-t fish! then ;
: aq-darting? aq-dart-t fish@ 0 > aq-dart-req fish@ 0 <> | ;

\ ( spdmb prevmb -- ) physics may slow an axis (a contact) but never speed it
\ up: an axis faster than the script left it is put back (Phase 3). The steer-
\ and-swim write below replaces the velocity anyway; this only guards a kick
\ between the two.
: aq-no-kick over read-mailbox abs over fish@ abs 0.001 + >
  if fish@ swap write-mailbox else 2drop then ;
: aq-no-kicks
  INDEXOF_XSPEED aq-vx aq-no-kick INDEXOF_YSPEED aq-vy aq-no-kick
  INDEXOF_ZSPEED aq-vz aq-no-kick ;
: aq-remember
  INDEXOF_XSPEED read-mailbox aq-vx fish! INDEXOF_YSPEED read-mailbox aq-vy fish!
  INDEXOF_ZSPEED read-mailbox aq-vz fish! ;

\ ---- the facing and the visible fish's turned box -------------------------
\ Player-side scratch: the rig's trig cells (the Director recomputes them in
\ fish-channels before it uses them, after this script has run).
: aq-sy fish-sc ;  : aq-cy fish-cc ;  : aq-sp fish-sb ;  : aq-cp fish-cb ;  : aq-sr fish-sa ;
: aq-sy@ aq-sy fish@ ;  : aq-cy@ aq-cy fish@ ;  : aq-sp@ aq-sp fish@ ;  : aq-cp@ aq-cp fish@ ;
: aq-fx@ aq-fx fish@ ;  : aq-fy@ aq-fy fish@ ;  : aq-fz@ aq-fz fish@ ;
\ yaw psi, elevation theta (nose up +): facing f = (cos t cos p, cos t sin p, sin t)
: aq-trig
  aq-yaw fish@ fish-sin aq-sy fish!  aq-yaw fish@ fish-cos aq-cy fish!
  aq-pitch fish@ fish-sin aq-sp fish!  aq-pitch fish@ fish-cos aq-cp fish!
  aq-roll fish@ fish-sin abs aq-sr fish!
  aq-cp@ aq-cy@ * aq-fx fish!  aq-cp@ aq-sy@ * aq-fy fish!  aq-sp@ aq-fz fish! ;
\ the box's local half-sizes, widened by the bank (it tips y into z and back)
: aq-hy2 aq-box-hy aq-sr fish@ aq-box-hz * + ;
: aq-hz2 aq-box-hz aq-sr fish@ aq-box-hy * + ;
\ world half extents: |R| times the local half-sizes. Local x = f, local y =
\ (-sin p, cos p, 0), local z = (-sin t cos p, -sin t sin p, cos t).
: aq-hxw aq-fx@ abs aq-box-hx * aq-sy@ abs aq-hy2 * + aq-sp@ aq-cy@ * abs aq-hz2 * + ;
: aq-hyw aq-fy@ abs aq-box-hx * aq-cy@ abs aq-hy2 * + aq-sp@ aq-sy@ * abs aq-hz2 * + ;
: aq-hzw aq-sp@ abs aq-box-hx * aq-cp@ aq-hz2 * + ;
\ the box centre's offset from the body origin (the tail is longer than the head)
: aq-cox aq-box-cx aq-fx@ * aq-box-cz aq-sp@ * aq-cy@ * - ;
: aq-coy aq-box-cx aq-fy@ * aq-box-cz aq-sp@ * aq-sy@ * - ;
: aq-coz aq-box-cx aq-fz@ * aq-box-cz aq-cp@ * + ;
\ six limits for the body origin (aq-ix/iy = inner faces less the margin;
\ aq-zlo/zhi = sand and water line with the margin; aq-zmin keeps the capsule
\ clear of the sand so Jolt never treats the fish as standing, Phase 3)
: aq-limits
  aq-ix aq-hxw - dup aq-cox - aq-hix fish!  negate aq-cox - aq-lox fish!
  aq-iy aq-hyw - dup aq-coy - aq-hiy fish!  negate aq-coy - aq-loy fish!
  aq-zhi aq-hzw - aq-coz - aq-hiz fish!
  aq-zlo aq-hzw + aq-coz - aq-zmin max aq-loz fish! ;
\ ( lo hi posmb -- ) keep the body origin inside [lo, hi]; a correction is a push.
\ 1 mm tolerance: positions are 16.16 fixed point (Phase 3).
: aq-keep >r r@ read-mailbox min max
  dup r@ read-mailbox - abs 0.001 > if r@ write-mailbox 1 aq-pushed fish! else drop then r> drop ;
: aq-keeps
  aq-lox fish@ aq-hix fish@ INDEXOF_X_POS aq-keep
  aq-loy fish@ aq-hiy fish@ INDEXOF_Y_POS aq-keep
  aq-loz fish@ aq-hiz fish@ INDEXOF_Z_POS aq-keep ;
\ ( lo hi posmb f -- ) lower aq-cap to (distance along the facing to this axis's
\ limit) / aq-tau-wall: the fish eases to a stop instead of hitting a clamp.
: aq-cap1 aq-t1 fish! read-mailbox >r
  aq-t1 fish@ 0.01 > if nip r@ - aq-t1 fish@ /
  else aq-t1 fish@ -0.01 < if drop r@ - aq-t1 fish@ / else 2drop 1000 then then
  r> drop 0 max aq-tau-wall / aq-cap fish@ min aq-cap fish! ;
: aq-caps 1000 aq-cap fish!
  aq-lox fish@ aq-hix fish@ INDEXOF_X_POS aq-fx@ aq-cap1
  aq-loy fish@ aq-hiy fish@ INDEXOF_Y_POS aq-fy@ aq-cap1
  aq-loz fish@ aq-hiz fish@ INDEXOF_Z_POS aq-fz@ aq-cap1 ;

\ ---- steering: target facing, then spring-damper turns --------------------
: aq-wrap-h dup 0.5 >= if 1 - then dup -0.5 < if 1 + then ;
\ ( -- yaw ) the held horizontal direction (8 of them), rev: 0 = +x, 0.25 = +y
: aq-yaw-of-input
  aq-dx fish@ 0 = if 0.25 aq-dy fish@ *
  else aq-dx fish@ 0 > if 0.125 aq-dy fish@ *
  else aq-dy fish@ 0 = if 0.5 else 0.375 aq-dy fish@ * then then then ;
\ ( -- ) near the sand or the surface the wanted pitch flattens (a dive levels
\ out); aq-flat keeps the factor so a pure Up/Down at a limit does not swim on.
: aq-flatten
  aq-pitch-t fish@ 0 > if aq-hiz fish@ INDEXOF_Z_POS read-mailbox -
  else INDEXOF_Z_POS read-mailbox aq-loz fish@ - then
  aq-flatten-d / fish-clamp01 dup aq-flat fish! aq-pitch-t fish@ * aq-pitch-t fish! ;
\ Up or Down alone while facing a wall (last tick's room ahead left less than
\ 0.3 V): the fish can only climb by swimming forward, so it turns a quarter
\ turn toward the tank's centre, along the wall, and climbs away from it. It
\ stops turning as soon as it has room. ( -- +1|-1 ) is the side whose quarter
\ turn points more toward the centre: the facing turned +1/4 is (-sin, cos),
\ and its dot with (-x, -y) is x sin - y cos.
: aq-blocked? aq-cap fish@ aq-v 0.3 * < ;
: aq-centre-side
  INDEXOF_X_POS read-mailbox aq-yaw fish@ fish-sin *
  INDEXOF_Y_POS read-mailbox aq-yaw fish@ fish-cos * - 0 < if -1 else 1 then ;
\ Input sets the target facing; no input keeps the yaw and levels the pitch.
: aq-targets
  aq-hor? if aq-yaw-of-input
  else aq-dz fish@ 0 <> aq-blocked? & if aq-yaw fish@ 0.25 aq-centre-side * + aq-wrap-h
  else aq-yaw fish@ then then aq-yaw-t fish!
  aq-dz fish@ aq-hor? if aq-pitch-diag else aq-pitch-max then * aq-pitch-t fish!
  1 aq-flat fish! aq-pitch-t fish@ 0 <> if aq-flatten then ;
\ ( err -- err' ) a reversal (|err| near half a turn) turns toward the tank's
\ centre line: through +y when in front of it, through -y (face to the
\ camera) otherwise, so a U-turn never swings into the glass.
: aq-uturn
  dup abs 0.45 > if
    dup 0.5 * aq-yaw fish@ + fish-sin
    INDEXOF_Y_POS read-mailbox 0 < if 0 < else 0 > then
    if dup 0 > if 1 - else 1 + then then
  then ;
\ yaw: rate' = wn^2 err - 2 zeta wn rate (semi-implicit Euler), |rate| capped
: aq-steer-yaw
  aq-yaw-t fish@ aq-yaw fish@ - aq-wrap-h aq-uturn aq-yaw-wn dup * *
  aq-yaw-w fish@ 2 aq-yaw-zeta * aq-yaw-wn * * -
  fish-dt * aq-yaw-w fish@ + aq-yaw-wmax fish-clampabs aq-yaw-w fish!
  aq-yaw-w fish@ fish-dt * aq-yaw fish@ + aq-wrap-h aq-yaw fish! ;
: aq-steer-pitch
  aq-pitch-t fish@ aq-pitch fish@ - aq-pitch-wn dup * *
  aq-pitch-w fish@ 2 aq-pitch-zeta * aq-pitch-wn * * -
  fish-dt * aq-pitch-w fish@ + aq-pitch-wmax fish-clampabs aq-pitch-w fish!
  aq-pitch-w fish@ fish-dt * aq-pitch fish@ + aq-pitch-max fish-clampabs aq-pitch fish! ;
\ bank into the turn: a left turn (rate > 0) lowers the left side (A < 0)
: aq-bank-tick aq-yaw-w fish@ aq-bank * negate aq-bank-max fish-clampabs aq-roll fish! ;

\ ---- speed: burst-and-coast along the facing ------------------------------
\ ( target tau -- ) ease aq-speed toward target with time constant tau
: aq-ease >r aq-speed fish@ - fish-dt r> / fish-clamp01 * aq-speed fish@ + aq-speed fish! ;
\ swimming: held input, unless it is a pure Up/Down stalled at the sand/surface
: aq-drive? aq-any? aq-hor? aq-flat fish@ 0.2 > | & ;
: aq-gait
  aq-drive? aq-was-moving fish@ 0 = & if 0 aq-cyc fish! then     \ a new swim starts with a burst
  aq-cyc fish@ fish-dt + dup aq-cycle >= if aq-cycle - then aq-cyc fish!
  0 aq-brake fish!  0 aq-burst fish!
  aq-dart-t fish@ 0 > if aq-dart-v aq-tau-dart aq-ease 1 aq-burst fish!
  else aq-drive? if
    aq-cyc fish@ aq-cycle aq-duty * < if
      aq-burst-v 1 aq-turn-dip aq-yaw-w fish@ abs aq-yaw-wmax / * - *   \ a tight turn dips the speed
      aq-tau-a aq-ease 1 aq-burst fish!
    else 0 aq-tau-c aq-ease then
  else
    0 aq-tau-glide aq-ease  aq-speed fish@ aq-v / fish-clamp01 aq-brake fish!
    aq-speed fish@ 0.01 < if 0 aq-speed fish! then
  then then
  aq-drive? aq-was-moving fish! ;
\ the only velocity write: speed (capped by the room ahead) times the facing
: aq-swim-write
  aq-speed fish@ aq-cap fish@ min dup aq-speed fish!
  dup aq-fx@ * INDEXOF_XSPEED write-mailbox
  dup aq-fy@ * INDEXOF_YSPEED write-mailbox
  aq-fz@ * INDEXOF_ZSPEED write-mailbox ;
\ what the rig needs to pose the visible fish (rig pitch B: + = nose DOWN)
: aq-publish
  aq-yaw fish@ fish-heading fish!  aq-pitch fish@ negate fish-pitch fish!
  aq-roll fish@ fish-roll fish!  aq-yaw-w fish@ fish-yaw-rate fish!
  aq-speed fish@ fish-speed fish!  aq-burst fish@ fish-burst fish!
  aq-brake fish@ fish-brake fish! ;

: aq-player-tick
  0 INDEXOF_INPUT write-mailbox
  aq-no-kicks
  aq-touch if aq-read-touch else aq-read-keys then
  aq-dart
  0 aq-pushed fish!
  aq-trig aq-limits aq-keeps
  aq-targets aq-steer-yaw aq-steer-pitch aq-bank-tick
  aq-trig aq-limits aq-caps
  aq-gait aq-swim-write aq-remember aq-publish
  aq-joy aq-prev fish!
  aq-any? aq-darting? | fish-idle-sense ;

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
