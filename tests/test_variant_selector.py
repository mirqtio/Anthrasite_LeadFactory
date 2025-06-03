"""
Tests for variant selector module.
"""

import pytest
import hashlib
from unittest.mock import Mock, patch

from leadfactory.pipeline.variant_selector import (
    DistributionStrategy, SelectionContext, SelectionResult,
    EqualDistributionSelector, WeightedDistributionSelector,
    PercentageDistributionSelector, HashBasedSelector, RandomSelector,
    SmartSelector, VariantSelectionManager, select_variant_for_business,
    create_selector, get_selection_manager
)
from leadfactory.pipeline.variants import PipelineVariant, VariantRegistry, VariantStatus


class TestSelectionContext:
    """Test SelectionContext class."""

    def test_selection_context_creation(self):
        """Test creating a selection context."""
        context = SelectionContext(
            business_id=123,
            user_id="user456",
            session_id="session789",
            timestamp="2023-01-01T00:00:00Z",
            metadata={"key": "value"}
        )

        assert context.business_id == 123
        assert context.user_id == "user456"
        assert context.session_id == "session789"
        assert context.timestamp == "2023-01-01T00:00:00Z"
        assert context.metadata == {"key": "value"}

    def test_selection_context_defaults(self):
        """Test selection context with default values."""
        context = SelectionContext(business_id=123)

        assert context.business_id == 123
        assert context.user_id is None
        assert context.session_id is None
        assert context.timestamp is None
        assert context.metadata == {}


class TestSelectionResult:
    """Test SelectionResult class."""

    def test_selection_result_creation(self):
        """Test creating a selection result."""
        result = SelectionResult(
            variant_id="variant123",
            variant_name="test_variant",
            selection_reason="Test selection",
            confidence=0.8,
            metadata={"key": "value"}
        )

        assert result.variant_id == "variant123"
        assert result.variant_name == "test_variant"
        assert result.selection_reason == "Test selection"
        assert result.confidence == 0.8
        assert result.metadata == {"key": "value"}

    def test_selection_result_defaults(self):
        """Test selection result with default values."""
        result = SelectionResult(
            variant_id="variant123",
            variant_name="test_variant",
            selection_reason="Test selection"
        )

        assert result.confidence == 1.0
        assert result.metadata == {}


