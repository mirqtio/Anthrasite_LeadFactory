"""
CLI commands for database backup management.
"""

from datetime import datetime

import click

from leadfactory.services.db_backup_service import BackupError, db_backup_service


@click.group()
def backup():
    """Database backup management commands."""
    pass


@backup.command()
@click.option("--name", help="Custom backup name (defaults to timestamp)")
@click.option(
    "--no-data", is_flag=True, help="Create schema-only backup (no table data)"
)
@click.option(
    "--no-schema", is_flag=True, help="Create data-only backup (no schema definitions)"
)
@click.option(
    "--config", type=click.Path(exists=True), help="Path to backup configuration file"
)
def create(name, no_data, no_schema, config):
    """Create a database backup."""
    try:
        # Validate options
        if no_data and no_schema:
            click.echo("Error: Cannot specify both --no-data and --no-schema", err=True)
            return

        # Initialize service with custom config if provided
        if config:
            global db_backup_service
            from leadfactory.services.db_backup_service import DatabaseBackupService

            db_backup_service = DatabaseBackupService(config_path=config)

        click.echo("Starting database backup...")

        result = db_backup_service.create_backup(
            backup_name=name,
            include_data=not no_data,
            include_schema=not no_schema,
        )

        click.echo("✅ Backup completed successfully!")
        click.echo(f"   Name: {result['backup_name']}")
        click.echo(f"   File: {result['backup_file']}")
        click.echo(f"   Size: {result['file_size_mb']:.2f} MB")

        if result.get("compression"):
            click.echo(f"   Compression: {result['compression']}")

        if result.get("remote_upload"):
            click.echo(f"   Remote upload: ✅ {result.get('remote_type', 'Unknown')}")

    except BackupError as e:
        click.echo(f"❌ Backup failed: {e}", err=True)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)


@backup.command()
def list():
    """List all available backups."""
    try:
        backups = db_backup_service.list_backups()

        if not backups:
            click.echo("No backups found.")
            return

        click.echo(f"Found {len(backups)} backup(s):\n")

        for backup in backups:
            created_date = datetime.fromisoformat(backup["created_at"])
            click.echo(f"📁 {backup['name']}")
            click.echo(f"   Created: {created_date.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(f"   Size: {backup['size_mb']:.2f} MB")
            click.echo(f"   File: {backup['file']}")
            if backup["compressed"]:
                click.echo("   Compressed: ✅")
            click.echo()

    except Exception as e:
        click.echo(f"❌ Error listing backups: {e}", err=True)


@backup.command()
@click.argument("backup_name")
@click.option("--target-db", help="Target database name (defaults to current database)")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def restore(backup_name, target_db, confirm):
    """Restore database from backup."""
    try:
        # Safety confirmation
        if not confirm:
            db_name = target_db or "current database"
            if not click.confirm(
                f"⚠️  This will restore '{backup_name}' to '{db_name}'. "
                f"This operation will overwrite existing data. Continue?"
            ):
                click.echo("Restore cancelled.")
                return

        click.echo(f"Starting database restore from: {backup_name}")

        result = db_backup_service.restore_backup(
            backup_name=backup_name, target_database=target_db
        )

        click.echo("✅ Restore completed successfully!")
        click.echo(f"   Backup: {result['backup_name']}")
        click.echo(f"   Target DB: {result['target_database']}")
        click.echo(f"   Restored at: {result['restored_at']}")

    except BackupError as e:
        click.echo(f"❌ Restore failed: {e}", err=True)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)


