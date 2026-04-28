"""
PATCH-117 + PATCH-115b — src/prod_ops_agent.py
Murphy System — Production Ops Agent (inherits AgentBase / RosettaSoul)
"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.prod_ops")


class ProdOpsAgent(AgentBase):
    """
    PATCH-117: Production Operations automation agent.
    Carries RosettaSoul via AgentBase inheritance.
    """

    HEALTH_THRESHOLDS = {
        "cpu_percent":  85.0,
        "ram_percent":  85.0,
        "disk_percent": 90.0,
        "latency_ms":  500.0,
        "error_rate":    0.05,
    }

    def __init__(self):
        super().__init__("prod_ops")

    def act(self, signal: dict) -> dict:
        """AgentBase interface — route signal to correct prod_ops task."""
        signal_type = signal.get("signal_type", "")
        if signal_type == "git":
            return self.handle_git_event(signal)
        elif signal_type in ("telemetry", "incident"):
            return self.handle_incident(signal)
        else:
            return self.health_watchdog()

    def health_watchdog(self) -> Dict:
        """Check system health. Return status + any auto-heal actions taken."""
        from src.signal_collector import get_collector
        from src.workflow_dag import build_dag, task_node, get_executor

        health_result = {"timestamp": datetime.now(timezone.utc).isoformat(), "checks": [], "actions": []}

        # Pull hardware telemetry
        try:
            from src.hardware_telemetry import HardwareTelemetryEngine
            tele = HardwareTelemetryEngine()
            snap = tele.snapshot()
            # HardwareSnapshot is a dataclass — use attributes not .get()
            cpu = getattr(getattr(snap, "cpu", None), "utilization_percent", 0) or 0
            ram = getattr(getattr(snap, "ram", None), "percent", 0) or 0
            grade = getattr(snap, "health_grade", "?")

            health_result["checks"].append({"metric": "cpu", "value": cpu, "ok": cpu < self.HEALTH_THRESHOLDS["cpu_percent"]})
            health_result["checks"].append({"metric": "ram", "value": ram, "ok": ram < self.HEALTH_THRESHOLDS["ram_percent"]})
            health_result["grade"] = grade

            # Signal if threshold breached
            if cpu > self.HEALTH_THRESHOLDS["cpu_percent"]:
                get_collector().ingest_hardware_alert("cpu_percent", cpu, self.HEALTH_THRESHOLDS["cpu_percent"])
                health_result["actions"].append("alert_high_cpu")
            if ram > self.HEALTH_THRESHOLDS["ram_percent"]:
                get_collector().ingest_hardware_alert("ram_percent", ram, self.HEALTH_THRESHOLDS["ram_percent"])
                health_result["actions"].append("alert_high_ram")
        except Exception as exc:
            health_result["checks"].append({"metric": "telemetry", "error": str(exc)})

        # Check murphy service
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "murphy-production"],
                capture_output=True, text=True, timeout=5
            )
            svc_ok = result.stdout.strip() == "active"
            health_result["checks"].append({"metric": "murphy_service", "value": result.stdout.strip(), "ok": svc_ok})
        except Exception as exc:
            health_result["checks"].append({"metric": "murphy_service", "error": str(exc)})

        health_result["overall"] = "healthy" if all(
            c.get("ok", True) for c in health_result["checks"]
        ) else "degraded"

        return health_result

    def handle_incident(self, signal: Dict) -> Dict:
        """Classify and respond to an incident signal."""
        from src.workflow_dag import build_dag, task_node, get_executor

        metric = signal.get("raw_payload", {}).get("metric", "unknown")
        value = signal.get("raw_payload", {}).get("value", 0)
        intent = signal.get("intent_hint", "")

        # Build incident response DAG
        dag = build_dag(
            name=f"incident_{metric}",
            description=f"Auto-incident response: {intent[:80]}",
            domain="prod_ops",
            stake="high",
            account="murphy-prodops",
        )
        dag.add_node(task_node("classify_incident", "incident_classifier",
                               args={"metric": metric, "value": value}))
        dag.add_node(task_node("run_runbook", "execute_runbook_steps",
                               depends_on=["classify_incident"]))
        dag.add_node(task_node("send_alert", "notify_oncall",
                               args={"channel": "prodops", "severity": "high"},
                               depends_on=["classify_incident"]))
        dag.add_node(task_node("verify_resolution", "check_metric_post_action",
                               depends_on=["run_runbook"]))
        dag.add_node(task_node("log_outcome", "record_incident_to_pattern_lib",
                               depends_on=["verify_resolution"]))

        result = get_executor().execute(dag)
        return {"dag_id": dag.dag_id, "status": result.status, "metric": metric}

    def trigger_self_patch(self, dry_run: bool = True) -> Dict:
        """Trigger Murphy's autonomous self-improvement cycle."""
        try:
            from src.self_modification import self_mod
            result = self_mod.run_autonomous_cycle(
                max_patches=1, min_priority="MEDIUM", dry_run=dry_run
            )
            return {"triggered": True, "dry_run": dry_run, "result": result}
        except Exception as exc:
            logger.error("Self-patch trigger failed: %s", exc)
            return {"triggered": False, "error": str(exc)}

    def handle_git_event(self, signal: Dict) -> Dict:
        """Respond to a git push/PR event — trigger deploy workflow."""
        from src.workflow_dag import build_dag, task_node, get_executor

        payload = signal.get("raw_payload", {})
        branch = payload.get("branch", "unknown")
        author = payload.get("author", "unknown")
        message = payload.get("message", "")

        stake = "high" if branch in ("main", "master") else "low"
        dag = build_dag(f"deploy_{branch}", f"Deploy: {message[:60]}",
                        domain="prod_ops", stake=stake, account=author)
        dag.add_node(task_node("run_tests", "execute_test_suite"))
        dag.add_node(task_node("build", "build_application", depends_on=["run_tests"]))
        dag.add_node(task_node("deploy", "deploy_to_production",
                               args={"branch": branch}, depends_on=["build"]))
        dag.add_node(task_node("health_check", "verify_post_deploy_health",
                               depends_on=["deploy"]))
        dag.add_node(task_node("log_deploy", "record_deployment_to_pattern_lib",
                               depends_on=["health_check"]))

        result = get_executor().execute(dag)
        return {"dag_id": dag.dag_id, "status": result.status, "branch": branch}


# ── Singleton ──────────────────────────────────────────────────────────────────
    def request_automation(self, description: str, priority: str = "normal",
                           context: dict = None) -> dict:
        """
        PATCH-135b: Request a new automation from the NL pipeline.
        Called when prod_ops detects a recurring ops pattern needing automation.
        """
        try:
            from src.automation_request import request_automation as _req
            return _req(
                description=description,
                account_id="cpost@murphy.systems",
                requester="prod_ops",
                priority=priority,
                context=context or {},
                auto_schedule=True,
            )
        except Exception as e:
            import logging
            logging.getLogger("murphy.prod_ops").error("request_automation failed: %s", e)
            return {"success": False, "error": str(e), "requester": "prod_ops"}

_prod_ops: Optional[ProdOpsAgent] = None

def get_prod_ops() -> ProdOpsAgent:
    global _prod_ops
    if _prod_ops is None:
        _prod_ops = ProdOpsAgent()
    return _prod_ops
