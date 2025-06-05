"""
API response optimization utilities.

Provides response compression, pagination, and field filtering for
optimal API performance.
"""

import gzip
import io
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Union

from fastapi import Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger(__name__)


@dataclass
class PaginationParams:
    """Pagination parameters for API responses."""

    limit: int = Query(default=50, ge=1, le=1000, description="Items per page")
    offset: int = Query(default=0, ge=0, description="Number of items to skip")
    cursor: Optional[str] = Query(
        default=None, description="Cursor for cursor-based pagination"
    )

    @property
    def use_cursor(self) -> bool:
        """Check if cursor-based pagination should be used."""
        return self.cursor is not None


@dataclass
class FieldSelection:
    """Field selection parameters for API responses."""

    fields: Optional[str] = Query(
        default=None, description="Comma-separated list of fields to include"
    )
    exclude: Optional[str] = Query(
        default=None, description="Comma-separated list of fields to exclude"
    )

    def get_fields_set(self) -> Optional[Set[str]]:
        """Get set of fields to include."""
        if self.fields:
            return set(field.strip() for field in self.fields.split(","))
        return None

    def get_exclude_set(self) -> Optional[Set[str]]:
        """Get set of fields to exclude."""
        if self.exclude:
            return set(field.strip() for field in self.exclude.split(","))
        return None


