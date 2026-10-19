\ Local flow integrator, independent of engine extensions. Director is owner.
\ Inputs/outputs 1300..1318 are a mouth-aligned relative frame; no position tween.
\ 0..2 prey xyz, 3..5 velocity, 6 dt, 7 pulse [0,1], 8 aperture radius,
\ 9 line-of-sight clear, 10..12 flow velocity, 13 r2, 14 strength,
\ 15..17 active swimming acceleration, 18 expansion/flow acceleration factor.
: lf@ 1300 + read-mailbox ; : lf! 1300 + write-mailbox ;
: lf-flow
  0 10 lf! 0 11 lf! 0 12 lf! 0 14 lf!
  0 lf@ 0 >= 9 lf@ 0 <> & 7 lf@ 0 > & if
    0 lf@ dup * 1 lf@ dup * + 2 lf@ dup * + 13 lf!
    8 lf@ dup * 13 lf@ + .0001 max
    8 lf@ dup * swap / dup *
    7 lf@ * 16 * 14 lf!
    \ Rapid distance decay, bounded at the aperture; radial convergence.
    0 lf@ .035 + negate 14 lf@ * -4 max 4 min 10 lf!
    1 lf@ negate 14 lf@ * -4 max 4 min 11 lf!
    2 lf@ negate 14 lf@ * -4 max 4 min 12 lf!
  then ;
: lf-step
  lf-flow
  3 0 do
    i 10 + lf@ i 3 + lf@ - 14 lf@ 1 min 18 * *
    i 10 + lf@ 18 lf@ * + i 15 + lf@ +
    -80 max 80 min 6 lf@ 0 max .005 min * i 3 + lf@ +
    -4 max 4 min i 3 + lf!
    i lf@ i 3 + lf@ 6 lf@ 0 max .005 min * + i lf!
  loop ;
