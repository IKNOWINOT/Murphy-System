"""
CRM Manager — SQLite-backed persistent implementation.
PATCH-158: Replaces in-memory stub with persistent SQLite backend.
"""
from __future__ import annotations
import sqlite3, uuid, json, logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from .models import Contact, ContactType, Deal, DealStage, Pipeline, Stage, CRMActivity, ActivityType, _now, _new_id

logger = logging.getLogger(__name__)
_UTC = timezone.utc
_DB_PATH = "/var/lib/murphy-production/crm.db"


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(_DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT, company TEXT,
        contact_type TEXT DEFAULT 'lead', owner_id TEXT DEFAULT '',
        tags TEXT DEFAULT '[]', custom_fields TEXT DEFAULT '{}', created_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS deals (
        id TEXT PRIMARY KEY, title TEXT, contact_id TEXT DEFAULT '',
        pipeline_id TEXT DEFAULT '', stage TEXT DEFAULT 'lead',
        value REAL DEFAULT 0, currency TEXT DEFAULT 'USD',
        owner_id TEXT DEFAULT '', expected_close_date TEXT DEFAULT '',
        notes TEXT DEFAULT '', created_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS pipelines (
        id TEXT PRIMARY KEY, name TEXT, stages TEXT DEFAULT '[]', created_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS activities (
        id TEXT PRIMARY KEY, activity_type TEXT, contact_id TEXT DEFAULT '',
        deal_id TEXT DEFAULT '', user_id TEXT DEFAULT '',
        summary TEXT DEFAULT '', details TEXT DEFAULT '', created_at TEXT)""")
    db.commit()
    return db


def _seed():
    db = _db()
    if db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] > 0:
        db.close(); return
    now = _now()
    contacts = [
        (_new_id(), "Aria Chen",    "aria@techcorp.io",  "+1-415-555-0101", "TechCorp",  "customer", "founder", '["enterprise","saas"]', '{}', now),
        (_new_id(), "Marcus Webb",  "marcus@growthco.io","+1-212-555-0102", "GrowthCo",  "lead",     "founder", '["smb"]',               '{}', now),
        (_new_id(), "Priya Sharma", "priya@finova.io",   "+1-650-555-0103", "Finova",    "customer", "founder", '["fintech"]',            '{}', now),
        (_new_id(), "Jordan Blake", "jordan@nexgen.io",  "+1-310-555-0104", "NexGen AI", "lead",     "founder", '["ai","enterprise"]',    '{}', now),
        (_new_id(), "Sam Rivera",   "sam@startupx.io",   "+1-408-555-0105", "StartupX",  "partner",  "founder", '["startup"]',            '{}', now),
    ]
    for row in contacts:
        db.execute("INSERT INTO contacts VALUES (?,?,?,?,?,?,?,?,?,?)", row)
    # Default pipeline
    pid = _new_id()
    stages = json.dumps([
        {"id":"s1","name":"Lead","probability":10},
        {"id":"s2","name":"Qualified","probability":30},
        {"id":"s3","name":"Proposal","probability":60},
        {"id":"s4","name":"Negotiation","probability":80},
        {"id":"s5","name":"Closed Won","probability":100},
    ])
    db.execute("INSERT INTO pipelines VALUES (?,?,?,?)", (pid, "Sales Pipeline", stages, now))
    db.commit(); db.close()


class CRMManager:
    def __init__(self): _seed()

    def _row_to_contact(self, r) -> Contact:
        ct = ContactType(r["contact_type"]) if r["contact_type"] in [e.value for e in ContactType] else ContactType.LEAD
        c = Contact(id=r["id"], name=r["name"], email=r["email"], phone=r["phone"],
                    company=r["company"], contact_type=ct, owner_id=r["owner_id"] or "",
                    tags=json.loads(r["tags"] or "[]"),
                    custom_fields=json.loads(r["custom_fields"] or "{}"),
                    created_at=r["created_at"])
        return c

    def _row_to_deal(self, r) -> Deal:
        stage = r["stage"] if r["stage"] else "lead"
        return Deal(id=r["id"], title=r["title"], contact_id=r["contact_id"] or "",
                    pipeline_id=r["pipeline_id"] or "", stage=stage,
                    value=float(r["value"] or 0), currency=r["currency"] or "USD",
                    owner_id=r["owner_id"] or "", expected_close_date=r["expected_close_date"] or "",
                    created_at=r["created_at"])

    def create_contact(self, name, *, email="", phone="", company="",
                       contact_type=ContactType.LEAD, owner_id="", tags=None) -> Contact:
        db = _db(); now = _now()
        ct = contact_type if isinstance(contact_type, ContactType) else ContactType(contact_type)
        c = Contact(name=name, email=email, phone=phone, company=company,
                    contact_type=ct, owner_id=owner_id, tags=tags or [], created_at=now)
        db.execute("INSERT INTO contacts VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (c.id, c.name, c.email, c.phone, c.company, c.contact_type.value,
                    c.owner_id, json.dumps(c.tags), json.dumps(c.custom_fields), c.created_at))
        db.commit(); db.close(); return c

    def list_contacts(self, *, contact_type=None, owner_id=None, search=None) -> List[Contact]:
        db = _db(); q = "SELECT * FROM contacts WHERE 1=1"; params = []
        if contact_type: q += " AND contact_type=?"; params.append(str(contact_type.value if hasattr(contact_type, 'value') else contact_type))
        if owner_id: q += " AND owner_id=?"; params.append(owner_id)
        if search: q += " AND (name LIKE ? OR email LIKE ? OR company LIKE ?)"; params += [f"%{search}%"]*3
        q += " ORDER BY created_at DESC"
        rows = db.execute(q, params).fetchall(); db.close()
        return [self._row_to_contact(r) for r in rows]

    def get_contact(self, contact_id: str) -> Optional[Contact]:
        db = _db(); r = db.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone(); db.close()
        return self._row_to_contact(r) if r else None

    def update_contact(self, contact_id: str, **kwargs) -> Optional[Contact]:
        db = _db(); fields = []; vals = []
        for k, v in kwargs.items():
            if k == "tags": fields.append("tags=?"); vals.append(json.dumps(v if isinstance(v, list) else []))
            elif k in ("name","email","phone","company","owner_id"): fields.append(f"{k}=?"); vals.append(str(v))
            elif k == "contact_type": fields.append("contact_type=?"); vals.append(v.value if hasattr(v,"value") else str(v))
        if fields:
            vals.append(contact_id)
            db.execute(f"UPDATE contacts SET {', '.join(fields)} WHERE id=?", vals)
            db.commit()
        db.close(); return self.get_contact(contact_id)

    def delete_contact(self, contact_id: str) -> bool:
        db = _db(); db.execute("DELETE FROM contacts WHERE id=?", (contact_id,)); db.commit(); db.close(); return True

    def create_pipeline(self, name: str, stages=None) -> Pipeline:
        db = _db(); now = _now()
        default_stages = stages or [
            Stage(name="Lead"), Stage(name="Qualified"), Stage(name="Proposal"),
            Stage(name="Closed Won"), Stage(name="Closed Lost"),
        ]
        p = Pipeline(name=name, stages=default_stages, created_at=now)
        db.execute("INSERT INTO pipelines VALUES (?,?,?,?)",
                   (p.id, p.name, json.dumps([s.to_dict() if hasattr(s,"to_dict") else {"id":s.id,"name":s.name,"probability":s.probability} for s in p.stages]), p.created_at))
        db.commit(); db.close(); return p

    def list_pipelines(self) -> List[Pipeline]:
        db = _db(); rows = db.execute("SELECT * FROM pipelines ORDER BY created_at").fetchall(); db.close()
        result = []
        for r in rows:
            p = Pipeline(id=r["id"], name=r["name"], created_at=r["created_at"])
            try: p.stages = [Stage(**s) for s in json.loads(r["stages"] or "[]")]
            except: p.stages = []
            result.append(p)
        return result

    def get_pipeline(self, pipeline_id: str) -> Optional[Pipeline]:
        db = _db(); r = db.execute("SELECT * FROM pipelines WHERE id=?", (pipeline_id,)).fetchone(); db.close()
        if not r: return None
        p = Pipeline(id=r["id"], name=r["name"], created_at=r["created_at"])
        try: p.stages = [Stage(**s) for s in json.loads(r["stages"] or "[]")]
        except: p.stages = []
        return p

    def create_deal(self, title, *, contact_id="", pipeline_id="", stage=DealStage.LEAD,
                    value=0.0, currency="USD", owner_id="", expected_close_date="") -> Deal:
        db = _db(); now = _now()
        st = stage if isinstance(stage, DealStage) else DealStage(stage)
        d = Deal(title=title, contact_id=contact_id, pipeline_id=pipeline_id, stage=st,
                 value=value, currency=currency, owner_id=owner_id,
                 expected_close_date=expected_close_date, created_at=now)
        db.execute("INSERT INTO deals VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (d.id, d.title, d.contact_id, d.pipeline_id, d.stage.value,
                    d.value, d.currency, d.owner_id, d.expected_close_date, "", d.created_at))
        db.commit(); db.close(); return d

    def list_deals(self, *, pipeline_id=None, stage=None, contact_id=None, owner_id=None) -> List[Deal]:
        db = _db(); q = "SELECT * FROM deals WHERE 1=1"; params = []
        if pipeline_id: q += " AND pipeline_id=?"; params.append(pipeline_id)
        if stage: q += " AND stage=?"; params.append(stage.value if hasattr(stage,"value") else str(stage))
        if contact_id: q += " AND contact_id=?"; params.append(contact_id)
        q += " ORDER BY created_at DESC"
        rows = db.execute(q, params).fetchall(); db.close()
        return [self._row_to_deal(r) for r in rows]

    def get_deal(self, deal_id: str) -> Optional[Deal]:
        db = _db(); r = db.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone(); db.close()
        return self._row_to_deal(r) if r else None

    def update_deal(self, deal_id: str, **kwargs) -> Optional[Deal]:
        db = _db(); fields = []; vals = []
        for k, v in kwargs.items():
            if k == "stage": fields.append("stage=?"); vals.append(v.value if hasattr(v,"value") else str(v))
            elif k in ("title","currency","owner_id","expected_close_date"): fields.append(f"{k}=?"); vals.append(str(v))
            elif k == "value": fields.append("value=?"); vals.append(float(v))
        if fields:
            vals.append(deal_id)
            db.execute(f"UPDATE deals SET {', '.join(fields)} WHERE id=?", vals)
            db.commit()
        db.close(); return self.get_deal(deal_id)

    def move_deal(self, deal_id: str, stage) -> Optional[Deal]:
        return self.update_deal(deal_id, stage=stage)

    def delete_deal(self, deal_id: str) -> bool:
        db = _db(); db.execute("DELETE FROM deals WHERE id=?", (deal_id,)); db.commit(); db.close(); return True

    def pipeline_value(self, pipeline_id: str) -> Dict[str, Any]:
        deals = self.list_deals(pipeline_id=pipeline_id)
        total = sum(d.value for d in deals)
        by_stage = {}
        for d in deals:
            by_stage[d.stage.value] = by_stage.get(d.stage.value, 0) + d.value
        return {"pipeline_id": pipeline_id, "total_value": total, "by_stage": by_stage, "deal_count": len(deals)}

    def log_activity(self, activity_type, *, contact_id="", deal_id="",
                     user_id="", summary="", details="") -> CRMActivity:
        db = _db(); now = _now()
        at = activity_type if isinstance(activity_type, ActivityType) else ActivityType(activity_type)
        a = CRMActivity(activity_type=at, contact_id=contact_id, deal_id=deal_id,
                        user_id=user_id, summary=summary, details=details, created_at=now)
        db.execute("INSERT INTO activities VALUES (?,?,?,?,?,?,?,?)",
                   (a.id, a.activity_type.value, a.contact_id, a.deal_id, a.user_id, a.summary, a.details, a.created_at))
        db.commit(); db.close(); return a

    def list_activities(self, *, contact_id=None, deal_id=None, limit=50) -> List[CRMActivity]:
        db = _db(); q = "SELECT * FROM activities WHERE 1=1"; params = []
        if contact_id: q += " AND contact_id=?"; params.append(contact_id)
        if deal_id: q += " AND deal_id=?"; params.append(deal_id)
        q += f" ORDER BY created_at DESC LIMIT {int(limit)}"
        rows = db.execute(q, params).fetchall(); db.close()
        result = []
        for r in rows:
            at = ActivityType(r["activity_type"]) if r["activity_type"] in [e.value for e in ActivityType] else ActivityType.NOTE
            result.append(CRMActivity(id=r["id"], activity_type=at, contact_id=r["contact_id"],
                                      deal_id=r["deal_id"], user_id=r["user_id"],
                                      summary=r["summary"], details=r["details"], created_at=r["created_at"]))
        return result

    def crm_summary(self) -> Dict[str, Any]:
        db = _db()
        total_contacts = db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        total_deals = db.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
        won = db.execute("SELECT COUNT(*) FROM deals WHERE stage='closed_won'").fetchone()[0]
        total_val = db.execute("SELECT SUM(value) FROM deals").fetchone()[0] or 0
        db.close()
        return {"total_contacts": total_contacts, "total_deals": total_deals,
                "deals_won": won, "pipeline_value": total_val}
