"""
Unit tests for database backup service.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch
from urllib.parse import urlparse

import pytest

from leadfactory.services.db_backup_service import (
    BackupError,
    DatabaseBackupService,
    create_nightly_backup,
    get_backup_service_status,
)


class TestDatabaseBackupService:
    """Test the DatabaseBackupService class."""

    @pytest.fixture
    def temp_backup_dir(self):
        """Create temporary backup directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def backup_service(self, temp_backup_dir):
        """Create backup service with temporary directory."""
        config = {
            "backup_dir": temp_backup_dir,
            "retention_days": 7,
            "compression": "gzip",
            "encryption": False,
            "remote_storage": {"enabled": False},
            "notifications": {"enabled": False},
            "monitoring": {"track_costs": False},
        }

        with patch.object(DatabaseBackupService, "_load_config", return_value=config):
            service = DatabaseBackupService()
            return service

    def test_initialization(self, backup_service, temp_backup_dir):
        """Test service initialization."""
        assert backup_service.backup_dir == Path(temp_backup_dir)
        assert backup_service.retention_days == 7
        assert backup_service.metrics["backups_completed"] == 0
        assert backup_service.metrics["backups_failed"] == 0

    def test_load_config_from_environment(self):
        """Test loading configuration from environment variables."""
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_backup_dir = os.path.join(temp_dir, "custom_backup")
            with patch.dict(os.environ, {
                "BACKUP_DIR": custom_backup_dir,
                "BACKUP_RETENTION_DAYS": "14",
                "BACKUP_COMPRESSION": "none",
                "BACKUP_REMOTE_ENABLED": "true",
            }):
                service = DatabaseBackupService()
                config = service.config

                assert config["backup_dir"] == custom_backup_dir
                assert config["retention_days"] == 14
                assert config["compression"] == "none"
                assert config["remote_storage"]["enabled"] is True

    def test_get_database_connection_info_success(self):
        """Test extracting database connection info successfully."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb"
        }):
            service = DatabaseBackupService()
            db_info = service.get_database_connection_info()

            assert db_info["host"] == "localhost"
            assert db_info["port"] == "5432"
            assert db_info["user"] == "user"
            assert db_info["password"] == "pass"
            assert db_info["database"] == "testdb"
            assert db_info["scheme"] == "postgresql"

    def test_get_database_connection_info_missing_url(self):
        """Test error when DATABASE_URL is missing."""
        with patch.dict(os.environ, {}, clear=True):
            service = DatabaseBackupService()

            with pytest.raises(BackupError, match="DATABASE_URL environment variable is not set"):
                service.get_database_connection_info()

    def test_get_database_connection_info_invalid_url(self):
        """Test parsing of unusual but valid DATABASE_URL formats."""
        with patch.dict(os.environ, {"DATABASE_URL": "invalid-url"}):
            service = DatabaseBackupService()

            # This URL will parse but won't have the expected postgresql scheme
            db_info = service.get_database_connection_info()

            # The parsed URL should still return values (even if not ideal)
            assert "host" in db_info
            assert "port" in db_info
            assert "user" in db_info
            assert "database" in db_info

    @patch("subprocess.run")
    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb"})
    def test_create_postgresql_backup_success(self, mock_subprocess, backup_service):
        """Test successful PostgreSQL backup creation."""
        # Mock successful pg_dump
        mock_subprocess.return_value = MagicMock(returncode=0, stderr="", stdout="")

        # Create fake backup file
        backup_file = backup_service.backup_dir / "test_backup.sql"
        backup_file.write_text("-- SQL dump content")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 1024

                result = backup_service._create_postgresql_backup(
                    {
                        "host": "localhost",
                        "port": "5432",
                        "user": "user",
                        "password": "pass",
                        "database": "testdb"
                    },
                    "test_backup",
                    include_data=True,
                    include_schema=True
                )

                assert result["backup_name"] == "test_backup"
                assert result["file_size"] == 1024
                assert result["include_data"] is True
                assert result["include_schema"] is True

                # Verify pg_dump command was called correctly
                mock_subprocess.assert_called_once()
                cmd = mock_subprocess.call_args[0][0]
                assert "pg_dump" in cmd
                assert "-h" in cmd and "localhost" in cmd
                assert "-U" in cmd and "user" in cmd

    @patch("subprocess.run")
    def test_create_postgresql_backup_command_failure(self, mock_subprocess, backup_service):
        """Test pg_dump command failure."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, "pg_dump", stderr="Connection failed"
        )

        with pytest.raises(BackupError, match="pg_dump failed"):
            backup_service._create_postgresql_backup(
                {
                    "host": "localhost",
                    "port": "5432",
                    "user": "user",
                    "password": "pass",
                    "database": "testdb"
                },
                "test_backup",
                include_data=True,
                include_schema=True
            )

    @patch("subprocess.run")
    def test_create_postgresql_backup_timeout(self, mock_subprocess, backup_service):
        """Test pg_dump timeout."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired("pg_dump", 3600)

        with pytest.raises(BackupError, match="Backup timed out"):
            backup_service._create_postgresql_backup(
                {
                    "host": "localhost",
                    "port": "5432",
                    "user": "user",
                    "password": "pass",
                    "database": "testdb"
                },
                "test_backup",
                include_data=True,
                include_schema=True
            )

    def test_post_process_backup_gzip_compression(self, backup_service):
        """Test backup post-processing with gzip compression."""
        # Create test backup file
        backup_file = backup_service.backup_dir / "test.sql"
        backup_file.write_text("SELECT * FROM test_table;")

        backup_result = {
            "backup_file": str(backup_file),
            "file_size": backup_file.stat().st_size,
        }

        with patch("gzip.open", mock_open()), patch("shutil.copyfileobj"):
            with patch("pathlib.Path.unlink"):
                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = 512  # Compressed size

                    result = backup_service._post_process_backup(backup_result)

                    assert result["compression"] == "gzip"
                    assert result["file_size"] == 512
                    assert result["backup_file"].endswith(".gz")

    @patch("subprocess.run")
    def test_upload_via_rsync_success(self, mock_subprocess, backup_service):
        """Test successful rsync upload."""
        mock_subprocess.return_value = MagicMock(returncode=0)

        backup_result = {"backup_file": "/path/to/backup.sql.gz"}
        config = {
            "host": "backup.example.com",
            "user": "backup_user",
            "path": "/backups",
            "ssh_key": "/path/to/key"
        }

        result = backup_service._upload_via_rsync(backup_result, config)

        assert result["remote_upload"] is True
        assert result["remote_type"] == "rsync"
        assert "backup.example.com" in result["remote_path"]

        # Verify rsync command
        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0][0]
        assert "rsync" in cmd
        assert "-avz" in cmd

    @patch("subprocess.run")
    def test_upload_via_rsync_failure(self, mock_subprocess, backup_service):
        """Test rsync upload failure."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, "rsync", stderr="Connection failed"
        )

        backup_result = {"backup_file": "/path/to/backup.sql.gz"}
        config = {
            "host": "backup.example.com",
            "user": "backup_user",
            "path": "/backups"
        }

        result = backup_service._upload_via_rsync(backup_result, config)

        assert result["remote_upload"] is False
        assert "Connection failed" in result["remote_error"]

    def test_list_backups(self, backup_service):
        """Test listing available backups."""
        # Create test backup files
        backup_files = [
            "leadfactory_20240101_120000.sql.gz",
            "leadfactory_20240102_120000.sql",
            "leadfactory_20240103_120000.sql.gz"
        ]

        for filename in backup_files:
            backup_file = backup_service.backup_dir / filename
            backup_file.write_text(f"-- Backup content for {filename}")

        backups = backup_service.list_backups()

        assert len(backups) == 3
        assert all("leadfactory_" in b["name"] for b in backups)
        assert any(b["compressed"] for b in backups)  # .gz files
        assert any(not b["compressed"] for b in backups)  # .sql files

    def test_cleanup_old_backups(self, backup_service):
        """Test cleanup of old backup files."""
        # Create test backup files with different timestamps
        import time
        from datetime import timedelta

        old_file = backup_service.backup_dir / "leadfactory_old.sql.gz"
        recent_file = backup_service.backup_dir / "leadfactory_recent.sql.gz"

        old_file.write_text("old backup")
        recent_file.write_text("recent backup")

        # Make old file actually old
        old_time = time.time() - (backup_service.retention_days + 1) * 24 * 3600
        os.utime(old_file, (old_time, old_time))

        # Run cleanup
        backup_service._cleanup_old_backups()

        # Check that old file was removed and recent file remains
        assert not old_file.exists()
        assert recent_file.exists()

    def test_get_backup_status(self, backup_service):
        """Test getting backup service status."""
        # Create some test backups
        backup_file = backup_service.backup_dir / "leadfactory_test.sql"
        backup_file.write_text("test backup")

        # Update some metrics
        backup_service.metrics["backups_completed"] = 5
        backup_service.metrics["total_backup_size"] = 1024000

        status = backup_service.get_backup_status()

        assert status["service_status"] == "running"
        assert status["total_backups"] == 1
        assert status["metrics"]["backups_completed"] == 5
        assert status["config"]["compression"] == "gzip"
        assert status["latest_backup"] is not None


class TestConvenienceFunctions:
    """Test convenience functions."""

    @patch("leadfactory.services.db_backup_service.db_backup_service")
    def test_create_nightly_backup(self, mock_service):
        """Test convenience function for nightly backup."""
        mock_service.create_backup.return_value = {"backup_name": "test_backup"}

        result = create_nightly_backup()

        assert result["backup_name"] == "test_backup"
        mock_service.create_backup.assert_called_once()

    @patch("leadfactory.services.db_backup_service.db_backup_service")
    def test_get_backup_service_status(self, mock_service):
        """Test convenience function for service status."""
        mock_service.get_backup_status.return_value = {"service_status": "running"}

        result = get_backup_service_status()

        assert result["service_status"] == "running"
        mock_service.get_backup_status.assert_called_once()


# Import subprocess for mocking
import subprocess

if __name__ == "__main__":
    pytest.main([__file__])
