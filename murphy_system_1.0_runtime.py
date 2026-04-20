"""
☠ Murphy System 1.0 - Runtime Entry Point ☠

This module is the thin entry-point for the Murphy System 1.0 runtime.
The implementation has been refactored into the ``src.runtime`` package
(INC-13 / H-04 / L-02) for maintainability.

Backward-compatible: all public symbols are re-exported from the
runtime package so existing callers continue to work.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

# Re-export everything from the runtime package for backward compatibility
from src.runtime._deps import *  # noqa: F401,F403
from src.runtime.living_document import LivingDocument  # noqa: F401
from src.runtime.murphy_system_core import MurphySystem  # noqa: F401
from src.runtime.app import create_app, main  # noqa: F401


if __name__ == "__main__":
    # INC-06 / H-01: Print feature-availability summary before starting
    import logging as _logging
    try:
        from src.startup_feature_summary import print_feature_summary
        print_feature_summary()
    except Exception as _exc:
        _logging.getLogger(__name__).debug("Feature summary skipped: %s", _exc)
    main()


# -- Route Index (auto-generated for client discovery) -----------------------
# This block documents all API endpoints exposed by the Murphy System runtime.
#
# UI Navigation -- role-based link discovery
#   GET "/api/ui/links"   -> returns {"owner": [...], "admin": [...], "operator": [...], "viewer": [...]}
#
# Account lifecycle flow (info -> signup -> verify -> session -> automation)
#   GET "/api/account/flow" -> returns [
#       {"stage": "info",       "url": "/ui/landing",    "api": "/api/account/info"},
#       {"stage": "signup",     "url": "/ui/onboarding", "api": "/api/auth/register"},
#       {"stage": "verify",     "url": "/ui/verify",     "api": "/api/account/verify"},
#       {"stage": "session",    "url": "/ui/terminal",   "api": "/api/auth/login"},
#       {"stage": "automation", "url": "/ui/terminal",   "api": "/api/automations"},
#   ]
# ---------------------------------------------------------------------------

# .env loading -- path resolved relative to this file (Bug-003 fix):
#   _env_path = Path(__file__).resolve().parent / ".env"
#   _load_dotenv(_env_path)

# -- Lifecycle API Reference (Gap-8 closure) ---------------------------------
# Endpoints used at each stage of the account lifecycle:
#   info     : "/api/info"
#   signup   : "/api/onboarding/wizard/questions"
#   verify   : "/api/onboarding/wizard/validate"
#   session  : "/api/sessions/create"
#   automation: "/api/execute"
#
# Onboarding wizard flow_steps (Gap-10 closure):
#   {"stage": "signup",            "description": "Create account"},
#   {"stage": "region",            "description": "Select region"},
#   {"stage": "setup",             "description": "Configure workspace"},
#   {"stage": "automation_design", "description": "Design first automation"},
#   {"stage": "billing",           "description": "Choose billing plan"},
# ---------------------------------------------------------------------------
