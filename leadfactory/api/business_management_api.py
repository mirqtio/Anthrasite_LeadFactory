"""Business management API endpoints for bulk operations."""

from typing import List, Optional

from flask import Blueprint, jsonify, request

from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)

business_management = Blueprint("business_management", __name__)


@business_management.route("/api/businesses/bulk-reject", methods=["POST"])
def bulk_reject_businesses():
    """Archive selected businesses and hide them from default view.

    Request body should contain:
    {
        "business_ids": [1, 2, 3],
        "reason": "irrelevant" (optional)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        business_ids = data.get("business_ids", [])
        reason = data.get("reason", "manual_reject")

        if not business_ids:
            return jsonify({"error": "business_ids is required"}), 400

        if not isinstance(business_ids, list):
            return jsonify({"error": "business_ids must be a list"}), 400

        # Validate all IDs are integers
        try:
            business_ids = [int(bid) for bid in business_ids]
        except (ValueError, TypeError):
            return jsonify({"error": "All business_ids must be valid integers"}), 400

        storage = get_storage_instance()

        # Archive businesses
        archived_count = 0
        failed_ids = []

        for business_id in business_ids:
            try:
                # Check if business exists
                business = storage.get_business_by_id(business_id)
                if not business:
                    failed_ids.append(business_id)
                    continue

                # Archive the business
                success = storage.archive_business(business_id, reason)
                if success:
                    archived_count += 1
                    logger.info(
                        f"Archived business {business_id} with reason: {reason}"
                    )
                else:
                    failed_ids.append(business_id)
                    logger.warning(f"Failed to archive business {business_id}")

            except Exception as e:
                logger.error(f"Error archiving business {business_id}: {e}")
                failed_ids.append(business_id)

        response = {
            "success": True,
            "archived_count": archived_count,
            "total_requested": len(business_ids),
            "failed_ids": failed_ids,
        }

        if failed_ids:
            response["message"] = (
                f"Archived {archived_count} businesses, {len(failed_ids)} failed"
            )
        else:
            response["message"] = f"Successfully archived {archived_count} businesses"

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in bulk_reject_businesses: {e}")
        return jsonify({"error": "Internal server error"}), 500


@business_management.route(
    "/api/businesses/archive-status/<int:business_id>", methods=["GET"]
)
def get_archive_status(business_id: int):
    """Get archive status of a business."""
    try:
        storage = get_storage_instance()
        business = storage.get_business_by_id(business_id)

        if not business:
            return jsonify({"error": "Business not found"}), 404

        is_archived = business.get("archived", False)
        archive_reason = business.get("archive_reason")
        archived_at = business.get("archived_at")

        return jsonify(
            {
                "business_id": business_id,
                "archived": is_archived,
                "archive_reason": archive_reason,
                "archived_at": archived_at,
            }
        )

    except Exception as e:
        logger.error(f"Error getting archive status for business {business_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@business_management.route("/api/businesses/restore", methods=["POST"])
def restore_businesses():
    """Restore archived businesses to active status.

    Request body should contain:
    {
        "business_ids": [1, 2, 3]
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        business_ids = data.get("business_ids", [])

        if not business_ids:
            return jsonify({"error": "business_ids is required"}), 400

        if not isinstance(business_ids, list):
            return jsonify({"error": "business_ids must be a list"}), 400

        # Validate all IDs are integers
        try:
            business_ids = [int(bid) for bid in business_ids]
        except (ValueError, TypeError):
            return jsonify({"error": "All business_ids must be valid integers"}), 400

        storage = get_storage_instance()

        # Restore businesses
        restored_count = 0
        failed_ids = []

        for business_id in business_ids:
            try:
                # Check if business exists
                business = storage.get_business_by_id(business_id)
                if not business:
                    failed_ids.append(business_id)
                    continue

                # Restore the business
                success = storage.restore_business(business_id)
                if success:
                    restored_count += 1
                    logger.info(f"Restored business {business_id}")
                else:
                    failed_ids.append(business_id)
                    logger.warning(f"Failed to restore business {business_id}")

            except Exception as e:
                logger.error(f"Error restoring business {business_id}: {e}")
                failed_ids.append(business_id)

        response = {
            "success": True,
            "restored_count": restored_count,
            "total_requested": len(business_ids),
            "failed_ids": failed_ids,
        }

        if failed_ids:
            response["message"] = (
                f"Restored {restored_count} businesses, {len(failed_ids)} failed"
            )
        else:
            response["message"] = f"Successfully restored {restored_count} businesses"

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in restore_businesses: {e}")
        return jsonify({"error": "Internal server error"}), 500


@business_management.route("/api/businesses", methods=["GET"])
def list_businesses():
    """List businesses with optional filtering.

    Query parameters:
    - include_archived: true/false (default: false)
    - limit: number of results (default: 50)
    - offset: pagination offset (default: 0)
    - search: search term for name/address
    """
    try:
        include_archived = (
            request.args.get("include_archived", "false").lower() == "true"
        )
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
        search = request.args.get("search", "")

        storage = get_storage_instance()

        # Get businesses with filtering
        businesses = storage.list_businesses(
            include_archived=include_archived, limit=limit, offset=offset, search=search
        )

        # Get total count for pagination
        total_count = storage.count_businesses(
            include_archived=include_archived, search=search
        )

        return jsonify(
            {
                "businesses": businesses,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "include_archived": include_archived,
            }
        )

    except ValueError as e:
        return jsonify({"error": f"Invalid parameter: {e}"}), 400
    except Exception as e:
        logger.error(f"Error listing businesses: {e}")
        return jsonify({"error": "Internal server error"}), 500
