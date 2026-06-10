"""PCR-090g.0 — Verify claims about files existing on disk."""
import os
from .base import VerifierBase, Claim, VerifyResult


_ALLOWED_PREFIXES = (
    "/opt/Murphy-System/",
    "/var/lib/murphy-production/",
    "/etc/murphy-production/",
)


class FileVerifier(VerifierBase):
    claim_types = ("file",)

    def verify(self, claim: Claim) -> VerifyResult:
        path = claim.subject
        if not path:
            return VerifyResult(status="unverifiable", note="no path")
        # Sanitize: only check paths under our trusted prefixes
        if not any(path.startswith(p) for p in _ALLOWED_PREFIXES):
            return VerifyResult(
                status="unverifiable",
                note=f"path outside trusted prefixes (no verifier coverage)",
            )
        if "../" in path or path.startswith("/."):
            return VerifyResult(status="unverifiable", note="path traversal blocked")
        if os.path.exists(path):
            return VerifyResult(
                status="verified",
                ground_truth=f"file exists: {path}",
                ground_truth_source="filesystem",
                confidence=1.0,
            )
        return VerifyResult(
            status="refuted",
            ground_truth=f"no such file: {path}",
            ground_truth_source="filesystem",
            confidence=0.95,
        )
