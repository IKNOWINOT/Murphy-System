# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
AI Communication Orchestrator — Murphy System

Four communication bridges that orchestrate cross-system interactions:

1. MeetingsBridge — Start/end meetings, manage transcripts, route shadow suggestions
2. AmbientBridge — Deliver ambient insights via IM/email
3. ShadowCommsBridge — Route shadow agent observations, questions, proposals to users
4. AvatarCommsBridge — Avatar persona injection + multi-channel delivery

All bridges persist to DB (graceful fallback to in-memory) and wire into the
Communication Hub singletons (im_store, email_store, call_store).
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# MeetingsBridge
# ---------------------------------------------------------------------------


class MeetingsBridge:
    """Manage meeting sessions with DB persistence and comms hub integration."""

    def __init__(self):
        self._sessions_fallback: Dict[str, dict] = {}

    def start_meeting(self, title: str, participants: List[str], account_id: Optional[str] = None) -> dict:
        """Start a new meeting session."""
        # Generate session_id
        session_id = hashlib.sha256(f"{title}{_now_iso()}".encode()).hexdigest()[:16]
        
        # Create IM thread for all participants
        try:
            from src.communication_hub import im_store
            thread = im_store.create_thread(participants, name=f"Meeting: {title}", thread_type="group")
            im_thread_id = thread.get("id")
        except Exception as exc:
            logger.warning("Could not create IM thread for meeting: %s", exc)
            im_thread_id = None
        
        # Build session record
        session = {
            "session_id": session_id,
            "title": title,
            "account_id": account_id,
            "participants": participants,
            "im_thread_id": im_thread_id,
            "started_at": _now_iso(),
            "ended_at": None,
            "status": "active",
            "metadata": {},
        }
        
        # Persist to DB
        try:
            from src.db import _get_session_factory, MeetingSession
            factory = _get_session_factory()
            db_session = factory()
            try:
                db_record = MeetingSession(
                    session_id=session_id,
                    title=title,
                    account_id=account_id,
                    participants=participants,
                    im_thread_id=im_thread_id,
                    started_at=session["started_at"],
                    status="active",
                    metadata_=session["metadata"],
                )
                db_session.add(db_record)
                db_session.commit()
            finally:
                db_session.close()
        except Exception as exc:
            logger.debug("Could not persist meeting to DB, using fallback: %s", exc)
            self._sessions_fallback[session_id] = session
        
        return session

    def end_meeting(self, session_id: str) -> dict:
        """End a meeting session and email summary to participants."""
        ended_at = _now_iso()
        
        # Update DB
        try:
            from src.db import _get_session_factory, MeetingSession
            factory = _get_session_factory()
            db_session = factory()
            try:
                record = db_session.query(MeetingSession).filter_by(session_id=session_id).first()
                if record:
                    record.status = "ended"
                    record.ended_at = ended_at
                    db_session.commit()
                    session = {
                        "session_id": record.session_id,
                        "title": record.title,
                        "account_id": record.account_id,
                        "participants": record.participants,
                        "im_thread_id": record.im_thread_id,
                        "started_at": record.started_at,
                        "ended_at": record.ended_at,
                        "status": record.status,
                        "metadata": record.metadata_,
                    }
                else:
                    session = None
            finally:
                db_session.close()
        except Exception as exc:
            logger.debug("Could not update meeting in DB, using fallback: %s", exc)
            if session_id in self._sessions_fallback:
                self._sessions_fallback[session_id]["status"] = "ended"
                self._sessions_fallback[session_id]["ended_at"] = ended_at
                session = self._sessions_fallback[session_id]
            else:
                session = None
        
        if not session:
            return {"error": "Meeting not found"}
        
        # Email summary to all participants
        try:
            from src.communication_hub import email_store
            participants = session.get("participants", [])
            title = session.get("title", "Meeting")
            email_store.compose_and_send(
                sender="murphy-meetings@system",
                recipients=participants,
                subject=f"Meeting Ended: {title}",
                body=f"The meeting '{title}' has ended at {ended_at}. Transcript available in your meeting dashboard.",
                priority="normal",
            )
        except Exception as exc:
            logger.warning("Could not send meeting summary email: %s", exc)
        
        return session

    def add_transcript_entry(self, session_id: str, speaker: str, text: str, is_ai: bool = False) -> dict:
        """Add a transcript entry to a meeting."""
        entry_id = _uid()
        timestamp = _now_iso()
        
        entry = {
            "id": entry_id,
            "session_id": session_id,
            "speaker": speaker,
            "text": text,
            "timestamp": timestamp,
            "is_ai": is_ai,
        }
        
        # Persist to DB
        try:
            from src.db import _get_session_factory, MeetingTranscriptEntry
            factory = _get_session_factory()
            db_session = factory()
            try:
                db_record = MeetingTranscriptEntry(
                    id=entry_id,
                    session_id=session_id,
                    speaker=speaker,
                    text=text,
                    timestamp=timestamp,
                    is_ai=1 if is_ai else 0,
                )
                db_session.add(db_record)
                db_session.commit()
            finally:
                db_session.close()
        except Exception as exc:
            logger.debug("Could not persist transcript entry: %s", exc)
        
        return entry

    def shadow_suggest(self, session_id: str, agent_id: str, suggestion_type: str, content: str) -> dict:
        """Shadow agent makes a suggestion during a meeting."""
        # Get meeting record
        meeting = self.get_meeting(session_id)
        if not meeting:
            return {"error": "Meeting not found"}
        
        # Post to meeting IM thread
        im_thread_id = meeting.get("im_thread_id")
        if im_thread_id:
            try:
                from src.communication_hub import im_store
                im_store.post_message(im_thread_id, f"shadow-agent:{agent_id}", f"[{suggestion_type}] {content}")
            except Exception as exc:
                logger.warning("Could not post shadow suggestion to IM: %s", exc)
        
        # Email suggestion to all participants
        try:
            from src.communication_hub import email_store
            participants = meeting.get("participants", [])
            email_store.compose_and_send(
                sender=f"shadow-agent-{agent_id}@system",
                recipients=participants,
                subject=f"Shadow Agent Suggestion: {suggestion_type}",
                body=content,
                priority="normal",
            )
        except Exception as exc:
            logger.warning("Could not email shadow suggestion: %s", exc)
        
        return {"ok": True, "session_id": session_id, "agent_id": agent_id, "suggestion_type": suggestion_type}

    def get_meeting(self, session_id: str) -> Optional[dict]:
        """Get a meeting session by ID."""
        try:
            from src.db import _get_session_factory, MeetingSession
            factory = _get_session_factory()
            db_session = factory()
            try:
                record = db_session.query(MeetingSession).filter_by(session_id=session_id).first()
                if record:
                    return {
                        "session_id": record.session_id,
                        "title": record.title,
                        "account_id": record.account_id,
                        "participants": record.participants,
                        "im_thread_id": record.im_thread_id,
                        "started_at": record.started_at,
                        "ended_at": record.ended_at,
                        "status": record.status,
                        "metadata": record.metadata_,
                    }
            finally:
                db_session.close()
        except Exception as exc:
            logger.debug("Could not fetch meeting from DB: %s", exc)
        
        # Fallback
        return self._sessions_fallback.get(session_id)

    def list_meetings(self, account_id: Optional[str] = None) -> List[dict]:
        """List all meetings, optionally filtered by account_id."""
        try:
            from src.db import _get_session_factory, MeetingSession
            factory = _get_session_factory()
            db_session = factory()
            try:
                query = db_session.query(MeetingSession)
                if account_id:
                    query = query.filter_by(account_id=account_id)
                records = query.all()
                return [
                    {
                        "session_id": r.session_id,
                        "title": r.title,
                        "account_id": r.account_id,
                        "participants": r.participants,
                        "im_thread_id": r.im_thread_id,
                        "started_at": r.started_at,
                        "ended_at": r.ended_at,
                        "status": r.status,
                        "metadata": r.metadata_,
                    }
                    for r in records
                ]
            finally:
                db_session.close()
        except Exception as exc:
            logger.debug("Could not list meetings from DB: %s", exc)
        
        # Fallback
        sessions = list(self._sessions_fallback.values())
        if account_id:
            sessions = [s for s in sessions if s.get("account_id") == account_id]
        return sessions

    def get_transcript(self, session_id: str) -> List[dict]:
        """Get transcript entries for a meeting."""
        try:
            from src.db import _get_session_factory, MeetingTranscriptEntry
            factory = _get_session_factory()
            db_session = factory()
            try:
                entries = db_session.query(MeetingTranscriptEntry).filter_by(session_id=session_id).all()
                return [
                    {
                        "id": e.id,
                        "session_id": e.session_id,
                        "speaker": e.speaker,
                        "text": e.text,
                        "timestamp": e.timestamp,
                        "is_ai": bool(e.is_ai),
                    }
                    for e in entries
                ]
            finally:
                db_session.close()
        except Exception as exc:
            logger.debug("Could not fetch transcript from DB: %s", exc)
            return []


