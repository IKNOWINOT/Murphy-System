"""PCR-090g.0 — Verifier base + result types.

Shared by both post-hoc (PCR-090f) and realtime (PCR-090g) surfaces.
"""
import time
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class Claim:
    """A factual claim extracted from an LLM response."""
    claim_id: str = ""
    text: str = ""
    claim_type: str = ""       # 'table' | 'endpoint' | 'file' | 'schema' | 'metric' | 'generic'
    subject: str = ""          # what is being claimed about
    predicate: str = ""        # the relationship: 'exists', 'has_column', 'returns', etc.
    object_value: str = ""     # the asserted value
    source_agent: str = ""
    confidence: float = 0.5


@dataclass
class VerifyResult:
    """Outcome of running a verifier on a claim."""
    status: str                # 'verified' | 'refuted' | 'unverifiable'
    ground_truth: Optional[str] = None       # actual value (or None if unknown)
    ground_truth_source: Optional[str] = None  # which db/file/source proved it
    confidence: float = 0.0    # 0-1
    latency_ms: int = 0
    error: Optional[str] = None
    note: Optional[str] = None

    @property
    def is_verified(self) -> bool:
        return self.status == "verified"

    @property
    def is_refuted(self) -> bool:
        return self.status == "refuted"


class VerifierBase:
    """Abstract verifier — subclasses implement can_verify + verify."""

    claim_types: tuple = ()    # which claim_types this verifier handles

    def can_verify(self, claim: Claim) -> bool:
        return claim.claim_type in self.claim_types

    def verify(self, claim: Claim) -> VerifyResult:  # pragma: no cover
        raise NotImplementedError

    def _timed_verify(self, claim: Claim) -> VerifyResult:
        """Internal: wraps verify() with timing."""
        t0 = time.time()
        try:
            result = self.verify(claim)
        except Exception as e:
            result = VerifyResult(
                status="unverifiable",
                error=f"{type(e).__name__}: {e}",
            )
        result.latency_ms = int((time.time() - t0) * 1000)
        return result
