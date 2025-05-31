"""
Unified deduplication module using the unified Postgres connector.

This module handles the identification and merging of duplicate business records
using the unified database connector from leadfactory.utils.e2e_db_connector.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import Levenshtein
import requests

# Import configuration
from leadfactory.config.dedupe_config import DedupeConfig, load_dedupe_config

# Import conflict resolution
from leadfactory.pipeline.conflict_resolution import (
    ConflictResolver,
    ConflictType,
    ResolutionStrategy,
)
from leadfactory.pipeline.data_preservation import (
    DataPreservationManager,
    with_data_preservation,
)
from leadfactory.pipeline.dedupe_logging import (
    DedupeLogger,
    dedupe_operation,
    log_dedupe_performance,
)

# Import storage abstraction
from leadfactory.storage.factory import get_storage

# Import from unified connector
from leadfactory.utils.e2e_db_connector import (
    check_dedupe_tables_exist,
    create_dedupe_tables,
    get_potential_duplicate_pairs,
    merge_business_records,
    update_business_fields,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize enhanced dedupe logger
dedupe_logger = DedupeLogger("unified")


class LevenshteinMatcher:
    """Matcher using Levenshtein distance for string similarity."""

    def __init__(self, threshold: float = 0.85):
        """Initialize the matcher with a similarity threshold."""
        self.threshold = threshold

    def calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity score between two strings."""
        if not str1 or not str2:
            return 0.0

        # Normalize strings
        str1 = str1.lower().strip()
        str2 = str2.lower().strip()

        # Calculate Levenshtein distance
        distance = Levenshtein.distance(str1, str2)
        max_len = max(len(str1), len(str2))

        if max_len == 0:
            return 1.0

        # Convert distance to similarity score
        similarity = 1.0 - (distance / max_len)
        return similarity

    def is_match(self, str1: str, str2: str) -> bool:
        """Check if two strings match based on the threshold."""
        return self.calculate_similarity(str1, str2) >= self.threshold


class OllamaVerifier:
    """Verifier using Ollama LLM for duplicate detection."""

    def __init__(self, config: DedupeConfig):
        """Initialize the verifier with configuration."""
        self.config = config
        self.model = config.llm_model
        self.base_url = config.llm_base_url
        self.api_url = f"{config.llm_base_url}/api/generate"
        self.timeout = config.llm_timeout

    def verify_duplicates(
        self, business1: dict, business2: dict
    ) -> tuple[bool, float, str]:
        """
        Verify if two businesses are duplicates using LLM.

        Returns:
            Tuple of (is_duplicate, confidence, reasoning)
        """
        prompt = self._create_prompt(business1, business2)

        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1,
                },
                timeout=self.timeout,
            )

            if response.status_code == 200:
                result = response.json()
                return self._parse_response(result.get("response", ""))
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return False, 0.0, "API error"

        except Exception as e:
            logger.error(f"Error calling Ollama API: {e}")
            return False, 0.0, f"Error: {str(e)}"

    def _create_prompt(self, business1: dict, business2: dict) -> str:
        """Create a prompt for the LLM to verify duplicates."""
        return f"""
        Analyze if these two businesses are duplicates. Consider name similarity,
        address proximity, phone/email/website matches, and business type.

        Business 1:
        - Name: {business1.get('name', 'N/A')}
        - Phone: {business1.get('phone', 'N/A')}
        - Email: {business1.get('email', 'N/A')}
        - Website: {business1.get('website', 'N/A')}
        - Address: {business1.get('address', 'N/A')}, {business1.get('city', 'N/A')}, {business1.get('state', 'N/A')} {business1.get('zip', 'N/A')}
        - Category: {business1.get('category', 'N/A')}

        Business 2:
        - Name: {business2.get('name', 'N/A')}
        - Phone: {business2.get('phone', 'N/A')}
        - Email: {business2.get('email', 'N/A')}
        - Website: {business2.get('website', 'N/A')}
        - Address: {business2.get('address', 'N/A')}, {business2.get('city', 'N/A')}, {business2.get('state', 'N/A')} {business2.get('zip', 'N/A')}
        - Category: {business2.get('category', 'N/A')}

        Respond in JSON format:
        {{
            "is_duplicate": true/false,
            "confidence": 0.0-1.0,
            "reasoning": "explanation"
        }}
        """

    def _parse_response(self, response: str) -> tuple[bool, float, str]:
        """Parse the LLM response."""
        try:
            # Try to extract JSON from response
            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return (
                    data.get("is_duplicate", False),
                    float(data.get("confidence", 0.0)),
                    data.get("reasoning", "No reasoning provided"),
                )
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")

        # Fallback parsing
        is_duplicate = "duplicate" in response.lower() and "not" not in response.lower()
        confidence = 0.5 if is_duplicate else 0.3
        return is_duplicate, confidence, response[:200]


