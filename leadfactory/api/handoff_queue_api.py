"""API endpoints for handoff queue management and bulk qualification.

Implements Feature 5 Extension: TR-4 Bulk Qualify for Handoff.
- Bulk qualification operations
- Queue management endpoints
- Sales team assignment APIs
- Analytics and reporting endpoints
"""

from typing import List, Optional

from flask import Blueprint, jsonify, request

from leadfactory.services.handoff_queue_service import HandoffQueueService
from leadfactory.services.qualification_engine import QualificationEngine
from leadfactory.storage import get_storage_instance
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)

handoff_queue = Blueprint("handoff_queue", __name__)

# Initialize services
queue_service = HandoffQueueService()
qualification_engine = QualificationEngine()


@handoff_queue.route("/api/handoff/qualify-bulk", methods=["POST"])
def bulk_qualify_businesses():
    """Qualify multiple businesses for handoff to sales team.

    Request body should contain:
    {
        "business_ids": [1, 2, 3],
        "criteria_id": 1,
        "force_rescore": false (optional),
        "performed_by": "user123" (optional)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        business_ids = data.get("business_ids", [])
        criteria_id = data.get("criteria_id")
        force_rescore = data.get("force_rescore", False)
        performed_by = data.get("performed_by")

        # Validation
        if not business_ids:
            return jsonify({"error": "business_ids is required"}), 400

        if not isinstance(business_ids, list):
            return jsonify({"error": "business_ids must be a list"}), 400

        if criteria_id is None:
            return jsonify({"error": "criteria_id is required"}), 400

        try:
            business_ids = [int(bid) for bid in business_ids]
            criteria_id = int(criteria_id)
        except (ValueError, TypeError):
            return (
                jsonify(
                    {"error": "business_ids and criteria_id must be valid integers"}
                ),
                400,
            )

        # Check criteria exists
        criteria = qualification_engine.get_criteria_by_id(criteria_id)
        if not criteria:
            return (
                jsonify({"error": f"Qualification criteria {criteria_id} not found"}),
                404,
            )

        if not criteria.is_active:
            return (
                jsonify(
                    {"error": f"Qualification criteria {criteria_id} is not active"}
                ),
                400,
            )

        # Perform bulk qualification
        operation_id = queue_service.bulk_qualify(
            business_ids=business_ids,
            criteria_id=criteria_id,
            performed_by=performed_by,
            force_rescore=force_rescore,
        )

        return (
            jsonify(
                {
                    "success": True,
                    "operation_id": operation_id,
                    "message": f"Bulk qualification started for {len(business_ids)} businesses",
                    "criteria_name": criteria.name,
                    "total_businesses": len(business_ids),
                }
            ),
            202,
        )

    except Exception as e:
        logger.error(f"Error in bulk_qualify_businesses: {e}")
        return jsonify({"error": "Internal server error"}), 500


@handoff_queue.route("/api/handoff/assign-bulk", methods=["POST"])
def bulk_assign_queue_entries():
    """Assign multiple queue entries to a sales team member.

    Request body should contain:
    {
        "queue_entry_ids": [1, 2, 3],
        "assignee_user_id": "sales_rep_1",
        "performed_by": "user123" (optional)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        queue_entry_ids = data.get("queue_entry_ids", [])
        assignee_user_id = data.get("assignee_user_id")
        performed_by = data.get("performed_by")

        # Validation
        if not queue_entry_ids:
            return jsonify({"error": "queue_entry_ids is required"}), 400

        if not isinstance(queue_entry_ids, list):
            return jsonify({"error": "queue_entry_ids must be a list"}), 400

        if not assignee_user_id:
            return jsonify({"error": "assignee_user_id is required"}), 400

        try:
            queue_entry_ids = [int(eid) for eid in queue_entry_ids]
        except (ValueError, TypeError):
            return jsonify({"error": "All queue_entry_ids must be valid integers"}), 400

        # Check assignee exists
        assignee = queue_service.get_sales_team_member(assignee_user_id)
        if not assignee:
            return (
                jsonify({"error": f"Sales team member {assignee_user_id} not found"}),
                404,
            )

        if not assignee.is_active:
            return (
                jsonify(
                    {"error": f"Sales team member {assignee_user_id} is not active"}
                ),
                400,
            )

        # Check capacity
        available_capacity = assignee.max_capacity - assignee.current_capacity
        if len(queue_entry_ids) > available_capacity:
            return (
                jsonify(
                    {
                        "error": f"Assignment would exceed capacity. Available: {available_capacity}, Requested: {len(queue_entry_ids)}"
                    }
                ),
                400,
            )

        # Perform bulk assignment
        operation_id = queue_service.bulk_assign(
            queue_entry_ids=queue_entry_ids,
            assignee_user_id=assignee_user_id,
            performed_by=performed_by,
        )

        return (
            jsonify(
                {
                    "success": True,
                    "operation_id": operation_id,
                    "message": f"Bulk assignment started for {len(queue_entry_ids)} queue entries",
                    "assignee_name": assignee.name,
                    "total_entries": len(queue_entry_ids),
                }
            ),
            202,
        )

    except Exception as e:
        logger.error(f"Error in bulk_assign_queue_entries: {e}")
        return jsonify({"error": "Internal server error"}), 500


@handoff_queue.route("/api/handoff/queue", methods=["GET"])
def list_handoff_queue():
    """List handoff queue entries with filtering.

    Query parameters:
    - status: Filter by status (qualified, assigned, contacted, closed, rejected)
    - assigned_to: Filter by assignee user ID
    - min_priority: Minimum priority threshold
    - limit: Number of results (default: 50)
    - offset: Pagination offset (default: 0)
    """
    try:
        status = request.args.get("status")
        assigned_to = request.args.get("assigned_to")
        min_priority = request.args.get("min_priority")
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))

        if min_priority is not None:
            min_priority = int(min_priority)

        # Get queue entries
        entries = queue_service.list_queue_entries(
            status=status,
            assigned_to=assigned_to,
            min_priority=min_priority,
            limit=limit,
            offset=offset,
        )

        # Convert to dictionaries and enrich with business data
        storage = get_storage_instance()
        enriched_entries = []

        for entry in entries:
            entry_dict = entry.to_dict()

            # Get business data
            business = storage.get_business_by_id(entry.business_id)
            if business:
                entry_dict["business"] = {
                    "id": business["id"],
                    "name": business.get("name"),
                    "email": business.get("email"),
                    "website": business.get("website"),
                    "category": business.get("category"),
                    "score": business.get("score", 0),
                }

            # Get criteria data
            criteria = qualification_engine.get_criteria_by_id(
                entry.qualification_criteria_id
            )
            if criteria:
                entry_dict["criteria"] = {
                    "id": criteria.id,
                    "name": criteria.name,
                    "description": criteria.description,
                }

            # Get assignee data if assigned
            if entry.assigned_to:
                assignee = queue_service.get_sales_team_member(entry.assigned_to)
                if assignee:
                    entry_dict["assignee"] = {
                        "user_id": assignee.user_id,
                        "name": assignee.name,
                        "email": assignee.email,
                        "role": assignee.role,
                    }

            enriched_entries.append(entry_dict)

        return jsonify(
            {
                "entries": enriched_entries,
                "total_count": len(enriched_entries),
                "limit": limit,
                "offset": offset,
                "filters": {
                    "status": status,
                    "assigned_to": assigned_to,
                    "min_priority": min_priority,
                },
            }
        )

    except ValueError as e:
        return jsonify({"error": f"Invalid parameter: {e}"}), 400
    except Exception as e:
        logger.error(f"Error listing handoff queue: {e}")
        return jsonify({"error": "Internal server error"}), 500


