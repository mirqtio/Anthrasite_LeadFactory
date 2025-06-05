"""
Scraper microservice implementation.

Provides web scraping functionality as an independent service with
Kafka integration for async processing.
"""

import asyncio
import logging
from typing import Any, Dict

from leadfactory.pipeline.scrape import ScraperClient
from leadfactory.services.pipeline_services.base_service import (
    BasePipelineService,
    ServiceConfig,
)
from leadfactory.services.pipeline_services.kafka_integration import (
    PipelineMessage,
    kafka_manager,
)
from leadfactory.utils.metrics import get_metrics_client

logger = logging.getLogger(__name__)
metrics = get_metrics_client()


class ScraperService(BasePipelineService):
    """Scraper microservice implementation."""

    def __init__(self, config: ServiceConfig = None):
        """Initialize scraper service."""
        if config is None:
            config = ServiceConfig(
                service_name="scraper-service",
                service_version="1.0.0",
                port=8001,
            )

        super().__init__(config)
        self.scraper_client = ScraperClient()
        self.kafka_connected = False

    async def _process_task(self, request) -> dict[str, Any]:
        """Process a scraping task."""
        task_id = request.task_id

        try:
            # Extract parameters
            zip_codes = request.metadata.get("zip_codes", [])
            verticals = request.metadata.get("verticals", [])

            if not zip_codes or not verticals:
                raise ValueError("Missing required parameters: zip_codes and verticals")

            logger.info(
                f"Starting scrape task {task_id} for {len(zip_codes)} zip codes"
            )

            # Track metrics
            metrics.increment("scraper.tasks.started")
            start_time = asyncio.get_event_loop().time()

            # Perform scraping
            results = []
            total_businesses = 0

            for zip_code in zip_codes:
                for vertical in verticals:
                    try:
                        # Scrape businesses for this zip/vertical combination
                        businesses = await self._scrape_businesses(zip_code, vertical)

                        results.append(
                            {
                                "zip_code": zip_code,
                                "vertical": vertical,
                                "business_count": len(businesses),
                                "businesses": businesses,
                            }
                        )

                        total_businesses += len(businesses)

                        # Track per-vertical metrics
                        metrics.increment(
                            f"scraper.businesses.scraped.{vertical}", len(businesses)
                        )

                    except Exception as e:
                        logger.error(f"Error scraping {vertical} in {zip_code}: {e}")
                        results.append(
                            {
                                "zip_code": zip_code,
                                "vertical": vertical,
                                "error": str(e),
                            }
                        )

            # Calculate processing time
            processing_time = asyncio.get_event_loop().time() - start_time

            # Track completion metrics
            metrics.increment("scraper.tasks.completed")
            metrics.histogram("scraper.processing_time", processing_time)
            metrics.increment("scraper.businesses.total", total_businesses)

            # Publish results to Kafka for next stage
            if self.kafka_connected and total_businesses > 0:
                await self._publish_for_enrichment(task_id, results)

            return {
                "task_id": task_id,
                "zip_codes_processed": len(zip_codes),
                "verticals_processed": len(verticals),
                "total_businesses": total_businesses,
                "processing_time": processing_time,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Error processing scrape task {task_id}: {e}")
            metrics.increment("scraper.tasks.failed")
            raise

    async def _scrape_businesses(self, zip_code: str, vertical: str) -> list:
        """Scrape businesses for a specific zip code and vertical."""
        # Use the existing scraper client
        businesses = self.scraper_client.search_google_places(
            query=f"{vertical} near {zip_code}",
            location=zip_code,
        )

        # Also try Yelp
        yelp_businesses = self.scraper_client.search_yelp(
            term=vertical,
            location=zip_code,
        )

        # Combine and deduplicate results
        all_businesses = businesses + yelp_businesses

        # Basic deduplication by name/address
        seen = set()
        unique_businesses = []

        for business in all_businesses:
            key = (business.get("name", ""), business.get("address", ""))
            if key not in seen and key[0]:  # Ensure name exists
                seen.add(key)
                unique_businesses.append(business)

        return unique_businesses

    async def _publish_for_enrichment(self, task_id: str, results: list):
        """Publish scraping results for enrichment."""
        try:
            # Group businesses by batch for efficient processing
            batch_size = 50
            all_businesses = []

            for result in results:
                if "businesses" in result:
                    all_businesses.extend(result["businesses"])

            # Create batches
            for i in range(0, len(all_businesses), batch_size):
                batch = all_businesses[i : i + batch_size]

                await kafka_manager.publish_task(
                    task_type="enrich",
                    payload={
                        "parent_task_id": task_id,
                        "batch_index": i // batch_size,
                        "businesses": batch,
                    },
                    priority=3,  # Higher priority for workflow tasks
                )

            logger.info(f"Published {len(all_businesses)} businesses for enrichment")

        except Exception as e:
            logger.error(f"Error publishing to enrichment queue: {e}")

    async def start_kafka_consumer(self):
        """Start consuming from Kafka queue."""
        try:
            await kafka_manager.start()
            self.kafka_connected = True

            # Subscribe to scrape tasks
            await kafka_manager.subscribe_to_tasks(
                ["scrape"],
                self._handle_kafka_message,
                consumer_group="scraper_workers",
            )

        except Exception as e:
            logger.error(f"Error starting Kafka consumer: {e}")
            self.kafka_connected = False

    async def _handle_kafka_message(self, message: PipelineMessage):
        """Handle message from Kafka queue."""
        logger.info(f"Processing Kafka message: {message.message_id}")

        # Convert Kafka message to task request
        from leadfactory.services.pipeline_services.base_service import TaskRequest

        request = TaskRequest(
            task_id=message.message_id,
            priority=message.priority,
            metadata=message.payload,
        )

        # Process the task
        result = await self._process_task(request)

        # Handle workflow progression if needed
        if "execution_id" in message.payload:
            from leadfactory.services.pipeline_services.kafka_integration import (
                workflow_manager,
            )

            await workflow_manager.handle_stage_completion(message, result)


def create_scraper_service() -> ScraperService:
    """Factory function to create scraper service."""
    import os

    config = ServiceConfig(
        service_name="scraper-service",
        service_version="1.0.0",
        host="0.0.0.0",
        port=int(os.getenv("SERVICE_PORT", 8001)),
        enable_metrics=True,
        kafka_brokers=os.getenv("KAFKA_BROKERS", "localhost:9092"),
    )

    return ScraperService(config)


def main():
    """Main entry point for scraper service."""
    import asyncio

    service = create_scraper_service()

    # Start Kafka consumer in background
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if os.getenv("KAFKA_ENABLED", "true").lower() == "true":
        loop.create_task(service.start_kafka_consumer())

    # Run the FastAPI service
    service.run()


if __name__ == "__main__":
    main()
