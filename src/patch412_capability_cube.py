"""
PATCH-412 — CapabilityCube
==========================

WHAT THIS IS:
  A 6-axis semantic addressing scheme for Murphy capability modules.
  Every module is a point in cube-space defined by its (accepts, produces,
  domain, risk_class, trust_tier, soul_fit) coordinates.

  Rosetta dispatch "rotates the cube" — picks one or more faces to
  filter on — and gets back the candidate modules that match. This
  replaces the static domain → agent dict.

WHY IT EXISTS:
  Gap 1 from the autonomy audit (May 24, 2026). Today Rosetta picks
  agents from a hardcoded dict in rosetta_core.py:455-466. Adding a
  new capability means editing rosetta_core. There's no discovery,
  no soul-fit reasoning, no risk gating.

  After PATCH-412:
  - Modules declare a CapabilityManifest at registration
  - Rosetta queries the cube for "modules that accept X, produce Y,
    in domain Z, with risk ≤ R, trust ≥ T, soul-fit S"
  - HITL gate enforces founder-approval for high-risk dispatches
  - New modules become available the moment they register — zero
    rosetta_core changes

HOW IT FITS:
  - Lives in murphy-ops (it's a control-plane concern, not core logic)
  - Wraps module_registry.register() — modules opt-in by providing a
    `capability=CapabilityManifest(...)` kwarg
  - Exposes /api/cube/* endpoints
  - SwarmCoordinator.dispatch() consults the cube via cube.find()

THE 6 FACES (Rubik's cube metaphor):
  U  (Up)    : accepts      — input shapes  (text, image, telemetry…)
  D  (Down)  : produces     — output shapes (report, command, plan…)
  F  (Front) : domain       — sales/ops/finance/robotics/security/ux/…
  B  (Back)  : risk_class   — green/yellow/red
  L  (Left)  : trust_tier   — builtin/signed/community/unknown
  R  (Right) : soul_fit     — agent soul affinity

ENDPOINTS / PUBLIC SURFACE:
  GET   /api/cube/list                  — all registered capabilities
  GET   /api/cube/find?{face}={value}   — rotate + filter
  GET   /api/cube/address/{name}        — one module's 6-tuple
  POST  /api/cube/dispatch              — semantic dispatch
                                          body: {accepts, produces, domain,
                                                 max_risk, min_trust, prefer_soul}
                                          returns: ranked candidate list

DEPENDENCIES:
  - module_registry (PATCH-OPT-2) — modules live there, we enrich them
  - causality_sandbox (optional) — dispatches with risk>green get a
    sandbox simulation before HITL approval

KEY DESIGN: This is metadata-only. The cube doesn't EXECUTE modules,
it only ADDRESSES them. Module execution still goes through whatever
service hosts the module (edge/core/ops/robotics).

LAST UPDATED: 2026-05-24 by Murphy (PATCH-412)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Any, Tuple
from enum import Enum
from pydantic import BaseModel

log = logging.getLogger("murphy.capability_cube")


# ── The six axis enums ──────────────────────────────────────────────────────

class Accepts(str, Enum):
    """What input shapes a capability consumes."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    CODE = "code"
    STRUCTURED_DATA = "structured_data"
    ROBOT_TELEMETRY = "robot_telemetry"
    USER_INTENT = "user_intent"
    SYSTEM_EVENT = "system_event"
    HTTP_REQUEST = "http_request"
    ANY = "any"  # universal accept (use sparingly)


class Produces(str, Enum):
    """What output shapes a capability emits."""
    REPORT = "report"
    COMMAND = "command"
    PLAN = "plan"
    AUDIT_EVENT = "audit_event"
    NOTIFICATION = "notification"
    DATA_RECORD = "data_record"
    HTTP_RESPONSE = "http_response"
    SIDE_EFFECT = "side_effect"
    ROBOT_ACTION = "robot_action"
    NOTHING = "nothing"


class Domain(str, Enum):
    """Business domain a capability serves."""
    SALES = "sales"
    OPERATIONS = "operations"
    FINANCE = "finance"
    ROBOTICS = "robotics"
    SECURITY = "security"
    UX = "ux"
    IDENTITY = "identity"
    OBSERVABILITY = "observability"
    PLATFORM = "platform"
    HOUSEHOLD = "household"
    UNKNOWN = "unknown"


