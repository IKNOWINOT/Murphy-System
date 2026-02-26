from __future__ import annotations


def classify_line(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith('#'):
        return 'comment'
    if stripped.startswith('"""') or stripped.startswith("'''"):
        return 'docstring'
    return 'code'
