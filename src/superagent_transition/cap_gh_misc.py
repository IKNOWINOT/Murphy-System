"""Caps G.1 + H.1 + H.2 + H.4 + H.5 — payments hint, secrets,
feedback, channels, credits.

Five caps in one file. All reuse existing Murphy infra:

  G.1  suggest_payments_installation — choose wix/stripe by use case
  H.1  set_secrets                   — register secret schema + .env append
  H.2  vent_send_feedback            — JSONL queue at /var/lib/.../feedback
  H.4  setup_telegram_connection     — wraps integrations/telegram_connector
  H.5  get_credit_usage              — wraps llm_cost_ledger.today_summary

H.6/H.7/H.8 are SOUL behaviors and ship as Standing Decisions 61/62/63,
not code.
"""
from __future__ import annotations
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ENV_FILE = "/etc/murphy-production/secrets.env"
FEEDBACK_DIR = Path("/var/lib/murphy-production/feedback")
SECRET_REGISTRY = Path("/var/lib/murphy-production/secret_registry.json")

# ── G.1 suggest_payments_installation ─────────────────────────────────────

WIX_BLOCKED_CATEGORIES = {
    "adult", "weapons", "drugs", "gambling", "cryptocurrency",
    "counterfeit", "get_rich_quick", "fake_ids", "hate_speech",
}
WIX_UNAVAILABLE_COUNTRIES = {"IL", "Israel", "israel"}


def suggest_payments_installation(
    reason: str,
    *,
    category: Optional[str] = None,
    country: Optional[str] = None,
    explicit_stripe: bool = False,
) -> Dict[str, Any]:
    """Pick wix_payments / stripe / payments_by_wix based on context."""
    out: Dict[str, Any] = {"ok": False, "error": None}
    try:
        if not reason or not reason.strip():
            out["error"] = "reason is required (what the user wants to do)"
            return out
        cat = (category or "").lower().strip()
        # Detect blocked categories from text
        blocked_hit = next((c for c in WIX_BLOCKED_CATEGORIES if c in reason.lower()), None)
        if explicit_stripe:
            provider = "stripe"
            decision = "User explicitly requested Stripe."
        elif blocked_hit or cat in WIX_BLOCKED_CATEGORIES:
            provider = "stripe"
            decision = f"Wix prohibits category '{blocked_hit or cat}', using Stripe instead."
        elif country and country.strip() in WIX_UNAVAILABLE_COUNTRIES:
            provider = "payments_by_wix"
            decision = f"Wix Payments unavailable in {country}; using Payments by Wix."
        else:
            provider = "wix_payments"
            decision = "Standard commerce/subscription — Wix Payments is the default."

        out["provider"] = provider
        out["provider_decision_reason"] = decision
        out["reason"] = reason
        out["existing_murphy_integrations"] = ["stripe_connector", "nowpayments_billing"]
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── H.1 set_secrets ───────────────────────────────────────────────────────

SECRET_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def _read_env_keys() -> Dict[str, str]:
    """Read current /etc/murphy-production/secrets.env keys (NOT values)."""
    keys: Dict[str, str] = {}
    if not os.path.exists(ENV_FILE):
        return keys
    try:
        with open(ENV_FILE) as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith("#") or "=" not in ln:
                    continue
                k = ln.split("=", 1)[0].strip()
                if k: keys[k] = "(set)"
    except PermissionError:
        return {"_error": "cannot read secrets.env"}
    return keys


def _read_secret_registry() -> List[Dict[str, Any]]:
    if SECRET_REGISTRY.exists():
        try:
            return json.loads(SECRET_REGISTRY.read_text())
        except Exception:
            return []
    return []


def _write_secret_registry(entries: List[Dict[str, Any]]) -> None:
    SECRET_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    SECRET_REGISTRY.write_text(json.dumps(entries, indent=2))


def set_secrets(secrets_schema: List[Dict[str, str]]) -> Dict[str, Any]:
    """Register secret schemas. Does NOT capture values — prompts user
    via separate secure form (Murphy convention)."""
    out: Dict[str, Any] = {"ok": False, "registered": [], "already_set": [],
                            "form_required": [], "error": None}
    try:
        if not isinstance(secrets_schema, list):
            out["error"] = "secrets_schema must be a list of {secretName, description}"
            return out
        if not secrets_schema:
            out["error"] = "empty secrets_schema"; return out

        existing_keys = _read_env_keys()
        registry = _read_secret_registry()
        registered_names = {e["secretName"] for e in registry}

        for entry in secrets_schema:
            if not isinstance(entry, dict):
                out["error"] = "each schema entry must be a dict"; return out
            name = (entry.get("secretName") or "").strip()
            desc = (entry.get("description") or "").strip()
            if not SECRET_NAME_RE.match(name):
                out["error"] = f"invalid secretName: {name!r} (UPPER_SNAKE_CASE only)"
                return out
            if not desc:
                out["error"] = f"description required for {name}"; return out

            is_set = name in existing_keys
            if is_set:
                out["already_set"].append(name)
            else:
                out["form_required"].append({"name": name, "description": desc})

            # Append to registry if new
            if name not in registered_names:
                registry.append({
                    "secretName": name, "description": desc,
                    "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                    "currently_set": is_set,
                })
                out["registered"].append(name)
        _write_secret_registry(registry)
        out["env_file"] = ENV_FILE
        out["registry_file"] = str(SECRET_REGISTRY)
        out["form_url_hint"] = "Murphy will present a secure form to the user for missing secrets"
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── H.2 vent_send_feedback ────────────────────────────────────────────────

