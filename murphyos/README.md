# MurphyOS — The Transparent Security Operating System

> **Vision:** *Security that works for humans, not against them.*

MurphyOS is a security-first operating-system layer that wraps around a
standard Linux kernel to provide **post-quantum cryptography (PQC)**,
**transparent file encryption**, **automatic patching**, **network threat
detection**, **credential vaulting**, and **file-integrity monitoring** —
all orchestrated by a single confidence-scored control plane.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       Murphy CLI / Desktop                   │
│  murphy status · murphy forge · murphy swarm · murphy gate   │
├──────────────────────────────────────────────────────────────┤
│                        MurphyFS (FUSE)                       │
│  /murphy/live/confidence  ·  /murphy/engines/*  ·  events    │
├──────────────────────────────────────────────────────────────┤
│                     Userspace Services                       │
│  murphy-dbus  ·  murphy-resolved  ·  murphy-nftables         │
├──────────────────────────────────────────────────────────────┤
│               AutoSec Orchestrator (autosec)                 │
│  ┌────────────┐ ┌──────────┐ ┌──────────────┐ ┌───────────┐ │
│  │ AutoEncrypt │ │ AutoPatch│ │ NetworkSenti-│ │ Credential│ │
│  │   Engine    │ │  Engine  │ │ nel Engine   │ │   Vault   │ │
│  └────────────┘ └──────────┘ └──────────────┘ └───────────┘ │
│  ┌────────────┐ ┌──────────────────────────────────────────┐ │
│  │ Integrity  │ │       Memory Protection Engine           │ │
│  │  Monitor   │ │ (ASLR max · W^X · stack canaries)       │ │
│  └────────────┘ └──────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│             Post-Quantum Cryptography (PQC)                  │
│  ML-KEM-1024 · ML-DSA-87 · SLH-DSA · Hybrid KEM/Sig         │
│  PQC Key Manager · PQC TLS · PQC Tokens · Secure Boot       │
├──────────────────────────────────────────────────────────────┤
│                   Linux Kernel + murphy-kmod                 │
│  murphy_netfilter · nftables rules · udev · PAM              │
├──────────────────────────────────────────────────────────────┤
│                        Hardware / Boot                       │
│  Secure Boot chain · manifest signing · TPM (optional)       │
└──────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
murphyos/
├── desktop/                    # GNOME shell extension & Nautilus plugin
│   ├── file-manager-plugins/
│   └── gnome-shell-extension/
├── kernel/                     # murphy-kmod (C kernel module)
│   └── murphy-kmod/
├── packaging/                  # Debian packaging (deb)
│   └── debian/
├── security/
│   ├── apparmor/               # AppArmor profiles
│   ├── auto-hardening/         # Python security engines
│   │   ├── murphy_auto_encrypt.py
│   │   ├── murphy_auto_patch.py
│   │   ├── murphy_autosec_orchestrator.py
│   │   ├── murphy_credential_vault.py
│   │   ├── murphy_integrity_monitor.py
│   │   ├── murphy_memory_protect.py
│   │   └── murphy_network_sentinel.py
│   └── quantum/                # Post-quantum cryptography
│       ├── boot/               #   Secure-boot & manifest signing
│       ├── kernel/             #   PQC kernel module (C)
│       └── userspace/          #   PQC Python library & services
├── tests/                      # pytest test suite
│   ├── conftest.py
│   ├── test_auto_encrypt.py
│   ├── test_auto_patch.py
│   └── ...
└── userspace/
    ├── murphy-cli/             # Command-line interface
    ├── murphy-dbus/            # D-Bus system service
    ├── murphy-init/            # systemd units & generators
    ├── murphy-nftables/        # Firewall rules
    ├── murphy-pam/             # PAM module (C)
    ├── murphy-resolved/        # DNS resolver
    ├── murphy-udev/            # udev rules
    └── murphyfs/               # FUSE virtual filesystem
```

---

## Security Philosophy

### Zero-Trust by Default

Every component authenticates every request. No implicit trust between
services — even local IPC goes through the D-Bus policy and PQC-signed
tokens.

### Post-Quantum Cryptography (PQC)

MurphyOS uses **ML-KEM-1024** for key encapsulation, **ML-DSA-87** for
digital signatures, and **SLH-DSA (SPHINCS+)** for hash-based signatures.
When `liboqs` is unavailable, pure-Python fallback stubs maintain API
compatibility (reduced security — logged as `MURPHY-PQC-ERR-001`).

### Transparent Auto-Encryption

The `AutoEncryptEngine` watches directories via inotify and encrypts new
files with AES-256-GCM. A 4-byte magic header (`MFSE`) prevents
double-encryption. Decryption is transparent to authorised processes.

### Automatic Patching

`AutoPatchEngine` polls an update server, verifies patch signatures with
the PQC stack, creates btrfs/LVM snapshots before applying, and rolls back
automatically on failure.

### Memory Hardening

`MemoryProtectionEngine` maximises ASLR (`randomize_va_space = 2`),
enforces W⊕X (no page is both writable and executable), raises
`mmap_min_addr`, and seals sensitive memory regions with `mlock`.

### Network Sentinel

`NetworkSentinel` scores every outbound connection using port heuristics,
TLD reputation, and Shannon-entropy analysis of DNS queries to detect
data exfiltration. Threats above the threshold are auto-blocked via
nftables with configurable time-to-live.

### Credential Vault

`CredentialVault` stores secrets encrypted at rest with PBKDF2-derived
keys, enforces 90-day rotation, owner-based ACLs, and HMAC-based tamper
detection.

### File-Integrity Monitoring

`IntegrityMonitor` builds SHA3-256 baselines over watched paths, detects
modifications, and quarantines tampered files to a secure directory.

---

## Building & Testing

```bash
# Install test dependencies
pip install pytest

# Run the full test suite
python -m pytest murphyos/tests/ -v

# Run a single test module
python -m pytest murphyos/tests/test_auto_encrypt.py -v
```

All tests are designed to run on a **standard Ubuntu runner** with no
kernel modules, D-Bus, FUSE, or nftables. System dependencies are mocked
with `unittest.mock`.

---

## Error Codes

See [ERROR-CODES.md](ERROR-CODES.md) for the complete catalog of
`MURPHY-*-ERR-*` codes grouped by module.

---

## License

MurphyOS is released under the terms specified in the repository root
[LICENSE](../LICENSE) file.
