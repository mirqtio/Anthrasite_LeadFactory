#!/usr/bin/env python
"""
Setup WAL Archiving for Point-in-Time Recovery
--------------------------------------------
This script configures WAL-G for PostgreSQL Write-Ahead Log archiving
to enable point-in-time recovery capabilities.

Usage:
    python setup_wal_archiving.py --install
    python setup_wal_archiving.py --configure
    python setup_wal_archiving.py --test

Features:
- Installs WAL-G tool for PostgreSQL WAL archiving
- Configures PostgreSQL for continuous WAL archiving
- Sets up automated backups to remote storage
- Provides testing and verification of the WAL archiving setup
"""

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path("logs") / "wal_archiving.log"),
    ],
)
logger = logging.getLogger("setup_wal_archiving")


def ensure_directories():
    """Ensure necessary directories exist."""
    directories = ["logs", "scripts/wal_archive"]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")


def run_command(command, cwd=None, env=None, shell=False):
    """Run a command and return the result."""
    cmd_str = " ".join(command) if isinstance(command, list) else command
    logger.info(f"Running command: {cmd_str}")

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            shell=shell,  # nosec B602
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info("Command succeeded")
            return True, result.stdout
        else:
            logger.error("Command failed")
            logger.error(f"Error: {result.stderr}")
            return False, result.stderr
    except Exception as e:
        logger.exception(f"Error running command: {e}")
        return False, str(e)


def install_wal_g():
    """Install WAL-G tool for PostgreSQL WAL archiving."""
    logger.info("Installing WAL-G")

    # Check if WAL-G is already installed
    if shutil.which("wal-g"):
        logger.info("WAL-G is already installed")
        return True

    # Install WAL-G using the appropriate method for the system
    if Path("/etc/debian_version").exists():
        # Debian/Ubuntu
        commands = [
            ["sudo", "apt-get", "update"],
            [
                "sudo",
                "apt-get",
                "install",
                "-y",
                "wget",
                "lzma-dev",
                "pv",
                "liblzo2-dev",
            ],
            [
                "wget",
                "https://github.com/wal-g/wal-g/releases/download/v1.1.1/wal-g-pg-ubuntu-20.04-amd64.tar.gz",
            ],
            ["tar", "xvzf", "wal-g-pg-ubuntu-20.04-amd64.tar.gz"],
            ["sudo", "mv", "wal-g-pg-ubuntu-20.04-amd64", "/usr/local/bin/wal-g"],
            ["sudo", "chmod", "+x", "/usr/local/bin/wal-g"],
            ["rm", "wal-g-pg-ubuntu-20.04-amd64.tar.gz"],
        ]
    elif Path("/etc/redhat-release").exists():
        # RHEL/CentOS
        commands = [
            ["sudo", "yum", "install", "-y", "wget", "lzma-devel", "pv", "lzo-devel"],
            [
                "wget",
                "https://github.com/wal-g/wal-g/releases/download/v1.1.1/wal-g-pg-centos7-amd64.tar.gz",
            ],
            ["tar", "xvzf", "wal-g-pg-centos7-amd64.tar.gz"],
            ["sudo", "mv", "wal-g-pg-centos7-amd64", "/usr/local/bin/wal-g"],
            ["sudo", "chmod", "+x", "/usr/local/bin/wal-g"],
            ["rm", "wal-g-pg-centos7-amd64.tar.gz"],
        ]
    elif Path("/etc/arch-release").exists():
        # Arch Linux
        commands = [
            ["sudo", "pacman", "-Sy", "--noconfirm", "wget", "pv"],
            [
                "wget",
                "https://github.com/wal-g/wal-g/releases/download/v1.1.1/wal-g-pg-ubuntu-20.04-amd64.tar.gz",
            ],
            ["tar", "xvzf", "wal-g-pg-ubuntu-20.04-amd64.tar.gz"],
            ["sudo", "mv", "wal-g-pg-ubuntu-20.04-amd64", "/usr/local/bin/wal-g"],
            ["sudo", "chmod", "+x", "/usr/local/bin/wal-g"],
            ["rm", "wal-g-pg-ubuntu-20.04-amd64.tar.gz"],
        ]
    elif sys.platform == "darwin":
        # macOS
        commands = [["brew", "install", "wal-g"]]
    else:
        logger.error("Unsupported operating system")
        return False

    # Run each command
    for command in commands:
        success, output = run_command(command)
        if not success:
            logger.error("Failed to install WAL-G")
            return False

    logger.info("WAL-G installed successfully")
    return True


