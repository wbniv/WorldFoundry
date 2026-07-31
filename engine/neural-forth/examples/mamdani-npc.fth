\ wf
\ mamdani-npc.fth — Mamdani fuzzy NPC controller.
\
\ Inputs  (normalised, float [0,1]):
\   distance : 0 = standing next to player, 1 = far away
\   health   : 0 = critical / dying,         1 = full health
\
\ Output (float [0,1]):
\   flee-impulse : 0 = hold position, 1 = maximum flee
\
\ Rules:
\   R1: IF distance IS close AND health IS low  THEN flee IS high
\   R2: IF distance IS far   AND health IS high THEN flee IS low
\
\ Defuzzification: centre-of-gravity over universe [0,1].
\
\ Requires kCoreBootstrap (variable, @, !).

variable npc-dist
variable npc-health
variable mf-d-close  variable mf-d-far
variable mf-h-low    variable mf-h-high
variable mf-f-low    variable mf-f-high
variable rule1-str   variable rule2-str

: init-fuzzy ( -- )
  0.0 0.0 0.35 0.6  trapezoidal  mf-d-close !
  0.4 0.65 1.0 1.0  trapezoidal  mf-d-far   !
  0.0 0.0 0.35 0.6  trapezoidal  mf-h-low   !
  0.4 0.65 1.0 1.0  trapezoidal  mf-h-high  !
  0.0 0.0 0.35 0.6  trapezoidal  mf-f-low   !
  0.4 0.65 1.0 1.0  trapezoidal  mf-f-high  ! ;

init-fuzzy

: npc-tick ( distance health -- flee )
  npc-health !
  npc-dist   !

  \ R1: close AND low → high flee
  npc-dist   @ mf-d-close @ mu@
  npc-health @ mf-h-low   @ mu@
  fand   rule1-str !

  \ R2: far AND high → low flee
  npc-dist   @ mf-d-far   @ mu@
  npc-health @ mf-h-high  @ mu@
  fand   rule2-str !

  \ Aggregate and defuzzify
  fuzzy-reset
  rule1-str @ mf-f-high @ fuzzy-add
  rule2-str @ mf-f-low  @ fuzzy-add
  defuzz-cog ;
