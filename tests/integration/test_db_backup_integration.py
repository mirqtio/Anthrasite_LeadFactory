"""
Integration tests for database backup service.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from leadfactory.services.db_backup_service import BackupError, DatabaseBackupService


class TestDatabaseBackupIntegration:
    """Integration tests for database backup service."""

    @pytest.fixture
    def temp_backup_dir(self):
        """Create temporary backup directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def backup_service(self, temp_backup_dir):
        """Create backup service for integration testing."""
        config = {
            "backup_dir": temp_backup_dir,
            "retention_days": 7,
            "compression": "gzip",
            "encryption": False,
            "remote_storage": {"enabled": False},
            "notifications": {"enabled": False},
            "monitoring": {
                "track_costs": True,
                "cost_per_gb": 0.02,
            }
        }

        with patch.object(DatabaseBackupService, "_load_config", return_value=config):
            service = DatabaseBackupService()
            return service

    def test_full_backup_workflow_with_mocked_database(self, backup_service):
        """Test complete backup workflow with mocked database operations."""
        # Mock database connection
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test_db"
        }):
            # Mock pg_dump subprocess call
            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value.returncode = 0
                mock_subprocess.return_value.stderr = ""

                # Mock backup file creation
                backup_file = backup_service.backup_dir / "test_backup.sql"
                backup_file.write_text("-- Test backup content\nSELECT 1;")

                with patch("pathlib.Path.exists", return_value=True):
                    with patch("pathlib.Path.stat") as mock_stat:
                        mock_stat.return_value.st_size = len("-- Test backup content\nSELECT 1;")

                        # Mock gzip compression
                        with patch("gzip.open"):
                            with patch("shutil.copyfileobj"):
                                # Mock compressed file
                                compressed_file = backup_service.backup_dir / "test_backup.sql.gz"
                                compressed_file.write_bytes(b"compressed content")

                                with patch("pathlib.Path.unlink"):  # Mock removing original file
                                    # Mock cleanup to avoid directory issues
                                    with patch.object(backup_service, "_cleanup_old_backups"):
                                        result = backup_service.create_backup("test_backup")

                                    assert result["backup_name"] == "test_backup"
                                    assert result["compression"] == "gzip"
                                    assert result["backup_file"].endswith(".gz")

                                    # Verify metrics were updated
                                    assert backup_service.metrics["backups_completed"] == 1
                                    assert backup_service.metrics["last_backup_time"] is not None

    def test_backup_with_cost_tracking(self, backup_service):
        """Test that backup costs are tracked when enabled."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test_db"
        }):
            with patch("leadfactory.services.db_backup_service.cost_tracker") as mock_tracker:
                # Mock successful backup creation
                with patch.object(backup_service, "_create_postgresql_backup") as mock_create:
                    mock_create.return_value = {
                        "backup_name": "cost_test",
                        "backup_file": "/tmp/test.sql",
                        "file_size": 1024 * 1024 * 100,  # 100 MB
                        "file_size_mb": 100,
                        "created_at": "2024-01-01T12:00:00",
                        "include_data": True,
                        "include_schema": True,
                        "compression": None,
                        "encrypted": False,
                    }

                    with patch.object(backup_service, "_post_process_backup") as mock_process:
                        mock_process.return_value = mock_create.return_value

                        backup_service.create_backup("cost_test")

                        # Verify cost was tracked
                        mock_tracker.add_cost.assert_called_once()
                        cost_call = mock_tracker.add_cost.call_args

                        # Should track cost based on file size
                        expected_cost = (100 / 1024) * 0.02  # 100MB in GB * $0.02/GB
                        assert cost_call[1]["amount"] == expected_cost
                        assert cost_call[1]["service"] == "backup"
                        assert cost_call[1]["operation"] == "database_backup"

    def test_backup_list_and_cleanup_integration(self, backup_service):
        """Test backup listing and cleanup functionality together."""
        # Create several test backup files with different ages
        import time
        from datetime import timedelta

        backup_files = [
            ("leadfactory_20240101_120000.sql.gz", "old backup 1"),
            ("leadfactory_20240102_120000.sql", "old backup 2"),
            ("leadfactory_20240115_120000.sql.gz", "recent backup 1"),
            ("leadfactory_20240116_120000.sql", "recent backup 2"),
        ]

        for filename, content in backup_files:
            backup_file = backup_service.backup_dir / filename
            backup_file.write_text(content)

            # Make first two files old
            if "20240101" in filename or "20240102" in filename:
                old_time = time.time() - (backup_service.retention_days + 1) * 24 * 3600
                os.utime(backup_file, (old_time, old_time))

        # List backups before cleanup
        backups_before = backup_service.list_backups()
        assert len(backups_before) == 4

        # Run cleanup
        backup_service._cleanup_old_backups()

        # List backups after cleanup
        backups_after = backup_service.list_backups()
        assert len(backups_after) == 2

        # Verify only recent backups remain
        remaining_names = [b["name"] for b in backups_after]
        assert all("20240115" in name or "20240116" in name for name in remaining_names)

    def test_backup_service_status_integration(self, backup_service):
        """Test complete status reporting integration."""
        # Create some test backups
        test_files = [
            "leadfactory_20240101_120000.sql.gz",
            "leadfactory_20240102_120000.sql"
        ]

        for filename in test_files:
            backup_file = backup_service.backup_dir / filename
            backup_file.write_text(f"Test content for {filename}")

        # Update metrics to simulate activity
        backup_service.metrics.update({
            "backups_completed": 10,
            "backups_failed": 1,
            "total_backup_size": 1024 * 1024 * 50,  # 50 MB
            "last_backup_time": "2024-01-15T12:00:00",
            "last_backup_duration": 120.5,
        })

        # Get comprehensive status
        status = backup_service.get_backup_status()

        # Verify status structure and content
        assert status["service_status"] == "running"
        assert status["total_backups"] == 2
        assert status["backup_directory"] == str(backup_service.backup_dir)
        assert status["retention_days"] == 7

        # Check metrics
        metrics = status["metrics"]
        assert metrics["backups_completed"] == 10
        assert metrics["backups_failed"] == 1
        assert metrics["total_backup_size"] == 1024 * 1024 * 50

        # Check configuration
        config = status["config"]
        assert config["compression"] == "gzip"
        assert config["encryption"] is False
        assert config["remote_storage_enabled"] is False

        # Check latest backup info
        latest = status["latest_backup"]
        assert latest is not None
        assert "leadfactory_" in latest["name"]

    def test_error_handling_and_metrics_integration(self, backup_service):
        """Test error handling and failure metric tracking."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@nonexistent:5432/test_db"
        }):
            # Mock pg_dump failure
            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.side_effect = subprocess.CalledProcessError(
                    1, "pg_dump", stderr="Connection refused"
                )

                initial_failures = backup_service.metrics["backups_failed"]

                # Attempt backup (should fail)
                with pytest.raises(BackupError):
                    backup_service.create_backup("failure_test")

                # Verify failure was tracked
                assert backup_service.metrics["backups_failed"] == initial_failures + 1

                # Verify successful backups counter wasn't incremented
                assert backup_service.metrics["backups_completed"] == 0

    @patch("subprocess.run")
    def test_restore_integration(self, mock_subprocess, backup_service):
        """Test backup restore functionality integration."""
        # Create a test backup file
        backup_file = backup_service.backup_dir / "restore_test.sql.gz"

        # Mock compressed backup content
        import gzip
        test_sql = "CREATE TABLE test (id INTEGER); INSERT INTO test VALUES (1);"
        with gzip.open(backup_file, "wt") as f:
            f.write(test_sql)

        # Mock successful psql execution
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stderr = ""

        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test_db"
        }):
            result = backup_service.restore_backup("restore_test")

            assert result["backup_name"] == "restore_test"
            assert result["target_database"] == "test_db"
            assert result["success"] is True

            # Verify psql was called with correct parameters
            mock_subprocess.assert_called_once()
            cmd = mock_subprocess.call_args[0][0]
            assert "psql" in cmd
            assert "-f" in cmd

    def test_configuration_loading_integration(self, temp_backup_dir):
        """Test configuration loading from file and environment."""
        # Create a test config file
        config_file = Path(temp_backup_dir) / "backup_config.yml"
        custom_backup_dir = Path(temp_backup_dir) / "custom_backup"
        config_content = f"""
backup:
  backup_dir: {custom_backup_dir}
  retention_days: 14
  compression: none
  encryption: true
  remote_storage:
    enabled: true
    type: s3
    config:
      bucket: my-backup-bucket
  notifications:
    enabled: true
    email: admin@example.com
  monitoring:
    track_costs: true
    cost_per_gb: 0.05
"""
        config_file.write_text(config_content)

        # Load service with config file
        service = DatabaseBackupService(config_path=str(config_file))

        # Verify configuration was loaded correctly
        assert service.config["retention_days"] == 14
        assert service.config["compression"] == "none"
        assert service.config["encryption"] is True
        assert service.config["remote_storage"]["enabled"] is True
        assert service.config["remote_storage"]["type"] == "s3"
        assert service.config["notifications"]["email"] == "admin@example.com"
        assert service.config["monitoring"]["cost_per_gb"] == 0.05
        assert str(service.backup_dir) == str(custom_backup_dir)


# Import required modules for mocking
import subprocess

if __name__ == "__main__":
    pytest.main([__file__])
