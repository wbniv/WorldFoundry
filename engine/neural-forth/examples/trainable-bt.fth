\ wf
\ trainable-bt.fth — behaviour tree with a ∂4-style trainable CHOOSE slot.
\
\ A behaviour-tree priority node that learns which arithmetic operation
\ {a+b, a-b, a*b, min, max} best maps (threat-dist, threat-dmg) → priority.
\
\ The slot is a soft mixture over five fixed operations (Bošnjak et al. ICML
\ 2017, §3.1 CHOOSE primitive).  Training via Adam minimises MSE against
\ supervisor signals from gameplay traces (or a handcrafted teacher policy).
\
\ Three-stage structure (per paper):
\   encoder   — identity (scalar pass-through at Stage 7)
\   transform — CHOOSE: y = Σ_i softmax(logits/T)[i] · op_i(a, b)
\   decoder   — identity
\
\ Forth word reference (all registered in neural-forth dictionary):
\   slot-declare  ( n_in n_out -- slot_h )
\   slot-run      ( t_1 .. t_N slot_h -- result_h )
\   .params       ( slot_h -- logits_h )
\   temperature!  ( temp slot_h -- )
\   with-tape / end-tape / backward / zero-grad
\   adam-new      ( lr -- opt_h )
\   adam-step     ( opt_h -- )
\   tensor-new    ( rows cols -- t_h )
\   loss-mse      ( pred target -- loss )
\
\ Requirements: kCoreBootstrap must be loaded for `constant` and `variable`.
\ When running inside WorldFoundry the engine boots kCoreBootstrap before
\ calling nf_init(), so those words are always available in level scripts.

\ ── Slot creation ───────────────────────────────────────────────────────────

\ Create a 2-input, 1-output slot.  Logits initialise to 0 (uniform softmax).
2 1 slot-declare constant aim-priority

\ Warm start: apply softmax temperature of 2.0 for smooth early training.
2 aim-priority temperature!

\ ── Optimizer ───────────────────────────────────────────────────────────────

0.05 adam-new constant adam-opt

\ ── Inference word ──────────────────────────────────────────────────────────

\ tick ( dist-t dmg-t -- priority-t )
\   Run one forward inference step.  Inputs and output are tensor handles.
: tick ( dist-t dmg-t -- priority-t )
  aim-priority slot-run ;

\ ── Training word ───────────────────────────────────────────────────────────

\ train-once ( dist-t dmg-t target-t -- )
\   One gradient step toward target priority.
: train-once ( dist-t dmg-t target-t -- )
  >r                           \ save target-t
  with-tape
    r>                         \ restore: dist-t dmg-t target-t on stack
    swap >r swap               \ re-order: dist-t dmg-t, r: target-t
    tick                       \ -- priority-t
    r>                         \ -- priority-t target-t
    loss-mse                   \ -- loss-t
    backward
  end-tape
  aim-priority .params         \ -- logits_h (slot parameters)
  drop                         \ (params pushed to Adam via register; drop handle)
  adam-opt adam-step
  zero-grad ;

\ ── Convenience: train N steps with scalar inputs ───────────────────────────

\ make-scalar ( v -- t )  allocate a 1×1 tensor and write v into it
: make-scalar ( v -- t )
  1 1 tensor-new               \ -- t
  dup >r                       \ save t
  0 0 rot r> t! ;              \ t!(v 0 0 t) — stack must be ( v i j t )
  \ Note: t! expects ( v i j t -- ); adjust if calling directly in C tests.

\ Supervisor policy: for these inputs the correct answer is a+b.
\ In a real game the supervisor signal comes from designer-scripted or
\ replay-logged target values written into a mailbox each tick.
: supervisor-target ( dist dmg -- sum )
  + ;

\ For level scripts the training loop runs over many ticks, not in one word.
\ This sketch shows the per-tick pattern:
\
\   ( each game tick, if training is enabled )
\   dist-scalar dmg-scalar supervisor-target  \ compute target float
\
\   dist-scalar make-scalar                   \ dist-t
\   dmg-scalar  make-scalar                   \ dmg-t
\   over over supervisor-target make-scalar   \ target-t
\   train-once                                \ gradient step
\
\   tensor-free tensor-free tensor-free       \ release temporaries

\ ── Convergence check (read-only) ───────────────────────────────────────────

\ print-dominant-op ( -- )
\   After training, the logit with the largest value is the learned operation.
\   Op indices: 0=+  1=-  2=*  3=min  4=max
: print-dominant-op ( -- )
  aim-priority .params         \ -- logits_h
  dup 0 0 t@                   \ -- logits_h logit_0
  dup >r                       \ save max so far
  swap 1 0 t@ dup r> max >r   \ compare logit_1
  swap 2 0 t@ dup r> max >r
  swap 3 0 t@ dup r> max >r
  swap 4 0 t@ dup r> max
  drop drop                    \ ( largest value left — emit its index separately )
  ;                            \ full argmax requires kCoreBootstrap DO/LOOP
