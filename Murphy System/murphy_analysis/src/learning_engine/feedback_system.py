"""
Feedback System for Murphy System Runtime

This module provides comprehensive feedback collection and analysis capabilities:
- Collect feedback from operations
- Analyze feedback for patterns
- Generate improvement recommendations
- Track feedback over time
"""

import time
import json
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics


@dataclass
class FeedbackEntry:
    """Represents a single feedback entry"""
    feedback_id: str
    feedback_type: str  # 'operation', 'decision', 'workflow', 'integration'
    operation_id: str
    source: str  # 'system', 'human', 'automated'
    success: bool
    confidence: float  # 0.0 to 1.0
    rating: Optional[int]  # 1-5 if human feedback
    timestamp: datetime
    feedback_data: Dict[str, Any] = field(default_factory=dict)
    comments: Optional[str] = None


@dataclass
class FeedbackAnalysis:
    """Represents an analysis of feedback"""
    analysis_id: str
    feedback_type: str
    time_period: str
    success_rate: float
    average_confidence: float
    average_rating: Optional[float]
    trends: List[Dict[str, Any]]
    issues: List[Dict[str, Any]]
    recommendations: List[str]
    timestamp: datetime


@dataclass
class FeedbackIssue:
    """Represents an issue identified from feedback"""
    issue_id: str
    issue_type: str  # 'performance', 'reliability', 'accuracy', 'usability'
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    affected_operations: List[str]
    frequency: int
    first_seen: datetime
    last_seen: datetime
    recommended_actions: List[str]


class FeedbackStorage:
    """Storage for feedback entries"""
    
    def __init__(self, max_entries: int = 100000):
        self.max_entries = max_entries
        self.entries: deque = deque(maxlen=max_entries)
        self.entries_by_id: Dict[str, FeedbackEntry] = {}
        self.entries_by_type: Dict[str, List[str]] = defaultdict(list)
        self.entries_by_operation: Dict[str, List[str]] = defaultdict(list)
        self.lock = threading.Lock()
    
    def add_entry(self, entry: FeedbackEntry) -> None:
        """Add a feedback entry"""
        with self.lock:
            self.entries.append(entry)
            self.entries_by_id[entry.feedback_id] = entry
            self.entries_by_type[entry.feedback_type].append(entry.feedback_id)
            self.entries_by_operation[entry.operation_id].append(entry.feedback_id)
    
    def get_entry(self, feedback_id: str) -> Optional[FeedbackEntry]:
        """Get a feedback entry by ID"""
        return self.entries_by_id.get(feedback_id)
    
    def get_entries_by_type(self, feedback_type: str, 
                           limit: int = 100) -> List[FeedbackEntry]:
        """Get feedback entries of a specific type"""
        with self.lock:
            entry_ids = self.entries_by_type.get(feedback_type, [])
            return [self.entries_by_id[eid] for eid in entry_ids[-limit:]]
    
    def get_entries_by_operation(self, operation_id: str,
                                limit: int = 100) -> List[FeedbackEntry]:
        """Get feedback entries for a specific operation"""
        with self.lock:
            entry_ids = self.entries_by_operation.get(operation_id, [])
            return [self.entries_by_id[eid] for eid in entry_ids[-limit:]]
    
    def get_entries_in_range(self, start_time: datetime,
                            end_time: datetime) -> List[FeedbackEntry]:
        """Get feedback entries within a time range"""
        with self.lock:
            return [
                e for e in self.entries
                if start_time <= e.timestamp <= end_time
            ]
    
    def get_recent_entries(self, count: int = 10) -> List[FeedbackEntry]:
        """Get recent feedback entries"""
        with self.lock:
            entries_list = list(self.entries)
            return entries_list[-count:]


