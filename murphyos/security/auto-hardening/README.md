# MurphyOS Auto-Hardening Security Layer

> **Philosophy:** "Humans don't want to perform security — the system keeps
> our stuff secure for us."

Every mechanism is **automatic**, **invisible** to the user, and **never
blocks legitimate work**.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│              AutoSecOrchestrator                     │
│  initialise() ─► health_check() ─► posture score    │
├──────┬──────┬──────┬──────┬──────┬──────────────────┤
│Encry-│Patch │Memory│Net   │Cred  │Integrity         │
│ption │Engine│Prot. │Senti-│Vault │Monitor           │
│Engine│      │Engine│nel   │      │                  │
└──────┴──────┴──────┴──────┴──────┴──────────────────┘
       ▲                                     ▲
       │  PQC key hierarchy (optional)       │
       └─────────────────────────────────────┘
```

## Engines

| Engine | File | Purpose |
|--------|------|---------|
| **AutoEncryptEngine** | `murphy_auto_encrypt.py` | AES-256-GCM file encryption at rest with MFSE header |
| **AutoPatchEngine** | `murphy_auto_patch.py` | Self-updating with btrfs/LVM/tar rollback |
| **MemoryProtectionEngine** | `murphy_memory_protect.py` | ASLR, stack protection, W^X, memory sealing |
| **NetworkSentinel** | `murphy_network_sentinel.py` | Heuristic threat scoring, nftables auto-block, DNS exfil detection |
| **CredentialVault** | `murphy_credential_vault.py` | Encrypted secret storage, per-user ACL, breach-triggered rotation |
| **IntegrityMonitor** | `murphy_integrity_monitor.py` | SHA3-256 baselines, quarantine & restore on tampering |

## Error Codes

All errors follow the format `MURPHY-AUTOSEC-ERR-NNN`:

| Range | Engine |
|-------|--------|
| 001–010 | Auto-Encrypt |
| 011–020 | Auto-Patch |
| 021–030 | Memory Protection |
| 031–045 | Network Sentinel |
| 046–060 | Credential Vault |
| 061–075 | Integrity Monitor |
| 076–085 | Orchestrator |

## Quick Start

```python
from murphyos.security.auto_hardening import AutoSecOrchestrator

orch = AutoSecOrchestrator()
status = orch.initialize()   # starts all engines transparently
print(orch.get_security_posture())   # 0–100
print(orch.get_threat_summary())
```

## systemd Integration

```bash
sudo cp murphy-autosec.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now murphy-autosec
```

The service unit applies strict sandboxing: `NoNewPrivileges`,
`ProtectSystem=strict`, `MemoryDenyWriteExecute`, and more.

## Configuration

Edit `auto-hardening.yaml` to enable/disable individual engines or
customise thresholds.  All engines are enabled by default.

## License

BSL 1.1 — © 2020 Inoni Limited Liability Company — Creator: Corey Post
