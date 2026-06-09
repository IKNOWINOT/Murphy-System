"""
PCR-054d — Engagement Outreach (outbound engagement_request email)

Connects the engagement state machine to the existing murphy_mail.send_email
infrastructure. When a folder moves drafting -> outreach_queued, this module
composes a defensible engagement_request email, fires it through Postfix,
and records the outbound event on the folder.

Composes with:
  PCR-054c engagement_folder.transition() / record_external_event()
  PCR-054f engagement_rates.quote_rate()
  R300    murphy_mail.send_email()

The compose path is a pure function (`compose_engagement_request`) so the
template can be unit-tested without touching SMTP. The send path
(`send_engagement_request`) is the thin I/O wrapper.

DEFAULT POLICY (founder-implicit "follow recommendations"):
  - All outbound is dry_run=False ONLY when the caller explicitly opts in
    via send_engagement_request(..., dry_run=False). Default is dry_run=True
    so accidental real sends require an explicit override.
  - The email_log row carries deal_id=<engagement_id> for cross-system
    correlation between murphy_mail.email_log and engagement_events.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.engagement_folder import (
    DEFAULT_DB_PATH as ENGAGEMENT_DB_PATH,
    FolderState,
    get_folder,
    record_external_event,
    transition,
)
from src.engagement_rates import RateQuote, quote_rate

LOG = logging.getLogger("murphy.engagement_outreach")


# ─────────────────────────────────────────────────────────────────────
# Defaults + branding
# ─────────────────────────────────────────────────────────────────────


DEFAULT_FROM_NAME = "Murphy on behalf of {tenant_id}"
DEFAULT_SUBJECT   = "Engagement Request — {artifact_type} review and attestation"

# Email body template. Plain text, no markdown — most mail clients render
# this cleanly. The template is intentionally short and direct because
# practitioners are time-constrained.
BODY_TEMPLATE = """\
Hello{salutation_name},

You have been invited to a professional engagement on behalf of
{tenant_id}, coordinated by Murphy on their behalf.

ENGAGEMENT
  Engagement ID:   {engagement_id}
  Artifact type:   {artifact_type}
  Jurisdiction:    {jurisdiction_required}
  License needed:  {license_type_required}

PROPOSED FEE
  ${usd_total:.2f} total ({hours_estimated} hours estimated at ${hourly_usd:.2f}/hour)
  {citation}

WHAT WE'RE ASKING FOR
  1. Review the attached draft for accuracy, completeness, and compliance.
  2. If you concur, reply with the attestation language below, including
     your active license credentials. Your reply IS the act of attestation.
  3. If you do NOT concur, reply with the specific edits or concerns you
     have, and we will revise and resubmit.

ATTESTATION LANGUAGE TO INCLUDE IN YOUR REPLY (if you concur)
---
I, {{your full name}}, holder of {license_type_required} license
number {{your license number}}, issued by {jurisdiction_required},
current and in good standing through {{your expiration date}},
have personally reviewed engagement {engagement_id} and take
professional responsibility for the conclusions reached in this
artifact. I attest to its accuracy and compliance with applicable
standards in {jurisdiction_required}.

  Signed: {{your name}}
  License #: {{your license number}}
  Date: {{today}}
---

DRAFT
{draft_preview}

If you accept this engagement, please reply within {response_deadline_days}
business days. If you cannot take this engagement, please reply with
"DECLINE" so we can route to another practitioner.

