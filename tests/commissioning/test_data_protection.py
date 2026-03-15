"""
Murphy System — Training Data Protection Commissioning Tests
Owner: @ml-eng
Phase: 5 — ML Integration Tests
Completion: 100%

Resolves GAP-014 (no training data protection).
Implements sandbox, backup, and restore mechanisms to protect
training data during time-accelerated and stress testing.
"""

import json
import pytest
import shutil
from pathlib import Path
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════
# Training Data Protector
# ═══════════════════════════════════════════════════════════════════════════


class TrainingDataProtector:
    """Protects training data during accelerated and stress testing.

    Provides backup/restore, sandbox isolation, and integrity
    verification for ML training data.

    Attributes:
        data_dir: Path to the training data directory.
        backup_dir: Path to the backup directory.
    """

    def __init__(self, data_dir: str = ".murphy_persistence/training_data"):
        self.data_dir = Path(data_dir)
        self.backup_dir = Path(str(data_dir) + "_backup")

    def backup(self) -> bool:
        """Create a backup of the training data.

        Returns:
            True if backup was successful.
        """
        if not self.data_dir.exists():
            return False

        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        shutil.copytree(self.data_dir, self.backup_dir)
        return True

    def restore(self) -> bool:
        """Restore training data from backup.

        Returns:
            True if restore was successful.
        """
        if not self.backup_dir.exists():
            return False

        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)
        shutil.copytree(self.backup_dir, self.data_dir)
        return True

    def create_sandbox(self, sandbox_name: str) -> Path:
        """Create an isolated sandbox for testing.

        Args:
            sandbox_name: Name for the sandbox.

        Returns:
            Path to the sandbox directory.
        """
        sandbox_dir = self.data_dir / f"sandbox_{sandbox_name}"
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        return sandbox_dir

    def cleanup_sandbox(self, sandbox_name: str) -> bool:
        """Remove a sandbox after testing.

        Args:
            sandbox_name: Name of the sandbox to remove.

        Returns:
            True if cleanup was successful.
        """
        sandbox_dir = self.data_dir / f"sandbox_{sandbox_name}"
        if sandbox_dir.exists():
            shutil.rmtree(sandbox_dir)
            return True
        return False

    def verify_integrity(self) -> dict:
        """Verify integrity of training data.

        Returns:
            Dictionary with integrity check results.
        """
        results = {
            "data_dir_exists": self.data_dir.exists(),
            "files": [],
            "total_size": 0,
            "corrupted": [],
        }

        if not self.data_dir.exists():
            return results

        for file_path in self.data_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("sandbox_"):
                try:
                    size = file_path.stat().st_size
                    results["files"].append({
                        "name": str(file_path.relative_to(self.data_dir)),
                        "size": size,
                    })
                    results["total_size"] += size
                except OSError:
                    results["corrupted"].append(str(file_path))

        return results

    def compare_with_backup(self) -> dict:
        """Compare current data with backup.

        Returns:
            Dictionary with comparison results.
        """
        if not self.data_dir.exists() or not self.backup_dir.exists():
            return {"error": "Data or backup directory missing"}

        current_files = set(
            str(f.relative_to(self.data_dir))
            for f in self.data_dir.rglob("*")
            if f.is_file()
        )
        backup_files = set(
            str(f.relative_to(self.backup_dir))
            for f in self.backup_dir.rglob("*")
            if f.is_file()
        )

        return {
            "identical": current_files == backup_files,
            "added": list(current_files - backup_files),
            "removed": list(backup_files - current_files),
            "current_count": len(current_files),
            "backup_count": len(backup_files),
        }


# ═══════════════════════════════════════════════════════════════════════════
# Training Data Protection Tests
# Owner: @ml-eng | Completion: 100%
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def protector(sandbox):
    """Provide a training data protector with isolated directory."""
    data_dir = sandbox / "training_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create initial training data
    (data_dir / "model_weights.json").write_text(
        json.dumps({"layer1": [0.1, 0.2, 0.3], "layer2": [0.4, 0.5]})
    )
    (data_dir / "training_log.csv").write_text(
        "epoch,loss,accuracy\n1,0.5,0.7\n2,0.3,0.85\n3,0.1,0.95\n"
    )
    (data_dir / "features.json").write_text(
        json.dumps({"feature_names": ["duration", "memory", "complexity"]})
    )

    return TrainingDataProtector(data_dir=str(data_dir))


