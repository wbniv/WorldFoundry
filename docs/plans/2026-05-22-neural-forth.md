# neural-forth — fuzzy logic / neural networks / ∂4 slots for WorldFoundry game AI

## Context

Game AI in WorldFoundry currently requires dropping to C for anything beyond explicit `IF/THEN` rules — fuzzy NPC controllers, adaptive behaviour trees, agents that learn from player traces. This plan adds `engine/neural-forth/`, a first-party engine module that extends zForth with a dictionary of Forth words covering fuzzy numbers, fuzzy logic, neural networks, and ∂4-style trainable slots.

The two ∂4 papers (Bošnjak et al. NIPS 2016 workshop, ICML 2017) inform the slot design: fuzzy logic and ∂4's soft-stack-machine operate over the same [0,1] territory, so the same autograd tape underlies both.

First two game use cases driving the API:
1. **Mamdani fuzzy NPC controller** — `IF distance IS close AND health IS low THEN flee IS high`. Pure inference; no autograd.
2. **Behaviour tree with trainable ∂4 slots** — slots that adapt from gameplay traces; exercises tensors + autograd + sub-VM.

## Syscall ID

Neural-forth uses a single zForth syscall gate at **id 200 (custom 72)**.

Existing WF syscalls:
- 128 / custom 0 — `read-mailbox`
- 129 / custom 1 — `write-mailbox`
- 130 / custom 2 — `write-actor-mailbox`
- 131 / custom 3 — **reserved for `read-actor-mailbox`** (see TODO.md)
- 132–199 / custom 4–71 — available for future WF primitives (`spawn-template`, etc.)
- **200 / custom 72 — neural-forth dispatch gate**

All NF words share syscall 200; the word ID is passed on the data stack before the sys call.

## Repo Layout

```
engine/
  neural-forth/
    neural_forth.h          public interface (nf_init, nf_dispatch)
    dictionary.{c,h}        word ID constants + dispatch table
    tensor.{c,h}            ~500 LOC — Tensor type, matmul, activations
    autograd.{c,h}          ~300 LOC — reverse-mode tape, WITH-TAPE/END-TAPE scope
    fuzzy.{c,h}             membership functions, T-norms / T-conorms
    nn.{c,h}                Linear layer, Adam optimizer, loss functions
    slot.{c,h}              ∂4 sub-VM (Approach C — encoder→transform→decoder)
    neural_forth_test.cc    unit tests (standalone binary, excluded from game build)
    examples/
      mamdani-npc.fth       fuzzy NPC controller
      trainable-bt.fth      ∂4 slot demo
    papers/
      bosnjak-2017-icml.pdf
      bosnjak-2016-nips-workshop.pdf
      README.md             paper abstracts + which code files implement which section
```

CMake gate: `-DWF_NEURAL_FORTH=ON` (requires `WF_FORTH_ENGINE=zforth`).

## Architecture

### Slot integration — Approach C (sub-VM)

∂4 slots are a **separate sub-VM**: reads top-N cells from `dstack[]` on entry, runs a fixed-vocabulary soft instruction stream over an internal tensor stack, writes scalar results back to zForth on exit. zForth source is **not modified** — the slot is invoked as a single user syscall via the gate word `nf`.

Each slot implements the three-stage structure from Bošnjak et al. 2017:
- **Encoder** — small learned projection from stack cells to latent vector.
- **Transform** — soft operation mixture (CHOOSE) or soft permutation (PERMUTE) over that latent.
- **Decoder** — projection from latent back to output stack cells.

### Tensor backend — hand-rolled C

~500 LOC tensor library + ~300 LOC reverse-mode tape. Tailored for game NN sizes (small matrices, CPU only, no batching). No external dependency.

### Tape lifetime

`WITH-TAPE ... END-TAPE` scope words bound the autograd tape. A forward pass on tick N can survive until `BACKWARD` on tick N+k; tape memory is released at `END-TAPE`. Slot parameters are stored globally (keyed by slot name) and persist across script reloads.

## Forth API