@backup.command()
def status():
    """Show backup service status and metrics."""
    try:
        status = db_backup_service.get_backup_status()

        click.echo("🔧 Database Backup Service Status\n")

        # Service info
        click.echo(f"Status: {status['service_status']}")
        click.echo(f"Backup Directory: {status['backup_directory']}")
        click.echo(f"Retention Period: {status['retention_days']} days")
        click.echo(f"Total Backups: {status['total_backups']}")
        click.echo()

        # Configuration
        config = status["config"]
        click.echo("📋 Configuration:")
        click.echo(f"   Compression: {config['compression']}")
        click.echo(f"   Encryption: {'✅' if config['encryption'] else '❌'}")
        click.echo(
            f"   Remote Storage: {'✅' if config['remote_storage_enabled'] else '❌'}"
        )
        click.echo(
            f"   Notifications: {'✅' if config['notifications_enabled'] else '❌'}"
        )
        click.echo()

        # Metrics
        metrics = status["metrics"]
        click.echo("📊 Metrics:")
        click.echo(f"   Backups Completed: {metrics['backups_completed']}")
        click.echo(f"   Backups Failed: {metrics['backups_failed']}")

        if metrics["total_backup_size"] > 0:
            total_size_mb = metrics["total_backup_size"] / (1024 * 1024)
            click.echo(f"   Total Size: {total_size_mb:.2f} MB")

        if metrics["last_backup_time"]:
            last_backup = datetime.fromisoformat(metrics["last_backup_time"])
            click.echo(f"   Last Backup: {last_backup.strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(
                f"   Last Duration: {metrics['last_backup_duration']:.1f} seconds"
            )

        # Latest backup info
        if status["latest_backup"]:
            latest = status["latest_backup"]
            click.echo()
            click.echo("📁 Latest Backup:")
            click.echo(f"   Name: {latest['name']}")
            click.echo(f"   Size: {latest['size_mb']:.2f} MB")
            created = datetime.fromisoformat(latest["created_at"])
            click.echo(f"   Created: {created.strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        click.echo(f"❌ Error getting status: {e}", err=True)


@backup.command()
@click.option(
    "--days", default=30, help="Remove backups older than N days (default: 30)"
)
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def cleanup(days, confirm):
    """Clean up old backup files."""
    try:
        backups = db_backup_service.list_backups()

        if not backups:
            click.echo("No backups found to clean up.")
            return

        # Count backups that would be removed
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        old_backups = [
            b for b in backups if datetime.fromisoformat(b["created_at"]) < cutoff_date
        ]

        if not old_backups:
            click.echo(f"No backups older than {days} days found.")
            return

        total_size_mb = sum(b["size_mb"] for b in old_backups)

        if not confirm and not click.confirm(
            f"⚠️  This will remove {len(old_backups)} backup(s) "
            f"older than {days} days ({total_size_mb:.2f} MB). Continue?"
        ):
            click.echo("Cleanup cancelled.")
            return

        # Perform cleanup by updating retention and calling internal method
        original_retention = db_backup_service.retention_days
        db_backup_service.retention_days = days
        db_backup_service._cleanup_old_backups()
        db_backup_service.retention_days = original_retention

        click.echo(f"✅ Cleaned up {len(old_backups)} old backup(s)")
        click.echo(f"   Freed space: {total_size_mb:.2f} MB")

    except Exception as e:
        click.echo(f"❌ Error during cleanup: {e}", err=True)


@backup.command()
def schedule():
    """Show scheduling information and recommendations."""
    click.echo("⏰ Database Backup Scheduling\n")

    click.echo("To set up nightly backups, add the following to your crontab:")
    click.echo("(Edit with: crontab -e)\n")

    click.echo("# Daily backup at 2:00 AM")
    click.echo(
        "0 2 * * * cd /path/to/leadfactory && python -m leadfactory.cli backup create"
    )
    click.echo()

    click.echo("# Weekly full backup on Sundays at 3:00 AM")
    click.echo(
        "0 3 * * 0 cd /path/to/leadfactory && python -m leadfactory.cli backup create --name weekly_$(date +%Y%m%d)"
    )
    click.echo()

    click.echo("# Monthly cleanup on 1st of each month at 4:00 AM")
    click.echo(
        "0 4 1 * * cd /path/to/leadfactory && python -m leadfactory.cli backup cleanup --days 30 --confirm"
    )
    click.echo()

    click.echo("Alternative: Use the existing shell script:")
    click.echo("0 2 * * * /path/to/leadfactory/scripts/backup_postgres.sh")
    click.echo()

    click.echo("For systemd-based systems, you can also use systemd timers.")
    click.echo("See: /etc/systemd/system/leadfactory-backup.timer")


if __name__ == "__main__":
    backup()
