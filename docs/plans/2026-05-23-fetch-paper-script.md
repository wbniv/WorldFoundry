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
