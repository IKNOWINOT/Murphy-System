"""
Historical Data Analysis System
Analyzes historical data to improve UD (Uncertainty in Data) calculations.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field
import statistics
from collections import defaultdict


class DataQualityMetric(str, Enum):
    """Types of data quality metrics."""
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    VALIDITY = "validity"
    UNIQUENESS = "uniqueness"


class DataSourceType(str, Enum):
    """Types of data sources."""
    DATABASE = "database"
    API = "api"
    FILE = "file"
    STREAM = "stream"
    MANUAL_ENTRY = "manual_entry"
    EXTERNAL_SERVICE = "external_service"


class HistoricalDataPoint(BaseModel):
    """Represents a historical data point."""
    id: str
    source_type: DataSourceType
    source_name: str
    timestamp: datetime
    quality_metrics: Dict[DataQualityMetric, float] = Field(default_factory=dict)
    error_count: int = 0
    success_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataQualityScore(BaseModel):
    """Overall data quality score."""
    completeness: float = Field(ge=0.0, le=1.0)
    accuracy: float = Field(ge=0.0, le=1.0)
    consistency: float = Field(ge=0.0, le=1.0)
    timeliness: float = Field(ge=0.0, le=1.0)
    validity: float = Field(ge=0.0, le=1.0)
    uniqueness: float = Field(ge=0.0, le=1.0)
    overall: float = Field(ge=0.0, le=1.0)
    
    @classmethod
    def calculate_overall(cls, metrics: Dict[DataQualityMetric, float]) -> float:
        """Calculate overall quality score from individual metrics."""
        if not metrics:
            return 0.0
        return sum(metrics.values()) / len(metrics)


class HistoricalAnalysisResult(BaseModel):
    """Result of historical data analysis."""
    source_name: str
    source_type: DataSourceType
    analysis_period: Tuple[datetime, datetime]
    data_points_analyzed: int
    quality_score: DataQualityScore
    reliability_score: float = Field(ge=0.0, le=1.0)
    uncertainty_score: float = Field(ge=0.0, le=1.0)
    trends: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)


class HistoricalDataStore:
    """
    Stores historical data points for analysis.
    In production, this would use a time-series database.
    """
    
    def __init__(self):
        self.data_points: List[HistoricalDataPoint] = []
        self.source_index: Dict[str, List[HistoricalDataPoint]] = defaultdict(list)
    
    def add_data_point(self, data_point: HistoricalDataPoint):
        """Add a historical data point."""
        self.data_points.append(data_point)
        self.source_index[data_point.source_name].append(data_point)
    
    def get_data_points(
        self,
        source_name: Optional[str] = None,
        source_type: Optional[DataSourceType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[HistoricalDataPoint]:
        """Retrieve data points with filters."""
        points = self.data_points
        
        if source_name:
            points = self.source_index.get(source_name, [])
        
        if source_type:
            points = [p for p in points if p.source_type == source_type]
        
        if start_time:
            points = [p for p in points if p.timestamp >= start_time]
        
        if end_time:
            points = [p for p in points if p.timestamp <= end_time]
        
        return points
    
    def get_recent_data_points(
        self,
        source_name: str,
        hours: int = 24
    ) -> List[HistoricalDataPoint]:
        """Get recent data points for a source."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return self.get_data_points(
            source_name=source_name,
            start_time=cutoff
        )


