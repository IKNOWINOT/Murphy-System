"""Simple caching proxy for external API calls."""
from __future__ import annotations

import time
from functools import lru_cache
import requests

@lru_cache(maxsize=256)
def cached_get(url: str) -> str:
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return resp.text
