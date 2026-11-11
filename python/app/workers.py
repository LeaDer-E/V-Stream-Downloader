import logging
import traceback
from typing import Any, Callable, Optional
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(object)


class AsyncTask(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except RuntimeError:
            # Qt signal target may already be deleted during application exit
            pass
        except Exception as exc:
            logger.error("Worker exception in %s: %s\n%s", getattr(self.fn, "__name__", "fn"), exc, traceback.format_exc())
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass


_ACTIVE_KEEPALIVE: set[AsyncTask] = set()


def run_async(
    fn: Callable[..., Any],
    on_done: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    *args: Any,
    **kwargs: Any,
) -> AsyncTask:
    task = AsyncTask(fn, *args, **kwargs)
    _ACTIVE_KEEPALIVE.add(task)

    def _cleanup_done(res: Any) -> None:
        _ACTIVE_KEEPALIVE.discard(task)
        if on_done is not None:
            on_done(res)

    def _cleanup_err(err: str) -> None:
        _ACTIVE_KEEPALIVE.discard(task)
        if on_error is not None:
            on_error(err)

    task.signals.finished.connect(_cleanup_done)
    task.signals.error.connect(_cleanup_err)
    QThreadPool.globalInstance().start(task)
    return task


def wait_for_all_workers(timeout_ms: int = 3500) -> bool:
    """Waits gracefully for active QThreadPool workers to finish before quitting."""
    pool = QThreadPool.globalInstance()
    return pool.waitForDone(timeout_ms)
