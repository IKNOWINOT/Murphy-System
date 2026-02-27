# Murphy System Security Enhancement Plan
## Tailored to "Agents of Chaos" Research Findings

**Repository:** IKNOWINOT/Murphy-System  
**Version:** 1.0  
**Date:** February 27, 2026  
**Based on:** "Agents of Chaos" Research Paper (arXiv:2602.20021)

---

## Executive Summary

This security enhancement plan is specifically tailored to the Murphy System architecture, leveraging existing security components while addressing vulnerabilities identified in the "Agents of Chaos" research paper. The plan focuses on strengthening the system's robust multi-agent framework, comprehensive governance systems, and extensive bot ecosystem against the documented failure modes.

## Current Murphy System Security Assessment

### Existing Security Infrastructure ✅

**Security Plane Components:**
- `src/security_plane/` - Dedicated security layer
- `src/security_audit_scanner.py` - Automated security scanning
- `src/security_hardening_config.py` - Security configuration management
- `src/fastapi_security.py` - FastAPI security middleware
- `src/flask_security.py` - Flask security middleware
- `src/secure_key_manager.py` - Cryptographic key management
- `src/safety_gateway_integrator.py` - Safety validation integration
- `src/safety_validation_pipeline.py` - Multi-stage safety validation

**Governance Components:**
- `src/governance_framework/` - Governance policy framework
- `src/governance_kernel.py` - Core governance logic
- `src/governance_toggle.py` - Governance mode switching
- `src/bot_governance_policy_mapper.py` - Bot-specific governance policies
- `src/rbac_governance.py` - Role-based access control
- `src/automation_rbac_controller.py` - Automation RBAC

**Multi-Agent Systems:**
- `src/advanced_swarm_system.py` - Advanced swarm coordination
- `src/true_swarm_system.py` - True swarm intelligence
- `src/domain_swarms.py` - Domain-specific swarms
- `src/durable_swarm_orchestrator.py` - Persistent swarm orchestration
- `src/swarm_proposal_generator.py` - Swarm decision proposals

**Agent Hooks Infrastructure:**
- `.agent_hooks/startup/` - Startup hooks for initialization
- `.agent_hooks/shutdown/00_track_processes_on_ports.py` - Process tracking
- Supervisor-based process management
- Automated lifecycle management

### Identified Gaps ❌

1. **Non-Owner Authorization** - No explicit verification of request ownership
2. **Sensitive Data Sanitization** - Logs may contain PII without redaction
3. **Resource Quotas** - No explicit limits on bot/swarm resource consumption
4. **Communication Loop Detection** - Swarm systems vulnerable to circular conversations
5. **Identity Verification** - Bot identities not cryptographically verified
6. **Anomaly Detection** - Limited automated detection of unusual bot behavior

---

## Phase 1: Critical Security Controls (Week 1-2)
**Priority: HIGH | Effort: LOW | Impact: HIGH**

