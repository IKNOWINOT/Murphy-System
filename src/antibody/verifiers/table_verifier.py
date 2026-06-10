"""PCR-090g.0 — Verify claims about tables existing."""
from .base import VerifierBase, Claim, VerifyResult
from .cache import known_tables, table_to_db


class TableVerifier(VerifierBase):
    claim_types = ("table",)

    def verify(self, claim: Claim) -> VerifyResult:
        if not claim.subject:
            return VerifyResult(
                status="unverifiable",
                note="no subject",
                confidence=0.0,
            )
        # Tier 1: cache lookup
        tables = known_tables()
        if claim.subject in tables:
            db = table_to_db(claim.subject)
            return VerifyResult(
                status="verified",
                ground_truth=f"table '{claim.subject}' exists in {db}",
                ground_truth_source=db or "registry_db_inventory",
                confidence=0.95,
                note="tier1_cache",
            )
        # If the claim asserts existence ("X is a table") but cache doesn't have it
        if claim.predicate == "exists" and claim.object_value == "true":
            return VerifyResult(
                status="refuted",
                ground_truth=f"no table named '{claim.subject}' in registry_db_inventory ({len(tables)} tables catalogued)",
                ground_truth_source="registry_db_inventory",
                confidence=0.85,
                note="tier1_cache_miss",
            )
        return VerifyResult(
            status="unverifiable",
            confidence=0.0,
            note="no match in cache, can't disprove",
        )
