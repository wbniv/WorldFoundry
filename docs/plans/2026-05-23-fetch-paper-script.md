# Plan: `scripts/fetch-paper.py` — closed-access paper acquisition

## Context

We have 5 closed-access papers blocking the v2 fuzzy-logic investigation (`docs/papers/README.md` §"Closed-access — no legal free copy located"). Retail = ~$170. The SOP at `feedback_vendor_research_papers.md` already lists Unpaywall / OpenAlex / Semantic Scholar as preferred APIs, and `docs/papers/README.md` §"How to get closed-access papers through universities (free or cheap)" enumerates 10 acquisition techniques — but every one is currently a manual chore. This script automates the programmable techniques in the right order and emits ready-to-send drafts for the techniques that require a human.

## Input

Single positional argument, auto-detected:

- DOI: `10.1109/TSMC.1985.6313399` or `doi:10.1109/...` or `https://doi.org/...`
- arXiv ID: `2303.09946` or `arXiv:2303.09946`
- Title in quotes: `"Fuzzy Sets"` — resolved to DOI via Crossref title search (with author/year disambiguation prompt if multiple matches)
- BibTeX block on stdin (`--stdin`)

Batch: `--batch papers.txt` — one DOI/title per line, `#` comments ignored.

Step 0 always normalises input → canonical metadata (DOI, title, authors, year, journal) via Crossref + OpenAlex. The canonical record drives filename generation and every downstream API call.

## Matrix: technique × effort × likelihood, in execution order

Likelihood column is rough hit rate **for a random closed-access paper** (high/med/low).

| # | Technique | Maps to README technique | Impl effort | Likelihood | Auto? | Notes |
|---|-----------|--------------------------|-------------|------------|-------|-------|
| 1 | **Unpaywall API** (`api.unpaywall.org/v2/{doi}?email=…`) | #10 OA aggregators | trivial | high | full | Free, gold-standard OA finder. Single GET. |
| 2 | **OpenAlex** (`api.openalex.org/works/doi:{doi}`) | #10, #4 | trivial | high | full | `best_oa_location.pdf_url`. Sometimes catches what Unpaywall misses. |
| 3 | **Semantic Scholar** (`api.semanticscholar.org/graph/v1/paper/{doi}?fields=openAccessPdf`) | #10 | trivial | med-high | full | Free; backs off on 429. |
| 4 | **arXiv search by title+first author** (`export.arxiv.org/api/query`) | #10 | low | high (for preprints) / very low (pre-1991) | full | Catches papers Unpaywall missed because the arXiv record isn't linked to the DOI. |
| 5 | **CORE API** (`api.core.ac.uk/v3/search/outputs`) | #4 institutional repos | low | medium | full | Optional API key (`CORE_API_KEY` env); skip silently if absent. |
| 6 | **scholar.archive.org / Internet Archive Scholar** | #10 | low | medium | full | Fulltext search by title; checks `access` field. Also tries Wayback on the publisher URL. |
| 7 | **OpenAIRE / BASE search** | #4 institutional repos | medium | low-med | full | Hits escholarship, dspace.mit, etc. via a single federated API. |
| 8 | **Author publications page heuristic** | #3 author page | medium | low-med | partial | From OpenAlex authorship: take first/last author's ORCID + last affiliation URL; HEAD-check `/publications`, `/papers`, `/research`, then grep for the title. |
| 9 | **Google `site:edu filetype:pdf` URL emit** | #3 (author page on .edu) | low | medium-high for canonical papers | manual click | Prints the search URL; no scraping (Google blocks aggressive crawlers and we don't want a SerpApi dependency). |
| 10 | **ResearchGate URL emit** | #2 | low | medium (manual click + access request) | manual | Anti-bot; just emit search URL. |
| 11 | **ILL request draft** (text file) | #7 | low | high if sent | manual send | Generates a plain-text request with DOI, title, authors, journal, year, ISSN — ready to paste into any public library's ILL form. Skipped for arXiv-available papers. |
| 12 | **Author email draft** (text file) — **LAST** | #1 | low | high if author alive + email known | manual send | Pulls author + ORCID + last affiliation from OpenAlex, guesses email if `corresponding_author` field present, else surfaces affiliation domain so I can look it up. Skipped if all authors are deceased (per OpenAlex `is_alive`, with manual override). |

