#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Scoring Logic (04_score.py)
Applies scoring rules defined in scoring_rules.yml to calculate lead scores.
Usage:
    python bin/04_score.py [--limit N] [--id BUSINESS_ID] [--recalculate]
Options:
    --limit N        Limit the number of businesses to process (default: all)
    --id BUSINESS_ID Process only the specified business ID
    --recalculate    Recalculate scores for businesses that already have scores
"""
import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Union

# Use lowercase versions for Python 3.9 compatibility
# Use lowercase versions for Python 3.9 compatibility
import yaml
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Local application/library specific imports with try-except for Python 3.9 compatibility during testing
# Import database utilities with conditional imports for testing


# For Python 3.9 compatibility, define fallback implementations for when imports are not available


# Define fallback function and class implementations
class _TestingDatabaseConnection:
    """Alternative database connection for testing environments."""

    def __init__(self, db_path=None):
        self.db_path = db_path
        self.connection = None
        self.cursor = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def execute(self, query, params=None):
        return None

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def commit(self):
        pass


# Try to import real implementations first
# Instead of defining a local DatabaseConnection, we use an adapter function
# This avoids name conflicts while providing the same functionality
def get_database_connection(db_path=None):
    """Return appropriate DatabaseConnection implementation based on environment."""
    try:
        # Try to import the real implementation
        from leadfactory.utils.e2e_db_connector import (
            db_connection as DatabaseConnection,
        )

        return DatabaseConnection(db_path)
    except ImportError:
        # Fall back to our testing implementation
        return _TestingDatabaseConnection(db_path)


try:
    from utils.logging_config import get_logger
except ImportError:
    # During testing, provide a dummy logger
    def get_logger(name: str) -> logging.Logger:
        import logging

        return logging.getLogger(name)


# Set up logging
logger = get_logger(__name__)
# Load environment variables
load_dotenv()
# Constants
DEFAULT_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
CURRENT_TIER = int(os.getenv("TIER", "1"))
RULES_FILE = str(Path(__file__).resolve().parent.parent / "etc" / "scoring_rules.yml")


class RuleEngine:
    """Evaluates business data against scoring rules."""

    def __init__(self, rules_file: str = RULES_FILE):
        """Initialize the rule engine.
        Args:
            rules_file: Path to the YAML file containing scoring rules.
        """
        self.rules_file = rules_file
        self.rules: dict[str, Any] = {}
        self.settings: dict[str, Any] = {}
        self.multipliers: list[dict[str, Any]] = []
        self.load_rules()
        # Define condition evaluators with proper type annotation
        self.condition_evaluators: dict[str, Callable[[Any, dict[str, Any]], bool]] = {
            "tech_stack_contains": self._eval_tech_stack_contains,
            "tech_stack_contains_any": self._eval_tech_stack_contains_any,
            "tech_stack_version_lt": self._eval_tech_stack_version_lt,
            "tech_stack_version_gt": self._eval_tech_stack_version_gt,
            "performance_score_lt": self._eval_performance_score_lt,
            "performance_score_gt": self._eval_performance_score_gt,
            "performance_score_between": self._eval_performance_score_between,
            "lcp_gt": self._eval_lcp_gt,
            "cls_gt": self._eval_cls_gt,
            "category_contains_any": self._eval_category_contains_any,
            "website_missing": self._eval_website_missing,
            "website_contains_any": self._eval_website_contains_any,
            "state_equals": self._eval_state_equals,
            "has_multiple_locations": self._eval_has_multiple_locations,
            "review_count_gt": self._eval_review_count_gt,
            "review_count_lt": self._eval_review_count_lt,
            "seo_score_lt": self._eval_seo_score_lt,
            "accessibility_score_lt": self._eval_accessibility_score_lt,
            "semrush_errors_gt": self._eval_semrush_errors_gt,
            "semrush_score_lt": self._eval_semrush_score_lt,
            "tier_gt": self._eval_tier_gt,
            "tier_equals": self._eval_tier_equals,
            "vertical_in": self._eval_vertical_in,
        }

    def load_rules(self):
        """Load scoring rules from YAML file."""
        try:
            with Path(self.rules_file).open() as f:
                data = yaml.safe_load(f)
            self.settings = data.get("settings", {})
            self.rules = data.get("rules", [])
            self.multipliers = data.get("multipliers", [])
            logger.info(
                f"Loaded {len(self.rules)} rules and {len(self.multipliers)} multipliers from {self.rules_file}"
            )
        except Exception as e:
            logger.error(f"Error loading rules from {self.rules_file}: {e}")
            # Use default settings if loading fails
            self.settings = {
                "base_score": 50,
                "min_score": 0,
                "max_score": 100,
                "high_score_threshold": 75,
            }
            self.rules = []
            self.multipliers = []

    def calculate_score(self, business_data: dict) -> tuple[int, list[dict]]:
        """Calculate score for a business based on the defined rules.
        Args:
            business_data: Business data including tech stack, performance metrics, etc.
        Returns:
            tuple of (final_score, applied_rules).
        """
        # Start with base score
        score = self.settings.get("base_score", 50)
        applied_rules: list[dict[str, Any]] = []
        # Apply each rule
        for rule in self.rules:
            # Skip if rule is not a dictionary
            if not isinstance(rule, dict):
                logger.warning(f"Skipping invalid rule: {rule}")
                continue
            rule_name = rule.get("name", "unnamed_rule")
            rule_condition = rule.get("condition", {})
            rule_score = rule.get("score", 0)
            rule_description = rule.get("description", "")
            # Evaluate rule condition
            if self._evaluate_condition(rule_condition, business_data):
                # Apply score adjustment
                score += rule_score
                # Record applied rule
                applied_rules.append(
                    {
                        "name": rule_name,
                        "description": rule_description,
                        "score_adjustment": rule_score,
                    }
                )
                logger.debug(f"Applied rule '{rule_name}': {rule_score:+d} points")
        # Apply multipliers
        multiplier_value = 1.0
        for multiplier in self.multipliers:
            multiplier_name = multiplier.get("name", "unnamed_multiplier")
            multiplier_condition = multiplier.get("condition", {})
            multiplier_factor = multiplier.get("multiplier", 1.0)
            multiplier_description = multiplier.get("description", "")
            # Evaluate multiplier condition
            if self._evaluate_condition(multiplier_condition, business_data):
                # Apply multiplier
                multiplier_value *= multiplier_factor
                # Record applied multiplier
                applied_rules.append(
                    {
                        "name": multiplier_name,
                        "description": multiplier_description,
                        "multiplier": multiplier_factor,
                    }
                )
                logger.debug(
                    f"Applied multiplier '{multiplier_name}': x{multiplier_factor:.2f}"
                )
        # Apply multiplier to score
        score = int(score * multiplier_value)
        # Ensure score is within min/max bounds
        min_score = self.settings.get("min_score", 0)
        max_score = self.settings.get("max_score", 100)
        score = max(min_score, min(score, max_score))
        return score, applied_rules

    def _evaluate_condition(self, condition: dict, business_data: dict) -> bool:
        """Evaluate a rule condition against business data.
        Args:
            condition: Rule condition definition.
            business_data: Business data to evaluate against.
        Returns:
            True if condition is met, False otherwise.
        """
        # Handle empty condition (always true)
        if not condition:
            return True
        # Evaluate each condition key
        for key, value in condition.items():
            if key in self.condition_evaluators:
                # Call the appropriate evaluator function
                if not self.condition_evaluators[key](value, business_data):
                    return False
            else:
                logger.warning(f"Unknown condition type: {key}")
                return False
        # All conditions passed
        return True

    # Condition evaluator methods
    def _eval_tech_stack_contains(self, technology: str, business_data: dict) -> bool:
        """Check if business tech stack contains a specific technology."""
        tech_stack = self._get_tech_stack(business_data)
        return technology in tech_stack

    def _eval_tech_stack_contains_any(
        self, technologies: list[str], business_data: dict
    ) -> bool:
        """Check if business tech stack contains any of the specified technologies."""
        tech_stack = self._get_tech_stack(business_data)
        return any(tech in tech_stack for tech in technologies)

    def _eval_tech_stack_version_lt(self, condition: dict, business_data: dict) -> bool:
        """Check if business tech stack contains a technology with version less than specified."""
        tech_stack = self._get_tech_stack(business_data)
        technology = condition.get("technology", "")
        version = condition.get("version", "")
        if technology not in tech_stack:
            return False
        tech_version = self._get_tech_version(business_data, technology)
        if not tech_version:
            return False
        return self._compare_versions(tech_version, version) < 0

    def _eval_tech_stack_version_gt(self, condition: dict, business_data: dict) -> bool:
        """Check if business tech stack contains a technology with version greater than specified."""
        tech_stack = self._get_tech_stack(business_data)
        technology = condition.get("technology", "")
        version = condition.get("version", "")
        if technology not in tech_stack:
            return False
        tech_version = self._get_tech_version(business_data, technology)
        if not tech_version:
            return False
        return self._compare_versions(tech_version, version) > 0

    def _eval_performance_score_lt(self, threshold: int, business_data: dict) -> bool:
        """Check if business performance score is less than threshold."""
        performance_score = self._get_performance_score(business_data)
        return performance_score < threshold

    def _eval_performance_score_gt(self, threshold: int, business_data: dict) -> bool:
        """Check if business performance score is greater than threshold."""
        performance_score = self._get_performance_score(business_data)
        return performance_score > threshold

    def _eval_performance_score_between(
        self, condition: dict, business_data: dict
    ) -> bool:
        """Check if business performance score is between min and max values."""
        performance_score = self._get_performance_score(business_data)
        min_value = condition.get("min", 0)
        max_value = condition.get("max", 100)
        return min_value <= performance_score <= max_value

    def _eval_lcp_gt(self, threshold: int, business_data: dict) -> bool:
        """Check if business LCP is greater than threshold."""
        lcp = self._get_lcp(business_data)
        return lcp > threshold

    def _eval_cls_gt(self, threshold: float, business_data: dict) -> bool:
        """Check if business CLS is greater than threshold."""
        cls = self._get_cls(business_data)
        return cls > threshold

    def _eval_category_contains_any(
        self, categories: list[str], business_data: dict
    ) -> bool:
        """Check if business category contains any of the specified categories."""
        business_category = business_data.get("category", "").lower()
        return any(category.lower() in business_category for category in categories)

    def _eval_website_missing(self, value: bool, business_data: dict) -> bool:
        """Check if business website is missing."""
        has_website = bool(business_data.get("website"))
        return not has_website if value else has_website

    def _eval_website_contains_any(
        self, patterns: list[str], business_data: dict
    ) -> bool:
        """Check if business website contains any of the specified patterns."""
        website = business_data.get("website", "")
        if not website:
            return False
        website_content = self._get_website_content(business_data)
        return any(pattern in website_content for pattern in patterns)

    def _eval_state_equals(self, state: str, business_data: dict) -> bool:
        """Check if business state equals the specified state."""
        business_state = business_data.get("state", "")
        return business_state.upper() == state.upper()

    def _eval_has_multiple_locations(self, value: bool, business_data: dict) -> bool:
        """Check if business has multiple locations."""
        has_multiple = business_data.get("has_multiple_locations", False)
        return has_multiple if value else not has_multiple

    def _eval_review_count_gt(self, threshold: int, business_data: dict) -> bool:
        """Check if business review count is greater than threshold."""
        review_count = business_data.get("review_count", 0)
        return review_count > threshold

    def _eval_review_count_lt(self, threshold: int, business_data: dict) -> bool:
        """Check if business review count is less than threshold."""
        review_count = business_data.get("review_count", 0)
        return review_count < threshold

    def _eval_seo_score_lt(self, threshold: int, business_data: dict) -> bool:
        """Check if business SEO score is less than threshold."""
        seo_score = self._get_seo_score(business_data)
        return seo_score < threshold

    def _eval_accessibility_score_lt(self, threshold: int, business_data: dict) -> bool:
        """Check if business accessibility score is less than threshold."""
        accessibility_score = self._get_accessibility_score(business_data)
        return accessibility_score < threshold

    def _eval_semrush_errors_gt(self, threshold: int, business_data: dict) -> bool:
        """Check if business SEMrush errors count is greater than threshold."""
        semrush_errors = self._get_semrush_errors(business_data)
        return semrush_errors > threshold

    def _eval_semrush_score_lt(self, threshold: int, business_data: dict) -> bool:
        """Check if business SEMrush score is less than threshold."""
        semrush_score = self._get_semrush_score(business_data)
        return semrush_score < threshold

    def _eval_tier_gt(self, threshold: int, business_data: dict) -> bool:
        """Check if business tier is greater than threshold."""
        tier = business_data.get("tier", CURRENT_TIER)
        return tier > threshold

    def _eval_tier_equals(self, value: int, business_data: dict) -> bool:
        """Check if business tier equals the specified value."""
        tier = business_data.get("tier", CURRENT_TIER)
        return tier == value

    def _eval_vertical_in(self, verticals: list[str], business_data: dict) -> bool:
        """Check if business vertical is in the specified list."""
        vertical = business_data.get("vertical", "")
        return vertical in verticals

    # Helper methods
    def _get_tech_stack(self, business_data: dict) -> dict:
        """Get tech stack from business data."""
        features = business_data.get("features", {})
        tech_stack_json = features.get("tech_stack", "{}")
        if isinstance(tech_stack_json, str):
            try:
                tech_stack = json.loads(tech_stack_json)
            except json.JSONDecodeError:
                tech_stack = {}
        else:
            tech_stack = tech_stack_json
        return tech_stack

    def _get_tech_version(self, business_data: dict, technology: str) -> Optional[str]:
        """Get version of a specific technology from business data."""
        tech_stack = self._get_tech_stack(business_data)
        tech_info = tech_stack.get(technology, {})
        if isinstance(tech_info, dict):
            return tech_info.get("version")
        return None

    def _get_performance_score(self, business_data: dict) -> int:
        """Get performance score from business data."""
        features = business_data.get("features", {})
        return features.get("page_speed", 0)

    def _get_lcp(self, business_data: dict) -> float:
        """Get Largest Contentful Paint from business data."""
        features = business_data.get("features", {})
        page_speed_json = features.get("page_speed_json", "{}")
        if isinstance(page_speed_json, str):
            try:
                page_speed = json.loads(page_speed_json)
            except json.JSONDecodeError:
                page_speed = {}
        else:
            page_speed = page_speed_json
        return page_speed.get("largest_contentful_paint", 0)

    def _get_cls(self, business_data: dict) -> float:
        """Get Cumulative Layout Shift from business data."""
        features = business_data.get("features", {})
        page_speed_json = features.get("page_speed_json", "{}")
        if isinstance(page_speed_json, str):
            try:
                page_speed = json.loads(page_speed_json)
            except json.JSONDecodeError:
                page_speed = {}
        else:
            page_speed = page_speed_json
        return page_speed.get("cumulative_layout_shift", 0)

    def _get_seo_score(self, business_data: dict) -> int:
        """Get SEO score from business data."""
        features = business_data.get("features", {})
        page_speed_json = features.get("page_speed_json", "{}")
        if isinstance(page_speed_json, str):
            try:
                page_speed = json.loads(page_speed_json)
            except json.JSONDecodeError:
                page_speed = {}
        else:
            page_speed = page_speed_json
        return page_speed.get("seo_score", 0)

    def _get_accessibility_score(self, business_data: dict) -> int:
        """Get accessibility score from business data."""
        features = business_data.get("features", {})
        page_speed_json = features.get("page_speed_json", "{}")
        if isinstance(page_speed_json, str):
            try:
                page_speed = json.loads(page_speed_json)
            except json.JSONDecodeError:
                page_speed = {}
        else:
            page_speed = page_speed_json
        return page_speed.get("accessibility_score", 0)

    def _get_semrush_errors(self, business_data: dict) -> int:
        """Get SEMrush errors count from business data."""
        features = business_data.get("features", {})
        semrush_json = features.get("semrush_json", "{}")
        if isinstance(semrush_json, str):
            try:
                semrush = json.loads(semrush_json)
            except json.JSONDecodeError:
                semrush = {}
        else:
            semrush = semrush_json
        return semrush.get("errors", 0)

    def _get_semrush_score(self, business_data: dict) -> int:
        """Get SEMrush score from business data."""
        features = business_data.get("features", {})
        semrush_json = features.get("semrush_json", "{}")
        if isinstance(semrush_json, str):
            try:
                semrush = json.loads(semrush_json)
            except json.JSONDecodeError:
                semrush = {}
        else:
            semrush = semrush_json
        return semrush.get("total_score", 0)

    def _get_website_content(self, business_data: dict) -> str:
        """Get website content from business data."""
        # In a real implementation, this would fetch the content from a cache
        # For the prototype, we'll just use the website URL
        return business_data.get("website", "")

    def _compare_versions(self, version1: str, version2: str) -> int:
        """Compare two version strings.
        Args:
            version1: First version string.
            version2: Second version string.
        Returns:
            -1 if version1 < version2, 0 if version1 == version2, 1 if version1 > version2.
        """
        if not version1 and not version2:
            return 0
        if not version1:
            return -1
        if not version2:
            return 1

        # Extract version components
        def normalize_version(version):
            # Convert version string to list of integers
            return [int(x) for x in re.findall(r"\d+", version)]

        v1_parts = normalize_version(version1)
        v2_parts = normalize_version(version2)
        # Compare version components
        for i in range(min(len(v1_parts), len(v2_parts))):
            if v1_parts[i] < v2_parts[i]:
                return -1
            if v1_parts[i] > v2_parts[i]:
                return 1
        # If all components are equal, compare lengths
        if len(v1_parts) < len(v2_parts):
            return -1
        if len(v1_parts) > len(v2_parts):
            return 1
        return 0


def get_businesses_to_score(
    limit: Optional[int] = None,
    business_id: Optional[int] = None,
    recalculate: bool = False,
) -> list[dict]:
    """Get list of businesses to score.
    Args:
        limit: Maximum number of businesses to return.
        business_id: Specific business ID to return.
        recalculate: If True, include businesses that already have scores.
    Returns:
        list of dictionaries containing business information.
    """
    try:
        with get_database_connection() as cursor:
            # Build query based on parameters
            query_parts = ["SELECT b.*, f.* FROM businesses b"]
            query_parts.append("LEFT JOIN features f ON b.id = f.business_id")
            where_clauses = []
            params = []
            # Add business ID filter if specified
            if business_id:
                where_clauses.append("b.id = ?")
                params.append(business_id)
            # Add status filter
            where_clauses.append("b.status = 'active'")
            # Add features filter
            where_clauses.append("f.id IS NOT NULL")
            # Add score filter if not recalculating
            if not recalculate:
                where_clauses.append("b.score IS NULL")
            # Combine where clauses
            if where_clauses:
                query_parts.append("WHERE " + " AND ".join(where_clauses))
            # Add limit if specified
            if limit:
                query_parts.append(f"LIMIT {limit}")
            # Execute query
            query = " ".join(query_parts)
            cursor.execute(query, params)
            businesses = cursor.fetchall()
        logger.info(f"Found {len(businesses)} businesses to score")
        return businesses
    except Exception as e:
        logger.error(f"Error getting businesses to score: {e}")
        return []


def save_business_score(
    business_id: int, score: int, applied_rules: list[dict]
) -> bool:
    """Save business score to database.
    Args:
        business_id: Business ID.
        score: Calculated score.
        applied_rules: list of applied rules.
    Returns:
        True if successful, False otherwise.
    """
    try:
        with get_database_connection() as cursor:
            # Update business score
            cursor.execute(
                """
                UPDATE businesses
                SET score = ?, score_details = ?
                WHERE id = ?
                """,
                (score, json.dumps(applied_rules), business_id),
            )
        logger.info(f"Saved score {score} for business ID {business_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving score for business ID {business_id}: {e}")
        return False


def score_business(business: dict, rule_engine: RuleEngine) -> bool:
    """Score a business using the rule engine.
    Args:
        business: Business data.
        rule_engine: RuleEngine instance.
    Returns:
        True if successful, False otherwise.
    """
    business_id = business["id"]
    try:
        # Calculate score
        score, applied_rules = rule_engine.calculate_score(business)
        logger.info(
            f"Calculated score {score} for business ID {business_id} with {len(applied_rules)} applied rules"
        )
        # Save score to database
        success = save_business_score(business_id, score, applied_rules)
        return success
    except Exception as e:
        logger.error(f"Error scoring business ID {business_id}: {e}")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Calculate lead scores based on defined rules"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit the number of businesses to process"
    )
    parser.add_argument("--id", type=int, help="Process only the specified business ID")
    parser.add_argument(
        "--recalculate",
        action="store_true",
        help="Recalculate scores for businesses that already have scores",
    )
    args = parser.parse_args()
    # Initialize rule engine
    rule_engine = RuleEngine()
    # Get businesses to score
    businesses = get_businesses_to_score(
        limit=args.limit, business_id=args.id, recalculate=args.recalculate
    )
    if not businesses:
        logger.warning("No businesses to score")
        return 0
    logger.info(f"Scoring {len(businesses)} businesses")
    # Process businesses
    success_count = 0
    error_count = 0
    for business in businesses:
        try:
            success = score_business(business, rule_engine)
            if success:
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            logger.error(f"Error processing business ID {business['id']}: {e}")
            error_count += 1
    logger.info(f"Scoring completed. Success: {success_count}, Errors: {error_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
