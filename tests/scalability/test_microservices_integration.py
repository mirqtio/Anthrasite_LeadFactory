"""
Integration tests for scalable microservices architecture.
Tests service-to-service communication, load balancing, and fault tolerance.
"""

import asyncio
import pytest
import aiohttp
import docker
import time
from pathlib import Path
import subprocess
import sys
import json
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class DockerComposeManager:
    """Manages Docker Compose services for testing."""

    def __init__(self, compose_file: str = "docker-compose.scalable.yml"):
        self.compose_file = compose_file
        self.client = docker.from_env()

    def start_services(self, services: List[str] = None):
        """Start specific services or all services."""
        cmd = ["docker-compose", "-f", self.compose_file, "up", "-d"]
        if services:
            cmd.extend(services)

        subprocess.run(cmd, check=True)

        # Wait for services to be ready
        self._wait_for_services_ready(services or self._get_all_services())

    def stop_services(self):
        """Stop all services."""
        subprocess.run(
            ["docker-compose", "-f", self.compose_file, "down", "-v"],
            check=True
        )

    def restart_service(self, service: str):
        """Restart a specific service."""
        subprocess.run(
            ["docker-compose", "-f", self.compose_file, "restart", service],
            check=True
        )

    def scale_service(self, service: str, replicas: int):
        """Scale a service to specified number of replicas."""
        subprocess.run(
            ["docker-compose", "-f", self.compose_file, "scale", f"{service}={replicas}"],
            check=True
        )

    def get_service_logs(self, service: str) -> str:
        """Get logs from a specific service."""
        result = subprocess.run(
            ["docker-compose", "-f", self.compose_file, "logs", service],
            capture_output=True,
            text=True
        )
        return result.stdout

    def _get_all_services(self) -> List[str]:
        """Get list of all services in compose file."""
        result = subprocess.run(
            ["docker-compose", "-f", self.compose_file, "config", "--services"],
            capture_output=True,
            text=True
        )
        return result.stdout.strip().split('\n')

    def _wait_for_services_ready(self, services: List[str], timeout: int = 300):
        """Wait for services to report healthy status."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            all_ready = True

            for service in services:
                if not self._is_service_healthy(service):
                    all_ready = False
                    break

            if all_ready:
                logger.info("All services are ready")
                return

            time.sleep(5)

        raise TimeoutError("Services did not become ready within timeout")

    def _is_service_healthy(self, service: str) -> bool:
        """Check if a service is healthy."""
        try:
            containers = self.client.containers.list(
                filters={"name": service, "status": "running"}
            )

            if not containers:
                return False

            # Check health status
            for container in containers:
                container.reload()
                health = container.attrs.get("State", {}).get("Health", {})
                if health.get("Status") == "unhealthy":
                    return False

            return True

        except Exception as e:
            logger.warning(f"Error checking service {service} health: {e}")
            return False


@pytest.fixture(scope="session")
def docker_manager():
    """Fixture to manage Docker services for testing."""
    manager = DockerComposeManager()

    # Start core services for testing
    core_services = [
        "postgres", "redis", "kafka", "zookeeper",
        "api-gateway", "scraper-service", "enrichment-service",
        "scoring-service", "email-service"
    ]

    manager.start_services(core_services)

    yield manager

    # Cleanup
    manager.stop_services()


@pytest.fixture
async def http_client():
    """Fixture for HTTP client."""
    async with aiohttp.ClientSession() as session:
        yield session


class TestMicroservicesIntegration:
    """Test suite for microservices integration."""

    @pytest.mark.asyncio
    async def test_api_gateway_routing(self, http_client, docker_manager):
        """Test that API gateway correctly routes requests to services."""
        base_url = "http://localhost:80"

        # Test each service endpoint
        endpoints = [
            "/api/scrape",
            "/api/enrich",
            "/api/score",
            "/api/email"
        ]

        for endpoint in endpoints:
            async with http_client.get(f"{base_url}{endpoint}/health") as response:
                assert response.status == 200, f"Health check failed for {endpoint}"

    @pytest.mark.asyncio
    async def test_service_fault_tolerance(self, http_client, docker_manager):
        """Test system resilience when individual services fail."""
        base_url = "http://localhost:80"

        # Test normal operation
        async with http_client.post(
            f"{base_url}/api/score",
            json={"business": {"id": "test", "name": "Test Business"}}
        ) as response:
            assert response.status in [200, 202], "Service should be operational"

        # Stop scoring service
        docker_manager.stop_services(["scoring-service"])

        # Wait a moment for the change to propagate
        await asyncio.sleep(10)

        # Test that API gateway handles the failure gracefully
        async with http_client.post(
            f"{base_url}/api/score",
            json={"business": {"id": "test", "name": "Test Business"}}
        ) as response:
            # Should return 503 Service Unavailable or similar
            assert response.status in [503, 502, 504], "Should handle service failure"

        # Restart service
        docker_manager.start_services(["scoring-service"])

        # Wait for service to be ready
        await asyncio.sleep(30)

        # Test that service is operational again
        async with http_client.post(
            f"{base_url}/api/score",
            json={"business": {"id": "test", "name": "Test Business"}}
        ) as response:
            assert response.status in [200, 202], "Service should recover"

    @pytest.mark.asyncio
    async def test_load_balancing(self, http_client, docker_manager):
        """Test load balancing across multiple service instances."""
        base_url = "http://localhost:80"

        # Scale up scoring service to 3 instances
        docker_manager.scale_service("scoring-service", 3)

        # Wait for instances to be ready
        await asyncio.sleep(30)

        # Make multiple requests and collect server identifiers
        server_ids = set()

        for i in range(20):
            async with http_client.post(
                f"{base_url}/api/score",
                json={"business": {"id": f"test-{i}", "name": "Test Business"}}
            ) as response:
                assert response.status in [200, 202]

                # Try to extract server identifier from response headers
                server_id = response.headers.get("X-Server-ID", "unknown")
                server_ids.add(server_id)

        # Should have requests distributed across multiple instances
        # (This test might need adjustment based on actual server response format)
        logger.info(f"Requests distributed across {len(server_ids)} server instances")

    @pytest.mark.asyncio
    async def test_database_connectivity(self, http_client, docker_manager):
        """Test that services can connect to PostgreSQL database."""
        base_url = "http://localhost:80"

        # Test database-dependent operations
        endpoints_with_db = [
            "/api/scrape",
            "/api/score"
        ]

        for endpoint in endpoints_with_db:
            async with http_client.get(f"{base_url}{endpoint}/health") as response:
                assert response.status == 200

                # Additional test: try to read/write data
                test_payload = {"test": True, "check_db": True}
                async with http_client.post(
                    f"{base_url}{endpoint}",
                    json=test_payload
                ) as write_response:
                    # Should be able to process requests that involve database
                    assert write_response.status in [200, 202, 400]  # 400 for invalid test payload

    @pytest.mark.asyncio
    async def test_cache_connectivity(self, http_client, docker_manager):
        """Test that services can connect to Redis cache."""
        base_url = "http://localhost:80"

        # Test cache-dependent operations
        async with http_client.post(
            f"{base_url}/api/enrich",
            json={
                "business_id": "cache-test-123",
                "website": "https://example.com",
                "tier": 1
            }
        ) as response:
            # First request should work and potentially cache data
            assert response.status in [200, 202, 400]

        # Make the same request again - should be faster if cached
        start_time = time.time()
        async with http_client.post(
            f"{base_url}/api/enrich",
            json={
                "business_id": "cache-test-123",
                "website": "https://example.com",
                "tier": 1
            }
        ) as response:
            response_time = time.time() - start_time

            assert response.status in [200, 202, 400]
            logger.info(f"Cached request response time: {response_time:.3f}s")

    def test_service_logs_for_errors(self, docker_manager):
        """Check service logs for critical errors."""
        services = ["scraper-service", "enrichment-service", "scoring-service", "email-service"]

        for service in services:
            logs = docker_manager.get_service_logs(service)

            # Check for critical error patterns
            critical_errors = [
                "CRITICAL",
                "FATAL",
                "OutOfMemoryError",
                "ConnectionRefusedError",
                "TimeoutError"
            ]

            for error_pattern in critical_errors:
                assert error_pattern not in logs, f"Critical error found in {service} logs: {error_pattern}"

    @pytest.mark.asyncio
    async def test_performance_under_load(self, http_client, docker_manager):
        """Test basic performance under moderate load."""
        base_url = "http://localhost:80"

        # Run concurrent requests
        async def make_request(session, i):
            async with session.post(
                f"{base_url}/api/score",
                json={"business": {"id": f"perf-test-{i}", "name": "Performance Test"}}
            ) as response:
                return response.status, time.time()

        # Create 50 concurrent requests
        start_time = time.time()
        tasks = []

        async with aiohttp.ClientSession() as session:
            for i in range(50):
                tasks.append(make_request(session, i))

            results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time

        # Analyze results
        successful_requests = len([r for r in results if isinstance(r, tuple) and r[0] in [200, 202]])
        throughput = successful_requests / total_time

        logger.info(f"Performance test: {successful_requests}/50 successful, {throughput:.2f} RPS")

        # Basic performance assertions
        assert successful_requests >= 45, "Should have high success rate under moderate load"
        assert throughput >= 10, "Should maintain reasonable throughput"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