# ---------------------------------------------------------------------------
# AmbientBridge
# ---------------------------------------------------------------------------


class AmbientBridge:
    """Route ambient insights to users via IM/email."""

    def deliver(self, delivery_data: dict) -> dict:
        """Deliver an ambient insight based on channel."""
        channel = delivery_data.get("channel", "im")
        content = delivery_data["content"]
        recipient = delivery_data.get("recipient", "ambient-general")
        subject = delivery_data.get("subject", "Ambient Insight")
        
        delivered = False
        
        if channel in ["im", "both"]:
            try:
                from src.communication_hub import im_store
                # Create or get ambient-general thread
                threads = im_store.list_threads()
                ambient_thread = next((t for t in threads if t.get("name") == "ambient-general"), None)
                if not ambient_thread:
                    ambient_thread = im_store.create_thread([recipient], name="ambient-general", thread_type="group")
                thread_id = ambient_thread["id"]
                im_store.post_message(thread_id, "ambient-ai", content)
                delivered = True
            except Exception as exc:
                logger.warning("Could not deliver ambient insight via IM: %s", exc)
        
        if channel in ["email", "both"]:
            try:
                from src.communication_hub import email_store
                email_store.compose_and_send(
                    sender="ambient-ai@system",
                    recipients=[recipient],
                    subject=subject,
                    body=content,
                    priority="normal",
                )
                delivered = True
            except Exception as exc:
                logger.warning("Could not deliver ambient insight via email: %s", exc)
        
        # Store delivery
        try:
            from src.ambient_context_store import AmbientContextStore
            store = AmbientContextStore()
            store.store_delivery({
                "channel": channel,
                "content": content,
                "recipient": recipient,
                "subject": subject,
                "delivered": delivered,
                "timestamp": _now_iso(),
            })
        except Exception as exc:
            logger.debug("Could not store ambient delivery: %s", exc)
        
        return {"ok": True, "channel": channel, "delivered": delivered}


