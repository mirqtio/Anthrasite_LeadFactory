"""
Variant Selection Mechanism for A/B Testing.

This module provides functionality for assigning leads to different pipeline
variants based on configurable distribution strategies.
"""

import hashlib
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.pipeline.variants import (
    PipelineVariant,
    VariantRegistry,
    get_variant_registry,
)
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class DistributionStrategy(Enum):
    """Distribution strategies for variant selection."""

    EQUAL = "equal"  # Equal distribution across all variants
    WEIGHTED = "weighted"  # Distribution based on variant weights
    PERCENTAGE = "percentage"  # Distribution based on target percentages
    HASH_BASED = "hash_based"  # Deterministic hash-based distribution
    RANDOM = "random"  # Pure random distribution


@dataclass
class SelectionContext:
    """Context information for variant selection."""

    business_id: int
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SelectionResult:
    """Result of variant selection."""

    variant_id: str
    variant_name: str
    selection_reason: str
    confidence: float = 1.0  # Confidence in the selection (0.0 to 1.0)
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class VariantSelector(ABC):
    """Abstract base class for variant selection strategies."""

    def __init__(self, registry: Optional[VariantRegistry] = None):
        self.registry = registry or get_variant_registry()

    @abstractmethod
    def select_variant(self, context: SelectionContext) -> Optional[SelectionResult]:
        """Select a variant based on the given context."""
        pass

    def get_available_variants(self) -> List[PipelineVariant]:
        """Get all available active variants."""
        return self.registry.get_active_variants()


class EqualDistributionSelector(VariantSelector):
    """Selects variants with equal probability."""

    def select_variant(self, context: SelectionContext) -> Optional[SelectionResult]:
        variants = self.get_available_variants()
        if not variants:
            logger.warning("No active variants available for selection")
            return None

        # Use deterministic selection based on business_id for consistency
        index = context.business_id % len(variants)
        selected_variant = variants[index]

        return SelectionResult(
            variant_id=selected_variant.id,
            variant_name=selected_variant.name,
            selection_reason=f"Equal distribution (index {index} of {len(variants)})",
            confidence=1.0,
        )


class WeightedDistributionSelector(VariantSelector):
    """Selects variants based on their weights."""

    def select_variant(self, context: SelectionContext) -> Optional[SelectionResult]:
        variants = self.get_available_variants()
        if not variants:
            logger.warning("No active variants available for selection")
            return None

        # Calculate total weight
        total_weight = sum(variant.weight for variant in variants)
        if total_weight <= 0:
            logger.error("Total weight is zero or negative")
            return None

        # Use deterministic selection based on business_id
        # This ensures the same business always gets the same variant
        hash_input = f"{context.business_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        selection_point = (hash_value % 10000) / 10000.0 * total_weight

        # Find the variant that corresponds to this selection point
        cumulative_weight = 0
        for variant in variants:
            cumulative_weight += variant.weight
            if selection_point <= cumulative_weight:
                return SelectionResult(
                    variant_id=variant.id,
                    variant_name=variant.name,
                    selection_reason=f"Weighted distribution (weight: {variant.weight}/{total_weight})",
                    confidence=variant.weight / total_weight,
                )

        # Fallback to last variant (shouldn't happen with proper weights)
        last_variant = variants[-1]
        return SelectionResult(
            variant_id=last_variant.id,
            variant_name=last_variant.name,
            selection_reason="Weighted distribution (fallback)",
            confidence=last_variant.weight / total_weight,
        )


class PercentageDistributionSelector(VariantSelector):
    """Selects variants based on target percentages."""

    def select_variant(self, context: SelectionContext) -> Optional[SelectionResult]:
        variants = self.get_available_variants()
        if not variants:
            logger.warning("No active variants available for selection")
            return None

        # Filter variants with target percentages
        percentage_variants = [v for v in variants if v.target_percentage is not None]
        if not percentage_variants:
            logger.warning(
                "No variants with target percentages found, falling back to equal distribution"
            )
            return EqualDistributionSelector(self.registry).select_variant(context)

        # Validate that percentages don't exceed 100%
        total_percentage = sum(v.target_percentage for v in percentage_variants)
        if total_percentage > 100:
            logger.error(f"Total target percentages exceed 100%: {total_percentage}")
            return None

        # Use deterministic selection based on business_id
        hash_input = f"{context.business_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        selection_point = (hash_value % 10000) / 100.0  # 0-100 range

        # Find the variant that corresponds to this selection point
        cumulative_percentage = 0
        for variant in percentage_variants:
            cumulative_percentage += variant.target_percentage
            if selection_point <= cumulative_percentage:
                return SelectionResult(
                    variant_id=variant.id,
                    variant_name=variant.name,
                    selection_reason=f"Percentage distribution (target: {variant.target_percentage}%)",
                    confidence=variant.target_percentage / 100.0,
                )

        # If selection point is beyond all percentages, use default variant or first one
        default_variant = percentage_variants[0]
        return SelectionResult(
            variant_id=default_variant.id,
            variant_name=default_variant.name,
            selection_reason="Percentage distribution (default)",
            confidence=(
                default_variant.target_percentage / 100.0
                if default_variant.target_percentage
                else 0.5
            ),
        )


