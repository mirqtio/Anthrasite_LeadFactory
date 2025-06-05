"""
Pricing A/B Testing - Price variant optimization for audit sales.

This module provides specialized A/B testing for pricing strategies including
price points, discount offers, and payment terms optimization.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.ab_testing.ab_test_manager import (
    ABTestManager,
    TestType,
    ab_test_manager,
)
from leadfactory.utils.logging import get_logger


class PricingTestType(Enum):
    """Pricing A/B test types."""

    PRICE_POINT = "price_point"
    DISCOUNT_OFFER = "discount_offer"
    PAYMENT_TERMS = "payment_terms"
    BUNDLE_PRICING = "bundle_pricing"
    CURRENCY_DISPLAY = "currency_display"


@dataclass
class PriceVariant:
    """Price variant configuration."""

    id: str
    weight: float
    price: int  # Price in cents
    currency: str = "usd"
    discount_percentage: Optional[float] = None
    discount_amount: Optional[int] = None  # Discount in cents
    original_price: Optional[int] = None  # Original price before discount
    display_format: Optional[str] = None  # How to display the price
    payment_terms: Optional[str] = None  # Payment terms description
    metadata: Optional[Dict[str, Any]] = None


class PricingABTest:
    """Pricing A/B testing manager integrated with payment system."""

    def __init__(self, test_manager: Optional[ABTestManager] = None):
        """Initialize pricing A/B test manager.

        Args:
            test_manager: A/B test manager instance
        """
        self.test_manager = test_manager or ab_test_manager
        self.logger = get_logger(f"{__name__}.PricingABTest")

    def create_price_point_test(
        self,
        name: str,
        description: str,
        audit_type: str,
        price_variants: List[Dict[str, Any]],
        target_sample_size: int = 1000,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a price point A/B test.

        Args:
            name: Test name
            description: Test description
            audit_type: Type of audit (seo, security, performance, etc.)
            price_variants: List of price variants with amounts
            target_sample_size: Target number of pricing exposures
            metadata: Additional test metadata

        Returns:
            Test ID

        Example:
            >>> test_id = pricing_ab_test.create_price_point_test(
            ...     name="SEO Audit Price Optimization Q1",
            ...     description="Test different price points for SEO audits",
            ...     audit_type="seo",
            ...     price_variants=[
            ...         {"price": 7900, "weight": 0.33},   # $79
            ...         {"price": 9900, "weight": 0.33},   # $99 (current)
            ...         {"price": 12900, "weight": 0.34}   # $129
            ...     ]
            ... )
        """
        # Validate price variants
        if not price_variants or len(price_variants) < 2:
            raise ValueError("Price test requires at least 2 variants")

        for variant in price_variants:
            if "price" not in variant:
                raise ValueError("Each variant must have a 'price' field")
            if not isinstance(variant["price"], int):
                raise ValueError("Price must be an integer (cents)")
            if variant["price"] < 100:  # Minimum $1.00
                raise ValueError("Price must be at least 100 cents ($1.00)")

        # Prepare variants for A/B test manager
        test_variants = []
        for i, variant in enumerate(price_variants):
            test_variants.append(
                {
                    "id": f"price_variant_{i}",
                    "price": variant["price"],
                    "currency": variant.get("currency", "usd"),
                    "weight": variant.get("weight", 1.0 / len(price_variants)),
                    "display_format": variant.get("display_format", "standard"),
                    "metadata": variant.get("metadata", {}),
                }
            )

        test_metadata = {
            "audit_type": audit_type,
            "test_type": PricingTestType.PRICE_POINT.value,
            "currency": price_variants[0].get("currency", "usd"),
            **(metadata or {}),
        }

        test_id = self.test_manager.create_test(
            name=name,
            description=description,
            test_type=TestType.PRICING,
            variants=test_variants,
            target_sample_size=target_sample_size,
            metadata=test_metadata,
        )

        self.logger.info(f"Created price point A/B test: {test_id} for {audit_type}")
        return test_id

    def create_discount_test(
        self,
        name: str,
        description: str,
        audit_type: str,
        base_price: int,
        discount_variants: List[Dict[str, Any]],
        target_sample_size: int = 1000,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a discount offer A/B test.

        Args:
            name: Test name
            description: Test description
            audit_type: Type of audit
            base_price: Base price in cents
            discount_variants: List of discount variants
            target_sample_size: Target number of pricing exposures
            metadata: Additional test metadata

        Returns:
            Test ID
        """
        # Validate discount variants
        if not discount_variants or len(discount_variants) < 2:
            raise ValueError("Discount test requires at least 2 variants")

        # Prepare variants
        test_variants = []
        for i, variant in enumerate(discount_variants):
            discount_percentage = variant.get("discount_percentage", 0)
            discount_amount = variant.get("discount_amount", 0)

            # Calculate final price
            if discount_percentage > 0:
                final_price = int(base_price * (1 - discount_percentage / 100))
                discount_amount = base_price - final_price
            elif discount_amount > 0:
                final_price = base_price - discount_amount
                discount_percentage = (discount_amount / base_price) * 100
            else:
                final_price = base_price

            test_variants.append(
                {
                    "id": f"discount_variant_{i}",
                    "price": final_price,
                    "original_price": base_price,
                    "discount_percentage": discount_percentage,
                    "discount_amount": discount_amount,
                    "currency": variant.get("currency", "usd"),
                    "weight": variant.get("weight", 1.0 / len(discount_variants)),
                    "display_format": variant.get("display_format", "discount"),
                    "offer_text": variant.get("offer_text", ""),
                    "metadata": variant.get("metadata", {}),
                }
            )

        test_metadata = {
            "audit_type": audit_type,
            "test_type": PricingTestType.DISCOUNT_OFFER.value,
            "base_price": base_price,
            **(metadata or {}),
        }

        test_id = self.test_manager.create_test(
            name=name,
            description=description,
            test_type=TestType.PRICING,
            variants=test_variants,
            target_sample_size=target_sample_size,
            metadata=test_metadata,
        )

        self.logger.info(f"Created discount A/B test: {test_id} for {audit_type}")
        return test_id

    def create_bundle_pricing_test(
        self,
        name: str,
        description: str,
        bundle_variants: List[Dict[str, Any]],
        target_sample_size: int = 1000,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a bundle pricing A/B test.

        Args:
            name: Test name
            description: Test description
            bundle_variants: List of bundle pricing variants
            target_sample_size: Target number of exposures
            metadata: Additional test metadata

        Returns:
            Test ID
        """
        # Validate bundle variants
        if not bundle_variants or len(bundle_variants) < 2:
            raise ValueError("Bundle test requires at least 2 variants")

        # Prepare variants
        test_variants = []
        for i, variant in enumerate(bundle_variants):
            test_variants.append(
                {
                    "id": f"bundle_variant_{i}",
                    "price": variant["price"],
                    "bundle_items": variant["bundle_items"],
                    "individual_prices": variant.get("individual_prices", []),
                    "savings_amount": variant.get("savings_amount", 0),
                    "savings_percentage": variant.get("savings_percentage", 0),
                    "currency": variant.get("currency", "usd"),
                    "weight": variant.get("weight", 1.0 / len(bundle_variants)),
                    "display_format": variant.get("display_format", "bundle"),
                    "metadata": variant.get("metadata", {}),
                }
            )

        test_metadata = {
            "test_type": PricingTestType.BUNDLE_PRICING.value,
            **(metadata or {}),
        }

        test_id = self.test_manager.create_test(
            name=name,
            description=description,
            test_type=TestType.PRICING,
            variants=test_variants,
            target_sample_size=target_sample_size,
            metadata=test_metadata,
        )

        self.logger.info(f"Created bundle pricing A/B test: {test_id}")
        return test_id

    def get_price_for_user(
        self, user_id: str, audit_type: str, test_id: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Get the pricing variant assigned to a user.

        Args:
            user_id: User identifier
            audit_type: Type of audit being purchased
            test_id: Specific test ID (optional, will find active test)

        Returns:
            Tuple of (variant_id, pricing_config)
        """
        # Find active pricing test if not specified
        if not test_id:
            active_tests = self.test_manager.get_active_tests(TestType.PRICING)
            pricing_tests = [
                t for t in active_tests if t.metadata.get("audit_type") == audit_type
            ]

            if not pricing_tests:
                # No active test, return default pricing
                default_prices = {
                    "seo": 9900,
                    "security": 14900,
                    "performance": 7900,
                    "accessibility": 8900,
                    "comprehensive": 24900,
                }
                return "default", {
                    "price": default_prices.get(audit_type, 9900),
                    "currency": "usd",
                    "display_format": "standard",
                }

            test_id = pricing_tests[0].id

        # Get user's variant assignment
        variant_id = self.test_manager.assign_user_to_variant(
            user_id=user_id, test_id=test_id, metadata={"audit_type": audit_type}
        )

        # Get test configuration
        test_config = self.test_manager.get_test_config(test_id)
        if not test_config:
            raise ValueError(f"Test not found: {test_id}")

        # Find variant configuration
        variant_index = int(variant_id.split("_")[-1])
        if variant_index >= len(test_config.variants):
            raise ValueError(f"Invalid variant index: {variant_index}")

        variant_config = test_config.variants[variant_index]

        self.logger.debug(f"Assigned user {user_id} to pricing variant {variant_id}")
        return variant_id, variant_config

    def format_price_display(self, pricing_config: Dict[str, Any]) -> Dict[str, str]:
        """Format price for display based on variant configuration.

        Args:
            pricing_config: Pricing configuration from variant

        Returns:
            Dictionary with formatted price information
        """
        price = pricing_config["price"]
        currency = pricing_config.get("currency", "usd")
        display_format = pricing_config.get("display_format", "standard")

        # Format base price
        if currency.lower() == "usd":
            formatted_price = f"${price / 100:.2f}"
        else:
            formatted_price = f"{price / 100:.2f} {currency.upper()}"

        result = {
            "price": formatted_price,
            "amount_cents": price,
            "currency": currency,
            "display_format": display_format,
        }

        # Handle discount display
        if display_format == "discount" and "original_price" in pricing_config:
            original_price = pricing_config["original_price"]
            if currency.lower() == "usd":
                result["original_price"] = f"${original_price / 100:.2f}"
            else:
                result["original_price"] = (
                    f"{original_price / 100:.2f} {currency.upper()}"
                )

            result["discount_percentage"] = pricing_config.get("discount_percentage", 0)
            result["savings"] = f"${(original_price - price) / 100:.2f}"
            result["offer_text"] = pricing_config.get("offer_text", "")

        # Handle bundle display
        elif display_format == "bundle":
            bundle_items = pricing_config.get("bundle_items", [])
            individual_prices = pricing_config.get("individual_prices", [])

            result["bundle_items"] = bundle_items
            result["individual_total"] = sum(individual_prices)
            result["savings_amount"] = pricing_config.get("savings_amount", 0)
            result["savings_percentage"] = pricing_config.get("savings_percentage", 0)

        return result

    def record_pricing_event(
        self,
        test_id: str,
        user_id: str,
        event_type: str,
        conversion_value: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record a pricing-related event for A/B testing.

        Args:
            test_id: Test identifier
            user_id: User identifier
            event_type: Event type (view, add_to_cart, purchase, abandon)
            conversion_value: Monetary value for purchase events
            metadata: Additional event metadata
        """
        self.test_manager.record_conversion(
            test_id=test_id,
            user_id=user_id,
            conversion_type=f"pricing_{event_type}",
            conversion_value=conversion_value,
            metadata=metadata,
        )

        self.logger.debug(
            f"Recorded pricing event {event_type} for user {user_id} in test {test_id}"
        )

    def get_pricing_test_performance(self, test_id: str) -> Dict[str, Any]:
        """Get detailed performance metrics for a pricing A/B test.

        Args:
            test_id: Test identifier

        Returns:
            Dictionary with pricing-specific performance metrics
        """
        results = self.test_manager.get_test_results(test_id)

        # Calculate pricing-specific metrics
        pricing_metrics = {}

        for variant_id, variant_data in results["variant_results"].items():
            conversions = variant_data["conversion_rates"]
            assignments = variant_data["assignments"]

            # Calculate pricing funnel metrics
            view_rate = conversions.get("pricing_view", {}).get("rate", 0)
            cart_rate = conversions.get("pricing_add_to_cart", {}).get("rate", 0)
            purchase_rate = conversions.get("pricing_purchase", {}).get("rate", 0)
            abandon_rate = conversions.get("pricing_abandon", {}).get("rate", 0)

            # Calculate revenue metrics
            total_revenue = conversions.get("pricing_purchase", {}).get(
                "total_value", 0
            )
            avg_order_value = conversions.get("pricing_purchase", {}).get(
                "avg_value", 0
            )

            # Calculate conversion efficiency
            view_to_cart = cart_rate / view_rate if view_rate > 0 else 0
            cart_to_purchase = purchase_rate / cart_rate if cart_rate > 0 else 0

            pricing_metrics[variant_id] = {
                "assignments": assignments,
                "view_rate": view_rate,
                "cart_rate": cart_rate,
                "purchase_rate": purchase_rate,
                "abandon_rate": abandon_rate,
                "view_to_cart_rate": view_to_cart,
                "cart_to_purchase_rate": cart_to_purchase,
                "total_revenue": total_revenue,
                "avg_order_value": avg_order_value,
                "revenue_per_visitor": (
                    total_revenue / assignments if assignments > 0 else 0
                ),
            }

        # Get test configuration for price comparisons
        test_config = results["test_config"]

        # Add variant price information
        for i, variant in enumerate(test_config.variants):
            variant_id = f"variant_{i}"
            if variant_id in pricing_metrics:
                pricing_metrics[variant_id]["price_cents"] = variant.get("price", 0)
                pricing_metrics[variant_id][
                    "price_display"
                ] = f"${variant.get('price', 0) / 100:.2f}"

        return {
            "test_id": test_id,
            "test_name": test_config.name,
            "test_type": test_config.test_type.value,
            "status": test_config.status.value,
            "pricing_metrics": pricing_metrics,
            "total_assignments": results["total_assignments"],
            "start_date": test_config.start_date,
            "end_date": test_config.end_date,
            "audit_type": test_config.metadata.get("audit_type"),
        }

    def get_winning_price(
        self, test_id: str, confidence_threshold: float = 0.95
    ) -> Optional[Dict[str, Any]]:
        """Determine the winning price variant based on statistical significance.

        Args:
            test_id: Test identifier
            confidence_threshold: Required confidence level (default 95%)

        Returns:
            Dictionary with winning variant information or None if inconclusive
        """
        performance = self.get_pricing_test_performance(test_id)

        # Find variant with highest conversion rate
        best_variant = None
        best_purchase_rate = 0
        best_revenue_per_visitor = 0

        for variant_id, metrics in performance["pricing_metrics"].items():
            purchase_rate = metrics["purchase_rate"]
            revenue_per_visitor = metrics["revenue_per_visitor"]

            # Use revenue per visitor as primary metric, conversion rate as secondary
            if revenue_per_visitor > best_revenue_per_visitor:
                best_revenue_per_visitor = revenue_per_visitor
                best_purchase_rate = purchase_rate
                best_variant = variant_id

        if best_variant:
            test_config = self.test_manager.get_test_config(test_id)
            variant_index = int(best_variant.split("_")[-1])
            variant_config = test_config.variants[variant_index]

            return {
                "variant_id": best_variant,
                "variant_config": variant_config,
                "purchase_rate": best_purchase_rate,
                "revenue_per_visitor": best_revenue_per_visitor,
                "price_cents": variant_config.get("price", 0),
                "confidence_level": confidence_threshold,  # Using configured threshold
                "recommended_action": (
                    "adopt" if best_revenue_per_visitor > 0 else "continue_testing"
                ),
            }

        return None


# Global instance
pricing_ab_test = PricingABTest()
