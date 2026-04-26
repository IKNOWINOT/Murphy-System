"""
src/hardware_telemetry.py
PATCH-102: Murphy Hardware Telemetry Engine

What this module does:
  Gives Murphy a continuous, quantified view of its own physical substrate:
  CPU load + frequency, RAM pressure, disk I/O, network throughput (upload/download),
  external latency (ping), system uptime, service clock hours, thermal state,
  hardware specs, and a self-derived Health Score.

Design intent:
  - Murphy should know its own body.
  - Health Score (0.0–1.0) feeds into RROM as Face 7: hardware_health.
  - All measurements are from /proc and psutil — no external deps beyond psutil.
  - Snapshot is cheap (<50ms). Historical ring buffer (last 60 snapshots = 5 min at 5s).
  - API: /api/hardware/* — all public.

Architecture:
  HardwareTelemetryEngine.snapshot() → HardwareSnapshot dataclass
  snapshot() is called by RROM every 5s, by the API on demand.
  ring_buffer: deque(maxlen=60) for trend analysis.

PATCH: 102
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import threading
import json
from collections import deque
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_SERVICE_NAME     = "murphy-production"
_NETWORK_IFACE    = "eth0"
_PING_HOST        = "8.8.8.8"
_PING_COUNT       = 1
_BUFFER_SIZE      = 60          # 5 min at 5s intervals
_HEALTH_WEIGHTS   = {
    "cpu":        0.25,
    "ram":        0.20,
    "disk":       0.10,
    "latency":    0.20,
    "network_rx": 0.10,
    "network_tx": 0.10,
    "uptime":     0.05,
}

# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class CPUStats:
    cores:          int
    vendor:         str
    model:          str
    freq_mhz:       float           # current average freq
    load_1m:        float
    load_5m:        float
    load_15m:       float
    util_pct:       float           # psutil cpu_percent (non-blocking)
    per_core_util:  List[float]     # per-core %


@dataclass
class RAMStats:
    total_gb:       float
    used_gb:        float
    available_gb:   float
    util_pct:       float
    swap_total_gb:  float
    swap_used_gb:   float
    swap_pct:       float


@dataclass
class DiskStats:
    total_gb:       float
    used_gb:        float
    free_gb:        float
    util_pct:       float
    read_mb_s:      float           # delta since last snapshot
    write_mb_s:     float


@dataclass
class NetworkStats:
    iface:          str
    state:          str             # "up" | "down"
    rx_bytes_total: int             # cumulative since boot
    tx_bytes_total: int
    rx_mb_s:        float           # delta since last snapshot (download)
    tx_mb_s:        float           # delta since last snapshot (upload)
    rx_mb_total:    float           # total GB received since boot
    tx_mb_total:    float


@dataclass
class LatencyStats:
    host:           str
    ping_ms:        Optional[float]
    ping_loss_pct:  float
    local_api_ms:   Optional[float] # loopback /api/health round-trip


@dataclass
class UptimeStats:
    system_uptime_s:    float
    system_uptime_str:  str         # human readable
    service_uptime_s:   Optional[float]
    service_uptime_str: Optional[str]
    clock_hours_today:  float       # hours service has run today


@dataclass
class ThermalStats:
    available:      bool
    zones:          Dict[str, float]  # zone_name → °C
    avg_temp_c:     Optional[float]
    note:           str


@dataclass
class HardwareSpecs:
    cpu_cores:      int
    cpu_model:      str
    cpu_vendor:     str
    ram_total_gb:   float
    disk_total_gb:  float
    network_iface:  str
    vm_platform:    str             # "Hetzner CX31 / QEMU" etc.
    kernel:         str


@dataclass
class HardwareSnapshot:
    """Full hardware telemetry snapshot. PATCH-102."""
    timestamp:      str
    epoch:          float

    # Subsystems
    cpu:            CPUStats
    ram:            RAMStats
    disk:           DiskStats
    network:        NetworkStats
    latency:        LatencyStats
    uptime:         UptimeStats
    thermal:        ThermalStats
    specs:          HardwareSpecs

    # Derived
    health_score:   float           # 0.0 (critical) – 1.0 (optimal)
    health_grade:   str             # A / B / C / D / F
    health_notes:   List[str]       # specific warnings

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Engine ────────────────────────────────────────────────────────────────────

class HardwareTelemetryEngine:
    """
    PATCH-102 — Murphy's hardware telemetry engine.

    Provides real-time and historical hardware metrics.
    Singleton — use hardware_telemetry module-level instance.
    """

    def __init__(self) -> None:
        self._ring:         deque[HardwareSnapshot] = deque(maxlen=_BUFFER_SIZE)
        self._lock          = threading.Lock()
        self._specs:        Optional[HardwareSpecs] = None
        # Delta tracking for rates
        self._last_net_rx:  Optional[int]   = None
        self._last_net_tx:  Optional[int]   = None
        self._last_disk_r:  Optional[int]   = None
        self._last_disk_w:  Optional[int]   = None
        self._last_ts:      Optional[float] = None
        # Service start time
        self._service_start: Optional[datetime] = self._get_service_start()
        # Warm up cpu_percent so first call returns real data (not 0.0)
        try:
            import psutil as _p
            _p.cpu_percent(interval=0.1, percpu=True)
        except Exception:
            pass
        logger.info("HardwareTelemetryEngine initialized — PATCH-102")

    # ── Specs (static, cached) ────────────────────────────────────────────────

    def _get_specs(self) -> HardwareSpecs:
        if self._specs:
            return self._specs
        import psutil
        cpu_info = self._read_cpu_info()
        vm_info  = self._detect_platform()
        kernel   = self._read_file("/proc/version").split()[2] if os.path.exists("/proc/version") else "unknown"
        disk     = psutil.disk_usage("/")
        self._specs = HardwareSpecs(
            cpu_cores     = psutil.cpu_count(logical=True),
            cpu_model     = cpu_info.get("model", "Unknown"),
            cpu_vendor    = cpu_info.get("vendor", "Unknown"),
            ram_total_gb  = round(psutil.virtual_memory().total / 1e9, 2),
            disk_total_gb = round(disk.total / 1e9, 1),
            network_iface = _NETWORK_IFACE,
            vm_platform   = vm_info,
            kernel        = kernel.strip(),
        )
        return self._specs

    def _read_cpu_info(self) -> Dict[str, str]:
        result = {}
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line and "model" not in result:
                        result["model"] = line.split(":", 1)[1].strip()
                    if "vendor_id" in line and "vendor" not in result:
                        result["vendor"] = line.split(":", 1)[1].strip()
        except Exception:
            pass
        return result

    def _detect_platform(self) -> str:
        try:
            dmi = self._read_file("/sys/class/dmi/id/sys_vendor").strip()
            prod = self._read_file("/sys/class/dmi/id/product_name").strip()
            return f"{dmi} / {prod}" if dmi and prod else "Unknown VM"
        except Exception:
            return "Unknown VM"

    def _get_service_start(self) -> Optional[datetime]:
        try:
            out = subprocess.check_output(
                ["systemctl", "show", _SERVICE_NAME, "--property=ActiveEnterTimestamp"],
                timeout=3, stderr=subprocess.DEVNULL
            ).decode().strip()
            ts_str = out.replace("ActiveEnterTimestamp=", "").strip()
            if ts_str and ts_str != "n/a":
                from dateutil import parser as dparser
                return dparser.parse(ts_str)
        except Exception:
            pass
        return None

    # ── CPU ──────────────────────────────────────────────────────────────────

    def _measure_cpu(self) -> CPUStats:
        import psutil
        cpu_info    = self._read_cpu_info()
        load        = os.getloadavg()
        per_core    = psutil.cpu_percent(interval=None, percpu=True)
        util        = sum(per_core) / len(per_core) if per_core else 0.0

        # Current frequency
        try:
            freq_lines = self._read_file("/proc/cpuinfo").split("\n")
            freqs = [float(l.split(":")[1].strip()) for l in freq_lines if "cpu MHz" in l]
            freq_mhz = sum(freqs) / len(freqs) if freqs else 0.0
        except Exception:
            freq_mhz = 0.0

        return CPUStats(
            cores        = len(per_core),
            vendor       = cpu_info.get("vendor", "Unknown"),
            model        = cpu_info.get("model", "Unknown"),
            freq_mhz     = round(freq_mhz, 1),
            load_1m      = round(load[0], 3),
            load_5m      = round(load[1], 3),
            load_15m     = round(load[2], 3),
            util_pct     = round(util, 1),
            per_core_util= [round(p, 1) for p in per_core],
        )

    # ── RAM ──────────────────────────────────────────────────────────────────

    def _measure_ram(self) -> RAMStats:
        import psutil
        m = psutil.virtual_memory()
        s = psutil.swap_memory()
        return RAMStats(
            total_gb    = round(m.total     / 1e9, 2),
            used_gb     = round(m.used      / 1e9, 2),
            available_gb= round(m.available / 1e9, 2),
            util_pct    = round(m.percent, 1),
            swap_total_gb = round(s.total / 1e9, 2),
            swap_used_gb  = round(s.used  / 1e9, 2),
            swap_pct      = round(s.percent, 1),
        )

    # ── Disk ─────────────────────────────────────────────────────────────────

    def _measure_disk(self, elapsed_s: float) -> DiskStats:
        import psutil
        usage = psutil.disk_usage("/")
        io    = psutil.disk_io_counters()

        read_mb_s = write_mb_s = 0.0
        if io and self._last_disk_r is not None and elapsed_s > 0:
            dr = io.read_bytes  - self._last_disk_r
            dw = io.write_bytes - self._last_disk_w
            read_mb_s  = round(max(0, dr) / 1e6 / elapsed_s, 3)
            write_mb_s = round(max(0, dw) / 1e6 / elapsed_s, 3)

        if io:
            self._last_disk_r = io.read_bytes
            self._last_disk_w = io.write_bytes

        return DiskStats(
            total_gb  = round(usage.total / 1e9, 1),
            used_gb   = round(usage.used  / 1e9, 1),
            free_gb   = round(usage.free  / 1e9, 1),
            util_pct  = round(usage.percent, 1),
            read_mb_s = read_mb_s,
            write_mb_s= write_mb_s,
        )

    # ── Network ──────────────────────────────────────────────────────────────

    def _measure_network(self, elapsed_s: float) -> NetworkStats:
        import psutil
        ifaces = psutil.net_io_counters(pernic=True)
        io     = ifaces.get(_NETWORK_IFACE) or ifaces.get("eth0") or ifaces.get("ens3")

        rx_total = tx_total = 0
        rx_mb_s  = tx_mb_s  = 0.0

        if io:
            rx_total = io.bytes_recv
            tx_total = io.bytes_sent
            if self._last_net_rx is not None and elapsed_s > 0:
                drx = rx_total - self._last_net_rx
                dtx = tx_total - self._last_net_tx
                rx_mb_s = round(max(0, drx) / 1e6 / elapsed_s, 4)
                tx_mb_s = round(max(0, dtx) / 1e6 / elapsed_s, 4)
            self._last_net_rx = rx_total
            self._last_net_tx = tx_total

        # NIC state
        state = "unknown"
        try:
            state = self._read_file(f"/sys/class/net/{_NETWORK_IFACE}/operstate").strip()
        except Exception:
            pass

        return NetworkStats(
            iface         = _NETWORK_IFACE,
            state         = state,
            rx_bytes_total= rx_total,
            tx_bytes_total= tx_total,
            rx_mb_s       = rx_mb_s,
            tx_mb_s       = tx_mb_s,
            rx_mb_total   = round(rx_total / 1e6, 1),
            tx_mb_total   = round(tx_total / 1e6, 1),
        )

    # ── Latency ──────────────────────────────────────────────────────────────

    def _measure_latency(self) -> LatencyStats:
        # External ping
        ping_ms = loss = None
        try:
            result = subprocess.run(
                ["/bin/ping", "-c", str(_PING_COUNT), "-W", "1", _PING_HOST],
                capture_output=True, text=True, timeout=4
            )
            for line in result.stdout.split("\n"):
                if "rtt" in line and "avg" in line:
                    # rtt min/avg/max/mdev = 15.3/15.4/15.5/0.06 ms
                    parts = line.split("=")[1].strip().split("/")
                    ping_ms = float(parts[1])
                if "packet loss" in line:
                    m = re.search(r"(\d+)% packet loss", line)
                    if m:
                        loss = float(m.group(1))
        except Exception:
            pass

        # Local API round-trip
        local_ms = None
        try:
            import urllib.request
            t0 = time.monotonic()
            urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=3)
            local_ms = round((time.monotonic() - t0) * 1000, 2)
        except Exception:
            pass

        return LatencyStats(
            host          = _PING_HOST,
            ping_ms       = round(ping_ms, 2) if ping_ms is not None else None,
            ping_loss_pct = loss if loss is not None else 100.0,
            local_api_ms  = local_ms,
        )

    # ── Uptime ───────────────────────────────────────────────────────────────

    def _measure_uptime(self) -> UptimeStats:
        # System uptime from /proc/uptime
        sys_uptime_s = 0.0
        try:
            val = float(self._read_file("/proc/uptime").split()[0])
            sys_uptime_s = val
        except Exception:
            pass

        # Service uptime
        svc_uptime_s = None
        if self._service_start:
            try:
                now = datetime.now(timezone.utc)
                svc = self._service_start
                if svc.tzinfo is None:
                    svc = svc.replace(tzinfo=timezone.utc)
                svc_uptime_s = max(0.0, (now - svc).total_seconds())
            except Exception:
                pass

        # Clock hours today = hours service has been running today (UTC)
        clock_today = 0.0
        if self._service_start:
            try:
                now = datetime.now(timezone.utc)
                svc = self._service_start
                if svc.tzinfo is None:
                    svc = svc.replace(tzinfo=timezone.utc)
                midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
                start_of_count = max(svc, midnight)
                clock_today = max(0.0, (now - start_of_count).total_seconds() / 3600)
            except Exception:
                pass

        def fmt(s: float) -> str:
            s = int(s)
            d, rem = divmod(s, 86400)
            h, rem = divmod(rem, 3600)
            m, sec = divmod(rem, 60)
            parts = []
            if d: parts.append(f"{d}d")
            if h: parts.append(f"{h}h")
            if m: parts.append(f"{m}m")
            if sec or not parts: parts.append(f"{sec}s")
            return " ".join(parts)

        return UptimeStats(
            system_uptime_s   = round(sys_uptime_s, 1),
            system_uptime_str = fmt(sys_uptime_s),
            service_uptime_s  = round(svc_uptime_s, 1) if svc_uptime_s is not None else None,
            service_uptime_str= fmt(svc_uptime_s) if svc_uptime_s is not None else None,
            clock_hours_today = round(clock_today, 3),
        )

    # ── Thermal ──────────────────────────────────────────────────────────────

    def _measure_thermal(self) -> ThermalStats:
        zones = {}
        try:
            import psutil
            temps = psutil.sensors_temperatures()
            for sensor, readings in temps.items():
                for r in readings:
                    key = f"{sensor}/{r.label or 'core'}"
                    zones[key] = r.current
        except Exception:
            pass

        # Also try /sys/class/thermal
        if not zones:
            try:
                base = "/sys/class/thermal"
                for d in os.listdir(base):
                    zone_path = os.path.join(base, d, "temp")
                    if os.path.exists(zone_path):
                        val = int(self._read_file(zone_path).strip())
                        zones[d] = round(val / 1000, 1)
            except Exception:
                pass

        available = bool(zones)
        avg = round(sum(zones.values()) / len(zones), 1) if zones else None
        note = "VM guest — no physical sensors exposed" if not available else "Physical sensors available"

        return ThermalStats(
            available  = available,
            zones      = zones,
            avg_temp_c = avg,
            note       = note,
        )

    # ── Health Score ─────────────────────────────────────────────────────────

    def _compute_health(
        self,
        cpu:     CPUStats,
        ram:     RAMStats,
        disk:    DiskStats,
        net:     NetworkStats,
        lat:     LatencyStats,
    ) -> tuple[float, str, list[str]]:
        """
        Derive a 0.0–1.0 Health Score from subsystem metrics.
        Lower is worse. Murphy uses this to know when to throttle or alert.
        """
        notes = []
        scores: Dict[str, float] = {}

        # CPU: 0.0 = 100% util, 1.0 = 0% util
        cpu_score = max(0.0, 1.0 - cpu.util_pct / 100.0)
        if cpu.load_1m > cpu.cores * 0.8:
            notes.append(f"CPU load high: {cpu.load_1m:.2f} (cores={cpu.cores})")
            cpu_score *= 0.7
        scores["cpu"] = cpu_score

        # RAM: linear score vs util
        ram_score = max(0.0, 1.0 - ram.util_pct / 100.0)
        if ram.util_pct > 85:
            notes.append(f"RAM critical: {ram.util_pct}% used")
        elif ram.util_pct > 70:
            notes.append(f"RAM elevated: {ram.util_pct}% used")
        if ram.swap_pct > 50:
            notes.append(f"Swap pressure: {ram.swap_pct}% used")
            ram_score *= 0.8
        scores["ram"] = ram_score

        # Disk: punish >80% usage
        disk_score = max(0.0, 1.0 - disk.util_pct / 100.0)
        if disk.util_pct > 80:
            notes.append(f"Disk critical: {disk.util_pct}% used")
        scores["disk"] = disk_score

        # Latency (external ping)
        if lat.ping_ms is None:
            lat_score = 0.3
            notes.append("External ping unreachable")
        elif lat.ping_ms < 20:
            lat_score = 1.0
        elif lat.ping_ms < 50:
            lat_score = 0.8
        elif lat.ping_ms < 100:
            lat_score = 0.6
        elif lat.ping_ms < 200:
            lat_score = 0.4
        else:
            lat_score = 0.2
            notes.append(f"High latency: {lat.ping_ms}ms")
        if lat.ping_loss_pct > 0:
            lat_score *= max(0.3, 1.0 - lat.ping_loss_pct / 100.0)
            notes.append(f"Packet loss: {lat.ping_loss_pct}%")
        scores["latency"] = lat_score

        # Network throughput (no upper cap — just flag if interface is down)
        net_rx_score = 1.0 if net.state == "up" else 0.0
        net_tx_score = 1.0 if net.state == "up" else 0.0
        if net.state != "up":
            notes.append(f"Network interface {net.iface} state: {net.state}")
        scores["network_rx"] = net_rx_score
        scores["network_tx"] = net_tx_score

        # Uptime (bonus if service has been stable >1h)
        scores["uptime"] = 1.0  # Hetzner VPS uptime is mostly out of Murphy's control

        # Weighted sum
        total = sum(_HEALTH_WEIGHTS[k] * scores[k] for k in _HEALTH_WEIGHTS)
        total = round(min(1.0, max(0.0, total)), 4)

        # Grade
        if total >= 0.90: grade = "A"
        elif total >= 0.75: grade = "B"
        elif total >= 0.60: grade = "C"
        elif total >= 0.40: grade = "D"
        else:               grade = "F"

        return total, grade, notes

    # ── Main snapshot ─────────────────────────────────────────────────────────

    def snapshot(self) -> HardwareSnapshot:
        """
        Capture a full hardware telemetry snapshot.
        Thread-safe. Delta rates are computed against the previous snapshot.
        """
        import psutil
        # Warm up cpu_percent (non-blocking — returns since last call)
        psutil.cpu_percent(interval=None, percpu=True)

        now     = time.monotonic()
        elapsed = (now - self._last_ts) if self._last_ts else 5.0
        self._last_ts = now

        specs   = self._get_specs()
        cpu     = self._measure_cpu()
        ram     = self._measure_ram()
        disk    = self._measure_disk(elapsed)
        network = self._measure_network(elapsed)
        latency = self._measure_latency()
        uptime  = self._measure_uptime()
        thermal = self._measure_thermal()

        health_score, health_grade, health_notes = self._compute_health(
            cpu, ram, disk, network, latency
        )

        snap = HardwareSnapshot(
            timestamp    = datetime.now(timezone.utc).isoformat(),
            epoch        = time.time(),
            cpu          = cpu,
            ram          = ram,
            disk         = disk,
            network      = network,
            latency      = latency,
            uptime       = uptime,
            thermal      = thermal,
            specs        = specs,
            health_score = health_score,
            health_grade = health_grade,
            health_notes = health_notes,
        )

        with self._lock:
            self._ring.append(snap)

        return snap

    def history(self, n: int = 12) -> List[Dict[str, Any]]:
        """Return last N snapshots as dicts (for trend graphs)."""
        with self._lock:
            snaps = list(self._ring)[-n:]
        return [
            {
                "ts":           s.timestamp,
                "health":       s.health_score,
                "grade":        s.health_grade,
                "cpu_pct":      s.cpu.util_pct,
                "ram_pct":      s.ram.util_pct,
                "disk_pct":     s.disk.util_pct,
                "ping_ms":      s.latency.ping_ms,
                "rx_mb_s":      s.network.rx_mb_s,
                "tx_mb_s":      s.network.tx_mb_s,
                "api_ms":       s.latency.local_api_ms,
                "load_1m":      s.cpu.load_1m,
                "clock_hours":  s.uptime.clock_hours_today,
            }
            for s in snaps
        ]

    def summary(self) -> Dict[str, Any]:
        """Lightweight summary for RROM face 7."""
        snap = self.snapshot()
        return {
            "health_score":     snap.health_score,
            "health_grade":     snap.health_grade,
            "health_notes":     snap.health_notes,
            "cpu_util_pct":     snap.cpu.util_pct,
            "cpu_load_1m":      snap.cpu.load_1m,
            "cpu_freq_mhz":     snap.cpu.freq_mhz,
            "ram_util_pct":     snap.ram.util_pct,
            "disk_util_pct":    snap.disk.util_pct,
            "ping_ms":          snap.latency.ping_ms,
            "local_api_ms":     snap.latency.local_api_ms,
            "rx_mb_s":          snap.network.rx_mb_s,
            "tx_mb_s":          snap.network.tx_mb_s,
            "net_state":        snap.network.state,
            "system_uptime":    snap.uptime.system_uptime_str,
            "service_uptime":   snap.uptime.service_uptime_str,
            "clock_hours_today":snap.uptime.clock_hours_today,
            "thermal_note":     snap.thermal.note,
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _read_file(path: str) -> str:
        with open(path) as f:
            return f.read()


# ── Singleton ─────────────────────────────────────────────────────────────────

hardware_telemetry = HardwareTelemetryEngine()
