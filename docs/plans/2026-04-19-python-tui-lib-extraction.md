# Plan: extract reusable TUI code into `python-tui-lib`

**Date:** 2026-04-19
**Status:** Awaiting approval

## Context

`parking-space/scripts/ui/` and `scripts/tui/` contain a real TUI framework
— markdown viewer (~5.4K LOC), widgets, overlays, LLM picker, threading +
image cache, a Lisp-like automation DSL, playable games — that's outgrown
one-repo use. WorldFoundry's `scripts/git-branch-browser.py` wants to embed
the markdown viewer for a `?` help page; other standalone tools already want
the LLM picker. Rather than `sys.path`-hacking across sibling repos, promote
the shared code to its own repo so every consumer pulls from one source of
truth.

Exploration (single Explore agent, 2026-04-19) confirmed: **no circular
imports**, **no dependencies on parking-space-external code**, and the
reusable slice is ~32K LOC out of ~78K total. The domain-specific half
(31 AWS/occupancy/revenue dashboards + their fetchers) stays in
parking-space.

## Decisions (confirmed with user)

- **Repo name:** `python-tui-lib` at `/home/will/python-tui-lib`
- **Python package name:** `tuilib` (import root). `from tuilib.ui.doc_viewer.renderer import DocViewer`
- **Scope:** wholesale move of `scripts/ui/` (incl. `doc_viewer/` and `llm_picker/`) + `scripts/tui/widgets/` + framework pieces of `scripts/tui/` (layout, timing, recorder, generic cache + taskfile worker pool) + scripting DSL + games.
- **Packaging:** git submodule — no `pip install` step; consumers vendor via `git submodule add`.
- **Doc-viewer slicing, parameterization of parkingspace-specific strings, AWS-fetcher extraction — all deferred** (noted in follow-ups).
- **Interpretation of "easy/guaranteed to work right now":** move files verbatim, including the `parkingspace-tui` cache path strings + SSM prefix + User-Agent etc. baked into `ui/config.py` and `ui/llm_picker/client.py`. They're ugly but harmless — no consumer breaks. Cleanup is a follow-up task.

## Layout of the new repo

```
python-tui-lib/                           # git repo
  README.md
  pyproject.toml                          # metadata only (no install step needed)
  .gitignore
  tuilib/                                 # Python package (import root)
    __init__.py
    ui/                                   # ← scripts/ui/ (verbatim)
      __init__.py
      theme.py    text.py    config.py   config.yaml
      box.py      scrollbar.py            help_overlay.py
      ansi_art.py input_editor.py         image_cache.py
      doc_viewer/                         # 11 files, ~5.4K LOC — MOVE WHOLESALE
      llm_picker/                         # 4 files, ~650 LOC — MOVE WHOLESALE
    widgets/                              # ← scripts/tui/widgets/ (verbatim)
      __init__.py
      ansi.py chat_overlay.py content_drawer.py expandable.py
      flash.py flow.py meter.py palette.py sparkline.py
      status.py table.py tab_panel.py treemap.py
    framework/                            # new subpackage; framework bits of scripts/tui/
      __init__.py
      layout.py                           # ← scripts/tui/layout.py
      timing_fps.py                       # ← scripts/tui/timing_fps.py
      recorder.py                         # ← scripts/tui/recorder.py
      cache.py                            # ← scripts/tui/data/cache.py   (generic DataCache)
      taskfile.py                         # ← scripts/tui/data/taskfile.py (generic TaskRunnerPool)
    panes/                                # generic panes (new subpackage)
      __init__.py
      base.py                             # ← scripts/tui/panes/base.py
      flat_list_pane.py                   # ← scripts/tui/panes/flat_list_pane.py
      document.py                         # ← scripts/tui/panes/document.py (wraps DocViewer)
      todo.py                             # ← scripts/tui/panes/todo.py (extends DocumentPane)
      output.py                           # ← scripts/tui/panes/output.py (generic subprocess output)
      runbook.py                          # ← scripts/tui/panes/runbook.py (needs state-dir parameterization)
      runbook_parser.py                   # ← scripts/tui/data/runbook_parser.py (pure stdlib parser)
    scripting/                            # ← scripts/tui/scripting/ (verbatim, ~3.5K LOC)
    games/                                # ← scripts/tui/games/ (verbatim, ~1K LOC + assets/)
    assets/                               # ← scripts/tui/assets/ (Dragon's Lair ANSI art)
  tests/                                  # ← scripts/tui/tests/ (the subset that tests moved code)
```