def vent_send_feedback(summary: str, details: str,
                       *, suggested_fix: Optional[str] = None) -> Dict[str, Any]:
    """Append a structured feedback entry to the JSONL queue."""
    out: Dict[str, Any] = {"ok": False, "error": None}
    try:
        if not summary or not summary.strip():
            out["error"] = "summary required"; return out
        if len(summary) > 120:
            out["error"] = f"summary too long ({len(summary)} > 120 chars)"; return out
        if not details or not details.strip():
            out["error"] = "details required"; return out

        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        log_file = FEEDBACK_DIR / "feedback.jsonl"
        entry = {
            "id": str(uuid.uuid4())[:12],
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
            "summary": summary.strip(),
            "details": details.strip(),
            "suggested_fix": (suggested_fix or "").strip() or None,
            "source": "superagent",
        }
        with log_file.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        out["feedback_id"] = entry["id"]
        out["log_file"] = str(log_file)
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def list_feedback(*, limit: int = 20) -> Dict[str, Any]:
    """Bonus: read recent feedback entries."""
    out: Dict[str, Any] = {"ok": False, "entries": [], "error": None}
    try:
        log_file = FEEDBACK_DIR / "feedback.jsonl"
        if not log_file.exists():
            out["ok"] = True; out["count"] = 0; return out
        entries: List[Dict[str, Any]] = []
        with log_file.open() as f:
            for line in f:
                try: entries.append(json.loads(line))
                except Exception: continue
        entries = entries[-limit:][::-1]
        out["entries"] = entries
        out["count"] = len(entries)
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── H.4 setup_telegram_connection ─────────────────────────────────────────

def setup_telegram_connection(bot_token: Optional[str] = None) -> Dict[str, Any]:
    """Set up Telegram bot. Without token → generates 1-click bot
    creation link. With token → registers it."""
    out: Dict[str, Any] = {"ok": False, "error": None}
    try:
        if bot_token:
            # Validate basic shape (Telegram tokens: <id>:<35 chars>)
            if not re.match(r"^\d+:[A-Za-z0-9_-]{30,}$", bot_token.strip()):
                out["error"] = "bot_token doesn't match Telegram format <id>:<35chars>"
                return out
            # Register schema (don't store the value here; H.1 handles vault)
            r = set_secrets([{
                "secretName": "TELEGRAM_BOT_TOKEN",
                "description": "Telegram bot token from @BotFather",
            }])
            out["mode"] = "token_registration"
            out["secret_registration"] = r
            out["next_step"] = "Token must be added to /etc/murphy-production/secrets.env"
            out["ok"] = True
            return out
        else:
            # Generate 1-click bot creation link
            out["mode"] = "bot_creation_link"
            out["botfather_url"] = "https://t.me/BotFather"
            out["instructions"] = [
                "1. Open https://t.me/BotFather in Telegram",
                "2. Send /newbot, follow prompts to name your bot",
                "3. Copy the token BotFather sends back",
                "4. Call setup_telegram_connection(bot_token='YOUR_TOKEN_HERE')",
            ]
            out["existing_murphy_integration"] = "src/integrations/telegram_connector.py"
            out["ok"] = True
            return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── H.5 get_credit_usage ──────────────────────────────────────────────────

def get_credit_usage(*, include_models: bool = False,
                     include_recent: bool = False) -> Dict[str, Any]:
    """Wrap llm_cost_ledger to expose credit/spend awareness."""
    out: Dict[str, Any] = {"ok": False, "error": None}
    try:
        from llm_cost_ledger import _get_ledger
        ld = _get_ledger()
        summary = ld.today_summary()
        out["today"] = summary.get("today", {})
        out["all_time"] = summary.get("all_time", {})
        if include_models:
            try:
                out["model_breakdown"] = ld.model_breakdown()
            except Exception as e:
                out["model_breakdown_error"] = str(e)
        if include_recent:
            try:
                rc = ld.recent_calls()
                out["recent_calls"] = rc[:10] if rc else []
            except Exception as e:
                out["recent_calls_error"] = str(e)
        # Spend pace heuristic
        today_cost = out["today"].get("total_cost_usd", 0) or 0
        all_time_cost = out["all_time"].get("total_cost_usd", 0) or 0
        out["alerts"] = []
        if today_cost > 5:
            out["alerts"].append(f"high daily spend: ${today_cost:.2f}")
        if all_time_cost > 100:
            out["alerts"].append(f"all-time spend exceeds $100: ${all_time_cost:.2f}")
        out["ok"] = True
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── Executor wrappers ─────────────────────────────────────────────────────

def execute_suggest_payments_installation(**kwargs) -> Dict[str, Any]:
    return suggest_payments_installation(
        reason=kwargs.get("reason", ""),
        category=kwargs.get("category"),
        country=kwargs.get("country"),
        explicit_stripe=bool(kwargs.get("explicit_stripe", False)),
    )

def execute_set_secrets(**kwargs) -> Dict[str, Any]:
    return set_secrets(secrets_schema=kwargs.get("secrets_schema") or [])

def execute_vent_send_feedback(**kwargs) -> Dict[str, Any]:
    return vent_send_feedback(
        summary=kwargs.get("summary", ""),
        details=kwargs.get("details", ""),
        suggested_fix=kwargs.get("suggested_fix"),
    )

def execute_list_feedback(**kwargs) -> Dict[str, Any]:
    return list_feedback(limit=int(kwargs.get("limit", 20)))

def execute_setup_telegram_connection(**kwargs) -> Dict[str, Any]:
    return setup_telegram_connection(bot_token=kwargs.get("bot_token"))

def execute_get_credit_usage(**kwargs) -> Dict[str, Any]:
    return get_credit_usage(
        include_models=bool(kwargs.get("include_models", False)),
        include_recent=bool(kwargs.get("include_recent", False)),
    )
