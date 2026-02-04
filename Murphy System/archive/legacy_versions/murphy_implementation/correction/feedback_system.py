"""
Human Feedback Capture System
Comprehensive system for collecting, categorizing, validating, and analyzing human feedback.
Covers Tasks 2.1, 2.2, 2.3, and 2.4.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid
from collections import defaultdict
import statistics


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
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
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
        cutoff = datetime.utcnow() - timedelta(days=days)
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
            "daily_average": sum(by_day.values()) / len(by_day),
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
        feedback.metadata["validation"] = validation.dict()
        
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
            feedback.reviewed_at = datetime.utcnow()
        elif status in [FeedbackStatus.IMPLEMENTED, FeedbackStatus.REJECTED]:
            feedback.resolved_at = datetime.utcnow()
        
        return True
    
    def get_pending_feedback(self) -> List[Feedback]:
        """Get all pending feedback."""
        return [
            f for f in self.all_feedback.values()
            if f.status == FeedbackStatus.SUBMITTED
        ]