# Plan 4: extract generic `WorkerPool` from `data/fetcher.py`

**Date:** 2026-04-19
**Status:** Done — 2026-04-19. Landed in tuilib commit `d071e1f`: 174-LOC `WorkerPool` in `tuilib/framework/worker_pool.py` + 7 unit tests (all pass). Contract is return-value-only (per survey of 50 DataFetcher call-sites; opt-out deferred until needed). Parking-space untouched — plan 2 writes the adapter.
**Prerequisite:** Plan 1 landed same day.

## Context

`scripts/tui/data/fetcher.py` (800 LOC) is two things mashed together:

1. A **generic scheduling primitive** — `ThreadPoolExecutor(max_workers=64)` + per-key intervals + tick-driven job dispatch + cache writes + explicit lock for schedule-dict access. ~200 LOC of real mechanism.
2. **60+ AWS-specific fetch-job registrations** — `_maybe_fetch('instances:us-west-2', 30, fetch_instances, ...)`, `_maybe_fetch('alarms', 60, fetch_cloudwatch_alarms)`, etc. ~600 LOC of parking-space-specific glue.

Consumers beyond parking-space want #1 without #2: a "schedule these recurring background jobs on a thread pool, write results to a shared cache, I'll call `tick()` from my event loop" primitive. This plan carves that out.

**Not in this plan:**
- Parking-space's `DataFetcher` is not touched. Plan 2 later rewrites it to compose `WorkerPool` + register the AWS jobs against it.

## Scope

### What moves to tuilib

- **New:** `tuilib/framework/worker_pool.py` (~200 LOC) — `WorkerPool` class + a short ADR-style header describing the public API.

### What stays untouched

- `parking-space/scripts/tui/data/fetcher.py` — original `DataFetcher` unchanged. Parking-space keeps using it until plan 2 migrates.
- `parking-space/scripts/tui/data/aws.py`, `health.py`, `pagerduty.py`, etc. — all 60+ concrete fetchers stay where they are.

### The `WorkerPool` API (proposed)

```python
# tuilib/framework/worker_pool.py
from concurrent.futures import ThreadPoolExecutor
from tuilib.framework.cache import DataCache

class WorkerPool:
    """Scheduled background-job primitive.

    Consumers register recurring jobs with `schedule()` and call `tick()`
    from their event loop each frame. Jobs whose interval has elapsed
    are submitted to a shared ThreadPoolExecutor; results land in the
    DataCache keyed by the job's registered key.
    """

    def __init__(self, max_workers: int = 64, cache: DataCache | None = None):
        ...

    def schedule(self, key: str, interval_s: float, fn, *args, **kwargs) -> None:
        """Register a recurring job. `fn(*args, **kwargs)` runs every `interval_s`
        and its return value is stored in `cache[key]`. Re-registering a key
        replaces the existing schedule."""

    def force_refresh(self, stagger_s: float = 0.0) -> None:
        """Schedule every registered job to run at (now + jitter * stagger_s)."""

    def invalidate(self, key: str) -> None:
        """Remove a key's schedule and cache entry."""

    def tick(self) -> None:
        """Must be called from the host event loop. Submits any job whose
        next_fetch_time has elapsed."""

    def stop(self) -> None:
        """Shut down the executor; blocks until in-flight jobs complete."""

    @property
    def cache(self) -> DataCache:
        """Shared cache (either the one passed to __init__ or a default)."""
```

### Threading model (preserved from DataFetcher)

- One `ThreadPoolExecutor` instance owned by the WorkerPool.
- Schedule dict guarded by an explicit `threading.Lock`.
- Futures are not awaited; results land in the cache directly from the job function (which calls `cache.set(key, value)` via a closure the pool passes in, or by return-value convention — **see open question below**).
- `tick()` is lock-only; job submission is non-blocking (the lock is held only for the dict read/update, not the executor submit).

### Open question — return-value vs explicit-cache

Two contracts possible:
- **(a)** Job functions take `(cache, *args)` and write to the cache themselves: `fetch_instances(cache, region)` does `cache.set(f'instances:{region}', result)`. More flexible (a job can write multiple keys); matches the current DataFetcher pattern.
- **(b)** Job functions take `(*args)` and return a value; `WorkerPool` writes the return value to `cache[key]` for them. Simpler API; less flexible.

**Recommendation:** default to (b) for simplicity; support (a) via a `WorkerPool(cache_write='caller')` ctor flag for the minority of jobs that need to write multiple keys. Parking-space's fetchers are mostly (b)-shaped, so the default matches.

Decide at Phase 1; document in the module docstring.

## Phases

### Phase 1 — design decision + module header
1. Read all 60+ `_maybe_fetch(...)` calls in parking-space's `fetcher.py` and tally which shape they need: (b) "return a value the pool writes" vs (a) "write the cache explicitly" vs mixed.
2. Record the chosen default and the opt-out mechanism in a module-top comment block in `tuilib/framework/worker_pool.py`.
3. Commit: "design: WorkerPool contract (see module header)".

