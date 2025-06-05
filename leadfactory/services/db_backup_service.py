"""
Database Backup Service
-----------------------
This module provides automated database backup functionality with support for multiple
storage backends, encryption, compression, and monitoring integration.
"""

import contextlib
import gzip
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import yaml

from leadfactory.cost.cost_tracking import cost_tracker
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class BackupError(Exception):
    """Exception raised when backup operations fail."""

    pass


class DatabaseBackupService:
    """Service for automated database backups with multiple storage options."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the database backup service.

        Args:
            config_path: Path to backup configuration file
        """
        self.config = self._load_config(config_path)
        self.backup_dir = Path(self.config.get("backup_dir", "./data/backups"))
        self.retention_days = self.config.get("retention_days", 30)

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Initialize metrics tracking
        self.metrics = {
            "backups_completed": 0,
            "backups_failed": 0,
            "total_backup_size": 0,
            "last_backup_time": None,
            "last_backup_duration": 0,
        }

        logger.info(
            f"Database backup service initialized (backup_dir: {self.backup_dir})"
        )

    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load backup configuration from file or environment."""
        # Default configuration
        config = {
            "backup_dir": os.environ.get("BACKUP_DIR", "./data/backups"),
            "retention_days": int(os.environ.get("BACKUP_RETENTION_DAYS", "30")),
            "compression": os.environ.get("BACKUP_COMPRESSION", "gzip").lower(),
            "encryption": os.environ.get("BACKUP_ENCRYPTION", "false").lower()
            == "true",
            "remote_storage": {
                "enabled": os.environ.get("BACKUP_REMOTE_ENABLED", "false").lower()
                == "true",
                # rsync, s3, gcs
                "type": os.environ.get("BACKUP_REMOTE_TYPE", "rsync"),
                "config": {
                    "host": os.environ.get("RSYNC_TARGET_HOST"),
                    "user": os.environ.get("RSYNC_TARGET_USER"),
                    "path": os.environ.get("RSYNC_TARGET_PATH"),
                    "ssh_key": os.environ.get("RSYNC_SSH_KEY_PATH"),
                },
            },
            "notifications": {
                "enabled": os.environ.get(
                    "BACKUP_NOTIFICATIONS_ENABLED", "false"
                ).lower()
                == "true",
                "email": os.environ.get("BACKUP_NOTIFICATION_EMAIL"),
                "slack_webhook": os.environ.get("BACKUP_SLACK_WEBHOOK"),
            },
            "monitoring": {
                "track_costs": os.environ.get("BACKUP_TRACK_COSTS", "true").lower()
                == "true",
                "cost_per_gb": float(os.environ.get("BACKUP_COST_PER_GB", "0.02")),
            },
        }

        # Load from config file if provided
        if config_path and Path(config_path).exists():
            try:
                with open(config_path) as f:
                    file_config = yaml.safe_load(f)
                    config.update(file_config.get("backup", {}))
                logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config file {config_path}: {e}")

        return config

    def get_database_connection_info(self) -> dict[str, str]:
        """Extract database connection information from DATABASE_URL."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise BackupError("DATABASE_URL environment variable is not set")

        try:
            parsed = urlparse(database_url)

            return {
                "host": parsed.hostname or "localhost",
                "port": str(parsed.port or 5432),
                "user": parsed.username or "postgres",
                "password": parsed.password or "",
                "database": parsed.path.lstrip("/") if parsed.path else "postgres",
                "scheme": parsed.scheme,
            }
        except Exception as e:
            raise BackupError(f"Failed to parse DATABASE_URL: {e}")

    def create_backup(
        self,
        backup_name: Optional[str] = None,
        include_data: bool = True,
        include_schema: bool = True,
    ) -> dict[str, any]:
        """
        Create a database backup.

        Args:
            backup_name: Custom backup name (defaults to timestamp)
            include_data: Whether to include table data
            include_schema: Whether to include schema definitions

        Returns:
            Dictionary with backup information
        """
        start_time = datetime.now()

        if backup_name is None:
            backup_name = f"leadfactory_{start_time.strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Starting database backup: {backup_name}")

        try:
            # Get database connection info
            db_info = self.get_database_connection_info()

            # Create backup using pg_dump
            backup_result = self._create_postgresql_backup(
                db_info, backup_name, include_data, include_schema
            )

            # Post-process backup (compression, encryption)
            processed_result = self._post_process_backup(backup_result)

            # Upload to remote storage if configured
            if self.config["remote_storage"]["enabled"]:
                remote_result = self._upload_to_remote_storage(processed_result)
                processed_result.update(remote_result)

            # Track metrics and costs
            self._update_metrics(processed_result, start_time)

            # Send notifications if configured
            if self.config["notifications"]["enabled"]:
                self._send_backup_notification(processed_result, success=True)

            # Clean up old backups
            self._cleanup_old_backups()

            logger.info(f"Backup completed successfully: {backup_name}")
            return processed_result

        except Exception as e:
            error_msg = f"Backup failed: {e}"
            logger.error(error_msg)

            self.metrics["backups_failed"] += 1

            # Send failure notification
            if self.config["notifications"]["enabled"]:
                self._send_backup_notification(
                    {"backup_name": backup_name, "error": str(e)}, success=False
                )

            raise BackupError(error_msg)

    def _create_postgresql_backup(
        self,
        db_info: dict[str, str],
        backup_name: str,
        include_data: bool,
        include_schema: bool,
    ) -> dict[str, any]:
        """Create PostgreSQL backup using pg_dump."""
        backup_file = self.backup_dir / f"{backup_name}.sql"

        # Build pg_dump command
        cmd = [
            "pg_dump",
            "-h",
            db_info["host"],
            "-p",
            db_info["port"],
            "-U",
            db_info["user"],
            "-d",
            db_info["database"],
            "-f",
            str(backup_file),
            "--verbose",
        ]

        # Add options based on parameters
        if not include_data:
            cmd.append("--schema-only")
        elif not include_schema:
            cmd.append("--data-only")

        # Set password environment variable
        env = os.environ.copy()
        if db_info["password"]:
            env["PGPASSWORD"] = db_info["password"]

        try:
            logger.debug(
                f"Running pg_dump command: {' '.join(cmd[:-2])} [password hidden]"
            )

            subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True,
                timeout=3600,  # 1 hour timeout
            )

            # Check if backup file was created
            if not backup_file.exists():
                raise BackupError("Backup file was not created")

            file_size = backup_file.stat().st_size

            return {
                "backup_name": backup_name,
                "backup_file": str(backup_file),
                "file_size": file_size,
                "file_size_mb": file_size / (1024 * 1024),
                "created_at": datetime.now().isoformat(),
                "include_data": include_data,
                "include_schema": include_schema,
                "compression": None,
                "encrypted": False,
            }

        except subprocess.TimeoutExpired:
            raise BackupError("Backup timed out after 1 hour")
        except subprocess.CalledProcessError as e:
            error_msg = f"pg_dump failed: {e.stderr}"
            raise BackupError(error_msg)
        finally:
            # Clear password from environment
            if "PGPASSWORD" in env:
                del env["PGPASSWORD"]

    def _post_process_backup(self, backup_result: dict[str, any]) -> dict[str, any]:
        """Post-process backup with compression and encryption."""
        backup_file = Path(backup_result["backup_file"])
        processed_file = backup_file

        # Compression
        if self.config["compression"] == "gzip":
            compressed_file = backup_file.with_suffix(backup_file.suffix + ".gz")

            logger.debug(f"Compressing backup: {backup_file} -> {compressed_file}")

            with open(backup_file, "rb") as f_in:
                with gzip.open(compressed_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Remove original file
            backup_file.unlink()
            processed_file = compressed_file

            # Update result
            backup_result["backup_file"] = str(processed_file)
            backup_result["compression"] = "gzip"
            backup_result["file_size"] = processed_file.stat().st_size
            backup_result["file_size_mb"] = backup_result["file_size"] / (1024 * 1024)

            logger.debug(
                f"Compression completed, size reduced to {backup_result['file_size_mb']:.2f} MB"
            )

        # Encryption (placeholder for future implementation)
        if self.config["encryption"]:
            logger.warning("Encryption is configured but not yet implemented")
            # TODO: Implement encryption using gpg or similar

        return backup_result

    def _upload_to_remote_storage(
        self, backup_result: dict[str, any]
    ) -> dict[str, any]:
        """Upload backup to remote storage."""
        remote_config = self.config["remote_storage"]["config"]
        storage_type = self.config["remote_storage"]["type"]

        if storage_type == "rsync":
            return self._upload_via_rsync(backup_result, remote_config)
        elif storage_type == "s3":
            return self._upload_via_s3(backup_result, remote_config)
        else:
            logger.warning(f"Unsupported remote storage type: {storage_type}")
            return {"remote_upload": False}

    def _upload_via_rsync(
        self, backup_result: dict[str, any], config: dict
    ) -> dict[str, any]:
        """Upload backup via rsync."""
        host = config.get("host")
        user = config.get("user")
        path = config.get("path")
        ssh_key = config.get("ssh_key")

        if not all([host, user, path]):
            logger.warning("Incomplete rsync configuration, skipping remote upload")
            return {"remote_upload": False}

        backup_file = backup_result["backup_file"]
        remote_path = f"{user}@{host}:{path}/"

        # Build rsync command
        cmd = ["rsync", "-avz"]

        if ssh_key:
            cmd.extend(["-e", f"ssh -i {ssh_key}"])

        cmd.extend([backup_file, remote_path])

        try:
            logger.debug(f"Uploading via rsync to {remote_path}")

            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=1800,  # 30 minute timeout
            )

            logger.info(f"Successfully uploaded backup to {remote_path}")

            return {
                "remote_upload": True,
                "remote_type": "rsync",
                "remote_path": remote_path,
                "upload_duration": None,  # Could be extracted from rsync output
            }

        except subprocess.CalledProcessError as e:
            error_msg = f"rsync upload failed: {e.stderr}"
            logger.error(error_msg)
            return {
                "remote_upload": False,
                "remote_error": error_msg,
            }

    def _upload_via_s3(
        self, backup_result: dict[str, any], config: dict
    ) -> dict[str, any]:
        """Upload backup via AWS S3 (placeholder for future implementation)."""
        logger.warning("S3 upload is not yet implemented")
        return {"remote_upload": False, "remote_error": "S3 upload not implemented"}

    def _update_metrics(self, backup_result: dict[str, any], start_time: datetime):
        """Update backup metrics and track costs."""
        duration = (datetime.now() - start_time).total_seconds()

        self.metrics["backups_completed"] += 1
        self.metrics["total_backup_size"] += backup_result["file_size"]
        self.metrics["last_backup_time"] = datetime.now().isoformat()
        self.metrics["last_backup_duration"] = duration

        # Track backup costs if enabled
        if self.config["monitoring"]["track_costs"]:
            size_gb = backup_result["file_size"] / (1024 * 1024 * 1024)
            cost_per_gb = self.config["monitoring"]["cost_per_gb"]
            backup_cost = size_gb * cost_per_gb

            cost_tracker.add_cost(
                amount=backup_cost,
                service="backup",
                operation="database_backup",
                details={
                    "backup_name": backup_result["backup_name"],
                    "file_size_gb": size_gb,
                    "cost_per_gb": cost_per_gb,
                    "duration_seconds": duration,
                    "remote_upload": backup_result.get("remote_upload", False),
                },
            )

            logger.debug(f"Tracked backup cost: ${backup_cost:.4f}")

    def _send_backup_notification(self, backup_result: dict[str, any], success: bool):
        """Send backup notification via configured channels."""
        # This is a placeholder for notification implementation
        # In a real implementation, you would integrate with email and Slack
        # services

        if success:
            message = f"✅ Database backup completed successfully: {backup_result['backup_name']}"
            if "file_size_mb" in backup_result:
                message += f" (Size: {backup_result['file_size_mb']:.2f} MB)"
        else:
            message = f"❌ Database backup failed: {backup_result.get('backup_name', 'Unknown')}"
            if "error" in backup_result:
                message += f" - Error: {backup_result['error']}"

        logger.info(f"Backup notification: {message}")

        # TODO: Implement actual email/Slack notifications
        # if self.config["notifications"]["email"]:
        #     send_email(self.config["notifications"]["email"], "Backup Status", message)
        # if self.config["notifications"]["slack_webhook"]:
        #     send_slack_notification(self.config["notifications"]["slack_webhook"], message)

    def _cleanup_old_backups(self):
        """Remove backup files older than retention period."""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        removed_count = 0
        freed_bytes = 0

        for backup_file in self.backup_dir.glob("leadfactory_*.sql*"):
            if backup_file.stat().st_mtime < cutoff_date.timestamp():
                file_size = backup_file.stat().st_size
                backup_file.unlink()
                removed_count += 1
                freed_bytes += file_size

                logger.debug(f"Removed old backup: {backup_file}")

        if removed_count > 0:
            freed_mb = freed_bytes / (1024 * 1024)
            logger.info(
                f"Cleaned up {removed_count} old backups, freed {freed_mb:.2f} MB"
            )

    def list_backups(self) -> list[dict[str, any]]:
        """List all available backups."""
        backups = []

        for backup_file in sorted(self.backup_dir.glob("leadfactory_*.sql*")):
            stat_info = backup_file.stat()

            backup_info = {
                "name": backup_file.stem.replace(".sql", ""),
                "file": str(backup_file),
                "size": stat_info.st_size,
                "size_mb": stat_info.st_size / (1024 * 1024),
                "created_at": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                "compressed": backup_file.suffix == ".gz",
            }

            backups.append(backup_info)

        return backups

    def restore_backup(
        self, backup_name: str, target_database: Optional[str] = None
    ) -> dict[str, any]:
        """
        Restore a database from backup.

        Args:
            backup_name: Name of the backup to restore
            target_database: Target database name (defaults to current database)

        Returns:
            Dictionary with restore information
        """
        # Find backup file
        backup_files = list(self.backup_dir.glob(f"{backup_name}.sql*"))
        if not backup_files:
            raise BackupError(f"Backup not found: {backup_name}")

        backup_file = backup_files[0]

        logger.info(f"Starting database restore from: {backup_file}")

        try:
            # Get database connection info
            db_info = self.get_database_connection_info()
            if target_database:
                db_info["database"] = target_database

            # Decompress if needed
            if backup_file.suffix == ".gz":
                with tempfile.NamedTemporaryFile(
                    mode="wb", delete=False, suffix=".sql"
                ) as temp_file:
                    with gzip.open(backup_file, "rb") as gz_file:
                        shutil.copyfileobj(gz_file, temp_file)
                    sql_file = temp_file.name
            else:
                sql_file = str(backup_file)

            # Restore using psql
            cmd = [
                "psql",
                "-h",
                db_info["host"],
                "-p",
                db_info["port"],
                "-U",
                db_info["user"],
                "-d",
                db_info["database"],
                "-f",
                sql_file,
                "-v",
                "ON_ERROR_STOP=1",
            ]

            # Set password environment variable
            env = os.environ.copy()
            if db_info["password"]:
                env["PGPASSWORD"] = db_info["password"]

            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                check=True,
                timeout=3600,  # 1 hour timeout
            )

            logger.info("Database restore completed successfully")

            return {
                "backup_name": backup_name,
                "target_database": db_info["database"],
                "restored_at": datetime.now().isoformat(),
                "success": True,
            }

        except subprocess.CalledProcessError as e:
            error_msg = f"Database restore failed: {e.stderr}"
            logger.error(error_msg)
            raise BackupError(error_msg)

        finally:
            # Clean up temporary file if created
            if backup_file.suffix == ".gz" and "sql_file" in locals():
                with contextlib.suppress(BaseException):
                    os.unlink(sql_file)

    def get_backup_status(self) -> dict[str, any]:
        """Get current backup service status and metrics."""
        backups = self.list_backups()

        return {
            "service_status": "running",
            "backup_directory": str(self.backup_dir),
            "retention_days": self.retention_days,
            "total_backups": len(backups),
            "metrics": self.metrics,
            "config": {
                "compression": self.config["compression"],
                "encryption": self.config["encryption"],
                "remote_storage_enabled": self.config["remote_storage"]["enabled"],
                "notifications_enabled": self.config["notifications"]["enabled"],
            },
            "latest_backup": backups[-1] if backups else None,
        }


# Create a default instance
db_backup_service = DatabaseBackupService()


def create_nightly_backup() -> dict[str, any]:
    """
    Convenience function for creating nightly backups.

    Returns:
        Backup result dictionary
    """
    return db_backup_service.create_backup()


def get_backup_service_status() -> dict[str, any]:
    """
    Convenience function for getting backup service status.

    Returns:
        Service status dictionary
    """
    return db_backup_service.get_backup_status()
