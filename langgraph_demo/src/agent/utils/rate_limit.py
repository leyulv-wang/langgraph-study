from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, max_per_minute: int):
        self._max_per_minute = max(1, int(max_per_minute))
        self._lock = threading.Lock()
        self._window_start = time.monotonic()
        self._count = 0

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._window_start
                if elapsed >= 60:
                    self._window_start = now
                    self._count = 0

                if self._count < self._max_per_minute:
                    self._count += 1
                    return

                wait_s = max(0.0, 60 - elapsed)

            time.sleep(wait_s)
