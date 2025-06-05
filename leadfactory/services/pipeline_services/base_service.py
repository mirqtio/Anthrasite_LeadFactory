"""
Base service class for pipeline microservices.

Provides common functionality for all pipeline services including
health checks, metrics, error handling, and service discovery.
"""

import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    """Configuration for pipeline services."""

    service_name: str
    service_version: str = "1.0.0"
    host: str = "127.0.0.1"  # nosec B104
    port: int = 8000
    workers: int = 1
    debug: bool = False
    enable_metrics: bool = True
    enable_tracing: bool = True
    kafka_brokers: str = os.getenv("KAFKA_BROKERS", "localhost:9092")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    postgres_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/leadfactory",  # pragma: allowlist secret
    )


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: datetime
    service: str
    version: str
    uptime_seconds: float
    dependencies: dict[str, str]
    metrics: dict[str, Any]


class TaskRequest(BaseModel):
    """Base task request model."""

    task_id: str
    priority: int = 5
    metadata: Optional[dict[str, Any]] = None
    timeout_seconds: Optional[int] = 300


class TaskResponse(BaseModel):
    """Base task response model."""

    task_id: str
    status: str  # success, error, processing
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    processing_time_ms: float
    timestamp: datetime


class BasePipelineService(ABC):
    """
    Base class for all pipeline microservices.

    Provides common functionality including FastAPI app setup,
    health checks, metrics collection, and error handling.
    """

    def __init__(self, config: ServiceConfig):
        """Initialize the service with configuration."""
        self.config = config
        self.start_time = time.time()
        self.app = FastAPI(
            title=f"{config.service_name} API",
            version=config.service_version,
            description=f"Scalable {config.service_name} service for LeadFactory pipeline",
        )

        # Add CORS middleware with secure defaults
        allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key"],
        )

        # Service metrics
        self.metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_error": 0,
            "processing_time_total": 0.0,
            "active_tasks": 0,
        }

        # Setup routes
        self._setup_routes()

        logger.info(
            f"Initialized {config.service_name} service v{config.service_version}"
        )

    def _setup_routes(self):
        """Setup FastAPI routes for the service."""

        @self.app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint."""
            dependencies = await self._check_dependencies()

            return HealthResponse(
                status=(
                    "healthy"
                    if all(status == "ok" for status in dependencies.values())
                    else "degraded"
                ),
                timestamp=datetime.utcnow(),
                service=self.config.service_name,
                version=self.config.service_version,
                uptime_seconds=time.time() - self.start_time,
                dependencies=dependencies,
                metrics=self.metrics.copy(),
            )

        @self.app.get("/metrics")
        async def get_metrics():
            """Prometheus-compatible metrics endpoint."""
            metrics_text = []
            for metric_name, value in self.metrics.items():
                metrics_text.append(
                    f"leadfactory_{self.config.service_name}_{metric_name} {value}"
                )
            return "\n".join(metrics_text)

        @self.app.post("/process", response_model=TaskResponse)
        async def process_task(request: TaskRequest):
            """Process a task through this pipeline stage."""
            start_time = time.time()
            self.metrics["requests_total"] += 1
            self.metrics["active_tasks"] += 1

            try:
                # Call the abstract process method
                result = await self._process_task(request)

                processing_time = (time.time() - start_time) * 1000
                self.metrics["requests_success"] += 1
                self.metrics["processing_time_total"] += processing_time

                return TaskResponse(
                    task_id=request.task_id,
                    status="success",
                    result=result,
                    processing_time_ms=processing_time,
                    timestamp=datetime.utcnow(),
                )

            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                self.metrics["requests_error"] += 1

                logger.error(f"Task {request.task_id} failed: {e}")

                return TaskResponse(
                    task_id=request.task_id,
                    status="error",
                    error=str(e),
                    processing_time_ms=processing_time,
                    timestamp=datetime.utcnow(),
                )
            finally:
                self.metrics["active_tasks"] -= 1

        @self.app.get("/status")
        async def get_status():
            """Get detailed service status."""
            return {
                "service": self.config.service_name,
                "version": self.config.service_version,
                "uptime_seconds": time.time() - self.start_time,
                "metrics": self.metrics,
                "config": {
                    "host": self.config.host,
                    "port": self.config.port,
                    "workers": self.config.workers,
                    "debug": self.config.debug,
                },
            }

    async def _check_dependencies(self) -> dict[str, str]:
        """Check the health of service dependencies."""
        dependencies = {
            "database": "ok",  # Implement actual health checks
            "redis": "ok",
            "kafka": "ok",
        }

        # Override in subclasses to implement actual dependency checks
        return dependencies

    @abstractmethod
    async def _process_task(self, request: TaskRequest) -> dict[str, Any]:
        """
        Process a task through this pipeline stage.

        Must be implemented by each service to define the specific
        processing logic for that pipeline stage.

        Args:
            request: Task request with data and parameters

        Returns:
            Dictionary containing the processing results
        """
        pass

    def run(self):
        """Run the service."""
        logger.info(
            f"Starting {self.config.service_name} service on {self.config.host}:{self.config.port}"
        )

        uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            workers=self.config.workers,
            log_level="debug" if self.config.debug else "info",
        )


class ServiceRegistry:
    """Service registry for microservices discovery."""

    def __init__(self):
        self.services = {}

    def register_service(
        self, service_name: str, host: str, port: int, health_endpoint: str = "/health"
    ):
        """Register a service in the registry."""
        self.services[service_name] = {
            "host": host,
            "port": port,
            "health_endpoint": health_endpoint,
            "registered_at": datetime.utcnow(),
            "status": "unknown",
        }
        logger.info(f"Registered service {service_name} at {host}:{port}")

    def get_service(self, service_name: str) -> Optional[dict[str, Any]]:
        """Get service information by name."""
        return self.services.get(service_name)

    def list_services(self) -> dict[str, dict[str, Any]]:
        """List all registered services."""
        return self.services.copy()

    async def check_service_health(self, service_name: str) -> bool:
        """Check if a service is healthy."""
        service = self.get_service(service_name)
        if not service:
            return False

        try:
            # Implement HTTP health check
            # This would use aiohttp to check the health endpoint
            return True  # Placeholder
        except Exception as e:
            logger.warning(f"Health check failed for {service_name}: {e}")
            return False


# Global service registry instance
service_registry = ServiceRegistry()
