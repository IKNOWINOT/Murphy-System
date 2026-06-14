"""
Ship 31bh — canonical HITL recipient distribution.

Every HITL approval email goes to ALL four addresses:
  - corey.gfc@gmail.com   (Corey, primary Gmail)
  - cpost@murphy.systems  (Corey, Murphy address)
  - hpost@murphy.systems  (Hawthorne, Murphy address)
  - callmehandy@gmail.com (Hawthorne, primary Gmail)

The To: field carries all 4 (no CC theater). All four people see
the same Accept/Reject/Revise buttons and any of them can act.
First click wins; subsequent clicks return 'already actioned'.
"""

HITL_RECIPIENTS = (
    "corey.gfc@gmail.com",
    "cpost@murphy.systems",
    "hpost@murphy.systems",
    "callmehandy@gmail.com",
)


def to_field() -> str:
    """Comma-joined To: header for SMTP."""
    return ", ".join(HITL_RECIPIENTS)


def all_recipients() -> tuple:
    return HITL_RECIPIENTS


if __name__ == "__main__":
    print("HITL distribution list:")
    for r in HITL_RECIPIENTS:
        print(f"  → {r}")
    print(f"\nTo: header → {to_field()}")
