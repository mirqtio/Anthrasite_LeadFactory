"""
Deduplication service for scalable pipeline architecture.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

from pydantic import BaseModel
from .base_service import BasePipelineService, ServiceConfig, TaskRequest


logger = logging.getLogger(__name__)


class DedupeService(BasePipelineService):
    """Deduplication microservice."""
    
    def __init__(self, config: Optional[ServiceConfig] = None):
        if config is None:
            config = ServiceConfig(service_name="dedupe", port=8003)
        super().__init__(config)
        self._initialize_dedupe()
    
    def _initialize_dedupe(self):
        try:
            from leadfactory.pipeline.dedupe_unified import process_deduplication
            self._process_dedupe = process_deduplication
            self._dedupe_available = True
        except ImportError as e:
            logger.error(f"Failed to import dedupe modules: {e}")
            self._dedupe_available = False
    
    async def _process_task(self, request: TaskRequest) -> Dict[str, Any]:
        """Process deduplication task."""
        dedupe_data = request.metadata or {}
        business_ids = dedupe_data.get("business_ids", [])
        
        if not business_ids and hasattr(self, '_process_dedupe'):
            # Process all businesses needing deduplication
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._process_dedupe, {"limit": 1000}
            )
        else:
            # Mock deduplication for testing
            await asyncio.sleep(0.5)
            result = {
                "duplicates_found": len(business_ids) // 10,
                "businesses_processed": len(business_ids),
                "merges_performed": len(business_ids) // 20
            }
        
        return result


def create_dedupe_service() -> DedupeService:
    config = ServiceConfig(service_name="dedupe", port=8003, debug=True)
    return DedupeService(config)