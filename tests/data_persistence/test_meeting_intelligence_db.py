"""
Tests for Meeting Intelligence DB Persistence

Validates:
- MeetingDraft and MeetingVote ORM models exist in src.db
- DB models can be instantiated and persisted
- Round-trip: write then read back

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Force SQLite in-memory for tests
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMeetingDraftModel:
    """Test MeetingDraft ORM model."""

    def test_model_importable(self):
        from src.db import MeetingDraft
        assert MeetingDraft.__tablename__ == "meeting_drafts"

    def test_model_columns(self):
        from src.db import MeetingDraft
        cols = {c.name for c in MeetingDraft.__table__.columns}
        assert "session_id" in cols
        assert "draft_type" in cols
        assert "content" in cols
        assert "status" in cols

    def test_create_and_query(self):
        from src.db import Base, MeetingDraft
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            db.add(MeetingDraft(
                session_id="test-session",
                draft_type="agenda",
                content="Discuss roadmap",
                status="saved",
            ))
            db.commit()
            result = db.query(MeetingDraft).filter_by(session_id="test-session").first()
            assert result is not None
            assert result.draft_type == "agenda"
            assert result.content == "Discuss roadmap"
        finally:
            db.close()


class TestMeetingVoteModel:
    """Test MeetingVote ORM model."""

    def test_model_importable(self):
        from src.db import MeetingVote
        assert MeetingVote.__tablename__ == "meeting_votes"

    def test_model_columns(self):
        from src.db import MeetingVote
        cols = {c.name for c in MeetingVote.__table__.columns}
        assert "session_id" in cols
        assert "draft_type" in cols
        assert "vote" in cols
        assert "comment" in cols

    def test_create_and_query(self):
        from src.db import Base, MeetingVote
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            db.add(MeetingVote(
                session_id="test-session",
                draft_type="agenda",
                vote="approve",
                comment="Looks good",
            ))
            db.commit()
            result = db.query(MeetingVote).filter_by(session_id="test-session").first()
            assert result is not None
            assert result.vote == "approve"
            assert result.comment == "Looks good"
        finally:
            db.close()

    def test_multiple_votes_per_session(self):
        from src.db import Base, MeetingVote
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            for i in range(3):
                db.add(MeetingVote(
                    session_id="multi-session",
                    draft_type="agenda",
                    vote=f"vote-{i}",
                    comment=f"comment-{i}",
                    voter_id=f"user-{i}",
                ))
            db.commit()
            votes = db.query(MeetingVote).filter_by(session_id="multi-session").all()
            assert len(votes) == 3
        finally:
            db.close()
