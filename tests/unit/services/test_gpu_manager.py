"""
Unit tests for GPU Auto-Scaling Manager.

Tests the core functionality of the GPU manager including queue monitoring,
scaling decisions, instance provisioning, and cost tracking.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from leadfactory.services.gpu_manager import (
    GPUAutoSpinManager, GPUInstanceType, GPUInstance, 
    QueueMetrics, GPUResourceConfig, HetznerAPIClient
)


class TestGPUAutoSpinManager:
    """Test cases for GPUAutoSpinManager."""
    
    @pytest.fixture
    def gpu_manager(self):
        """Create a GPU manager instance for testing."""
        with patch('leadfactory.services.gpu_manager.credential_manager'), \
             patch('leadfactory.services.gpu_manager.network_security'), \
             patch('leadfactory.services.gpu_manager.audit_logger'), \
             patch('leadfactory.services.gpu_manager.rate_limiter'):
            manager = GPUAutoSpinManager()
            manager.aws_client = Mock()
            manager.hetzner_client = Mock()
            return manager
    
    def test_initialization(self, gpu_manager):
        """Test GPU manager initialization."""
        assert gpu_manager.active_instances == {}
        assert isinstance(gpu_manager.queue_metrics, QueueMetrics)
        assert gpu_manager.monitoring_interval == 30
        assert not gpu_manager.running
        
        # Check resource configurations are loaded
        assert GPUInstanceType.LOCAL_GPU in gpu_manager.resource_configs
        assert GPUInstanceType.HETZNER_GTX1080 in gpu_manager.resource_configs
        assert GPUInstanceType.AWS_G4DN_XLARGE in gpu_manager.resource_configs
    
    def test_resource_configs(self, gpu_manager):
        """Test GPU resource configurations."""
        local_config = gpu_manager.resource_configs[GPUInstanceType.LOCAL_GPU]
        assert local_config.cost_per_hour == 0.0
        assert local_config.max_concurrent_tasks == 4
        
        hetzner_config = gpu_manager.resource_configs[GPUInstanceType.HETZNER_GTX1080]
        assert hetzner_config.cost_per_hour == 0.35
        assert hetzner_config.max_concurrent_tasks == 8
        
        aws_config = gpu_manager.resource_configs[GPUInstanceType.AWS_G4DN_XLARGE]
        assert aws_config.cost_per_hour == 0.526
        assert aws_config.max_concurrent_tasks == 8
    
    @pytest.mark.asyncio
    async def test_update_queue_metrics(self, gpu_manager):
        """Test queue metrics updating."""
        # Mock the get_queue_metrics function
        mock_metrics = {
            "total": 150,
            "pending": 120,
            "processing": 30,
            "avg_time": 180.0,
            "eta": 3600.0,
            "growth_rate": 5.0
        }
        
        with patch('leadfactory.services.gpu_manager.get_queue_metrics', return_value=mock_metrics):
            await gpu_manager._update_queue_metrics()
        
        assert gpu_manager.queue_metrics.total_tasks == 150
        assert gpu_manager.queue_metrics.pending_tasks == 120
        assert gpu_manager.queue_metrics.processing_tasks == 30
        assert gpu_manager.queue_metrics.average_processing_time == 180.0
        assert gpu_manager.queue_metrics.estimated_completion_time == 3600.0
        assert gpu_manager.queue_metrics.queue_growth_rate == 5.0
    
    def test_within_budget_to_scale(self, gpu_manager):
        """Test budget checking for scaling decisions."""
        gpu_manager.cost_tracking = {"daily_budget": 100.0, "current_spend": 50.0}
        
        # Should allow scaling when within budget
        assert gpu_manager._within_budget_to_scale()
        
        # Should not allow scaling when over budget
        gpu_manager.cost_tracking["current_spend"] = 95.0
        assert not gpu_manager._within_budget_to_scale()
    
    def test_can_scale_up_cooldown(self, gpu_manager):
        """Test scale up cooldown logic."""
        # Should allow scaling when no previous scale up
        assert gpu_manager._can_scale_up()
        
        # Should not allow scaling during cooldown period
        gpu_manager.last_scale_up = datetime.utcnow()
        assert not gpu_manager._can_scale_up()
        
        # Should allow scaling after cooldown period
        gpu_manager.last_scale_up = datetime.utcnow() - timedelta(minutes=10)
        assert gpu_manager._can_scale_up()
    
    def test_can_scale_down_cooldown(self, gpu_manager):
        """Test scale down cooldown logic."""
        # Should allow scaling when no previous scale down
        assert gpu_manager._can_scale_down()
        
        # Should not allow scaling during cooldown period
        gpu_manager.last_scale_down = datetime.utcnow()
        assert not gpu_manager._can_scale_down()
        
        # Should allow scaling after cooldown period
        gpu_manager.last_scale_down = datetime.utcnow() - timedelta(minutes=15)
        assert gpu_manager._can_scale_down()
    
    @pytest.mark.asyncio
    async def test_evaluate_scaling_needs(self, gpu_manager):
        """Test scaling decision logic."""
        # Set up queue metrics that should trigger scale up
        gpu_manager.queue_metrics = QueueMetrics(
            total_tasks=2500,
            pending_tasks=2100,  # Above 2000 threshold
            processing_tasks=50,
            average_processing_time=300.0,
            estimated_completion_time=2000.0,  # Above 1800 threshold
            queue_growth_rate=10.0
        )
        
        # Mock budget check
        gpu_manager.cost_tracking = {"daily_budget": 500.0, "current_spend": 100.0}
        
        with patch.object(gpu_manager, '_scale_up') as mock_scale_up:
            await gpu_manager._evaluate_scaling_needs()
            mock_scale_up.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_scale_up_instance_selection(self, gpu_manager):
        """Test instance type selection during scale up."""
        # Test Hetzner RTX4090 selection for large queue
        gpu_manager.queue_metrics.pending_tasks = 5500
        with patch.object(gpu_manager, 'start_gpu_instance') as mock_start:
            mock_start.return_value = "test-instance-id"
            await gpu_manager._scale_up()
            mock_start.assert_called_with(GPUInstanceType.HETZNER_RTX4090)
        
        # Test Hetzner RTX3080 selection for medium queue
        gpu_manager.queue_metrics.pending_tasks = 3500
        with patch.object(gpu_manager, 'start_gpu_instance') as mock_start:
            mock_start.return_value = "test-instance-id"
            await gpu_manager._scale_up()
            mock_start.assert_called_with(GPUInstanceType.HETZNER_RTX3080)
        
        # Test Hetzner GTX1080 selection for threshold queue
        gpu_manager.queue_metrics.pending_tasks = 2100
        with patch.object(gpu_manager, 'start_gpu_instance') as mock_start:
            mock_start.return_value = "test-instance-id"
            await gpu_manager._scale_up()
            mock_start.assert_called_with(GPUInstanceType.HETZNER_GTX1080)
    
    @pytest.mark.asyncio
    async def test_scale_down(self, gpu_manager):
        """Test scaling down idle instances."""
        # Add some test instances
        gpu_manager.active_instances = {
            "instance1": GPUInstance(
                instance_id="instance1",
                instance_type=GPUInstanceType.HETZNER_GTX1080,
                status="running",
                current_tasks=0  # Idle
            ),
            "instance2": GPUInstance(
                instance_id="instance2", 
                instance_type=GPUInstanceType.HETZNER_RTX3080,
                status="running",
                current_tasks=0  # Idle
            )
        }
        
        with patch.object(gpu_manager, 'stop_gpu_instance') as mock_stop:
            await gpu_manager._scale_down()
            # Should stop the more expensive instance (RTX3080)
            mock_stop.assert_called_with("instance2")
    
    @pytest.mark.asyncio
    async def test_start_hetzner_instance(self, gpu_manager):
        """Test starting Hetzner GPU instance."""
        # Mock Hetzner client response
        mock_response = {
            "server": {
                "id": 12345,
                "name": "test-server",
                "status": "initializing"
            }
        }
        gpu_manager.hetzner_client.create_server.return_value = mock_response
        
        with patch('leadfactory.services.gpu_manager.SECURITY_AVAILABLE', True), \
             patch('leadfactory.services.gpu_manager.network_security') as mock_security:
            mock_security.load_ssh_keys.return_value = ["ssh-rsa AAAA..."]
            
            instance_id = await gpu_manager._start_hetzner_instance(GPUInstanceType.HETZNER_GTX1080)
            
            assert instance_id == "12345"
            assert "12345" in gpu_manager.active_instances
            
            instance = gpu_manager.active_instances["12345"]
            assert instance.instance_type == GPUInstanceType.HETZNER_GTX1080
            assert instance.status == "starting"
    
    @pytest.mark.asyncio
    async def test_stop_gpu_instance(self, gpu_manager):
        """Test stopping GPU instances."""
        # Add test instance
        instance = GPUInstance(
            instance_id="test-instance",
            instance_type=GPUInstanceType.HETZNER_GTX1080,
            status="running",
            start_time=datetime.utcnow() - timedelta(hours=2)
        )
        gpu_manager.active_instances["test-instance"] = instance
        
        with patch.object(gpu_manager, '_stop_hetzner_instance') as mock_stop:
            await gpu_manager.stop_gpu_instance("test-instance")
            
            mock_stop.assert_called_with("test-instance")
            assert "test-instance" not in gpu_manager.active_instances
    
    def test_get_status(self, gpu_manager):
        """Test getting GPU manager status."""
        # Add test instances
        gpu_manager.active_instances = {
            "instance1": GPUInstance(
                instance_id="instance1",
                instance_type=GPUInstanceType.HETZNER_GTX1080,
                status="running",
                current_tasks=2,
                cost_incurred=5.0
            )
        }
        
        gpu_manager.queue_metrics = QueueMetrics(
            total_tasks=100,
            pending_tasks=50,
            processing_tasks=25,
            average_processing_time=200.0,
            estimated_completion_time=1000.0,
            queue_growth_rate=3.0
        )
        
        status = gpu_manager.get_status()
        
        assert status["running"] == gpu_manager.running
        assert status["active_instances"] == 1
        assert status["queue_metrics"]["total_tasks"] == 100
        assert status["queue_metrics"]["pending_tasks"] == 50
        assert "instance1" in status["instances"]
        assert status["instances"]["instance1"]["current_tasks"] == 2


class TestHetznerAPIClient:
    """Test cases for HetznerAPIClient."""
    
    @pytest.fixture
    def hetzner_client(self):
        """Create a Hetzner API client for testing."""
        return HetznerAPIClient("test-token")
    
    def test_initialization(self, hetzner_client):
        """Test Hetzner client initialization."""
        assert hetzner_client.api_token == "test-token"
        assert hetzner_client.base_url == "https://api.hetzner.cloud/v1"
        assert "Bearer test-token" in hetzner_client.headers["Authorization"]
    
    @patch('leadfactory.services.gpu_manager.requests')
    def test_create_server(self, mock_requests, hetzner_client):
        """Test server creation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "server": {"id": 12345, "name": "test-server"}
        }
        mock_requests.post.return_value = mock_response
        
        result = hetzner_client.create_server(
            name="test-server",
            server_type="cx21",
            image="ubuntu-20.04",
            ssh_keys=["test-key"]
        )
        
        assert result["server"]["id"] == 12345
        mock_requests.post.assert_called_once()
    
    @patch('leadfactory.services.gpu_manager.requests')
    def test_delete_server(self, mock_requests, hetzner_client):
        """Test server deletion."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_requests.delete.return_value = mock_response
        
        hetzner_client.delete_server("12345")
        
        mock_requests.delete.assert_called_once()
        call_args = mock_requests.delete.call_args
        assert "servers/12345" in call_args[0][0]
    
    @patch('leadfactory.services.gpu_manager.requests')
    def test_get_server(self, mock_requests, hetzner_client):
        """Test getting server details."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "server": {
                "id": 12345,
                "name": "test-server",
                "status": "running",
                "public_net": {"ipv4": {"ip": "1.2.3.4"}}
            }
        }
        mock_requests.get.return_value = mock_response
        
        result = hetzner_client.get_server("12345")
        
        assert result["server"]["status"] == "running"
        assert result["server"]["public_net"]["ipv4"]["ip"] == "1.2.3.4"


