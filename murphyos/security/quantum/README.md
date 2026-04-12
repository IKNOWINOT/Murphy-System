# MurphyOS Post-Quantum Cryptography (PQC) Security Layer

© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

---

## Why Post-Quantum Cryptography?

### The Quantum Threat

Cryptographically-relevant quantum computers (CRQCs) will break the
asymmetric algorithms that secure every modern TLS handshake, digital
signature, and key exchange:

| Classical algorithm | Quantum attack | Status |
|---|---|---|
| RSA-2048 / RSA-4096 | Shor's algorithm | Broken in polynomial time |
| ECDSA / ECDH (P-256, secp256k1) | Shor's algorithm | Broken |
| X25519 / Ed25519 | Shor's algorithm | Broken |
| AES-256, SHA-3 | Grover's algorithm | Security halved — still safe at 256-bit |

### Harvest Now, Decrypt Later (HNDL)

Nation-state adversaries are **recording encrypted traffic today** with the
expectation that quantum computers will decrypt it in the future.  Any data
with a secrecy lifetime beyond ~2030 must be protected with
quantum-resistant algorithms **now**.

MurphyOS processes behavioural-confidence data, authentication tokens, and
fleet-coordination traffic — all of which carry long-term sensitivity.

---

## NIST Standardisation Status

MurphyOS uses the three algorithms standardised by NIST in 2024:

| MurphyOS name | NIST standard | Former name | Purpose |
|---|---|---|---|
| **ML-KEM-1024** | FIPS 203 | CRYSTALS-Kyber-1024 | Key Encapsulation (key exchange) |
| **ML-DSA-87** | FIPS 204 | CRYSTALS-Dilithium5 | Digital Signatures (tokens, certs) |
| **SLH-DSA-SHA2-256f** | FIPS 205 | SPHINCS⁺-SHA2-256f | Hash-Based Signatures (boot, long-term) |

All three are lattice/hash-based and resist both classical and quantum
attacks.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Boot Chain                        │
│  verify_chain.sh → murphy_secureboot.py             │
│  SLH-DSA-SHA2-256f manifest signature               │
└────────────────────────┬────────────────────────────┘
                         │ verified runtime
┌────────────────────────▼────────────────────────────┐
│              Kernel (murphy_pqc_kmod)                │
│  HMAC-SHA3-256 on /dev/murphy-event                 │
│  Per-session key via ioctl from keymanager           │
│  sysfs: /sys/murphy/pqc/{algorithm,key_epoch}       │
└────────────────────────┬────────────────────────────┘
                         │ ioctl key push
┌────────────────────────▼────────────────────────────┐
│           Key Manager (murphy_pqc_keymanager)       │
│  Generates & rotates ML-KEM / ML-DSA keypairs       │
│  Pushes HMAC keys to kernel                         │
│  Distributes public keys to fleet peers             │
│  Stores keys in /murphy/keys/ (0600)                │
└────────────────────────┬────────────────────────────┘
                         │ keys
┌────────────────────────▼────────────────────────────┐
│               Userspace Libraries                    │
│  murphy_pqc.py        — core crypto primitives      │
│  murphy_pqc_tls.py    — hybrid TLS wrapper          │
│  murphy_pqc_tokens.py — PQC-signed session tokens   │
└─────────────────────────────────────────────────────┘
```

---

## Key Lifecycle Management

### Generation

The key manager daemon (`murphy-pqc-keymanager.service`) generates:
- **ML-KEM-1024** keypair — for key exchange / encapsulation
- **ML-DSA-87** keypair — for signing tokens and certificates
- **SLH-DSA-SHA2-256f** keypair — for long-term boot manifest signing
- **HMAC-SHA3-256 session key** — derived via HKDF from KEM + DSA material

### Rotation

| Key type | Rotation interval | Trigger |
|---|---|---|
| HMAC session key | 24 hours (configurable) | Timer |
| ML-KEM / ML-DSA | 24 hours (configurable) | Timer |
| SLH-DSA (boot signing) | Manual / build-time | New release |
| Session tokens | 8 hours or confidence drift > 0.10 | Timer / event |

### Storage

All key material is stored under `/murphy/keys/` with POSIX permissions
`0600` (owner: `murphy`).  The epoch counter is persisted to survive
reboots.

### Distribution

Public keys are distributed to fleet peers via authenticated HTTPS POST.
Only public keys leave the node — secret keys never traverse the network.

---

## Hybrid Mode

MurphyOS defaults to **hybrid mode**: every cryptographic operation
combines a classical algorithm with its PQC counterpart.

| Operation | Classical | PQC | Combined via |
|---|---|---|---|
| Key exchange | X25519 | ML-KEM-1024 | HKDF-SHA3-256 over both shared secrets |
| Signing | Ed25519 | ML-DSA-87 | Both signatures required |
| TLS | X25519 + Ed25519 | ML-KEM-1024 + ML-DSA-87 | Dual verification |

This ensures security even if one algorithm family is unexpectedly broken.
Set `force_pqc_only: true` in `pqc.yaml` to reject classical-only
connections.

---

## Performance Considerations

| Algorithm | Key gen | Encap / Sign | Decap / Verify | Public key size | Ciphertext / Sig size |
|---|---|---|---|---|---|
| ML-KEM-1024 | ~0.2 ms | ~0.3 ms | ~0.3 ms | 1,568 B | 1,568 B |
| ML-DSA-87 | ~1.0 ms | ~2.5 ms | ~1.0 ms | 2,592 B | 4,627 B |
| SLH-DSA-SHA2-256f | ~10 ms | ~400 ms | ~20 ms | 64 B | 49,856 B |

- **KEM/DSA** are fast enough for per-request use.
- **SLH-DSA** is used only at boot / build time due to larger signatures
  and slower signing.
- HMAC-SHA3-256 in the kernel module adds < 1 µs per event.
- AES-256-GCM symmetric encryption is hardware-accelerated on modern CPUs.

---

## Upgrade Path

When NIST finalises additional algorithms (HQC for KEM round 4, etc.),
the architecture supports drop-in replacement:

1. Update `pqc.yaml` with the new algorithm name.
2. Update `murphy_pqc.py` backend mappings.
3. Rotate all keys via the key manager.
4. Re-sign boot manifests with the new hash-based scheme.

The hybrid approach means MurphyOS can adopt new algorithms incrementally
without a flag-day migration.

---

## File Reference

| Path | Purpose |
|---|---|
| `kernel/murphy_pqc_kmod.c` | Kernel module — HMAC-SHA3-256 event authentication |
| `kernel/murphy_pqc_kmod.h` | Kernel ioctl definitions |
| `kernel/Makefile` | Kernel module build |
| `userspace/murphy_pqc.py` | Core PQC library (KEM, DSA, SPHINCS+, hybrid) |
| `userspace/murphy_pqc_keymanager.py` | Key management daemon |
| `userspace/murphy_pqc_tls.py` | Quantum-safe TLS wrapper |
| `userspace/murphy_pqc_tokens.py` | PQC-signed session tokens |
| `boot/murphy_secureboot.py` | Boot-time manifest verification |
| `boot/murphy_manifest_sign.py` | Build-time manifest signing |
| `boot/verify_chain.sh` | Early-boot verification script |
| `pqc.yaml` | Default PQC configuration |
| `murphy-pqc-keymanager.service` | systemd service unit |
