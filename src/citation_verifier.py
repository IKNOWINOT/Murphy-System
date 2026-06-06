"""
R65b-B1+B2 — Citation & Plagiarism Verifier
============================================

WHAT THIS IS
  Single-pass verifier for Murphy deliverables. Given a body of generated
  text, extracts cited URLs and run-time-checks each one (HTTP 200 + snippet
  overlap with the citation's claim). Also runs a lightweight plagiarism
  gate by hashing paragraphs and looking for verbatim matches against the
  cited sources.

WHY
  Founder R65 directive: "no plagiarism, cited sources are real and
  verifiable, prove it live."

PUBLIC SURFACE
  verify_deliverable(text: str) → dict
    Returns:
      {
        ok: bool,
        citations: [
          {url, claim, http_code, snippet_match: bool, latency_ms},
          ...
        ],
        plagiarism: {
          paragraphs_checked: int,
          flagged: [{para_idx, similarity, matched_url}],
          score: float (0..1, 1 = unique)
        },
        verdict: 'pass' | 'warn' | 'fail'
      }

DESIGN
  - Citation extraction: regex for [N] URL · markdown [text](url) · plain URLs
  - Each citation HEAD-fetched with 8s timeout
  - Snippet match: split URL page text into 5-word shingles, compute Jaccard
    overlap with the surrounding text in the deliverable
  - Plagiarism gate: each paragraph >40 words is hashed (rolling 5-word
    shingles); we compare against the 200-char preview from each verified
    URL's actual page content. Similarity = (shared shingles / total)
  - Total budget: 30s for a 12-page deliverable with ~20 citations

LICENSE: BSL 1.1 — Inoni LLC / Corey Post
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import urllib.parse
from typing import Dict, List, Optional, Set, Tuple

try:
    import requests
    _REQUESTS_OK = True
except Exception:
    _REQUESTS_OK = False

logger = logging.getLogger(__name__)

# ── Extraction ──────────────────────────────────────────────────────────
_URL_PATTERNS = [
    # Markdown link  [text](https://...)
    re.compile(r'\[([^\]]+)\]\((https?://[^\)\s]+)\)'),
    # Footnote with URL  [1] https://...
    re.compile(r'\[(\d+)\]\s+(https?://[^\s,]+)'),
    # Plain URL preceded by "Source:" or similar
    re.compile(r'(?:Source|Cite|See|Ref|Reference)s?:\s*(https?://\S+)', re.IGNORECASE),
    # Plain URL anywhere
    re.compile(r'(?<![\(\[])(https?://[^\s\)\],]+)'),
]

# URLs that are licenses, platform self-refs, or repo metadata — not real citations.
# Per founder R65b-B4 directive: "Apache is for software it generates. Citations are
# for books written." A bibliographic citation refers to source material the author
# consulted — not the license under which the deliverable is published.
_NON_CITATION_PATTERNS = [
    re.compile(r"apache\.org/licenses?/", re.IGNORECASE),
    re.compile(r"creativecommons\.org/licenses?/", re.IGNORECASE),
    re.compile(r"opensource\.org/licenses?/", re.IGNORECASE),
    re.compile(r"gnu\.org/licenses?/", re.IGNORECASE),
    re.compile(r"mit-license\.org", re.IGNORECASE),
    re.compile(r"github\.com/[^/]+/[^/]+/blob/[^/]+/LICENSE", re.IGNORECASE),
    re.compile(r"github\.com/[^/]+/[^/]+/?$", re.IGNORECASE),  # bare repo link
    re.compile(r"^https?://murphy\.systems/?", re.IGNORECASE),  # platform self-ref
    re.compile(r"inoni\.(com|llc|systems)", re.IGNORECASE),  # publisher self-ref
]

def _is_real_citation(url: str) -> bool:
    """Filter out license/platform/self-ref URLs that aren't bibliographic citations."""
    for pat in _NON_CITATION_PATTERNS:
        if pat.search(url):
            return False
    return True

