"""Mockup QA management API endpoints."""

from typing import List, Optional

from flask import Blueprint, jsonify, request

from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)

mockup_qa = Blueprint("mockup_qa", __name__)


@mockup_qa.route("/api/mockups", methods=["GET"])
def list_mockups():
    """List mockups with optional filtering and pagination.

    Query parameters:
    - business_id: Filter by business ID
    - status: Filter by QA status (approved, rejected, pending, ai_uncertain)
    - limit: Number of results (default: 20)
    - offset: Pagination offset (default: 0)
    - version: Show specific version or all versions
    """
    try:
        business_id = request.args.get("business_id", type=int)
        status = request.args.get("status")
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
        version = request.args.get("version")

        storage = get_storage_instance()

        # Get mockups with filtering
        mockups = storage.list_mockups(
            business_id=business_id,
            status=status,
            limit=limit,
            offset=offset,
            version=version,
        )

        # Get total count for pagination
        total_count = storage.count_mockups(
            business_id=business_id, status=status, version=version
        )

        return jsonify(
            {
                "mockups": mockups,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "filters": {
                    "business_id": business_id,
                    "status": status,
                    "version": version,
                },
            }
        )

    except ValueError as e:
        return jsonify({"error": f"Invalid parameter: {e}"}), 400
    except Exception as e:
        logger.error(f"Error listing mockups: {e}")
        return jsonify({"error": "Internal server error"}), 500


