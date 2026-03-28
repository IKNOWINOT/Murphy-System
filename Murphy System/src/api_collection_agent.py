"""
API Collection Agent — Murphy System

Applies the same HITL loop used by EnvironmentSetupAgent to every API
call the system needs to make.  For each identified API requirement the
agent:

  1. Discovers what the call needs (endpoint, method, headers, body fields)
  2. Pre-fills every field it can from existing context (profile, env state,
     previous results)
  3. Marks unknown or sensitive fields as "blank" — highlighted for the user
  4. Presents the draft request for human review via the approval queue
  5. User may fill blanks, override any field, or reject the whole request
  6. Only after explicit approval does the agent submit the request
  7. Result is returned to the calling subsystem and audit-logged

The "blank" concept maps directly to the UI highlighter: every field whose
``value`` is None or empty is a highlight target in the overlay layer.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_MAX_AUDIT = 10_000


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class APIMethod(str, Enum):
    """HTTP method enum for outbound API collection requests."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class FieldSource(str, Enum):
    """How a field value was obtained."""
    PREFILLED = "prefilled"    # agent derived it from context
    USER = "user"              # user explicitly set it
    DEFAULT = "default"        # static default
    BLANK = "blank"            # unknown — needs user input (highlighted)


class RequestStatus(str, Enum):
    """Lifecycle status of an API request managed by the collection agent."""
    DRAFT = "draft"            # being assembled
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class APIField:
    """A single field in an API request body or query string."""

    name: str
    value: Optional[Any] = None
    source: FieldSource = FieldSource.BLANK
    required: bool = True
    description: str = ""
    sensitive: bool = False        # e.g. passwords, tokens → never auto-fill
    highlight: bool = False        # True → show in overlay for user review

    @property
    def is_blank(self) -> bool:
        return self.value is None or self.value == ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": None if self.sensitive and self.value else self.value,
            "source": self.source.value,
            "required": self.required,
            "description": self.description,
            "sensitive": self.sensitive,
            "highlight": self.highlight,
        }


@dataclass
class APIRequirement:
    """Describes a single API call the system needs to make."""

    requirement_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""                           # human-readable name, e.g. "signup"
    endpoint: str = ""                       # e.g. "/api/auth/signup"
    method: APIMethod = APIMethod.POST
    description: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    fields: List[APIField] = field(default_factory=list)
    context_keys: List[str] = field(default_factory=list)  # profile/env keys to pull from
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def blank_fields(self) -> List[APIField]:
        return [f for f in self.fields if f.is_blank and f.required]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "name": self.name,
            "endpoint": self.endpoint,
            "method": self.method.value,
            "description": self.description,
            "headers": self.headers,
            "fields": [f.to_dict() for f in self.fields],
            "blank_fields": [f.name for f in self.blank_fields()],
            "created_at": self.created_at,
        }


@dataclass
class APIRequest:
    """A fully-assembled API request ready for HITL review."""

    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    requirement: Optional[APIRequirement] = None
    base_url: str = "http://localhost:8000"
    status: RequestStatus = RequestStatus.DRAFT
    approved_by: str = ""
    approved_at: str = ""
    rejection_reason: str = ""
    response: Optional[Dict[str, Any]] = None
    error: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def full_url(self) -> str:
        if self.requirement:
            return self.base_url.rstrip("/") + self.requirement.endpoint
        return self.base_url

    @property
    def body(self) -> Dict[str, Any]:
        if self.requirement is None:
            return {}
        return {
            f.name: f.value
            for f in self.requirement.fields
            if f.value is not None
        }

    def has_blanks(self) -> bool:
        if self.requirement is None:
            return False
        return bool(self.requirement.blank_fields())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "requirement": self.requirement.to_dict() if self.requirement else None,
            "base_url": self.base_url,
            "full_url": self.full_url,
            "body": self.body,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rejection_reason": self.rejection_reason,
            "has_blanks": self.has_blanks(),
            "response": self.response,
            "error": self.error,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Pre-filler: best-effort auto-population from context
# ---------------------------------------------------------------------------


