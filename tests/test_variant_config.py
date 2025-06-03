"""
Tests for variant configuration module.
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch

from leadfactory.pipeline.variant_config import (
    VariantConfig, VariantConfigManager, VariantAdminInterface,
    get_variant_config_manager, get_variant_admin_interface
)
from leadfactory.pipeline.variant_selector import DistributionStrategy
from leadfactory.pipeline.variants import PipelineVariant, VariantStatus, VariantRegistry


class TestVariantConfig:
    """Test VariantConfig class."""

    def test_variant_config_creation(self):
        """Test creating variant configuration."""
        config = VariantConfig(
            enabled=True,
            default_strategy=DistributionStrategy.WEIGHTED,
            tracking_enabled=True,
            config_file_path="custom_variants.json",
            auto_save=False
        )

        assert config.enabled is True
        assert config.default_strategy == DistributionStrategy.WEIGHTED
        assert config.tracking_enabled is True
        assert config.config_file_path == "custom_variants.json"
        assert config.auto_save is False

    def test_variant_config_defaults(self):
        """Test variant configuration with defaults."""
        config = VariantConfig()

        assert config.enabled is True
        assert config.default_strategy == DistributionStrategy.EQUAL
        assert config.tracking_enabled is True
        assert config.config_file_path == "variants.json"
        assert config.auto_save is True
        assert config.backup_enabled is True
        assert config.backup_retention_days == 30

    def test_variant_config_serialization(self):
        """Test variant configuration serialization."""
        config = VariantConfig(
            enabled=False,
            default_strategy=DistributionStrategy.PERCENTAGE,
            tracking_db_path="/custom/path/tracking.db"
        )

        data = config.to_dict()

        assert data["enabled"] is False
        assert data["default_strategy"] == "percentage"
        assert data["tracking_db_path"] == "/custom/path/tracking.db"

    def test_variant_config_deserialization(self):
        """Test variant configuration deserialization."""
        data = {
            "enabled": False,
            "default_strategy": "hash_based",
            "tracking_enabled": False,
            "config_file_path": "test_variants.json",
            "auto_save": False,
            "backup_retention_days": 60
        }

        config = VariantConfig.from_dict(data)

        assert config.enabled is False
        assert config.default_strategy == DistributionStrategy.HASH_BASED
        assert config.tracking_enabled is False
        assert config.config_file_path == "test_variants.json"
        assert config.auto_save is False
        assert config.backup_retention_days == 60


class TestVariantConfigManager:
    """Test VariantConfigManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = VariantConfigManager(config_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_config_manager_creation(self):
        """Test creating configuration manager."""
        assert self.config_manager.config_dir == Path(self.temp_dir)
        assert isinstance(self.config_manager.config, VariantConfig)
        assert self.config_manager.config_dir.exists()

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        # Modify configuration
        self.config_manager.config.enabled = False
        self.config_manager.config.default_strategy = DistributionStrategy.WEIGHTED
        self.config_manager.config.backup_retention_days = 45

        # Save configuration
        success = self.config_manager.save_config()
        assert success is True

        # Create new manager to test loading
        new_manager = VariantConfigManager(config_dir=self.temp_dir)

        assert new_manager.config.enabled is False
        assert new_manager.config.default_strategy == DistributionStrategy.WEIGHTED
        assert new_manager.config.backup_retention_days == 45

    def test_initialize_default_variants(self):
        """Test initializing default variants."""
        success = self.config_manager.initialize_default_variants()
        assert success is True

        # Verify variants were created
        variants = self.config_manager.registry.list_variants()
        assert len(variants) == 2

        variant_names = [v.name for v in variants]
        assert "default" in variant_names
        assert "minimal" in variant_names

        # Verify variants are active
        active_variants = self.config_manager.registry.get_active_variants()
        assert len(active_variants) == 2

    def test_save_and_load_variants(self):
        """Test saving and loading variants."""
        # Initialize with default variants
        self.config_manager.initialize_default_variants()

        # Save variants
        success = self.config_manager.save_variants()
        assert success is True

        # Verify file was created
        variants_file = self.config_manager.config_dir / self.config_manager.config.config_file_path
        assert variants_file.exists()

        # Clear registry and reload
        self.config_manager.registry.clear()
        assert len(self.config_manager.registry.list_variants()) == 0

        success = self.config_manager.load_variants()
        assert success is True

        # Verify variants were loaded
        variants = self.config_manager.registry.list_variants()
        assert len(variants) == 2

    def test_backup_creation(self):
        """Test backup creation."""
        # Initialize variants and save
        self.config_manager.initialize_default_variants()
        self.config_manager.save_variants()

        # Modify and save again (should create backup)
        variant = self.config_manager.registry.list_variants()[0]
        variant.description = "Modified description"
        self.config_manager.registry.update_variant(variant)

        success = self.config_manager.save_variants(create_backup=True)
        assert success is True

        # Verify backup was created
        backup_dir = self.config_manager.config_dir / "backups"
        assert backup_dir.exists()

        backup_files = list(backup_dir.glob("*.json"))
        assert len(backup_files) >= 1

    def test_get_system_status(self):
        """Test getting system status."""
        self.config_manager.initialize_default_variants()

        status = self.config_manager.get_system_status()

        assert "config" in status
        assert "total_variants" in status
        assert "active_variants" in status
        assert "variant_summary" in status
        assert "tracking_enabled" in status
        assert "last_updated" in status

        assert status["total_variants"] == 2
        assert status["active_variants"] == 2
        assert len(status["variant_summary"]) == 2

    def test_validate_system(self):
        """Test system validation."""
        # Test with no variants
        issues = self.config_manager.validate_system()
        assert "No active variants found" in issues

        # Initialize variants
        self.config_manager.initialize_default_variants()

        # Test with valid system
        issues = self.config_manager.validate_system()
        assert len(issues) == 0

        # Test with invalid variant
        variant = self.config_manager.registry.list_variants()[0]
        variant.weight = -1.0  # Invalid weight

        issues = self.config_manager.validate_system()
        assert any("Weight must be positive" in issue for issue in issues)

    def test_export_import_configuration(self):
        """Test exporting and importing complete configuration."""
        # Set up test data
        self.config_manager.config.enabled = False
        self.config_manager.initialize_default_variants()

        export_file = os.path.join(self.temp_dir, "export.json")

        # Export configuration
        success = self.config_manager.export_configuration(export_file)
        assert success is True
        assert os.path.exists(export_file)

        # Verify export content
        with open(export_file, 'r') as f:
            export_data = json.load(f)

        assert "system_config" in export_data
        assert "variants" in export_data
        assert "system_status" in export_data
        assert export_data["system_config"]["enabled"] is False

        # Create new manager and import
        new_manager = VariantConfigManager(config_dir=tempfile.mkdtemp())

        success = new_manager.import_configuration(export_file)
        assert success is True

        # Verify import
        assert new_manager.config.enabled is False
        variants = new_manager.registry.list_variants()
        assert len(variants) == 2


class TestVariantAdminInterface:
    """Test VariantAdminInterface class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = VariantConfigManager(config_dir=self.temp_dir)
        self.admin = VariantAdminInterface(self.config_manager)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_create_variant(self):
        """Test creating a variant through admin interface."""
        variant_id = self.admin.create_variant(
            name="test_variant",
            description="Test variant for admin interface",
            weight=2.0,
            target_percentage=30.0
        )

        assert variant_id is not None

        # Verify variant was created
        variant = self.admin.registry.get_variant(variant_id)
        assert variant is not None
        assert variant.name == "test_variant"
        assert variant.description == "Test variant for admin interface"
        assert variant.weight == 2.0
        assert variant.target_percentage == 30.0
        assert variant.status == VariantStatus.DRAFT

    def test_update_variant(self):
        """Test updating a variant."""
        # Create variant
        variant_id = self.admin.create_variant(name="update_test")

        # Update variant
        success = self.admin.update_variant(
            variant_id,
            description="Updated description",
            weight=3.0,
            target_percentage=40.0
        )

        assert success is True

        # Verify update
        variant = self.admin.registry.get_variant(variant_id)
        assert variant.description == "Updated description"
        assert variant.weight == 3.0
        assert variant.target_percentage == 40.0

    def test_activate_deactivate_variant(self):
        """Test activating and deactivating variants."""
        # Create variant (starts as DRAFT)
        variant_id = self.admin.create_variant(name="activation_test")

        # Activate variant
        success = self.admin.activate_variant(variant_id)
        assert success is True

        variant = self.admin.registry.get_variant(variant_id)
        assert variant.status == VariantStatus.ACTIVE

        # Deactivate variant
        success = self.admin.deactivate_variant(variant_id)
        assert success is True

        variant = self.admin.registry.get_variant(variant_id)
        assert variant.status == VariantStatus.PAUSED

    def test_delete_variant(self):
        """Test deleting a variant."""
        # Create variant
        variant_id = self.admin.create_variant(name="delete_test")

        # Verify it exists
        assert self.admin.registry.get_variant(variant_id) is not None

        # Delete variant
        success = self.admin.delete_variant(variant_id)
        assert success is True

        # Verify it's gone
        assert self.admin.registry.get_variant(variant_id) is None

    def test_list_variants(self):
        """Test listing variants."""
        # Create test variants
        variant1_id = self.admin.create_variant(name="list_test_1")
        variant2_id = self.admin.create_variant(name="list_test_2")

        # Activate one variant
        self.admin.activate_variant(variant1_id)

        # List all variants
        all_variants = self.admin.list_variants()
        assert len(all_variants) == 2

        # List by status
        draft_variants = self.admin.list_variants(VariantStatus.DRAFT)
        assert len(draft_variants) == 1
        assert draft_variants[0]["name"] == "list_test_2"

        active_variants = self.admin.list_variants(VariantStatus.ACTIVE)
        assert len(active_variants) == 1
        assert active_variants[0]["name"] == "list_test_1"

    @patch('leadfactory.pipeline.variant_config.VariantTracker')
    def test_get_variant_metrics(self, mock_tracker_class):
        """Test getting variant metrics."""
        # Mock tracker and metrics
        mock_tracker = Mock()
        mock_metrics = Mock()
        mock_metrics.to_dict.return_value = {"conversions": 10, "success_rate": 0.8}
        mock_tracker.get_variant_metrics.return_value = mock_metrics

        # Patch the admin's tracker
        self.admin.tracker = mock_tracker

        # Create variant
        variant_id = self.admin.create_variant(name="metrics_test")

        # Get metrics
        metrics = self.admin.get_variant_metrics(variant_id)

        assert metrics is not None
        assert metrics["conversions"] == 10
        assert metrics["success_rate"] == 0.8

        mock_tracker.get_variant_metrics.assert_called_once_with(variant_id)

    def test_get_system_health(self):
        """Test getting system health."""
        # Test unhealthy system (no variants)
        health = self.admin.get_system_health()

        assert health["healthy"] is False
        assert len(health["issues"]) > 0
        assert "No active variants found" in health["issues"]
        assert len(health["recommendations"]) > 0

        # Create and activate variants
        variant1_id = self.admin.create_variant(name="health_test_1")
        variant2_id = self.admin.create_variant(name="health_test_2")
        self.admin.activate_variant(variant1_id)
        self.admin.activate_variant(variant2_id)

        # Test healthy system
        health = self.admin.get_system_health()

        assert health["healthy"] is True
        assert len(health["issues"]) == 0


class TestGlobalInstances:
    """Test global instance functions."""

    def test_get_variant_config_manager(self):
        """Test getting global config manager."""
        manager1 = get_variant_config_manager()
        manager2 = get_variant_config_manager()

        # Should return the same instance
        assert manager1 is manager2
        assert isinstance(manager1, VariantConfigManager)

    def test_get_variant_admin_interface(self):
        """Test getting global admin interface."""
        admin1 = get_variant_admin_interface()
        admin2 = get_variant_admin_interface()

        # Should return the same instance
        assert admin1 is admin2
        assert isinstance(admin1, VariantAdminInterface)


class TestVariantConfigIntegration:
    """Integration tests for variant configuration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_full_configuration_workflow(self):
        """Test complete configuration workflow."""
        # Create config manager
        config_manager = VariantConfigManager(config_dir=self.temp_dir)
        admin = VariantAdminInterface(config_manager)

        # Configure system
        config_manager.config.enabled = True
        config_manager.config.default_strategy = DistributionStrategy.WEIGHTED
        config_manager.config.auto_save = True

        # Initialize with default variants
        success = config_manager.initialize_default_variants()
        assert success is True

        # Create custom variant through admin
        custom_variant_id = admin.create_variant(
            name="custom_variant",
            description="Custom variant for testing",
            weight=1.5,
            target_percentage=25.0
        )

        # Activate custom variant
        admin.activate_variant(custom_variant_id)

        # Verify system status
        status = config_manager.get_system_status()
        assert status["total_variants"] == 3
        assert status["active_variants"] == 3

        # Validate system
        issues = config_manager.validate_system()
        assert len(issues) == 0

        # Export configuration
        export_file = os.path.join(self.temp_dir, "full_config.json")
        success = config_manager.export_configuration(export_file)
        assert success is True

        # Create new environment and import
        new_temp_dir = tempfile.mkdtemp()
        try:
            new_config_manager = VariantConfigManager(config_dir=new_temp_dir)
            new_admin = VariantAdminInterface(new_config_manager)

            success = new_config_manager.import_configuration(export_file)
            assert success is True

            # Verify import
            new_status = new_config_manager.get_system_status()
            assert new_status["total_variants"] == 3
            assert new_status["active_variants"] == 3

            # Verify custom variant was imported
            variants = new_admin.list_variants()
            custom_variants = [v for v in variants if v["name"] == "custom_variant"]
            assert len(custom_variants) == 1
            assert custom_variants[0]["weight"] == 1.5

        finally:
            import shutil
            shutil.rmtree(new_temp_dir)

    def test_configuration_persistence(self):
        """Test configuration persistence across restarts."""
        # Create and configure system
        config_manager = VariantConfigManager(config_dir=self.temp_dir)
        admin = VariantAdminInterface(config_manager)

        # Modify configuration
        config_manager.config.enabled = False
        config_manager.config.backup_retention_days = 60
        config_manager.save_config()

        # Create variants
        variant_id = admin.create_variant(
            name="persistent_variant",
            description="Test persistence",
            weight=2.5
        )
        admin.activate_variant(variant_id)

        # Save variants
        config_manager.save_variants()

        # Simulate restart by creating new manager
        new_config_manager = VariantConfigManager(config_dir=self.temp_dir)
        new_admin = VariantAdminInterface(new_config_manager)

        # Verify configuration persisted
        assert new_config_manager.config.enabled is False
        assert new_config_manager.config.backup_retention_days == 60

        # Verify variants persisted
        variants = new_admin.list_variants()
        persistent_variants = [v for v in variants if v["name"] == "persistent_variant"]
        assert len(persistent_variants) == 1
        assert persistent_variants[0]["weight"] == 2.5
        assert persistent_variants[0]["status"] == "active"
