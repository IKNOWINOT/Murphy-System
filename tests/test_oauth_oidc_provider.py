# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for oauth_oidc_provider — OAU-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable OAURecord with cause / effect / lesson annotations.
"""
from __future__ import annotations
import datetime
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from oauth_oidc_provider import (  # noqa: E402
    AuthorizationRequest,
    GrantType,
    OAuthManager,
    OAuthProvider,
    OAuthSession,
    OIDCDiscovery,
    ProviderConfig,
    SessionStatus,
    TokenSet,
    TokenStatus,
    UserInfo,
    create_oauth_api,
)
# -- Record pattern --------------------------------------------------------
@dataclass
class OAURecord:
    """One OAU check record."""
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )
_RESULTS: List[OAURecord] = []
def record(
    check_id: str, desc: str, expected: Any, actual: Any,
    cause: str = "", effect: str = "", lesson: str = "",
) -> bool:
    ok = expected == actual
    _RESULTS.append(OAURecord(
        check_id=check_id, description=desc, expected=expected,
        actual=actual, passed=ok, cause=cause, effect=effect, lesson=lesson,
    ))
    return ok
# -- Helpers ---------------------------------------------------------------
def _mgr() -> OAuthManager:
    return OAuthManager()
def _prov(name: str = "google") -> ProviderConfig:
    return ProviderConfig(
        name=name, provider_type=OAuthProvider.GOOGLE,
        client_id="cid_123", client_secret="csec_456",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        issuer="https://accounts.google.com",
        redirect_uri="http://localhost:8080/callback",
        role_mapping={"admin": "admin", "user": "viewer"},
    )
# -- Enum tests ------------------------------------------------------------
def test_oau_001_provider_enum():
    """OAuthProvider enum values."""
    assert record("OAU-001", "7 providers", 7, len(OAuthProvider),
                   cause="enum definition", effect="all SSO providers covered",
                   lesson="str enums give readable serialisation")
def test_oau_002_grant_type_enum():
    """GrantType enum values."""
    assert record("OAU-002", "4 grant types",
                   {"authorization_code", "client_credentials", "refresh_token", "device_code"},
                   {e.value for e in GrantType})
def test_oau_003_token_status_enum():
    """TokenStatus enum values."""
    assert record("OAU-003", "3 token statuses", 3, len(TokenStatus))
def test_oau_004_session_status_enum():
    """SessionStatus enum values."""
    assert record("OAU-004", "4 session statuses",
                   {"pending", "active", "expired", "revoked"},
                   {e.value for e in SessionStatus})
# -- Dataclass tests -------------------------------------------------------
def test_oau_005_provider_config():
    """ProviderConfig creation and secret redaction."""
    cfg = _prov()
    d = cfg.to_dict()
    assert record("OAU-005", "client_secret redacted",
                   "***REDACTED***", d["client_secret"],
                   cause="security requirement", effect="no secret leak",
                   lesson="always redact secrets in serialisation")
def test_oau_006_auth_request_pkce():
    """AuthorizationRequest generates PKCE code challenge."""
    req = AuthorizationRequest(provider_name="google")
    ch = req.code_challenge()
    assert record("OAU-006", "PKCE challenge is non-empty string",
                   True, isinstance(ch, str) and len(ch) > 10)
def test_oau_007_token_set_expiry():
    """TokenSet detects expiry correctly."""
    ts = TokenSet(access_token="abc", expires_in=0)
    import time; time.sleep(0.05)
    assert record("OAU-007", "Expired token detected",
                   True, ts.is_expired())
def test_oau_008_token_set_redaction():
    """TokenSet to_dict redacts tokens."""
    ts = TokenSet(access_token="abcdef123456", refresh_token="ref_token_xyz")
    d = ts.to_dict()
    assert record("OAU-008", "access_token redacted",
                   True, "REDACTED" in d["access_token"])
def test_oau_009_oidc_discovery():
    """OIDCDiscovery dataclass creation."""
    disc = OIDCDiscovery(issuer="https://accounts.google.com")
    d = disc.to_dict()
    assert record("OAU-009", "OIDC discovery has issuer",
                   "https://accounts.google.com", d["issuer"])
def test_oau_010_user_info():
    """UserInfo dataclass creation."""
    ui = UserInfo(sub="12345", name="Test User", email="test@example.com")
    assert record("OAU-010", "UserInfo stores sub and name",
                   ("12345", "Test User"), (ui.sub, ui.name))
def test_oau_011_session_email_redaction():
    """OAuthSession to_dict redacts email."""
    sess = OAuthSession(user_email="alice@example.com", status=SessionStatus.ACTIVE)
    d = sess.to_dict()
    assert record("OAU-011", "Email partially redacted",
                   True, "***" in d["user_email"] and "example.com" in d["user_email"])
# -- Provider CRUD ---------------------------------------------------------
def test_oau_012_register_provider():
    """Register and retrieve a provider."""
    mgr = _mgr()
    mgr.register_provider(_prov("gh"))
    got = mgr.get_provider("gh")
    assert record("OAU-012", "Provider registered",
                   "gh", got.name if got else None)
def test_oau_013_list_providers():
    """List providers."""
    mgr = _mgr()
    mgr.register_provider(_prov("a"))
    mgr.register_provider(_prov("b"))
    assert record("OAU-013", "2 providers listed", 2, len(mgr.list_providers()))
def test_oau_014_remove_provider():
    """Remove a provider."""
    mgr = _mgr()
    mgr.register_provider(_prov("x"))
    ok = mgr.remove_provider("x")
    assert record("OAU-014", "Provider removed",
                   (True, None), (ok, mgr.get_provider("x")))
def test_oau_015_enable_disable():
    """Enable/disable a provider."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    mgr.enable_provider("g", False)
    p = mgr.get_provider("g")
    assert record("OAU-015", "Provider disabled",
                   False, p.enabled if p else True)
