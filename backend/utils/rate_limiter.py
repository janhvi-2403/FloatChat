import logging
import threading
import time
from collections import deque
from typing import Deque, Dict

logger = logging.getLogger(__name__)


class RateLimiter:
    """Thread-safe sliding-window rate limiter for external API calls."""

    def __init__(self, calls_per_minute: int = 10) -> None:
        self.calls_per_minute = calls_per_minute
        self._window_seconds = 60
        self._timestamps: Deque[float] = deque()
        self._lock = threading.Lock()
        self._metrics = {
            "total_calls": 0,
            "blocks": 0,
            "wait_time_seconds": 0.0,
        }

    def acquire(self) -> float:
        with self._lock:
            now = time.time()
            window_start = now - self._window_seconds
            while self._timestamps and self._timestamps[0] < window_start:
                self._timestamps.popleft()

            if len(self._timestamps) < self.calls_per_minute:
                self._timestamps.append(now)
                self._metrics["total_calls"] += 1
                return 0.0

            self._metrics["blocks"] += 1
            wait_time = self._window_seconds - (now - self._timestamps[0]) + 0.1
            self._metrics["wait_time_seconds"] += wait_time
            logger.warning("Rate limit reached; waiting %.2f seconds", wait_time)
            time.sleep(wait_time)
            self._timestamps.append(time.time())
            self._metrics["total_calls"] += 1
            return wait_time

    def get_metrics(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._metrics)


rate_limiter = RateLimiter()