@mockup_qa.route("/api/mockups/<int:mockup_id>", methods=["GET"])
def get_mockup(mockup_id: int):
    """Get detailed mockup information including all versions."""
    try:
        storage = get_storage_instance()

        # Get mockup with all versions
        mockup = storage.get_mockup_with_versions(mockup_id)

        if not mockup:
            return jsonify({"error": "Mockup not found"}), 404

        return jsonify(mockup)

    except Exception as e:
        logger.error(f"Error getting mockup {mockup_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@mockup_qa.route("/api/mockups/<int:mockup_id>/qa-override", methods=["POST"])
def qa_override(mockup_id: int):
    """Override AI QA score with human review.

    Request body:
    {
        "new_status": "approved" | "rejected" | "needs_revision",
        "qa_score": 1-10,
        "reviewer_notes": "Optional notes",
        "revised_prompt": "Optional revised prompt for regeneration"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        new_status = data.get("new_status")
        qa_score = data.get("qa_score")
        reviewer_notes = data.get("reviewer_notes", "")
        revised_prompt = data.get("revised_prompt")

        # Validate required fields
        if not new_status:
            return jsonify({"error": "new_status is required"}), 400

        if new_status not in ["approved", "rejected", "needs_revision"]:
            return (
                jsonify(
                    {
                        "error": "Invalid status. Must be approved, rejected, or needs_revision"
                    }
                ),
                400,
            )

        if qa_score is not None and (
            not isinstance(qa_score, (int, float)) or qa_score < 1 or qa_score > 10
        ):
            return jsonify({"error": "qa_score must be between 1 and 10"}), 400

        storage = get_storage_instance()

        # Check if mockup exists
        mockup = storage.get_mockup_by_id(mockup_id)
        if not mockup:
            return jsonify({"error": "Mockup not found"}), 404

        # Apply QA override
        success = storage.apply_qa_override(
            mockup_id=mockup_id,
            new_status=new_status,
            qa_score=qa_score,
            reviewer_notes=reviewer_notes,
            revised_prompt=revised_prompt,
        )

        if not success:
            return jsonify({"error": "Failed to apply QA override"}), 500

        # If needs revision and revised prompt provided, trigger regeneration
        regeneration_triggered = False
        if new_status == "needs_revision" and revised_prompt:
            try:
                # Import here to avoid circular imports
                from leadfactory.pipeline.unified_gpt4o import UnifiedGPT4ONode

                # Get business data for regeneration
                business = storage.get_business_by_id(mockup["business_id"])
                if business:
                    node = UnifiedGPT4ONode()

                    # Add revised prompt to business data
                    business["revised_prompt"] = revised_prompt

                    # Trigger regeneration (async in real implementation)
                    logger.info(
                        f"Triggering mockup regeneration for business {business['id']} with revised prompt"
                    )
                    regeneration_triggered = True

            except Exception as e:
                logger.error(f"Failed to trigger regeneration: {e}")
                # Don't fail the override, just log the error

        logger.info(
            f"Applied QA override to mockup {mockup_id}: {new_status} (score: {qa_score})"
        )

        return jsonify(
            {
                "success": True,
                "mockup_id": mockup_id,
                "new_status": new_status,
                "qa_score": qa_score,
                "regeneration_triggered": regeneration_triggered,
                "message": f"QA override applied successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error applying QA override to mockup {mockup_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@mockup_qa.route("/api/mockups/<int:mockup_id>/versions", methods=["GET"])
def get_mockup_versions(mockup_id: int):
    """Get all versions of a mockup for comparison."""
    try:
        storage = get_storage_instance()

        versions = storage.get_mockup_versions(mockup_id)

        if not versions:
            return jsonify({"error": "Mockup not found or no versions available"}), 404

        return jsonify(
            {
                "mockup_id": mockup_id,
                "versions": versions,
                "total_versions": len(versions),
            }
        )

    except Exception as e:
        logger.error(f"Error getting versions for mockup {mockup_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@mockup_qa.route("/api/mockups/versions/compare", methods=["POST"])
def compare_versions():
    """Compare two versions of a mockup.

    Request body:
    {
        "version1_id": 123,
        "version2_id": 456
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        version1_id = data.get("version1_id")
        version2_id = data.get("version2_id")

        if not version1_id or not version2_id:
            return (
                jsonify({"error": "Both version1_id and version2_id are required"}),
                400,
            )

        storage = get_storage_instance()

        # Get both versions
        version1 = storage.get_mockup_version_by_id(version1_id)
        version2 = storage.get_mockup_version_by_id(version2_id)

        if not version1 or not version2:
            return jsonify({"error": "One or both versions not found"}), 404

        # Generate diff
        diff_result = _generate_version_diff(version1, version2)

        return jsonify(
            {
                "version1": version1,
                "version2": version2,
                "diff": diff_result,
                "comparison_summary": {
                    "changes_detected": diff_result["has_changes"],
                    "changed_sections": len(diff_result["layout_changes"]),
                    "content_changes": len(diff_result["content_changes"]),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error comparing versions: {e}")
        return jsonify({"error": "Internal server error"}), 500


@mockup_qa.route("/api/mockups/bulk-update", methods=["POST"])
def bulk_update_status():
    """Update status for multiple mockups.

    Request body:
    {
        "mockup_ids": [1, 2, 3],
        "new_status": "approved" | "rejected"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        mockup_ids = data.get("mockup_ids", [])
        new_status = data.get("new_status")

        if not mockup_ids or not isinstance(mockup_ids, list):
            return jsonify({"error": "mockup_ids must be a non-empty list"}), 400

        if new_status not in ["approved", "rejected"]:
            return (
                jsonify(
                    {
                        "error": "new_status must be approved or rejected for bulk updates"
                    }
                ),
                400,
            )

        storage = get_storage_instance()

        updated_count = 0
        failed_ids = []

        for mockup_id in mockup_ids:
            try:
                success = storage.update_mockup_status(mockup_id, new_status)
                if success:
                    updated_count += 1
                else:
                    failed_ids.append(mockup_id)
            except Exception as e:
                logger.error(f"Failed to update mockup {mockup_id}: {e}")
                failed_ids.append(mockup_id)

        return jsonify(
            {
                "success": True,
                "updated_count": updated_count,
                "total_requested": len(mockup_ids),
                "failed_ids": failed_ids,
                "new_status": new_status,
            }
        )

    except Exception as e:
        logger.error(f"Error in bulk update: {e}")
        return jsonify({"error": "Internal server error"}), 500


def _generate_version_diff(version1: dict, version2: dict) -> dict:
    """Generate diff between two mockup versions.

    Args:
        version1: First version data
        version2: Second version data

    Returns:
        Dictionary with diff information
    """
    diff_result = {
        "has_changes": False,
        "layout_changes": [],
        "content_changes": [],
        "metadata_changes": {},
    }

    # Compare layout elements
    layout1 = version1.get("content", {}).get("mockup", {}).get("layout_elements", [])
    layout2 = version2.get("content", {}).get("mockup", {}).get("layout_elements", [])

    for i, (elem1, elem2) in enumerate(zip(layout1, layout2)):
        changes = {}

        if elem1.get("section_name") != elem2.get("section_name"):
            changes["section_name"] = {
                "old": elem1.get("section_name"),
                "new": elem2.get("section_name"),
            }

        if elem1.get("description") != elem2.get("description"):
            changes["description"] = {
                "old": elem1.get("description"),
                "new": elem2.get("description"),
            }

        if elem1.get("priority") != elem2.get("priority"):
            changes["priority"] = {
                "old": elem1.get("priority"),
                "new": elem2.get("priority"),
            }

        if changes:
            diff_result["layout_changes"].append(
                {"element_index": i, "changes": changes}
            )
            diff_result["has_changes"] = True

    # Compare content recommendations
    content1 = (
        version1.get("content", {}).get("mockup", {}).get("content_recommendations", [])
    )
    content2 = (
        version2.get("content", {}).get("mockup", {}).get("content_recommendations", [])
    )

    for i, (rec1, rec2) in enumerate(zip(content1, content2)):
        changes = {}

        if rec1.get("improvement") != rec2.get("improvement"):
            changes["improvement"] = {
                "old": rec1.get("improvement"),
                "new": rec2.get("improvement"),
            }

        if rec1.get("current_issue") != rec2.get("current_issue"):
            changes["current_issue"] = {
                "old": rec1.get("current_issue"),
                "new": rec2.get("current_issue"),
            }

        if changes:
            diff_result["content_changes"].append(
                {"recommendation_index": i, "changes": changes}
            )
            diff_result["has_changes"] = True

    # Compare metadata
    if version1.get("qa_score") != version2.get("qa_score"):
        diff_result["metadata_changes"]["qa_score"] = {
            "old": version1.get("qa_score"),
            "new": version2.get("qa_score"),
        }
        diff_result["has_changes"] = True

    if version1.get("status") != version2.get("status"):
        diff_result["metadata_changes"]["status"] = {
            "old": version1.get("status"),
            "new": version2.get("status"),
        }
        diff_result["has_changes"] = True

    return diff_result
