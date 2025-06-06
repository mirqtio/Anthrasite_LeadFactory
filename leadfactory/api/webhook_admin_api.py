#!/usr/bin/env python3
"""
Webhook Administration API.

This module provides administrative endpoints for managing webhooks,
monitoring health, managing retries, and handling dead letter queues.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from leadfactory.utils.logging import get_logger
from leadfactory.webhooks.dead_letter_queue import (
    DeadLetterCategory,
    DeadLetterReason,
    DeadLetterStatus,
)
from leadfactory.webhooks.webhook_integration import get_webhook_integration_service
from leadfactory.webhooks.webhook_monitor import HealthStatus, MetricType
from leadfactory.webhooks.webhook_retry_manager import WebhookPriority

logger = get_logger(__name__)

# Create blueprint for webhook admin API
webhook_admin_bp = Blueprint(
    "webhook_admin", __name__, url_prefix="/api/webhooks/admin"
)


# Helper function to get service instance
def _get_service():
    """Get webhook integration service instance."""
    return get_webhook_integration_service()


@webhook_admin_bp.route("/health", methods=["GET"])
def get_overall_health():
    """Get overall webhook system health."""
    try:
        service = get_webhook_integration_service()
        health_data = service.webhook_monitor.get_overall_health()
        return jsonify(health_data), 200
    except Exception as e:
        logger.error(f"Error getting overall health: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/health/<webhook_name>", methods=["GET"])
def get_webhook_health(webhook_name: str):
    """Get health status for a specific webhook."""
    try:
        service = get_webhook_integration_service()
        health_data = service.webhook_monitor.get_webhook_health(webhook_name)
        if health_data:
            return jsonify(health_data), 200
        else:
            return jsonify({"error": "Webhook not found"}), 404
    except Exception as e:
        logger.error(f"Error getting webhook health: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/health/<webhook_name>/config", methods=["PUT"])
def update_health_config(webhook_name: str):
    """Update health check configuration for a webhook."""
    try:
        config_data = request.get_json()
        if not config_data:
            return jsonify({"error": "No configuration data provided"}), 400

        service = get_webhook_integration_service()
        success = service.webhook_monitor.update_health_check(
            webhook_name, **config_data
        )

        if success:
            return jsonify({"message": "Health check configuration updated"}), 200
        else:
            return jsonify({"error": "Failed to update configuration"}), 500

    except Exception as e:
        logger.error(f"Error updating health config: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/metrics/<webhook_name>/<metric_type>", methods=["GET"])
def get_metrics_history(webhook_name: str, metric_type: str):
    """Get historical metrics for a webhook."""
    try:
        hours = request.args.get("hours", 24, type=int)

        # Validate metric type
        try:
            metric_type_enum = MetricType(metric_type)
        except ValueError:
            return jsonify({"error": f"Invalid metric type: {metric_type}"}), 400

        metrics = _get_service().webhook_monitor.get_metrics_history(
            webhook_name, metric_type_enum, hours
        )

        return jsonify({"metrics": metrics}), 200

    except Exception as e:
        logger.error(f"Error getting metrics history: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/retry/queue", methods=["GET"])
def get_retry_queue_stats():
    """Get retry queue statistics."""
    try:
        stats = _get_service().retry_manager.get_queue_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error getting retry queue stats: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/retry/queue/priority-distribution", methods=["GET"])
def get_priority_distribution():
    """Get distribution of items by priority in retry queue."""
    try:
        distribution = _get_service().retry_manager.get_priority_distribution()
        return jsonify(distribution), 200
    except Exception as e:
        logger.error(f"Error getting priority distribution: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/retry/queue/pause", methods=["POST"])
def pause_retry_queue():
    """Pause the retry queue processing."""
    try:
        _get_service().retry_manager.pause_queue()
        return jsonify({"message": "Retry queue paused"}), 200
    except Exception as e:
        logger.error(f"Error pausing retry queue: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/retry/queue/resume", methods=["POST"])
def resume_retry_queue():
    """Resume the retry queue processing."""
    try:
        _get_service().retry_manager.resume_queue()
        return jsonify({"message": "Retry queue resumed"}), 200
    except Exception as e:
        logger.error(f"Error resuming retry queue: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/retry/queue/clear", methods=["POST"])
def clear_retry_queue():
    """Clear the retry queue."""
    try:
        webhook_name = request.args.get("webhook_name")
        _get_service().retry_manager.clear_queue(webhook_name)

        message = (
            f"Retry queue cleared for webhook: {webhook_name}"
            if webhook_name
            else "Entire retry queue cleared"
        )
        return jsonify({"message": message}), 200

    except Exception as e:
        logger.error(f"Error clearing retry queue: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/retry/force/<event_id>", methods=["POST"])
def force_retry_event(event_id: str):
    """Force immediate retry of a specific event."""
    try:
        priority_str = request.args.get("priority", "high")
        try:
            priority = WebhookPriority(priority_str.upper())
        except ValueError:
            priority = WebhookPriority.HIGH

        success = _get_service().retry_manager.force_retry_event(event_id, priority)

        if success:
            return (
                jsonify({"message": f"Forced retry scheduled for event {event_id}"}),
                200,
            )
        else:
            return jsonify({"error": "Failed to schedule retry"}), 500

    except Exception as e:
        logger.error(f"Error forcing retry: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/dead-letter", methods=["GET"])
def get_dead_letter_events():
    """Get dead letter queue events with filtering."""
    try:
        # Parse query parameters
        status = request.args.get("status")
        category = request.args.get("category")
        webhook_name = request.args.get("webhook_name")
        reason = request.args.get("reason")
        assigned_to = request.args.get("assigned_to")
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)

        # Convert string enums
        status_enum = None
        if status:
            try:
                status_enum = DeadLetterStatus(status)
            except ValueError:
                return jsonify({"error": f"Invalid status: {status}"}), 400

        category_enum = None
        if category:
            try:
                category_enum = DeadLetterCategory(category)
            except ValueError:
                return jsonify({"error": f"Invalid category: {category}"}), 400

        reason_enum = None
        if reason:
            try:
                reason_enum = DeadLetterReason(reason)
            except ValueError:
                return jsonify({"error": f"Invalid reason: {reason}"}), 400

        # Get events
        events = _get_service().dead_letter_manager.get_events(
            status=status_enum,
            category=category_enum,
            webhook_name=webhook_name,
            reason=reason_enum,
            assigned_to=assigned_to,
            limit=limit,
            offset=offset,
        )

        # Convert to dict format
        events_data = [event.to_dict() for event in events]

        return (
            jsonify(
                {
                    "events": events_data,
                    "total": len(events_data),
                    "limit": limit,
                    "offset": offset,
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error getting dead letter events: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/dead-letter/statistics", methods=["GET"])
def get_dead_letter_statistics():
    """Get dead letter queue statistics."""
    try:
        stats = _get_service().dead_letter_manager.get_statistics()
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error getting dead letter statistics: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/dead-letter/<event_id>", methods=["GET"])
def get_dead_letter_event(event_id: str):
    """Get a specific dead letter event."""
    try:
        event = _get_service().dead_letter_manager.get_event(event_id)
        if event:
            return jsonify(event.to_dict()), 200
        else:
            return jsonify({"error": "Event not found"}), 404
    except Exception as e:
        logger.error(f"Error getting dead letter event: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/dead-letter/<event_id>/status", methods=["PUT"])
def update_dead_letter_status(event_id: str):
    """Update the status of a dead letter event."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        status_str = data.get("status")
        if not status_str:
            return jsonify({"error": "Status is required"}), 400

        try:
            status = DeadLetterStatus(status_str)
        except ValueError:
            return jsonify({"error": f"Invalid status: {status_str}"}), 400

        notes = data.get("notes")
        assigned_to = data.get("assigned_to")

        success = _get_service().dead_letter_manager.update_event_status(
            event_id, status, notes, assigned_to
        )

        if success:
            return jsonify({"message": "Event status updated"}), 200
        else:
            return jsonify({"error": "Failed to update status"}), 500

    except Exception as e:
        logger.error(f"Error updating dead letter status: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/dead-letter/<event_id>/reprocess", methods=["POST"])