class HistoricalDataAnalyzer:
    """
    Analyzes historical data to calculate uncertainty scores.
    """
    
    def __init__(self, data_store: HistoricalDataStore):
        self.data_store = data_store
    
    def analyze_source(
        self,
        source_name: str,
        analysis_period_hours: int = 168  # 7 days default
    ) -> HistoricalAnalysisResult:
        """
        Analyze historical data for a source.
        
        Args:
            source_name: Name of the data source
            analysis_period_hours: Hours of history to analyze
            
        Returns:
            HistoricalAnalysisResult with quality and uncertainty scores
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=analysis_period_hours)
        
        data_points = self.data_store.get_data_points(
            source_name=source_name,
            start_time=start_time,
            end_time=end_time
        )
        
        if not data_points:
            return self._create_default_result(source_name, start_time, end_time)
        
        # Calculate quality metrics
        quality_score = self._calculate_quality_score(data_points)
        
        # Calculate reliability score
        reliability_score = self._calculate_reliability_score(data_points)
        
        # Calculate uncertainty score (inverse of reliability)
        uncertainty_score = 1.0 - reliability_score
        
        # Analyze trends
        trends = self._analyze_trends(data_points)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            quality_score,
            reliability_score,
            trends
        )
        
        return HistoricalAnalysisResult(
            source_name=source_name,
            source_type=data_points[0].source_type,
            analysis_period=(start_time, end_time),
            data_points_analyzed=len(data_points),
            quality_score=quality_score,
            reliability_score=reliability_score,
            uncertainty_score=uncertainty_score,
            trends=trends,
            recommendations=recommendations
        )
    
    def _calculate_quality_score(self, data_points: List[HistoricalDataPoint]) -> DataQualityScore:
        """Calculate overall quality score from data points."""
        metric_scores: Dict[DataQualityMetric, List[float]] = defaultdict(list)
        
        # Collect all metric scores
        for point in data_points:
            for metric, score in point.quality_metrics.items():
                metric_scores[metric].append(score)
        
        # Calculate average for each metric
        avg_scores = {}
        for metric in DataQualityMetric:
            scores = metric_scores.get(metric, [])
            avg_scores[metric] = statistics.mean(scores) if scores else 0.5
        
        return DataQualityScore(
            completeness=avg_scores.get(DataQualityMetric.COMPLETENESS, 0.5),
            accuracy=avg_scores.get(DataQualityMetric.ACCURACY, 0.5),
            consistency=avg_scores.get(DataQualityMetric.CONSISTENCY, 0.5),
            timeliness=avg_scores.get(DataQualityMetric.TIMELINESS, 0.5),
            validity=avg_scores.get(DataQualityMetric.VALIDITY, 0.5),
            uniqueness=avg_scores.get(DataQualityMetric.UNIQUENESS, 0.5),
            overall=DataQualityScore.calculate_overall(avg_scores)
        )
    
    def _calculate_reliability_score(self, data_points: List[HistoricalDataPoint]) -> float:
        """
        Calculate reliability score based on success/error rates.
        
        Returns:
            Reliability score (0.0 to 1.0)
        """
        total_success = sum(p.success_count for p in data_points)
        total_errors = sum(p.error_count for p in data_points)
        total_operations = total_success + total_errors
        
        if total_operations == 0:
            return 0.5  # Neutral score if no data
        
        success_rate = total_success / total_operations
        
        # Factor in consistency of success rate over time
        if len(data_points) > 1:
            success_rates = [
                p.success_count / (p.success_count + p.error_count)
                if (p.success_count + p.error_count) > 0 else 0.5
                for p in data_points
            ]
            consistency = 1.0 - statistics.stdev(success_rates) if len(success_rates) > 1 else 1.0
            
            # Weighted average: 70% success rate, 30% consistency
            return 0.7 * success_rate + 0.3 * consistency
        
        return success_rate
    
    def _analyze_trends(self, data_points: List[HistoricalDataPoint]) -> Dict[str, Any]:
        """Analyze trends in the data."""
        if len(data_points) < 2:
            return {"trend": "insufficient_data"}
        
        # Sort by timestamp
        sorted_points = sorted(data_points, key=lambda p: p.timestamp)
        
        # Calculate error rate trend
        error_rates = [
            p.error_count / (p.success_count + p.error_count)
            if (p.success_count + p.error_count) > 0 else 0
            for p in sorted_points
        ]
        
        # Simple trend detection: compare first half to second half
        mid = len(error_rates) // 2
        first_half_avg = statistics.mean(error_rates[:mid]) if mid > 0 else 0
        second_half_avg = statistics.mean(error_rates[mid:]) if mid > 0 else 0
        
        trend = "stable"
        if second_half_avg > first_half_avg * 1.2:
            trend = "degrading"
        elif second_half_avg < first_half_avg * 0.8:
            trend = "improving"
        
        return {
            "trend": trend,
            "error_rate_change": second_half_avg - first_half_avg,
            "current_error_rate": error_rates[-1] if error_rates else 0,
            "average_error_rate": statistics.mean(error_rates) if error_rates else 0
        }
    
    def _generate_recommendations(
        self,
        quality_score: DataQualityScore,
        reliability_score: float,
        trends: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # Quality-based recommendations
        if quality_score.completeness < 0.7:
            recommendations.append("Improve data completeness - missing fields detected")
        
        if quality_score.accuracy < 0.7:
            recommendations.append("Verify data accuracy - inconsistencies detected")
        
        if quality_score.timeliness < 0.7:
            recommendations.append("Update data more frequently - staleness detected")
        
        # Reliability-based recommendations
        if reliability_score < 0.7:
            recommendations.append("Investigate reliability issues - high error rate detected")
        
        if reliability_score < 0.5:
            recommendations.append("CRITICAL: Consider alternative data source - reliability below threshold")
        
        # Trend-based recommendations
        if trends.get("trend") == "degrading":
            recommendations.append("WARNING: Data quality is degrading - immediate attention required")
        
        if trends.get("current_error_rate", 0) > 0.3:
            recommendations.append("High current error rate - verify data source availability")
        
        return recommendations
    
    def _create_default_result(
        self,
        source_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> HistoricalAnalysisResult:
        """Create default result when no data available."""
        return HistoricalAnalysisResult(
            source_name=source_name,
            source_type=DataSourceType.EXTERNAL_SERVICE,
            analysis_period=(start_time, end_time),
            data_points_analyzed=0,
            quality_score=DataQualityScore(
                completeness=0.5,
                accuracy=0.5,
                consistency=0.5,
                timeliness=0.5,
                validity=0.5,
                uniqueness=0.5,
                overall=0.5
            ),
            reliability_score=0.5,
            uncertainty_score=0.5,
            trends={"trend": "no_data"},
            recommendations=["No historical data available - cannot assess reliability"]
        )
    
    def compare_sources(
        self,
        source_names: List[str],
        analysis_period_hours: int = 168
    ) -> Dict[str, HistoricalAnalysisResult]:
        """
        Compare multiple data sources.
        
        Args:
            source_names: List of source names to compare
            analysis_period_hours: Hours of history to analyze
            
        Returns:
            Dictionary mapping source names to analysis results
        """
        results = {}
        for source_name in source_names:
            results[source_name] = self.analyze_source(source_name, analysis_period_hours)
        return results
    
    def get_best_source(
        self,
        source_names: List[str],
        analysis_period_hours: int = 168
    ) -> Tuple[str, HistoricalAnalysisResult]:
        """
        Identify the best data source based on historical analysis.
        
        Args:
            source_names: List of source names to compare
            analysis_period_hours: Hours of history to analyze
            
        Returns:
            Tuple of (best_source_name, analysis_result)
        """
        results = self.compare_sources(source_names, analysis_period_hours)
        
        if not results:
            raise ValueError("No sources to compare")
        
        # Rank by reliability score
        best_source = max(results.items(), key=lambda x: x[1].reliability_score)
        return best_source


class UDCalculator:
    """
    Calculates UD (Uncertainty in Data) using historical analysis.
    Integrates with Murphy's uncertainty framework.
    """
    
    def __init__(self, analyzer: HistoricalDataAnalyzer):
        self.analyzer = analyzer
    
    def calculate_ud(
        self,
        source_name: str,
        analysis_period_hours: int = 168
    ) -> float:
        """
        Calculate UD score for a data source.
        
        Args:
            source_name: Name of the data source
            analysis_period_hours: Hours of history to analyze
            
        Returns:
            UD score (0.0 to 1.0, where 0 = certain, 1 = highly uncertain)
        """
        analysis = self.analyzer.analyze_source(source_name, analysis_period_hours)
        
        # UD is the uncertainty score from historical analysis
        return analysis.uncertainty_score
    
    def calculate_ud_with_context(
        self,
        source_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate UD with additional context and breakdown.
        
        Args:
            source_name: Name of the data source
            context: Additional context (e.g., required_quality_threshold)
            
        Returns:
            Dictionary with UD score and detailed breakdown
        """
        analysis_period = context.get("analysis_period_hours", 168)
        analysis = self.analyzer.analyze_source(source_name, analysis_period)
        
        # Calculate component scores
        quality_uncertainty = 1.0 - analysis.quality_score.overall
        reliability_uncertainty = 1.0 - analysis.reliability_score
        
        # Weighted combination
        ud_score = 0.6 * reliability_uncertainty + 0.4 * quality_uncertainty
        
        return {
            "ud_score": ud_score,
            "reliability_uncertainty": reliability_uncertainty,
            "quality_uncertainty": quality_uncertainty,
            "quality_breakdown": {
                "completeness": analysis.quality_score.completeness,
                "accuracy": analysis.quality_score.accuracy,
                "consistency": analysis.quality_score.consistency,
                "timeliness": analysis.quality_score.timeliness
            },
            "trends": analysis.trends,
            "recommendations": analysis.recommendations,
            "data_points_analyzed": analysis.data_points_analyzed
        }


