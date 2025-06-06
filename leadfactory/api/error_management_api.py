"""
Error Management API with Bulk Operations - FL-4 Implementation.

This module extends the error management capabilities with bulk operations
for dismissing, categorizing, and fixing errors. Part of Feature 8: Fallback & Retry.
"""

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, jsonify, request

from leadfactory.api.input_validation import rate_limit, validate_request_args
from leadfactory.pipeline.error_aggregation import ErrorAggregator, TimeWindow
from leadfactory.pipeline.error_handling import (
    ErrorCategory,
    ErrorSeverity,
    PipelineError,
)
from leadfactory.pipeline.manual_fix_scripts import manual_fix_orchestrator
from leadfactory.storage import get_storage
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)

# Create Blueprint for error management
error_management = Blueprint("error_management", __name__, url_prefix="/api/errors")

# Global instances
storage = get_storage()
error_aggregator = ErrorAggregator()


@error_management.route("/bulk-dismiss", methods=["POST"])
@rate_limit(max_requests=20, window_seconds=60)
def bulk_dismiss_errors() -> Response:
    """
    Bulk dismiss multiple errors.

    Expected JSON payload:
    {
        "error_ids": ["error1", "error2", ...],
        "reason": "resolved_manually" | "false_positive" | "duplicate" | "ignored",
        "comment": "Optional explanation",
        "dismissed_by": "user_id or system"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON payload required"}), 400

        # Validate required fields
        error_ids = data.get("error_ids", [])
        if not error_ids or not isinstance(error_ids, list):
            return jsonify({"error": "error_ids must be a non-empty list"}), 400

        reason = data.get("reason", "ignored")
        valid_reasons = ["resolved_manually", "false_positive", "duplicate", "ignored"]
        if reason not in valid_reasons:
            return jsonify({"error": f"reason must be one of: {valid_reasons}"}), 400

        comment = data.get("comment", "")
        dismissed_by = data.get("dismissed_by", "api_user")

        # Track results
        results = {
            "dismissed": [],
            "not_found": [],
            "failed": [],
            "total_requested": len(error_ids),
        }

        for error_id in error_ids:
            try:
                # Get error details
                if hasattr(storage, "get_error_by_id"):
                    error_data = storage.get_error_by_id(error_id)
                    if not error_data:
                        results["not_found"].append(error_id)
                        continue

                # Create dismissal record
                dismissal_data = {
                    "error_id": error_id,
                    "reason": reason,
                    "comment": comment,
                    "dismissed_by": dismissed_by,
                    "dismissed_at": datetime.now().isoformat(),
                    "business_id": error_data.get("business_id"),
                }

                # Store dismissal
                if hasattr(storage, "dismiss_error"):
                    if storage.dismiss_error(error_id, dismissal_data):
                        results["dismissed"].append(
                            {
                                "error_id": error_id,
                                "business_id": error_data.get("business_id"),
                                "dismissal_data": dismissal_data,
                            }
                        )
                    else:
                        results["failed"].append(error_id)
                else:
                    # Fallback: mark as dismissed in error record
                    update_data = {
                        "status": "dismissed",
                        "dismissal_reason": reason,
                        "dismissal_comment": comment,
                        "dismissed_by": dismissed_by,
                        "dismissed_at": datetime.now().isoformat(),
                    }

                    if hasattr(storage, "update_error"):
                        if storage.update_error(error_id, update_data):
                            results["dismissed"].append(
                                {
                                    "error_id": error_id,
                                    "business_id": error_data.get("business_id"),
                                    "dismissal_data": dismissal_data,
                                }
                            )
                        else:
                            results["failed"].append(error_id)
                    else:
                        results["failed"].append(error_id)

            except Exception as e:
                logger.error(f"Error dismissing {error_id}: {e}")
                results["failed"].append(error_id)

        # Log bulk dismissal
        logger.info(
            f"Bulk dismissal completed: {len(results['dismissed'])} dismissed, "
            f"{len(results['failed'])} failed, {len(results['not_found'])} not found"
        )

        return jsonify(
            {
                "success": True,
                "results": results,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Bulk dismiss errors failed: {e}")
        return jsonify({"error": "Internal server error"}), 500


@error_management.route("/bulk-categorize", methods=["POST"])
@rate_limit(max_requests=20, window_seconds=60)
def bulk_categorize_errors() -> Response:
    """
    Bulk categorize multiple errors.

    Expected JSON payload:
    {
        "error_ids": ["error1", "error2", ...],
        "category": "network" | "database" | "validation" | ...,
        "severity": "low" | "medium" | "high" | "critical",
        "tags": ["tag1", "tag2"],
        "updated_by": "user_id"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON payload required"}), 400

        # Validate required fields
        error_ids = data.get("error_ids", [])
        if not error_ids or not isinstance(error_ids, list):
            return jsonify({"error": "error_ids must be a non-empty list"}), 400

        category = data.get("category")
        severity = data.get("severity")
        tags = data.get("tags", [])
        updated_by = data.get("updated_by", "api_user")

        # Validate category if provided
        if category:
            valid_categories = [c.value for c in ErrorCategory]
            if category not in valid_categories:
                return (
                    jsonify({"error": f"category must be one of: {valid_categories}"}),
                    400,
                )

        # Validate severity if provided
        if severity:
            valid_severities = [s.value for s in ErrorSeverity]
            if severity not in valid_severities:
                return (
                    jsonify({"error": f"severity must be one of: {valid_severities}"}),
                    400,
                )

        # Track results
        results = {
            "updated": [],
            "not_found": [],
            "failed": [],
            "total_requested": len(error_ids),
        }

        for error_id in error_ids:
            try:
                # Get error details
                if hasattr(storage, "get_error_by_id"):
                    error_data = storage.get_error_by_id(error_id)
                    if not error_data:
                        results["not_found"].append(error_id)
                        continue

                # Build update data
                update_data = {
                    "updated_by": updated_by,
                    "updated_at": datetime.now().isoformat(),
                }

                if category:
                    update_data["category"] = category
                if severity:
                    update_data["severity"] = severity
                if tags:
                    update_data["tags"] = tags

                # Update error
                if hasattr(storage, "update_error"):
                    if storage.update_error(error_id, update_data):
                        results["updated"].append(
                            {
                                "error_id": error_id,
                                "business_id": error_data.get("business_id"),
                                "updates": update_data,
                            }
                        )
                    else:
                        results["failed"].append(error_id)
                else:
                    results["failed"].append(error_id)

            except Exception as e:
                logger.error(f"Error categorizing {error_id}: {e}")
                results["failed"].append(error_id)

        logger.info(
            f"Bulk categorization completed: {len(results['updated'])} updated, "
            f"{len(results['failed'])} failed, {len(results['not_found'])} not found"
        )

        return jsonify(
            {
                "success": True,
                "results": results,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Bulk categorize errors failed: {e}")
        return jsonify({"error": "Internal server error"}), 500


@error_management.route("/bulk-fix", methods=["POST"])
@rate_limit(max_requests=10, window_seconds=60)
def bulk_fix_errors() -> Response:
    """
    Attempt to bulk fix multiple errors using manual fix scripts.

    Expected JSON payload:
    {
        "error_ids": ["error1", "error2", ...],
        "max_fixes_per_error": 3,
        "initiated_by": "user_id"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON payload required"}), 400

        # Validate required fields
        error_ids = data.get("error_ids", [])
        if not error_ids or not isinstance(error_ids, list):
            return jsonify({"error": "error_ids must be a non-empty list"}), 400

        max_fixes_per_error = data.get("max_fixes_per_error", 3)
        initiated_by = data.get("initiated_by", "api_user")

        # Limit batch size to prevent overwhelming the system
        if len(error_ids) > 50:
            return jsonify({"error": "Maximum 50 errors per batch"}), 400

        # Track results
        results = {
            "fix_attempts": {},
            "not_found": [],
            "no_applicable_fixes": [],
            "total_requested": len(error_ids),
            "summary": {
                "successful_fixes": 0,
                "partial_fixes": 0,
                "failed_fixes": 0,
                "manual_intervention_required": 0,
            },
        }

        for error_id in error_ids:
            try:
                # Get error details and convert to PipelineError
                if hasattr(storage, "get_error_by_id"):
                    error_data = storage.get_error_by_id(error_id)
                    if not error_data:
                        results["not_found"].append(error_id)
                        continue

                    # Convert to PipelineError object
                    pipeline_error = PipelineError(
                        id=error_id,
                        timestamp=datetime.fromisoformat(
                            error_data.get("timestamp", datetime.now().isoformat())
                        ),
                        stage=error_data.get("stage", ""),
                        operation=error_data.get("operation", ""),
                        error_type=error_data.get("error_type", ""),
                        error_message=error_data.get("error_message", ""),
                        severity=ErrorSeverity(error_data.get("severity", "medium")),
                        category=ErrorCategory(
                            error_data.get("category", "business_logic")
                        ),
                        context=error_data.get("context", {}),
                        business_id=error_data.get("business_id"),
                    )

                    # Attempt fixes
                    fix_executions = manual_fix_orchestrator.fix_error(
                        pipeline_error, max_fixes=max_fixes_per_error
                    )

                    if not fix_executions:
                        results["no_applicable_fixes"].append(error_id)
                        continue

                    # Process fix results
                    error_result = {
                        "error_id": error_id,
                        "business_id": pipeline_error.business_id,
                        "fix_executions": [
                            asdict(execution) for execution in fix_executions
                        ],
                        "overall_result": "failed",
                    }

                    # Determine overall result
                    for execution in fix_executions:
                        if execution.result.value == "success":
                            error_result["overall_result"] = "success"
                            results["summary"]["successful_fixes"] += 1
                            break
                        elif execution.result.value == "partial_success":
                            error_result["overall_result"] = "partial_success"
                            results["summary"]["partial_fixes"] += 1
                        elif execution.result.value == "manual_intervention":
                            error_result["overall_result"] = "manual_intervention"
                            results["summary"]["manual_intervention_required"] += 1

                    if error_result["overall_result"] == "failed":
                        results["summary"]["failed_fixes"] += 1

                    results["fix_attempts"][error_id] = error_result

                else:
                    results["not_found"].append(error_id)

            except Exception as e:
                logger.error(f"Error fixing {error_id}: {e}")
                results["fix_attempts"][error_id] = {
                    "error_id": error_id,
                    "overall_result": "failed",
                    "error": str(e),
                }
                results["summary"]["failed_fixes"] += 1

        logger.info(
            f"Bulk fix completed: {results['summary']['successful_fixes']} successful, "
            f"{results['summary']['failed_fixes']} failed, "
            f"{results['summary']['manual_intervention_required']} require manual intervention"
        )

        return jsonify(
            {
                "success": True,
                "results": results,
                "initiated_by": initiated_by,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Bulk fix errors failed: {e}")
        return jsonify({"error": "Internal server error"}), 500


@error_management.route("/dashboard-data", methods=["GET"])
def get_error_dashboard_data() -> Response:
    """Get comprehensive error dashboard data."""
    try:
        # Get time window from query parameter
        time_window_str = request.args.get("time_window", "last_24_hours")
        try:
            time_window = TimeWindow(time_window_str)
        except ValueError:
            time_window = TimeWindow.LAST_24_HOURS

        # Generate error metrics
        metrics = error_aggregator.generate_error_metrics(time_window)
        alerts = error_aggregator.check_alert_thresholds(metrics)

        # Get fix script statistics
        fix_stats = manual_fix_orchestrator.get_fix_script_stats()
        recent_fixes = manual_fix_orchestrator.get_recent_fix_executions(24)

        # Build dashboard data
        dashboard_data = {
            "timestamp": datetime.now().isoformat(),
            "time_window": time_window.value,
            "error_metrics": metrics.to_dict(),
            "active_alerts": alerts,
            "fix_script_stats": fix_stats,
            "recent_fix_executions": [
                asdict(execution) for execution in recent_fixes[:20]
            ],
            "summary": {
                "total_errors": metrics.total_errors,
                "critical_errors": metrics.critical_error_count,
                "error_rate_per_hour": round(metrics.error_rate_per_hour, 2),
                "top_error_patterns": [
                    pattern.to_dict() for pattern in metrics.patterns[:5]
                ],
                "affected_businesses": len(metrics.affected_businesses),
                "recent_fixes_count": len(recent_fixes),
                "successful_fixes_24h": sum(
                    1 for ex in recent_fixes if ex.result.value == "success"
                ),
            },
        }

        return jsonify(dashboard_data)

    except Exception as e:
        logger.error(f"Error generating dashboard data: {e}")
        return jsonify({"error": "Internal server error"}), 500


@error_management.route("/patterns", methods=["GET"])
def get_error_patterns() -> Response:
    """Get error patterns for analysis."""
    try:
        # Get time window from query parameter
        time_window_str = request.args.get("time_window", "last_24_hours")
        try:
            time_window = TimeWindow(time_window_str)
        except ValueError:
            time_window = TimeWindow.LAST_24_HOURS

        # Get minimum frequency threshold
        min_frequency = int(request.args.get("min_frequency", 5))

        # Generate metrics and extract patterns
        metrics = error_aggregator.generate_error_metrics(time_window)

        # Filter patterns by frequency
        significant_patterns = [
            pattern
            for pattern in metrics.patterns
            if pattern.frequency >= min_frequency
        ]

        return jsonify(
            {
                "time_window": time_window.value,
                "min_frequency": min_frequency,
                "total_patterns": len(metrics.patterns),
                "significant_patterns": len(significant_patterns),
                "patterns": [pattern.to_dict() for pattern in significant_patterns],
            }
        )

    except Exception as e:
        logger.error(f"Error getting error patterns: {e}")
        return jsonify({"error": "Internal server error"}), 500


@error_management.route("/fix-scripts", methods=["GET"])
def get_fix_scripts_info() -> Response:
    """Get information about available fix scripts."""
    try:
        fix_stats = manual_fix_orchestrator.get_fix_script_stats()

        return jsonify(
            {
                "available_scripts": len(fix_stats),
                "scripts": fix_stats,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error getting fix scripts info: {e}")
        return jsonify({"error": "Internal server error"}), 500


@error_management.route("/dismissal-reasons", methods=["GET"])
def get_dismissal_reasons() -> Response:
    """Get available dismissal reasons for errors."""
    return jsonify(
        {
            "reasons": [
                {
                    "value": "resolved_manually",
                    "label": "Resolved Manually",
                    "description": "Error was fixed through manual intervention",
                },
                {
                    "value": "false_positive",
                    "label": "False Positive",
                    "description": "Error was incorrectly flagged",
                },
                {
                    "value": "duplicate",
                    "label": "Duplicate",
                    "description": "Error is a duplicate of another issue",
                },
                {
                    "value": "ignored",
                    "label": "Ignored",
                    "description": "Error is acknowledged but no action needed",
                },
            ]
        }
    )


@error_management.route("/health", methods=["GET"])
def health_check() -> Response:
    """Health check for error management API."""
    try:
        # Basic health checks
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "storage": "healthy" if storage else "unavailable",
                "error_aggregator": "healthy",
                "fix_orchestrator": "healthy",
            },
        }

        # Check if storage is responsive
        if hasattr(storage, "test_connection"):
            try:
                if storage.test_connection():
                    health_status["services"]["storage"] = "healthy"
                else:
                    health_status["services"]["storage"] = "unhealthy"
            except Exception:
                health_status["services"]["storage"] = "unhealthy"

        # Overall status
        if any(status == "unhealthy" for status in health_status["services"].values()):
            health_status["status"] = "degraded"
        elif any(
            status == "unavailable" for status in health_status["services"].values()
        ):
            health_status["status"] = "partial"

        return jsonify(health_status)

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            500,
        )