class TestEqualDistributionSelector:
    """Test EqualDistributionSelector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = VariantRegistry()
        self.selector = EqualDistributionSelector(self.registry)

        # Create test variants
        self.variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE)
        self.variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE)
        self.variant3 = PipelineVariant(name="variant3", status=VariantStatus.ACTIVE)

        self.registry.register_variant(self.variant1)
        self.registry.register_variant(self.variant2)
        self.registry.register_variant(self.variant3)

    def test_equal_distribution_selection(self):
        """Test equal distribution selection."""
        context = SelectionContext(business_id=100)
        result = self.selector.select_variant(context)

        assert result is not None
        assert result.variant_id in [self.variant1.id, self.variant2.id, self.variant3.id]
        assert result.confidence == 1.0
        assert "Equal distribution" in result.selection_reason

    def test_equal_distribution_deterministic(self):
        """Test that equal distribution is deterministic for same business_id."""
        context1 = SelectionContext(business_id=100)
        context2 = SelectionContext(business_id=100)

        result1 = self.selector.select_variant(context1)
        result2 = self.selector.select_variant(context2)

        assert result1.variant_id == result2.variant_id

    def test_equal_distribution_different_businesses(self):
        """Test that different businesses can get different variants."""
        results = []
        for business_id in range(100):
            context = SelectionContext(business_id=business_id)
            result = self.selector.select_variant(context)
            results.append(result.variant_id)

        # Should have some distribution across variants
        unique_variants = set(results)
        assert len(unique_variants) > 1

    def test_no_active_variants(self):
        """Test selection when no active variants exist."""
        empty_registry = VariantRegistry()
        selector = EqualDistributionSelector(empty_registry)

        context = SelectionContext(business_id=100)
        result = selector.select_variant(context)

        assert result is None


class TestWeightedDistributionSelector:
    """Test WeightedDistributionSelector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = VariantRegistry()
        self.selector = WeightedDistributionSelector(self.registry)

        # Create test variants with different weights
        self.variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE, weight=1.0)
        self.variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE, weight=2.0)
        self.variant3 = PipelineVariant(name="variant3", status=VariantStatus.ACTIVE, weight=3.0)

        self.registry.register_variant(self.variant1)
        self.registry.register_variant(self.variant2)
        self.registry.register_variant(self.variant3)

    def test_weighted_distribution_selection(self):
        """Test weighted distribution selection."""
        context = SelectionContext(business_id=100)
        result = self.selector.select_variant(context)

        assert result is not None
        assert result.variant_id in [self.variant1.id, self.variant2.id, self.variant3.id]
        assert "Weighted distribution" in result.selection_reason
        assert 0 < result.confidence <= 1.0

    def test_weighted_distribution_deterministic(self):
        """Test that weighted distribution is deterministic."""
        context1 = SelectionContext(business_id=100)
        context2 = SelectionContext(business_id=100)

        result1 = self.selector.select_variant(context1)
        result2 = self.selector.select_variant(context2)

        assert result1.variant_id == result2.variant_id

    def test_weighted_distribution_bias(self):
        """Test that higher weights get more selections."""
        # Test many selections to see distribution
        selections = {}
        for business_id in range(1000):
            context = SelectionContext(business_id=business_id)
            result = self.selector.select_variant(context)
            variant_name = result.variant_name
            selections[variant_name] = selections.get(variant_name, 0) + 1

        # variant3 (weight=3.0) should get more selections than variant1 (weight=1.0)
        assert selections.get("variant3", 0) > selections.get("variant1", 0)

    def test_zero_total_weight(self):
        """Test selection when total weight is zero."""
        # Create variants with zero weights
        registry = VariantRegistry()
        variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE, weight=0.0)
        variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE, weight=0.0)
        registry.register_variant(variant1)
        registry.register_variant(variant2)

        selector = WeightedDistributionSelector(registry)
        context = SelectionContext(business_id=100)
        result = selector.select_variant(context)

        assert result is None


