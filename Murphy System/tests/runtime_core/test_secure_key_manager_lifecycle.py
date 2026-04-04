"""
Tests: Secure Key Manager — Lifecycle & No-Stdout-Leak

Proves that:
1. Encrypt → store → load → decrypt round-trip works correctly
2. Key add / remove / list operations function
3. No sensitive material is printed to stdout (CWE-532)
4. verify_encryption self-check passes

Bug Label  : CWE-532 — Insertion of Sensitive Information into Log File
Module     : src/secure_key_manager.py
"""

import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Ensure a master key is available so the manager doesn't try to create .env
os.environ.setdefault(
    "MURPHY_MASTER_KEY",
    "VGVzdEtleUZvclVuaXRUZXN0c0FBQUFBQUFBQUE9"  # will be overridden below
)

from cryptography.fernet import Fernet

# Generate a valid Fernet key for all tests
_TEST_KEY = Fernet.generate_key().decode()
os.environ["MURPHY_MASTER_KEY"] = _TEST_KEY

from secure_key_manager import SecureKeyManager


class TestEncryptDecryptRoundTrip(unittest.TestCase):
    """encrypt_and_store_keys → load_keys must return identical data."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.keys_path = os.path.join(self.tmpdir, "keys.json")
        self.mgr = SecureKeyManager(encrypted_keys_path=self.keys_path)

    def test_round_trip(self):
        original = [("openai", "sk-abc123"), ("anthropic", "sk-xyz789")]
        self.mgr.encrypt_and_store_keys(original)
        loaded = self.mgr.load_keys()
        self.assertEqual(loaded, original)

    def test_stored_file_is_encrypted(self):
        """The JSON file must NOT contain the plaintext key."""
        self.mgr.encrypt_and_store_keys([("secret", "my-super-secret-key")])
        with open(self.keys_path) as f:
            raw = f.read()
        self.assertNotIn("my-super-secret-key", raw)

    def test_verify_encryption(self):
        self.assertTrue(self.mgr.verify_encryption())


class TestAddRemoveList(unittest.TestCase):
    """Key lifecycle: add, list, remove."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.keys_path = os.path.join(self.tmpdir, "keys.json")
        self.mgr = SecureKeyManager(encrypted_keys_path=self.keys_path)
        self.mgr.encrypt_and_store_keys([("initial", "k1")])

    def test_add_key(self):
        self.mgr.add_key("new_key", "k2")
        names = self.mgr.list_keys()
        self.assertIn("initial", names)
        self.assertIn("new_key", names)

    def test_remove_key(self):
        self.mgr.remove_key("initial")
        names = self.mgr.list_keys()
        self.assertNotIn("initial", names)

    def test_remove_nonexistent_key(self):
        """Removing a key that doesn't exist should not raise."""
        self.mgr.remove_key("ghost")
        names = self.mgr.list_keys()
        self.assertIn("initial", names)


class TestNoStdoutLeak(unittest.TestCase):
    """No print() calls should leak sensitive information to stdout (CWE-532)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.keys_path = os.path.join(self.tmpdir, "keys.json")
        self.mgr = SecureKeyManager(encrypted_keys_path=self.keys_path)

    def test_encrypt_store_no_stdout(self):
        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            self.mgr.encrypt_and_store_keys([("a", "secret123")])
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        self.assertNotIn("secret123", output)
        # Should not contain the old emoji-print patterns
        self.assertNotIn("✅", output)

    def test_add_key_no_stdout(self):
        self.mgr.encrypt_and_store_keys([("x", "y")])
        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            self.mgr.add_key("new", "newsecret")
        finally:
            sys.stdout = old_stdout
        self.assertNotIn("newsecret", captured.getvalue())
        self.assertNotIn("✅", captured.getvalue())

    def test_verify_no_stdout(self):
        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            self.mgr.verify_encryption()
        finally:
            sys.stdout = old_stdout
        self.assertEqual(captured.getvalue(), "")


class TestSourceNoPrint(unittest.TestCase):
    """The source file must not use print() for sensitive operations."""

    def test_no_print_in_class_methods(self):
        src = os.path.join(
            os.path.dirname(__file__), "..", "src", "secure_key_manager.py"
        )
        with open(src) as f:
            lines = f.readlines()

        in_class = False
        for lineno, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("class SecureKeyManager"):
                in_class = True
                continue
            if in_class and not line.startswith(" ") and not line.strip() == "":
                in_class = False
            if in_class and "print(" in stripped and not stripped.startswith("#"):
                self.fail(
                    f"print() found in SecureKeyManager class body at line {lineno}: "
                    f"{stripped!r}"
                )


if __name__ == "__main__":
    unittest.main()
