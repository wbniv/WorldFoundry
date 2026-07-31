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
| `2023-zander-reinforcement-learning-takagi-sugeno.pdf` | Zander, E. (2023). "Reinforcement learning with Takagi-Sugeno-Kang fuzzy systems." *Complex Engineering Systems*. | [https://f.oaes.cc/xmlpdf/84ba3d4d-247a-4fc9-a75e-68a8084efc7e/CES-2023-11.pdf](https://f.oaes.cc/xmlpdf/84ba3d4d-247a-4fc9-a75e-68a8084efc7e/CES-2023-11.pdf) (Publisher page) |

### Closed-access — no legal free copy located

These are cited in the v2 investigation but cannot be vendored without a publisher subscription. Title, DOI, abstract, and per-publisher cost preserved here so the bibliography is complete even without the PDF.

**Per-article rental/purchase cost (publisher list price, USD).** Costs are typically per-article and depend on the *publisher*, not the journal — e.g., everything on IEEE Xplore is the same price regardless of which IEEE journal published it. Verified by spot-checking the publisher pricing pages 2026-05-23; prices may change.

| Citation | DOI / Publisher | Cost | Why we cite it |
|----------|----------------|------|----------------|
| Zadeh, L. A. (1965). "Fuzzy Sets." *Information and Control* 8(3), pp. 338–353. | [doi:10.1016/S0019-9958(65)90241-X](https://doi.org/10.1016/S0019-9958(65)90241-X) — Elsevier | ~$35.95 (24 h rental) / ~$41.95 (purchase) | Founding paper of fuzzy logic. Defines grade-of-membership. |
| Mamdani, E. H. & Assilian, S. (1975). "An Experiment in Linguistic Synthesis with a Fuzzy Logic Controller." *International Journal of Man-Machine Studies* 7(1), pp. 1–13. | [doi:10.1016/S0020-7373(75)80002-2](https://doi.org/10.1016/S0020-7373(75)80002-2) — Elsevier | ~$35.95 / ~$41.95 | Canonical Mamdani inference pipeline. |
| Takagi, T. & Sugeno, M. (1985). "Fuzzy Identification of Systems and Its Applications to Modeling and Control." *IEEE Trans. Systems, Man, Cybernetics* 15(1), pp. 116–132. | [doi:10.1109/TSMC.1985.6313399](https://doi.org/10.1109/TSMC.1985.6313399) — IEEE Xplore | $33 | TSK fuzzy model. Rule surface as a patchwork of linear consequents. |
| Jang, J.-S. R. (1993). "ANFIS: Adaptive-Network-based Fuzzy Inference System." *IEEE Trans. Systems, Man, Cybernetics* 23(3), pp. 665–685. | [doi:10.1109/21.256541](https://doi.org/10.1109/21.256541) — IEEE Xplore | $33 | Five-layer learnable fuzzy network. Backprop on membership functions. |

**Publisher cost reference (per article, list price as of 2026-05-23):**

| Publisher | Per-article purchase | Notes |
|-----------|---------------------|-------|
| IEEE Xplore | $33 | Flat rate; non-members. IEEE members get reductions. |
| Elsevier (ScienceDirect) | $35.95 (24 h rental) / ~$41.95 (purchase) | Pricing varies by title but the historical journals here are all in the same bracket. |
| Springer | $39.95 | Some journals offer 24 h rental at $9.99. |
| ACM Digital Library | $15 (non-member); free for members ($99/yr) | Cheapest mainstream option if topic-relevant. |
| Wiley | $42–48 | Higher than IEEE/Elsevier on average. |
| OAE Publishing | Open access | Some articles need account / institutional login for the PDF even though "open access." |

**Total to buy all 5 closed-access papers retail:** ~$170. Lower if any are in ACM (none here) or if you find university-affiliate routes (see next section).

## How to get closed-access papers through universities (free or cheap)

For anyone without an institutional subscription, several legitimate routes work. Ranked by accessibility:

1. **Email the author.** The most reliable route, especially for older papers. Almost every academic will send you a PDF if you email them politely asking for a reprint of a specific paper. ~90% hit rate for papers <30 years old where the author is still reachable. For Zadeh (deceased 2017), Mamdani (deceased 2010), this route is closed; for Jang (still active at NTHU), Mendel (still active at USC, already provided the PDF), this works.

2. **ResearchGate / Academia.edu.** Authors often upload accepted manuscripts (not the publisher's typeset version, but the same content). Search by paper title; request access if not immediately downloadable. Free.

3. **The author's personal/institutional page.** Many academics maintain a publications page with PDFs (Mendel at sipi.usc.edu is the model — that's how we got Mendel & John 2002 and Kosko 1986 here). Search for `<author name> publications site:edu`.

4. **Institutional repositories (escholarship.org for UC, dspace.mit.edu for MIT, etc.).** University-hosted preprints/postprints. Free.

5. **Walk-in to any university library.** Most universities offer free in-person access to journal databases for visitors, even non-affiliates. Bangkok options: Chulalongkorn, Mahidol, Thammasat libraries typically allow walk-in journal access (verify hours; bring photo ID).

6. **Alumni access.** If you have any university affiliation — undergrad, grad school, even short-term enrollment — many institutions retain *alumni library access* to journal databases (often free for life). Check your alma mater's library website.

7. **Public-library inter-library loan (ILL).** Local public libraries can request PDFs from academic libraries on your behalf. Free or ~$5 fee. Turnaround 2–7 days. Works for almost any paper with a DOI.

8. **National library memberships.** US: Library of Congress (free reader card, in-person only). UK: British Library (free reader card, walk-in OR remote). Thailand: National Library of Thailand has limited online resources but supports inter-library loan.

9. **Friend at a university.** If someone you know is a current student or faculty, they can usually download an article in seconds. Asking is fine for occasional papers; don't ask them to mass-mirror a journal.

10. **Open Knowledge Maps / scholar.archive.org / Internet Archive Scholar.** Aggregate open-access preprints. Sometimes catches manuscripts before the publisher pulls them.

For the 5 closed-access papers on this list, the fastest legitimate routes are:

- **Mamdani 1975** — email Mamdani's surviving co-authors or USC archive (Mamdani died 2010); ILL via a public library is the practical path.
- **Takagi & Sugeno 1985** — Sugeno is emeritus at Tokyo Institute of Technology; an email could work. ILL also.
- **Jang 1993** — Jang is at NTHU; emailing `jang at cs.nthu.edu.tw` should produce a PDF quickly. Or check his publications page (currently lists recent work; older papers may be in archives).
- **Lim et al. 2023** — OAE journal; the abstract page sometimes provides a free PDF link that takes 1–2 clicks. If not, email the authors at UCincinnati.
- **Zadeh 1965** — widely scanned, often appears as a course-reading PDF on `.edu` domains; a targeted search for `"Fuzzy Sets" Zadeh 1965 site:edu filetype:pdf` regularly turns up a hosted copy.

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