## What moves, what stays

**Moves to tuilib** (agent-confirmed reusable, ~34.2K LOC):

- All of `scripts/ui/` — 11,689 LOC, 25 files
- All of `scripts/tui/widgets/` — ~1200 LOC, 12 files
- `scripts/tui/{layout,timing_fps,recorder}.py` — ~1450 LOC
- `scripts/tui/data/{cache,taskfile}.py` — ~370 LOC (generic)
- `scripts/tui/data/runbook_parser.py` — 235 LOC (sibling parser for `runbook.py`, pure stdlib)
- `scripts/tui/scripting/` — ~3500 LOC (automation DSL, self-contained)
- `scripts/tui/games/` — ~1000 LOC (only depend on widgets + theme)
- `scripts/tui/assets/` — Dragon's Lair ANSI art (referenced by games)
- `scripts/tui/panes/{base,flat_list_pane,document,todo,output,runbook}.py` — ~1745 LOC
- Test subset from `scripts/tui/tests/` that covers moved modules

**Parking-space is not touched by this plan.** Its tree stays unchanged; `scripts/ui/` and `scripts/tui/` keep their current files. `tuilib` will contain an independent copy of the reusable subset; WorldFoundry consumes the copy. Migrating parking-space to also consume `tuilib` (and deleting the originals) is a separate plan — see "Follow-on plan: parking-space migration" below.

**Excluded from tuilib** (domain-coupled, stays only in parking-space):

- `scripts/tui/app.py` (1200 LOC) — wired to ~25 domain panes
- `scripts/tui/__main__.py` — parking-space-specific log path
- `scripts/tui/panes/` — the domain-coupled subset (see pane inventory below for per-file classification)
- `scripts/tui/data/` — `fetcher.py`, `aws.py`, `health.py`, `project.py`, `pagerduty.py`, `vm.py`, `dep_*`, `log_query.py` (CloudWatch-specific, 1363 LOC), `llm_billing.py`, `script_runs.py`, `alarm.py` — all AWS/domain-coupled
- `scripts/chat/`, `scripts/view/` — standalone parking-space tools; not copied

### Pane inventory (36 files, ~30K LOC)

Column "Scope" — **tuilib** (copied to tuilib by this plan), **excluded** (not copied; only lives in parking-space), **later** (queued for a future tuilib plan, not this one).

| #  | File | LOC | Scope | Notes |
|----|------|-----|-------|-------|
| 1  | `__init__.py` | 1 | tuilib | empty |
| 2  | `base.py` | 134 | tuilib | `BasePane` abstract class — framework, move with panes |
| 3  | `_parse_prices.py` | 156 | excluded | helper for `region_pricing.py` |
| 4  | `flat_list_pane.py` | 97 | tuilib | reusable list-pane base |
| 5  | `document.py` | 117 | **tuilib** | ★ wraps `DocViewer` for embedding — this is exactly the pattern branch-browser wants |
| 6  | `todo.py` | 460 | **tuilib** | ★ extends `DocumentPane`; path already parameterized (`file_path` ctor arg) — consumer passes `project.root/TODO.md` |
| 7  | `tui_about.py` | 632 | excluded | hardcodes parking-space branding + URL + depends on `data/llm_billing.py`; extraction needs a data-driven content config. Stays for now |
| 8  | `output.py` | 98 | **tuilib** | ★ fully generic subprocess output viewer; only imports base + theme + widgets/ansi + scrollbar |
| 9  | `runbook.py` | 839 | **tuilib** | ★ runbook path already parameterized via `project.root`; **state-dir hardcode `'parkingspace'` at line 28 needs a ctor arg**; pulls in `data/runbook_parser.py` (235 LOC, pure stdlib) which also moves |
| 10 | `sparkline_dashboard.py` | 678 | excluded | tech demo only — never extracted |
| 11 | `logs.py` | 2818 | later | ★ TUI log tailer + search + LLM summarization; genuinely reusable but CloudWatch-coupled via `data/log_query.py` — extraction needs an abstract log-source interface. Deferred #7 |
| 12 | `audit.py` | 338 | excluded | audit log |
| 13 | `bg_deploy.py` | 573 | excluded | blue/green deploy state |
| 14 | `capacity_planner.py` | 2253 | excluded | capacity planning |
| 15 | `certs.py` | 517 | excluded | TLS certs |
| 16 | `costs.py` | 499 | excluded | AWS cost breakdown |
| 17 | `database.py` | 666 | excluded | RDS/DB state |
| 18 | `dep_versions.py` | 606 | excluded | dependency versions |
| 19 | `geo_map.py` | 293 | excluded | geographic map |
| 20 | `health.py` | 211 | excluded | endpoint health |
| 21 | `heatmap.py` | 257 | excluded | activity heatmap |
| 22 | `incidents.py` | 634 | excluded | PagerDuty incidents |
| 23 | `instances.py` | 861 | excluded | EC2 instances |
| 24 | `network.py` | 3928 | excluded | VPC / networking (largest file) |
| 25 | `pipeline.py` | 440 | excluded | deploy pipeline |
| 26 | `region_check.py` | 2059 | excluded | region enablement |
| 27 | `region_pricing.py` | 1340 | excluded | cross-region pricing |
| 28 | `regions.py` | 257 | excluded | region list |
| 29 | `resources.py` | 1910 | excluded | AWS resource catalog |
| 30 | `revenue.py` | 440 | excluded | revenue dashboard |
| 31 | `scheduled_tasks.py` | 662 | excluded | cron / scheduled tasks |
| 32 | `sessions.py` | 580 | excluded | active user sessions |
| 33 | `tasks.py` | 359 | excluded | go-task targets |
| 34 | `tf_locks.py` | 339 | excluded | Terraform state locks |
| 35 | `traffic.py` | 419 | excluded | request traffic |
| 36 | `versions.py` | 3261 | excluded | app versions |

