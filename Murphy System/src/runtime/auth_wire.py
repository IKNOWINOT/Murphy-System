# src/runtime/auth_wire.py
# PATCH-274-wire: Hot-patches _load_prod_accounts_from_db and _persist_prod_account
# in the running MPS process to use auth_persist (no import-cache problem).
import logging
import sys

log = logging.getLogger(__name__)
_MOD_NAME = "src.runtime.auth"

def install_persistence_hooks(mps_module=None):
    try:
        from src.runtime import auth_persist as _ap
    except Exception as exc:
        log.error("auth_wire: cannot import auth_persist: %s", exc)
        return False
    target = mps_module
    if target is None:
        for name, mod in sys.modules.items():
            if mod and hasattr(mod, "_prod_user_store") and hasattr(mod, "_prod_email_to_account"):
                target = mod
                break
    if target is None:
        log.warning("auth_wire: could not find MPS module in sys.modules")
        return False
    _prod_user_store = getattr(target, "_prod_user_store", {})
    _prod_email_to_account = getattr(target, "_prod_email_to_account", {})

    def _load_prod_accounts_from_db_patched():
        accounts = _ap.load_all_accounts()
        loaded = 0
        for acct in accounts:
            aid = acct["account_id"]
            em = acct["email"]
            if aid not in _prod_user_store:
                _prod_user_store[aid] = acct
                _prod_email_to_account[em] = aid
                loaded += 1
        if loaded:
            log.info("PATCH-274-wire: loaded %d accounts from persistent DB", loaded)

    def _persist_prod_account_patched(account_id):
        acct = _prod_user_store.get(account_id)
        if acct:
            _ap.upsert_account(acct)

    target._load_prod_accounts_from_db = _load_prod_accounts_from_db_patched
    target._persist_prod_account = _persist_prod_account_patched
    log.info("auth_wire: hooks installed")
    _load_prod_accounts_from_db_patched()
    return True
