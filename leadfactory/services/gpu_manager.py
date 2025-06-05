"""
GPU Auto-Spin Manager for Large Personalisation Queue.

Automatically provisions and manages GPU resources for intensive
personalization tasks, scaling based on queue depth and processing demand.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, NamedTuple, Optional

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# LeadFactory modules
try:
    from leadfactory.utils.metrics import (
        GPU_COST_HOURLY,
        GPU_INSTANCES_ACTIVE,
        GPU_PROVISIONING_TIME,
        GPU_QUEUE_SIZE,
        GPU_SCALING_EVENTS,
        GPU_UTILIZATION,
        record_metric,
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

try:
    from leadfactory.services.gpu_alerting import check_all_gpu_alerts

    ALERTING_AVAILABLE = True
except ImportError:
    ALERTING_AVAILABLE = False

try:
    from leadfactory.services.gpu_security import (
        audit_logger,
        credential_manager,
        network_security,
        rate_limiter,
    )

    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

try:
    import boto3

    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

try:
    import docker

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

try:
    import requests

    HETZNER_AVAILABLE = True
except ImportError:
    HETZNER_AVAILABLE = False


logger = logging.getLogger(__name__)


class GPUInstanceType(Enum):
    """Available GPU instance types."""

    LOCAL_GPU = "local"
    AWS_G4DN_XLARGE = "g4dn.xlarge"
    AWS_G4DN_2XLARGE = "g4dn.2xlarge"
    AWS_G4DN_4XLARGE = "g4dn.4xlarge"
    AWS_P3_2XLARGE = "p3.2xlarge"
    AWS_P3_8XLARGE = "p3.8xlarge"
    HETZNER_GTX1080 = "hetzner.gtx1080"
    HETZNER_RTX3080 = "hetzner.rtx3080"
    HETZNER_RTX4090 = "hetzner.rtx4090"


@dataclass
class GPUResourceConfig:
    """Configuration for GPU resources."""

    instance_type: GPUInstanceType
    max_concurrent_tasks: int
    cost_per_hour: float
    memory_gb: int
    vram_gb: int
    cuda_cores: int
    spin_up_time_seconds: int = 120
    min_utilization_threshold: float = 0.2
    max_utilization_threshold: float = 0.8


@dataclass
class QueueMetrics:
    """Metrics for personalization queue."""

    total_tasks: int
    pending_tasks: int
    processing_tasks: int
    average_processing_time: float
    estimated_completion_time: float
    queue_growth_rate: float


@dataclass
class GPUInstance:
    """Represents a GPU compute instance."""

    instance_id: str
    instance_type: GPUInstanceType
    status: str  # "starting", "running", "stopping", "stopped"
    ip_address: Optional[str] = None
    start_time: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    current_tasks: int = 0
    total_tasks_processed: int = 0
    cost_incurred: float = 0.0


class HetznerAPIClient:
    """Client for interacting with Hetzner Cloud API."""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.hetzner.cloud/v1"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make HTTP request to Hetzner API."""
        url = f"{self.base_url}/{endpoint}"

        if method.upper() == "GET":
            response = requests.get(url, headers=self.headers)
        elif method.upper() == "POST":
            response = requests.post(url, headers=self.headers, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=self.headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json() if response.content else {}

    def create_server(
        self,
        name: str,
        server_type: str,
        image: str,
        location: str = "nbg1",
        ssh_keys: list[str] = None,
        user_data: str = None,
    ) -> dict:
        """Create a new server instance."""
        data = {
            "name": name,
            "server_type": server_type,
            "image": image,
            "location": location,
            "start_after_create": True,
        }

        if ssh_keys:
            data["ssh_keys"] = ssh_keys
        if user_data:
            data["user_data"] = user_data

        return self._make_request("POST", "servers", data)

    def delete_server(self, server_id: str) -> dict:
        """Delete a server instance."""
        return self._make_request("DELETE", f"servers/{server_id}")

    def get_server(self, server_id: str) -> dict:
        """Get server details."""
        return self._make_request("GET", f"servers/{server_id}")

    def list_servers(self, name_prefix: str = None) -> dict:
        """List all servers, optionally filtered by name prefix."""
        endpoint = "servers"
        if name_prefix:
            endpoint += f"?name={name_prefix}"
        return self._make_request("GET", endpoint)

    def get_server_types(self) -> dict:
        """Get available server types."""
        return self._make_request("GET", "server_types")

    def get_images(self) -> dict:
        """Get available images."""
        return self._make_request("GET", "images")


class GPUAutoSpinManager:
    """
    Manages automatic provisioning and scaling of GPU resources
    for large personalization workloads.
    """

    def __init__(self, config_file: str = "etc/gpu_config.yml"):
        """Initialize GPU manager."""
        self.config_file = config_file
        self.active_instances: dict[str, GPUInstance] = {}
        self.queue_metrics = QueueMetrics(0, 0, 0, 0.0, 0.0, 0.0)
        self.resource_configs = self._initialize_resource_configs()
        self.cost_tracking = {"daily_budget": 500.0, "current_spend": 0.0}
        self.monitoring_interval = 30  # seconds
        self.running = False

        # Cooldown tracking for scaling decisions
        self.last_scale_up = None
        self.last_scale_down = None
        self.scale_up_cooldown = 300  # 5 minutes
        self.scale_down_cooldown = 600  # 10 minutes

        # Initialize cloud providers
        self.aws_client = None
        self.docker_client = None
        self.hetzner_client = None
        self._initialize_providers()

    def _initialize_resource_configs(self) -> dict[GPUInstanceType, GPUResourceConfig]:
        """Initialize GPU resource configurations."""
        return {
            GPUInstanceType.LOCAL_GPU: GPUResourceConfig(
                instance_type=GPUInstanceType.LOCAL_GPU,
                max_concurrent_tasks=4,
                cost_per_hour=0.0,
                memory_gb=32,
                vram_gb=8,
                cuda_cores=2048,
                spin_up_time_seconds=10,
            ),
            GPUInstanceType.AWS_G4DN_XLARGE: GPUResourceConfig(
                instance_type=GPUInstanceType.AWS_G4DN_XLARGE,
                max_concurrent_tasks=8,
                cost_per_hour=0.526,
                memory_gb=16,
                vram_gb=16,
                cuda_cores=2560,
                spin_up_time_seconds=180,
            ),
            GPUInstanceType.AWS_G4DN_2XLARGE: GPUResourceConfig(
                instance_type=GPUInstanceType.AWS_G4DN_2XLARGE,
                max_concurrent_tasks=16,
                cost_per_hour=0.752,
                memory_gb=32,
                vram_gb=16,
                cuda_cores=2560,
                spin_up_time_seconds=180,
            ),
            GPUInstanceType.AWS_P3_2XLARGE: GPUResourceConfig(
                instance_type=GPUInstanceType.AWS_P3_2XLARGE,
                max_concurrent_tasks=20,
                cost_per_hour=3.06,
                memory_gb=61,
                vram_gb=16,
                cuda_cores=5120,
                spin_up_time_seconds=240,
            ),
            GPUInstanceType.HETZNER_GTX1080: GPUResourceConfig(
                instance_type=GPUInstanceType.HETZNER_GTX1080,
                max_concurrent_tasks=8,
                cost_per_hour=0.35,
                memory_gb=32,
                vram_gb=8,
                cuda_cores=2560,
                spin_up_time_seconds=120,
            ),
            GPUInstanceType.HETZNER_RTX3080: GPUResourceConfig(
                instance_type=GPUInstanceType.HETZNER_RTX3080,
                max_concurrent_tasks=12,
                cost_per_hour=0.60,
                memory_gb=32,
                vram_gb=10,
                cuda_cores=8704,
                spin_up_time_seconds=120,
            ),
            GPUInstanceType.HETZNER_RTX4090: GPUResourceConfig(
                instance_type=GPUInstanceType.HETZNER_RTX4090,
                max_concurrent_tasks=16,
                cost_per_hour=1.20,
                memory_gb=64,
                vram_gb=24,
                cuda_cores=16384,
                spin_up_time_seconds=120,
            ),
        }

    def _initialize_providers(self):
        """Initialize cloud provider clients."""
        if AWS_AVAILABLE:
            try:
                self.aws_client = boto3.client("ec2")
                logger.info("AWS EC2 client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize AWS client: {e}")

        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
                logger.info("Docker client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Docker client: {e}")

        if HETZNER_AVAILABLE:
            try:
                # Use secure credential manager if available
                if SECURITY_AVAILABLE:
                    hetzner_token = credential_manager.get_credential(
                        "hetzner", "api_token"
                    )
                else:
                    hetzner_token = os.environ.get("HETZNER_API_TOKEN")

                if hetzner_token:
                    self.hetzner_client = HetznerAPIClient(hetzner_token)
                    logger.info("Hetzner API client initialized")

                    # Audit log the initialization
                    if SECURITY_AVAILABLE:
                        audit_logger.log_event(
                            "hetzner_client_init",
                            {"message": "Hetzner client initialized successfully"},
                            severity="info",
                        )
                else:
                    logger.warning("HETZNER_API_TOKEN not available")
            except Exception as e:
                logger.warning(f"Failed to initialize Hetzner client: {e}")
                if SECURITY_AVAILABLE:
                    audit_logger.log_event(
                        "hetzner_client_init_failed",
                        {"message": f"Failed to initialize Hetzner client: {e}"},
                        severity="warning",
                    )

    async def start_monitoring(self):
        """Start the GPU auto-spin monitoring loop."""
        self.running = True
        logger.info("GPU Auto-Spin Manager started")

        while self.running:
            try:
                # Update queue metrics
                await self._update_queue_metrics()

                # Make scaling decisions
                await self._evaluate_scaling_needs()

                # Update instance status
                await self._update_instance_status()

                # Track costs
                await self._update_cost_tracking()

                # Check alerts
                await self._check_alerts()

                # Log status
                await self._log_status()

                await asyncio.sleep(self.monitoring_interval)

            except Exception as e:
                logger.error(f"Error in GPU monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_interval)

    async def stop_monitoring(self):
        """Stop the GPU monitoring and clean up resources."""
        self.running = False

        # Stop all running instances
        for instance_id in list(self.active_instances.keys()):
            await self.stop_gpu_instance(instance_id)

        logger.info("GPU Auto-Spin Manager stopped")

    async def _update_queue_metrics(self):
        """Update metrics for the personalization queue."""
        try:
            # This would integrate with actual queue monitoring
            # For now, simulate metrics based on current load

            from leadfactory.utils.metrics import get_queue_metrics

            # Get current queue state
            queue_data = await asyncio.get_event_loop().run_in_executor(
                None, get_queue_metrics, "personalization"
            )

            if queue_data:
                self.queue_metrics = QueueMetrics(
                    total_tasks=queue_data.get("total", 0),
                    pending_tasks=queue_data.get("pending", 0),
                    processing_tasks=queue_data.get("processing", 0),
                    average_processing_time=queue_data.get("avg_time", 300.0),
                    estimated_completion_time=queue_data.get("eta", 0.0),
                    queue_growth_rate=queue_data.get("growth_rate", 0.0),
                )
            else:
                # Mock metrics for demonstration
                self.queue_metrics = QueueMetrics(
                    total_tasks=150,
                    pending_tasks=120,
                    processing_tasks=30,
                    average_processing_time=180.0,
                    estimated_completion_time=3600.0,
                    queue_growth_rate=5.0,
                )

        except Exception as e:
            logger.error(f"Failed to update queue metrics: {e}")

    async def _evaluate_scaling_needs(self):
        """Evaluate if GPU instances need to be scaled up or down."""
        # Calculate current capacity
        total_capacity = sum(
            self.resource_configs[inst.instance_type].max_concurrent_tasks
            for inst in self.active_instances.values()
            if inst.status == "running"
        )

        current_utilization = self.queue_metrics.processing_tasks / max(
            total_capacity, 1
        )

        # Decision logic for scaling - Updated for Task 22 requirements
        should_scale_up = (
            self.queue_metrics.pending_tasks
            > 2000  # Large queue (2000 threshold per requirements)
            and current_utilization > 0.8  # High utilization
            and self.queue_metrics.estimated_completion_time > 1800  # >30min ETA
            and self._within_budget_to_scale()
            and self._can_scale_up()  # Check cooldown period
        )

        should_scale_down = (
            self.queue_metrics.pending_tasks < 100  # Small queue (updated threshold)
            and current_utilization < 0.2  # Low utilization
            and len(self.active_instances) > 1  # Keep at least one instance
            and self._can_scale_down()  # Check cooldown period
        )

        if should_scale_up:
            await self._scale_up()
        elif should_scale_down:
            await self._scale_down()

    def _within_budget_to_scale(self) -> bool:
        """Check if scaling up is within budget constraints."""
        daily_remaining = (
            self.cost_tracking["daily_budget"] - self.cost_tracking["current_spend"]
        )

        # Estimate cost for next instance (assume 4 hours)
        cheapest_instance = min(
            self.resource_configs.values(), key=lambda x: x.cost_per_hour
        )
        estimated_cost = cheapest_instance.cost_per_hour * 4

        return daily_remaining >= estimated_cost

    def _can_scale_up(self) -> bool:
        """Check if we can scale up (cooldown period)."""
        if self.last_scale_up is None:
            return True

        time_since_last = (datetime.utcnow() - self.last_scale_up).total_seconds()
        return time_since_last >= self.scale_up_cooldown

    def _can_scale_down(self) -> bool:
        """Check if we can scale down (cooldown period)."""
        if self.last_scale_down is None:
            return True

        time_since_last = (datetime.utcnow() - self.last_scale_down).total_seconds()
        return time_since_last >= self.scale_down_cooldown

    async def _scale_up(self):
        """Scale up GPU resources."""
        # Choose appropriate instance type based on queue size
        # Prioritize Hetzner instances per Task 22 requirements
        if self.queue_metrics.pending_tasks > 5000:
            instance_type = GPUInstanceType.HETZNER_RTX4090
        elif self.queue_metrics.pending_tasks > 3000:
            instance_type = GPUInstanceType.HETZNER_RTX3080
        elif self.queue_metrics.pending_tasks > 2000:
            instance_type = GPUInstanceType.HETZNER_GTX1080
        else:
            # Fallback to AWS if queue is smaller
            instance_type = GPUInstanceType.AWS_G4DN_XLARGE

        # Check if we already have this type running
        running_types = [
            inst.instance_type
            for inst in self.active_instances.values()
            if inst.status == "running"
        ]

        if instance_type not in running_types:
            instance_id = await self.start_gpu_instance(instance_type)
            if instance_id:
                self.last_scale_up = datetime.utcnow()
                logger.info(
                    f"Scaled up: Started {instance_type.value} instance {instance_id}"
                )

                # Record scaling event
                if METRICS_AVAILABLE:
                    provider = (
                        "hetzner"
                        if instance_type.value.startswith("hetzner")
                        else "aws"
                    )
                    record_metric(
                        GPU_SCALING_EVENTS,
                        1,
                        action="scale_up",
                        provider=provider,
                        instance_type=instance_type.value,
                    )

    async def _scale_down(self):
        """Scale down GPU resources."""
        # Find least utilized instance to stop
        running_instances = [
            inst
            for inst in self.active_instances.values()
            if inst.status == "running" and inst.current_tasks == 0
        ]

        if running_instances:
            # Stop the most expensive idle instance
            instance_to_stop = max(
                running_instances,
                key=lambda x: self.resource_configs[x.instance_type].cost_per_hour,
            )

            await self.stop_gpu_instance(instance_to_stop.instance_id)
            self.last_scale_down = datetime.utcnow()
            logger.info(f"Scaled down: Stopped instance {instance_to_stop.instance_id}")

            # Record scaling event
            if METRICS_AVAILABLE:
                provider = (
                    "hetzner"
                    if instance_to_stop.instance_type.value.startswith("hetzner")
                    else "aws"
                )
                record_metric(
                    GPU_SCALING_EVENTS,
                    1,
                    action="scale_down",
                    provider=provider,
                    instance_type=instance_to_stop.instance_type.value,
                )

    async def start_gpu_instance(self, instance_type: GPUInstanceType) -> Optional[str]:
        """Start a new GPU instance."""
        self.resource_configs[instance_type]

        # Security checks
        if SECURITY_AVAILABLE:
            # Check rate limits
            if not rate_limiter.check_rate_limit("instance_provision"):
                logger.warning("Rate limit exceeded for instance provisioning")
                audit_logger.log_event(
                    "rate_limit_exceeded",
                    {
                        "operation": "instance_provision",
                        "instance_type": instance_type.value,
                    },
                    severity="warning",
                )
                return None

            # Audit log the provisioning attempt
            audit_logger.log_event(
                "instance_provision_start",
                {
                    "instance_type": instance_type.value,
                    "provider": (
                        "hetzner"
                        if instance_type.value.startswith("hetzner")
                        else "aws"
                    ),
                },
                severity="info",
            )

        try:
            instance_id = None

            if instance_type == GPUInstanceType.LOCAL_GPU:
                instance_id = await self._start_local_gpu()
            elif instance_type.value.startswith("aws_"):
                instance_id = await self._start_aws_instance(instance_type)
            elif instance_type.value.startswith("hetzner."):
                instance_id = await self._start_hetzner_instance(instance_type)
            else:
                logger.error(f"Unsupported instance type: {instance_type}")
                if SECURITY_AVAILABLE:
                    audit_logger.log_event(
                        "instance_provision_failed",
                        {
                            "reason": "unsupported_instance_type",
                            "instance_type": instance_type.value,
                        },
                        severity="warning",
                    )
                return None

            # Log successful provisioning
            if instance_id and SECURITY_AVAILABLE:
                audit_logger.log_event(
                    "instance_provision_success",
                    {"instance_id": instance_id, "instance_type": instance_type.value},
                    severity="info",
                )

            return instance_id

        except Exception as e:
            logger.error(f"Failed to start {instance_type.value} instance: {e}")
            if SECURITY_AVAILABLE:
                audit_logger.log_event(
                    "instance_provision_failed",
                    {"reason": str(e), "instance_type": instance_type.value},
                    severity="critical",
                )
            return None

    async def _start_local_gpu(self) -> Optional[str]:
        """Start local GPU processing."""
        instance_id = f"local_gpu_{int(time.time())}"

        # Check if GPU is available
        gpu_available = await self._check_local_gpu()
        if not gpu_available:
            logger.warning("Local GPU not available")
            return None

        instance = GPUInstance(
            instance_id=instance_id,
            instance_type=GPUInstanceType.LOCAL_GPU,
            status="running",
            ip_address="localhost",
            start_time=datetime.utcnow(),
        )

        self.active_instances[instance_id] = instance
        return instance_id

    async def _check_local_gpu(self) -> bool:
        """Check if local GPU is available."""
        try:
            # Try to detect NVIDIA GPU
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    async def _start_aws_instance(
        self, instance_type: GPUInstanceType
    ) -> Optional[str]:
        """Start AWS GPU instance."""
        if not self.aws_client:
            logger.error("AWS client not available")
            return None

        self.resource_configs[instance_type]

        # AWS instance configuration
        aws_instance_type = instance_type.value.replace("aws_", "").replace("_", ".")

        try:
            # Launch EC2 instance
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.aws_client.run_instances,
                {
                    "ImageId": "ami-0c94855ba95b798c7",  # Deep Learning AMI
                    "MinCount": 1,
                    "MaxCount": 1,
                    "InstanceType": aws_instance_type,
                    "KeyName": "leadfactory-gpu",  # Configure in AWS
                    "SecurityGroups": ["leadfactory-gpu-sg"],
                    "UserData": self._get_gpu_startup_script(),
                    "TagSpecifications": [
                        {
                            "ResourceType": "instance",
                            "Tags": [
                                {
                                    "Key": "Name",
                                    "Value": f"leadfactory-gpu-{instance_type.value}",
                                },
                                {"Key": "Purpose", "Value": "personalization"},
                                {"Key": "AutoSpin", "Value": "true"},
                            ],
                        }
                    ],
                },
            )

            instance_id = response["Instances"][0]["InstanceId"]

            instance = GPUInstance(
                instance_id=instance_id,
                instance_type=instance_type,
                status="starting",
                start_time=datetime.utcnow(),
            )

            self.active_instances[instance_id] = instance

            logger.info(f"Started AWS GPU instance {instance_id} ({aws_instance_type})")
            return instance_id

        except Exception as e:
            logger.error(f"Failed to start AWS instance: {e}")
            return None

    async def _start_hetzner_instance(
        self, instance_type: GPUInstanceType
    ) -> Optional[str]:
        """Start Hetzner GPU instance."""
        if not self.hetzner_client:
            logger.error("Hetzner client not available")
            return None

        self.resource_configs[instance_type]

        # Map instance types to Hetzner server types
        hetzner_server_types = {
            GPUInstanceType.HETZNER_GTX1080: "cx21",  # 2 vCPU, 4GB RAM + GTX 1080
            GPUInstanceType.HETZNER_RTX3080: "cx31",  # 2 vCPU, 8GB RAM + RTX 3080
            GPUInstanceType.HETZNER_RTX4090: "cx41",  # 4 vCPU, 16GB RAM + RTX 4090
        }

        hetzner_type = hetzner_server_types.get(instance_type)
        if not hetzner_type:
            logger.error(f"No Hetzner server type mapping for {instance_type}")
            return None

        try:
            # Create Hetzner server
            server_name = f"leadfactory-gpu-{instance_type.value}-{int(time.time())}"

            # Get SSH keys from security manager
            ssh_keys = []
            if SECURITY_AVAILABLE:
                ssh_keys = network_security.load_ssh_keys()
                if not ssh_keys:
                    logger.warning("No SSH keys available for Hetzner instance")

            # Default SSH key name if none available
            if not ssh_keys:
                ssh_keys = ["leadfactory-gpu"]

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.hetzner_client.create_server,
                server_name,
                hetzner_type,
                "ubuntu-20.04",  # Ubuntu 20.04 image
                "nbg1",  # Nuremberg datacenter
                ssh_keys[:1],  # Use first SSH key
                self._get_hetzner_startup_script(),
            )

            instance_id = str(response["server"]["id"])

            instance = GPUInstance(
                instance_id=instance_id,
                instance_type=instance_type,
                status="starting",
                start_time=datetime.utcnow(),
            )

            self.active_instances[instance_id] = instance

            logger.info(f"Started Hetzner GPU instance {instance_id} ({hetzner_type})")
            return instance_id

        except Exception as e:
            logger.error(f"Failed to start Hetzner instance: {e}")
            return None

    def _get_gpu_startup_script(self) -> str:
        """Get startup script for GPU instances."""
        return """#!/bin/bash
# Install Docker if not present
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
fi

# Install nvidia-docker
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Pull and run personalization service
docker pull leadfactory/personalization-gpu:latest
docker run -d --gpus all --name personalization-worker \
    -p 8080:8080 \
    -e WORKER_TYPE=gpu \
    -e QUEUE_URL=https://api.leadfactory.com/queue \
    leadfactory/personalization-gpu:latest

# Signal readiness
curl -X POST https://api.leadfactory.com/gpu/ready -d "instance_id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)"
"""

    def _get_hetzner_startup_script(self) -> str:
        """Get startup script for Hetzner GPU instances."""
        return """#!/bin/bash
set -e

# Update system
apt-get update -y

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker root
fi

# Install NVIDIA drivers and nvidia-docker
apt-get install -y nvidia-driver-470
apt-get install -y nvidia-docker2

# Configure NVIDIA Docker runtime
cat > /etc/docker/daemon.json <<EOF
{
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    }
}
EOF

systemctl restart docker

# Configure GPU monitoring
nvidia-smi -pm 1
nvidia-smi -c 3

# Pull and start personalization worker
docker pull leadfactory/personalization-gpu:latest
docker run -d --gpus all --name personalization-worker \
    --restart unless-stopped \
    -p 8080:8080 \
    -e WORKER_TYPE=gpu \
    -e QUEUE_URL=$QUEUE_URL \
    -e INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/hostname) \
    -e HETZNER_INSTANCE=true \
    leadfactory/personalization-gpu:latest

# Signal readiness to manager
sleep 60
curl -X POST $MANAGER_URL/gpu/ready \
    -H "Content-Type: application/json" \
    -d "{\"instance_id\": \"$(curl -s http://169.254.169.254/latest/meta-data/hostname)\", \"status\": \"ready\", \"provider\": \"hetzner\"}"
"""

    async def stop_gpu_instance(self, instance_id: str):
        """Stop a GPU instance."""
        if instance_id not in self.active_instances:
            logger.warning(f"Instance {instance_id} not found")
            return

        instance = self.active_instances[instance_id]

        try:
            if instance.instance_type == GPUInstanceType.LOCAL_GPU:
                await self._stop_local_gpu(instance_id)
            elif instance.instance_type.value.startswith("aws_"):
                await self._stop_aws_instance(instance_id)
            elif instance.instance_type.value.startswith("hetzner."):
                await self._stop_hetzner_instance(instance_id)

            instance.status = "stopped"

            # Calculate final cost
            if instance.start_time:
                runtime_hours = (
                    datetime.utcnow() - instance.start_time
                ).total_seconds() / 3600
                config = self.resource_configs[instance.instance_type]
                instance.cost_incurred = runtime_hours * config.cost_per_hour
                self.cost_tracking["current_spend"] += instance.cost_incurred

            del self.active_instances[instance_id]

        except Exception as e:
            logger.error(f"Failed to stop instance {instance_id}: {e}")

    async def _stop_local_gpu(self, instance_id: str):
        """Stop local GPU processing."""
        logger.info(f"Stopped local GPU instance {instance_id}")

    async def _stop_aws_instance(self, instance_id: str):
        """Stop AWS GPU instance."""
        if not self.aws_client:
            return

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.aws_client.terminate_instances,
                {"InstanceIds": [instance_id]},
            )
            logger.info(f"Terminated AWS instance {instance_id}")

        except Exception as e:
            logger.error(f"Failed to terminate AWS instance {instance_id}: {e}")

    async def _stop_hetzner_instance(self, instance_id: str):
        """Stop Hetzner GPU instance."""
        if not self.hetzner_client:
            return

        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self.hetzner_client.delete_server, instance_id
            )
            logger.info(f"Deleted Hetzner instance {instance_id}")

        except Exception as e:
            logger.error(f"Failed to delete Hetzner instance {instance_id}: {e}")

    async def _update_instance_status(self):
        """Update status of all active instances."""
        for _instance_id, instance in list(self.active_instances.items()):
            if instance.instance_type.value.startswith("aws_"):
                await self._update_aws_instance_status(instance)
            elif instance.instance_type.value.startswith("hetzner."):
                await self._update_hetzner_instance_status(instance)

    async def _update_aws_instance_status(self, instance: GPUInstance):
        """Update AWS instance status."""
        if not self.aws_client:
            return

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.aws_client.describe_instances,
                {"InstanceIds": [instance.instance_id]},
            )

            aws_instance = response["Reservations"][0]["Instances"][0]
            instance.status = aws_instance["State"]["Name"]

            if instance.status == "running" and not instance.ip_address:
                instance.ip_address = aws_instance.get("PublicIpAddress")

        except Exception as e:
            logger.error(
                f"Failed to update instance {instance.instance_id} status: {e}"
            )

    async def _update_hetzner_instance_status(self, instance: GPUInstance):
        """Update Hetzner instance status."""
        if not self.hetzner_client:
            return

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.hetzner_client.get_server, instance.instance_id
            )

            hetzner_server = response["server"]

            # Map Hetzner status to our status
            status_mapping = {
                "initializing": "starting",
                "starting": "starting",
                "running": "running",
                "stopping": "stopping",
                "off": "stopped",
            }

            instance.status = status_mapping.get(
                hetzner_server["status"], hetzner_server["status"]
            )

            if instance.status == "running" and not instance.ip_address:
                instance.ip_address = hetzner_server["public_net"]["ipv4"]["ip"]

        except Exception as e:
            logger.error(
                f"Failed to update Hetzner instance {instance.instance_id} status: {e}"
            )

    async def _update_cost_tracking(self):
        """Update cost tracking for budget management."""
        total_hourly_cost = 0

        for instance in self.active_instances.values():
            if instance.status == "running":
                config = self.resource_configs[instance.instance_type]
                total_hourly_cost += config.cost_per_hour

        # Add current hour cost to daily spend
        current_hour_cost = total_hourly_cost / 24  # Approximate
        self.cost_tracking["current_spend"] += current_hour_cost

    async def _check_alerts(self):
        """Check for alert conditions and send notifications."""
        if ALERTING_AVAILABLE:
            try:
                alerts = await check_all_gpu_alerts(self)
                if alerts:
                    logger.info(f"Processed {len(alerts)} GPU alerts")
            except Exception as e:
                logger.error(f"Error checking GPU alerts: {e}")

    async def _log_status(self):
        """Log current GPU manager status and update metrics."""
        running_instances = sum(
            1 for inst in self.active_instances.values() if inst.status == "running"
        )

        total_capacity = sum(
            self.resource_configs[inst.instance_type].max_concurrent_tasks
            for inst in self.active_instances.values()
            if inst.status == "running"
        )

        logger.info(
            f"GPU Status: {running_instances} instances, "
            f"{total_capacity} total capacity, "
            f"{self.queue_metrics.pending_tasks} pending tasks, "
            f"${self.cost_tracking['current_spend']:.2f} daily spend"
        )

        # Update metrics
        if METRICS_AVAILABLE:
            # Update queue metrics
            record_metric(
                GPU_QUEUE_SIZE, self.queue_metrics.pending_tasks, status="pending"
            )
            record_metric(
                GPU_QUEUE_SIZE, self.queue_metrics.processing_tasks, status="processing"
            )

            # Update instance metrics by provider and type
            instance_counts = {}
            hourly_costs = {}

            for instance in self.active_instances.values():
                if instance.status == "running":
                    provider = (
                        "hetzner"
                        if instance.instance_type.value.startswith("hetzner")
                        else "aws"
                    )
                    instance_type = instance.instance_type.value

                    key = (provider, instance_type)
                    instance_counts[key] = instance_counts.get(key, 0) + 1

                    if key not in hourly_costs:
                        config = self.resource_configs[instance.instance_type]
                        hourly_costs[key] = config.cost_per_hour

            # Record metrics
            for (provider, instance_type), count in instance_counts.items():
                record_metric(
                    GPU_INSTANCES_ACTIVE,
                    count,
                    provider=provider,
                    instance_type=instance_type,
                )
                record_metric(
                    GPU_COST_HOURLY,
                    hourly_costs[(provider, instance_type)],
                    provider=provider,
                    instance_type=instance_type,
                )

    def get_status(self) -> dict[str, Any]:
        """Get current status of GPU manager."""
        return {
            "running": self.running,
            "active_instances": len(self.active_instances),
            "queue_metrics": asdict(self.queue_metrics),
            "cost_tracking": self.cost_tracking,
            "instances": {
                instance_id: {
                    "type": inst.instance_type.value,
                    "status": inst.status,
                    "current_tasks": inst.current_tasks,
                    "cost_incurred": inst.cost_incurred,
                }
                for instance_id, inst in self.active_instances.items()
            },
        }


# Global instance
gpu_manager = GPUAutoSpinManager()


async def main():
    """Example usage of GPU Auto-Spin Manager."""
    try:
        await gpu_manager.start_monitoring()
    except KeyboardInterrupt:
        await gpu_manager.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(main())