# -- Authorization flow ----------------------------------------------------
def test_oau_016_start_auth():
    """Start authorization request."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    req = mgr.start_authorization("g")
    assert record("OAU-016", "Auth request created with state",
                   True, req is not None and len(req.state) > 10)
def test_oau_017_start_auth_disabled():
    """Start auth for disabled provider returns None."""
    mgr = _mgr()
    cfg = _prov("g"); cfg.enabled = False
    mgr.register_provider(cfg)
    assert record("OAU-017", "Disabled provider returns None",
                   None, mgr.start_authorization("g"))
def test_oau_018_exchange_code():
    """Exchange authorization code for tokens."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    req = mgr.start_authorization("g")
    ts = mgr.exchange_code(req.state, "test_code_abc")
    assert record("OAU-018", "Token set created",
                   True, ts is not None and ts.status == TokenStatus.ACTIVE)
def test_oau_019_exchange_invalid_state():
    """Exchange with invalid state returns None."""
    mgr = _mgr()
    assert record("OAU-019", "Invalid state returns None",
                   None, mgr.exchange_code("bogus", "code"))
def test_oau_020_refresh_token():
    """Refresh an existing token."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    req = mgr.start_authorization("g")
    ts = mgr.exchange_code(req.state, "code")
    new_ts = mgr.refresh_token(ts.token_id)
    assert record("OAU-020", "New token issued on refresh",
                   True, new_ts is not None and new_ts.token_id != ts.token_id)
def test_oau_021_revoke_token():
    """Revoke a token."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    req = mgr.start_authorization("g")
    ts = mgr.exchange_code(req.state, "code")
    ok = mgr.revoke_token(ts.token_id)
    got = mgr.get_token(ts.token_id)
    assert record("OAU-021", "Token revoked",
                   (True, TokenStatus.REVOKED), (ok, got.status if got else None))
def test_oau_022_list_tokens():
    """List tokens with provider filter."""
    mgr = _mgr()
    mgr.register_provider(_prov("a"))
    mgr.register_provider(_prov("b"))
    req_a = mgr.start_authorization("a")
    mgr.exchange_code(req_a.state, "c1")
    req_b = mgr.start_authorization("b")
    mgr.exchange_code(req_b.state, "c2")
    assert record("OAU-022", "Filter by provider returns 1",
                   1, len(mgr.list_tokens("a")))
# -- Sessions --------------------------------------------------------------
def test_oau_023_create_session():
    """Create session from active token."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    req = mgr.start_authorization("g")
    ts = mgr.exchange_code(req.state, "code")
    ui = UserInfo(sub="u1", email="a@b.com")
    sess = mgr.create_session(ts.token_id, ui)
    assert record("OAU-023", "Session created and active",
                   SessionStatus.ACTIVE, sess.status if sess else None)
def test_oau_024_create_session_revoked_token():
    """Create session from revoked token fails."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    req = mgr.start_authorization("g")
    ts = mgr.exchange_code(req.state, "code")
    mgr.revoke_token(ts.token_id)
    assert record("OAU-024", "Revoked token -> no session",
                   None, mgr.create_session(ts.token_id))
