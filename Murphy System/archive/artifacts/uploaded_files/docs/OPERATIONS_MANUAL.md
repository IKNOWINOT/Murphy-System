# Operations Manual

## Table of Contents

1. [System Operations](#system-operations)
2. [Startup & Shutdown Procedures](#startup--shutdown-procedures)
3. [Backup & Recovery](#backup--recovery)
4. [Monitoring & Alerting](#monitoring--alerting)
5. [Troubleshooting](#troubleshooting)
6. [Incident Response](#incident-response)
7. [Maintenance Procedures](#maintenance-procedures)
8. [Performance Tuning](#performance-tuning)

---

## System Operations

### Service Overview

The automation platform consists of 5 core services:

| Service | Port | Purpose | Auto-Start |
|---------|------|---------|------------|
| PostgreSQL | 5432 | Database | Yes |
| n8n | 5678 | Workflow engine | Yes |
| Health Check | 8081 | System health | Manual |
| Monitoring API | 8082 | Dashboard API | Manual |
| Dashboard | 8083 | Web dashboards | Manual |

### Service Dependencies

```
PostgreSQL (must start first)
    ↓
n8n (depends on PostgreSQL)
    ↓
Health Check, Monitoring API, Dashboards (depend on PostgreSQL and n8n)
```

---

## Startup & Shutdown Procedures

### System Startup

#### 1. Start PostgreSQL

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL if not running
sudo systemctl start postgresql

# Verify connection
psql -U postgres -d automation_platform -c "SELECT 1"
```

**Expected Output:** `1` (single row)

#### 2. Start n8n

```bash
# Start n8n in background
nohup n8n start > /workspace/storage/logs/n8n.log 2>&1 &

# Verify n8n is running
curl http://localhost:5678/healthz

# Check active workflows
sqlite3 /root/.n8n/database.sqlite "SELECT name, active FROM workflow_entity WHERE active = 1"
```

**Expected Output:** HTTP 200 response, list of active workflows

#### 3. Start Health Check Server

```bash
# Start health check server
cd /workspace
nohup python3 server/health_check.py > /workspace/storage/logs/health_check.log 2>&1 &

# Verify health check
curl http://localhost:8081/health
```

**Expected Output:** JSON with status "healthy"

#### 4. Start Monitoring API

```bash
# Start monitoring API
cd /workspace
nohup python3 server/monitoring_api.py > /workspace/storage/logs/monitoring_api.log 2>&1 &

# Verify API
curl http://localhost:8082/api/health
```

**Expected Output:** JSON with system health status

#### 5. Start Dashboard Server

```bash
# Start dashboard server
cd /workspace/dashboard
nohup python3 -m http.server 8083 > /workspace/storage/logs/dashboard.log 2>&1 &

# Verify dashboard
curl http://localhost:8083/monitoring_dashboard.html
```

**Expected Output:** HTML content

### Complete Startup Script

```bash
#!/bin/bash
# File: /workspace/scripts/startup.sh

echo "Starting Automation Platform..."

# 1. Start PostgreSQL
echo "Starting PostgreSQL..."
sudo systemctl start postgresql
sleep 2

# 2. Start n8n
echo "Starting n8n..."
nohup n8n start > /workspace/storage/logs/n8n.log 2>&1 &
sleep 5

# 3. Start Health Check
echo "Starting Health Check Server..."
cd /workspace
nohup python3 server/health_check.py > /workspace/storage/logs/health_check.log 2>&1 &
sleep 2

# 4. Start Monitoring API
echo "Starting Monitoring API..."
nohup python3 server/monitoring_api.py > /workspace/storage/logs/monitoring_api.log 2>&1 &
sleep 2

# 5. Start Dashboard
echo "Starting Dashboard Server..."
cd /workspace/dashboard
nohup python3 -m http.server 8083 > /workspace/storage/logs/dashboard.log 2>&1 &

echo "All services started!"
echo "Health Check: http://localhost:8081/health"
echo "n8n UI: http://localhost:5678"
echo "Monitoring Dashboard: http://localhost:8083/monitoring_dashboard.html"
```

### System Shutdown

#### Graceful Shutdown

```bash
#!/bin/bash
# File: /workspace/scripts/shutdown.sh

echo "Shutting down Automation Platform..."

# 1. Stop Dashboard
echo "Stopping Dashboard Server..."
pkill -f "python3 -m http.server 8083"

# 2. Stop Monitoring API
echo "Stopping Monitoring API..."
pkill -f "monitoring_api.py"

# 3. Stop Health Check
echo "Stopping Health Check Server..."
pkill -f "health_check.py"

# 4. Stop n8n (graceful)
echo "Stopping n8n..."
pkill -SIGTERM -f "n8n start"
sleep 5

# 5. Stop PostgreSQL
echo "Stopping PostgreSQL..."
sudo systemctl stop postgresql

echo "All services stopped!"
```

#### Emergency Shutdown

```bash
# Force kill all services
pkill -9 -f "n8n start"
pkill -9 -f "python3"
sudo systemctl stop postgresql
```

---

## Backup & Recovery

### Automated Backup

**Backup Script:** `/workspace/scripts/backup.sh`

**Schedule:** Daily at 2 AM (configure with cron)

```bash
# Add to crontab
crontab -e

# Add this line:
0 2 * * * /workspace/scripts/backup.sh
```

**Backup Contents:**
- Complete PostgreSQL database dump
- n8n workflow definitions (SQLite)
- Configuration files
- Encryption keys

**Backup Location:** `/workspace/backups/`

**Retention:** 30 days (automatic cleanup)

### Manual Backup

```bash
# Run backup script manually
/workspace/scripts/backup.sh

# Verify backup
ls -lh /workspace/backups/
```

### Database Recovery

#### Full Database Restore

```bash
# 1. Stop all services
/workspace/scripts/shutdown.sh

# 2. List available backups
ls -lh /workspace/backups/

# 3. Restore from backup
BACKUP_FILE="/workspace/backups/automation_platform_YYYYMMDD_HHMMSS.sql"
psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS automation_platform"
psql -U postgres -d postgres -c "CREATE DATABASE automation_platform"
psql -U postgres -d automation_platform -f $BACKUP_FILE

# 4. Verify restoration
psql -U postgres -d automation_platform -c "\dt"

# 5. Restart services
/workspace/scripts/startup.sh
```

#### Workflow Recovery

```bash
# 1. Backup current n8n database
cp /root/.n8n/database.sqlite /root/.n8n/database.sqlite.backup

# 2. Restore from backup
BACKUP_FILE="/workspace/backups/n8n_database_YYYYMMDD.sqlite"
cp $BACKUP_FILE /root/.n8n/database.sqlite

# 3. Restart n8n
pkill -f "n8n start"
nohup n8n start > /workspace/storage/logs/n8n.log 2>&1 &

# 4. Verify workflows
curl http://localhost:5678/healthz
```

---

## Monitoring & Alerting

### Health Check Endpoints

#### System Health

```bash
# Overall system health
curl http://localhost:8081/health

# Expected response:
{
  "status": "healthy",
  "database": {"status": "healthy", "latency_ms": 7.5},
  "n8n": {"status": "healthy", "active_executions": 2},
  "storage": {"status": "healthy", "disk_usage_percent": 77.7}
}
```

#### Readiness Check

```bash
# Check if system is ready to accept requests
curl http://localhost:8081/ready

# Expected response:
{"status": "ready"}
```

#### Liveness Check

```bash
# Check if system is alive
curl http://localhost:8081/live

# Expected response:
{"status": "alive"}
```

### Monitoring Dashboards

#### Access Dashboards

1. **Monitoring Dashboard:** http://localhost:8083/monitoring_dashboard.html
   - System metrics
   - Active alerts
   - Recent errors
   - Dependency health

2. **Task Dashboard:** http://localhost:8080/task_dashboard.html
   - Task statistics
   - Team performance
   - Task list

3. **Security Dashboard:** http://localhost:8080/security_dashboard.html
   - Credential management
   - Security events
   - Role management

### Alert Management

#### View Active Alerts

```bash
# Query active alerts
psql -U postgres -d automation_platform << EOF
SELECT alert_severity, alert_type, alert_title, triggered_at
FROM alerts
WHERE acknowledged = FALSE
ORDER BY triggered_at DESC
LIMIT 10;
EOF
```

#### Acknowledge Alert

```bash
# Acknowledge alert via API
curl -X POST http://localhost:8082/api/alerts/ALERT_ID/acknowledge

# Or via database
psql -U postgres -d automation_platform << EOF
UPDATE alerts
SET acknowledged = TRUE,
    acknowledged_by = 'admin',
    acknowledged_at = NOW()
WHERE id = ALERT_ID;
EOF
```

### Metrics Collection

#### View Recent Metrics

```bash
# Query recent metrics
psql -U postgres -d automation_platform << EOF
SELECT metric_name, metric_value, metric_unit, recorded_at
FROM metrics
WHERE recorded_at >= NOW() - INTERVAL '1 hour'
ORDER BY recorded_at DESC
LIMIT 20;
EOF
```

#### Key Metrics to Monitor

| Metric | Threshold | Action |
|--------|-----------|--------|
| Workflow error rate | >10% | Investigate errors |
| Disk usage | >90% | Clean up old files |
| Database connections | >80% of max | Check for leaks |
| DLQ count | >50 items | Review failed operations |
| Response time | >5 seconds | Performance tuning |

---

## Troubleshooting

### Common Issues

#### Issue 1: n8n Won't Start

**Symptoms:**
- n8n process exits immediately
- Error in logs: "Database locked"

**Solution:**
```bash
# 1. Check if n8n is already running
ps aux | grep n8n

# 2. Kill existing processes
pkill -f "n8n start"

# 3. Check database file
ls -lh /root/.n8n/database.sqlite

# 4. Remove lock file if exists
rm -f /root/.n8n/database.sqlite-shm
rm -f /root/.n8n/database.sqlite-wal

# 5. Restart n8n
nohup n8n start > /workspace/storage/logs/n8n.log 2>&1 &
```

#### Issue 2: Database Connection Failures

**Symptoms:**
- Workflows fail with "connection refused"
- Health check shows database unhealthy

**Solution:**
```bash
# 1. Check PostgreSQL status
sudo systemctl status postgresql

# 2. Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log

# 3. Test connection
psql -U postgres -d automation_platform -c "SELECT 1"

# 4. Restart PostgreSQL if needed
sudo systemctl restart postgresql

# 5. Verify connection
psql -U postgres -d automation_platform -c "\conninfo"
```

#### Issue 3: Workflows Not Executing

**Symptoms:**
- Workflows show as active but don't execute
- No execution logs

**Solution:**
```bash
# 1. Check workflow status
sqlite3 /root/.n8n/database.sqlite "SELECT name, active FROM workflow_entity"

# 2. Check n8n logs
tail -f /workspace/storage/logs/n8n.log

# 3. Manually trigger workflow via n8n UI
# Navigate to http://localhost:5678

# 4. Check for errors in workflow_executions table
psql -U postgres -d automation_platform << EOF
SELECT workflow_name, status, error_message
FROM workflow_executions
WHERE status = 'failed'
ORDER BY started_at DESC
LIMIT 10;
EOF
```

#### Issue 4: High Disk Usage

**Symptoms:**
- Disk usage >90%
- System slow or unresponsive

**Solution:**
```bash
# 1. Check disk usage
df -h

# 2. Find large files
du -sh /workspace/* | sort -hr | head -10

# 3. Clean up old logs
find /workspace/storage/logs -name "*.log" -mtime +30 -delete

# 4. Clean up old backups
find /workspace/backups -name "*.sql" -mtime +30 -delete

# 5. Vacuum database
psql -U postgres -d automation_platform -c "VACUUM FULL"
```

#### Issue 5: Monitoring Dashboard Not Loading

**Symptoms:**
- Dashboard shows "Failed to load metrics"
- API returns errors

**Solution:**
```bash
# 1. Check Monitoring API status
curl http://localhost:8082/api/health

# 2. Check API logs
tail -f /workspace/storage/logs/monitoring_api.log

# 3. Restart Monitoring API
pkill -f "monitoring_api.py"
cd /workspace
nohup python3 server/monitoring_api.py > /workspace/storage/logs/monitoring_api.log 2>&1 &

# 4. Verify API is running
curl http://localhost:8082/api/metrics
```

### Log Locations

| Service | Log Location |
|---------|-------------|
| n8n | `/workspace/storage/logs/n8n.log` |
| Health Check | `/workspace/storage/logs/health_check.log` |
| Monitoring API | `/workspace/storage/logs/monitoring_api.log` |
| Dashboard | `/workspace/storage/logs/dashboard.log` |
| PostgreSQL | `/var/log/postgresql/postgresql-15-main.log` |

### Diagnostic Commands

```bash
# System overview
/workspace/scripts/system_status.sh

# Check all services
ps aux | grep -E "n8n|postgres|python3"

# Check ports
netstat -tulpn | grep -E "5432|5678|8081|8082|8083"

# Check disk space
df -h

# Check memory usage
free -h

# Check database size
psql -U postgres -d automation_platform -c "SELECT pg_size_pretty(pg_database_size('automation_platform'))"

# Check workflow execution count
psql -U postgres -d automation_platform -c "SELECT COUNT(*) FROM workflow_executions"
```

---

## Incident Response

### Incident Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| P1 - Critical | System down, data loss | Immediate | Escalate immediately |
| P2 - High | Major functionality broken | 1 hour | Escalate if not resolved in 2 hours |
| P3 - Medium | Minor functionality issues | 4 hours | Escalate if not resolved in 8 hours |
| P4 - Low | Cosmetic issues, requests | 24 hours | No escalation needed |

### Incident Response Playbook

#### P1 - Critical Incident

**Examples:**
- Database corruption
- Complete system outage
- Data breach

**Response Steps:**
1. **Immediate Actions (0-5 minutes)**
   - Acknowledge incident
   - Assess impact
   - Notify stakeholders
   - Begin investigation

2. **Containment (5-15 minutes)**
   - Stop affected services if needed
   - Prevent further damage
   - Preserve evidence

3. **Resolution (15-60 minutes)**
   - Restore from backup if needed
   - Fix root cause
   - Verify system functionality

4. **Post-Incident (After resolution)**
   - Document incident
   - Conduct post-mortem
   - Implement preventive measures

#### P2 - High Priority Incident

**Examples:**
- Workflow failures
- Performance degradation
- Integration failures

**Response Steps:**
1. Investigate error logs
2. Identify root cause
3. Implement fix
4. Test thoroughly
5. Monitor for recurrence

### Emergency Contacts

| Role | Contact | Availability |
|------|---------|-------------|
| System Admin | admin@company.com | 24/7 |
| Database Admin | dba@company.com | Business hours |
| Security Team | security@company.com | 24/7 |
| Support Team | support@company.com | Business hours |

---

## Maintenance Procedures

### Daily Maintenance

```bash
#!/bin/bash
# Daily maintenance script

# 1. Check system health
curl http://localhost:8081/health

# 2. Check disk space
df -h | grep -E "/$|/workspace"

# 3. Review error logs
tail -n 100 /workspace/storage/logs/n8n.log | grep -i error

# 4. Check active alerts
psql -U postgres -d automation_platform -c "SELECT COUNT(*) FROM alerts WHERE acknowledged = FALSE"

# 5. Verify backups
ls -lh /workspace/backups/ | tail -5
```

### Weekly Maintenance

```bash
#!/bin/bash
# Weekly maintenance script

# 1. Database statistics
psql -U postgres -d automation_platform << EOF
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
EOF

# 2. Workflow execution statistics
psql -U postgres -d automation_platform << EOF
SELECT 
  workflow_name,
  COUNT(*) as total,
  COUNT(CASE WHEN status = 'success' THEN 1 END) as success,
  COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
FROM workflow_executions
WHERE started_at >= NOW() - INTERVAL '7 days'
GROUP BY workflow_name
ORDER BY total DESC;
EOF

# 3. Clean up old logs
find /workspace/storage/logs -name "*.log" -mtime +7 -exec gzip {} \;

# 4. Vacuum database
psql -U postgres -d automation_platform -c "VACUUM ANALYZE"
```

### Monthly Maintenance

```bash
#!/bin/bash
# Monthly maintenance script

# 1. Full database backup
/workspace/scripts/backup.sh

# 2. Clean up old backups (keep 30 days)
find /workspace/backups -name "*.sql" -mtime +30 -delete

# 3. Update statistics
psql -U postgres -d automation_platform -c "ANALYZE"

# 4. Check for unused indexes
psql -U postgres -d automation_platform << EOF
SELECT 
  schemaname,
  tablename,
  indexname,
  idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;
EOF

# 5. Generate monthly report
python3 /workspace/scripts/generate_monthly_report.py
```

---

## Performance Tuning

### Database Optimization

#### Query Performance

```sql
-- Find slow queries
SELECT 
  query,
  calls,
  total_time,
  mean_time,
  max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Add missing indexes
CREATE INDEX CONCURRENTLY idx_name ON table_name(column_name);

-- Update statistics
ANALYZE table_name;
```

#### Connection Pooling

```bash
# Check active connections
psql -U postgres -d automation_platform << EOF
SELECT 
  count(*) as connections,
  state
FROM pg_stat_activity
GROUP BY state;
EOF

# Kill idle connections
psql -U postgres -d automation_platform << EOF
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND state_change < NOW() - INTERVAL '1 hour';
EOF
```

### Workflow Optimization

#### Identify Slow Workflows

```sql
-- Find slowest workflows
SELECT 
  workflow_name,
  AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds,
  COUNT(*) as execution_count
FROM workflow_executions
WHERE completed_at IS NOT NULL
GROUP BY workflow_name
ORDER BY avg_duration_seconds DESC
LIMIT 10;
```

#### Optimize Workflow Execution

1. **Batch Processing:** Process multiple items in single execution
2. **Async Operations:** Use non-blocking operations where possible
3. **Caching:** Cache frequently accessed data
4. **Parallel Execution:** Run independent tasks in parallel

### System Resource Optimization

```bash
# Check CPU usage
top -bn1 | grep "Cpu(s)"

# Check memory usage
free -h

# Check I/O wait
iostat -x 1 5

# Optimize if needed:
# 1. Increase PostgreSQL shared_buffers
# 2. Adjust n8n worker threads
# 3. Add more RAM
# 4. Use SSD for database
```

---

## Appendix

### Quick Reference Commands

```bash
# Start system
/workspace/scripts/startup.sh

# Stop system
/workspace/scripts/shutdown.sh

# Check health
curl http://localhost:8081/health

# View logs
tail -f /workspace/storage/logs/n8n.log

# Backup database
/workspace/scripts/backup.sh

# Access n8n UI
http://localhost:5678

# Access monitoring dashboard
http://localhost:8083/monitoring_dashboard.html
```

### Configuration Files

| File | Purpose |
|------|---------|
| `/workspace/config/.env.example` | Environment variables template |
| `/root/.n8n/config` | n8n configuration |
| `/etc/postgresql/15/main/postgresql.conf` | PostgreSQL configuration |

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-29  
**Maintained By:** Operations Team