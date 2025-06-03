"""
Integration of Variant System with DAG Pipeline.

This module provides integration between the variant system and the existing
DAG traversal pipeline, enabling variant-aware pipeline execution.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from leadfactory.config.node_config import NodeType
from leadfactory.pipeline.dag_traversal import (
    PipelineDAG,
    PipelineExecutor,
    PipelineStage,
    StageDependency,
    StageResult,
)
from leadfactory.pipeline.variant_selector import (
    SelectionContext,
    SelectionResult,
    get_selection_manager,
)
from leadfactory.pipeline.variant_tracking import (
    EventType,
    get_variant_tracker,
    track_pipeline_start,
    track_variant_assignment,
)
from leadfactory.pipeline.variants import PipelineVariant, get_variant_registry
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VariantExecutionContext:
    """Context for variant-aware pipeline execution."""

    business_id: int
    variant_id: str
    variant_name: str
    session_id: str = ""
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if not self.session_id:
            self.session_id = str(uuid4())
        if self.metadata is None:
            self.metadata = {}


class VariantAwareDAG(PipelineDAG):
    """DAG that supports variant-specific configuration."""

    def __init__(self, variant: Optional[PipelineVariant] = None):
        super().__init__()
        self.variant = variant
        if variant:
            self._apply_variant_configuration()

    def _apply_variant_configuration(self):
        """Apply variant-specific configuration to the DAG."""
        if not self.variant:
            return

        # Add custom dependencies from the variant
        for dependency in self.variant.custom_dependencies:
            self.add_dependency(dependency)

        logger.info(f"Applied variant configuration for {self.variant.name}")

    def get_enabled_stages(self) -> Set[PipelineStage]:
        """Get stages enabled for this variant."""
        if not self.variant:
            return set(PipelineStage)

        return self.variant.get_enabled_stages()

    def topological_sort(
        self,
        available_stages: Optional[Set[PipelineStage]] = None,
        node_type: Optional[NodeType] = None,
        budget_cents: Optional[float] = None,
    ) -> List[PipelineStage]:
        """Override to filter by variant-enabled stages."""

        # Get enabled stages from variant
        enabled_stages = self.get_enabled_stages()

        # Combine with available stages filter
        if available_stages is not None:
            enabled_stages = enabled_stages.intersection(available_stages)

        return super().topological_sort(enabled_stages, node_type, budget_cents)

    def get_stage_configuration(self, stage: PipelineStage) -> Dict[str, Any]:
        """Get variant-specific configuration for a stage."""
        if not self.variant:
            return {}

        config = self.variant.get_stage_config(stage)
        return {
            "enabled": config.enabled,
            "parameters": config.parameters,
            "node_type": config.node_type,
            "cost_limit_cents": config.cost_limit_cents,
            "timeout_seconds": config.timeout_seconds,
            "retry_attempts": config.retry_attempts,
        }


class VariantAwareExecutor(PipelineExecutor):
    """Pipeline executor with variant tracking and configuration."""

    def __init__(
        self,
        execution_context: VariantExecutionContext,
        dag: Optional[VariantAwareDAG] = None,
    ):

        # Get the variant and create variant-aware DAG
        registry = get_variant_registry()
        variant = registry.get_variant(execution_context.variant_id)

        if not variant:
            logger.error(f"Variant {execution_context.variant_id} not found")
            raise ValueError(f"Variant {execution_context.variant_id} not found")

        variant_dag = dag or VariantAwareDAG(variant)
        super().__init__(variant_dag)

        self.execution_context = execution_context
        self.variant = variant
        self.tracker = get_variant_tracker()

        # Track variant assignment and pipeline start
        self._track_pipeline_start()

    def _track_pipeline_start(self):
        """Track the start of pipeline execution."""
        track_pipeline_start(
            variant_id=self.execution_context.variant_id,
            business_id=self.execution_context.business_id,
            session_id=self.execution_context.session_id,
            properties={
                "variant_name": self.execution_context.variant_name,
                "user_id": self.execution_context.user_id,
                **self.execution_context.metadata,
            },
        )

    def execute_stage(self, stage: PipelineStage, **kwargs) -> StageResult:
        """Execute a stage with variant tracking."""

        # Get stage configuration from variant
        stage_config = self.dag.get_stage_configuration(stage)

        # Check if stage is enabled
        if not stage_config.get("enabled", True):
            logger.info(f"Stage {stage.value} disabled for variant {self.variant.name}")
            return StageResult(
                stage=stage,
                success=True,
                skipped=True,
                message=f"Stage disabled for variant {self.variant.name}",
            )

        # Track stage start
        self.tracker.track_event(
            variant_id=self.execution_context.variant_id,
            business_id=self.execution_context.business_id,
            event_type=EventType.STAGE_STARTED,
            stage=stage.value,
            session_id=self.execution_context.session_id,
            properties={"stage_config": stage_config, **kwargs},
        )

        start_time = logger.info(
            f"Starting stage {stage.value} for variant {self.variant.name}"
        )

        try:
            # Apply variant-specific parameters
            variant_params = stage_config.get("parameters", {})
            merged_kwargs = {**kwargs, **variant_params}

            # Apply cost and timeout limits
            if stage_config.get("cost_limit_cents"):
                merged_kwargs["cost_limit_cents"] = stage_config["cost_limit_cents"]

            if stage_config.get("timeout_seconds"):
                merged_kwargs["timeout_seconds"] = stage_config["timeout_seconds"]

            # Execute the stage (this would call the actual stage implementation)
            result = super().execute_stage(stage, **merged_kwargs)

            # Track stage completion
            properties = {
                "success": result.success,
                "message": result.message,
            }
            if hasattr(result, "metadata"):
                properties.update(result.metadata)

            self.tracker.track_stage_completion(
                variant_id=self.execution_context.variant_id,
                business_id=self.execution_context.business_id,
                stage=stage.value,
                duration_seconds=(
                    result.duration_seconds
                    if hasattr(result, "duration_seconds")
                    else None
                ),
                cost_cents=result.cost_cents if hasattr(result, "cost_cents") else None,
                session_id=self.execution_context.session_id,
                properties=properties,
            )

            logger.info(
                f"Completed stage {stage.value} for variant {self.variant.name}: {result.success}"
            )
            return result

        except Exception as e:
            # Track stage failure
            self.tracker.track_event(
                variant_id=self.execution_context.variant_id,
                business_id=self.execution_context.business_id,
                event_type=EventType.STAGE_FAILED,
                stage=stage.value,
                session_id=self.execution_context.session_id,
                properties={"error": str(e), "stage_config": stage_config},
            )

            logger.error(
                f"Stage {stage.value} failed for variant {self.variant.name}: {e}"
            )
            raise

    def execute_pipeline(
        self,
        target_stages: Optional[Set[PipelineStage]] = None,
        node_type: Optional[NodeType] = None,
        budget_cents: Optional[float] = None,
    ) -> Dict[PipelineStage, StageResult]:
        """Execute the full pipeline with variant tracking."""

        try:
            # Get execution plan
            execution_plan = self.dag.get_execution_plan(
                target_stages, node_type, budget_cents
            )

            logger.info(
                f"Executing pipeline for variant {self.variant.name} with {len(execution_plan)} stages"
            )

            results = {}

            for stage in execution_plan:
                if self.can_execute_stage(stage):
                    result = self.execute_stage(stage)
                    results[stage] = result
                    self.mark_stage_completed(stage, result)

                    if not result.success and not result.skipped:
                        logger.error(f"Pipeline failed at stage {stage.value}")
                        break
                else:
                    logger.warning(
                        f"Cannot execute stage {stage.value} - dependencies not met"
                    )

            # Track pipeline completion
            success = all(r.success for r in results.values())

            if success:
                self.tracker.track_event(
                    variant_id=self.execution_context.variant_id,
                    business_id=self.execution_context.business_id,
                    event_type=EventType.PIPELINE_COMPLETED,
                    session_id=self.execution_context.session_id,
                    properties={
                        "completed_stages": [s.value for s in results.keys()],
                        "total_stages": len(execution_plan),
                    },
                )
                logger.info(
                    f"Pipeline completed successfully for variant {self.variant.name}"
                )
            else:
                self.tracker.track_event(
                    variant_id=self.execution_context.variant_id,
                    business_id=self.execution_context.business_id,
                    event_type=EventType.PIPELINE_FAILED,
                    session_id=self.execution_context.session_id,
                    properties={
                        "failed_stages": [
                            s.value for s, r in results.items() if not r.success
                        ],
                        "completed_stages": [
                            s.value for s, r in results.items() if r.success
                        ],
                    },
                )
                logger.error(f"Pipeline failed for variant {self.variant.name}")

            return results

        except Exception as e:
            # Track pipeline failure
            self.tracker.track_event(
                variant_id=self.execution_context.variant_id,
                business_id=self.execution_context.business_id,
                event_type=EventType.PIPELINE_FAILED,
                session_id=self.execution_context.session_id,
                properties={
                    "error": str(e),
                    "execution_context": self.execution_context.metadata,
                },
            )

            logger.error(
                f"Pipeline execution failed for variant {self.variant.name}: {e}"
            )
            raise


class VariantPipelineManager:
    """Manages variant-aware pipeline execution."""

    def __init__(self):
        self.selection_manager = get_selection_manager()
        self.registry = get_variant_registry()
        self.tracker = get_variant_tracker()

    def execute_pipeline_for_business(
        self,
        business_id: int,
        target_stages: Optional[Set[PipelineStage]] = None,
        node_type: Optional[NodeType] = None,
        budget_cents: Optional[float] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[PipelineStage, StageResult]:
        """Execute pipeline for a business with automatic variant selection."""

        # Select variant for this business
        selection_context = SelectionContext(
            business_id=business_id,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
        )

        selection_result = self.selection_manager.select_variant(selection_context)

        if not selection_result:
            raise RuntimeError("Failed to select variant for pipeline execution")

        # Track variant assignment
        track_variant_assignment(
            variant_id=selection_result.variant_id,
            business_id=business_id,
            session_id=session_id,
            user_id=user_id,
            properties={
                "selection_reason": selection_result.selection_reason,
                "confidence": selection_result.confidence,
                **selection_result.metadata,
            },
        )

        # Create execution context
        execution_context = VariantExecutionContext(
            business_id=business_id,
            variant_id=selection_result.variant_id,
            variant_name=selection_result.variant_name,
            session_id=session_id or str(uuid4()),
            user_id=user_id,
            metadata=metadata or {},
        )

        # Execute pipeline with variant
        executor = VariantAwareExecutor(execution_context)
        return executor.execute_pipeline(target_stages, node_type, budget_cents)

    def execute_pipeline_with_variant(
        self,
        business_id: int,
        variant_id: str,
        target_stages: Optional[Set[PipelineStage]] = None,
        node_type: Optional[NodeType] = None,
        budget_cents: Optional[float] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[PipelineStage, StageResult]:
        """Execute pipeline for a business with a specific variant."""

        # Get variant
        variant = self.registry.get_variant(variant_id)
        if not variant:
            raise ValueError(f"Variant {variant_id} not found")

        # Track variant assignment
        track_variant_assignment(
            variant_id=variant_id,
            business_id=business_id,
            session_id=session_id,
            user_id=user_id,
            properties={
                "selection_reason": "manual_assignment",
                "confidence": 1.0,
                "variant_name": variant.name,
            },
        )

        # Create execution context
        execution_context = VariantExecutionContext(
            business_id=business_id,
            variant_id=variant_id,
            variant_name=variant.name,
            session_id=session_id or str(uuid4()),
            user_id=user_id,
            metadata=metadata or {},
        )

        # Execute pipeline with variant
        executor = VariantAwareExecutor(execution_context)
        return executor.execute_pipeline(target_stages, node_type, budget_cents)

    def get_variant_for_business(
        self, business_id: int, **kwargs
    ) -> Optional[SelectionResult]:
        """Get the variant that would be selected for a business."""
        selection_context = SelectionContext(business_id=business_id, **kwargs)
        return self.selection_manager.select_variant(selection_context)


# Global pipeline manager instance
_global_pipeline_manager = VariantPipelineManager()


def get_variant_pipeline_manager() -> VariantPipelineManager:
    """Get the global variant pipeline manager."""
    return _global_pipeline_manager


def execute_variant_pipeline(
    business_id: int, **kwargs
) -> Dict[PipelineStage, StageResult]:
    """Convenience function to execute pipeline with variant selection."""
    return get_variant_pipeline_manager().execute_pipeline_for_business(
        business_id, **kwargs
    )


def execute_pipeline_with_variant(
    business_id: int, variant_id: str, **kwargs
) -> Dict[PipelineStage, StageResult]:
    """Convenience function to execute pipeline with specific variant."""
    return get_variant_pipeline_manager().execute_pipeline_with_variant(
        business_id, variant_id, **kwargs
    )
