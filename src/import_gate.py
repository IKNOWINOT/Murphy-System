"""
PATCH-IMPORT-GATE-001 (2026-05-28 R46) — Per-Job Artifact Intake Gate

WHAT THIS IS:
  Declarative gate that says "this chain template requires THESE artifacts
  before any downstream step can execute." It's the input-side counterpart to
  domain_gate_generator (which is the output validation side).

WHY IT EXISTS:
  chain_engine.create_chain accepts a template_code + tenant_id today and
  starts execution immediately. There is no concept of required INPUTS — a
  chain for "build SaaS MVP" doesn't check whether the founder uploaded a
  requirements doc, a design brief, or a target-customer profile first.

  Per R32 directive (Corey), there are TWO kinds of gates:
    OUTPUT gates: domain_gate_generator validates code/tests/docs AFTER
    INPUT gates:  THIS module — required artifacts BEFORE chain proceeds

HOW IT FITS:
  document_processor.py classifies 7 doc types from uploads.
  chain_engine.create_chain creates a chain instance.
  import_gate sits between them:

    upload → document_processor → classified artifact stored
    chain_template → import_gate.declare_required(template_code) → required set
    chain_create → import_gate.check_missing(chain_id, tenant_id) → list of gaps

KEY CONCEPTS:
  - REQUIRED: artifact types a chain template needs before it can run
  - PROVIDED: artifact types currently uploaded for a tenant/chain
  - MISSING: REQUIRED - PROVIDED — gates the chain, sends to HITL or intake

ENDPOINTS / PUBLIC SURFACE:
  declare_required_artifacts(template_code) -> List[str]
  check_missing(chain_id, tenant_id) -> Dict[str, Any]
  get_template_requirements_catalog() -> Dict[str, List[str]]

DEPENDENCIES:
  - document_processor.DocumentType enum (read-only)
  - chain_engine.db.chain_templates (read-only, optional)
  - own SQLite table: chain_template_requirements

DB SCHEMA OWNED:
  chain_template_requirements (
    template_code TEXT,
    required_artifact_type TEXT,
    rationale TEXT,
    is_mandatory INTEGER DEFAULT 1,
    PRIMARY KEY (template_code, required_artifact_type)
  )

KNOWN LIMITS:
  - Hardcoded requirement catalog for 3 templates initially (saas_mvp,
    enterprise_outreach, marketing_launch). Founder can extend via
    add_requirement(template_code, artifact_type, rationale).
  - Does NOT call upload — only declares + checks. Upload path is upstream.
  - Does NOT auto-route to HITL — caller decides.

LAST UPDATED: 2026-05-28 R46
"""

import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger("import_gate")

_DB_PATH = "/var/lib/murphy-production/import_gate.db"

# ── Hardcoded initial requirements catalog ────────────────────────────────────
_INITIAL_REQUIREMENTS: Dict[str, List[tuple]] = {
    "saas_mvp": [
        ("REQUIREMENTS", "Product requirements — what we're building", True),
        ("DESIGN",       "User-flow design or wireframes",              False),
        ("BUSINESS",     "Business model / monetization plan",          True),
    ],
    "enterprise_outreach": [
        ("BUSINESS",     "Founder business plan / value prop",          True),
        ("SPECIFICATION","Target-customer profile (ICP)",               True),
    ],
    "marketing_launch": [
        ("BUSINESS",     "Positioning / value prop doc",                True),
        ("DESIGN",       "Brand / visual assets",                       False),
        ("REQUIREMENTS", "Launch checklist / target outcomes",          False),
    ],
}


