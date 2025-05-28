"""
Conflict resolution module for deduplication.

This module provides strategies and algorithms for resolving data conflicts
when merging duplicate business records.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from leadfactory.config.dedupe_config import DedupeConfig

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of conflicts that can occur during deduplication."""

    DIFFERENT_VALUES = "different_values"
    MISSING_IN_PRIMARY = "missing_in_primary"
    MISSING_IN_SECONDARY = "missing_in_secondary"
    BOTH_PRESENT_DIFFERENT = "both_present_different"
    BOTH_PRESENT_SAME = "both_present_same"


class ResolutionStrategy(Enum):
    """Strategies for resolving conflicts."""

    KEEP_PRIMARY = "keep_primary"
    KEEP_SECONDARY = "keep_secondary"
    MERGE_CONCATENATE = "merge_concatenate"
    MERGE_NEWEST = "merge_newest"
    MERGE_LONGEST = "merge_longest"
    MERGE_HIGHEST_QUALITY = "merge_highest_quality"
    MANUAL_REVIEW = "manual_review"


class ConflictResolver:
    """Handles conflict resolution during business record merging."""

    def __init__(self, config: DedupeConfig):
        """Initialize conflict resolver with configuration."""
        self.config = config
        self.resolution_rules = self._initialize_resolution_rules()

    def _initialize_resolution_rules(self) -> Dict[str, ResolutionStrategy]:
        """Initialize default resolution rules for different fields."""
        return {
            # Core fields - prefer primary unless empty
            "name": ResolutionStrategy.KEEP_PRIMARY,
            "phone": ResolutionStrategy.KEEP_PRIMARY,
            "email": ResolutionStrategy.KEEP_PRIMARY,
            # Address fields - keep consistent set
            "address": ResolutionStrategy.KEEP_PRIMARY,
            "city": ResolutionStrategy.KEEP_PRIMARY,
            "state": ResolutionStrategy.KEEP_PRIMARY,
            "zip": ResolutionStrategy.KEEP_PRIMARY,
            # Descriptive fields - merge or keep longest
            "category": ResolutionStrategy.MERGE_LONGEST,
            "website": ResolutionStrategy.KEEP_PRIMARY,
            # Response fields - keep newest or highest quality
            "google_response": ResolutionStrategy.MERGE_NEWEST,
            "yelp_response": ResolutionStrategy.MERGE_NEWEST,
            "manual_response": ResolutionStrategy.MERGE_NEWEST,
        }

    def identify_conflicts(
        self, primary: Dict[str, Any], secondary: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Identify all conflicts between two business records.

        Args:
            primary: Primary business record
            secondary: Secondary business record

        Returns:
            List of conflict dictionaries
        """
        conflicts = []

        # Check all fields that might need merging
        all_fields = set(primary.keys()) | set(secondary.keys())

        for field in all_fields:
            if field in ["id", "created_at", "updated_at"]:
                continue  # Skip system fields

            primary_value = primary.get(field)
            secondary_value = secondary.get(field)

            conflict_type = self._determine_conflict_type(
                primary_value, secondary_value
            )

            if conflict_type != ConflictType.BOTH_PRESENT_SAME:
                # Check if field requires manual review
                if (
                    self.config.enable_manual_review
                    and field in self.config.manual_review_fields
                    and conflict_type == ConflictType.BOTH_PRESENT_DIFFERENT
                ):
                    resolution_strategy = ResolutionStrategy.MANUAL_REVIEW
                else:
                    resolution_strategy = self.resolution_rules.get(
                        field, ResolutionStrategy.KEEP_PRIMARY
                    )

                conflicts.append(
                    {
                        "field": field,
                        "type": conflict_type,
                        "primary_value": primary_value,
                        "secondary_value": secondary_value,
                        "resolution_strategy": resolution_strategy,
                    }
                )

        return conflicts

    def _determine_conflict_type(
        self, primary_value: Any, secondary_value: Any
    ) -> ConflictType:
        """Determine the type of conflict between two values."""
        if primary_value is None and secondary_value is None:
            return ConflictType.BOTH_PRESENT_SAME
        elif primary_value is None:
            return ConflictType.MISSING_IN_PRIMARY
        elif secondary_value is None:
            return ConflictType.MISSING_IN_SECONDARY
        elif primary_value == secondary_value:
            return ConflictType.BOTH_PRESENT_SAME
        else:
            return ConflictType.BOTH_PRESENT_DIFFERENT

    def resolve_conflicts(
        self,
        conflicts: List[Dict[str, Any]],
        primary: Dict[str, Any],
        secondary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve conflicts and return updates to apply to primary record.

        Args:
            conflicts: List of identified conflicts
            primary: Primary business record
            secondary: Secondary business record

        Returns:
            Dictionary of field updates to apply
        """
        updates = {}
        manual_review_needed = []

        for conflict in conflicts:
            field = conflict["field"]
            strategy = conflict["resolution_strategy"]
            resolved_value = None

            if strategy == ResolutionStrategy.KEEP_PRIMARY:
                # Only update if primary is missing the value
                if conflict["type"] == ConflictType.MISSING_IN_PRIMARY:
                    resolved_value = conflict["secondary_value"]

            elif strategy == ResolutionStrategy.KEEP_SECONDARY:
                resolved_value = conflict["secondary_value"]

            elif strategy == ResolutionStrategy.MERGE_CONCATENATE:
                resolved_value = self._merge_concatenate(
                    conflict["primary_value"], conflict["secondary_value"]
                )

            elif strategy == ResolutionStrategy.MERGE_LONGEST:
                resolved_value = self._merge_longest(
                    conflict["primary_value"], conflict["secondary_value"]
                )

            elif strategy == ResolutionStrategy.MERGE_NEWEST:
                resolved_value = self._merge_newest(field, primary, secondary)

            elif strategy == ResolutionStrategy.MERGE_HIGHEST_QUALITY:
                resolved_value = self._merge_highest_quality(field, primary, secondary)

            elif strategy == ResolutionStrategy.MANUAL_REVIEW:
                manual_review_needed.append(conflict)
                continue

            # Apply the resolved value if different from primary
            if resolved_value is not None and resolved_value != primary.get(field):
                updates[field] = resolved_value

        # Log manual review requirements
        if manual_review_needed:
            logger.warning(
                f"Manual review needed for {len(manual_review_needed)} conflicts: "
                f"{[c['field'] for c in manual_review_needed]}"
            )

        return updates

    def _merge_concatenate(self, value1: Any, value2: Any) -> Optional[str]:
        """Merge by concatenating non-empty values."""
        values = []
        if value1:
            values.append(str(value1))
        if value2:
            values.append(str(value2))

        if not values:
            return None
        elif len(values) == 1:
            return values[0]
        else:
            return " | ".join(values)

    def _merge_longest(self, value1: Any, value2: Any) -> Any:
        """Keep the longest non-empty value."""
        if not value1:
            return value2
        if not value2:
            return value1

        len1 = len(str(value1))
        len2 = len(str(value2))

        return value1 if len1 >= len2 else value2

    def _merge_newest(
        self, field: str, primary: Dict[str, Any], secondary: Dict[str, Any]
    ) -> Any:
        """Keep the value from the most recently updated record."""
        # Check if we have timestamp information
        primary_updated = primary.get("updated_at") or primary.get("created_at")
        secondary_updated = secondary.get("updated_at") or secondary.get("created_at")

        if not primary_updated or not secondary_updated:
            # Fallback to keeping primary if no timestamps
            return primary.get(field)

        # Compare timestamps
        if isinstance(primary_updated, str):
            primary_updated = datetime.fromisoformat(
                primary_updated.replace("Z", "+00:00")
            )
        if isinstance(secondary_updated, str):
            secondary_updated = datetime.fromisoformat(
                secondary_updated.replace("Z", "+00:00")
            )

        if secondary_updated > primary_updated:
            return secondary.get(field)
        else:
            return primary.get(field)

    def _merge_highest_quality(
        self, field: str, primary: Dict[str, Any], secondary: Dict[str, Any]
    ) -> Any:
        """Keep the highest quality value based on source priority."""
        primary_source = primary.get("source", "unknown")
        secondary_source = secondary.get("source", "unknown")

        primary_priority = self.config.source_priorities.get(primary_source, 0)
        secondary_priority = self.config.source_priorities.get(secondary_source, 0)

        if secondary_priority > primary_priority:
            return secondary.get(field)
        else:
            return primary.get(field)

    def generate_conflict_report(
        self, conflicts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a detailed conflict report for logging or review.

        Args:
            conflicts: List of identified conflicts

        Returns:
            Conflict report dictionary
        """
        report = {
            "total_conflicts": len(conflicts),
            "conflicts_by_type": {},
            "conflicts_by_field": {},
            "resolution_strategies": {},
            "manual_review_required": [],
        }

        for conflict in conflicts:
            # Count by type
            conflict_type = conflict["type"].value
            report["conflicts_by_type"][conflict_type] = (
                report["conflicts_by_type"].get(conflict_type, 0) + 1
            )

            # Count by field
            field = conflict["field"]
            report["conflicts_by_field"][field] = (
                report["conflicts_by_field"].get(field, 0) + 1
            )

            # Track resolution strategies
            strategy = conflict["resolution_strategy"].value
            report["resolution_strategies"][strategy] = (
                report["resolution_strategies"].get(strategy, 0) + 1
            )

            # Track manual review requirements
            if conflict["resolution_strategy"] == ResolutionStrategy.MANUAL_REVIEW:
                report["manual_review_required"].append(
                    {
                        "field": field,
                        "primary_value": conflict["primary_value"],
                        "secondary_value": conflict["secondary_value"],
                    }
                )

        return report


def apply_conflict_resolution(
    primary: Dict[str, Any], secondary: Dict[str, Any], config: DedupeConfig
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Apply conflict resolution to two business records.

    Args:
        primary: Primary business record
        secondary: Secondary business record
        config: Deduplication configuration

    Returns:
        Tuple of (updates to apply, conflict report)
    """
    resolver = ConflictResolver(config)

    # Identify conflicts
    conflicts = resolver.identify_conflicts(primary, secondary)

    # Resolve conflicts
    updates = resolver.resolve_conflicts(conflicts, primary, secondary)

    # Generate report
    report = resolver.generate_conflict_report(conflicts)

    logger.info(
        f"Conflict resolution completed: {len(conflicts)} conflicts found, "
        f"{len(updates)} updates to apply"
    )

    return updates, report
