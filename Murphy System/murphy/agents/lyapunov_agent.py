# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""LyapunovAgent — MURPHY-AGENT-LYAPUNOV-001

Owner: Platform Engineering
Dep: AgentOutput schema, Rosetta org lookup, BAT sealing

Stability monitoring agent.  Computes a stability score (0.0–1.0) from
drift between current telemetry and the historical baseline.

Thresholds:
  score >= 0.7  → Stable (no alert)
  0.4 <= score < 0.7 → Drift alert (Matrix + BAT)
  score < 0.4  → Critical alert (HITL required, Executive authority)

Input:
  telemetry_stream (list of metric dicts), historical_baseline (dict)
Output:
  AgentOutput with content_type=compliance_report

Error codes: LYAPUNOV-ERR-001 through LYAPUNOV-ERR-004.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from murphy.rosetta.org_lookup import (
    get_rosetta_state_hash,
    resolve_hitl_authority,
    _post_matrix_alert,
    _seal_to_bat,
    OrgChartLookupError,
    BATSealError,
)
from murphy.schemas.agent_output import AgentOutput, ContentType, RenderType

logger = logging.getLogger(__name__)

# Stability thresholds
STABLE_THRESHOLD = 0.7
CRITICAL_THRESHOLD = 0.4


class LyapunovAgent:
    """Telemetry stability agent using Lyapunov-inspired drift detection.

    Computes stability_score from the mean squared drift between current
    telemetry and the historical baseline.  The score is clamped to [0, 1].
    """

    AGENT_NAME = "LyapunovAgent"

    def __init__(self, *, org_node_id: str = "platform-engineering") -> None:
        self.agent_id = f"lyapunov-{uuid.uuid4().hex[:8]}"
        self.org_node_id = org_node_id

    def run(
        self,
        telemetry_stream: List[Dict[str, Any]],
        historical_baseline: Dict[str, Any],
        org_chart: Dict[str, Any] | None = None,
    ) -> AgentOutput:
        """Execute the Lyapunov agent.

        Args:
            telemetry_stream: Current telemetry metrics.
            historical_baseline: Expected metric ranges/values.
            org_chart: Org chart for HITL authority resolution (needed
                       for critical alerts).

        Returns:
            AgentOutput with compliance_report content.
        """
        try:
            # Compute stability
            stability_score, drift_metrics = self._compute_stability(
                telemetry_stream, historical_baseline,
            )

            # Determine alert level
            if stability_score < CRITICAL_THRESHOLD:
                alert_level = "critical"
                recommended_action = (
                    "Immediate intervention required — system stability critically degraded"
                )
            elif stability_score < STABLE_THRESHOLD:
                alert_level = "warning"
                recommended_action = (
                    "Investigate drift metrics — stability below acceptable threshold"
                )
            else:
                alert_level = "stable"
                recommended_action = "No action required — system stable"

            report = {
                "stability_score": round(stability_score, 4),
                "drift_metrics": drift_metrics,
                "alert_level": alert_level,
                "recommended_action": recommended_action,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "telemetry_count": len(telemetry_stream),
            }

            state_hash = get_rosetta_state_hash()

            # Alert handling
            hitl_required = False
            hitl_authority_node_id = None

            if alert_level == "critical":
                hitl_required = True
                # Resolve HITL authority for critical alerts
                if org_chart:
                    try:
                        hitl_authority_node_id = resolve_hitl_authority(
                            action_type="lyapunov_critical_alert",
                            risk_level="critical",
                            org_chart=org_chart,
                        )
                    except (OrgChartLookupError, BATSealError) as exc:
                        logger.error("LYAPUNOV-ERR-003: %s", exc)
                        hitl_authority_node_id = "executive-fallback"
                else:
                    hitl_authority_node_id = "executive-fallback"

                _post_matrix_alert(
                    f"🚨 CRITICAL STABILITY ALERT: score={stability_score:.4f} "
                    f"— {recommended_action}"
                )

            elif alert_level == "warning":
                _post_matrix_alert(
                    f"⚠️ DRIFT ALERT: stability_score={stability_score:.4f} "
                    f"— {recommended_action}"
                )

            # BAT seal for all non-stable results
            if alert_level != "stable":
                try:
                    _seal_to_bat(
                        action=f"lyapunov_{alert_level}",
                        resource="telemetry_stability",
                        metadata=report,
                    )
                except BATSealError as exc:  # LYAPUNOV-ERR-004
                    logger.error("LYAPUNOV-ERR-004: BAT seal failed — %s", exc)
                    # Continue — alert is still valid even if seal fails

            return AgentOutput(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path="stability_report.json",
                content_type=ContentType.COMPLIANCE_REPORT,
                content=json.dumps(report, indent=2, default=str),
                lang="json",
                depends_on=[],
                org_node_id=self.org_node_id,
                rosetta_state_hash=state_hash,
                render_type=RenderType.DOCUMENT,
                hitl_required=hitl_required,
                hitl_authority_node_id=hitl_authority_node_id,
                bat_seal_required=alert_level != "stable",
            )

        except Exception as exc:  # LYAPUNOV-ERR-001
            logger.error("LYAPUNOV-ERR-001: %s", exc)
            return AgentOutput.from_error(
                agent_id=self.agent_id,
                agent_name=self.AGENT_NAME,
                file_path="stability_report.json",
                org_node_id=self.org_node_id,
                error_message=f"LYAPUNOV-ERR-001: {exc}",
            )

    # ------------------------------------------------------------------
    # Core computation  (LYAPUNOV-COMPUTE-001)
    # ------------------------------------------------------------------

    def _compute_stability(
        self,
        telemetry: List[Dict[str, Any]],
        baseline: Dict[str, Any],
    ) -> tuple[float, List[Dict[str, Any]]]:
        """Compute stability score from telemetry vs baseline.

        Uses mean squared drift: score = 1.0 - clamp(mean_drift, 0, 1).

        Returns (stability_score, drift_metrics_list).
        """
        if not telemetry:
            return 1.0, []  # No telemetry = no drift detected

        baseline_values = baseline.get("metrics", {})
        if not baseline_values:
            return 1.0, []  # No baseline = assume stable

        drift_metrics: List[Dict[str, Any]] = []
        total_drift = 0.0
        count = 0

        for metric in telemetry:
            name = metric.get("name", "")
            value = metric.get("value")
            if name and value is not None and name in baseline_values:
                expected = baseline_values[name]
                try:
                    current = float(value)
                    target = float(expected)
                    if target != 0:
                        drift = abs(current - target) / abs(target)
                    else:
                        drift = abs(current)
                    drift_metrics.append({
                        "metric": name,
                        "current": current,
                        "baseline": target,
                        "drift": round(drift, 4),
                    })
                    total_drift += drift
                    count += 1
                except (TypeError, ValueError):
                    continue

        if count == 0:
            return 1.0, drift_metrics

        mean_drift = total_drift / count
        stability_score = max(0.0, min(1.0, 1.0 - mean_drift))
        return stability_score, drift_metrics
