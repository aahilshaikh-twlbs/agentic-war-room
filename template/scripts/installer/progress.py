"""In-place progress lines for the installer execute phase.

Renders ``[N/M] <label> ........ ok (2.3s)`` with an in-place ANSI clear
(``\\r\\x1b[K``) so the running line is overwritten by its final result. Used
as a context manager: it self-marks ``ok`` on clean exit and ``fail`` if the
body raised.

Stdlib only, Python >=3.9.
"""
from __future__ import annotations

import sys
import time
from typing import Optional, TextIO

_CLEAR_LINE = "\r\x1b[K"


class StageRunner:
    """Context manager rendering one execute-phase stage line."""

    def __init__(
        self,
        index: int,
        total: int,
        label: str,
        *,
        stream: Optional[TextIO] = None,
        width: int = 56,
        clock=time.monotonic,
    ):
        self.index = index
        self.total = total
        self.label = label
        self.stream = stream if stream is not None else sys.stdout
        self.width = width
        self._clock = clock
        self._t0 = 0.0
        self.status = ""

    def _prefix(self) -> str:
        return "[%d/%d] %s " % (self.index, self.total, self.label)

    def __enter__(self) -> "StageRunner":
        self._t0 = self._clock()
        self.stream.write(self._prefix())
        self.stream.flush()
        return self

    def _finish(self, status: str, detail: str = "") -> None:
        if self.status:  # already finished explicitly
            return
        self.status = status
        elapsed = self._clock() - self._t0
        tail = status if not detail else "%s -- %s" % (status, detail)
        right = "%s (%.1fs)" % (tail, elapsed)
        prefix = self._prefix()
        pad = max(3, self.width - len(prefix) - len(right) - 1)
        line = "%s%s%s %s" % (_CLEAR_LINE, prefix, "." * pad, right)
        self.stream.write(line + "\n")
        self.stream.flush()

    def ok(self, detail: str = "") -> None:
        self._finish("ok", detail)

    def fail(self, detail: str = "") -> None:
        self._finish("fail", detail)

    def skip(self, detail: str = "") -> None:
        self._finish("skip", detail)

    def warn(self, detail: str = "") -> None:
        self._finish("warn", detail)

    def __exit__(self, exc_type, exc, tb) -> bool:
        if not self.status:
            if exc_type is None:
                self.ok()
            else:
                self.fail(str(exc)[:48])
        return False  # never suppress exceptions
