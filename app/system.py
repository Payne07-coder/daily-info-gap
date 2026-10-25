from __future__ import annotations

import ctypes
import os
from contextlib import contextmanager
from typing import Iterator


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


@contextmanager
def keep_system_awake() -> Iterator[None]:
    if os.name != "nt":
        yield
        return
    kernel32 = ctypes.windll.kernel32
    kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    try:
        yield
    finally:
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)

