#!/usr/bin/env python3
"""
Bootstrap Founder Account — Murphy System

Creates the founder (god-user) account and an optional test worker account
via SignupGateway.  Run this once during initial production deployment to
obtain the founder user_id, org_id, and test user_id that you'll store in
your operator runbook.

Usage::

    python scripts/bootstrap_founder.py \
        --email founder@example.com \
        --name "Corey Post" \
        --org-name "Murphy System"

    # With a separate test account:
    python scripts/bootstrap_founder.py \
        --email founder@example.com \
        --test-email test@example.com

All created IDs are printed to stdout.  Redirect to a file or paste into
your .env / secrets manager.

Requirements:
    pip install -e .   (or ensure src/ is on PYTHONPATH)
"""
from __future__ import annotations

import argparse
import sys
import os

# Ensure src/ is importable when run from the repo root
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))
sys.path.insert(0, os.path.join(_REPO_ROOT, "Murphy System", "src"))


def _build_gateway():
    try:
        from signup_gateway import SignupGateway
        return SignupGateway()
    except ImportError as exc:
        sys.exit(
            f"ERROR: Could not import SignupGateway — is src/ on PYTHONPATH?\n  {exc}"
        )


def bootstrap_founder(
    name: str,
    email: str,
    org_name: str,
    test_email: str | None = None,
) -> None:
    gw = _build_gateway()

    # ------------------------------------------------------------------ #
    # 1. Create the founder account                                        #
    # ------------------------------------------------------------------ #
    print(f"\n[1/5] Creating founder account for {email!r} …")
    founder_profile = gw.signup(
        name=name,
        email=email,
        position="Founder",
        justification="System owner",
        new_org_name=org_name,
    )
    print(f"      founder_user_id : {founder_profile.user_id}")
    print(f"      org_id          : {founder_profile.org_id}")
    print(f"      role            : {founder_profile.role}")

    # ------------------------------------------------------------------ #
    # 2. Validate founder email (skip real email round-trip for bootstrap) #
    # ------------------------------------------------------------------ #
    print("[2/5] Validating founder email token …")
    gw.validate_email(founder_profile.user_id, founder_profile.email_validation_token)
    print("      email_validated : True")

    # ------------------------------------------------------------------ #
    # 3. Accept EULA                                                       #
    # ------------------------------------------------------------------ #
    print("[3/5] Accepting EULA …")
    gw.accept_eula(founder_profile.user_id, ip_address="127.0.0.1")
    print("      eula_accepted   : True")

    # ------------------------------------------------------------------ #
    # 4. Verify fully onboarded                                            #
    # ------------------------------------------------------------------ #
    print("[4/5] Verifying onboarding …")
    profile = gw.get_profile(founder_profile.user_id)
    assert profile.is_fully_onboarded(), "Founder is NOT fully onboarded — check logs"
    print("      is_fully_onboarded : True")

    # ------------------------------------------------------------------ #
    # 5. Assemble terminal config — founder must get commands == ["*"]    #
    # ------------------------------------------------------------------ #
    print("[5/5] Assembling terminal config …")
    config = gw.assemble_terminal_config(founder_profile.user_id)
    assert config["commands"] == ["*"], (
        f"Expected commands=['*'] for founder_admin, got: {config['commands']}"
    )
    print(f"      commands        : {config['commands']}")
    print(f"      features        : {list(config['features'].keys())}")

    # ------------------------------------------------------------------ #
    # Optional: create a test worker account in the same org              #
    # ------------------------------------------------------------------ #
    test_user_id = None
    if test_email:
        print(f"\n[+] Creating test worker account for {test_email!r} …")
        test_profile = gw.signup(
            name="Test User",
            email=test_email,
            position="QA Engineer",
            justification="Integration testing",
            org_id=founder_profile.org_id,
        )
        gw.validate_email(test_profile.user_id, test_profile.email_validation_token)
        gw.accept_eula(test_profile.user_id, ip_address="127.0.0.1")
        assert test_profile.role == "worker", (
            f"Expected role='worker' for org-join signup, got: {test_profile.role}"
        )
        test_user_id = test_profile.user_id
        print(f"      test_user_id    : {test_user_id}")
        print(f"      test_role       : {test_profile.role}")

    # ------------------------------------------------------------------ #
    # Summary — save these values                                          #
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 60)
    print("BOOTSTRAP COMPLETE — save the following IDs:")
    print("=" * 60)
    print(f"  FOUNDER_USER_ID={founder_profile.user_id}")
    print(f"  ORG_ID={founder_profile.org_id}")
    if test_user_id:
        print(f"  TEST_USER_ID={test_user_id}")
    print("=" * 60)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap the Murphy System founder account.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--email",
        default="cpost@murphy.systems",
        help="Founder email address",
    )
    parser.add_argument(
        "--name",
        default="Corey Post",
        help="Founder display name",
    )
    parser.add_argument(
        "--org-name",
        default="Murphy System",
        help="Organisation name to create",
    )
    parser.add_argument(
        "--test-email",
        default=None,
        help="Optional test worker email address (joins the same org)",
    )
    args = parser.parse_args()

    bootstrap_founder(
        name=args.name,
        email=args.email,
        org_name=args.org_name,
        test_email=args.test_email,
    )


if __name__ == "__main__":
    main()