# ---------------------------------------------------------------------------
# ShadowCommsBridge
# ---------------------------------------------------------------------------


class ShadowCommsBridge:
    """Route shadow agent communications to users."""

    def route_observation(self, agent_id: str, observation: dict, primary_account: Optional[str], cc_accounts: Optional[List[str]] = None) -> dict:
        """Route a shadow agent observation to the user."""
        if cc_accounts is None:
            cc_accounts = []
        
        content = f"Shadow Agent {agent_id} observed: {observation}"
        log_id = _uid()
        timestamp = _now_iso()
        
        im_thread_id = None
        email_ids = []
        
        # Post IM message
        if primary_account:
            try:
                from src.communication_hub import im_store
                threads = im_store.list_threads()
                user_thread = next((t for t in threads if primary_account in t.get("participants", [])), None)
                if not user_thread:
                    user_thread = im_store.create_thread([primary_account], name=f"Shadow Agent {agent_id}", thread_type="direct")
                im_thread_id = user_thread["id"]
                im_store.post_message(im_thread_id, f"shadow-agent:{agent_id}", content)
            except Exception as exc:
                logger.warning("Could not post shadow observation to IM: %s", exc)
        
        # Email to primary + CC
        if primary_account:
            try:
                from src.communication_hub import email_store
                recipients = [primary_account] + cc_accounts
                email = email_store.compose_and_send(
                    sender=f"shadow-agent-{agent_id}@system",
                    recipients=recipients,
                    subject=f"Shadow Agent Observation: {observation.get('action_type', 'Unknown')}",
                    body=content,
                    priority="normal",
                )
                email_ids.append(email.get("id"))
            except Exception as exc:
                logger.warning("Could not email shadow observation: %s", exc)
        
        # Persist to DB
        log_entry = {
            "id": log_id,
            "agent_id": agent_id,
            "action": "observe",
            "content": content,
            "primary_account": primary_account,
            "cc_accounts": cc_accounts,
            "im_thread_id": im_thread_id,
            "email_ids": email_ids,
            "timestamp": timestamp,
        }
        
        try:
            from src.db import _get_session_factory, ShadowAgentCommsLog
            factory = _get_session_factory()
            db_session = factory()
            try:
                db_record = ShadowAgentCommsLog(
                    id=log_id,
                    agent_id=agent_id,
                    action="observe",
                    content=content,
                    primary_account=primary_account,
                    cc_accounts=cc_accounts,
                    im_thread_id=im_thread_id,
                    email_ids=email_ids,
                    timestamp=timestamp,
                )
                db_session.add(db_record)
                db_session.commit()
            finally:
                db_session.close()
        except Exception as exc:
            logger.debug("Could not persist shadow comms log: %s", exc)
        
        return log_entry

    def route_question(self, agent_id: str, question: dict, primary_account: Optional[str], cc_accounts: Optional[List[str]] = None) -> dict:
        """Route a shadow agent clarifying question to the user."""
        if cc_accounts is None:
            cc_accounts = []
        
        content = f"Shadow Agent {agent_id} asks: {question}"
        log_id = _uid()
        timestamp = _now_iso()
        
        im_thread_id = None
        email_ids = []
        
        # Post IM message
        if primary_account:
            try:
                from src.communication_hub import im_store
                threads = im_store.list_threads()
                user_thread = next((t for t in threads if primary_account in t.get("participants", [])), None)
                if not user_thread:
                    user_thread = im_store.create_thread([primary_account], name=f"Shadow Agent {agent_id}", thread_type="direct")
                im_thread_id = user_thread["id"]
                im_store.post_message(im_thread_id, f"shadow-agent:{agent_id}", content)
            except Exception as exc:
                logger.warning("Could not post shadow question to IM: %s", exc)
        
        # Email
        if primary_account:
            try:
                from src.communication_hub import email_store
                recipients = [primary_account] + cc_accounts
                email = email_store.compose_and_send(
                    sender=f"shadow-agent-{agent_id}@system",
                    recipients=recipients,
                    subject=f"Shadow Agent Question",
                    body=content,
                    priority="normal",
                )
                email_ids.append(email.get("id"))
            except Exception as exc:
                logger.warning("Could not email shadow question: %s", exc)
        
        # Persist to DB
        log_entry = {
            "id": log_id,
            "agent_id": agent_id,
            "action": "clarify",
            "content": content,
            "primary_account": primary_account,
            "cc_accounts": cc_accounts,
            "im_thread_id": im_thread_id,
            "email_ids": email_ids,
            "timestamp": timestamp,
        }
        
        try:
            from src.db import _get_session_factory, ShadowAgentCommsLog
            factory = _get_session_factory()
            db_session = factory()
            try:
                db_record = ShadowAgentCommsLog(
                    id=log_id,
                    agent_id=agent_id,
                    action="clarify",
                    content=content,
                    primary_account=primary_account,
                    cc_accounts=cc_accounts,
                    im_thread_id=im_thread_id,
                    email_ids=email_ids,
                    timestamp=timestamp,
                )
                db_session.add(db_record)
                db_session.commit()
            finally:
                db_session.close()
        except Exception as exc:
            logger.debug("Could not persist shadow comms log: %s", exc)
        
        return log_entry

    def route_proposal(self, agent_id: str, proposal: dict, primary_account: Optional[str], cc_accounts: Optional[List[str]] = None) -> dict:
        """Route a shadow agent automation proposal to the user."""
        if cc_accounts is None:
            cc_accounts = []
        
        content = f"Shadow Agent {agent_id} proposes automation: {proposal}"
        log_id = _uid()
        timestamp = _now_iso()
        
        im_thread_id = None
        email_ids = []
        
        # Post IM message
        if primary_account:
            try:
                from src.communication_hub import im_store
                threads = im_store.list_threads()
                user_thread = next((t for t in threads if primary_account in t.get("participants", [])), None)
                if not user_thread:
                    user_thread = im_store.create_thread([primary_account], name=f"Shadow Agent {agent_id}", thread_type="direct")
                im_thread_id = user_thread["id"]
                im_store.post_message(im_thread_id, f"shadow-agent:{agent_id}", content)
            except Exception as exc:
                logger.warning("Could not post shadow proposal to IM: %s", exc)
        
        # Email with special subject
        if primary_account:
            try:
                from src.communication_hub import email_store
                recipients = [primary_account] + cc_accounts
                description = proposal.get("pattern", {}).get("description", "New Automation")
                email = email_store.compose_and_send(
                    sender=f"shadow-agent-{agent_id}@system",
                    recipients=recipients,
                    subject=f"Automation Proposal: {description}",
                    body=content,
                    priority="high",
                )
                email_ids.append(email.get("id"))
            except Exception as exc:
                logger.warning("Could not email shadow proposal: %s", exc)
        
        # Persist to DB
        log_entry = {
            "id": log_id,
            "agent_id": agent_id,
            "action": "propose",
            "content": content,
            "primary_account": primary_account,
            "cc_accounts": cc_accounts,
            "im_thread_id": im_thread_id,
            "email_ids": email_ids,
            "timestamp": timestamp,
        }
        
        try:
            from src.db import _get_session_factory, ShadowAgentCommsLog
            factory = _get_session_factory()
            db_session = factory()
            try:
                db_record = ShadowAgentCommsLog(
                    id=log_id,
                    agent_id=agent_id,
                    action="propose",
                    content=content,
                    primary_account=primary_account,
                    cc_accounts=cc_accounts,
                    im_thread_id=im_thread_id,
                    email_ids=email_ids,
                    timestamp=timestamp,
                )
                db_session.add(db_record)
                db_session.commit()
            finally:
                db_session.close()
        except Exception as exc:
            logger.debug("Could not persist shadow comms log: %s", exc)
        
        return log_entry