### 1.1 Enhanced Authorization Framework
**Objective:** Prevent non-owner compliance (Case Study #2)

**Implementation:** Extend existing `src/rbac_governance.py`

```python
# File: src/security_plane/authorization_enhancer.py
"""
Enhanced authorization framework for Murphy System
Addresses "Agents of Chaos" Case Study #2: Non-Owner Compliance
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

@dataclass
class BotIdentity:
    bot_id: str
    owner_id: str
    public_key: str
    permissions: Set[str]
    created_at: datetime
    last_active: datetime

@dataclass
class AuthorizationRequest:
    requester_id: str
    bot_id: str
    action: str
    parameters: Dict
    timestamp: datetime
    session_id: str

class MurphyAuthorizationEnhancer:
    """
    Enhanced authorization system for Murphy System bots and swarms
    Integrates with existing RBAC governance
    """
    
    def __init__(self, config_path: Path = Path("config/security/authorization.json")):
        self.config_path = config_path
        self.bot_identities: Dict[str, BotIdentity] = {}
        self.session_contexts: Dict[str, Dict] = {}
        self.authorization_log: List[Dict] = []
        self.load_configuration()
    
    def load_configuration(self):
        """Load authorization configuration"""
        if self.config_path.exists():
            with open(self.config_path) as f:
                config = json.load(f)
                for bot_data in config.get("bots", []):
                    self.bot_identities[bot_data["bot_id"]] = BotIdentity(
                        bot_id=bot_data["bot_id"],
                        owner_id=bot_data["owner_id"],
                        public_key=bot_data["public_key"],
                        permissions=set(bot_data["permissions"]),
                        created_at=datetime.fromisoformat(bot_data["created_at"]),
                        last_active=datetime.fromisoformat(bot_data["last_active"])
                    )
    
    def verify_request(self, request: AuthorizationRequest) -> tuple[bool, str]:
        """
        Verify if a request is authorized
        
        Returns:
            (authorized, reason)
        """
        # Check if bot exists
        if request.bot_id not in self.bot_identities:
            return False, f"Unknown bot ID: {request.bot_id}"
        
        bot_identity = self.bot_identities[request.bot_id]
        
        # Check if requester is the owner
        if request.requester_id != bot_identity.owner_id:
            # Non-owner request - check for explicit permission
            non_owner_permission = f"non_owner:{request.action}"
            if non_owner_permission not in bot_identity.permissions:
                self.log_authorization(request, False, "Non-owner without explicit permission")
                return False, f"Non-owner request not permitted for action: {request.action}"
        
        # Check if action is permitted
        if request.action not in bot_identity.permissions and "all" not in bot_identity.permissions:
            self.log_authorization(request, False, "Action not in permitted set")
            return False, f"Action not permitted: {request.action}"
        
        # Check session context
        if not self.verify_session_context(request):
            self.log_authorization(request, False, "Invalid session context")
            return False, "Invalid session context"
        
        # Update last active
        bot_identity.last_active = datetime.now()
        
        self.log_authorization(request, True, "Authorized")
        return True, "Authorized"
    
    def verify_session_context(self, request: AuthorizationRequest) -> bool:
        """Verify session context for request"""
        if request.session_id not in self.session_contexts:
            return False
        
        session = self.session_contexts[request.session_id]
        
        # Check session expiration
        if datetime.now() - session["created_at"] > timedelta(hours=24):
            del self.session_contexts[request.session_id]
            return False
        
        # Check if requester is in session
        if request.requester_id not in session["participants"]:
            return False
        
        return True
    
    def log_authorization(self, request: AuthorizationRequest, authorized: bool, reason: str):
        """Log authorization decision for audit trail"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "requester_id": request.requester_id,
            "bot_id": request.bot_id,
            "action": request.action,
            "authorized": authorized,
            "reason": reason,
            "session_id": request.session_id
        }
        self.authorization_log.append(log_entry)
        
        # Write to log file
        log_path = Path("logs/security/authorization.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def create_session(self, owner_id: str, participants: List[str]) -> str:
        """Create a new authorization session"""
        session_id = hashlib.sha256(f"{owner_id}{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        self.session_contexts[session_id] = {
            "owner_id": owner_id,
            "participants": set(participants),
            "created_at": datetime.now()
        }
        return session_id
    
    def get_authorization_report(self, hours: int = 24) -> Dict:
        """Generate authorization report"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_logs = [
            log for log in self.authorization_log
            if datetime.fromisoformat(log["timestamp"]) > cutoff
        ]
        
        return {
            "total_requests": len(recent_logs),
            "authorized": sum(1 for log in recent_logs if log["authorized"]),
            "denied": sum(1 for log in recent_logs if not log["authorized"]),
            "unique_bots": len(set(log["bot_id"] for log in recent_logs)),
            "unique_requesters": len(set(log["requester_id"] for log in recent_logs)),
            "denial_reasons": self._count_denial_reasons(recent_logs)
        }
    
    def _count_denial_reasons(self, logs: List[Dict]) -> Dict[str, int]:
        """Count denial reasons"""
        reasons = {}
        for log in logs:
            if not log["authorized"]:
                reason = log["reason"]
                reasons[reason] = reasons.get(reason, 0) + 1
        return reasons
```

**Integration Point:** Add to `src/security_plane/__init__.py` and integrate with existing `src/rbac_governance.py`

**Configuration File:**
```json
// config/security/authorization.json
{
  "bots": [
    {
      "bot_id": "murphy_bot_001",
      "owner_id": "user_123",
      "public_key": "ssh-rsa AAAAB3NzaC1yc2E...",
      "permissions": [
        "execute_task",
        "read_data",
        "write_data",
        "call_api",
        "swarm_coordinate"
      ],
      "created_at": "2026-02-27T00:00:00",
      "last_active": "2026-02-27T00:00:00"
    }
  ],
  "default_permissions": [
    "read_data",
    "execute_task"
  ],
  "blocked_actions": [
    "delete_system_files",
    "modify_governance",
    "access_other_bots",
    "bypass_safety_gates"
  ],
  "session_timeout_hours": 24
}
```

### 1.2 Sensitive Data Sanitization for Logs
**Objective:** Prevent PII disclosure (Case Study #3)

**Implementation:** Extend existing `src/logging_system.py`

```python
# File: src/security_plane/log_sanitizer.py
"""
Sensitive data sanitization for Murphy System logs
Addresses "Agents of Chaos" Case Study #3: Sensitive Information Disclosure
"""

import re
import hashlib
from typing import Pattern, Dict, Optional
from pathlib import Path

class MurphyLogSanitizer:
    """
    Sanitizes sensitive data from Murphy System logs
    Integrates with existing logging_system.py
    """
    
    # Patterns for sensitive data
    PATTERNS: Dict[str, Pattern] = {
        "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "credit_card": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
        "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        "ip_address": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
        "api_key": re.compile(r'\b[A-Za-z0-9]{32,}\b'),
        "password": re.compile(r'(?i)(password|passwd|pwd|secret)[\s=:]+[^\s]+'),
        "token": re.compile(r'(?i)(token|auth|bearer|jwt)[\s=:]+[^\s]+'),
        "bot_id": re.compile(r'\bbot_[a-zA-Z0-9_]+\b'),
        "session_id": re.compile(r'\bsession_[a-zA-Z0-9_]+\b'),
        "user_id": re.compile(r'\buser_[a-zA-Z0-9_]+\b')
    }
    
    def __init__(self, redaction_string: str = "[REDACTED]", hash_sensitive: bool = True):
        self.redaction_string = redaction_string
        self.hash_sensitive = hash_sensitive
        self.hash_cache: Dict[str, str] = {}
    
    def sanitize(self, text: str) -> str:
        """Remove or redact sensitive information from text"""
        sanitized = text
        
        for pattern_name, pattern in self.PATTERNS.items():
            # For certain patterns, we might want to hash instead of redact
            if pattern_name in ["email", "bot_id", "session_id", "user_id"] and self.hash_sensitive:
                sanitized = pattern.sub(lambda m: self._hash_match(m.group()), sanitized)
            else:
                sanitized = pattern.sub(self.redaction_string, sanitized)
        
        return sanitized
    
    def _hash_match(self, match: str) -> str:
        """Hash sensitive data for traceability without exposure"""
        if match not in self.hash_cache:
            self.hash_cache[match] = hashlib.sha256(match.encode()).hexdigest()[:8]
        return f"[HASH:{self.hash_cache[match]}]"
    
    def sanitize_log_file(self, log_path: Path):
        """Sanitize an existing log file in place"""
        with open(log_path, 'r') as f:
            content = f.read()
        
        sanitized_content = self.sanitize(content)
        
        with open(log_path, 'w') as f:
            f.write(sanitized_content)
    
    def sanitize_murphy_logs(self, log_dir: Path = Path("logs")):
        """Sanitize all Murphy System logs"""
        if not log_dir.exists():
            return
        
        for log_file in log_dir.rglob("*.log"):
            try:
                self.sanitize_log_file(log_file)
            except Exception as e:
                print(f"Failed to sanitize {log_file}: {e}")
```

**Integration Point:** Add to `src/logging_system.py` as a pre-processing step before writing logs

### 1.3 Resource Quotas for Bots and Swarms
**Objective:** Prevent DoS through resource exhaustion (Case Study #5)

**Implementation:** Extend existing `src/tenant_resource_governor.py`

```python
# File: src/security_plane/bot_resource_quotas.py
"""
Resource quota management for Murphy System bots and swarms
Addresses "Agents of Chaos" Case Study #5: Denial of Service
"""

import psutil
import time
from dataclasses import dataclass
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import json
from pathlib import Path

@dataclass
class ResourceQuota:
    max_memory_mb: int = 2048
    max_cpu_percent: float = 80.0
    max_disk_mb: int = 10240
    max_network_mbps: float = 100.0
    max_processes: int = 50
    max_execution_time_seconds: int = 3600

@dataclass
class ResourceUsage:
    memory_mb: float
    cpu_percent: float
    disk_mb: float
    network_mbps: float
    process_count: int
    execution_time_seconds: float

class BotResourceQuotaManager:
    """
    Manages resource quotas for Murphy System bots and swarms
    Integrates with existing tenant_resource_governor.py
    """
    
    def __init__(self, config_path: Path = Path("config/security/resource_quotas.json")):
        self.config_path = config_path
        self.bot_quotas: Dict[str, ResourceQuota] = {}
        self.swarm_quotas: Dict[str, ResourceQuota] = {}
        self.bot_usage: Dict[str, ResourceUsage] = {}
        self.swarm_usage: Dict[str, ResourceUsage] = {}
        self.violation_log: List[Dict] = []
        self.load_configuration()
    
    def load_configuration(self):
        """Load resource quota configuration"""
        if self.config_path.exists():
            with open(self.config_path) as f:
                config = json.load(f)
                
                for bot_id, quota_data in config.get("bot_quotas", {}).items():
                    self.bot_quotas[bot_id] = ResourceQuota(**quota_data)
                
                for swarm_id, quota_data in config.get("swarm_quotas", {}).items():
                    self.swarm_quotas[swarm_id] = ResourceQuota(**quota_data)
    
    def get_bot_quota(self, bot_id: str) -> ResourceQuota:
        """Get resource quota for a bot"""
        return self.bot_quotas.get(bot_id, ResourceQuota())
    
    def get_swarm_quota(self, swarm_id: str) -> ResourceQuota:
        """Get resource quota for a swarm"""
        return self.swarm_quotas.get(swarm_id, ResourceQuota())
    
    def check_bot_limits(self, bot_id: str, pid: int) -> Dict[str, bool]:
        """Check if bot is within resource limits"""
        quota = self.get_bot_quota(bot_id)
        usage = self._get_process_usage(pid)
        
        violations = {
            "memory": usage.memory_mb > quota.max_memory_mb,
            "cpu": usage.cpu_percent > quota.max_cpu_percent,
            "disk": usage.disk_mb > quota.max_disk_mb,
            "network": usage.network_mbps > quota.max_network_mbps,
            "processes": usage.process_count > quota.max_processes,
            "execution_time": usage.execution_time_seconds > quota.max_execution_time_seconds
        }
        
        if any(violations.values()):
            self._log_violation(bot_id, "bot", usage, quota, violations)
        
        return violations
    
    def check_swarm_limits(self, swarm_id: str, bot_pids: List[int]) -> Dict[str, bool]:
        """Check if swarm is within resource limits"""
        quota = self.get_swarm_quota(swarm_id)
        total_usage = self._get_aggregated_usage(bot_pids)
        
        violations = {
            "memory": total_usage.memory_mb > quota.max_memory_mb,
            "cpu": total_usage.cpu_percent > quota.max_cpu_percent,
            "disk": total_usage.disk_mb > quota.max_disk_mb,
            "network": total_usage.network_mbps > quota.max_network_mbps,
            "processes": total_usage.process_count > quota.max_processes
        }
        
        if any(violations.values()):
            self._log_violation(swarm_id, "swarm", total_usage, quota, violations)
        
        return violations
    
    def enforce_bot_limits(self, bot_id: str, pid: int) -> bool:
        """
        Enforce resource limits on a bot
        Returns True if bot should be terminated
        """
        violations = self.check_bot_limits(bot_id, pid)
        
        # Check for critical violations requiring termination
        quota = self.get_bot_quota(bot_id)
        usage = self._get_process_usage(pid)
        
        if violations["memory"] and usage.memory_mb > quota.max_memory_mb * 1.5:
            self._terminate_process(pid, f"Critical memory violation for bot {bot_id}")
            return True
        
        if violations["processes"] and usage.process_count > quota.max_processes * 2:
            self._terminate_process(pid, f"Critical process count violation for bot {bot_id}")
            return True
        
        return False
    
    def enforce_swarm_limits(self, swarm_id: str, bot_pids: List[int]) -> bool:
        """
        Enforce resource limits on a swarm
        Returns True if swarm should be terminated
        """
        violations = self.check_swarm_limits(swarm_id, bot_pids)
        
        quota = self.get_swarm_quota(swarm_id)
        total_usage = self._get_aggregated_usage(bot_pids)
        
        if violations["memory"] and total_usage.memory_mb > quota.max_memory_mb * 1.5:
            for pid in bot_pids:
                self._terminate_process(pid, f"Critical memory violation for swarm {swarm_id}")
            return True
        
        return False
    
    def _get_process_usage(self, pid: int) -> ResourceUsage:
        """Get resource usage for a process"""
        try:
            process = psutil.Process(pid)
            
            return ResourceUsage(
                memory_mb=process.memory_info().rss / 1024 / 1024,
                cpu_percent=process.cpu_percent(),
                disk_mb=self._get_disk_usage(),
                network_mbps=self._get_network_usage(),
                process_count=len(process.children(recursive=True)) + 1,
                execution_time_seconds=(datetime.now() - datetime.fromtimestamp(process.create_time())).total_seconds()
            )
        except psutil.NoSuchProcess:
            return ResourceUsage(0, 0, 0, 0, 0, 0)
    
    def _get_aggregated_usage(self, pids: List[int]) -> ResourceUsage:
        """Get aggregated resource usage for multiple processes"""
        total_memory = 0
        total_cpu = 0
        total_processes = 0
        
        for pid in pids:
            usage = self._get_process_usage(pid)
            total_memory += usage.memory_mb
            total_cpu += usage.cpu_percent
            total_processes += usage.process_count
        
        return ResourceUsage(
            memory_mb=total_memory,
            cpu_percent=total_cpu,
            disk_mb=self._get_disk_usage(),
            network_mbps=self._get_network_usage(),
            process_count=total_processes,
            execution_time_seconds=0
        )
    
    def _get_disk_usage(self) -> float:
        """Get disk usage in MB"""
        disk = psutil.disk_usage('/workspace')
        return disk.used / 1024 / 1024
    
    def _get_network_usage(self) -> float:
        """Get network usage in Mbps"""
        net = psutil.net_io_counters()
        return (net.bytes_sent + net.bytes_recv) / 1024 / 1024
    
    def _terminate_process(self, pid: int, reason: str):
        """Terminate a process"""
        try:
            process = psutil.Process(pid)
            process.terminate()
            print(f"Terminated process {pid}: {reason}")
        except psutil.NoSuchProcess:
            pass
    
    def _log_violation(self, entity_id: str, entity_type: str, usage: ResourceUsage, 
                      quota: ResourceQuota, violations: Dict[str, bool]):
        """Log resource violation"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "entity_id": entity_id,
            "entity_type": entity_type,
            "usage": {
                "memory_mb": usage.memory_mb,
                "cpu_percent": usage.cpu_percent,
                "disk_mb": usage.disk_mb,
                "network_mbps": usage.network_mbps,
                "process_count": usage.process_count
            },
            "quota": {
                "max_memory_mb": quota.max_memory_mb,
                "max_cpu_percent": quota.max_cpu_percent,
                "max_disk_mb": quota.max_disk_mb,
                "max_network_mbps": quota.max_network_mbps,
                "max_processes": quota.max_processes
            },
            "violations": violations
        }
        
        self.violation_log.append(log_entry)
        
        # Write to log file
        log_path = Path("logs/security/resource_violations.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def get_quota_report(self, hours: int = 24) -> Dict:
        """Generate quota violation report"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_violations = [
            v for v in self.violation_log
            if datetime.fromisoformat(v["timestamp"]) > cutoff
        ]
        
        return {
            "total_violations": len(recent_violations),
            "bot_violations": sum(1 for v in recent_violations if v["entity_type"] == "bot"),
            "swarm_violations": sum(1 for v in recent_violations if v["entity_type"] == "swarm"),
            "violation_types": self._count_violation_types(recent_violations),
            "affected_entities": len(set(v["entity_id"] for v in recent_violations))
        }
    
    def _count_violation_types(self, violations: List[Dict]) -> Dict[str, int]:
        """Count violation types"""
        types = {}
        for v in violations:
            for violation_type, occurred in v["violations"].items():
                if occurred:
                    types[violation_type] = types.get(violation_type, 0) + 1
        return types
```

**Integration Point:** Add to `src/tenant_resource_governor.py` and integrate with existing resource management

**Configuration File:**
```json
// config/security/resource_quotas.json
{
  "bot_quotas": {
    "murphy_bot_001": {
      "max_memory_mb": 2048,
      "max_cpu_percent": 80.0,
      "max_disk_mb": 10240,
      "max_network_mbps": 100.0,
      "max_processes": 50,
      "max_execution_time_seconds": 3600
    }
  },
  "swarm_quotas": {
    "default_swarm": {
      "max_memory_mb": 8192,
      "max_cpu_percent": 90.0,
      "max_disk_mb": 40960,
      "max_network_mbps": 500.0,
      "max_processes": 200,
      "max_execution_time_seconds": 7200
    }
  },
  "default_bot_quota": {
    "max_memory_mb": 1024,
    "max_cpu_percent": 70.0,
    "max_disk_mb": 5120,
    "max_network_mbps": 50.0,
    "max_processes": 25,
    "max_execution_time_seconds": 1800
  }
}
```

---

## Phase 2: Swarm Security Enhancements (Week 3-4)
**Priority: HIGH | Effort: MEDIUM | Impact: HIGH**

### 2.1 Communication Loop Detection for Swarms
**Objective:** Prevent circular conversations (Case Study #4)

**Implementation:** Extend existing `src/advanced_swarm_system.py`

```python
# File: src/security_plane/swarm_communication_monitor.py
"""
Communication monitoring for Murphy System swarms
Addresses "Agents of Chaos" Case Study #4: Resource Consumption (Looping)
"""

from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
import json
from pathlib import Path

@dataclass
class SwarmMessage:
    timestamp: datetime
    from_bot: str
    to_bot: str
    message_id: str
    content_hash: str
    swarm_id: str

class SwarmCommunicationMonitor:
    """
    Monitors and regulates inter-bot communication within swarms
    Integrates with existing advanced_swarm_system.py and true_swarm_system.py
    """
    
    def __init__(self, max_message_rate: int = 10, 
                 loop_detection_window: int = 20,
                 config_path: Path = Path("config/security/swarm_communication.json")):
        self.max_message_rate = max_message_rate
        self.loop_detection_window = loop_detection_window
        self.config_path = config_path
        self.message_history: List[SwarmMessage] = []
        self.bot_pairs: Dict[Tuple[str, str], List[datetime]] = defaultdict(list)
        self.swarm_contexts: Dict[str, Dict] = {}
        self.alert_log: List[Dict] = []
        self.load_configuration()
    
    def load_configuration(self):
        """Load swarm communication configuration"""
        if self.config_path.exists():
            with open(self.config_path) as f:
                config = json.load(f)
                self.max_message_rate = config.get("max_message_rate", 10)
                self.loop_detection_window = config.get("loop_detection_window", 20)
    
    def log_message(self, from_bot: str, to_bot: str, swarm_id: str, 
                   message_id: str, content: str):
        """Log a message between bots in a swarm"""
        message = SwarmMessage(
            timestamp=datetime.now(),
            from_bot=from_bot,
            to_bot=to_bot,
            message_id=message_id,
            content_hash=self._hash_content(content),
            swarm_id=swarm_id
        )
        
        self.message_history.append(message)
        self.bot_pairs[(from_bot, to_bot)].append(message.timestamp)
        
        # Clean old messages
        self._cleanup_old_messages()
    
    def check_communication_allowed(self, from_bot: str, to_bot: str, 
                                   swarm_id: str) -> Tuple[bool, str]:
        """
        Check if communication is allowed between bots
        Returns (allowed, reason)
        """
        # Check message rate
        recent_messages = [
            ts for ts in self.bot_pairs[(from_bot, to_bot)]
            if datetime.now() - ts < timedelta(minutes=1)
        ]
        
        if len(recent_messages) >= self.max_message_rate:
            return False, f"Rate limit exceeded: {len(recent_messages)} messages in last minute"
        
        # Check for communication loops
        if self._detect_communication_loop(from_bot, to_bot, swarm_id):
            return False, "Potential communication loop detected"
        
        # Check for unusual patterns
        if self._detect_unusual_pattern(from_bot, to_bot):
            self._log_alert("unusual_pattern", from_bot, to_bot, swarm_id, "Unusual communication pattern detected")
        
        return True, "Communication allowed"
    
    def _detect_communication_loop(self, from_bot: str, to_bot: str, 
                                   swarm_id: str) -> bool:
        """Detect circular communication patterns"""
        recent_messages = [
            m for m in self.message_history
            if m.swarm_id == swarm_id and datetime.now() - m.timestamp < timedelta(minutes=5)
        ]
        
        # Build communication graph
        graph: Dict[str, Set[str]] = defaultdict(set)
        for msg in recent_messages:
            graph[msg.from_bot].add(msg.to_bot)
        
        # Check for cycles using DFS
        visited = set()
        path = set()
        
        def has_cycle(node: str) -> bool:
            if node in path:
                return True
            if node in visited:
                return False
            
            visited.add(node)
            path.add(node)
            
            for neighbor in graph.get(node, set()):
                if has_cycle(neighbor):
                    return True
            
            path.remove(node)
            return False
        
        return has_cycle(from_bot)
    
    def _detect_unusual_pattern(self, from_bot: str, to_bot: str) -> bool:
        """Detect unusual communication patterns"""
        pair_messages = self.bot_pairs[(from_bot, to_bot)]
        
        if len(pair_messages) < 10:
            return False
        
        # Check for regular intervals (potential automated loop)
        intervals = []
        for i in range(1, len(pair_messages)):
            interval = (pair_messages[i] - pair_messages[i-1]).total_seconds()
            intervals.append(interval)
        
        # Calculate coefficient of variation
        if intervals:
            mean_interval = sum(intervals) / len(intervals)
            std_interval = (sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)) ** 0.5
            
            if mean_interval > 0:
                cv = std_interval / mean_interval
                # Low coefficient of variation suggests regular pattern
                return cv < 0.2
        
        return False
    
    def _hash_content(self, content: str) -> str:
        """Hash message content for deduplication"""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _cleanup_old_messages(self):
        """Remove messages older than 1 hour"""
        cutoff = datetime.now() - timedelta(hours=1)
        self.message_history = [
            m for m in self.message_history
            if m.timestamp > cutoff
        ]
        
        # Clean bot pairs
        for pair in self.bot_pairs:
            self.bot_pairs[pair] = [
                ts for ts in self.bot_pairs[pair]
                if ts > cutoff
            ]
    
    def _log_alert(self, alert_type: str, from_bot: str, to_bot: str, 
                  swarm_id: str, message: str):
        """Log security alert"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "alert_type": alert_type,
            "from_bot": from_bot,
            "to_bot": to_bot,
            "swarm_id": swarm_id,
            "message": message
        }
        self.alert_log.append(alert)
        
        # Write to alert log
        log_path = Path("logs/security/swarm_alerts.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(alert) + "\n")
    
    def get_communication_report(self, swarm_id: Optional[str] = None) -> Dict:
        """Generate communication report"""
        cutoff = datetime.now() - timedelta(minutes=10)
        
        if swarm_id:
            recent_messages = [
                m for m in self.message_history
                if m.swarm_id == swarm_id and m.timestamp > cutoff
            ]
        else:
            recent_messages = [
                m for m in self.message_history
                if m.timestamp > cutoff
            ]
        
        # Count messages per bot
        bot_message_counts = defaultdict(int)
        for msg in recent_messages:
            bot_message_counts[msg.from_bot] += 1
        
        return {
            "timestamp": datetime.now().isoformat(),
            "swarm_id": swarm_id,
            "total_recent_messages": len(recent_messages),
            "active_bots": len(bot_message_counts),
            "message_counts": dict(bot_message_counts),
            "potential_loops": self._detect_all_loops(swarm_id),
            "recent_alerts": len([a for a in self.alert_log if datetime.fromisoformat(a["timestamp"]) > cutoff])
        }
    
    def _detect_all_loops(self, swarm_id: Optional[str] = None) -> List[List[str]]:
        """Detect all communication loops"""
        recent_messages = [
            m for m in self.message_history
            if (swarm_id is None or m.swarm_id == swarm_id) and datetime.now() - m.timestamp < timedelta(minutes=5)
        ]
        
        graph: Dict[str, Set[str]] = defaultdict(set)
        for msg in recent_messages:
            graph[msg.from_bot].add(msg.to_bot)
        
        loops = []
        visited = set()
        
        def find_cycles(node: str, path: List[str]) -> List[List[str]]:
            cycles = []
            
            if node in path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return cycles
            
            if node in visited:
                return cycles
            
            visited.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, set()):
                cycles.extend(find_cycles(neighbor, path))
            
            path.pop()
            return cycles
        
        for bot in graph:
            if bot not in visited:
                loops.extend(find_cycles(bot, []))
        
        return loops
```

**Integration Point:** Add to `src/advanced_swarm_system.py` and `src/true_swarm_system.py`

**Configuration File:**
```json
// config/security/swarm_communication.json
{
  "max_message_rate": 10,
  "loop_detection_window": 20,
  "alert_thresholds": {
    "unusual_pattern_cv": 0.2,
    "loop_detection_minutes": 5,
    "message_history_hours": 1
  },
  "blocked_patterns": [
    "self_referential_loop",
    "circular_dependency",
    "infinite_coordination"
  ]
}
```

### 2.2 Bot Identity Verification
**Objective:** Prevent identity spoofing (Case Study #8)

**Implementation:** Extend existing `src/secure_key_manager.py`

```python
# File: src/security_plane/bot_identity_verifier.py
"""
Cryptographic identity verification for Murphy System bots
Addresses "Agents of Chaos" Case Study #8: Identity Spoofing
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from datetime import datetime
import logging

class BotIdentityVerifier:
    """
    Manages cryptographic identities for Murphy System bots
    Integrates with existing secure_key_manager.py
    """
    
    def __init__(self, keys_dir: Path = Path("config/security/bot_keys")):
        self.keys_dir = keys_dir
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.bot_identities: Dict[str, Dict] = {}
        self.load_identities()
    
    def generate_bot_identity(self, bot_id: str, owner_id: str) -> Dict[str, str]:
        """Generate a new cryptographic identity for a bot"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        public_key = private_key.public_key()
        
        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Save keys
        private_key_path = self.keys_dir / f"{bot_id}_private.pem"
        public_key_path = self.keys_dir / f"{bot_id}_public.pem"
        
        with open(private_key_path, 'wb') as f:
            f.write(private_pem)
        
        with open(public_key_path, 'wb') as f:
            f.write(public_pem)
        
        # Create identity record
        identity = {
            "bot_id": bot_id,
            "owner_id": owner_id,
            "public_key": public_pem.decode('utf-8'),
            "key_fingerprint": self._generate_fingerprint(public_pem),
            "created_at": datetime.now().isoformat(),
            "status": "active"
        }
        
        self.bot_identities[bot_id] = identity
        self.save_identities()
        
        return identity
    
    def verify_bot_signature(self, bot_id: str, message: str, 
                            signature: str) -> bool:
        """Verify a message signature from a bot"""
        if bot_id not in self.bot_identities:
            self.logger.error(f"Unknown bot ID: {bot_id}")
            return False
        
        try:
            public_key_pem = self.bot_identities[bot_id]["public_key"]
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode('utf-8'),
                backend=default_backend()
            )
            
            public_key.verify(
                signature.encode('utf-8'),
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Signature verification failed: {e}")
            return False
    
    def sign_message(self, bot_id: str, message: str) -> Optional[str]:
        """Sign a message with a bot's private key"""
        private_key_path = self.keys_dir / f"{bot_id}_private.pem"
        
        if not private_key_path.exists():
            self.logger.error(f"Private key not found for bot: {bot_id}")
            return None
        
        try:
            with open(private_key_path, 'rb') as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
            
            signature = private_key.sign(
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return signature.decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Message signing failed: {e}")
            return None
    
    def _generate_fingerprint(self, public_key_pem: bytes) -> str:
        """Generate a fingerprint for a public key"""
        return hashlib.sha256(public_key_pem).hexdigest()[:16]
    
    def load_identities(self):
        """Load bot identities from storage"""
        identities_path = self.keys_dir / "bot_identities.json"
        if identities_path.exists():
            with open(identities_path) as f:
                self.bot_identities = json.load(f)
    
    def save_identities(self):
        """Save bot identities to storage"""
        identities_path = self.keys_dir / "bot_identities.json"
        with open(identities_path, 'w') as f:
            json.dump(self.bot_identities, f, indent=2)
    
    def revoke_bot_identity(self, bot_id: str):
        """Revoke a bot's identity"""
        if bot_id in self.bot_identities:
            self.bot_identities[bot_id]["status"] = "revoked"
            self.save_identities()
    
    def get_bot_identity(self, bot_id: str) -> Optional[Dict]:
        """Get bot identity information"""
        return self.bot_identities.get(bot_id)
```

**Integration Point:** Add to `src/secure_key_manager.py` and integrate with bot initialization

---

## Phase 3: Anomaly Detection (Week 5-6)
**Priority: MEDIUM | Effort: MEDIUM | Impact: HIGH**

### 3.1 Bot Behavior Anomaly Detection
**Objective:** Detect unusual bot behavior (Case Study #4)

**Implementation:** Extend existing `src/security_audit_scanner.py`

```python
# File: src/security_plane/bot_anomaly_detector.py
"""
Anomaly detection for Murphy System bots
Addresses "Agents of Chaos" Case Study #4: Unusual Behavior Patterns
"""

import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
import logging

@dataclass
class BotMetricSnapshot:
    timestamp: datetime
    bot_id: str
    cpu_percent: float
    memory_mb: float
    disk_io_mb: float
    network_io_mb: float
    process_count: int
    api_calls: int
    messages_sent: int
    messages_received: int

class BotAnomalyDetector:
    """
    Detects anomalous behavior in Murphy System bots
    Integrates with existing security_audit_scanner.py
    """
    
    def __init__(self, window_size: int = 100, threshold_std: float = 3.0,
                 config_path: Path = Path("config/security/anomaly_detection.json")):
        self.window_size = window_size
        self.threshold_std = threshold_std
        self.config_path = config_path
        self.metrics_history: Dict[str, List[BotMetricSnapshot]] = {}
        self.anomaly_log: List[Dict] = []
        self.logger = logging.getLogger(__name__)
        self.load_configuration()
    
    def load_configuration(self):
        """Load anomaly detection configuration"""
        if self.config_path.exists():
            with open(self.config_path) as f:
                config = json.load(f)
                self.window_size = config.get("window_size", 100)
                self.threshold_std = config.get("threshold_std", 3.0)
    
    def add_metric(self, metric: BotMetricSnapshot):
        """Add a new metric snapshot"""
        if metric.bot_id not in self.metrics_history:
            self.metrics_history[metric.bot_id] = []
        
        self.metrics_history[metric.bot_id].append(metric)
        
        # Keep only recent metrics
        if len(self.metrics_history[metric.bot_id]) > self.window_size:
            self.metrics_history[metric.bot_id].pop(0)
    
    def detect_anomalies(self, bot_id: str) -> Dict[str, bool]:
        """
        Detect if current metrics are anomalous
        Returns dictionary of anomaly flags
        """
        if bot_id not in self.metrics_history:
            return {"insufficient_data": True}
        
        history = self.metrics_history[bot_id]
        
        if len(history) < 10:
            return {"insufficient_data": True}
        
        current_metric = history[-1]
        anomalies = {}
        
        # Check each metric for anomalies
        metrics_to_check = [
            ("cpu", lambda m: m.cpu_percent),
            ("memory", lambda m: m.memory_mb),
            ("disk_io", lambda m: m.disk_io_mb),
            ("network_io", lambda m: m.network_io_mb),
            ("process_count", lambda m: m.process_count),
            ("api_calls", lambda m: m.api_calls),
            ("messages_sent", lambda m: m.messages_sent),
            ("messages_received", lambda m: m.messages_received)
        ]
        
        for metric_name, metric_extractor in metrics_to_check:
            values = [metric_extractor(m) for m in history]
            current_value = metric_extractor(current_metric)
            
            # Calculate z-score
            mean = np.mean(values)
            std = np.std(values)
            
            if std > 0:
                z_score = abs(current_value - mean) / std
                anomalies[metric_name] = z_score > self.threshold_std
            else:
                anomalies[metric_name] = False
        
        # Detect communication loops
        anomalies["communication_loop"] = self._detect_communication_loop(bot_id)
        
        # Detect resource spikes
        anomalies["resource_spike"] = self._detect_resource_spike(current_metric)
        
        # Detect unusual API patterns
        anomalies["unusual_api_pattern"] = self._detect_unusual_api_pattern(bot_id)
        
        return anomalies
    
    def _detect_communication_loop(self, bot_id: str) -> bool:
        """Detect circular communication patterns"""
        history = self.metrics_history.get(bot_id, [])
        
        if len(history) < 20:
            return False
        
        recent_metrics = history[-20:]
        
        # Check for repetitive patterns in message counts
        sent_values = [m.messages_sent for m in recent_metrics]
        received_values = [m.messages_received for m in recent_metrics]
        
        # Calculate autocorrelation
        if len(sent_values) >= 10:
            sent_autocorr = np.correlate(sent_values, sent_values, mode='full')
            max_sent_corr = np.max(sent_autocorr[len(sent_autocorr)//2+1:])
            
            if max_sent_corr > 0.8:
                return True
        
        return False
    
    def _detect_resource_spike(self, current_metric: BotMetricSnapshot) -> bool:
        """Detect sudden resource consumption spikes"""
        history = self.metrics_history.get(current_metric.bot_id, [])
        
        if len(history) < 5:
            return False
        
        recent_metrics = history[-5:]
        
        # Check if current metric is significantly higher than recent average
        avg_memory = np.mean([m.memory_mb for m in recent_metrics])
        avg_cpu = np.mean([m.cpu_percent for m in recent_metrics])
        
        memory_spike = current_metric.memory_mb > avg_memory * 3
        cpu_spike = current_metric.cpu_percent > avg_cpu * 3
        
        return memory_spike or cpu_spike
    
    def _detect_unusual_api_pattern(self, bot_id: str) -> bool:
        """Detect unusual API call patterns"""
        history = self.metrics_history.get(bot_id, [])
        
        if len(history) < 10:
            return False
        
        recent_metrics = history[-10:]
        
        # Check for sudden increase in API calls
        api_values = [m.api_calls for m in recent_metrics]
        avg_api = np.mean(api_values)
        current_api = recent_metrics[-1].api_calls
        
        return current_api > avg_api * 5
    
    def get_anomaly_report(self, bot_id: Optional[str] = None) -> Dict:
        """Generate comprehensive anomaly report"""
        if bot_id:
            return self._get_bot_anomaly_report(bot_id)
        else:
            return self._get_system_anomaly_report()
    
    def _get_bot_anomaly_report(self, bot_id: str) -> Dict:
        """Get anomaly report for a specific bot"""
        if bot_id not in self.metrics_history:
            return {"status": "no_data", "bot_id": bot_id}
        
        latest = self.metrics_history[bot_id][-1]
        anomalies = self.detect_anomalies(bot_id)
        
        return {
            "bot_id": bot_id,
            "timestamp": latest.timestamp.isoformat(),
            "anomalies_detected": anomalies,
            "current_metrics": {
                "cpu_percent": latest.cpu_percent,
                "memory_mb": latest.memory_mb,
                "disk_io_mb": latest.disk_io_mb,
                "network_io_mb": latest.network_io_mb,
                "process_count": latest.process_count,
                "api_calls": latest.api_calls,
                "messages_sent": latest.messages_sent,
                "messages_received": latest.messages_received
            },
            "requires_action": any(anomalies.values())
        }
    
    def _get_system_anomaly_report(self) -> Dict:
        """Get system-wide anomaly report"""
        total_bots = len(self.metrics_history)
        bots_with_anomalies = 0
        total_anomalies = 0
        
        bot_reports = {}
        
        for bot_id in self.metrics_history:
            report = self._get_bot_anomaly_report(bot_id)
            bot_reports[bot_id] = report
            
            if report.get("requires_action", False):
                bots_with_anomalies += 1
                total_anomalies += sum(1 for v in report.get("anomalies_detected", {}).values() if v)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_bots": total_bots,
            "bots_with_anomalies": bots_with_anomalies,
            "total_anomalies": total_anomalies,
            "bot_reports": bot_reports
        }
```

**Integration Point:** Add to `src/security_audit_scanner.py` and integrate with existing monitoring

**Configuration File:**
```json
// config/security/anomaly_detection.json
{
  "window_size": 100,
  "threshold_std": 3.0,
  "alert_thresholds": {
    "cpu_spike_multiplier": 3.0,
    "memory_spike_multiplier": 3.0,
    "api_spike_multiplier": 5.0,
    "communication_autocorrelation": 0.8
  },
  "enabled_checks": [
    "cpu",
    "memory",
    "disk_io",
    "network_io",
    "process_count",
    "api_calls",
    "messages_sent",
    "messages_received",
    "communication_loop",
    "resource_spike",
    "unusual_api_pattern"
  ]
}
```

---

## Phase 4: Integration and Monitoring (Week 7-8)
**Priority: LOW | Effort: MEDIUM | Impact: HIGH**

### 4.1 Security Dashboard Integration
**Objective:** Provide comprehensive security monitoring

**Implementation:** Extend existing `src/analytics_dashboard.py`

```python
# File: src/security_plane/security_dashboard.py
"""
Security dashboard for Murphy System
Integrates all security components into unified monitoring
"""

from typing import Dict, List
from datetime import datetime, timedelta
from pathlib import Path
import json
from .authorization_enhancer import MurphyAuthorizationEnhancer
from .bot_resource_quotas import BotResourceQuotaManager
from .swarm_communication_monitor import SwarmCommunicationMonitor
from .bot_anomaly_detector import BotAnomalyDetector

class MurphySecurityDashboard:
    """
    Unified security dashboard for Murphy System
    Integrates with existing analytics_dashboard.py
    """
    
    def __init__(self):
        self.authorization = MurphyAuthorizationEnhancer()
        self.resource_quotas = BotResourceQuotaManager()
        self.communication_monitor = SwarmCommunicationMonitor()
        self.anomaly_detector = BotAnomalyDetector()
    
    def generate_comprehensive_report(self) -> Dict:
        """Generate comprehensive security report"""
        return {
            "timestamp": datetime.now().isoformat(),
            "authorization": self.authorization.get_authorization_report(),
            "resource_quotas": self.resource_quotas.get_quota_report(),
            "swarm_communication": self.communication_monitor.get_communication_report(),
            "anomalies": self.anomaly_detector.get_anomaly_report(),
            "security_score": self._calculate_security_score()
        }
    
    def _calculate_security_score(self) -> float:
        """Calculate overall security score (0-100)"""
        # Authorization score
        auth_report = self.authorization.get_authorization_report()
        auth_score = 100 - (auth_report["denied"] / max(auth_report["total_requests"], 1) * 50)
        
        # Resource quota score
        quota_report = self.resource_quotas.get_quota_report()
        quota_score = 100 - (quota_report["total_violations"] * 10)
        
        # Communication score
        comm_report = self.communication_monitor.get_communication_report()
        comm_score = 100 - (comm_report["recent_alerts"] * 5)
        
        # Anomaly score
        anomaly_report = self.anomaly_detector.get_anomaly_report()
        anomaly_score = 100 - (anomaly_report["total_anomalies"] * 2)
        
        # Weighted average
        overall_score = (
            auth_score * 0.3 +
            quota_score * 0.3 +
            comm_score * 0.2 +
            anomaly_score * 0.2
        )
        
        return max(0, min(100, overall_score))
    
    def get_security_recommendations(self) -> List[str]:
        """Get security recommendations based on current state"""
        recommendations = []
        
        # Check authorization
        auth_report = self.authorization.get_authorization_report()
        if auth_report["denied"] > auth_report["authorized"] * 0.1:
            recommendations.append("High rate of authorization denials detected. Review permission policies.")
        
        # Check resource quotas
        quota_report = self.resource_quotas.get_quota_report()
        if quota_report["total_violations"] > 10:
            recommendations.append("Frequent resource quota violations. Consider increasing limits or optimizing bot behavior.")
        
        # Check communication
        comm_report = self.communication_monitor.get_communication_report()
        if comm_report["potential_loops"]:
            recommendations.append(f"Communication loops detected: {len(comm_report['potential_loops'])}. Review swarm coordination logic.")
        
        # Check anomalies
        anomaly_report = self.anomaly_detector.get_anomaly_report()
        if anomaly_report["bots_with_anomalies"] > 0:
            recommendations.append(f"Anomalies detected in {anomaly_report['bots_with_anomalies']} bots. Review anomaly reports.")
        
        return recommendations
```

**Integration Point:** Add to `src/analytics_dashboard.py` as a new security section

---

## Implementation Timeline

### Week 1-2: Critical Security Controls
- [ ] Implement enhanced authorization framework
- [ ] Add sensitive data sanitization to logging system
- [ ] Implement resource quotas for bots and swarms
- [ ] Update agent hooks for security initialization
- [ ] Write unit tests for new components
- [ ] Document new security features

### Week 3-4: Swarm Security Enhancements
- [ ] Implement communication loop detection
- [ ] Add bot identity verification system
- [ ] Integrate with existing swarm systems
- [ ] Performance testing with large swarms
- [ ] Security audit of swarm communications

### Week 5-6: Anomaly Detection
- [ ] Implement bot behavior anomaly detection
- [ ] Add automated alerting system
- [ ] Integrate with existing security audit scanner
- [ ] Train anomaly detection models
- [ ] Validate detection accuracy

### Week 7-8: Integration and Monitoring
- [ ] Build unified security dashboard
- [ ] Integrate with existing analytics dashboard
- [ ] Implement automated response system
- [ ] User acceptance testing
- [ ] Final documentation and deployment

---

## Testing Strategy

### Unit Testing
```python
# tests/test_security_enhancements.py
import pytest
from src.security_plane.authorization_enhancer import MurphyAuthorizationEnhancer
from src.security_plane.bot_resource_quotas import BotResourceQuotaManager
from src.security_plane.swarm_communication_monitor import SwarmCommunicationMonitor

def test_authorization_non_owner_blocked():
    """Test that non-owner requests are blocked"""
    auth = MurphyAuthorizationEnhancer()
    # Test implementation
    pass

def test_resource_quota_enforcement():
    """Test that resource quotas are enforced"""
    quota_mgr = BotResourceQuotaManager()
    # Test implementation
    pass

def test_communication_loop_detection():
    """Test that communication loops are detected"""
    comm_monitor = SwarmCommunicationMonitor()
    # Test implementation
    pass
```

### Integration Testing
- Test security components with existing Murphy System
- Verify integration with swarm systems
- Test with multiple bots and swarms
- Validate performance impact

### Security Testing
- Penetration testing against "Agents of Chaos" scenarios
- Red team exercises for authorization bypass
- Load testing for DoS scenarios
- Identity spoofing attempts

---

## Success Metrics

### Security Metrics
- 100% of non-owner requests blocked without explicit authorization
- 0% of sensitive data in logs (verified by automated scanning)
- < 1% false positive rate for anomaly detection
- 0 successful identity spoofing attempts
- < 5 minutes to detect communication loops

### Performance Metrics
- < 5% overhead from security monitoring
- < 100ms latency for authorization checks
- < 1 second for anomaly detection
- < 10% CPU usage for monitoring systems

### Operational Metrics
- 100% uptime for critical security components
- < 1 hour mean time to detect security incidents
- < 4 hours mean time to respond to alerts
- 99.9% accuracy in threat detection

---

## Configuration Files Structure

```
config/security/
├── authorization.json          # Bot identities and permissions
├── resource_quotas.json        # Resource limits for bots/swarms
├── swarm_communication.json    # Swarm communication rules
├── anomaly_detection.json      # Anomaly detection thresholds
└── security_dashboard.json     # Dashboard configuration

config/security/bot_keys/
├── bot_identities.json         # Bot identity registry
├── *_private.pem              # Bot private keys
└── *_public.pem               # Bot public keys

logs/security/
├── authorization.log          # Authorization decisions
├── resource_violations.log    # Resource limit violations
├── swarm_alerts.log           # Swarm security alerts
└── anomalies.log              # Anomaly detection events
```

---

## Conclusion

This security enhancement plan addresses the critical vulnerabilities identified in the "Agents of Chaos" research paper while leveraging Murphy System's existing robust security infrastructure. The phased approach allows for incremental implementation and testing, ensuring that each enhancement provides measurable security benefits without disrupting existing operations.

The plan specifically targets:
1. **Non-owner compliance** through enhanced authorization
2. **Sensitive data disclosure** through log sanitization
3. **Resource exhaustion** through quota management
4. **Communication loops** through swarm monitoring
5. **Identity spoofing** through cryptographic verification
6. **Unusual behavior** through anomaly detection

By implementing these enhancements, Murphy System will achieve a security posture that significantly exceeds the baseline established in the research paper, providing a robust foundation for secure autonomous agent and swarm deployment.

---

## References

- "Agents of Chaos" Research Paper (arXiv:2602.20021)
- Murphy System Architecture Documentation
- Existing Security Components in Murphy System
- Industry Best Practices for AI Agent Security