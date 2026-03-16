"""Utilities for computing diffs between memory entry versions."""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import List

@dataclass
class MemoryVersion:
    text: str
    editor: str
    timestamp: float
    reason: str = ""


def get_diff(old: str, new: str) -> str:
    """Return a unified diff string between two text blocks."""
    return "\n".join(
        difflib.unified_diff(
            old.splitlines(), new.splitlines(), fromfile="before", tofile="after", lineterm=""
        )
    )
