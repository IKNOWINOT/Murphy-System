"""
Avatar Identity Layer

Manages AI avatar identities with personality injection, user adaptation,
sentiment analysis, and third-party connector integration.
"""

from .avatar_models import (
    AvatarProfile,
    AvatarSession,
    AvatarStyle,
    AvatarVoice,
    ComplianceViolation,
    CostEntry,
    SentimentResult,
    UserAdaptation,
)
from .avatar_registry import AvatarRegistry
from .avatar_session_manager import AvatarSessionManager
from .behavioral_scoring_engine import BehavioralScoringEngine
from .compliance_guard import ComplianceGuard
from .cost_ledger import CostLedger
from .persona_injector import PersonaInjector
from .sentiment_classifier import SentimentClassifier
from .user_adaptation_engine import UserAdaptationEngine

__all__ = [
    "AvatarProfile",
    "AvatarRegistry",
    "AvatarSession",
    "AvatarSessionManager",
    "AvatarStyle",
    "AvatarVoice",
    "BehavioralScoringEngine",
    "ComplianceGuard",
    "ComplianceViolation",
    "CostEntry",
    "CostLedger",
    "PersonaInjector",
    "SentimentClassifier",
    "SentimentResult",
    "UserAdaptation",
    "UserAdaptationEngine",
]

__version__ = "1.0.0"
