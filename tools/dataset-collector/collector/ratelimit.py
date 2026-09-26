import time


class RateLimiter:
    """Simple fixed-interval limiter: at most `per_minute` calls per minute."""

    def __init__(self, per_minute: int, sleep_fn=time.sleep, clock=time.monotonic):
        self.interval = 60.0 / max(1, per_minute)
        self.sleep_fn = sleep_fn
        self.clock = clock
        self._last = None

    def wait(self):
        now = self.clock()
        if self._last is not None:
            elapsed = now - self._last
            if elapsed < self.interval:
                self.sleep_fn(self.interval - elapsed)
        self._last = self.clock()


def retry_backoff(fn, retries: int = 3, base_delay: float = 1.0, sleep_fn=time.sleep):
    """Call fn(); on exception retry with exponential backoff (base, 2x, 4x...)."""
    attempt = 0
    while True:
        try:
            return fn()
        except Exception:
            attempt += 1
            if attempt > retries:
                raise
            sleep_fn(base_delay * (2 ** (attempt - 1)))
