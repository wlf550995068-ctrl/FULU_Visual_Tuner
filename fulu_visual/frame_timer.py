"""A pacing adapter for moderngl-window's existing timer, not a window loop."""
import time
from moderngl_window.timers.clock import Timer


class FrameTimer(Timer):
    def __init__(self, fps):
        super().__init__()
        self.period = 1.0/fps
        self.deadline = None
        self.monotonic_start = None
        self.previous = 0.0

    @property
    def time(self):
        if self.monotonic_start is None:
            return 0.0
        return time.perf_counter()-self.monotonic_start

    def start(self):
        super().start()
        self.monotonic_start = time.perf_counter()
        self.deadline = self.monotonic_start
        self.previous = 0.0

    def next_frame(self):
        now = time.perf_counter()
        if self.deadline is not None and self.deadline > now:
            time.sleep(self.deadline-now)
        current = self.time
        delta = current-self.previous
        self.previous = current
        self._frames += 1
        self._fps = 1/delta if delta>0 else 0.0
        # Drop missed deadlines; never replay accumulated frames after a stall.
        now = time.perf_counter()
        self.deadline += self.period
        if self.deadline < now:
            self.deadline = now+self.period
        return current,delta

    def stop(self):
        return self.time,self.time
