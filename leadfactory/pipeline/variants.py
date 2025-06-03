"""
Pipeline Variant System for A/B Testing.

This module provides functionality for defining, managing, and executing
different pipeline variants for A/B testing purposes.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from uuid import uuid4

from leadfactory.config.node_config import NodeType
from leadfactory.pipeline.dag_traversal import (
    DependencyType,
    PipelineDAG,
    PipelineStage,
    StageDependency,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class VariantStatus(Enum):
    """Status of a pipeline variant."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class StageConfiguration:
    """Configuration for a specific pipeline stage in a variant."""

    stage: PipelineStage
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    node_type: Optional[NodeType] = None
    cost_limit_cents: Optional[float] = None
    timeout_seconds: Optional[int] = None
    retry_attempts: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "stage": self.stage.value,
            "enabled": self.enabled,
            "parameters": self.parameters,
            "node_type": self.node_type.value if self.node_type else None,
            "cost_limit_cents": self.cost_limit_cents,
            "timeout_seconds": self.timeout_seconds,
            "retry_attempts": self.retry_attempts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StageConfiguration":
        """Create from dictionary for deserialization."""
        return cls(
            stage=PipelineStage(data["stage"]),
            enabled=data.get("enabled", True),
            parameters=data.get("parameters", {}),
            node_type=NodeType(data["node_type"]) if data.get("node_type") else None,
            cost_limit_cents=data.get("cost_limit_cents"),
            timeout_seconds=data.get("timeout_seconds"),
            retry_attempts=data.get("retry_attempts", 3),
        )


