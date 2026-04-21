"""PSM-003 / PSM-004 — Operator-approved HTTP launch surface.

Design labels: ``PSM-003`` (POST /launch), ``PSM-004`` (GET /console)
Owner: Platform Engineering
Depends on: :class:`RSCSelfModificationGate`, :class:`SelfEditLedger`,
            ``SelfAutomationOrchestrator`` (loose-coupled via duck-type),
            ``LyapunovMonitor`` (loose-coupled via duck-type).

Commissioning answers (CLAUDE.md / problem-statement checklist):

* **What is this module supposed to do?**
  Expose a *single* HTTP entry point for an operator to launch a
  self-modification cycle, with three immovable invariants:

    1. The request MUST carry a valid platform operator token in the
       ``X-Murphy-Platform-Operator`` header. No header → 401.
    2. The RSC pre-launch gate MUST allow the cycle. Veto → 409
       (and a ``VETOED`` ledger entry is still written).
    3. EVERY outcome — accepted, vetoed, errored — MUST land in the
       immutable ledger. The endpoint never returns a non-error code
       without ledger writes for both REQUESTED and (APPROVED+LAUNCHED
       or VETOED).

  The companion ``GET /console`` returns minimal server-rendered HTML
  showing the current Lyapunov state, the last 20 ledger entries, and a
  form that POSTs to ``/launch``. No JS framework, no client state.

* **What conditions are possible?**
  401 missing/invalid token; 422 bad body; 503 orchestrator not wired;
  503 ledger I/O failure; 409 RSC veto; 202 launched. Every code path
  has a unit test.

* **Restart-from-symptom:** every response carries a ``ledger_seq``
  field (or ``ledger_seq=null`` if the failure prevented a ledger
  write — a 503 outcome we surface explicitly, never silently). An
  operator can copy that seq and ``ledger.find_by_proposal(...)`` it.

* **Hardening:** constant-time token compare; no operator token in
  responses or logs; pydantic-validated body; orchestrator call wrapped
  to ledger-record FAILED on exception so a crash inside the
  orchestrator can never cause a silent partial state.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hmac
import html as html_lib
import logging
import os
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, ValidationError

from .ledger import LedgerEntryKind, SelfEditLedger
from .rsc_gate import RSCSelfModificationGate

logger = logging.getLogger(__name__)


DEFAULT_LEDGER_PATH = "data/platform_self_edit_ledger.jsonl"
LEDGER_PATH_ENV = "MURPHY_PLATFORM_SELF_EDIT_LEDGER_PATH"
OPERATOR_TOKEN_ENV = "MURPHY_PLATFORM_OPERATOR_TOKEN"
OPERATOR_HEADER = "X-Murphy-Platform-Operator"


class LaunchRequest(BaseModel):
    """Body of POST /api/platform/self-modification/launch.

    ``proposal_id`` ties this cycle to the originating
    ``ImprovementProposal`` (revertibility requirement). ``operator_id``
    is the human operator on record (audit requirement). ``justification``
    is free text shown in the ledger and the console.

    ``directive_id`` (ROSETTA-ORG-008) is the optional CEOBranch-side
    correlation id when the launch was triggered by
    ``CEOBranch.dispatch_directive_to_psm``.  When present it is
    forwarded into ``gap_analysis`` so the orchestrator can tie its
    cycle back to the originating directive end-to-end.
    """

    proposal_id: str = Field(min_length=1, max_length=128)
    operator_id: str = Field(min_length=1, max_length=128)
    justification: str = Field(min_length=1, max_length=2000)
    directive_id: Optional[str] = Field(default=None, max_length=128)


def _resolve_ledger_path() -> str:
    return os.environ.get(LEDGER_PATH_ENV, DEFAULT_LEDGER_PATH)


def _resolve_expected_token() -> Optional[str]:
    """Return the configured operator token, or None if unconfigured.

    Unconfigured means *every* request is denied — fail closed. We
    deliberately do NOT auto-generate a dev token; production explicitly
    sets the env var, dev/test sets it via fixture.
    """
    val = os.environ.get(OPERATOR_TOKEN_ENV, "").strip()
    return val or None


def _check_operator_token(supplied: Optional[str]) -> bool:
    expected = _resolve_expected_token()
    if not expected:
        return False
    if not supplied:
        return False
    # Constant-time compare prevents timing side-channels even though
    # this is a single static token.
    return hmac.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8"))


# ---------------------------------------------------------------------------
# ROSETTA-ORG-007 — executive + operations context collectors.
#
# Both collectors follow the same contract: given a zero-arg callable
# (or None), return a dict with a well-known shape containing the
# gathered context and a NAMED status.  Every failure mode is surfaced
# explicitly — never silent.
# ---------------------------------------------------------------------------

_MAX_INITIATIVES_IN_CONTEXT = 10
_COMPLETED_INITIATIVE_STATUSES = {"completed", "cancelled"}


def _collect_executive_context(
    get_planner: Optional[Callable[[], Any]],
    owner_role: Optional[str],
) -> Dict[str, Any]:
    """Collect open executive initiatives for the owner role.

    Returns a dict with keys:
        initiatives — list[dict] of at most
            ``_MAX_INITIATIVES_IN_CONTEXT`` open initiatives,
            ranked by ``rank_initiatives()``.  Empty when none
            available or when the engine is not wired.
        status — one of:
            * ``"not_wired"`` — ``get_planner`` was not supplied
              OR it returned ``None``.
            * ``"ok"`` — initiatives were collected successfully
              (may be an empty list if none are open).
            * ``"exception"`` — the planner raised; error is in
              ``error``.
        owner_role — echo of the input for downstream correlation.
        error — present only when ``status == "exception"``.

    ``owner_role`` is threaded through so callers can correlate the
    initiatives to the role later (the current
    :class:`ExecutiveStrategyPlanner` does not itself filter by role —
    future work: ROSETTA-ORG-009).
    """
    result: Dict[str, Any] = {
        "initiatives": [],
        "status": "not_wired",
        "owner_role": owner_role,
    }
    if get_planner is None:
        return result
    try:
        planner = get_planner()
    except Exception as exc:  # noqa: BLE001 — loud, not silent
        logger.warning("ROSETTA-ORG-007: get_executive_planner raised: %s", exc)
        result["status"] = "exception"
        result["error"] = f"get_planner: {exc}"
        return result
    if planner is None:
        return result
    try:
        ranked = planner.rank_initiatives()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ROSETTA-ORG-007: rank_initiatives raised: %s", exc)
        result["status"] = "exception"
        result["error"] = f"rank_initiatives: {exc}"
        return result

    open_initiatives: List[Dict[str, Any]] = []
    for init in ranked or []:
        try:
            status = str(init.get("status", "")).lower()
        except AttributeError:
            continue
        if status in _COMPLETED_INITIATIVE_STATUSES:
            continue
        open_initiatives.append(init)
        if len(open_initiatives) >= _MAX_INITIATIVES_IN_CONTEXT:
            break

    result["initiatives"] = open_initiatives
    result["status"] = "ok"
    return result


def _collect_operations_context(
    get_engine: Optional[Callable[[], Any]],
) -> Dict[str, Any]:
    """Collect active operations cycles from the OperationsCycleEngine.

    Returns a dict with keys:
        cycles — dict snapshot from ``engine.get_status()`` (empty
            when the engine is not wired).
        status — one of ``"not_wired"``, ``"ok"``, ``"exception"``.
        error — present only when ``status == "exception"``.
    """
    result: Dict[str, Any] = {"cycles": {}, "status": "not_wired"}
    if get_engine is None:
        return result
    try:
        engine = get_engine()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ROSETTA-ORG-007: get_operations_cycle_engine raised: %s", exc)
        result["status"] = "exception"
        result["error"] = f"get_engine: {exc}"
        return result
    if engine is None:
        return result
    try:
        snapshot = engine.get_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ROSETTA-ORG-007: engine.get_status raised: %s", exc)
        result["status"] = "exception"
        result["error"] = f"get_status: {exc}"
        return result

    result["cycles"] = snapshot if isinstance(snapshot, dict) else {"raw": snapshot}
    result["status"] = "ok"
    return result


def build_router(
    *,
    get_orchestrator: Callable[[], Any],
    get_lyapunov_source: Callable[[], Any],
    ledger_path: Optional[str] = None,
    get_rosetta_manager: Optional[Callable[[], Any]] = None,
    get_executive_planner: Optional[Callable[[], Any]] = None,
    get_operations_cycle_engine: Optional[Callable[[], Any]] = None,
) -> APIRouter:
    """Construct the platform self-modification router.

    Parameters
    ----------
    get_orchestrator:
        Zero-arg callable returning the SelfAutomationOrchestrator (or
        None if not yet wired). Resolved per-request so startup ordering
        bugs surface as a 503 instead of a stale closure.
    get_lyapunov_source:
        Zero-arg callable returning a LyapunovMonitor or
        RecursiveStabilityController (or None if RSC isn't running). The
        gate fails closed when None is returned.
    ledger_path:
        Override for tests. Defaults to env-or-disk default.
    get_rosetta_manager:
        ROSETTA-ORG-004. Optional zero-arg callable returning a
        :class:`RosettaManager`. When supplied, the launch endpoint
        attaches ``owner_role`` and ``approver_chain`` (walked via the
        platform org chart) to the APPROVED + LAUNCHED ledger payloads
        and to ``gap_analysis``.  An unknown operator_id surfaces an
        explicit ``owner_lookup: "unknown_operator"`` — never silent.
        If omitted, behavior is unchanged from PSM-003 baseline.
    get_executive_planner:
        ROSETTA-ORG-007. Optional zero-arg callable returning an
        :class:`ExecutivePlanningEngine.ExecutiveStrategyPlanner`-style
        object (any duck-typed value with a ``rank_initiatives()``
        method returning ``List[Dict[str, Any]]``).  When wired, the
        launch attaches up to 10 open initiatives (not COMPLETED /
        CANCELLED) to ``gap_analysis["executive_initiatives"]`` with
        ``executive_status="ok"``.  Exceptions surface as
        ``executive_status="exception"`` with the error message — never
        silent.  When omitted, ``executive_status="not_wired"``.
    get_operations_cycle_engine:
        ROSETTA-ORG-007. Optional zero-arg callable returning an
        :class:`OperationsCycleEngine`-style object (any duck-typed
        value with a ``get_status()`` method returning a dict).  When
        wired, ``gap_analysis["operations_cycles"]`` is populated with
        the status snapshot and ``ops_status="ok"``.  Exceptions
        surface as ``ops_status="exception"``.  When omitted,
        ``ops_status="not_wired"``.
    """
    router = APIRouter(prefix="/api/platform/self-modification", tags=["platform-self-mod"])
    ledger = SelfEditLedger(ledger_path or _resolve_ledger_path())

    # --------------------------------------------------------------
    # PSM-003 — POST /launch
    # --------------------------------------------------------------

    @router.post("/launch", status_code=status.HTTP_202_ACCEPTED)
    async def launch_self_modification(  # noqa: D401 — endpoint, not function
        request: Request,
        x_murphy_platform_operator: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        """Launch a self-modification cycle (operator-approved, RSC-gated)."""

        # 1. AuthN — must be first; never log the supplied token.
        if not _check_operator_token(x_murphy_platform_operator):
            return JSONResponse(
                status_code=401,
                content={
                    "ok": False,
                    "error": "missing_or_invalid_operator_token",
                    "message": (
                        "PSM-003: request lacks a valid "
                        f"{OPERATOR_HEADER} header."
                    ),
                },
            )

        # 2. Parse + validate body. Pydantic gives us 422-shaped errors.
        try:
            raw = await request.json()
        except Exception:
            raw = None
        if not isinstance(raw, dict):
            return JSONResponse(
                status_code=422,
                content={"ok": False, "error": "invalid_json_body"},
            )
        try:
            req = LaunchRequest(**raw)
        except ValidationError as ve:
            return JSONResponse(
                status_code=422,
                content={"ok": False, "error": "validation_error", "detail": ve.errors()},
            )

        # 3. Ledger REQUESTED — even VETOED requests need provenance.
        try:
            requested_entry = ledger.record(
                LedgerEntryKind.REQUESTED,
                proposal_id=req.proposal_id,
                operator_id=req.operator_id,
                payload={"justification": req.justification},
            )
        except Exception as exc:  # noqa: BLE001 — surface, never silent
            logger.exception("PSM-003: ledger write failed on REQUESTED")
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error": "ledger_unavailable",
                    "message": f"PSM-003: ledger write failed: {exc}",
                    "ledger_seq": None,
                },
            )

        # 4. RSC pre-launch gate.
        lyap_source = get_lyapunov_source()
        if lyap_source is None:
            decision_snapshot = {"reason": "lyapunov_source_missing"}
            ledger.record(
                LedgerEntryKind.VETOED,
                proposal_id=req.proposal_id,
                operator_id=req.operator_id,
                rsc_snapshot=decision_snapshot,
                payload={"reason": "lyapunov_source_missing"},
            )
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error": "rsc_unavailable",
                    "message": "PSM-003: RSC/Lyapunov source not wired; cannot gate.",
                    "ledger_seq": requested_entry.seq,
                },
            )

        gate = RSCSelfModificationGate(lyap_source)
        decision = gate.check_pre_launch()
        if not decision.allowed:
            vetoed = ledger.record(
                LedgerEntryKind.VETOED,
                proposal_id=req.proposal_id,
                operator_id=req.operator_id,
                rsc_snapshot=decision.snapshot,
                payload={"reason": decision.reason, "message": decision.message},
            )
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "error": "rsc_veto",
                    "reason": decision.reason,
                    "message": decision.message,
                    "ledger_seq": vetoed.seq,
                },
            )

        # 5. Orchestrator MUST be present before we record APPROVED — we
        # don't want an APPROVED entry that never becomes a LAUNCHED.
        orchestrator = get_orchestrator()
        if orchestrator is None:
            ledger.record(
                LedgerEntryKind.FAILED,
                proposal_id=req.proposal_id,
                operator_id=req.operator_id,
                rsc_snapshot=decision.snapshot,
                payload={"reason": "orchestrator_unavailable"},
            )
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error": "orchestrator_unavailable",
                    "message": "PSM-003: SelfAutomationOrchestrator not wired.",
                    "ledger_seq": requested_entry.seq,
                },
            )

        # ROSETTA-ORG-004: owner-role attribution.  Failures here MUST
        # NOT block the launch (the pipeline pre-dates Rosetta wiring),
        # but every failure mode is named explicitly in owner_info so
        # the ledger and response carry it forward — never silent.
        owner_info: Dict[str, Any] = {
            "owner_role": None,
            "approver_chain": [],
            "owner_lookup": "rosetta_not_wired",
        }
        if get_rosetta_manager is not None:
            try:
                from rosetta.org_chart import lookup_role_for_operator
                manager = get_rosetta_manager()
                owner_info = lookup_role_for_operator(manager, req.operator_id)
            except Exception as _lookup_exc:  # noqa: BLE001
                logger.error(
                    "PSM-003: Rosetta owner lookup raised: %s",
                    _lookup_exc, exc_info=_lookup_exc,
                )
                owner_info = {
                    "owner_role": None,
                    "approver_chain": [],
                    "owner_lookup": "lookup_exception",
                    "lookup_error": str(_lookup_exc),
                }

        approved = ledger.record(
            LedgerEntryKind.APPROVED,
            proposal_id=req.proposal_id,
            operator_id=req.operator_id,
            rsc_snapshot=decision.snapshot,
            payload={"reason": decision.reason, **owner_info},
        )

        # ROSETTA-ORG-007 — collect executive + ops context.  Each
        # failure mode is named in the gap_analysis / ledger payload
        # so the orchestrator never silently loses context.
        exec_info = _collect_executive_context(
            get_executive_planner, owner_info.get("owner_role"),
        )
        ops_info = _collect_operations_context(get_operations_cycle_engine)

        # 6. Hand off to the orchestrator. Wrapped so any exception in
        # third-party code becomes a FAILED entry, not a 500 with no
        # provenance.
        try:
            cycle = orchestrator.start_cycle(
                gap_analysis={
                    "source": "platform_self_modification",
                    "proposal_id": req.proposal_id,
                    "operator_id": req.operator_id,
                    "justification": req.justification,
                    "ledger_seq_approved": approved.seq,
                    # ROSETTA-ORG-004: tell the orchestrator who owns
                    # this cycle and who the approvers are.
                    "owner_role": owner_info.get("owner_role"),
                    "approver_chain": owner_info.get("approver_chain", []),
                    "owner_lookup": owner_info.get("owner_lookup"),
                    # ROSETTA-ORG-007: executive + ops context.
                    "executive_initiatives": exec_info["initiatives"],
                    "executive_status": exec_info["status"],
                    "operations_cycles": ops_info["cycles"],
                    "ops_status": ops_info["status"],
                    # ROSETTA-ORG-008: directive correlation id (or None
                    # if this launch was not triggered by a CEOBranch
                    # directive).  Carrying it makes the end-to-end
                    # trace queryable from either side.
                    "directive_id": req.directive_id,
                }
            )
            cycle_id = getattr(cycle, "cycle_id", None) or str(cycle)
        except Exception as exc:  # noqa: BLE001
            logger.exception("PSM-003: orchestrator.start_cycle failed")
            ledger.record(
                LedgerEntryKind.FAILED,
                proposal_id=req.proposal_id,
                operator_id=req.operator_id,
                rsc_snapshot=decision.snapshot,
                payload={
                    "reason": "orchestrator_exception",
                    "detail": str(exc),
                    **owner_info,
                    "executive_status": exec_info["status"],
                    "ops_status": ops_info["status"],
                    "directive_id": req.directive_id,
                },
            )
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "error": "orchestrator_error",
                    "message": f"PSM-003: orchestrator raised: {exc}",
                    "ledger_seq": approved.seq,
                },
            )

        launched = ledger.record(
            LedgerEntryKind.LAUNCHED,
            proposal_id=req.proposal_id,
            operator_id=req.operator_id,
            rsc_snapshot=decision.snapshot,
            payload={
                "cycle_id": cycle_id,
                **owner_info,
                "executive_status": exec_info["status"],
                "ops_status": ops_info["status"],
                "directive_id": req.directive_id,
            },
        )
        return JSONResponse(
            status_code=202,
            content={
                "ok": True,
                "cycle_id": cycle_id,
                "proposal_id": req.proposal_id,
                "ledger_seq": launched.seq,
                "rsc_reason": decision.reason,
                "owner_role": owner_info.get("owner_role"),
                "owner_lookup": owner_info.get("owner_lookup"),
                "executive_status": exec_info["status"],
                "ops_status": ops_info["status"],
                "directive_id": req.directive_id,
            },
        )

    # --------------------------------------------------------------
    # GET /ledger — JSON view of the immutable log
    # --------------------------------------------------------------

    @router.get("/ledger")
    async def ledger_tail(limit: int = 20) -> JSONResponse:
        limit = max(1, min(int(limit), 200))
        entries = [e.to_dict() for e in ledger.tail(limit)]
        ok, err = ledger.verify_chain()
        return JSONResponse(
            {
                "ok": True,
                "chain_verified": ok,
                "chain_error": err,
                "count": len(entries),
                "entries": entries,
            }
        )

    # --------------------------------------------------------------
    # PSM-004 — GET /console (server-rendered HTML "operator button")
    # --------------------------------------------------------------

    @router.get("/console", response_class=HTMLResponse)
    async def console() -> HTMLResponse:
        lyap_source = get_lyapunov_source()
        if lyap_source is None:
            rsc_block = (
                '<p class="warn">RSC/Lyapunov source not wired — '
                "launches will fail with 503.</p>"
            )
        else:
            try:
                gate = RSCSelfModificationGate(lyap_source)
                decision = gate.check_pre_launch()
                cls = "ok" if decision.allowed else "warn"
                rsc_block = (
                    f'<p class="{cls}"><strong>RSC:</strong> '
                    f"{html_lib.escape(decision.reason)} — "
                    f"{html_lib.escape(decision.message)}</p>"
                )
            except Exception as exc:  # noqa: BLE001
                rsc_block = (
                    f'<p class="warn">RSC gate evaluation error: '
                    f"{html_lib.escape(str(exc))}</p>"
                )

        rows = []
        for e in reversed(ledger.tail(20)):
            rows.append(
                "<tr>"
                f"<td>{e.seq}</td>"
                f"<td>{html_lib.escape(e.ts)}</td>"
                f"<td>{html_lib.escape(e.kind)}</td>"
                f"<td>{html_lib.escape(e.proposal_id)}</td>"
                f"<td>{html_lib.escape(e.operator_id)}</td>"
                f"<td><code>{html_lib.escape(e.this_hash[:12])}…</code></td>"
                "</tr>"
            )
        if not rows:
            rows.append('<tr><td colspan="6"><em>No entries yet.</em></td></tr>')

        token_status = (
            "configured" if _resolve_expected_token() else "NOT CONFIGURED — endpoint will refuse all requests"
        )

        body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Murphy — Platform Self-Modification Console</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; }}
  h1 {{ margin-bottom: .25rem; }}
  .sub {{ color: #666; margin-top: 0; }}
  .ok {{ color: #060; }}
  .warn {{ color: #a40; font-weight: 600; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .9rem; }}
  th, td {{ border: 1px solid #ccc; padding: .35rem .5rem; text-align: left; }}
  th {{ background: #f4f4f4; }}
  form {{ background: #fafafa; border: 1px solid #ddd; padding: 1rem; margin: 1rem 0; }}
  label {{ display: block; margin: .5rem 0 .15rem; font-weight: 600; }}
  input, textarea {{ width: 100%; padding: .35rem; box-sizing: border-box; }}
  button {{ margin-top: .75rem; padding: .5rem 1rem; font-weight: 600; cursor: pointer; }}
</style></head>
<body>
<h1>Platform Self-Modification Console</h1>
<p class="sub">PSM-004 · Operator-approved launch surface · platform-scope only
(distinct from per-tenant HITL).</p>

<h2>Pre-launch status</h2>
{rsc_block}
<p>Operator token: <strong>{token_status}</strong></p>

<h2>Launch a cycle</h2>
<form method="post" action="/api/platform/self-modification/launch"
      onsubmit="
        var t = document.getElementById('opToken').value;
        var p = document.getElementById('proposalId').value;
        var o = document.getElementById('operatorId').value;
        var j = document.getElementById('justification').value;
        fetch(this.action, {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json',
            '{OPERATOR_HEADER}': t,
          }},
          body: JSON.stringify({{
            proposal_id: p, operator_id: o, justification: j,
          }}),
        }}).then(r => r.json().then(b => alert(r.status + ' — ' + JSON.stringify(b, null, 2))));
        return false;">
  <label for="opToken">Operator approval token (sent in <code>{OPERATOR_HEADER}</code>)</label>
  <input id="opToken" type="password" autocomplete="off" required>
  <label for="proposalId">ImprovementProposal ID</label>
  <input id="proposalId" type="text" required>
  <label for="operatorId">Operator ID (your name / employee ID)</label>
  <input id="operatorId" type="text" required>
  <label for="justification">Justification (audited)</label>
  <textarea id="justification" rows="3" required></textarea>
  <button type="submit">Launch self-modification cycle</button>
</form>

<h2>Recent ledger entries (newest first)</h2>
<table>
  <thead><tr><th>Seq</th><th>Timestamp</th><th>Kind</th>
  <th>Proposal</th><th>Operator</th><th>Hash</th></tr></thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
</body></html>"""
        return HTMLResponse(content=body)

    return router
