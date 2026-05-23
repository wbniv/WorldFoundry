# Vendored Research Papers — Investigation References

This directory holds open-access PDFs of papers cited in `docs/investigations/`.
Implementation-reference papers (those that informed actual engine code) live
elsewhere — see `engine/neural-forth/papers/` for the Bošnjak / differentiable
Forth papers behind `engine/neural-forth/slot.c`.

## Vendoring as SOP

When an investigation cites academic work, vendor the open-access PDF here in
the same commit. The full SOP — what to vendor, where, how to name files, what
to do when a paper is paywalled — is documented in user memory
`feedback_vendor_research_papers.md`.

## Index

### Open-access PDFs (this directory)

| File | Citation | Source |
|------|----------|--------|
| `1986-kosko-fuzzy-cognitive-maps.pdf` | Kosko, B. (1986). "Fuzzy Cognitive Maps." *International Journal of Man-Machine Studies* 24(1), pp. 65–75. | [sipi.usc.edu/~kosko/FCM.pdf](https://sipi.usc.edu/~kosko/FCM.pdf) (author host) |
| `2002-mendel-john-type2-made-simple.pdf` | Mendel, J. M. & John, R. I. B. (2002). "Type-2 Fuzzy Sets Made Simple." *IEEE Transactions on Fuzzy Systems* 10(2), pp. 117–127. | [sipi.usc.edu/~mendel/publications/](https://sipi.usc.edu/~mendel/publications/Mendel%26John%202002.pdf) (author host) |
| `2023-ferranti-fuzzylogic-jl.pdf` | Ferranti, L. & Boutellier, J. (2023). "FuzzyLogic.jl: a Flexible Library for Efficient and Productive Fuzzy Inference." FUZZ-IEEE 2023, doi 10.1109/FUZZ52849.2023.10309777. | [arXiv:2306.10316](https://arxiv.org/abs/2306.10316) |
| `2023-qu-fuzzy-rl-flock.pdf` | Qu, S., Abouheaf, M., Gueaieb, W., Spinello, D. (2023). "An Adaptive Fuzzy Reinforcement Learning Cooperative Approach for the Autonomous Control of Flock Systems." doi 10.1109/ICRA48506.2021.9561204. | [arXiv:2303.09946](https://arxiv.org/abs/2303.09946) |
| `2025-gu-interpretable-tsk-clustering.pdf` | Gu, S., Wang, Y., Chou, Y., Cong, J., Lu, M., Jiao, Z. (2025). "Interpretable Style Takagi-Sugeno-Kang Fuzzy Clustering." | [arXiv:2504.05125](https://arxiv.org/abs/2504.05125) |
| `2026-wan-fuz-rl-safe-rl.pdf` | Wan, X., Yang, C., Yang, C., Song, J., Sun, M. (2026). "Fuz-RL: A Fuzzy-Guided Robust Framework for Safe Reinforcement Learning under Uncertainty." | [arXiv:2602.20729](https://arxiv.org/abs/2602.20729) |

### Closed-access — no legal free copy located

These are cited in the v2 investigation but cannot be vendored without a
publisher subscription. Title, DOI, and one-line summary preserved here so
the bibliography is complete even without the PDF.

| Citation | DOI / Link | Why we cite it |
|----------|-----------|----------------|
| Zadeh, L. A. (1965). "Fuzzy Sets." *Information and Control* 8(3), pp. 338–353. | [doi:10.1016/S0019-9958(65)90241-X](https://doi.org/10.1016/S0019-9958(65)90241-X) | Founding paper of fuzzy logic. Defines grade-of-membership. |
| Mamdani, E. H. & Assilian, S. (1975). "An Experiment in Linguistic Synthesis with a Fuzzy Logic Controller." *International Journal of Man-Machine Studies* 7(1), pp. 1–13. | [doi:10.1016/S0020-7373(75)80002-2](https://doi.org/10.1016/S0020-7373(75)80002-2) | Canonical Mamdani inference pipeline. |
| Takagi, T. & Sugeno, M. (1985). "Fuzzy Identification of Systems and Its Applications to Modeling and Control." *IEEE Trans. Systems, Man, Cybernetics* 15(1), pp. 116–132. | [doi:10.1109/TSMC.1985.6313399](https://doi.org/10.1109/TSMC.1985.6313399) | TSK fuzzy model. Rule surface as a patchwork of linear consequents. |
| Jang, J.-S. R. (1993). "ANFIS: Adaptive-Network-based Fuzzy Inference System." *IEEE Trans. Systems, Man, Cybernetics* 23(3), pp. 665–685. | [doi:10.1109/21.256541](https://doi.org/10.1109/21.256541) | Five-layer learnable fuzzy network. Backprop on membership functions. |
| Lim, B. et al. (2023). "Reinforcement Learning with Takagi-Sugeno-Kang Fuzzy Systems." *Complex Engineering Systems*. | [doi:10.20517/ces.2023.11](https://doi.org/10.20517/ces.2023.11) | Actor-critic + DQN on TSK/ANFIS. XFC 2022 Asteroid Smasher. |

## Verification status of v1 / critique claims

The original investigation flagged several citations as "needs verification."
This vendoring pass resolved them:

- ✅ **Fuz-RL 2026 (arXiv 2602.20729)** — **REAL**. The critique's flag of "possibly hallucinated" was over-cautious; the paper exists with all the claimed authors and topic.
- ✅ **Adaptive Fuzzy RL for Flock (arXiv 2303.09946)** — **REAL**. Verified title and authors match v1's claim.
- ✅ **Interpretable Style TSK Fuzzy Clustering (arXiv 2504.05125)** — **REAL**.
- ✅ **TSK-RL (doi 10.20517/ces.2023.11)** — **REAL**. Title differs slightly from v1's framing.
- ✅ **All five seminal classics** — **REAL**, DOIs resolve via OpenAlex.
- ⚠️ **TSK high-dim multilabel (doi 10.1109/TFUZZ.2024.3385464)** — OpenAlex returned no record. Treat as unconfirmed.
- ⚠️ **Type-3 UAV (Springer, "Guo et al. 2024")** — Vague attribution in v1; no DOI verified. Treat as unconfirmed.

Update the critique (`2026-05-23-fuzzy-logic-visualization-gaps-critique.md`,
§1) to reflect that Fuz-RL is in fact real.
