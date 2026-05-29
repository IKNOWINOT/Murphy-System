"""
PATCH-KEK-R100 (2026-05-28 R100) — Key-Encrypting-Key envelope layering

WHAT THIS IS:
  Substrate for Corey R98.5 worry-layer pattern. K_root from
  /etc/murphy-production/environment never rotates. Outer wrapping layers
  are added when worry rises. unwrap_to_root() walks chain to recover
  K_root for derivation by R96 credential_vault.

WHY IT EXISTS:
  Corey R98.5: "key for accessing a key... another layer of security from
  another vault... when worried add an entire new layer with one button
  API that is loaded and changed and saved in a secure on device way"

  Industry standard KEK hierarchy made operator-friendly.

PUBLIC SURFACE:
  add_worry_layer(label, reason, on_device_keyref=None, created_by="system")
    Generates new outer key, wraps current outermost, persists.
    
  unwrap_to_root() -> bytes
    Walks layer_seq DESC, unwrapping each layer until layer_seq=1 (root).
    Returns 32-byte K_root for use by credential_vault HKDF.
    
  panic_rotate(reason, created_by="founder")
    One-button: calls add_worry_layer with auto-label.
    Returns {ok, new_layer_seq, layer_label, created_at}.
    
  current_outermost() -> dict
    Metadata about active outer layer (seq, label, created_at, keyref).
    Never returns key material.
    
  list_layers() -> list[dict]
    Audit view: all layers, statuses, no key material.

DESIGN CHOICE LOCKED R100 (Murphy refused — I chose immediate disk fsync):
  panic_rotate writes new key to disk + fsync BEFORE returning success.
  Reason: if process crashes between memory-write and return-to-caller,
  caller thinks rotate succeeded but key is gone. Durability > latency
  for security-rotation primitive.

KEY STORAGE (on-device):
  file:// scheme written this round; future rounds add keychain/dpapi/android
  Path: /etc/murphy-production/key_layers/layer_{seq:03d}.key
  Mode 0600 root:murphy (only Murphy reads, only root rotates)

DEPENDS ON:
  cryptography library (AES-256-GCM)
  /etc/murphy-production/environment with MURPHY_VAULT_MASTER_KEY (R98)
  /etc/murphy-production/key_layers/ directory (R100 schema)
  hitl_provenance.db key_envelope_layers table

LAST UPDATED: 2026-05-28 R100
"""

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_DB_PATH = "/var/lib/murphy-production/hitl_provenance.db"
_KEY_DIR = "/etc/murphy-production/key_layers"
_ENV_FILE = "/etc/murphy-production/environment"


def _load_root_key_from_env() -> bytes:
    """K_root from /etc/murphy-production/environment MURPHY_VAULT_MASTER_KEY."""
    # Check env first (process inherits when systemd runs monolith)
    raw = os.environ.get("MURPHY_VAULT_MASTER_KEY", "").strip()
    if not raw:
        try:
            with open(_ENV_FILE) as f:
                for line in f:
                    if line.startswith("MURPHY_VAULT_MASTER_KEY="):
                        raw = line.split("=", 1)[1].strip()
                        break
        except (OSError, IOError):
            pass
    if not raw:
        raise RuntimeError("MURPHY_VAULT_MASTER_KEY not set in env or /etc env file")
    # Hex string → 32 bytes
    if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
        return bytes.fromhex(raw)
    # Fallback: SHA-256 of whatever it is
    return hashlib.sha256(raw.encode()).digest()


def _layer_id(layer_seq: int, label: str) -> str:
    """Deterministic ID — seq+label uniquely identifies a layer."""
    return hashlib.sha256(
        "kek::{}::{}".format(layer_seq, label).encode()
    ).hexdigest()[:16]


def _file_keyref(layer_seq: int) -> str:
    """Build the on-device keyref for file:// scheme."""
    return "file://{}/layer_{:03d}.key".format(_KEY_DIR, layer_seq)


def _read_keyref_file(keyref: str) -> bytes:
    """Read key bytes from file:// keyref. 32 hex chars or 32 raw bytes."""
    if not keyref.startswith("file://"):
        raise NotImplementedError(
            "keyref scheme not yet supported: {}".format(keyref[:20])
        )
    path = keyref.replace("file://", "")
    with open(path, "rb") as f:
        raw = f.read().strip()
    if len(raw) == 64:
        try:
            return bytes.fromhex(raw.decode())
        except Exception:
            pass
    if len(raw) == 32:
        return raw
    # Treat as hex or fall back to SHA-256
    try:
        return bytes.fromhex(raw.decode())
    except Exception:
        return hashlib.sha256(raw).digest()


