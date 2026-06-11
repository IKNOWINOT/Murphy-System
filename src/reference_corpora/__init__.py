"""
Reference corpora — pluggable grounding sources.

Each adapter exposes:
  search(query: str, limit: int = 5) -> List[Ref]
  fetch(url: str) -> Optional[Doc]
  cite(ref: Ref) -> str       # human-readable attribution

A Ref is a dict: {title, url, snippet, corpus_name, retrieved_ts}
A Doc is a dict: {title, url, body_text, retrieved_ts}

Conservative defaults: respect robots.txt, cache aggressively,
attribute every use, never claim authorship of cited content.
"""
from .engineering_toolbox import EngineeringToolboxAdapter

ADAPTERS = {
    "engineering_toolbox": EngineeringToolboxAdapter(),
}


def get(name: str):
    return ADAPTERS.get(name)


def available() -> list:
    return list(ADAPTERS.keys())
