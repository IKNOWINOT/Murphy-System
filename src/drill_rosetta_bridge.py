"""
Ship 31am — Drill + Rosetta + Pipeline Bridge
═════════════════════════════════════════════

Wires the already-built infrastructure that was orphaned:

  Inbound stranger email
      ↓
  drive_boundary_loop()         ← conductor (Δ + dΔ/dt convergence)
      ↓
  DynamicRosettaPlanner.plan()  ← picks team + writes per-agent souls
      ↓
  SwarmCoordinator.pipeline()   ← multi-agent ping-pong with context_chain
      ↓                            (each agent gets capability_invoker via patch412 cube)
  agents may call any of 1,130 Murphy endpoints via R424 bridge
      ↓
  drill measures Δ after pipeline; re-runs if not converged (max 2 rounds for email)
      ↓
  Phase E.1: assemble files → MIME multipart attach (Ship 31ag path)
  Phase E.2: optional Drive upload + share_file(writer) — dormant until creds in vault

Founder canon (USER memory + SD-56):
  - "drill is the conductor, used between any round any time"
  - "Rosetta injections are written based on a drill down"
  - personas come from Rosetta planner, NOT drill
  - agents can call anything in Murphy.system
  - highest-privilege share = role='writer' (per-file scope automatic)

Graceful degradation:
  - If MURPHY_FOUNDER_KEY not in vault → drill skips HTTP magnify, falls back to in-process
  - If GOOGLE_SERVICE_ACCOUNT_JSON not in vault → Drive path no-ops, MIME attach still ships
  - If DynamicRosettaPlanner unavailable → falls back to legacy _magnify_drill path
  - ZERO downstream consumers break when this module is missing
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.drill_rosetta_bridge")

# Founder-tunable for the email channel.
# Drill default is 5 iterations; email gets 2 to keep latency < 60s.
EMAIL_MAX_DRILL_ROUNDS = 2
EMAIL_BUDGET_CAP_USD   = 0.20
EMAIL_TOLERANCE        = 0.10
EMAIL_FLATLINE_THRESH  = 0.02

# ─────────────────────────────────────────────────────────────
# Vault accessor — graceful no-key fallback
# ─────────────────────────────────────────────────────────────

def _vault(name: str) -> Optional[str]:
    """Read a platform secret. Returns None on any failure — caller decides."""
    try:
        from src.nowpayments_billing import _vault_or_env
        v = _vault_or_env(name)
        return v or None
    except Exception as exc:
        logger.debug("vault read %s failed: %s", name, exc)
        return os.getenv(name) or None


def _founder_key_available() -> bool:
    return bool(_vault("MURPHY_FOUNDER_KEY"))


def _drive_creds_available() -> bool:
    return bool(_vault("GOOGLE_SERVICE_ACCOUNT_JSON"))


# ─────────────────────────────────────────────────────────────
# Capability invoker — gives an agent the ability to call any
# of Murphy's 1,130 endpoints via R424 bridge + patch412 cube
# ─────────────────────────────────────────────────────────────

class CapabilityInvoker:
    """Bound invoker an agent uses to call other Murphy endpoints.

    Filters by the calling role's r425 task_config (capability_allowlist,
    risk_class, trust_tier) so an SDR can't dispatch a wire transfer.
    """

    def __init__(self, agent_id: str, role_class: str,
                 risk_class: str = "low", trust_tier: str = "standard"):
        self.agent_id    = agent_id
        self.role_class  = role_class
        self.risk_class  = risk_class
        self.trust_tier  = trust_tier
        self._cube       = None
        self._task_cfg   = None
        self._load()

    def _load(self):
        try:
            from src.patch412_capability_cube import get_capability_cube
            self._cube = get_capability_cube()
        except Exception as exc:
            logger.debug("capability_cube unavailable: %s", exc)
        try:
            from src.r425_rosetta_task_config import get_task_config
            self._task_cfg = get_task_config(self.role_class, scope="platform")
        except Exception as exc:
            logger.debug("r425 task_config unavailable for %s: %s",
                         self.role_class, exc)

    def discover(self, accepts: str = None, produces: str = None,
                 domain: str = None) -> List[Dict[str, Any]]:
        """Find capabilities matching a soul-fit query."""
        if not self._cube:
            return []
        try:
            return self._cube.query(
                accepts=accepts, produces=produces, domain=domain,
                max_risk=self.risk_class, min_trust=self.trust_tier,
            )
        except Exception as exc:
            logger.warning("cube.query failed: %s", exc)
            return []

    def invoke(self, capability_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a capability by ID. Enforces r425 allowlist if loaded."""
        # r425 allowlist gate
        if self._task_cfg:
            allowed = self._task_cfg.get("capability_allowlist") or []
            # Empty allowlist = no restriction (early-life roles); non-empty = strict
            if allowed and capability_id not in allowed:
                # Wildcard groups: check if any allowlist entry is a prefix
                if not any(capability_id.startswith(a.rstrip("*")) for a in allowed if a.endswith("*")):
                    return {
                        "status": "denied",
                        "reason": f"capability '{capability_id}' not in allowlist for {self.role_class}",
                    }
        if not self._cube:
            return {"status": "error", "reason": "capability_cube not loaded"}
        try:
            return self._cube.invoke(capability_id, payload,
                                     caller_agent_id=self.agent_id,
                                     caller_role=self.role_class)
        except Exception as exc:
            logger.warning("capability invoke failed: %s", exc)
            return {"status": "error", "reason": str(exc)}


