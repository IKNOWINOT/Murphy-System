"""Unit tests for ``src.oidc_verifier`` (ADR-0012 Release N).

Covers:
* JWT happy path (RS256) → ``VerifiedClaims``
* expired / not-yet-valid tokens
* wrong issuer / wrong audience
* unknown ``kid`` triggers a forced JWKS refresh and retries once
* unsupported algorithms (HS256 explicitly rejected — no shared secrets)
* malformed tokens
* discovery-document issuer mismatch
* JWKS cache TTL behaviour (cache hit / refresh)
* the discovery / JWKS-fetch error path raises ``OIDCDiscoveryError``
  so the middleware can surface it as 503 (no silent fallback)

Skip cleanly when ``cryptography`` / ``pyjwt`` are not installed —
matching the existing ``test_aionmind`` sandbox-skip conventions.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

import pytest

pytest.importorskip("jwt")
pytest.importorskip("cryptography")

import jwt as pyjwt  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402

from oidc_verifier import (  # noqa: E402
    JWKS_GRACE_SECONDS,
    JWKS_TTL_SECONDS,
    OIDCDiscoveryError,
    OIDCTokenError,
    OIDCVerifier,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


def _new_keypair() -> Tuple[Any, Dict[str, Any]]:
    """Return an RSA private key + the JWK form of its public counterpart."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key()
    public_pem = public.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    # Build the JWK from the public key.
    jwk = pyjwt.algorithms.RSAAlgorithm.to_jwk(
        pyjwt.algorithms.RSAAlgorithm.from_jwk(
            pyjwt.algorithms.RSAAlgorithm.to_jwk(
                serialization.load_pem_public_key(public_pem)
            )
        ),
        as_dict=True,
    )
    return private, jwk


def _sign(
    private,
    *,
    iss: str,
    aud: str,
    sub: str,
    kid: str = "kid-1",
    exp_offset: int = 300,
    nbf_offset: int = -10,
    extra: Dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    payload: Dict[str, Any] = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "iat": now,
        "nbf": now + nbf_offset,
        "exp": now + exp_offset,
    }
    if extra:
        payload.update(extra)
    return pyjwt.encode(payload, private, algorithm="RS256", headers={"kid": kid})