class RiskClass(str, Enum):
    """Severity of side effects.

    GREEN  — read-only, no state mutation, no external calls
    YELLOW — write to own DB, internal messages, reversible
    RED    — destructive: delete records, external comms (email/SMS),
             payment, robot motion, system config changes
    """
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class TrustTier(str, Enum):
    """Provenance level of the module."""
    BUILTIN = "builtin"       # ships with Murphy, founder-approved
    SIGNED = "signed"          # signed by a trusted publisher key
    COMMUNITY = "community"    # known publisher, not yet signed
    UNKNOWN = "unknown"        # never run by default


class SoulFit(str, Enum):
    """Which agent soul has natural affinity for this capability.

    Used by Rosetta to choose between candidates when multiple modules
    match the request.
    """
    COLLECTOR = "collector"
    TRANSLATOR = "translator"
    EXECUTOR = "executor"
    AUDITOR = "auditor"
    SCHEDULER = "scheduler"
    HITL = "hitl"
    EXEC_ADMIN = "exec_admin"
    PROD_OPS = "prod_ops"
    ROSETTA = "rosetta"
    ANY = "any"


# ── The manifest: a module's address in cube-space ──────────────────────────

@dataclass
class CapabilityManifest:
    """A module's 6-tuple address in the cube.

    `accepts` and `produces` are SETS — a module can handle multiple
    input shapes and emit multiple output shapes.

    Example — a sales-followup module:
        CapabilityManifest(
            accepts={Accepts.USER_INTENT, Accepts.STRUCTURED_DATA},
            produces={Produces.NOTIFICATION, Produces.AUDIT_EVENT},
            domain=Domain.SALES,
            risk_class=RiskClass.RED,        # sends external email
            trust_tier=TrustTier.BUILTIN,
            soul_fit=SoulFit.EXECUTOR,
            cost_hint=0.02,                   # ~$0.02 per dispatch
            avg_latency_ms=1500,
            description="Send a sales follow-up email to a lead",
        )
    """
    accepts: Set[Accepts]
    produces: Set[Produces]
    domain: Domain
    risk_class: RiskClass
    trust_tier: TrustTier
    soul_fit: SoulFit
    cost_hint: float = 0.0        # estimated $ cost per invocation
    avg_latency_ms: int = 0        # rough latency for ranking
    description: str = ""
    requires_hitl: bool = False    # force HITL approval regardless of risk
    tags: List[str] = field(default_factory=list)

    def address(self) -> Tuple:
        """The 6-axis address. Hashable; useful for indexing."""
        return (
            frozenset(self.accepts),
            frozenset(self.produces),
            self.domain,
            self.risk_class,
            self.trust_tier,
            self.soul_fit,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepts": sorted(a.value for a in self.accepts),
            "produces": sorted(p.value for p in self.produces),
            "domain": self.domain.value,
            "risk_class": self.risk_class.value,
            "trust_tier": self.trust_tier.value,
            "soul_fit": self.soul_fit.value,
            "cost_hint": self.cost_hint,
            "avg_latency_ms": self.avg_latency_ms,
            "description": self.description,
            "requires_hitl": self.requires_hitl,
            "tags": list(self.tags),
        }


# ── The cube: indexed storage for fast face-rotation queries ────────────────
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CapabilityManifest":
        """R615.7p — reconstruct a CapabilityManifest from a dict (DB row JSON).

        Inverse of to_dict. Tolerant of missing optional fields.
        """
        return cls(
            accepts={Accepts(a) for a in d.get("accepts", [])},
            produces={Produces(p) for p in d.get("produces", [])},
            domain=Domain(d["domain"]),
            risk_class=RiskClass(d["risk_class"]),
            trust_tier=TrustTier(d["trust_tier"]),
            soul_fit=SoulFit(d["soul_fit"]),
            cost_hint=d.get("cost_hint", 0.0),
            avg_latency_ms=d.get("avg_latency_ms", 0),
            description=d.get("description", ""),
            requires_hitl=d.get("requires_hitl", False),
            tags=d.get("tags", []),
        )


