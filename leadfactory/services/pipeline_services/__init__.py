"""
Scalable pipeline services package.

Provides microservices architecture for high-volume lead processing
with 10x capacity improvements through distributed processing.
"""

from .base_service import BasePipelineService, ServiceConfig, TaskRequest, ServiceRegistry
from .orchestrator import PipelineOrchestrator, orchestrator
from .kafka_integration import KafkaManager, WorkflowManager, kafka_manager, workflow_manager
from .performance_tests import PipelineLoadTester, CapacityValidator

# Service implementations
from .scrape_service import ScrapeService, create_scrape_service
from .enrich_service import EnrichService, create_enrich_service
from .dedupe_service import DedupeService, create_dedupe_service
from .score_service import ScoreService, create_score_service
from .mockup_service import MockupService
from .email_service import EmailService, create_email_service


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