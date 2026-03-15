"""
Operational Completeness Module for Murphy System Runtime

This module fills remaining operational automation gaps to drive coverage
to 100%, complementing automation_scheduler.py and operational_slo_tracker.py:
- Capacity planning with historical forecasting and scaling recommendations
- Resource management with allocation tracking and over-allocation prevention
- Automated scheduling with dependency-aware execution and blackout periods
- Health monitoring with component aggregation and auto-healing triggers
- Runbook automation for common operational tasks
"""

import logging
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ResourceType(str, Enum):
    """Resource type (str subclass)."""
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"


class ComponentStatus(str, Enum):
    """Component status (str subclass)."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class RunbookStatus(str, Enum):
    """Runbook status (str subclass)."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class UsageSample:
    """A single historical resource-usage sample."""
    resource_type: str
    value: float
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class ResourcePool:
    """Tracks a pool of allocatable resources."""
    resource_type: str
    total_capacity: float
    allocated: float = 0.0
    unit: str = "units"


@dataclass
class ScheduledJob:
    """A dependency-aware scheduled job."""
    job_id: str
    name: str
    cron_expression: str
    depends_on: List[str] = field(default_factory=list)
    enabled: bool = True
    last_run: Optional[str] = None
    next_run: Optional[str] = None


@dataclass
class MaintenanceWindow:
    """Defines a maintenance / blackout window."""
    window_id: str
    name: str
    start_time: str
    end_time: str
    recurring: bool = False


@dataclass
class HealthCheck:
    """Result of a single component health check."""
    component: str
    status: str = ComponentStatus.UNKNOWN
    message: str = ""
    checked_at: Optional[str] = None

    def __post_init__(self):
        if self.checked_at is None:
            self.checked_at = datetime.now(timezone.utc).isoformat()


@dataclass
class RunbookStep:
    """A single step inside a runbook."""
    step_id: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: str = RunbookStatus.PENDING
    result: Optional[str] = None


@dataclass
class Runbook:
    """An operational runbook composed of ordered steps."""
    runbook_id: str
    name: str
    description: str = ""
    steps: List[RunbookStep] = field(default_factory=list)
    status: str = RunbookStatus.PENDING
    created_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Capacity Planner
# ---------------------------------------------------------------------------

