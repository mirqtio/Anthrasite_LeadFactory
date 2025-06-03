"""
Configuration and Management Interface for Pipeline Variants.

This module provides configuration management, persistence, and administrative
interfaces for the variant A/B testing system.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from leadfactory.pipeline.variant_selector import (
    DistributionStrategy,
    VariantSelectionManager,
    get_selection_manager,
)
from leadfactory.pipeline.variant_tracking import VariantTracker, get_variant_tracker
from leadfactory.pipeline.variants import (
    PipelineVariant,
    VariantRegistry,
    VariantStatus,
    create_default_variant,
    create_minimal_variant,
    get_variant_registry,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VariantConfig:
    """Configuration for the variant system."""

    enabled: bool = True
    default_strategy: DistributionStrategy = DistributionStrategy.EQUAL
    tracking_enabled: bool = True
    tracking_db_path: Optional[str] = None
    config_file_path: str = "variants.json"
    auto_save: bool = True
    backup_enabled: bool = True
    backup_retention_days: int = 30

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "enabled": self.enabled,
            "default_strategy": self.default_strategy.value,
            "tracking_enabled": self.tracking_enabled,
            "tracking_db_path": self.tracking_db_path,
            "config_file_path": self.config_file_path,
            "auto_save": self.auto_save,
            "backup_enabled": self.backup_enabled,
            "backup_retention_days": self.backup_retention_days,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VariantConfig":
        """Create from dictionary for deserialization."""
        return cls(
            enabled=data.get("enabled", True),
            default_strategy=DistributionStrategy(
                data.get("default_strategy", "equal")
            ),
            tracking_enabled=data.get("tracking_enabled", True),
            tracking_db_path=data.get("tracking_db_path"),
            config_file_path=data.get("config_file_path", "variants.json"),
            auto_save=data.get("auto_save", True),
            backup_enabled=data.get("backup_enabled", True),
            backup_retention_days=data.get("backup_retention_days", 30),
        )


class VariantConfigManager:
    """Manages variant system configuration and persistence."""

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(
            config_dir or os.path.expanduser("~/.leadfactory/variants")
        )
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.config = VariantConfig()
        self.registry = get_variant_registry()
        self.selection_manager = get_selection_manager()
        self.tracker = get_variant_tracker()

        self._load_config()

    def _load_config(self):
        """Load configuration from file."""
        config_file = self.config_dir / "config.json"

        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    config_data = json.load(f)
                self.config = VariantConfig.from_dict(config_data)
                logger.info("Loaded variant configuration")
            except Exception as e:
                logger.error(f"Failed to load variant configuration: {e}")
        else:
            logger.info("Using default variant configuration")

    def save_config(self) -> bool:
        """Save configuration to file."""
        try:
            config_file = self.config_dir / "config.json"
            with open(config_file, "w") as f:
                json.dump(self.config.to_dict(), f, indent=2)
            logger.info("Saved variant configuration")
            return True
        except Exception as e:
            logger.error(f"Failed to save variant configuration: {e}")
            return False

    def load_variants(self, file_path: Optional[str] = None) -> bool:
        """Load variants from file."""
        variants_file = Path(
            file_path or self.config_dir / self.config.config_file_path
        )

        if not variants_file.exists():
            logger.warning(f"Variants file not found: {variants_file}")
            return False

        try:
            with open(variants_file, "r") as f:
                data = json.load(f)

            success = self.registry.import_variants(data)
            if success:
                logger.info(f"Loaded variants from {variants_file}")
            return success

        except Exception as e:
            logger.error(f"Failed to load variants from {variants_file}: {e}")
            return False

    def save_variants(
        self, file_path: Optional[str] = None, create_backup: bool = None
    ) -> bool:
        """Save variants to file."""
        variants_file = Path(
            file_path or self.config_dir / self.config.config_file_path
        )

        # Create backup if enabled
        if create_backup is None:
            create_backup = self.config.backup_enabled

        if create_backup and variants_file.exists():
            self._create_backup(variants_file)

        try:
            # Export variants data
            data = self.registry.export_variants()
            data["exported_at"] = datetime.utcnow().isoformat()
            data["config"] = self.config.to_dict()

            # Write to file
            with open(variants_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved variants to {variants_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save variants to {variants_file}: {e}")
            return False

    def _create_backup(self, original_file: Path):
        """Create a backup of the variants file."""
        try:
            backup_dir = self.config_dir / "backups"
            backup_dir.mkdir(exist_ok=True)

            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"{original_file.stem}_{timestamp}.json"

            # Copy original to backup
            import shutil

            shutil.copy2(original_file, backup_file)

            logger.info(f"Created backup: {backup_file}")

            # Clean old backups
            self._cleanup_old_backups(backup_dir)

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")

    def _cleanup_old_backups(self, backup_dir: Path):
        """Clean up old backup files."""
        try:
            cutoff_date = datetime.utcnow().timestamp() - (
                self.config.backup_retention_days * 24 * 3600
            )

            for backup_file in backup_dir.glob("*.json"):
                if backup_file.stat().st_mtime < cutoff_date:
                    backup_file.unlink()
                    logger.debug(f"Removed old backup: {backup_file}")

        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")

    def initialize_default_variants(self) -> bool:
        """Initialize the system with default variants."""
        try:
            # Clear existing variants
            self.registry.clear()

            # Create default variant
            default_variant = create_default_variant("default")
            default_variant.description = (
                "Default pipeline configuration with all stages enabled"
            )
            default_variant.weight = 0.8
            default_variant.target_percentage = 80.0

            # Create minimal variant
            minimal_variant = create_minimal_variant("minimal")
            minimal_variant.description = (
                "Minimal pipeline configuration for cost optimization"
            )
            minimal_variant.weight = 0.2
            minimal_variant.target_percentage = 20.0

            # Register variants
            self.registry.register_variant(default_variant)
            self.registry.register_variant(minimal_variant)

            # Save to file if auto-save is enabled
            if self.config.auto_save:
                self.save_variants()

            logger.info("Initialized default variants")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize default variants: {e}")
            return False

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        variants = self.registry.list_variants()
        active_variants = self.registry.get_active_variants()

        return {
            "config": self.config.to_dict(),
            "total_variants": len(variants),
            "active_variants": len(active_variants),
            "variant_summary": [
                {
                    "id": v.id,
                    "name": v.name,
                    "status": v.status.value,
                    "weight": v.weight,
                    "target_percentage": v.target_percentage,
                    "enabled_stages": len(v.get_enabled_stages()),
                }
                for v in variants
            ],
            "tracking_enabled": self.config.tracking_enabled,
            "config_file": str(self.config_dir / self.config.config_file_path),
            "last_updated": datetime.utcnow().isoformat(),
        }

    def validate_system(self) -> List[str]:
        """Validate the variant system configuration."""
        issues = []

        # Check if system is enabled
        if not self.config.enabled:
            issues.append("Variant system is disabled")

        # Check for active variants
        active_variants = self.registry.get_active_variants()
        if not active_variants:
            issues.append("No active variants found")

        # Validate variant configurations
        for variant in active_variants:
            variant_issues = variant.validate()
            for issue in variant_issues:
                issues.append(f"Variant {variant.name}: {issue}")

        # Check weight/percentage consistency
        if len(active_variants) > 1:
            total_weight = sum(v.weight for v in active_variants)
            total_percentage = sum(
                v.target_percentage or 0 for v in active_variants if v.target_percentage
            )

            if total_percentage > 100:
                issues.append(
                    f"Total target percentages exceed 100%: {total_percentage}%"
                )

            if total_weight <= 0:
                issues.append("Total variant weights is zero or negative")

        # Check file permissions
        config_file = self.config_dir / self.config.config_file_path
        if config_file.exists() and not os.access(config_file, os.W_OK):
            issues.append(f"Cannot write to variants file: {config_file}")

        return issues

    def export_configuration(self, export_path: str) -> bool:
        """Export complete system configuration."""
        try:
            export_data = {
                "system_config": self.config.to_dict(),
                "variants": self.registry.export_variants(),
                "system_status": self.get_system_status(),
                "exported_at": datetime.utcnow().isoformat(),
                "version": "1.0",
            }

            with open(export_path, "w") as f:
                json.dump(export_data, f, indent=2)

            logger.info(f"Exported configuration to {export_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            return False

    def import_configuration(self, import_path: str) -> bool:
        """Import complete system configuration."""
        try:
            with open(import_path, "r") as f:
                data = json.load(f)

            # Import system config
            if "system_config" in data:
                self.config = VariantConfig.from_dict(data["system_config"])

            # Import variants
            if "variants" in data:
                success = self.registry.import_variants(data["variants"])
                if not success:
                    return False

            # Save configuration
            self.save_config()
            if self.config.auto_save:
                self.save_variants()

            logger.info(f"Imported configuration from {import_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            return False


class VariantAdminInterface:
    """Administrative interface for variant management."""

    def __init__(self, config_manager: Optional[VariantConfigManager] = None):
        self.config_manager = config_manager or VariantConfigManager()
        self.registry = get_variant_registry()
        self.tracker = get_variant_tracker()

    def create_variant(
        self,
        name: str,
        description: str = "",
        weight: float = 1.0,
        target_percentage: Optional[float] = None,
    ) -> Optional[str]:
        """Create a new variant."""
        try:
            variant = PipelineVariant(
                name=name,
                description=description,
                weight=weight,
                target_percentage=target_percentage,
                status=VariantStatus.DRAFT,
            )

            success = self.registry.register_variant(variant)
            if success:
                if self.config_manager.config.auto_save:
                    self.config_manager.save_variants()
                logger.info(f"Created variant: {name}")
                return variant.id

            return None

        except Exception as e:
            logger.error(f"Failed to create variant {name}: {e}")
            return None

    def update_variant(self, variant_id: str, **updates) -> bool:
        """Update an existing variant."""
        try:
            variant = self.registry.get_variant(variant_id)
            if not variant:
                logger.error(f"Variant {variant_id} not found")
                return False

            # Apply updates
            for key, value in updates.items():
                if hasattr(variant, key):
                    setattr(variant, key, value)

            variant.updated_at = datetime.utcnow().isoformat()

            success = self.registry.update_variant(variant)
            if success and self.config_manager.config.auto_save:
                self.config_manager.save_variants()

            return success

        except Exception as e:
            logger.error(f"Failed to update variant {variant_id}: {e}")
            return False

    def activate_variant(self, variant_id: str) -> bool:
        """Activate a variant."""
        success = self.registry.activate_variant(variant_id)
        if success and self.config_manager.config.auto_save:
            self.config_manager.save_variants()
        return success

    def deactivate_variant(self, variant_id: str) -> bool:
        """Deactivate a variant."""
        success = self.registry.deactivate_variant(variant_id)
        if success and self.config_manager.config.auto_save:
            self.config_manager.save_variants()
        return success

    def delete_variant(self, variant_id: str) -> bool:
        """Delete a variant."""
        success = self.registry.remove_variant(variant_id)
        if success and self.config_manager.config.auto_save:
            self.config_manager.save_variants()
        return success

    def get_variant_metrics(self, variant_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a variant."""
        try:
            metrics = self.tracker.get_variant_metrics(variant_id)
            return metrics.to_dict()
        except Exception as e:
            logger.error(f"Failed to get metrics for variant {variant_id}: {e}")
            return None

    def list_variants(
        self, status: Optional[VariantStatus] = None
    ) -> List[Dict[str, Any]]:
        """List variants with their basic information."""
        variants = self.registry.list_variants(status)
        return [
            {
                "id": v.id,
                "name": v.name,
                "description": v.description,
                "status": v.status.value,
                "weight": v.weight,
                "target_percentage": v.target_percentage,
                "enabled_stages": len(v.get_enabled_stages()),
                "created_at": v.created_at,
                "updated_at": v.updated_at,
            }
            for v in variants
        ]

    def get_system_health(self) -> Dict[str, Any]:
        """Get system health status."""
        issues = self.config_manager.validate_system()
        status = self.config_manager.get_system_status()

        return {
            "healthy": len(issues) == 0,
            "issues": issues,
            "status": status,
            "recommendations": self._get_health_recommendations(issues, status),
        }

    def _get_health_recommendations(
        self, issues: List[str], status: Dict[str, Any]
    ) -> List[str]:
        """Generate health recommendations."""
        recommendations = []

        if not status.get("active_variants", 0):
            recommendations.append(
                "Activate at least one variant to enable A/B testing"
            )

        if status.get("active_variants", 0) == 1:
            recommendations.append(
                "Consider adding more variants for meaningful A/B testing"
            )

        if "No active variants found" in issues:
            recommendations.append(
                "Initialize default variants or activate existing ones"
            )

        if any("exceed 100%" in issue for issue in issues):
            recommendations.append(
                "Adjust variant target percentages to total 100% or less"
            )

        return recommendations


# Global instances
_global_config_manager = VariantConfigManager()
_global_admin_interface = VariantAdminInterface(_global_config_manager)


def get_variant_config_manager() -> VariantConfigManager:
    """Get the global variant configuration manager."""
    return _global_config_manager


def get_variant_admin_interface() -> VariantAdminInterface:
    """Get the global variant admin interface."""
    return _global_admin_interface