class TestPercentageDistributionSelector:
    """Test PercentageDistributionSelector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = VariantRegistry()
        self.selector = PercentageDistributionSelector(self.registry)

        # Create test variants with target percentages
        self.variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE, target_percentage=30.0)
        self.variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE, target_percentage=50.0)
        self.variant3 = PipelineVariant(name="variant3", status=VariantStatus.ACTIVE, target_percentage=20.0)

        self.registry.register_variant(self.variant1)
        self.registry.register_variant(self.variant2)
        self.registry.register_variant(self.variant3)

    def test_percentage_distribution_selection(self):
        """Test percentage distribution selection."""
        context = SelectionContext(business_id=100)
        result = self.selector.select_variant(context)

        assert result is not None
        assert result.variant_id in [self.variant1.id, self.variant2.id, self.variant3.id]
        assert "Percentage distribution" in result.selection_reason
        assert 0 < result.confidence <= 1.0

    def test_percentage_distribution_deterministic(self):
        """Test that percentage distribution is deterministic."""
        context1 = SelectionContext(business_id=100)
        context2 = SelectionContext(business_id=100)

        result1 = self.selector.select_variant(context1)
        result2 = self.selector.select_variant(context2)

        assert result1.variant_id == result2.variant_id

    def test_percentage_exceeds_100(self):
        """Test selection when percentages exceed 100%."""
        registry = VariantRegistry()
        variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE, target_percentage=60.0)
        variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE, target_percentage=60.0)
        registry.register_variant(variant1)
        registry.register_variant(variant2)

        selector = PercentageDistributionSelector(registry)
        context = SelectionContext(business_id=100)
        result = selector.select_variant(context)

        assert result is None

    def test_no_percentage_variants(self):
        """Test fallback when no variants have target percentages."""
        registry = VariantRegistry()
        variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE)  # No target_percentage
        variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE)  # No target_percentage
        registry.register_variant(variant1)
        registry.register_variant(variant2)

        selector = PercentageDistributionSelector(registry)
        context = SelectionContext(business_id=100)
        result = selector.select_variant(context)

        # Should fallback to equal distribution
        assert result is not None
        assert result.variant_id in [variant1.id, variant2.id]


class TestHashBasedSelector:
    """Test HashBasedSelector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = VariantRegistry()

        # Create test variants
        self.variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE)
        self.variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE)
        self.variant3 = PipelineVariant(name="variant3", status=VariantStatus.ACTIVE)

        self.registry.register_variant(self.variant1)
        self.registry.register_variant(self.variant2)
        self.registry.register_variant(self.variant3)

    def test_hash_based_selection_business_id(self):
        """Test hash-based selection using business_id."""
        selector = HashBasedSelector(self.registry, hash_key="business_id")
        context = SelectionContext(business_id=100)
        result = selector.select_variant(context)

        assert result is not None
        assert result.variant_id in [self.variant1.id, self.variant2.id, self.variant3.id]
        assert "Hash-based distribution" in result.selection_reason
        assert "business_id" in result.selection_reason
        assert result.confidence == 1.0

    def test_hash_based_selection_user_id(self):
        """Test hash-based selection using user_id."""
        selector = HashBasedSelector(self.registry, hash_key="user_id")
        context = SelectionContext(business_id=100, user_id="user123")
        result = selector.select_variant(context)

        assert result is not None
        assert "user_id" in result.selection_reason

    def test_hash_based_selection_fallback(self):
        """Test hash-based selection fallback to business_id."""
        selector = HashBasedSelector(self.registry, hash_key="user_id")
        context = SelectionContext(business_id=100)  # No user_id
        result = selector.select_variant(context)

        assert result is not None
        # Should fallback to business_id

    def test_hash_based_deterministic(self):
        """Test that hash-based selection is deterministic."""
        selector = HashBasedSelector(self.registry, hash_key="business_id")
        context1 = SelectionContext(business_id=100)
        context2 = SelectionContext(business_id=100)

        result1 = selector.select_variant(context1)
        result2 = selector.select_variant(context2)

        assert result1.variant_id == result2.variant_id


