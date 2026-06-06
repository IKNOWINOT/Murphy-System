"""Lazy-loaded detailed instructions for platform skills.

When the user request relates to one of these topics, activate the
skill to load the full spec. Mirrors Base44's activate_platform_skill.

Specs are kept short and actionable — the goal is just-in-time
context loading, not a documentation dump.
"""
SPECS = {
    "channel-connections": """# Channel Connections

For Telegram: call `setup_telegram_connection` with NO token first to
generate a 1-click bot link. If user already has a bot token, the same
tool surfaces a secure form to paste it.

For WhatsApp/iMessage: route to Murphy's voice_bridge (which already
handles SMS via Twilio).

Channel state lives in `/var/lib/murphy-production/channels.db`.""",

    "connectors": """# Third-Party Connectors

1. Call `get_connectors_info()` to see which connectors are authorized.
2. If not authorized, call `request_oauth_authorization(integration_type, scopes, reason)`.
3. Use `get_connector_token(integration_type)` to inject the token as
   `$<TYPE>_ACCESS_TOKEN` env var.
4. Token refreshes automatically; on 401, call `get_connector_token` again.

Pick MINIMAL scopes for the specific request.""",

    "backend-functions": """# Backend Functions (Deno runtime)

1. Write code to `functions/<name>.ts` via write_file so the user sees it.
2. Call `deploy_backend_function(function_name, code)` — same code.
3. Test with `test_backend_function(function_name, payload)`.

Use for non-LLM external APIs (Stripe, SendGrid). For LLM work,
handle it yourself — don't proxy through a function.""",

    "stripe-payments": """# Stripe Payments

Pattern: Product → Price → Checkout Session.
- Create one Product per offering.
- Each Product can have multiple Prices (one-time, recurring).
- Generate Checkout Sessions per customer for the purchase flow.

For simple commerce, prefer `suggest_payments_installation` first.""",

    "browserbase": """# Browser Automation (Browserbase)

Use `browserbase_navigate` → `browserbase_screenshot` to see pages.
Click with CSS selectors via `browserbase_click`.
Type into focused fields with `browserbase_type`.

Always check `browserbase_get_session` before assuming a live session
exists. Reset with `browserbase_reset_context` if cookies cause issues.""",

    "skills": """# Custom Skills

Create scripts under `.agents/skills/`:
- Flat: `<name>.sh`, `<name>.py`, `<name>.js`
- Directory: `<name>/SKILL.md` + `scripts/run.{sh,py,js}`

Run via `run_skill(skill_name, arguments)`.

Skills are sandboxed in YOUR workspace. Use for repeatable tasks.""",

    "skill-store": """# Skill Store

Before writing code from scratch, call:
  `suggest_skill_installation(query='<topic>')`

Common matches: docx, pdf, excel, email, crm, weather, stock,
calendar. 130+ available. User approves install via a one-click form.""",
}


def get(skill_name: str) -> dict:
    spec = SPECS.get(skill_name)
    if spec is None:
        return {"ok": False, "skill_name": skill_name,
                "error": f"unknown platform skill (valid: {sorted(SPECS)})"}
    return {"ok": True, "skill_name": skill_name, "spec": spec,
            "chars": len(spec)}


def list_available() -> dict:
    return {"ok": True, "skills": [
        {"name": k, "preview": v.split('\n')[1][:80] if '\n' in v else v[:80]}
        for k, v in SPECS.items()
    ]}