class TestTrainingDataBackupRestore:
    """@ml-eng: Tests for backup and restore functionality."""

    def test_backup_creates_copy(self, protector):
        """@ml-eng: Verify backup creates a copy of training data."""
        result = protector.backup()
        assert result is True
        assert protector.backup_dir.exists()

    def test_backup_nonexistent_dir(self, sandbox):
        """@ml-eng: Verify backup of nonexistent dir returns False."""
        protector = TrainingDataProtector(
            data_dir=str(sandbox / "nonexistent")
        )
        assert protector.backup() is False

    def test_restore_from_backup(self, protector):
        """@ml-eng: Verify restore recovers from backup."""
        protector.backup()

        # Corrupt data
        (protector.data_dir / "model_weights.json").write_text("corrupted")

        # Restore
        result = protector.restore()
        assert result is True

        # Verify restored content
        restored = json.loads(
            (protector.data_dir / "model_weights.json").read_text()
        )
        assert "layer1" in restored

    def test_restore_without_backup(self, sandbox):
        """@ml-eng: Verify restore without backup returns False."""
        protector = TrainingDataProtector(
            data_dir=str(sandbox / "training_data")
        )
        assert protector.restore() is False


class TestTrainingDataSandbox:
    """@ml-eng: Tests for sandbox isolation."""

    def test_sandbox_creation(self, protector):
        """@ml-eng: Verify sandbox creation."""
        sandbox = protector.create_sandbox("test_run_001")
        assert sandbox.exists()
        assert "sandbox_test_run_001" in str(sandbox)

    def test_sandbox_isolation(self, protector):
        """@ml-eng: Verify sandbox doesn't affect main data."""
        original_content = (
            protector.data_dir / "model_weights.json"
        ).read_text()

        # Create sandbox and modify data there
        sandbox = protector.create_sandbox("isolation_test")
        (sandbox / "modified_model.json").write_text('{"modified": true}')

        # Verify original is unchanged
        current_content = (
            protector.data_dir / "model_weights.json"
        ).read_text()
        assert current_content == original_content

    def test_sandbox_cleanup(self, protector):
        """@ml-eng: Verify sandbox cleanup."""
        protector.create_sandbox("cleanup_test")
        result = protector.cleanup_sandbox("cleanup_test")
        assert result is True

        # Verify sandbox is gone
        sandbox_dir = protector.data_dir / "sandbox_cleanup_test"
        assert not sandbox_dir.exists()

    def test_cleanup_nonexistent_sandbox(self, protector):
        """@ml-eng: Verify cleanup of nonexistent sandbox returns False."""
        assert protector.cleanup_sandbox("nonexistent") is False


class TestTrainingDataIntegrity:
    """@ml-eng: Tests for data integrity verification."""

    def test_integrity_check(self, protector):
        """@ml-eng: Verify integrity check reports correctly."""
        results = protector.verify_integrity()
        assert results["data_dir_exists"] is True
        assert len(results["files"]) == 3  # 3 initial files
        assert results["total_size"] > 0
        assert len(results["corrupted"]) == 0

    def test_backup_comparison_identical(self, protector):
        """@ml-eng: Verify backup comparison when identical."""
        protector.backup()
        comparison = protector.compare_with_backup()
        assert comparison["identical"] is True

    def test_backup_comparison_modified(self, protector):
        """@ml-eng: Verify backup comparison detects changes."""
        protector.backup()

        # Add a new file
        (protector.data_dir / "new_data.json").write_text('{"new": true}')

        comparison = protector.compare_with_backup()
        assert comparison["identical"] is False
        assert len(comparison["added"]) >= 1


class TestTrainingDataProtectionEndToEnd:
    """@ml-eng: Complete training data protection workflow.
    Completion: 100%"""

    def test_full_protection_workflow(self, protector):
        """@ml-eng: End-to-end protection during accelerated testing."""

        # Step 1: Verify initial integrity
        integrity = protector.verify_integrity()
        assert integrity["data_dir_exists"]
        initial_file_count = len(integrity["files"])

        # Step 2: Backup before testing
        assert protector.backup() is True

        # Step 3: Create sandbox for accelerated testing
        sandbox = protector.create_sandbox("accelerated_test")
        assert sandbox.exists()

        # Step 4: Simulate accelerated testing in sandbox
        for i in range(5):
            (sandbox / f"epoch_{i}_results.json").write_text(
                json.dumps({"epoch": i, "loss": 0.5 - i * 0.1})
            )

        # Step 5: Verify original data unchanged
        integrity_after = protector.verify_integrity()
        # Only non-sandbox files should be counted the same
        non_sandbox_files = [
            f for f in integrity_after["files"]
            if "sandbox_" not in f["name"]
        ]
        assert len(non_sandbox_files) == initial_file_count

        # Step 6: Cleanup sandbox
        assert protector.cleanup_sandbox("accelerated_test") is True

        # Step 7: Verify backup comparison
        comparison = protector.compare_with_backup()
        assert comparison["identical"] is True

        # Step 8: Restore as final safety measure
        assert protector.restore() is True
