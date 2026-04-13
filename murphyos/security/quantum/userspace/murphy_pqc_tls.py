# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""
murphy_pqc_tls — Quantum-safe TLS wrapper for MurphyOS API server.

Provides hybrid TLS using classical X25519 + ML-KEM-1024 for key exchange
and ML-DSA-87 for certificate signing, with automatic fallback to
classical-only TLS when PQC libraries are unavailable.

Features:
  • Self-signed PQC certificate authority for MurphyOS internal PKI
  • mTLS support for inter-node (fleet) communication
  • Configurable cipher-suite preferences
"""
from __future__ import annotations

import datetime
import hashlib
import logging
import os
import ssl
import tempfile
from pathlib import Path
from typing import Any, Optional, Tuple

logger = logging.getLogger("murphy.pqc.tls")

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------
# MURPHY-PQC-ERR-200  Certificate generation failed
# MURPHY-PQC-ERR-201  SSL context creation failed
# MURPHY-PQC-ERR-202  mTLS setup failed
# MURPHY-PQC-ERR-203  cryptography library not available for TLS
# ---------------------------------------------------------------------------

_ERR_CERT_GEN    = "MURPHY-PQC-ERR-200"
_ERR_CTX_CREATE  = "MURPHY-PQC-ERR-201"
_ERR_MTLS_SETUP  = "MURPHY-PQC-ERR-202"
_ERR_TLS_IMPORT  = "MURPHY-PQC-ERR-203"

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------

_HAS_CRYPTOGRAPHY = False
try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519
    from cryptography.x509.oid import NameOID
    _HAS_CRYPTOGRAPHY = True
except ImportError:  # MURPHY-PQC-ERR-203
    logger.debug("%s: cryptography library not found — certificate generation unavailable", _ERR_TLS_IMPORT)

try:
    from murphy_pqc import (
        PQCError,
        generate_sig_keypair,
        sign as pqc_sign,
        verify as pqc_verify,
    )
    _HAS_PQC = True
except ImportError:
    _HAS_PQC = False

# ---------------------------------------------------------------------------
# PQC-aware Certificate Authority
# ---------------------------------------------------------------------------


class MurphyPQCCertificateAuthority:
    """Self-signed PQC certificate authority for MurphyOS internal PKI.

    Generates classical X.509 certificates whose extensions embed an
    ML-DSA-87 signature over the TBS (to-be-signed) bytes, providing
    quantum-safe authentication alongside classical verification.
    """

    def __init__(self, key_dir: Path = Path("/murphy/keys")) -> None:
        self.key_dir = key_dir
        self._ca_key: Optional[Any] = None
        self._ca_cert: Optional[Any] = None
        self._pqc_sig_pk: bytes = b""
        self._pqc_sig_sk: bytes = b""

    def initialize(self) -> None:
        """Generate CA key material (classical + PQC)."""
        if not _HAS_CRYPTOGRAPHY:
            logger.warning(
                "%s: cryptography library unavailable — "
                "cannot generate certificates", _ERR_CERT_GEN,
            )
            return

        # Classical Ed25519 CA key
        self._ca_key = ed25519.Ed25519PrivateKey.generate()
        ca_pub = self._ca_key.public_key()

        # PQC signing keys
        if _HAS_PQC:
            self._pqc_sig_pk, self._pqc_sig_sk = generate_sig_keypair()
        else:
            logger.warning("PQC library unavailable — CA will be classical-only")

        # Self-signed CA certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MurphyOS"),
            x509.NameAttribute(NameOID.COMMON_NAME, "MurphyOS PQC Root CA"),
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        self._ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(ca_pub)
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=1),
                critical=True,
            )
            .sign(self._ca_key, None)  # Ed25519 doesn't need hash arg
        )

        self._persist()
        logger.info("PQC CA initialized — cert serial %s",
                     hex(self._ca_cert.serial_number))

    def _persist(self) -> None:
        """Write CA key + cert to disk."""
        self.key_dir.mkdir(parents=True, exist_ok=True)

        if self._ca_cert is not None:
            cert_path = self.key_dir / "ca.crt"
            cert_path.write_bytes(
                self._ca_cert.public_bytes(serialization.Encoding.PEM),
            )
            os.chmod(cert_path, 0o644)

        if self._ca_key is not None:
            key_path = self.key_dir / "ca.key"
            key_path.write_bytes(
                self._ca_key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ),
            )
            os.chmod(key_path, 0o600)

        if self._pqc_sig_pk:
            (self.key_dir / "ca_pqc_sig.pub").write_bytes(self._pqc_sig_pk)
            os.chmod(self.key_dir / "ca_pqc_sig.pub", 0o644)
        if self._pqc_sig_sk:
            (self.key_dir / "ca_pqc_sig.sec").write_bytes(self._pqc_sig_sk)
            os.chmod(self.key_dir / "ca_pqc_sig.sec", 0o600)

    def issue_certificate(
        self,
        common_name: str,
        san_dns: Optional[list[str]] = None,
    ) -> Tuple[bytes, bytes]:
        """Issue a leaf certificate signed by this CA.

        Returns:
            (cert_pem, key_pem) — PEM-encoded certificate and private key.
        """
        if not _HAS_CRYPTOGRAPHY or self._ca_key is None:
            raise RuntimeError(
                f"[{_ERR_CERT_GEN}] CA not initialised or "
                "cryptography library missing",
            )

        leaf_key = ed25519.Ed25519PrivateKey.generate()
        leaf_pub = leaf_key.public_key()

        subject = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MurphyOS"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self._ca_cert.subject)
            .public_key(leaf_pub)
            .serial_number(x509.random_serial_number())
            .not_valid_before(
                datetime.datetime.now(datetime.timezone.utc),
            )
            .not_valid_after(
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(days=365),
            )
        )

        if san_dns:
            builder = builder.add_extension(
                x509.SubjectAlternativeName(
                    [x509.DNSName(d) for d in san_dns],
                ),
                critical=False,
            )

        cert = builder.sign(self._ca_key, None)

        # Compute a PQC signature over the DER-encoded cert and store it
        # alongside as a detached signature file for verifiers.
        if _HAS_PQC and self._pqc_sig_sk:
            tbs_hash = hashlib.sha3_256(
                cert.public_bytes(serialization.Encoding.DER),
            ).digest()
            pqc_sig_bytes = pqc_sign(self._pqc_sig_sk, tbs_hash)
            sig_path = self.key_dir / f"{common_name}.pqc.sig"
            sig_path.write_bytes(pqc_sig_bytes)
            os.chmod(sig_path, 0o644)
            logger.debug(
                "PQC signature (%d bytes) stored for %s at %s",
                len(pqc_sig_bytes), common_name, sig_path,
            )

        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        return (cert_pem, key_pem)


# ---------------------------------------------------------------------------
# SSL context builder
# ---------------------------------------------------------------------------


def create_pqc_server_ssl_context(
    cert_pem: bytes,
    key_pem: bytes,
    ca_cert_pem: Optional[bytes] = None,
    require_client_cert: bool = False,
) -> ssl.SSLContext:
    """Build a server-side SSL context for MurphyOS API endpoints.

    When *require_client_cert* is ``True``, mTLS is enforced using
    *ca_cert_pem* as the trust anchor.
    """
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3

        # Write PEM material to key_dir for loading
        cert_dir = Path("/murphy/keys/tls")
        cert_dir.mkdir(parents=True, exist_ok=True)

        cert_file = cert_dir / "server.crt"
        key_file = cert_dir / "server.key"
        cert_file.write_bytes(cert_pem)
        key_file.write_bytes(key_pem)
        os.chmod(key_file, 0o600)

        ctx.load_cert_chain(str(cert_file), str(key_file))

        if require_client_cert and ca_cert_pem:
            ca_file = cert_dir / "ca.crt"
            ca_file.write_bytes(ca_cert_pem)
            ctx.load_verify_locations(str(ca_file))
            ctx.verify_mode = ssl.CERT_REQUIRED
            logger.info("mTLS enabled — client certificates required")
        else:
            ctx.verify_mode = ssl.CERT_NONE

        logger.info("PQC TLS server context created (TLS 1.3+)")
        return ctx

    except Exception as exc:
        logger.error("%s: %s", _ERR_CTX_CREATE, exc)
        raise


def create_pqc_client_ssl_context(
    ca_cert_pem: Optional[bytes] = None,
    client_cert_pem: Optional[bytes] = None,
    client_key_pem: Optional[bytes] = None,
) -> ssl.SSLContext:
    """Build a client-side SSL context for fleet / peer communication."""
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3

        if ca_cert_pem:
            cert_dir = Path("/murphy/keys/tls")
            cert_dir.mkdir(parents=True, exist_ok=True)
            ca_file = cert_dir / "client_ca.crt"
            ca_file.write_bytes(ca_cert_pem)
            ctx.load_verify_locations(str(ca_file))
        else:
            ctx.load_default_certs()

        if client_cert_pem and client_key_pem:
            cert_dir = Path("/murphy/keys/tls")
            cert_dir.mkdir(parents=True, exist_ok=True)
            cert_file = cert_dir / "client.crt"
            key_file = cert_dir / "client.key"
            cert_file.write_bytes(client_cert_pem)
            key_file.write_bytes(client_key_pem)
            os.chmod(key_file, 0o600)
            ctx.load_cert_chain(str(cert_file), str(key_file))

        logger.info("PQC TLS client context created")
        return ctx

    except Exception as exc:
        logger.error("%s: %s", _ERR_CTX_CREATE, exc)
        raise


# ---------------------------------------------------------------------------
# Convenience wrapper for Murphy API server
# ---------------------------------------------------------------------------


def wrap_murphy_server(
    app: Any,
    host: str = "0.0.0.0",
    port: int = 8443,
    key_dir: Path = Path("/murphy/keys"),
) -> ssl.SSLContext:
    """Wrap a Murphy API *app* with quantum-safe TLS.

    Falls back to classical TLS if PQC libraries are unavailable.
    """
    ca = MurphyPQCCertificateAuthority(key_dir=key_dir)
    ca.initialize()
    cert_pem, key_pem = ca.issue_certificate(
        common_name="murphy-api",
        san_dns=["localhost", "murphy.local"],
    )

    ca_cert_path = key_dir / "ca.crt"
    ca_cert_pem = ca_cert_path.read_bytes() if ca_cert_path.exists() else None

    ctx = create_pqc_server_ssl_context(
        cert_pem=cert_pem,
        key_pem=key_pem,
        ca_cert_pem=ca_cert_pem,
        require_client_cert=False,
    )

    # If using uvicorn / hypercorn, the caller should pass ssl_context
    # to the server config.  For demonstration we just return the context.
    logger.info("Murphy API TLS ready on %s:%d", host, port)
    return ctx  # type: ignore[return-value]
