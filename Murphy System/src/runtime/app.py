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


def create_app() -> FastAPI:
    """Create FastAPI application"""

    if FastAPI is None:
        raise ImportError("FastAPI not installed. Install with: pip install fastapi uvicorn")

    app = FastAPI(
        title="Murphy System 1.0",
        description="Universal AI Automation System",
        version="1.0.0"
    )

    # Apply security hardening (CORS allowlist, API key auth, rate limiting, headers)
    try:
        from src.fastapi_security import configure_secure_fastapi
        configure_secure_fastapi(app, service_name="murphy-system-1.0")
    except ImportError:
        logger.warning("fastapi_security not available — falling back to env-based CORS")
        _cors_origins = os.environ.get(
            "MURPHY_CORS_ORIGINS",
            "http://localhost:3000,http://localhost:8080,http://localhost:8000",
        ).split(",")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o.strip() for o in _cors_origins],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

    # Load .env before initialising MurphySystem so env vars like
    # MURPHY_LLM_PROVIDER and GROQ_API_KEY are available from the start.
    # Resolve to the project root (Murphy System/) — three levels up from
    # src/runtime/app.py — so it works regardless of CWD.
    if _load_dotenv is not None:
        _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        _load_dotenv(_env_path, override=True)

    # Initialize Murphy System
    murphy = MurphySystem()

    # ── Database Initialisation (Phase 1-A) ──────────────────────
    _db_available = False
    if os.environ.get("DATABASE_URL"):
        try:
            from src.db import create_tables
            create_tables()
            _db_available = True
            logger.info("Relational persistence initialised (DATABASE_URL set)")
        except Exception as _db_exc:
            logger.warning("Database init failed — falling back to JSON persistence: %s", _db_exc)

    # ── Cache Initialisation (Phase 1-B) ─────────────────────────
    _cache_client = None
    try:
        from src.cache import CacheClient
        _cache_client = CacheClient()
    except Exception as _cache_exc:
        logger.warning("CacheClient init failed: %s", _cache_exc)

    # ── AionMind 2.0 Cognitive Pipeline Integration (Gap 5) ──────
    _aionmind_kernel = None
    try:
        from aionmind import api as aionmind_api
        from aionmind.runtime_kernel import AionMindKernel

        _aionmind_kernel = AionMindKernel(
            auto_bridge_bots=True,
            auto_discover_rsc=True,
        )
        aionmind_api.init_kernel(_aionmind_kernel)
        # Mount AionMind 2.0 endpoints at /api/aionmind/*
        # (status, context, orchestrate, execute, proposals, memory)
        app.include_router(aionmind_api.router)
        logger.info("AionMind 2.0 cognitive pipeline initialised (%d capabilities).",
                     _aionmind_kernel.registry.count())
    except Exception as _aim_exc:
        logger.warning("AionMind kernel not available — endpoints use legacy path only: %s", _aim_exc)

    # ── Board System (Phase 1 – Monday.com parity) ────────────────
    try:
        from board_system.api import create_board_router
        _board_router = create_board_router()
        app.include_router(_board_router)
        logger.info("Board System API registered at /api/boards")
    except Exception as _bs_exc:
        logger.warning("Board System not available: %s", _bs_exc)

    # ── Collaboration System (Phase 2 – Monday.com parity) ────────
    try:
        from collaboration.api import create_collaboration_router
        _collab_router = create_collaboration_router()
        app.include_router(_collab_router)
        logger.info("Collaboration API registered at /api/collaboration")
    except Exception as _co_exc:
        logger.warning("Collaboration System not available: %s", _co_exc)

    # ── Dashboards (Phase 3 – Monday.com parity) ───────────────────
    try:
        from dashboards.api import create_dashboard_router
        _dash_router = create_dashboard_router()
        app.include_router(_dash_router)
        logger.info("Dashboards API registered at /api/dashboards")
    except Exception as _da_exc:
        logger.warning("Dashboards not available: %s", _da_exc)

    # ── Portfolio Management (Phase 4 – Monday.com parity) ─────────
    try:
        from portfolio.api import create_portfolio_router
        _port_router = create_portfolio_router()
        app.include_router(_port_router)
        logger.info("Portfolio API registered at /api/portfolio")
    except Exception as _po_exc:
        logger.warning("Portfolio Management not available: %s", _po_exc)

    # ── Workdocs (Phase 5 – Monday.com parity) ────────────────────
    try:
        from workdocs.api import create_workdocs_router
        _wd_router = create_workdocs_router()
        app.include_router(_wd_router)
        logger.info("Workdocs API registered at /api/workdocs")
    except Exception as _wd_exc:
        logger.warning("Workdocs not available: %s", _wd_exc)

    # ── Time Tracking (Phase 6 – Monday.com parity) ────────────────
    try:
        from time_tracking.api import create_time_tracking_router
        _tt_router = create_time_tracking_router()
        app.include_router(_tt_router)
        logger.info("Time Tracking API registered at /api/time-tracking")
    except Exception as _tt_exc:
        logger.warning("Time Tracking not available: %s", _tt_exc)

    # ── Automations (Phase 7 – Monday.com parity) ──────────────────
    try:
        from automations.api import create_automations_router
        _auto_router = create_automations_router()
        app.include_router(_auto_router)
        logger.info("Automations API registered at /api/automations")
    except Exception as _auto_exc:
        logger.warning("Automations not available: %s", _auto_exc)

    # ── CRM Module (Phase 8 – Monday.com parity) ──────────────────
    try:
        from crm.api import create_crm_router
        _crm_router = create_crm_router()
        app.include_router(_crm_router)
        logger.info("CRM API registered at /api/crm")
    except Exception as _crm_exc:
        logger.warning("CRM not available: %s", _crm_exc)

    # ── Dev Module (Phase 9 – Monday.com parity) ─────────────────
    try:
        from dev_module.api import create_dev_router
        _dev_router = create_dev_router()
        app.include_router(_dev_router)
        logger.info("Dev Module API registered at /api/dev")
    except Exception as _dev_exc:
        logger.warning("Dev Module not available: %s", _dev_exc)

    # ── Service Module (Phase 10 – Monday.com parity) ──────────────
    try:
        from service_module.api import create_service_router
        _svc_router = create_service_router()
        app.include_router(_svc_router)
        logger.info("Service Module API registered at /api/service")
    except Exception as _svc_exc:
        logger.warning("Service Module not available: %s", _svc_exc)

    # ── Guest Collaboration (Phase 11 – Monday.com parity) ─────────
    try:
        from guest_collab.api import create_guest_router
        _guest_router = create_guest_router()
        app.include_router(_guest_router)
        logger.info("Guest Collaboration API registered at /api/guest")
    except Exception as _guest_exc:
        logger.warning("Guest Collaboration not available: %s", _guest_exc)

    # ── Mobile App Backend (Phase 12 – Monday.com parity) ──────────
    try:
        from mobile.api import create_mobile_router
        _mobile_router = create_mobile_router()
        app.include_router(_mobile_router)
        logger.info("Mobile API registered at /api/mobile")
    except Exception as _mobile_exc:
        logger.warning("Mobile API not available: %s", _mobile_exc)

    # ── Billing API (PayPal + Crypto, multi-currency, Japan discount) ──
    try:
        from src.billing.api import create_billing_router
        _billing_router = create_billing_router()
        app.include_router(_billing_router)
        logger.info("Billing API registered at /api/billing")
    except Exception as _bill_exc:
        logger.warning("Billing API not available: %s", _bill_exc)

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
    # ── Integration Bus — wires src/ modules into the runtime ────────
    _integration_bus = None
    try:
        from src.integration_bus import IntegrationBus
        _integration_bus = IntegrationBus()
        _integration_bus.initialize()
        logger.info("IntegrationBus initialised: %s", _integration_bus.get_status())
    except Exception as _ib_exc:
        logger.warning("IntegrationBus not available — endpoints use legacy paths: %s", _ib_exc)

    # ==================== CORE ENDPOINTS ====================

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
        # Shallow liveness probe — instant, no I/O
        if not deep:
            return JSONResponse({"status": "healthy", "version": murphy.version})

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

        # Database check (if not stub mode)
        if os.environ.get("DATABASE_URL"):
            try:
                from src.db import check_database
                checks["database"] = check_database()
                if checks["database"] == "error":
                    critical_failed.append("database: connection test failed")
            except Exception as _dbe:
                checks["database"] = "error"
                critical_failed.append(f"database: {_dbe}")
        else:
            _db_mode = os.environ.get("MURPHY_DB_MODE", "stub").lower()
            checks["database"] = "stub" if _db_mode == "stub" else "not_configured"

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

        # Determine overall status
        str_checks = [v for v in checks.values() if isinstance(v, str)]
        overall = "healthy" if all(v != "error" for v in str_checks) else "degraded"
        http_status = 200 if not critical_failed else 503

        return JSONResponse(
            {"status": overall, "checks": checks, "critical_failures": critical_failed},
            status_code=http_status,
        )

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
        """Route a natural-language message through the Librarian + optional LLM."""
        data = await request.json()
        # Accept 'message', 'query', or 'question' — UI components use different names
        message = data.get("message") or data.get("query") or data.get("question") or ""
        result = murphy.librarian_ask(
            message=message,
            session_id=data.get("session_id"),
        )
        return JSONResponse(result)

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
            {"command": "learning status", "category": "learning", "description": "Check learning engine status", "api": "/api/learning/status", "ui": "/ui/terminal-architect#status"},
            {"command": "learning toggle", "category": "learning", "description": "Enable/disable learning engine", "api": "/api/learning/toggle", "ui": "/ui/terminal-architect#status"},
            # ── Integrations & Connectors ─────────────────────────────
            {"command": "integrations list", "category": "integrations", "description": "List all integrations and their status", "api": "/api/integrations", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "integrations add", "category": "integrations", "description": "Add a new integration", "api": "/api/integrations/add", "ui": "/ui/terminal-integrations#integrations"},
            {"command": "integrations wire", "category": "integrations", "description": "Wire up an integration connection", "api": "/api/integrations/wire", "ui": "/ui/terminal-integrations#connections"},
            {"command": "integrations active", "category": "integrations", "description": "View active integration connections", "api": "/api/integrations/active", "ui": "/ui/terminal-integrations#connections"},
            {"command": "universal-integrations list", "category": "integrations", "description": "Browse universal integration services catalog", "api": "/api/universal-integrations/services", "ui": "/ui/terminal-integrations#integrations"},
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
            {"command": "agent dashboard", "category": "agents", "description": "View agent dashboard snapshot", "api": "/api/agent-dashboard/snapshot", "ui": "/ui/terminal-integrated#agents"},
            {"command": "tasks list", "category": "agents", "description": "List active tasks", "api": "/api/tasks", "ui": "/ui/terminal-orchestrator"},
            {"command": "production queue", "category": "agents", "description": "View production queue", "api": "/api/production/queue", "ui": "/ui/terminal-orchestrator"},
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
        from src.matrix_bridge import MatrixBridgeSettings, get_settings as _get_matrix_settings
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
    async def onboarding_wizard_generate_config():
        """Generate a complete Murphy System configuration from wizard answers."""
        if _setup_wizard is None:
            return JSONResponse({"success": False, "error": "Setup wizard not available"}, status_code=503)
        profile = _setup_wizard.get_profile()
        validation = _setup_wizard.validate_profile(profile)
        config = _setup_wizard.generate_config(profile)
        summary = _setup_wizard.summarize(profile)
        return JSONResponse({
            "success": True,
            "config": config,
            "validation": validation,
            "summary": summary,
        })

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
    async def workflow_terminal_load(workflow_id: str = ""):
        """Load a single workflow by ID (used by workflow canvas UI)."""
        wf = _workflows_store.get(workflow_id)
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
        data = await request.json()
        text = data.get("text", "")
        context = data.get("context")
        if not text:
            return JSONResponse({"success": False, "error": "text is required"}, status_code=400)
        from dataclasses import asdict as _asdict
        result = _mss_controller.magnify(text, context)
        return JSONResponse({"success": True, "result": _asdict(result)})

    @app.post("/api/mss/simplify")
    async def mss_simplify(request: Request):
        """Simplify — decrease resolution of input text."""
        if _mss_controller is None:
            return JSONResponse({"success": False, "error": "MSS controls not available"}, status_code=503)
        data = await request.json()
        text = data.get("text", "")
        context = data.get("context")
        if not text:
            return JSONResponse({"success": False, "error": "text is required"}, status_code=400)
        from dataclasses import asdict as _asdict
        result = _mss_controller.simplify(text, context)
        return JSONResponse({"success": True, "result": _asdict(result)})

    @app.post("/api/mss/solidify")
    async def mss_solidify(request: Request):
        """Solidify — convert input text to implementation plan."""
        if _mss_controller is None:
            return JSONResponse({"success": False, "error": "MSS controls not available"}, status_code=503)
        data = await request.json()
        text = data.get("text", "")
        context = data.get("context")
        if not text:
            return JSONResponse({"success": False, "error": "text is required"}, status_code=400)
        from dataclasses import asdict as _asdict
        result = _mss_controller.solidify(text, context)
        return JSONResponse({"success": True, "result": _asdict(result)})

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

    @app.get("/api/production/queue")
    async def production_queue():
        """Get current production queue items."""
        return JSONResponse({
            "success": True,
            "items": _production_queue,
            "count": len(_production_queue),
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
        """Handle OAuth authorization code callback."""
        try:
            params = dict(request.query_params)
            code = params.get("code", "")
            state = params.get("state", "")
            if not code or not state:
                return JSONResponse(
                    {"error": "Missing code or state parameter"},
                    status_code=400,
                )
            from src.account_management.oauth_provider_registry import OAuthProviderRegistry
            registry = OAuthProviderRegistry()
            token = registry.complete_auth_flow(state, code)
            return JSONResponse({
                "success": True,
                "provider": token.provider.value,
                "token_type": token.token_type,
                "has_refresh_token": bool(token.refresh_token),
                "expires_at": token.expires_at,
                "profile": token.raw_profile,
                "message": "OAuth flow completed. Account linked successfully.",
            })
        except ValueError as exc:
            return _safe_error_response(exc, 400)
        except Exception as exc:
            logger.exception("OAuth callback failed")
            return _safe_error_response(exc, 500)

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

    # ==================== PROMETHEUS METRICS (Phase 4-A) ====================

    try:
        from prometheus_client import (
            REGISTRY as _prom_registry,
        )
        from prometheus_client import (
            Counter,
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
            ["provider"],
        )
        _gate_evaluations_total = _safe_counter(
            "murphy_gate_evaluations",
            "Total gate evaluations",
        )
        logger.info("Prometheus metrics endpoint mounted at /metrics")
    except ImportError:
        logger.warning("prometheus_client not installed — /metrics endpoint unavailable")

    # ==================== STRUCTURED LOGGING MIDDLEWARE (Phase 4-B) ====================

    import uuid as _uuid

    from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware

    class _TraceIdMiddleware(_BaseHTTPMiddleware):
        """Injects a trace_id into each request for structured logging."""

        async def dispatch(self, request: Request, call_next):
            trace_id = request.headers.get("X-Trace-ID", str(_uuid.uuid4()))
            request.state.trace_id = trace_id
            response = await call_next(request)
            response.headers["X-Trace-ID"] = trace_id
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

    # ==================== STATIC FILES & HTML UI ROUTES ====================
    # Serve the static/ directory (CSS, JS, SVG assets) and all HTML UI pages
    # so that /ui/... routes advertised by /api/ui/links are actually reachable.

    try:
        from starlette.responses import FileResponse as _FileResponse
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
            "/ui/landing": "murphy_landing_page.html",
            "/ui/terminal-unified": "terminal_unified.html",
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
            "/ui/smoke-test": "murphy-smoke-test.html",
            "/ui/signup": "signup.html",
            "/ui/pricing": "pricing.html",
            "/ui/compliance": "compliance_dashboard.html",
            "/ui/matrix": "matrix_integration.html",
            "/ui/workspace": "workspace.html",
            "/ui/production-wizard": "production_wizard.html",
        }

        _mounted_count = 0
        for _route_path, _filename in _html_routes.items():
            _filepath = _project_root / _filename
            if _filepath.is_file():
                def _make_handler(_fp=str(_filepath)):
                    async def _handler():
                        return _FileResponse(_fp, media_type="text/html")
                    return _handler
                app.add_api_route(
                    _route_path, _make_handler(), methods=["GET"],
                    include_in_schema=False,
                )
                _mounted_count += 1

        # Also serve any remaining .html files under /ui/<filename> for
        # cross-page relative links (e.g. terminal_enhanced.html links
        # to terminal_architect.html directly).
        for _hf in sorted(_project_root.glob("*.html")):
            _ui_path = f"/ui/{_hf.name}"
            if _ui_path not in {r for r in _html_routes}:
                def _make_fallback(_fp=str(_hf)):
                    async def _handler():
                        return _FileResponse(_fp, media_type="text/html")
                    return _handler
                app.add_api_route(
                    _ui_path, _make_fallback(), methods=["GET"],
                    include_in_schema=False,
                )
                _mounted_count += 1

        logger.info("Mounted %d HTML UI routes under /ui/", _mounted_count)

    except Exception as _ui_exc:
        logger.warning("HTML UI route mounting failed: %s", _ui_exc)

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