def _ensure_db() -> None:
    """Create schema if absent. Idempotent."""
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=3)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chain_template_requirements (
                template_code           TEXT NOT NULL,
                required_artifact_type  TEXT NOT NULL,
                rationale               TEXT,
                is_mandatory            INTEGER DEFAULT 1,
                created_at              TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (template_code, required_artifact_type)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ctr_template
            ON chain_template_requirements(template_code)
        """)
        # Seed initial catalog if table is empty
        cur = conn.execute("SELECT COUNT(*) FROM chain_template_requirements")
        if cur.fetchone()[0] == 0:
            for tmpl, items in _INITIAL_REQUIREMENTS.items():
                for art_type, rationale, mandatory in items:
                    conn.execute(
                        "INSERT OR IGNORE INTO chain_template_requirements "
                        "(template_code, required_artifact_type, rationale, is_mandatory) "
                        "VALUES (?, ?, ?, ?)",
                        (tmpl, art_type, rationale, 1 if mandatory else 0),
                    )
            logger.info("import_gate: seeded %d templates", len(_INITIAL_REQUIREMENTS))
        conn.commit()
    finally:
        conn.close()


def declare_required_artifacts(template_code: str) -> List[Dict[str, Any]]:
    """
    Return the list of artifact types this chain template requires before
    it can run.

    Args:
        template_code: chain template identifier (e.g. "saas_mvp")

    Returns:
        List of {artifact_type, rationale, is_mandatory} dicts.
        Empty list if template has no requirements declared.
    """
    _ensure_db()
    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=2)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT required_artifact_type AS artifact_type, rationale, "
            "is_mandatory FROM chain_template_requirements "
            "WHERE template_code = ? ORDER BY is_mandatory DESC, artifact_type",
            (template_code,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _list_provided_artifacts(tenant_id: str, chain_id: Optional[str]) -> List[str]:
    """
    Return artifact types currently provided for this tenant/chain.
    Falls back to empty list if data_room_artifacts table unavailable.
    """
    provided: List[str] = []
    candidate_dbs = [
        "/var/lib/murphy-production/entity_graph.db",
        "/var/lib/murphy-production/data_room.db",
        "/var/lib/murphy-production/records_assembly.db",
    ]
    for db_path in candidate_dbs:
        if not os.path.exists(db_path):
            continue
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
            try:
                # try common shapes — tolerate column variance
                for sql in [
                    "SELECT DISTINCT artifact_type FROM data_room_artifacts "
                    "WHERE tenant_id = ?",
                    "SELECT DISTINCT doc_type FROM data_room_artifacts "
                    "WHERE tenant_id = ?",
                    "SELECT DISTINCT type FROM data_room_artifacts "
                    "WHERE tenant_id = ?",
                ]:
                    try:
                        cur = conn.execute(sql, (tenant_id,))
                        provided = [r[0] for r in cur.fetchall() if r[0]]
                        if provided:
                            return provided
                    except sqlite3.OperationalError:
                        continue
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("import_gate: %s read failed: %s", db_path, exc)
    return provided


def check_missing(
    template_code: str,
    tenant_id: str = "platform",
    chain_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return what's missing for this chain to legally start.

    Args:
        template_code: chain template the founder wants to run.
        tenant_id: tenant context (defaults to "platform" = Murphy's own).
        chain_id: optional specific chain instance.

    Returns:
        {
          "template_code": str,
          "tenant_id": str,
          "required": [{artifact_type, rationale, is_mandatory}],
          "provided": [artifact_type],
          "missing_mandatory": [artifact_type],
          "missing_optional":  [artifact_type],
          "can_proceed": bool,   # True iff no mandatory gaps
          "wire_version": "IMPORT-GATE-001",
        }

    Never raises. Missing data shows up as empty lists.
    """
    required = declare_required_artifacts(template_code)
    provided = _list_provided_artifacts(tenant_id, chain_id)

    mandatory_set = {r["artifact_type"] for r in required if r["is_mandatory"]}
    optional_set  = {r["artifact_type"] for r in required if not r["is_mandatory"]}
    provided_set  = set(provided)

    missing_mandatory = sorted(mandatory_set - provided_set)
    missing_optional  = sorted(optional_set  - provided_set)

    can_proceed = len(missing_mandatory) == 0
    logger.info(
        "import_gate: template=%s tenant=%s mandatory_gaps=%d optional_gaps=%d "
        "can_proceed=%s",
        template_code, tenant_id, len(missing_mandatory), len(missing_optional),
        can_proceed,
    )

    return {
        "template_code": template_code,
        "tenant_id": tenant_id,
        "required": required,
        "provided": provided,
        "missing_mandatory": missing_mandatory,
        "missing_optional": missing_optional,
        "can_proceed": can_proceed,
        "wire_version": "IMPORT-GATE-001",
    }


def get_template_requirements_catalog() -> Dict[str, List[Dict[str, Any]]]:
    """Return full catalog: template_code → list of requirement dicts."""
    _ensure_db()
    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=2)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT template_code, required_artifact_type AS artifact_type, "
            "rationale, is_mandatory FROM chain_template_requirements "
            "ORDER BY template_code, is_mandatory DESC"
        )
        out: Dict[str, List[Dict[str, Any]]] = {}
        for row in cur.fetchall():
            d = dict(row)
            out.setdefault(d.pop("template_code"), []).append(d)
        return out
    finally:
        conn.close()


def add_requirement(
    template_code: str,
    artifact_type: str,
    rationale: str = "",
    is_mandatory: bool = True,
) -> bool:
    """Extend catalog — founder/operator can add new requirements at runtime."""
    _ensure_db()
    conn = sqlite3.connect(_DB_PATH, timeout=3)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO chain_template_requirements "
            "(template_code, required_artifact_type, rationale, is_mandatory) "
            "VALUES (?, ?, ?, ?)",
            (template_code, artifact_type, rationale, 1 if is_mandatory else 0),
        )
        conn.commit()
        logger.info("import_gate: added requirement %s/%s", template_code, artifact_type)
        return True
    finally:
        conn.close()


if __name__ == "__main__":
    import json as _j
    print("── Test 1: declare_required_artifacts('saas_mvp') ──")
    print(_j.dumps(declare_required_artifacts("saas_mvp"), indent=2))

    print("\n── Test 2: check_missing('saas_mvp', tenant_id='t1') ──")
    r = check_missing("saas_mvp", tenant_id="t1")
    print(_j.dumps(r, indent=2, default=str))

    print("\n── Test 3: catalog ──")
    print(_j.dumps(get_template_requirements_catalog(), indent=2))
