#!/usr/bin/env python3
"""
fetch-paper.py — automated open-access paper acquisition.

Iteration 1: Unpaywall only (rows 2-12 deferred until needed).

Usage:
  fetch-paper.py [--no-write] <doi|arxiv-id|"quoted title">
  fetch-paper.py [--no-write] --batch <file>
  fetch-paper.py --stdin            # read BibTeX from stdin

Input is auto-detected:
  10.xxx/... or doi:10.xxx/... or https://doi.org/...  -> DOI
  NNNN.NNNNN or arXiv:NNNN.NNNNN                       -> arXiv ID
  "Quoted string"                                       -> title search
  --stdin                                               -> BibTeX on stdin
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse

try:
    import requests
except ImportError:
    sys.exit("requests is required: pip install requests")

EMAIL = "wbnorris@gmail.com"
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PAPERS_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "docs", "papers"))
README_PATH = os.path.join(PAPERS_DIR, "README.md")

_STOPWORDS = {
    "a", "an", "the", "of", "in", "for", "and", "or", "to", "with",
    "on", "at", "by", "its", "is", "as", "via", "from", "based",
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _ts():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg):
    print(f"{_ts()} {msg}", flush=True)


# ---------------------------------------------------------------------------
# Slug / filename generation
# ---------------------------------------------------------------------------

def _ascii(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _family_name(author_str):
    """Extract family name from 'Family, Given' or 'Given Family' formats."""
    s = author_str.strip()
    if "," in s:
        return s.split(",")[0].strip()
    parts = s.split()
    return parts[-1] if parts else s


def _title_words(title, n=4):
    words = re.split(r"\W+", title.lower())
    words = [_ascii(w) for w in words if w and w not in _STOPWORDS]
    return "-".join(words[:n])


def make_slug(canonical):
    year = str(canonical.get("year", "0000"))
    authors = canonical.get("authors", [])
    last = re.sub(r"[^a-z0-9]", "", _ascii(_family_name(authors[0])).lower()) if authors else "unknown"
    short = _title_words(canonical.get("title", "untitled"))
    return f"{year}-{last}-{short}"


# ---------------------------------------------------------------------------
# Input detection + normalisation
# ---------------------------------------------------------------------------

def _normalise_doi(raw):
    raw = raw.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "DOI:"):
        if raw.lower().startswith(prefix.lower()):
            return raw[len(prefix):]
    return raw


def detect_input(arg):
    """Return (type, normalised_value)."""
    s = arg.strip()
    # explicit doi: prefix or full URL
    if re.match(r"^(doi:|https?://doi\.org/)", s, re.IGNORECASE):
        return "doi", _normalise_doi(s)
    # bare DOI
    if re.match(r"^10\.\d{4,}/", s):
        return "doi", s
    # arXiv
    if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", s) or s.lower().startswith("arxiv:"):
        return "arxiv", s.lower().replace("arxiv:", "").strip()
    # quoted title
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return "title", s[1:-1]
    # fallback: treat as title
    return "title", s


def _parse_bibtex_doi(text):
    m = re.search(r"\bdoi\s*=\s*[{\"](.*?)[}\"]", text, re.IGNORECASE)
    if m:
        return _normalise_doi(m.group(1).strip())
    return None


# ---------------------------------------------------------------------------
# Metadata resolution
# ---------------------------------------------------------------------------

def _crossref_item_to_canonical(doi, item):
    authors_raw = item.get("author", [])
    authors = []
    for a in authors_raw:
        family = a.get("family", "")
        given = a.get("given", "")
        entry = family
        if given:
            entry = f"{family}, {given}"
        if entry:
            authors.append(entry)
    issued = (item.get("issued") or {}).get("date-parts", [[None]])[0]
    year = str(issued[0]) if issued and issued[0] else "????"
    title = (item.get("title") or ["Untitled"])[0]
    journal = (item.get("container-title") or [""])[0]
    return {
        "doi": doi,
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
    }


def fetch_crossref_doi(doi):
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='/')}"
    log(f"Crossref: GET {url}")
    r = requests.get(url, timeout=15,
                     headers={"User-Agent": f"fetch-paper/1 (mailto:{EMAIL})"})
    if r.status_code != 200:
        log(f"Crossref: HTTP {r.status_code}")
        return None
    item = r.json().get("message", {})
    return _crossref_item_to_canonical(doi, item)


def fetch_crossref_title(title):
    url = "https://api.crossref.org/works"
    params = {
        "query.title": title,
        "rows": 5,
        "select": "DOI,title,author,issued,container-title",
    }
    log(f"Crossref title search: {title!r}")
    r = requests.get(url, params=params, timeout=15,
                     headers={"User-Agent": f"fetch-paper/1 (mailto:{EMAIL})"})
    if r.status_code != 200:
        log(f"Crossref title search: HTTP {r.status_code}")
        return None
    items = r.json().get("message", {}).get("items", [])
    if not items:
        log("Crossref title search: no results")
        return None
    if len(items) == 1:
        return fetch_crossref_doi(items[0]["DOI"])
    # multiple matches — prompt
    print("Multiple matches found:")
    for i, item in enumerate(items, 1):
        t = (item.get("title") or ["?"])[0]
        issued = (item.get("issued") or {}).get("date-parts", [[None]])[0]
        year = str(issued[0]) if issued and issued[0] else "????"
        authors_raw = item.get("author", [])
        first = authors_raw[0].get("family", "?") if authors_raw else "?"
        print(f"  {i}. {t!r} — {first}, {year}")
    choice = input("Enter number (or q to quit): ").strip()
    if choice.lower() == "q":
        return None
    try:
        return fetch_crossref_doi(items[int(choice) - 1]["DOI"])
    except (ValueError, IndexError):
        log("Invalid selection.")
        return None


def fetch_arxiv(arxiv_id):
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(arxiv_id)}"
    log(f"arXiv: GET {url}")
    r = requests.get(url, timeout=15)
    if r.status_code != 200:
        log(f"arXiv: HTTP {r.status_code}")
        return None
    title_m = re.search(r"<entry>.*?<title>(.*?)</title>", r.text, re.DOTALL)
    author_ms = re.findall(r"<author>\s*<name>(.*?)</name>", r.text)
    published_m = re.search(r"<published>(\d{4})", r.text)
    if not title_m:
        log("arXiv: could not parse entry")
        return None
    title = re.sub(r"\s+", " ", title_m.group(1)).strip()
    year = published_m.group(1) if published_m else "????"
    return {
        "doi": None,
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": author_ms,
        "year": year,
        "journal": "arXiv",
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
    }


# ---------------------------------------------------------------------------
# Rows 1–3: OA aggregator APIs
# ---------------------------------------------------------------------------

def try_unpaywall(doi):
    url = (f"https://api.unpaywall.org/v2/"
           f"{urllib.parse.quote(doi, safe='/')}?email={EMAIL}")
    log(f"Unpaywall: GET {url}")
    r = requests.get(url, timeout=15)
    if r.status_code == 404:
        log("Unpaywall: DOI not found (404)")
        return None
    if r.status_code != 200:
        log(f"Unpaywall: HTTP {r.status_code}")
        return None
    data = r.json()
    # try best_oa_location first
    best = data.get("best_oa_location") or {}
    pdf_url = best.get("url_for_pdf")
    if not pdf_url:
        for loc in data.get("oa_locations", []):
            if loc.get("url_for_pdf"):
                pdf_url = loc["url_for_pdf"]
                log(f"Unpaywall: url_for_pdf from oa_locations: {pdf_url}")
                break
    if pdf_url:
        log(f"Unpaywall: HIT → {pdf_url}")
    else:
        log("Unpaywall: no url_for_pdf found")
    return pdf_url


def try_openalex(doi):
    """Row 2: OpenAlex best_oa_location.pdf_url."""
    url = f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi, safe='/')}"
    log(f"OpenAlex: GET {url}")
    r = requests.get(url, timeout=15,
                     headers={"User-Agent": f"fetch-paper/1 (mailto:{EMAIL})"})
    if r.status_code != 200:
        log(f"OpenAlex: HTTP {r.status_code}")
        return None
    data = r.json()
    best = data.get("best_oa_location") or {}
    pdf_url = best.get("pdf_url")
    if pdf_url:
        log(f"OpenAlex: HIT → {pdf_url}")
    else:
        log("OpenAlex: no pdf_url in best_oa_location")
    return pdf_url


def try_semantic_scholar(doi):
    """Row 3: Semantic Scholar openAccessPdf.url."""
    url = (f"https://api.semanticscholar.org/graph/v1/paper/"
           f"{urllib.parse.quote(doi, safe='/')}?fields=openAccessPdf,title")
    log(f"Semantic Scholar: GET {url}")
    r = requests.get(url, timeout=15)
    if r.status_code == 429:
        log("Semantic Scholar: 429 rate-limited, skipping")
        return None
    if r.status_code != 200:
        log(f"Semantic Scholar: HTTP {r.status_code}")
        return None
    data = r.json()
    pdf_info = data.get("openAccessPdf") or {}
    pdf_url = pdf_info.get("url")
    if pdf_url and pdf_url.startswith("https://doi.org/"):
        log(f"Semantic Scholar: url is just DOI redirect ({pdf_url}), skipping")
        return None
    if pdf_url:
        log(f"Semantic Scholar: HIT → {pdf_url}")
    else:
        log("Semantic Scholar: no openAccessPdf.url")
    return pdf_url


def try_publisher_page(doi):
    """Row 4b: Follow DOI redirect → scrape publisher HTML for embedded PDF links.

    Catches OA publishers (OAE, etc.) that embed the PDF URL in the article
    HTML but don't register it with Unpaywall/OpenAlex.
    """
    doi_url = f"https://doi.org/{urllib.parse.quote(doi, safe='/')}"
    log(f"Publisher page: following {doi_url}")
    try:
        r = requests.get(doi_url, timeout=20, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
    except requests.RequestException as e:
        log(f"Publisher page: request failed: {e}")
        return None
    if r.status_code != 200:
        log(f"Publisher page: HTTP {r.status_code}")
        return None
    if "text/html" not in r.headers.get("content-type", ""):
        log("Publisher page: not HTML, skipping")
        return None
    # extract all https PDF links from the HTML
    candidates = re.findall(r'["\'](https?://[^"\']*\.pdf[^"\']*)["\']', r.text)
    # also catch CDN/download URLs that don't end in .pdf explicitly
    candidates += re.findall(
        r'["\'](https?://[^"\']*(?:xmlpdf|fulltext|download/pdf)[^"\']*)["\']', r.text
    )
    # deduplicate, prefer CDN/download URLs over thumbnails/images
    seen = set()
    ranked = []
    for u in candidates:
        if u in seen:
            continue
        seen.add(u)
        # deprioritize images and tiny assets
        if re.search(r"\.(png|jpg|gif|svg|ico|css|js)", u, re.IGNORECASE):
            continue
        ranked.append(u)
    if not ranked:
        log("Publisher page: no PDF URLs found in HTML")
        return None
    log(f"Publisher page: {len(ranked)} candidate(s): {ranked[:3]}")
    # return first (will be validated by caller)
    return ranked[0]


# ---------------------------------------------------------------------------
# Download + validate
# ---------------------------------------------------------------------------

def download_pdf(pdf_url):
    log(f"Downloading: {pdf_url}")
    r = requests.get(pdf_url, timeout=60, allow_redirects=True,
                     headers={"User-Agent": f"fetch-paper/1 (mailto:{EMAIL})"})
    if r.status_code != 200:
        log(f"Download failed: HTTP {r.status_code}")
        return None
    return r.content


def validate_pdf(data):
    """Return (ok: bool, reason: str)."""
    if not data:
        return False, "empty download"
    if data[:5] != b"%PDF-":
        return False, f"not a PDF (magic bytes: {data[:8]!r})"
    size_kb = len(data) // 1024
    if len(data) < 50 * 1024:
        return False, f"too small ({size_kb} KB, need ≥50 KB)"
    # try pdfinfo via temp file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(data)
        tmp_path = tf.name
    try:
        result = subprocess.run(
            ["pdfinfo", tmp_path],
            capture_output=True, timeout=10,
        )
        m = re.search(rb"Pages:\s+(\d+)", result.stdout)
        if m:
            pages = int(m.group(1))
            if pages < 2:
                return False, f"only {pages} page(s) per pdfinfo"
            return True, f"{pages} pages, {size_kb} KB"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    finally:
        os.unlink(tmp_path)
    # fallback: count /Page dictionary entries
    page_count = len(re.findall(rb"/Type\s*/Page\b", data))
    if page_count < 1:
        # looser scan
        page_count = data.count(b"/Page")
    if page_count < 2:
        return False, f"page heuristic: {page_count} /Page token(s)"
    return True, f"~{page_count} pages (heuristic), {size_kb} KB"


# ---------------------------------------------------------------------------
# README.md update
# ---------------------------------------------------------------------------

def _build_citation(canonical):
    authors = canonical.get("authors", [])
    first = authors[0] if authors else "Unknown"
    # normalise to "Family, I." style for the first author
    if "," in first:
        fam, giv = first.split(",", 1)
        initials = " ".join(p[0] + "." for p in giv.split() if p)
        first_fmt = f"{fam.strip()}, {initials}".strip(", ")
    else:
        parts = first.split()
        if len(parts) >= 2:
            first_fmt = f"{parts[-1]}, {'. '.join(p[0] for p in parts[:-1])}."
        else:
            first_fmt = first
    year = canonical.get("year", "????")
    title = canonical.get("title", "Untitled")
    journal = canonical.get("journal", "")
    return f'{first_fmt} ({year}). "{title}." *{journal}*.'


def update_readme(canonical, slug, pdf_url, technique):
    doi = (canonical.get("doi") or "").strip().lower()
    with open(README_PATH, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    # remove matching closed-access row (match by DOI)
    removed = False
    new_lines = []
    for line in lines:
        if doi and doi in line.lower() and line.strip().startswith("|"):
            log(f"README: removing closed-access row (doi:{doi})")
            removed = True
            continue
        new_lines.append(line)
    if not removed:
        log("README: WARNING — no matching closed-access row found; not removing")

    # build new open-access row
    citation = _build_citation(canonical)
    new_row = f"| `{slug}.pdf` | {citation} | [{pdf_url}]({pdf_url}) ({technique}) |\n"

    # insert after last data row of the open-access table
    oa_table_last = None
    in_oa = False
    for i, line in enumerate(new_lines):
        if "### Open-access PDFs" in line:
            in_oa = True
        if in_oa and "### Closed-access" in line:
            break
        if in_oa and line.strip().startswith("|"):
            oa_table_last = i

    if oa_table_last is not None:
        new_lines.insert(oa_table_last + 1, new_row)
        log(f"README: inserted open-access row after line {oa_table_last + 1}")
    else:
        log("README: WARNING — could not find open-access table; appending at end")
        new_lines.append(new_row)

    with open(README_PATH, "w", encoding="utf-8") as fh:
        fh.writelines(new_lines)


# ---------------------------------------------------------------------------
# Core per-paper logic
# ---------------------------------------------------------------------------

def process_one(arg, no_write=False, stdin_bibtex=None):
    """Process a single paper. Returns True on success (PDF acquired)."""

    # Step 0: input normalisation → canonical metadata
    if stdin_bibtex is not None:
        doi = _parse_bibtex_doi(stdin_bibtex)
        if not doi:
            log("ERROR: no DOI field found in BibTeX input")
            return False
        input_type, input_val = "doi", doi
    else:
        input_type, input_val = detect_input(arg)

    log(f"Input: type={input_type!r} value={input_val!r}")

    if input_type == "doi":
        canonical = fetch_crossref_doi(input_val)
        if not canonical:
            log(f"ERROR: could not resolve DOI via Crossref: {input_val!r}")
            return False
    elif input_type == "arxiv":
        canonical = fetch_arxiv(input_val)
        if not canonical:
            log(f"ERROR: could not resolve arXiv ID: {input_val!r}")
            return False
    elif input_type == "title":
        canonical = fetch_crossref_title(input_val)
        if not canonical:
            return False
    else:
        log(f"ERROR: unknown input type: {input_type!r}")
        return False

    doi = canonical.get("doi") or ""
    title = canonical.get("title", "Untitled")
    authors = canonical.get("authors", [])
    year = canonical.get("year", "????")
    first_author = _family_name(authors[0]) if authors else "Unknown"
    slug = make_slug(canonical)

    log(f"Canonical: {first_author} {year} — {title!r}")
    log(f"DOI: {doi or '(none)'}")
    log(f"Target filename: {slug}.pdf")

    # Rows 1–4b: try OA aggregators then publisher page scrape
    pdf_url = None
    technique = None
    matrix_log = []  # (row_name, result)

    if canonical.get("pdf_url"):
        pdf_url = canonical["pdf_url"]
        technique = "arXiv direct"
        log(f"Using direct arXiv PDF URL: {pdf_url}")
        matrix_log.append(("arXiv direct", "HIT"))
    else:
        for row_name, row_fn in [
            ("Unpaywall",       lambda: try_unpaywall(doi) if doi else None),
            ("OpenAlex",        lambda: try_openalex(doi) if doi else None),
            ("Semantic Scholar", lambda: try_semantic_scholar(doi) if doi else None),
            ("Publisher page",  lambda: try_publisher_page(doi) if doi else None),
        ]:
            result = row_fn()
            if result:
                pdf_url = result
                technique = row_name
                matrix_log.append((row_name, "HIT"))
                break
            else:
                matrix_log.append((row_name, "MISS"))

    if not pdf_url:
        print(f"✗ {first_author} {year}: no OA copy found")
        for name, status in matrix_log:
            print(f"  {name}: {status}")
        print(f"  (rows 5–12 not yet implemented)")
        return False

    # --no-write: dry run
    if no_write:
        print(f"✓ {first_author} {year} — would save as docs/papers/{slug}.pdf")
        print(f"  Source ({technique}): {pdf_url}")
        return True

    # Download
    data = download_pdf(pdf_url)
    ok, reason = validate_pdf(data)
    if not ok:
        log(f"PDF validation FAIL: {reason}")
        print(f"✗ {first_author} {year}: downloaded but invalid — {reason}")
        return False

    log(f"PDF validation OK: {reason}")

    # Save
    out_path = os.path.join(PAPERS_DIR, f"{slug}.pdf")
    if os.path.exists(out_path):
        log(f"WARNING: {out_path} already exists — overwriting")
    with open(out_path, "wb") as fh:
        fh.write(data)
    log(f"Saved: {out_path} ({len(data) // 1024} KB)")

    # Update README
    update_readme(canonical, slug, pdf_url, technique)

    print(f"✓ {first_author} {year} → docs/papers/{slug}.pdf (via {technique})")
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch open-access PDFs for academic papers (rows 1-4b: Unpaywall/OpenAlex/S2/publisher-page).",
        epilog=(
            "Examples:\n"
            "  fetch-paper.py doi:10.1016/S0020-7373(86)80040-2\n"
            "  fetch-paper.py --no-write doi:10.1016/S0020-7373(86)80040-2\n"
            "  fetch-paper.py 2303.09946\n"
            "  fetch-paper.py '\"Fuzzy Sets\"'\n"
            "  fetch-paper.py --batch papers.txt\n"
            "  fetch-paper.py --stdin < paper.bib"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", nargs="?", help="DOI, arXiv ID, or quoted title")
    parser.add_argument(
        "--no-write", action="store_true",
        help="dry run — report PDF URL but do not save or modify README",
    )
    parser.add_argument(
        "--batch", metavar="FILE",
        help="process one DOI/title per line (# = comment)",
    )
    parser.add_argument(
        "--stdin", action="store_true",
        help="read BibTeX block from stdin; extract DOI",
    )
    args = parser.parse_args()

    if args.stdin:
        bibtex = sys.stdin.read()
        ok = process_one(None, no_write=args.no_write, stdin_bibtex=bibtex)
        sys.exit(0 if ok else 1)

    if args.batch:
        try:
            with open(args.batch, encoding="utf-8") as fh:
                entries = [
                    ln.strip() for ln in fh
                    if ln.strip() and not ln.strip().startswith("#")
                ]
        except FileNotFoundError:
            log(f"ERROR: batch file not found: {args.batch!r}")
            sys.exit(1)
        results = []
        for entry in entries:
            log(f"=== Batch: {entry!r} ===")
            ok = process_one(entry, no_write=args.no_write)
            results.append((entry, ok))
        n_ok = sum(1 for _, ok in results if ok)
        print(f"\nBatch summary: {n_ok}/{len(results)} acquired")
        for entry, ok in results:
            print(f"  {'✓' if ok else '✗'} {entry}")
        sys.exit(0 if n_ok == len(results) else 1)

    if not args.input:
        parser.print_help()
        sys.exit(1)

    ok = process_one(args.input, no_write=args.no_write)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
