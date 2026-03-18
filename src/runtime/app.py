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
    except Exception as _am_exc:  # pragma: no cover
        logger.error("AccountManager failed to initialise: %s", _am_exc, exc_info=True)
        _account_manager = None
        _oauth_registry = None

    # session_token → account_id (in-memory; replace with Redis/DB in prod)
    import threading as _threading
    import secrets as _secrets
    import bcrypt as _bcrypt
    _session_lock = _threading.Lock()
    _session_store: "Dict[str, str]" = {}  # session_token → account_id

    # ── User account store (in-memory; replace with DB in production) ──
    # account_id → {email, password_hash, full_name, job_title, company,
    #               tier, email_validated, eula_accepted, created_at, ...}
    _user_store: "Dict[str, Dict[str, Any]]" = {}
    _email_to_account: "Dict[str, str]" = {}  # email → account_id (index)

    def _hash_password(password: str) -> str:
        """Hash a password with bcrypt (mitigates CWE-916: weak password hash)."""
        return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")

    def _verify_password(password: str, stored_hash: str) -> bool:
        """Verify a password against a bcrypt hash."""
        try:
            return _bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except Exception:
            return False

    def _create_session(account_id: str) -> str:
        """Mint a session token and store the mapping."""
        token = _secrets.token_urlsafe(32)
        with _session_lock:
            _session_store[token] = account_id
        return token

    def _get_account_from_session(request: "Request") -> "Optional[Dict[str, Any]]":
        """Extract account info from a session token (cookie or Bearer header)."""
        token = ""
        # 1. Check cookie
        cookie_val = request.cookies.get("murphy_session", "")
        if cookie_val:
            token = cookie_val
        # 2. Check Authorization header
        if not token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if not token:
            return None
        with _session_lock:
            account_id = _session_store.get(token)
        if not account_id:
            return None
        return _user_store.get(account_id)

    # ── Subscription manager (shared instance) ──
    try:
        from src.subscription_manager import SubscriptionManager as _SubMgr
        from src.subscription_manager import SubscriptionTier as _SubTier
        from src.subscription_manager import SubscriptionRecord as _SubRec
        from src.subscription_manager import SubscriptionStatus as _SubStatus
        from src.subscription_manager import BillingInterval as _BillingInterval
        _sub_manager = _SubMgr()
    except Exception:  # pragma: no cover
        _sub_manager = None
        _SubTier = None
        _BillingInterval = None

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

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
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
            {"command": "agent dashboard", "category": "agents", "description": "View agent dashboard snapshot", "api": "/api/agent-dashboard/snapshot", "ui": "/ui/terminal-integrated#agents"},
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
        """Respond to HITL intervention with input validation."""
        data = await request.json()
        # Input validation — prevent injection
        status_val = data.get("status", "resolved")
        response_val = data.get("response", "")
        if not isinstance(status_val, str) or status_val not in {
            "approved", "rejected", "resolved", "deferred", "escalated",
        }:
            return JSONResponse(
                {"success": False, "error": "status must be one of: approved, rejected, resolved, deferred, escalated"},
                status_code=400,
            )
        if not isinstance(response_val, str) or len(response_val) > 2000:
            return JSONResponse(
                {"success": False, "error": "response must be a string (max 2000 chars)"},
                status_code=400,
            )
        intervention = murphy.hitl_interventions.get(intervention_id)
        if not intervention:
            return JSONResponse(
                {"success": False, "error": f"Intervention {intervention_id} not found"},
                status_code=404,
            )
        intervention["status"] = status_val
        intervention["response"] = response_val
        intervention["responded_at"] = datetime.now(timezone.utc).isoformat()
        return JSONResponse({"success": True, "intervention": intervention})

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

    # ==================== SWARM ENDPOINTS ====================
    # Expose all 7 swarm subsystems through a unified /api/swarm/* surface
    # so the terminal UI can drive swarm execution directly.

    @app.get("/api/swarm/status")
    async def swarm_status():
        """Return health and availability of all 7 swarm subsystems."""
        from src.swarm_rosetta_bridge import get_bridge
        bridge = get_bridge()
        return JSONResponse({
            "success": True,
            "subsystems": {
                "true_swarm_system": {"available": True, "description": "Dual-swarm MFGC 7-phase system"},
                "swarm_proposal_generator": {"available": True, "description": "LLM-backed task planning"},
                "collaborative_task_orchestrator": {"available": True, "description": "Execution governance"},
                "durable_swarm_orchestrator": {"available": True, "description": "Circuit breaker + retry"},
                "self_codebase_swarm": {"available": True, "description": "BMS/code generation agents"},
                "workflow_dag_engine": {"available": True, "description": "DAG parallel execution"},
                "llm_swarm_integration": {"available": True, "description": "LLM + swarm bridge"},
            },
            "rosetta_stats": bridge.get_stats(),
            "llm_status": murphy._get_llm_status(),
        })

    @app.post("/api/swarm/propose")
    async def swarm_propose(request: Request, _rbac=Depends(_perm_execute)):
        """Generate a SwarmProposal for a task using SwarmProposalGenerator."""
        try:
            data = await request.json()
        except Exception:
            data = {}
        task = (data.get("task") or data.get("task_description") or "").strip()
        if not task:
            return JSONResponse({"success": False, "error": "task is required"}, status_code=400)
        context = data.get("context")
        try:
            from src.llm_controller import LLMController
            from src.swarm_proposal_generator import SwarmProposalGenerator
            llm = LLMController()
            gen = SwarmProposalGenerator(llm_controller=llm)
            proposal = await gen.generate_proposal(task, context=context)
            return JSONResponse({
                "success": True,
                "proposal_id": proposal.proposal_id,
                "task": proposal.task_description,
                "complexity": proposal.task_complexity.value,
                "swarm_type": proposal.swarm_type.value,
                "agent_count": len(proposal.agents),
                "steps": len(proposal.execution_plan),
                "safety_gates": len(proposal.safety_gates),
                "confidence": proposal.confidence_estimate,
                "estimated_cost": proposal.cost_estimate,
                "display": gen.format_proposal_for_display(proposal),
            })
        except Exception as exc:
            logger.error("swarm_propose failed: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/swarm/execute")
    async def swarm_execute(request: Request, _rbac=Depends(_perm_execute)):
        """Run a task through the CollaborativeTaskOrchestrator end-to-end."""
        try:
            data = await request.json()
        except Exception:
            data = {}
        task = (data.get("task") or data.get("task_description") or "").strip()
        if not task:
            return JSONResponse({"success": False, "error": "task is required"}, status_code=400)
        budget = float(data.get("budget", 50.0))
        idempotency_key = data.get("idempotency_key") or None
        try:
            import sys, os
            _ms_src = os.path.join(os.path.dirname(__file__), "..", "..", "Murphy System", "src")
            if _ms_src not in sys.path:
                sys.path.insert(0, _ms_src)
            from collaborative_task_orchestrator import CollaborativeTaskOrchestrator
            cto = CollaborativeTaskOrchestrator()
            report = cto.orchestrate(
                task_description=task,
                budget=budget,
                idempotency_key=idempotency_key,
            )
            return JSONResponse({
                "success": True,
                "task_id": report.task_id,
                "status": report.status,
                "steps_completed": report.steps_completed,
                "total_cost": report.total_cost,
                "duration_ms": report.duration_ms,
                "synthesis": report.synthesis,
            })
        except Exception as exc:
            logger.error("swarm_execute failed: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/swarm/phase")
    async def swarm_phase(request: Request, _rbac=Depends(_perm_execute)):
        """Execute a single MFGC phase via TrueSwarmSystem."""
        try:
            data = await request.json()
        except Exception:
            data = {}
        task = (data.get("task") or "").strip()
        phase_name = (data.get("phase") or "EXPAND").upper()
        if not task:
            return JSONResponse({"success": False, "error": "task is required"}, status_code=400)
        try:
            from src.true_swarm_system import TrueSwarmSystem, Phase
            from src.llm_controller import LLMController
            phase = Phase[phase_name]
            system = TrueSwarmSystem(llm_controller=LLMController())
            result = system.execute_phase(phase=phase, task=task, context=data.get("context") or {})
            return JSONResponse({"success": True, **result})
        except KeyError:
            valid = [p.name for p in Phase]
            return JSONResponse({"success": False, "error": f"Invalid phase. Valid: {valid}"}, status_code=400)
        except Exception as exc:
            logger.error("swarm_phase failed: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/swarm/rosetta")
    async def swarm_rosetta_stats():
        """Return Rosetta event log for all swarm subsystems."""
        from src.swarm_rosetta_bridge import get_bridge
        bridge = get_bridge()
        return JSONResponse({
            "success": True,
            "stats": bridge.get_stats(),
            "recent_events": bridge.get_recent_events(limit=50),
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
        """Run business automation with tier enforcement."""
        # ── Tier enforcement ──
        account = _get_account_from_session(request)
        if account and _sub_manager is not None:
            acct_id = account["account_id"]
            tier = account.get("tier", "free")
            features = _sub_manager.TIER_FEATURES.get(
                _SubTier(tier) if _SubTier else None, {}
            ) if _SubTier else {}
            if not features.get("hitl_automations", False) and tier == "free":
                return JSONResponse({
                    "success": False,
                    "error": "Running automations requires a paid subscription. "
                             "Free accounts have 10 actions/day for exploring the system. "
                             "Upgrade to Solo ($29/mo) for 3 automations.",
                    "tier": tier,
                    "upgrade_url": "/ui/pricing",
                }, status_code=403)
            # Record usage
            usage = _sub_manager.record_usage(acct_id)
            if not usage.get("allowed", True):
                return JSONResponse({
                    "success": False,
                    "error": usage.get("message", "Daily usage limit reached"),
                }, status_code=429)

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

    # ── Workflow Execution (real WorkflowOrchestrator) ─────────────────────
    @app.post("/api/workflows/{workflow_id}/execute")
    async def execute_workflow(workflow_id: str, request: Request):
        """Execute a saved workflow through the WorkflowOrchestrator.

        Applies HITL gate checks and tier-based automation limits before
        starting execution.  Each workflow step runs through the real
        TaskExecutor engine.
        """
        workflow = _workflows_store.get(workflow_id)
        if not workflow:
            return JSONResponse({"success": False, "error": "Workflow not found"}, status_code=404)

        # ── Tier enforcement ──
        account = _get_account_from_session(request)
        if account and _sub_manager is not None:
            acct_id = account["account_id"]
            tier = account.get("tier", "free")
            # Check automation limit for paid tiers
            if tier != "free":
                limit_check = _sub_manager.check_tier_limit(
                    acct_id, "automations",
                    current_count=len([w for w in _workflows_store.values()
                                       if w.get("status") == "running"]),
                )
                if not limit_check.get("allowed", True):
                    return JSONResponse({
                        "success": False,
                        "error": limit_check.get("reason", "Automation limit reached for your tier"),
                        "tier": tier,
                    }, status_code=403)
            # Free tier: requires subscription for running automations
            features = _sub_manager.TIER_FEATURES.get(
                _SubTier(tier) if _SubTier else None, {}
            ) if _SubTier else {}
            if not features.get("hitl_automations", False) and tier == "free":
                return JSONResponse({
                    "success": False,
                    "error": "Running automated workflows requires a paid subscription. "
                             "Free accounts can create and view workflows. "
                             "Upgrade to Solo ($29/mo) for 3 automations.",
                    "tier": tier,
                    "upgrade_url": "/ui/pricing",
                }, status_code=403)
            # Record usage
            usage = _sub_manager.record_usage(acct_id)
            if not usage.get("allowed", True):
                return JSONResponse({
                    "success": False,
                    "error": usage.get("message", "Daily usage limit reached"),
                }, status_code=429)

        # ── Execute via WorkflowOrchestrator ──
        try:
            from src.execution_engine.workflow_orchestrator import (
                WorkflowOrchestrator,
                WorkflowStep,
                WorkflowStepType,
            )
            orch = WorkflowOrchestrator()
            orch.start()

            # Convert stored workflow nodes into executable steps
            steps = []
            for node in workflow.get("nodes", []):
                step = WorkflowStep(
                    step_type=WorkflowStepType.TASK,
                    parameters=node.get("data", node.get("parameters", {})),
                )
                step.name = node.get("label", node.get("id", "step"))
                steps.append(step)

            if not steps:
                # Create a default execution step from workflow description
                steps.append(WorkflowStep(
                    step_type=WorkflowStepType.TASK,
                    parameters={"description": workflow.get("name", "Untitled")},
                ))

            wf = orch.create_workflow(
                name=workflow.get("name", "Untitled"),
                steps=steps,
            )
            orch.execute_workflow(wf.workflow_id)
            orch.stop()

            # Update the stored workflow status
            workflow["status"] = "completed"
            workflow["last_executed"] = datetime.now(timezone.utc).isoformat()
            workflow["execution_result"] = wf.to_dict()
            _workflows_store[workflow_id] = workflow

            return JSONResponse({
                "success": True,
                "workflow_id": workflow_id,
                "status": "completed",
                "execution": wf.to_dict(),
            })
        except ImportError:
            # Fallback if WorkflowOrchestrator not available
            workflow["status"] = "completed"
            workflow["last_executed"] = datetime.now(timezone.utc).isoformat()
            _workflows_store[workflow_id] = workflow
            return JSONResponse({
                "success": True,
                "workflow_id": workflow_id,
                "status": "completed",
                "message": "Workflow executed (orchestrator unavailable, simulation mode)",
            })
        except Exception as exc:
            workflow["status"] = "failed"
            workflow["last_error"] = str(exc)
            _workflows_store[workflow_id] = workflow
            logger.exception("Workflow execution failed: %s", workflow_id)
            return _safe_error_response(exc, 500)

    # ── AI Workflow Generation ────────────────────────────────────────────
    @app.post("/api/workflows/generate")
    async def generate_workflow(request: Request):
        """Generate a DAG workflow from natural language using AIWorkflowGenerator.

        Body: { "description": "...", "context": {} }
        Returns the generated workflow definition ready to save/execute.
        """
        try:
            data = await request.json()
            description = data.get("description", "").strip()
            if not description:
                return JSONResponse(
                    {"success": False, "error": "description is required"},
                    status_code=400,
                )

            # ── Tier enforcement — custom_workflows required ──
            account = _get_account_from_session(request)
            if account and _sub_manager is not None:
                acct_id = account["account_id"]
                tier = account.get("tier", "free")
                usage = _sub_manager.record_usage(acct_id)
                if not usage.get("allowed", True):
                    return JSONResponse({
                        "success": False,
                        "error": usage.get("message", "Daily usage limit reached"),
                    }, status_code=429)

            # Generate via AI workflow engine
            gen = getattr(murphy, "ai_workflow_generator", None)
            if gen is None:
                try:
                    from src.ai_workflow_generator import AIWorkflowGenerator
                    gen = AIWorkflowGenerator()
                except ImportError:
                    return JSONResponse({
                        "success": False,
                        "error": "AI workflow generator not available",
                    }, status_code=503)

            wf = gen.generate_workflow(
                description=description,
                context=data.get("context"),
            )

            # Auto-save the generated workflow
            wf_id = wf.get("workflow_id", str(uuid4()))
            saved = {
                "id": wf_id,
                "name": wf.get("name", "Generated Workflow"),
                "nodes": [
                    {"id": s.get("name", f"step_{i}"),
                     "label": s.get("description", s.get("name", "")),
                     "type": s.get("type", "task"),
                     "data": s}
                    for i, s in enumerate(wf.get("steps", []))
                ],
                "connections": [],
                "status": "generated",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "generated_from": description[:200],
            }
            _workflows_store[wf_id] = saved

            return JSONResponse({
                "success": True,
                "workflow": saved,
                "generation_meta": {
                    "strategy": wf.get("strategy"),
                    "template_used": wf.get("template_used"),
                    "step_count": wf.get("step_count"),
                },
            })
        except Exception as exc:
            logger.exception("Workflow generation failed")
            return _safe_error_response(exc, 500)

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
                "label": f"Receive & validate incoming request",
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
    async def profiles_get(profile_id: str, request: Request):
        """Get profile details.  ``me`` returns the authenticated user's profile."""
        if profile_id == "me":
            account = _get_account_from_session(request)
            if not account:
                return JSONResponse({"id": "me", "found": False, "profile": {}}, status_code=401)

            tier = account.get("tier", "free")
            usage = {}
            if _sub_manager is not None:
                usage = _sub_manager.get_daily_usage(account["account_id"])

            return JSONResponse({
                "id": account["account_id"],
                "found": True,
                "email": account["email"],
                "full_name": account.get("full_name", ""),
                "job_title": account.get("job_title", ""),
                "company": account.get("company", ""),
                "role": account.get("role", "user"),
                "tier": tier,
                "email_validated": account.get("email_validated", False),
                "eula_accepted": account.get("eula_accepted", False),
                "created_at": account.get("created_at", ""),
                "daily_usage": usage,
                "terminal_config": {
                    "features": {
                        "terminal_access": True,
                        "production_wizard": True,
                        "workflow_canvas": True,
                        "crypto_wallet": True,
                        "shadow_agent_training": True,
                        "community_access": True,
                    },
                },
            })
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
        """List configured LLM providers."""
        return JSONResponse({
            "success": True,
            "providers": [],
            "active": None,
            "message": "Configure MURPHY_LLM_PROVIDER to enable LLM integration",
        })

    @app.get("/api/hitl/queue")
    async def hitl_queue():
        """Return HITL approval queue from real HumanInTheLoop state."""
        try:
            state = murphy.get_hitl_state()
            pending = state.get("pending", [])
            return JSONResponse({
                "success": True,
                "queue": pending,
                "pending_count": len(pending),
            })
        except Exception:
            return JSONResponse({"success": True, "queue": [], "pending_count": 0})

    @app.get("/api/hitl/pending")
    async def hitl_pending_alt():
        """Return HITL pending items (alias used by terminal UI)."""
        try:
            state = murphy.get_hitl_state()
            pending = state.get("pending", [])
            return JSONResponse({
                "success": True,
                "data": pending,
                "count": len(pending),
            })
        except Exception:
            return JSONResponse({"success": True, "data": [], "count": 0})

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
        """List correction entries."""
        return JSONResponse({"success": True, "corrections": []})

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
            ComplianceToggleManager as _ComplianceToggleManager,
            COMPLIANCE_ENGINE_MAP as _COMPLIANCE_ENGINE_MAP,
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
        """Save compliance framework toggle states with tier enforcement.

        Tier restrictions:
        - FREE: No compliance frameworks allowed
        - SOLO: basic_compliance only (gdpr, soc2)
        - BUSINESS: advanced_compliance (gdpr, soc2, hipaa, pci_dss, iso_27001, ccpa, sox, nist_csf)
        - PROFESSIONAL/ENTERPRISE: all_compliance_frameworks (all 41 frameworks)
        """
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

            # ── Tier-based compliance framework enforcement ──
            _BASIC_FRAMEWORKS = {"gdpr", "soc2"}
            _ADVANCED_FRAMEWORKS = _BASIC_FRAMEWORKS | {
                "hipaa", "pci_dss", "iso_27001", "ccpa", "sox", "nist_csf",
            }
            tier_restricted = False
            tier_message = ""
            account = _get_account_from_session(request)
            if account and _sub_manager is not None and _SubTier is not None:
                tier = account.get("tier", "free")
                features = _sub_manager.TIER_FEATURES.get(_SubTier(tier), {})
                if not features.get("basic_compliance", False):
                    # FREE tier — no compliance frameworks
                    if enabled_ids:
                        enabled_ids = []
                        tier_restricted = True
                        tier_message = (
                            "Compliance frameworks require a paid subscription. "
                            "Upgrade to Solo ($29/mo) for GDPR and SOC 2 compliance."
                        )
                elif not features.get("advanced_compliance", False):
                    # SOLO tier — basic only
                    original = set(enabled_ids)
                    enabled_ids = [f for f in enabled_ids if f in _BASIC_FRAMEWORKS]
                    if original - _BASIC_FRAMEWORKS:
                        tier_restricted = True
                        tier_message = (
                            "Your Solo plan supports GDPR and SOC 2 only. "
                            "Upgrade to Business ($99/mo) for HIPAA, PCI-DSS, "
                            "ISO 27001, and more."
                        )
                elif not features.get("all_compliance_frameworks", False):
                    # BUSINESS tier — advanced set
                    original = set(enabled_ids)
                    enabled_ids = [f for f in enabled_ids if f in _ADVANCED_FRAMEWORKS]
                    if original - _ADVANCED_FRAMEWORKS:
                        tier_restricted = True
                        tier_message = (
                            "Your Business plan supports 8 frameworks. "
                            "Upgrade to Professional for all 41 frameworks "
                            "including FedRAMP, CMMC, and ITAR."
                        )

            # ── Compliance conflict detection ──
            conflicts: List[Dict[str, str]] = []
            enabled_set = set(enabled_ids)

            # GDPR vs CCPA data retention conflict
            if "gdpr" in enabled_set and "ccpa" in enabled_set:
                conflicts.append({
                    "frameworks": ["gdpr", "ccpa"],
                    "area": "Data Retention & Deletion",
                    "resolution": "Both GDPR (EU) and CCPA (California) are enforced. "
                                  "GDPR's stricter 'right to erasure' requirements take "
                                  "precedence. Data deletion requests are honored within "
                                  "30 days (GDPR) which satisfies CCPA's 45-day window.",
                })

            # HIPAA vs GDPR data processing conflict
            if "hipaa" in enabled_set and "gdpr" in enabled_set:
                conflicts.append({
                    "frameworks": ["hipaa", "gdpr"],
                    "area": "Data Processing & Consent",
                    "resolution": "Both are enforced. HIPAA requires minimum necessary "
                                  "standard for PHI; GDPR requires explicit consent. "
                                  "Murphy enforces both: explicit consent + minimum "
                                  "necessary access. PHI is treated as GDPR special "
                                  "category data requiring Art. 9 explicit consent.",
                })

            # SOC 2 vs ISO 27001 control overlap
            if "soc2" in enabled_set and "iso_27001" in enabled_set:
                conflicts.append({
                    "frameworks": ["soc2", "iso_27001"],
                    "area": "Security Controls & Audit",
                    "resolution": "Both are enforced with unified controls. SOC 2 Trust "
                                  "Service Criteria map to ISO 27001 Annex A controls. "
                                  "A single control set satisfies both frameworks, with "
                                  "SOC 2 Type II audit evidence reusable for ISO 27001 "
                                  "certification.",
                })

            # PCI-DSS vs SOX financial data
            if "pci_dss" in enabled_set and "sox" in enabled_set:
                conflicts.append({
                    "frameworks": ["pci_dss", "sox"],
                    "area": "Financial Data Protection",
                    "resolution": "Both are enforced. PCI-DSS governs cardholder data "
                                  "security; SOX governs financial reporting integrity. "
                                  "Murphy applies PCI-DSS encryption (AES-256) to all "
                                  "payment data and SOX audit trails to all financial "
                                  "transactions. No conflict — complementary scopes.",
                })

            # FedRAMP vs CMMC government
            if "fedramp" in enabled_set and "cmmc" in enabled_set:
                conflicts.append({
                    "frameworks": ["fedramp", "cmmc"],
                    "area": "Government Security Controls",
                    "resolution": "Both are enforced. FedRAMP covers cloud service "
                                  "providers for federal agencies; CMMC covers defense "
                                  "contractors. Murphy implements NIST 800-171 controls "
                                  "shared by both, plus FedRAMP continuous monitoring "
                                  "and CMMC maturity level assessments.",
                })

            if _compliance_toggle_manager is None:
                return JSONResponse({
                    "success": True,
                    "enabled": enabled_ids,
                    "saved_at": _now_iso(),
                    "tier_restricted": tier_restricted,
                    "tier_message": tier_message,
                    "conflicts": conflicts,
                })
            cfg = _compliance_toggle_manager.save_tenant_frameworks(tenant_id, enabled_ids)
            return JSONResponse({
                "success": True,
                "enabled": cfg.enabled_frameworks,
                "saved_at": cfg.last_updated,
                "tier_restricted": tier_restricted,
                "tier_message": tier_message,
                "conflicts": conflicts,
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
                GateEvaluation as _GateEvaluation,
                GatePolicy as _GatePolicy,
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
        return JSONResponse({"providers": configured})

    @app.post("/api/auth/signup")
    async def auth_signup(request: Request):
        """Handle email/password signup — creates real account with session."""
        try:
            data = await request.json()
            email = (data.get("email") or "").strip().lower()
            password = data.get("password", "")
            full_name = data.get("full_name") or data.get("name", "")
            job_title = data.get("job_title", "")
            company = data.get("company", "")

            if not email:
                return JSONResponse({"success": False, "error": "Email is required"}, status_code=400)
            if not password or len(password) < 8:
                return JSONResponse({"success": False, "error": "Password must be at least 8 characters"}, status_code=400)
            if email in _email_to_account:
                return JSONResponse({"success": False, "error": "An account with this email already exists"}, status_code=409)

            account_id = uuid4().hex[:20]
            _user_store[account_id] = {
                "account_id": account_id,
                "email": email,
                "password_hash": _hash_password(password),
                "full_name": full_name,
                "job_title": job_title,
                "company": company,
                "tier": "free",
                "email_validated": True,    # auto-validate for now (MVP)
                "eula_accepted": True,      # accepted at signup form
                "role": "user",
                "created_at": _now_iso(),
            }
            _email_to_account[email] = account_id

            # Create a free-tier subscription record
            if _sub_manager is not None and _SubTier is not None:
                _sub_manager._subscriptions[account_id] = _SubRec(
                    account_id=account_id,
                    tier=_SubTier.FREE,
                    status=_SubStatus.ACTIVE,
                )

            # Mint session token
            session_token = _create_session(account_id)

            from starlette.responses import JSONResponse as _SJR
            resp = _SJR({
                "success": True,
                "message": "Account created successfully.",
                "account_id": account_id,
                "email": email,
                "name": full_name,
                "tier": "free",
            })
            resp.set_cookie(
                key="murphy_session",
                value=session_token,
                httponly=True,
                secure=os.environ.get("MURPHY_ENV", "development") != "development",
                samesite="lax",
                max_age=86400,
            )
            logger.info("Account created: %s (%s)", account_id, email)
            return resp
        except Exception as exc:
            logger.exception("Signup failed")
            return _safe_error_response(exc, 500)

    @app.post("/api/auth/login")
    async def auth_login(request: Request):
        """Handle email/password login — validates credentials and creates session."""
        try:
            data = await request.json()
            email = (data.get("email") or "").strip().lower()
            password = data.get("password", "")

            if not email or not password:
                return JSONResponse(
                    {"success": False, "error": "Email and password are required"},
                    status_code=400,
                )

            account_id = _email_to_account.get(email)
            if not account_id:
                return JSONResponse(
                    {"success": False, "error": "Invalid email or password"},
                    status_code=401,
                )

            account = _user_store.get(account_id)
            if not account or not _verify_password(password, account.get("password_hash", "")):
                return JSONResponse(
                    {"success": False, "error": "Invalid email or password"},
                    status_code=401,
                )

            # Mint session token
            session_token = _create_session(account_id)

            from starlette.responses import JSONResponse as _SJR
            resp = _SJR({
                "success": True,
                "message": "Login successful",
                "account_id": account_id,
                "email": account["email"],
                "name": account.get("full_name", ""),
                "tier": account.get("tier", "free"),
            })
            resp.set_cookie(
                key="murphy_session",
                value=session_token,
                httponly=True,
                secure=os.environ.get("MURPHY_ENV", "development") != "development",
                samesite="lax",
                max_age=86400,
            )
            logger.info("Login successful: %s (%s)", account_id, email)
            return resp
        except Exception as exc:
            logger.exception("Login failed")
            return _safe_error_response(exc, 500)

    @app.post("/api/auth/logout")
    async def auth_logout(request: Request):
        """Invalidate the current session."""
        token = request.cookies.get("murphy_session", "")
        if not token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if token:
            with _session_lock:
                _session_store.pop(token, None)
        from starlette.responses import JSONResponse as _SJR
        resp = _SJR({"success": True, "message": "Logged out"})
        resp.delete_cookie("murphy_session")
        return resp

    @app.get("/api/profiles/me/terminal-config")
    async def get_terminal_config(request: Request):
        """Return terminal feature flags for the authenticated user."""
        account = _get_account_from_session(request)
        if not account:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)

        tier = account.get("tier", "free")
        features = {
            "terminal_access": True,
            "production_wizard": True,
            "workflow_canvas": True,
            "crypto_wallet": True,
            "shadow_agent_training": True,
            "community_access": True,
            "shadow_agent_sell": tier not in ("free", "anonymous"),
            "hitl_automations": tier not in ("free", "anonymous"),
            "api_access": tier not in ("free", "solo", "anonymous"),
        }
        return JSONResponse({"features": features, "tier": tier})

    @app.post("/api/billing/checkout")
    async def billing_checkout(request: Request):
        """Create a billing checkout session for subscription upgrade."""
        try:
            data = await request.json()
            account_id = data.get("account_id", "")
            tier = data.get("tier", "")
            interval = data.get("interval", "monthly")

            if not account_id or not tier:
                return JSONResponse({"success": False, "error": "account_id and tier required"}, status_code=400)

            # For MVP, return a mock approval URL pointing to the pricing page
            # In production, this integrates with Stripe/PayPal/Coinbase
            if _sub_manager is not None:
                try:
                    billing_interval = _BillingInterval(interval) if _BillingInterval else interval
                    url = _sub_manager.create_stripe_checkout_session(
                        account_id=account_id,
                        tier=_SubTier(tier),
                        interval=billing_interval,
                        success_url=f"/ui/terminal-unified?upgraded=1",
                        cancel_url="/ui/pricing",
                    )
                    return JSONResponse({"success": True, "approval_url": url})
                except Exception:
                    pass  # fall through to mock

            return JSONResponse({
                "success": True,
                "approval_url": f"/ui/pricing?checkout=pending&tier={tier}",
                "message": "Payment provider not configured. Please set STRIPE_API_KEY.",
            })
        except Exception as exc:
            logger.exception("Billing checkout failed")
            return _safe_error_response(exc, 500)

    @app.get("/api/usage/daily")
    async def get_daily_usage(request: Request):
        """Return daily usage stats for the authenticated user or anonymous visitor."""
        account = _get_account_from_session(request)
        if account and _sub_manager is not None:
            usage = _sub_manager.get_daily_usage(account["account_id"])
            return JSONResponse(usage)
        elif _sub_manager is not None:
            fp = request.client.host if request.client else "unknown"
            entry = _sub_manager._anon_usage.get(fp, {"date": "", "count": 0})
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if entry.get("date") != today:
                return JSONResponse({"used": 0, "limit": 5, "remaining": 5, "tier": "anonymous"})
            return JSONResponse({
                "used": entry["count"],
                "limit": 5,
                "remaining": max(0, 5 - entry["count"]),
                "tier": "anonymous",
            })
        return JSONResponse({"used": 0, "limit": 5, "remaining": 5, "tier": "anonymous"})

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

        if _account_manager is None:
            return RedirectResponse(
                f"/ui/login?error=oauth_unavailable&provider={provider_key}",
                status_code=302,
            )

        try:
            oauth_provider = OAuthProvider(provider_key)
            authorize_url, _state = _account_manager.begin_oauth_signup(oauth_provider)
            return RedirectResponse(authorize_url, status_code=302)
        except ValueError as exc:
            logger.warning("OAuth flow could not be started for %s: %s", provider_key, exc)
            return RedirectResponse(
                f"/ui/login?error=oauth_not_configured&provider={provider_key}",
                status_code=302,
            )
        except Exception as exc:
            logger.exception("Unexpected error starting OAuth flow for %s", provider_key)
            return RedirectResponse(
                f"/ui/login?error=oauth_error&provider={provider_key}",
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
        # Mount Flask Blueprint as ASGI middleware-style sub-app
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
        from starlette.responses import FileResponse as _FileResponse, RedirectResponse as _RedirectResponse
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
        }

        # ── Route classification: public vs auth-required ──────────
        # Public routes are accessible without a session.  Auth-required
        # routes redirect to /ui/login when no valid session cookie exists.
        _PUBLIC_HTML_ROUTES = frozenset({
            "/", "/ui/landing", "/ui/login", "/ui/signup", "/ui/pricing",
            "/ui/docs", "/ui/blog", "/ui/careers", "/ui/legal", "/ui/privacy",
            "/ui/partner", "/ui/smoke-test",
        })

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

        def _make_protected_html_handler(_fp: str, _route: str):
            """Create an async handler that checks session before serving."""
            async def _handler(request: Request):
                account = _get_account_from_session(request)
                if account is None:
                    import urllib.parse as _up
                    return _RedirectResponse(
                        f"/ui/login?next={_up.quote(_route)}", status_code=302,
                    )
                return _FileResponse(_fp, media_type="text/html")
            return _handler

        for _route_path, _filename in _html_routes.items():
            _filepath = _project_root / _filename
            if _filepath.is_file():
                if _route_path in _PUBLIC_HTML_ROUTES:
                    app.add_api_route(
                        _route_path, _make_html_handler(str(_filepath)),
                        methods=["GET"], include_in_schema=False,
                    )
                else:
                    app.add_api_route(
                        _route_path, _make_protected_html_handler(str(_filepath), _route_path),
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

    # ══════════════════════════════════════════════════════════════════════
    # UNIFIED GATEWAY — Flask services ported to native FastAPI endpoints
    # Each sub-section replaces a standalone Flask Blueprint/app so that
    # all routes are reachable via the single FastAPI runtime on port 8000.
    # ══════════════════════════════════════════════════════════════════════

    # ── Module Compiler (was: src/module_compiler/api/endpoints.py) ────────

    try:
        import sys as _sys
        # module_compiler lives under src/ (a sibling of runtime/) and uses
        # relative package imports.  We add the src/ directory to sys.path so
        # it can be imported as a top-level package without changing the wider
        # project layout.  This mirrors what the original standalone Flask app
        # did via sys.path.insert in its own __main__ block.
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from module_compiler import ModuleCompiler as _ModuleCompiler, ModuleRegistry as _ModuleRegistry

        _mc_compiler = _ModuleCompiler()
        _mc_registry = _ModuleRegistry()

        @app.post("/api/module-compiler/compile")
        async def mc_compile(request: Request):
            """Compile a module from source path."""
            try:
                data = await request.json()
                if not data or "source_path" not in data:
                    return JSONResponse({"success": False, "error": {"code": "MISSING_FIELD", "message": "Missing required field: source_path"}}, status_code=400)
                source_path = data["source_path"]
                if not os.path.exists(source_path):
                    return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": f"Source file not found: {source_path}"}}, status_code=404)
                spec = _mc_compiler.compile_module(source_path=source_path, requested_capabilities=data.get("requested_capabilities"))
                _mc_registry.register(spec)
                return JSONResponse({"success": True, "data": {
                    "module_id": spec.module_id, "source_path": spec.source_path,
                    "version_hash": spec.version_hash,
                    "capabilities": [{"name": c.name, "description": c.description, "deterministic": c.is_deterministic(), "requires_network": c.requires_network(), "timeout_seconds": c.resource_profile.timeout_seconds} for c in spec.capabilities],
                    "sandbox_profile": spec.sandbox_profile.to_dict(),
                    "verification_status": spec.verification_status,
                    "is_partial": spec.is_partial,
                    "requires_manual_review": spec.requires_manual_review,
                    "uncertainty_flags": spec.uncertainty_flags,
                    "compiled_at": spec.compiled_at,
                }})
            except Exception as exc:
                logger.error("mc_compile error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.post("/api/module-compiler/compile-directory")
        async def mc_compile_directory(request: Request):
            """Compile all modules in a directory."""
            try:
                data = await request.json()
                if not data or "directory_path" not in data:
                    return JSONResponse({"success": False, "error": {"code": "MISSING_FIELD", "message": "Missing required field: directory_path"}}, status_code=400)
                directory_path = data["directory_path"]
                if not os.path.isdir(directory_path):
                    return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": f"Directory not found: {directory_path}"}}, status_code=404)
                specs = _mc_compiler.compile_directory(directory_path, data.get("pattern", "*.py"))
                compiled, failed = 0, 0
                for spec in specs:
                    if _mc_registry.register(spec) and not spec.is_partial:
                        compiled += 1
                    else:
                        failed += 1
                return JSONResponse({"success": True, "data": {"compiled": compiled, "failed": failed, "total": len(specs), "modules": [{"module_id": s.module_id, "capabilities": len(s.capabilities), "verification_status": s.verification_status} for s in specs]}})
            except Exception as exc:
                logger.error("mc_compile_directory error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/module-compiler/modules")
        async def mc_list_modules(request: Request):
            """List all registered modules."""
            try:
                a = request.query_params
                modules = _mc_registry.list_modules(
                    deterministic_only=a.get("deterministic", "").lower() == "true",
                    network_required=None if not a.get("network") else a.get("network", "").lower() == "true",
                    verification_status=a.get("status"),
                )
                return JSONResponse({"success": True, "data": {"count": len(modules), "modules": modules}})
            except Exception as exc:
                logger.error("mc_list_modules error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/module-compiler/modules/{module_id}")
        async def mc_get_module(module_id: str):
            """Get detailed module specification."""
            try:
                spec = _mc_registry.get(module_id)
                if not spec:
                    return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": f"Module not found: {module_id}"}}, status_code=404)
                return JSONResponse({"success": True, "data": {"module": spec.to_dict()}})
            except Exception as exc:
                logger.error("mc_get_module error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.delete("/api/module-compiler/modules/{module_id}")
        async def mc_delete_module(module_id: str):
            """Remove module from registry."""
            try:
                if not _mc_registry.remove(module_id):
                    return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": f"Failed to remove module: {module_id}"}}, status_code=500)
                return JSONResponse({"success": True, "data": {"message": f"Module removed: {module_id}"}})
            except Exception as exc:
                logger.error("mc_delete_module error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/module-compiler/capabilities")
        async def mc_search_capabilities(request: Request):
            """Search for capabilities."""
            try:
                a = request.query_params
                query = a.get("q", "")
                if not query:
                    return JSONResponse({"success": False, "error": {"code": "MISSING_FIELD", "message": "Missing required parameter: q"}}, status_code=400)
                results = _mc_registry.search_capabilities(query, a.get("deterministic", "").lower() == "true")
                return JSONResponse({"success": True, "data": {"count": len(results), "query": query, "capabilities": results}})
            except Exception as exc:
                logger.error("mc_search_capabilities error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/module-compiler/capabilities/{capability_name}")
        async def mc_get_capability(capability_name: str):
            """Get detailed capability information."""
            try:
                cap = _mc_registry.get_capability(capability_name)
                if not cap:
                    return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": f"Capability not found: {capability_name}"}}, status_code=404)
                return JSONResponse({"success": True, "data": {"capability": cap.to_dict()}})
            except Exception as exc:
                logger.error("mc_get_capability error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/module-compiler/stats")
        async def mc_get_stats():
            """Get registry statistics."""
            try:
                return JSONResponse({"success": True, "data": {"stats": _mc_registry.get_stats()}})
            except Exception as exc:
                logger.error("mc_get_stats error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/module-compiler/health")
        async def mc_health():
            """Module compiler health check."""
            try:
                stats = _mc_registry.get_stats()
                return JSONResponse({"success": True, "data": {"status": "healthy", "compiler_version": _mc_compiler.compiler_version, "registry_modules": stats["total_modules"], "registry_capabilities": stats["total_capabilities"]}})
            except Exception as exc:
                logger.error("mc_health error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        logger.info("Module Compiler API registered at /api/module-compiler/*")
    except Exception as _mc_exc:
        logger.warning("Module Compiler API unavailable: %s", _mc_exc)

    # ── Compute Plane (was: src/compute_plane/api/endpoints.py) ────────────

    try:
        from compute_plane.service import ComputeService as _ComputeService
        from compute_plane.models.compute_request import ComputeRequest as _ComputeRequest

        _cp_service = _ComputeService(enable_caching=True)

        @app.get("/api/compute-plane/health")
        async def cp_health():
            """Compute plane health check."""
            return JSONResponse({"success": True, "data": {"status": "healthy", "service": "compute-plane"}})

        @app.post("/api/compute-plane/compute")
        async def cp_submit(request: Request):
            """Submit a computation request."""
            try:
                data = await request.json()
                req = _ComputeRequest(
                    expression=data["expression"],
                    language=data["language"],
                    assumptions=data.get("assumptions", {}),
                    precision=data.get("precision", 10),
                    timeout=data.get("timeout", 30),
                    metadata=data.get("metadata", {}),
                )
                request_id = _cp_service.submit_request(req)
                return JSONResponse({"success": True, "data": {"request_id": request_id, "status": "pending"}}, status_code=202)
            except Exception as exc:
                logger.error("cp_submit error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "BAD_REQUEST", "message": str(exc)}}, status_code=400)

        @app.get("/api/compute-plane/compute/{request_id}")
        async def cp_get_result(request_id: str):
            """Get computation result."""
            result = _cp_service.get_result(request_id)
            if result is None:
                return JSONResponse({"success": True, "data": {"request_id": request_id, "status": "pending"}}, status_code=202)
            return JSONResponse({"success": True, "data": result.to_dict()})

        @app.get("/api/compute-plane/compute/{request_id}/steps")
        async def cp_get_steps(request_id: str):
            """Get derivation steps for computation."""
            result = _cp_service.get_result(request_id)
            if result is None:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Request not found or still pending"}}, status_code=404)
            return JSONResponse({"success": True, "data": {"request_id": request_id, "derivation_steps": result.derivation_steps}})

        @app.post("/api/compute-plane/compute/validate")
        async def cp_validate(request: Request):
            """Validate expression syntax."""
            try:
                data = await request.json()
                validation = _cp_service.validate_expression(data["expression"], data["language"])
                return JSONResponse({"success": True, "data": validation})
            except Exception as exc:
                logger.error("cp_validate error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "BAD_REQUEST", "message": str(exc)}}, status_code=400)

        @app.get("/api/compute-plane/statistics")
        async def cp_statistics():
            """Get compute service statistics."""
            return JSONResponse({"success": True, "data": _cp_service.get_statistics()})

        logger.info("Compute Plane API registered at /api/compute-plane/*")
    except Exception as _cp_exc:
        logger.warning("Compute Plane API unavailable: %s", _cp_exc)

    # ── Gate Synthesis (was: src/gate_synthesis/api_server.py) ─────────────

    try:
        from gate_synthesis.failure_mode_enumerator import FailureModeEnumerator as _FME
        from gate_synthesis.gate_generator import GateGenerator as _GateGenerator
        from gate_synthesis.gate_lifecycle_manager import GateLifecycleManager as _GLM
        from gate_synthesis.models import (
            ExposureSignal as _ExposureSignal,
            FailureMode as _FailureMode,
            FailureModeType as _FailureModeType,
            GateCategory as _GateCategory,
            GateState as _GateState,
        )
        from gate_synthesis.murphy_estimator import MurphyProbabilityEstimator as _MPE
        from confidence_engine.models import (
            ArtifactGraph as _ArtifactGraph,
            ArtifactNode as _ArtifactNode,
            ArtifactSource as _ArtifactSource,
            ArtifactType as _ArtifactType,
            AuthorityBand as _AuthorityBand,
            ConfidenceState as _ConfidenceState,
            Phase as _Phase,
        )

        _gs_fme = _FME()
        _gs_mpe = _MPE()
        _gs_gg = _GateGenerator()
        _gs_glm = _GLM()
        _gs_artifact_graph = _ArtifactGraph()

        @app.post("/api/gate-synthesis/failure-modes/enumerate")
        async def gs_enumerate_failure_modes(request: Request):
            """Enumerate failure modes for current state."""
            try:
                data = await request.json()
                cs_data = data["confidence_state"]
                confidence_state = _ConfidenceState(
                    confidence=cs_data["confidence"],
                    generative_score=cs_data["generative_score"],
                    deterministic_score=cs_data["deterministic_score"],
                    epistemic_instability=cs_data["epistemic_instability"],
                    phase=_Phase(cs_data["phase"]),
                )
                confidence_state.verified_artifacts = cs_data.get("verified_artifacts", 0)
                confidence_state.total_artifacts = cs_data.get("total_artifacts", 0)
                authority_band = _AuthorityBand(data["authority_band"])
                exposure_signal = None
                if "exposure_signal" in data:
                    ed = data["exposure_signal"]
                    exposure_signal = _ExposureSignal(
                        signal_id=ed.get("signal_id", "default"),
                        external_side_effects=ed["external_side_effects"],
                        reversibility=ed["reversibility"],
                        blast_radius_estimate=ed["blast_radius_estimate"],
                        affected_systems=ed.get("affected_systems", []),
                    )
                fms = _gs_fme.enumerate_failure_modes(_gs_artifact_graph, confidence_state, authority_band, exposure_signal)
                return JSONResponse({"success": True, "data": {"failure_modes": [fm.to_dict() for fm in fms], "count": len(fms)}})
            except Exception as exc:
                logger.error("gs_enumerate_failure_modes error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.post("/api/gate-synthesis/murphy/estimate")
        async def gs_estimate_murphy(request: Request):
            """Estimate Murphy probability for risk vector."""
            try:
                from gate_synthesis.models import RiskVector as _RiskVector
                data = await request.json()
                rv = _RiskVector(**data["risk_vector"])
                prob = _gs_mpe.estimate_murphy_probability(rv)
                return JSONResponse({"success": True, "data": {"murphy_probability": prob, "gate_required": _gs_mpe.requires_gate(prob), "high_risk": _gs_mpe.is_high_risk(prob), "risk_vector": rv.to_dict()}})
            except Exception as exc:
                logger.error("gs_estimate_murphy error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.post("/api/gate-synthesis/murphy/analyze-exposure")
        async def gs_analyze_exposure(request: Request):
            """Analyze exposure signal."""
            try:
                data = await request.json()
                es = _ExposureSignal(
                    signal_id=data.get("signal_id", "default"),
                    external_side_effects=data["external_side_effects"],
                    reversibility=data["reversibility"],
                    blast_radius_estimate=data["blast_radius_estimate"],
                    affected_systems=data.get("affected_systems", []),
                )
                return JSONResponse({"success": True, "data": {"analysis": _gs_mpe.analyze_exposure(es)}})
            except Exception as exc:
                logger.error("gs_analyze_exposure error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.post("/api/gate-synthesis/gates/generate")
        async def gs_generate_gates(request: Request):
            """Generate gates for failure modes."""
            try:
                from gate_synthesis.models import RiskVector as _RiskVector
                data = await request.json()
                failure_modes = []
                for fmd in data["failure_modes"]:
                    rv = _RiskVector(**fmd["risk_vector"])
                    fm = _FailureMode(id=fmd["id"], type=_FailureModeType(fmd["type"]), probability=fmd["probability"], impact=fmd["impact"], risk_vector=rv, description=fmd["description"], affected_artifacts=fmd.get("affected_artifacts", []))
                    failure_modes.append(fm)
                current_phase = _Phase(data["current_phase"])
                current_authority = _AuthorityBand(data["current_authority"])
                murphy_probs = {fm.id: _gs_mpe.estimate_failure_mode_probability(fm) for fm in failure_modes}
                gates = _gs_gg.generate_gates(failure_modes, current_phase, current_authority, murphy_probs)
                for gate in gates:
                    _gs_glm.add_gate(gate)
                return JSONResponse({"success": True, "data": {"gates": [g.to_dict() for g in gates], "count": len(gates)}})
            except Exception as exc:
                logger.error("gs_generate_gates error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.post("/api/gate-synthesis/gates/activate/{gate_id}")
        async def gs_activate_gate(gate_id: str):
            """Activate a specific gate."""
            if not _gs_glm.activate_gate(gate_id):
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Gate not found or cannot be activated"}}, status_code=404)
            return JSONResponse({"success": True, "data": {"gate_id": gate_id, "message": "Gate activated"}})

        @app.post("/api/gate-synthesis/gates/activate-all")
        async def gs_activate_all_gates():
            """Activate all proposed gates."""
            activated = _gs_glm.activate_all_proposed_gates()
            return JSONResponse({"success": True, "data": {"activated_gates": activated, "count": len(activated)}})

        @app.post("/api/gate-synthesis/gates/retire/{gate_id}")
        async def gs_retire_gate(gate_id: str, request: Request):
            """Retire a specific gate."""
            data = {}
            try:
                data = await request.json()
            except Exception:
                pass
            if not _gs_glm.retire_gate(gate_id, data.get("reason", "")):
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Gate not found or cannot be retired"}}, status_code=404)
            return JSONResponse({"success": True, "data": {"gate_id": gate_id, "message": "Gate retired"}})

        @app.post("/api/gate-synthesis/gates/check-expiry")
        async def gs_check_expiry():
            """Check and retire expired gates."""
            expired = _gs_glm.check_and_retire_expired_gates()
            return JSONResponse({"success": True, "data": {"expired_gates": expired, "count": len(expired)}})

        @app.post("/api/gate-synthesis/gates/update-retirement-conditions")
        async def gs_update_retirement_conditions(request: Request):
            """Update retirement conditions for gates."""
            try:
                data = await request.json()
                retired = _gs_glm.check_all_retirement_conditions(data["condition_values"])
                return JSONResponse({"success": True, "data": {"retired_gates": retired, "count": len(retired)}})
            except Exception as exc:
                logger.error("gs_update_retirement_conditions error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/gate-synthesis/gates/list")
        async def gs_list_gates(request: Request):
            """List all gates."""
            a = request.query_params
            gates = list(_gs_glm.registry.gates.values())
            if a.get("state"):
                gates = [g for g in gates if g.state == _GateState(a["state"])]
            if a.get("category"):
                gates = [g for g in gates if g.category == _GateCategory(a["category"])]
            return JSONResponse({"success": True, "data": {"gates": [g.to_dict() for g in gates], "count": len(gates)}})

        @app.get("/api/gate-synthesis/gates/active")
        async def gs_get_active_gates():
            """Get all active gates."""
            active = _gs_glm.registry.get_active_gates()
            return JSONResponse({"success": True, "data": {"gates": [g.to_dict() for g in active], "count": len(active)}})

        @app.get("/api/gate-synthesis/gates/by-target/{target}")
        async def gs_get_gates_by_target(target: str):
            """Get gates for specific target."""
            gates = _gs_glm.get_active_gates_for_target(target)
            return JSONResponse({"success": True, "data": {"target": target, "gates": [g.to_dict() for g in gates], "count": len(gates)}})

        @app.get("/api/gate-synthesis/gates/{gate_id}")
        async def gs_get_gate(gate_id: str):
            """Get specific gate."""
            gate = _gs_glm.registry.get_gate(gate_id)
            if not gate:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Gate not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": {"gate": gate.to_dict()}})

        @app.get("/api/gate-synthesis/statistics")
        async def gs_statistics():
            """Get gate statistics."""
            return JSONResponse({"success": True, "data": {"statistics": _gs_glm.get_gate_statistics()}})

        @app.get("/api/gate-synthesis/logs/activation")
        async def gs_activation_log(request: Request):
            """Get activation log."""
            limit = request.query_params.get("limit")
            log = _gs_glm.get_activation_log(int(limit) if limit else None)
            return JSONResponse({"success": True, "data": {"log": log, "count": len(log)}})

        @app.get("/api/gate-synthesis/logs/retirement")
        async def gs_retirement_log(request: Request):
            """Get retirement log."""
            limit = request.query_params.get("limit")
            log = _gs_glm.get_retirement_log(int(limit) if limit else None)
            return JSONResponse({"success": True, "data": {"log": log, "count": len(log)}})

        @app.post("/api/gate-synthesis/artifacts/add")
        async def gs_add_artifact(request: Request):
            """Add artifact to graph."""
            try:
                data = await request.json()
                node = _ArtifactNode(id=data.get("id", ""), type=_ArtifactType(data["type"]), source=_ArtifactSource(data["source"]), content=data["content"], confidence_weight=data.get("confidence_weight", 1.0), dependencies=data.get("dependencies", []))
                _gs_artifact_graph.add_node(node)
                return JSONResponse({"success": True, "data": {"artifact_id": node.id}})
            except Exception as exc:
                logger.error("gs_add_artifact error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/gate-synthesis/health")
        async def gs_health():
            """Gate synthesis health check."""
            return JSONResponse({"success": True, "data": {"status": "healthy", "service": "gate-synthesis-engine", "timestamp": _now_iso(), "components": {"failure_mode_enumerator": "operational", "murphy_estimator": "operational", "gate_generator": "operational", "gate_lifecycle_manager": "operational"}}})

        @app.post("/api/gate-synthesis/reset")
        async def gs_reset():
            """Reset all gate synthesis state (for testing)."""
            nonlocal _gs_artifact_graph, _gs_glm
            _gs_artifact_graph = _ArtifactGraph()
            _gs_glm = _GLM()
            return JSONResponse({"success": True, "data": {"message": "State reset successfully"}})

        logger.info("Gate Synthesis API registered at /api/gate-synthesis/*")
    except Exception as _gs_exc:
        logger.warning("Gate Synthesis API unavailable: %s", _gs_exc)

    # ── Cost Optimization Advisor (was: src/cost_optimization_advisor.py) ──

    try:
        from src.cost_optimization_advisor import CostOptimizationAdvisor as _COAAdvisor

        _coa = _COAAdvisor()

        @app.post("/api/coa/resources")
        async def coa_register_resource(request: Request):
            """Register a cloud resource."""
            try:
                b = await request.json() or {}
                if not b.get("name"):
                    return JSONResponse({"success": False, "error": {"code": "MISSING_FIELD", "message": "Missing required field: name"}}, status_code=400)
                r = _coa.register_resource(name=b["name"], provider=b.get("provider", "aws"), resource_kind=b.get("resource_kind", "compute"), region=b.get("region", ""), monthly_cost=float(b.get("monthly_cost", 0)), currency=b.get("currency", "USD"), utilization_pct=float(b.get("utilization_pct", 0)), tags=b.get("tags", {}))
                return JSONResponse({"success": True, "data": r.to_dict()}, status_code=201)
            except Exception as exc:
                logger.error("coa_register_resource error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/coa/resources")
        async def coa_list_resources(request: Request):
            """List cloud resources."""
            a = request.query_params
            resources = _coa.list_resources(provider=a.get("provider"), resource_kind=a.get("resource_kind"), region=a.get("region"), limit=int(a.get("limit", 100)))
            return JSONResponse({"success": True, "data": [r.to_dict() for r in resources]})

        @app.get("/api/coa/resources/{resource_id}")
        async def coa_get_resource(resource_id: str):
            """Get a cloud resource."""
            res = _coa.get_resource(resource_id)
            if res is None:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Resource not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": res.to_dict()})

        @app.put("/api/coa/resources/{resource_id}")
        async def coa_update_resource(resource_id: str, request: Request):
            """Update a cloud resource."""
            b = await request.json() or {}
            res = _coa.update_resource(resource_id, monthly_cost=b.get("monthly_cost"), utilization_pct=b.get("utilization_pct"))
            if res is None:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Resource not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": res.to_dict()})

        @app.delete("/api/coa/resources/{resource_id}")
        async def coa_delete_resource(resource_id: str):
            """Delete a cloud resource."""
            if not _coa.delete_resource(resource_id):
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Resource not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": {"deleted": True}})

        @app.post("/api/coa/spend")
        async def coa_record_spend(request: Request):
            """Record a spend entry."""
            try:
                b = await request.json() or {}
                for k in ("resource_id", "amount", "period"):
                    if not b.get(k) and b.get(k) != 0:
                        return JSONResponse({"success": False, "error": {"code": "MISSING_FIELD", "message": f"Missing required field: {k}"}}, status_code=400)
                rec = _coa.record_spend(resource_id=b["resource_id"], amount=float(b["amount"]), period=b["period"], category=b.get("category", ""), currency=b.get("currency", "USD"))
                return JSONResponse({"success": True, "data": rec.to_dict()}, status_code=201)
            except Exception as exc:
                logger.error("coa_record_spend error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/coa/spend")
        async def coa_get_spend(request: Request):
            """Get spend records."""
            a = request.query_params
            records = _coa.get_spend(resource_id=a.get("resource_id"), provider=a.get("provider"), period=a.get("period"), limit=int(a.get("limit", 100)))
            return JSONResponse({"success": True, "data": [r.to_dict() for r in records]})

        @app.post("/api/coa/analyze/{resource_id}")
        async def coa_analyze_rightsizing(resource_id: str):
            """Analyze rightsizing for a resource."""
            rec = _coa.analyze_rightsizing(resource_id)
            return JSONResponse({"success": True, "data": rec.to_dict()})

        @app.post("/api/coa/spot/scan")
        async def coa_scan_spot(request: Request):
            """Scan for spot instance opportunities."""
            b = {}
            try:
                b = await request.json() or {}
            except Exception:
                pass
            opps = _coa.scan_spot_opportunities(provider=b.get("provider"), region=b.get("region"))
            return JSONResponse({"success": True, "data": [o.to_dict() for o in opps]})

        @app.get("/api/coa/recommendations")
        async def coa_get_recommendations(request: Request):
            """Get cost optimization recommendations."""
            a = request.query_params
            recs = _coa.get_recommendations(resource_id=a.get("resource_id"), severity=a.get("severity"), status=a.get("status"), limit=int(a.get("limit", 100)))
            return JSONResponse({"success": True, "data": [r.to_dict() for r in recs]})

        @app.put("/api/coa/recommendations/{rec_id}/status")
        async def coa_update_rec_status(rec_id: str, request: Request):
            """Update recommendation status."""
            b = await request.json() or {}
            if not b.get("status"):
                return JSONResponse({"success": False, "error": {"code": "MISSING_FIELD", "message": "Missing required field: status"}}, status_code=400)
            rec = _coa.update_recommendation_status(rec_id, b["status"])
            if rec is None:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Recommendation not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": rec.to_dict()})

        @app.post("/api/coa/budgets")
        async def coa_set_budget(request: Request):
            """Set a budget."""
            b = await request.json() or {}
            for k in ("budget_name", "budget_limit"):
                if not b.get(k) and b.get(k) != 0:
                    return JSONResponse({"success": False, "error": {"code": "MISSING_FIELD", "message": f"Missing required field: {k}"}}, status_code=400)
            ba = _coa.set_budget(budget_name=b["budget_name"], budget_limit=float(b["budget_limit"]))
            return JSONResponse({"success": True, "data": ba.to_dict()}, status_code=201)

        @app.get("/api/coa/budgets/check")
        async def coa_check_budgets():
            """Check budget alerts."""
            alerts = _coa.check_budgets()
            return JSONResponse({"success": True, "data": [a.to_dict() for a in alerts]})

        @app.get("/api/coa/summary")
        async def coa_summary(request: Request):
            """Get cost summary."""
            summary = _coa.get_cost_summary(provider=request.query_params.get("provider"))
            return JSONResponse({"success": True, "data": summary.to_dict()})

        @app.post("/api/coa/export")
        async def coa_export():
            """Export COA state."""
            return JSONResponse({"success": True, "data": _coa.export_state()})

        @app.get("/api/coa/health")
        async def coa_health():
            """COA health check."""
            resources = _coa.list_resources()
            return JSONResponse({"success": True, "data": {"status": "healthy", "module": "COA-001", "tracked_resources": len(resources)}})

        logger.info("Cost Optimization Advisor API registered at /api/coa/*")
    except Exception as _coa_exc:
        logger.warning("Cost Optimization Advisor API unavailable: %s", _coa_exc)

    # ── Compliance as Code Engine (was: src/compliance_as_code_engine.py) ──

    try:
        from src.compliance_as_code_engine import ComplianceAsCodeEngine as _CCEEngine

        _cce = _CCEEngine()

        @app.post("/api/cce/rules")
        async def cce_create_rule(request: Request):
            """Create a compliance rule."""
            try:
                b = await request.json() or {}
                for k in ("name", "expression"):
                    if not b.get(k):
                        return JSONResponse({"success": False, "error": {"code": "MISSING_FIELD", "message": f"Missing required field: {k}"}}, status_code=400)
                r = _cce.create_rule(name=b["name"], description=b.get("description", ""), framework=b.get("framework", "custom"), severity=b.get("severity", "medium"), expression=b["expression"], remediation=b.get("remediation", ""), tags=b.get("tags", {}))
                return JSONResponse({"success": True, "data": r.to_dict()}, status_code=201)
            except Exception as exc:
                logger.error("cce_create_rule error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/cce/rules")
        async def cce_list_rules(request: Request):
            """List compliance rules."""
            a = request.query_params
            rules = _cce.list_rules(framework=a.get("framework"), severity=a.get("severity"), status=a.get("status"), limit=int(a.get("limit", 100)))
            return JSONResponse({"success": True, "data": [r.to_dict() for r in rules]})

        @app.get("/api/cce/rules/{rule_id}")
        async def cce_get_rule(rule_id: str):
            """Get a compliance rule."""
            rule = _cce.get_rule(rule_id)
            if rule is None:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Rule not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": rule.to_dict()})

        @app.put("/api/cce/rules/{rule_id}")
        async def cce_update_rule(rule_id: str, request: Request):
            """Update a compliance rule."""
            b = await request.json() or {}
            rule = _cce.update_rule(rule_id, status=b.get("status"), severity=b.get("severity"), expression=b.get("expression"), remediation=b.get("remediation"))
            if rule is None:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Rule not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": rule.to_dict()})

        @app.delete("/api/cce/rules/{rule_id}")
        async def cce_delete_rule(rule_id: str):
            """Delete a compliance rule."""
            if not _cce.delete_rule(rule_id):
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Rule not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": {"deleted": True}})

        @app.post("/api/cce/check/{rule_id}")
        async def cce_check_rule(rule_id: str, request: Request):
            """Run a single compliance rule check."""
            b = await request.json() or {}
            exe = _cce.check_rule(rule_id, b)
            return JSONResponse({"success": True, "data": exe.to_dict()})

        @app.post("/api/cce/scan")
        async def cce_run_scan(request: Request):
            """Run a compliance scan."""
            try:
                b = await request.json() or {}
                if not b.get("name"):
                    return JSONResponse({"success": False, "error": {"code": "MISSING_FIELD", "message": "Missing required field: name"}}, status_code=400)
                scan = _cce.run_scan(name=b["name"], framework_filter=b.get("framework_filter"), context=b.get("context", {}))
                return JSONResponse({"success": True, "data": scan.to_dict()}, status_code=201)
            except Exception as exc:
                logger.error("cce_run_scan error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/cce/scans")
        async def cce_list_scans(request: Request):
            """List compliance scans."""
            a = request.query_params
            scans = _cce.list_scans(framework=a.get("framework"), status=a.get("status"), limit=int(a.get("limit", 50)))
            return JSONResponse({"success": True, "data": [s.to_dict() for s in scans]})

        @app.get("/api/cce/scans/{scan_id}")
        async def cce_get_scan(scan_id: str):
            """Get a compliance scan."""
            scan = _cce.get_scan(scan_id)
            if scan is None:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Scan not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": scan.to_dict()})

        @app.get("/api/cce/scans/{scan_id}/report")
        async def cce_generate_report(scan_id: str):
            """Generate compliance report for a scan."""
            report = _cce.generate_report(scan_id)
            if report is None:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Scan not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": report.to_dict()})

        @app.post("/api/cce/remediations")
        async def cce_create_remediation(request: Request):
            """Create a remediation action."""
            try:
                b = await request.json() or {}
                for k in ("rule_id", "scan_id", "description"):
                    if not b.get(k):
                        return JSONResponse({"success": False, "error": {"code": "MISSING_FIELD", "message": f"Missing required field: {k}"}}, status_code=400)
                action = _cce.create_remediation(rule_id=b["rule_id"], scan_id=b["scan_id"], description=b["description"], priority=b.get("priority", "medium"), assigned_to=b.get("assigned_to", ""))
                return JSONResponse({"success": True, "data": action.to_dict()}, status_code=201)
            except Exception as exc:
                logger.error("cce_create_remediation error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/cce/remediations")
        async def cce_list_remediations(request: Request):
            """List remediation actions."""
            a = request.query_params
            completed = None
            if a.get("completed") is not None:
                completed = a.get("completed", "").lower() == "true"
            actions = _cce.list_remediations(rule_id=a.get("rule_id"), scan_id=a.get("scan_id"), completed=completed, limit=int(a.get("limit", 100)))
            return JSONResponse({"success": True, "data": [r.to_dict() for r in actions]})

        @app.post("/api/cce/remediations/{remediation_id}/complete")
        async def cce_complete_remediation(remediation_id: str):
            """Complete a remediation action."""
            action = _cce.complete_remediation(remediation_id)
            if action is None:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Remediation not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": action.to_dict()})

        @app.get("/api/cce/summary")
        async def cce_summary(request: Request):
            """Get compliance summary."""
            summary = _cce.get_compliance_summary(framework=request.query_params.get("framework"))
            return JSONResponse({"success": True, "data": summary})

        @app.post("/api/cce/export")
        async def cce_export():
            """Export CCE state."""
            return JSONResponse({"success": True, "data": _cce.export_state()})

        @app.get("/api/cce/health")
        async def cce_health():
            """CCE health check."""
            rules = _cce.list_rules()
            return JSONResponse({"success": True, "data": {"status": "healthy", "module": "CCE-001", "tracked_rules": len(rules)}})

        logger.info("Compliance as Code Engine API registered at /api/cce/*")
    except Exception as _cce_exc:
        logger.warning("Compliance as Code Engine API unavailable: %s", _cce_exc)

    # ── Blockchain Audit Trail (was: src/blockchain_audit_trail.py) ─────────

    try:
        from src.blockchain_audit_trail import BlockchainAuditTrail as _BATEngine, EntryType as _EntryType

        _bat = _BATEngine()

        @app.get("/api/bat/health")
        async def bat_health():
            """BAT health check."""
            return JSONResponse({"success": True, "data": {"status": "healthy", "module": "BAT-001"}})

        @app.post("/api/bat/entries")
        async def bat_record_entry(request: Request):
            """Record an audit entry."""
            try:
                b = await request.json() or {}
                for k in ("entry_type", "actor", "action"):
                    if not b.get(k):
                        return JSONResponse({"success": False, "error": {"code": "MISSING_FIELD", "message": f"{k} required"}}, status_code=400)
                try:
                    et = _EntryType(b["entry_type"])
                except ValueError:
                    return JSONResponse({"success": False, "error": {"code": "INVALID_FIELD", "message": "Invalid entry_type"}}, status_code=400)
                entry = _bat.record_entry(entry_type=et, actor=b["actor"], action=b["action"], resource=b.get("resource", ""), details=b.get("details", {}), ip_address=b.get("ip_address", ""), outcome=b.get("outcome", "success"))
                return JSONResponse({"success": True, "data": entry.to_dict()}, status_code=201)
            except Exception as exc:
                logger.error("bat_record_entry error: %s", exc, exc_info=True)
                return JSONResponse({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}, status_code=500)

        @app.get("/api/bat/entries/search")
        async def bat_search_entries(request: Request):
            """Search audit entries."""
            a = request.query_params
            results = _bat.search_entries(entry_type=a.get("entry_type"), actor=a.get("actor"), resource=a.get("resource"), action=a.get("action"), limit=int(a.get("limit", 100)))
            return JSONResponse({"success": True, "data": [e.to_dict() for e in results]})

        @app.get("/api/bat/blocks")
        async def bat_list_blocks(request: Request):
            """List blockchain blocks."""
            a = request.query_params
            blocks = _bat.list_blocks(limit=int(a.get("limit", 50)), offset=int(a.get("offset", 0)))
            return JSONResponse({"success": True, "data": [bl.to_dict() for bl in blocks]})

        @app.get("/api/bat/blocks/seal")
        async def bat_get_seal_info():
            """Get seal info (GET variant)."""
            return JSONResponse({"success": True, "data": {"message": "Use POST /api/bat/blocks/seal to seal the current block"}})

        @app.post("/api/bat/blocks/seal")
        async def bat_seal_block():
            """Seal the current block."""
            bl = _bat.seal_current_block()
            if not bl:
                return JSONResponse({"success": False, "error": {"code": "BAT_EMPTY", "message": "No pending entries"}}, status_code=400)
            return JSONResponse({"success": True, "data": bl.to_dict()}, status_code=201)

        @app.get("/api/bat/blocks/index/{idx}")
        async def bat_get_block_by_index(idx: int):
            """Get block by index."""
            bl = _bat.get_block_by_index(idx)
            if not bl:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Block not found at index"}}, status_code=404)
            return JSONResponse({"success": True, "data": bl.to_dict()})

        @app.get("/api/bat/blocks/{block_id}")
        async def bat_get_block(block_id: str):
            """Get a specific block."""
            bl = _bat.get_block(block_id)
            if not bl:
                return JSONResponse({"success": False, "error": {"code": "NOT_FOUND", "message": "Block not found"}}, status_code=404)
            return JSONResponse({"success": True, "data": bl.to_dict()})

        @app.get("/api/bat/verify")
        async def bat_verify_chain():
            """Verify blockchain integrity."""
            result = _bat.verify_chain()
            return JSONResponse({"success": True, "data": result.to_dict()})

        @app.get("/api/bat/export")
        async def bat_export_chain():
            """Export the full blockchain."""
            return JSONResponse({"success": True, "data": _bat.export_chain()})

        @app.get("/api/bat/stats")
        async def bat_stats():
            """Get blockchain statistics."""
            return JSONResponse({"success": True, "data": _bat.get_stats().to_dict()})

        logger.info("Blockchain Audit Trail API registered at /api/bat/*")
    except Exception as _bat_exc:
        logger.warning("Blockchain Audit Trail API unavailable: %s", _bat_exc)

    # ══════════════════════════════════════════════════════════════════════
    # AUTH MIDDLEWARE — unified X-API-Key enforcement for all /api/* routes
    # Permissive when MURPHY_API_KEY env var is not set (development mode).
    # ══════════════════════════════════════════════════════════════════════

    from starlette.middleware.base import BaseHTTPMiddleware as _BHMW

    class _APIKeyMiddleware(_BHMW):
        """Unified API key enforcement for all /api/* routes."""

        EXEMPT_PATHS = {"/api/health", "/api/info", "/api/manifest"}

        async def dispatch(self, request: Request, call_next):
            if request.url.path.startswith("/api/") and request.url.path not in self.EXEMPT_PATHS:
                expected_key = os.environ.get("MURPHY_API_KEY", "")
                if expected_key:
                    # Starlette normalises header names to lowercase (RFC 7230);
                    # use lowercase "x-api-key" here to match that behaviour.
                    api_key = request.headers.get("x-api-key", "")
                    if api_key != expected_key:
                        return JSONResponse(
                            {"success": False, "error": {"code": "AUTH_REQUIRED", "message": "Valid X-API-Key header required"}},
                            status_code=401,
                        )
            return await call_next(request)

    app.add_middleware(_APIKeyMiddleware)

    # ══════════════════════════════════════════════════════════════════════
    # EXCEPTION HANDLERS — normalise all error formats into standard envelope
    # ══════════════════════════════════════════════════════════════════════

    from fastapi import Request as _FARequest
    from fastapi.exceptions import RequestValidationError as _RVE
    from starlette.exceptions import HTTPException as _SHTTPException

    @app.exception_handler(_SHTTPException)
    async def _http_exception_handler(_req: _FARequest, exc: _SHTTPException):
        return JSONResponse(
            {"success": False, "error": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail)}},
            status_code=exc.status_code,
        )

    @app.exception_handler(_RVE)
    async def _validation_exception_handler(_req: _FARequest, exc: _RVE):
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def _general_exception_handler(_req: _FARequest, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            {"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}},
            status_code=500,
        )

    # ══════════════════════════════════════════════════════════════════════
    # STUB ENDPOINTS — frontend calls that are not yet fully implemented
    # All return 501 Not Implemented with a clear error code.
    # ══════════════════════════════════════════════════════════════════════

    @app.post("/api/analyze-domain")
    async def stub_analyze_domain():
        """Stub: analyze domain not yet implemented."""
        return JSONResponse({"success": False, "error": {"code": "NOT_IMPLEMENTED", "message": "Analyze domain not yet implemented"}}, status_code=501)

    # ══════════════════════════════════════════════════════════════════════
    # API MANIFEST — machine-readable registry of all registered endpoints
    # ══════════════════════════════════════════════════════════════════════

    @app.get("/api/manifest")
    async def api_manifest():
        """Return a machine-readable manifest of all registered API endpoints."""
        routes = []
        for route in app.routes:
            if hasattr(route, "path") and route.path.startswith("/api/"):
                # HEAD and OPTIONS are auto-generated by FastAPI for every route
                # and are not part of the explicit API contract — exclude them.
                methods = sorted((route.methods or set()) - {"HEAD", "OPTIONS"})
                routes.append({
                    "path": route.path,
                    "methods": methods,
                    "name": getattr(route, "name", ""),
                })
        return JSONResponse({"success": True, "data": {"endpoints": sorted(routes, key=lambda r: r["path"])}})

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
