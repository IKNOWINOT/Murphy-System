"""Tests for Phase 11 – Guest / External Collaboration."""

import sys, os

import pytest
from guest_collab.models import (
    ClientPortal, ExternalForm, FormField, FormFieldType,
    FormSubmission, GuestPermission, GuestUser, InviteStatus,
    LinkAccess, ShareableLink,
)
from guest_collab.guest_manager import GuestManager


class TestModels:
    def test_guest_to_dict(self):
        g = GuestUser(email="a@b.com", permission=GuestPermission.EDIT)
        d = g.to_dict()
        assert d["email"] == "a@b.com"
        assert d["permission"] == "edit"

    def test_link_to_dict(self):
        l = ShareableLink(board_id="b1", password="secret")
        d = l.to_dict()
        assert d["has_password"] is True
        assert "password" not in d  # password not leaked

    def test_portal_to_dict(self):
        p = ClientPortal(name="Client Portal", primary_color="#FF0000")
        assert p.to_dict()["primary_color"] == "#FF0000"

    def test_form_to_dict(self):
        f = ExternalForm(name="Feedback", board_id="b1")
        assert f.to_dict()["active"] is True

    def test_submission_to_dict(self):
        s = FormSubmission(form_id="f1", data={"name": "Alice"})
        assert s.to_dict()["data"]["name"] == "Alice"


class TestGuestManager:
    def test_invite_guest(self):
        mgr = GuestManager()
        g = mgr.invite_guest("a@b.com", name="Alice", permission=GuestPermission.VIEW,
                             board_ids=["b1"], invited_by="u1")
        assert g.email == "a@b.com"
        assert g.status == InviteStatus.PENDING
        assert mgr.get_guest(g.id) is g

    def test_list_guests(self):
        mgr = GuestManager()
        mgr.invite_guest("a@b.com", invited_by="u1")
        mgr.invite_guest("b@b.com", invited_by="u2")
        assert len(mgr.list_guests()) == 2
        assert len(mgr.list_guests("u1")) == 1

    def test_accept_invite(self):
        mgr = GuestManager()
        g = mgr.invite_guest("a@b.com")
        mgr.accept_invite(g.id)
        assert g.status == InviteStatus.ACCEPTED

    def test_revoke_invite(self):
        mgr = GuestManager()
        g = mgr.invite_guest("a@b.com")
        mgr.revoke_invite(g.id)
        assert g.status == InviteStatus.REVOKED

    def test_update_guest_permissions(self):
        mgr = GuestManager()
        g = mgr.invite_guest("a@b.com", permission=GuestPermission.VIEW)
        mgr.update_guest_permissions(g.id, permission=GuestPermission.EDIT,
                                     board_ids=["b1", "b2"])
        assert g.permission == GuestPermission.EDIT
        assert g.board_ids == ["b1", "b2"]

    def test_create_shareable_link(self):
        mgr = GuestManager()
        link = mgr.create_shareable_link("b1", created_by="u1")
        assert link.board_id == "b1"
        assert link.active is True
        assert mgr.get_link(link.id) is link

    def test_get_link_by_token(self):
        mgr = GuestManager()
        link = mgr.create_shareable_link("b1")
        found = mgr.get_link_by_token(link.token)
        assert found is link

    def test_deactivate_link(self):
        mgr = GuestManager()
        link = mgr.create_shareable_link("b1")
        assert mgr.deactivate_link(link.id)
        assert link.active is False
        assert mgr.get_link_by_token(link.token) is None

    def test_link_view_count(self):
        mgr = GuestManager()
        link = mgr.create_shareable_link("b1")
        mgr.record_link_view(link.id)
        mgr.record_link_view(link.id)
        assert link.view_count == 2

    def test_create_portal(self):
        mgr = GuestManager()
        p = mgr.create_portal("Client Portal", "u1", board_ids=["b1"])
        assert p.name == "Client Portal"
        assert mgr.get_portal(p.id) is p

    def test_add_guest_to_portal(self):
        mgr = GuestManager()
        p = mgr.create_portal("Portal", "u1")
        g = mgr.invite_guest("a@b.com")
        mgr.add_guest_to_portal(p.id, g.id)
        assert g.id in p.guest_ids

    def test_create_form(self):
        mgr = GuestManager()
        f = mgr.create_form("Feedback", "b1", fields=[
            {"label": "Name", "field_type": "text", "required": True},
            {"label": "Rating", "field_type": "number"},
        ])
        assert len(f.fields) == 2
        assert f.fields[0].required is True

    def test_submit_form(self):
        mgr = GuestManager()
        f = mgr.create_form("FB", "b1", fields=[
            {"label": "Name", "field_type": "text", "required": True},
        ])
        s = mgr.submit_form(f.id, {"Name": "Alice"}, submitter_email="a@b.com")
        assert s.data["Name"] == "Alice"
        assert f.submission_count == 1

    def test_submit_form_missing_required(self):
        mgr = GuestManager()
        f = mgr.create_form("FB", "b1", fields=[
            {"label": "Name", "field_type": "text", "required": True},
        ])
        with pytest.raises(ValueError, match="Missing required field"):
            mgr.submit_form(f.id, {})

    def test_list_submissions(self):
        mgr = GuestManager()
        f = mgr.create_form("FB", "b1")
        mgr.submit_form(f.id, {"x": 1})
        mgr.submit_form(f.id, {"x": 2})
        assert len(mgr.list_submissions(f.id)) == 2

    def test_guest_not_found(self):
        mgr = GuestManager()
        with pytest.raises(KeyError):
            mgr.accept_invite("bad")

    def test_form_not_found(self):
        mgr = GuestManager()
        with pytest.raises(KeyError):
            mgr.submit_form("bad", {})


class TestAPIRouter:
    def test_create_router(self):
        from guest_collab.api import create_guest_router
        router = create_guest_router()
        assert router is not None