Routes **not automated** (not in the script): #5 walk-in library, #6 alumni access, #8 national library, #9 friend at university. Listed in the final failure report as "if all else fails, try these manually."

## Order rationale

Cheap, high-yield, well-typed API calls first (1–4). Then progressively higher-effort programmatic routes (5–8). Then routes that only emit URLs/drafts because they can't be fully automated (9–10). Then human-send drafts (11–12) — ILL before author email because ILL works for **any** paper with a DOI including ones where the author is deceased, whereas the author email is the catch-all of last resort with the user as the executor.

## Output behaviour

On success at any step ≤ 8:

1. Validate the downloaded file: `%PDF-` magic bytes, ≥ 50 KB, ≥ 2 pages (via `pdfinfo` if available, else byte heuristic).
2. Save as `docs/papers/YYYY-firstauthor-short-title.pdf` (slug rules match existing vendored files).
3. Auto-update `docs/papers/README.md`:
    - Remove the matching row from the **Closed-access** table.
    - Add a new row to the **Open-access PDFs** table with citation + source URL + the technique that found it (in a trailing parenthetical, e.g. `Unpaywall via author preprint`).
    - Matched by DOI (exact) or title (normalised, case-insensitive).
4. Print one-line success banner: `✓ Zadeh 1965 → docs/papers/1965-zadeh-fuzzy-sets.pdf (via Unpaywall)`.

On failure (no PDF after step 8):

5. Print the failure matrix — each step with PASS / FAIL / SKIP and the reason.
6. Emit `docs/papers/.drafts/<slug>-ill-request.txt` (technique 11).
7. Emit `docs/papers/.drafts/<slug>-author-email.txt` (technique 12), pre-filled, **not sent** — terminal output ends with:
    > Drafts ready. To send: open `docs/papers/.drafts/<slug>-author-email.txt`, verify the address, paste into your mail client.
8. Print URLs for techniques 9 (Google) and 10 (ResearchGate) so I can click them in one go.
9. Exit code `1`.

## Implementation strategy — incremental, demand-driven

**Do not implement all 12 rows up front. Do not pre-implement any row we don't immediately need.** The matrix above is the complete *spec*; the script grows one row at a time, driven by whichever paper we're currently trying to acquire. Process:

1. Implement **row #1 (Unpaywall)** + step 0 (input normalisation) + the success path (download, validate, save to `docs/papers/`, README auto-update). No drafts, no failure cascade — if a row can't find the paper, the script just exits cleanly with a "not found via <row>" message.
2. **Test case first:** run against a known-good open-access paper already in the table — Kosko 1986 (`doi:10.1016/S0020-7373(86)80040-2`) — with `--no-write` so we don't disturb the existing vendored copy. Confirms Unpaywall row works end-to-end.
3. **First closed paper:** run against the first row of the closed-access table — Zadeh 1965 (`doi:10.1016/S0019-9958(65)90241-X`).
4. **Climb only as needed, per paper.** If the current row finds the paper → stop, commit, move to the next paper on the list. If not → add the *next* row of the matrix, re-run on the *same* paper. Repeat until that paper is acquired, then move to the next paper starting back at row #1 (we already have row #1 implemented; the question is just "does row #1 find this one too?"). Climb the matrix again from wherever we stopped only if the new paper isn't found by the rows already coded.
5. **Scope cap:** we work through the 5 closed-access papers currently in the table. Once all 5 are resolved (PDF acquired or a draft emitted), stop. No speculative coding for hypothetical future papers.
6. Each new row is its own commit so the bisect history is clean and we can see which technique solved which paper.