### Phase 2 — implement `WorkerPool`
1. Lift the relevant code out of `DataFetcher` into a new `WorkerPool` class in `tuilib/framework/worker_pool.py`.
2. Keep internal state minimal: `_schedule: dict[str, ScheduleEntry]`, `_cache: DataCache`, `_executor: ThreadPoolExecutor`, `_lock: threading.Lock`.
3. `schedule()`, `tick()`, `force_refresh()`, `invalidate()`, `stop()` all implemented.
4. `cache` property exposes the underlying DataCache (either passed-in or default).
5. Follow `nullptr`-comparison-style preferences — no `ptr != None`; use truthiness.
6. Commit: "feat(framework): WorkerPool — scheduling primitive".

### Phase 3 — unit tests
1. `tuilib/tests/test_worker_pool.py`:
   - **Basic schedule + tick:** register a job with interval=0.1s, tick repeatedly over 0.5s, assert job ran ≥3× and cache holds its return value.
   - **Force refresh:** register five jobs with stagger=0.2s, `force_refresh()`, tick across 2s, assert all five ran and their submission times are spread.
   - **Invalidate:** schedule, invalidate, tick; assert job doesn't run and cache entry is cleared.
   - **Concurrent schedule:** spawn 4 threads that each register 10 keys; assert no race, all 40 keys present.
   - **Stop:** schedule long-running jobs, call stop, assert all complete; subsequent ticks are no-ops.
2. Run `pytest tuilib/tests/test_worker_pool.py` — all green.
3. Commit: "test(framework): WorkerPool unit tests (schedule, tick, force_refresh, invalidate, stop)".

### Phase 4 — usage example + docs
1. Ten-line snippet in the `WorkerPool` class docstring showing register → tick loop → read cache.
2. Note in `tuilib/framework/__init__.py` exporting `WorkerPool`, `DataCache`, `TaskRunnerPool`.
3. README blurb (if there is a README) — "tuilib.framework: reusable scheduling + cache + task-runner pool".
4. Commit: "docs(framework): WorkerPool usage example + framework exports".

### Phase 5 — closure
1. Update plan 2's "Adapter classes parking-space must write" section to formally reference `tuilib.framework.worker_pool.WorkerPool` (by path + API, not by hope).
2. Note the default contract chosen (return-value vs. explicit-cache) so plan 2 knows which jobs need the opt-out flag.
3. Mark this plan Done.

## Safety rails

1. **Parking-space's `DataFetcher` is not touched.** The original class still runs the current TUI; duplication during the plan-2 gap is the only cost.
2. **Thread safety matches the original.** Lock scope + ThreadPoolExecutor semantics are preserved from `DataFetcher`; no novel concurrency patterns. If the original works, so should the extraction.
3. **No silent API changes.** The `WorkerPool` method set is a proper superset of `DataFetcher`'s public surface (schedule / force_refresh / invalidate / tick / stop). Plan 2's rewrite is a call-site substitution, not a semantic port.
4. **Return-value vs. explicit-cache decided upfront.** Phase 1 records the decision and opt-out mechanism in the module header; Phase 2 implements both paths. No ambiguity for plan 2's adapter work.
5. **Unit tests include the race path.** Phase 3 explicitly tests concurrent `schedule()` calls because the original lock protection was the subtlest part of `DataFetcher` to get right.

## Verification

1. **Import** — `python3 -c "from tuilib.framework.worker_pool import WorkerPool; from tuilib.framework import DataCache, TaskRunnerPool"` succeeds.
2. **Pytest green** — `pytest tuilib/tests/test_worker_pool.py` — all 5+ tests pass.
3. **No regression in parking-space** — `git status` in parking-space is clean; `python -m scripts.tui` still uses its existing `DataFetcher` unchanged.
4. **Public-surface diff** — `inspect.getmembers(WorkerPool)` includes schedule, force_refresh, invalidate, tick, stop, cache. Nothing else public. (Catches accidental API leakage from internal helpers.)

## Rollback

This plan only adds files inside `python-tui-lib`. If something goes wrong:

```
cd ~/python-tui-lib
git reset --hard <plan-1-final-sha>
```

Parking-space and WorldFoundry are unaffected; tuilib rolls back to its post-plan-1 state.

## Follow-on work (out of scope here)

- **`AsyncWorkerPool`** — an asyncio variant for consumers that prefer `await`-style orchestration. Same public API, different internals.
- **Priority + deadlines** — tag jobs with priority so a backlog drains critical work first. Current fetcher has no such need.
- **Exponential backoff on repeated failures** — if a job raises N times in a row, push its `next_fetch_time` out. Current fetcher swallows errors silently; this would surface systemic failures earlier.
- **Metrics hook** — opt-in `on_job_start` / `on_job_end` callbacks so consumers can wire Prometheus/Grafana/logfmt/whatever without modifying the pool.

## Critical files

- **New:** `tuilib/framework/worker_pool.py` — the class (~200 LOC)
- **New:** `tuilib/tests/test_worker_pool.py` — unit tests (~150 LOC)
- **Updated:** `tuilib/framework/__init__.py` — export `WorkerPool`
- **Updated:** `parking-space/plans/2026-04-19-migrate-to-tuilib.md` — plan 2 gains a formal reference to `WorkerPool` in its adapter-class section
