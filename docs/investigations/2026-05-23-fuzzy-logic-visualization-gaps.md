# Investigation: Fuzzy Logic Research — Visualization Gaps and World Foundry Opportunities

**Date:** 2026-05-23
**Context:** World Foundry now has fuzzy logic, neural networks, and autograd in its scripting layer (`engine/neural-forth/`, wired in `9c91f83e`). This investigation identifies where a real-time 3D physics engine could contribute a simulator or visualization that the academic community genuinely lacks — either for a recent paper's methodology or as a pedagogical tool for classic concepts.

Existing tools (MATLAB Fuzzy Toolbox, scikit-fuzzy, JuzzyPy, FuzzyLogic.jl) all share the same limitation: 2D static plots, no physics coupling, no interactivity beyond parameter sliders, no embodied spatial metaphor for inherently geometric concepts.

---

## 1. TL;DR

**Top targets:**

| Priority | Paper | Concept | Engine effort |
|----------|-------|---------|--------------|
| 1 | Mamdani & Assilian 1975 | Full inference pipeline as layered 3D surfaces over a live physics plant | Low |
| 2 | Fuz-RL (2026, arXiv 2602.20729) | Choquet-integral uncertainty volume + safe-region boundary in 3D | Medium |
| 3 | Takagi & Sugeno 1985 + TSK-RL 2023 | Live rule surface coupled to Jolt pendulum | Low |
| 4 | Mendel & John 2002 (Type-2 FOU) | Type-2 membership solid — 3D object never rendered | Medium |
| 5 | Flock fuzzy RL (arXiv 2303.09946) | 3D boid swarm with per-agent rule-activation halos | Medium |

---

## 2. Seminal papers needing 3D visualization

### 2.1 Zadeh (1965) — "Fuzzy Sets"
*Information and Control* 8(3), pp. 338–353

**Concept:** Membership functions, grade-of-membership continuum, fuzzy set operations (union, intersection, complement).

**Gap:** All existing tools (MATLAB, scikit-fuzzy, JuzzyPy) render μ(x) as a 2D line plot, detached from any physical referent. A 3D scene with characters of varying heights whose diffuse color encodes their grade of membership in "tall", with the membership function rendered as a floating ribbon above the scene and real-time slider control of function parameters, is the difference between understanding a formula and understanding a concept. The 2010 Park & Park IS&T tool was 2D and non-embodied.

**Engine feasibility:** Very high. Physics bodies with a height scalar attribute; color driven by Gaussian/trapezoidal μ(x) evaluated at that height. A few hours of level scripting.

---

### 2.2 Mamdani & Assilian (1975) — "An Experiment in Linguistic Synthesis with a Fuzzy Logic Controller"
*International Journal of Man-Machine Studies* 7(1), pp. 1–13

**Concept:** The full Mamdani inference pipeline: fuzzification → rule firing → aggregation → defuzzification.

**Gap:** MATLAB's Rule Viewer is a 2D grid of mini-plots notorious among students for being unreadable. The eMathTeacher ACM 2008 tool was a 2D static web page. No 3D physics-coupled version exists.