def create_wal_g_config():
    """Create WAL-G configuration files."""
    logger.info("Creating WAL-G configuration")

    # Create WAL-G environment file
    env_file = Path("scripts/wal_archive/wal-g.env")

    # Load environment variables
    env_vars = {}
    env_file_path = ".env"
    if not Path(env_file_path).exists():
        env_file_path = ".env.production"

    if Path(env_file_path).exists():
        with Path(env_file_path).open() as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip("\"'")

    # Get storage configuration
    storage_type = env_vars.get("WAL_STORAGE_TYPE", "fs")

    if storage_type == "s3":
        # S3 configuration
        config = f"""
# S3 Storage Configuration
WALG_S3_PREFIX=s3://{env_vars.get('S3_BUCKET', 'leadfactory-wal-archive')}/\
{env_vars.get('S3_PREFIX', 'wal-archive')}
AWS_ACCESS_KEY_ID={env_vars.get('AWS_ACCESS_KEY_ID', '')}
AWS_SECRET_ACCESS_KEY={env_vars.get('AWS_SECRET_ACCESS_KEY', '')}
AWS_REGION={env_vars.get('AWS_REGION', 'us-east-1')}

# Compression settings
WALG_COMPRESSION_METHOD=lz4
"""
    elif storage_type == "gs":
        # Google Cloud Storage configuration
        config = f"""
# Google Cloud Storage Configuration
WALG_GS_PREFIX=gs://{env_vars.get('GS_BUCKET', 'leadfactory-wal-archive')}/\
{env_vars.get('GS_PREFIX', 'wal-archive')}
GOOGLE_APPLICATION_CREDENTIALS=\
{env_vars.get('GOOGLE_APPLICATION_CREDENTIALS', '/path/to/credentials.json')}

# Compression settings
WALG_COMPRESSION_METHOD=lz4
"""
    else:
        # File system configuration (default)
        config = f"""
# File System Storage Configuration
WALG_FILE_PREFIX={env_vars.get('BACKUP_REMOTE_PATH', '/var/backups/leadfactory')}/\
wal-archive

# Compression settings
WALG_COMPRESSION_METHOD=lz4
"""

    # Write configuration to file
    logger.info(f"Writing WAL-G environment configuration to {env_file}")
    with env_file.open("w") as f:
        f.write(config.strip())

    logger.info(f"Created WAL-G environment file at {env_file.resolve()}")
    return True


def create_backup_script():
    """Create WAL-G backup script."""
    logger.info("Creating WAL-G backup script")

    # Create backup script
    backup_script = Path("scripts/wal_archive/backup.sh")
    logger.info(f"Writing backup script to {backup_script}")
    with backup_script.open("w") as f:
        f.write(
            """#!/bin/bash
# WAL-G backup script

set -e

# Load environment variables
source /path/to/scripts/wal_archive/wal-g.env

# Create a base backup
echo "Creating a base backup with WAL-G at $(date)"
wal-g backup-push ${{PGDATA:-/var/lib/postgresql/data}}

echo "Base backup completed at $(date)"
"""
        )

    backup_script.chmod(0o755)  # nosec B103
    logger.info(f"Backup script created at {backup_script.resolve()}")
    return True


