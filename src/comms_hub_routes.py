# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Communication Hub Routes — Murphy System

FastAPI router surface for the unified Communication Hub.

Endpoints
---------
Instant Messaging (IM):
  POST /api/comms/im/threads                      — Create a new IM thread
  GET  /api/comms/im/threads                      — List IM threads (optionally filtered by user)
  GET  /api/comms/im/threads/{tid}                — Get thread details
  POST /api/comms/im/threads/{tid}/messages       — Post a message to a thread
  GET  /api/comms/im/threads/{tid}/messages       — Get messages in a thread
  POST /api/comms/im/threads/{tid}/messages/{mid}/reactions  — Add reaction

Voice Calls:
  POST /api/comms/voice/sessions                  — Initiate a voice call
  GET  /api/comms/voice/sessions                  — List voice sessions
  GET  /api/comms/voice/sessions/{sid}            — Get session details
  POST /api/comms/voice/sessions/{sid}/answer     — Answer a voice call
  POST /api/comms/voice/sessions/{sid}/hold       — Put call on hold
  POST /api/comms/voice/sessions/{sid}/end        — End a voice call
  POST /api/comms/voice/sessions/{sid}/reject     — Reject a call
  POST /api/comms/voice/sessions/{sid}/ice        — Submit ICE candidate

Video Calls:
  POST /api/comms/video/sessions                  — Initiate a video call
  GET  /api/comms/video/sessions                  — List video sessions
  GET  /api/comms/video/sessions/{sid}            — Get session details
  POST /api/comms/video/sessions/{sid}/answer     — Answer a video call
  POST /api/comms/video/sessions/{sid}/end        — End a video call
  POST /api/comms/video/sessions/{sid}/ice        — Submit ICE candidate

Email:
  POST /api/comms/email/send                      — Compose and send an email
  GET  /api/comms/email/inbox                     — Get user's inbox
  GET  /api/comms/email/outbox                    — Get user's outbox
  GET  /api/comms/email/{eid}                     — Get a specific email
  POST /api/comms/email/{eid}/read                — Mark an email as read

Automation Rules:
  POST /api/comms/automate/rules                  — Create an automation rule
  GET  /api/comms/automate/rules                  — List rules
  GET  /api/comms/automate/rules/{rid}            — Get a rule
  PATCH /api/comms/automate/rules/{rid}/toggle    — Enable/disable a rule
  DELETE /api/comms/automate/rules/{rid}          — Delete a rule
  POST /api/comms/automate/evaluate               — Evaluate rules against a payload