class HashBasedSelector(VariantSelector):
    """Deterministic hash-based variant selection."""

    def __init__(
        self, registry: Optional[VariantRegistry] = None, hash_key: str = "business_id"
    ):
        super().__init__(registry)
        self.hash_key = hash_key

    def select_variant(self, context: SelectionContext) -> Optional[SelectionResult]:
        variants = self.get_available_variants()
        if not variants:
            logger.warning("No active variants available for selection")
            return None

        # Create hash input based on the specified key
        if self.hash_key == "business_id":
            hash_input = str(context.business_id)
        elif self.hash_key == "user_id" and context.user_id:
            hash_input = context.user_id
        elif self.hash_key == "session_id" and context.session_id:
            hash_input = context.session_id
        else:
            hash_input = str(context.business_id)  # Fallback

        # Generate deterministic hash
        hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        index = hash_value % len(variants)
        selected_variant = variants[index]

        return SelectionResult(
            variant_id=selected_variant.id,
            variant_name=selected_variant.name,
            selection_reason=f"Hash-based distribution (key: {self.hash_key}, index: {index})",
            confidence=1.0,
        )


class RandomSelector(VariantSelector):
    """Pure random variant selection (non-deterministic)."""

    def __init__(
        self, registry: Optional[VariantRegistry] = None, seed: Optional[int] = None
    ):
        super().__init__(registry)
        if seed is not None:
            random.seed(seed)

    def select_variant(self, context: SelectionContext) -> Optional[SelectionResult]:
        variants = self.get_available_variants()
        if not variants:
            logger.warning("No active variants available for selection")
            return None

        selected_variant = random.choice(variants)

        return SelectionResult(
            variant_id=selected_variant.id,
            variant_name=selected_variant.name,
            selection_reason="Random selection",
            confidence=1.0 / len(variants),
        )


class SmartSelector(VariantSelector):
    """Smart selector that chooses the best strategy based on variant configuration."""

    def select_variant(self, context: SelectionContext) -> Optional[SelectionResult]:
        variants = self.get_available_variants()
        if not variants:
            logger.warning("No active variants available for selection")
            return None

        # Determine the best strategy based on variant configuration
        has_percentages = any(v.target_percentage is not None for v in variants)
        has_custom_weights = any(v.weight != 1.0 for v in variants)

        if has_percentages:
            selector = PercentageDistributionSelector(self.registry)
            strategy = "percentage"
        elif has_custom_weights:
            selector = WeightedDistributionSelector(self.registry)
            strategy = "weighted"
        else:
            selector = EqualDistributionSelector(self.registry)
            strategy = "equal"

        result = selector.select_variant(context)
        if result:
            result.selection_reason = (
                f"Smart selection ({strategy}): {result.selection_reason}"
            )

        return result


class VariantSelectionManager:
    """Manager for variant selection with caching and fallback strategies."""

    def __init__(
        self,
        primary_selector: Optional[VariantSelector] = None,
        fallback_selector: Optional[VariantSelector] = None,
        registry: Optional[VariantRegistry] = None,
    ):
        self.registry = registry or get_variant_registry()
        self.primary_selector = primary_selector or SmartSelector(self.registry)
        self.fallback_selector = fallback_selector or EqualDistributionSelector(
            self.registry
        )
        self._selection_cache: Dict[str, SelectionResult] = {}

    def select_variant(
        self, context: SelectionContext, use_cache: bool = True
    ) -> Optional[SelectionResult]:
        """Select a variant with caching and fallback support."""

        # Check cache first if enabled
        cache_key = self._generate_cache_key(context)
        if use_cache and cache_key in self._selection_cache:
            cached_result = self._selection_cache[cache_key]
            logger.debug(
                f"Using cached variant selection: {cached_result.variant_name}"
            )
            return cached_result

        # Try primary selector
        try:
            result = self.primary_selector.select_variant(context)
            if result:
                if use_cache:
                    self._selection_cache[cache_key] = result
                logger.info(
                    f"Selected variant: {result.variant_name} for business {context.business_id}"
                )
                return result
        except Exception as e:
            logger.error(f"Primary selector failed: {e}")

        # Try fallback selector
        try:
            result = self.fallback_selector.select_variant(context)
            if result:
                result.selection_reason = f"Fallback: {result.selection_reason}"
                if use_cache:
                    self._selection_cache[cache_key] = result
                logger.warning(
                    f"Used fallback selector for variant: {result.variant_name}"
                )
                return result
        except Exception as e:
            logger.error(f"Fallback selector failed: {e}")

        logger.error("All variant selectors failed")
        return None

    def _generate_cache_key(self, context: SelectionContext) -> str:
        """Generate a cache key for the selection context."""
        return f"{context.business_id}:{context.user_id}:{context.session_id}"

    def clear_cache(self):
        """Clear the selection cache."""
        self._selection_cache.clear()
        logger.info("Variant selection cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._selection_cache),
            "cached_variants": list(
                set(result.variant_id for result in self._selection_cache.values())
            ),
        }


# Global selection manager instance
_global_selection_manager = VariantSelectionManager()


def get_selection_manager() -> VariantSelectionManager:
    """Get the global variant selection manager."""
    return _global_selection_manager


def select_variant_for_business(
    business_id: int,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[SelectionResult]:
    """Convenience function to select a variant for a business."""
    context = SelectionContext(
        business_id=business_id,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata or {},
    )
    return get_selection_manager().select_variant(context)


def create_selector(strategy: DistributionStrategy, **kwargs) -> VariantSelector:
    """Factory function to create selectors based on strategy."""
    registry = kwargs.get("registry")

    if strategy == DistributionStrategy.EQUAL:
        return EqualDistributionSelector(registry)
    elif strategy == DistributionStrategy.WEIGHTED:
        return WeightedDistributionSelector(registry)
    elif strategy == DistributionStrategy.PERCENTAGE:
        return PercentageDistributionSelector(registry)
    elif strategy == DistributionStrategy.HASH_BASED:
        hash_key = kwargs.get("hash_key", "business_id")
        return HashBasedSelector(registry, hash_key)
    elif strategy == DistributionStrategy.RANDOM:
        seed = kwargs.get("seed")
        return RandomSelector(registry, seed)
    else:
        raise ValueError(f"Unknown distribution strategy: {strategy}")