**Moving to tuilib (in addition to earlier `scripts/ui/` + widgets + framework):**
- `panes/{base,flat_list_pane,document,todo,output,runbook}.py` → `tuilib/panes/` (new subpackage, ~1745 LOC)
- `data/runbook_parser.py` → `tuilib/panes/runbook_parser.py` (co-located with `runbook.py`, 235 LOC)
- **In-pass fix:** `runbook.py` line 28 `'parkingspace'` hardcoded state-dir → ctor arg `state_dir` (default `~/.cache/tuilib/runbook-state.json`, consumer overrides)

## Follow-on plans (committed, separate docs)

### Plan 2 — parking-space migration to tuilib

Rewrites parking-space to consume tuilib and deletes its in-tree copies. Written as `/home/will/parking-space/plans/2026-04-19-migrate-to-tuilib.md` (already committed). Summary:

1. `git submodule add <url> vendor/python-tui-lib` in parking-space.
2. Sys-path bootstrap in `scripts/tui/__main__.py`, `scripts/chat/__main__.py`, `scripts/view/__main__.py`.
3. Mechanical import rewrite across ~40 files: `scripts.ui.` → `tuilib.ui.`, `scripts.tui.widgets.` → `tuilib.widgets.`, `scripts.tui.layout` → `tuilib.framework.layout`, `scripts.tui.timing_fps` → `tuilib.framework.timing_fps`, `scripts.tui.recorder` → `tuilib.framework.recorder`, `scripts.tui.data.cache` → `tuilib.framework.cache`, `scripts.tui.data.taskfile` → `tuilib.framework.taskfile`, `scripts.tui.scripting.` → `tuilib.scripting.`, `scripts.tui.games.` → `tuilib.games.`, `scripts.tui.panes.{base,flat_list_pane,document,todo,output,runbook}` → `tuilib.panes.X`.
4. Delete the now-redundant files from parking-space.
5. Smoke test `python -m scripts.tui` and the full baseline tape.

Until plan 2 runs, parking-space and tuilib hold duplicate copies of the reusable subset. Bug fixes during that window have to land in both — noted as a risk, mitigated by keeping the window short.

### Plan 3 — extract `panes/logs.py` with abstract log-source interface

Not yet written. Moves the 2818-LOC log-tailer + LLM-summarization pane into `tuilib/panes/logs.py`, behind a pluggable log-source abstraction:
- Define `LogSource` protocol (query + tail + paginate methods).
- Leave CloudWatch-specific `data/log_query.py` in parking-space as the concrete impl.
- Parking-space's `app.py` instantiates `LogPane(source=CloudWatchLogSource(...))`.
- Other consumers plug in journald, k8s pods, raw files, etc.

Separated from this plan because the abstraction is design work, not a mechanical move — it warrants its own scoped plan. Committed follow-on, not a "maybe".