class CapabilityCube:
    """A semantic index over capability modules.

    The 'cube rotation' metaphor: each face is an axis, and querying
    `find(accepts=X, domain=Y)` is like rotating two faces and reading
    off the modules that align on both.
    """

    # Risk ordering: green < yellow < red
    _RISK_ORD = {RiskClass.GREEN: 0, RiskClass.YELLOW: 1, RiskClass.RED: 2}
    # Trust ordering: unknown < community < signed < builtin
    _TRUST_ORD = {
        TrustTier.UNKNOWN: 0,
        TrustTier.COMMUNITY: 1,
        TrustTier.SIGNED: 2,
        TrustTier.BUILTIN: 3,
    }

    def __init__(self):
        self._caps: Dict[str, CapabilityManifest] = {}
        # Inverted indexes per face — O(1) lookup per face value
        self._by_accept: Dict[Accepts, Set[str]] = {}
        self._by_produce: Dict[Produces, Set[str]] = {}
        self._by_domain: Dict[Domain, Set[str]] = {}
        self._by_risk: Dict[RiskClass, Set[str]] = {}
        self._by_trust: Dict[TrustTier, Set[str]] = {}
        self._by_soul: Dict[SoulFit, Set[str]] = {}

    # ── registration ────────────────────────────────────────────────────

    def register(self, name: str, manifest: CapabilityManifest) -> None:
        """Add a capability to the cube."""
        if name in self._caps:
            log.warning("capability %r already registered — overwriting", name)
            self._remove_from_indexes(name)
        self._caps[name] = manifest
        for a in manifest.accepts:
            self._by_accept.setdefault(a, set()).add(name)
        for p in manifest.produces:
            self._by_produce.setdefault(p, set()).add(name)
        self._by_domain.setdefault(manifest.domain, set()).add(name)
        self._by_risk.setdefault(manifest.risk_class, set()).add(name)
        self._by_trust.setdefault(manifest.trust_tier, set()).add(name)
        self._by_soul.setdefault(manifest.soul_fit, set()).add(name)
        log.info("CapabilityCube: registered %r at %s",
                 name, manifest.address())

    def _remove_from_indexes(self, name: str) -> None:
        m = self._caps.get(name)
        if not m:
            return
        for a in m.accepts:
            self._by_accept.get(a, set()).discard(name)
        for p in m.produces:
            self._by_produce.get(p, set()).discard(name)
        self._by_domain.get(m.domain, set()).discard(name)
        self._by_risk.get(m.risk_class, set()).discard(name)
        self._by_trust.get(m.trust_tier, set()).discard(name)
        self._by_soul.get(m.soul_fit, set()).discard(name)

    def unregister(self, name: str) -> bool:
        if name not in self._caps:
            return False
        self._remove_from_indexes(name)
        del self._caps[name]
        return True

    # ── queries ─────────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[CapabilityManifest]:
        return self._caps.get(name)

    def list_all(self) -> Dict[str, CapabilityManifest]:
        return dict(self._caps)

    def find(
        self,
        accepts: Optional[Accepts] = None,
        produces: Optional[Produces] = None,
        domain: Optional[Domain] = None,
        max_risk: Optional[RiskClass] = None,
        min_trust: Optional[TrustTier] = None,
        prefer_soul: Optional[SoulFit] = None,
    ) -> List[Tuple[str, float]]:
        """Rotate the cube on the given faces and return ranked matches.

        Returns a list of (name, score) tuples, highest score first.
        Score blends: soul-fit + trust + (1 - normalized_risk) + (1 - cost).
        """
        # Start with the universe
        candidates: Set[str] = set(self._caps.keys())

        # Apply face filters one by one — order doesn't affect final set
        if accepts is not None:
            candidates &= self._by_accept.get(accepts, set())
            # Also include modules accepting ANY
            candidates |= (
                self._by_accept.get(Accepts.ANY, set())
                & set(self._caps.keys())
            )
        if produces is not None:
            candidates &= self._by_produce.get(produces, set())
        if domain is not None:
            candidates &= self._by_domain.get(domain, set())

        # Risk gate: max_risk filters out anything more dangerous
        if max_risk is not None:
            risk_threshold = self._RISK_ORD[max_risk]
            candidates &= {
                n for n in candidates
                if self._RISK_ORD[self._caps[n].risk_class] <= risk_threshold
            }

        # Trust gate: min_trust filters out anything less trusted
        if min_trust is not None:
            trust_floor = self._TRUST_ORD[min_trust]
            candidates &= {
                n for n in candidates
                if self._TRUST_ORD[self._caps[n].trust_tier] >= trust_floor
            }

        # Score each surviving candidate
        ranked = [(n, self._score(n, prefer_soul)) for n in candidates]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def _score(self, name: str, prefer_soul: Optional[SoulFit]) -> float:
        """Score a candidate. Higher is better. Range roughly 0.0-1.0.

        Composition:
          0.35 * soul_fit_match
          0.25 * trust_level (normalized 0-1)
          0.20 * (1 - risk_level normalized 0-1)
          0.10 * (1 - cost_hint clipped at $1)
          0.10 * (1 - latency normalized at 10s)
        """
        m = self._caps[name]
        soul_score = 1.0 if (prefer_soul and m.soul_fit == prefer_soul) else (
            0.5 if m.soul_fit == SoulFit.ANY else 0.0
        )
        trust_score = self._TRUST_ORD[m.trust_tier] / 3.0  # 0..1
        risk_score = 1.0 - (self._RISK_ORD[m.risk_class] / 2.0)  # green=1, red=0
        cost_score = 1.0 - min(m.cost_hint, 1.0)
        latency_score = 1.0 - min(m.avg_latency_ms / 10000.0, 1.0)
        return (0.35 * soul_score
                + 0.25 * trust_score
                + 0.20 * risk_score
                + 0.10 * cost_score
                + 0.10 * latency_score)

    def address(self, name: str) -> Optional[Tuple]:
        m = self._caps.get(name)
        return m.address() if m else None

    def stats(self) -> Dict[str, Any]:
        return {
            "total_capabilities": len(self._caps),
            "by_domain": {d.value: len(s) for d, s in self._by_domain.items()},
            "by_risk":   {r.value: len(s) for r, s in self._by_risk.items()},
            "by_trust":  {t.value: len(s) for t, s in self._by_trust.items()},
            "by_soul":   {s.value: len(v) for s, v in self._by_soul.items()},
        }