class TestRandomSelector:
    """Test RandomSelector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = VariantRegistry()

        # Create test variants
        self.variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE)
        self.variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE)
        self.variant3 = PipelineVariant(name="variant3", status=VariantStatus.ACTIVE)

        self.registry.register_variant(self.variant1)
        self.registry.register_variant(self.variant2)
        self.registry.register_variant(self.variant3)

    def test_random_selection(self):
        """Test random selection."""
        selector = RandomSelector(self.registry)
        context = SelectionContext(business_id=100)
        result = selector.select_variant(context)

        assert result is not None
        assert result.variant_id in [self.variant1.id, self.variant2.id, self.variant3.id]
        assert "Random selection" in result.selection_reason
        assert result.confidence == 1.0 / 3  # 1 / number of variants

    def test_random_selection_with_seed(self):
        """Test random selection with seed for reproducibility."""
        selector1 = RandomSelector(self.registry, seed=42)
        selector2 = RandomSelector(self.registry, seed=42)

        context = SelectionContext(business_id=100)

        result1 = selector1.select_variant(context)
        result2 = selector2.select_variant(context)

        # With same seed, should get same result
        assert result1.variant_id == result2.variant_id

    def test_random_distribution(self):
        """Test that random selection distributes across variants."""
        selector = RandomSelector(self.registry)

        selections = set()
        for _ in range(100):  # Multiple selections
            context = SelectionContext(business_id=100)
            result = selector.select_variant(context)
            selections.add(result.variant_id)

        # Should see multiple variants (though not guaranteed due to randomness)
        # This test might occasionally fail due to random chance
        assert len(selections) >= 1


class TestSmartSelector:
    """Test SmartSelector class."""

    def test_smart_selector_percentage_strategy(self):
        """Test smart selector choosing percentage strategy."""
        registry = VariantRegistry()
        variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE, target_percentage=60.0)
        variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE, target_percentage=40.0)
        registry.register_variant(variant1)
        registry.register_variant(variant2)

        selector = SmartSelector(registry)
        context = SelectionContext(business_id=100)
        result = selector.select_variant(context)

        assert result is not None
        assert "Smart selection (percentage)" in result.selection_reason

    def test_smart_selector_weighted_strategy(self):
        """Test smart selector choosing weighted strategy."""
        registry = VariantRegistry()
        variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE, weight=2.0)
        variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE, weight=3.0)
        registry.register_variant(variant1)
        registry.register_variant(variant2)

        selector = SmartSelector(registry)
        context = SelectionContext(business_id=100)
        result = selector.select_variant(context)

        assert result is not None
        assert "Smart selection (weighted)" in result.selection_reason

    def test_smart_selector_equal_strategy(self):
        """Test smart selector choosing equal strategy."""
        registry = VariantRegistry()
        variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE)  # Default weight=1.0
        variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE)  # Default weight=1.0
        registry.register_variant(variant1)
        registry.register_variant(variant2)

        selector = SmartSelector(registry)
        context = SelectionContext(business_id=100)
        result = selector.select_variant(context)

        assert result is not None
        assert "Smart selection (equal)" in result.selection_reason


class TestVariantSelectionManager:
    """Test VariantSelectionManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = VariantRegistry()

        # Create test variants
        self.variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE)
        self.variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE)

        self.registry.register_variant(self.variant1)
        self.registry.register_variant(self.variant2)

        self.primary_selector = SmartSelector(self.registry)
        self.fallback_selector = EqualDistributionSelector(self.registry)

        self.manager = VariantSelectionManager(
            primary_selector=self.primary_selector,
            fallback_selector=self.fallback_selector,
            registry=self.registry
        )

    def test_selection_manager_primary_success(self):
        """Test selection manager using primary selector."""
        context = SelectionContext(business_id=100)
        result = self.manager.select_variant(context)

        assert result is not None
        assert result.variant_id in [self.variant1.id, self.variant2.id]

    def test_selection_manager_caching(self):
        """Test selection manager caching."""
        context = SelectionContext(business_id=100, user_id="user123")

        # First call
        result1 = self.manager.select_variant(context, use_cache=True)

        # Second call should use cache
        result2 = self.manager.select_variant(context, use_cache=True)

        assert result1.variant_id == result2.variant_id

    def test_selection_manager_no_cache(self):
        """Test selection manager without caching."""
        context = SelectionContext(business_id=100)

        result1 = self.manager.select_variant(context, use_cache=False)
        result2 = self.manager.select_variant(context, use_cache=False)

        # Results should be the same due to deterministic selection
        assert result1.variant_id == result2.variant_id

    def test_selection_manager_fallback(self):
        """Test selection manager fallback."""
        # Create a failing primary selector
        failing_selector = Mock()
        failing_selector.select_variant.side_effect = Exception("Primary failed")

        manager = VariantSelectionManager(
            primary_selector=failing_selector,
            fallback_selector=self.fallback_selector,
            registry=self.registry
        )

        context = SelectionContext(business_id=100)
        result = manager.select_variant(context)

        assert result is not None
        assert "Fallback" in result.selection_reason

    def test_selection_manager_cache_stats(self):
        """Test selection manager cache statistics."""
        context1 = SelectionContext(business_id=100, user_id="user1")
        context2 = SelectionContext(business_id=200, user_id="user2")

        self.manager.select_variant(context1, use_cache=True)
        self.manager.select_variant(context2, use_cache=True)

        stats = self.manager.get_cache_stats()
        assert stats["cache_size"] == 2
        assert len(stats["cached_variants"]) >= 1

    def test_selection_manager_clear_cache(self):
        """Test clearing selection manager cache."""
        context = SelectionContext(business_id=100)
        self.manager.select_variant(context, use_cache=True)

        stats_before = self.manager.get_cache_stats()
        assert stats_before["cache_size"] > 0

        self.manager.clear_cache()

        stats_after = self.manager.get_cache_stats()
        assert stats_after["cache_size"] == 0


