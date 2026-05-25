"""
PATCH-351 — Capacity Watchdog + Offering/Capability Alignment
Wire into app.py lifespan startup after MurphyMind.
"""

import threading, time, logging, sqlite3, os, json
from datetime import datetime, timezone

logger = logging.getLogger("murphy.capacity_watchdog")

# ── Offering → Module map (what each tier actually delivers) ──────────────────
OFFERING_CAPABILITY_MAP = {
    "solo": {
        "price_mo": 99, "max_automations": 3,
        "delivers": ["AutomationEngine", "CRM read-only", "Email outreach (1 seq)", "Basic ROI reporting"],
        "load_estimate": {"llm_calls_day": 20, "db_writes_day": 50, "cpu_pct": 5, "ram_mb": 128},
        "hitl_events": ["Contract signature", "Outreach copy approval"],
        "server_headroom": "20 concurrent solo tenants safe on current hardware",
    },
    "business": {
        "price_mo": 299, "max_automations": 15,
        "delivers": ["AutomationEngine full", "CRM full", "APC multi-sequence outreach",
                     "SwarmCoordinator light", "ProposalEngine", "HITL email gates", "ROI dashboard"],
        "load_estimate": {"llm_calls_day": 100, "db_writes_day": 400, "cpu_pct": 15, "ram_mb": 512},
        "hitl_events": ["Contract signature", "Outreach approval", "Proposal review", "Deal >$10k"],
        "server_headroom": "6 concurrent business tenants safe on current hardware",
    },
    "professional": {
        "price_mo": 599, "max_automations": 40,
        "delivers": ["Full Swarm (MFGC+MSS+Rosetta)", "APC full pipeline", "Murphy Client",
                     "Shield Wall", "ComplianceEngine HIPAA/SOC2", "MultiLLM chain",
                     "GameForge", "WorldStateEngine", "Shadow agent"],
        "load_estimate": {"llm_calls_day": 300, "db_writes_day": 2000, "cpu_pct": 35, "ram_mb": 1500},
        "hitl_events": ["Swarm confidence <0.7", "Contract >$25k", "Compliance flag", "LLM cost >$50/day"],
        "server_headroom": "2-3 concurrent professional tenants safe; MUST SCALE at 3+",
    },
    "enterprise": {
        "price_mo": None, "max_automations": None,
        "delivers": ["All professional + dedicated Ollama", "Custom org chart", "SLA 99.9% monitoring",
                     "Custom SCADA/ERP integrations", "Dedicated HITL workflow", "Dedicated VPS"],
        "load_estimate": {"llm_calls_day": 1000, "db_writes_day": 10000, "cpu_pct": 70, "ram_mb": 5000},
        "hitl_events": ["Auto-scale recommendation", "SLA breach risk", "New enterprise deal close"],
        "server_headroom": "REQUIRES dedicated Hetzner CPX41 (8vCPU/16GB ~$40/mo) per tenant",
    },
}

# ── Scale thresholds ──────────────────────────────────────────────────────────
SCALE_THRESHOLDS = {
    "cpu_warn":       80.0,   # % — notify
    "cpu_critical":   95.0,   # % — urgent notify + recommend scale
    "ram_warn":       80.0,   # % — notify
    "ram_critical":   90.0,   # % — urgent
    "disk_warn":      75.0,   # % — notify (disk grows fast from DBs)
    "disk_critical":  90.0,   # % — urgent
    "llm_calls_warn": 500,    # calls/day — notify
    "llm_cost_warn":  50.0,   # USD/day — notify
    "hitl_depth_warn": 5,     # items pending — notify
    "reply_stale_days": 7,    # days no inbound reply — notify
    # Disk growth projections (current rate):
    # murphy_mind.db: 14MB, growing ~1MB/day → fills ~69 days if unchecked
    # signal_records.db: 11MB, growing ~0.5MB/day
    # cidp_reports.db: 9MB
    # Recommend: auto-purge logs >30 days, archive signal_records monthly
}

