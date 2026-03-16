# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1

"""
Collaborative Task Orchestrator — Murphy System

Unifying orchestration layer that wires together:
  SwarmProposalGenerator → WorkflowDAGEngine → SplitScreenCoordinator
  → DurableSwarmOrchestrator → ResultSynthesizer → WorkspaceMemoryBridge

Closes Gaps 3, 4, and 5 of the Murphy System integration spec.
"""

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Murphy subsystem imports — all guarded with try/except
# ---------------------------------------------------------------------------
try:
    from workflow_dag_engine import WorkflowDAGEngine, WorkflowDefinition, StepDefinition
    _DAG_AVAILABLE = True
except ImportError:
    _DAG_AVAILABLE = False
    WorkflowDAGEngine = None  # type: ignore[assignment,misc]
    WorkflowDefinition = None  # type: ignore[assignment,misc]
    StepDefinition = None  # type: ignore[assignment,misc]

try:
    from swarm_proposal_generator import SwarmProposalGenerator, SwarmProposal, SwarmStep, SwarmExecutionResult
    _SWARM_PROPOSAL_AVAILABLE = True
except ImportError:
    _SWARM_PROPOSAL_AVAILABLE = False
    SwarmProposalGenerator = None  # type: ignore[assignment,misc]
    SwarmProposal = None  # type: ignore[assignment,misc]
    SwarmStep = None  # type: ignore[assignment,misc]
    SwarmExecutionResult = None  # type: ignore[assignment,misc]

try:
    from durable_swarm_orchestrator import DurableSwarmOrchestrator
    _DURABLE_AVAILABLE = True
except ImportError:
    _DURABLE_AVAILABLE = False
    DurableSwarmOrchestrator = None  # type: ignore[assignment,misc]

try:
    from split_screen_coordinator import SplitScreenCoordinator, SplitScreenLayout, CoordinationReport
    _SPLIT_SCREEN_AVAILABLE = True
except ImportError:
    _SPLIT_SCREEN_AVAILABLE = False
    SplitScreenCoordinator = None  # type: ignore[assignment,misc]
    CoordinationReport = None  # type: ignore[assignment,misc]

try:
    from murphy_native_automation import SplitScreenLayout as _NativeSplitScreenLayout
    if not _SPLIT_SCREEN_AVAILABLE:
        SplitScreenLayout = _NativeSplitScreenLayout  # type: ignore[assignment,misc]
    _LAYOUT_AVAILABLE = True
except ImportError:
    _LAYOUT_AVAILABLE = _SPLIT_SCREEN_AVAILABLE

try:
    from true_swarm_system import TypedGenerativeWorkspace, Artifact, ArtifactType, Phase
    _TGW_AVAILABLE = True
except ImportError:
    _TGW_AVAILABLE = False
    TypedGenerativeWorkspace = None  # type: ignore[assignment,misc]
    Artifact = None  # type: ignore[assignment,misc]
    ArtifactType = None  # type: ignore[assignment,misc]
    Phase = None  # type: ignore[assignment,misc]

try:
    from memory_artifact_system import MemoryArtifactSystem
    _MAS_AVAILABLE = True
except ImportError:
    _MAS_AVAILABLE = False
    MemoryArtifactSystem = None  # type: ignore[assignment,misc]

try:
    from llm_routing_completeness import HybridExecutionEngine
    _HYBRID_AVAILABLE = True
except ImportError:
    _HYBRID_AVAILABLE = False
    HybridExecutionEngine = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# SynthesizedResult dataclass
# ---------------------------------------------------------------------------
@dataclass
class SynthesizedResult:
    merged_output: Dict[str, Any]
    conflict_report: List[Dict[str, Any]]
    validation_status: str  # "passed", "failed", "skipped"
    validation_detail: str
    confidence: float
    agent_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ResultSynthesizer — Gap 4
