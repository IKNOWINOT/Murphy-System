# Changelog

## 0.1.0 — 2026-03-29

### Added
- Initial extraction from Murphy System
- `EventBackbone` with pub/sub, circuit breakers, DLQ, retry
- Background processing loop with configurable interval
- Backpressure detection and alerting (`system.backpressure` events)
- Idempotent event publishing via `publish_event()`
- Disk persistence with atomic writes (JSON)
- String-based event types (no enum lock-in)
- Thread-safe operation throughout
- Comprehensive test suite (41 tests across 13 test classes)
- PEP 561 typing marker (`py.typed`)
- Zero external dependencies (stdlib only)