def create_restore_script():
    """Create WAL-G restore script."""
    logger.info("Creating WAL-G restore script")

    # Create restore script
    restore_script = Path("scripts/wal_archive/restore.sh")
    logger.info(f"Writing restore script to {restore_script}")
    with restore_script.open("w") as f:
        f.write(
            """#!/bin/bash
# WAL-G restore script

set -e

# Load environment variables
source /path/to/scripts/wal_archive/wal-g.env

# Check if a backup name is provided
if [ -z "$1" ]; then
    echo "Usage: $0 BACKUP_NAME"
    echo "Available backups:"
    wal-g backup-list
    exit 1
fi

BACKUP_NAME=$1

# Stop PostgreSQL
echo "Stopping PostgreSQL"
sudo systemctl stop postgresql || true

# Clear PGDATA directory
echo "Clearing PGDATA directory"
sudo rm -rf ${{PGDATA:-/var/lib/postgresql/data}}/*

# Restore from backup
echo "Restoring from backup $BACKUP_NAME"
sudo -u postgres wal-g backup-fetch ${{PGDATA:-/var/lib/postgresql/data}} "$BACKUP_NAME"

# Create recovery.conf for PITR (PostgreSQL < 12)
if [ -n "$2" ]; then
    RECOVERY_TARGET_TIME=$2
    echo "Setting up recovery to point in time: $RECOVERY_TARGET_TIME"

    # For PostgreSQL 12+
    if [ -d "${{PGDATA:-/var/lib/postgresql/data}}/pg_wal" ]; then
        sudo -u postgres touch "${{PGDATA:-/var/lib/postgresql/data}}/recovery.signal"
        TARGET_CONF_FILE="${{PGDATA:-/var/lib/postgresql/data}}/postgresql.auto.conf"
        sudo -u postgres cat > "$TARGET_CONF_FILE" << EOF
restore_command = 'wal-g wal-fetch "%f" "%p"'
recovery_target_time = '$RECOVERY_TARGET_TIME'
recovery_target_action = 'promote'
EOF
    else
        # For PostgreSQL < 12
        TARGET_CONF_FILE="${{PGDATA:-/var/lib/postgresql/data}}/recovery.conf"
        sudo -u postgres cat > "$TARGET_CONF_FILE" << EOF
restore_command = 'wal-g wal-fetch "%f" "%p"'
recovery_target_time = '$RECOVERY_TARGET_TIME'
recovery_target_action = 'promote'
EOF
    fi
else
    # For PostgreSQL 12+
    if [ -d "${{PGDATA:-/var/lib/postgresql/data}}/pg_wal" ]; then
        sudo -u postgres touch "${{PGDATA:-/var/lib/postgresql/data}}/recovery.signal"
        TARGET_CONF_FILE="${{PGDATA:-/var/lib/postgresql/data}}/postgresql.auto.conf"
        sudo -u postgres cat > "$TARGET_CONF_FILE" << EOF
restore_command = 'wal-g wal-fetch "%f" "%p"'
EOF
    else
        # For PostgreSQL < 12
        TARGET_CONF_FILE="${{PGDATA:-/var/lib/postgresql/data}}/recovery.conf"
        sudo -u postgres cat > "$TARGET_CONF_FILE" << EOF
restore_command = 'wal-g wal-fetch "%f" "%p"'
EOF
    fi
fi

# Fix permissions
sudo chown -R postgres:postgres ${{PGDATA:-/var/lib/postgresql/data}}
sudo chmod -R 700 ${{PGDATA:-/var/lib/postgresql/data}}

# Start PostgreSQL
echo "Starting PostgreSQL"
sudo systemctl start postgresql || true

echo "Restore completed at $(date)"
"""
        )

    restore_script.chmod(0o755)  # nosec B103
    logger.info(f"Restore script created at {restore_script.resolve()}")
    return True


def create_cron_job_script():
    """Create WAL-G cron job script."""
    logger.info("Creating WAL-G cron job script")

    # Create cron job script
    cron_job = Path("scripts/wal_archive/wal-g_backup_cron.sh")
    logger.info(f"Writing cron job script to {cron_job}")
    with cron_job.open("w") as f:
        f.write(
            """#!/bin/bash
# WAL-G cron job for regular base backups

# Run the backup script
/path/to/scripts/wal_archive/backup.sh

# Retain backups for 90 days
source /path/to/scripts/wal_archive/wal-g.env
wal-g delete retain FIND_FULL $(( 90 * 24 )) --confirm
"""
        )

    cron_job.chmod(0o755)  # nosec B103
    logger.info(f"Cron job script created at {cron_job.resolve()}")
    return True