def extract_citations(text: str) -> List[Dict]:
    """Find every cited URL in the text + capture surrounding context.

    Excludes license URLs, platform self-references, and bare repo links —
    those are attribution/metadata, not bibliographic citations.
    """
    seen: Set[str] = set()
    cites: List[Dict] = []
    skipped: List[str] = []
    for pat in _URL_PATTERNS:
        for m in pat.finditer(text):
            groups = m.groups()
            url = groups[-1] if groups else m.group(0)
            url = url.rstrip('.,;:!?)')
            if url in seen:
                continue
            seen.add(url)
            if not _is_real_citation(url):
                skipped.append(url)
                continue
            # Capture 200 chars of context around the match
            ctx_start = max(0, m.start() - 200)
            ctx_end   = min(len(text), m.end() + 200)
            cites.append({
                "url": url,
                "claim": text[ctx_start:ctx_end].strip(),
                "anchor_text": groups[0] if len(groups) > 1 else None,
            })
    if skipped:
        logger.debug("Skipped %d non-citation URLs (licenses/platform): %s",
                     len(skipped), skipped[:5])
    return cites

# ── Verification ────────────────────────────────────────────────────────
_HEADERS = {
    "User-Agent": "Murphy-Citation-Verifier/1.0 (+https://murphy.systems)",
}

def _fetch_url(url: str, timeout: float = 8.0) -> Tuple[Optional[int], str, float]:
    """HEAD then GET (if HEAD allows). Returns (status_code, snippet, latency_ms)."""
    if not _REQUESTS_OK:
        return None, "", 0.0
    start = time.time()
    try:
        # Try HEAD first (cheap)
        h = requests.head(url, timeout=timeout, headers=_HEADERS, allow_redirects=True)
        if h.status_code >= 400:
            return h.status_code, "", (time.time() - start) * 1000
        # If HEAD ok, GET the first 8KB for snippet
        g = requests.get(url, timeout=timeout, headers=_HEADERS, stream=True, allow_redirects=True)
        snippet = g.raw.read(8192, decode_content=True).decode("utf-8", errors="replace")
        g.close()
        # Strip HTML tags crudely for shingling
        snippet = re.sub(r"<script[^<]*</script>", " ", snippet, flags=re.I|re.S)
        snippet = re.sub(r"<style[^<]*</style>", " ", snippet, flags=re.I|re.S)
        snippet = re.sub(r"<[^>]+>", " ", snippet)
        snippet = re.sub(r"\s+", " ", snippet).strip()
        return g.status_code, snippet[:4000], (time.time() - start) * 1000
    except Exception as e:
        return None, f"_err:{type(e).__name__}", (time.time() - start) * 1000

def _shingles(text: str, n: int = 5) -> Set[str]:
    """Return n-word shingles of text as a set."""
    words = re.findall(r"\w+", text.lower())
    return {" ".join(words[i:i+n]) for i in range(len(words) - n + 1)}

def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0

def verify_citation(cite: Dict, timeout: float = 8.0) -> Dict:
    """Verify a single citation: fetch URL, check overlap with claim."""
    code, snippet, latency = _fetch_url(cite["url"], timeout=timeout)
    if code is None or code >= 400:
        return {
            **cite,
            "http_code": code or 0,
            "snippet_match": False,
            "similarity": 0.0,
            "latency_ms": round(latency),
            "snippet_chars": 0,
            "verdict": "broken" if (code is None or code >= 400) else "unreachable",
        }
    claim_sh = _shingles(cite.get("claim", ""))
    src_sh = _shingles(snippet)
    sim = _jaccard(claim_sh, src_sh)
    return {
        **cite,
        "http_code": code,
        "snippet_match": sim > 0.05,
        "similarity": round(sim, 4),
        "latency_ms": round(latency),
        "snippet_chars": len(snippet),
        "verdict": "verified" if sim > 0.05 else ("reachable_no_match" if code < 400 else "broken"),
    }