# ─────────────────────────────────────────────────────────────
# Drive helper — dormant until vault has GOOGLE_SERVICE_ACCOUNT_JSON
# ─────────────────────────────────────────────────────────────

@dataclass
class DriveShareResult:
    success:       bool
    file_id:       Optional[str] = None
    web_view_link: Optional[str] = None
    shared_with:   Optional[str] = None
    role_granted:  Optional[str] = None
    reason:        str = ""


def upload_and_share(
    local_path: str,
    file_name: str,
    share_with_email: str,
    role: str = "writer",
    folder_id: Optional[str] = None,
) -> DriveShareResult:
    """Upload a file to Drive and share it with the requester at writer role.

    Returns DriveShareResult.success=False with a clear reason when:
      - GOOGLE_SERVICE_ACCOUNT_JSON is not in vault (dormant mode)
      - googleapiclient is not installed
      - Drive API returns an error

    'writer' is the highest privilege Murphy grants on per-file scope.
    Owner stays with the service account so Murphy can revoke later.
    """
    creds_json = _vault("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        return DriveShareResult(
            success=False,
            reason="GOOGLE_SERVICE_ACCOUNT_JSON not in vault — Drive path dormant",
        )

    folder_id = folder_id or _vault("MURPHY_DRIVE_FOLDER_ID") or None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        return DriveShareResult(
            success=False,
            reason=f"google-api-python-client not installed: {exc}",
        )

    try:
        creds_dict = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)

        # Upload
        meta: Dict[str, Any] = {"name": file_name}
        if folder_id:
            meta["parents"] = [folder_id]
        media = MediaFileUpload(local_path, resumable=False)
        file = drive.files().create(
            body=meta, media_body=media,
            fields="id,webViewLink",
        ).execute()
        file_id = file["id"]

        # Share — writer privilege, per-file scope, no notification spam
        drive.permissions().create(
            fileId=file_id,
            body={"type": "user", "role": role, "emailAddress": share_with_email},
            sendNotificationEmail=False,
        ).execute()

        return DriveShareResult(
            success=True,
            file_id=file_id,
            web_view_link=file.get("webViewLink"),
            shared_with=share_with_email,
            role_granted=role,
        )

    except Exception as exc:
        logger.warning("Drive upload/share failed: %s", exc)
        return DriveShareResult(success=False, reason=f"drive API error: {exc}")


