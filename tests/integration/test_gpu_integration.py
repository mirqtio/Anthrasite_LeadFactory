"""
Integration tests for GPU Auto-Scaling System.

Tests the integration between GPU manager, queue monitoring, pipeline integration,
and alert system.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from leadfactory.pipeline.unified_gpt4o import UnifiedGPT4ONode
from leadfactory.services.gpu_alerting import gpu_alert_manager
from leadfactory.services.gpu_manager import GPUInstanceType, gpu_manager


@pytest.mark.integration
class TestGPUPipelineIntegration:
    """Test GPU integration with pipeline."""

    @pytest.fixture
    def unified_node(self):
        """Create unified GPT-4o node for testing."""
        return UnifiedGPT4ONode()

    @pytest.fixture
    def mock_storage(self):
        """Mock storage backend."""
        with patch("leadfactory.storage.factory.get_storage") as mock:
            storage = Mock()
            mock.return_value = storage
            yield storage

    @pytest.mark.asyncio
    async def test_gpu_queue_integration(self, unified_node, mock_storage):
        """Test integration between unified node and GPU queue."""
        # Mock business data that requires GPU processing

        # Mock storage responses
        mock_storage.execute_query.return_value = [{"id": 1}]  # Queue task ID

        # Mock LLM client
        with patch.object(unified_node, "llm_client") as mock_llm:
            mock_llm.chat_completion.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": '{"mockup_concept": {"design_theme": "Modern"}, "email_content": {"subject": "Test"}}'
                        }
                    }
                ],
                "provider": "openai",
                "model": "gpt-4o",
                "usage": {"total_tokens": 100},
            }

            result = unified_node.process_business(123)

            # Verify GPU processing was detected
            assert result["gpu_required"] is True
            assert result["queue_task_id"] == 1
            assert result["success"] is True

            # Verify queue task was added
            mock_storage.execute_query.assert_called()

            # Check that the task was added to personalization queue
            call_args = mock_storage.execute_query.call_args_list
            queue_insert_call = None
            for call in call_args:
                if "INSERT INTO personalization_queue" in call[0][0]:
                    queue_insert_call = call
                    break

            assert queue_insert_call is not None
            assert (
                queue_insert_call[0][1][1] == "ai_content_personalization"
            )  # task_type
            assert queue_insert_call[0][1][2] is True  # gpu_required

    @pytest.mark.asyncio
    async def test_queue_metrics_integration(self, mock_storage):
        """Test queue metrics integration with GPU manager."""
        from leadfactory.utils.metrics import get_queue_metrics

        # Mock queue metrics from database
        mock_storage.execute_query.side_effect = [
            [(50,)],  # total tasks
            [(30,)],  # pending tasks
            [(15,)],  # processing tasks
            [(180.0,)],  # average processing time
            [(5,)],  # recent additions
        ]

        metrics = get_queue_metrics("personalization")

        assert metrics is not None
        assert metrics["total"] == 50
        assert metrics["pending"] == 30
        assert metrics["processing"] == 15
        assert metrics["avg_time"] == 180.0
        assert metrics["growth_rate"] == 30.0  # 5 * 6 (extrapolated to per hour)

    @pytest.mark.asyncio
    async def test_scaling_trigger_integration(self):
        """Test that queue size triggers GPU scaling."""
        with (
            patch("leadfactory.services.gpu_manager.get_queue_metrics") as mock_metrics,
            patch.object(gpu_manager, "start_gpu_instance") as mock_start,
            patch("leadfactory.services.gpu_manager.SECURITY_AVAILABLE", False),
        ):
            # Mock queue metrics that should trigger scaling
            mock_metrics.return_value = {
                "total": 2500,
                "pending": 2100,  # Above 2000 threshold
                "processing": 50,
                "avg_time": 300.0,
                "eta": 2000.0,  # Above 1800 threshold
                "growth_rate": 10.0,
            }

            # Mock successful instance start
            mock_start.return_value = "test-instance-123"

            # Update queue metrics
            await gpu_manager._update_queue_metrics()

            # Verify scaling decision
            await gpu_manager._evaluate_scaling_needs()

            # Should have triggered scale up
            mock_start.assert_called_once()
            assert mock_start.call_args[0][0] == GPUInstanceType.HETZNER_GTX1080


@pytest.mark.integration
class TestGPUAlertIntegration:
    """Test GPU alert system integration."""

    @pytest.mark.asyncio
    async def test_budget_alert_integration(self):
        """Test budget alerts are triggered correctly."""
        from leadfactory.services.gpu_alerting import check_all_gpu_alerts

        # Set up GPU manager with high cost
        with (
            patch.object(gpu_manager, "get_status") as mock_status,
            patch.object(
                gpu_manager,
                "cost_tracking",
                {"current_spend": 450.0, "daily_budget": 500.0},
            ),
            patch.object(gpu_manager, "queue_metrics") as mock_queue,
        ):
            mock_status.return_value = {"instances": {}, "active_instances": 0}
            mock_queue.pending_tasks = 100
            mock_queue.processing_tasks = 10
            mock_queue.estimated_completion_time = 500
            mock_queue.queue_growth_rate = 2.0

            alerts = await check_all_gpu_alerts(gpu_manager)

            # Should generate budget warning alert
            budget_alerts = [a for a in alerts if a["type"] == "budget_warning"]
            assert len(budget_alerts) > 0
            assert budget_alerts[0]["severity"] == "warning"
            assert "90.0%" in budget_alerts[0]["message"]

    @pytest.mark.asyncio
    async def test_queue_alert_integration(self):
        """Test queue size alerts are triggered."""
        from leadfactory.services.gpu_alerting import check_all_gpu_alerts

        # Set up GPU manager with large queue
        with (
            patch.object(gpu_manager, "get_status") as mock_status,
            patch.object(
                gpu_manager,
                "cost_tracking",
                {"current_spend": 50.0, "daily_budget": 500.0},
            ),
            patch.object(gpu_manager, "queue_metrics") as mock_queue,
        ):
            mock_status.return_value = {"instances": {}, "active_instances": 0}
            mock_queue.pending_tasks = 2600  # Above critical threshold
            mock_queue.processing_tasks = 50
            mock_queue.estimated_completion_time = 3000
            mock_queue.queue_growth_rate = 15.0

            alerts = await check_all_gpu_alerts(gpu_manager)

            # Should generate queue critical alert
            queue_alerts = [a for a in alerts if a["type"] == "queue_size_critical"]
            assert len(queue_alerts) > 0
            assert queue_alerts[0]["severity"] == "critical"
            assert "2600 pending tasks" in queue_alerts[0]["message"]

    def test_alert_cooldown_integration(self):
        """Test alert cooldown prevents spam."""
        # Send first alert
        {
            "type": "budget_warning",
            "severity": "warning",
            "message": "Test alert",
            "details": {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        # First alert should be allowed
        assert gpu_alert_manager._should_send_alert("budget_warning")

        # Record that we sent it
        gpu_alert_manager.alert_cooldowns["budget_warning"] = datetime.utcnow()

        # Second alert should be blocked by cooldown
        assert not gpu_alert_manager._should_send_alert("budget_warning")

        # Alert should be allowed after cooldown period
        gpu_alert_manager.alert_cooldowns["budget_warning"] = (
            datetime.utcnow() - timedelta(minutes=70)
        )
        assert gpu_alert_manager._should_send_alert("budget_warning")


@pytest.mark.integration
class TestGPUSecurityIntegration:
    """Test GPU security integration."""

    def test_credential_management_integration(self):
        """Test credential management in GPU provisioning."""
        from leadfactory.services.gpu_security import credential_manager

        # Store test credentials
        success = credential_manager.store_credential(
            "hetzner", "api_token", "test-token-12345", encrypted=True
        )
        assert success

        # Retrieve credentials
        token = credential_manager.get_credential("hetzner", "api_token")
        assert token == "test-token-12345"

        # Validate credentials
        validation = credential_manager.validate_credentials("hetzner")
        assert validation["api_token"] is True

    def test_ssh_key_integration(self):
        """Test SSH key loading for instances."""
        from leadfactory.services.gpu_security import network_security

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open") as mock_open,
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = (
                "ssh-rsa AAAAB3NzaC1yc2E..."
            )

            ssh_keys = network_security.load_ssh_keys()
            assert len(ssh_keys) > 0
            assert ssh_keys[0].startswith("ssh-rsa")

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self):
        """Test rate limiting in GPU provisioning."""
        from leadfactory.services.gpu_security import rate_limiter

        # First few provisions should be allowed
        for _i in range(5):
            assert rate_limiter.check_rate_limit("instance_provision")

        # Should eventually hit rate limit
        for _i in range(10):
            rate_limiter.check_rate_limit("instance_provision")

        # Should be blocked after hitting limit
        assert not rate_limiter.check_rate_limit("instance_provision")

    def test_audit_logging_integration(self):
        """Test audit logging integration."""
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
                "test_event",
                {"message": "Test audit event", "instance_id": "test-123"},
                user="test_user",
                severity="info",
            )

            # Verify audit log was written
            mock_file.write.assert_called_once()
            written_content = mock_file.write.call_args[0][0]
            assert "test_event" in written_content
            assert "test_user" in written_content
            assert "instance_id" in written_content


@pytest.mark.integration
class TestGPUMetricsIntegration:
    """Test GPU metrics integration."""

    @pytest.mark.asyncio
    async def test_metrics_collection_integration(self):
        """Test metrics are collected during GPU operations."""
        with (
            patch("leadfactory.services.gpu_manager.METRICS_AVAILABLE", True),
            patch("leadfactory.services.gpu_manager.record_metric") as mock_record,
            patch.object(gpu_manager, "hetzner_client") as mock_client,
            patch("leadfactory.services.gpu_manager.SECURITY_AVAILABLE", False),
        ):
            # Mock successful instance creation
            mock_client.create_server.return_value = {
                "server": {"id": 12345, "name": "test-server"}
            }

            # Start instance
            await gpu_manager.start_gpu_instance(
                GPUInstanceType.HETZNER_GTX1080
            )

            # Verify metrics were recorded
            mock_record.assert_called()

            # Check for scaling event metric
            scaling_calls = [
                call
                for call in mock_record.call_args_list
                if "GPU_SCALING_EVENTS" in str(call)
            ]
            assert len(scaling_calls) > 0

    @pytest.mark.asyncio
    async def test_status_metrics_integration(self):
        """Test status logging includes metrics."""
        with (
            patch("leadfactory.services.gpu_manager.METRICS_AVAILABLE", True),
            patch("leadfactory.services.gpu_manager.record_metric") as mock_record,
        ):
            # Set up test state
            gpu_manager.queue_metrics.pending_tasks = 100
            gpu_manager.queue_metrics.processing_tasks = 25

            # Log status
            await gpu_manager._log_status()

            # Verify queue metrics were recorded
            queue_calls = [
                call
                for call in mock_record.call_args_list
                if "GPU_QUEUE_SIZE" in str(call)
            ]
            assert len(queue_calls) >= 2  # One for pending, one for processing


@pytest.mark.e2e
class TestGPUEndToEnd:
    """End-to-end tests for GPU system."""

    @pytest.mark.asyncio
    async def test_complete_gpu_workflow(self):
        """Test complete workflow from business processing to GPU scaling."""
        # This would be a comprehensive end-to-end test
        # that exercises the entire GPU auto-scaling workflow

        with (
            patch("leadfactory.storage.factory.get_storage") as mock_storage,
            patch("leadfactory.services.gpu_manager.get_queue_metrics") as mock_metrics,
            patch.object(gpu_manager, "hetzner_client") as mock_client,
            patch("leadfactory.services.gpu_manager.SECURITY_AVAILABLE", False),
            patch("leadfactory.services.gpu_manager.METRICS_AVAILABLE", False),
            patch("leadfactory.services.gpu_manager.ALERTING_AVAILABLE", False),
        ):
            # Mock storage for unified node
            storage = Mock()
            mock_storage.return_value = storage
            storage.execute_query.return_value = [{"id": 1}]

            # Mock queue growing over time
            queue_states = [
                {
                    "total": 500,
                    "pending": 400,
                    "processing": 50,
                    "avg_time": 200,
                    "eta": 1000,
                    "growth_rate": 5,
                },
                {
                    "total": 1500,
                    "pending": 1200,
                    "processing": 100,
                    "avg_time": 180,
                    "eta": 1800,
                    "growth_rate": 8,
                },
                {
                    "total": 2200,
                    "pending": 2100,
                    "processing": 80,
                    "avg_time": 220,
                    "eta": 2500,
                    "growth_rate": 12,
                },
            ]

            # Mock GPU instance creation
            mock_client.create_server.return_value = {
                "server": {"id": 12345, "name": "test-server"}
            }

            # Simulate workflow
            unified_node = UnifiedGPT4ONode()

            for i, queue_state in enumerate(queue_states):
                mock_metrics.return_value = queue_state

                # Process a business (adds to queue)
                with patch.object(unified_node, "llm_client") as mock_llm:
                    mock_llm.chat_completion.return_value = {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"mockup_concept": {}, "email_content": {}}'
                                }
                            }
                        ],
                        "provider": "test",
                        "model": "test",
                        "usage": {},
                    }

                    business_data = {
                        "id": i + 1,
                        "name": f"Business {i + 1}",
                        "website": "test.com",
                        "description": "Test",
                        "contact_email": "test@test.com",
                        "industry": "technology",
                    }

                    with patch.object(
                        unified_node, "_fetch_business_data", return_value=business_data
                    ):
                        result = unified_node.process_business(i + 1)
                        assert result["success"] is True

                # Update GPU manager
                await gpu_manager._update_queue_metrics()
                await gpu_manager._evaluate_scaling_needs()

                # Check if scaling occurred for large queue
                if queue_state["pending"] > 2000:
                    assert len(gpu_manager.active_instances) > 0

            # Verify final state
            assert gpu_manager.queue_metrics.pending_tasks == 2100
            # Would have provisioned GPU instance due to queue size


if __name__ == "__main__":
    pytest.main([__file__])
