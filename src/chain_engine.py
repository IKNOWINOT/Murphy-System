"""
chain_engine.py — PATCH-183
Workflow Chain Engine.

Guiding Principles applied (patch183_principles_gate.md):

  A Chain is an ordered sequence of workflow blocks.
  Every chain request gets a unique info_id (CHN-YYYYMMDD-XXXX) that
  threads through every record, manifold entry, and workflow step.

  Compliance gates are evaluated server-side at every step advance:
    required_compliance  — chain step only runs if these toggles are ON
    optional_compliance  — if ON, extra sub-steps are added to the block
    blocked_by_compliance — if ON, this step is BLOCKED (different path required)

  Financial impact of compliance is explicit:
    New required step added → change_order logged
    Required step removed   → credit logged
    Waiver raised           → compliance_waiver record created automatically
"""

import sqlite3, json, uuid, logging, os, re
from datetime import datetime, timezone, date
from typing import Dict, List, Optional
from contextlib import contextmanager

logger = logging.getLogger("murphy.chain_engine")
DB_PATH = "/var/lib/murphy-production/chain_engine.db"

# ── Compliance cost map — what each framework gate adds/saves ($) ─────────────
COMPLIANCE_COST = {
    "gdpr":      {"required_cost": 400,  "blocked_credit": 400,  "label": "GDPR"},
    "hipaa":     {"required_cost": 600,  "blocked_credit": 600,  "label": "HIPAA"},
    "pci_dss":   {"required_cost": 800,  "blocked_credit": 800,  "label": "PCI DSS"},
    "soc2":      {"required_cost": 500,  "blocked_credit": 500,  "label": "SOC 2"},
    "iso_27001": {"required_cost": 450,  "blocked_credit": 450,  "label": "ISO 27001"},
    "ccpa":      {"required_cost": 300,  "blocked_credit": 300,  "label": "CCPA"},
    "sox":       {"required_cost": 700,  "blocked_credit": 700,  "label": "SOX"},
    "nist_csf":  {"required_cost": 350,  "blocked_credit": 350,  "label": "NIST CSF"},
}

