"""
FastAPI router for the ML subsystem.

Endpoints:
  POST /api/ml/train           — Trigger a training run (HITL gated)
  GET  /api/ml/models          — List model versions
  POST /api/ml/evaluate        — Run the evaluation harness
  GET  /api/ml/metrics         — Training / inference metrics
  POST /api/ml/infer           — Direct inference endpoint
  PUT  /api/ml/active-model    — Switch active model (HITL gated)

All responses follow: {"success": bool, "data": ...}
All endpoints are wrapped in try/except with _safe_error_response.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy FastAPI import — the module must load even without fastapi installed.
# ---------------------------------------------------------------------------

try:
    from fastapi import APIRouter, Request  # type: ignore
    from fastapi.responses import JSONResponse  # type: ignore
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False
    APIRouter = None  # type: ignore
    Request = None  # type: ignore
    JSONResponse = None  # type: ignore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Any = None) -> "JSONResponse":
    return JSONResponse({"success": True, "data": data})


def _safe_error_response(exc: Exception, context: str = "") -> "JSONResponse":
    msg = f"{context}: {exc}" if context else str(exc)
    logger.warning("ML API error — %s", msg)
    return JSONResponse({"success": False, "error": msg}, status_code=500)


def _bad_request(msg: str) -> "JSONResponse":
    return JSONResponse({"success": False, "error": msg}, status_code=400)


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_ml_router() -> Any:
    """Return an APIRouter with all ML endpoints mounted under /api/ml."""
    if not _FASTAPI_AVAILABLE:
        logger.warning("FastAPI not installed; ML router cannot be created")
        return None

    router = APIRouter(prefix="/api/ml", tags=["ml"])

    # Lazy-initialised singletons — created once on first use.
    _state: Dict[str, Any] = {}

    def _get_pipeline():
        if "pipeline" not in _state:
            from .training_pipeline import TrainingPipeline  # type: ignore
            _state["pipeline"] = TrainingPipeline()
        return _state["pipeline"]

    def _get_registry():
        if "registry" not in _state:
            from .model_registry import ModelRegistry  # type: ignore
            _state["registry"] = ModelRegistry()
        return _state["registry"]

    def _get_engine():
        if "engine" not in _state:
            from .inference_engine import InferenceEngine  # type: ignore
            _state["engine"] = InferenceEngine()
        return _state["engine"]

    def _get_evaluator():
        if "evaluator" not in _state:
            from .evaluation import ModelEvaluator  # type: ignore
            _state["evaluator"] = ModelEvaluator(inference_engine=_get_engine())
        return _state["evaluator"]

    # ------------------------------------------------------------------
    # POST /api/ml/train
    # ------------------------------------------------------------------

    @router.post("/train")
    async def trigger_training(request: Request) -> JSONResponse:
        """Trigger a training run. Requires HITL approval by default."""
        try:
            body: Dict[str, Any] = {}
            try:
                body = await request.json()
            except Exception:
                logger.debug("Suppressed exception in api")

            from .training_pipeline import TrainingSource  # type: ignore
            raw_sources = body.get("sources", None)
            sources = None
            if raw_sources:
                try:
                    sources = [TrainingSource(s) for s in raw_sources]
                except ValueError as exc:
                    return _bad_request(f"Invalid source: {exc}")

            hitl_required: bool = body.get("hitl_required", True)
            pipeline = _get_pipeline()
            job = pipeline.schedule_training_run(sources=sources, hitl_required=hitl_required)
            return _ok(job.to_dict())
        except Exception as exc:
            return _safe_error_response(exc, "trigger_training")

    # ------------------------------------------------------------------
    # POST /api/ml/train/{job_id}/approve
    # ------------------------------------------------------------------

    @router.post("/train/{job_id}/approve")
    async def approve_training_job(job_id: str) -> JSONResponse:
        """Approve a HITL-gated training job so it can run."""
        try:
            pipeline = _get_pipeline()
            job = pipeline.approve_hitl(job_id)
            return _ok(job.to_dict())
        except Exception as exc:
            return _safe_error_response(exc, "approve_training_job")

    # ------------------------------------------------------------------
    # POST /api/ml/train/{job_id}/run
    # ------------------------------------------------------------------

    @router.post("/train/{job_id}/run")
    async def run_training_job(job_id: str) -> JSONResponse:
        """Execute an approved training job."""
        try:
            pipeline = _get_pipeline()
            job = pipeline.run_training_job(job_id)
            return _ok(job.to_dict())
        except Exception as exc:
            return _safe_error_response(exc, "run_training_job")

    # ------------------------------------------------------------------
    # GET /api/ml/train/{job_id}
    # ------------------------------------------------------------------

    @router.get("/train/{job_id}")
    async def get_training_job(job_id: str) -> JSONResponse:
        try:
            pipeline = _get_pipeline()
            job = pipeline.get_job_status(job_id)
            if job is None:
                return JSONResponse({"success": False, "error": "Job not found"}, status_code=404)
            return _ok(job.to_dict())
        except Exception as exc:
            return _safe_error_response(exc, "get_training_job")

    # ------------------------------------------------------------------
    # GET /api/ml/models
    # ------------------------------------------------------------------

    @router.get("/models")
    async def list_models() -> JSONResponse:
        try:
            registry = _get_registry()
            versions = registry.list_models()
            return _ok([v.to_dict() for v in versions])
        except Exception as exc:
            return _safe_error_response(exc, "list_models")

    # ------------------------------------------------------------------
    # POST /api/ml/models/register
    # ------------------------------------------------------------------

    @router.post("/models/register")
    async def register_model(request: Request) -> JSONResponse:
        try:
            body: Dict[str, Any] = await request.json()
            version_name = body.get("version_name", "")
            provider = body.get("provider", "mfm")
            config = body.get("config", {})
            metrics = body.get("metrics")
            if not version_name:
                return _bad_request("version_name is required")
            registry = _get_registry()
            mv = registry.register_model(
                version_name=version_name,
                provider=provider,
                config=config,
                metrics=metrics,
            )
            return _ok(mv.to_dict())
        except Exception as exc:
            return _safe_error_response(exc, "register_model")

    # ------------------------------------------------------------------
    # POST /api/ml/evaluate
    # ------------------------------------------------------------------

    @router.post("/evaluate")
    async def run_evaluation(request: Request) -> JSONResponse:
        """Run the evaluation harness against a specific model version."""
        try:
            body: Dict[str, Any] = {}
            try:
                body = await request.json()
            except Exception:
                logger.debug("Suppressed exception in api")

            version_id: str = body.get("version_id", "current")
            raw_domains = body.get("domains", None)
            domains = None
            if raw_domains:
                from .evaluation import BusinessDomain  # type: ignore
                try:
                    domains = [BusinessDomain(d) for d in raw_domains]
                except ValueError as exc:
                    return _bad_request(f"Invalid domain: {exc}")

            evaluator = _get_evaluator()
            result = evaluator.evaluate_model(version_id=version_id, domains=domains)
            return _ok(result.to_dict())
        except Exception as exc:
            return _safe_error_response(exc, "run_evaluation")

    # ------------------------------------------------------------------
    # GET /api/ml/metrics
    # ------------------------------------------------------------------

    @router.get("/metrics")
    async def get_metrics() -> JSONResponse:
        """Return combined training and inference metrics."""
        try:
            data: Dict[str, Any] = {}

            # Inference metrics.
            try:
                engine = _get_engine()
                data["inference"] = engine.get_metrics()
            except Exception as exc:
                data["inference"] = {"error": str(exc)}

            # Training job summary.
            try:
                pipeline = _get_pipeline()
                jobs = pipeline.list_jobs(limit=50)
                from .training_pipeline import JobStatus  # type: ignore
                data["training"] = {
                    "total_jobs": len(jobs),
                    "completed": sum(1 for j in jobs if j.status == JobStatus.COMPLETED),
                    "failed": sum(1 for j in jobs if j.status == JobStatus.FAILED),
                    "pending": sum(
                        1 for j in jobs
                        if j.status in (JobStatus.PENDING, JobStatus.AWAITING_HITL, JobStatus.RUNNING)
                    ),
                    "recent": [j.to_dict() for j in jobs[-5:]],
                }
            except Exception as exc:
                data["training"] = {"error": str(exc)}

            # Evaluation history summary.
            try:
                evaluator = _get_evaluator()
                history = evaluator.get_eval_history(limit=5)
                data["evaluation"] = {
                    "recent_evals": [e.to_dict() for e in history],
                }
            except Exception as exc:
                data["evaluation"] = {"error": str(exc)}

            return _ok(data)
        except Exception as exc:
            return _safe_error_response(exc, "get_metrics")

    # ------------------------------------------------------------------
    # POST /api/ml/infer
    # ------------------------------------------------------------------

    @router.post("/infer")
    async def direct_infer(request: Request) -> JSONResponse:
        """Direct inference endpoint — routes prompt through the full provider chain."""
        try:
            body: Dict[str, Any] = await request.json()
            prompt: str = body.get("prompt", "")
            if not prompt:
                return _bad_request("prompt is required")

            raw_complexity = body.get("task_complexity", None)
            complexity = None
            if raw_complexity:
                from .model_config import TaskComplexity  # type: ignore
                try:
                    complexity = TaskComplexity(raw_complexity)
                except ValueError:
                    return _bad_request(f"Invalid task_complexity: {raw_complexity}")

            context = body.get("context", None)
            metadata = body.get("metadata", None)

            engine = _get_engine()
            result = engine.infer(
                prompt=prompt,
                task_complexity=complexity,
                context=context,
                metadata=metadata,
            )
            return _ok(result.to_dict())
        except Exception as exc:
            return _safe_error_response(exc, "direct_infer")

    # ------------------------------------------------------------------
    # PUT /api/ml/active-model
    # ------------------------------------------------------------------

    @router.put("/active-model")
    async def set_active_model(request: Request) -> JSONResponse:
        """Promote a model version to production (HITL gated by default)."""
        try:
            body: Dict[str, Any] = await request.json()
            version_id: str = body.get("version_id", "")
            if not version_id:
                return _bad_request("version_id is required")
            hitl_required: bool = body.get("hitl_required", True)

            registry = _get_registry()
            mv = registry.set_active_model(version_id=version_id, hitl_required=hitl_required)
            return _ok(mv.to_dict())
        except Exception as exc:
            return _safe_error_response(exc, "set_active_model")

    # ------------------------------------------------------------------
    # POST /api/ml/rollback
    # ------------------------------------------------------------------

    @router.post("/rollback")
    async def rollback_model(request: Request) -> JSONResponse:
        """Roll back to a specific model version."""
        try:
            body: Dict[str, Any] = await request.json()
            version_id: str = body.get("version_id", "")
            if not version_id:
                return _bad_request("version_id is required")
            registry = _get_registry()
            mv = registry.rollback_model(version_id=version_id)
            return _ok(mv.to_dict() if mv else None)
        except Exception as exc:
            return _safe_error_response(exc, "rollback_model")

    # ------------------------------------------------------------------
    # POST /api/ml/ab-test
    # ------------------------------------------------------------------

    @router.post("/ab-test")
    async def start_ab_test(request: Request) -> JSONResponse:
        """Start an A/B test between two model versions."""
        try:
            body: Dict[str, Any] = await request.json()
            version_a: str = body.get("version_a", "")
            version_b: str = body.get("version_b", "")
            traffic_split: float = float(body.get("traffic_split", 0.1))
            if not version_a or not version_b:
                return _bad_request("version_a and version_b are required")
            registry = _get_registry()
            test = registry.start_ab_test(version_a, version_b, traffic_split)
            return _ok(test.to_dict())
        except Exception as exc:
            return _safe_error_response(exc, "start_ab_test")

    return router
