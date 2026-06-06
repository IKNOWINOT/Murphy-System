"""Cap H.3 — web_search + read_web_page.

Reuses Murphy's existing `web_tool.search()` (DuckDuckGo, no API key)
and `web_tool.fetch()` (requests + bs4 text extraction).

Mirrors Base44 superagent's web_search tool which accepts an action
in {google_search, news_search, jobs_search, google_maps_search,
read_web_page}. Murphy's underlying transport is DuckDuckGo, so:

  - "google_search"      → DDG general search (closest equivalent)
  - "news_search"        → DDG with "news" appended (best effort)
  - "jobs_search"        → DDG with "jobs" appended
  - "google_maps_search" → DDG with "near me" / location hint
  - "read_web_page"      → web_tool.fetch(url)

Future enhancement (logged): swap DDG for Tavily/Brave/Serper when a
key is added. The cap signature is action-agnostic.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

import web_tool as _wt  # Murphy's existing web tool

VALID_ACTIONS = {
    "google_search", "news_search", "jobs_search",
    "google_maps_search", "read_web_page",
}
MAX_RESULTS = 10
DEFAULT_RESULTS = 8


def web_search_one(query: WebQuery_like) -> Dict[str, Any]:
    """Run a single sub-query. Returns a structured result block."""
    ...


# Use a simple dict-based query format (matches Base44's $defs.WebQuery)
def _run_single(action: str, qu: str, max_results: int = DEFAULT_RESULTS) -> Dict[str, Any]:
    block: Dict[str, Any] = {
        "action": action, "query_or_url": qu,
        "ok": False, "error": None,
    }
    try:
        action = (action or "").strip().lower()
        if action not in VALID_ACTIONS:
            block["error"] = f"invalid action: {action} (valid: {sorted(VALID_ACTIONS)})"
            return block
        if not qu or not str(qu).strip():
            block["error"] = "empty query_or_url"
            return block

        if action == "read_web_page":
            if not str(qu).startswith(("http://", "https://")):
                block["error"] = "read_web_page requires full http(s):// URL"
                return block
            r = _wt.fetch(str(qu), timeout=20)
            if isinstance(r, dict):
                block["ok"] = bool(r.get("ok", True))
                block["url"] = r.get("url")
                block["title"] = r.get("title")
                block["text"] = r.get("text", "")[:50_000]  # cap 50KB
                block["status_code"] = r.get("status_code")
                block["link_count"] = len(r.get("links") or [])
                if not block["ok"] and not block["error"]:
                    block["error"] = f"fetch failed status={block['status_code']}"
            else:
                block["error"] = f"unexpected fetch return: {type(r).__name__}"
            return block

        # Search modes — augment query for non-general search modes
        max_results = max(1, min(MAX_RESULTS, int(max_results)))
        q = str(qu).strip()
        if action == "news_search":
            q = f"{q} news"
        elif action == "jobs_search":
            q = f"{q} jobs"
        elif action == "google_maps_search":
            q = f"{q} location address"
        # else google_search → use as-is

        results = _wt.search(q, max_results=max_results) or []
        # Normalize
        norm: List[Dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            norm.append({
                "title":   item.get("title") or item.get("heading") or "",
                "url":     item.get("url") or item.get("href") or "",
                "snippet": item.get("snippet") or item.get("body") or item.get("description") or "",
            })
        block["ok"] = True
        block["results"] = norm
        block["count"] = len(norm)
        block["underlying_engine"] = "duckduckgo"
        return block
    except Exception as e:
        block["error"] = f"{type(e).__name__}: {e}"
        return block


def web_search(queries: List[Dict[str, str]]) -> Dict[str, Any]:
    """Run multiple sub-queries concurrently-ish.

    Mirrors Base44's web_search shape: a list of {action, query_or_url}.
    """
    out: Dict[str, Any] = {"ok": False, "blocks": [], "error": None}
    try:
        if not queries or not isinstance(queries, list):
            out["error"] = "queries must be a non-empty list"
            return out
        for q in queries:
            if not isinstance(q, dict):
                out["blocks"].append({"ok": False, "error": "query item not a dict"})
                continue
            action = q.get("action") or q.get("type") or "google_search"
            qu = q.get("query_or_url") or q.get("query") or q.get("url") or ""
            out["blocks"].append(_run_single(action, qu, max_results=int(q.get("max_results", DEFAULT_RESULTS))))
        out["ok"] = all(b.get("ok") for b in out["blocks"])
        out["count"] = sum(1 for b in out["blocks"] if b.get("ok"))
        out["block_count"] = len(out["blocks"])
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out


def read_web_page(url: str) -> Dict[str, Any]:
    """Convenience single-page fetch (matches Base44's read_web_page action)."""
    return _run_single("read_web_page", url)


# ── Executor wrappers ─────────────────────────────────────────────────────

def execute_web_search(**kwargs) -> Dict[str, Any]:
    # Accept either explicit queries list, or single (action, query_or_url)
    if "queries" in kwargs:
        return web_search(kwargs["queries"])
    action = kwargs.get("action", "google_search")
    qu = kwargs.get("query_or_url") or kwargs.get("query") or kwargs.get("url") or ""
    return web_search([{"action": action, "query_or_url": qu,
                        "max_results": kwargs.get("max_results", DEFAULT_RESULTS)}])


def execute_read_web_page(**kwargs) -> Dict[str, Any]:
    return read_web_page(kwargs.get("url") or kwargs.get("query_or_url", ""))


# Hint to remove stray placeholder symbol
del web_search_one  # noqa
