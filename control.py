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
        # A model usage limit holds only model calls; downloads and frame extraction carry on.
        self.model_go = threading.Event()
        self.model_go.set()
        self.limit: dict | None = None   # {"what", "until", "message", "since"} while waiting for a limit
        self._lock = threading.Lock()

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

    def model_checkpoint(self) -> bool:
        """Before a model call: wait while paused, and while a usage limit is being waited out."""
        while not self.is_set() and (not self.go.is_set() or not self.model_go.is_set()):
            (self.go if not self.go.is_set() else self.model_go).wait(0.5)
        return self.is_set()

    POLL = 15 * 60   # when a limit does not say when it resets, try again this often

    def wait_limit(self, lim: dict, what: str, log) -> bool:
        """A model call hit a usage limit: hold every model call of this run until the limit resets
        (or Retry now is pressed), then return True so the call is made again. False if stopped."""
        with self._lock:
            target = (lim.get("until") + 30) if lim.get("until") else time.time() + self.POLL
            if self.model_go.is_set():   # the first call to hit it
                self.limit = {"what": what, "until": target, "message": lim.get("message", ""), "since": time.time()}
                self.model_go.clear()
                when = time.strftime("%H:%M", time.localtime(target))
                log(f"{what} usage limit reached ({lim.get('message', '')[:160]}). Model calls wait until about {when}"
                    + ("" if lim.get("until") else " and are tried again then")
                    + "; downloads and frame extraction carry on. It resumes by itself.")
            elif self.limit:
                self.limit["until"] = max(self.limit["until"], target)
        while not self.is_set():
            if self.model_go.is_set():   # Retry now, or another waiting call resumed
                return True
            with self._lock:
                if self.limit and time.time() >= self.limit["until"]:
                    self.limit = None
                    self.model_go.set()
                    log(f"{what}: trying again after the usage limit wait")
                    return True
            self.model_go.wait(1)
        return False

    def retry_now(self) -> None:
        with self._lock:
            if not self.model_go.is_set():
                self.limit = None
                self.model_go.set()


def checkpoint_of(cancel) -> callable:
    """The waiting check for a stop flag: a RunControl's checkpoint, or a plain Event's is_set."""
    return getattr(cancel, "checkpoint", None) or (cancel.is_set if cancel is not None else (lambda: False))