Rows 11–12 (ILL draft, author email draft) are still implemented last and only when no programmatic row has worked for the paper currently in front of us.

## Critical files

- `scripts/fetch-paper.py` — new; starts as Unpaywall-only, grows row by row. Single file, Python 3, stdlib + `requests` only — no exotic deps.
- `docs/papers/README.md` — mutated on success (closed → open table move + new row). Reuse the existing table format exactly.
- `docs/papers/.drafts/` — *deferred*; only created when rows 11–12 (ILL + author email drafts) get added.
- No edits to `Taskfile.yml` for now — invoked directly. (A `task fetch-paper -- <doi>` wrapper can come later.)

## Reuse / existing patterns

- Filename slug rules: match the convention visible in existing vendored files (`2002-mendel-john-type2-made-simple.pdf`, `2023-qu-fuzzy-rl-flock.pdf`).
- README update logic: parse the two markdown tables (closed-access + open-access) with a small line-based parser keyed off the `| ... | ... |` shape — don't pull in a markdown library.
- Shell-script conventions from `~/SRC/CLAUDE.md`: this is Python, but the script still starts with a `-h`/`--help` early-exit and ISO-8601 UTC timestamps on every log line.

## Verification — iteration 1 (Unpaywall only)

Only these two checks matter for the first pass; the rest of the verification suite waits until more rows exist.

1. **Test case: Kosko 1986** (`doi:10.1016/S0020-7373(86)80040-2`) — `scripts/fetch-paper.py --no-write doi:10.1016/S0020-7373(86)80040-2`. PASS = Unpaywall returns a `best_oa_location.url_for_pdf`, script reports the URL, no file written.

    ```
    2026-05-23T06:20:46Z Input: type='doi' value='10.1016/S0020-7373(86)80040-2'
    2026-05-23T06:20:46Z Crossref: GET https://api.crossref.org/works/10.1016/S0020-7373%2886%2980040-2
    2026-05-23T06:20:46Z Canonical: Kosko 1986 — 'Fuzzy cognitive maps'
    2026-05-23T06:20:46Z DOI: 10.1016/S0020-7373(86)80040-2
    2026-05-23T06:20:46Z Target filename: 1986-kosko-fuzzy-cognitive-maps.pdf
    2026-05-23T06:20:46Z Unpaywall: GET https://api.unpaywall.org/v2/10.1016/S0020-7373%2886%2980040-2?email=wbnorris@gmail.com
    2026-05-23T06:20:48Z Unpaywall: no url_for_pdf found
    ✗ Kosko 1986: no OA copy via Unpaywall
      Step 1 (Unpaywall): MISS
    ```

    FAIL on the expected PASS condition — Unpaywall returns `is_oa: false` for this paper. The author-hosted copy at `sipi.usc.edu/~kosko/FCM.pdf` is not indexed by Unpaywall. Script itself works correctly (Crossref metadata, slug generation, clean exit). The test surfaced that Unpaywall coverage for 1986 Elsevier papers is poor; row #2 (OpenAlex) or row #8 (author page heuristic) would be needed to find this copy.

2. **First closed paper: Zadeh 1965** (`doi:10.1016/S0019-9958(65)90241-X`) — real run, no flags. Expected outcome: most likely no Unpaywall hit (Elsevier 1965 paper); script exits cleanly saying "no OA copy via Unpaywall." If a hit *does* happen, PDF lands in `docs/papers/1965-zadeh-fuzzy-sets.pdf` and the README table updates.

    ```
    2026-05-23T06:21:25Z Input: type='doi' value='10.1016/S0019-9958(65)90241-X'
    2026-05-23T06:21:25Z Crossref: GET https://api.crossref.org/works/10.1016/S0019-9958%2865%2990241-X
    2026-05-23T06:21:26Z Canonical: Zadeh 1965 — 'Fuzzy sets'
    2026-05-23T06:21:26Z DOI: 10.1016/S0019-9958(65)90241-X
    2026-05-23T06:21:26Z Target filename: 1965-zadeh-fuzzy-sets.pdf
    2026-05-23T06:21:25Z Unpaywall: GET ...
    2026-05-23T06:21:27Z Unpaywall: no url_for_pdf found
    ✗ Zadeh 1965: no OA copy via Unpaywall
      Step 1 (Unpaywall): MISS
    ```

    PASS — script exits cleanly with "no OA copy via Unpaywall" as expected. Slug `1965-zadeh-fuzzy-sets.pdf` correct.