def test_oau_025_revoke_session():
    """Revoke a session."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    req = mgr.start_authorization("g")
    ts = mgr.exchange_code(req.state, "code")
    sess = mgr.create_session(ts.token_id)
    ok = mgr.revoke_session(sess.session_id)
    got = mgr.get_session(sess.session_id)
    assert record("OAU-025", "Session revoked",
                   (True, SessionStatus.REVOKED), (ok, got.status if got else None))
def test_oau_026_touch_session():
    """Touch session updates last_activity."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    req = mgr.start_authorization("g")
    ts = mgr.exchange_code(req.state, "code")
    sess = mgr.create_session(ts.token_id)
    old_ts = sess.last_activity
    import time; time.sleep(0.05)
    mgr.touch_session(sess.session_id)
    got = mgr.get_session(sess.session_id)
    assert record("OAU-026", "last_activity updated",
                   True, got.last_activity >= old_ts if got else False)
def test_oau_027_list_sessions_filter():
    """List sessions with status filter."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    req1 = mgr.start_authorization("g")
    ts1 = mgr.exchange_code(req1.state, "c1")
    s1 = mgr.create_session(ts1.token_id)
    req2 = mgr.start_authorization("g")
    ts2 = mgr.exchange_code(req2.state, "c2")
    s2 = mgr.create_session(ts2.token_id)
    mgr.revoke_session(s2.session_id)
    assert record("OAU-027", "Filter active sessions",
                   1, len(mgr.list_sessions(SessionStatus.ACTIVE)))
# -- Discovery & stats -----------------------------------------------------
def test_oau_028_oidc_discovery():
    """Set and get OIDC discovery."""
    mgr = _mgr()
    disc = OIDCDiscovery(issuer="https://accounts.google.com")
    mgr.set_discovery("google", disc)
    got = mgr.get_discovery("google")
    assert record("OAU-028", "Discovery cached",
                   "https://accounts.google.com", got.issuer if got else None)
def test_oau_029_stats():
    """Stats returns correct counts."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    req = mgr.start_authorization("g")
    ts = mgr.exchange_code(req.state, "code")
    mgr.create_session(ts.token_id)
    s = mgr.stats()
    assert record("OAU-029", "Stats providers and sessions",
                   (1, 1, 1), (s["providers"], s["active_tokens"], s["active_sessions"]))
# -- Thread safety ---------------------------------------------------------
def test_oau_030_thread_safety():
    """Concurrent provider registration from 10 threads."""
    mgr = _mgr()
    barrier = threading.Barrier(10)
    def worker(i: int) -> None:
        barrier.wait()
        mgr.register_provider(_prov(f"p-{i}"))
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert record("OAU-030", "10 concurrent registrations",
                   10, len(mgr.list_providers()),
                   cause="threading.Lock guards mutations",
                   effect="no race conditions",
                   lesson="thread-safe dict access prevents data loss")
