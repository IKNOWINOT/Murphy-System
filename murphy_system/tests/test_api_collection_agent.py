"""
Tests for APICollectionAgent — the HITL loop for every Murphy System API call.
Validates: discovery, pre-filling, blank detection, approval gate,
rejection, fill_blank, execute (mocked HTTP), and audit log.

Design Label: TEST-API-COLLECTION-001
Owner: QA Team
"""
import os
import pytest


from api_collection_agent import (
    APICollectionAgent,
    APIField,
    APIPreFiller,
    APIRequirement,
    APIRequest,
    FieldSource,
    RequestStatus,
    APIMethod,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def agent():
    return APICollectionAgent(base_url="http://localhost:8000")


@pytest.fixture
def signup_req():
    return APIRequirement(
        name="signup",
        endpoint="/api/auth/signup",
        method=APIMethod.POST,
        description="Create account",
        fields=[
            APIField("name", required=True),
            APIField("email", required=True),
            APIField("position", required=True),
            APIField("justification", required=True),
        ],
    )


@pytest.fixture
def filled_context():
    return {
        "name": "Alice Smith",
        "email": "alice@example.com",
        "position": "Software Engineer",
        "justification": "Need Murphy access",
    }


# ---------------------------------------------------------------------------
# APIField
# ---------------------------------------------------------------------------


class TestAPIField:
    def test_blank_when_value_none(self):
        f = APIField("email")
        assert f.is_blank

    def test_blank_when_empty_string(self):
        f = APIField("email", value="")
        assert f.is_blank

    def test_not_blank_when_value_set(self):
        f = APIField("email", value="x@x.com")
        assert not f.is_blank

    def test_to_dict_excludes_sensitive_value(self):
        f = APIField("token", value="secret123", sensitive=True)
        d = f.to_dict()
        assert d["value"] is None

    def test_to_dict_includes_non_sensitive_value(self):
        f = APIField("name", value="Alice")
        d = f.to_dict()
        assert d["value"] == "Alice"


# ---------------------------------------------------------------------------
# APIPreFiller
# ---------------------------------------------------------------------------


class TestAPIPreFiller:
    def test_fills_exact_match(self):
        req = APIRequirement(fields=[APIField("name"), APIField("email")])
        ctx = {"name": "Bob", "email": "bob@test.com"}
        filled = APIPreFiller().prefill(req, ctx)
        names = {f.name: f.value for f in filled.fields}
        assert names["name"] == "Bob"
        assert names["email"] == "bob@test.com"

    def test_fills_alias(self):
        req = APIRequirement(fields=[APIField("email")])
        ctx = {"user_email": "carol@x.com"}
        filled = APIPreFiller().prefill(req, ctx)
        assert filled.fields[0].value == "carol@x.com"

    def test_marks_blank_as_highlight(self):
        req = APIRequirement(fields=[APIField("justification")])
        filled = APIPreFiller().prefill(req, {})
        assert filled.fields[0].highlight is True

    def test_sensitive_field_never_prefilled(self):
        req = APIRequirement(fields=[APIField("token", sensitive=True)])
        ctx = {"token": "should-not-be-set"}
        filled = APIPreFiller().prefill(req, ctx)
        assert filled.fields[0].is_blank

    def test_filled_source_is_prefilled(self):
        req = APIRequirement(fields=[APIField("name")])
        ctx = {"name": "Dave"}
        filled = APIPreFiller().prefill(req, ctx)
        assert filled.fields[0].source == FieldSource.PREFILLED

    def test_nested_path_resolution(self):
        req = APIRequirement(fields=[APIField("profile.email")])
        ctx = {"profile": {"email": "eve@test.com"}}
        filled = APIPreFiller().prefill(req, ctx)
        assert filled.fields[0].value == "eve@test.com"


# ---------------------------------------------------------------------------
# Built-in requirements
# ---------------------------------------------------------------------------


class TestBuiltInRequirements:
    def test_returns_list(self):
        reqs = APICollectionAgent.built_in_requirements()
        assert isinstance(reqs, list)
        assert len(reqs) >= 5

    def test_all_have_endpoint_and_method(self):
        for req in APICollectionAgent.built_in_requirements():
            assert req.endpoint.startswith("/api/")
            assert isinstance(req.method, APIMethod)

    def test_signup_requirement_present(self):
        names = [r.name for r in APICollectionAgent.built_in_requirements()]
        assert "signup" in names


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------


class TestEnqueue:
    def test_enqueue_returns_api_request(self, agent, signup_req, filled_context):
        req = agent.enqueue(signup_req, context=filled_context)
        assert isinstance(req, APIRequest)
        assert req.status == RequestStatus.PENDING_APPROVAL

    def test_enqueue_prefills_from_context(self, agent, signup_req, filled_context):
        req = agent.enqueue(signup_req, context=filled_context)
        names_to_values = {f.name: f.value for f in req.requirement.fields}
        assert names_to_values["name"] == "Alice Smith"
        assert names_to_values["email"] == "alice@example.com"

    def test_enqueue_no_blanks_when_context_complete(self, agent, signup_req, filled_context):
        req = agent.enqueue(signup_req, context=filled_context)
        assert not req.has_blanks()

    def test_enqueue_has_blanks_when_context_empty(self, agent, signup_req):
        req = agent.enqueue(signup_req, context={})
        assert req.has_blanks()

    def test_enqueue_appears_in_pending(self, agent, signup_req, filled_context):
        agent.enqueue(signup_req, context=filled_context)
        pending = agent.pending_requests()
        assert len(pending) >= 1


# ---------------------------------------------------------------------------
# Fill blank
# ---------------------------------------------------------------------------


class TestFillBlank:
    def test_fill_blank_sets_value(self, agent, signup_req):
        req = agent.enqueue(signup_req, context={})
        result = agent.fill_blank(req.request_id, "name", "Frank")
        assert result is True
        updated_req = agent.get_request(req.request_id)
        name_field = next(f for f in updated_req.requirement.fields if f.name == "name")
        assert name_field.value == "Frank"
        assert name_field.source == FieldSource.USER

    def test_fill_blank_unknown_request(self, agent):
        assert agent.fill_blank("notexist", "name", "X") is False

    def test_fill_blank_removes_highlight(self, agent, signup_req):
        req = agent.enqueue(signup_req, context={})
        agent.fill_blank(req.request_id, "name", "Grace")
        updated = agent.get_request(req.request_id)
        name_field = next(f for f in updated.requirement.fields if f.name == "name")
        assert name_field.highlight is False


# ---------------------------------------------------------------------------
# Approve / Reject
# ---------------------------------------------------------------------------


class TestApproveReject:
    def test_approve_fully_filled_request(self, agent, signup_req, filled_context):
        req = agent.enqueue(signup_req, context=filled_context)
        assert agent.approve(req.request_id, approved_by="alice")
        updated = agent.get_request(req.request_id)
        assert updated.status == RequestStatus.APPROVED
        assert updated.approved_by == "alice"
        assert updated.approved_at

    def test_approve_with_blanks_fails(self, agent, signup_req):
        req = agent.enqueue(signup_req, context={})
        result = agent.approve(req.request_id)
        assert result is False
        assert agent.get_request(req.request_id).status == RequestStatus.PENDING_APPROVAL

    def test_reject_request(self, agent, signup_req, filled_context):
        req = agent.enqueue(signup_req, context=filled_context)
        assert agent.reject(req.request_id, reason="Not needed right now")
        updated = agent.get_request(req.request_id)
        assert updated.status == RequestStatus.REJECTED
        assert updated.rejection_reason == "Not needed right now"

    def test_approve_unknown_request(self, agent):
        assert agent.approve("notexist") is False

    def test_reject_unknown_request(self, agent):
        assert agent.reject("notexist") is False

    def test_approved_request_not_in_pending(self, agent, signup_req, filled_context):
        req = agent.enqueue(signup_req, context=filled_context)
        agent.approve(req.request_id)
        pending = agent.pending_requests()
        assert not any(r.request_id == req.request_id for r in pending)

    def test_requests_with_blanks_filter(self, agent, signup_req):
        req_blank = agent.enqueue(signup_req, context={})
        req_full = agent.enqueue(
            APIRequirement(name="no_fields", endpoint="/api/test",
                           method=APIMethod.GET, fields=[]),
            context={},
        )
        with_blanks = agent.requests_with_blanks()
        ids = [r.request_id for r in with_blanks]
        assert req_blank.request_id in ids
        assert req_full.request_id not in ids


# ---------------------------------------------------------------------------
# Execute (mocked — no live server needed)
# ---------------------------------------------------------------------------


class TestExecute:
    def test_execute_unapproved_returns_error(self, agent, signup_req, filled_context):
        req = agent.enqueue(signup_req, context=filled_context)
        result = agent.execute(req.request_id)
        assert "error" in result

    def test_execute_unknown_request(self, agent):
        result = agent.execute("bad-id")
        assert result["error"] == "request_not_found"

    def test_execute_approved_attempts_http(self, agent, signup_req, filled_context):
        """After approval, execute should attempt the HTTP call.
        It will fail (no server), but status should be FAILED not PENDING."""
        req = agent.enqueue(signup_req, context=filled_context)
        agent.approve(req.request_id)
        result = agent.execute(req.request_id)
        # No live server → URL error expected
        assert "error" in result
        updated = agent.get_request(req.request_id)
        assert updated.status == RequestStatus.FAILED


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_audit_log_populated_after_enqueue_and_approve(
        self, agent, signup_req, filled_context
    ):
        req = agent.enqueue(signup_req, context=filled_context)
        agent.approve(req.request_id)
        log = agent.get_audit_log()
        actions = [e["action"] for e in log]
        assert "enqueue" in actions
        assert "approve" in actions

    def test_audit_log_records_rejection(self, agent, signup_req, filled_context):
        req = agent.enqueue(signup_req, context=filled_context)
        agent.reject(req.request_id, reason="test rejection")
        log = agent.get_audit_log()
        reject_entries = [e for e in log if e["action"] == "reject"]
        assert len(reject_entries) >= 1

    def test_audit_entries_have_timestamp(self, agent, signup_req, filled_context):
        agent.enqueue(signup_req, context=filled_context)
        for entry in agent.get_audit_log():
            assert "timestamp" in entry
