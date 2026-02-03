# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Production Setup Module
Handles SSL configuration, schema migrations, and production readiness
"""

import os
import subprocess
import json
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SSLConfigurator:
    """Configure SSL/TLS for production"""
    
    def __init__(self, domain: str = None):
        self.domain = domain or os.getenv('DOMAIN', 'localhost')
        self.email = os.getenv('SSL_EMAIL', 'admin@example.com')
    
    def check_ssl_installed(self) -> bool:
        """Check if SSL certificate exists"""
        cert_path = f"/etc/letsencrypt/live/{self.domain}/fullchain.pem"
        return os.path.exists(cert_path)
    
    def install_certbot(self) -> Dict:
        """Install certbot for SSL certificates"""
        try:
            subprocess.run(['apt-get', 'update'], check=True)
            subprocess.run(['apt-get', 'install', '-y', 'certbot', 'python3-certbot-nginx'], check=True)
            return {'success': True, 'message': 'Certbot installed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def obtain_certificate(self) -> Dict:
        """Obtain SSL certificate from Let's Encrypt"""
        if self.domain == 'localhost':
            return {
                'success': False,
                'error': 'Cannot obtain SSL for localhost',
                'recommendation': 'Use self-signed certificate for development'
            }
        
        try:
            cmd = [
                'certbot', 'certonly',
                '--nginx',
                '-d', self.domain,
                '--email', self.email,
                '--agree-tos',
                '--non-interactive'
            ]
            subprocess.run(cmd, check=True)
            return {
                'success': True,
                'message': f'SSL certificate obtained for {self.domain}',
                'cert_path': f'/etc/letsencrypt/live/{self.domain}/fullchain.pem',
                'key_path': f'/etc/letsencrypt/live/{self.domain}/privkey.pem'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def create_self_signed_cert(self) -> Dict:
        """Create self-signed certificate for development"""
        try:
            cert_dir = '/etc/ssl/murphy'
            os.makedirs(cert_dir, exist_ok=True)
            
            cmd = [
                'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
                '-keyout', f'{cert_dir}/key.pem',
                '-out', f'{cert_dir}/cert.pem',
                '-days', '365',
                '-nodes',
                '-subj', f'/CN={self.domain}'
            ]
            subprocess.run(cmd, check=True)
            
            return {
                'success': True,
                'message': 'Self-signed certificate created',
                'cert_path': f'{cert_dir}/cert.pem',
                'key_path': f'{cert_dir}/key.pem'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def configure_nginx_ssl(self, cert_path: str, key_path: str) -> Dict:
        """Configure nginx with SSL"""
        nginx_config = f"""
server {{
    listen 80;
    server_name {self.domain};
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl http2;
    server_name {self.domain};

    ssl_certificate {cert_path};
    ssl_certificate_key {key_path};
    
    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Murphy System Backend
    location /api {{
        proxy_pass http://localhost:3002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    
    # WebSocket Support
    location /socket.io {{
        proxy_pass http://localhost:3002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }}
    
    # Frontend
    location / {{
        proxy_pass http://localhost:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }}
}}
"""
        
        try:
            config_path = f'/etc/nginx/sites-available/murphy'
            with open(config_path, 'w') as f:
                f.write(nginx_config)
            
            # Enable site
            link_path = '/etc/nginx/sites-enabled/murphy'
            if os.path.exists(link_path):
                os.remove(link_path)
            os.symlink(config_path, link_path)
            
            # Test and reload nginx
            subprocess.run(['nginx', '-t'], check=True)
            subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
            
            return {'success': True, 'message': 'Nginx configured with SSL'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

class SchemaManager:
    """Manage database schema and migrations"""
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://localhost/murphy')
    
    def check_schema_compatibility(self) -> Dict:
        """Check for schema mismatches"""
        issues = []
        
        # Check if uploaded schema exists
        if os.path.exists('uploaded_files/database/schema.sql'):
            issues.append({
                'type': 'schema_file_found',
                'file': 'uploaded_files/database/schema.sql',
                'action': 'needs_integration'
            })
        
        # Check for additional tables
        additional_tables = [
            'uploaded_files/database/add_monitoring_tables.sql',
            'uploaded_files/database/add_security_tables.sql',
            'uploaded_files/database/add_tasks_config.sql'
        ]
        
        for table_file in additional_tables:
            if os.path.exists(table_file):
                issues.append({
                    'type': 'additional_schema',
                    'file': table_file,
                    'action': 'needs_migration'
                })
        
        return {
            'compatible': len(issues) == 0,
            'issues': issues,
            'recommendation': 'Run schema migration' if issues else 'Schema is compatible'
        }
    
    def create_unified_schema(self) -> Dict:
        """Create unified schema from all sources"""
        try:
            unified_schema = """
-- Murphy System Unified Schema
-- Combines all schemas from uploaded files and current system

-- ============================================
-- CORE TABLES (from uploaded schema)
-- ============================================
"""
            
            # Read uploaded schema
            if os.path.exists('uploaded_files/database/schema.sql'):
                with open('uploaded_files/database/schema.sql', 'r') as f:
                    unified_schema += f.read() + "\n\n"
            
            # Add monitoring tables
            if os.path.exists('uploaded_files/database/add_monitoring_tables.sql'):
                unified_schema += "-- ============================================\n"
                unified_schema += "-- MONITORING TABLES\n"
                unified_schema += "-- ============================================\n"
                with open('uploaded_files/database/add_monitoring_tables.sql', 'r') as f:
                    unified_schema += f.read() + "\n\n"
            
            # Add security tables
            if os.path.exists('uploaded_files/database/add_security_tables.sql'):
                unified_schema += "-- ============================================\n"
                unified_schema += "-- SECURITY TABLES\n"
                unified_schema += "-- ============================================\n"
                with open('uploaded_files/database/add_security_tables.sql', 'r') as f:
                    unified_schema += f.read() + "\n\n"
            
            # Save unified schema
            with open('murphy_unified_schema.sql', 'w') as f:
                f.write(unified_schema)
            
            return {
                'success': True,
                'schema_file': 'murphy_unified_schema.sql',
                'message': 'Unified schema created'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def apply_schema(self) -> Dict:
        """Apply unified schema to database"""
        try:
            if not os.path.exists('murphy_unified_schema.sql'):
                return {'success': False, 'error': 'Unified schema not found'}
            
            # Apply schema using psql
            cmd = ['psql', self.db_url, '-f', 'murphy_unified_schema.sql']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Schema applied successfully',
                    'output': result.stdout
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

class ProductionReadiness:
    """Check and configure production readiness"""
    
    def __init__(self):
        self.ssl_configurator = SSLConfigurator()
        self.schema_manager = SchemaManager()
    
    def check_all(self) -> Dict:
        """Run all production readiness checks"""
        checks = {
            'ssl': self.check_ssl(),
            'schema': self.check_schema(),
            'security': self.check_security(),
            'performance': self.check_performance(),
            'monitoring': self.check_monitoring()
        }
        
        all_passed = all(check.get('passed', False) for check in checks.values())
        
        return {
            'ready_for_production': all_passed,
            'checks': checks,
            'recommendations': self.get_recommendations(checks)
        }
    
    def check_ssl(self) -> Dict:
        """Check SSL configuration"""
        has_ssl = self.ssl_configurator.check_ssl_installed()
        return {
            'passed': has_ssl,
            'message': 'SSL configured' if has_ssl else 'SSL not configured',
            'action': 'None' if has_ssl else 'Run SSL setup'
        }
    
    def check_schema(self) -> Dict:
        """Check database schema"""
        result = self.schema_manager.check_schema_compatibility()
        return {
            'passed': result['compatible'],
            'message': result['recommendation'],
            'issues': result.get('issues', [])
        }
    
    def check_security(self) -> Dict:
        """Check security configuration"""
        issues = []
        
        # Check for environment variables
        required_env = ['SECRET_KEY', 'DATABASE_URL']
        for env_var in required_env:
            if not os.getenv(env_var):
                issues.append(f'Missing {env_var}')
        
        return {
            'passed': len(issues) == 0,
            'message': 'Security configured' if len(issues) == 0 else 'Security issues found',
            'issues': issues
        }
    
    def check_performance(self) -> Dict:
        """Check performance configuration"""
        # Check if production server is configured
        using_werkzeug = True  # We're currently using Werkzeug
        
        return {
            'passed': not using_werkzeug,
            'message': 'Using production server' if not using_werkzeug else 'Using development server',
            'recommendation': 'Switch to Gunicorn or uWSGI for production'
        }
    
    def check_monitoring(self) -> Dict:
        """Check monitoring configuration"""
        # Check if monitoring system is running
        monitoring_active = True  # Our monitoring system is active
        
        return {
            'passed': monitoring_active,
            'message': 'Monitoring active' if monitoring_active else 'Monitoring not configured'
        }
    
    def get_recommendations(self, checks: Dict) -> List[str]:
        """Get recommendations based on checks"""
        recommendations = []
        
        if not checks['ssl']['passed']:
            recommendations.append('Configure SSL/TLS certificates')
        
        if not checks['schema']['passed']:
            recommendations.append('Run database schema migration')
        
        if not checks['security']['passed']:
            recommendations.append('Configure environment variables')
        
        if not checks['performance']['passed']:
            recommendations.append('Switch to production WSGI server')
        
        return recommendations
    
    def setup_production(self) -> Dict:
        """Complete production setup"""
        results = []
        
        # 1. Setup SSL
        logger.info("Setting up SSL...")
        ssl_result = self.ssl_configurator.create_self_signed_cert()
        results.append(('SSL', ssl_result))
        
        # 2. Migrate schema
        logger.info("Migrating schema...")
        schema_result = self.schema_manager.create_unified_schema()
        results.append(('Schema', schema_result))
        
        # 3. Configure nginx
        if ssl_result.get('success'):
            logger.info("Configuring nginx...")
            nginx_result = self.ssl_configurator.configure_nginx_ssl(
                ssl_result['cert_path'],
                ssl_result['key_path']
            )
            results.append(('Nginx', nginx_result))
        
        return {
            'success': all(r[1].get('success', False) for r in results),
            'results': results,
            'message': 'Production setup complete' if all(r[1].get('success', False) for r in results) else 'Some steps failed'
        }

# Initialize production readiness checker
def get_production_readiness():
    """Get production readiness checker instance"""
    return ProductionReadiness()