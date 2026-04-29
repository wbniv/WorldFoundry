"""
Thread/queue/timer bridge between Blender's main thread and the Rust asset
provider.  Workers run in a ThreadPoolExecutor; results arrive back on the
main thread via a queue.Queue polled by a bpy.app.timers tick.
"""

import queue
import threading
from concurrent.futures import ThreadPoolExecutor

_Q: queue.Queue = queue.Queue()
_EXECUTOR: ThreadPoolExecutor | None = None
_TIMER_RUNNING = False
_TICK_INTERVAL = 0.1  # seconds

# How many provider searches can fly at once across all workers
_MAX_WORKERS = 8


def _get_executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None or _EXECUTOR._shutdown:
        _EXECUTOR = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="wf_asset")
    return _EXECUTOR


def submit(fn, *args, on_result=None, on_error=None):
    """Run fn(*args) on a worker thread.

    on_result(result) and on_error(exc) are called on the main thread once the
    future resolves.  Both callbacks are optional.
    """
    def _work():
        try:
            result = fn(*args)
            _Q.put(("ok", on_result, result))
        except Exception as exc:
            _Q.put(("err", on_error, exc))

    _get_executor().submit(_work)
    _ensure_timer()


def _ensure_timer():
    global _TIMER_RUNNING
    if not _TIMER_RUNNING:
        import bpy
        bpy.app.timers.register(_tick, first_interval=_TICK_INTERVAL)
        _TIMER_RUNNING = True


def _tick():
    """Drain the result queue on the main thread."""
    try:
        while True:
            tag, callback, payload = _Q.get_nowait()
            if callback is not None:
                try:
                    callback(payload)
                except Exception as e:
                    print(f"[wf_asset] callback error: {e}")
    except queue.Empty:
        pass
    return _TICK_INTERVAL  # reschedule


def shutdown():
    """Shut down the executor cleanly (called from add-on unregister)."""
    global _EXECUTOR, _TIMER_RUNNING
    if _EXECUTOR is not None:
        _EXECUTOR.shutdown(wait=False)
        _EXECUTOR = None
    _TIMER_RUNNING = False
    # The timer will stop rescheduling once it returns None... but we've
    # already dropped the reference.  Leave any pending results in the queue
    # since Blender is unregistering anyway.
