"""PCR-090g.0 — Verify claims about /api/* endpoints existing."""
import threading
import time
from typing import Set, Optional
from .base import VerifierBase, Claim, VerifyResult

_ROUTES: Set[str] = set()
_LAST_LOAD: float = 0.0
_LOCK = threading.Lock()
_TTL = 120


def _refresh_routes():
    """Load currently-registered routes from the running FastAPI app."""
    global _ROUTES, _LAST_LOAD
    try:
        # Lazy import — only available within the live app process
        from src.runtime.app import app  # type: ignore
        new = set()
        for route in app.routes:
            path = getattr(route, "path", None)
            if path and path.startswith("/"):
                # Normalize {param} placeholders to a recognizable form
                new.add(path)
        _ROUTES = new
        _LAST_LOAD = time.time()
    except Exception:
        pass


def _ensure_routes():
    with _LOCK:
        if time.time() - _LAST_LOAD > _TTL or not _ROUTES:
            _refresh_routes()


class EndpointVerifier(VerifierBase):
    claim_types = ("endpoint",)

    def verify(self, claim: Claim) -> VerifyResult:
        _ensure_routes()
        path = claim.subject or ""
        if not path.startswith("/"):
            return VerifyResult(status="unverifiable", note="not a path-shaped subject")
        if not _ROUTES:
            return VerifyResult(status="unverifiable", note="route cache empty")
        # Exact match
        if path in _ROUTES:
            return VerifyResult(
                status="verified",
                ground_truth=f"route {path} registered in app",
                ground_truth_source="fastapi.app.routes",
                confidence=0.95,
            )
        # Templated match — e.g. /api/converge/{domain} matches /api/converge/work
        for route_path in _ROUTES:
            if "{" in route_path:
                # Build a regex from the template
                import re
                pattern = re.escape(route_path)
                pattern = re.sub(r"\\\{[^}]+\\\}", r"[^/]+", pattern)
                if re.fullmatch(pattern, path):
                    return VerifyResult(
                        status="verified",
                        ground_truth=f"route {path} matches template {route_path}",
                        ground_truth_source="fastapi.app.routes",
                        confidence=0.9,
                    )
        if claim.predicate == "exists" and claim.object_value == "true":
            return VerifyResult(
                status="refuted",
                ground_truth=f"no registered route matches {path} (have {len(_ROUTES)} routes)",
                ground_truth_source="fastapi.app.routes",
                confidence=0.85,
            )
        return VerifyResult(status="unverifiable", note="no match")