class HistoricalDataAnalysisSystem:
    """
    Complete historical data analysis system.
    Provides unified interface for historical analysis and UD calculation.
    """
    
    def __init__(self):
        self.store = HistoricalDataStore()
        self.analyzer = HistoricalDataAnalyzer(self.store)
        self.ud_calculator = UDCalculator(self.analyzer)
    
    def record_data_point(
        self,
        source_name: str,
        source_type: DataSourceType,
        quality_metrics: Dict[DataQualityMetric, float],
        success_count: int = 0,
        error_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a new historical data point."""
        data_point = HistoricalDataPoint(
            id=f"{source_name}_{datetime.utcnow().timestamp()}",
            source_type=source_type,
            source_name=source_name,
            timestamp=datetime.utcnow(),
            quality_metrics=quality_metrics,
            success_count=success_count,
            error_count=error_count,
            metadata=metadata or {}
        )
        self.store.add_data_point(data_point)
    
    def analyze_source(self, source_name: str) -> HistoricalAnalysisResult:
        """Analyze a data source."""
        return self.analyzer.analyze_source(source_name)
    
    def calculate_ud(self, source_name: str) -> float:
        """Calculate UD score for a source."""
        return self.ud_calculator.calculate_ud(source_name)
    
    def calculate_ud_detailed(
        self,
        source_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculate UD with detailed breakdown."""
        return self.ud_calculator.calculate_ud_with_context(
            source_name,
            context or {}
        )
    
    def compare_sources(self, source_names: List[str]) -> Dict[str, HistoricalAnalysisResult]:
        """Compare multiple sources."""
        return self.analyzer.compare_sources(source_names)
    
    def get_best_source(self, source_names: List[str]) -> Tuple[str, HistoricalAnalysisResult]:
        """Get the best source from a list."""
        return self.analyzer.get_best_source(source_names)