"""
DAG Traversal Module for LeadFactory Pipeline.

This module implements topological sorting and dependency management for the
pipeline stages, allowing for dynamic execution order based on available
capabilities and dependencies.
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from leadfactory.config.node_config import (
    DeploymentEnvironment,
    NodeType,
    get_enabled_capabilities,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class PipelineStage(Enum):
    """Enumeration of available pipeline stages."""

    SCRAPE = "scrape"
    ENRICH = "enrich"
    DEDUPE = "dedupe"
    SCORE = "score"
    EMAIL_QUEUE = "email_queue"
    MOCKUP = "mockup"
    SCREENSHOT = "screenshot"
    UNIFIED_GPT4O = "unified_gpt4o"  # New unified terminal node


class DependencyType(Enum):
    """Types of dependencies between pipeline stages."""

    REQUIRED = "required"  # Must be completed for stage to run
    OPTIONAL = "optional"  # Enhances output but not required
    CONDITIONAL = "conditional"  # Required only under certain conditions


@dataclass
class StageDependency:
    """Represents a dependency between pipeline stages."""

    from_stage: PipelineStage
    to_stage: PipelineStage
    dependency_type: DependencyType
    condition: Optional[str] = None  # Condition for conditional dependencies


@dataclass
class StageResult:
    """Result of executing a pipeline stage."""

    stage: PipelineStage
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time: float = 0.0
    dependencies_met: list[PipelineStage] = field(default_factory=list)
    dependencies_missing: list[PipelineStage] = field(default_factory=list)


class PipelineDAG:
    """
    Directed Acyclic Graph for pipeline stage management.

    Manages dependencies between pipeline stages and provides topological
    sorting for execution order.
    """

    def __init__(self):
        """Initialize the pipeline DAG with default dependencies."""
        self.dependencies: dict[PipelineStage, list[StageDependency]] = defaultdict(
            list
        )
        self.reverse_dependencies: dict[PipelineStage, list[StageDependency]] = (
            defaultdict(list)
        )
        self._setup_default_dependencies()

    def _setup_default_dependencies(self):
        """Set up the default pipeline dependencies."""
        # Define the standard pipeline flow
        default_deps = [
            # Scraping is the entry point - no dependencies
            # Enrichment depends on scraping
            StageDependency(
                PipelineStage.SCRAPE, PipelineStage.ENRICH, DependencyType.REQUIRED
            ),
            # Deduplication can run after scraping (optional enrichment)
            StageDependency(
                PipelineStage.SCRAPE, PipelineStage.DEDUPE, DependencyType.REQUIRED
            ),
            StageDependency(
                PipelineStage.ENRICH, PipelineStage.DEDUPE, DependencyType.OPTIONAL
            ),
            # Scoring depends on enrichment and deduplication
            StageDependency(
                PipelineStage.ENRICH, PipelineStage.SCORE, DependencyType.REQUIRED
            ),
            StageDependency(
                PipelineStage.DEDUPE, PipelineStage.SCORE, DependencyType.REQUIRED
            ),
            # Email queue depends on scoring
            StageDependency(
                PipelineStage.SCORE, PipelineStage.EMAIL_QUEUE, DependencyType.REQUIRED
            ),
            # Mockup and screenshot can run after enrichment (deprecated - replaced by unified node)
            StageDependency(
                PipelineStage.ENRICH, PipelineStage.MOCKUP, DependencyType.OPTIONAL
            ),
            StageDependency(
                PipelineStage.ENRICH, PipelineStage.SCREENSHOT, DependencyType.OPTIONAL
            ),
            # Unified GPT-4o node - terminal node that requires enrichment and scoring
            StageDependency(
                PipelineStage.ENRICH,
                PipelineStage.UNIFIED_GPT4O,
                DependencyType.REQUIRED,
            ),
            StageDependency(
                PipelineStage.SCORE,
                PipelineStage.UNIFIED_GPT4O,
                DependencyType.REQUIRED,
            ),
            # Optional dependencies for unified node to enhance output quality
            StageDependency(
                PipelineStage.DEDUPE,
                PipelineStage.UNIFIED_GPT4O,
                DependencyType.OPTIONAL,
            ),
            StageDependency(
                PipelineStage.SCREENSHOT,
                PipelineStage.UNIFIED_GPT4O,
                DependencyType.OPTIONAL,
            ),
        ]

        for dep in default_deps:
            self.add_dependency(dep)

    def add_dependency(self, dependency: StageDependency):
        """Add a dependency to the DAG."""
        self.dependencies[dependency.to_stage].append(dependency)
        self.reverse_dependencies[dependency.from_stage].append(dependency)

    def remove_dependency(self, from_stage: PipelineStage, to_stage: PipelineStage):
        """Remove a dependency from the DAG."""
        self.dependencies[to_stage] = [
            dep for dep in self.dependencies[to_stage] if dep.from_stage != from_stage
        ]
        self.reverse_dependencies[from_stage] = [
            dep
            for dep in self.reverse_dependencies[from_stage]
            if dep.to_stage != to_stage
        ]

    def get_dependencies(self, stage: PipelineStage) -> list[StageDependency]:
        """Get all dependencies for a given stage."""
        return self.dependencies[stage]

    def get_dependents(self, stage: PipelineStage) -> list[StageDependency]:
        """Get all stages that depend on the given stage."""
        return self.reverse_dependencies[stage]

    def topological_sort(
        self,
        available_stages: Optional[set[PipelineStage]] = None,
        node_type: Optional[NodeType] = None,
        budget_cents: Optional[float] = None,
    ) -> list[PipelineStage]:
        """
        Perform topological sorting on the DAG.

        Args:
            available_stages: Set of stages that are available to run
            node_type: Type of node for capability checking
            budget_cents: Available budget for cost-aware filtering

        Returns:
            List of stages in topological order
        """
        if available_stages is None:
            available_stages = set(PipelineStage)

        # Filter stages based on node capabilities if provided
        if node_type is not None:
            enabled_capabilities = get_enabled_capabilities(
                node_type, budget_cents, None
            )  # Auto-detect environment
            # Convert NodeCapability objects to capability name strings
            capability_names = [cap.name for cap in enabled_capabilities]
            available_stages = self._filter_by_capabilities(
                available_stages, capability_names
            )

        # Calculate in-degrees for available stages
        in_degree = defaultdict(int)
        for stage in available_stages:
            in_degree[stage] = 0

        for stage in available_stages:
            for dep in self.dependencies[stage]:
                if dep.from_stage in available_stages:
                    if dep.dependency_type == DependencyType.REQUIRED:
                        in_degree[stage] += 1

        # Initialize queue with stages that have no dependencies
        queue = deque([stage for stage in available_stages if in_degree[stage] == 0])
        result = []

        while queue:
            current = queue.popleft()
            result.append(current)

            # Update in-degrees of dependent stages
            for dep in self.reverse_dependencies[current]:
                if (
                    dep.to_stage in available_stages
                    and dep.dependency_type == DependencyType.REQUIRED
                ):
                    in_degree[dep.to_stage] -= 1
                    if in_degree[dep.to_stage] == 0:
                        queue.append(dep.to_stage)

        # Check for cycles
        if len(result) != len(available_stages):
            remaining = available_stages - set(result)
            logger.warning(f"Cycle detected in DAG. Remaining stages: {remaining}")
            # Add remaining stages in arbitrary order
            result.extend(remaining)

        return result

    def _filter_by_capabilities(
        self, stages: set[PipelineStage], capabilities: list[str]
    ) -> set[PipelineStage]:
        """Filter stages based on available capabilities."""
        # Map stages to required capabilities based on actual NodeCapability names
        stage_capabilities = {
            # Basic pipeline stages - always available
            PipelineStage.SCRAPE: [],  # No specific capability requirement
            PipelineStage.DEDUPE: [],  # No specific capability requirement
            PipelineStage.SCORE: [],  # No specific capability requirement
            # ENRICH stage requires any enrich capability
            PipelineStage.ENRICH: [],  # Will be allowed if any ENRICH capabilities exist
            # Final output stages require specific capabilities
            PipelineStage.EMAIL_QUEUE: ["email_generation"],
            PipelineStage.MOCKUP: ["mockup_generation"],
            PipelineStage.SCREENSHOT: ["screenshot_capture"],
            PipelineStage.UNIFIED_GPT4O: [],  # Generic stage, no specific requirement
        }

        # ENRICH stage should be available if we have any ENRICH node capabilities
        enrich_capabilities = {
            "tech_stack_analysis",
            "core_web_vitals",
            "screenshot_capture",
            "semrush_site_audit",
        }
        has_enrich_capability = any(cap in enrich_capabilities for cap in capabilities)

        filtered_stages = set()
        for stage in stages:
            required_caps = stage_capabilities.get(stage, [])

            # Special handling for ENRICH stage
            if stage == PipelineStage.ENRICH:
                if has_enrich_capability:
                    filtered_stages.add(stage)
                else:
                    logger.info(
                        f"Stage {stage.value} filtered out due to no enrich capabilities available"
                    )
            elif all(cap in capabilities for cap in required_caps):
                filtered_stages.add(stage)
            else:
                missing_caps = set(required_caps) - set(capabilities)
                if missing_caps:  # Only log if there are missing capabilities
                    logger.info(
                        f"Stage {stage.value} filtered out due to missing capabilities: "
                        f"{missing_caps}"
                    )

        return filtered_stages

    def validate_dependencies(
        self, completed_stages: set[PipelineStage], target_stage: PipelineStage
    ) -> tuple[bool, list[PipelineStage], list[PipelineStage]]:
        """
        Validate if dependencies are met for a target stage.

        Args:
            completed_stages: Set of stages that have been completed
            target_stage: Stage to validate dependencies for

        Returns:
            Tuple of (can_run, missing_required, missing_optional)
        """
        dependencies = self.get_dependencies(target_stage)
        missing_required = []
        missing_optional = []

        for dep in dependencies:
            if dep.from_stage not in completed_stages:
                if dep.dependency_type == DependencyType.REQUIRED:
                    missing_required.append(dep.from_stage)
                elif dep.dependency_type == DependencyType.OPTIONAL:
                    missing_optional.append(dep.from_stage)
                elif dep.dependency_type == DependencyType.CONDITIONAL:
                    # For now, treat conditional as optional
                    # Evaluate condition based on node data
                    if callable(edge.condition):
                        if not edge.condition(node_data):
                            continue
                    elif isinstance(edge.condition, str):
                        # Simple string conditions
                        if (
                            edge.condition == "success"
                            and node_data.get("status") != "success"
                        ) or (
                            edge.condition == "failure"
                            and node_data.get("status") != "failure"
                        ):
                            continue
                    missing_optional.append(dep.from_stage)

        can_run = len(missing_required) == 0
        return can_run, missing_required, missing_optional

    def get_execution_plan(
        self,
        target_stages: Optional[set[PipelineStage]] = None,
        node_type: Optional[NodeType] = None,
        budget_cents: Optional[float] = None,
    ) -> list[PipelineStage]:
        """
        Get an execution plan for the pipeline.

        Args:
            target_stages: Specific stages to include in the plan
            node_type: Type of node for capability checking
            budget_cents: Available budget for cost-aware filtering

        Returns:
            Ordered list of stages to execute
        """
        if target_stages is None:
            target_stages = set(PipelineStage)

        # Get topological order
        execution_order = self.topological_sort(target_stages, node_type, budget_cents)

        logger.info(f"Generated execution plan: {[s.value for s in execution_order]}")
        return execution_order

    def get_stage_info(self, stage: PipelineStage) -> dict[str, Any]:
        """Get detailed information about a stage."""
        dependencies = self.get_dependencies(stage)
        dependents = self.get_dependents(stage)

        return {
            "stage": stage.value,
            "dependencies": [
                {
                    "from": dep.from_stage.value,
                    "type": dep.dependency_type.value,
                    "condition": dep.condition,
                }
                for dep in dependencies
            ],
            "dependents": [
                {
                    "to": dep.to_stage.value,
                    "type": dep.dependency_type.value,
                    "condition": dep.condition,
                }
                for dep in dependents
            ],
        }


class PipelineExecutor:
    """
    Executes pipeline stages in the correct order based on DAG traversal.
    """

    def __init__(self, dag: Optional[PipelineDAG] = None):
        """Initialize the pipeline executor."""
        self.dag = dag or PipelineDAG()
        self.completed_stages: set[PipelineStage] = set()
        self.stage_results: dict[PipelineStage, StageResult] = {}

    def can_execute_stage(self, stage: PipelineStage) -> bool:
        """Check if a stage can be executed based on its dependencies."""
        can_run, missing_required, missing_optional = self.dag.validate_dependencies(
            self.completed_stages, stage
        )

        if missing_required:
            logger.warning(
                f"Cannot execute {stage.value}: missing required dependencies: "
                f"{[s.value for s in missing_required]}"
            )

        if missing_optional:
            logger.info(
                f"Stage {stage.value} missing optional dependencies: "
                f"{[s.value for s in missing_optional]}"
            )

        return can_run

    def mark_stage_completed(self, stage: PipelineStage, result: StageResult):
        """Mark a stage as completed and store its result."""
        self.completed_stages.add(stage)
        self.stage_results[stage] = result
        logger.info(f"Stage {stage.value} completed successfully")

    def mark_stage_failed(self, stage: PipelineStage, error: str):
        """Mark a stage as failed."""
        result = StageResult(stage=stage, success=False, error=error)
        self.stage_results[stage] = result
        logger.error(f"Stage {stage.value} failed: {error}")

    def get_next_executable_stages(
        self, available_stages: Optional[set[PipelineStage]] = None
    ) -> list[PipelineStage]:
        """Get the next stages that can be executed."""
        if available_stages is None:
            available_stages = set(PipelineStage)

        # Filter out already completed stages
        remaining_stages = available_stages - self.completed_stages

        # Find stages that can be executed
        executable = []
        for stage in remaining_stages:
            if self.can_execute_stage(stage):
                executable.append(stage)

        return executable

    def reset(self):
        """Reset the executor state."""
        self.completed_stages.clear()
        self.stage_results.clear()
        logger.info("Pipeline executor state reset")


# Convenience functions for easy access
def create_pipeline_dag() -> PipelineDAG:
    """Create a new pipeline DAG with default configuration."""
    return PipelineDAG()


def get_execution_plan(
    target_stages: Optional[set[PipelineStage]] = None,
    node_type: Optional[NodeType] = None,
    budget_cents: Optional[float] = None,
) -> list[PipelineStage]:
    """Get an execution plan for the pipeline."""
    dag = create_pipeline_dag()
    return dag.get_execution_plan(target_stages, node_type, budget_cents)


def validate_stage_dependencies(
    completed_stages: set[PipelineStage], target_stage: PipelineStage
) -> tuple[bool, list[PipelineStage], list[PipelineStage]]:
    """Validate dependencies for a target stage."""
    dag = create_pipeline_dag()
    return dag.validate_dependencies(completed_stages, target_stage)
