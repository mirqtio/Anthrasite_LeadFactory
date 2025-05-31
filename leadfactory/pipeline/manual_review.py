"""
Manual review interface for deduplication conflicts.

This module provides functionality for handling manual review of
conflicts that cannot be automatically resolved.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from leadfactory.storage import get_storage

logger = logging.getLogger(__name__)


class ManualReviewManager:
    """Manages manual review processes for deduplication conflicts."""

    def __init__(self):
        """Initialize the manual review manager."""
        self.pending_reviews = []
        self.storage = get_storage()

    def create_review_request(
        self,
        primary_id: int,
        secondary_id: int,
        conflicts: list[dict[str, Any]],
        conflict_report: dict[str, Any],
    ) -> Optional[int]:
        """
        Create a manual review request for conflicting records.

        Args:
            primary_id: ID of the primary business
            secondary_id: ID of the secondary business
            conflicts: List of conflicts requiring review
            conflict_report: Full conflict report

        Returns:
            Review request ID or None if failed
        """
        review_data = {
            "primary_id": primary_id,
            "secondary_id": secondary_id,
            "conflicts": conflicts,
            "conflict_report": conflict_report,
            "created_at": datetime.now().isoformat(),
            "status": "pending",
        }

        # Add to review queue with detailed information
        reason = f"Manual review required for {len(conflicts)} conflicts"
        details = json.dumps(review_data)

        try:
            review_id = self.storage.add_to_review_queue(
                primary_id, secondary_id, reason=reason, details=details
            )
            logger.info(f"Created manual review request {review_id}")
            return review_id
        except Exception as e:
            logger.error(f"Failed to create review request: {e}")
            return None

    def get_pending_reviews(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get pending manual review requests.

        Args:
            limit: Maximum number of reviews to retrieve

        Returns:
            List of pending review requests
        """
        try:
            reviews = self.storage.get_review_queue_items(status="pending", limit=limit)

            # Parse the details JSON for each review
            for review in reviews:
                if review.get("details"):
                    try:
                        review["parsed_details"] = json.loads(review["details"])
                    except json.JSONDecodeError:
                        review["parsed_details"] = {}

            return reviews
        except Exception as e:
            logger.error(f"Failed to get pending reviews: {e}")
            return []

    def format_review_for_display(self, review: dict[str, Any]) -> str:
        """
        Format a review request for human-readable display.

        Args:
            review: Review request data

        Returns:
            Formatted string for display
        """
        output = []
        output.append(f"Review ID: {review.get('id', 'N/A')}")
        output.append(f"Primary Business ID: {review.get('business1_id', 'N/A')}")
        output.append(f"Secondary Business ID: {review.get('business2_id', 'N/A')}")
        output.append(f"Reason: {review.get('reason', 'N/A')}")
        output.append(f"Created: {review.get('created_at', 'N/A')}")
        output.append("")

        # Display conflicts if available
        details = review.get("parsed_details", {})
        conflicts = details.get("conflicts", [])

        if conflicts:
            output.append("Conflicts:")
            output.append("-" * 50)
            for conflict in conflicts:
                output.append(f"Field: {conflict['field']}")
                output.append(f"  Primary value: {conflict['primary_value']}")
                output.append(f"  Secondary value: {conflict['secondary_value']}")
                output.append(
                    f"  Conflict type: {conflict['type'].value if hasattr(conflict['type'], 'value') else conflict['type']}"
                )
                output.append("")

        return "\n".join(output)

    def resolve_review(
        self, review_id: int, resolutions: dict[str, Any], merge_decision: str
    ) -> bool:
        """
        Resolve a manual review with user decisions.

        Args:
            review_id: ID of the review to resolve
            resolutions: Dictionary of field resolutions
            merge_decision: 'merge', 'keep_separate', or 'defer'

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update review status
            resolution_data = {
                "resolutions": resolutions,
                "merge_decision": merge_decision,
                "resolved_at": datetime.now().isoformat(),
            }

            status = "resolved" if merge_decision != "defer" else "deferred"

            success = self.storage.update_review_status(
                review_id, status=status, resolution=json.dumps(resolution_data)
            )

            if success:
                logger.info(
                    f"Resolved review {review_id} with decision: {merge_decision}"
                )
            else:
                logger.error(f"Failed to update review {review_id} status")

            return success

        except Exception as e:
            logger.error(f"Failed to resolve review {review_id}: {e}")
            return False

    def get_review_statistics(self) -> dict[str, Any]:
        """
        Get statistics about manual reviews.

        Returns:
            Dictionary of review statistics
        """
        try:
            return self.storage.get_review_statistics()
        except Exception as e:
            logger.error(f"Failed to get review statistics: {e}")
            return {}

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.0f} seconds"
        elif seconds < 3600:
            return f"{seconds/60:.1f} minutes"
        elif seconds < 86400:
            return f"{seconds/3600:.1f} hours"
        else:
            return f"{seconds/86400:.1f} days"


def interactive_review_session():
    """
    Run an interactive manual review session.

    This is a simple CLI interface for reviewing conflicts.
    """
    manager = ManualReviewManager()

    # Get pending reviews
    reviews = manager.get_pending_reviews(limit=5)

    if not reviews:
        return

    for review in reviews:

        # Get user decision

        choice = input("\nEnter your choice (1-5): ").strip()

        if choice == "5":
            break
        elif choice == "4":
            continue
        elif choice in ["1", "2", "3"]:
            merge_decision = {"1": "merge", "2": "keep_separate", "3": "defer"}[choice]

            # For now, we'll use empty resolutions
            # In a real implementation, we'd collect field-by-field decisions
            resolutions = {}

            success = manager.resolve_review(review["id"], resolutions, merge_decision)

            if success:
                pass
            else:
                pass

    # Show statistics
    manager.get_review_statistics()


if __name__ == "__main__":
    # Run interactive review session if called directly
    interactive_review_session()
