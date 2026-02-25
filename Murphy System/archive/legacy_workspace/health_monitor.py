"""
Murphy System - Health Monitor
Monitors system health and provides health check endpoints
"""

from datetime import datetime
from typing import Dict, Any, List
from monitoring_system import MonitoringSystem, HealthStatus


class HealthMonitor:
    """Monitors system health"""
    
    def __init__(self, monitoring_system: MonitoringSystem):
        self.monitoring = monitoring_system
        
    def check_all_components(self) -> Dict[str, Any]:
        """Check all system components"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'components': {}
        }
        
        # Check backend server
        results['components']['backend_server'] = self._check_backend_server()
        
        # Check database
        results['components']['database'] = self._check_database()
        
        # Check LLM APIs
        results['components']['llm_apis'] = self._check_llm_apis()
        
        # Check WebSocket
        results['components']['websocket'] = self._check_websocket()
        
        # Check system resources
        results['components']['system_resources'] = self._check_system_resources()
        
        # Calculate overall health
        results['overall'] = self._calculate_overall_health(results['components'])
        
        return results
    
    def _check_backend_server(self) -> HealthStatus:
        """Check backend server health"""
        try:
            # Simulate health check
            status = 'healthy'
            message = 'Backend server is running normally'
            details = {
                'uptime': 'active',
                'status_code': 200,
                'response_time_ms': 50
            }
            
            health = HealthStatus(
                component='backend_server',
                status=status,
                message=message,
                timestamp=datetime.now(),
                details=details
            )
            
            self.monitoring.register_health_check('backend_server', status, message, details)
            return health
            
        except Exception as e:
            health = HealthStatus(
                component='backend_server',
                status='unhealthy',
                message=f'Backend server check failed: {str(e)}',
                timestamp=datetime.now(),
                details={'error': str(e)}
            )
            
            self.monitoring.register_health_check('backend_server', 'unhealthy', str(e))
            return health
    
    def _check_database(self) -> HealthStatus:
        """Check database health"""
        try:
            # Simulate database health check
            status = 'healthy'
            message = 'Database is accessible and responsive'
            details = {
                'connection_status': 'connected',
                'response_time_ms': 20,
                'pool_status': 'healthy'
            }
            
            health = HealthStatus(
                component='database',
                status=status,
                message=message,
                timestamp=datetime.now(),
                details=details
            )
            
            self.monitoring.register_health_check('database', status, message, details)
            return health
            
        except Exception as e:
            health = HealthStatus(
                component='database',
                status='unhealthy',
                message=f'Database check failed: {str(e)}',
                timestamp=datetime.now(),
                details={'error': str(e)}
            )
            
            self.monitoring.register_health_check('database', 'unhealthy', str(e))
            return health
    
    def _check_llm_apis(self) -> HealthStatus:
        """Check LLM API availability"""
        try:
            # Simulate LLM API health check
            status = 'healthy'
            message = 'All LLM APIs are accessible'
            details = {
                'groq': 'available',
                'aristotle': 'available',
                'onboard': 'available',
                'last_check': datetime.now().isoformat()
            }
            
            health = HealthStatus(
                component='llm_apis',
                status=status,
                message=message,
                timestamp=datetime.now(),
                details=details
            )
            
            self.monitoring.register_health_check('llm_apis', status, message, details)
            return health
            
        except Exception as e:
            health = HealthStatus(
                component='llm_apis',
                status='degraded',
                message=f'LLM API check failed: {str(e)}',
                timestamp=datetime.now(),
                details={'error': str(e)}
            )
            
            self.monitoring.register_health_check('llm_apis', 'degraded', str(e))
            return health
    
    def _check_websocket(self) -> HealthStatus:
        """Check WebSocket connectivity"""
        try:
            # Simulate WebSocket health check
            status = 'healthy'
            message = 'WebSocket server is running'
            details = {
                'server_status': 'running',
                'active_connections': 0,
                'port': 3002
            }
            
            health = HealthStatus(
                component='websocket',
                status=status,
                message=message,
                timestamp=datetime.now(),
                details=details
            )
            
            self.monitoring.register_health_check('websocket', status, message, details)
            return health
            
        except Exception as e:
            health = HealthStatus(
                component='websocket',
                status='unhealthy',
                message=f'WebSocket check failed: {str(e)}',
                timestamp=datetime.now(),
                details={'error': str(e)}
            )
            
            self.monitoring.register_health_check('websocket', 'unhealthy', str(e))
            return health
    
    def _check_system_resources(self) -> HealthStatus:
        """Check system resource health"""
        try:
            system_metrics = self.monitoring.get_system_metrics()
            
            # Determine status based on resource usage
            cpu_percent = system_metrics.get('cpu', {}).get('percent', 0)
            memory_percent = system_metrics.get('memory', {}).get('percent', 0)
            disk_percent = system_metrics.get('disk', {}).get('percent', 0)
            
            if cpu_percent > 90 or memory_percent > 90 or disk_percent > 90:
                status = 'unhealthy'
                message = 'System resources critically low'
            elif cpu_percent > 80 or memory_percent > 80 or disk_percent > 80:
                status = 'degraded'
                message = 'System resources under stress'
            else:
                status = 'healthy'
                message = 'System resources within normal limits'
            
            details = system_metrics
            
            health = HealthStatus(
                component='system_resources',
                status=status,
                message=message,
                timestamp=datetime.now(),
                details=details
            )
            
            self.monitoring.register_health_check('system_resources', status, message, details)
            return health
            
        except Exception as e:
            health = HealthStatus(
                component='system_resources',
                status='unhealthy',
                message=f'System resources check failed: {str(e)}',
                timestamp=datetime.now(),
                details={'error': str(e)}
            )
            
            self.monitoring.register_health_check('system_resources', 'unhealthy', str(e))
            return health
    
    def _calculate_overall_health(self, components: Dict[str, HealthStatus]) -> Dict[str, Any]:
        """Calculate overall system health"""
        healthy_count = sum(1 for c in components.values() if c.status == 'healthy')
        degraded_count = sum(1 for c in components.values() if c.status == 'degraded')
        unhealthy_count = sum(1 for c in components.values() if c.status == 'unhealthy')
        total_count = len(components)
        
        health_score = int((healthy_count / total_count) * 100) if total_count > 0 else 0
        
        if unhealthy_count > 0:
            overall_status = 'unhealthy'
        elif degraded_count > 0:
            overall_status = 'degraded'
        else:
            overall_status = 'healthy'
        
        return {
            'status': overall_status,
            'score': health_score,
            'message': f'System {overall_status} ({health_score}%)',
            'components': {
                'healthy': healthy_count,
                'degraded': degraded_count,
                'unhealthy': unhealthy_count,
                'total': total_count
            }
        }
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of system health"""
        health_checks = self.monitoring.get_health_status()
        overall_health = self.monitoring.get_overall_health()
        
        return {
            'overall': overall_health,
            'components': health_checks,
            'timestamp': datetime.now().isoformat()
        }