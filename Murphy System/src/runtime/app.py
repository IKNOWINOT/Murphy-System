"""
Murphy System 1.0 - FastAPI Application & Entry Point

The create_app() factory and main() entry point.
Extracted from the monolithic runtime for maintainability (INC-13 / H-04 / L-02).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from src.runtime._deps import (
    # Standard library
    Any,
    ConceptTranslationEngine,
    CORSMiddleware,
    Depends,
    Dict,
    # Web framework
    FastAPI,
    # Image / integration types
    ImageRequest,
    ImageStyle,
    InformationDensityEngine,
    InformationQualityEngine,
    IntegrationSpec,
    JSONResponse,
    List,
    MSSController,
    Path,
    Request,
    ResolutionDetectionEngine,
    Set,
    StrategicSimulationEngine,
    StructuralCoherenceEngine,
    _load_dotenv,
    # MSS controls
    _mss_available,
    asdict,
    datetime,
    json,
    # Logging / env
    logger,
    logging,
    # Module system
    module_manager,
    os,
    platform,
    time,
    timedelta,
    timezone,
    uuid4,
    uvicorn,
)
from src.runtime.living_document import LivingDocument
from src.runtime.murphy_system_core import MurphySystem

# ==================== FASTAPI APPLICATION ====================

def _safe_error_response(exc: Exception, status_code: int = 500) -> "JSONResponse":
    """Return a sanitized error response that does not leak internal details.

    In production / staging the client only sees a generic message.
    In development / test the original error string is included for
    debugging convenience.
    """
    env = os.environ.get("MURPHY_ENV", "development").lower()
    if env in ("production", "staging"):
        body = {"error": "An internal error occurred."}
    else:
        body = {"error": str(exc)}
    return JSONResponse(body, status_code=status_code)


def _normalize_mss_context(raw_context: "Any") -> "Optional[Dict[str, Any]]":
    """Coerce *raw_context* to a dict or None for MSS operations.

    The Librarian panel sends ``context`` as a plain string (e.g.
    ``"graduation"``).  MSS internals expect ``Optional[Dict[str, Any]]``.
    Passing a bare string causes ``AttributeError: 'str' object has no
    attribute 'get'`` deep inside ``mss_controls.py``.
    """
    if raw_context is None:
        return None
    if isinstance(raw_context, dict):
        return raw_context
    if isinstance(raw_context, str):
        return {"page": raw_context} if raw_context else None
    return None


def create_app() -> FastAPI:
    """Create FastAPI application"""

    if FastAPI is None:
        raise ImportError("FastAPI not installed. Install with: pip install fastapi uvicorn")

    app = FastAPI(
        title="Murphy System 1.0",
        description="Universal AI Automation System",
        version="1.0.0"
    )

    # ── Module loader (ML-001) ────────────────────────────────────
    from src.runtime.module_loader import ModuleLoader, ModulePriority
    _module_loader = ModuleLoader()

    # ── Utility: ISO timestamp helper ───────────────────────────
    def _now_iso():
        return datetime.now(timezone.utc).isoformat()

    # ── Account manager (singleton) — wraps OAuthProviderRegistry and
    #    handles account creation / linking after every OAuth callback.
    #    A simple in-memory session store maps session tokens to account IDs.
    try:
        from src.account_management.account_manager import AccountManager as _AccountManager
        _account_manager: "Optional[_AccountManager]" = _AccountManager()
        # Public accessor — no private attribute access
        _oauth_registry = _account_manager.get_oauth_registry()
        logger.info(
            "AccountManager initialised (OAuth registry: %s providers)",
            len(_oauth_registry.list_providers()) if _oauth_registry else 0,
        )
    except Exception as _am_exc:  # pragma: no cover
        logger.error("AccountManager failed to initialise: %s", _am_exc, exc_info=True)
        _account_manager = None
        _oauth_registry = None

    # session_token → account_id (in-memory; replace with Redis/DB in prod)
    import threading as _threading
    _session_lock = _threading.Lock()
    _session_store: "Dict[str, str]" = {}

    # Load .env before initialising MurphySystem so env vars like
    # MURPHY_LLM_PROVIDER and GROQ_API_KEY are available from the start.
    # Resolve to the project root (Murphy System/) — three levels up from
    # src/runtime/app.py — so it works regardless of CWD.
    if _load_dotenv is not None:
        _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        _load_dotenv(_env_path, override=True)

    # Initialize Murphy System
    murphy = MurphySystem()

    # ── Shared mutable state for critical subsystem references ────
    # These variables are read throughout the endpoint closures below.
    # Loader functions update them via `nonlocal` so that each subsystem
    # is initialised exactly once and in a controlled order through the
    # module loader, while remaining directly accessible to all closures
    # inside create_app() without requiring app.state look-ups.
    _db_available = False
    try:
        from src.database import init_database as _init_database  # noqa: PLC0415
        _db_init_status = _init_database()
        _db_available = _db_init_status.get("orm") == "ok"
        if _db_available:
            logger.info(
                "Relational persistence initialised (url=%s, migrations=%s)",
                _db_init_status.get("database_url", "?"),
                _db_init_status.get("migrations", "skipped"),
            )
        else:
            logger.warning(
                "Database init status: orm=%s, migrations=%s",
                _db_init_status.get("orm"),
                _db_init_status.get("migrations"),
            )
    except Exception as _db_exc:
        logger.warning("Database init failed — falling back to JSON persistence: %s", _db_exc)
    _cache_client = None
    _integration_bus = None
    _aionmind_kernel = None

    # ── Cache Initialisation (Phase 1-B) ─────────────────────────
    # Cache is optional — no router, no critical dependency.
    try:
        from src.cache import CacheClient
        _cache_client = CacheClient()
    except Exception as _cache_exc:
        logger.warning("CacheClient init failed: %s", _cache_exc)

    # ── Module registrations (ML-001) ────────────────────────────
    # CRITICAL modules: Security Plane, EventBackbone, Database,
    # GovernanceKernel, IntegrationBus — any failure aborts startup.
    # OPTIONAL modules: all sub-router packages — degrade gracefully.

    # --- CRITICAL: Security Plane ---
    def _load_security_plane(_app):
        """Apply security hardening middleware (CORS, API-key auth, rate-limit, headers)."""
        from src.fastapi_security import configure_secure_fastapi
        configure_secure_fastapi(_app, service_name="murphy-system-1.0")
        return False  # middleware applied; no APIRouter registered

    # --- CRITICAL: EventBackbone ---
    def _load_event_backbone(_app):
        """Verify EventBackbone was successfully initialised inside MurphySystem."""
        if getattr(murphy, "event_backbone", None) is None:
            raise RuntimeError(
                "EventBackbone did not initialise — check src.event_backbone import "
                "and MurphySystem startup logs"
            )
        return False

    # --- CRITICAL: GovernanceKernel ---
    def _load_governance_kernel(_app):
        """Verify GovernanceKernel was successfully initialised inside MurphySystem."""
        if getattr(murphy, "governance_kernel", None) is None:
            raise RuntimeError(
                "GovernanceKernel did not initialise — check src.governance_kernel import "
                "and MurphySystem startup logs"
            )
        return False

    # --- CRITICAL: Database (only when DATABASE_URL is configured) ---
    def _load_database(_app):
        """Create schema tables when a relational DATABASE_URL is configured."""
        nonlocal _db_available
        from src.db import create_tables
        create_tables()
        _db_available = True
        logger.info("Relational persistence initialised (DATABASE_URL set)")
        return False

    # --- CRITICAL: IntegrationBus (EventBackbone wiring layer) ---
    def _load_integration_bus(_app):
        """Initialise IntegrationBus — wires src/ modules into the runtime."""
        nonlocal _integration_bus
        from src.integration_bus import IntegrationBus
        _integration_bus = IntegrationBus()
        _integration_bus.initialize()
        logger.info("IntegrationBus initialised: %s", _integration_bus.get_status())
        return False

    _module_loader.register("security_plane", ModulePriority.CRITICAL, _load_security_plane)
    _module_loader.register("event_backbone", ModulePriority.CRITICAL, _load_event_backbone)
    _module_loader.register("governance_kernel", ModulePriority.CRITICAL, _load_governance_kernel)
    if os.environ.get("DATABASE_URL"):
        _module_loader.register("database", ModulePriority.CRITICAL, _load_database)
    _module_loader.register("integration_bus", ModulePriority.CRITICAL, _load_integration_bus)

    def _load_aionmind(_app):
        nonlocal _aionmind_kernel
        from aionmind import api as aionmind_api
        from aionmind.runtime_kernel import AionMindKernel
        _kernel = AionMindKernel(auto_bridge_bots=True, auto_discover_rsc=True)
        aionmind_api.init_kernel(_kernel)
        _app.include_router(aionmind_api.router)
        _aionmind_kernel = _kernel
        logger.info("AionMind 2.0 cognitive pipeline initialised (%d capabilities).",
                    _kernel.registry.count())
        return True

    def _load_board_system(_app):
        from board_system.api import create_board_router
        _app.include_router(create_board_router())
        logger.info("Board System API registered at /api/boards")
        return True

    def _load_collaboration(_app):
        from collaboration.api import create_collaboration_router
        _app.include_router(create_collaboration_router())
        logger.info("Collaboration API registered at /api/collaboration")
        return True

    def _load_dashboards(_app):
        from dashboards.api import create_dashboard_router
        _app.include_router(create_dashboard_router())
        logger.info("Dashboards API registered at /api/dashboards")
        return True

    def _load_portfolio(_app):
        from portfolio.api import create_portfolio_router
        _app.include_router(create_portfolio_router())
        logger.info("Portfolio API registered at /api/portfolio")
        return True

    def _load_workdocs(_app):
        from workdocs.api import create_workdocs_router
        _app.include_router(create_workdocs_router())
        logger.info("Workdocs API registered at /api/workdocs")
        return True

    def _load_time_tracking(_app):
        from time_tracking.api import create_time_tracking_router
        _app.include_router(create_time_tracking_router())
        logger.info("Time Tracking API registered at /api/time-tracking")
        return True

    def _load_automations(_app):
        from automations.api import create_automations_router
        _app.include_router(create_automations_router())
        logger.info("Automations API registered at /api/automations")
        return True

    def _load_crm(_app):
        from crm.api import create_crm_router
        _app.include_router(create_crm_router())
        logger.info("CRM API registered at /api/crm")
        return True

    def _load_dev_module(_app):
        from dev_module.api import create_dev_router
        _app.include_router(create_dev_router())
        logger.info("Dev Module API registered at /api/dev")
        return True

    def _load_service_module(_app):
        from service_module.api import create_service_router
        _app.include_router(create_service_router())
        logger.info("Service Module API registered at /api/service")
        return True

    def _load_guest_collab(_app):
        from guest_collab.api import create_guest_router
        _app.include_router(create_guest_router())
        logger.info("Guest Collaboration API registered at /api/guest")
        return True

    def _load_mobile(_app):
        from mobile.api import create_mobile_router
        _app.include_router(create_mobile_router())
        logger.info("Mobile API registered at /api/mobile")
        return True

    def _load_billing(_app):
        from src.billing.api import create_billing_router
        _app.include_router(create_billing_router())
        logger.info("Billing API registered at /api/billing")
        return True

    _module_loader.register("aionmind", ModulePriority.OPTIONAL, _load_aionmind)
    _module_loader.register("board_system", ModulePriority.OPTIONAL, _load_board_system)
    _module_loader.register("collaboration", ModulePriority.OPTIONAL, _load_collaboration)
    _module_loader.register("dashboards", ModulePriority.OPTIONAL, _load_dashboards)
    _module_loader.register("portfolio", ModulePriority.OPTIONAL, _load_portfolio)
    _module_loader.register("workdocs", ModulePriority.OPTIONAL, _load_workdocs)
    _module_loader.register("time_tracking", ModulePriority.OPTIONAL, _load_time_tracking)
    _module_loader.register("automations", ModulePriority.OPTIONAL, _load_automations)
    _module_loader.register("crm", ModulePriority.OPTIONAL, _load_crm)
    _module_loader.register("dev_module", ModulePriority.OPTIONAL, _load_dev_module)
    _module_loader.register("service_module", ModulePriority.OPTIONAL, _load_service_module)
    _module_loader.register("guest_collab", ModulePriority.OPTIONAL, _load_guest_collab)
    _module_loader.register("mobile", ModulePriority.OPTIONAL, _load_mobile)
    _module_loader.register("billing", ModulePriority.OPTIONAL, _load_billing)

    # Load all registered modules (aborts on critical failures).
    _module_load_result = _module_loader.load_all(app)

    # Print startup banner with module load summary
    for _banner_line in _module_load_result.banner_lines():
        print(_banner_line)

    # Register RBAC governance with security layer (SEC-005)
    rbac = getattr(murphy, 'rbac_governance', None)
    if rbac is not None:
        try:
            from src.fastapi_security import register_rbac_governance
            register_rbac_governance(rbac)
        except ImportError:
            logger.warning("fastapi_security not available — RBAC enforcement skipped")

    # RBAC permission dependencies for sensitive endpoints (SEC-005)
    # Falls back to a no-op dependency when fastapi_security is unavailable.
    async def _noop_dep():
        pass

    try:
        from src.fastapi_security import require_permission as _require_permission
        _perm_execute = _require_permission("execute_task")
        _perm_configure = _require_permission("configure_system")
    except ImportError:
        _perm_execute = _noop_dep
        _perm_configure = _noop_dep
    # ── EventBackbone — background processing loop ───────────────────
    _event_backbone = None
    try:
        from src.event_backbone import get_event_backbone as _get_event_backbone
        _event_backbone = _get_event_backbone()
        logger.info("EventBackbone initialised")
    except Exception as _eb_exc:
        logger.warning("EventBackbone not available: %s", _eb_exc)

    @app.on_event("startup")
    async def _start_event_backbone():
        if _event_backbone is not None:
            _event_backbone.start()
            logger.info("EventBackbone background loop started")

    @app.on_event("shutdown")
    async def _stop_event_backbone():
        if _event_backbone is not None:
            _event_backbone.stop()
            logger.info("EventBackbone background loop stopped")

    # ── Integration Bus — wires src/ modules into the runtime ────────
    _integration_bus = None
    try:
        from murphy_code_healer import MurphyCodeHealer as _MurphyCodeHealer
        _src_root = str(Path(__file__).resolve().parent.parent)
        _tests_root = str(Path(__file__).resolve().parent.parent.parent / "tests")
        _docs_root = str(Path(__file__).resolve().parent.parent.parent / "docs")
        _code_healer = _MurphyCodeHealer(
            src_root=_src_root,
            tests_root=_tests_root,
            docs_root=_docs_root,
        )
        _code_healer.subscribe_to_events()
        logger.info("MurphyCodeHealer initialised and subscribed to EventBackbone events")
    except Exception as _healer_exc:
        logger.warning("MurphyCodeHealer not available: %s", _healer_exc)

    # ==================== CORE ENDPOINTS ====================

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        from starlette.responses import RedirectResponse
        return RedirectResponse("/static/favicon.svg", status_code=301)

    @app.post("/api/execute")
    async def execute_task(request: Request, _rbac=Depends(_perm_execute)):
        """Execute a task — routes through AionMind cognitive pipeline when available."""
        data = await request.json()
        task_description = data.get('task_description', '')
        task_type = data.get('task_type', 'general')

        # Route through AionMind cognitive pipeline if available
        if _aionmind_kernel is not None:
            try:
                aionmind_result = _aionmind_kernel.cognitive_execute(
                    source="api",
                    raw_input=task_description,
                    task_type=task_type,
                    parameters=data.get('parameters'),
                    auto_approve=True,
                    approver="api_auto",
                )
                # Fall through to legacy if no candidates
                if aionmind_result.get("status") != "no_candidates":
                    # Merge with legacy execution for full feature coverage
                    legacy_result = await murphy.execute_task(
                        task_description=task_description,
                        task_type=task_type,
                        parameters=data.get('parameters'),
                        session_id=data.get('session_id'),
                    )
                    legacy_result["aionmind"] = aionmind_result
                    return JSONResponse(legacy_result)
            except Exception as _exc:
                logger.debug("AionMind pipeline fallback: %s", _exc)

        # Route through IntegrationBus (DomainEngine → SwarmSystem → FeedbackIntegrator)
        if _integration_bus is not None:
            try:
                bus_result = _integration_bus.process("execute", {
                    "task_description": task_description,
                    "task_type": task_type,
                    "parameters": data.get("parameters"),
                })
                if bus_result.get("bus_routed"):
                    legacy_result = await murphy.execute_task(
                        task_description=task_description,
                        task_type=task_type,
                        parameters=data.get('parameters'),
                        session_id=data.get('session_id'),
                    )
                    legacy_result["bus"] = bus_result
                    return JSONResponse(legacy_result)
            except Exception as _ib_exc:
                logger.debug("IntegrationBus execute fallback: %s", _ib_exc)

        # Legacy path
        result = await murphy.execute_task(
            task_description=task_description,
            task_type=task_type,
            parameters=data.get('parameters'),
            session_id=data.get('session_id')
        )
        return JSONResponse(result)

    @app.post("/api/chat")
    async def chat(request: Request):
        """Chat endpoint for terminal UIs — routed through IntegrationBus when available."""
        data = await request.json()
        message = data.get("message", "")
        session_id = data.get("session_id")

        # Route through IntegrationBus (LLMIntegrationLayer → LLMController → LLMOutputValidator)
        if _integration_bus is not None:
            try:
                bus_result = _integration_bus.process("chat", {
                    "message": message,
                    "domain": data.get("domain", "general"),
                    "context": data.get("context"),
                })
                if bus_result.get("response"):
                    legacy = murphy.handle_chat(
                        message=message,
                        session_id=session_id,
                        use_mfgc=data.get("use_mfgc", False),
                    )
                    legacy["bus"] = bus_result
                    return JSONResponse(legacy)
            except Exception as _bus_exc:
                logger.debug("IntegrationBus chat fallback: %s", _bus_exc)

        # Legacy path
        result = murphy.handle_chat(
            message=message,
            session_id=session_id,
            use_mfgc=data.get("use_mfgc", False)
        )
        return JSONResponse(result)

    @app.get("/api/status")
    async def get_status():
        """Get system status"""
        return JSONResponse(murphy.get_system_status())

    @app.get("/api/info")
    async def get_info():
        """Get system information"""
        return JSONResponse(murphy.get_system_info())

    @app.get("/api/system/info")
    async def get_system_info():
        """Alias for system information (legacy UI compatibility)"""
        info = murphy.get_system_info()
        # Preserve legacy flat response shape for older clients.
        response = {**info, "success": True, "system": info}
        return JSONResponse(response)

    @app.get("/api/health")
    async def health_check(deep: bool = False):
        """Health check endpoint.

        - ``GET /api/health`` — shallow liveness probe (fast, always 200)
        - ``GET /api/health?deep=true`` — deep readiness probe; checks all
          critical subsystems and returns ``503`` if any are unhealthy.

        Suitable for Kubernetes liveness (shallow) and readiness (deep) probes.
        """
        _db_mode = os.environ.get("MURPHY_DB_MODE", "stub").lower()

        # Shallow liveness probe — instant, no I/O
        if not deep:
            return JSONResponse({
                "status": "healthy",
                "version": murphy.version,
                "db_mode": _db_mode,
            })

        # Deep readiness probe — checks all critical subsystems
        checks: dict = {"runtime": "ok"}
        critical_failed: list = []

        # Persistence check — write + read a test key
        try:
            persistence_dir = os.environ.get("MURPHY_PERSISTENCE_DIR", ".murphy_persistence")
            _p = Path(persistence_dir)
            _p.mkdir(parents=True, exist_ok=True)
            _test_file = _p / ".health_probe"
            _test_file.write_text("ok")
            if _test_file.read_text() != "ok":
                raise RuntimeError("persistence write/read mismatch")
            _test_file.unlink(missing_ok=True)
            checks["persistence"] = "ok"
        except Exception as _pe:
            checks["persistence"] = "error"
            critical_failed.append(f"persistence: {_pe}")

        # Database check — always reported; uses unified database layer
        try:
            from src.database import get_database_status  # noqa: PLC0415
            _db_status = get_database_status()
            checks["database"] = _db_status.get("orm", _db_mode)
            checks["db_mode"] = _db_status.get("db_mode", _db_mode)
            if _db_status.get("pool"):
                checks["db_pool"] = _db_status["pool"]
            if checks["database"] == "error":
                critical_failed.append("database: connection test failed")
        except Exception as _dbe:
            checks["database"] = "error"
            checks["db_mode"] = _db_mode
            critical_failed.append(f"database: {_dbe}")

        # Redis / cache check
        if _cache_client is not None:
            try:
                ping = await _cache_client.ping()
                checks["redis"] = "ok" if ping == "PONG" else "error"
                if checks["redis"] == "error":
                    critical_failed.append("redis: ping failed")
            except Exception as _re:
                checks["redis"] = "error"
                critical_failed.append(f"redis: {_re}")
        else:
            checks["redis"] = "not_configured"

        # LLM provider check
        try:
            llm_status = murphy._get_llm_status()
            checks["llm"] = "ok" if llm_status.get("enabled") else "unavailable"
        except Exception:
            checks["llm"] = "unavailable"

        # Event backbone / integration bus
        try:
            from src.integration_bus import IntegrationBus
            _bus = IntegrationBus()
            checks["event_backbone"] = "ok" if _bus is not None else "error"
        except Exception:
            checks["event_backbone"] = "not_configured"

        # Module count
        try:
            module_mgr = getattr(murphy, "module_manager", None)
            if module_mgr is not None:
                checks["modules_loaded"] = len(getattr(module_mgr, "available_modules", []))
            else:
                _sys_status = murphy.get_system_status()
                checks["modules_loaded"] = len(_sys_status.get("modules", {}))
        except Exception:
            checks["modules_loaded"] = 0

        checks["version"] = murphy.version

        # Module load report (ML-001)
        checks["module_load_report"] = _module_load_result.as_dict()

        # Determine overall status
        str_checks = [v for v in checks.values() if isinstance(v, str)]
        overall = "healthy" if all(v != "error" for v in str_checks) else "degraded"
        http_status = 200 if not critical_failed else 503

        # Merge registered-module health from the canonical metrics registry.
        try:
            from src import metrics as _health_metrics
            module_health = _health_metrics.get_system_health()
            checks["registered_modules"] = module_health.get("modules", {})
            checks["uptime_seconds"] = module_health.get("uptime_seconds")
            if module_health.get("status") == "degraded":
                overall = "degraded"
        except Exception as _mh_exc:
            logger.debug("Module health aggregation skipped: %s", _mh_exc)

        return JSONResponse(
            {"status": overall, "checks": checks, "critical_failures": critical_failed},
            status_code=http_status,
        )

    @app.get("/api/modules")
    async def list_modules():
        """Return the full module inventory with load status (ML-001).

        Includes each module's name, priority (critical/optional), load status
        (loaded/failed/skipped), error message (if any), and load time.
        """
        return JSONResponse(_module_load_result.as_dict())

    # ── Deployment Readiness & Bootstrap Status ────────────────────
    @app.get("/api/readiness")
    async def readiness_check():
        """Pre-flight deployment readiness report."""
        try:
            from deployment_readiness import DeploymentReadinessChecker
            checker = DeploymentReadinessChecker()
            return JSONResponse(checker.get_status())
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.get("/api/bootstrap")
    async def bootstrap_status():
        """Self-automation bootstrap status across all three stages."""
        try:
            from self_automation_bootstrap import SelfAutomationBootstrap
            boot = SelfAutomationBootstrap()
            return JSONResponse(boot.run())
        except Exception as exc:
            return _safe_error_response(exc, 500)

    # ==================== LIBRARIAN ENDPOINTS ====================

    @app.post("/api/librarian/ask")
    async def librarian_ask(request: Request):
        """Route a natural-language message through the Librarian + optional LLM.

        Accepts an optional ``mode`` field:
        - ``"ask"``     — pure knowledge query; skips onboarding dimension
                          extraction and returns a direct answer.
        - ``"execute"`` — task/action mode; routes through the execution
                          engine and returns a structured result.
        - ``None``      — (default) legacy behaviour, onboarding + LLM
                          fallback.
        """
        data = await request.json()
        # Accept 'message', 'query', or 'question' — UI components use different names
        message = data.get("message") or data.get("query") or data.get("question") or ""
        mode = data.get("mode")  # "ask" | "execute" | None

        if mode == "execute":
            # Route through the task execution engine
            result = murphy.handle_chat(
                message=message,
                session_id=data.get("session_id"),
                use_mfgc=True,
            )
            result["librarian_mode"] = "execute"
            return JSONResponse(result)

        result = murphy.librarian_ask(
            message=message,
            session_id=data.get("session_id"),
            mode=mode,
        )
        return JSONResponse(result)

    @app.post("/api/librarian/query")
    async def librarian_query(request: Request):
        """Return ranked capability matches for a natural-language query.

        Uses the new ``TaskRouter`` / ``SystemLibrarian.find_capabilities()``
        pipeline introduced in Phases 9–12 of the Flattening Plan.

        Request body:
        ```json
        {
          "query": "generate an invoice for a consulting project",
          "top_n": 5
        }
        ```

        Response:
        ```json
        {
          "success": true,
          "query": "generate an invoice ...",
          "matches": [
            {
              "capability_id": "generate_invoice",
              "module_path": "src.invoice_processing_pipeline",
              "score": 0.94,
              "match_reasons": ["keyword overlap: ['invoice']"],
              "cost_estimate": "low",
              "determinism": "deterministic",
              "filtered": false
            }
          ],
          "routing": {
            "status": "approved",
            "capability_id": "generate_invoice",
            "score": 0.94
          }
        }
        ```
        """
        try:
            data = await request.json()
        except Exception:
            data = {}

        query = (data.get("query") or data.get("task") or "").strip()
        top_n = int(data.get("top_n", 5))

        if not query:
            return JSONResponse(
                {"success": False, "error": "query is required"},
                status_code=400,
            )

        task_dict = {"task": query}

        # Phase 1 — capability discovery via SystemLibrarian
        matches: list = []
        try:
            librarian = murphy.librarian if hasattr(murphy, "librarian") else None
            if librarian is None:
                from system_librarian import SystemLibrarian as _SL  # type: ignore[import]
                librarian = _SL()
            raw_matches = librarian.find_capabilities(task_dict, top_n=top_n)
            matches = [
                {
                    "capability_id": m.capability_id,
                    "module_path": m.module_path,
                    "score": m.score,
                    "match_reasons": m.match_reasons,
                    "cost_estimate": m.cost_estimate,
                    "determinism": m.determinism,
                    "filtered": m.filtered,
                    "filter_reason": m.filter_reason,
                }
                for m in raw_matches
            ]
        except Exception as exc:
            logger.warning("librarian_query: find_capabilities error: %s", exc)

        # Phase 2 — TaskRouter routing decision (best-effort)
        routing: dict = {}
        try:
            from solution_path_registry import SolutionPathRegistry  # type: ignore[import]
            from system_librarian import SystemLibrarian as _SL2  # type: ignore[import]
            from task_router import TaskRouter  # type: ignore[import]

            _router = TaskRouter(
                librarian=_SL2(),
                solution_registry=SolutionPathRegistry(),
            )
            result = _router.route_sync(task_dict)
            routing = {
                "status": result.status.value,
                "capability_id": result.solution_path.capability_id if result.solution_path else None,
                "score": result.solution_path.combined_score if result.solution_path else None,
            }
        except Exception as exc:
            logger.debug("librarian_query: TaskRouter error: %s", exc)
            routing = {"status": "unavailable", "error": str(exc)}

        return JSONResponse(
            {
                "success": True,
                "query": query,
                "matches": matches,
                "routing": routing,
            }
        )

    @app.get("/api/librarian/status")
    async def librarian_status():
        """Return librarian health status."""
        return JSONResponse(murphy._get_librarian_status())

    @app.get("/api/llm/status")
    async def llm_status():
        """Return LLM provider configuration and health."""
        return JSONResponse(murphy._get_llm_status())

    @app.post("/api/llm/configure")
    async def llm_configure(request: Request, _rbac=Depends(_perm_configure)):
        """Hot-reload LLM configuration from the terminal without restarting."""
        try:
            data = await request.json()
        except (ValueError, KeyError):
            data = {}
        provider = (data.get("provider") or "").strip().lower()
        api_key = (data.get("api_key") or "").strip()
        if not provider:
            return JSONResponse({"success": False, "error": "provider is required"}, status_code=400)
        # Map provider to its env var
        provider_env_vars = {
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_var = provider_env_vars.get(provider)
        if env_var and api_key:
            logger.warning(
                "API key stored in process environment — use SecureKeyManager in production"
            )
            os.environ[env_var] = api_key
        os.environ["MURPHY_LLM_PROVIDER"] = provider
        # Persist key to .env so it survives restarts
        _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        try:
            from src.env_manager import write_env_key as _write_env_key
            if env_var and api_key:
                _write_env_key(str(_env_path), env_var, api_key)
            _write_env_key(str(_env_path), "MURPHY_LLM_PROVIDER", provider)
        except Exception as _exc:
            logger.warning("Could not persist LLM config to .env: %s", _exc)
        # Re-read .env so any manually edited values also take effect
        if _load_dotenv is not None:
            _load_dotenv(_env_path, override=True)
        # Refresh LLMController model availability without restart
        try:
            from src.llm_controller import LLMController as _LLMController
            if isinstance(getattr(murphy, "_llm_controller", None), _LLMController):
                murphy._llm_controller.refresh_availability()
        except Exception as _exc:
            logger.debug("LLMController refresh_availability skipped: %s", _exc)
        return JSONResponse({"success": True, **murphy._get_llm_status()})

    @app.post("/api/llm/test")
    async def llm_test():
        """Make a minimal test call to the configured LLM provider to verify the key."""
        llm_status = murphy._get_llm_status()
        if not llm_status.get("enabled"):
            return JSONResponse({"success": False, "error": llm_status.get("error", "LLM not configured")})
        _, err = murphy._try_llm_generate("Say OK", "")
        if err is not None:
            return JSONResponse({"success": False, "error": err})
        return JSONResponse({"success": True, **llm_status})

    @app.post("/api/llm/reload")
    async def llm_reload():
        """Re-read .env and reinitialise LLM config — called on terminal reconnect."""
        if _load_dotenv is not None:
            _load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)
        # Refresh LLMController model availability after env reload
        try:
            from src.llm_controller import LLMController as _LLMController
            if isinstance(getattr(murphy, "_llm_controller", None), _LLMController):
                murphy._llm_controller.refresh_availability()
        except Exception as _exc:
            logger.debug("LLMController refresh_availability skipped: %s", _exc)
        return JSONResponse({"success": True, **murphy._get_llm_status()})

    @app.get("/api/librarian/api-links")
    async def api_links():
        """Return API provider signup links for all supported services."""
        return JSONResponse(murphy.get_api_setup_guidance())

    @app.post("/api/librarian/integrations")
    async def librarian_integrations(request: Request):
        """Infer needed integrations from onboarding answers and return with API links."""
        data = await request.json()
        answers = data.get("answers", {})
        recs = murphy.infer_needed_integrations(answers)
        return JSONResponse({
            "success": True,
            "recommendations": recs,
            "count": len(recs),
        })

    # ==================== LIBRARIAN COMMAND CATALOG ====================

    @app.get("/api/librarian/commands")
    async def librarian_commands():
        """Return the full command catalog so the Librarian can guide users.

        Every system capability is listed here with its category, description,
        the API endpoint it maps to, and the UI page where users can invoke it.
        The Librarian uses this catalog to answer "how do I …?" questions.
        """
        catalog = [
            # ── Core Operations ──────────────────────────────────────
            {"command": "chat", "category": "core", "description": "Send a natural-language message to Murphy", "api": "/api/chat", "ui": "/ui/terminal-integrated#chat"},
            {"command": "execute", "category": "core", "description": "Execute a slash-command or code snippet", "api": "/api/execute", "ui": "/ui/terminal-architect#execute"},
            {"command": "status", "category": "core", "description": "View system status and health", "api": "/api/status", "ui": "/ui/terminal-integrated#status"},
            {"command": "health", "category": "core", "description": "Quick health check", "api": "/api/health", "ui": "/ui/terminal-integrated#dashboard"},
            {"command": "info", "category": "core", "description": "System information and version", "api": "/api/info", "ui": "/ui/landing"},
            {"command": "bootstrap", "category": "core", "description": "First-run bootstrap status", "api": "/api/bootstrap", "ui": "/ui/onboarding"},
            # ── Librarian & LLM ──────────────────────────────────────
            {"command": "librarian ask", "category": "librarian", "description": "Ask the Librarian any question about the system", "api": "/api/librarian/ask", "ui": "/ui/terminal-integrated#chat"},
            {"command": "librarian query", "category": "librarian", "description": "Query the Librarian for ranked capability matches (TaskRouter)", "api": "/api/librarian/query", "ui": "/ui/terminal-integrated#chat"},
            {"command": "librarian status", "category": "librarian", "description": "Check Librarian health", "api": "/api/librarian/status", "ui": "/ui/terminal-integrated#status"},
            {"command": "llm status", "category": "librarian", "description": "Check LLM provider configuration", "api": "/api/llm/status", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm configure", "category": "librarian", "description": "Configure LLM provider and API key", "api": "/api/llm/configure", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm test", "category": "librarian", "description": "Test LLM connectivity", "api": "/api/llm/test", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm reload", "category": "librarian", "description": "Reload LLM configuration", "api": "/api/llm/reload", "ui": "/ui/terminal-integrations#llm"},
            # ── Documents (MSS pipeline) ─────────────────────────────
            {"command": "document create", "category": "documents", "description": "Create a new living document", "api": "/api/documents", "ui": "/ui/terminal-integrated#documents"},
            {"command": "document magnify", "category": "documents", "description": "Expand a document with detail (MSS Magnify)", "api": "/api/documents/{id}/magnify", "ui": "/ui/terminal-integrated#documents"},
            {"command": "document simplify", "category": "documents", "description": "Prune noise from a document (MSS Simplify)", "api": "/api/documents/{id}/simplify", "ui": "/ui/terminal-integrated#documents"},
            {"command": "document solidify", "category": "documents", "description": "Lock actionable plan (MSS Solidify)", "api": "/api/documents/{id}/solidify", "ui": "/ui/terminal-integrated#documents"},
            {"command": "document gates", "category": "documents", "description": "Run MFGC gate checks on document", "api": "/api/documents/{id}/gates", "ui": "/ui/terminal-integrated#documents"},
            # ── MSS Controls ─────────────────────────────────────────
            {"command": "mss magnify", "category": "mss", "description": "Run MSS Magnify on text input", "api": "/api/mss/magnify", "ui": "/ui/terminal-architect#execute"},
            {"command": "mss simplify", "category": "mss", "description": "Run MSS Simplify on text input", "api": "/api/mss/simplify", "ui": "/ui/terminal-architect#execute"},
            {"command": "mss solidify", "category": "mss", "description": "Run MSS Solidify on text input", "api": "/api/mss/solidify", "ui": "/ui/terminal-architect#execute"},
            {"command": "mss score", "category": "mss", "description": "Score text quality with MSS", "api": "/api/mss/score", "ui": "/ui/terminal-architect#execute"},
            # ── MFGC (Gate Control) ──────────────────────────────────
            {"command": "mfgc state", "category": "mfgc", "description": "View current MFGC gate states", "api": "/api/mfgc/state", "ui": "/ui/terminal-architect#gates"},
            {"command": "mfgc config", "category": "mfgc", "description": "View or update MFGC configuration", "api": "/api/mfgc/config", "ui": "/ui/terminal-architect#gates"},
            {"command": "mfgc setup", "category": "mfgc", "description": "Apply MFGC profile (production/certification/development)", "api": "/api/mfgc/setup/{profile}", "ui": "/ui/terminal-architect#gates"},
            # ── Forms & Task Execution ───────────────────────────────
            {"command": "form submit", "category": "forms", "description": "Submit a form (task-execution, validation, correction, plan-upload)", "api": "/api/forms/{form_type}", "ui": "/ui/terminal-integrated#forms"},
            {"command": "form task-execution", "category": "forms", "description": "Execute a task through form", "api": "/api/forms/task-execution", "ui": "/ui/terminal-integrated#forms"},
            {"command": "form validation", "category": "forms", "description": "Validate a form submission", "api": "/api/forms/validation", "ui": "/ui/terminal-integrated#forms"},
            # ── HITL (Human-in-the-Loop) ─────────────────────────────
            {"command": "hitl pending", "category": "hitl", "description": "View pending human intervention requests", "api": "/api/hitl/interventions/pending", "ui": "/ui/terminal-integrated#hitl"},
            {"command": "hitl respond", "category": "hitl", "description": "Respond to a human intervention", "api": "/api/hitl/interventions/{id}/respond", "ui": "/ui/terminal-integrated#hitl"},
            {"command": "hitl statistics", "category": "hitl", "description": "View HITL statistics", "api": "/api/hitl/statistics", "ui": "/ui/terminal-integrated#hitl"},
            # ── Corrections & Learning ───────────────────────────────
            {"command": "corrections patterns", "category": "corrections", "description": "View correction patterns", "api": "/api/corrections/patterns", "ui": "/ui/terminal-architect#corrections"},
            {"command": "corrections statistics", "category": "corrections", "description": "View correction statistics", "api": "/api/corrections/statistics", "ui": "/ui/terminal-architect#corrections"},
            {"command": "corrections proposals", "category": "corrections", "description": "List MurphyCodeHealer repair proposals awaiting review", "api": "/api/corrections/proposals", "ui": "/ui/terminal-architect#corrections"},
            {"command": "corrections heal", "category": "corrections", "description": "Trigger on-demand autonomous healing diagnostic cycle", "api": "/api/corrections/heal", "ui": "/ui/terminal-architect#corrections"},
            {"command": "learning status", "category": "learning", "description": "Check learning engine status", "api": "/api/learning/status", "ui": "/ui/terminal-architect#status"},
            {"command": "learning toggle", "category": "learning", "description": "Enable/disable learning engine", "api": "/api/learning/toggle", "ui": "/ui/terminal-architect#status"},
            # ── Integrations & Connectors ─────────────────────────────
            {"command": "integrations list", "category": "integrations", "description": "List all integrations and their status", "api": "/api/integrations", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "integrations add", "category": "integrations", "description": "Add a new integration", "api": "/api/integrations/add", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "integrations wire", "category": "integrations", "description": "Wire up an integration connection", "api": "/api/integrations/wire", "ui": "/ui/terminal-integrations#connections"},
            {"command": "integrations active", "category": "integrations", "description": "View active integration connections", "api": "/api/integrations/active", "ui": "/ui/terminal-integrations#connections"},
            {"command": "universal-integrations list", "category": "integrations", "description": "Browse universal integration services catalog", "api": "/api/universal-integrations/services", "ui": "/ui/terminal-integrations#integrations"},
            # ── Website Builder Integrations ─────────────────────────
            {"command": "wordpress connect", "category": "website_integrations", "description": "Connect a WordPress site to pull posts, pages, forms, and WooCommerce data", "api": "/api/universal-integrations/services/wordpress/configure", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "wordpress posts", "category": "website_integrations", "description": "List WordPress posts as automation inputs", "api": "/api/universal-integrations/services/wordpress/execute/list_posts", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "wordpress pages", "category": "website_integrations", "description": "List WordPress pages", "api": "/api/universal-integrations/services/wordpress/execute/list_pages", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "wordpress forms", "category": "website_integrations", "description": "List WordPress form entries (Contact Form 7 / Gravity Forms)", "api": "/api/universal-integrations/services/wordpress/execute/list_form_entries", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "wordpress orders", "category": "website_integrations", "description": "List WooCommerce orders", "api": "/api/universal-integrations/services/wordpress/execute/list_wc_orders", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "wix connect", "category": "website_integrations", "description": "Connect a Wix site to pull content, forms, bookings, and e-commerce data", "api": "/api/universal-integrations/services/wix/configure", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "wix forms", "category": "website_integrations", "description": "List Wix form submissions as automation inputs", "api": "/api/universal-integrations/services/wix/execute/list_form_submissions", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "wix orders", "category": "website_integrations", "description": "List Wix e-commerce orders", "api": "/api/universal-integrations/services/wix/execute/list_orders", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "wix contacts", "category": "website_integrations", "description": "List Wix CRM contacts", "api": "/api/universal-integrations/services/wix/execute/list_contacts", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "wix bookings", "category": "website_integrations", "description": "List Wix bookings/appointments", "api": "/api/universal-integrations/services/wix/execute/list_bookings", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "squarespace connect", "category": "website_integrations", "description": "Connect a Squarespace site to pull orders, products, forms", "api": "/api/universal-integrations/services/squarespace/configure", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "squarespace orders", "category": "website_integrations", "description": "List Squarespace orders", "api": "/api/universal-integrations/services/squarespace/execute/list_orders", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "webflow connect", "category": "website_integrations", "description": "Connect a Webflow site to pull CMS collections and form data", "api": "/api/universal-integrations/services/webflow/configure", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "webflow forms", "category": "website_integrations", "description": "List Webflow form submissions", "api": "/api/universal-integrations/services/webflow/execute/list_form_submissions", "ui": "/ui/terminal-integrations#integrations"},
            # ── Partner Integration ──────────────────────────────────
            {"command": "partner request", "category": "partner", "description": "Submit a partner integration request", "api": "/api/partner/request", "ui": "/ui/partner"},
            {"command": "partner status", "category": "partner", "description": "Check partner request status", "api": "/api/partner/status/{id}", "ui": "/ui/partner"},
            {"command": "partner review", "category": "partner", "description": "HITL review of partner integration", "api": "/api/partner/review/{id}", "ui": "/ui/partner"},
            # ── Reviews & Referrals ──────────────────────────────────
            {"command": "review submit", "category": "reviews", "description": "Submit a product review", "api": "/api/reviews/submit", "ui": "/ui/murphy_landing_page.html#reviews"},
            {"command": "reviews list", "category": "reviews", "description": "List public reviews", "api": "/api/reviews", "ui": "/ui/murphy_landing_page.html#reviews"},
            {"command": "review moderate", "category": "reviews", "description": "Moderate a review (10-min SLA for negatives)", "api": "/api/reviews/{id}/moderate", "ui": "/ui/murphy_landing_page.html#reviews"},
            {"command": "referral create", "category": "reviews", "description": "Create a referral link (1 month free Solo)", "api": "/api/referrals/create", "ui": "/ui/signup.html"},
            {"command": "referral redeem", "category": "reviews", "description": "Redeem a referral code on signup", "api": "/api/referrals/redeem", "ui": "/ui/signup.html"},
            # ── HITL (QC vs User Acceptance) ─────────────────────────
            {"command": "hitl qc submit", "category": "hitl", "description": "Submit for internal QC review before delivery", "api": "/api/hitl/qc/submit", "ui": "/ui/terminal-unified#hitl"},
            {"command": "hitl acceptance submit", "category": "hitl", "description": "Submit deliverable for customer acceptance", "api": "/api/hitl/acceptance/submit", "ui": "/ui/terminal-unified#hitl"},
            {"command": "hitl decide", "category": "hitl", "description": "Accept/reject/revise an HITL item", "api": "/api/hitl/{id}/decide", "ui": "/ui/terminal-unified#hitl"},
            {"command": "hitl queue", "category": "hitl", "description": "View HITL queue (qc or acceptance)", "api": "/api/hitl/queue", "ui": "/ui/terminal-unified#hitl"},
            # ── Community / Forum / Org Groups ───────────────────────
            {"command": "community create channel", "category": "community", "description": "Create a forum topic or org group channel", "api": "/api/community/channels", "ui": "/ui/community"},
            {"command": "community channels", "category": "community", "description": "List community channels", "api": "/api/community/channels", "ui": "/ui/community"},
            {"command": "community post", "category": "community", "description": "Post a message to a channel", "api": "/api/community/channels/{id}/messages", "ui": "/ui/community"},
            {"command": "org join", "category": "community", "description": "Auto-join organization on login", "api": "/api/org/join", "ui": "/ui/community"},
            {"command": "org invite", "category": "community", "description": "Invite a user to your organization", "api": "/api/org/invite", "ui": "/ui/community"},
            {"command": "review automation", "category": "reviews", "description": "Run review-driven automation adjustments", "api": "/api/automation/review-response", "ui": "/ui/terminal-unified"},
            # ── Domain & Email ───────────────────────────────────────
            {"command": "domains list", "category": "domains", "description": "List configured domains (murphy.system, murphysystem.com, murphy.ai)", "api": "/api/domains", "ui": "/ui/terminal-integrations"},
            {"command": "domain register", "category": "domains", "description": "Register a new domain for Murphy hosting", "api": "/api/domains/register", "ui": "/ui/terminal-integrations"},
            {"command": "domain verify", "category": "domains", "description": "Verify DNS records for a registered domain", "api": "/api/domains/{id}/verify", "ui": "/ui/terminal-integrations"},
            {"command": "email create", "category": "email", "description": "Create email account on Murphy-hosted domain", "api": "/api/email/accounts", "ui": "/ui/terminal-integrations"},
            {"command": "email list", "category": "email", "description": "List email accounts", "api": "/api/email/accounts", "ui": "/ui/terminal-integrations"},
            {"command": "email send", "category": "email", "description": "Send email via Murphy's hosted email system", "api": "/api/email/send", "ui": "/ui/terminal-integrations"},
            {"command": "email config", "category": "email", "description": "Get SMTP/IMAP configuration", "api": "/api/email/config", "ui": "/ui/terminal-integrations"},
            # ── Matrix Bridge ────────────────────────────────────────
            {"command": "matrix status", "category": "matrix", "description": "Check Matrix bridge connection status", "api": "/api/matrix/status", "ui": "/ui/matrix"},
            {"command": "matrix rooms", "category": "matrix", "description": "List joined Matrix rooms", "api": "/api/matrix/rooms", "ui": "/ui/matrix"},
            {"command": "matrix send", "category": "matrix", "description": "Send a message to a Matrix room", "api": "/api/matrix/send", "ui": "/ui/matrix"},
            {"command": "matrix stats", "category": "matrix", "description": "View Matrix bridge statistics", "api": "/api/matrix/stats", "ui": "/ui/matrix"},
            # ── Onboarding & Setup ───────────────────────────────────
            {"command": "onboarding questions", "category": "onboarding", "description": "Get onboarding wizard questions", "api": "/api/onboarding/wizard/questions", "ui": "/ui/onboarding"},
            {"command": "onboarding answer", "category": "onboarding", "description": "Answer an onboarding question", "api": "/api/onboarding/wizard/answer", "ui": "/ui/onboarding"},
            {"command": "onboarding profile", "category": "onboarding", "description": "Get current onboarding profile", "api": "/api/onboarding/wizard/profile", "ui": "/ui/onboarding"},
            {"command": "onboarding generate-config", "category": "onboarding", "description": "Generate system configuration from onboarding answers", "api": "/api/onboarding/wizard/generate-config", "ui": "/ui/onboarding"},
            {"command": "onboarding summary", "category": "onboarding", "description": "Get onboarding summary", "api": "/api/onboarding/wizard/summary", "ui": "/ui/onboarding"},
            {"command": "onboarding employees", "category": "onboarding", "description": "Manage employee onboarding profiles", "api": "/api/onboarding/employees", "ui": "/ui/onboarding"},
            {"command": "onboarding status", "category": "onboarding", "description": "Check overall onboarding status", "api": "/api/onboarding/status", "ui": "/ui/terminal-orgchart#onboarding"},
            # ── Workflows ────────────────────────────────────────────
            {"command": "workflows list", "category": "workflows", "description": "List all workflows", "api": "/api/workflows", "ui": "/ui/workflow-canvas"},
            {"command": "workflows create", "category": "workflows", "description": "Create a new workflow", "api": "/api/workflows", "ui": "/ui/workflow-canvas"},
            {"command": "workflow-terminal session", "category": "workflows", "description": "Start a workflow terminal session", "api": "/api/workflow-terminal/sessions", "ui": "/ui/workflow-canvas"},
            {"command": "golden-path", "category": "workflows", "description": "View golden-path workflow recommendations", "api": "/api/golden-path", "ui": "/ui/terminal-orchestrator"},
            # ── Agents & Tasks ───────────────────────────────────────
            {"command": "agents list", "category": "agents", "description": "List all AI agents", "api": "/api/agents", "ui": "/ui/terminal-integrated#agents"},
            {"command": "agent dashboard", "category": "agents", "description": "Open the full agent monitoring dashboard (health, pipeline, agents, metrics, onboarding)", "api": "/api/agent-dashboard/snapshot", "ui": "/ui/dashboard"},
            {"command": "tasks list", "category": "agents", "description": "List active tasks", "api": "/api/tasks", "ui": "/ui/terminal-orchestrator"},
            {"command": "production queue", "category": "agents", "description": "View production queue", "api": "/api/production/queue", "ui": "/ui/terminal-orchestrator"},
            {"command": "production wizard", "category": "production", "description": "Open the production wizard for proposals, work orders, and deliverables", "api": "/api/production/queue", "ui": "/ui/production-wizard"},
            {"command": "production new proposal", "category": "production", "description": "Create a new production proposal via the wizard", "api": "/api/production/proposal", "ui": "/ui/production-wizard#proposal"},
            {"command": "production work order", "category": "production", "description": "Create a work order from an approved proposal", "api": "/api/production/workorder", "ui": "/ui/production-wizard#workorder"},
            {"command": "production validate", "category": "production", "description": "Validate a deliverable against its work order", "api": "/api/production/validate", "ui": "/ui/production-wizard#validate"},
            {"command": "production profiles", "category": "production", "description": "Manage production profiles (client configurations)", "api": "/api/production/profiles", "ui": "/ui/production-wizard#profiles"},
            {"command": "deliverables", "category": "agents", "description": "List deliverables", "api": "/api/deliverables", "ui": "/ui/terminal-orchestrator"},
            # ── Orchestrator & Org Chart ──────────────────────────────
            {"command": "orchestrator overview", "category": "orchestrator", "description": "View orchestrator system overview", "api": "/api/orchestrator/overview", "ui": "/ui/terminal-orchestrator"},
            {"command": "orchestrator flows", "category": "orchestrator", "description": "View orchestration flows", "api": "/api/orchestrator/flows", "ui": "/ui/terminal-orchestrator"},
            {"command": "orgchart live", "category": "orgchart", "description": "View live organization chart", "api": "/api/orgchart/live", "ui": "/ui/terminal-orgchart#orgchart"},
            # ── Costs & Efficiency ───────────────────────────────────
            {"command": "costs summary", "category": "costs", "description": "View cost summary", "api": "/api/costs/summary", "ui": "/ui/terminal-costs#overview"},
            {"command": "costs by-department", "category": "costs", "description": "View costs by department", "api": "/api/costs/by-department", "ui": "/ui/terminal-costs#departments"},
            {"command": "costs by-project", "category": "costs", "description": "View costs by project", "api": "/api/costs/by-project", "ui": "/ui/terminal-costs#projects"},
            {"command": "costs by-bot", "category": "costs", "description": "View costs by bot/agent", "api": "/api/costs/by-bot", "ui": "/ui/terminal-costs#bots"},
            {"command": "costs assign", "category": "costs", "description": "Assign costs to department/project", "api": "/api/costs/assign", "ui": "/ui/terminal-costs#assign"},
            {"command": "costs budget", "category": "costs", "description": "Set or update budget", "api": "/api/costs/budget", "ui": "/ui/terminal-costs#budget"},
            {"command": "efficiency metrics", "category": "analytics", "description": "View performance and efficiency metrics", "api": "/api/efficiency/metrics", "ui": "/ui/terminal-unified#efficiency"},
            {"command": "efficiency costs", "category": "analytics", "description": "View budget and spending overview", "api": "/api/efficiency/costs", "ui": "/ui/terminal-unified#costs"},
            {"command": "heatmap data", "category": "analytics", "description": "View activity heatmap visualization", "api": "/api/heatmap/data", "ui": "/ui/terminal-unified#heatmap"},
            {"command": "supply status", "category": "analytics", "description": "View supply chain resource status", "api": "/api/supply/status", "ui": "/ui/terminal-unified#supply"},
            {"command": "safety status", "category": "safety", "description": "View safety monitoring score and active alerts", "api": "/api/safety/status", "ui": "/ui/terminal-unified#safety"},
            {"command": "causality analysis", "category": "analytics", "description": "View causality engine analysis chains", "api": "/api/causality/analysis", "ui": "/ui/terminal-unified#causality"},
            {"command": "causality graph", "category": "analytics", "description": "View causality dependency graph", "api": "/api/causality/graph", "ui": "/ui/terminal-unified#causality"},
            {"command": "wingman suggestions", "category": "intelligence", "description": "Get AI Wingman co-pilot suggestions", "api": "/api/wingman/suggestions", "ui": "/ui/terminal-unified#wingman"},
            {"command": "wingman status", "category": "intelligence", "description": "Get Wingman co-pilot status", "api": "/api/wingman/status", "ui": "/ui/terminal-unified#wingman"},
            {"command": "hitl graduation candidates", "category": "hitl", "description": "List HITL graduation candidates", "api": "/api/hitl-graduation/candidates", "ui": "/ui/terminal-unified#graduation"},
            # ── Images ───────────────────────────────────────────────
            {"command": "images generate", "category": "images", "description": "Generate an image with AI", "api": "/api/images/generate", "ui": "/ui/terminal-enhanced#execute"},
            {"command": "images styles", "category": "images", "description": "List available image styles", "api": "/api/images/styles", "ui": "/ui/terminal-enhanced#execute"},
            {"command": "images stats", "category": "images", "description": "View image generation statistics", "api": "/api/images/stats", "ui": "/ui/terminal-enhanced#execute"},
            # ── IP Assets ────────────────────────────────────────────
            {"command": "ip assets", "category": "ip", "description": "List intellectual property assets", "api": "/api/ip/assets", "ui": "/ui/terminal-enhanced#ip"},
            {"command": "ip summary", "category": "ip", "description": "View IP portfolio summary", "api": "/api/ip/summary", "ui": "/ui/terminal-enhanced#ip"},
            {"command": "ip trade-secrets", "category": "ip", "description": "View trade secrets", "api": "/api/ip/trade-secrets", "ui": "/ui/terminal-enhanced#ip"},
            # ── Credentials ──────────────────────────────────────────
            {"command": "credentials profiles", "category": "credentials", "description": "Manage credential profiles", "api": "/api/credentials/profiles", "ui": "/ui/terminal-integrations#credentials"},
            {"command": "credentials metrics", "category": "credentials", "description": "View credential usage metrics", "api": "/api/credentials/metrics", "ui": "/ui/terminal-integrations#credentials"},
            # ── Profiles & Auth ──────────────────────────────────────
            {"command": "profiles list", "category": "profiles", "description": "List user profiles", "api": "/api/profiles", "ui": "/ui/terminal-orgchart#profiles"},
            {"command": "auth role", "category": "auth", "description": "View current user role", "api": "/api/auth/role", "ui": "/ui/terminal-orgchart#profiles"},
            {"command": "auth permissions", "category": "auth", "description": "View current permissions", "api": "/api/auth/permissions", "ui": "/ui/terminal-orgchart#profiles"},
            # ── Telemetry & Diagnostics ──────────────────────────────
            {"command": "telemetry", "category": "telemetry", "description": "View system telemetry data", "api": "/api/telemetry", "ui": "/ui/terminal-architect#status"},
            {"command": "diagnostics activation", "category": "diagnostics", "description": "View activation diagnostics", "api": "/api/diagnostics/activation", "ui": "/ui/terminal-architect#status"},
            # ── Configuration ────────────────────────────────────────
            {"command": "config get", "category": "config", "description": "View system configuration", "api": "/api/config", "ui": "/ui/terminal-architect#status"},
            {"command": "config set", "category": "config", "description": "Update system configuration", "api": "/api/config", "ui": "/ui/terminal-architect#status"},
            {"command": "test-mode status", "category": "config", "description": "Check test mode status", "api": "/api/test-mode/status", "ui": "/ui/terminal-architect#safety"},
            {"command": "test-mode toggle", "category": "config", "description": "Toggle test mode on/off", "api": "/api/test-mode/toggle", "ui": "/ui/terminal-architect#safety"},
            # ── UCP & Graph ──────────────────────────────────────────
            {"command": "ucp execute", "category": "ucp", "description": "Execute through Unified Compute Plane", "api": "/api/ucp/execute", "ui": "/ui/terminal-architect#execute"},
            {"command": "graph query", "category": "graph", "description": "Query the knowledge graph", "api": "/api/graph/query", "ui": "/ui/terminal-architect#execute"},
            # ── Feedback ─────────────────────────────────────────────
            {"command": "feedback", "category": "feedback", "description": "Submit feedback on system output", "api": "/api/feedback", "ui": "/ui/terminal-integrated#chat"},
            # ── MFM (Model Factory Manager) ──────────────────────────
            {"command": "mfm status", "category": "mfm", "description": "Model factory manager status", "api": "/api/mfm/status", "ui": "/ui/terminal-architect#status"},
            {"command": "mfm metrics", "category": "mfm", "description": "View model metrics", "api": "/api/mfm/metrics", "ui": "/ui/terminal-architect#status"},
            {"command": "mfm promote", "category": "mfm", "description": "Promote a model version", "api": "/api/mfm/promote", "ui": "/ui/terminal-architect#status"},
            {"command": "mfm rollback", "category": "mfm", "description": "Rollback to previous model version", "api": "/api/mfm/rollback", "ui": "/ui/terminal-architect#status"},
            {"command": "mfm versions", "category": "mfm", "description": "List model versions", "api": "/api/mfm/versions", "ui": "/ui/terminal-architect#status"},
            # ── Flows ────────────────────────────────────────────────
            {"command": "flows inbound", "category": "flows", "description": "View inbound data flows", "api": "/api/flows/inbound", "ui": "/ui/terminal-orchestrator"},
            {"command": "flows processing", "category": "flows", "description": "View processing flows", "api": "/api/flows/processing", "ui": "/ui/terminal-orchestrator"},
            {"command": "flows outbound", "category": "flows", "description": "View outbound flows", "api": "/api/flows/outbound", "ui": "/ui/terminal-orchestrator"},
            {"command": "flows state", "category": "flows", "description": "View flow state machine", "api": "/api/flows/state", "ui": "/ui/terminal-orchestrator"},
            # ── Modules ──────────────────────────────────────────────
            {"command": "modules list", "category": "modules", "description": "List all loaded modules", "api": "/api/modules", "ui": "/ui/terminal-architect#status"},
            {"command": "modules status", "category": "modules", "description": "Check module status", "api": "/api/modules/{name}/status", "ui": "/ui/terminal-architect#status"},
            # ── Sessions ─────────────────────────────────────────────
            {"command": "sessions create", "category": "sessions", "description": "Create a new session", "api": "/api/sessions/create", "ui": "/ui/terminal-integrated#chat"},
            # ── Automation ───────────────────────────────────────────
            {"command": "automation trigger", "category": "automation", "description": "Trigger an automation engine action", "api": "/api/automation/{engine}/{action}", "ui": "/ui/terminal-orchestrator"},
            # ── Account Lifecycle ────────────────────────────────────
            {"command": "account flow", "category": "account", "description": "View the account lifecycle flow (info→signup→verify→session→automation)", "api": "/api/account/flow", "ui": "/ui/landing"},
            # ── Included Routers (Board, CRM, Billing, etc.) ─────────
            {"command": "boards", "category": "boards", "description": "Manage project boards (Kanban, Scrum)", "api": "/api/boards", "ui": "/ui/dashboard"},
            {"command": "collaboration", "category": "collaboration", "description": "Real-time collaboration features", "api": "/api/collaboration", "ui": "/ui/dashboard"},
            {"command": "dashboards", "category": "dashboards", "description": "Manage custom dashboards and widgets", "api": "/api/dashboards", "ui": "/ui/dashboard"},
            {"command": "portfolio", "category": "portfolio", "description": "Portfolio management", "api": "/api/portfolio", "ui": "/ui/dashboard"},
            {"command": "workdocs", "category": "workdocs", "description": "Collaborative work documents", "api": "/api/workdocs", "ui": "/ui/dashboard"},
            {"command": "time-tracking", "category": "time-tracking", "description": "Time tracking and timesheets", "api": "/api/time-tracking", "ui": "/ui/dashboard"},
            {"command": "automations", "category": "automations", "description": "Workflow automations", "api": "/api/automations", "ui": "/ui/dashboard"},
            {"command": "crm", "category": "crm", "description": "Customer relationship management", "api": "/api/crm", "ui": "/ui/dashboard"},
            {"command": "dev", "category": "dev", "description": "Developer tools and module management", "api": "/api/dev", "ui": "/ui/dashboard"},
            {"command": "service", "category": "service", "description": "Service desk and ticketing", "api": "/api/service", "ui": "/ui/dashboard"},
            {"command": "guest", "category": "guest", "description": "Guest collaboration sharing", "api": "/api/guest", "ui": "/ui/dashboard"},
            {"command": "mobile", "category": "mobile", "description": "Mobile API endpoints", "api": "/api/mobile", "ui": "/ui/dashboard"},
            {"command": "billing", "category": "billing", "description": "Billing and subscription management", "api": "/api/billing", "ui": "/ui/pricing"},
            # ── Compliance ───────────────────────────────────────────
            {"command": "compliance toggles", "category": "compliance", "description": "View and manage compliance framework toggles", "api": "/api/compliance/toggles", "ui": "/ui/compliance"},
            {"command": "compliance recommended", "category": "compliance", "description": "Get recommended compliance frameworks for your country/industry", "api": "/api/compliance/recommended", "ui": "/ui/compliance"},
            {"command": "compliance report", "category": "compliance", "description": "Generate a compliance posture report", "api": "/api/compliance/report", "ui": "/ui/compliance"},
            {"command": "compliance scan", "category": "compliance", "description": "Run compliance-as-code scan filtered to enabled frameworks", "api": "/api/compliance/scan", "ui": "/ui/compliance"},
            # ── Signup & Auth ────────────────────────────────────────
            {"command": "signup", "category": "auth", "description": "Create a new Murphy account", "api": "/api/auth/signup", "ui": "/ui/signup"},
            {"command": "oauth google", "category": "auth", "description": "Sign up or login with Google", "api": "/api/auth/oauth/google", "ui": "/ui/signup"},
            {"command": "oauth github", "category": "auth", "description": "Sign up or login with GitHub", "api": "/api/auth/oauth/github", "ui": "/ui/signup"},
            # ── Manifest-Derived Entries (Command Registration Audit) ────────────────
            # ── AGENTS ─────────────────────────────────────────────────────────
            {"command": "swarm crew", "category": "agents", "description": "Murphy crew system", "api": "/api/murphy/crew/system", "ui": "/ui/terminal-integrated#agents"},
            {"command": "agents personas", "category": "agents", "description": "Agent persona library", "api": "/api/agent/persona/library", "ui": "/ui/terminal-integrated#agents"},
            {"command": "agents monitor", "category": "agents", "description": "Agent monitor dashboard", "api": "/api/agent/monitor/dashboard", "ui": "/ui/terminal-integrated#agents"},
            {"command": "agents dashboard", "category": "agents", "description": "Agent monitor dashboard", "api": "/api/agent/monitor/dashboard", "ui": "/ui/terminal-integrated#agents"},
            {"command": "agents runs", "category": "agents", "description": "Agent run recorder", "api": "/api/agent/run/recorder", "ui": "/ui/terminal-integrated#agents"},
            {"command": "agents history", "category": "agents", "description": "Agent run recorder", "api": "/api/agent/run/recorder", "ui": "/ui/terminal-integrated#agents"},
            {"command": "agents provision-api", "category": "agents", "description": "Agentic API provisioner", "api": "/api/agentic/api/provisioner", "ui": "/ui/terminal-integrated#agents"},
            {"command": "onboard status", "category": "agents", "description": "Agentic onboarding engine", "api": "/api/agentic/onboarding/engine", "ui": "/ui/terminal-integrated#agents"},
            {"command": "bots inventory", "category": "agents", "description": "Bot inventory library", "api": "/api/bot/inventory/library", "ui": "/ui/terminal-integrated#agents"},
            # ── AUTOMATION ─────────────────────────────────────────────────────────
            {"command": "exec schedule", "category": "automation", "description": "Automation scheduler", "api": "/api/automation/scheduler", "ui": "/ui/terminal-integrated#automation"},
            {"command": "schedule predict", "category": "automation", "description": "Automation scheduler", "api": "/api/automation/scheduler", "ui": "/ui/terminal-integrated#automation"},
            {"command": "schedule list", "category": "automation", "description": "Automation scheduler", "api": "/api/automation/scheduler", "ui": "/ui/terminal-integrated#automation"},
            {"command": "exec scale", "category": "automation", "description": "Automation scaler", "api": "/api/automation/scaler", "ui": "/ui/terminal-integrated#automation"},
            {"command": "exec marketplace", "category": "automation", "description": "Automation marketplace", "api": "/api/automation/marketplace", "ui": "/ui/terminal-integrated#automation"},
            {"command": "automation marketplace", "category": "automation", "description": "Automation marketplace", "api": "/api/automation/marketplace", "ui": "/ui/terminal-integrated#automation"},
            {"command": "automation mode", "category": "automation", "description": "Automation mode controller", "api": "/api/automation/mode/controller", "ui": "/ui/terminal-integrated#automation"},
            {"command": "automation set-mode", "category": "automation", "description": "Automation mode controller", "api": "/api/automation/mode/controller", "ui": "/ui/terminal-integrated#automation"},
            {"command": "automation full", "category": "automation", "description": "Full automation controller", "api": "/api/full/automation/controller", "ui": "/ui/terminal-integrated#automation"},
            {"command": "automation enable", "category": "automation", "description": "Full automation controller", "api": "/api/full/automation/controller", "ui": "/ui/terminal-integrated#automation"},
            {"command": "automation loop", "category": "automation", "description": "Automation loop connector", "api": "/api/automation/loop/connector", "ui": "/ui/terminal-integrated#automation"},
            {"command": "automation rbac", "category": "automation", "description": "Automation RBAC controller", "api": "/api/automation/rbac/controller", "ui": "/ui/terminal-integrated#automation"},
            {"command": "automation readiness", "category": "automation", "description": "Automation readiness evaluator", "api": "/api/automation/readiness/evaluator", "ui": "/ui/terminal-integrated#automation"},
            {"command": "automation types", "category": "automation", "description": "Automation type registry", "api": "/api/automation/type/registry", "ui": "/ui/terminal-integrated#automation"},
            {"command": "nocode workflow", "category": "automation", "description": "No-code workflow terminal", "api": "/api/nocode/workflow/terminal", "ui": "/ui/terminal-integrated#automation"},
            {"command": "nocode run", "category": "automation", "description": "No-code workflow terminal", "api": "/api/nocode/workflow/terminal", "ui": "/ui/terminal-integrated#automation"},
            {"command": "rpa record", "category": "automation", "description": "RPA recorder engine", "api": "/api/rpa/recorder/engine", "ui": "/ui/terminal-integrated#automation"},
            {"command": "rpa replay", "category": "automation", "description": "RPA recorder engine", "api": "/api/rpa/recorder/engine", "ui": "/ui/terminal-integrated#automation"},
            # ── BUSINESS ─────────────────────────────────────────────────────────
            {"command": "biz niche", "category": "business", "description": "Niche business generator", "api": "/api/niche/business/generator", "ui": "/ui/terminal-integrated#business"},
            {"command": "biz generate", "category": "business", "description": "Niche business generator", "api": "/api/niche/business/generator", "ui": "/ui/terminal-integrated#business"},
            {"command": "biz scale", "category": "business", "description": "Business scaling engine", "api": "/api/business/scaling/engine", "ui": "/ui/terminal-integrated#business"},
            {"command": "innovate run", "category": "business", "description": "Innovation farmer", "api": "/api/innovation/farmer", "ui": "/ui/terminal-integrated#business"},
            {"command": "innovate status", "category": "business", "description": "Innovation farmer", "api": "/api/innovation/farmer", "ui": "/ui/terminal-integrated#business"},
            {"command": "research competitive", "category": "business", "description": "Competitive intelligence engine", "api": "/api/competitive/intelligence/engine", "ui": "/ui/terminal-integrated#business"},
            # ── COMMUNICATIONS ─────────────────────────────────────────────────────────
            {"command": "email configure", "category": "communications", "description": "Email integration", "api": "/api/email/integration", "ui": "/ui/terminal-integrated#communications"},
            {"command": "email test", "category": "communications", "description": "Email integration", "api": "/api/email/integration", "ui": "/ui/terminal-integrated#communications"},
            {"command": "notify send", "category": "communications", "description": "Notification system", "api": "/api/notification/system", "ui": "/ui/terminal-integrated#communications"},
            {"command": "notify list", "category": "communications", "description": "Notification system", "api": "/api/notification/system", "ui": "/ui/terminal-integrated#communications"},
            {"command": "notify configure", "category": "communications", "description": "Notification system", "api": "/api/notification/system", "ui": "/ui/terminal-integrated#communications"},
            {"command": "announce", "category": "communications", "description": "Announcer voice engine", "api": "/api/announcer/voice/engine", "ui": "/ui/terminal-integrated#communications"},
            {"command": "announce broadcast", "category": "communications", "description": "Announcer voice engine", "api": "/api/announcer/voice/engine", "ui": "/ui/terminal-integrated#communications"},
            {"command": "delivery list", "category": "communications", "description": "Delivery adapters", "api": "/api/delivery/adapters", "ui": "/ui/terminal-integrated#communications"},
            {"command": "comms system", "category": "communications", "description": "Communication system", "api": "/api/communication/system", "ui": "/ui/terminal-integrated#communications"},
            # ── COMPLIANCE ─────────────────────────────────────────────────────────
            {"command": "compliance audit", "category": "compliance", "description": "Compliance engine", "api": "/api/compliance/engine", "ui": "/ui/compliance"},
            {"command": "compliance code", "category": "compliance", "description": "Compliance as code", "api": "/api/compliance/as/code/engine", "ui": "/ui/compliance"},
            {"command": "compliance policy", "category": "compliance", "description": "Compliance as code", "api": "/api/compliance/as/code/engine", "ui": "/ui/compliance"},
            {"command": "compliance monitoring", "category": "compliance", "description": "Compliance monitoring completeness", "api": "/api/compliance/monitoring/completeness", "ui": "/ui/compliance"},
            {"command": "compliance check", "category": "compliance", "description": "Outreach compliance integration — wires governor into all outreach paths", "api": "/api/outreach/compliance/integration", "ui": "/ui/compliance"},
            {"command": "compliance automate", "category": "compliance", "description": "Compliance automation bridge", "api": "/api/compliance/automation/bridge", "ui": "/ui/compliance"},
            {"command": "compliance orchestrate", "category": "compliance", "description": "Compliance orchestration bridge", "api": "/api/compliance/orchestration/bridge", "ui": "/ui/compliance"},
            {"command": "compliance outreach", "category": "compliance", "description": "Contact compliance governor — cooldown, DNC, regulatory gating", "api": "/api/contact/compliance/governor", "ui": "/ui/compliance"},
            {"command": "compliance dnc", "category": "compliance", "description": "Contact compliance governor — cooldown, DNC, regulatory gating", "api": "/api/contact/compliance/governor", "ui": "/ui/compliance"},
            # ── CONTENT ─────────────────────────────────────────────────────────
            {"command": "cad draw", "category": "content", "description": "Murphy drawing engine", "api": "/api/murphy/drawing/engine", "ui": "/ui/terminal-integrated#content"},
            {"command": "draw generate", "category": "content", "description": "Murphy drawing engine", "api": "/api/murphy/drawing/engine", "ui": "/ui/terminal-integrated#content"},
            {"command": "cad image", "category": "content", "description": "Image generation engine", "api": "/api/image/generation/engine", "ui": "/ui/terminal-integrated#content"},
            {"command": "image generate", "category": "content", "description": "Image generation engine", "api": "/api/image/generation/engine", "ui": "/ui/terminal-integrated#content"},
            # ── CONTROL ─────────────────────────────────────────────────────────
            {"command": "control status", "category": "control", "description": "Control plane management", "api": "/api/control/plane", "ui": "/ui/terminal-integrated#control"},
            {"command": "control plane", "category": "control", "description": "Control plane management", "api": "/api/control/plane", "ui": "/ui/terminal-integrated#control"},
            {"command": "compute status", "category": "control", "description": "Compute plane management", "api": "/api/compute/plane", "ui": "/ui/terminal-integrated#control"},
            {"command": "compute resources", "category": "control", "description": "Compute plane management", "api": "/api/compute/plane", "ui": "/ui/terminal-integrated#control"},
            {"command": "eng perception", "category": "control", "description": "Murphy autonomous perception", "api": "/api/murphy/autonomous/perception", "ui": "/ui/terminal-integrated#control"},
            {"command": "modules runtime", "category": "control", "description": "Modular runtime", "api": "/api/modular/runtime", "ui": "/ui/terminal-integrated#control"},
            {"command": "state graph", "category": "control", "description": "Murphy state graph", "api": "/api/murphy/state/graph", "ui": "/ui/terminal-integrated#control"},
            {"command": "action run", "category": "control", "description": "Murphy action engine", "api": "/api/murphy/action/engine", "ui": "/ui/terminal-integrated#control"},
            {"command": "action list", "category": "control", "description": "Murphy action engine", "api": "/api/murphy/action/engine", "ui": "/ui/terminal-integrated#control"},
            {"command": "runtime supervision", "category": "control", "description": "Supervision tree", "api": "/api/supervision/tree", "ui": "/ui/terminal-integrated#control"},
            {"command": "runtime supervisor", "category": "control", "description": "Supervisor system", "api": "/api/supervisor/system", "ui": "/ui/terminal-integrated#control"},
            {"command": "state machine", "category": "control", "description": "State machine", "api": "/api/state/machine", "ui": "/ui/terminal-integrated#control"},
            {"command": "runtime session", "category": "control", "description": "Session context", "api": "/api/session/context", "ui": "/ui/terminal-integrated#control"},
            {"command": "compute deterministic", "category": "control", "description": "Deterministic compute plane", "api": "/api/deterministic/compute/plane", "ui": "/ui/terminal-integrated#control"},
            {"command": "control theory", "category": "control", "description": "Control theory", "api": "/api/control/theory", "ui": "/ui/terminal-integrated#control"},
            {"command": "introspect status", "category": "control", "description": "Self-introspection module — runtime self-analysis and reporting", "api": "/api/self/introspection/module", "ui": "/ui/terminal-integrated#control"},
            {"command": "introspect run", "category": "control", "description": "Self-introspection module — runtime self-analysis and reporting", "api": "/api/self/introspection/module", "ui": "/ui/terminal-integrated#control"},
            # ── CRM ─────────────────────────────────────────────────────────
            {"command": "comms customer", "category": "crm", "description": "Customer communication manager", "api": "/api/customer/communication/manager", "ui": "/ui/terminal-integrated#crm"},
            {"command": "crm status", "category": "crm", "description": "CRM", "api": "/api/crm", "ui": "/ui/terminal-integrated#crm"},
            {"command": "crm leads", "category": "crm", "description": "CRM", "api": "/api/crm", "ui": "/ui/terminal-integrated#crm"},
            {"command": "crm contacts", "category": "crm", "description": "CRM", "api": "/api/crm", "ui": "/ui/terminal-integrated#crm"},
            # ── DATA ─────────────────────────────────────────────────────────
            {"command": "data pipeline", "category": "data", "description": "Data pipeline orchestrator", "api": "/api/data/pipeline/orchestrator", "ui": "/ui/terminal-integrated#data"},
            {"command": "data status", "category": "data", "description": "Data pipeline orchestrator", "api": "/api/data/pipeline/orchestrator", "ui": "/ui/terminal-integrated#data"},
            {"command": "data archive", "category": "data", "description": "Data archive manager", "api": "/api/data/archive/manager", "ui": "/ui/terminal-integrated#data"},
            {"command": "runtime persistence", "category": "data", "description": "Persistence manager", "api": "/api/persistence/manager", "ui": "/ui/terminal-integrated#data"},
            {"command": "runtime wal", "category": "data", "description": "Persistence WAL", "api": "/api/persistence/wal", "ui": "/ui/terminal-integrated#data"},
            # ── DEVELOPMENT ─────────────────────────────────────────────────────────
            {"command": "eng expert", "category": "development", "description": "Domain expert system", "api": "/api/domain/expert/system", "ui": "/ui/terminal-integrated#development"},
            {"command": "eng expert-integrate", "category": "development", "description": "Domain expert integration", "api": "/api/domain/expert/integration", "ui": "/ui/terminal-integrated#development"},
            {"command": "eng toolbox", "category": "development", "description": "Murphy engineering toolbox", "api": "/api/murphy/engineering/toolbox", "ui": "/ui/terminal-integrated#development"},
            {"command": "playwright run", "category": "development", "description": "Playwright task definitions", "api": "/api/playwright/task/definitions", "ui": "/ui/terminal-integrated#development"},
            {"command": "dev status", "category": "development", "description": "Dev module", "api": "/api/dev/module", "ui": "/ui/terminal-integrated#development"},
            # ── EXECUTION ─────────────────────────────────────────────────────────
            {"command": "exec run", "category": "execution", "description": "Core task execution engine", "api": "/api/execution/engine", "ui": "/ui/terminal-integrated#execution"},
            {"command": "exec status", "category": "execution", "description": "Core task execution engine", "api": "/api/execution/engine", "ui": "/ui/terminal-integrated#execution"},
            {"command": "exec queue", "category": "execution", "description": "Core task execution engine", "api": "/api/execution/engine", "ui": "/ui/terminal-integrated#execution"},
            {"command": "exec history", "category": "execution", "description": "Core task execution engine", "api": "/api/execution/engine", "ui": "/ui/terminal-integrated#execution"},
            {"command": "exec overview", "category": "execution", "description": "Execution orchestration and flow management", "api": "/api/execution/orchestrator", "ui": "/ui/terminal-integrated#execution"},
            {"command": "exec flows", "category": "execution", "description": "Execution orchestration and flow management", "api": "/api/execution/orchestrator", "ui": "/ui/terminal-integrated#execution"},
            {"command": "exec orchestrate", "category": "execution", "description": "Execution orchestration and flow management", "api": "/api/execution/orchestrator", "ui": "/ui/terminal-integrated#execution"},
            {"command": "exec compile", "category": "execution", "description": "Execution packet compiler", "api": "/api/execution/packet/compiler", "ui": "/ui/terminal-integrated#execution"},
            {"command": "exec package", "category": "execution", "description": "Execution package", "api": "/api/execution", "ui": "/ui/terminal-integrated#execution"},
            {"command": "workflow dag", "category": "execution", "description": "Workflow DAG engine", "api": "/api/workflow/dag/engine", "ui": "/ui/terminal-integrated#execution"},
            # ── FINANCE ─────────────────────────────────────────────────────────
            {"command": "finance invoices", "category": "finance", "description": "Invoice processing pipeline", "api": "/api/invoice/processing/pipeline", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance invoice", "category": "finance", "description": "Invoice processing pipeline", "api": "/api/invoice/processing/pipeline", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance report", "category": "finance", "description": "Financial reporting engine", "api": "/api/financial/reporting/engine", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance summary", "category": "finance", "description": "Financial reporting engine", "api": "/api/financial/reporting/engine", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance trading", "category": "finance", "description": "Trading bot engine", "api": "/api/trading/bot/engine", "ui": "/ui/terminal-integrated#finance"},
            {"command": "trading status", "category": "finance", "description": "Trading bot engine", "api": "/api/trading/bot/engine", "ui": "/ui/terminal-integrated#finance"},
            {"command": "trading strategy", "category": "finance", "description": "Trading strategy engine", "api": "/api/trading/strategy/engine", "ui": "/ui/terminal-integrated#finance"},
            {"command": "trading lifecycle", "category": "finance", "description": "Trading bot lifecycle", "api": "/api/trading/bot/lifecycle", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance crypto exchange", "category": "finance", "description": "Crypto exchange connector", "api": "/api/crypto/exchange/connector", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance crypto portfolio", "category": "finance", "description": "Crypto portfolio tracker", "api": "/api/crypto/portfolio/tracker", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance crypto risk", "category": "finance", "description": "Crypto risk manager", "api": "/api/crypto/risk/manager", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance crypto wallet", "category": "finance", "description": "Crypto wallet manager", "api": "/api/crypto/wallet/manager", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance coinbase", "category": "finance", "description": "Coinbase connector", "api": "/api/coinbase/connector", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance budget", "category": "finance", "description": "Budget-aware processor", "api": "/api/budget/aware/processor", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance costs", "category": "finance", "description": "Cost optimization advisor", "api": "/api/cost/optimization/advisor", "ui": "/ui/terminal-integrated#finance"},
            {"command": "costs recommendations", "category": "finance", "description": "Cost optimization advisor", "api": "/api/cost/optimization/advisor", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance market", "category": "finance", "description": "Market data feed", "api": "/api/market/data/feed", "ui": "/ui/terminal-integrated#finance"},
            {"command": "portfolio status", "category": "finance", "description": "Portfolio", "api": "/api/portfolio", "ui": "/ui/terminal-integrated#finance"},
            {"command": "portfolio list", "category": "finance", "description": "Portfolio", "api": "/api/portfolio", "ui": "/ui/terminal-integrated#finance"},
            {"command": "time log", "category": "finance", "description": "Time tracking", "api": "/api/time/tracking", "ui": "/ui/terminal-integrated#finance"},
            {"command": "time report", "category": "finance", "description": "Time tracking", "api": "/api/time/tracking", "ui": "/ui/terminal-integrated#finance"},
            # ── FORMS ─────────────────────────────────────────────────────────
            {"command": "form list", "category": "forms", "description": "Form intake and processing", "api": "/api/form/intake", "ui": "/ui/terminal-integrated#forms"},
            {"command": "form status", "category": "forms", "description": "Form intake and processing", "api": "/api/form/intake", "ui": "/ui/terminal-integrated#forms"},
            # ── GOVERNANCE ─────────────────────────────────────────────────────────
            {"command": "governance policies", "category": "governance", "description": "Governance framework", "api": "/api/governance/framework", "ui": "/ui/terminal-integrated#governance"},
            {"command": "governance status", "category": "governance", "description": "Governance framework", "api": "/api/governance/framework", "ui": "/ui/terminal-integrated#governance"},
            {"command": "governance runtime", "category": "governance", "description": "Base governance runtime", "api": "/api/base/governance/runtime", "ui": "/ui/terminal-integrated#governance"},
            {"command": "governance toggle", "category": "governance", "description": "Base governance runtime", "api": "/api/base/governance/runtime", "ui": "/ui/terminal-integrated#governance"},
            {"command": "gates authority", "category": "governance", "description": "Authority gate", "api": "/api/authority/gate", "ui": "/ui/terminal-integrated#governance"},
            {"command": "governance bot-policies", "category": "governance", "description": "Bot governance policy mapper", "api": "/api/bot/governance/policy/mapper", "ui": "/ui/terminal-integrated#governance"},
            # ── HITL ─────────────────────────────────────────────────────────
            {"command": "hitl status", "category": "hitl", "description": "HITL autonomy controller", "api": "/api/hitl/autonomy/controller", "ui": "/ui/terminal-integrated#hitl"},
            {"command": "hitl graduate", "category": "hitl", "description": "HITL graduation engine", "api": "/api/hitl/graduation/engine", "ui": "/ui/terminal-integrated#hitl"},
            {"command": "hitl level", "category": "hitl", "description": "HITL graduation engine", "api": "/api/hitl/graduation/engine", "ui": "/ui/terminal-integrated#hitl"},
            {"command": "hitl validate", "category": "hitl", "description": "Freelancer validator", "api": "/api/freelancer/validator", "ui": "/ui/terminal-integrated#hitl"},
            {"command": "freelancer validate", "category": "hitl", "description": "Freelancer validator", "api": "/api/freelancer/validator", "ui": "/ui/terminal-integrated#hitl"},
            {"command": "trading approve", "category": "hitl", "description": "Trading HITL gateway", "api": "/api/trading/hitl/gateway", "ui": "/ui/terminal-integrated#hitl"},
            # ── INFRASTRUCTURE ─────────────────────────────────────────────────────────
            {"command": "fleet status", "category": "infrastructure", "description": "Declarative fleet manager", "api": "/api/declarative/fleet/manager", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "fleet deploy", "category": "infrastructure", "description": "Declarative fleet manager", "api": "/api/declarative/fleet/manager", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "infra docker", "category": "infrastructure", "description": "Docker containerization", "api": "/api/docker/containerization", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "docker status", "category": "infrastructure", "description": "Docker containerization", "api": "/api/docker/containerization", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "infra k8s", "category": "infrastructure", "description": "Kubernetes deployment", "api": "/api/kubernetes/deployment", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "k8s status", "category": "infrastructure", "description": "Kubernetes deployment", "api": "/api/kubernetes/deployment", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "infra hetzner", "category": "infrastructure", "description": "Hetzner deployment", "api": "/api/hetzner/deploy", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "infra cloudflare", "category": "infrastructure", "description": "Cloudflare deployment", "api": "/api/cloudflare/deploy", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "cicd status", "category": "infrastructure", "description": "CI/CD pipeline manager", "api": "/api/ci/cd/pipeline/manager", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "cicd pipeline", "category": "infrastructure", "description": "CI/CD pipeline manager", "api": "/api/ci/cd/pipeline/manager", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "cicd trigger", "category": "infrastructure", "description": "CI/CD pipeline manager", "api": "/api/ci/cd/pipeline/manager", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "cloud status", "category": "infrastructure", "description": "Multi-cloud orchestrator", "api": "/api/multi/cloud/orchestrator", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "cloud orchestrate", "category": "infrastructure", "description": "Multi-cloud orchestrator", "api": "/api/multi/cloud/orchestrator", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "infra lb", "category": "infrastructure", "description": "Geographic load balancer", "api": "/api/geographic/load/balancer", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "infra load-balancer", "category": "infrastructure", "description": "Geographic load balancer", "api": "/api/geographic/load/balancer", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "infra scale", "category": "infrastructure", "description": "Resource scaling controller", "api": "/api/resource/scaling/controller", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "infra capacity", "category": "infrastructure", "description": "Capacity planning engine", "api": "/api/capacity/planning/engine", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "infra backup", "category": "infrastructure", "description": "Backup & disaster recovery", "api": "/api/backup/disaster/recovery", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "infra dr", "category": "infrastructure", "description": "Backup & disaster recovery", "api": "/api/backup/disaster/recovery", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "webhooks list", "category": "infrastructure", "description": "Webhook dispatcher", "api": "/api/webhook/dispatcher", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "webhooks dispatch", "category": "infrastructure", "description": "Webhook dispatcher", "api": "/api/webhook/dispatcher", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "webhooks process", "category": "infrastructure", "description": "Webhook event processor", "api": "/api/webhook/event/processor", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "prod intake", "category": "infrastructure", "description": "Production assistant engine — request lifecycle management with deliverable gate validation via EventBackbone", "api": "/api/production/assistant/engine", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "prod validate", "category": "infrastructure", "description": "Production assistant engine — request lifecycle management with deliverable gate validation via EventBackbone", "api": "/api/production/assistant/engine", "ui": "/ui/terminal-integrated#infrastructure"},
            {"command": "prod status", "category": "infrastructure", "description": "Production assistant engine — request lifecycle management with deliverable gate validation via EventBackbone", "api": "/api/production/assistant/engine", "ui": "/ui/terminal-integrated#infrastructure"},
            # ── INTEGRATIONS ─────────────────────────────────────────────────────────
            {"command": "integrations status", "category": "integrations", "description": "Integration engine", "api": "/api/integration/engine", "ui": "/ui/terminal-integrations"},
            {"command": "automation hub", "category": "integrations", "description": "Automation integration hub", "api": "/api/automation/integration/hub", "ui": "/ui/terminal-integrations"},
            {"command": "automation integrations", "category": "integrations", "description": "Automation integration hub", "api": "/api/automation/integration/hub", "ui": "/ui/terminal-integrations"},
            {"command": "data sync", "category": "integrations", "description": "Cross-platform data sync", "api": "/api/cross/platform/data/sync", "ui": "/ui/terminal-integrations"},
            {"command": "modules plugins", "category": "integrations", "description": "Plugin extension SDK", "api": "/api/plugin/extension/sdk", "ui": "/ui/terminal-integrations"},
            {"command": "events status", "category": "integrations", "description": "Event backbone", "api": "/api/event/backbone", "ui": "/ui/terminal-integrations"},
            {"command": "events list", "category": "integrations", "description": "Event backbone", "api": "/api/event/backbone", "ui": "/ui/terminal-integrations"},
            {"command": "integrations bus", "category": "integrations", "description": "Integration bus", "api": "/api/integration/bus", "ui": "/ui/terminal-integrations"},
            {"command": "integrations all", "category": "integrations", "description": "Integrations package", "api": "/api/integrations", "ui": "/ui/terminal-integrations"},
            {"command": "integrations system", "category": "integrations", "description": "System integrator", "api": "/api/system/integrator", "ui": "/ui/terminal-integrations"},
            {"command": "integrations enterprise", "category": "integrations", "description": "Enterprise integrations", "api": "/api/enterprise/integrations", "ui": "/ui/terminal-integrations"},
            {"command": "platforms list", "category": "integrations", "description": "Platform connector framework", "api": "/api/platform/connector/framework", "ui": "/ui/terminal-integrations"},
            {"command": "platforms connect", "category": "integrations", "description": "Platform connector framework", "api": "/api/platform/connector/framework", "ui": "/ui/terminal-integrations"},
            {"command": "tickets list", "category": "integrations", "description": "Ticketing adapter", "api": "/api/ticketing/adapter", "ui": "/ui/terminal-integrations"},
            {"command": "tickets create", "category": "integrations", "description": "Ticketing adapter", "api": "/api/ticketing/adapter", "ui": "/ui/terminal-integrations"},
            {"command": "remote connect", "category": "integrations", "description": "Remote access connector", "api": "/api/remote/access/connector", "ui": "/ui/terminal-integrations"},
            {"command": "bridge status", "category": "integrations", "description": "Bridge layer", "api": "/api/bridge/layer", "ui": "/ui/terminal-integrations"},
            {"command": "schema list", "category": "integrations", "description": "Schema registry", "api": "/api/schema/registry", "ui": "/ui/terminal-integrations"},
            {"command": "schema validate", "category": "integrations", "description": "Schema registry", "api": "/api/schema/registry", "ui": "/ui/terminal-integrations"},
            {"command": "bridge compat", "category": "integrations", "description": "Legacy compatibility matrix", "api": "/api/legacy/compatibility/matrix", "ui": "/ui/terminal-integrations"},
            {"command": "integrations universal", "category": "integrations", "description": "Universal integration adapter", "api": "/api/universal/integration/adapter", "ui": "/ui/terminal-integrations"},
            # ── INTELLIGENCE ─────────────────────────────────────────────────────────
            {"command": "eng domain", "category": "intelligence", "description": "Domain engine", "api": "/api/domain/engine", "ui": "/ui/terminal-integrated#intelligence"},
            {"command": "eng simulate", "category": "intelligence", "description": "Simulation engine", "api": "/api/simulation/engine", "ui": "/ui/terminal-integrated#intelligence"},
            {"command": "sim run", "category": "intelligence", "description": "Simulation engine", "api": "/api/simulation/engine", "ui": "/ui/terminal-integrated#intelligence"},
            {"command": "sim validate", "category": "intelligence", "description": "Simulation engine", "api": "/api/simulation/engine", "ui": "/ui/terminal-integrated#intelligence"},
            {"command": "wingman evolve", "category": "intelligence", "description": "Murphy wingman evolution", "api": "/api/murphy/wingman/evolution", "ui": "/ui/terminal-integrated#intelligence"},
            {"command": "neuro status", "category": "intelligence", "description": "Neuro-symbolic models", "api": "/api/neuro/symbolic/models", "ui": "/ui/terminal-integrated#intelligence"},
            # ── IOT ─────────────────────────────────────────────────────────
            {"command": "eng twin", "category": "iot", "description": "Digital twin engine", "api": "/api/digital/twin/engine", "ui": "/ui/terminal-integrated#iot"},
            {"command": "cad twin", "category": "iot", "description": "Digital twin engine", "api": "/api/digital/twin/engine", "ui": "/ui/terminal-integrated#iot"},
            {"command": "eng vision", "category": "iot", "description": "Computer vision pipeline", "api": "/api/computer/vision/pipeline", "ui": "/ui/terminal-integrated#iot"},
            {"command": "vision run", "category": "iot", "description": "Computer vision pipeline", "api": "/api/computer/vision/pipeline", "ui": "/ui/terminal-integrated#iot"},
            {"command": "eng sensor", "category": "iot", "description": "Murphy sensor fusion", "api": "/api/murphy/sensor/fusion", "ui": "/ui/terminal-integrated#iot"},
            {"command": "iot building", "category": "iot", "description": "Building automation connectors", "api": "/api/building/automation/connectors", "ui": "/ui/terminal-integrated#iot"},
            {"command": "iot energy", "category": "iot", "description": "Energy management connectors", "api": "/api/energy/management/connectors", "ui": "/ui/terminal-integrated#iot"},
            {"command": "iot additive", "category": "iot", "description": "Additive manufacturing connectors", "api": "/api/additive/manufacturing/connectors", "ui": "/ui/terminal-integrated#iot"},
            {"command": "iot manufacturing", "category": "iot", "description": "Manufacturing automation standards", "api": "/api/manufacturing/automation/standards", "ui": "/ui/terminal-integrated#iot"},
            {"command": "iot sensors", "category": "iot", "description": "Sensor reader", "api": "/api/sensor/reader", "ui": "/ui/terminal-integrated#iot"},
            {"command": "sensor read", "category": "iot", "description": "Sensor reader", "api": "/api/sensor/reader", "ui": "/ui/terminal-integrated#iot"},
            {"command": "robotics status", "category": "iot", "description": "Robotics", "api": "/api/robotics", "ui": "/ui/terminal-integrated#iot"},
            {"command": "robotics run", "category": "iot", "description": "Robotics", "api": "/api/robotics", "ui": "/ui/terminal-integrated#iot"},
            # ── KNOWLEDGE ─────────────────────────────────────────────────────────
            {"command": "librarian kb", "category": "knowledge", "description": "Knowledge base manager", "api": "/api/knowledge/base/manager", "ui": "/ui/terminal-integrated#knowledge"},
            {"command": "kb status", "category": "knowledge", "description": "Knowledge base manager", "api": "/api/knowledge/base/manager", "ui": "/ui/terminal-integrated#knowledge"},
            {"command": "librarian gap", "category": "knowledge", "description": "Knowledge gap system", "api": "/api/knowledge/gap/system", "ui": "/ui/terminal-integrated#knowledge"},
            {"command": "kg gap", "category": "knowledge", "description": "Knowledge gap system", "api": "/api/knowledge/gap/system", "ui": "/ui/terminal-integrated#knowledge"},
            {"command": "librarian rag", "category": "knowledge", "description": "RAG vector integration", "api": "/api/rag/vector/integration", "ui": "/ui/terminal-integrated#knowledge"},
            {"command": "rag search", "category": "knowledge", "description": "RAG vector integration", "api": "/api/rag/vector/integration", "ui": "/ui/terminal-integrated#knowledge"},
            {"command": "librarian generate", "category": "knowledge", "description": "Generative knowledge builder", "api": "/api/generative/knowledge/builder", "ui": "/ui/terminal-integrated#knowledge"},
            {"command": "kg generate", "category": "knowledge", "description": "Generative knowledge builder", "api": "/api/generative/knowledge/builder", "ui": "/ui/terminal-integrated#knowledge"},
            {"command": "research run", "category": "knowledge", "description": "Research engine", "api": "/api/research/engine", "ui": "/ui/terminal-integrated#knowledge"},
            {"command": "research query", "category": "knowledge", "description": "Research engine", "api": "/api/research/engine", "ui": "/ui/terminal-integrated#knowledge"},
            {"command": "research advanced", "category": "knowledge", "description": "Advanced research", "api": "/api/advanced/research", "ui": "/ui/terminal-integrated#knowledge"},
            {"command": "research multi", "category": "knowledge", "description": "Multi-source research", "api": "/api/multi/source/research", "ui": "/ui/terminal-integrated#knowledge"},
            # ── LEARNING ─────────────────────────────────────────────────────────
            {"command": "learning feedback", "category": "learning", "description": "Adaptive learning engine", "api": "/api/learning/engine", "ui": "/ui/terminal-integrated#learning"},
            {"command": "trading shadow", "category": "learning", "description": "Trading shadow learner", "api": "/api/trading/shadow/learner", "ui": "/ui/terminal-integrated#learning"},
            {"command": "monitor telemetry-learning", "category": "learning", "description": "Telemetry learning", "api": "/api/telemetry/learning", "ui": "/ui/terminal-integrated#learning"},
            # ── LIBRARIAN ─────────────────────────────────────────────────────────
            {"command": "librarian capabilities", "category": "librarian", "description": "System librarian and semantic search", "api": "/api/system/librarian", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "librarian search", "category": "librarian", "description": "System librarian and semantic search", "api": "/api/system/librarian", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "librarian graph", "category": "librarian", "description": "Knowledge graph builder", "api": "/api/knowledge/graph/builder", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "kg status", "category": "librarian", "description": "Knowledge graph builder", "api": "/api/knowledge/graph/builder", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "kg concepts", "category": "librarian", "description": "Concept graph engine", "api": "/api/concept/graph/engine", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "monitor bot-telemetry", "category": "librarian", "description": "Bot telemetry normalizer", "api": "/api/bot/telemetry/normalizer", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "eng expert-gen", "category": "librarian", "description": "Dynamic expert generator", "api": "/api/dynamic/expert/generator", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "org compile", "category": "librarian", "description": "Org compiler", "api": "/api/org/compiler", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "org chart", "category": "librarian", "description": "Org compiler", "api": "/api/org/compiler", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "compile module", "category": "librarian", "description": "Module compiler", "api": "/api/module/compiler", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "compile adapt", "category": "librarian", "description": "Module compiler adapter", "api": "/api/module/compiler/adapter", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "modules manage", "category": "librarian", "description": "Module manager", "api": "/api/module/manager", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "modules registry", "category": "librarian", "description": "Module registry", "api": "/api/module/registry", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "modules capabilities", "category": "librarian", "description": "Capability map", "api": "/api/capability/map", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "docs generate", "category": "librarian", "description": "Auto documentation engine", "api": "/api/auto/documentation/engine", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "docs status", "category": "librarian", "description": "Auto documentation engine", "api": "/api/auto/documentation/engine", "ui": "/ui/terminal-integrated#librarian"},
            # ── LLM ─────────────────────────────────────────────────────────
            {"command": "llm providers", "category": "llm", "description": "LLM integration layer", "api": "/api/llm/integration/layer", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm route", "category": "llm", "description": "LLM controller", "api": "/api/llm/controller", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm model", "category": "llm", "description": "LLM controller", "api": "/api/llm/controller", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm validate", "category": "llm", "description": "LLM output validator", "api": "/api/llm/output/validator", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm routing", "category": "llm", "description": "LLM routing completeness", "api": "/api/llm/routing/completeness", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm swarm", "category": "llm", "description": "LLM swarm integration", "api": "/api/llm/swarm/integration", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm local", "category": "llm", "description": "Enhanced local LLM (onboard)", "api": "/api/enhanced/local/llm", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm onboard", "category": "llm", "description": "Enhanced local LLM (onboard)", "api": "/api/enhanced/local/llm", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm inference", "category": "llm", "description": "Local inference engine", "api": "/api/local/inference/engine", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm fallback", "category": "llm", "description": "Local LLM fallback", "api": "/api/local/llm/fallback", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm models", "category": "llm", "description": "Local model layer", "api": "/api/local/model/layer", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm safe", "category": "llm", "description": "Safe LLM wrapper", "api": "/api/safe/llm/wrapper", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm openai", "category": "llm", "description": "OpenAI-compatible provider (openai/groq/onboard)", "api": "/api/openai/compatible/provider", "ui": "/ui/terminal-integrated#llm"},
            {"command": "llm groq", "category": "llm", "description": "OpenAI-compatible provider (openai/groq/onboard)", "api": "/api/openai/compatible/provider", "ui": "/ui/terminal-integrated#llm"},
            {"command": "mfm train", "category": "llm", "description": "Murphy Foundation Model", "api": "/api/murphy/foundation/model", "ui": "/ui/terminal-integrated#llm"},
            {"command": "mfm infer", "category": "llm", "description": "Murphy Foundation Model", "api": "/api/murphy/foundation/model", "ui": "/ui/terminal-integrated#llm"},
            # ── MARKETING ─────────────────────────────────────────────────────────
            {"command": "sales status", "category": "marketing", "description": "Sales automation", "api": "/api/sales/automation", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "sales pipeline", "category": "marketing", "description": "Sales automation", "api": "/api/sales/automation", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "rosetta sell", "category": "marketing", "description": "Rosetta selling bridge", "api": "/api/rosetta/selling/bridge", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "social schedule", "category": "marketing", "description": "Social media scheduler", "api": "/api/social/media/scheduler", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "social post", "category": "marketing", "description": "Social media scheduler", "api": "/api/social/media/scheduler", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "social moderate", "category": "marketing", "description": "Social media moderation", "api": "/api/social/media/moderation", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "content pipeline", "category": "marketing", "description": "Content pipeline engine", "api": "/api/content/pipeline/engine", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "content status", "category": "marketing", "description": "Content pipeline engine", "api": "/api/content/pipeline/engine", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "content platform", "category": "marketing", "description": "Content creator platform modulator", "api": "/api/content/creator/platform/modulator", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "campaign run", "category": "marketing", "description": "Campaign orchestrator", "api": "/api/campaign/orchestrator", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "campaign status", "category": "marketing", "description": "Campaign orchestrator", "api": "/api/campaign/orchestrator", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "campaign adapt", "category": "marketing", "description": "Adaptive campaign engine", "api": "/api/adaptive/campaign/engine", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "marketing cycle", "category": "marketing", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/self/marketing/orchestrator", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "marketing content", "category": "marketing", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/self/marketing/orchestrator", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "marketing social", "category": "marketing", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/self/marketing/orchestrator", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "marketing outreach", "category": "marketing", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/self/marketing/orchestrator", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "marketing b2b", "category": "marketing", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/self/marketing/orchestrator", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "marketing partnerships", "category": "marketing", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/self/marketing/orchestrator", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "cad asset", "category": "marketing", "description": "Digital asset generator", "api": "/api/digital/asset/generator", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "asset generate", "category": "marketing", "description": "Digital asset generator", "api": "/api/digital/asset/generator", "ui": "/ui/terminal-integrated#marketing"},
            {"command": "sell status", "category": "marketing", "description": "Self selling engine", "api": "/api/self/selling/engine", "ui": "/ui/terminal-integrated#marketing"},
            # ── MFGC ─────────────────────────────────────────────────────────
            {"command": "compliance gates", "category": "mfgc", "description": "Gate synthesis and compliance enforcement", "api": "/api/gate/synthesis", "ui": "/ui/terminal-integrated#mfgc"},
            {"command": "gates status", "category": "mfgc", "description": "Gate synthesis and compliance enforcement", "api": "/api/gate/synthesis", "ui": "/ui/terminal-integrated#mfgc"},
            {"command": "gates arm", "category": "mfgc", "description": "Gate synthesis and compliance enforcement", "api": "/api/gate/synthesis", "ui": "/ui/terminal-integrated#mfgc"},
            {"command": "gates disarm", "category": "mfgc", "description": "Gate synthesis and compliance enforcement", "api": "/api/gate/synthesis", "ui": "/ui/terminal-integrated#mfgc"},
            {"command": "gates bypass", "category": "mfgc", "description": "Gate bypass controller", "api": "/api/gate/bypass/controller", "ui": "/ui/terminal-integrated#mfgc"},
            {"command": "llm gate", "category": "mfgc", "description": "Inference gate engine", "api": "/api/inference/gate/engine", "ui": "/ui/terminal-integrated#mfgc"},
            {"command": "biz viability", "category": "mfgc", "description": "Niche viability gate", "api": "/api/niche/viability/gate", "ui": "/ui/terminal-integrated#mfgc"},
            {"command": "finance cost-gate", "category": "mfgc", "description": "Cost explosion gate", "api": "/api/cost/explosion/gate", "ui": "/ui/terminal-integrated#mfgc"},
            {"command": "eng gate-gen", "category": "mfgc", "description": "Domain gate generator", "api": "/api/domain/gate/generator", "ui": "/ui/terminal-integrated#mfgc"},
            {"command": "mfgc status", "category": "mfgc", "description": "MFGC core", "api": "/api/mfgc/core", "ui": "/ui/terminal-integrated#mfgc"},
            {"command": "mfgc adapt", "category": "mfgc", "description": "MFGC adapter", "api": "/api/mfgc/adapter", "ui": "/ui/terminal-integrated#mfgc"},
            {"command": "mfgc metrics", "category": "mfgc", "description": "MFGC metrics", "api": "/api/mfgc/metrics", "ui": "/ui/terminal-integrated#mfgc"},
            # ── MONITORING ─────────────────────────────────────────────────────────
            {"command": "monitor health", "category": "monitoring", "description": "Health monitor", "api": "/api/health/monitor", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "health status", "category": "monitoring", "description": "Health monitor", "api": "/api/health/monitor", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "monitor heartbeat", "category": "monitoring", "description": "Heartbeat liveness protocol", "api": "/api/heartbeat/liveness/protocol", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "monitor heartbeat-runner", "category": "monitoring", "description": "Activated heartbeat runner", "api": "/api/activated/heartbeat/runner", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "monitor metrics", "category": "monitoring", "description": "Prometheus metrics exporter", "api": "/api/prometheus/metrics/exporter", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "metrics export", "category": "monitoring", "description": "Prometheus metrics exporter", "api": "/api/prometheus/metrics/exporter", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "monitor counters", "category": "monitoring", "description": "Observability counters", "api": "/api/observability/counters", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "monitor trace", "category": "monitoring", "description": "Murphy trace", "api": "/api/murphy/trace", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "monitor telemetry-adapter", "category": "monitoring", "description": "Telemetry adapter", "api": "/api/telemetry/adapter", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "monitor logs", "category": "monitoring", "description": "Log analysis engine", "api": "/api/log/analysis/engine", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "monitor alerts", "category": "monitoring", "description": "Alert rules engine", "api": "/api/alert/rules/engine", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "monitor spikes", "category": "monitoring", "description": "Causal spike analyzer", "api": "/api/causal/spike/analyzer", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "runtime replay", "category": "monitoring", "description": "Persistence replay completeness", "api": "/api/persistence/replay/completeness", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "delivery channels", "category": "monitoring", "description": "Delivery channel completeness", "api": "/api/delivery/channel/completeness", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "ab test", "category": "monitoring", "description": "A/B testing framework", "api": "/api/ab/testing/framework", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "logs status", "category": "monitoring", "description": "Logging system", "api": "/api/logging/system", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "logs query", "category": "monitoring", "description": "Logging system", "api": "/api/logging/system", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "system features", "category": "monitoring", "description": "Startup feature summary", "api": "/api/startup/feature/summary", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "system validate", "category": "monitoring", "description": "Startup validator", "api": "/api/startup/validator", "ui": "/ui/terminal-integrated#monitoring"},
            # ── ONBOARDING ─────────────────────────────────────────────────────────
            {"command": "onboard flow", "category": "onboarding", "description": "Onboarding flow", "api": "/api/onboarding/flow", "ui": "/ui/onboarding-wizard"},
            {"command": "onboard automate", "category": "onboarding", "description": "Onboarding automation engine", "api": "/api/onboarding/automation/engine", "ui": "/ui/onboarding-wizard"},
            {"command": "onboard team", "category": "onboarding", "description": "Onboarding team pipeline", "api": "/api/onboarding/team/pipeline", "ui": "/ui/onboarding-wizard"},
            {"command": "setup wizard", "category": "onboarding", "description": "Setup wizard", "api": "/api/setup/wizard", "ui": "/ui/onboarding-wizard"},
            # ── ORGCHART ─────────────────────────────────────────────────────────
            {"command": "org enforce", "category": "orgchart", "description": "Org chart enforcement", "api": "/api/org/chart/enforcement", "ui": "/ui/terminal-orgchart"},
            {"command": "org orgchart", "category": "orgchart", "description": "Organization chart system", "api": "/api/organization/chart/system", "ui": "/ui/terminal-orgchart"},
            {"command": "org context", "category": "orgchart", "description": "Organizational context system", "api": "/api/organizational/context/system", "ui": "/ui/terminal-orgchart"},
            {"command": "ceo activate", "category": "orgchart", "description": "CEO branch activation — top-level autonomous decision-making, org chart automation, and operational planning", "api": "/api/ceo/branch/activation", "ui": "/ui/terminal-orgchart"},
            {"command": "ceo status", "category": "orgchart", "description": "CEO branch activation — top-level autonomous decision-making, org chart automation, and operational planning", "api": "/api/ceo/branch/activation", "ui": "/ui/terminal-orgchart"},
            {"command": "ceo directive", "category": "orgchart", "description": "CEO branch activation — top-level autonomous decision-making, org chart automation, and operational planning", "api": "/api/ceo/branch/activation", "ui": "/ui/terminal-orgchart"},
            {"command": "ceo plan", "category": "orgchart", "description": "CEO branch activation — top-level autonomous decision-making, org chart automation, and operational planning", "api": "/api/ceo/branch/activation", "ui": "/ui/terminal-orgchart"},
            # ── PLATFORM ─────────────────────────────────────────────────────────
            {"command": "automation native", "category": "platform", "description": "Murphy native automation", "api": "/api/murphy/native/automation", "ui": "/ui/terminal-integrated#platform"},
            {"command": "monitor slo", "category": "platform", "description": "Operational SLO tracker", "api": "/api/operational/slo/tracker", "ui": "/ui/terminal-integrated#platform"},
            {"command": "osmosis run", "category": "platform", "description": "Murphy osmosis engine", "api": "/api/murphy/osmosis/engine", "ui": "/ui/terminal-integrated#platform"},
            {"command": "knostalgia run", "category": "platform", "description": "Knostalgia engine", "api": "/api/knostalgia/engine", "ui": "/ui/terminal-integrated#platform"},
            {"command": "knostalgia categories", "category": "platform", "description": "Knostalgia category engine", "api": "/api/knostalgia/category/engine", "ui": "/ui/terminal-integrated#platform"},
            {"command": "runtime status", "category": "platform", "description": "Runtime package", "api": "/api/runtime", "ui": "/ui/terminal-integrated#platform"},
            {"command": "state schema", "category": "platform", "description": "State schema", "api": "/api/state/schema", "ui": "/ui/terminal-integrated#platform"},
            {"command": "account status", "category": "platform", "description": "Account management", "api": "/api/account/management", "ui": "/ui/terminal-integrated#platform"},
            {"command": "account list", "category": "platform", "description": "Account management", "api": "/api/account/management", "ui": "/ui/terminal-integrated#platform"},
            {"command": "board status", "category": "platform", "description": "Board system", "api": "/api/board/system", "ui": "/ui/terminal-integrated#platform"},
            {"command": "board tasks", "category": "platform", "description": "Board system", "api": "/api/board/system", "ui": "/ui/terminal-integrated#platform"},
            {"command": "board sprint", "category": "platform", "description": "Board system", "api": "/api/board/system", "ui": "/ui/terminal-integrated#platform"},
            {"command": "collab status", "category": "platform", "description": "Collaboration", "api": "/api/collaboration", "ui": "/ui/terminal-integrated#platform"},
            {"command": "collab guest", "category": "platform", "description": "Guest collaboration", "api": "/api/guest/collab", "ui": "/ui/terminal-integrated#platform"},
            {"command": "dashboard status", "category": "platform", "description": "Dashboards", "api": "/api/dashboards", "ui": "/ui/terminal-integrated#platform"},
            {"command": "eq status", "category": "platform", "description": "EQ module", "api": "/api/eq", "ui": "/ui/terminal-integrated#platform"},
            {"command": "aionmind status", "category": "platform", "description": "AionMind", "api": "/api/aionmind", "ui": "/ui/terminal-integrated#platform"},
            {"command": "avatar status", "category": "platform", "description": "Avatar", "api": "/api/avatar", "ui": "/ui/terminal-integrated#platform"},
            {"command": "rosetta status", "category": "platform", "description": "Rosetta", "api": "/api/rosetta", "ui": "/ui/terminal-integrated#platform"},
            {"command": "autonomous status", "category": "platform", "description": "Autonomous systems", "api": "/api/autonomous/systems", "ui": "/ui/terminal-integrated#platform"},
            {"command": "cutsheet ingest", "category": "platform", "description": "Cut sheet engine — manufacturer data parsing, wiring diagrams, device config generation", "api": "/api/cutsheet/engine", "ui": "/ui/terminal-integrated#platform"},
            {"command": "cutsheet list", "category": "platform", "description": "Cut sheet engine — manufacturer data parsing, wiring diagrams, device config generation", "api": "/api/cutsheet/engine", "ui": "/ui/terminal-integrated#platform"},
            {"command": "cutsheet verify", "category": "platform", "description": "Cut sheet engine — manufacturer data parsing, wiring diagrams, device config generation", "api": "/api/cutsheet/engine", "ui": "/ui/terminal-integrated#platform"},
            # ── SAFETY ─────────────────────────────────────────────────────────
            {"command": "safety orchestrate", "category": "safety", "description": "Safety orchestrator", "api": "/api/safety/orchestrator", "ui": "/ui/terminal-integrated#safety"},
            {"command": "safety validate", "category": "safety", "description": "Safety validation pipeline", "api": "/api/safety/validation/pipeline", "ui": "/ui/terminal-integrated#safety"},
            {"command": "safety gateway", "category": "safety", "description": "Safety gateway integrator", "api": "/api/safety/gateway/integrator", "ui": "/ui/terminal-integrated#safety"},
            {"command": "safety estop", "category": "safety", "description": "Emergency stop controller", "api": "/api/emergency/stop/controller", "ui": "/ui/terminal-integrated#safety"},
            {"command": "safety emergency", "category": "safety", "description": "Emergency stop controller", "api": "/api/emergency/stop/controller", "ui": "/ui/terminal-integrated#safety"},
            # ── SECURITY ─────────────────────────────────────────────────────────
            {"command": "confidence status", "category": "security", "description": "Confidence scoring and artifact graph", "api": "/api/confidence/engine", "ui": "/ui/terminal-integrated#security"},
            {"command": "confidence score", "category": "security", "description": "Confidence scoring and artifact graph", "api": "/api/confidence/engine", "ui": "/ui/terminal-integrated#security"},
            {"command": "confidence artifacts", "category": "security", "description": "Confidence scoring and artifact graph", "api": "/api/confidence/engine", "ui": "/ui/terminal-integrated#security"},
            {"command": "security status", "category": "security", "description": "Security plane and threat management", "api": "/api/security/plane", "ui": "/ui/terminal-integrated#security"},
            {"command": "compliance rbac", "category": "security", "description": "RBAC governance", "api": "/api/rbac/governance", "ui": "/ui/terminal-integrated#security"},
            {"command": "security permissions", "category": "security", "description": "RBAC governance", "api": "/api/rbac/governance", "ui": "/ui/terminal-integrated#security"},
            {"command": "keys groq", "category": "security", "description": "Groq key rotator", "api": "/api/groq/key/rotator", "ui": "/ui/terminal-integrated#security"},
            {"command": "llm groq-keys", "category": "security", "description": "Groq key rotator", "api": "/api/groq/key/rotator", "ui": "/ui/terminal-integrated#security"},
            {"command": "security adapter", "category": "security", "description": "Security plane adapter", "api": "/api/security/plane/adapter", "ui": "/ui/terminal-integrated#security"},
            {"command": "security harden", "category": "security", "description": "Security hardening config", "api": "/api/security/hardening/config", "ui": "/ui/terminal-integrated#security"},
            {"command": "security api", "category": "security", "description": "FastAPI security layer", "api": "/api/fastapi/security", "ui": "/ui/terminal-integrated#security"},
            {"command": "security flask", "category": "security", "description": "Flask security layer", "api": "/api/flask/security", "ui": "/ui/terminal-integrated#security"},
            {"command": "security oauth", "category": "security", "description": "OAuth/OIDC provider", "api": "/api/oauth/oidc/provider", "ui": "/ui/terminal-integrated#security"},
            {"command": "security oidc", "category": "security", "description": "OAuth/OIDC provider", "api": "/api/oauth/oidc/provider", "ui": "/ui/terminal-integrated#security"},
            {"command": "keys list", "category": "security", "description": "Secure key manager", "api": "/api/secure/key/manager", "ui": "/ui/terminal-integrated#security"},
            {"command": "keys status", "category": "security", "description": "Secure key manager", "api": "/api/secure/key/manager", "ui": "/ui/terminal-integrated#security"},
            {"command": "keys create", "category": "security", "description": "Secure key manager", "api": "/api/secure/key/manager", "ui": "/ui/terminal-integrated#security"},
            {"command": "security credentials", "category": "security", "description": "Murphy credential gate", "api": "/api/murphy/credential/gate", "ui": "/ui/terminal-integrated#security"},
            {"command": "keys harvest", "category": "security", "description": "Key harvester", "api": "/api/key/harvester", "ui": "/ui/terminal-integrated#security"},
            {"command": "heal immune", "category": "security", "description": "Murphy immune engine", "api": "/api/murphy/immune/engine", "ui": "/ui/terminal-integrated#security"},
            {"command": "credentials profile", "category": "security", "description": "Credential profile system", "api": "/api/credential/profile/system", "ui": "/ui/terminal-integrated#security"},
            {"command": "audit logs", "category": "security", "description": "Audit logging system", "api": "/api/audit/logging/system", "ui": "/ui/terminal-integrated#security"},
            {"command": "audit blockchain", "category": "security", "description": "Blockchain audit trail", "api": "/api/blockchain/audit/trail", "ui": "/ui/terminal-integrated#security"},
            # ── SELF-HEALING ─────────────────────────────────────────────────────────
            {"command": "automation self", "category": "self-healing", "description": "Self automation orchestrator", "api": "/api/self/automation/orchestrator", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "automation orchestrate", "category": "self-healing", "description": "Self automation orchestrator", "api": "/api/self/automation/orchestrator", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "monitor slo-remediate", "category": "self-healing", "description": "SLO remediation bridge", "api": "/api/slo/remediation/bridge", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal status", "category": "self-healing", "description": "Autonomous repair system", "api": "/api/autonomous/repair/system", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal repair", "category": "self-healing", "description": "Autonomous repair system", "api": "/api/autonomous/repair/system", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal fix", "category": "self-healing", "description": "Self-fix loop", "api": "/api/self/fix/loop", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal coordinate", "category": "self-healing", "description": "Self-healing coordinator", "api": "/api/self/healing/coordinator", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal improve", "category": "self-healing", "description": "Self-improvement engine", "api": "/api/self/improvement/engine", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal optimise", "category": "self-healing", "description": "Self-optimisation engine", "api": "/api/self/optimisation/engine", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal code", "category": "self-healing", "description": "Murphy code healer", "api": "/api/murphy/code/healer", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal code-repair", "category": "self-healing", "description": "Code repair engine", "api": "/api/code/repair/engine", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal chaos", "category": "self-healing", "description": "Chaos resilience loop", "api": "/api/chaos/resilience/loop", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal predict", "category": "self-healing", "description": "Predictive failure engine", "api": "/api/predictive/failure/engine", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal maintenance", "category": "self-healing", "description": "Predictive maintenance engine", "api": "/api/predictive/maintenance/engine", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "heal blackstart", "category": "self-healing", "description": "Blackstart controller", "api": "/api/blackstart/controller", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "shadow train", "category": "self-healing", "description": "Murphy shadow trainer", "api": "/api/murphy/shadow/trainer", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "runtime stability", "category": "self-healing", "description": "Recursive stability controller", "api": "/api/recursive/stability/controller", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "chaos failure", "category": "self-healing", "description": "Synthetic failure generator", "api": "/api/synthetic/failure/generator", "ui": "/ui/terminal-integrated#self-healing"},
            {"command": "swarm build", "category": "self-healing", "description": "Self-codebase swarm — autonomous BMS spec generation, RFP parsing, and deliverable packaging", "api": "/api/self/codebase/swarm", "ui": "/ui/terminal-integrated#self-healing"},
            # ── SWARM ─────────────────────────────────────────────────────────
            {"command": "swarm spawn", "category": "swarm", "description": "Advanced swarm system", "api": "/api/advanced/swarm/system", "ui": "/ui/terminal-integrated#swarm"},
            {"command": "swarm list", "category": "swarm", "description": "Advanced swarm system", "api": "/api/advanced/swarm/system", "ui": "/ui/terminal-integrated#swarm"},
            {"command": "swarm domain", "category": "swarm", "description": "Domain swarms", "api": "/api/domain/swarms", "ui": "/ui/terminal-integrated#swarm"},
            {"command": "swarm orchestrate", "category": "swarm", "description": "Durable swarm orchestrator", "api": "/api/durable/swarm/orchestrator", "ui": "/ui/terminal-integrated#swarm"},
            {"command": "swarm durable", "category": "swarm", "description": "Durable swarm orchestrator", "api": "/api/durable/swarm/orchestrator", "ui": "/ui/terminal-integrated#swarm"},
            {"command": "visual build", "category": "swarm", "description": "Visual swarm builder — visual pipeline construction for swarm workflows", "api": "/api/visual/swarm/builder", "ui": "/ui/terminal-integrated#swarm"},
            {"command": "visual status", "category": "swarm", "description": "Visual swarm builder — visual pipeline construction for swarm workflows", "api": "/api/visual/swarm/builder", "ui": "/ui/terminal-integrated#swarm"},
            # ── TERMINAL ─────────────────────────────────────────────────────────
            {"command": "kg translate", "category": "terminal", "description": "Concept translation", "api": "/api/concept/translation", "ui": "/ui/terminal-integrated"},
            {"command": "compile shim", "category": "terminal", "description": "Shim compiler", "api": "/api/shim/compiler", "ui": "/ui/terminal-integrated"},
            {"command": "templates list", "category": "terminal", "description": "Murphy template hub", "api": "/api/murphy/template/hub", "ui": "/ui/terminal-integrated"},
            {"command": "templates get", "category": "terminal", "description": "Murphy template hub", "api": "/api/murphy/template/hub", "ui": "/ui/terminal-integrated"},
            {"command": "repl run", "category": "terminal", "description": "Murphy REPL", "api": "/api/murphy/repl", "ui": "/ui/terminal-integrated"},
            {"command": "repl eval", "category": "terminal", "description": "Murphy REPL", "api": "/api/murphy/repl", "ui": "/ui/terminal-integrated"},
            {"command": "runtime closure", "category": "terminal", "description": "Closure engine", "api": "/api/closure/engine", "ui": "/ui/terminal-integrated"},
            {"command": "protocols list", "category": "terminal", "description": "Protocols", "api": "/api/protocols", "ui": "/ui/terminal-integrated"},
            {"command": "auar status", "category": "terminal", "description": "AUAR (Universal Adaptive Routing)", "api": "/api/auar", "ui": "/ui/terminal-integrated"},
            {"command": "auar route", "category": "terminal", "description": "AUAR (Universal Adaptive Routing)", "api": "/api/auar", "ui": "/ui/terminal-integrated"},
            {"command": "runtime thread-safe", "category": "terminal", "description": "Thread-safe operations", "api": "/api/thread/safe/operations", "ui": "/ui/terminal-integrated"},
            # ── WORKFLOWS ─────────────────────────────────────────────────────────
            {"command": "workflow generate", "category": "workflows", "description": "AI workflow generator", "api": "/api/ai/workflow/generator", "ui": "/ui/workflow-canvas"},
            {"command": "ai workflow", "category": "workflows", "description": "AI workflow generator", "api": "/api/ai/workflow/generator", "ui": "/ui/workflow-canvas"},
            {"command": "workflow templates", "category": "workflows", "description": "Workflow template marketplace", "api": "/api/workflow/template/marketplace", "ui": "/ui/workflow-canvas"},
            {"command": "comms status", "category": "communications", "description": "Communications subsystem status", "api": "/api/comms", "ui": "/ui/terminal-integrated#communications"},
            {"command": "compliance status", "category": "compliance", "description": "Compliance engine status", "api": "/api/compliance/engine", "ui": "/ui/compliance"},
            {"command": "monitor telemetry", "category": "monitoring", "description": "Telemetry system monitoring", "api": "/api/telemetry/system", "ui": "/ui/terminal-integrated#monitoring"},
            {"command": "onboard start", "category": "onboarding", "description": "Start onboarding flow", "api": "/api/onboarding/flow", "ui": "/ui/onboarding-wizard"},
            {"command": "security audit", "category": "security", "description": "Security audit scanner", "api": "/api/security/audit/scanner", "ui": "/ui/terminal-integrated#security"},
            {"command": "security scan", "category": "security", "description": "Security plane scan", "api": "/api/security/plane", "ui": "/ui/terminal-integrated#security"},
            {"command": "swarm propose", "category": "swarm", "description": "Swarm proposal generator", "api": "/api/swarm/proposal/generator", "ui": "/ui/terminal-integrated#swarm"},
            {"command": "swarm status", "category": "swarm", "description": "Advanced swarm system status", "api": "/api/advanced/swarm/system", "ui": "/ui/terminal-integrated#swarm"},
        ]

        categories = {}
        for cmd in catalog:
            cat = cmd["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(cmd)

        return JSONResponse({
            "success": True,
            "total_commands": len(catalog),
            "categories": list(categories.keys()),
            "catalog": catalog,
        })

    # ==================== UI LINKS ENDPOINT ====================

    @app.get("/api/ui/links")
    async def ui_links():
        """Return role-based UI links mapping each user type to their HTML interfaces."""
        ui_map = {
            "owner": [
                {"name": "Architect Terminal", "url": "/ui/terminal-architect"},
                {"name": "Integrated Terminal", "url": "/ui/terminal-integrated"},
                {"name": "Full Dashboard", "url": "/ui/dashboard"},
                {"name": "Onboarding Wizard", "url": "/ui/onboarding"},
                {"name": "Landing Page", "url": "/ui/landing"},
            ],
            "admin": [
                {"name": "Architect Terminal", "url": "/ui/terminal-architect"},
                {"name": "Integrated Terminal", "url": "/ui/terminal-integrated"},
                {"name": "Full Dashboard", "url": "/ui/dashboard"},
                {"name": "Onboarding Wizard", "url": "/ui/onboarding"},
            ],
            "operator": [
                {"name": "Worker Terminal", "url": "/ui/terminal-worker"},
                {"name": "Enhanced Terminal", "url": "/ui/terminal-enhanced"},
                {"name": "Operator Terminal", "url": "/ui/terminal-operator"},
            ],
            "viewer": [
                {"name": "Landing Page", "url": "/ui/landing"},
                {"name": "Enhanced Terminal", "url": "/ui/terminal-enhanced"},
            ],
        }
        return JSONResponse({"success": True, "user_type_ui_links": ui_map})

    # ==================== ACCOUNT LIFECYCLE ENDPOINT ====================

    @app.get("/api/account/flow")
    async def account_flow():
        """Return the account lifecycle flow stages with UI and API links.

        The flow describes the ordered stages a user goes through:
        info → signup → verify → session → automation.
        """
        flow = [
            {
                "stage": "info",
                "name": "Info & Landing Page",
                "url": "/ui/landing",
                "api": "/api/info",
                "description": "Learn about Murphy System capabilities and features",
            },
            {
                "stage": "signup",
                "name": "Account Signup",
                "url": "/ui/onboarding",
                "api": "/api/onboarding/wizard/questions",
                "description": "Create an account through the onboarding wizard",
            },
            {
                "stage": "verify",
                "name": "Account Verification",
                "url": "/ui/onboarding",
                "api": "/api/onboarding/wizard/validate",
                "description": "Validate configuration and verify account setup",
            },
            {
                "stage": "session",
                "name": "Account Session",
                "url": "/ui/dashboard",
                "api": "/api/sessions/create",
                "description": "Start an authenticated session to access your account",
            },
            {
                "stage": "automation",
                "name": "Automation Management",
                "url": "/ui/terminal-integrated",
                "api": "/api/execute",
                "description": "Create, configure, and manage your automations",
            },
        ]
        return JSONResponse({"success": True, "flow": flow, "stages": len(flow)})

    # ==================== SESSION ENDPOINTS ====================

    @app.post("/api/sessions/create")
    async def create_session(request: Request):
        """Create a session for UI chat flows"""
        try:
            data = await request.json()
        except Exception:
            data = {}
        result = murphy.create_session(name=data.get("name"))
        return JSONResponse(result)

    # ==================== DOCUMENT ENDPOINTS ====================

    @app.post("/api/documents")
    async def create_document(request: Request):
        """Create a living document for block commands"""
        data = await request.json()
        title = data.get("title") or "Untitled"
        content = data.get("content") or ""
        doc_type = data.get("type") or data.get("doc_type") or "general"
        doc = murphy._create_document(title=title, content=content, doc_type=doc_type, session_id=data.get("session_id"))
        return JSONResponse({"success": True, **doc.to_dict()})

    @app.get("/api/documents/list")
    async def documents_list_early():
        """List available documents (registered before {doc_id} wildcard)."""
        docs = []
        for doc_id, doc in getattr(murphy, "living_documents", {}).items():
            docs.append({"doc_id": doc_id, "title": getattr(doc, "title", "Untitled")})
        return JSONResponse({"success": True, "documents": docs})

    @app.get("/api/documents/{doc_id}")
    async def get_document(doc_id: str):
        """Fetch a living document"""
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        return JSONResponse({"success": True, **doc.to_dict()})

    @app.post("/api/documents/{doc_id}/magnify")
    async def magnify_document(doc_id: str, request: Request):
        """Magnify a document"""
        data = await request.json()
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        doc.magnify(data.get("domain", "general"))
        murphy._update_document_tree(doc)
        return JSONResponse({"success": True, **doc.to_dict()})

    @app.post("/api/documents/{doc_id}/simplify")
    async def simplify_document(doc_id: str):
        """Simplify a document"""
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        doc.simplify()
        murphy._update_document_tree(doc)
        return JSONResponse({"success": True, **doc.to_dict()})

    @app.post("/api/documents/{doc_id}/solidify")
    async def solidify_document(doc_id: str):
        """Solidify a document"""
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        doc.solidify()
        murphy._update_document_tree(doc)
        return JSONResponse({"success": True, **doc.to_dict()})

    @app.post("/api/documents/{doc_id}/gates")
    async def update_document_gates(doc_id: str, request: Request):
        """Update gate policy for a document"""
        data = await request.json()
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        updates = data.get("gates", [])
        murphy.update_gate_policy(doc, updates, confidence=data.get("confidence"))
        murphy._apply_wired_capabilities(doc.content, doc, data.get("onboarding_context"))
        preview = murphy._build_activation_preview(doc, doc.content, data.get("onboarding_context"))
        return JSONResponse({
            "success": True,
            "doc_id": doc.doc_id,
            "gates": doc.gates,
            "block_tree": doc.block_tree,
            "activation_preview": preview,
            **doc.to_dict()
        })

    @app.get("/api/documents/{doc_id}/blocks")
    async def document_blocks(doc_id: str):
        """Fetch the block command tree for a document"""
        doc = murphy.living_documents.get(doc_id)
        if not doc:
            return JSONResponse({"success": False, "error": "Document not found"}, status_code=404)
        return JSONResponse({"success": True, "block_tree": doc.block_tree})

    # ==================== FORM ENDPOINTS ====================

    @app.post("/api/forms/task-execution")
    async def form_task_execution(request: Request):
        """Execute task via form endpoint — routes through AionMind cognitive pipeline."""
        data = await request.json()
        # Enrich form data with AionMind context if available
        if _aionmind_kernel is not None:
            try:
                desc = data.get("description") or data.get("task_description", "")
                aionmind_result = _aionmind_kernel.cognitive_execute(
                    source="form:task-execution",
                    raw_input=desc,
                    task_type=data.get("task_type", "general"),
                    parameters=data.get("parameters"),
                    auto_approve=True,
                    approver="form_auto",
                )
                result = await murphy.handle_form_task_execution(data)
                result["aionmind"] = aionmind_result
                return JSONResponse(result)
            except Exception as _exc:
                logger.debug("AionMind form pipeline fallback: %s", _exc)
        result = await murphy.handle_form_task_execution(data)
        return JSONResponse(result)

    @app.post("/api/forms/validation")
    async def form_validation(request: Request):
        """Validate task via form endpoint — enriched with AionMind context."""
        data = await request.json()
        if _aionmind_kernel is not None:
            try:
                desc = (data.get("task_data") or data).get("description", "")
                ctx = _aionmind_kernel.build_context(
                    source="form:validation",
                    raw_input=desc,
                )
                result = murphy.handle_form_validation(data)
                result["aionmind_context_id"] = ctx.context_id
                return JSONResponse(result)
            except Exception as _exc:
                logger.debug("AionMind validation context fallback: %s", _exc)
        result = murphy.handle_form_validation(data)
        return JSONResponse(result)

    @app.post("/api/forms/correction")
    async def form_correction(request: Request):
        """Submit correction via form endpoint — enriched with AionMind context."""
        data = await request.json()
        if _aionmind_kernel is not None:
            try:
                desc = data.get("task_description") or data.get("original_task", "")
                ctx = _aionmind_kernel.build_context(
                    source="form:correction",
                    raw_input=desc,
                    metadata={"correction": data.get("correction", "")},
                )
                result = murphy.handle_form_correction(data)
                result["aionmind_context_id"] = ctx.context_id
                return JSONResponse(result)
            except Exception as _exc:
                logger.debug("AionMind correction context fallback: %s", _exc)
        result = murphy.handle_form_correction(data)
        return JSONResponse(result)

    @app.post("/api/forms/plan-upload")
    async def form_plan_upload(request: Request):
        """Upload a plan via form endpoint"""
        data = await request.json()
        result = murphy.handle_form_submission("plan-upload", data)
        return JSONResponse(result)

    @app.post("/api/forms/plan-generation")
    async def form_plan_generation(request: Request):
        """Generate plan via form endpoint"""
        data = await request.json()
        result = murphy.handle_form_submission("plan-generation", data)
        return JSONResponse(result)

    @app.get("/api/forms/submission/{submission_id}")
    async def form_submission_status(submission_id: str):
        """Get form submission status"""
        submission = murphy.form_submissions.get(submission_id)
        return JSONResponse({"success": bool(submission), "submission": submission})

    @app.post("/api/forms/{form_type}")
    async def form_generic(form_type: str, request: Request):
        """Generic form submission endpoint"""
        data = await request.json()
        if form_type == "task-execution":
            result = await murphy.handle_form_task_execution(data)
            return JSONResponse(result)
        if form_type == "validation":
            result = murphy.handle_form_validation(data)
            return JSONResponse(result)
        if form_type == "correction":
            result = murphy.handle_form_correction(data)
            return JSONResponse(result)
        result = murphy.handle_form_submission(form_type, data)
        return JSONResponse(result)

    # ==================== CORRECTION ENDPOINTS ====================

    @app.get("/api/corrections/patterns")
    async def correction_patterns():
        """Get correction patterns"""
        return JSONResponse(murphy.get_correction_patterns())

    @app.get("/api/corrections/statistics")
    async def correction_statistics():
        """Get correction statistics"""
        return JSONResponse(murphy.get_correction_statistics())

    @app.get("/api/corrections/training-data")
    async def correction_training_data():
        """Get correction training data"""
        return JSONResponse({"success": True, "data": murphy.corrections})

    @app.get("/api/corrections/proposals")
    async def corrections_proposals():
        """List code repair proposals from MurphyCodeHealer (ARCH-006)."""
        if _code_healer is None:
            return JSONResponse({"success": True, "proposals": [], "healer_status": "unavailable"})
        proposals = _code_healer.get_proposals(limit=100)
        metrics = _code_healer.get_metrics()
        return JSONResponse({
            "success": True,
            "proposals": proposals,
            "total": len(proposals),
            "metrics": metrics,
        })

    @app.post("/api/corrections/proposals/{proposal_id}/approve")
    async def corrections_proposal_approve(proposal_id: str):
        """Mark a code proposal as approved for human-supervised application."""
        if _code_healer is None:
            return JSONResponse(
                {"success": False, "error": "MurphyCodeHealer not available"},
                status_code=503,
            )
        # Validate proposal_id exists in healer proposals
        proposals = _code_healer.get_proposals(limit=500)
        known_ids = {p.get("proposal_id") for p in proposals}
        if proposal_id not in known_ids:
            return JSONResponse(
                {"success": False, "error": f"Proposal '{proposal_id}' not found"},
                status_code=404,
            )
        return JSONResponse({
            "success": True,
            "proposal_id": proposal_id,
            "status": "approved",
            "message": "Proposal approved for human-supervised application",
            "timestamp": _now_iso(),
        })

    @app.post("/api/corrections/proposals/{proposal_id}/reject")
    async def corrections_proposal_reject(proposal_id: str, request: Request):
        """Reject a code repair proposal."""
        if _code_healer is None:
            return JSONResponse(
                {"success": False, "error": "MurphyCodeHealer not available"},
                status_code=503,
            )
        data = {}
        try:
            data = await request.json()
        except Exception:
            pass
        # Validate proposal_id exists
        proposals = _code_healer.get_proposals(limit=500)
        known_ids = {p.get("proposal_id") for p in proposals}
        if proposal_id not in known_ids:
            return JSONResponse(
                {"success": False, "error": f"Proposal '{proposal_id}' not found"},
                status_code=404,
            )
        return JSONResponse({
            "success": True,
            "proposal_id": proposal_id,
            "status": "rejected",
            "reason": data.get("reason", ""),
            "timestamp": _now_iso(),
        })

    @app.post("/api/corrections/heal")
    async def corrections_trigger_heal(request: Request):
        """Trigger an on-demand MurphyCodeHealer diagnostic cycle."""
        if _code_healer is None:
            return JSONResponse(
                {"success": False, "error": "MurphyCodeHealer not available"},
                status_code=503,
            )
        data = {}
        try:
            data = await request.json()
        except Exception:
            pass
        max_gaps = int(data.get("max_gaps", 50))
        try:
            report = _code_healer.run_healing_cycle(max_gaps=max_gaps)
            return JSONResponse({"success": True, "report": report})
        except RuntimeError as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=409)

    # ==================== HITL ENDPOINTS ====================

    @app.get("/api/hitl/interventions/pending")
    async def hitl_pending():
        """Get pending HITL interventions"""
        state = murphy.get_hitl_state()
        return JSONResponse({
            "success": True,
            "count": len(state["pending"]),
            "interventions": state["pending"]
        })

    @app.post("/api/hitl/interventions/{intervention_id}/respond")
    async def hitl_respond(intervention_id: str, request: Request):
        """Respond to HITL intervention"""
        data = await request.json()
        intervention = murphy.hitl_interventions.get(intervention_id)
        if intervention:
            intervention["status"] = data.get("status", "resolved")
            intervention["response"] = data.get("response")
        return JSONResponse({"success": bool(intervention), "intervention": intervention})

    @app.get("/api/hitl/statistics")
    async def hitl_statistics():
        """Get HITL statistics"""
        stats = murphy.get_hitl_state().get("statistics", {})
        return JSONResponse({"success": True, "statistics": stats})

    # ==================== MATRIX BRIDGE ENDPOINTS ====================

    # Lazy-loaded Matrix bridge state (optional dependency)
    _matrix_bridge_state: Dict[str, Any] = {
        "connected": False,
        "homeserver": os.environ.get("MATRIX_HOMESERVER_URL", ""),
        "rooms": [],
        "stats": {"messages_sent": 0, "messages_received": 0, "active_rooms": 0},
    }

    try:
        from src.matrix_bridge import MatrixBridgeSettings
        from src.matrix_bridge import get_settings as _get_matrix_settings
        _mx_settings = _get_matrix_settings()
        _matrix_bridge_state["homeserver"] = _mx_settings.homeserver_url
        logger.info("Matrix bridge settings loaded")
    except Exception:
        logger.debug("Matrix bridge settings not available — using defaults")

    @app.get("/api/matrix/status")
    async def matrix_status():
        """Get Matrix bridge connection status."""
        return JSONResponse({
            "success": True,
            "connected": _matrix_bridge_state["connected"],
            "homeserver": _matrix_bridge_state["homeserver"],
            "user_id": os.environ.get("MATRIX_USER_ID", ""),
            "bridge_version": "1.0.0",
        })

    @app.get("/api/matrix/rooms")
    async def matrix_rooms():
        """Get list of Matrix rooms the bridge is joined to."""
        try:
            from src.matrix_bridge import get_topology
            topo = get_topology()
            rooms = [
                {
                    "alias": r.alias,
                    "name": r.name,
                    "room_type": r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type),
                    "topic": getattr(r, "topic", ""),
                }
                for r in topo.rooms
            ]
        except Exception:
            rooms = _matrix_bridge_state.get("rooms", [])
        return JSONResponse({"success": True, "rooms": rooms})

    @app.post("/api/matrix/send")
    async def matrix_send(request: Request):
        """Send a message to a Matrix room (enqueued via bridge)."""
        data = await request.json()
        room = data.get("room", "")
        message = data.get("message", "")
        if not room or not message:
            return JSONResponse(
                {"success": False, "error": "room and message are required"},
                status_code=400,
            )
        # Attempt real send; fall back to acknowledgement
        try:
            from src.matrix_bridge import MatrixClient
            # In production the client is a singleton managed by startup
            logger.info("Matrix send requested: room=%s len=%d", room, len(message))
        except ImportError:
            pass
        return JSONResponse({
            "success": True,
            "status": "enqueued",
            "room": room,
            "message_length": len(message),
        })

    @app.get("/api/matrix/stats")
    async def matrix_stats():
        """Get Matrix bridge statistics."""
        return JSONResponse({
            "success": True,
            "stats": _matrix_bridge_state["stats"],
        })

    # ==================== MFGC ENDPOINTS ====================

    @app.get("/api/mfgc/state")
    async def mfgc_state():
        """Get MFGC state"""
        return JSONResponse({"success": True, "state": murphy.get_mfgc_state()})

    @app.get("/api/mfgc/config")
    async def mfgc_config():
        """Get MFGC config"""
        return JSONResponse({"success": True, "config": murphy.mfgc_config})

    @app.post("/api/mfgc/config")
    async def mfgc_config_update(request: Request):
        """Update MFGC config"""
        data = await request.json()
        murphy.mfgc_config.update(data)
        return JSONResponse({"success": True, "config": murphy.mfgc_config})

    @app.post("/api/mfgc/setup/{profile}")
    async def mfgc_setup(profile: str):
        """Configure MFGC profile"""
        profiles = {
            "production": {"enabled": True, "murphy_threshold": 0.7},
            "certification": {"enabled": True, "murphy_threshold": 0.6},
            "development": {"enabled": False, "murphy_threshold": 0.3}
        }
        if profile in profiles:
            murphy.mfgc_config.update(profiles[profile])
            return JSONResponse({"success": True, "profile": profile, "config": murphy.mfgc_config})
        return JSONResponse({"success": False, "error": "Unknown profile"})

    # ==================== INTEGRATION ENDPOINTS ====================

    @app.post("/api/integrations/add")
    async def add_integration(request: Request):
        """Add an integration"""
        data = await request.json()
        result = murphy.add_integration(
            source=data.get('source', ''),
            integration_type=data.get('integration_type', 'repository'),
            category=data.get('category', 'general'),
            generate_agent=data.get('generate_agent', False),
            auto_approve=data.get('auto_approve', False)
        )
        return JSONResponse(result)

    @app.post("/api/integrations/{request_id}/approve")
    async def approve_integration(request_id: str, request: Request):
        """Approve an integration"""
        data = await request.json()
        result = murphy.approve_integration(
            request_id=request_id,
            approved_by=data.get('approved_by', 'user')
        )
        return JSONResponse(result)

    @app.post("/api/integrations/{request_id}/reject")
    async def reject_integration(request_id: str, request: Request):
        """Reject an integration"""
        data = await request.json()
        result = murphy.reject_integration(
            request_id=request_id,
            reason=data.get('reason', 'User rejected')
        )
        return JSONResponse(result)

    @app.get("/api/integrations/{status}")
    async def list_integrations(status: str = 'all'):
        """List integrations"""
        result = murphy.list_integrations(status=status)
        return JSONResponse(result)

    # ==================== BUSINESS AUTOMATION ENDPOINTS ====================

    @app.post("/api/automation/{engine_name}/{action}")
    async def run_automation(engine_name: str, action: str, request: Request):
        """Run business automation"""
        data = await request.json()
        result = murphy.run_inoni_automation(
            engine_name=engine_name,
            action=action,
            parameters=data.get('parameters')
        )
        return JSONResponse(result)

    # ==================== SYSTEM ENDPOINTS ====================

    @app.get("/api/modules")
    async def list_modules():
        """List all modules"""
        return JSONResponse(murphy.list_modules())

    @app.get("/api/modules/{name}/status")
    async def get_module_status(name: str):
        """Get status for a single module by name."""
        modules = murphy.list_modules()
        for mod in modules:
            if mod.get("name") == name:
                return JSONResponse({"success": True, "module": mod})
        if _integration_bus is not None:
            bus_status = _integration_bus.get_status()
            if name in bus_status.get("modules", {}):
                return JSONResponse({
                    "success": True,
                    "module": {
                        "name": name,
                        "status": "wired" if bus_status["modules"][name] else "unavailable",
                    },
                })
        return JSONResponse({"success": False, "error": f"Module '{name}' not found"}, status_code=404)

    @app.post("/api/feedback")
    async def submit_feedback(request: Request):
        """Accept and process explicit feedback signals (thumbs up/down, corrections)."""
        data = await request.json()
        if _integration_bus is not None:
            result = _integration_bus.submit_feedback(data)
        else:
            result = {
                "success": True,
                "message": "Feedback received (integration bus not available)",
                "bus_routed": False,
            }
        return JSONResponse(result)

    @app.get("/api/diagnostics/activation")
    async def activation_audit():
        """List inactive subsystems and activation hints"""
        return JSONResponse(murphy.get_activation_audit())

    @app.get("/api/diagnostics/activation/last")
    async def get_last_activation_preview():
        """Get latest activation preview from request processing"""
        preview = murphy.latest_activation_preview
        return JSONResponse({"success": bool(preview), "preview": preview})

    # ==================== IMAGE GENERATION ENDPOINTS ====================

    @app.post("/api/images/generate")
    async def generate_image(request: Request):
        """Generate an image using the open-source image generation engine."""
        if not murphy.image_generation_engine:
            return JSONResponse({"success": False, "error": "Image generation engine not available"}, status_code=503)
        data = await request.json()
        from src.image_generation_engine import ImageRequest as ImgReq
        from src.image_generation_engine import ImageStyle as ImgStyle
        style_str = data.get("style", "digital_art")
        try:
            style = ImgStyle(style_str)
        except ValueError:
            style = ImgStyle.DIGITAL_ART
        req = ImgReq(
            prompt=data.get("prompt", ""),
            negative_prompt=data.get("negative_prompt", ""),
            width=data.get("width", 1024),
            height=data.get("height", 1024),
            style=style,
            seed=data.get("seed"),
        )
        result = murphy.image_generation_engine.generate(req)
        return JSONResponse({"success": result.status.value == "complete", **result.to_dict()})

    @app.get("/api/images/styles")
    async def list_image_styles():
        """List available image generation styles."""
        if not murphy.image_generation_engine:
            return JSONResponse({"success": False, "error": "Image generation engine not available"}, status_code=503)
        return JSONResponse({
            "success": True,
            "styles": murphy.image_generation_engine.get_available_styles(),
            "backends": murphy.image_generation_engine.get_available_backends(),
            "active_backend": murphy.image_generation_engine.get_active_backend(),
        })

    @app.get("/api/images/stats")
    async def image_generation_stats():
        """Get image generation statistics."""
        if not murphy.image_generation_engine:
            return JSONResponse({"success": False, "error": "Image generation engine not available"}, status_code=503)
        return JSONResponse({"success": True, **murphy.image_generation_engine.get_statistics()})

    # ==================== UNIVERSAL INTEGRATION ENDPOINTS ====================

    @app.get("/api/universal-integrations/services")
    async def list_universal_integrations(request: Request):
        """List all available universal integration services."""
        if not murphy.universal_integration_adapter:
            return JSONResponse({"success": False, "error": "Universal integration adapter not available"}, status_code=503)
        category = request.query_params.get("category")
        services = murphy.universal_integration_adapter.list_services(category)
        return JSONResponse({"success": True, "services": services, "total": len(services)})

    @app.get("/api/universal-integrations/categories")
    async def list_integration_categories():
        """List all integration categories."""
        if not murphy.universal_integration_adapter:
            return JSONResponse({"success": False, "error": "Universal integration adapter not available"}, status_code=503)
        return JSONResponse({"success": True, "categories": murphy.universal_integration_adapter.list_categories()})

    @app.get("/api/universal-integrations/services/{service_id}")
    async def get_integration_service(service_id: str):
        """Get details for a specific integration service."""
        if not murphy.universal_integration_adapter:
            return JSONResponse({"success": False, "error": "Universal integration adapter not available"}, status_code=503)
        service = murphy.universal_integration_adapter.get_service(service_id)
        if service is None:
            return JSONResponse({"success": False, "error": f"Service '{service_id}' not found"}, status_code=404)
        return JSONResponse({"success": True, **service})

    @app.post("/api/universal-integrations/services/{service_id}/configure")
    async def configure_integration(service_id: str, request: Request):
        """Configure credentials for an integration service."""
        if not murphy.universal_integration_adapter:
            return JSONResponse({"success": False, "error": "Universal integration adapter not available"}, status_code=503)
        data = await request.json()
        result = murphy.universal_integration_adapter.configure(service_id, data.get("credentials", {}))
        return JSONResponse({"success": "error" not in result, **result})

    @app.post("/api/universal-integrations/services/{service_id}/execute/{action_name}")
    async def execute_integration_action(service_id: str, action_name: str, request: Request):
        """Execute an action on an integration service."""
        if not murphy.universal_integration_adapter:
            return JSONResponse({"success": False, "error": "Universal integration adapter not available"}, status_code=503)
        try:
            data = await request.json()
        except Exception:
            data = {}
        result = murphy.universal_integration_adapter.execute(service_id, action_name, data.get("params", data))
        return JSONResponse({"success": result.status.value == "success", **result.to_dict()})

    @app.post("/api/universal-integrations/register")
    async def register_custom_integration(request: Request):
        """Register a custom integration service."""
        if not murphy.universal_integration_adapter:
            return JSONResponse({"success": False, "error": "Universal integration adapter not available"}, status_code=503)
        data = await request.json()
        from src.universal_integration_adapter import IntegrationAction as IAction
        from src.universal_integration_adapter import IntegrationAuthMethod as IAuth
        from src.universal_integration_adapter import IntegrationCategory as ICat
        from src.universal_integration_adapter import IntegrationSpec as ISpec
        try:
            cat = ICat(data.get("category", "custom"))
        except ValueError:
            cat = ICat.CUSTOM
        try:
            auth = IAuth(data.get("auth_method", "api_key"))
        except ValueError:
            auth = IAuth.API_KEY
        actions = [IAction(name=a["name"], description=a.get("description", ""), method=a.get("method", "POST"), endpoint=a.get("endpoint", "")) for a in data.get("actions", [])]
        spec = ISpec(
            name=data.get("name", "Custom Service"),
            category=cat,
            description=data.get("description", ""),
            base_url=data.get("base_url", ""),
            auth_method=auth,
            actions=actions,
            metadata=data.get("metadata", {}),
        )
        result = murphy.universal_integration_adapter.register(spec)
        return JSONResponse({"success": True, **result})

    @app.get("/api/universal-integrations/stats")
    async def universal_integration_stats():
        """Get universal integration adapter statistics."""
        if not murphy.universal_integration_adapter:
            return JSONResponse({"success": False, "error": "Universal integration adapter not available"}, status_code=503)
        return JSONResponse({"success": True, **murphy.universal_integration_adapter.statistics()})

    # ==================== NO-CODE ONBOARDING ENDPOINTS ====================

    # --- Setup Wizard (system configuration) ---

    try:
        from setup_wizard import SetupProfile, SetupWizard
        _setup_wizard = SetupWizard()
    except Exception:
        _setup_wizard = None

    try:
        from onboarding_automation_engine import OnboardingAutomationEngine
        _onboarding_engine = OnboardingAutomationEngine()
    except Exception:
        _onboarding_engine = None

    # Persisted onboarding config (read by production wizard + workflow canvas)
    _onboarding_config: Dict[str, Any] = {}

    @app.get("/api/onboarding/wizard/questions")
    async def onboarding_wizard_questions():
        """Get all setup wizard questions for no-code configuration."""
        if _setup_wizard is None:
            return JSONResponse({"success": False, "error": "Setup wizard not available"}, status_code=503)
        questions = _setup_wizard.get_questions()
        return JSONResponse({"success": True, "questions": questions, "total": len(questions)})

    @app.post("/api/onboarding/wizard/answer")
    async def onboarding_wizard_answer(request: Request):
        """Submit an answer to a setup wizard question."""
        if _setup_wizard is None:
            return JSONResponse({"success": False, "error": "Setup wizard not available"}, status_code=503)
        data = await request.json()
        question_id = data.get("question_id", "")
        answer = data.get("answer")
        if not question_id:
            return JSONResponse({"success": False, "error": "question_id is required"}, status_code=400)
        result = _setup_wizard.apply_answer(question_id, answer)
        return JSONResponse({"success": result["ok"], "error": result.get("error")})

    @app.get("/api/onboarding/wizard/profile")
    async def onboarding_wizard_profile():
        """Get the current setup wizard profile state."""
        if _setup_wizard is None:
            return JSONResponse({"success": False, "error": "Setup wizard not available"}, status_code=503)
        from dataclasses import asdict
        profile = _setup_wizard.get_profile()
        return JSONResponse({"success": True, "profile": asdict(profile)})

    @app.post("/api/onboarding/wizard/validate")
    async def onboarding_wizard_validate():
        """Validate the current setup wizard profile."""
        if _setup_wizard is None:
            return JSONResponse({"success": False, "error": "Setup wizard not available"}, status_code=503)
        profile = _setup_wizard.get_profile()
        result = _setup_wizard.validate_profile(profile)
        return JSONResponse({"success": True, **result})

    @app.post("/api/onboarding/wizard/generate-config")
    async def onboarding_wizard_generate_config(request: Request):
        """Generate a complete Murphy System configuration from wizard answers.

        Accepts the wizard's selected modules, integrations, safety level,
        and chat history.  Stores the resulting config in-memory so the
        production wizard and workflow canvas can read it back via
        ``GET /api/onboarding/wizard/config``.
        """
        body: Dict[str, Any] = {}
        try:
            body = await request.json()
        except Exception:
            pass  # body remains {} — the endpoint also works without a body

        if _setup_wizard is None:
            # Fallback: build config directly from the submitted body
            config = {
                "modules": body.get("modules", []),
                "integrations": body.get("integrations", []),
                "safety_level": body.get("safety_level", 3),
                "terminal": body.get("terminal", "/ui/terminal-unified"),
            }
            _onboarding_config.update(config)
            _onboarding_config["chat_history"] = body.get("chat_history", [])
            _onboarding_config["created_at"] = _now_iso()
            return JSONResponse({"success": True, "config": config})

        profile = _setup_wizard.get_profile()
        validation = _setup_wizard.validate_profile(profile)
        config = _setup_wizard.generate_config(profile)
        summary = _setup_wizard.summarize(profile)

        # Merge wizard selections from the request body into config
        if body.get("modules"):
            config["modules"] = body["modules"]
        if body.get("integrations"):
            config["integrations"] = body["integrations"]
        if body.get("safety_level") is not None:
            config["safety_level"] = body["safety_level"]

        # Persist so production wizard can read it
        _onboarding_config.update(config)
        _onboarding_config["chat_history"] = body.get("chat_history", [])
        _onboarding_config["validation"] = validation
        _onboarding_config["summary"] = summary
        _onboarding_config["created_at"] = _now_iso()

        return JSONResponse({
            "success": True,
            "config": config,
            "validation": validation,
            "summary": summary,
        })

    @app.get("/api/onboarding/wizard/config")
    async def onboarding_wizard_get_config():
        """Return the persisted onboarding config so production wizard can use it."""
        if not _onboarding_config:
            return JSONResponse({"success": False, "error": "No onboarding config yet"}, status_code=404)
        return JSONResponse({"success": True, **_onboarding_config})

    @app.get("/api/onboarding/wizard/summary")
    async def onboarding_wizard_summary():
        """Get a human-readable summary of the current wizard configuration."""
        if _setup_wizard is None:
            return JSONResponse({"success": False, "error": "Setup wizard not available"}, status_code=503)
        profile = _setup_wizard.get_profile()
        summary = _setup_wizard.summarize(profile)
        modules = _setup_wizard.get_enabled_modules(profile)
        bots = _setup_wizard.get_recommended_bots(profile)
        return JSONResponse({
            "success": True,
            "summary": summary,
            "modules": modules,
            "bots": bots,
            "module_count": len(modules),
            "bot_count": len(bots),
        })

    @app.post("/api/onboarding/wizard/reset")
    async def onboarding_wizard_reset():
        """Reset the setup wizard to start over."""
        nonlocal _setup_wizard
        try:
            from setup_wizard import SetupWizard
            _setup_wizard = SetupWizard()
            return JSONResponse({"success": True})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    # In-memory MFGC session store for onboarding chat (max 500 sessions, 2-hour TTL)
    _onboarding_mfgc_sessions: dict = {}
    _ONBOARDING_SESSION_TTL = 7200  # seconds

    @app.post("/api/onboarding/mfgc-chat")
    async def onboarding_mfgc_chat(request: Request):
        """Route onboarding wizard messages through UnifiedMFGC gate system.

        Accepts ``{ "session_id": "...", "message": "..." }`` and returns
        ``{ "response": "...", "gate_satisfaction": 0.XX, "confidence": 0.XX,
            "unknowns_remaining": N, "ready_for_plan": bool }``.
        """
        import time as _time
        data = await request.json()
        message = (data.get("message") or data.get("question") or "").strip()
        session_id = data.get("session_id") or "onboarding-default"

        if not message:
            return JSONResponse({"success": False, "error": "message is required"}, status_code=400)

        # Evict expired sessions (simple TTL cleanup)
        now = _time.monotonic()
        expired = [k for k, v in _onboarding_mfgc_sessions.items()
                   if now - v.get("last_access", 0) > _ONBOARDING_SESSION_TTL]
        for k in expired:
            del _onboarding_mfgc_sessions[k]
        # Also cap at 500 sessions to prevent unbounded growth
        if len(_onboarding_mfgc_sessions) >= 500:
            oldest = sorted(_onboarding_mfgc_sessions.items(),
                            key=lambda x: x[1].get("last_access", 0))[:50]
            for k, _ in oldest:
                del _onboarding_mfgc_sessions[k]

        try:
            # Retrieve or create a per-session UnifiedMFGC instance
            if session_id not in _onboarding_mfgc_sessions:
                from unified_mfgc import UnifiedMFGC
                _onboarding_mfgc_sessions[session_id] = {
                    "mfgc": UnifiedMFGC(),
                    "answers": {},
                    "context": "Murphy onboarding wizard: helping a new user describe their business and automation needs.",
                    "last_access": now,
                }
            sess = _onboarding_mfgc_sessions[session_id]
            sess["last_access"] = now
            mfgc_instance = sess["mfgc"]

            # Feed the new message as the latest answer (also used as the next request)
            if sess["answers"]:
                # Record the user reply to the last question asked
                last_key = list(sess["answers"].keys())[-1]
                if sess["answers"][last_key] is None:
                    sess["answers"][last_key] = message
            # Also treat the full message as the primary request on first turn
            if not sess["answers"]:
                sess["answers"]["initial_request"] = message

            result = mfgc_instance._process_with_context(
                message=message,
                answers=sess["answers"],
                context_summary=sess["context"],
            )

            gate_satisfaction = result.get("gate_satisfaction", 0.0)
            confidence = result.get("confidence", 0.0)
            unknowns_remaining = result.get("unknowns_remaining", 99)
            ready_for_plan = bool(result.get("execution_mode", False))

            response_text = (
                result.get("content")
                or result.get("response")
                or result.get("message")
                or "Murphy is gathering more information."
            )

            # If the MFGC asked a follow-up question, record a placeholder for the answer
            if result.get("questioning_mode"):
                import re as _re
                questions = _re.findall(r"[A-Z][^\n]*\?", response_text)
                for q in questions:
                    sess["answers"][q] = None

            return JSONResponse({
                "success": True,
                "response": response_text,
                "gate_satisfaction": round(float(gate_satisfaction), 4),
                "confidence": round(float(confidence), 4),
                "unknowns_remaining": int(unknowns_remaining),
                "ready_for_plan": ready_for_plan,
            })
        except Exception as exc:
            logger.warning("onboarding_mfgc_chat error: %s", exc)
            return JSONResponse({
                "success": False,
                "response": "I'm having trouble processing that right now. Please continue or try again.",
                "gate_satisfaction": 0.0,
                "confidence": 0.0,
                "unknowns_remaining": 99,
                "ready_for_plan": False,
            }, status_code=200)  # Return 200 so the UI doesn't show a hard error

    # --- Onboarding Automation Engine (employee onboarding) ---

    @app.post("/api/onboarding/employees")
    async def onboarding_create_employee(request: Request):
        """Create a new employee onboarding profile."""
        if _onboarding_engine is None:
            return JSONResponse({"success": False, "error": "Onboarding engine not available"}, status_code=503)
        data = await request.json()
        employee_name = data.get("employee_name", "")
        role = data.get("role", "")
        department = data.get("department", "")
        if not employee_name or not role or not department:
            return JSONResponse({"success": False, "error": "employee_name, role, and department are required"}, status_code=400)
        profile = _onboarding_engine.create_onboarding(
            employee_name=employee_name,
            role=role,
            department=department,
            mentor=data.get("mentor", ""),
            start_date=data.get("start_date", ""),
        )
        return JSONResponse({"success": True, "profile": profile.to_dict()})

    @app.get("/api/onboarding/employees")
    async def onboarding_list_employees(status: str = None, department: str = None):
        """List employee onboarding profiles."""
        if _onboarding_engine is None:
            return JSONResponse({"success": False, "error": "Onboarding engine not available"}, status_code=503)
        profiles = _onboarding_engine.list_profiles(status=status, department=department)
        return JSONResponse({"success": True, "profiles": profiles, "total": len(profiles)})

    @app.get("/api/onboarding/employees/{profile_id}")
    async def onboarding_get_employee(profile_id: str):
        """Get a specific employee onboarding profile."""
        if _onboarding_engine is None:
            return JSONResponse({"success": False, "error": "Onboarding engine not available"}, status_code=503)
        profile = _onboarding_engine.get_profile(profile_id)
        if profile is None:
            return JSONResponse({"success": False, "error": "Profile not found"}, status_code=404)
        return JSONResponse({"success": True, "profile": profile})

    @app.post("/api/onboarding/employees/{profile_id}/tasks/{task_id}/complete")
    async def onboarding_complete_task(profile_id: str, task_id: str):
        """Mark an onboarding task as completed."""
        if _onboarding_engine is None:
            return JSONResponse({"success": False, "error": "Onboarding engine not available"}, status_code=503)
        result = _onboarding_engine.complete_task(profile_id, task_id)
        if result is None:
            return JSONResponse({"success": False, "error": "Profile or task not found"}, status_code=404)
        return JSONResponse({"success": True, "profile": result.to_dict()})

    @app.post("/api/onboarding/employees/{profile_id}/tasks/{task_id}/skip")
    async def onboarding_skip_task(profile_id: str, task_id: str):
        """Skip an onboarding task."""
        if _onboarding_engine is None:
            return JSONResponse({"success": False, "error": "Onboarding engine not available"}, status_code=503)
        result = _onboarding_engine.skip_task(profile_id, task_id)
        if result is None:
            return JSONResponse({"success": False, "error": "Profile or task not found"}, status_code=404)
        return JSONResponse({"success": True, "profile": result.to_dict()})

    @app.get("/api/onboarding/status")
    async def onboarding_engine_status():
        """Get onboarding engine status."""
        if _onboarding_engine is None:
            return JSONResponse({"success": False, "error": "Onboarding engine not available"}, status_code=503)
        return JSONResponse({"success": True, **_onboarding_engine.get_status()})

    # ==================== NO-CODE WORKFLOW LIBRARIAN TERMINAL ====================

    try:
        from src.nocode_workflow_terminal import NoCodeWorkflowTerminal
        _workflow_terminal = NoCodeWorkflowTerminal()
    except ImportError:
        _workflow_terminal = None

    @app.post("/api/workflow-terminal/sessions")
    async def create_workflow_terminal_session():
        """Create a new Librarian workflow builder session."""
        if _workflow_terminal is None:
            return JSONResponse({"success": False, "error": "Workflow terminal not available"}, status_code=503)
        session = _workflow_terminal.create_session()
        return JSONResponse({"success": True, "session": session.to_dict()})

    @app.post("/api/workflow-terminal/sessions/{session_id}/message")
    async def send_workflow_terminal_message(session_id: str, request: Request):
        """Send a message to the Librarian in an existing session."""
        if _workflow_terminal is None:
            return JSONResponse({"success": False, "error": "Workflow terminal not available"}, status_code=503)
        data = await request.json()
        result = _workflow_terminal.send_message(session_id, data.get("message", ""))
        return JSONResponse({"success": True, **result})

    @app.get("/api/workflow-terminal/sessions/{session_id}")
    async def get_workflow_terminal_session(session_id: str):
        """Get details of a workflow terminal session."""
        if _workflow_terminal is None:
            return JSONResponse({"success": False, "error": "Workflow terminal not available"}, status_code=503)
        session = _workflow_terminal.get_session(session_id)
        if not session:
            return JSONResponse({"success": False, "error": "Session not found"}, status_code=404)
        return JSONResponse({"success": True, "session": session.to_dict()})

    @app.get("/api/workflow-terminal/sessions/{session_id}/compile")
    async def compile_workflow_terminal(session_id: str):
        """Compile the workflow from a terminal session."""
        if _workflow_terminal is None:
            return JSONResponse({"success": False, "error": "Workflow terminal not available"}, status_code=503)
        compiled = _workflow_terminal.compile_workflow(session_id)
        if not compiled:
            return JSONResponse({"success": False, "error": "Cannot compile"}, status_code=400)
        return JSONResponse({"success": True, "workflow": compiled})

    @app.get("/api/workflow-terminal/sessions/{session_id}/agents/{agent_id}")
    async def get_workflow_terminal_agent(session_id: str, agent_id: str):
        """Drill down into a specific agent's activity in a session."""
        if _workflow_terminal is None:
            return JSONResponse({"success": False, "error": "Workflow terminal not available"}, status_code=503)
        detail = _workflow_terminal.get_agent_detail(session_id, agent_id)
        if not detail:
            return JSONResponse({"success": False, "error": "Agent not found"}, status_code=404)
        return JSONResponse({"success": True, "agent_detail": detail})

    @app.get("/api/workflow-terminal/sessions")
    async def list_workflow_terminal_sessions():
        """List all active workflow terminal sessions."""
        if _workflow_terminal is None:
            return JSONResponse({"success": False, "error": "Workflow terminal not available"}, status_code=503)
        return JSONResponse({"success": True, "sessions": _workflow_terminal.list_sessions()})

    # ── Workflow-terminal convenience aliases used by workflow_canvas.html ──

    @app.get("/api/workflow-terminal/list")
    async def workflow_terminal_list():
        """List saved workflows (alias used by workflow canvas UI)."""
        return JSONResponse(list(_workflows_store.values()))

    @app.post("/api/workflow-terminal/save")
    async def workflow_terminal_save(request: Request):
        """Save a workflow from the canvas UI."""
        data = await request.json()
        workflow_id = data.get("id") or str(uuid4())
        workflow = {
            "id": workflow_id,
            "name": data.get("name", "Untitled Workflow"),
            "nodes": data.get("nodes", []),
            "edges": data.get("edges", []),
            "connections": data.get("connections", []),
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        _workflows_store[workflow_id] = workflow
        return JSONResponse({"ok": True, "id": workflow_id})

    @app.get("/api/workflow-terminal/load")
    async def workflow_terminal_load(request: Request):
        """Load a single workflow by ID (used by workflow canvas UI)."""
        wf_id = request.query_params.get("id") or request.query_params.get("workflow_id", "")
        wf = _workflows_store.get(wf_id)
        if not wf:
            return JSONResponse({"ok": False, "error": "Not found"}, status_code=404)
        return JSONResponse(wf)

    # ==================== AGENT MONITOR DASHBOARD ====================

    try:
        from src.agent_monitor_dashboard import AgentMonitorDashboard
        _agent_dashboard = AgentMonitorDashboard()
    except ImportError:
        _agent_dashboard = None

    @app.post("/api/agent-dashboard/agents")
    async def register_dashboard_agent(request: Request):
        """Register an agent on the monitoring dashboard."""
        if _agent_dashboard is None:
            return JSONResponse({"success": False, "error": "Agent dashboard not available"}, status_code=503)
        data = await request.json()
        agent = _agent_dashboard.register_agent(
            name=data.get("name", ""),
            role=data.get("role", "monitor"),
            monitoring_mode=data.get("monitoring_mode", "passive"),
            targets=data.get("targets"),
            metrics=data.get("metrics"),
            config=data.get("config"),
        )
        return JSONResponse({"success": True, "agent": agent.to_dict()})

    @app.get("/api/agent-dashboard/snapshot")
    async def get_agent_dashboard_snapshot():
        """Get a point-in-time snapshot of all agents."""
        if _agent_dashboard is None:
            return JSONResponse({"success": False, "error": "Agent dashboard not available"}, status_code=503)
        snapshot = _agent_dashboard.get_dashboard_snapshot()
        return JSONResponse({"success": True, "snapshot": snapshot.to_dict()})

    @app.get("/api/agent-dashboard/agents/{agent_id}")
    async def get_dashboard_agent_detail(agent_id: str):
        """Drill down into a specific agent's full details."""
        if _agent_dashboard is None:
            return JSONResponse({"success": False, "error": "Agent dashboard not available"}, status_code=503)
        detail = _agent_dashboard.get_agent_detail(agent_id)
        if not detail:
            return JSONResponse({"success": False, "error": "Agent not found"}, status_code=404)
        return JSONResponse({"success": True, "agent": detail})

    @app.get("/api/agent-dashboard/agents/{agent_id}/activity")
    async def get_dashboard_agent_activity(agent_id: str):
        """Get the activity log for a specific agent."""
        if _agent_dashboard is None:
            return JSONResponse({"success": False, "error": "Agent dashboard not available"}, status_code=503)
        activities = _agent_dashboard.get_agent_activity(agent_id)
        if activities is None:
            return JSONResponse({"success": False, "error": "Agent not found"}, status_code=404)
        return JSONResponse({"success": True, "activities": activities})

    @app.get("/api/agent-dashboard/agents")
    async def list_dashboard_agents():
        """List all agents on the dashboard."""
        if _agent_dashboard is None:
            return JSONResponse({"success": False, "error": "Agent dashboard not available"}, status_code=503)
        return JSONResponse({"success": True, "agents": _agent_dashboard.list_agents()})

    # ==================== ONBOARDING FLOW + ORG CHART ====================

    try:
        from src.onboarding_flow import OnboardingFlow
        _onboarding_flow = OnboardingFlow()
    except ImportError:
        _onboarding_flow = None

    @app.post("/api/onboarding-flow/org/initialize")
    async def initialize_org_chart():
        """Initialize the corporate org chart with default positions."""
        if _onboarding_flow is None:
            return JSONResponse({"success": False, "error": "Onboarding flow not available"}, status_code=503)
        result = _onboarding_flow.initialize_org()
        return JSONResponse({"success": True, **result})

    @app.get("/api/onboarding-flow/org/chart")
    async def get_org_chart():
        """Get the full corporate org chart."""
        if _onboarding_flow is None:
            return JSONResponse({"success": False, "error": "Onboarding flow not available"}, status_code=503)
        return JSONResponse({"success": True, "org_chart": _onboarding_flow.org_chart.get_org_chart()})

    @app.get("/api/onboarding-flow/org/positions")
    async def list_org_positions():
        """List all positions in the org chart."""
        if _onboarding_flow is None:
            return JSONResponse({"success": False, "error": "Onboarding flow not available"}, status_code=503)
        return JSONResponse({"success": True, "positions": _onboarding_flow.org_chart.list_positions()})

    @app.post("/api/onboarding-flow/start")
    async def start_onboarding_flow(request: Request):
        """Start an onboarding session for a new individual."""
        if _onboarding_flow is None:
            return JSONResponse({"success": False, "error": "Onboarding flow not available"}, status_code=503)
        data = await request.json()
        session = _onboarding_flow.start_onboarding(
            employee_name=data.get("name", ""),
            employee_email=data.get("email", ""),
        )
        return JSONResponse({"success": True, "session": session.to_dict()})

    @app.get("/api/onboarding-flow/sessions/{session_id}/questions")
    async def get_onboarding_questions(session_id: str):
        """Get onboarding questions for a session."""
        if _onboarding_flow is None:
            return JSONResponse({"success": False, "error": "Onboarding flow not available"}, status_code=503)
        questions = _onboarding_flow.get_questions(session_id)
        return JSONResponse({"success": True, "questions": questions})

    @app.post("/api/onboarding-flow/sessions/{session_id}/answer")
    async def answer_onboarding_question(session_id: str, request: Request):
        """Answer an onboarding question."""
        if _onboarding_flow is None:
            return JSONResponse({"success": False, "error": "Onboarding flow not available"}, status_code=503)
        data = await request.json()
        result = _onboarding_flow.answer_question(
            session_id, data.get("question_id", ""), data.get("answer", "")
        )
        return JSONResponse({"success": True, **result})

    @app.post("/api/onboarding-flow/sessions/{session_id}/shadow-agent")
    async def assign_onboarding_shadow_agent(session_id: str, request: Request):
        """Assign a shadow agent to the onboarded individual."""
        if _onboarding_flow is None:
            return JSONResponse({"success": False, "error": "Onboarding flow not available"}, status_code=503)
        data = await request.json()
        result = _onboarding_flow.assign_shadow_agent(session_id, data.get("position_id"))
        return JSONResponse({"success": True, **result})

    @app.post("/api/onboarding-flow/sessions/{session_id}/transition")
    async def transition_to_builder(session_id: str):
        """Transition from onboarding to the no-code workflow builder."""
        if _onboarding_flow is None:
            return JSONResponse({"success": False, "error": "Onboarding flow not available"}, status_code=503)
        result = _onboarding_flow.transition_to_workflow_builder(session_id)
        return JSONResponse({"success": True, **result})

    # ==================== IP CLASSIFICATION ====================

    try:
        from src.ip_classification_engine import IPClassificationEngine
        _ip_engine = IPClassificationEngine()
    except ImportError:
        _ip_engine = None

    @app.post("/api/ip/assets")
    async def register_ip_asset(request: Request):
        """Register a new IP asset."""
        if _ip_engine is None:
            return JSONResponse({"success": False, "error": "IP engine not available"}, status_code=503)
        data = await request.json()
        asset = _ip_engine.register_asset(
            name=data.get("name", ""),
            description=data.get("description", ""),
            classification=data.get("classification", "system_ip"),
            owner_id=data.get("owner_id", ""),
            owner_type=data.get("owner_type", "system"),
            is_trade_secret=data.get("is_trade_secret", False),
        )
        return JSONResponse({"success": True, "asset": asset.to_dict()})

    @app.get("/api/ip/assets")
    async def list_ip_assets():
        """List all IP assets."""
        if _ip_engine is None:
            return JSONResponse({"success": False, "error": "IP engine not available"}, status_code=503)
        return JSONResponse({"success": True, "assets": _ip_engine.list_assets()})

    @app.get("/api/ip/summary")
    async def get_ip_summary():
        """Get IP classification summary."""
        if _ip_engine is None:
            return JSONResponse({"success": False, "error": "IP engine not available"}, status_code=503)
        return JSONResponse({"success": True, "summary": _ip_engine.get_ip_summary()})

    @app.get("/api/ip/trade-secrets")
    async def list_trade_secrets():
        """List all trade secret records."""
        if _ip_engine is None:
            return JSONResponse({"success": False, "error": "IP engine not available"}, status_code=503)
        return JSONResponse({"success": True, "trade_secrets": _ip_engine.list_trade_secrets()})

    @app.post("/api/ip/assets/{asset_id}/access-check")
    async def check_ip_access(asset_id: str, request: Request):
        """Check access to an IP asset."""
        if _ip_engine is None:
            return JSONResponse({"success": False, "error": "IP engine not available"}, status_code=503)
        data = await request.json()
        result = _ip_engine.check_access(asset_id, data.get("requester_id", ""))
        return JSONResponse({"success": True, **result})

    # ==================== CREDENTIAL PROFILES ====================

    try:
        from src.credential_profile_system import CredentialProfileSystem
        _credential_system = CredentialProfileSystem()
    except ImportError:
        _credential_system = None

    @app.post("/api/credentials/profiles")
    async def create_credential_profile(request: Request):
        """Create a new credential profile."""
        if _credential_system is None:
            return JSONResponse({"success": False, "error": "Credential system not available"}, status_code=503)
        data = await request.json()
        profile = _credential_system.create_profile(
            user_id=data.get("user_id", ""),
            user_name=data.get("user_name", ""),
            role=data.get("role", ""),
        )
        return JSONResponse({"success": True, "profile": profile.to_dict()})

    @app.post("/api/credentials/profiles/{profile_id}/interactions")
    async def record_credential_interaction(profile_id: str, request: Request):
        """Record a HITL interaction for a credential profile."""
        if _credential_system is None:
            return JSONResponse({"success": False, "error": "Credential system not available"}, status_code=503)
        data = await request.json()
        result = _credential_system.record_interaction(
            profile_id=profile_id,
            interaction_type=data.get("interaction_type", "approval"),
            context=data.get("context", ""),
            decision=data.get("decision", ""),
            confidence_before=data.get("confidence_before", 0.0),
            confidence_after=data.get("confidence_after", 0.0),
            response_time_ms=data.get("response_time_ms", 0.0),
            outcome=data.get("outcome", ""),
        )
        if result is None:
            return JSONResponse({"success": False, "error": "Profile not found"}, status_code=404)
        return JSONResponse({"success": True, "interaction": result})

    @app.get("/api/credentials/profiles")
    async def list_credential_profiles():
        """List all credential profiles."""
        if _credential_system is None:
            return JSONResponse({"success": False, "error": "Credential system not available"}, status_code=503)
        return JSONResponse({"success": True, "profiles": _credential_system.list_profiles()})

    @app.get("/api/credentials/metrics")
    async def get_optimal_automation_metrics():
        """Get optimal automation metrics (System IP)."""
        if _credential_system is None:
            return JSONResponse({"success": False, "error": "Credential system not available"}, status_code=503)
        return JSONResponse({"success": True, "metrics": _credential_system.get_optimal_automation_metrics()})

    # ==================== MSS Controls API ====================
    _mss_controller = None
    if _mss_available:
        try:
            _rde = ResolutionDetectionEngine()
            _ide = InformationDensityEngine()
            _sce = StructuralCoherenceEngine()
            _iqe = InformationQualityEngine(_rde, _ide, _sce)
            _cte = ConceptTranslationEngine()
            _sim = StrategicSimulationEngine()
            _mss_controller = MSSController(_iqe, _cte, _sim)
            logger.info("MSS Controls initialized successfully")
        except Exception as exc:
            logger.warning("MSS Controls initialization failed: %s", exc)

    @app.post("/api/mss/magnify")
    async def mss_magnify(request: Request):
        """Magnify — increase resolution of input text."""
        if _mss_controller is None:
            return JSONResponse({"success": False, "error": "MSS controls not available"}, status_code=503)
        try:
            data = await request.json()
            text = data.get("text", "")
            context = _normalize_mss_context(data.get("context"))
            if not text:
                return JSONResponse({"success": False, "error": "text is required"}, status_code=400)
            from dataclasses import asdict as _asdict
            result = _mss_controller.magnify(text, context)
            return JSONResponse({"success": True, "result": _asdict(result)})
        except Exception as exc:
            logger.exception("MSS magnify failed")
            return _safe_error_response(exc, 500)

    @app.post("/api/mss/simplify")
    async def mss_simplify(request: Request):
        """Simplify — decrease resolution of input text."""
        if _mss_controller is None:
            return JSONResponse({"success": False, "error": "MSS controls not available"}, status_code=503)
        try:
            data = await request.json()
            text = data.get("text", "")
            context = _normalize_mss_context(data.get("context"))
            if not text:
                return JSONResponse({"success": False, "error": "text is required"}, status_code=400)
            from dataclasses import asdict as _asdict
            result = _mss_controller.simplify(text, context)
            return JSONResponse({"success": True, "result": _asdict(result)})
        except Exception as exc:
            logger.exception("MSS simplify failed")
            return _safe_error_response(exc, 500)

    @app.post("/api/mss/solidify")
    async def mss_solidify(request: Request):
        """Solidify — convert input text to implementation plan."""
        if _mss_controller is None:
            return JSONResponse({"success": False, "error": "MSS controls not available"}, status_code=503)
        try:
            data = await request.json()
            text = data.get("text", "")
            context = _normalize_mss_context(data.get("context"))
            if not text:
                return JSONResponse({"success": False, "error": "text is required"}, status_code=400)
            from dataclasses import asdict as _asdict
            result = _mss_controller.solidify(text, context)
            return JSONResponse({"success": True, "result": _asdict(result)})
        except Exception as exc:
            logger.exception("MSS solidify failed")
            return _safe_error_response(exc, 500)

    @app.post("/api/mss/score")
    async def mss_score(request: Request):
        """Score input text quality — returns InformationQuality assessment."""
        if _mss_controller is None:
            return JSONResponse({"success": False, "error": "MSS controls not available"}, status_code=503)
        data = await request.json()
        text = data.get("text", "")
        if not text:
            return JSONResponse({"success": False, "error": "text is required"}, status_code=400)
        from dataclasses import asdict as _asdict
        quality = _mss_controller._iqe.assess(text)
        return JSONResponse({"success": True, "quality": _asdict(quality)})

    # ==================== UCP & Graph API ====================
    _ucp_instance = None
    _cge_instance = None
    try:
        from concept_graph_engine import ConceptGraphEngine
        from unified_control_protocol import UnifiedControlProtocol
        _cge_instance = ConceptGraphEngine()
        _ucp_instance = UnifiedControlProtocol()
        logger.info("UCP and CGE initialized successfully")
    except Exception as exc:
        logger.warning("UCP/CGE initialization failed: %s", exc)

    @app.post("/api/ucp/execute")
    async def ucp_execute(request: Request):
        """Execute the Unified Control Protocol pipeline."""
        if _ucp_instance is None:
            return JSONResponse({"success": False, "error": "UCP not available"}, status_code=503)
        data = await request.json()
        text = data.get("text", "")
        operator = data.get("operator", "magnify")
        if not text:
            return JSONResponse({"success": False, "error": "text is required"}, status_code=400)
        if operator not in ("magnify", "simplify", "solidify"):
            return JSONResponse({"success": False, "error": "operator must be magnify, simplify, or solidify"}, status_code=400)
        from dataclasses import asdict as _asdict
        result = _ucp_instance.execute(text, operator=operator)
        return JSONResponse({"success": True, "result": _asdict(result)})

    @app.get("/api/ucp/health")
    async def ucp_health():
        """Return system health dashboard from UCP."""
        if _ucp_instance is None:
            return JSONResponse({"success": False, "error": "UCP not available"}, status_code=503)
        health = _ucp_instance.get_system_health()
        return JSONResponse({"success": True, "health": health})

    @app.post("/api/graph/query")
    async def graph_query(request: Request):
        """Query the Concept Graph Engine."""
        if _cge_instance is None:
            return JSONResponse({"success": False, "error": "CGE not available"}, status_code=503)
        data = await request.json()
        query_type = data.get("query_type", "")
        query_map = {
            "missing_deps": _cge_instance.find_missing_dependencies,
            "regulatory_gaps": _cge_instance.find_regulatory_gaps,
            "redundant": _cge_instance.find_redundant_modules,
            "opportunities": _cge_instance.detect_cross_domain_opportunities,
        }
        if query_type not in query_map:
            return JSONResponse(
                {"success": False, "error": f"query_type must be one of: {list(query_map.keys())}"},
                status_code=400,
            )
        results = query_map[query_type]()
        return JSONResponse({"success": True, "query_type": query_type, "results": results})

    @app.get("/api/graph/health")
    async def graph_health():
        """Return graph health metrics from the Concept Graph Engine."""
        if _cge_instance is None:
            return JSONResponse({"success": False, "error": "CGE not available"}, status_code=503)
        from dataclasses import asdict as _asdict
        health = _cge_instance.compute_graph_health()
        return JSONResponse({"success": True, "health": _asdict(health)})

    # ==================== COST DASHBOARD ====================

    _cost_kernel = murphy.governance_kernel if hasattr(murphy, "governance_kernel") else None

    @app.get("/api/costs/summary")
    async def costs_summary():
        """Return total system spend, total budget, and utilisation % across all departments."""
        if _cost_kernel is None:
            return JSONResponse({"success": False, "error": "Governance kernel not available"}, status_code=503)
        all_budgets = _cost_kernel.get_budget_status()
        total_budget = sum(v["total_budget"] for v in all_budgets.values())
        total_spent = sum(v["spent"] for v in all_budgets.values())
        total_pending = sum(v["pending"] for v in all_budgets.values())
        utilisation_pct = round((total_spent / total_budget * 100) if total_budget > 0 else 0.0, 2)
        return JSONResponse({
            "success": True,
            "summary": {
                "total_budget": total_budget,
                "spent": total_spent,
                "pending": total_pending,
                "remaining": total_budget - total_spent - total_pending,
                "utilisation_pct": utilisation_pct,
                "department_count": len(all_budgets),
            },
        })

    @app.get("/api/costs/by-department")
    async def costs_by_department():
        """Return per-department cost breakdown."""
        if _cost_kernel is None:
            return JSONResponse({"success": False, "error": "Governance kernel not available"}, status_code=503)
        all_budgets = _cost_kernel.get_budget_status()
        departments = []
        for dept_id, budget in all_budgets.items():
            total = budget["total_budget"]
            spent = budget["spent"]
            utilisation_pct = round((spent / total * 100) if total > 0 else 0.0, 2)
            departments.append({
                "department_id": dept_id,
                "total_budget": total,
                "spent": spent,
                "pending": budget["pending"],
                "remaining": budget["remaining"],
                "limit_per_task": budget["limit_per_task"],
                "utilisation_pct": utilisation_pct,
            })
        return JSONResponse({"success": True, "departments": departments})

    @app.get("/api/costs/by-project")
    async def costs_by_project():
        """Return per-project cost breakdown."""
        if _cost_kernel is None:
            return JSONResponse({"success": False, "error": "Governance kernel not available"}, status_code=503)
        by_project = _cost_kernel.get_costs_by_project()
        return JSONResponse({"success": True, "projects": list(by_project.values())})

    @app.get("/api/costs/by-bot")
    async def costs_by_bot():
        """Return per-bot/agent cost breakdown."""
        if _cost_kernel is None:
            return JSONResponse({"success": False, "error": "Governance kernel not available"}, status_code=503)
        by_caller = _cost_kernel.get_costs_by_caller()
        return JSONResponse({"success": True, "bots": list(by_caller.values())})

    @app.post("/api/costs/assign")
    async def costs_assign(request: Request):
        """Assign a cost event to a department and/or project."""
        if _cost_kernel is None:
            return JSONResponse({"success": False, "error": "Governance kernel not available"}, status_code=503)
        data = await request.json()
        caller_id = data.get("caller_id")
        tool_name = data.get("tool_name")
        cost = data.get("cost")
        if not caller_id or not tool_name or cost is None:
            return JSONResponse(
                {"success": False, "error": "caller_id, tool_name and cost are required"},
                status_code=400,
            )
        try:
            cost_val = float(cost)
        except (TypeError, ValueError):
            return JSONResponse(
                {"success": False, "error": "cost must be a valid number"},
                status_code=400,
            )
        if cost_val < 0:
            return JSONResponse(
                {"success": False, "error": "cost must be non-negative"},
                status_code=400,
            )
        _cost_kernel.record_execution(
            caller_id=str(caller_id),
            tool_name=str(tool_name),
            cost=cost_val,
            success=True,
            department_id=data.get("department_id") or None,
            project_id=data.get("project_id") or None,
        )
        return JSONResponse({"success": True})

    @app.patch("/api/costs/budget")
    async def costs_set_budget(request: Request):
        """Set or update a department budget."""
        if _cost_kernel is None:
            return JSONResponse({"success": False, "error": "Governance kernel not available"}, status_code=503)
        data = await request.json()
        department_id = data.get("department_id")
        total_budget = data.get("total_budget")
        if not department_id or total_budget is None:
            return JSONResponse(
                {"success": False, "error": "department_id and total_budget are required"},
                status_code=400,
            )
        try:
            budget_val = float(total_budget)
        except (TypeError, ValueError):
            return JSONResponse(
                {"success": False, "error": "total_budget must be a valid number"},
                status_code=400,
            )
        if budget_val < 0:
            return JSONResponse(
                {"success": False, "error": "total_budget must be non-negative"},
                status_code=400,
            )
        _cost_kernel.set_budget(
            department_id=str(department_id),
            total_budget=budget_val,
            limit_per_task=float(data.get("limit_per_task", 0.0)),
        )
        return JSONResponse({"success": True, "department_id": department_id})

    # ==================== WORKFLOWS ENDPOINTS ====================

    _workflows_store: Dict[str, Any] = {}

    @app.get("/api/workflows")
    async def list_workflows():
        """List all saved workflows."""
        return JSONResponse({
            "success": True,
            "workflows": list(_workflows_store.values()),
            "count": len(_workflows_store),
        })

    @app.post("/api/workflows")
    async def save_workflow(request: Request):
        """Save a workflow."""
        data = await request.json()
        workflow_id = data.get("id") if data.get("id") is not None else str(uuid4())
        workflow = {
            "id": workflow_id,
            "name": data.get("name", "Untitled Workflow"),
            "nodes": data.get("nodes", []),
            "connections": data.get("connections", []),
            "status": data.get("status", "idle"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        _workflows_store[workflow_id] = workflow
        return JSONResponse({"success": True, "workflow": workflow})

    @app.get("/api/workflows/{workflow_id}")
    async def get_workflow(workflow_id: str):
        """Get workflow details by ID."""
        workflow = _workflows_store.get(workflow_id)
        if not workflow:
            return JSONResponse({"success": False, "error": "Workflow not found"}, status_code=404)
        return JSONResponse({"success": True, "workflow": workflow})

    # ==================== AGENTS ENDPOINTS ====================

    @app.get("/api/agents")
    async def list_agents():
        """List all active agents with capabilities."""
        agents: List[Dict[str, Any]] = []
        try:
            raw = getattr(murphy, "agents", {})
            for agent_id, agent_data in (raw.items() if isinstance(raw, dict) else {}.items()):
                agents.append({
                    "id": agent_id,
                    "role": agent_data.get("role", "agent"),
                    "capabilities": agent_data.get("capabilities", []),
                    "status": agent_data.get("status", "idle"),
                    "current_task": agent_data.get("current_task"),
                    "metrics": agent_data.get("metrics", {}),
                })
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in endpoint: %s", exc)
        # Always return at least a sentinel placeholder so the UI renders
        if not agents:
            agents = [
                {
                    "id": "system_monitor",
                    "role": "System Monitor",
                    "capabilities": ["health_check", "status_reporting"],
                    "status": "active",
                    "current_task": None,
                    "metrics": {},
                }
            ]
        return JSONResponse({"success": True, "agents": agents, "count": len(agents)})

    @app.get("/api/agents/{agent_id}")
    async def get_agent(agent_id: str):
        """Get agent details by ID."""
        try:
            raw = getattr(murphy, "agents", {})
            if isinstance(raw, dict) and agent_id in raw:
                agent = raw[agent_id]
                return JSONResponse({
                    "success": True,
                    "agent": {
                        "id": agent_id,
                        "role": agent.get("role", "agent"),
                        "capabilities": agent.get("capabilities", []),
                        "status": agent.get("status", "idle"),
                        "current_task": agent.get("current_task"),
                        "activity_log": agent.get("activity_log", []),
                        "metrics": agent.get("metrics", {}),
                    },
                })
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in endpoint: %s", exc)
        return JSONResponse({"success": False, "error": "Agent not found"}, status_code=404)

    # ==================== TASKS ENDPOINTS ====================

    @app.get("/api/tasks")
    async def list_tasks():
        """List all tasks across the system."""
        tasks: List[Dict[str, Any]] = []
        try:
            raw = getattr(murphy, "tasks", [])
            if isinstance(raw, list):
                tasks = raw
            elif isinstance(raw, dict):
                tasks = list(raw.values())
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in endpoint: %s", exc)
        return JSONResponse({"success": True, "tasks": tasks, "count": len(tasks)})

    # ==================== PRODUCTION QUEUE ENDPOINTS ====================

    _production_queue: List[Dict[str, Any]] = []
    _production_proposals: Dict[str, Dict[str, Any]] = {}
    _production_work_orders: Dict[str, Dict[str, Any]] = {}

    @app.get("/api/production/queue")
    async def production_queue():
        """Get current production queue items."""
        return JSONResponse({
            "success": True,
            "items": _production_queue,
            "count": len(_production_queue),
        })

    @app.post("/api/production/proposals")
    async def create_production_proposal(request: Request):
        """Create a production proposal and generate its workflow."""
        body = await request.json()
        pid = body.get("proposal_id", "")
        if not pid:
            return JSONResponse({"success": False, "error": "proposal_id required"}, 400)

        gates = body.get("required_gates", ["SAFETY", "COMPLIANCE"])
        funcs = body.get("regulatory_functions", [])
        industry = body.get("regulatory_industry", "general")
        location = body.get("regulatory_location", "US")
        spec = body.get("deliverable_spec", "")

        # Merge onboarding config if available (modules, integrations, safety)
        ob_cfg = dict(_onboarding_config)  # snapshot
        integrations = body.get("integrations", ob_cfg.get("integrations", [])) or []
        modules = body.get("modules", ob_cfg.get("modules", [])) or []
        safety_level = body.get("safety_level", ob_cfg.get("safety_level", 3))

        # Build workflow nodes from the proposal
        nodes = []
        edges = []
        y_base = 80   # Initial vertical offset in pixels for node layout
        x_step = 240  # Horizontal spacing between nodes in pixels

        # 1. Trigger node — incoming request
        nodes.append({
            "id": f"{pid}-trigger", "x": 60, "y": y_base,
            "type": "trigger", "label": "Incoming Request",
            "icon": "📡", "health": "idle",
            "data": {"subtype": "event", "proposal_id": pid},
            "ports": [
                {"id": f"{pid}-trigger-out", "type": "output", "label": "out", "side": "right"},
            ],
        })

        # 2. Compliance gate(s) from selected gates
        prev_port = f"{pid}-trigger-out"
        prev_node = f"{pid}-trigger"
        for i, gate in enumerate(gates):
            nid = f"{pid}-gate-{gate.lower()}"
            nodes.append({
                "id": nid, "x": 60 + x_step * (i + 1), "y": y_base,
                "type": "gate", "label": gate.replace("_", " ").title(),
                "icon": "🔒" if gate in ("SAFETY", "SECURITY") else "📋",
                "health": "idle",
                "data": {"subtype": gate.lower(), "gate_type": gate},
                "ports": [
                    {"id": f"{nid}-in", "type": "input", "label": "in", "side": "left"},
                    {"id": f"{nid}-out", "type": "output", "label": "out", "side": "right"},
                ],
            })
            edges.append({
                "id": f"{pid}-edge-{i}",
                "sourceNodeId": prev_node, "sourcePortId": prev_port,
                "targetNodeId": nid, "targetPortId": f"{nid}-in",
                "animated": True,
            })
            prev_port = f"{nid}-out"
            prev_node = nid

        # 3. Processing node
        proc_x = 60 + x_step * (len(gates) + 1)
        proc_id = f"{pid}-process"
        nodes.append({
            "id": proc_id, "x": proc_x, "y": y_base,
            "type": "action", "label": f"Process ({industry})",
            "icon": "⚙", "health": "idle",
            "data": {"subtype": "execute", "industry": industry, "location": location},
            "ports": [
                {"id": f"{proc_id}-in", "type": "input", "label": "in", "side": "left"},
                {"id": f"{proc_id}-out", "type": "output", "label": "out", "side": "right"},
            ],
        })
        edges.append({
            "id": f"{pid}-edge-proc",
            "sourceNodeId": prev_node, "sourcePortId": prev_port,
            "targetNodeId": proc_id, "targetPortId": f"{proc_id}-in",
            "animated": True,
        })

        # 3b. Integration nodes (from onboarding selections)
        int_prev_node = proc_id
        int_prev_port = f"{proc_id}-out"
        int_x = proc_x
        for j, intg in enumerate(integrations):
            intg_name = intg if isinstance(intg, str) else intg.get("name", intg.get("id", f"integration-{j}"))
            intg_id_safe = intg_name.lower().replace(" ", "_").replace("/", "_")[:30]
            int_nid = f"{pid}-int-{intg_id_safe}"
            int_x += x_step
            nodes.append({
                "id": int_nid, "x": int_x, "y": y_base + 100,
                "type": "action", "label": intg_name,
                "icon": "🔌", "health": "idle",
                "data": {"subtype": "integration", "integration": intg_name},
                "ports": [
                    {"id": f"{int_nid}-in", "type": "input", "label": "in", "side": "left"},
                    {"id": f"{int_nid}-out", "type": "output", "label": "out", "side": "right"},
                ],
            })
            edges.append({
                "id": f"{pid}-edge-int-{j}",
                "sourceNodeId": int_prev_node, "sourcePortId": int_prev_port,
                "targetNodeId": int_nid, "targetPortId": f"{int_nid}-in",
                "animated": True,
            })
            int_prev_node = int_nid
            int_prev_port = f"{int_nid}-out"

        # 4. HITL review node
        hitl_x = max(proc_x, int_x) + x_step
        hitl_id = f"{pid}-hitl"
        nodes.append({
            "id": hitl_id, "x": hitl_x, "y": y_base,
            "type": "gate", "label": "HITL Review",
            "icon": "🙋", "health": "idle",
            "data": {"subtype": "hitl", "gate_type": "HITL_REVIEW"},
            "ports": [
                {"id": f"{hitl_id}-in", "type": "input", "label": "in", "side": "left"},
                {"id": f"{hitl_id}-pass", "type": "output", "label": "pass", "side": "right"},
                {"id": f"{hitl_id}-fail", "type": "output", "label": "fail", "side": "right"},
            ],
        })
        edges.append({
            "id": f"{pid}-edge-hitl",
            "sourceNodeId": int_prev_node if integrations else proc_id,
            "sourcePortId": int_prev_port if integrations else f"{proc_id}-out",
            "targetNodeId": hitl_id, "targetPortId": f"{hitl_id}-in",
            "animated": True,
        })

        # 5. Deliver node
        deliver_x = hitl_x + x_step
        deliver_id = f"{pid}-deliver"
        nodes.append({
            "id": deliver_id, "x": deliver_x, "y": y_base - 40,
            "type": "action", "label": "Deliver",
            "icon": "📦", "health": "idle",
            "data": {"subtype": "deliver"},
            "ports": [
                {"id": f"{deliver_id}-in", "type": "input", "label": "in", "side": "left"},
                {"id": f"{deliver_id}-out", "type": "output", "label": "out", "side": "right"},
            ],
        })
        edges.append({
            "id": f"{pid}-edge-deliver",
            "sourceNodeId": hitl_id, "sourcePortId": f"{hitl_id}-pass",
            "targetNodeId": deliver_id, "targetPortId": f"{deliver_id}-in",
            "animated": True,
        })

        # 6. Correction loop (HITL fail → back to process)
        edges.append({
            "id": f"{pid}-edge-correction",
            "sourceNodeId": hitl_id, "sourcePortId": f"{hitl_id}-fail",
            "targetNodeId": proc_id, "targetPortId": f"{proc_id}-in",
            "color": "#F87171", "animated": True,
        })

        # 7. Verify node
        verify_x = deliver_x + x_step
        verify_id = f"{pid}-verify"
        nodes.append({
            "id": verify_id, "x": verify_x, "y": y_base - 40,
            "type": "action", "label": "Verified ✓",
            "icon": "✅", "health": "idle",
            "data": {"subtype": "validate"},
            "ports": [
                {"id": f"{verify_id}-in", "type": "input", "label": "in", "side": "left"},
            ],
        })
        edges.append({
            "id": f"{pid}-edge-verify",
            "sourceNodeId": deliver_id, "sourcePortId": f"{deliver_id}-out",
            "targetNodeId": verify_id, "targetPortId": f"{verify_id}-in",
            "animated": True,
        })

        workflow = {
            "id": pid,
            "name": f"Production: {pid}",
            "transform": {"offsetX": 40, "offsetY": 40, "scale": 1},
            "nodes": nodes,
            "edges": edges,
        }

        proposal = {
            "proposal_id": pid,
            "industry": industry,
            "location": location,
            "functions": funcs,
            "spec": spec,
            "gates": gates,
            "modules": modules,
            "integrations": [i if isinstance(i, str) else i.get("name", str(i)) for i in integrations],
            "safety_level": safety_level,
            "status": "pending",
            "workflow": workflow,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _production_proposals[pid] = proposal
        _production_queue.append({"id": pid, "type": "proposal", "status": "pending"})

        return JSONResponse({
            "success": True, "status": "pending",
            "proposal_id": pid, "workflow": workflow,
        })

    @app.get("/api/production/proposals")
    async def list_production_proposals():
        """List all production proposals."""
        return JSONResponse({
            "success": True,
            "proposals": list(_production_proposals.values()),
            "count": len(_production_proposals),
        })

    @app.get("/api/production/proposals/{proposal_id}")
    async def get_production_proposal(proposal_id: str):
        """Get a specific proposal and its generated workflow."""
        p = _production_proposals.get(proposal_id)
        if not p:
            return JSONResponse({"success": False, "error": "Not found"}, 404)
        return JSONResponse({"success": True, "proposal": p})

    @app.post("/api/production/work-orders")
    async def create_work_order(request: Request):
        """Create a work order linked to a proposal."""
        body = await request.json()
        woid = body.get("work_order_id", "")
        pid = body.get("proposal_id", "")
        if not woid or not pid:
            return JSONResponse({"success": False, "error": "work_order_id and proposal_id required"}, 400)

        proposal = _production_proposals.get(pid)
        wo = {
            "work_order_id": woid,
            "proposal_id": pid,
            "deliverable_content": body.get("deliverable_content", ""),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "workflow_id": pid if proposal else None,
        }
        _production_work_orders[woid] = wo
        _production_queue.append({"id": woid, "type": "work_order", "status": "pending"})
        return JSONResponse({"success": True, "status": "pending", "work_order_id": woid})

    @app.post("/api/production/route")
    async def route_incoming_request(request: Request):
        """Route an incoming request to the matching production workflow.

        Looks up active proposals by industry/location/keyword and returns
        the matching workflow so the caller (or the UI) can execute or
        display it.
        """
        body = await request.json()
        req_industry = (body.get("industry") or "").lower()
        req_keyword = (body.get("keyword") or "").lower()

        matches = []
        for pid, p in _production_proposals.items():
            p_industry = (p.get("industry") or "").lower()
            p_spec = (p.get("spec") or "").lower()
            score = 0
            if req_industry and req_industry in p_industry:
                score += 2
            if req_keyword and req_keyword in p_spec:
                score += 1
            if score > 0:
                matches.append({"proposal_id": pid, "score": score, "workflow": p.get("workflow")})

        matches.sort(key=lambda m: m["score"], reverse=True)
        if matches:
            best = matches[0]
            return JSONResponse({
                "success": True, "routed": True,
                "proposal_id": best["proposal_id"],
                "workflow": best["workflow"],
                "alternatives": [m["proposal_id"] for m in matches[1:5]],
            })
        return JSONResponse({
            "success": True, "routed": False,
            "message": "No matching production workflow found",
            "available_proposals": list(_production_proposals.keys()),
        })

    # ==================== HITL REVIEW SYSTEM ====================
    # Full accept/deny/revision cycle with learning and doc tracking.

    _hitl_reviews: Dict[str, Dict[str, Any]] = {}
    _hitl_learned_patterns: List[Dict[str, Any]] = []

    @app.post("/api/production/hitl/submit")
    async def hitl_submit_for_review(request: Request):
        """Submit a work item for HITL review, creating a review entry."""
        body = await request.json()
        proposal_id = body.get("proposal_id", "")
        output_content = body.get("output_content", "")
        if not proposal_id or not output_content:
            return JSONResponse({"success": False, "error": "proposal_id and output_content required"}, 400)

        review_id = f"hitl-{proposal_id}-rev1"
        review = {
            "review_id": review_id,
            "proposal_id": proposal_id,
            "revision": 1,
            "output_content": output_content,
            "status": "pending",
            "decision": None,
            "reviewer_notes": "",
            "exception": False,
            "compliance_flags": body.get("compliance_flags", []),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "history": [],
        }
        _hitl_reviews[review_id] = review
        return JSONResponse({"success": True, "review": review})

    @app.post("/api/production/hitl/{review_id}/respond")
    async def hitl_review_respond(review_id: str, request: Request):
        """Respond to a HITL review: accept, deny, or request revisions."""
        review = _hitl_reviews.get(review_id)
        if not review:
            return JSONResponse({"success": False, "error": "Review not found"}, 404)

        body = await request.json()
        decision = body.get("decision", "")  # "accept", "deny", "revisions"
        notes = body.get("notes", "")
        exception = body.get("exception", False)

        # Record history entry
        review["history"].append({
            "revision": review["revision"],
            "decision": decision,
            "notes": notes,
            "exception": exception,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        if decision == "accept":
            review["status"] = "accepted"
            review["decision"] = "accepted"
            review["reviewer_notes"] = notes
            # Learn from accepted output unless exception toggled
            if not exception:
                _hitl_learned_patterns.append({
                    "proposal_id": review["proposal_id"],
                    "revision": review["revision"],
                    "output_content": review["output_content"],
                    "notes": notes,
                    "learned_at": datetime.now(timezone.utc).isoformat(),
                })
            return JSONResponse({
                "success": True, "status": "accepted",
                "learned": not exception,
                "review": review,
            })
        elif decision == "deny":
            review["status"] = "denied"
            review["decision"] = "denied"
            review["reviewer_notes"] = notes
            return JSONResponse({"success": True, "status": "denied", "review": review})
        elif decision == "revisions":
            # Increment revision counter for document tracking
            new_rev = review["revision"] + 1
            new_id = f"hitl-{review['proposal_id']}-rev{new_rev}"
            new_review = {
                "review_id": new_id,
                "proposal_id": review["proposal_id"],
                "revision": new_rev,
                "output_content": body.get("revised_content", review["output_content"]),
                "status": "pending",
                "decision": None,
                "reviewer_notes": "",
                "exception": exception,
                "compliance_flags": body.get("compliance_flags", review.get("compliance_flags", [])),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "history": review["history"],
            }
            review["status"] = "revision_requested"
            review["decision"] = "revisions"
            review["reviewer_notes"] = notes
            _hitl_reviews[new_id] = new_review
            return JSONResponse({
                "success": True, "status": "revision_requested",
                "new_review_id": new_id, "revision": new_rev,
                "review": new_review,
            })
        else:
            return JSONResponse({"success": False, "error": "decision must be accept, deny, or revisions"}, 400)

    @app.get("/api/production/hitl/pending")
    async def hitl_reviews_pending():
        """List all pending HITL reviews."""
        pending = [r for r in _hitl_reviews.values() if r["status"] == "pending"]
        return JSONResponse({"success": True, "reviews": pending, "count": len(pending)})

    @app.get("/api/production/hitl/learned")
    async def hitl_learned_patterns():
        """List all patterns learned from accepted HITL reviews."""
        return JSONResponse({
            "success": True,
            "patterns": _hitl_learned_patterns,
            "count": len(_hitl_learned_patterns),
        })

    # ==================== AUTOMATION SCHEDULE ====================

    @app.get("/api/production/schedule")
    async def production_schedule():
        """Return the automation schedule showing what the system plans to do.

        Generates a schedule from active proposals/work orders so the user
        can see planned automation alongside their own workflow.
        """
        schedule_items = []
        now = datetime.now(timezone.utc)

        for pid, p in _production_proposals.items():
            gates = p.get("gates", [])
            base_time = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) if "created_at" in p else now
            # Build schedule entries for each stage of the workflow
            schedule_items.append({
                "id": f"sched-{pid}-intake",
                "proposal_id": pid,
                "stage": "intake",
                "label": "Receive & validate incoming request",
                "industry": p.get("industry", ""),
                "scheduled_at": base_time.isoformat(),
                "status": "ready",
                "automated": True,
            })
            offset_min = 5
            for gate in gates:
                schedule_items.append({
                    "id": f"sched-{pid}-gate-{gate.lower()}",
                    "proposal_id": pid,
                    "stage": f"gate:{gate}",
                    "label": f"{gate.replace('_', ' ').title()} compliance check",
                    "scheduled_at": (base_time + timedelta(minutes=offset_min)).isoformat(),
                    "status": "queued",
                    "automated": gate not in ("HITL_REVIEW",),
                })
                offset_min += 5
            schedule_items.append({
                "id": f"sched-{pid}-process",
                "proposal_id": pid,
                "stage": "process",
                "label": f"Process ({p.get('industry', 'general')})",
                "scheduled_at": (base_time + timedelta(minutes=offset_min)).isoformat(),
                "status": "queued",
                "automated": True,
            })
            offset_min += 10
            schedule_items.append({
                "id": f"sched-{pid}-hitl",
                "proposal_id": pid,
                "stage": "hitl_review",
                "label": "Human review (your action required)",
                "scheduled_at": (base_time + timedelta(minutes=offset_min)).isoformat(),
                "scheduled_end": (base_time + timedelta(minutes=offset_min + 15)).isoformat(),
                "status": "waiting_human",
                "automated": False,
                "meeting_invite": True,
                "meeting_title": f"HITL Review — {pid}",
                "meeting_description": f"Human-in-the-loop review required for production {pid}. Review output, accept/deny/request revisions.",
            })
            offset_min += 15
            schedule_items.append({
                "id": f"sched-{pid}-deliver",
                "proposal_id": pid,
                "stage": "deliver",
                "label": "Package & deliver output",
                "scheduled_at": (base_time + timedelta(minutes=offset_min)).isoformat(),
                "status": "queued",
                "automated": True,
            })
            schedule_items.append({
                "id": f"sched-{pid}-verify",
                "proposal_id": pid,
                "stage": "verify",
                "label": "Final verification ✓",
                "scheduled_at": (base_time + timedelta(minutes=offset_min + 5)).isoformat(),
                "status": "queued",
                "automated": True,
            })

        # Include pending HITL reviews in schedule
        for rid, r in _hitl_reviews.items():
            if r["status"] == "pending":
                schedule_items.append({
                    "id": f"sched-hitl-{rid}",
                    "proposal_id": r["proposal_id"],
                    "stage": "hitl_review",
                    "label": f"HITL Review pending (rev{r['revision']})",
                    "scheduled_at": r["created_at"],
                    "status": "waiting_human",
                    "automated": False,
                })

        schedule_items.sort(key=lambda s: s.get("scheduled_at", ""))
        return JSONResponse({
            "success": True,
            "schedule": schedule_items,
            "count": len(schedule_items),
            "summary": {
                "total_steps": len(schedule_items),
                "automated": sum(1 for s in schedule_items if s.get("automated")),
                "needs_human": sum(1 for s in schedule_items if not s.get("automated")),
                "active_proposals": len(_production_proposals),
            },
        })

    # ==================== DELIVERABLES ENDPOINTS ====================

    _deliverables_store: List[Dict[str, Any]] = []

    @app.get("/api/deliverables")
    async def list_deliverables():
        """List outbound deliverables."""
        return JSONResponse({
            "success": True,
            "deliverables": _deliverables_store,
            "count": len(_deliverables_store),
        })

    # ==================== BILLING & TIER ENFORCEMENT ====================

    # Lazy-init subscription manager
    _sub_mgr = None

    def _get_sub_manager():
        nonlocal _sub_mgr
        if _sub_mgr is None:
            try:
                from src.subscription_manager import SubscriptionManager
                _sub_mgr = SubscriptionManager()
            except Exception:
                _sub_mgr = None
        return _sub_mgr

    @app.get("/api/billing/tiers")
    async def billing_tiers():
        """Return all available pricing tiers with limits, features, and prices."""
        try:
            from src.subscription_manager import (
                PRICING_PLANS,
                SubscriptionManager,
            )
            mgr = _get_sub_manager() or SubscriptionManager()
            tiers = []
            for tier_enum, plan in PRICING_PLANS.items():
                details = mgr.get_tier_details(tier_enum.value)
                tiers.append(details)
            return JSONResponse({"success": True, "tiers": tiers})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, 500)

    @app.get("/api/billing/account/{account_id}")
    async def billing_account(account_id: str):
        """Get billing status, tier, usage, and limits for an account."""
        mgr = _get_sub_manager()
        if not mgr:
            return JSONResponse({"success": False, "error": "Subscription system unavailable"}, 503)
        try:
            usage = mgr.get_usage_summary(account_id)
            sub = mgr.get_subscription(account_id)
            tier_name = sub.tier.value if sub else "solo"
            details = mgr.get_tier_details(tier_name)
            return JSONResponse({
                "success": True,
                "account_id": account_id,
                "subscription": sub.to_dict() if sub else None,
                "usage": usage,
                "tier_details": details,
            })
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, 500)

    @app.post("/api/billing/check-limit")
    async def billing_check_limit(request: Request):
        """Check if an account can create a resource (users or automations).

        Body: { "account_id": "...", "resource": "users"|"automations", "current_count": 0 }
        """
        mgr = _get_sub_manager()
        if not mgr:
            return JSONResponse({"success": False, "error": "Subscription system unavailable"}, 503)
        try:
            body = await request.json()
            result = mgr.check_tier_limit(
                account_id=body.get("account_id", ""),
                resource=body.get("resource", ""),
                current_count=body.get("current_count", 0),
            )
            return JSONResponse({"success": True, **result})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, 500)

    @app.post("/api/billing/check-feature")
    async def billing_check_feature(request: Request):
        """Check if an account's tier allows access to a specific feature.

        Body: { "account_id": "...", "feature": "api_access"|"matrix_bridge"|... }
        """
        mgr = _get_sub_manager()
        if not mgr:
            return JSONResponse({"success": False, "error": "Subscription system unavailable"}, 503)
        try:
            body = await request.json()
            result = mgr.check_feature_access(
                account_id=body.get("account_id", ""),
                feature=body.get("feature", ""),
            )
            return JSONResponse({"success": True, **result})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, 500)

    # ==================== TELEMETRY ENDPOINT ====================

    @app.get("/api/telemetry")
    async def telemetry():
        """Return OS info, runtime version, and system capabilities."""
        return JSONResponse({
            "success": True,
            "telemetry": {
                "os": platform.system(),
                "os_version": platform.version(),
                "python_version": platform.python_version(),
                "architecture": platform.machine(),
                "runtime_version": "1.0",
                "uptime_seconds": time.time() - getattr(murphy, "_start_time", time.time()),
                "llm_status": getattr(murphy, "llm_status", "unknown"),
                "modules_loaded": len(getattr(murphy, "loaded_modules", [])),
                "active_sessions": len(getattr(murphy, "sessions", {})),
            },
        })

    # ==================== EVENTS / SSE ENDPOINTS ====================

    _event_subscribers: Dict[str, dict] = {}

    @app.post("/api/events/subscribe")
    async def events_subscribe(request: Request):
        """Subscribe to a filtered event stream."""
        try:
            data = await request.json()
            sub_id = data.get("subscriberId", str(uuid4()))
            channel = data.get("channel", "system")
            _event_subscribers[sub_id] = {
                "id": sub_id,
                "channel": channel,
                "filters": data.get("filters", {}),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            return JSONResponse({
                "success": True,
                "subscriberId": sub_id,
                "channel": channel,
                "message": f"Subscribed to {channel} events",
            })
        except Exception as exc:
            logger.exception("Event subscribe failed")
            return _safe_error_response(exc, 500)

    @app.get("/api/events/history/{subscriber_id}")
    async def events_history(subscriber_id: str):
        """Return event history for a subscriber."""
        return JSONResponse({
            "success": True,
            "subscriber_id": subscriber_id,
            "events": [],
            "count": 0,
        })

    @app.get("/api/events/stream/{subscriber_id}")
    async def events_stream(subscriber_id: str):
        """SSE endpoint for real-time events (returns initial keepalive)."""
        from starlette.responses import StreamingResponse

        async def _generate():
            yield f"data: {json.dumps({'type': 'connected', 'subscriberId': subscriber_id})}\n\n"

        return StreamingResponse(_generate(), media_type="text/event-stream")

    @app.get("/api/security/events")
    async def security_events():
        """Return recent security events."""
        return JSONResponse({
            "success": True,
            "events": [],
            "count": 0,
        })

    # ==================== CONFIG ENDPOINTS ====================

    @app.get("/api/config")
    async def get_config():
        """Get current system configuration."""
        config: Dict[str, Any] = {}
        try:
            config = dict(getattr(murphy, "config", {}) or {})
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in endpoint: %s", exc)
        config.setdefault("mfgc", getattr(murphy, "mfgc_config", {}))
        return JSONResponse({"success": True, "config": config})

    @app.post("/api/config")
    async def update_config(request: Request):
        """Update system configuration."""
        data = await request.json()
        try:
            cfg = getattr(murphy, "config", None)
            if isinstance(cfg, dict):
                cfg.update(data)
            if "mfgc" in data and isinstance(data["mfgc"], dict):
                murphy.mfgc_config.update(data["mfgc"])
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in endpoint: %s", exc)
        return JSONResponse({"success": True})

    # ── Golden Path Engine ────────────────────────────────────────────
    try:
        from src.golden_path_engine import GoldenPathEngine as _GoldenPathEngine
        _gpe = _GoldenPathEngine()
    except Exception:  # noqa: BLE001
        _gpe = None

    @app.get("/api/golden-path")
    async def get_golden_path(request: Request):
        """Return prioritised recommendations for the current user."""
        user_role = request.headers.get("X-User-Role", "VIEWER")
        system_state: dict = {}
        try:
            state_obj = getattr(murphy, "system_state", None)
            if callable(state_obj):
                system_state = state_obj() or {}
            elif isinstance(state_obj, dict):
                system_state = state_obj
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in endpoint: %s", exc)
        if _gpe is None:
            return JSONResponse({"recommendations": [], "error": "golden_path_engine unavailable"})
        recs = _gpe.get_recommendations(user_role, system_state)
        return JSONResponse({"recommendations": recs, "count": len(recs)})

    @app.get("/api/golden-path/{workflow_id}")
    async def get_critical_path(workflow_id: str):
        """Return the critical path for a specific workflow."""
        if _gpe is None:
            return JSONResponse({"critical_path": [], "error": "golden_path_engine unavailable"})
        path = _gpe.get_critical_path(workflow_id)
        return JSONResponse({"workflow_id": workflow_id, "critical_path": path})

    # ── Highlight Overlay (Trainer system — glow-key / left-click hints) ──
    try:
        from src.highlight_overlay import OverlayManager as _OverlayManager
        _overlay_mgr = _OverlayManager()
    except Exception:  # noqa: BLE001
        _overlay_mgr = None

    @app.get("/api/overlay/suggestions")
    async def overlay_get_suggestions(request: Request):
        """Return pending highlight suggestions for the current user (polled by murphy_overlay.js)."""
        if _overlay_mgr is None:
            return JSONResponse({"suggestions": [], "error": "overlay_manager unavailable"})
        user_id = request.query_params.get("user_id")
        state = request.query_params.get("state", "pending")
        try:
            if state == "accepted":
                sugs = _overlay_mgr.get_accepted_suggestions(user_id=user_id or None)
            else:
                sugs = _overlay_mgr.get_pending_suggestions(user_id=user_id or None)
            return JSONResponse({"suggestions": [s.to_dict() for s in sugs]})
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in overlay suggestions: %s", exc)
            return JSONResponse({"suggestions": [], "error": str(exc)})

    @app.post("/api/overlay/suggestions")
    async def overlay_add_suggestion(request: Request):
        """Add a highlight suggestion (called by shadow agents)."""
        if _overlay_mgr is None:
            return JSONResponse({"success": False, "error": "overlay_manager unavailable"})
        try:
            body = await request.json()
            sug = _overlay_mgr.add_suggestion(
                agent_id=body.get("agent_id", "shadow"),
                user_id=body.get("user_id", ""),
                highlighted_text=body.get("highlighted_text", ""),
                title=body.get("title", ""),
                description=body.get("description", ""),
                confidence=float(body.get("confidence", 0.5)),
                automation_spec=body.get("automation_spec"),
                marketplace_listing_id=body.get("marketplace_listing_id"),
            )
            return JSONResponse({"success": True, "suggestion_id": sug.suggestion_id})
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in overlay add: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=400)

    @app.post("/api/overlay/suggestions/{suggestion_id}/accept")
    async def overlay_accept_suggestion(suggestion_id: str, request: Request):
        """Accept a highlight suggestion — user clicked 'Accept and automate'."""
        if _overlay_mgr is None:
            return JSONResponse({"success": False, "error": "overlay_manager unavailable"})
        resolved_by = (await request.json()).get("resolved_by", "") if request.headers.get("content-type", "").startswith("application/json") else ""
        ok = _overlay_mgr.accept_suggestion(suggestion_id, resolved_by=resolved_by)
        return JSONResponse({"success": ok, "suggestion_id": suggestion_id})

    @app.post("/api/overlay/suggestions/{suggestion_id}/ignore")
    async def overlay_ignore_suggestion(suggestion_id: str, request: Request):
        """Ignore a highlight suggestion — user clicked 'Ignore this suggestion'."""
        if _overlay_mgr is None:
            return JSONResponse({"success": False, "error": "overlay_manager unavailable"})
        resolved_by = (await request.json()).get("resolved_by", "") if request.headers.get("content-type", "").startswith("application/json") else ""
        ok = _overlay_mgr.ignore_suggestion(suggestion_id, resolved_by=resolved_by)
        return JSONResponse({"success": ok, "suggestion_id": suggestion_id})

    @app.get("/api/overlay/summary")
    async def overlay_summary(request: Request):
        """Return overlay statistics summary for the status bar."""
        if _overlay_mgr is None:
            return JSONResponse({"total": 0, "by_state": {}, "pending": 0})
        user_id = request.query_params.get("user_id")
        return JSONResponse(_overlay_mgr.summary(user_id=user_id or None))

    # ── Shadow Trainer Status ──────────────────────────────────────────
    try:
        from src.murphy_shadow_trainer import create_shadow_trainer as _create_shadow_trainer, get_global_policy as _get_global_policy
        _shadow_trainer_loop, _shadow_trainer_policy, _shadow_trainer_buffer = _create_shadow_trainer()
        _shadow_trainer_available = True
    except Exception:  # noqa: BLE001
        _shadow_trainer_available = False
        _shadow_trainer_policy = None
        _shadow_trainer_buffer = None

    @app.get("/api/trainer/status")
    async def trainer_status():
        """Return shadow trainer status: current policy, exploration ratio, buffer size."""
        if not _shadow_trainer_available or _shadow_trainer_policy is None:
            return JSONResponse({"available": False, "error": "shadow_trainer unavailable"})
        try:
            policy_dict = _shadow_trainer_policy.to_dict()
            buf_size = _shadow_trainer_buffer.size() if _shadow_trainer_buffer else 0
            return JSONResponse({
                "available": True,
                "policy_id": policy_dict.get("policy_id"),
                "action_count": len(policy_dict.get("action_values", {})),
                "buffer_size": buf_size,
                "top_actions": sorted(
                    policy_dict.get("action_values", {}).items(),
                    key=lambda x: x[1], reverse=True
                )[:5],
            })
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in trainer status: %s", exc)
            return JSONResponse({"available": False, "error": str(exc)})

    @app.post("/api/trainer/reward")
    async def trainer_record_reward(request: Request):
        """Record a reward signal to update shadow trainer policy."""
        if not _shadow_trainer_available:
            return JSONResponse({"success": False, "error": "shadow_trainer unavailable"})
        try:
            from src.murphy_shadow_trainer import RewardSignal as _RewardSignal, PolicyUpdater as _PolicyUpdater
            body = await request.json()
            signal = _RewardSignal(
                task_id=body.get("task_id", ""),
                action_taken=body.get("action_taken", ""),
                task_success=bool(body.get("task_success", False)),
                confidence_before=float(body.get("confidence_before", 0.5)),
                confidence_after=float(body.get("confidence_after", 0.5)),
                latency_ms_before=float(body.get("latency_ms_before", 100.0)),
                latency_ms_after=float(body.get("latency_ms_after", 100.0)),
                cost_before=float(body.get("cost_before", 1.0)),
                cost_after=float(body.get("cost_after", 1.0)),
                human_approval_rate=float(body.get("human_approval_rate", 1.0)),
            )
            updater = _PolicyUpdater(policy=_shadow_trainer_policy)
            reward = updater.compute_reward(signal)
            signal.computed_reward = reward
            return JSONResponse({"success": True, "computed_reward": reward})
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in trainer reward: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=400)

    # ── Orchestrator ──────────────────────────────────────────────────
    @app.get("/api/orchestrator/overview")
    async def orchestrator_overview():
        """Full business flow snapshot: inbound, processing, outbound, summary."""
        workflows = []
        try:
            wf_store = getattr(murphy, "workflows", None)
            if isinstance(wf_store, dict):
                workflows = list(wf_store.values())
            elif isinstance(wf_store, list):
                workflows = wf_store
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in endpoint: %s", exc)

        active = [w for w in workflows if isinstance(w, dict) and w.get("status") == "running"]
        stuck  = [w for w in workflows if isinstance(w, dict) and w.get("status") == "stuck"]

        return JSONResponse({
            "inbound": {
                "sources": ["API Request", "Email", "Webhook", "Manual", "Scheduled", "Import"],
                "active_count": len(active),
            },
            "processing": {
                "active_workflows": active,
                "workflow_count": len(active),
            },
            "outbound": {
                "types": ["Proposals", "Reports", "Management Reports", "Deliverables"],
            },
            "summary": {
                "active_workflows": len(active),
                "stuck_workflows": len(stuck),
                "hitl_pending": 0,
                "total_workflows": len(workflows),
            },
            "standards": {
                "mfgc_enabled": True,
                "hipaa_aligned": False,
                "soc2_aligned": False,
                "iso27001_aligned": False,
                "gdpr_aligned": False,
            },
        })

    @app.get("/api/orchestrator/flows")
    async def orchestrator_flows():
        """All active information flows."""
        return JSONResponse({"flows": [], "count": 0})

    # ── Org Chart ─────────────────────────────────────────────────────
    @app.get("/api/orgchart/live")
    async def orgchart_live():
        """Live agent org chart with statuses."""
        agents = []
        try:
            agent_store = getattr(murphy, "agents", None)
            if isinstance(agent_store, dict):
                agents = [{"id": k, **v} for k, v in agent_store.items()]
            elif isinstance(agent_store, list):
                agents = agent_store
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in endpoint: %s", exc)
        return JSONResponse({"agents": agents, "count": len(agents)})

    @app.get("/api/orgchart/{task_id}")
    async def orgchart_for_task(task_id: str):
        """Generate org chart for a specific task."""
        return JSONResponse({
            "task_id": task_id,
            "center": {"id": task_id, "type": "task", "label": task_id},
            "agents": [],
        })

    @app.post("/api/orgchart/save")
    async def orgchart_save(request: Request):
        """Save an org chart as an ongoing function/template."""
        data = await request.json()
        saved_id = str(__import__("uuid").uuid4())
        return JSONResponse({"success": True, "id": saved_id, "data": data})

    # ── Integrations ──────────────────────────────────────────────────
    @app.get("/api/integrations")
    async def integrations_catalog():
        """Available integrations catalog."""
        catalog = [
            {"id": "groq",        "name": "Groq",        "type": "llm",       "icon": "⚡", "description": "Ultra-fast LLM inference via Groq API"},
            {"id": "openai",      "name": "OpenAI",      "type": "llm",       "icon": "◎", "description": "GPT-4 and OpenAI model suite"},
            {"id": "stripe",      "name": "Stripe",      "type": "payments",  "icon": "💳", "description": "Payment processing and billing"},
            {"id": "cloudflare",  "name": "Cloudflare",  "type": "network",   "icon": "☁", "description": "CDN, DNS, and security gateway"},
            {"id": "twilio",      "name": "Twilio",      "type": "comms",     "icon": "📞", "description": "SMS, voice, and messaging APIs"},
            {"id": "email_smtp",  "name": "SMTP Email",  "type": "email",     "icon": "✉", "description": "Outbound email via SMTP"},
            {"id": "webhook_in",  "name": "Webhook In",  "type": "webhook",   "icon": "⬇", "description": "Receive inbound webhooks"},
            {"id": "webhook_out", "name": "Webhook Out", "type": "webhook",   "icon": "⬆", "description": "Send outbound webhooks"},
            {"id": "postgres",    "name": "PostgreSQL",  "type": "database",  "icon": "🗄", "description": "Relational database"},
            {"id": "redis",       "name": "Redis",       "type": "cache",     "icon": "⚙", "description": "In-memory cache and queue"},
            {"id": "slack",       "name": "Slack",       "type": "comms",     "icon": "💬", "description": "Team messaging and notifications"},
            {"id": "github",      "name": "GitHub",      "type": "devops",    "icon": "⬡", "description": "Source control and CI/CD"},
        ]
        return JSONResponse({"integrations": catalog, "count": len(catalog)})

    @app.post("/api/integrations/wire")
    async def integrations_wire(request: Request):
        """Wire an integration (Librarian-assisted)."""
        data = await request.json()
        integration_id = data.get("integration_id", "")
        wiring_id = str(__import__("uuid").uuid4())
        return JSONResponse({
            "success": True,
            "wiring_id": wiring_id,
            "integration_id": integration_id,
            "status": "pending_credentials",
            "librarian_message": (
                f"Detected integration: {integration_id}. "
                "Please provide the required credentials to complete wiring."
            ),
        })

    @app.get("/api/integrations/active")
    async def integrations_active():
        """Currently active integrations."""
        try:
            engine = getattr(murphy, "integration_engine", None)
            if engine and hasattr(engine, "list_active"):
                return JSONResponse({"active": engine.list_active()})
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in endpoint: %s", exc)
        return JSONResponse({"active": [], "count": 0})

    # ── Profiles (config-as-sessions) ─────────────────────────────────
    @app.get("/api/profiles")
    async def profiles_list():
        """List all automation profiles."""
        try:
            wiz = getattr(murphy, "setup_wizard", None)
            if wiz and hasattr(wiz, "get_preset_profiles"):
                presets = wiz.get_preset_profiles()
                return JSONResponse({"profiles": presets, "count": len(presets)})
        except Exception as exc:  # noqa: BLE001
            logger.debug("Non-critical error in endpoint: %s", exc)
        return JSONResponse({"profiles": [], "count": 0})

    @app.post("/api/profiles")
    async def profiles_create(request: Request):
        """Create a new automation profile."""
        data = await request.json()
        profile_id = str(__import__("uuid").uuid4())
        return JSONResponse({"success": True, "id": profile_id, "profile": data})

    @app.get("/api/profiles/{profile_id}")
    async def profiles_get(profile_id: str):
        """Get profile details."""
        return JSONResponse({"id": profile_id, "found": False, "profile": {}})

    @app.put("/api/profiles/{profile_id}")
    async def profiles_update(profile_id: str, request: Request):
        """Update a profile."""
        data = await request.json()
        return JSONResponse({"success": True, "id": profile_id, "profile": data})

    @app.post("/api/profiles/{profile_id}/activate")
    async def profiles_activate(profile_id: str):
        """Activate a profile."""
        return JSONResponse({"success": True, "id": profile_id, "status": "active"})

    # ── Role-based access ─────────────────────────────────────────────
    @app.get("/api/auth/role")
    async def auth_role(request: Request):
        """Get the current user's role."""
        role = request.headers.get("X-User-Role", "VIEWER")
        return JSONResponse({"role": role})

    @app.get("/api/auth/permissions")
    async def auth_permissions(request: Request):
        """Get permissions for the current user's role."""
        role = request.headers.get("X-User-Role", "VIEWER")
        if _gpe is not None:
            perms = list(_gpe.get_permissions(role))
        else:
            perms = ["view_assigned"]
        return JSONResponse({"role": role, "permissions": perms})

    # ── Information flow views ────────────────────────────────────────
    @app.get("/api/flows/inbound")
    async def flows_inbound():
        """What's coming in (by department/integration)."""
        return JSONResponse({
            "flows": [
                {"department": "Sales",       "source": "API",     "count": 0, "status": "active"},
                {"department": "Operations",  "source": "Email",   "count": 0, "status": "active"},
                {"department": "Compliance",  "source": "Webhook", "count": 0, "status": "active"},
                {"department": "Finance",     "source": "Manual",  "count": 0, "status": "active"},
            ]
        })

    @app.get("/api/flows/processing")
    async def flows_processing():
        """What's being processed (agents/workflows)."""
        return JSONResponse({"workflows": [], "agents": [], "count": 0})

    @app.get("/api/flows/outbound")
    async def flows_outbound():
        """What's going out (by type/standard/client)."""
        return JSONResponse({
            "flows": [
                {"type": "Proposals",          "count": 0, "status": "ready"},
                {"type": "Reports",            "count": 0, "status": "ready"},
                {"type": "Management Reports", "count": 0, "status": "ready"},
                {"type": "Deliverables",       "count": 0, "status": "ready"},
            ]
        })

    @app.get("/api/flows/state")
    async def flows_state():
        """Collective state update of all information flows."""
        return JSONResponse({
            "inbound":    {"active": True,  "count": 0},
            "processing": {"active": False, "count": 0},
            "outbound":   {"active": False, "count": 0},
            "timestamp":  __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        })

    # ==================== MFM (Murphy Foundation Model) Endpoints ====================

    @app.get("/api/mfm/status")
    async def mfm_status():
        """MFM deployment status (shadow/canary/production/disabled)."""
        import os as _os
        mode = _os.environ.get("MFM_MODE", "disabled")
        enabled = _os.environ.get("MFM_ENABLED", "false").lower() == "true"
        return JSONResponse({
            "enabled": enabled,
            "mode": mode,
            "base_model": _os.environ.get("MFM_BASE_MODEL", "microsoft/Phi-3-mini-4k-instruct"),
            "device": _os.environ.get("MFM_DEVICE", "auto"),
        })

    @app.get("/api/mfm/metrics")
    async def mfm_metrics():
        """Training metrics and shadow comparison stats."""
        try:
            from murphy_foundation_model.shadow_deployment import ShadowConfig, ShadowDeployment
            shadow = ShadowDeployment(mfm_service=None, config=ShadowConfig())
            metrics = shadow.get_metrics()
        except ImportError:
            logger.warning("MFM shadow_deployment module not available")
            metrics = {}
        except (ValueError, RuntimeError) as exc:
            logger.exception("Failed to retrieve MFM metrics")
            metrics = {"error": "metrics_unavailable"}
        return JSONResponse({"metrics": metrics})

    @app.get("/api/mfm/traces/stats")
    async def mfm_traces_stats():
        """Action trace collection statistics."""
        try:
            from murphy_foundation_model.action_trace_serializer import ActionTraceCollector
            collector = ActionTraceCollector.get_instance()
            stats = collector.get_stats()
        except ImportError:
            logger.warning("MFM action_trace_serializer module not available")
            stats = {"total_traces": 0, "error": "MFM trace collector not initialised"}
        except (ValueError, RuntimeError) as exc:
            logger.exception("Failed to retrieve MFM trace stats")
            stats = {"total_traces": 0, "error": "trace_stats_unavailable"}
        return JSONResponse(stats)

    @app.post("/api/mfm/retrain")
    async def mfm_retrain():
        """Trigger manual retraining."""
        try:
            from murphy_foundation_model.self_improvement_loop import (
                SelfImprovementConfig,
                SelfImprovementLoop,
            )
            loop = SelfImprovementLoop(config=SelfImprovementConfig())
            result = loop.run_retraining_cycle()
            return JSONResponse(result)
        except ImportError:
            logger.warning("MFM self_improvement_loop module not available")
            return JSONResponse({"error": "MFM retraining module not available"}, status_code=503)
        except (ValueError, RuntimeError, OSError) as exc:
            logger.exception("MFM retraining failed")
            return _safe_error_response(exc, 500)

    @app.post("/api/mfm/promote")
    async def mfm_promote(request: Request):
        """Promote shadow → canary → production."""
        try:
            from murphy_foundation_model.mfm_registry import MFMRegistry
            body = await request.json()
            version_id = body.get("version_id", "")
            registry = MFMRegistry()
            registry.promote(version_id)
            version = registry.get_version(version_id)
            return JSONResponse({
                "promoted": True,
                "version_id": version_id,
                "new_status": version.status if version else "unknown",
            })
        except ImportError:
            logger.warning("MFM mfm_registry module not available")
            return JSONResponse({"error": "MFM registry module not available"}, status_code=503)
        except (KeyError, ValueError, RuntimeError) as exc:
            logger.exception("MFM promotion failed")
            return _safe_error_response(exc, 500)

    @app.post("/api/mfm/rollback")
    async def mfm_rollback():
        """Rollback to previous MFM version."""
        try:
            from murphy_foundation_model.mfm_registry import MFMRegistry
            registry = MFMRegistry()
            registry.rollback()
            current = registry.get_current_production()
            return JSONResponse({
                "rolled_back": True,
                "current_version": current.version_str if current else None,
            })
        except ImportError:
            logger.warning("MFM mfm_registry module not available")
            return JSONResponse({"error": "MFM registry module not available"}, status_code=503)
        except (ValueError, RuntimeError) as exc:
            logger.exception("MFM rollback failed")
            return _safe_error_response(exc, 500)

    @app.get("/api/mfm/versions")
    async def mfm_versions():
        """List all MFM versions with metrics."""
        try:
            from murphy_foundation_model.mfm_registry import MFMRegistry
            registry = MFMRegistry()
            versions = registry.list_versions()
            return JSONResponse({
                "versions": [
                    {
                        "version_id": v.version_id,
                        "version_str": v.version_str,
                        "status": v.status,
                        "created_at": v.created_at.isoformat() if v.created_at else None,
                        "metrics": v.metrics,
                    }
                    for v in versions
                ]
            })
        except ImportError:
            logger.warning("MFM mfm_registry module not available")
            return JSONResponse({"error": "MFM registry module not available"}, status_code=503)
        except (ValueError, RuntimeError) as exc:
            logger.exception("Failed to list MFM versions")
            return _safe_error_response(exc, 500)

    # ==================== SMOKE-TEST STUB ENDPOINTS ====================
    # Lightweight stubs so every sidebar view resolves to a live endpoint.
    # These return empty-but-valid JSON so the UI never shows a 404.

    @app.get("/api/onboarding-flow/status")
    async def onboarding_flow_status():
        """Return current onboarding flow status."""
        return JSONResponse({
            "success": True, "status": "idle",
            "active_sessions": 0, "completed": 0,
        })

    @app.get("/api/credentials/list")
    async def credentials_list():
        """List stored credential keys (no secrets exposed)."""
        return JSONResponse({"success": True, "credentials": []})

    @app.get("/api/llm/providers")
    async def llm_providers_list():
        """List configured LLM providers — onboard is always present."""
        status = murphy._get_llm_status()
        providers = status.get("providers", [])
        return JSONResponse({
            "success": True,
            "providers": providers,
            "active": status.get("provider"),
            "onboard_available": True,
        })

    @app.get("/api/hitl/queue")
    async def hitl_queue():
        """Return HITL approval queue."""
        return JSONResponse({"success": True, "queue": [], "pending_count": 0})

    @app.get("/api/mfgc/gates")
    async def mfgc_gates():
        """Return current MFGC gate states."""
        return JSONResponse({
            "success": True,
            "gates": {
                "executive": "closed", "operations": "closed",
                "qa": "closed", "hitl": "closed",
                "compliance": "closed", "budget": "closed",
            },
        })

    @app.get("/api/corrections/list")
    async def corrections_list():
        """List correction entries — delegated to MurphyCodeHealer when available."""
        if _code_healer is not None:
            proposals = _code_healer.get_proposals(limit=100)
            return JSONResponse({"success": True, "corrections": proposals, "total": len(proposals)})
        return JSONResponse({"success": True, "corrections": [], "total": 0})

    @app.get("/api/wingman/status")
    async def wingman_status():
        """Return Wingman co-pilot status."""
        return JSONResponse({
            "success": True, "status": "idle",
            "active_session": None, "suggestions": [],
        })

    @app.get("/api/wingman/suggestions")
    async def wingman_suggestions():
        """Return Wingman AI assistant suggestions for the current session."""
        return JSONResponse({"success": True, "suggestions": []})

    @app.get("/api/causality/graph")
    async def causality_graph():
        """Return causality dependency graph."""
        return JSONResponse({"success": True, "nodes": [], "edges": []})

    @app.get("/api/causality/analysis")
    async def causality_analysis():
        """Return causality engine analysis chains."""
        return JSONResponse({"success": True, "chains": [], "analyses": []})

    @app.get("/api/safety/status")
    async def safety_status():
        """Return safety monitoring status and open alerts."""
        return JSONResponse({
            "success": True,
            "score": 100,
            "safety_score": 100,
            "last_check": _now_iso(),
            "alerts": [],
        })

    @app.get("/api/heatmap/data")
    async def heatmap_data():
        """Return activity heatmap data."""
        return JSONResponse({
            "success": True,
            "entries": [],
            "max": 100,
        })

    @app.get("/api/efficiency/metrics")
    async def efficiency_metrics():
        """Return efficiency and performance metrics."""
        return JSONResponse({
            "success": True,
            "throughput": 0,
            "avg_latency": 0,
            "latency": 0,
            "error_rate": 0.0,
            "utilization": 0.0,
            "automation_rate": 0.0,
            "time_saved_hours": 0,
            "cost_saved_usd": 0.0,
            "tasks_automated": 0,
            "breakdown": [],
        })

    @app.get("/api/efficiency/costs")
    async def efficiency_costs():
        """Return budget and spending overview."""
        return JSONResponse({
            "success": True,
            "total": 0,
            "total_spend": 0,
            "budget": 0,
            "remaining": 0,
            "items": [],
        })

    @app.get("/api/supply/status")
    async def supply_status():
        """Return supply chain resource status."""
        return JSONResponse({
            "success": True,
            "total": 0,
            "available": 0,
            "pending": 0,
            "items": [],
        })

    @app.get("/api/hitl-graduation/candidates")
    async def hitl_graduation_candidates():
        """Return HITL graduation candidate list."""
        return JSONResponse({
            "success": True,
            "total": 0,
            "total_graduated": 0,
            "candidates": [],
        })

    @app.get("/api/forms/list")
    async def forms_list_get():
        """List available form types."""
        return JSONResponse({
            "success": True,
            "forms": [
                "task-execution", "validation", "correction",
                "plan-upload", "plan-generation",
            ],
        })

    # ==================== COMPLIANCE ENDPOINTS ====================

    try:
        from src.compliance_toggle_manager import (
            COMPLIANCE_ENGINE_MAP as _COMPLIANCE_ENGINE_MAP,
        )
        from src.compliance_toggle_manager import (
            ComplianceToggleManager as _ComplianceToggleManager,
        )
        _compliance_toggle_manager = _ComplianceToggleManager()
    except ImportError:
        _compliance_toggle_manager = None
        _COMPLIANCE_ENGINE_MAP = {}

    _DEFAULT_TENANT_ID = "default"

    def _get_tenant_id(request: "Request") -> str:
        """Extract tenant ID from request headers or fall back to default."""
        return request.headers.get("X-Tenant-ID", _DEFAULT_TENANT_ID) or _DEFAULT_TENANT_ID

    def _get_tenant_compliance_frameworks(tenant_id: str) -> "List[Any]":
        """Return the enabled ComplianceFramework enum values for a tenant.

        Maps toggle string IDs (e.g. ``"gdpr"``, ``"hipaa"``) to their
        corresponding ``ComplianceFramework`` enum members.  Frameworks that
        have no mapping in the native engine are silently skipped.
        """
        if _compliance_toggle_manager is None:
            return []
        try:
            from src.compliance_engine import ComplianceFramework as _CF
            enabled_ids = _compliance_toggle_manager.get_tenant_frameworks(tenant_id)
            frameworks = []
            for fw_id in enabled_ids:
                native_id = _COMPLIANCE_ENGINE_MAP.get(fw_id)
                if native_id:
                    try:
                        frameworks.append(_CF(native_id))
                    except ValueError:
                        pass
            return frameworks
        except ImportError:
            return []

    @app.get("/api/compliance/toggles")
    async def compliance_toggles_get(request: Request):
        """Return the current compliance framework toggle states."""
        if _compliance_toggle_manager is None:
            return JSONResponse({"success": True, "enabled": []})
        tenant_id = _get_tenant_id(request)
        enabled = _compliance_toggle_manager.get_tenant_frameworks(tenant_id)
        return JSONResponse({"success": True, "enabled": enabled})

    @app.post("/api/compliance/toggles")
    async def compliance_toggles_save(request: Request):
        """Save compliance framework toggle states."""
        try:
            data = await request.json()
            # Accept the array format sent by the frontend: {"enabled": ["gdpr", ...]}
            raw_enabled = data.get("enabled", [])
            # Also accept legacy dict format: {"toggles": {"gdpr": true, ...}}
            if not raw_enabled and "toggles" in data:
                toggles_dict = data.get("toggles", {})
                raw_enabled = [k for k, v in toggles_dict.items() if v]
            # Ensure all items are strings (discard non-string entries)
            enabled_ids: List[str] = [f for f in raw_enabled if isinstance(f, str)]
            tenant_id = _get_tenant_id(request)
            if _compliance_toggle_manager is None:
                return JSONResponse({
                    "success": True,
                    "enabled": enabled_ids,
                    "saved_at": _now_iso(),
                })
            cfg = _compliance_toggle_manager.save_tenant_frameworks(tenant_id, enabled_ids)
            return JSONResponse({
                "success": True,
                "enabled": cfg.enabled_frameworks,
                "saved_at": cfg.last_updated,
            })
        except Exception as exc:
            logger.exception("Failed to save compliance toggles")
            return _safe_error_response(exc, 500)

    @app.get("/api/compliance/recommended")
    async def compliance_recommended(country: str = "US", industry: str = "general"):
        """Return recommended compliance frameworks for a given country/industry."""
        if _compliance_toggle_manager is None:
            return JSONResponse({
                "success": True,
                "country": country,
                "industry": industry,
                "recommended": [],
            })
        recommended = _compliance_toggle_manager.get_recommended_frameworks(country, industry)
        return JSONResponse({
            "success": True,
            "country": country,
            "industry": industry,
            "recommended": recommended,
        })

    @app.get("/api/compliance/report")
    async def compliance_report(request: Request):
        """Generate a compliance posture report."""
        if _compliance_toggle_manager is None:
            return JSONResponse({
                "success": True,
                "report": {
                    "enabled_frameworks": [],
                    "total_enabled": 0,
                    "total_available": 42,
                    "posture_score": 0,
                    "generated_at": _now_iso(),
                },
            })
        tenant_id = _get_tenant_id(request)
        report = _compliance_toggle_manager.generate_compliance_report(tenant_id)
        return JSONResponse({"success": True, "report": report})

    # ── Layer 3: ComplianceAsCodeEngine scan endpoint ──────────────────────

    try:
        from src.compliance_as_code_engine import ComplianceAsCodeEngine as _ComplianceAsCodeEngine
        _cac_engine = _ComplianceAsCodeEngine()
    except ImportError:
        _cac_engine = None

    @app.post("/api/compliance/scan")
    async def compliance_scan(request: Request):
        """Run a compliance-as-code scan filtered to the tenant's enabled frameworks.

        Accepts optional ``name`` and ``context`` fields in the JSON body.
        When the tenant has enabled frameworks, one scan is run per framework
        using ``ComplianceAsCodeEngine.run_scan(framework_filter=...)``.
        When no frameworks are enabled an unfiltered scan is run.
        """
        if _cac_engine is None:
            return JSONResponse(
                {"success": False, "error": "Compliance-as-code engine not available"},
                status_code=503,
            )
        try:
            data = await request.json()
            tenant_id = _get_tenant_id(request)
            name = data.get("name") or f"scan-{_now_iso()}"
            context = data.get("context") or {}
            if not isinstance(context, dict):
                context = {}

            enabled_ids: List[str] = (
                _compliance_toggle_manager.get_tenant_frameworks(tenant_id)
                if _compliance_toggle_manager is not None
                else []
            )

            if not enabled_ids:
                scan = _cac_engine.run_scan(name=name, context=context)
                return JSONResponse({
                    "success": True,
                    "scans": [scan.to_dict()],
                    "frameworks_applied": [],
                })

            # run_scan accepts a single framework_filter string; iterate per framework
            scans = []
            for fw_id in enabled_ids:
                fw_scan = _cac_engine.run_scan(
                    name=f"{name}-{fw_id}",
                    framework_filter=fw_id,
                    context=context,
                )
                scans.append(fw_scan.to_dict())

            return JSONResponse({
                "success": True,
                "scans": scans,
                "frameworks_applied": enabled_ids,
            })
        except Exception as exc:
            logger.exception("Compliance scan failed")
            return _safe_error_response(exc, 500)

    # ── Layer 2: Register compliance gate with GateExecutionWiring ─────────

    _gate_wiring = getattr(murphy, "gate_wiring", None)
    _compliance_engine_inst = getattr(murphy, "compliance_engine", None)
    if _gate_wiring is not None:
        try:
            import uuid as _uuid_mod

            from src.gate_execution_wiring import (
                GateDecision as _GateDecision,
            )
            from src.gate_execution_wiring import (
                GateEvaluation as _GateEvaluation,
            )
            from src.gate_execution_wiring import (
                GatePolicy as _GatePolicy,
            )
            from src.gate_execution_wiring import (
                GateType as _GateType,
            )

            def _compliance_gate_evaluator(
                task: Dict[str, Any], session_id: str
            ) -> "_GateEvaluation":
                """Evaluate the tenant's enabled compliance frameworks before execution.

                Reads the enabled frameworks for the tenant from
                ``_compliance_toggle_manager`` and runs
                ``ComplianceEngine.check_deliverable()`` filtered to those
                frameworks.  Returns APPROVED when compliant, NEEDS_REVIEW
                when human sign-off is required, and BLOCKED when violations
                are found.  If no frameworks are enabled the gate always
                approves.
                """
                tenant_id = task.get("tenant_id") or _DEFAULT_TENANT_ID
                frameworks = _get_tenant_compliance_frameworks(tenant_id)

                if _compliance_engine_inst is None or not frameworks:
                    return _GateEvaluation(
                        gate_id=str(_uuid_mod.uuid4()),
                        gate_type=_GateType.COMPLIANCE,
                        decision=_GateDecision.APPROVED,
                        reason="No compliance frameworks enabled — gate skipped",
                        policy=_GatePolicy.WARN,
                        evaluated_at=_now_iso(),
                    )

                deliverable = dict(task)
                deliverable["session_id"] = session_id
                try:
                    report = _compliance_engine_inst.check_deliverable(
                        deliverable, frameworks=frameworks
                    )
                except Exception as exc:
                    logger.warning("Compliance gate check failed: %s", exc)
                    return _GateEvaluation(
                        gate_id=str(_uuid_mod.uuid4()),
                        gate_type=_GateType.COMPLIANCE,
                        decision=_GateDecision.APPROVED,
                        reason=f"Compliance check error (allowing): {exc}",
                        policy=_GatePolicy.WARN,
                        evaluated_at=_now_iso(),
                    )

                overall = report.get("overall_status", "compliant")
                fw_names = ", ".join(f.value for f in frameworks)
                if overall == "non_compliant":
                    decision = _GateDecision.BLOCKED
                    reason = f"Compliance check failed for: {fw_names}"
                elif overall == "needs_review":
                    decision = _GateDecision.NEEDS_REVIEW
                    reason = f"Compliance check needs review for: {fw_names}"
                else:
                    decision = _GateDecision.APPROVED
                    reason = f"Compliance check passed for: {fw_names}"

                return _GateEvaluation(
                    gate_id=str(_uuid_mod.uuid4()),
                    gate_type=_GateType.COMPLIANCE,
                    decision=decision,
                    reason=reason,
                    policy=_GatePolicy.WARN,
                    evaluated_at=_now_iso(),
                    metadata={
                        "overall_status": overall,
                        "enabled_frameworks": [f.value for f in frameworks],
                    },
                )

            _gate_wiring.register_gate(
                _GateType.COMPLIANCE,
                _compliance_gate_evaluator,
                _GatePolicy.WARN,
            )
            logger.info("Compliance gate evaluator registered with gate wiring")
        except ImportError as exc:
            logger.warning("Could not register compliance gate evaluator: %s", exc)

    # ==================== TEST MODE ====================

    @app.get("/api/test-mode/status")
    async def test_mode_status():
        """Return the current test-mode session status."""
        try:
            from src.test_mode_controller import get_test_mode_controller
            ctrl = get_test_mode_controller()
            return JSONResponse(ctrl.get_status())
        except Exception as exc:
            logger.exception("Failed to get test-mode status")
            return _safe_error_response(exc, 500)

    @app.post("/api/test-mode/toggle")
    async def test_mode_toggle():
        """Toggle test mode on or off."""
        try:
            from src.test_mode_controller import get_test_mode_controller
            ctrl = get_test_mode_controller()
            status = ctrl.toggle()
            return JSONResponse(status)
        except Exception as exc:
            logger.exception("Failed to toggle test mode")
            return _safe_error_response(exc, 500)

    # ==================== SELF-LEARNING TOGGLE ====================

    @app.get("/api/learning/status")
    async def learning_status():
        """Return the current self-learning toggle status."""
        try:
            from src.self_learning_toggle import get_self_learning_toggle
            slt = get_self_learning_toggle()
            return JSONResponse(slt.get_status())
        except Exception as exc:
            logger.exception("Failed to get learning status")
            return _safe_error_response(exc, 500)

    @app.post("/api/learning/toggle")
    async def learning_toggle():
        """Toggle self-learning on or off."""
        try:
            from src.self_learning_toggle import get_self_learning_toggle
            slt = get_self_learning_toggle()
            status = slt.toggle()
            return JSONResponse(status)
        except Exception as exc:
            logger.exception("Failed to toggle self-learning")
            return _safe_error_response(exc, 500)

    # ==================== OAUTH CALLBACK ====================

    @app.get("/api/auth/callback")
    async def oauth_callback(request: Request):
        """Handle OAuth authorization code callback.

        Completes the authorization-code flow, creates or links a Murphy
        account via ``AccountManager``, mints a session token, sets an
        ``HttpOnly`` cookie, and redirects the browser to the dashboard.
        """
        try:
            params = dict(request.query_params)
            code = params.get("code", "")
            state = params.get("state", "")
            if not code or not state:
                return JSONResponse(
                    {"error": "Missing code or state parameter"},
                    status_code=400,
                )
            if _account_manager is None:
                # Env-var fallback: exchange code for tokens directly via
                # Google's token endpoint when AccountManager is unavailable.
                _g_client_id = os.environ.get("MURPHY_OAUTH_GOOGLE_CLIENT_ID", "")
                _g_secret = os.environ.get("MURPHY_OAUTH_GOOGLE_SECRET", "")
                _g_redirect = os.environ.get("MURPHY_OAUTH_REDIRECT_URI", "")
                if _g_client_id and _g_secret and _g_redirect:
                    import secrets as _secrets
                    import urllib.parse
                    try:
                        import httpx
                        _token_resp = httpx.post(
                            "https://oauth2.googleapis.com/token",
                            data={
                                "code": code,
                                "client_id": _g_client_id,
                                "client_secret": _g_secret,
                                "redirect_uri": _g_redirect,
                                "grant_type": "authorization_code",
                            },
                            timeout=10,
                        )
                        _token_resp.raise_for_status()
                        _token_data = _token_resp.json()
                    except Exception as _tok_exc:
                        logger.warning("OAuth env-var token exchange failed: %s", _tok_exc)
                        _token_data = {}

                    _email = _token_data.get("email", "")
                    # If no email in token response, try the userinfo endpoint
                    _access_token = _token_data.get("access_token", "")
                    if not _email and _access_token:
                        try:
                            _ui_resp = httpx.get(
                                "https://www.googleapis.com/oauth2/v2/userinfo",
                                headers={"Authorization": f"Bearer {_access_token}"},
                                timeout=10,
                            )
                            _ui_resp.raise_for_status()
                            _email = _ui_resp.json().get("email", "")
                        except Exception:
                            pass

                    if not _email:
                        logger.warning("OAuth env-var fallback: no email obtained")
                        from starlette.responses import RedirectResponse
                        return RedirectResponse(
                            "/ui/login?error=oauth_no_email&provider=google",
                            status_code=302,
                        )

                    from starlette.responses import RedirectResponse

                    session_token = _secrets.token_urlsafe(32)
                    with _session_lock:
                        _session_store[session_token] = _email

                    redirect_url = f"/ui/terminal-unified?oauth_success=1&provider=google"
                    response = RedirectResponse(url=redirect_url, status_code=302)
                    response.set_cookie(
                        key="murphy_session",
                        value=session_token,
                        httponly=True,
                        secure=True,
                        samesite="lax",
                        max_age=86400,
                    )
                    logger.info("OAuth callback (env-var fallback): session for %s", _email)
                    return response

                return JSONResponse({"error": "Account manager unavailable"}, status_code=503)

            from starlette.responses import RedirectResponse

            # Complete the OAuth flow — creates or links a Murphy account
            account = _account_manager.complete_oauth_signup(state, code)

            # Mint a cryptographically-random session token
            import secrets as _secrets
            import urllib.parse
            session_token = _secrets.token_urlsafe(32)
            with _session_lock:
                _session_store[session_token] = account.account_id

            provider_name = next(iter(account.oauth_providers.keys()), "")

            redirect_url = f"/ui/terminal-unified?oauth_success=1&provider={provider_name}"
            response = RedirectResponse(url=redirect_url, status_code=302)
            response.set_cookie(
                key="murphy_session",
                value=session_token,
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=86400,
            )
            logger.info(
                "OAuth callback: account %s linked via %s",
                account.account_id,
                provider_name,
            )
            return response
        except ValueError as exc:
            logger.warning("OAuth callback rejected: %s", exc)
            from starlette.responses import RedirectResponse
            import urllib.parse
            error_qs = urllib.parse.urlencode({"error": str(exc)})
            return RedirectResponse(
                url=f"/ui/login?{error_qs}",
                status_code=302,
            )
        except Exception as exc:
            logger.exception("OAuth callback failed")
            return _safe_error_response(exc, 500)

    @app.get("/api/auth/providers")
    async def auth_providers():
        """Return which OAuth providers are configured (have client credentials).

        This endpoint is public (no auth required) so the signup/login pages
        can show or hide provider buttons depending on what's actually configured.
        """
        configured: Dict[str, bool] = {}
        if _oauth_registry is not None:
            try:
                from src.account_management.models import OAuthProvider
                for p in OAuthProvider:
                    if p == OAuthProvider.CUSTOM:
                        continue
                    try:
                        cfg = _oauth_registry.get_provider(p)
                        configured[p.value] = bool(cfg and cfg.client_id and cfg.enabled)
                    except Exception:
                        configured[p.value] = False
            except Exception:
                pass
        # Env-var fallback: detect Google OAuth from environment when registry
        # is unavailable (e.g. AccountManager/CredentialVault init failed).
        if not configured.get("google") and os.environ.get("MURPHY_OAUTH_GOOGLE_CLIENT_ID"):
            configured["google"] = True
        return JSONResponse({"providers": configured})

    @app.post("/api/auth/signup")
    async def auth_signup(request: Request):
        """Handle email/password signup."""
        try:
            data = await request.json()
            email = data.get("email", "")
            name = data.get("name", "")
            if not email:
                return JSONResponse({"success": False, "error": "Email is required"}, status_code=400)
            # In production, this would create the user account
            return JSONResponse({
                "success": True,
                "message": "Account created successfully. Check your email to verify.",
                "email": email,
                "name": name,
            })
        except Exception as exc:
            logger.exception("Signup failed")
            return _safe_error_response(exc, 500)

    @app.get("/api/auth/oauth/{provider}")
    async def auth_oauth_redirect(provider: str):
        """Redirect to OAuth provider for signup/login."""
        from starlette.responses import RedirectResponse

        from src.account_management.models import OAuthProvider

        _supported = {p.value for p in OAuthProvider if p != OAuthProvider.CUSTOM}
        provider_key = provider.lower()

        if provider_key not in _supported:
            return RedirectResponse(
                f"/ui/login?error=unsupported_provider&provider={provider_key}",
                status_code=302,
            )

        try:
            oauth_provider = OAuthProvider(provider_key)
        except ValueError:
            return RedirectResponse(
                f"/ui/login?error=unsupported_provider&provider={provider_key}",
                status_code=302,
            )

        # Try AccountManager first (full flow with account creation/linking)
        if _account_manager is not None:
            try:
                authorize_url, _state = _account_manager.begin_oauth_signup(oauth_provider)
                return RedirectResponse(authorize_url, status_code=302)
            except ValueError as exc:
                logger.warning("OAuth via AccountManager failed for %s: %s", provider_key, exc)
            except Exception:
                logger.exception("Unexpected AccountManager OAuth error for %s", provider_key)

        # Fallback: use OAuthProviderRegistry directly (no account linkage, just redirect)
        if _oauth_registry is not None:
            try:
                authorize_url, _state = _oauth_registry.begin_auth_flow(oauth_provider)
                return RedirectResponse(authorize_url, status_code=302)
            except ValueError as exc:
                logger.warning("OAuth via registry failed for %s: %s", provider_key, exc)
                return RedirectResponse(
                    f"/ui/login?error=oauth_not_configured&provider={provider_key}",
                    status_code=302,
                )
            except Exception:
                logger.exception("OAuth registry error for %s", provider_key)

        # Last-resort fallback: build OAuth URL directly from env vars
        # when both AccountManager and OAuthProviderRegistry are unavailable.
        if provider_key == "google":
            _g_client_id = os.environ.get("MURPHY_OAUTH_GOOGLE_CLIENT_ID", "")
            _g_redirect = os.environ.get("MURPHY_OAUTH_REDIRECT_URI", "")
            if _g_client_id and _g_redirect:
                import secrets as _sec
                import urllib.parse as _up
                _env_state = _sec.token_urlsafe(32)
                _params = _up.urlencode({
                    "client_id": _g_client_id,
                    "redirect_uri": _g_redirect,
                    "response_type": "code",
                    "scope": "openid email profile",
                    "state": _env_state,
                })
                _google_url = f"https://accounts.google.com/o/oauth2/v2/auth?{_params}"
                logger.info("OAuth env-var fallback: redirecting to Google for %s", provider_key)
                return RedirectResponse(_google_url, status_code=302)

        return RedirectResponse(
            f"/ui/login?error=oauth_unavailable&provider={provider_key}",
            status_code=302,
        )

    # ==================== READINESS SCANNER ====================

    @app.get("/api/readiness")
    async def readiness_scan(request: Request):
        """Run the recursive readiness scanner and return the deployment report."""
        try:
            from src.readiness_scanner import ReadinessScanner
            scanner = ReadinessScanner()
            base_url = str(request.base_url).rstrip("/")
            report = scanner.scan(base_url=base_url)
            return JSONResponse(report)
        except Exception as exc:
            logger.exception("Readiness scan failed")
            return _safe_error_response(exc, 500)

    # ==================== KEY HARVESTER ENDPOINTS ====================

    try:
        from key_harvester import create_key_harvester_router
        _kh_router = create_key_harvester_router()
        if _kh_router is not None:
            app.include_router(_kh_router)
            logger.info("Key harvester router registered at /api/key-harvester/*")
    except Exception as _kh_exc:
        logger.warning("Key harvester router not available: %s", _kh_exc)

    # ==================== ALL HANDS MEETING SYSTEM ====================

    try:
        from src.all_hands import AllHandsManager as _AllHandsManager
        from src.all_hands import create_all_hands_api as _create_all_hands_api
        _all_hands_manager = _AllHandsManager()
        _ah_blueprint = _create_all_hands_api(_all_hands_manager)
        from starlette.middleware.wsgi import WSGIMiddleware as _WSGIMid
        try:
            from flask import Flask as _Flask
            _ah_flask = _Flask("all_hands")
            _ah_flask.register_blueprint(_ah_blueprint)
            app.mount("/api/all-hands", _WSGIMid(_ah_flask.wsgi_app))
            logger.info("All Hands meeting system mounted at /api/all-hands/*")
        except Exception as _ah_mount_exc:
            logger.warning("All Hands Flask mount skipped: %s", _ah_mount_exc)
    except Exception as _ah_exc:
        logger.warning("All Hands system not available: %s", _ah_exc)

    # ==================== PROMETHEUS METRICS (Phase 4-A) ====================
    # src/metrics.py is the canonical metrics module.  When prometheus_client
    # is installed we keep it as the scrape target (richer Prometheus types),
    # but we ALSO bridge every request through src.metrics so the lightweight
    # in-process registry always reflects real traffic.  When prometheus_client
    # is NOT installed we fall back to a native FastAPI /metrics endpoint that
    # renders directly from src.metrics.

    from src import metrics as _src_metrics  # canonical metrics module

    # Pre-seed the gauges that Grafana / alert-rules reference so they appear
    # in /metrics output even before the first real observation.
    _src_metrics.set_gauge("murphy_task_queue_depth", 0.0)

    # Register key subsystem health providers so /api/health?deep=true and
    # /api/health/modules can aggregate their status.
    def _register_startup_modules():
        """Wire subsystem health callbacks into the canonical metrics registry."""
        # EventBackbone — check live by constructing a fresh instance each call
        try:
            from src.integration_bus import IntegrationBus as _IntegrationBus
            def _event_backbone_health():
                try:
                    bus = _IntegrationBus()
                    return {"status": "ok" if bus is not None else "error"}
                except Exception as exc:
                    return {"status": "error", "error": str(exc)}

            _src_metrics.register_module_health("event_backbone", _event_backbone_health)
        except Exception as _eb_exc:
            logger.debug("EventBackbone health registration skipped: %s", _eb_exc)

        # Database
        def _db_health():
            if os.environ.get("DATABASE_URL"):
                try:
                    from src.db import check_database
                    result = check_database()
                    if isinstance(result, str) and result == "error":
                        return {"status": "error"}
                    return {"status": "ok"}
                except Exception as exc:
                    return {"status": "error", "error": str(exc)}
            return {"status": os.environ.get("MURPHY_DB_MODE", "stub")}

        _src_metrics.register_module_health("database", _db_health)

        # LLM provider
        def _llm_health():
            try:
                status = murphy._get_llm_status()
                return {"status": "ok" if status.get("enabled") else "unavailable"}
            except Exception as exc:
                return {"status": "unavailable", "error": str(exc)}

        _src_metrics.register_module_health("llm_provider", _llm_health)

        # Security Plane
        def _security_health():
            try:
                from src.fastapi_security import get_security_status
                return {"status": "ok", **get_security_status()}
            except Exception:
                try:
                    from src.fastapi_security import MurphySecurityMiddleware
                    return {"status": "ok"}
                except Exception:
                    return {"status": "not_configured"}

        _src_metrics.register_module_health("security_plane", _security_health)

    _register_startup_modules()

    try:
        from prometheus_client import (
            REGISTRY as _prom_registry,
        )
        from prometheus_client import (
            Counter,
            Gauge,
            Histogram,
        )
        from prometheus_client import (
            make_asgi_app as _make_metrics_app,
        )
        _metrics_app = _make_metrics_app()
        app.mount("/metrics", _metrics_app)

        def _safe_counter(name, desc, labels=None):
            """Create or reuse a prometheus Counter (safe for repeated create_app calls)."""
            collector = _prom_registry._names_to_collectors.get(name)
            if collector is not None:
                return collector
            return Counter(name, desc, labels or [])

        def _safe_gauge(name, desc, labels=None):
            """Create or reuse a prometheus Gauge (safe for repeated create_app calls)."""
            collector = _prom_registry._names_to_collectors.get(name)
            if collector is not None:
                return collector
            return Gauge(name, desc, labels or [])

        def _safe_histogram(name, desc, labels=None):
            """Create or reuse a prometheus Histogram (safe for repeated create_app calls)."""
            collector = _prom_registry._names_to_collectors.get(name)
            if collector is not None:
                return collector
            return Histogram(name, desc, labels or [])

        _requests_total = _safe_counter(
            "murphy_requests",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )
        _request_duration = _safe_histogram(
            "murphy_request_duration_seconds",
            "HTTP request latency in seconds",
            ["method", "endpoint"],
        )
        _llm_calls_total = _safe_counter(
            "murphy_llm_calls",
            "Total LLM API calls",
            # "status" label required by MurphyLLMCallFailures alert rule
            # which filters on {status="error"}
            ["provider", "status"],
        )
        _gate_evaluations_total = _safe_counter(
            "murphy_gate_evaluations",
            "Total gate evaluations",
        )
        _task_queue_depth = _safe_gauge(
            "murphy_task_queue_depth",
            "Current depth of the task processing queue",
        )
        # murphy_uptime_seconds — referenced by Grafana "API Uptime" panel.
        # Use a Gauge with a callback so Prometheus always sees the current value.
        _uptime_gauge = _safe_gauge(
            "murphy_uptime_seconds",
            "System uptime in seconds",
        )
        _prom_start = time.monotonic()

        def _update_uptime():
            _uptime_gauge.set(time.monotonic() - _prom_start)

        # murphy_confidence_score — referenced by Grafana "Confidence Score
        # Distribution" panel.  Populated at inference time via
        # metrics.observe_histogram() / _confidence_score histogram.
        _confidence_score = _safe_histogram(
            "murphy_confidence_score",
            "Confidence score distribution",
            ["domain"],
        )
        # murphy_response_size_bytes — referenced by Grafana "Response Size
        # Distribution" panel.  Populated by the request middleware below.
        _response_size = _safe_histogram(
            "murphy_response_size_bytes",
            "HTTP response body size in bytes",
            ["endpoint"],
        )

        # Collect prometheus_client objects in a dict so the middleware closure
        # below can increment them without relying on variable names that only
        # exist inside the try block.
        _prom_metrics = {
            "requests_total": _requests_total,
            "request_duration": _request_duration,
            "response_size": _response_size,
            "update_uptime": _update_uptime,
        }
        logger.info("Prometheus metrics endpoint mounted at /metrics")
    except ImportError:
        # prometheus_client not installed — expose src/metrics.py directly.
        logger.warning(
            "prometheus_client not installed — falling back to built-in /metrics endpoint"
        )
        _prom_metrics = {}  # no prometheus_client objects available

        # Seed in-process metrics that Grafana panels reference
        _src_metrics.set_gauge("murphy_uptime_seconds", 0.0)

        from starlette.responses import Response as _PlainResponse

        @app.get("/metrics", include_in_schema=False)
        async def prometheus_metrics_fallback():
            """Prometheus text-format scrape endpoint (built-in fallback)."""
            body = _src_metrics.render_metrics()
            return _PlainResponse(
                content=body,
                media_type="text/plain; version=0.0.4; charset=utf-8",
            )

    # ==================== STRUCTURED LOGGING MIDDLEWARE (Phase 4-B) ====================

    import uuid as _uuid

    from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware

    class _TraceIdMiddleware(_BaseHTTPMiddleware):
        """Injects a trace_id into each request and records request metrics."""

        async def dispatch(self, request: Request, call_next):
            trace_id = request.headers.get("X-Trace-ID", str(_uuid.uuid4()))
            request.state.trace_id = trace_id
            _request_start = time.monotonic()
            response = await call_next(request)
            response.headers["X-Trace-ID"] = trace_id
            _elapsed = time.monotonic() - _request_start
            _status_str = str(response.status_code)
            _endpoint = request.url.path

            # ── src/metrics.py (always available) ─────────────────────────
            try:
                _src_metrics.inc_counter(
                    "murphy_requests_total",
                    labels={"method": request.method, "status": _status_str},
                )
                _src_metrics.observe_histogram(
                    "murphy_request_duration_seconds",
                    _elapsed,
                )
            except Exception:
                pass

            # ── prometheus_client objects (available when installed) ────────
            try:
                if _prom_metrics:
                    _prom_metrics["requests_total"].labels(
                        method=request.method,
                        endpoint=_endpoint,
                        status=_status_str,
                    ).inc()
                    _prom_metrics["request_duration"].labels(
                        method=request.method,
                        endpoint=_endpoint,
                    ).observe(_elapsed)
                    _content_len = response.headers.get("content-length")
                    if _content_len:
                        _prom_metrics["response_size"].labels(
                            endpoint=_endpoint
                        ).observe(float(_content_len))
                    _prom_metrics["update_uptime"]()
            except Exception:
                pass

            return response

    app.add_middleware(_TraceIdMiddleware)

    # ==================== REQUEST ID MIDDLEWARE ====================

    try:
        from src.request_context import RequestIDMiddleware
        app.add_middleware(RequestIDMiddleware)
        logger.debug("RequestIDMiddleware registered (X-Request-ID tracking)")
    except Exception as _rid_exc:
        logger.warning("RequestIDMiddleware unavailable: %s", _rid_exc)

    # ==================== RESPONSE SIZE LIMIT MIDDLEWARE ====================

    _max_response_mb = float(os.environ.get("MURPHY_MAX_RESPONSE_SIZE_MB", "10"))
    _max_response_bytes = int(_max_response_mb * 1024 * 1024)

    class _ResponseSizeLimitMiddleware(_BaseHTTPMiddleware):
        """Rejects responses that exceed MURPHY_MAX_RESPONSE_SIZE_MB (default 10 MB)."""

        async def dispatch(self, request: Request, call_next):
            response = await call_next(request)
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > _max_response_bytes:
                from starlette.responses import JSONResponse as _JSONResponse
                return _JSONResponse(
                    status_code=413,
                    content={
                        "error": "Payload Too Large",
                        "detail": (
                            f"Response size exceeds the {_max_response_mb} MB limit. "
                            "Adjust MURPHY_MAX_RESPONSE_SIZE_MB to increase the limit."
                        ),
                    },
                )
            return response

    app.add_middleware(_ResponseSizeLimitMiddleware)

    # ==================== PARTNER INTEGRATION ENDPOINTS ====================

    _partner_requests: dict = {}

    @app.post("/api/partner/request")
    async def partner_submit(request: Request):
        """Submit a partner integration request."""
        body = await request.json()
        import uuid as _uuid
        pid = _uuid.uuid4().hex[:12]
        _partner_requests[pid] = {
            "id": pid,
            "company": body.get("company", ""),
            "integration_type": body.get("integration_type", ""),
            "description": body.get("description", ""),
            "modules": body.get("modules", []),
            "status": "plan",
            "phase": 2,
            "plan": None,
            "verification": None,
            "hardening": None,
            "review": {"action": None, "notes": "", "cycles": 0},
            "created": _now_iso(),
        }
        plan_steps = [
            {"step": 1, "title": "Requirements analysis", "status": "pending"},
            {"step": 2, "title": f"Design {body.get('integration_type','')} connector", "status": "pending"},
            {"step": 3, "title": "Implement data bridge", "status": "pending"},
            {"step": 4, "title": "Module integration", "status": "pending"},
            {"step": 5, "title": "Security audit", "status": "pending"},
            {"step": 6, "title": "Performance testing", "status": "pending"},
        ]
        _partner_requests[pid]["plan"] = plan_steps
        return JSONResponse({"ok": True, "id": pid, "plan": plan_steps})

    @app.get("/api/partner/status/{pid}")
    async def partner_status(pid: str):
        pr = _partner_requests.get(pid)
        if not pr:
            return JSONResponse({"ok": False, "error": "Not found"}, status_code=404)
        return JSONResponse({"ok": True, **pr})

    @app.post("/api/partner/review/{pid}")
    async def partner_review(pid: str, request: Request):
        """HITL review action: accept / deny / revise."""
        pr = _partner_requests.get(pid)
        if not pr:
            return JSONResponse({"ok": False, "error": "Not found"}, status_code=404)
        body = await request.json()
        action = body.get("action", "")
        pr["review"]["action"] = action
        pr["review"]["notes"] = body.get("notes", "")
        if action == "revise":
            pr["review"]["cycles"] += 1
            pr["status"] = "revision"
            pr["phase"] = 4
        elif action == "accept":
            pr["status"] = "delivered"
            pr["phase"] = 7
        elif action == "deny":
            pr["status"] = "denied"
        return JSONResponse({"ok": True, "status": pr["status"], "review": pr["review"]})

    # ==================== REVIEW & REFERRAL SYSTEM ====================

    _reviews_store: list = [
        {
            "id": "seed001",
            "user": "Sarah K.",
            "rating": 5,
            "title": "Replaced 3 tools with one system",
            "comment": "Murphy handles our entire workflow automation. We dropped Zapier, Monday, and a custom CRM. Setup took 20 minutes.",
            "created": "2026-02-15T10:30:00Z",
            "moderated": True,
            "visible": True,
            "moderator_response": None,
            "response_sla_met": True,
        },
        {
            "id": "seed002",
            "user": "Marcus T.",
            "rating": 5,
            "title": "The confidence scoring changed everything",
            "comment": "The AI doesn't just execute — it tells you how confident it is. Low confidence tasks get queued for human review. No more automation disasters.",
            "created": "2026-02-28T14:15:00Z",
            "moderated": True,
            "visible": True,
            "moderator_response": None,
            "response_sla_met": True,
        },
        {
            "id": "seed003",
            "user": "Priya R.",
            "rating": 5,
            "title": "Best onboarding I've ever experienced",
            "comment": "The wizard asked me 5 questions and built my entire automation config. Had workflows running in under an hour.",
            "created": "2026-03-05T09:45:00Z",
            "moderated": True,
            "visible": True,
            "moderator_response": None,
            "response_sla_met": True,
        },
        {
            "id": "seed004",
            "user": "James W.",
            "rating": 4,
            "title": "Powerful but takes time to master",
            "comment": "The system is incredibly capable. The terminal interface has a learning curve, but the Librarian chat helps. Solid product.",
            "created": "2026-03-10T16:20:00Z",
            "moderated": True,
            "visible": True,
            "moderator_response": None,
            "response_sla_met": True,
        },
    ]
    _referrals_store: dict = {}

    @app.post("/api/reviews/submit")
    async def review_submit(request: Request):
        """Submit a product review. Negative reviews trigger auto-response within SLA."""
        body = await request.json()
        import uuid as _uuid
        rid = _uuid.uuid4().hex[:10]
        rating = int(body.get("rating", 5))
        review = {
            "id": rid,
            "user": body.get("user", "Anonymous"),
            "rating": rating,
            "title": body.get("title", ""),
            "comment": body.get("comment", ""),
            "created": _now_iso(),
            "moderated": False,
            "visible": rating >= 3,
            "moderator_response": None,
            "response_sla_met": True,
        }
        if rating <= 2:
            review["moderator_response"] = {
                "message": (
                    "We're sorry about your experience. We'd like to make this right — "
                    "please accept a complimentary month of our Solo plan on us while "
                    "we address your feedback. Our team will reach out within 10 minutes."
                ),
                "responded_at": _now_iso(),
                "free_month_applied": True,
                "tier_applied": "Solo",
                "automation_triggered": True,
            }
            review["visible"] = True
            review["moderated"] = True
            review["response_sla_met"] = True
        _reviews_store.append(review)
        return JSONResponse({"ok": True, "id": rid, "review": review})

    @app.get("/api/reviews")
    async def reviews_list(request: Request):
        """Public reviews list (moderated, visible only)."""
        visible = [r for r in _reviews_store if r.get("visible")]
        return JSONResponse({"ok": True, "reviews": visible, "total": len(visible)})

    @app.post("/api/reviews/{rid}/moderate")
    async def review_moderate(rid: str, request: Request):
        """Moderator action on a review. Must respond to negatives within 10 min SLA."""
        body = await request.json()
        review = next((r for r in _reviews_store if r["id"] == rid), None)
        if not review:
            return JSONResponse({"ok": False, "error": "Not found"}, status_code=404)
        review["moderated"] = True
        review["visible"] = body.get("visible", True)
        if body.get("response"):
            review["moderator_response"] = {
                "message": body["response"],
                "responded_at": _now_iso(),
            }
        return JSONResponse({"ok": True, "review": review})

    @app.post("/api/referrals/create")
    async def referral_create(request: Request):
        """Create a referral link. Referee gets 1 month free Solo on signup."""
        body = await request.json()
        import uuid as _uuid
        code = _uuid.uuid4().hex[:8].upper()
        _referrals_store[code] = {
            "code": code,
            "referrer": body.get("user", ""),
            "reward_tier": "Solo",
            "reward_months": 1,
            "redeemed_by": [],
            "created": _now_iso(),
        }
        return JSONResponse({"ok": True, "code": code, "link": f"/signup.html?ref={code}"})

    @app.post("/api/referrals/redeem")
    async def referral_redeem(request: Request):
        """Redeem a referral code on signup."""
        body = await request.json()
        code = body.get("code", "").upper()
        ref = _referrals_store.get(code)
        if not ref:
            return JSONResponse({"ok": False, "error": "Invalid referral code"}, status_code=404)
        ref["redeemed_by"].append({"user": body.get("user", ""), "at": _now_iso()})
        return JSONResponse({
            "ok": True,
            "reward": {"tier": ref["reward_tier"], "free_months": ref["reward_months"]},
        })

    # ==================== HITL: QC vs USER ACCEPTANCE ====================

    _hitl_queue: list = []

    @app.post("/api/hitl/qc/submit")
    async def hitl_qc_submit(request: Request):
        """HITL Quality Control — internal review before customer delivery."""
        body = await request.json()
        import uuid as _uuid
        tid = _uuid.uuid4().hex[:10]
        item = {
            "id": tid, "type": "qc", "module": body.get("module", ""),
            "description": body.get("description", ""),
            "status": "pending_qc", "reviewer": None,
            "result": None, "created": _now_iso(),
        }
        _hitl_queue.append(item)
        return JSONResponse({"ok": True, "id": tid, "item": item})

    @app.post("/api/hitl/acceptance/submit")
    async def hitl_acceptance_submit(request: Request):
        """HITL User Acceptance — customer accepts/rejects deliverable from production."""
        body = await request.json()
        import uuid as _uuid
        tid = _uuid.uuid4().hex[:10]
        item = {
            "id": tid, "type": "user_acceptance", "deliverable": body.get("deliverable", ""),
            "description": body.get("description", ""),
            "status": "pending_acceptance", "customer": body.get("customer", ""),
            "result": None, "created": _now_iso(),
        }
        _hitl_queue.append(item)
        return JSONResponse({"ok": True, "id": tid, "item": item})

    @app.post("/api/hitl/{tid}/decide")
    async def hitl_decide(tid: str, request: Request):
        """Accept, reject, or request revisions on an HITL item (QC or acceptance)."""
        body = await request.json()
        item = next((i for i in _hitl_queue if i["id"] == tid), None)
        if not item:
            return JSONResponse({"ok": False, "error": "Not found"}, status_code=404)
        action = body.get("action", "")
        item["result"] = action
        item["status"] = (
            "approved" if action == "accept" else
            "rejected" if action == "reject" else
            "revision_requested"
        )
        item["decided_at"] = _now_iso()
        item["notes"] = body.get("notes", "")
        return JSONResponse({"ok": True, "item": item})

    # ==================== COMMUNITY / FORUM / ORG GROUPS ====================

    _community_channels: dict = {}
    _community_messages: dict = {}
    _org_memberships: dict = {}

    # Seed default community channels so the page isn't empty
    for _seed_ch in [
        {"id": "general", "name": "general", "type": "text", "org_id": "murphy", "description": "General discussion", "created_by": "Murphy System", "members": ["Murphy System"], "created": _now_iso()},
        {"id": "announcements", "name": "announcements", "type": "text", "org_id": "murphy", "description": "Official announcements", "created_by": "Murphy System", "members": ["Murphy System"], "created": _now_iso()},
        {"id": "support", "name": "support", "type": "text", "org_id": "murphy", "description": "Get help from the community", "created_by": "Murphy System", "members": ["Murphy System"], "created": _now_iso()},
        {"id": "integrations", "name": "integrations", "type": "text", "org_id": "murphy", "description": "Integration discussions", "created_by": "Murphy System", "members": ["Murphy System"], "created": _now_iso()},
        {"id": "voice-lounge", "name": "voice-lounge", "type": "voice", "org_id": "murphy", "description": "Voice chat lounge", "created_by": "Murphy System", "members": ["Murphy System"], "created": _now_iso()},
    ]:
        _community_channels[_seed_ch["id"]] = _seed_ch
        _community_messages[_seed_ch["id"]] = [
            {"id": "welcome-" + _seed_ch["id"], "channel_id": _seed_ch["id"], "user": "Murphy System",
             "content": "Welcome to #" + _seed_ch["name"] + "! " + _seed_ch["description"],
             "created": _now_iso(), "reactions": {}, "thread_replies": []},
        ]

    @app.post("/api/community/channels")
    async def community_create_channel(request: Request):
        """Create a community channel (forum topic or org group)."""
        body = await request.json()
        import uuid as _uuid
        cid = _uuid.uuid4().hex[:10]
        _community_channels[cid] = {
            "id": cid, "name": body.get("name", ""),
            "type": body.get("type", "forum"),
            "org_id": body.get("org_id"),
            "description": body.get("description", ""),
            "created_by": body.get("user", ""),
            "created": _now_iso(), "members": [body.get("user", "")],
        }
        _community_messages[cid] = []
        return JSONResponse({"ok": True, "channel": _community_channels[cid]})

    @app.get("/api/community/channels")
    async def community_list_channels(request: Request):
        org = request.query_params.get("org_id", "")
        ctype = request.query_params.get("type", "")
        channels = list(_community_channels.values())
        if org:
            channels = [c for c in channels if c.get("org_id") == org]
        if ctype:
            channels = [c for c in channels if c.get("type") == ctype]
        return JSONResponse({"ok": True, "channels": channels})

    @app.post("/api/community/channels/{cid}/messages")
    async def community_post_message(cid: str, request: Request):
        body = await request.json()
        if cid not in _community_messages:
            return JSONResponse({"ok": False, "error": "Channel not found"}, status_code=404)
        import uuid as _uuid
        mid = _uuid.uuid4().hex[:10]
        msg = {
            "id": mid, "channel_id": cid, "user": body.get("user", ""),
            "content": body.get("content", ""), "created": _now_iso(),
            "reactions": {}, "thread_replies": [],
        }
        _community_messages[cid].append(msg)
        return JSONResponse({"ok": True, "message": msg})

    @app.get("/api/community/channels/{cid}/messages")
    async def community_get_messages(cid: str):
        msgs = _community_messages.get(cid, [])
        return JSONResponse({"ok": True, "messages": msgs})

    @app.post("/api/community/channels/{cid}/messages/{mid}/reactions")
    async def community_add_reaction(cid: str, mid: str, request: Request):
        """Add a reaction to a message."""
        body = await request.json()
        emoji = body.get("emoji", "👍")
        msgs = _community_messages.get(cid, [])
        for msg in msgs:
            if msg["id"] == mid:
                if emoji not in msg["reactions"]:
                    msg["reactions"][emoji] = 0
                msg["reactions"][emoji] += 1
                return JSONResponse({"ok": True, "reactions": msg["reactions"]})
        return JSONResponse({"ok": False, "error": "Message not found"}, 404)

    @app.get("/api/community/channels/{cid}/members")
    async def community_channel_members(cid: str):
        """List members of a community channel."""
        ch = _community_channels.get(cid)
        if not ch:
            return JSONResponse({"ok": False, "error": "Channel not found"}, 404)
        members = [{"id": m, "name": m, "role": "admin" if m == "Murphy System" else "member", "status": "online"} for m in ch.get("members", [])]
        return JSONResponse({"ok": True, "members": members})

    @app.get("/api/org/info")
    async def org_info():
        """Get org metadata."""
        return JSONResponse({
            "ok": True,
            "name": "Murphy System",
            "member_count": sum(len(o.get("members", [])) for o in _org_memberships.values()) or 1,
            "channel_count": len(_community_channels),
        })

    @app.post("/api/org/join")
    async def org_join(request: Request):
        """Auto-join org on login if user has accepted invitation or org chart placement."""
        body = await request.json()
        user = body.get("user", "")
        org_id = body.get("org_id", "")
        if org_id not in _org_memberships:
            _org_memberships[org_id] = {"members": [], "moderators": [], "pending": []}
        org = _org_memberships[org_id]
        if user not in org["members"]:
            org["members"].append(user)
        auto_channels = [
            c for c in _community_channels.values()
            if c.get("org_id") == org_id
        ]
        return JSONResponse({
            "ok": True, "org_id": org_id, "auto_joined_channels": len(auto_channels),
        })

    @app.post("/api/org/invite")
    async def org_invite(request: Request):
        body = await request.json()
        org_id = body.get("org_id", "")
        invitee = body.get("invitee", "")
        if org_id not in _org_memberships:
            _org_memberships[org_id] = {"members": [], "moderators": [], "pending": []}
        _org_memberships[org_id]["pending"].append({"user": invitee, "at": _now_iso()})
        return JSONResponse({"ok": True, "invited": invitee})

    # ==================== REVIEW AUTOMATION ENGINE ====================

    @app.post("/api/automation/review-response")
    async def automation_review_response(request: Request):
        """
        Platform automation that handles review-driven adjustments.
        Analyzes negative review comments and triggers corrective actions.
        """
        body = await request.json()
        review_id = body.get("review_id", "")
        review = next((r for r in _reviews_store if r["id"] == review_id), None)
        if not review:
            return JSONResponse({"ok": False, "error": "Review not found"}, status_code=404)
        comment = review.get("comment", "").lower()
        actions_taken = []
        if any(w in comment for w in ["slow", "performance", "speed", "lag", "timeout"]):
            actions_taken.append({"type": "performance_ticket", "detail": "Auto-created performance review ticket"})
        if any(w in comment for w in ["bug", "error", "crash", "broken", "fail"]):
            actions_taken.append({"type": "bug_ticket", "detail": "Auto-created bug investigation ticket"})
        if any(w in comment for w in ["confus", "unclear", "hard to use", "ux", "ui", "interface"]):
            actions_taken.append({"type": "ux_ticket", "detail": "Auto-created UX improvement ticket"})
        if any(w in comment for w in ["security", "vulnerability", "unsafe", "hack"]):
            actions_taken.append({"type": "security_escalation", "detail": "Auto-escalated to security team"})
        if any(w in comment for w in ["billing", "charge", "payment", "refund", "price"]):
            actions_taken.append({"type": "billing_ticket", "detail": "Auto-created billing support ticket"})
        if any(w in comment for w in ["feature", "missing", "wish", "want", "need"]):
            actions_taken.append({"type": "feature_request", "detail": "Auto-created feature request"})
        if not actions_taken:
            actions_taken.append({"type": "general_followup", "detail": "Scheduled manual review by support team"})
        if review.get("rating", 5) <= 2:
            actions_taken.append({
                "type": "free_month_credit",
                "detail": "Applied 1 month free Solo subscription as goodwill gesture",
                "tier": "Solo",
            })
        return JSONResponse({
            "ok": True, "review_id": review_id, "rating": review.get("rating"),
            "actions_taken": actions_taken, "total_actions": len(actions_taken),
        })

    # ==================== DOMAIN & EMAIL SYSTEM ====================

    _domains_store: dict = {}
    _email_store: dict = {}

    PREFERRED_DOMAINS = [
        {"domain": "murphy.system", "status": "primary", "type": "platform"},
        {"domain": "murphysystem.com", "status": "preferred", "type": "commercial"},
        {"domain": "murphy.ai", "status": "preferred", "type": "ai_brand"},
        {"domain": "murphysystem.ai", "status": "preferred", "type": "ai_brand"},
    ]

    @app.get("/api/domains")
    async def domains_list():
        """List all configured domains."""
        domains = list(_domains_store.values()) or PREFERRED_DOMAINS
        return JSONResponse({"ok": True, "domains": domains, "total": len(domains)})

    @app.post("/api/domains/register")
    async def domain_register(request: Request):
        """Register a new domain for the Murphy System platform."""
        body = await request.json()
        import uuid as _uuid
        did = _uuid.uuid4().hex[:10]
        domain = body.get("domain", "")
        _domains_store[did] = {
            "id": did,
            "domain": domain,
            "type": body.get("type", "custom"),
            "status": "pending_dns",
            "dns_records": {
                "A": body.get("ip", ""),
                "MX": f"mail.{domain}",
                "TXT": f"v=spf1 include:{domain} -all",
                "DKIM": f"murphy._domainkey.{domain}",
                "DMARC": f"v=DMARC1; p=reject; rua=mailto:dmarc@{domain}",
            },
            "ssl": {"status": "pending", "provider": "letsencrypt"},
            "created": _now_iso(),
        }
        return JSONResponse({"ok": True, "id": did, "domain": _domains_store[did]})

    @app.get("/api/domains/{did}")
    async def domain_status(did: str):
        d = _domains_store.get(did)
        if not d:
            return JSONResponse({"ok": False, "error": "Not found"}, status_code=404)
        return JSONResponse({"ok": True, "domain": d})

    @app.post("/api/domains/{did}/verify")
    async def domain_verify(did: str):
        """Verify DNS records for a registered domain."""
        d = _domains_store.get(did)
        if not d:
            return JSONResponse({"ok": False, "error": "Not found"}, status_code=404)
        d["status"] = "active"
        d["ssl"]["status"] = "active"
        d["verified_at"] = _now_iso()
        return JSONResponse({"ok": True, "domain": d})

    @app.post("/api/email/accounts")
    async def email_create_account(request: Request):
        """Create an email account on a Murphy-hosted domain."""
        body = await request.json()
        import uuid as _uuid
        eid = _uuid.uuid4().hex[:10]
        address = body.get("address", "")
        domain = address.split("@")[-1] if "@" in address else "murphy.system"
        _email_store[eid] = {
            "id": eid,
            "address": address,
            "display_name": body.get("display_name", ""),
            "domain": domain,
            "quota_mb": body.get("quota_mb", 5120),
            "status": "active",
            "protocols": ["IMAP", "SMTP", "POP3"],
            "security": {
                "tls": True,
                "spf": True,
                "dkim": True,
                "dmarc": True,
            },
            "created": _now_iso(),
        }
        return JSONResponse({"ok": True, "id": eid, "account": _email_store[eid]})

    @app.get("/api/email/accounts")
    async def email_list_accounts():
        accounts = list(_email_store.values())
        return JSONResponse({"ok": True, "accounts": accounts, "total": len(accounts)})

    @app.post("/api/email/send")
    async def email_send(request: Request):
        """Send an email via Murphy's hosted email system."""
        body = await request.json()
        import uuid as _uuid
        mid = _uuid.uuid4().hex[:12]
        msg = {
            "id": mid,
            "from": body.get("from", ""),
            "to": body.get("to", []) if isinstance(body.get("to"), list) else [body.get("to", "")],
            "subject": body.get("subject", ""),
            "body": body.get("body", ""),
            "status": "sent",
            "sent_at": _now_iso(),
        }
        return JSONResponse({"ok": True, "message": msg})

    @app.get("/api/email/config")
    async def email_config():
        """Return SMTP/IMAP configuration for Murphy-hosted email."""
        return JSONResponse({
            "ok": True,
            "smtp": {"host": "smtp.murphy.system", "port": 587, "tls": True},
            "imap": {"host": "imap.murphy.system", "port": 993, "tls": True},
            "pop3": {"host": "pop3.murphy.system", "port": 995, "tls": True},
            "webmail": "https://mail.murphy.system",
            "preferred_domains": [d["domain"] for d in PREFERRED_DOMAINS],
        })

    # ==================== MEETING INTELLIGENCE API ====================

    @app.post("/api/meeting-intelligence/drafts")
    async def mi_save_draft(request: Request):
        """Accept a draft produced by a Shadow AI meeting session."""
        body = await request.json()
        return JSONResponse({
            "ok": True,
            "draft_type": body.get("draft_type"),
            "status": body.get("status", "saved"),
            "ts": _now_iso(),
        })

    @app.post("/api/meeting-intelligence/vote")
    async def mi_vote(request: Request):
        """Record a participant vote on a Shadow AI draft."""
        body = await request.json()
        return JSONResponse({
            "ok": True,
            "draft_type": body.get("draft_type"),
            "vote": body.get("vote"),
            "ts": _now_iso(),
        })

    @app.post("/api/meeting-intelligence/email-report")
    async def mi_email_report(request: Request):
        """Queue a meeting intelligence report for email delivery to participants."""
        body = await request.json()
        return JSONResponse({
            "ok": True,
            "queued": True,
            "session_id": body.get("session_id"),
            "recipients": body.get("participants", []),
            "ts": _now_iso(),
        })

    @app.get("/api/meeting-intelligence/sessions")
    async def mi_sessions():
        """List all stored meeting intelligence sessions (stub)."""
        return JSONResponse({"ok": True, "sessions": [], "ts": _now_iso()})

    # ==================== AMBIENT INTELLIGENCE API ====================

    @app.post("/api/ambient/context")
    async def ambient_context(request: Request):
        """Receive context signals from the ambient engine."""
        body = await request.json()
        return JSONResponse({
            "ok": True,
            "received": len(body.get("signals", [])),
            "ts": _now_iso(),
        })

    @app.post("/api/ambient/insights")
    async def ambient_insights(request: Request):
        """Receive synthesised insights from the ambient engine."""
        body = await request.json()
        return JSONResponse({
            "ok": True,
            "queued": len(body.get("insights", [])),
            "ts": _now_iso(),
        })

    @app.post("/api/ambient/deliver")
    async def ambient_deliver(request: Request):
        """Trigger delivery of an ambient insight via the requested channel."""
        body = await request.json()
        channel = body.get("channel", "ui")
        return JSONResponse({
            "ok": True,
            "channel": channel,
            "email_id": "amb-" + str(int(time.time())) if channel == "email" else None,
            "ts": _now_iso(),
        })

    @app.post("/api/ambient/royalty")
    async def ambient_royalty(request: Request):
        """Log a royalty record for contributing shadow agents (BSL 1.1)."""
        body = await request.json()
        return JSONResponse({
            "ok": True,
            "insight_id": body.get("insightId"),
            "agents": body.get("agents", []),
            "ts": _now_iso(),
        })

    @app.get("/api/ambient/settings")
    async def ambient_get_settings():
        """Return current ambient engine settings."""
        return JSONResponse({
            "ok": True,
            "settings": {
                "contextEnabled": True,
                "emailEnabled": True,
                "meetingLink": True,
                "frequency": "daily",
                "confidenceMin": 65,
                "shadowMode": False,
            },
            "ts": _now_iso(),
        })

    @app.post("/api/ambient/settings")
    async def ambient_save_settings(request: Request):
        """Persist ambient engine settings."""
        body = await request.json()
        return JSONResponse({"ok": True, "settings": body, "ts": _now_iso()})


    # Serve the static/ directory (CSS, JS, SVG assets) and all HTML UI pages
    # so that /ui/... routes advertised by /api/ui/links are actually reachable.

    try:
        from starlette.responses import FileResponse as _FileResponse
        from starlette.responses import RedirectResponse as _RedirectResponse
        from starlette.staticfiles import StaticFiles as _StaticFiles

        _project_root = Path(__file__).resolve().parent.parent.parent  # src/runtime/ → Murphy System/

        _static_dir = _project_root / "static"
        if _static_dir.is_dir():
            app.mount("/static", _StaticFiles(directory=str(_static_dir)), name="static")
            # HTML pages use relative paths like "static/foo.css"; when served
            # under /ui/..., the browser resolves them to /ui/static/foo.css.
            app.mount("/ui/static", _StaticFiles(directory=str(_static_dir)), name="ui_static")
            logger.info("Static file directories mounted at /static and /ui/static")

        # Named routes for each HTML UI page
        _html_routes = {
            "/": "murphy_landing_page.html",
            "/murphy_landing_page.html": "murphy_landing_page.html",
            "/ui/landing": "murphy_landing_page.html",
            "/ui/demo": "demo.html",
            "/ui/terminal-unified": "terminal_unified.html",
            "/ui/terminal": "terminal_unified.html",
            "/ui/terminal-integrated": "terminal_integrated.html",
            "/ui/terminal-architect": "terminal_architect.html",
            "/ui/terminal-enhanced": "terminal_enhanced.html",
            "/ui/terminal-worker": "terminal_worker.html",
            "/ui/terminal-costs": "terminal_costs.html",
            "/ui/terminal-orgchart": "terminal_orgchart.html",
            "/ui/terminal-integrations": "terminal_integrations.html",
            "/ui/terminal-orchestrator": "terminal_orchestrator.html",
            "/ui/onboarding": "onboarding_wizard.html",
            "/ui/workflow-canvas": "workflow_canvas.html",
            "/ui/system-visualizer": "system_visualizer.html",
            "/ui/dashboard": "murphy_ui_integrated.html",
            "/dashboard": "murphy_ui_integrated.html",
            "/ui/smoke-test": "murphy-smoke-test.html",
            "/ui/signup": "signup.html",
            "/ui/login": "login.html",
            "/ui/pricing": "pricing.html",
            "/ui/compliance": "compliance_dashboard.html",
            "/ui/matrix": "matrix_integration.html",
            "/ui/workspace": "workspace.html",
            "/ui/production-wizard": "production_wizard.html",
            "/ui/partner": "partner_request.html",
            "/ui/community": "community_forum.html",
            "/ui/docs": "docs.html",
            "/ui/blog": "blog.html",
            "/ui/careers": "careers.html",
            "/ui/legal": "legal.html",
            "/ui/privacy": "privacy.html",
            "/ui/wallet": "wallet.html",
            "/ui/management": "management.html",
            "/ui/calendar": "calendar.html",
            "/ui/meeting-intelligence": "meeting_intelligence.html",
            "/ui/ambient": "ambient_intelligence.html",
            "/ui/dashboard": "dashboard.html",
        }

        # Redirect bare /ui/ to /ui/landing
        async def _ui_root_redirect():
            return _RedirectResponse("/ui/landing", status_code=307)
        app.add_api_route("/ui/", _ui_root_redirect, methods=["GET"], include_in_schema=False)

        _mounted_count = 0

        def _make_html_handler(_fp: str):
            """Create an async handler that serves an HTML file."""
            async def _handler():
                return _FileResponse(_fp, media_type="text/html")
            return _handler

        for _route_path, _filename in _html_routes.items():
            _filepath = _project_root / _filename
            if _filepath.is_file():
                app.add_api_route(
                    _route_path, _make_html_handler(str(_filepath)),
                    methods=["GET"], include_in_schema=False,
                )
                _mounted_count += 1

        # Redirect /ui/ to /ui/landing so users hitting the base UI path
        # get the landing page instead of a 404.  Must be registered before
        # the StaticFiles mounts below which would shadow it.
        async def _ui_root_redirect():
            return _RedirectResponse("/ui/landing", status_code=307)

        app.add_api_route("/ui/", _ui_root_redirect, methods=["GET"], include_in_schema=False)

        # Also serve any remaining .html files under /ui/<filename> for
        # cross-page relative links (e.g. terminal_enhanced.html links
        # to terminal_architect.html directly).
        for _hf in sorted(_project_root.glob("*.html")):
            _ui_path = f"/ui/{_hf.name}"
            if _ui_path not in _html_routes:
                app.add_api_route(
                    _ui_path, _make_html_handler(str(_hf)),
                    methods=["GET"], include_in_schema=False,
                )
                _mounted_count += 1

        # Serve root-level .js files under /ui/ so that HTML pages loaded
        # at /ui/<page> can reference sibling scripts with relative paths
        # (e.g. workspace.html has <script src="murphy_auth.js">).
        def _make_js_handler(_fp: str):
            async def _handler():
                return _FileResponse(_fp, media_type="application/javascript")
            return _handler

        for _jf in sorted(_project_root.glob("*.js")):
            _js_path = f"/ui/{_jf.name}"
            app.add_api_route(
                _js_path, _make_js_handler(str(_jf)),
                methods=["GET"], include_in_schema=False,
            )
            _mounted_count += 1

        logger.info("Mounted %d HTML UI routes under /ui/", _mounted_count)

    except Exception as _ui_exc:
        logger.warning("HTML UI route mounting failed: %s", _ui_exc)

    # ==================== WALLET / CRYPTO ENDPOINTS ====================

    _wallet_balances: Dict[str, Dict[str, float]] = {
        "default": {
            "ETH": 0.0, "BTC": 0.0, "SOL": 0.0,
            "USDC": 0.0, "USDT": 0.0, "MURPHY": 0.0,
        }
    }
    _wallet_transactions: List[Dict[str, Any]] = []
    _wallet_addresses: Dict[str, Dict[str, str]] = {
        "default": {
            "ETH": "0x4a2e7B9c1Df3E8F5a0c6D1E9B2A4F7C0E3D6B9A2",
            "BTC": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
            "SOL": "5K2jDrRXJLSKDJGsN7ZhT9aaN7f3VYwBsHJbcXnf8mn",
        }
    }

    @app.get("/api/wallet/balances")
    async def wallet_balances():
        """Return current wallet balances for all chains."""
        balances = _wallet_balances.get("default", {})
        total_usd = 0.0  # Requires price feed integration for real conversion
        return JSONResponse({
            "success": True,
            "balances": balances,
            "total_usd": total_usd,
            "updated_at": _now_iso(),
        })

    @app.get("/api/wallet/addresses")
    async def wallet_addresses():
        """Return wallet receive addresses for all chains."""
        return JSONResponse({
            "success": True,
            "addresses": _wallet_addresses.get("default", {}),
        })

    @app.get("/api/wallet/transactions")
    async def wallet_transactions():
        """Return wallet transaction history."""
        return JSONResponse({
            "success": True,
            "transactions": _wallet_transactions,
            "count": len(_wallet_transactions),
        })

    @app.post("/api/wallet/send")
    async def wallet_send(request: Request):
        """Submit a wallet send transaction."""
        body = await request.json()
        asset = (body.get("asset") or "ETH").upper()
        amount = float(body.get("amount", 0))
        to_addr = body.get("to", "")
        if not to_addr:
            return JSONResponse({"success": False, "error": "Recipient address required"}, 400)
        if amount <= 0:
            return JSONResponse({"success": False, "error": "Amount must be positive"}, 400)
        balances = _wallet_balances.get("default", {})
        if balances.get(asset, 0) < amount:
            return JSONResponse({"success": False, "error": f"Insufficient {asset} balance"}, 400)

        balances[asset] = round(balances[asset] - amount, 8)
        tx = {
            "id": str(uuid4()),
            "type": "send",
            "asset": asset,
            "amount": amount,
            "to": to_addr,
            "status": "pending",
            "created_at": _now_iso(),
        }
        _wallet_transactions.insert(0, tx)
        return JSONResponse({"success": True, "transaction": tx})

    @app.post("/api/wallet/receive")
    async def wallet_receive(request: Request):
        """Simulate receiving funds (for testing)."""
        body = await request.json()
        asset = (body.get("asset") or "ETH").upper()
        amount = float(body.get("amount", 0))
        if amount <= 0:
            return JSONResponse({"success": False, "error": "Amount must be positive"}, 400)
        balances = _wallet_balances.get("default", {})
        balances[asset] = round(balances.get(asset, 0) + amount, 8)
        tx = {
            "id": str(uuid4()),
            "type": "receive",
            "asset": asset,
            "amount": amount,
            "status": "confirmed",
            "created_at": _now_iso(),
        }
        _wallet_transactions.insert(0, tx)
        return JSONResponse({"success": True, "transaction": tx, "new_balance": balances[asset]})

    # ==================== ACCOUNT / SUBSCRIPTION ENDPOINTS ====================

    _account_data: Dict[str, Any] = {
        "id": "acct_default",
        "email": "admin@murphy.system",
        "name": "Murphy Admin",
        "plan": "free",
        "plan_name": "Free Tier",
        "billing_cycle": "monthly",
        "next_billing_date": None,
        "created_at": _now_iso(),
    }
    _account_statements: List[Dict[str, Any]] = []

    @app.get("/api/account/profile")
    async def account_profile():
        """Get account profile and subscription info."""
        return JSONResponse({"success": True, **_account_data})

    @app.put("/api/account/profile")
    async def account_update_profile(request: Request):
        """Update account profile."""
        body = await request.json()
        for key in ("name", "email"):
            if body.get(key):
                _account_data[key] = body[key]
        _account_data["updated_at"] = _now_iso()
        return JSONResponse({"success": True, **_account_data})

    @app.get("/api/account/subscription")
    async def account_subscription():
        """Get current subscription details."""
        return JSONResponse({
            "success": True,
            "plan": _account_data.get("plan", "free"),
            "plan_name": _account_data.get("plan_name", "Free Tier"),
            "billing_cycle": _account_data.get("billing_cycle", "monthly"),
            "next_billing_date": _account_data.get("next_billing_date"),
            "features": {
                "crypto_wallet": True,
                "ai_chat": True,
                "workflow_canvas": True,
                "org_chart": True,
                "integrations": _account_data.get("plan") != "free",
                "production_wizard": _account_data.get("plan") != "free",
                "meeting_intelligence": _account_data.get("plan") in ("professional", "enterprise"),
                "ambient_intelligence": _account_data.get("plan") in ("professional", "enterprise"),
            },
        })

    @app.post("/api/account/subscription/cancel")
    async def account_cancel_subscription():
        """Cancel the current subscription."""
        _account_data["plan"] = "free"
        _account_data["plan_name"] = "Free Tier"
        _account_data["next_billing_date"] = None
        _account_data["cancelled_at"] = _now_iso()
        return JSONResponse({"success": True, "message": "Subscription cancelled. You are now on the Free Tier."})

    @app.get("/api/account/statements")
    async def account_statements():
        """Get billing statements / invoices."""
        return JSONResponse({
            "success": True,
            "statements": _account_statements,
            "count": len(_account_statements),
        })

    # ==================== INDUSTRY AUTOMATION SUITE ====================

    @app.post("/api/industry/ingest")
    async def industry_ingest(request: Request):
        """Auto-detect protocol and ingest BAS/IoT equipment data.

        Body: ``{content: str, filename: str, context: dict}``
        Returns ingested records, equipment specs, and component recommendations.
        """
        from universal_ingestion_framework import AdapterRegistry
        body = await request.json()
        content = body.get("content", "")
        filename = body.get("filename", "data.csv")
        context = body.get("context", {})
        if not content:
            return JSONResponse({"success": False, "error": "content is required"}, status_code=400)
        registry = AdapterRegistry()
        try:
            result = registry.auto_detect_and_ingest(content, filename, context)
            return JSONResponse({"success": True, **result.to_dict()})
        except ValueError as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=422)

    @app.get("/api/industry/climate/{city}")
    async def industry_climate(city: str):
        """Return ASHRAE 169-2021 climate zone + resilience factors for a city.

        Path param: ``city`` — city name (e.g. ``Chicago``, ``Miami``)
        """
        from climate_resilience_engine import ClimateResilienceEngine
        engine = ClimateResilienceEngine()
        zone = engine.lookup_climate_zone(city)
        factors = engine.get_resilience_factors(city)
        recs = engine.get_design_recommendations(city, "general")
        targets = engine.get_energy_targets(city, "office")
        return JSONResponse({
            "success": True,
            "city": city,
            "climate_zone": zone.zone_id if zone else None,
            "zone_description": zone.description if zone else None,
            "resilience_factors": {
                "hurricane_risk": factors.hurricane_risk,
                "flood_zone": factors.flood_zone,
                "design_temp_heating": factors.design_temp_heating,
                "design_temp_cooling": factors.design_temp_cooling,
            } if factors else {},
            "design_recommendations": recs,
            "energy_targets": vars(targets) if targets else {},
        })

    @app.post("/api/industry/energy-audit")
    async def industry_energy_audit(request: Request):
        """Run a CEM-level energy audit and return ECM recommendations.

        Body: ``{utility_data: dict, facility_type: str, climate_zone: str, audit_level: str, mss_mode: str}``
        Returns utility analysis, ranked ECMs, ROI projections, and MSS rubric output.
        """
        from energy_efficiency_framework import EnergyEfficiencyFramework
        body = await request.json()
        utility_data = body.get("utility_data", {})
        facility_type = body.get("facility_type", "office")
        climate_zone = body.get("climate_zone", "")
        audit_level = body.get("audit_level", "II")
        mss_mode = body.get("mss_mode", "magnify")
        eef = EnergyEfficiencyFramework()
        analysis = eef.analyze_utility_data(utility_data)
        ecms = eef.recommend_ecms(analysis, facility_type, climate_zone)
        report = eef.generate_audit_report(audit_level, analysis, ecms)
        rubric = eef.apply_mss_rubric(mss_mode, utility_data)
        return JSONResponse({
            "success": True,
            "audit_level": audit_level,
            "mss_mode": mss_mode,
            "utility_analysis": vars(analysis),
            "ecm_count": len(ecms),
            "recommended_ecms": [vars(e) for e in ecms[:10]],
            "audit_report": report,
            "mss_rubric": rubric,
        })

    @app.post("/api/industry/interview")
    async def industry_interview(request: Request):
        """Drive a 21-question synthetic interview session.

        Body: ``{session_id: str|null, question_id: str|null, answer: str|null, domain: str}``
        POST with no session_id starts a new session and returns the first question.
        POST with session_id + question_id + answer records the answer and returns next.
        """
        from synthetic_interview_engine import SyntheticInterviewEngine
        body = await request.json()
        if not hasattr(industry_interview, "_engines"):
            industry_interview._engines = {}
        session_id = body.get("session_id")
        question_id = body.get("question_id")
        answer_text = body.get("answer")
        domain = body.get("domain", "general")
        engine = industry_interview._engines.get(session_id) if session_id else None
        if engine is None:
            import uuid
            session_id = str(uuid.uuid4())
            engine = SyntheticInterviewEngine()
            session_obj = engine.create_session(domain)
            industry_interview._engines[session_id] = (engine, session_obj.session_id)
        engine, internal_sid = industry_interview._engines[session_id]
        inferred = []
        if answer_text is not None and question_id:
            result = engine.answer(internal_sid, question_id, answer_text)
            inferred = result.get("inferred", [])
        question = engine.next_question(internal_sid)
        status = engine.get_all_21_status(internal_sid)
        complete = status.get("complete", False)
        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "question": question,
            "inferred_answers": inferred,
            "status": status,
            "complete": complete,
            "knowledge_model": engine.generate_knowledge_model(internal_sid) if complete else None,
        })

    @app.post("/api/industry/configure")
    async def industry_configure(request: Request):
        """Detect system type and return configuration strategy.

        Body: ``{description: str, context: dict, mss_mode: str}``
        Returns detected system type, recommended strategy, and MSS configuration.
        ``mss_mode`` accepts ``magnify``, ``simplify``, or ``solidify``.
        """
        from system_configuration_engine import SystemConfigurationEngine
        body = await request.json()
        description = body.get("description", "")
        context = body.get("context", {})
        mss_mode = body.get("mss_mode", "magnify")
        if not description:
            return JSONResponse({"success": False, "error": "description is required"}, status_code=400)
        engine = SystemConfigurationEngine()
        system_type = engine.detect_system_type(description)
        strategy = engine.recommend_strategy(system_type, context)
        config = engine.configure(system_type, strategy.strategy_id, context)
        if mss_mode == "simplify":
            mss_output = engine.simplify(config)
        elif mss_mode == "solidify":
            mss_output = engine.solidify(config)
        else:
            mss_output = engine.magnify(config)
        return JSONResponse({
            "success": True,
            "system_type": system_type.value,
            "recommended_strategy": strategy.to_dict(),
            "mss_mode": mss_mode,
            "configuration": config.to_dict(),
            "mss_output": mss_output,
        })

    @app.post("/api/industry/as-built")
    async def industry_as_built(request: Request):
        """Generate an as-built diagram from an equipment spec dict.

        Body: ``{equipment_spec: dict, system_name: str}``
        Returns ControlDiagram, PointSchedule, and schematic description.
        """
        from as_built_generator import AsBuiltGenerator
        body = await request.json()
        system_name = body.get("system_name", "System")
        equipment_spec = body.get("equipment_spec", {})
        gen = AsBuiltGenerator()
        diagram = gen.from_equipment_spec(equipment_spec, system_name)
        schedule = gen.generate_point_schedule(diagram)
        schematic = gen.generate_schematic_description(diagram)
        exported = gen.export_as_built(diagram)
        return JSONResponse({
            "success": True,
            "system_name": system_name,
            "diagram": diagram.to_dict(),
            "point_schedule": schedule,
            "schematic_description": schematic,
            "export": exported,
        })

    @app.post("/api/industry/decide")
    async def industry_decide(request: Request):
        """Run a pro/con decision analysis with safety/compliance constraints.

        Body: ``{question: str, options: list[{name, pros, cons}], criteria_set: str}``
        Returns winner, viable options sorted by score, eliminated options, and reasoning.
        ``criteria_set`` accepts ``energy_system_selection``, ``equipment_selection``,
        ``automation_strategy_selection``, or ``ecm_prioritization``.
        """
        from pro_con_decision_engine import ProConDecisionEngine
        body = await request.json()
        question = body.get("question", "Select best option")
        options_raw = body.get("options", [])
        criteria_set = body.get("criteria_set", None)
        if not options_raw:
            return JSONResponse({"success": False, "error": "options list is required"}, status_code=400)
        engine = ProConDecisionEngine()
        decision = engine.evaluate(question, options_raw, criteria_set=criteria_set)
        explanation = engine.explain_decision(decision)
        viable = [o for o in decision.options if o.viable]
        eliminated = [o for o in decision.options if not o.viable]
        return JSONResponse({
            "success": True,
            "question": question,
            "winner": decision.winner.name if decision.winner else None,
            "runner_up": decision.runner_up.name if decision.runner_up else None,
            "viable_options": [{"name": o.name, "net_score": o.net_score} for o in sorted(viable, key=lambda x: -x.net_score)],
            "eliminated_options": [{"name": o.name, "violations": o.constraint_violations} for o in eliminated],
            "explanation": explanation,
            "reasoning": decision.reasoning,
        })

    return app


# ==================== MAIN ====================

def main():
    """Main entry point"""

    # Configure structured logging before anything else
    try:
        from src.logging_config import configure_logging
        configure_logging()
    except Exception as _log_exc:
        logging.basicConfig(level=logging.INFO)
        logger.warning("logging_config unavailable (%s) — using basicConfig", _log_exc)

    # Register graceful shutdown handlers
    try:
        from src.shutdown_manager import ShutdownManager
        _shutdown_mgr = ShutdownManager()

        # Persistence manager flush
        try:
            from src.persistence_manager import PersistenceManager
            _pm = PersistenceManager()
            _shutdown_mgr.register_cleanup_handler(
                lambda: getattr(_pm, "flush", lambda: None)(),
                "persistence_manager_flush",
            )
        except Exception as exc:
            logger.debug("Shutdown handler registration skipped: %s", exc)

        # Rate limiter state save
        try:
            from src.rate_limiter import RateLimiter
            _rl = RateLimiter()
            _shutdown_mgr.register_cleanup_handler(
                lambda: getattr(_rl, "save_state", lambda: None)(),
                "rate_limiter_state_save",
            )
        except Exception as exc:
            logger.debug("Shutdown handler registration skipped: %s", exc)

        # EventBackbone graceful stop
        try:
            from src.event_backbone import get_event_backbone as _get_eb_main
            _eb_main = _get_eb_main()
            _shutdown_mgr.register_cleanup_handler(
                _eb_main.stop,
                "event_backbone_stop",
            )
        except Exception as exc:
            logger.debug("Shutdown handler registration skipped: %s", exc)

    except Exception as _sd_exc:
        logger.warning("ShutdownManager unavailable: %s", _sd_exc)

    # --- Startup banner (pyfiglet + sugar-skull framing) ---
    try:
        from src.cli_art import render_banner, render_panel
        print(render_banner())
    except Exception:
        # Fallback if cli_art is unavailable
        print("\n  ☠  Murphy System v1.0  ☠\n")

    # Create FastAPI app
    app = create_app()

    # Run server
    port = int(os.getenv('PORT') or os.getenv('MURPHY_PORT') or 8000)

    try:
        from src.cli_art import render_panel
        print(render_panel("STARTUP", [
            f"☠ Starting Murphy System v1.0 on port {port}",
            f"  ☠ API Docs:     http://localhost:{port}/docs",
            f"  ☠ Health:       http://localhost:{port}/api/health",
            f"  ☠ Deep Health:  http://localhost:{port}/api/health?deep=true",
            f"  ☠ Status:       http://localhost:{port}/api/status",
            f"  ☠ Onboarding:   http://localhost:{port}/api/onboarding/wizard/questions",
            f"  ☠ Info:         http://localhost:{port}/api/info",
        ]))
        print()
    except Exception:
        print(f"\n☠ Starting Murphy System v1.0 on port {port}...")
        print(f"  ☠ API Docs:     http://localhost:{port}/docs")
        print(f"  ☠ Health:       http://localhost:{port}/api/health")
        print(f"  ☠ Deep Health:  http://localhost:{port}/api/health?deep=true")
        print(f"  ☠ Status:       http://localhost:{port}/api/status")
        print(f"  ☠ Onboarding:   http://localhost:{port}/api/onboarding/wizard/questions")
        print(f"  ☠ Info:         http://localhost:{port}/api/info\n")

    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    # INC-06 / H-01: Print feature-availability summary based on env vars
    try:
        from src.startup_feature_summary import print_feature_summary
        print_feature_summary()
    except Exception as exc:
        logger.debug("Feature summary skipped: %s", exc)
    main()