class TestQueueMetrics:
    """Test cases for QueueMetrics dataclass."""
    
    def test_queue_metrics_creation(self):
        """Test creating QueueMetrics instance."""
        metrics = QueueMetrics(
            total_tasks=100,
            pending_tasks=50,
            processing_tasks=25,
            average_processing_time=180.0,
            estimated_completion_time=900.0,
            queue_growth_rate=2.5
        )
        
        assert metrics.total_tasks == 100
        assert metrics.pending_tasks == 50
        assert metrics.processing_tasks == 25
        assert metrics.average_processing_time == 180.0
        assert metrics.estimated_completion_time == 900.0
        assert metrics.queue_growth_rate == 2.5


class TestGPUInstance:
    """Test cases for GPUInstance dataclass."""
    
    def test_gpu_instance_creation(self):
        """Test creating GPUInstance."""
        start_time = datetime.utcnow()
        instance = GPUInstance(
            instance_id="test-123",
            instance_type=GPUInstanceType.HETZNER_GTX1080,
            status="running",
            ip_address="1.2.3.4",
            start_time=start_time,
            current_tasks=3,
            total_tasks_processed=25,
            cost_incurred=12.50
        )
        
        assert instance.instance_id == "test-123"
        assert instance.instance_type == GPUInstanceType.HETZNER_GTX1080
        assert instance.status == "running"
        assert instance.ip_address == "1.2.3.4"
        assert instance.start_time == start_time
        assert instance.current_tasks == 3
        assert instance.total_tasks_processed == 25
        assert instance.cost_incurred == 12.50


