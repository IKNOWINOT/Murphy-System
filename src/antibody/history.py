"""PCR-090h — History writers (append-only, no mutation)."""
import hashlib
import json
import sqlite3
import time
import uuid
from typing import Optional, Dict, Any

CLAIM_DB = "/var/lib/murphy-production/claim_ledger.db"
BUTTON_DB = "/var/lib/murphy-production/button_commission.db"
INTV_DB = "/var/lib/murphy-production/antibody_interventions.db"


def log_claim_event(
    claim_id: str,
    event: str,
    prior_status: Optional[str] = None,
    new_status: Optional[str] = None,
    prior_ground_truth: Optional[str] = None,
    new_ground_truth: Optional[str] = None,
    prior_source: Optional[str] = None,
    new_source: Optional[str] = None,
    verifier_name: Optional[str] = None,
    verifier_confidence: Optional[float] = None,
    verifier_latency_ms: Optional[int] = None,
    note: Optional[str] = None,
) -> int:
    conn = sqlite3.connect(CLAIM_DB, timeout=2.0)
    try:
        cur = conn.execute(
            """INSERT INTO claim_ledger_history
               (claim_id, ts, event, prior_status, new_status,
                prior_ground_truth, new_ground_truth, prior_source, new_source,
                verifier_name, verifier_confidence, verifier_latency_ms, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (claim_id, time.time(), event, prior_status, new_status,
             prior_ground_truth, new_ground_truth, prior_source, new_source,
             verifier_name, verifier_confidence, verifier_latency_ms, note),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def log_button_event_full(
    button_id: str,
    event: str,
    prior: Optional[Dict[str, str]] = None,
    new: Optional[Dict[str, str]] = None,
    actor: str = "system",
    detail: str = "",
) -> int:
    prior = prior or {}
    new = new or {}
    conn = sqlite3.connect(BUTTON_DB, timeout=2.0)
    try:
        cur = conn.execute(
            """INSERT INTO button_commission_history
               (button_id, ts, event,
                prior_intent, new_intent,
                prior_success, new_success,
                prior_fail, new_fail,
                prior_error, new_error,
                prior_status, new_status,
                actor, detail)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (button_id, time.time(), event,
             prior.get("intent"), new.get("intent"),
             prior.get("success_surface"), new.get("success_surface"),
             prior.get("fail_surface"), new.get("fail_surface"),
             prior.get("error_surface"), new.get("error_surface"),
             prior.get("status"), new.get("status"),
             actor, detail),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _hash_content(parts: list) -> str:
    h = hashlib.sha256()
    for p in parts:
        if p is None:
            p = ""
        h.update(str(p).encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()


def log_antibody_intervention(
    prompt: str,
    original_response: str,
    action_taken: str,
    corrected_response: Optional[str] = None,
    claims_found: int = 0,
    claims_refuted: int = 0,
    refuted_claims: Optional[list] = None,
    regulatory_flag: str = "safe",
    agent_name: str = "unknown",
    tenant_id: Optional[str] = None,
    engagement_id: Optional[str] = None,
) -> str:
    """Log a single antibody intervention with hash chain.
    
    Returns intervention_id.
    """
    iid = f"intv_{uuid.uuid4().hex[:12]}"
    ts = time.time()
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    orig_hash = hashlib.sha256(original_response.encode("utf-8")).hexdigest()
    corr_hash = hashlib.sha256(corrected_response.encode("utf-8")).hexdigest() if corrected_response else None
    refuted_json = json.dumps(refuted_claims or [])

    conn = sqlite3.connect(INTV_DB, timeout=2.0)
    try:
        # Look up previous event hash for chain
        prev_row = conn.execute(
            "SELECT event_hash FROM antibody_interventions ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        prev_hash = prev_row[0] if prev_row else None

        event_hash = _hash_content([
            iid, ts, prompt_hash, orig_hash, action_taken, corr_hash,
            claims_found, claims_refuted, refuted_json, regulatory_flag,
            agent_name, tenant_id, engagement_id, prev_hash,
        ])

        conn.execute(
            """INSERT INTO antibody_interventions
               (intervention_id, ts, prompt_hash, original_response, original_hash,
                claims_found, claims_refuted, action_taken, corrected_response,
                corrected_hash, refuted_claims_json, regulatory_flag,
                agent_name, tenant_id, engagement_id, prev_event_hash, event_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (iid, ts, prompt_hash, original_response, orig_hash,
             claims_found, claims_refuted, action_taken, corrected_response,
             corr_hash, refuted_json, regulatory_flag,
             agent_name, tenant_id, engagement_id, prev_hash, event_hash),
        )
        conn.commit()
        return iid
    finally:
        conn.close()


def verify_chain(limit: int = 100) -> Dict[str, Any]:
    """Walk antibody_interventions chain, verify hash linkage."""
    conn = sqlite3.connect(f"file:{INTV_DB}?mode=ro", uri=True, timeout=2.0)
    try:
        rows = conn.execute(
            """SELECT intervention_id, ts, prompt_hash, original_hash,
               action_taken, corrected_hash, claims_found, claims_refuted,
               refuted_claims_json, regulatory_flag, agent_name, tenant_id,
               engagement_id, prev_event_hash, event_hash
               FROM antibody_interventions
               ORDER BY ts ASC LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    broken = []
    prev_hash = None
    for r in rows:
        (iid, ts, p_h, o_h, action, c_h, found, refuted, refuted_json, flag,
         agent, tenant, eng, claimed_prev, claimed_event) = r
        if claimed_prev != prev_hash:
            broken.append({"intervention_id": iid, "issue": "prev_hash mismatch"})
        recomputed = _hash_content([
            iid, ts, p_h, o_h, action, c_h, found, refuted, refuted_json,
            flag, agent, tenant, eng, claimed_prev,
        ])
        if recomputed != claimed_event:
            broken.append({"intervention_id": iid, "issue": "event_hash mismatch"})
        prev_hash = claimed_event
    return {
        "total": len(rows),
        "broken": broken,
        "chain_intact": len(broken) == 0,
    }
