"""Utilities for progress bars."""
from __future__ import annotations

from contextlib import contextmanager
try:
    from tqdm import tqdm
except Exception:  # pragma: no cover - optional dependency
    tqdm = None


@contextmanager
def progress_bar(total: int, description: str = ''):
    if tqdm is None:
        class Dummy:
            def update(self, *_):
                pass
            def close(self):
                pass
        bar = Dummy()
    else:
        bar = tqdm(total=total, desc=description)
    try:
        yield bar
    finally:
        bar.close()
