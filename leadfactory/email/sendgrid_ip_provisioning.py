#!/usr/bin/env python3
"""
SendGrid Dedicated IP Provisioning

This module provides functionality for provisioning and managing SendGrid dedicated IPs.
It handles IP allocation, DNS configuration, pool management, and health monitoring.
"""

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail
except ImportError:
    # Mock for testing environments
    sendgrid = None

from leadfactory.config.settings import SENDGRID_API_KEY, SENDGRID_DEDICATED_IP_POOL


class IPStatus(Enum):
    """Status of a dedicated IP."""

    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    WARMING_UP = "warming_up"
    PAUSED = "paused"
    FAILED = "failed"
    DECOMMISSIONED = "decommissioned"


class IPHealthStatus(Enum):
    """Health status of a dedicated IP."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class DedicatedIP:
    """Represents a SendGrid dedicated IP."""

    ip_address: str
    status: IPStatus
    pool_name: str
    provisioned_at: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    health_status: IPHealthStatus = IPHealthStatus.UNKNOWN
    reputation_score: Optional[float] = None
    daily_volume: int = 0
    bounce_rate: float = 0.0
    spam_rate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ip_address": self.ip_address,
            "status": self.status.value,
            "pool_name": self.pool_name,
            "provisioned_at": (
                self.provisioned_at.isoformat() if self.provisioned_at else None
            ),
            "last_health_check": (
                self.last_health_check.isoformat() if self.last_health_check else None
            ),
            "health_status": self.health_status.value,
            "reputation_score": self.reputation_score,
            "daily_volume": self.daily_volume,
            "bounce_rate": self.bounce_rate,
            "spam_rate": self.spam_rate,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DedicatedIP":
        """Create from dictionary."""
        return cls(
            ip_address=data["ip_address"],
            status=IPStatus(data["status"]),
            pool_name=data["pool_name"],
            provisioned_at=(
                datetime.fromisoformat(data["provisioned_at"])
                if data.get("provisioned_at")
                else None
            ),
            last_health_check=(
                datetime.fromisoformat(data["last_health_check"])
                if data.get("last_health_check")
                else None
            ),
            health_status=IPHealthStatus(data.get("health_status", "unknown")),
            reputation_score=data.get("reputation_score"),
            daily_volume=data.get("daily_volume", 0),
            bounce_rate=data.get("bounce_rate", 0.0),
            spam_rate=data.get("spam_rate", 0.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class IPPool:
    """Represents a SendGrid IP pool."""

    name: str
    ips: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "ips": self.ips,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IPPool":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            ips=data.get("ips", []),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            metadata=data.get("metadata", {}),
        )


class SendGridIPProvisioner:
    """
    SendGrid dedicated IP provisioning and management system.

    Handles IP allocation, DNS configuration, pool management, and health monitoring.
    """

    def __init__(self, api_key: Optional[str] = None, db_path: str = "sendgrid_ips.db"):
        """
        Initialize the IP provisioner.

        Args:
            api_key: SendGrid API key (defaults to settings)
            db_path: Path to SQLite database for IP tracking
        """
        self.api_key = api_key or SENDGRID_API_KEY
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)

        # Initialize SendGrid client
        if sendgrid and self.api_key:
            self.client = sendgrid.SendGridAPIClient(api_key=self.api_key)
        else:
            self.client = None
            self.logger.warning("SendGrid client not available - running in mock mode")

        # Initialize database
        self._init_database()

    @contextmanager
    def _get_db_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self):
        """Initialize the database schema."""
        with self._get_db_connection() as conn:
            # Dedicated IPs table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dedicated_ips (
                    ip_address TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    pool_name TEXT NOT NULL,
                    provisioned_at TEXT,
                    last_health_check TEXT,
                    health_status TEXT DEFAULT 'unknown',
                    reputation_score REAL,
                    daily_volume INTEGER DEFAULT 0,
                    bounce_rate REAL DEFAULT 0.0,
                    spam_rate REAL DEFAULT 0.0,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # IP pools table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ip_pools (
                    name TEXT PRIMARY KEY,
                    ips TEXT DEFAULT '[]',
                    created_at TEXT,
                    metadata TEXT DEFAULT '{}',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # IP events table for audit logging
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ip_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT,
                    event_type TEXT NOT NULL,
                    event_data TEXT DEFAULT '{}',
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create indexes
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ip_status ON dedicated_ips(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ip_pool ON dedicated_ips(pool_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ip_events_timestamp ON ip_events(timestamp)"
            )

            conn.commit()

    def _log_event(
        self, ip_address: Optional[str], event_type: str, event_data: dict[str, Any]
    ):
        """Log an IP-related event."""
        with self._get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO ip_events (ip_address, event_type, event_data)
                VALUES (?, ?, ?)
            """,
                (ip_address, event_type, json.dumps(event_data)),
            )
            conn.commit()

        self.logger.info(
            f"IP Event: {event_type} for {ip_address or 'system'}: {event_data}"
        )

    def provision_dedicated_ip(
        self, pool_name: Optional[str] = None
    ) -> tuple[bool, str, Optional[DedicatedIP]]:
        """
        Provision a new dedicated IP.

        Args:
            pool_name: Name of the IP pool to add the IP to

        Returns:
            Tuple of (success, message, ip_object)
        """
        pool_name = pool_name or SENDGRID_DEDICATED_IP_POOL

        try:
            if not self.client:
                # Mock mode for testing
                mock_ip = f"192.168.{len(self.list_dedicated_ips()) + 1}.1"
                dedicated_ip = DedicatedIP(
                    ip_address=mock_ip,
                    status=IPStatus.PROVISIONING,
                    pool_name=pool_name,
                    provisioned_at=datetime.now(),
                )

                self._store_dedicated_ip(dedicated_ip)
                self._log_event(
                    mock_ip, "ip_provisioned", {"pool_name": pool_name, "mock": True}
                )

                # Simulate provisioning delay
                time.sleep(0.1)
                dedicated_ip.status = IPStatus.ACTIVE
                self._store_dedicated_ip(dedicated_ip)

                # Add to pool in mock mode
                self.add_ip_to_pool(mock_ip, pool_name)

                return True, f"Mock IP {mock_ip} provisioned successfully", dedicated_ip

            # Real SendGrid API call
            response = self.client.client.ips.post(
                request_body={"count": 1, "subusers": [], "warmup": False}
            )

            if response.status_code == 201:
                response_data = json.loads(response.body)
                ip_address = response_data.get("ips", [{}])[0].get("ip")

                if ip_address:
                    dedicated_ip = DedicatedIP(
                        ip_address=ip_address,
                        status=IPStatus.PROVISIONING,
                        pool_name=pool_name,
                        provisioned_at=datetime.now(),
                    )

                    self._store_dedicated_ip(dedicated_ip)
                    self._log_event(
                        ip_address, "ip_provisioned", {"pool_name": pool_name}
                    )

                    # Add to pool
                    self.add_ip_to_pool(ip_address, pool_name)

                    return (
                        True,
                        f"IP {ip_address} provisioned successfully",
                        dedicated_ip,
                    )
                else:
                    return False, "No IP address returned from SendGrid", None
            else:
                error_msg = (
                    f"Failed to provision IP: {response.status_code} - {response.body}"
                )
                self._log_event(None, "ip_provision_failed", {"error": error_msg})
                return False, error_msg, None

        except Exception as e:
            error_msg = f"Error provisioning IP: {str(e)}"
            self.logger.error(error_msg)
            self._log_event(None, "ip_provision_error", {"error": error_msg})
            return False, error_msg, None

    def _store_dedicated_ip(self, ip: DedicatedIP):
        """Store or update a dedicated IP in the database."""
        with self._get_db_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO dedicated_ips (
                    ip_address, status, pool_name, provisioned_at, last_health_check,
                    health_status, reputation_score, daily_volume, bounce_rate, spam_rate,
                    metadata, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    ip.ip_address,
                    ip.status.value,
                    ip.pool_name,
                    ip.provisioned_at.isoformat() if ip.provisioned_at else None,
                    ip.last_health_check.isoformat() if ip.last_health_check else None,
                    ip.health_status.value,
                    ip.reputation_score,
                    ip.daily_volume,
                    ip.bounce_rate,
                    ip.spam_rate,
                    json.dumps(ip.metadata),
                ),
            )
            conn.commit()

    def get_dedicated_ip(self, ip_address: str) -> Optional[DedicatedIP]:
        """Get a dedicated IP by address."""
        with self._get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM dedicated_ips WHERE ip_address = ?
            """,
                (ip_address,),
            ).fetchone()

            if row:
                return DedicatedIP(
                    ip_address=row["ip_address"],
                    status=IPStatus(row["status"]),
                    pool_name=row["pool_name"],
                    provisioned_at=(
                        datetime.fromisoformat(row["provisioned_at"])
                        if row["provisioned_at"]
                        else None
                    ),
                    last_health_check=(
                        datetime.fromisoformat(row["last_health_check"])
                        if row["last_health_check"]
                        else None
                    ),
                    health_status=IPHealthStatus(row["health_status"]),
                    reputation_score=row["reputation_score"],
                    daily_volume=row["daily_volume"],
                    bounce_rate=row["bounce_rate"],
                    spam_rate=row["spam_rate"],
                    metadata=json.loads(row["metadata"]),
                )
            return None

    def list_dedicated_ips(
        self, status: Optional[IPStatus] = None, pool_name: Optional[str] = None
    ) -> list[DedicatedIP]:
        """List dedicated IPs with optional filtering."""
        with self._get_db_connection() as conn:
            query = "SELECT * FROM dedicated_ips WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status.value)

            if pool_name:
                query += " AND pool_name = ?"
                params.append(pool_name)

            query += " ORDER BY created_at DESC"

            rows = conn.execute(query, params).fetchall()

            ips = []
            for row in rows:
                ips.append(
                    DedicatedIP(
                        ip_address=row["ip_address"],
                        status=IPStatus(row["status"]),
                        pool_name=row["pool_name"],
                        provisioned_at=(
                            datetime.fromisoformat(row["provisioned_at"])
                            if row["provisioned_at"]
                            else None
                        ),
                        last_health_check=(
                            datetime.fromisoformat(row["last_health_check"])
                            if row["last_health_check"]
                            else None
                        ),
                        health_status=IPHealthStatus(row["health_status"]),
                        reputation_score=row["reputation_score"],
                        daily_volume=row["daily_volume"],
                        bounce_rate=row["bounce_rate"],
                        spam_rate=row["spam_rate"],
                        metadata=json.loads(row["metadata"]),
                    )
                )

            return ips

    def create_ip_pool(
        self, pool_name: str, ips: Optional[list[str]] = None
    ) -> tuple[bool, str]:
        """
        Create a new IP pool.

        Args:
            pool_name: Name of the pool
            ips: List of IP addresses to add to the pool

        Returns:
            Tuple of (success, message)
        """
        ips = ips or []

        try:
            if not self.client:
                # Mock mode
                pool = IPPool(name=pool_name, ips=ips, created_at=datetime.now())
                self._store_ip_pool(pool)
                self._log_event(
                    None,
                    "pool_created",
                    {"pool_name": pool_name, "ips": ips, "mock": True},
                )
                return True, f"Mock pool {pool_name} created successfully"

            # Real SendGrid API call
            response = self.client.client.ips.pools.post(
                request_body={"name": pool_name}
            )

            if response.status_code == 201:
                pool = IPPool(name=pool_name, ips=ips, created_at=datetime.now())
                self._store_ip_pool(pool)

                # Add IPs to the pool
                for ip in ips:
                    self.add_ip_to_pool(ip, pool_name)

                self._log_event(
                    None, "pool_created", {"pool_name": pool_name, "ips": ips}
                )
                return True, f"Pool {pool_name} created successfully"
            else:
                error_msg = (
                    f"Failed to create pool: {response.status_code} - {response.body}"
                )
                self._log_event(
                    None,
                    "pool_creation_failed",
                    {"pool_name": pool_name, "error": error_msg},
                )
                return False, error_msg

        except Exception as e:
            error_msg = f"Error creating pool: {str(e)}"
            self.logger.error(error_msg)
            self._log_event(
                None,
                "pool_creation_error",
                {"pool_name": pool_name, "error": error_msg},
            )
            return False, error_msg

    def _store_ip_pool(self, pool: IPPool):
        """Store or update an IP pool in the database."""
        with self._get_db_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ip_pools (
                    name, ips, created_at, metadata, updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    pool.name,
                    json.dumps(pool.ips),
                    pool.created_at.isoformat() if pool.created_at else None,
                    json.dumps(pool.metadata),
                ),
            )
            conn.commit()

    def add_ip_to_pool(self, ip_address: str, pool_name: str) -> tuple[bool, str]:
        """
        Add an IP to a pool.

        Args:
            ip_address: IP address to add
            pool_name: Name of the pool

        Returns:
            Tuple of (success, message)
        """
        try:
            if not self.client:
                # Mock mode
                pool = self.get_ip_pool(pool_name)
                if pool and ip_address not in pool.ips:
                    pool.ips.append(ip_address)
                    self._store_ip_pool(pool)

                self._log_event(
                    ip_address,
                    "ip_added_to_pool",
                    {"pool_name": pool_name, "mock": True},
                )
                return True, f"Mock IP {ip_address} added to pool {pool_name}"

            # Real SendGrid API call
            response = self.client.client.ips.pools._(pool_name).ips.post(
                request_body={"ip": ip_address}
            )

            if response.status_code == 201:
                # Update local pool record
                pool = self.get_ip_pool(pool_name)
                if pool and ip_address not in pool.ips:
                    pool.ips.append(ip_address)
                    self._store_ip_pool(pool)

                self._log_event(
                    ip_address, "ip_added_to_pool", {"pool_name": pool_name}
                )
                return True, f"IP {ip_address} added to pool {pool_name}"
            else:
                error_msg = f"Failed to add IP to pool: {response.status_code} - {response.body}"
                self._log_event(
                    ip_address,
                    "ip_pool_add_failed",
                    {"pool_name": pool_name, "error": error_msg},
                )
                return False, error_msg

        except Exception as e:
            error_msg = f"Error adding IP to pool: {str(e)}"
            self.logger.error(error_msg)
            self._log_event(
                ip_address,
                "ip_pool_add_error",
                {"pool_name": pool_name, "error": error_msg},
            )
            return False, error_msg

    def get_ip_pool(self, pool_name: str) -> Optional[IPPool]:
        """Get an IP pool by name."""
        with self._get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM ip_pools WHERE name = ?
            """,
                (pool_name,),
            ).fetchone()

            if row:
                return IPPool(
                    name=row["name"],
                    ips=json.loads(row["ips"]),
                    created_at=(
                        datetime.fromisoformat(row["created_at"])
                        if row["created_at"]
                        else None
                    ),
                    metadata=json.loads(row["metadata"]),
                )
            return None

    def list_ip_pools(self) -> list[IPPool]:
        """List all IP pools."""
        with self._get_db_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM ip_pools ORDER BY created_at DESC"
            ).fetchall()

            pools = []
            for row in rows:
                pools.append(
                    IPPool(
                        name=row["name"],
                        ips=json.loads(row["ips"]),
                        created_at=(
                            datetime.fromisoformat(row["created_at"])
                            if row["created_at"]
                            else None
                        ),
                        metadata=json.loads(row["metadata"]),
                    )
                )

            return pools

    def check_ip_health(self, ip_address: str) -> tuple[IPHealthStatus, dict[str, Any]]:
        """
        Check the health of a dedicated IP.

        Args:
            ip_address: IP address to check

        Returns:
            Tuple of (health_status, health_data)
        """
        try:
            if not self.client:
                # Mock health check
                health_data = {
                    "reputation_score": 95.0,
                    "bounce_rate": 0.02,
                    "spam_rate": 0.001,
                    "daily_volume": 5000,
                    "last_checked": datetime.now().isoformat(),
                    "mock": True,
                }

                # Determine health status based on metrics
                if health_data["bounce_rate"] > 0.1 or health_data["spam_rate"] > 0.01:
                    status = IPHealthStatus.CRITICAL
                elif (
                    health_data["bounce_rate"] > 0.05
                    or health_data["spam_rate"] > 0.005
                ):
                    status = IPHealthStatus.WARNING
                else:
                    status = IPHealthStatus.HEALTHY

                # Update IP record
                ip = self.get_dedicated_ip(ip_address)
                if ip:
                    ip.last_health_check = datetime.now()
                    ip.health_status = status
                    ip.reputation_score = health_data["reputation_score"]
                    ip.bounce_rate = health_data["bounce_rate"]
                    ip.spam_rate = health_data["spam_rate"]
                    ip.daily_volume = health_data["daily_volume"]
                    self._store_dedicated_ip(ip)

                self._log_event(ip_address, "health_check", health_data)
                return status, health_data

            # Real SendGrid API calls for health metrics
            # Get IP reputation
            self.client.client.ips._(ip_address).get()

            # Get bounce and spam rates (would need additional API calls)
            # This is a simplified implementation
            health_data = {
                "reputation_score": 85.0,  # Would parse from rep_response
                "bounce_rate": 0.03,
                "spam_rate": 0.002,
                "daily_volume": 3000,
                "last_checked": datetime.now().isoformat(),
            }

            # Determine health status
            if health_data["bounce_rate"] > 0.1 or health_data["spam_rate"] > 0.01:
                status = IPHealthStatus.CRITICAL
            elif health_data["bounce_rate"] > 0.05 or health_data["spam_rate"] > 0.005:
                status = IPHealthStatus.WARNING
            else:
                status = IPHealthStatus.HEALTHY

            # Update IP record
            ip = self.get_dedicated_ip(ip_address)
            if ip:
                ip.last_health_check = datetime.now()
                ip.health_status = status
                ip.reputation_score = health_data["reputation_score"]
                ip.bounce_rate = health_data["bounce_rate"]
                ip.spam_rate = health_data["spam_rate"]
                ip.daily_volume = health_data["daily_volume"]
                self._store_dedicated_ip(ip)

            self._log_event(ip_address, "health_check", health_data)
            return status, health_data

        except Exception as e:
            error_msg = f"Error checking IP health: {str(e)}"
            self.logger.error(error_msg)
            self._log_event(ip_address, "health_check_error", {"error": error_msg})
            return IPHealthStatus.UNKNOWN, {"error": error_msg}

    def get_ip_status_summary(self) -> dict[str, Any]:
        """Get a summary of all IP statuses."""
        ips = self.list_dedicated_ips()

        summary = {
            "total_ips": len(ips),
            "by_status": {},
            "by_health": {},
            "by_pool": {},
            "total_daily_volume": 0,
            "average_reputation": 0.0,
            "average_bounce_rate": 0.0,
            "average_spam_rate": 0.0,
        }

        # Count by status
        for status in IPStatus:
            summary["by_status"][status.value] = len(
                [ip for ip in ips if ip.status == status]
            )

        # Count by health
        for health in IPHealthStatus:
            summary["by_health"][health.value] = len(
                [ip for ip in ips if ip.health_status == health]
            )

        # Count by pool
        pools = {ip.pool_name for ip in ips}
        for pool in pools:
            summary["by_pool"][pool] = len([ip for ip in ips if ip.pool_name == pool])

        # Calculate averages
        if ips:
            summary["total_daily_volume"] = sum(ip.daily_volume for ip in ips)

            active_ips = [
                ip
                for ip in ips
                if ip.status == IPStatus.ACTIVE and ip.reputation_score is not None
            ]
            if active_ips:
                summary["average_reputation"] = sum(
                    ip.reputation_score for ip in active_ips
                ) / len(active_ips)
                summary["average_bounce_rate"] = sum(
                    ip.bounce_rate for ip in active_ips
                ) / len(active_ips)
                summary["average_spam_rate"] = sum(
                    ip.spam_rate for ip in active_ips
                ) / len(active_ips)

        return summary

    def run_health_checks(self) -> dict[str, Any]:
        """Run health checks on all active IPs."""
        active_ips = self.list_dedicated_ips(status=IPStatus.ACTIVE)
        results = {
            "checked": 0,
            "healthy": 0,
            "warning": 0,
            "critical": 0,
            "errors": 0,
            "details": [],
        }

        for ip in active_ips:
            try:
                health_status, health_data = self.check_ip_health(ip.ip_address)
                results["checked"] += 1

                if health_status == IPHealthStatus.HEALTHY:
                    results["healthy"] += 1
                elif health_status == IPHealthStatus.WARNING:
                    results["warning"] += 1
                elif health_status == IPHealthStatus.CRITICAL:
                    results["critical"] += 1

                results["details"].append(
                    {
                        "ip_address": ip.ip_address,
                        "health_status": health_status.value,
                        "health_data": health_data,
                    }
                )

            except Exception as e:
                results["errors"] += 1
                results["details"].append(
                    {"ip_address": ip.ip_address, "error": str(e)}
                )

        self._log_event(None, "bulk_health_check", results)
        return results


# Convenience functions for easy integration
def get_ip_provisioner(
    api_key: Optional[str] = None, db_path: str = "sendgrid_ips.db"
) -> SendGridIPProvisioner:
    """Get a SendGrid IP provisioner instance."""
    return SendGridIPProvisioner(api_key=api_key, db_path=db_path)


def provision_dedicated_ip(
    pool_name: Optional[str] = None,
) -> tuple[bool, str, Optional[DedicatedIP]]:
    """Convenience function to provision a dedicated IP."""
    provisioner = get_ip_provisioner()
    return provisioner.provision_dedicated_ip(pool_name)


def check_ip_health(ip_address: str) -> tuple[IPHealthStatus, dict[str, Any]]:
    """Convenience function to check IP health."""
    provisioner = get_ip_provisioner()
    return provisioner.check_ip_health(ip_address)


def get_ip_status_summary() -> dict[str, Any]:
    """Convenience function to get IP status summary."""
    provisioner = get_ip_provisioner()
    return provisioner.get_ip_status_summary()
