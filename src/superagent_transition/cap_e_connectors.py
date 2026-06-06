"""Caps E.1 + E.2 + E.3 — OAuth / connector unified surface.

Wraps Murphy's 32 connectors (integrations/*_connector.py) all
inheriting from BaseIntegrationConnector. Discovers them at import
time so the registry stays in sync with the codebase.

Murphy's connector pattern is env-var based (not OAuth flow). So:
  - E.1 request_oauth_authorization → returns setup instructions
        + credential keys needed (links to SETUP_URL)
  - E.2 get_connectors_info → discovery + configured status
  - E.3 get_connector_token → inject credentials into env or
        returns the credential dict for the integration

Discovery cached at module level; refresh available.
"""
from __future__ import annotations
import importlib
import inspect
import os
import pkgutil
import threading
from typing import Any, Dict, List, Optional

_CACHE: Dict[str, Any] = {"connectors": None, "ts": 0.0}
_CACHE_LOCK = threading.Lock()


def _discover() -> List[Dict[str, Any]]:
    """Walk integrations/ and collect all BaseIntegrationConnector subclasses."""
    from integrations.base_connector import BaseIntegrationConnector
    import integrations as pkg

    found: List[Dict[str, Any]] = []
    for _, modname, _ in pkgutil.iter_modules(pkg.__path__):
        if modname == "base_connector" or not modname.endswith("_connector"):
            continue
        try:
            mod = importlib.import_module(f"integrations.{modname}")
        except Exception:
            continue
        for cls_name, cls in inspect.getmembers(mod, inspect.isclass):
            if cls is BaseIntegrationConnector: continue
            if not issubclass(cls, BaseIntegrationConnector): continue
            if cls.__module__ != mod.__name__: continue
            integration_type = modname.replace("_connector", "")
            found.append({
                "integration_type": integration_type,
                "module": f"integrations.{modname}",
                "class": cls.__name__,
                "integration_name": getattr(cls, "INTEGRATION_NAME", "?"),
                "base_url": getattr(cls, "BASE_URL", ""),
                "credentials_all": list(getattr(cls, "CREDENTIAL_KEYS", []) or []),
                "credentials_required": list(getattr(cls, "REQUIRED_CREDENTIALS", []) or []),
                "free_tier": bool(getattr(cls, "FREE_TIER", False)),
                "setup_url": getattr(cls, "SETUP_URL", ""),
                "documentation_url": getattr(cls, "DOCUMENTATION_URL", ""),
            })
    found.sort(key=lambda c: c["integration_type"])
    return found


def _get_all(refresh: bool = False) -> List[Dict[str, Any]]:
    with _CACHE_LOCK:
        if not refresh and _CACHE["connectors"] is not None:
            return _CACHE["connectors"]
        _CACHE["connectors"] = _discover()
        import time
        _CACHE["ts"] = time.time()
        return _CACHE["connectors"]


def _is_authorized(c: Dict[str, Any]) -> bool:
    """A connector is authorized if all REQUIRED_CREDENTIALS env vars are set."""
    req = c.get("credentials_required") or []
    if not req:
        return True  # no credentials needed
    return all(os.environ.get(k) for k in req)


# ── E.2  get_connectors_info ──────────────────────────────────────────────

def get_connectors_info(integration_types: Optional[List[str]] = None,
                        refresh: bool = False) -> Dict[str, Any]:
    """List authorized connectors (no args), or details for specific types."""
    out: Dict[str, Any] = {"ok": False, "error": None}
    try:
        all_connectors = _get_all(refresh=refresh)
        by_type = {c["integration_type"]: c for c in all_connectors}

        if not integration_types:
            # No filter — return summary of authorized + total
            authorized = [c["integration_type"] for c in all_connectors if _is_authorized(c)]
            unauthorized = [c["integration_type"] for c in all_connectors if not _is_authorized(c)]
            out["total"] = len(all_connectors)
            out["authorized"] = authorized
            out["authorized_count"] = len(authorized)
            out["unauthorized"] = unauthorized
            out["unauthorized_count"] = len(unauthorized)
            out["ok"] = True
            return out

        # Detailed info for requested types
        details: List[Dict[str, Any]] = []
        unknown: List[str] = []
        for t in integration_types:
            t = t.lower().strip()
            c = by_type.get(t)
            if not c:
                unknown.append(t); continue
            detail = dict(c)
            detail["authorized"] = _is_authorized(c)
            detail["missing_credentials"] = [
                k for k in c["credentials_required"] if not os.environ.get(k)
            ]
            details.append(detail)
        out["connectors"] = details
        out["count"] = len(details)
        if unknown:
            out["unknown_types"] = unknown
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── E.1  request_oauth_authorization ──────────────────────────────────────