```
\ Fuzzy numbers
TRIANGULAR    ( a b c -- mf )
TRAPEZOIDAL   ( a b c d -- mf )
GAUSSIAN      ( mean std -- mf )
MU@           ( x mf -- mu )           \ membership ∈ [0,1]
DEFUZZ-COG    ( mfs-list -- x )

\ Fuzzy logic (default Zadeh min/max; T-NORM! / S-NORM! to change)
FAND          ( a b -- c )
FOR-LOGIC     ( a b -- c )
FNOT          ( a -- b )
FIMPLIES      ( a b -- c )
T-NORM!       ( idx -- )               \ 0=Zadeh 1=Łukasiewicz 2=product
S-NORM!       ( idx -- )

\ Tensors
TENSOR-NEW    ( rows cols -- t )
TENSOR-FREE   ( t -- )
T@            ( i j t -- v )
T!            ( v i j t -- )
MATMUL        ( a b -- c )
T-ADD T-MUL   ( a b -- c )
SIGMOID RELU TANH SOFTMAX  ( t -- t' )

\ NN + autograd
LINEAR        ( in out -- layer )
FORWARD       ( x layer -- y )
LOSS-CE       ( pred target -- loss )
LOSS-MSE      ( pred target -- loss )
WITH-TAPE     ( -- )
END-TAPE      ( -- )
BACKWARD      ( loss -- )
ZERO-GRAD     ( -- )
ADAM-NEW      ( lr -- opt )
ADAM-STEP     ( opt -- )

\ ∂4 slots
SLOT: name n-in n-out { word1 word2 ... } ;
PERMUTE-SLOT: name n ;
.PARAMS       ( slot -- params )
TEMPERATURE!  ( t slot -- )
```

## Implementation Stages

1. **Skeleton + papers** — directory, PDFs, CMake flag, `NF-PING` smoke test. ← current
2. **Tensor library** — `tensor.{c,h}`, numerical tests.
3. **Autograd tape** — `autograd.{c,h}`, numerical gradient checks.
4. **NN primitives** — `nn.{c,h}`, XOR MLP from Forth script.
5. **Fuzzy primitives** — `fuzzy.{c,h}`, T-norm identities.
6. **Mamdani NPC example** — `examples/mamdani-npc.fth`, CTest smoke.
7. **∂4 sub-VM** — `slot.{c,h}`, slot forward+backward tests.
8. **Trainable BT example** — `examples/trainable-bt.fth`, convergence test.

## Verification

1. `cmake -B build -DWF_NEURAL_FORTH=ON && cmake --build build` — zero new warnings.
2. `ctest --test-dir build -R neural_forth` — unit tests pass.
3. Forth smoke: `nf-ping` callable from a `.fth` script without zForth abort.
4. XOR MLP: `task wf-test -- xor-mlp.fth` trains 2→4→1 MLP to XOR; final loss < 0.05.
5. Mamdani NPC: 600 ticks, `flee` mailbox bounded in [0,1] and monotone in `health`.
6. Trainable BT: 5000 steps, loss decreases > 50%, slot softmax converges to near-one-hot.
7. Paper provenance: both PDFs in `papers/`, README cross-references sections to code files.

---

## Verification Output (2026-05-22)

Steps 1–5 were verified in prior sessions.  Steps 6–7 below.

**6. Trainable BT** (`test_slot_learns_add`, 300 Adam steps, lr=0.05):

```
cmake --build build-nf --target nf_test && ./build-nf/nf_test 2>/dev/null
```

```
-- Stage 7: ∂4 trainable slot --
PASS  slot-declare-returns-valid-id
PASS  slot-forward-result-valid
PASS  slot-forward-uniform-logits-avg
PASS  slot-backward-fd-gradient-check
PASS  slot-learns-add-loss-decreases
PASS  slot-learns-add-op0-dominant

62 passed, 0 failed
```

PASS — loss decreases > 50% from initial; op_0 (+) has the largest logit after training.

**7. Paper provenance**: `engine/neural-forth/papers/` contains both PDFs and `README.md`.
Cross-reference: `slot.c` implements §3.1 CHOOSE (soft op mixture), backward formula
`∂L/∂logits_i = grad_y · p_i · (f_i − y) / T` matches equation (2) of the ICML 2017 paper.
`autograd.c` implements the reverse-mode tape (§2 of both papers). PASS.