def _write_keyref_file(keyref: str, key_bytes: bytes) -> None:
    """Write key bytes to file:// keyref with strict perms + fsync."""
    if not keyref.startswith("file://"):
        raise NotImplementedError(
            "keyref scheme not yet supported: {}".format(keyref[:20])
        )
    path = keyref.replace("file://", "")
    # Write hex-encoded for readability (parity with env file format)
    hex_str = key_bytes.hex()
    # Atomic write via temp + rename + fsync
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, hex_str.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    # fsync the directory entry too
    try:
        dir_fd = os.open(os.path.dirname(path), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        pass


def _next_seq(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(layer_seq), 0) + 1 FROM key_envelope_layers"
    ).fetchone()
    return row[0] if row else 1


def _bootstrap_root_if_missing(db_path: str = _DB_PATH) -> None:
    """Seed seq=1 (root) row if absent. Root key comes from env file."""
    conn = sqlite3.connect(db_path, timeout=5)
    row = conn.execute(
        "SELECT layer_seq FROM key_envelope_layers WHERE layer_seq = 1"
    ).fetchone()
    if row:
        conn.close()
        return
    # Insert root metadata. K_root itself lives in env file, NOT in this table.
    layer_id = _layer_id(1, "root")
    conn.execute(
        "INSERT INTO key_envelope_layers "
        "(layer_id, layer_seq, layer_label, wraps_layer_seq, wrapped_key, "
        " nonce, on_device_keyref, created_by, add_reason, status) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (layer_id, 1, "root", None, None, None,
         "envfile://MURPHY_VAULT_MASTER_KEY",
         "R98_bootstrap", "initial root from environment", "active"),
    )
    conn.commit()
    conn.close()


def add_worry_layer(label: str, reason: str = "",
                    on_device_keyref: Optional[str] = None,
                    created_by: str = "system",
                    db_path: str = _DB_PATH) -> Dict[str, Any]:
    """Generate new outer key, wrap current outermost, persist."""
    _bootstrap_root_if_missing(db_path)
    conn = sqlite3.connect(db_path, timeout=5)

    # Find current outermost layer
    cur_outer = conn.execute(
        "SELECT layer_seq, layer_label, on_device_keyref FROM key_envelope_layers "
        "WHERE status = 'active' ORDER BY layer_seq DESC LIMIT 1"
    ).fetchone()
    if not cur_outer:
        conn.close()
        return {"ok": False, "reason": "no_active_layer_to_wrap"}
    cur_seq, cur_label, cur_keyref = cur_outer

    # Resolve current outer key bytes (root from env, otherwise from file)
    if cur_seq == 1:
        cur_key = _load_root_key_from_env()
    else:
        try:
            cur_key = _read_keyref_file(cur_keyref)
        except Exception as e:
            conn.close()
            return {"ok": False, "reason": "read_current_failed: {}".format(e)}

    # Generate new outer K
    new_seq = _next_seq(conn)
    new_key = secrets.token_bytes(32)
    new_keyref = on_device_keyref or _file_keyref(new_seq)
    new_layer_id = _layer_id(new_seq, label)

    # Write new key to disk FIRST (durable before DB commit)
    try:
        _write_keyref_file(new_keyref, new_key)
    except Exception as e:
        conn.close()
        return {"ok": False, "reason": "disk_write_failed: {}".format(e)}

    # Wrap current outer key with new outer key
    aad = "kek::{}::wraps::{}".format(new_seq, cur_seq).encode()
    nonce = secrets.token_bytes(12)
    try:
        aesgcm = AESGCM(new_key)
        wrapped = aesgcm.encrypt(nonce, cur_key, associated_data=aad)
    except Exception as e:
        conn.close()
        return {"ok": False, "reason": "wrap_failed: {}: {}".format(type(e).__name__, e)}

    # Persist new layer record
    try:
        conn.execute(
            "INSERT INTO key_envelope_layers "
            "(layer_id, layer_seq, layer_label, wraps_layer_seq, wrapped_key, "
            " nonce, associated_data, on_device_keyref, created_by, add_reason) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (new_layer_id, new_seq, label, cur_seq, wrapped, nonce, aad,
             new_keyref, created_by, reason),
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return {"ok": False, "reason": "db_persist_failed: {}".format(e)}
    finally:
        conn.close()

    return {
        "ok": True,
        "new_layer_seq": new_seq,
        "layer_label": label,
        "on_device_keyref": new_keyref,
        "wraps_layer_seq": cur_seq,
    }