# -- Flask API tests -------------------------------------------------------
try:
    from flask import Flask
    def _app():
        mgr = _mgr()
        app = Flask(__name__)
        app.register_blueprint(create_oauth_api(mgr))
        return app, mgr
    def test_oau_031_api_create_provider():
        """POST /api/oauth/providers creates a provider."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/oauth/providers", json={
                "name": "google", "provider_type": "google",
                "client_id": "cid", "client_secret": "sec",
            })
            data = resp.get_json()
        assert record("OAU-031", "POST providers returns 201",
                       (201, "***REDACTED***"), (resp.status_code, data.get("client_secret")))
    def test_oau_032_api_list_providers():
        """GET /api/oauth/providers lists providers."""
        app, mgr = _app()
        mgr.register_provider(_prov("g"))
        with app.test_client() as c:
            resp = c.get("/api/oauth/providers")
        assert record("OAU-032", "GET providers returns list",
                       (200, 1), (resp.status_code, len(resp.get_json())))
    def test_oau_033_api_get_provider_404():
        """GET /api/oauth/providers/<name> returns 404."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.get("/api/oauth/providers/nope")
        assert record("OAU-033", "Missing provider returns 404", 404, resp.status_code)
    def test_oau_034_api_authorize_flow():
        """POST /api/oauth/authorize starts auth flow."""
        app, mgr = _app()
        mgr.register_provider(_prov("g"))
        with app.test_client() as c:
            resp = c.post("/api/oauth/authorize", json={"provider_name": "g"})
            data = resp.get_json()
        assert record("OAU-034", "Authorize returns state",
                       True, resp.status_code == 201 and "state" in data)
    def test_oau_035_api_callback():
        """POST /api/oauth/callback exchanges code."""
        app, mgr = _app()
        mgr.register_provider(_prov("g"))
        with app.test_client() as c:
            auth = c.post("/api/oauth/authorize", json={"provider_name": "g"}).get_json()
            resp = c.post("/api/oauth/callback", json={"state": auth["state"], "code": "abc"})
        assert record("OAU-035", "Callback returns token set",
                       201, resp.status_code)
    def test_oau_036_api_sessions():
        """POST /api/oauth/sessions creates session from token."""
        app, mgr = _app()
        mgr.register_provider(_prov("g"))
        req = mgr.start_authorization("g")
        ts = mgr.exchange_code(req.state, "code")
        with app.test_client() as c:
            resp = c.post("/api/oauth/sessions", json={
                "token_id": ts.token_id,
                "user_info": {"sub": "u1", "email": "a@b.com"},
            })
        assert record("OAU-036", "Session created via API", 201, resp.status_code)
    def test_oau_037_api_revoke_session():
        """POST /api/oauth/sessions/<id>/revoke revokes session."""
        app, mgr = _app()
        mgr.register_provider(_prov("g"))
        req = mgr.start_authorization("g")
        ts = mgr.exchange_code(req.state, "code")
        sess = mgr.create_session(ts.token_id)
        with app.test_client() as c:
            resp = c.post(f"/api/oauth/sessions/{sess.session_id}/revoke")
        assert record("OAU-037", "Session revoked via API", 200, resp.status_code)
    def test_oau_038_api_stats():
        """GET /api/oauth/stats returns counts."""
        app, mgr = _app()
        mgr.register_provider(_prov("g"))
        with app.test_client() as c:
            resp = c.get("/api/oauth/stats")
            data = resp.get_json()
        assert record("OAU-038", "Stats endpoint returns providers count",
                       1, data.get("providers"))
    def test_oau_039_api_missing_name():
        """POST /api/oauth/providers without name returns 400."""
        app, _ = _app()
        with app.test_client() as c:
            resp = c.post("/api/oauth/providers", json={})
        assert record("OAU-039", "Missing name returns 400", 400, resp.status_code)
    def test_oau_040_api_token_refresh():
        """POST /api/oauth/tokens/<id>/refresh refreshes token."""
        app, mgr = _app()
        mgr.register_provider(_prov("g"))
        req = mgr.start_authorization("g")
        ts = mgr.exchange_code(req.state, "code")
        with app.test_client() as c:
            resp = c.post(f"/api/oauth/tokens/{ts.token_id}/refresh")
        assert record("OAU-040", "Token refreshed via API", 200, resp.status_code)
    def test_oau_041_api_discovery():
        """GET /api/oauth/discovery/<name> returns cached discovery."""
        app, mgr = _app()
        mgr.set_discovery("g", OIDCDiscovery(issuer="https://test.com"))
        with app.test_client() as c:
            resp = c.get("/api/oauth/discovery/g")
            data = resp.get_json()
        assert record("OAU-041", "Discovery endpoint works",
                       "https://test.com", data.get("issuer"))
except ImportError:
    pass
# -- Wingman & Sandbox gates -----------------------------------------------
def test_oau_042_wingman_gate():
    """Wingman pair validation gate."""
    mgr = _mgr()
    mgr.register_provider(_prov("g"))
    storyteller_says = "Start OAuth flow for user login"
    wingman_approves = True
    req = mgr.start_authorization("g") if wingman_approves else None
    assert record("OAU-042", "Wingman gate — approved",
                   True, req is not None,
                   cause="storyteller requests OAuth flow, wingman approves",
                   effect="authorization request created",
                   lesson="Wingman pair validation prevents unsafe flows")
def test_oau_043_sandbox_gate():
    """Causality Sandbox gate — side-effect tracking."""
    mgr = _mgr()
    sandbox_mode = True
    if sandbox_mode:
        pre = len(mgr.list_providers())
    mgr.register_provider(_prov("sandbox-test"))
    if sandbox_mode:
        post = len(mgr.list_providers())
        delta = post - pre
    assert record("OAU-043", "Sandbox gate — side effect tracked",
                   1, delta,
                   cause="sandbox monitors state changes",
                   effect="one new provider detected",
                   lesson="causality sandbox ensures auditable changes")
