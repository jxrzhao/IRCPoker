"""In-place progress bar for streaming pipelines. Stdlib-only, no deps.

The bar updates at most every ``min_interval`` seconds to keep per-hand
overhead negligible. It is automatically suppressed when ``sys.stderr`` is
not a TTY (e.g. when output is redirected to a log file) so piped logs do
not get spammed with carriage-return updates.

The percentage shown is computed against whichever denominator is available:

* hands processed / ``max_hands``, if a hand cap was set, else
* bytes read / ``total_bytes`` (the default when streaming a file).

Each refresh prints a single line of the form::

    [###########---------------]  37.2% |   1,820,310 hands |  82,514 h/s |
        elapsed 0:00:22 | ETA 0:00:37
"""

from __future__ import annotations

import sys
import time


class Progress:
    """In-place stderr progress bar."""

    def __init__(
        self,
        total_bytes: int,
        max_hands: int | None,
        *,
        enabled: bool = True,
        width: int = 30,
        min_interval: float = 0.2,
    ) -> None:
        self.total_bytes  = total_bytes
        self.max_hands    = max_hands
        self.enabled      = enabled and sys.stderr.isatty()
        self.width        = width
        self.min_interval = min_interval

        self._start       = time.monotonic()
        self._last_render = 0.0
        self._last_len    = 0
        self._hands       = 0
        self._bytes       = 0
        self._closed      = False

    # ------------------------------------------------------------------ API

    def update(self, hands: int, bytes_read: int) -> None:
        """Record the latest progress and possibly redraw the bar."""
        self._hands = hands
        self._bytes = bytes_read
        if not self.enabled:
            return
        now = time.monotonic()
        if now - self._last_render < self.min_interval:
            return
        self._last_render = now
        self._render(now)

    def close(self) -> None:
        """Render the final state and move to a new line. Idempotent."""
        if self._closed:
            return
        self._closed = True
        if self.enabled:
            self._render(time.monotonic())
            sys.stderr.write("\n")
            sys.stderr.flush()

    # -------------------------------------------------------------- internal

    def _render(self, now: float) -> None:
        if self.max_hands is not None and self.max_hands > 0:
            frac = min(1.0, self._hands / self.max_hands)
        elif self.total_bytes > 0:
            frac = min(1.0, self._bytes / self.total_bytes)
        else:
            frac = 0.0
        filled = int(round(frac * self.width))
        bar = "#" * filled + "-" * (self.width - filled)
        elapsed = max(now - self._start, 1e-6)
        rate = self._hands / elapsed
        if 0.0 < frac < 1.0:
            eta = self._fmt_secs((1.0 - frac) / frac * elapsed)
        elif frac >= 1.0:
            eta = "0:00:00"
        else:
            eta = "  ?  "
        line = (
            f"[{bar}] {frac * 100:5.1f}% | "
            f"{self._hands:>10,} hands | "
            f"{rate:>7,.0f} h/s | "
            f"elapsed {self._fmt_secs(elapsed)} | "
            f"ETA {eta}"
        )
        sys.stderr.write("\r" + line.ljust(self._last_len))
        sys.stderr.flush()
        self._last_len = len(line)

    @staticmethod
    def _fmt_secs(secs: float) -> str:
        secs = int(secs)
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