def reprocess_dead_letter_event(event_id: str):
    """Reprocess a dead letter event."""
    try:
        force = request.args.get("force", "false").lower() == "true"

        success = _get_service().dead_letter_manager.reprocess_event(event_id, force)

        if success:
            return (
                jsonify({"message": f"Event {event_id} reprocessed successfully"}),
                200,
            )
        else:
            return jsonify({"error": "Failed to reprocess event"}), 500

    except Exception as e:
        logger.error(f"Error reprocessing dead letter event: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/dead-letter/bulk-reprocess", methods=["POST"])
def bulk_reprocess_dead_letter():
    """Bulk reprocess dead letter events."""
    try:
        data = request.get_json() or {}
        filters = data.get("filters", {})
        max_events = data.get("max_events", 10)

        results = _get_service().dead_letter_manager.bulk_reprocess(
            filters=filters, max_events=max_events
        )

        return jsonify(results), 200

    except Exception as e:
        logger.error(f"Error in bulk reprocess: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/dead-letter/archive-old", methods=["POST"])
def archive_old_dead_letter():
    """Archive old dead letter events."""
    try:
        days = request.args.get("days", type=int)
        archived_count = _get_service().dead_letter_manager.archive_old_events(days)

        return (
            jsonify(
                {
                    "message": f"Archived {archived_count} old events",
                    "archived_count": archived_count,
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error archiving old events: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/dead-letter/cleanup", methods=["POST"])
def cleanup_old_dead_letter():
    """Delete very old archived events."""
    try:
        days = request.args.get("days", 90, type=int)
        deleted_count = _get_service().dead_letter_manager.cleanup_old_events(days)

        return (
            jsonify(
                {
                    "message": f"Deleted {deleted_count} old archived events",
                    "deleted_count": deleted_count,
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"Error cleaning up old events: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/webhooks", methods=["GET"])
def list_webhook_configs():
    """List all webhook configurations."""
    try:
        configs = {}
        for name, config in _get_service().webhook_validator.webhook_configs.items():
            configs[name] = {
                "name": config.name,
                "endpoint_path": config.endpoint_path,
                "event_types": [et.value for et in config.event_types],
                "enabled": config.enabled,
                "timeout_seconds": config.timeout_seconds,
                "max_retries": config.max_retries,
                "rate_limit_per_minute": config.rate_limit_per_minute,
            }

        return jsonify(configs), 200

    except Exception as e:
        logger.error(f"Error listing webhook configs: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/webhooks/<webhook_name>/stats", methods=["GET"])
def get_webhook_stats(webhook_name: str):
    """Get processing statistics for a webhook."""
    try:
        stats = _get_service().webhook_validator.get_webhook_stats(webhook_name)
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Error getting webhook stats: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/system/status", methods=["GET"])
def get_system_status():
    """Get overall system status."""
    try:
        status = _get_service().get_integration_status()
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/monitoring/start", methods=["POST"])
def start_monitoring():
    """Start webhook monitoring."""
    try:
        _get_service().webhook_monitor.start_monitoring()
        return jsonify({"message": "Monitoring started"}), 200
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/monitoring/stop", methods=["POST"])
def stop_monitoring():
    """Stop webhook monitoring."""
    try:
        _get_service().webhook_monitor.stop_monitoring()
        return jsonify({"message": "Monitoring stopped"}), 200
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/dashboard", methods=["GET"])
def get_dashboard_data():
    """Get comprehensive dashboard data."""
    try:
        # Get data from all components
        health_data = _get_service().webhook_monitor.get_overall_health()
        retry_stats = _get_service().retry_manager.get_queue_stats()
        dl_stats = _get_service().dead_letter_manager.get_statistics()

        # Recent activity (last 24 hours)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)

        dashboard_data = {
            "summary": {
                "total_webhooks": health_data.get("total_webhooks", 0),
                "healthy_webhooks": health_data.get("webhooks_by_status", {}).get(
                    "healthy", 0
                ),
                "total_retry_items": retry_stats.get("items_in_queue", 0),
                "total_dead_letter": dl_stats.get("total_events", 0),
                "active_dead_letter": dl_stats.get("by_status", {}).get("active", 0),
            },
            "health": health_data,
            "retry_queue": retry_stats,
            "dead_letter": dl_stats,
            "recent_activity": {
                "dead_letter_last_24h": dl_stats.get("events_last_24h", 0),
                "dead_letter_last_7d": dl_stats.get("events_last_7d", 0),
            },
            "last_updated": datetime.utcnow().isoformat(),
        }

        return jsonify(dashboard_data), 200

    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_admin_bp.route("/events/<event_id>", methods=["GET"])
def get_webhook_event(event_id: str):
    """Get details of a specific webhook event."""
    try:
        # Try to find the event in various places
        from leadfactory.storage import get_storage_instance

        storage = get_storage_instance()

        # First try regular webhook events
        event_data = storage.get_webhook_event(event_id)
        if event_data:
            return (
                jsonify(
                    {
                        "event": event_data,
                        "location": "webhook_events",
                    }
                ),
                200,
            )

        # Then try dead letter queue
        dl_event = _get_service().dead_letter_manager.get_event(event_id)
        if dl_event:
            return (
                jsonify(
                    {
                        "event": dl_event.to_dict(),
                        "location": "dead_letter",
                    }
                ),
                200,
            )

        return jsonify({"error": "Event not found"}), 404

    except Exception as e:
        logger.error(f"Error getting webhook event: {e}")
        return jsonify({"error": str(e)}), 500


# Error handlers
@webhook_admin_bp.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad request"}), 400


@webhook_admin_bp.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


@webhook_admin_bp.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500
