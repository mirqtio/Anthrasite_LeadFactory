"""
Scalable pipeline services package.

Provides microservices architecture for high-volume lead processing
with 10x capacity improvements through distributed processing.
"""

from .base_service import (
    BasePipelineService,
    ServiceConfig,
    ServiceRegistry,
    TaskRequest,
)
from .dedupe_service import DedupeService, create_dedupe_service
from .email_service import EmailService, create_email_service
from .enrich_service import EnrichService, create_enrich_service
from .kafka_integration import (
    KafkaManager,
    WorkflowManager,
    kafka_manager,
    workflow_manager,
)
from .mockup_service import MockupService
from .orchestrator import PipelineOrchestrator, orchestrator
from .performance_tests import CapacityValidator, PipelineLoadTester
from .score_service import ScoreService, create_score_service

# Service implementations
from .scrape_service import ScrapeService, create_scrape_service

__all__ = [
    # Core components
    "BasePipelineService",
    "ServiceConfig",
    "TaskRequest",
    "ServiceRegistry",
    "PipelineOrchestrator",
    "orchestrator",
    # Messaging and workflows
    "KafkaManager",
    "WorkflowManager",
    "kafka_manager",
    "workflow_manager",
    # Performance testing
    "PipelineLoadTester",
    "CapacityValidator",
    # Service implementations
    "ScrapeService",
    "EnrichService",
    "DedupeService",
    "ScoreService",
    "MockupService",
    "EmailService",
    # Service factories
    "create_scrape_service",
    "create_enrich_service",
    "create_dedupe_service",
    "create_email_service",
]


# Package metadata
__version__ = "1.0.0"
__author__ = "LeadFactory Team"
__description__ = "Scalable microservices architecture for lead processing pipeline"
