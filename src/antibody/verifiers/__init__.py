"""PCR-090g.0 — Verifier registry.

Shared between post-hoc (PCR-090f) and realtime (PCR-090g) surfaces.
"""
from typing import List, Optional
from .base import VerifierBase, Claim, VerifyResult
from .cache import cache_stats, known_tables, refresh_if_stale
from .table_verifier import TableVerifier
from .file_verifier import FileVerifier
from .endpoint_verifier import EndpointVerifier

# Order matters: more specific first
_VERIFIERS: List[VerifierBase] = [
    TableVerifier(),
    FileVerifier(),
    EndpointVerifier(),
]


def verify_claim(claim: Claim) -> VerifyResult:
    """Find a verifier for the claim and run it."""
    for v in _VERIFIERS:
        if v.can_verify(claim):
            return v._timed_verify(claim)
    return VerifyResult(
        status="unverifiable",
        error="AB_E002 no verifier for claim_type",
        note=f"unsupported claim_type: {claim.claim_type}",
    )


def supported_claim_types() -> List[str]:
    types = set()
    for v in _VERIFIERS:
        types.update(v.claim_types)
    return sorted(types)
