"""A run's Stop flag that also carries Pause.

It is a threading.Event, set when the run is stopped, so everything that already checks
`cancel.is_set()` or passes it to the model runners keeps working. checkpoint() is the place
work waits while the run is paused: before each download, each frame, each model call.
"""
from __future__ import annotations

import threading
import time


class RunControl(threading.Event):
    def __init__(self) -> None:
        super().__init__()
        self.go = threading.Event()
        self.go.set()
        self.paused_since: float | None = None
        self.paused_total = 0.0

    @property
    def paused(self) -> bool:
        return not self.go.is_set()

    def pause(self) -> None:
        if self.go.is_set():
            self.paused_since = time.time()
            self.go.clear()

    def resume(self) -> None:
        if not self.go.is_set():
            self.paused_total += time.time() - (self.paused_since or time.time())
            self.paused_since = None
            self.go.set()

    def paused_for(self) -> float:
        """Seconds this run has spent paused, including a pause still going on."""
        return self.paused_total + (time.time() - self.paused_since if self.paused_since else 0.0)

    def checkpoint(self) -> bool:
        """Wait here while paused. Returns True when the run has been stopped."""
        while not self.go.is_set() and not self.is_set():
            self.go.wait(0.5)
        return self.is_set()


def checkpoint_of(cancel) -> callable:
    """The waiting check for a stop flag: a RunControl's checkpoint, or a plain Event's is_set."""
    return getattr(cancel, "checkpoint", None) or (cancel.is_set if cancel is not None else (lambda: False))
