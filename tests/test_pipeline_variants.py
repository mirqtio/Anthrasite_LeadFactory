"""
Tests for pipeline variants module.
"""

import pytest
import json
from unittest.mock import Mock, patch

from leadfactory.pipeline.variants import (
    PipelineVariant, VariantStatus, StageConfiguration, VariantRegistry,
    create_default_variant, create_minimal_variant, get_variant_registry
)
from leadfactory.pipeline.dag_traversal import PipelineStage, StageDependency, DependencyType
from leadfactory.config.node_config import NodeType


class TestStageConfiguration:
    """Test StageConfiguration class."""

    def test_stage_configuration_creation(self):
        """Test creating a stage configuration."""
        config = StageConfiguration(
            stage=PipelineStage.SCRAPE,
            enabled=True,
            parameters={"param1": "value1"},
            node_type=NodeType.UNIFIED_GPT4O,
            cost_limit_cents=100.0,
            timeout_seconds=300,
            retry_attempts=3
        )

        assert config.stage == PipelineStage.SCRAPE
        assert config.enabled is True
        assert config.parameters == {"param1": "value1"}
        assert config.node_type == NodeType.UNIFIED_GPT4O
        assert config.cost_limit_cents == 100.0
        assert config.timeout_seconds == 300
        assert config.retry_attempts == 3

    def test_stage_configuration_defaults(self):
        """Test stage configuration with default values."""
        config = StageConfiguration(stage=PipelineStage.ENRICH)

        assert config.stage == PipelineStage.ENRICH
        assert config.enabled is True
        assert config.parameters == {}
        assert config.node_type is None
        assert config.cost_limit_cents is None
        assert config.timeout_seconds is None
        assert config.retry_attempts == 3

    def test_stage_configuration_serialization(self):
        """Test stage configuration serialization."""
        config = StageConfiguration(
            stage=PipelineStage.SCORE,
            enabled=False,
            parameters={"threshold": 0.8},
            node_type=NodeType.UNIFIED_GPT4O,
            cost_limit_cents=50.0
        )

        data = config.to_dict()
        expected = {
            "stage": "score",
            "enabled": False,
            "parameters": {"threshold": 0.8},
            "node_type": "unified_gpt4o",
            "cost_limit_cents": 50.0,
            "timeout_seconds": None,
            "retry_attempts": 3
        }

        assert data == expected

    def test_stage_configuration_deserialization(self):
        """Test stage configuration deserialization."""
        data = {
            "stage": "email_queue",
            "enabled": True,
            "parameters": {"batch_size": 100},
            "node_type": "unified_gpt4o",
            "cost_limit_cents": 200.0,
            "timeout_seconds": 600,
            "retry_attempts": 5
        }

        config = StageConfiguration.from_dict(data)

        assert config.stage == PipelineStage.EMAIL_QUEUE
        assert config.enabled is True
        assert config.parameters == {"batch_size": 100}
        assert config.node_type == NodeType.UNIFIED_GPT4O
        assert config.cost_limit_cents == 200.0
        assert config.timeout_seconds == 600
        assert config.retry_attempts == 5


