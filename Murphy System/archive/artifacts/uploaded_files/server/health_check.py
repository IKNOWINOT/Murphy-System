#!/usr/bin/env python3
"""
Health Check Server for Client-Facing Automation System
Provides health, readiness, and liveness endpoints
"""

import os
import sys
import json
import time
import psycopg2
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import subprocess

# Configuration
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
POSTGRES_DB = os.getenv('POSTGRES_DB', 'automation_platform')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Handle health check requests"""
    
    def _set_headers(self, status_code=200):
        """Set response headers"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
    
    def _check_database(self):
        """Check PostgreSQL database connectivity"""
        try:
            start_time = time.time()
            conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD
            )
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.fetchone()
            cursor.close()
            conn.close()
            latency = round((time.time() - start_time) * 1000, 2)
            return True, latency, None
        except Exception as e:
            return False, 0, str(e)
    
    def _check_n8n(self):
        """Check if n8n is running"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'n8n'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Count active executions
                return True, int(result.stdout.strip().count('\n')) + 1, None
            return False, 0, "n8n process not found"
        except Exception as e:
            return False, 0, str(e)
    
    def _check_storage(self):
        """Check file storage availability"""
        try:
            storage_path = os.getenv('LOCAL_STORAGE_PATH', '/workspace/storage')
            if os.path.exists(storage_path) and os.access(storage_path, os.W_OK):
                disk_usage = os.statvfs(storage_path)
                total = disk_usage.f_frsize * disk_usage.f_blocks
                free = disk_usage.f_frsize * disk_usage.f_bavail
                used_percent = round(((total - free) / total) * 100, 2)
                return True, used_percent, None
            return False, 0, f"Storage path {storage_path} not accessible"
        except Exception as e:
            return False, 0, str(e)
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health' or self.path == '/':
            # Main health check
            db_healthy, db_latency, db_error = self._check_database()
            n8n_healthy, n8n_active, n8n_error = self._check_n8n()
            storage_healthy, storage_usage, storage_error = self._check_storage()
            
            overall_healthy = db_healthy and storage_healthy
            
            response = {
                "status": "healthy" if overall_healthy else "unhealthy",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "checks": {
                    "database": {
                        "status": "healthy" if db_healthy else "unhealthy",
                        "latency_ms": db_latency,
                        "error": db_error
                    },
                    "n8n": {
                        "status": "healthy" if n8n_healthy else "unhealthy",
                        "active_executions": n8n_active if n8n_healthy else 0,
                        "error": n8n_error
                    },
                    "storage": {
                        "status": "healthy" if storage_healthy else "unhealthy",
                        "disk_usage_percent": storage_usage,
                        "error": storage_error
                    }
                }
            }
            
            self._set_headers(200 if overall_healthy else 503)
            self.wfile.write(json.dumps(response, indent=2).encode())
        
        elif self.path == '/ready':
            # Readiness check - can we accept requests?
            db_healthy, _, _ = self._check_database()
            n8n_healthy, _, _ = self._check_n8n()
            
            ready = db_healthy and n8n_healthy
            
            response = {
                "status": "ready" if ready else "not_ready",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            self._set_headers(200 if ready else 503)
            self.wfile.write(json.dumps(response, indent=2).encode())
        
        elif self.path == '/live':
            # Liveness check - are main processes running?
            n8n_healthy, _, _ = self._check_n8n()
            db_healthy, _, _ = self._check_database()
            
            alive = n8n_healthy or db_healthy
            
            response = {
                "status": "alive" if alive else "dead",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            self._set_headers(200 if alive else 503)
            self.wfile.write(json.dumps(response, indent=2).encode())
        
        elif self.path == '/health/dependencies':
            # Check external dependencies
            checks = {
                "postgres": self._check_database(),
                "n8n": self._check_n8n(),
                "storage": self._check_storage()
            }
            
            response = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "dependencies": {
                    name: {
                        "status": "healthy" if healthy else "unhealthy",
                        "error": error
                    }
                    for name, (healthy, _, error) in checks.items()
                }
            }
            
            all_healthy = all(healthy for healthy, _, _ in checks.values())
            self._set_headers(200 if all_healthy else 503)
            self.wfile.write(json.dumps(response, indent=2).encode())
        
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Not found"}')
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

def run_server(port=8080):
    """Start the health check server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    print(f"Health check server starting on port {port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down health check server")
        httpd.shutdown()

if __name__ == '__main__':
    port = int(os.getenv('HEALTH_CHECK_PORT', 8081))
    run_server(port)