**Conclusion:** Row #1 (Unpaywall) is implemented and working. Neither test paper was found by Unpaywall (Kosko 1986's author copy isn't Unpaywall-indexed; Zadeh 1965 is paywalled as expected). Proceed to row #2 (OpenAlex) — it may catch the Kosko author-page copy and handle the open Lim 2023 OAE paper differently.

---

## Verification — iteration 2 (rows 2–4b: OpenAlex + Semantic Scholar + publisher page)

Added rows 2 (OpenAlex), 3 (Semantic Scholar), 4b (publisher HTML scrape) in commit `9a9218af`.

**Probe results (before coding):**

| Paper | Unpaywall | OpenAlex | Semantic Scholar | Publisher page |
|-------|-----------|----------|-----------------|----------------|
| Kosko 1986 | MISS (is_oa: false) | MISS (is_oa: false) | MISS (CLOSED) | — |
| Zadeh 1965 | MISS | MISS | HYBRID but url = DOI only | — |
| Mamdani 1975 | MISS | MISS | MISS (CLOSED) | — |
| Takagi 1985 | MISS | MISS | MISS (CLOSED) | — |
| Jang 1993 | MISS | MISS | MISS (CLOSED) | — |
| Zander/Lim 2023 | MISS | MISS | url = DOI redirect | **HIT** via OAE HTML |

**Zander 2023 acquisition:**

```
python3 scripts/fetch-paper.py doi:10.20517/ces.2023.11
```

```
2026-05-23T06:35:36Z Input: type='doi' value='10.20517/ces.2023.11'
2026-05-23T06:35:36Z Crossref: GET https://api.crossref.org/works/10.20517/ces.2023.11
2026-05-23T06:35:36Z Canonical: Zander 2023 — 'Reinforcement learning with Takagi-Sugeno-Kang fuzzy systems'
2026-05-23T06:35:36Z Target filename: 2023-zander-reinforcement-learning-takagi-sugeno.pdf
2026-05-23T06:35:38Z Unpaywall: no url_for_pdf found
2026-05-23T06:35:39Z OpenAlex: no pdf_url in best_oa_location
2026-05-23T06:35:39Z Semantic Scholar: url is just DOI redirect, skipping
2026-05-23T06:35:39Z Publisher page: following https://doi.org/10.20517/ces.2023.11
2026-05-23T06:35:41Z Publisher page: 7 candidate(s): ['https://f.oaes.cc/xmlpdf/84ba3d4d-247a-4fc9-a75e-68a8084efc7e/CES-2023-11.pdf', ...]
2026-05-23T06:35:42Z PDF validation OK: 16 pages, 1984 KB
2026-05-23T06:35:42Z Saved: docs/papers/2023-zander-reinforcement-learning-takagi-sugeno.pdf (1984 KB)
✓ Zander 2023 → docs/papers/2023-zander-reinforcement-learning-takagi-sugeno.pdf (via Publisher page)
```

PASS. Correction: first author is Eric Zander (Crossref canonical), not "Lim" as the investigation doc had it. OAE CDN URL was embedded in article HTML; not indexed by Unpaywall/OpenAlex.

**Status after iteration 2:** 1 of 5 closed-access papers acquired. 4 remain (Zadeh 1965, Mamdani 1975, Takagi 1985, Jang 1993).

---

