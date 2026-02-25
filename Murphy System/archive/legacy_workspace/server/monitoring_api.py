#!/usr/bin/env python3
"""
Monitoring API endpoints for dashboard
Provides REST API for metrics, alerts, errors, and dependencies
"""

import os
import json
import psycopg2
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

# Database connection
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'automation_platform')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

app = Flask(__name__)
CORS(app)

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """Get latest metrics"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get latest metrics from last 5 minutes
        cursor.execute("""
            SELECT metric_name, metric_value, metric_unit, recorded_at
            FROM metrics
            WHERE recorded_at >= NOW() - INTERVAL '5 minutes'
            ORDER BY recorded_at DESC, metric_name
            LIMIT 100
        """)
        
        metrics = []
        for row in cursor.fetchall():
            metrics.append({
                'metric_name': row[0],
                'metric_value': float(row[1]),
                'metric_unit': row[2],
                'recorded_at': row[3].isoformat()
            })
        
        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get active alerts"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get unacknowledged alerts from last 24 hours
        cursor.execute("""
            SELECT id, client_id, alert_type, alert_severity, alert_title, alert_message,
                   source_workflow, triggered_at, acknowledged, acknowledged_at
            FROM alerts
            WHERE triggered_at >= NOW() - INTERVAL '24 hours'
            ORDER BY triggered_at DESC
            LIMIT 50
        """)
        
        alerts = []
        for row in cursor.fetchall():
            alerts.append({
                'id': row[0],
                'client_id': row[1],
                'alert_type': row[2],
                'alert_severity': row[3],
                'alert_title': row[4],
                'alert_message': row[5],
                'source_workflow': row[6],
                'triggered_at': row[7].isoformat(),
                'acknowledged': row[8],
                'acknowledged_at': row[9].isoformat() if row[9] else None
            })
        
        return jsonify(alerts)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/errors', methods=['GET'])
def get_errors():
    """Get recent errors"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get errors from last 24 hours
        cursor.execute("""
            SELECT id, client_id, workflow_id, error_type, error_message,
                   error_severity, error_category, occurred_at, resolved
            FROM errors
            WHERE occurred_at >= NOW() - INTERVAL '24 hours'
            ORDER BY occurred_at DESC
            LIMIT 50
        """)
        
        errors = []
        for row in cursor.fetchall():
            errors.append({
                'id': row[0],
                'client_id': row[1],
                'workflow_id': row[2],
                'error_type': row[3],
                'error_message': row[4],
                'error_severity': row[5],
                'error_category': row[6],
                'occurred_at': row[7].isoformat(),
                'resolved': row[8]
            })
        
        return jsonify(errors)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/dependencies', methods=['GET'])
def get_dependencies():
    """Get dependency health status"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all dependency health records
        cursor.execute("""
            SELECT dependency_name, dependency_type, health_status, last_check,
                   response_time_ms, uptime_percentage, error_message
            FROM dependency_health
            ORDER BY dependency_name
        """)
        
        dependencies = []
        for row in cursor.fetchall():
            dependencies.append({
                'dependency_name': row[0],
                'dependency_type': row[1],
                'health_status': row[2],
                'last_check': row[3].isoformat(),
                'response_time_ms': float(row[4]) if row[4] else None,
                'uptime_percentage': float(row[5]) if row[5] else None,
                'error_message': row[6]
            })
        
        return jsonify(dependencies)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/health', methods=['GET'])
def get_health():
    """Get overall system health"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check database health
        cursor.execute("SELECT 1")
        db_healthy = cursor.fetchone()[0] == 1
        
        # Check for critical alerts
        cursor.execute("""
            SELECT COUNT(*) FROM alerts
            WHERE alert_severity = 'critical'
              AND acknowledged = FALSE
              AND triggered_at >= NOW() - INTERVAL '1 hour'
        """)
        critical_alerts = cursor.fetchone()[0]
        
        # Check for critical errors
        cursor.execute("""
            SELECT COUNT(*) FROM errors
            WHERE error_severity = 'critical'
              AND resolved = FALSE
              AND occurred_at >= NOW() - INTERVAL '1 hour'
        """)
        critical_errors = cursor.fetchone()[0]
        
        # Determine overall health
        overall_health = 'healthy'
        if critical_alerts > 0 or critical_errors > 0:
            overall_health = 'unhealthy'
        
        return jsonify({
            'status': overall_health,
            'database': 'healthy' if db_healthy else 'unhealthy',
            'critical_alerts': critical_alerts,
            'critical_errors': critical_errors,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE alerts
            SET acknowledged = TRUE,
                acknowledged_by = 'api',
                acknowledged_at = NOW()
            WHERE id = %s
            RETURNING id
        """, (alert_id,))
        
        if cursor.fetchone():
            conn.commit()
            return jsonify({'success': True, 'message': 'Alert acknowledged'})
        else:
            return jsonify({'error': 'Alert not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082, debug=True)