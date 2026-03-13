"""
Signup Gateway — Murphy System

Implements signup, email validation, EULA acceptance, and user profile
management. Provides the UserProfile data model and backend logic for
the Part 1 requirements: Signup Gateway and Profile-Gated Terminals.

Design Principles:
  - HITL everywhere: no access until signup + email validation + EULA
  - Alpha disclaimer: BSL 1.1, no warranty
  - Ownership model: shadow automations → user IP, corporate → org IP
  - Thread-safe with bounded audit log

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from thread_safe_operations import capped_append

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PII Redaction Helpers
# ---------------------------------------------------------------------------

def _redact_email(email: str) -> str:
    """Redact email for safe logging: u***@domain.com."""
    if not email or "@" not in email:
        return "[REDACTED_EMAIL]"
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}"


def _redact_ip(ip: str) -> str:
    """Redact IP address for safe logging: 192.168.xxx.xxx."""
    if not ip:
        return "[REDACTED_IP]"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.xxx.xxx"
    return "[REDACTED_IP]"

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

_PHONE_RE = re.compile(r"^\+\d{10,15}$|^\d{10,15}$")

_EMAIL_TOKEN_EXPIRY = timedelta(hours=24)

_OTP_EXPIRY = timedelta(minutes=10)

_OTP_MAX_ATTEMPTS = 5

_OTP_LOCKOUT_WINDOW = 300  # seconds

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EULA_VERSION = "1.0-alpha"

EULA_TEXT = """\
END USER AGREEMENT — MURPHY SYSTEM (ALPHA)
Version: {version}

IMPORTANT: READ CAREFULLY BEFORE PROCEEDING.

1. ALPHA SOFTWARE DISCLAIMER
   Murphy System is alpha software provided "AS IS" with NO WARRANTY OF ANY
   KIND. Inoni LLC expressly disclaims all warranties, express or implied,
   including but not limited to merchantability, fitness for a particular
   purpose, and non-infringement. USE AT YOUR OWN RISK.

2. LIABILITY SPLIT
   a. HITL Validators are solely liable for their own validation decisions.
   b. The subscribing Business/Organization is solely liable for business
      decisions made using Murphy System outputs.
   c. Inoni LLC provides no warranty and accepts no liability for alpha
      software defects, data loss, or consequential damages.

3. DATA AND LOGS
   All system logs, interaction data, and feedback submitted by users are
   available to Inoni LLC for creating fixes, adjustments, and improvements
   based on negative feedback and aggregate usage patterns.

4. INTELLECTUAL PROPERTY OWNERSHIP
   a. Shadow Automations: Automations created by a user through their shadow
      agent are the exclusive intellectual property of that user.
   b. Corporate/Org-Chart Automations: Automations created in the context of
      an organization's workflows are the intellectual property of that
      organization.
   c. Murphy System License: Both user-owned and org-owned automations are
      licensed to Inoni LLC on a perpetual, non-exclusive, royalty-free basis
      solely for use within the Murphy System database for anonymized and
      aggregated pattern improvement. This license does not grant Inoni LLC
      rights to distribute or sell individual user automations.

5. ACCESS CONDITIONS
   Access to any Murphy System terminal requires:
   - Completed signup with valid contact information
   - Email address validation
   - Acceptance of this End User Agreement

6. GOVERNING LAW
   This agreement is governed by the laws of the jurisdiction in which Inoni
   LLC is incorporated.

By clicking "I Accept" you acknowledge that you have read, understood, and
agree to be bound by this End User Agreement.
""".format(version=EULA_VERSION)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class UserProfile:
    """Complete user profile created during onboarding signup."""

    user_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    email: str = ""
    name: str = ""
    position: str = ""
    department: str = ""
    employee_letter: str = ""      # text content or file reference
    justification: str = ""
    org_id: str = ""
    role: str = "worker"           # "founder_admin" | "manager" | "worker"
    shadow_agent_id: str = ""      # assigned after onboarding
    eula_accepted: bool = False
    eula_version: str = ""
    eula_accepted_at: str = ""
    email_validated: bool = False
    email_validation_token: str = field(
        default_factory=lambda: uuid.uuid4().hex
    )
    email_validation_token_created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    phone: str = ""
    phone_validated: bool = False
    phone_validation_code: str = ""
    phone_otp_created_at: str = ""
    terminal_config: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain-dict representation of the signup request."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "position": self.position,
            "department": self.department,
            "employee_letter": self.employee_letter,
            "justification": self.justification,
            "org_id": self.org_id,
            "role": self.role,
            "shadow_agent_id": self.shadow_agent_id,
            "eula_accepted": self.eula_accepted,
            "eula_version": self.eula_version,
            "eula_accepted_at": self.eula_accepted_at,
            "email_validated": self.email_validated,
            "phone": self.phone,
            "phone_validated": self.phone_validated,
            "terminal_config": self.terminal_config,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def is_fully_onboarded(self) -> bool:
        """Return True only when signup, email validation, and EULA are done."""
        return self.email_validated and self.eula_accepted


@dataclass
class Organization:
    """An organization in the Murphy System account plane."""

    org_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    founder_user_id: str = ""
    member_ids: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain-dict representation of the organisation record."""
        return {
            "org_id": self.org_id,
            "name": self.name,
            "founder_user_id": self.founder_user_id,
            "member_ids": self.member_ids,
            "created_at": self.created_at,
        }