class FeedbackAnalyzer:
    """Analyzes feedback to identify patterns and issues"""
    
    def __init__(self):
        self.issues: Dict[str, FeedbackIssue] = {}
        self.lock = threading.Lock()
    
    def analyze_feedback(self, entries: List[FeedbackEntry]) -> FeedbackAnalysis:
        """Analyze feedback entries"""
        if not entries:
            return FeedbackAnalysis(
                analysis_id=f"analysis_{int(time.time())}",
                feedback_type="none",
                time_period="none",
                success_rate=0.0,
                average_confidence=0.0,
                average_rating=None,
                trends=[],
                issues=[],
                recommendations=[],
                timestamp=datetime.now()
            )
        
        # Group by type
        by_type = defaultdict(list)
        for entry in entries:
            by_type[entry.feedback_type].append(entry)
        
        # Calculate overall statistics
        total_entries = len(entries)
        successful = sum(1 for e in entries if e.success)
        success_rate = successful / total_entries if total_entries > 0 else 0.0
        
        confidences = [e.confidence for e in entries]
        avg_confidence = statistics.mean(confidences) if confidences else 0.0
        
        ratings = [e.rating for e in entries if e.rating is not None]
        avg_rating = statistics.mean(ratings) if ratings else None
        
        # Analyze trends
        trends = self._analyze_trends(entries)
        
        # Identify issues
        issues = self._identify_issues(entries)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(issues, success_rate, avg_confidence)
        
        # Determine time period
        if entries:
            time_span = entries[-1].timestamp - entries[0].timestamp
            if time_span < timedelta(hours=1):
                time_period = "last_hour"
            elif time_span < timedelta(days=1):
                time_period = "last_day"
            elif time_span < timedelta(weeks=1):
                time_period = "last_week"
            else:
                time_period = "last_month"
        else:
            time_period = "none"
        
        # Get primary feedback type
        primary_type = max(by_type.keys(), key=lambda k: len(by_type[k])) if by_type else "none"
        
        return FeedbackAnalysis(
            analysis_id=f"analysis_{int(time.time())}",
            feedback_type=primary_type,
            time_period=time_period,
            success_rate=success_rate,
            average_confidence=avg_confidence,
            average_rating=avg_rating,
            trends=trends,
            issues=issues,
            recommendations=recommendations,
            timestamp=datetime.now()
        )
    
    def _analyze_trends(self, entries: List[FeedbackEntry]) -> List[Dict[str, Any]]:
        """Analyze trends in feedback"""
        trends = []
        
        if len(entries) < 10:
            return trends
        
        # Split into two halves
        mid = len(entries) // 2
        first_half = entries[:mid]
        second_half = entries[mid:]
        
        # Compare success rates
        first_success_rate = sum(1 for e in first_half if e.success) / len(first_half)
        second_success_rate = sum(1 for e in second_half if e.success) / len(second_half)
        
        if abs(second_success_rate - first_success_rate) > 0.1:
            direction = "improving" if second_success_rate > first_success_rate else "declining"
            trends.append({
                'type': 'success_rate',
                'direction': direction,
                'first_half': first_success_rate,
                'second_half': second_success_rate
            })
        
        # Compare confidence levels
        first_avg_conf = statistics.mean([e.confidence for e in first_half])
        second_avg_conf = statistics.mean([e.confidence for e in second_half])
        
        if abs(second_avg_conf - first_avg_conf) > 0.1:
            direction = "increasing" if second_avg_conf > first_avg_conf else "decreasing"
            trends.append({
                'type': 'confidence',
                'direction': direction,
                'first_half': first_avg_conf,
                'second_half': second_avg_conf
            })
        
        return trends
    
    def _identify_issues(self, entries: List[FeedbackEntry]) -> List[Dict[str, Any]]:
        """Identify issues from feedback"""
        issues = []
        
        # Group by operation
        by_operation = defaultdict(list)
        for entry in entries:
            by_operation[entry.operation_id].append(entry)
        
        # Identify operations with low success rate
        for operation_id, operation_entries in by_operation.items():
            if len(operation_entries) < 3:
                continue
            
            success_rate = sum(1 for e in operation_entries if e.success) / len(operation_entries)
            
            if success_rate < 0.7:
                avg_confidence = statistics.mean([e.confidence for e in operation_entries])
                
                severity = "critical" if success_rate < 0.5 else "high"
                
                issues.append({
                    'issue_type': 'low_success_rate',
                    'severity': severity,
                    'operation_id': operation_id,
                    'success_rate': success_rate,
                    'average_confidence': avg_confidence,
                    'frequency': len(operation_entries)
                })
        
        # Identify operations with low confidence
        for operation_id, operation_entries in by_operation.items():
            if len(operation_entries) < 3:
                continue
            
            avg_confidence = statistics.mean([e.confidence for e in operation_entries])
            
            if avg_confidence < 0.6:
                issues.append({
                    'issue_type': 'low_confidence',
                    'severity': 'medium',
                    'operation_id': operation_id,
                    'average_confidence': avg_confidence,
                    'frequency': len(operation_entries)
                })
        
        return issues
    
    def _generate_recommendations(self, issues: List[Dict[str, Any]],
                                 success_rate: float,
                                 avg_confidence: float) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        if success_rate < 0.8:
            recommendations.append("Review and improve operation reliability")
            recommendations.append("Implement better error handling and retry logic")
        
        if avg_confidence < 0.7:
            recommendations.append("Improve confidence scoring algorithms")
            recommendations.append("Gather more data for better predictions")
        
        # Issue-specific recommendations
        for issue in issues:
            if issue['issue_type'] == 'low_success_rate':
                recommendations.append(f"Investigate operation {issue['operation_id']} for failures")
            elif issue['issue_type'] == 'low_confidence':
                recommendations.append(f"Improve data quality for operation {issue['operation_id']}")
        
        return recommendations
    
    def track_issue(self, operation_id: str, issue_type: str,
                   description: str, severity: str) -> FeedbackIssue:
        """Track a persistent issue"""
        issue_id = f"{operation_id}_{issue_type}"
        
        if issue_id in self.issues:
            issue = self.issues[issue_id]
            issue.frequency += 1
            issue.last_seen = datetime.now()
            if operation_id not in issue.affected_operations:
                issue.affected_operations.append(operation_id)
        else:
            issue = FeedbackIssue(
                issue_id=issue_id,
                issue_type=issue_type,
                severity=severity,
                description=description,
                affected_operations=[operation_id],
                frequency=1,
                first_seen=datetime.now(),
                last_seen=datetime.now(),
                recommended_actions=[]
            )
            self.issues[issue_id] = issue
        
        return issue
    
    def get_issues(self, severity: Optional[str] = None) -> List[FeedbackIssue]:
        """Get tracked issues"""
        if severity:
            return [i for i in self.issues.values() if i.severity == severity]
        return list(self.issues.values())


