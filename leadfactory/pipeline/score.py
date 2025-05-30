"""
Business scoring module for LeadFactory.

This module provides functionality to score business data based on various criteria.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional, Union

# Import the new scoring engine
from leadfactory.scoring import ScoringEngine

# Import the unified logging system
from leadfactory.utils.logging import LogContext, get_logger, log_execution_time

# Import metrics
from leadfactory.utils.metrics import (
    LEADS_SCORED,
    PIPELINE_DURATION,
    PIPELINE_ERRORS,
    MetricsTimer,
    record_metric,
)

# Initialize logging with the unified system
logger = get_logger(__name__)


class RuleEngine:
    """
    Rule engine for business scoring.

    This class now acts as a wrapper around the new ScoringEngine
    to maintain backward compatibility.
    """

    def __init__(self, rules=None):
        """
        Initialize the rule engine.

        Args:
            rules: List of scoring rules (ignored, uses YAML config).
        """
        self.logger = get_logger(__name__ + ".RuleEngine")

        # Initialize the new scoring engine
        self.scoring_engine = ScoringEngine()
        try:
            self.scoring_engine.load_rules()
            stats = self.scoring_engine.get_rule_statistics()
            self.logger.info(
                f"Initialized rule engine with {stats['total_rules']} rules "
                f"and {stats['total_multipliers']} multipliers"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize scoring engine: {e}")
            raise

    def evaluate(self, business: dict[str, Any]) -> int:
        """
        Evaluate a business against all rules.

        Args:
            business: Business information.

        Returns:
            Total score as integer.
        """
        business_id = business.get("id", "unknown")
        business_name = business.get("name", "unknown")

        with LogContext(
            self.logger, business_id=business_id, business_name=business_name
        ):
            try:
                # Use the new scoring engine
                result = self.scoring_engine.score_business(business)

                self.logger.info(
                    f"Business {business_name} scored {result['score']} points",
                    extra={
                        "total_score": result["score"],
                        "adjustments": len(result["adjustments"]),
                        "multiplier": result["final_multiplier"],
                    },
                )

                return result["score"]

            except Exception as e:
                self.logger.error(
                    f"Error evaluating rules for business {business_name}: {str(e)}",
                    extra={"error_type": type(e).__name__, "error_message": str(e)},
                )
                return 0


@log_execution_time
def score_business(business: dict[str, Any]) -> int:
    """
    Score a business based on various criteria.

    Args:
        business: Business information.

    Returns:
        Score as integer.
    """
    business_id = business.get("id", "unknown")
    business_name = business.get("name", "unknown")

    # Use LogContext to add structured context to all log messages in this scope
    with LogContext(logger, business_id=business_id, business_name=business_name):
        logger.info(
            f"Scoring business {business_name}", extra={"operation": "score_business"}
        )

        # Use MetricsTimer to measure and record the duration of the scoring process
        with MetricsTimer(PIPELINE_DURATION, stage="scoring"):
            try:
                # Implementation to be migrated from bin/score 2.py
                engine = RuleEngine()
                score = engine.evaluate(business)

                # Categorize the score for metrics
                score_range = (
                    "low" if score < 30 else "medium" if score < 70 else "high"
                )

                # Record in metrics
                LEADS_SCORED.labels(score_range=score_range).inc()

                logger.info(
                    f"Successfully scored business {business_name}: {score} points ({score_range})",
                    extra={
                        "score": score,
                        "score_range": score_range,
                        "outcome": "success",
                    },
                )
                return score

            except Exception as e:
                # Record error in metrics
                PIPELINE_ERRORS.labels(
                    stage="scoring", error_type=type(e).__name__
                ).inc()

                logger.error(
                    f"Failed to score business {business_name}: {str(e)}",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "outcome": "failure",
                    },
                )
                return 0


@log_execution_time
def get_businesses_to_score(
    limit: Optional[int] = None, business_id: Optional[int] = None
) -> list[dict[str, Any]]:
    """
    Get list of businesses to score.

    Args:
        limit: Maximum number of businesses to return.
        business_id: Specific business ID to return.

    Returns:
        List of businesses to score.
    """
    logger.info(
        "Retrieving businesses to score",
        extra={
            "limit": limit,
            "business_id": business_id,
            "operation": "get_businesses",
        },
    )

    try:
        # Implementation to be migrated from bin/score 2.py
        # Mock implementation for demonstration
        businesses = []

        if business_id:
            businesses = [
                {
                    "id": business_id,
                    "name": f"Business {business_id}",
                    "data": {"mock": "data"},
                }
            ]
        else:
            # Generate mock businesses
            count = limit or 5
            businesses = [
                {"id": i, "name": f"Business {i}", "data": {"mock": "data"}}
                for i in range(1, count + 1)
            ]

        logger.info(
            f"Retrieved {len(businesses)} businesses to score",
            extra={"count": len(businesses)},
        )
        return businesses

    except Exception as e:
        logger.error(
            f"Error retrieving businesses to score: {str(e)}",
            extra={"error_type": type(e).__name__, "error_message": str(e)},
        )
        return []


@log_execution_time
def save_business_score(business_id: int, score: int) -> bool:
    """
    Save business score to database.

    Args:
        business_id: Business ID.
        score: Score value.

    Returns:
        True if successful, False otherwise.
    """
    with LogContext(logger, business_id=business_id, score=score):
        logger.info(
            f"Saving score {score} for business {business_id}",
            extra={"operation": "save_score"},
        )

        try:
            # Implementation to be migrated from bin/score 2.py
            # Mock implementation for demonstration
            # In a real implementation, this would save to a database

            # Simulating successful save
            logger.info(
                f"Successfully saved score for business {business_id}",
                extra={"outcome": "success"},
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to save score for business {business_id}: {str(e)}",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "outcome": "failure",
                },
            )
            return False


def main() -> int:
    """
    Main function for the scoring module.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(description="Score business data")
    parser.add_argument(
        "--limit", type=int, help="Limit the number of businesses to process"
    )
    parser.add_argument("--id", type=int, help="Process only the specified business ID")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level",
    )

    args = parser.parse_args()

    # Configure log level if specified
    if args.log_level:
        logger.setLevel(args.log_level)

    try:
        # Start the process with structured logging
        batch_id = f"score_batch_{int(time.time())}"

        logger.info(
            "Starting scoring process",
            extra={
                "cli_args": vars(args),
                "operation": "cli_score",
                "batch_id": batch_id,
            },
        )

        # Use MetricsTimer for the entire scoring batch process
        with MetricsTimer(PIPELINE_DURATION, stage="score_batch"):
            # Get businesses to score
            businesses = get_businesses_to_score(
                limit=args.limit,
                business_id=args.id,
            )

            logger.info(
                f"Found {len(businesses)} businesses to score",
                extra={"business_count": len(businesses), "batch_id": batch_id},
            )

            # Score businesses
            count = 0
            for business in businesses:
                score = score_business(business)
                if save_business_score(business["id"], score):
                    count += 1

            # Log result with structured data
            success_rate = count / len(businesses) if businesses else 0
            logger.info(
                f"Completed scoring process: {count}/{len(businesses)} businesses successfully scored",
                extra={
                    "businesses_scored": count,
                    "total_businesses": len(businesses),
                    "success_rate": success_rate,
                    "batch_id": batch_id,
                },
            )

        return 0 if count > 0 else 1

    except Exception as e:
        # Log any unexpected errors
        logger.error(
            f"Scoring process failed with unexpected error: {str(e)}",
            extra={"error_type": type(e).__name__, "error_message": str(e)},
        )
        return 1