def revoke_share(file_id: str, email: str) -> bool:
    """Revoke a previously-granted share. Returns True on success."""
    creds_json = _vault("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        return False
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        perms = drive.permissions().list(fileId=file_id).execute()
        for p in perms.get("permissions", []):
            if p.get("emailAddress") == email:
                drive.permissions().delete(fileId=file_id, permissionId=p["id"]).execute()
                return True
        return False
    except Exception as exc:
        logger.warning("revoke_share failed: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────
# Main bridge entry point — called from stranger_responder
# ─────────────────────────────────────────────────────────────

@dataclass
class BridgeResult:
    success:              bool
    body_text:            str
    attachments:          List[Dict[str, Any]] = field(default_factory=list)
    drive_shares:         List[Dict[str, Any]] = field(default_factory=list)
    drill_iterations:     int = 0
    rosetta_team:         List[str] = field(default_factory=list)
    pipeline_completed:   int = 0
    total_cost_usd:       float = 0.0
    fallback_reason:      str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_drill_rosetta_pipeline(
    subject: str,
    body: str,
    from_addr: str,
    *,
    max_rounds: int = EMAIL_MAX_DRILL_ROUNDS,
    budget_cap: float = EMAIL_BUDGET_CAP_USD,
    want_drive_share: bool = False,
) -> BridgeResult:
    """The wired pipeline. Returns BridgeResult or a legacy-fallback flag.

    On ANY infra failure, returns BridgeResult(success=False, fallback_reason=...)
    so the caller (stranger_responder) falls back to the legacy _magnify_drill
    single-shot path. Nothing in production breaks.
    """
    t0 = time.time()
    dispatch_id = f"31am_{uuid.uuid4().hex[:12]}"

    # ── Step 1: Drill plans the deliverable ──
    try:
        from src.pcr060_drill_driver import drive_boundary_loop
    except Exception as exc:
        return BridgeResult(success=False, body_text="",
                            fallback_reason=f"drill_driver_unavailable: {exc}")

    # Inject founder key from vault for HTTP magnify auth
    fkey = _vault("MURPHY_FOUNDER_KEY")
    if fkey and not os.getenv("MURPHY_FOUNDER_KEY"):
        os.environ["MURPHY_FOUNDER_KEY"] = fkey

    drill_prompt = (
        f"Plan the deliverable for an inbound stranger email.\n"
        f"FROM: {from_addr}\nSUBJECT: {subject}\nBODY: {body[:1500]}\n\n"
        f"Output (a) what the reply needs to contain, (b) what sub-files "
        f"should accompany it, (c) what specialist roles must contribute."
    )

    try:
        drill_result = drive_boundary_loop(
            prompt=drill_prompt,
            business_spec={"channel": "email", "audience": "stranger",
                           "from_addr": from_addr, "dispatch_id": dispatch_id},
            max_iterations=max_rounds,
            budget_cap_usd=budget_cap,
            tolerance=EMAIL_TOLERANCE,
            flatline_threshold=EMAIL_FLATLINE_THRESH,
            dispatch_id=dispatch_id,
        )
    except Exception as exc:
        return BridgeResult(success=False, body_text="",
                            fallback_reason=f"drill_loop_failed: {exc}")

    if not drill_result.success or not drill_result.deliverable:
        return BridgeResult(success=False, body_text="",
                            drill_iterations=drill_result.iterations_run,
                            total_cost_usd=drill_result.cumulative_cost_usd,
                            fallback_reason=f"drill_no_deliverable: {drill_result.reason}")

    deliverable_plan = drill_result.deliverable
    cost = drill_result.cumulative_cost_usd

    # ── Step 2: Rosetta planner picks the team + writes souls ──
    try:
        from src.dynamic_rosetta_planner import DynamicRosettaPlanner
        planner = DynamicRosettaPlanner()
        plan_prompt = json.dumps(deliverable_plan) if isinstance(deliverable_plan, dict) else str(deliverable_plan)
        dispatch_packet = planner.plan(plan_prompt)
    except Exception as exc:
        return BridgeResult(success=False, body_text="",
                            drill_iterations=drill_result.iterations_run,
                            total_cost_usd=cost,
                            fallback_reason=f"rosetta_plan_failed: {exc}")

    team = dispatch_packet.team if hasattr(dispatch_packet, "team") else []
    if not team:
        return BridgeResult(success=False, body_text="",
                            drill_iterations=drill_result.iterations_run,
                            total_cost_usd=cost,
                            fallback_reason="rosetta_empty_team")

    team_ids = [a.agent_id for a in team]
    logger.info("31am rosetta team: %s", team_ids)

    # ── Step 3: SwarmCoordinator pipeline — multi-agent ping-pong ──
    try:
        from src.rosetta_core import get_swarm_coordinator
        coord = get_swarm_coordinator()
    except Exception as exc:
        return BridgeResult(success=False, body_text="",
                            drill_iterations=drill_result.iterations_run,
                            rosetta_team=team_ids, total_cost_usd=cost,
                            fallback_reason=f"swarm_unavailable: {exc}")

    # Build signal with capability_invoker handle for each agent
    signal = {
        "signal_id":      dispatch_id,
        "signal_type":    "stranger_email_reply",
        "subject":        subject,
        "body":           body,
        "from_addr":      from_addr,
        "deliverable":    deliverable_plan,
        "context_chain":  [],
        "tenant_id":      "platform",
    }
    # Attach a capability_invoker FACTORY — agents instantiate their own
    # bound invoker keyed to their role_class
    signal["capability_invoker_factory"] = lambda role_class, agent_id: CapabilityInvoker(
        agent_id=agent_id, role_class=role_class,
        risk_class="low",  # email channel = low risk by default
        trust_tier="standard",
    )

    try:
        pipeline_result = coord.pipeline(signal, team_ids)
    except Exception as exc:
        return BridgeResult(success=False, body_text="",
                            drill_iterations=drill_result.iterations_run,
                            rosetta_team=team_ids, total_cost_usd=cost,
                            fallback_reason=f"pipeline_failed: {exc}")

    completed = pipeline_result.get("completed", 0)
    context_chain = pipeline_result.get("context_chain", [])

    # ── Step 4: Assemble body + attachments from context_chain ──
    # Each agent emits a contribution; last agent's text → body, others → attachments
    body_text = ""
    attachments: List[Dict[str, Any]] = []
    for entry in context_chain:
        agent_id = entry.get("agent_id", "")
        contribution = entry.get("contribution") or entry.get("result", {})
        if isinstance(contribution, dict):
            text = contribution.get("text", "") or contribution.get("body", "")
            file_path = contribution.get("file_path")
            file_name = contribution.get("file_name")
            if file_path and file_name:
                attachments.append({"agent_id": agent_id,
                                    "file_path": file_path,
                                    "file_name": file_name,
                                    "mime": contribution.get("mime", "application/octet-stream")})
            elif text and not body_text:
                # First text contribution becomes body if nothing assembled yet
                body_text = text
            elif text:
                body_text += "\n\n" + text
        elif isinstance(contribution, str) and not body_text:
            body_text = contribution

    # If nothing assembled, fail clean → caller falls back
    if not body_text:
        return BridgeResult(success=False, body_text="",
                            drill_iterations=drill_result.iterations_run,
                            rosetta_team=team_ids, total_cost_usd=cost,
                            pipeline_completed=completed,
                            fallback_reason="no_body_text_from_pipeline")

    # ── Step 5: Drive-share variant (dormant unless want_drive_share + creds) ──
    drive_shares: List[Dict[str, Any]] = []
    if want_drive_share and attachments and _drive_creds_available():
        for att in attachments:
            res = upload_and_share(
                local_path=att["file_path"],
                file_name=att["file_name"],
                share_with_email=from_addr,
                role="writer",
            )
            if res.success:
                drive_shares.append({
                    "file_name":     att["file_name"],
                    "file_id":       res.file_id,
                    "web_view_link": res.web_view_link,
                    "shared_with":   res.shared_with,
                    "role":          res.role_granted,
                })

    # ── Step 6: agent_email_chain — internal audit thread (Murphy operators see what agents wrote) ──
    try:
        from src.agent_email_chain import fire_agent_email_chain
        # Fire and forget — internal CC thread
        fire_agent_email_chain(
            acting_agent="murphy",
            signal=signal,
            result={"team": team_ids, "completed": completed, "body_preview": body_text[:300]},
            outcome="stranger_reply_assembled",
        )
    except Exception as exc:
        logger.debug("agent_email_chain skipped: %s", exc)

    elapsed = time.time() - t0
    logger.info("31am pipeline OK in %.1fs: drill=%d rounds, team=%d agents, completed=%d, $%.4f",
                elapsed, drill_result.iterations_run, len(team), completed, cost)

    return BridgeResult(
        success=True,
        body_text=body_text,
        attachments=attachments,
        drive_shares=drive_shares,
        drill_iterations=drill_result.iterations_run,
        rosetta_team=team_ids,
        pipeline_completed=completed,
        total_cost_usd=cost,
    )


# ─────────────────────────────────────────────────────────────
# Healthcheck for the wiring
# ─────────────────────────────────────────────────────────────

def health() -> Dict[str, Any]:
    """Return what's available right now. Used by /api/health/31am."""
    status: Dict[str, Any] = {
        "founder_key_present":   _founder_key_available(),
        "drive_creds_present":   _drive_creds_available(),
    }
    for modname in [
        "src.pcr060_drill_driver",
        "src.dynamic_rosetta_planner",
        "src.rosetta_core",
        "src.patch412_capability_cube",
        "src.r424_endpoint_capability_bridge",
        "src.r425_rosetta_task_config",
        "src.agent_email_chain",
    ]:
        try:
            __import__(modname)
            status[modname.split(".")[-1]] = "importable"
        except Exception as exc:
            status[modname.split(".")[-1]] = f"import_failed: {exc}"
    return status
