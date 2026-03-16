"""Avatar identity data models."""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AvatarVoice(str, Enum):
    """Avatar voice (str subclass)."""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    AUTHORITATIVE = "authoritative"
    EMPATHETIC = "empathetic"
    NEUTRAL = "neutral"
    ENERGETIC = "energetic"


class AvatarStyle(str, Enum):
    """Avatar style (str subclass)."""
    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    EXECUTIVE = "executive"
    CREATIVE = "creative"
    SUPPORTIVE = "supportive"


class AvatarProfile(BaseModel):
    """Avatar profile."""
    avatar_id: str
    name: str
    voice: AvatarVoice = AvatarVoice.PROFESSIONAL
    style: AvatarStyle = AvatarStyle.FORMAL
    personality_traits: Dict[str, float] = {}
    knowledge_domains: List[str] = []
    greeting_template: str = "Hello, I'm {name}. How can I assist you?"
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = {}


class UserAdaptation(BaseModel):
    """User adaptation."""
    user_id: str
    avatar_id: str
    interaction_count: int = 0
    preferred_response_length: str = "medium"
    preferred_formality: float = 0.5
    topics_of_interest: List[str] = []
    behavioral_score: float = 1.0
    last_interaction: Optional[datetime] = None
    feedback_history: List[Dict[str, Any]] = []


class SentimentResult(BaseModel):
    """Sentiment result."""
    text: str
    sentiment: str
    confidence: float
    emotions: Dict[str, float] = {}


class CostEntry(BaseModel):
    """Cost entry."""
    entry_id: str
    avatar_id: str
    service: str
    operation: str
    cost_usd: float
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class ComplianceViolation(BaseModel):
    """Compliance violation."""
    violation_id: str
    avatar_id: str
    rule: str
    description: str
    severity: str
    timestamp: datetime
    resolved: bool = False


class AvatarSession(BaseModel):
    """Avatar session."""
    session_id: str
    avatar_id: str
    user_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    message_count: int = 0
    total_cost_usd: float = 0.0
    active: bool = True
