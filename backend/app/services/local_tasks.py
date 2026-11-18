from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore


class LocalExecutor:
    """One analytics thread with a fixed bound on running and queued work."""

    def __init__(self, capacity: int = 16):
        self._slots = BoundedSemaphore(capacity)
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analyst-local")

    def submit(self, run: Callable[[str], None], job_id: str) -> bool:
        if not self._slots.acquire(blocking=False):
            return False
        try:
            future = self._pool.submit(run, job_id)
        except RuntimeError:
            self._slots.release()
            return False
        future.add_done_callback(lambda _: self._slots.release())
        return True

    def close(self):
        # Pending jobs retain their database records for a manual retry after
        # the next startup. The launcher also bounds process shutdown.
        self._pool.shutdown(wait=False, cancel_futures=True)