@dataclass
class PipelineVariant:
    """Defines a pipeline variant for A/B testing."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    status: VariantStatus = VariantStatus.DRAFT
    stage_configurations: Dict[PipelineStage, StageConfiguration] = field(
        default_factory=dict
    )
    custom_dependencies: List[StageDependency] = field(default_factory=list)
    weight: float = 1.0  # For weighted distribution
    target_percentage: Optional[float] = None  # For percentage-based distribution
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        """Initialize default configurations if not provided."""
        if not self.stage_configurations:
            self._setup_default_configurations()
        if not self.name:
            self.name = f"Variant-{self.id[:8]}"

    def _setup_default_configurations(self):
        """Set up default stage configurations for all pipeline stages."""
        for stage in PipelineStage:
            self.stage_configurations[stage] = StageConfiguration(stage=stage)

    def get_stage_config(self, stage: PipelineStage) -> StageConfiguration:
        """Get configuration for a specific stage."""
        if stage not in self.stage_configurations:
            self.stage_configurations[stage] = StageConfiguration(stage=stage)
        return self.stage_configurations[stage]

    def set_stage_config(self, stage: PipelineStage, config: StageConfiguration):
        """Set configuration for a specific stage."""
        self.stage_configurations[stage] = config

    def enable_stage(
        self, stage: PipelineStage, parameters: Optional[Dict[str, Any]] = None
    ):
        """Enable a stage with optional parameters."""
        config = self.get_stage_config(stage)
        config.enabled = True
        if parameters:
            config.parameters.update(parameters)

    def disable_stage(self, stage: PipelineStage):
        """Disable a stage."""
        config = self.get_stage_config(stage)
        config.enabled = False

    def get_enabled_stages(self) -> Set[PipelineStage]:
        """Get all enabled stages in this variant."""
        return {
            stage
            for stage, config in self.stage_configurations.items()
            if config.enabled
        }

    def create_dag(self) -> PipelineDAG:
        """Create a DAG instance configured for this variant."""
        dag = PipelineDAG()

        # Add custom dependencies if any
        for dependency in self.custom_dependencies:
            dag.add_dependency(dependency)

        return dag

    def validate(self) -> List[str]:
        """Validate the variant configuration."""
        errors = []

        # Check if at least one stage is enabled
        enabled_stages = self.get_enabled_stages()
        if not enabled_stages:
            errors.append("At least one stage must be enabled")

        # Validate weight
        if self.weight <= 0:
            errors.append("Weight must be positive")

        # Validate target percentage
        if self.target_percentage is not None:
            if not (0 < self.target_percentage <= 100):
                errors.append("Target percentage must be between 0 and 100")

        # Validate stage configurations
        for stage, config in self.stage_configurations.items():
            if config.cost_limit_cents is not None and config.cost_limit_cents < 0:
                errors.append(f"Cost limit for {stage.value} must be non-negative")

            if config.timeout_seconds is not None and config.timeout_seconds <= 0:
                errors.append(f"Timeout for {stage.value} must be positive")

            if config.retry_attempts < 0:
                errors.append(f"Retry attempts for {stage.value} must be non-negative")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "stage_configurations": {
                stage.value: config.to_dict()
                for stage, config in self.stage_configurations.items()
            },
            "custom_dependencies": [
                {
                    "from_stage": dep.from_stage.value,
                    "to_stage": dep.to_stage.value,
                    "dependency_type": dep.dependency_type.value,
                    "condition": dep.condition,
                }
                for dep in self.custom_dependencies
            ],
            "weight": self.weight,
            "target_percentage": self.target_percentage,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineVariant":
        """Create from dictionary for deserialization."""
        variant = cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            status=VariantStatus(data["status"]),
            weight=data.get("weight", 1.0),
            target_percentage=data.get("target_percentage"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

        # Load stage configurations
        stage_configs = data.get("stage_configurations", {})
        for stage_name, config_data in stage_configs.items():
            stage = PipelineStage(stage_name)
            variant.stage_configurations[stage] = StageConfiguration.from_dict(
                config_data
            )

        # Load custom dependencies
        custom_deps = data.get("custom_dependencies", [])
        for dep_data in custom_deps:
            dependency = StageDependency(
                from_stage=PipelineStage(dep_data["from_stage"]),
                to_stage=PipelineStage(dep_data["to_stage"]),
                dependency_type=DependencyType(dep_data["dependency_type"]),
                condition=dep_data.get("condition"),
            )
            variant.custom_dependencies.append(dependency)

        return variant


class VariantRegistry:
    """Registry for managing pipeline variants."""

    def __init__(self):
        self._variants: Dict[str, PipelineVariant] = {}
        self._active_variants: Set[str] = set()

    def register_variant(self, variant: PipelineVariant) -> bool:
        """Register a new variant."""
        try:
            # Validate the variant
            errors = variant.validate()
            if errors:
                logger.error(f"Variant validation failed: {errors}")
                return False

            self._variants[variant.id] = variant

            if variant.status == VariantStatus.ACTIVE:
                self._active_variants.add(variant.id)

            logger.info(f"Registered variant: {variant.name} ({variant.id})")
            return True

        except Exception as e:
            logger.error(f"Failed to register variant {variant.name}: {e}")
            return False

    def get_variant(self, variant_id: str) -> Optional[PipelineVariant]:
        """Get a variant by ID."""
        return self._variants.get(variant_id)

    def get_variant_by_name(self, name: str) -> Optional[PipelineVariant]:
        """Get a variant by name."""
        for variant in self._variants.values():
            if variant.name == name:
                return variant
        return None

    def list_variants(
        self, status: Optional[VariantStatus] = None
    ) -> List[PipelineVariant]:
        """List all variants, optionally filtered by status."""
        variants = list(self._variants.values())
        if status:
            variants = [v for v in variants if v.status == status]
        return variants

    def get_active_variants(self) -> List[PipelineVariant]:
        """Get all active variants."""
        return [
            self._variants[vid]
            for vid in self._active_variants
            if vid in self._variants
        ]

    def activate_variant(self, variant_id: str) -> bool:
        """Activate a variant."""
        variant = self.get_variant(variant_id)
        if not variant:
            logger.error(f"Variant {variant_id} not found")
            return False

        variant.status = VariantStatus.ACTIVE
        self._active_variants.add(variant_id)
        logger.info(f"Activated variant: {variant.name}")
        return True

    def deactivate_variant(self, variant_id: str) -> bool:
        """Deactivate a variant."""
        variant = self.get_variant(variant_id)
        if not variant:
            logger.error(f"Variant {variant_id} not found")
            return False

        variant.status = VariantStatus.PAUSED
        self._active_variants.discard(variant_id)
        logger.info(f"Deactivated variant: {variant.name}")
        return True

    def remove_variant(self, variant_id: str) -> bool:
        """Remove a variant from the registry."""
        if variant_id not in self._variants:
            logger.error(f"Variant {variant_id} not found")
            return False

        variant = self._variants[variant_id]
        del self._variants[variant_id]
        self._active_variants.discard(variant_id)
        logger.info(f"Removed variant: {variant.name}")
        return True

    def update_variant(self, variant: PipelineVariant) -> bool:
        """Update an existing variant."""
        if variant.id not in self._variants:
            logger.error(f"Variant {variant.id} not found for update")
            return False

        # Validate the updated variant
        errors = variant.validate()
        if errors:
            logger.error(f"Variant validation failed: {errors}")
            return False

        self._variants[variant.id] = variant

        # Update active status
        if variant.status == VariantStatus.ACTIVE:
            self._active_variants.add(variant.id)
        else:
            self._active_variants.discard(variant.id)

        logger.info(f"Updated variant: {variant.name}")
        return True

    def clear(self):
        """Clear all variants from the registry."""
        self._variants.clear()
        self._active_variants.clear()

    def export_variants(self) -> Dict[str, Any]:
        """Export all variants to a dictionary."""
        return {
            "variants": [variant.to_dict() for variant in self._variants.values()],
            "active_variants": list(self._active_variants),
        }

    def import_variants(self, data: Dict[str, Any]) -> bool:
        """Import variants from a dictionary."""
        try:
            self.clear()

            for variant_data in data.get("variants", []):
                variant = PipelineVariant.from_dict(variant_data)
                self.register_variant(variant)

            # Restore active variants
            active_variants = data.get("active_variants", [])
            for variant_id in active_variants:
                if variant_id in self._variants:
                    self._active_variants.add(variant_id)

            logger.info(f"Imported {len(self._variants)} variants")
            return True

        except Exception as e:
            logger.error(f"Failed to import variants: {e}")
            return False


# Global registry instance
_global_registry = VariantRegistry()


def get_variant_registry() -> VariantRegistry:
    """Get the global variant registry."""
    return _global_registry


def create_default_variant(name: str = "default") -> PipelineVariant:
    """Create a default variant with all stages enabled."""
    variant = PipelineVariant(name=name, description="Default pipeline configuration")
    variant.status = VariantStatus.ACTIVE
    return variant


def create_minimal_variant(name: str = "minimal") -> PipelineVariant:
    """Create a minimal variant with only essential stages."""
    variant = PipelineVariant(name=name, description="Minimal pipeline configuration")

    # Enable only essential stages
    essential_stages = {
        PipelineStage.SCRAPE,
        PipelineStage.ENRICH,
        PipelineStage.SCORE,
        PipelineStage.EMAIL_QUEUE,
    }

    for stage in PipelineStage:
        if stage in essential_stages:
            variant.enable_stage(stage)
        else:
            variant.disable_stage(stage)

    return variant
