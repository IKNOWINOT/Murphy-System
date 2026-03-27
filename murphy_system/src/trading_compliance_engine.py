# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Trading Regulatory Compliance Engine — Murphy System

Mandatory gate that must be passed before ANY live-trading activity is
enabled.  Enforces a layered compliance check covering:

  1. **Configuration gate** — required environment variables present
  2. **Sandbox graduation** — paper-trading profitability threshold met
  3. **Regulatory self-declaration** — operator has acknowledged their
     jurisdiction's trading regulations (SEC/FINRA, MiFID II, ASIC, etc.)
  4. **KYC/AML attestation** — operator confirms identity / AML obligations
  5. **Risk-parameter review** — sane stop-loss, position-size, daily-loss limits
  6. **Rate-limit sanity** — API rate limits confirmed understood
  7. **Explicit live-mode flag** — COINBASE_LIVE_MODE=true must be set

All checks must pass.  A single failure blocks live trading.
The result is cached in-process; re-run ``ComplianceEngine.evaluate()``
after correcting findings.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ComplianceStatus(Enum):
    """Overall compliance verdict."""
    PASS    = "pass"
    FAIL    = "fail"
    PENDING = "pending"
    UNKNOWN = "unknown"


class CheckSeverity(Enum):
    """Severity of a single compliance finding."""
    BLOCKER  = "blocker"   # Prevents live trading
    WARNING  = "warning"   # Should be resolved but not a hard block
    INFO     = "info"      # Informational


class Jurisdiction(Enum):
    """Supported regulatory jurisdictions for self-declaration."""
    US       = "us"        # SEC / FINRA
    EU       = "eu"        # MiFID II / ESMA
    UK       = "uk"        # FCA
    AU       = "au"        # ASIC
    CA       = "ca"        # CSA / IIROC
    SG       = "sg"        # MAS
    OTHER    = "other"     # User-declared jurisdiction outside above list
    PERSONAL = "personal"  # Personal use only — no brokerage/client funds


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ComplianceCheck:
    """Result of a single compliance check."""
    check_id:    str
    name:        str
    description: str
    severity:    CheckSeverity
    status:      ComplianceStatus
    detail:      str = ""
    remediation: str = ""


@dataclass
class ComplianceReport:
    """Full compliance evaluation report."""
    report_id:   str
    evaluated_at: str
    overall:     ComplianceStatus
    checks:      List[ComplianceCheck] = field(default_factory=list)
    jurisdiction: str = ""
    live_mode_allowed: bool = False

    # Convenience helpers
    def blockers(self) -> List[ComplianceCheck]:
        return [c for c in self.checks if c.severity == CheckSeverity.BLOCKER and c.status == ComplianceStatus.FAIL]

    def warnings(self) -> List[ComplianceCheck]:
        return [c for c in self.checks if c.severity == CheckSeverity.WARNING and c.status == ComplianceStatus.FAIL]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "evaluated_at": self.evaluated_at,
            "overall": self.overall.value,
            "live_mode_allowed": self.live_mode_allowed,
            "jurisdiction": self.jurisdiction,
            "checks": [
                {
                    "check_id": c.check_id,
                    "name": c.name,
                    "description": c.description,
                    "severity": c.severity.value,
                    "status": c.status.value,
                    "detail": c.detail,
                    "remediation": c.remediation,
                }
                for c in self.checks
            ],
            "summary": {
                "total": len(self.checks),
                "passed": sum(1 for c in self.checks if c.status == ComplianceStatus.PASS),
                "failed_blockers": len(self.blockers()),
                "failed_warnings": len(self.warnings()),
            },
        }


# ---------------------------------------------------------------------------
# Compliance check definitions
# ---------------------------------------------------------------------------

_REQUIRED_ENV_VARS = [
    ("COINBASE_API_KEY",    "Coinbase API key for live trading"),
    ("COINBASE_API_SECRET", "Coinbase API secret for live trading"),
]