@dataclass
class EulaRecord:
    """Immutable record of a user's EULA acceptance."""

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_id: str = ""
    eula_version: str = EULA_VERSION
    accepted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ip_address: str = ""
    user_agent: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain-dict representation of the EULA acceptance record."""
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "eula_version": self.eula_version,
            "accepted_at": self.accepted_at,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SignupError(Exception):
    """Raised when signup validation fails."""


class AuthError(Exception):
    """Raised when authentication/authorization fails."""


# ---------------------------------------------------------------------------
# SignupGateway
# ---------------------------------------------------------------------------

_MAX_AUDIT_LOG = 10_000


class SignupGateway:
    """Backend logic for signup, email validation, EULA, and profiles.

    All public methods are thread-safe. The audit log is bounded to
    prevent unbounded memory growth.

    Usage::

        gw = SignupGateway()
        profile = gw.signup(
            name="Alice",
            email="alice@example.com",
            position="Engineer",
            justification="Need to automate CI",
            new_org_name="Acme Corp",
        )
        gw.validate_email(profile.user_id, profile.email_validation_token)
        gw.accept_eula(profile.user_id, ip_address="127.0.0.1")
        assert gw.get_profile(profile.user_id).is_fully_onboarded()
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profiles: Dict[str, UserProfile] = {}
        self._orgs: Dict[str, Organization] = {}
        self._eula_records: Dict[str, EulaRecord] = {}  # user_id → record
        self._audit_log: List[Dict[str, Any]] = []
        self._otp_attempts: Dict[str, List[float]] = {}  # user_id → [timestamps]
        self._otp_lockouts: Dict[str, float] = {}  # user_id → lockout_until

    # ------------------------------------------------------------------
    # Signup
    # ------------------------------------------------------------------

    def signup(
        self,
        name: str,
        email: str,
        position: str,
        justification: str,
        department: str = "",
        employee_letter: str = "",
        org_id: Optional[str] = None,
        new_org_name: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> UserProfile:
        """Create a new user account.

        Either ``org_id`` (join existing) or ``new_org_name`` (create new)
        must be provided.  When creating a new org the user becomes the
        ``founder_admin``.
        """
        if not name or not name.strip():
            raise SignupError("name is required")
        if not email or not email.strip():
            raise SignupError("email is required")
        if not _EMAIL_RE.match(email.strip()):
            raise SignupError("invalid email format")
        if not position or not position.strip():
            raise SignupError("position is required")
        if not justification or not justification.strip():
            raise SignupError("justification is required")
        if org_id is None and not new_org_name:
            raise SignupError("org_id or new_org_name is required")

        with self._lock:
            # Duplicate email check
            for p in self._profiles.values():
                if p.email.lower() == email.lower().strip():
                    raise SignupError("email already registered")

            role = "worker"
            resolved_org_id = org_id or ""

            if new_org_name:
                org = Organization(name=new_org_name.strip())
                role = "founder_admin"
                resolved_org_id = org.org_id
                self._orgs[org.org_id] = org

            profile = UserProfile(
                name=name.strip(),
                email=email.lower().strip(),
                position=position.strip(),
                department=department.strip(),
                employee_letter=employee_letter,
                justification=justification.strip(),
                org_id=resolved_org_id,
                role=role,
                phone=phone.strip() if phone else "",
            )

            if new_org_name:
                self._orgs[resolved_org_id].founder_user_id = profile.user_id
                self._orgs[resolved_org_id].member_ids.append(profile.user_id)
            elif org_id and org_id in self._orgs:
                self._orgs[org_id].member_ids.append(profile.user_id)

            self._profiles[profile.user_id] = profile
            self._audit("signup", profile.user_id, {"email": _redact_email(profile.email), "role": role})

        logger.info("Signup: user_id=%s email=%s role=%s", profile.user_id, _redact_email(profile.email), role)
        return profile

    # ------------------------------------------------------------------
    # Email validation
    # ------------------------------------------------------------------

    def validate_email(self, user_id: str, token: str) -> UserProfile:
        """Validate the email token for a user.

        Tokens expire after 24 hours.  Uses constant-time comparison
        to prevent timing-based token guessing.
        """
        with self._lock:
            profile = self._profiles.get(user_id)
            if profile is None:
                raise AuthError("user not found")
            if profile.email_validated:
                return profile
            # Check token expiry
            if profile.email_validation_token_created_at:
                created = datetime.fromisoformat(profile.email_validation_token_created_at)
                if datetime.now(timezone.utc) - created > _EMAIL_TOKEN_EXPIRY:
                    raise AuthError("email validation token has expired")
            if not hmac.compare_digest(profile.email_validation_token, token):
                raise AuthError("invalid email validation token")
            profile.email_validated = True
            profile.updated_at = datetime.now(timezone.utc).isoformat()
            self._audit("validate_email", user_id, {})

        logger.info("Email validated: user_id=%s", user_id)
        return profile

    # ------------------------------------------------------------------
    # Phone OTP
    # ------------------------------------------------------------------

    def send_phone_otp(self, user_id: str) -> str:
        """Generate and store a 6-digit OTP for phone verification.

        Returns the OTP code (in production this would be sent via SMS,
        e.g. through the Twilio API).  Validates phone number format
        (E.164 / 10–15 digit) before generating.
        """
        import random
        otp = f"{random.randint(0, 999999):06d}"
        with self._lock:
            profile = self._profiles.get(user_id)
            if profile is None:
                raise AuthError("user not found")
            if not profile.phone:
                raise SignupError("no phone number on file")
            if not _PHONE_RE.match(profile.phone):
                raise SignupError("invalid phone number format")
            profile.phone_validation_code = otp
            profile.phone_otp_created_at = datetime.now(timezone.utc).isoformat()
            profile.updated_at = datetime.now(timezone.utc).isoformat()
            self._otp_attempts.pop(user_id, None)
            self._otp_lockouts.pop(user_id, None)
            self._audit("send_phone_otp", user_id, {})

        # Production: call Twilio here, e.g.:
        #   twilio_client.messages.create(to=profile.phone, body=f"Your Murphy OTP: {otp}", ...)
        logger.info("Phone OTP generated: user_id=%s", user_id)
        return otp

    def validate_phone(self, user_id: str, otp: str) -> UserProfile:
        """Verify the 6-digit OTP and mark the phone number as validated.

        Hardening:
        - Constant-time comparison via ``hmac.compare_digest``
        - OTP expires after 10 minutes
        - Max 5 failed attempts before 5-minute lockout
        """
        now = time.time()
        with self._lock:
            profile = self._profiles.get(user_id)
            if profile is None:
                raise AuthError("user not found")

            # Check lockout
            lockout_until = self._otp_lockouts.get(user_id, 0.0)
            if now < lockout_until:
                raise AuthError("too many failed OTP attempts — try again later")

            if not profile.phone:
                raise SignupError("no phone number on file")
            if not profile.phone_validation_code:
                raise AuthError("no OTP issued — call send_phone_otp first")

            # Check OTP expiry
            if profile.phone_otp_created_at:
                created = datetime.fromisoformat(profile.phone_otp_created_at)
                if datetime.now(timezone.utc) - created > _OTP_EXPIRY:
                    profile.phone_validation_code = ""
                    raise AuthError("OTP has expired — request a new one")

            if not hmac.compare_digest(profile.phone_validation_code, otp):
                attempts = self._otp_attempts.setdefault(user_id, [])
                attempts.append(now)
                # Prune old attempts outside the window
                attempts[:] = [t for t in attempts if now - t < _OTP_LOCKOUT_WINDOW]
                if len(attempts) >= _OTP_MAX_ATTEMPTS:
                    self._otp_lockouts[user_id] = now + _OTP_LOCKOUT_WINDOW
                    logger.warning("OTP lockout triggered: user_id=%s", user_id)
                raise AuthError("invalid phone OTP")

            profile.phone_validated = True
            profile.phone_validation_code = ""
            profile.phone_otp_created_at = ""
            profile.updated_at = datetime.now(timezone.utc).isoformat()
            self._otp_attempts.pop(user_id, None)
            self._otp_lockouts.pop(user_id, None)
            self._audit("validate_phone", user_id, {})

        logger.info("Phone validated: user_id=%s", user_id)
        return profile

    # ------------------------------------------------------------------
    # EULA
    # ------------------------------------------------------------------

    def get_eula(self) -> Dict[str, str]:
        """Return the current EULA text and version."""
        return {"version": EULA_VERSION, "text": EULA_TEXT}

    def accept_eula(
        self,
        user_id: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> EulaRecord:
        """Record that the user has accepted the EULA."""
        with self._lock:
            profile = self._profiles.get(user_id)
            if profile is None:
                raise AuthError("user not found")
            if not profile.email_validated:
                raise AuthError("email must be validated before accepting EULA")

            record = EulaRecord(
                user_id=user_id,
                eula_version=EULA_VERSION,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            profile.eula_accepted = True
            profile.eula_version = EULA_VERSION
            profile.eula_accepted_at = record.accepted_at
            profile.updated_at = record.accepted_at
            self._eula_records[user_id] = record
            self._audit("accept_eula", user_id, {"version": EULA_VERSION, "ip": _redact_ip(ip_address)})

        logger.info("EULA accepted: user_id=%s version=%s", user_id, EULA_VERSION)
        return record

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    def get_profile(self, user_id: str) -> UserProfile:
        """Return a user's profile (raises AuthError if not found)."""
        with self._lock:
            profile = self._profiles.get(user_id)
        if profile is None:
            raise AuthError("user not found")
        return profile

    def update_profile(
        self,
        user_id: str,
        updates: Dict[str, Any],
    ) -> UserProfile:
        """Apply a dict of updates to the user's profile."""
        _IMMUTABLE = {"user_id", "email", "created_at", "email_validation_token"}
        with self._lock:
            profile = self._profiles.get(user_id)
            if profile is None:
                raise AuthError("user not found")
            for key, value in updates.items():
                if key in _IMMUTABLE:
                    continue
                if hasattr(profile, key):
                    setattr(profile, key, value)
            profile.updated_at = datetime.now(timezone.utc).isoformat()
            self._audit("update_profile", user_id, {"fields": list(updates.keys())})
        return profile

    def get_org_profiles(self, org_id: str) -> List[UserProfile]:
        """Return all profiles belonging to an org."""
        with self._lock:
            return [p for p in self._profiles.values() if p.org_id == org_id]

    # ------------------------------------------------------------------
    # Terminal config
    # ------------------------------------------------------------------

    def assemble_terminal_config(self, user_id: str) -> Dict[str, Any]:
        """Assemble a terminal_config for the user based on their profile.

        Murphy infers which features to expose based on the user's position,
        department, role, and employee letter.  In production this would
        invoke an LLM planning pass; here we provide rule-based inference.
        """
        with self._lock:
            profile = self._profiles.get(user_id)
        if profile is None:
            raise AuthError("user not found")
        if not profile.is_fully_onboarded():
            raise AuthError("user is not fully onboarded")

        config: Dict[str, Any] = {
            "user_id": user_id,
            "role": profile.role,
            "features": {},
            "commands": [],
            "assembled_at": datetime.now(timezone.utc).isoformat(),
        }

        # Founder/admin gets full access
        if profile.role == "founder_admin":
            config["features"] = {
                "architect_terminal": True,
                "org_chart_editor": True,
                "user_management": True,
                "shadow_agent_config": True,
                "automation_library": True,
                "analytics_dashboard": True,
                "audit_log_viewer": True,
            }
            config["commands"] = ["*"]
        elif profile.role == "manager":
            config["features"] = {
                "worker_terminal": True,
                "team_dashboard": True,
                "automation_library": True,
                "analytics_dashboard": True,
                "shadow_agent_config": False,
            }
            config["commands"] = ["run", "status", "report", "assign"]
        else:
            # Worker — infer from position text
            pos_lower = profile.position.lower()
            config["features"] = {
                "worker_terminal": True,
                "automation_library": "engineer" in pos_lower or "developer" in pos_lower,
                "analytics_dashboard": "analyst" in pos_lower,
                "shadow_agent_config": False,
            }
            config["commands"] = ["run", "status"]

        # Save back into profile
        with self._lock:
            self._profiles[user_id].terminal_config = config
            self._audit("assemble_terminal_config", user_id, {"role": profile.role})

        return config

    # ------------------------------------------------------------------
    # Session / auth check
    # ------------------------------------------------------------------

    def check_terminal_access(self, user_id: str) -> Dict[str, Any]:
        """Return access status for a user trying to open a terminal.

        Returns::
            {"allowed": bool, "reason": str, "profile": dict | None}
        """
        try:
            profile = self.get_profile(user_id)
        except AuthError:
            return {"allowed": False, "reason": "user_not_found", "profile": None}

        if not profile.email_validated:
            return {
                "allowed": False,
                "reason": "email_not_validated",
                "profile": profile.to_dict(),
            }
        if not profile.eula_accepted:
            return {
                "allowed": False,
                "reason": "eula_not_accepted",
                "profile": profile.to_dict(),
            }
        return {"allowed": True, "reason": "ok", "profile": profile.to_dict()}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _audit(self, action: str, user_id: str, details: Dict[str, Any]) -> None:
        entry = {
            "action": action,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Return a copy of the audit log."""
        with self._lock:
            return list(self._audit_log)
