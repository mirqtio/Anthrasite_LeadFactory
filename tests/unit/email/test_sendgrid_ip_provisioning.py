#!/usr/bin/env python3
"""
Unit tests for SendGrid IP provisioning system.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from leadfactory.email.sendgrid_ip_provisioning import (
    DedicatedIP,
    IPHealthStatus,
    IPPool,
    IPStatus,
    SendGridIPProvisioner,
    check_ip_health,
    get_ip_provisioner,
    get_ip_status_summary,
    provision_dedicated_ip,
)


class TestDedicatedIP(unittest.TestCase):
    """Test DedicatedIP dataclass."""

    def test_dedicated_ip_creation(self):
        """Test creating a DedicatedIP instance."""
        ip = DedicatedIP(
            ip_address="192.168.1.1", status=IPStatus.ACTIVE, pool_name="test-pool"
        )

        self.assertEqual(ip.ip_address, "192.168.1.1")
        self.assertEqual(ip.status, IPStatus.ACTIVE)
        self.assertEqual(ip.pool_name, "test-pool")
        self.assertEqual(ip.health_status, IPHealthStatus.UNKNOWN)
        self.assertEqual(ip.daily_volume, 0)
        self.assertEqual(ip.bounce_rate, 0.0)
        self.assertEqual(ip.spam_rate, 0.0)

    def test_dedicated_ip_to_dict(self):
        """Test converting DedicatedIP to dictionary."""
        now = datetime.now()
        ip = DedicatedIP(
            ip_address="192.168.1.1",
            status=IPStatus.ACTIVE,
            pool_name="test-pool",
            provisioned_at=now,
            health_status=IPHealthStatus.HEALTHY,
            reputation_score=95.0,
            daily_volume=1000,
            bounce_rate=0.02,
            spam_rate=0.001,
            metadata={"test": "value"},
        )

        data = ip.to_dict()

        self.assertEqual(data["ip_address"], "192.168.1.1")
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["pool_name"], "test-pool")
        self.assertEqual(data["provisioned_at"], now.isoformat())
        self.assertEqual(data["health_status"], "healthy")
        self.assertEqual(data["reputation_score"], 95.0)
        self.assertEqual(data["daily_volume"], 1000)
        self.assertEqual(data["bounce_rate"], 0.02)
        self.assertEqual(data["spam_rate"], 0.001)
        self.assertEqual(data["metadata"], {"test": "value"})

    def test_dedicated_ip_from_dict(self):
        """Test creating DedicatedIP from dictionary."""
        now = datetime.now()
        data = {
            "ip_address": "192.168.1.1",
            "status": "active",
            "pool_name": "test-pool",
            "provisioned_at": now.isoformat(),
            "health_status": "healthy",
            "reputation_score": 95.0,
            "daily_volume": 1000,
            "bounce_rate": 0.02,
            "spam_rate": 0.001,
            "metadata": {"test": "value"},
        }

        ip = DedicatedIP.from_dict(data)

        self.assertEqual(ip.ip_address, "192.168.1.1")
        self.assertEqual(ip.status, IPStatus.ACTIVE)
        self.assertEqual(ip.pool_name, "test-pool")
        self.assertEqual(ip.provisioned_at, now)
        self.assertEqual(ip.health_status, IPHealthStatus.HEALTHY)
        self.assertEqual(ip.reputation_score, 95.0)
        self.assertEqual(ip.daily_volume, 1000)
        self.assertEqual(ip.bounce_rate, 0.02)
        self.assertEqual(ip.spam_rate, 0.001)
        self.assertEqual(ip.metadata, {"test": "value"})


class TestIPPool(unittest.TestCase):
    """Test IPPool dataclass."""

    def test_ip_pool_creation(self):
        """Test creating an IPPool instance."""
        pool = IPPool(name="test-pool", ips=["192.168.1.1", "192.168.1.2"])

        self.assertEqual(pool.name, "test-pool")
        self.assertEqual(pool.ips, ["192.168.1.1", "192.168.1.2"])
        self.assertIsNone(pool.created_at)
        self.assertEqual(pool.metadata, {})

    def test_ip_pool_to_dict(self):
        """Test converting IPPool to dictionary."""
        now = datetime.now()
        pool = IPPool(
            name="test-pool",
            ips=["192.168.1.1", "192.168.1.2"],
            created_at=now,
            metadata={"test": "value"},
        )

        data = pool.to_dict()

        self.assertEqual(data["name"], "test-pool")
        self.assertEqual(data["ips"], ["192.168.1.1", "192.168.1.2"])
        self.assertEqual(data["created_at"], now.isoformat())
        self.assertEqual(data["metadata"], {"test": "value"})

    def test_ip_pool_from_dict(self):
        """Test creating IPPool from dictionary."""
        now = datetime.now()
        data = {
            "name": "test-pool",
            "ips": ["192.168.1.1", "192.168.1.2"],
            "created_at": now.isoformat(),
            "metadata": {"test": "value"},
        }

        pool = IPPool.from_dict(data)

        self.assertEqual(pool.name, "test-pool")
        self.assertEqual(pool.ips, ["192.168.1.1", "192.168.1.2"])
        self.assertEqual(pool.created_at, now)
        self.assertEqual(pool.metadata, {"test": "value"})


class TestSendGridIPProvisioner(unittest.TestCase):
    """Test SendGridIPProvisioner class."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Create provisioner instance
        self.provisioner = SendGridIPProvisioner(
            api_key="test-key", db_path=self.db_path
        )

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary database file
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_provisioner_initialization(self):
        """Test provisioner initialization."""
        self.assertEqual(self.provisioner.api_key, "test-key")
        self.assertEqual(self.provisioner.db_path, self.db_path)
        self.assertIsNone(self.provisioner.client)  # Should be None in test mode

    def test_database_initialization(self):
        """Test database schema creation."""
        # Database should be initialized in setUp
        with self.provisioner._get_db_connection() as conn:
            # Check that tables exist
            tables = conn.execute("""
                SELECT name FROM sqlite_master WHERE type='table'
            """).fetchall()

            table_names = [table[0] for table in tables]
            self.assertIn("dedicated_ips", table_names)
            self.assertIn("ip_pools", table_names)
            self.assertIn("ip_events", table_names)

    def test_provision_dedicated_ip_mock(self):
        """Test provisioning a dedicated IP in mock mode."""
        success, message, ip = self.provisioner.provision_dedicated_ip("test-pool")

        self.assertTrue(success)
        self.assertIn("provisioned successfully", message)
        self.assertIsNotNone(ip)
        self.assertEqual(ip.status, IPStatus.ACTIVE)
        self.assertEqual(ip.pool_name, "test-pool")
        self.assertIsNotNone(ip.provisioned_at)

    def test_store_and_get_dedicated_ip(self):
        """Test storing and retrieving a dedicated IP."""
        ip = DedicatedIP(
            ip_address="192.168.1.1",
            status=IPStatus.ACTIVE,
            pool_name="test-pool",
            provisioned_at=datetime.now(),
            health_status=IPHealthStatus.HEALTHY,
            reputation_score=95.0,
        )

        # Store IP
        self.provisioner._store_dedicated_ip(ip)

        # Retrieve IP
        retrieved_ip = self.provisioner.get_dedicated_ip("192.168.1.1")

        self.assertIsNotNone(retrieved_ip)
        self.assertEqual(retrieved_ip.ip_address, "192.168.1.1")
        self.assertEqual(retrieved_ip.status, IPStatus.ACTIVE)
        self.assertEqual(retrieved_ip.pool_name, "test-pool")
        self.assertEqual(retrieved_ip.health_status, IPHealthStatus.HEALTHY)
        self.assertEqual(retrieved_ip.reputation_score, 95.0)

    def test_list_dedicated_ips(self):
        """Test listing dedicated IPs."""
        # Create test IPs
        ip1 = DedicatedIP("192.168.1.1", IPStatus.ACTIVE, "pool1")
        ip2 = DedicatedIP("192.168.1.2", IPStatus.PROVISIONING, "pool2")
        ip3 = DedicatedIP("192.168.1.3", IPStatus.ACTIVE, "pool1")

        # Store IPs
        self.provisioner._store_dedicated_ip(ip1)
        self.provisioner._store_dedicated_ip(ip2)
        self.provisioner._store_dedicated_ip(ip3)

        # List all IPs
        all_ips = self.provisioner.list_dedicated_ips()
        self.assertEqual(len(all_ips), 3)

        # List by status
        active_ips = self.provisioner.list_dedicated_ips(status=IPStatus.ACTIVE)
        self.assertEqual(len(active_ips), 2)

        # List by pool
        pool1_ips = self.provisioner.list_dedicated_ips(pool_name="pool1")
        self.assertEqual(len(pool1_ips), 2)

    def test_create_ip_pool_mock(self):
        """Test creating an IP pool in mock mode."""
        success, message = self.provisioner.create_ip_pool("test-pool", ["192.168.1.1"])

        self.assertTrue(success)
        self.assertIn("created successfully", message)

        # Verify pool was stored
        pool = self.provisioner.get_ip_pool("test-pool")
        self.assertIsNotNone(pool)
        self.assertEqual(pool.name, "test-pool")
        self.assertEqual(pool.ips, ["192.168.1.1"])

    def test_store_and_get_ip_pool(self):
        """Test storing and retrieving an IP pool."""
        pool = IPPool(
            name="test-pool",
            ips=["192.168.1.1", "192.168.1.2"],
            created_at=datetime.now(),
            metadata={"test": "value"},
        )

        # Store pool
        self.provisioner._store_ip_pool(pool)

        # Retrieve pool
        retrieved_pool = self.provisioner.get_ip_pool("test-pool")

        self.assertIsNotNone(retrieved_pool)
        self.assertEqual(retrieved_pool.name, "test-pool")
        self.assertEqual(retrieved_pool.ips, ["192.168.1.1", "192.168.1.2"])
        self.assertEqual(retrieved_pool.metadata, {"test": "value"})

    def test_add_ip_to_pool_mock(self):
        """Test adding an IP to a pool in mock mode."""
        # Create pool first
        self.provisioner.create_ip_pool("test-pool", [])

        # Add IP to pool
        success, message = self.provisioner.add_ip_to_pool("192.168.1.1", "test-pool")

        self.assertTrue(success)
        self.assertIn("added to pool", message)

        # Verify IP was added
        pool = self.provisioner.get_ip_pool("test-pool")
        self.assertIn("192.168.1.1", pool.ips)

    def test_check_ip_health_mock(self):
        """Test checking IP health in mock mode."""
        # Create test IP
        ip = DedicatedIP("192.168.1.1", IPStatus.ACTIVE, "test-pool")
        self.provisioner._store_dedicated_ip(ip)

        # Check health
        health_status, health_data = self.provisioner.check_ip_health("192.168.1.1")

        self.assertIsInstance(health_status, IPHealthStatus)
        self.assertIn("reputation_score", health_data)
        self.assertIn("bounce_rate", health_data)
        self.assertIn("spam_rate", health_data)
        self.assertIn("daily_volume", health_data)
        self.assertTrue(health_data["mock"])

        # Verify IP was updated
        updated_ip = self.provisioner.get_dedicated_ip("192.168.1.1")
        self.assertIsNotNone(updated_ip.last_health_check)
        self.assertEqual(updated_ip.health_status, health_status)

    def test_get_ip_status_summary(self):
        """Test getting IP status summary."""
        # Create test IPs with different statuses
        ip1 = DedicatedIP(
            "192.168.1.1",
            IPStatus.ACTIVE,
            "pool1",
            health_status=IPHealthStatus.HEALTHY,
            reputation_score=95.0,
            daily_volume=1000,
        )
        ip2 = DedicatedIP(
            "192.168.1.2",
            IPStatus.PROVISIONING,
            "pool1",
            health_status=IPHealthStatus.UNKNOWN,
        )
        ip3 = DedicatedIP(
            "192.168.1.3",
            IPStatus.ACTIVE,
            "pool2",
            health_status=IPHealthStatus.WARNING,
            reputation_score=85.0,
            daily_volume=500,
        )

        # Store IPs
        self.provisioner._store_dedicated_ip(ip1)
        self.provisioner._store_dedicated_ip(ip2)
        self.provisioner._store_dedicated_ip(ip3)

        # Get summary
        summary = self.provisioner.get_ip_status_summary()

        self.assertEqual(summary["total_ips"], 3)
        self.assertEqual(summary["by_status"]["active"], 2)
        self.assertEqual(summary["by_status"]["provisioning"], 1)
        self.assertEqual(summary["by_health"]["healthy"], 1)
        self.assertEqual(summary["by_health"]["warning"], 1)
        self.assertEqual(summary["by_health"]["unknown"], 1)
        self.assertEqual(summary["by_pool"]["pool1"], 2)
        self.assertEqual(summary["by_pool"]["pool2"], 1)
        self.assertEqual(summary["total_daily_volume"], 1500)
        self.assertEqual(summary["average_reputation"], 90.0)

    def test_run_health_checks(self):
        """Test running health checks on all active IPs."""
        # Create test IPs
        ip1 = DedicatedIP("192.168.1.1", IPStatus.ACTIVE, "pool1")
        ip2 = DedicatedIP("192.168.1.2", IPStatus.ACTIVE, "pool1")
        ip3 = DedicatedIP(
            "192.168.1.3", IPStatus.PROVISIONING, "pool1"
        )  # Should be skipped

        # Store IPs
        self.provisioner._store_dedicated_ip(ip1)
        self.provisioner._store_dedicated_ip(ip2)
        self.provisioner._store_dedicated_ip(ip3)

        # Run health checks
        results = self.provisioner.run_health_checks()

        self.assertEqual(results["checked"], 2)  # Only active IPs
        self.assertEqual(results["errors"], 0)
        self.assertEqual(len(results["details"]), 2)

        # Check that health statuses are recorded
        for detail in results["details"]:
            self.assertIn("ip_address", detail)
            self.assertIn("health_status", detail)
            self.assertIn("health_data", detail)

    def test_log_event(self):
        """Test event logging."""
        self.provisioner._log_event("192.168.1.1", "test_event", {"key": "value"})

        # Verify event was logged
        with self.provisioner._get_db_connection() as conn:
            events = conn.execute("""
                SELECT * FROM ip_events WHERE event_type = 'test_event'
            """).fetchall()

            self.assertEqual(len(events), 1)
            event = events[0]
            self.assertEqual(event["ip_address"], "192.168.1.1")
            self.assertEqual(event["event_type"], "test_event")
            self.assertEqual(json.loads(event["event_data"]), {"key": "value"})

    def test_list_ip_pools(self):
        """Test listing IP pools."""
        # Create test pools
        pool1 = IPPool("pool1", ["192.168.1.1"], datetime.now())
        pool2 = IPPool("pool2", ["192.168.1.2", "192.168.1.3"], datetime.now())

        # Store pools
        self.provisioner._store_ip_pool(pool1)
        self.provisioner._store_ip_pool(pool2)

        # List pools
        pools = self.provisioner.list_ip_pools()

        self.assertEqual(len(pools), 2)
        pool_names = [pool.name for pool in pools]
        self.assertIn("pool1", pool_names)
        self.assertIn("pool2", pool_names)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary database file
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    @patch("leadfactory.email.sendgrid_ip_provisioning.SendGridIPProvisioner")
    def test_get_ip_provisioner(self, mock_provisioner_class):
        """Test get_ip_provisioner convenience function."""
        mock_instance = Mock()
        mock_provisioner_class.return_value = mock_instance

        result = get_ip_provisioner(api_key="test-key", db_path=self.db_path)

        mock_provisioner_class.assert_called_once_with(
            api_key="test-key", db_path=self.db_path
        )
        self.assertEqual(result, mock_instance)

    @patch("leadfactory.email.sendgrid_ip_provisioning.get_ip_provisioner")
    def test_provision_dedicated_ip_convenience(self, mock_get_provisioner):
        """Test provision_dedicated_ip convenience function."""
        mock_provisioner = Mock()
        mock_get_provisioner.return_value = mock_provisioner
        mock_provisioner.provision_dedicated_ip.return_value = (True, "Success", None)

        result = provision_dedicated_ip("test-pool")

        mock_get_provisioner.assert_called_once()
        mock_provisioner.provision_dedicated_ip.assert_called_once_with("test-pool")
        self.assertEqual(result, (True, "Success", None))

    @patch("leadfactory.email.sendgrid_ip_provisioning.get_ip_provisioner")
    def test_check_ip_health_convenience(self, mock_get_provisioner):
        """Test check_ip_health convenience function."""
        mock_provisioner = Mock()
        mock_get_provisioner.return_value = mock_provisioner
        mock_provisioner.check_ip_health.return_value = (
            IPHealthStatus.HEALTHY,
            {"test": "data"},
        )

        result = check_ip_health("192.168.1.1")

        mock_get_provisioner.assert_called_once()
        mock_provisioner.check_ip_health.assert_called_once_with("192.168.1.1")
        self.assertEqual(result, (IPHealthStatus.HEALTHY, {"test": "data"}))

    @patch("leadfactory.email.sendgrid_ip_provisioning.get_ip_provisioner")
    def test_get_ip_status_summary_convenience(self, mock_get_provisioner):
        """Test get_ip_status_summary convenience function."""
        mock_provisioner = Mock()
        mock_get_provisioner.return_value = mock_provisioner
        mock_provisioner.get_ip_status_summary.return_value = {"total_ips": 5}

        result = get_ip_status_summary()

        mock_get_provisioner.assert_called_once()
        mock_provisioner.get_ip_status_summary.assert_called_once()
        self.assertEqual(result, {"total_ips": 5})


if __name__ == "__main__":
    unittest.main()
