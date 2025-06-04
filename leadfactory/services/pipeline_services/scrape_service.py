"""
Scrape service for scalable pipeline architecture.

Microservice wrapper for the scraping pipeline stage that provides
HTTP API endpoints for distributed processing.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .base_service import BasePipelineService, ServiceConfig, TaskRequest

logger = logging.getLogger(__name__)


class ScrapeRequest(BaseModel):
    """Scrape request model."""

    zip_codes: List[str]
    verticals: List[str] = ["hvac", "plumber", "vet"]
    limit_per_zip: int = 50
    include_enrichment: bool = False
    priority: int = 5


class ScrapeResult(BaseModel):
    """Scrape result model."""

    businesses_scraped: int
    zip_codes_processed: List[str]
    verticals_processed: List[str]
    processing_stats: Dict[str, Any]
    business_ids: List[int]


class ScrapeService(BasePipelineService):
    """
    Scrape microservice for distributed lead scraping.

    Provides HTTP API endpoints for scraping business listings
    from multiple sources (Yelp, Google Places) with support
    for distributed processing and queue-based workflows.
    """

    def __init__(self, config: Optional[ServiceConfig] = None):
        """Initialize scrape service."""
        if config is None:
            config = ServiceConfig(service_name="scrape", port=8001)

        super().__init__(config)

        # Import pipeline modules (lazy loading)
        self._scraper = None
        self._initialize_scraper()

    def _initialize_scraper(self):
        """Initialize the scraper with lazy loading."""
        try:
            # Import the actual scraping module
            from leadfactory.pipeline.scrape import (
                get_zip_codes_to_process,
                scrape_google_places_businesses,
                scrape_yelp_businesses,
            )

            self._scrape_yelp = scrape_yelp_businesses
            self._scrape_google = scrape_google_places_businesses
            self._get_zip_codes = get_zip_codes_to_process

            logger.info("Scraper modules loaded successfully")

        except ImportError as e:
            logger.error(f"Failed to import scraper modules: {e}")
            self._scraper_available = False
        else:
            self._scraper_available = True

    async def _check_dependencies(self) -> Dict[str, str]:
        """Check scraper dependencies."""
        dependencies = await super()._check_dependencies()

        # Check API keys
        import os

        dependencies["yelp_api"] = "ok" if os.getenv("YELP_API_KEY") else "missing"
        dependencies["google_api"] = "ok" if os.getenv("GOOGLE_API_KEY") else "missing"
        dependencies["scraper_modules"] = "ok" if self._scraper_available else "error"

        return dependencies

    async def _process_task(self, request: TaskRequest) -> Dict[str, Any]:
        """Process a scraping task."""
        # Parse the request data as scrape parameters
        scrape_data = request.metadata or {}

        zip_codes = scrape_data.get("zip_codes", [])
        verticals = scrape_data.get("verticals", ["hvac", "plumber", "vet"])
        limit_per_zip = scrape_data.get("limit_per_zip", 50)

        if not zip_codes:
            # Get zip codes from database if not provided
            if hasattr(self, "_get_zip_codes"):
                zip_codes = await asyncio.get_event_loop().run_in_executor(
                    None, self._get_zip_codes, 10
                )
            else:
                raise ValueError("No zip codes provided and scraper not available")

        logger.info(
            f"Starting scrape task {request.task_id} for {len(zip_codes)} zip codes"
        )

        businesses_scraped = 0
        business_ids = []
        processing_stats = {
            "yelp_results": 0,
            "google_results": 0,
            "errors": 0,
            "duplicates": 0,
        }

        # Process each zip code and vertical combination
        for zip_code in zip_codes:
            for vertical in verticals:
                try:
                    # Scrape from Yelp
                    if hasattr(self, "_scrape_yelp"):
                        yelp_results = await asyncio.get_event_loop().run_in_executor(
                            None,
                            self._scrape_yelp,
                            zip_code,
                            vertical,
                            limit_per_zip // 2,  # Split between Yelp and Google
                        )
                        processing_stats["yelp_results"] += len(yelp_results)
                        business_ids.extend(
                            [b.get("id") for b in yelp_results if b.get("id")]
                        )

                    # Scrape from Google Places
                    if hasattr(self, "_scrape_google"):
                        google_results = await asyncio.get_event_loop().run_in_executor(
                            None,
                            self._scrape_google,
                            zip_code,
                            vertical,
                            limit_per_zip // 2,
                        )
                        processing_stats["google_results"] += len(google_results)
                        business_ids.extend(
                            [b.get("id") for b in google_results if b.get("id")]
                        )

                    businesses_scraped += (
                        processing_stats["yelp_results"]
                        + processing_stats["google_results"]
                    )

                except Exception as e:
                    logger.error(f"Error scraping {zip_code}/{vertical}: {e}")
                    processing_stats["errors"] += 1

        result = {
            "businesses_scraped": businesses_scraped,
            "zip_codes_processed": zip_codes,
            "verticals_processed": verticals,
            "processing_stats": processing_stats,
            "business_ids": business_ids[:1000],  # Limit response size
        }

        logger.info(
            f"Completed scrape task {request.task_id}: {businesses_scraped} businesses"
        )
        return result


def create_scrape_service() -> ScrapeService:
    """Factory function to create scrape service."""
    config = ServiceConfig(service_name="scrape", port=8001, debug=True)
    return ScrapeService(config)


if __name__ == "__main__":
    # Run the scrape service directly
    service = create_scrape_service()
    service.run()
