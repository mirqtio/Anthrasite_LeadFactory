#!/usr/bin/env python3
"""
Integration tests for SendGrid IP provisioning system.
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
)


class TestSendGridIPProvisioningIntegration(unittest.TestCase):
    """Integration tests for SendGrid IP provisioning."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Create provisioner instance
        self.provisioner = SendGridIPProvisioner(api_key="test-key", db_path=self.db_path)

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary database file
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_complete_ip_provisioning_workflow(self):
        """Test complete IP provisioning workflow."""
        # Step 1: Create IP pool
        success, message = self.provisioner.create_ip_pool("production-pool")
        self.assertTrue(success)
        self.assertIn("created successfully", message)

        # Step 2: Provision dedicated IP
        success, message, ip = self.provisioner.provision_dedicated_ip("production-pool")
        self.assertTrue(success)
        self.assertIsNotNone(ip)
        self.assertEqual(ip.status, IPStatus.ACTIVE)
        self.assertEqual(ip.pool_name, "production-pool")

        ip_address = ip.ip_address

        # Step 3: Verify IP is stored and retrievable
        stored_ip = self.provisioner.get_dedicated_ip(ip_address)
        self.assertIsNotNone(stored_ip)
        self.assertEqual(stored_ip.ip_address, ip_address)
        self.assertEqual(stored_ip.status, IPStatus.ACTIVE)

        # Step 4: Check IP health
        health_status, health_data = self.provisioner.check_ip_health(ip_address)
        self.assertIsInstance(health_status, IPHealthStatus)
        self.assertIn("reputation_score", health_data)

        # Step 5: Verify IP appears in listings
        all_ips = self.provisioner.list_dedicated_ips()
        self.assertEqual(len(all_ips), 1)
        self.assertEqual(all_ips[0].ip_address, ip_address)

        active_ips = self.provisioner.list_dedicated_ips(status=IPStatus.ACTIVE)
        self.assertEqual(len(active_ips), 1)

        pool_ips = self.provisioner.list_dedicated_ips(pool_name="production-pool")
        self.assertEqual(len(pool_ips), 1)

        # Step 6: Verify pool contains the IP
        pool = self.provisioner.get_ip_pool("production-pool")
        self.assertIsNotNone(pool)
        self.assertIn(ip_address, pool.ips)

    def test_multiple_ips_and_pools_workflow(self):
        """Test managing multiple IPs across different pools."""
        # Create multiple pools
        pools = ["pool-1", "pool-2", "pool-3"]
        for pool_name in pools:
            success, _ = self.provisioner.create_ip_pool(pool_name)
            self.assertTrue(success)

        # Provision IPs for each pool
        provisioned_ips = []
        for pool_name in pools:
            for i in range(2):  # 2 IPs per pool
                success, _, ip = self.provisioner.provision_dedicated_ip(pool_name)
                self.assertTrue(success)
                self.assertIsNotNone(ip)
                provisioned_ips.append(ip)

        # Verify total IP count
        all_ips = self.provisioner.list_dedicated_ips()
        self.assertEqual(len(all_ips), 6)  # 3 pools × 2 IPs

        # Verify IPs per pool
        for pool_name in pools:
            pool_ips = self.provisioner.list_dedicated_ips(pool_name=pool_name)
            self.assertEqual(len(pool_ips), 2)

            # Verify pool contains the IPs
            pool = self.provisioner.get_ip_pool(pool_name)
            self.assertEqual(len(pool.ips), 2)

        # Test status summary
        summary = self.provisioner.get_ip_status_summary()
        self.assertEqual(summary["total_ips"], 6)
        self.assertEqual(summary["by_status"]["active"], 6)
        self.assertEqual(len(summary["by_pool"]), 3)
        for pool_name in pools:
            self.assertEqual(summary["by_pool"][pool_name], 2)

    def test_ip_health_monitoring_workflow(self):
        """Test IP health monitoring workflow."""
        # Provision test IPs
        test_ips = []
        for i in range(3):
            success, _, ip = self.provisioner.provision_dedicated_ip("health-test-pool")
            self.assertTrue(success)
            test_ips.append(ip)

        # Run individual health checks
        for ip in test_ips:
            health_status, health_data = self.provisioner.check_ip_health(ip.ip_address)
            self.assertIsInstance(health_status, IPHealthStatus)
            self.assertIn("reputation_score", health_data)
            self.assertIn("bounce_rate", health_data)
            self.assertIn("spam_rate", health_data)

            # Verify IP record was updated
            updated_ip = self.provisioner.get_dedicated_ip(ip.ip_address)
            self.assertIsNotNone(updated_ip.last_health_check)
            self.assertEqual(updated_ip.health_status, health_status)

        # Run bulk health checks
        results = self.provisioner.run_health_checks()
        self.assertEqual(results["checked"], 3)
        self.assertEqual(results["errors"], 0)
        self.assertEqual(len(results["details"]), 3)

        # Verify all IPs have health data
        for detail in results["details"]:
            self.assertIn("health_status", detail)
            self.assertIn("health_data", detail)

    def test_ip_pool_management_workflow(self):
        """Test IP pool management workflow."""
        # Create pool with initial IPs
        initial_ips = ["192.168.1.1", "192.168.1.2"]
        success, message = self.provisioner.create_ip_pool("managed-pool", initial_ips)
        self.assertTrue(success)

        # Verify pool creation
        pool = self.provisioner.get_ip_pool("managed-pool")
        self.assertIsNotNone(pool)
        self.assertEqual(pool.ips, initial_ips)

        # Add more IPs to the pool
        additional_ips = ["192.168.1.3", "192.168.1.4"]
        for ip_address in additional_ips:
            success, message = self.provisioner.add_ip_to_pool(ip_address, "managed-pool")
            self.assertTrue(success)

        # Verify all IPs are in the pool
        updated_pool = self.provisioner.get_ip_pool("managed-pool")
        expected_ips = initial_ips + additional_ips
        self.assertEqual(len(updated_pool.ips), len(expected_ips))
        for ip in expected_ips:
            self.assertIn(ip, updated_pool.ips)

        # Test pool listing
        pools = self.provisioner.list_ip_pools()
        self.assertEqual(len(pools), 1)
        self.assertEqual(pools[0].name, "managed-pool")

    def test_ip_lifecycle_management(self):
        """Test complete IP lifecycle from provisioning to decommission."""
        # Provision IP
        success, _, ip = self.provisioner.provision_dedicated_ip("lifecycle-pool")
        self.assertTrue(success)
        ip_address = ip.ip_address

        # Verify initial status
        stored_ip = self.provisioner.get_dedicated_ip(ip_address)
        self.assertEqual(stored_ip.status, IPStatus.ACTIVE)

        # Simulate status changes through lifecycle
        status_progression = [
            IPStatus.WARMING_UP,
            IPStatus.ACTIVE,
            IPStatus.PAUSED,
            IPStatus.ACTIVE,
            IPStatus.DECOMMISSIONED
        ]

        for new_status in status_progression:
            # Update status
            stored_ip.status = new_status
            self.provisioner._store_dedicated_ip(stored_ip)

            # Verify status change
            updated_ip = self.provisioner.get_dedicated_ip(ip_address)
            self.assertEqual(updated_ip.status, new_status)

            # Log status change event
            self.provisioner._log_event(
                ip_address,
                "status_change",
                {"old_status": "previous", "new_status": new_status.value}
            )

        # Verify final status
        final_ip = self.provisioner.get_dedicated_ip(ip_address)
        self.assertEqual(final_ip.status, IPStatus.DECOMMISSIONED)

    def test_event_logging_and_audit_trail(self):
        """Test event logging and audit trail functionality."""
        # Provision IP to generate events
        success, _, ip = self.provisioner.provision_dedicated_ip("audit-pool")
        self.assertTrue(success)
        ip_address = ip.ip_address

        # Perform various operations to generate events
        self.provisioner.check_ip_health(ip_address)
        self.provisioner.add_ip_to_pool(ip_address, "audit-pool")

        # Manually log some events
        test_events = [
            ("configuration_change", {"setting": "reputation_threshold", "value": 90}),
            ("alert_triggered", {"type": "high_bounce_rate", "rate": 0.15}),
            ("maintenance_start", {"type": "scheduled", "duration": "2h"}),
            ("maintenance_end", {"type": "scheduled", "result": "success"})
        ]

        for event_type, event_data in test_events:
            self.provisioner._log_event(ip_address, event_type, event_data)

        # Verify events were logged
        with self.provisioner._get_db_connection() as conn:
            events = conn.execute("""
                SELECT * FROM ip_events
                WHERE ip_address = ?
                ORDER BY timestamp DESC
            """, (ip_address,)).fetchall()

            # Should have events from provisioning, health check, pool add, plus manual events
            self.assertGreaterEqual(len(events), len(test_events))

            # Verify event structure
            for event in events:
                self.assertIsNotNone(event["event_type"])
                self.assertIsNotNone(event["event_data"])
                self.assertIsNotNone(event["timestamp"])

                # Verify event_data is valid JSON
                event_data = json.loads(event["event_data"])
                self.assertIsInstance(event_data, dict)

    def test_error_handling_and_recovery(self):
        """Test error handling and recovery scenarios."""
        # Test getting non-existent IP
        non_existent_ip = self.provisioner.get_dedicated_ip("999.999.999.999")
        self.assertIsNone(non_existent_ip)

        # Test getting non-existent pool
        non_existent_pool = self.provisioner.get_ip_pool("non-existent-pool")
        self.assertIsNone(non_existent_pool)

        # Test adding IP to non-existent pool
        success, message = self.provisioner.add_ip_to_pool("192.168.1.1", "non-existent-pool")
        # Should succeed in mock mode but log the attempt

        # Test health check on non-existent IP
        health_status, health_data = self.provisioner.check_ip_health("999.999.999.999")
        # Should return unknown status or handle gracefully

        # Verify system remains stable after error conditions
        summary = self.provisioner.get_ip_status_summary()
        self.assertIsInstance(summary, dict)
        self.assertIn("total_ips", summary)

    def test_database_persistence_across_sessions(self):
        """Test that data persists across provisioner sessions."""
        # Create data in first session
        success, _, ip1 = self.provisioner.provision_dedicated_ip("persistence-pool")
        self.assertTrue(success)

        success, message = self.provisioner.create_ip_pool("test-persistence", [ip1.ip_address])
        self.assertTrue(success)

        # Close first provisioner
        first_ip_address = ip1.ip_address
        del self.provisioner

        # Create new provisioner with same database
        new_provisioner = SendGridIPProvisioner(api_key="test-key", db_path=self.db_path)

        # Verify data persists
        retrieved_ip = new_provisioner.get_dedicated_ip(first_ip_address)
        self.assertIsNotNone(retrieved_ip)
        self.assertEqual(retrieved_ip.ip_address, first_ip_address)

        retrieved_pool = new_provisioner.get_ip_pool("test-persistence")
        self.assertIsNotNone(retrieved_pool)
        self.assertIn(first_ip_address, retrieved_pool.ips)

        # Verify summary includes persisted data
        summary = new_provisioner.get_ip_status_summary()
        self.assertGreaterEqual(summary["total_ips"], 1)

    def test_concurrent_operations_simulation(self):
        """Test simulation of concurrent operations."""
        # Simulate multiple operations happening in sequence
        # (In real concurrent testing, this would use threading)

        operations = [
            ("provision", "pool-1"),
            ("provision", "pool-2"),
            ("create_pool", "pool-3"),
            ("provision", "pool-3"),
            ("health_check", None),  # Will check all active IPs
            ("provision", "pool-1"),
            ("create_pool", "pool-4"),
        ]

        provisioned_ips = []

        for operation, pool_name in operations:
            if operation == "provision":
                success, _, ip = self.provisioner.provision_dedicated_ip(pool_name)
                if success and ip:
                    provisioned_ips.append(ip.ip_address)
            elif operation == "create_pool":
                success, _ = self.provisioner.create_ip_pool(pool_name)
                self.assertTrue(success)
            elif operation == "health_check":
                results = self.provisioner.run_health_checks()
                self.assertGreaterEqual(results["checked"], 0)

        # Verify final state is consistent
        all_ips = self.provisioner.list_dedicated_ips()
        all_pools = self.provisioner.list_ip_pools()

        # Should have created some IPs and pools
        self.assertGreater(len(all_ips), 0)
        self.assertGreater(len(all_pools), 0)

        # Verify summary is consistent
        summary = self.provisioner.get_ip_status_summary()
        self.assertEqual(summary["total_ips"], len(all_ips))


if __name__ == "__main__":
    unittest.main()