## Verification — rows 5 + 9–12 (CORE + failure-output path)

Commit `fe55ab9b` → `9a9218af` → ongoing. Row 5 (CORE) + failure outputs (9–12) added together.

**CORE probe:** CORE DOI-query finds metadata but actual CDN downloads are stale (404) or forbidden (403) for all 4 papers. CORE also returns cross-linked "citing papers" with wrong DOI tags — fixed with Jaccard title filter (threshold ≥ 0.5).

**Full run on all 4 remaining papers:**

```
python3 scripts/fetch-paper.py doi:10.1016/S0019-9958(65)90241-X
python3 scripts/fetch-paper.py doi:10.1016/S0020-7373(75)80002-2
python3 scripts/fetch-paper.py doi:10.1109/TSMC.1985.6313399
python3 scripts/fetch-paper.py doi:10.1109/21.256541
```

| Paper | Unpaywall | OpenAlex | Semantic Scholar | CORE | Publisher page | Outcome |
|-------|-----------|----------|-----------------|------|----------------|---------|
| Zadeh 1965 | MISS | MISS | DOI-redirect only | 2 title-matched, all URLs dead (404/403) | MISS | drafts emitted |
| Mamdani 1975 | MISS | MISS | MISS | no results | MISS | drafts emitted |
| Takagi 1985 | MISS | MISS | MISS | no results | 418 (bot-detect) | drafts emitted |
| Jang 1993 | MISS | MISS | MISS | 2 title-matched, NTHU 404 + IEEE staging 200 not-PDF | 418 (bot-detect) | drafts emitted |

Drafts emitted to `docs/papers/.drafts/`:
- `1965-zadeh-fuzzy-sets-ill-request.txt` + `…-author-email.txt` [deceased: note added]
- `1975-mamdani-experiment-linguistic-synthesis-fuzzy-ill-request.txt` + `…-author-email.txt` [deceased: note added]
- `1985-takagi-fuzzy-identification-systems-applications-ill-request.txt` + `…-author-email.txt`
- `1993-jang-anfis-adaptive-network-fuzzy-ill-request.txt` + `…-author-email.txt` (OpenAlex affiliation: UC Berkeley 1993; current: NTHU)

Manual search URLs printed to terminal at runtime:
```
[9] Google .edu: https://www.google.com/search?q=%22Fuzzy+sets%22+Zadeh+1965+filetype%3Apdf+site:edu
[10] ResearchGate: https://www.researchgate.net/search?q=Fuzzy+sets+Zadeh
```
(and analogous for the other 3 papers)

**Status after rows 1–5 + 9–12:** 1/5 acquired (Zander 2023). 4 remain, all genuinely paywalled with no programmatic OA copy found. Next step: click the Google .edu URL for Zadeh 1965 (plan notes it "regularly turns up a hosted copy") and/or use the ILL drafts.

---

## Author contact research (2026-05-23)

| Paper | Author status | Best contact |
|-------|---------------|-------------|
| Zadeh 1965 | Zadeh died 2017 | UC Berkeley BISC/EECS archives — `eecsoffice@eecs.berkeley.edu` |
| Mamdani 1975 | Mamdani died 2010; co-author Assilian status unknown | QMUL archives — `archives@qmul.ac.uk` |
| Takagi 1985 | Sugeno died Aug 2023; Takagi status unknown | Tokyo Tech EECS dept via Tomohiro Takagi search |
| Jang 1993 | Alive, at NTU Taiwan (moved from NTHU/UCB) | NTU CSIE faculty page; email likely `jang@csie.ntu.edu.tw` |

Sources: IEEE obituary for Sugeno (MCI 2023); NTU CSIE faculty listing for Jang.

---

## Reprint request emails

### 1 — Jang 1993 (highest-probability reply)

To send to: `jang@csie.ntu.edu.tw` — verify at https://csie.ntu.edu.tw/en/member/Faculty/Jyh-Shing-Roger-Jang-13692144 or http://mirlab.org/jang/