class ResponseOptimizer:
    """Optimizes API responses for performance."""

    def __init__(self):
        """Initialize response optimizer."""
        self.compression_threshold = 1024  # Compress responses larger than 1KB
        self.max_response_size = 10 * 1024 * 1024  # 10MB max response size

    def filter_fields(
        self,
        data: Union[Dict, List[Dict]],
        fields: Optional[Set[str]] = None,
        exclude: Optional[Set[str]] = None,
    ) -> Union[Dict, List[Dict]]:
        """Filter response fields based on selection criteria."""
        if isinstance(data, list):
            return [self._filter_dict(item, fields, exclude) for item in data]
        else:
            return self._filter_dict(data, fields, exclude)

    def _filter_dict(
        self,
        data: Dict[str, Any],
        fields: Optional[Set[str]] = None,
        exclude: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Filter a single dictionary."""
        if not fields and not exclude:
            return data

        result = {}

        if fields:
            # Include only specified fields
            for field in fields:
                if "." in field:
                    # Handle nested fields
                    parts = field.split(".", 1)
                    if parts[0] in data:
                        if isinstance(data[parts[0]], dict):
                            nested = self._filter_dict(data[parts[0]], {parts[1]}, None)
                            if nested:
                                result[parts[0]] = nested
                        else:
                            result[parts[0]] = data[parts[0]]
                elif field in data:
                    result[field] = data[field]
        else:
            # Include all fields except excluded
            result = data.copy()

        # Remove excluded fields
        if exclude:
            for field in exclude:
                if "." in field:
                    # Handle nested exclusions
                    parts = field.split(".", 1)
                    if parts[0] in result and isinstance(result[parts[0]], dict):
                        result[parts[0]] = self._filter_dict(
                            result[parts[0]], None, {parts[1]}
                        )
                else:
                    result.pop(field, None)

        return result

    def paginate_response(
        self,
        items: List[Any],
        total: int,
        pagination: PaginationParams,
        request: Request,
    ) -> Dict[str, Any]:
        """Create paginated response with metadata."""
        if pagination.use_cursor:
            # Cursor-based pagination
            next_cursor = None
            if len(items) == pagination.limit:
                # Generate next cursor from last item
                last_item = items[-1]
                next_cursor = self._generate_cursor(last_item)

            return {
                "data": items,
                "pagination": {
                    "cursor": pagination.cursor,
                    "next_cursor": next_cursor,
                    "has_more": len(items) == pagination.limit,
                    "limit": pagination.limit,
                },
            }
        else:
            # Offset-based pagination
            has_next = pagination.offset + len(items) < total
            has_prev = pagination.offset > 0

            # Generate URLs
            base_url = str(request.url).split("?")[0]
            query_params = dict(request.query_params)

            links = {}
            if has_next:
                query_params["offset"] = pagination.offset + pagination.limit
                links["next"] = f"{base_url}?{self._build_query_string(query_params)}"

            if has_prev:
                query_params["offset"] = max(0, pagination.offset - pagination.limit)
                links["prev"] = f"{base_url}?{self._build_query_string(query_params)}"

            return {
                "data": items,
                "pagination": {
                    "total": total,
                    "limit": pagination.limit,
                    "offset": pagination.offset,
                    "has_next": has_next,
                    "has_prev": has_prev,
                },
                "links": links,
            }

    def _generate_cursor(self, item: Any) -> str:
        """Generate cursor from item."""
        # Simple cursor based on ID and timestamp
        cursor_data = {
            "id": getattr(item, "id", None),
            "created_at": str(getattr(item, "created_at", "")),
        }

        import base64

        cursor_json = json.dumps(cursor_data, separators=(",", ":"))
        return base64.urlsafe_b64encode(cursor_json.encode()).decode()

    def _build_query_string(self, params: Dict[str, Any]) -> str:
        """Build query string from parameters."""
        from urllib.parse import urlencode

        return urlencode(params)

    def compress_response(
        self, content: Union[str, bytes], request: Request
    ) -> Optional[Response]:
        """Compress response if client supports it."""
        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return None

        # Check if content is large enough to compress
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content

        if len(content_bytes) < self.compression_threshold:
            return None

        # Compress content
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
            gz.write(content_bytes)

        compressed = buffer.getvalue()

        # Only use compression if it reduces size
        if len(compressed) >= len(content_bytes):
            return None

        return Response(
            content=compressed,
            media_type="application/json",
            headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"},
        )

    def create_optimized_response(
        self,
        data: Any,
        request: Request,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        """Create an optimized response with compression and caching headers."""
        # Convert data to JSON
        content = json.dumps(data, separators=(",", ":"))

        # Check response size
        if len(content) > self.max_response_size:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Response too large",
                    "max_size": self.max_response_size,
                },
            )

        # Try to compress
        compressed_response = self.compress_response(content, request)
        if compressed_response:
            if headers:
                compressed_response.headers.update(headers)
            return compressed_response

        # Return uncompressed response
        response = Response(
            content=content, status_code=status_code, media_type="application/json"
        )

        if headers:
            response.headers.update(headers)

        return response

    def add_cache_headers(
        self,
        response: Response,
        max_age: int = 60,
        private: bool = False,
        must_revalidate: bool = True,
    ) -> Response:
        """Add cache control headers to response."""
        cache_control_parts = []

        if private:
            cache_control_parts.append("private")
        else:
            cache_control_parts.append("public")

        cache_control_parts.append(f"max-age={max_age}")

        if must_revalidate:
            cache_control_parts.append("must-revalidate")

        response.headers["Cache-Control"] = ", ".join(cache_control_parts)

        # Add ETag for conditional requests
        import hashlib

        etag = hashlib.md5(response.body, usedforsecurity=False).hexdigest()
        response.headers["ETag"] = f'"{etag}"'

        return response


# Global response optimizer instance
response_optimizer = ResponseOptimizer()


# FastAPI dependencies
async def get_pagination_params(
    limit: int = Query(default=50, ge=1, le=1000, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    cursor: Optional[str] = Query(default=None, description="Cursor for pagination"),
) -> PaginationParams:
    """Get pagination parameters from query."""
    return PaginationParams(limit=limit, offset=offset, cursor=cursor)


async def get_field_selection(
    fields: Optional[str] = Query(None, description="Fields to include"),
    exclude: Optional[str] = Query(None, description="Fields to exclude"),
) -> FieldSelection:
    """Get field selection parameters from query."""
    return FieldSelection(fields=fields, exclude=exclude)


# Example usage in FastAPI
def create_paginated_endpoint(router):
    """Example of creating an optimized paginated endpoint."""
    from fastapi import Depends

    @router.get("/businesses")
    async def list_businesses(
        request: Request,
        pagination: PaginationParams = Depends(get_pagination_params),
        fields: FieldSelection = Depends(get_field_selection),
        vertical: Optional[str] = Query(None, description="Filter by vertical"),
        zip_code: Optional[str] = Query(None, description="Filter by ZIP code"),
    ):
        # Get data from database
        query_filters = {}
        if vertical:
            query_filters["vertical"] = vertical
        if zip_code:
            query_filters["zip"] = zip_code

        # Get total count
        total = await get_business_count(query_filters)

        # Get paginated data
        businesses = await get_businesses(
            filters=query_filters, limit=pagination.limit, offset=pagination.offset
        )

        # Filter fields
        fields_set = fields.get_fields_set()
        exclude_set = fields.get_exclude_set()

        filtered_businesses = response_optimizer.filter_fields(
            businesses, fields=fields_set, exclude=exclude_set
        )

        # Create paginated response
        response_data = response_optimizer.paginate_response(
            items=filtered_businesses,
            total=total,
            pagination=pagination,
            request=request,
        )

        # Create optimized response with caching
        response = response_optimizer.create_optimized_response(
            data=response_data, request=request
        )

        # Add cache headers
        response = response_optimizer.add_cache_headers(
            response, max_age=300, private=False  # Cache for 5 minutes
        )

        return response


# Placeholder functions for example
async def get_business_count(filters: dict) -> int:
    """Get count of businesses matching filters."""
    # Implementation would query database
    return 100


async def get_businesses(filters: dict, limit: int, offset: int) -> List[dict]:
    """Get businesses with pagination."""
    # Implementation would query database
    return [
        {
            "id": i,
            "name": f"Business {i}",
            "address": f"{i} Main St",
            "phone": f"555-{i:04d}",
            "email": f"business{i}@example.com",
            "metadata": {"created_at": "2024-01-01", "updated_at": "2024-01-02"},
        }
        for i in range(offset, min(offset + limit, 100))
    ]