def configure_postgresql():
    """Configure PostgreSQL for WAL archiving."""
    logger.info("Configuring PostgreSQL for WAL archiving")

    # Create PostgreSQL configuration
    pg_config = """
# WAL Archiving Configuration
wal_level = replica
archive_mode = on
archive_command = 'source /path/to/scripts/wal_archive/wal-g.env && wal-g wal-push %p'
archive_timeout = 60
"""

    # Write configuration to a file
    config_file = Path("scripts/wal_archive/postgresql_wal.conf")
    with config_file.open("w") as f:
        f.write(pg_config)

    logger.info(f"PostgreSQL WAL configuration created at {config_file.resolve()}")
    logger.info("To enable WAL archiving, include this file in your postgresql.conf")
    logger.info(
        "Example: echo 'include = '/path/to/scripts/wal_archive/"
        "postgresql_wal.conf'' >> /etc/postgresql/13/main/postgresql.conf"
    )

    # Configure PostgreSQL replication settings
    success, pg_config_output = run_command(["pg_config", "--bindir"])
    if not success:
        logger.error(f"Failed to get pg_config path: {pg_config_output}")
        return False

    pg_config_dir = Path(pg_config_output.strip()).parent
    pg_hba_conf = Path(pg_config_dir) / "pg_hba.conf"
    if not Path(pg_hba_conf).exists():
        logger.error(f"pg_hba.conf not found at {pg_hba_conf}")
        return False
    with Path(pg_hba_conf).open("r") as f:
        pg_hba_content = f.read()
    if "host replication all 0.0.0.0/0 md5" not in pg_hba_content:
        with Path(pg_hba_conf).open("w") as f:
            f.write(pg_hba_content + "\nhost replication all 0.0.0.0/0 md5\n")
        logger.info(f"Updated {pg_hba_conf} for replication")

    postgresql_conf = Path(pg_config_dir) / "postgresql.conf"
    if not Path(postgresql_conf).exists():
        logger.error(f"postgresql.conf not found at {postgresql_conf}")
        return False
    with Path(postgresql_conf).open("r") as f:
        postgresql_content = f.read()
    if "archive_command = 'wal-g wal-push %p'" not in postgresql_content:
        with Path(postgresql_conf).open("w") as f:
            # Ensure necessary settings are present
            new_config_lines = []
            for line in postgresql_content.splitlines():
                if line.strip().startswith("wal_level"):
                    new_config_lines.append("wal_level = replica")
                elif line.strip().startswith("archive_mode"):
                    new_config_lines.append("archive_mode = on")
                elif line.strip().startswith("archive_command"):
                    new_config_lines.append(
                        "archive_command = 'source /path/to/scripts/wal_archive/"
                        "wal-g.env && wal-g wal-push %p'"
                    )
                elif line.strip().startswith("archive_timeout"):
                    new_config_lines.append("archive_timeout = 60")
                else:
                    new_config_lines.append(line)
            f.write("\n".join(new_config_lines))

    cron_job = Path("scripts/wal_archive/wal-g_backup_cron.sh")
    cron_job.chmod(0o755)  # nosec B103

    logger.info("To schedule regular backups, add this to crontab:")
    logger.info(f"0 1 * * * {cron_job.resolve()} >> /var/log/wal-g-backup.log 2>&1")

    logger.info("PostgreSQL configured for WAL archiving")
    return True


def test_wal_g_setup():
    """Test the WAL-G setup."""
    logger.info("Testing WAL-G setup")

    # Check if WAL-G is installed
    success, output = run_command(["which", "wal-g"])
    if not success:
        logger.error("WAL-G is not installed")
        return False

    logger.info(f"WAL-G is installed at: {output.strip()}")

    # Check WAL-G version
    success, output = run_command(["wal-g", "version"])
    if success:
        logger.info(f"WAL-G version: {output.strip()}")

    # Test environment file
    env_file = Path("scripts/wal_archive/wal-g.env")
    if not env_file.exists():
        logger.error(f"Environment file {env_file} does not exist")
        return False

    logger.info(f"Environment file {env_file} exists")

    # Test backup script
    backup_script = Path("scripts/wal_archive/backup.sh")
    if not backup_script.exists():
        logger.error(f"Backup script {backup_script} does not exist")
        return False

    logger.info(f"Backup script {backup_script} exists")

    # Test restore script
    restore_script = Path("scripts/wal_archive/restore.sh")
    if not restore_script.exists():
        logger.error(f"Restore script {restore_script} does not exist")
        return False

    logger.info(f"Restore script {restore_script} exists")

    logger.info("WAL-G setup test prerequisites met.")
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Setup WAL Archiving for Point-in-Time Recovery"
    )
    parser.add_argument("--install", action="store_true", help="Install WAL-G")
    parser.add_argument(
        "--configure", action="store_true", help="Configure WAL-G and PostgreSQL"
    )
    parser.add_argument("--test", action="store_true", help="Test WAL-G setup")
    parser.add_argument("--fail-fast", action="store_true", help="Fail fast on errors")
    args = parser.parse_args()

    try:
        # Ensure directories exist
        ensure_directories()

        if args.install and not install_wal_g():
            # Install WAL-G
            return 1

        if args.configure:
            # Configure WAL-G and PostgreSQL
            if not create_wal_g_config():
                return 1
            if not create_backup_script():
                return 1
            if not create_restore_script():
                return 1
            if not configure_postgresql():
                return 1

        if args.test and not test_wal_g_setup():
            # Test WAL-G setup
            return 1

        logger.info("WAL-G setup process completed.")
        return 0

    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