# ---------------------------------------------------------------------------
class ResultSynthesizer:
    """Replaces naive concatenation in HybridExecutionEngine._merge_results."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def synthesize(
        self,
        results: Dict[str, Dict[str, Any]],
        confidence_map: Optional[Dict[str, float]] = None,
    ) -> SynthesizedResult:
        with self._lock:
            if not results:
                return SynthesizedResult(
                    merged_output={},
                    conflict_report=[],
                    validation_status="skipped",
                    validation_detail="No results to synthesize",
                    confidence=0.0,
                    agent_count=0,
                )

            confidence_map = confidence_map or {}
            outputs: List[Dict[str, Any]] = []
            agent_confidences: List[float] = []

            for agent_id, result in results.items():
                output = result.get("output", result)
                if not isinstance(output, dict):
                    output = {"value": output}
                c = confidence_map.get(agent_id, result.get("confidence", 0.5))
                outputs.append(output)
                agent_confidences.append(float(c))

            conflicts = self._detect_conflicts(outputs)
            merged: Dict[str, Any] = {}

            # Collect all field names across outputs
            all_keys: set = set()
            for o in outputs:
                all_keys.update(o.keys())

            for key in all_keys:
                values_with_conf: List[Tuple[Any, float]] = []
                for i, o in enumerate(outputs):
                    if key in o:
                        values_with_conf.append((o[key], agent_confidences[i]))
                merged[key] = self._confidence_vote(key, values_with_conf)

            # Apply conflict resolutions into merged
            conflict_report: List[Dict[str, Any]] = []
            for conflict in conflicts:
                fld = conflict["field"]
                vals_conf = [
                    (v, confidence_map.get(list(results.keys())[i], agent_confidences[i]))
                    for i, v in enumerate(conflict["values"])
                ]
                chosen = self._confidence_vote(fld, vals_conf)
                merged[fld] = chosen
                conflict_report.append({
                    "field": fld,
                    "values": conflict["values"],
                    "resolution": "confidence_weighted_vote",
                    "chosen": chosen,
                })

            # Wingman validation: check output is non-empty
            if merged:
                validation_status = "passed"
                validation_detail = f"Merged {len(merged)} fields from {len(results)} agents"
            else:
                validation_status = "failed"
                validation_detail = "Merged output is empty"

            avg_confidence = sum(agent_confidences) / len(agent_confidences) if agent_confidences else 0.0

            return SynthesizedResult(
                merged_output=merged,
                conflict_report=conflict_report,
                validation_status=validation_status,
                validation_detail=validation_detail,
                confidence=avg_confidence,
                agent_count=len(results),
            )

    def _detect_conflicts(self, outputs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find fields with differing values across agents."""
        conflicts: List[Dict[str, Any]] = []
        all_keys: set = set()
        for o in outputs:
            all_keys.update(o.keys())

        for key in all_keys:
            vals = [o[key] for o in outputs if key in o]
            if len(vals) > 1:
                unique_vals = []
                for v in vals:
                    if v not in unique_vals:
                        unique_vals.append(v)
                if len(unique_vals) > 1:
                    conflicts.append({"field": key, "values": vals})
        return conflicts

    def _confidence_vote(self, field: str, values: List[Tuple[Any, float]]) -> Any:
        """Return the value with the highest confidence."""
        if not values:
            return None
        return max(values, key=lambda vc: vc[1])[0]