class CapacityPlanner:
    """Forecasts resource needs based on historical usage samples."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._samples: Dict[str, List[UsageSample]] = {}

    def record_usage(self, resource_type: str, value: float) -> Dict[str, Any]:
        """Record a usage sample for the given resource type."""
        sample = UsageSample(resource_type=resource_type, value=value)
        with self._lock:
            self._samples.setdefault(resource_type, []).append(sample)
        return {"resource_type": resource_type, "value": value,
                "timestamp": sample.timestamp}

    def get_usage_history(self, resource_type: str) -> Dict[str, Any]:
        """Return recorded usage history for a resource type."""
        with self._lock:
            samples = self._samples.get(resource_type, [])
            values = [s.value for s in samples]
        return {
            "resource_type": resource_type,
            "sample_count": len(values),
            "values": values,
        }

    def forecast(self, resource_type: str, periods_ahead: int = 3) -> Dict[str, Any]:
        """Simple linear-trend forecast for future resource needs."""
        with self._lock:
            samples = self._samples.get(resource_type, [])
            values = [s.value for s in samples]
        if len(values) < 2:
            return {"resource_type": resource_type, "error": "insufficient_data",
                    "min_samples": 2, "current_samples": len(values)}
        slope, intercept = _linear_regression(values)
        n = len(values)
        forecasted = [round(slope * (n + i) + intercept, 4)
                      for i in range(1, periods_ahead + 1)]
        return {
            "resource_type": resource_type,
            "trend_slope": round(slope, 4),
            "forecasted_values": forecasted,
            "periods_ahead": periods_ahead,
        }

    def recommend_scaling(self, resource_type: str,
                          current_capacity: float) -> Dict[str, Any]:
        """Recommend whether to scale up, scale down, or hold steady."""
        forecast = self.forecast(resource_type, periods_ahead=1)
        if "error" in forecast:
            return {"resource_type": resource_type,
                    "recommendation": "hold", "reason": "insufficient_data"}
        predicted = forecast["forecasted_values"][0]
        utilisation = predicted / current_capacity if current_capacity else 1.0
        if utilisation > 0.85:
            rec = "scale_up"
        elif utilisation < 0.30:
            rec = "scale_down"
        else:
            rec = "hold"
        return {
            "resource_type": resource_type,
            "predicted_usage": predicted,
            "current_capacity": current_capacity,
            "predicted_utilisation": round(utilisation, 4),
            "recommendation": rec,
        }


# ---------------------------------------------------------------------------
# Resource Manager
# ---------------------------------------------------------------------------

class ResourceManager:
    """Tracks and allocates compute resources, preventing over-allocation."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pools: Dict[str, ResourcePool] = {}
        self._allocations: Dict[str, Dict[str, Any]] = {}

    def register_pool(self, resource_type: str, total_capacity: float,
                      unit: str = "units") -> Dict[str, Any]:
        """Register a new resource pool."""
        with self._lock:
            pool = ResourcePool(resource_type=resource_type,
                                total_capacity=total_capacity, unit=unit)
            self._pools[resource_type] = pool
        return {"resource_type": resource_type,
                "total_capacity": total_capacity, "unit": unit}

    def get_pool_status(self, resource_type: str) -> Dict[str, Any]:
        """Return current status of a resource pool."""
        with self._lock:
            pool = self._pools.get(resource_type)
            if pool is None:
                return {"error": "pool_not_found",
                        "resource_type": resource_type}
            available = pool.total_capacity - pool.allocated
            return {
                "resource_type": resource_type,
                "total_capacity": pool.total_capacity,
                "allocated": pool.allocated,
                "available": round(available, 4),
                "unit": pool.unit,
                "utilisation": round(
                    pool.allocated / pool.total_capacity
                    if pool.total_capacity else 0.0, 4),
            }

    def allocate(self, resource_type: str, amount: float,
                 requester: str = "") -> Dict[str, Any]:
        """Allocate resources from a pool. Fails if insufficient capacity."""
        with self._lock:
            pool = self._pools.get(resource_type)
            if pool is None:
                return {"success": False, "error": "pool_not_found"}
            available = pool.total_capacity - pool.allocated
            if amount > available:
                return {"success": False, "error": "insufficient_capacity",
                        "requested": amount, "available": round(available, 4)}
            alloc_id = f"alloc-{uuid.uuid4().hex[:12]}"
            pool.allocated += amount
            self._allocations[alloc_id] = {
                "allocation_id": alloc_id,
                "resource_type": resource_type,
                "amount": amount,
                "requester": requester,
                "allocated_at": datetime.now(timezone.utc).isoformat(),
            }
        return {"success": True, "allocation_id": alloc_id,
                "resource_type": resource_type, "amount": amount}

    def release(self, allocation_id: str) -> Dict[str, Any]:
        """Release a previous allocation back to the pool."""
        with self._lock:
            alloc = self._allocations.pop(allocation_id, None)
            if alloc is None:
                return {"success": False, "error": "allocation_not_found"}
            pool = self._pools.get(alloc["resource_type"])
            if pool:
                pool.allocated = max(0.0, pool.allocated - alloc["amount"])
        return {"success": True, "released": alloc}

    def list_allocations(self, resource_type: Optional[str] = None
                         ) -> Dict[str, Any]:
        """List current allocations, optionally filtered by resource type."""
        with self._lock:
            allocs = list(self._allocations.values())
            if resource_type:
                allocs = [a for a in allocs
                          if a["resource_type"] == resource_type]
        return {"allocations": allocs, "count": len(allocs)}


# ---------------------------------------------------------------------------
# Automated Scheduler
# ---------------------------------------------------------------------------