class FeedbackSystem:
    """
    Main feedback system that coordinates feedback collection and analysis
    
    The feedback system:
    - Collects feedback from various sources
    - Stores feedback for analysis
    - Analyzes feedback for patterns
    - Identifies issues and trends
    - Generates improvement recommendations
    """
    
    def __init__(self, enable_feedback: bool = True):
        self.enable_feedback = enable_feedback
        self.storage = FeedbackStorage()
        self.analyzer = FeedbackAnalyzer()
        self.feedback_counter = 0
        self.lock = threading.Lock()
    
    def collect_feedback(self, feedback_type: str, operation_id: str,
                        source: str, success: bool, confidence: float,
                        rating: Optional[int] = None,
                        feedback_data: Optional[Dict[str, Any]] = None,
                        comments: Optional[str] = None) -> str:
        """Collect feedback from an operation"""
        if not self.enable_feedback:
            return ""
        
        with self.lock:
            self.feedback_counter += 1
            feedback_id = f"feedback_{self.feedback_counter}"
        
        entry = FeedbackEntry(
            feedback_id=feedback_id,
            feedback_type=feedback_type,
            operation_id=operation_id,
            source=source,
            success=success,
            confidence=confidence,
            rating=rating,
            timestamp=datetime.now(),
            feedback_data=feedback_data or {},
            comments=comments
        )
        
        self.storage.add_entry(entry)
        
        # Track issues if applicable
        if not success:
            self.analyzer.track_issue(
                operation_id=operation_id,
                issue_type='operation_failure',
                description=f"Operation {operation_id} failed",
                severity='high'
            )
        
        return feedback_id
    
    def analyze_recent_feedback(self, time_period: str = "hour") -> FeedbackAnalysis:
        """Analyze recent feedback"""
        if not self.enable_feedback:
            return FeedbackAnalysis(
                analysis_id="disabled",
                feedback_type="none",
                time_period="none",
                success_rate=0.0,
                average_confidence=0.0,
                average_rating=None,
                trends=[],
                issues=[],
                recommendations=[],
                timestamp=datetime.now()
            )
        
        # Determine time range
        now = datetime.now()
        if time_period == "hour":
            start_time = now - timedelta(hours=1)
        elif time_period == "day":
            start_time = now - timedelta(days=1)
        elif time_period == "week":
            start_time = now - timedelta(weeks=1)
        else:
            start_time = now - timedelta(hours=1)
        
        entries = self.storage.get_entries_in_range(start_time, now)
        
        return self.analyzer.analyze_feedback(entries)
    
    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get summary of collected feedback"""
        recent = self.storage.get_recent_entries(100)
        
        if not recent:
            return {
                'total_entries': 0,
                'success_rate': 0.0,
                'average_confidence': 0.0,
                'average_rating': None,
                'by_type': {},
                'by_source': {}
            }
        
        # Calculate statistics
        success_rate = sum(1 for e in recent if e.success) / len(recent)
        avg_confidence = statistics.mean([e.confidence for e in recent])
        
        ratings = [e.rating for e in recent if e.rating is not None]
        avg_rating = statistics.mean(ratings) if ratings else None
        
        # Group by type
        by_type = {}
        for entry in recent:
            if entry.feedback_type not in by_type:
                by_type[entry.feedback_type] = {
                    'count': 0,
                    'successes': 0,
                    'total_confidence': 0.0
                }
            by_type[entry.feedback_type]['count'] += 1
            if entry.success:
                by_type[entry.feedback_type]['successes'] += 1
            by_type[entry.feedback_type]['total_confidence'] += entry.confidence
        
        # Calculate per-type statistics
        for feedback_type, stats in by_type.items():
            stats['success_rate'] = stats['successes'] / stats['count']
            stats['average_confidence'] = stats['total_confidence'] / stats['count']
            del stats['successes']
            del stats['total_confidence']
        
        # Group by source
        by_source = {}
        for entry in recent:
            if entry.source not in by_source:
                by_source[entry.source] = 0
            by_source[entry.source] += 1
        
        return {
            'total_entries': len(recent),
            'success_rate': success_rate,
            'average_confidence': avg_confidence,
            'average_rating': avg_rating,
            'by_type': by_type,
            'by_source': by_source
        }
    
    def get_tracked_issues(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tracked issues"""
        issues = self.analyzer.get_issues(severity)
        return [
            {
                'issue_id': i.issue_id,
                'issue_type': i.issue_type,
                'severity': i.severity,
                'description': i.description,
                'affected_operations': i.affected_operations,
                'frequency': i.frequency,
                'first_seen': i.first_seen.isoformat(),
                'last_seen': i.last_seen.isoformat(),
                'recommended_actions': i.recommended_actions
            }
            for i in issues
        ]
    
    def get_feedback_for_operation(self, operation_id: str) -> List[Dict[str, Any]]:
        """Get feedback for a specific operation"""
        entries = self.storage.get_entries_by_operation(operation_id)
        return [
            {
                'feedback_id': e.feedback_id,
                'feedback_type': e.feedback_type,
                'source': e.source,
                'success': e.success,
                'confidence': e.confidence,
                'rating': e.rating,
                'timestamp': e.timestamp.isoformat(),
                'feedback_data': e.feedback_data,
                'comments': e.comments
            }
            for e in entries
        ]
    
    def export_feedback_data(self) -> Dict[str, Any]:
        """Export feedback data for analysis"""
        recent = self.storage.get_recent_entries(1000)
        
        return {
            'summary': self.get_feedback_summary(),
            'issues': self.get_tracked_issues(),
            'recent_entries': [
                {
                    'feedback_id': e.feedback_id,
                    'feedback_type': e.feedback_type,
                    'operation_id': e.operation_id,
                    'source': e.source,
                    'success': e.success,
                    'confidence': e.confidence,
                    'rating': e.rating,
                    'timestamp': e.timestamp.isoformat(),
                    'feedback_data': e.feedback_data,
                    'comments': e.comments
                }
                for e in recent
            ]
        }
    
    def reset_feedback(self) -> None:
        """Reset all feedback data"""
        self.storage = FeedbackStorage()
        self.analyzer = FeedbackAnalyzer()
        self.feedback_counter = 0