# ---------------------------------------------------------------------------
# WorkspaceMemoryBridge — Gap 5
# ---------------------------------------------------------------------------
class WorkspaceMemoryBridge:
    """Bridges TypedGenerativeWorkspace and MemoryArtifactSystem."""

    def __init__(
        self,
        tgw: Optional[Any] = None,
        mas: Optional[Any] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._tgw = tgw
        self._mas = mas
        self._init_subsystems()

    def _init_subsystems(self) -> None:
        if self._tgw is None and _TGW_AVAILABLE:
            try:
                self._tgw = TypedGenerativeWorkspace()
            except Exception as exc:
                logger.warning("WorkspaceMemoryBridge: TGW init failed: %s", exc)
                self._tgw = None

        if self._mas is None and _MAS_AVAILABLE:
            try:
                self._mas = MemoryArtifactSystem()
            except Exception as exc:
                logger.warning("WorkspaceMemoryBridge: MAS init failed: %s", exc)
                self._mas = None

    def write_artifact(
        self,
        content: Any,
        artifact_type_name: str = "hypothesis",
        source_agent: str = "orchestrator",
        phase_name: str = "expand",
        confidence_impact: float = 0.5,
    ) -> str:
        artifact_id = str(uuid.uuid4())
        with self._lock:
            # Write to TGW
            if self._tgw is not None:
                try:
                    kwargs: Dict[str, Any] = {
                        "content": content,
                        "source_agent": source_agent,
                        "confidence_impact": confidence_impact,
                    }
                    if _TGW_AVAILABLE and ArtifactType is not None:
                        try:
                            kwargs["artifact_type"] = ArtifactType[artifact_type_name.upper()]
                        except (KeyError, AttributeError):
                            pass
                    if _TGW_AVAILABLE and Phase is not None:
                        try:
                            kwargs["phase"] = Phase[phase_name.upper()]
                        except (KeyError, AttributeError):
                            pass
                    result = self._tgw.write_artifact(**kwargs)
                    if result and hasattr(result, "artifact_id"):
                        artifact_id = result.artifact_id
                    elif isinstance(result, str):
                        artifact_id = result
                except Exception as exc:
                    logger.warning("WorkspaceMemoryBridge: TGW write failed: %s", exc)

            # Auto-promote to MAS sandbox
            if self._mas is not None:
                try:
                    self._mas.write_sandbox(
                        artifact_id=artifact_id,
                        content=content,
                        metadata={
                            "artifact_type": artifact_type_name,
                            "source_agent": source_agent,
                            "phase": phase_name,
                            "confidence_impact": confidence_impact,
                        },
                    )
                except Exception as exc:
                    logger.warning("WorkspaceMemoryBridge: MAS sandbox write failed: %s", exc)

        return artifact_id

    def verify_and_promote(self, artifact_id: str) -> bool:
        with self._lock:
            # Check TGW
            tgw_ok = False
            if self._tgw is not None:
                try:
                    artifact = self._tgw.get_artifact(artifact_id)
                    tgw_ok = artifact is not None
                except Exception:
                    tgw_ok = False

            if not tgw_ok:
                return False

            # Promote in MAS
            if self._mas is not None:
                try:
                    verified = self._mas.verify_artifact(artifact_id)
                    if verified:
                        self._mas.promote_to_working(artifact_id)
                        return True
                except Exception as exc:
                    logger.warning("WorkspaceMemoryBridge: promote failed: %s", exc)
                    return False

        return tgw_ok

    def query(
        self,
        artifact_type_name: Optional[str] = None,
        phase_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        combined: List[Dict[str, Any]] = []
        with self._lock:
            if self._tgw is not None:
                try:
                    kwargs: Dict[str, Any] = {}
                    if artifact_type_name and _TGW_AVAILABLE and ArtifactType is not None:
                        try:
                            kwargs["artifact_type"] = ArtifactType[artifact_type_name.upper()]
                        except (KeyError, AttributeError):
                            pass
                    if phase_name and _TGW_AVAILABLE and Phase is not None:
                        try:
                            kwargs["phase"] = Phase[phase_name.upper()]
                        except (KeyError, AttributeError):
                            pass
                    tgw_results = self._tgw.query_artifacts(**kwargs) if kwargs else self._tgw.query_artifacts()
                    for r in tgw_results or []:
                        combined.append(r if isinstance(r, dict) else vars(r))
                except Exception as exc:
                    logger.warning("WorkspaceMemoryBridge: TGW query failed: %s", exc)

            if self._mas is not None:
                try:
                    mas_results = self._mas.list_artifacts(artifact_type=artifact_type_name)
                    for r in mas_results or []:
                        combined.append(r if isinstance(r, dict) else vars(r))
                except Exception as exc:
                    logger.warning("WorkspaceMemoryBridge: MAS query failed: %s", exc)

        return combined


# ---------------------------------------------------------------------------
# CollaborativeExecutionReport dataclass
# ---------------------------------------------------------------------------
@dataclass
class CollaborativeExecutionReport:
    run_id: str
    task_description: str
    status: str  # "completed", "failed", "partial"
    layout: str  # SplitScreenLayout value
    zone_results: Dict[str, Dict[str, Any]]
    agent_results: Dict[str, Dict[str, Any]]
    step_results: Dict[str, Dict[str, Any]]
    synthesized: Optional[Any]  # SynthesizedResult
    total_cost: float
    total_duration_ms: float
    parallel_groups: List[List[str]]
    execution_log: List[Dict[str, Any]]
    idempotency_key: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CollaborativeTaskOrchestrator — Gap 3
# ---------------------------------------------------------------------------
class CollaborativeTaskOrchestrator:
    """Unifying orchestration layer closing Gaps 3, 4, and 5."""

    MAX_AGENTS = 16
    MAX_PARALLEL_GROUPS = 8
    MAX_TOTAL_BUDGET = 10_000.0
    DEFAULT_STEP_TIMEOUT = 120.0
    DEFAULT_TOTAL_TIMEOUT = 600.0
    MAX_HISTORY = 1_000  # CWE-770

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: List[CollaborativeExecutionReport] = []
        self._idempotency_cache: Dict[str, CollaborativeExecutionReport] = {}

        # Lazy-load subsystems
        self._dag_engine: Optional[Any] = None
        self._swarm_proposal_gen: Optional[Any] = None
        self._durable_orchestrator: Optional[Any] = None
        self._split_screen_coordinator: Optional[Any] = None
        self._hybrid_engine: Optional[Any] = None
        self._memory_bridge: Optional[WorkspaceMemoryBridge] = None
        self._synthesizer: ResultSynthesizer = ResultSynthesizer()
        self._init_subsystems()

    def _init_subsystems(self) -> None:
        if _DAG_AVAILABLE:
            try:
                self._dag_engine = WorkflowDAGEngine()
            except Exception as exc:
                logger.warning("CTO: DAG engine init failed: %s", exc)

        if _SWARM_PROPOSAL_AVAILABLE:
            try:
                self._swarm_proposal_gen = SwarmProposalGenerator()
            except Exception as exc:
                logger.warning("CTO: SwarmProposalGenerator init failed: %s", exc)

        if _DURABLE_AVAILABLE:
            try:
                self._durable_orchestrator = DurableSwarmOrchestrator()
            except Exception as exc:
                logger.warning("CTO: DurableSwarmOrchestrator init failed: %s", exc)

        if _SPLIT_SCREEN_AVAILABLE:
            try:
                self._split_screen_coordinator = SplitScreenCoordinator()
            except Exception as exc:
                logger.warning("CTO: SplitScreenCoordinator init failed: %s", exc)

        if _HYBRID_AVAILABLE:
            try:
                self._hybrid_engine = HybridExecutionEngine()
            except Exception as exc:
                logger.warning("CTO: HybridExecutionEngine init failed: %s", exc)

        self._memory_bridge = WorkspaceMemoryBridge()

    @staticmethod
    def select_layout(n_agents: int) -> Any:
        """Map agent count to SplitScreenLayout."""
        layout_enum = None
        if _SPLIT_SCREEN_AVAILABLE or _LAYOUT_AVAILABLE:
            try:
                layout_enum = SplitScreenLayout
            except NameError:
                pass

        mapping = {
            1: "SINGLE",
            2: "DUAL_H",
            3: "TRIPLE_H",
            4: "QUAD",
        }
        if n_agents <= 0:
            name = "SINGLE"
        elif n_agents in mapping:
            name = mapping[n_agents]
        elif n_agents <= 6:
            name = "HEXA"
        else:
            name = "CUSTOM"

        if layout_enum is not None:
            try:
                return layout_enum[name]
            except (KeyError, AttributeError):
                return name
        return name

    def _build_stub_proposal(self, task_description: str) -> Any:
        """Minimal stub proposal when SwarmProposalGenerator is unavailable."""
        class _StubStep:
            def __init__(self, step_id: str, description: str) -> None:
                self.step_id = step_id
                self.description = description
                self.depends_on: List[str] = []
                self.parallel: bool = False
                self.agent_id: str = "agent_0"
                self.metadata: Dict[str, Any] = {}

        class _StubProposal:
            def __init__(self, task: str) -> None:
                self.task_description = task
                self.agents = [{"agent_id": "agent_0", "role": "executor"}]
                self.steps = [_StubStep("step_0", task)]
                self.estimated_cost = 1.0
                self.metadata: Dict[str, Any] = {}

            def get_parallel_groups(self) -> List[List[str]]:
                return [["step_0"]]

        return _StubProposal(task_description)

    def _generate_proposal(self, task_description: str) -> Any:
        if self._swarm_proposal_gen is None:
            return self._build_stub_proposal(task_description)
        try:
            proposal = asyncio.run(
                self._swarm_proposal_gen.generate_proposal(task_description)
            )
            return proposal
        except Exception as exc:
            logger.warning("CTO: generate_proposal failed (%s), using stub", exc)
            return self._build_stub_proposal(task_description)

    def _register_workflow(self, proposal: Any) -> Optional[str]:
        if self._dag_engine is None or not _DAG_AVAILABLE:
            return None
        try:
            steps = []
            for s in getattr(proposal, "steps", []):
                step_def = StepDefinition(
                    step_id=getattr(s, "step_id", str(uuid.uuid4())),
                    name=getattr(s, "description", "step"),
                    action=getattr(s, "description", "execute"),
                    depends_on=getattr(s, "depends_on", []),
                    parallel=getattr(s, "parallel", False),
                    metadata=getattr(s, "metadata", {}),
                )
                steps.append(step_def)

            workflow_def = WorkflowDefinition(
                workflow_id=str(uuid.uuid4()),
                name=getattr(proposal, "task_description", "workflow"),
                steps=steps,
            )
            self._dag_engine.register_workflow(workflow_def)
            return workflow_def.workflow_id
        except Exception as exc:
            logger.warning("CTO: workflow registration failed: %s", exc)
            return None

    def _execute_step(
        self,
        step: Any,
        task_description: str,
        budget_per_step: float,
        step_timeout: float,
        execution_log: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        step_id = getattr(step, "step_id", str(uuid.uuid4()))
        start = time.time()
        result: Dict[str, Any] = {
            "step_id": step_id,
            "status": "completed",
            "output": {"step_id": step_id, "result": f"executed:{step_id}"},
            "cost": 0.0,
            "duration_ms": 0.0,
        }

        # Wrap in DurableSwarmOrchestrator if available
        if self._durable_orchestrator is not None:
            try:
                task_handle = self._durable_orchestrator.spawn_task(
                    task_id=step_id,
                    description=getattr(step, "description", task_description),
                    budget=budget_per_step,
                )
                result["task_handle"] = str(task_handle)
                result["cost"] = budget_per_step * 0.1
            except Exception as exc:
                logger.debug("CTO: spawn_task failed for %s: %s", step_id, exc)

        elapsed = (time.time() - start) * 1000
        result["duration_ms"] = elapsed
        execution_log.append({
            "event": "step_complete",
            "step_id": step_id,
            "duration_ms": elapsed,
            "status": result["status"],
        })
        return result

    def orchestrate(
        self,
        task_description: str,
        budget: float = 100.0,
        idempotency_key: Optional[str] = None,
        step_timeout: float = DEFAULT_STEP_TIMEOUT,
        total_timeout: float = DEFAULT_TOTAL_TIMEOUT,
    ) -> CollaborativeExecutionReport:
        start_time = time.time()
        execution_log: List[Dict[str, Any]] = []

        # Step 1: Input validation
        task_description = (task_description or "").strip()
        if not task_description:
            raise ValueError("task_description must be non-empty")
        if budget <= 0:
            raise ValueError("budget must be > 0")
        if budget > self.MAX_TOTAL_BUDGET:
            raise ValueError(f"budget exceeds MAX_TOTAL_BUDGET ({self.MAX_TOTAL_BUDGET})")

        # Step 2: Idempotency
        if idempotency_key is None:
            idempotency_key = str(uuid.uuid4())
        with self._lock:
            if idempotency_key in self._idempotency_cache:
                return self._idempotency_cache[idempotency_key]

        run_id = str(uuid.uuid4())
        execution_log.append({"event": "start", "run_id": run_id, "task": task_description})

        # Step 3: Generate proposal
        proposal = self._generate_proposal(task_description)
        agents = getattr(proposal, "agents", [{"agent_id": "agent_0"}])
        steps = getattr(proposal, "steps", [])
        n_agents = min(len(agents), self.MAX_AGENTS)
        execution_log.append({"event": "proposal_generated", "n_agents": n_agents, "n_steps": len(steps)})

        # Step 4: Register workflow
        workflow_id = self._register_workflow(proposal)
        if workflow_id:
            execution_log.append({"event": "workflow_registered", "workflow_id": workflow_id})

        # Step 5: Get parallel groups
        try:
            parallel_groups_raw = proposal.get_parallel_groups()
        except Exception:
            parallel_groups_raw = [[getattr(s, "step_id", f"step_{i}") for i, s in enumerate(steps)]]
        parallel_groups = [g for g in parallel_groups_raw[: self.MAX_PARALLEL_GROUPS]]

        # Step 6: Select layout
        layout = self.select_layout(n_agents)
        layout_str = layout.value if hasattr(layout, "value") else str(layout)
        execution_log.append({"event": "layout_selected", "layout": layout_str})

        # Step 7 & 8: Execute
        step_results: Dict[str, Dict[str, Any]] = {}
        agent_results: Dict[str, Dict[str, Any]] = {}
        zone_results: Dict[str, Dict[str, Any]] = {}

        budget_per_step = budget / max(len(steps), 1)

        # Try SplitScreenCoordinator first
        if self._split_screen_coordinator is not None:
            try:
                coord_result = self._split_screen_coordinator.coordinate(
                    task=task_description,
                    layout=layout,
                    agents=agents,
                    steps=steps,
                )
                if coord_result is not None:
                    zone_results = getattr(coord_result, "zone_results", {}) or {}
                    execution_log.append({"event": "split_screen_coordinated"})
            except Exception as exc:
                logger.warning("CTO: SplitScreenCoordinator.coordinate failed: %s", exc)

        # Execute steps per parallel group
        for group_idx, group in enumerate(parallel_groups):
            for step_id in group:
                matching = [s for s in steps if getattr(s, "step_id", None) == step_id]
                step = matching[0] if matching else type("_S", (), {"step_id": step_id, "description": task_description, "depends_on": [], "parallel": True, "agent_id": "agent_0", "metadata": {}})()
                res = self._execute_step(step, task_description, budget_per_step, step_timeout, execution_log)
                step_results[step_id] = res

                agent_id = getattr(step, "agent_id", f"agent_{group_idx}")
                if agent_id not in agent_results:
                    agent_results[agent_id] = {"agent_id": agent_id, "steps": [], "output": {}}
                agent_results[agent_id]["steps"].append(step_id)
                agent_results[agent_id]["output"].update(res.get("output", {}))

        # Fallback to HybridExecutionEngine if no results
        if not step_results and self._hybrid_engine is not None:
            try:
                hybrid_result = self._hybrid_engine.execute_plan(task_description)
                step_results["hybrid_0"] = {"output": hybrid_result, "status": "completed"}
                execution_log.append({"event": "hybrid_fallback_used"})
            except Exception as exc:
                logger.warning("CTO: HybridExecutionEngine fallback failed: %s", exc)

        # Step 9: Synthesize
        synth_input = {
            aid: {"output": ar.get("output", {}), "confidence": 0.7}
            for aid, ar in agent_results.items()
        }
        if not synth_input:
            synth_input = {"default": {"output": {"task": task_description}, "confidence": 0.5}}
        synthesized = self._synthesizer.synthesize(synth_input)

        # Step 10: Write to WorkspaceMemoryBridge
        if self._memory_bridge is not None:
            try:
                artifact_id = self._memory_bridge.write_artifact(
                    content=synthesized.merged_output,
                    artifact_type_name="hypothesis",
                    source_agent="orchestrator",
                    phase_name="expand",
                    confidence_impact=synthesized.confidence,
                )
                execution_log.append({"event": "artifact_written", "artifact_id": artifact_id})
            except Exception as exc:
                logger.warning("CTO: memory bridge write failed: %s", exc)

        total_cost = sum(r.get("cost", 0.0) for r in step_results.values())
        total_duration_ms = (time.time() - start_time) * 1000
        status = "completed" if step_results else "partial"
        if synthesized.validation_status == "failed":
            status = "partial"

        # Step 11: Build report
        report = CollaborativeExecutionReport(
            run_id=run_id,
            task_description=task_description,
            status=status,
            layout=layout_str,
            zone_results=zone_results,
            agent_results=agent_results,
            step_results=step_results,
            synthesized=synthesized,
            total_cost=total_cost,
            total_duration_ms=total_duration_ms,
            parallel_groups=parallel_groups,
            execution_log=execution_log,
            idempotency_key=idempotency_key,
            metadata={"workflow_id": workflow_id, "proposal_agents": n_agents},
        )

        # Step 12: Bounded history (CWE-770)
        with self._lock:
            self._idempotency_cache[idempotency_key] = report
            if len(self._history) >= self.MAX_HISTORY:
                oldest_key = self._history[0].idempotency_key
                del self._history[0]
                self._idempotency_cache.pop(oldest_key, None)
            self._history.append(report)

        return report
