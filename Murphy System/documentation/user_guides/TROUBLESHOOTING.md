# Troubleshooting Guide - Murphy System Runtime

**Common issues and solutions**

---

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Server Issues](#server-issues)
3. [API Issues](#api-issues)
4. [Performance Issues](#performance-issues)
5. [Configuration Issues](#configuration-issues)
6. [Data Issues](#data-issues)
7. [Network Issues](#network-issues)
8. [Getting Help](#getting-help)

---

## Installation Issues

### Issue: Python Version Incompatible

**Symptoms**:
- Installation fails with Python version errors
- Module import errors

**Diagnosis**:
```bash
python --version
# Should be 3.10 or higher
```

**Solutions**:

1. **Install Python 3.10+**:
   ```bash
   # Linux
   sudo apt-get update
   sudo apt-get install python3.10

   # macOS
   brew install python@3.10

   # Windows
   # Download from https://www.python.org/downloads/
   ```

2. **Use Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```

3. **Verify Installation**:
   ```bash
   python --version
   pip --version
   ```

---

### Issue: Dependencies Not Found

**Symptoms**:
- Import errors for required packages
- Module not found errors

**Diagnosis**:
```bash
pip list | grep -E "rich|prompt-toolkit|pyyaml"
```

**Solutions**:

1. **Upgrade pip**:
   ```bash
   pip install --upgrade pip
   ```

2. **Reinstall Dependencies**:
   ```bash
   pip install --force-reinstall -r requirements_murphy_1.0.txt
   ```

3. **Install Manually**:
   ```bash
   pip install rich prompt-toolkit pyyaml networkx cryptography numpy
   ```

4. **Check Python Path**:
   ```bash
   python -c "import sys; print(sys.path)"
   ```

---

### Issue: Permission Denied

**Symptoms**:
- Permission denied errors during installation
- Cannot write to directories

**Solutions**:

1. **Use Virtual Environment** (Recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements_murphy_1.0.txt
   ```

2. **User Installation**:
   ```bash
   pip install --user -r requirements_murphy_1.0.txt
   ```

3. **Fix Permissions** (Linux/macOS):
   ```bash
   sudo chown -R $USER ~/.local
   ```

---

## Server Issues

### Issue: Server Won't Start

**Symptoms**:
- API server fails to start
- No response on health endpoint

**Diagnosis**:
```bash
# Check if server is running
ps aux | grep murphy_system_1.0_runtime

# Check port usage
lsof -i :8000
netstat -tuln | grep 8000
```

**Solutions**:

1. **Kill Existing Process**:
   ```bash
   # Find process
   lsof -i :8000

   # Kill process
   kill -9 <PID>
   ```

2. **Use Different Port**:
   ```bash
   python murphy_system_1.0_runtime.py --port 8053
   ```

3. **Check Logs**:
   ```bash
   # Run with verbose output
   python murphy_system_1.0_runtime.py --log-level DEBUG
   ```

4. **Verify Dependencies**:
   ```bash
   python -c "import src.system_integrator; print('OK')"
   ```

---

### Issue: Server Crashes

**Symptoms**:
- Server stops unexpectedly
- Crash dumps or errors

**Diagnosis**:
```bash
# Check logs
tail -f /var/log/murphy-production.log

# Check system resources
htop
free -h
df -h
```

**Solutions**:

1. **Increase Memory**:
   ```bash
   # Check available memory
   free -h

   # Add swap space if needed
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

2. **Reduce Cache Size**:
   ```yaml
   # Edit config.yaml
   cache:
     enabled: true
     level: 2  # Reduce from 3
     max_size: 512  # Reduce from 1024
   ```

3. **Enable Debug Mode**:
   ```bash
   python murphy_system_1.0_runtime.py --log-level DEBUG
   ```

4. **Check System Logs**:
   ```bash
   journalctl -xe
   dmesg | tail
   ```

---

### Issue: High Memory Usage

**Symptoms**:
- Server consuming excessive memory
- System becomes slow

**Diagnosis**:
```bash
# Check memory usage
ps aux | grep murphy_system_1.0_runtime
top -p $(pgrep -f murphy_system_1.0_runtime)
```

**Solutions**:

1. **Reduce Cache Size**:
   ```yaml
   cache:
     max_size: 256  # Reduce from 1024
   ```

2. **Enable Garbage Collection**:
   ```python
   # In your code
   import gc
   gc.collect()
   ```

3. **Limit Workers**:
   ```yaml
   server:
     workers: 4  # Reduce from 8
   ```

4. **Monitor Memory**:
   ```bash
   # Monitor memory usage
   watch -n 1 'ps aux | grep murphy_system_1.0_runtime'
   ```

---

## API Issues

### Issue: API Returns 500 Errors

**Symptoms**:
- Internal server errors
- API requests fail

**Diagnosis**:
```bash
# Check server logs
tail -f /var/log/murphy-production.log

# Test with curl
curl -v http://localhost:8000/api/health
```

**Solutions**:

1. **Check Server Logs**:
   ```bash
   tail -100 /var/log/murphy-production.log
   ```

2. **Verify Request Format**:
   ```bash
   # Check JSON validity
   echo '{"test": "data"}' | jq .
   ```

3. **Check Authentication**:
   ```bash
   # Verify API key
   curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8000/api/health
   ```

4. **Test with Simple Request**:
   ```bash
   curl http://localhost:8000/api/health
   ```

---

### Issue: Rate Limit Exceeded

**Symptoms**:
- 429 Too Many Requests error from `POST /api/auth/login`
- Login attempts blocked (IP locked out)

> **Note:** Only `POST /api/auth/login` failures count toward the brute-force
> lockout.  Chat (`/api/chat`), Librarian (`/api/librarian/ask`), and all other
> API endpoints return `401` on auth failure but **never** contribute to the
> lockout counter.  If you see `429` on non-login endpoints it is the API
> per-minute rate limiter, not the brute-force tracker.

**Diagnosis**:
```bash
# Check rate limit headers
curl -I http://localhost:8000/api/health
```

**Solutions**:

1. **Check Rate Limit Headers**:
   ```bash
   curl -I http://localhost:8000/api/health | grep -i rate
   ```

2. **Wait and Retry**:
   ```bash
   # Wait for Retry-After seconds
   sleep 60
   # Retry request
   ```

3. **Upgrade Plan** (If using hosted service):
   - Contact support for higher limits
   - Upgrade to higher tier

4. **Implement Exponential Backoff**:
   ```python
   import time
   
   for attempt in range(3):
       try:
           response = make_request()
           break
       except RateLimitError:
           wait_time = 2 ** attempt
           time.sleep(wait_time)
   ```

---

### Issue: Authentication Failed

**Symptoms**:
- 401 Unauthorized errors
- Invalid API key errors

**Diagnosis**:
```bash
# Test with API key
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8000/api/health
```

**Solutions**:

1. **Verify API Key**:
   ```bash
   # Check API key is correct
   echo "YOUR_API_KEY" | wc -c
   ```

2. **Generate New API Key**:
   ```python
   from src.auth import APIKeyManager
   
   manager = APIKeyManager()
   api_key = manager.generate_key(user_id="user_123")
   print(api_key)
   ```

3. **Check Scopes**:
   ```bash
   # Ensure API key has required scopes
   curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8000/api/experts
   ```

4. **Check API Key Expiration**:
   ```python
   from src.auth import APIKeyManager
   
   manager = APIKeyManager()
   is_valid = manager.validate_key("YOUR_API_KEY")
   print(is_valid)
   ```

---

## Performance Issues

### Issue: Slow Response Times

**Symptoms**:
- API responses take long time
- System feels sluggish

**Diagnosis**:
```bash
# Measure response time
time curl http://localhost:8000/api/health

# Check system resources
htop
iostat -x 1
```

**Solutions**:

1. **Enable Caching**:
   ```yaml
   cache:
     enabled: true
     level: 3
   ```

2. **Increase Workers**:
   ```yaml
   server:
     workers: 8  # Increase from 4
   ```

3. **Optimize Database Queries**:
   ```sql
   -- Add indexes
   CREATE INDEX idx_experts_domain ON experts(domain);
   ```

4. **Use Connection Pooling**:
   ```yaml
   database:
     pool_size: 20
     max_overflow: 10
   ```

---

### Issue: High CPU Usage

**Symptoms**:
- CPU usage consistently high
- System becomes slow

**Diagnosis**:
```bash
# Check CPU usage
top -p $(pgrep -f murphy_system_1.0_runtime)
```

**Solutions**:

1. **Profile Code**:
   ```python
   import cProfile
   
   cProfile.run('your_function()', sort='cumtime')
   ```

2. **Optimize Hot Paths**:
   - Identify slow functions
   - Optimize algorithms
   - Use caching

3. **Reduce Workers**:
   ```yaml
   server:
     workers: 4  # Reduce from 8
   ```

4. **Enable Rate Limiting**:
   ```yaml
   rate_limiting:
     enabled: true
     requests_per_minute: 1000
   ```

---

## Configuration Issues

### Issue: Configuration Not Loading

**Symptoms**:
- Default settings used instead of custom config
- Configuration changes not applied

**Diagnosis**:
```bash
# Check config file exists
ls -la config/config.yaml

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
```

**Solutions**:

1. **Verify Config File**:
   ```bash
   # Check file exists
   ls -l config/config.yaml

   # Check permissions
   chmod 644 config/config.yaml
   ```

2. **Validate YAML Syntax**:
   ```bash
   # Validate YAML
   python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
   ```

3. **Check Config Path**:
   ```bash
   # Specify config explicitly
   python murphy_system_1.0_runtime.py --config config/config.yaml
   ```

4. **Use Environment Variables**:
   ```bash
   export MURPHY_CONFIG=/path/to/config.yaml
   python murphy_system_1.0_runtime.py
   ```

---

### Issue: Invalid Configuration Values

**Symptoms**:
- Errors on startup
- Invalid value errors

**Diagnosis**:
```bash
# Check config file
cat config/config.yaml
```

**Solutions**:

1. **Validate Configuration**:
   ```yaml
   # Check values are valid
   server:
     port: 8000  # Must be 1-65535
     workers: 8  # Must be positive integer
   ```

2. **Check Data Types**:
   ```yaml
   # Ensure correct types
   cache:
     enabled: true  # boolean
     level: 3  # integer
     max_size: 1024  # integer
   ```

3. **Use Example Config**:
   ```bash
   # Start with example
   cp config/config.example.yaml config/config.yaml
   # Then modify
   ```

4. **Validate with Schema**:
   ```python
   from pydantic import BaseModel
   
   class Config(BaseModel):
       port: int
       workers: int
   
   config = Config(**config_data)
   ```

---

## Data Issues

### Issue: Database Connection Failed

**Symptoms**:
- Cannot connect to database
- Database errors

**Diagnosis**:
```bash
# Test database connection
psql -U murphy_user -d murphy_production -h localhost
```

**Solutions**:

1. **Check Database Status**:
   ```bash
   # PostgreSQL
   sudo systemctl status postgresql
   
   # Check if database exists
   sudo -u postgres psql -l
   ```

2. **Verify Credentials**:
   ```yaml
   # Check config
   database:
     host: localhost
     port: 5432
     database: murphy_production
     username: murphy_user
     password: ${MURPHY_DB_PASSWORD}
   ```

3. **Create Database**:
   ```sql
   CREATE DATABASE murphy_production;
   CREATE USER murphy_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE murphy_production TO murphy_user;
   ```

4. **Check Firewall**:
   ```bash
   # Check if port is open
   sudo ufw status
   sudo ufw allow 5432
   ```

---

### Issue: Cache Not Working

**Symptoms**:
- No performance improvement from cache
- Cache misses frequently

**Diagnosis**:
```bash
# Check cache metrics
curl http://localhost:8000/api/telemetry/metrics?type=cache
```

**Solutions**:

1. **Verify Cache Enabled**:
   ```yaml
   cache:
     enabled: true
     level: 3
   ```

2. **Check Cache Configuration**:
   ```yaml
   cache:
     ttl: 3600  # Check TTL
     max_size: 1024  # Check size
   ```

3. **Clear Cache**:
   ```python
   from src.cache import CacheManager
   
   manager = CacheManager()
   manager.clear()
   ```

4. **Monitor Cache Hit Rate**:
   ```bash
   # Check cache statistics
   curl http://localhost:8000/api/telemetry/metrics
   ```

---

## Network Issues

### Issue: Cannot Connect to Server

**Symptoms**:
- Connection refused errors
- Cannot reach API endpoints

**Diagnosis**:
```bash
# Check if server is running
ps aux | grep murphy_system_1.0_runtime

# Check if port is listening
netstat -tuln | grep 8000

# Test connectivity
telnet localhost 8000
```

**Solutions**:

1. **Start Server**:
   ```bash
   python murphy_system_1.0_runtime.py
   ```

2. **Check Firewall**:
   ```bash
   # Check firewall status
   sudo ufw status
   
   # Allow port
   sudo ufw allow 8000
   ```

3. **Check Network**:
   ```bash
   # Test connectivity
   ping localhost
   telnet localhost 8000
   ```

4. **Check Reverse Proxy**:
   ```bash
   # If using nginx
   sudo systemctl status nginx
   sudo nginx -t
   ```

---

### Issue: SSL/TLS Errors

**Symptoms**:
- SSL certificate errors
- HTTPS connection failures

**Diagnosis**:
```bash
# Test SSL
curl -v https://yourdomain.com/api/health
```

**Solutions**:

1. **Generate SSL Certificate**:
   ```bash
   # Self-signed
   openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365
   
   # Let's Encrypt
   certbot certonly --webroot -w /var/www/html -d yourdomain.com
   ```

2. **Configure SSL**:
   ```nginx
   server {
       listen 443 ssl http2;
       ssl_certificate /etc/ssl/certs/yourdomain.com.crt;
       ssl_certificate_key /etc/ssl/private/yourdomain.com.key;
       ssl_protocols TLSv1.2 TLSv1.3;
   }
   ```

3. **Check Certificate Expiry**:
   ```bash
   openssl x509 -enddate -noout -in /path/to/cert.pem
   ```

4. **Renew Certificate**:
   ```bash
   certbot renew
   ```

---

## Getting Help

### Before Asking for Help

1. **Check Documentation**:
   - Review user guides
   - Check API documentation
   - Read troubleshooting guide

2. **Gather Information**:
   ```bash
   # System information
   uname -a
   python --version
   pip --version

   # Server status
   systemctl status murphy-production
   ps aux | grep murphy_system_1.0_runtime

   # Logs
   tail -100 /var/log/murphy-production.log
   ```

3. **Reproduce Issue**:
   - Document steps to reproduce
   - Note expected vs actual behavior
   - Include error messages

### Contact Support

**Email**: corey.gfc@gmail.com

**Include**:
- System version
- Error messages
- Configuration (remove sensitive data)
- Steps to reproduce
- Logs (relevant sections)

### Community Resources

- Documentation: `/documentation`
- Examples: `/examples`
- Test Cases: `/tests`

---

## Debugging Tips

### Enable Debug Mode

```bash
# Run with debug logging
python murphy_system_1.0_runtime.py --log-level DEBUG
```

### Use Verbose Output

```bash
# Verbose curl
curl -v http://localhost:8000/api/health

# Verbose Python
python -v murphy_system_1.0_runtime.py
```

### Check Logs

```bash
# Follow logs
tail -f /var/log/murphy-production.log

# Search logs
grep "ERROR" /var/log/murphy-production.log
grep "WARN" /var/log/murphy-production.log
```

### Test Components

```bash
# Test system integrator
python -c "from src.system_integrator import SystemIntegrator; print('OK')"

# Test database
python -c "from src.database import Database; print('OK')"

# Test API
curl http://localhost:8000/api/health
```

---

## Ollama / Onboard LLM Troubleshooting

Murphy uses Ollama for local LLM inference when no external API key is set.
Use these steps when LLM responses are canned/generic or the health endpoint
reports `"ollama_running": false`.

### Check Ollama service

```bash
systemctl status ollama
# If inactive:
systemctl start ollama
```

### Check which models are pulled

```bash
ollama list
# Expected output (at minimum):
#   NAME          ID          SIZE   MODIFIED
#   llama3:latest ...         4.7 GB ...
```

### Pull a model if none are present

```bash
ollama pull llama3       # ~4.7 GB — default (requires 6 GB+ RAM)
ollama pull phi3         # ~2.3 GB — use on 2.5–6 GB systems
ollama pull tinyllama    # ~1 GB   — minimal (< 2.5 GB RAM)
```

### Verify Ollama responds directly

```bash
curl -s http://localhost:11434/api/tags | python3 -m json.tool
# Should show {"models": [...]}

# Quick generation test
curl -s http://localhost:11434/api/generate \
  -d '{"model":"llama3","prompt":"Say hi","stream":false}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('response',''))"
```

### Check Murphy's view of Ollama

```bash
curl -s 'http://localhost:8000/api/health?deep=true' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin).get('checks', {})
print('LLM:           ', d.get('llm'))
print('Ollama running:', d.get('ollama_running'))
print('Ollama models: ', d.get('ollama_models'))
print('Ollama host:   ', d.get('ollama_host'))
"

# Or via the LLM status endpoint
curl -s http://localhost:8000/api/llm/status | python3 -m json.tool
```

### Set OLLAMA_MODEL to a pulled model

If Ollama is running but Murphy still falls back to pattern-matching, make
sure the `OLLAMA_MODEL` env var matches an actually-pulled model name:

```bash
# Add to /etc/murphy-production/environment (or your .env)
OLLAMA_MODEL=llama3    # must match a name shown by `ollama list`

# Then restart Murphy
systemctl restart murphy-production
```

---
**© 2025 Corey Post InonI LLC. All rights reserved.**  
**Licensed under BSL 1.1 (converts to Apache 2.0 after 4 years)**  
**Contact: corey.gfc@gmail.com**
