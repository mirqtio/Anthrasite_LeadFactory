"""
Pipeline orchestrator for coordinating microservices.

Provides workflow management, service discovery, and coordination
for the scalable pipeline architecture.
"""

import asyncio
import contextlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from .base_service import ServiceRegistry, service_registry

logger = logging.getLogger(__name__)


@dataclass
class PipelineStage:
    """Definition of a pipeline stage."""

    name: str
    service_name: str
    dependencies: list[str]
    timeout_seconds: int = 300
    retry_attempts: int = 3
    required: bool = True


@dataclass
class WorkflowDefinition:
    """Definition of a complete pipeline workflow."""

    name: str
    version: str
    stages: list[PipelineStage]
    global_timeout_seconds: int = 3600
    parallel_execution: bool = False


class PipelineOrchestrator:
    """
    Orchestrates the complete pipeline workflow across microservices.

    Manages service discovery, task routing, error handling, and
    workflow coordination for scalable processing.
    """

    def __init__(self, registry: ServiceRegistry = None):
        """Initialize the orchestrator."""
        self.registry = registry or service_registry
        self.workflows = {}
        self.active_executions = {}

        # Define the default pipeline workflow
        self._define_default_workflow()

        logger.info("Pipeline orchestrator initialized")

    def _define_default_workflow(self):
        """Define the default lead processing workflow."""
        default_workflow = WorkflowDefinition(
            name="lead_processing",
            version="1.0.0",
            stages=[
                PipelineStage(
                    name="scrape",
                    service_name="scrape",
                    dependencies=[],
                    timeout_seconds=600,
                    retry_attempts=2,
                ),
                PipelineStage(
                    name="enrich",
                    service_name="enrich",
                    dependencies=["scrape"],
                    timeout_seconds=900,
                    retry_attempts=3,
                ),
                PipelineStage(
                    name="dedupe",
                    service_name="dedupe",
                    dependencies=["enrich"],
                    timeout_seconds=300,
                    retry_attempts=2,
                ),
                PipelineStage(
                    name="score",
                    service_name="score",
                    dependencies=["dedupe"],
                    timeout_seconds=180,
                    retry_attempts=1,
                ),
                PipelineStage(
                    name="mockup",
                    service_name="mockup",
                    dependencies=["score"],
                    timeout_seconds=1200,
                    retry_attempts=2,
                    required=False,  # Optional stage
                ),
                PipelineStage(
                    name="email",
                    service_name="email",
                    dependencies=["mockup"],
                    timeout_seconds=300,
                    retry_attempts=3,
                ),
            ],
        )

        self.workflows["default"] = default_workflow

    async def execute_workflow(
        self,
        workflow_name: str = "default",
        input_data: dict[str, Any] = None,
        execution_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Execute a complete pipeline workflow.

        Args:
            workflow_name: Name of workflow to execute
            input_data: Initial data for the workflow
            execution_id: Unique ID for this execution

        Returns:
            Workflow execution results
        """
        if workflow_name not in self.workflows:
            raise ValueError(f"Unknown workflow: {workflow_name}")

        workflow = self.workflows[workflow_name]
        execution_id = (
            execution_id or f"{workflow_name}_{datetime.utcnow().isoformat()}"
        )

        logger.info(f"Starting workflow execution {execution_id}")

        execution_context = {
            "execution_id": execution_id,
            "workflow": workflow,
            "start_time": datetime.utcnow(),
            "status": "running",
            "stages_completed": [],
            "stages_failed": [],
            "stage_results": {},
            "input_data": input_data or {},
        }

        self.active_executions[execution_id] = execution_context

        try:
            # Execute stages in dependency order
            if workflow.parallel_execution:
                result = await self._execute_stages_parallel(execution_context)
            else:
                result = await self._execute_stages_sequential(execution_context)

            execution_context["status"] = "completed"
            execution_context["end_time"] = datetime.utcnow()

            return result

        except Exception as e:
            execution_context["status"] = "failed"
            execution_context["error"] = str(e)
            execution_context["end_time"] = datetime.utcnow()

            logger.error(f"Workflow execution {execution_id} failed: {e}")
            raise
        finally:
            # Clean up after a delay
            asyncio.create_task(self._cleanup_execution(execution_id, delay=3600))

    async def _execute_stages_sequential(
        self, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute workflow stages sequentially."""
        workflow = context["workflow"]
        results = {}

        for stage in workflow.stages:
            # Check if dependencies are satisfied
            for dep in stage.dependencies:
                if dep not in context["stages_completed"]:
                    if stage.required:
                        raise RuntimeError(
                            f"Stage {stage.name} dependency {dep} not satisfied"
                        )
                    else:
                        logger.warning(
                            f"Skipping optional stage {stage.name} due to missing dependency {dep}"
                        )
                        continue

            # Execute the stage
            try:
                stage_result = await self._execute_stage(stage, context, results)
                results[stage.name] = stage_result
                context["stages_completed"].append(stage.name)
                context["stage_results"][stage.name] = stage_result

                logger.info(f"Stage {stage.name} completed successfully")

            except Exception as e:
                context["stages_failed"].append(stage.name)

                if stage.required:
                    logger.error(f"Required stage {stage.name} failed: {e}")
                    raise
                else:
                    logger.warning(f"Optional stage {stage.name} failed: {e}")
                    results[stage.name] = {"error": str(e), "status": "failed"}

        return results

    async def _execute_stage(
        self,
        stage: PipelineStage,
        context: dict[str, Any],
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single pipeline stage."""
        service_info = self.registry.get_service(stage.service_name)
        if not service_info:
            raise RuntimeError(f"Service {stage.service_name} not found in registry")

        # Prepare request data
        request_data = {
            "task_id": f"{context['execution_id']}_{stage.name}",
            "priority": 5,
            "metadata": {
                "stage_name": stage.name,
                "input_data": context["input_data"],
                "previous_results": previous_results,
            },
        }

        # Make HTTP request to service
        service_url = f"http://{service_info['host']}:{service_info['port']}/process"

        for attempt in range(stage.retry_attempts + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        service_url,
                        json=request_data,
                        timeout=aiohttp.ClientTimeout(total=stage.timeout_seconds),
                    ) as response:
                        response.raise_for_status()
                        result = await response.json()

                        if result["status"] == "success":
                            return result["result"]
                        else:
                            raise RuntimeError(
                                f"Stage failed: {result.get('error', 'Unknown error')}"
                            )

            except Exception as e:
                if attempt < stage.retry_attempts:
                    wait_time = 2**attempt  # Exponential backoff
                    logger.warning(
                        f"Stage {stage.name} attempt {attempt + 1} failed, retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Stage {stage.name} failed after {stage.retry_attempts} retries: {e}"
                    )

    async def _cleanup_execution(self, execution_id: str, delay: int = 3600):
        """Clean up execution context after delay."""
        await asyncio.sleep(delay)
        if execution_id in self.active_executions:
            del self.active_executions[execution_id]
            logger.debug(f"Cleaned up execution {execution_id}")

    def get_execution_status(self, execution_id: str) -> Optional[dict[str, Any]]:
        """Get the status of a workflow execution."""
        return self.active_executions.get(execution_id)

    def list_active_executions(self) -> list[str]:
        """List all active workflow executions."""
        return list(self.active_executions.keys())

    async def health_check_services(self) -> dict[str, dict[str, Any]]:
        """Check health of all registered services."""
        health_status = {}

        for service_name, service_info in self.registry.list_services().items():
            try:
                health_url = (
                    f"http://{service_info['host']}:{service_info['port']}/health"
                )

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        health_url, timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            health_data = await response.json()
                            health_status[service_name] = {
                                "status": "healthy",
                                "details": health_data,
                            }
                        else:
                            health_status[service_name] = {
                                "status": "unhealthy",
                                "error": f"HTTP {response.status}",
                            }

            except Exception as e:
                health_status[service_name] = {"status": "unreachable", "error": str(e)}

        return health_status


# Global orchestrator instance
orchestrator = PipelineOrchestrator()


async def main():
    """Example usage of the orchestrator."""
    # Register services (normally done by service startup)
    orchestrator.registry.register_service("scrape", "localhost", 8001)
    orchestrator.registry.register_service("enrich", "localhost", 8002)
    orchestrator.registry.register_service("dedupe", "localhost", 8003)
    orchestrator.registry.register_service("score", "localhost", 8004)
    orchestrator.registry.register_service("mockup", "localhost", 8005)
    orchestrator.registry.register_service("email", "localhost", 8006)

    # Execute workflow
    with contextlib.suppress(Exception):
        await orchestrator.execute_workflow(
            "default",
            {
                "zip_codes": ["10002", "98908"],
                "verticals": ["hvac", "plumber"],
                "tier_level": 2,
            },
        )


if __name__ == "__main__":
    asyncio.run(main())