Moderator Console:
  GET  /api/moderator/users                       — List all users
  POST /api/moderator/users/{user}/role           — Set user role
  POST /api/moderator/users/{user}/warn           — Warn a user
  POST /api/moderator/users/{user}/mute           — Mute a user
  POST /api/moderator/users/{user}/unmute         — Unmute a user
  POST /api/moderator/users/{user}/kick           — Kick a user
  POST /api/moderator/users/{user}/ban            — Ban a user
  POST /api/moderator/users/{user}/unban          — Unban a user
  DELETE /api/moderator/messages/{channel}/{mid}  — Delete a message (mod)
  GET  /api/moderator/automod/words               — List blocked words
  POST /api/moderator/automod/words               — Add blocked words
  DELETE /api/moderator/automod/words/{word}      — Remove a blocked word
  POST /api/moderator/automod/check               — Check content against automod
  GET  /api/moderator/broadcast/targets           — List broadcast targets
  POST /api/moderator/broadcast/targets           — Register a broadcast target
  DELETE /api/moderator/broadcast/targets/{platform}/{channel_id} — Unregister target
  POST /api/moderator/broadcast                   — Broadcast to multiple platforms
  GET  /api/moderator/broadcast/history           — Broadcast history
  GET  /api/moderator/audit                       — Moderator audit log

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.communication_hub import (
    im_store,
    call_store,
    email_store,
    automation_store,
    mod_console,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class CreateThreadRequest(BaseModel):
    participants: List[str]
    name: Optional[str] = None
    type: str = "direct"


class PostMessageRequest(BaseModel):
    sender: str
    content: str
    attachments: Optional[List[str]] = None


class AddReactionRequest(BaseModel):
    emoji: str = "👍"
    user: str


class InitiateCallRequest(BaseModel):
    caller: str
    participants: List[str]
    sdp_offer: Optional[str] = None


class AnswerCallRequest(BaseModel):
    sdp_answer: Optional[str] = None


class IceCandidateRequest(BaseModel):
    candidate: str


class EndCallRequest(BaseModel):
    voicemail_url: Optional[str] = None


class SendEmailRequest(BaseModel):
    """PATCH-008: sender/recipients have defaults so "to"/"from" aliases work.
    Accepts both {"to":[...], "sender":"..."} and {"recipients":[...], "sender":"..."}.
    sender defaults to "system" when not provided (auth resolved upstream).
    """
    sender: str = "system"
    recipients: Optional[List[str]] = None
    # Alias: accept "to" as well as "recipients"
    to: Optional[List[str]] = None
    subject: str
    body: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    attachments: Optional[List[str]] = None
    priority: str = "normal"
    thread_id: Optional[str] = None

    @property
    def effective_recipients(self) -> List[str]:
        return self.recipients or self.to or []


class MarkReadRequest(BaseModel):
    user: str


class CreateRuleRequest(BaseModel):
    name: str
    trigger: str
    channel: str
    action: str
    conditions: Optional[Dict[str, Any]] = None
    action_params: Optional[Dict[str, Any]] = None
    created_by: str = "system"


class ToggleRuleRequest(BaseModel):
    enabled: bool


class EvaluateRulesRequest(BaseModel):
    trigger: str
    channel: str
    payload: Dict[str, Any] = {}


class SetRoleRequest(BaseModel):
    role: str
    by: str = "admin"


class ModActionRequest(BaseModel):
    reason: str = ""
    by: str


class AddBlockedWordsRequest(BaseModel):
    words: List[str]
    by: str = "moderator"


class CheckContentRequest(BaseModel):
    text: str


class RegisterTargetRequest(BaseModel):
    platform: str
    channel_id: str
    by: str = "moderator"


class BroadcastRequest(BaseModel):
    message: str
    platforms: Optional[List[str]] = None
    sender: str = "moderator"
    subject: Optional[str] = None
    priority: str = "normal"


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_comms_hub_router(account_resolver=None) -> APIRouter:
    """Return the FastAPI router for all /api/comms/* and /api/moderator/* routes."""
    router = APIRouter(tags=["Communication Hub"])

    # ========================================================================
    # IM — Instant Messaging
    # ========================================================================

    @router.post("/api/comms/im/threads")
    async def im_create_thread(body: CreateThreadRequest) -> Dict[str, Any]:
        """Create a new IM thread (direct or group)."""
        thread = im_store.create_thread(
            participants=body.participants,
            name=body.name,
            thread_type=body.type,
        )
        return {"ok": True, "thread": thread}

    @router.get("/api/comms/im/threads")
    async def im_list_threads(user: Optional[str] = None) -> Dict[str, Any]:
        """List all IM threads, optionally filtered to a specific user."""
        return {"ok": True, "threads": im_store.list_threads(user=user)}

    @router.get("/api/comms/im/threads/{tid}")
    async def im_get_thread(tid: str) -> Dict[str, Any]:
        """Get a specific IM thread."""
        thread = im_store.get_thread(tid)
        if thread is None:
            raise HTTPException(status_code=404, detail=f"Thread {tid!r} not found")
        return {"ok": True, "thread": {k: v for k, v in thread.items() if k != "messages"}}

    @router.post("/api/comms/im/threads/{tid}/messages")
    async def im_post_message(tid: str, body: PostMessageRequest) -> Dict[str, Any]:
        """Post a message to an IM thread."""
        try:
            msg = im_store.post_message(
                thread_id=tid,
                sender=body.sender,
                content=body.content,
                attachments=body.attachments,
                extra_blocked_words=mod_console._extra_blocked,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        # Evaluate automation rules
        matched_rules = automation_store.evaluate(
            trigger="on_message",
            channel="im",
            payload={"content": body.content, "sender": body.sender, "automod_flagged": msg["automod"]["flagged"]},
        )
        for rule in matched_rules:
            automation_store.fire_rule(rule["id"])
        return {"ok": True, "message": msg, "rules_fired": [r["id"] for r in matched_rules]}

    @router.get("/api/comms/im/threads/{tid}/messages")
    async def im_get_messages(tid: str, limit: int = 50) -> Dict[str, Any]:
        """Get messages from an IM thread."""
        msgs = im_store.get_messages(tid, limit=limit)
        return {"ok": True, "messages": msgs}

    @router.post("/api/comms/im/threads/{tid}/messages/{mid}/reactions")
    async def im_add_reaction(tid: str, mid: str, body: AddReactionRequest) -> Dict[str, Any]:
        """Add an emoji reaction to a message."""
        try:
            reactions = im_store.add_reaction(tid, mid, body.emoji, body.user)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"ok": True, "reactions": reactions}

    # ========================================================================
    # Voice Calls
    # ========================================================================

    @router.post("/api/comms/voice/sessions")
    async def voice_initiate(body: InitiateCallRequest) -> Dict[str, Any]:
        """Initiate a voice call session."""
        session = call_store.create_session(
            caller=body.caller,
            participants=body.participants,
            call_type="voice",
            sdp_offer=body.sdp_offer,
        )
        return {"ok": True, "session": session}

    @router.get("/api/comms/voice/sessions")
    async def voice_list_sessions(user: Optional[str] = None, state: Optional[str] = None) -> Dict[str, Any]:
        """List voice call sessions."""
        sessions = call_store.list_sessions(user=user, call_type="voice", state=state)
        return {"ok": True, "sessions": sessions}

    @router.get("/api/comms/voice/sessions/{sid}")
    async def voice_get_session(sid: str) -> Dict[str, Any]:
        """Get a voice call session."""
        session = call_store.get_session(sid)
        if session is None or session["type"] != "voice":
            raise HTTPException(status_code=404, detail=f"Voice session {sid!r} not found")
        return {"ok": True, "session": session}

    @router.post("/api/comms/voice/sessions/{sid}/answer")
    async def voice_answer(sid: str, body: AnswerCallRequest) -> Dict[str, Any]:
        """Answer a voice call."""
        try:
            session = call_store.answer_session(sid, sdp_answer=body.sdp_answer)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"ok": True, "session": session}

    @router.post("/api/comms/voice/sessions/{sid}/hold")
    async def voice_hold(sid: str) -> Dict[str, Any]:
        """Put a voice call on hold."""
        try:
            session = call_store.hold_session(sid)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"ok": True, "session": session}

    @router.post("/api/comms/voice/sessions/{sid}/end")
    async def voice_end(sid: str, body: EndCallRequest) -> Dict[str, Any]:
        """End a voice call."""
        try:
            session = call_store.end_session(sid, voicemail_url=body.voicemail_url)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        # Evaluate missed-call automation if voicemail was left
        if body.voicemail_url:
            matched = automation_store.evaluate("on_missed_call", "*", {"session_id": sid})
            for rule in matched:
                automation_store.fire_rule(rule["id"])
        return {"ok": True, "session": session}

    @router.post("/api/comms/voice/sessions/{sid}/reject")
    async def voice_reject(sid: str) -> Dict[str, Any]:
        """Reject an incoming voice call."""
        try:
            session = call_store.reject_session(sid)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"ok": True, "session": session}

    @router.post("/api/comms/voice/sessions/{sid}/ice")
    async def voice_ice(sid: str, body: IceCandidateRequest) -> Dict[str, Any]:
        """Submit an ICE candidate for a voice call."""
        try:
            call_store.add_ice_candidate(sid, body.candidate)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"ok": True, "session_id": sid}

    # ========================================================================
    # Video Calls
    # ========================================================================

    @router.post("/api/comms/video/sessions")
    async def video_initiate(body: InitiateCallRequest) -> Dict[str, Any]:
        """Initiate a video call session."""
        session = call_store.create_session(
            caller=body.caller,
            participants=body.participants,
            call_type="video",
            sdp_offer=body.sdp_offer,
        )
        return {"ok": True, "session": session}

    @router.get("/api/comms/video/sessions")
    async def video_list_sessions(user: Optional[str] = None, state: Optional[str] = None) -> Dict[str, Any]:
        """List video call sessions."""
        sessions = call_store.list_sessions(user=user, call_type="video", state=state)
        return {"ok": True, "sessions": sessions}

    @router.get("/api/comms/video/sessions/{sid}")
    async def video_get_session(sid: str) -> Dict[str, Any]:
        """Get a video call session."""
        session = call_store.get_session(sid)
        if session is None or session["type"] != "video":
            raise HTTPException(status_code=404, detail=f"Video session {sid!r} not found")
        return {"ok": True, "session": session}

    @router.post("/api/comms/video/sessions/{sid}/answer")
    async def video_answer(sid: str, body: AnswerCallRequest) -> Dict[str, Any]:
        """Answer a video call."""
        try:
            session = call_store.answer_session(sid, sdp_answer=body.sdp_answer)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"ok": True, "session": session}

    @router.post("/api/comms/video/sessions/{sid}/end")
    async def video_end(sid: str, body: EndCallRequest) -> Dict[str, Any]:
        """End a video call."""
        try:
            session = call_store.end_session(sid)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"ok": True, "session": session}

    @router.post("/api/comms/video/sessions/{sid}/ice")
    async def video_ice(sid: str, body: IceCandidateRequest) -> Dict[str, Any]:
        """Submit an ICE candidate for a video call."""
        try:
            call_store.add_ice_candidate(sid, body.candidate)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"ok": True, "session_id": sid}

    # ========================================================================
    # Email
    # ========================================================================

    @router.post("/api/comms/email/send")
    async def email_send(body: SendEmailRequest) -> Dict[str, Any]:
        """Compose and send an email."""
        # PATCH-008: resolve recipients via alias
        _recips = body.recipients or body.to or []
        email = email_store.compose_and_send(
            sender=body.sender,
            recipients=_recips,
            subject=body.subject,
            body=body.body,
            cc=body.cc,
            bcc=body.bcc,
            attachments=body.attachments,
            priority=body.priority,
            thread_id=body.thread_id,
        )
        # Evaluate email automation rules
        matched = automation_store.evaluate(
            "on_email", "email",
            {"content": body.body, "subject": body.subject, "sender": body.sender},
        )
        for rule in matched:
            automation_store.fire_rule(rule["id"])
        return {"ok": True, "email": email, "rules_fired": [r["id"] for r in matched]}

    @router.get("/api/comms/email/inbox")
    async def email_inbox(request: Request, user: str = "") -> Dict[str, Any]:
        """Get email inbox. Uses injected account_resolver if user param omitted.
        PATCH-005b: avoids circular import via dependency injection.
        """
        if not user and account_resolver:
            acct = account_resolver(request)
            if acct:
                user = acct.get("email", "")
        if not user:
            return {"ok": False, "error": "Provide ?user= param or authenticate", "emails": []}
        return {"ok": True, "emails": email_store.get_inbox(user)}

    @router.get("/api/comms/email/outbox")
    async def email_outbox(request: Request, user: str = "") -> Dict[str, Any]:
        """Get email outbox. Uses injected account_resolver if user param omitted.
        PATCH-005b: avoids circular import via dependency injection.
        """
        if not user and account_resolver:
            acct = account_resolver(request)
            if acct:
                user = acct.get("email", "")
        if not user:
            return {"ok": False, "error": "Provide ?user= param or authenticate", "emails": []}
        return {"ok": True, "emails": email_store.get_outbox(user)}

    @router.get("/api/comms/email/{eid}")
    async def email_get(eid: str) -> Dict[str, Any]:
        """Get a specific email by ID."""
        email = email_store.get_email(eid)
        if email is None:
            raise HTTPException(status_code=404, detail=f"Email {eid!r} not found")
        return {"ok": True, "email": email}

    @router.post("/api/comms/email/{eid}/read")
    async def email_mark_read(eid: str, body: MarkReadRequest) -> Dict[str, Any]:
        """Mark an email as read by a user."""
        try:
            email = email_store.mark_read(eid, body.user)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"ok": True, "email": email}

    # ========================================================================
    # Automation Rules
    # ========================================================================

    @router.post("/api/comms/automate/rules")
    async def automate_create_rule(body: CreateRuleRequest) -> Dict[str, Any]:
        """Create a new automation rule."""
        rule = automation_store.create_rule(
            name=body.name,
            trigger=body.trigger,
            channel=body.channel,
            action=body.action,
            conditions=body.conditions,
            action_params=body.action_params,
            created_by=body.created_by,
        )
        return {"ok": True, "rule": rule}

    @router.get("/api/comms/automate/rules")
    async def automate_list_rules(channel: Optional[str] = None) -> Dict[str, Any]:
        """List automation rules."""
        return {"ok": True, "rules": automation_store.list_rules(channel=channel)}

    @router.get("/api/comms/automate/rules/{rid}")
    async def automate_get_rule(rid: str) -> Dict[str, Any]:
        """Get a specific automation rule."""
        rule = automation_store.get_rule(rid)
        if rule is None:
            raise HTTPException(status_code=404, detail=f"Rule {rid!r} not found")
        return {"ok": True, "rule": rule}

    @router.patch("/api/comms/automate/rules/{rid}/toggle")
    async def automate_toggle_rule(rid: str, body: ToggleRuleRequest) -> Dict[str, Any]:
        """Enable or disable an automation rule."""
        try:
            rule = automation_store.toggle_rule(rid, body.enabled)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"ok": True, "rule": rule}

    @router.delete("/api/comms/automate/rules/{rid}")
    async def automate_delete_rule(rid: str) -> Dict[str, Any]:
        """Delete an automation rule."""
        deleted = automation_store.delete_rule(rid)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Rule {rid!r} not found")
        return {"ok": True, "deleted": rid}

    @router.post("/api/comms/automate/evaluate")
    async def automate_evaluate(body: EvaluateRulesRequest) -> Dict[str, Any]:
        """Evaluate automation rules against a payload and return matched rules."""
        matched = automation_store.evaluate(body.trigger, body.channel, body.payload)
        for rule in matched:
            automation_store.fire_rule(rule["id"])
        return {"ok": True, "matched_rules": matched}

    # ========================================================================
    # Moderator Console
    # ========================================================================

    @router.get("/api/moderator/users")
    async def mod_list_users() -> Dict[str, Any]:
        """List all users known to the moderator console."""
        return {"ok": True, "users": mod_console.list_users()}

    @router.post("/api/moderator/users/{user}/role")
    async def mod_set_role(user: str, body: SetRoleRequest) -> Dict[str, Any]:
        """Set a user's role (admin, moderator, member)."""
        profile = mod_console.set_user_role(user, body.role, by=body.by)
        return {"ok": True, "user": user, "profile": profile}

    @router.post("/api/moderator/users/{user}/warn")
    async def mod_warn(user: str, body: ModActionRequest) -> Dict[str, Any]:
        """Issue a warning to a user."""
        result = mod_console.warn_user(user, reason=body.reason, by=body.by)
        return {"ok": True, **result}

    @router.post("/api/moderator/users/{user}/mute")
    async def mod_mute(user: str, body: ModActionRequest) -> Dict[str, Any]:
        """Mute a user (prevent them from posting)."""
        result = mod_console.mute_user(user, reason=body.reason, by=body.by)
        return {"ok": True, **result}

    @router.post("/api/moderator/users/{user}/unmute")
    async def mod_unmute(user: str, body: ModActionRequest) -> Dict[str, Any]:
        """Unmute a user."""
        result = mod_console.unmute_user(user, by=body.by)
        return {"ok": True, **result}

    @router.post("/api/moderator/users/{user}/kick")
    async def mod_kick(user: str, body: ModActionRequest) -> Dict[str, Any]:
        """Kick a user from a channel."""
        result = mod_console.kick_user(user, reason=body.reason, by=body.by)
        return {"ok": True, **result}

    @router.post("/api/moderator/users/{user}/ban")
    async def mod_ban(user: str, body: ModActionRequest) -> Dict[str, Any]:
        """Ban a user."""
        result = mod_console.ban_user(user, reason=body.reason, by=body.by)
        return {"ok": True, **result}

    @router.post("/api/moderator/users/{user}/unban")
    async def mod_unban(user: str, body: ModActionRequest) -> Dict[str, Any]:
        """Unban a user."""
        result = mod_console.unban_user(user, by=body.by)
        return {"ok": True, **result}

    @router.delete("/api/moderator/messages/{channel}/{mid}")
    async def mod_delete_message(channel: str, mid: str, by: str = "moderator", reason: str = "") -> Dict[str, Any]:
        """Delete a message (moderator action)."""
        result = mod_console.delete_message(channel=channel, message_id=mid, by=by, reason=reason)
        return result

    # ── Auto-moderation ──────────────────────────────────────────────────

    @router.get("/api/moderator/automod/words")
    async def mod_list_blocked_words() -> Dict[str, Any]:
        """List default and custom blocked words."""
        return {"ok": True, "blocked_words": mod_console.list_blocked_words()}

    @router.post("/api/moderator/automod/words")
    async def mod_add_blocked_words(body: AddBlockedWordsRequest) -> Dict[str, Any]:
        """Add custom blocked words to the auto-moderation list."""
        updated = mod_console.add_blocked_words(body.words, by=body.by)
        return {"ok": True, "custom_blocked_words": updated}

    @router.delete("/api/moderator/automod/words/{word}")
    async def mod_remove_blocked_word(word: str, by: str = "moderator") -> Dict[str, Any]:
        """Remove a custom blocked word."""
        updated = mod_console.remove_blocked_word(word, by=by)
        return {"ok": True, "custom_blocked_words": updated}

    @router.post("/api/moderator/automod/check")
    async def mod_check_content(body: CheckContentRequest) -> Dict[str, Any]:
        """Check a piece of content against the auto-moderation rules."""
        result = mod_console.check_content(body.text)
        return {"ok": True, "automod": result}

    # ── Broadcast ─────────────────────────────────────────────────────────

    @router.get("/api/moderator/broadcast/targets")
    async def mod_list_targets() -> Dict[str, Any]:
        """List all registered broadcast targets."""
        return {"ok": True, "targets": mod_console.list_targets()}

    @router.post("/api/moderator/broadcast/targets")
    async def mod_register_target(body: RegisterTargetRequest) -> Dict[str, Any]:
        """Register a channel as a broadcast target for a given platform."""
        try:
            mod_console.register_target(body.platform, body.channel_id, by=body.by)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True, "targets": mod_console.list_targets()}

    @router.delete("/api/moderator/broadcast/targets/{platform}/{channel_id}")
    async def mod_unregister_target(
        platform: str, channel_id: str, by: str = "moderator"
    ) -> Dict[str, Any]:
        """Unregister a broadcast target."""
        mod_console.unregister_target(platform, channel_id, by=by)
        return {"ok": True, "targets": mod_console.list_targets()}

    @router.post("/api/moderator/broadcast")
    async def mod_broadcast(body: BroadcastRequest) -> Dict[str, Any]:
        """Broadcast a message to multiple platforms simultaneously."""
        result = mod_console.broadcast(
            message=body.message,
            platforms=body.platforms,
            sender=body.sender,
            subject=body.subject,
            priority=body.priority,
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Broadcast failed"))
        return result

    @router.get("/api/moderator/broadcast/history")
    async def mod_broadcast_history(limit: int = 50) -> Dict[str, Any]:
        """Get broadcast history."""
        return {"ok": True, "broadcasts": mod_console.broadcast_history(limit=limit)}

    @router.get("/api/moderator/audit")
    async def mod_audit_log(limit: int = 100) -> Dict[str, Any]:
        """Get the moderator audit log."""
        return {"ok": True, "audit_log": mod_console.get_audit_log(limit=limit)}

    return router
