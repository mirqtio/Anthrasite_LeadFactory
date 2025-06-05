"""
Backend API for HTML and LLM Logs Retrieval and Management.

Implements Task 11: Web Interface for HTML and LLM Logs Browsing
- RESTful API endpoints for log retrieval, filtering, and export
- Efficient database queries with pagination
- Authentication and authorization
- Search functionality across log content
- Export capabilities in multiple formats
"""

import csv
import io
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS

from leadfactory.api.cache import get_cache
from leadfactory.storage import get_storage
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LogEntry:
    """Data structure for log entries."""

    id: int
    business_id: int
    log_type: str  # 'html', 'llm', 'raw_html', 'enrichment'
    content: str
    timestamp: datetime
    metadata: Dict[str, Any]
    file_path: Optional[str] = None
    file_size: Optional[int] = None


@dataclass
class LogSearchFilters:
    """Search and filter parameters for log queries."""

    business_id: Optional[int] = None
    log_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    search_query: Optional[str] = None
    limit: int = 50
    offset: int = 0
    sort_by: str = "timestamp"
    sort_order: str = "desc"


class LogsAPI:
    """
    API class for handling HTML and LLM logs retrieval and management.

    Provides endpoints for:
    - Fetching logs with pagination and filtering
    - Searching log content
    - Exporting logs in various formats
    - Managing log metadata
    """

    def __init__(self, app: Optional[Flask] = None):
        """Initialize the Logs API."""
        self.storage = get_storage()
        self.cache = get_cache()

        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initialize Flask app with API routes."""
        CORS(app)

        # Register API routes
        app.add_url_rule("/api/logs", "get_logs", self.get_logs, methods=["GET"])
        app.add_url_rule(
            "/api/logs/<int:log_id>",
            "get_log_detail",
            self.get_log_detail,
            methods=["GET"],
        )
        app.add_url_rule(
            "/api/logs/search", "search_logs", self.search_logs, methods=["POST"]
        )
        app.add_url_rule(
            "/api/logs/export", "export_logs", self.export_logs, methods=["POST"]
        )
        app.add_url_rule(
            "/api/logs/export/stream",
            "export_logs_stream",
            self.export_logs_stream,
            methods=["POST"],
        )
        app.add_url_rule(
            "/api/logs/stats", "get_log_stats", self.get_log_stats, methods=["GET"]
        )
        app.add_url_rule(
            "/api/logs/types", "get_log_types", self.get_log_types, methods=["GET"]
        )
        app.add_url_rule(
            "/api/businesses", "get_businesses", self.get_businesses, methods=["GET"]
        )
        app.add_url_rule(
            "/api/cache/stats", "get_cache_stats", self.get_cache_stats, methods=["GET"]
        )
        app.add_url_rule(
            "/api/cache/clear", "clear_cache", self.clear_cache, methods=["POST"]
        )

        logger.info("Logs API routes registered")

    def get_logs(self) -> Response:
        """
        Get logs with optional filtering and pagination.

        Query parameters:
        - business_id: Filter by business ID
        - log_type: Filter by log type (html, llm, raw_html, enrichment)
        - start_date: Filter by start date (ISO format)
        - end_date: Filter by end date (ISO format)
        - search: Search query for content
        - limit: Number of results (default: 50, max: 1000)
        - offset: Pagination offset (default: 0)
        - sort_by: Sort field (timestamp, business_id, log_type)
        - sort_order: Sort order (asc, desc)
        """
        try:
            # Parse query parameters
            filters = self._parse_query_filters(request.args)

            # Validate parameters
            validation_error = self._validate_filters(filters)
            if validation_error:
                return jsonify({"error": validation_error}), 400

            # Fetch logs from storage
            logs, total_count = self._fetch_logs(filters)

            # Format response
            response_data = {
                "logs": [self._format_log_entry(log) for log in logs],
                "pagination": {
                    "limit": filters.limit,
                    "offset": filters.offset,
                    "total": total_count,
                    "has_more": (filters.offset + filters.limit) < total_count,
                },
                "filters": asdict(filters),
            }

            logger.info(f"Retrieved {len(logs)} logs (total: {total_count})")
            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error retrieving logs: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def get_log_detail(self, log_id: int) -> Response:
        """Get detailed information for a specific log entry."""
        try:
            log_entry = self._fetch_log_by_id(log_id)

            if not log_entry:
                return jsonify({"error": "Log not found"}), 404

            # Include full content and metadata
            response_data = self._format_log_entry(log_entry, include_full_content=True)

            logger.info(f"Retrieved log detail for ID: {log_id}")
            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error retrieving log detail {log_id}: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def search_logs(self) -> Response:
        """
        Advanced search across log content with filters.

        Expected JSON payload:
        {
            "query": "search term",
            "filters": {
                "business_id": 123,
                "log_type": "llm",
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-12-31T23:59:59Z"
            },
            "pagination": {
                "limit": 50,
                "offset": 0
            },
            "sort": {
                "by": "timestamp",
                "order": "desc"
            }
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON payload required"}), 400

            # Parse search parameters
            search_query = data.get("query", "")
            filter_data = data.get("filters", {})
            pagination = data.get("pagination", {})
            sort_data = data.get("sort", {})

            # Build search filters
            filters = LogSearchFilters(
                business_id=filter_data.get("business_id"),
                log_type=filter_data.get("log_type"),
                start_date=self._parse_datetime(filter_data.get("start_date")),
                end_date=self._parse_datetime(filter_data.get("end_date")),
                search_query=search_query if search_query else None,
                limit=min(pagination.get("limit", 50), 1000),
                offset=pagination.get("offset", 0),
                sort_by=sort_data.get("by", "timestamp"),
                sort_order=sort_data.get("order", "desc"),
            )

            # Perform search
            logs, total_count = self._search_logs(filters)

            response_data = {
                "logs": [self._format_log_entry(log) for log in logs],
                "search": {
                    "query": search_query,
                    "total_results": total_count,
                    "execution_time_ms": 0,  # Could add timing if needed
                },
                "pagination": {
                    "limit": filters.limit,
                    "offset": filters.offset,
                    "total": total_count,
                    "has_more": (filters.offset + filters.limit) < total_count,
                },
            }

            logger.info(
                f"Search completed: '{search_query}' returned {len(logs)} results"
            )
            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error searching logs: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def export_logs(self) -> Response:
        """
        Export logs in various formats (CSV, JSON).

        Expected JSON payload:
        {
            "filters": { ... },
            "format": "csv" | "json",
            "include_content": true | false
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON payload required"}), 400

            export_format = data.get("format", "csv").lower()
            include_content = data.get("include_content", False)
            filter_data = data.get("filters", {})

            if export_format not in ["csv", "json", "xlsx"]:
                return jsonify({"error": "Format must be csv, json, or xlsx"}), 400

            # Build filters for export
            filters = LogSearchFilters(
                business_id=filter_data.get("business_id"),
                log_type=filter_data.get("log_type"),
                start_date=self._parse_datetime(filter_data.get("start_date")),
                end_date=self._parse_datetime(filter_data.get("end_date")),
                search_query=filter_data.get("search_query"),
                limit=10000,  # Large limit for export
                offset=0,
                sort_by="timestamp",
                sort_order="desc",
            )

            # Fetch logs for export
            logs, total_count = self._fetch_logs(filters)

            # Generate export file
            if export_format == "csv":
                return self._export_csv(logs, include_content)
            elif export_format == "json":
                return self._export_json(logs, include_content)
            elif export_format == "xlsx":
                return self._export_xlsx(logs, include_content)

        except Exception as e:
            logger.error(f"Error exporting logs: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def get_log_stats(self) -> Response:
        """Get statistical information about logs."""
        try:
            stats = self._calculate_log_stats()

            logger.info("Retrieved log statistics")
            return jsonify(stats)

        except Exception as e:
            logger.error(f"Error retrieving log stats: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def get_log_types(self) -> Response:
        """Get available log types."""
        try:
            log_types = self._get_available_log_types()

            return jsonify({"log_types": log_types})

        except Exception as e:
            logger.error(f"Error retrieving log types: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def get_businesses(self) -> Response:
        """Get list of businesses for filtering."""
        try:
            businesses = self._get_businesses_with_logs()

            return jsonify({"businesses": businesses})

        except Exception as e:
            logger.error(f"Error retrieving businesses: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def _parse_query_filters(self, args) -> LogSearchFilters:
        """Parse query parameters into LogSearchFilters."""
        return LogSearchFilters(
            business_id=args.get("business_id", type=int),
            log_type=args.get("log_type"),
            start_date=self._parse_datetime(args.get("start_date")),
            end_date=self._parse_datetime(args.get("end_date")),
            search_query=args.get("search"),
            limit=min(args.get("limit", 50, type=int), 1000),
            offset=args.get("offset", 0, type=int),
            sort_by=args.get("sort_by", "timestamp"),
            sort_order=args.get("sort_order", "desc"),
        )

    def _validate_filters(self, filters: LogSearchFilters) -> Optional[str]:
        """Validate filter parameters."""
        if filters.limit < 1 or filters.limit > 1000:
            return "Limit must be between 1 and 1000"

        if filters.offset < 0:
            return "Offset must be non-negative"

        if filters.sort_by not in ["timestamp", "business_id", "log_type", "id"]:
            return "Invalid sort_by field"

        if filters.sort_order not in ["asc", "desc"]:
            return "Sort order must be 'asc' or 'desc'"

        if filters.log_type and filters.log_type not in [
            "html",
            "llm",
            "raw_html",
            "enrichment",
        ]:
            return "Invalid log_type"

        return None

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string in ISO format."""
        if not date_str:
            return None

        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(f"Invalid datetime format: {date_str}")
            return None

    def _fetch_logs(self, filters: LogSearchFilters) -> tuple[List[LogEntry], int]:
        """Fetch logs from storage based on filters with caching."""
        try:
            # Check cache first
            cache_result = self.cache.get_logs_with_filters(
                business_id=filters.business_id,
                log_type=filters.log_type,
                start_date=filters.start_date,
                end_date=filters.end_date,
                search_query=filters.search_query,
                limit=filters.limit,
                offset=filters.offset,
                sort_by=filters.sort_by,
                sort_order=filters.sort_order,
            )

            if cache_result is not None:
                logs_data, total_count = cache_result
                logger.debug("Cache hit for logs query")
            else:
                # Cache miss - fetch from storage
                query_params = {
                    "business_id": filters.business_id,
                    "log_type": filters.log_type,
                    "start_date": filters.start_date,
                    "end_date": filters.end_date,
                    "search_query": filters.search_query,
                    "limit": filters.limit,
                    "offset": filters.offset,
                    "sort_by": filters.sort_by,
                    "sort_order": filters.sort_order,
                }

                # Remove None values
                query_params = {k: v for k, v in query_params.items() if v is not None}

                # Call storage method
                if hasattr(self.storage, "get_logs_with_filters"):
                    logs_data, total_count = self.storage.get_logs_with_filters(
                        **query_params
                    )

                    # Cache the result
                    self.cache.set_logs_with_filters(
                        (logs_data, total_count),
                        business_id=filters.business_id,
                        log_type=filters.log_type,
                        start_date=filters.start_date,
                        end_date=filters.end_date,
                        search_query=filters.search_query,
                        limit=filters.limit,
                        offset=filters.offset,
                        sort_by=filters.sort_by,
                        sort_order=filters.sort_order,
                    )
                    logger.debug("Cached logs query result")
                else:
                    # Fallback implementation
                    logs_data = []
                    total_count = 0
                    logger.warning(
                        "Storage does not implement get_logs_with_filters method"
                    )

            # Convert to LogEntry objects
            logs = []
            for log_data in logs_data:
                log_entry = LogEntry(
                    id=log_data.get("id"),
                    business_id=log_data.get("business_id"),
                    log_type=log_data.get("log_type"),
                    content=log_data.get("content", ""),
                    timestamp=log_data.get("timestamp", datetime.utcnow()),
                    metadata=log_data.get("metadata", {}),
                    file_path=log_data.get("file_path"),
                    file_size=log_data.get("file_size"),
                )
                logs.append(log_entry)

            return logs, total_count

        except Exception as e:
            logger.error(f"Error fetching logs: {e}")
            return [], 0

    def _fetch_log_by_id(self, log_id: int) -> Optional[LogEntry]:
        """Fetch a single log entry by ID."""
        try:
            if hasattr(self.storage, "get_log_by_id"):
                log_data = self.storage.get_log_by_id(log_id)
                if log_data:
                    return LogEntry(
                        id=log_data.get("id"),
                        business_id=log_data.get("business_id"),
                        log_type=log_data.get("log_type"),
                        content=log_data.get("content", ""),
                        timestamp=log_data.get("timestamp", datetime.utcnow()),
                        metadata=log_data.get("metadata", {}),
                        file_path=log_data.get("file_path"),
                        file_size=log_data.get("file_size"),
                    )
            return None

        except Exception as e:
            logger.error(f"Error fetching log {log_id}: {e}")
            return None

    def _search_logs(self, filters: LogSearchFilters) -> tuple[List[LogEntry], int]:
        """Perform full-text search across log content."""
        # This delegates to the same method as _fetch_logs since search is handled by filters
        return self._fetch_logs(filters)

    def _format_log_entry(
        self, log: LogEntry, include_full_content: bool = False
    ) -> Dict[str, Any]:
        """Format log entry for API response."""
        formatted = {
            "id": log.id,
            "business_id": log.business_id,
            "log_type": log.log_type,
            "timestamp": (
                log.timestamp.isoformat()
                if isinstance(log.timestamp, datetime)
                else log.timestamp
            ),
            "metadata": log.metadata,
            "content_preview": (
                log.content[:200] + "..." if len(log.content) > 200 else log.content
            ),
            "content_length": len(log.content),
            "file_path": log.file_path,
            "file_size": log.file_size,
        }

        if include_full_content:
            formatted["content"] = log.content

        return formatted

    def _export_csv(self, logs: List[LogEntry], include_content: bool) -> Response:
        """Export logs as CSV."""
        output = io.StringIO()

        fieldnames = ["id", "business_id", "log_type", "timestamp", "content_length"]
        if include_content:
            fieldnames.append("content")
        fieldnames.extend(["file_path", "file_size"])

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for log in logs:
            row = {
                "id": log.id,
                "business_id": log.business_id,
                "log_type": log.log_type,
                "timestamp": (
                    log.timestamp.isoformat()
                    if isinstance(log.timestamp, datetime)
                    else log.timestamp
                ),
                "content_length": len(log.content),
                "file_path": log.file_path or "",
                "file_size": log.file_size or "",
            }

            if include_content:
                row["content"] = log.content

            writer.writerow(row)

        output.seek(0)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=logs_export_{timestamp}.csv"
            },
        )

    def _export_json(self, logs: List[LogEntry], include_content: bool) -> Response:
        """Export logs as JSON."""
        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "total_logs": len(logs),
            "include_content": include_content,
            "logs": [self._format_log_entry(log, include_content) for log in logs],
        }

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        return Response(
            json.dumps(export_data, indent=2),
            mimetype="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=logs_export_{timestamp}.json"
            },
        )

    def _export_xlsx(self, logs: List[LogEntry], include_content: bool) -> Response:
        """Export logs as Excel file."""
        try:
            import openpyxl
            import pandas as pd
            from openpyxl.utils.dataframe import dataframe_to_rows

            # Convert logs to DataFrame
            data = []
            for log in logs:
                row = {
                    "ID": log.id,
                    "Business ID": log.business_id,
                    "Log Type": log.log_type,
                    "Timestamp": (
                        log.timestamp.isoformat()
                        if isinstance(log.timestamp, datetime)
                        else log.timestamp
                    ),
                    "Content Length": len(log.content),
                    "File Path": log.file_path or "",
                    "File Size": log.file_size or "",
                }

                if include_content:
                    row["Content"] = log.content[:32767]  # Excel cell limit

                data.append(row)

            df = pd.DataFrame(data)

            # Create Excel file in memory
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Logs", index=False)

                # Add some formatting
                worksheet = writer.sheets["Logs"]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except (AttributeError, TypeError, ValueError):
                            # Skip cells with problematic values
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

            output.seek(0)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

            return Response(
                output.getvalue(),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=logs_export_{timestamp}.xlsx"
                },
            )

        except ImportError:
            logger.error("openpyxl and pandas required for Excel export")
            return Response(
                "Excel export requires additional dependencies (openpyxl, pandas)",
                status=500,
                mimetype="text/plain",
            )
        except Exception as e:
            logger.error(f"Error creating Excel export: {e}")
            return Response(
                f"Error creating Excel export: {e}", status=500, mimetype="text/plain"
            )

    def export_logs_stream(self) -> Response:
        """
        Stream large log exports for better performance with large datasets.

        Expected JSON payload:
        {
            "filters": { ... },
            "format": "csv" | "json",
            "include_content": true | false,
            "chunk_size": 1000
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON payload required"}), 400

            export_format = data.get("format", "csv").lower()
            include_content = data.get("include_content", False)
            chunk_size = data.get("chunk_size", 1000)
            filter_data = data.get("filters", {})

            if export_format not in ["csv", "json"]:
                return jsonify({"error": "Streaming format must be csv or json"}), 400

            if chunk_size > 5000:
                return jsonify({"error": "Chunk size too large (max 5000)"}), 400

            # Build base filters
            base_filters = LogSearchFilters(
                business_id=filter_data.get("business_id"),
                log_type=filter_data.get("log_type"),
                start_date=self._parse_datetime(filter_data.get("start_date")),
                end_date=self._parse_datetime(filter_data.get("end_date")),
                search_query=filter_data.get("search_query"),
                limit=chunk_size,
                offset=0,
                sort_by="timestamp",
                sort_order="desc",
            )

            def generate_csv_stream():
                """Generator for CSV streaming."""
                # Write CSV header
                fieldnames = [
                    "id",
                    "business_id",
                    "log_type",
                    "timestamp",
                    "content_length",
                ]
                if include_content:
                    fieldnames.append("content")
                fieldnames.extend(["file_path", "file_size"])

                yield ",".join(fieldnames) + "\n"

                offset = 0
                while True:
                    base_filters.offset = offset
                    logs, total_count = self._fetch_logs(base_filters)

                    if not logs:
                        break

                    for log in logs:
                        row_data = [
                            str(log.id),
                            str(log.business_id),
                            log.log_type,
                            (
                                log.timestamp.isoformat()
                                if isinstance(log.timestamp, datetime)
                                else str(log.timestamp)
                            ),
                            str(len(log.content)),
                        ]

                        if include_content:
                            # Escape CSV content
                            content = log.content.replace('"', '""')
                            row_data.append(f'"{content}"')

                        row_data.extend([log.file_path or "", str(log.file_size or "")])

                        yield ",".join(row_data) + "\n"

                    offset += chunk_size

                    # Stop if we've processed all available logs
                    if len(logs) < chunk_size:
                        break

            def generate_json_stream():
                """Generator for JSON streaming."""
                yield '{"logs": [\n'

                offset = 0
                first_chunk = True

                while True:
                    base_filters.offset = offset
                    logs, total_count = self._fetch_logs(base_filters)

                    if not logs:
                        break

                    for i, log in enumerate(logs):
                        if not first_chunk or (first_chunk and offset > 0) or i > 0:
                            yield ",\n"

                        log_data = self._format_log_entry(log, include_content)
                        yield json.dumps(log_data, indent=2)

                        first_chunk = False

                    offset += chunk_size

                    # Stop if we've processed all available logs
                    if len(logs) < chunk_size:
                        break

                yield "\n]}"

            # Select appropriate generator
            if export_format == "csv":
                generator = generate_csv_stream()
                mimetype = "text/csv"
                filename = f"logs_export_stream_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            else:
                generator = generate_json_stream()
                mimetype = "application/json"
                filename = f"logs_export_stream_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

            return Response(
                generator,
                mimetype=mimetype,
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Cache-Control": "no-cache",
                },
            )

        except Exception as e:
            logger.error(f"Error streaming logs export: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def _calculate_log_stats(self) -> Dict[str, Any]:
        """Calculate statistical information about logs with caching."""
        try:
            # Check cache first
            cached_stats = self.cache.get_log_statistics()
            if cached_stats is not None:
                logger.debug("Cache hit for log statistics")
                return cached_stats

            # Cache miss - calculate from storage
            if hasattr(self.storage, "get_log_statistics"):
                stats = self.storage.get_log_statistics()

                # Cache the result
                self.cache.set_log_statistics(stats)
                logger.debug("Cached log statistics")
            else:
                # Fallback basic stats
                stats = {
                    "total_logs": 0,
                    "logs_by_type": {},
                    "logs_by_business": {},
                    "date_range": {},
                    "storage_usage": {},
                }
                logger.warning("Storage does not implement get_log_statistics method")

            return stats

        except Exception as e:
            logger.error(f"Error calculating log stats: {e}")
            return {}

    def _get_available_log_types(self) -> List[str]:
        """Get list of available log types."""
        try:
            if hasattr(self.storage, "get_available_log_types"):
                return self.storage.get_available_log_types()
            else:
                # Default log types
                return ["html", "llm", "raw_html", "enrichment"]

        except Exception as e:
            logger.error(f"Error getting log types: {e}")
            return []

    def _get_businesses_with_logs(self) -> List[Dict[str, Any]]:
        """Get list of businesses that have logs."""
        try:
            if hasattr(self.storage, "get_businesses_with_logs"):
                return self.storage.get_businesses_with_logs()
            else:
                # Fallback to get all businesses
                businesses = (
                    self.storage.get_all_businesses()
                    if hasattr(self.storage, "get_all_businesses")
                    else []
                )
                return [
                    {"id": b.get("id"), "name": b.get("name", "Unknown")}
                    for b in businesses
                ]

        except Exception as e:
            logger.error(f"Error getting businesses: {e}")
            return []

    def get_cache_stats(self) -> Response:
        """Get cache statistics and performance metrics."""
        try:
            cache_stats = self.cache.get_stats()

            response_data = {
                "cache_stats": cache_stats,
                "timestamp": datetime.utcnow().isoformat(),
            }

            return jsonify(response_data)

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def clear_cache(self) -> Response:
        """Clear the application cache."""
        try:
            cache_stats_before = self.cache.get_stats()
            self.cache.clear()

            logger.info("Cache cleared via API")

            return jsonify(
                {
                    "message": "Cache cleared successfully",
                    "stats_before_clear": cache_stats_before,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return jsonify({"error": "Internal server error"}), 500


# Flask app factory
def create_logs_app() -> Flask:
    """Create Flask app with Logs API."""
    app = Flask(__name__)

    # Configure app
    import os

    app.config["SECRET_KEY"] = os.environ.get(
        "FLASK_SECRET_KEY", "dev-key-not-for-production"
    )  # nosec
    app.config["JSON_SORT_KEYS"] = False

    # Initialize API
    logs_api = LogsAPI(app)

    @app.route("/api/health")
    def health_check():
        """Health check endpoint."""
        return jsonify(
            {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
        )

    @app.route("/")
    def index():
        """Root endpoint."""
        return jsonify(
            {
                "service": "LeadFactory Logs API",
                "version": "1.0.0",
                "endpoints": [
                    "/api/logs",
                    "/api/logs/search",
                    "/api/logs/export",
                    "/api/logs/stats",
                    "/api/logs/types",
                    "/api/businesses",
                ],
            }
        )

    return app


if __name__ == "__main__":
    # Development server
    import os

    app = create_logs_app()
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"  # nosec
    host = os.environ.get(
        "FLASK_HOST", "127.0.0.1"
    )  # Default to localhost for security
    port = int(os.environ.get("FLASK_PORT", "5000"))
    app.run(debug=debug_mode, host=host, port=port)  # nosec B104
