# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Anomaly Detection Engine
Detects unusual patterns and behaviors in system metrics
"""

import statistics
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from monitoring_system import MonitoringSystem, Anomaly


class AnomalyDetector:
    """Detects anomalies in system metrics"""
    
    def __init__(self, monitoring_system: MonitoringSystem):
        self.monitoring = monitoring_system
        self.threshold_stddev = 3.0  # Z-score threshold
        self.threshold_iqr_multiplier = 1.5  # IQR multiplier
        self.min_samples = 10  # Minimum samples for anomaly detection
        
    def detect_anomalies(self) -> List[Anomaly]:
        """Run anomaly detection on all metrics"""
        anomalies = []
        
        # Get all metric names
        all_metrics = self.monitoring.get_metrics()
        metric_names = set(m.name for m in all_metrics)
        
        # Detect anomalies for each metric
        for metric_name in metric_names:
            metric_anomalies = self.detect_metric_anomalies(metric_name)
            anomalies.extend(metric_anomalies)
        
        return anomalies
    
    def detect_metric_anomalies(self, metric_name: str) -> List[Anomaly]:
        """Detect anomalies for a specific metric"""
        metrics = self.monitoring.get_metrics(metric_name)
        
        if len(metrics) < self.min_samples:
            return []
        
        anomalies = []
        values = [m.value for m in metrics]
        
        # Statistical anomaly detection (Z-score)
        z_score_anomalies = self._detect_zscore_anomalies(metrics, values)
        anomalies.extend(z_score_anomalies)
        
        # IQR method
        iqr_anomalies = self._detect_iqr_anomalies(metrics, values)
        anomalies.extend(iqr_anomalies)
        
        # Moving average deviation
        ma_anomalies = self._detect_moving_average_anomalies(metrics, values)
        anomalies.extend(ma_anomalies)
        
        # Rate of change anomalies
        roc_anomalies = self._detect_rate_of_change_anomalies(metrics, values)
        anomalies.extend(roc_anomalies)
        
        return anomalies
    
    def _detect_zscore_anomalies(self, metrics: List, values: List[float]) -> List[Anomaly]:
        """Detect anomalies using Z-score method"""
        if len(values) < 2:
            return []
        
        mean = statistics.mean(values)
        stddev = statistics.stdev(values)
        
        if stddev == 0:
            return []
        
        anomalies = []
        for metric, value in zip(metrics, values):
            z_score = abs((value - mean) / stddev)
            
            if z_score > self.threshold_stddev:
                severity = self._calculate_severity(z_score)
                anomaly = Anomaly(
                    id=f"zscore_{metric.name}_{int(metric.timestamp.timestamp())}",
                    type="statistical",
                    severity=severity,
                    metric_name=metric.name,
                    description=f"Value {value:.2f} is {z_score:.2f} standard deviations from mean",
                    value=value,
                    threshold=mean + (self.threshold_stddev * stddev),
                    timestamp=metric.timestamp
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    def _detect_iqr_anomalies(self, metrics: List, values: List[float]) -> List[Anomaly]:
        """Detect anomalies using IQR method"""
        if len(values) < 4:
            return []
        
        sorted_values = sorted(values)
        q1 = self._percentile(sorted_values, 25)
        q3 = self._percentile(sorted_values, 75)
        iqr = q3 - q1
        
        if iqr == 0:
            return []
        
        lower_bound = q1 - (self.threshold_iqr_multiplier * iqr)
        upper_bound = q3 + (self.threshold_iqr_multiplier * iqr)
        
        anomalies = []
        for metric, value in zip(metrics, values):
            if value < lower_bound or value > upper_bound:
                severity = self._calculate_iqr_severity(value, lower_bound, upper_bound, iqr)
                anomaly = Anomaly(
                    id=f"iqr_{metric.name}_{int(metric.timestamp.timestamp())}",
                    type="statistical",
                    severity=severity,
                    metric_name=metric.name,
                    description=f"Value {value:.2f} outside IQR range ({lower_bound:.2f} - {upper_bound:.2f})",
                    value=value,
                    threshold=upper_bound if value > upper_bound else lower_bound,
                    timestamp=metric.timestamp
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    def _detect_moving_average_anomalies(self, metrics: List, values: List[float], window: int = 5) -> List[Anomaly]:
        """Detect anomalies using moving average deviation"""
        if len(values) < window + 1:
            return []
        
        anomalies = []
        for i in range(window, len(values)):
            window_values = values[i-window:i]
            moving_avg = statistics.mean(window_values)
            current_value = values[i]
            
            # Check if current value deviates significantly from moving average
            deviation = abs(current_value - moving_avg)
            window_stddev = statistics.stdev(window_values) if len(window_values) > 1 else 0
            
            if window_stddev > 0 and deviation > 2 * window_stddev:
                severity = self._calculate_severity(deviation / window_stddev)
                anomaly = Anomaly(
                    id=f"ma_{metrics[i].name}_{int(metrics[i].timestamp.timestamp())}",
                    type="pattern",
                    severity=severity,
                    metric_name=metrics[i].name,
                    description=f"Value {current_value:.2f} deviates from moving average {moving_avg:.2f}",
                    value=current_value,
                    threshold=moving_avg,
                    timestamp=metrics[i].timestamp
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    def _detect_rate_of_change_anomalies(self, metrics: List, values: List[float]) -> List[Anomaly]:
        """Detect anomalies in rate of change"""
        if len(values) < 2:
            return []
        
        anomalies = []
        roc_threshold = 2.0  # Rate of change threshold (200%)
        
        for i in range(1, len(values)):
            if values[i-1] != 0:
                roc = abs((values[i] - values[i-1]) / values[i-1]) * 100
                
                if roc > roc_threshold:
                    severity = 'critical' if roc > 500 else ('high' if roc > 300 else 'medium')
                    anomaly = Anomaly(
                        id=f"roc_{metrics[i].name}_{int(metrics[i].timestamp.timestamp())}",
                        type="pattern",
                        severity=severity,
                        metric_name=metrics[i].name,
                        description=f"Rate of change {roc:.1f}% exceeds threshold {roc_threshold}%",
                        value=roc,
                        threshold=roc_threshold,
                        timestamp=metrics[i].timestamp
                    )
                    anomalies.append(anomaly)
        
        return anomalies
    
    def _percentile(self, data: List[float], p: int) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((p / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _calculate_severity(self, z_score: float) -> str:
        """Calculate severity based on z-score"""
        if z_score > 5:
            return 'critical'
        elif z_score > 4:
            return 'high'
        elif z_score > 3:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_iqr_severity(self, value: float, lower: float, upper: float, iqr: float) -> str:
        """Calculate severity for IQR anomalies"""
        if value > upper:
            deviation = (value - upper) / iqr
        else:
            deviation = (lower - value) / iqr
        
        if deviation > 2:
            return 'critical'
        elif deviation > 1.5:
            return 'high'
        elif deviation > 1:
            return 'medium'
        else:
            return 'low'
    
    def detect_performance_anomalies(self, response_times: List[float]) -> List[Anomaly]:
        """Detect performance anomalies in response times"""
        if not response_times:
            return []
        
        anomalies = []
        threshold_p99 = self._percentile(response_times, 99)
        
        for i, rt in enumerate(response_times):
            if rt > threshold_p99 * 1.5:
                severity = 'critical' if rt > threshold_p99 * 2 else 'high'
                anomaly = Anomaly(
                    id=f"perf_rt_{i}_{int(datetime.now().timestamp())}",
                    type="performance",
                    severity=severity,
                    metric_name="response_time",
                    description=f"Response time {rt:.2f}ms exceeds p99 threshold {threshold_p99:.2f}ms",
                    value=rt,
                    threshold=threshold_p99,
                    timestamp=datetime.now()
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    def detect_resource_anomalies(self, cpu_percent: float, memory_percent: float, disk_percent: float) -> List[Anomaly]:
        """Detect resource anomalies"""
        anomalies = []
        
        # CPU anomaly
        if cpu_percent > 90:
            anomaly = Anomaly(
                id=f"res_cpu_{int(datetime.now().timestamp())}",
                type="resource",
                severity='critical',
                metric_name="cpu_percent",
                description=f"CPU usage {cpu_percent}% exceeds critical threshold",
                value=cpu_percent,
                threshold=90,
                timestamp=datetime.now()
            )
            anomalies.append(anomaly)
        elif cpu_percent > 80:
            anomaly = Anomaly(
                id=f"res_cpu_{int(datetime.now().timestamp())}",
                type="resource",
                severity='high',
                metric_name="cpu_percent",
                description=f"CPU usage {cpu_percent}% exceeds warning threshold",
                value=cpu_percent,
                threshold=80,
                timestamp=datetime.now()
            )
            anomalies.append(anomaly)
        
        # Memory anomaly
        if memory_percent > 90:
            anomaly = Anomaly(
                id=f"res_mem_{int(datetime.now().timestamp())}",
                type="resource",
                severity='critical',
                metric_name="memory_percent",
                description=f"Memory usage {memory_percent}% exceeds critical threshold",
                value=memory_percent,
                threshold=90,
                timestamp=datetime.now()
            )
            anomalies.append(anomaly)
        
        # Disk anomaly
        if disk_percent > 90:
            anomaly = Anomaly(
                id=f"res_disk_{int(datetime.now().timestamp())}",
                type="resource",
                severity='critical',
                metric_name="disk_percent",
                description=f"Disk usage {disk_percent}% exceeds critical threshold",
                value=disk_percent,
                threshold=90,
                timestamp=datetime.now()
            )
            anomalies.append(anomaly)
        
        return anomalies