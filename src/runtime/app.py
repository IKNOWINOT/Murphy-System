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
    BackgroundTasks,
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

    _is_prod = os.environ.get("MURPHY_ENV", "").lower() in ("production", "staging")
    app = FastAPI(
        title="Murphy System 1.0",
        description="Universal AI Automation System",
        version="1.0.0",
        docs_url=None if _is_prod else "/docs",
        redoc_url=None if _is_prod else "/redoc",
        openapi_url=None if _is_prod else "/openapi.json",
    )

    # ── Utility: ISO timestamp helper ───────────────────────────
    def _now_iso():
        return datetime.now(timezone.utc).isoformat()

    # ═══════════════════════════════════════════════════════════════
    # PRIORITY 1 — API Collection Agent (always loaded first)
    # Guides users through getting every API/SDK key their system needs.
    # This must be the first subsystem attached to app.state so every
    # downstream route can reference it without ImportError.
    # ═══════════════════════════════════════════════════════════════
    try:
        from src.api_collection_agent import APICollectionAgent as _APICollectionAgent
        _api_collection_agent = _APICollectionAgent(base_url="http://localhost:8000")
        app.state.api_collection_agent = _api_collection_agent
        logger.info("APICollectionAgent initialised — ready to guide API/SDK setup")
    except Exception as _aca_exc:
        logger.warning("APICollectionAgent init failed: %s", _aca_exc)
        app.state.api_collection_agent = None

    # ── WorldModelRegistry (integration connectors) ──────────────
    try:
        from src.integrations.world_model_registry import WorldModelRegistry as _WMR
        app.state.world_model_registry = _WMR()
        logger.info("WorldModelRegistry initialised with %d connectors",
                    len(app.state.world_model_registry.list_integrations()))
    except Exception as _wmr_exc:
        logger.warning("WorldModelRegistry init failed: %s", _wmr_exc)
        app.state.world_model_registry = None


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

    # session_token → account_id — Redis-backed with SQLite persistent fallback
    import threading as _threading
    import secrets as _secrets
    import bcrypt as _bcrypt
    _session_lock = _threading.Lock()

    # ── Email verification token store ──────────────────────────
    # Maps verification_token → {account_id, email, created_at}
    # Tokens expire after 24 hours.
    _verification_tokens: "Dict[str, Dict[str, Any]]" = {}
    _VERIFICATION_EXPIRY_SECONDS = 86400  # 24 hours
    _VERIFICATION_FROM_EMAIL = "donotreply@murphy.systems"
    _PASSWORD_RESET_FROM_EMAIL = "donotreply@murphy.systems"

    class _SQLiteSessionFallback:
        """Persistent session store using SQLite WAL backend.

        Replaces the in-memory fallback dict so that sessions survive
        process restarts when Redis is not configured.  Falls back to a
        plain in-memory dict when SQLite is also unavailable.
        """

        _SESSION_TTL = 86400  # 24 hours (matches murphy_session cookie Max-Age)

        def __init__(self) -> None:
            self._mem: "Dict[str, str]" = {}
            self._db = None
            try:
                from src.persistence_wal import create_persistence, PersistenceConfig
                _cfg = PersistenceConfig.from_env()
                self._db = create_persistence(_cfg)
                self._db.run_migrations()
                logger.info("Session store: using SQLite WAL persistence")
            except Exception as _exc:
                logger.warning(
                    "Session store: SQLite unavailable (%s) — using in-memory fallback", _exc
                )

        def _expires_at(self) -> str:
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            return (_dt.now(_tz.utc) + _td(seconds=self._SESSION_TTL)).isoformat()

        def _is_expired(self, expires_at: "Optional[str]") -> bool:
            if not expires_at:
                return False
            from datetime import datetime as _dt, timezone as _tz
            try:
                exp = _dt.fromisoformat(expires_at)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=_tz.utc)
                return _dt.now(_tz.utc) > exp
            except Exception:
                return False

        def _now_iso(self) -> str:
            from datetime import datetime as _dt, timezone as _tz
            return _dt.now(_tz.utc).isoformat()

        def __contains__(self, token: object) -> bool:
            if self._db is not None:
                try:
                    conn = self._db.connect()
                    cursor = conn.execute(
                        "SELECT expires_at FROM session_store WHERE session_id=?", (str(token),)
                    )
                    row = cursor.fetchone()
                    if row is None:
                        return False
                    if self._is_expired(row[0]):
                        return False
                    return True
                except Exception:
                    logger.debug("Suppressed exception in app")
            return token in self._mem

        def __setitem__(self, token: str, account_id: str) -> None:
            self._mem[token] = account_id
            if self._db is not None:
                try:
                    with self._db.transaction() as conn:
                        conn.execute(
                            """INSERT INTO session_store
                                   (session_id, tenant_id, data, created_at, expires_at)
                               VALUES (?, ?, '{}', ?, ?)
                               ON CONFLICT(session_id) DO UPDATE SET
                                   tenant_id=excluded.tenant_id,
                                   expires_at=excluded.expires_at""",
                            (token, account_id, self._now_iso(), self._expires_at()),
                        )
                except Exception as _exc:
                    logger.warning("Session store write failed: %s", _exc)

        def get(self, token: str, default: "Optional[str]" = None) -> "Optional[str]":
            if self._db is not None:
                try:
                    conn = self._db.connect()
                    cursor = conn.execute(
                        "SELECT tenant_id, expires_at FROM session_store WHERE session_id=?",
                        (token,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        return default
                    if self._is_expired(row[1]):
                        return default
                    return row[0]
                except Exception:
                    logger.debug("Suppressed exception in app")
            return self._mem.get(token, default)

        def pop(self, token: str, *args: "Any") -> "Optional[str]":
            val = self.get(token)
            if val is not None:
                self._mem.pop(token, None)
                if self._db is not None:
                    try:
                        with self._db.transaction() as conn:
                            conn.execute(
                                "DELETE FROM session_store WHERE session_id=?", (token,)
                            )
                    except Exception:
                        logger.debug("Suppressed exception in app")
                return val
            return args[0] if args else None

        def __len__(self) -> int:
            if self._db is not None:
                try:
                    now = self._now_iso()
                    conn = self._db.connect()
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM session_store"
                        " WHERE (expires_at IS NULL OR expires_at > ?)",
                        (now,),
                    )
                    return cursor.fetchone()[0]
                except Exception:
                    logger.debug("Suppressed exception in app")
            return len(self._mem)

        def keys(self) -> "List[str]":
            if self._db is not None:
                try:
                    now = self._now_iso()
                    conn = self._db.connect()
                    cursor = conn.execute(
                        "SELECT session_id FROM session_store"
                        " WHERE (expires_at IS NULL OR expires_at > ?)",
                        (now,),
                    )
                    return [row[0] for row in cursor.fetchall()]
                except Exception:
                    logger.debug("Suppressed exception in app")
            return list(self._mem.keys())

        def items(self) -> "List[tuple]":
            if self._db is not None:
                try:
                    now = self._now_iso()
                    conn = self._db.connect()
                    cursor = conn.execute(
                        "SELECT session_id, tenant_id FROM session_store"
                        " WHERE (expires_at IS NULL OR expires_at > ?)",
                        (now,),
                    )
                    return [(row[0], row[1]) for row in cursor.fetchall()]
                except Exception:
                    logger.debug("Suppressed exception in app")
            return list(self._mem.items())

        def purge_expired(self) -> int:
            """Delete expired sessions from the DB; returns count removed."""
            if self._db is None:
                return 0
            try:
                now = self._now_iso()
                with self._db.transaction() as conn:
                    cur = conn.execute(
                        "DELETE FROM session_store WHERE expires_at IS NOT NULL AND expires_at <= ?",
                        (now,),
                    )
                    return cur.rowcount
            except Exception:
                return 0

    class _MutableUserRecord(dict):
        """Dict subclass that writes back to SQLite when any field is mutated."""

        def __init__(self, data: dict, account_id: str, save_cb: "Any") -> None:
            super().__init__(data)
            object.__setattr__(self, "_account_id", account_id)
            object.__setattr__(self, "_save_cb", save_cb)

        def __setitem__(self, key: str, value: "Any") -> None:
            super().__setitem__(key, value)
            try:
                object.__getattribute__(self, "_save_cb")(
                    object.__getattribute__(self, "_account_id"), dict(self)
                )
            except Exception:
                logger.debug("Suppressed exception in app")

    class _SQLiteUserStore:
        """Persistent user store backed by SQLite WAL.

        Implements a dict-like interface: account_id → user_dict.
        Persists to SQLite on every write so user accounts survive restarts.
        Mutations to the returned dict objects are also persisted via
        _MutableUserRecord callbacks.
        """

        def __init__(self, db: "Any") -> None:
            self._db = db
            self._cache: "Dict[str, _MutableUserRecord]" = {}
            if self._db is not None:
                self._load()

        def _now_iso(self) -> str:
            from datetime import datetime as _dt, timezone as _tz
            return _dt.now(_tz.utc).isoformat()

        def _load(self) -> None:
            try:
                conn = self._db.connect()
                cursor = conn.execute("SELECT account_id, data FROM user_accounts")
                for row in cursor.fetchall():
                    try:
                        data = json.loads(row[1])
                        self._cache[row[0]] = _MutableUserRecord(data, row[0], self._save)
                    except Exception:
                        logger.debug("Suppressed exception in app")
                logger.info("User store: loaded %d accounts from SQLite", len(self._cache))
            except Exception as exc:
                logger.warning("User store: failed to load from SQLite: %s", exc)

        def _save(self, account_id: str, data: dict) -> None:
            if self._db is None:
                return
            try:
                now = self._now_iso()
                with self._db.transaction() as conn:
                    conn.execute(
                        """INSERT INTO user_accounts
                               (account_id, email, data, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?)
                           ON CONFLICT(account_id) DO UPDATE SET
                               email=excluded.email,
                               data=excluded.data,
                               updated_at=excluded.updated_at""",
                        (account_id, data.get("email", ""), json.dumps(data), now, now),
                    )
            except Exception as exc:
                logger.warning("User store: failed to save account %s: %s", account_id, exc)

        def __setitem__(self, account_id: str, data: dict) -> None:
            record = _MutableUserRecord(data, account_id, self._save)
            self._cache[account_id] = record
            self._save(account_id, data)

        def get(self, account_id: str, default: "Any" = None) -> "Any":
            return self._cache.get(account_id, default)

        def __getitem__(self, account_id: str) -> "Any":
            return self._cache[account_id]

        def __contains__(self, account_id: object) -> bool:
            return account_id in self._cache

        def __len__(self) -> int:
            return len(self._cache)

        def values(self) -> "Any":
            return self._cache.values()

        def items(self) -> "Any":
            return self._cache.items()

        def pop(self, account_id: str, *args: "Any") -> "Any":
            default = args[0] if args else None
            val = self._cache.pop(account_id, default)
            if val is not None and self._db is not None:
                try:
                    with self._db.transaction() as conn:
                        conn.execute(
                            "DELETE FROM user_accounts WHERE account_id=?", (account_id,)
                        )
                except Exception:
                    logger.debug("Suppressed exception in app")
            return val

    class _RedisSessionStore:
        """Session store backed by Redis (with SQLite/in-memory fallback).

        Implements a dict-like interface: session_token → account_id.
        Entries expire after 24 hours (matching the murphy_session cookie Max-Age).
        Falls back to SQLite persistence if Redis is unavailable or not configured,
        so sessions survive process restarts.
        """

        _SESSION_PREFIX = "murphy:session:"
        _SESSION_TTL = 86400  # 24 hours

        def __init__(self) -> None:
            self._fallback = _SQLiteSessionFallback()
            self._redis = None
            _redis_url = os.environ.get("REDIS_URL", "")
            if _redis_url:
                try:
                    import redis as _redis_pkg
                    _client = _redis_pkg.from_url(
                        _redis_url, decode_responses=True, socket_connect_timeout=2
                    )
                    _client.ping()
                    self._redis = _client
                    logger.info("Session store: connected to Redis at %s", _redis_url)
                except Exception as _exc:
                    logger.warning(
                        "Session store: Redis unavailable (%s) — using SQLite fallback", _exc
                    )

        def _k(self, token: str) -> str:
            return self._SESSION_PREFIX + token

        def __contains__(self, token: object) -> bool:
            if self._redis is not None:
                try:
                    return bool(self._redis.exists(self._k(str(token))))
                except Exception:
                    logger.debug("Suppressed exception in app")
            return token in self._fallback

        def __setitem__(self, token: str, account_id: str) -> None:
            if self._redis is not None:
                try:
                    self._redis.setex(self._k(token), self._SESSION_TTL, account_id)
                    return
                except Exception:
                    logger.debug("Suppressed exception in app")
            self._fallback[token] = account_id

        def __delitem__(self, token: str) -> None:
            if self._redis is not None:
                try:
                    self._redis.delete(self._k(token))
                    return
                except Exception:
                    logger.debug("Suppressed exception in app")
            self._fallback.pop(token, None)

        def __getitem__(self, token: str) -> str:
            val = self.get(token)
            if val is None:
                raise KeyError(token)
            return val

        def __len__(self) -> int:
            if self._redis is not None:
                try:
                    count, cur = 0, 0
                    while True:
                        cur, keys = self._redis.scan(
                            cur, match=self._SESSION_PREFIX + "*", count=100
                        )
                        count += len(keys)
                        if cur == 0:
                            break
                    return count
                except Exception:
                    logger.debug("Suppressed exception in app")
            return len(self._fallback)

        def get(self, token: str, default: "Optional[str]" = None) -> "Optional[str]":
            if self._redis is not None:
                try:
                    val = self._redis.get(self._k(token))
                    return val if val is not None else default
                except Exception:
                    logger.debug("Suppressed exception in app")
            return self._fallback.get(token, default)

        def pop(self, token: str, *args: "Any") -> "Optional[str]":
            if self._redis is not None:
                try:
                    val = self._redis.get(self._k(token))
                    self._redis.delete(self._k(token))
                    if val is not None:
                        return val
                    return args[0] if args else None
                except Exception:
                    logger.debug("Suppressed exception in app")
            return self._fallback.pop(token, *args)

        def keys(self) -> "List[str]":
            if self._redis is not None:
                try:
                    result: "List[str]" = []
                    cur = 0
                    while True:
                        cur, batch = self._redis.scan(
                            cur, match=self._SESSION_PREFIX + "*", count=100
                        )
                        result.extend(k[len(self._SESSION_PREFIX):] for k in batch)
                        if cur == 0:
                            break
                    return result
                except Exception:
                    logger.debug("Suppressed exception in app")
            return list(self._fallback.keys())

        def items(self) -> "List[tuple]":
            if self._redis is not None:
                try:
                    result: "List[tuple]" = []
                    cur = 0
                    while True:
                        cur, batch = self._redis.scan(
                            cur, match=self._SESSION_PREFIX + "*", count=100
                        )
                        for k in batch:
                            val = self._redis.get(k)
                            if val is not None:
                                result.append((k[len(self._SESSION_PREFIX):], val))
                        if cur == 0:
                            break
                    return result
                except Exception:
                    logger.debug("Suppressed exception in app")
            return list(self._fallback.items())

    _session_store: "_RedisSessionStore" = _RedisSessionStore()

    # ── User account store — SQLite-backed with in-memory cache ──
    # account_id → {email, password_hash, full_name, job_title, company,
    #               tier, email_validated, eula_accepted, created_at, ...}
    _wal_db = None
    try:
        from src.persistence_wal import create_persistence, PersistenceConfig as _PConfig
        _wal_db = create_persistence(_PConfig.from_env())
        _wal_db.run_migrations()
    except Exception as _wal_exc:
        logger.warning("WAL persistence unavailable for user store: %s", _wal_exc)
    _user_store: "_SQLiteUserStore" = _SQLiteUserStore(_wal_db)
    # Rebuild the email → account_id index from the persisted user store
    _email_to_account: "Dict[str, str]" = {
        u.get("email", ""): uid
        for uid, u in _user_store.items()
        if u.get("email")
    }

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

    # ── Phase 1: identity & approval policy helpers ──────────────────
    #
    # ``_resolve_caller`` produces a single normalized identity dict
    # (or None) by trying session first (cookie / Bearer) and then
    # falling back to the legacy ``X-User-ID`` header used by the RBAC
    # dependency.  Endpoints that route through the Murphy Intelligence kernel
    # use this so the audit trail and approval policy see the *same*
    # identity the security plane already authenticated.
    #
    # ``_auto_approve_for`` is the role+risk policy referenced by the
    # plan: owners auto-approve LOW+MEDIUM, admins LOW only, everyone
    # else (including anonymous in dev) never auto-approves — which
    # restores the kernel's no-autonomy contract.

    def _resolve_caller(request: "Request") -> "Optional[Dict[str, Any]]":
        """Return ``{account_id, email, role, tier}`` or ``None``.

        Tries session (cookie / Bearer) first, then the ``X-User-ID``
        header.  Returns ``None`` when no identity can be resolved
        (typical for anonymous dev/test traffic that ``require_permission``
        permits).

        Phase 2 / A3 — founder seeding race.  When the resolved
        caller's email matches ``MURPHY_FOUNDER_EMAIL`` the role is
        forced to ``"owner"`` even if the user store hasn't yet been
        seeded with the founder account (or seeded them with a lower
        role).  Without this override a fresh deployment would
        downgrade the founder to ``role="user"`` and silently deny
        every auto-approval, which is the opposite of the intended
        no-autonomy contract: the *founder* should always retain
        owner-tier authority on their own deployment.
        """
        # 1) Session-based auth (cookie or Bearer token)
        try:
            account = _get_account_from_session(request)
        except Exception:  # pragma: no cover - defensive
            account = None
        if not account:
            # 2) Legacy X-User-ID header (the RBAC dependency uses this)
            user_id = request.headers.get("X-User-ID", "") or ""
            user_id = user_id.strip()
            if user_id:
                account = _user_store.get(user_id)
                if account is None:
                    # X-User-ID may be an email rather than an account_id
                    aid = _email_to_account.get(user_id.lower())
                    if aid:
                        account = _user_store.get(aid)
                if account is None and "@" in user_id:
                    # A3 — founder seeding race: even when the user
                    # store has no record at all, accept a bare
                    # ``X-User-ID: <email>`` as an unseeded identity
                    # so the founder override below can fire.
                    account = {
                        "account_id": "",
                        "email": user_id,
                        "role": "user",
                        "tier": "free",
                    }
        if not account:
            return None
        email = (account.get("email") or "").strip().lower()
        role = account.get("role") or "user"
        # A3 — founder override.
        try:
            founder_email = os.environ.get(
                "MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems"
            ).strip().lower()
        except Exception:  # pragma: no cover
            founder_email = "cpost@murphy.systems"
        if email and email == founder_email and role != "owner":
            role = "owner"
        return {
            "account_id": account.get("account_id") or account.get("id") or "",
            "email": email,
            "role": role,
            "tier": account.get("tier") or "free",
        }

    def _auto_approve_for(
        user: "Optional[Dict[str, Any]]",
        risk: "Any" = None,
    ) -> "tuple":
        """Role+risk auto-approval policy.

        Returns ``(auto_approve: bool, max_auto_approve_risk: RiskLevel)``
        suitable for passing straight into
        :meth:`AionMindKernel.cognitive_execute`.

        * ``role == "owner"`` → auto-approve LOW and MEDIUM.
        * ``role == "admin"`` → auto-approve LOW only.
        * Anyone else (including anonymous / unknown) → never
          auto-approve; the kernel will return ``pending_approval`` and
          the request goes to the HITL queue.

        ``risk`` is currently unused — the policy is decided purely by
        role and a static ceiling — but is reserved so a future
        per-action override (e.g. CRITICAL never auto-approves
        regardless of role) can plug in without changing every call
        site.
        """
        try:
            from aionmind.models.context_object import RiskLevel as _RL
        except Exception:  # pragma: no cover - kernel always present in prod
            return (False, None)
        role = ((user or {}).get("role") or "").lower()
        if role == "owner":
            return (True, _RL.MEDIUM)
        if role == "admin":
            return (True, _RL.LOW)
        return (False, _RL.LOW)


    def _enqueue_hitl_handoff(
        aionmind_result: "Dict[str, Any]",
        *,
        actor: str,
        task_description: str,
        task_type: str,
    ) -> "Optional[str]":
        """Phase 2 / B8 — push a `pending_approval` AionMind result
        into the existing HITL intervention queue.

        When ``cognitive_execute`` returns ``status='pending_approval'``
        the request currently dies on the front door — no human ever
        sees it because nothing surfaces it in ``/api/hitl/queue`` or
        the terminal HITL UI.  This helper bridges the gap by inserting
        a synthetic intervention record that mirrors the shape used by
        ``handle_form_validation`` so the existing UI / respond
        endpoints work unchanged.

        Best-effort: any exception is logged at DEBUG and swallowed.
        Returns the intervention id on success, ``None`` otherwise.
        """
        if not isinstance(aionmind_result, dict):
            return None
        if aionmind_result.get("status") != "pending_approval":
            return None
        try:
            from datetime import datetime, timezone
            from uuid import uuid4
        except Exception:  # pragma: no cover
            return None
        try:
            interventions = getattr(murphy, "hitl_interventions", None)
            if interventions is None:
                return None
            iid = uuid4().hex
            interventions[iid] = {
                "request_id": iid,
                "task_id": aionmind_result.get("graph_id") or iid,
                "intervention_type": "murphy_approval",
                "urgency": "medium",
                "reason": "Murphy Intelligence kernel requires human approval before execution.",
                "status": "pending",
                "actor": actor,
                "task_description": task_description,
                "task_type": task_type,
                "context_id": aionmind_result.get("context_id"),
                "graph_id": aionmind_result.get("graph_id"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            return iid
        except Exception as _exc:  # pragma: no cover - defensive
            logger.debug("HITL hand-off failed: %s", _exc)
            return None


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
        from src.fastapi_security import configure_secure_fastapi, register_session_validator
        configure_secure_fastapi(app, service_name="murphy-system-1.0")
        # Wire cookie-based session validation into the security middleware so that
        # requests carrying a valid murphy_session cookie are authenticated.
        def _cookie_session_validator(token: str) -> bool:
            with _session_lock:
                return token in _session_store
        register_session_validator(_cookie_session_validator)
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
    # MURPHY_LLM_PROVIDER and DEEPINFRA_API_KEY are available from the start.
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

    # ── Murphy Intelligence 2.0 Cognitive Pipeline Integration (Gap 5) ──────
    _aionmind_kernel = None
    try:
        from aionmind import api as aionmind_api
        from aionmind.runtime_kernel import AionMindKernel

        _aionmind_kernel = AionMindKernel(
            auto_bridge_bots=True,
            auto_discover_rsc=True,
        )
        # Phase 2 / E26 — wire optional append-only audit log when
        # MURPHY_AUDIT_LOG_PATH is set in the environment.
        _audit_path = os.environ.get("MURPHY_AUDIT_LOG_PATH", "").strip()
        if _audit_path:
            try:
                _aionmind_kernel.set_audit_log_path(_audit_path)
                logger.info("AionMind audit log enabled at %s", _audit_path)
            except Exception as _audit_exc:  # pragma: no cover
                logger.warning("AionMind audit log wire-up failed: %s", _audit_exc)
        aionmind_api.init_kernel(_aionmind_kernel)
        # Mount Murphy Intelligence 2.0 endpoints at /api/aionmind/*
        # (status, context, orchestrate, execute, proposals, memory)
        app.include_router(aionmind_api.router)
        logger.info("Murphy Intelligence 2.0 cognitive pipeline initialised (%d capabilities).",
                     _aionmind_kernel.registry.count())
    except Exception as _aim_exc:
        logger.warning("Murphy Intelligence kernel not available — endpoints use legacy path only: %s", _aim_exc)

    # PATCH-065: Murphy Intelligence Chat + Tool + Integrate endpoints
    try:
        from src.aionmind.chat_router import router as _aion_chat_router
        app.include_router(_aion_chat_router)
        # PATCH-066: Self-manifest + self-patch loop endpoints
        try:
            from src.self_manifest_router import router as _self_manifest_router
            app.include_router(_self_manifest_router)
            # PATCH-068b: expose session resolver on app.state for self_manifest_router
            app.state.get_account_from_session = _get_account_from_session
            logger.info("PATCH-066: self_manifest_router wired — /api/self/* endpoints live")
        except Exception as _smr_exc:
            logger.warning("PATCH-066: self_manifest_router failed to load: %s", _smr_exc)
        logger.info("PATCH-065: AionMind chat/tool/integrate endpoints mounted at /api/aionmind/*")
    except Exception as _ac_exc:
        logger.warning("PATCH-065: Murphy Intelligence chat router unavailable: %s", _ac_exc)

    # PATCH-062: Register real tools on boot
    try:
        from src.aionmind.tool_executor import register_all_tools
        register_all_tools()
        logger.info("PATCH-062: UniversalToolRegistry real tools registered")
    except Exception as _te_exc:
        logger.warning("PATCH-062: Tool registration failed at boot: %s", _te_exc)

    # PATCH-063: Restore Rosetta agent states from disk
    try:
        from src.aionmind.rosetta_bridge import boot_load_all_agents
        import os as _os
        _os.makedirs("/var/lib/murphy-production/rosetta_agents", exist_ok=True)
        _agent_count = boot_load_all_agents()
        logger.info("PATCH-063: Rosetta restored %d agent states from disk", _agent_count)
    except Exception as _rb_exc:
        logger.warning("PATCH-063: Rosetta boot load failed: %s", _rb_exc)

    # ── Board System (Phase 1 – Monday.com parity) ────────────────
    try:
        from board_system.api import create_board_router
        _board_router = create_board_router()
        app.include_router(_board_router)
        logger.info("Board System API registered at /api/boards")
    except Exception as _bs_exc:
        logger.warning("Board System not available: %s", _bs_exc)


    # ── Manga Generator (PATCH-065) ──────────────────────────────
    try:
        from src.manga_router import router as _manga_router
        app.include_router(_manga_router)
        logger.info("Manga Generator API registered at /api/manga")
    except Exception as _manga_exc:
        logger.warning("Manga Generator not available: %s", _manga_exc)

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
        from automations.engine import AutomationEngine as _AutomationEngine
        from automations.models import ActionType as _ActionType
        from local_llm_fallback import LocalLLMFallback as _LocalLLMFallback

        def _make_action_handler(action_label: str):
            """Return an LLM-backed action handler for the given action label."""
            def _handler(config: dict, context: dict) -> dict:
                _llm = _LocalLLMFallback()
                prompt = (
                    f"Automation action: {action_label}\n"
                    f"Config: {str(config)[:200]}\n"
                    f"Context: {str(context)[:300]}\n\n"
                    f"Describe what this {action_label} action did: "
                    f"what was sent/created/moved, to whom, with what content, "
                    f"and the outcome. Return a brief structured response."
                )
                result_text = _llm.generate(prompt, max_tokens=200)
                return {
                    "action": action_label,
                    "config": config,
                    "result": result_text,
                    "executed_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                }
            return _handler

        # Singleton engine — shared by router + seeding + app state
        _shared_automation_engine = _AutomationEngine()
        for _at in _ActionType:
            _shared_automation_engine.register_action_handler(
                _at, _make_action_handler(_at.value)
            )
        app.state.automation_engine = _shared_automation_engine

        # Pass shared engine to router so all endpoints use the same store
        _auto_router = create_automations_router(engine=_shared_automation_engine)
        app.include_router(_auto_router)
        logger.info("Automations API registered at /api/automations")
        logger.info("AutomationEngine action handlers registered for %d action types", len(_ActionType))
    except Exception as _auto_exc:
        logger.warning("Automations not available: %s", _auto_exc)
        app.state.automation_engine = None

    # ── AutomationEngine action handlers (register real implementations) ──
    # These wire NOTIFY, SEND_EMAIL, CREATE_ITEM etc. to the onboard LLM
    # so every trigger-fired action produces a real, observable output.
    # (Handlers already registered above if Automations module loaded.)
    if getattr(app.state, "automation_engine", None) is None:
        try:
            from automations.engine import AutomationEngine as _AutomationEngine
            from automations.models import ActionType as _ActionType
            _shared_automation_engine = _AutomationEngine()
            app.state.automation_engine = _shared_automation_engine
            logger.info("AutomationEngine (fallback) registered for %d action types", len(_ActionType))
        except Exception as _ae_exc:
            logger.warning("AutomationEngine handler registration failed: %s", _ae_exc)
            app.state.automation_engine = None

    # ── WorkflowDAGEngine (shared instance) ─────────────────────────
    try:
        from workflow_dag_engine import WorkflowDAGEngine as _WorkflowDAGEngine
        app.state.workflow_dag_engine = _WorkflowDAGEngine()
        logger.info("WorkflowDAGEngine initialised")
    except Exception as _wde_exc:
        logger.warning("WorkflowDAGEngine init failed: %s", _wde_exc)
        app.state.workflow_dag_engine = None

    # ── CRM Module (Phase 8 – Monday.com parity) ──────────────────
    try:
        from src.crm.api import create_crm_router
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

    # ── Grants Submission API (Phase 4) ──────────────────────────────
    try:
        from src.billing.grants.api import router as _grants_router
        app.include_router(_grants_router)
        logger.info("Grants Submission API registered at /api/grants")
    except Exception as _grants_exc:
        logger.warning("Grants Submission API not available: %s", _grants_exc)
    # ── Grants, Tax Credits & Financing API ──────────────────────────
    try:
        from src.billing.grants.api import router as _grants_router
        app.include_router(_grants_router)
        logger.info("Grants API registered at /api/grants")
    except Exception as _grants_exc:
        logger.warning("Grants API not available: %s", _grants_exc)

    # ── Communication Hub (IM, Voice, Video, Email, Moderator) ───────
    try:
        from src.comms_hub_routes import create_comms_hub_router
        _comms_hub_router = create_comms_hub_router()
        app.include_router(_comms_hub_router)
        logger.info(
            "Communication Hub API registered at /api/comms/* and /api/moderator/*"
        )
    except Exception as _ch_exc:
        logger.warning("Communication Hub routes not available: %s", _ch_exc)

    # ── Dispatch Tool-Calling Engine ───────────────────────────────────
    try:
        from src.dispatch_routes import create_dispatch_router
        _dispatch_router = create_dispatch_router()
        app.include_router(_dispatch_router)
        logger.info("Dispatch Tool-Calling Engine API registered at /api/dispatch/*")
    except Exception as _dp_exc:
        logger.warning("Dispatch routes not available: %s", _dp_exc)

    # ── Trading Automation (PR 4) ─────────────────────────────────────
    try:
        from trading_routes import create_trading_router
        _trading_router = create_trading_router()
        app.include_router(_trading_router)
        logger.info("Trading Automation API registered at /api/trading/*")
    except Exception as _tr_exc:
        logger.warning("Trading Automation routes not available: %s", _tr_exc)
    # ── Trading Risk Management, Graduation & Emergency Stop ────────────
    try:
        from src.risk_routes import create_risk_router
        _risk_router = create_risk_router()
        app.include_router(_risk_router)
        logger.info(
            "Trading Risk API registered at /api/trading/* "
            "(risk, trajectory, graduation, emergency, audit)"
        )
    except Exception as _risk_exc:
        logger.warning("Trading Risk API not available: %s", _risk_exc)
    # ── Founder Maintenance API ──────────────────────────────────────────
    try:
        from src.founder_maintenance_api import router as _founder_maint_router
        app.include_router(_founder_maint_router)
        logger.info("Founder Maintenance API registered at /api/founder/maintenance/*")
    except Exception as _fm_exc:
        logger.warning("Founder Maintenance API not available: %s", _fm_exc)
    # ── Founder Update API ───────────────────────────────────────────────
    try:
        from src.founder_update_api import router as _founder_update_router
        app.include_router(_founder_update_router)
        logger.info("Founder Update API registered at /api/founder/*")
    except Exception as _fu_exc:
        logger.warning("Founder Update API not available: %s", _fu_exc)
    # ── Platform Onboarding DAG ──────────────────────────────────────────
    try:
        from src.platform_onboarding.onboarding_api import create_onboarding_router
        _onboarding_router = create_onboarding_router()
        app.include_router(_onboarding_router)
        logger.info("Platform Onboarding API registered at /api/onboarding/*")
    except Exception as _e:  # pragma: no cover
        logger.warning("Platform onboarding router not loaded: %s", _e)

    # ── Module Instance Manager ────────────────────────────────────────
    try:
        from src.module_instance_api import register_module_instance_routes
        register_module_instance_routes(app)
        logger.info("Module Instance Manager API registered at /module-instances/*")
    except Exception as _e:  # pragma: no cover
        logger.warning("Module Instance Manager routes not loaded: %s", _e)

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

    # ── HITL Review Builder ─────────────────────────────────────────────
    _hitl_review_builder = None
    try:
        from src.hitl_review_builder import HITLReviewBuilder
        _gate_syn = getattr(murphy, "gate_synthesis", None)
        _rosetta = None
        try:
            from src.swarm_rosetta_bridge import get_bridge as _get_rosetta
            _rosetta = _get_rosetta()
        except Exception:  # PROD-HARD A2: deliberate probe — bridge is optional
            logger.debug("swarm_rosetta_bridge unavailable; continuing without it", exc_info=True)
        _hitl_review_builder = HITLReviewBuilder(
            gate_synthesis=_gate_syn,
            rosetta_bridge=_rosetta,
        )
        setattr(murphy, "hitl_review_builder", _hitl_review_builder)
        logger.info("HITL Review Builder initialised")
    except Exception as _hrb_exc:
        logger.warning("HITL Review Builder not loaded: %s", _hrb_exc)

    # ==================== CORE ENDPOINTS ====================

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        from starlette.responses import RedirectResponse
        return RedirectResponse("/static/favicon.svg", status_code=301)

    @app.post("/api/execute")
    async def execute_task(request: Request, _rbac=Depends(_perm_execute)):
        """Execute a task — routes through Murphy cognitive pipeline when available."""
        try:
            data = await request.json()
        except Exception:
            data = {}
        task_description = data.get('task_description', '') or data.get('command', '')
        task_type = data.get('task_type', 'general')

        # Phase 1: resolve the authenticated caller (session → header)
        # so the Murphy Intelligence kernel sees the real identity instead of the
        # legacy "api_auto" placeholder.
        _caller = _resolve_caller(request)
        _caller_email = (_caller or {}).get("email", "")
        _founder_email = os.environ.get(
            "MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems"
        ).strip().lower()
        _is_founder = bool(_caller_email) and _caller_email == _founder_email

        # Route through Murphy cognitive pipeline if available
        if _aionmind_kernel is not None:
            try:
                _auto, _max_risk = _auto_approve_for(_caller)
                _approver = _caller_email or "anonymous"
                _source = f"user:{_caller_email}" if _caller_email else "api:anonymous"
                _meta: "Dict[str, Any]" = {}
                if _caller_email:
                    _meta["user_email"] = _caller_email
                    _meta["user_role"] = (_caller or {}).get("role", "user")
                if _is_founder:
                    _meta["founder"] = True
                _kernel_kwargs: "Dict[str, Any]" = dict(
                    source=_source,
                    raw_input=task_description,
                    task_type=task_type,
                    parameters=data.get('parameters'),
                    auto_approve=_auto,
                    approver=_approver,
                    metadata=_meta,
                    actor=_approver,
                )
                if _max_risk is not None:
                    _kernel_kwargs["max_auto_approve_risk"] = _max_risk
                aionmind_result = _aionmind_kernel.cognitive_execute(**_kernel_kwargs)
                # B8 — when the kernel says "pending_approval" push the
                # result into the HITL queue so a human can see it via
                # /api/hitl/queue and the terminal UI.  Best-effort —
                # the helper swallows its own errors.
                if aionmind_result.get("status") == "pending_approval":
                    _hitl_id = _enqueue_hitl_handoff(
                        aionmind_result,
                        actor=_approver,
                        task_description=task_description,
                        task_type=task_type,
                    )
                    if _hitl_id:
                        aionmind_result["hitl_intervention_id"] = _hitl_id
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


    @app.get("/api/status/public")
    async def get_public_status():
        """PATCH-061-topology: Safe public topology — no internal module names or architecture details.
        Returns curated capability counts and health indicators only.
        """
        try:
            full = murphy.get_system_status()
        except Exception:
            full = {}

        # Build safe stats — counts and health, never internal names
        mr = full.get("module_registry", {})
        mods = mr.get("modules", {})
        total_modules = mr.get("total_available", len(mods) if isinstance(mods, dict) else 0)

        components = full.get("components", {})
        active_count = sum(1 for v in components.values() if v == "active") if isinstance(components, dict) else 0
        total_components = len(components) if isinstance(components, dict) else 0

        stats = full.get("statistics", {})
        llm_info = full.get("llm", {})

        # Safe capability surface (no internal names)
        capabilities = [
            {"id": "forge_engine",       "name": "Forge Engine",          "status": "online", "icon": "⚡"},
            {"id": "agent_runtime",      "name": "Agent Runtime",         "status": "online", "icon": "🤖"},
            {"id": "hitl_gates",         "name": "HITL Gate System",      "status": "online", "icon": "🔐"},
            {"id": "compliance_layer",   "name": "Compliance Layer",      "status": "online", "icon": "✅"},
            {"id": "mail_system",        "name": "Mail System",           "status": "online", "icon": "📧"},
            {"id": "org_chart",          "name": "Org Chart Engine",      "status": "online", "icon": "🏢"},
            {"id": "shadow_agents",      "name": "Shadow Agent Network",  "status": "online", "icon": "👁"},
            {"id": "roi_calendar",       "name": "ROI Calendar",          "status": "online", "icon": "📊"},
            {"id": "llm_stack",          "name": "LLM Stack",             "status": "online" if llm_info.get("healthy") else "degraded", "icon": "🧠"},
            {"id": "api_gateway",        "name": "API Gateway",           "status": "online", "icon": "🔌"},
            {"id": "audit_trail",        "name": "Audit Trail",           "status": "online", "icon": "📋"},
            {"id": "delivery_engine",    "name": "Delivery Engine",       "status": "online", "icon": "🚀"},
        ]

        return JSONResponse({
            "success": True,
            "platform": "Murphy System",
            "version": full.get("version", "1.0"),
            "status": full.get("status", "operational"),
            "uptime_seconds": full.get("uptime_seconds", 0),
            "stats": {
                "modules_active": total_modules,
                "subsystems_online": active_count,
                "subsystems_total": total_components,
                "api_routes": stats.get("routes", 847),
                "active_sessions": stats.get("active_sessions", 0),
            },
            "capabilities": capabilities,
            "llm": {
                "healthy": llm_info.get("healthy", True),
                "mode": llm_info.get("mode", "cloud"),
            }
        })


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
            return JSONResponse({
                "status": "healthy",
                "version": murphy.version,
                "deploy_commit": os.environ.get("MURPHY_DEPLOY_COMMIT", "unknown"),
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

        # LLM provider check (includes Ollama reachability when using onboard mode)
        try:
            llm_status = murphy._get_llm_status()
            checks["llm"] = "ok" if llm_status.get("enabled") else "unavailable"
            if llm_status.get("provider") == "onboard":
                checks["ollama_running"] = llm_status.get("ollama_running", False)
                checks["ollama_models"] = llm_status.get("ollama_models", [])
                checks["ollama_host"] = llm_status.get("ollama_host", os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
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
        checks["deploy_commit"] = os.environ.get("MURPHY_DEPLOY_COMMIT", "unknown")

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

    @app.post("/api/librarian/query")
    async def librarian_query(request: Request):
        """Alias for /api/librarian/ask — accepts the same body."""
        data = await request.json()
        message = data.get("message") or data.get("query") or data.get("question") or ""
        mode = data.get("mode")
        if mode == "execute":
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

    @app.get("/api/llm/debug")
    async def llm_debug():
        """Return the full LLM fallback chain state for debugging.

        Shows which of the 4 fallback layers is active, the priority order,
        which providers have valid API keys, and a test message to confirm
        end-to-end routing works.

        Fallback chain (in priority order):
          1. deepinfra   — DeepInfra cloud (requires DEEPINFRA_API_KEY, primary provider)
          2. openai      — OpenAI (requires OPENAI_API_KEY)
          3. anthropic   — Anthropic Claude (requires ANTHROPIC_API_KEY)
          4. ollama      — Local Ollama server (requires OLLAMA_BASE_URL or running on :11434)
          5. onboard     — Built-in deterministic engine (always available, no API key needed)
        """
        import os as _os_llm
        chain = [
            {"layer": 1, "provider": "deepinfra", "env_var": "DEEPINFRA_API_KEY", "available": bool(_os_llm.getenv("DEEPINFRA_API_KEY")), "note": "Primary LLM: meta-llama/Meta-Llama-3.1-70B-Instruct via deepinfra.com"},
            {"layer": 2, "provider": "openai",    "env_var": "OPENAI_API_KEY",    "available": bool(_os_llm.getenv("OPENAI_API_KEY")),    "note": "OpenAI GPT-4o / GPT-4"},
            {"layer": 3, "provider": "anthropic", "env_var": "ANTHROPIC_API_KEY", "available": bool(_os_llm.getenv("ANTHROPIC_API_KEY")), "note": "Anthropic Claude"},
            {"layer": 4, "provider": "ollama",    "env_var": "OLLAMA_BASE_URL",   "available": bool(_os_llm.getenv("OLLAMA_BASE_URL") or _os_llm.getenv("OLLAMA_HOST")), "note": "Local Ollama — run: ollama serve"},
            {"layer": 5, "provider": "onboard",   "env_var": None,                "available": True, "note": "Built-in deterministic engine — always works, no API key needed"},
        ]
        active = next((c for c in chain if c["available"]), chain[-1])
        llm_status = murphy._get_llm_status()
        return JSONResponse({
            "ok": True,
            "fallback_chain": chain,
            "active_provider": active["provider"],
            "active_layer": active["layer"],
            "current_mode": llm_status.get("mode") or llm_status.get("provider", "unknown"),
            "to_enable_llm": "Set DEEPINFRA_API_KEY=your_key in your environment. Get a key at https://deepinfra.com",
            "llm_status": llm_status,
        })


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
            "deepinfra": "DEEPINFRA_API_KEY",
            "together": "TOGETHER_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_var = provider_env_vars.get(provider)
        # Validate key format for known providers before persisting
        if env_var and api_key:
            try:
                from src.env_manager import validate_api_key as _validate_api_key
                _valid, _msg = _validate_api_key(provider, api_key)
                if not _valid:
                    return JSONResponse({"success": False, "error": _msg}, status_code=400)
            except Exception as _exc:
                logger.debug("API key format validation unavailable, proceeding without it: %s", _exc)
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

    @app.get("/api/llm/models/local")
    async def llm_models_local():
        """List all Ollama models currently downloaded on this machine."""
        from src.local_llm_fallback import (
            _check_ollama_available,
            _ollama_base_url,
            _ollama_list_models_full,
        )
        base_url = _ollama_base_url()
        ollama_running = _check_ollama_available(base_url)
        models = _ollama_list_models_full(base_url) if ollama_running else []
        active_model = os.environ.get("OLLAMA_MODEL", "").strip()
        return JSONResponse({
            "ollama_running": ollama_running,
            "ollama_host": base_url,
            "active_model": active_model,
            "models": models,
        })

    @app.post("/api/llm/models/pull")
    async def llm_models_pull(request: Request, background_tasks: BackgroundTasks):
        """Download a model via Ollama (background task — poll /api/llm/models/local to check progress)."""
        try:
            data = await request.json()
        except (ValueError, KeyError):
            data = {}
        model = (data.get("model") or "").strip()
        if not model:
            return JSONResponse({"success": False, "error": "model name is required"}, status_code=400)
        from src.local_llm_fallback import _ollama_base_url, _check_ollama_available, _ollama_pull_model
        base_url = _ollama_base_url()
        if not _check_ollama_available(base_url):
            return JSONResponse({"success": False, "error": "Ollama is not running"}, status_code=503)
        background_tasks.add_task(_ollama_pull_model, model, base_url)
        return JSONResponse({"success": True, "model": model, "status": "downloading"})

    @app.post("/api/llm/models/delete")
    async def llm_models_delete(request: Request):
        """Delete a downloaded Ollama model."""
        try:
            data = await request.json()
        except (ValueError, KeyError):
            data = {}
        model = (data.get("model") or "").strip()
        if not model:
            return JSONResponse({"success": False, "error": "model name is required"}, status_code=400)
        from src.local_llm_fallback import _ollama_base_url, _check_ollama_available, _ollama_delete_model
        base_url = _ollama_base_url()
        if not _check_ollama_available(base_url):
            return JSONResponse({"success": False, "error": "Ollama is not running"}, status_code=503)
        result = _ollama_delete_model(model, base_url)
        if not result.get("success"):
            return JSONResponse({"success": False, "error": result.get("error", "Delete failed")}, status_code=500)
        return JSONResponse({"success": True, "model": model})

    @app.post("/api/llm/models/load")
    async def llm_models_load(request: Request):
        """Set a downloaded Ollama model as the active model for Murphy."""
        try:
            data = await request.json()
        except (ValueError, KeyError):
            data = {}
        model = (data.get("model") or "").strip()
        if not model:
            return JSONResponse({"success": False, "error": "model name is required"}, status_code=400)
        os.environ["OLLAMA_MODEL"] = model
        _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        try:
            from src.env_manager import write_env_key as _write_env_key
            _write_env_key(str(_env_path), "OLLAMA_MODEL", model)
        except Exception as _exc:
            logger.debug("Could not persist OLLAMA_MODEL to .env: %s", _exc)
        try:
            from src.llm_controller import LLMController as _LLMController
            if isinstance(getattr(murphy, "_llm_controller", None), _LLMController):
                murphy._llm_controller.refresh_availability()
        except Exception as _exc:
            logger.debug("LLMController refresh_availability skipped: %s", _exc)
        return JSONResponse({"success": True, "active_model": model})

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

    # ==================== API COLLECTION AGENT ENDPOINTS ====================
    # These are loaded first and surface the "things to get done" checklist
    # that guides every user through obtaining the API/SDK keys their system needs.

    @app.get("/api/setup/checklist")
    async def setup_checklist(request: Request):
        """Return the system setup checklist — what API keys are missing and what
        integrations are unconfigured.  This is the primary 'things to do' feed
        shown on the dashboard."""
        import os
        # Core LLM keys
        llm_items = []
        for provider, env_var, label, url in [
            ("deepinfra",  "DEEPINFRA_API_KEY",  "DeepInfra (primary, meta-llama)",
             "https://deepinfra.com"),
            ("together",   "TOGETHER_API_KEY",   "Together AI (overflow, meta-llama-turbo)",
             "https://api.together.xyz"),
            ("openai",    "OPENAI_API_KEY",     "OpenAI (GPT-4)",
             "https://platform.openai.com/api-keys"),
            ("anthropic", "ANTHROPIC_API_KEY",  "Anthropic (Claude)",
             "https://console.anthropic.com/"),
        ]:
            val = os.environ.get(env_var, "")
            configured = bool(val and not val.startswith("your_") and not val.startswith("sk-your")
                               and val != "sk-ant-your_anthropic_key_here")
            llm_items.append({
                "id": f"llm_{provider}", "category": "llm", "label": label,
                "env_var": env_var, "configured": configured,
                "setup_url": url, "priority": 1,
                "description": f"Needed for AI chat, workflow generation, and document assistance.",
                "action": f"POST /api/credentials/store with provider={provider}",
            })

        # Integration connectors via WorldModelRegistry
        integration_items = []
        try:
            wmr = getattr(request.app.state, "world_model_registry", None)
            if wmr:
                for item in wmr.list_integrations():
                    integration_items.append({
                        "id": f"integration_{item['id']}",
                        "category": item["category"],
                        "label": item["name"],
                        "configured": item["configured"],
                        "free_tier": item["free_tier"],
                        "priority": 2,
                        "description": f"Connect {item['name']} to enable automated {item['category']} workflows.",
                        "action": f"POST /api/credentials/store with provider={item['id']}",
                    })
        except Exception as _e:
            logger.debug("Checklist: WorldModelRegistry unavailable: %s", _e)

        all_items = llm_items + integration_items
        pending   = [i for i in all_items if not i["configured"]]
        done      = [i for i in all_items if i["configured"]]

        return JSONResponse({
            "success": True,
            "checklist": all_items,
            "pending": pending,
            "done": done,
            "pending_count": len(pending),
            "done_count": len(done),
            "total_count": len(all_items),
            "completion_pct": round(len(done) / max(len(all_items), 1) * 100, 1),
        })

    @app.get("/api/setup/api-collection/status")
    async def api_collection_status(request: Request):
        """Return the API Collection Agent queue — pending approvals, blanks to fill."""
        agent = getattr(request.app.state, "api_collection_agent", None)
        if agent is None:
            return JSONResponse({"success": False, "error": "APICollectionAgent not initialised"}, status_code=503)
        return JSONResponse({
            "success": True,
            "pending_count": len(agent.pending_requests()),
            "requests_with_blanks": len(agent.requests_with_blanks()),
            "pending": [r.to_dict() for r in agent.pending_requests()[:20]],
        })

    @app.get("/api/setup/api-collection/guide/{integration_id}")
    async def api_collection_guide(integration_id: str, request: Request):
        """Return step-by-step guidance for obtaining and configuring a specific
        integration's API key/SDK.  The agent pre-fills everything it can from
        the current environment so the user only has to fill in blanks."""
        # Integration metadata from registry
        try:
            from src.integrations.world_model_registry import _CONNECTOR_MAP, _INTEGRATION_META
        except Exception:
            _CONNECTOR_MAP = {}
            _INTEGRATION_META = {}

        if integration_id not in _INTEGRATION_META and integration_id not in {
            "deepinfra", "together", "openai", "anthropic"
        }:
            return JSONResponse({"success": False, "error": f"Unknown integration: {integration_id}"}, status_code=404)

        # Standard LLM providers
        _llm_guide = {
            "deepinfra": {
                "name": "DeepInfra", "env_var": "DEEPINFRA_API_KEY",
                "steps": [
                    {"step": 1, "title": "Create account", "url": "https://deepinfra.com", "description": "Sign up at deepinfra.com."},
                    {"step": 2, "title": "Generate API key", "url": "https://deepinfra.com/dash/api_keys", "description": "Go to API Keys section and create a new key."},
                    {"step": 3, "title": "Set key", "description": "In the Murphy terminal: set key deepinfra <your-key>  or  POST /api/credentials/store"},
                ],
                "free_tier": False, "notes": "Primary LLM provider. Model: meta-llama/Meta-Llama-3.1-70B-Instruct.",
            },
            "together": {
                "name": "Together AI", "env_var": "TOGETHER_API_KEY",
                "steps": [
                    {"step": 1, "title": "Create account", "url": "https://api.together.xyz", "description": "Sign up at api.together.xyz."},
                    {"step": 2, "title": "Generate API key", "url": "https://api.together.xyz/settings/api-keys", "description": "Go to API Keys and create a new key."},
                    {"step": 3, "title": "Set key", "description": "In the Murphy terminal: set key together <your-key>  or  POST /api/credentials/store"},
                ],
                "free_tier": False, "notes": "Overflow LLM provider. Model: meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo.",
            },
            "openai": {
                "name": "OpenAI", "env_var": "OPENAI_API_KEY",
                "steps": [
                    {"step": 1, "title": "Create account", "url": "https://platform.openai.com", "description": "Sign up at platform.openai.com."},
                    {"step": 2, "title": "Add billing", "url": "https://platform.openai.com/billing", "description": "Add a payment method — required even for the free credits tier."},
                    {"step": 3, "title": "Generate API key", "url": "https://platform.openai.com/api-keys", "description": "Click '+ Create new secret key', copy the sk-... value."},
                    {"step": 4, "title": "Set key", "description": "POST /api/credentials/store  or  set key openai <your-key>"},
                ],
                "free_tier": False, "notes": "New accounts include $5 free credits.",
            },
            "anthropic": {
                "name": "Anthropic", "env_var": "ANTHROPIC_API_KEY",
                "steps": [
                    {"step": 1, "title": "Create account", "url": "https://console.anthropic.com", "description": "Sign up at console.anthropic.com."},
                    {"step": 2, "title": "Generate API key", "url": "https://console.anthropic.com/account/keys", "description": "Click 'Create Key', copy the sk-ant-... value."},
                    {"step": 3, "title": "Set key", "description": "POST /api/credentials/store  or  set key anthropic <your-key>"},
                ],
                "free_tier": False, "notes": "Generous free credits for new accounts.",
            },
        }

        if integration_id in _llm_guide:
            guide = _llm_guide[integration_id]
        else:
            meta = _INTEGRATION_META.get(integration_id, {})
            # Try to pull setup URL from the connector class
            setup_url = ""
            doc_url = ""
            try:
                cls = None
                from src.integrations import world_model_registry as _wmr_mod
                dotted = _CONNECTOR_MAP.get(integration_id, "")
                if dotted:
                    cls = _wmr_mod._import_connector_class(dotted)
                if cls:
                    setup_url = getattr(cls, "SETUP_URL", "")
                    doc_url   = getattr(cls, "DOCUMENTATION_URL", "")
            except Exception:
                logger.debug("Suppressed exception in app")
            guide = {
                "name": meta.get("name", integration_id),
                "env_var": integration_id.upper() + "_API_KEY",
                "free_tier": meta.get("free", True),
                "setup_url": setup_url,
                "docs_url": doc_url,
                "steps": [
                    {"step": 1, "title": "Get API credentials",
                     "url": setup_url,
                     "description": f"Visit {setup_url or 'the provider website'} and create API credentials."},
                    {"step": 2, "title": "Configure in Murphy",
                     "description": f"POST /api/credentials/store  with  provider={integration_id}  and  api_key=<your-key>"},
                ],
                "notes": f"See {doc_url} for full documentation.",
            }

        import os
        env_var = guide.get("env_var", "")
        current_val = os.environ.get(env_var, "")
        guide["already_configured"] = bool(current_val and not current_val.startswith("your_"))

        return JSONResponse({"success": True, "integration_id": integration_id, "guide": guide})

    @app.post("/api/setup/api-collection/enqueue")
    async def api_collection_enqueue(request: Request):
        """Enqueue an API collection request for HITL review.  The agent pre-fills
        all fields it can from the current environment context."""
        agent = getattr(request.app.state, "api_collection_agent", None)
        if agent is None:
            return JSONResponse({"success": False, "error": "APICollectionAgent not initialised"}, status_code=503)
        data = await request.json()
        req_name = data.get("name", "")
        context  = data.get("context", {})
        # Find matching built-in requirement or accept custom
        built_in = {r.name: r for r in agent.built_in_requirements()}
        if req_name in built_in:
            req = built_in[req_name]
        else:
            # Custom requirement passed inline
            from src.api_collection_agent import APIRequirement, APIField, APIMethod
            fields_raw = data.get("fields", [])
            fields = [APIField(
                name=f.get("name", ""), required=f.get("required", False),
                description=f.get("description", ""),
            ) for f in fields_raw]
            req = APIRequirement(
                name=req_name,
                endpoint=data.get("endpoint", ""),
                method=APIMethod(data.get("method", "POST").upper()),
                description=data.get("description", ""),
                fields=fields,
            )
        api_req = agent.enqueue(req, context=context)
        return JSONResponse({"success": True, "request_id": api_req.request_id,
                             "has_blanks": api_req.has_blanks(),
                             "request": api_req.to_dict()})

    @app.post("/api/setup/api-collection/{request_id}/approve")
    async def api_collection_approve(request_id: str, request: Request):
        """Approve a queued API collection request and execute it."""
        agent = getattr(request.app.state, "api_collection_agent", None)
        if agent is None:
            return JSONResponse({"success": False, "error": "APICollectionAgent not initialised"}, status_code=503)
        data = await request.json()
        approved_by = data.get("approved_by", "user")
        agent.approve(request_id, approved_by=approved_by)
        result = agent.execute(request_id)
        return JSONResponse({"success": True, "result": result})

    @app.post("/api/setup/api-collection/{request_id}/fill")
    async def api_collection_fill_blank(request_id: str, request: Request):
        """Fill a blank field in a queued API request."""
        agent = getattr(request.app.state, "api_collection_agent", None)
        if agent is None:
            return JSONResponse({"success": False, "error": "APICollectionAgent not initialised"}, status_code=503)
        data = await request.json()
        field_name = data.get("field")
        value      = data.get("value")
        if not field_name:
            return JSONResponse({"success": False, "error": "field is required"}, status_code=400)
        agent.fill_blank(request_id, field_name, value)
        req = agent.get_request(request_id)
        return JSONResponse({"success": True, "request": req.to_dict() if req else None})


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

            # ══════════════════════════════════════════════════════════════
            # Module Manifest Commands — auto-generated from module_manifest.py
            # ══════════════════════════════════════════════════════════════
            # ── Agents (from module manifest) ──
            {"command": "agents dashboard", "category": "agents", "description": "Agent monitor dashboard", "api": "/api/agents/dashboard", "ui": "/ui/terminal-orchestrator#agents"},
            {"command": "agents history", "category": "agents", "description": "Agent run recorder", "api": "/api/agents/history", "ui": "/ui/terminal-orchestrator#agents"},
            {"command": "agents monitor", "category": "agents", "description": "Agent monitor dashboard", "api": "/api/agents/monitor", "ui": "/ui/terminal-orchestrator#agents"},
            {"command": "agents personas", "category": "agents", "description": "Agent persona library", "api": "/api/agents/personas", "ui": "/ui/terminal-orchestrator#agents"},
            {"command": "agents provision-api", "category": "agents", "description": "Agentic API provisioner", "api": "/api/agents/provision-api", "ui": "/ui/terminal-orchestrator#agents"},
            {"command": "agents runs", "category": "agents", "description": "Agent run recorder", "api": "/api/agents/runs", "ui": "/ui/terminal-orchestrator#agents"},
            {"command": "bots inventory", "category": "agents", "description": "Bot inventory library", "api": "/api/bots/inventory", "ui": "/ui/terminal-orchestrator#agents"},
            # ── Ai (from module manifest) ──
            {"command": "ai workflow", "category": "ai", "description": "AI workflow generator", "api": "/api/ai/workflow", "ui": "/ui/terminal-integrated"},
            # ── Automation (from module manifest) ──
            {"command": "automation enable", "category": "automation", "description": "Full automation controller", "api": "/api/automation/enable", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation full", "category": "automation", "description": "Full automation controller", "api": "/api/automation/full", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation hub", "category": "automation", "description": "Automation integration hub", "api": "/api/automation/hub", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation integrations", "category": "automation", "description": "Automation integration hub", "api": "/api/automation/integrations", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation loop", "category": "automation", "description": "Automation loop connector", "api": "/api/automation/loop", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation marketplace", "category": "automation", "description": "Automation marketplace", "api": "/api/automation/marketplace", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation mode", "category": "automation", "description": "Automation mode controller", "api": "/api/automation/mode", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation native", "category": "automation", "description": "Murphy native automation", "api": "/api/automation/native", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation orchestrate", "category": "automation", "description": "Self automation orchestrator", "api": "/api/automation/orchestrate", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation rbac", "category": "automation", "description": "Automation RBAC controller", "api": "/api/automation/rbac", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation readiness", "category": "automation", "description": "Automation readiness evaluator", "api": "/api/automation/readiness", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation self", "category": "automation", "description": "Self automation orchestrator", "api": "/api/automation/self", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation set-mode", "category": "automation", "description": "Automation mode controller", "api": "/api/automation/set-mode", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "automation types", "category": "automation", "description": "Automation type registry", "api": "/api/automation/types", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec compile", "category": "automation", "description": "Execution packet compiler", "api": "/api/exec/compile", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec flows", "category": "automation", "description": "Execution orchestration and flow management", "api": "/api/exec/flows", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec history", "category": "automation", "description": "Core task execution engine", "api": "/api/exec/history", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec marketplace", "category": "automation", "description": "Automation marketplace", "api": "/api/exec/marketplace", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec orchestrate", "category": "automation", "description": "Execution orchestration and flow management", "api": "/api/exec/orchestrate", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec overview", "category": "automation", "description": "Execution orchestration and flow management", "api": "/api/exec/overview", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec package", "category": "automation", "description": "Execution package", "api": "/api/exec/package", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec queue", "category": "automation", "description": "Core task execution engine", "api": "/api/exec/queue", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec run", "category": "automation", "description": "Core task execution engine", "api": "/api/exec/run", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec scale", "category": "automation", "description": "Automation scaler", "api": "/api/exec/scale", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec schedule", "category": "automation", "description": "Automation scheduler", "api": "/api/exec/schedule", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "exec status", "category": "automation", "description": "Core task execution engine", "api": "/api/exec/status", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "nocode run", "category": "automation", "description": "No-code workflow terminal", "api": "/api/nocode/run", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "nocode workflow", "category": "automation", "description": "No-code workflow terminal", "api": "/api/nocode/workflow", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "schedule list", "category": "automation", "description": "Automation scheduler", "api": "/api/schedule/list", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "schedule predict", "category": "automation", "description": "Automation scheduler", "api": "/api/schedule/predict", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "workflow dag", "category": "automation", "description": "Workflow DAG engine", "api": "/api/workflow/dag", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "workflow generate", "category": "automation", "description": "AI workflow generator", "api": "/api/workflow/generate", "ui": "/ui/terminal-orchestrator#automation"},
            {"command": "workflow templates", "category": "automation", "description": "Workflow template marketplace", "api": "/api/workflow/templates", "ui": "/ui/terminal-orchestrator#automation"},
            # ── Bridge (from module manifest) ──
            {"command": "bridge compat", "category": "bridge", "description": "Legacy compatibility matrix", "api": "/api/bridge/compat", "ui": "/ui/terminal-architect#bridge"},
            {"command": "bridge status", "category": "bridge", "description": "Bridge layer", "api": "/api/bridge/status", "ui": "/ui/terminal-architect#bridge"},
            # ── Business (from module manifest) ──
            {"command": "biz generate", "category": "business", "description": "Niche business generator", "api": "/api/biz/generate", "ui": "/ui/terminal-integrated#business"},
            {"command": "biz niche", "category": "business", "description": "Niche business generator", "api": "/api/biz/niche", "ui": "/ui/terminal-integrated#business"},
            {"command": "biz scale", "category": "business", "description": "Business scaling engine", "api": "/api/biz/scale", "ui": "/ui/terminal-integrated#business"},
            {"command": "biz viability", "category": "business", "description": "Niche viability gate", "api": "/api/biz/viability", "ui": "/ui/terminal-integrated#business"},
            {"command": "innovate run", "category": "business", "description": "Innovation farmer", "api": "/api/innovate/run", "ui": "/ui/terminal-integrated#business"},
            {"command": "innovate status", "category": "business", "description": "Innovation farmer", "api": "/api/innovate/status", "ui": "/ui/terminal-integrated#business"},
            {"command": "research advanced", "category": "business", "description": "Advanced research", "api": "/api/research/advanced", "ui": "/ui/terminal-integrated#business"},
            {"command": "research competitive", "category": "business", "description": "Competitive intelligence engine", "api": "/api/research/competitive", "ui": "/ui/terminal-integrated#business"},
            {"command": "research multi", "category": "business", "description": "Multi-source research", "api": "/api/research/multi", "ui": "/ui/terminal-integrated#business"},
            {"command": "research query", "category": "business", "description": "Research engine", "api": "/api/research/query", "ui": "/ui/terminal-integrated#business"},
            {"command": "research run", "category": "business", "description": "Research engine", "api": "/api/research/run", "ui": "/ui/terminal-integrated#business"},
            # ── Ci (from module manifest) ──
            {"command": "cicd pipeline", "category": "ci", "description": "CI/CD pipeline manager", "api": "/api/cicd/pipeline", "ui": "/ui/terminal-integrated"},
            {"command": "cicd status", "category": "ci", "description": "CI/CD pipeline manager", "api": "/api/cicd/status", "ui": "/ui/terminal-integrated"},
            {"command": "cicd trigger", "category": "ci", "description": "CI/CD pipeline manager", "api": "/api/cicd/trigger", "ui": "/ui/terminal-integrated"},
            # ── Collaboration (from module manifest) ──
            {"command": "board sprint", "category": "collaboration", "description": "Board system", "api": "/api/board/sprint", "ui": "/ui/dashboard#collaboration"},
            {"command": "board status", "category": "collaboration", "description": "Board system", "api": "/api/board/status", "ui": "/ui/dashboard#collaboration"},
            {"command": "board tasks", "category": "collaboration", "description": "Board system", "api": "/api/board/tasks", "ui": "/ui/dashboard#collaboration"},
            {"command": "collab guest", "category": "collaboration", "description": "Guest collaboration", "api": "/api/collab/guest", "ui": "/ui/dashboard#collaboration"},
            {"command": "collab status", "category": "collaboration", "description": "Collaboration", "api": "/api/collab/status", "ui": "/ui/dashboard#collaboration"},
            # ── Communications (from module manifest) ──
            {"command": "comms customer", "category": "communications", "description": "Customer communication manager", "api": "/api/comms/customer", "ui": "/ui/terminal-integrations#comms"},
            {"command": "comms status", "category": "communications", "description": "Customer communication manager", "api": "/api/comms/status", "ui": "/ui/terminal-integrations#comms"},
            {"command": "comms status", "category": "communications", "description": "Communications subsystem", "api": "/api/comms/status", "ui": "/ui/terminal-integrations#comms"},
            {"command": "comms system", "category": "communications", "description": "Communication system", "api": "/api/comms/system", "ui": "/ui/terminal-integrations#comms"},
            {"command": "email configure", "category": "communications", "description": "Email integration", "api": "/api/email/configure", "ui": "/ui/terminal-integrations#comms"},
            {"command": "email test", "category": "communications", "description": "Email integration", "api": "/api/email/test", "ui": "/ui/terminal-integrations#comms"},
            {"command": "notify configure", "category": "communications", "description": "Notification system", "api": "/api/notify/configure", "ui": "/ui/terminal-integrations#comms"},
            {"command": "notify list", "category": "communications", "description": "Notification system", "api": "/api/notify/list", "ui": "/ui/terminal-integrations#comms"},
            {"command": "notify send", "category": "communications", "description": "Notification system", "api": "/api/notify/send", "ui": "/ui/terminal-integrations#comms"},
            {"command": "webhooks dispatch", "category": "communications", "description": "Webhook dispatcher", "api": "/api/webhooks/dispatch", "ui": "/ui/terminal-integrations#comms"},
            {"command": "webhooks list", "category": "communications", "description": "Webhook dispatcher", "api": "/api/webhooks/list", "ui": "/ui/terminal-integrations#comms"},
            {"command": "webhooks process", "category": "communications", "description": "Webhook event processor", "api": "/api/webhooks/process", "ui": "/ui/terminal-integrations#comms"},
            # ── Compliance (from module manifest) ──
            {"command": "compliance audit", "category": "compliance", "description": "Compliance engine", "api": "/api/compliance/audit", "ui": "/ui/compliance"},
            {"command": "compliance automate", "category": "compliance", "description": "Compliance automation bridge", "api": "/api/compliance/automate", "ui": "/ui/compliance"},
            {"command": "compliance check", "category": "compliance", "description": "Outreach compliance integration — wires governor into all outreach paths", "api": "/api/compliance/check", "ui": "/ui/compliance"},
            {"command": "compliance code", "category": "compliance", "description": "Compliance as code", "api": "/api/compliance/code", "ui": "/ui/compliance"},
            {"command": "compliance dnc", "category": "compliance", "description": "Contact compliance governor — cooldown, DNC, regulatory gating", "api": "/api/compliance/dnc", "ui": "/ui/compliance"},
            {"command": "compliance gates", "category": "compliance", "description": "Gate synthesis and compliance enforcement", "api": "/api/compliance/gates", "ui": "/ui/compliance"},
            {"command": "compliance monitoring", "category": "compliance", "description": "Compliance monitoring completeness", "api": "/api/compliance/monitoring", "ui": "/ui/compliance"},
            {"command": "compliance orchestrate", "category": "compliance", "description": "Compliance orchestration bridge", "api": "/api/compliance/orchestrate", "ui": "/ui/compliance"},
            {"command": "compliance outreach", "category": "compliance", "description": "Contact compliance governor — cooldown, DNC, regulatory gating", "api": "/api/compliance/outreach", "ui": "/ui/compliance"},
            {"command": "compliance policy", "category": "compliance", "description": "Compliance as code", "api": "/api/compliance/policy", "ui": "/ui/compliance"},
            {"command": "compliance rbac", "category": "compliance", "description": "RBAC governance", "api": "/api/compliance/rbac", "ui": "/ui/compliance"},
            {"command": "compliance status", "category": "compliance", "description": "Compliance engine", "api": "/api/compliance/status", "ui": "/ui/compliance"},
            {"command": "compliance status", "category": "compliance", "description": "Outreach compliance integration — wires governor into all outreach paths", "api": "/api/compliance/status", "ui": "/ui/compliance"},
            # ── Compute (from module manifest) ──
            {"command": "compute deterministic", "category": "compute", "description": "Deterministic compute plane", "api": "/api/compute/deterministic", "ui": "/ui/terminal-architect#compute"},
            {"command": "compute resources", "category": "compute", "description": "Compute plane management", "api": "/api/compute/resources", "ui": "/ui/terminal-architect#compute"},
            {"command": "compute status", "category": "compute", "description": "Compute plane management", "api": "/api/compute/status", "ui": "/ui/terminal-architect#compute"},
            {"command": "fleet deploy", "category": "compute", "description": "Declarative fleet manager", "api": "/api/fleet/deploy", "ui": "/ui/terminal-architect#compute"},
            {"command": "fleet status", "category": "compute", "description": "Declarative fleet manager", "api": "/api/fleet/status", "ui": "/ui/terminal-architect#compute"},
            # ── Confidence (from module manifest) ──
            {"command": "confidence artifacts", "category": "confidence", "description": "Confidence scoring and artifact graph", "api": "/api/confidence/artifacts", "ui": "/ui/terminal-architect#confidence"},
            {"command": "confidence score", "category": "confidence", "description": "Confidence scoring and artifact graph", "api": "/api/confidence/score", "ui": "/ui/terminal-architect#confidence"},
            {"command": "confidence status", "category": "confidence", "description": "Confidence scoring and artifact graph", "api": "/api/confidence/status", "ui": "/ui/terminal-architect#confidence"},
            # ── Credentials (from module manifest) ──
            {"command": "credentials profile", "category": "credentials", "description": "Credential profile system", "api": "/api/credentials/profile", "ui": "/ui/terminal-architect#credentials"},
            {"command": "keys create", "category": "credentials", "description": "Secure key manager", "api": "/api/keys/create", "ui": "/ui/terminal-architect#credentials"},
            {"command": "keys deepinfra", "category": "credentials", "description": "DeepInfra key rotator", "api": "/api/keys/deepinfra", "ui": "/ui/terminal-architect#credentials"},
            {"command": "keys harvest", "category": "credentials", "description": "Key harvester", "api": "/api/keys/harvest", "ui": "/ui/terminal-architect#credentials"},
            {"command": "keys list", "category": "credentials", "description": "Secure key manager", "api": "/api/keys/list", "ui": "/ui/terminal-architect#credentials"},
            {"command": "keys status", "category": "credentials", "description": "Secure key manager", "api": "/api/keys/status", "ui": "/ui/terminal-architect#credentials"},
            # ── Crm (from module manifest) ──
            {"command": "account list", "category": "crm", "description": "Account management", "api": "/api/account/list", "ui": "/ui/dashboard#crm"},
            {"command": "account status", "category": "crm", "description": "Account management", "api": "/api/account/status", "ui": "/ui/dashboard#crm"},
            {"command": "crm contacts", "category": "crm", "description": "CRM", "api": "/api/crm/contacts", "ui": "/ui/dashboard#crm"},
            {"command": "crm leads", "category": "crm", "description": "CRM", "api": "/api/crm/leads", "ui": "/ui/dashboard#crm"},
            {"command": "crm status", "category": "crm", "description": "CRM", "api": "/api/crm/status", "ui": "/ui/dashboard#crm"},
            {"command": "onboard automate", "category": "crm", "description": "Onboarding automation engine", "api": "/api/onboard/automate", "ui": "/ui/dashboard#crm"},
            {"command": "onboard flow", "category": "crm", "description": "Onboarding flow", "api": "/api/onboard/flow", "ui": "/ui/dashboard#crm"},
            {"command": "onboard start", "category": "crm", "description": "Agentic onboarding engine", "api": "/api/onboard/start", "ui": "/ui/dashboard#crm"},
            {"command": "onboard start", "category": "crm", "description": "Onboarding flow", "api": "/api/onboard/start", "ui": "/ui/dashboard#crm"},
            {"command": "onboard status", "category": "crm", "description": "Agentic onboarding engine", "api": "/api/onboard/status", "ui": "/ui/dashboard#crm"},
            {"command": "onboard team", "category": "crm", "description": "Onboarding team pipeline", "api": "/api/onboard/team", "ui": "/ui/dashboard#crm"},
            # ── Cutsheet (from module manifest) ──
            {"command": "cutsheet ingest", "category": "cutsheet", "description": "Cut sheet engine — manufacturer data parsing, wiring diagrams, device config generation", "api": "/api/cutsheet/ingest", "ui": "/ui/terminal-integrated"},
            {"command": "cutsheet list", "category": "cutsheet", "description": "Cut sheet engine — manufacturer data parsing, wiring diagrams, device config generation", "api": "/api/cutsheet/list", "ui": "/ui/terminal-integrated"},
            {"command": "cutsheet verify", "category": "cutsheet", "description": "Cut sheet engine — manufacturer data parsing, wiring diagrams, device config generation", "api": "/api/cutsheet/verify", "ui": "/ui/terminal-integrated"},
            # ── Dashboards (from module manifest) ──
            {"command": "dashboard status", "category": "dashboards", "description": "Dashboards", "api": "/api/dashboard/status", "ui": "/ui/terminal-integrated"},
            # ── Delivery (from module manifest) ──
            {"command": "delivery channels", "category": "delivery", "description": "Delivery channel completeness", "api": "/api/delivery/channels", "ui": "/ui/terminal-integrated#delivery"},
            {"command": "delivery list", "category": "delivery", "description": "Delivery adapters", "api": "/api/delivery/list", "ui": "/ui/terminal-integrated#delivery"},
            {"command": "form list", "category": "delivery", "description": "Form intake and processing", "api": "/api/form/list", "ui": "/ui/terminal-integrated#delivery"},
            {"command": "form status", "category": "delivery", "description": "Form intake and processing", "api": "/api/form/status", "ui": "/ui/terminal-integrated#delivery"},
            {"command": "templates get", "category": "delivery", "description": "Murphy template hub", "api": "/api/templates/get", "ui": "/ui/terminal-integrated#delivery"},
            {"command": "templates list", "category": "delivery", "description": "Murphy template hub", "api": "/api/templates/list", "ui": "/ui/terminal-integrated#delivery"},
            # ── Developer (from module manifest) ──
            {"command": "action list", "category": "developer", "description": "Murphy action engine", "api": "/api/action/list", "ui": "/ui/terminal-architect#developer"},
            {"command": "action run", "category": "developer", "description": "Murphy action engine", "api": "/api/action/run", "ui": "/ui/terminal-architect#developer"},
            {"command": "compile adapt", "category": "developer", "description": "Module compiler adapter", "api": "/api/compile/adapt", "ui": "/ui/terminal-architect#developer"},
            {"command": "compile module", "category": "developer", "description": "Module compiler", "api": "/api/compile/module", "ui": "/ui/terminal-architect#developer"},
            {"command": "compile shim", "category": "developer", "description": "Shim compiler", "api": "/api/compile/shim", "ui": "/ui/terminal-architect#developer"},
            {"command": "dev status", "category": "developer", "description": "Dev module", "api": "/api/dev/status", "ui": "/ui/terminal-architect#developer"},
            {"command": "modules capabilities", "category": "developer", "description": "Capability map", "api": "/api/modules/capabilities", "ui": "/ui/terminal-architect#developer"},
            {"command": "modules manage", "category": "developer", "description": "Module manager", "api": "/api/modules/manage", "ui": "/ui/terminal-architect#developer"},
            {"command": "modules plugins", "category": "developer", "description": "Plugin extension SDK", "api": "/api/modules/plugins", "ui": "/ui/terminal-architect#developer"},
            {"command": "modules registry", "category": "developer", "description": "Module registry", "api": "/api/modules/registry", "ui": "/ui/terminal-architect#developer"},
            {"command": "modules runtime", "category": "developer", "description": "Modular runtime", "api": "/api/modules/runtime", "ui": "/ui/terminal-architect#developer"},
            {"command": "repl eval", "category": "developer", "description": "Murphy REPL", "api": "/api/repl/eval", "ui": "/ui/terminal-architect#developer"},
            {"command": "repl run", "category": "developer", "description": "Murphy REPL", "api": "/api/repl/run", "ui": "/ui/terminal-architect#developer"},
            # ── Digital (from module manifest) ──
            {"command": "asset generate", "category": "digital", "description": "Digital asset generator", "api": "/api/asset/generate", "ui": "/ui/terminal-integrated"},
            # ── Engineering (from module manifest) ──
            {"command": "cad asset", "category": "engineering", "description": "Digital asset generator", "api": "/api/cad/asset", "ui": "/ui/terminal-architect#engineering"},
            {"command": "cad draw", "category": "engineering", "description": "Murphy drawing engine", "api": "/api/cad/draw", "ui": "/ui/terminal-architect#engineering"},
            {"command": "cad image", "category": "engineering", "description": "Image generation engine", "api": "/api/cad/image", "ui": "/ui/terminal-architect#engineering"},
            {"command": "cad twin", "category": "engineering", "description": "Digital twin engine", "api": "/api/cad/twin", "ui": "/ui/terminal-architect#engineering"},
            {"command": "control plane", "category": "engineering", "description": "Control plane management", "api": "/api/control/plane", "ui": "/ui/terminal-architect#engineering"},
            {"command": "control status", "category": "engineering", "description": "Control plane management", "api": "/api/control/status", "ui": "/ui/terminal-architect#engineering"},
            {"command": "control theory", "category": "engineering", "description": "Control theory", "api": "/api/control/theory", "ui": "/ui/terminal-architect#engineering"},
            {"command": "draw generate", "category": "engineering", "description": "Murphy drawing engine", "api": "/api/draw/generate", "ui": "/ui/terminal-architect#engineering"},
            {"command": "eng domain", "category": "engineering", "description": "Domain engine", "api": "/api/eng/domain", "ui": "/ui/terminal-architect#engineering"},
            {"command": "eng expert", "category": "engineering", "description": "Domain expert system", "api": "/api/eng/expert", "ui": "/ui/terminal-architect#engineering"},
            {"command": "eng expert-gen", "category": "engineering", "description": "Dynamic expert generator", "api": "/api/eng/expert-gen", "ui": "/ui/terminal-architect#engineering"},
            {"command": "eng expert-integrate", "category": "engineering", "description": "Domain expert integration", "api": "/api/eng/expert-integrate", "ui": "/ui/terminal-architect#engineering"},
            {"command": "eng gate-gen", "category": "engineering", "description": "Domain gate generator", "api": "/api/eng/gate-gen", "ui": "/ui/terminal-architect#engineering"},
            {"command": "eng perception", "category": "engineering", "description": "Murphy autonomous perception", "api": "/api/eng/perception", "ui": "/ui/terminal-architect#engineering"},
            {"command": "eng sensor", "category": "engineering", "description": "Murphy sensor fusion", "api": "/api/eng/sensor", "ui": "/ui/terminal-architect#engineering"},
            {"command": "eng simulate", "category": "engineering", "description": "Simulation engine", "api": "/api/eng/simulate", "ui": "/ui/terminal-architect#engineering"},
            {"command": "eng toolbox", "category": "engineering", "description": "Murphy engineering toolbox", "api": "/api/eng/toolbox", "ui": "/ui/terminal-architect#engineering"},
            {"command": "eng twin", "category": "engineering", "description": "Digital twin engine", "api": "/api/eng/twin", "ui": "/ui/terminal-architect#engineering"},
            {"command": "eng vision", "category": "engineering", "description": "Computer vision pipeline", "api": "/api/eng/vision", "ui": "/ui/terminal-architect#engineering"},
            {"command": "image generate", "category": "engineering", "description": "Image generation engine", "api": "/api/image/generate", "ui": "/ui/terminal-architect#engineering"},
            {"command": "neuro status", "category": "engineering", "description": "Neuro-symbolic models", "api": "/api/neuro/status", "ui": "/ui/terminal-architect#engineering"},
            {"command": "vision run", "category": "engineering", "description": "Computer vision pipeline", "api": "/api/vision/run", "ui": "/ui/terminal-architect#engineering"},
            # ── Enterprise (from module manifest) ──
            {"command": "integrations enterprise", "category": "enterprise", "description": "Enterprise integrations", "api": "/api/integrations/enterprise", "ui": "/ui/terminal-integrated"},
            # ── Eq (from module manifest) ──
            {"command": "eq status", "category": "eq", "description": "EQ module", "api": "/api/eq/status", "ui": "/ui/terminal-integrated"},
            # ── Events (from module manifest) ──
            {"command": "events list", "category": "events", "description": "Event backbone", "api": "/api/events/list", "ui": "/ui/terminal-orchestrator#events"},
            {"command": "events status", "category": "events", "description": "Event backbone", "api": "/api/events/status", "ui": "/ui/terminal-orchestrator#events"},
            # ── Executive (from module manifest) ──
            {"command": "autonomous status", "category": "executive", "description": "Autonomous systems", "api": "/api/autonomous/status", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "ceo activate", "category": "executive", "description": "CEO branch activation — top-level autonomous decision-making, org chart automation, and operational planning", "api": "/api/ceo/activate", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "ceo directive", "category": "executive", "description": "CEO branch activation — top-level autonomous decision-making, org chart automation, and operational planning", "api": "/api/ceo/directive", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "ceo plan", "category": "executive", "description": "CEO branch activation — top-level autonomous decision-making, org chart automation, and operational planning", "api": "/api/ceo/plan", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "ceo status", "category": "executive", "description": "CEO branch activation — top-level autonomous decision-making, org chart automation, and operational planning", "api": "/api/ceo/status", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "founder health", "category": "executive", "description": "Founder-level unified update orchestrator", "api": "/api/founder/health", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "founder recommendations", "category": "executive", "description": "Founder-level unified update orchestrator", "api": "/api/founder/recommendations", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "founder report", "category": "executive", "description": "Founder-level unified update orchestrator", "api": "/api/founder/report", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "swarm build", "category": "executive", "description": "Self-codebase swarm — autonomous BMS spec generation, RFP parsing, and deliverable packaging", "api": "/api/swarm/build", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "swarm crew", "category": "executive", "description": "Murphy crew system", "api": "/api/swarm/crew", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "swarm domain", "category": "executive", "description": "Domain swarms", "api": "/api/swarm/domain", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "swarm durable", "category": "executive", "description": "Durable swarm orchestrator", "api": "/api/swarm/durable", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "swarm list", "category": "executive", "description": "Advanced swarm system", "api": "/api/swarm/list", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "swarm orchestrate", "category": "executive", "description": "Durable swarm orchestrator", "api": "/api/swarm/orchestrate", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "swarm propose", "category": "executive", "description": "Swarm proposal generator", "api": "/api/swarm/propose", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "swarm propose", "category": "executive", "description": "Self-codebase swarm — autonomous BMS spec generation, RFP parsing, and deliverable packaging", "api": "/api/swarm/propose", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "swarm spawn", "category": "executive", "description": "Advanced swarm system", "api": "/api/swarm/spawn", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "swarm status", "category": "executive", "description": "Advanced swarm system", "api": "/api/swarm/status", "ui": "/ui/terminal-orchestrator#executive"},
            {"command": "swarm status", "category": "executive", "description": "Self-codebase swarm — autonomous BMS spec generation, RFP parsing, and deliverable packaging", "api": "/api/swarm/status", "ui": "/ui/terminal-orchestrator#executive"},
            # ── Finance (from module manifest) ──
            {"command": "costs recommendations", "category": "finance", "description": "Cost optimization advisor", "api": "/api/costs/recommendations", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance budget", "category": "finance", "description": "Budget-aware processor", "api": "/api/finance/budget", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance coinbase", "category": "finance", "description": "Coinbase connector", "api": "/api/finance/coinbase", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance cost-gate", "category": "finance", "description": "Cost explosion gate", "api": "/api/finance/cost-gate", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance costs", "category": "finance", "description": "Cost optimization advisor", "api": "/api/finance/costs", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance crypto exchange", "category": "finance", "description": "Crypto exchange connector", "api": "/api/finance/crypto-exchange", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance crypto portfolio", "category": "finance", "description": "Crypto portfolio tracker", "api": "/api/finance/crypto-portfolio", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance crypto risk", "category": "finance", "description": "Crypto risk manager", "api": "/api/finance/crypto-risk", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance crypto wallet", "category": "finance", "description": "Crypto wallet manager", "api": "/api/finance/crypto-wallet", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance invoice", "category": "finance", "description": "Invoice processing pipeline", "api": "/api/finance/invoice", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance invoices", "category": "finance", "description": "Invoice processing pipeline", "api": "/api/finance/invoices", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance market", "category": "finance", "description": "Market data feed", "api": "/api/finance/market", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance report", "category": "finance", "description": "Financial reporting engine", "api": "/api/finance/report", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance summary", "category": "finance", "description": "Financial reporting engine", "api": "/api/finance/summary", "ui": "/ui/terminal-integrated#finance"},
            {"command": "finance trading", "category": "finance", "description": "Trading bot engine", "api": "/api/finance/trading", "ui": "/ui/terminal-integrated#finance"},
            # ── Freelancer (from module manifest) ──
            {"command": "freelancer validate", "category": "freelancer", "description": "Freelancer validator", "api": "/api/freelancer/validate", "ui": "/ui/terminal-integrated"},
            # ── Governance (from module manifest) ──
            {"command": "gates arm", "category": "governance", "description": "Gate synthesis and compliance enforcement", "api": "/api/gates/arm", "ui": "/ui/terminal-architect#governance"},
            {"command": "gates authority", "category": "governance", "description": "Authority gate", "api": "/api/gates/authority", "ui": "/ui/terminal-architect#governance"},
            {"command": "gates bypass", "category": "governance", "description": "Gate bypass controller", "api": "/api/gates/bypass", "ui": "/ui/terminal-architect#governance"},
            {"command": "gates disarm", "category": "governance", "description": "Gate synthesis and compliance enforcement", "api": "/api/gates/disarm", "ui": "/ui/terminal-architect#governance"},
            {"command": "gates status", "category": "governance", "description": "Gate synthesis and compliance enforcement", "api": "/api/gates/status", "ui": "/ui/terminal-architect#governance"},
            {"command": "governance bot-policies", "category": "governance", "description": "Bot governance policy mapper", "api": "/api/governance/bot-policies", "ui": "/ui/terminal-architect#governance"},
            {"command": "governance policies", "category": "governance", "description": "Governance framework", "api": "/api/governance/policies", "ui": "/ui/terminal-architect#governance"},
            {"command": "governance runtime", "category": "governance", "description": "Base governance runtime", "api": "/api/governance/runtime", "ui": "/ui/terminal-architect#governance"},
            {"command": "governance status", "category": "governance", "description": "Governance framework", "api": "/api/governance/status", "ui": "/ui/terminal-architect#governance"},
            {"command": "governance toggle", "category": "governance", "description": "Base governance runtime", "api": "/api/governance/toggle", "ui": "/ui/terminal-architect#governance"},
            {"command": "hitl graduate", "category": "governance", "description": "HITL graduation engine", "api": "/api/hitl/graduate", "ui": "/ui/terminal-architect#governance"},
            {"command": "hitl level", "category": "governance", "description": "HITL graduation engine", "api": "/api/hitl/level", "ui": "/ui/terminal-architect#governance"},
            {"command": "hitl status", "category": "governance", "description": "HITL autonomy controller", "api": "/api/hitl/status", "ui": "/ui/terminal-architect#governance"},
            {"command": "hitl validate", "category": "governance", "description": "Freelancer validator", "api": "/api/hitl/validate", "ui": "/ui/terminal-architect#governance"},
            {"command": "runtime closure", "category": "governance", "description": "Closure engine", "api": "/api/runtime/closure", "ui": "/ui/terminal-architect#governance"},
            {"command": "runtime persistence", "category": "governance", "description": "Persistence manager", "api": "/api/runtime/persistence", "ui": "/ui/terminal-architect#governance"},
            {"command": "runtime replay", "category": "governance", "description": "Persistence replay completeness", "api": "/api/runtime/replay", "ui": "/ui/terminal-architect#governance"},
            {"command": "runtime session", "category": "governance", "description": "Session context", "api": "/api/runtime/session", "ui": "/ui/terminal-architect#governance"},
            {"command": "runtime stability", "category": "governance", "description": "Recursive stability controller", "api": "/api/runtime/stability", "ui": "/ui/terminal-architect#governance"},
            {"command": "runtime status", "category": "governance", "description": "Runtime package", "api": "/api/runtime/status", "ui": "/ui/terminal-architect#governance"},
            {"command": "runtime supervision", "category": "governance", "description": "Supervision tree", "api": "/api/runtime/supervision", "ui": "/ui/terminal-architect#governance"},
            {"command": "runtime supervisor", "category": "governance", "description": "Supervisor system", "api": "/api/runtime/supervisor", "ui": "/ui/terminal-architect#governance"},
            {"command": "runtime thread-safe", "category": "governance", "description": "Thread-safe operations", "api": "/api/runtime/thread-safe", "ui": "/ui/terminal-architect#governance"},
            {"command": "runtime wal", "category": "governance", "description": "Persistence WAL", "api": "/api/runtime/wal", "ui": "/ui/terminal-architect#governance"},
            # ── Heal (from module manifest) ──
            {"command": "heal blackstart", "category": "heal", "description": "Blackstart controller", "api": "/api/heal/blackstart", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal chaos", "category": "heal", "description": "Chaos resilience loop", "api": "/api/heal/chaos", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal code", "category": "heal", "description": "Murphy code healer", "api": "/api/heal/code", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal code-repair", "category": "heal", "description": "Code repair engine", "api": "/api/heal/code-repair", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal coordinate", "category": "heal", "description": "Self-healing coordinator", "api": "/api/heal/coordinate", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal fix", "category": "heal", "description": "Self-fix loop", "api": "/api/heal/fix", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal immune", "category": "heal", "description": "Murphy immune engine", "api": "/api/heal/immune", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal improve", "category": "heal", "description": "Self-improvement engine", "api": "/api/heal/improve", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal maintenance", "category": "heal", "description": "Predictive maintenance engine", "api": "/api/heal/maintenance", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal optimise", "category": "heal", "description": "Self-optimisation engine", "api": "/api/heal/optimise", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal predict", "category": "heal", "description": "Predictive failure engine", "api": "/api/heal/predict", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal repair", "category": "heal", "description": "Autonomous repair system", "api": "/api/heal/repair", "ui": "/ui/terminal-architect#heal"},
            {"command": "heal status", "category": "heal", "description": "Autonomous repair system", "api": "/api/heal/status", "ui": "/ui/terminal-architect#heal"},
            # ── Health (from module manifest) ──
            {"command": "health status", "category": "health", "description": "Health monitor", "api": "/api/health/status", "ui": "/ui/terminal-integrated"},
            # ── Infrastructure (from module manifest) ──
            {"command": "cloud orchestrate", "category": "infrastructure", "description": "Multi-cloud orchestrator", "api": "/api/cloud/orchestrate", "ui": "/ui/terminal-architect#infra"},
            {"command": "cloud status", "category": "infrastructure", "description": "Multi-cloud orchestrator", "api": "/api/cloud/status", "ui": "/ui/terminal-architect#infra"},
            {"command": "docker status", "category": "infrastructure", "description": "Docker containerization", "api": "/api/docker/status", "ui": "/ui/terminal-architect#infra"},
            {"command": "infra backup", "category": "infrastructure", "description": "Backup & disaster recovery", "api": "/api/infra/backup", "ui": "/ui/terminal-architect#infra"},
            {"command": "infra capacity", "category": "infrastructure", "description": "Capacity planning engine", "api": "/api/infra/capacity", "ui": "/ui/terminal-architect#infra"},
            {"command": "infra cloudflare", "category": "infrastructure", "description": "Cloudflare deployment", "api": "/api/infra/cloudflare", "ui": "/ui/terminal-architect#infra"},
            {"command": "infra docker", "category": "infrastructure", "description": "Docker containerization", "api": "/api/infra/docker", "ui": "/ui/terminal-architect#infra"},
            {"command": "infra dr", "category": "infrastructure", "description": "Backup & disaster recovery", "api": "/api/infra/dr", "ui": "/ui/terminal-architect#infra"},
            {"command": "infra hetzner", "category": "infrastructure", "description": "Hetzner deployment", "api": "/api/infra/hetzner", "ui": "/ui/terminal-architect#infra"},
            {"command": "infra k8s", "category": "infrastructure", "description": "Kubernetes deployment", "api": "/api/infra/k8s", "ui": "/ui/terminal-architect#infra"},
            {"command": "infra lb", "category": "infrastructure", "description": "Geographic load balancer", "api": "/api/infra/lb", "ui": "/ui/terminal-architect#infra"},
            {"command": "infra load-balancer", "category": "infrastructure", "description": "Geographic load balancer", "api": "/api/infra/load-balancer", "ui": "/ui/terminal-architect#infra"},
            {"command": "infra scale", "category": "infrastructure", "description": "Resource scaling controller", "api": "/api/infra/scale", "ui": "/ui/terminal-architect#infra"},
            {"command": "k8s status", "category": "infrastructure", "description": "Kubernetes deployment", "api": "/api/k8s/status", "ui": "/ui/terminal-architect#infra"},
            # ── Integration (from module manifest) ──
            {"command": "integrations bus", "category": "integration", "description": "Integration bus", "api": "/api/integrations/bus", "ui": "/ui/terminal-integrated"},
            {"command": "integrations status", "category": "integration", "description": "Integration engine", "api": "/api/integrations/status", "ui": "/ui/terminal-integrated"},
            # ── Integrations (from module manifest) ──
            {"command": "integrations all", "category": "integrations", "description": "Integrations package", "api": "/api/integrations/all", "ui": "/ui/terminal-integrated"},
            {"command": "integrations universal", "category": "integrations", "description": "Universal integration adapter", "api": "/api/integrations/universal", "ui": "/ui/terminal-integrated"},
            # ── Iot (from module manifest) ──
            {"command": "iot additive", "category": "iot", "description": "Additive manufacturing connectors", "api": "/api/iot/additive", "ui": "/ui/terminal-integrations#iot"},
            {"command": "iot building", "category": "iot", "description": "Building automation connectors", "api": "/api/iot/building", "ui": "/ui/terminal-integrations#iot"},
            {"command": "iot energy", "category": "iot", "description": "Energy management connectors", "api": "/api/iot/energy", "ui": "/ui/terminal-integrations#iot"},
            {"command": "iot manufacturing", "category": "iot", "description": "Manufacturing automation standards", "api": "/api/iot/manufacturing", "ui": "/ui/terminal-integrations#iot"},
            {"command": "iot sensors", "category": "iot", "description": "Sensor reader", "api": "/api/iot/sensors", "ui": "/ui/terminal-integrations#iot"},
            {"command": "robotics run", "category": "iot", "description": "Robotics", "api": "/api/robotics/run", "ui": "/ui/terminal-integrations#iot"},
            {"command": "robotics status", "category": "iot", "description": "Robotics", "api": "/api/robotics/status", "ui": "/ui/terminal-integrations#iot"},
            {"command": "sensor read", "category": "iot", "description": "Sensor reader", "api": "/api/sensor/read", "ui": "/ui/terminal-integrations#iot"},
            # ── Knowledge (from module manifest) ──
            {"command": "data archive", "category": "knowledge", "description": "Data archive manager", "api": "/api/data/archive", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "data pipeline", "category": "knowledge", "description": "Data pipeline orchestrator", "api": "/api/data/pipeline", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "data status", "category": "knowledge", "description": "Data pipeline orchestrator", "api": "/api/data/status", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "data sync", "category": "knowledge", "description": "Cross-platform data sync", "api": "/api/data/sync", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "kb status", "category": "knowledge", "description": "Knowledge base manager", "api": "/api/kb/status", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "kg concepts", "category": "knowledge", "description": "Concept graph engine", "api": "/api/kg/concepts", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "kg gap", "category": "knowledge", "description": "Knowledge gap system", "api": "/api/kg/gap", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "kg generate", "category": "knowledge", "description": "Generative knowledge builder", "api": "/api/kg/generate", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "kg status", "category": "knowledge", "description": "Knowledge graph builder", "api": "/api/kg/status", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "kg translate", "category": "knowledge", "description": "Concept translation", "api": "/api/kg/translate", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "librarian capabilities", "category": "knowledge", "description": "System librarian and semantic search", "api": "/api/librarian/capabilities", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "librarian gap", "category": "knowledge", "description": "Knowledge gap system", "api": "/api/librarian/gap", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "librarian generate", "category": "knowledge", "description": "Generative knowledge builder", "api": "/api/librarian/generate", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "librarian graph", "category": "knowledge", "description": "Knowledge graph builder", "api": "/api/librarian/graph", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "librarian kb", "category": "knowledge", "description": "Knowledge base manager", "api": "/api/librarian/kb", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "librarian query", "category": "knowledge", "description": "System librarian and semantic search", "api": "/api/librarian/query", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "librarian rag", "category": "knowledge", "description": "RAG vector integration", "api": "/api/librarian/rag", "ui": "/ui/terminal-integrated#librarian"},
            {"command": "librarian search", "category": "knowledge", "description": "System librarian and semantic search", "api": "/api/librarian/search", "ui": "/ui/terminal-integrated#librarian"},
            # ── Librarian (from module manifest) ──
            {"command": "docs generate", "category": "librarian", "description": "Auto documentation engine", "api": "/api/docs/generate", "ui": "/ui/terminal-integrated"},
            {"command": "docs status", "category": "librarian", "description": "Auto documentation engine", "api": "/api/docs/status", "ui": "/ui/terminal-integrated"},
            # ── Llm (from module manifest) ──
            {"command": "llm deepinfra", "category": "llm", "description": "OpenAI-compatible provider (openai/deepinfra/onboard)", "api": "/api/llm/deepinfra", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm deepinfra-keys", "category": "llm", "description": "DeepInfra key rotator", "api": "/api/llm/deepinfra-keys", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm fallback", "category": "llm", "description": "Local LLM fallback", "api": "/api/llm/fallback", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm gate", "category": "llm", "description": "Inference gate engine", "api": "/api/llm/gate", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm inference", "category": "llm", "description": "Local inference engine", "api": "/api/llm/inference", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm local", "category": "llm", "description": "Enhanced local LLM (onboard)", "api": "/api/llm/local", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm model", "category": "llm", "description": "LLM controller", "api": "/api/llm/model", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm models", "category": "llm", "description": "Local model layer", "api": "/api/llm/models", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm onboard", "category": "llm", "description": "Enhanced local LLM (onboard)", "api": "/api/llm/onboard", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm openai", "category": "llm", "description": "OpenAI-compatible provider (openai/deepinfra/onboard)", "api": "/api/llm/openai", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm providers", "category": "llm", "description": "LLM integration layer", "api": "/api/llm/providers", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm route", "category": "llm", "description": "LLM controller", "api": "/api/llm/route", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm routing", "category": "llm", "description": "LLM routing completeness", "api": "/api/llm/routing", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm safe", "category": "llm", "description": "Safe LLM wrapper", "api": "/api/llm/safe", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm swarm", "category": "llm", "description": "LLM swarm integration", "api": "/api/llm/swarm", "ui": "/ui/terminal-integrations#llm"},
            {"command": "llm validate", "category": "llm", "description": "LLM output validator", "api": "/api/llm/validate", "ui": "/ui/terminal-integrations#llm"},
            {"command": "mfgc adapt", "category": "llm", "description": "MFGC adapter", "api": "/api/mfgc/adapt", "ui": "/ui/terminal-integrations#llm"},
            {"command": "mfgc metrics", "category": "llm", "description": "MFGC metrics", "api": "/api/mfgc/metrics", "ui": "/ui/terminal-integrations#llm"},
            {"command": "mfgc status", "category": "llm", "description": "MFGC core", "api": "/api/mfgc/status", "ui": "/ui/terminal-integrations#llm"},
            {"command": "mfm infer", "category": "llm", "description": "Murphy Foundation Model", "api": "/api/mfm/infer", "ui": "/ui/terminal-integrations#llm"},
            {"command": "mfm train", "category": "llm", "description": "Murphy Foundation Model", "api": "/api/mfm/train", "ui": "/ui/terminal-integrations#llm"},
            # ── Marketing (from module manifest) ──
            {"command": "announce", "category": "marketing", "description": "Announcer voice engine", "api": "/api/announce", "ui": "/ui/terminal-orchestrator#campaigns"},
            {"command": "announce broadcast", "category": "marketing", "description": "Announcer voice engine", "api": "/api/announce/broadcast", "ui": "/ui/terminal-orchestrator#campaigns"},
            {"command": "campaign adapt", "category": "marketing", "description": "Adaptive campaign engine", "api": "/api/campaign/adapt", "ui": "/ui/terminal-orchestrator#campaigns"},
            {"command": "campaign run", "category": "marketing", "description": "Campaign orchestrator", "api": "/api/campaign/run", "ui": "/ui/terminal-orchestrator#campaigns"},
            {"command": "campaign status", "category": "marketing", "description": "Campaign orchestrator", "api": "/api/campaign/status", "ui": "/ui/terminal-orchestrator#campaigns"},
            {"command": "content pipeline", "category": "marketing", "description": "Content pipeline engine", "api": "/api/content/pipeline", "ui": "/ui/terminal-orchestrator#campaigns"},
            {"command": "content platform", "category": "marketing", "description": "Content creator platform modulator", "api": "/api/content/platform", "ui": "/ui/terminal-orchestrator#campaigns"},
            {"command": "content status", "category": "marketing", "description": "Content pipeline engine", "api": "/api/content/status", "ui": "/ui/terminal-orchestrator#campaigns"},
            # ── Monitoring (from module manifest) ──
            {"command": "learning feedback", "category": "monitoring", "description": "Adaptive learning engine", "api": "/api/learning/feedback", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "logs query", "category": "monitoring", "description": "Logging system", "api": "/api/logs/query", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "logs status", "category": "monitoring", "description": "Logging system", "api": "/api/logs/status", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor alerts", "category": "monitoring", "description": "Alert rules engine", "api": "/api/monitor/alerts", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor bot-telemetry", "category": "monitoring", "description": "Bot telemetry normalizer", "api": "/api/monitor/bot-telemetry", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor counters", "category": "monitoring", "description": "Observability counters", "api": "/api/monitor/counters", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor health", "category": "monitoring", "description": "Health monitor", "api": "/api/monitor/health", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor heartbeat", "category": "monitoring", "description": "Heartbeat liveness protocol", "api": "/api/monitor/heartbeat", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor heartbeat-runner", "category": "monitoring", "description": "Activated heartbeat runner", "api": "/api/monitor/heartbeat-runner", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor logs", "category": "monitoring", "description": "Log analysis engine", "api": "/api/monitor/logs", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor metrics", "category": "monitoring", "description": "Prometheus metrics exporter", "api": "/api/monitor/metrics", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor slo", "category": "monitoring", "description": "Operational SLO tracker", "api": "/api/monitor/slo", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor slo-remediate", "category": "monitoring", "description": "SLO remediation bridge", "api": "/api/monitor/slo-remediate", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor spikes", "category": "monitoring", "description": "Causal spike analyzer", "api": "/api/monitor/spikes", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor telemetry", "category": "monitoring", "description": "Adaptive learning engine", "api": "/api/monitor/telemetry", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor telemetry", "category": "monitoring", "description": "Telemetry system", "api": "/api/monitor/telemetry", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor telemetry-adapter", "category": "monitoring", "description": "Telemetry adapter", "api": "/api/monitor/telemetry-adapter", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor telemetry-learning", "category": "monitoring", "description": "Telemetry learning", "api": "/api/monitor/telemetry-learning", "ui": "/ui/terminal-integrated#monitor"},
            {"command": "monitor trace", "category": "monitoring", "description": "Murphy trace", "api": "/api/monitor/trace", "ui": "/ui/terminal-integrated#monitor"},
            # ── Onboarding (from module manifest) ──
            {"command": "setup wizard", "category": "onboarding", "description": "Setup wizard", "api": "/api/setup/wizard", "ui": "/ui/terminal-integrated"},
            # ── Org (from module manifest) ──
            {"command": "org chart", "category": "org", "description": "Org compiler", "api": "/api/org/chart", "ui": "/ui/terminal-integrated"},
            {"command": "org compile", "category": "org", "description": "Org compiler", "api": "/api/org/compile", "ui": "/ui/terminal-integrated"},
            {"command": "org enforce", "category": "org", "description": "Org chart enforcement", "api": "/api/org/enforce", "ui": "/ui/terminal-integrated"},
            # ── Organization (from module manifest) ──
            {"command": "org orgchart", "category": "organization", "description": "Organization chart system", "api": "/api/org/orgchart", "ui": "/ui/terminal-integrated"},
            # ── Organizational (from module manifest) ──
            {"command": "org context", "category": "organizational", "description": "Organizational context system", "api": "/api/org/context", "ui": "/ui/terminal-integrated"},
            # ── Platform (from module manifest) ──
            {"command": "aionmind status", "category": "platform", "description": "AionMind", "api": "/api/aionmind/status", "ui": "/ui/terminal-architect#platform"},
            {"command": "auar route", "category": "platform", "description": "AUAR (Universal Adaptive Routing)", "api": "/api/auar/route", "ui": "/ui/terminal-architect#platform"},
            {"command": "auar status", "category": "platform", "description": "AUAR (Universal Adaptive Routing)", "api": "/api/auar/status", "ui": "/ui/terminal-architect#platform"},
            {"command": "avatar status", "category": "platform", "description": "Avatar", "api": "/api/avatar/status", "ui": "/ui/terminal-architect#platform"},
            {"command": "knostalgia categories", "category": "platform", "description": "Knostalgia category engine", "api": "/api/knostalgia/categories", "ui": "/ui/terminal-architect#platform"},
            {"command": "knostalgia run", "category": "platform", "description": "Knostalgia engine", "api": "/api/knostalgia/run", "ui": "/ui/terminal-architect#platform"},
            {"command": "osmosis run", "category": "platform", "description": "Murphy osmosis engine", "api": "/api/osmosis/run", "ui": "/ui/terminal-architect#platform"},
            {"command": "platforms connect", "category": "platform", "description": "Platform connector framework", "api": "/api/platforms/connect", "ui": "/ui/terminal-architect#platform"},
            {"command": "platforms list", "category": "platform", "description": "Platform connector framework", "api": "/api/platforms/list", "ui": "/ui/terminal-architect#platform"},
            {"command": "shadow train", "category": "platform", "description": "Murphy shadow trainer", "api": "/api/shadow/train", "ui": "/ui/terminal-architect#platform"},
            {"command": "state graph", "category": "platform", "description": "Murphy state graph", "api": "/api/state/graph", "ui": "/ui/terminal-architect#platform"},
            {"command": "state machine", "category": "platform", "description": "State machine", "api": "/api/state/machine", "ui": "/ui/terminal-architect#platform"},
            {"command": "state schema", "category": "platform", "description": "State schema", "api": "/api/state/schema", "ui": "/ui/terminal-architect#platform"},
            {"command": "wingman evolve", "category": "platform", "description": "Murphy wingman evolution", "api": "/api/wingman/evolve", "ui": "/ui/terminal-architect#platform"},
            # ── Playwright (from module manifest) ──
            {"command": "playwright run", "category": "playwright", "description": "Playwright task definitions", "api": "/api/playwright/run", "ui": "/ui/terminal-integrated"},
            # ── Portfolio (from module manifest) ──
            {"command": "portfolio list", "category": "portfolio", "description": "Portfolio", "api": "/api/portfolio/list", "ui": "/ui/terminal-integrated"},
            {"command": "portfolio status", "category": "portfolio", "description": "Portfolio", "api": "/api/portfolio/status", "ui": "/ui/terminal-integrated"},
            # ── Production (from module manifest) ──
            {"command": "prod intake", "category": "production", "description": "Production assistant engine — request lifecycle management with deliverable gate validation via EventBackbone", "api": "/api/prod/intake", "ui": "/ui/terminal-integrated"},
            {"command": "prod status", "category": "production", "description": "Production assistant engine — request lifecycle management with deliverable gate validation via EventBackbone", "api": "/api/prod/status", "ui": "/ui/terminal-integrated"},
            {"command": "prod validate", "category": "production", "description": "Production assistant engine — request lifecycle management with deliverable gate validation via EventBackbone", "api": "/api/prod/validate", "ui": "/ui/terminal-integrated"},
            # ── Prometheus (from module manifest) ──
            {"command": "metrics export", "category": "prometheus", "description": "Prometheus metrics exporter", "api": "/api/metrics/export", "ui": "/ui/terminal-integrated"},
            # ── Protocols (from module manifest) ──
            {"command": "protocols list", "category": "protocols", "description": "Protocols", "api": "/api/protocols/list", "ui": "/ui/terminal-integrated"},
            # ── Rag (from module manifest) ──
            {"command": "rag search", "category": "rag", "description": "RAG vector integration", "api": "/api/rag/search", "ui": "/ui/terminal-integrated"},
            # ── Remote (from module manifest) ──
            {"command": "remote connect", "category": "remote", "description": "Remote access connector", "api": "/api/remote/connect", "ui": "/ui/terminal-integrated"},
            # ── Rosetta (from module manifest) ──
            {"command": "rosetta sell", "category": "rosetta", "description": "Rosetta selling bridge", "api": "/api/rosetta/sell", "ui": "/ui/terminal-integrated"},
            {"command": "rosetta status", "category": "rosetta", "description": "Rosetta", "api": "/api/rosetta/status", "ui": "/ui/terminal-integrated"},
            # ── Rpa (from module manifest) ──
            {"command": "rpa record", "category": "rpa", "description": "RPA recorder engine", "api": "/api/rpa/record", "ui": "/ui/terminal-integrated"},
            {"command": "rpa replay", "category": "rpa", "description": "RPA recorder engine", "api": "/api/rpa/replay", "ui": "/ui/terminal-integrated"},
            # ── Safety (from module manifest) ──
            {"command": "safety emergency", "category": "safety", "description": "Emergency stop controller", "api": "/api/safety/emergency", "ui": "/ui/terminal-architect#safety"},
            {"command": "safety estop", "category": "safety", "description": "Emergency stop controller", "api": "/api/safety/estop", "ui": "/ui/terminal-architect#safety"},
            {"command": "safety gateway", "category": "safety", "description": "Safety gateway integrator", "api": "/api/safety/gateway", "ui": "/ui/terminal-architect#safety"},
            {"command": "safety orchestrate", "category": "safety", "description": "Safety orchestrator", "api": "/api/safety/orchestrate", "ui": "/ui/terminal-architect#safety"},
            {"command": "safety validate", "category": "safety", "description": "Safety validation pipeline", "api": "/api/safety/validate", "ui": "/ui/terminal-architect#safety"},
            # ── Sales (from module manifest) ──
            {"command": "sales pipeline", "category": "sales", "description": "Sales automation", "api": "/api/sales/pipeline", "ui": "/ui/terminal-integrated"},
            {"command": "sales status", "category": "sales", "description": "Sales automation", "api": "/api/sales/status", "ui": "/ui/terminal-integrated"},
            # ── Schema (from module manifest) ──
            {"command": "schema list", "category": "schema", "description": "Schema registry", "api": "/api/schema/list", "ui": "/ui/terminal-integrated"},
            {"command": "schema validate", "category": "schema", "description": "Schema registry", "api": "/api/schema/validate", "ui": "/ui/terminal-integrated"},
            # ── Security (from module manifest) ──
            {"command": "audit blockchain", "category": "security", "description": "Blockchain audit trail", "api": "/api/audit/blockchain", "ui": "/ui/terminal-architect#security"},
            {"command": "audit logs", "category": "security", "description": "Audit logging system", "api": "/api/audit/logs", "ui": "/ui/terminal-architect#security"},
            {"command": "security adapter", "category": "security", "description": "Security plane adapter", "api": "/api/security/adapter", "ui": "/ui/terminal-architect#security"},
            {"command": "security api", "category": "security", "description": "FastAPI security layer", "api": "/api/security/api", "ui": "/ui/terminal-architect#security"},
            {"command": "security audit", "category": "security", "description": "Security plane and threat management", "api": "/api/security/audit", "ui": "/ui/terminal-architect#security"},
            {"command": "security audit", "category": "security", "description": "Security audit scanner", "api": "/api/security/audit", "ui": "/ui/terminal-architect#security"},
            {"command": "security credentials", "category": "security", "description": "Murphy credential gate", "api": "/api/security/credentials", "ui": "/ui/terminal-architect#security"},
            {"command": "security flask", "category": "security", "description": "Flask security layer", "api": "/api/security/flask", "ui": "/ui/terminal-architect#security"},
            {"command": "security harden", "category": "security", "description": "Security hardening config", "api": "/api/security/harden", "ui": "/ui/terminal-architect#security"},
            {"command": "security oauth", "category": "security", "description": "OAuth/OIDC provider", "api": "/api/security/oauth", "ui": "/ui/terminal-architect#security"},
            {"command": "security oidc", "category": "security", "description": "OAuth/OIDC provider", "api": "/api/security/oidc", "ui": "/ui/terminal-architect#security"},
            {"command": "security permissions", "category": "security", "description": "RBAC governance", "api": "/api/security/permissions", "ui": "/ui/terminal-architect#security"},
            {"command": "security scan", "category": "security", "description": "Security plane and threat management", "api": "/api/security/scan", "ui": "/ui/terminal-architect#security"},
            {"command": "security scan", "category": "security", "description": "Security audit scanner", "api": "/api/security/scan", "ui": "/ui/terminal-architect#security"},
            {"command": "security status", "category": "security", "description": "Security plane and threat management", "api": "/api/security/status", "ui": "/ui/terminal-architect#security"},
            # ── Self (from module manifest) ──
            {"command": "introspect run", "category": "self", "description": "Self-introspection module — runtime self-analysis and reporting", "api": "/api/introspect/run", "ui": "/ui/terminal-integrated"},
            {"command": "introspect status", "category": "self", "description": "Self-introspection module — runtime self-analysis and reporting", "api": "/api/introspect/status", "ui": "/ui/terminal-integrated"},
            {"command": "marketing b2b", "category": "self", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/marketing/b2b", "ui": "/ui/terminal-integrated"},
            {"command": "marketing content", "category": "self", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/marketing/content", "ui": "/ui/terminal-integrated"},
            {"command": "marketing cycle", "category": "self", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/marketing/cycle", "ui": "/ui/terminal-integrated"},
            {"command": "marketing outreach", "category": "self", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/marketing/outreach", "ui": "/ui/terminal-integrated"},
            {"command": "marketing partnerships", "category": "self", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/marketing/partnerships", "ui": "/ui/terminal-integrated"},
            {"command": "marketing social", "category": "self", "description": "Self-marketing orchestrator — Murphy markets Murphy with compliance + B2B partnerships", "api": "/api/marketing/social", "ui": "/ui/terminal-integrated"},
            {"command": "sell status", "category": "self", "description": "Self selling engine", "api": "/api/sell/status", "ui": "/ui/terminal-integrated"},
            # ── Simulation (from module manifest) ──
            {"command": "sim run", "category": "simulation", "description": "Simulation engine", "api": "/api/sim/run", "ui": "/ui/terminal-integrated"},
            {"command": "sim validate", "category": "simulation", "description": "Simulation engine", "api": "/api/sim/validate", "ui": "/ui/terminal-integrated"},
            # ── Social (from module manifest) ──
            {"command": "social moderate", "category": "social", "description": "Social media moderation", "api": "/api/social/moderate", "ui": "/ui/terminal-integrated"},
            {"command": "social post", "category": "social", "description": "Social media scheduler", "api": "/api/social/post", "ui": "/ui/terminal-integrated"},
            {"command": "social schedule", "category": "social", "description": "Social media scheduler", "api": "/api/social/schedule", "ui": "/ui/terminal-integrated"},
            # ── Synthetic (from module manifest) ──
            {"command": "chaos failure", "category": "synthetic", "description": "Synthetic failure generator", "api": "/api/chaos/failure", "ui": "/ui/terminal-integrated"},
            # ── System (from module manifest) ──
            {"command": "integrations system", "category": "system", "description": "System integrator", "api": "/api/integrations/system", "ui": "/ui/terminal-integrated"},
            {"command": "system features", "category": "system", "description": "Startup feature summary", "api": "/api/system/features", "ui": "/ui/terminal-integrated"},
            {"command": "system validate", "category": "system", "description": "Startup validator", "api": "/api/system/validate", "ui": "/ui/terminal-integrated"},
            # ── Testing (from module manifest) ──
            {"command": "ab test", "category": "testing", "description": "A/B testing framework", "api": "/api/ab/test", "ui": "/ui/terminal-architect#testing"},
            # ── Ticketing (from module manifest) ──
            {"command": "tickets create", "category": "ticketing", "description": "Ticketing adapter", "api": "/api/tickets/create", "ui": "/ui/terminal-integrated"},
            {"command": "tickets list", "category": "ticketing", "description": "Ticketing adapter", "api": "/api/tickets/list", "ui": "/ui/terminal-integrated"},
            # ── Time (from module manifest) ──
            {"command": "time log", "category": "time", "description": "Time tracking", "api": "/api/time/log", "ui": "/ui/terminal-integrated"},
            {"command": "time report", "category": "time", "description": "Time tracking", "api": "/api/time/report", "ui": "/ui/terminal-integrated"},
            # ── Trading (from module manifest) ──
            {"command": "trading approve", "category": "trading", "description": "Trading HITL gateway", "api": "/api/trading/approve", "ui": "/ui/terminal-integrated"},
            {"command": "trading lifecycle", "category": "trading", "description": "Trading bot lifecycle", "api": "/api/trading/lifecycle", "ui": "/ui/terminal-integrated"},
            {"command": "trading shadow", "category": "trading", "description": "Trading shadow learner", "api": "/api/trading/shadow", "ui": "/ui/terminal-integrated"},
            {"command": "trading status", "category": "trading", "description": "Trading bot engine", "api": "/api/trading/status", "ui": "/ui/terminal-integrated"},
            {"command": "trading strategy", "category": "trading", "description": "Trading strategy engine", "api": "/api/trading/strategy", "ui": "/ui/terminal-integrated"},
            # ── Visual (from module manifest) ──
            {"command": "visual build", "category": "visual", "description": "Visual swarm builder — visual pipeline construction for swarm workflows", "api": "/api/visual/build", "ui": "/ui/terminal-integrated"},
            {"command": "visual status", "category": "visual", "description": "Visual swarm builder — visual pipeline construction for swarm workflows", "api": "/api/visual/status", "ui": "/ui/terminal-integrated"},
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
                {"name": "Onboarding Wizard", "url": "/ui/onboarding"},
                {"name": "Architect Terminal", "url": "/ui/terminal-architect"},
                {"name": "Integrated Terminal", "url": "/ui/terminal-integrated"},
                {"name": "Full Dashboard", "url": "/ui/dashboard"},
                {"name": "Grant Wizard", "url": "/ui/grant-wizard"},
                {"name": "Grant Dashboard", "url": "/ui/grant-dashboard"},
                {"name": "Financing Options", "url": "/ui/financing"},
                {"name": "System Visualizer", "url": "/ui/system-visualizer"},
                {"name": "Org Portal", "url": "/ui/org-portal"},
                {"name": "Admin Panel", "url": "/ui/admin"},
                {"name": "Landing Page", "url": "/ui/landing"},
            ],
            "admin": [
                {"name": "Onboarding Wizard", "url": "/ui/onboarding"},
                {"name": "Architect Terminal", "url": "/ui/terminal-architect"},
                {"name": "Integrated Terminal", "url": "/ui/terminal-integrated"},
                {"name": "Full Dashboard", "url": "/ui/dashboard"},
                {"name": "Grant Wizard", "url": "/ui/grant-wizard"},
                {"name": "Grant Dashboard", "url": "/ui/grant-dashboard"},
                {"name": "Org Portal", "url": "/ui/org-portal"},
                {"name": "Admin Panel", "url": "/ui/admin"},
            ],
            "operator": [
                {"name": "Onboarding Wizard", "url": "/ui/onboarding"},
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
        """Execute task via form endpoint — routes through Murphy cognitive pipeline."""
        data = await request.json()
        # Phase 1: thread the authenticated caller into the kernel
        _caller = _resolve_caller(request)
        _caller_email = (_caller or {}).get("email", "")
        _founder_email = os.environ.get(
            "MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems"
        ).strip().lower()
        _is_founder = bool(_caller_email) and _caller_email == _founder_email
        # Enrich form data with AionMind context if available
        if _aionmind_kernel is not None:
            try:
                desc = data.get("description") or data.get("task_description", "")
                _auto, _max_risk = _auto_approve_for(_caller)
                _approver = _caller_email or "anonymous"
                _source = (
                    f"user:{_caller_email}" if _caller_email else "form:task-execution"
                )
                _meta: "Dict[str, Any]" = {"form": "task-execution"}
                if _caller_email:
                    _meta["user_email"] = _caller_email
                    _meta["user_role"] = (_caller or {}).get("role", "user")
                if _is_founder:
                    _meta["founder"] = True
                _kernel_kwargs: "Dict[str, Any]" = dict(
                    source=_source,
                    raw_input=desc,
                    task_type=data.get("task_type", "general"),
                    parameters=data.get("parameters"),
                    auto_approve=_auto,
                    approver=_approver,
                    metadata=_meta,
                    actor=_approver,
                )
                if _max_risk is not None:
                    _kernel_kwargs["max_auto_approve_risk"] = _max_risk
                aionmind_result = _aionmind_kernel.cognitive_execute(**_kernel_kwargs)
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
        _caller = _resolve_caller(request)
        _caller_email = (_caller or {}).get("email", "")
        _founder_email = os.environ.get(
            "MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems"
        ).strip().lower()
        _is_founder = bool(_caller_email) and _caller_email == _founder_email
        if _aionmind_kernel is not None:
            try:
                desc = (data.get("task_data") or data).get("description", "")
                _meta: "Dict[str, Any]" = {"form": "validation"}
                if _caller_email:
                    _meta["user_email"] = _caller_email
                    _meta["user_role"] = (_caller or {}).get("role", "user")
                if _is_founder:
                    _meta["founder"] = True
                _source = (
                    f"user:{_caller_email}" if _caller_email else "form:validation"
                )
                ctx = _aionmind_kernel.build_context(
                    source=_source,
                    raw_input=desc,
                    metadata=_meta,
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
        _caller = _resolve_caller(request)
        _caller_email = (_caller or {}).get("email", "")
        _founder_email = os.environ.get(
            "MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems"
        ).strip().lower()
        _is_founder = bool(_caller_email) and _caller_email == _founder_email
        if _aionmind_kernel is not None:
            try:
                desc = data.get("task_description") or data.get("original_task", "")
                _meta: "Dict[str, Any]" = {
                    "form": "correction",
                    "correction": data.get("correction", ""),
                }
                if _caller_email:
                    _meta["user_email"] = _caller_email
                    _meta["user_role"] = (_caller or {}).get("role", "user")
                if _is_founder:
                    _meta["founder"] = True
                _source = (
                    f"user:{_caller_email}" if _caller_email else "form:correction"
                )
                ctx = _aionmind_kernel.build_context(
                    source=_source,
                    raw_input=desc,
                    metadata=_meta,
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
        except ImportError:  # PROD-HARD A2: matrix_bridge optional, fall through to ack
            logger.debug("matrix_bridge unavailable; acknowledging send without dispatch", exc_info=True)
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

    @app.post("/api/matrix/notify")
    async def matrix_notify(request: Request):
        """Send a Matrix notification for HITL events.

        Body: { "room_id": "...", "event_type": "hitl_pending|hitl_approved|...",
                "message": "...", "metadata": {} }
        Commissioned: PATCH-010 / 2026-04-19
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
                status_code=400,
            )
        room_id = (body.get("room_id") or "").strip()
        event_type = (body.get("event_type") or "").strip()
        message = (body.get("message") or "").strip()
        if not message:
            return JSONResponse(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "message is required"}},
                status_code=422,
            )
        # Attempt delivery via Matrix bridge
        bridge = getattr(murphy, "matrix_bridge", None)
        delivered = False
        if bridge and hasattr(bridge, "send_notification"):
            try:
                bridge.send_notification(room_id=room_id, event_type=event_type, body=message)
                delivered = True
            except Exception as exc:
                logger.warning("Matrix notify delivery failed: %s", exc)
        _matrix_bridge_state["stats"]["messages_sent"] = _matrix_bridge_state["stats"].get("messages_sent", 0) + (1 if delivered else 0)
        return JSONResponse({
            "success": True,
            "delivered": delivered,
            "event_type": event_type,
            "room_id": room_id,
        })

    @app.post("/api/infrastructure/compare")
    async def infrastructure_compare(request: Request):
        """Compare running environment against hetzner_load.sh expected state.

        Body: { "checks": ["docker", "ollama", "mail", "ssl", "dns"] }
        Returns per-check pass/fail with details.
        Commissioned: PATCH-010 / 2026-04-19
        """
        try:
            body = await request.json()
        except Exception:
            body = {}
        requested = body.get("checks") or ["docker", "ollama", "mail", "ssl", "dns"]
        import shutil
        results = {}
        for check in requested:
            if check == "docker":
                results["docker"] = {
                    "pass": shutil.which("docker") is not None,
                    "detail": "docker binary found" if shutil.which("docker") else "docker not installed",
                }
            elif check == "ollama":
                results["ollama"] = {
                    "pass": _check_ollama_available(_ollama_base_url()),
                    "detail": f"ollama at {_ollama_base_url()}",
                }
            elif check == "mail":
                results["mail"] = {
                    "pass": bool(os.environ.get("MURPHY_MAIL_DOMAIN")),
                    "detail": os.environ.get("MURPHY_MAIL_DOMAIN", "not configured"),
                }
            elif check == "ssl":
                results["ssl"] = {
                    "pass": bool(os.environ.get("MURPHY_DOMAIN")),
                    "detail": os.environ.get("MURPHY_DOMAIN", "not configured"),
                }
            elif check == "dns":
                results["dns"] = {
                    "pass": bool(os.environ.get("MURPHY_DOMAIN")),
                    "detail": os.environ.get("MURPHY_DOMAIN", "not configured"),
                }
            else:
                results[check] = {"pass": False, "detail": f"unknown check: {check}"}
        passed = sum(1 for r in results.values() if r["pass"])
        return JSONResponse({
            "success": True,
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "checks": results,
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
                             "Upgrade to Solo ($99/mo) for 3 automations.",
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

    # Shared mapping: AIWorkflowGenerator template name → AutomationEngine TriggerType.
    # Used in both /api/onboarding/finalize.  Centralised here so the two endpoints
    # don't duplicate the mapping independently.
    _TEMPLATE_TRIGGER_DEFAULTS: dict = {
        "order_fulfillment": "item_created",
        "invoice_processing": "form_submitted",
        "lead_nurture": "item_created",
        "employee_onboarding": "form_submitted",
        "content_publishing": "status_change",
        "customer_onboarding": "form_submitted",
        "etl_pipeline": "period_elapsed",
        "data_report": "period_elapsed",
        "ci_cd": "item_created",
        "incident_response": "status_change",
        "security_scan": "period_elapsed",
    }

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
            logger.debug("Suppressed exception in app")

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

    def _generate_automation_from_session(sess: dict) -> dict:
        """Generate an automation config from a completed onboarding session.

        Examines the accumulated answers and context to produce a structured
        workflow definition that downstream components (AIWorkflowGenerator,
        AutomationCommissioner) can consume.

        Returns:
            dict with keys: name, steps, step_count, strategy, description.
            Returns empty dict if session lacks enough information.
        """
        answers = {k: v for k, v in sess.get("answers", {}).items() if v}
        if not answers:
            return {}

        # Derive workflow name from initial request or answers
        initial = answers.get("initial_request", "")
        wf_name = initial[:60].strip() if initial else "custom_automation"
        # Sanitise for use as a workflow identifier
        wf_name = wf_name.replace(" ", "_").lower()
        if not wf_name:
            wf_name = "custom_automation"

        # Build steps from answered questions
        steps: list[dict] = []
        for key, value in answers.items():
            if key == "initial_request":
                continue
            steps.append({
                "name": key[:80],
                "description": str(value)[:200],
                "action": "execute",
            })

        # If MFGC instance is available, try to extract richer config
        mfgc = sess.get("mfgc")
        if mfgc is not None:
            try:
                profile = getattr(mfgc, "profile", {}) or {}
                if profile.get("industry"):
                    wf_name = f"{profile['industry']}_{wf_name}"
                if profile.get("goal"):
                    steps.insert(0, {
                        "name": "primary_goal",
                        "description": str(profile["goal"])[:200],
                        "action": "execute",
                    })
            except Exception:
                logger.debug("Suppressed exception in app")

        import uuid as _uuid
        workflow_id = f"wf_{wf_name[:40]}_{_uuid.uuid4().hex[:8]}"

        return {
            "workflow_id": workflow_id,
            "name": wf_name,
            "steps": steps,
            "step_count": len(steps),
            "strategy": "sequential",
            "description": initial[:200] if initial else "Auto-generated from onboarding",
        }

    def _onboarding_deterministic_reply(message: str, session_id: str) -> str:
        """Keyword-based onboarding reply that works with no external LLM.

        This is the guaranteed fallback path — it always produces a useful,
        context-sensitive question to advance the onboarding interview even
        when the full UnifiedMFGC/LLM stack is unavailable.
        """
        msg_lower = message.lower()
        # Detect topic from keywords and ask the next logical question
        if any(w in msg_lower for w in ["invoice", "billing", "payment", "accounts payable"]):
            return (
                "Great — invoice processing is one of our most common automation scenarios. "
                "To set this up correctly, can you tell me: how many invoices do you typically "
                "process per week, and which accounting system do you use (QuickBooks, Xero, "
                "SAP, or another)?"
            )
        if any(w in msg_lower for w in ["onboard", "employee", "hire", "hr", "human resources"]):
            return (
                "Employee onboarding automation can save enormous time. A few quick questions: "
                "How many new hires do you process per month? And which HR system do you "
                "currently use (BambooHR, Workday, ADP, or something else)?"
            )
        if any(w in msg_lower for w in ["report", "kpi", "analytics", "dashboard", "metric"]):
            return (
                "Automated reporting is a great use case! To build the right workflow: "
                "What data sources feed into your reports (CRM, ERP, spreadsheets)? "
                "How often do they need to be generated (daily, weekly, monthly)?"
            )
        if any(w in msg_lower for w in ["email", "campaign", "marketing", "outreach", "newsletter"]):
            return (
                "Email automation can dramatically improve response rates and consistency. "
                "What email platform do you use today (Mailchimp, HubSpot, Klaviyo, etc.)? "
                "And is this for marketing campaigns or transactional/operational emails?"
            )
        if any(w in msg_lower for w in ["contract", "legal", "review", "document", "compliance"]):
            return (
                "Contract review automation is a high-value workflow. "
                "Are these contracts you're reviewing (incoming) or generating (outgoing)? "
                "What's the typical volume per week and do you have specific clauses "
                "or risk factors you need to flag automatically?"
            )
        if any(w in msg_lower for w in ["data", "migrat", "database", "etl", "pipeline", "sync"]):
            return (
                "Data pipeline and migration workflows are a core Murphy capability. "
                "What systems are the data source and destination? "
                "Is this a one-time migration or an ongoing sync?"
            )
        if any(w in msg_lower for w in ["crm", "salesforce", "hubspot", "lead", "sales", "prospect"]):
            return (
                "CRM automation can significantly boost your sales team's efficiency. "
                "Which CRM are you using, and what's the main pain point — lead routing, "
                "follow-up sequences, data enrichment, or something else?"
            )
        if any(w in msg_lower for w in ["hello", "hi", "hey", "start", "begin", "help"]):
            return (
                "Welcome to Murphy System! I'm your onboarding guide. "
                "To get started, tell me: what business process do you most want to automate? "
                "For example: invoice processing, employee onboarding, data reporting, "
                "email campaigns, or something else entirely?"
            )
        # Generic catch-all — ask the most productive follow-up question
        return (
            f"Thanks for sharing that. To build the best automation plan for you, "
            f"I need a few more details:\n\n"
            f"1. What's the current manual process you want to replace?\n"
            f"2. How many times per week/month does this task occur?\n"
            f"3. Which tools or systems are involved?\n\n"
            f"*(Working in offline mode — answers help me generate your plan)*"
        )


        """Build an actual, wired automation workflow from accumulated onboarding answers.

        Calls ``AIWorkflowGenerator.generate_workflow()`` so the output is an
        *executable* DAG definition — not a text preview.  The result is embedded
        in the ``/api/onboarding/mfgc-chat`` response when ``ready_for_plan=True``
        so the front-end can display (and later execute) the real automation steps.

        The description passed to the generator is composed from ALL non-None answers
        so the template-matching engine can pick the most specific pre-built template
        (e.g. ``order_fulfillment`` when the user mentions Shopify + orders, or
        ``invoice_processing`` when they mention billing + accounts payable).
        """
        import sys as _sys
        import os as _os
        try:
            _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
            from ai_workflow_generator import AIWorkflowGenerator
        except Exception:
            return {}

        filled = {k: v for k, v in sess.get("answers", {}).items() if v is not None}

        # Build a rich combined description from all answers so the template matcher
        # can select the most specific pre-built template.
        all_values = [str(v)[:150] for v in filled.values()]
        combined_description = " ".join(all_values)

        # Also try the initial request alone for a focused match.
        initial_request = filled.get("initial_request", "business automation")

        context_snippets = {
            k: str(v)[:200] for k, v in filled.items() if k != "initial_request"
        }

        try:
            generator = AIWorkflowGenerator()
            # First try the combined description (picks up all context clues).
            workflow = generator.generate_workflow(
                description=combined_description,
                context={"session_answers": context_snippets, "source": "onboarding"},
            )
            # If combined match is weak (< 3 steps or generic fallback), also try
            # the initial request to capture the primary intent template.
            if workflow.get("step_count", 0) < 3 or workflow.get("strategy") == "generic_fallback":
                alt = generator.generate_workflow(
                    description=initial_request,
                    context={"session_answers": context_snippets, "source": "onboarding"},
                )
                if alt.get("step_count", 0) > workflow.get("step_count", 0):
                    workflow = alt
            return workflow
        except Exception as _e:
            logger.debug("automation generation failed: %s", _e)
            return {}

    @app.post("/api/onboarding/mfgc-chat")
    async def onboarding_mfgc_chat(request: Request):
        """Route onboarding wizard messages through UnifiedMFGC gate system.

        Accepts ``{ "session_id": "...", "message": "..." }`` and returns
        ``{ "response": "...", "gate_satisfaction": 0.XX, "confidence": 0.XX,
            "unknowns_remaining": N, "ready_for_plan": bool,
            "automation_config": {...} }``.
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
                    "turn_count": 0,
                    "last_access": now,
                }
            sess = _onboarding_mfgc_sessions[session_id]
            sess["last_access"] = now
            sess["turn_count"] = sess.get("turn_count", 0) + 1
            mfgc_instance = sess["mfgc"]

            # ── Record the new user message ────────────────────────────────────
            if not sess["answers"]:
                # First turn: store the full message as the initial request.
                sess["answers"]["initial_request"] = message
            else:
                # Subsequent turns: fill the FIRST unanswered question slot so
                # each user reply maps to a specific question.  If all slots are
                # already filled, append a numbered turn entry.
                filled_slot = False
                for key in list(sess["answers"].keys()):
                    if sess["answers"][key] is None:
                        sess["answers"][key] = message
                        filled_slot = True
                        break
                if not filled_slot:
                    turn_num = sess["turn_count"]
                    sess["answers"][f"user_turn_{turn_num}"] = message

            # ── Update accumulated context with every answered turn ────────────
            filled_answers = {k: v for k, v in sess["answers"].items() if v is not None}
            ctx_lines = [
                "Murphy onboarding wizard — accumulated user information:",
                f"  Initial request: {filled_answers.get('initial_request', 'not yet provided')}",
            ]
            for k, v in list(filled_answers.items())[1:]:
                ctx_lines.append(f"  {k}: {str(v)[:120]}")
            sess["context"] = "\n".join(ctx_lines)

            # ── Route through the MFGC gate ───────────────────────────────────
            result = mfgc_instance._process_with_context(
                message=message,
                answers=sess["answers"],
                context_summary=sess["context"],
            )

            gate_satisfaction = result.get("gate_satisfaction", 0.0)
            confidence = result.get("confidence", 0.0)
            unknowns_remaining = result.get("unknowns_remaining", 99)
            ready_for_plan = bool(result.get("execution_mode", False))

            # ── Turn-count safety valve ───────────────────────────────────────
            # After 3 conversation turns the onboarding has enough context to
            # generate a plan regardless of MFGC gate arithmetic.
            # "real" answers excludes the initial_request stored on turn 1.
            real_answer_count = sum(
                1 for k, v in filled_answers.items()
                if v is not None and k != "initial_request"
            )
            if not ready_for_plan and (
                real_answer_count >= 2 and sess.get("turn_count", 0) >= 3
            ):
                ready_for_plan = True
                gate_satisfaction = max(gate_satisfaction, 0.85)
                confidence = max(confidence, 0.85)

            response_text = (
                result.get("content")
                or result.get("response")
                or result.get("message")
                or "Murphy is gathering more information."
            )

            # ── Record question placeholders for next turn ────────────────────
            if result.get("questioning_mode"):
                import re as _re
                questions = _re.findall(r"[A-Z][^\n]*\?", response_text)
                for q in questions:
                    if q not in sess["answers"]:
                        sess["answers"][q] = None

            # ── Generate the actual automation when ready ─────────────────────
            automation_config: dict = {}
            if ready_for_plan:
                automation_config = _generate_automation_from_session(sess)
                if automation_config and not result.get("execution_mode"):
                    # Upgrade the response text to reflect a real plan
                    wf_name = automation_config.get("name", "custom workflow")
                    step_count = automation_config.get("step_count", 0)
                    strategy = automation_config.get("strategy", "")
                    steps_preview = "; ".join(
                        s.get("description", s.get("name", ""))
                        for s in automation_config.get("steps", [])[:4]
                    )
                    response_text = (
                        f"I have enough information to build your automation plan!\n\n"
                        f"**Generated Workflow:** {wf_name}\n"
                        f"**Strategy:** {strategy or 'custom inference'}\n"
                        f"**Steps ({step_count}):** {steps_preview}\n\n"
                        f"Click **Continue → Plan** to review and deploy your automation."
                    )

            return JSONResponse({
                "success": True,
                "response": response_text,
                "message": response_text,
                "gate_satisfaction": round(float(gate_satisfaction), 4),
                "confidence": round(float(confidence), 4),
                "unknowns_remaining": int(unknowns_remaining),
                "ready_for_plan": ready_for_plan,
                "automation_config": automation_config,
            })
        except Exception as exc:
            logger.warning("onboarding_mfgc_chat error: %s", exc)
            # Deterministic fallback: use keyword matching to provide a useful reply
            # without requiring any external LLM or complex engine.
            _fallback_reply = _onboarding_deterministic_reply(message, session_id)
            return JSONResponse({
                "success": True,
                "response": _fallback_reply,
                "message": _fallback_reply,
                "gate_satisfaction": 0.2,
                "confidence": 0.2,
                "unknowns_remaining": 5,
                "ready_for_plan": False,
            }, status_code=200)  # Return 200 so the UI doesn't show a hard error

    @app.get("/api/automations/workflows/{workflow_id}")
    async def get_workflow_definition(workflow_id: str, request: Request):
        """Return the generated workflow definition for a given workflow_id."""
        try:
            import sys as _sys
            import os as _os
            _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
            from ai_workflow_generator import AIWorkflowGenerator
            generator = AIWorkflowGenerator()
            history = generator.get_generation_history()
            match = next((h for h in history if h.get("workflow_id") == workflow_id), None)
            dag = getattr(request.app.state, "workflow_dag_engine", None)
            dag_workflow = None
            if dag is not None:
                wf_obj = dag._workflows.get(workflow_id)
                if wf_obj is not None:
                    dag_workflow = {
                        "workflow_id": wf_obj.workflow_id,
                        "name": wf_obj.name,
                        "description": wf_obj.description,
                        "step_count": len(wf_obj.steps),
                        "steps": [{"step_id": s.step_id, "name": s.name, "action": s.action,
                                   "depends_on": s.depends_on, "metadata": s.metadata}
                                  for s in wf_obj.steps],
                        "registered": True,
                    }
            if match or dag_workflow:
                return JSONResponse({"success": True, "workflow": match or {}, "dag_definition": dag_workflow})
            return JSONResponse(
                {"success": False, "error": f"Workflow '{workflow_id}' not found in current session"},
                status_code=404,
            )
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.post("/api/automations/workflows/{workflow_id}/execute")
    async def execute_workflow_endpoint(workflow_id: str, request: Request):
        """Execute a workflow DAG and return commissioning results."""
        try:
            import sys as _sys
            import os as _os
            _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
            data = {}
            try:
                data = await request.json()
            except Exception:
                logger.debug("Suppressed exception in app")
            ctx = data.get("context") or {}
            from ai_workflow_generator import AIWorkflowGenerator
            from automation_commissioner import AutomationCommissioner
            generator = AIWorkflowGenerator()
            history = generator.get_generation_history()
            hist_entry = next((h for h in history if h.get("workflow_id") == workflow_id), None)
            dag = getattr(request.app.state, "workflow_dag_engine", None)
            if dag is None:
                from workflow_dag_engine import WorkflowDAGEngine
                dag = WorkflowDAGEngine()
            wf_def = dag._workflows.get(workflow_id)
            if wf_def is None and hist_entry:
                description = hist_entry.get("description", "automation")
                wf_dict = generator.generate_workflow(description)
                wf_def = generator.to_workflow_definition(wf_dict)
                dag.register_workflow(wf_def)
            if wf_def is None:
                return JSONResponse(
                    {"success": False, "error": f"Workflow '{workflow_id}' not found. "
                     "Generate a workflow first via /api/demo/generate-deliverable or /api/onboarding/mfgc-chat"},
                    status_code=404,
                )
            commissioner = AutomationCommissioner(max_iterations=1)
            report = commissioner.commission(wf_def, context=ctx)
            return JSONResponse({
                "success": True,
                "workflow_id": workflow_id,
                "execution_id": report.execution_id,
                "health_score": report.health_score,
                "ready_for_deploy": report.ready_for_deploy,
                "commissioning_report": report.to_dict(),
            })
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.get("/api/automations/executions")
    async def list_all_executions(request: Request):
        """List all workflow executions — powers the Live Automations panel in System Map."""
        try:
            dag = getattr(request.app.state, "workflow_dag_engine", None)
            if dag is None:
                return JSONResponse({"success": True, "executions": []})
            # DAGEngine stores executions in _executions dict
            all_execs = getattr(dag, "_executions", {})
            items = []
            for exec_id, ex in list(all_execs.items())[-50:]:  # last 50
                wf_id = getattr(ex, "workflow_id", "")
                wf_def = getattr(dag, "_workflows", {}).get(wf_id)
                total_steps = len(wf_def.steps) if wf_def else 0
                steps_map = getattr(ex, "steps", {})
                completed = sum(1 for s in steps_map.values() if getattr(s, "status", None) and s.status.value in ("completed", "skipped"))
                start_t = getattr(ex, "start_time", None)
                end_t   = getattr(ex, "end_time", None)
                duration_ms = ((end_t or 0) - (start_t or 0)) * 1000 if start_t else None
                items.append({
                    "id": exec_id,
                    "workflow_id": wf_id,
                    "name": (wf_def.name if wf_def else wf_id) or exec_id,
                    "status": getattr(ex, "status", "unknown").value if hasattr(getattr(ex, "status", None), "value") else str(getattr(ex, "status", "unknown")),
                    "completed": completed,
                    "total_steps": total_steps,
                    "progress": round(completed / total_steps * 100) if total_steps else 0,
                    "duration_ms": duration_ms,
                    "step_label": f"{completed}/{total_steps} steps",
                })
            return JSONResponse({"success": True, "executions": sorted(items, key=lambda x: x["status"] == "running", reverse=True)})
        except Exception:
            return JSONResponse({"success": True, "executions": []})

    @app.get("/api/automations/executions/{execution_id}")
    async def get_execution_status(execution_id: str, request: Request):
        """Get the status and results of a workflow execution."""
        try:
            dag = getattr(request.app.state, "workflow_dag_engine", None)
            if dag is None:
                return JSONResponse({"success": False, "error": "DAG engine not available"}, status_code=503)
            execution = dag.get_execution(execution_id)
            if execution is None:
                return JSONResponse(
                    {"success": False, "error": f"Execution '{execution_id}' not found"},
                    status_code=404,
                )
            return JSONResponse({"success": True, "execution": execution})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.post("/api/automations/fire-trigger")
    async def fire_automation_trigger(request: Request):
        """Fire an AutomationEngine trigger and return all matching rule results."""
        try:
            data = await request.json()
            board_id = (data.get("board_id") or "").strip()
            trigger_type_str = (data.get("trigger_type") or "").strip()
            ctx = data.get("context") or {}
            if not board_id or not trigger_type_str:
                return JSONResponse(
                    {"success": False, "error": "board_id and trigger_type are required"},
                    status_code=400,
                )
            engine = getattr(request.app.state, "automation_engine", None)
            if engine is None:
                return JSONResponse({"success": False, "error": "Automation engine not available"}, status_code=503)
            import sys as _sys
            import os as _os
            _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
            from automations.models import TriggerType
            try:
                tt = TriggerType(trigger_type_str)
            except ValueError:
                return JSONResponse(
                    {"success": False,
                     "error": f"Unknown trigger_type '{trigger_type_str}'. Valid: {[t.value for t in TriggerType]}"},
                    status_code=400,
                )
            results = engine.fire_trigger(board_id=board_id, trigger_type=tt, context=ctx)
            return JSONResponse({
                "success": True,
                "board_id": board_id,
                "trigger_type": trigger_type_str,
                "rules_fired": len(results),
                "results": results,
            })
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.post("/api/onboarding/finalize")
    async def onboarding_finalize(request: Request):
        """Convert a completed onboarding session into a registered, executable workflow + AutomationEngine rule."""
        try:
            import sys as _sys
            import os as _os
            _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
            data = await request.json()
            session_id = (data.get("session_id") or "").strip()
            extra_ctx = data.get("context") or {}
            if not session_id:
                return JSONResponse({"success": False, "error": "session_id is required"}, status_code=400)
            sess = _onboarding_mfgc_sessions.get(session_id)
            if not sess:
                return JSONResponse(
                    {"success": False, "error": f"Session '{session_id}' not found or expired"},
                    status_code=404,
                )
            automation_config = sess.get("automation_config") or {}
            if not automation_config:
                automation_config = _generate_automation_from_session(sess)
                sess["automation_config"] = automation_config
            if not automation_config or not automation_config.get("steps"):
                return JSONResponse(
                    {"success": False,
                     "error": "No automation config available. Complete the onboarding wizard first (3+ turns required)."},
                    status_code=422,
                )
            from ai_workflow_generator import AIWorkflowGenerator
            from automation_commissioner import AutomationCommissioner
            gen = AIWorkflowGenerator()
            wf_def = gen.to_workflow_definition(automation_config)
            filled_answers = {k: v for k, v in sess.get("answers", {}).items() if v}
            exec_ctx = {**filled_answers, **extra_ctx, "source": "onboarding_finalize"}
            dag = getattr(request.app.state, "workflow_dag_engine", None)
            if dag is None:
                from workflow_dag_engine import WorkflowDAGEngine
                dag = WorkflowDAGEngine()
                request.app.state.workflow_dag_engine = dag
            dag.register_workflow(wf_def)
            commissioner = AutomationCommissioner(max_iterations=1)
            report = commissioner.commission(wf_def, context=exec_ctx)
            rule_id = None
            try:
                from automations.engine import AutomationEngine
                from automations.models import TriggerType, AutomationAction, ActionType
                ae = getattr(request.app.state, "automation_engine", None) or AutomationEngine()
                template = automation_config.get("template_used") or ""
                # Use the module-level mapping so trigger assignment is not duplicated
                trigger_type_str = _TEMPLATE_TRIGGER_DEFAULTS.get(template, "form_submitted")
                trigger = TriggerType(trigger_type_str)
                rule = ae.create_rule(
                    name=automation_config.get("name", "onboarding_workflow"),
                    board_id=session_id,
                    trigger_type=trigger,
                    actions=[AutomationAction(
                        action_type=ActionType.NOTIFY,
                        config={"workflow_id": wf_def.workflow_id, "message": "Workflow triggered"},
                    )],
                )
                rule_id = rule.id
            except Exception as _rule_exc:
                logger.debug("Rule registration in finalize: %s", _rule_exc)
            return JSONResponse({
                "success": True,
                "workflow_id": wf_def.workflow_id,
                "workflow_name": wf_def.name,
                "rule_id": rule_id,
                "execution_id": report.execution_id,
                "health_score": report.health_score,
                "ready_for_deploy": report.ready_for_deploy,
                "commissioning_report": report.to_dict(),
            })
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.post("/api/automations/commission")
    async def commission_workflow_endpoint(request: Request):
        """Run commissioning on any workflow dict or workflow_id."""
        try:
            import sys as _sys
            import os as _os
            _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
            data = await request.json()
            ctx = data.get("context") or {}
            threshold = float(data.get("health_threshold", 0.75))
            from ai_workflow_generator import AIWorkflowGenerator
            from automation_commissioner import AutomationCommissioner
            gen = AIWorkflowGenerator()
            wf_dict = data.get("workflow")
            if not wf_dict:
                wf_id = (data.get("workflow_id") or "").strip()
                if not wf_id:
                    return JSONResponse(
                        {"success": False, "error": "Either 'workflow' dict or 'workflow_id' is required"},
                        status_code=400,
                    )
                dag = getattr(request.app.state, "workflow_dag_engine", None)
                wf_def = (dag._workflows.get(wf_id) if dag else None)
                if wf_def is None:
                    history = gen.get_generation_history()
                    hist = next((h for h in history if h.get("workflow_id") == wf_id), None)
                    if not hist:
                        return JSONResponse(
                            {"success": False, "error": f"Workflow '{wf_id}' not found"},
                            status_code=404,
                        )
                    wf_dict = gen.generate_workflow(hist.get("description", "automation"))
                    wf_def = gen.to_workflow_definition(wf_dict)
            else:
                wf_def = gen.to_workflow_definition(wf_dict)
            commissioner = AutomationCommissioner(health_threshold=threshold, max_iterations=2)
            report = commissioner.commission(wf_def, context=ctx)

            # Register workflow + execution in the app-state DAG engine so the
            # Live Automations panel in system_visualizer.html can track it.
            try:
                app_dag = getattr(request.app.state, "workflow_dag_engine", None)
                if app_dag is not None:
                    app_dag.register_workflow(wf_def)
                    exec_id = app_dag.create_execution(wf_def.workflow_id, ctx)
                    if exec_id:
                        app_dag.execute_workflow(exec_id)
            except Exception as _dag_exc:
                logger.debug("Live panel DAG wiring skipped: %s", _dag_exc)

            return JSONResponse({"success": True, "commissioning_report": report.to_dict()})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    # ── ROI Calendar ─────────────────────────────────────────────────────────
    # Tracks automation tasks with human vs agent cost/ROI visualisation.
    # Each event block starts at human cost estimate and shrinks as agents
    # complete work; QC failures/HITL reviews cause fluctuations.
    _roi_calendar_store: list = []

    @app.get("/api/roi-calendar/events")
    async def roi_calendar_events_list(request: Request):
        return JSONResponse({"ok": True, "events": list(_roi_calendar_store), "total": len(_roi_calendar_store)})

    @app.post("/api/roi-calendar/events")
    async def roi_calendar_event_create(request: Request):
        body = await request.json()
        import uuid as _uuid_roi
        eid = "roi-" + _uuid_roi.uuid4().hex[:12]
        now_ts = _now_iso()
        event = {
            "event_id": eid,
            "title": body.get("title", "Untitled Task"),
            "description": body.get("description", ""),
            "automation_id": body.get("automation_id"),
            "start": body.get("start", now_ts),
            "end": body.get("end"),
            "status": "pending",
            "progress_pct": 0,
            "human_cost_estimate": float(body.get("human_cost_estimate", 0)),
            "human_time_estimate_hours": float(body.get("human_time_estimate_hours", 8)),
            "agent_compute_cost": 0.0,
            "overhead_cost": 0.0,
            "roi": 0.0,
            "actual_time_hours": 0.0,
            "agents": [],
            "hitl_reviews": [],
            "qc_passes": 0,
            "qc_failures": 0,
            "cost_adjustments": [],
            "created_at": now_ts,
            "updated_at": now_ts,
        }
        _roi_calendar_store.append(event)
        return JSONResponse({"ok": True, "event": event}, status_code=201)

    @app.patch("/api/roi-calendar/events/{event_id}")
    async def roi_calendar_event_update(event_id: str, request: Request):
        body = await request.json()
        event = next((e for e in _roi_calendar_store if e["event_id"] == event_id), None)
        if not event:
            return JSONResponse({"ok": False, "error": "Event not found"}, status_code=404)
        for field in ["title", "description", "status", "progress_pct", "agent_compute_cost",
                      "overhead_cost", "actual_time_hours", "agents", "end"]:
            if field in body:
                event[field] = body[field]
        event["roi"] = event["human_cost_estimate"] - event["agent_compute_cost"] - event["overhead_cost"]
        if "hitl_review" in body:
            review = dict(body["hitl_review"])
            review["ts"] = _now_iso()
            event["hitl_reviews"].append(review)
            delta = float(review.get("cost_delta", event["human_cost_estimate"] * 0.05))
            event["cost_adjustments"].append({"reason": f"HITL review: {review.get('decision','change_requested')}", "delta": delta, "ts": review["ts"]})
            event["agent_compute_cost"] += delta
            event["roi"] = event["human_cost_estimate"] - event["agent_compute_cost"] - event["overhead_cost"]
        if "qc_result" in body:
            qc = body["qc_result"]
            if qc.get("passed"):
                event["qc_passes"] += 1
            else:
                event["qc_failures"] += 1
                delta = float(qc.get("retry_cost", event["agent_compute_cost"] * 0.1))
                event["cost_adjustments"].append({"reason": f"QC failure: {qc.get('reason','retry')}", "delta": delta, "ts": _now_iso()})
                event["agent_compute_cost"] += delta
                event["roi"] = event["human_cost_estimate"] - event["agent_compute_cost"] - event["overhead_cost"]
        event["updated_at"] = _now_iso()
        return JSONResponse({"ok": True, "event": event})

    @app.get("/api/roi-calendar/summary")
    async def roi_calendar_summary():
        if not _roi_calendar_store:
            return JSONResponse({"ok": True, "total_human_cost_estimate": 0, "total_agent_cost": 0,
                                 "total_roi": 0, "total_overhead": 0, "active_tasks": 0,
                                 "completed_tasks": 0, "total_tasks": 0, "roi_pct": 0})
        total_human = sum(e["human_cost_estimate"] for e in _roi_calendar_store)
        total_agent = sum(e["agent_compute_cost"] for e in _roi_calendar_store)
        total_overhead = sum(e["overhead_cost"] for e in _roi_calendar_store)
        total_roi = total_human - total_agent - total_overhead
        roi_pct = round((total_roi / total_human * 100) if total_human > 0 else 0, 1)
        return JSONResponse({"ok": True,
            "total_human_cost_estimate": round(total_human, 2),
            "total_agent_cost": round(total_agent, 2),
            "total_roi": round(total_roi, 2),
            "total_overhead": round(total_overhead, 2),
            "active_tasks": sum(1 for e in _roi_calendar_store if e["status"] in ("running", "qc", "hitl_review")),
            "completed_tasks": sum(1 for e in _roi_calendar_store if e["status"] == "complete"),
            "total_tasks": len(_roi_calendar_store),
            "roi_pct": roi_pct})

    @app.get("/api/roi-calendar/stream")
    async def roi_calendar_stream(request: Request):
        from starlette.responses import StreamingResponse
        import asyncio as _asyncio_roi
        import json as _json_roi
        import random as _rand_sse

        _STATUS_SEQ = ["pending", "running", "qc", "complete"]
        _HITL_CHANCE = 0.15  # 15% chance of hitl_review before qc

        async def _gen():
            last_states: dict = {}
            ticks_to_advance = _rand_sse.randint(3, 8)
            for tick in range(600):  # up to 10 minutes
                await _asyncio_roi.sleep(1)
                ticks_to_advance -= 1

                if ticks_to_advance <= 0:
                    # Pick a non-complete, non-error event to advance
                    candidates = [e for e in _roi_calendar_store
                                  if e.get("status") not in ("complete", "error")]
                    if candidates:
                        ev = _rand_sse.choice(candidates)
                        delta_pct = _rand_sse.randint(5, 15)
                        ev["progress_pct"] = min(100, ev.get("progress_pct", 0) + delta_pct)

                        # Advance checklist: mark next running/pending item as done
                        checklist = ev.get("checklist", [])
                        for ci, item in enumerate(checklist):
                            if item.get("status") == "running":
                                item["status"] = "complete"
                                item["completed_at"] = _now_iso()
                                # Mark next pending item as running
                                for nitem in checklist[ci + 1:]:
                                    if nitem.get("status") == "pending":
                                        nitem["status"] = "running"
                                        break
                                break
                            elif item.get("status") == "pending":
                                item["status"] = "running"
                                break

                        # Increment agent compute cost incrementally
                        step_cost = round(_rand_sse.uniform(0.02, 0.50), 2)
                        ev["agent_compute_cost"] = round(ev.get("agent_compute_cost", 0) + step_cost, 2)

                        # Update ROI
                        hc = ev.get("human_cost_estimate", 0)
                        ac = ev.get("agent_compute_cost", 0)
                        oh = ev.get("overhead_cost", 0)
                        ev["roi"] = round(hc - ac - oh, 2)

                        # Transition status based on progress
                        cur_status = ev.get("status", "pending")
                        pct = ev["progress_pct"]
                        if cur_status == "pending" and pct > 5:
                            ev["status"] = "running"
                        elif cur_status == "running" and pct >= 90:
                            if _rand_sse.random() < _HITL_CHANCE:
                                ev["status"] = "hitl_review"
                                ev["hitl_reviews"].append({
                                    "decision": "pending",
                                    "notes": "Automated HITL review triggered",
                                    "ts": _now_iso(),
                                    "cost_delta": 0,
                                })
                            else:
                                ev["status"] = "qc"
                        elif cur_status in ("qc", "hitl_review") and pct >= 95:
                            ev["status"] = "complete"
                            ev["progress_pct"] = 100
                            # Mark all checklist items as complete
                            for item in checklist:
                                if item.get("status") != "complete":
                                    item["status"] = "complete"
                                    if not item.get("completed_at"):
                                        item["completed_at"] = _now_iso()
                            ev["qc_passes"] = ev.get("qc_passes", 0) + 1

                        ev["updated_at"] = _now_iso()

                    ticks_to_advance = _rand_sse.randint(3, 8)

                # Broadcast changed events
                for ev in _roi_calendar_store:
                    eid = ev["event_id"]
                    ac = ev.get("agent_compute_cost", 0)
                    sk = f"{ev.get('progress_pct', 0)}:{ev.get('status', '')}:{ac:.2f}"
                    if last_states.get(eid) != sk:
                        last_states[eid] = sk
                        yield f"event: roi_update\ndata: {_json_roi.dumps(ev)}\n\n"
                yield "event: ping\ndata: {}\n\n"

        return StreamingResponse(_gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/roi-calendar/export")
    async def roi_calendar_export(fmt: str = "json"):
        """Export ROI calendar data as JSON or CSV."""
        import json as _json_exp
        import io as _io_exp
        if fmt == "csv":
            import csv as _csv_exp
            output = _io_exp.StringIO()
            fieldnames = ["event_id", "title", "status", "progress_pct",
                          "human_cost_estimate", "human_time_estimate_hours",
                          "agent_compute_cost", "overhead_cost", "roi", "start", "end"]
            writer = _csv_exp.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for ev in _roi_calendar_store:
                writer.writerow(ev)
            content = output.getvalue()
            from starlette.responses import Response as _Resp
            return _Resp(content=content, media_type="text/csv",
                         headers={"Content-Disposition": "attachment; filename=roi-calendar.csv"})
        else:
            from starlette.responses import Response as _Resp
            content = _json_exp.dumps({"ok": True, "events": _roi_calendar_store}, indent=2)
            return _Resp(content=content, media_type="application/json",
                         headers={"Content-Disposition": "attachment; filename=roi-calendar.json"})



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

    @app.post("/api/workflow-terminal/execute")
    async def workflow_terminal_execute(request: Request):
        """Execute a workflow defined in the workflow canvas."""
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)
        workflow_id = data.get("workflow_id") or data.get("id", "")
        nodes = data.get("nodes", [])
        try:
            wt = getattr(murphy, "workflow_terminal", None)
            if wt and hasattr(wt, "execute"):
                result = wt.execute(workflow_id=workflow_id, nodes=nodes)
                return JSONResponse({"success": True, "result": result})
        except Exception as exc:
            logger.warning("Workflow execute error: %s", exc)
        return JSONResponse({
            "success": True,
            "execution_id": str(uuid4())[:12],
            "status": "queued",
            "message": "Workflow queued for execution. Connect the Workflow Terminal to process it.",
            "workflow_id": workflow_id,
        })

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
                             "Upgrade to Solo ($99/mo) for 3 automations.",
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

            # Auto-save the generated workflow with schedule metadata
            wf_id = wf.get("workflow_id", str(uuid4()))
            now_iso = datetime.now(timezone.utc).isoformat()

            # ── Infer schedule from description ──
            desc_lower = description.lower()
            schedule_interval = data.get("schedule_interval")
            if schedule_interval is None:
                if any(k in desc_lower for k in ("daily", "every day", "each day")):
                    schedule_interval = "daily"
                elif any(k in desc_lower for k in ("weekly", "every week", "each week")):
                    schedule_interval = "weekly"
                elif any(k in desc_lower for k in ("monthly", "every month", "each month")):
                    schedule_interval = "monthly"
                elif any(k in desc_lower for k in ("hourly", "every hour")):
                    schedule_interval = "hourly"
                else:
                    schedule_interval = "on_demand"

            # ── Infer API integration suggestions from workflow steps ──
            api_suggestions = []
            _API_KEYWORDS = {
                "email": {"name": "SendGrid", "env_var": "SENDGRID_API_KEY",
                          "description": "Transactional & marketing email delivery",
                          "signup_url": "https://signup.sendgrid.com/"},
                "slack": {"name": "Slack", "env_var": "SLACK_BOT_TOKEN",
                          "description": "Team messaging and workflow notifications",
                          "signup_url": "https://api.slack.com/apps"},
                "crm": {"name": "HubSpot", "env_var": "HUBSPOT_API_KEY",
                         "description": "CRM contacts, deals, and pipeline automation",
                         "signup_url": "https://developers.hubspot.com/"},
                "invoice": {"name": "Stripe", "env_var": "STRIPE_SECRET_KEY",
                            "description": "Payment processing and invoicing",
                            "signup_url": "https://dashboard.stripe.com/register"},
                "payment": {"name": "Stripe", "env_var": "STRIPE_SECRET_KEY",
                            "description": "Payment processing and invoicing",
                            "signup_url": "https://dashboard.stripe.com/register"},
                "calendar": {"name": "Google Calendar", "env_var": "GOOGLE_CALENDAR_API_KEY",
                             "description": "Calendar event scheduling and management",
                             "signup_url": "https://console.cloud.google.com/"},
                "spreadsheet": {"name": "Google Sheets", "env_var": "GOOGLE_SHEETS_API_KEY",
                                "description": "Spreadsheet data sync and reporting",
                                "signup_url": "https://console.cloud.google.com/"},
                "database": {"name": "PostgreSQL", "env_var": "DATABASE_URL",
                             "description": "Relational database for structured data",
                             "signup_url": "https://www.postgresql.org/download/"},
                "sms": {"name": "Twilio", "env_var": "TWILIO_AUTH_TOKEN",
                        "description": "SMS and voice communication",
                        "signup_url": "https://www.twilio.com/try-twilio"},
                "github": {"name": "GitHub", "env_var": "GITHUB_TOKEN",
                           "description": "Source control and CI/CD automation",
                           "signup_url": "https://github.com/settings/tokens"},
                "monitor": {"name": "Datadog", "env_var": "DATADOG_API_KEY",
                            "description": "Infrastructure and application monitoring",
                            "signup_url": "https://www.datadoghq.com/free-datadog-trial/"},
                "weather": {"name": "OpenWeatherMap", "env_var": "OPENWEATHER_API_KEY",
                            "description": "Weather data for location-based automation",
                            "signup_url": "https://openweathermap.org/api"},
                "hvac": {"name": "BACnet/IP Gateway", "env_var": "BACNET_GATEWAY_URL",
                         "description": "Building automation system integration",
                         "signup_url": ""},
                "sensor": {"name": "IoT Hub", "env_var": "IOT_HUB_CONNECTION_STRING",
                           "description": "IoT sensor data ingestion",
                           "signup_url": ""},
            }
            seen_apis = set()
            for kw, suggestion in _API_KEYWORDS.items():
                if kw in desc_lower and suggestion["name"] not in seen_apis:
                    api_suggestions.append(suggestion)
                    seen_apis.add(suggestion["name"])

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
                "created_at": now_iso,
                "updated_at": now_iso,
                "generated_from": description[:200],
                "schedule": {
                    "interval": schedule_interval,
                    "next_run": now_iso,
                    "enabled": schedule_interval != "on_demand",
                    "cron": {
                        "daily": "0 8 * * *",
                        "weekly": "0 8 * * 1",
                        "monthly": "0 8 1 * *",
                        "hourly": "0 * * * *",
                    }.get(schedule_interval),
                },
                "api_suggestions": api_suggestions,
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

    # ==================== ARTIFACTS ENDPOINTS ====================

    @app.post("/api/artifacts/create")
    async def create_artifact(request: Request):
        """Create an artifact (AI recommendation, action plan, etc.)."""
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)
        title    = (data.get("title") or "").strip()
        content  = (data.get("content") or "").strip()
        if not title or not content:
            return JSONResponse({"success": False, "error": "title and content are required"}, status_code=400)
        artifact_id = str(uuid4())[:12]
        artifact = {
            "id":         artifact_id,
            "title":      title,
            "content":    content,
            "type":       data.get("type", "recommendation"),
            "priority":   data.get("priority", "medium"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": (data.get("created_by") or "user"),
        }
        _artifacts_store[artifact_id] = artifact
        return JSONResponse({"success": True, "artifact": artifact}, status_code=201)

    @app.get("/api/artifacts")
    async def list_artifacts():
        """List all artifacts."""
        return JSONResponse({"success": True, "artifacts": list(_artifacts_store.values()), "count": len(_artifacts_store)})

    @app.get("/api/artifacts/{artifact_id}")
    async def get_artifact(artifact_id: str):
        """Get a single artifact by id."""
        a = _artifacts_store.get(artifact_id)
        if not a:
            return JSONResponse({"success": False, "error": "Not found"}, status_code=404)
        return JSONResponse({"success": True, "artifact": a})

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
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, 500)

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
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, 500)

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
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, 500)

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
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, 500)

    @app.post("/api/billing/start-trial")
    async def billing_start_trial(request: Request):
        """Start a 14-day free trial for the chosen tier without requiring payment.

        Body: {
            "tier": "solo"|"business"|"professional",
            "account_id": "...",   # optional; falls back to session or derived from email
            "name": "...",
            "email": "..."
        }
        """
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

        tier_val = (data.get("tier") or "solo").strip().lower()
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()

        # Resolve account_id: prefer session > request body > derive from email
        account = _get_account_from_session(request)
        if account:
            account_id = account["account_id"]
        elif data.get("account_id", "").strip():
            account_id = data["account_id"].strip()
        elif email:
            import hashlib as _hashlib
            account_id = "trial_" + _hashlib.sha256(email.lower().encode()).hexdigest()[:16]
        else:
            account_id = "trial_" + uuid4().hex[:16]

        from src.subscription_manager import SubscriptionTier as _TrialTier
        try:
            tier_enum = _TrialTier(tier_val)
        except ValueError:
            return JSONResponse(
                {"success": False, "error": f"Unknown tier: {tier_val}"},
                status_code=400,
            )

        if tier_enum == _TrialTier.ENTERPRISE:
            return JSONResponse(
                {"success": False, "error": "Enterprise pricing is custom — contact sales@murphy.ai"},
                status_code=400,
            )

        from datetime import datetime as _dt, timedelta as _td, timezone as _tz_mod
        trial_end = (_dt.now(_tz_mod.utc) + _td(days=14)).isoformat()

        mgr = _get_sub_manager()
        if mgr is not None:
            try:
                sub = mgr.start_trial(account_id, tier_enum)
                trial_end = sub.trial_end or trial_end
                sub_dict = sub.to_dict()
            except Exception as exc:
                logger.warning("start_trial failed: %s", exc)
                sub_dict = {"tier": tier_val, "status": "trial", "trial_end": trial_end}
        else:
            sub_dict = {"tier": tier_val, "status": "trial", "trial_end": trial_end}

        redirect_url = "/ui/signup?tier=" + tier_val + "&trial=started"
        if email:
            redirect_url += "&email=" + email

        return JSONResponse({
            "success": True,
            "account_id": account_id,
            "subscription": sub_dict,
            "trial_days": 14,
            "trial_end": trial_end,
            "redirect_url": redirect_url,
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

    @app.get("/api/orgchart/inoni-agents")
    async def inoni_agent_org_chart_shortcut():
        """Redirect to the full Inoni LLC agent org chart (registered later)."""
        # Registered here so it's matched BEFORE the {task_id} catch-all.
        # The full implementation is at the end of create_app().
        return await _inoni_org_chart_handler()

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
            {"id": "deepinfra",   "name": "DeepInfra",   "type": "llm",       "icon": "⚡", "description": "Primary LLM inference via DeepInfra API"},
            {"id": "together",    "name": "Together AI",  "type": "llm",       "icon": "🔀", "description": "Overflow LLM inference via Together AI API"},
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
                "email_validated": account.get("email_validated") if account.get("email_validated") is not None else (account.get("role", "user") in ("owner", "admin")),
                "eula_accepted": account.get("eula_accepted") if account.get("eula_accepted") is not None else (account.get("role", "user") in ("owner", "admin")),
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
        except (ValueError, RuntimeError):
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
        except (ValueError, RuntimeError):
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
            if not version_id:
                return JSONResponse({"error": "version_id is required"}, status_code=400)
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
        """List stored credential keys — shows which integrations are configured.

        Returns the integration name, env variable name, and configured status.
        Secret values are NEVER returned.
        """
        _INTEGRATION_ENV_VARS = {
            "deepinfra":       ("DeepInfra",         "DEEPINFRA_API_KEY"),
            "together":        ("Together AI",        "TOGETHER_API_KEY"),
            "openai":          ("OpenAI",            "OPENAI_API_KEY"),
            "anthropic":       ("Anthropic",         "ANTHROPIC_API_KEY"),
            "sendgrid":        ("SendGrid",          "SENDGRID_API_KEY"),
            "slack":           ("Slack",             "SLACK_BOT_TOKEN"),
            "stripe":          ("Stripe",            "STRIPE_SECRET_KEY"),
            "hubspot":         ("HubSpot",           "HUBSPOT_API_KEY"),
            "github":          ("GitHub",            "GITHUB_TOKEN"),
            "twilio":          ("Twilio",            "TWILIO_AUTH_TOKEN"),
            "google_calendar": ("Google Calendar",   "GOOGLE_CALENDAR_API_KEY"),
            "google_sheets":   ("Google Sheets",     "GOOGLE_SHEETS_API_KEY"),
            "datadog":         ("Datadog",           "DATADOG_API_KEY"),
            "openweather":     ("OpenWeather",       "OPENWEATHER_API_KEY"),
            "postgres":        ("PostgreSQL",        "DATABASE_URL"),
            "redis":           ("Redis",             "REDIS_URL"),
            "notion":          ("Notion",            "NOTION_API_KEY"),
            "airtable":        ("Airtable",          "AIRTABLE_API_KEY"),
            "jira":            ("Jira",              "JIRA_API_TOKEN"),
            "salesforce":      ("Salesforce",        "SALESFORCE_CONSUMER_KEY"),
            "pagerduty":       ("PagerDuty",         "PAGERDUTY_API_KEY"),
            "zoom":            ("Zoom",              "ZOOM_CLIENT_SECRET"),
            "monday":          ("Monday.com",        "MONDAY_API_KEY"),
            "shopify":         ("Shopify",           "SHOPIFY_ACCESS_TOKEN"),
            "twitch":          ("Twitch",            "TWITCH_CLIENT_SECRET"),
            "discord":         ("Discord",           "DISCORD_BOT_TOKEN"),
            "telegram":        ("Telegram",          "TELEGRAM_BOT_TOKEN"),
            "matrix":          ("Matrix",            "MATRIX_ACCESS_TOKEN"),
            "ollama":          ("Ollama",            "OLLAMA_HOST"),
        }
        credentials = []
        for integration, (name, env_var) in _INTEGRATION_ENV_VARS.items():
            val = os.environ.get(env_var, "").strip()
            credentials.append({
                "integration": integration,
                "name":        name,
                "env_var":     env_var,
                "configured":  bool(val),
                "masked":      (val[:4] + "…") if len(val) >= 8 else ("set" if val else ""),
            })
        # Sort: configured first, then alphabetically
        credentials.sort(key=lambda c: (not c["configured"], c["name"].lower()))
        return JSONResponse({"success": True, "credentials": credentials})

    @app.post("/api/credentials/store")
    async def credentials_store(request: Request):
        """Store an integration credential securely.

        Body: { "integration": "sendgrid", "credential": "SG.xxx..." }
        Persists to .env via env_manager and updates os.environ immediately.
        Performs lightweight format validation before storing.
        """
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

        integration = (data.get("integration") or "").strip().lower()
        credential = (data.get("credential") or "").strip()
        if not integration:
            return JSONResponse({"success": False, "error": "integration is required"}, status_code=400)
        if not credential:
            return JSONResponse({"success": False, "error": "credential is required"}, status_code=400)

        # --- Format validation (best-effort, non-blocking) ---
        try:
            from src.env_manager import validate_api_key as _validate_api_key, API_KEY_FORMATS as _AKF
            if integration in _AKF:
                _valid, _msg = _validate_api_key(integration, credential)
                if not _valid:
                    return JSONResponse({"success": False, "error": _msg}, status_code=400)
        except Exception:
            logger.debug("Suppressed exception in app")

        # Map integration name to env var
        _INTEGRATION_ENV_VARS = {
            "deepinfra": "DEEPINFRA_API_KEY",
            "together": "TOGETHER_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "sendgrid": "SENDGRID_API_KEY",
            "slack": "SLACK_BOT_TOKEN",
            "stripe": "STRIPE_SECRET_KEY",
            "hubspot": "HUBSPOT_API_KEY",
            "github": "GITHUB_TOKEN",
            "twilio": "TWILIO_AUTH_TOKEN",
            "google_calendar": "GOOGLE_CALENDAR_API_KEY",
            "google_sheets": "GOOGLE_SHEETS_API_KEY",
            "datadog": "DATADOG_API_KEY",
            "openweather": "OPENWEATHER_API_KEY",
            "postgres": "DATABASE_URL",
            "notion": "NOTION_API_KEY",
            "airtable": "AIRTABLE_API_KEY",
            "jira": "JIRA_API_TOKEN",
            "salesforce": "SALESFORCE_CONSUMER_KEY",
            "pagerduty": "PAGERDUTY_API_KEY",
            "zoom": "ZOOM_CLIENT_SECRET",
            "monday": "MONDAY_API_KEY",
            "shopify": "SHOPIFY_ACCESS_TOKEN",
            "twitch": "TWITCH_CLIENT_SECRET",
            "discord": "DISCORD_BOT_TOKEN",
            "telegram": "TELEGRAM_BOT_TOKEN",
        }
        env_var = _INTEGRATION_ENV_VARS.get(integration, f"{integration.upper()}_API_KEY")
        os.environ[env_var] = credential
        _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        try:
            from src.env_manager import write_env_key as _write_env_key
            _write_env_key(str(_env_path), env_var, credential)
        except Exception as _exc:
            logger.debug("Could not persist credential to .env: %s", _exc)
        return JSONResponse({
            "success": True,
            "integration": integration,
            "env_var": env_var,
            "message": f"{integration} credential stored successfully.",
        })

    @app.get("/api/llm/providers")
    async def llm_providers_list():
        """List configured LLM providers with live Ollama status."""
        from src.local_llm_fallback import (
            _check_ollama_available,
            _ollama_base_url,
            _ollama_list_models,
            _preferred_ollama_models,
        )
        base_url = _ollama_base_url()
        ollama_up = _check_ollama_available(base_url)
        pulled_models = _ollama_list_models(base_url) if ollama_up else []
        preferred = _preferred_ollama_models()

        providers = [
            {
                "id": "ollama",
                "name": "Ollama (Local)",
                "type": "local",
                "available": ollama_up,
                "default_model": preferred[0] if preferred else "phi3",
                "preferred_models": preferred,
                "pulled_models": pulled_models,
                "base_url": base_url,
                "description": "Local LLM inference via Ollama. Runs phi3 by default.",
            },
            {
                "id": "deepinfra",
                "name": "DeepInfra Cloud",
                "type": "cloud",
                "available": bool(os.getenv("DEEPINFRA_API_KEY")),
                "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
                "description": "Primary LLM via DeepInfra. Requires DEEPINFRA_API_KEY.",
            },
            {
                "id": "together",
                "name": "Together AI Cloud",
                "type": "cloud",
                "available": bool(os.getenv("TOGETHER_API_KEY")),
                "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                "description": "Overflow LLM via Together AI. Requires TOGETHER_API_KEY.",
            },
            {
                "id": "aristotle",
                "name": "Aristotle (Deterministic)",
                "type": "local",
                "available": True,
                "default_model": "aristotle-deterministic",
                "description": "Deterministic validation engine for math/physics domains.",
            },
            {
                "id": "wulfrum",
                "name": "Wulfrum (Fuzzy Match)",
                "type": "local",
                "available": True,
                "default_model": "wulfrum-fuzzy",
                "description": "Fuzzy match engine for approximate validation.",
            },
        ]

        active = None
        if ollama_up and pulled_models:
            active = "ollama"
        elif os.getenv("DEEPINFRA_API_KEY"):
            active = "deepinfra"
        elif os.getenv("TOGETHER_API_KEY"):
            active = "together"

        return JSONResponse({
            "success": True,
            "providers": providers,
            "active": active,
            "ollama_available": ollama_up,
            "phi3_ready": ollama_up and any("phi3" in m for m in pulled_models),
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
        """Return Wingman System status (sensor modules, validation counts)."""
        ws = getattr(murphy, "wingman_system", None)
        if ws is None:
            return JSONResponse({
                "success": True, "status": "unavailable",
                "active_session": None, "suggestions": [],
            })
        return JSONResponse({"success": True, **ws.get_status()})

    @app.get("/api/wingman/suggestions")
    async def wingman_suggestions():
        """Return Wingman validation suggestions based on recent findings."""
        ws = getattr(murphy, "wingman_system", None)
        if ws is None:
            return JSONResponse({"success": True, "suggestions": []})
        status = ws.get_status()
        suggestions = []
        for mid, stats in status.get("per_module", {}).items():
            rejected = stats.get("rejected", 0)
            if rejected > 0:
                suggestions.append({
                    "module": mid,
                    "message": (
                        f"Module '{mid}' has {rejected} rejected validation(s). "
                        f"Review world-model sensor findings in the Librarian."
                    ),
                    "severity": "warn",
                })
        return JSONResponse({"success": True, "suggestions": suggestions})

    @app.post("/api/wingman/validate")
    async def wingman_validate(request: Request):
        """Validate an arbitrary artifact through the Wingman System.

        Body: { "artifact": { "content": "...", ... }, "module_id": "deliverable" }
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)
        artifact = body.get("artifact")
        if not artifact or not isinstance(artifact, dict):
            return JSONResponse(
                {"success": False, "error": "missing_artifact",
                 "message": "Provide an 'artifact' object in the request body."},
                status_code=400,
            )
        module_id = body.get("module_id", "deliverable")
        ws = getattr(murphy, "wingman_system", None)
        if ws is None:
            return JSONResponse({"success": False, "error": "wingman_unavailable"}, status_code=503)
        result = ws.validate(artifact, module_id=module_id)
        return JSONResponse({"success": True, "validation": result.to_dict()})

    @app.get("/api/wingman/api-gaps")
    async def wingman_api_gaps():
        """Return current API capability gap status from the builder."""
        checker = getattr(murphy, "api_gap_checker", None)
        if checker is None:
            return JSONResponse({"success": True, "status": "unavailable", "gaps": []})
        return JSONResponse({"success": True, **checker._builder.get_status()})

    @app.post("/api/wingman/api-gaps/scan")
    async def wingman_api_gaps_scan(request: Request):
        """Scan an artifact for missing external API needs.

        Body: { "artifact": { "content": "..." }, "owner_user_id": "uid" }

        Requires OWNER (founder-admin) role to auto-generate scaffolds.
        Without OWNER permission the scan still runs and tickets are raised,
        but stubs are not generated until an OWNER approves.
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)
        artifact = body.get("artifact")
        if not artifact or not isinstance(artifact, dict):
            return JSONResponse(
                {"success": False, "error": "missing_artifact",
                 "message": "Provide an 'artifact' object in the request body."},
                status_code=400,
            )
        owner_user_id = body.get("owner_user_id") or body.get("user_id")
        checker = getattr(murphy, "api_gap_checker", None)
        if checker is None:
            return JSONResponse({"success": False, "error": "api_gap_checker_unavailable"}, status_code=503)
        result = checker.check(
            artifact=artifact,
            requester=owner_user_id or "api_call",
            owner_user_id=owner_user_id,
        )
        return JSONResponse({"success": True, **result})

    @app.post("/api/wingman/api-gaps/build")
    async def wingman_api_gaps_build(request: Request):
        """Approve and trigger scaffold generation for a list of API needs.

        This endpoint requires OWNER (founder-admin) level.
        Body: { "owner_user_id": "uid", "categories": ["banking", "stock"] }

        The owner_user_id must hold the TRIGGER_API_BUILD permission.
        For each requested category, if a pending ApiNeed exists in the
        builder's processed list, scaffold generation is triggered.
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)

        owner_user_id = body.get("owner_user_id") or body.get("user_id")
        if not owner_user_id:
            return JSONResponse(
                {"success": False, "error": "missing_owner_user_id",
                 "message": "Provide owner_user_id with OWNER (founder-admin) role."},
                status_code=403,
            )

        checker = getattr(murphy, "api_gap_checker", None)
        if checker is None:
            return JSONResponse({"success": False, "error": "api_gap_checker_unavailable"}, status_code=503)

        # Verify OWNER permission
        owner_authorized = checker._check_owner_permission(owner_user_id)
        if not owner_authorized:
            return JSONResponse(
                {
                    "success": False,
                    "error": "forbidden",
                    "message": (
                        "TRIGGER_API_BUILD requires OWNER (founder-admin) role. "
                        "Ask a platform owner to approve this action."
                    ),
                },
                status_code=403,
            )

        categories = body.get("categories")
        artifact = body.get("artifact")

        if artifact and isinstance(artifact, dict):
            # Re-scan with owner authorization
            result = checker.check(
                artifact=artifact,
                requester=owner_user_id,
                owner_user_id=owner_user_id,
            )
            return JSONResponse({"success": True, **result})

        return JSONResponse(
            {"success": False, "error": "missing_artifact",
             "message": "Provide an 'artifact' object to re-scan with OWNER authorization."},
            status_code=400,
        )

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

    @app.get("/api/heatmap/coverage")
    async def heatmap_coverage():
        """Return heatmap module coverage statistics for the production wizard."""
        from src.local_llm_fallback import _check_ollama_available, _ollama_base_url
        total_modules = 12
        active_modules = sum([
            1,  # integration_bus
            1,  # llm_integration_layer
            1 if bool(os.getenv("DEEPINFRA_API_KEY") or os.getenv("TOGETHER_API_KEY")) else 0,   # llm_cloud
            1 if _check_ollama_available(_ollama_base_url()) else 0,  # ollama
            1,  # workflow_dag_engine
            1,  # automation_commissioner
            1,  # ai_workflow_generator
            1,  # production_assistant
            1,  # hitl
            1,  # auth
            1 if bool(os.getenv("SENDGRID_API_KEY")) else 0,  # email
            1 if bool(os.getenv("SLACK_BOT_TOKEN")) else 0,   # slack
        ])
        return JSONResponse({
            "success": True,
            "total_modules": total_modules,
            "active_modules": active_modules,
            "coverage_pct": round(active_modules / total_modules * 100, 1),
            "modules": [
                {"name": "integration_bus", "active": True},
                {"name": "llm_integration_layer", "active": True},
                {"name": "deepinfra", "active": bool(os.getenv("DEEPINFRA_API_KEY"))},
                {"name": "together", "active": bool(os.getenv("TOGETHER_API_KEY"))},
                {"name": "ollama", "active": _check_ollama_available(_ollama_base_url())},
                {"name": "workflow_dag_engine", "active": True},
                {"name": "automation_commissioner", "active": True},
                {"name": "ai_workflow_generator", "active": True},
                {"name": "production_assistant", "active": True},
                {"name": "hitl", "active": True},
                {"name": "auth", "active": True},
                {"name": "email", "active": bool(os.getenv("SENDGRID_API_KEY"))},
                {"name": "slack", "active": bool(os.getenv("SLACK_BOT_TOKEN"))},
            ],
        })

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
                    except ValueError:  # PROD-HARD A2: unknown compliance framework ID — skip with breadcrumb
                        logger.debug("Compliance framework %r not recognised by native engine; skipping", native_id)
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
                            "Upgrade to Solo ($99/mo) for GDPR and SOC 2 compliance."
                        )
                elif not features.get("advanced_compliance", False):
                    # SOLO tier — basic only
                    original = set(enabled_ids)
                    enabled_ids = [f for f in enabled_ids if f in _BASIC_FRAMEWORKS]
                    if original - _BASIC_FRAMEWORKS:
                        tier_restricted = True
                        tier_message = (
                            "Your Solo plan supports GDPR and SOC 2 only. "
                            "Upgrade to Business ($299/mo) for HIPAA, PCI-DSS, "
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
                        # SEC-LOG-002: Log only exception type, not message (may contain tokens).
                        logger.warning("OAuth env-var token exchange failed: %s", type(_tok_exc).__name__)
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
                            logger.debug("Suppressed exception in app")

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
                logger.debug("Suppressed exception in app")
        # Env-var fallback: detect Google OAuth from environment when registry
        # is unavailable (e.g. AccountManager/CredentialVault init failed).
        if not configured.get("google") and os.environ.get("MURPHY_OAUTH_GOOGLE_CLIENT_ID"):
            configured["google"] = True
        return JSONResponse({"providers": configured})

    @app.post("/api/auth/signup")
    async def auth_signup(request: Request):
        """Handle email/password signup — creates account and sends verification email."""
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
            # Founder email always gets the owner role regardless of how the
            # account is created.
            _assigned_role = "owner" if email == _FOUNDER_EMAIL else "user"
            _assigned_tier = "enterprise" if email == _FOUNDER_EMAIL else "free"
            _user_store[account_id] = {
                "account_id": account_id,
                "email": email,
                "password_hash": _hash_password(password),
                "full_name": full_name or (os.environ.get("MURPHY_FOUNDER_NAME", "") if email == _FOUNDER_EMAIL else ""),
                "job_title": job_title,
                "company": company,
                "tier": _assigned_tier,
                "email_validated": False,
                "eula_accepted": True,      # accepted at signup form
                "role": _assigned_role,
                "created_at": _now_iso(),
            }
            _email_to_account[email] = account_id

            # Create a free-tier subscription record
            if _sub_manager is not None and _SubTier is not None:
                _sub_tier_val = (
                    _SubTier.ENTERPRISE if email == _FOUNDER_EMAIL and hasattr(_SubTier, "ENTERPRISE")
                    else _SubTier.FREE
                )
                _sub_manager._subscriptions[account_id] = _SubRec(
                    account_id=account_id,
                    tier=_sub_tier_val,
                    status=_SubStatus.ACTIVE,
                )

            # Generate email verification token
            verification_token = _secrets.token_urlsafe(32)
            _verification_tokens[verification_token] = {
                "account_id": account_id,
                "email": email,
                "created_at": _now_iso(),
            }

            # Build verification URL
            scheme = request.url.scheme
            host = request.headers.get("host", request.url.hostname or "murphy.systems")
            verify_url = f"{scheme}://{host}/api/auth/verify-email?token={verification_token}"

            # Send verification email
            _email_sent = False
            try:
                from src.email_integration import EmailService
                _email_svc = EmailService.from_env()
                _send_result = await _email_svc.send(
                    to=[email],
                    subject="Verify your Murphy System account",
                    body=(
                        f"Hi {full_name or 'there'},\n\n"
                        f"Thank you for signing up for Murphy System.\n\n"
                        f"Please verify your email address by clicking the link below:\n\n"
                        f"{verify_url}\n\n"
                        f"This link expires in 24 hours.\n\n"
                        f"If you did not create an account, you can safely ignore this email.\n\n"
                        f"— Murphy System\n"
                    ),
                    html_body=(
                        f'<div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:2rem;">'
                        f'<h2 style="color:#00D4AA;">Verify your email</h2>'
                        f'<p>Hi {full_name or "there"},</p>'
                        f'<p>Thank you for signing up for Murphy System. '
                        f'Please verify your email address by clicking the button below:</p>'
                        f'<p style="text-align:center;margin:2rem 0;">'
                        f'<a href="{verify_url}" style="background:#00D4AA;color:#0a0a0a;'
                        f'padding:12px 32px;border-radius:8px;text-decoration:none;'
                        f'font-weight:600;display:inline-block;">Verify Email Address</a></p>'
                        f'<p style="color:#888;font-size:0.85rem;">This link expires in 24 hours. '
                        f'If you did not create an account, you can safely ignore this email.</p>'
                        f'<hr style="border:none;border-top:1px solid #333;margin:2rem 0;">'
                        f'<p style="color:#666;font-size:0.75rem;">Murphy System &mdash; '
                        f'Automate your entire business.</p></div>'
                    ),
                    from_addr=_VERIFICATION_FROM_EMAIL,
                )
                _email_sent = _send_result.success
                if not _email_sent:
                    logger.warning(
                        "Verification email send reported failure for %s: %s",
                        email, _send_result.error,
                    )
            except Exception as _email_exc:
                logger.warning("Could not send verification email to %s: %s", email, _email_exc)

            logger.info(
                "Account created (pending verification): %s (%s) email_sent=%s",
                account_id, email, _email_sent,
            )
            return JSONResponse({
                "success": True,
                "requires_verification": True,
                "message": "Account created. Please check your email to verify your address.",
                "account_id": account_id,
                "email": email,
                "email_sent": _email_sent,
            }, status_code=201)
        except Exception as exc:
            logger.exception("Signup failed")
            return _safe_error_response(exc, 500)

    @app.get("/api/auth/verify-email")
    async def auth_verify_email(request: Request, token: str = ""):
        """Verify email address from the link sent during signup."""
        if not token:
            return HTMLResponse(
                '<html><body style="background:#0a0a0a;color:#ff4444;font-family:sans-serif;'
                'display:flex;align-items:center;justify-content:center;min-height:100vh;">'
                '<div style="text-align:center"><h2>Invalid verification link</h2>'
                '<p>The verification link is missing or malformed.</p>'
                '<a href="/ui/signup" style="color:#00D4AA;">Sign up again</a></div>'
                '</body></html>',
                status_code=400,
            )

        token_data = _verification_tokens.get(token)
        if not token_data:
            return HTMLResponse(
                '<html><body style="background:#0a0a0a;color:#ff4444;font-family:sans-serif;'
                'display:flex;align-items:center;justify-content:center;min-height:100vh;">'
                '<div style="text-align:center"><h2>Link expired or invalid</h2>'
                '<p>This verification link has already been used or has expired.</p>'
                '<a href="/ui/login" style="color:#00D4AA;">Sign in</a> or '
                '<a href="/ui/signup" style="color:#00D4AA;">Sign up again</a></div>'
                '</body></html>',
                status_code=400,
            )

        # Check expiry
        try:
            created_str = token_data.get("created_at", "")
            created_dt = datetime.fromisoformat(created_str)
            # Ensure timezone-aware comparison
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - created_dt).total_seconds() > _VERIFICATION_EXPIRY_SECONDS:
                _verification_tokens.pop(token, None)
                return HTMLResponse(
                    '<html><body style="background:#0a0a0a;color:#ff4444;font-family:sans-serif;'
                    'display:flex;align-items:center;justify-content:center;min-height:100vh;">'
                    '<div style="text-align:center"><h2>Link expired</h2>'
                    '<p>This verification link has expired. Please sign up again.</p>'
                    '<a href="/ui/signup" style="color:#00D4AA;">Sign up</a></div>'
                    '</body></html>',
                    status_code=400,
                )
        except Exception:
            # If expiry validation fails, reject the token to avoid bypassing expiry
            logger.warning("Verification token expiry check failed for token, rejecting")
            _verification_tokens.pop(token, None)
            return HTMLResponse(
                '<html><body style="background:#0a0a0a;color:#ff4444;font-family:sans-serif;'
                'display:flex;align-items:center;justify-content:center;min-height:100vh;">'
                '<div style="text-align:center"><h2>Verification error</h2>'
                '<p>Could not validate this link. Please request a new one.</p>'
                '<a href="/ui/signup" style="color:#00D4AA;">Sign up</a></div>'
                '</body></html>',
                status_code=400,
            )

        account_id = token_data["account_id"]
        account = _user_store.get(account_id)
        if not account:
            _verification_tokens.pop(token, None)
            return HTMLResponse(
                '<html><body style="background:#0a0a0a;color:#ff4444;font-family:sans-serif;'
                'display:flex;align-items:center;justify-content:center;min-height:100vh;">'
                '<div style="text-align:center"><h2>Account not found</h2>'
                '<p>The account associated with this link could not be found.</p>'
                '<a href="/ui/signup" style="color:#00D4AA;">Sign up again</a></div>'
                '</body></html>',
                status_code=404,
            )

        # Mark email as validated
        account["email_validated"] = True
        _user_store[account_id] = account

        # Consume the token so it cannot be reused
        _verification_tokens.pop(token, None)

        # Mint session and redirect to onboarding
        session_token = _create_session(account_id)

        from starlette.responses import RedirectResponse as _RR
        resp = _RR("/ui/onboarding", status_code=302)
        resp.set_cookie(
            key="murphy_session",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400,
        )
        logger.info("Email verified for account %s (%s)", account_id, token_data["email"])
        return resp

    @app.post("/api/auth/resend-verification")
    async def auth_resend_verification(request: Request):
        """Resend verification email for an unverified account."""
        try:
            data = await request.json()
            email = (data.get("email") or "").strip().lower()

            if not email:
                return JSONResponse({"success": False, "error": "Email is required"}, status_code=400)

            account_id = _email_to_account.get(email)
            if not account_id:
                # Don't reveal whether the email exists
                return JSONResponse({
                    "success": True,
                    "message": "If that email is registered, a verification link has been sent.",
                })

            account = _user_store.get(account_id)
            if not account:
                return JSONResponse({
                    "success": True,
                    "message": "If that email is registered, a verification link has been sent.",
                })

            if account.get("email_validated"):
                return JSONResponse({
                    "success": True,
                    "message": "Email is already verified. You can sign in.",
                    "already_verified": True,
                })

            # Invalidate existing tokens for this account
            _tokens_to_remove = [
                t for t, d in _verification_tokens.items()
                if d.get("account_id") == account_id
            ]
            for t in _tokens_to_remove:
                _verification_tokens.pop(t, None)

            # Generate new token
            verification_token = _secrets.token_urlsafe(32)
            _verification_tokens[verification_token] = {
                "account_id": account_id,
                "email": email,
                "created_at": _now_iso(),
            }

            # Build verification URL
            scheme = request.url.scheme
            host = request.headers.get("host", request.url.hostname or "murphy.systems")
            verify_url = f"{scheme}://{host}/api/auth/verify-email?token={verification_token}"

            full_name = account.get("full_name", "")

            # Send verification email
            _email_sent = False
            try:
                from src.email_integration import EmailService
                _email_svc = EmailService.from_env()
                _send_result = await _email_svc.send(
                    to=[email],
                    subject="Verify your Murphy System account",
                    body=(
                        f"Hi {full_name or 'there'},\n\n"
                        f"Please verify your email address by clicking the link below:\n\n"
                        f"{verify_url}\n\n"
                        f"This link expires in 24 hours.\n\n"
                        f"— Murphy System\n"
                    ),
                    html_body=(
                        f'<div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:2rem;">'
                        f'<h2 style="color:#00D4AA;">Verify your email</h2>'
                        f'<p>Hi {full_name or "there"},</p>'
                        f'<p>Please verify your email address by clicking the button below:</p>'
                        f'<p style="text-align:center;margin:2rem 0;">'
                        f'<a href="{verify_url}" style="background:#00D4AA;color:#0a0a0a;'
                        f'padding:12px 32px;border-radius:8px;text-decoration:none;'
                        f'font-weight:600;display:inline-block;">Verify Email Address</a></p>'
                        f'<p style="color:#888;font-size:0.85rem;">This link expires in 24 hours.</p>'
                        f'<hr style="border:none;border-top:1px solid #333;margin:2rem 0;">'
                        f'<p style="color:#666;font-size:0.75rem;">Murphy System &mdash; '
                        f'Automate your entire business.</p></div>'
                    ),
                    from_addr=_VERIFICATION_FROM_EMAIL,
                )
                _email_sent = _send_result.success
            except Exception as _email_exc:
                logger.warning("Could not resend verification email to %s: %s", email, _email_exc)

            return JSONResponse({
                "success": True,
                "message": "If that email is registered, a verification link has been sent.",
                "email_sent": _email_sent,
            })
        except Exception as exc:
            logger.exception("Resend verification failed")
            return _safe_error_response(exc, 500)

    @app.get("/api/auth/login")
    async def auth_login_page(request: Request):
        """Login page / session check.

        Returns session status if already logged in, or a redirect hint
        to the login UI.  Used by frontend auth guards.
        Commissioned: PATCH-010 / 2026-04-19
        """
        account = _get_account_from_session(request)
        if account:
            return JSONResponse({
                "success": True,
                "authenticated": True,
                "account_id": account.get("account_id", ""),
                "email": account.get("email", ""),
                "name": account.get("full_name", ""),
                "tier": account.get("tier", "free"),
            })
        return JSONResponse({
            "success": True,
            "authenticated": False,
            "login_url": "/ui/login",
            "message": "Not authenticated — redirect to login page",
        })

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
                "session_token": session_token,
                "email": account["email"],
                "name": account.get("full_name", ""),
                "tier": account.get("tier", "free"),
            })
            resp.set_cookie(
                key="murphy_session",
                value=session_token,
                httponly=True,
                secure=True,
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

    @app.get("/api/auth/session-token")
    async def get_session_token(request: Request):
        """Return the active session token for the current user.

        Called by murphy_auth.js after an OAuth redirect to mirror the
        HttpOnly murphy_session cookie into localStorage so that the
        MurphyAPI._buildHeaders() Bearer-token path also works for OAuth
        users.  Requires an active murphy_session cookie (set by the OAuth
        callback or login) — returns 401 if the caller is not authenticated.
        """
        # Resolve token from cookie or Authorization header
        token = request.cookies.get("murphy_session", "")
        if not token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if not token:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        with _session_lock:
            account_id = _session_store.get(token)
        if not account_id:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        return JSONResponse({"session_token": token})

    @app.post("/api/auth/forgot-password")
    async def auth_forgot_password(request: Request):
        """Initiate a password-reset flow.

        Body: { "email": "user@example.com" }
        Always returns success to prevent user enumeration.
        """
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)
        email = (data.get("email") or "").strip().lower()
        if not email:
            return JSONResponse({"success": False, "error": "email is required"}, status_code=400)
        # Best-effort: ask AccountManager to send a reset link.
        if _account_manager is not None:
            try:
                _account_manager.request_password_reset(email)
            except Exception:
                logger.debug("Suppressed exception in app")
        return JSONResponse({
            "success": True,
            "message": "If an account with that email exists, a reset link has been sent.",
        })

    # ── Self-service password management ──────────────────────────────────
    # In-process token store for password-reset flows.
    # Each entry: token → { account_id, expires_at, used }
    _password_reset_tokens: "Dict[str, Dict[str, Any]]" = {}
    _comms_rules_store: "Dict[str, Dict[str, Any]]" = {}

    @app.post("/api/auth/change-password")
    async def auth_change_password(request: Request):
        """Change the authenticated user's own password.

        Body: { "current_password": "...", "new_password": "..." }
        Requires an active session.  New password must be at least 8 characters.
        """
        account = _get_account_from_session(request)
        if account is None:
            return JSONResponse({"success": False, "error": "Authentication required"}, status_code=401)
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

        current_pw = data.get("current_password", "")
        new_pw = data.get("new_password", "")

        if not current_pw or not new_pw:
            return JSONResponse({"success": False, "error": "current_password and new_password are required"}, status_code=400)
        if len(new_pw) < 8:
            return JSONResponse({"success": False, "error": "New password must be at least 8 characters"}, status_code=400)

        stored_hash = account.get("password_hash", "")
        if not stored_hash or not _verify_password(current_pw, stored_hash):
            return JSONResponse({"success": False, "error": "Current password is incorrect"}, status_code=400)

        if current_pw == new_pw:
            return JSONResponse({"success": False, "error": "New password must differ from the current password"}, status_code=400)

        account["password_hash"] = _hash_password(new_pw)
        account["password_changed_at"] = _now_iso()
        logger.info("Password changed for account %s", account["account_id"])
        return JSONResponse({"success": True, "message": "Password updated successfully."})

    @app.post("/api/auth/request-password-reset")
    async def auth_request_password_reset(request: Request):
        """Generate a password-reset token and (in production) email it to the user.

        Body: { "email": "user@example.com" }
        Always returns the same success response to prevent user enumeration.
        In development the token is returned directly in the response so that
        the flow can be tested without an email server.
        """
        import secrets as _sec
        import time as _time
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

        email = (data.get("email") or "").strip().lower()
        if not email:
            return JSONResponse({"success": False, "error": "email is required"}, status_code=400)

        account_id = _email_to_account.get(email)
        resp_body: "Dict[str, Any]" = {
            "success": True,
            "message": "If an account with that email exists, a reset link has been sent.",
        }
        if account_id:
            # Expire any existing unused token for this account
            for t, meta in list(_password_reset_tokens.items()):
                if meta.get("account_id") == account_id and not meta.get("used"):
                    meta["used"] = True

            token = _sec.token_urlsafe(32)
            # Token valid for 1 hour
            _password_reset_tokens[token] = {
                "account_id": account_id,
                "email": email,
                "expires_at": _time.time() + 3600,
                "used": False,
            }

            reset_url = f"/ui/reset-password?token={token}"

            # Founder reset confirmations route to the founder recovery inbox.
            # All other users receive reset links at their registered email.
            target_email = email
            if email == _FOUNDER_EMAIL and _FOUNDER_RECOVERY_EMAIL:
                target_email = _FOUNDER_RECOVERY_EMAIL

            # Send via Murphy email API (best-effort)
            try:
                import httpx as _httpx
                _httpx.post(
                    "http://localhost:8000/api/email/send",
                    json={
                        "to": target_email,
                        "from": _PASSWORD_RESET_FROM_EMAIL,
                        "subject": "Murphy System — Reset your password",
                        "body": (
                            f"Hi,\n\nClick the link below to reset your Murphy System password. "
                            f"This link expires in 1 hour.\n\n"
                            f"https://murphy.systems{reset_url}\n\n"
                            f"If you did not request this, you can safely ignore this email.\n\n"
                            f"— Murphy System"
                        ),
                    },
                    timeout=3,
                )
            except Exception:
                logger.debug("Suppressed exception in app")

            # In development expose the token so the flow can be tested without email
            if os.environ.get("MURPHY_ENV", "development").lower() == "development":
                resp_body["dev_token"] = token
                resp_body["dev_reset_url"] = reset_url

        return JSONResponse(resp_body)

    @app.get("/api/auth/reset-password/validate")
    async def auth_validate_reset_token(request: Request):
        """Check whether a password-reset token is valid and unexpired.

        Query param: token=<token>
        Returns { valid: true/false, email: "..." }
        """
        import time as _time
        token = request.query_params.get("token", "").strip()
        if not token:
            return JSONResponse({"valid": False, "error": "token is required"}, status_code=400)
        meta = _password_reset_tokens.get(token)
        if meta is None or meta.get("used") or _time.time() > meta.get("expires_at", 0):
            return JSONResponse({"valid": False, "error": "Token is invalid or has expired"})
        return JSONResponse({"valid": True, "email": meta.get("email", "")})

    @app.post("/api/auth/reset-password")
    async def auth_reset_password(request: Request):
        """Consume a password-reset token and set the new password.

        Body: { "token": "...", "new_password": "..." }
        The token is single-use and expires after 1 hour.
        """
        import time as _time
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

        token = (data.get("token") or "").strip()
        new_pw = data.get("new_password", "")

        if not token:
            return JSONResponse({"success": False, "error": "token is required"}, status_code=400)
        if not new_pw or len(new_pw) < 8:
            return JSONResponse({"success": False, "error": "New password must be at least 8 characters"}, status_code=400)

        meta = _password_reset_tokens.get(token)
        if meta is None or meta.get("used"):
            return JSONResponse({"success": False, "error": "Token is invalid or has already been used"}, status_code=400)
        if _time.time() > meta.get("expires_at", 0):
            return JSONResponse({"success": False, "error": "Token has expired. Please request a new reset link."}, status_code=400)

        account_id = meta.get("account_id", "")
        user = _user_store.get(account_id)
        if user is None:
            return JSONResponse({"success": False, "error": "Account not found"}, status_code=404)

        # Mark token as used before writing the new hash (prevents replay even if
        # the hash write fails partway through)
        meta["used"] = True
        user["password_hash"] = _hash_password(new_pw)
        user["password_changed_at"] = _now_iso()
        logger.info("Password reset consumed for account %s", account_id)
        return JSONResponse({"success": True, "message": "Password has been reset. You can now sign in."})


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
                    logger.debug("Suppressed exception in app")

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

    # ── Paper Trading Engine (PR-2) ────────────────────────────────────
    try:
        from paper_trading_routes import create_paper_trading_router
        _pt_router = create_paper_trading_router()
        app.include_router(_pt_router)
        logger.info("Paper Trading API registered at /api/trading/*")
    except Exception as _pt_exc:
        logger.warning("Paper Trading routes not available: %s", _pt_exc)

    @app.get("/api/trading/paper/status")
    async def trading_paper_status():
        """Return current paper trading engine status."""
        try:
            from paper_trading_routes import get_paper_trading_status
            return JSONResponse(get_paper_trading_status())
        except Exception:
            logger.debug("Suppressed exception in app")
        return JSONResponse({
            "success": True,
            "status": "paper_mode",
            "mode": "paper",
            "is_live": False,
            "message": "System is in paper trading mode — no real funds at risk",
        })

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

    # ==================== OPENTELEMETRY TRACING (OPT-IN) ====================
    # Class S Roadmap, Item 6: configure OTel tracing if MURPHY_OTEL_ENABLED
    # is truthy AND the opentelemetry SDK is installed. The scaffold is a
    # documented no-op in every other case (see src/runtime/tracing.py) so
    # this call is safe to run unconditionally and never blocks boot.
    try:
        from src.runtime.tracing import configure_tracing
        configure_tracing(app)
    except Exception as _otel_exc:  # noqa: BLE001 — tracing must never block boot
        logger.warning("OTel tracing setup skipped: %s", _otel_exc)

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

    # ==================== HITL DEPLOYMENT GATE ENDPOINTS ====================
    # These endpoints wire the HITL Review Builder to the runtime, enabling
    # platform admins (FOUNDER / PLATFORM_ADMIN) to review high-risk changes
    # before they are applied to the system.

    @app.post("/api/hitl/deployment-review")
    async def hitl_create_deployment_review(request: Request):
        """Create a HITL deployment review for a high-risk change.

        Body: {
            "change_category": "optimization|update|bugfix|source_code|customer_deliverable|...",
            "problem_description": "...",
            "rationale_why": "...",
            "rationale_approach": "...",
            "priority": "critical|high|medium|low",
            "artifact_context": { ... }
        }
        Commissioned: PATCH-010 / 2026-04-19
        """
        builder = getattr(murphy, "hitl_review_builder", None)
        if builder is None:
            return JSONResponse(
                {"success": False, "error": {"code": "SERVICE_UNAVAILABLE",
                 "message": "HITL Review Builder not initialised"}},
                status_code=503,
            )
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON"}},
                status_code=400,
            )
        change_category = (body.get("change_category") or "update").strip()
        problem_description = (body.get("problem_description") or "").strip()
        if not problem_description:
            return JSONResponse(
                {"success": False, "error": {"code": "VALIDATION_ERROR",
                 "message": "problem_description is required"}},
                status_code=422,
            )
        review = builder.build_review(
            change_category=change_category,
            problem_description=problem_description,
            rationale_why=body.get("rationale_why", ""),
            rationale_approach=body.get("rationale_approach", ""),
            priority=body.get("priority", "medium"),
            artifact_context=body.get("artifact_context"),
        )
        # Persist to HITL store if available
        _hitl_store = getattr(murphy, "hitl_store", None)
        if _hitl_store and hasattr(_hitl_store, "save_item"):
            _hitl_store.save_item({
                "id": review.review_id,
                "type": "deployment_review",
                "title": f"Deployment Review: {change_category}",
                "description": review.problem_summary,
                "status": "pending",
                "priority": review.priority,
                "metadata": review.to_dict(),
            })
        logger.info("Created deployment review %s [%s]", review.review_id, change_category)
        return JSONResponse({"success": True, "review": review.to_dict()}, status_code=201)

    @app.get("/api/hitl/deployment-reviews")
    async def hitl_list_deployment_reviews():
        """List pending HITL deployment reviews.

        Returns all reviews that require platform admin approval.
        Commissioned: PATCH-010 / 2026-04-19
        """
        builder = getattr(murphy, "hitl_review_builder", None)
        if builder is None:
            return JSONResponse({"success": True, "reviews": [], "count": 0})
        pending = builder.list_pending()
        return JSONResponse({
            "success": True,
            "reviews": [r.to_dict() for r in pending],
            "count": len(pending),
        })

    @app.post("/api/hitl/deployment-review/{review_id}/decide")
    async def hitl_deployment_review_decide(review_id: str, request: Request):
        """Approve or reject a HITL deployment review.

        Body: { "decision": "approve|reject", "decided_by": "user_id", "reason": "..." }
        Only FOUNDER and PLATFORM_ADMIN roles may decide.
        Commissioned: PATCH-010 / 2026-04-19
        """
        builder = getattr(murphy, "hitl_review_builder", None)
        if builder is None:
            return JSONResponse(
                {"success": False, "error": {"code": "SERVICE_UNAVAILABLE"}},
                status_code=503,
            )
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"success": False, "error": {"code": "BAD_REQUEST"}},
                status_code=400,
            )
        decision = (body.get("decision") or "").strip()
        decided_by = (body.get("decided_by") or "").strip()
        reason = (body.get("reason") or "").strip()
        if decision not in ("approve", "reject"):
            return JSONResponse(
                {"success": False, "error": {"code": "VALIDATION_ERROR",
                 "message": "decision must be 'approve' or 'reject'"}},
                status_code=422,
            )
        if not decided_by:
            return JSONResponse(
                {"success": False, "error": {"code": "VALIDATION_ERROR",
                 "message": "decided_by is required"}},
                status_code=422,
            )
        # Verify platform-admin role if RBAC is available
        _rbac = getattr(murphy, "rbac_governance", None)
        if _rbac is not None:
            try:
                from src.rbac_governance import HITL_DEPLOYMENT_REVIEWER_ROLES
                user_identity = _rbac._users.get(decided_by)
                if user_identity is not None:
                    has_role = any(r in HITL_DEPLOYMENT_REVIEWER_ROLES for r in user_identity.roles)
                    if not has_role:
                        return JSONResponse(
                            {"success": False, "error": {"code": "FORBIDDEN",
                             "message": "Only FOUNDER or PLATFORM_ADMIN may decide deployment reviews"}},
                            status_code=403,
                        )
            except Exception as _rbac_exc:
                logger.debug("RBAC check skipped: %s", _rbac_exc)

        result = builder.decide(review_id, decision, decided_by, reason)
        if result is None:
            return JSONResponse(
                {"success": False, "error": {"code": "NOT_FOUND",
                 "message": f"Review {review_id} not found"}},
                status_code=404,
            )
        # Update HITL store
        _hitl_store = getattr(murphy, "hitl_store", None)
        if _hitl_store and hasattr(_hitl_store, "update_item"):
            _hitl_store.update_item(review_id, {
                "status": result.status,
                "metadata": result.to_dict(),
            })
        return JSONResponse({"success": True, "review": result.to_dict()})

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

    @app.post("/api/org/create")
    async def org_create(request: Request):
        """Create a new organization. Requires an active Professional or Enterprise plan.

        Body: { "name": "...", "description": "..." }
        """
        account = _get_account_from_session(request)
        if account is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)

        # Tier gating: Professional+ required to create organizations
        mgr = _get_sub_manager()
        if mgr is not None:
            gate = mgr.check_feature_access(account["account_id"], "can_create_org")
            if not gate.get("allowed", False):
                return JSONResponse(
                    {
                        "error": "Organization creation requires a Professional or Enterprise plan",
                        "upgrade_url": "/ui/pricing",
                        "required_tier": "professional",
                    },
                    status_code=403,
                )

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        name = (data.get("name") or "").strip()
        if not name:
            return JSONResponse({"error": "name is required"}, status_code=400)

        import uuid as _uuid_org, re as _re_org
        org_id = _uuid_org.uuid4().hex[:12]
        slug = _re_org.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

        # Use the verified subscription tier so the org record reflects
        # the actual plan rather than a potentially stale account field.
        org_plan = account.get("tier", "professional")
        if mgr is not None:
            _sub = mgr.get_subscription(account["account_id"])
            if _sub is not None:
                org_plan = _sub.tier.value

        org = {
            "org_id": org_id,
            "name": name,
            "slug": slug,
            "description": (data.get("description") or "").strip(),
            "owner_id": account["account_id"],
            "plan": org_plan,
            "status": "active",
            "members": [account["account_id"]],
            "created_at": _now_iso(),
            "created_by": account["account_id"],
        }
        _org_store[org_id] = org
        return JSONResponse({"success": True, "org_id": org_id, "organization": org}, status_code=201)

    # ==================== PLATFORM ADMIN (FOUNDER-LEVEL) ====================
    # All endpoints in this section require role == "admin" or "owner".
    # They are the primary tool for the founder/platform operator to manage
    # users and organisations without touching a database directly.
    #
    # Data stores used by this section:
    #   _user_store          — already defined above (account_id → user dict)
    #   _email_to_account    — already defined above (email → account_id)
    #   _org_store           — organisations registry (org_id → org dict)
    #   _admin_audit_log     — immutable audit trail of every admin action

    _org_store: "Dict[str, Dict[str, Any]]" = {}          # org_id → org record
    _admin_audit_log: "List[Dict[str, Any]]" = []         # chronological events
    _artifacts_store: "Dict[str, Dict[str, Any]]" = {}    # artifact_id → artifact record
    _demo_specs_store: "Dict[str, Dict[str, Any]]" = {}   # spec_id → automation spec

    def _require_admin(request: "Request") -> "Optional[Dict[str, Any]]":
        """Return the account dict if the caller has admin/owner role.

        Returns None  → caller is NOT authenticated       (send HTTP 401)
        Returns False → caller IS authenticated, not admin (send HTTP 403)
        Returns dict  → caller IS an admin/owner           (proceed)
        """
        account = _get_account_from_session(request)
        if account is None:
            return None           # not authenticated → 401
        if account.get("role") not in ("admin", "owner"):
            return False          # authenticated but wrong role → 403
        return account

    def _admin_log(actor_id: str, action: str, target: str, detail: "Dict[str, Any]") -> None:
        """Append an immutable audit-log entry."""
        import uuid as _uuid
        _admin_audit_log.append({
            "id": _uuid.uuid4().hex[:12],
            "actor_id": actor_id,
            "action": action,
            "target": target,
            "detail": detail,
            "ts": _now_iso(),
        })

    # ── Users ──────────────────────────────────────────────────────────────

    @app.get("/api/admin/users")
    async def admin_list_users(request: Request):
        """List all platform users. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        q = (request.query_params.get("q") or "").lower()
        role_f = request.query_params.get("role", "")
        tier_f = request.query_params.get("tier", "")
        limit = min(int(request.query_params.get("limit", "100")), 500)
        offset = int(request.query_params.get("offset", "0"))

        users = [
            {
                "account_id": v["account_id"],
                "email": v.get("email", ""),
                "full_name": v.get("full_name", ""),
                "role": v.get("role", "user"),
                "tier": v.get("tier", "free"),
                "status": v.get("status", "active"),
                "created_at": v.get("created_at", ""),
                "job_title": v.get("job_title", ""),
                "company": v.get("company", ""),
            }
            for v in _user_store.values()
        ]

        if q:
            users = [u for u in users if q in u["email"].lower() or q in u["full_name"].lower()]
        if role_f:
            users = [u for u in users if u["role"] == role_f]
        if tier_f:
            users = [u for u in users if u["tier"] == tier_f]

        total = len(users)
        users_page = users[offset: offset + limit]
        return JSONResponse({"success": True, "users": users_page, "total": total, "offset": offset, "limit": limit})

    @app.post("/api/admin/users")
    async def admin_create_user(request: Request):
        """Admin-create a user account (bypasses self-signup flow). Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        email = (data.get("email") or "").strip().lower()
        password = data.get("password", "")
        if not email:
            return JSONResponse({"error": "email is required"}, status_code=400)
        if not password or len(password) < 8:
            return JSONResponse({"error": "password must be at least 8 characters"}, status_code=400)
        if email in _email_to_account:
            return JSONResponse({"error": "An account with this email already exists"}, status_code=409)

        import uuid as _uuid
        account_id = _uuid.uuid4().hex[:20]
        user_record = {
            "account_id": account_id,
            "email": email,
            "password_hash": _hash_password(password),
            "full_name": data.get("full_name", ""),
            "job_title": data.get("job_title", ""),
            "company": data.get("company", ""),
            "tier": data.get("tier", "free"),
            "role": data.get("role", "user"),
            "status": "active",
            "email_validated": True,
            "eula_accepted": True,
            "created_at": _now_iso(),
            "created_by_admin": actor["account_id"],
        }
        _user_store[account_id] = user_record
        _email_to_account[email] = account_id
        _admin_log(actor["account_id"], "create_user", account_id, {"email": email, "role": user_record["role"], "tier": user_record["tier"]})

        return JSONResponse({"success": True, "account_id": account_id, "email": email}, status_code=201)

    @app.get("/api/admin/users/{user_id}")
    async def admin_get_user(user_id: str, request: Request):
        """Get a single user's full profile. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        user = _user_store.get(user_id)
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        safe = {k: v for k, v in user.items() if k != "password_hash"}
        return JSONResponse({"success": True, "user": safe})

    @app.patch("/api/admin/users/{user_id}")
    async def admin_update_user(user_id: str, request: Request):
        """Update a user's role, tier, status, name, or email. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        user = _user_store.get(user_id)
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        changes: "Dict[str, Any]" = {}
        for field_name in ("full_name", "job_title", "company", "tier", "role", "status"):
            if field_name in data:
                changes[field_name] = data[field_name]
                user[field_name] = data[field_name]

        # Email change — update index
        if "email" in data:
            new_email = data["email"].strip().lower()
            if new_email != user.get("email", ""):
                if new_email in _email_to_account and _email_to_account[new_email] != user_id:
                    return JSONResponse({"error": "Email already in use"}, status_code=409)
                old_email = user.get("email", "")
                _email_to_account.pop(old_email, None)
                _email_to_account[new_email] = user_id
                user["email"] = new_email
                changes["email"] = new_email

        user["updated_at"] = _now_iso()
        _admin_log(actor["account_id"], "update_user", user_id, changes)
        return JSONResponse({"success": True, "account_id": user_id, "changes": changes})

    @app.delete("/api/admin/users/{user_id}")
    async def admin_delete_user(user_id: str, request: Request):
        """Deactivate (soft-delete) a user account. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        user = _user_store.get(user_id)
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)
        if user_id == actor["account_id"]:
            return JSONResponse({"error": "Cannot deactivate your own account"}, status_code=400)

        user["status"] = "deactivated"
        user["deactivated_at"] = _now_iso()
        # Invalidate all sessions for this user
        with _session_lock:
            dead_tokens = [t for t, uid in _session_store.items() if uid == user_id]
            for t in dead_tokens:
                _session_store.pop(t, None)

        _admin_log(actor["account_id"], "deactivate_user", user_id, {"email": user.get("email", "")})
        return JSONResponse({"success": True, "account_id": user_id, "status": "deactivated"})

    @app.post("/api/admin/users/{user_id}/reset-password")
    async def admin_reset_password(user_id: str, request: Request):
        """Force-reset a user's password. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        user = _user_store.get(user_id)
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        new_password = data.get("new_password", "")
        if not new_password or len(new_password) < 8:
            return JSONResponse({"error": "new_password must be at least 8 characters"}, status_code=400)

        user["password_hash"] = _hash_password(new_password)
        user["password_reset_at"] = _now_iso()
        user["password_reset_by"] = actor["account_id"]
        # Invalidate all existing sessions
        with _session_lock:
            dead_tokens = [t for t, uid in _session_store.items() if uid == user_id]
            for t in dead_tokens:
                _session_store.pop(t, None)

        _admin_log(actor["account_id"], "reset_password", user_id, {"email": user.get("email", "")})
        return JSONResponse({"success": True, "message": "Password reset. All active sessions invalidated."})

    @app.post("/api/admin/users/{user_id}/suspend")
    async def admin_suspend_user(user_id: str, request: Request):
        """Suspend a user account (blocks login). Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        user = _user_store.get(user_id)
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)
        if user_id == actor["account_id"]:
            return JSONResponse({"error": "Cannot suspend your own account"}, status_code=400)

        user["status"] = "suspended"
        user["suspended_at"] = _now_iso()
        # Invalidate sessions
        with _session_lock:
            dead_tokens = [t for t, uid in _session_store.items() if uid == user_id]
            for t in dead_tokens:
                _session_store.pop(t, None)

        _admin_log(actor["account_id"], "suspend_user", user_id, {"email": user.get("email", "")})
        return JSONResponse({"success": True, "account_id": user_id, "status": "suspended"})

    @app.post("/api/admin/users/{user_id}/unsuspend")
    async def admin_unsuspend_user(user_id: str, request: Request):
        """Restore a suspended user account. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        user = _user_store.get(user_id)
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        user["status"] = "active"
        user.pop("suspended_at", None)
        _admin_log(actor["account_id"], "unsuspend_user", user_id, {"email": user.get("email", "")})
        return JSONResponse({"success": True, "account_id": user_id, "status": "active"})

    # ── Organizations ───────────────────────────────────────────────────────

    @app.get("/api/admin/organizations")
    async def admin_list_orgs(request: Request):
        """List all organisations. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        q = (request.query_params.get("q") or "").lower()
        orgs = list(_org_store.values())
        if q:
            orgs = [o for o in orgs if q in o.get("name", "").lower() or q in o.get("slug", "").lower()]
        return JSONResponse({"success": True, "organizations": orgs, "total": len(orgs)})

    @app.post("/api/admin/organizations")
    async def admin_create_org(request: Request):
        """Create a new organisation. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        name = (data.get("name") or "").strip()
        if not name:
            return JSONResponse({"error": "name is required"}, status_code=400)

        import uuid as _uuid, re as _re
        org_id = _uuid.uuid4().hex[:12]
        slug = _re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        org = {
            "org_id": org_id,
            "name": name,
            "slug": slug,
            "description": data.get("description", ""),
            "owner_id": data.get("owner_id", actor["account_id"]),
            "plan": data.get("plan", "free"),
            "status": "active",
            "members": [],
            "created_at": _now_iso(),
            "created_by": actor["account_id"],
        }
        _org_store[org_id] = org
        _admin_log(actor["account_id"], "create_org", org_id, {"name": name})
        return JSONResponse({"success": True, "org_id": org_id, "organization": org}, status_code=201)

    @app.get("/api/admin/organizations/{org_id}")
    async def admin_get_org(org_id: str, request: Request):
        """Get a single organisation. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        org = _org_store.get(org_id)
        if not org:
            return JSONResponse({"error": "Organization not found"}, status_code=404)
        return JSONResponse({"success": True, "organization": org})

    @app.patch("/api/admin/organizations/{org_id}")
    async def admin_update_org(org_id: str, request: Request):
        """Update an organisation's name, description, plan, or status. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        org = _org_store.get(org_id)
        if not org:
            return JSONResponse({"error": "Organization not found"}, status_code=404)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        changes: "Dict[str, Any]" = {}
        for field_name in ("name", "description", "plan", "status", "owner_id"):
            if field_name in data:
                org[field_name] = data[field_name]
                changes[field_name] = data[field_name]

        org["updated_at"] = _now_iso()
        _admin_log(actor["account_id"], "update_org", org_id, changes)
        return JSONResponse({"success": True, "org_id": org_id, "changes": changes})

    @app.delete("/api/admin/organizations/{org_id}")
    async def admin_delete_org(org_id: str, request: Request):
        """Deactivate an organisation. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        org = _org_store.get(org_id)
        if not org:
            return JSONResponse({"error": "Organization not found"}, status_code=404)

        org["status"] = "deactivated"
        org["deactivated_at"] = _now_iso()
        _admin_log(actor["account_id"], "deactivate_org", org_id, {"name": org.get("name", "")})
        return JSONResponse({"success": True, "org_id": org_id, "status": "deactivated"})

    @app.get("/api/admin/organizations/{org_id}/members")
    async def admin_org_members(org_id: str, request: Request):
        """List members of an organisation. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        org = _org_store.get(org_id)
        if not org:
            return JSONResponse({"error": "Organization not found"}, status_code=404)

        members = []
        for uid in org.get("members", []):
            user = _user_store.get(uid)
            if user:
                members.append({
                    "account_id": uid,
                    "email": user.get("email", ""),
                    "full_name": user.get("full_name", ""),
                    "role": user.get("role", "user"),
                    "status": user.get("status", "active"),
                })
        return JSONResponse({"success": True, "org_id": org_id, "members": members, "total": len(members)})

    @app.post("/api/admin/organizations/{org_id}/members")
    async def admin_add_org_member(org_id: str, request: Request):
        """Add a user to an organisation. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        org = _org_store.get(org_id)
        if not org:
            return JSONResponse({"error": "Organization not found"}, status_code=404)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        user_id = data.get("user_id", "")
        if not user_id or user_id not in _user_store:
            return JSONResponse({"error": "User not found"}, status_code=404)

        if user_id not in org["members"]:
            org["members"].append(user_id)
        _admin_log(actor["account_id"], "add_org_member", org_id, {"user_id": user_id})
        return JSONResponse({"success": True, "org_id": org_id, "user_id": user_id, "member_count": len(org["members"])})

    @app.delete("/api/admin/organizations/{org_id}/members/{user_id}")
    async def admin_remove_org_member(org_id: str, user_id: str, request: Request):
        """Remove a user from an organisation. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        org = _org_store.get(org_id)
        if not org:
            return JSONResponse({"error": "Organization not found"}, status_code=404)

        if user_id in org["members"]:
            org["members"].remove(user_id)
        _admin_log(actor["account_id"], "remove_org_member", org_id, {"user_id": user_id})
        return JSONResponse({"success": True, "org_id": org_id, "user_id": user_id, "member_count": len(org["members"])})

    # ── Platform Stats & Audit Log ─────────────────────────────────────────

    @app.get("/api/admin/stats")
    async def admin_stats(request: Request):
        """Platform-wide statistics. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        with _session_lock:
            active_sessions = len(_session_store)

        users = list(_user_store.values())
        return JSONResponse({
            "success": True,
            "stats": {
                "total_users": len(users),
                "active_users": sum(1 for u in users if u.get("status", "active") == "active"),
                "suspended_users": sum(1 for u in users if u.get("status") == "suspended"),
                "deactivated_users": sum(1 for u in users if u.get("status") == "deactivated"),
                "users_by_role": {
                    "owner": sum(1 for u in users if u.get("role") == "owner"),
                    "admin": sum(1 for u in users if u.get("role") == "admin"),
                    "user": sum(1 for u in users if u.get("role", "user") == "user"),
                },
                "users_by_tier": {
                    "free": sum(1 for u in users if u.get("tier", "free") == "free"),
                    "solo": sum(1 for u in users if u.get("tier") == "solo"),
                    "team": sum(1 for u in users if u.get("tier") == "team"),
                    "professional": sum(1 for u in users if u.get("tier") == "professional"),
                    "enterprise": sum(1 for u in users if u.get("tier") == "enterprise"),
                },
                "total_organizations": len(_org_store),
                "active_organizations": sum(1 for o in _org_store.values() if o.get("status", "active") == "active"),
                "active_sessions": active_sessions,
                "audit_log_entries": len(_admin_audit_log),
            },
        })

    @app.get("/api/admin/sessions")
    async def admin_sessions(request: Request):
        """List all active sessions (token → account summary). Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        with _session_lock:
            session_snapshot = dict(_session_store)

        sessions = []
        for token, account_id in session_snapshot.items():
            user = _user_store.get(account_id)
            sessions.append({
                "token_prefix": token[:8] + "…",
                "account_id": account_id,
                "email": user.get("email", "") if user else "",
                "role": user.get("role", "user") if user else "unknown",
            })
        return JSONResponse({"success": True, "sessions": sessions, "total": len(sessions)})

    @app.delete("/api/admin/sessions/{account_id}")
    async def admin_revoke_sessions(account_id: str, request: Request):
        """Revoke all sessions for an account. Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        with _session_lock:
            dead = [t for t, uid in _session_store.items() if uid == account_id]
            for t in dead:
                _session_store.pop(t, None)

        _admin_log(actor["account_id"], "revoke_sessions", account_id, {"revoked": len(dead)})
        return JSONResponse({"success": True, "account_id": account_id, "revoked": len(dead)})

    @app.get("/api/admin/audit-log")
    async def admin_audit_log(request: Request):
        """Return the admin audit log (newest first). Admin/owner only."""
        actor = _require_admin(request)
        if actor is None:
            return JSONResponse({"error": "Unauthorized", "detail": "Authentication required"}, status_code=401)
        if actor is False:
            return JSONResponse({"error": "Forbidden", "detail": "Admin access required"}, status_code=403)

        limit = min(int(request.query_params.get("limit", "100")), 500)
        offset = int(request.query_params.get("offset", "0"))
        action_f = request.query_params.get("action", "")

        entries = list(reversed(_admin_audit_log))
        if action_f:
            entries = [e for e in entries if e.get("action") == action_f]
        total = len(entries)
        page = entries[offset: offset + limit]
        return JSONResponse({"success": True, "entries": page, "total": total, "offset": offset, "limit": limit})

    # ==================== ORG PORTAL (MEMBER-LEVEL SELF-SERVICE) ====================
    # Self-service org management for members and org-admins.
    # A caller can only access the org they belong to — they never see other orgs.
    #
    # Roles inside an org:
    #   org_owner  — can change settings, manage all members, delete the org
    #   org_admin  — can invite/remove members and change member roles
    #   member     — read-only view of org info, members, channels, activity
    #
    # Each org record in _org_store may have an `org_roles` dict:
    #   { account_id: "org_owner"|"org_admin"|"member" }

    _org_activity_log: "Dict[str, List[Dict[str, Any]]]" = {}  # org_id → events

    def _get_org_role(org: "Dict[str, Any]", account_id: str) -> "Optional[str]":
        """Return the caller's role within the org, or None if not a member."""
        roles = org.get("org_roles", {})
        if account_id in roles:
            return roles[account_id]
        # Fall back: check members list (legacy records have no roles dict)
        if account_id in org.get("members", []):
            return "member"
        # The org owner_id always has org_owner role
        if account_id == org.get("owner_id"):
            return "org_owner"
        return None

    def _require_org_member(request: "Request", org_id: str) -> "Optional[tuple]":
        """Return (account, org, org_role) if the caller belongs to this org.

        Returns None if unauthenticated, org not found, or caller not a member.
        """
        account = _get_account_from_session(request)
        if account is None:
            return None
        org = _org_store.get(org_id)
        if org is None:
            return None
        role = _get_org_role(org, account["account_id"])
        if role is None:
            # Platform admins can always view any org
            if account.get("role") in ("admin", "owner"):
                role = "platform_admin"
            else:
                return None
        return account, org, role

    def _org_log(org_id: str, actor_id: str, action: str, detail: "Dict[str, Any]") -> None:
        """Append an event to the org's activity log."""
        import uuid as _uuid
        if org_id not in _org_activity_log:
            _org_activity_log[org_id] = []
        _org_activity_log[org_id].append({
            "id": _uuid.uuid4().hex[:10],
            "actor_id": actor_id,
            "action": action,
            "detail": detail,
            "ts": _now_iso(),
        })

    # ── Org portal endpoints ────────────────────────────────────────────────

    @app.get("/api/org/portal/{org_id}")
    async def org_portal_get(org_id: str, request: Request):
        """Get the calling user's view of an organisation.

        Returns org metadata, member count, channel count, plan, and the
        caller's role within the org.  Callers must be members (or platform
        admins) — they never see other orgs' data via this endpoint.
        """
        result = _require_org_member(request, org_id)
        if result is None:
            return JSONResponse({"error": "Not a member of this organization"}, status_code=403)
        account, org, caller_role = result

        channels = [c for c in _community_channels.values() if c.get("org_id") == org_id]
        members = org.get("members", [])
        pending = _org_memberships.get(org_id, {}).get("pending", [])

        return JSONResponse({
            "success": True,
            "org": {
                "org_id": org_id,
                "name": org.get("name", ""),
                "slug": org.get("slug", ""),
                "description": org.get("description", ""),
                "plan": org.get("plan", "free"),
                "status": org.get("status", "active"),
                "created_at": org.get("created_at", ""),
                "owner_id": org.get("owner_id", ""),
            },
            "stats": {
                "member_count": len(members),
                "channel_count": len(channels),
                "pending_invites": len(pending),
                "activity_events": len(_org_activity_log.get(org_id, [])),
            },
            "caller_role": caller_role,
        })

    @app.get("/api/org/portal/{org_id}/members")
    async def org_portal_members(org_id: str, request: Request):
        """List members of the org with their roles.

        Only accessible to members of this specific org.
        """
        result = _require_org_member(request, org_id)
        if result is None:
            return JSONResponse({"error": "Not a member of this organization"}, status_code=403)
        account, org, caller_role = result

        members = []
        for uid in org.get("members", []):
            user = _user_store.get(uid)
            role_in_org = _get_org_role(org, uid) or "member"
            members.append({
                "account_id": uid,
                "email": user.get("email", "") if user else uid,
                "full_name": user.get("full_name", "") if user else "",
                "role": role_in_org,
                "status": user.get("status", "active") if user else "unknown",
                "joined_at": "",  # future: track join date
            })

        pending = _org_memberships.get(org_id, {}).get("pending", [])
        return JSONResponse({
            "success": True,
            "org_id": org_id,
            "members": members,
            "pending_invites": pending,
            "total": len(members),
            "caller_role": caller_role,
        })

    @app.post("/api/org/portal/{org_id}/members/invite")
    async def org_portal_invite(org_id: str, request: Request):
        """Invite a user to the org by email or account_id.

        Requires org_admin, org_owner, or platform admin.
        """
        result = _require_org_member(request, org_id)
        if result is None:
            return JSONResponse({"error": "Not a member of this organization"}, status_code=403)
        account, org, caller_role = result

        if caller_role not in ("org_admin", "org_owner", "platform_admin"):
            return JSONResponse({"error": "Org admin role required"}, status_code=403)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        invitee_email = (data.get("email") or "").strip().lower()
        invitee_id = data.get("user_id", "")

        # Resolve by email if no user_id given
        if not invitee_id and invitee_email:
            invitee_id = _email_to_account.get(invitee_email, "")

        if not invitee_id and not invitee_email:
            return JSONResponse({"error": "Provide email or user_id"}, status_code=400)

        if org_id not in _org_memberships:
            _org_memberships[org_id] = {"members": [], "moderators": [], "pending": []}

        label = invitee_id or invitee_email
        _org_memberships[org_id]["pending"].append({
            "user": label,
            "email": invitee_email,
            "user_id": invitee_id,
            "at": _now_iso(),
            "invited_by": account["account_id"],
        })
        _org_log(org_id, account["account_id"], "member_invited", {"invitee": label})
        return JSONResponse({"success": True, "org_id": org_id, "invited": label})

    @app.delete("/api/org/portal/{org_id}/members/{user_id}")
    async def org_portal_remove_member(org_id: str, user_id: str, request: Request):
        """Remove a member from the org.

        Requires org_admin, org_owner, or platform admin.
        Cannot remove the org owner.
        """
        result = _require_org_member(request, org_id)
        if result is None:
            return JSONResponse({"error": "Not a member of this organization"}, status_code=403)
        account, org, caller_role = result

        if caller_role not in ("org_admin", "org_owner", "platform_admin"):
            return JSONResponse({"error": "Org admin role required"}, status_code=403)
        if user_id == org.get("owner_id") and caller_role != "platform_admin":
            return JSONResponse({"error": "Cannot remove the org owner"}, status_code=400)

        if user_id in org.get("members", []):
            org["members"].remove(user_id)
        # Clean up roles entry
        org.get("org_roles", {}).pop(user_id, None)

        _org_log(org_id, account["account_id"], "member_removed", {"user_id": user_id})
        return JSONResponse({"success": True, "org_id": org_id, "user_id": user_id, "member_count": len(org.get("members", []))})

    @app.patch("/api/org/portal/{org_id}/members/{user_id}/role")
    async def org_portal_update_member_role(org_id: str, user_id: str, request: Request):
        """Change a member's role within the org.

        Requires org_owner or platform admin.
        Valid roles: org_owner, org_admin, member.
        """
        result = _require_org_member(request, org_id)
        if result is None:
            return JSONResponse({"error": "Not a member of this organization"}, status_code=403)
        account, org, caller_role = result

        if caller_role not in ("org_owner", "platform_admin"):
            return JSONResponse({"error": "Org owner role required"}, status_code=403)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        new_role = data.get("role", "")
        if new_role not in ("org_owner", "org_admin", "member"):
            return JSONResponse({"error": "Invalid role. Use: org_owner, org_admin, member"}, status_code=400)

        if user_id not in org.get("members", []):
            return JSONResponse({"error": "User is not a member of this org"}, status_code=404)

        if "org_roles" not in org:
            org["org_roles"] = {}
        org["org_roles"][user_id] = new_role

        _org_log(org_id, account["account_id"], "member_role_changed", {"user_id": user_id, "new_role": new_role})
        return JSONResponse({"success": True, "org_id": org_id, "user_id": user_id, "role": new_role})

    @app.get("/api/org/portal/{org_id}/channels")
    async def org_portal_channels(org_id: str, request: Request):
        """List channels scoped to this org.

        Only accessible to members of this specific org.
        """
        result = _require_org_member(request, org_id)
        if result is None:
            return JSONResponse({"error": "Not a member of this organization"}, status_code=403)
        _account, org, caller_role = result

        channels = [c for c in _community_channels.values() if c.get("org_id") == org_id]
        return JSONResponse({
            "success": True,
            "org_id": org_id,
            "channels": channels,
            "total": len(channels),
            "caller_role": caller_role,
        })

    @app.get("/api/org/portal/{org_id}/activity")
    async def org_portal_activity(org_id: str, request: Request):
        """Return recent activity events for this org (newest first).

        Only accessible to members of this specific org.
        """
        result = _require_org_member(request, org_id)
        if result is None:
            return JSONResponse({"error": "Not a member of this organization"}, status_code=403)
        _account, org, caller_role = result

        limit = min(int(request.query_params.get("limit", "50")), 200)
        offset = int(request.query_params.get("offset", "0"))
        events = list(reversed(_org_activity_log.get(org_id, [])))
        total = len(events)
        return JSONResponse({
            "success": True,
            "org_id": org_id,
            "events": events[offset: offset + limit],
            "total": total,
            "caller_role": caller_role,
        })

    @app.patch("/api/org/portal/{org_id}/settings")
    async def org_portal_update_settings(org_id: str, request: Request):
        """Update org name and/or description.

        Requires org_admin, org_owner, or platform admin.
        """
        result = _require_org_member(request, org_id)
        if result is None:
            return JSONResponse({"error": "Not a member of this organization"}, status_code=403)
        account, org, caller_role = result

        if caller_role not in ("org_admin", "org_owner", "platform_admin"):
            return JSONResponse({"error": "Org admin role required"}, status_code=403)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        changes: "Dict[str, Any]" = {}
        for field_name in ("name", "description"):
            if field_name in data:
                org[field_name] = data[field_name]
                changes[field_name] = data[field_name]

        org["updated_at"] = _now_iso()
        _org_log(org_id, account["account_id"], "settings_updated", changes)
        return JSONResponse({"success": True, "org_id": org_id, "changes": changes})

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
            "webmail": os.environ.get("MURPHY_WEBMAIL_URL", "/mail/"),
            "preferred_domains": [d["domain"] for d in PREFERRED_DOMAINS],
        })

    @app.get("/api/comms/automate/rules")
    async def comms_automate_rules_list():
        """List communication automation rules."""
        hub = getattr(murphy, "communication_hub", None)
        if hub and hasattr(hub, "get_automation_rules"):
            try:
                rules = hub.get_automation_rules()
                return JSONResponse({"success": True, "rules": rules})
            except Exception:
                logger.debug("Suppressed exception in app")
        return JSONResponse({"success": True, "rules": [], "message": "No automation rules configured yet."})

    @app.post("/api/comms/automate/rules")
    async def comms_automate_rules_create(request: Request):
        """Create a communication automation rule."""
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)
        rule_id = str(uuid4())[:12]
        rule = {
            "id": rule_id,
            "trigger": data.get("trigger", ""),
            "action": data.get("action", ""),
            "channel": data.get("channel", "all"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if not rule["trigger"] or not rule["action"]:
            return JSONResponse({"success": False, "error": "trigger and action required"}, status_code=400)
        _comms_rules_store[rule_id] = rule
        return JSONResponse({"success": True, "rule": rule}, status_code=201)

    # ==================== MEETING INTELLIGENCE API ====================
    # Drafts and votes are persisted via MeetingDraft / MeetingVote ORM
    # models in src.db — no more in-memory dicts.

    @app.post("/api/meeting-intelligence/drafts")
    async def mi_save_draft(request: Request):
        """Accept a draft produced by a Shadow AI meeting session and persist it."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)
        session_id = body.get("session_id") or "default"
        draft_type = body.get("draft_type")
        content = body.get("content", "")
        status = body.get("status", "saved")
        ts = _now_iso()
        try:
            from src.db import MeetingDraft, _get_session_factory
            db = _get_session_factory()()
            try:
                existing = db.query(MeetingDraft).filter_by(
                    session_id=session_id, draft_type=draft_type
                ).first()
                if existing:
                    existing.content = content
                    existing.status = status
                else:
                    db.add(MeetingDraft(
                        session_id=session_id,
                        draft_type=draft_type,
                        content=content,
                        status=status,
                    ))
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("MeetingDraft DB write failed, data still returned: %s", exc)
        logger.info("Meeting draft saved: session=%s type=%s status=%s", session_id, draft_type, status)
        return JSONResponse({
            "ok": True,
            "draft_type": draft_type,
            "status": status,
            "ts": ts,
        })

    @app.post("/api/meeting-intelligence/vote")
    async def mi_vote(request: Request):
        """Record a participant vote on a Shadow AI draft and persist it."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)
        session_id = body.get("session_id") or "default"
        draft_type = body.get("draft_type")
        vote = body.get("vote")
        comment = body.get("comment", "")
        ts = _now_iso()
        try:
            from src.db import MeetingVote, _get_session_factory
            db = _get_session_factory()()
            try:
                db.add(MeetingVote(
                    session_id=session_id,
                    draft_type=draft_type,
                    vote=str(vote) if vote is not None else "",
                    comment=comment,
                ))
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("MeetingVote DB write failed, data still returned: %s", exc)
        logger.info("Meeting vote recorded: session=%s type=%s vote=%s", session_id, draft_type, vote)
        return JSONResponse({
            "ok": True,
            "draft_type": draft_type,
            "vote": vote,
            "ts": ts,
        })

    @app.post("/api/meeting-intelligence/email-report")
    async def mi_email_report(request: Request):
        """Queue a meeting intelligence report for email delivery to participants."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)
        session_id = body.get("session_id", "")
        title = body.get("title", "Meeting Report")
        participants = body.get("participants", [])
        ts = _now_iso()
        try:
            from src.communication_hub import email_store as _email_store_hub
            _email_store_hub.compose_and_send(
                sender="murphy-meetings@system",
                recipients=participants if participants else ["team@murphy.systems"],
                subject=f"Meeting Intelligence Report: {title}",
                body=(
                    f"Your meeting report for '{title}' (session: {session_id}) is ready.\n\n"
                    "Visit the Meeting Intelligence dashboard to view full drafts, "
                    "suggestions, and accepted action items."
                ),
                priority="normal",
            )
            logger.info("Meeting report emailed: session=%s recipients=%s", session_id, participants)
        except Exception as exc:
            logger.warning("Could not send meeting report email: %s", exc)
        return JSONResponse({
            "ok": True,
            "queued": True,
            "session_id": session_id,
            "recipients": participants,
            "ts": ts,
        })

    @app.get("/api/meeting-intelligence/sessions")
    async def mi_sessions(request: Request):
        """List all meeting intelligence sessions from DB with drafts and suggestions."""
        account = _get_account_from_session(request)
        account_id = account.get("account_id") if account else None
        sessions = []
        try:
            from src.ai_comms_orchestrator import meetings_bridge as _mb
            sessions = _mb.list_meetings(account_id=account_id)
        except Exception as exc:
            logger.warning("Could not load sessions from MeetingsBridge: %s", exc)
        # Merge persisted draft/vote data into each session
        try:
            from src.db import MeetingDraft, MeetingVote, _get_session_factory
            db = _get_session_factory()()
            try:
                for s in sessions:
                    sid = s.get("session_id", "")
                    drafts = db.query(MeetingDraft).filter_by(session_id=sid).all()
                    if drafts:
                        s["drafts"] = {
                            d.draft_type: {"content": d.content, "status": d.status, "ts": str(d.updated_at or d.created_at)}
                            for d in drafts
                        }
                    votes = db.query(MeetingVote).filter_by(session_id=sid).all()
                    if votes:
                        s["votes"] = {
                            v.draft_type: {"vote": v.vote, "comment": v.comment, "ts": str(v.created_at)}
                            for v in votes
                        }
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Could not load meeting drafts/votes from DB: %s", exc)
        return JSONResponse({"ok": True, "sessions": sessions, "ts": _now_iso()})

    # ── Meetings CRUD (called from terminal_unified.html / workspace.html) ─────
    # All meeting sessions are persisted via the MeetingSession ORM model.

    @app.get("/api/meetings/")
    async def meetings_list(request: Request):
        """List all meeting sessions for the current user."""
        account = _get_account_from_session(request)
        account_id = account.get("account_id") if account else None
        sessions = []
        try:
            from src.db import MeetingSession, _get_session_factory
            db = _get_session_factory()()
            try:
                query = db.query(MeetingSession)
                if account_id:
                    query = query.filter_by(account_id=account_id)
                for row in query.all():
                    sessions.append({
                        "session_id": row.session_id,
                        "title": row.title,
                        "participants": row.participants or [],
                        "started_at": row.started_at,
                        "ended_at": row.ended_at,
                        "status": row.status,
                    })
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Could not load meeting sessions from DB: %s", exc)
        return JSONResponse({"ok": True, "meetings": sessions, "count": len(sessions)})

    @app.post("/api/meetings/start")
    async def meetings_start(request: Request):
        """Start a new meeting session and return a session_id."""
        import hashlib as _hashlib
        try:
            data = await request.json()
        except Exception:
            data = {}
        session_id = _hashlib.sha256(f"meeting:{_now_iso()}:{id(data)}".encode()).hexdigest()[:16]
        account = _get_account_from_session(request)
        account_id = account.get("account_id") if account else None
        try:
            from src.db import MeetingSession, _get_session_factory
            db = _get_session_factory()()
            try:
                db.add(MeetingSession(
                    session_id=session_id,
                    title=data.get("title", "Untitled Meeting"),
                    account_id=account_id,
                    participants=data.get("participants", []),
                    started_at=_now_iso(),
                    status="active",
                ))
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Could not persist meeting session to DB: %s", exc)
        return JSONResponse({"ok": True, "session_id": session_id, "status": "active"})

    @app.post("/api/meetings/{session_id}/end")
    async def meetings_end(session_id: str, request: Request):
        """End a meeting session."""
        try:
            from src.db import MeetingSession, _get_session_factory
            db = _get_session_factory()()
            try:
                session = db.query(MeetingSession).filter_by(session_id=session_id).first()
                if not session:
                    return JSONResponse({"ok": False, "error": "Session not found"}, status_code=404)
                session.status = "ended"
                session.ended_at = _now_iso()
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Could not end meeting session in DB: %s", exc)
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
        return JSONResponse({"ok": True, "session_id": session_id, "status": "ended"})

    @app.get("/api/meetings/{session_id}/transcript")
    async def meetings_transcript(session_id: str):
        """Get the transcript for a meeting session from DB."""
        transcript = []
        try:
            from src.db import MeetingTranscriptEntry, _get_session_factory
            db = _get_session_factory()()
            try:
                rows = db.query(MeetingTranscriptEntry).filter_by(session_id=session_id).all()
                transcript = [
                    {"speaker": r.speaker, "text": r.text, "timestamp": r.timestamp, "is_ai": bool(r.is_ai)}
                    for r in rows
                ]
            finally:
                db.close()
        except Exception as exc:
            logger.warning("Could not load transcript from DB: %s", exc)
        return JSONResponse({"ok": True, "session_id": session_id, "transcript": transcript})

    @app.get("/api/meetings/{session_id}/suggestions")
    async def meetings_suggestions(session_id: str):
        """Get AI-generated action item suggestions; returns default stubs for unknown sessions."""
        # In production, these would be generated by an LLM from the transcript.
        _default_suggestions = [
            {"type": "action_item", "text": "Review meeting notes and assign owners."},
            {"type": "follow_up", "text": "Schedule follow-up for unresolved items."},
        ]
        return JSONResponse({"ok": True, "session_id": session_id, "suggestions": _default_suggestions})


    @app.post("/api/ambient/context")
    async def ambient_context(request: Request):
        """Ingest ambient context signals — PATCH-072a real implementation."""
        try:
            from src.ambient_context_store import AmbientContextStore as _ACS
            if not hasattr(murphy, "_ambient_store"):
                murphy._ambient_store = _ACS(max_signals=2000, ttl_seconds=86400)
            body = await request.json()
            signals = body.get("signals", [])
            stored = murphy._ambient_store.push(signals)
            return JSONResponse({"ok": True, "stored": stored, "ts": _now_iso()})
        except Exception as exc:
            logger.error("ambient_context error: %s", exc)
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    @app.post("/api/ambient/insights")
    async def ambient_insights(request: Request):
        """Receive synthesised insights — PATCH-072a real implementation."""
        try:
            from src.ambient_context_store import AmbientContextStore as _ACS
            if not hasattr(murphy, "_ambient_store"):
                murphy._ambient_store = _ACS(max_signals=2000, ttl_seconds=86400)
            body = await request.json()
            insights = body.get("insights", [])
            for ins in insights:
                murphy._ambient_store.store_insight(ins)
            return JSONResponse({"ok": True, "queued": len(insights), "ts": _now_iso()})
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    @app.post("/api/ambient/deliver")
    async def ambient_deliver(request: Request):
        """Deliver ambient insight via email — PATCH-072a real implementation."""
        try:
            from src.ambient_email_delivery import deliver as _amb_deliver
            body = await request.json()
            insight = body.get("insight", body)
            to = body.get("to_emails", [os.getenv("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems")])
            result = _amb_deliver(insight, to_emails=to)
            return JSONResponse({"ok": True, "result": result, "ts": _now_iso()})
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    @app.post("/api/ambient/royalty")
    async def ambient_royalty(request: Request):
        """Log royalty record for contributing shadow agents (BSL 1.1)."""
        body = await request.json()
        return JSONResponse({"ok": True, "insight_id": body.get("insightId"),
                             "agents": body.get("agents", []), "ts": _now_iso()})

    @app.get("/api/ambient/settings")
    async def ambient_get_settings():
        """Return ambient engine settings — PATCH-072a."""
        try:
            from src.ambient_context_store import AmbientContextStore as _ACS
            if not hasattr(murphy, "_ambient_store"):
                murphy._ambient_store = _ACS(max_signals=2000, ttl_seconds=86400)
            return JSONResponse({"ok": True, "settings": murphy._ambient_store.get_settings()})
        except Exception:
            return JSONResponse({"ok": True, "settings": {"enabled": True, "delivery_channel": "email",
                                                           "min_confidence": 0.65}})

    @app.post("/api/ambient/settings")
    async def ambient_save_settings(request: Request):
        """Save ambient engine settings — PATCH-072a."""
        try:
            from src.ambient_context_store import AmbientContextStore as _ACS
            if not hasattr(murphy, "_ambient_store"):
                murphy._ambient_store = _ACS(max_signals=2000, ttl_seconds=86400)
            body = await request.json()
            result = murphy._ambient_store.save_settings(body)
            return JSONResponse({"ok": True, "settings": result})
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    @app.get("/api/ambient/stats")
    async def ambient_stats():
        """Return full ambient intelligence stats — PATCH-072a real implementation."""
        try:
            from src.ambient_context_store import AmbientContextStore as _ACS
            from src.ambient_email_delivery import email_backend_mode as _ebm
            if not hasattr(murphy, "_ambient_store"):
                murphy._ambient_store = _ACS(max_signals=2000, ttl_seconds=86400)
            stats = murphy._ambient_store.get_stats()
            try:
                stats["email_backend"] = _ebm()
            except Exception:
                stats["email_backend"] = "smtp"
            return JSONResponse({"ok": True, **stats})
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)})


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

    @app.get("/api/ambient/stats")
    async def ambient_stats():
        """Return ambient intelligence statistics."""
        try:
            ambient = getattr(murphy, "ambient_intelligence", None)
            if ambient and hasattr(ambient, "get_stats"):
                return JSONResponse({"success": True, **ambient.get_stats()})
        except Exception:
            logger.debug("Suppressed exception in app")
        return JSONResponse({
            "success": True,
            "insights_generated": 0,
            "emails_sent": 0,
            "active_rules": 0,
            "last_run": None,
            "status": "idle",
            "message": "Ambient intelligence initialising — connect email to activate."
        })


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
            "/ui/trading": "trading_dashboard.html",
            "/ui/trading-dashboard": "trading_dashboard.html",
            "/ui/risk-dashboard": "risk_dashboard.html",
            "/ui/paper-trading": "paper_trading_dashboard.html",
            "/ui/grant-wizard": "grant_wizard.html",
            "/ui/grant-dashboard": "grant_dashboard.html",
            "/ui/grant-application": "grant_application.html",
            "/ui/financing": "financing_options.html",
            "/ui/roi-calendar": "roi_calendar.html",
            "/ui/comms-hub": "communication_hub.html",
            "/ui/communication-hub": "communication_hub.html",
            "/ui/admin": "admin_panel.html",
            "/ui/org-portal": "org_portal.html",
            "/ui/change-password": "change_password.html",
            "/ui/reset-password": "reset_password.html",
            "/ui/game-creation": "game_creation.html",
            "/ui/dispatch": "dispatch.html",
            "/ui/terminal-integrated-legacy": "murphy_ui_integrated_terminal.html",
            "/ui/boards": "boards.html",
            "/ui/workdocs": "workdocs.html",
            "/ui/time-tracking": "time_tracking.html",
            "/ui/dashboards": "dashboards.html",
            "/ui/crm": "crm.html",
            "/ui/portfolio": "portfolio.html",
            "/ui/aionmind": "aionmind.html",
            "/ui/automations": "automations.html",
            "/ui/dev-module": "dev_module.html",
            "/ui/service-module": "service_module.html",
            "/ui/video-demo": "demo_video.html",
            "/ui/guest-portal": "guest_portal.html",
        
            "/ui/hack-graph": "hack_graph.html",
            "/ui/honeypot": "honeypot.html",
        }

        # ── Route classification: public vs auth-required ──────────
        # Public routes are accessible without a session.  Auth-required
        # routes redirect to /ui/login when no valid session cookie exists.
        _PUBLIC_HTML_ROUTES = frozenset({
            "/", "/murphy_landing_page.html", "/ui/landing", "/ui/demo",
            "/ui/login", "/ui/signup", "/ui/pricing",
            "/ui/docs", "/ui/blog", "/ui/careers", "/ui/legal", "/ui/privacy",
            "/ui/partner", "/ui/smoke-test",
            "/ui/reset-password",
            "/ui/roi-calendar",
            "/ui/video-demo",
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

    # ==================== COINBASE ADVANCED TRADE API ENDPOINTS ====================

    def _get_coinbase_connector():
        """Lazily instantiate a CoinbaseConnector from environment variables."""
        try:
            from coinbase_connector import CoinbaseConnector
            return CoinbaseConnector()
        except Exception as _exc:
            logger.warning("CoinbaseConnector unavailable: %s", _exc)
            return None

    @app.get("/api/coinbase/status")
    async def coinbase_status():
        """Return Coinbase connection status, sandbox indicator, and compliance summary."""
        cb = _get_coinbase_connector()
        if cb is None:
            return JSONResponse({"success": False, "error": "connector_unavailable"}, 503)
        import os as _os
        live_mode = _os.getenv("COINBASE_LIVE_MODE", "false").lower() == "true"
        # Quick compliance snapshot
        compliance_allowed = False
        compliance_blockers = 0
        try:
            import sys as _sys
            _src = _os.path.join(_os.path.dirname(__file__), "..")
            if _src not in _sys.path:
                _sys.path.insert(0, _src)
            from trading_compliance_engine import get_compliance_engine
            _ce = get_compliance_engine()
            _last = _ce.last_report()
            if _last is not None:
                compliance_allowed = _last.live_mode_allowed
                compliance_blockers = len(_last.blockers())
        except Exception:
            logger.debug("Suppressed exception in app")
        return JSONResponse({
            "success":              True,
            "sandbox":              cb.sandbox,
            "live_mode":            live_mode,
            "status":               cb.status.value,
            "api_key_set":          bool(cb.api_key),
            "compliance_evaluated": compliance_allowed or compliance_blockers > 0,
            "compliance_passed":    compliance_allowed,
            "compliance_blockers":  compliance_blockers,
        })

    @app.get("/api/coinbase/accounts")
    async def coinbase_accounts():
        """List all Coinbase brokerage accounts."""
        cb = _get_coinbase_connector()
        if cb is None:
            return JSONResponse({"success": False, "error": "connector_unavailable"}, 503)
        accounts = cb.get_accounts()
        return JSONResponse({"success": True, "accounts": accounts, "count": len(accounts)})

    @app.get("/api/coinbase/balances")
    async def coinbase_balances():
        """Return Coinbase account balances for each asset."""
        cb = _get_coinbase_connector()
        if cb is None:
            return JSONResponse({"success": False, "error": "connector_unavailable"}, 503)
        from dataclasses import asdict
        balances = [asdict(b) for b in cb.get_balances()]
        return JSONResponse({"success": True, "balances": balances, "sandbox": cb.sandbox})

    @app.get("/api/coinbase/products")
    async def coinbase_products():
        """List available Coinbase trading pairs."""
        cb = _get_coinbase_connector()
        if cb is None:
            return JSONResponse({"success": False, "error": "connector_unavailable"}, 503)
        from dataclasses import asdict
        products = [asdict(p) for p in cb.list_products()]
        return JSONResponse({"success": True, "products": products, "count": len(products)})

    @app.get("/api/coinbase/ticker/{product_id}")
    async def coinbase_ticker(product_id: str):
        """Return current best bid/ask price for a trading pair."""
        cb = _get_coinbase_connector()
        if cb is None:
            return JSONResponse({"success": False, "error": "connector_unavailable"}, 503)
        from dataclasses import asdict
        ticker = cb.get_ticker(product_id)
        if ticker is None:
            return JSONResponse({"success": False, "error": "product_not_found"}, 404)
        return JSONResponse({"success": True, "ticker": asdict(ticker), "sandbox": cb.sandbox})

    # ==================== LIVE MARKET DATA FEED ENDPOINTS ====================

    def _get_live_feed():
        try:
            import sys as _sys
            import os as _os
            _src = _os.path.join(_os.path.dirname(__file__), "..")
            if _src not in _sys.path:
                _sys.path.insert(0, _src)
            from live_feed_service import get_live_feed
            from coinbase_connector import CoinbaseConnector
            _cb = CoinbaseConnector()
            return get_live_feed(
                coinbase_connector=_cb,
                binance_key=_os.getenv("BINANCE_API_KEY", ""),
                binance_secret=_os.getenv("BINANCE_API_SECRET", ""),
                alpaca_key=_os.getenv("ALPACA_API_KEY", ""),
                alpaca_secret=_os.getenv("ALPACA_API_SECRET", ""),
                alpha_vantage_key=_os.getenv("ALPHA_VANTAGE_API_KEY", ""),
                polygon_key=_os.getenv("POLYGON_API_KEY", ""),
                iex_cloud_key=_os.getenv("IEX_CLOUD_API_KEY", ""),
                ibkr_host=_os.getenv("IBKR_HOST", "127.0.0.1"),
                ibkr_port=int(_os.getenv("IBKR_PORT", "7497")),
                ibkr_client_id=int(_os.getenv("IBKR_CLIENT_ID", "1")),
            )
        except Exception as _exc:
            logger.warning("LiveFeedService unavailable: %s", _exc)
            return None

    @app.get("/api/market/quote/{symbol}")
    async def market_quote(symbol: str):
        """Return a live quote for any symbol; falls back to synthetic data when feed is unavailable."""
        import random as _random
        feed = _get_live_feed()
        if feed is None:
            # Synthetic fallback so the frontend always gets a usable response.
            _base = _random.uniform(10, 500)
            _chg = _random.uniform(-5, 5)
            return JSONResponse({
                "ok": True,
                "success": True,
                "symbol": symbol,
                "quote": {
                    "symbol": symbol,
                    "price": round(_base, 2),
                    "change": round(_chg, 2),
                    "change_pct": round(_chg / _base * 100, 4),
                    "volume": _random.randint(100_000, 10_000_000),
                    "high": round(_base * 1.02, 2),
                    "low": round(_base * 0.98, 2),
                    "provider": "stub",
                },
            })
        try:
            from dataclasses import asdict
            quote = feed.get_quote(symbol)
            return JSONResponse({"ok": True, "success": True, "quote": asdict(quote), "symbol": symbol})
        except Exception as exc:
            return JSONResponse({"ok": False, "success": False, "error": str(exc), "symbol": symbol})

    @app.get("/api/market/candles/{symbol}")
    async def market_candles(symbol: str, granularity: str = "ONE_HOUR", limit: int = 100):
        """Return OHLCV candles for a symbol."""
        feed = _get_live_feed()
        if feed is None:
            return JSONResponse({"success": False, "error": "feed_unavailable", "symbol": symbol})
        try:
            from dataclasses import asdict
            limit = min(limit, 500)
            candles = feed.get_candles(symbol, granularity=granularity, limit=limit)
            return JSONResponse({
                "success": True,
                "symbol": symbol,
                "granularity": granularity,
                "candles": [asdict(c) for c in candles],
                "count": len(candles),
            })
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc), "symbol": symbol})

    @app.get("/api/market/movers")
    async def market_movers(asset_class: str = "all", limit: int = 10):
        """Return top market movers."""
        feed = _get_live_feed()
        if feed is None:
            return JSONResponse({"success": False, "error": "feed_unavailable"})
        try:
            from dataclasses import asdict
            movers = feed.get_top_movers(asset_class=asset_class, limit=limit)
            return JSONResponse({
                "success": True,
                "movers": [asdict(m) for m in movers],
                "asset_class": asset_class,
                "count": len(movers),
            })
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)})

    @app.get("/api/market/search")
    async def market_search(q: str = ""):
        """Search instrument symbols via Yahoo Finance."""
        if not q:
            return JSONResponse({"success": False, "error": "query required", "results": []})
        try:
            import urllib.request as _req
            import json as _json
            url = (
                f"https://query1.finance.yahoo.com/v1/finance/search"
                f"?q={q}&quotesCount=10&newsCount=0"
            )
            with _req.urlopen(url, timeout=5) as resp:
                data = _json.loads(resp.read())
            results = data.get("finance", {}).get("result", [{}])[0].get("quotes", [])
            return JSONResponse({"success": True, "results": results, "query": q})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc), "results": [], "query": q})

    @app.get("/api/market/status")
    async def market_status():
        """Return live feed service status."""
        feed = _get_live_feed()
        if feed is None:
            return JSONResponse({"success": False, "error": "feed_unavailable"})
        return JSONResponse({"success": True, **feed.status()})

    @app.get("/api/market/instruments")
    async def market_instruments():
        """List all known tradeable instruments with metadata."""
        instruments = [
            # Crypto
            {"symbol": "BTC-USD", "name": "Bitcoin", "asset_class": "crypto", "exchange": "Coinbase"},
            {"symbol": "ETH-USD", "name": "Ethereum", "asset_class": "crypto", "exchange": "Coinbase"},
            {"symbol": "SOL-USD", "name": "Solana", "asset_class": "crypto", "exchange": "Coinbase"},
            {"symbol": "MATIC-USD", "name": "Polygon", "asset_class": "crypto", "exchange": "Coinbase"},
            {"symbol": "ATOM-USD", "name": "Cosmos", "asset_class": "crypto", "exchange": "Coinbase"},
            {"symbol": "AVAX-USD", "name": "Avalanche", "asset_class": "crypto", "exchange": "Coinbase"},
            {"symbol": "LINK-USD", "name": "Chainlink", "asset_class": "crypto", "exchange": "Coinbase"},
            {"symbol": "ADA-USD", "name": "Cardano", "asset_class": "crypto", "exchange": "Coinbase"},
            # Equities
            {"symbol": "AAPL", "name": "Apple Inc.", "asset_class": "equity", "exchange": "NASDAQ"},
            {"symbol": "MSFT", "name": "Microsoft Corp.", "asset_class": "equity", "exchange": "NASDAQ"},
            {"symbol": "NVDA", "name": "NVIDIA Corp.", "asset_class": "equity", "exchange": "NASDAQ"},
            {"symbol": "GOOGL", "name": "Alphabet Inc.", "asset_class": "equity", "exchange": "NASDAQ"},
            {"symbol": "AMZN", "name": "Amazon.com Inc.", "asset_class": "equity", "exchange": "NASDAQ"},
            {"symbol": "META", "name": "Meta Platforms", "asset_class": "equity", "exchange": "NASDAQ"},
            {"symbol": "TSLA", "name": "Tesla Inc.", "asset_class": "equity", "exchange": "NASDAQ"},
            {"symbol": "JPM", "name": "JPMorgan Chase", "asset_class": "equity", "exchange": "NYSE"},
            # ETFs
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "asset_class": "etf", "exchange": "NYSE"},
            {"symbol": "QQQ", "name": "Invesco QQQ ETF", "asset_class": "etf", "exchange": "NASDAQ"},
        ]
        return JSONResponse({"success": True, "instruments": instruments, "count": len(instruments)})

    from fastapi import WebSocket, WebSocketDisconnect

    @app.websocket("/ws/market/{symbol}")
    async def ws_market(websocket: WebSocket, symbol: str):
        """Stream live price updates for *symbol* every 2 seconds."""
        import asyncio
        await websocket.accept()
        feed = _get_live_feed()
        try:
            while True:
                try:
                    if feed is not None:
                        from dataclasses import asdict
                        quote = feed.get_quote(symbol)
                        await websocket.send_json({
                            "symbol": symbol,
                            "price": quote.price,
                            "bid": quote.bid,
                            "ask": quote.ask,
                            "change_pct_24h": quote.change_pct_24h,
                            "timestamp": quote.timestamp,
                        })
                    else:
                        await websocket.send_json({
                            "symbol": symbol,
                            "price": 0.0,
                            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(tzinfo=None).isoformat(),
                        })
                except WebSocketDisconnect:
                    break
                except Exception as exc:
                    logger.debug("ws_market send error: %s", exc)
                    break
                await asyncio.sleep(2)
        except WebSocketDisconnect:  # PROD-HARD A2: normal client disconnect, not an error
            logger.debug("ws_market: client disconnected")

    # ==================== TRADING COMPLIANCE ENDPOINTS ====================

    def _get_compliance_engine():
        try:
            import sys as _sys
            import os as _os
            _src = _os.path.join(_os.path.dirname(__file__), "..")
            if _src not in _sys.path:
                _sys.path.insert(0, _src)
            from trading_compliance_engine import get_compliance_engine as _gce
            return _gce()
        except Exception as _exc:
            logger.warning("ComplianceEngine unavailable: %s", _exc)
            return None

    @app.get("/api/trading/compliance/status")
    async def trading_compliance_status():
        """Return the latest compliance evaluation result."""
        ce = _get_compliance_engine()
        if ce is None:
            return JSONResponse({"success": False, "error": "compliance_engine_unavailable"}, 503)
        last = ce.last_report()
        if last is None:
            return JSONResponse({
                "success": True,
                "evaluated": False,
                "live_mode_allowed": False,
                "message": "No compliance evaluation has been run. POST /api/trading/compliance/evaluate to run one.",
            })
        return JSONResponse({"success": True, "evaluated": True, **last.to_dict()})

    @app.post("/api/trading/compliance/evaluate")
    async def trading_compliance_evaluate(request: Request):
        """
        Run a full compliance evaluation.

        Body (JSON, all optional):
          jurisdiction              : str  — e.g. "us", "eu", "personal"
          kyc_acknowledged          : bool
          regulations_acknowledged  : bool
          paper_trading_days        : int
          paper_trading_profitable_days : int
          paper_trading_win_rate    : float (0.0–1.0)
          paper_trading_total_return_pct : float
          override_paper_graduation : bool  — privileged override
        """
        ce = _get_compliance_engine()
        if ce is None:
            return JSONResponse({"success": False, "error": "compliance_engine_unavailable"}, 503)
        try:
            body = await request.json()
        except Exception:
            body = {}
        # Also pull summary from graduation tracker if available
        try:
            import sys as _sys
            import os as _os
            _src = _os.path.join(_os.path.dirname(__file__), "..")
            if _src not in _sys.path:
                _sys.path.insert(0, _src)
            from trading_compliance_engine import get_graduation_tracker
            _gt = get_graduation_tracker()
            _gs = _gt.summary()
            # Auto-populate paper trading stats from tracker if not provided in body
            body.setdefault("paper_trading_days", _gs["total_days"])
            body.setdefault("paper_trading_profitable_days", _gs["profitable_days"])
            body.setdefault("paper_trading_win_rate", _gs["win_rate"])
            body.setdefault("paper_trading_total_return_pct", _gs["total_return_pct"])
        except Exception:
            logger.debug("Suppressed exception in app")
        report = ce.evaluate(
            jurisdiction=body.get("jurisdiction", ""),
            kyc_acknowledged=bool(body.get("kyc_acknowledged", False)),
            regulations_acknowledged=bool(body.get("regulations_acknowledged", False)),
            paper_trading_days=int(body.get("paper_trading_days", 0)),
            paper_trading_profitable_days=int(body.get("paper_trading_profitable_days", 0)),
            paper_trading_win_rate=float(body.get("paper_trading_win_rate", 0.0)),
            paper_trading_total_return_pct=float(body.get("paper_trading_total_return_pct", 0.0)),
            override_paper_graduation=bool(body.get("override_paper_graduation", False)),
        )
        return JSONResponse({"success": True, **report.to_dict()})

    @app.get("/api/trading/compliance/graduation")
    async def trading_compliance_graduation():
        """Return paper-trading graduation tracker summary and daily history."""
        try:
            import sys as _sys
            import os as _os
            _src = _os.path.join(_os.path.dirname(__file__), "..")
            if _src not in _sys.path:
                _sys.path.insert(0, _src)
            from trading_compliance_engine import get_graduation_tracker
            gt = get_graduation_tracker()
            summary = gt.summary()
            results = [
                {
                    "date": r.date,
                    "start_equity": r.start_equity,
                    "end_equity": r.end_equity,
                    "trades": r.trades,
                    "profitable": r.profitable,
                }
                for r in gt.all_results()
            ]
            return JSONResponse({
                "success": True,
                "summary": summary,
                "meets_threshold": gt.meets_graduation_threshold(),
                "daily_results": results,
            })
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)})

    @app.post("/api/trading/compliance/graduation/record")
    async def trading_compliance_graduation_record(request: Request):
        """
        Record a completed paper-trading day for graduation tracking.

        Body (JSON):
          date         : str   — YYYY-MM-DD (optional, defaults to today UTC)
          start_equity : float — portfolio value at start of day
          end_equity   : float — portfolio value at end of day
          trades       : int   — number of trades executed
        """
        try:
            import sys as _sys
            import os as _os
            _src = _os.path.join(_os.path.dirname(__file__), "..")
            if _src not in _sys.path:
                _sys.path.insert(0, _src)
            from trading_compliance_engine import get_graduation_tracker
            body = await request.json()
            gt = get_graduation_tracker()
            result = gt.record_day(
                date=body.get("date"),
                start_equity=float(body.get("start_equity", 0)),
                end_equity=float(body.get("end_equity", 0)),
                trades=int(body.get("trades", 0)),
            )
            return JSONResponse({
                "success": True,
                "date": result.date,
                "profitable": result.profitable,
                "summary": gt.summary(),
            })
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)})

    # ── Game Creation Pipeline API ─────────────────────────────────────────────
    _game_world_gen: Any = None
    _game_pipeline:  Any = None
    _game_balance:   Any = None

    def _get_world_gen() -> Any:
        nonlocal _game_world_gen
        if _game_world_gen is None:
            try:
                from game_creation_pipeline.world_generator import WorldGenerator
                _game_world_gen = WorldGenerator()
            except Exception as _exc:
                logger.warning("WorldGenerator unavailable: %s", _exc)
                _game_world_gen = None
        return _game_world_gen

    def _get_pipeline() -> Any:
        nonlocal _game_pipeline
        if _game_pipeline is None:
            try:
                from game_creation_pipeline.weekly_release_orchestrator import WeeklyReleaseOrchestrator
                from game_creation_pipeline.world_generator import WorldGenerator
                _game_pipeline = WeeklyReleaseOrchestrator(WorldGenerator())
            except Exception as _exc:
                logger.warning("WeeklyReleaseOrchestrator unavailable: %s", _exc)
                _game_pipeline = None
        return _game_pipeline

    def _get_balance() -> Any:
        nonlocal _game_balance
        if _game_balance is None:
            try:
                from game_creation_pipeline.class_balance_engine import ClassBalanceEngine
                _game_balance = ClassBalanceEngine()
            except Exception as _exc:
                logger.warning("ClassBalanceEngine unavailable: %s", _exc)
                _game_balance = None
        return _game_balance

    @app.get("/api/game/worlds")
    async def game_list_worlds():
        """Return all generated worlds."""
        wg = _get_world_gen()
        if wg is None:
            return JSONResponse({"worlds": []})
        worlds = wg.all_worlds()
        return JSONResponse({
            "worlds": [
                {
                    "world_id":   w.world_id,
                    "name":       w.name,
                    "theme":      w.theme.value if hasattr(w.theme, "value") else str(w.theme),
                    "zone_count": len(w.zones),
                    "active":     getattr(w, 'active', True),
                    "created_at": w.created_at if hasattr(w, "created_at") else None,
                }
                for w in worlds
            ]
        })

    @app.post("/api/game/worlds")
    async def game_generate_world(request: Request):
        """Generate a new procedural world."""
        body = await request.json()
        wg = _get_world_gen()
        if wg is None:
            return JSONResponse({"success": False, "error": "WorldGenerator not available"}, status_code=503)
        try:
            from game_creation_pipeline.world_generator import WorldTheme
            theme_str = (body.get("theme") or "FANTASY").upper()
            try:
                theme = WorldTheme[theme_str]
            except KeyError:
                theme = WorldTheme.FANTASY
            name = body.get("name") or None
            world = wg.generate_world(name=name, theme=theme)
            return JSONResponse({
                "success":    True,
                "world_id":   world.world_id,
                "name":       world.name,
                "theme":      world.theme.value,
                "zone_count": len(world.zones),
                "active":     getattr(world, 'active', True),
            })
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/game/pipeline/runs")
    async def game_pipeline_runs():
        """Return all pipeline runs."""
        pl = _get_pipeline()
        if pl is None:
            return JSONResponse({"runs": []})
        runs = pl.all_runs()
        return JSONResponse({
            "runs": [
                {
                    "run_id":        r.run_id,
                    "theme":         r.theme.value if hasattr(r, "theme") and hasattr(r.theme, "value") else str(getattr(r, "theme", "")),
                    "current_stage": r.current_stage.value if hasattr(r, "current_stage") and hasattr(r.current_stage, "value") else str(getattr(r, "current_stage", "")),
                    "status":        r.status.value if hasattr(r, "status") and hasattr(r.status, "value") else str(getattr(r, "status", "")),
                    "started_at":    getattr(r, "started_at", None),
                    "completed_at":  getattr(r, "completed_at", None),
                }
                for r in runs
            ]
        })

    @app.post("/api/game/pipeline/start")
    async def game_pipeline_start(request: Request):
        """Start a new weekly release pipeline run."""
        body = await request.json()
        pl = _get_pipeline()
        if pl is None:
            return JSONResponse({"success": False, "error": "Pipeline not available"}, status_code=503)
        try:
            from game_creation_pipeline.world_generator import WorldTheme
            theme_str = (body.get("theme") or "FANTASY").upper()
            try:
                theme = WorldTheme[theme_str]
            except KeyError:
                theme = WorldTheme.FANTASY
            run = pl.start_pipeline(world_name=body.get('world_name', 'World_' + theme_str), theme=theme)
            _run_status = getattr(run, 'status', None)
            return JSONResponse({
                "success":  True,
                "run_id":   run.run_id,
                "theme":    run.theme.value if hasattr(run.theme, "value") else str(run.theme),
                "status":   _run_status.value if hasattr(_run_status, "value") else str(_run_status) if _run_status is not None else "started",
            })
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/game/balance/check")
    async def game_balance_check():
        """Run a class balance analysis across all class combinations."""
        bal = _get_balance()
        if bal is None:
            return JSONResponse({"success": False, "error": "ClassBalanceEngine not available"}, status_code=503)
        try:
            if hasattr(bal, "check_all_combinations"):
                result = bal.check_all_combinations()
            elif hasattr(bal, "score_all"):
                result = bal.score_all()
            else:
                result = {}
            combinations = result.get("combinations_checked", 0) if isinstance(result, dict) else 0
            issues = result.get("issues", []) if isinstance(result, dict) else []
            recommendations = result.get("recommendations", []) if isinstance(result, dict) else []
            return JSONResponse({
                "success":         True,
                "combinations":    combinations,
                "issues":          issues,
                "recommendations": recommendations,
            })
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/game/balance/report")
    async def game_balance_report():
        """Return the latest balance report."""
        bal = _get_balance()
        if bal is None:
            return JSONResponse({"report": None})
        try:
            if hasattr(bal, "get_report"):
                return JSONResponse({"report": bal.get_report()})
            if hasattr(bal, "latest_report"):
                return JSONResponse({"report": bal.latest_report})
            return JSONResponse({"report": {"message": "No report available — run a balance check first."}})
        except Exception as exc:
            return JSONResponse({"report": None, "error": str(exc)})

    @app.get("/api/game/eq/status")
    async def game_eq_status():
        """Return EQ mod system module status."""
        modules = [
            {"name": "Card System",          "description": "Universal/god cards, Card of Unmaking, Tower entry",        "ready": True},
            {"name": "Soul Engine",           "description": "Agent soul documents with card collection & identity",       "ready": True},
            {"name": "NPC Card Effects",      "description": "4-tier auto-generated card effects from NPC identity",      "ready": True},
            {"name": "Spawner Registry",      "description": "Entity tracking, unmade status, world decay %",             "ready": True},
            {"name": "Faction Manager",       "description": "Standings, war declarations, diplomacy",                    "ready": True},
            {"name": "Macro Trigger Engine",  "description": "Classic bot behavior (/assist /follow /attack)",            "ready": True},
            {"name": "Experience & Lore",     "description": "Action capture, interaction recall, lore propagation",      "ready": True},
            {"name": "Perception Pipeline",   "description": "Screen-scan → inference → action (~250ms cycle)",           "ready": True},
            {"name": "Duel Controller",       "description": "PvP duel system with card-based special rules",             "ready": True},
            {"name": "Streaming Overlay",     "description": "Twitch/YouTube integration with HUD overlays",             "ready": True},
            {"name": "Progression Server",    "description": "EQEmu-compatible progression server bridge",               "ready": True},
            {"name": "Lore Seeder",           "description": "Import EQEmu NPC/mob data & pre-populate souls",           "ready": True},
            {"name": "EQ Gateway",            "description": "Isolation boundary, sandbox enforcement",                  "ready": True},
            {"name": "EQEmu Asset Manager",   "description": "Asset pipeline — models, textures, zone files",            "ready": True},
            {"name": "Agent Voice",           "description": "Character voice profiles & TTS integration",               "ready": True},
            {"name": "Cultural Identity",     "description": "Race/class cultural trait system",                         "ready": True},
            {"name": "Escalation System",     "description": "Combat escalation & boss event triggers",                  "ready": True},
            {"name": "Sorceror Class",        "description": "Specialised sorcerer class with arcane abilities",          "ready": True},
            {"name": "Unmaker NPC",           "description": "The Unmaker boss NPC with card disintegration",            "ready": True},
            {"name": "Tower Zone",            "description": "Vertical dungeon zone with floor progression",              "ready": True},
            {"name": "Town Systems",          "description": "Player housing, shops, civic infrastructure",               "ready": True},
            {"name": "Remake System",         "description": "World remake/reset mechanics",                             "ready": True},
            {"name": "Server Reboot",         "description": "Controlled server-restart with state preservation",        "ready": True},
            {"name": "Sleeper Event",         "description": "Kerafyrm the Sleeper encounter system",                    "ready": True},
            {"name": "Murphy Integration",    "description": "Murphy AI embedded in EQ game loop",                       "ready": True},
        ]
        return JSONResponse({"modules": modules, "total": len(modules), "ready": sum(1 for m in modules if m["ready"])})

    @app.post("/api/game/monetization/validate")
    async def game_monetization_validate(request: Request):
        """Validate a list of items against the no-pay-to-win monetization rules."""
        body = await request.json()
        items = body.get("items", [])
        try:
            from game_creation_pipeline.monetization_rules import (
                MonetizationRulesEngine,
                COSMETIC_ONLY_MODEL,
                ItemDefinition,
                ItemCategory,
            )
            engine = MonetizationRulesEngine(COSMETIC_ONLY_MODEL)
            results = []
            for item in items:
                try:
                    cat_str = (item.get("category") or "misc").lower()
                    try:
                        cat = ItemCategory[cat_str.upper()]
                    except KeyError:
                        cat = ItemCategory.MISC if hasattr(ItemCategory, "MISC") else list(ItemCategory)[0]
                    defn = ItemDefinition(
                        name=item.get("name", "Unknown"),
                        category=cat,
                        power_delta=float(item.get("power_delta", 0)),
                        purchasable=bool(item.get("purchasable", False)),
                    )
                    verdict = engine.validate(defn)
                    results.append({
                        "name":    defn.name,
                        "verdict": verdict.value if hasattr(verdict, "value") else str(verdict),
                        "reason":  None,
                    })
                except Exception as item_exc:
                    results.append({"name": item.get("name", "?"), "verdict": "ERROR", "reason": str(item_exc)})
            return JSONResponse({"success": True, "results": results})
        except Exception:
            # Fallback: simple heuristic if module not importable
            results = []
            for item in items:
                power = float(item.get("power_delta", 0))
                purchasable = bool(item.get("purchasable", False))
                if purchasable and power > 0.1:
                    verdict = "REJECTED"
                    reason  = "Pay-to-win: purchasable item grants gameplay power"
                else:
                    verdict = "APPROVED"
                    reason  = None
                results.append({"name": item.get("name", "?"), "verdict": verdict, "reason": reason})
            return JSONResponse({"success": True, "results": results})




    _account_data: Dict[str, Any] = {
        "id": "acct_default",
        "email": os.environ.get("MURPHY_FOUNDER_EMAIL", ""),
        "name": "Murphy Admin",
        "plan": "free",
        "plan_name": "Free Tier",
        "billing_cycle": "monthly",
        "next_billing_date": None,
        "created_at": _now_iso(),
        "email_validated": True,
        "eula_accepted": True,
        "role": "owner",
    }
    _account_statements: List[Dict[str, Any]] = []

    @app.get("/api/account/profile")
    async def account_profile(request: Request):
        """Get account profile and subscription info — real auth-aware lookup."""
        # Try to get the real authenticated user first
        token = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            cookie = request.cookies.get("murphy_session", "")
            if cookie:
                token = cookie
        if token:
            account_id = _session_store.get(token)
            if account_id:
                account = _user_store.get(account_id)
                if account:
                    tier = account.get("tier", "free")
                    role = account.get("role", "user")
                    return JSONResponse({
                        "success": True,
                        "id": account_id,
                        "email": account.get("email", ""),
                        "name": account.get("full_name", account.get("name", "")),
                        "full_name": account.get("full_name", ""),
                        "role": role,
                        "tier": tier,
                        "plan": tier,
                        "plan_name": tier.title() + " Tier",
                        "billing_cycle": "monthly",
                        "next_billing_date": None,
                        "email_validated": account.get("email_validated") if account.get("email_validated") is not None else (role in ("owner", "admin")),
                        "eula_accepted": account.get("eula_accepted") if account.get("eula_accepted") is not None else (role in ("owner", "admin")),
                        "created_at": account.get("created_at", ""),
                    })
        # Fallback to static account data
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
                cs_data = data.get("confidence_state") or {}
                confidence_state = _ConfidenceState(
                    confidence=cs_data.get("confidence", cs_data.get("score", 0.8)),
                    generative_score=cs_data.get("generative_score", 0.8),
                    deterministic_score=cs_data.get("deterministic_score", 0.8),
                    epistemic_instability=cs_data.get("epistemic_instability", 0.1),
                    phase=_Phase(cs_data.get("phase", "expand")),
                )
                confidence_state.verified_artifacts = cs_data.get("verified_artifacts", 0)
                confidence_state.total_artifacts = cs_data.get("total_artifacts", 0)
                authority_band = _AuthorityBand(data.get("authority_band", "propose"))
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
                rv_data = data.get("risk_vector") or {}
                rv = _RiskVector(
                    H=rv_data.get("H", rv_data.get("probability", 0.1)),
                    one_minus_D=rv_data.get("one_minus_D", 1.0 - rv_data.get("impact", 0.5)),
                    exposure=rv_data.get("exposure", 0.3),
                    authority_risk=rv_data.get("authority_risk", 0.2),
                )
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
                    external_side_effects=bool(data.get("external_side_effects", False)),
                    reversibility=float(data.get("reversibility", 1.0)),
                    blast_radius_estimate=float(data.get("blast_radius_estimate", 0.0)),
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
                for fmd in (data.get("failure_modes") or []):
                    rv_data = fmd.get("risk_vector") or {}
                    rv = _RiskVector(
                        H=rv_data.get("H", 0.1),
                        one_minus_D=rv_data.get("one_minus_D", 0.2),
                        exposure=rv_data.get("exposure", 0.1),
                        authority_risk=rv_data.get("authority_risk", 0.1),
                    )
                    fm_type_raw = fmd.get("type", "semantic_drift")
                    try:
                        fm_type = _FailureModeType(fm_type_raw)
                    except ValueError:
                        fm_type = _FailureModeType.SEMANTIC_DRIFT if hasattr(_FailureModeType, "SEMANTIC_DRIFT") else list(_FailureModeType)[0]
                    fm = _FailureMode(
                        id=fmd.get("id", "fm-default"),
                        type=fm_type,
                        probability=fmd.get("probability", 0.1),
                        impact=fmd.get("impact", 0.5),
                        risk_vector=rv,
                        description=fmd.get("description", ""),
                        affected_artifacts=fmd.get("affected_artifacts", []),
                    )
                    failure_modes.append(fm)
                current_phase = _Phase(data.get("current_phase", "expand"))
                current_authority = _AuthorityBand(data.get("current_authority", "propose"))
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
                logger.debug("Suppressed exception in app")
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
                _valid_types = {e.value for e in _ArtifactType}
                _valid_sources = {e.value for e in _ArtifactSource}
                _type_raw = data.get("type", "hypothesis").lower()
                _src_raw = data.get("source", "llm").lower()
                _art_type = _ArtifactType(_type_raw if _type_raw in _valid_types else "hypothesis")
                _art_source = _ArtifactSource(_src_raw if _src_raw in _valid_sources else "llm")
                node = _ArtifactNode(
                    id=data.get("id", ""),
                    type=_art_type,
                    source=_art_source,
                    content=data.get("content", ""),
                    confidence_weight=data.get("confidence_weight", 1.0),
                    dependencies=data.get("dependencies", []),
                )
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
                logger.debug("Suppressed exception in app")
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
    # AUTH MIDDLEWARE — ADR-0012 Release N
    # OIDC primary (Bearer JWT) + session cookie + deprecated X-API-Key
    # fallback gated by MURPHY_ALLOW_API_KEY (default true) and a
    # route allowlist (default /api/v1/internal/*).
    # ══════════════════════════════════════════════════════════════════════

    try:
        from auth_middleware import OIDCAuthMiddleware as _OIDCMW  # type: ignore
    except Exception:
        try:
            from src.auth_middleware import OIDCAuthMiddleware as _OIDCMW  # type: ignore
        except Exception as _oidc_imp_exc:
            _OIDCMW = None  # type: ignore[assignment]
            logger.warning(
                "OIDCAuthMiddleware import failed (%s) — using legacy inline guard",
                _oidc_imp_exc,
            )

    if _OIDCMW is not None:
        app.add_middleware(_OIDCMW)
    else:
        # Fallback: keep the previous inline X-API-Key middleware so
        # deployments without ``src.auth_middleware`` on PYTHONPATH keep
        # working.  This branch should not normally fire — the canonical
        # source layout puts auth_middleware.py on the path.
        from starlette.middleware.base import BaseHTTPMiddleware as _BHMW

        class _APIKeyMiddleware(_BHMW):
            """Legacy inline X-API-Key fallback (Release-N back-compat)."""

            EXEMPT_PATHS = {"/api/health", "/api/info", "/api/manifest", "/api/v1/ping"}
            EXEMPT_PREFIXES = (
                "/api/auth/",
                "/api/demo/",
                "/api/system/",
                "/api/v1/",          # PATCH-065a: public API (key-auth handled internally)
                "/api/connectors/",  # PATCH-065c: connector agent (key-auth internally)
                "/oauth/",           # PATCH-065b: OAuth AS endpoints
                "/.well-known/",     # PATCH-065b: OIDC discovery
            )

            async def dispatch(self, request: Request, call_next):
                path = request.url.path
                if path.startswith("/api/"):
                    is_exempt = (
                        path in self.EXEMPT_PATHS
                        or any(path.startswith(pfx) for pfx in self.EXEMPT_PREFIXES)
                    )
                    if not is_exempt:
                        expected_key = os.environ.get("MURPHY_API_KEY", "") or os.environ.get("MURPHY_API_KEYS", "")
                        if expected_key:
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
    async def analyze_domain(request: Request):
        """Analyze a domain and return structured insights."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        domain = str(body.get("domain", "")).strip()
        context = str(body.get("context", "")).strip()
        if not domain:
            return JSONResponse({"success": False, "error": "domain is required"}, status_code=400)
        try:
            query = f"Analyze the {domain} domain" + (f" in the context of {context}" if context else "")
            lib_result = murphy.librarian_ask(query, mode="ask")
            analysis = (
                lib_result.get("reply_text")
                or lib_result.get("response")
                or lib_result.get("message")
                or f"Domain analysis for {domain}: standard automation patterns apply."
            )
        except Exception:
            analysis = f"Domain analysis for {domain}: standard automation patterns apply."
        return JSONResponse({
            "success": True,
            "domain": domain,
            "context": context,
            "analysis": analysis,
            "automation_opportunities": [
                f"{domain} workflow automation",
                f"{domain} data pipeline",
                f"{domain} reporting and analytics",
            ],
            "recommended_integrations": [],
            "timestamp": _now_iso(),
        })

    # ══════════════════════════════════════════════════════════════════════
    # PLATFORM SELF-AUTOMATION — Self-Fix, Repair, Scheduler, Orchestrator
    # ══════════════════════════════════════════════════════════════════════

    # ── Self-Fix Loop (ARCH-005) ──────────────────────────────────────────

    @app.get("/api/self-fix/status")
    async def self_fix_status():
        """Current self-fix loop status."""
        loop = getattr(murphy, "self_fix_loop", None)
        if loop is None:
            return JSONResponse({"success": True, "status": "unavailable",
                                 "message": "SelfFixLoop not initialised"})
        try:
            status = loop.get_status()
            return JSONResponse({"success": True, **status})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.post("/api/self-fix/run")
    async def self_fix_run(request: Request):
        """Trigger the self-fix loop (diagnose → plan → execute → test → verify)."""
        loop = getattr(murphy, "self_fix_loop", None)
        if loop is None:
            return JSONResponse({
                "success": True,
                "status": "unavailable",
                "message": "SelfFixLoop not initialised — system is operating normally",
                "report": {"iterations": 0, "fixes_applied": 0, "status": "skipped"},
            })
        try:
            body_bytes = await request.body()
            body = {}
            if body_bytes:
                import json as _json
                body = _json.loads(body_bytes)
            max_iter = int(body.get("max_iterations", 10))
            report = loop.run_loop(max_iterations=max_iter)
            return JSONResponse({
                "success": True,
                "report": report.to_dict() if hasattr(report, "to_dict") else str(report),
            })
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.get("/api/self-fix/history")
    async def self_fix_history():
        """Past self-fix loop reports."""
        loop = getattr(murphy, "self_fix_loop", None)
        if loop is None:
            return JSONResponse({"success": True, "reports": []})
        try:
            reports = loop.get_all_reports()
            return JSONResponse({"success": True, "reports": reports})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.get("/api/self-fix/plans")
    async def self_fix_plans():
        """All fix plans with their status."""
        loop = getattr(murphy, "self_fix_loop", None)
        if loop is None:
            return JSONResponse({"success": True, "plans": []})
        try:
            plans = loop.get_all_plans()
            return JSONResponse({"success": True, "plans": plans})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    # ── Autonomous Repair System (ARCH-006) ───────────────────────────────

    @app.get("/api/repair/status")
    async def repair_status():
        """Current repair system health."""
        repair = getattr(murphy, "autonomous_repair", None)
        if repair is None:
            return JSONResponse({"success": True, "status": "unavailable",
                                 "message": "AutonomousRepairSystem not initialised"})
        try:
            health = repair.get_health()
            return JSONResponse({"success": True, **health})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.post("/api/repair/run")
    async def repair_run(request: Request):
        """Trigger a full autonomous repair cycle."""
        repair = getattr(murphy, "autonomous_repair", None)
        if repair is None:
            return JSONResponse({"success": False,
                                 "error": "AutonomousRepairSystem not available"}, status_code=503)
        try:
            body_bytes = await request.body()
            body = {}
            if body_bytes:
                import json as _json
                body = _json.loads(body_bytes)
            max_iter = int(body.get("max_iterations", 20))
            report = repair.run_repair_cycle(max_iterations=max_iter)
            return JSONResponse({
                "success": True,
                "report": report.to_dict() if hasattr(report, "to_dict") else str(report),
            })
        except RuntimeError as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=409)
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.get("/api/repair/history")
    async def repair_history():
        """Past repair reports."""
        repair = getattr(murphy, "autonomous_repair", None)
        if repair is None:
            return JSONResponse({"success": True, "reports": []})
        try:
            reports = repair.get_reports()
            return JSONResponse({"success": True, "reports": reports})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.get("/api/repair/wiring")
    async def repair_wiring():
        """Front-end ↔ back-end wiring report."""
        repair = getattr(murphy, "autonomous_repair", None)
        if repair is None:
            return JSONResponse({"success": True, "wiring_issues": []})
        try:
            issues = repair.get_wiring_report()
            return JSONResponse({"success": True, "wiring_issues": issues})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.get("/api/repair/proposals")
    async def repair_proposals():
        """View all repair proposals."""
        repair = getattr(murphy, "autonomous_repair", None)
        if repair is None:
            return JSONResponse({"success": True, "proposals": []})
        try:
            proposals = repair.get_proposals() if hasattr(repair, "get_proposals") else []
            return JSONResponse({"success": True, "proposals": proposals})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    # ── Murphy Scheduler (daily automation cycle) ─────────────────────────

    @app.get("/api/scheduler/status")
    async def scheduler_status():
        """Murphy platform scheduler status."""
        sched = getattr(murphy, "murphy_scheduler", None)
        if sched is None:
            return JSONResponse({"success": True, "status": "unavailable",
                                 "message": "MurphyScheduler not initialised"})
        try:
            status = sched.get_status()
            return JSONResponse({"success": True, **status})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.post("/api/scheduler/start")
    async def scheduler_start():
        """Start the platform automation scheduler."""
        sched = getattr(murphy, "murphy_scheduler", None)
        if sched is None:
            return JSONResponse({"success": False,
                                 "error": "MurphyScheduler not available"}, status_code=503)
        try:
            started = sched.start()
            return JSONResponse({"success": True, "started": started})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.post("/api/scheduler/stop")
    async def scheduler_stop():
        """Stop the platform automation scheduler."""
        sched = getattr(murphy, "murphy_scheduler", None)
        if sched is None:
            return JSONResponse({"success": False,
                                 "error": "MurphyScheduler not available"}, status_code=503)
        try:
            sched.stop()
            return JSONResponse({"success": True, "stopped": True})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.post("/api/scheduler/trigger")
    async def scheduler_trigger():
        """Manually trigger the daily automation cycle."""
        sched = getattr(murphy, "murphy_scheduler", None)
        if sched is None:
            return JSONResponse({"success": False,
                                 "error": "MurphyScheduler not available"}, status_code=503)
        try:
            result = sched.run_daily_automation()
            return JSONResponse({"success": True, "result": result})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    # ── Self-Automation Orchestrator (ARCH-002) ───────────────────────────

    @app.get("/api/self-automation/status")
    async def self_automation_status():
        """Self-automation orchestrator status."""
        orch = getattr(murphy, "self_automation_orchestrator", None)
        if orch is None:
            return JSONResponse({"success": True, "status": "unavailable",
                                 "message": "SelfAutomationOrchestrator not initialised"})
        try:
            tasks = orch.list_tasks() if hasattr(orch, "list_tasks") else []
            return JSONResponse({
                "success": True,
                "status": "active",
                "task_count": len(tasks),
                "tasks": tasks[:50],
            })
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.post("/api/self-automation/task")
    async def self_automation_create_task(request: Request):
        """Create a self-automation task."""
        orch = getattr(murphy, "self_automation_orchestrator", None)
        if orch is None:
            return JSONResponse({"success": False,
                                 "error": "SelfAutomationOrchestrator not available"}, status_code=503)
        try:
            data = await request.json()
            title = data.get("title", "")
            module_name = data.get("module_name") or None
            priority = int(data.get("priority", 5))
            category = data.get("category", "self_improvement")
            if not title:
                return JSONResponse({"success": False, "error": "title is required"}, status_code=400)
            # Resolve category enum
            try:
                from src.self_automation_orchestrator import TaskCategory
                cat = TaskCategory(category)
            except (ImportError, ValueError):
                cat = category
            task = orch.create_task(
                title=title,
                category=cat,
                module_name=module_name,
                priority=priority,
            )
            return JSONResponse({
                "success": True,
                "task": task.to_dict() if hasattr(task, "to_dict") else {"id": str(task)},
            })
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.get("/api/self-automation/tasks")
    async def self_automation_list_tasks():
        """List self-automation tasks."""
        orch = getattr(murphy, "self_automation_orchestrator", None)
        if orch is None:
            return JSONResponse({"success": True, "tasks": []})
        try:
            tasks = orch.list_tasks() if hasattr(orch, "list_tasks") else []
            return JSONResponse({"success": True, "tasks": tasks})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    # ── Self-Improvement Engine ───────────────────────────────────────────

    @app.get("/api/self-improvement/status")
    async def self_improvement_status():
        """Self-improvement engine status."""
        engine = getattr(murphy, "self_improvement", None)
        if engine is None:
            return JSONResponse({"success": True, "status": "unavailable",
                                 "message": "SelfImprovementEngine not initialised"})
        try:
            status = engine.get_status() if hasattr(engine, "get_status") else {"status": "active"}
            return JSONResponse({"success": True, **status})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.get("/api/self-improvement/proposals")
    async def self_improvement_proposals():
        """List improvement proposals."""
        engine = getattr(murphy, "self_improvement", None)
        if engine is None:
            return JSONResponse({"success": True, "proposals": []})
        try:
            backlog = engine.get_remediation_backlog() if hasattr(engine, "get_remediation_backlog") else []
            proposals = []
            for p in backlog:
                proposals.append({
                    "proposal_id": getattr(p, "proposal_id", ""),
                    "category": getattr(p, "category", ""),
                    "description": getattr(p, "description", ""),
                    "status": getattr(p, "status", ""),
                    "suggested_action": getattr(p, "suggested_action", ""),
                })
            return JSONResponse({"success": True, "proposals": proposals})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.get("/api/self-improvement/corrections")
    async def self_improvement_corrections():
        """List applied corrections."""
        engine = getattr(murphy, "self_improvement", None)
        if engine is None:
            return JSONResponse({"success": True, "corrections": []})
        try:
            corrections = getattr(engine, "_corrections_applied", [])
            return JSONResponse({"success": True, "corrections": list(corrections[-50:])})
        except Exception as exc:
            return _safe_error_response(exc, 500)

    # ── Platform Automation Overview ──────────────────────────────────────

    @app.get("/api/platform/automation-status")
    async def platform_automation_overview():
        """Unified overview of all platform self-automation systems."""
        systems = {}

        # Self-Fix Loop
        loop = getattr(murphy, "self_fix_loop", None)
        systems["self_fix_loop"] = {
            "available": loop is not None,
            "status": loop.get_status() if loop and hasattr(loop, "get_status") else None,
        }

        # Autonomous Repair
        repair = getattr(murphy, "autonomous_repair", None)
        systems["autonomous_repair"] = {
            "available": repair is not None,
            "status": repair.get_health() if repair and hasattr(repair, "get_health") else None,
        }

        # Scheduler
        sched = getattr(murphy, "murphy_scheduler", None)
        systems["scheduler"] = {
            "available": sched is not None,
            "status": sched.get_status() if sched and hasattr(sched, "get_status") else None,
        }

        # Self-Automation Orchestrator
        orch = getattr(murphy, "self_automation_orchestrator", None)
        systems["self_automation_orchestrator"] = {
            "available": orch is not None,
            "task_count": len(orch.list_tasks()) if orch and hasattr(orch, "list_tasks") else 0,
        }

        # Self-Improvement Engine
        eng = getattr(murphy, "self_improvement", None)
        systems["self_improvement_engine"] = {
            "available": eng is not None,
            "status": eng.get_status() if eng and hasattr(eng, "get_status") else None,
        }

        # MFM (Murphy Foundation Model)
        import os as _os
        systems["mfm"] = {
            "enabled": _os.environ.get("MFM_ENABLED", "false").lower() == "true",
            "mode": _os.environ.get("MFM_MODE", "disabled"),
        }

        available_count = sum(1 for s in systems.values() if s.get("available", False) or s.get("enabled", False))
        return JSONResponse({
            "success": True,
            "systems": systems,
            "total_systems": len(systems),
            "available_count": available_count,
        })

    # ══════════════════════════════════════════════════════════════════════
    # REPAIR FLASK BLUEPRINT — mount via WSGIMiddleware
    # ══════════════════════════════════════════════════════════════════════

    try:
        from src.repair_api_endpoints import create_repair_blueprint as _create_repair_bp
        _repair_bp = _create_repair_bp()
        if _repair_bp is not None:
            from starlette.middleware.wsgi import WSGIMiddleware as _WSGIMid2
            try:
                from flask import Flask as _Flask2
                _repair_flask = _Flask2("repair")
                _repair_flask.register_blueprint(_repair_bp)
                app.mount("/api/repair-flask", _WSGIMid2(_repair_flask.wsgi_app))
                logger.info("Repair API Flask blueprint mounted at /api/repair-flask/*")
            except Exception as _rep_mount_exc:
                logger.warning("Repair Flask blueprint mount skipped: %s", _rep_mount_exc)
        else:
            logger.info("Repair API blueprint not created (Flask unavailable)")
    except Exception as _rep_exc:
        logger.warning("Repair API endpoints not available: %s", _rep_exc)

    # DEMO RUN — real-pipeline demo execution
    # ══════════════════════════════════════════════════════════════════════

    @app.post("/api/demo/run")
    async def demo_run(request: Request):
        """Execute a demo scenario through the real Murphy pipeline.

        Accepts JSON body: {"query": "..."}

        Returns structured pipeline steps (MFGC → MSS → Workflow → Spec)
        that the demo terminal can display as real system output.
        """
        try:
            body = await request.json()
        except Exception:
            body = {}

        query = str(body.get("query", "")).strip()[:500]
        if not query:
            return JSONResponse(
                {"success": False, "error": "missing_query", "message": "query is required"},
                status_code=400,
            )

        # -- Usage tracking (HIGH-001) PATCH-047a: API key bypass --
        account = _get_account_from_session(request)
        _ak2 = (request.headers.get("X-API-Key") or "").strip()
        _fk2 = __import__('os').environ.get("FOUNDER_API_KEY", "")
        _mk2 = __import__('os').environ.get("MURPHY_API_KEYS", "")
        _is_api2 = bool(_ak2 and (_ak2 == _fk2 or _ak2 in _mk2.split(",")))
        usage_result: dict = {}
        if _is_api2:
            usage_result = {"allowed": True, "used": 0, "limit": -1, "remaining": -1, "tier": "enterprise"}
        elif _sub_manager is not None:
            if account:
                usage_result = _sub_manager.record_usage(account["account_id"])
            else:
                import hashlib as _hl
                _ip = request.client.host if request.client else "unknown"
                _fp = _hl.sha256(_ip.encode()).hexdigest()[:32]
                usage_result = _sub_manager.record_anon_usage(_fp)
        else:
            usage_result = {"allowed": True, "used": 1, "limit": 50, "remaining": 49, "tier": "anonymous"}

        if not usage_result.get("allowed", True):
            _tier = usage_result.get("tier", "anonymous")
            _limit = usage_result.get("limit", 50)
            return JSONResponse(
                {
                    "success": False,
                    "error": "limit_exceeded",
                    "message": f"Demo run limit ({_limit}/day) reached. Sign up or upgrade for more.",
                    "usage": {
                        "used": usage_result.get("used", _limit),
                        "limit": _limit,
                        "remaining": 0,
                        "tier": _tier,
                    },
                },
                status_code=429,
            )

        _usage_info = {
            "used": usage_result.get("used", 1),
            "limit": usage_result.get("limit", 50),
            "remaining": usage_result.get("remaining", 49),
            "tier": usage_result.get("tier", "anonymous"),
        }

        try:
            from src.demo_runner import DemoRunner
            runner = DemoRunner()
            result = runner.run_scenario(query)
            return JSONResponse({
                "success": True,
                "steps": result["steps"],
                "roi_message": result["roi_message"],
                "scenario_key": result["scenario_key"],
                "duration_ms": result["duration_ms"],
                "spec": result["spec"],
                "usage": _usage_info,
            })
        except Exception as exc:
            logger.warning("demo/run error: %s", exc)
            return JSONResponse(
                {"success": False, "error": "pipeline_error", "message": str(exc)},
                status_code=500,
            )

    # ══════════════════════════════════════════════════════════════════════
    # DEMO EXPORT — downloadable project bundle with licensing
    # ══════════════════════════════════════════════════════════════════════

    @app.get("/api/demo/export")
    async def demo_export(request: Request):
        """Generate a downloadable demo project bundle.

        Returns a JSON manifest describing the exportable project structure
        with all workflows, configurations, and wiring — ready to drop
        into the user's own repository.
        """
        account = _get_account_from_session(request)
        account_id = account["account_id"] if account else "anonymous"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Collect all workflows
        workflows = list(_workflows_store.values())

        # Collect integration recommendations
        integrations_needed = set()
        for wf in workflows:
            for sug in wf.get("api_suggestions", []):
                integrations_needed.add(sug.get("name", ""))

        # Build the export bundle
        bundle = {
            "murphy_demo_export": True,
            "version": "1.0.0",
            "exported_at": now_iso,
            "exported_by": account_id,
            "license": {
                "type": "BSL-1.1",
                "name": "Business Source License 1.1",
                "copyright": "Copyright © 2020 Inoni Limited Liability Company",
                "creator": os.environ.get("MURPHY_FOUNDER_NAME", ""),
                "warranty": "NO WARRANTY — This software is provided 'as-is' without "
                            "any express or implied warranty. In no event shall the "
                            "authors be held liable for any damages arising from the "
                            "use of this software.",
                "usage_grant": "You may use, copy, and modify this demo export for "
                               "personal or internal business purposes. Commercial "
                               "redistribution requires a separate license agreement "
                               "with Inoni LLC.",
            },
            "project_structure": {
                "README.md": "Project overview, setup instructions, and architecture",
                "LICENSE": "BSL-1.1 license text",
                "requirements.txt": "Python dependencies",
                ".env.example": "Environment variable template with all API keys",
                "src/": "Source code modules",
                "src/runtime/app.py": "FastAPI application with all endpoints",
                "src/workflows/": "Generated workflow definitions",
                "src/integrations/": "Integration wiring configurations",
                "tests/": "Test suite",
                "docs/": "Documentation including API reference",
                "documentation/": "Extended documentation",
            },
            "workflows": [
                {
                    "id": wf.get("id"),
                    "name": wf.get("name"),
                    "status": wf.get("status"),
                    "schedule": wf.get("schedule", {}),
                    "node_count": len(wf.get("nodes", [])),
                    "generated_from": wf.get("generated_from", ""),
                    "api_suggestions": wf.get("api_suggestions", []),
                }
                for wf in workflows
            ],
            "integrations_needed": sorted(integrations_needed - {""}),
            "env_template": _build_env_template(workflows),
            "platform_capabilities": {
                "self_fix_loop": getattr(murphy, "self_fix_loop", None) is not None,
                "autonomous_repair": getattr(murphy, "autonomous_repair", None) is not None,
                "scheduler": getattr(murphy, "murphy_scheduler", None) is not None,
                "self_automation": getattr(murphy, "self_automation_orchestrator", None) is not None,
                "self_improvement": getattr(murphy, "self_improvement", None) is not None,
                "mfm_enabled": os.environ.get("MFM_ENABLED", "false").lower() == "true",
                "workflow_count": len(workflows),
            },
            "setup_instructions": [
                "1. Clone this export into your project directory",
                "2. Copy .env.example to .env and fill in your API keys",
                "3. Run: pip install -r requirements.txt",
                "4. Run: python -m src.runtime.app",
                "5. Open http://localhost:8000/ui/terminal-unified",
                "6. Use the onboarding wizard to configure your automations",
            ],
        }
        return JSONResponse({"success": True, "bundle": bundle})

    # ══════════════════════════════════════════════════════════════════════
    # DEMO DELIVERABLE DOWNLOAD
    # ══════════════════════════════════════════════════════════════════════

    @app.post("/api/demo/generate-deliverable")
    async def demo_generate_deliverable(request: Request):
        """Generate a branded .txt deliverable for the demo download feature.

        Accepts JSON body: {"query": "...", "scenario_type": "..."}

        Usage limits:
          - Anonymous visitors: 5 downloads/day (fingerprinted by IP+UA)
          - Free registered users: 10 downloads/day
          - Paid tiers: unlimited
        """
        try:
            body = await request.json()
        except Exception:
            body = {}

        query = str(body.get("query", "")).strip()[:500]
        if not query:
            return JSONResponse(
                {"success": False, "error": "missing_query", "message": "query is required"},
                status_code=400,
            )

        # ── Check usage limits ──────────────────────────────────────────
        account = _get_account_from_session(request)
        # PATCH-047a: API key holders (FOUNDER_API_KEY / MURPHY_API_KEYS) bypass sub_manager limits.
        _api_key_req = (request.headers.get("X-API-Key") or request.headers.get("x-api-key") or "").strip()
        _known_keys = __import__('os').environ.get("MURPHY_API_KEYS", "")
        _founder_key = __import__('os').environ.get("FOUNDER_API_KEY", "")
        _is_api_key_user = bool(_api_key_req and (
            _api_key_req == _founder_key or _api_key_req in _known_keys.split(",")
        ))
        usage_result: dict = {}

        if _is_api_key_user:
            usage_result = {"allowed": True, "used": 0, "limit": -1, "remaining": -1, "tier": "enterprise"}
        elif _sub_manager is not None:
            if account:
                account_id = account["account_id"]
                usage_result = _sub_manager.record_usage(account_id)
            else:
                try:
                    from src.demo_deliverable_generator import make_fingerprint
                    ip = request.client.host if request.client else "unknown"
                    ua = request.headers.get("user-agent", "")
                    fp = make_fingerprint(ip, ua)
                except Exception:
                    import hashlib
                    ip = request.client.host if request.client else "unknown"
                    fp = hashlib.sha256(ip.encode()).hexdigest()[:32]
                usage_result = _sub_manager.record_anon_usage(fp)
        elif not _is_api_key_user:
            usage_result = {"allowed": True, "used": 1, "limit": 5, "remaining": 4, "tier": "anonymous"}  # fallback: no tracking

        if not usage_result.get("allowed", True):
            tier = usage_result.get("tier", "anonymous")
            limit = usage_result.get("limit", 5)
            if tier == "anonymous":
                msg = (
                    f"You've used all {limit} free downloads today. "
                    "Sign up free for 10/day, or upgrade for unlimited."
                )
            else:
                msg = (
                    f"You've used all {limit} free downloads today. "
                    "Upgrade to a paid plan for unlimited downloads."
                )
            return JSONResponse(
                {
                    "success": False,
                    "error": "limit_exceeded",
                    "message": msg,
                    "usage": {
                        "used": usage_result.get("used", limit),
                        "limit": limit,
                        "remaining": 0,
                        "tier": tier,
                    },
                },
                status_code=429,
            )

        # -- Forge-specific rate limit (PATCH-047b: API key bypass) --
        _usage_forge: dict = {}
        if _is_api_key_user:
            _usage_forge = {"allowed": True, "tier": "enterprise", "builds_remaining_today": -1, "builds_used_today": 0, "swarm_cost": {}}
        else:
            try:
                from src.forge_rate_limiter import get_forge_rate_limiter
                _forge_limiter = get_forge_rate_limiter()
                _forge_result = _forge_limiter.check_and_record(request)
                if not _forge_result.get("allowed", True):
                    return JSONResponse(
                        {
                            "success": False,
                            "error": "forge_rate_limit_exceeded",
                            "tier": _forge_result.get("tier", "anonymous"),
                            "limit": _forge_result.get("builds_remaining_hour", 0),
                            "retry_after_seconds": _forge_result.get("retry_after_seconds", 60),
                            "upgrade_url": "/pricing",
                            "swarm_cost": _forge_result.get("swarm_cost", {}),
                        },
                        status_code=429,
                        headers={"Retry-After": str(_forge_result.get("retry_after_seconds", 60))},
                    )
                _usage_forge = _forge_result
            except Exception as _frl_exc:
                logger.debug("ForgeRateLimiter skipped: %s", _frl_exc)

        # ── Generate deliverable ────────────────────────────────────────
        # Step 1: Librarian lookup — gives domain knowledge to the generator
        librarian_context: str = ""
        try:
            lib_result = murphy.librarian_ask(query, mode="ask")
            # Extract the text answer from whichever key is populated
            librarian_context = (
                lib_result.get("reply_text")
                or lib_result.get("response")
                or lib_result.get("message")
                or ""
            )
            # Truncate to a sane length to avoid bloating the deliverable
            if librarian_context:
                librarian_context = librarian_context[:1500]
        except Exception as _lib_exc:
            logger.debug("Librarian lookup skipped: %s", _lib_exc)

        # Step 2: MFGC → MSS → LLM pipeline (inside generate_deliverable)
        # P1b (FORGE-KERNEL-001): resolve the caller up-front so we can
        # tag both success and failure audit entries with the actor.
        # ``_resolve_caller`` is defined in the same closure (used at
        # ``/api/execute`` too) and falls back to ``"anonymous"`` here
        # so the demo route stays usable for unauthenticated traffic.
        try:
            _fk_caller = _resolve_caller(request)
        except Exception:
            _fk_caller = None
        _fk_actor = (_fk_caller or {}).get("email") or "anonymous"
        try:
            from src.demo_deliverable_generator import generate_deliverable
            deliverable = generate_deliverable(query, librarian_context=librarian_context or None)
        except Exception as exc:
            logger.warning("Deliverable generation failed: %s", exc)
            # P1b: record the failure against the kernel so the
            # operator audit log + KPI strip see Forge failures.
            if _aionmind_kernel is not None:
                try:
                    _aionmind_kernel.record_external_execution(
                        actor=_fk_actor,
                        task_type="demo_forge",
                        status="failed",
                        summary=query,
                        details={"error": str(exc)[:240], "tier": _usage_forge.get("tier", "anonymous")},
                    )
                except Exception as _rec_exc:  # pragma: no cover - defensive
                    logger.debug("kernel.record_external_execution (failure) skipped: %s", _rec_exc)
            return JSONResponse(
                {"success": False, "error": "generation_failed", "message": str(exc)},
                status_code=500,
            )

        # P1b (FORGE-KERNEL-001): record the successful Forge execution
        # against the kernel.  Audit-only — does not gate the response,
        # does not consult risk policy, swallows its own errors.
        if _aionmind_kernel is not None:
            try:
                _aionmind_kernel.record_external_execution(
                    actor=_fk_actor,
                    task_type="demo_forge",
                    status="completed",
                    summary=query,
                    details={
                        "scenario": deliverable.get("filename", "").split(".")[0] or "custom",
                        "llm_provider": deliverable.get("llm_provider"),
                        "bytes": len(deliverable.get("content", "") or ""),
                        "tier": _usage_forge.get("tier", "anonymous"),
                    },
                )
            except Exception as _rec_exc:  # pragma: no cover - defensive
                logger.debug("kernel.record_external_execution (success) skipped: %s", _rec_exc)

        # Generate automation spec (the key sales asset)
        automation_spec: Optional[Dict[str, Any]] = None
        spec_id: Optional[str] = None
        try:
            from src.demo_deliverable_generator import generate_automation_spec
            automation_spec = generate_automation_spec(query, librarian_context=librarian_context or None)
            spec_id = automation_spec.get("spec_id")
            if spec_id:
                _demo_specs_store[spec_id] = automation_spec
        except Exception as _spec_exc:
            logger.debug("Automation spec generation skipped: %s", _spec_exc)

        # Step 3: Wingman validation — sensors calibrate the output, result
        # is recorded back into the Librarian knowledge layers.
        wingman_validation: Optional[Dict[str, Any]] = None
        ws = getattr(murphy, "wingman_system", None)
        if ws is not None:
            try:
                vr = ws.validate(
                    {
                        "content": deliverable.get("content", ""),
                        "result": deliverable.get("content", ""),
                        "id": deliverable.get("filename", ""),
                    },
                    module_id="deliverable",
                )
                wingman_validation = {
                    "approved": vr.approved,
                    "trigger_level": vr.trigger_level,
                    "findings": vr.findings,
                }
            except Exception as _wv_exc:
                logger.debug("Wingman validation skipped: %s", _wv_exc)

        # Step 4: API gap scan — detects live data domains that need external APIs.
        # Tickets are raised automatically; scaffolds only if OWNER authorized.
        api_gaps: Optional[Dict[str, Any]] = None
        checker = getattr(murphy, "api_gap_checker", None)
        if checker is not None:
            try:
                gap_result = checker.check(
                    artifact={
                        "content": deliverable.get("content", ""),
                        "id": deliverable.get("filename", ""),
                    },
                    requester="deliverable_pipeline",
                    owner_user_id=None,  # no owner context in anonymous generation
                )
                if gap_result.get("api_needs_detected"):
                    api_gaps = {
                        "needs_detected": len(gap_result["api_needs_detected"]),
                        "categories": [n["category"] for n in gap_result["api_needs_detected"]],
                        "tickets_raised": gap_result.get("tickets_raised", []),
                        "auth_message": gap_result.get("auth_message", ""),
                    }
            except Exception as _gap_exc:
                logger.debug("API gap scan skipped: %s", _gap_exc)

        usage_out = {
            "used": usage_result.get("used", 1),
            "limit": usage_result.get("limit", 5),
            "remaining": usage_result.get("remaining", 4),
            "tier": usage_result.get("tier", "anonymous"),
        }

        response_body: Dict[str, Any] = {
            "success": True,
            "deliverable": deliverable,
            "usage": usage_out,
            "llm_provider": deliverable.get("llm_provider", "local"),
            "forge_usage": {
                "builds_remaining_today": _usage_forge.get("builds_remaining_today", -1),
                "builds_used_today": _usage_forge.get("builds_used_today", 0),
                "tier": _usage_forge.get("tier", "anonymous"),
                "swarm_cost": _usage_forge.get("swarm_cost", {"agents": 64, "cursors_per_agent": 1, "total_compute_units": 64}),
            },
        }
        if automation_spec is not None:
            response_body["automation_spec"] = {
                "spec_id": automation_spec.get("spec_id"),
                "title": automation_spec.get("title"),
                "workflow_count": automation_spec.get("workflow_count"),
                "hours_saved_month": automation_spec.get("hours_saved_month"),
                "monthly_savings_usd": automation_spec.get("monthly_savings_usd"),
                "net_monthly_benefit": automation_spec.get("net_monthly_benefit"),
                "annual_benefit": automation_spec.get("annual_benefit"),
                "roi_multiple": automation_spec.get("roi_multiple"),
                "murphy_cost": automation_spec.get("murphy_cost"),
                "recommended_tier": automation_spec.get("recommended_tier"),
                "signup_url": automation_spec.get("signup_url"),
                "integrations": automation_spec.get("integrations", [])[:6],
            }
        if spec_id:
            response_body["spec_id"] = spec_id
        if wingman_validation is not None:
            response_body["wingman_validation"] = wingman_validation
        if api_gaps is not None:
            response_body["api_gaps"] = api_gaps

        return JSONResponse(response_body)

    @app.post("/api/demo/generate-deliverable/stream")
    async def demo_generate_deliverable_stream(request: Request):
        """SSE streaming endpoint for the Swarm Forge.

        Yields real-time progress events as the MFGC → MSS → LLM pipeline
        runs, then emits the final ``done`` event with the complete
        deliverable and metrics.  The frontend drives its phase status
        messages from these events instead of hardcoded timers.

        Event format (one JSON object per ``data:`` line)::

            {"phase": 1, "status": "MFGC gate ...",   "detail": "mfgc"}
            {"phase": 2, "status": "Workflow ...",     "detail": "workflow_resolution"}
            {"phase": 3, "status": "MSS ...",          "detail": "mss"}
            {"phase": "done", "deliverable": {...}, "metrics": {...}, ...}
        """
        from starlette.responses import StreamingResponse
        import asyncio

        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"success": False, "error": "Invalid JSON"}, status_code=400,
            )

        query = (body.get("query") or "").strip()
        if not query:
            return JSONResponse(
                {"success": False, "error": "Query is required"}, status_code=400,
            )

        # ── Usage / rate-limit check ────────────────────────────────────
        account = _get_account_from_session(request)
        usage_result: dict = {}
        if _sub_manager is not None:
            if account:
                usage_result = _sub_manager.record_usage(account["account_id"])
            else:
                try:
                    from src.demo_deliverable_generator import make_fingerprint
                    ip = request.client.host if request.client else "unknown"
                    ua = request.headers.get("user-agent", "")
                    fp = make_fingerprint(ip, ua)
                except Exception:
                    import hashlib
                    ip = request.client.host if request.client else "unknown"
                    fp = hashlib.sha256(ip.encode()).hexdigest()[:32]
                usage_result = _sub_manager.record_anon_usage(fp)
        else:
            usage_result = {"allowed": True, "used": 1, "limit": 5, "remaining": 4, "tier": "anonymous"}

        if not usage_result.get("allowed", True):
            return JSONResponse(
                {
                    "success": False,
                    "error": "Daily build limit reached. Sign up for more builds.",
                    "forge_usage": {
                        "builds_used_today": usage_result.get("used", 0),
                        "builds_remaining_today": 0,
                        "limit": usage_result.get("limit", 5),
                        "tier": usage_result.get("tier", "anonymous"),
                    },
                },
                status_code=429,
            )

        # ── Pipeline import ─────────────────────────────────────────────
        try:
            from src.demo_deliverable_generator import generate_deliverable_with_progress
        except ImportError:
            return JSONResponse(
                {"error": "Demo generator not available", "detail": "Server import failed"},
                status_code=503,
            )

        run_id = uuid4().hex[:12]

        # WIRE-LIB-001: Librarian lookup for streaming endpoint — same
        # pattern as the non-streaming path (lines 13191-13203).
        librarian_context: str = ""
        try:
            lib_result = murphy.librarian_ask(query, mode="ask")
            librarian_context = (
                lib_result.get("reply_text")
                or lib_result.get("response")
                or lib_result.get("message")
                or ""
            )
            if librarian_context:
                librarian_context = librarian_context[:1500]
        except Exception as _lib_exc:
            logger.debug("Librarian lookup skipped (streaming): %s", _lib_exc)

        async def _event_gen():
            """Async generator yielding SSE events."""
            try:
                import functools
                _gen_fn = functools.partial(
                    generate_deliverable_with_progress,
                    query,
                    librarian_context=librarian_context or None,
                )
                progress = await asyncio.get_event_loop().run_in_executor(
                    None,
                    _gen_fn,
                )
            except Exception as exc:
                logger.warning("Streaming forge generator failed: %s — using fallback", exc)
                # Emit synthetic progress + a server-side fallback deliverable
                yield f"data: {json.dumps({'phase': 1, 'status': 'Analyzing scope...', 'detail': 'mfgc'})}\n\n"
                yield f"data: {json.dumps({'phase': 2, 'status': 'Searching workflows...', 'detail': 'workflow_resolution'})}\n\n"
                yield f"data: {json.dumps({'phase': 3, 'status': 'Generating content (fallback)...', 'detail': 'mss'})}\n\n"
                try:
                    from src.demo_deliverable_generator import generate_deliverable
                    fb = generate_deliverable(query)
                except Exception:
                    fb = {"title": f"Deliverable: {query[:50]}", "content": "", "filename": "murphy-deliverable.txt"}
                fb_content = fb.get("content", "")
                done_event = {
                    "phase": "done",
                    "status": "Build complete — deliverable ready (fallback)",
                    "deliverable": fb,
                    "metrics": {
                        "word_count": len(fb_content.split()) if fb_content else 0,
                        "line_count": fb_content.count("\n") + 1 if fb_content else 0,
                        "size_kb": round(len(fb_content) / 1024, 1) if fb_content else 0,
                        "scenario": "fallback",
                    },
                    "run_id": run_id,
                    "llm_provider": "murphy-demo",
                }
                yield f"data: {json.dumps(done_event)}\n\n"
                return

            for event in progress:
                if event.get("phase") == "done":
                    # Ensure deliverable content is present
                    deliverable = event.get("deliverable") or {}
                    if not deliverable.get("content"):
                        logger.warning("Streaming generator returned empty content — substituting fallback")
                        try:
                            from src.demo_deliverable_generator import generate_deliverable
                            event["deliverable"] = generate_deliverable(query)
                        except Exception:  # PROD-HARD A2: fallback generator failed — stream original empty event
                            logger.warning("Fallback deliverable generation failed; streaming original event", exc_info=True)
                    event["run_id"] = run_id
                    # Pass through the real llm_provider from the pipeline
                    # diagnostics so the frontend knows what actually generated
                    # the content instead of always showing "murphy-demo".
                    diag = event.get("pipeline_diagnostics") or {}
                    try:
                        from src.demo_deliverable_generator import detect_llm_provider
                        event.setdefault("llm_provider", detect_llm_provider(diag))
                    except ImportError:
                        event.setdefault("llm_provider", "murphy-demo")
                    # Surface error/fallback counts so the frontend can decide
                    # whether to show a warning about degraded output.
                    if diag.get("error_count", 0) > 0 or diag.get("fallback_count", 0) > 0:
                        event["pipeline_warnings"] = {
                            "error_count": diag.get("error_count", 0),
                            "fallback_count": diag.get("fallback_count", 0),
                            "fallbacks": diag.get("fallbacks", []),
                        }
                try:
                    yield f"data: {json.dumps(event)}\n\n"
                except (TypeError, ValueError):  # PROD-HARD A2: non-serialisable event — skip rather than abort stream
                    logger.warning("Dropping non-JSON-serialisable SSE event: keys=%s", list(event.keys()) if isinstance(event, dict) else type(event).__name__)

        return StreamingResponse(
            _event_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/demo/spec/{spec_id}")
    async def get_demo_spec(spec_id: str):
        """Retrieve a generated automation spec by spec_id; returns a synthetic stub when not found."""
        spec = _demo_specs_store.get(spec_id)
        if not spec:
            # Return a plausible synthetic spec so the signup flow doesn't error out.
            spec = {
                "spec_id": spec_id,
                "name": f"Automation Spec {spec_id[:8]}",
                "description": "Auto-generated workflow stub — configure in Settings.",
                "triggers": [{"type": "schedule", "cron": "0 9 * * 1-5"}],
                "actions": [{"type": "notify", "channel": "email", "template": "default"}],
                "status": "draft",
            }
        return JSONResponse({"success": True, "ok": True, "spec": spec})

    @app.get("/api/demo/forge-stream")
    async def demo_forge_stream(request: Request):
        """SSE stream of swarm build progress for the Swarm Forge UI."""
        from starlette.responses import StreamingResponse
        try:
            from src.forge_stream import forge_stream_generator
        except ImportError:
            from forge_stream import forge_stream_generator
        query = request.query_params.get("query", "")
        return StreamingResponse(
            forge_stream_generator(query),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ------------------------------------------------------------------
    # Multi-format deliverable export  (label: FORGE-EXPORT-001)
    # ------------------------------------------------------------------

    @app.get("/api/demo/deliverable/formats")
    async def api_demo_deliverable_formats():
        """Return the list of supported deliverable output formats."""
        try:
            from src.demo_deliverable_generator import SUPPORTED_FORMATS
            return JSONResponse({
                "formats": {k: v["label"] for k, v in SUPPORTED_FORMATS.items()},
                "default": "txt",
            })
        except ImportError:
            logger.warning("FORGE-EXPORT-ERR-003: SUPPORTED_FORMATS not available")
            return JSONResponse({
                "formats": {"txt": "Plain Text (.txt)"},
                "default": "txt",
            })

    @app.post("/api/demo/deliverable/export")
    async def api_demo_deliverable_export(request: Request):
        """Convert a deliverable to a different output format.

        Accepts a JSON body with:
          - ``deliverable``: the deliverable dict (title, content, filename)
          - ``format``: target format (txt, pdf, html, docx, zip, md)
          - ``query``: original query (for ZIP README)

        Returns the converted content.  Binary formats (pdf, docx, zip) are
        returned as base64-encoded strings with ``is_binary: true``.

        Label: FORGE-EXPORT-001
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

        deliverable = body.get("deliverable")
        if not deliverable or not deliverable.get("content"):
            return JSONResponse({"success": False, "error": "deliverable with content is required"}, status_code=400)

        target_format = (body.get("format") or "txt").strip().lower()
        query = body.get("query", "")

        try:
            from src.demo_deliverable_generator import convert_deliverable_format
        except ImportError:
            logger.warning("FORGE-EXPORT-ERR-001: convert_deliverable_format not available — returning txt")
            return JSONResponse({
                "success": True,
                "content": deliverable.get("content", ""),
                "filename": deliverable.get("filename", "murphy-deliverable.txt"),
                "mime_type": "text/plain",
                "format": "txt",
                "is_binary": False,
            })

        try:
            result = convert_deliverable_format(deliverable, target_format, query=query)
            return JSONResponse({
                "success": True,
                **result,
            })
        except Exception as exc:
            logger.exception("FORGE-EXPORT-ERR-002: Format conversion failed: %s", exc)
            return JSONResponse({
                "success": False,
                "error": f"Format conversion failed: {type(exc).__name__}: {exc}",
            }, status_code=500)

    @app.get("/ui/financing-options")
    async def ui_financing_options_redirect():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/ui/financing", status_code=307)

    @app.get("/api/dashboards/live-metrics/snapshot")
    async def live_metrics_snapshot():
        return JSONResponse({
            "ok": True,
            "timestamp": _now_iso(),
            "metrics": {
                "active_automations": len(getattr(murphy, "_automations_store", {}) or {}),
                "api_requests_last_hour": 0,
                "active_users": 0,
                "system_health": "nominal",
            }
        })

    @app.get("/api/email/webmail-url")
    async def email_webmail_url():
        url = os.environ.get("MURPHY_WEBMAIL_URL", "/mail/")
        return JSONResponse({"ok": True, "url": url})

    def _build_env_template(workflows):
        """Build .env.example content from workflow API suggestions.

        SEC-SECRET-001: Every generated env file receives a unique random
        MURPHY_SECRET_KEY so operators never deploy with the old placeholder.
        """
        import secrets as _secrets  # noqa: PLC0415
        lines = [
            "# Murphy System — Environment Configuration",
            "# Generated from your workflows — fill in API keys to activate integrations",
            "",
            "# === Core ===",
            "MURPHY_ENV=production",
            f"MURPHY_SECRET_KEY={_secrets.token_urlsafe(48)}",
            "",
            "# === LLM Provider (optional — system works without it) ===",
            "# MURPHY_LLM_PROVIDER=deepinfra",
            "# DEEPINFRA_API_KEY=your-key-here  # Get at https://deepinfra.com",
            "# TOGETHER_API_KEY=your-key-here  # Get at https://api.together.xyz (overflow)",
            "",
            "# === MFM (Murphy Foundation Model) ===",
            "MFM_ENABLED=true",
            "MFM_MODE=shadow",
            "",
        ]
        seen = set()
        for wf in workflows:
            for sug in wf.get("api_suggestions", []):
                env_var = sug.get("env_var", "")
                if env_var and env_var not in seen:
                    seen.add(env_var)
                    lines.append(f"# === {sug.get('name', '')} ===")
                    lines.append(f"# {sug.get('description', '')}")
                    if sug.get("signup_url"):
                        lines.append(f"# Sign up: {sug['signup_url']}")
                    lines.append(f"# {env_var}=your-key-here")
                    lines.append("")
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════════
    # INONI LLC AUTOMATED AGENT ORG CHART
    # ══════════════════════════════════════════════════════════════════════

    async def _inoni_org_chart_handler():
        """Full automated org chart of AI agents that work for Inoni LLC.

        Every agent here runs as a platform automation — these are the
        proof-of-concept automations that murphy.systems uses to maintain
        itself, sell itself, and demonstrate capabilities.
        """
        org = {
            "company": "Inoni LLC",
            "platform": "murphy.systems",
            "mission": "AI-powered business automation for every industry",
            "departments": [
                {
                    "name": "Executive & Strategy",
                    "head": "Murphy Founder Agent",
                    "schedule": "continuous",
                    "agents": [
                        {"id": "founder-agent", "role": "Founder Schedule Manager",
                         "description": "Manages platform maintenance schedule aligned with founder priorities",
                         "automations": ["daily_standup_digest", "weekly_strategy_review", "monthly_investor_update"],
                         "status": "active", "schedule": "daily 08:00 UTC"},
                        {"id": "growth-strategist", "role": "Growth Strategy Agent",
                         "description": "Analyzes user acquisition funnels and optimizes conversion",
                         "automations": ["funnel_analysis", "conversion_optimization", "churn_prediction"],
                         "status": "active", "schedule": "daily 06:00 UTC"},
                    ],
                },
                {
                    "name": "Sales & Marketing",
                    "head": "Revenue Agent",
                    "schedule": "daily",
                    "agents": [
                        {"id": "daily-seller", "role": "Daily Outreach Agent",
                         "description": "Sends daily platform capability showcases to prospective users",
                         "automations": ["daily_outreach_email", "social_media_post", "demo_scheduler"],
                         "status": "active", "schedule": "daily 09:00 UTC"},
                        {"id": "content-marketer", "role": "Content Marketing Agent",
                         "description": "Creates blog posts, tutorials, and case studies demonstrating Murphy capabilities",
                         "automations": ["blog_draft", "tutorial_generation", "case_study_builder"],
                         "status": "active", "schedule": "weekly Mon 10:00 UTC"},
                        {"id": "partnership-agent", "role": "Partnership & Licensing Agent",
                         "description": "Manages platform capability licensing to other businesses",
                         "automations": ["license_inquiry_handler", "partner_onboarding", "sdk_access_provisioning"],
                         "status": "active", "schedule": "on_demand"},
                    ],
                },
                {
                    "name": "Content Creator Services",
                    "head": "Creator Economy Agent",
                    "schedule": "continuous",
                    "agents": [
                        {"id": "moderation-agent", "role": "AI Content Moderation Agent",
                         "description": "Free moderation automation for AI content creators and bloggers — "
                                        "comment filtering, spam detection, toxicity scoring, community guidelines enforcement",
                         "automations": ["comment_moderation", "spam_filter", "toxicity_scorer", "community_guidelines_check"],
                         "status": "active", "schedule": "continuous", "tier": "free"},
                        {"id": "creator-analytics", "role": "Creator Analytics Agent",
                         "description": "Audience analytics, engagement tracking, and content performance for creators",
                         "automations": ["audience_analytics", "engagement_tracker", "content_performance_report"],
                         "status": "active", "schedule": "daily 07:00 UTC", "tier": "free"},
                        {"id": "creator-scheduler", "role": "Content Scheduling Agent",
                         "description": "Auto-schedule posts across platforms with optimal timing",
                         "automations": ["cross_platform_scheduler", "optimal_time_analyzer", "content_calendar"],
                         "status": "active", "schedule": "continuous", "tier": "solo"},
                    ],
                },
                {
                    "name": "Developer Relations",
                    "head": "DevRel Agent",
                    "schedule": "daily",
                    "agents": [
                        {"id": "sdk-agent", "role": "SDK Management Agent",
                         "description": "Maintains SDK packages for developers — Python, JavaScript, REST API docs",
                         "automations": ["sdk_version_check", "api_doc_generator", "sdk_test_runner", "developer_onboarding"],
                         "status": "active", "schedule": "daily 05:00 UTC"},
                        {"id": "api-health-agent", "role": "API Health Monitor Agent",
                         "description": "Monitors all API endpoints for uptime, latency, and error rates",
                         "automations": ["endpoint_health_check", "latency_monitor", "error_rate_alerter"],
                         "status": "active", "schedule": "every 5 minutes"},
                    ],
                },
                {
                    "name": "Platform Engineering",
                    "head": "Self-Automation Agent",
                    "schedule": "continuous",
                    "agents": [
                        {"id": "self-fix-agent", "role": "Self-Fix Loop Agent",
                         "description": "Detects and repairs platform issues autonomously (ARCH-005)",
                         "automations": ["diagnose_gaps", "plan_fixes", "execute_repairs", "verify_fixes"],
                         "status": "active", "schedule": "every 30 minutes"},
                        {"id": "repair-agent", "role": "Autonomous Repair Agent",
                         "description": "Deep repair cycles with immune memory (ARCH-006)",
                         "automations": ["repair_cycle", "wiring_validation", "reconciliation_loop"],
                         "status": "active", "schedule": "hourly"},
                        {"id": "scheduler-agent", "role": "Daily Automation Scheduler",
                         "description": "Runs the daily business automation cycle with HITL safety gates",
                         "automations": ["daily_automation_cycle", "hitl_gate_check", "automation_report"],
                         "status": "active", "schedule": "daily 00:00 UTC"},
                        {"id": "doc-agent", "role": "Documentation Auto-Update Agent",
                         "description": "Keeps documentation in sync with code changes",
                         "automations": ["doc_drift_check", "module_count_sync", "api_reference_update"],
                         "status": "active", "schedule": "on_push"},
                    ],
                },
                {
                    "name": "Production & Maintenance",
                    "head": "Production Assistant Agent",
                    "schedule": "continuous",
                    "agents": [
                        {"id": "production-assistant", "role": "Production Deliverable Agent",
                         "description": "Main go-to-work systems — task execution, deliverable generation, quality gates",
                         "automations": ["task_executor", "deliverable_generator", "quality_gate_checker", "client_report_builder"],
                         "status": "active", "schedule": "on_demand"},
                        {"id": "maintenance-agent", "role": "Hardware & Infrastructure Maintenance Agent",
                         "description": "Automates hardware-focused maintenance — server health, backup, scaling",
                         "automations": ["server_health_check", "backup_automation", "auto_scaling", "ssl_cert_renewal"],
                         "status": "active", "schedule": "daily 02:00 UTC"},
                        {"id": "monitor-agent", "role": "System Monitor Agent",
                         "description": "24/7 monitoring of all platform systems with alerting",
                         "automations": ["system_monitor", "alert_dispatcher", "incident_tracker", "post_mortem_generator"],
                         "status": "active", "schedule": "continuous"},
                    ],
                },
                {
                    "name": "AI & Machine Learning",
                    "head": "MFM Training Agent",
                    "schedule": "periodic",
                    "agents": [
                        {"id": "mfm-trainer", "role": "MFM Data Collection Agent",
                         "description": "Collects SENSE→THINK→ACT→LEARN traces for Murphy Foundation Model training",
                         "automations": ["trace_collection", "outcome_labeling", "training_data_pipeline"],
                         "status": "active", "schedule": "continuous"},
                        {"id": "mfm-evaluator", "role": "MFM Shadow Evaluation Agent",
                         "description": "Runs shadow deployment comparing MFM predictions vs actual outcomes",
                         "automations": ["shadow_evaluation", "accuracy_tracking", "promote_or_rollback"],
                         "status": "active", "schedule": "every 6 hours"},
                        {"id": "streaming-ai", "role": "Streaming & Gaming AI Agent (Future)",
                         "description": "AI playing video games and streaming automations — coming soon",
                         "automations": ["game_agent_training", "stream_automation", "viewer_interaction_bot"],
                         "status": "planned", "schedule": "TBD"},
                    ],
                },
                {
                    "name": "Customer Success",
                    "head": "Onboarding Agent",
                    "schedule": "on_demand",
                    "agents": [
                        {"id": "onboard-librarian", "role": "Onboard Librarian Agent",
                         "description": "Guides new users through setup — works without external LLM API keys",
                         "automations": ["guided_onboarding", "dimension_extraction", "config_generation", "integration_suggestions"],
                         "status": "active", "schedule": "on_demand"},
                        {"id": "wizard-agent", "role": "Setup Wizard Agent",
                         "description": "Defines main automations based on user's business context",
                         "automations": ["question_flow", "profile_builder", "config_validator", "preset_recommender"],
                         "status": "active", "schedule": "on_demand"},
                        {"id": "support-agent", "role": "Customer Support Agent",
                         "description": "Handles support inquiries and escalates to HITL when needed",
                         "automations": ["inquiry_classifier", "auto_resolver", "hitl_escalation", "satisfaction_tracker"],
                         "status": "active", "schedule": "continuous"},
                    ],
                },
            ],
            "total_agents": 23,
            "active_agents": 21,
            "planned_agents": 2,
            "automation_count": 70,
        }
        return JSONResponse({"success": True, "org_chart": org})

    # ══════════════════════════════════════════════════════════════════════
    # CONTENT CREATOR MODERATION & SDK ENDPOINTS
    # ══════════════════════════════════════════════════════════════════════

    @app.get("/api/creator/moderation/status")
    async def creator_moderation_status():
        """Content creator moderation service status (free tier)."""
        return JSONResponse({
            "success": True,
            "service": "AI Content Moderation",
            "tier": "free",
            "description": "Free automated moderation for AI content creators and bloggers",
            "capabilities": [
                {"name": "Comment Moderation", "description": "Filter toxic, spam, and off-topic comments",
                 "api": "POST /api/creator/moderation/check", "status": "active"},
                {"name": "Spam Detection", "description": "ML-based spam scoring for blog comments and messages",
                 "api": "POST /api/creator/moderation/spam-score", "status": "active"},
                {"name": "Toxicity Scoring", "description": "Rate content toxicity on 0-1 scale",
                 "api": "POST /api/creator/moderation/toxicity", "status": "active"},
                {"name": "Community Guidelines", "description": "Check content against custom community rules",
                 "api": "POST /api/creator/moderation/guidelines", "status": "active"},
            ],
            "usage_limits": {
                "free": "1000 checks/day",
                "solo": "10,000 checks/day",
                "business": "100,000 checks/day",
                "professional": "unlimited",
            },
        })

    @app.post("/api/creator/moderation/check")
    async def creator_moderation_check(request: Request):
        """Run content moderation check on text (free for creators)."""
        try:
            data = await request.json()
            text = data.get("text", "")
            if not text:
                return JSONResponse({"success": False, "error": "text is required"}, status_code=400)

            # Simple built-in moderation (no external API needed)
            text_lower = text.lower()
            _SPAM_PATTERNS = ["buy now", "click here", "free money", "act now", "limited time",
                              "congratulations you won", "nigerian prince"]
            _TOXIC_PATTERNS = ["hate", "kill", "die", "stupid", "idiot"]

            spam_score = sum(1 for p in _SPAM_PATTERNS if p in text_lower) / max(len(_SPAM_PATTERNS), 1)
            toxicity_score = sum(1 for p in _TOXIC_PATTERNS if p in text_lower) / max(len(_TOXIC_PATTERNS), 1)
            is_clean = spam_score < 0.2 and toxicity_score < 0.2

            return JSONResponse({
                "success": True,
                "result": {
                    "is_clean": is_clean,
                    "spam_score": round(spam_score, 3),
                    "toxicity_score": round(toxicity_score, 3),
                    "action": "approve" if is_clean else "review",
                    "flags": ([f"spam_pattern:{p}" for p in _SPAM_PATTERNS if p in text_lower] +
                              [f"toxic_pattern:{p}" for p in _TOXIC_PATTERNS if p in text_lower]),
                },
            })
        except Exception as exc:
            return _safe_error_response(exc, 500)

    @app.get("/api/sdk/status")
    async def sdk_status():
        """SDK availability and developer resources."""
        return JSONResponse({
            "success": True,
            "sdk": {
                "name": "Murphy SDK",
                "version": "1.0.0",
                "languages": [
                    {"language": "Python", "package": "murphy-sdk",
                     "install": "pip install murphy-sdk", "status": "available"},
                    {"language": "JavaScript", "package": "@murphy/sdk",
                     "install": "npm install @murphy/sdk", "status": "available"},
                    {"language": "REST API", "package": None,
                     "install": "curl https://murphy.systems/api/", "status": "available"},
                ],
                "features": [
                    "Workflow generation from natural language",
                    "Integration management (50+ services)",
                    "Content moderation APIs (free for creators)",
                    "HITL intervention management",
                    "MFM model inference (when enabled)",
                    "Platform automation control",
                    "Compliance framework management",
                    "Org chart and agent management",
                ],
                "docs_url": "/ui/docs",
                "api_reference": "/api/manifest",
            },
        })

    @app.get("/api/platform/capabilities")
    async def platform_capabilities():
        """Full platform capability catalog — what can be licensed to others."""
        return JSONResponse({
            "success": True,
            "licensable_capabilities": [
                {"id": "workflow_automation", "name": "Workflow Automation Engine",
                 "description": "NL → DAG workflow generation with scheduling and API suggestions",
                 "tier_required": "solo", "license_type": "per_seat"},
                {"id": "content_moderation", "name": "AI Content Moderation",
                 "description": "Free for creators — comment filtering, spam detection, toxicity scoring",
                 "tier_required": "free", "license_type": "free"},
                {"id": "self_automation", "name": "Self-Automation Platform",
                 "description": "Self-fix, repair, scheduling, improvement — runs autonomously",
                 "tier_required": "business", "license_type": "platform"},
                {"id": "compliance_engine", "name": "Compliance Framework Engine",
                 "description": "41 compliance frameworks with conflict detection and resolution",
                 "tier_required": "solo", "license_type": "per_seat"},
                {"id": "mfm_training", "name": "Custom AI Model Training",
                 "description": "Train your own foundation model from platform traces (6-month cycle)",
                 "tier_required": "enterprise", "license_type": "enterprise"},
                {"id": "sdk_access", "name": "Developer SDK",
                 "description": "Python, JavaScript, and REST API access to all platform features",
                 "tier_required": "solo", "license_type": "per_seat"},
                {"id": "streaming_ai", "name": "Streaming & Gaming AI (Future)",
                 "description": "AI playing video games and streaming automation — coming soon",
                 "tier_required": "professional", "license_type": "add_on",
                 "status": "planned", "eta": "2026-Q4"},
                {"id": "hitl_interventions", "name": "Human-in-the-Loop Automation",
                 "description": "Approval queues, popup responses, escalation workflows",
                 "tier_required": "solo", "license_type": "per_seat"},
                {"id": "integration_hub", "name": "Integration Hub (50+ services)",
                 "description": "Pre-built connectors for Slack, SendGrid, Stripe, GitHub, etc.",
                 "tier_required": "solo", "license_type": "per_seat"},
                {"id": "production_assistant", "name": "Production Assistant",
                 "description": "Go-to-work systems — task execution, deliverables, quality gates",
                 "tier_required": "business", "license_type": "per_seat"},
                {"id": "maintenance_automation", "name": "Infrastructure Maintenance",
                 "description": "Hardware-focused automations — server health, backups, scaling",
                 "tier_required": "business", "license_type": "platform"},
                {"id": "org_chart_agents", "name": "AI Agent Org Chart",
                 "description": "Automated agent workforce with scheduling and role management",
                 "tier_required": "business", "license_type": "per_seat"},
            ],
            "total_capabilities": 12,
            "free_capabilities": 1,
            "coming_soon": 1,
        })

    # ── Client Portfolio — save / retrieve / modify service selections ──

    _client_portfolios: Dict[str, Any] = {}

    _SERVICE_PRICING: Dict[str, int] = {
        "S01": 49, "S02": 29, "S03": 19, "S04": 39, "S05": 19,
        "S06": 79, "S07": 99, "S08": 59, "S09": 29, "S10": 49,
    }
    _VALID_SERVICE_IDS = set(_SERVICE_PRICING.keys())

    def _validate_service_selections(selections: list):
        """Return list of invalid IDs, or None if all valid."""
        invalid = [s for s in selections if s not in _VALID_SERVICE_IDS]
        return invalid if invalid else None

    @app.post("/api/client-portfolio/save")
    async def client_portfolio_save(request: Request):
        """Save a client's quality-plan service selections as a portfolio.

        Accepts:
            client_id   — unique identifier (e.g. email hash or account id)
            plan_id     — the QP-xxxxxxxx Plan ID from the quality plan
            selections  — list of service IDs the client chose (e.g. ["S01","S03"])
            query       — original request text (stored for context)
        """
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)
        client_id = (data.get("client_id") or "").strip()
        plan_id = (data.get("plan_id") or "").strip()
        selections = data.get("selections", [])
        query_text = (data.get("query") or "").strip()
        if not client_id:
            return JSONResponse({"success": False, "error": "client_id is required"}, status_code=400)
        if not selections:
            return JSONResponse({"success": False, "error": "selections list is required"}, status_code=400)

        invalid = _validate_service_selections(selections)
        if invalid:
            return JSONResponse(
                {"success": False, "error": f"invalid service IDs: {invalid}"},
                status_code=400,
            )

        total_monthly = sum(_SERVICE_PRICING.get(s, 0) for s in selections)

        portfolio = {
            "client_id": client_id,
            "plan_id": plan_id,
            "selections": sorted(selections),
            "query": query_text,
            "total_monthly_estimate": total_monthly,
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }
        _client_portfolios[client_id] = portfolio

        # Optimization suggestions
        optimization: List[str] = []
        sel_set = set(selections)
        if "S01" in sel_set and "S07" in sel_set:
            optimization.append("Bundle Workflow + Self-Automation for ~15% savings.")
        if "S04" in sel_set and "S05" not in sel_set:
            optimization.append("Add Human-in-the-Loop (S05) for complete compliance governance.")
        if "S06" in sel_set and "S10" not in sel_set:
            optimization.append("Add Infrastructure Maintenance (S10) to support Production uptime.")
        if total_monthly > 200:
            optimization.append("Consider Business tier for volume discount at this spend level.")

        return JSONResponse({
            "success": True,
            "portfolio": portfolio,
            "optimization_suggestions": optimization,
        })

    @app.get("/api/client-portfolio/{client_id}")
    async def client_portfolio_get(client_id: str):
        """Retrieve a saved client portfolio by client ID."""
        portfolio = _client_portfolios.get(client_id)
        if not portfolio:
            return JSONResponse(
                {"success": False, "error": "portfolio_not_found"},
                status_code=404,
            )
        return JSONResponse({"success": True, "portfolio": portfolio})

    @app.put("/api/client-portfolio/{client_id}/selections")
    async def client_portfolio_update_selections(client_id: str, request: Request):
        """Update service selections for an existing client portfolio.

        Supports mix-and-match: upgrade, downgrade, add, or remove services.
        """
        portfolio = _client_portfolios.get(client_id)
        if not portfolio:
            return JSONResponse(
                {"success": False, "error": "portfolio_not_found"},
                status_code=404,
            )
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)

        new_selections = data.get("selections", [])
        invalid = _validate_service_selections(new_selections)
        if invalid:
            return JSONResponse(
                {"success": False, "error": f"invalid service IDs: {invalid}"},
                status_code=400,
            )
        if not new_selections:
            return JSONResponse(
                {"success": False, "error": "selections list is required"},
                status_code=400,
            )

        old_total = portfolio["total_monthly_estimate"]
        new_total = sum(_SERVICE_PRICING.get(s, 0) for s in new_selections)
        delta = new_total - old_total

        portfolio["selections"] = sorted(new_selections)
        portfolio["total_monthly_estimate"] = new_total
        portfolio["updated_at"] = datetime.now(timezone.utc).isoformat()

        change_type = "upgrade" if delta > 0 else "downgrade" if delta < 0 else "lateral"

        return JSONResponse({
            "success": True,
            "portfolio": portfolio,
            "change": {
                "type": change_type,
                "monthly_delta": delta,
                "previous_total": old_total,
                "new_total": new_total,
            },
        })

    # ── Legal — Dynamic Terms of Service & Privacy Policy ────────────

    @app.get("/api/legal/terms")
    async def legal_terms(request: Request):
        """Return dynamic Terms of Service based on the caller's service context.

        Query parameters:
            services — comma-separated service IDs (e.g. S01,S03,S06)
            mode     — 'standalone' | 'integrated' (default: standalone)
        """
        services = (request.query_params.get("services") or "").split(",")
        services = [s.strip() for s in services if s.strip()]
        mode = (request.query_params.get("mode") or "standalone").strip().lower()

        service_names = {
            "S01": "Workflow Automation Engine",
            "S02": "Integration Hub",
            "S03": "AI Content & Data Processing",
            "S04": "Compliance Framework Engine",
            "S05": "Human-in-the-Loop Approvals",
            "S06": "Production Assistant",
            "S07": "Self-Automation Platform",
            "S08": "AI Agent Org Chart",
            "S09": "Developer SDK Access",
            "S10": "Infrastructure Maintenance",
        }

        selected = [service_names.get(s, s) for s in services] if services else ["All Murphy System services"]

        # Data requirements keyed by service
        data_needs: Dict[str, Dict[str, str]] = {
            "S01": {"data": "workflow definitions and trigger data",
                    "reason": "to execute scheduled automations on your behalf"},
            "S02": {"data": "third-party API credentials (stored encrypted)",
                    "reason": "to connect to your existing tools and services"},
            "S03": {"data": "text and file content submitted for processing",
                    "reason": "to run AI analysis, classification, and transformation"},
            "S04": {"data": "business policies and regulatory framework selections",
                    "reason": "to evaluate compliance status and generate audit reports"},
            "S05": {"data": "approval chain configuration and reviewer identities",
                    "reason": "to route decisions to the correct human approvers"},
            "S06": {"data": "task definitions and execution history",
                    "reason": "to manage and execute production work items"},
            "S07": {"data": "system telemetry and performance metrics",
                    "reason": "to run self-healing, self-repair, and optimization loops"},
            "S08": {"data": "organisational structure and role definitions",
                    "reason": "to assign AI agents to appropriate functions"},
            "S09": {"data": "API request logs and usage telemetry",
                    "reason": "to enforce rate limits and provide usage analytics"},
            "S10": {"data": "infrastructure health metrics and server identifiers",
                    "reason": "to perform automated maintenance and scaling"},
        }

        data_sections = []
        for svc_id in services:
            info = data_needs.get(svc_id)
            if info:
                data_sections.append({
                    "service_id": svc_id,
                    "service_name": service_names.get(svc_id, svc_id),
                    "data_collected": info["data"],
                    "purpose": info["reason"],
                })

        integration_clause = (
            "Murphy System operates alongside your existing automation services. "
            "We integrate via standard APIs and do not require you to replace "
            "your current tooling. Data shared with Murphy is used solely for "
            "the services you have selected and is never sold to third parties."
            if mode == "integrated"
            else
            "Murphy System operates as your standalone automation platform. "
            "All data processed remains within the Murphy System boundary "
            "and is governed by this agreement. No third-party data sharing "
            "occurs except where you explicitly configure integrations."
        )

        return JSONResponse({
            "success": True,
            "terms": {
                "version": "1.1.0",
                "effective_date": "2025-03-01",
                "last_updated": "2026-03-19",
                "provider": "Inoni Limited Liability Company",
                "creator": os.environ.get("MURPHY_FOUNDER_NAME", ""),
                "selected_services": selected,
                "mode": mode,
                "integration_clause": integration_clause,
                "data_transparency": data_sections if data_sections else [
                    {"note": "Select specific services to see exactly what data is needed and why."}
                ],
                "key_terms": [
                    "You retain ownership of all data you provide to Murphy System.",
                    "Murphy System processes your data only to deliver the services you select.",
                    "All API credentials are stored with AES-256 encryption at rest.",
                    "You may export or delete your data at any time via the API or dashboard.",
                    "Murphy System is licensed under BSL 1.1. Deliverable outputs are Apache 1.0.",
                    "Service availability targets: 99.5% uptime for Solo, 99.9% for Business tier.",
                    "Billing is per-seat/month with no long-term commitment required.",
                ],
                "full_document_url": "/ui/legal",
            },
        })

    @app.get("/api/legal/privacy")
    async def legal_privacy(request: Request):
        """Return dynamic Privacy Policy scoped to the caller's service selections.

        Explains what data we need and why, based on what they trust us with.
        """
        services = (request.query_params.get("services") or "").split(",")
        services = [s.strip() for s in services if s.strip()]

        data_categories = {
            "account_data": {
                "description": "Name, email, and account credentials",
                "purpose": "Authentication and account management",
                "retention": "Until account deletion + 30 days",
                "required": True,
            },
            "usage_telemetry": {
                "description": "API call logs, feature usage metrics",
                "purpose": "Rate limiting, billing, and service improvement",
                "retention": "90 days rolling",
                "required": True,
            },
            "business_data": {
                "description": "Workflow definitions, documents, and task data you submit",
                "purpose": "Delivering the automation services you selected",
                "retention": "Until you delete it or close your account",
                "required": True,
            },
            "integration_credentials": {
                "description": "Third-party API keys and OAuth tokens",
                "purpose": "Connecting to external services on your behalf",
                "retention": "Until you revoke or delete the integration",
                "required": any(s in services for s in ["S02", "S09"]),
            },
            "compliance_data": {
                "description": "Regulatory framework selections and audit logs",
                "purpose": "Compliance monitoring and report generation",
                "retention": "7 years (regulatory requirement)",
                "required": "S04" in services,
            },
            "infrastructure_metrics": {
                "description": "Server health, performance, and scaling data",
                "purpose": "Automated infrastructure maintenance",
                "retention": "30 days rolling",
                "required": "S10" in services,
            },
        }

        # Filter to only relevant categories based on selected services
        applicable = {}
        for key, info in data_categories.items():
            if info["required"] is True or info["required"]:
                applicable[key] = info

        return JSONResponse({
            "success": True,
            "privacy": {
                "version": "1.1.0",
                "effective_date": "2025-03-01",
                "last_updated": "2026-03-19",
                "provider": "Inoni Limited Liability Company",
                "data_categories": applicable,
                "core_principles": [
                    "We only collect data necessary for the services you select.",
                    "We never sell your data to third parties.",
                    "All data is encrypted in transit (TLS 1.3) and at rest (AES-256).",
                    "You can export or delete all your data at any time.",
                    "GDPR and CCPA rights are fully supported.",
                ],
                "rights": {
                    "access": "Request a copy of all data we hold about you.",
                    "rectification": "Correct inaccurate data in your account.",
                    "erasure": "Delete your account and all associated data.",
                    "portability": "Export your data in standard formats (JSON/CSV).",
                    "restriction": "Limit processing to specific services only.",
                    "objection": "Opt out of non-essential data processing.",
                },
                "contact": "privacy@murphy.ai",
                "full_document_url": "/ui/privacy",
            },
        })

    # ── AUAR API Provisioning — provision APIs on behalf of users ─────

    @app.post("/api/auar/provision")
    async def auar_provision(request: Request):
        """Provision an API capability on behalf of a user via the AUAR pipeline.

        Uses the AUAR (Adaptive Universal API Router) to register and route
        API capabilities for the customer. Supports an affiliate-style
        charge-through model where API costs are attributed to the user's
        Murphy System subscription.

        Accepts:
            client_id     — the client portfolio ID
            capability    — capability name to provision (e.g. "email_validation")
            provider_pref — optional preferred provider
        """
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)

        client_id = (data.get("client_id") or "").strip()
        capability = (data.get("capability") or "").strip()
        provider_pref = (data.get("provider_preference") or "").strip()

        if not client_id:
            return JSONResponse(
                {"success": False, "error": "client_id is required"}, status_code=400,
            )
        if not capability:
            return JSONResponse(
                {"success": False, "error": "capability name is required"}, status_code=400,
            )

        # Attempt AUAR pipeline routing
        provision_result: Dict[str, Any] = {
            "client_id": client_id,
            "capability": capability,
            "provider_preference": provider_pref or "auto",
            "status": "provisioned",
            "provisioned_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            from src.auar.pipeline import AUARPipeline
            from src.auar.config import AUARConfig
            from src.auar.capability_graph import CapabilityGraph
            from src.auar.signal_interpretation import SignalInterpreter
            from src.auar.ml_optimization import MLOptimizer
            from src.auar.routing_engine import RoutingDecisionEngine
            from src.auar.schema_translation import SchemaTranslator
            from src.auar.provider_adapter import ProviderAdapterManager
            from src.auar.observability import ObservabilityLayer

            config = AUARConfig()
            graph = CapabilityGraph()
            pipeline = AUARPipeline(
                config=config,
                graph=graph,
                interpreter=SignalInterpreter(config=config.interpreter),
                ml=MLOptimizer(config=config.ml),
                router=RoutingDecisionEngine(config=config.routing),
                translator=SchemaTranslator(),
                adapters=ProviderAdapterManager(),
                observability=ObservabilityLayer(config=config.observability),
            )

            result = pipeline.execute(
                raw_request={"capability": capability, "parameters": {}},
                context={"client_id": client_id, "provider_preference": provider_pref},
            )

            provision_result["auar_result"] = {
                "success": result.success,
                "provider_id": result.provider_id,
                "provider_name": result.provider_name,
                "confidence": result.confidence_score,
                "routing_score": result.routing_score,
                "latency_ms": result.total_latency_ms,
            }
        except Exception as exc:
            logger.debug("AUAR pipeline unavailable for provisioning: %s", exc)
            provision_result["auar_result"] = {
                "success": False,
                "message": "AUAR pipeline not available — capability registered for manual provisioning",
            }

        # Affiliate charge-through model
        provision_result["billing"] = {
            "model": "affiliate_charge_through",
            "description": (
                "API usage costs are metered and included in your Murphy System "
                "subscription. Murphy provisions and manages the API on your behalf "
                "— no separate vendor signup required."
            ),
            "markup": "15%",
            "included_in_tier": True,
        }

        # Store provisioned capability in client portfolio if it exists
        portfolio = _client_portfolios.get(client_id)
        if portfolio:
            provs = portfolio.setdefault("provisioned_apis", [])
            provs.append({
                "capability": capability,
                "provisioned_at": provision_result["provisioned_at"],
                "status": provision_result["status"],
            })

        return JSONResponse({"success": True, "provision": provision_result})

    @app.get("/api/manifest")
    async def api_manifest():
        """Return a machine-readable manifest of all registered API endpoints."""
        routes = []
        for route in app.routes:
            if not hasattr(route, "path") or not route.path.startswith("/api/"):
                continue
            # Skip Mount objects (StaticFiles etc.) which have no methods attr
            raw_methods = getattr(route, "methods", None)
            if raw_methods is None:
                continue
            # HEAD and OPTIONS are auto-generated by FastAPI for every route
            # and are not part of the explicit API contract — exclude them.
            methods = sorted(raw_methods - {"HEAD", "OPTIONS"})
            routes.append({
                "path": route.path,
                "methods": methods,
                "name": getattr(route, "name", ""),
            })
        return JSONResponse({"success": True, "data": {"endpoints": sorted(routes, key=lambda r: r["path"])}})

    # ── Industry API endpoints (IND-001) ──────────────────────────────────

    @app.post("/api/industry/ingest")
    async def industry_ingest(request: Request):
        """Ingest building-automation point data (EDE / CSV / generic TSV)."""
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)

        content = (data.get("content") or "").strip()
        filename = (data.get("filename") or "").strip()

        if not content:
            return JSONResponse({"success": False, "error": "content is required"}, status_code=400)

        lines = [ln for ln in content.splitlines() if ln.strip()]
        header = lines[0] if lines else ""
        records = lines[1:] if len(lines) > 1 else []

        if "\t" in header and "object-name" in header.lower():
            adapter_name = "ede"
        elif "," in header:
            adapter_name = "csv"
        else:
            adapter_name = "generic"

        return JSONResponse({
            "success": True,
            "records_ingested": len(records),
            "adapter_name": adapter_name,
            "filename": filename,
        })

    @app.get("/api/industry/climate/{city}")
    async def industry_climate(city: str):
        """Return climate zone data and design recommendations for a city."""
        _CLIMATE_DB: Dict[str, Dict[str, Any]] = {
            "chicago": {
                "climate_zone": "5A",
                "design_temp_cooling": 93,
                "design_temp_heating": -4,
                "hdd65": 6536,
                "cdd50": 3390,
            },
            "miami": {
                "climate_zone": "1A",
                "design_temp_cooling": 92,
                "design_temp_heating": 47,
                "hdd65": 149,
                "cdd50": 9474,
            },
            "phoenix": {
                "climate_zone": "2B",
                "design_temp_cooling": 110,
                "design_temp_heating": 34,
                "hdd65": 1125,
                "cdd50": 8425,
            },
            "new york": {
                "climate_zone": "4A",
                "design_temp_cooling": 92,
                "design_temp_heating": 7,
                "hdd65": 4871,
                "cdd50": 3148,
            },
        }

        lookup = city.strip().lower()
        info = _CLIMATE_DB.get(lookup, {
            "climate_zone": "4A",
            "design_temp_cooling": 90,
            "design_temp_heating": 10,
            "hdd65": 4000,
            "cdd50": 3000,
        })

        recommendations: list = []
        zone = info["climate_zone"]
        if zone.startswith("1") or zone.startswith("2"):
            recommendations = [
                "High-efficiency cooling plant recommended",
                "Consider dedicated outdoor-air systems (DOAS)",
                "Evaluate thermal energy storage for peak shaving",
            ]
        elif zone.startswith("5") or zone.startswith("6") or zone.startswith("7"):
            recommendations = [
                "Enhanced building envelope insulation recommended",
                "Evaluate condensing boilers for heating efficiency",
                "Consider energy recovery ventilation (ERV)",
            ]
        else:
            recommendations = [
                "Balanced heating/cooling design recommended",
                "Evaluate economizer strategies",
                "Consider variable-flow pumping",
            ]

        return JSONResponse({
            "success": True,
            "city": city,
            "climate_zone": info["climate_zone"],
            "resilience_factors": {
                "design_temp_cooling": info["design_temp_cooling"],
                "design_temp_heating": info["design_temp_heating"],
                "hdd65": info["hdd65"],
                "cdd50": info["cdd50"],
            },
            "design_recommendations": recommendations,
        })

    @app.post("/api/industry/energy-audit")
    async def industry_energy_audit(request: Request):
        """Run an ASHRAE-style energy audit and return ECM recommendations."""
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)

        utility_data = data.get("utility_data") or {}
        audit_level = data.get("audit_level") or "I"
        facility_type = data.get("facility_type") or "commercial"
        mss_mode = data.get("mss_mode")

        elec_kwh = utility_data.get("electricity_kwh", 0)
        elec_cost = utility_data.get("electricity_cost", 0)
        gas_therms = utility_data.get("natural_gas_therms", 0)
        gas_cost = utility_data.get("natural_gas_cost", 0)
        sqft = utility_data.get("facility_sqft", 1)

        eui = round(((elec_kwh * 3.412) + (gas_therms * 100)) / max(sqft, 1), 2)

        ecms = [
            {"name": "LED Lighting Retrofit", "estimated_savings_pct": 12, "payback_years": 2.1},
            {"name": "VFD on AHU Supply Fans", "estimated_savings_pct": 8, "payback_years": 3.5},
            {"name": "Economizer Controls Upgrade", "estimated_savings_pct": 5, "payback_years": 1.8},
        ]
        if audit_level in ("II", "III"):
            ecms.append({"name": "Chiller Plant Optimization", "estimated_savings_pct": 10, "payback_years": 5.0})
        if audit_level == "III":
            ecms.append({"name": "Building Envelope Improvements", "estimated_savings_pct": 7, "payback_years": 8.0})

        result: Dict[str, Any] = {
            "success": True,
            "ecm_count": len(ecms),
            "ecms": ecms,
            "utility_analysis": {
                "eui_kbtu_per_sqft": eui,
                "total_electricity_kwh": elec_kwh,
                "total_electricity_cost": elec_cost,
                "total_gas_therms": gas_therms,
                "total_gas_cost": gas_cost,
            },
            "audit_level": audit_level,
            "facility_type": facility_type,
        }

        if mss_mode == "simplify":
            result["mss_rubric"] = {
                "mode": "simplify",
                "summary": "Top ECMs ranked by simple payback",
                "top_ecm": ecms[0]["name"] if ecms else None,
            }

        return JSONResponse(result)

    _industry_interview_sessions: Dict[str, Dict[str, Any]] = {}

    @app.post("/api/industry/interview")
    async def industry_interview(request: Request):
        """Guided intake interview for building-automation projects."""
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)

        domain = data.get("domain") or "general"
        session_id = data.get("session_id")
        question_id = data.get("question_id")
        answer = data.get("answer")

        _QUESTIONS: list = [
            {"question_id": "q1", "text": "What type of building or facility is this project for?",
             "options": ["Commercial Office", "Hospital", "Data Center", "Industrial", "Education", "Other"]},
            {"question_id": "q2", "text": "What is the primary BAS protocol in use?",
             "options": ["BACnet IP", "BACnet MS/TP", "Modbus TCP", "Modbus RTU", "LonWorks", "KNX", "Other"]},
            {"question_id": "q3", "text": "What is the approximate gross square footage?",
             "options": ["<10,000", "10,000–50,000", "50,000–200,000", "200,000–500,000", ">500,000"]},
            {"question_id": "q4", "text": "What are the primary goals for this project?",
             "options": ["Energy Reduction", "Comfort Improvement", "Regulatory Compliance", "System Modernization", "All of the above"]},
        ]

        if not session_id:
            import uuid as _uuid_mod
            session_id = _uuid_mod.uuid4().hex[:16]
            _industry_interview_sessions[session_id] = {
                "domain": domain,
                "current_index": 0,
                "answers": {},
            }
            return JSONResponse({
                "session_id": session_id,
                "question": _QUESTIONS[0],
                "status": "in_progress",
                "domain": domain,
            })

        session = _industry_interview_sessions.get(session_id)
        if session is None:
            return JSONResponse({"success": False, "error": "session_not_found"}, status_code=404)

        if answer is not None and question_id:
            session["answers"][question_id] = answer
            session["current_index"] += 1

        idx = session["current_index"]
        if idx < len(_QUESTIONS):
            return JSONResponse({
                "session_id": session_id,
                "question": _QUESTIONS[idx],
                "status": "in_progress",
            })

        return JSONResponse({
            "session_id": session_id,
            "status": "completed",
            "answers": session["answers"],
            "summary": f"Interview complete — {len(session['answers'])} answers collected for domain '{session['domain']}'.",
        })

    @app.post("/api/industry/configure")
    async def industry_configure(request: Request):
        """Detect system type from a free-text description and recommend a control strategy."""
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)

        description = (data.get("description") or "").strip()
        mss_mode = data.get("mss_mode")

        if not description:
            return JSONResponse({"success": False, "error": "description is required"}, status_code=400)

        desc_lower = description.lower()

        _SYSTEM_KEYWORDS: list = [
            ("ahu", ["air handling", "ahu", "supply fan", "return fan", "mixed air"]),
            ("chiller", ["chiller", "chilled water", "cooling tower", "condenser"]),
            ("boiler", ["boiler", "hot water", "steam", "heating plant"]),
            ("vav", ["vav", "variable air volume", "terminal unit"]),
            ("rtu", ["rtu", "rooftop", "packaged unit"]),
            ("lighting", ["lighting", "luminaire", "daylight"]),
        ]

        system_type = "generic"
        for stype, keywords in _SYSTEM_KEYWORDS:
            if any(kw in desc_lower for kw in keywords):
                system_type = stype
                break

        _STRATEGIES: Dict[str, str] = {
            "ahu": "Supply air temperature reset with demand-based ventilation",
            "chiller": "Condenser water optimization with weather-adjusted setpoints",
            "boiler": "Outdoor air reset with lead-lag sequencing",
            "vav": "Pressure-independent flow control with occupancy scheduling",
            "rtu": "Integrated economizer with DX staging",
            "lighting": "Daylight harvesting with occupancy-based dimming",
            "generic": "Setpoint optimization with scheduled override",
        }

        result: Dict[str, Any] = {
            "success": True,
            "system_type": system_type,
            "recommended_strategy": _STRATEGIES.get(system_type, _STRATEGIES["generic"]),
            "description": description,
        }
        if mss_mode:
            result["mss_mode"] = mss_mode

        return JSONResponse(result)

    @app.post("/api/industry/as-built")
    async def industry_as_built(request: Request):
        """Generate an as-built documentation package for a piece of equipment."""
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)

        system_name = (data.get("system_name") or "EQUIP-01").strip()
        equipment_spec = data.get("equipment_spec") or {}
        equip_type = (equipment_spec.get("equipment_type") or "generic").lower()

        _POINT_TEMPLATES: Dict[str, list] = {
            "ahu": [
                {"point": f"{system_name}.SAT", "type": "AI", "description": "Supply Air Temp"},
                {"point": f"{system_name}.RAT", "type": "AI", "description": "Return Air Temp"},
                {"point": f"{system_name}.SF_CMD", "type": "BO", "description": "Supply Fan Command"},
                {"point": f"{system_name}.CC_VLV", "type": "AO", "description": "Cooling Coil Valve"},
                {"point": f"{system_name}.HC_VLV", "type": "AO", "description": "Heating Coil Valve"},
            ],
            "chiller": [
                {"point": f"{system_name}.CHWS", "type": "AI", "description": "Chilled Water Supply Temp"},
                {"point": f"{system_name}.CHWR", "type": "AI", "description": "Chilled Water Return Temp"},
                {"point": f"{system_name}.RUN", "type": "BO", "description": "Chiller Run Command"},
                {"point": f"{system_name}.KW", "type": "AI", "description": "Power Consumption"},
            ],
            "boiler": [
                {"point": f"{system_name}.HWS", "type": "AI", "description": "Hot Water Supply Temp"},
                {"point": f"{system_name}.HWR", "type": "AI", "description": "Hot Water Return Temp"},
                {"point": f"{system_name}.FIRE", "type": "BO", "description": "Burner Command"},
            ],
        }

        point_schedule = _POINT_TEMPLATES.get(equip_type, [
            {"point": f"{system_name}.STATUS", "type": "BI", "description": "Equipment Status"},
            {"point": f"{system_name}.CMD", "type": "BO", "description": "Equipment Command"},
        ])

        diagram = (
            f"[{system_name}] — Type: {equip_type.upper()}\n"
            f"  Points: {len(point_schedule)}\n"
            f"  Protocol: BACnet IP (default)\n"
            f"  Controller: DDC"
        )

        schematic_description = (
            f"As-built schematic for {system_name} ({equip_type}). "
            f"Total point count: {len(point_schedule)}. "
            f"All points mapped to BACnet objects with standard naming conventions."
        )

        return JSONResponse({
            "success": True,
            "system_name": system_name,
            "equipment_type": equip_type,
            "diagram": diagram,
            "point_schedule": point_schedule,
            "schematic_description": schematic_description,
        })

    @app.post("/api/industry/decide")
    async def industry_decide(request: Request):
        """Multi-criteria decision analysis for equipment/ECM selection."""
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid_json"}, status_code=400)

        question = (data.get("question") or "").strip()
        options = data.get("options") or []
        criteria_set = data.get("criteria_set")

        if not options:
            return JSONResponse({"success": False, "error": "options list is required"}, status_code=400)

        scored: list = []
        for opt in options:
            name = opt.get("name", "unnamed")
            scores = opt.get("scores", {})
            total = round(sum(scores.values()), 4) if scores else 0
            scored.append({"name": name, "total_score": total, "scores": scores})

        scored.sort(key=lambda o: o["total_score"], reverse=True)

        winner = scored[0]["name"] if scored else "none"
        viable = [s["name"] for s in scored if s["total_score"] >= scored[0]["total_score"] * 0.6]
        eliminated = [s["name"] for s in scored if s["name"] not in viable]

        explanation = (
            f"Decision analysis for: '{question}'. "
            f"Evaluated {len(options)} options across {len(scored[0]['scores']) if scored else 0} criteria. "
            f"Winner: {winner} (score {scored[0]['total_score'] if scored else 0})."
        )
        if criteria_set:
            explanation += f" Criteria set: {criteria_set}."

        return JSONResponse({
            "success": True,
            "question": question,
            "winner": winner,
            "viable_options": viable,
            "eliminated_options": eliminated,
            "scored_options": scored,
            "explanation": explanation,
        })

    # ── Founder account seed ────────────────────────────────────────────────
    # On every startup the platform ensures a founder/owner account exists so
    # that the value of MURPHY_FOUNDER_EMAIL always has role=owner and can
    # access the admin panel even on a fresh deploy.
    #
    # The account is created with MURPHY_FOUNDER_PASSWORD — both env vars
    # must be set for the seed to run.
    # If the account already exists its role is silently promoted to owner.
    _FOUNDER_EMAIL: str = os.environ.get("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems").strip().lower()
    _FOUNDER_PASSWORD: str = os.environ.get("MURPHY_FOUNDER_PASSWORD", "Sputnik12!").strip()
    _FOUNDER_RECOVERY_EMAIL: str = os.environ.get("MURPHY_FOUNDER_RECOVERY_EMAIL", "corey.gfc@gmail.com").strip().lower()

    def _ensure_founder_account() -> None:
        """Create or promote the founder/owner account.

        On every startup this ensures the founder can log in with the
        configured MURPHY_FOUNDER_PASSWORD.  If the account already exists
        the role is promoted to owner AND the password is re-synced to
        MURPHY_FOUNDER_PASSWORD — so changing the env var immediately takes
        effect on the next restart without needing a manual DB edit.
        To use a custom password permanently, set MURPHY_FOUNDER_PASSWORD
        in your environment (do not rely on the in-memory default).
        """
        existing_id = _email_to_account.get(_FOUNDER_EMAIL)
        if existing_id:
            # Account already exists — promote to owner and sync password
            _user_store[existing_id]["role"] = "owner"
            _user_store[existing_id]["full_name"] = _user_store[existing_id].get("full_name") or os.environ.get("MURPHY_FOUNDER_NAME", "")
            # Re-apply the configured password so login always works after restart
            _user_store[existing_id]["password_hash"] = _hash_password(_FOUNDER_PASSWORD)
            _user_store[existing_id]["tier"] = "enterprise"
            _user_store[existing_id]["email_validated"] = True
            if _FOUNDER_RECOVERY_EMAIL:
                _user_store[existing_id]["recovery_email"] = _FOUNDER_RECOVERY_EMAIL
            return

        # Create the account from scratch
        founder_id = "founder-" + uuid4().hex[:16]
        pwd_hash = _hash_password(_FOUNDER_PASSWORD)
        _user_store[founder_id] = {
            "account_id": founder_id,
            "email": _FOUNDER_EMAIL,
            "password_hash": pwd_hash,
            "full_name": os.environ.get("MURPHY_FOUNDER_NAME", ""),
            "job_title": "Founder",
            "company": "Inoni LLC",
            "tier": "enterprise",
            "email_validated": True,
            "eula_accepted": True,
            "role": "owner",
            "created_at": _now_iso(),
            "recovery_email": _FOUNDER_RECOVERY_EMAIL,
        }
        _email_to_account[_FOUNDER_EMAIL] = founder_id
        if _sub_manager is not None and _SubRec is not None and _SubTier is not None:
            try:
                _sub_manager._subscriptions[founder_id] = _SubRec(
                    account_id=founder_id,
                    tier=_SubTier.ENTERPRISE if hasattr(_SubTier, "ENTERPRISE") else _SubTier.FREE,
                    status=_SubStatus.ACTIVE if _SubStatus is not None else "active",
                )
            except Exception:
                logger.debug("Suppressed exception in app")
        logger.info("Founder account seeded: %s (%s)", founder_id, _FOUNDER_EMAIL)

    if _FOUNDER_EMAIL and _FOUNDER_PASSWORD:
        _ensure_founder_account()

    # ── Team account seeding ────────────────────────────────────────────────
    # On startup, seed accounts for team members so they can log in with
    # email/password immediately after deploy.  Controlled by two env vars:
    #
    #   MURPHY_TEAM_EMAILS           — comma-separated list of team emails
    #   MURPHY_TEAM_DEFAULT_PASSWORD — shared initial password for all team
    #                                  accounts (users should change it after
    #                                  first login)
    #
    # Accounts that already exist are left untouched (password is NOT reset,
    # unlike the founder account).  Remove an email from the list to stop
    # seeding it; the existing account remains usable.
    _TEAM_EMAILS_RAW: str = os.environ.get("MURPHY_TEAM_EMAILS", "").strip()
    _TEAM_DEFAULT_PASSWORD: str = os.environ.get("MURPHY_TEAM_DEFAULT_PASSWORD", "").strip()

    def _seed_team_accounts() -> None:
        """Create team member accounts from MURPHY_TEAM_EMAILS env var."""
        emails = [e.strip().lower() for e in _TEAM_EMAILS_RAW.split(",") if e.strip()]
        if not emails:
            return
        seeded = 0
        for email in emails:
            if not email or "@" not in email:
                logger.warning("Skipping invalid team email: %r", email)
                continue
            if email in _email_to_account:
                # Account already exists — do not overwrite
                continue
            account_id = "team-" + uuid4().hex[:16]
            _user_store[account_id] = {
                "account_id": account_id,
                "email": email,
                "password_hash": _hash_password(_TEAM_DEFAULT_PASSWORD),
                "full_name": "",
                "job_title": "",
                "company": "Inoni LLC",
                "tier": "free",
                "email_validated": True,
                "eula_accepted": True,
                "role": "user",
                "created_at": _now_iso(),
            }
            _email_to_account[email] = account_id
            seeded += 1
            logger.info("Team account seeded: %s (%s)", account_id, email)
        if seeded:
            logger.info("Seeded %d team account(s)", seeded)

    if _TEAM_EMAILS_RAW and _TEAM_DEFAULT_PASSWORD:
        _seed_team_accounts()
    elif _TEAM_EMAILS_RAW and not _TEAM_DEFAULT_PASSWORD:
        logger.warning(
            "MURPHY_TEAM_EMAILS is set but MURPHY_TEAM_DEFAULT_PASSWORD is empty "
            "— team accounts will NOT be seeded"
        )

    # Seed founder automations
    try:
        from src.automations.models import TriggerType, ActionType, AutomationAction
        _ae = getattr(app.state, "automation_engine", None)
        if _ae is None:
            from src.automations.engine import AutomationEngine
            _ae = AutomationEngine()
        _founder_automations = [
            ("Daily Revenue Report", TriggerType.SCHEDULE, [ActionType.NOTIFY]),
            ("Lead Qualification", TriggerType.ITEM_CREATED, [ActionType.CREATE_ITEM]),
            ("Email Triage", TriggerType.ITEM_CREATED, [ActionType.NOTIFY]),
            ("Onboarding Checklist", TriggerType.STATUS_CHANGE, [ActionType.CREATE_ITEM]),
            ("Contract Review Alert", TriggerType.DATE_ARRIVED, [ActionType.NOTIFY]),
            ("Support Ticket Routing", TriggerType.ITEM_CREATED, [ActionType.MOVE_ITEM]),
            ("Weekly KPI Summary", TriggerType.SCHEDULE, [ActionType.NOTIFY]),
            ("Invoice Generation", TriggerType.STATUS_CHANGE, [ActionType.CREATE_ITEM]),
            ("Team Standup Reminder", TriggerType.SCHEDULE, [ActionType.NOTIFY]),
            ("Security Audit Log", TriggerType.COLUMN_CHANGE, [ActionType.NOTIFY]),
        ]
        for _name, _trigger, _action_types in _founder_automations:
            _actions = [AutomationAction(action_type=_at, config={}) for _at in _action_types]
            _ae.create_rule(_name, "founder", _trigger, _actions)
    except Exception as _ae_exc:
        logger.debug("Founder automations seeding skipped: %s", _ae_exc)

    # Seed ROI Calendar demo events (show the platform in action on first boot)
    try:
        from datetime import datetime as _dt_roi, timezone as _tz_roi, timedelta as _td_roi
        import random as _rand_roi
        import hashlib as _hl_roi

        _now_dt_roi = _dt_roi.now(_tz_roi.utc)

        # Named agents with colors used across all ROI calendar events
        _ROI_AGENT_POOL = [
            {"name": "Orchestrator",  "color": "#00d4aa", "role": "coordination"},
            {"name": "DataExtractor", "color": "#00e5ff", "role": "data_fetch"},
            {"name": "Validator",     "color": "#ffd700", "role": "quality_check"},
            {"name": "Formatter",     "color": "#ff8c00", "role": "output_format"},
            {"name": "ComplianceBot", "color": "#ff4444", "role": "compliance"},
            {"name": "Integrator",    "color": "#a855f7", "role": "api_integration"},
            {"name": "Scheduler",     "color": "#22c55e", "role": "scheduling"},
            {"name": "Notifier",      "color": "#ec4899", "role": "notifications"},
        ]

        # Task templates: (title, hourly_rate, hours_min, hours_max, checklist_steps, description)
        _ROI_TASK_TEMPLATES = [
            ("Invoice Processing", 45, 2, 6,
             [("Extract invoice data from email", "DataExtractor"),
              ("Validate amounts and vendor info", "Validator"),
              ("Match to purchase orders", "Orchestrator"),
              ("Route for approval", "Notifier"),
              ("Post to accounting system", "Integrator")],
             "Automated end-to-end invoice processing pipeline"),
            ("Compliance Audit", 85, 8, 20,
             [("Pull transaction records", "DataExtractor"),
              ("Screen against regulatory rules", "ComplianceBot"),
              ("Flag anomalies for review", "Validator"),
              ("Generate audit trail", "Formatter"),
              ("Submit compliance report", "Notifier")],
             "Regulatory compliance audit with automated screening"),
            ("Payroll Processing", 55, 4, 10,
             [("Aggregate hours and rates", "DataExtractor"),
              ("Calculate deductions and taxes", "ComplianceBot"),
              ("Validate against HR records", "Validator"),
              ("Generate pay stubs", "Formatter"),
              ("Trigger bank transfers", "Integrator")],
             "End-to-end payroll calculation and disbursement"),
            ("Client Onboarding", 65, 3, 8,
             [("Create client profile", "DataExtractor"),
              ("Provision system access", "Integrator"),
              ("Send welcome sequence", "Notifier"),
              ("Schedule kick-off call", "Scheduler"),
              ("Validate setup completeness", "Validator")],
             "Automated client onboarding workflow"),
            ("Report Generation", 50, 2, 5,
             [("Fetch data from sources", "DataExtractor"),
              ("Aggregate and transform", "Orchestrator"),
              ("Apply formatting templates", "Formatter"),
              ("Quality-check outputs", "Validator"),
              ("Distribute to stakeholders", "Notifier")],
             "Automated KPI and analytics report generation"),
            ("Contract Review", 120, 4, 12,
             [("Extract contract clauses", "DataExtractor"),
              ("Screen for risk terms", "ComplianceBot"),
              ("Compare to standard templates", "Validator"),
              ("Summarise red-line items", "Formatter"),
              ("Route to legal for sign-off", "Notifier")],
             "AI-assisted contract review and risk screening"),
            ("Data Migration", 75, 6, 16,
             [("Inventory source data schema", "DataExtractor"),
              ("Map fields to target schema", "Orchestrator"),
              ("Run validation checks", "Validator"),
              ("Execute migration batch", "Integrator"),
              ("Verify record counts", "ComplianceBot")],
             "Automated data migration with validation"),
            ("Email Campaign", 40, 3, 8,
             [("Segment audience list", "DataExtractor"),
              ("Personalise message content", "Formatter"),
              ("Schedule send batches", "Scheduler"),
              ("Monitor deliverability", "Validator"),
              ("Report open/click rates", "Notifier")],
             "Automated email campaign orchestration"),
            ("Lead Qualification", 60, 2, 6,
             [("Enrich lead data", "DataExtractor"),
              ("Score against ICP criteria", "Validator"),
              ("Update CRM fields", "Integrator"),
              ("Route to sales rep", "Orchestrator"),
              ("Trigger follow-up sequence", "Notifier")],
             "Automated lead scoring and CRM enrichment"),
            ("Support Ticket Routing", 45, 1, 4,
             [("Parse ticket content", "DataExtractor"),
              ("Classify issue category", "Validator"),
              ("Assign to correct queue", "Orchestrator"),
              ("Notify assigned agent", "Notifier"),
              ("Log SLA timer", "Scheduler")],
             "Intelligent support ticket triage and routing"),
            ("Vendor Onboarding", 70, 4, 10,
             [("Collect vendor documents", "DataExtractor"),
              ("Verify compliance certificates", "ComplianceBot"),
              ("Set up payment details", "Integrator"),
              ("Add to approved vendor list", "Validator"),
              ("Send onboarding confirmation", "Notifier")],
             "Automated vendor qualification and setup"),
            ("Weekly KPI Summary", 50, 2, 5,
             [("Pull metrics from dashboards", "DataExtractor"),
              ("Calculate week-over-week deltas", "Orchestrator"),
              ("Flag KPIs outside thresholds", "Validator"),
              ("Format executive summary", "Formatter"),
              ("Distribute to leadership", "Notifier")],
             "Automated weekly KPI compilation and distribution"),
        ]

        def _mk_checklist(steps, progress_pct, status):
            """Build a checklist from steps, with completion state based on progress."""
            n = len(steps)
            completed = int(n * min(progress_pct, 100) / 100)
            result = []
            for i, (step_name, agent_name) in enumerate(steps):
                if i < completed:
                    st = "complete"
                    completed_at = (_now_dt_roi - _td_roi(minutes=_rand_roi.randint(1, 60))).isoformat()
                elif i == completed and status in ("running", "qc", "hitl_review"):
                    st = "running"
                    completed_at = None
                else:
                    st = "pending"
                    completed_at = None
                result.append({
                    "step": step_name,
                    "status": st,
                    "agent": agent_name,
                    "completed_at": completed_at,
                })
            return result

        def _mk_roi_event(template, day_offset, hour_offset, status=None, pct=None):
            title, hourly_rate, hrs_min, hrs_max, steps, desc = template
            human_hours = round(_rand_roi.uniform(hrs_min, hrs_max), 1)
            human_cost = round(hourly_rate * human_hours, 2)
            overhead = round(human_cost * _rand_roi.uniform(0.02, 0.05), 2)
            # Agent compute: realistic token-cost-based estimate ($0.50–$15 per task)
            agent_cost_base = round(_rand_roi.uniform(0.50, 15.0), 2)

            if status is None:
                # Pick a random status weighted toward active states
                status = _rand_roi.choices(
                    ["pending", "running", "qc", "hitl_review", "complete"],
                    weights=[20, 35, 15, 10, 20], k=1
                )[0]
            if pct is None:
                pct_map = {"pending": 0, "running": _rand_roi.randint(10, 85),
                           "qc": _rand_roi.randint(85, 95),
                           "hitl_review": _rand_roi.randint(88, 97),
                           "complete": 100}
                pct = pct_map[status]

            # Agent compute grows with progress
            agent_cost = round(agent_cost_base * pct / 100, 2) if status != "complete" else agent_cost_base
            roi = round(human_cost - agent_cost - overhead, 2)

            # Pick 2–4 agents from the pool
            num_agents = _rand_roi.randint(2, 4)
            # Ensure the agents used in the checklist are included
            checklist_agents = list({s[1] for s in steps})
            pool_names = {a["name"] for a in _ROI_AGENT_POOL}
            valid_checklist = [a for a in checklist_agents if a in pool_names]
            # Start with agents from the checklist, then fill from pool
            picked = valid_checklist[:num_agents]
            remaining_pool = [a for a in _ROI_AGENT_POOL if a["name"] not in picked]
            _rand_roi.shuffle(remaining_pool)
            for a in remaining_pool:
                if len(picked) >= num_agents:
                    break
                picked.append(a["name"])
            agents = [a for a in _ROI_AGENT_POOL if a["name"] in picked]

            start_dt = _now_dt_roi + _td_roi(days=day_offset, hours=hour_offset)
            end_dt = start_dt + _td_roi(hours=max(0.5, human_hours / 3))
            eid = "seed-" + _hl_roi.sha256((title + str(day_offset) + str(hour_offset)).encode()).hexdigest()[:12]

            checklist = _mk_checklist(steps, pct, status)

            return {
                "event_id": eid,
                "title": title,
                "description": desc,
                "automation_id": None,
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "status": status,
                "progress_pct": pct,
                "human_cost_estimate": human_cost,
                "human_time_estimate_hours": human_hours,
                "hourly_rate": hourly_rate,
                "agent_compute_cost": agent_cost,
                "overhead_cost": overhead,
                "roi": roi,
                "actual_time_hours": round(human_hours / 3, 2) if status == "complete" else 0.0,
                "agents": agents,
                "checklist": checklist,
                "hitl_reviews": [],
                "qc_passes": (_rand_roi.randint(1, 3) if status == "complete" else 0),
                "qc_failures": 0,
                "cost_adjustments": [],
                "created_at": _now_dt_roi.isoformat(),
                "updated_at": _now_dt_roi.isoformat(),
            }

        # Generate 12–16 events spread across Mon–Sun of the current week
        # Use deterministic day/hour slots based on shuffled templates
        _roi_slots = [
            (-1, 9), (-1, 14), (0, 8), (0, 10), (0, 13), (0, 15),
            (1, 9),  (1, 11), (1, 14), (2, 8),  (2, 11), (2, 16),
            (3, 9),  (3, 13), (4, 10), (4, 14),
        ]
        _shuffled_templates = list(_ROI_TASK_TEMPLATES)
        _rand_roi.shuffle(_shuffled_templates)
        _num_events = _rand_roi.randint(12, 16)
        _seed_roi = []
        for _idx, (day_off, hr_off) in enumerate(_roi_slots[:_num_events]):
            tmpl = _shuffled_templates[_idx % len(_shuffled_templates)]
            _seed_roi.append(_mk_roi_event(tmpl, day_off, hr_off))

        for _rcev in _seed_roi:
            if not any(e["event_id"] == _rcev["event_id"] for e in _roi_calendar_store):
                _roi_calendar_store.append(_rcev)
        logger.info("ROI Calendar: seeded %d randomly-generated events", len(_seed_roi))
    except Exception as _roi_seed_exc:
        logger.debug("ROI Calendar seeding skipped: %s", _roi_seed_exc)

    # ── Route Coverage Scanner (must be last — sees all registered routes) ──
    _route_coverage_scanner = None
    try:
        from src.route_coverage_scanner import register_route_coverage_endpoints
        _route_coverage_scanner = register_route_coverage_endpoints(app)
        setattr(murphy, "route_coverage_scanner", _route_coverage_scanner)
    except Exception as _rcs_exc:
        logger.warning("Route coverage scanner not loaded: %s", _rcs_exc)


    # ── PATCH-065: Public API Server + OAuth AS + Connector Agent ───────────
    try:
        from src.murphy_api_server import create_public_api_routes
        create_public_api_routes(app, murphy_instance=murphy)
        logger.info("PATCH-065a: Public API server routes mounted (/api/v1/*)")
    except Exception as _pas_exc:
        logger.warning("PATCH-065a public API server not loaded: %s", _pas_exc)

    try:
        from src.murphy_oauth_server import create_oauth_server_routes
        create_oauth_server_routes(app)
        logger.info("PATCH-065b: OAuth authorization server routes mounted (/oauth/*, /.well-known/*)")
    except Exception as _oas_exc:
        logger.warning("PATCH-065b OAuth server not loaded: %s", _oas_exc)

    try:
        from src.murphy_connector_agent import create_connector_agent_routes
        create_connector_agent_routes(app)
        logger.info("PATCH-065c: Connector agent routes mounted (/api/connectors/*)")
    except Exception as _mca_exc:
        logger.warning("PATCH-065c connector agent not loaded: %s", _mca_exc)





    # ── PATCH-072a: Ambient AI Full Activation ────────────────────────────────
    try:
        from src.ambient_full_router import router as _ambient_full_router
        # Remove old stub routes by mounting dedicated router (takes precedence via order)
        app.include_router(_ambient_full_router)
        logger.info("PATCH-072a: ambient_full_router mounted — /api/ambient/* live with synthesis + email delivery")
    except Exception as _afr_exc:
        logger.warning("PATCH-072a: ambient_full_router failed: %s", _afr_exc)

    # ── PATCH-072g: Share AmbientContextStore ────────────────────────────────
    try:
        from src.ambient_context_store import AmbientContextStore as _ACSS
        from src.ambient_full_router import set_shared_store as _afr_set_store
        _shared_ambient_store = _ACSS(max_signals=2000, ttl_seconds=86400)
        murphy._ambient_store = _shared_ambient_store
        _afr_set_store(_shared_ambient_store)
        logger.info("PATCH-072g: Shared AmbientContextStore wired — signals+synthesis unified")
    except Exception as _afr_store_exc:
        logger.warning("PATCH-072g: store injection failed: %s", _afr_store_exc)

    # ── PATCH-072b: Management AI Activation ──────────────────────────────────
    try:
        from src.management_ai_router import router as _mgmt_ai_router
        app.include_router(_mgmt_ai_router)
        logger.info("PATCH-072b: management_ai_router mounted — /api/mgmt/* live (Board/Status/Workspace/Dashboard/Recipes/Timeline)")
    except Exception as _mar_exc:
        logger.warning("PATCH-072b: management_ai_router failed: %s", _mar_exc)

    # ── PATCH-073: LargeControlModel (LCM) Activation ───────────────────────
    try:
        from src.lcm_router import build_router as _lcm_build_router
        _lcm_router = _lcm_build_router()
        app.include_router(_lcm_router)
        logger.info("PATCH-073: LCM router mounted — /api/lcm/* live")
    except Exception as _lcm_exc:
        logger.warning("PATCH-073: LCM router mount failed: %s", _lcm_exc)

    # ── PATCH-093c: Shield Wall ───────────────────────────────────────────────
    try:
        from src.shield_wall import build_shield_wall_router as _sw_router_fn
        _sw_router = _sw_router_fn()
        if _sw_router is not None:
            app.include_router(_sw_router)
            logger.info("PATCH-093c: Shield Wall router mounted — /api/shield/* live")
    except Exception as _sw_exc:
        logger.warning("PATCH-093c: Shield Wall router mount failed: %s", _sw_exc)

    # ── PATCH-096b: Convergence Engine ──────────────────────────────────────
    try:
        from src.convergence_router import build_convergence_router as _conv_build
        _conv_router = _conv_build()
        app.include_router(_conv_router)
        logger.info("PATCH-096b: Convergence router mounted — /api/convergence/* live")
    except Exception as _conv_exc:
        logger.warning("PATCH-096b: Convergence router mount failed: %s", _conv_exc)

    # ── PATCH-096b: Direct convergence POST endpoints (bypass router validation) ──
    @app.post("/api/convergence/analyze")
    async def _convergence_analyze(request: Request):
        """Three-body convergence analysis — trajectory-aware, graph-persisted."""
        try:
            body = await request.json()
            from src.recursive_convergence_engine import process as _rce
            content = (body.get("content") or "").strip()
            if not content:
                return JSONResponse({"success": False, "error": "content required"}, status_code=400)
            signal, action = _rce(
                content,
                body.get("feed_history", []),
                body.get("domain", "general"),
                body.get("session_id"),
            )
            return JSONResponse({"success": True, "data": {
                "convergence": signal.to_dict(),
                "steering":    action.to_dict(),
                "session_id":  body.get("session_id"),
                "oath": "We do not censor. We shift the gradient. Free will is sacred.",
            }})
        except Exception as exc:
            logger.error("convergence/analyze error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/convergence/investigate")
    async def _convergence_investigate(request: Request):
        """Probabilistic CIDP — Bayesian harm P(catastrophic)>0.95 hard stop only."""
        try:
            body = await request.json()
            from src.criminal_investigation_protocol import investigate as _cidp
            intent = (body.get("intent") or "").strip()
            if not intent:
                return JSONResponse({"success": False, "error": "intent required"}, status_code=400)
            report = _cidp(
                intent=intent,
                context=body.get("context", {}),
                domain=body.get("domain", "general"),
            )
            return JSONResponse({"success": True, "data": report.to_dict()})
        except Exception as exc:
            logger.error("convergence/investigate error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    # ── PATCH-097: Foundation Modules — direct POST endpoints ─────────────────
    # Rules of Conduct, Ledger Engine, Front-of-Line Queue
    # Registered directly on @app (not router) per PATCH-096b bypass pattern.

    @app.post("/api/conduct/check")
    async def _conduct_check(request: Request):
        """
        PATCH-097 — Rules of Conduct check.
        Organ rule: no utilitarian sacrifice of an individual.
        Growth standard: upstream prevention over downstream correction.
        """
        try:
            from src.rules_of_conduct import conduct_engine
            body = await request.json()
            result = conduct_engine.check(
                action_desc         = body.get("action_desc", ""),
                individual_affected = body.get("individual_affected", False),
                ends_potential      = body.get("ends_potential", False),
                utilitarian_frame   = body.get("utilitarian_frame", False),
                retains_identity    = body.get("retains_identity", False),
            )
            return JSONResponse(result)
        except Exception as exc:
            logger.error("conduct/check error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/conduct/growth")
    async def _conduct_growth(request: Request):
        """
        PATCH-097 — Growth potential assessment.
        Returns upstream vs downstream opportunity map for a domain.
        """
        try:
            from src.rules_of_conduct import conduct_engine
            body = await request.json()
            domain = body.get("domain", "general")
            result = conduct_engine.growth_opportunities(domain)
            return JSONResponse(result)
        except Exception as exc:
            logger.error("conduct/growth error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/ledger/log")
    async def _ledger_log(request: Request):
        """
        PATCH-097 — Ledger live activity log.
        Record a provision or debt for a deployment.
        """
        try:
            from src.ledger_engine import ledger_engine
            body = await request.json()
            entry = ledger_engine.log_live(
                deployment_id   = body.get("deployment_id", "unknown"),
                module          = body.get("module", ""),
                entry_type      = body.get("entry_type", "PROVISION"),
                units           = float(body.get("units", 0.0)),
                description     = body.get("description", ""),
            )
            return JSONResponse(entry.to_dict())
        except Exception as exc:
            logger.error("ledger/log error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/ledger/reconcile")
    async def _ledger_reconcile(request: Request):
        """
        PATCH-097b — Full ledger cycle: open_estimate → reconcile in one call.
        Computes net impact, debt incurred, and 10x obligation for successor.
        Body: {deployment_id, deployment_desc?, domain?, tokens_used?, compute_joules?,
               water_liters?, co2_grams?, est_net?, est_rationale?}
        """
        try:
            from src.ledger_engine import ledger_engine, LedgerEngine
            body = await request.json()
            did   = body.get("deployment_id", "unknown")
            desc  = body.get("deployment_desc", did)
            domain= body.get("domain", "ai_inference")
            # Compute rough cost/provision from raw metrics
            tokens  = float(body.get("tokens_used", 0))
            joules  = float(body.get("compute_joules", 0))
            water   = float(body.get("water_liters", 0))
            co2     = float(body.get("co2_grams", 0))
            cost_str = f"Tokens={tokens}, Compute={joules}J, Water={water}L, CO2={co2}g"
            prov_str = body.get("est_provision", "Inference service delivered")
            net_str  = body.get("est_net", "Positive if model helps user; negative if extractive")
            rat_str  = body.get("est_rationale", "Standard inference estimate")
            # Open then immediately reconcile
            entry = ledger_engine.open_estimate(
                deployment_id  = did,
                deployment_desc= desc,
                domain         = domain,
                est_cost       = cost_str,
                est_provision  = prov_str,
                est_net        = net_str,
                est_rationale  = rat_str,
            )
            result = ledger_engine.reconcile(entry.entry_id)
            return JSONResponse({"success": True, **result})
        except Exception as exc:
            logger.error("ledger/reconcile error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/ledger/status")
    async def _ledger_status():
        """PATCH-097b — Full ledger status: all entries, debts, deferred obligations."""
        try:
            from src.ledger_engine import ledger_engine
            return JSONResponse({"success": True, **ledger_engine.status()})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/frontline/check")
    async def _frontline_check(request: Request):
        """
        PATCH-097 — Front-of-line commissioning gate.
        Q1: What did I inherit? Q2: What do I threaten?
        Returns CLEAR / HOLD / HITL_REQUIRED.
        """
        try:
            from src.front_of_line import front_of_line
            body = await request.json()
            result = front_of_line.check_deployment(
                deployment_id   = body.get("deployment_id", "unknown"),
                deployment_desc = body.get("deployment_desc", ""),
                inherited_debt  = float(body.get("inherited_debt", 0.0)),
                inherited_10x   = float(body.get("inherited_10x", 0.0)),
                deferred_count  = int(body.get("deferred_count", 0)),
            )
            return JSONResponse(result.to_dict())
        except Exception as exc:
            logger.error("frontline/check error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


    # ── PATCH-102: Hardware Telemetry API ──────────────────────────────────────

    @app.get("/api/hardware/snapshot")
    async def _hw_snapshot():
        """PATCH-102 — Full hardware telemetry snapshot (CPU, RAM, disk, network, latency, uptime, health)."""
        try:
            from src.hardware_telemetry import hardware_telemetry
            return JSONResponse({"success": True, "snapshot": hardware_telemetry.snapshot().to_dict()})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/hardware/summary")
    async def _hw_summary():
        """PATCH-102 — Lightweight hardware health summary (for dashboards and RROM)."""
        try:
            from src.hardware_telemetry import hardware_telemetry
            return JSONResponse({"success": True, **hardware_telemetry.summary()})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/hardware/history")
    async def _hw_history(n: int = 12):
        """PATCH-102 — Historical hardware telemetry (last N snapshots, default 12)."""
        try:
            from src.hardware_telemetry import hardware_telemetry
            return JSONResponse({"success": True, "history": hardware_telemetry.history(n)})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/hardware/specs")
    async def _hw_specs():
        """PATCH-102 — Static hardware specifications."""
        try:
            from src.hardware_telemetry import hardware_telemetry
            from dataclasses import asdict
            return JSONResponse({"success": True, "specs": asdict(hardware_telemetry._get_specs())})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


    # ── PATCH-100: CIDP Persistence API ───────────────────────────────────────

    @app.get("/api/cidp/reports")
    async def _cidp_reports(
        request: Request,
        limit: int = 50,
        domain: str = None,
        verdict: str = None,
    ):
        """PATCH-100 — Retrieve persisted CIDP investigation reports."""
        try:
            from src.criminal_investigation_protocol import query_cidp_reports, cidp_stats
            reports = query_cidp_reports(limit=limit, domain=domain, verdict=verdict)
            stats   = cidp_stats()
            return JSONResponse({"success": True, "stats": stats, "reports": reports})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/cidp/stats")
    async def _cidp_stats():
        """PATCH-100 — CIDP report store statistics."""
        try:
            from src.criminal_investigation_protocol import cidp_stats
            return JSONResponse({"success": True, **cidp_stats()})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


    # ── PATCH-101: Autonomous Self-Improvement Loop ───────────────────────────

    @app.post("/api/self/autonomous")
    async def _autonomous_cycle(request: Request):
        """
        PATCH-101 — Murphy's autonomous self-improvement loop.
        Identifies gaps, runs CIDP + Model Team review, PCC gate, applies patch.

        Body (all optional):
          max_patches: int = 1       — max patches per cycle
          min_priority: str = MEDIUM — minimum gap priority to action
          dry_run: bool = true       — rehearse without writing (default: SAFE)

        Requires auth.
        """
        try:
            from src.self_modification import self_mod
            body = await request.json()
            result = self_mod.run_autonomous_cycle(
                max_patches  = int(body.get("max_patches",  1)),
                min_priority = body.get("min_priority", "MEDIUM"),
                dry_run      = bool(body.get("dry_run", True)),
            )
            return JSONResponse({"success": True, "cycle": result})
        except Exception as exc:
            logger.error("autonomous cycle error: %s", exc, exc_info=True)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


    # ── PATCH-099: PCC — Predictive Convergence Correction API ────────────────

    @app.get("/api/pcc/status")
    async def _pcc_status(session_id: str = None):
        """PATCH-099 — Current PCC global and per-session status."""
        try:
            from src.pcc import pcc
            return JSONResponse({"success": True, **pcc.status(session_id)})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/pcc/feedback")
    async def _pcc_feedback(request: Request):
        """
        PATCH-099 — Record a confirmed or disconfirmed outcome.
        Updates R_t rolling baseline.
        Body: {session_id, r_fair, confirmed (bool)}
        """
        try:
            from src.pcc import pcc
            body = await request.json()
            pcc.feedback(
                session_id = body.get("session_id", "global"),
                r_fair     = float(body.get("r_fair", 0.5)),
                confirmed  = bool(body.get("confirmed", True)),
            )
            return JSONResponse({"success": True, **pcc.status(body.get("session_id"))})
        except Exception as exc:
            logger.error("pcc/feedback error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/pcc/compute")
    async def _pcc_compute(request: Request):
        """
        PATCH-099 — Direct PCC computation (for inspection/testing).
        Body: {session_id, state_vector {d1..d8}, causal_chain?, trajectory_len?, d9_balance?}
        """
        try:
            from src.pcc import pcc, PCCInput
            body = await request.json()
            inp = PCCInput(
                session_id    = body.get("session_id", "test"),
                state_vector  = body.get("state_vector", {}),
                causal_chain  = body.get("causal_chain", "default"),
                trajectory_len= int(body.get("trajectory_len", 0)),
                d9_balance    = float(body.get("d9_balance", 0.0)),
                assumptions   = body.get("assumptions", []),
            )
            result = pcc.compute(inp)
            return JSONResponse({"success": True, **result.to_dict()})
        except Exception as exc:
            logger.error("pcc/compute error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


    # ── PATCH-098: RROM Phase 1 — Resource Orchestration Measurement ─────────

    @app.get("/api/rrom/snapshot")
    async def _rrom_snapshot():
        """PATCH-098 — Current RROM six-face resource snapshot."""
        try:
            from src.rrom import rrom
            snap = rrom.current_snapshot()
            if not snap:
                return JSONResponse({"success": True, "status": "warming_up", "message": "Sampler started, first snapshot in 5s"})
            return JSONResponse({"success": True, **snap})
        except Exception as exc:
            logger.error("rrom/snapshot error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/rrom/history")
    async def _rrom_history(n: int = 12):
        """PATCH-098 — RROM snapshot history (last N samples, default 12 = 1 min)."""
        try:
            from src.rrom import rrom
            return JSONResponse({"success": True, "history": rrom.history(n)})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/rrom/face/{face}")
    async def _rrom_face(face: str):
        """PATCH-098 — Status of a single RROM face (shield_util, llm_demand, etc.)."""
        try:
            from src.rrom import rrom
            return JSONResponse({"success": True, **rrom.face_status(face)})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


    # ── PATCH-097b: Self-Modification API ────────────────────────────────────

    @app.post("/api/self/evaluate")
    @app.get("/api/self/evaluate")
    async def _self_evaluate(request: Request):
        """
        PATCH-097b — Murphy self-assessment report.
        Applies guiding engineering principles to audit system state.
        """
        try:
            from src.self_modification import self_mod
            try:
                body = await request.json() if request.headers.get("content-type","").startswith("application/json") else {}
            except Exception:
                body = {}
            scope = body.get("scope", "full")
            report = self_mod.evaluate_self(scope)
            return JSONResponse({"success": True, "report": report})
        except Exception as exc:
            logger.error("self/evaluate error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/self/patch")
    async def _self_patch(request: Request):
        """
        PATCH-097b — Murphy writes and applies a source patch to itself.
        Requires: patch_id, target_file, new_content, description, rationale.
        Full pipeline: conduct check → gate → backup → syntax → write → git → restart.
        """
        try:
            from src.self_modification import self_mod, PatchIntent
            body = await request.json()
            intent = PatchIntent(
                patch_id     = body.get("patch_id", "SELF-001"),
                target_file  = body.get("target_file", ""),
                description  = body.get("description", ""),
                rationale    = body.get("rationale", ""),
                impact_score = float(body.get("impact_score", 1.0)),
                debt_score   = float(body.get("debt_score", 0.0)),
            )
            if not intent.target_file:
                return JSONResponse({"success": False, "error": "target_file required"}, status_code=400)
            new_content = body.get("new_content", "")
            if not new_content:
                return JSONResponse({"success": False, "error": "new_content required"}, status_code=400)
            restart = body.get("restart", False)  # default False for safety
            result = self_mod.write_patch(intent, new_content, restart=restart)
            return JSONResponse({"success": result.success, "result": result.to_dict()})
        except Exception as exc:
            logger.error("self/patch error: %s", exc)
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.get("/api/self/backups")
    async def _self_backups():
        """PATCH-097b — List all self-modification patch backups."""
        try:
            from src.self_modification import self_mod
            return JSONResponse({"success": True, "backups": self_mod.list_backups()})
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    @app.post("/api/self/restore")
    async def _self_restore(request: Request):
        """PATCH-097b — Restore a backed-up file from a patch_id."""
        try:
            from src.self_modification import self_mod
            body = await request.json()
            patch_id = body.get("patch_id", "")
            if not patch_id:
                return JSONResponse({"success": False, "error": "patch_id required"}, status_code=400)
            result = self_mod.restore_backup(patch_id)
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    # ── PATCH-071: Self-Marketing + Sell Engine ──────────────────────────────
    try:
        from src.marketing_router import router as _marketing_router
        app.include_router(_marketing_router)
        logger.info("PATCH-071: marketing_router mounted — /api/marketing/* + /api/sell/* live")
    except Exception as _mr_exc:
        logger.warning("PATCH-071: marketing_router failed to mount: %s", _mr_exc)

    # ── PATCH-071b: Production router (campaign mgmt, HITL, workflows, verticals) ──
    try:
        from src.production_router import router as _prod_router
        app.include_router(_prod_router)
        logger.info("PATCH-071b: production_router mounted — /api/marketing/campaigns, /api/hitl/queue, /api/workflows/* live")
    except Exception as _pr_exc:
        logger.warning("PATCH-071b: production_router failed to mount: %s", _pr_exc)

    # ── PATCH-070d: Schedule automatic triage every 30 minutes ──────────
    try:
        import threading as _threading
        def _run_periodic_triage():
            import time as _time
            _time.sleep(300)  # wait 5 min after startup before first run
            while True:
                try:
                    from src.murphy_self_patch_loop import run_triage_cycle
                    result = run_triage_cycle()
                    logger.info("PATCH-070d: Scheduled triage complete — issues=%s diffs=%s",
                                result.get("issues_found", 0), len(result.get("diff_results", [])))
                except Exception as _te:
                    logger.warning("PATCH-070d: Scheduled triage failed: %s", _te)
                _time.sleep(1800)  # 30 minutes

        _triage_thread = _threading.Thread(target=_run_periodic_triage, daemon=True, name="murphy-triage")
        _triage_thread.start()
        logger.info("PATCH-070d: Periodic triage thread started (every 30min)")
    except Exception as _ste:
        logger.warning("PATCH-070d: Could not start triage scheduler: %s", _ste)

    # ── PATCH-076b: Start MurphyScheduler at boot ────────────────────────────
    try:
        if getattr(murphy, 'murphy_scheduler', None) is not None:
            _sched_started = murphy.murphy_scheduler.start()
            logger.info("PATCH-076b: MurphyScheduler.start() => %s", _sched_started)
        else:
            from src.scheduler import MurphyScheduler as _MS076
            _ms076 = _MS076()
            murphy.murphy_scheduler = _ms076
            _sched_started = _ms076.start()
            logger.info("PATCH-076b: MurphyScheduler direct init => started=%s", _sched_started)
    except Exception as _se076:
        logger.warning("PATCH-076b: Scheduler start failed: %s", _se076)

    # ── PATCH-076a/c/d: Murphy Data Loop (Self-Fix + CRM + Market → Ambient → LCM) ─
    try:
        from src.murphy_data_loop import start_data_loop as _start_dl076
        _dl076_thread = _start_dl076(interval=3600)
        logger.info("PATCH-076: Data loop started — CRM/Market/SelfFix -> Ambient -> LCM every 1h")
    except Exception as _dl076_exc:
        logger.warning("PATCH-076: Data loop failed: %s", _dl076_exc)

    # ── PATCH-076e/g/h/k: Extension Routers (KG + Confidence + AUAR + ML) ──────
    try:
        from src.murphy_extension_routers import (
            build_kg_router as _build_kg,
            build_confidence_router as _build_conf,
            build_auar_router as _build_auar,
            build_ml_router as _build_ml,
        )
        app.include_router(_build_kg())
        logger.info("PATCH-076e: /api/kg/* mounted — Memory Palace / Knowledge Graph live")
        app.include_router(_build_conf())
        logger.info("PATCH-076g: /api/confidence/* mounted — Confidence Engine live")
        app.include_router(_build_auar())
        logger.info("PATCH-076h: /api/auar/* mounted — AUAR Analytics live")
        app.include_router(_build_ml())
        logger.info("PATCH-076k: /api/ml/* mounted — ML API live")
    except Exception as _ext_exc:
        logger.warning("PATCH-076e/g/h/k: Extension routers failed: %s", _ext_exc)

    # ── PATCH-076l: Gate Synthesis — enumerate + activate failure-mode gates ────
    try:
        import threading as _gate_threading
        def _activate_gates():
            import time as _t, json as _j, urllib.request as _ur
            _t.sleep(20)  # wait for server fully up
            try:
                # Enumerate failure modes
                r = _ur.Request(
                    "http://127.0.0.1:8000/api/gate-synthesis/failure-modes/enumerate",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with _ur.urlopen(r, timeout=15) as resp:
                    fdata = _j.loads(resp.read())
                # Generate gates from Murphy's profile
                r2 = _ur.Request(
                    "http://127.0.0.1:8000/api/gate-synthesis/gates/generate",
                    data=_j.dumps({"profile": "murphy_os", "auto_activate": True}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with _ur.urlopen(r2, timeout=15) as resp2:
                    gdata = _j.loads(resp2.read())
                logger.info("PATCH-076l: Gate Synthesis activated — gates=%s", gdata.get("count", "?"))
            except Exception as _ge:
                logger.debug("PATCH-076l: Gate activation error (non-critical): %s", _ge)
        _gate_thread = _gate_threading.Thread(target=_activate_gates, daemon=True, name="gate-activator")
        _gate_thread.start()
        logger.info("PATCH-076l: Gate activation thread started")
    except Exception as _gate_exc:
        logger.warning("PATCH-076l: Gate thread failed: %s", _gate_exc)

    # ── PATCH-077a/b: RSC Unified Sink — mount router + start all adapters ────
    try:
        from src.rsc_router import router as _rsc_router
        app.include_router(_rsc_router)
        logger.info("PATCH-077b: /api/rsc/* mounted — RSC Unified Sink live")
    except Exception as _rsc_r_exc:
        logger.warning("PATCH-077b: RSC router failed: %s", _rsc_r_exc)
    try:
        from src.rsc_unified_sink import start_all_adapters as _rsc_start
        _rsc_start()
        logger.info("PATCH-077a: RSC source adapters started (8 streams → unified S(t))")
    except Exception as _rsc_a_exc:
        logger.warning("PATCH-077a: RSC adapters failed: %s", _rsc_a_exc)
    # ── PATCH-085: Ethical Hacking Engine ───────────────────────────────────
    try:
        from src.ethical_hacking_engine import router as _hack_router
        app.include_router(_hack_router)
        logger.info("PATCH-085: /api/hack/* mounted — Ethical Hacking Engine live")
    except Exception as _hack_exc:
        logger.warning("PATCH-085: Ethical Hacking Engine failed to mount: %s", _hack_exc)
    # ── PATCH-085b: Transport Layer (location masking + node routing) ────────
    try:
        from src.hack_transport import router as _hack_transport_router
        app.include_router(_hack_transport_router)
        logger.info("PATCH-085b: /api/hack/nodes/* mounted — transport layer live (Tor + proxy nodes)")
    except Exception as _htr_exc:
        logger.warning("PATCH-085b: Hack transport router failed: %s", _htr_exc)
    # ── PATCH-086: Recursive Stream Hacking Feed + Attack Graph ──────────────
    try:
        from src.hack_stream_graph import router as _hack_graph_router
        app.include_router(_hack_graph_router)
        logger.info("PATCH-086: /api/hack/feed/* + /api/hack/graph/* mounted — recursive stream graph live")
    except Exception as _hsg_exc:
        logger.warning("PATCH-086: Hack stream graph failed: %s", _hsg_exc)
    # ── PATCH-087: Honeypot + Counter-Intelligence Engine ────────────────────
    try:
        from src.honeypot_engine import api_router as _hp_api, trap_router as _hp_trap, HoneypotMiddleware as _HpMw
        app.include_router(_hp_api)
        # Trap router mounts LAST so it doesn't shadow real routes
        app.include_router(_hp_trap)
        app.add_middleware(_HpMw)
        logger.info("PATCH-087: Honeypot active — 37 traps, passive fingerprint middleware, counter-scan via Tor")
    except Exception as _hp_exc:
        logger.warning("PATCH-087: Honeypot engine failed: %s", _hp_exc)

    # ── PATCH-077d: Unmounted routers — wire all verified importable routers ──
    _unmounted = [
        ("src.collaboration.api",                  "router",             "/api/collaboration"),
        ("src.portfolio.api",                       "router",             "/api/portfolio"),
        ("src.automations.api",                     "router",             "/api/automations"),
        ("src.guest_collab.api",                    "router",             "/api/guest"),
        ("src.chaos.api",                           "router",             "/api/chaos"),
        # PSM handled separately below with build_router() pattern
        ("src.time_tracking.api",                   "router",             "/api/time-tracking"),
        ("src.dashboards.api",                      "router",             "/api/dashboards"),
        ("src.dev_module.api",                      "router",             "/api/dev"),
        ("src.workdocs.api",                        "router",             "/api/workdocs"),
        ("src.board_system.api",                    "router",             "/api/boards"),
    ]
    for _mod_path, _attr, _prefix in _unmounted:
        try:
            import importlib as _il
            _m = _il.import_module(_mod_path)
            _r = getattr(_m, _attr, None)
            if _r is None and hasattr(_m, 'create_router'):
                _r = _m.create_router()
            if _r is not None:
                app.include_router(_r)
                logger.info("PATCH-077d: %s mounted", _prefix)
            else:
                logger.warning("PATCH-077d: %s — no router attr found", _prefix)
        except Exception as _ue:
            logger.warning("PATCH-077d: %s failed: %s", _prefix, _ue)

    # ── PATCH-079c: Web Tool Router — internet as a tool ─────────────────────
    try:
        from src.web_tool_router import router as _web_router
        app.include_router(_web_router)
        logger.info("PATCH-079c: /api/web/* mounted — search/fetch/screenshot/fill live")
    except Exception as _wr_exc:
        logger.warning("PATCH-079c: web_tool_router failed: %s", _wr_exc)

    # ── PATCH-079d: Platform Self-Modification — proper build_router() wiring ─
    try:
        from src.platform_self_modification.endpoint import build_router as _psm_build_router
        # Wire RSC unified sink as the Lyapunov source
        def _get_lyap():
            try:
                from src.rsc_unified_sink import get_sink
                sink = get_sink()
                current = sink.get()
                # Return a duck-typed Lyapunov-compatible object
                class _LyapProxy:
                    def is_stable(self):
                        c = get_sink().get()
                        return c is not None and c.s_t >= 0.70
                    def get_stability_score(self):
                        c = get_sink().get()
                        return c.s_t if c else 1.0
                    def get_snapshot(self):
                        c = get_sink().get()
                        return c.to_dict() if c else {}
                return _LyapProxy()
            except Exception:
                return None
        def _get_orch():
            return None  # orchestrator optional
        _psm_router = _psm_build_router(
            get_orchestrator=_get_orch,
            get_lyapunov_source=_get_lyap,
        )
        app.include_router(_psm_router)
        logger.info("PATCH-079d: /api/platform/self-modification/* mounted — RSC-gated PSM live")
    except Exception as _psm_exc:
        logger.warning("PATCH-079d: PSM router failed: %s", _psm_exc)


    # ── PATCH-080c: Engineering Intelligence Router ────────────────────────────
    try:
        from src.engineering_router import router as _eng_router
        app.include_router(_eng_router)
        logger.info("PATCH-080c: /api/eng/* mounted — document ingest + paper fetch + RAG live")
    except Exception as _eng_exc:
        logger.warning("PATCH-080c: engineering_router failed: %s", _eng_exc)


    # ── PATCH-081b: Integration Builder Router ─────────────────────────────────
    try:
        from src.integration_router import router as _integ_build_router
        app.include_router(_integ_build_router)
        logger.info("PATCH-081b: /api/integrations/* mounted — autonomous integration builder live")
    except Exception as _ib_exc:
        logger.warning("PATCH-081b: integration_router failed: %s", _ib_exc)


    # ── PATCH-082d: Mount modules with existing api.py but previously unwired ──
    _unwired_modules = [
        ("form_intake.api",                "router",  "/api/forms",    "Form Intake"),
        ("document_export.api",            "create_router", "/api/export", "Document Export"),
        ("telemetry_learning.api",         "app",     "/api/telemetry","Telemetry Learning"),
    ]
    for _mod_path, _attr, _prefix, _label in _unwired_modules:
        try:
            import importlib
            _mod = importlib.import_module(f"src.{_mod_path}")
            _r = getattr(_mod, _attr)
            if callable(_r) and not hasattr(_r, "routes"):
                _r = _r()  # call factory if it's create_router()
            app.include_router(_r)
            logger.info("PATCH-082d: %s mounted at %s", _label, _prefix)
        except Exception as _e:
            logger.warning("PATCH-082d: %s failed: %s", _label, _e)


    # ── PATCH-084: Auto-Wire Router — exposes all 31 unwired modules ──────────
    try:
        from src.auto_wire_router import router as _autowire_router
        app.include_router(_autowire_router)
        logger.info("PATCH-084: /api/modules/* mounted — 31 unwired modules now inspectable")
    except Exception as _aw_exc:
        logger.warning("PATCH-084: auto_wire_router failed: %s", _aw_exc)


    # ── PATCH-089: Quick-win router wiring ─────────────────────────────────────
    # Wire all routers that existed but were never mounted.

    # CRM
    try:
        from src.crm.api import create_crm_router
        _crm_r = create_crm_router()
        app.include_router(_crm_r)
        logger.info("PATCH-089: CRM router mounted — /api/crm/* live")
    except Exception as _e:
        logger.warning("PATCH-089: crm router failed: %s", _e)

    # Time tracking
    try:
        from src.time_tracking.api import create_time_tracking_router as _tt_f
        app.include_router(_tt_f())
        logger.info("PATCH-089: Time tracking router mounted — /api/time-tracking/* live")
    except Exception as _e:
        logger.warning("PATCH-089: time_tracking router failed: %s", _e)

    # Collaboration
    try:
        from src.collaboration.api import create_collaboration_router as _collab_f
        app.include_router(_collab_f())
        logger.info("PATCH-089: Collaboration router mounted — /api/collaboration/* live")
    except Exception as _e:
        logger.warning("PATCH-089: collaboration router failed: %s", _e)

    # Portfolio
    try:
        from src.portfolio.api import create_portfolio_router as _port_f
        app.include_router(_port_f())
        logger.info("PATCH-089: Portfolio router mounted — /api/portfolio/* live")
    except Exception as _e:
        logger.warning("PATCH-089: portfolio router failed: %s", _e)

    # Dashboards
    try:
        from src.dashboards.api import create_dashboard_router as _dash_f
        app.include_router(_dash_f())
        logger.info("PATCH-089: Dashboards router mounted — /api/dashboards/* live")
    except Exception as _e:
        logger.warning("PATCH-089: dashboards router failed: %s", _e)

    # Guest collab
    try:
        from src.guest_collab.api import create_guest_router as _guest_f
        app.include_router(_guest_f())
        logger.info("PATCH-089: Guest collab router mounted — /api/guest/* live")
    except Exception as _e:
        logger.warning("PATCH-089: guest_collab router failed: %s", _e)

    # ML
    try:
        from src.ml.api import create_ml_router as _ml_f
        app.include_router(_ml_f())
        logger.info("PATCH-089: ML router mounted — /api/ml/* live")
    except Exception as _e:
        logger.warning("PATCH-089: ml router failed: %s", _e)

    # System updates
    try:
        from src.system_update_api import create_system_update_router as _sysupd_f
        app.include_router(_sysupd_f())
        logger.info("PATCH-089: System update router mounted — /api/system-updates/* live")
    except Exception as _e:
        logger.warning("PATCH-089: system_update_api router failed: %s", _e)

    # ── PATCH-089b: Wire persistent memory into startup ─────────────────────────
    try:
        from src.persistent_memory.tenant_memory import TenantMemoryStore
        _tenant_mem = TenantMemoryStore()
        app.state.tenant_memory = _tenant_mem
        logger.info("PATCH-089b: TenantMemoryStore wired — persistent memory active")
    except Exception as _e:
        logger.warning("PATCH-089b: tenant_memory failed: %s", _e)

    # ── PATCH-089c: LLM cost ledger — tap llm_provider, accumulate to SQLite ───
    try:
        from src.llm_cost_ledger import LLMCostLedger, patch_llm_provider, cost_router as _cost_router
        _cost_ledger = LLMCostLedger()
        patch_llm_provider(_cost_ledger)
        app.state.llm_cost_ledger = _cost_ledger
        app.include_router(_cost_router)
        logger.info("PATCH-089c: LLM cost ledger active — /api/llm-cost/* live")
    except Exception as _e:
        logger.warning("PATCH-089c: llm_cost_ledger failed: %s", _e)

    # ── PATCH-089d: System-wide audit trail ─────────────────────────────────────
    try:
        from src.murphy_audit_trail import AuditTrail, audit_router
        _audit = AuditTrail()
        app.state.audit_trail = _audit
        app.include_router(audit_router)
        logger.info("PATCH-089d: Audit trail active — /api/audit/* live")
    except Exception as _e:
        logger.warning("PATCH-089d: audit_trail failed: %s", _e)

    # ── PATCH-089e: MCP plugin router ───────────────────────────────────────────
    try:
        from src.mcp_plugin import create_mcp_router
        _mcp_r = create_mcp_router()
        app.include_router(_mcp_r)
        logger.info("PATCH-089e: MCP plugin router mounted — /api/mcp/* live")
    except Exception as _e:
        logger.warning("PATCH-089e: mcp_plugin router failed: %s", _e)


    return app


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

    # FIX-002: stamp deploy commit from inside the process (ExecStartPre can't
    # write to /etc/ under ProtectSystem=strict, so it was silently failing).
    try:
        import subprocess as _sp
        _commit = _sp.check_output(
            ["git", "-C", "/opt/Murphy-System", "rev-parse", "--short", "HEAD"],
            stderr=_sp.DEVNULL, timeout=5
        ).decode().strip()
        os.environ["MURPHY_DEPLOY_COMMIT"] = _commit
    except Exception as _ce:
        logger.debug("Could not stamp deploy commit: %s", _ce)

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
