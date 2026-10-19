---
name: vendor-research-papers
description: "SOP — when an investigation cites academic papers, vendor open-access PDFs into the repo in the same commit"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ac975391-be78-4e9a-9979-d9fe03148827
---

When writing an investigation or any document that cites academic research papers, vendor the open-access PDFs into the repository in the same commit as the document.

**Why:** Without local copies, the bibliography rots — arXiv IDs hold up but author webpages move, journal links require institutional access, and "I had to check the paper" later turns into a wild Google chase. Vendoring also resolves citation-verification gaps cheaply: confirms the paper exists, confirms the authors are who you say they are, and surfaces "possibly hallucinated" subagent output before it costs trust. (Concrete case: 2026-05-23 fuzzy logic investigation flagged Fuz-RL 2026 as "possibly hallucinated" in self-critique, but vendoring confirmed it was real.)

**How to apply:** Apply whenever a document cites academic papers (any of: arXiv ID, DOI, journal name + year). Don't ask permission — vendor in the same commit as the doc, default location and naming as below.

## Location

- **Implementation-reference papers** (informed actual engine code): `engine/<component>/papers/`
  - Example: `engine/neural-forth/papers/` for the Bošnjak differentiable Forth papers behind `slot.c`.
- **Investigation-reference papers** (cited in `docs/investigations/`): `docs/papers/` (flat)
  - Filename: `YYYY-firstauthor-short-title.pdf` (e.g., `2002-mendel-john-type2-made-simple.pdf`, `2026-wan-fuz-rl-safe-rl.pdf`)

## Procedure

1. **Verify every citation exists** before downloading — check the actual title and authors match the claim. Subagents hallucinate.
2. **Download PDFs** preferring legitimate sources, in order of preference:
   - arXiv (`curl -sL -o name.pdf https://arxiv.org/pdf/<id>`)
   - Author personal/institutional pages (`sipi.usc.edu/~mendel/...`, `mirlab.org/jang/`)
   - Conference proceedings (NeurIPS, ICML, FUZZ-IEEE)
   - Institutional repos (escholarship.org, repositories.lib.utexas.edu)
   - Semantic Scholar / OpenAlex / Unpaywall — they aggregate `openAccessPdf` URLs.
3. **For closed-access papers** with no legitimate free copy: record citation, DOI, abstract in `README.md` of the papers dir. Don't use sci-hub or similar — questionable legally.
4. **Write a `README.md`** in the papers dir listing every file with full citation, source URL, and one-line summary of why it's cited.
5. **Verify each PDF** with `file <name>.pdf` — confirms it's actually a PDF and shows page count. Multi-page real papers; 1–2 page hits are usually citation lists or error pages.
6. **Cross-link** from the investigation doc to the papers dir (`See docs/papers/README.md`).

## Useful APIs

- OpenAlex: `https://api.openalex.org/works/doi:<DOI>` → returns `open_access.oa_url` and `best_oa_location.pdf_url` when available.
- Semantic Scholar: `https://api.semanticscholar.org/graph/v1/paper/search?query=...&fields=openAccessPdf` — same purpose.
- Unpaywall: `https://api.unpaywall.org/v2/<DOI>?email=...` — most reliable for "is there a legal free PDF anywhere."

## What not to vendor

- Books, textbooks, or anything not a single-paper PDF.
- Papers behind paywalls without a legitimate open-access source — record metadata only.
- Talks/slides/blog posts — link inline in the doc instead.