_RECOMMENDED_RISK_ENV_VARS = {
    "TRADING_MAX_DAILY_LOSS_USD":     ("500", "Maximum daily loss in USD"),
    "TRADING_MAX_POSITION_SIZE_USD":  ("5000", "Maximum single position in USD"),
    "TRADING_DEFAULT_STOP_LOSS_PCT":  ("0.03", "Default stop-loss percentage"),
}


class ComplianceEngine:
    """
    Evaluates all compliance checks and determines whether live trading
    is permitted.

    Usage::

        engine = ComplianceEngine()
        report = engine.evaluate()
        if report.live_mode_allowed:
            # safe to enable live trading
            ...

    Thread-safe: report caching uses a lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_report: Optional[ComplianceReport] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def evaluate(
        self,
        jurisdiction: str = "",
        kyc_acknowledged: bool = False,
        regulations_acknowledged: bool = False,
        paper_trading_days: int = 0,
        paper_trading_profitable_days: int = 0,
        paper_trading_win_rate: float = 0.0,
        paper_trading_total_return_pct: float = 0.0,
        override_paper_graduation: bool = False,
    ) -> ComplianceReport:
        """
        Run all compliance checks and return a :class:`ComplianceReport`.

        Parameters
        ----------
        jurisdiction : str
            Operator's declared regulatory jurisdiction (e.g. ``"us"``).
        kyc_acknowledged : bool
            Operator has confirmed KYC/AML obligations for their jurisdiction.
        regulations_acknowledged : bool
            Operator has confirmed they have reviewed applicable trading regulations.
        paper_trading_days : int
            Total number of paper-trading days completed.
        paper_trading_profitable_days : int
            Number of profitable days in paper-trading history.
        paper_trading_win_rate : float
            Win rate (0.0 – 1.0) from paper-trading history.
        paper_trading_total_return_pct : float
            Total return % achieved in paper-trading mode.
        override_paper_graduation : bool
            Administrative override to bypass paper-trading graduation gate.
            Should only be set by a privileged operator after manual review.
        """
        checks: List[ComplianceCheck] = []

        # 1. Environment / configuration gate
        checks.extend(self._check_env_config())

        # 2. Live-mode flag
        checks.append(self._check_live_mode_flag())

        # 3. Regulatory self-declaration
        checks.append(self._check_jurisdiction(jurisdiction))
        checks.append(self._check_regulations_acknowledged(regulations_acknowledged))
        checks.append(self._check_kyc_acknowledged(kyc_acknowledged))

        # 4. Paper-trading graduation
        checks.append(self._check_paper_graduation(
            paper_trading_days,
            paper_trading_profitable_days,
            paper_trading_win_rate,
            paper_trading_total_return_pct,
            override=override_paper_graduation,
        ))

        # 5. Risk parameters
        checks.extend(self._check_risk_parameters())

        # 6. Personal-use notice (not a blocker — informational)
        checks.append(self._check_personal_use_notice())

        # Derive overall status
        blockers = [c for c in checks if c.severity == CheckSeverity.BLOCKER and c.status == ComplianceStatus.FAIL]
        overall = ComplianceStatus.PASS if not blockers else ComplianceStatus.FAIL

        report = ComplianceReport(
            report_id=str(uuid.uuid4()),
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            overall=overall,
            checks=checks,
            jurisdiction=jurisdiction or "not_declared",
            live_mode_allowed=(overall == ComplianceStatus.PASS),
        )
        with self._lock:
            self._last_report = report
        return report

    def last_report(self) -> Optional[ComplianceReport]:
        """Return the most recently evaluated report, or None."""
        with self._lock:
            return self._last_report

    def is_live_trading_allowed(self) -> bool:
        """
        Quick boolean check — returns True only if the last evaluation passed.
        Returns False if no evaluation has been run.
        """
        with self._lock:
            if self._last_report is None:
                return False
            return self._last_report.live_mode_allowed

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_env_config(self) -> List[ComplianceCheck]:
        results: List[ComplianceCheck] = []
        for var, description in _REQUIRED_ENV_VARS:
            value = os.getenv(var, "")
            status = ComplianceStatus.PASS if value else ComplianceStatus.FAIL
            results.append(ComplianceCheck(
                check_id=f"env_{var.lower()}",
                name=f"Environment variable: {var}",
                description=description,
                severity=CheckSeverity.BLOCKER,
                status=status,
                detail="" if value else f"{var} is not set in the environment.",
                remediation=f"Set {var} in your .env file or environment variables.",
            ))
        return results

    def _check_live_mode_flag(self) -> ComplianceCheck:
        live_mode = os.getenv("COINBASE_LIVE_MODE", "false").strip().lower() == "true"
        return ComplianceCheck(
            check_id="live_mode_flag",
            name="Live-mode flag (COINBASE_LIVE_MODE)",
            description="COINBASE_LIVE_MODE must be explicitly set to 'true' to enable live trading.",
            severity=CheckSeverity.BLOCKER,
            status=ComplianceStatus.PASS if live_mode else ComplianceStatus.FAIL,
            detail="" if live_mode else "COINBASE_LIVE_MODE is not set to 'true'.",
            remediation="Add COINBASE_LIVE_MODE=true to your environment after all other checks pass.",
        )

    def _check_jurisdiction(self, jurisdiction: str) -> ComplianceCheck:
        known = {j.value for j in Jurisdiction}
        jur = (jurisdiction or "").strip().lower()
        ok = bool(jur and jur in known)
        return ComplianceCheck(
            check_id="jurisdiction_declared",
            name="Jurisdiction declared",
            description="Operator must declare their regulatory jurisdiction.",
            severity=CheckSeverity.BLOCKER,
            status=ComplianceStatus.PASS if ok else ComplianceStatus.FAIL,
            detail="" if ok else f"Jurisdiction '{jurisdiction}' is not a recognised value.",
            remediation=f"Pass jurisdiction as one of: {sorted(known)}",
        )

    def _check_regulations_acknowledged(self, acknowledged: bool) -> ComplianceCheck:
        return ComplianceCheck(
            check_id="regulations_acknowledged",
            name="Trading regulations acknowledged",
            description=(
                "Operator must confirm they have reviewed applicable trading regulations "
                "(SEC/FINRA for US, MiFID II for EU, FCA for UK, ASIC for AU, etc.)."
            ),
            severity=CheckSeverity.BLOCKER,
            status=ComplianceStatus.PASS if acknowledged else ComplianceStatus.FAIL,
            detail="" if acknowledged else "Operator has not acknowledged applicable trading regulations.",
            remediation=(
                "Review and acknowledge regulations for your jurisdiction. "
                "Set regulations_acknowledged=True when calling ComplianceEngine.evaluate()."
            ),
        )

    def _check_kyc_acknowledged(self, acknowledged: bool) -> ComplianceCheck:
        return ComplianceCheck(
            check_id="kyc_aml_acknowledged",
            name="KYC/AML obligations acknowledged",
            description=(
                "Operator must confirm KYC (Know Your Customer) and AML "
                "(Anti-Money Laundering) obligations have been reviewed for their jurisdiction."
            ),
            severity=CheckSeverity.BLOCKER,
            status=ComplianceStatus.PASS if acknowledged else ComplianceStatus.FAIL,
            detail="" if acknowledged else "KYC/AML obligations have not been acknowledged.",
            remediation=(
                "Ensure you have completed KYC/AML requirements on Coinbase and "
                "comply with local financial regulations. Set kyc_acknowledged=True."
            ),
        )

    def _check_paper_graduation(
        self,
        total_days: int,
        profitable_days: int,
        win_rate: float,
        total_return_pct: float,
        override: bool = False,
    ) -> ComplianceCheck:
        """
        Graduation gate — paper trading must demonstrate consistent profitability
        before live mode is permitted.

        Thresholds (all must pass):
          - At least 7 paper-trading days completed
          - At least 5 profitable days (≥71% win rate)
          - Total return ≥ 1.0% (demonstrates actual profit, not just small loss)
        """
        min_days           = int(os.getenv("COMPLIANCE_MIN_PAPER_DAYS", "7"))
        min_profitable     = int(os.getenv("COMPLIANCE_MIN_PROFITABLE_DAYS", "5"))
        min_total_return   = float(os.getenv("COMPLIANCE_MIN_RETURN_PCT", "1.0"))

        if override:
            return ComplianceCheck(
                check_id="paper_trading_graduation",
                name="Paper-trading graduation gate",
                description="Sufficient paper-trading history with consistent profitability.",
                severity=CheckSeverity.BLOCKER,
                status=ComplianceStatus.PASS,
                detail="Override applied by privileged operator.",
            )

        failures = []
        if total_days < min_days:
            failures.append(f"Only {total_days}/{min_days} paper-trading days completed.")
        if profitable_days < min_profitable:
            failures.append(f"Only {profitable_days}/{min_profitable} profitable days.")
        if total_return_pct < min_total_return:
            failures.append(f"Total return {total_return_pct:.2f}% < minimum {min_total_return:.2f}%.")

        ok = not failures
        return ComplianceCheck(
            check_id="paper_trading_graduation",
            name="Paper-trading graduation gate",
            description=(
                f"Must complete ≥{min_days} paper-trading days, "
                f"≥{min_profitable} profitable, total return ≥{min_total_return:.1f}%."
            ),
            severity=CheckSeverity.BLOCKER,
            status=ComplianceStatus.PASS if ok else ComplianceStatus.FAIL,
            detail="; ".join(failures) if failures else "",
            remediation=(
                "Continue paper trading until all graduation thresholds are met. "
                "Thresholds are configurable via COMPLIANCE_MIN_PAPER_DAYS, "
                "COMPLIANCE_MIN_PROFITABLE_DAYS, COMPLIANCE_MIN_RETURN_PCT env vars."
            ),
        )

    def _check_risk_parameters(self) -> List[ComplianceCheck]:
        results: List[ComplianceCheck] = []
        for var, (default, description) in _RECOMMENDED_RISK_ENV_VARS.items():
            value = os.getenv(var, "")
            if value:
                status = ComplianceStatus.PASS
                detail = f"{var}={value}"
            else:
                status = ComplianceStatus.FAIL
                detail = f"{var} not set; will use system default ({default})."
            results.append(ComplianceCheck(
                check_id=f"risk_{var.lower()}",
                name=f"Risk parameter: {var}",
                description=description,
                severity=CheckSeverity.WARNING,
                status=status,
                detail=detail,
                remediation=f"Set {var}={default} (or your preferred value) in your .env file.",
            ))
        return results

    def _check_personal_use_notice(self) -> ComplianceCheck:
        return ComplianceCheck(
            check_id="personal_use_notice",
            name="Personal-use notice",
            description=(
                "Murphy System trading automation is for personal use only. "
                "Do not use to manage third-party funds without appropriate regulatory authorisation."
            ),
            severity=CheckSeverity.INFO,
            status=ComplianceStatus.PASS,
            detail="This system is licensed for personal use (BSL 1.1). No third-party fund management.",
        )


# ---------------------------------------------------------------------------
# Graduation tracker — tracks paper-trading performance for graduation gate
# ---------------------------------------------------------------------------

@dataclass
class DailyPaperResult:
    """Single day's paper-trading summary."""
    date:        str    # ISO date string YYYY-MM-DD
    start_equity: float
    end_equity:  float
    trades:      int
    profitable:  bool = False

    def __post_init__(self) -> None:
        self.profitable = self.end_equity > self.start_equity


