"""
Ship 31bf — canonical founder identity.

The ONLY place founder email addresses are defined.
Every module that needs to check 'is this Corey?' MUST import from here.

WHY THIS EXISTS
  Prior to this ship, founder emails were hardcoded in 14 different
  places across the codebase, with inconsistent allowlists. Multiple
  modules had different opinions about what 'founder' meant. This
  centralizes the truth so adding/removing a founder address is a
  one-file edit.

PRINCIPLE
  Email channels are READ-ONLY for platform changes. Even Corey's
  emails cannot mutate the platform via email body. Platform changes
  require either:
    1. Authenticated HITL approval URL click (session cookie)
    2. CLI access on the platform host
    3. OIDC bearer token on an admin route

  Email allowlists ONLY decide WHO receives auto-replies from Murphy.
  They do NOT grant any execution authority.
"""

# ─── primary founder email (HITL acceptance prompts go here) ───
PRIMARY_FOUNDER_EMAIL = "cpost@murphy.systems"

# ─── all known Corey addresses (for identity verification) ───
# Added 2026-06-13: corey.hfc@gmail.com per founder direction
FOUNDER_EMAILS = frozenset({
    "cpost@murphy.systems",
    "corey.gfc@gmail.com",
    "corey.hfc@gmail.com",
    "corey.eecs@gmail.com",
})

# ─── trusted-non-founder addresses (auto-reply, not founder) ───
TRUSTED_ALLOWLIST = frozenset({
    "callmehandy@gmail.com",   # Hawthorne
    "hpost@murphy.systems",    # Hawthorne (Murphy address)
})


def is_founder_email(addr: str) -> bool:
    """True if this address belongs to Corey."""
    if not addr:
        return False
    return addr.lower().strip() in {e.lower() for e in FOUNDER_EMAILS}


def is_trusted_email(addr: str) -> bool:
    """True if this address gets auto-replies (founder OR trusted)."""
    if not addr:
        return False
    a = addr.lower().strip()
    return a in {e.lower() for e in FOUNDER_EMAILS} or \
           a in {e.lower() for e in TRUSTED_ALLOWLIST}


def all_founder_addresses() -> list:
    """All known founder addresses (for display only)."""
    return sorted(FOUNDER_EMAILS)


if __name__ == "__main__":
    import json
    cases = [
        ("cpost@murphy.systems",      True,  True),
        ("corey.hfc@gmail.com",       True,  True),
        ("corey.gfc@gmail.com",       True,  True),
        ("corey.eecs@gmail.com",      True,  True),
        ("callmehandy@gmail.com",     False, True),
        ("attacker@evil.com",         False, False),
        ("",                          False, False),
    ]
    print("FOUNDER IDENTITY SELF-TEST")
    for addr, exp_founder, exp_trusted in cases:
        f = is_founder_email(addr)
        t = is_trusted_email(addr)
        mark = "✅" if (f == exp_founder and t == exp_trusted) else "❌"
        print(f"  {mark} '{addr:30}' founder={f} trusted={t}")
    print()
    print(f"FOUNDER ADDRESSES ({len(FOUNDER_EMAILS)}):")
    for e in all_founder_addresses():
        print(f"  - {e}")