class TestPipelineVariant:
    """Test PipelineVariant class."""

    def test_variant_creation(self):
        """Test creating a pipeline variant."""
        variant = PipelineVariant(
            name="test_variant",
            description="Test variant for unit tests",
            status=VariantStatus.ACTIVE,
            weight=1.5,
            target_percentage=25.0
        )

        assert variant.name == "test_variant"
        assert variant.description == "Test variant for unit tests"
        assert variant.status == VariantStatus.ACTIVE
        assert variant.weight == 1.5
        assert variant.target_percentage == 25.0
        assert len(variant.id) > 0
        assert len(variant.stage_configurations) == len(PipelineStage)

    def test_variant_default_name(self):
        """Test variant with auto-generated name."""
        variant = PipelineVariant()
        assert variant.name.startswith("Variant-")
        assert len(variant.name) > 8

    def test_variant_stage_configuration(self):
        """Test variant stage configuration management."""
        variant = PipelineVariant(name="test")

        # Test getting stage config
        config = variant.get_stage_config(PipelineStage.SCRAPE)
        assert config.stage == PipelineStage.SCRAPE
        assert config.enabled is True

        # Test setting stage config
        new_config = StageConfiguration(
            stage=PipelineStage.SCRAPE,
            enabled=False,
            parameters={"custom": "value"}
        )
        variant.set_stage_config(PipelineStage.SCRAPE, new_config)

        retrieved_config = variant.get_stage_config(PipelineStage.SCRAPE)
        assert retrieved_config.enabled is False
        assert retrieved_config.parameters == {"custom": "value"}

    def test_variant_enable_disable_stages(self):
        """Test enabling and disabling stages."""
        variant = PipelineVariant(name="test")

        # Test disabling a stage
        variant.disable_stage(PipelineStage.DEDUPE)
        config = variant.get_stage_config(PipelineStage.DEDUPE)
        assert config.enabled is False

        # Test enabling a stage with parameters
        variant.enable_stage(PipelineStage.DEDUPE, {"param": "value"})
        config = variant.get_stage_config(PipelineStage.DEDUPE)
        assert config.enabled is True
        assert config.parameters["param"] == "value"

    def test_variant_enabled_stages(self):
        """Test getting enabled stages."""
        variant = PipelineVariant(name="test")

        # Initially all stages should be enabled
        enabled_stages = variant.get_enabled_stages()
        assert len(enabled_stages) == len(PipelineStage)

        # Disable some stages
        variant.disable_stage(PipelineStage.DEDUPE)
        variant.disable_stage(PipelineStage.SCORE)

        enabled_stages = variant.get_enabled_stages()
        assert PipelineStage.DEDUPE not in enabled_stages
        assert PipelineStage.SCORE not in enabled_stages
        assert PipelineStage.SCRAPE in enabled_stages

    def test_variant_create_dag(self):
        """Test creating DAG from variant."""
        variant = PipelineVariant(name="test")

        # Add custom dependency
        custom_dep = StageDependency(
            from_stage=PipelineStage.SCRAPE,
            to_stage=PipelineStage.EMAIL_QUEUE,
            dependency_type=DependencyType.REQUIRED
        )
        variant.custom_dependencies.append(custom_dep)

        dag = variant.create_dag()
        assert dag is not None
        # Note: More detailed DAG testing would require access to DAG internals

    def test_variant_validation(self):
        """Test variant validation."""
        variant = PipelineVariant(name="test")

        # Valid variant should have no errors
        errors = variant.validate()
        assert len(errors) == 0

        # Test invalid weight
        variant.weight = -1.0
        errors = variant.validate()
        assert any("Weight must be positive" in error for error in errors)

        # Test invalid target percentage
        variant.weight = 1.0
        variant.target_percentage = 150.0
        errors = variant.validate()
        assert any("Target percentage must be between 0 and 100" in error for error in errors)

        # Test no enabled stages
        variant.target_percentage = 50.0
        for stage in PipelineStage:
            variant.disable_stage(stage)
        errors = variant.validate()
        assert any("At least one stage must be enabled" in error for error in errors)

    def test_variant_serialization(self):
        """Test variant serialization."""
        variant = PipelineVariant(
            name="test_variant",
            description="Test description",
            status=VariantStatus.ACTIVE,
            weight=2.0,
            target_percentage=30.0
        )

        # Modify a stage configuration
        variant.enable_stage(PipelineStage.SCRAPE, {"param": "value"})

        # Add custom dependency
        custom_dep = StageDependency(
            from_stage=PipelineStage.SCRAPE,
            to_stage=PipelineStage.ENRICH,
            dependency_type=DependencyType.OPTIONAL
        )
        variant.custom_dependencies.append(custom_dep)

        data = variant.to_dict()

        assert data["name"] == "test_variant"
        assert data["description"] == "Test description"
        assert data["status"] == "active"
        assert data["weight"] == 2.0
        assert data["target_percentage"] == 30.0
        assert "stage_configurations" in data
        assert "custom_dependencies" in data
        assert len(data["custom_dependencies"]) == 1

    def test_variant_deserialization(self):
        """Test variant deserialization."""
        data = {
            "id": "test-id-123",
            "name": "test_variant",
            "description": "Test description",
            "status": "active",
            "stage_configurations": {
                "scrape": {
                    "stage": "scrape",
                    "enabled": True,
                    "parameters": {"param": "value"},
                    "node_type": None,
                    "cost_limit_cents": None,
                    "timeout_seconds": None,
                    "retry_attempts": 3
                }
            },
            "custom_dependencies": [
                {
                    "from_stage": "scrape",
                    "to_stage": "enrich",
                    "dependency_type": "optional",
                    "condition": None
                }
            ],
            "weight": 2.0,
            "target_percentage": 30.0,
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-02T00:00:00"
        }

        variant = PipelineVariant.from_dict(data)

        assert variant.id == "test-id-123"
        assert variant.name == "test_variant"
        assert variant.description == "Test description"
        assert variant.status == VariantStatus.ACTIVE
        assert variant.weight == 2.0
        assert variant.target_percentage == 30.0
        assert variant.created_at == "2023-01-01T00:00:00"
        assert variant.updated_at == "2023-01-02T00:00:00"
        assert len(variant.custom_dependencies) == 1
        assert variant.custom_dependencies[0].from_stage == PipelineStage.SCRAPE