Thank you,
Murphy
on behalf of {tenant_id}
"""


# ─────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────


@dataclass
class ComposedEmail:
    """The pure output of compose_engagement_request()."""
    to_addr:   str
    from_name: str
    subject:   str
    body:      str
    quote:     RateQuote


# ─────────────────────────────────────────────────────────────────────
# Pure compose path (no I/O)
# ─────────────────────────────────────────────────────────────────────


def compose_engagement_request(
    engagement_id: str,
    practitioner_email: str,
    tenant_id: str,
    artifact_type: str,
    license_type_required: str,
    jurisdiction_required: str,
    draft_preview: str,
    hours_estimated: float = 8.0,
    salutation_name: Optional[str] = None,
    response_deadline_days: int = 5,
    rate_source: str = "bls",
    rate_percentile: int = 90,
) -> ComposedEmail:
    """Compose the engagement_request email body + subject. Pure function.

    Raises ValueError on bad inputs from quote_rate (caller decides how to
    handle — typically by skipping outreach and flagging the folder).
    """
    quote = quote_rate(
        license_type=license_type_required,
        jurisdiction=jurisdiction_required,
        hours_estimated=hours_estimated,
        source=rate_source,
        percentile=rate_percentile,
    )

    salutation = f" {salutation_name}" if salutation_name else ""

    body = BODY_TEMPLATE.format(
        salutation_name=salutation,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        artifact_type=artifact_type,
        jurisdiction_required=jurisdiction_required,
        license_type_required=license_type_required,
        usd_total=quote.usd_total,
        hours_estimated=hours_estimated,
        hourly_usd=quote.hourly_usd,
        citation=quote.citation,
        draft_preview=draft_preview or "(no draft body provided)",
        response_deadline_days=response_deadline_days,
    )

    subject = DEFAULT_SUBJECT.format(artifact_type=artifact_type)
    from_name = DEFAULT_FROM_NAME.format(tenant_id=tenant_id)

    return ComposedEmail(
        to_addr=practitioner_email,
        from_name=from_name,
        subject=subject,
        body=body,
        quote=quote,
    )


# ─────────────────────────────────────────────────────────────────────
# Send path (I/O — wraps murphy_mail.send_email)
# ─────────────────────────────────────────────────────────────────────


def send_engagement_request(
    engagement_id: str,
    *,
    hours_estimated: float = 8.0,
    salutation_name: Optional[str] = None,
    response_deadline_days: int = 5,
    rate_source: str = "bls",
    rate_percentile: int = 90,
    dry_run: bool = True,
    advance_state: bool = True,
    db_path: str = ENGAGEMENT_DB_PATH,
) -> Dict[str, Any]:
    """Compose + send the engagement_request email for a folder.

    Default dry_run=True. Caller must explicitly pass dry_run=False to
    actually deliver mail.

    If advance_state=True, transitions the folder outreach_queued ->
    awaiting_attestation on successful send. Otherwise leaves state alone
    (useful for tests + previews).

    Returns dict with ok, log_id, message_id, status, composed (preview).
    """
    folder = get_folder(engagement_id, db_path=db_path)
    if folder is None:
        return {"ok": False, "error": f"folder {engagement_id} not found"}

    if folder.practitioner_email is None:
        return {"ok": False, "error": "folder has no practitioner_email; assign one first"}

    if folder.license_type_required is None or folder.jurisdiction_required is None:
        return {
            "ok": False,
            "error": "folder missing license_type_required or jurisdiction_required",
        }

    # Read draft preview from artifact_path
    draft_preview = ""
    try:
        with open(folder.artifact_path) as fh:
            draft_preview = fh.read()[:2000]
    except Exception as e:
        LOG.warning("PCR-054d could not read draft for %s: %s", engagement_id, e)

    try:
        composed = compose_engagement_request(
            engagement_id=engagement_id,
            practitioner_email=folder.practitioner_email,
            tenant_id=folder.tenant_id,
            artifact_type=folder.artifact_type,
            license_type_required=folder.license_type_required,
            jurisdiction_required=folder.jurisdiction_required,
            draft_preview=draft_preview,
            hours_estimated=hours_estimated,
            salutation_name=salutation_name,
            response_deadline_days=response_deadline_days,
            rate_source=rate_source,
            rate_percentile=rate_percentile,
        )
    except Exception as e:
        LOG.exception("PCR-054d compose failed for %s", engagement_id)
        return {"ok": False, "error": f"compose_failed: {type(e).__name__}: {e}"}

    # Send via murphy_mail. Import lazily so tests can monkeypatch easily.
    from src.murphy_mail import send_email

    send_result = send_email(
        to_addr=composed.to_addr,
        subject=composed.subject,
        body=composed.body,
        from_name=composed.from_name,
        deal_id=engagement_id,            # correlate email_log <-> engagement
        tenant_id=folder.tenant_id,
        dry_run=dry_run,
    )

    # Record the outbound event on the folder regardless of dry_run status
    record_external_event(
        engagement_id=engagement_id,
        event_type="outbound_email",
        actor="system:engagement_outreach",
        payload={
            "to":             composed.to_addr,
            "subject":        composed.subject,
            "rate_usd_total": composed.quote.usd_total,
            "rate_source":    composed.quote.machine_source,
            "send_status":    send_result.get("status"),
            "log_id":         send_result.get("log_id"),
            "dry_run":        dry_run,
        },
        db_path=db_path,
    )

    # Optionally advance state outreach_queued -> awaiting_attestation
    if advance_state and send_result.get("ok") and folder.state is FolderState.OUTREACH_QUEUED:
        try:
            transition(
                engagement_id,
                FolderState.AWAITING_ATTESTATION,
                actor="system:engagement_outreach",
                reason=f"engagement_request email {'dry-run logged' if dry_run else 'sent'} to {composed.to_addr}",
                update_fields={
                    "rate_quote_usd":    composed.quote.usd_total,
                    "rate_quote_source": composed.quote.machine_source,
                },
                db_path=db_path,
            )
        except Exception as e:
            LOG.warning("PCR-054d state advance failed for %s: %s", engagement_id, e)

    return {
        "ok":           bool(send_result.get("ok")),
        "log_id":       send_result.get("log_id"),
        "message_id":   send_result.get("message_id"),
        "status":       send_result.get("status"),
        "dry_run":      dry_run,
        "to":           composed.to_addr,
        "subject":      composed.subject,
        "rate_quote":   composed.quote.as_dict(),
        "body_preview": composed.body[:400],
    }