class _FakeHttp:
    """Records every (url, headers) pair, returns scripted responses."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Dict[str, str]]] = []
        self._responses: Dict[str, Tuple[int, Dict[str, Any]]] = {}
        self._fail: Dict[str, Exception] = {}

    def stub(self, url: str, status: int, body: Dict[str, Any]) -> None:
        self._responses[url] = (status, body)

    def fail(self, url: str, exc: Exception) -> None:
        self._fail[url] = exc

    def __call__(self, url: str, headers: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
        self.calls.append((url, dict(headers)))
        if url in self._fail:
            raise self._fail[url]
        if url not in self._responses:
            raise AssertionError(f"unexpected GET {url}")
        return self._responses[url]


@pytest.fixture
def keypair():
    return _new_keypair()


@pytest.fixture
def issuer():
    return "https://issuer.example.com"


@pytest.fixture
def audience():
    return "client-abc"


@pytest.fixture
def http(issuer, keypair):
    _, jwk = keypair
    jwk_with_kid = dict(jwk)
    jwk_with_kid["kid"] = "kid-1"
    jwk_with_kid["alg"] = "RS256"
    h = _FakeHttp()
    h.stub(
        f"{issuer}/.well-known/openid-configuration",
        200,
        {"issuer": issuer, "jwks_uri": f"{issuer}/jwks"},
    )
    h.stub(f"{issuer}/jwks", 200, {"keys": [jwk_with_kid]})
    return h


@pytest.fixture
def verifier(issuer, audience, http):
    return OIDCVerifier(
        issuer=issuer,
        audience=audience,
        http_get=http,
    )


# ── Happy path & claim validation ──────────────────────────────────────────


class TestHappyPath:
    def test_valid_jwt_returns_claims(self, verifier, keypair, issuer, audience):
        private, _ = keypair
        token = _sign(
            private, iss=issuer, aud=audience, sub="user-1",
            extra={"tenant": "acme"},
        )
        out = verifier.verify(token)
        assert out.sub == "user-1"
        assert out.tenant == "acme"
        assert out.issuer == issuer
        assert out.audience == audience

    def test_tenant_claim_defaults_to_empty_when_missing(self, verifier, keypair, issuer, audience):
        private, _ = keypair
        token = _sign(private, iss=issuer, aud=audience, sub="user-1")
        out = verifier.verify(token)
        assert out.tenant == ""

    def test_tenant_claim_name_is_configurable(self, issuer, audience, http, keypair):
        private, _ = keypair
        v = OIDCVerifier(
            issuer=issuer, audience=audience, http_get=http,
            tenant_claim="org_id",
        )
        token = _sign(
            private, iss=issuer, aud=audience, sub="u",
            extra={"org_id": "org-42"},
        )
        assert v.verify(token).tenant == "org-42"


class TestRejection:
    def test_expired_token(self, verifier, keypair, issuer, audience):
        private, _ = keypair
        token = _sign(private, iss=issuer, aud=audience, sub="u", exp_offset=-100)
        with pytest.raises(OIDCTokenError) as ei:
            verifier.verify(token)
        assert ei.value.reason == "expired"

    def test_not_yet_valid_token(self, verifier, keypair, issuer, audience):
        private, _ = keypair
        # nbf 5 minutes in the future, well outside the 30s leeway
        token = _sign(private, iss=issuer, aud=audience, sub="u", nbf_offset=300)
        with pytest.raises(OIDCTokenError) as ei:
            verifier.verify(token)
        assert ei.value.reason == "not_yet_valid"

    def test_wrong_issuer(self, verifier, keypair, audience):
        private, _ = keypair
        token = _sign(private, iss="https://other.example", aud=audience, sub="u")
        with pytest.raises(OIDCTokenError) as ei:
            verifier.verify(token)
        assert ei.value.reason == "wrong_issuer"

    def test_wrong_audience(self, verifier, keypair, issuer):
        private, _ = keypair
        token = _sign(private, iss=issuer, aud="other-client", sub="u")
        with pytest.raises(OIDCTokenError) as ei:
            verifier.verify(token)
        assert ei.value.reason == "wrong_audience"

    def test_malformed_token(self, verifier):
        with pytest.raises(OIDCTokenError) as ei:
            verifier.verify("not.a.jwt.at.all")
        assert ei.value.reason == "malformed"

    def test_hs256_token_rejected_as_unsupported_algorithm(self, verifier, issuer, audience):
        # The verifier MUST refuse symmetric algorithms because the
        # whole point of ADR-0012 is to remove shared secrets.
        bad = pyjwt.encode(
            {"iss": issuer, "aud": audience, "sub": "u",
             "iat": int(time.time()), "exp": int(time.time()) + 60},
            "shared-secret",
            algorithm="HS256",
            headers={"kid": "kid-1"},
        )
        with pytest.raises(OIDCTokenError) as ei:
            verifier.verify(bad)
        assert ei.value.reason == "unsupported_algorithm"


# ── JWKS cache + kid-miss refresh ──────────────────────────────────────────


class TestJWKSRefresh:
    def test_unknown_kid_triggers_one_refresh_then_succeeds(
        self, issuer, audience, keypair
    ):
        """A token signed with a kid the cache doesn't yet know about
        must trigger exactly one extra JWKS GET, after which verification
        succeeds with the freshly-fetched key.
        """
        private, jwk = keypair
        # Initial JWKS only knows kid-1; the token will use kid-2.
        first_jwk = dict(jwk)
        first_jwk["kid"] = "kid-1"
        first_jwk["alg"] = "RS256"
        rotated_jwk = dict(jwk)
        rotated_jwk["kid"] = "kid-2"
        rotated_jwk["alg"] = "RS256"

        # The fake http returns the rotated key list on the second
        # call to /jwks (simulating the IdP rotating keys).
        responses = [
            {"keys": [first_jwk]},
            {"keys": [rotated_jwk]},
        ]

        class RotatingHttp:
            def __init__(self):
                self.calls = []
            def __call__(self, url, headers):
                self.calls.append(url)
                if url.endswith("openid-configuration"):
                    return (200, {"issuer": issuer, "jwks_uri": f"{issuer}/jwks"})
                if url.endswith("/jwks"):
                    body = responses.pop(0) if responses else {"keys": [rotated_jwk]}
                    return (200, body)
                raise AssertionError(url)

        http = RotatingHttp()
        v = OIDCVerifier(issuer=issuer, audience=audience, http_get=http)
        token = _sign(private, iss=issuer, aud=audience, sub="u", kid="kid-2")
        out = v.verify(token)
        assert out.sub == "u"
        # Exactly: discovery + initial JWKS + one forced refresh = 3 calls.
        assert sum(1 for u in http.calls if u.endswith("/jwks")) == 2

    def test_unknown_kid_after_refresh_still_fails(self, verifier, keypair, issuer, audience):
        private, _ = keypair
        token = _sign(private, iss=issuer, aud=audience, sub="u", kid="kid-99")
        with pytest.raises(OIDCTokenError) as ei:
            verifier.verify(token)
        assert ei.value.reason == "unknown_kid"

    def test_jwks_cached_on_repeat_verify(self, verifier, http, keypair, issuer, audience):
        private, _ = keypair
        for _ in range(5):
            verifier.verify(
                _sign(private, iss=issuer, aud=audience, sub="u")
            )
        # discovery + 1 JWKS == 2 GETs total, regardless of verify count.
        urls = [u for u, _ in http.calls]
        assert urls.count(f"{issuer}/jwks") == 1
        assert urls.count(f"{issuer}/.well-known/openid-configuration") == 1


# ── Discovery / transport errors ───────────────────────────────────────────


class TestDiscoveryErrors:
    @staticmethod
    def _well_formed_token():
        # Any RS256-signed JWT will do — the verifier reaches the
        # JWKS path before it gets to signature checking.
        priv, _ = _new_keypair()
        return _sign(priv, iss="https://x", aud="y", sub="u")

    def test_discovery_failure_raises_OIDCDiscoveryError(self, issuer, audience):
        h = _FakeHttp()
        h.fail(
            f"{issuer}/.well-known/openid-configuration",
            ConnectionError("boom"),
        )
        v = OIDCVerifier(issuer=issuer, audience=audience, http_get=h)
        with pytest.raises(OIDCDiscoveryError):
            v.verify(self._well_formed_token())

    def test_discovery_issuer_mismatch_rejected(self, issuer, audience, keypair):
        _, jwk = keypair
        jwk = dict(jwk); jwk["kid"] = "kid-1"; jwk["alg"] = "RS256"
        h = _FakeHttp()
        h.stub(
            f"{issuer}/.well-known/openid-configuration",
            200,
            {"issuer": "https://imposter.example", "jwks_uri": f"{issuer}/jwks"},
        )
        h.stub(f"{issuer}/jwks", 200, {"keys": [jwk]})
        v = OIDCVerifier(issuer=issuer, audience=audience, http_get=h)
        with pytest.raises(OIDCDiscoveryError):
            v.verify(self._well_formed_token())

    def test_jwks_fetch_non_200_raises(self, issuer, audience):
        h = _FakeHttp()
        h.stub(
            f"{issuer}/.well-known/openid-configuration",
            200,
            {"issuer": issuer, "jwks_uri": f"{issuer}/jwks"},
        )
        h.stub(f"{issuer}/jwks", 503, {"error": "down"})
        v = OIDCVerifier(issuer=issuer, audience=audience, http_get=h)
        with pytest.raises(OIDCDiscoveryError):
            v.verify(self._well_formed_token())


# ── Sanity ─────────────────────────────────────────────────────────────────


class TestConfig:
    def test_missing_issuer_rejected_at_construction(self, audience):
        with pytest.raises(Exception):
            OIDCVerifier(issuer="", audience=audience)

    def test_missing_audience_rejected_at_construction(self, issuer):
        with pytest.raises(Exception):
            OIDCVerifier(issuer=issuer, audience="")

    def test_jwks_ttl_constants_match_adr(self):
        # ADR-0012 §"Provider configuration": 1 h cache, 5 m grace.
        assert JWKS_TTL_SECONDS == 60 * 60
        assert JWKS_GRACE_SECONDS == 5 * 60