class TestVariantRegistry:
    """Test VariantRegistry class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = VariantRegistry()

    def test_register_variant(self):
        """Test registering a variant."""
        variant = PipelineVariant(name="test_variant", status=VariantStatus.ACTIVE)

        success = self.registry.register_variant(variant)
        assert success is True

        retrieved = self.registry.get_variant(variant.id)
        assert retrieved is not None
        assert retrieved.name == "test_variant"

    def test_register_invalid_variant(self):
        """Test registering an invalid variant."""
        variant = PipelineVariant(name="invalid", weight=-1.0)  # Invalid weight

        success = self.registry.register_variant(variant)
        assert success is False

    def test_get_variant_by_name(self):
        """Test getting variant by name."""
        variant = PipelineVariant(name="unique_name")
        self.registry.register_variant(variant)

        retrieved = self.registry.get_variant_by_name("unique_name")
        assert retrieved is not None
        assert retrieved.id == variant.id

        not_found = self.registry.get_variant_by_name("nonexistent")
        assert not_found is None

    def test_list_variants(self):
        """Test listing variants."""
        variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE)
        variant2 = PipelineVariant(name="variant2", status=VariantStatus.DRAFT)
        variant3 = PipelineVariant(name="variant3", status=VariantStatus.ACTIVE)

        self.registry.register_variant(variant1)
        self.registry.register_variant(variant2)
        self.registry.register_variant(variant3)

        # Test listing all variants
        all_variants = self.registry.list_variants()
        assert len(all_variants) == 3

        # Test listing by status
        active_variants = self.registry.list_variants(VariantStatus.ACTIVE)
        assert len(active_variants) == 2

        draft_variants = self.registry.list_variants(VariantStatus.DRAFT)
        assert len(draft_variants) == 1

    def test_get_active_variants(self):
        """Test getting active variants."""
        variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE)
        variant2 = PipelineVariant(name="variant2", status=VariantStatus.DRAFT)

        self.registry.register_variant(variant1)
        self.registry.register_variant(variant2)

        active_variants = self.registry.get_active_variants()
        assert len(active_variants) == 1
        assert active_variants[0].name == "variant1"

    def test_activate_deactivate_variant(self):
        """Test activating and deactivating variants."""
        variant = PipelineVariant(name="test", status=VariantStatus.DRAFT)
        self.registry.register_variant(variant)

        # Test activation
        success = self.registry.activate_variant(variant.id)
        assert success is True
        assert variant.status == VariantStatus.ACTIVE

        active_variants = self.registry.get_active_variants()
        assert len(active_variants) == 1

        # Test deactivation
        success = self.registry.deactivate_variant(variant.id)
        assert success is True
        assert variant.status == VariantStatus.PAUSED

        active_variants = self.registry.get_active_variants()
        assert len(active_variants) == 0

    def test_remove_variant(self):
        """Test removing a variant."""
        variant = PipelineVariant(name="test")
        self.registry.register_variant(variant)

        # Verify it exists
        assert self.registry.get_variant(variant.id) is not None

        # Remove it
        success = self.registry.remove_variant(variant.id)
        assert success is True

        # Verify it's gone
        assert self.registry.get_variant(variant.id) is None

    def test_update_variant(self):
        """Test updating a variant."""
        variant = PipelineVariant(name="original", description="Original description")
        self.registry.register_variant(variant)

        # Modify the variant
        variant.name = "updated"
        variant.description = "Updated description"

        success = self.registry.update_variant(variant)
        assert success is True

        # Verify the update
        retrieved = self.registry.get_variant(variant.id)
        assert retrieved.name == "updated"
        assert retrieved.description == "Updated description"

    def test_export_import_variants(self):
        """Test exporting and importing variants."""
        variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE)
        variant2 = PipelineVariant(name="variant2", status=VariantStatus.DRAFT)

        self.registry.register_variant(variant1)
        self.registry.register_variant(variant2)

        # Export
        export_data = self.registry.export_variants()
        assert "variants" in export_data
        assert "active_variants" in export_data
        assert len(export_data["variants"]) == 2
        assert len(export_data["active_variants"]) == 1

        # Clear and import
        self.registry.clear()
        assert len(self.registry.list_variants()) == 0

        success = self.registry.import_variants(export_data)
        assert success is True

        # Verify import
        imported_variants = self.registry.list_variants()
        assert len(imported_variants) == 2

        active_variants = self.registry.get_active_variants()
        assert len(active_variants) == 1


class TestVariantFactoryFunctions:
    """Test variant factory functions."""

    def test_create_default_variant(self):
        """Test creating default variant."""
        variant = create_default_variant("my_default")

        assert variant.name == "my_default"
        assert variant.status == VariantStatus.ACTIVE
        assert len(variant.get_enabled_stages()) == len(PipelineStage)

    def test_create_minimal_variant(self):
        """Test creating minimal variant."""
        variant = create_minimal_variant("my_minimal")

        assert variant.name == "my_minimal"
        enabled_stages = variant.get_enabled_stages()

        # Should have only essential stages
        essential_stages = {
            PipelineStage.SCRAPE,
            PipelineStage.ENRICH,
            PipelineStage.SCORE,
            PipelineStage.EMAIL_QUEUE
        }

        assert enabled_stages == essential_stages

    def test_get_variant_registry(self):
        """Test getting global variant registry."""
        registry1 = get_variant_registry()
        registry2 = get_variant_registry()

        # Should return the same instance
        assert registry1 is registry2


class TestVariantRegistryIntegration:
    """Integration tests for variant registry."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use a fresh registry for each test
        self.registry = VariantRegistry()

    def test_full_variant_lifecycle(self):
        """Test complete variant lifecycle."""
        # Create variant
        variant = PipelineVariant(
            name="lifecycle_test",
            description="Testing full lifecycle",
            status=VariantStatus.DRAFT,
            weight=1.5,
            target_percentage=25.0
        )

        # Customize some stages
        variant.disable_stage(PipelineStage.DEDUPE)
        variant.enable_stage(PipelineStage.SCRAPE, {"custom_param": "value"})

        # Register
        success = self.registry.register_variant(variant)
        assert success is True

        # Activate
        success = self.registry.activate_variant(variant.id)
        assert success is True

        # Verify active
        active_variants = self.registry.get_active_variants()
        assert len(active_variants) == 1
        assert active_variants[0].id == variant.id

        # Update
        variant.description = "Updated description"
        success = self.registry.update_variant(variant)
        assert success is True

        # Verify update
        retrieved = self.registry.get_variant(variant.id)
        assert retrieved.description == "Updated description"

        # Export/Import cycle
        export_data = self.registry.export_variants()
        self.registry.clear()
        success = self.registry.import_variants(export_data)
        assert success is True

        # Verify after import
        imported_variant = self.registry.get_variant(variant.id)
        assert imported_variant is not None
        assert imported_variant.name == "lifecycle_test"
        assert imported_variant.description == "Updated description"

        # Clean up
        success = self.registry.remove_variant(variant.id)
        assert success is True
        assert self.registry.get_variant(variant.id) is None
