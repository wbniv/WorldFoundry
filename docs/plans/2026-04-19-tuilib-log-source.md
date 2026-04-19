# Plan 3: extract `panes/logs.py` behind abstract `LogSource`

**Date:** 2026-04-19
**Status:** Draft — waiting on prerequisite plan
**Prerequisite:** Plan 1 (`2026-04-19-python-tui-lib-extraction.md`) must land first — this plan touches tuilib and assumes its structure exists.

## Context

`scripts/tui/panes/logs.py` (2818 LOC) is the largest generic pane in parking-space: a TUI log tailer with search, filtering, and LLM summarization. But it's hard-coupled to CloudWatch via `scripts/tui/data/log_query.py` (1363 LOC of Insights-query functions). That coupling makes it unreusable for any consumer whose logs aren't in CloudWatch — journald, k8s pods, raw files, git log tailing, systemd journals on servers, etc.

This plan separates the pane from the query backend via an abstract `LogSource` protocol so the pane can live in tuilib and work against any log stream a consumer plugs in.

**Not in this plan:**
- Parking-space's own `logs.py` / `log_query.py` are not touched. Plan 2 writes a `CloudWatchLogSource` adapter and rewires parking-space after plans 1+3 have landed.

## Scope

### What moves to tuilib

- **New:** `tuilib/panes/log_source.py` (~80 LOC) — `LogSource` protocol, `LogEvent` dataclass, a minimal `StubLogSource` for tests.
- **New:** `tuilib/panes/logs.py` (~2818 LOC, ported from parking-space's `scripts/tui/panes/logs.py`) — ctor takes a `LogSource` instance; every direct `data.log_query.X` call is routed through `self._source`.

### What stays untouched

- `parking-space/scripts/tui/panes/logs.py` — original unchanged. Parking-space keeps using it until plan 2 migrates.
- `parking-space/scripts/tui/data/log_query.py` — CloudWatch-specific queries stay put. Plan 2 wraps them in a `CloudWatchLogSource` adapter.

### The `LogSource` protocol (proposed)

```python
# tuilib/panes/log_source.py
from dataclasses import dataclass, field
from typing import Protocol, Iterable, Iterator, runtime_checkable

@dataclass
class LogEvent:
    timestamp: float       # Unix seconds (float for sub-second precision)
    message: str           # the raw log line
    source: str = ''       # log group / stream / file / service name
    level: str = ''        # 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' — optional, '' if unknown
    fields: dict = field(default_factory=dict)  # arbitrary extra fields

@runtime_checkable
class LogSource(Protocol):
    def query(self, expr: str, window_s: int = 3600, limit: int = 1000) -> Iterable[LogEvent]:
        """Run a query against the source; return matching events newest-first."""

    def tail(self, expr: str) -> Iterator[LogEvent]:
        """Stream events as they arrive; yields LogEvents until the iterator is closed."""

    def groups(self) -> list[str]:
        """List available log groups / streams / files / sources."""

    def fields(self) -> list[str]:
        """List fields the consumer can filter/query on for this source."""
```

The `expr` parameter is an opaque string — each concrete source interprets it in its own query language (CloudWatch Insights, journald filter spec, ripgrep regex, etc.). The pane renders the expr as-is in the UI and hands it back verbatim.

### `StubLogSource` for tests

```python
# tuilib/panes/log_source.py (same file)
class StubLogSource:
    """Fixed-list LogSource for unit tests and doc examples."""
    def __init__(self, events: list[LogEvent]):
        self._events = events
    def query(self, expr, window_s=3600, limit=1000):
        return [e for e in self._events if expr in e.message][:limit]
    def tail(self, expr):
        return iter([])  # tests control timing explicitly
    def groups(self): return ['stub']
    def fields(self): return ['timestamp', 'message', 'source', 'level']
```

## Phases

### Phase 1 — define the protocol + dataclass
1. Write `tuilib/panes/log_source.py` with the `LogSource` protocol, `LogEvent` dataclass, `StubLogSource` helper.
2. Export from `tuilib/panes/__init__.py`.
3. Smoke-import: `python3 -c "from tuilib.panes.log_source import LogSource, LogEvent, StubLogSource"` — no error.
4. Commit: "feat(panes): LogSource protocol + LogEvent dataclass + StubLogSource".

### Phase 2 — port `logs.py` to tuilib
1. `cp parking-space/scripts/tui/panes/logs.py tuilib/panes/logs.py`
2. Rewrite imports: the existing `from ..data.log_query import ...` becomes a ctor arg. Remove the hard import entirely.
3. Ctor signature change: `LogPane.__init__(self, source: LogSource, *, index=18, title='Logs', ...)` — `source` is the first required positional arg. All other args keep their current defaults/behavior.
4. Every `log_query.X(...)` call in the body gets rewritten to `self._source.X(...)` (where X is `query`, `tail`, `groups`, `fields`, or a rename if the source API diverges).
5. LLM summarization code is untouched — it already operates on lists of event-like dicts; pass it `LogEvent`-derived dicts (`asdict(event)` or a to-dict helper).
6. Smoke-import: `python3 -c "from tuilib.panes.logs import LogPane"` — no error.
7. Commit: "feat(panes): port LogPane into tuilib with LogSource injection".

### Phase 3 — unit tests with StubLogSource
1. `tuilib/tests/test_log_pane.py`:
   - Constructs `LogPane(source=StubLogSource([LogEvent(...)]*3))`.
   - Uses a headless curses `newpad`, calls `pane.on_draw()`, asserts the three messages appear in the rendered grid.
   - Tests `query` path with a filter expr.
   - Tests `groups()` dropdown population.
2. Run `pytest tuilib/tests/test_log_pane.py` — green.
3. Commit: "test(panes): unit tests for LogPane against StubLogSource".

### Phase 4 — documentation
1. Module docstring at the top of `tuilib/panes/log_source.py` explaining: what a LogSource is, how to implement one, minimal example (10 lines) wrapping a generator.
2. Module docstring at the top of `tuilib/panes/logs.py`: usage snippet — `LogPane(source=MyLogSource(...))`, key bindings, LLM summarization opt-in.
3. Commit: "docs(panes): LogSource + LogPane usage examples".

### Phase 5 — closure
1. Update tuilib's README (if it exists) to mention `LogPane` as an available pane.
2. Update plan 1's pane inventory table: flip row 11 (`logs.py`) from `later` to `tuilib`.
3. Update plan 2's "Files to delete from parking-space" list to include `scripts/tui/panes/logs.py` + add a Phase-3.5-equivalent section documenting the `CloudWatchLogSource` adapter parking-space must write.
4. Mark this plan Done.

## Safety rails

1. **Parking-space's `logs.py` is not touched.** The original keeps working unchanged; duplication during the window between this plan and plan 2 is the only cost.
2. **Smoke-import gate before unit tests.** If `from tuilib.panes.logs import LogPane` raises at Phase 2, the port is incomplete — don't proceed to tests.
3. **No LLM dependencies in the happy path.** `LogPane` renders fine without any LLM configured; summarization is opt-in. A smoke test verifies this.
4. **Stub source ships with the protocol.** Consumers can wire up `LogPane(source=StubLogSource([]))` as a first step without writing a real source — confirms the pane loads correctly in their env before they tackle their own backend.
5. **No breaking changes to LogEvent.** `LogEvent` is a plain dataclass; `fields: dict` absorbs any extra data a source wants to carry. Additions go on the dict, not as new required dataclass fields.

## Verification

1. **Protocol import** — `python3 -c "from tuilib.panes.log_source import LogSource, LogEvent, StubLogSource"` succeeds.
2. **Pane import** — `python3 -c "from tuilib.panes.logs import LogPane"` succeeds with no CloudWatch / boto3 / parking-space dependencies resolved (log_source + logs.py are the only tuilib modules needed).
3. **Stub-source render** — unit test renders three events without error.
4. **No runtime regression in parking-space** — `git status` in parking-space is clean; `python -m scripts.tui` still uses its existing `panes/logs.py` unchanged.
5. **Pane count in parking-space is unchanged** — 32 panes before and after.

## Rollback

This plan only adds files inside the `python-tui-lib` repo. If something goes wrong:

```
cd ~/python-tui-lib
git reset --hard <plan-1-final-sha>
```

Parking-space and WorldFoundry are unaffected; tuilib rolls back to its post-plan-1 state.

## Follow-on work (out of scope here)

- **`CloudWatchLogSource`** — a concrete adapter wrapping `parking-space/scripts/tui/data/log_query.py` functions; written during plan 2.
- **`JournaldLogSource`** — reads `systemd-journald` via `journalctl` subprocess or the `systemd.journal` Python bindings. Reusable on Linux servers.
- **`FileLogSource`** — tails one or more plain-text log files with optional regex filtering. Reusable for any daemon that writes to disk.
- **`GitLogSource`** — wraps `git log` output; LogEvent.timestamp = commit time, LogEvent.message = subject, LogEvent.fields = author/sha/diffstat. Would make `git-branch-browser.py`'s commit-log tail a natural consumer of LogPane.

## Critical files

- **New:** `tuilib/panes/log_source.py` — protocol + dataclass + stub (~80 LOC)
- **New:** `tuilib/panes/logs.py` — ported pane (~2818 LOC)
- **New:** `tuilib/tests/test_log_pane.py` — stub-based unit tests (~100 LOC)
- **Updated:** `tuilib/panes/__init__.py` — export `LogPane`, `LogSource`, `LogEvent`, `StubLogSource`
- **Updated:** `WorldFoundry/docs/plans/2026-04-19-python-tui-lib-extraction.md` — plan 1's pane inventory row 11 flipped to `tuilib`
- **Updated:** `parking-space/plans/2026-04-19-migrate-to-tuilib.md` — plan 2 gains a `CloudWatchLogSource` adapter step