class APIPreFiller:
    """Fills API fields from a context dictionary using best knowledge.

    Rules (in priority order):
      1. Exact key match:  field.name == context key
      2. Nested path:      field.name contains '.' (e.g. profile.email)
      3. Alias lookup:     common field name aliases (email → user_email, etc.)
      4. Anything still blank is marked highlight=True for the overlay
    """

    _ALIASES: Dict[str, List[str]] = {
        "email": ["user_email", "contact_email", "email_address"],
        "name": ["full_name", "display_name", "user_name"],
        "org_id": ["organization_id", "org", "company_id"],
        "user_id": ["uid", "account_id"],
        "token": ["api_token", "auth_token", "access_token"],
    }

    def prefill(
        self,
        requirement: APIRequirement,
        context: Dict[str, Any],
    ) -> APIRequirement:
        """Mutate *requirement* in-place, returning it for chaining."""
        for api_field in requirement.fields:
            if api_field.sensitive:
                api_field.highlight = True
                continue
            if not api_field.is_blank:
                continue

            value = self._resolve(api_field.name, context)
            if value is not None:
                api_field.value = value
                api_field.source = FieldSource.PREFILLED
                api_field.highlight = False
            else:
                api_field.highlight = True   # needs user attention

        return requirement

    # ------------------------------------------------------------------

    def _resolve(self, field_name: str, context: Dict[str, Any]) -> Optional[Any]:
        # 1. Exact match
        if field_name in context:
            return context[field_name]

        # 2. Nested path (e.g. "profile.email")
        if "." in field_name:
            parts = field_name.split(".")
            val: Any = context
            try:
                for part in parts:
                    val = val[part]
                return val
            except (KeyError, TypeError) as exc:
                logging.getLogger(__name__).debug("Context path lookup failed for %r: %s", field_name, exc)

        # 3. Alias lookup
        for canonical, aliases in self._ALIASES.items():
            if field_name == canonical:
                for alias in aliases:
                    if alias in context:
                        return context[alias]
            if field_name in aliases and canonical in context:
                return context[canonical]

        return None


# ---------------------------------------------------------------------------
# APICollectionAgent
# ---------------------------------------------------------------------------