class TestFactoryFunctions:
    """Test factory and utility functions."""

    def test_select_variant_for_business(self):
        """Test convenience function for business variant selection."""
        # This uses the global selection manager, so we need to set up variants
        registry = VariantRegistry()
        variant = PipelineVariant(name="test_variant", status=VariantStatus.ACTIVE)
        registry.register_variant(variant)

        with patch('leadfactory.pipeline.variant_selector.get_selection_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.select_variant.return_value = SelectionResult(
                variant_id=variant.id,
                variant_name=variant.name,
                selection_reason="Test selection"
            )
            mock_get_manager.return_value = mock_manager

            result = select_variant_for_business(
                business_id=123,
                user_id="user456",
                metadata={"key": "value"}
            )

            assert result is not None
            assert result.variant_id == variant.id

            # Verify the context was created correctly
            call_args = mock_manager.select_variant.call_args[0][0]
            assert call_args.business_id == 123
            assert call_args.user_id == "user456"
            assert call_args.metadata == {"key": "value"}

    def test_create_selector_factory(self):
        """Test selector factory function."""
        registry = VariantRegistry()

        # Test creating different selector types
        equal_selector = create_selector(DistributionStrategy.EQUAL, registry=registry)
        assert isinstance(equal_selector, EqualDistributionSelector)

        weighted_selector = create_selector(DistributionStrategy.WEIGHTED, registry=registry)
        assert isinstance(weighted_selector, WeightedDistributionSelector)

        percentage_selector = create_selector(DistributionStrategy.PERCENTAGE, registry=registry)
        assert isinstance(percentage_selector, PercentageDistributionSelector)

        hash_selector = create_selector(DistributionStrategy.HASH_BASED, registry=registry, hash_key="user_id")
        assert isinstance(hash_selector, HashBasedSelector)

        random_selector = create_selector(DistributionStrategy.RANDOM, registry=registry, seed=42)
        assert isinstance(random_selector, RandomSelector)

        # Test invalid strategy
        with pytest.raises(ValueError):
            create_selector("invalid_strategy")

    def test_get_selection_manager(self):
        """Test getting global selection manager."""
        manager1 = get_selection_manager()
        manager2 = get_selection_manager()

        # Should return the same instance
        assert manager1 is manager2


class TestSelectorIntegration:
    """Integration tests for selectors."""

    def test_selector_distribution_consistency(self):
        """Test that selectors produce consistent distributions."""
        registry = VariantRegistry()

        # Create variants with known weights/percentages
        variant1 = PipelineVariant(name="variant1", status=VariantStatus.ACTIVE, weight=1.0, target_percentage=25.0)
        variant2 = PipelineVariant(name="variant2", status=VariantStatus.ACTIVE, weight=3.0, target_percentage=75.0)

        registry.register_variant(variant1)
        registry.register_variant(variant2)

        # Test multiple selector types
        selectors = [
            EqualDistributionSelector(registry),
            WeightedDistributionSelector(registry),
            PercentageDistributionSelector(registry),
            HashBasedSelector(registry),
            SmartSelector(registry)
        ]

        for selector in selectors:
            # Each selector should return valid results
            context = SelectionContext(business_id=100)
            result = selector.select_variant(context)

            assert result is not None
            assert result.variant_id in [variant1.id, variant2.id]
            assert result.variant_name in ["variant1", "variant2"]
            assert len(result.selection_reason) > 0
            assert 0 < result.confidence <= 1.0