@handoff_queue.route("/api/handoff/queue/<int:entry_id>", methods=["GET"])
def get_handoff_queue_entry(entry_id: int):
    """Get a specific handoff queue entry."""
    try:
        entry = queue_service.get_queue_entry(entry_id)
        if not entry:
            return jsonify({"error": "Queue entry not found"}), 404

        # Enrich with related data
        entry_dict = entry.to_dict()
        storage = get_storage_instance()

        # Get business data
        business = storage.get_business_by_id(entry.business_id)
        if business:
            entry_dict["business"] = business

        # Get criteria data
        criteria = qualification_engine.get_criteria_by_id(
            entry.qualification_criteria_id
        )
        if criteria:
            entry_dict["criteria"] = criteria.to_dict()

        # Get assignee data if assigned
        if entry.assigned_to:
            assignee = queue_service.get_sales_team_member(entry.assigned_to)
            if assignee:
                entry_dict["assignee"] = assignee.to_dict()

        return jsonify(entry_dict)

    except Exception as e:
        logger.error(f"Error getting queue entry {entry_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@handoff_queue.route("/api/handoff/queue/<int:entry_id>/assign", methods=["POST"])
def assign_queue_entry(entry_id: int):
    """Assign a queue entry to a sales team member.

    Request body should contain:
    {
        "assignee_user_id": "sales_rep_1",
        "assigned_by": "user123" (optional)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        assignee_user_id = data.get("assignee_user_id")
        assigned_by = data.get("assigned_by")

        if not assignee_user_id:
            return jsonify({"error": "assignee_user_id is required"}), 400

        # Check assignee exists
        assignee = queue_service.get_sales_team_member(assignee_user_id)
        if not assignee:
            return (
                jsonify({"error": f"Sales team member {assignee_user_id} not found"}),
                404,
            )

        if not assignee.is_active:
            return (
                jsonify(
                    {"error": f"Sales team member {assignee_user_id} is not active"}
                ),
                400,
            )

        # Perform assignment
        success = queue_service.assign_queue_entry(
            entry_id, assignee_user_id, assigned_by
        )

        if success:
            return jsonify(
                {
                    "success": True,
                    "message": f"Queue entry {entry_id} assigned to {assignee.name}",
                    "assignee": {
                        "user_id": assignee.user_id,
                        "name": assignee.name,
                        "email": assignee.email,
                    },
                }
            )
        else:
            return jsonify({"error": "Assignment failed"}), 400

    except Exception as e:
        logger.error(f"Error assigning queue entry {entry_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@handoff_queue.route("/api/handoff/criteria", methods=["GET"])
def list_qualification_criteria():
    """List qualification criteria.

    Query parameters:
    - active_only: true/false (default: true)
    """
    try:
        active_only = request.args.get("active_only", "true").lower() == "true"

        criteria_list = qualification_engine.list_criteria(active_only=active_only)

        return jsonify(
            {
                "criteria": [criteria.to_dict() for criteria in criteria_list],
                "total_count": len(criteria_list),
                "active_only": active_only,
            }
        )

    except Exception as e:
        logger.error(f"Error listing qualification criteria: {e}")
        return jsonify({"error": "Internal server error"}), 500


@handoff_queue.route("/api/handoff/criteria", methods=["POST"])
def create_qualification_criteria():
    """Create new qualification criteria.

    Request body should contain:
    {
        "name": "Custom Criteria",
        "description": "Description",
        "min_score": 70,
        "max_score": null (optional),
        "required_fields": ["name", "email"],
        "engagement_requirements": {"min_page_views": 3},
        "custom_rules": {"has_website": true}
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        name = data.get("name")
        description = data.get("description")
        min_score = data.get("min_score", 0)
        max_score = data.get("max_score")
        required_fields = data.get("required_fields", [])
        engagement_requirements = data.get("engagement_requirements", {})
        custom_rules = data.get("custom_rules", {})

        # Validation
        if not name:
            return jsonify({"error": "name is required"}), 400

        if not description:
            return jsonify({"error": "description is required"}), 400

        try:
            min_score = int(min_score)
            if max_score is not None:
                max_score = int(max_score)
        except (ValueError, TypeError):
            return jsonify({"error": "min_score and max_score must be integers"}), 400

        if not isinstance(required_fields, list):
            return jsonify({"error": "required_fields must be a list"}), 400

        if not isinstance(engagement_requirements, dict):
            return (
                jsonify({"error": "engagement_requirements must be a dictionary"}),
                400,
            )

        if not isinstance(custom_rules, dict):
            return jsonify({"error": "custom_rules must be a dictionary"}), 400

        # Create criteria
        criteria_id = qualification_engine.create_criteria(
            name=name,
            description=description,
            min_score=min_score,
            max_score=max_score,
            required_fields=required_fields,
            engagement_requirements=engagement_requirements,
            custom_rules=custom_rules,
        )

        if criteria_id:
            criteria = qualification_engine.get_criteria_by_id(criteria_id)
            return (
                jsonify(
                    {
                        "success": True,
                        "criteria_id": criteria_id,
                        "message": f"Qualification criteria '{name}' created successfully",
                        "criteria": criteria.to_dict() if criteria else None,
                    }
                ),
                201,
            )
        else:
            return jsonify({"error": "Failed to create qualification criteria"}), 400

    except Exception as e:
        logger.error(f"Error creating qualification criteria: {e}")
        return jsonify({"error": "Internal server error"}), 500


@handoff_queue.route("/api/handoff/sales-team", methods=["GET"])
def list_sales_team():
    """List sales team members.

    Query parameters:
    - active_only: true/false (default: true)
    """
    try:
        active_only = request.args.get("active_only", "true").lower() == "true"

        storage = get_storage_instance()

        with storage.cursor() as cursor:
            if active_only:
                cursor.execute(
                    "SELECT * FROM sales_team_members WHERE is_active = TRUE ORDER BY name"
                )
            else:
                cursor.execute("SELECT * FROM sales_team_members ORDER BY name")

            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

            members = []
            for row in rows:
                member_data = dict(zip(columns, row))

                # Parse JSON fields
                member_data["specialties"] = member_data.get("specialties", [])
                member_data["working_hours"] = member_data.get("working_hours", {})

                # Calculate capacity utilization
                member_data["capacity_utilization"] = (
                    member_data["current_capacity"] / member_data["max_capacity"]
                    if member_data["max_capacity"] > 0
                    else 0
                )

                members.append(member_data)

        return jsonify(
            {
                "members": members,
                "total_count": len(members),
                "active_only": active_only,
            }
        )

    except Exception as e:
        logger.error(f"Error listing sales team: {e}")
        return jsonify({"error": "Internal server error"}), 500


@handoff_queue.route("/api/handoff/operations/<operation_id>", methods=["GET"])
def get_bulk_operation_status(operation_id: str):
    """Get status of a bulk operation."""
    try:
        storage = get_storage_instance()

        with storage.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM bulk_qualification_operations
                WHERE operation_id = %s
                """,
                (operation_id,),
            )

            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "Operation not found"}), 404

            columns = [desc[0] for desc in cursor.description]
            operation_data = dict(zip(columns, row))

            # Parse JSON fields
            operation_data["operation_details"] = operation_data.get(
                "operation_details", {}
            )

            return jsonify(operation_data)

    except Exception as e:
        logger.error(f"Error getting operation status {operation_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@handoff_queue.route("/api/handoff/analytics/summary", methods=["GET"])
def get_handoff_analytics_summary():
    """Get handoff queue analytics summary."""
    try:
        storage = get_storage_instance()

        with storage.cursor() as cursor:
            # Get queue summary by status
            cursor.execute(
                """
                SELECT status, COUNT(*) as count, AVG(priority) as avg_priority,
                       AVG(qualification_score) as avg_score
                FROM handoff_queue
                GROUP BY status
                ORDER BY status
                """
            )

            status_summary = []
            for row in cursor.fetchall():
                status_summary.append(
                    {
                        "status": row[0],
                        "count": row[1],
                        "avg_priority": round(float(row[2]) if row[2] else 0, 2),
                        "avg_score": round(float(row[3]) if row[3] else 0, 2),
                    }
                )

            # Get assignment summary
            cursor.execute(
                """
                SELECT assigned_to, COUNT(*) as count
                FROM handoff_queue
                WHERE assigned_to IS NOT NULL
                GROUP BY assigned_to
                ORDER BY count DESC
                """
            )

            assignment_summary = []
            for row in cursor.fetchall():
                assignee = queue_service.get_sales_team_member(row[0])
                assignment_summary.append(
                    {
                        "assignee_id": row[0],
                        "assignee_name": assignee.name if assignee else "Unknown",
                        "assigned_count": row[1],
                    }
                )

            # Get criteria summary
            cursor.execute(
                """
                SELECT hq.qualification_criteria_id, hqc.name, COUNT(*) as count,
                       AVG(hq.qualification_score) as avg_score
                FROM handoff_queue hq
                JOIN handoff_qualification_criteria hqc ON hq.qualification_criteria_id = hqc.id
                GROUP BY hq.qualification_criteria_id, hqc.name
                ORDER BY count DESC
                """
            )

            criteria_summary = []
            for row in cursor.fetchall():
                criteria_summary.append(
                    {
                        "criteria_id": row[0],
                        "criteria_name": row[1],
                        "qualified_count": row[2],
                        "avg_score": round(float(row[3]) if row[3] else 0, 2),
                    }
                )

            # Get total counts
            cursor.execute("SELECT COUNT(*) FROM handoff_queue")
            total_queue_entries = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM handoff_queue WHERE status = 'qualified'"
            )
            unassigned_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM sales_team_members WHERE is_active = TRUE"
            )
            active_sales_members = cursor.fetchone()[0]

        return jsonify(
            {
                "summary": {
                    "total_queue_entries": total_queue_entries,
                    "unassigned_count": unassigned_count,
                    "active_sales_members": active_sales_members,
                },
                "status_breakdown": status_summary,
                "assignment_breakdown": assignment_summary,
                "criteria_breakdown": criteria_summary,
            }
        )

    except Exception as e:
        logger.error(f"Error getting handoff analytics summary: {e}")
        return jsonify({"error": "Internal server error"}), 500
