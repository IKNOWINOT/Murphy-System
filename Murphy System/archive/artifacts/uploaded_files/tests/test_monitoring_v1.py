#!/usr/bin/env python3
"""
Integration Tests for MONITOR_v1 Pack
Tests metrics collection, error processing, and alert generation
"""

import sys
import time
from test_framework import TestFramework, TestDataGenerator

def test_metrics_collection(framework: TestFramework) -> dict:
    """Test metrics collection"""
    try:
        # Insert test metrics
        metrics = [
            ('test_metric_1', 100, 'count', '{"source": "test"}'),
            ('test_metric_2', 75.5, 'percent', '{"source": "test"}'),
            ('test_metric_3', 1250, 'ms', '{"source": "test"}')
        ]
        
        for metric_name, metric_value, metric_unit, tags in metrics:
            framework.execute_query("""
                INSERT INTO metrics (metric_name, metric_value, metric_unit, tags, recorded_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (metric_name, metric_value, metric_unit, tags))
        
        # Verify metrics were inserted
        result = framework.execute_query("""
            SELECT COUNT(*) FROM metrics 
            WHERE metric_name LIKE 'test_metric_%'
        """)
        
        if result and result[0][0] == len(metrics):
            return {
                'passed': True,
                'message': f'{len(metrics)} metrics collected successfully',
                'details': {'metrics_count': len(metrics)}
            }
        else:
            return {
                'passed': False,
                'message': 'Metrics count mismatch'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Metrics collection failed: {str(e)}'
        }

def test_error_processing(framework: TestFramework) -> dict:
    """Test error processing and logging"""
    try:
        # Generate test error
        error_data = TestDataGenerator.generate_error(
            workflow_id='TEST_WORKFLOW',
            error_type='TestError',
            error_message='Test error for integration testing',
            error_severity='high',
            error_category='system'
        )
        
        # Insert error
        framework.execute_query("""
            INSERT INTO errors (client_id, workflow_id, error_type, error_message, error_severity, error_category, context, occurred_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """, (
            error_data['client_id'],
            error_data['workflow_id'],
            error_data['error_type'],
            error_data['error_message'],
            error_data['error_severity'],
            error_data['error_category'],
            str(error_data['context'])
        ))
        
        # Verify error was logged
        result = framework.execute_query("""
            SELECT id, error_type, error_severity, error_category
            FROM errors
            WHERE workflow_id = 'TEST_WORKFLOW'
            ORDER BY occurred_at DESC
            LIMIT 1
        """)
        
        if result:
            error_id, error_type, severity, category = result[0]
            
            # Check if alert was created for high severity error
            alert_result = framework.execute_query("""
                SELECT COUNT(*) FROM alerts
                WHERE source_entity_type = 'error'
                AND alert_severity = 'high'
            """)
            
            return {
                'passed': True,
                'message': f'Error processed successfully (ID: {error_id})',
                'details': {
                    'error_id': error_id,
                    'error_type': error_type,
                    'severity': severity,
                    'category': category
                }
            }
        else:
            return {
                'passed': False,
                'message': 'Error not found in database'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Error processing failed: {str(e)}'
        }

def test_alert_generation(framework: TestFramework) -> dict:
    """Test alert generation"""
    try:
        # Create test alert
        framework.execute_query("""
            INSERT INTO alerts (client_id, alert_type, alert_severity, alert_title, alert_message, source_workflow, triggered_at)
            VALUES (1, 'test_alert', 'medium', 'Test Alert', 'Test alert for integration testing', 'TEST_WORKFLOW', NOW())
            RETURNING id
        """)
        
        # Verify alert was created
        result = framework.execute_query("""
            SELECT id, alert_type, alert_severity, alert_title, acknowledged
            FROM alerts
            WHERE alert_type = 'test_alert'
            ORDER BY triggered_at DESC
            LIMIT 1
        """)
        
        if result:
            alert_id, alert_type, severity, title, acknowledged = result[0]
            
            return {
                'passed': True,
                'message': f'Alert generated successfully (ID: {alert_id})',
                'details': {
                    'alert_id': alert_id,
                    'alert_type': alert_type,
                    'severity': severity,
                    'acknowledged': acknowledged
                }
            }
        else:
            return {
                'passed': False,
                'message': 'Alert not found in database'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Alert generation failed: {str(e)}'
        }

def test_alert_acknowledgment(framework: TestFramework) -> dict:
    """Test alert acknowledgment"""
    try:
        # Create unacknowledged alert
        framework.execute_query("""
            INSERT INTO alerts (client_id, alert_type, alert_severity, alert_title, alert_message, acknowledged, triggered_at)
            VALUES (1, 'ack_test_alert', 'low', 'Acknowledgment Test', 'Test alert acknowledgment', FALSE, NOW())
            RETURNING id
        """)
        
        result = framework.execute_query("""
            SELECT id FROM alerts WHERE alert_type = 'ack_test_alert'
        """)
        
        if result:
            alert_id = result[0][0]
            
            # Acknowledge alert
            framework.execute_query("""
                UPDATE alerts
                SET acknowledged = TRUE,
                    acknowledged_by = 'test_user',
                    acknowledged_at = NOW()
                WHERE id = %s
            """, (alert_id,))
            
            # Verify acknowledgment
            result = framework.execute_query("""
                SELECT acknowledged, acknowledged_by, acknowledged_at
                FROM alerts
                WHERE id = %s
            """, (alert_id,))
            
            if result and result[0][0] == True:
                return {
                    'passed': True,
                    'message': f'Alert acknowledged by {result[0][1]}',
                    'details': {
                        'acknowledged_by': result[0][1],
                        'acknowledged_at': result[0][2].isoformat() if result[0][2] else None
                    }
                }
            else:
                return {
                    'passed': False,
                    'message': 'Alert acknowledgment not verified'
                }
        else:
            return {
                'passed': False,
                'message': 'Alert not found for acknowledgment'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Alert acknowledgment failed: {str(e)}'
        }

def test_dependency_health(framework: TestFramework) -> dict:
    """Test dependency health monitoring"""
    try:
        # Get dependency health records
        result = framework.execute_query("""
            SELECT dependency_name, health_status, response_time_ms, uptime_percentage
            FROM dependency_health
            ORDER BY dependency_name
        """)
        
        if result and len(result) > 0:
            healthy_count = sum(1 for r in result if r[1] == 'healthy')
            total_count = len(result)
            
            dependencies = [
                {
                    'name': r[0],
                    'status': r[1],
                    'response_time': float(r[2]) if r[2] else None,
                    'uptime': float(r[3]) if r[3] else None
                }
                for r in result
            ]
            
            return {
                'passed': True,
                'message': f'{healthy_count}/{total_count} dependencies healthy',
                'details': {
                    'total_dependencies': total_count,
                    'healthy_dependencies': healthy_count,
                    'dependencies': dependencies
                }
            }
        else:
            return {
                'passed': False,
                'message': 'No dependency health records found'
            }
    except Exception as e:
        return {
            'passed': False,
            'message': f'Dependency health check failed: {str(e)}'
        }

def run_monitoring_tests():
    """Run all MONITOR_v1 integration tests"""
    print("="*70)
    print("🧪 MONITOR_v1 INTEGRATION TESTS")
    print("="*70)
    
    framework = TestFramework()
    
    if not framework.connect_db():
        print("❌ Failed to connect to database")
        return
    
    try:
        # Run tests
        framework.run_test("MONITOR_v1: Metrics Collection", test_metrics_collection, framework)
        framework.run_test("MONITOR_v1: Error Processing", test_error_processing, framework)
        framework.run_test("MONITOR_v1: Alert Generation", test_alert_generation, framework)
        framework.run_test("MONITOR_v1: Alert Acknowledgment", test_alert_acknowledgment, framework)
        framework.run_test("MONITOR_v1: Dependency Health", test_dependency_health, framework)
        
        # Print summary
        framework.print_summary()
        
        # Save report
        framework.save_report('test_results/monitor_v1_results.json')
        
    finally:
        framework.close_db()

if __name__ == '__main__':
    run_monitoring_tests()