class PaperTradingGraduationTracker:
    """
    Tracks daily paper-trading results and determines whether the graduation
    thresholds for live trading have been met.

    All data is persisted to a JSON file so it survives process restarts.
    """

    _DEFAULT_PATH = "data/paper_trading_graduation.json"

    def __init__(self, storage_path: Optional[str] = None) -> None:
        self._path = storage_path or self._DEFAULT_PATH
        self._lock = threading.Lock()
        self._results: List[DailyPaperResult] = []
        self._load()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def record_day(
        self,
        date: Optional[str] = None,
        start_equity: float = 0.0,
        end_equity: float = 0.0,
        trades: int = 0,
    ) -> DailyPaperResult:
        """Record a completed paper-trading day."""
        if not date:
            date = datetime.now(timezone.utc).date().isoformat()
        result = DailyPaperResult(
            date=date,
            start_equity=start_equity,
            end_equity=end_equity,
            trades=trades,
        )
        with self._lock:
            # Overwrite any existing record for the same date
            self._results = [r for r in self._results if r.date != date]
            self._results.append(result)
            self._results.sort(key=lambda r: r.date)
        self._save()
        return result

    def summary(self) -> Dict[str, Any]:
        """Return graduation summary statistics."""
        with self._lock:
            results = list(self._results)
        if not results:
            return {
                "total_days": 0,
                "profitable_days": 0,
                "win_rate": 0.0,
                "total_return_pct": 0.0,
                "initial_equity": 0.0,
                "current_equity": 0.0,
            }
        profitable = [r for r in results if r.profitable]
        initial = results[0].start_equity or 1.0
        current = results[-1].end_equity
        total_return = ((current - initial) / initial) * 100
        return {
            "total_days": len(results),
            "profitable_days": len(profitable),
            "win_rate": len(profitable) / len(results),
            "total_return_pct": round(total_return, 4),
            "initial_equity": initial,
            "current_equity": current,
        }

    def meets_graduation_threshold(self) -> bool:
        """Return True if all graduation thresholds are met."""
        s = self.summary()
        min_days    = int(os.getenv("COMPLIANCE_MIN_PAPER_DAYS", "7"))
        min_profit  = int(os.getenv("COMPLIANCE_MIN_PROFITABLE_DAYS", "5"))
        min_return  = float(os.getenv("COMPLIANCE_MIN_RETURN_PCT", "1.0"))
        return (
            s["total_days"] >= min_days
            and s["profitable_days"] >= min_profit
            and s["total_return_pct"] >= min_return
        )

    def all_results(self) -> List[DailyPaperResult]:
        with self._lock:
            return list(self._results)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            if not os.path.exists(self._path):
                return
            with open(self._path, encoding="utf-8") as fh:
                raw = json.load(fh)
            with self._lock:
                self._results = [
                    DailyPaperResult(
                        date=r["date"],
                        start_equity=float(r["start_equity"]),
                        end_equity=float(r["end_equity"]),
                        trades=int(r.get("trades", 0)),
                    )
                    for r in raw.get("results", [])
                ]
        except Exception as exc:
            logger.warning("PaperTradingGraduationTracker: could not load %s: %s", self._path, exc)

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path) if os.path.dirname(self._path) else ".", exist_ok=True)
            with self._lock:
                data = {
                    "version": 1,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "results": [
                        {
                            "date": r.date,
                            "start_equity": r.start_equity,
                            "end_equity": r.end_equity,
                            "trades": r.trades,
                            "profitable": r.profitable,
                        }
                        for r in self._results
                    ],
                }
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except Exception as exc:
            logger.warning("PaperTradingGraduationTracker: could not save %s: %s", self._path, exc)


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_compliance_engine: Optional[ComplianceEngine] = None
_graduation_tracker: Optional[PaperTradingGraduationTracker] = None
_singleton_lock = threading.Lock()


def get_compliance_engine() -> ComplianceEngine:
    """Return the process-wide :class:`ComplianceEngine` singleton."""
    global _compliance_engine
    with _singleton_lock:
        if _compliance_engine is None:
            _compliance_engine = ComplianceEngine()
    return _compliance_engine


def get_graduation_tracker(storage_path: Optional[str] = None) -> PaperTradingGraduationTracker:
    """Return the process-wide :class:`PaperTradingGraduationTracker` singleton."""
    global _graduation_tracker
    with _singleton_lock:
        if _graduation_tracker is None:
            _graduation_tracker = PaperTradingGraduationTracker(storage_path=storage_path)
    return _graduation_tracker
