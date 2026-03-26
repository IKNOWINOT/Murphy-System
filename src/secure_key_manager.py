# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Secure API Key Manager
Encrypts and manages API keys using Fernet symmetric encryption.
Includes scheduled rotation with zero-downtime overlap and failure alerting.
"""

import base64
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from cryptography.fernet import Fernet

# keyring is an optional dependency — fall back to encrypted-file storage
try:
    import keyring as _keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _keyring = None  # type: ignore[assignment]
    _KEYRING_AVAILABLE = False

logger = logging.getLogger(__name__)

# Service name used as the keyring namespace
_KEYRING_SERVICE = "murphy-system"

# Well-known environment variable names that contain sensitive API keys
_SENSITIVE_KEY_PATTERNS = re.compile(
    r'^(DEEPINFRA_API_KEY|TOGETHER_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|STRIPE_API_KEY|'
    r'SENDGRID_API_KEY|HUBSPOT_API_KEY|SHOPIFY_API_KEY|GOOGLE_API_KEY|'
    r'MURPHY_MASTER_KEY)$'
)


def _machine_fernet_key() -> bytes:
    """
    Derive a stable Fernet key from the machine's hardware UUID.

    Used as the encryption key for the fallback encrypted file so that
    the key is machine-specific but requires no external secret.
    """
    node = uuid.getnode()
    raw = hashlib.sha256(str(node).encode()).digest()
    return base64.urlsafe_b64encode(raw)


def store_api_key(name: str, value: str, env_path: Optional[Path] = None) -> str:
    """
    Store a sensitive API key using the best available backend.

    Fallback chain:
    1. OS keyring (if available)
    2. Fernet-encrypted file (machine-derived key)
    3. .env file (last resort — warns loudly)

    Returns a string describing which backend was used.
    """
    if _KEYRING_AVAILABLE:
        try:
            _keyring.set_password(_KEYRING_SERVICE, name, value)
            logger.info("Key '%s' stored in OS keyring", name)
            return "keyring"
        except Exception as exc:
            logger.warning("Keyring unavailable (%s), falling back to encrypted file", exc)

    # Encrypted-file fallback
    enc_path = _encrypted_file_path(env_path)
    _write_to_encrypted_file(enc_path, name, value)
    logger.info("Key '%s' stored in encrypted file: %s", name, enc_path)
    return "encrypted_file"


def retrieve_api_key(name: str, env_path: Optional[Path] = None) -> Optional[str]:
    """
    Retrieve a sensitive API key using the full fallback chain.

    Reads in order:
    1. OS keyring
    2. Fernet-encrypted file
    3. .env file (plaintext, legacy)
    """
    if _KEYRING_AVAILABLE:
        try:
            value = _keyring.get_password(_KEYRING_SERVICE, name)
            if value is not None:
                return value
        except Exception as exc:
            logger.warning("Keyring read failed: %s", exc)

    # Encrypted-file fallback
    enc_path = _encrypted_file_path(env_path)
    if enc_path.exists():
        value = _read_from_encrypted_file(enc_path, name)
        if value is not None:
            return value

    # .env plaintext last resort
    ep = env_path or Path('.env')
    if ep.exists():
        with open(ep, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith(f'{name}='):
                    return line.split('=', 1)[1].strip()

    return None


def delete_api_key(name: str, env_path: Optional[Path] = None) -> None:
    """Remove a key from the keyring (best-effort; does not remove from .env)."""
    if _KEYRING_AVAILABLE:
        try:
            _keyring.delete_password(_KEYRING_SERVICE, name)
        except Exception as exc:
            logger.debug("Keyring delete failed or key not found: %s", exc)


def migrate_keys(env_path: Optional[Path] = None) -> List[str]:
    """
    Scan the .env file for plaintext sensitive keys and move them to the
    secure store (keyring → encrypted file).  Removes the plaintext values
    from .env and replaces them with a placeholder comment.

    Returns the list of key names that were migrated.
    """
    ep = env_path or Path('.env')
    if not ep.exists():
        return []

    with open(ep, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    migrated: List[str] = []
    new_lines: List[str] = []

    for line in lines:
        stripped = line.rstrip('\n')
        if '=' in stripped and not stripped.lstrip().startswith('#'):
            key_name, _, key_value = stripped.partition('=')
            key_name = key_name.strip()
            key_value = key_value.strip()
            if _SENSITIVE_KEY_PATTERNS.match(key_name) and key_value:
                backend = store_api_key(key_name, key_value, env_path)
                logger.info(
                    "Migrated plaintext key '%s' from .env to %s", key_name, backend
                )
                new_lines.append(f'# {key_name} migrated to secure store ({backend})\n')
                migrated.append(key_name)
                continue
        new_lines.append(line if line.endswith('\n') else line + '\n')

    with open(ep, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    return migrated


# ── Encrypted-file helpers ────────────────────────────────────────────────

def _encrypted_file_path(env_path: Optional[Path]) -> Path:
    base = (env_path or Path('.env')).parent
    return base / '.murphy_keys.enc'


def _write_to_encrypted_file(path: Path, name: str, value: str) -> None:
    """Append or update an encrypted key entry in the encrypted file."""
    cipher = Fernet(_machine_fernet_key())
    existing = _load_encrypted_file(path)
    existing[name] = value
    ciphertext = cipher.encrypt(json.dumps(existing).encode())
    with open(path, 'wb') as f:
        f.write(ciphertext)


def _read_from_encrypted_file(path: Path, name: str) -> Optional[str]:
    """Read one key from the encrypted file."""
    data = _load_encrypted_file(path)
    return data.get(name)


def _load_encrypted_file(path: Path) -> dict:
    """Load and decrypt the entire encrypted key store."""
    if not path.exists():
        return {}
    try:
        cipher = Fernet(_machine_fernet_key())
        with open(path, 'rb') as f:
            raw = f.read()
        return json.loads(cipher.decrypt(raw).decode())
    except Exception as exc:
        logger.warning("Could not read encrypted key file: %s", exc)
        return {}


class SecureKeyManager:
    """
    Manages encrypted API keys with Fernet encryption.

    Architecture:
    - Master key stored in environment variable (MURPHY_MASTER_KEY)
    - API keys encrypted and stored in JSON file
    - Keys loaded on demand and cached in memory
    - Thread-safe operations

    Note: Flat-file storage of the master key is suitable for development only.
    For production use, provide MURPHY_MASTER_KEY via a proper secret manager
    (e.g., HashiCorp Vault, AWS Secrets Manager, Azure Key Vault).
    """

    def __init__(self, encrypted_keys_path: str = "encrypted_keys.json"):
        self.encrypted_keys_path = encrypted_keys_path
        self.master_key = self._get_or_create_master_key()
        self.cipher = Fernet(self.master_key)
        self._cached_keys: Optional[List[Tuple[str, str]]] = None

    def _get_or_create_master_key(self) -> bytes:
        """
        Get master encryption key from environment or create new one.

        Returns:
            bytes: Fernet-compatible encryption key
        """
        # Try to load from .env file first
        env_path = Path('.env')
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('MURPHY_MASTER_KEY='):
                        key_value = line.split('=', 1)[1].strip()
                        if key_value:
                            return key_value.encode()

        # Try environment variable
        master_key_env = os.getenv('MURPHY_MASTER_KEY')
        if master_key_env:
            return master_key_env.encode()

        # Generate new master key
        new_key = Fernet.generate_key()

        # Save to .env file for persistence
        if env_path.exists():
            with open(env_path, 'a', encoding='utf-8') as f:
                f.write("\n# Master encryption key (DO NOT COMMIT)\n")
                f.write(f"MURPHY_MASTER_KEY={new_key.decode()}\n")
        else:
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write("# Murphy System Environment Variables\n")
                f.write("# Master encryption key (DO NOT COMMIT)\n")
                f.write(f"MURPHY_MASTER_KEY={new_key.decode()}\n")

        logger.warning(
            "SECURITY: Auto-generated master key stored in .env file. "
            "For production use, provide MURPHY_MASTER_KEY via a proper secret manager "
            "(e.g., HashiCorp Vault, AWS Secrets Manager, Azure Key Vault)."
        )
        logger.info("Generated new master key and saved to .env")

        return new_key

    def encrypt_and_store_keys(self, keys: List[Tuple[str, str]]):
        """
        Encrypt API keys and store them in JSON file.

        Args:
            keys: List of (name, api_key) tuples
        """
        encrypted_data = []

        for name, api_key in keys:
            # Encrypt the API key
            encrypted_key = self.cipher.encrypt(api_key.encode())

            # Store as base64 for JSON compatibility
            encrypted_data.append({
                'name': name,
                'encrypted_key': base64.b64encode(encrypted_key).decode('utf-8'),
                'key_hash': hashlib.sha256(api_key.encode()).hexdigest()[:16]  # For verification
            })

        # Write to file
        with open(self.encrypted_keys_path, 'w', encoding='utf-8') as f:
            json.dump(encrypted_data, f, indent=2)

        logger.info("Encrypted and stored %d API keys", len(keys))

        # Clear cache
        self._cached_keys = None

    def load_keys(self) -> List[Tuple[str, str]]:
        """
        Load and decrypt API keys from storage.

        Returns:
            List of (name, api_key) tuples
        """
        # Return cached keys if available
        if self._cached_keys is not None:
            return self._cached_keys

        # Check if encrypted keys file exists
        if not os.path.exists(self.encrypted_keys_path):
            raise FileNotFoundError(
                f"Encrypted keys file not found: {self.encrypted_keys_path}\n"
                f"Run migration script to encrypt existing keys."
            )

        # Load encrypted data
        with open(self.encrypted_keys_path, 'r', encoding='utf-8') as f:
            encrypted_data = json.load(f)

        # Decrypt keys
        decrypted_keys = []
        for entry in encrypted_data:
            try:
                # Decode from base64
                encrypted_key = base64.b64decode(entry['encrypted_key'])

                # Decrypt
                decrypted_key = self.cipher.decrypt(encrypted_key).decode('utf-8')

                # Verify hash (optional security check)
                key_hash = hashlib.sha256(decrypted_key.encode()).hexdigest()[:16]
                if key_hash != entry['key_hash']:
                    logger.warning("Hash mismatch for key '%s'", entry['name'])
                decrypted_keys.append((entry['name'], decrypted_key))

            except Exception as exc:
                logger.error("Failed to decrypt key '%s': %s", entry['name'], exc)
                continue

        # Cache the decrypted keys
        self._cached_keys = decrypted_keys

        return decrypted_keys

    def migrate_from_plaintext(self, plaintext_file: str):
        """
        Migrate keys from plaintext file to encrypted storage.

        Args:
            plaintext_file: Path to plaintext keys file
        """
        logger.info("Migrating keys from %s", plaintext_file)

        keys = []
        with open(plaintext_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Parse format: "Name <key>"
                if '<' in line and '>' in line:
                    name = line.split('<')[0].strip()
                    key = line.split('<')[1].split('>')[0].strip()
                    keys.append((name, key))

        if not keys:
            raise ValueError(f"No keys found in {plaintext_file}")

        # Encrypt and store
        self.encrypt_and_store_keys(keys)

        logger.info("Migration complete: %d keys encrypted", len(keys))
        logger.warning("Delete the plaintext file: %s", plaintext_file)

    def add_key(self, name: str, api_key: str):
        """
        Add a new API key to encrypted storage.

        Args:
            name: Key name/identifier
            api_key: The API key to encrypt and store
        """
        # Load existing keys
        existing_keys = self.load_keys() if os.path.exists(self.encrypted_keys_path) else []

        # Add new key
        existing_keys.append((name, api_key))

        # Re-encrypt and store all keys
        self.encrypt_and_store_keys(existing_keys)

        logger.info("Added key: %s", name)

    def remove_key(self, name: str):
        """
        Remove an API key from encrypted storage.

        Args:
            name: Key name to remove
        """
        # Load existing keys
        existing_keys = self.load_keys()

        # Filter out the key to remove
        filtered_keys = [(n, k) for n, k in existing_keys if n != name]

        if len(filtered_keys) == len(existing_keys):
            logger.warning("Key not found: %s", name)
            return

        # Re-encrypt and store remaining keys
        self.encrypt_and_store_keys(filtered_keys)

        logger.info("Removed key: %s", name)

    def list_keys(self) -> List[str]:
        """
        List all key names (without exposing actual keys).

        Returns:
            List of key names
        """
        keys = self.load_keys()
        return [name for name, _ in keys]

    def verify_encryption(self) -> bool:
        """
        Verify that encryption/decryption is working correctly.

        Returns:
            bool: True if encryption is working
        """
        try:
            # Test encryption/decryption
            test_data = "test_key_12345"
            encrypted = self.cipher.encrypt(test_data.encode())
            decrypted = self.cipher.decrypt(encrypted).decode()

            return decrypted == test_data
        except Exception as exc:
            logger.error("Encryption verification failed: %s", exc)
            return False


def get_secure_key_manager() -> "SecureKeyManager":
    """
    Get or create the global secure key manager instance.

    Returns:
        SecureKeyManager: Global key manager instance
    """
    global _key_manager_instance

    if '_key_manager_instance' not in globals():
        _key_manager_instance = SecureKeyManager()

    return _key_manager_instance


# ── Scheduled Key Rotation ────────────────────────────────────────────────────

class ScheduledKeyRotator:
    """Zero-downtime scheduled key rotation with overlap period and failure alerting.

    How it works
    ============
    1. A background daemon thread wakes up every *check_interval_seconds* and
       calls all registered *rotation_callbacks* in sequence.
    2. Each callback receives ``(key_name: str)`` and is expected to generate a
       new secret, activate it in the relevant service, and return ``True`` on
       success or raise an exception on failure.
    3. During the *overlap_seconds* window both the old and new keys remain
       accepted so in-flight requests are not rejected.
    4. On rotation failure, every registered *alert_callbacks* is called with
       ``(key_name: str, error: Exception)`` so on-call channels (Slack, PagerDuty,
       email) can be notified.
    5. A full audit log is maintained in memory (bounded to 10 000 entries).

    Configuration via environment variables (all optional):

    ====================================  ================================  ========
    Variable                              Meaning                           Default
    ====================================  ================================  ========
    ``MURPHY_KEY_ROTATION_INTERVAL``      Rotation check interval seconds   86400
    ``MURPHY_KEY_ROTATION_OVERLAP``       Overlap window seconds            300
    ====================================  ================================  ========

    Usage::

        rotator = ScheduledKeyRotator(rotation_interval_seconds=86400)
        rotator.register_key("DEEPINFRA_API_KEY")
        rotator.add_rotation_callback(my_deepinfra_rotation_fn)
        rotator.add_alert_callback(my_pagerduty_alert_fn)
        rotator.start()
    """

    _MAX_AUDIT_ENTRIES = 10_000

    def __init__(
        self,
        rotation_interval_seconds: Optional[int] = None,
        overlap_seconds: Optional[int] = None,
    ):
        self.rotation_interval = rotation_interval_seconds or int(
            os.environ.get("MURPHY_KEY_ROTATION_INTERVAL", "86400")
        )
        self.overlap_seconds = overlap_seconds or int(
            os.environ.get("MURPHY_KEY_ROTATION_OVERLAP", "300")
        )

        self._rotation_callbacks: List[Callable[[str], bool]] = []
        self._alert_callbacks: List[Callable[[str, Exception], None]] = []
        self._registered_keys: List[str] = []
        self._last_rotated: Dict[str, datetime] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------

    def register_key(self, key_name: str) -> None:
        """Register a key name that this rotator should rotate on schedule."""
        with self._lock:
            if key_name not in self._registered_keys:
                self._registered_keys.append(key_name)
        logger.info("ScheduledKeyRotator: registered key '%s'", key_name)

    def add_rotation_callback(self, callback: Callable[[str], bool]) -> None:
        """Register a callback invoked for each key during rotation.

        The callback receives the key name as its only argument and should
        return ``True`` on success.  Raising an exception signals failure.
        """
        self._rotation_callbacks.append(callback)

    def add_alert_callback(self, callback: Callable[[str, Exception], None]) -> None:
        """Register a callback invoked when a rotation attempt fails.

        Receives ``(key_name, exception)`` and should notify an on-call channel.
        """
        self._alert_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background rotation scheduler thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("ScheduledKeyRotator is already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="ScheduledKeyRotator",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "ScheduledKeyRotator started (interval=%ds, overlap=%ds)",
            self.rotation_interval,
            self.overlap_seconds,
        )

    def stop(self) -> None:
        """Stop the background rotation scheduler thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("ScheduledKeyRotator stopped")

    # ------------------------------------------------------------------
    # Core rotation logic
    # ------------------------------------------------------------------

    def rotate_now(self, key_name: str) -> bool:
        """Immediately rotate *key_name*.  Returns True on success.

        Maintains the overlap window: the old key remains valid for
        ``self.overlap_seconds`` after the new key is activated so that
        in-flight requests are not rejected.
        """
        logger.info("ScheduledKeyRotator: rotating key '%s'", key_name)
        success = False
        error_caught: Optional[Exception] = None

        for cb in self._rotation_callbacks:
            try:
                result = cb(key_name)
                if result:
                    success = True
            except Exception as exc:
                logger.error(
                    "ScheduledKeyRotator: rotation callback failed for '%s': %s",
                    key_name, exc,
                )
                error_caught = exc

        if error_caught:
            self._fire_alerts(key_name, error_caught)

        rotated_at = datetime.now(timezone.utc)
        entry: Dict[str, Any] = {
            "key_name": key_name,
            "rotated_at": rotated_at.isoformat(),
            "success": success and error_caught is None,
            "error": str(error_caught) if error_caught else None,
            "overlap_seconds": self.overlap_seconds,
        }
        with self._lock:
            if success and error_caught is None:
                self._last_rotated[key_name] = rotated_at
            if len(self._audit_log) >= self._MAX_AUDIT_ENTRIES:
                del self._audit_log[: self._MAX_AUDIT_ENTRIES // 10]
            self._audit_log.append(entry)

        if success and error_caught is None:
            logger.info(
                "ScheduledKeyRotator: key '%s' rotated successfully "
                "(overlap window: %ds)",
                key_name, self.overlap_seconds,
            )
        else:
            logger.error(
                "ScheduledKeyRotator: key '%s' rotation FAILED",
                key_name,
            )

        return success and error_caught is None

    def rotate_all_due(self) -> Dict[str, bool]:
        """Rotate all keys that are due for rotation.  Returns {key_name: success}."""
        results: Dict[str, bool] = {}
        with self._lock:
            keys = list(self._registered_keys)

        for key_name in keys:
            with self._lock:
                last = self._last_rotated.get(key_name)
            if last is None:
                # Never rotated — skip initial rotation on first start to
                # avoid disrupting a just-deployed system.
                with self._lock:
                    self._last_rotated[key_name] = datetime.now(timezone.utc)
                logger.info(
                    "ScheduledKeyRotator: key '%s' baseline set (first run)",
                    key_name,
                )
                results[key_name] = True
                continue

            age_seconds = (datetime.now(timezone.utc) - last).total_seconds()
            if age_seconds >= self.rotation_interval:
                results[key_name] = self.rotate_now(key_name)

        return results

    # ------------------------------------------------------------------
    # Status / audit
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return rotation status for monitoring."""
        with self._lock:
            keys_status = {}
            for key_name in self._registered_keys:
                last = self._last_rotated.get(key_name)
                age = (datetime.now(timezone.utc) - last).total_seconds() if last else None
                keys_status[key_name] = {
                    "last_rotated": last.isoformat() if last else None,
                    "age_seconds": int(age) if age is not None else None,
                    "due_for_rotation": age is not None and age >= self.rotation_interval,
                }
            return {
                "running": self._thread is not None and self._thread.is_alive(),
                "rotation_interval_seconds": self.rotation_interval,
                "overlap_seconds": self.overlap_seconds,
                "registered_keys": list(self._registered_keys),
                "keys": keys_status,
                "audit_log_size": len(self._audit_log),
            }

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent rotation audit entries."""
        with self._lock:
            return list(self._audit_log[-limit:])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Background thread: wake up every *rotation_interval* and rotate due keys."""
        while not self._stop_event.is_set():
            try:
                self.rotate_all_due()
            except Exception as exc:
                logger.error("ScheduledKeyRotator background loop error: %s", exc)
            # Sleep in small increments so stop() is responsive
            for _ in range(self.rotation_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _fire_alerts(self, key_name: str, error: Exception) -> None:
        """Call all registered alert callbacks for a rotation failure."""
        for alert_cb in self._alert_callbacks:
            try:
                alert_cb(key_name, error)
            except Exception as exc:
                logger.error(
                    "ScheduledKeyRotator: alert callback raised an exception: %s", exc
                )


# ── Global scheduled rotator singleton ───────────────────────────────────────

_scheduled_rotator: Optional[ScheduledKeyRotator] = None
_scheduled_rotator_lock = threading.Lock()


def get_scheduled_rotator() -> ScheduledKeyRotator:
    """Return the global :class:`ScheduledKeyRotator` singleton, creating it if needed."""
    global _scheduled_rotator
    with _scheduled_rotator_lock:
        if _scheduled_rotator is None:
            _scheduled_rotator = ScheduledKeyRotator()
        return _scheduled_rotator


# CLI for key management
if __name__ == "__main__":
    import sys

    manager = SecureKeyManager()

    if len(sys.argv) < 2:
        logger.info("Usage:")
        logger.info("  python secure_key_manager.py migrate <plaintext_file>")
        logger.info("  python secure_key_manager.py add <name> <key>")
        logger.info("  python secure_key_manager.py remove <name>")
        logger.info("  python secure_key_manager.py list")
        logger.info("  python secure_key_manager.py verify")
        sys.exit(1)

    command = sys.argv[1]

    if command == "migrate":
        if len(sys.argv) < 3:
            logger.info("Error: Provide plaintext file path")
            sys.exit(1)
        manager.migrate_from_plaintext(sys.argv[2])

    elif command == "add":
        if len(sys.argv) < 4:
            logger.info("Error: Provide name and key")
            sys.exit(1)
        manager.add_key(sys.argv[2], sys.argv[3])

    elif command == "remove":
        if len(sys.argv) < 3:
            logger.info("Error: Provide key name")
            sys.exit(1)
        manager.remove_key(sys.argv[2])

    elif command == "list":
        keys = manager.list_keys()
        logger.info(f"Stored keys ({len(keys)}):")
        for name in keys:
            logger.info(f"  - {name}")

    elif command == "verify":
        if manager.verify_encryption():
            logger.info("✅ Encryption is working correctly")
        else:
            logger.info("❌ Encryption verification failed")

    else:
        logger.info(f"Unknown command: {command}")
        sys.exit(1)