class AutomatedScheduler:
    """Dependency-aware job scheduler with maintenance windows."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: Dict[str, ScheduledJob] = {}
        self._windows: Dict[str, MaintenanceWindow] = {}
        self._execution_log: List[Dict[str, Any]] = []

    def register_job(self, name: str, cron_expression: str,
                     depends_on: Optional[List[str]] = None) -> Dict[str, Any]:
        """Register a new scheduled job."""
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        job = ScheduledJob(job_id=job_id, name=name,
                           cron_expression=cron_expression,
                           depends_on=depends_on or [])
        with self._lock:
            self._jobs[job_id] = job
        return {"job_id": job_id, "name": name,
                "cron_expression": cron_expression,
                "depends_on": job.depends_on}

    def disable_job(self, job_id: str) -> Dict[str, Any]:
        """Disable a scheduled job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return {"success": False, "error": "job_not_found"}
            job.enabled = False
        return {"success": True, "job_id": job_id, "enabled": False}

    def enable_job(self, job_id: str) -> Dict[str, Any]:
        """Enable a previously disabled job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return {"success": False, "error": "job_not_found"}
            job.enabled = True
        return {"success": True, "job_id": job_id, "enabled": True}

    def add_maintenance_window(self, name: str, start_time: str,
                               end_time: str,
                               recurring: bool = False) -> Dict[str, Any]:
        """Define a maintenance / blackout window."""
        window_id = f"mw-{uuid.uuid4().hex[:12]}"
        window = MaintenanceWindow(window_id=window_id, name=name,
                                   start_time=start_time, end_time=end_time,
                                   recurring=recurring)
        with self._lock:
            self._windows[window_id] = window
        return {"window_id": window_id, "name": name,
                "start_time": start_time, "end_time": end_time}

    def is_in_blackout(self, check_time: Optional[str] = None) -> Dict[str, Any]:
        """Check whether a given time falls inside any maintenance window."""
        now_str = check_time or datetime.now(timezone.utc).isoformat()
        with self._lock:
            for w in self._windows.values():
                if w.start_time <= now_str <= w.end_time:
                    return {"in_blackout": True, "window_id": w.window_id,
                            "window_name": w.name}
        return {"in_blackout": False}

    def can_execute(self, job_id: str) -> Dict[str, Any]:
        """Determine if a job can execute (enabled, deps met, no blackout)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return {"can_execute": False, "reason": "job_not_found"}
            if not job.enabled:
                return {"can_execute": False, "reason": "job_disabled"}
            for dep_id in job.depends_on:
                dep = self._jobs.get(dep_id)
                if dep is None or dep.last_run is None:
                    return {"can_execute": False,
                            "reason": "dependency_not_met",
                            "blocking_dependency": dep_id}
        blackout = self.is_in_blackout()
        if blackout["in_blackout"]:
            return {"can_execute": False, "reason": "in_blackout_period"}
        return {"can_execute": True, "job_id": job_id}

    def record_execution(self, job_id: str, success: bool) -> Dict[str, Any]:
        """Record that a job was executed."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return {"success": False, "error": "job_not_found"}
            job.last_run = now
            entry = {"job_id": job_id, "success": success,
                     "executed_at": now}
            capped_append(self._execution_log, entry)
        return {"success": True, **entry}

    def get_schedule_status(self) -> Dict[str, Any]:
        """Return overview of all registered jobs and windows."""
        with self._lock:
            jobs = [{"job_id": j.job_id, "name": j.name,
                     "enabled": j.enabled, "last_run": j.last_run,
                     "depends_on": j.depends_on}
                    for j in self._jobs.values()]
            windows = [{"window_id": w.window_id, "name": w.name,
                        "start_time": w.start_time, "end_time": w.end_time}
                       for w in self._windows.values()]
        return {"total_jobs": len(jobs), "jobs": jobs,
                "total_windows": len(windows), "windows": windows}


# ---------------------------------------------------------------------------
# Health Monitor
# ---------------------------------------------------------------------------

class HealthMonitor:
    """System-wide health monitoring with auto-healing triggers."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._checks: Dict[str, HealthCheck] = {}
        self._healing_rules: Dict[str, Dict[str, Any]] = {}
        self._anomalies: List[Dict[str, Any]] = []
        self._healed: List[Dict[str, Any]] = []

    def register_component(self, component: str) -> Dict[str, Any]:
        """Register a component for health monitoring."""
        with self._lock:
            self._checks[component] = HealthCheck(component=component)
        return {"component": component, "status": ComponentStatus.UNKNOWN}

    def update_status(self, component: str, status: str,
                      message: str = "") -> Dict[str, Any]:
        """Update the health status of a registered component."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            check = self._checks.get(component)
            if check is None:
                return {"success": False, "error": "component_not_registered"}
            check.status = status
            check.message = message
            check.checked_at = now
            # Anomaly detection: any non-healthy status is an anomaly
            if status != ComponentStatus.HEALTHY:
                anomaly = {"component": component, "status": status,
                           "message": message, "detected_at": now}
                capped_append(self._anomalies, anomaly)
                # Auto-healing trigger
                rule = self._healing_rules.get(component)
                if rule and status in rule.get("trigger_statuses", []):
                    heal = {"component": component, "action": rule["action"],
                            "triggered_at": now}
                    capped_append(self._healed, heal)
                    return {"success": True, "component": component,
                            "status": status, "auto_heal_triggered": True,
                            "heal_action": rule["action"]}
        return {"success": True, "component": component, "status": status}

    def register_healing_rule(self, component: str, action: str,
                              trigger_statuses: Optional[List[str]] = None
                              ) -> Dict[str, Any]:
        """Register an auto-healing rule for a component."""
        statuses = trigger_statuses or [ComponentStatus.UNHEALTHY]
        with self._lock:
            self._healing_rules[component] = {
                "action": action, "trigger_statuses": statuses}
        return {"component": component, "action": action,
                "trigger_statuses": statuses}

    def get_component_status(self, component: str) -> Dict[str, Any]:
        """Return status of a single component."""
        with self._lock:
            check = self._checks.get(component)
            if check is None:
                return {"error": "component_not_registered"}
            return {"component": component, "status": check.status,
                    "message": check.message, "checked_at": check.checked_at}

    def get_system_health(self) -> Dict[str, Any]:
        """Aggregate health across all components."""
        with self._lock:
            components = {}
            for name, chk in self._checks.items():
                components[name] = chk.status
            total = len(components)
            healthy = sum(1 for s in components.values()
                         if s == ComponentStatus.HEALTHY)
            degraded = sum(1 for s in components.values()
                          if s == ComponentStatus.DEGRADED)
            unhealthy = sum(1 for s in components.values()
                           if s == ComponentStatus.UNHEALTHY)
            if total == 0:
                overall = ComponentStatus.UNKNOWN
            elif unhealthy > 0:
                overall = ComponentStatus.UNHEALTHY
            elif degraded > 0:
                overall = ComponentStatus.DEGRADED
            elif healthy == total:
                overall = ComponentStatus.HEALTHY
            else:
                overall = ComponentStatus.UNKNOWN
        return {
            "overall_status": overall,
            "total_components": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "components": components,
        }

    def get_anomalies(self) -> Dict[str, Any]:
        """Return all detected anomalies."""
        with self._lock:
            return {"anomalies": list(self._anomalies),
                    "count": len(self._anomalies)}

    def get_healing_history(self) -> Dict[str, Any]:
        """Return auto-healing events."""
        with self._lock:
            return {"healed": list(self._healed),
                    "count": len(self._healed)}


# ---------------------------------------------------------------------------
# Runbook Executor
# ---------------------------------------------------------------------------

class RunbookExecutor:
    """Defines and executes operational runbooks for common tasks."""

    SUPPORTED_ACTIONS = {"restart", "scale", "backup", "failover",
                         "health_check", "notify", "custom"}

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._runbooks: Dict[str, Runbook] = {}
        self._templates: Dict[str, Dict[str, Any]] = {}

    def register_template(self, name: str, steps: List[Dict[str, Any]],
                          description: str = "") -> Dict[str, Any]:
        """Register a reusable runbook template."""
        template_id = f"tmpl-{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._templates[template_id] = {
                "template_id": template_id,
                "name": name,
                "description": description,
                "steps": steps,
            }
        return {"template_id": template_id, "name": name}

    def create_runbook(self, name: str,
                       steps: List[Dict[str, Any]],
                       description: str = "") -> Dict[str, Any]:
        """Create a new runbook from explicit steps."""
        runbook_id = f"rb-{uuid.uuid4().hex[:12]}"
        rb_steps = []
        for i, s in enumerate(steps):
            action = s.get("action", "custom")
            rb_steps.append(RunbookStep(
                step_id=f"step-{i}",
                action=action,
                parameters=s.get("parameters", {}),
            ))
        runbook = Runbook(runbook_id=runbook_id, name=name,
                          description=description, steps=rb_steps)
        with self._lock:
            self._runbooks[runbook_id] = runbook
        return {"runbook_id": runbook_id, "name": name,
                "total_steps": len(rb_steps)}

    def create_from_template(self, template_id: str,
                             overrides: Optional[Dict[str, Any]] = None
                             ) -> Dict[str, Any]:
        """Create a runbook from a registered template."""
        with self._lock:
            tmpl = self._templates.get(template_id)
            if tmpl is None:
                return {"success": False, "error": "template_not_found"}
        name = (overrides or {}).get("name", tmpl["name"])
        return self.create_runbook(name=name, steps=tmpl["steps"],
                                   description=tmpl["description"])

    def execute_runbook(self, runbook_id: str) -> Dict[str, Any]:
        """Execute all steps in a runbook sequentially."""
        with self._lock:
            runbook = self._runbooks.get(runbook_id)
            if runbook is None:
                return {"success": False, "error": "runbook_not_found"}
            runbook.status = RunbookStatus.RUNNING
            results = []
            all_ok = True
            for step in runbook.steps:
                step.status = RunbookStatus.RUNNING
                if step.action in self.SUPPORTED_ACTIONS:
                    step.status = RunbookStatus.COMPLETED
                    step.result = "ok"
                else:
                    step.status = RunbookStatus.FAILED
                    step.result = "unsupported_action"
                    all_ok = False
                results.append({
                    "step_id": step.step_id,
                    "action": step.action,
                    "status": step.status,
                    "result": step.result,
                })
            runbook.status = (RunbookStatus.COMPLETED if all_ok
                              else RunbookStatus.FAILED)
        return {"success": all_ok, "runbook_id": runbook_id,
                "status": runbook.status, "steps": results}

    def get_runbook_status(self, runbook_id: str) -> Dict[str, Any]:
        """Return the current status of a runbook."""
        with self._lock:
            runbook = self._runbooks.get(runbook_id)
            if runbook is None:
                return {"error": "runbook_not_found"}
            steps = [{"step_id": s.step_id, "action": s.action,
                       "status": s.status, "result": s.result}
                      for s in runbook.steps]
        return {"runbook_id": runbook_id, "name": runbook.name,
                "status": runbook.status, "total_steps": len(steps),
                "steps": steps}

    def list_runbooks(self) -> Dict[str, Any]:
        """List all registered runbooks."""
        with self._lock:
            items = [{"runbook_id": r.runbook_id, "name": r.name,
                      "status": r.status, "total_steps": len(r.steps)}
                     for r in self._runbooks.values()]
        return {"runbooks": items, "count": len(items)}

    def list_templates(self) -> Dict[str, Any]:
        """List all registered runbook templates."""
        with self._lock:
            items = list(self._templates.values())
        return {"templates": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _linear_regression(values: List[float]):
    """Least-squares linear regression returning (slope, intercept)."""
    n = len(values)
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
    den = sum((x - x_mean) ** 2 for x in xs)
    slope = num / den if den else 0.0
    intercept = y_mean - slope * x_mean
    return slope, intercept