# ── Plagiarism Gate ─────────────────────────────────────────────────────
def _paragraphs(text: str, min_words: int = 40) -> List[str]:
    paras = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paras if len(p.split()) >= min_words]

def check_plagiarism(text: str, source_snippets: List[str]) -> Dict:
    """For each paragraph, compute max similarity to any source snippet.

    If similarity > 0.4, flag as potential plagiarism.
    Score = 1 - (mean of max similarities); 1 = fully original.
    """
    paras = _paragraphs(text)
    if not paras:
        return {"paragraphs_checked": 0, "flagged": [], "score": 1.0}
    source_shingles = [_shingles(s) for s in source_snippets if s]
    flagged: List[Dict] = []
    sims: List[float] = []
    for idx, para in enumerate(paras):
        para_sh = _shingles(para)
        if not para_sh:
            continue
        max_sim = 0.0
        max_idx = -1
        for s_idx, src in enumerate(source_shingles):
            j = _jaccard(para_sh, src)
            if j > max_sim:
                max_sim = j
                max_idx = s_idx
        sims.append(max_sim)
        if max_sim > 0.4:
            flagged.append({
                "para_idx": idx,
                "similarity": round(max_sim, 4),
                "matched_source_idx": max_idx,
                "preview": para[:120],
            })
    score = 1.0 - (sum(sims) / len(sims)) if sims else 1.0
    return {
        "paragraphs_checked": len(paras),
        "flagged": flagged,
        "score": round(score, 4),
    }

# ── Top-level ───────────────────────────────────────────────────────────
def verify_deliverable(text: str, max_citations: int = 30, timeout_per_citation: float = 8.0) -> Dict:
    """Full pass: extract citations, verify each, run plagiarism gate.

    Total budget ≤ 30s for typical 12-page deliverable. Bounded by
    max_citations and per-call timeout.
    """
    start = time.time()
    cites_raw = extract_citations(text)[:max_citations]
    verified: List[Dict] = []
    source_snippets: List[str] = []
    for c in cites_raw:
        r = verify_citation(c, timeout=timeout_per_citation)
        verified.append(r)
        if r.get("snippet_chars", 0) > 0:
            # Capture the snippet for plagiarism matching
            _, snip, _ = _fetch_url(c["url"], timeout=timeout_per_citation)
            if snip:
                source_snippets.append(snip)
    plag = check_plagiarism(text, source_snippets)
    verified_count = sum(1 for v in verified if v["verdict"] == "verified")
    broken_count = sum(1 for v in verified if v["verdict"] in ("broken", "unreachable"))

    # Verdict logic
    if not verified:
        verdict = "no_citations"
    elif broken_count > len(verified) * 0.3:
        verdict = "fail"
    elif plag["flagged"]:
        verdict = "warn"
    elif verified_count == len(verified) and plag["score"] > 0.8:
        verdict = "pass"
    else:
        verdict = "warn"

    return {
        "ok": True,
        "citations": verified,
        "citation_summary": {
            "total": len(verified),
            "verified": verified_count,
            "broken": broken_count,
            "unmatched": len(verified) - verified_count - broken_count,
            "note": "License/repo/platform URLs excluded — not bibliographic citations",
        },
        "plagiarism": plag,
        "verdict": verdict,
        "elapsed_ms": round((time.time() - start) * 1000),
    }


# ── Self-test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = """
According to recent research, Murphy's law has held up under analysis [1] https://en.wikipedia.org/wiki/Murphy%27s_law.

The Python language was created by Guido van Rossum in the late 1980s as a successor to ABC ([source](https://www.python.org/doc/essays/foreword/)).

This paragraph is original content written for testing.
We're checking whether the verifier can detect originality
versus plagiarism via shingle-overlap with the cited sources.
The point is to validate the verifier's verdict logic.
"""
    result = verify_deliverable(sample)
    import json
    print(json.dumps(result, indent=2))