@pytest.mark.integration
class TestGPUManagerIntegration:
    """Integration tests for GPU Manager."""
    
    @pytest.mark.asyncio
    async def test_full_scaling_cycle(self):
        """Test complete scaling up and down cycle."""
        with patch('leadfactory.services.gpu_manager.credential_manager'), \
             patch('leadfactory.services.gpu_manager.network_security'), \
             patch('leadfactory.services.gpu_manager.audit_logger'), \
             patch('leadfactory.services.gpu_manager.rate_limiter'):
            
            manager = GPUAutoSpinManager()
            manager.hetzner_client = Mock()
            
            # Mock successful instance creation
            manager.hetzner_client.create_server.return_value = {
                "server": {"id": 12345, "name": "test-server"}
            }
            
            # Simulate queue growth requiring scale up
            manager.queue_metrics = QueueMetrics(
                total_tasks=2500,
                pending_tasks=2100,
                processing_tasks=50,
                average_processing_time=300.0,
                estimated_completion_time=2000.0,
                queue_growth_rate=10.0
            )
            
            # Scale up
            instance_id = await manager.start_gpu_instance(GPUInstanceType.HETZNER_GTX1080)
            assert instance_id == "12345"
            assert len(manager.active_instances) == 1
            
            # Simulate queue reduction requiring scale down
            manager.queue_metrics.pending_tasks = 50
            manager.active_instances["12345"].current_tasks = 0  # Make idle
            
            # Scale down
            await manager.stop_gpu_instance("12345")
            assert len(manager.active_instances) == 0


if __name__ == "__main__":
    pytest.main([__file__])