# ── Cooldown state (in-memory, resets on restart) ────────────────────────────
_last_alert: dict = {}
_COOLDOWNS = {
    "cpu_warn": 1800, "cpu_critical": 600, "ram_warn": 1800,
    "ram_critical": 600, "disk_warn": 7200, "disk_critical": 900,
    "llm_calls_warn": 3600, "llm_cost_warn": 7200,
    "hitl_depth_warn": 3600, "reply_stale_days": 86400,
}

def _on_cooldown(key: str) -> bool:
    last = _last_alert.get(key, 0)
    return (time.time() - last) < _COOLDOWNS.get(key, 3600)

def _mark_fired(key: str):
    _last_alert[key] = time.time()

def _notify_corey(message: str, severity: str = "warning", data: dict = None):
    """Send notification via /api/murphy/ask-steve (internal call)."""
    try:
        import urllib.request
        payload = json.dumps({
            "message": f"[MURPHY CAPACITY {severity.upper()}]\n\n{message}",
            "source": "capacity_watchdog",
            "severity": severity,
            "data": data or {},
            "ts": datetime.now(timezone.utc).isoformat(),
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/murphy/ask-steve",
            data=payload,
            headers={"Content-Type": "application/json", "X-Internal": "capacity_watchdog"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
        logger.info("Capacity alert sent: %s", message[:80])
    except Exception as e:
        logger.warning("Capacity alert delivery failed: %s | msg: %s", e, message[:80])

def _get_metrics() -> dict:
    """Collect live system metrics."""
    metrics = {}
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        metrics["cpu_pct"] = cpu
        metrics["ram_pct"] = mem.percent
        metrics["ram_used_gb"] = mem.used / (1024**3)
        metrics["disk_pct"] = disk.percent
        metrics["disk_used_gb"] = disk.used / (1024**3)
        metrics["disk_free_gb"] = disk.free / (1024**3)
    except Exception as e:
        logger.warning("psutil metrics failed: %s", e)
        # Fallback: read /proc
        try:
            with open("/proc/loadavg") as f:
                load = float(f.read().split()[0])
            metrics["cpu_pct"] = min(load / 4 * 100, 100)  # 4 vCPUs
        except Exception:
            metrics["cpu_pct"] = 0

    # LLM cost today
    try:
        db = sqlite3.connect("/var/lib/murphy-production/llm_cost_ledger.db", timeout=3)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = db.execute("SELECT total_calls, total_cost_usd FROM daily_summary WHERE date=?", (today,)).fetchone()
        metrics["llm_calls_today"] = row[0] if row else 0
        metrics["llm_cost_today"] = row[1] if row else 0.0
        db.close()
    except Exception:
        metrics["llm_calls_today"] = 0
        metrics["llm_cost_today"] = 0.0

    # HITL queue depth
    try:
        db2 = sqlite3.connect("/var/lib/murphy-production/hitl_queue.db", timeout=3)
        depth = db2.execute("SELECT COUNT(*) FROM hitl_queue WHERE status='pending'").fetchone()
        metrics["hitl_depth"] = depth[0] if depth else 0
        db2.close()
    except Exception:
        metrics["hitl_depth"] = 0

    # Days since last inbound reply
    try:
        db3 = sqlite3.connect("/var/lib/murphy-production/crm.db", timeout=3)
        last_act = db3.execute(
            "SELECT created_at FROM activities WHERE activity_type LIKE '%inbound%' OR activity_type LIKE '%reply%' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if last_act and last_act[0]:
            from datetime import datetime as _dt
            last_dt = _dt.fromisoformat(str(last_act[0]).replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - last_dt
            metrics["days_since_reply"] = delta.days
        else:
            metrics["days_since_reply"] = 999
        db3.close()
    except Exception:
        metrics["days_since_reply"] = 0

    return metrics

def run_watchdog_cycle():
    """Single watchdog evaluation. Called every 5 minutes."""
    try:
        m = _get_metrics()
        alerts = []

        # CPU
        cpu = m.get("cpu_pct", 0)
        if cpu > SCALE_THRESHOLDS["cpu_critical"] and not _on_cooldown("cpu_critical"):
            msg = f"CPU CRITICAL at {cpu:.1f}% — Murphy is degraded. Swarm tasks backing up. Recommend: scale to Hetzner CPX41 (8vCPU/16GB, ~$40/mo)."
            _notify_corey(msg, "critical", {"cpu_pct": cpu})
            _mark_fired("cpu_critical")
            alerts.append("CPU_CRITICAL")
        elif cpu > SCALE_THRESHOLDS["cpu_warn"] and not _on_cooldown("cpu_warn"):
            msg = f"CPU at {cpu:.1f}% — approaching limit. Current: 4 vCPU. Consider throttling APC cadence or Swarm concurrency."
            _notify_corey(msg, "warning", {"cpu_pct": cpu})
            _mark_fired("cpu_warn")
            alerts.append("CPU_WARN")

        # RAM
        ram = m.get("ram_pct", 0)
        ram_gb = m.get("ram_used_gb", 0)
        if ram > SCALE_THRESHOLDS["ram_critical"] and not _on_cooldown("ram_critical"):
            msg = f"RAM CRITICAL at {ram:.1f}% ({ram_gb:.1f}GB / 8GB) — OOM risk. Ollama phi3 + swarm tasks are memory-heavy. Restart or scale."
            _notify_corey(msg, "critical", {"ram_pct": ram, "ram_used_gb": ram_gb})
            _mark_fired("ram_critical")
            alerts.append("RAM_CRITICAL")
        elif ram > SCALE_THRESHOLDS["ram_warn"] and not _on_cooldown("ram_warn"):
            msg = f"RAM at {ram:.1f}% ({ram_gb:.1f}GB / 8GB) — getting tight. Monitor for OOM on next Swarm run."
            _notify_corey(msg, "warning", {"ram_pct": ram, "ram_used_gb": ram_gb})
            _mark_fired("ram_warn")
            alerts.append("RAM_WARN")

        # Disk
        disk = m.get("disk_pct", 0)
        free_gb = m.get("disk_free_gb", 0)
        if disk > SCALE_THRESHOLDS["disk_critical"] and not _on_cooldown("disk_critical"):
            msg = f"DISK CRITICAL at {disk:.1f}% ({free_gb:.1f}GB free) — Murphy will crash if disk fills. Purge /var/lib/murphy-production/signal_records.db older records NOW."
            _notify_corey(msg, "critical", {"disk_pct": disk, "free_gb": free_gb})
            _mark_fired("disk_critical")
            alerts.append("DISK_CRITICAL")
        elif disk > SCALE_THRESHOLDS["disk_warn"] and not _on_cooldown("disk_warn"):
            msg = f"Disk at {disk:.1f}% ({free_gb:.1f}GB free) — murphy_mind.db, signal_records.db, cidp_reports.db are growing. Set up 30-day log rotation."
            _notify_corey(msg, "warning", {"disk_pct": disk, "free_gb": free_gb})
            _mark_fired("disk_warn")
            alerts.append("DISK_WARN")

        # LLM calls
        llm_calls = m.get("llm_calls_today", 0)
        if llm_calls > SCALE_THRESHOLDS["llm_calls_warn"] and not _on_cooldown("llm_calls_warn"):
            msg = f"LLM calls today: {llm_calls} — approaching Together.ai rate limits. Review which workflows are making excess calls."
            _notify_corey(msg, "warning", {"llm_calls_today": llm_calls})
            _mark_fired("llm_calls_warn")
            alerts.append("LLM_CALLS_WARN")

        # LLM cost
        llm_cost = m.get("llm_cost_today", 0.0)
        if llm_cost > SCALE_THRESHOLDS["llm_cost_warn"] and not _on_cooldown("llm_cost_warn"):
            msg = f"LLM cost today: ${llm_cost:.2f} — spike detected. Review logs at /api/llm/cost/ledger."
            _notify_corey(msg, "warning", {"llm_cost_usd": llm_cost})
            _mark_fired("llm_cost_warn")
            alerts.append("LLM_COST_WARN")

        # HITL depth
        hitl = m.get("hitl_depth", 0)
        if hitl > SCALE_THRESHOLDS["hitl_depth_warn"] and not _on_cooldown("hitl_depth_warn"):
            msg = f"HITL queue has {hitl} pending items waiting for you. Murphy is blocked on human decisions. Check https://murphy.systems/ui/dashboard → HITL tab."
            _notify_corey(msg, "warning", {"hitl_queue_depth": hitl})
            _mark_fired("hitl_depth_warn")
            alerts.append("HITL_DEPTH_WARN")

        # Reply staleness
        days = m.get("days_since_reply", 0)
        if days > SCALE_THRESHOLDS["reply_stale_days"] and not _on_cooldown("reply_stale_days"):
            msg = f"No inbound replies in {days} days. APC outreach may need copy refresh. Check outreach log at /api/crm/activities."
            _notify_corey(msg, "info", {"days_since_reply": days})
            _mark_fired("reply_stale_days")
            alerts.append("REPLY_STALE")

        if alerts:
            logger.warning("Watchdog fired alerts: %s | metrics: cpu=%.1f%% ram=%.1f%% disk=%.1f%% llm_calls=%d hitl=%d",
                           alerts, cpu, m.get("ram_pct",0), m.get("disk_pct",0), llm_calls, hitl)
        else:
            logger.debug("Watchdog OK: cpu=%.1f%% ram=%.1f%% disk=%.1f%% llm=%d hitl=%d",
                         cpu, m.get("ram_pct",0), m.get("disk_pct",0), llm_calls, hitl)

        # Write metrics to DB for /api/health/capacity endpoint
        try:
            db = sqlite3.connect("/var/lib/murphy-production/murphy_audit.db", timeout=3)
            db.execute("""
                CREATE TABLE IF NOT EXISTS capacity_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT,
                    cpu_pct REAL, ram_pct REAL, disk_pct REAL,
                    llm_calls_today INTEGER, llm_cost_today REAL,
                    hitl_depth INTEGER, days_since_reply INTEGER,
                    alerts TEXT
                )
            """)
            db.execute("""
                INSERT INTO capacity_snapshots
                (ts, cpu_pct, ram_pct, disk_pct, llm_calls_today, llm_cost_today, hitl_depth, days_since_reply, alerts)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                m.get("cpu_pct", 0), m.get("ram_pct", 0), m.get("disk_pct", 0),
                m.get("llm_calls_today", 0), m.get("llm_cost_today", 0),
                m.get("hitl_depth", 0), m.get("days_since_reply", 0),
                json.dumps(alerts),
            ))
            # Keep last 2880 snapshots (10 days at 5min intervals)
            db.execute("DELETE FROM capacity_snapshots WHERE id NOT IN (SELECT id FROM capacity_snapshots ORDER BY id DESC LIMIT 2880)")
            db.commit()
            db.close()
        except Exception as db_e:
            logger.debug("Capacity snapshot write failed: %s", db_e)

    except Exception as e:
        logger.error("Watchdog cycle error: %s", e)

def start_capacity_watchdog():
    """Start the 5-minute capacity watchdog in a background thread."""
    def _loop():
        logger.info("PATCH-351: Capacity watchdog started — 5min interval")
        # Run once immediately at startup
        run_watchdog_cycle()
        while True:
            time.sleep(300)  # 5 minutes
            run_watchdog_cycle()

    t = threading.Thread(target=_loop, daemon=True, name="murphy-capacity-watchdog")
    t.start()
    return t

