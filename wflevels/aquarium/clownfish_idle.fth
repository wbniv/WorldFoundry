\ clownfish_idle.fth - the canonical clownfish's swim stub, idle sense and part rig.
\
\ Needs the constants header that wflevels/aquarium/clownfish.py generates in front
\ of this file: every tunable (fish-bob-amp ...), the fish's global mailboxes
\ (fish-w ... 600..639), the part pivot offsets (fish-off-<part>-x/y/z) and the
\ runtime actor indices (fish-actor-player, fish-actor-body ...).
\
\ Entry points, one per script:
\   fish-player-tick   the Physics Player's script. Swim stub, then idle sense.
\   fish-rig-tick      the Director's script. The Director runs after every
\                      main-loop actor, so it sees this tick's post-physics
\                      Player position: the parts never lag the body.
\ A real swim controller replaces fish-swim-tick and calls
\   ( moving? ) fish-idle-sense   and   fish-turn   itself.
\
\ The Player is an invisible collision hull. The five visible parts are Mass-0
\ anchored platforms (never statplats: every statplat gets a Jolt body) placed
\ here each tick; nothing below writes the Player's position,
\ so the idle motion cannot move the physics body.
\ Plan: docs/plans/2026-09-30-clownfish-idle-animation.md

\ Every fish mailbox goes through fish-off (generated into the header: mailbox 1016, 0 for the player), so the same rig poses a
\ follower whose 40 mailboxes sit at 600 + fish-off. The player's tick never sees anything else: the Director resets it to 0.
: fish@ fish-off + read-mailbox ;
: fish! fish-off + write-mailbox ;
\ 1037 holds (frames since this fish was last posed) - 1, 0 for the player: a follower posed every other frame advances by two frames of time
: fish-dt INDEXOF_DELTA_TIME read-mailbox 1037 read-mailbox 1 + * ;
: fish-wrap dup 0 < if 1 + then dup 1 >= if 1 - then ;
\ Bhaskara sine, revolutions in (the condo's cc-sin): error under 0.2 %.
: fish-sin fish-wrap dup 0.5 > if 0.5 - -1 else 1 then >r
  2 * dup 1 swap - * dup 16 * swap 4 * 5 swap - / r> * ;
: fish-cos 0.25 + fish-sin ;
: fish-clamp01 0 max 1 min ;
: fish-lerp >r over - r> * + ;
: fish-smooth dup dup * swap 2 * 3 swap - * ;
: fish-clampabs 2dup > if nip else negate max then ;

\ ---- Player side --------------------------------------------------------
: fish-held INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox & 0 <> if 1 else 0 then ;
: fish-dir-x JOYSTICK_BUTTON_RIGHT fish-held JOYSTICK_BUTTON_LEFT fish-held - ;
: fish-dir-z JOYSTICK_BUTTON_UP fish-held JOYSTICK_BUTTON_DOWN fish-held - ;

\ ( moving? -- ) idle timer, then the idle weight ramps toward 1 or 0.
: fish-idle-sense
  if 0 fish-idle-t fish! 1 fish-input fish!
  else fish-idle-t fish@ fish-dt + fish-idle-t fish! 0 fish-input fish! then
  fish-idle-t fish@ fish-idle-delay >=
  if fish-w fish@ fish-dt fish-idle-in / +
  else fish-w fish@ fish-dt fish-idle-out / - then
  fish-clamp01 fish-w fish! ;

\ Visual heading eases toward its target: half a turn in fish-turn-time.
: fish-turn
  fish-heading-target fish@ fish-heading fish@ -
  0.5 fish-dt * fish-turn-time / fish-clampabs
  fish-heading fish@ + fish-heading fish! ;

\ ( -- moving? ) Swim STUB with the aquarium Phase 1 controls: while a direction is
\ held, write +-fish-swim-speed to that axis; write nothing on release, so the air drag
\ glides it; INPUT 0 every tick. No clamps here: the level adds its X/Z clamps.
: fish-swim-tick
  0 INDEXOF_INPUT write-mailbox
  fish-dir-x fish-dx fish!  fish-dir-z fish-dz fish!
  fish-dx fish@ 0 <> if fish-dx fish@ fish-swim-speed * INDEXOF_XSPEED write-mailbox then
  fish-dz fish@ 0 <> if fish-dz fish@ fish-swim-speed * INDEXOF_ZSPEED write-mailbox then
  fish-dx fish@ 0 > if 0 fish-heading-target fish! then
  fish-dx fish@ 0 < if -0.5 fish-heading-target fish! then
  fish-turn
  \ tell the rig: speed while held, the tail drives while held (no burst-and-coast in the stub)
  fish-dx fish@ 0 <> fish-dz fish@ 0 <> |
  if fish-swim-speed 1 else 0 0 then fish-burst fish! fish-speed fish!
  fish-dx fish@ 0 <> fish-dz fish@ 0 <> | ;

: fish-player-tick fish-swim-tick fish-idle-sense ;

\ ---- Director side: the rig ---------------------------------------------
: fish-ws@ fish-ws fish@ ;
\ ( hz slot -- ) phase accumulator: a changing frequency never jumps the phase.
: fish-advance >r fish-dt * r@ fish@ + fish-wrap r> fish! ;

\ Phase 4: the swimming tail beats at the Strouhal frequency of the ACTUAL speed,
\ f = St U / A (capped under Nyquist), and only while fish-burst is set (the
\ envelope eases it in and out, so a coast leaves the body straight); idle
\ sculling is a separate slow oscillator weighted by the idle weight. The
\ pectorals speed up from 2.4 to 4.6 beats/s with speed (A. ocellaris).
: fish-speed@ fish-speed fish@ ;
: fish-phases
  fish-w fish@ fish-smooth fish-ws fish!
  fish-bob-hz fish-ph-bob fish-advance
  fish-sway-hz fish-ph-sway fish-advance
  fish-tail-idle-hz fish-ph-tail fish-advance
  fish-strouhal fish-speed@ * fish-tail-app / fish-tail-hz-max min fish-ph-swim fish-advance
  fish-pec-idle-hz fish-pec-hz-hi fish-speed@ fish-pec-v-hi / fish-clamp01 fish-lerp fish-ph-pec fish-advance
  fish-dorsal-hz fish-ph-dorsal fish-advance
  fish-burst fish@ fish-tail-env fish@ - fish-dt fish-tail-env-t / fish-clamp01 *
  fish-tail-env fish@ + fish-tail-env fish! ;

\ ( -- env ) 1 at a burst, 0 coasting or idle
: fish-env@ fish-tail-env fish@ ;
\ ( -- shift ) far pectoral's phase lag: 0.5 (alternating) at low speed, 0 (synchronous) fast
: fish-pec-lag 0.5 1 fish-speed@ fish-pec-sync-lo - fish-pec-sync-hi fish-pec-sync-lo - / fish-clamp01 - * ;
\ ( -- flare ) off the flank; wider to brake, folded while coasting
: fish-flare@ fish-pec-flare fish-brake fish@ fish-pec-brake * +
  1 fish-ws@ - 1 fish-env@ - * 1 fish-brake fish@ - * fish-pec-fold * - ;

\ ( -- z ) the body origin into fish-bx and fish-by, its height left on the stack: the player's actor, or for a follower the
\ position its school code wrote to the globals 1032..1034.
: fish-read-pos
  fish-off 0 = if
    INDEXOF_X_POS fish-actor-player read-actor-mailbox fish-bx fish!
    INDEXOF_Y_POS fish-actor-player read-actor-mailbox fish-by fish!
    INDEXOF_Z_POS fish-actor-player read-actor-mailbox
  else
    1032 read-mailbox fish-bx fish!
    1033 read-mailbox fish-by fish!
    1034 read-mailbox
  then ;
: fish-channels
  fish-ws@ fish-tail-idle-amp * fish-ph-tail fish@ fish-sin *
  fish-env@ fish-tail-swim-amp * fish-ph-swim fish@ fish-sin * +
  fish-bend fish-yaw-rate fish@ * - fish-tail fish!
  fish-pec-coast-amp fish-pec-swim-amp fish-env@ fish-lerp fish-pec-idle-amp fish-ws@ fish-lerp
  dup fish-ph-pec fish@ fish-sin * fish-pec fish!
  fish-ph-pec fish@ fish-pec-lag + fish-sin * fish-pec-far fish!
  1 fish-ws@ fish-dorsal-amp * 0.5 0.5 fish-ph-dorsal fish@ fish-cos * - * - fish-dorsal fish!
  fish-heading fish@ fish-ws@ fish-sway-yaw * fish-ph-sway fish@ fish-sin * +
  fish-counter-yaw fish-tail fish@ * - fish-body-c fish!
  fish-pitch fish@ fish-ws@ fish-sway-pitch * fish-ph-sway fish@ 0.25 + fish-sin * + fish-body-b fish!
  fish-body-c fish@ fish-sin fish-sc fish!  fish-body-c fish@ fish-cos fish-cc fish!
  fish-body-b fish@ fish-sin fish-sb fish!  fish-body-b fish@ fish-cos fish-cb fish!
  fish-roll fish@ fish-sin fish-sa fish!  fish-roll fish@ fish-cos fish-ca fish!
  fish-read-pos
  fish-ws@ fish-bob-amp * fish-ph-bob fish@ fish-sin * + fish-bz fish! ;

\ ( ox oy oz -- ) body-local pivot -> world, into fish-ox/oy/oz.
\ Engine Euler (matrix34.cc): world = Rz(C) Ry(B) Rx(A) local; +B tips the nose
\ down, A banks (Phase 4: the swim controller's roll into a turn).
: fish-sa@ fish-sa fish@ ;  : fish-ca@ fish-ca fish@ ;
: fish-sb@ fish-sb fish@ ;  : fish-cb@ fish-cb fish@ ;
: fish-sc@ fish-sc fish@ ;  : fish-cc@ fish-cc fish@ ;
: fish-ox@ fish-ox fish@ ;  : fish-oy@ fish-oy fish@ ;  : fish-oz@ fish-oz fish@ ;
: fish-size 639 fish@ dup 0 = if drop 1 then ;   \ the 40th mailbox of a fish's block: 0 (never written, the player) means full size
: fish-place
  fish-size * fish-oz fish! fish-size * fish-oy fish! fish-size * fish-ox fish!
  fish-ox@ fish-cb@ * fish-cc@ *
  fish-oy@ fish-sb@ fish-sa@ * fish-cc@ * fish-ca@ fish-sc@ * - * +
  fish-oz@ fish-sb@ fish-ca@ * fish-cc@ * fish-sa@ fish-sc@ * + * + fish-bx fish@ +
  fish-ox@ fish-cb@ * fish-sc@ *
  fish-oy@ fish-sb@ fish-sa@ * fish-sc@ * fish-ca@ fish-cc@ * + * +
  fish-oz@ fish-sb@ fish-ca@ * fish-sc@ * fish-sa@ fish-cc@ * - * + fish-by fish@ +
  fish-ox@ fish-sb@ * negate
  fish-oy@ fish-cb@ * fish-sa@ * +
  fish-oz@ fish-cb@ * fish-ca@ * + fish-bz fish@ +
  fish-oz fish! fish-oy fish! fish-ox fish! ;

\ ( actor -- )
: fish-put >r
  fish-ox fish@ INDEXOF_X_POS r@ write-actor-mailbox
  fish-oy fish@ INDEXOF_Y_POS r@ write-actor-mailbox
  fish-oz fish@ INDEXOF_Z_POS r> write-actor-mailbox ;

\ ( a b c actor -- ) A and B only land in a static Euler shared by every actor
\ (actor.cc WriteSystemMailbox); the C write commits all three. Always A, B, C.
: fish-orient >r rot INDEXOF_ROTATION_A r@ write-actor-mailbox
  swap INDEXOF_ROTATION_B r@ write-actor-mailbox
  INDEXOF_ROTATION_C r> write-actor-mailbox ;

: fish-a@ fish-roll fish@ ;
: fish-pose-body
  fish-off-body-x fish-off-body-y fish-off-body-z fish-place fish-actor-body fish-put
  fish-a@ fish-body-b fish@ fish-body-c fish@ fish-actor-body fish-orient ;
: fish-pose-tail
  fish-off-tail-x fish-off-tail-y fish-off-tail-z fish-place fish-actor-tail fish-put
  fish-a@ fish-body-b fish@ fish-body-c fish@ fish-tail fish@ + fish-actor-tail fish-orient ;
: fish-pose-dorsal
  fish-off-dorsal-x fish-off-dorsal-y fish-off-dorsal-z fish-place fish-actor-dorsal fish-put
  fish-a@ fish-body-b fish@ fish-body-c fish@ fish-actor-dorsal fish-orient
  fish-dorsal fish@ fish-size * INDEXOF_Z_SCALE fish-actor-dorsal write-actor-mailbox ;
\ The far fin's swing is its own channel (fish-pec-far): at low speed it lags
\ half a beat (alternating, the old mirror image), at speed it beats in phase.
: fish-pose-pecs
  fish-off-pec-near-x fish-off-pec-near-y fish-off-pec-near-z fish-place fish-actor-pec-near fish-put
  fish-a@ fish-body-b fish@ fish-pec fish@ +
  fish-body-c fish@ fish-flare@ + fish-actor-pec-near fish-orient
  fish-off-pec-far-x fish-off-pec-far-y fish-off-pec-far-z fish-place fish-actor-pec-far fish-put
  fish-a@ fish-body-b fish@ fish-pec-far fish@ +
  fish-body-c fish@ fish-flare@ - fish-actor-pec-far fish-orient ;

: fish-rig-tick
  fish-phases fish-channels
  fish-pose-body fish-pose-tail fish-pose-dorsal fish-pose-pecs ;