class APICollectionAgent:
    """HITL-gated agent that collects, pre-fills, and submits API requests.

    The workflow mirrors EnvironmentSetupAgent:

      collect_requirements() → prefill from context → add to approval queue
      → user reviews (fills blanks, overrides fields) → approve/reject
      → execute_approved() → return results

    Usage::

        agent = APICollectionAgent(base_url="http://localhost:8000")

        # Register built-in Murphy API requirements
        reqs = agent.built_in_requirements()
        for req in reqs:
            agent.enqueue(req, context=user_profile_dict)

        # In the UI: user fills blanks and approves
        agent.fill_blank(request_id, "employee_letter", "I work in QA...")
        agent.approve(request_id, approved_by="alice@example.com")

        result = agent.execute(request_id)
    """

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self._prefiller = APIPreFiller()
        self._lock = threading.Lock()
        self._requests: Dict[str, APIRequest] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Built-in Murphy System API requirements
    # ------------------------------------------------------------------

    @staticmethod
    def built_in_requirements() -> List[APIRequirement]:
        """Return the canonical list of Murphy System API requirements.

        Each entry matches a route defined in the problem statement's
        /api/auth/ and /api/setup/ namespaces.
        """
        return [
            APIRequirement(
                name="signup",
                endpoint="/api/auth/signup",
                method=APIMethod.POST,
                description="Create a new user account",
                fields=[
                    APIField("name", required=True, description="Full name"),
                    APIField("email", required=True, description="Contact email"),
                    APIField("phone", required=False, description="Phone (optional)"),
                    APIField("position", required=True, description="Job title"),
                    APIField("department", required=False, description="Department"),
                    APIField("employee_letter", required=False,
                             description="Role description / employee letter text"),
                    APIField("justification", required=True,
                             description="Why you need Murphy System access"),
                    APIField("org_id", required=False, description="Join existing org (optional)"),
                    APIField("new_org_name", required=False,
                             description="Create new org (if not joining existing)"),
                ],
                context_keys=["name", "email", "phone", "position", "department",
                               "justification", "org_id"],
            ),
            APIRequirement(
                name="validate_email",
                endpoint="/api/auth/validate-email",
                method=APIMethod.POST,
                description="Validate email with token from signup",
                fields=[
                    APIField("user_id", required=True, description="User ID from signup"),
                    APIField("token", required=True, description="Validation token (from email)",
                             sensitive=True),
                ],
                context_keys=["user_id"],
            ),
            APIRequirement(
                name="accept_eula",
                endpoint="/api/auth/accept-eula",
                method=APIMethod.POST,
                description="Record EULA acceptance",
                fields=[
                    APIField("user_id", required=True, description="User ID"),
                    APIField("eula_version", required=True,
                             description="EULA version being accepted"),
                    APIField("ip_address", required=False, description="Client IP"),
                ],
                context_keys=["user_id", "eula_version"],
            ),
            APIRequirement(
                name="update_profile",
                endpoint="/api/profiles/me",
                method=APIMethod.PUT,
                description="Update current user profile",
                fields=[
                    APIField("department", required=False, description="Department"),
                    APIField("position", required=False, description="Job title"),
                    APIField("employee_letter", required=False, description="Role description"),
                ],
                context_keys=["department", "position", "employee_letter"],
            ),
            APIRequirement(
                name="assemble_terminal_config",
                endpoint="/api/profiles/me/terminal-config/assemble",
                method=APIMethod.POST,
                description="Trigger Murphy to assemble terminal config from profile",
                fields=[
                    APIField("user_id", required=True, description="User ID"),
                ],
                context_keys=["user_id"],
            ),
            APIRequirement(
                name="run_environment_probe",
                endpoint="/api/setup/probe",
                method=APIMethod.GET,
                description="Run environment probe and return report",
                fields=[],
            ),
            APIRequirement(
                name="generate_setup_plan",
                endpoint="/api/setup/plan",
                method=APIMethod.POST,
                description="Generate setup plan from probe results",
                fields=[
                    APIField("probe_results", required=True,
                             description="JSON probe report from /api/setup/probe"),
                ],
                context_keys=["probe_results"],
            ),
            APIRequirement(
                name="approve_setup_plan",
                endpoint="/api/setup/approve",
                method=APIMethod.POST,
                description="Approve setup plan (HITL gate)",
                fields=[
                    APIField("plan_id", required=True, description="Plan ID to approve"),
                    APIField("step_ids", required=False,
                             description="Specific step IDs to approve (empty = approve all)"),
                    APIField("approved_by", required=True, description="Approver identifier"),
                ],
                context_keys=["plan_id", "approved_by"],
            ),
            APIRequirement(
                name="execute_setup_plan",
                endpoint="/api/setup/execute",
                method=APIMethod.POST,
                description="Execute the approved setup plan",
                fields=[
                    APIField("plan_id", required=True, description="Plan ID to execute"),
                ],
                context_keys=["plan_id"],
            ),
        ]

    # ------------------------------------------------------------------
    # Enqueue & prefill
    # ------------------------------------------------------------------

    def enqueue(
        self,
        requirement: APIRequirement,
        context: Optional[Dict[str, Any]] = None,
    ) -> APIRequest:
        """Pre-fill *requirement* from *context* and add to the approval queue."""
        ctx = context or {}
        filled_req = self._prefiller.prefill(requirement, ctx)

        api_request = APIRequest(
            requirement=filled_req,
            base_url=self.base_url,
            status=RequestStatus.PENDING_APPROVAL,
        )

        with self._lock:
            self._requests[api_request.request_id] = api_request
            self._audit("enqueue", api_request.request_id, {
                "endpoint": requirement.endpoint,
                "blanks": [f.name for f in filled_req.blank_fields()],
            })

        logger.info(
            "Enqueued API request %s (%s %s) — %d blank field(s)",
            api_request.request_id,
            requirement.method.value,
            requirement.endpoint,
            len(filled_req.blank_fields()),
        )
        return api_request

    # ------------------------------------------------------------------
    # User interactions (fill blanks / override / approve / reject)
    # ------------------------------------------------------------------

    def fill_blank(
        self,
        request_id: str,
        field_name: str,
        value: Any,
    ) -> bool:
        """Let the user supply a value for a blank (or override any) field.

        Returns True if the field was found and updated.
        """
        with self._lock:
            req = self._requests.get(request_id)
            if req is None or req.requirement is None:
                return False
            for f in req.requirement.fields:
                if f.name == field_name:
                    f.value = value
                    f.source = FieldSource.USER
                    f.highlight = False
                    self._audit("fill_blank", request_id, {"field": field_name})
                    return True
        return False

    def approve(
        self,
        request_id: str,
        approved_by: str = "user",
    ) -> bool:
        """HITL approval gate — mark the request as approved for submission.

        Returns False if the request has required blank fields still unfilled.
        """
        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                return False
            if req.status != RequestStatus.PENDING_APPROVAL:
                return False
            blanks = req.requirement.blank_fields() if req.requirement else []
            if blanks:
                logger.warning(
                    "Request %s has %d required blank field(s): %s — cannot approve",
                    request_id,
                    len(blanks),
                    [f.name for f in blanks],
                )
                return False
            req.status = RequestStatus.APPROVED
            req.approved_by = approved_by
            req.approved_at = datetime.now(timezone.utc).isoformat()
            self._audit("approve", request_id, {"approved_by": approved_by})

        logger.info("Request %s approved by %s", request_id, approved_by)
        return True

    def reject(
        self,
        request_id: str,
        reason: str = "",
    ) -> bool:
        """Reject the request — it will not be submitted."""
        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                return False
            req.status = RequestStatus.REJECTED
            req.rejection_reason = reason
            self._audit("reject", request_id, {"reason": reason})
        logger.info("Request %s rejected: %s", request_id, reason)
        return True

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, request_id: str) -> Dict[str, Any]:
        """Submit the approved request and return the response.

        The request must be in APPROVED status.  On success, status becomes
        COMPLETED; on HTTP/network error, FAILED.
        """
        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                return {"error": "request_not_found"}
            if req.status != RequestStatus.APPROVED:
                return {"error": f"request_not_approved (status={req.status.value})"}
            req.status = RequestStatus.SUBMITTED

        response = self._http_submit(req)

        with self._lock:
            req.response = response
            req.status = (
                RequestStatus.COMPLETED
                if not response.get("error")
                else RequestStatus.FAILED
            )
            req.error = response.get("error", "")
            self._audit("execute", request_id, {
                "status": req.status.value,
                "http_status": response.get("http_status"),
            })

        return response

    def execute_all_approved(self) -> List[Dict[str, Any]]:
        """Execute all requests currently in APPROVED status."""
        with self._lock:
            approved_ids = [
                rid for rid, r in self._requests.items()
                if r.status == RequestStatus.APPROVED
            ]
        return [self.execute(rid) for rid in approved_ids]

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_request(self, request_id: str) -> Optional[APIRequest]:
        with self._lock:
            return self._requests.get(request_id)

    def pending_requests(self) -> List[APIRequest]:
        with self._lock:
            return [r for r in self._requests.values()
                    if r.status == RequestStatus.PENDING_APPROVAL]

    def requests_with_blanks(self) -> List[APIRequest]:
        """Return all pending requests that still have blank required fields."""
        with self._lock:
            return [
                r for r in self._requests.values()
                if r.status == RequestStatus.PENDING_APPROVAL and r.has_blanks()
            ]

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _http_submit(self, req: APIRequest) -> Dict[str, Any]:
        """Send the HTTP request using urllib (stdlib, no extra deps)."""
        try:
            url = req.full_url
            method = req.requirement.method.value if req.requirement else "POST"
            body_bytes = json.dumps(req.body).encode("utf-8")

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if req.requirement:
                headers.update(req.requirement.headers)

            http_req = urllib.request.Request(
                url,
                data=body_bytes if method not in ("GET", "DELETE") else None,
                headers=headers,
                method=method,
            )

            with urllib.request.urlopen(http_req, timeout=30) as resp:
                raw = resp.read()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"raw": raw.decode("utf-8", errors="replace")}
                return {"http_status": resp.status, "data": data}

        except urllib.error.HTTPError as exc:
            return {"error": f"http_error:{exc.code}", "http_status": exc.code}
        except urllib.error.URLError as exc:
            return {"error": f"url_error:{exc.reason}"}
        except Exception as exc:
            return {"error": str(exc)}

    def _audit(self, action: str, request_id: str, details: Dict[str, Any]) -> None:
        entry = {
            "action": action,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        capped_append(self._audit_log, entry, max_size=_MAX_AUDIT)
