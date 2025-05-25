#!/usr/bin/env python
"""
Health Check System
----------------
This module provides a health check system for the Anthrasite LeadFactory
platform. It monitors the health of various components and triggers failover
to the backup VPS if necessary.

Usage:
    python bin/health_check.py --check-all
"""

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Any

# Use lowercase versions for Python 3.9 compatibility
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(Path("logs") / "health_check.log")),
    ],
)
logger = logging.getLogger("health_check")


class HealthCheckSystem:
    """Health check system for LeadFactory."""

    def __init__(self):
        """Initialize health check system."""
        # Load configuration from environment variables
        self.primary_host = os.environ.get("PRIMARY_HOST", "localhost")
        self.backup_host = os.environ.get("BACKUP_HOST", "")
        self.failure_threshold = int(
            os.environ.get("HEALTH_CHECK_FAILURES_THRESHOLD", "2")
        )
        self.check_interval = int(
            os.environ.get("HEALTH_CHECK_INTERVAL", "300")
        )  # 5 minutes
        self.notification_email = os.environ.get("NOTIFICATION_EMAIL", "")
        self.notification_slack_webhook = os.environ.get(
            "NOTIFICATION_SLACK_WEBHOOK", ""
        )

        # Initialize state
        self.failure_count = 0
        self.last_check_time = None
        self.last_check_status = None
        self.failover_active = False
        self.failover_time = None

        # Initialize checks
        self.checks = {
            "docker": self._check_docker,
            "database": self._check_database,
            "api": self._check_api,
            "disk": self._check_disk_space,
            "memory": self._check_memory,
            "network": self._check_network,
        }

        logger.info(
            f"Health check system initialized (failure_threshold={self.failure_threshold}, check_interval={self.check_interval}s)"
        )

    def check_all(self) -> bool:
        """Run all health checks.

        Returns:
            True if all checks pass, False otherwise
        """
        logger.info("Running all health checks")

        self.last_check_time = datetime.now()
        all_passed = True
        results = {}

        for name, check_func in self.checks.items():
            try:
                passed, details = check_func()
                results[name] = {"passed": passed, "details": details}

                if not passed:
                    all_passed = False
                    logger.warning(f"Health check '{name}' failed: {details}")
                else:
                    logger.info(f"Health check '{name}' passed: {details}")
            except Exception as e:
                all_passed = False
                results[name] = {"passed": False, "details": f"Error: {str(e)}"}
                logger.exception(f"Error running health check '{name}': {e}")

        # Update state
        self.last_check_status = all_passed

        if all_passed:
            # Reset failure count on success
            self.failure_count = 0
        else:
            # Increment failure count
            self.failure_count += 1

            # Check if failover should be triggered
            if self.failure_count >= self.failure_threshold:
                logger.critical(
                    f"Health check failure threshold reached ({self.failure_count}/{self.failure_threshold}), triggering failover"
                )
                self._trigger_failover()

        # Save results to file
        self._save_results(results)

        return all_passed

    def _check_docker(self) -> tuple:
        """Check if Docker is running.

        Returns:
            tuple of (passed, details)
        """
        try:
            # Run docker ps command
            result = subprocess.run(
                ["docker", "ps"], capture_output=True, text=True, check=False
            )

            if result.returncode == 0:
                # Count running containers
                container_count = len(result.stdout.strip().split("\n")) - 1
                return True, f"{container_count} containers running"
            else:
                return False, f"Docker not running: {result.stderr.strip()}"
        except Exception as e:
            return False, f"Error checking Docker: {str(e)}"

    def _check_database(self) -> tuple:
        """Check if database is accessible.

        Returns:
            tuple of (passed, details)
        """
        try:
            # Try to connect to PostgreSQL
            import psycopg2

            host = os.environ.get("DB_HOST", "localhost")
            port = int(os.environ.get("DB_PORT", "5432"))
            user = os.environ.get("DB_USER", "postgres")
            password = os.environ.get("DB_PASSWORD", "")
            dbname = os.environ.get("DB_NAME", "postgres")

            conn = psycopg2.connect(
                host=host, port=port, user=user, password=password, dbname=dbname
            )

            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            return True, f"Database accessible: {version}"
        except ImportError:
            # Psycopg2 not installed, try a simple socket check
            host = os.environ.get("DB_HOST", "localhost")
            port = int(os.environ.get("DB_PORT", "5432"))

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                return True, f"Database port {port} is open"
            else:
                return False, f"Database port {port} is closed"
        except Exception as e:
            return False, f"Error connecting to database: {str(e)}"

    def _check_api(self) -> tuple:
        """Check if API is accessible.

        Returns:
            tuple of (passed, details)
        """
        try:
            # Try to connect to API
            api_url = os.environ.get("API_URL", "http://localhost:8000/health")

            response = requests.get(api_url, timeout=5)

            if response.status_code == 200:
                return True, f"API accessible: {response.text.strip()}"
            else:
                return False, f"API returned status code {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, f"Error connecting to API: {str(e)}"

    def _check_disk_space(self) -> tuple:
        """Check if disk space is sufficient.

        Returns:
            tuple of (passed, details)
        """
        try:
            # Get disk usage
            import shutil

            total, used, free = shutil.disk_usage("/")

            # Convert to GB
            total / (1024**3)
            used / (1024**3)
            free_gb = free / (1024**3)

            # Calculate percentage used
            percent_used = (used / total) * 100

            # Check if disk space is sufficient (less than 90% used)
            if percent_used < 90:
                return (
                    True,
                    f"Disk space sufficient: {free_gb:.1f} GB free ({percent_used:.1f}% used)",
                )
            else:
                return (
                    False,
                    f"Disk space low: {free_gb:.1f} GB free ({percent_used:.1f}% used)",
                )
        except Exception as e:
            return False, f"Error checking disk space: {str(e)}"

    def _check_memory(self) -> tuple:
        """Check if memory is sufficient.

        Returns:
            tuple of (passed, details)
        """
        try:
            # Get memory usage
            import psutil

            memory = psutil.virtual_memory()

            # Convert to GB
            memory.total / (1024**3)
            memory.used / (1024**3)
            free_gb = memory.available / (1024**3)

            # Calculate percentage used
            percent_used = memory.percent

            # Check if memory is sufficient (less than 90% used)
            if percent_used < 90:
                return (
                    True,
                    f"Memory sufficient: {free_gb:.1f} GB free ({percent_used:.1f}% used)",
                )
            else:
                return (
                    False,
                    f"Memory low: {free_gb:.1f} GB free ({percent_used:.1f}% used)",
                )
        except ImportError:
            # Psutil not installed, try reading from /proc/meminfo
            try:
                with Path("/proc/meminfo").open() as f:
                    meminfo = {}
                    for line in f:
                        key, value = line.split(":", 1)
                        meminfo[key.strip()] = int(value.strip().split()[0])

                total_kb = meminfo.get("MemTotal", 0)
                free_kb = meminfo.get("MemFree", 0)
                buffers_kb = meminfo.get("Buffers", 0)
                cached_kb = meminfo.get("Cached", 0)

                # Calculate available memory
                available_kb = free_kb + buffers_kb + cached_kb

                # Convert to GB
                total_kb / (1024**2)
                available_gb = available_kb / (1024**2)

                # Calculate percentage used
                percent_used = ((total_kb - available_kb) / total_kb) * 100

                # Check if memory is sufficient (less than 90% used)
                if percent_used < 90:
                    return (
                        True,
                        f"Memory sufficient: {available_gb:.1f} GB free ({percent_used:.1f}% used)",
                    )
                else:
                    return (
                        False,
                        f"Memory low: {available_gb:.1f} GB free ({percent_used:.1f}% used)",
                    )
            except Exception as e:
                return False, f"Error reading memory info: {str(e)}"
        except Exception as e:
            return False, f"Error checking memory: {str(e)}"

    def _check_network(self) -> tuple:
        """Check if network is accessible.

        Returns:
            tuple of (passed, details)
        """
        try:
            # Ping Google DNS
            result = subprocess.run(
                ["ping", "-c", "1", "8.8.8.8"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                return True, "Network accessible"
            else:
                return False, f"Network not accessible: {result.stderr.strip()}"
        except Exception as e:
            return False, f"Error checking network: {str(e)}"

    def _trigger_failover(self):
        """Trigger failover to backup VPS."""
        if self.failover_active:
            logger.warning("Failover already active, skipping")
            return

        if not self.backup_host:
            logger.error("Backup host not configured, cannot trigger failover")
            return

        try:
            logger.critical("Triggering failover to backup VPS")

            # Set failover state
            self.failover_active = True
            self.failover_time = datetime.now()

            # Send notification
            self._send_notification(
                subject="LeadFactory Failover Triggered",
                message=f"Failover triggered at {self.failover_time.isoformat()} due to {self.failure_count} consecutive health check failures.",
            )

            # Call failover script on backup VPS
            if Path("/usr/local/bin/trigger_failover.sh").exists():
                result = subprocess.run(
                    ["/usr/local/bin/trigger_failover.sh"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode == 0:
                    logger.info(
                        f"Failover script executed successfully: {result.stdout.strip()}"
                    )
                else:
                    logger.error(f"Failover script failed: {result.stderr.strip()}")
            else:
                logger.warning(
                    "Failover script not found at /usr/local/bin/trigger_failover.sh"
                )

                # Try SSH to backup VPS
                ssh_command_list = [
                    "ssh",
                    self.backup_host,
                    "sudo /usr/local/bin/activate_failover.sh",
                ]
                result = subprocess.run(
                    ssh_command_list, capture_output=True, text=True, check=False
                )

                if result.returncode == 0:
                    logger.info(
                        f"Failover activated on backup VPS: {result.stdout.strip()}"
                    )
                else:
                    logger.error(
                        f"Failed to activate failover on backup VPS: {result.stderr.strip()}"
                    )
        except Exception as e:
            logger.exception(f"Error triggering failover: {e}")

    def _send_notification(self, subject: str, message: str):
        """Send a notification.

        Args:
            subject: Notification subject
            message: Notification message
        """
        try:
            # Send email notification
            if self.notification_email:
                import smtplib
                from email.mime.text import MIMEText

                smtp_host = os.environ.get("SMTP_HOST", "localhost")
                smtp_port = int(os.environ.get("SMTP_PORT", "25"))
                smtp_user = os.environ.get("SMTP_USER", "")
                smtp_password = os.environ.get("SMTP_PASSWORD", "")

                msg = MIMEText(message)
                msg["Subject"] = subject
                msg["From"] = os.environ.get("SMTP_FROM", "leadfactory@localhost")
                msg["To"] = self.notification_email

                try:
                    smtp = smtplib.SMTP(smtp_host, smtp_port)

                    if smtp_user and smtp_password:
                        smtp.login(smtp_user, smtp_password)

                    smtp.send_message(msg)
                    smtp.quit()

                    logger.info(f"Email notification sent to {self.notification_email}")
                except Exception as e:
                    logger.error(f"Error sending email notification: {str(e)}")

            # Send Slack notification
            if self.notification_slack_webhook:
                try:
                    payload = {"text": f"*{subject}*\n{message}"}

                    response = requests.post(
                        self.notification_slack_webhook,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=30,  # Added timeout
                    )

                    if response.status_code == 200:
                        logger.info("Slack notification sent")
                    else:
                        logger.error(
                            f"Error sending Slack notification: {response.status_code} {response.text}"
                        )
                except Exception as e:
                    logger.error(f"Error sending Slack notification: {str(e)}")
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")

    def _save_results(self, results: dict[str, Any]):
        """Save health check results to file.

        Args:
            results: Health check results
        """
        try:
            # Create results directory if it doesn't exist
            Path("data/health_checks").mkdir(parents=True, exist_ok=True)

            # Create results file
            filename = f"data/health_checks/health_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            with Path(filename).open("w") as f:
                json.dump(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "passed": self.last_check_status,
                        "failure_count": self.failure_count,
                        "failover_active": self.failover_active,
                        "failover_time": (
                            self.failover_time.isoformat()
                            if self.failover_time
                            else None
                        ),
                        "results": results,
                    },
                    f,
                    indent=2,
                )

            logger.info(f"Health check results saved to {filename}")

            # Create a symlink to the latest results
            latest_link = "data/health_checks/latest.json"

            latest_link_path = Path(latest_link)
            if latest_link_path.exists():
                latest_link_path.unlink()

            # Create a symlink to the latest health check
            os.symlink(Path(filename).resolve(), latest_link)
        except Exception as e:
            logger.error(f"Error saving health check results: {str(e)}")

    def start_monitoring(self):
        """Start continuous health check monitoring."""

        def monitoring_thread():
            while True:
                try:
                    # Run health checks
                    self.check_all()
                except Exception as e:
                    logger.exception(f"Error in monitoring thread: {e}")

                # Sleep until next check
                time.sleep(self.check_interval)

        # Start thread
        thread = threading.Thread(target=monitoring_thread, daemon=True)
        thread.start()
        logger.info(
            f"Started health check monitoring (interval={self.check_interval}s)"
        )

        return thread


# Create a singleton instance
health_check = HealthCheckSystem()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Health Check System")
    parser.add_argument(
        "--check-all", action="store_true", help="Run all health checks"
    )
    parser.add_argument(
        "--monitor", action="store_true", help="Start continuous monitoring"
    )
    parser.add_argument(
        "--trigger-failover", action="store_true", help="Trigger failover to backup VPS"
    )
    args = parser.parse_args()

    try:
        if args.check_all:
            # Run all health checks
            passed = health_check.check_all()

            if passed:
                return 0
            else:
                return 1

        elif args.monitor:
            # Start continuous monitoring
            health_check.start_monitoring()

            # Keep main thread alive
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

        elif args.trigger_failover:
            # Trigger failover
            health_check._trigger_failover()

        else:
            # Show help
            parser.print_help()

        return 0

    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