def request_oauth_authorization(reason: str,
                                integration_type: Optional[str] = None,
                                scopes: Optional[List[str]] = None,
                                connector_id: Optional[str] = None) -> Dict[str, Any]:
    """Build an authorization request payload with setup instructions.

    Murphy uses env-var credentials (not OAuth flow), so this returns
    structured 'what user needs to provide' instructions rather than a
    redirect URL.
    """
    out: Dict[str, Any] = {"ok": False, "error": None}
    try:
        if not reason or not reason.strip():
            out["error"] = "reason required (user-facing explanation)"; return out
        if not integration_type and not connector_id:
            out["error"] = "must provide integration_type OR connector_id"; return out
        if integration_type and connector_id:
            out["error"] = "provide only one of integration_type/connector_id"; return out

        target_type = (integration_type or connector_id).lower().strip()
        all_connectors = _get_all()
        c = next((x for x in all_connectors if x["integration_type"] == target_type), None)
        if not c:
            out["error"] = f"unknown integration: {target_type}"
            out["available_types"] = [x["integration_type"] for x in all_connectors[:30]]
            return out

        already = _is_authorized(c)
        out["integration_type"] = target_type
        out["integration_name"] = c["integration_name"]
        out["reason"] = reason
        out["already_authorized"] = already
        out["mode"] = "env_var" if c["credentials_required"] else "no_credentials"
        out["credentials_needed"] = c["credentials_required"]
        out["missing_credentials"] = [
            k for k in c["credentials_required"] if not os.environ.get(k)
        ]
        out["setup_url"] = c["setup_url"]
        out["documentation_url"] = c["documentation_url"]
        out["scopes"] = scopes or []
        if not already:
            out["next_step"] = (
                "Add the missing credential(s) to /etc/murphy-production/secrets.env "
                f"(needs: {', '.join(out['missing_credentials'])}). "
                f"Get them from: {c['setup_url'] or c['documentation_url'] or '(no URL on file)'}"
            )
        else:
            out["next_step"] = "Connector is already authorized — proceed to use it."
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── E.3  get_connector_token ──────────────────────────────────────────────

def get_connector_token(integration_type: str,
                        *, reveal: bool = False) -> Dict[str, Any]:
    """Return credentials for a connector. By default, returns
    credential-key presence only (NOT the secret values) to avoid
    accidental leaks. reveal=True returns the actual values for
    in-process use (e.g., env-var injection)."""
    out: Dict[str, Any] = {"ok": False, "error": None}
    try:
        if not integration_type:
            out["error"] = "integration_type required"; return out
        target = integration_type.lower().strip()
        all_connectors = _get_all()
        c = next((x for x in all_connectors if x["integration_type"] == target), None)
        if not c:
            out["error"] = f"unknown integration: {target}"; return out

        keys = c["credentials_all"] or c["credentials_required"]
        if not keys:
            out["mode"] = "no_credentials_needed"
            out["integration_type"] = target
            out["ok"] = True
            return out

        present: Dict[str, Any] = {}
        for k in keys:
            v = os.environ.get(k, "")
            if reveal:
                present[k] = v
            else:
                present[k] = {"set": bool(v), "length": len(v) if v else 0}

        missing = [k for k in c["credentials_required"] if not os.environ.get(k)]
        out["integration_type"] = target
        out["credentials"] = present
        out["missing_required"] = missing
        out["fully_authorized"] = (not missing)
        out["mode"] = "revealed" if reveal else "presence_only"
        if reveal:
            out["warning"] = "credentials returned in plaintext — use only for in-process injection"
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── Executor wrappers ─────────────────────────────────────────────────────

def execute_request_oauth_authorization(**kwargs) -> Dict[str, Any]:
    return request_oauth_authorization(
        reason=kwargs.get("reason", ""),
        integration_type=kwargs.get("integration_type"),
        connector_id=kwargs.get("connector_id"),
        scopes=kwargs.get("scopes"),
    )

def execute_get_connectors_info(**kwargs) -> Dict[str, Any]:
    return get_connectors_info(
        integration_types=kwargs.get("integration_types"),
        refresh=bool(kwargs.get("refresh", False)),
    )

def execute_get_connector_token(**kwargs) -> Dict[str, Any]:
    return get_connector_token(
        integration_type=kwargs.get("integration_type", ""),
        reveal=bool(kwargs.get("reveal", False)),
    )
