# Financial Reporting Engine

**Design Label:** BIZ-001 — Automated Financial Data Collection & Reporting  
**Source File:** `src/financial_reporting_engine.py`  
**Owner:** Finance Team / Platform Engineering

---

## Overview

The Financial Reporting Engine (FRE) collects financial data entries
(revenue, costs, refunds, transactions), generates summary reports with
trend analysis, and publishes events for downstream automation and
dashboard display.  All state is thread-safe and history is bounded
to prevent unbounded memory growth.

---

## Architecture

```
External Callers
     │  record_entry()
     ▼
FinancialReportingEngine
     │
     ├── _entries: list[FinancialEntry]  (append-only, capped)
     │
     ├── generate_report(period)
     │     compute revenue, costs, trends
     │     persist via PersistenceManager
     │     publish LEARNING_FEEDBACK event
     │
     └── get_dashboard_metrics()
           returns real-time KPIs for AnalyticsDashboard
```

---

## Key Classes

### `FinancialReportingEngine`

| Method | Description |
|--------|-------------|
| `record_entry(entry_type, amount, metadata)` | Appends an immutable financial entry |
| `generate_report(period)` | Builds a `FinancialReport` for the given time period |
| `get_dashboard_metrics()` | Returns live KPIs (revenue, burn rate, margin) |
| `get_entries(start, end)` | Retrieves entries within a date range |

### `FinancialEntry`

```python
@dataclass
class FinancialEntry:
    entry_id: str
    entry_type: EntryType         # REVENUE | EXPENSE | REFUND | TRANSFER
    amount: Decimal
    currency: str                 # ISO 4217 (e.g. "USD")
    timestamp: datetime
    metadata: dict                # arbitrary context (e.g. {"source": "stripe"})
```

### `EntryType`

```python
class EntryType(Enum):
    REVENUE  = "revenue"
    EXPENSE  = "expense"
    REFUND   = "refund"
    TRANSFER = "transfer"
```

### `FinancialReport`

```python
@dataclass
class FinancialReport:
    report_id: str
    period_start: datetime
    period_end: datetime
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal
    gross_margin: float           # 0.0 – 1.0
    growth_rate: float            # period-over-period, signed
    burn_rate: Decimal            # monthly spend rate
    entry_count: int
    generated_at: datetime
```

---

## Events Published

| Event | Payload |
|-------|---------|
| `LEARNING_FEEDBACK` | `{report_id, period, net_income, growth_rate}` |

---

## Safety Invariants

- **Thread-safe:** all shared state is guarded by `threading.Lock`
- **Immutable entries:** recorded entries cannot be modified, only appended
- **Bounded history:** configurable `max_entries` (default 100,000) prevents unbounded growth
- **Audit trail:** every `record_entry` and `generate_report` call is logged

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_entries` | `100000` | Maximum number of entries in memory |
| `default_currency` | `USD` | Default currency for reports |
| `trend_lookback_periods` | `3` | Number of prior periods for trend calculation |

---

## Dependencies

- `persistence_wal.py` — durable storage for generated reports
- `event_bus.py` — `EventBackbone` for publishing `LEARNING_FEEDBACK` events
- `analytics_dashboard.py` — optional metric aggregation consumer

---

## Usage

```python
from financial_reporting_engine import FinancialReportingEngine, EntryType
from decimal import Decimal

engine = FinancialReportingEngine()

# Record entries
engine.record_entry(
    entry_type=EntryType.REVENUE,
    amount=Decimal("4999.00"),
    metadata={"plan": "growth", "customer_id": "cust-001"},
)
engine.record_entry(
    entry_type=EntryType.EXPENSE,
    amount=Decimal("1200.00"),
    metadata={"category": "hosting"},
)

# Generate a monthly report
report = engine.generate_report(period="2026-03")
print(f"Net income: {report.net_income}, Margin: {report.gross_margin:.1%}")
```

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