### Plan 4 — extract generic worker-pool from `scripts/tui/data/fetcher.py`

Not yet written. Carves a lean `tuilib.framework.worker_pool` out of the 800-LOC `DataFetcher`:
- Keep: `ThreadPoolExecutor`, scheduling (`_maybe_fetch` interval rotation), `DataCache` integration, `tick()` entry point.
- Leave behind in parking-space: the 60+ AWS-specific fetch jobs (aws/health/pagerduty/vm/dep_versions/…).
- Parking-space refactors `DataFetcher` to subclass or compose the generic worker-pool and register its own jobs.
- Other consumers get a generic "schedule recurring background work on a thread pool" primitive.

Separated from this plan because, like plan 3, this is design work (what's the public API? how do consumers register jobs? one lock or per-job?), not a mechanical move. Committed follow-on.

## Hardcoded-path parameterization (in-scope, Phase B)

Every reference to `parkingspace` / `parking-space-tui` / `parkingspace-tui` gets replaced with a runtime-derived value from `tuilib.APP_NAME`. Consumers set `APP_NAME` before importing anything heavy; sensible default is `'tuilib'`.

### The `tuilib.APP_NAME` symbol

```python
# tuilib/__init__.py
import os
APP_NAME = os.environ.get('TUILIB_APP_NAME', 'tuilib')
```

Consumers override one of two ways:
- **Env var:** `TUILIB_APP_NAME=branch-browser python3 git-branch-browser.py`
- **Python:** `import tuilib; tuilib.APP_NAME = 'branch-browser'` **before** any other tuilib import

### Specific sites to rewrite

| File | Before | After |
|---|---|---|
| `tuilib/ui/config.py:317` | `SSM_KEY_PREFIX = '/parkingspace/tui/'` | `SSM_KEY_PREFIX = f'/{tuilib.APP_NAME}/tui/'` |
| `tuilib/ui/llm_picker/client.py` (config dir) | `~/.config/parking-space-tui/` | `~/.config/{tuilib.APP_NAME}/` |
| `tuilib/ui/llm_picker/client.py` (User-Agent) | `parking-space-tui/...` | `{tuilib.APP_NAME}/...` |
| `tuilib/ui/llm_picker/client.py` (SSM prefix) | `/parkingspace/tui/` | `/{tuilib.APP_NAME}/tui/` |
| `tuilib/ui/text.py` (ctypes width cache) | `~/.cache/parkingspace-tui/` | `~/.cache/{tuilib.APP_NAME}/` |
| `tuilib/ui/image_cache.py` | `~/.cache/parkingspace-tui/images/` | `~/.cache/{tuilib.APP_NAME}/images/` |
| `tuilib/ui/doc_viewer/mermaid_cache.py` | `~/.cache/parkingspace-tui/mermaid/` | `~/.cache/{tuilib.APP_NAME}/mermaid/` |
| `tuilib/ui/doc_viewer/full_text_search.py` | vault-size heuristic tagged `parkingspace` | neutral / keyed off `{tuilib.APP_NAME}` |

### Plan-2 implication (state continuity for parking-space)

When plan 2 rewires parking-space to tuilib, its entry points (`scripts/tui/__main__.py`, `scripts/chat/__main__.py`, `scripts/view/__main__.py`) will set `tuilib.APP_NAME = 'parkingspace'` (or `'parking-space-tui'` — whichever matches the original cache-dir name) **before importing anything**, so existing caches, configs, and SSM paths resolve to exactly the same locations they used before. Plan 2 already mentions "preserve on-disk state locations" — this is the mechanism.

### Read-only lookup helpers (not hardcoded)

Introduce one utility in `tuilib/ui/config.py` that every path-using module calls, rather than re-deriving:

```python
def app_cache_dir(*parts):
    return os.path.join(os.path.expanduser(f'~/.cache/{tuilib.APP_NAME}'), *parts)

def app_config_dir(*parts):
    return os.path.join(os.path.expanduser(f'~/.config/{tuilib.APP_NAME}'), *parts)

def app_ssm_prefix():
    return f'/{tuilib.APP_NAME}/tui/'
```

Each rewrite above points at one of these helpers. Keeps the "where do paths come from" contract in one file.

## Asset paths that break when files move

- `tuilib/games/dragons_lair.py` loads assets via `os.path.join(project.root, 'scripts', 'tui', 'assets', ...)` — needs rewrite to relative-to-`__file__` or `tuilib.games.assets`. **Address in Phase B.**
- `tuilib/ui/config.py` loads `config.yaml` via `os.path.join(os.path.dirname(__file__), 'config.yaml')` — **already file-relative**, no change needed.
- `scripts/tui/data/documents/notes.md` — **the file stays in parking-space** (parking-space-owned content, not a tuilib asset). `DocumentPane` itself moves to `tuilib/panes/document.py`; parking-space's `app.py` instantiates it with the path: `DocumentPane(file_path='scripts/tui/data/documents/notes.md')`. Same pattern TodoPane already uses — consumer supplies the content path.

## Third-party dependencies to declare

In `python-tui-lib/pyproject.toml` optional-deps or a lightweight `requirements.txt`:

- `pyyaml` — used by `ui/config.py` (caught gracefully on ImportError today)
- `matplotlib`, `squarify` — used by `widgets/treemap.py`
- `pytest` — for the test subset

System binaries referenced via subprocess (document, don't hard-require):
- `chafa` (image rendering in `ui/image_cache.py`)
- `mmdc` / mermaid-cli (in `doc_viewer/mermaid_cache.py`)
- `git`, `rg` (ripgrep) — for `doc_viewer/git_history.py` and `full_text_search.py`

## Phases

### Phase A — stand up the new repo
1. `git init /home/will/python-tui-lib`
2. Minimal `pyproject.toml` (name=python-tui-lib, description, py ver), `README.md` explaining layout + consumption via submodule, `.gitignore`.
3. Copy files per the layout table above. **Imports inside the copied files stay as `from scripts.ui...` for this phase** — no rewrites yet.
4. Commit: "initial import from parking-space@<sha>".

### Phase B — rewrite imports within tuilib
1. Single-pass rewrite across all tuilib files: `scripts.ui.` → `tuilib.ui.`, `scripts.tui.widgets.` → `tuilib.widgets.`, `scripts.tui.layout` → `tuilib.framework.layout`, `scripts.tui.timing_fps` → `tuilib.framework.timing_fps`, `scripts.tui.recorder` → `tuilib.framework.recorder`, `scripts.tui.data.cache` → `tuilib.framework.cache`, `scripts.tui.data.taskfile` → `tuilib.framework.taskfile`, `scripts.tui.scripting.` → `tuilib.scripting.`, `scripts.tui.games.` → `tuilib.games.`.
2. Rewrite `games/dragons_lair.py` asset path to `__file__`-relative.
3. Smoke-verify: `PYTHONPATH=/home/will/python-tui-lib python3 -c "import tuilib; import tuilib.ui.doc_viewer.renderer; import tuilib.widgets.table; import tuilib.framework.layout"` — no ImportError.
4. Commit: "rewrite imports to tuilib.* package root".

### Phase C — WorldFoundry consumer
1. `git submodule add <url> vendor/python-tui-lib` in WorldFoundry.
2. In `scripts/git-branch-browser.py`:
   - Prepend `vendor/python-tui-lib/` to `sys.path` at startup.
   - Import `from tuilib.ui.doc_viewer.renderer import DocViewer` (or `help_overlay` fallback if the full viewer proves heavy).
3. Write `scripts/git-branch-browser.help.md` — user's guide covering: what the chain is, keybindings, diff modes, compare workflow.
4. Embed the markdown via `importlib.resources` or read-at-startup from the script's directory.
5. Add `?` key handler: open DocViewer overlay over the current screen; `?`/`Esc`/`q` close.
6. Smoke-test: `task git` boots, chain renders, `?` opens help, scrolling works, Esc closes, Ctrl+C still exits cleanly.
7. Commit in WorldFoundry: "add tuilib submodule + embedded markdown help (`?`)".

### Phase D — wf-status + plan-doc sync
Update WorldFoundry's `wf-status.md` row + this plan's `**Status:**` line to reflect the landed state. Per the sync rule, both move together.

## Critical files

**New (in python-tui-lib):**
- `/home/will/python-tui-lib/` — entire repo tree per layout above

**Modified (WorldFoundry):**
- `scripts/git-branch-browser.py` — `?` key, `sys.path` bootstrap, `DocViewer` import
- New: `scripts/git-branch-browser.help.md`
- Add `.gitmodules` entry for `vendor/python-tui-lib`
- Update: `docs/plans/2026-04-16-git-branch-browser.md` (`**Status:**` line), `wf-status.md` (Summary rolling entry + Complete row), `docs/plans/2026-04-19-python-tui-lib-extraction.md` (this plan's `**Status:**` line)

**NOT modified by this plan:** parking-space. Kept completely intact. See follow-on migration plan.

## Reused existing code (do NOT rewrite)

- `tuilib/ui/doc_viewer/renderer.py:DocViewer` — the full markdown renderer. Branch-browser will call `DocViewer().load_text(md_string, title='Help')` + `.draw(stdscr, ...)` + `.handle_key(ch)`.
- `tuilib/ui/help_overlay.py:draw_help_overlay` — fallback/alternative if DocViewer proves too heavy for a one-page help.

## Safety rails

Since this plan does **not** modify parking-space, the risk surface is small: we're creating a new repo, populating it from file copies, and wiring one new consumer (WorldFoundry). Still worth the following:

1. **`cp`, not `git mv`, when populating tuilib.** Parking-space isn't touched at all; tuilib gets independent copies. (When the follow-on migration plan runs, it will delete from parking-space then — `git mv` is for that plan, not this one.)
2. **Import-surface linter after Phase B.** `PYTHONPATH=~/python-tui-lib python3 -c "<import every module>"` loop — catches any `scripts.X` leftover from the mechanical rewrite. A tiny `tests/smoke_imports.py` under `python-tui-lib/tests/` codifies this.
3. **Phase boundary = clean commit.** Phase A commits verbatim copies; Phase B commits the import rewrite; each is reviewable in isolation.
4. **Ctor-signature back-compat for touched panes.** `RunbookPane(state_dir=...)` default preserves the parking-space path (`~/.cache/parkingspace/runbook-state.json`) so when the parking-space migration plan runs later, the `app.py` instantiation line works unchanged.
5. **Defer runtime verification to Phase C.** Phase A/B can't really be exercised end-to-end until a consumer exists. Phase C's smoke test (branch-browser `?` opens help) is the first real "does this work" signal.

**What would a breakage look like at each phase?**

| Phase | Typical breakage | Detection |
|---|---|---|
| A (copy files into tuilib) | (should be none — no consumers yet) | N/A |
| B (rewrite imports inside tuilib) | Circular import, wrong path, missed `scripts.X` | `python3 -c "import tuilib.ui.doc_viewer.renderer"` fails; smoke-imports test catches it |
| C (WorldFoundry consumer) | DocViewer import pulls in a module that needs env/state parking-space supplies (e.g. libsixel, chafa, an LLM credential dir) | `task git` + `?` key raises at import time or first draw |

## Verification

1. **Structural** — `PYTHONPATH=~/python-tui-lib python3 -c "from tuilib.ui.doc_viewer.renderer import DocViewer; from tuilib.widgets.table import *; from tuilib.framework.layout import Layout; from tuilib.panes.runbook import RunbookPane"` succeeds.
2. **Smoke-imports test** — `pytest python-tui-lib/tests/smoke_imports.py` imports every module in tuilib without error.
3. **Moved test subset** — `pytest python-tui-lib/tests/` passes (the tests that were copied over from `scripts/tui/tests/`).
4. **WorldFoundry smoke** — `task git` lists branches, cursor/scroll/expand work, `?` opens help page rendered as markdown, headings / lists / code fences / inline formatting visible, scrolling via ↑↓/PgUp/PgDn, Esc/`?`/`q` close the overlay. Ctrl+C exits cleanly.
5. **Parking-space not broken** — `git status` in parking-space shows no changes; `python -m scripts.tui` runs identically to before (no code touched, no behavior change).

## Deferred follow-ups (noted, genuinely "maybe someday")

Committed follow-on plans are listed above. These are actual "maybe" ideas:

1. **Slice `md_viewer` from `doc_viewer/renderer.py`** — minimal markdown pager (~900 LOC) dropping vault/mermaid/HAR/CSV/FTS/images/wiki. Swap WorldFoundry's branch-browser to it once stable. Maybe; the full renderer works fine for now.
2. **Installable packaging** — revisit `pip install -e .` vs submodule once there are ≥3 consumers.
3. **Move `scripts/view/` and `scripts/chat/` into `tuilib/tools/`** — ship them as bundled example CLIs.
4. **Third-party install bootstrap** — document optional deps (`chafa`, `mmdc`, `rg`) and how consumers declare them.
5. **`tui_about.py` extraction** — once the branding/URL/billing-provider is data-driven, move it to `tuilib/panes/`.