# ── Singleton + helper ──────────────────────────────────────────────────────


# ── R615.7p — DB persistence layer ─────────────────────────────────────────
# CapabilityCube is per-process in-memory. To make registrations survive
# across processes and restarts (required by R615.7 "permanent org-chart node"
# contract), we persist to agent_substrate.db.capabilities and lazy-load
# the singleton from DB on first access.
#
# Standing Decision 53: persistence must survive PROCESS RESTART, not just
# Python session. This module is verified per Decision 53.

import json as _r615p_json
import sqlite3 as _r615p_sqlite3

_R615P_DB_PATH = "/var/lib/murphy-production/agent_substrate.db"


def _r615p_conn():
    c = _r615p_sqlite3.connect(_R615P_DB_PATH)
    c.row_factory = _r615p_sqlite3.Row
    return c


def _r615p_ensure_table(c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS capabilities (
            name TEXT PRIMARY KEY,
            manifest_json TEXT NOT NULL,
            domain TEXT NOT NULL,
            risk_class TEXT NOT NULL,
            trust_tier TEXT NOT NULL,
            soul_fit TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_cap_domain ON capabilities(domain)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cap_risk ON capabilities(risk_class)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cap_trust ON capabilities(trust_tier)")


def _r615p_persist(name: str, manifest: CapabilityManifest) -> None:
    """Write a capability to DB. Idempotent via PRIMARY KEY upsert."""
    try:
        manifest_json = _r615p_json.dumps(manifest.to_dict(), sort_keys=True, default=str)
        with _r615p_conn() as c:
            _r615p_ensure_table(c)
            c.execute("""
                INSERT INTO capabilities (name, manifest_json, domain, risk_class, trust_tier, soul_fit, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    manifest_json=excluded.manifest_json,
                    domain=excluded.domain,
                    risk_class=excluded.risk_class,
                    trust_tier=excluded.trust_tier,
                    soul_fit=excluded.soul_fit,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                name, manifest_json,
                manifest.domain.value, manifest.risk_class.value,
                manifest.trust_tier.value, manifest.soul_fit.value,
            ))
    except Exception as e:
        log.warning("R615.7p persist failed for %r: %s", name, e)


def _r615p_load_all() -> Dict[str, CapabilityManifest]:
    """Load all persisted capabilities from DB. Returns {} if table empty/missing."""
    out: Dict[str, CapabilityManifest] = {}
    try:
        with _r615p_conn() as c:
            _r615p_ensure_table(c)
            rows = c.execute("SELECT name, manifest_json FROM capabilities").fetchall()
            for r in rows:
                try:
                    d = _r615p_json.loads(r["manifest_json"])
                    out[r["name"]] = CapabilityManifest.from_dict(d)
                except Exception as e:
                    log.warning("R615.7p skip malformed manifest %r: %s", r["name"], e)
    except Exception as e:
        log.warning("R615.7p load failed: %s", e)
    return out


_CUBE: Optional[CapabilityCube] = None


def get_cube() -> CapabilityCube:
    """R615.7p — singleton with lazy-load from DB.

    On first access in a process, hydrates the cube from agent_substrate.db
    capabilities table so registrations from other processes are visible.
    """
    global _CUBE
    if _CUBE is None:
        _CUBE = CapabilityCube()
        # Lazy-load persisted capabilities (Decision 53: cross-process visibility)
        try:
            persisted = _r615p_load_all()
            for name, manifest in persisted.items():
                # Use private path to avoid re-writing back to DB on hydration
                _CUBE._caps[name] = manifest
                for a in manifest.accepts:
                    _CUBE._by_accept.setdefault(a, set()).add(name)
                for p in manifest.produces:
                    _CUBE._by_produce.setdefault(p, set()).add(name)
                _CUBE._by_domain.setdefault(manifest.domain, set()).add(name)
                _CUBE._by_risk.setdefault(manifest.risk_class, set()).add(name)
                _CUBE._by_trust.setdefault(manifest.trust_tier, set()).add(name)
                _CUBE._by_soul.setdefault(manifest.soul_fit, set()).add(name)
            if persisted:
                log.info("R615.7p: hydrated %d capabilities from DB", len(persisted))
        except Exception as e:
            log.warning("R615.7p hydration failed: %s", e)
    return _CUBE


def register_capability(name: str, manifest: CapabilityManifest) -> None:
    """Register + persist a capability.

    R615.7p: writes to both in-memory singleton AND the DB so registrations
    survive process restarts and are visible to other processes.
    """
    get_cube().register(name, manifest)
    _r615p_persist(name, manifest)


# ── FastAPI route mounting ──────────────────────────────────────────────────

class DispatchRequest(BaseModel):
    """Body for POST /api/cube/dispatch."""
    accepts: Optional[str] = None
    produces: Optional[str] = None
    domain: Optional[str] = None
    max_risk: Optional[str] = "yellow"
    min_trust: Optional[str] = "signed"
    prefer_soul: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


def install_cube_routes(app, require_auth=None) -> None:
    """Mount /api/cube/* routes on a FastAPI app.

    require_auth: optional dependency callable — if provided, will be
    used as a Depends() guard on POST endpoints. None = exposed (use
    middleware-level auth instead).
    """
    from fastapi import APIRouter, HTTPException, Query
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/cube", tags=["capability-cube"])
    cube = get_cube()

    @router.get("/health")
    def health():
        return {"ok": True, "patch": "412", "module": "capability_cube"}

    @router.get("/list")
    def list_caps():
        return {
            "capabilities": {
                name: m.to_dict() for name, m in cube.list_all().items()
            },
            "count": len(cube.list_all()),
        }

    @router.get("/stats")
    def stats():
        return cube.stats()

    @router.get("/address/{name}")
    def address(name: str):
        m = cube.get(name)
        if not m:
            raise HTTPException(404, f"capability '{name}' not found")
        return {
            "name": name,
            "manifest": m.to_dict(),
            "address": [str(x) for x in m.address()],
        }

    @router.get("/find")
    def find(
        accepts: Optional[str] = Query(None),
        produces: Optional[str] = Query(None),
        domain: Optional[str] = Query(None),
        max_risk: Optional[str] = Query(None),
        min_trust: Optional[str] = Query(None),
        prefer_soul: Optional[str] = Query(None),
    ):
        """Rotate the cube. All params optional."""
        try:
            results = cube.find(
                accepts=Accepts(accepts) if accepts else None,
                produces=Produces(produces) if produces else None,
                domain=Domain(domain) if domain else None,
                max_risk=RiskClass(max_risk) if max_risk else None,
                min_trust=TrustTier(min_trust) if min_trust else None,
                prefer_soul=SoulFit(prefer_soul) if prefer_soul else None,
            )
        except ValueError as e:
            raise HTTPException(400, f"invalid face value: {e}")
        return {
            "matches": [
                {"name": n, "score": round(s, 4),
                 "manifest": cube.get(n).to_dict()}
                for n, s in results
            ],
            "count": len(results),
        }

    @router.post("/dispatch")
    def dispatch(req: DispatchRequest):
        """Semantic dispatch — returns top candidate (not yet executed).

        This endpoint only ADDRESSES — it does not invoke the module.
        Invocation goes through whatever service hosts the module.
        Caller takes the top candidate's name and routes accordingly.
        """
        try:
            results = cube.find(
                accepts=Accepts(req.accepts) if req.accepts else None,
                produces=Produces(req.produces) if req.produces else None,
                domain=Domain(req.domain) if req.domain else None,
                max_risk=RiskClass(req.max_risk) if req.max_risk else None,
                min_trust=TrustTier(req.min_trust) if req.min_trust else None,
                prefer_soul=SoulFit(req.prefer_soul) if req.prefer_soul else None,
            )
        except ValueError as e:
            raise HTTPException(400, f"invalid face value: {e}")
        if not results:
            return {"matched": False, "candidates": [], "reason": "no capability matches all filters"}
        top_name, top_score = results[0]
        top_manifest = cube.get(top_name)
        return {
            "matched": True,
            "selected": top_name,
            "score": round(top_score, 4),
            "manifest": top_manifest.to_dict(),
            "requires_hitl": top_manifest.requires_hitl or top_manifest.risk_class == RiskClass.RED,
            "candidates": [
                {"name": n, "score": round(s, 4)} for n, s in results[:5]
            ],
        }

    app.include_router(router)
    log.info("PATCH-412 CapabilityCube routes mounted at /api/cube/*")


# ── Seed: register the modules we already know about ───────────────────────

def seed_builtin_capabilities() -> None:
    """Pre-register the capabilities Murphy already has built-in.

    Called once at boot. Idempotent — re-registering is safe.
    """
    seeds = [
        # Identity & auth
        ("identity_device_pair", CapabilityManifest(
            accepts={Accepts.USER_INTENT}, produces={Produces.DATA_RECORD, Produces.AUDIT_EVENT},
            domain=Domain.IDENTITY, risk_class=RiskClass.YELLOW,
            trust_tier=TrustTier.BUILTIN, soul_fit=SoulFit.EXEC_ADMIN,
            cost_hint=0.0, avg_latency_ms=200,
            description="Pair a new device to a user account",
        )),
        # Vault
        ("vault_read", CapabilityManifest(
            accepts={Accepts.USER_INTENT}, produces={Produces.DATA_RECORD},
            domain=Domain.SECURITY, risk_class=RiskClass.GREEN,
            trust_tier=TrustTier.BUILTIN, soul_fit=SoulFit.AUDITOR,
            cost_hint=0.0, avg_latency_ms=50,
            description="Read a stored secret with HITL approval",
            requires_hitl=True,
        )),
        ("vault_write", CapabilityManifest(
            accepts={Accepts.USER_INTENT}, produces={Produces.DATA_RECORD, Produces.AUDIT_EVENT},
            domain=Domain.SECURITY, risk_class=RiskClass.YELLOW,
            trust_tier=TrustTier.BUILTIN, soul_fit=SoulFit.EXEC_ADMIN,
            cost_hint=0.0, avg_latency_ms=100,
            description="Store a new secret in the vault",
            requires_hitl=True,
        )),
        # Audit
        ("audit_history_read", CapabilityManifest(
            accepts={Accepts.USER_INTENT}, produces={Produces.REPORT},
            domain=Domain.OBSERVABILITY, risk_class=RiskClass.GREEN,
            trust_tier=TrustTier.BUILTIN, soul_fit=SoulFit.AUDITOR,
            cost_hint=0.0, avg_latency_ms=100,
            description="Read audit log entries",
        )),
        # Robotics
        ("picarx_move", CapabilityManifest(
            accepts={Accepts.COMMAND if False else Accepts.USER_INTENT},
            produces={Produces.ROBOT_ACTION, Produces.AUDIT_EVENT},
            domain=Domain.ROBOTICS, risk_class=RiskClass.RED,
            trust_tier=TrustTier.BUILTIN, soul_fit=SoulFit.EXECUTOR,
            cost_hint=0.0, avg_latency_ms=300,
            description="Send a movement command to PiCar-X",
            requires_hitl=False,  # household-trusted, no HITL needed
        )),
        # Sales
        ("sales_followup_send", CapabilityManifest(
            accepts={Accepts.USER_INTENT, Accepts.STRUCTURED_DATA},
            produces={Produces.NOTIFICATION, Produces.AUDIT_EVENT},
            domain=Domain.SALES, risk_class=RiskClass.RED,
            trust_tier=TrustTier.BUILTIN, soul_fit=SoulFit.EXECUTOR,
            cost_hint=0.02, avg_latency_ms=1500,
            description="Send a sales follow-up email to a lead",
            requires_hitl=False,
        )),
        # Household
        ("household_profile_read", CapabilityManifest(
            accepts={Accepts.USER_INTENT}, produces={Produces.DATA_RECORD},
            domain=Domain.HOUSEHOLD, risk_class=RiskClass.GREEN,
            trust_tier=TrustTier.BUILTIN, soul_fit=SoulFit.AUDITOR,
            cost_hint=0.0, avg_latency_ms=50,
            description="Read a household member profile",
        )),
        # Sorting hat (client solutions)
        ("client_solutions_classify", CapabilityManifest(
            accepts={Accepts.TEXT, Accepts.HTTP_REQUEST},
            produces={Produces.DATA_RECORD, Produces.AUDIT_EVENT},
            domain=Domain.UX, risk_class=RiskClass.YELLOW,
            trust_tier=TrustTier.BUILTIN, soul_fit=SoulFit.TRANSLATOR,
            cost_hint=0.005, avg_latency_ms=400,
            description="Classify an incoming support ticket into billing/outage/sales",
        )),
        # Rosetta dispatch
        ("rosetta_dispatch", CapabilityManifest(
            accepts={Accepts.USER_INTENT, Accepts.SYSTEM_EVENT},
            produces={Produces.PLAN, Produces.COMMAND},
            domain=Domain.PLATFORM, risk_class=RiskClass.YELLOW,
            trust_tier=TrustTier.BUILTIN, soul_fit=SoulFit.ROSETTA,
            cost_hint=0.0, avg_latency_ms=100,
            description="Route a signal to the correct swarm agent",
        )),
        # Self-heal
        ("self_heal_probe", CapabilityManifest(
            accepts={Accepts.SYSTEM_EVENT}, produces={Produces.AUDIT_EVENT, Produces.SIDE_EFFECT},
            domain=Domain.OBSERVABILITY, risk_class=RiskClass.YELLOW,
            trust_tier=TrustTier.BUILTIN, soul_fit=SoulFit.PROD_OPS,
            cost_hint=0.0, avg_latency_ms=8000,
            description="Probe a route and trigger restart if persistently failing",
        )),
    ]
    cube = get_cube()
    for name, manifest in seeds:
        cube.register(name, manifest)
    log.info("PATCH-412 seeded %d builtin capabilities", len(seeds))