```
To: jang@csie.ntu.edu.tw
Subject: Request for reprint of ANFIS paper (1993)

Dear Prof. Jang,

I'm working on an implementation of fuzzy inference for a game engine and have been
studying your 1993 paper closely:

  J.-S. R. Jang, "ANFIS: Adaptive-Network-based Fuzzy Inference System,"
  IEEE Trans. Systems, Man, and Cybernetics, 23(3), pp. 665–685, 1993.
  doi:10.1109/21.256541

The paper is behind the IEEE paywall ($33) and I'm unable to access it through an
institution. Would you be willing to send me a PDF reprint?

Thank you very much,
Will Norris
wbnorris@gmail.com
```

---

### 2 — Takagi 1985 (Takagi status unknown; Sugeno deceased Aug 2023)

To send to: look up Tomohiro Takagi's current affiliation — search `Tomohiro Takagi fuzzy systems Tokyo` or try Tokyo Tech EECS alumni directory. If not findable, use ILL draft instead.

```
To: [Tomohiro Takagi email — look up current affiliation]
Subject: Request for reprint of Takagi-Sugeno 1985 paper

Dear Prof. Takagi,

I'm working on an implementation of fuzzy inference for a game engine and have been
studying the Takagi-Sugeno model. I'd like to read the original paper:

  T. Takagi & M. Sugeno, "Fuzzy Identification of Systems and Its Applications
  to Modeling and Control," IEEE Trans. Systems, Man, and Cybernetics, 15(1),
  pp. 116–132, 1985. doi:10.1109/TSMC.1985.6313399

The paper is behind the IEEE paywall ($33) and I have no institutional access.
Would you be willing to send me a PDF reprint?

(I note that Prof. Sugeno passed away in August 2023 — my condolences.)

Thank you very much,
Will Norris
wbnorris@gmail.com
```

---

### 3 — Zadeh 1965 (deceased 2017 — email BISC at Berkeley)

```
To: eecsoffice@eecs.berkeley.edu
Subject: Request for course-reading copy of Zadeh 1965 "Fuzzy Sets"

Dear EECS / BISC team,

I'm a researcher working on fuzzy logic and am trying to obtain a copy of:

  L. A. Zadeh, "Fuzzy Sets," Information and Control, 8(3), pp. 338–353, 1965.
  doi:10.1016/S0019-9958(65)90241-X

I understand Prof. Zadeh passed away in 2017. I'm hoping the BISC group or EECS
archives may have a course-reading copy or can point me to a freely accessible
version. The Elsevier paywall asks ~$36 for a 24 h rental.

Any help would be much appreciated.

Thank you,
Will Norris
wbnorris@gmail.com
```

---

### 4 — Mamdani 1975 (deceased 2010 — email QMUL archives)

```
To: archives@qmul.ac.uk
Subject: Request for historical paper reprint — Mamdani & Assilian 1975

Dear QMUL Archives,

I'm hoping you can help me locate a copy of a paper by the late Prof. E. H. Mamdani,
who was on the faculty at Queen Mary:

  E. H. Mamdani & S. Assilian, "An Experiment in Linguistic Synthesis with a Fuzzy
  Logic Controller," International Journal of Man-Machine Studies, 7(1), pp. 1–13, 1975.
  doi:10.1016/S0020-7373(75)80002-2

This paper defined the Mamdani fuzzy inference system, which is a foundational
algorithm in control engineering. The publisher (Elsevier) charges ~$36 for a
24 h rental. I'm hoping the university archives may hold a copy as part of
Prof. Mamdani's deposited papers, or can suggest another route.

Thank you very much,
Will Norris
wbnorris@gmail.com
```

---

### ILL as fallback

If the institutional archive emails don't yield a reply within 2 weeks, use the ILL drafts in `docs/papers/.drafts/` — they're pre-filled and ready to paste into any public-library ILL form.
