# Murphy System Operations Runbook

## Table of Contents
1. [Common Issues](#common-issues)
2. [Emergency Procedures](#emergency-procedures)
3. [Monitoring and Alerts](#monitoring-and-alerts)
4. [Deployment Procedures](#deployment-procedures)
5. [Troubleshooting Guide](#troubleshooting-guide)

---

## Common Issues

### Issue 1: High Error Rate

**Symptoms:**
- Error rate > 10%
- Alert: `HighErrorRate` firing
- Users reporting failures

**Diagnosis:**
```bash
# Check error logs
kubectl logs -n murphy-system -l app=murphy-api --tail=100 | grep ERROR

# Check error metrics
curl http://prometheus:9090/api/v1/query?query=rate(murphy_api_errors_total[5m])
```

**Resolution:**
1. Identify error type from logs
2. Check if it's a known issue
3. If database-related, check database connectivity
4. If model-related, check shadow agent status
5. Consider rolling back if errors persist

**Rollback Command:**
```bash
./deployment/scripts/deploy.sh rollback
```

---

### Issue 2: Low Model Accuracy

**Symptoms:**
- Model accuracy < 70%
- Alert: `LowModelAccuracy` firing
- High fallback rate to Murphy Gate

**Diagnosis:**
```bash
# Check model metrics
curl http://murphy-api:8000/api/shadow-agent/stats

# Check recent predictions
kubectl exec -n murphy-system murphy-api-xxx -- python -c "
from murphy_implementation.shadow_agent import create_shadow_agent_system
system = create_shadow_agent_system()
print(system.shadow_agent.get_prediction_stats())
"
```

**Resolution:**
1. Check if model is loaded correctly
2. Review recent training data quality
3. Check for data drift
4. Consider retraining model with recent corrections
5. Temporarily increase fallback threshold

**Retrain Command:**
```python
from murphy_implementation.shadow_agent import create_shadow_agent_system

system = create_shadow_agent_system()
model_id = system.train_from_corrections(
    corrections=recent_corrections,
    tune_hyperparameters=True
)
system.deploy_model(model_id, use_gradual_rollout=True)
```

---

### Issue 3: High Response Time

**Symptoms:**
- p95 response time > 1s
- Alert: `HighResponseTime` firing
- Slow user experience

**Diagnosis:**
```bash
# Check response time distribution
curl http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,rate(murphy_api_request_duration_seconds_bucket[5m]))

# Check resource usage
kubectl top pods -n murphy-system
```

**Resolution:**
1. Check if CPU/memory limits are reached
2. Scale up if needed: `kubectl scale deployment murphy-api -n murphy-system --replicas=5`
3. Check database query performance
4. Review slow endpoints in logs
5. Consider caching frequently accessed data

---

### Issue 4: Service Down

**Symptoms:**
- Alert: `ServiceDown` firing
- API not responding
- Health check failing

**Diagnosis:**
```bash
# Check pod status
kubectl get pods -n murphy-system

# Check pod logs
kubectl logs -n murphy-system murphy-api-xxx --tail=50

# Check events
kubectl get events -n murphy-system --sort-by='.lastTimestamp'
```

**Resolution:**
1. Check if pods are running: `kubectl get pods -n murphy-system`
2. If pods are CrashLooping, check logs for errors
3. If pods are Pending, check resource availability
4. Restart deployment if needed: `kubectl rollout restart deployment/murphy-api -n murphy-system`
5. If issue persists, rollback to previous version

---

## Emergency Procedures

### Emergency Rollback

**When to use:**
- Critical production issue
- High error rate (>50%)
- Service completely down
- Data corruption detected

**Procedure:**
```bash
# 1. Immediate rollback
./deployment/scripts/deploy.sh rollback

# 2. Verify rollback
kubectl rollout status deployment/murphy-api -n murphy-system

# 3. Check health
curl http://murphy-api-service/health

# 4. Monitor metrics
# Open Grafana dashboard and verify metrics are normal

# 5. Notify team
# Send notification to #murphy-alerts channel
```

---

### Emergency Scale-Up

**When to use:**
- Sudden traffic spike
- High CPU/memory usage
- Slow response times

**Procedure:**
```bash
# 1. Scale up replicas
kubectl scale deployment murphy-api -n murphy-system --replicas=10

# 2. Verify scaling
kubectl get pods -n murphy-system -w

# 3. Monitor performance
# Check Grafana dashboard for improvements

# 4. Adjust HPA if needed
kubectl edit hpa murphy-api-hpa -n murphy-system
```

---

### Emergency Maintenance Mode

**When to use:**
- Critical bug fix needed
- Database maintenance
- Security patch

**Procedure:**
```bash
# 1. Enable maintenance mode
kubectl set env deployment/murphy-api -n murphy-system MAINTENANCE_MODE=true

# 2. Scale down to 1 replica
kubectl scale deployment murphy-api -n murphy-system --replicas=1

# 3. Perform maintenance
# ... your maintenance tasks ...

# 4. Disable maintenance mode
kubectl set env deployment/murphy-api -n murphy-system MAINTENANCE_MODE=false

# 5. Scale back up
kubectl scale deployment murphy-api -n murphy-system --replicas=3
```

---

## Monitoring and Alerts

### Alert Response Matrix

| Alert | Severity | Response Time | Action |
|-------|----------|---------------|--------|
| HighErrorRate | Critical | Immediate | Investigate logs, consider rollback |
| ServiceDown | Critical | Immediate | Check pods, restart if needed |
| LowModelAccuracy | Warning | 1 hour | Review model performance, plan retrain |
| HighResponseTime | Warning | 30 minutes | Check resources, scale if needed |
| HighMemoryUsage | Warning | 1 hour | Monitor, scale if continues |
| LowDataQuality | Info | 4 hours | Review training data |

### Dashboard Access

- **Grafana:** http://grafana.murphy-system.com
- **Prometheus:** http://prometheus.murphy-system.com
- **Kubernetes Dashboard:** http://k8s-dashboard.murphy-system.com

### Key Metrics to Monitor

1. **API Health:**
   - Request rate
   - Error rate
   - Response time (p50, p95, p99)

2. **Model Performance:**
   - Accuracy
   - Confidence distribution
   - Fallback rate

3. **System Resources:**
   - CPU usage
   - Memory usage
   - Disk usage

4. **Business Metrics:**
   - Shadow agent usage rate
   - Training data quality
   - Correction capture rate

---

## Deployment Procedures

### Standard Deployment

```bash
# 1. Run tests locally
pytest tests/

# 2. Build and test Docker image
docker build -t murphy-system:test -f murphy_implementation/deployment/Dockerfile .
docker run murphy-system:test python -m pytest

# 3. Deploy to staging
./deployment/scripts/deploy.sh staging

# 4. Run smoke tests on staging
curl http://staging.murphy-system.com/health

# 5. Deploy to production
./deployment/scripts/deploy.sh production

# 6. Monitor deployment
kubectl rollout status deployment/murphy-api -n murphy-system

# 7. Verify health
curl http://murphy-api-service/health
```

### Hotfix Deployment

```bash
# 1. Create hotfix branch
git checkout -b hotfix/critical-fix

# 2. Make fix and test
# ... make changes ...
pytest tests/

# 3. Fast-track deployment
./deployment/scripts/deploy.sh production latest

# 4. Monitor closely
# Watch Grafana dashboard for 30 minutes

# 5. Merge to main
git checkout main
git merge hotfix/critical-fix
```

---

## Troubleshooting Guide

### Database Connection Issues

**Symptoms:**
- Database connection errors in logs
- Timeouts on database operations

**Steps:**
```bash
# 1. Check database pod
kubectl get pods -n murphy-system | grep postgres

# 2. Check database logs
kubectl logs -n murphy-system postgres-xxx

# 3. Test connection
kubectl exec -n murphy-system murphy-api-xxx -- python -c "
import psycopg2
conn = psycopg2.connect('postgresql://murphy:murphy@postgres:5432/murphy')
print('Connection successful')
"

# 4. Check connection pool
# Review connection pool settings in application config
```

---

### Model Loading Issues

**Symptoms:**
- "No model loaded" errors
- Shadow agent not making predictions

**Steps:**
```bash
# 1. Check model registry
kubectl exec -n murphy-system murphy-api-xxx -- python -c "
from murphy_implementation.shadow_agent import ModelRegistry
registry = ModelRegistry()
print(registry.get_registry_summary())
"

# 2. Check deployed model
# Verify model is marked as deployed in registry

# 3. Reload model
# Restart pods to reload model
kubectl rollout restart deployment/murphy-api -n murphy-system
```

---

### Memory Leaks

**Symptoms:**
- Gradually increasing memory usage
- OOMKilled pods
- Slow performance over time

**Steps:**
```bash
# 1. Check memory usage trend
# Open Grafana and check memory usage over 24h

# 2. Get memory profile
kubectl exec -n murphy-system murphy-api-xxx -- python -m memory_profiler

# 3. Restart pods to free memory
kubectl rollout restart deployment/murphy-api -n murphy-system

# 4. Investigate code for leaks
# Review recent changes for potential memory leaks
```

---

## Contact Information

- **On-Call Engineer:** Check PagerDuty schedule
- **Team Lead:** [email]
- **DevOps Team:** #devops-murphy
- **Slack Alerts:** #murphy-alerts
- **Incident Channel:** #murphy-incidents

---

## Useful Commands

```bash
# View logs
kubectl logs -n murphy-system -l app=murphy-api --tail=100 -f

# Get pod status
kubectl get pods -n murphy-system

# Describe pod
kubectl describe pod -n murphy-system murphy-api-xxx

# Execute command in pod
kubectl exec -n murphy-system murphy-api-xxx -- command

# Port forward for local access
kubectl port-forward -n murphy-system svc/murphy-api-service 8000:80

# View resource usage
kubectl top pods -n murphy-system

# View events
kubectl get events -n murphy-system --sort-by='.lastTimestamp'

# Scale deployment
kubectl scale deployment murphy-api -n murphy-system --replicas=5

# Restart deployment
kubectl rollout restart deployment/murphy-api -n murphy-system

# Check rollout status
kubectl rollout status deployment/murphy-api -n murphy-system

# View deployment history
kubectl rollout history deployment/murphy-api -n murphy-system
```