"""
PCR-054h — Post-fact license verification

After a folder is FINALIZED (the 6-point gate passed), we still don't
*know* the practitioner's license is real. The attestation is binding,
but trust-but-verify means we look it up in the public license registry
maintained by the appropriate authority:

  CPA          -> AICPA / state board CPA lookup
  PE           -> NCEES record-holder verification
  Attorney     -> State Bar admission search
  PMP          -> PMI verification
  RA           -> State architect board lookup

These authorities all have public lookup interfaces (some web, some API).
This module is the abstraction layer: each authority is a "provider"
that exposes verify(license_type, license_number, jurisdiction) ->
VerificationResult.

V1 STUB POLICY (HONEST, per Standing Decision 55)
=================================================
Real third-party lookups require API keys, captcha handling, or
HTML scraping for each authority. We aren't pretending to do that
yet. Instead each provider is a DETERMINISTIC STUB:

  - license numbers starting with 'GOOD'    -> verified (positive lookup)
  - license numbers starting with 'BAD'     -> flagged (license not found)
  - license numbers starting with 'EXP'     -> flagged (expired)
  - all other license numbers               -> verified by default
    (production stubs that pass through with low confidence -
    real lookups replace this in 054h-followup patches)

Each stub returns an evidence dict that names the authority + reason,
so when the real provider lands the call signature is identical.

STATE MACHINE
=============
This module transitions:
  FINALIZED  ->  VERIFYING  ->  VERIFIED   (positive lookup)
                            ->  FLAGGED    (negative or expired)

It is idempotent: folders already in VERIFIED/FLAGGED are skipped.

Composes with:
  PCR-054c engagement_folder  state machine + transition()
                              + verified_at / verified_via / verification_notes
  PCR-054e engagement_inbound  produces the attestation_payloads rows we look up
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.engagement_folder import (
    DEFAULT_DB_PATH as ENGAGEMENT_DB_PATH,
    FolderState,
    get_attestations,
    get_folder,
    list_folders,
    record_external_event,
    transition,
)

LOG = logging.getLogger("murphy.engagement_verification")


# ─────────────────────────────────────────────────────────────────────
# Provider mapping
# ─────────────────────────────────────────────────────────────────────


# license_type -> authority name used in evidence + audit
LICENSE_TYPE_TO_AUTHORITY = {
    "CPA":      "AICPA + state board lookup (stub)",
    "PE":       "NCEES record-holder verification (stub)",
    "Attorney": "State Bar admission search (stub)",
    "PMP":      "PMI verification (stub)",
    "RA":       "State architect board lookup (stub)",
}


# ─────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────


@dataclass
class VerificationResult:
    verified:        bool
    source:          str                # authority name
    license_number:  str
    license_type:    str
    jurisdiction:    str
    evidence:        Dict[str, Any] = field(default_factory=dict)
    error:           Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "verified":       self.verified,
            "source":         self.source,
            "license_number": self.license_number,
            "license_type":   self.license_type,
            "jurisdiction":   self.jurisdiction,
            "evidence":       dict(self.evidence),
            "error":          self.error,
        }


# ─────────────────────────────────────────────────────────────────────
# Provider stubs (each follows the same call signature)
# ─────────────────────────────────────────────────────────────────────


def _stub_verify(
    license_type: str,
    license_number: str,
    jurisdiction: str,
    *,
    authority: str,
) -> VerificationResult:
    """Shared stub logic used by every provider until real APIs land.

    Decision is deterministic on license_number prefix.
    """
    ln = (license_number or "").upper()

    if ln.startswith("BAD"):
        return VerificationResult(
            verified=False, source=authority,
            license_number=license_number, license_type=license_type,
            jurisdiction=jurisdiction,
            evidence={
                "lookup_outcome":  "no_record",
                "lookup_method":   "stub_deterministic_prefix",
                "matched_prefix":  "BAD",
            },
            error="license number not found in registry",
        )

    if ln.startswith("EXP"):
        return VerificationResult(
            verified=False, source=authority,
            license_number=license_number, license_type=license_type,
            jurisdiction=jurisdiction,
            evidence={
                "lookup_outcome":   "expired",
                "lookup_method":    "stub_deterministic_prefix",
                "matched_prefix":   "EXP",
            },
            error="license is recorded but expired",
        )

    # Default: verified. Either GOOD-prefix or any other format —
    # real provider will replace this with an actual lookup.
    return VerificationResult(
        verified=True, source=authority,
        license_number=license_number, license_type=license_type,
        jurisdiction=jurisdiction,
        evidence={
            "lookup_outcome":   "verified",
            "lookup_method":    "stub_deterministic_prefix",
            "match_confidence": "high" if ln.startswith("GOOD") else "stub_passthrough",
        },
        error=None,
    )


def verify_cpa(license_number: str, jurisdiction: str) -> VerificationResult:
    return _stub_verify("CPA", license_number, jurisdiction,
                        authority=LICENSE_TYPE_TO_AUTHORITY["CPA"])


def verify_pe(license_number: str, jurisdiction: str) -> VerificationResult:
    return _stub_verify("PE", license_number, jurisdiction,
                        authority=LICENSE_TYPE_TO_AUTHORITY["PE"])


def verify_attorney(license_number: str, jurisdiction: str) -> VerificationResult:
    return _stub_verify("Attorney", license_number, jurisdiction,
                        authority=LICENSE_TYPE_TO_AUTHORITY["Attorney"])


def verify_pmp(license_number: str, jurisdiction: str) -> VerificationResult:
    return _stub_verify("PMP", license_number, jurisdiction,
                        authority=LICENSE_TYPE_TO_AUTHORITY["PMP"])


def verify_ra(license_number: str, jurisdiction: str) -> VerificationResult:
    return _stub_verify("RA", license_number, jurisdiction,
                        authority=LICENSE_TYPE_TO_AUTHORITY["RA"])


PROVIDERS = {
    "CPA":      verify_cpa,
    "PE":       verify_pe,
    "Attorney": verify_attorney,
    "PMP":      verify_pmp,
    "RA":       verify_ra,
}


# ─────────────────────────────────────────────────────────────────────
# Lookup dispatcher
# ─────────────────────────────────────────────────────────────────────


def verify(
    license_type: str,
    license_number: str,
    jurisdiction: str,
) -> VerificationResult:
    """Dispatch to the right provider, or return an unknown-license-type error."""
    provider = PROVIDERS.get(license_type)
    if provider is None:
        return VerificationResult(
            verified=False,
            source="dispatcher",
            license_number=license_number,
            license_type=license_type,
            jurisdiction=jurisdiction,
            evidence={"known_types": sorted(PROVIDERS.keys())},
            error=f"no provider configured for license_type={license_type!r}",
        )
    return provider(license_number, jurisdiction)


# ─────────────────────────────────────────────────────────────────────
# Folder-level verification (single)
# ─────────────────────────────────────────────────────────────────────


def verify_folder(
    engagement_id: str,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, Any]:
    """Run verification on a single FINALIZED folder.

    1. fetch folder; skip if not FINALIZED
    2. pull most-recent attestation payload (license_number_claimed)
    3. transition FINALIZED -> VERIFYING (we're about to do the work)
    4. dispatch to provider
    5. transition VERIFYING -> VERIFIED OR FLAGGED with notes
    """
    folder = get_folder(engagement_id, db_path=db_path)
    if folder is None:
        return {"ok": False, "skipped": True, "reason": "folder not found"}

    if folder.state is not FolderState.FINALIZED:
        return {
            "ok": False, "skipped": True,
            "reason": f"folder in state {folder.state.value}, not finalized",
            "engagement_id": engagement_id,
        }

    atts = get_attestations(engagement_id, db_path=db_path)
    if not atts:
        return {
            "ok": False, "skipped": True,
            "reason": "no attestation payload on file",
            "engagement_id": engagement_id,
        }
    # Use the most recent attestation
    att = atts[-1]
    license_number = att.get("license_number_claimed") or ""
    license_type = att.get("license_type_claimed") or folder.license_type_required or ""
    jurisdiction = att.get("license_jurisdiction_claimed") or folder.jurisdiction_required or ""

    # Step 1: advance to VERIFYING
    transition(
        engagement_id,
        FolderState.VERIFYING,
        actor="system:engagement_verification",
        reason=f"starting verification of {license_type} #{license_number}",
        db_path=db_path,
    )

    # Step 2: call the provider
    result = verify(license_type, license_number, jurisdiction)

    # Step 3: record outbound-event with the provider response
    record_external_event(
        engagement_id=engagement_id,
        event_type="license_verification",
        actor="system:engagement_verification",
        payload=result.as_dict(),
        db_path=db_path,
    )

    # Step 4: VERIFIED or FLAGGED
    now = time.time()
    if result.verified:
        notes = f"{license_type} #{license_number} verified via {result.source}"
        transition(
            engagement_id, FolderState.VERIFIED,
            actor="system:engagement_verification",
            reason=notes,
            update_fields={
                "verified_at":        now,
                "verified_via":       result.source,
                "verification_notes": notes[:500],
            },
            db_path=db_path,
        )
        outcome = "verified"
    else:
        notes = f"{license_type} #{license_number}: {result.error or 'verification failed'}"
        transition(
            engagement_id, FolderState.FLAGGED,
            actor="system:engagement_verification",
            reason=notes,
            update_fields={
                "verified_at":        now,   # when we did the check
                "verified_via":       result.source,
                "verification_notes": notes[:500],
            },
            db_path=db_path,
        )
        outcome = "flagged"

    return {
        "ok":            True,
        "engagement_id": engagement_id,
        "outcome":       outcome,
        "result":        result.as_dict(),
    }


# ─────────────────────────────────────────────────────────────────────
# Batch processor (cron entrypoint)
# ─────────────────────────────────────────────────────────────────────


def verify_finalized_engagements(
    limit: int = 100,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, Any]:
    """Scan FINALIZED folders, verify each, push to VERIFIED/FLAGGED."""
    folders = list_folders(state=FolderState.FINALIZED, limit=limit, db_path=db_path)

    verified = 0
    flagged = 0
    skipped = 0
    results: List[Dict[str, Any]] = []

    for folder in folders:
        outcome = verify_folder(folder.engagement_id, db_path=db_path)
        results.append(outcome)
        if outcome.get("skipped"):
            skipped += 1
        elif outcome.get("outcome") == "verified":
            verified += 1
        elif outcome.get("outcome") == "flagged":
            flagged += 1

    return {
        "ok":         True,
        "scanned":    len(folders),
        "verified":   verified,
        "flagged":    flagged,
        "skipped":    skipped,
        "results":    results,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