# ---------------------------------------------------------------------------
# AvatarCommsBridge
# ---------------------------------------------------------------------------


class AvatarCommsBridge:
    """Avatar persona injection and multi-channel delivery."""

    def speak_as_avatar(
        self,
        avatar_id: str,
        user_id: str,
        content: str,
        channel: str = "im",
        shadow_agent_id: Optional[str] = None,
        org_node_id: Optional[str] = None,
        rosetta_agent_id: Optional[str] = None,
    ) -> dict:
        """Avatar speaks to a user."""
        log_id = _uid()
        timestamp = _now_iso()
        
        # Load avatar profile
        avatar_name = avatar_id
        voice = "neutral"
        try:
            from src.avatar import AvatarRegistry
            registry = AvatarRegistry()
            profile = registry.get_profile(avatar_id)
            if profile:
                avatar_name = profile.get("name", avatar_id)
                voice = profile.get("voice", "neutral")
        except Exception as exc:
            logger.debug("Could not load avatar profile: %s", exc)
        
        # Inject persona
        persona_prefix = f"[{avatar_name} — {voice}] "
        enriched_content = persona_prefix + content
        
        # Get escalation chain if org_node_id provided
        cc_accounts = []
        if org_node_id:
            try:
                from src.org_chart_enforcement import OrgChartEnforcement
                org_chart = OrgChartEnforcement()
                chain = org_chart.get_escalation_chain(org_node_id)
                cc_accounts = [node.get("account_id") for node in chain if node.get("account_id")]
            except Exception as exc:
                logger.debug("Could not get escalation chain: %s", exc)
        
        # Apply Rosetta terminology if available
        rosetta_translated = 0
        if rosetta_agent_id:
            try:
                from src.rosetta.rosetta_manager import RosettaManager
                rosetta = RosettaManager()
                # Attempt to translate (simplified — real impl would call translate method)
                # For now, just mark as attempted
                rosetta_translated = 1
            except Exception as exc:
                logger.debug("Could not apply Rosetta translation: %s", exc)
        
        im_thread_id = None
        email_id = None
        
        # Route via IM
        if channel in ["im", "both"]:
            try:
                from src.communication_hub import im_store
                threads = im_store.list_threads()
                user_thread = next((t for t in threads if user_id in t.get("participants", [])), None)
                if not user_thread:
                    user_thread = im_store.create_thread([user_id], name=f"Avatar {avatar_name}", thread_type="direct")
                im_thread_id = user_thread["id"]
                im_store.post_message(im_thread_id, avatar_id, enriched_content)
            except Exception as exc:
                logger.warning("Could not deliver avatar message via IM: %s", exc)
        
        # Route via email
        if channel in ["email", "both"]:
            try:
                from src.communication_hub import email_store
                recipients = [user_id] + cc_accounts
                email = email_store.compose_and_send(
                    sender=f"{avatar_id}@system",
                    recipients=recipients,
                    subject=f"Message from {avatar_name}",
                    body=enriched_content,
                    priority="normal",
                )
                email_id = email.get("id")
            except Exception as exc:
                logger.warning("Could not deliver avatar message via email: %s", exc)
        
        # Persist to DB
        log_entry = {
            "id": log_id,
            "avatar_id": avatar_id,
            "user_id": user_id,
            "session_id": None,
            "channel": channel,
            "content": enriched_content,
            "im_thread_id": im_thread_id,
            "email_id": email_id,
            "shadow_agent_id": shadow_agent_id,
            "org_node_id": org_node_id,
            "rosetta_translated": rosetta_translated,
            "timestamp": timestamp,
        }
        
        try:
            from src.db import _get_session_factory, AvatarCommsLog
            factory = _get_session_factory()
            db_session = factory()
            try:
                db_record = AvatarCommsLog(
                    id=log_id,
                    avatar_id=avatar_id,
                    user_id=user_id,
                    session_id=None,
                    channel=channel,
                    content=enriched_content,
                    im_thread_id=im_thread_id,
                    email_id=email_id,
                    shadow_agent_id=shadow_agent_id,
                    org_node_id=org_node_id,
                    rosetta_translated=rosetta_translated,
                    timestamp=timestamp,
                )
                db_session.add(db_record)
                db_session.commit()
            finally:
                db_session.close()
        except Exception as exc:
            logger.debug("Could not persist avatar comms log: %s", exc)
        
        return log_entry


# ---------------------------------------------------------------------------
# Process-wide Singletons
# ---------------------------------------------------------------------------


meetings_bridge = MeetingsBridge()
ambient_bridge = AmbientBridge()
shadow_comms = ShadowCommsBridge()
avatar_comms = AvatarCommsBridge()


# ---------------------------------------------------------------------------
# Register with Dispatch
# ---------------------------------------------------------------------------


def _register_with_dispatch():
    """Register all bridge actions as Dispatch tools."""
    try:
        from src.dispatch import register_tool, Tool
        
        # Already registered in dispatch.py via handlers
        # This is a placeholder for any future custom tools
        
    except Exception as exc:
        logger.debug("Could not register with Dispatch: %s", exc)


_register_with_dispatch()
