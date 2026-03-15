"""
Human Feedback Capture System
Comprehensive system for collecting, categorizing, validating, and analyzing human feedback.
Covers Tasks 2.1, 2.2, 2.3, and 2.4.
"""

import logging
import statistics
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ============================================================================
# TASK 2.1: FEEDBACK COLLECTION INTERFACE
# ============================================================================

class FeedbackType(str, Enum):
    """Types of feedback."""
    CORRECTION = "correction"
    SUGGESTION = "suggestion"
    COMPLAINT = "complaint"
    PRAISE = "praise"
    QUESTION = "question"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"


class FeedbackPriority(str, Enum):
    """Priority levels for feedback."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FeedbackStatus(str, Enum):
    """Status of feedback."""
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    VALIDATED = "validated"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class Feedback(BaseModel):
    """Feedback from human users."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    feedback_type: FeedbackType
    priority: FeedbackPriority = FeedbackPriority.MEDIUM
    status: FeedbackStatus = FeedbackStatus.SUBMITTED

    # Content
    title: str
    description: str
    context: Dict[str, Any] = Field(default_factory=dict)

    # User info
    user_id: str
    user_role: Optional[str] = None

    # Related items
    task_id: Optional[str] = None
    correction_id: Optional[str] = None

    # Timestamps
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    # Metadata
    tags: List[str] = Field(default_factory=list)
    attachments: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeedbackCollectionInterface:
    """Interface for collecting feedback from users."""

    def __init__(self):
        self.feedback_queue: List[Feedback] = []
        self.templates: Dict[str, Dict[str, Any]] = {}
        self._initialize_templates()

    def _initialize_templates(self):
        """Initialize feedback templates."""
        self.templates = {
            "correction": {
                "title": "Correction Needed",
                "fields": ["what_is_wrong", "expected_output", "reasoning"],
                "priority": FeedbackPriority.HIGH
            },
            "bug_report": {
                "title": "Bug Report",
                "fields": ["steps_to_reproduce", "expected_behavior", "actual_behavior"],
                "priority": FeedbackPriority.HIGH
            },
            "suggestion": {
                "title": "Suggestion",
                "fields": ["suggestion", "benefits", "implementation_ideas"],
                "priority": FeedbackPriority.MEDIUM
            }
        }

    def collect_feedback(
        self,
        feedback_type: FeedbackType,
        title: str,
        description: str,
        user_id: str,
        **kwargs
    ) -> Feedback:
        """
        Collect feedback from a user.

        Args:
            feedback_type: Type of feedback
            title: Feedback title
            description: Detailed description
            user_id: User providing feedback
            **kwargs: Additional fields

        Returns:
            Feedback object
        """
        feedback = Feedback(
            feedback_type=feedback_type,
            title=title,
            description=description,
            user_id=user_id,
            priority=kwargs.get("priority", FeedbackPriority.MEDIUM),
            context=kwargs.get("context", {}),
            task_id=kwargs.get("task_id"),
            correction_id=kwargs.get("correction_id"),
            tags=kwargs.get("tags", []),
            metadata=kwargs.get("metadata", {})
        )

        self.feedback_queue.append(feedback)
        return feedback

    def collect_structured_feedback(
        self,
        template_name: str,
        user_id: str,
        field_values: Dict[str, Any]
    ) -> Feedback:
        """
        Collect feedback using a template.

        Args:
            template_name: Name of template to use
            user_id: User providing feedback
            field_values: Values for template fields

        Returns:
            Feedback object
        """
        template = self.templates.get(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")

        # Build description from fields
        description_parts = []
        for field in template["fields"]:
            if field in field_values:
                description_parts.append(f"{field}: {field_values[field]}")

        description = "\n".join(description_parts)

        feedback = Feedback(
            feedback_type=FeedbackType(template_name) if template_name in [t.value for t in FeedbackType] else FeedbackType.SUGGESTION,
            title=template["title"],
            description=description,
            user_id=user_id,
            priority=template["priority"],
            metadata={"template": template_name, "fields": field_values}
        )

        self.feedback_queue.append(feedback)
        return feedback

    def get_feedback_form(self, feedback_type: FeedbackType) -> Dict[str, Any]:
        """Get form structure for a feedback type."""
        template_name = feedback_type.value
        template = self.templates.get(template_name, {})

        return {
            "feedback_type": feedback_type,
            "title": template.get("title", "Feedback"),
            "fields": template.get("fields", ["description"]),
            "priority": template.get("priority", FeedbackPriority.MEDIUM)
        }


# ============================================================================
# TASK 2.2: FEEDBACK CATEGORIZATION
# ============================================================================

class FeedbackCategory(str, Enum):
    """Categories for feedback."""
    OUTPUT_QUALITY = "output_quality"
    PERFORMANCE = "performance"
    USABILITY = "usability"
    FUNCTIONALITY = "functionality"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    OTHER = "other"


class FeedbackCategorizer:
    """Automatically categorizes feedback."""

    def __init__(self):
        self.category_keywords = {
            FeedbackCategory.OUTPUT_QUALITY: ["wrong", "incorrect", "error", "mistake", "quality"],
            FeedbackCategory.PERFORMANCE: ["slow", "fast", "performance", "speed", "timeout"],
            FeedbackCategory.USABILITY: ["confusing", "difficult", "easy", "intuitive", "ux"],
            FeedbackCategory.FUNCTIONALITY: ["feature", "function", "capability", "missing"],
            FeedbackCategory.DOCUMENTATION: ["documentation", "docs", "help", "guide"],
            FeedbackCategory.SECURITY: ["security", "vulnerability", "exploit", "unsafe"]
        }

    def categorize(self, feedback: Feedback) -> List[FeedbackCategory]:
        """
        Categorize feedback based on content.

        Args:
            feedback: Feedback to categorize

        Returns:
            List of applicable categories
        """
        categories = []
        text = f"{feedback.title} {feedback.description}".lower()

        for category, keywords in self.category_keywords.items():
            if any(keyword in text for keyword in keywords):
                categories.append(category)

        if not categories:
            categories.append(FeedbackCategory.OTHER)

        return categories

    def categorize_batch(self, feedbacks: List[Feedback]) -> Dict[str, List[FeedbackCategory]]:
        """Categorize multiple feedbacks."""
        return {
            feedback.id: self.categorize(feedback)
            for feedback in feedbacks
        }


# ============================================================================
# TASK 2.3: FEEDBACK VALIDATION
# ============================================================================

class ValidationResult(BaseModel):
    """Result of feedback validation."""
    is_valid: bool
    confidence: float = Field(ge=0.0, le=1.0)
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class FeedbackValidator:
    """Validates feedback for quality and completeness."""

    def __init__(self):
        self.validation_rules: List[callable] = []
        self._initialize_rules()

    def _initialize_rules(self):
        """Initialize validation rules."""
        self.validation_rules = [
            self._validate_length,
            self._validate_clarity,
            self._validate_context,
            self._validate_actionability
        ]

    def validate(self, feedback: Feedback) -> ValidationResult:
        """
        Validate feedback.

        Args:
            feedback: Feedback to validate

        Returns:
            ValidationResult
        """
        issues = []
        suggestions = []

        for rule in self.validation_rules:
            rule_issues, rule_suggestions = rule(feedback)
            issues.extend(rule_issues)
            suggestions.extend(rule_suggestions)

        is_valid = len(issues) == 0
        confidence = 1.0 - (len(issues) * 0.2)  # Reduce confidence for each issue
        confidence = max(confidence, 0.0)

        return ValidationResult(
            is_valid=is_valid,
            confidence=confidence,
            issues=issues,
            suggestions=suggestions
        )

    def _validate_length(self, feedback: Feedback) -> Tuple[List[str], List[str]]:
        """Validate feedback length."""
        issues = []
        suggestions = []

        if len(feedback.description) < 10:
            issues.append("Description too short")
            suggestions.append("Provide more details about the issue")

        if len(feedback.title) < 5:
            issues.append("Title too short")
            suggestions.append("Use a more descriptive title")

        return issues, suggestions

    def _validate_clarity(self, feedback: Feedback) -> Tuple[List[str], List[str]]:
        """Validate feedback clarity."""
        issues = []
        suggestions = []

        # Check for vague words
        vague_words = ["something", "somehow", "maybe", "kind of"]
        text = feedback.description.lower()

        if any(word in text for word in vague_words):
            suggestions.append("Be more specific about the issue")

        return issues, suggestions

    def _validate_context(self, feedback: Feedback) -> Tuple[List[str], List[str]]:
        """Validate feedback context."""
        issues = []
        suggestions = []

        if not feedback.task_id and feedback.feedback_type == FeedbackType.CORRECTION:
            suggestions.append("Include task ID for better tracking")

        return issues, suggestions

    def _validate_actionability(self, feedback: Feedback) -> Tuple[List[str], List[str]]:
        """Validate if feedback is actionable."""
        issues = []
        suggestions = []

        # Check for action words
        action_words = ["should", "could", "need", "want", "fix", "change", "add"]
        text = feedback.description.lower()

        if not any(word in text for word in action_words):
            suggestions.append("Clearly state what action is needed")

        return issues, suggestions


# ============================================================================
# TASK 2.4: FEEDBACK ANALYTICS
# ============================================================================

class FeedbackAnalytics:
    """Analytics for feedback data."""

    def __init__(self):
        self.feedback_store: List[Feedback] = []

    def add_feedback(self, feedback: Feedback):
        """Add feedback to analytics."""
        self.feedback_store.append(feedback)

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall feedback statistics."""
        if not self.feedback_store:
            return {"total_feedback": 0}

        # Count by type
        by_type = defaultdict(int)
        for feedback in self.feedback_store:
            by_type[feedback.feedback_type.value] += 1

        # Count by priority
        by_priority = defaultdict(int)
        for feedback in self.feedback_store:
            by_priority[feedback.priority.value] += 1

        # Count by status
        by_status = defaultdict(int)
        for feedback in self.feedback_store:
            by_status[feedback.status.value] += 1

        # Calculate resolution time
        resolution_times = []
        for feedback in self.feedback_store:
            if feedback.resolved_at and feedback.submitted_at:
                delta = (feedback.resolved_at - feedback.submitted_at).total_seconds() / 3600
                resolution_times.append(delta)

        return {
            "total_feedback": len(self.feedback_store),
            "by_type": dict(by_type),
            "by_priority": dict(by_priority),
            "by_status": dict(by_status),
            "average_resolution_time_hours": statistics.mean(resolution_times) if resolution_times else 0,
            "pending_feedback": sum(1 for f in self.feedback_store if f.status == FeedbackStatus.SUBMITTED)
        }

    def get_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get feedback trends."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = [f for f in self.feedback_store if f.submitted_at >= cutoff]

        if not recent:
            return {"trend": "no_data"}

        # Group by day
        by_day = defaultdict(int)
        for feedback in recent:
            day = feedback.submitted_at.date()
            by_day[day] += 1

        # Calculate trend
        days_list = sorted(by_day.keys())
        if len(days_list) < 2:
            return {"trend": "insufficient_data"}

        mid = len(days_list) // 2
        first_half_avg = sum(by_day[d] for d in days_list[:mid]) / mid
        second_half_avg = sum(by_day[d] for d in days_list[mid:]) / (len(days_list) - mid)

        if second_half_avg > first_half_avg * 1.2:
            trend = "increasing"
        elif second_half_avg < first_half_avg * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "daily_average": sum(by_day.values()) / (len(by_day) or 1),
            "total_recent": len(recent)
        }

    def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a specific user."""
        user_feedback = [f for f in self.feedback_store if f.user_id == user_id]

        if not user_feedback:
            return {"total_feedback": 0}

        by_type = defaultdict(int)
        for feedback in user_feedback:
            by_type[feedback.feedback_type.value] += 1

        return {
            "total_feedback": len(user_feedback),
            "by_type": dict(by_type),
            "most_recent": user_feedback[-1].submitted_at.isoformat() if user_feedback else None
        }

    def identify_common_issues(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Identify most common issues from feedback."""
        # Extract keywords from feedback
        word_counts = defaultdict(int)

        for feedback in self.feedback_store:
            words = feedback.description.lower().split()
            # Filter out common words
            filtered_words = [w for w in words if len(w) > 4]
            for word in filtered_words:
                word_counts[word] += 1

        # Return top issues
        return sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:limit]


# ============================================================================
# UNIFIED FEEDBACK SYSTEM
# ============================================================================

class HumanFeedbackSystem:
    """
    Complete human feedback capture system.
    Integrates collection, categorization, validation, and analytics.
    """

    def __init__(self):
        self.collector = FeedbackCollectionInterface()
        self.categorizer = FeedbackCategorizer()
        self.validator = FeedbackValidator()
        self.analytics = FeedbackAnalytics()
        self.all_feedback: Dict[str, Feedback] = {}

    # Collection (Task 2.1)
    def collect_feedback(
        self,
        feedback_type: FeedbackType,
        title: str,
        description: str,
        user_id: str,
        **kwargs
    ) -> Feedback:
        """Collect feedback from user."""
        feedback = self.collector.collect_feedback(
            feedback_type, title, description, user_id, **kwargs
        )

        # Automatically categorize
        categories = self.categorizer.categorize(feedback)
        feedback.tags.extend([c.value for c in categories])

        # Validate
        validation = self.validator.validate(feedback)
        feedback.metadata["validation"] = validation.model_dump()

        # Store
        self.all_feedback[feedback.id] = feedback
        self.analytics.add_feedback(feedback)

        return feedback

    def collect_structured_feedback(
        self,
        template_name: str,
        user_id: str,
        field_values: Dict[str, Any]
    ) -> Feedback:
        """Collect structured feedback using template."""
        feedback = self.collector.collect_structured_feedback(
            template_name, user_id, field_values
        )

        categories = self.categorizer.categorize(feedback)
        feedback.tags.extend([c.value for c in categories])

        self.all_feedback[feedback.id] = feedback
        self.analytics.add_feedback(feedback)

        return feedback

    # Categorization (Task 2.2)
    def categorize_feedback(self, feedback_id: str) -> List[FeedbackCategory]:
        """Categorize feedback."""
        feedback = self.all_feedback.get(feedback_id)
        if not feedback:
            return []
        return self.categorizer.categorize(feedback)

    # Validation (Task 2.3)
    def validate_feedback(self, feedback_id: str) -> ValidationResult:
        """Validate feedback."""
        feedback = self.all_feedback.get(feedback_id)
        if not feedback:
            return ValidationResult(is_valid=False, confidence=0.0, issues=["Feedback not found"])
        return self.validator.validate(feedback)

    # Analytics (Task 2.4)
    def get_statistics(self) -> Dict[str, Any]:
        """Get feedback statistics."""
        return self.analytics.get_statistics()

    def get_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get feedback trends."""
        return self.analytics.get_trends(days)

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics."""
        return self.analytics.get_user_statistics(user_id)

    def get_common_issues(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get common issues."""
        return self.analytics.identify_common_issues(limit)

    # Utility methods
    def get_feedback(self, feedback_id: str) -> Optional[Feedback]:
        """Get feedback by ID."""
        return self.all_feedback.get(feedback_id)

    def update_feedback_status(
        self,
        feedback_id: str,
        status: FeedbackStatus
    ) -> bool:
        """Update feedback status."""
        feedback = self.all_feedback.get(feedback_id)
        if not feedback:
            return False

        feedback.status = status

        if status == FeedbackStatus.UNDER_REVIEW:
            feedback.reviewed_at = datetime.now(timezone.utc)
        elif status in [FeedbackStatus.IMPLEMENTED, FeedbackStatus.REJECTED]:
            feedback.resolved_at = datetime.now(timezone.utc)

        return True

    def get_pending_feedback(self) -> List[Feedback]:
        """Get all pending feedback."""
        return [
            f for f in self.all_feedback.values()
            if f.status == FeedbackStatus.SUBMITTED
        ]


# ============================================================================
# OPERATIONAL FEEDBACK COMPONENTS
# ============================================================================

class FeedbackEntry:
    """A single feedback entry for operational feedback tracking."""

    def __init__(self, feedback_id, feedback_type, operation_id, source,
                 success, confidence, rating=None, timestamp=None,
                 feedback_data=None, comments=None):
        self.feedback_id = feedback_id
        self.feedback_type = feedback_type
        self.operation_id = operation_id
        self.source = source
        self.success = success
        self.confidence = confidence
        self.rating = rating
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.feedback_data = feedback_data or {}
        self.comments = comments


class FeedbackStorage:
    """Storage for operational feedback entries."""

    def __init__(self, max_entries=1000):
        self.max_entries = max_entries
        self._entries: List[FeedbackEntry] = []
        self._index: Dict[str, FeedbackEntry] = {}

    def add_entry(self, entry: FeedbackEntry):
        capped_append(self._entries, entry)
        self._index[entry.feedback_id] = entry
        while len(self._entries) > self.max_entries:
            removed = self._entries.pop(0)
            self._index.pop(removed.feedback_id, None)

    def get_entry(self, feedback_id: str) -> Optional[FeedbackEntry]:
        return self._index.get(feedback_id)

    def get_entries_by_type(self, feedback_type: str) -> List[FeedbackEntry]:
        return [e for e in self._entries if e.feedback_type == feedback_type]

    def get_entries_by_operation(self, operation_id: str) -> List[FeedbackEntry]:
        return [e for e in self._entries if e.operation_id == operation_id]

    def get_entries_in_range(self, start_time: datetime, end_time: datetime) -> List[FeedbackEntry]:
        return [e for e in self._entries if start_time <= e.timestamp <= end_time]

    def get_recent_entries(self, count: int = 10) -> List[FeedbackEntry]:
        return self._entries[-count:]

    def get_all_entries(self) -> List[FeedbackEntry]:
        """Return a copy of all stored entries."""
        return self._entries[:]


class FeedbackAnalysis:
    """Result of operational feedback analysis."""

    def __init__(self, success_rate=0.0, average_confidence=0.0, issues=None,
                 feedback_type="", recommendations=None):
        self.success_rate = success_rate
        self.average_confidence = average_confidence
        self.issues = issues if issues is not None else []
        self.feedback_type = feedback_type
        self.recommendations = recommendations if recommendations is not None else []


class _TrackedIssue:
    """A tracked operational issue."""

    def __init__(self, issue_id, operation_id, issue_type, description, severity):
        self.issue_id = issue_id
        self.operation_id = operation_id
        self.issue_type = issue_type
        self.description = description
        self.severity = severity
        self.frequency = 1


class FeedbackAnalyzer:
    """Analyzer for operational feedback entries."""

    def __init__(self):
        self._tracked_issues: Dict[str, _TrackedIssue] = {}

    def analyze_feedback(self, entries: List[FeedbackEntry]) -> FeedbackAnalysis:
        if not entries:
            return FeedbackAnalysis()

        success_count = sum(1 for e in entries if e.success)
        success_rate = success_count / len(entries)
        average_confidence = sum(e.confidence for e in entries) / (len(entries) or 1)

        ops: Dict[str, Dict[str, int]] = defaultdict(lambda: {'success': 0, 'total': 0})
        type_counts: Dict[str, int] = defaultdict(int)
        for e in entries:
            ops[e.operation_id]['total'] += 1
            if e.success:
                ops[e.operation_id]['success'] += 1
            type_counts[e.feedback_type] += 1

        issues = []
        for op_id, counts in ops.items():
            rate = counts['success'] / counts['total'] if counts['total'] > 0 else 0
            if rate < 0.5:
                issues.append({'operation_id': op_id, 'success_rate': rate, 'total': counts['total']})

        feedback_type = max(type_counts, key=type_counts.get) if type_counts else ""

        recommendations = []
        if success_rate < 0.9:
            recommendations.append("Review operations with low success rates")
        for issue in issues:
            recommendations.append(f"Investigate operation {issue['operation_id']}")

        return FeedbackAnalysis(
            success_rate=success_rate,
            average_confidence=average_confidence,
            issues=issues,
            feedback_type=feedback_type,
            recommendations=recommendations
        )

    def track_issue(self, operation_id, issue_type, description, severity):
        issue_id = f"{operation_id}_{issue_type}"
        if issue_id in self._tracked_issues:
            self._tracked_issues[issue_id].frequency += 1
            return self._tracked_issues[issue_id]
        issue = _TrackedIssue(issue_id, operation_id, issue_type, description, severity)
        self._tracked_issues[issue_id] = issue
        return issue

    def get_tracked_issues(self):
        return list(self._tracked_issues.values())


class OperationalFeedbackSystem:
    """
    Operational feedback system providing operation-oriented feedback
    collection, analysis, and issue tracking.
    """

    def __init__(self, enable_feedback=True):
        self.enable_feedback = enable_feedback
        self.storage = FeedbackStorage()
        self.analyzer = FeedbackAnalyzer()
        self._counter = 0

    def collect_feedback(self, feedback_type, operation_id, source, success,
                         confidence, rating=None, comments=None,
                         feedback_data=None):
        if not self.enable_feedback:
            return ""

        self._counter += 1
        feedback_id = f"feedback_{self._counter}"

        entry = FeedbackEntry(
            feedback_id=feedback_id,
            feedback_type=feedback_type,
            operation_id=operation_id,
            source=source,
            success=success,
            confidence=confidence,
            rating=rating,
            timestamp=datetime.now(timezone.utc),
            feedback_data=feedback_data or {},
            comments=comments
        )

        self.storage.add_entry(entry)

        # Auto-detect issues for operations with enough data
        op_entries = self.storage.get_entries_by_operation(operation_id)
        if len(op_entries) >= 3:
            success_count = sum(1 for e in op_entries if e.success)
            rate = success_count / len(op_entries)
            if rate < 0.5:
                self.analyzer.track_issue(
                    operation_id=operation_id,
                    issue_type="low_success_rate",
                    description=f"Operation {operation_id} has {rate:.0%} success rate",
                    severity="high" if rate < 0.3 else "medium"
                )

        return feedback_id

    def analyze_recent_feedback(self, time_period="hour"):
        delta_map = {"hour": timedelta(hours=1), "day": timedelta(days=1), "week": timedelta(weeks=1)}
        delta = delta_map.get(time_period, timedelta(hours=1))
        now = datetime.now(timezone.utc)
        entries = self.storage.get_entries_in_range(now - delta, now)
        return self.analyzer.analyze_feedback(entries)

    def get_feedback_summary(self):
        entries = self.storage.get_all_entries()
        if not entries:
            return {'total_entries': 0, 'success_rate': 0.0, 'by_type': {}, 'by_source': {}}

        total = len(entries)
        success_count = sum(1 for e in entries if e.success)
        success_rate = success_count / total

        by_type: Dict[str, int] = defaultdict(int)
        by_source: Dict[str, int] = defaultdict(int)
        for e in entries:
            by_type[e.feedback_type] += 1
            by_source[e.source] += 1

        return {
            'total_entries': total,
            'success_rate': success_rate,
            'by_type': dict(by_type),
            'by_source': dict(by_source)
        }

    def get_tracked_issues(self):
        return self.analyzer.get_tracked_issues()

    def get_feedback_for_operation(self, operation_id):
        return self.storage.get_entries_by_operation(operation_id)

    def export_feedback_data(self):
        return {
            'summary': self.get_feedback_summary(),
            'issues': self.get_tracked_issues(),
            'recent_entries': self.storage.get_all_entries()
        }

    def reset_feedback(self):
        self.storage = FeedbackStorage()
        self.analyzer = FeedbackAnalyzer()
        self._counter = 0
