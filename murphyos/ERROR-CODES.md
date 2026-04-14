# MurphyOS — Error Code Catalog

Every runtime error emitted by MurphyOS components follows the pattern
`MURPHY-<MODULE>-ERR-<NNN>`. This document provides the complete catalog
grouped by module.

> **Tip:** Search your logs with `grep -E 'MURPHY-.*-ERR-'` to locate
> any error quickly.

---

## Table of Contents

1. [Auto-Encrypt Engine (001–010)](#auto-encrypt-engine)
2. [Auto-Patch Engine (011–020)](#auto-patch-engine)
3. [Memory Protection (021–030)](#memory-protection)
4. [Network Sentinel (031–043)](#network-sentinel)
5. [Credential Vault (046–060)](#credential-vault)
6. [Integrity Monitor (061–075)](#integrity-monitor)
7. [AutoSec Orchestrator (076–085)](#autosec-orchestrator)
8. [Murphy CLI (001–014)](#murphy-cli)
9. [Murphy D-Bus Service (001–003)](#murphy-d-bus-service)
10. [PQC Core Library (001–070)](#pqc-core-library)
11. [PQC Key Manager (100–106)](#pqc-key-manager)
12. [PQC TLS (200–204)](#pqc-tls)
13. [PQC Tokens (300–304)](#pqc-tokens)
14. [PQC Token Utilities (TOKEN-001–003)](#pqc-token-utilities)
15. [Secure Boot (001–004)](#secure-boot)
16. [Manifest Signing (001)](#manifest-signing)
17. [MurphyFS (001–014)](#murphyfs)
18. [Murphy Resolved (001–003)](#murphy-resolved)
19. [Nautilus Plugin (001–002)](#nautilus-plugin)

---

## Auto-Encrypt Engine

Module: `security/auto-hardening/murphy_auto_encrypt.py`

| Code | Description |
|------|-------------|
| `MURPHY-AUTOSEC-ERR-001` | `cryptography` package not installed; AES-GCM uses stdlib fallback |
| `MURPHY-AUTOSEC-ERR-002` | Could not load `libcrypto` via ctypes |
| `MURPHY-AUTOSEC-ERR-003` | `inotify` package unavailable; filesystem watcher disabled |
| `MURPHY-AUTOSEC-ERR-004` | `EVP_CIPHER_CTX_new` failed / libcrypto not loaded |
| `MURPHY-AUTOSEC-ERR-005` | GCM tag verification failed (decryption) |
| `MURPHY-AUTOSEC-ERR-006` | PQC key provider failed; falling back to local key derivation |
| `MURPHY-AUTOSEC-ERR-007` | Cannot read source file for encryption check |
| `MURPHY-AUTOSEC-ERR-008` | Cannot read file for encryption |
| `MURPHY-AUTOSEC-ERR-009` | Encryption or decryption operation failed |
| `MURPHY-AUTOSEC-ERR-010` | Cannot write encrypted file to disk |

---

## Auto-Patch Engine

Module: `security/auto-hardening/murphy_auto_patch.py`

| Code | Description |
|------|-------------|
| `MURPHY-AUTOSEC-ERR-011` | `urllib.request` unavailable / no HTTP client |
| `MURPHY-AUTOSEC-ERR-012` | btrfs probe failed |
| `MURPHY-AUTOSEC-ERR-013` | LVM probe failed |
| `MURPHY-AUTOSEC-ERR-014` | Snapshot creation failed / cannot create pre-patch snapshot |
| `MURPHY-AUTOSEC-ERR-015` | Snapshot restore failed / no snapshot path for rollback |
| `MURPHY-AUTOSEC-ERR-016` | Update check failed (network or parse error) |
| `MURPHY-AUTOSEC-ERR-017` | PQC verification error / no verifier / signature invalid |
| `MURPHY-AUTOSEC-ERR-018` | Patch URL missing / download failed |
| `MURPHY-AUTOSEC-ERR-019` | SHA3-256 mismatch — aborting patch |
| `MURPHY-AUTOSEC-ERR-020` | Patch application failed / initiating rollback |

---

## Memory Protection

Module: `security/auto-hardening/murphy_memory_protect.py`

| Code | Description |
|------|-------------|
| `MURPHY-AUTOSEC-ERR-021` | Could not load libc via ctypes |
| `MURPHY-AUTOSEC-ERR-022` | Cannot write to sysctl path |
| `MURPHY-AUTOSEC-ERR-023` | Cannot read from sysctl path |
| `MURPHY-AUTOSEC-ERR-024` | Unable to maximise ASLR (`randomize_va_space`) |
| `MURPHY-AUTOSEC-ERR-025` | Cannot raise `mmap_min_addr` |
| `MURPHY-AUTOSEC-ERR-026` | W⊕X enforcement only partially applied |
| `MURPHY-AUTOSEC-ERR-027` | libc unavailable; cannot seal memory |
| `MURPHY-AUTOSEC-ERR-028` | `mlockall` / `mlock` failed |
| `MURPHY-AUTOSEC-ERR-029` | `madvise(DONTDUMP)` failed |
| `MURPHY-AUTOSEC-ERR-030` | Unexpected error sealing memory |

---

## Network Sentinel

Module: `security/auto-hardening/murphy_network_sentinel.py`

| Code | Description |
|------|-------------|
| `MURPHY-AUTOSEC-ERR-031` | `nftables` binary not found in PATH |
| `MURPHY-AUTOSEC-ERR-032` | `nftables` table/chain setup failed |
| `MURPHY-AUTOSEC-ERR-033` | Cannot block IP — nftables unavailable |
| `MURPHY-AUTOSEC-ERR-034` | `nft add rule` command failed |
| `MURPHY-AUTOSEC-ERR-035` | Block error (generic) |
| `MURPHY-AUTOSEC-ERR-036` | Unblock / rule removal failed |
| `MURPHY-AUTOSEC-ERR-037` | Excessive DNS labels in query (exfiltration heuristic) |
| `MURPHY-AUTOSEC-ERR-038` | Oversized DNS label (>63 chars) |
| `MURPHY-AUTOSEC-ERR-039` | High-entropy DNS label detected |
| `MURPHY-AUTOSEC-ERR-040` | No connections to learn from / empty learning window |
| `MURPHY-AUTOSEC-ERR-041` | State save to disk failed |
| `MURPHY-AUTOSEC-ERR-042` | No saved state found on disk |
| `MURPHY-AUTOSEC-ERR-043` | State load / parse failed |

---

## Credential Vault

Module: `security/auto-hardening/murphy_credential_vault.py`

| Code | Description |
|------|-------------|
| `MURPHY-AUTOSEC-ERR-046` | `cryptography` library not installed |
| `MURPHY-AUTOSEC-ERR-047` | Encryption unavailable; storing credential as plaintext |
| `MURPHY-AUTOSEC-ERR-048` | HMAC verification failed — possible tampering |
| `MURPHY-AUTOSEC-ERR-049` | PQC key provider failed |
| `MURPHY-AUTOSEC-ERR-050` | Metadata save to disk failed |
| `MURPHY-AUTOSEC-ERR-051` | No vault metadata found |
| `MURPHY-AUTOSEC-ERR-052` | Metadata load / parse error |
| `MURPHY-AUTOSEC-ERR-053` | Failed to store credential |
| `MURPHY-AUTOSEC-ERR-054` | Access denied for credential retrieval |
| `MURPHY-AUTOSEC-ERR-055` | Credential not found |
| `MURPHY-AUTOSEC-ERR-056` | Decryption of credential failed |
| `MURPHY-AUTOSEC-ERR-057` | Rotation denied for credential |
| `MURPHY-AUTOSEC-ERR-058` | Credentials overdue for rotation |
| `MURPHY-AUTOSEC-ERR-059` | Auto-rotation failed |
| `MURPHY-AUTOSEC-ERR-060` | Deletion denied or deletion failed |

---

## Integrity Monitor

Module: `security/auto-hardening/murphy_integrity_monitor.py`

| Code | Description |
|------|-------------|
| `MURPHY-AUTOSEC-ERR-061` | Cannot hash file (read error) |
| `MURPHY-AUTOSEC-ERR-062` | Watched path does not exist |
| `MURPHY-AUTOSEC-ERR-063` | Baseline PQC signing failed |
| `MURPHY-AUTOSEC-ERR-064` | Baseline persist to disk failed |
| `MURPHY-AUTOSEC-ERR-065` | No baseline file found |
| `MURPHY-AUTOSEC-ERR-066` | Baseline read error |
| `MURPHY-AUTOSEC-ERR-067` | Baseline PQC signature **INVALID** |
| `MURPHY-AUTOSEC-ERR-068` | Baseline signature verification error |
| `MURPHY-AUTOSEC-ERR-069` | File missing from baseline |
| `MURPHY-AUTOSEC-ERR-070` | Integrity mismatch detected |
| `MURPHY-AUTOSEC-ERR-071` | Quarantine move failed |
| `MURPHY-AUTOSEC-ERR-072` | Restore from quarantine failed |
| `MURPHY-AUTOSEC-ERR-073` | No backup available for restore |
| `MURPHY-AUTOSEC-ERR-074` | Backup directory creation or backup copy failed |
| `MURPHY-AUTOSEC-ERR-075` | Monitoring loop error |

---

## AutoSec Orchestrator

Module: `security/auto-hardening/murphy_autosec_orchestrator.py`

| Code | Description |
|------|-------------|
| `MURPHY-AUTOSEC-ERR-076` | Security component unavailable at import time |
| `MURPHY-AUTOSEC-ERR-077` | D-Bus service not available |
| `MURPHY-AUTOSEC-ERR-078` | systemd journal not available |
| `MURPHY-AUTOSEC-ERR-079` | Encrypt / Patch engine initialization failed |
| `MURPHY-AUTOSEC-ERR-080` | Memory protection initialization failed |
| `MURPHY-AUTOSEC-ERR-081` | Network sentinel initialization failed |
| `MURPHY-AUTOSEC-ERR-082` | Credential vault initialization failed |
| `MURPHY-AUTOSEC-ERR-083` | Integrity monitor initialization failed |
| `MURPHY-AUTOSEC-ERR-084` | Health check or integrity/network scoring failed |
| `MURPHY-AUTOSEC-ERR-085` | Threat summary aggregation error |

---

## Murphy CLI

Module: `userspace/murphy-cli/murphy_cli.py`

| Code | Description |
|------|-------------|
| `MURPHY-CLI-ERR-001` | REST API GET request failed |
| `MURPHY-CLI-ERR-002` | REST API POST request failed |
| `MURPHY-CLI-ERR-003` | REST API DELETE request failed |
| `MURPHY-CLI-ERR-004` | Failed to read MurphyFS live file |
| `MURPHY-CLI-ERR-005` | D-Bus method call failed |
| `MURPHY-CLI-ERR-006` | Failed to parse MurphyFS live file as JSON |
| `MURPHY-CLI-ERR-007` | Non-numeric confidence score in status display |
| `MURPHY-CLI-ERR-008` | Gate approve filesystem fallback failed |
| `MURPHY-CLI-ERR-009` | Gate deny filesystem fallback failed |
| `MURPHY-CLI-ERR-010` | Event stream file not found |
| `MURPHY-CLI-ERR-011` | Event streaming interrupted by user |
| `MURPHY-CLI-ERR-012` | Non-numeric confidence score in confidence command |
| `MURPHY-CLI-ERR-013` | Command interrupted by user (KeyboardInterrupt) |
| `MURPHY-CLI-ERR-014` | Unhandled exception in command dispatch |

---

## Murphy D-Bus Service

Module: `userspace/murphy-dbus/murphy_dbus_service.py`

| Code | Description |
|------|-------------|
| `MURPHY-DBUS-ERR-001` | Failed to write confidence to `/murphy/live/confidence` |
| `MURPHY-DBUS-ERR-002` | Confidence polling cycle encountered an error |
| `MURPHY-DBUS-ERR-003` | Main event loop interrupted by KeyboardInterrupt |

---

## PQC Core Library

Module: `security/quantum/userspace/murphy_pqc.py`

| Code | Description |
|------|-------------|
| `MURPHY-PQC-ERR-001` | `liboqs-python` unavailable — PQC fallback stubs active |
| `MURPHY-PQC-ERR-002` | `PyNaCl` unavailable — hybrid mode disabled |
| `MURPHY-PQC-ERR-003` | `cryptography` library unavailable — AES-GCM fallback |
| `MURPHY-PQC-ERR-010` | ML-KEM-1024 key generation failed |
| `MURPHY-PQC-ERR-011` | ML-KEM-1024 encapsulation failed |
| `MURPHY-PQC-ERR-012` | ML-KEM-1024 decapsulation failed |
| `MURPHY-PQC-ERR-020` | ML-DSA-87 key generation failed |
| `MURPHY-PQC-ERR-021` | ML-DSA-87 signing failed |
| `MURPHY-PQC-ERR-022` | ML-DSA-87 verification failed |
| `MURPHY-PQC-ERR-030` | SLH-DSA key generation failed |
| `MURPHY-PQC-ERR-031` | SLH-DSA signing failed |
| `MURPHY-PQC-ERR-032` | SLH-DSA verification failed |
| `MURPHY-PQC-ERR-040` | Hybrid key exchange failed |
| `MURPHY-PQC-ERR-041` | Hybrid classical signature verification failed |
| `MURPHY-PQC-ERR-050` | AES-256-GCM symmetric encryption/decryption error |
| `MURPHY-PQC-ERR-060` | HKDF-SHA3-256 key derivation failed |
| `MURPHY-PQC-ERR-070` | Session token generation failed |

---

## PQC Key Manager

Module: `security/quantum/userspace/murphy_pqc_keymanager.py`

| Code | Description |
|------|-------------|
| `MURPHY-PQC-ERR-100` | `ioctl SET_PQC_KEY` failed |
| `MURPHY-PQC-ERR-101` | Failed to load epoch file |
| `MURPHY-PQC-ERR-102` | `aiohttp` not available for fleet key distribution |
| `MURPHY-PQC-ERR-103` | Fleet key distribution to peer failed |
| `MURPHY-PQC-ERR-104` | PQC key rotation failed (PQCError) |
| `MURPHY-PQC-ERR-105` | Unexpected error during key rotation |
| `MURPHY-PQC-ERR-106` | Failed to load `pqc.yaml` configuration |

---

## PQC TLS

Module: `security/quantum/userspace/murphy_pqc_tls.py`

| Code | Description |
|------|-------------|
| `MURPHY-PQC-ERR-200` | Certificate generation failed |
| `MURPHY-PQC-ERR-201` | SSL context creation failed |
| `MURPHY-PQC-ERR-202` | mTLS setup failed |
| `MURPHY-PQC-ERR-203` | `cryptography` library not available for TLS |
| `MURPHY-PQC-ERR-204` | Additional TLS import error |

---

## PQC Tokens

Module: `security/quantum/userspace/murphy_pqc_tokens.py`

| Code | Description |
|------|-------------|
| `MURPHY-PQC-ERR-300` | Token creation failed |
| `MURPHY-PQC-ERR-301` | Token verification failed |
| `MURPHY-PQC-ERR-302` | Token expired |
| `MURPHY-PQC-ERR-303` | Token revoked |
| `MURPHY-PQC-ERR-304` | Token parse error |

---

## PQC Token Utilities

Module: `security/quantum/userspace/murphy_pqc_tokens.py`

| Code | Description |
|------|-------------|
| `MURPHY-PQC-TOKEN-ERR-001` | Import error during PQC token initialization |
| `MURPHY-PQC-TOKEN-ERR-002` | Failed to load revocation list |
| `MURPHY-PQC-TOKEN-ERR-003` | Token invalid during rotation check |

---

## Secure Boot

Module: `security/quantum/boot/murphy_secureboot.py`

| Code | Description |
|------|-------------|
| `MURPHY-SECBOOT-ERR-001` | PQC library (`murphy_pqc`) not available |
| `MURPHY-SECBOOT-ERR-002` | Cannot write safety-level flag file |
| `MURPHY-SECBOOT-ERR-003` | Failed to parse manifest JSON |
| `MURPHY-SECBOOT-ERR-004` | PQC signature verification error |

---

## Manifest Signing

Module: `security/quantum/boot/murphy_manifest_sign.py`

| Code | Description |
|------|-------------|
| `MURPHY-MANIFEST-ERR-001` | PQC library (`murphy_pqc`) not available |

---

## MurphyFS

Module: `userspace/murphyfs/murphyfs.py`

| Code | Description |
|------|-------------|
| `MURPHYFS-ERR-001` | `fusepy` not installed |
| `MURPHYFS-ERR-002` | API request failed |
| `MURPHYFS-ERR-003` | Mount-point directory missing |
| `MURPHYFS-ERR-004` | Unexpected FUSE callback error |
| `MURPHYFS-ERR-005` | Write operation failed |
| `MURPHYFS-ERR-006` | Cache refresh failed |
| `MURPHYFS-ERR-007` | `urllib` import failed (should never happen — stdlib) |
| `MURPHYFS-ERR-008` | `/dev/murphy-confidence` not readable |
| `MURPHYFS-ERR-009` | Confidence JSON parse failed |
| `MURPHYFS-ERR-010` | Engine list JSON parse failed |
| `MURPHYFS-ERR-011` | Swarm agent list JSON parse failed |
| `MURPHYFS-ERR-012` | Gate status JSON parse failed |
| `MURPHYFS-ERR-013` | System version JSON parse failed |
| `MURPHYFS-ERR-014` | System uptime JSON parse failed |

---

## Murphy Resolved

Module: `userspace/murphy-resolved/murphy_resolved.py`

| Code | Description |
|------|-------------|
| `MURPHY-RESOLVED-ERR-001` | `dnslib` dependency not installed |
| `MURPHY-RESOLVED-ERR-002` | Upstream DNS forward failed |
| `MURPHY-RESOLVED-ERR-003` | Interrupted by KeyboardInterrupt during shutdown |

---

## Nautilus Plugin

Module: `desktop/file-manager-plugins/murphy-nautilus.py`

| Code | Description |
|------|-------------|
| `MURPHY-NAUTILUS-ERR-001` | HTTP request to Murphy API failed (URLError) |
| `MURPHY-NAUTILUS-ERR-002` | D-Bus fallback invocation failed |

---

## CGroup Manager

Module: `userspace/murphy-cgroup/murphy_cgroup_manager.py`

| Code | Description |
|------|-------------|
| `MURPHY-CGROUP-ERR-001` | cgroup v2 not available on this kernel |
| `MURPHY-CGROUP-ERR-002` | Base slice directory creation failed |
| `MURPHY-CGROUP-ERR-003` | Scope creation failed |
| `MURPHY-CGROUP-ERR-004` | Scope removal failed |
| `MURPHY-CGROUP-ERR-005` | cgroup file write failed |
| `MURPHY-CGROUP-ERR-006` | cgroup file read failed |
| `MURPHY-CGROUP-ERR-007` | Scope not found |
| `MURPHY-CGROUP-ERR-008` | cgroup stat read error |
| `MURPHY-CGROUP-ERR-009` | Permission denied writing cgroup controller |
| `MURPHY-CGROUP-ERR-010` | Orphan cleanup failed |
| `MURPHY-CGROUP-ERR-011` | Configuration file load error |
| `MURPHY-CGROUP-ERR-012` | Invalid memory specification |
| `MURPHY-CGROUP-ERR-013` | Invalid scope name format |
| `MURPHY-CGROUP-ERR-014` | Scope already exists |
| `MURPHY-CGROUP-ERR-015` | systemd sd_notify failed |

---

## Journal Bridge

Module: `userspace/murphy-journal/murphy_journal.py`

| Code | Description |
|------|-------------|
| `MURPHY-JOURNAL-ERR-001` | python-systemd journal.send() failed |
| `MURPHY-JOURNAL-ERR-002` | logger(1) subprocess failed |
| `MURPHY-JOURNAL-ERR-003` | Invalid event type |
| `MURPHY-JOURNAL-ERR-004` | Invalid severity level |
| `MURPHY-JOURNAL-ERR-005` | Journal query failed |
| `MURPHY-JOURNAL-ERR-006` | Journal Reader not available |
| `MURPHY-JOURNAL-ERR-007` | Daemon initialization error |
| `MURPHY-JOURNAL-ERR-008` | Configuration load error |

---

## Backup Manager

Module: `userspace/murphy-backup/murphy_backup.py`

| Code | Description |
|------|-------------|
| `MURPHY-BACKUP-ERR-001` | Backup target directory not found |
| `MURPHY-BACKUP-ERR-002` | btrfs snapshot creation failed |
| `MURPHY-BACKUP-ERR-003` | LVM snapshot creation failed |
| `MURPHY-BACKUP-ERR-004` | restic backup failed |
| `MURPHY-BACKUP-ERR-005` | tar archive creation failed |
| `MURPHY-BACKUP-ERR-006` | Manifest write failed |
| `MURPHY-BACKUP-ERR-007` | Restore failed |
| `MURPHY-BACKUP-ERR-008` | SHA3-256 verification mismatch |
| `MURPHY-BACKUP-ERR-009` | Pre-hook execution failed |
| `MURPHY-BACKUP-ERR-010` | Post-hook execution failed |
| `MURPHY-BACKUP-ERR-011` | Backup pruning failed |
| `MURPHY-BACKUP-ERR-012` | Export failed |
| `MURPHY-BACKUP-ERR-013` | Manifest not found |
| `MURPHY-BACKUP-ERR-014` | Database dump failed |
| `MURPHY-BACKUP-ERR-015` | Configuration load error |

---

## LLM Governor

Module: `userspace/murphy-llm-governor/murphy_llm_governor.py`

| Code | Description |
|------|-------------|
| `MURPHY-LLM-GOV-ERR-001` | State persistence write failed |
| `MURPHY-LLM-GOV-ERR-002` | State persistence load failed |
| `MURPHY-LLM-GOV-ERR-003` | nvidia-smi GPU stats query failed |
| `MURPHY-LLM-GOV-ERR-004` | Per-provider daily budget exceeded — circuit breaker tripped |
| `MURPHY-LLM-GOV-ERR-005` | Global hourly budget exceeded — circuit breaker tripped |
| `MURPHY-LLM-GOV-ERR-006` | Rate limiter acquire denied (RPM exceeded) |
| `MURPHY-LLM-GOV-ERR-007` | Rate limiter acquire denied (TPM exceeded) |
| `MURPHY-LLM-GOV-ERR-008` | GPU OOM prevention — memory > 90% threshold |
| `MURPHY-LLM-GOV-ERR-009` | GPU temperature limit exceeded |
| `MURPHY-LLM-GOV-ERR-010` | Provider health check — error rate > threshold |
| `MURPHY-LLM-GOV-ERR-011` | Configuration parse error |
| `MURPHY-LLM-GOV-ERR-012` | Circuit breaker OPEN for provider |

---

## Telemetry Exporter

Module: `userspace/murphy-telemetry-export/murphy_telemetry_export.py`

| Code | Description |
|------|-------------|
| `MURPHY-TELEMETRY-ERR-001` | D-Bus data source query failed |
| `MURPHY-TELEMETRY-ERR-002` | REST API data source query failed |
| `MURPHY-TELEMETRY-ERR-003` | MurphyFS data source read failed |
| `MURPHY-TELEMETRY-ERR-004` | cgroup filesystem read failed |
| `MURPHY-TELEMETRY-ERR-005` | Prometheus textfile atomic write failed |
| `MURPHY-TELEMETRY-ERR-006` | Metric collection cycle failed |
| `MURPHY-TELEMETRY-ERR-007` | Configuration parse error |
| `MURPHY-TELEMETRY-ERR-008` | Output directory does not exist |
| `MURPHY-TELEMETRY-ERR-009` | Daemon initialization error |
| `MURPHY-TELEMETRY-ERR-010` | Invalid metric format in render |

---

## Module Lifecycle Manager

Module: `userspace/murphy-module-lifecycle/murphy_module_lifecycle.py`

| Code | Description |
|------|-------------|
| `MURPHY-MODULE-ERR-001` | Module registry load failed |
| `MURPHY-MODULE-ERR-002` | Module registry persist failed |
| `MURPHY-MODULE-ERR-003` | Module already registered |
| `MURPHY-MODULE-ERR-004` | Module not found in registry |
| `MURPHY-MODULE-ERR-005` | systemd-run start failed |
| `MURPHY-MODULE-ERR-006` | systemctl stop failed |
| `MURPHY-MODULE-ERR-007` | Module health check failed |
| `MURPHY-MODULE-ERR-008` | Module health check — HTTP timeout |
| `MURPHY-MODULE-ERR-009` | journalctl log retrieval failed |
| `MURPHY-MODULE-ERR-010` | Auto-restart limit exceeded |
| `MURPHY-MODULE-ERR-011` | Configuration parse error |
| `MURPHY-MODULE-ERR-012` | Daemon initialization error |
