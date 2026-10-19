# World Foundry GDK — Announcing neural-forth

**FOR IMMEDIATE RELEASE**  
World Foundry Game Development Kit  
May 2026

---

## World Foundry GDK Adds Differentiable Forth: Fuzzy Logic and On-Device Learning for Actor Scripts

*Game AI that adapts at runtime, trained in the same language designers already use to script level behaviour*

**World Foundry, May 2026** — The World Foundry Game Development Kit today ships
`neural-forth`, a first-party engine module that extends the built-in Forth scripting
system with fuzzy logic, neural networks, and differentiable operation slots. Game
actors can now blend rules, interpolate behaviours, and learn strategies from
gameplay traces — all from within the same per-frame Forth scripts that have always
driven World Foundry level logic.

---

### The Problem neural-forth Solves

World Foundry actor scripts are compact and fast. A Joust enemy is a handful of
Forth lines that read mailboxes and write actions. What sharp `if/then` rules cannot
do is *interpolate*. An enemy health threshold of 50 makes health 49 and health 51
behave identically until crossing the line, then radically differently. Designers
work around this by adding more rules, tighter value ranges, and carefully tuned
constants — exactly the kind of fiddly calibration work that never feels finished.

neural-forth replaces that process with three tools that work at the same scripting
level designers already operate at.

---

### Fuzzy Logic: Soft Rules, Smooth Behaviour

The fuzzy sub-system brings triangular, trapezoidal, and Gaussian membership
functions to Forth. A "close enemy" is no longer 0 or 1 — it is a degree between 0
and 1 that varies smoothly with distance. Fuzzy AND (`fand`), OR (`for-logic`), NOT
(`fnot`), and implication (`fimplies`) combine those degrees using selectable T-norms
(Zadeh min/max, Łukasiewicz, product). A Centre-of-Gravity defuzzifier (`defuzz-cog`)
converts the result back to an actionable scalar.

The classic Mamdani controller pattern — the backbone of industrial fuzzy control
systems since 1975 — is now expressible in a Forth NPC script:

```forth
\ IF enemy IS close AND health IS low THEN flee IS high
over mfd-close mu@  over mfh-low mu@  fand
fuzzy-reset  swap mff-high fuzzy-add  mff-low fuzzy-add
defuzz-cog
FLEE-MB write-mailbox
```

No external library, no CPU budget surprise — the entire fuzzy engine is ~220 lines
of C baked into the neural-forth module.

---

### Neural Networks: Trainable Parameters in Level Scripts

A tiny hand-rolled neural network backend gives level scripts access to linear
layers, activations (sigmoid, ReLU, tanh, softmax), MSE and cross-entropy losses,
and an Adam optimizer. All operations participate in a reverse-mode autograd tape
opened with `with-tape` and closed with `end-tape`. Gradients flow backward through
the tape with a single `backward` call, and `adam-step` updates the parameters.

A 2→4→1 MLP trained entirely from within a Forth script reaches near-zero XOR error
in 300 steps. The training loop is six Forth words:

```forth
with-tape
  x l1 forward relu  l2 forward sigmoid
  target loss-mse backward
end-tape
opt adam-step  zero-grad
```

The neural network backend is intentionally minimal: no GPU, no batching, no
external dependencies. It is sized for game AI — dozens of parameters, not millions.

---

### Differentiable Slots: Learning Which Operation to Apply

The flagship feature is the ∂4-style trainable slot, based on Bošnjak et al.
("Programming with a Differentiable Forth Interpreter," ICML 2017). A slot is a
typed hole in a Forth program that learns *which arithmetic operation* best fits the
task, rather than requiring a designer to hard-code the choice.

A combat priority node that needs to combine threat distance and threat damage can
declare a slot and let the game train it:

```forth
2 1 slot-declare constant aim-slot

: tick ( dist-t dmg-t -- priority-t )
  aim-slot slot-run ;
```