def apply_conflict_resolution(
    primary: dict[str, Any], secondary: dict[str, Any], config: DedupeConfig
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Apply conflict resolution between two business records.

    Args:
        primary: Primary business record
        secondary: Secondary business record
        config: Deduplication configuration

    Returns:
        Tuple of (updates_to_apply, conflict_report)
    """
    resolver = ConflictResolver(config)

    # Identify conflicts
    conflicts = resolver.identify_conflicts(primary, secondary)

    # Resolve conflicts
    updates = {}
    manual_review_fields = []

    for conflict in conflicts:
        field = conflict["field"]
        strategy = conflict["resolution_strategy"]

        if strategy == ResolutionStrategy.MANUAL_REVIEW:
            manual_review_fields.append(field)
        else:
            # Apply the resolution strategy
            resolved_updates = resolver.resolve_conflicts(
                [conflict], primary, secondary
            )
            updates.update(resolved_updates)

    # Generate report
    conflict_report = resolver.generate_conflict_report(conflicts)
    conflict_report["manual_review_required"] = manual_review_fields

    return updates, conflict_report


def get_potential_duplicates(limit: Optional[int] = None) -> list[dict[str, Any]]:
    """Get potential duplicate pairs from the database."""
    return get_potential_duplicate_pairs(limit)


def get_business_by_id(business_id: int) -> Optional[dict[str, Any]]:
    """Get business details by ID."""
    storage = get_storage()
    return storage.get_business_by_id(business_id)


def merge_businesses(
    primary_id: int, secondary_id: int, config: Optional[DedupeConfig] = None
) -> Optional[dict[str, Any]]:
    """
    Merge two business records using the unified connector with data preservation.

    Args:
        primary_id: ID of the primary (surviving) business
        secondary_id: ID of the secondary (to be merged) business
        config: Deduplication configuration

    Returns:
        Merge result dictionary or None if merge failed
    """
    if not config:
        config = load_dedupe_config()

    preservation_manager = DataPreservationManager()

    # Use enhanced logging context
    with dedupe_operation(
        dedupe_logger,
        "merge_businesses",
        primary_id=primary_id,
        secondary_id=secondary_id,
    ):

        # Create backup before merge
        backup_id = preservation_manager.create_backup(
            business_ids=[primary_id, secondary_id], operation="merge"
        )

        # Log the start of the merge operation
        preservation_manager.log_operation(
            operation_type="merge_start",
            business1_id=primary_id,
            business2_id=secondary_id,
            operation_data={"config": config.__dict__, "backup_id": backup_id},
            status="pending",
        )

        # Create savepoint for transaction
        savepoint_name = f"dedupe_merge_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        preservation_manager.create_transaction_savepoint(savepoint_name)

        try:
            # Get business details
            primary = get_business_by_id(primary_id)
            secondary = get_business_by_id(secondary_id)

            if not primary or not secondary:
                logger.error("One or both businesses not found")
                dedupe_logger.log_merge_decision(
                    primary_id, secondary_id, "failed", 0.0, reason="Business not found"
                )
                preservation_manager.log_operation(
                    operation_type="merge_failed",
                    business1_id=primary_id,
                    business2_id=secondary_id,
                    operation_data={"reason": "Business not found"},
                    status="failed",
                )
                return None

            # Apply conflict resolution
            updates, conflict_report = apply_conflict_resolution(
                primary, secondary, config
            )

            # Log conflict resolution results
            logger.info(
                f"Conflict resolution for merge {secondary_id} -> {primary_id}: "
                f"{conflict_report['total_conflicts']} conflicts, "
                f"{len(updates)} updates to apply"
            )

            # Log each conflict
            for conflict in conflict_report.get("conflicts", []):
                dedupe_logger.log_conflict(
                    field=conflict["field"],
                    primary_value=conflict["primary_value"],
                    secondary_value=conflict["secondary_value"],
                    resolution_strategy=conflict["resolution_strategy"],
                    resolved_value=conflict["resolved_value"],
                )

            # Check if manual review is required
            if conflict_report.get("manual_review_required"):
                logger.warning(
                    f"Manual review required for {len(conflict_report['manual_review_required'])} fields"
                )
                dedupe_logger.log_merge_decision(
                    primary_id,
                    secondary_id,
                    "manual_review_required",
                    0.5,
                    fields_requiring_review=conflict_report["manual_review_required"],
                )

                # Add to review queue
                storage = get_storage()
                review_id = storage.add_to_review_queue(
                    business1_id=primary_id,
                    business2_id=secondary_id,
                    reason=f"Manual review required for fields: {', '.join(conflict_report['manual_review_required'])}",
                    details=json.dumps(conflict_report),
                )

                preservation_manager.log_operation(
                    operation_type="manual_review_queued",
                    business1_id=primary_id,
                    business2_id=secondary_id,
                    operation_data={
                        "review_id": review_id,
                        "fields": conflict_report["manual_review_required"],
                    },
                    status="pending_review",
                )

                # Don't proceed with automatic merge if manual review is required
                if config.require_manual_review:
                    preservation_manager.release_savepoint(savepoint_name)
                    return {
                        "status": "manual_review_required",
                        "review_id": review_id,
                        "conflict_report": conflict_report,
                    }

            # Apply updates to primary business
            if updates:
                success = update_business_fields(primary_id, updates)
                if not success:
                    logger.error(f"Failed to update business {primary_id}")
                    dedupe_logger.log_merge_decision(
                        primary_id,
                        secondary_id,
                        "update_failed",
                        0.0,
                        reason="Failed to update primary business",
                    )
                    preservation_manager.rollback_to_savepoint(savepoint_name)
                    preservation_manager.log_operation(
                        operation_type="merge_failed",
                        business1_id=primary_id,
                        business2_id=secondary_id,
                        operation_data={"reason": "Update failed"},
                        status="failed",
                    )
                    return None

            # Perform the merge using unified connector
            result = merge_business_records(primary_id, secondary_id)

            if not result:
                logger.error(f"Failed to merge records {secondary_id} -> {primary_id}")
                dedupe_logger.log_merge_decision(
                    primary_id,
                    secondary_id,
                    "merge_failed",
                    0.0,
                    reason="Database merge operation failed",
                )
                preservation_manager.rollback_to_savepoint(savepoint_name)
                preservation_manager.log_operation(
                    operation_type="merge_failed",
                    business1_id=primary_id,
                    business2_id=secondary_id,
                    operation_data={"reason": "Merge operation failed"},
                    status="failed",
                )
                return None

            # Release savepoint on success
            preservation_manager.release_savepoint(savepoint_name)

            # Log successful merge
            preservation_manager.log_operation(
                operation_type="merge_complete",
                business1_id=primary_id,
                business2_id=secondary_id,
                operation_data={
                    "backup_id": backup_id,
                    "updates_applied": len(updates),
                    "conflicts_resolved": conflict_report["total_conflicts"],
                },
                status="success",
            )

            logger.info(
                f"Successfully merged business {secondary_id} into {primary_id}"
            )
            dedupe_logger.log_merge_decision(
                primary_id,
                secondary_id,
                "merged",
                1.0,
                updates_applied=len(updates),
                conflicts_resolved=conflict_report["total_conflicts"],
            )

            return result

        except Exception as e:
            logger.error(f"Error during merge: {str(e)}")
            # Rollback to savepoint
            preservation_manager.rollback_to_savepoint(savepoint_name)
            preservation_manager.log_operation(
                operation_type="merge_error",
                business1_id=primary_id,
                business2_id=secondary_id,
                operation_data={"error": str(e), "backup_id": backup_id},
                status="error",
            )
            raise


def select_primary_business(
    business1: dict, business2: dict, config: DedupeConfig
) -> tuple[int, int]:
    """
    Select which business should be primary based on data quality.

    Returns:
        Tuple of (primary_id, secondary_id)
    """
    # Calculate completeness scores
    score1 = calculate_completeness_score(business1, config)
    score2 = calculate_completeness_score(business2, config)

    # Check source priority
    priority1 = config.source_priorities.get(business1.get("source", ""), 0)
    priority2 = config.source_priorities.get(business2.get("source", ""), 0)

    # Decide based on source priority first, then completeness
    if priority1 > priority2:
        return business1["id"], business2["id"]
    elif priority2 > priority1:
        return business2["id"], business1["id"]
    elif score1 >= score2:
        return business1["id"], business2["id"]
    else:
        return business2["id"], business1["id"]


def calculate_completeness_score(business: dict, config: DedupeConfig) -> int:
    """Calculate how complete a business record is."""
    score = 0

    for field in config.matching_fields:
        if business.get(field):
            score += 1

    # Extra points for having response data
    if (
        business.get("google_response")
        or business.get("yelp_response")
        or business.get("manual_response")
    ):
        score += 2

    return score


def flag_for_review(
    business1_id: int, business2_id: int, reason: str, similarity_score: float = 0.0
) -> bool:
    """Flag a potential duplicate pair for manual review."""
    storage = get_storage()
    review_id = storage.add_to_review_queue(
        business1_id=business1_id,
        business2_id=business2_id,
        reason=reason,
        details=json.dumps({"similarity_score": similarity_score}),
    )
    return review_id is not None


def process_duplicate_pair(
    pair: dict,
    matcher: LevenshteinMatcher,
    config: DedupeConfig,
    verifier: Optional[OllamaVerifier] = None,
) -> bool:
    """
    Process a single duplicate pair.

    Returns:
        True if successfully processed, False otherwise
    """
    business1_id = pair["business1_id"]
    business2_id = pair["business2_id"]

    # Initialize tracking flags
    pair["merged"] = False
    pair["flagged"] = False

    # Get full business details
    business1 = get_business_by_id(business1_id)
    business2 = get_business_by_id(business2_id)

    if not business1 or not business2:
        logger.error(
            f"Could not fetch business details for pair {business1_id}, {business2_id}"
        )
        return False

    # Check name similarity
    name_similarity = matcher.calculate_similarity(
        business1.get("name", ""), business2.get("name", "")
    )

    # Log duplicate found
    dedupe_logger.log_duplicate_found(
        business1_id,
        business2_id,
        name_similarity,
        "name_similarity",
        business1_name=business1.get("name"),
        business2_name=business2.get("name"),
    )

    # Use LLM verification if available
    if verifier and config.use_llm_verification:
        is_duplicate, confidence, reasoning = verifier.verify_duplicates(
            business1, business2
        )
        logger.info(
            f"LLM verification: is_duplicate={is_duplicate}, confidence={confidence}, reasoning={reasoning}"
        )

        if not is_duplicate and confidence > config.llm_confidence_threshold:
            # High confidence they're not duplicates
            return True

        if (
            is_duplicate
            and confidence < config.low_confidence_threshold
            and config.auto_flag_low_confidence
        ):
            # Low confidence, flag for review
            flag_for_review(
                business1_id,
                business2_id,
                f"Low confidence duplicate: {reasoning}",
                name_similarity,
            )
            pair["flagged"] = True
            return True

    # Check for exact matches
    if (
        (business1.get("phone") and business1["phone"] == business2.get("phone"))
        or (business1.get("email") and business1["email"] == business2.get("email"))
        or (
            business1.get("website")
            and business1["website"] == business2.get("website")
        )
    ):
        # Definite duplicate
        primary_id, secondary_id = select_primary_business(business1, business2, config)
        result = merge_businesses(primary_id, secondary_id, config)
        if result:
            pair["merged"] = True
            dedupe_logger.log_duplicate_found(
                business1_id,
                business2_id,
                1.0,
                "exact_match",
                match_field="phone/email/website",
            )
        return True

    # Check for same name but different address
    if (
        name_similarity > 0.9
        and business1.get("address") != business2.get("address")
        and config.flag_same_name_different_address
    ):
        # Could be chain locations
        flag_for_review(
            business1_id,
            business2_id,
            "Same name but different addresses",
            name_similarity,
        )
        pair["flagged"] = True
        dedupe_logger.log_duplicate_found(
            business1_id,
            business2_id,
            name_similarity,
            "possible_chain",
            reason="Same name but different addresses",
        )
        return True

    # High name similarity with other matching fields
    if name_similarity > matcher.threshold:
        primary_id, secondary_id = select_primary_business(business1, business2, config)
        result = merge_businesses(primary_id, secondary_id, config)
        if result:
            pair["merged"] = True
            dedupe_logger.log_duplicate_found(
                business1_id,
                business2_id,
                name_similarity,
                "high_similarity",
                threshold=matcher.threshold,
            )
        return True

    return True


@log_dedupe_performance(dedupe_logger)
def deduplicate(
    config: Optional[DedupeConfig] = None,
    limit: Optional[int] = None,
    use_optimized: bool = True,
) -> dict[str, int]:
    """
    Run the deduplication process.

    Args:
        config: Deduplication configuration (uses default if None)
        limit: Maximum number of duplicate pairs to process
        use_optimized: Whether to use optimized processing (default: True)

    Returns:
        Dictionary with counts of processed, merged, and flagged pairs
    """
    # Use optimized version if requested and available
    if use_optimized:
        try:
            from leadfactory.pipeline.dedupe_performance import (
                run_optimized_deduplication,
            )

            logger.info("Using optimized deduplication processing...")
            result = run_optimized_deduplication(config, limit)
            return result["stats"]
        except ImportError:
            logger.warning(
                "Optimized deduplication not available, falling back to standard processing"
            )
        except Exception as e:
            logger.error(
                f"Error in optimized deduplication: {e}, falling back to standard processing"
            )

    # Fall back to standard processing
    logger.info("Using standard deduplication processing...")
    # Use provided config or load default
    if config is None:
        config = load_dedupe_config()

    # Override limit if specified in config
    if limit is None and config.max_pairs_per_run:
        limit = config.max_pairs_per_run

    # Start dedupe operation tracking
    with dedupe_operation(
        dedupe_logger,
        "full_deduplication",
        limit=limit,
        config_name=config.name if hasattr(config, "name") else "default",
    ):

        # Ensure dedupe tables exist
        if not check_dedupe_tables_exist():
            logger.info("Creating dedupe tables...")
            dedupe_logger.start_operation("create_tables")
            if not create_dedupe_tables():
                logger.error("Failed to create dedupe tables")
                dedupe_logger.end_operation("create_tables", status="failure")
                return {"processed": 0, "merged": 0, "flagged": 0, "errors": 0}
            dedupe_logger.end_operation("create_tables", status="success")

        # Initialize components
        matcher = LevenshteinMatcher(threshold=config.name_similarity_threshold)
        verifier = OllamaVerifier(config) if config.use_llm_verification else None

        # Get potential duplicates
        find_op = dedupe_logger.start_operation("find_duplicates", limit=limit)
        duplicates = get_potential_duplicates(limit)
        dedupe_logger.end_operation(find_op, duplicate_count=len(duplicates))
        logger.info(f"Found {len(duplicates)} potential duplicate pairs")

        # Process each pair
        stats = {"processed": 0, "merged": 0, "flagged": 0, "errors": 0}
        batch_id = f"batch_{int(time.time())}"

        for i, pair in enumerate(duplicates):
            try:
                # Log batch progress every 10 items
                if i % 10 == 0:
                    dedupe_logger.log_batch_progress(
                        batch_id=batch_id,
                        processed=i,
                        total=len(duplicates),
                        errors=stats["errors"],
                        merged=stats["merged"],
                        flagged=stats["flagged"],
                    )

                # Process the pair
                process_op = dedupe_logger.start_operation(
                    "process_pair",
                    business1_id=pair.get("business1_id"),
                    business2_id=pair.get("business2_id"),
                )

                if process_duplicate_pair(pair, matcher, config, verifier):
                    stats["processed"] += 1
                    # Check if it was merged or flagged
                    if pair.get("merged"):
                        stats["merged"] += 1
                    elif pair.get("flagged"):
                        stats["flagged"] += 1
                    dedupe_logger.end_operation(process_op, status="success")
                else:
                    stats["errors"] += 1
                    dedupe_logger.end_operation(process_op, status="failure")

            except Exception as e:
                logger.error(
                    f"Error processing pair {pair.get('business1_id')}, {pair.get('business2_id')}: {e}"
                )
                stats["errors"] += 1
                dedupe_logger.end_operation(process_op, status="error", error=str(e))

        # Final batch progress
        dedupe_logger.log_batch_progress(
            batch_id=batch_id,
            processed=len(duplicates),
            total=len(duplicates),
            errors=stats["errors"],
            merged=stats["merged"],
            flagged=stats["flagged"],
        )

        # Log final metrics
        dedupe_logger.logger.info(
            "Deduplication complete",
            extra={
                "event_type": "deduplication_summary",
                "total_pairs": len(duplicates),
                "processed": stats["processed"],
                "merged": stats["merged"],
                "flagged": stats["flagged"],
                "errors": stats["errors"],
                "success_rate": (
                    (stats["processed"] / len(duplicates) * 100) if duplicates else 0
                ),
            },
        )

        logger.info(f"Deduplication complete: {stats}")
        return stats


def main():
    """Main entry point for the dedupe script."""
    parser = argparse.ArgumentParser(description="Deduplicate business records")
    parser.add_argument(
        "--limit", type=int, help="Limit number of duplicates to process"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.85, help="Similarity threshold (0-1)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without making changes"
    )
    parser.add_argument(
        "--use-llm", action="store_true", help="Use LLM for verification"
    )
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument(
        "--no-optimize", action="store_true", help="Disable performance optimizations"
    )

    args = parser.parse_args()

    # Load configuration
    config = load_dedupe_config(args.config)

    # Override config with command line arguments
    if args.threshold:
        config.name_similarity_threshold = args.threshold
    if args.dry_run:
        config.dry_run = True
    if args.use_llm:
        config.use_llm_verification = True

    # Run deduplication
    stats = deduplicate(
        config=config, limit=args.limit, use_optimized=not args.no_optimize
    )

    # Exit with error code if there were errors
    if stats["errors"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
