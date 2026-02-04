# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Monitoring System
Core monitoring infrastructure for system health, performance, and anomaly detection
"""

import time
import psutil
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
import threading


@dataclass
class HealthStatus:
    """System health status"""
    component: str
    status: str  # 'healthy', 'degraded', 'unhealthy', 'unknown'
    message: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Metric:
    """Performance metric"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Anomaly:
    """Detected anomaly"""
    id: str
    type: str  # 'statistical', 'pattern', 'performance', 'resource'
    severity: str  # 'low', 'medium', 'high', 'critical'
    metric_name: str
    description: str
    value: float
    threshold: float
    timestamp: datetime
    resolved: bool = False
    resolution_note: str = ""


@dataclass
class Recommendation:
    """Optimization recommendation"""
    id: str
    category: str  # 'performance', 'resources', 'api', 'caching', 'database', 'scaling'
    priority: str  # 'low', 'medium', 'high', 'critical'
    title: str
    description: str
    expected_impact: str
    action_items: List[str]
    timestamp: datetime
    implemented: bool = False


class MonitoringSystem:
    """Main monitoring system"""
    
    def __init__(self, max_history=1000):
        self.max_history = max_history
        self.metrics_history = deque(maxlen=max_history)
        self.health_checks: Dict[str, HealthStatus] = {}
        self.anomalies: List[Anomaly] = []
        self.recommendations: List[Recommendation] = []
        self.lock = threading.Lock()
        
    def record_metric(self, name: str, value: float, unit: str = "", metadata: Dict = None):
        """Record a metric"""
        metric = Metric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        with self.lock:
            self.metrics_history.append(metric)
    
    def get_metrics(self, metric_name: str = None, limit: int = 100) -> List[Metric]:
        """Get metrics, optionally filtered by name"""
        with self.lock:
            metrics = list(self.metrics_history)
        
        if metric_name:
            metrics = [m for m in metrics if m.name == metric_name]
        
        return metrics[-limit:] if limit else metrics
    
    def calculate_metric_stats(self, metric_name: str) -> Dict[str, float]:
        """Calculate statistics for a metric"""
        metrics = self.get_metrics(metric_name)
        
        if not metrics:
            return {}
        
        values = [m.value for m in metrics]
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': statistics.mean(values),
            'median': statistics.median(values),
            'stddev': statistics.stdev(values) if len(values) > 1 else 0,
            'p95': self._percentile(values, 95),
            'p99': self._percentile(values, 99)
        }
    
    def _percentile(self, data: List[float], p: int) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((p / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def register_health_check(self, component: str, status: str, message: str, details: Dict = None):
        """Register a health check result"""
        health_status = HealthStatus(
            component=component,
            status=status,
            message=message,
            timestamp=datetime.now(),
            details=details or {}
        )
        
        with self.lock:
            self.health_checks[component] = health_status
    
    def get_health_status(self) -> Dict[str, HealthStatus]:
        """Get all health statuses"""
        with self.lock:
            return dict(self.health_checks)
    
    def get_overall_health(self) -> Dict[str, Any]:
        """Calculate overall system health"""
        health_checks = self.get_health_status()
        
        if not health_checks:
            return {
                'status': 'unknown',
                'score': 0,
                'message': 'No health checks available'
            }
        
        # Count statuses
        status_counts = {}
        for check in health_checks.values():
            status_counts[check.status] = status_counts.get(check.status, 0) + 1
        
        # Calculate health score
        healthy = status_counts.get('healthy', 0)
        total = len(health_checks)
        score = int((healthy / total) * 100) if total > 0 else 0
        
        # Determine overall status
        if score == 100:
            overall_status = 'healthy'
        elif score >= 70:
            overall_status = 'degraded'
        else:
            overall_status = 'unhealthy'
        
        return {
            'status': overall_status,
            'score': score,
            'message': f'System {overall_status} ({score}%)',
            'components': len(health_checks),
            'status_breakdown': status_counts
        }
    
    def add_anomaly(self, anomaly: Anomaly):
        """Add a detected anomaly"""
        with self.lock:
            self.anomalies.append(anomaly)
    
    def get_anomalies(self, resolved: bool = False) -> List[Anomaly]:
        """Get anomalies, optionally filtered by resolution status"""
        with self.lock:
            anomalies = [a for a in self.anomalies if a.resolved == resolved]
        return sorted(anomalies, key=lambda x: x.timestamp, reverse=True)
    
    def add_recommendation(self, recommendation: Recommendation):
        """Add an optimization recommendation"""
        with self.lock:
            self.recommendations.append(recommendation)
    
    def get_recommendations(self, implemented: bool = False) -> List[Recommendation]:
        """Get recommendations, optionally filtered by implementation status"""
        with self.lock:
            recommendations = [r for r in self.recommendations if r.implemented == implemented]
        return sorted(recommendations, key=lambda x: x.timestamp, reverse=True)
    
    def cleanup_old_data(self, max_age_hours: int = 24):
        """Clean up old data"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self.lock:
            # Clean old metrics
            self.metrics_history = deque(
                [m for m in self.metrics_history if m.timestamp > cutoff_time],
                maxlen=self.max_history
            )
            
            # Clean old anomalies
            self.anomalies = [a for a in self.anomalies if a.timestamp > cutoff_time]
            
            # Clean old recommendations
            self.recommendations = [r for r in self.recommendations if r.timestamp > cutoff_time]
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system resource metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': psutil.cpu_count(),
                    'load_avg': list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else []
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent
                },
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Global monitoring instance
monitoring_system = MonitoringSystem()