The slot maintains a learned distribution over five operations — add, subtract,
multiply, min, max. Early in training all five fire simultaneously with equal weight
(soft mixture). As gradient steps accumulate the distribution concentrates toward
whichever single operation best predicts the designer's supervisor signal. By the
end of training `slot-run` is approximately a single fast arithmetic op, and the
Forth script behaves as if the designer had chosen the right formula from the start.

Temperature annealing (`temperature!`) controls the sharpening schedule:

```forth
2.0 aim-slot temperature!   \ warm start — broad exploration
\ ... training steps ...
0.1 aim-slot temperature!   \ cool down — sharpen toward one-hot
```

---

### What Ships

| Component | Words | Capability |
|-----------|-------|-----------|
| Fuzzy | triangular, trapezoidal, gaussian, mu@, fand, for-logic, fnot, fimplies, defuzz-cog | Mamdani/Sugeno fuzzy controllers |
| Tensor | tensor-new, tensor-free, t@, t!, matmul, t-add, t-mul, sigmoid, relu, tanh-w, softmax | Foundation for NN and slot |
| Autograd | with-tape, end-tape, backward, zero-grad | Reverse-mode gradient tape |
| NN | linear, forward, loss-mse, loss-ce, adam-new, adam-step | Trainable MLPs |
| Slots | slot-declare, slot-run, .params, temperature! | ∂4 differentiable operation holes |

All 39 words are registered in the existing NF dispatch table and are callable from
any actor `.fth` script in the same way as the existing mailbox words. No changes to
level file format, no new asset types, no engine restart required to add a trainable
NPC.

---

### Verified Results

All 62 unit tests pass on the Linux reference build:

- **XOR MLP** converges to loss < 0.02 in 300 Adam steps.
- **Mamdani NPC** produces flee values bounded in [0,1] and monotone with health
  across 600 ticks.
- **Slot gradient check:** finite-difference vs analytical gradients agree to within
  2% relative error across all five logit parameters.
- **Slot convergence:** trained on *f(a,b) = a+b* supervision, the + operation
  becomes dominant (largest logit) within 300 steps; loss decreases > 50% from
  initial.

---

### Design Philosophy

neural-forth follows the same principles as the rest of the World Foundry GDK:

**No external dependencies.** The entire module — tensors, autograd, fuzzy engine,
Adam optimizer, slot sub-VM — is ~1700 lines of portable C99. It links against
nothing beyond the C standard library and zForth, which is already vendored.

**No changes to zForth.** The slot sub-VM reads scalar values off zForth's data
stack and writes results back. The zForth source is MIT-licensed and remains
upstream-mergeable.

**Sized for games, not research.** Tensor pool: 64 slots. Parameter registry: 128
entries. Tape: 1024 entries. Optimizer pool: 4 instances. These numbers cover the
largest game AI an actor script is likely to need; they are constants in the headers
and trivially raised if a specific use case requires it.

**Same scripting level, new capabilities.** A designer who knows the existing WF
Forth dialect can start using fuzzy membership functions in an afternoon. The
`slot-declare` / `slot-run` / `adam-step` words compose naturally with existing
mailbox reads and writes. Training lives inside the same `: word ... ;` definitions
as the rest of the level script.

---

### Getting Started

Build the standalone test binary:

```sh
cmake -B build-nf -DWORLDFOUNDRY_NEURAL_FORTH_STANDALONE=ON
cmake --build build-nf --target nf_test
./build-nf/nf_test
```

Example scripts:

- `engine/neural-forth/examples/mamdani-npc.fth` — fuzzy NPC controller
- `engine/neural-forth/examples/trainable-bt.fth` — behaviour tree with trainable slot

Research background and paper → code cross-references:

- `engine/neural-forth/papers/README.md`

---

*neural-forth is part of the World Foundry GDK. Source code, build instructions,
and documentation are in `engine/neural-forth/` of the WorldFoundry-wbniv
repository.*