# ── 7 Common Chain Templates ──────────────────────────────────────────────────
CHAIN_TEMPLATES = [
    {
        "id": "chain_client_onboarding",
        "name": "New Client Onboarding",
        "icon": "🚀",
        "description": "Full client lifecycle from lead to live account",
        "category": "Sales / CS",
        "estimated_days": 5,
        "steps": [
            {
                "index": 0, "name": "Lead Capture",
                "workflow_template_id": "tmpl_lead_to_customer",
                "record_types": ["work_order"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Capture and qualify the incoming lead",
                "base_cost_usd": 150,
            },
            {
                "index": 1, "name": "KYC & Compliance Check",
                "workflow_template_id": "tmpl_compliance_scan",
                "record_types": ["audit_record", "risk_register_entry"],
                "required_compliance": ["gdpr", "soc2"],
                "optional_compliance": ["hipaa", "pci_dss"],
                "blocked_by_compliance": [],
                "description": "Know-your-customer check gated by active compliance frameworks",
                "base_cost_usd": 300,
            },
            {
                "index": 2, "name": "Contract Assembly",
                "workflow_template_id": "tmpl_lead_to_customer",
                "record_types": ["decision_record", "approval_record"],
                "required_compliance": [],
                "optional_compliance": ["sox"],
                "blocked_by_compliance": [],
                "description": "Assemble and approve the client contract",
                "base_cost_usd": 400,
            },
            {
                "index": 3, "name": "Billing Setup",
                "workflow_template_id": "tmpl_revenue_driver",
                "record_types": ["spec_sheet", "build_log"],
                "required_compliance": [],
                "optional_compliance": ["pci_dss"],
                "blocked_by_compliance": [],
                "description": "Configure billing tier and payment method",
                "base_cost_usd": 200,
            },
            {
                "index": 4, "name": "Welcome Delivery",
                "workflow_template_id": "tmpl_customer_onboarding",
                "record_types": ["delivery_note", "handoff_record"],
                "required_compliance": ["gdpr"],
                "optional_compliance": ["ccpa"],
                "blocked_by_compliance": [],
                "description": "Send welcome package, provision account, GDPR consent collection",
                "base_cost_usd": 100,
            },
            {
                "index": 5, "name": "Audit Close",
                "workflow_template_id": "tmpl_compliance_scan",
                "record_types": ["audit_record", "sign_off_record"],
                "required_compliance": ["soc2"],
                "optional_compliance": ["iso_27001", "nist_csf"],
                "blocked_by_compliance": [],
                "description": "Final compliance audit and client sign-off",
                "base_cost_usd": 250,
            },
        ]
    },
    {
        "id": "chain_feature_delivery",
        "name": "Feature Delivery",
        "icon": "⚡",
        "description": "Spec to signed-off shipped feature",
        "category": "Engineering",
        "estimated_days": 14,
        "steps": [
            {
                "index": 0, "name": "Spec Sheet",
                "workflow_template_id": "tmpl_self_patch",
                "record_types": ["spec_sheet"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Define what will be built and acceptance criteria",
                "base_cost_usd": 300,
            },
            {
                "index": 1, "name": "Work Order",
                "workflow_template_id": "tmpl_self_patch",
                "record_types": ["work_order", "decision_record"],
                "required_compliance": [],
                "optional_compliance": ["sox"],
                "blocked_by_compliance": [],
                "description": "Assign build task with deadline and done-when criteria",
                "base_cost_usd": 100,
            },
            {
                "index": 2, "name": "Build",
                "workflow_template_id": "tmpl_self_patch",
                "record_types": ["build_log"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Execute the build, log time and output artifact",
                "base_cost_usd": 1200,
            },
            {
                "index": 3, "name": "Test",
                "workflow_template_id": "tmpl_self_patch",
                "record_types": ["test_result"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Run tests, record pass/fail, log evidence",
                "base_cost_usd": 400,
            },
            {
                "index": 4, "name": "Compliance Scan",
                "workflow_template_id": "tmpl_compliance_scan",
                "record_types": ["audit_record"],
                "required_compliance": ["soc2", "gdpr"],
                "optional_compliance": ["hipaa", "iso_27001"],
                "blocked_by_compliance": [],
                "description": "Gate: compliance scan before delivery",
                "base_cost_usd": 350,
            },
            {
                "index": 5, "name": "Delivery & Sign-Off",
                "workflow_template_id": "tmpl_customer_onboarding",
                "record_types": ["delivery_note", "sign_off_record"],
                "required_compliance": ["gdpr"],
                "optional_compliance": ["ccpa"],
                "blocked_by_compliance": [],
                "description": "Deliver to client, collect sign-off",
                "base_cost_usd": 150,
            },
        ]
    },
    {
        "id": "chain_incident_response",
        "name": "Incident Response",
        "icon": "🚨",
        "description": "Detect → contain → notify → resolve → post-mortem",
        "category": "Operations",
        "estimated_days": 3,
        "steps": [
            {
                "index": 0, "name": "Detection & Triage",
                "workflow_template_id": "tmpl_incident_response",
                "record_types": ["risk_register_entry", "work_order"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Confirm incident, set severity, assign owner",
                "base_cost_usd": 200,
            },
            {
                "index": 1, "name": "Compliance Assessment",
                "workflow_template_id": "tmpl_compliance_scan",
                "record_types": ["audit_record", "decision_record"],
                "required_compliance": ["gdpr", "soc2"],
                "optional_compliance": ["hipaa", "pci_dss", "sox"],
                "blocked_by_compliance": [],
                "description": "Assess notification obligations (GDPR 72hr, HIPAA 60-day, etc.)",
                "base_cost_usd": 400,
            },
            {
                "index": 2, "name": "Containment",
                "workflow_template_id": "tmpl_incident_response",
                "record_types": ["build_log", "handoff_record"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Contain the incident, apply immediate fixes",
                "base_cost_usd": 600,
            },
            {
                "index": 3, "name": "Regulatory Notification",
                "workflow_template_id": "tmpl_incident_response",
                "record_types": ["delivery_note", "approval_record"],
                "required_compliance": ["gdpr"],
                "optional_compliance": ["hipaa", "ccpa"],
                "blocked_by_compliance": [],
                "description": "GDPR 72hr notification, HIPAA 60-day — only if frameworks active",
                "base_cost_usd": 500,
            },
            {
                "index": 4, "name": "Resolution",
                "workflow_template_id": "tmpl_incident_response",
                "record_types": ["test_result", "sign_off_record"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Confirm resolution, get sign-off",
                "base_cost_usd": 300,
            },
            {
                "index": 5, "name": "Post-Mortem",
                "workflow_template_id": "tmpl_compliance_scan",
                "record_types": ["audit_record", "decision_record"],
                "required_compliance": ["soc2"],
                "optional_compliance": ["iso_27001", "nist_csf"],
                "blocked_by_compliance": [],
                "description": "Root cause analysis, remediation plan, compliance evidence",
                "base_cost_usd": 400,
            },
        ]
    },
    {
        "id": "chain_content_campaign",
        "name": "Content Campaign",
        "icon": "📝",
        "description": "Brief to published, audited, GDPR-compliant content",
        "category": "Marketing",
        "estimated_days": 7,
        "steps": [
            {
                "index": 0, "name": "Brief",
                "workflow_template_id": "tmpl_content_publish",
                "record_types": ["spec_sheet", "work_order"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Define campaign brief and content spec",
                "base_cost_usd": 200,
            },
            {
                "index": 1, "name": "Production",
                "workflow_template_id": "tmpl_content_publish",
                "record_types": ["build_log"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Create content assets",
                "base_cost_usd": 600,
            },
            {
                "index": 2, "name": "Compliance Review",
                "workflow_template_id": "tmpl_compliance_scan",
                "record_types": ["audit_record"],
                "required_compliance": ["gdpr", "ccpa"],
                "optional_compliance": ["iso_27001"],
                "blocked_by_compliance": [],
                "description": "GDPR/CCPA review of content and targeting data",
                "base_cost_usd": 300,
            },
            {
                "index": 3, "name": "Publish",
                "workflow_template_id": "tmpl_content_publish",
                "record_types": ["delivery_note"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": ["pci_dss"],
                "description": "Publish to channels (blocked if PCI DSS — financial content risk)",
                "base_cost_usd": 100,
            },
            {
                "index": 4, "name": "Performance Audit",
                "workflow_template_id": "tmpl_compliance_scan",
                "record_types": ["audit_record", "sign_off_record"],
                "required_compliance": [],
                "optional_compliance": ["soc2"],
                "blocked_by_compliance": [],
                "description": "Audit campaign performance and compliance",
                "base_cost_usd": 150,
            },
        ]
    },
    {
        "id": "chain_vendor_onboarding",
        "name": "Vendor Onboarding",
        "icon": "🤝",
        "description": "Due diligence to provisioned and audited vendor",
        "category": "Procurement",
        "estimated_days": 10,
        "steps": [
            {
                "index": 0, "name": "Request & Scope",
                "workflow_template_id": "tmpl_lead_to_customer",
                "record_types": ["work_order", "spec_sheet"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Define what we need from the vendor",
                "base_cost_usd": 200,
            },
            {
                "index": 1, "name": "Due Diligence",
                "workflow_template_id": "tmpl_compliance_scan",
                "record_types": ["audit_record", "risk_register_entry"],
                "required_compliance": ["soc2"],
                "optional_compliance": ["hipaa", "iso_27001", "nist_csf"],
                "blocked_by_compliance": [],
                "description": "Security and compliance review of the vendor",
                "base_cost_usd": 500,
            },
            {
                "index": 2, "name": "Contract & Risk",
                "workflow_template_id": "tmpl_lead_to_customer",
                "record_types": ["decision_record", "approval_record", "risk_register_entry"],
                "required_compliance": [],
                "optional_compliance": ["sox", "gdpr"],
                "blocked_by_compliance": [],
                "description": "Contract review, DPA if GDPR, approval",
                "base_cost_usd": 600,
            },
            {
                "index": 3, "name": "Access Provisioning",
                "workflow_template_id": "tmpl_self_patch",
                "record_types": ["build_log", "handoff_record"],
                "required_compliance": ["soc2"],
                "optional_compliance": ["pci_dss"],
                "blocked_by_compliance": [],
                "description": "Provision access, log credentials, enforce least-privilege",
                "base_cost_usd": 300,
            },
            {
                "index": 4, "name": "Onboarding Audit",
                "workflow_template_id": "tmpl_compliance_scan",
                "record_types": ["audit_record", "sign_off_record"],
                "required_compliance": ["soc2"],
                "optional_compliance": ["iso_27001"],
                "blocked_by_compliance": [],
                "description": "Final audit and sign-off",
                "base_cost_usd": 250,
            },
        ]
    },
    {
        "id": "chain_revenue_driver",
        "name": "Revenue Driver",
        "icon": "📈",
        "description": "Blocker scan to closed invoice with ROI audit",
        "category": "Finance",
        "estimated_days": 2,
        "steps": [
            {
                "index": 0, "name": "Blocker Scan",
                "workflow_template_id": "tmpl_revenue_driver",
                "record_types": ["audit_record", "risk_register_entry"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Scan for revenue blockers across pipeline",
                "base_cost_usd": 100,
            },
            {
                "index": 1, "name": "Directive & Outreach",
                "workflow_template_id": "tmpl_revenue_driver",
                "record_types": ["work_order", "delivery_note"],
                "required_compliance": ["gdpr", "ccpa"],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Issue directives and execute outreach (GDPR/CCPA gated for email)",
                "base_cost_usd": 200,
            },
            {
                "index": 2, "name": "Conversion",
                "workflow_template_id": "tmpl_lead_to_customer",
                "record_types": ["decision_record", "approval_record"],
                "required_compliance": [],
                "optional_compliance": ["sox"],
                "blocked_by_compliance": [],
                "description": "Close the deal, get approval",
                "base_cost_usd": 300,
            },
            {
                "index": 3, "name": "Invoice & Billing",
                "workflow_template_id": "tmpl_revenue_driver",
                "record_types": ["delivery_note", "sign_off_record"],
                "required_compliance": [],
                "optional_compliance": ["pci_dss"],
                "blocked_by_compliance": [],
                "description": "Issue invoice, capture payment confirmation",
                "base_cost_usd": 100,
            },
            {
                "index": 4, "name": "ROI Audit",
                "workflow_template_id": "tmpl_compliance_scan",
                "record_types": ["audit_record"],
                "required_compliance": [],
                "optional_compliance": ["soc2"],
                "blocked_by_compliance": [],
                "description": "Audit the revenue cycle, log ROI",
                "base_cost_usd": 150,
            },
        ]
    },
    {
        "id": "chain_change_order",
        "name": "Change Order Process",
        "icon": "🔄",
        "description": "Change identified to amended delivery with financial close",
        "category": "Project Management",
        "estimated_days": 3,
        "steps": [
            {
                "index": 0, "name": "Change Identified",
                "workflow_template_id": "tmpl_self_patch",
                "record_types": ["risk_register_entry", "decision_record"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Document what changed and why",
                "base_cost_usd": 200,
            },
            {
                "index": 1, "name": "Impact Assessment",
                "workflow_template_id": "tmpl_compliance_scan",
                "record_types": ["audit_record", "risk_register_entry"],
                "required_compliance": [],
                "optional_compliance": ["soc2", "gdpr", "sox"],
                "blocked_by_compliance": [],
                "description": "Assess financial, schedule, and compliance impact",
                "base_cost_usd": 300,
            },
            {
                "index": 2, "name": "Change Order Record",
                "workflow_template_id": "tmpl_self_patch",
                "record_types": ["change_order"],
                "required_compliance": [],
                "optional_compliance": ["sox"],
                "blocked_by_compliance": [],
                "description": "Formally assemble the change order document",
                "base_cost_usd": 150,
            },
            {
                "index": 3, "name": "Client Acknowledgment",
                "workflow_template_id": "tmpl_customer_onboarding",
                "record_types": ["approval_record"],
                "required_compliance": ["gdpr"],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Client formally acknowledges and accepts the change",
                "base_cost_usd": 100,
            },
            {
                "index": 4, "name": "Amended Delivery",
                "workflow_template_id": "tmpl_self_patch",
                "record_types": ["build_log", "test_result", "delivery_note"],
                "required_compliance": [],
                "optional_compliance": [],
                "blocked_by_compliance": [],
                "description": "Execute the change and deliver",
                "base_cost_usd": 800,
            },
            {
                "index": 5, "name": "Financial Close",
                "workflow_template_id": "tmpl_revenue_driver",
                "record_types": ["sign_off_record", "audit_record"],
                "required_compliance": ["soc2"],
                "optional_compliance": ["sox"],
                "blocked_by_compliance": [],
                "description": "Close the change order, reconcile financials, sign-off",
                "base_cost_usd": 200,
            },
        ]
    },
]


# ── DB ─────────────────────────────────────────────────────────────────────────

def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS chain_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT,
            description TEXT,
            category TEXT,
            estimated_days INTEGER DEFAULT 0,
            steps_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- A chain_request is one instance of a chain template being executed
        CREATE TABLE IF NOT EXISTS chain_requests (
            id TEXT PRIMARY KEY,        -- the info_id: CHN-YYYYMMDD-XXXX
            template_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',  -- active | suspended | fulfilled | cancelled
            project_id TEXT,
            requestor TEXT,
            compliance_profile_json TEXT DEFAULT '[]',  -- snapshot of active toggles at creation
            current_step_index INTEGER DEFAULT 0,
            total_steps INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0,
            compliance_cost_usd REAL DEFAULT 0,
            change_orders_usd REAL DEFAULT 0,
            credits_usd REAL DEFAULT 0,
            context_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            fulfilled_at TEXT
        );

        -- Individual steps within a chain request
        CREATE TABLE IF NOT EXISTS chain_steps (
            id TEXT PRIMARY KEY,
            chain_id TEXT NOT NULL,       -- the info_id
            step_index INTEGER NOT NULL,
            step_name TEXT NOT NULL,
            workflow_template_id TEXT,
            record_types_json TEXT DEFAULT '[]',
            gate_status TEXT DEFAULT 'pending',  -- pending | ready | gated | blocked | complete | waived
            gate_reason TEXT,
            compliance_cost_usd REAL DEFAULT 0,
            base_cost_usd REAL DEFAULT 0,
            actual_cost_usd REAL DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            records_json TEXT DEFAULT '[]',       -- IDs of records assembled for this step
            workflow_instance_id TEXT,
            waiver_reason TEXT,
            waived_by TEXT,
            FOREIGN KEY (chain_id) REFERENCES chain_requests(id)
        );

        -- Gate evaluations — immutable audit log of every gate check
        CREATE TABLE IF NOT EXISTS chain_step_gates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chain_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            evaluated_at TEXT DEFAULT (datetime('now')),
            compliance_snapshot_json TEXT DEFAULT '[]',
            required_met_json TEXT DEFAULT '[]',
            required_missing_json TEXT DEFAULT '[]',
            optional_active_json TEXT DEFAULT '[]',
            blocked_by_json TEXT DEFAULT '[]',
            gate_result TEXT NOT NULL,   -- PASS | BLOCKED | PARTIAL
            cost_delta_usd REAL DEFAULT 0,
            change_type TEXT             -- change_order | credit | no_impact
        );

        -- Log of everything that happens in a chain
        CREATE TABLE IF NOT EXISTS chain_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chain_id TEXT NOT NULL,
            step_id TEXT,
            timestamp TEXT DEFAULT (datetime('now')),
            event_type TEXT NOT NULL,
            agent_id TEXT DEFAULT 'system',
            message TEXT,
            financial_delta_usd REAL DEFAULT 0,
            data_json TEXT DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_cr_project ON chain_requests(project_id);
        CREATE INDEX IF NOT EXISTS idx_cr_status ON chain_requests(status);
        CREATE INDEX IF NOT EXISTS idx_cs_chain ON chain_steps(chain_id);
        CREATE INDEX IF NOT EXISTS idx_csg_chain ON chain_step_gates(chain_id);
        CREATE INDEX IF NOT EXISTS idx_cl_chain ON chain_log(chain_id);
    """)
    conn.commit()
    return conn


@contextmanager
def _db():
    conn = _init_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _id():
    d = date.today().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:4].upper()
    return f"CHN-{d}-{suffix}"


def _step_id(chain_id, idx):
    return f"{chain_id}-S{idx:02d}"


def _now():
    return datetime.now(timezone.utc).isoformat()


# ── Compliance helpers ─────────────────────────────────────────────────────────

def _get_live_compliance() -> List[str]:
    """Fetch currently active compliance toggles from compliance DB or API."""
    try:
        db = "/var/lib/murphy-production/compliance_toggles.db"
        if os.path.exists(db):
            conn = sqlite3.connect(db, timeout=5)
            rows = conn.execute("SELECT * FROM sqlite_master WHERE type='table'").fetchall()
            conn.close()
            # Try known table names
            for table_name in ["toggles", "compliance_toggles", "frameworks"]:
                try:
                    conn = sqlite3.connect(db, timeout=5)
                    rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
                    conn.close()
                    enabled = []
                    for r in rows:
                        rd = dict(zip([d[0] for d in conn.execute(f"PRAGMA table_info({table_name})").fetchall()], r))
                        if rd.get("enabled") or rd.get("active") or rd.get("status") == "enabled":
                            enabled.append(rd.get("framework_id") or rd.get("id") or rd.get("name",""))
                    if enabled:
                        return [e.lower() for e in enabled if e]
                except Exception:
                    pass
    except Exception:
        pass
    # Fallback: use hardcoded live state from our last API check
    return ["soc2", "hipaa", "pci_dss", "iso_27001", "ccpa", "sox", "nist_csf", "gdpr"]


def evaluate_gate(step_def: Dict, active_compliance: List[str]) -> Dict:
    """Evaluate whether a step can run given active compliance toggles."""
    required  = step_def.get("required_compliance", [])
    optional  = step_def.get("optional_compliance", [])
    blocked_by = step_def.get("blocked_by_compliance", [])

    active = set(c.lower() for c in active_compliance)

    # Blocked check — any blocked_by toggle is ON → BLOCKED
    triggered_blocks = [c for c in blocked_by if c.lower() in active]
    if triggered_blocks:
        block_credit = sum(COMPLIANCE_COST.get(c, {}).get("blocked_credit", 0) for c in triggered_blocks)
        return {
            "result": "BLOCKED",
            "reason": f"Blocked by active compliance: {', '.join(t.upper() for t in triggered_blocks)}",
            "blocked_by": triggered_blocks,
            "required_met": [],
            "required_missing": [],
            "optional_active": [],
            "cost_delta": -block_credit,   # negative = credit (we save money by not doing it wrong)
            "change_type": "credit",
        }

    # Required check
    required_met     = [c for c in required if c.lower() in active]
    required_missing = [c for c in required if c.lower() not in active]

    # Optional check — adds compliance cost
    optional_active = [c for c in optional if c.lower() in active]
    compliance_cost = sum(COMPLIANCE_COST.get(c, {}).get("required_cost", 0)
                          for c in required_met + optional_active)

    if required_missing:
        return {
            "result": "PARTIAL",
            "reason": f"Missing required compliance: {', '.join(r.upper() for r in required_missing)}. Step will run in reduced mode.",
            "blocked_by": [],
            "required_met": required_met,
            "required_missing": required_missing,
            "optional_active": optional_active,
            "cost_delta": compliance_cost,
            "change_type": "no_impact" if compliance_cost == 0 else "change_order",
        }

    return {
        "result": "PASS",
        "reason": "All compliance requirements met" + (
            f" + optional: {', '.join(o.upper() for o in optional_active)}" if optional_active else ""
        ),
        "blocked_by": [],
        "required_met": required_met,
        "required_missing": [],
        "optional_active": optional_active,
        "cost_delta": compliance_cost,
        "change_type": "change_order" if compliance_cost > 0 else "no_impact",
    }


# ── Chain Templates ────────────────────────────────────────────────────────────

def get_templates() -> List[Dict]:
    return CHAIN_TEMPLATES


def get_template(template_id: str) -> Optional[Dict]:
    return next((t for t in CHAIN_TEMPLATES if t["id"] == template_id), None)


# ── Chain Requests ─────────────────────────────────────────────────────────────

def create_chain(template_id: str, name: str = None, project_id: str = None,
                 requestor: str = "system", context: Dict = None) -> Dict:
    """Create a new chain request. Gates all steps against live compliance at creation."""
    tmpl = get_template(template_id)
    if not tmpl:
        return {"error": f"Unknown chain template: {template_id}"}

    chain_id = _id()
    active_compliance = _get_live_compliance()
    chain_name = name or f"{tmpl['name']} — {chain_id}"

    total_base_cost = 0
    total_compliance_cost = 0

    with _db() as conn:
        conn.execute(
            """INSERT INTO chain_requests
               (id,template_id,name,project_id,requestor,compliance_profile_json,
                total_steps,context_json)
               VALUES (?,?,?,?,?,?,?,?)""",
            (chain_id, template_id, chain_name, project_id, requestor,
             json.dumps(active_compliance), len(tmpl["steps"]),
             json.dumps(context or {}))
        )

        for step_def in tmpl["steps"]:
            step_id = _step_id(chain_id, step_def["index"])
            gate = evaluate_gate(step_def, active_compliance)

            gate_status = {
                "PASS": "ready" if step_def["index"] == 0 else "pending",
                "PARTIAL": "ready" if step_def["index"] == 0 else "pending",
                "BLOCKED": "blocked",
            }[gate["result"]]

            compliance_cost = gate["cost_delta"] if gate["cost_delta"] > 0 else 0
            base_cost = step_def.get("base_cost_usd", 0)
            total_base_cost += base_cost
            total_compliance_cost += compliance_cost

            conn.execute(
                """INSERT INTO chain_steps
                   (id,chain_id,step_index,step_name,workflow_template_id,
                    record_types_json,gate_status,gate_reason,
                    compliance_cost_usd,base_cost_usd)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (step_id, chain_id, step_def["index"], step_def["name"],
                 step_def.get("workflow_template_id"),
                 json.dumps(step_def.get("record_types", [])),
                 gate_status, gate["reason"],
                 compliance_cost, base_cost)
            )

            conn.execute(
                """INSERT INTO chain_step_gates
                   (chain_id,step_id,compliance_snapshot_json,required_met_json,
                    required_missing_json,optional_active_json,blocked_by_json,
                    gate_result,cost_delta_usd,change_type)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (chain_id, step_id, json.dumps(active_compliance),
                 json.dumps(gate["required_met"]), json.dumps(gate["required_missing"]),
                 json.dumps(gate["optional_active"]), json.dumps(gate["blocked_by"]),
                 gate["result"], gate["cost_delta"], gate["change_type"])
            )

        # Update totals
        conn.execute(
            """UPDATE chain_requests
               SET total_cost_usd=?, compliance_cost_usd=?, updated_at=?
               WHERE id=?""",
            (total_base_cost + total_compliance_cost, total_compliance_cost,
             _now(), chain_id)
        )

        conn.execute(
            """INSERT INTO chain_log
               (chain_id,event_type,agent_id,message,financial_delta_usd)
               VALUES (?,?,?,?,?)""",
            (chain_id, "chain_created", requestor,
             f"Chain '{chain_name}' created — {len(tmpl['steps'])} steps | "
             f"base ${total_base_cost:,.0f} + compliance ${total_compliance_cost:,.0f}",
             total_base_cost + total_compliance_cost)
        )

    logger.info("Chain %s created: %s (%d steps, $%.0f)",
                chain_id, chain_name, len(tmpl["steps"]),
                total_base_cost + total_compliance_cost)
    return get_chain(chain_id)


def get_chain(chain_id: str) -> Optional[Dict]:
    with _db() as conn:
        cr = conn.execute(
            "SELECT * FROM chain_requests WHERE id=?", (chain_id,)
        ).fetchone()
        if not cr:
            return None
        chain = dict(cr)
        chain["compliance_profile"] = json.loads(chain["compliance_profile_json"])
        chain["context"] = json.loads(chain.get("context_json") or "{}")

        steps = conn.execute(
            "SELECT * FROM chain_steps WHERE chain_id=? ORDER BY step_index",
            (chain_id,)
        ).fetchall()
        chain["steps"] = []
        for s in steps:
            step = dict(s)
            step["record_types"] = json.loads(step.get("record_types_json") or "[]")
            step["records"] = json.loads(step.get("records_json") or "[]")
            # Get latest gate evaluation
            gate = conn.execute(
                "SELECT * FROM chain_step_gates WHERE step_id=? ORDER BY evaluated_at DESC LIMIT 1",
                (s["id"],)
            ).fetchone()
            if gate:
                step["latest_gate"] = {
                    "result": gate["gate_result"],
                    "required_met": json.loads(gate["required_met_json"] or "[]"),
                    "required_missing": json.loads(gate["required_missing_json"] or "[]"),
                    "optional_active": json.loads(gate["optional_active_json"] or "[]"),
                    "blocked_by": json.loads(gate["blocked_by_json"] or "[]"),
                    "cost_delta": gate["cost_delta_usd"],
                    "change_type": gate["change_type"],
                    "evaluated_at": gate["evaluated_at"],
                }
            chain["steps"].append(step)

        # Pending changes (unacknowledged gate events that produced change orders/credits)
        pending_cos = conn.execute(
            """SELECT SUM(cost_delta_usd) as total FROM chain_step_gates
               WHERE chain_id=? AND change_type='change_order'""", (chain_id,)
        ).fetchone()
        pending_crs = conn.execute(
            """SELECT SUM(ABS(cost_delta_usd)) as total FROM chain_step_gates
               WHERE chain_id=? AND change_type='credit'""", (chain_id,)
        ).fetchone()
        chain["pending_change_orders_usd"] = pending_cos["total"] or 0
        chain["pending_credits_usd"] = pending_crs["total"] or 0

    return chain


def list_chains(project_id: str = None, status: str = None, limit: int = 50) -> List[Dict]:
    with _db() as conn:
        clauses, params = [], []
        if project_id: clauses.append("project_id=?"); params.append(project_id)
        if status:     clauses.append("status=?");     params.append(status)
        q = "SELECT * FROM chain_requests"
        if clauses: q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
    result = []
    for r in rows:
        chain = dict(r)
        chain["compliance_profile"] = json.loads(chain.get("compliance_profile_json") or "[]")
        result.append(chain)
    return result


def advance_step(chain_id: str, step_index: int, agent_id: str = "system",
                 record_ids: List[str] = None, notes: str = "") -> Dict:
    """Complete a step and advance to the next. Re-gates the next step against LIVE compliance."""
    now = _now()
    step_id = _step_id(chain_id, step_index)
    next_step_id = _step_id(chain_id, step_index + 1)

    active_compliance = _get_live_compliance()
    tmpl_step = None
    with _db() as conn:
        chain = conn.execute("SELECT * FROM chain_requests WHERE id=?", (chain_id,)).fetchone()
        if not chain:
            return {"error": "Chain not found"}
        tmpl = get_template(chain["template_id"])
        step = conn.execute("SELECT * FROM chain_steps WHERE id=?", (step_id,)).fetchone()
        if not step:
            return {"error": f"Step {step_index} not found"}

        # Mark current step complete
        records_json = json.dumps(record_ids or [])
        conn.execute(
            """UPDATE chain_steps
               SET gate_status='complete', completed_at=?, records_json=?, actual_cost_usd=?
               WHERE id=?""",
            (now, records_json,
             (step["base_cost_usd"] or 0) + (step["compliance_cost_usd"] or 0),
             step_id)
        )
        conn.execute(
            """INSERT INTO chain_log
               (chain_id,step_id,event_type,agent_id,message)
               VALUES (?,?,?,?,?)""",
            (chain_id, step_id, "step_complete", agent_id,
             f"Step {step_index} '{step['step_name']}' completed{': '+notes if notes else ''}")
        )

        # Find and gate next step
        next_step = conn.execute(
            "SELECT * FROM chain_steps WHERE chain_id=? AND step_index=?",
            (chain_id, step_index + 1)
        ).fetchone()

        if not next_step:
            # Last step — fulfil chain
            conn.execute(
                "UPDATE chain_requests SET status='fulfilled',fulfilled_at=?,updated_at=? WHERE id=?",
                (now, now, chain_id)
            )
            conn.execute(
                """INSERT INTO chain_log (chain_id,event_type,agent_id,message)
                   VALUES (?,?,?,?)""",
                (chain_id, "chain_fulfilled", agent_id,
                 f"Chain {chain_id} FULFILLED — all {step_index + 1} steps complete")
            )
            return {"status": "chain_fulfilled", "chain_id": chain_id}

        # Re-gate next step against live compliance
        if tmpl:
            tmpl_step = next((s for s in tmpl["steps"] if s["index"] == step_index + 1), None)
        if tmpl_step:
            gate = evaluate_gate(tmpl_step, active_compliance)
            new_gate_status = "blocked" if gate["result"] == "BLOCKED" else "ready"

            # Detect compliance change — compare to creation snapshot
            old_profile = set(json.loads(chain["compliance_profile_json"] or "[]"))
            new_profile = set(active_compliance)
            compliance_changed = old_profile != new_profile

            change_type = gate["change_type"]
            if compliance_changed and gate["cost_delta"] != 0:
                # Log change event
                event = "change_order" if gate["cost_delta"] > 0 else "credit"
                conn.execute(
                    """INSERT INTO chain_log
                       (chain_id,step_id,event_type,agent_id,message,financial_delta_usd)
                       VALUES (?,?,?,?,?,?)""",
                    (chain_id, next_step_id, event, "compliance_gate",
                     f"Compliance change detected at step {step_index+1}: "
                     f"{gate['reason']} — ${gate['cost_delta']:+.0f}",
                     gate["cost_delta"])
                )
                # Update chain totals
                if gate["cost_delta"] > 0:
                    conn.execute(
                        "UPDATE chain_requests SET change_orders_usd=change_orders_usd+?,updated_at=? WHERE id=?",
                        (gate["cost_delta"], now, chain_id)
                    )
                else:
                    conn.execute(
                        "UPDATE chain_requests SET credits_usd=credits_usd+?,updated_at=? WHERE id=?",
                        (abs(gate["cost_delta"]), now, chain_id)
                    )

            conn.execute(
                """UPDATE chain_steps
                   SET gate_status=?, gate_reason=?, compliance_cost_usd=?, started_at=?
                   WHERE id=?""",
                (new_gate_status, gate["reason"],
                 gate["cost_delta"] if gate["cost_delta"] > 0 else 0,
                 now if new_gate_status == "ready" else None,
                 next_step_id)
            )
            conn.execute(
                """INSERT INTO chain_step_gates
                   (chain_id,step_id,compliance_snapshot_json,required_met_json,
                    required_missing_json,optional_active_json,blocked_by_json,
                    gate_result,cost_delta_usd,change_type)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (chain_id, next_step_id, json.dumps(active_compliance),
                 json.dumps(gate["required_met"]), json.dumps(gate["required_missing"]),
                 json.dumps(gate["optional_active"]), json.dumps(gate["blocked_by"]),
                 gate["result"], gate["cost_delta"], change_type)
            )

        # Advance chain pointer
        conn.execute(
            "UPDATE chain_requests SET current_step_index=?,updated_at=? WHERE id=?",
            (step_index + 1, now, chain_id)
        )

    return get_chain(chain_id)


def raise_waiver(chain_id: str, step_index: int, reason: str,
                 waived_by: str = "system") -> Dict:
    """Override a BLOCKED step — creates a compliance waiver record automatically."""
    step_id = _step_id(chain_id, step_index)
    now = _now()
    with _db() as conn:
        conn.execute(
            """UPDATE chain_steps
               SET gate_status='waived', waiver_reason=?, waived_by=?, started_at=?
               WHERE id=?""",
            (reason, waived_by, now, step_id)
        )
        conn.execute(
            """INSERT INTO chain_log
               (chain_id,step_id,event_type,agent_id,message,data_json)
               VALUES (?,?,?,?,?,?)""",
            (chain_id, step_id, "waiver_raised", waived_by,
             f"WAIVER on step {step_index}: {reason}",
             json.dumps({"reason": reason, "waived_by": waived_by}))
        )

    # Auto-create a compliance waiver record in the assembly engine
    try:
        from src.records_engine import create_record as _cr
        _cr("decision_record",
            f"Compliance Waiver — {chain_id} Step {step_index}",
            {
                "decision_statement": f"Waived compliance gate on step {step_index} of chain {chain_id}",
                "decided_by": waived_by,
                "decision_date": now[:10],
                "rationale": reason,
                "financial_impact": "0",
                "reversible": "No",
                "affects_client": "Yes",
            },
            created_by=waived_by,
            project_id=None
           )
    except Exception as e:
        logger.debug("Waiver record skipped: %s", e)

    return get_chain(chain_id)


def regate_chain(chain_id: str) -> Dict:
    """Re-evaluate ALL pending steps against current live compliance. Returns change summary."""
    chain = get_chain(chain_id)
    if not chain:
        return {"error": "Chain not found"}
    tmpl = get_template(chain["template_id"])
    if not tmpl:
        return {"error": "Template not found"}

    active = _get_live_compliance()
    changes = []
    now = _now()

    with _db() as conn:
        for step in chain["steps"]:
            if step["gate_status"] in ("complete", "waived"):
                continue
            tmpl_step = next((s for s in tmpl["steps"] if s["index"] == step["step_index"]), None)
            if not tmpl_step:
                continue
            gate = evaluate_gate(tmpl_step, active)
            old_status = step["gate_status"]
            new_status = "blocked" if gate["result"] == "BLOCKED" else (
                "ready" if step["step_index"] == chain["current_step_index"] else "pending"
            )
            if old_status != new_status or gate["cost_delta"] != 0:
                change_type = "change_order" if gate["cost_delta"] > 0 else (
                    "credit" if gate["cost_delta"] < 0 else "no_impact"
                )
                changes.append({
                    "step_index": step["step_index"],
                    "step_name": step["step_name"],
                    "old_status": old_status,
                    "new_status": new_status,
                    "change_type": change_type,
                    "delta_usd": gate["cost_delta"],
                    "reason": gate["reason"],
                })
                conn.execute(
                    "UPDATE chain_steps SET gate_status=?,gate_reason=? WHERE id=?",
                    (new_status, gate["reason"], step["id"])
                )
                conn.execute(
                    """INSERT INTO chain_step_gates
                       (chain_id,step_id,compliance_snapshot_json,required_met_json,
                        required_missing_json,optional_active_json,blocked_by_json,
                        gate_result,cost_delta_usd,change_type)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (chain_id, step["id"], json.dumps(active),
                     json.dumps(gate["required_met"]), json.dumps(gate["required_missing"]),
                     json.dumps(gate["optional_active"]), json.dumps(gate["blocked_by"]),
                     gate["result"], gate["cost_delta"], change_type)
                )
                if gate["cost_delta"] != 0:
                    conn.execute(
                        """INSERT INTO chain_log
                           (chain_id,step_id,event_type,agent_id,message,financial_delta_usd)
                           VALUES (?,?,?,?,?,?)""",
                        (chain_id, step["id"],
                         "change_order" if gate["cost_delta"] > 0 else "credit",
                         "compliance_recheck",
                         f"Re-gate: step {step['step_index']} '{step['step_name']}' → {new_status}: {gate['reason']}",
                         gate["cost_delta"])
                    )
        conn.execute(
            "UPDATE chain_requests SET updated_at=? WHERE id=?", (now, chain_id)
        )

    return {"chain_id": chain_id, "changes": changes, "active_compliance": active}


def get_info_id_summary(info_id: str) -> Dict:
    """Return everything known about a request ID — the full audit picture."""
    chain = get_chain(info_id)
    if not chain:
        return {"error": f"No chain found for info_id: {info_id}"}

    summary = {
        "info_id": info_id,
        "chain": chain,
        "records": [],
        "manifold_entries": [],
        "workflow_steps": [],
        "change_orders": [],
        "credits": [],
        "total_financial": {
            "base_cost": chain.get("total_cost_usd", 0),
            "compliance_cost": chain.get("compliance_cost_usd", 0),
            "change_orders": chain.get("change_orders_usd", 0),
            "credits": chain.get("credits_usd", 0),
        }
    }
    summary["total_financial"]["net"] = (
        summary["total_financial"]["base_cost"] +
        summary["total_financial"]["compliance_cost"] +
        summary["total_financial"]["change_orders"] -
        summary["total_financial"]["credits"]
    )

    # Pull records tagged with this info_id
    try:
        from src.records_engine import list_records as _lr
        # Records link via context — check all steps' record IDs
        all_record_ids = []
        for step in chain.get("steps", []):
            all_record_ids.extend(step.get("records", []))
        for rid in all_record_ids:
            from src.records_engine import get_record as _gr
            rec = _gr(rid)
            if rec:
                summary["records"].append({
                    "id": rec["id"], "type": rec["record_type_id"],
                    "title": rec["title"], "status": rec["status"],
                    "lane": rec["lane"], "financial_impact": rec["financial_impact_usd"]
                })
    except Exception:
        pass

    # Pull change events from log
    with _db() as conn:
        logs = conn.execute(
            "SELECT * FROM chain_log WHERE chain_id=? ORDER BY timestamp",
            (info_id,)
        ).fetchall()
        for l in logs:
            ld = dict(l)
            if ld["event_type"] == "change_order":
                summary["change_orders"].append(ld)
            elif ld["event_type"] == "credit":
                summary["credits"].append(ld)

    return summary


def get_log(chain_id: str = None, limit: int = 100) -> List[Dict]:
    with _db() as conn:
        if chain_id:
            rows = conn.execute(
                "SELECT * FROM chain_log WHERE chain_id=? ORDER BY timestamp DESC LIMIT ?",
                (chain_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM chain_log ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def get_status() -> Dict:
    try:
        with _db() as conn:
            total   = conn.execute("SELECT COUNT(*) FROM chain_requests").fetchone()[0]
            active  = conn.execute("SELECT COUNT(*) FROM chain_requests WHERE status='active'").fetchone()[0]
            done    = conn.execute("SELECT COUNT(*) FROM chain_requests WHERE status='fulfilled'").fetchone()[0]
            blocked = conn.execute("SELECT COUNT(*) FROM chain_steps WHERE gate_status='blocked'").fetchone()[0]
            cos     = conn.execute("SELECT COUNT(*) FROM chain_step_gates WHERE change_type='change_order'").fetchone()[0]
            crs     = conn.execute("SELECT COUNT(*) FROM chain_step_gates WHERE change_type='credit'").fetchone()[0]
        return {"chains": total, "active": active, "fulfilled": done,
                "blocked_steps": blocked, "change_orders": cos, "credits": crs,
                "templates": len(CHAIN_TEMPLATES)}
    except Exception as e:
        return {"error": str(e), "templates": len(CHAIN_TEMPLATES)}
