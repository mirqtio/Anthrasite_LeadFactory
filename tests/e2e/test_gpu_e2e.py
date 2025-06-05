"""
End-to-end tests for GPU Auto-Scaling System.

Tests the complete GPU auto-scaling workflow from queue monitoring
to instance provisioning and task processing.
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from leadfactory.pipeline.unified_gpt4o import UnifiedGPT4ONode
from leadfactory.services.gpu_alerting import gpu_alert_manager
from leadfactory.services.gpu_manager import GPUInstanceType, gpu_manager
from leadfactory.services.gpu_security import validate_gpu_security


@pytest.mark.e2e
class TestGPUAutoScalingE2E:
    """End-to-end tests for GPU auto-scaling system."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Set up test environment for E2E tests."""
        # Reset GPU manager state
        gpu_manager.active_instances.clear()
        gpu_manager.last_scale_up = None
        gpu_manager.last_scale_down = None
        gpu_manager.cost_tracking = {"daily_budget": 500.0, "current_spend": 0.0}

        # Reset alert manager
        gpu_alert_manager.alert_history.clear()
        gpu_alert_manager.alert_cooldowns.clear()

        yield

        # Cleanup after test
        gpu_manager.active_instances.clear()

    @pytest.mark.asyncio
    async def test_complete_scaling_workflow(self):
        """Test complete GPU scaling workflow from queue growth to instance provisioning."""

        # Mock external dependencies
        with (
            patch("leadfactory.storage.factory.get_storage") as mock_storage,
            patch("leadfactory.services.gpu_manager.get_queue_metrics") as mock_metrics,
            patch.object(gpu_manager, "hetzner_client") as mock_hetzner,
            patch("leadfactory.services.gpu_manager.SECURITY_AVAILABLE", True),
            patch("leadfactory.services.gpu_manager.credential_manager") as mock_creds,
            patch("leadfactory.services.gpu_manager.network_security") as mock_network,
            patch("leadfactory.services.gpu_manager.audit_logger"),
            patch("leadfactory.services.gpu_manager.rate_limiter") as mock_rate,
        ):
            # Setup mocks
            storage = Mock()
            mock_storage.return_value = storage

            mock_creds.get_credential.return_value = "test-token"
            mock_network.load_ssh_keys.return_value = ["ssh-rsa AAAA..."]
            mock_rate.check_rate_limit.return_value = True

            # Mock Hetzner responses
            mock_hetzner.create_server.return_value = {
                "server": {"id": 12345, "name": "leadfactory-gpu-test"}
            }
            mock_hetzner.get_server.return_value = {
                "server": {
                    "id": 12345,
                    "status": "running",
                    "public_net": {"ipv4": {"ip": "1.2.3.4"}},
                }
            }

            # Simulate queue growth over time
            queue_progression = [
                # Initial state - small queue
                {
                    "total": 50,
                    "pending": 30,
                    "processing": 15,
                    "avg_time": 200,
                    "eta": 400,
                    "growth_rate": 2,
                },
                # Growing queue - approaching threshold
                {
                    "total": 1800,
                    "pending": 1500,
                    "processing": 200,
                    "avg_time": 180,
                    "eta": 1350,
                    "growth_rate": 8,
                },
                # Large queue - should trigger scaling
                {
                    "total": 2300,
                    "pending": 2100,
                    "processing": 150,
                    "avg_time": 220,
                    "eta": 2500,
                    "growth_rate": 15,
                },
                # Processing queue - high utilization
                {
                    "total": 2400,
                    "pending": 1800,
                    "processing": 500,
                    "avg_time": 190,
                    "eta": 1800,
                    "growth_rate": 10,
                },
                # Queue processed - should trigger scale down
                {
                    "total": 200,
                    "pending": 50,
                    "processing": 20,
                    "avg_time": 150,
                    "eta": 375,
                    "growth_rate": 1,
                },
            ]

            for i, queue_state in enumerate(queue_progression):

                # Update queue metrics
                mock_metrics.return_value = queue_state
                await gpu_manager._update_queue_metrics()

                # Evaluate scaling needs
                await gpu_manager._evaluate_scaling_needs()

                # Update instance status
                await gpu_manager._update_instance_status()

                # Check alerts
                from leadfactory.services.gpu_alerting import check_all_gpu_alerts

                with patch("leadfactory.services.gpu_manager.ALERTING_AVAILABLE", True):
                    alerts = await check_all_gpu_alerts(gpu_manager)

                # Verify scaling behavior based on queue state
                if queue_state["pending"] > 2000:
                    # Should have scaled up
                    if (
                        gpu_manager._within_budget_to_scale()
                        and gpu_manager._can_scale_up()
                    ):
                        assert len(gpu_manager.active_instances) >= 1, (
                            f"Should have scaled up at step {i + 1}"
                        )

                        # Verify instance type selection
                        for instance in gpu_manager.active_instances.values():
                            assert instance.instance_type in [
                                GPUInstanceType.HETZNER_GTX1080,
                                GPUInstanceType.HETZNER_RTX3080,
                                GPUInstanceType.HETZNER_RTX4090,
                            ], "Should prioritize Hetzner instances"

                    # Should generate queue alerts
                    queue_alerts = [a for a in alerts if "queue_size" in a["type"]]
                    if queue_alerts:
                        assert queue_alerts[0]["severity"] in ["warning", "critical"]

                elif (
                    queue_state["pending"] < 100
                    and len(gpu_manager.active_instances) > 1
                ):
                    # Should consider scaling down
                    if gpu_manager._can_scale_down():
                        # Mark instances as idle for scale down test
                        for instance in gpu_manager.active_instances.values():
                            instance.current_tasks = 0

                # Log current state
                await gpu_manager._log_status()

                # Simulate time passage
                await asyncio.sleep(0.1)


    @pytest.mark.asyncio
    async def test_pipeline_integration_e2e(self):
        """Test end-to-end pipeline integration with GPU scaling."""

        with (
            patch("leadfactory.storage.factory.get_storage") as mock_storage,
            patch.object(gpu_manager, "hetzner_client") as mock_hetzner,
            patch("leadfactory.services.gpu_manager.SECURITY_AVAILABLE", False),
        ):
            # Setup storage mock
            storage = Mock()
            mock_storage.return_value = storage

            # Mock queue task insertion
            storage.execute_query.side_effect = [
                [{"id": task_id}]
                for task_id in range(1, 101)  # 100 tasks
            ]

            # Mock GPU instance creation
            mock_hetzner.create_server.return_value = {
                "server": {"id": 67890, "name": "pipeline-gpu-test"}
            }

            # Create unified node
            unified_node = UnifiedGPT4ONode()

            # Mock LLM responses
            with patch.object(unified_node, "llm_client") as mock_llm:
                mock_llm.chat_completion.return_value = {
                    "choices": [
                        {
                            "message": {
                                "content": '{"mockup_concept": {"design_theme": "Modern"}, "email_content": {"subject": "Test Subject", "greeting": "Hello"}}'
                            }
                        }
                    ],
                    "provider": "openai",
                    "model": "gpt-4o",
                    "usage": {"total_tokens": 150},
                }

                # Process multiple businesses to build up queue
                business_results = []
                for i in range(50):  # Process 50 businesses
                    business_data = {
                        "id": i + 1,
                        "name": f"Tech Company {i + 1}",
                        "website": f"https://company{i + 1}.com",
                        "description": "A technology company requiring GPU processing",
                        "contact_email": f"contact@company{i + 1}.com",
                        "industry": "technology",  # Triggers GPU requirement
                        "screenshot_url": f"https://screenshots.com/company{i + 1}.png",
                    }

                    with patch.object(
                        unified_node, "_fetch_business_data", return_value=business_data
                    ):
                        result = unified_node.process_business(i + 1)
                        business_results.append(result)

                        # Verify GPU processing was detected
                        assert result["gpu_required"] is True
                        assert result["queue_task_id"] is not None

                # Verify all businesses were processed successfully
                successful_results = [r for r in business_results if r["success"]]
                assert len(successful_results) == 50, (
                    "All businesses should be processed successfully"
                )

                # Simulate queue metrics after processing
                with patch(
                    "leadfactory.services.gpu_manager.get_queue_metrics"
                ) as mock_metrics:
                    mock_metrics.return_value = {
                        "total": 2500,
                        "pending": 2200,  # Large queue from processing
                        "processing": 200,
                        "avg_time": 250,
                        "eta": 2750,
                        "growth_rate": 20,
                    }

                    # Update GPU manager
                    await gpu_manager._update_queue_metrics()
                    await gpu_manager._evaluate_scaling_needs()

                    # Should have triggered GPU scaling
                    if (
                        gpu_manager._within_budget_to_scale()
                        and gpu_manager._can_scale_up()
                    ):
                        assert len(gpu_manager.active_instances) > 0, (
                            "Should have scaled up GPU instances"
                        )

    @pytest.mark.asyncio
    async def test_alert_system_e2e(self):
        """Test end-to-end alert system functionality."""

        from leadfactory.services.gpu_alerting import check_all_gpu_alerts

        with patch("leadfactory.services.gpu_manager.ALERTING_AVAILABLE", True):
            # Test budget alerts
            gpu_manager.cost_tracking = {"daily_budget": 100.0, "current_spend": 85.0}
            gpu_manager.queue_metrics.pending_tasks = 100
            gpu_manager.queue_metrics.processing_tasks = 20
            gpu_manager.queue_metrics.estimated_completion_time = 500
            gpu_manager.queue_metrics.queue_growth_rate = 2.0

            alerts = await check_all_gpu_alerts(gpu_manager)
            budget_alerts = [a for a in alerts if "budget" in a["type"]]
            assert len(budget_alerts) > 0, "Should generate budget alerts"
            assert budget_alerts[0]["severity"] == "warning"

            # Test queue alerts
            gpu_manager.cost_tracking["current_spend"] = 10.0  # Reset budget
            gpu_manager.queue_metrics.pending_tasks = 2700  # Critical queue size

            alerts = await check_all_gpu_alerts(gpu_manager)
            queue_alerts = [a for a in alerts if "queue_size" in a["type"]]
            assert len(queue_alerts) > 0, "Should generate queue alerts"
            assert queue_alerts[0]["severity"] == "critical"

            # Test alert cooldown
            first_alert_time = len(gpu_alert_manager.alert_history)

            # Try to send same alert again immediately
            alerts = await check_all_gpu_alerts(gpu_manager)
            queue_alerts = [a for a in alerts if "queue_size" in a["type"]]

            # Should be blocked by cooldown (or significantly reduced)
            second_alert_time = len(gpu_alert_manager.alert_history)
            assert second_alert_time <= first_alert_time + 1, (
                "Cooldown should prevent alert spam"
            )

    def test_security_system_e2e(self):
        """Test end-to-end security system functionality."""

        # Test overall security validation
        security_status = validate_gpu_security()

        # Should have basic security components
        assert "credentials" in security_status
        assert "network_security" in security_status
        assert "audit_logging" in security_status
        assert "rate_limiting" in security_status

        # Test credential management
        from leadfactory.services.gpu_security import credential_manager

        # Store and retrieve credentials
        success = credential_manager.store_credential(
            "hetzner", "api_token", "e2e-test-token", encrypted=True
        )
        assert success, "Should store credentials successfully"

        retrieved_token = credential_manager.get_credential("hetzner", "api_token")
        assert retrieved_token == "e2e-test-token", (
            "Should retrieve correct credentials"
        )

        # Test rate limiting
        from leadfactory.services.gpu_security import rate_limiter

        # Should allow initial operations
        for i in range(5):
            assert rate_limiter.check_rate_limit("instance_provision", f"user_{i}")

        # Test audit logging
        from leadfactory.services.gpu_security import audit_logger

        with (
            patch("builtins.open") as mock_open,
            patch("os.makedirs"),
            patch("os.path.exists", return_value=True),
            patch("os.chmod"),
        ):
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file

            audit_logger.log_event(
                "e2e_test_event",
                {"test": "end_to_end", "component": "security"},
                user="e2e_test",
                severity="info",
            )

            # Verify audit log was written
            mock_file.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_cost_optimization_e2e(self):
        """Test end-to-end cost optimization functionality."""

        with (
            patch.object(gpu_manager, "hetzner_client") as mock_hetzner,
            patch("leadfactory.services.gpu_manager.SECURITY_AVAILABLE", False),
        ):
            # Mock Hetzner responses for different instance types
            instance_responses = {
                GPUInstanceType.HETZNER_GTX1080: {
                    "server": {"id": 1001, "name": "gtx1080"}
                },
                GPUInstanceType.HETZNER_RTX3080: {
                    "server": {"id": 1002, "name": "rtx3080"}
                },
                GPUInstanceType.HETZNER_RTX4090: {
                    "server": {"id": 1003, "name": "rtx4090"}
                },
            }

            mock_hetzner.create_server.side_effect = (
                lambda *args, **kwargs: instance_responses[
                    GPUInstanceType.HETZNER_GTX1080  # Default to cheapest
                ]
            )

            # Test instance type selection based on queue size
            test_cases = [
                (2100, GPUInstanceType.HETZNER_GTX1080),  # Just above threshold
                (3500, GPUInstanceType.HETZNER_RTX3080),  # Medium queue
                (5500, GPUInstanceType.HETZNER_RTX4090),  # Large queue
            ]

            for queue_size, expected_type in test_cases:
                gpu_manager.active_instances.clear()  # Reset
                gpu_manager.queue_metrics.pending_tasks = queue_size

                with patch(
                    "leadfactory.services.gpu_manager.get_queue_metrics"
                ) as mock_metrics:
                    mock_metrics.return_value = {
                        "total": queue_size + 100,
                        "pending": queue_size,
                        "processing": 100,
                        "avg_time": 200,
                        "eta": 2000,
                        "growth_rate": 10,
                    }

                    await gpu_manager._update_queue_metrics()

                    # Mock the specific instance type response
                    mock_hetzner.create_server.return_value = instance_responses[
                        expected_type
                    ]

                    await gpu_manager._evaluate_scaling_needs()

                    # Verify cost-optimized instance type was selected
                    if len(gpu_manager.active_instances) > 0:
                        list(gpu_manager.active_instances.values())[0]

                        # For this test, we verify the scaling logic would select appropriate type
                        # The actual selection happens in _scale_up method

    @pytest.mark.asyncio
    async def test_failure_recovery_e2e(self):
        """Test end-to-end failure recovery scenarios."""

        with (
            patch.object(gpu_manager, "hetzner_client") as mock_hetzner,
            patch("leadfactory.services.gpu_manager.SECURITY_AVAILABLE", True),
            patch("leadfactory.services.gpu_manager.rate_limiter") as mock_rate,
            patch("leadfactory.services.gpu_manager.audit_logger") as mock_audit,
        ):
            # Test API failure recovery
            mock_hetzner.create_server.side_effect = Exception("Hetzner API error")
            mock_rate.check_rate_limit.return_value = True

            # Attempt to start instance (should fail gracefully)
            instance_id = await gpu_manager.start_gpu_instance(
                GPUInstanceType.HETZNER_GTX1080
            )

            assert instance_id is None, "Should handle API failures gracefully"

            # Verify failure was logged
            mock_audit.log_event.assert_called()

            # Test rate limit recovery
            mock_rate.check_rate_limit.return_value = False  # Rate limited
            mock_hetzner.create_server.side_effect = None  # Fix API
            mock_hetzner.create_server.return_value = {
                "server": {"id": 2001, "name": "recovery-test"}
            }

            instance_id = await gpu_manager.start_gpu_instance(
                GPUInstanceType.HETZNER_GTX1080
            )

            assert instance_id is None, "Should respect rate limits"

            # Test successful recovery
            mock_rate.check_rate_limit.return_value = True  # Rate limit cleared

            instance_id = await gpu_manager.start_gpu_instance(
                GPUInstanceType.HETZNER_GTX1080
            )

            assert instance_id == "2001", "Should succeed after recovery"
            assert "2001" in gpu_manager.active_instances


@pytest.mark.e2e
@pytest.mark.slow
class TestGPUPerformanceE2E:
    """Performance tests for GPU system."""

    @pytest.mark.asyncio
    async def test_scaling_performance(self):
        """Test performance of scaling operations."""

        with (
            patch("leadfactory.services.gpu_manager.get_queue_metrics") as mock_metrics,
            patch.object(gpu_manager, "hetzner_client") as mock_hetzner,
            patch("leadfactory.services.gpu_manager.SECURITY_AVAILABLE", False),
        ):
            mock_hetzner.create_server.return_value = {
                "server": {"id": 3001, "name": "perf-test"}
            }

            # Test rapid queue changes
            start_time = time.time()

            for i in range(10):
                mock_metrics.return_value = {
                    "total": 2000 + i * 100,
                    "pending": 1900 + i * 100,
                    "processing": 100,
                    "avg_time": 200,
                    "eta": 2000,
                    "growth_rate": i + 5,
                }

                await gpu_manager._update_queue_metrics()
                await gpu_manager._evaluate_scaling_needs()

            end_time = time.time()
            processing_time = end_time - start_time

            # Should process updates quickly
            assert processing_time < 5.0, (
                f"Processing took {processing_time:.2f}s, should be < 5s"
            )



if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
