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
import os
import shutil
import subprocess
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "wal_archiving.log")),
    ],
)
logger = logging.getLogger("setup_wal_archiving")


def ensure_directories():
    """Ensure necessary directories exist."""
    directories = ["logs", "scripts/wal_archive"]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")


def run_command(command, cwd=None, env=None, shell=False):
    """Run a command and return the result."""
    logger.info(
        f"Running command: {' '.join(command) if isinstance(command, list) else command}"
    )

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
    if os.path.exists("/etc/debian_version"):
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
    elif os.path.exists("/etc/redhat-release"):
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
    elif os.path.exists("/etc/arch-release"):
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
    env_file = "scripts/wal_archive/wal-g.env"

    # Load environment variables
    env_vars = {}
    env_file_path = ".env"
    if not os.path.exists(env_file_path):
        env_file_path = ".env.production"

    if os.path.exists(env_file_path):
        with open(env_file_path) as f:
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
WALG_S3_PREFIX=s3://{env_vars.get('S3_BUCKET', 'leadfactory-wal-archive')}/{env_vars.get('S3_PREFIX', 'wal-archive')}
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
WALG_GS_PREFIX=gs://{env_vars.get('GS_BUCKET', 'leadfactory-wal-archive')}/{env_vars.get('GS_PREFIX', 'wal-archive')}
GOOGLE_APPLICATION_CREDENTIALS={env_vars.get('GOOGLE_APPLICATION_CREDENTIALS', '/path/to/credentials.json')}

# Compression settings
WALG_COMPRESSION_METHOD=lz4
"""
    else:
        # File system configuration (default)
        config = f"""
# File System Storage Configuration
WALG_FILE_PREFIX={env_vars.get('BACKUP_REMOTE_PATH', '/var/backups/leadfactory')}/wal-archive

# Compression settings
WALG_COMPRESSION_METHOD=lz4
"""

    # Write configuration to file
    with open(env_file, "w") as f:
        f.write(config)

    logger.info(f"WAL-G configuration created at {env_file}")

    # Create shell scripts for backup and restore

    # Backup script
    backup_script = "scripts/wal_archive/backup.sh"
    with open(backup_script, "w") as f:
        f.write(
            f"""#!/bin/bash
# WAL-G backup script

set -e

# Load environment variables
source {os.path.abspath(env_file)}

# Create a base backup
echo "Creating a base backup with WAL-G at $(date)"
wal-g backup-push ${{PGDATA:-/var/lib/postgresql/data}}

echo "Base backup completed at $(date)"
"""
        )

    os.chmod(backup_script, 0o755)  # nosec B103

    # Restore script
    restore_script = "scripts/wal_archive/restore.sh"
    with open(restore_script, "w") as f:
        f.write(
            f"""#!/bin/bash
# WAL-G restore script

set -e

# Load environment variables
source {os.path.abspath(env_file)}

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
        sudo -u postgres cat > "${{PGDATA:-/var/lib/postgresql/data}}/postgresql.auto.conf" << EOF
restore_command = 'wal-g wal-fetch "%f" "%p"'
recovery_target_time = '$RECOVERY_TARGET_TIME'
recovery_target_action = 'promote'
EOF
    else
        # For PostgreSQL < 12
        sudo -u postgres cat > "${{PGDATA:-/var/lib/postgresql/data}}/recovery.conf" << EOF
restore_command = 'wal-g wal-fetch "%f" "%p"'
recovery_target_time = '$RECOVERY_TARGET_TIME'
recovery_target_action = 'promote'
EOF
    fi
else
    # For PostgreSQL 12+
    if [ -d "${{PGDATA:-/var/lib/postgresql/data}}/pg_wal" ]; then
        sudo -u postgres touch "${{PGDATA:-/var/lib/postgresql/data}}/recovery.signal"
        sudo -u postgres cat > "${{PGDATA:-/var/lib/postgresql/data}}/postgresql.auto.conf" << EOF
restore_command = 'wal-g wal-fetch "%f" "%p"'
EOF
    else
        # For PostgreSQL < 12
        sudo -u postgres cat > "${{PGDATA:-/var/lib/postgresql/data}}/recovery.conf" << EOF
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

    os.chmod(restore_script, 0o755)  # nosec B103

    logger.info(f"Backup script created at {backup_script}")
    logger.info(f"Restore script created at {restore_script}")

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
    config_file = "scripts/wal_archive/postgresql_wal.conf"
    with open(config_file, "w") as f:
        f.write(pg_config)

    logger.info(f"PostgreSQL WAL configuration created at {config_file}")
    logger.info("To enable WAL archiving, include this file in your postgresql.conf")
    logger.info(
        "Example: echo 'include = '/path/to/scripts/wal_archive/postgresql_wal.conf'' >> /etc/postgresql/13/main/postgresql.conf"
    )

    # Create a cron job for regular base backups
    cron_job = "scripts/wal_archive/cron_backup.sh"
    with open(cron_job, "w") as f:
        f.write(
            f"""#!/bin/bash
# WAL-G cron job for regular base backups

# Run the backup script
{os.path.abspath('scripts/wal_archive/backup.sh')}

# Retain backups for 90 days
source {os.path.abspath('scripts/wal_archive/wal-g.env')}
wal-g delete retain FIND_FULL $(( 90 * 24 )) --confirm
"""
        )

    os.chmod(cron_job, 0o755)  # nosec B103

    logger.info(f"Cron job script created at {cron_job}")
    logger.info("To schedule regular backups, add this to crontab:")
    logger.info(
        f"0 1 * * * {os.path.abspath(cron_job)} >> /var/log/wal-g-backup.log 2>&1"
    )

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
    env_file = "scripts/wal_archive/wal-g.env"
    if not os.path.exists(env_file):
        logger.error(f"Environment file {env_file} does not exist")
        return False

    logger.info(f"Environment file {env_file} exists")

    # Test backup script
    backup_script = "scripts/wal_archive/backup.sh"
    if not os.path.exists(backup_script):
        logger.error(f"Backup script {backup_script} does not exist")
        return False

    logger.info(f"Backup script {backup_script} exists")

    # Test restore script
    restore_script = "scripts/wal_archive/restore.sh"
    if not os.path.exists(restore_script):
        logger.error(f"Restore script {restore_script} does not exist")
        return False

    logger.info(f"Restore script {restore_script} exists")

    logger.info("WAL-G setup test completed successfully")
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
    args = parser.parse_args()

    try:
        # Ensure directories exist
        ensure_directories()

        if args.install:
            # Install WAL-G
            if not install_wal_g():
                return 1

        if args.configure:
            # Create WAL-G configuration
            if not create_wal_g_config():
                return 1

            # Configure PostgreSQL
            if not configure_postgresql():
                return 1

        if args.test:
            # Test WAL-G setup
            if not test_wal_g_setup():
                return 1

        if not (args.install or args.configure or args.test):
            # No arguments provided, show help
            parser.print_help()

        return 0

    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
