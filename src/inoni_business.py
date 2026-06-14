"""
Ship 31bb — canonical Inoni LLC business identity.

CRITICAL: This is the ONLY place Inoni LLC's address lives in code.
Every other module that needs the address MUST import from here.
No more hardcoded street addresses anywhere else in the codebase.

If the business moves, change this file. That's the only edit.
"""

# ─────────────────────────────────────────────────────────────────────
#  Inoni LLC — registered business identity
# ─────────────────────────────────────────────────────────────────────
LEGAL_NAME = "Inoni LLC"

STREET = "7805 SE 70th Ave"
CITY = "Portland"
STATE = "Oregon"
STATE_ABBR = "OR"
ZIP_CODE = "97206"
COUNTRY = "USA"


# ─── address renderings ───
def address_full() -> str:
    """Inoni LLC · 7805 SE 70th Ave · Portland, OR 97206"""
    return f"{STREET}\n{CITY}, {STATE_ABBR} {ZIP_CODE}"


def address_single_line() -> str:
    """7805 SE 70th Ave, Portland, OR 97206"""
    return f"{STREET}, {CITY}, {STATE_ABBR} {ZIP_CODE}"


def address_html() -> str:
    """Multi-line HTML address block."""
    return f"{LEGAL_NAME}<br>{STREET}<br>{CITY}, {STATE_ABBR} {ZIP_CODE}"


def transmission_strip() -> str:
    """Used in art-deco email header — locale stamp."""
    return f"{LEGAL_NAME.upper()} · {CITY.upper()} {STATE_ABBR}"


def footer_locale(year_roman: str = "MMXXVI") -> str:
    """End-of-transmission art-deco footer."""
    return f"{LEGAL_NAME.upper()} · {CITY.upper()} · {STATE.upper()} · {year_roman}"


def short_signature() -> str:
    """One-line elegant sign-off used by the Victorian / Gatsby cards."""
    return f"{LEGAL_NAME} · {CITY}, {STATE}"


if __name__ == "__main__":
    print("FULL:")
    print(address_full())
    print()
    print("ONE LINE:")
    print(address_single_line())
    print()
    print("HTML:")
    print(address_html())
    print()
    print("TRANSMISSION:", transmission_strip())
    print("FOOTER:",       footer_locale())
    print("SIGNATURE:",    short_signature())
