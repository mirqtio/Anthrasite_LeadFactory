"""
Rule evaluation logic for scoring engine.

This module contains the logic for evaluating businesses against scoring rules.
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Union

from leadfactory.utils.logging import get_logger

from .yaml_parser import RuleCondition, ScoringMultiplier, ScoringRule

logger = get_logger(__name__)


class RuleEvaluator:
    """Evaluates businesses against scoring rules."""

    def __init__(self):
        """Initialize the rule evaluator."""
        self.logger = get_logger(__name__ + ".RuleEvaluator")

    def evaluate_rule(
        self, business: Dict[str, Any], rule: ScoringRule
    ) -> Tuple[bool, int]:
        """
        Evaluate a single rule against a business.

        Args:
            business: Business data dictionary.
            rule: ScoringRule to evaluate.

        Returns:
            Tuple of (rule_matched, score_adjustment).
        """
        try:
            if self._evaluate_condition(business, rule.condition):
                self.logger.debug(
                    f"Rule '{rule.name}' matched for business {business.get('name', 'unknown')}",
                    extra={"rule": rule.name, "score": rule.score},
                )
                return True, rule.score
            return False, 0
        except Exception as e:
            self.logger.error(
                f"Error evaluating rule '{rule.name}': {e}",
                extra={"rule": rule.name, "error": str(e)},
            )
            return False, 0

    def evaluate_multiplier(
        self, business: Dict[str, Any], multiplier: ScoringMultiplier
    ) -> float:
        """
        Evaluate a scoring multiplier against a business.

        Args:
            business: Business data dictionary.
            multiplier: ScoringMultiplier to evaluate.

        Returns:
            Multiplier value if condition matches, 1.0 otherwise.
        """
        try:
            if self._evaluate_condition(business, multiplier.condition):
                self.logger.debug(
                    f"Multiplier '{multiplier.name}' matched for business "
                    f"{business.get('name', 'unknown')}",
                    extra={
                        "multiplier": multiplier.name,
                        "value": multiplier.multiplier,
                    },
                )
                return multiplier.multiplier
            return 1.0
        except Exception as e:
            self.logger.error(
                f"Error evaluating multiplier '{multiplier.name}': {e}",
                extra={"multiplier": multiplier.name, "error": str(e)},
            )
            return 1.0

    def _evaluate_condition(
        self, business: Dict[str, Any], condition: RuleCondition
    ) -> bool:
        """
        Evaluate a condition against business data.

        Args:
            business: Business data dictionary.
            condition: Condition to evaluate.

        Returns:
            True if condition matches, False otherwise.
        """
        # Handle combined conditions first
        if condition.all_of:
            return all(
                self._evaluate_condition(business, RuleCondition(**sub_condition))
                for sub_condition in condition.all_of
            )

        if condition.any_of:
            return any(
                self._evaluate_condition(business, RuleCondition(**sub_condition))
                for sub_condition in condition.any_of
            )

        if condition.none_of:
            return not any(
                self._evaluate_condition(business, RuleCondition(**sub_condition))
                for sub_condition in condition.none_of
            )

        # Tech stack conditions
        if condition.tech_stack_contains:
            return self._check_tech_stack_contains(
                business, condition.tech_stack_contains
            )

        if condition.tech_stack_contains_any:
            return any(
                self._check_tech_stack_contains(business, tech)
                for tech in condition.tech_stack_contains_any
            )

        if condition.tech_stack_version_lt:
            return self._check_tech_version(
                business,
                condition.tech_stack_version_lt["technology"],
                condition.tech_stack_version_lt["version"],
                "lt",
            )

        if condition.tech_stack_version_gt:
            return self._check_tech_version(
                business,
                condition.tech_stack_version_gt["technology"],
                condition.tech_stack_version_gt["version"],
                "gt",
            )

        # Business attribute conditions
        if condition.vertical_in:
            return self._check_attribute_in(business, "vertical", condition.vertical_in)

        if condition.vertical_not_in:
            return not self._check_attribute_in(
                business, "vertical", condition.vertical_not_in
            )

        if condition.location_in:
            return self._check_location_in(business, condition.location_in)

        if condition.location_not_in:
            return not self._check_location_in(business, condition.location_not_in)

        if condition.employee_count_gt is not None:
            return self._check_numeric_comparison(
                business, "employee_count", condition.employee_count_gt, "gt"
            )

        if condition.employee_count_lt is not None:
            return self._check_numeric_comparison(
                business, "employee_count", condition.employee_count_lt, "lt"
            )

        if condition.revenue_gt is not None:
            return self._check_numeric_comparison(
                business, "revenue", condition.revenue_gt, "gt"
            )

        if condition.revenue_lt is not None:
            return self._check_numeric_comparison(
                business, "revenue", condition.revenue_lt, "lt"
            )

        if condition.founded_year_gt is not None:
            return self._check_numeric_comparison(
                business, "founded_year", condition.founded_year_gt, "gt"
            )

        if condition.founded_year_lt is not None:
            return self._check_numeric_comparison(
                business, "founded_year", condition.founded_year_lt, "lt"
            )

        # Social media conditions
        if condition.has_social_media:
            return self._check_has_social_media(business, condition.has_social_media)

        if condition.social_followers_gt:
            return self._check_social_metric(
                business, "followers", condition.social_followers_gt, "gt"
            )

        if condition.social_engagement_gt:
            return self._check_social_metric(
                business, "engagement", condition.social_engagement_gt, "gt"
            )

        # Website conditions
        if condition.has_contact_form is not None:
            return business.get("has_contact_form", False) == condition.has_contact_form

        if condition.has_phone_number is not None:
            return business.get("has_phone_number", False) == condition.has_phone_number

        if condition.has_email is not None:
            return business.get("has_email", False) == condition.has_email

        if condition.page_count_gt is not None:
            return self._check_numeric_comparison(
                business, "page_count", condition.page_count_gt, "gt"
            )

        if condition.page_count_lt is not None:
            return self._check_numeric_comparison(
                business, "page_count", condition.page_count_lt, "lt"
            )

        # If no conditions are specified, return True
        return True

    def _check_tech_stack_contains(
        self, business: Dict[str, Any], technology: str
    ) -> bool:
        """Check if business tech stack contains a technology."""
        tech_stack = business.get("tech_stack", [])
        if isinstance(tech_stack, list):
            # Handle list of strings
            return any(technology.lower() in str(tech).lower() for tech in tech_stack)
        elif isinstance(tech_stack, dict):
            # Handle dict format {"technology": "version"}
            return technology.lower() in [k.lower() for k in tech_stack.keys()]
        return False

    def _check_tech_version(
        self, business: Dict[str, Any], technology: str, version: str, operator: str
    ) -> bool:
        """Check technology version comparison."""
        tech_stack = business.get("tech_stack", {})

        if isinstance(tech_stack, dict):
            tech_version = tech_stack.get(technology)
            if tech_version:
                return self._compare_versions(tech_version, version, operator)
        elif isinstance(tech_stack, list):
            # Try to extract version from list format
            for tech in tech_stack:
                if isinstance(tech, str) and technology.lower() in tech.lower():
                    # Try to extract version number
                    match = re.search(r"(\d+(?:\.\d+)*)", tech)
                    if match:
                        return self._compare_versions(match.group(1), version, operator)
        return False

    def _compare_versions(self, v1: str, v2: str, operator: str) -> bool:
        """Compare two version strings."""
        try:
            # Convert version strings to tuples of integers
            v1_parts = tuple(int(x) for x in str(v1).split("."))
            v2_parts = tuple(int(x) for x in str(v2).split("."))

            if operator == "lt":
                return v1_parts < v2_parts
            elif operator == "gt":
                return v1_parts > v2_parts
            elif operator == "eq":
                return v1_parts == v2_parts
            else:
                return False
        except (ValueError, AttributeError):
            # If version parsing fails, do string comparison
            if operator == "lt":
                return str(v1) < str(v2)
            elif operator == "gt":
                return str(v1) > str(v2)
            elif operator == "eq":
                return str(v1) == str(v2)
            return False

    def _check_attribute_in(
        self, business: Dict[str, Any], attribute: str, values: List[str]
    ) -> bool:
        """Check if business attribute is in list of values."""
        business_value = business.get(attribute, "")
        if isinstance(business_value, str):
            return any(value.lower() in business_value.lower() for value in values)
        return False

    def _check_location_in(
        self, business: Dict[str, Any], locations: List[str]
    ) -> bool:
        """Check if business location matches any of the specified locations."""
        # Check multiple location fields
        location_fields = ["location", "city", "state", "country", "region"]

        for field in location_fields:
            field_value = business.get(field, "")
            if isinstance(field_value, str):
                for location in locations:
                    if location.lower() in field_value.lower():
                        return True

        # Also check address if available
        address = business.get("address", "")
        if isinstance(address, str):
            for location in locations:
                if location.lower() in address.lower():
                    return True

        return False

    def _check_numeric_comparison(
        self,
        business: Dict[str, Any],
        field: str,
        value: Union[int, float],
        operator: str,
    ) -> bool:
        """Check numeric field comparison."""
        business_value = business.get(field)

        if business_value is None:
            return False

        try:
            business_value = float(business_value)
            value = float(value)

            if operator == "gt":
                return business_value > value
            elif operator == "lt":
                return business_value < value
            elif operator == "eq":
                return business_value == value
            elif operator == "gte":
                return business_value >= value
            elif operator == "lte":
                return business_value <= value
            else:
                return False
        except (ValueError, TypeError):
            return False

    def _check_has_social_media(
        self, business: Dict[str, Any], platforms: List[str]
    ) -> bool:
        """Check if business has specified social media platforms."""
        social_media = business.get("social_media", {})

        if isinstance(social_media, dict):
            return any(
                platform.lower() in [k.lower() for k in social_media.keys()]
                for platform in platforms
            )
        elif isinstance(social_media, list):
            return any(
                platform.lower() in [s.lower() for s in social_media]
                for platform in platforms
            )
        return False

    def _check_social_metric(
        self,
        business: Dict[str, Any],
        metric: str,
        thresholds: Dict[str, int],
        operator: str,
    ) -> bool:
        """Check social media metric comparison."""
        social_media = business.get("social_media", {})

        if not isinstance(social_media, dict):
            return False

        for platform, threshold in thresholds.items():
            platform_data = social_media.get(platform, {})
            if isinstance(platform_data, dict):
                metric_value = platform_data.get(metric, 0)
                if self._check_numeric_comparison(
                    {metric: metric_value}, metric, threshold, operator
                ):
                    return True

        return False