def unwrap_to_root(db_path: str = _DB_PATH) -> bytes:
    """Walk outermost → root, unwrapping each layer. Returns 32-byte K_root."""
    _bootstrap_root_if_missing(db_path)
    conn = sqlite3.connect(db_path, timeout=5)
    layers = conn.execute(
        "SELECT layer_seq, on_device_keyref, wrapped_key, nonce, associated_data, "
        "       wraps_layer_seq FROM key_envelope_layers "
        "WHERE status = 'active' ORDER BY layer_seq DESC"
    ).fetchall()
    conn.close()

    if not layers:
        raise RuntimeError("no active layers")

    # Start at outermost: read its key from disk
    out_seq, out_keyref, _, _, _, _ = layers[0]
    if out_seq == 1:
        return _load_root_key_from_env()
    cur_key = _read_keyref_file(out_keyref)

    # Walk: each layer's wrapped_key decrypts to the NEXT inner key
    for (seq, keyref, wrapped, nonce, aad, wraps_seq) in layers:
        if seq == 1:
            # Root reached — env-stored, not wrapped
            return _load_root_key_from_env()
        if wrapped is None or nonce is None:
            continue
        try:
            aesgcm = AESGCM(cur_key)
            cur_key = aesgcm.decrypt(bytes(nonce), bytes(wrapped),
                                     associated_data=bytes(aad) if aad else None)
        except Exception as e:
            raise RuntimeError("unwrap failed at seq={}: {}".format(seq, e))

        # Now we have the key for wraps_seq. If wraps_seq is root, return env key.
        if wraps_seq == 1:
            return _load_root_key_from_env()
    return cur_key


def panic_rotate(reason: str = "panic_rotate triggered",
                 created_by: str = "founder",
                 db_path: str = _DB_PATH) -> Dict[str, Any]:
    """One-button: add a fresh outer layer with auto-label."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = "panic_{}".format(ts)
    return add_worry_layer(label, reason, on_device_keyref=None,
                           created_by=created_by, db_path=db_path)


def current_outermost(db_path: str = _DB_PATH) -> Dict[str, Any]:
    """Metadata about active outer layer. No key material returned."""
    _bootstrap_root_if_missing(db_path)
    conn = sqlite3.connect(db_path, timeout=3)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT layer_seq, layer_label, wraps_layer_seq, on_device_keyref, "
        "       created_at, created_by, add_reason "
        "FROM key_envelope_layers WHERE status = 'active' "
        "ORDER BY layer_seq DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def list_layers(db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Audit view of all layers. No key material returned."""
    _bootstrap_root_if_missing(db_path)
    conn = sqlite3.connect(db_path, timeout=3)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT layer_seq, layer_label, wraps_layer_seq, status, "
        "       on_device_keyref, created_at, created_by, add_reason "
        "FROM key_envelope_layers ORDER BY layer_seq"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    print("R100 KEK substrate demo")
    print("  current outermost:", current_outermost())
    print()
    r1 = add_worry_layer("worry_drill_a", "first synthetic worry layer",
                         created_by="r100_smoke")
    print("  add layer 1: {}".format(r1))
    r2 = add_worry_layer("worry_drill_b", "second synthetic worry layer",
                         created_by="r100_smoke")
    print("  add layer 2: {}".format(r2))
    r3 = panic_rotate(reason="r100_smoke panic test", created_by="founder")
    print("  panic_rotate: {}".format(r3))
    print()
    print("  All layers:")
    for L in list_layers():
        print("    seq={} label={} status={} wraps={} keyref={}".format(
            L.get("layer_seq"), L.get("layer_label"), L.get("status"),
            L.get("wraps_layer_seq"), (L.get("on_device_keyref") or "")[:50]))
    print()
    root = unwrap_to_root()
    print("  unwrap_to_root: {} bytes (correct = 32)".format(len(root)))
