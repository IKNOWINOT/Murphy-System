"""
Murphy System - Optimization Engine
Provides optimization recommendations based on system analysis
"""

from datetime import datetime
from typing import List, Dict, Any
from monitoring_system import MonitoringSystem, Recommendation


class OptimizationEngine:
    """Generates optimization recommendations"""
    
    def __init__(self, monitoring_system: MonitoringSystem):
        self.monitoring = monitoring_system
        
    def generate_recommendations(self) -> List[Recommendation]:
        """Generate all optimization recommendations"""
        recommendations = []
        
        # Performance recommendations
        recommendations.extend(self._analyze_performance())
        
        # Resource recommendations
        recommendations.extend(self._analyze_resources())
        
        # API recommendations
        recommendations.extend(self._analyze_api_usage())
        
        # Caching recommendations
        recommendations.extend(self._analyze_caching())
        
        # Scaling recommendations
        recommendations.extend(self._analyze_scaling())
        
        return recommendations
    
    def _analyze_performance(self) -> List[Recommendation]:
        """Analyze performance and generate recommendations"""
        recommendations = []
        
        # Analyze response times
        rt_stats = self.monitoring.calculate_metric_stats('response_time')
        
        if rt_stats and rt_stats.get('avg', 0) > 1000:
            recommendations.append(Recommendation(
                id=f"perf_rt_{int(datetime.now().timestamp())}",
                category="performance",
                priority="high",
                title="Optimize Response Time",
                description=f"Average response time is {rt_stats['avg']:.2f}ms, which is above the recommended 1000ms threshold",
                expected_impact="Reduce response time by 30-50%",
                action_items=[
                    "Review and optimize slow database queries",
                    "Implement query result caching",
                    "Consider database indexing improvements",
                    "Review and optimize algorithm complexity",
                    "Consider load balancing if applicable"
                ],
                timestamp=datetime.now()
            ))
        
        # Analyze error rates
        error_stats = self.monitoring.calculate_metric_stats('error_rate')
        
        if error_stats and error_stats.get('avg', 0) > 5:
            recommendations.append(Recommendation(
                id=f"perf_err_{int(datetime.now().timestamp())}",
                category="performance",
                priority="high",
                title="Reduce Error Rate",
                description=f"Average error rate is {error_stats['avg']:.2f}%, which is above the recommended 5% threshold",
                expected_impact="Improve reliability and user experience",
                action_items=[
                    "Review error logs to identify common issues",
                    "Implement better error handling",
                    "Add input validation",
                    "Improve retry logic for transient failures",
                    "Consider implementing circuit breakers"
                ],
                timestamp=datetime.now()
            ))
        
        return recommendations
    
    def _analyze_resources(self) -> List[Recommendation]:
        """Analyze resource usage and generate recommendations"""
        recommendations = []
        
        system_metrics = self.monitoring.get_system_metrics()
        
        # CPU recommendations
        if 'cpu' in system_metrics:
            cpu_percent = system_metrics['cpu'].get('percent', 0)
            if cpu_percent > 80:
                recommendations.append(Recommendation(
                    id=f"res_cpu_{int(datetime.now().timestamp())}",
                    category="resources",
                    priority="high" if cpu_percent > 90 else "medium",
                    title="Optimize CPU Usage",
                    description=f"CPU usage is at {cpu_percent}%, which is above recommended levels",
                    expected_impact="Reduce CPU usage by 20-30%",
                    action_items=[
                        "Profile CPU-intensive operations",
                        "Optimize algorithm efficiency",
                        "Consider parallel processing where appropriate",
                        "Review and optimize infinite loops or polling",
                        "Consider upgrading hardware if optimization not possible"
                    ],
                    timestamp=datetime.now()
                ))
        
        # Memory recommendations
        if 'memory' in system_metrics:
            memory_percent = system_metrics['memory'].get('percent', 0)
            if memory_percent > 80:
                recommendations.append(Recommendation(
                    id=f"res_mem_{int(datetime.now().timestamp())}",
                    category="resources",
                    priority="high" if memory_percent > 90 else "medium",
                    title="Optimize Memory Usage",
                    description=f"Memory usage is at {memory_percent}%, which is above recommended levels",
                    expected_impact="Reduce memory usage by 30-40%",
                    action_items=[
                        "Profile memory usage to identify memory leaks",
                        "Optimize data structures",
                        "Implement proper memory cleanup",
                        "Consider streaming instead of loading large datasets",
                        "Review cache size and eviction policies"
                    ],
                    timestamp=datetime.now()
                ))
        
        # Disk recommendations
        if 'disk' in system_metrics:
            disk_percent = system_metrics['disk'].get('percent', 0)
            if disk_percent > 80:
                recommendations.append(Recommendation(
                    id=f"res_disk_{int(datetime.now().timestamp())}",
                    category="resources",
                    priority="high" if disk_percent > 90 else "medium",
                    title="Manage Disk Space",
                    description=f"Disk usage is at {disk_percent}%, which is above recommended levels",
                    expected_impact="Free up disk space and improve performance",
                    action_items=[
                        "Clean up temporary files and logs",
                        "Implement log rotation and archival",
                        "Archive old data",
                        "Review and clean up unnecessary files",
                        "Consider expanding storage if needed"
                    ],
                    timestamp=datetime.now()
                ))
        
        return recommendations
    
    def _analyze_api_usage(self) -> List[Recommendation]:
        """Analyze API usage and generate recommendations"""
        recommendations = []
        
        # Analyze LLM API call times
        llm_stats = self.monitoring.calculate_metric_stats('llm_api_time')
        
        if llm_stats and llm_stats.get('avg', 0) > 5000:
            recommendations.append(Recommendation(
                id=f"api_llm_{int(datetime.now().timestamp())}",
                category="api",
                priority="medium",
                title="Optimize LLM API Calls",
                description=f"Average LLM API response time is {llm_stats['avg']:.2f}ms",
                expected_impact="Reduce API response time by 20-40%",
                action_items=[
                    "Review and optimize prompt complexity",
                    "Implement request batching where possible",
                    "Consider using faster models for simple tasks",
                    "Implement response caching",
                    "Review API rate limits and implement backoff"
                ],
                timestamp=datetime.now()
            ))
        
        # Analyze API failure rates
        failure_stats = self.monitoring.calculate_metric_stats('api_failure_rate')
        
        if failure_stats and failure_stats.get('avg', 0) > 2:
            recommendations.append(Recommendation(
                id=f"api_fail_{int(datetime.now().timestamp())}",
                category="api",
                priority="high",
                title="Reduce API Failure Rate",
                description=f"API failure rate is {failure_stats['avg']:.2f}%, which is above recommended levels",
                expected_impact="Improve reliability and reduce costs",
                action_items=[
                    "Review API error logs",
                    "Implement better error handling and retry logic",
                    "Check API key quotas and limits",
                    "Implement circuit breakers for failing endpoints",
                    "Consider fallback mechanisms"
                ],
                timestamp=datetime.now()
            ))
        
        return recommendations
    
    def _analyze_caching(self) -> List[Recommendation]:
        """Analyze caching and generate recommendations"""
        recommendations = []
        
        # Check cache hit rate
        cache_stats = self.monitoring.calculate_metric_stats('cache_hit_rate')
        
        if cache_stats and cache_stats.get('avg', 0) < 50:
            recommendations.append(Recommendation(
                id=f"cache_hit_{int(datetime.now().timestamp())}",
                category="caching",
                priority="medium",
                title="Improve Cache Hit Rate",
                description=f"Cache hit rate is {cache_stats['avg']:.2f}%, which is below the recommended 50%",
                expected_impact="Increase cache hit rate to 70-80%",
                action_items=[
                    "Review cache key generation strategy",
                    "Increase cache size if needed",
                    "Implement multi-level caching",
                    "Review cache expiration policies",
                    "Consider caching more frequently accessed data"
                ],
                timestamp=datetime.now()
            ))
        
        # Analyze cache response time
        cache_rt_stats = self.monitoring.calculate_metric_stats('cache_response_time')
        
        if cache_rt_stats and cache_rt_stats.get('avg', 0) > 100:
            recommendations.append(Recommendation(
                id=f"cache_rt_{int(datetime.now().timestamp())}",
                category="caching",
                priority="low",
                title="Optimize Cache Response Time",
                description=f"Cache response time is {cache_rt_stats['avg']:.2f}ms",
                expected_impact="Reduce cache response time by 20-30%",
                action_items=[
                    "Review cache backend performance",
                    "Consider using faster cache storage (Redis, Memcached)",
                    "Optimize cache serialization",
                    "Review cache connection pooling"
                ],
                timestamp=datetime.now()
            ))
        
        return recommendations
    
    def _analyze_scaling(self) -> List[Recommendation]:
        """Analyze scaling needs and generate recommendations"""
        recommendations = []
        
        # Analyze throughput
        throughput_stats = self.monitoring.calculate_metric_stats('throughput')
        
        if throughput_stats and throughput_stats.get('avg', 0) > 0:
            # Check if throughput is increasing
            throughput_values = self.monitoring.get_metrics('throughput')
            if len(throughput_values) > 10:
                recent_avg = sum(m.value for m in throughput_values[-5:]) / 5
                earlier_avg = sum(m.value for m in throughput_values[-10:-5]) / 5
                
                if recent_avg > earlier_avg * 1.5:
                    recommendations.append(Recommendation(
                        id=f"scale_throughput_{int(datetime.now().timestamp())}",
                        category="scaling",
                        priority="high",
                        title="Consider Scaling Up",
                        description=f"Throughput has increased by {((recent_avg/earlier_avg - 1) * 100):.1f}% in the recent period",
                        expected_impact="Handle increased load efficiently",
                        action_items=[
                            "Monitor system capacity closely",
                            "Consider horizontal scaling (add more instances)",
                            "Consider vertical scaling (increase instance size)",
                            "Review and optimize bottlenecks",
                            "Implement load balancing if not already"
                        ],
                        timestamp=datetime.now()
                    ))
        
        return recommendations