**Proposed visualization:** A 3D steam-boiler scene (the paper's original application) where the inference pipeline floats above it as a stack of 3D surfaces: bottom layer = input membership function ribbons, middle = fired-rule volumes highlighted by activation strength, top = aggregated output surface, with a vertical COG cursor dropping to the crisp output value that drives the valve angle as a physics constraint. All layers animate as boiler state changes in real time.

**Engine feasibility:** Very high. Boiler = two rigid bodies (vessel + valve) with a heat scalar. Mamdani inference over a 2×1 rule base is ~50 lines of zForth. Pipeline = textured planes with procedurally updated vertex colors.

---

### 2.3 Takagi & Sugeno (1985) — "Fuzzy Identification of Systems and Its Applications to Modeling and Control"
*IEEE Trans. Systems, Man, Cybernetics* 15(1), pp. 116–132

**Concept:** The rule surface — how a TSK system approximates a nonlinear function as a patchwork of local linear models.

**Gap:** MATLAB `surfview` shows a static 3D mesh the user cannot interact with, decoupled from any physics. No tool lets you grab a membership function boundary and watch adjacent linear patches stitch together or pull apart in real time, with residual error shown as deviation vectors.

**Proposed visualization:** Interactive rule-surface mesh coupled to a live Jolt nonlinear pendulum. The user adjusts MF shoulders in the 3D UI; the TSK surface deforms; the controller output changes; the pendulum reacts. Closing the loop between the abstract surface and the physical plant in real time.

**Engine feasibility:** Very high. TSK surface evaluation is a dot product per rule. Pendulum is a single revolute constraint in Jolt. This target converges with the 2023 TSK-RL paper (§3.2) — one tool serves both.

---

### 2.4 Mendel & John (2002) — "Type-2 Fuzzy Sets Made Simple"
*IEEE Trans. Fuzzy Systems* 10(2), pp. 117–127

**Concept:** The Footprint of Uncertainty (FOU) as a genuine 3D object; the secondary membership function f(x,u) as a surface over the primary domain.

**Gap:** A type-2 fuzzy set is inherently 3D: primary variable x, primary membership u, secondary grade f(x,u). Every paper including Mendel's own uses the 2D FOU projection because the actual 3D object is hard to draw. JuzzyPy supports GT2 but renders 2D FOU plots only.

**Proposed visualization:** A translucent 3D membership solid floating above the x-axis — its base traces the FOU, its height encodes f(x,u) as color and vertex elevation. The IT2 special case (f = 1 inside FOU) becomes a flat-topped slab, making the IT2 vs GT2 distinction visually immediate. Interactive sliders for upper/lower MF parameters regenerate the mesh via vertex buffer updates.

**Engine feasibility:** High. FOU is a closed region defined by upper/lower MFs; extrusion to 3D solid is a mesh generation problem. The interactive update is a vertex buffer rewrite per frame — fast.

---

### 2.5 Jang (1993) — "ANFIS: Adaptive-Network-based Fuzzy Inference System"
*IEEE Trans. Systems, Man, Cybernetics* 23(3), pp. 665–685

**Concept:** Five-layer architecture where each layer has a clear geometric meaning; how backpropagation moves membership function parameters during training.

**Gap:** MATLAB's ANFIS editor shows a static node-link diagram. No tool renders the architecture as a physical scene where Layer 1 nodes are Gaussian bells in input space, Layer 2 is a grid of firing-strength discs, and Layer 5 is a deforming output surface updated live during gradient descent.

**Why World Foundry is a natural fit:** WF already has autograd in `engine/neural-forth/autograd.c`. Gaussian MF gradient w.r.t. center and width is trivial. Running gradient descent live in the engine while surfaces animate would make backpropagation viscerally understandable — without requiring a separate plotting library.

**Engine feasibility:** Very high given existing autograd. The DAG visualization is a standard layered node-link layout in 3D.

---

### 2.6 Kosko (1986) — "Fuzzy Cognitive Maps"
*International Journal of Man-Machine Studies* 24(1), pp. 65–75

**Concept:** FCM as a dynamic causal system; activation propagating and converging (or oscillating) through a signed weighted graph.

**Gap:** FCM-VSS (ScienceDirect 2025) exists as a 2D web tool but has no physics coupling or 3D embodiment. No tool shows FCM dynamics as a coupled physical simulation where FCM output directly drives forces on rigid bodies.

**Proposed visualization:** Nodes as glowing orbs (brightness = activation), edges as glowing beams (opacity = weight magnitude). The user pushes/pulls individual node activations and watches ripples propagate. Physics bodies in the scene are driven by FCM outputs — e.g., a cart's velocity proportional to node activation.

**Engine feasibility:** High. FCM update rule = matrix-vector multiply + sigmoid. Physics coupling is the novel contribution. Glow encoding via additive blending.

---

## 3. Recent papers (2020–2025) lacking simulators

### 3.1 Fuz-RL: Fuzzy-Guided Robust Safe Reinforcement Learning (2026)
*arXiv 2602.20729*, Xu Wan et al., Zhejiang University / Alibaba DAMO Academy / Peking University

**What it proposes:** A fuzzy Bellman operator using Choquet integrals to estimate robust value functions under multiple simultaneous uncertainty sources (observation noise, action noise, dynamics uncertainty). Proved equivalent to distributionally robust safe RL while avoiding min-max optimization.

**Gap:** Evaluated only on 2D benchmark tasks (pendulum, point robot). The Choquet fuzzy measure over uncertainty sources is inherently a 3D object — each uncertainty dimension maps to a membership grade governing the integral. No visualization of how the safety boundary shifts as uncertainty compounds. The paper's main claim is never shown geometrically.

**Proposed visualization:** A 3D physics scene where uncertainty sources are sliders. The Choquet-weighted value surface morphs in real time as a 3D mesh; the safety constraint boundary is a level-set surface; the agent navigates the scene subject to changing uncertainty regimes.

**Engine feasibility:** High. Choquet integral is a weighted sum computable in a few dozen lines of zForth. Level-set surface rendering is standard. Safe-control-gym environments (pendulum, point robot) are straightforward Jolt rigid bodies.

---

### 3.2 RL with TSK Fuzzy Systems — XFC 2022 Challenge
*Complex Engineering Systems*, doi 10.20517/ces.2023.11, Beomsoo Lim et al., University of Cincinnati

**What it proposes:** Actor-critic optimization of existing TSK systems + DQN adapted to ANFIS, targeting the 2022 XFC "Asteroid Smasher" explainability challenge.

**Gap:** Rule surfaces published as static 2D tables. The "Asteroid Smasher" environment was a 2D Flash/Java game with no publicly released engine. A 3D re-implementation with live rule-activation overlays (each rule lights up its region of input space as a glowing volume; the crisp output is a point on the rule surface) would be the canonical visualization this line of work needs.

**Engine feasibility:** Very high. TSK inference = linear combination of rule outputs weighted by firing strengths. Asteroid smasher in 3D Jolt is straightforward. This target converges with §2.3.

---

### 3.3 Adaptive Fuzzy RL for Flock (Boid) Control (2023)
*arXiv 2303.09946*, Shuzheng Qu et al., University of Ottawa

**What it proposes:** Online fuzzy RL scheme for N-agent flocking: simultaneous leader-following, collision avoidance, and velocity consensus. Rules adapt via RL. The paper itself identifies 3D extension as future work.

**Gap:** Validation is 2D matplotlib trajectory plots. Flocking emergent behavior is quintessentially 3D — lane formation, turbulence, cluster splitting only appear with real spatial volume. No tool shows individual agent rule weights live or lets the user tweak membership functions and watch the flock respond.

**Proposed visualization:** 20–100 physics bodies in 3D, each agent's fuzzy rule weights shown as a color-coded halo. User tweaks MF parameters at runtime; flock behavior changes immediately. Per-agent rule activations rendered via instanced geometry.

**Engine feasibility:** High. Fuzzy controller per agent is tiny (3–5 rules). Multi-actor levels are a solved problem in WF. Instanced rendering for N agents is standard.

---

### 3.4 TSK for High-Dimensional Multilabel Classification (2024)
*IEEE Trans. Fuzzy Systems*, doi 10.1109/TFUZZ.2024.3385464

**What it proposes:** TSK extended to 50–500 input dimensions via consistent dimensional reduction (CDR) embedded in rule antecedents. Tackles the curse of dimensionality while preserving interpretability.

**Gap:** Every figure collapses to 2D projections. When CDR reduces 200 → 2 dimensions, the latent space is where rules make sense — but it is never shown dynamically. No tool lets an XAI auditor rotate the 2D latent manifold in 3D, drag membership function boundaries, and watch projections change.

**Engine feasibility:** Medium. Dimensionality reduction is pre-computed offline; the engine renders the result as a 3D point cloud with color-coded rule activations. The interactive MF boundary dragging is a 2D UI overlay.

---

### 3.5 Type-3 Fuzzy Stabilizer for UAV Control (2024)
*Complex & Intelligent Systems* (Springer), Guo et al.

**What it proposes:** A type-3 fuzzy logic system (second-order extension of IT2) compensating identification error in UAV dynamics, tuned by sliding mode control.

**Gap:** Type-3 membership functions are 4-dimensional objects. No existing open-source tool renders them. The paper validates on Simulink altitude/angle traces only.

**Proposed visualization:** A 3D quadrotor scene where the type-3 uncertainty bounds are rendered as nested translucent shells around each UAV axis: inner = type-1 crisp core, middle = IT2 FOU shell, outer = T3 additional uncertainty layer. The first live illustration of what "type-3" means geometrically.

**Engine feasibility:** Medium. Quadrotor dynamics = rigid body + four upward thrust forces (standard in Jolt). Nested shell visualization = additive-blended sphere meshes. The hard part: correctly computing the outer Karnik-Mendel loop for T3 reduction.

---

## 4. Implementation priority

For a first WF academic contribution, ranked by impact-to-effort ratio:

1. **Mamdani inference pipeline** (§2.2) — most-cited classic (800+ citations), completely missing 3D embodied version, boiler physics is simple, the visualization *is* the contribution. Directly citable against a 50-year-old paper. Estimated: 2–3 days.

2. **TSK rule surface + live pendulum** (§2.3 + §3.2) — these two converge. One interactive rule-surface tool serves both the 1985 Takagi-Sugeno pedagogical need and the 2023 TSK-RL paper's interpretability gap. Estimated: 2 days on top of #1.

3. **Fuz-RL safety boundary** (§3.1) — recent (2026), active research area, the Choquet uncertainty volume is a genuinely novel visualization, authors are reachable. Estimated: 3–4 days (Jolt physics setup is the main work).

4. **Type-2 FOU solid** (§2.4) — the 3D membership solid is unpublished anywhere; it is a clean paper contribution with WF as the implementation vehicle. Estimated: 1–2 days (pure rendering, no physics).

5. **Fuzzy boid swarm** (§3.3) — highest visual drama, good demo material, the paper explicitly invites 3D extension. Estimated: 4–5 days.

---

## 5. Sources

- Fuz-RL: [arXiv 2602.20729](https://arxiv.org/abs/2602.20729)
- RL with TSK: [OAE Complex Engineering Systems 2023](https://www.oaepublish.com/articles/ces.2023.11)
- Fuzzy RL flock: [arXiv 2303.09946](https://arxiv.org/abs/2303.09946)
- TSK high-dim: [IEEE TFS 2024](https://ieeexplore.ieee.org/document/10485465/)
- Type-3 UAV: [Complex & Intelligent Systems 2024](https://link.springer.com/article/10.1007/s40747-024-01434-y)
- Interpretable TSK clustering: [arXiv 2504.05125](https://arxiv.org/abs/2504.05125)
- Mendel & John 2002: [IEEE TFS](https://sipi.usc.edu/~mendel/publications/Mendel&John%202002.pdf)
- Mamdani eMathTeacher 2008: [ACM DL](https://dl.acm.org/doi/abs/10.5555/1457927.1457930)
- FCM-VSS 2025: [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2352711025000251)
- JuzzyPy / FuzzyLogic.jl: [arXiv 2306.10316](https://arxiv.org/html/2306.10316v1)
